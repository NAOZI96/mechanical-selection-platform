# 方案 A 计算规格——绞车与卷筒选型助手

文档版本：0.1.0  
拟定计算模型版本：`winch_drum.calc.1.0.0`  
状态：Phase 0；带“待确认”的项目不得在 Phase 1 中静默设默认值

## 1. 范围、结论等级与基本假设

本规格只覆盖准静态功率、规则密排条件下的逐层几何容绳、转速/减速比和静态保持制动力矩参考。它不覆盖绳强度、卷筒结构强度、启动冲击、加速度、热平衡、工作制、排绳质量、入绳偏角、压绳、多层乱绳、绳压变形、Lebus 绳槽、制动热容量或失效安全设计。

结果等级：

- `calculated`：在本模型及输入假设内由确定公式计算的值；不等于真实设备的测量真值。
- `preliminary`：可用于方案初选，但依赖设备策略、标准系列、制造约束或未建模工况。
- `review_required`：当前信息不足，不应自动给出数值，显示“待工程师确认”。
- `informational`：换算或提示，不参与核心定型。

基本假设：单根圆截面缆绳、各层规则排列、相邻圈轴向节距恒定、每增加一层绳中心半径增加一个绳径、无交叉压陷/弹性压缩/绳槽特殊几何、绳速定义为卷筒处绳速。任何不满足均需人工复核。

## 2. 输入符号、单位、默认值与边界

所有 API 数值必须是有限实数，禁止 NaN/Infinity。表中“默认值”仅表示产品行为；“无”表示必须显式输入，“待确认”表示不得擅自写入数值默认。

| API 字段 | 符号 | 显示单位 | SI 单位 | 默认值 | 硬边界/校验 | 说明 |
|---|---|---:|---:|---|---|---|
| `rated_line_pull_kn` | `F_r` | kN | N | 无 | `> 0` | 卷筒处额定绳张力，不是载荷端重量。 |
| `rope_diameter_mm` | `d` | mm | m | 无 | `> 0` | 仅几何用途；绳型/结构缺失会触发警告。 |
| `rope_speed_m_per_min` | `v` | m/min | m/s | 无 | `> 0` | 卷筒处目标绳速。 |
| `target_rope_capacity_m` | `L_t` | m | m | 无 | `> 0` | 不自动增加死圈或外部余绳。 |
| `service_factor` | `K_s` | — | — | 无 | `>= 1` | 驱动设计拉力使用；来源须确认。 |
| `total_efficiency` | `η` | — | — | 无 | `0 < η <= 1` | 正向：电机至卷筒。 |
| `motor_rated_speed_rpm` | `n_m` | r/min | rad/s 可派生 | 无 | `> 0` | 用于速比参考。 |
| `motor_type` | — | 文本/枚举 | — | 无 | 1–64 字符 | 仅提示，不映射系数。 |
| `drum_core_diameter_mm` | `D_c` | mm | m | `null` | 若有则 `> 0` | 裸卷筒外径；非绳中心线直径。 |
| `drum_face_length_mm` | `B` | mm | m | `null` | 若有则 `> 0` | 两法兰内侧总轴向排绳面长度，包含余量。 |
| `max_layers` | `z_max` | 层 | — | 无 | 整数 `>= 1` | 产品上限建议 100，防止滥用和资源异常。 |
| `pitch_factor` | `K_p` | — | — | 无 | `>= 1` | `p=K_p d`；具体值需结合绳槽/排绳确认。 |
| `side_margin_mm` | `b` | mm/侧 | m | 无 | `>= 0` | 两侧各扣除一次。 |
| `reeving_ratio` | `M` | — | — | 无 | `>= 1` | 可允许小数但 UI 默认整数；仅换算提示。 |
| `brake_safety_factor` | `K_b` | — | — | 无 | `>= 1` | 静态保持制动使用。 |
| `duty_class` | — | 文本/枚举 | — | 无 | 1–64 字符 | 仅提示，不自动映射 `K_s`。 |
| `approved_core_ratio` | `R_Dd` | — | — | `null` | 若有则 `> 0` | 可选高级字段；必须标记来源/批准，Phase 0 不设数值。 |
| `dead_wraps` | `N_dead` | 圈 | — | `0`（MVP 范围假设） | 整数 `>= 0` | MVP UI 可不开放；若项目要求保留死圈，应在 Phase 1 纳入。该默认需用户确认。 |
| `allow_forward_efficiency_as_reverse_approx` | — | 布尔 | — | `false` | true/false | 安全默认：不允许正向效率静默替代反向效率。 |

