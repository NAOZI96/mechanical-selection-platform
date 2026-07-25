"""Deterministic standard external spur-gear geometry and mesh-force formulas."""

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

from .schema import GearDriveInput, GearDriveResult

MODULE_ID = "gear_drive"
MODULE_NAME = "齿轮传动设计"
MODULE_VERSION = "1.0.0"
CALCULATION_MODEL_VERSION = "gear_drive.calc.1.0.0"
REPORT_TEMPLATE_VERSION = "gear_drive.report.1.0.0"

DISCLAIMER = (
    "本结果限于用户给定模数、齿数、压力角、输入工况和效率下的标准直齿外啮合基础几何与名义啮合力。"
    "本模块明确不执行齿根弯曲强度、齿面接触强度、胶合、磨损、寿命、材料、齿宽、精度、修形、"
    "润滑及热平衡设计；制造商限值比较也不等同于标准合格或采购放行。"
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
    source: GearDriveInput,
    tangential_force_n: float,
    pitch_line_speed_m_s: float,
) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = [
        WarningRecord(
            code="GEAR_STRENGTH_NOT_CHECKED",
            severity=WarningSeverity.HIGH,
            title="齿根和齿面强度未校核",
            message="当前结果只有标准直齿外啮合节圆几何和名义啮合力，不能据此判定齿轮承载能力。",
            affected_result=("tangential_force_n", "radial_force_n", "output_torque_nm"),
            recommended_action="按适用标准补充材料、齿宽、载荷系数、寿命、精度、润滑及齿根/齿面强度校核。",
        )
    ]
    if source.basis_source_status is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            WarningRecord(
                code="BASIS_PENDING",
                severity=WarningSeverity.HIGH,
                title="几何与工况依据待确认",
                message="总体计算依据被标记为待确认，所有结果仅供方案讨论。",
                affected_result=("pinion_pitch_diameter_m", "tangential_force_n", "output_torque_nm"),
                recommended_action="确认项目输入、适用标准和齿轮参数版本后重新计算。",
            )
        )
    if source.allowable_tangential_force_n is None:
        warnings.append(
            WarningRecord(
                code="ALLOWABLE_FORCE_MISSING",
                severity=WarningSeverity.WARNING,
                title="未提供制造商许用切向力",
                message="无法执行候选齿轮或减速机的许用切向力比较。",
                affected_result=("tangential_force_utilization", "tangential_force_satisfied"),
                recommended_action="提供候选型号、许用切向力、定义口径及制造商数据版本。",
            )
        )
    elif tangential_force_n > source.allowable_tangential_force_n:
        warnings.append(
            WarningRecord(
                code="ALLOWABLE_FORCE_EXCEEDED",
                severity=WarningSeverity.HIGH,
                title="名义切向力超过提供的许用值",
                message="按当前输入计算的名义节圆切向力超过用户提供的候选许用切向力。",
                affected_result=("tangential_force_utilization", "tangential_force_satisfied"),
                recommended_action="更换候选或调整输入；同时按适用标准执行完整强度校核。",
            )
        )
    if source.maximum_pitch_line_speed_m_s is None:
        warnings.append(
            WarningRecord(
                code="MAXIMUM_SPEED_MISSING",
                severity=WarningSeverity.WARNING,
                title="未提供制造商最大节线速度",
                message="无法执行候选齿轮的节线速度上限比较。",
                affected_result=("pitch_line_speed_utilization", "pitch_line_speed_satisfied"),
                recommended_action="提供候选型号的最大节线速度及制造商数据版本。",
            )
        )
    elif pitch_line_speed_m_s > source.maximum_pitch_line_speed_m_s:
        warnings.append(
            WarningRecord(
                code="MAXIMUM_SPEED_EXCEEDED",
                severity=WarningSeverity.HIGH,
                title="节线速度超过提供的最大值",
                message="计算节线速度超过用户提供的候选最大节线速度。",
                affected_result=("pitch_line_speed_utilization", "pitch_line_speed_satisfied"),
                recommended_action="降低转速、调整节圆直径或更换候选，并复核润滑与动载要求。",
            )
        )
    if SourceStatus.PENDING_CONFIRMATION in {
        source.allowable_tangential_force_source_status,
        source.maximum_pitch_line_speed_source_status,
    }:
        warnings.append(
            WarningRecord(
                code="MANUFACTURER_LIMIT_PENDING",
                severity=WarningSeverity.HIGH,
                title="候选限值来源待确认",
                message="至少一项候选制造商限值的来源状态仍为待确认。",
                affected_result=("tangential_force_satisfied", "pitch_line_speed_satisfied"),
                recommended_action="核对候选型号、样本修订版、工况适用范围和限值定义。",
            )
        )
    return tuple(warnings)


