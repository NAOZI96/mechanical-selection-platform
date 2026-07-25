"""Equivalent square-thread sliding lead-screw calculations."""

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

from .schema import LeadScrewInput, LeadScrewResult

MODULE_ID = "lead_screw"
MODULE_NAME = "丝杆传动选型"
MODULE_VERSION = "1.0.0"
CALCULATION_MODEL_VERSION = "lead_screw.calc.1.0.0"
REPORT_TEMPLATE_VERSION = "lead_screw.report.1.0.1"

DISCLAIMER = (
    "本结果采用等效方牙滑动丝杠、恒定螺纹摩擦和轴心静载模型；提升/下降转矩不含止推轴承或端面摩擦。"
    "Euler 临界载荷是理想弹性直杆理论值，未引入安全系数，也未验证细长比适用性、初弯曲、不对中、"
    "根部应力集中、螺纹/螺母强度、磨损、PV、热、疲劳或临界转速。结果不得直接作为产品放行依据。"
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


def _warning_records(
    source: LeadScrewInput,
    *,
    self_locking: bool,
    buckling_satisfied: bool,
) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = [
        WarningRecord(
            code="LEAD_SCREW_SCOPE_LIMITED",
            severity=WarningSeverity.HIGH,
            title="当前为等效方牙滑动丝杠模型",
            message="未计算止推轴承/端面摩擦、实际牙型修正、螺纹与螺母强度、磨损、PV、热、疲劳和临界转速。",
            affected_result=("raising_torque_nm", "raising_input_power_w", "euler_buckling_satisfied"),
            recommended_action="结合实际牙型、支承、材料、润滑、工作制和制造商数据完成专项校核。",
        ),
        WarningRecord(
            code="EULER_IDEAL_MODEL",
            severity=WarningSeverity.WARNING,
            title="Euler 校核为理想弹性柱模型",
            message="临界载荷未含安全系数，且未验证细长比、初弯曲、不对中和端部约束模型的适用性。",
            affected_result=("euler_critical_load_n", "buckling_utilization", "euler_buckling_satisfied"),
            recommended_action="确认端部约束和有效长度系数，补充细长比、缺陷、动态载荷及适用标准校核。",
        ),
    ]
    pending_inputs = [
        label
        for label, status in (
            ("摩擦系数", source.friction_source_status),
            ("弹性模量", source.youngs_modulus_source_status),
            ("有效长度系数", source.effective_length_factor_source_status),
        )
        if status is SourceStatus.PENDING_CONFIRMATION
    ]
    if source.basis_source_status is SourceStatus.PENDING_CONFIRMATION or pending_inputs:
        warnings.append(
            WarningRecord(
                code="SCREW_DATA_PENDING",
                severity=WarningSeverity.HIGH,
                title="丝杠关键参数来源待确认",
                message=(
                    "总体依据或以下参数来源仍待确认："
                    f"{'、'.join(pending_inputs) if pending_inputs else '总体计算依据'}。"
                ),
                affected_result=(
                    "raising_torque_nm",
                    "raising_efficiency",
                    "euler_critical_load_n",
                ),
                recommended_action="确认材料、润滑状态、摩擦试验/样本数据和实际端部约束。",
            )
        )
    if not self_locking:
        warnings.append(
            WarningRecord(
                code="NOT_SELF_LOCKING",
                severity=WarningSeverity.HIGH,
                title="等效螺纹模型不自锁",
                message="tan(导程角) 大于给定摩擦系数，下降转矩为负，载荷可能反驱丝杠。",
                affected_result=("lowering_torque_nm", "self_locking"),
                recommended_action="设置独立制动或防坠装置，并按实际摩擦范围和动态工况验证反驱风险。",
            )
        )
    if not buckling_satisfied:
        warnings.append(
            WarningRecord(
                code="EULER_CRITICAL_LOAD_EXCEEDED",
                severity=WarningSeverity.HIGH,
                title="轴向载荷超过 Euler 理论临界载荷",
                message="当前轴向载荷已超过理想弹性柱模型计算的临界载荷。",
                affected_result=("buckling_utilization", "euler_buckling_satisfied"),
                recommended_action="停止使用该几何方案，增大根径、缩短无支撑长度或调整支承，并完成详细稳定性设计。",
            )
        )
    if source.candidate_allowable_axial_load_n is None:
        warnings.append(
            WarningRecord(
                code="CANDIDATE_AXIAL_LOAD_MISSING",
                severity=WarningSeverity.WARNING,
                title="未提供候选产品许用轴向载荷",
                message="无法把轴向载荷与候选丝杠或螺母的制造商许用轴向载荷比较。",
                affected_result=(
                    "candidate_axial_load_utilization",
                    "candidate_axial_load_margin_n",
                    "candidate_axial_load_satisfied",
                ),
                recommended_action="提供完整候选型号、许用轴向载荷口径和制造商数据版本。",
            )
        )
    elif source.axial_force_n > source.candidate_allowable_axial_load_n:
        warnings.append(
            WarningRecord(
                code="CANDIDATE_AXIAL_LOAD_EXCEEDED",
                severity=WarningSeverity.HIGH,
                title="轴向载荷超过候选许用值",
                message="用户给定轴向载荷超过候选产品许用轴向载荷。",
                affected_result=("candidate_axial_load_utilization", "candidate_axial_load_satisfied"),
                recommended_action="更换候选或调整工况，并核对制造商许用值的寿命、速度和安装条件。",
            )
        )
    if source.candidate_source_status is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            WarningRecord(
                code="CANDIDATE_DATA_PENDING",
                severity=WarningSeverity.HIGH,
                title="候选许用载荷来源待确认",
                message="候选许用轴向载荷已填写，但来源状态仍为待确认。",
                affected_result=("candidate_axial_load_satisfied",),
                recommended_action="向制造商确认完整型号、样本修订版及额定值适用条件。",
            )
        )
    return tuple(warnings)


