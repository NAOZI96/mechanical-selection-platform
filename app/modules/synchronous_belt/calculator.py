"""Deterministic synchronous-belt kinematics, geometry, and candidate checks."""

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

from .constants import (
    CALCULATION_MODEL_VERSION,
    DISCLAIMER,
    MODULE_ID,
    MODULE_VERSION,
)
from .schema import SynchronousBeltInput, SynchronousBeltResult


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


def calculate(data: SynchronousBeltInput) -> SynchronousBeltResult:
    """Calculate an open synchronous-belt layout from explicit SI inputs."""

    if not isinstance(data, SynchronousBeltInput):
        raise TypeError("synchronous_belt calculate 需要 SynchronousBeltInput")

    ratio = data.driven_teeth / data.driver_teeth
    driven_speed = data.driver_angular_speed_rad_s / ratio
    driver_diameter = data.belt_pitch_m * data.driver_teeth / math.pi
    driven_diameter = data.belt_pitch_m * data.driven_teeth / math.pi
    belt_speed = data.driver_angular_speed_rad_s * driver_diameter / 2.0
    design_power = data.transmitted_power_w * data.service_factor
    effective_force = design_power / belt_speed

    diameter_large = max(driver_diameter, driven_diameter)
    diameter_small = min(driver_diameter, driven_diameter)
    teeth_small = min(data.driver_teeth, data.driven_teeth)
    diameter_difference = diameter_large - diameter_small
    approximate_length = (
        2.0 * data.center_distance_m
        + math.pi * (diameter_large + diameter_small) / 2.0
        + diameter_difference**2 / (4.0 * data.center_distance_m)
    )
    wrap_angle = math.pi - 2.0 * math.asin(diameter_difference / (2.0 * data.center_distance_m))
    engaged_teeth = teeth_small * wrap_angle / (2.0 * math.pi)

    steps = [
        FormulaStep(
            sequence=1,
            formula_id="BELT_KIN-001",
            expression="i = z2 / z1",
            variables={"z1": data.driver_teeth, "z2": data.driven_teeth},
            result_value=ratio,
            unit="",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=2,
            formula_id="BELT_KIN-002",
            expression="omega2 = omega1 / i",
            variables={"omega1": data.driver_angular_speed_rad_s, "i": ratio},
            result_value=driven_speed,
            unit="rad/s",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=3,
            formula_id="BELT_GEOM-001",
            expression="d1 = p * z1 / pi",
            variables={"p": data.belt_pitch_m, "z1": data.driver_teeth},
            result_value=driver_diameter,
            unit="m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=4,
            formula_id="BELT_GEOM-002",
            expression="d2 = p * z2 / pi",
            variables={"p": data.belt_pitch_m, "z2": data.driven_teeth},
            result_value=driven_diameter,
            unit="m",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=5,
            formula_id="BELT_KIN-003",
            expression="v = omega1 * d1 / 2",
            variables={"omega1": data.driver_angular_speed_rad_s, "d1": driver_diameter},
            result_value=belt_speed,
            unit="m/s",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=6,
            formula_id="BELT_POWER-001",
            expression="P_design = P_transmitted * K_service",
            variables={"P_transmitted": data.transmitted_power_w, "K_service": data.service_factor},
            result_value=design_power,
            unit="W",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=7,
            formula_id="BELT_FORCE-001",
            expression="F_effective = P_design / v",
            variables={"P_design": design_power, "v": belt_speed},
            result_value=effective_force,
            unit="N",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=8,
            formula_id="BELT_GEOM-003",
            expression="L_approx = 2*C + pi*(D+d)/2 + (D-d)^2/(4*C)",
            variables={
                "C": data.center_distance_m,
                "D": diameter_large,
                "d": diameter_small,
            },
            result_value=approximate_length,
            unit="m",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=9,
            formula_id="BELT_GEOM-004",
            expression="alpha_small = pi - 2*asin((D-d)/(2*C))",
            variables={
                "C": data.center_distance_m,
                "D": diameter_large,
                "d": diameter_small,
            },
            result_value=wrap_angle,
            unit="rad",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=10,
            formula_id="BELT_GEOM-005",
            expression="z_engaged = z_small * alpha_small / (2*pi)",
            variables={"z_small": teeth_small, "alpha_small": wrap_angle},
            result_value=engaged_teeth,
            unit="tooth",
            classification=ResultClassification.PRELIMINARY,
        ),
    ]

    warnings: list[WarningRecord] = [
        _warning(
            "BELT_LENGTH_APPROXIMATION",
            WarningSeverity.INFO,
            "带长为连续几何近似值",
            "当前开式带长公式未将结果离散到制造商标准节线长度，也未计算张紧行程。",
            ("approximate_open_belt_length_m",),
            "按候选制造商目录选择标准节线长度，并据此回算实际中心距和张紧范围。",
        )
    ]
    if data.basis_source_status is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            _warning(
                "BELT_BASIS_PENDING",
                WarningSeverity.WARNING,
                "计算依据待确认",
                "输入所声明的计算依据尚未确认，初选结果不得直接用于采购或制造。",
                ("design_power_w", "effective_circumferential_force_n"),
                "由项目工程师确认工况、使用系数及依据版本。",
            )
        )

    if data.manufacturer_allowable_effective_tension_n is None:
        allowable_tension_result = _scalar(
            None,
            "",
            ResultClassification.REVIEW_REQUIRED,
            "BELT_CHECK-001",
            "未提供制造商许用有效圆周力，无法完成承载校核。",
        )
        warnings.append(
            _warning(
                "BELT_ALLOWABLE_TENSION_MISSING",
                WarningSeverity.HIGH,
                "缺少候选带许用圆周力",
                "已计算有效圆周力，但没有可追溯的制造商许用值可供比较。",
                ("allowable_tension_pass",),
                "提供与带型、带宽和运行条件对应的制造商许用有效圆周力及数据版本。",
            )
        )
    else:
        tension_pass = effective_force <= data.manufacturer_allowable_effective_tension_n
        allowable_tension_result = _scalar(
            tension_pass,
            "",
            ResultClassification.PRELIMINARY,
            "BELT_CHECK-001",
        )
        steps.append(
            FormulaStep(
                sequence=len(steps) + 1,
                formula_id="BELT_CHECK-001",
                expression="pass_tension = F_effective <= F_allowable",
                variables={
                    "F_effective": effective_force,
                    "F_allowable": data.manufacturer_allowable_effective_tension_n,
                },
                result_value=tension_pass,
                unit="",
                classification=ResultClassification.PRELIMINARY,
            )
        )
        if not tension_pass:
            warnings.append(
                _warning(
                    "BELT_ALLOWABLE_TENSION_EXCEEDED",
                    WarningSeverity.BLOCKING,
                    "候选同步带承载不足",
                    "设计有效圆周力超过所提供的制造商许用有效圆周力。",
                    ("allowable_tension_pass",),
                    "增大带宽或更换带型，并使用同一制造商选型程序重新校核。",
                )
            )

    if data.manufacturer_max_belt_speed_m_s is None:
        maximum_speed_result = _scalar(
            None,
            "",
            ResultClassification.REVIEW_REQUIRED,
            "BELT_CHECK-002",
            "未提供制造商最大带速，无法完成速度校核。",
        )
        warnings.append(
            _warning(
                "BELT_MAX_SPEED_MISSING",
                WarningSeverity.HIGH,
                "缺少候选带最大带速",
                "当前带速尚未与制造商允许的最大带速比较。",
                ("maximum_speed_pass",),
                "提供候选带型对应的最大带速及制造商数据版本。",
            )
        )
    else:
        speed_pass = belt_speed <= data.manufacturer_max_belt_speed_m_s
        maximum_speed_result = _scalar(
            speed_pass,
            "",
            ResultClassification.PRELIMINARY,
            "BELT_CHECK-002",
        )
        steps.append(
            FormulaStep(
                sequence=len(steps) + 1,
                formula_id="BELT_CHECK-002",
                expression="pass_speed = v <= v_max",
                variables={"v": belt_speed, "v_max": data.manufacturer_max_belt_speed_m_s},
                result_value=speed_pass,
                unit="",
                classification=ResultClassification.PRELIMINARY,
            )
        )
        if not speed_pass:
            warnings.append(
                _warning(
                    "BELT_MAX_SPEED_EXCEEDED",
                    WarningSeverity.BLOCKING,
                    "候选同步带速度超限",
                    "计算带速超过所提供的制造商最大带速。",
                    ("maximum_speed_pass",),
                    "降低主动轮转速或重新选择带型和带轮参数。",
                )
            )

    if (
        data.candidate_data_source_status is not None
        and data.candidate_data_source_status is not SourceStatus.MANUFACTURER_DATA
    ):
        warnings.append(
            _warning(
                "BELT_CANDIDATE_SOURCE_UNCONFIRMED",
                WarningSeverity.WARNING,
                "候选带数据并非已确认制造商数据",
                "候选额定值可以进行算术比较，但其来源状态不足以形成产品放行结论。",
                ("allowable_tension_pass", "maximum_speed_pass"),
                "用可追溯的制造商样本或选型程序结果替换候选额定值。",
            )
        )

    assumptions = [
        AssumptionRecord(
            key="calculation_basis",
            value=data.basis_reference,
            source_status=data.basis_source_status,
            note="所有输入均由调用方以 SI 单位提供；模块不补入未声明的工程默认值。",
        ),
        AssumptionRecord(
            key="service_factor",
            value=data.service_factor,
            source_status=data.basis_source_status,
            note="使用系数仅在传递功率换算为设计功率时乘用一次。",
        ),
        AssumptionRecord(
            key="pitch_geometry",
            value="d=p*z/pi",
            source_status=SourceStatus.PROJECT_SETTING,
            note="节径按同步带节距与带轮齿数的运动学关系计算。",
        ),
        AssumptionRecord(
            key="open_belt_length_model",
            value="continuous_open_belt_approximation",
            source_status=SourceStatus.PROJECT_SETTING,
            note="按两轮开式带连续几何近似计算，结果不是制造商标准节线长度。",
        ),
    ]
    if data.candidate_reference is not None and data.candidate_data_source_status is not None:
        assumptions.append(
            AssumptionRecord(
                key="candidate_data",
                value=data.candidate_reference,
                source_status=data.candidate_data_source_status,
                note="候选许用圆周力和最大带速仅按用户声明的数据版本使用。",
            )
        )

    warning_tuple = tuple(warnings)
    status = CalculationStatus.COMPLETED_WITH_WARNINGS if warning_tuple else CalculationStatus.COMPLETED
    return SynchronousBeltResult(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        status=status,
        input_si=data,
        speed_ratio=_scalar(ratio, "", ResultClassification.CALCULATED, "BELT_KIN-001"),
        driven_angular_speed_rad_s=_scalar(
            driven_speed,
            "rad/s",
            ResultClassification.CALCULATED,
            "BELT_KIN-002",
        ),
        driver_pitch_diameter_m=_scalar(
            driver_diameter,
            "m",
            ResultClassification.CALCULATED,
            "BELT_GEOM-001",
        ),
        driven_pitch_diameter_m=_scalar(
            driven_diameter,
            "m",
            ResultClassification.CALCULATED,
            "BELT_GEOM-002",
        ),
        belt_speed_m_s=_scalar(
            belt_speed,
            "m/s",
            ResultClassification.CALCULATED,
            "BELT_KIN-003",
        ),
        design_power_w=_scalar(
            design_power,
            "W",
            ResultClassification.PRELIMINARY,
            "BELT_POWER-001",
        ),
        effective_circumferential_force_n=_scalar(
            effective_force,
            "N",
            ResultClassification.PRELIMINARY,
            "BELT_FORCE-001",
        ),
        approximate_open_belt_length_m=_scalar(
            approximate_length,
            "m",
            ResultClassification.PRELIMINARY,
            "BELT_GEOM-003",
        ),
        small_pulley_wrap_angle_rad=_scalar(
            wrap_angle,
            "rad",
            ResultClassification.PRELIMINARY,
            "BELT_GEOM-004",
        ),
        small_pulley_engaged_teeth=_scalar(
            engaged_teeth,
            "tooth",
            ResultClassification.PRELIMINARY,
            "BELT_GEOM-005",
        ),
        allowable_tension_pass=allowable_tension_result,
        maximum_speed_pass=maximum_speed_result,
        unchecked_items=(
            "belt_profile_compatibility",
            "catalog_pitch_length",
            "belt_width_and_tooth_capacity",
            "pretension_and_bearing_load",
            "fatigue_life",
            "environmental_derating",
        ),
        calculation_steps=tuple(steps),
        warnings=warning_tuple,
        assumptions=tuple(assumptions),
        disclaimer=DISCLAIMER,
    )


__all__ = ["calculate"]
