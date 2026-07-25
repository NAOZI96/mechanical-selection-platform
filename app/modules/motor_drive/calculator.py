"""Deterministic two-segment motor-side load reflection and candidate checks."""

from __future__ import annotations

import math

from app.modules.engineering_common import (
    AssumptionRecord,
    CalculationStatus,
    FormulaStep,
    ResultClassification,
    ScalarResult,
    SourceStatus,
    WarningRecord,
    WarningSeverity,
)

from .constants import CALCULATION_MODEL_VERSION, DISCLAIMER, MODULE_ID, MODULE_VERSION
from .schema import MotorDriveInput, MotorDriveResult


def _scalar(
    value: float | bool | None,
    unit: str,
    classification: ResultClassification,
    formula_id: str,
    reason: str | None = None,
) -> ScalarResult:
    return ScalarResult(
        value=value,
        unit=unit,
        classification=classification,
        formula_ids=(formula_id,),
        reason=reason,
    )


def _warning(
    code: str,
    severity: WarningSeverity,
    title: str,
    message: str,
    affected_result: tuple[str, ...],
    action: str,
) -> WarningRecord:
    return WarningRecord(
        code=code,
        severity=severity,
        title=title,
        message=message,
        affected_result=affected_result,
        recommended_action=action,
    )


def _candidate_check(
    *,
    actual: float,
    limit: float | None,
    formula_id: str,
    missing_reason: str,
) -> tuple[ScalarResult, bool | None]:
    if limit is None:
        return (
            _scalar(
                None,
                "",
                ResultClassification.REVIEW_REQUIRED,
                formula_id,
                missing_reason,
            ),
            None,
        )
    passed = actual <= limit
    return (
        _scalar(passed, "", ResultClassification.PRELIMINARY, formula_id),
        passed,
    )


