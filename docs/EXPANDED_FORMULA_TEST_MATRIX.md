# 八个扩展模块公式测试矩阵

文档版本：0.1.0
适用规格：[`EXPANDED_MODULES_CALCULATION_SPEC.md`](EXPANDED_MODULES_CALCULATION_SPEC.md)

本矩阵把八个扩展模块当前实现的每个公式 ID 映射到正常金样、边界/非法输入和候选数据缺失路径。公式 ID 是模块内编号；矩阵中的唯一定位为 `module_id + formula_id`。

`PASS` 表示该公式在独立算术金样路径中执行，且所属模块同时有输入边界、派生数值安全和候选缺失证据。部分中间步骤由最终量间接约束，并非每一行都有单独的数值断言；这不改变公式清单，但评审时应结合持久化 `calculation_steps` 检查。自动化通过不代表参数来源、适用标准或机械设计获批。

## 1. 覆盖汇总

| 模块 | 计算模型 | 公式实例数 | 正常金样 | 边界/非法 | 缺候选 `review_required` |
|---|---|---:|---|---|---|
| `transmission_check` | `transmission_check.calc.1.0.0` | 19 | PASS | PASS | PASS |
| `gear_drive` | `gear_drive.calc.1.0.0` | 17 | PASS | PASS | PASS |
| `shaft_bearing` | `shaft_bearing.calc.1.0.0` | 12 | PASS | PASS | PASS |
| `lead_screw` | `lead_screw.calc.1.0.0` | 20 | PASS | PASS | PASS |
| `synchronous_belt` | `synchronous_belt.calc.1.0.0` | 12 | PASS | PASS | PASS |
| `motor_drive` | `motor_drive.calc.1.0.0` | 16 | PASS | PASS | PASS |
| `stepper_motor` | `stepper_motor.calc.1.0.0` | 13 | PASS | PASS | PASS |
| `pneumatic_cylinder` | `pneumatic_cylinder.calc.1.0.0` | 17 | PASS | PASS | PASS |
| **合计** | — | **126** | **PASS** | **PASS** | **PASS** |

“126”是八模块公式实例总数，不是全平台总数；绞车模块公式另见 [`FORMULA_TEST_MATRIX.md`](FORMULA_TEST_MATRIX.md)。

## 2. 自动化证据索引

### 2.1 A 组

文件：`tests/test_engineering_modules_group_a.py`

| 证据代号 | 测试 |
|---|---|
| `TC-G1` | `TransmissionCheckTests.test_two_stage_independent_gold_case` |
| `TC-G4` | `TransmissionCheckTests.test_four_stage_path_executes_all_dynamic_stage_formula_ids` |
| `TC-B` | `TransmissionCheckTests.test_stage_count_and_cross_field_boundaries` |
| `TC-M` | `TransmissionCheckTests.test_missing_candidate_is_review_required` |
| `TC-R` | `TransmissionCheckTests.test_repeat_execution_is_identical` |
| `GD-G` | `GearDriveTests.test_spur_gear_independent_gold_case` |
| `GD-B` | `GearDriveTests.test_angle_and_optional_supplier_data_boundaries` |
| `GD-M` | `GearDriveTests.test_missing_supplier_limits_are_review_required` |
| `GD-R` | `GearDriveTests.test_repeat_execution_is_identical` |
| `SB-G` | `ShaftBearingTests.test_bearing_life_and_shaft_stress_independent_gold_case` |
| `SB-B` | `ShaftBearingTests.test_cross_field_and_source_requirements` |
| `SB-M` | `ShaftBearingTests.test_missing_allowable_stress_is_review_required` |
| `SB-R` | `ShaftBearingTests.test_repeat_execution_is_identical` |
| `LS-G` | `LeadScrewTests.test_square_thread_and_euler_independent_gold_case` |
| `LS-B` | `LeadScrewTests.test_geometry_formula_and_candidate_cross_field_boundaries` |
| `LS-M` | `LeadScrewTests.test_missing_candidate_is_review_required` |
| `LS-R` | `LeadScrewTests.test_repeat_execution_is_identical` |

