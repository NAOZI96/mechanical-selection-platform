"""Deterministic stepper-motor inertia, motion, torque, and point checks."""

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
from .schema import StepperMotorInput, StepperMotorResult


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


def calculate(data: StepperMotorInput) -> StepperMotorResult:
    """Calculate a rigid, constant-acceleration stepper preselection."""

    if not isinstance(data, StepperMotorInput):
        raise TypeError("stepper_motor calculate 需要 StepperMotorInput")

    ratio = data.transmission_ratio_motor_to_load
    reflected_inertia = data.load_inertia_kg_m2 / ratio**2
    total_inertia = data.motor_rotor_inertia_kg_m2 + reflected_inertia
    working_speed = data.target_load_speed_rad_s * ratio
    angular_acceleration = working_speed / data.acceleration_time_s
    inertial_torque = total_inertia * angular_acceleration
    steady_motor_torque = data.steady_load_torque_n_m / (ratio * data.transmission_efficiency)
    acceleration_torque = inertial_torque + steady_motor_torque
    required_steady_torque = steady_motor_torque * data.service_factor
    required_peak_torque = acceleration_torque * data.service_factor
    pulse_frequency = working_speed / (2.0 * math.pi) * data.full_steps_per_revolution * data.microstep_divisor
    inertia_ratio = reflected_inertia / data.motor_rotor_inertia_kg_m2

    steps = [
        FormulaStep(
            sequence=1,
            formula_id="STEP_INERTIA-001",
            expression="J_reflected = J_load / i^2",
            variables={"J_load": data.load_inertia_kg_m2, "i": ratio},
            result_value=reflected_inertia,
            unit="kg*m^2",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=2,
            formula_id="STEP_INERTIA-002",
            expression="J_total = J_rotor + J_reflected",
            variables={
                "J_rotor": data.motor_rotor_inertia_kg_m2,
                "J_reflected": reflected_inertia,
            },
            result_value=total_inertia,
            unit="kg*m^2",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=3,
            formula_id="STEP_KIN-001",
            expression="omega_motor = omega_load * i",
            variables={"omega_load": data.target_load_speed_rad_s, "i": ratio},
            result_value=working_speed,
            unit="rad/s",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=4,
            formula_id="STEP_KIN-002",
            expression="alpha_motor = omega_motor / t_acceleration",
            variables={
                "omega_motor": working_speed,
                "t_acceleration": data.acceleration_time_s,
            },
            result_value=angular_acceleration,
            unit="rad/s^2",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=5,
            formula_id="STEP_TORQUE-001",
            expression="T_inertia = J_total * alpha_motor",
            variables={"J_total": total_inertia, "alpha_motor": angular_acceleration},
            result_value=inertial_torque,
            unit="N*m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=6,
            formula_id="STEP_TORQUE-002",
            expression="T_steady = T_load / (i * eta)",
            variables={
                "T_load": data.steady_load_torque_n_m,
                "i": ratio,
                "eta": data.transmission_efficiency,
            },
            result_value=steady_motor_torque,
            unit="N*m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=7,
            formula_id="STEP_TORQUE-003",
            expression="T_acceleration = T_inertia + T_steady",
            variables={"T_inertia": inertial_torque, "T_steady": steady_motor_torque},
            result_value=acceleration_torque,
            unit="N*m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=8,
            formula_id="STEP_TORQUE-004",
            expression="T_steady_required = T_steady * K_service",
            variables={
                "T_steady": steady_motor_torque,
                "K_service": data.service_factor,
            },
            result_value=required_steady_torque,
            unit="N*m",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=9,
            formula_id="STEP_TORQUE-005",
            expression="T_peak_required = T_acceleration * K_service",
            variables={
                "T_acceleration": acceleration_torque,
                "K_service": data.service_factor,
            },
            result_value=required_peak_torque,
            unit="N*m",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=10,
            formula_id="STEP_KIN-003",
            expression="f_pulse = omega_motor/(2*pi) * steps_per_rev * microstep",
            variables={
                "omega_motor": working_speed,
                "steps_per_rev": data.full_steps_per_revolution,
                "microstep": data.microstep_divisor,
            },
            result_value=pulse_frequency,
            unit="Hz",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=11,
            formula_id="STEP_INERTIA-003",
            expression="R_inertia = J_reflected / J_rotor",
            variables={
                "J_reflected": reflected_inertia,
                "J_rotor": data.motor_rotor_inertia_kg_m2,
            },
            result_value=inertia_ratio,
            unit="",
            classification=ResultClassification.CALCULATED,
        ),
    ]

    warnings: list[WarningRecord] = [
        _warning(
            "STEP_FULL_CURVE_UNCHECKED",
            WarningSeverity.HIGH,
            "完整转矩-转速曲线待校核",
            "即使提供一个匹配工作点，单点比较仍不能覆盖从零速到工作速度的整个加速路径。",
            ("candidate_curve_torque_pass", "required_peak_torque_n_m"),
            "使用电机、驱动器、电压和电流完全匹配的制造商曲线逐段校核加速路径。",
        ),
        _warning(
            "STEP_RESONANCE_UNCHECKED",
            WarningSeverity.HIGH,
            "共振与失步风险待验证",
            "恒加速度刚性模型不预测机械共振、步进共振、转矩脉动或失步。",
            ("required_peak_torque_n_m", "pulse_frequency_hz"),
            "进行机械模态评估、驱动参数整定和全工况样机试验。",
        ),
        _warning(
            "STEP_ACCELERATION_LOSS_MODEL_UNCHECKED",
            WarningSeverity.HIGH,
            "惯性加速损耗模型待确认",
            "当前传动效率只用于稳态负载转矩折算；负载惯性加速项未计入传动损耗。",
            ("inertial_acceleration_torque_n_m", "required_peak_torque_n_m"),
            "由机械工程师确认加速损耗口径；确认前按完整驱动链模型独立复算峰值转矩。",
        ),
    ]
    if data.basis_source_status is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            _warning(
                "STEP_BASIS_PENDING",
                WarningSeverity.WARNING,
                "计算依据待确认",
                "惯量、负载转矩、效率或使用系数的依据尚未确认。",
                ("required_peak_torque_n_m", "inertia_ratio"),
                "由机械与电气工程师共同确认负载模型和传动参数。",
            )
        )

    if data.candidate_curve_point_torque_n_m is None:
        curve_result = _scalar(
            None,
            "",
            ResultClassification.REVIEW_REQUIRED,
            "STEP_CHECK-001",
            "未提供与计算工作速度匹配的制造商曲线转矩工作点。",
        )
        warnings.append(
            _warning(
                "STEP_CURVE_POINT_MISSING",
                WarningSeverity.HIGH,
                "缺少候选曲线工作点",
                "所需峰值转矩尚未与候选电机/驱动器的可用转矩比较。",
                ("candidate_curve_torque_pass",),
                "提供工作点速度、可用转矩、显式速度容差和可追溯曲线版本。",
            )
        )
    else:
        curve_pass = required_peak_torque <= data.candidate_curve_point_torque_n_m
        curve_result = _scalar(
            curve_pass,
            "",
            ResultClassification.PRELIMINARY,
            "STEP_CHECK-001",
        )
        steps.append(
            FormulaStep(
                sequence=len(steps) + 1,
                formula_id="STEP_CHECK-001",
                expression="pass_curve_point = T_peak_required <= T_curve_point",
                variables={
                    "T_peak_required": required_peak_torque,
                    "T_curve_point": data.candidate_curve_point_torque_n_m,
                },
                result_value=curve_pass,
                unit="",
                classification=ResultClassification.PRELIMINARY,
            )
        )
        if not curve_pass:
            warnings.append(
                _warning(
                    "STEP_CURVE_POINT_FAILED",
                    WarningSeverity.BLOCKING,
                    "候选曲线工作点转矩不足",
                    "所需峰值转矩超过用户提供的候选曲线工作点可用转矩。",
                    ("candidate_curve_torque_pass",),
                    "降低加速度或负载、调整传动比，或重新选择电机/驱动器。",
                )
            )

    if data.candidate_allowable_inertia_ratio is None:
        inertia_check_result = _scalar(
            None,
            "",
            ResultClassification.REVIEW_REQUIRED,
            "STEP_CHECK-002",
            "未提供制造商或项目批准的允许惯量比。",
        )
        warnings.append(
            _warning(
                "STEP_INERTIA_LIMIT_MISSING",
                WarningSeverity.HIGH,
                "缺少允许惯量比",
                "已计算负载/转子惯量比，但没有经确认的允许值可供比较。",
                ("candidate_inertia_ratio_pass",),
                "提供候选电机/驱动器对应的允许惯量比及其适用条件。",
            )
        )
    else:
        inertia_pass = inertia_ratio <= data.candidate_allowable_inertia_ratio
        inertia_check_result = _scalar(
            inertia_pass,
            "",
            ResultClassification.PRELIMINARY,
            "STEP_CHECK-002",
        )
        steps.append(
            FormulaStep(
                sequence=len(steps) + 1,
                formula_id="STEP_CHECK-002",
                expression="pass_inertia = R_inertia <= R_allowable",
                variables={
                    "R_inertia": inertia_ratio,
                    "R_allowable": data.candidate_allowable_inertia_ratio,
                },
                result_value=inertia_pass,
                unit="",
                classification=ResultClassification.PRELIMINARY,
            )
        )
        if not inertia_pass:
            warnings.append(
                _warning(
                    "STEP_INERTIA_LIMIT_FAILED",
                    WarningSeverity.HIGH,
                    "候选惯量比超限",
                    "折算负载惯量与转子惯量之比超过所提供的允许值。",
                    ("candidate_inertia_ratio_pass",),
                    "调整传动比、降低负载惯量或选择转子惯量更合适的电机。",
                )
            )

    if (
        data.candidate_data_source_status is not None
        and data.candidate_data_source_status is not SourceStatus.MANUFACTURER_DATA
    ):
        warnings.append(
            _warning(
                "STEP_CANDIDATE_SOURCE_UNCONFIRMED",
                WarningSeverity.WARNING,
                "候选数据并非已确认制造商数据",
                "工作点和惯量比可以进行算术比较，但不能形成产品能力放行结论。",
                ("candidate_curve_torque_pass", "candidate_inertia_ratio_pass"),
                "用指定电压、电流、驱动器组合下的制造商曲线和惯量指南替换当前数据。",
            )
        )

    assumptions = [
        AssumptionRecord(
            key="calculation_basis",
            value=data.basis_reference,
            source_status=data.basis_source_status,
            note="全部惯量、速度、时间和转矩均由调用方以 SI 单位提供。",
        ),
        AssumptionRecord(
            key="transmission_ratio_definition",
            value=ratio,
            source_status=data.basis_source_status,
            note="i=电机角速度/负载角速度，负载惯量按 J_load/i^2 折算。",
        ),
        AssumptionRecord(
            key="rigid_transmission",
            value=True,
            source_status=SourceStatus.PROJECT_SETTING,
            note="模型假定传动刚性且无间隙，不包含联轴器、皮带或丝杠等自身惯量。",
        ),
        AssumptionRecord(
            key="constant_acceleration",
            value=True,
            source_status=SourceStatus.PROJECT_SETTING,
            note="从零速到目标速度按恒角加速度计算，未加入加加速度或速度曲线整形。",
        ),
        AssumptionRecord(
            key="transmission_efficiency",
            value=data.transmission_efficiency,
            source_status=data.basis_source_status,
            note="效率仅用于负载侧稳态转矩向电机侧的正向折算。",
        ),
        AssumptionRecord(
            key="service_factor",
            value=data.service_factor,
            source_status=data.basis_source_status,
            note="使用系数在合成加速转矩后乘用一次，不对分项重复叠加。",
        ),
        AssumptionRecord(
            key="pulse_command",
            value=f"{data.full_steps_per_revolution}*{data.microstep_divisor}",
            unit="pulse/rev",
            source_status=data.basis_source_status,
            note="脉冲频率按整步数和微步细分数直接换算，不推定默认步距角。",
        ),
    ]
    if data.candidate_reference is not None and data.candidate_data_source_status is not None:
        assumptions.append(
            AssumptionRecord(
                key="candidate_data",
                value=data.candidate_reference,
                source_status=data.candidate_data_source_status,
                note="曲线点和允许惯量比仅按用户声明的数据版本使用。",
            )
        )

    warning_tuple = tuple(warnings)
    return StepperMotorResult(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        status=(CalculationStatus.COMPLETED_WITH_WARNINGS if warning_tuple else CalculationStatus.COMPLETED),
        input_si=data,
        reflected_load_inertia_kg_m2=_scalar(
            reflected_inertia,
            "kg*m^2",
            ResultClassification.CALCULATED,
            "STEP_INERTIA-001",
        ),
        total_motor_side_inertia_kg_m2=_scalar(
            total_inertia,
            "kg*m^2",
            ResultClassification.CALCULATED,
            "STEP_INERTIA-002",
        ),
        working_motor_speed_rad_s=_scalar(
            working_speed,
            "rad/s",
            ResultClassification.CALCULATED,
            "STEP_KIN-001",
        ),
        motor_angular_acceleration_rad_s2=_scalar(
            angular_acceleration,
            "rad/s^2",
            ResultClassification.CALCULATED,
            "STEP_KIN-002",
        ),
        inertial_acceleration_torque_n_m=_scalar(
            inertial_torque,
            "N*m",
            ResultClassification.CALCULATED,
            "STEP_TORQUE-001",
        ),
        steady_motor_torque_n_m=_scalar(
            steady_motor_torque,
            "N*m",
            ResultClassification.CALCULATED,
            "STEP_TORQUE-002",
        ),
        acceleration_motor_torque_n_m=_scalar(
            acceleration_torque,
            "N*m",
            ResultClassification.CALCULATED,
            "STEP_TORQUE-003",
        ),
        required_steady_torque_n_m=_scalar(
            required_steady_torque,
            "N*m",
            ResultClassification.PRELIMINARY,
            "STEP_TORQUE-004",
        ),
        required_peak_torque_n_m=_scalar(
            required_peak_torque,
            "N*m",
            ResultClassification.PRELIMINARY,
            "STEP_TORQUE-005",
        ),
        pulse_frequency_hz=_scalar(
            pulse_frequency,
            "Hz",
            ResultClassification.CALCULATED,
            "STEP_KIN-003",
        ),
        inertia_ratio=_scalar(
            inertia_ratio,
            "",
            ResultClassification.CALCULATED,
            "STEP_INERTIA-003",
        ),
        candidate_curve_torque_pass=curve_result,
        candidate_inertia_ratio_pass=inertia_check_result,
        unchecked_items=(
            "full_torque_speed_curve",
            "resonance_and_step_loss",
            "driver_electrical_conditions",
            "motor_thermal_capacity",
            "positioning_accuracy",
            "transmission_compliance",
            "acceleration_transmission_loss_model",
            "holding_and_braking",
        ),
        calculation_steps=tuple(steps),
        warnings=warning_tuple,
        assumptions=tuple(assumptions),
        disclaimer=DISCLAIMER,
    )


__all__ = ["calculate"]