def calculate(source: GearDriveInput) -> GearDriveResult:
    """Calculate pitch geometry, nominal mesh forces and optional supplier checks."""

    data = source.to_si()
    recorder = _StepRecorder()
    recorder.add(
        "UNIT-001",
        "m = module_mm / 1000",
        {"module_mm": source.module_mm},
        data.module_m,
        "m",
    )
    recorder.add(
        "UNIT-002",
        "alpha = pressure_angle_deg * pi/180",
        {"pressure_angle_deg": source.pressure_angle_deg},
        data.pressure_angle_rad,
        "rad",
    )
    recorder.add(
        "UNIT-003",
        "omega_1 = input_speed_rpm * 2*pi/60",
        {"input_speed_rpm": source.input_speed_rpm},
        data.input_angular_speed_rad_s,
        "rad/s",
    )

    d1 = data.module_m * data.pinion_teeth
    d2 = data.module_m * data.gear_teeth
    center_distance = (d1 + d2) / 2.0
    ratio = data.gear_teeth / data.pinion_teeth
    tangential_force = 2.0 * data.input_torque_nm / d1
    radial_force = tangential_force * math.tan(data.pressure_angle_rad)
    pitch_line_speed = data.input_angular_speed_rad_s * d1 / 2.0
    output_speed = data.input_angular_speed_rad_s / ratio
    output_torque = data.input_torque_nm * ratio * data.mesh_efficiency
    output_power = output_speed * output_torque

    recorder.add("GEOM-001", "d_1 = m*z_1", {"m": data.module_m, "z_1": data.pinion_teeth}, d1, "m")
    recorder.add("GEOM-002", "d_2 = m*z_2", {"m": data.module_m, "z_2": data.gear_teeth}, d2, "m")
    recorder.add(
        "GEOM-003",
        "a = (d_1+d_2)/2",
        {"d_1": d1, "d_2": d2},
        center_distance,
        "m",
    )
    recorder.add(
        "KIN-001",
        "i = z_2/z_1",
        {"z_1": data.pinion_teeth, "z_2": data.gear_teeth},
        ratio,
        "",
    )
    recorder.add(
        "FORCE-001",
        "F_t = 2*T_1/d_1",
        {"T_1": data.input_torque_nm, "d_1": d1},
        tangential_force,
        "N",
    )
    recorder.add(
        "FORCE-002",
        "F_r = F_t*tan(alpha)",
        {"F_t": tangential_force, "alpha": data.pressure_angle_rad},
        radial_force,
        "N",
    )
    recorder.add(
        "KIN-002",
        "v = omega_1*d_1/2",
        {"omega_1": data.input_angular_speed_rad_s, "d_1": d1},
        pitch_line_speed,
        "m/s",
    )
    recorder.add(
        "KIN-003",
        "omega_2 = omega_1/i",
        {"omega_1": data.input_angular_speed_rad_s, "i": ratio},
        output_speed,
        "rad/s",
    )
    recorder.add(
        "TORQUE-001",
        "T_2 = T_1*i*eta_mesh",
        {"T_1": data.input_torque_nm, "i": ratio, "eta_mesh": data.mesh_efficiency},
        output_torque,
        "N*m",
    )
    recorder.add(
        "POWER-001",
        "P_2 = T_2*omega_2",
        {"T_2": output_torque, "omega_2": output_speed},
        output_power,
        "W",
    )

    allowable_force = data.allowable_tangential_force_n
    force_utilization = None if allowable_force is None else tangential_force / allowable_force
    force_satisfied = None if allowable_force is None else tangential_force <= allowable_force
    if allowable_force is not None:
        recorder.add(
            "CHECK-001",
            "u_F = F_t/F_t,allow",
            {"F_t": tangential_force, "F_t_allow": allowable_force},
            force_utilization,
            "",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "CHECK-002",
            "force_satisfied = F_t <= F_t,allow",
            {"F_t": tangential_force, "F_t_allow": allowable_force},
            force_satisfied,
            "",
            ResultClassification.PRELIMINARY,
        )

    maximum_speed = data.maximum_pitch_line_speed_m_s
    speed_utilization = None if maximum_speed is None else pitch_line_speed / maximum_speed
    speed_satisfied = None if maximum_speed is None else pitch_line_speed <= maximum_speed
    if maximum_speed is not None:
        recorder.add(
            "CHECK-003",
            "u_v = v/v_max",
            {"v": pitch_line_speed, "v_max": maximum_speed},
            speed_utilization,
            "",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "CHECK-004",
            "speed_satisfied = v <= v_max",
            {"v": pitch_line_speed, "v_max": maximum_speed},
            speed_satisfied,
            "",
            ResultClassification.PRELIMINARY,
        )

    warnings = _warning_records(source, tangential_force, pitch_line_speed)
    force_missing_reason = "未提供带来源的制造商许用切向力，不能执行候选载荷校核。"
    speed_missing_reason = "未提供带来源的制造商最大节线速度，不能执行候选速度校核。"
    force_classification = (
        ResultClassification.REVIEW_REQUIRED if allowable_force is None else ResultClassification.PRELIMINARY
    )
    speed_classification = (
        ResultClassification.REVIEW_REQUIRED if maximum_speed is None else ResultClassification.PRELIMINARY
    )
    assumptions = [
        AssumptionRecord(
            key="calculation_basis",
            value=source.basis_reference,
            source_status=source.basis_source_status,
            note="本次齿轮几何与输入工况依据。",
        ),
        AssumptionRecord(
            key="gear_mesh_type",
            value="standard_external_spur",
            source_status=SourceStatus.USER_INPUT,
            note="仅适用于标准直齿外啮合基础节圆关系；未使用变位、斜齿或内啮合公式。",
        ),
        AssumptionRecord(
            key="mesh_efficiency",
            value=source.mesh_efficiency,
            source_status=source.basis_source_status,
            note=f"效率由用户显式给定；总体依据：{source.basis_reference}",
        ),
    ]
    if allowable_force is not None:
        assumptions.append(
            AssumptionRecord(
                key="allowable_tangential_force",
                value=allowable_force,
                unit="N",
                source_status=source.allowable_tangential_force_source_status,
                note=f"候选许用值依据：{source.allowable_tangential_force_reference}",
            )
        )
    if maximum_speed is not None:
        assumptions.append(
            AssumptionRecord(
                key="maximum_pitch_line_speed",
                value=maximum_speed,
                unit="m/s",
                source_status=source.maximum_pitch_line_speed_source_status,
                note=f"候选速度限值依据：{source.maximum_pitch_line_speed_reference}",
            )
        )

    return GearDriveResult(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        status=calculation_status(warnings),
        input_si=data,
        pinion_pitch_diameter_m=_scalar(d1, "m", ResultClassification.CALCULATED, ("GEOM-001",)),
        gear_pitch_diameter_m=_scalar(d2, "m", ResultClassification.CALCULATED, ("GEOM-002",)),
        center_distance_m=_scalar(
            center_distance,
            "m",
            ResultClassification.CALCULATED,
            ("GEOM-003",),
        ),
        transmission_ratio=_scalar(ratio, "", ResultClassification.CALCULATED, ("KIN-001",)),
        tangential_force_n=_scalar(
            tangential_force,
            "N",
            ResultClassification.CALCULATED,
            ("FORCE-001",),
        ),
        radial_force_n=_scalar(
            radial_force,
            "N",
            ResultClassification.CALCULATED,
            ("FORCE-002",),
        ),
        pitch_line_speed_m_s=_scalar(
            pitch_line_speed,
            "m/s",
            ResultClassification.CALCULATED,
            ("KIN-002",),
        ),
        output_speed_rad_s=_scalar(
            output_speed,
            "rad/s",
            ResultClassification.CALCULATED,
            ("KIN-003",),
        ),
        output_torque_nm=_scalar(
            output_torque,
            "N*m",
            ResultClassification.CALCULATED,
            ("TORQUE-001",),
        ),
        output_power_w=_scalar(output_power, "W", ResultClassification.CALCULATED, ("POWER-001",)),
        tangential_force_utilization=_scalar(
            force_utilization,
            "",
            force_classification,
            ("CHECK-001",),
            force_missing_reason if allowable_force is None else None,
        ),
        tangential_force_satisfied=_scalar(
            force_satisfied,
            "",
            force_classification,
            ("CHECK-002",),
            force_missing_reason if allowable_force is None else None,
        ),
        pitch_line_speed_utilization=_scalar(
            speed_utilization,
            "",
            speed_classification,
            ("CHECK-003",),
            speed_missing_reason if maximum_speed is None else None,
        ),
        pitch_line_speed_satisfied=_scalar(
            speed_satisfied,
            "",
            speed_classification,
            ("CHECK-004",),
            speed_missing_reason if maximum_speed is None else None,
        ),
        unchecked_items=(
            "tooth_root_bending_strength",
            "tooth_contact_strength",
            "scuffing_pitting_and_wear",
            "materials_and_heat_treatment",
            "face_width_and_load_distribution",
            "dynamic_load_and_accuracy_grade",
            "profile_shift_backlash_and_modification",
            "lubrication_and_thermal_balance",
            "shaft_bearing_and_housing",
            "standard_clause_confirmation",
            "manufacturer_application_approval",
        ),
        calculation_steps=tuple(recorder.steps),
        warnings=warnings,
        assumptions=tuple(assumptions),
        disclaimer=DISCLAIMER,
    )
