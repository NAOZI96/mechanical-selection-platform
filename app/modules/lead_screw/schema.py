"""Strict DTOs for an equivalent square-thread sliding lead screw."""

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


class LeadScrewInput(EngineeringInputBase):
    """User-facing square-thread-equivalent inputs normalized to SI."""

    axial_force_n: PositiveFloat = Field(title="轴向载荷", description="提升方向设计轴向载荷，N")
    mean_thread_diameter_mm: PositiveFloat = Field(title="螺纹中径", description="等效方牙螺纹中径，mm")
    root_diameter_mm: PositiveFloat = Field(title="螺纹根径", description="用于 Euler 截面惯性矩，mm")
    lead_mm_per_revolution: PositiveFloat = Field(title="导程", description="每转轴向位移，mm/rev")

    friction_coefficient: NonNegativeFloat = Field(title="螺纹摩擦系数")
    friction_source_status: SourceStatus = Field(title="摩擦系数来源状态")
    friction_reference: ReferenceText = Field(title="摩擦系数依据")

    rotational_speed_rpm: PositiveFloat = Field(title="丝杠转速", description="r/min")

    youngs_modulus_gpa: PositiveFloat = Field(title="弹性模量 E", description="GPa")
    youngs_modulus_source_status: SourceStatus = Field(title="弹性模量来源状态")
    youngs_modulus_reference: ReferenceText = Field(title="弹性模量依据")

    unsupported_length_mm: PositiveFloat = Field(title="受压无支撑长度", description="Euler 计算长度基准，mm")
    effective_length_factor: PositiveFloat = Field(
        title="有效长度系数 K",
        description="由用户依据实际端部约束显式给定；软件不提供经验默认值。",
    )
    effective_length_factor_source_status: SourceStatus = Field(title="有效长度系数来源状态")
    effective_length_factor_reference: ReferenceText = Field(title="有效长度系数依据")

    candidate_allowable_axial_load_n: PositiveFloat | None = Field(
        default=None,
        title="候选产品许用轴向载荷",
        description="可选制造商或已批准许用值，N。",
    )
    candidate_source_status: SourceStatus | None = Field(default=None, title="候选许用载荷来源状态")
    candidate_reference: ReferenceText | None = Field(default=None, title="候选型号及许用载荷依据")

    @field_validator(
        "friction_reference",
        "youngs_modulus_reference",
        "effective_length_factor_reference",
        "candidate_reference",
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
    def validate_geometry_candidate_and_numeric_range(self) -> LeadScrewInput:
        if self.root_diameter_mm >= self.mean_thread_diameter_mm:
            raise ValueError("螺纹根径必须小于等效螺纹中径")

        candidate_parts = (
            self.candidate_allowable_axial_load_n,
            self.candidate_source_status,
            self.candidate_reference,
        )
        if any(value is not None for value in candidate_parts) and not all(
            value is not None for value in candidate_parts
        ):
            raise ValueError("候选许用轴向载荷、来源状态和依据必须同时提供")

        try:
            mean_diameter_m = self.mean_thread_diameter_mm / 1000.0
            root_diameter_m = self.root_diameter_mm / 1000.0
            lead_m = self.lead_mm_per_revolution / 1000.0
            unsupported_length_m = self.unsupported_length_mm / 1000.0
            youngs_modulus_pa = self.youngs_modulus_gpa * 1.0e9
            omega = self.rotational_speed_rpm * 2.0 * math.pi / 60.0
            normalized_positive = (
                mean_diameter_m,
                root_diameter_m,
                lead_m,
                unsupported_length_m,
                youngs_modulus_pa,
                omega,
            )
            if not all(math.isfinite(value) and value > 0 for value in normalized_positive):
                raise ValueError("尺寸、弹性模量和转速在 SI 换算后必须保持有限正值")

            lead_angle_denominator = math.pi * mean_diameter_m
            if not math.isfinite(lead_angle_denominator) or lead_angle_denominator <= 0:
                raise ValueError("导程角分母必须保持有限正值")
            tan_lead_angle = lead_m / lead_angle_denominator
            raising_denominator = 1.0 - self.friction_coefficient * tan_lead_angle
            lowering_denominator = 1.0 + self.friction_coefficient * tan_lead_angle
            if (
                not math.isfinite(tan_lead_angle)
                or tan_lead_angle <= 0
                or not math.isfinite(raising_denominator)
                or raising_denominator <= 0
                or not math.isfinite(lowering_denominator)
                or lowering_denominator <= 0
            ):
                raise ValueError("摩擦系数与导程角组合使等效方牙转矩公式奇异或反号")

            raising_torque = (
                self.axial_force_n
                * mean_diameter_m
                / 2.0
                * (tan_lead_angle + self.friction_coefficient)
                / raising_denominator
            )
            lowering_torque = (
                self.axial_force_n
                * mean_diameter_m
                / 2.0
                * (self.friction_coefficient - tan_lead_angle)
                / lowering_denominator
            )
            root_diameter_fourth = root_diameter_m**4
            if not math.isfinite(root_diameter_fourth) or root_diameter_fourth <= 0:
                raise ValueError("根径四次方在 Euler 公式中必须保持有限正值")
            second_moment = math.pi * root_diameter_fourth / 64.0
            effective_length = self.effective_length_factor * unsupported_length_m
            effective_length_squared = effective_length**2
            if not all(
                math.isfinite(value) and value > 0
                for value in (raising_torque, second_moment, effective_length, effective_length_squared)
            ) or not math.isfinite(lowering_torque):
                raise ValueError("丝杠转矩、截面惯性矩或有效长度超出有限数值范围")

            critical_load = math.pi**2 * youngs_modulus_pa * second_moment / effective_length_squared
            efficiency = self.axial_force_n * lead_m / (2.0 * math.pi * raising_torque)
            linear_speed = lead_m * omega / (2.0 * math.pi)
            input_power = raising_torque * omega
            required_positive = (critical_load, efficiency, linear_speed, input_power)
            if not all(math.isfinite(value) and value > 0 for value in required_positive):
                raise ValueError("输入组合导致丝杠功率、效率或 Euler 计算失去有限正值")

            if self.candidate_allowable_axial_load_n is not None:
                candidate_utilization = self.axial_force_n / self.candidate_allowable_axial_load_n
                candidate_margin = self.candidate_allowable_axial_load_n - self.axial_force_n
                if not all(math.isfinite(value) for value in (candidate_utilization, candidate_margin)):
                    raise ValueError("候选许用载荷组合导致利用率或余量超出有限数值范围")
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("输入组合导致丝杠派生计算超出有限数值范围") from exc
        return self

    def to_si(self) -> LeadScrewSIInput:
        return LeadScrewSIInput(
            basis_source_status=self.basis_source_status,
            basis_reference=self.basis_reference,
            axial_force_n=self.axial_force_n,
            mean_thread_diameter_m=self.mean_thread_diameter_mm / 1000.0,
            root_diameter_m=self.root_diameter_mm / 1000.0,
            lead_m_per_revolution=self.lead_mm_per_revolution / 1000.0,
            friction_coefficient=self.friction_coefficient,
            friction_source_status=self.friction_source_status,
            friction_reference=self.friction_reference,
            angular_speed_rad_s=self.rotational_speed_rpm * 2.0 * math.pi / 60.0,
            youngs_modulus_pa=self.youngs_modulus_gpa * 1.0e9,
            youngs_modulus_source_status=self.youngs_modulus_source_status,
            youngs_modulus_reference=self.youngs_modulus_reference,
            unsupported_length_m=self.unsupported_length_mm / 1000.0,
            effective_length_factor=self.effective_length_factor,
            effective_length_factor_source_status=self.effective_length_factor_source_status,
            effective_length_factor_reference=self.effective_length_factor_reference,
            candidate_allowable_axial_load_n=self.candidate_allowable_axial_load_n,
            candidate_source_status=self.candidate_source_status,
            candidate_reference=self.candidate_reference,
        )


class LeadScrewSIInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    basis_source_status: SourceStatus
    basis_reference: str
    axial_force_n: float
    mean_thread_diameter_m: float
    root_diameter_m: float
    lead_m_per_revolution: float
    friction_coefficient: float
    friction_source_status: SourceStatus
    friction_reference: str
    angular_speed_rad_s: float
    youngs_modulus_pa: float
    youngs_modulus_source_status: SourceStatus
    youngs_modulus_reference: str
    unsupported_length_m: float
    effective_length_factor: float
    effective_length_factor_source_status: SourceStatus
    effective_length_factor_reference: str
    candidate_allowable_axial_load_n: float | None
    candidate_source_status: SourceStatus | None
    candidate_reference: str | None


class LeadScrewResult(EngineeringResultBase[LeadScrewSIInput]):
    lead_angle_rad: ScalarResult
    raising_torque_nm: ScalarResult
    lowering_torque_nm: ScalarResult
    raising_efficiency: ScalarResult
    linear_speed_m_s: ScalarResult
    raising_input_power_w: ScalarResult
    self_locking: ScalarResult
    root_second_moment_area_m4: ScalarResult
    euler_critical_load_n: ScalarResult
    buckling_utilization: ScalarResult
    euler_buckling_satisfied: ScalarResult
    candidate_axial_load_utilization: ScalarResult
    candidate_axial_load_margin_n: ScalarResult
    candidate_axial_load_satisfied: ScalarResult


Input = LeadScrewInput
Result = LeadScrewResult

__all__ = ["Input", "LeadScrewInput", "LeadScrewResult", "LeadScrewSIInput", "Result"]