建议 UI 软边界仅用于异常提示，不作为工程标准：数值超过产品配置上限时返回“超出已验证范围”，而非声称不合格。硬边界之外，还需满足：`B - 2b > 0`、可用宽度至少容纳 1 圈、计算层数不超过 `z_max`。

## 3. SI 规范化

| ID | 公式 | 结果 |
|---|---|---|
| `UNIT-001` | `F_r = rated_line_pull_kn × 1000` | N |
| `UNIT-002` | `d = rope_diameter_mm / 1000` | m |
| `UNIT-003` | `v = rope_speed_m_per_min / 60` | m/s |
| `UNIT-004` | `D_c = drum_core_diameter_mm / 1000` | m |
| `UNIT-005` | `B = drum_face_length_mm / 1000` | m |
| `UNIT-006` | `b = side_margin_mm / 1000` | m |

原始值、显示单位、SI 值和换算公式 ID 均进入快照。计算过程中不得混用 mm 与 m。

## 4. 计算顺序与公式

### 4.1 输入语义与可计算性门禁

1. 校验额定拉力与速度均指卷筒绳端；如用户选择“载荷端”，MVP 阻断并要求先换算，不能只除以倍率而忽略滑轮效率。
2. 若 `D_c` 缺失且 `R_Dd` 缺失，芯径建议为 `review_required`，所有依赖芯径的几何、转速和制动力矩结果不可计算。
3. 若 `D_c` 存在而 `B` 缺失，可按目标容量和最大层数反求最小面长。
4. 若 `B` 存在而 `D_c` 缺失，不能仅凭容量反求唯一芯径，因为弯曲比和绳结构约束缺失。
5. 若二者均存在，校核容量；不足时返回明确不足与最大可容长度，不自动改变输入。

### 4.2 驱动拉力和功率

| ID | 公式 | 符号/单位 | 等级 | 适用条件 |
|---|---|---|---|---|
| `FORCE-001` | `F_d = F_r K_s` | `F_d` 设计绳张力，N | calculated | 准静态；`K_s` 已由工程师确认且只在此处使用。 |
| `POWER-001` | `P_load = F_d v` | `P_load` 理论负载功率，W | calculated | 卷筒处机械功率，不含效率。 |
| `POWER-002` | `P_motor_min = P_load / η` | 最低所需电机机械功率，W | calculated | `η` 为正向总效率。 |
| `POWER-003` | `P_motor_suggested >= P_motor_min` | 建议电机功率（标准额定档位），W | preliminary | 需经批准的标准功率系列、工作制、热容量、启动/过载与环境条件；没有系列时只输出下限。 |

“理论负载功率”采用设计拉力而非额定拉力，名称和报告须明确。若产品还要展示额定工况功率，可另列 `F_r v`，不得与 `POWER-001` 混称。

### 4.3 卷筒芯径

| ID | 公式 | 等级 | 说明 |
|---|---|---|---|
| `DRUM-001` | 若输入 `D_c`：`D_c,used = D_c` | calculated（输入回显） | 只表示采用输入值，不代表合规。 |
| `DRUM-002` | 若无 `D_c` 且有经批准 `R_Dd`：`D_c,suggested = R_Dd d` | preliminary | `R_Dd` 的标准/供应商/项目来源必须保存在假设中。 |
| `DRUM-003` | 若两者皆无：不返回数值 | review_required | 显示“缺少绳结构、材料、允许弯曲比或批准标准”。 |

不得内置或声称某个 D/d 比适用于所有钢丝绳、合成绳或工作级别。

### 4.4 节距、可用宽度和每层圈数

| ID | 公式 | 单位 | 等级 | 边界 |
|---|---|---:|---|---|
| `GEOM-001` | `p = K_p d` | m | calculated | `K_p >= 1`。 |
| `GEOM-002` | `B_u = B - 2b` | m | calculated | 必须 `B_u > 0`。 |
| `GEOM-003` | `N_full = floor((B_u + ε) / p)` | 圈/完整层 | calculated | `N_full >= 1`；`ε` 仅为浮点容差，不得增加物理宽度。 |
| `GEOM-004` | `B_used = N_full p` | m | calculated | 应满足 `B_used <= B_u + ε`。 |

每层几何容量默认使用相同完整圈数。`N_dead` 若启用，只从第一层可用容绳中扣除相应圈数，但仍占用空间。

### 4.5 逐层离散容绳量

层号 `j = 1...z_max`。卷筒芯径是裸筒外径；第 `j` 层绳中心线工作直径为：

