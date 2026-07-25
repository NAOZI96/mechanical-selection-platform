"""Strict DTOs for standard external spur-gear geometry and mesh forces."""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictStr, field_validator, model_validator

from app.modules.engineering_common import (
    EngineeringInputBase,
    EngineeringResultBase,
    Fraction,
    PositiveFloat,
    PositiveInt,
    ScalarResult,
    SourceStatus,
)

ReferenceText = Annotated[StrictStr, Field(min_length=1, max_length=256)]
PressureAngleDegrees = Annotated[StrictFloat, Field(gt=0, lt=90)]


class GearDriveInput(EngineeringInputBase):
    """User-facing dimensions use mm, degrees and r/min and are normalized to SI."""

    module_mm: PositiveFloat = Field(title="模数", description="标准直齿圆柱齿轮端面模数，mm")
    pinion_teeth: PositiveInt = Field(title="小齿轮齿数")
    gear_teeth: PositiveInt = Field(title="大齿轮齿数")
    pressure_angle_deg: PressureAngleDegrees = Field(title="压力角", description="端面压力角，deg")
    input_speed_rpm: PositiveFloat = Field(title="小齿轮转速", description="r/min")
    input_torque_nm: PositiveFloat = Field(title="小齿轮输入转矩", description="N·m")
    mesh_efficiency: Fraction = Field(title="单级啮合正向效率")

    allowable_tangential_force_n: PositiveFloat | None = Field(
        default=None,
        title="制造商许用切向力",
        description="可选候选产品或已批准设计许用值，N。",
    )
    allowable_tangential_force_source_status: SourceStatus | None = Field(
        default=None,
        title="许用切向力来源状态",
    )
    allowable_tangential_force_reference: ReferenceText | None = Field(
        default=None,
        title="许用切向力依据",
    )
    maximum_pitch_line_speed_m_s: PositiveFloat | None = Field(
        default=None,
        title="制造商最大节线速度",
        description="可选候选产品最大节线速度，m/s。",
    )
    maximum_pitch_line_speed_source_status: SourceStatus | None = Field(
        default=None,
        title="最大节线速度来源状态",
    )
    maximum_pitch_line_speed_reference: ReferenceText | None = Field(
        default=None,
        title="最大节线速度依据",
    )

    @field_validator(
        "allowable_tangential_force_reference",
        "maximum_pitch_line_speed_reference",
    )
    @classmethod
    def strip_optional_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("制造商校核依据不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_optional_checks_and_range(self) -> GearDriveInput:
        tangential_parts = (
            self.allowable_tangential_force_n,
            self.allowable_tangential_force_source_status,
            self.allowable_tangential_force_reference,
        )
        if any(value is not None for value in tangential_parts) and not all(
            value is not None for value in tangential_parts
        ):
            raise ValueError("许用切向力、来源状态和依据必须同时提供")

        speed_parts = (
            self.maximum_pitch_line_speed_m_s,
            self.maximum_pitch_line_speed_source_status,
            self.maximum_pitch_line_speed_reference,
        )
        if any(value is not None for value in speed_parts) and not all(value is not None for value in speed_parts):
            raise ValueError("最大节线速度、来源状态和依据必须同时提供")

        try:
            module_m = self.module_mm / 1000.0
            pressure_angle_rad = math.radians(self.pressure_angle_deg)
            omega = self.input_speed_rpm * 2.0 * math.pi / 60.0
            d1 = module_m * self.pinion_teeth
            d2 = module_m * self.gear_teeth
            if not all(math.isfinite(value) and value > 0 for value in (module_m, pressure_angle_rad, omega, d1, d2)):
                raise ValueError("输入尺寸、压力角和转速在 SI 换算后必须保持有限正值")

            center_distance = (d1 + d2) / 2.0
            ratio = self.gear_teeth / self.pinion_teeth
            ft = 2.0 * self.input_torque_nm / d1
            radial_force = ft * math.tan(pressure_angle_rad)
            pitch_line_speed = omega * d1 / 2.0
            output_speed = omega / ratio
            output_torque = self.input_torque_nm * ratio * self.mesh_efficiency
            output_power = output_speed * output_torque
            required_positive = (
                center_distance,
                ratio,
                ft,
                radial_force,
                pitch_line_speed,
                output_speed,
                output_torque,
                output_power,
            )
            if not all(math.isfinite(value) and value > 0 for value in required_positive):
                raise ValueError("输入组合使齿轮几何、载荷、速度、转矩或功率失去有限正值")

            if self.allowable_tangential_force_n is not None:
                force_utilization = ft / self.allowable_tangential_force_n
                if not math.isfinite(force_utilization):
                    raise ValueError("许用切向力组合导致利用率超出有限数值范围")
            if self.maximum_pitch_line_speed_m_s is not None:
                speed_utilization = pitch_line_speed / self.maximum_pitch_line_speed_m_s
                if not math.isfinite(speed_utilization):
                    raise ValueError("最大节线速度组合导致利用率超出有限数值范围")
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("输入组合导致齿轮派生计算超出有限数值范围") from exc
        return self

    def to_si(self) -> GearDriveSIInput:
        return GearDriveSIInput(
            basis_source_status=self.basis_source_status,
            basis_reference=self.basis_reference,
            module_m=self.module_mm / 1000.0,
            pinion_teeth=self.pinion_teeth,
            gear_teeth=self.gear_teeth,
            pressure_angle_rad=math.radians(self.pressure_angle_deg),
            input_angular_speed_rad_s=self.input_speed_rpm * 2.0 * math.pi / 60.0,
            input_torque_nm=self.input_torque_nm,
            mesh_efficiency=self.mesh_efficiency,
            allowable_tangential_force_n=self.allowable_tangential_force_n,
            allowable_tangential_force_source_status=self.allowable_tangential_force_source_status,
            allowable_tangential_force_reference=self.allowable_tangential_force_reference,
            maximum_pitch_line_speed_m_s=self.maximum_pitch_line_speed_m_s,
            maximum_pitch_line_speed_source_status=self.maximum_pitch_line_speed_source_status,
            maximum_pitch_line_speed_reference=self.maximum_pitch_line_speed_reference,
        )


class GearDriveSIInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    basis_source_status: SourceStatus
    basis_reference: str
    module_m: float
    pinion_teeth: int
    gear_teeth: int
    pressure_angle_rad: float
    input_angular_speed_rad_s: float
    input_torque_nm: float
    mesh_efficiency: float
    allowable_tangential_force_n: float | None
    allowable_tangential_force_source_status: SourceStatus | None
    allowable_tangential_force_reference: str | None
    maximum_pitch_line_speed_m_s: float | None
    maximum_pitch_line_speed_source_status: SourceStatus | None
    maximum_pitch_line_speed_reference: str | None


class GearDriveResult(EngineeringResultBase[GearDriveSIInput]):
    pinion_pitch_diameter_m: ScalarResult
    gear_pitch_diameter_m: ScalarResult
    center_distance_m: ScalarResult
    transmission_ratio: ScalarResult
    tangential_force_n: ScalarResult
    radial_force_n: ScalarResult
    pitch_line_speed_m_s: ScalarResult
    output_speed_rad_s: ScalarResult
    output_torque_nm: ScalarResult
    output_power_w: ScalarResult
    tangential_force_utilization: ScalarResult
    tangential_force_satisfied: ScalarResult
    pitch_line_speed_utilization: ScalarResult
    pitch_line_speed_satisfied: ScalarResult


Input = GearDriveInput
Result = GearDriveResult

__all__ = ["GearDriveInput", "GearDriveResult", "GearDriveSIInput", "Input", "Result"]