### 2.2 B 组

文件：`tests/test_engineering_modules_group_b.py`

| 证据代号 | 测试 |
|---|---|
| `BELT-G` | `SynchronousBeltTests.test_independent_golden_case` |
| `BELT-B1` | `SynchronousBeltTests.test_geometrically_intersecting_pitch_circles_are_rejected` |
| `BELT-B2` | `SynchronousBeltTests.test_incomplete_candidate_provenance_is_rejected` |
| `BELT-M` | `SynchronousBeltTests.test_missing_manufacturer_limits_remain_review_required` |
| `MOTOR-G` | `MotorDriveTests.test_independent_golden_case` |
| `MOTOR-B1` | `MotorDriveTests.test_zero_duration_is_rejected` |
| `MOTOR-B2` | `MotorDriveTests.test_candidate_data_requires_source_and_reference` |
| `MOTOR-M` | `MotorDriveTests.test_missing_candidate_data_remains_review_required` |
| `STEP-G` | `StepperMotorTests.test_independent_golden_case` |
| `STEP-B1` | `StepperMotorTests.test_curve_point_must_match_working_speed_with_explicit_tolerance` |
| `STEP-B2` | `StepperMotorTests.test_partial_curve_point_is_rejected` |
| `STEP-M` | `StepperMotorTests.test_missing_curve_and_inertia_limit_remain_review_required` |
| `CYL-G` | `PneumaticCylinderTests.test_independent_golden_case` |
| `CYL-B1` | `PneumaticCylinderTests.test_rod_must_be_smaller_than_bore` |
| `CYL-B2` | `PneumaticCylinderTests.test_supply_absolute_pressure_must_exceed_ambient` |
| `CYL-M` | `PneumaticCylinderTests.test_missing_candidate_pressure_rating_remains_review_required` |
| `B-R` | `GroupBContractTests.test_calculations_are_exactly_repeatable` |
| `B-C` | `GroupBContractTests.test_public_contract_and_audit_payload_are_complete` |
| `B-BASIS` | `GroupBContractTests.test_common_basis_reference_is_strictly_non_blank` |

API、快照、HTML 和 PDF 的八模块贯通证据另见 `tests/test_expanded_module_api.py`。

### 2.3 派生数值安全

文件：`tests/test_expanded_numeric_safety.py`

| 证据代号 | 测试 |
|---|---|
| `NUM-FLOAT-MODEL` | `ExpandedNumericSafetyTests.test_each_input_rejects_unsafe_derived_float_arithmetic` |
| `NUM-FLOAT-API` | `ExpandedNumericSafetyTests.test_each_unsafe_numeric_input_returns_api_422` |

`NUM-FLOAT-MODEL` 对八个模块逐一注入 `5e-324` 及会使连乘、乘方、SI 换算或实际分母下溢的组合，证明输入模型在调用计算器前统一拒绝非有限、失去正值或不可安全相除的派生量。`NUM-FLOAT-API` 证明相同八组输入经真实计算 API 均返回 `422 VALIDATION_ERROR`，不会泄漏为 `ZeroDivisionError`、结果模型错误或 HTTP 500。该门禁只判断 IEEE 754 算术是否可安全执行，不引入工程允许下限。

## 3. 独立手算金样关键期望

这些数值来自测试中的独立算术注释和断言，不调用生产函数生成期望值。

