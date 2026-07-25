"""Strict DTOs for bearing basic life and solid-shaft nominal stress."""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from app.modules.engineering_common import (
    EngineeringInputBase,
    EngineeringResultBase,
    NonNegativeFloat,
    PositiveFloat,
    ScalarResult,
    SourceStatus,
)

ReferenceText = Annotated[StrictStr, Field(min_length=1, max_length=256)]


class ShaftBearingInput(EngineeringInputBase):
    """User input with explicit sources for every bearing catalogue coefficient."""

    bearing_radial_load_n: NonNegativeFloat = Field(title="轴承径向载荷", description="Fr，N")
    bearing_axial_load_n: NonNegativeFloat = Field(title="轴承轴向载荷", description="Fa，N")
    bearing_speed_rpm: PositiveFloat = Field(title="轴承转速", description="r/min")

    basic_dynamic_load_rating_n: PositiveFloat = Field(title="基本额定动载荷 C", description="N")
    dynamic_rating_source_status: SourceStatus = Field(title="额定动载荷来源状态")
    dynamic_rating_reference: ReferenceText = Field(title="额定动载荷型号及依据")

    radial_factor_x: NonNegativeFloat = Field(title="径向载荷系数 X")
    radial_factor_x_source_status: SourceStatus = Field(title="X 来源状态")
    radial_factor_x_reference: ReferenceText = Field(title="X 的选取依据")

    axial_factor_y: NonNegativeFloat = Field(title="轴向载荷系数 Y")
    axial_factor_y_source_status: SourceStatus = Field(title="Y 来源状态")
    axial_factor_y_reference: ReferenceText = Field(title="Y 的选取依据")

    life_exponent_p: PositiveFloat = Field(title="寿命指数 p")
    life_exponent_source_status: SourceStatus = Field(title="寿命指数来源状态")
    life_exponent_reference: ReferenceText = Field(title="寿命指数依据")

    shaft_diameter_mm: PositiveFloat = Field(title="实心圆轴直径", description="mm")
    shaft_bending_moment_nm: NonNegativeFloat = Field(title="轴截面弯矩", description="N·m")
    shaft_torque_nm: NonNegativeFloat = Field(title="轴截面扭矩", description="N·m")

    allowable_von_mises_stress_mpa: PositiveFloat | None = Field(
        default=None,
        title="候选许用 von Mises 应力",
        description="可选已批准许用值，MPa；不提供时不作强度通过结论。",
    )
    allowable_stress_source_status: SourceStatus | None = Field(default=None, title="许用应力来源状态")
    allowable_stress_reference: ReferenceText | None = Field(default=None, title="许用应力依据")

    @field_validator(
        "dynamic_rating_reference",
        "radial_factor_x_reference",
        "axial_factor_y_reference",
        "life_exponent_reference",
        "allowable_stress_reference",
    )
    @classmethod
    def strip_references(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("参数来源依据不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_loads_candidate_and_numeric_range(self) -> ShaftBearingInput:
        equivalent_load = (
            self.radial_factor_x * self.bearing_radial_load_n + self.axial_factor_y * self.bearing_axial_load_n
        )
        if equivalent_load <= 0:
            raise ValueError("X*Fr + Y*Fa 必须大于 0；请核对载荷和轴承系数")
        if self.shaft_bending_moment_nm == 0 and self.shaft_torque_nm == 0:
            raise ValueError("轴截面弯矩和扭矩不能同时为 0")

        allowable_parts = (
            self.allowable_von_mises_stress_mpa,
            self.allowable_stress_source_status,
            self.allowable_stress_reference,
        )
        if any(value is not None for value in allowable_parts) and not all(
            value is not None for value in allowable_parts
        ):
            raise ValueError("候选许用应力、来源状态和依据必须同时提供")

        try:
            shaft_diameter_m = self.shaft_diameter_mm / 1000.0
            bearing_omega = self.bearing_speed_rpm * 2.0 * math.pi / 60.0
            if not all(
                math.isfinite(value) and value > 0 for value in (equivalent_load, shaft_diameter_m, bearing_omega)
            ):
                raise ValueError("等效载荷、轴径和轴承角速度必须保持有限正值")

            rating_ratio = self.basic_dynamic_load_rating_n / equivalent_load
            if not math.isfinite(rating_ratio) or rating_ratio <= 0:
                raise ValueError("基本额定动载荷与等效载荷之比必须保持有限正值")
            l10_million_revolutions = math.pow(rating_ratio, self.life_exponent_p)

            diameter_cubed = shaft_diameter_m**3
            if not math.isfinite(diameter_cubed) or diameter_cubed <= 0:
                raise ValueError("轴径三次方在应力公式中必须保持有限正值")
            stress_denominator = math.pi * diameter_cubed
            bending_stress = 32.0 * self.shaft_bending_moment_nm / stress_denominator
            torsional_stress = 16.0 * self.shaft_torque_nm / stress_denominator
            von_mises_stress = math.sqrt(bending_stress**2 + 3.0 * torsional_stress**2)
            life_hours = l10_million_revolutions * 1.0e6 * 2.0 * math.pi / (bearing_omega * 3600.0)
            if (
                not all(
                    math.isfinite(value)
                    for value in (
                        l10_million_revolutions,
                        life_hours,
                        bending_stress,
                        torsional_stress,
                        von_mises_stress,
                    )
                )
                or l10_million_revolutions <= 0
            ):
                raise ValueError("输入组合导致寿命或应力计算超出有限数值范围")
            if von_mises_stress <= 0:
                raise ValueError("非零弯矩或扭矩必须产生有限正名义组合应力")

            allowable_stress_pa = (
                None if self.allowable_von_mises_stress_mpa is None else self.allowable_von_mises_stress_mpa * 1.0e6
            )
            if allowable_stress_pa is not None:
                stress_utilization = von_mises_stress / allowable_stress_pa
                stress_margin = allowable_stress_pa - von_mises_stress
                if not all(math.isfinite(value) for value in (allowable_stress_pa, stress_utilization, stress_margin)):
                    raise ValueError("许用应力组合导致利用率或余量超出有限数值范围")
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("输入组合导致轴承寿命或轴应力派生计算超出有限数值范围") from exc
        return self

    def to_si(self) -> ShaftBearingSIInput:
        return ShaftBearingSIInput(
            basis_source_status=self.basis_source_status,
            basis_reference=self.basis_reference,
            bearing_radial_load_n=self.bearing_radial_load_n,
            bearing_axial_load_n=self.bearing_axial_load_n,
            bearing_angular_speed_rad_s=self.bearing_speed_rpm * 2.0 * math.pi / 60.0,
            basic_dynamic_load_rating_n=self.basic_dynamic_load_rating_n,
            dynamic_rating_source_status=self.dynamic_rating_source_status,
            dynamic_rating_reference=self.dynamic_rating_reference,
            radial_factor_x=self.radial_factor_x,
            radial_factor_x_source_status=self.radial_factor_x_source_status,
            radial_factor_x_reference=self.radial_factor_x_reference,
            axial_factor_y=self.axial_factor_y,
            axial_factor_y_source_status=self.axial_factor_y_source_status,
            axial_factor_y_reference=self.axial_factor_y_reference,
            life_exponent_p=self.life_exponent_p,
            life_exponent_source_status=self.life_exponent_source_status,
            life_exponent_reference=self.life_exponent_reference,
            shaft_diameter_m=self.shaft_diameter_mm / 1000.0,
            shaft_bending_moment_nm=self.shaft_bending_moment_nm,
            shaft_torque_nm=self.shaft_torque_nm,
            allowable_von_mises_stress_pa=(
                None if self.allowable_von_mises_stress_mpa is None else self.allowable_von_mises_stress_mpa * 1.0e6
            ),
            allowable_stress_source_status=self.allowable_stress_source_status,
            allowable_stress_reference=self.allowable_stress_reference,
        )


class ShaftBearingSIInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    basis_source_status: SourceStatus
    basis_reference: str
    bearing_radial_load_n: float
    bearing_axial_load_n: float
    bearing_angular_speed_rad_s: float
    basic_dynamic_load_rating_n: float
    dynamic_rating_source_status: SourceStatus
    dynamic_rating_reference: str
    radial_factor_x: float
    radial_factor_x_source_status: SourceStatus
    radial_factor_x_reference: str
    axial_factor_y: float
    axial_factor_y_source_status: SourceStatus
    axial_factor_y_reference: str
    life_exponent_p: float
    life_exponent_source_status: SourceStatus
    life_exponent_reference: str
    shaft_diameter_m: float
    shaft_bending_moment_nm: float
    shaft_torque_nm: float
    allowable_von_mises_stress_pa: float | None
    allowable_stress_source_status: SourceStatus | None
    allowable_stress_reference: str | None


class ShaftBearingResult(EngineeringResultBase[ShaftBearingSIInput]):
    equivalent_dynamic_load_n: ScalarResult
    bearing_l10_million_revolutions: ScalarResult
    bearing_l10_life_hours: ScalarResult
    shaft_bending_stress_pa: ScalarResult
    shaft_torsional_shear_stress_pa: ScalarResult
    shaft_von_mises_stress_pa: ScalarResult
    allowable_stress_utilization: ScalarResult
    allowable_stress_margin_pa: ScalarResult
    allowable_stress_satisfied: ScalarResult


Input = ShaftBearingInput
Result = ShaftBearingResult

__all__ = ["Input", "Result", "ShaftBearingInput", "ShaftBearingResult", "ShaftBearingSIInput"]
