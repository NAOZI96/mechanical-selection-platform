"""Strict SI models for stepper-motor motion and torque preselection."""

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
    PositiveInt,
    ScalarResult,
    SourceStatus,
)

ReferenceText = Annotated[StrictStr, Field(min_length=1, max_length=256)]


class StepperMotorInput(EngineeringInputBase):
    """Stepper motor inputs; all mechanical quantities use SI units."""

    load_inertia_kg_m2: NonNegativeFloat
    motor_rotor_inertia_kg_m2: PositiveFloat
    transmission_ratio_motor_to_load: PositiveFloat
    transmission_efficiency: Fraction
    target_load_speed_rad_s: PositiveFloat
    acceleration_time_s: PositiveFloat
    steady_load_torque_n_m: NonNegativeFloat
    service_factor: FactorAtLeastOne
    full_steps_per_revolution: PositiveInt
    microstep_divisor: PositiveInt
    candidate_curve_point_speed_rad_s: PositiveFloat | None = None
    candidate_curve_point_torque_n_m: PositiveFloat | None = None
    curve_point_speed_tolerance_rad_s: NonNegativeFloat | None = None
    candidate_allowable_inertia_ratio: PositiveFloat | None = None
    candidate_data_source_status: SourceStatus | None = None
    candidate_reference: ReferenceText | None = None

    @field_validator("candidate_reference")
    @classmethod
    def strip_candidate_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("候选电机/驱动器数据版本不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_curve_point_and_provenance(self) -> StepperMotorInput:
        try:
            ratio_squared = self.transmission_ratio_motor_to_load**2
            ratio_efficiency = self.transmission_ratio_motor_to_load * self.transmission_efficiency
            if not all(math.isfinite(value) and value > 0 for value in (ratio_squared, ratio_efficiency)):
                raise ValueError("传动比平方和传动比效率乘积必须保持有限正值")

            reflected_inertia = self.load_inertia_kg_m2 / ratio_squared
            total_inertia = self.motor_rotor_inertia_kg_m2 + reflected_inertia
            working_speed = self.target_load_speed_rad_s * self.transmission_ratio_motor_to_load
            if not all(
                math.isfinite(value) and value > 0 for value in (total_inertia, working_speed)
            ) or not math.isfinite(reflected_inertia):
                raise ValueError("折算惯量、总惯量和工作速度必须保持有限有效值")

            angular_acceleration = working_speed / self.acceleration_time_s
            inertial_torque = total_inertia * angular_acceleration
            steady_torque = self.steady_load_torque_n_m / ratio_efficiency
            acceleration_torque = inertial_torque + steady_torque
            required_steady_torque = steady_torque * self.service_factor
            required_peak_torque = acceleration_torque * self.service_factor
            pulse_frequency = working_speed / (2.0 * math.pi) * self.full_steps_per_revolution * self.microstep_divisor
            inertia_ratio = reflected_inertia / self.motor_rotor_inertia_kg_m2
            if not all(
                math.isfinite(value) and value >= 0
                for value in (reflected_inertia, steady_torque, required_steady_torque, inertia_ratio)
            ) or not all(
                math.isfinite(value) and value > 0
                for value in (
                    angular_acceleration,
                    inertial_torque,
                    acceleration_torque,
                    required_peak_torque,
                    pulse_frequency,
                )
            ):
                raise ValueError("步进电机惯量、速度、转矩或脉冲频率超出有限数值范围")
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("输入组合导致步进电机派生计算超出有限数值范围") from exc

        curve_fields = (
            self.candidate_curve_point_speed_rad_s,
            self.candidate_curve_point_torque_n_m,
            self.curve_point_speed_tolerance_rad_s,
        )
        curve_field_count = sum(value is not None for value in curve_fields)
        if curve_field_count not in (0, len(curve_fields)):
            raise ValueError("曲线工作点速度、转矩和速度匹配容差必须同时提供")

        if curve_field_count == len(curve_fields):
            assert self.candidate_curve_point_speed_rad_s is not None
            assert self.curve_point_speed_tolerance_rad_s is not None
            speed_difference = abs(self.candidate_curve_point_speed_rad_s - working_speed)
            if speed_difference > self.curve_point_speed_tolerance_rad_s:
                raise ValueError("候选曲线工作点速度未在用户给定容差内匹配计算工作速度")

        has_candidate_data = curve_field_count > 0 or self.candidate_allowable_inertia_ratio is not None
        has_candidate_provenance = self.candidate_data_source_status is not None or self.candidate_reference is not None
        if has_candidate_data and (self.candidate_data_source_status is None or self.candidate_reference is None):
            raise ValueError("提供候选曲线或允许惯量比时必须同时提供来源状态和数据版本")
        if has_candidate_provenance and not has_candidate_data:
            raise ValueError("未提供候选数据时不得单独提供候选数据来源")
        return self


class StepperMotorResult(EngineeringResultBase[StepperMotorInput]):
    reflected_load_inertia_kg_m2: ScalarResult
    total_motor_side_inertia_kg_m2: ScalarResult
    working_motor_speed_rad_s: ScalarResult
    motor_angular_acceleration_rad_s2: ScalarResult
    inertial_acceleration_torque_n_m: ScalarResult
    steady_motor_torque_n_m: ScalarResult
    acceleration_motor_torque_n_m: ScalarResult
    required_steady_torque_n_m: ScalarResult
    required_peak_torque_n_m: ScalarResult
    pulse_frequency_hz: ScalarResult
    inertia_ratio: ScalarResult
    candidate_curve_torque_pass: ScalarResult
    candidate_inertia_ratio_pass: ScalarResult


Input = StepperMotorInput
Result = StepperMotorResult

__all__ = ["Input", "Result", "StepperMotorInput", "StepperMotorResult"]
