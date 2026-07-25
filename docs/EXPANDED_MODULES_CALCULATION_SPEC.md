# 八个扩展工程模块计算规格

文档版本：0.1.0
工程发布状态：`internal_testing`
适用计算模型：

- `transmission_check.calc.1.0.0`
- `gear_drive.calc.1.0.0`
- `shaft_bearing.calc.1.0.0`
- `lead_screw.calc.1.0.0`
- `synchronous_belt.calc.1.0.0`
- `motor_drive.calc.1.0.0`
- `stepper_motor.calc.1.0.0`
- `pneumatic_cylinder.calc.1.0.0`

自动化证据见 [`EXPANDED_FORMULA_TEST_MATRIX.md`](EXPANDED_FORMULA_TEST_MATRIX.md)。绞车与卷筒模块仍以 [`CALCULATION_SPEC.md`](CALCULATION_SPEC.md) 为唯一计算规格。

## 1. 适用范围与共同契约

本规格按当前 Python 实现逐项记录八个扩展模块的输入口径、SI 规范化、公式、结果等级、候选数据缺失语义和未覆盖项。它不是机械标准、产品目录或设计批准文件。

共同软件契约：

- 计算在本地以确定性 Python 执行，不访问网络，不从网页抓取参数。
- API 禁止额外字段、NaN 和 Infinity；输入模型冻结。公共数值类型还有防资源滥用的软件上限，这些上限不是工程允许值。
- 每次计算必须提供 `basis_source_status` 和非空 `basis_reference`。来源状态只能是 `user_input`、`project_setting`、`standard_confirmed`、`manufacturer_data` 或 `pending_confirmation`。
- `calculated` 表示按已声明模型直接计算；`preliminary` 表示仅可初选；`review_required` 表示信息不足且 `value=null`；`informational` 仅作提示。
- 候选额定值、许用值、材料值、效率、使用系数、寿命指数、有效长度系数和曲线点均由调用方显式提供。软件不内置或猜测任何厂商数值、标准系数、材料许用值或产品型号。
- 候选数据缺失时，基础理论量仍计算；依赖该候选数据的结果必须为 `value=null`、`classification=review_required` 并带非空原因。缺失候选时对应比较公式没有 `FormulaStep`，但 `ScalarResult.formula_ids` 仍声明预留公式 ID。
- 候选数据存在时，比较结果最多为 `preliminary`。即使比较为 `true`，也不等于标准合格、采购放行、制造放行或安全认证。
- 公式 ID 当前只在模块内部唯一。审计主键应使用 `(module_id, calculation_model_version, formula_id)`，不得只用裸 `formula_id`。
- 计算使用未舍入浮点值；显示层舍入不得回写计算输入或中间结果。

## 2. 官方资料的使用边界

以下官方资料只用于说明“最终工程选型还需要哪些厂商/标准条件”，不是当前运行公式的在线数据源，也不授权把其中示例值写成默认值：