| 金样 | 关键输入与独立期望 |
|---|---|
| `TC-A-001` | `i=3*4=12`；`eta=.95*.90=.855`；`T_out=100*12*.855=1026 N·m`；`omega_out=13.089969389957473 rad/s`；`P_out=13430.308594096367 W`；候选余量 `1100-1026=74 N·m`。 |
| `TC-A-004` | `i=3*4*2*5=120`；`eta=.95*.90*.98*.97=.812763`；`T_out=100*120*.812763=9753.156 N·m`；并断言 `KIN/TORQUE/POWER-013/-014` 均进入步骤。 |
| `GD-A-001` | `m=.004 m`；`d1=.08 m`；`d2=.24 m`；`a=.16 m`；`i=3`；`Ft=2500 N`；`Fr=909.9255856655059 N`；`v=5.026548245743669 m/s`；`T2=291 N·m`。 |
| `SB-A-001` | `P=.56*5000+1.6*1000=4400 N`；`L10=1000×10^6 rev`；`L10h=27777.777777777777 h`；`sigma_b=40743665.4315252 Pa`；`tau=12223099.62945756 Pa`；`sigma_vm=45915779.05743295 Pa`；许用余量 `74084220.94256705 Pa`。 |
| `LS-A-001` | `tan(lambda)=.006/(pi*.03)`；`lambda=.06357618167828312 rad`；`T_raise=27.761377890392023 N·m`；`T_lower=8.386634248253639 N·m`；`eta=.34397776015356396`；`v=.03 m/s`；`Fcr=93762.98068122665 N`；候选余量 `5000 N`。 |
| `BELT-GOLD-001` | `i=2`；`omega2=50 rad/s`；`d1=.06366197723675814 m`；`d2=.12732395447351627 m`；`v=3.1830988618379066 m/s`；`P_d=3000 W`；`F=942.477796076938 N`；`L=1.3020264236728467 m`；`alpha=3.0141825377923603 rad`；`z_engaged=9.594441005418556`。 |
| `MOTOR-GOLD-001` | `T1=25 N·m`；`T2=12.5 N·m`；`omega1=50 rad/s`；`omega2=25 rad/s`；`T_cont=17.5 N·m`；`T_peak=25 N·m`；`T_rms=18.540496217739157 N·m`；所需连续/峰值/RMS=`21/30/22.24859546128699 N·m`；`P=1500 W`。 |
| `STEP-GOLD-001` | `J_ref=.00125 kg·m²`；`J_total=.00225 kg·m²`；`omega=20 rad/s`；`alpha=10 rad/s²`；惯性/稳态/合成转矩=`.0225/2.5/2.5225 N·m`；所需稳态/峰值=`3.75/3.78375 N·m`；`f=10185.916357881302 Hz`；惯量比 `1.25`。 |
| `CYL-GOLD-001` | `A_ext=.007853981633974483 m²`；`A_ret=.006597344572538567 m²`；`Delta_p=600000 Pa`；理论伸/缩力=`4712.3889803846905/3958.40674352314 N`；需求力=`3600/2400 N`；余量=`1112.3889803846905/1558.40674352314 N`；每循环参考体积 `.05057964172279568 m³`；参考耗气 `.5057964172279568 m³/min`。 |

## 4. `transmission_check` 公式映射

共同边界证据 `TC-B`：拒绝 5 级、重复级名和不完整候选三元组。共同缺候选证据 `TC-M`：三个候选结果均为 `null/review_required`；基础公式仍执行。`TC-R` 证明同输入重复执行完全一致。

