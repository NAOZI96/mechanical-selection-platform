"""Strict SI input and result models for synchronous-belt calculations."""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import Field, StrictStr, field_validator, model_validator

from app.modules.engineering_common import (
    EngineeringInputBase,
    EngineeringResultBase,
    FactorAtLeastOne,
    PositiveFloat,
    PositiveInt,
    ScalarResult,
    SourceStatus,
)

ReferenceText = Annotated[StrictStr, Field(min_length=1, max_length=256)]


class SynchronousBeltInput(EngineeringInputBase):
    """All dimensional and kinematic values are supplied directly in SI units."""

    driver_teeth: PositiveInt
    driven_teeth: PositiveInt
    belt_pitch_m: PositiveFloat
    driver_angular_speed_rad_s: PositiveFloat
    transmitted_power_w: PositiveFloat
    service_factor: FactorAtLeastOne
    center_distance_m: PositiveFloat
    manufacturer_allowable_effective_tension_n: PositiveFloat | None = None
    manufacturer_max_belt_speed_m_s: PositiveFloat | None = None
    candidate_data_source_status: SourceStatus | None = None
    candidate_reference: ReferenceText | None = None

    @field_validator("candidate_reference")
    @classmethod
    def strip_candidate_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("候选带数据版本不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_geometry_and_candidate_provenance(self) -> SynchronousBeltInput:
        try:
            driver_diameter = self.belt_pitch_m * self.driver_teeth / math.pi
            driven_diameter = self.belt_pitch_m * self.driven_teeth / math.pi
            if not all(math.isfinite(value) and value > 0 for value in (driver_diameter, driven_diameter)):
                raise ValueError("带轮节径必须保持有限正值")

            minimum_non_intersecting_distance = (driver_diameter + driven_diameter) / 2.0
            if (
                not math.isfinite(minimum_non_intersecting_distance)
                or self.center_distance_m <= minimum_non_intersecting_distance
            ):
                raise ValueError("中心距必须大于两带轮节圆半径之和，带轮节圆不得相交")

            ratio = self.driven_teeth / self.driver_teeth
            driven_speed = self.driver_angular_speed_rad_s / ratio
            belt_speed = self.driver_angular_speed_rad_s * driver_diameter / 2.0
            design_power = self.transmitted_power_w * self.service_factor
            if not all(math.isfinite(value) and value > 0 for value in (ratio, driven_speed, belt_speed, design_power)):
                raise ValueError("速比、带速或设计功率必须保持有限正值")
            effective_force = design_power / belt_speed

            diameter_large = max(driver_diameter, driven_diameter)
            diameter_small = min(driver_diameter, driven_diameter)
            diameter_difference = diameter_large - diameter_small
            asin_argument = diameter_difference / (2.0 * self.center_distance_m)
            if not math.isfinite(asin_argument) or not 0 <= asin_argument < 1:
                raise ValueError("包角公式的反正弦参数必须位于 [0, 1) 且为有限值")
            approximate_length = (
                2.0 * self.center_distance_m
                + math.pi * (diameter_large + diameter_small) / 2.0
                + diameter_difference**2 / (4.0 * self.center_distance_m)
            )
            wrap_angle = math.pi - 2.0 * math.asin(asin_argument)
            engaged_teeth = min(self.driver_teeth, self.driven_teeth) * wrap_angle / (2.0 * math.pi)
            if not all(
                math.isfinite(value) and value > 0
                for value in (effective_force, approximate_length, wrap_angle, engaged_teeth)
            ):
                raise ValueError("输入组合使同步带派生力或几何量失去有限正值")
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("输入组合导致同步带派生计算超出有限数值范围") from exc

        has_candidate_data = (
            self.manufacturer_allowable_effective_tension_n is not None
            or self.manufacturer_max_belt_speed_m_s is not None
        )
        has_candidate_provenance = self.candidate_data_source_status is not None or self.candidate_reference is not None
        if has_candidate_data and (self.candidate_data_source_status is None or self.candidate_reference is None):
            raise ValueError("提供候选带额定数据时必须同时提供来源状态和数据版本")
        if has_candidate_provenance and not has_candidate_data:
            raise ValueError("未提供候选带额定数据时不得单独提供候选数据来源")
        return self


class SynchronousBeltResult(EngineeringResultBase[SynchronousBeltInput]):
    speed_ratio: ScalarResult
    driven_angular_speed_rad_s: ScalarResult
    driver_pitch_diameter_m: ScalarResult
    driven_pitch_diameter_m: ScalarResult
    belt_speed_m_s: ScalarResult
    design_power_w: ScalarResult
    effective_circumferential_force_n: ScalarResult
    approximate_open_belt_length_m: ScalarResult
    small_pulley_wrap_angle_rad: ScalarResult
    small_pulley_engaged_teeth: ScalarResult
    allowable_tension_pass: ScalarResult
    maximum_speed_pass: ScalarResult


Input = SynchronousBeltInput
Result = SynchronousBeltResult

__all__ = [
    "Input",
    "Result",
    "SynchronousBeltInput",
    "SynchronousBeltResult",
]