def calculate(source: LeadScrewInput) -> LeadScrewResult:
    """Calculate sliding-screw kinematics, torques, efficiency and Euler load."""

    data = source.to_si()
    recorder = _StepRecorder()
    recorder.add(
        "UNIT-001",
        "d_m = mean_thread_diameter_mm / 1000",
        {"mean_thread_diameter_mm": source.mean_thread_diameter_mm},
        data.mean_thread_diameter_m,
        "m",
    )
    recorder.add(
        "UNIT-002",
        "d_root = root_diameter_mm / 1000",
        {"root_diameter_mm": source.root_diameter_mm},
        data.root_diameter_m,
        "m",
    )
    recorder.add(
        "UNIT-003",
        "lead = lead_mm_per_revolution / 1000",
        {"lead_mm_per_revolution": source.lead_mm_per_revolution},
        data.lead_m_per_revolution,
        "m/rev",
    )
    recorder.add(
        "UNIT-004",
        "omega = rotational_speed_rpm * 2*pi/60",
        {"rotational_speed_rpm": source.rotational_speed_rpm},
        data.angular_speed_rad_s,
        "rad/s",
    )
    recorder.add(
        "UNIT-005",
        "E = youngs_modulus_gpa * 1e9",
        {"youngs_modulus_gpa": source.youngs_modulus_gpa},
        data.youngs_modulus_pa,
        "Pa",
    )
    recorder.add(
        "UNIT-006",
        "L = unsupported_length_mm / 1000",
        {"unsupported_length_mm": source.unsupported_length_mm},
        data.unsupported_length_m,
        "m",
    )

    tan_lead_angle = data.lead_m_per_revolution / (math.pi * data.mean_thread_diameter_m)
    lead_angle = math.atan(tan_lead_angle)
    raising_torque = (
        data.axial_force_n
        * data.mean_thread_diameter_m
        / 2.0
        * (tan_lead_angle + data.friction_coefficient)
        / (1.0 - data.friction_coefficient * tan_lead_angle)
    )
    lowering_torque = (
        data.axial_force_n
        * data.mean_thread_diameter_m
        / 2.0
        * (data.friction_coefficient - tan_lead_angle)
        / (1.0 + data.friction_coefficient * tan_lead_angle)
    )
    raising_efficiency = data.axial_force_n * data.lead_m_per_revolution / (2.0 * math.pi * raising_torque)
    linear_speed = data.lead_m_per_revolution * data.angular_speed_rad_s / (2.0 * math.pi)
    input_power = raising_torque * data.angular_speed_rad_s
    self_locking = data.friction_coefficient >= tan_lead_angle
    second_moment = math.pi * data.root_diameter_m**4 / 64.0
    effective_length = data.effective_length_factor * data.unsupported_length_m
    critical_load = math.pi**2 * data.youngs_modulus_pa * second_moment / effective_length**2
    buckling_utilization = data.axial_force_n / critical_load
    buckling_satisfied = data.axial_force_n <= critical_load

    recorder.add(
        "KIN-001",
        "lambda = atan(lead/(pi*d_m))",
        {"lead": data.lead_m_per_revolution, "d_m": data.mean_thread_diameter_m},
        lead_angle,
        "rad",
    )
    recorder.add(
        "TORQUE-001",
        "T_raise = F*d_m/2*(tan(lambda)+mu)/(1-mu*tan(lambda))",
        {
            "F": data.axial_force_n,
            "d_m": data.mean_thread_diameter_m,
            "tan_lambda": tan_lead_angle,
            "mu": data.friction_coefficient,
        },
        raising_torque,
        "N*m",
    )
    recorder.add(
        "TORQUE-002",
        "T_lower = F*d_m/2*(mu-tan(lambda))/(1+mu*tan(lambda))",
        {
            "F": data.axial_force_n,
            "d_m": data.mean_thread_diameter_m,
            "tan_lambda": tan_lead_angle,
            "mu": data.friction_coefficient,
        },
        lowering_torque,
        "N*m",
    )
    recorder.add(
        "POWER-001",
        "eta_raise = F*lead/(2*pi*T_raise)",
        {"F": data.axial_force_n, "lead": data.lead_m_per_revolution, "T_raise": raising_torque},
        raising_efficiency,
        "",
    )
    recorder.add(
        "KIN-002",
        "v = lead*omega/(2*pi)",
        {"lead": data.lead_m_per_revolution, "omega": data.angular_speed_rad_s},
        linear_speed,
        "m/s",
    )
    recorder.add(
        "POWER-002",
        "P_in,raise = T_raise*omega",
        {"T_raise": raising_torque, "omega": data.angular_speed_rad_s},
        input_power,
        "W",
    )
    recorder.add(
        "CHECK-001",
        "self_locking = mu >= tan(lambda)",
        {"mu": data.friction_coefficient, "tan_lambda": tan_lead_angle},
        self_locking,
        "",
    )
    recorder.add(
        "BUCKLING-001",
        "I_root = pi*d_root^4/64",
        {"d_root": data.root_diameter_m},
        second_moment,
        "m4",
        ResultClassification.PRELIMINARY,
    )
    recorder.add(
        "BUCKLING-002",
        "F_cr = pi^2*E*I_root/(K*L)^2",
        {
            "E": data.youngs_modulus_pa,
            "I_root": second_moment,
            "K": data.effective_length_factor,
            "L": data.unsupported_length_m,
        },
        critical_load,
        "N",
        ResultClassification.PRELIMINARY,
    )
    recorder.add(
        "CHECK-002",
        "u_buckling = F/F_cr",
        {"F": data.axial_force_n, "F_cr": critical_load},
        buckling_utilization,
        "",
        ResultClassification.PRELIMINARY,
    )
    recorder.add(
        "CHECK-003",
        "euler_buckling_satisfied = F <= F_cr",
        {"F": data.axial_force_n, "F_cr": critical_load},
        buckling_satisfied,
        "",
        ResultClassification.PRELIMINARY,
    )

    candidate_allowable = data.candidate_allowable_axial_load_n
    candidate_utilization = None if candidate_allowable is None else data.axial_force_n / candidate_allowable
    candidate_margin = None if candidate_allowable is None else candidate_allowable - data.axial_force_n
    candidate_satisfied = None if candidate_allowable is None else data.axial_force_n <= candidate_allowable
    if candidate_allowable is not None:
        recorder.add(
            "CHECK-004",
            "u_candidate = F/F_candidate,allow",
            {"F": data.axial_force_n, "F_candidate_allow": candidate_allowable},
            candidate_utilization,
            "",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "CHECK-005",
            "candidate_satisfied = F <= F_candidate,allow",
            {"F": data.axial_force_n, "F_candidate_allow": candidate_allowable},
            candidate_satisfied,
            "",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "CHECK-006",
            "Delta_F = F_candidate,allow - F",
            {"F": data.axial_force_n, "F_candidate_allow": candidate_allowable},
            candidate_margin,
            "N",
            ResultClassification.PRELIMINARY,
        )

    warnings = _warning_records(
        source,
        self_locking=self_locking,
        buckling_satisfied=buckling_satisfied,
    )
    missing_reason = "未提供带来源的候选产品许用轴向载荷，不能作候选承载校核。"
    candidate_classification = (
        ResultClassification.REVIEW_REQUIRED if candidate_allowable is None else ResultClassification.PRELIMINARY
    )
    assumptions = (
        AssumptionRecord(
            key="calculation_basis",
            value=source.basis_reference,
            source_status=source.basis_source_status,
            note="本次丝杠几何、载荷、速度和边界条件依据。",
        ),
        AssumptionRecord(
            key="equivalent_square_thread",
            value=True,
            source_status=SourceStatus.USER_INPUT,
            note="提升与下降转矩采用等效方牙滑动丝杠公式，不包含实际牙型角修正。",
        ),
        AssumptionRecord(
            key="thread_friction_coefficient",
            value=source.friction_coefficient,
            source_status=source.friction_source_status,
            note=f"螺纹摩擦依据：{source.friction_reference}；不含止推轴承或端面摩擦。",
        ),
        AssumptionRecord(
            key="youngs_modulus",
            value=source.youngs_modulus_gpa,
            unit="GPa",
            source_status=source.youngs_modulus_source_status,
            note=f"弹性模量依据：{source.youngs_modulus_reference}",
        ),
        AssumptionRecord(
            key="effective_length_factor",
            value=source.effective_length_factor,
            source_status=source.effective_length_factor_source_status,
            note=f"端部约束与有效长度系数依据：{source.effective_length_factor_reference}",
        ),
        AssumptionRecord(
            key="euler_centered_elastic_column",
            value=True,
            source_status=SourceStatus.USER_INPUT,
            note="Euler 公式假设轴心静压、理想直杆和线弹性；未计安全系数及初始缺陷。",
        ),
    )

    return LeadScrewResult(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        status=calculation_status(warnings),
        input_si=data,
        lead_angle_rad=_scalar(lead_angle, "rad", ResultClassification.CALCULATED, ("KIN-001",)),
        raising_torque_nm=_scalar(
            raising_torque,
            "N*m",
            ResultClassification.CALCULATED,
            ("TORQUE-001",),
        ),
        lowering_torque_nm=_scalar(
            lowering_torque,
            "N*m",
            ResultClassification.CALCULATED,
            ("TORQUE-002",),
        ),
        raising_efficiency=_scalar(
            raising_efficiency,
            "",
            ResultClassification.CALCULATED,
            ("POWER-001",),
        ),
        linear_speed_m_s=_scalar(
            linear_speed,
            "m/s",
            ResultClassification.CALCULATED,
            ("KIN-002",),
        ),
        raising_input_power_w=_scalar(
            input_power,
            "W",
            ResultClassification.CALCULATED,
            ("POWER-002",),
        ),
        self_locking=_scalar(
            self_locking,
            "",
            ResultClassification.CALCULATED,
            ("CHECK-001",),
        ),
        root_second_moment_area_m4=_scalar(
            second_moment,
            "m4",
            ResultClassification.PRELIMINARY,
            ("BUCKLING-001",),
        ),
        euler_critical_load_n=_scalar(
            critical_load,
            "N",
            ResultClassification.PRELIMINARY,
            ("BUCKLING-002",),
        ),
        buckling_utilization=_scalar(
            buckling_utilization,
            "",
            ResultClassification.PRELIMINARY,
            ("CHECK-002",),
        ),
        euler_buckling_satisfied=_scalar(
            buckling_satisfied,
            "",
            ResultClassification.PRELIMINARY,
            ("CHECK-003",),
        ),
        candidate_axial_load_utilization=_scalar(
            candidate_utilization,
            "",
            candidate_classification,
            ("CHECK-004",),
            missing_reason if candidate_allowable is None else None,
        ),
        candidate_axial_load_margin_n=_scalar(
            candidate_margin,
            "N",
            candidate_classification,
            ("CHECK-006",),
            missing_reason if candidate_allowable is None else None,
        ),
        candidate_axial_load_satisfied=_scalar(
            candidate_satisfied,
            "",
            candidate_classification,
            ("CHECK-005",),
            missing_reason if candidate_allowable is None else None,
        ),
        unchecked_items=(
            "actual_thread_form_correction",
            "collar_and_thrust_bearing_friction",
            "thread_and_nut_strength",
            "contact_pressure_and_wear",
            "pv_limit_lubrication_and_thermal",
            "fatigue_and_duty_cycle",
            "critical_speed_and_whirl",
            "euler_slenderness_and_initial_imperfection",
            "buckling_safety_factor_and_standard_clause",
            "mounting_alignment_and_lateral_load",
            "manufacturer_application_approval",
        ),
        calculation_steps=tuple(recorder.steps),
        warnings=warnings,
        assumptions=assumptions,
        disclaimer=DISCLAIMER,
    )