| 公式 ID | 正常金样证据 | 边界/非法证据 | 缺候选语义 | 状态 |
|---|---|---|---|---|
| `UNIT-001` | `TC-G1`：1500 r/min 路径 | `TC-B` 在公式前门禁 | 仍执行 | PASS |
| `KIN-001` | `TC-G1`：12；`TC-G4`：120 | `TC-B` 限制 1～4 级 | 仍执行 | PASS |
| `POWER-001` | `TC-G1`：.855；`TC-G4`：.812763 | `TC-B` 阻断无效级 | 仍执行 | PASS |
| `POWER-002` | `TC-G1` 金样路径执行 | `TC-B` 在公式前门禁 | 仍执行 | PASS |
| `KIN-011` | `TC-G1` 两级链 | `TC-B` 在公式前门禁 | 仍执行 | PASS |
| `TORQUE-011` | `TC-G1` 两级链 | `TC-B` 在公式前门禁 | 仍执行 | PASS |
| `POWER-011` | `TC-G1` 两级链 | `TC-B` 在公式前门禁 | 仍执行 | PASS |
| `KIN-012` | `TC-G1`：最终 13.089969389957473 rad/s | `TC-B` 在公式前门禁 | 仍执行 | PASS |
| `TORQUE-012` | `TC-G1`：最终 1026 N·m | `TC-B` 在公式前门禁 | 仍执行 | PASS |
| `POWER-012` | `TC-G1`：最终 13430.308594096367 W | `TC-B` 在公式前门禁 | 仍执行 | PASS |
| `KIN-013` | `TC-G4` 明确断言步骤存在 | `TC-B` 禁止第 5 级 | 仍执行 | PASS |
| `TORQUE-013` | `TC-G4` 明确断言步骤存在 | `TC-B` 禁止第 5 级 | 仍执行 | PASS |
| `POWER-013` | `TC-G4` 明确断言步骤存在 | `TC-B` 禁止第 5 级 | 仍执行 | PASS |
| `KIN-014` | `TC-G4` 明确断言步骤存在 | `TC-B` 禁止第 5 级 | 仍执行 | PASS |
| `TORQUE-014` | `TC-G4`：最终 9753.156 N·m | `TC-B` 禁止第 5 级 | 仍执行 | PASS |
| `POWER-014` | `TC-G4` 明确断言步骤存在 | `TC-B` 禁止第 5 级 | 仍执行 | PASS |
| `CHECK-001` | `TC-G1` 候选利用率路径 | `TC-B` 拒绝不完整候选 | `null/review_required`，无步骤 | PASS |
| `CHECK-002` | `TC-G1`：`true` | `TC-B` 拒绝不完整候选 | `null/review_required`，无步骤 | PASS |
| `CHECK-003` | `TC-G1`：74 N·m 且公式 ID 断言 | `TC-B` 拒绝不完整候选 | `null/review_required`，无步骤 | PASS |

## 5. `gear_drive` 公式映射

共同边界证据 `GD-B`：拒绝 90° 压力角、不完整许用力来源和空白总体依据。共同缺候选证据 `GD-M`：四个候选结果分别为 `null/review_required`。`GD-R` 证明确定性。

| 公式 ID | 正常金样证据 | 边界/非法证据 | 缺候选语义 | 状态 |
|---|---|---|---|---|
| `UNIT-001` | `GD-G`：4 mm→.004 m 路径 | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `UNIT-002` | `GD-G`：20° 路径 | `GD-B` 拒绝 90° | 仍执行 | PASS |
| `UNIT-003` | `GD-G`：1200 r/min 路径 | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `GEOM-001` | `GD-G`：.08 m | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `GEOM-002` | `GD-G`：.24 m | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `GEOM-003` | `GD-G`：.16 m | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `KIN-001` | `GD-G`：3 | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `FORCE-001` | `GD-G`：2500 N | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `FORCE-002` | `GD-G`：909.9255856655059 N | `GD-B` 拒绝非法角度 | 仍执行 | PASS |
| `KIN-002` | `GD-G`：5.026548245743669 m/s | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `KIN-003` | `GD-G` 金样路径执行 | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `TORQUE-001` | `GD-G`：291 N·m | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `POWER-001` | `GD-G` 金样路径执行 | `GD-B` 在公式前门禁 | 仍执行 | PASS |
| `CHECK-001` | `GD-G` 候选力利用率路径 | `GD-B` 拒绝不完整候选 | 对应结果 `null/review_required` | PASS |
| `CHECK-002` | `GD-G`：`true` | `GD-B` 拒绝不完整候选 | 对应结果 `null/review_required` | PASS |
| `CHECK-003` | `GD-G` 候选速度利用率路径 | `GD-B` 拒绝不完整候选 | 对应结果 `null/review_required` | PASS |
| `CHECK-004` | `GD-G` 候选速度通过路径 | `GD-B` 拒绝不完整候选 | 对应结果 `null/review_required` | PASS |

