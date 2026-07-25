"""Strict SI models for double-acting single-rod pneumatic cylinders."""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import Field, StrictStr, field_validator, model_validator

from app.modules.engineering_common import (
    EngineeringInputBase,
    EngineeringResultBase,
    FactorAtLeastOne,
    NonNegativeFloat,
    PositiveFloat,
    ScalarResult,
    SourceStatus,
)

ReferenceText = Annotated[StrictStr, Field(min_length=1, max_length=256)]


class PneumaticCylinderInput(EngineeringInputBase):
    """Double-acting single-rod cylinder inputs expressed in SI units."""

    bore_diameter_m: PositiveFloat
    rod_diameter_m: PositiveFloat
    stroke_m: PositiveFloat
    cylinder_supply_absolute_pressure_pa: PositiveFloat
    ambient_absolute_pressure_pa: PositiveFloat
    reference_absolute_pressure_pa: PositiveFloat
    extension_load_force_n: NonNegativeFloat
    retraction_load_force_n: NonNegativeFloat
    load_safety_factor: FactorAtLeastOne
    cycle_frequency_hz: PositiveFloat
    candidate_max_supply_absolute_pressure_pa: PositiveFloat | None = None
    candidate_data_source_status: SourceStatus | None = None
    candidate_reference: ReferenceText | None = None

    @field_validator("candidate_reference")
    @classmethod
    def strip_candidate_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("候选气缸数据版本不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_geometry_pressure_and_provenance(self) -> PneumaticCylinderInput:
        if self.rod_diameter_m >= self.bore_diameter_m:
            raise ValueError("活塞杆直径必须小于缸径")
        if self.cylinder_supply_absolute_pressure_pa <= self.ambient_absolute_pressure_pa:
            raise ValueError("气缸接口供气绝压必须大于环境绝压")
        if (
            self.candidate_max_supply_absolute_pressure_pa is not None
            and self.candidate_max_supply_absolute_pressure_pa <= self.ambient_absolute_pressure_pa
        ):
            raise ValueError("候选最大供气绝压必须大于环境绝压")

        has_candidate_data = self.candidate_max_supply_absolute_pressure_pa is not None
        has_candidate_provenance = self.candidate_data_source_status is not None or self.candidate_reference is not None
        if has_candidate_data and (self.candidate_data_source_status is None or self.candidate_reference is None):
            raise ValueError("提供候选气缸压力额定值时必须同时提供来源状态和数据版本")
        if has_candidate_provenance and not has_candidate_data:
            raise ValueError("未提供候选气缸压力额定值时不得单独提供候选数据来源")

        try:
            bore_squared = self.bore_diameter_m**2
            rod_squared = self.rod_diameter_m**2
            annular_squared_difference = bore_squared - rod_squared
            if not all(
                math.isfinite(value) and value > 0 for value in (bore_squared, rod_squared, annular_squared_difference)
            ):
                raise ValueError("缸径、杆径平方及其环形面积差必须保持有限正值")

            extension_area = math.pi * bore_squared / 4.0
            retraction_area = math.pi * annular_squared_difference / 4.0
            pressure_difference = self.cylinder_supply_absolute_pressure_pa - self.ambient_absolute_pressure_pa
            extension_force = pressure_difference * extension_area
            retraction_force = pressure_difference * retraction_area
            extension_volume = extension_area * self.stroke_m
            retraction_volume = retraction_area * self.stroke_m
            chamber_volume = extension_volume + retraction_volume
            required_positive = (
                extension_area,
                retraction_area,
                pressure_difference,
                extension_force,
                retraction_force,
                extension_volume,
                retraction_volume,
                chamber_volume,
            )
            if not all(math.isfinite(value) and value > 0 for value in required_positive):
                raise ValueError("气缸面积、压差、理论力或扫掠体积必须保持有限正值")

            required_extension_force = self.extension_load_force_n * self.load_safety_factor
            required_retraction_force = self.retraction_load_force_n * self.load_safety_factor
            extension_margin = extension_force - required_extension_force
            retraction_margin = retraction_force - required_retraction_force
            reference_volume = (
                chamber_volume * self.cylinder_supply_absolute_pressure_pa / self.reference_absolute_pressure_pa
            )
            reference_consumption = reference_volume * self.cycle_frequency_hz * 60.0
            if not all(
                math.isfinite(value)
                for value in (
                    required_extension_force,
                    required_retraction_force,
                    extension_margin,
                    retraction_margin,
                )
            ) or not all(math.isfinite(value) and value > 0 for value in (reference_volume, reference_consumption)):
                raise ValueError("气缸需求力、余量或参考耗气量超出有限数值范围")
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("输入组合导致气缸派生计算超出有限数值范围") from exc
        return self


class PneumaticCylinderResult(EngineeringResultBase[PneumaticCylinderInput]):
    extension_effective_area_m2: ScalarResult
    retraction_effective_area_m2: ScalarResult
    pressure_differential_pa: ScalarResult
    theoretical_extension_force_n: ScalarResult
    theoretical_retraction_force_n: ScalarResult
    required_extension_force_n: ScalarResult
    required_retraction_force_n: ScalarResult
    extension_force_margin_n: ScalarResult
    retraction_force_margin_n: ScalarResult
    extension_force_pass: ScalarResult
    retraction_force_pass: ScalarResult
    extension_chamber_volume_m3: ScalarResult
    retraction_chamber_volume_m3: ScalarResult
    chamber_volume_per_cycle_m3: ScalarResult
    reference_air_volume_per_cycle_m3: ScalarResult
    reference_air_consumption_m3_per_min: ScalarResult
    candidate_pressure_rating_pass: ScalarResult


Input = PneumaticCylinderInput
Result = PneumaticCylinderResult

__all__ = [
    "Input",
    "PneumaticCylinderInput",
    "PneumaticCylinderResult",
    "Result",
]
