"""Bearing basic rating life and solid circular shaft nominal stress."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.modules.engineering_common import (
    AssumptionRecord,
    FormulaStep,
    ResultClassification,
    ScalarResult,
    SourceStatus,
    WarningRecord,
    WarningSeverity,
    calculation_status,
)

from .schema import ShaftBearingInput, ShaftBearingResult

MODULE_ID = "shaft_bearing"
MODULE_NAME = "轴与轴承初选"
MODULE_VERSION = "1.0.0"
CALCULATION_MODEL_VERSION = "shaft_bearing.calc.1.0.0"
REPORT_TEMPLATE_VERSION = "shaft_bearing.report.1.0.0"

DISCLAIMER = (
    "轴承结果仅按用户指定的 X、Y、C、p 和恒定等效载荷计算基本额定 L10 寿命；"
    "轴结果仅为实心圆轴在给定截面弯矩与扭矩下的名义弹性应力。"
    "本模块不覆盖轴承静强度、可靠度修正、润滑污染、游隙配合、载荷谱，也不覆盖轴的疲劳、"
    "应力集中、键槽、挠度、临界转速、材料与表面状态，不能直接作为制造或放行依据。"
)


@dataclass
class _StepRecorder:
    steps: list[FormulaStep] = field(default_factory=list)

    def add(
        self,
        formula_id: str,
        expression: str,
        variables: dict[str, float | int | bool | str],
        result_value: float | int | bool,
        unit: str,
        classification: ResultClassification = ResultClassification.CALCULATED,
    ) -> None:
        self.steps.append(
            FormulaStep(
                sequence=len(self.steps) + 1,
                formula_id=formula_id,
                expression=expression,
                variables=variables,
                result_value=result_value,
                unit=unit,
                classification=classification,
            )
        )


def _scalar(
    value: float | bool | None,
    unit: str,
    classification: ResultClassification,
    formula_ids: tuple[str, ...],
    reason: str | None = None,
) -> ScalarResult:
    return ScalarResult(
        value=value,
        unit=unit,
        classification=classification,
        formula_ids=formula_ids,
        reason=reason,
    )


def _warnings(
    source: ShaftBearingInput,
    von_mises_stress_pa: float,
) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = [
        WarningRecord(
            code="BEARING_LIFE_SCOPE_LIMITED",
            severity=WarningSeverity.WARNING,
            title="轴承寿命为基本额定寿命",
            message="L10 仅使用用户给定 X、Y、C、p 和恒定等效载荷，不含可靠度、润滑、污染、游隙和载荷谱修正。",
            affected_result=("bearing_l10_million_revolutions", "bearing_l10_life_hours"),
            recommended_action="按实际轴承类型、工况和适用标准补充静强度、修正寿命及安装运行条件校核。",
        ),
        WarningRecord(
            code="SHAFT_NOMINAL_STRESS_ONLY",
            severity=WarningSeverity.HIGH,
            title="轴强度仅计算名义应力",
            message="实心圆轴公式未考虑键槽、台阶、圆角、过盈、疲劳、冲击、挠度和临界转速。",
            affected_result=("shaft_von_mises_stress_pa", "allowable_stress_satisfied"),
            recommended_action="根据实际轴系结构和载荷谱完成疲劳、应力集中、刚度、振动及材料专项校核。",
        ),
    ]
    pending_fields = [
        label
        for label, status in (
            ("C", source.dynamic_rating_source_status),
            ("X", source.radial_factor_x_source_status),
            ("Y", source.axial_factor_y_source_status),
            ("p", source.life_exponent_source_status),
        )
        if status is SourceStatus.PENDING_CONFIRMATION
    ]
    if source.basis_source_status is SourceStatus.PENDING_CONFIRMATION or pending_fields:
        warnings.append(
            WarningRecord(
                code="BEARING_DATA_PENDING",
                severity=WarningSeverity.HIGH,
                title="轴承参数来源待确认",
                message=(
                    "总体计算依据或以下轴承参数来源仍待确认："
                    f"{'、'.join(pending_fields) if pending_fields else '总体计算依据'}。"
                ),
                affected_result=(
                    "equivalent_dynamic_load_n",
                    "bearing_l10_million_revolutions",
                    "bearing_l10_life_hours",
                ),
                recommended_action="核对轴承完整型号、样本版本、载荷区间及 X、Y、C、p 选取条件。",
            )
        )
    if source.allowable_von_mises_stress_mpa is None:
        warnings.append(
            WarningRecord(
                code="ALLOWABLE_STRESS_MISSING",
                severity=WarningSeverity.WARNING,
                title="未提供候选许用应力",
                message="只能输出名义应力，不能判定候选轴材料或结构是否满足许用应力。",
                affected_result=(
                    "allowable_stress_utilization",
                    "allowable_stress_margin_pa",
                    "allowable_stress_satisfied",
                ),
                recommended_action="提供经批准的材料、工况许用应力及其标准或项目依据。",
            )
        )
    elif von_mises_stress_pa > source.allowable_von_mises_stress_mpa * 1.0e6:
        warnings.append(
            WarningRecord(
                code="ALLOWABLE_STRESS_EXCEEDED",
                severity=WarningSeverity.HIGH,
                title="名义 von Mises 应力超过许用值",
                message="当前名义组合应力已超过用户提供的许用应力。",
                affected_result=("allowable_stress_utilization", "allowable_stress_satisfied"),
                recommended_action="增大轴径或调整载荷，并基于实际几何和载荷谱完成详细轴强度设计。",
            )
        )
    if source.allowable_stress_source_status is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            WarningRecord(
                code="ALLOWABLE_STRESS_PENDING",
                severity=WarningSeverity.HIGH,
                title="许用应力来源待确认",
                message="已提供许用应力数值，但其来源状态仍为待确认。",
                affected_result=("allowable_stress_satisfied",),
                recommended_action="确认材料牌号、热处理、尺寸效应、工况与许用值口径。",
            )
        )
    return tuple(warnings)


def calculate(source: ShaftBearingInput) -> ShaftBearingResult:
    """Calculate basic bearing life and nominal solid-shaft stresses."""

    data = source.to_si()
    recorder = _StepRecorder()
    recorder.add(
        "UNIT-001",
        "omega = bearing_speed_rpm * 2*pi/60",
        {"bearing_speed_rpm": source.bearing_speed_rpm},
        data.bearing_angular_speed_rad_s,
        "rad/s",
    )
    recorder.add(
        "UNIT-002",
        "d = shaft_diameter_mm / 1000",
        {"shaft_diameter_mm": source.shaft_diameter_mm},
        data.shaft_diameter_m,
        "m",
    )
    if data.allowable_von_mises_stress_pa is not None:
        recorder.add(
            "UNIT-003",
            "sigma_allow = allowable_stress_mpa * 1e6",
            {"allowable_stress_mpa": source.allowable_von_mises_stress_mpa},
            data.allowable_von_mises_stress_pa,
            "Pa",
        )

    equivalent_load = (
        data.radial_factor_x * data.bearing_radial_load_n + data.axial_factor_y * data.bearing_axial_load_n
    )
    l10_million_revolutions = math.pow(
        data.basic_dynamic_load_rating_n / equivalent_load,
        data.life_exponent_p,
    )
    life_hours = l10_million_revolutions * 1.0e6 * 2.0 * math.pi / (data.bearing_angular_speed_rad_s * 3600.0)
    bending_stress = 32.0 * data.shaft_bending_moment_nm / (math.pi * data.shaft_diameter_m**3)
    torsional_stress = 16.0 * data.shaft_torque_nm / (math.pi * data.shaft_diameter_m**3)
    von_mises_stress = math.sqrt(bending_stress**2 + 3.0 * torsional_stress**2)

    recorder.add(
        "FORCE-001",
        "P = X*F_r + Y*F_a",
        {
            "X": data.radial_factor_x,
            "F_r": data.bearing_radial_load_n,
            "Y": data.axial_factor_y,
            "F_a": data.bearing_axial_load_n,
        },
        equivalent_load,
        "N",
    )
    recorder.add(
        "LIFE-001",
        "L_10 = (C/P)^p",
        {"C": data.basic_dynamic_load_rating_n, "P": equivalent_load, "p": data.life_exponent_p},
        l10_million_revolutions,
        "10^6 rev",
        ResultClassification.CALCULATED,
    )
    recorder.add(
        "LIFE-002",
        "L_10h = L_10*1e6/(60*n_rpm)",
        {
            "L_10": l10_million_revolutions,
            "n_rpm": source.bearing_speed_rpm,
        },
        life_hours,
        "h",
        ResultClassification.CALCULATED,
    )
    recorder.add(
        "STRESS-001",
        "sigma_b = 32*M/(pi*d^3)",
        {"M": data.shaft_bending_moment_nm, "d": data.shaft_diameter_m},
        bending_stress,
        "Pa",
    )
    recorder.add(
        "STRESS-002",
        "tau_t = 16*T/(pi*d^3)",
        {"T": data.shaft_torque_nm, "d": data.shaft_diameter_m},
        torsional_stress,
        "Pa",
    )
    recorder.add(
        "STRESS-003",
        "sigma_vm = sqrt(sigma_b^2 + 3*tau_t^2)",
        {"sigma_b": bending_stress, "tau_t": torsional_stress},
        von_mises_stress,
        "Pa",
    )

    allowable_stress = data.allowable_von_mises_stress_pa
    stress_utilization = None if allowable_stress is None else von_mises_stress / allowable_stress
    stress_margin = None if allowable_stress is None else allowable_stress - von_mises_stress
    stress_satisfied = None if allowable_stress is None else von_mises_stress <= allowable_stress
    if allowable_stress is not None:
        recorder.add(
            "CHECK-001",
            "u_sigma = sigma_vm/sigma_allow",
            {"sigma_vm": von_mises_stress, "sigma_allow": allowable_stress},
            stress_utilization,
            "",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "CHECK-002",
            "stress_satisfied = sigma_vm <= sigma_allow",
            {"sigma_vm": von_mises_stress, "sigma_allow": allowable_stress},
            stress_satisfied,
            "",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "CHECK-003",
            "Delta_sigma = sigma_allow - sigma_vm",
            {"sigma_vm": von_mises_stress, "sigma_allow": allowable_stress},
            stress_margin,
            "Pa",
            ResultClassification.PRELIMINARY,
        )

    warnings = _warnings(source, von_mises_stress)
    missing_reason = "未提供带来源的候选许用应力，只能输出名义应力，不能作强度通过结论。"
    check_classification = (
        ResultClassification.REVIEW_REQUIRED if allowable_stress is None else ResultClassification.PRELIMINARY
    )
    assumptions = (
        AssumptionRecord(
            key="calculation_basis",
            value=source.basis_reference,
            source_status=source.basis_source_status,
            note="本次轴承和轴截面工况依据。",
        ),
        AssumptionRecord(
            key="bearing_dynamic_rating_c",
            value=source.basic_dynamic_load_rating_n,
            unit="N",
            source_status=source.dynamic_rating_source_status,
            note=f"完整型号和额定动载荷依据：{source.dynamic_rating_reference}",
        ),
        AssumptionRecord(
            key="bearing_radial_factor_x",
            value=source.radial_factor_x,
            source_status=source.radial_factor_x_source_status,
            note=f"X 选取依据：{source.radial_factor_x_reference}",
        ),
        AssumptionRecord(
            key="bearing_axial_factor_y",
            value=source.axial_factor_y,
            source_status=source.axial_factor_y_source_status,
            note=f"Y 选取依据：{source.axial_factor_y_reference}",
        ),
        AssumptionRecord(
            key="bearing_life_exponent_p",
            value=source.life_exponent_p,
            source_status=source.life_exponent_source_status,
            note=f"p 选取依据：{source.life_exponent_reference}",
        ),
        AssumptionRecord(
            key="solid_circular_shaft_nominal_stress",
            value=True,
            source_status=SourceStatus.USER_INPUT,
            note="只采用无孔、无应力集中实心圆截面的名义弯扭应力公式。",
        ),
    )

    return ShaftBearingResult(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        status=calculation_status(warnings),
        input_si=data,
        equivalent_dynamic_load_n=_scalar(
            equivalent_load,
            "N",
            ResultClassification.CALCULATED,
            ("FORCE-001",),
        ),
        bearing_l10_million_revolutions=_scalar(
            l10_million_revolutions,
            "10^6 rev",
            ResultClassification.CALCULATED,
            ("LIFE-001",),
        ),
        bearing_l10_life_hours=_scalar(
            life_hours,
            "h",
            ResultClassification.CALCULATED,
            ("LIFE-002",),
        ),
        shaft_bending_stress_pa=_scalar(
            bending_stress,
            "Pa",
            ResultClassification.CALCULATED,
            ("STRESS-001",),
        ),
        shaft_torsional_shear_stress_pa=_scalar(
            torsional_stress,
            "Pa",
            ResultClassification.CALCULATED,
            ("STRESS-002",),
        ),
        shaft_von_mises_stress_pa=_scalar(
            von_mises_stress,
            "Pa",
            ResultClassification.CALCULATED,
            ("STRESS-003",),
        ),
        allowable_stress_utilization=_scalar(
            stress_utilization,
            "",
            check_classification,
            ("CHECK-001",),
            missing_reason if allowable_stress is None else None,
        ),
        allowable_stress_margin_pa=_scalar(
            stress_margin,
            "Pa",
            check_classification,
            ("CHECK-003",),
            missing_reason if allowable_stress is None else None,
        ),
        allowable_stress_satisfied=_scalar(
            stress_satisfied,
            "",
            check_classification,
            ("CHECK-002",),
            missing_reason if allowable_stress is None else None,
        ),
        unchecked_items=(
            "bearing_static_safety",
            "bearing_reliability_adjustment",
            "lubrication_contamination_and_temperature",
            "bearing_clearance_fit_and_misalignment",
            "variable_load_spectrum",
            "shaft_fatigue_and_stress_concentration",
            "keyway_step_fillet_and_fit",
            "shaft_deflection_and_alignment",
            "critical_speed_and_vibration",
            "material_surface_and_size_effects",
            "standard_clause_confirmation",
            "manufacturer_application_approval",
        ),
        calculation_steps=tuple(recorder.steps),
        warnings=warnings,
        assumptions=assumptions,
        disclaimer=DISCLAIMER,
    )