## 6. `shaft_bearing` 公式映射

共同边界证据 `SB-B`：拒绝 `X*Fr+Y*Fa=0`、弯矩与扭矩同时为 0、缺少 `X` 来源和不完整许用应力三元组。共同缺候选证据 `SB-M`：利用率、余量和通过标志为 `null/review_required`。`SB-R` 证明确定性。

| 公式 ID | 正常金样证据 | 边界/非法证据 | 缺候选语义 | 状态 |
|---|---|---|---|---|
| `UNIT-001` | `SB-G`：600 r/min 寿命路径 | `SB-B` 在公式前门禁 | 仍执行 | PASS |
| `UNIT-002` | `SB-G`：50 mm→.05 m 路径 | `SB-B` 在公式前门禁 | 仍执行 | PASS |
| `UNIT-003` | `SB-G`：120 MPa→120e6 Pa 路径 | `SB-B` 拒绝不完整候选 | 不执行 | PASS |
| `FORCE-001` | `SB-G`：4400 N | `SB-B` 拒绝零等效载荷 | 仍执行 | PASS |
| `LIFE-001` | `SB-G`：1000×10^6 rev | `SB-B` 拒绝零等效载荷 | 仍执行 | PASS |
| `LIFE-002` | `SB-G`：27777.777777777777 h | `SB-B` 拒绝零等效载荷 | 仍执行 | PASS |
| `STRESS-001` | `SB-G`：40743665.4315252 Pa | `SB-B` 拒绝零弯矩且零扭矩 | 仍执行 | PASS |
| `STRESS-002` | `SB-G`：12223099.62945756 Pa | `SB-B` 拒绝零弯矩且零扭矩 | 仍执行 | PASS |
| `STRESS-003` | `SB-G`：45915779.05743295 Pa | `SB-B` 拒绝零弯矩且零扭矩 | 仍执行 | PASS |
| `CHECK-001` | `SB-G` 许用应力利用率路径 | `SB-B` 拒绝不完整候选 | `null/review_required`，无步骤 | PASS |
| `CHECK-002` | `SB-G`：`true` | `SB-B` 拒绝不完整候选 | `null/review_required`，无步骤 | PASS |
| `CHECK-003` | `SB-G`：74084220.94256705 Pa 且公式 ID 断言 | `SB-B` 拒绝不完整候选 | `null/review_required`，无步骤 | PASS |

## 7. `lead_screw` 公式映射

共同边界证据 `LS-B`：拒绝根径不小于中径、使提升转矩分母奇异/反号的摩擦组合和不完整候选三元组。共同缺候选证据 `LS-M`：候选利用率、余量和通过标志为 `null/review_required`。`LS-R` 证明确定性。

| 公式 ID | 正常金样证据 | 边界/非法证据 | 缺候选语义 | 状态 |
|---|---|---|---|---|
| `UNIT-001` | `LS-G`：30 mm→.03 m 路径 | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `UNIT-002` | `LS-G`：24 mm→.024 m 路径 | `LS-B` 拒绝根径>=中径 | 仍执行 | PASS |
| `UNIT-003` | `LS-G`：6 mm/rev→.006 m/rev | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `UNIT-004` | `LS-G`：300 r/min 路径 | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `UNIT-005` | `LS-G`：210 GPa→210e9 Pa | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `UNIT-006` | `LS-G`：600 mm→.6 m | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `KIN-001` | `LS-G`：.06357618167828312 rad | `LS-B` 拒绝奇异组合 | 仍执行 | PASS |
| `TORQUE-001` | `LS-G`：27.761377890392023 N·m | `LS-B` 拒绝奇异组合 | 仍执行 | PASS |
| `TORQUE-002` | `LS-G`：8.386634248253639 N·m | `LS-B` 拒绝无效几何 | 仍执行 | PASS |
| `POWER-001` | `LS-G`：.34397776015356396 | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `KIN-002` | `LS-G`：.03 m/s | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `POWER-002` | `LS-G` 金样路径执行 | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `CHECK-001` | `LS-G`：`true` | `LS-B` 拒绝奇异组合 | 仍执行 | PASS |
| `BUCKLING-001` | `LS-G` 金样路径执行 | `LS-B` 拒绝无效根径 | 仍执行 | PASS |
| `BUCKLING-002` | `LS-G`：93762.98068122665 N | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `CHECK-002` | `LS-G` Euler 利用率路径 | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `CHECK-003` | `LS-G`：`true` | `LS-B` 在公式前门禁 | 仍执行 | PASS |
| `CHECK-004` | `LS-G` 候选利用率路径 | `LS-B` 拒绝不完整候选 | `null/review_required`，无步骤 | PASS |
| `CHECK-005` | `LS-G`：`true` | `LS-B` 拒绝不完整候选 | `null/review_required`，无步骤 | PASS |
| `CHECK-006` | `LS-G`：5000 N 且公式 ID 断言 | `LS-B` 拒绝不完整候选 | `null/review_required`，无步骤 | PASS |

