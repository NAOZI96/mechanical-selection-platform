"""Strict DTOs for the deterministic transmission-chain worksheet."""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from app.modules.engineering_common import (
    EngineeringInputBase,
    EngineeringResultBase,
    Fraction,
    PositiveFloat,
    ScalarResult,
    SourceStatus,
)

ReferenceText = Annotated[StrictStr, Field(min_length=1, max_length=256)]
StageName = Annotated[StrictStr, Field(min_length=1, max_length=64)]


class TransmissionStageInput(BaseModel):
    """One explicitly sourced stage; ``ratio`` is defined as n_in / n_out."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    stage_name: StageName = Field(title="级名称")
    ratio: PositiveFloat = Field(title="该级传动比 i=n_in/n_out")
    efficiency: Fraction = Field(title="该级正向效率")
    ratio_source_status: SourceStatus = Field(title="传动比来源状态")
    ratio_reference: ReferenceText = Field(title="传动比依据")
    efficiency_source_status: SourceStatus = Field(title="效率来源状态")
    efficiency_reference: ReferenceText = Field(title="效率依据")

    @field_validator("stage_name", "ratio_reference", "efficiency_reference")
    @classmethod
    def strip_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("名称和来源依据不能为空")
        return normalized


class TransmissionCheckInput(EngineeringInputBase):
    """User-facing input for a one-to-four-stage steady transmission chain."""

    input_speed_rpm: PositiveFloat = Field(title="输入转速", description="传动链输入轴转速，r/min")
    input_torque_nm: PositiveFloat = Field(title="输入转矩", description="已按项目工况确定的输入轴转矩，N·m")
    stages: Annotated[tuple[TransmissionStageInput, ...], Field(min_length=1, max_length=4)] = Field(
        title="传动级",
        description="按动力流向填写 1～4 级；每级传动比定义为 n_in/n_out。",
    )
    candidate_rated_output_torque_nm: PositiveFloat | None = Field(
        default=None,
        title="候选装置额定输出转矩",
        description="可选制造商或已批准数据，N·m；不提供时不作候选合格结论。",
    )
    candidate_source_status: SourceStatus | None = Field(default=None, title="候选额定值来源状态")
    candidate_reference: ReferenceText | None = Field(default=None, title="候选型号及额定值依据")

    @field_validator("candidate_reference")
    @classmethod
    def strip_optional_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("候选型号及额定值依据不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_stage_and_candidate_contract(self) -> TransmissionCheckInput:
        stage_names = [stage.stage_name for stage in self.stages]
        if len(stage_names) != len(set(stage_names)):
            raise ValueError("传动级名称不得重复")

        candidate_parts = (
            self.candidate_rated_output_torque_nm,
            self.candidate_source_status,
            self.candidate_reference,
        )
        if any(value is not None for value in candidate_parts) and not all(
            value is not None for value in candidate_parts
        ):
            raise ValueError("候选额定输出转矩、来源状态和依据必须同时提供")

        try:
            total_ratio = math.prod(stage.ratio for stage in self.stages)
            total_efficiency = math.prod(stage.efficiency for stage in self.stages)
            input_angular_speed = self.input_speed_rpm * 2.0 * math.pi / 60.0
            if not all(
                math.isfinite(value) and value > 0 for value in (total_ratio, total_efficiency, input_angular_speed)
            ):
                raise ValueError("输入组合使传动比、效率或 SI 角速度失去有限正值")

            stage_speed = input_angular_speed
            stage_torque = self.input_torque_nm
            for stage in self.stages:
                stage_speed = stage_speed / stage.ratio
                stage_torque = stage_torque * stage.ratio * stage.efficiency
                stage_power = stage_speed * stage_torque
                if not all(math.isfinite(value) and value > 0 for value in (stage_speed, stage_torque, stage_power)):
                    raise ValueError("输入组合使逐级角速度、转矩或功率失去有限正值")
            if self.candidate_rated_output_torque_nm is not None:
                candidate_utilization = stage_torque / self.candidate_rated_output_torque_nm
                candidate_margin = self.candidate_rated_output_torque_nm - stage_torque
                if not all(math.isfinite(value) for value in (candidate_utilization, candidate_margin)):
                    raise ValueError("候选额定转矩组合导致利用率或余量超出有限数值范围")
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("输入组合导致传动链派生计算超出有限数值范围") from exc
        return self

    def to_si(self) -> TransmissionCheckSIInput:
        return TransmissionCheckSIInput(
            basis_source_status=self.basis_source_status,
            basis_reference=self.basis_reference,
            input_angular_speed_rad_s=self.input_speed_rpm * 2.0 * math.pi / 60.0,
            input_torque_nm=self.input_torque_nm,
            stages=tuple(
                TransmissionStageSI(
                    stage_name=stage.stage_name,
                    ratio=stage.ratio,
                    efficiency=stage.efficiency,
                    ratio_source_status=stage.ratio_source_status,
                    ratio_reference=stage.ratio_reference,
                    efficiency_source_status=stage.efficiency_source_status,
                    efficiency_reference=stage.efficiency_reference,
                )
                for stage in self.stages
            ),
            candidate_rated_output_torque_nm=self.candidate_rated_output_torque_nm,
            candidate_source_status=self.candidate_source_status,
            candidate_reference=self.candidate_reference,
        )


class TransmissionStageSI(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    stage_name: str
    ratio: float
    efficiency: float
    ratio_source_status: SourceStatus
    ratio_reference: str
    efficiency_source_status: SourceStatus
    efficiency_reference: str


class TransmissionCheckSIInput(BaseModel):
    """Immutable SI-normalized calculation input."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    basis_source_status: SourceStatus
    basis_reference: str
    input_angular_speed_rad_s: float
    input_torque_nm: float
    stages: tuple[TransmissionStageSI, ...]
    candidate_rated_output_torque_nm: float | None
    candidate_source_status: SourceStatus | None
    candidate_reference: str | None


class TransmissionStageResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    stage_number: int
    stage_name: str
    input_angular_speed_rad_s: float
    output_angular_speed_rad_s: float
    input_torque_nm: float
    output_torque_nm: float
    output_power_w: float


class TransmissionCheckResult(EngineeringResultBase[TransmissionCheckSIInput]):
    total_ratio: ScalarResult
    total_efficiency: ScalarResult
    input_power_w: ScalarResult
    output_speed_rad_s: ScalarResult
    output_torque_nm: ScalarResult
    output_power_w: ScalarResult
    candidate_torque_utilization: ScalarResult
    candidate_torque_margin_nm: ScalarResult
    candidate_torque_satisfied: ScalarResult
    stage_results: tuple[TransmissionStageResult, ...]


Input = TransmissionCheckInput
Result = TransmissionCheckResult

__all__ = [
    "Input",
    "Result",
    "TransmissionCheckInput",
    "TransmissionCheckResult",
    "TransmissionCheckSIInput",
    "TransmissionStageInput",
    "TransmissionStageResult",
    "TransmissionStageSI",
]