| ID | 公式 | 单位 | 等级 |
|---|---|---:|---|
| `CAP-001` | `D_j = D_c + (2j - 1)d` | m | calculated |
| `CAP-002` | `l_turn,j = sqrt((πD_j)^2 + p^2)` | m/圈 | calculated |
| `CAP-003` | `L_layer,j,gross = N_full l_turn,j` | m | calculated |
| `CAP-004` | 第一层：`L_layer,1,usable = max(0, (N_full-N_dead) l_turn,1)`；其余层等于 gross | m | calculated |
| `CAP-005` | `L_total,k = Σ(j=1..k) L_layer,j,usable` | m | calculated |

这是按每圈螺旋中心线长度计算的逐层离散模型，不使用卷筒包络总体积估算。

实际使用层数与末层圈数：找到最小 `k` 使 `L_total,k >= L_t`。此前完整使用各层；最后一层需求长度 `L_need,k = L_t - L_total,k-1`，末层使用圈数可报告为连续值 `N_used,k = L_need,k / l_turn,k`，制造/排绳占位建议另报告向上取整圈数 `ceil(N_used,k)`。若直到 `z_max` 仍不足，则工程结论为“容量不足”，整体请求仍可保存为 `completed_with_warnings`，并返回最大容量与缺口。

| ID | 公式 | 单位 | 等级 |
|---|---|---:|---|
| `CAP-006` | `z_actual = min{k | L_total,k >= L_t}` | 层 | calculated |
| `CAP-007` | `L_margin = L_total,z_actual - L_t` | m | calculated |
| `CAP-008` | `capacity_margin_pct = 100 L_margin / L_t` | % | calculated |

“总容绳量”必须同时标明口径：完整实际层容量或最大层数容量。API 分别命名为 `capacity_at_actual_layers_m` 和 `capacity_at_max_layers_m`，不得只用模糊的 `total_capacity`。

若 `z_max` 内无法满足目标，则 `capacity_satisfied=false`、`actual_layers=null`、`capacity_at_actual_layers_m=null`；另返回 `evaluated_layers=z_max`、`capacity_at_max_layers_m` 和 `capacity_shortfall_m=L_t-L_total,z_max`。此时“满卷工作直径/转速”以允许的最大层数 `z_max` 计算并在字段说明中标为 `max_layer_working_*`，不得伪称已满足目标的实际满卷值。

### 4.6 反求建议卷筒面长

条件：已知 `D_c`、`d`、`K_p`、`L_t`、`z_max` 和 `b`，且 `B` 未提供。`D_c` 必须来自用户输入或经批准的 `R_Dd`；优化器不得自行发明通用 D/d。优化器只枚举有限集合 `z = 1..z_max`（`z_max<=100`）。对每个候选层数求最小整数完整层圈数 `N_req,z`，使：

`Σ(j=1..z) max(0, N_req,z - I[j=1]N_dead) l_turn,j >= L_t`

`N_req,z` 由容量线性关系直接向上取整并做一次浮点边界校正，不使用无界循环。每个候选组合均计算：

| ID | 公式 | 单位 | 等级 |
|---|---|---:|---|
| `WIDTH-001` | `B_u,min,z = N_req,z p` | m | preliminary |
| `WIDTH-002` | `B_suggested = B_u,min + 2b` | m | preliminary |

当前版本使用 `B_suggested × (D_c + 2zd)^2` 作为透明的圆柱包络紧凑度代理量排序，并以面长、外包络直径和层数作确定性次级排序。该代理量不是质量、成本、强度或产品标准；返回完整候选列表和选中理由。建议面长是规则排绳几何下的最小值，不含法兰厚度、制造余量、排绳器行程余量、入绳偏角和附加工程裕度，必须人工复核。若产品决定加入容量裕量，必须增加独立输入 `capacity_design_margin`，不得偷偷并入 `K_p` 或两侧余量。

### 4.7 工作直径、卷筒转速和减速比

| ID | 公式 | 单位 | 等级 | 说明 |
|---|---|---:|---|---|
| `SPEED-001` | `D_work,empty = D_c + d` | m | calculated | 第一层绳中心线直径。 |
| `SPEED-002` | `D_work,full = D_c + (2z_actual-1)d` | m | calculated | 实际最外层绳中心线直径。 |
| `SPEED-003` | `n_drum = 60v/(πD_work)` | r/min | calculated | 以给定绳速反求卷筒转速。 |
| `SPEED-004` | `n_empty = 60v/(πD_work,empty)` | r/min | calculated | 空卷目标转速。 |
| `SPEED-005` | `n_full = 60v/(πD_work,full)` | r/min | calculated | 满卷目标转速。 |
| `RATIO-001` | `i_empty = n_m/n_empty`；`i_full = n_m/n_full` | — | preliminary | 保持恒绳速所需速比范围。 |
| `RATIO-002` | `D_ref=(D_work,empty+D_work,full)/2`；`n_ref=60v/(πD_ref)`；`i_ref=n_m/n_ref` | — | preliminary | 仅作名义参考；最终应由控制策略确定。 |