## 8. `synchronous_belt` 公式映射

共同边界证据 `BELT-B1/B2`：拒绝节圆相交和候选额定数据缺来源。共同缺候选证据 `BELT-M`：两个通过标志为 `null/review_required`。`B-R/B-C` 证明确定性和审计载荷完整。

| 公式 ID | 正常金样证据 | 边界/非法证据 | 缺候选语义 | 状态 |
|---|---|---|---|---|
| `BELT_KIN-001` | `BELT-G`：2 | `BELT-B1` 在公式前门禁 | 仍执行 | PASS |
| `BELT_KIN-002` | `BELT-G`：50 rad/s | `BELT-B1` 在公式前门禁 | 仍执行 | PASS |
| `BELT_GEOM-001` | `BELT-G`：.06366197723675814 m | `BELT-B1` 几何门禁 | 仍执行 | PASS |
| `BELT_GEOM-002` | `BELT-G`：.12732395447351627 m | `BELT-B1` 几何门禁 | 仍执行 | PASS |
| `BELT_KIN-003` | `BELT-G`：3.1830988618379066 m/s | `BELT-B1` 在公式前门禁 | 仍执行 | PASS |
| `BELT_POWER-001` | `BELT-G`：3000 W | `BELT-B1` 在公式前门禁 | 仍执行 | PASS |
| `BELT_FORCE-001` | `BELT-G`：942.477796076938 N | `BELT-B1` 在公式前门禁 | 仍执行 | PASS |
| `BELT_GEOM-003` | `BELT-G`：1.3020264236728467 m | `BELT-B1` 拒绝相交几何 | 仍执行 | PASS |
| `BELT_GEOM-004` | `BELT-G`：3.0141825377923603 rad | `BELT-B1` 拒绝相交几何 | 仍执行 | PASS |
| `BELT_GEOM-005` | `BELT-G`：9.594441005418556 tooth | `BELT-B1` 拒绝相交几何 | 仍执行 | PASS |
| `BELT_CHECK-001` | `BELT-G`：`true` | `BELT-B2` 拒绝缺来源候选 | `null/review_required`，无步骤 | PASS |
| `BELT_CHECK-002` | `BELT-G`：`true` | `BELT-B2` 拒绝缺来源候选 | `null/review_required`，无步骤 | PASS |

## 9. `motor_drive` 公式映射

共同边界证据 `MOTOR-B1/B2`：拒绝零时长和缺来源的候选额定数据。共同缺候选证据 `MOTOR-M`：四个候选通过标志为 `null/review_required`。`B-R/B-C` 证明确定性和审计载荷完整。