- SKF [`Rolling bearings`](https://www.skf.com/binaries/pub12/Images/0901d196802809de-Rolling-bearings---17000_1-EN_tcm_12-121486.pdf)：基本额定寿命及其适用条件参考。
- KHK [`Calculation of Gear Dimensions`](https://khkgears.net/gear-knowledge/gear-technical-reference/calculation-gear-dimensions/)：齿轮基础几何方法参考。
- THK [`Lead Screw Nut Selection`](https://www.thk.com/eu/en/products/other_power_transmission_elements/lead_screw_nut/selection/0002/)：丝杠驱动力与产品选型边界参考。
- Gates [`PowerGrip GT3 Drive Design Manual`](https://www.gates.com/content/dam/documents-library/catalogs/powergrip-gt3-drive-design-manual-en.pdf)：同步带完整选型、带宽、齿数与额定能力边界参考。
- Oriental Motor [`Motor Sizing Calculations`](https://www.orientalmotor.com/technology/motor-sizing-calculations.html)：惯量、加速转矩与电机选型流程参考。
- SEW-EURODRIVE [`Project planning for drives`](https://download.sew-eurodrive.com/download/pdf/10522913.pdf) 和 [`Technical data and dimension sheets`](https://download.sew-eurodrive.com/download/html/27804011/en-EN/2522218957940568946827.html)：驱动工作制、额定数据和项目规划边界参考。
- Festo [`Air consumption`](https://www.festo.com/ca/en/s/air-consumption) 与 Parker [`Pneumatic Actuator Products`](https://www.parker.com/content/dam/Parker-com/Literature/Literature-Files/pneumatic/Literature/Actuator-Cylinder/0900/0900P_Complete.pdf)：气缸耗气、压力、安装和产品额定边界参考。

运行时不会请求上述链接，也不会把厂商目录中的任何数值缓存到计算模型。项目使用时必须把具体型号、版本、页码/曲线、额定值定义和适用工况作为输入依据保存。

## 3. `transmission_check` 机械传动快速校核

### 3.1 模型边界

仅计算 1～4 级正向、稳态传动链的速比、效率、角速度、转矩和功率传递，以及可选候选额定输出转矩比较。传动比统一定义为 `i=n_in/n_out=omega_in/omega_out`。

### 3.2 输入与 SI 规范化

| API 字段 | 输入单位/口径 | SI 处理与硬校验 |
|---|---|---|
| `input_speed_rpm` | r/min，正数 | `omega_in=input_speed_rpm*2*pi/60`，rad/s |
| `input_torque_nm` | N·m，正数 | 已是 SI，不换算 |
| `stages` | 1～4 个，按动力流向 | 级名唯一 |
| `stages[].ratio` | `n_in/n_out`，正数 | 无默认值；每级必须带 `ratio_source_status/reference` |
| `stages[].efficiency` | 正向效率 | `0<eta<=1`；每级必须带 `efficiency_source_status/reference` |
| `candidate_rated_output_torque_nm` | N·m，可选正数 | 与 `candidate_source_status/reference` 三者全有或全无 |

组合校验会拒绝导致总速比、总效率、角速度、输出转矩或功率成为非有限值的输入。

### 3.3 公式

| 公式 ID | 当前表达式 | 单位 | 等级 | 条件/说明 |
|---|---|---:|---|---|
| `UNIT-001` | `omega_in=input_speed_rpm*2*pi/60` | rad/s | calculated | 始终执行 |
| `KIN-001` | `i_total=product(i_stage)` | — | calculated | 始终执行 |
| `POWER-001` | `eta_total=product(eta_stage)` | — | calculated | 名称沿用实现；结果是效率而非功率 |
| `POWER-002` | `P_in=T_in*omega_in` | W | calculated | 始终执行 |
| `KIN-011` | `omega_out,1=omega_in,1/i_1` | rad/s | calculated | 第 1 级 |
| `TORQUE-011` | `T_out,1=T_in,1*i_1*eta_1` | N·m | calculated | 第 1 级 |
| `POWER-011` | `P_out,1=T_out,1*omega_out,1` | W | calculated | 第 1 级 |
| `KIN-012` | `omega_out,2=omega_in,2/i_2` | rad/s | calculated | 有第 2 级时 |
| `TORQUE-012` | `T_out,2=T_in,2*i_2*eta_2` | N·m | calculated | 有第 2 级时 |
| `POWER-012` | `P_out,2=T_out,2*omega_out,2` | W | calculated | 有第 2 级时 |
| `KIN-013` | `omega_out,3=omega_in,3/i_3` | rad/s | calculated | 有第 3 级时 |
| `TORQUE-013` | `T_out,3=T_in,3*i_3*eta_3` | N·m | calculated | 有第 3 级时 |
| `POWER-013` | `P_out,3=T_out,3*omega_out,3` | W | calculated | 有第 3 级时 |
| `KIN-014` | `omega_out,4=omega_in,4/i_4` | rad/s | calculated | 有第 4 级时 |
| `TORQUE-014` | `T_out,4=T_in,4*i_4*eta_4` | N·m | calculated | 有第 4 级时 |
| `POWER-014` | `P_out,4=T_out,4*omega_out,4` | W | calculated | 有第 4 级时 |
| `CHECK-001` | `u_T=T_out/T_candidate,rated` | — | preliminary | 有候选额定转矩时 |
| `CHECK-002` | `candidate_torque_satisfied=(T_out<=T_candidate,rated)` | — | preliminary | 有候选额定转矩时 |
| `CHECK-003` | `Delta_T=T_candidate,rated-T_out` | N·m | preliminary | 有候选额定转矩时 |

### 3.4 候选缺失与未覆盖项

未提供候选额定转矩时，`candidate_torque_utilization`、`candidate_torque_margin_nm`、`candidate_torque_satisfied` 均为 `null/review_required`，并产生 `CANDIDATE_TORQUE_MISSING`。

明确未覆盖：动态/峰值转矩、载荷谱与疲劳、齿轮/带/链强度、轴/联轴器/键强度、轴承寿命、热容量与润滑、反驱与制动、扭振、标准条款确认、制造商应用批准。

## 4. `gear_drive` 齿轮传动设计

### 4.1 模型边界

只适用于用户给定参数的标准直齿外啮合基础节圆几何与名义啮合力。未使用变位、斜齿或内啮合公式。

### 4.2 输入与 SI 规范化

| API 字段 | 输入单位/口径 | SI 处理与硬校验 |
|---|---|---|
| `module_mm` | mm，正数 | `/1000` 得 `module_m` |
| `pinion_teeth` / `gear_teeth` | 正整数 | 当前只作齿数与速比输入 |
| `pressure_angle_deg` | deg | `0<alpha<90`，乘 `pi/180` 得 rad |
| `input_speed_rpm` | r/min，正数 | `*2*pi/60` 得 rad/s |
| `input_torque_nm` | N·m，正数 | 已是 SI |
| `mesh_efficiency` | 正向啮合效率 | `0<eta<=1` |
| `allowable_tangential_force_n` | N，可选 | 与来源状态、依据三者全有或全无 |
| `maximum_pitch_line_speed_m_s` | m/s，可选 | 与来源状态、依据三者全有或全无 |

两个候选限值彼此独立，可以只提供其中一组。

### 4.3 公式

| 公式 ID | 当前表达式 | 单位 | 等级 | 条件 |
|---|---|---:|---|---|
| `UNIT-001` | `m=module_mm/1000` | m | calculated | 始终 |
| `UNIT-002` | `alpha=pressure_angle_deg*pi/180` | rad | calculated | 始终 |
| `UNIT-003` | `omega_1=input_speed_rpm*2*pi/60` | rad/s | calculated | 始终 |
| `GEOM-001` | `d_1=m*z_1` | m | calculated | 始终 |
| `GEOM-002` | `d_2=m*z_2` | m | calculated | 始终 |
| `GEOM-003` | `a=(d_1+d_2)/2` | m | calculated | 始终 |
| `KIN-001` | `i=z_2/z_1` | — | calculated | 始终 |
| `FORCE-001` | `F_t=2*T_1/d_1` | N | calculated | 名义节圆切向力 |
| `FORCE-002` | `F_r=F_t*tan(alpha)` | N | calculated | 名义径向力 |
| `KIN-002` | `v=omega_1*d_1/2` | m/s | calculated | 节线速度 |
| `KIN-003` | `omega_2=omega_1/i` | rad/s | calculated | 输出角速度 |
| `TORQUE-001` | `T_2=T_1*i*eta_mesh` | N·m | calculated | 输出转矩 |
| `POWER-001` | `P_2=T_2*omega_2` | W | calculated | 输出功率 |
| `CHECK-001` | `u_F=F_t/F_t,allow` | — | preliminary | 有许用切向力 |
| `CHECK-002` | `force_satisfied=(F_t<=F_t,allow)` | — | preliminary | 有许用切向力 |
| `CHECK-003` | `u_v=v/v_max` | — | preliminary | 有最大节线速度 |
| `CHECK-004` | `speed_satisfied=(v<=v_max)` | — | preliminary | 有最大节线速度 |

### 4.4 候选缺失与未覆盖项

缺少某一候选限值时，只将该限值对应的利用率和通过标志置为 `null/review_required`；另一组候选数据仍可独立比较。

明确未覆盖：齿根弯曲强度、齿面接触强度、胶合/点蚀/磨损、材料与热处理、齿宽与载荷分布、动载与精度等级、变位/侧隙/修形、润滑与热平衡、轴承/轴/箱体、标准条款和制造商应用批准。

## 5. `shaft_bearing` 轴与轴承初选

### 5.1 模型边界

轴承部分只按用户给定 `X`、`Y`、`C`、`p` 和恒定等效载荷计算基本额定 `L10`；轴部分只计算无孔、无应力集中实心圆截面的名义弯扭弹性应力。

### 5.2 输入与 SI 规范化

| API 字段 | 输入单位/口径 | SI 处理与硬校验 |
|---|---|---|
| `bearing_radial_load_n` / `bearing_axial_load_n` | N，允许 0 | 必须满足 `X*Fr+Y*Fa>0` |
| `bearing_speed_rpm` | r/min，正数 | `*2*pi/60` 得 rad/s |
| `basic_dynamic_load_rating_n` | N，正数 | 必须带来源状态和完整型号/依据 |
| `radial_factor_x` / `axial_factor_y` | 无量纲，允许 0 | 各自必须带来源状态和依据 |
| `life_exponent_p` | 正数 | 必须带来源状态和依据；软件不按轴承类型推定 |
| `shaft_diameter_mm` | mm，正数 | `/1000` 得 m |
| `shaft_bending_moment_nm` / `shaft_torque_nm` | N·m，允许 0 | 两者不得同时为 0 |
| `allowable_von_mises_stress_mpa` | MPa，可选正数 | `*1e6` 得 Pa；与来源状态、依据全有或全无 |

### 5.3 公式

| 公式 ID | 当前表达式 | 单位 | 等级 | 条件 |
|---|---|---:|---|---|
| `UNIT-001` | `omega=bearing_speed_rpm*2*pi/60` | rad/s | calculated | 始终 |
| `UNIT-002` | `d=shaft_diameter_mm/1000` | m | calculated | 始终 |
| `UNIT-003` | `sigma_allow=allowable_stress_mpa*1e6` | Pa | calculated | 有候选许用应力 |
| `FORCE-001` | `P=X*F_r+Y*F_a` | N | calculated | 始终 |
| `LIFE-001` | `L_10=(C/P)^p` | 10^6 rev | calculated | 基本额定寿命 |
| `LIFE-002` | `L_10h=L_10*1e6/(60*n_rpm)` | h | calculated | 始终 |
| `STRESS-001` | `sigma_b=32*M/(pi*d^3)` | Pa | calculated | 实心圆轴名义弯曲应力 |
| `STRESS-002` | `tau_t=16*T/(pi*d^3)` | Pa | calculated | 实心圆轴名义扭转剪应力 |
| `STRESS-003` | `sigma_vm=sqrt(sigma_b^2+3*tau_t^2)` | Pa | calculated | 名义 von Mises 应力 |
| `CHECK-001` | `u_sigma=sigma_vm/sigma_allow` | — | preliminary | 有许用应力 |
| `CHECK-002` | `stress_satisfied=(sigma_vm<=sigma_allow)` | — | preliminary | 有许用应力 |
| `CHECK-003` | `Delta_sigma=sigma_allow-sigma_vm` | Pa | preliminary | 有许用应力 |

### 5.4 候选缺失与未覆盖项

缺少许用应力时，利用率、余量和通过标志均为 `null/review_required`，基础寿命和名义应力仍计算。

明确未覆盖：轴承静安全、可靠度修正、润滑/污染/温度、游隙/配合/不对中、变载谱；轴疲劳与应力集中、键槽/台阶/圆角/配合、挠度/对中、临界转速/振动、材料表面和尺寸效应、标准条款和制造商应用批准。

## 6. `lead_screw` 丝杆传动选型

### 6.1 模型边界

采用等效方牙滑动丝杠、恒定螺纹摩擦、轴心静载和理想 Euler 弹性柱模型。提升/下降转矩不含止推轴承或端面摩擦；Euler 结果未乘安全系数。

### 6.2 输入与 SI 规范化

| API 字段 | 输入单位/口径 | SI 处理与硬校验 |
|---|---|---|
| `axial_force_n` | N，正数 | 已是 SI |
| `mean_thread_diameter_mm` | mm，正数 | `/1000` 得 m |
| `root_diameter_mm` | mm，正数 | `/1000` 得 m，且必须小于中径 |
| `lead_mm_per_revolution` | mm/rev，正数 | `/1000` 得 m/rev |
| `friction_coefficient` | `mu>=0` | 必须带来源；且 `1-mu*tan(lambda)>0` |
| `rotational_speed_rpm` | r/min，正数 | `*2*pi/60` 得 rad/s |
| `youngs_modulus_gpa` | GPa，正数 | `*1e9` 得 Pa；必须带来源 |
| `unsupported_length_mm` | mm，正数 | `/1000` 得 m |
| `effective_length_factor` | `K>0` | 必须带端部约束来源；软件无默认值 |
| `candidate_allowable_axial_load_n` | N，可选正数 | 与来源状态、依据全有或全无 |

### 6.3 公式

| 公式 ID | 当前表达式 | 单位 | 等级 | 条件 |
|---|---|---:|---|---|
| `UNIT-001` | `d_m=mean_thread_diameter_mm/1000` | m | calculated | 始终 |
| `UNIT-002` | `d_root=root_diameter_mm/1000` | m | calculated | 始终 |
| `UNIT-003` | `lead=lead_mm_per_revolution/1000` | m/rev | calculated | 始终 |
| `UNIT-004` | `omega=rotational_speed_rpm*2*pi/60` | rad/s | calculated | 始终 |
| `UNIT-005` | `E=youngs_modulus_gpa*1e9` | Pa | calculated | 始终 |
| `UNIT-006` | `L=unsupported_length_mm/1000` | m | calculated | 始终 |
| `KIN-001` | `lambda=atan(lead/(pi*d_m))` | rad | calculated | 始终 |
| `TORQUE-001` | `T_raise=F*d_m/2*(tan(lambda)+mu)/(1-mu*tan(lambda))` | N·m | calculated | 始终 |
| `TORQUE-002` | `T_lower=F*d_m/2*(mu-tan(lambda))/(1+mu*tan(lambda))` | N·m | calculated | 可为负，表示等效模型不自锁 |
| `POWER-001` | `eta_raise=F*lead/(2*pi*T_raise)` | — | calculated | 始终 |
| `KIN-002` | `v=lead*omega/(2*pi)` | m/s | calculated | 始终 |
| `POWER-002` | `P_in,raise=T_raise*omega` | W | calculated | 始终 |
| `CHECK-001` | `self_locking=(mu>=tan(lambda))` | — | calculated | 只是等效螺纹静态判据 |
| `BUCKLING-001` | `I_root=pi*d_root^4/64` | m4 | preliminary | 根径实心圆截面 |
| `BUCKLING-002` | `F_cr=pi^2*E*I_root/(K*L)^2` | N | preliminary | 理想 Euler 模型 |
| `CHECK-002` | `u_buckling=F/F_cr` | — | preliminary | 始终 |
| `CHECK-003` | `euler_buckling_satisfied=(F<=F_cr)` | — | preliminary | 始终 |
| `CHECK-004` | `u_candidate=F/F_candidate,allow` | — | preliminary | 有候选许用载荷 |
| `CHECK-005` | `candidate_satisfied=(F<=F_candidate,allow)` | — | preliminary | 有候选许用载荷 |
| `CHECK-006` | `Delta_F=F_candidate,allow-F` | N | preliminary | 有候选许用载荷 |

### 6.4 候选缺失与未覆盖项

缺少候选许用轴向载荷时，候选利用率、余量和通过标志均为 `null/review_required`。Euler 校核与候选产品校核相互独立。

明确未覆盖：真实牙型修正、止推轴承/端面摩擦、螺纹与螺母强度、接触压强与磨损、PV/润滑/热、疲劳与工作制、临界转速与旋振、Euler 细长比与初始缺陷、屈曲安全系数/标准条款、安装不对中/横向载荷、制造商应用批准。

## 7. `synchronous_belt` 同步带传动

### 7.1 输入与 SI 口径

该模块所有尺寸、角速度、功率、力均直接使用 SI，不生成 `UNIT-*` 换算步骤。

| API 字段 | SI 单位/口径 | 硬校验 |
|---|---|---|
| `driver_teeth` / `driven_teeth` | 正整数齿数 | 无默认值 |
| `belt_pitch_m` | m，正数 | 无默认值 |
| `driver_angular_speed_rad_s` | rad/s，正数 | 无默认值 |
| `transmitted_power_w` | W，正数 | 无默认值 |
| `service_factor` | `>=1` | 只在设计功率中乘一次 |
| `center_distance_m` | m，正数 | 必须大于两节圆半径之和 |
| `manufacturer_allowable_effective_tension_n` | N，可选 | 可与最大带速只提供其中之一 |
| `manufacturer_max_belt_speed_m_s` | m/s，可选 | 有任一候选值时必须同时给来源状态和版本 |

### 7.2 公式

| 公式 ID | 当前表达式 | 单位 | 等级 |
|---|---|---:|---|
| `BELT_KIN-001` | `i=z2/z1` | — | calculated |
| `BELT_KIN-002` | `omega2=omega1/i` | rad/s | calculated |
| `BELT_GEOM-001` | `d1=p*z1/pi` | m | calculated |
| `BELT_GEOM-002` | `d2=p*z2/pi` | m | calculated |
| `BELT_KIN-003` | `v=omega1*d1/2` | m/s | calculated |
| `BELT_POWER-001` | `P_design=P_transmitted*K_service` | W | preliminary |
| `BELT_FORCE-001` | `F_effective=P_design/v` | N | preliminary |
| `BELT_GEOM-003` | `L_approx=2*C+pi*(D+d)/2+(D-d)^2/(4*C)` | m | preliminary |
| `BELT_GEOM-004` | `alpha_small=pi-2*asin((D-d)/(2*C))` | rad | preliminary |
| `BELT_GEOM-005` | `z_engaged=z_small*alpha_small/(2*pi)` | tooth | preliminary |
| `BELT_CHECK-001` | `pass_tension=(F_effective<=F_allowable)` | — | preliminary |
| `BELT_CHECK-002` | `pass_speed=(v<=v_max)` | — | preliminary |

带长是连续开式带几何近似值，不是制造商标准节线长度。

### 7.3 候选缺失与未覆盖项

两个候选限值分别缺失时，各自通过标志为 `null/review_required`；基础几何与圆周力继续计算。

明确未覆盖：带型兼容、目录标准节线长度、带宽与齿承载、预张力与轴承载荷、疲劳寿命、环境降额。

## 8. `motor_drive` 电机与驱动选型

### 8.1 输入与 SI 口径

该模块只接受两个明确的非再生稳态工作段，所有机械量直接使用 SI，不生成 `UNIT-*` 步骤。

| API 字段 | SI 单位/口径 | 硬校验 |
|---|---|---|
| 两段 `load_torque` | N·m，允许 0 | 不含加减速惯性转矩 |
| 两段 `load_speed` | rad/s，允许 0 | 非再生稳态方向 |
| 两段 `duration` | s，正数 | 两段均必须大于 0 |
| `transmission_ratio_motor_to_load` | `i=omega_motor/omega_load`，正数 | 无默认值 |
| `transmission_efficiency` | `0<eta<=1` | 仅正向折算 |
| `service_factor` | `>=1` | 对所需连续/峰值/RMS 转矩和功率各乘一次 |
| `declared_duty` | 可选文本 | 仅记录，不自动套用工作制或热降额 |
| 四个 `candidate_*` | N·m、rad/s、W，可分别缺失 | 有任一值时必须同时给来源状态和版本 |

### 8.2 公式

| 公式 ID | 当前表达式 | 单位 | 等级 |
|---|---|---:|---|
| `MOTOR_TORQUE-001` | `T_m1=T_load1/(i*eta)` | N·m | calculated |
| `MOTOR_TORQUE-002` | `T_m2=T_load2/(i*eta)` | N·m | calculated |
| `MOTOR_KIN-001` | `omega_m1=omega_load1*i` | rad/s | calculated |
| `MOTOR_KIN-002` | `omega_m2=omega_load2*i` | rad/s | calculated |
| `MOTOR_TORQUE-003` | `T_cont=(T_m1*t1+T_m2*t2)/(t1+t2)` | N·m | calculated |
| `MOTOR_TORQUE-004` | `T_peak=max(T_m1,T_m2)` | N·m | calculated |
| `MOTOR_TORQUE-005` | `T_rms=sqrt((T_m1^2*t1+T_m2^2*t2)/(t1+t2))` | N·m | calculated |
| `MOTOR_TORQUE-006` | `T_cont_required=T_cont*K_service` | N·m | preliminary |
| `MOTOR_TORQUE-007` | `T_peak_required=T_peak*K_service` | N·m | preliminary |
| `MOTOR_TORQUE-008` | `T_rms_required=T_rms*K_service` | N·m | preliminary |
| `MOTOR_POWER-001` | `P_required=max(T_m1*omega_m1,T_m2*omega_m2)*K_service` | W | preliminary |
| `MOTOR_KIN-003` | `omega_motor_max=max(omega_m1,omega_m2)` | rad/s | calculated |
| `MOTOR_CHECK-001` | `required_rms_torque<=candidate_rated_torque` | — | preliminary |
| `MOTOR_CHECK-002` | `required_peak_torque<=candidate_peak_torque` | — | preliminary |
| `MOTOR_CHECK-003` | `maximum_motor_speed<=candidate_max_speed` | — | preliminary |
| `MOTOR_CHECK-004` | `required_power<=candidate_rated_power` | — | preliminary |

### 8.3 候选缺失与未覆盖项

四项候选数据独立比较。缺少任一项时只将对应通过标志置为 `null/review_required`，其余已有候选仍可比较。

明确未覆盖：加速/减速、折算惯量、完整工作制与热模型、制造商完整转矩-转速曲线、再生与制动、供电与驱动器兼容性。

## 9. `stepper_motor` 步进电机选型

### 9.1 输入与 SI 口径

全部机械量直接使用 SI，不生成 `UNIT-*` 步骤。模型假设刚性无间隙传动，从零速到目标速度恒角加速。

| API 字段 | SI 单位/口径 | 硬校验 |
|---|---|---|
| `load_inertia_kg_m2` | kg·m²，允许 0 | 不含传动件自身惯量 |
| `motor_rotor_inertia_kg_m2` | kg·m²，正数 | 无默认值 |
| `transmission_ratio_motor_to_load` | `i=omega_motor/omega_load`，正数 | 无默认值 |
| `transmission_efficiency` | `0<eta<=1` | 只用于稳态转矩正向折算 |
| `target_load_speed_rad_s` | rad/s，正数 | 无默认值 |
| `acceleration_time_s` | s，正数 | 恒加速 |
| `steady_load_torque_n_m` | N·m，允许 0 | 无默认值 |
| `service_factor` | `>=1` | 合成后乘一次 |
| `full_steps_per_revolution` / `microstep_divisor` | 正整数 | 软件不推定默认步距角 |
| 曲线点速度/转矩/容差 | rad/s、N·m、rad/s，可选 | 三者全有或全无，曲线速度必须落入显式容差 |
| `candidate_allowable_inertia_ratio` | 可选正数 | 可与曲线点独立提供；任一候选需来源状态和版本 |

### 9.2 公式

| 公式 ID | 当前表达式 | 单位 | 等级 |
|---|---|---:|---|
| `STEP_INERTIA-001` | `J_reflected=J_load/i^2` | kg·m² | calculated |
| `STEP_INERTIA-002` | `J_total=J_rotor+J_reflected` | kg·m² | calculated |
| `STEP_KIN-001` | `omega_motor=omega_load*i` | rad/s | calculated |
| `STEP_KIN-002` | `alpha_motor=omega_motor/t_acceleration` | rad/s² | calculated |
| `STEP_TORQUE-001` | `T_inertia=J_total*alpha_motor` | N·m | calculated |
| `STEP_TORQUE-002` | `T_steady=T_load/(i*eta)` | N·m | calculated |
| `STEP_TORQUE-003` | `T_acceleration=T_inertia+T_steady` | N·m | calculated |
| `STEP_TORQUE-004` | `T_steady_required=T_steady*K_service` | N·m | preliminary |
| `STEP_TORQUE-005` | `T_peak_required=T_acceleration*K_service` | N·m | preliminary |
| `STEP_KIN-003` | `f_pulse=omega_motor/(2*pi)*steps_per_rev*microstep` | Hz | calculated |
| `STEP_INERTIA-003` | `R_inertia=J_reflected/J_rotor` | — | calculated |
| `STEP_CHECK-001` | `T_peak_required<=T_curve_point` | — | preliminary |
| `STEP_CHECK-002` | `R_inertia<=R_allowable` | — | preliminary |

候选曲线速度和容差只参与输入门禁，不产生独立公式步骤。单个曲线点不能替代从零速到工作速度的完整曲线校核。

### 9.3 候选缺失与未覆盖项

曲线点缺失时 `candidate_curve_torque_pass=null/review_required`；允许惯量比缺失时 `candidate_inertia_ratio_pass=null/review_required`。两项彼此独立。

明确未覆盖：负载惯性加速过程的传动损耗口径、完整转矩-转速曲线、共振与失步、驱动器电气条件、电机热容量、定位精度、传动柔性、保持与制动。当前 `transmission_efficiency` 仅用于稳态负载转矩折算；该口径未经项目机械审核前，不得把峰值转矩结果提升为工程放行值。

## 10. `pneumatic_cylinder` 气缸选型

### 10.1 输入与 SI 口径

全部输入直接使用 SI，不生成 `UNIT-*` 步骤。模型仅适用于双作用单杆气缸的理论力和理想同温参考体积。

| API 字段 | SI 单位/口径 | 硬校验 |
|---|---|---|
| `bore_diameter_m` / `rod_diameter_m` | m，正数 | 杆径必须小于缸径 |
| `stroke_m` | m，正数 | 全行程 |
| `cylinder_supply_absolute_pressure_pa` | Pa，绝压 | 必须大于环境绝压；应为气缸接口处压力 |
| `ambient_absolute_pressure_pa` | Pa，绝压 | 正数 |
| `reference_absolute_pressure_pa` | Pa，绝压 | 正数，由用户定义参考状态 |
| `extension_load_force_n` / `retraction_load_force_n` | N，允许 0 | 分别输入 |
| `load_safety_factor` | `>=1` | 只在需求力上乘一次 |
| `cycle_frequency_hz` | Hz，正数 | 一个循环=一次全伸+一次全缩 |
| `candidate_max_supply_absolute_pressure_pa` | Pa，绝压，可选 | 必须大于环境绝压；有值时必须带来源状态和版本 |

### 10.2 公式

| 公式 ID | 当前表达式 | 单位 | 等级 |
|---|---|---:|---|
| `CYL_GEOM-001` | `A_extension=pi*D^2/4` | m² | calculated |
| `CYL_GEOM-002` | `A_retraction=pi*(D^2-d_rod^2)/4` | m² | calculated |
| `CYL_PRESSURE-001` | `delta_p=p_supply_absolute-p_ambient_absolute` | Pa | calculated |
| `CYL_FORCE-001` | `F_extension=delta_p*A_extension` | N | preliminary |
| `CYL_FORCE-002` | `F_retraction=delta_p*A_retraction` | N | preliminary |
| `CYL_FORCE-003` | `F_extension_required=F_load_extension*K_safety` | N | preliminary |
| `CYL_FORCE-004` | `F_retraction_required=F_load_retraction*K_safety` | N | preliminary |
| `CYL_FORCE-005` | `margin_extension=F_extension-F_extension_required` | N | preliminary |
| `CYL_FORCE-006` | `margin_retraction=F_retraction-F_retraction_required` | N | preliminary |
| `CYL_CHECK-001` | `margin_extension>=0` | — | preliminary |
| `CYL_CHECK-002` | `margin_retraction>=0` | — | preliminary |
| `CYL_AIR-001` | `V_extension=A_extension*stroke` | m³ | calculated |
| `CYL_AIR-002` | `V_retraction=A_retraction*stroke` | m³ | calculated |
| `CYL_AIR-003` | `V_cycle=V_extension+V_retraction` | m³ | calculated |
| `CYL_AIR-004` | `V_reference=V_cycle*p_supply_absolute/p_reference_absolute` | m³ | preliminary |
| `CYL_AIR-005` | `Q_reference_per_min=V_reference*frequency_hz*60` | m³/min | preliminary |
| `CYL_CHECK-003` | `p_supply_absolute<=p_candidate_max` | — | preliminary |

理论力直接使用用户给定接口绝压与环境绝压之差；耗气量不扣环境压力，也不包含死腔、管容、泄漏、温差或辅助用气。

### 10.3 候选缺失与未覆盖项

缺少候选最大供气绝压时，`candidate_pressure_rating_pass=null/review_required`；理论力、需求力、余量和参考耗气量仍计算。

明确未覆盖：管路/阀压降、动态背压、流量/速度/循环时间、死腔/泄漏/温度、缓冲与冲击、活塞杆屈曲与安装、材料/环境/适用标准。

## 11. 工程使用限制与发布门禁

八个模块当前只能作为受控计算工作表使用。下列条件全部满足前，不得将 `internal_testing` 改为工程放行：

1. 项目工程师确认输入定义、最不利工况、来源版本和所有 `pending_confirmation`；
2. 按实际适用标准或制造商程序完成本规格明确排除的强度、寿命、热、动态、安装、环境和安全校核；
3. 对具体候选型号取得可追溯额定数据、曲线、降额和适用条件；
4. 对项目采用的候选数据和所有简化模型完成独立金样复核，并把评审记录与快照关联；
5. 由具备相应职责的机械、电气或气动工程师审核并签字。

本规格的公式与测试通过只证明软件按已声明的简化模型执行，不证明产品适用于任何真实项目。
