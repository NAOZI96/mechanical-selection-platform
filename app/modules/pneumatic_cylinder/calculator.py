"""Deterministic force and ideal air-consumption calculations for a cylinder."""

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
from .schema import PneumaticCylinderInput, PneumaticCylinderResult


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


def calculate(data: PneumaticCylinderInput) -> PneumaticCylinderResult:
    """Calculate theoretical force and reference-state air volume for one full cycle."""

    if not isinstance(data, PneumaticCylinderInput):
        raise TypeError("pneumatic_cylinder calculate 需要 PneumaticCylinderInput")

    extension_area = math.pi * data.bore_diameter_m**2 / 4.0
    retraction_area = math.pi * (data.bore_diameter_m**2 - data.rod_diameter_m**2) / 4.0
    pressure_difference = data.cylinder_supply_absolute_pressure_pa - data.ambient_absolute_pressure_pa
    extension_force = pressure_difference * extension_area
    retraction_force = pressure_difference * retraction_area
    required_extension_force = data.extension_load_force_n * data.load_safety_factor
    required_retraction_force = data.retraction_load_force_n * data.load_safety_factor
    extension_margin = extension_force - required_extension_force
    retraction_margin = retraction_force - required_retraction_force
    extension_pass = extension_margin >= 0.0
    retraction_pass = retraction_margin >= 0.0

    extension_volume = extension_area * data.stroke_m
    retraction_volume = retraction_area * data.stroke_m
    chamber_volume_per_cycle = extension_volume + retraction_volume
    reference_volume_per_cycle = (
        chamber_volume_per_cycle * data.cylinder_supply_absolute_pressure_pa / data.reference_absolute_pressure_pa
    )
    reference_consumption_per_minute = reference_volume_per_cycle * data.cycle_frequency_hz * 60.0

    steps = [
        FormulaStep(
            sequence=1,
            formula_id="CYL_GEOM-001",
            expression="A_extension = pi * D^2 / 4",
            variables={"D": data.bore_diameter_m},
            result_value=extension_area,
            unit="m^2",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=2,
            formula_id="CYL_GEOM-002",
            expression="A_retraction = pi * (D^2-d_rod^2) / 4",
            variables={"D": data.bore_diameter_m, "d_rod": data.rod_diameter_m},
            result_value=retraction_area,
            unit="m^2",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=3,
            formula_id="CYL_PRESSURE-001",
            expression="delta_p = p_supply_absolute - p_ambient_absolute",
            variables={
                "p_supply_absolute": data.cylinder_supply_absolute_pressure_pa,
                "p_ambient_absolute": data.ambient_absolute_pressure_pa,
            },
            result_value=pressure_difference,
            unit="Pa",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=4,
            formula_id="CYL_FORCE-001",
            expression="F_extension = delta_p * A_extension",
            variables={"delta_p": pressure_difference, "A_extension": extension_area},
            result_value=extension_force,
            unit="N",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=5,
            formula_id="CYL_FORCE-002",
            expression="F_retraction = delta_p * A_retraction",
            variables={"delta_p": pressure_difference, "A_retraction": retraction_area},
            result_value=retraction_force,
            unit="N",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=6,
            formula_id="CYL_FORCE-003",
            expression="F_extension_required = F_load_extension * K_safety",
            variables={
                "F_load_extension": data.extension_load_force_n,
                "K_safety": data.load_safety_factor,
            },
            result_value=required_extension_force,
            unit="N",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=7,
            formula_id="CYL_FORCE-004",
            expression="F_retraction_required = F_load_retraction * K_safety",
            variables={
                "F_load_retraction": data.retraction_load_force_n,
                "K_safety": data.load_safety_factor,
            },
            result_value=required_retraction_force,
            unit="N",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=8,
            formula_id="CYL_FORCE-005",
            expression="margin_extension = F_extension - F_extension_required",
            variables={
                "F_extension": extension_force,
                "F_extension_required": required_extension_force,
            },
            result_value=extension_margin,
            unit="N",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=9,
            formula_id="CYL_FORCE-006",
            expression="margin_retraction = F_retraction - F_retraction_required",
            variables={
                "F_retraction": retraction_force,
                "F_retraction_required": required_retraction_force,
            },
            result_value=retraction_margin,
            unit="N",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=10,
            formula_id="CYL_CHECK-001",
            expression="pass_extension = margin_extension >= 0",
            variables={"margin_extension": extension_margin},
            result_value=extension_pass,
            unit="",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=11,
            formula_id="CYL_CHECK-002",
            expression="pass_retraction = margin_retraction >= 0",
            variables={"margin_retraction": retraction_margin},
            result_value=retraction_pass,
            unit="",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=12,
            formula_id="CYL_AIR-001",
            expression="V_extension = A_extension * stroke",
            variables={"A_extension": extension_area, "stroke": data.stroke_m},
            result_value=extension_volume,
            unit="m^3",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=13,
            formula_id="CYL_AIR-002",
            expression="V_retraction = A_retraction * stroke",
            variables={"A_retraction": retraction_area, "stroke": data.stroke_m},
            result_value=retraction_volume,
            unit="m^3",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=14,
            formula_id="CYL_AIR-003",
            expression="V_cycle = V_extension + V_retraction",
            variables={
                "V_extension": extension_volume,
                "V_retraction": retraction_volume,
            },
            result_value=chamber_volume_per_cycle,
            unit="m^3",
            classification=ResultClassification.CALCULATED,
        ),
        FormulaStep(
            sequence=15,
            formula_id="CYL_AIR-004",
            expression="V_reference = V_cycle * p_supply_absolute / p_reference_absolute",
            variables={
                "V_cycle": chamber_volume_per_cycle,
                "p_supply_absolute": data.cylinder_supply_absolute_pressure_pa,
                "p_reference_absolute": data.reference_absolute_pressure_pa,
            },
            result_value=reference_volume_per_cycle,
            unit="m^3",
            classification=ResultClassification.PRELIMINARY,
        ),
        FormulaStep(
            sequence=16,
            formula_id="CYL_AIR-005",
            expression="Q_reference_per_min = V_reference * frequency_hz * 60",
            variables={
                "V_reference": reference_volume_per_cycle,
                "frequency_hz": data.cycle_frequency_hz,
            },
            result_value=reference_consumption_per_minute,
            unit="m^3/min",
            classification=ResultClassification.PRELIMINARY,
        ),
    ]

    warnings: list[WarningRecord] = [
        _warning(
            "CYL_PRESSURE_DROP_EXCLUDED",
            WarningSeverity.HIGH,
            "管路和阀压降未计算",
            "理论力直接使用用户给定的气缸接口供气绝压与环境绝压之差，不推定管路、接头或阀的压降。",
            ("theoretical_extension_force_n", "theoretical_retraction_force_n"),
            "用最不利动态工况下实测或经气路计算得到的气缸接口压力作为输入。",
        ),
        _warning(
            "CYL_AIR_IDEAL_MODEL",
            WarningSeverity.WARNING,
            "耗气量采用理想等温折算",
            "参考体积仅含两腔扫掠体积，不含死腔、管内容积、泄漏、温度差和吹气等附加耗气。",
            ("reference_air_consumption_m3_per_min",),
            "按实际阀岛、管路、温度、泄漏等级和辅助用气补充系统耗气预算。",
        ),
    ]
    if data.basis_source_status is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            _warning(
                "CYL_BASIS_PENDING",
                WarningSeverity.WARNING,
                "计算依据待确认",
                "负载、压力或安全系数的来源状态尚未确认。",
                ("extension_force_margin_n", "retraction_force_margin_n"),
                "由气动与机械工程师确认最不利负载、动态接口压力和安全系数。",
            )
        )
    if not extension_pass:
        warnings.append(
            _warning(
                "CYL_EXTENSION_FORCE_FAILED",
                WarningSeverity.BLOCKING,
                "伸出力不足",
                "理论伸出力小于计入安全系数后的伸出负载需求。",
                ("extension_force_pass", "extension_force_margin_n"),
                "增大缸径、提高经批准的接口压力或降低负载，并重新校核。",
            )
        )
    if not retraction_pass:
        warnings.append(
            _warning(
                "CYL_RETRACTION_FORCE_FAILED",
                WarningSeverity.BLOCKING,
                "缩回力不足",
                "理论缩回力小于计入安全系数后的缩回负载需求。",
                ("retraction_force_pass", "retraction_force_margin_n"),
                "增大缸径、减小杆径或降低负载，并重新校核。",
            )
        )

    if data.candidate_max_supply_absolute_pressure_pa is None:
        pressure_rating_result = _scalar(
            None,
            "",
            ResultClassification.REVIEW_REQUIRED,
            "CYL_CHECK-003",
            "未提供候选气缸最大允许供气绝压，无法完成压力额定校核。",
        )
        warnings.append(
            _warning(
                "CYL_PRESSURE_RATING_MISSING",
                WarningSeverity.HIGH,
                "缺少候选气缸压力额定值",
                "输入供气绝压尚未与候选气缸制造商额定值比较。",
                ("candidate_pressure_rating_pass",),
                "提供候选气缸最大允许供气绝压、样本版本和适用温度条件。",
            )
        )
    else:
        pressure_rating_pass = (
            data.cylinder_supply_absolute_pressure_pa <= data.candidate_max_supply_absolute_pressure_pa
        )
        pressure_rating_result = _scalar(
            pressure_rating_pass,
            "",
            ResultClassification.PRELIMINARY,
            "CYL_CHECK-003",
        )
        steps.append(
            FormulaStep(
                sequence=len(steps) + 1,
                formula_id="CYL_CHECK-003",
                expression="pass_pressure = p_supply_absolute <= p_candidate_max",
                variables={
                    "p_supply_absolute": data.cylinder_supply_absolute_pressure_pa,
                    "p_candidate_max": data.candidate_max_supply_absolute_pressure_pa,
                },
                result_value=pressure_rating_pass,
                unit="",
                classification=ResultClassification.PRELIMINARY,
            )
        )
        if not pressure_rating_pass:
            warnings.append(
                _warning(
                    "CYL_PRESSURE_RATING_FAILED",
                    WarningSeverity.BLOCKING,
                    "候选气缸压力额定值不足",
                    "输入的气缸接口供气绝压超过候选气缸最大允许值。",
                    ("candidate_pressure_rating_pass",),
                    "降低供气压力或选择额定压力更高的气缸和附件。",
                )
            )
        if data.candidate_data_source_status is not SourceStatus.MANUFACTURER_DATA:
            warnings.append(
                _warning(
                    "CYL_CANDIDATE_SOURCE_UNCONFIRMED",
                    WarningSeverity.WARNING,
                    "候选压力数据并非已确认制造商数据",
                    "压力额定比较可用于排查，但不能形成产品放行结论。",
                    ("candidate_pressure_rating_pass",),
                    "用候选型号制造商样本中的压力额定值及温度降额替换当前数据。",
                )
            )

    assumptions = [
        AssumptionRecord(
            key="calculation_basis",
            value=data.basis_reference,
            source_status=data.basis_source_status,
            note="直径、行程、绝对压力、负载和循环频率均由调用方以 SI 单位提供。",
        ),
        AssumptionRecord(
            key="single_rod_double_acting",
            value=True,
            source_status=SourceStatus.PROJECT_SETTING,
            note="伸出采用全活塞面积，缩回采用扣除活塞杆后的环形面积。",
        ),
        AssumptionRecord(
            key="cylinder_port_pressure",
            value=data.cylinder_supply_absolute_pressure_pa,
            unit="Pa",
            source_status=data.basis_source_status,
            note="输入应是气缸接口处绝对压力；模块不从上游供气压力估算管路和阀压降。",
        ),
        AssumptionRecord(
            key="load_safety_factor",
            value=data.load_safety_factor,
            source_status=data.basis_source_status,
            note="安全系数仅在负载需求力上乘用一次，不在理论气缸力上重复叠加。",
        ),
        AssumptionRecord(
            key="full_cycle",
            value="one_extension_plus_one_retraction",
            source_status=SourceStatus.PROJECT_SETTING,
            note="一个完整循环包含一次全行程伸出和一次全行程缩回。",
        ),
        AssumptionRecord(
            key="ideal_reference_volume",
            value="V_ref=V_cycle*p_supply_abs/p_ref_abs",
            source_status=SourceStatus.PROJECT_SETTING,
            note="按同温理想气体质量等价折算，不含死腔、泄漏、温差和附加用气。",
        ),
    ]
    if data.candidate_reference is not None and data.candidate_data_source_status is not None:
        assumptions.append(
            AssumptionRecord(
                key="candidate_data",
                value=data.candidate_reference,
                source_status=data.candidate_data_source_status,
                note="候选最大供气绝压仅按用户声明的数据版本使用。",
            )
        )

    warning_tuple = tuple(warnings)
    return PneumaticCylinderResult(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        status=(CalculationStatus.COMPLETED_WITH_WARNINGS if warning_tuple else CalculationStatus.COMPLETED),
        input_si=data,
        extension_effective_area_m2=_scalar(
            extension_area,
            "m^2",
            ResultClassification.CALCULATED,
            "CYL_GEOM-001",
        ),
        retraction_effective_area_m2=_scalar(
            retraction_area,
            "m^2",
            ResultClassification.CALCULATED,
            "CYL_GEOM-002",
        ),
        pressure_differential_pa=_scalar(
            pressure_difference,
            "Pa",
            ResultClassification.CALCULATED,
            "CYL_PRESSURE-001",
        ),
        theoretical_extension_force_n=_scalar(
            extension_force,
            "N",
            ResultClassification.PRELIMINARY,
            "CYL_FORCE-001",
        ),
        theoretical_retraction_force_n=_scalar(
            retraction_force,
            "N",
            ResultClassification.PRELIMINARY,
            "CYL_FORCE-002",
        ),
        required_extension_force_n=_scalar(
            required_extension_force,
            "N",
            ResultClassification.PRELIMINARY,
            "CYL_FORCE-003",
        ),
        required_retraction_force_n=_scalar(
            required_retraction_force,
            "N",
            ResultClassification.PRELIMINARY,
            "CYL_FORCE-004",
        ),
        extension_force_margin_n=_scalar(
            extension_margin,
            "N",
            ResultClassification.PRELIMINARY,
            "CYL_FORCE-005",
        ),
        retraction_force_margin_n=_scalar(
            retraction_margin,
            "N",
            ResultClassification.PRELIMINARY,
            "CYL_FORCE-006",
        ),
        extension_force_pass=_scalar(
            extension_pass,
            "",
            ResultClassification.PRELIMINARY,
            "CYL_CHECK-001",
        ),
        retraction_force_pass=_scalar(
            retraction_pass,
            "",
            ResultClassification.PRELIMINARY,
            "CYL_CHECK-002",
        ),
        extension_chamber_volume_m3=_scalar(
            extension_volume,
            "m^3",
            ResultClassification.CALCULATED,
            "CYL_AIR-001",
        ),
        retraction_chamber_volume_m3=_scalar(
            retraction_volume,
            "m^3",
            ResultClassification.CALCULATED,
            "CYL_AIR-002",
        ),
        chamber_volume_per_cycle_m3=_scalar(
            chamber_volume_per_cycle,
            "m^3",
            ResultClassification.CALCULATED,
            "CYL_AIR-003",
        ),
        reference_air_volume_per_cycle_m3=_scalar(
            reference_volume_per_cycle,
            "m^3",
            ResultClassification.PRELIMINARY,
            "CYL_AIR-004",
        ),
        reference_air_consumption_m3_per_min=_scalar(
            reference_consumption_per_minute,
            "m^3/min",
            ResultClassification.PRELIMINARY,
            "CYL_AIR-005",
        ),
        candidate_pressure_rating_pass=pressure_rating_result,
        unchecked_items=(
            "pipe_and_valve_pressure_drop",
            "dynamic_back_pressure",
            "flow_speed_and_cycle_time",
            "dead_volume_leakage_temperature",
            "cushioning_and_impact",
            "rod_buckling_and_mounting",
            "materials_environment_standards",
        ),
        calculation_steps=tuple(steps),
        warnings=warning_tuple,
        assumptions=tuple(assumptions),
        disclaimer=DISCLAIMER,
    )


__all__ = ["calculate"]