| 公式 ID | 正常金样证据 | 边界/非法证据 | 缺候选语义 | 状态 |
|---|---|---|---|---|
| `MOTOR_TORQUE-001` | `MOTOR-G`：25 N·m | `MOTOR-B1` 拒绝零时长 | 仍执行 | PASS |
| `MOTOR_TORQUE-002` | `MOTOR-G`：12.5 N·m | `MOTOR-B1` 拒绝零时长 | 仍执行 | PASS |
| `MOTOR_KIN-001` | `MOTOR-G`：50 rad/s | `MOTOR-B1` 在公式前门禁 | 仍执行 | PASS |
| `MOTOR_KIN-002` | `MOTOR-G`：25 rad/s | `MOTOR-B1` 在公式前门禁 | 仍执行 | PASS |
| `MOTOR_TORQUE-003` | `MOTOR-G`：17.5 N·m | `MOTOR-B1` 拒绝零时长 | 仍执行 | PASS |
| `MOTOR_TORQUE-004` | `MOTOR-G`：25 N·m | `MOTOR-B1` 在公式前门禁 | 仍执行 | PASS |
| `MOTOR_TORQUE-005` | `MOTOR-G`：18.540496217739157 N·m | `MOTOR-B1` 拒绝零时长 | 仍执行 | PASS |
| `MOTOR_TORQUE-006` | `MOTOR-G`：21 N·m | `MOTOR-B1` 在公式前门禁 | 仍执行 | PASS |
| `MOTOR_TORQUE-007` | `MOTOR-G`：30 N·m | `MOTOR-B1` 在公式前门禁 | 仍执行 | PASS |
| `MOTOR_TORQUE-008` | `MOTOR-G`：22.24859546128699 N·m | `MOTOR-B1` 在公式前门禁 | 仍执行 | PASS |
| `MOTOR_POWER-001` | `MOTOR-G`：1500 W | `MOTOR-B1` 在公式前门禁 | 仍执行 | PASS |
| `MOTOR_KIN-003` | `MOTOR-G`：50 rad/s | `MOTOR-B1` 在公式前门禁 | 仍执行 | PASS |
| `MOTOR_CHECK-001` | `MOTOR-G`：`true` | `MOTOR-B2` 拒绝缺来源候选 | `null/review_required`，无步骤 | PASS |
| `MOTOR_CHECK-002` | `MOTOR-G`：`true` | `MOTOR-B2` 拒绝缺来源候选 | `null/review_required`，无步骤 | PASS |
| `MOTOR_CHECK-003` | `MOTOR-G`：`true` | `MOTOR-B2` 拒绝缺来源候选 | `null/review_required`，无步骤 | PASS |
| `MOTOR_CHECK-004` | `MOTOR-G`：`true` | `MOTOR-B2` 拒绝缺来源候选 | `null/review_required`，无步骤 | PASS |

## 10. `stepper_motor` 公式映射

共同边界证据 `STEP-B1/B2`：拒绝不匹配容差的曲线速度和不完整曲线三元组。共同缺候选证据 `STEP-M`：曲线与惯量比通过标志为 `null/review_required`。`B-R/B-C` 证明确定性和审计载荷完整。