固定速比和固定电机转速无法同时保证空卷、满卷绳速恒定。系统必须给出速比范围及警告；若采用变频/液压调速，应在详细设计中确认转速范围、恒功率/恒转矩能力。不得将 `i_ref` 直接称为“最终减速比”。

### 4.8 制动力矩

MVP 把 `F_r` 视为静态保持基准，不再乘 `K_s`，再单独乘制动安全系数 `K_b`，避免默认重复使用安全系数。按最不利实际满卷工作直径计算：

| ID | 公式 | 单位 | 等级 | 说明 |
|---|---|---:|---|---|
| `BRAKE-001` | `T_brake,low = F_r (D_work,full/2) K_b` | N·m | preliminary | 低速轴静态保持参考；不含动态制动和惯性。 |
| `BRAKE-002` | `T_brake,high,ref = T_brake,low/(i_ref η_back)` | N·m | preliminary | 仅当制动器位于高速轴；`η_back` 为反向传动效率。 |

当前输入只有正向总效率 `η`，没有 `η_back`。因此 Phase 1 的严谨行为应是：高速轴结果默认 `review_required`；只有 `allow_forward_efficiency_as_reverse_approx=true` 且用户显式确认时，才令 `η_back=η` 并输出带高严重度警告的参考值。不能无提示套用。

还应提示：制动器额定/动态扭矩、热容量、响应时间、失电抱闸、冗余、安装位置、齿轮间隙、回程效率和适用安全标准均未核验。

### 4.9 滑轮组倍率提示

在忽略滑轮摩擦且 `M` 定义为承载绳段数的理想模型下：

| ID | 公式 | 等级 |
|---|---|---|
| `REEVE-001` | `F_load,ideal = M F_r` | informational |
| `REEVE-002` | `v_load,ideal = v/M` | informational |

这两个值不得反馈到 `FORCE-001`，否则会把倍率重复计入。真实载荷端能力需要滑轮效率、绳路、运动端定义及自重，当前输入不足。

## 5. 输出清单与分类

| 输出字段 | 公式 ID | 分类 |
|---|---|---|
| `design_line_pull_n` | `FORCE-001` | calculated |
| `theoretical_load_power_w` | `POWER-001` | calculated |
| `minimum_motor_power_w` | `POWER-002` | calculated |
| `suggested_motor_power_w` | `POWER-003` | preliminary 或 review_required |
| `used_or_suggested_core_diameter_m` | `DRUM-001/002/003` | calculated-input / preliminary / review_required |
| `suggested_drum_face_length_m` | `WIDTH-002` | preliminary |
| `actual_layers`（实际缠绕层数） | `CAP-006` | calculated |
| `turns_per_full_layer` | `GEOM-003` | calculated |
| `layer_details[]` | `CAP-001..005` | calculated |
| `capacity_at_actual_layers_m` | `CAP-005` | calculated |
| `capacity_at_max_layers_m` | `CAP-005` | calculated |
| `capacity_margin_m/pct` | `CAP-007/008` | calculated |
| `empty/full_working_diameter_m` | `SPEED-001/002` | calculated |
| `empty/full_drum_speed_rpm` | `SPEED-004/005` | calculated |
| `reference_ratio` 与范围 | `RATIO-001/002` | preliminary |
| `low_speed_brake_torque_nm` | `BRAKE-001` | preliminary |
| `high_speed_brake_torque_ref_nm` | `BRAKE-002` | review_required；确认近似后 preliminary |

## 6. 警告代码

