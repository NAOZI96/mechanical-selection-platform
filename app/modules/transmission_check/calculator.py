"""Side-effect-free transmission-chain calculations."""

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

from .schema import (
    TransmissionCheckInput,
    TransmissionCheckResult,
    TransmissionStageResult,
)

MODULE_ID = "transmission_check"
MODULE_NAME = "机械传动快速校核"
MODULE_VERSION = "1.0.0"
CALCULATION_MODEL_VERSION = "transmission_check.calc.1.0.0"
REPORT_TEMPLATE_VERSION = "transmission_check.report.1.0.1"

DISCLAIMER = (
    "本结果仅按用户给定的稳态输入转矩、转速、各级传动比与正向效率进行确定性传递计算。"
    "候选额定转矩比较不包含启动、冲击、载荷谱、疲劳、热平衡、反驱、制动、轴系与连接强度，"
    "不得替代适用标准校核、制造商确认和机械工程师签字。"
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
    value: float | int | bool | None,
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


def _warnings(data: TransmissionCheckInput, output_torque_nm: float) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = [
        WarningRecord(
            code="TRANSMISSION_SCOPE_LIMITED",
            severity=WarningSeverity.WARNING,
            title="当前仅完成稳态传递量校核",
            message="当前模型不计算齿轮、带、链、轴、联轴器强度，也不覆盖启动冲击、热平衡和载荷谱。",
            affected_result=("output_torque_nm", "candidate_torque_satisfied"),
            recommended_action="按实际传动型式补充强度、寿命、热容量、启动和异常工况专项校核。",
        )
    ]
    if data.basis_source_status is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            WarningRecord(
                code="BASIS_PENDING",
                severity=WarningSeverity.HIGH,
                title="计算依据仍待确认",
                message="本次计算依据被标记为待确认，结果只能作为数据整理和方案讨论。",
                affected_result=("total_ratio", "total_efficiency", "output_torque_nm"),
                recommended_action="补充已批准项目文件、适用标准条款或制造商数据版本后重新计算。",
            )
        )
    pending_stage_data = [
        stage.stage_name
        for stage in data.stages
        if SourceStatus.PENDING_CONFIRMATION in {stage.ratio_source_status, stage.efficiency_source_status}
    ]
    if pending_stage_data:
        warnings.append(
            WarningRecord(
                code="STAGE_DATA_PENDING",
                severity=WarningSeverity.HIGH,
                title="传动级参数来源待确认",
                message=f"以下传动级的传动比或效率来源待确认：{'、'.join(pending_stage_data)}。",
                affected_result=("total_ratio", "total_efficiency", "output_torque_nm"),
                recommended_action="逐级核对实际型号、齿数或制造商效率数据并更新来源状态。",
            )
        )
    if data.candidate_rated_output_torque_nm is None:
        warnings.append(
            WarningRecord(
                code="CANDIDATE_TORQUE_MISSING",
                severity=WarningSeverity.WARNING,
                title="未提供候选额定输出转矩",
                message="无法比较计算输出转矩与候选装置额定输出转矩。",
                affected_result=(
                    "candidate_torque_utilization",
                    "candidate_torque_margin_nm",
                    "candidate_torque_satisfied",
                ),
                recommended_action="提供候选型号、额定输出转矩、数据来源和版本后执行候选校核。",
            )
        )
    elif output_torque_nm > data.candidate_rated_output_torque_nm:
        warnings.append(
            WarningRecord(
                code="CANDIDATE_TORQUE_EXCEEDED",
                severity=WarningSeverity.HIGH,
                title="计算输出转矩超过候选额定值",
                message="稳态计算输出转矩已超过用户提供的候选额定输出转矩。",
                affected_result=("candidate_torque_utilization", "candidate_torque_satisfied"),
                recommended_action="更换候选装置或复核输入工况；仍须补充峰值、启动和载荷谱校核。",
            )
        )
    if data.candidate_source_status is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            WarningRecord(
                code="CANDIDATE_DATA_PENDING",
                severity=WarningSeverity.HIGH,
                title="候选额定值来源待确认",
                message="候选额定输出转矩已填写，但其来源状态仍为待确认。",
                affected_result=("candidate_torque_satisfied",),
                recommended_action="向制造商或项目批准人确认型号、额定值定义和样本版本。",
            )
        )
    return tuple(warnings)