| 公式 ID | 正常金样证据 | 边界/非法证据 | 缺候选语义 | 状态 |
|---|---|---|---|---|
| `STEP_INERTIA-001` | `STEP-G`：.00125 kg·m² | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_INERTIA-002` | `STEP-G`：.00225 kg·m² | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_KIN-001` | `STEP-G`：20 rad/s | `STEP-B1` 校验该工作速度 | 仍执行 | PASS |
| `STEP_KIN-002` | `STEP-G`：10 rad/s² | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_TORQUE-001` | `STEP-G`：.0225 N·m | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_TORQUE-002` | `STEP-G`：2.5 N·m | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_TORQUE-003` | `STEP-G`：2.5225 N·m | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_TORQUE-004` | `STEP-G`：3.75 N·m | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_TORQUE-005` | `STEP-G`：3.78375 N·m | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_KIN-003` | `STEP-G`：10185.916357881302 Hz | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_INERTIA-003` | `STEP-G`：1.25 | `STEP-B1` 在公式前门禁 | 仍执行 | PASS |
| `STEP_CHECK-001` | `STEP-G`：`true` | `STEP-B1/B2` 拒绝无效曲线点 | `null/review_required`，无步骤 | PASS |
| `STEP_CHECK-002` | `STEP-G`：`true` | `STEP-B2` 候选来源门禁 | `null/review_required`，无步骤 | PASS |

## 11. `pneumatic_cylinder` 公式映射

共同边界证据 `CYL-B1/B2`：拒绝杆径不小于缸径以及供气绝压不高于环境绝压。共同缺候选证据 `CYL-M`：压力额定通过标志为 `null/review_required`。`B-R/B-C` 证明确定性和审计载荷完整。

| 公式 ID | 正常金样证据 | 边界/非法证据 | 缺候选语义 | 状态 |
|---|---|---|---|---|
| `CYL_GEOM-001` | `CYL-G`：.007853981633974483 m² | `CYL-B1` 几何门禁 | 仍执行 | PASS |
| `CYL_GEOM-002` | `CYL-G`：.006597344572538567 m² | `CYL-B1` 拒绝杆径>=缸径 | 仍执行 | PASS |
| `CYL_PRESSURE-001` | `CYL-G`：600000 Pa | `CYL-B2` 拒绝非正压差 | 仍执行 | PASS |
| `CYL_FORCE-001` | `CYL-G`：4712.3889803846905 N | `CYL-B1/B2` 在公式前门禁 | 仍执行 | PASS |
| `CYL_FORCE-002` | `CYL-G`：3958.40674352314 N | `CYL-B1/B2` 在公式前门禁 | 仍执行 | PASS |
| `CYL_FORCE-003` | `CYL-G`：3600 N | `CYL-B1/B2` 在公式前门禁 | 仍执行 | PASS |
| `CYL_FORCE-004` | `CYL-G`：2400 N | `CYL-B1/B2` 在公式前门禁 | 仍执行 | PASS |
| `CYL_FORCE-005` | `CYL-G`：1112.3889803846905 N | `CYL-B1/B2` 在公式前门禁 | 仍执行 | PASS |
| `CYL_FORCE-006` | `CYL-G`：1558.40674352314 N | `CYL-B1/B2` 在公式前门禁 | 仍执行 | PASS |
| `CYL_CHECK-001` | `CYL-G`：`true` | `CYL-B1/B2` 在公式前门禁 | 仍执行 | PASS |
| `CYL_CHECK-002` | `CYL-G`：`true` | `CYL-B1/B2` 在公式前门禁 | 仍执行 | PASS |
| `CYL_AIR-001` | `CYL-G`：.003926990816987242 m³ | `CYL-B1` 几何门禁 | 仍执行 | PASS |
| `CYL_AIR-002` | `CYL-G`：.0032986722862692833 m³ | `CYL-B1` 几何门禁 | 仍执行 | PASS |
| `CYL_AIR-003` | `CYL-G`：.007225663103256525 m³ | `CYL-B1` 几何门禁 | 仍执行 | PASS |
| `CYL_AIR-004` | `CYL-G`：.05057964172279568 m³ | `CYL-B2` 压力门禁 | 仍执行 | PASS |
| `CYL_AIR-005` | `CYL-G`：.5057964172279568 m³/min | `CYL-B2` 压力门禁 | 仍执行 | PASS |
| `CYL_CHECK-003` | `CYL-G`：`true` | 候选压力也受绝压门禁 | `null/review_required`，无步骤 | PASS |

## 12. 审核边界

- 缺候选测试只证明软件不会在没有可追溯限值时生成伪合格结论。
- `NUM-FLOAT-MODEL/API` 只证明派生浮点运算在进入公式前受控；它们不是尺寸、转速、载荷或压力的工程下限。
- `preliminary=true` 只表示当前标量不等式成立；不覆盖规格中列出的强度、寿命、热、动态、安装、环境和安全项目。
- 金样中的候选值是测试数据，不是推荐参数或产品额定值。
- 模型、公式、输入口径或结果等级变化时，必须同步更新计算规格、此矩阵和独立金样；不得只改期望值使测试通过。
