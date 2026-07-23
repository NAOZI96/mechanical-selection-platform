# 方案 A 计算规格——绞车与卷筒选型助手

自动化证据索引见 [`FORMULA_TEST_MATRIX.md`](FORMULA_TEST_MATRIX.md)。矩阵通过只证明软件与本规格一致，不替代本规格及参数来源的机械工程签字。

文档版本：0.2.0

计算模型版本：`winch_drum.calc.1.1.0`
状态：C-01～C-09 项目决策已冻结，Phase 2R 一致性复审已完成

## C-01～C-07 冻结决策（与历史段落冲突时以本节为准）

- C-01：`m=v_drum/v_load>=1`。载荷端输入时 `F_drum=F_load/(m*η_pulley)`、`v_drum=m*v_load`，卷筒端输入直接采用；所有后续计算只用换算后的卷筒端值。`m>1` 使用默认效率 0.95 时产生 `W_PULLEY_EFFICIENCY_DEFAULT`。
- C-02：`B_effective=B-2*b_side>0`。实际可用槽数优先；其次实际槽距；否则 `p=pitch_factor*d`、`N=floor(B_effective/p)`。同时输出理论圈数、最终圈数和依据。
- C-03：死圈允许 2～8，默认 3。`L_required_total=L_target+L_dead_wrap+L_termination_allowance`；死圈按第一层绳中心螺旋圈长计算；`L_available_work=L_total_capacity-L_dead_wrap-L_termination_allowance`。目标工作绳长不含死圈和安装预留。
- C-04：允许绳径 4～64 mm，主要验证 6～32 mm。`D=D_core+d`、`D/d=(D_core+d)/d`，默认比值 20 反求 `D_core=(20-1)*d`。默认比值和未确认标准条款分别产生 `W_DD_PROJECT_DEFAULT`、`W_STANDARD_CLAUSE_NOT_CONFIRMED`。
- C-05：`service_factor=1.25` 仅在额定拉力输入时形成一次 `F_design`；设计/最大拉力输入时实际作用值为 1。`pitch_factor=1.10` 只用于理论节距。`brake_safety_factor=1.50` 只用于一次静态保持制动。
- C-06：满卷为静态最不利半径，`T_low=F_design*r_full*brake_safety_factor`，`T_high=T_low*η_back/i`。只有显式允许时才可用正向效率近似；自锁、蜗杆、不可逆或禁止反驱机构不得近似。动态、应急与热容量不作合格结论。
- C-07：`P_drum=F_design*v_drum`、`P_required=P_drum/η_forward`，不再乘使用系数。从集中功率系列向上选档；超过 315 kW 返回超范围。选档不代表启动、堵转、惯量、变频低速、认证或热容量合格。

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
| `rated_line_pull_kn` | `F_input` | kN | N | 无 | `> 0` 且组合计算不溢出 | 位置和类型由 `force_input_location/type` 显式说明。 |
| `force_input_location` | — | 枚举 | — | `load_end` | `load_end\|drum_rope_end` | 载荷端输入按倍率和滑轮效率换算到卷筒绳端。 |
| `speed_input_location` | — | 枚举 | — | `load_end` | `load_end\|drum_rope_end` | 载荷端速度按倍率换算到卷筒绳速。 |
| `force_input_type` | — | 枚举 | — | `rated` | `rated\|design\|maximum` | 仅 `rated` 输入应用一次使用系数。 |
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
| `approved_core_ratio` | `R_Dd` | — | — | `null` | 若有则 `> 1` | 可追溯的标准、制造商或项目批准值优先。 |
| `minimum_dd_ratio` | `R_Dd,project` | — | — | `20` | `> 1` | C-04 冻结的项目初选值；只生成 preliminary 结果并显著警告，不声称标准合规。 |
| `dead_wraps` / `dead_wrap_count` | `N_dead` | 圈 | — | `3` | 严格整数 `2..8`，且不超过实际/理论可用圈数 | 只从第一层工作绳容量中扣除。 |
| `termination_allowance_m` | `L_termination` | m | m | `0` | `>= 0` | 绳端安装预留，不计入目标有效工作绳长。 |
| `actual_groove_pitch_mm` | `p_actual` | mm | m | `null` | 若有则 `> 0` | 优先于理论节距。 |
| `actual_usable_groove_count` | `N_actual` | 圈 | — | `null` | 严格整数 `1..100` | 优先于理论圈数；必须与面宽/槽距一致。 |
| `brake_basis_type` | — | 枚举 | — | `design_force` | 当前只允许 `design_force` | 防止快照记录一种口径、实际按另一口径计算。 |
| `backdrive_efficiency` | `η_back` | — | — | `null` | 若有则 `0 < η_back <= 1` | 不提供无依据默认值。 |
| `transmission_backdrive_type` | — | 枚举 | — | `reversible` | 受控枚举 | 自锁、蜗杆、不可逆或禁止反驱时不生成高速轴反驱参考值。 |
| `allow_forward_efficiency_as_reverse_approx` | — | 布尔 | — | `false` | true/false | 安全默认：不允许正向效率静默替代反向效率。 |
| `motor_power_series_id` | — | 枚举 | — | `project_default_iec_kw` | 当前只允许冻结系列 ID | 禁止记录未执行的自定义系列。 |