def calculate(source: TransmissionCheckInput) -> TransmissionCheckResult:
    """Calculate one one-to-four-stage steady transmission chain."""

    data = source.to_si()
    recorder = _StepRecorder()
    recorder.add(
        "UNIT-001",
        "omega_in = input_speed_rpm * 2*pi/60",
        {"input_speed_rpm": source.input_speed_rpm},
        data.input_angular_speed_rad_s,
        "rad/s",
    )

    total_ratio = math.prod(stage.ratio for stage in data.stages)
    total_efficiency = math.prod(stage.efficiency for stage in data.stages)
    input_power_w = data.input_torque_nm * data.input_angular_speed_rad_s
    recorder.add(
        "KIN-001",
        "i_total = product(i_stage)",
        {f"i_{index}": stage.ratio for index, stage in enumerate(data.stages, start=1)},
        total_ratio,
        "",
    )
    recorder.add(
        "POWER-001",
        "eta_total = product(eta_stage)",
        {f"eta_{index}": stage.efficiency for index, stage in enumerate(data.stages, start=1)},
        total_efficiency,
        "",
    )
    recorder.add(
        "POWER-002",
        "P_in = T_in * omega_in",
        {"T_in": data.input_torque_nm, "omega_in": data.input_angular_speed_rad_s},
        input_power_w,
        "W",
    )

    stage_results: list[TransmissionStageResult] = []
    stage_speed = data.input_angular_speed_rad_s
    stage_torque = data.input_torque_nm
    for index, stage in enumerate(data.stages, start=1):
        input_speed = stage_speed
        input_torque = stage_torque
        stage_speed = input_speed / stage.ratio
        stage_torque = input_torque * stage.ratio * stage.efficiency
        stage_power = stage_speed * stage_torque
        recorder.add(
            f"KIN-{10 + index:03d}",
            "omega_out,j = omega_in,j / i_j",
            {"stage": index, "omega_in_j": input_speed, "i_j": stage.ratio},
            stage_speed,
            "rad/s",
        )
        recorder.add(
            f"TORQUE-{10 + index:03d}",
            "T_out,j = T_in,j * i_j * eta_j",
            {
                "stage": index,
                "T_in_j": input_torque,
                "i_j": stage.ratio,
                "eta_j": stage.efficiency,
            },
            stage_torque,
            "N*m",
        )
        recorder.add(
            f"POWER-{10 + index:03d}",
            "P_out,j = T_out,j * omega_out,j",
            {"stage": index, "T_out_j": stage_torque, "omega_out_j": stage_speed},
            stage_power,
            "W",
        )
        stage_results.append(
            TransmissionStageResult(
                stage_number=index,
                stage_name=stage.stage_name,
                input_angular_speed_rad_s=input_speed,
                output_angular_speed_rad_s=stage_speed,
                input_torque_nm=input_torque,
                output_torque_nm=stage_torque,
                output_power_w=stage_power,
            )
        )

    output_speed_rad_s = stage_speed
    output_torque_nm = stage_torque
    output_power_w = output_speed_rad_s * output_torque_nm
    candidate_rating = data.candidate_rated_output_torque_nm
    candidate_utilization = None if candidate_rating is None else output_torque_nm / candidate_rating
    candidate_margin = None if candidate_rating is None else candidate_rating - output_torque_nm
    candidate_satisfied = None if candidate_rating is None else output_torque_nm <= candidate_rating
    if candidate_rating is not None:
        recorder.add(
            "CHECK-001",
            "u_T = T_out / T_candidate,rated",
            {"T_out": output_torque_nm, "T_candidate_rated": candidate_rating},
            candidate_utilization,
            "",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "CHECK-002",
            "candidate_torque_satisfied = T_out <= T_candidate,rated",
            {"T_out": output_torque_nm, "T_candidate_rated": candidate_rating},
            candidate_satisfied,
            "",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "CHECK-003",
            "Delta_T = T_candidate,rated - T_out",
            {"T_out": output_torque_nm, "T_candidate_rated": candidate_rating},
            candidate_margin,
            "N*m",
            ResultClassification.PRELIMINARY,
        )

    warnings = _warnings(source, output_torque_nm)
    missing_candidate_reason = "未提供带来源的候选额定输出转矩，不能作候选转矩校核。"
    candidate_classification = (
        ResultClassification.REVIEW_REQUIRED if candidate_rating is None else ResultClassification.PRELIMINARY
    )
    assumptions: list[AssumptionRecord] = [
        AssumptionRecord(
            key="calculation_basis",
            value=source.basis_reference,
            source_status=source.basis_source_status,
            note="本次计算的总体输入、工况与数据版本依据。",
        ),
        AssumptionRecord(
            key="ratio_definition",
            value="i=n_in/n_out",
            source_status=SourceStatus.USER_INPUT,
            note="所有传动级均采用同一传动比方向定义。",
        ),
        AssumptionRecord(
            key="steady_power_flow",
            value=True,
            source_status=SourceStatus.USER_INPUT,
            note="只计算稳态正向功率流，不含启动、冲击、反驱和制动工况。",
        ),
    ]
    for index, stage in enumerate(source.stages, start=1):
        assumptions.extend(
            (
                AssumptionRecord(
                    key=f"stage_{index}_ratio",
                    value=stage.ratio,
                    source_status=stage.ratio_source_status,
                    note=f"{stage.stage_name}；依据：{stage.ratio_reference}",
                ),
                AssumptionRecord(
                    key=f"stage_{index}_efficiency",
                    value=stage.efficiency,
                    source_status=stage.efficiency_source_status,
                    note=f"{stage.stage_name}；依据：{stage.efficiency_reference}",
                ),
            )
        )

    return TransmissionCheckResult(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        status=calculation_status(warnings),
        input_si=data,
        total_ratio=_scalar(total_ratio, "", ResultClassification.CALCULATED, ("KIN-001",)),
        total_efficiency=_scalar(
            total_efficiency,
            "",
            ResultClassification.CALCULATED,
            ("POWER-001",),
        ),
        input_power_w=_scalar(input_power_w, "W", ResultClassification.CALCULATED, ("POWER-002",)),
        output_speed_rad_s=_scalar(
            output_speed_rad_s,
            "rad/s",
            ResultClassification.CALCULATED,
            tuple(f"KIN-{10 + index:03d}" for index in range(1, len(data.stages) + 1)),
        ),
        output_torque_nm=_scalar(
            output_torque_nm,
            "N*m",
            ResultClassification.CALCULATED,
            tuple(f"TORQUE-{10 + index:03d}" for index in range(1, len(data.stages) + 1)),
        ),
        output_power_w=_scalar(
            output_power_w,
            "W",
            ResultClassification.CALCULATED,
            tuple(f"POWER-{10 + index:03d}" for index in range(1, len(data.stages) + 1)),
        ),
        candidate_torque_utilization=_scalar(
            candidate_utilization,
            "",
            candidate_classification,
            ("CHECK-001",),
            missing_candidate_reason if candidate_rating is None else None,
        ),
        candidate_torque_margin_nm=_scalar(
            candidate_margin,
            "N*m",
            candidate_classification,
            ("CHECK-003",),
            missing_candidate_reason if candidate_rating is None else None,
        ),
        candidate_torque_satisfied=_scalar(
            candidate_satisfied,
            "",
            candidate_classification,
            ("CHECK-002",),
            missing_candidate_reason if candidate_rating is None else None,
        ),
        stage_results=tuple(stage_results),
        unchecked_items=(
            "dynamic_and_peak_torque",
            "load_spectrum_and_fatigue",
            "gear_belt_chain_strength",
            "shaft_coupling_key_strength",
            "bearing_life",
            "thermal_capacity_and_lubrication",
            "backdrive_and_braking",
            "torsional_vibration",
            "standard_clause_confirmation",
            "manufacturer_application_approval",
        ),
        calculation_steps=tuple(recorder.steps),
        warnings=warnings,
        assumptions=tuple(assumptions),
        disclaimer=DISCLAIMER,
    )