def calculate(data: MotorDriveInput) -> MotorDriveResult:
    """Reflect the two load-side segments to the motor shaft and check a candidate."""

    if not isinstance(data, MotorDriveInput):
        raise TypeError("motor_drive calculate 需要 MotorDriveInput")

    ratio = data.transmission_ratio_motor_to_load
    efficiency = data.transmission_efficiency
    torque_1 = data.segment_1_load_torque_n_m / (ratio * efficiency)
    torque_2 = data.segment_2_load_torque_n_m / (ratio * efficiency)
    speed_1 = data.segment_1_load_speed_rad_s * ratio
    speed_2 = data.segment_2_load_speed_rad_s * ratio
    total_duration = data.segment_1_duration_s + data.segment_2_duration_s
    continuous_torque = (torque_1 * data.segment_1_duration_s + torque_2 * data.segment_2_duration_s) / total_duration
    peak_torque = max(torque_1, torque_2)
    rms_torque = math.sqrt(
        (torque_1**2 * data.segment_1_duration_s + torque_2**2 * data.segment_2_duration_s) / total_duration
    )
    required_continuous_torque = continuous_torque * data.service_factor
    required_peak_torque = peak_torque * data.service_factor
    required_rms_torque = rms_torque * data.service_factor
    power_1 = torque_1 * speed_1
    power_2 = torque_2 * speed_2
    required_power = max(power_1, power_2) * data.service_factor
    maximum_motor_speed = max(speed_1, speed_2)

    steps = [
        FormulaStep(
            sequence=1,
            formula_id="MOTOR_TORQUE-001",
            expression="T_m1 = T_load1 / (i * eta)",
            variables={
                "T_load1": data.segment_1_load_torque_n_m,
                "i": ratio,
                "eta": efficiency,
            },
            result_value=torque_1,
            unit="N*m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=2,
            formula_id="MOTOR_TORQUE-002",
            expression="T_m2 = T_load2 / (i * eta)",
            variables={
                "T_load2": data.segment_2_load_torque_n_m,
                "i": ratio,
                "eta": efficiency,
            },
            result_value=torque_2,
            unit="N*m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=3,
            formula_id="MOTOR_KIN-001",
            expression="omega_m1 = omega_load1 * i",
            variables={"omega_load1": data.segment_1_load_speed_rad_s, "i": ratio},
            result_value=speed_1,
            unit="rad/s",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=4,
            formula_id="MOTOR_KIN-002",
            expression="omega_m2 = omega_load2 * i",
            variables={"omega_load2": data.segment_2_load_speed_rad_s, "i": ratio},
            result_value=speed_2,
            unit="rad/s",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=5,
            formula_id="MOTOR_TORQUE-003",
            expression="T_cont = (T_m1*t1 + T_m2*t2) / (t1+t2)",
            variables={
                "T_m1": torque_1,
                "t1": data.segment_1_duration_s,
                "T_m2": torque_2,
                "t2": data.segment_2_duration_s,
            },
            result_value=continuous_torque,
            unit="N*m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=6,
            formula_id="MOTOR_TORQUE-004",
            expression="T_peak = max(T_m1, T_m2)",
            variables={"T_m1": torque_1, "T_m2": torque_2},
            result_value=peak_torque,
            unit="N*m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=7,
            formula_id="MOTOR_TORQUE-005",
            expression="T_rms = sqrt((T_m1^2*t1 + T_m2^2*t2)/(t1+t2))",
            variables={
                "T_m1": torque_1,
                "t1": data.segment_1_duration_s,
                "T_m2": torque_2,
                "t2": data.segment_2_duration_s,
            },
            result_value=rms_torque,
            unit="N*m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=8,
            formula_id="MOTOR_TORQUE-006",
            expression="T_cont_required = T_cont * K_service",
            variables={"T_cont": continuous_torque, "K_service": data.service_factor},
            result_value=required_continuous_torque,
            unit="N*m",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=9,
            formula_id="MOTOR_TORQUE-007",
            expression="T_peak_required = T_peak * K_service",
            variables={"T_peak": peak_torque, "K_service": data.service_factor},
            result_value=required_peak_torque,
            unit="N*m",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=10,
            formula_id="MOTOR_TORQUE-008",
            expression="T_rms_required = T_rms * K_service",
            variables={"T_rms": rms_torque, "K_service": data.service_factor},
            result_value=required_rms_torque,
            unit="N*m",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=11,
            formula_id="MOTOR_POWER-001",
            expression="P_required = max(T_m1*omega_m1, T_m2*omega_m2) * K_service",
            variables={
                "T_m1": torque_1,
                "omega_m1": speed_1,
                "T_m2": torque_2,
                "omega_m2": speed_2,
                "K_service": data.service_factor,
            },
            result_value=required_power,
            unit="W",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=12,
            formula_id="MOTOR_KIN-003",
            expression="omega_motor_max = max(omega_m1, omega_m2)",
            variables={"omega_m1": speed_1, "omega_m2": speed_2},
            result_value=maximum_motor_speed,
            unit="rad/s",
            classification=ResultClassification.CALCULATED,
        ),
    ]

    warnings: list[WarningRecord] = [
        _warning(
            "MOTOR_TWO_SEGMENT_BOUNDARY",
            WarningSeverity.INFO,
            "模型仅包含两个稳态工作段",
            "RMS转矩和功率只覆盖输入的两个稳态段，未包含启动、加速、减速、停机或冲击事件。",
            ("rms_motor_torque_n_m", "required_power_w"),
            "在最终选型前补充完整工作循环、负载惯量和瞬态转矩。",
        ),
        _warning(
            "MOTOR_DUTY_UNCONFIRMED",
            WarningSeverity.HIGH,
            "工作制与热容量待确认",
            "用户声明的工作制尚未通过制造商热模型或适用标准校核。",
            ("candidate_rated_torque_pass", "candidate_rated_power_pass"),
            "由电机制造商按完整周期、环境温度、冷却方式和启停频次确认工作制及热容量。",
        ),
        _warning(
            "MOTOR_CURVE_UNCHECKED",
            WarningSeverity.HIGH,
            "制造商转矩-转速曲线待校核",
            "额定值和峰值的标量比较不能替代驱动器供电条件下的完整转矩-转速曲线。",
            ("candidate_peak_torque_pass", "candidate_speed_pass"),
            "取得电机与驱动器组合的制造商曲线，并覆盖全部稳态和瞬态工作点。",
        ),
    ]
    if data.basis_source_status is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            _warning(
                "MOTOR_BASIS_PENDING",
                WarningSeverity.WARNING,
                "计算依据待确认",
                "负载、传动效率或使用系数的依据尚未确认。",
                ("required_rms_torque_n_m", "required_power_w"),
                "由项目机械与电气工程师共同确认负载谱、效率和使用系数。",
            )
        )

    rated_result, rated_pass = _candidate_check(
        actual=required_rms_torque,
        limit=data.candidate_rated_torque_n_m,
        formula_id="MOTOR_CHECK-001",
        missing_reason="未提供候选电机额定转矩，无法按所需RMS转矩校核。",
    )
    peak_result, peak_pass = _candidate_check(
        actual=required_peak_torque,
        limit=data.candidate_peak_torque_n_m,
        formula_id="MOTOR_CHECK-002",
        missing_reason="未提供候选电机峰值转矩，无法完成峰值校核。",
    )
    speed_result, speed_pass = _candidate_check(
        actual=maximum_motor_speed,
        limit=data.candidate_max_speed_rad_s,
        formula_id="MOTOR_CHECK-003",
        missing_reason="未提供候选电机最大角速度，无法完成转速校核。",
    )
    power_result, power_pass = _candidate_check(
        actual=required_power,
        limit=data.candidate_rated_power_w,
        formula_id="MOTOR_CHECK-004",
        missing_reason="未提供候选电机额定功率，无法完成功率校核。",
    )

    checks = (
        (
            "MOTOR_CHECK-001",
            required_rms_torque,
            data.candidate_rated_torque_n_m,
            rated_pass,
            "required_rms_torque",
            "candidate_rated_torque",
        ),
        (
            "MOTOR_CHECK-002",
            required_peak_torque,
            data.candidate_peak_torque_n_m,
            peak_pass,
            "required_peak_torque",
            "candidate_peak_torque",
        ),
        (
            "MOTOR_CHECK-003",
            maximum_motor_speed,
            data.candidate_max_speed_rad_s,
            speed_pass,
            "maximum_motor_speed",
            "candidate_max_speed",
        ),
        (
            "MOTOR_CHECK-004",
            required_power,
            data.candidate_rated_power_w,
            power_pass,
            "required_power",
            "candidate_rated_power",
        ),
    )
    for formula_id, actual, limit, passed, actual_name, limit_name in checks:
        if limit is None or passed is None:
            warnings.append(
                _warning(
                    f"{formula_id.replace('-', '_')}_MISSING",
                    WarningSeverity.HIGH,
                    "候选电机额定数据不完整",
                    f"缺少 {limit_name}，对应候选校核保持待校核。",
                    (
                        {
                            "MOTOR_CHECK-001": "candidate_rated_torque_pass",
                            "MOTOR_CHECK-002": "candidate_peak_torque_pass",
                            "MOTOR_CHECK-003": "candidate_speed_pass",
                            "MOTOR_CHECK-004": "candidate_rated_power_pass",
                        }[formula_id],
                    ),
                    "补充候选电机制造商额定数据及可追溯版本。",
                )
            )
            continue
        steps.append(
            FormulaStep(
                sequence=len(steps) + 1,
                formula_id=formula_id,
                expression=f"pass = {actual_name} <= {limit_name}",
                variables={actual_name: actual, limit_name: limit},
                result_value=passed,
                unit="",
                classification=ResultClassification.PRELIMINARY,
            )
        )
        if not passed:
            warnings.append(
                _warning(
                    f"{formula_id.replace('-', '_')}_FAILED",
                    WarningSeverity.BLOCKING,
                    "候选电机额定值不足",
                    f"{actual_name} 超过所提供的 {limit_name}。",
                    (
                        {
                            "MOTOR_CHECK-001": "candidate_rated_torque_pass",
                            "MOTOR_CHECK-002": "candidate_peak_torque_pass",
                            "MOTOR_CHECK-003": "candidate_speed_pass",
                            "MOTOR_CHECK-004": "candidate_rated_power_pass",
                        }[formula_id],
                    ),
                    "重新选择电机/驱动器组合或调整传动比和工作循环。",
                )
            )

    if (
        data.candidate_data_source_status is not None
        and data.candidate_data_source_status is not SourceStatus.MANUFACTURER_DATA
    ):
        warnings.append(
            _warning(
                "MOTOR_CANDIDATE_SOURCE_UNCONFIRMED",
                WarningSeverity.WARNING,
                "候选电机数据并非已确认制造商数据",
                "标量校核结果可用于排查，但不能作为产品额定能力结论。",
                (
                    "candidate_rated_torque_pass",
                    "candidate_peak_torque_pass",
                    "candidate_speed_pass",
                    "candidate_rated_power_pass",
                ),
                "用制造商样本、曲线和驱动器组合数据替换当前候选值。",
            )
        )

    assumptions = [
        AssumptionRecord(
            key="calculation_basis",
            value=data.basis_reference,
            source_status=data.basis_source_status,
            note="所有载荷、速度和时间均由调用方以 SI 单位提供。",
        ),
        AssumptionRecord(
            key="two_segment_cycle",
            value=True,
            source_status=SourceStatus.PROJECT_SETTING,
            note="仅对两个明确稳态段进行时长加权；未隐式加入第三段或启动时间。",
        ),
        AssumptionRecord(
            key="transmission_ratio_definition",
            value=data.transmission_ratio_motor_to_load,
            source_status=data.basis_source_status,
            note="i=电机角速度/负载角速度；正向负载转矩按 Tm=Tload/(i*eta) 折算。",
        ),
        AssumptionRecord(
            key="transmission_efficiency",
            value=data.transmission_efficiency,
            source_status=data.basis_source_status,
            note="效率仅用于正向驱动转矩折算；本模型不处理再生或反驱效率。",
        ),
        AssumptionRecord(
            key="service_factor",
            value=data.service_factor,
            source_status=data.basis_source_status,
            note="使用系数在所需连续、峰值、RMS转矩和功率上各乘用一次。",
        ),
        AssumptionRecord(
            key="declared_duty",
            value=data.declared_duty,
            source_status=data.basis_source_status,
            note="该字段仅记录用户声明，模块不据此自动套用标准或热降额。",
        ),
    ]
    if data.candidate_reference is not None and data.candidate_data_source_status is not None:
        assumptions.append(
            AssumptionRecord(
                key="candidate_data",
                value=data.candidate_reference,
                source_status=data.candidate_data_source_status,
                note="候选额定值仅按用户声明的数据版本用于标量比较。",
            )
        )

    warning_tuple = tuple(warnings)
    return MotorDriveResult(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        status=(CalculationStatus.COMPLETED_WITH_WARNINGS if warning_tuple else CalculationStatus.COMPLETED),
        input_si=data,
        segment_1_motor_torque_n_m=_scalar(
            torque_1,
            "N*m",
            ResultClassification.CALCULATED,
            "MOTOR_TORQUE-001",
        ),
        segment_2_motor_torque_n_m=_scalar(
            torque_2,
            "N*m",
            ResultClassification.CALCULATED,
            "MOTOR_TORQUE-002",
        ),
        segment_1_motor_speed_rad_s=_scalar(
            speed_1,
            "rad/s",
            ResultClassification.CALCULATED,
            "MOTOR_KIN-001",
        ),
        segment_2_motor_speed_rad_s=_scalar(
            speed_2,
            "rad/s",
            ResultClassification.CALCULATED,
            "MOTOR_KIN-002",
        ),
        continuous_motor_torque_n_m=_scalar(
            continuous_torque,
            "N*m",
            ResultClassification.CALCULATED,
            "MOTOR_TORQUE-003",
        ),
        peak_motor_torque_n_m=_scalar(
            peak_torque,
            "N*m",
            ResultClassification.CALCULATED,
            "MOTOR_TORQUE-004",
        ),
        rms_motor_torque_n_m=_scalar(
            rms_torque,
            "N*m",
            ResultClassification.CALCULATED,
            "MOTOR_TORQUE-005",
        ),
        required_continuous_torque_n_m=_scalar(
            required_continuous_torque,
            "N*m",
            ResultClassification.PRELIMINARY,
            "MOTOR_TORQUE-006",
        ),
        required_peak_torque_n_m=_scalar(
            required_peak_torque,
            "N*m",
            ResultClassification.PRELIMINARY,
            "MOTOR_TORQUE-007",
        ),
        required_rms_torque_n_m=_scalar(
            required_rms_torque,
            "N*m",
            ResultClassification.PRELIMINARY,
            "MOTOR_TORQUE-008",
        ),
        required_power_w=_scalar(
            required_power,
            "W",
            ResultClassification.PRELIMINARY,
            "MOTOR_POWER-001",
        ),
        maximum_motor_speed_rad_s=_scalar(
            maximum_motor_speed,
            "rad/s",
            ResultClassification.CALCULATED,
            "MOTOR_KIN-003",
        ),
        candidate_rated_torque_pass=rated_result,
        candidate_peak_torque_pass=peak_result,
        candidate_speed_pass=speed_result,
        candidate_rated_power_pass=power_result,
        unchecked_items=(
            "acceleration_and_deceleration",
            "reflected_inertia",
            "duty_and_thermal_model",
            "manufacturer_torque_speed_curve",
            "regeneration_and_braking",
            "supply_and_drive_compatibility",
        ),
        calculation_steps=tuple(steps),
        warnings=warning_tuple,
        assumptions=tuple(assumptions),
        disclaimer=DISCLAIMER,
    )


__all__ = ["calculate"]