建议 UI 软边界仅用于异常提示，不作为工程标准：数值超过产品配置上限时返回“超出已验证范围”，而非声称不合格。硬边界之外，还需满足：`B - 2b > 0`、可用宽度至少容纳 1 圈、计算层数不超过 `z_max`。

## 3. SI 规范化

| ID | 公式 | 结果 |
|---|---|---|
| `UNIT-001` | `F_input = rated_line_pull_kn × 1000` | N |
| `UNIT-002` | `d = rope_diameter_mm / 1000` | m |
| `UNIT-003` | `v = rope_speed_m_per_min / 60` | m/s |
| `UNIT-004` | `D_c = drum_core_diameter_mm / 1000` | m |
| `UNIT-005` | `B = drum_face_length_mm / 1000` | m |
| `UNIT-006` | `b = side_margin_mm / 1000` | m |

原始值、显示单位、SI 值和换算公式 ID 均进入快照。计算过程中不得混用 mm 与 m。

## 4. 计算顺序与公式

### 4.1 输入语义与可计算性门禁

1. 将拉力和速度按显式输入位置换算到卷筒绳端；载荷端拉力必须同时使用倍率和滑轮效率，不能只除以倍率。
2. 若 `D_c` 缺失，优先采用已批准 `R_Dd`；否则采用带 `project_default` 来源和警告的项目初选比 20，不得把该结果描述为标准合规。
3. 若 `D_c` 存在而 `B` 缺失，可按目标容量和最大层数反求最小面长。
4. 若 `B` 存在而 `D_c` 缺失，仍按第 2 项取得芯径；若走项目初选比 20，芯径及其后续几何结果保持 `preliminary` 并带来源警告。
5. 若二者均存在，校核容量；不足时返回明确不足与最大可容长度，不自动改变输入。

### 4.2 驱动拉力和功率

| ID | 公式 | 符号/单位 | 等级 | 适用条件 |
|---|---|---|---|---|
| `FORCE-001` | `F_design = F_drum K_s,applied`；额定输入时 `K_s,applied=K_s`，设计/最大输入时为 1 | `F_design` 设计绳张力，N | calculated | `F_drum` 已按输入位置换算到卷筒绳端；使用系数最多作用一次。 |
| `POWER-001` | `P_drum = F_design v_drum` | `P_drum` 理论卷筒机械功率，W | calculated | 不含效率。 |
| `POWER-002` | `P_motor_min = P_load / η` | 最低所需电机机械功率，W | calculated | `η` 为正向总效率。 |
| `POWER-003` | `P_motor_suggested >= P_motor_min` | 建议电机功率（标准额定档位），W | preliminary | 需经批准的标准功率系列、工作制、热容量、启动/过载与环境条件；没有系列时只输出下限。 |

“理论负载功率”采用 `F_design` 而非原始输入拉力，名称和报告须明确。若产品还要展示原始输入工况功率，可另列计算项，不得与 `POWER-001` 混称。

### 4.3 卷筒芯径

| ID | 公式 | 等级 | 说明 |
|---|---|---|---|
| `DRUM-001` | 若输入 `D_c`：`D_c,used = D_c` | calculated（输入回显） | 只表示采用输入值，不代表合规。 |
| `DRUM-002` | 若无 `D_c`：`D_c,suggested = (R_Dd-1)d`；优先采用已确认比值，否则采用项目初选默认 20 | preliminary | `R_Dd` 来源必须保存在假设中；项目默认产生警告。 |

