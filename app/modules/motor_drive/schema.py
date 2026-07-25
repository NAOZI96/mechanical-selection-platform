"""Strict SI models for a two-segment motor-drive duty calculation."""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import Field, StrictStr, field_validator, model_validator

from app.modules.engineering_common import (
    EngineeringInputBase,
    EngineeringResultBase,
    FactorAtLeastOne,
    Fraction,
    NonNegativeFloat,
    PositiveFloat,
    ScalarResult,
    SourceStatus,
)

ReferenceText = Annotated[StrictStr, Field(min_length=1, max_length=256)]
DutyText = Annotated[StrictStr, Field(min_length=1, max_length=64)]


class MotorDriveInput(EngineeringInputBase):
    """Two explicit, non-regenerative steady operating segments in SI units."""

    segment_1_load_torque_n_m: NonNegativeFloat
    segment_1_load_speed_rad_s: NonNegativeFloat
    segment_1_duration_s: PositiveFloat
    segment_2_load_torque_n_m: NonNegativeFloat
    segment_2_load_speed_rad_s: NonNegativeFloat
    segment_2_duration_s: PositiveFloat
    transmission_ratio_motor_to_load: PositiveFloat
    transmission_efficiency: Fraction
    service_factor: FactorAtLeastOne
    declared_duty: DutyText | None = None
    candidate_rated_torque_n_m: PositiveFloat | None = None
    candidate_peak_torque_n_m: PositiveFloat | None = None
    candidate_max_speed_rad_s: PositiveFloat | None = None
    candidate_rated_power_w: PositiveFloat | None = None
    candidate_data_source_status: SourceStatus | None = None
    candidate_reference: ReferenceText | None = None

    @field_validator("declared_duty", "candidate_reference")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("文本字段不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_candidate_provenance(self) -> MotorDriveInput:
        has_candidate_data = any(
            value is not None
            for value in (
                self.candidate_rated_torque_n_m,
                self.candidate_peak_torque_n_m,
                self.candidate_max_speed_rad_s,
                self.candidate_rated_power_w,
            )
        )
        has_candidate_provenance = self.candidate_data_source_status is not None or self.candidate_reference is not None
        if has_candidate_data and (self.candidate_data_source_status is None or self.candidate_reference is None):
            raise ValueError("提供候选电机额定数据时必须同时提供来源状态和数据版本")
        if has_candidate_provenance and not has_candidate_data:
            raise ValueError("未提供候选电机额定数据时不得单独提供候选数据来源")

        try:
            ratio_efficiency = self.transmission_ratio_motor_to_load * self.transmission_efficiency
            total_duration = self.segment_1_duration_s + self.segment_2_duration_s
            if not all(math.isfinite(value) and value > 0 for value in (ratio_efficiency, total_duration)):
                raise ValueError("传动比效率乘积和总持续时间必须保持有限正值")

            torque_1 = self.segment_1_load_torque_n_m / ratio_efficiency
            torque_2 = self.segment_2_load_torque_n_m / ratio_efficiency
            speed_1 = self.segment_1_load_speed_rad_s * self.transmission_ratio_motor_to_load
            speed_2 = self.segment_2_load_speed_rad_s * self.transmission_ratio_motor_to_load
            weighted_torque = torque_1 * self.segment_1_duration_s + torque_2 * self.segment_2_duration_s
            weighted_squared_torque = torque_1**2 * self.segment_1_duration_s + torque_2**2 * self.segment_2_duration_s
            if not all(
                math.isfinite(value) and value >= 0
                for value in (
                    torque_1,
                    torque_2,
                    speed_1,
                    speed_2,
                    weighted_torque,
                    weighted_squared_torque,
                )
            ):
                raise ValueError("两段折算转矩、速度或加权量必须保持有限非负值")

            continuous_torque = weighted_torque / total_duration
            rms_torque = math.sqrt(weighted_squared_torque / total_duration)
            peak_torque = max(torque_1, torque_2)
            required_values = (
                continuous_torque * self.service_factor,
                peak_torque * self.service_factor,
                rms_torque * self.service_factor,
                max(torque_1 * speed_1, torque_2 * speed_2) * self.service_factor,
                max(speed_1, speed_2),
            )
            if not all(math.isfinite(value) and value >= 0 for value in required_values):
                raise ValueError("所需转矩、功率或最大速度超出有限非负数值范围")
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("输入组合导致电机派生计算超出有限数值范围") from exc
        return self


class MotorDriveResult(EngineeringResultBase[MotorDriveInput]):
    segment_1_motor_torque_n_m: ScalarResult
    segment_2_motor_torque_n_m: ScalarResult
    segment_1_motor_speed_rad_s: ScalarResult
    segment_2_motor_speed_rad_s: ScalarResult
    continuous_motor_torque_n_m: ScalarResult
    peak_motor_torque_n_m: ScalarResult
    rms_motor_torque_n_m: ScalarResult
    required_continuous_torque_n_m: ScalarResult
    required_peak_torque_n_m: ScalarResult
    required_rms_torque_n_m: ScalarResult
    required_power_w: ScalarResult
    maximum_motor_speed_rad_s: ScalarResult
    candidate_rated_torque_pass: ScalarResult
    candidate_peak_torque_pass: ScalarResult
    candidate_speed_pass: ScalarResult
    candidate_rated_power_pass: ScalarResult


Input = MotorDriveInput
Result = MotorDriveResult

__all__ = ["Input", "MotorDriveInput", "MotorDriveResult", "Result"]