| 代码 | 严重度 | 触发条件 |
|---|---|---|
| `W_INPUT_SCOPE` | high | 额定拉力/速度并非明确的卷筒绳端量。 |
| `W_CORE_RULE_MISSING` | high | 芯径和批准 D/d 规则均缺失。 |
| `W_CORE_UNVERIFIED` | high | 采用的用户芯径或 D/d 来源仍未完成绳型、强度和弯曲比核验。 |
| `W_CAPACITY_INSUFFICIENT` | high | 最大层数下容量小于目标。 |
| `W_FIXED_RATIO_SPEED_VARIATION` | medium | 空满卷要求的速比不同。 |
| `W_MOTOR_SELECTION_INCOMPLETE` | high | 缺工作制/标准系列/启动与热校核。 |
| `W_BRAKE_STATIC_ONLY` | high | 制动结果仅为静态保持参考。 |
| `W_REVERSE_EFFICIENCY_UNKNOWN` | high | 未提供反向效率。 |
| `W_REVERSE_EFFICIENCY_APPROXIMATED` | high | 用户明确允许用正向效率近似反向效率。 |
| `W_SERVICE_FACTOR_SOURCE` | medium | 使用系数来源未记录。 |
| `W_PITCH_FACTOR_SOURCE` | medium | 节距系数来源未记录。 |
| `W_DUTY_CLASS_INFO_ONLY` | medium | 工作级别未参与自动计算。 |
| `W_ROPE_STRENGTH_NOT_CHECKED` | high | 所有计算均提示绳强度未校核。 |
| `W_DRUM_STRUCTURE_NOT_CHECKED` | high | 卷筒结构/法兰/轴承等未校核。 |
| `W_DEAD_WRAPS_ASSUMED_ZERO` | medium | `N_dead=0`。 |
| `W_VALIDATED_RANGE_EXCEEDED` | medium | 输入超出已测试的产品软边界。 |

警告代码及触发逻辑属于计算模型版本的一部分；文案可本地化，但不得改变含义。

## 7. 当前输入充分性检查

### 7.1 足够完成

- 在芯径和面长均已提供时：设计拉力、最低功率、逐层理论容量、空满卷工作直径/目标转速和参考速比。
- 芯径已提供、面长缺失时：按已给最大层数反求规则几何最小面长。
- 低速轴静态保持力矩参考（仍需人工复核）。

### 7.2 不足或语义需确认

- 芯径建议：缺绳类型、结构、材料、最小弯曲比及适用标准/供应商要求。
- 电机额定功率定型：缺工作制、负载谱、启动次数、加速度、环境、供电、过载与标准功率系列。
- 高速轴制动力矩：缺反向效率、真实速比、制动器位置和动态/热工况。
- 滑轮组真实载荷能力：缺各滑轮效率、承载绳段定义、运动端、自重与摩擦。
- 容绳可制造性：缺绳槽形式、绳槽几何、法兰高度、死圈、排绳器、入绳角及绳压缩数据。
- 结构安全：缺材料、许用应力、壁厚、法兰、焊缝、轴承跨距、轴载荷、疲劳和法规/标准。

建议 Phase 1 把 `rope_type/rope_construction`、`dead_wraps`、`input_force_basis`、`input_speed_basis` 和 `assumption_sources` 至少作为显式字段或阻断确认项；否则“芯径建议”和制动结果只能保持待确认。

## 8. 潜在重复安全系数检查

1. `K_s` 仅用于 `F_d` 与驱动功率，不默认用于 `BRAKE-001`。
2. `K_b` 仅用于制动保持基准；默认基准是 `F_r`。若项目规定基准必须用 `F_d`，须新增枚举 `brake_force_basis=rated|design`，报告展示所选口径，禁止同时暗乘。
3. `M` 不作用于已定义为绳张力的 `F_r`；仅做载荷端理想换算。
4. 电机标准功率向上取整不是新的安全系数，必须与 `K_s` 分开报告。
5. 容量余量不得隐含在节距系数、两侧余量或目标长度中；如需要，设独立字段。
6. 若额定拉力来源本身已含冲击/安全系数，用户必须记录来源；系统无法自行拆分，应警告潜在重复。

## 9. 舍入、比较与报告

- 所有中间计算使用未舍入值；只有显示层舍入。
- 建议显示：力 0.01 kN、功率 0.01 kW、长度/直径 0.1 mm 或 0.001 m、转速 0.01 r/min、速比 0.001、力矩 0.01 N·m/kN·m；这些显示位数待确认，不影响快照原值。
- `floor` 前使用量级相关且经测试的极小容差 `ε`，具体实现和测试必须冻结，防止恰好整圈时因二进制误差少算一圈。
- PDF/HTML 必须展示关键参数汇总表、参数警告、公式 ID、符号定义、原始输入、SI 输入、代入值、结果等级、假设、模型版本和免责声明。

## 10. 免责声明基线

“本报告为基于所填数据和所列假设的工程计算与初选辅助结果，不构成制造、采购、施工或安全认证依据。钢丝绳/缆绳强度、卷筒结构、制动动态与热容量、传动系统、工作制、环境条件及适用标准尚需具备资质的工程师和供应商复核。输入或模型假设变化时应重新计算。”