不得内置或声称某个 D/d 比适用于所有钢丝绳、合成绳或工作级别。

### 4.4 节距、可用宽度和每层圈数

| ID | 公式 | 单位 | 等级 | 边界 |
|---|---|---:|---|---|
| `GEOM-001` | 有实际槽距时 `p=p_actual`，否则 `p = K_p d` | m | calculated | 审计步骤必须记录实际采用的分支。 |
| `GEOM-002` | `B_u = B - 2b` | m | calculated | 必须 `B_u > 0`。 |
| `GEOM-003` | 有实际可用槽数时 `N_used=N_actual`，否则 `N_full = floor((B_u + ε) / p)` | 圈/完整层 | calculated | 实际槽数优先且必须满足宽度/槽距交叉校验；`ε` 仅为浮点容差。 |
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

比较口径先从第一层扣除死圈，再用 `L_req,usable=L_t+L_termination` 作为所需可用容量；包含死圈的总储绳需求另报告为 `L_required,total=L_t+L_dead+L_termination`。实际使用层数与末层圈数：找到最小 `k` 使 `L_total,k >= L_req,usable`。此前完整使用各层；最后一层需求长度 `L_need,k = L_req,usable - L_total,k-1`，末层使用圈数可报告为连续值 `N_used,k = L_need,k / l_turn,k`。若直到 `z_max` 仍不足，则工程结论为“容量不足”，整体请求仍可保存为 `completed_with_warnings`，并返回最大可用容量与缺口。

| ID | 公式 | 单位 | 等级 |
|---|---|---:|---|
| `CAP-006` | `z_actual = min{k | L_total,k >= L_req,usable}` | 层 | calculated |
| `CAP-007` | `L_margin = L_total,z_actual - L_req,usable`；不足时 `L_shortfall=L_req,usable-L_total,z_max` | m | calculated |
| `CAP-008` | `capacity_margin_pct = 100 L_margin / L_t` | % | calculated |

“总容绳量”必须同时标明口径：完整实际层容量或最大层数容量。API 分别命名为 `capacity_at_actual_layers_m` 和 `capacity_at_max_layers_m`，不得只用模糊的 `total_capacity`。

若 `z_max` 内无法满足目标，则 `capacity_satisfied=false`、`actual_layers=null`、`capacity_at_actual_layers_m=null`；另返回 `evaluated_layers=z_max`、`capacity_at_max_layers_m` 和 `capacity_shortfall_m=L_req,usable-L_total,z_max`。此时 `full_working_diameter_m`、`full_drum_speed_rpm` 和 `reference_ratio_full` 必须为 `null`；允许最大层的对应值只写入 `max_layer_working_diameter_m`、`max_layer_drum_speed_rpm` 和 `reference_ratio_max_layer`，不得伪称已满足目标的满绳状态。

### 4.6 反求建议卷筒面长

条件：已知 `D_c`、`d`、`K_p`、`L_t`、`z_max` 和 `b`，且 `B` 未提供。`D_c` 来自用户输入、已批准的 `R_Dd`，或显式标为 `project_default/preliminary` 的项目初选比 20；优化器不得自行发明其他通用 D/d。优化器只枚举有限集合 `z = 1..z_max`（`z_max<=100`）。对每个候选层数求最小整数完整层圈数 `N_req,z`，使：

`Σ(j=1..z) max(0, N_req,z - I[j=1]N_dead) l_turn,j >= L_t+L_termination`

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
| `SPEED-002` | 满足容量时 `D_work,full = D_c + (2z_actual-1)d`；不足时 `D_work,max = D_c + (2z_max-1)d` | m | calculated | 两种状态写入不同字段。 |
| `SPEED-003` | `n_drum = 60v/(πD_work)` | r/min | calculated | 以给定绳速反求卷筒转速。 |
| `SPEED-004` | `n_empty = 60v/(πD_work,empty)` | r/min | calculated | 空卷目标转速。 |
| `SPEED-005` | 满足容量时 `n_full = 60v/(πD_work,full)`；不足时计算 `n_max` | r/min | calculated | 两种状态写入不同字段。 |
| `RATIO-001` | `i_empty = n_m/n_empty`；满足容量时计算 `i_full`，不足时计算 `i_max` | — | preliminary | 保持恒绳速所需速比范围。 |
| `RATIO-002` | `D_ref=(D_work,empty+D_work,outer)/2`；`n_ref=60v/(πD_ref)`；`i_ref=n_m/n_ref` | — | preliminary | `outer` 是实际满绳层或允许最大层；仅作名义参考。 |

固定速比和固定电机转速无法同时保证空卷、满卷绳速恒定。系统必须给出速比范围及警告；若采用变频/液压调速，应在详细设计中确认转速范围、恒功率/恒转矩能力。不得将 `i_ref` 直接称为“最终减速比”。

### 4.8 制动力矩

冻结口径把 `F_design` 作为静态保持基准，并只再乘一次独立制动系数 `K_b`。满足容量时按实际满绳工作直径计算；容量不足时只能按已评估最大层半径给出初选值，同时保留容量不足高严重度警告：

| ID | 公式 | 单位 | 等级 | 说明 |
|---|---|---:|---|---|
| `BRAKE-001` | `T_brake,low = F_design (D_work,outer/2) K_b` | N·m | preliminary | `outer` 见上文；不含动态制动和惯性。 |
| `BRAKE-002` | `T_brake,high,ref = T_brake,low η_back/i_ref` | N·m | preliminary | 载荷从低速侧反驱高速侧的静态等效初选；`η_back` 为反向效率。 |

`η_back` 默认为空，因此高速轴结果默认 `review_required`。可逆传动下，用户可直接提供反向效率；或只有 `allow_forward_efficiency_as_reverse_approx=true` 时才令 `η_back=η`，并输出高严重度近似警告。自锁、蜗杆、不可逆或禁止反驱机构即使填入效率也不生成高速轴参考值。

还应提示：制动器额定/动态扭矩、热容量、响应时间、失电抱闸、冗余、安装位置、齿轮间隙、回程效率和适用安全标准均未核验。

### 4.9 滑轮组倍率提示

`REEVE-001/002` 首先把输入位置统一到卷筒绳端；再从卷筒端给出载荷端理想换算提示：

| ID | 公式 | 等级 |
|---|---|---|
| `REEVE-001` | 载荷端输入：`F_drum=F_input/(Mη_pulley)`；卷筒端输入：`F_drum=F_input`。提示值：`F_load,ideal=F_drum Mη_pulley` | calculated / informational |
| `REEVE-002` | 载荷端输入：`v_drum=Mv_input`；卷筒端输入：`v_drum=v_input`。提示值：`v_load,ideal=v_drum/M` | calculated / informational |

后续 `FORCE-001` 只使用已换算的 `F_drum`，不得再次计入倍率。提示值不代表已校核的真实载荷能力。

## 5. 输出清单与分类

| 输出字段 | 公式 ID | 分类 |
|---|---|---|
| `design_line_pull_n` | `FORCE-001` | calculated |
| `theoretical_load_power_w` | `POWER-001` | calculated |
| `minimum_motor_power_w` | `POWER-002` | calculated |
| `suggested_motor_power_w` | `POWER-003` | preliminary 或 review_required |
| `used_or_suggested_core_diameter_m` | `DRUM-001/002` | calculated-input / preliminary |
| `suggested_drum_face_length_m` | `WIDTH-002` | preliminary |
| `actual_layers`（实际缠绕层数） | `CAP-006` | calculated |
| `turns_per_full_layer` | `GEOM-003` | calculated |
| `layer_details[]` | `CAP-001..005` | calculated |
| `capacity_at_actual_layers_m` | `CAP-005` | calculated |
| `capacity_at_max_layers_m` | `CAP-005` | calculated |
| `capacity_margin_m/pct` | `CAP-007/008` | calculated |
| `empty/full/max_layer_working_diameter_m` | `SPEED-001/002` | calculated；满绳与最大层互斥 |
| `empty/full/max_layer_drum_speed_rpm` | `SPEED-004/005` | calculated；满绳与最大层互斥 |
| `reference_ratio_empty/full/max_layer/nominal` | `RATIO-001/002` | preliminary |
| `low_speed_brake_torque_nm` | `BRAKE-001` | preliminary |
| `high_speed_brake_torque_ref_nm` | `BRAKE-002` | review_required；确认近似后 preliminary |

## 6. 警告代码

| 代码 | 严重度 | 触发条件 |
|---|---|---|
| `W_CORE_RULE_MISSING` | high | 芯径和批准 D/d 规则均缺失。 |
| `W_CORE_UNVERIFIED` | high | 采用的用户芯径或 D/d 来源仍未完成绳型、强度和弯曲比核验。 |
| `W_CAPACITY_INSUFFICIENT` | high | 最大层数下容量小于目标。 |
| `W_FIXED_RATIO_SPEED_VARIATION` | warning | 空卷与外层要求的速比不同。 |
| `W_MOTOR_SELECTION_INCOMPLETE` | high | 缺工作制/标准系列/启动与热校核。 |
| `W_BRAKE_STATIC_ONLY` | high | 制动结果仅为静态保持参考。 |
| `W_REVERSE_EFFICIENCY_UNKNOWN` | high | 未提供反向效率。 |
| `W_REVERSE_EFFICIENCY_APPROXIMATED` | high | 用户明确允许用正向效率近似反向效率。 |
| `W_SERVICE_FACTOR_SOURCE` | warning | 使用系数来源待确认。 |
| `W_PITCH_FACTOR_SOURCE` | warning | 节距系数来源待确认。 |
| `W_DUTY_CLASS_INFO_ONLY` | warning | 工作级别未参与自动计算。 |
| `W_ROPE_STRENGTH_NOT_CHECKED` | high | 所有计算均提示绳强度未校核。 |
| `W_DRUM_STRUCTURE_NOT_CHECKED` | high | 卷筒结构/法兰/轴承等未校核。 |
| `W_DEAD_WRAP_BELOW_DEFAULT` | high | 固定死圈少于项目初选默认 3 圈。 |
| `W_PULLEY_EFFICIENCY_DEFAULT` | warning | 倍率大于 1 且滑轮效率采用项目初选默认值。 |
| `W_ROPE_DIAMETER_OUTSIDE_VALIDATED_RANGE` | warning | 绳径超出主要验证范围 6～32 mm。 |
| `W_DD_PROJECT_DEFAULT` | warning | D/d 采用项目初选默认值。 |
| `W_DYNAMIC_BRAKE_NOT_CHECKED` | high | 动态制动和热容量未校核。 |
| `W_MOTOR_THERMAL_NOT_CHECKED` | high | 电机启动、工作制和热容量未校核。 |
| `W_STANDARD_CLAUSE_NOT_CONFIRMED` | warning | 适用标准版本、条款和页码未确认。 |

警告代码及触发逻辑属于计算模型版本的一部分；文案可本地化，但不得改变含义。

## 7. 当前输入充分性检查

### 7.1 足够完成

- 在芯径和面长均已提供时：设计拉力、最低功率、逐层理论容量、空满卷工作直径/目标转速和参考速比。
- 芯径已提供、面长缺失时：按已给最大层数反求规则几何最小面长。
- 低速轴静态保持力矩参考（仍需人工复核）。

### 7.2 不足或语义需确认

- 芯径建议：缺绳类型、结构、材料、最小弯曲比及适用标准/供应商要求。
- 电机额定功率定型：缺工作制、负载谱、启动次数、加速度、环境、供电、过载与标准功率系列。
- 高速轴制动力矩：仅在可逆传动并提供反向效率或显式允许近似时给出初选；真实速比、制动器位置和动态/热工况仍需确认。
- 滑轮组真实载荷能力：缺各滑轮效率、承载绳段定义、运动端、自重与摩擦。
- 容绳可制造性：缺绳槽形式、绳槽几何、法兰高度、死圈、排绳器、入绳角及绳压缩数据。
- 结构安全：缺材料、许用应力、壁厚、法兰、焊缝、轴承跨距、轴载荷、疲劳和法规/标准。

上述绳型、输入位置/类型、死圈和假设来源已作为显式字段进入快照；这些记录不替代绳强度、标准条款和供应商复核。

## 8. 潜在重复安全系数检查

1. `K_s` 只在输入类型为 `rated` 时作用一次，形成 `F_design`；设计/最大拉力输入的实际作用值为 1。
2. `K_b` 只在 `BRAKE-001` 中作用一次；冻结基准是 `F_design`，`brake_basis_type` 当前只允许 `design_force`，从而防止记录口径与实际公式不一致。
3. `M` 与 `η_pulley` 只用于输入位置统一；`FORCE-001` 使用换算后的卷筒绳端力，不再次乘除倍率。
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
