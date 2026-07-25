from __future__ import annotations

import unittest

from pydantic import ValidationError

import app.modules.motor_drive as motor_drive
import app.modules.pneumatic_cylinder as pneumatic_cylinder
import app.modules.stepper_motor as stepper_motor
import app.modules.synchronous_belt as synchronous_belt
from app.modules.engineering_common import ResultClassification, SourceStatus


def belt_values(*, with_candidate: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "basis_source_status": SourceStatus.MANUFACTURER_DATA,
        "basis_reference": "独立金样 BELT-GOLD-001",
        "driver_teeth": 20,
        "driven_teeth": 40,
        "belt_pitch_m": 0.01,
        "driver_angular_speed_rad_s": 100.0,
        "transmitted_power_w": 2000.0,
        "service_factor": 1.5,
        "center_distance_m": 0.5,
    }
    if with_candidate:
        values.update(
            {
                "manufacturer_allowable_effective_tension_n": 1000.0,
                "manufacturer_max_belt_speed_m_s": 4.0,
                "candidate_data_source_status": SourceStatus.MANUFACTURER_DATA,
                "candidate_reference": "候选带样本 BELT-CAT-001",
            }
        )
    return values


def motor_values(*, with_candidate: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "basis_source_status": SourceStatus.USER_INPUT,
        "basis_reference": "独立金样 MOTOR-GOLD-001",
        "segment_1_load_torque_n_m": 100.0,
        "segment_1_load_speed_rad_s": 10.0,
        "segment_1_duration_s": 4.0,
        "segment_2_load_torque_n_m": 50.0,
        "segment_2_load_speed_rad_s": 5.0,
        "segment_2_duration_s": 6.0,
        "transmission_ratio_motor_to_load": 5.0,
        "transmission_efficiency": 0.8,
        "service_factor": 1.2,
        "declared_duty": "用户声明的两段循环，工作制待供应商确认",
    }
    if with_candidate:
        values.update(
            {
                "candidate_rated_torque_n_m": 25.0,
                "candidate_peak_torque_n_m": 35.0,
                "candidate_max_speed_rad_s": 60.0,
                "candidate_rated_power_w": 2000.0,
                "candidate_data_source_status": SourceStatus.MANUFACTURER_DATA,
                "candidate_reference": "候选电机样本 MOTOR-CAT-001",
            }
        )
    return values


def stepper_values(*, with_candidate: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "basis_source_status": SourceStatus.USER_INPUT,
        "basis_reference": "独立金样 STEP-GOLD-001",
        "load_inertia_kg_m2": 0.02,
        "motor_rotor_inertia_kg_m2": 0.001,
        "transmission_ratio_motor_to_load": 4.0,
        "transmission_efficiency": 0.8,
        "target_load_speed_rad_s": 5.0,
        "acceleration_time_s": 2.0,
        "steady_load_torque_n_m": 8.0,
        "service_factor": 1.5,
        "full_steps_per_revolution": 200,
        "microstep_divisor": 16,
    }
    if with_candidate:
        values.update(
            {
                "candidate_curve_point_speed_rad_s": 20.0,
                "candidate_curve_point_torque_n_m": 4.0,
                "curve_point_speed_tolerance_rad_s": 0.0,
                "candidate_allowable_inertia_ratio": 2.0,
                "candidate_data_source_status": SourceStatus.MANUFACTURER_DATA,
                "candidate_reference": "候选曲线 STEP-CURVE-001",
            }
        )
    return values


def cylinder_values(*, with_candidate: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "basis_source_status": SourceStatus.USER_INPUT,
        "basis_reference": "独立金样 CYL-GOLD-001",
        "bore_diameter_m": 0.1,
        "rod_diameter_m": 0.04,
        "stroke_m": 0.5,
        "cylinder_supply_absolute_pressure_pa": 700000.0,
        "ambient_absolute_pressure_pa": 100000.0,
        "reference_absolute_pressure_pa": 100000.0,
        "extension_load_force_n": 3000.0,
        "retraction_load_force_n": 2000.0,
        "load_safety_factor": 1.2,
        # 1/6 Hz is exactly 10 complete extension/retraction cycles per minute.
        "cycle_frequency_hz": 1.0 / 6.0,
    }
    if with_candidate:
        values.update(
            {
                "candidate_max_supply_absolute_pressure_pa": 1000000.0,
                "candidate_data_source_status": SourceStatus.MANUFACTURER_DATA,
                "candidate_reference": "候选气缸样本 CYL-CAT-001",
            }
        )
    return values


class SynchronousBeltTests(unittest.TestCase):
    def test_independent_golden_case(self) -> None:
        result = synchronous_belt.calculate(synchronous_belt.Input(**belt_values()))

        # Independent arithmetic:
        # i=40/20=2; d1=0.01*20/pi; v=100*d1/2; P_d=2000*1.5;
        # F=P_d/v; L=2C+pi(D+d)/2+(D-d)^2/(4C).
        self.assertAlmostEqual(result.speed_ratio.value, 2.0, places=12)
        self.assertAlmostEqual(result.driven_angular_speed_rad_s.value, 50.0, places=12)
        self.assertAlmostEqual(result.driver_pitch_diameter_m.value, 0.06366197723675814, places=12)
        self.assertAlmostEqual(result.driven_pitch_diameter_m.value, 0.12732395447351627, places=12)
        self.assertAlmostEqual(result.belt_speed_m_s.value, 3.1830988618379066, places=12)
        self.assertAlmostEqual(result.design_power_w.value, 3000.0, places=12)
        self.assertAlmostEqual(result.effective_circumferential_force_n.value, 942.477796076938, places=9)
        self.assertAlmostEqual(result.approximate_open_belt_length_m.value, 1.3020264236728467, places=12)
        self.assertAlmostEqual(result.small_pulley_wrap_angle_rad.value, 3.0141825377923603, places=12)
        self.assertAlmostEqual(result.small_pulley_engaged_teeth.value, 9.594441005418556, places=12)
        self.assertIs(result.allowable_tension_pass.value, True)
        self.assertIs(result.maximum_speed_pass.value, True)

    def test_geometrically_intersecting_pitch_circles_are_rejected(self) -> None:
        values = belt_values()
        values["center_distance_m"] = 0.05
        with self.assertRaises(ValidationError):
            synchronous_belt.Input(**values)

    def test_incomplete_candidate_provenance_is_rejected(self) -> None:
        values = belt_values(with_candidate=False)
        values["manufacturer_max_belt_speed_m_s"] = 4.0
        with self.assertRaises(ValidationError):
            synchronous_belt.Input(**values)

    def test_missing_manufacturer_limits_remain_review_required(self) -> None:
        result = synchronous_belt.calculate(synchronous_belt.Input(**belt_values(with_candidate=False)))
        self.assertIsNone(result.allowable_tension_pass.value)
        self.assertIs(
            result.allowable_tension_pass.classification,
            ResultClassification.REVIEW_REQUIRED,
        )
        self.assertIsNone(result.maximum_speed_pass.value)
        self.assertIs(
            result.maximum_speed_pass.classification,
            ResultClassification.REVIEW_REQUIRED,
        )


class MotorDriveTests(unittest.TestCase):
    def test_independent_golden_case(self) -> None:
        result = motor_drive.calculate(motor_drive.Input(**motor_values()))

        # Independent arithmetic:
        # T1=100/(5*0.8)=25; T2=12.5; average=(25*4+12.5*6)/10=17.5;
        # RMS=sqrt((25^2*4+12.5^2*6)/10)=18.540496217739157.
        self.assertAlmostEqual(result.segment_1_motor_torque_n_m.value, 25.0, places=12)
        self.assertAlmostEqual(result.segment_2_motor_torque_n_m.value, 12.5, places=12)
        self.assertAlmostEqual(result.segment_1_motor_speed_rad_s.value, 50.0, places=12)
        self.assertAlmostEqual(result.segment_2_motor_speed_rad_s.value, 25.0, places=12)
        self.assertAlmostEqual(result.continuous_motor_torque_n_m.value, 17.5, places=12)
        self.assertAlmostEqual(result.peak_motor_torque_n_m.value, 25.0, places=12)
        self.assertAlmostEqual(result.rms_motor_torque_n_m.value, 18.540496217739157, places=12)
        self.assertAlmostEqual(result.required_continuous_torque_n_m.value, 21.0, places=12)
        self.assertAlmostEqual(result.required_peak_torque_n_m.value, 30.0, places=12)
        self.assertAlmostEqual(result.required_rms_torque_n_m.value, 22.24859546128699, places=12)
        self.assertAlmostEqual(result.required_power_w.value, 1500.0, places=12)
        self.assertAlmostEqual(result.maximum_motor_speed_rad_s.value, 50.0, places=12)
        self.assertIs(result.candidate_rated_torque_pass.value, True)
        self.assertIs(result.candidate_peak_torque_pass.value, True)
        self.assertIs(result.candidate_speed_pass.value, True)
        self.assertIs(result.candidate_rated_power_pass.value, True)

    def test_zero_duration_is_rejected(self) -> None:
        values = motor_values()
        values["segment_1_duration_s"] = 0.0
        with self.assertRaises(ValidationError):
            motor_drive.Input(**values)

    def test_candidate_data_requires_source_and_reference(self) -> None:
        values = motor_values(with_candidate=False)
        values["candidate_rated_torque_n_m"] = 25.0
        with self.assertRaises(ValidationError):
            motor_drive.Input(**values)

    def test_missing_candidate_data_remains_review_required(self) -> None:
        result = motor_drive.calculate(motor_drive.Input(**motor_values(with_candidate=False)))
        for field in (
            "candidate_rated_torque_pass",
            "candidate_peak_torque_pass",
            "candidate_speed_pass",
            "candidate_rated_power_pass",
        ):
            scalar = getattr(result, field)
            with self.subTest(field=field):
                self.assertIsNone(scalar.value)
                self.assertIs(scalar.classification, ResultClassification.REVIEW_REQUIRED)


class StepperMotorTests(unittest.TestCase):
    def test_independent_golden_case(self) -> None:
        result = stepper_motor.calculate(stepper_motor.Input(**stepper_values()))

        # Independent arithmetic:
        # J_ref=0.02/4^2=0.00125; J_total=0.00225; alpha=(5*4)/2=10;
        # T_peak_required=(0.00225*10 + 8/(4*0.8))*1.5=3.78375 N*m.
        self.assertAlmostEqual(result.reflected_load_inertia_kg_m2.value, 0.00125, places=15)
        self.assertAlmostEqual(result.total_motor_side_inertia_kg_m2.value, 0.00225, places=15)
        self.assertAlmostEqual(result.working_motor_speed_rad_s.value, 20.0, places=12)
        self.assertAlmostEqual(result.motor_angular_acceleration_rad_s2.value, 10.0, places=12)
        self.assertAlmostEqual(result.inertial_acceleration_torque_n_m.value, 0.0225, places=12)
        self.assertAlmostEqual(result.steady_motor_torque_n_m.value, 2.5, places=12)
        self.assertAlmostEqual(result.acceleration_motor_torque_n_m.value, 2.5225, places=12)
        self.assertAlmostEqual(result.required_steady_torque_n_m.value, 3.75, places=12)
        self.assertAlmostEqual(result.required_peak_torque_n_m.value, 3.78375, places=12)
        self.assertAlmostEqual(result.pulse_frequency_hz.value, 10185.916357881302, places=9)
        self.assertAlmostEqual(result.inertia_ratio.value, 1.25, places=12)
        self.assertIs(result.candidate_curve_torque_pass.value, True)
        self.assertIs(result.candidate_inertia_ratio_pass.value, True)
        self.assertIn("acceleration_transmission_loss_model", result.unchecked_items)
        self.assertIn(
            "STEP_ACCELERATION_LOSS_MODEL_UNCHECKED",
            {warning.code for warning in result.warnings},
        )

    def test_curve_point_must_match_working_speed_with_explicit_tolerance(self) -> None:
        values = stepper_values()
        values["candidate_curve_point_speed_rad_s"] = 21.0
        values["curve_point_speed_tolerance_rad_s"] = 0.5
        with self.assertRaises(ValidationError):
            stepper_motor.Input(**values)

    def test_partial_curve_point_is_rejected(self) -> None:
        values = stepper_values(with_candidate=False)
        values.update(
            {
                "candidate_curve_point_speed_rad_s": 20.0,
                "candidate_curve_point_torque_n_m": 4.0,
            }
        )
        with self.assertRaises(ValidationError):
            stepper_motor.Input(**values)

    def test_missing_curve_and_inertia_limit_remain_review_required(self) -> None:
        result = stepper_motor.calculate(stepper_motor.Input(**stepper_values(with_candidate=False)))
        self.assertIsNone(result.candidate_curve_torque_pass.value)
        self.assertIs(
            result.candidate_curve_torque_pass.classification,
            ResultClassification.REVIEW_REQUIRED,
        )
        self.assertIsNone(result.candidate_inertia_ratio_pass.value)
        self.assertIs(
            result.candidate_inertia_ratio_pass.classification,
            ResultClassification.REVIEW_REQUIRED,
        )


class PneumaticCylinderTests(unittest.TestCase):
    def test_independent_golden_case(self) -> None:
        result = pneumatic_cylinder.calculate(pneumatic_cylinder.Input(**cylinder_values()))

        # Independent arithmetic:
        # A_ext=pi*0.1^2/4; A_ret=pi*(0.1^2-0.04^2)/4; delta_p=600000 Pa.
        # V_ref/cycle=(A_ext+A_ret)*0.5*(700000/100000);
        # Q_ref/min=V_ref/cycle*(1/6)*60.
        self.assertAlmostEqual(result.extension_effective_area_m2.value, 0.007853981633974483, places=15)
        self.assertAlmostEqual(result.retraction_effective_area_m2.value, 0.006597344572538567, places=15)
        self.assertAlmostEqual(result.pressure_differential_pa.value, 600000.0, places=9)
        self.assertAlmostEqual(result.theoretical_extension_force_n.value, 4712.3889803846905, places=9)
        self.assertAlmostEqual(result.theoretical_retraction_force_n.value, 3958.40674352314, places=9)
        self.assertAlmostEqual(result.required_extension_force_n.value, 3600.0, places=9)
        self.assertAlmostEqual(result.required_retraction_force_n.value, 2400.0, places=9)
        self.assertAlmostEqual(result.extension_force_margin_n.value, 1112.3889803846905, places=9)
        self.assertAlmostEqual(result.retraction_force_margin_n.value, 1558.40674352314, places=9)
        self.assertIs(result.extension_force_pass.value, True)
        self.assertIs(result.retraction_force_pass.value, True)
        self.assertAlmostEqual(result.extension_chamber_volume_m3.value, 0.003926990816987242, places=15)
        self.assertAlmostEqual(result.retraction_chamber_volume_m3.value, 0.0032986722862692833, places=15)
        self.assertAlmostEqual(result.chamber_volume_per_cycle_m3.value, 0.007225663103256525, places=15)
        self.assertAlmostEqual(result.reference_air_volume_per_cycle_m3.value, 0.05057964172279568, places=14)
        self.assertAlmostEqual(result.reference_air_consumption_m3_per_min.value, 0.5057964172279568, places=12)
        self.assertIs(result.candidate_pressure_rating_pass.value, True)

    def test_rod_must_be_smaller_than_bore(self) -> None:
        values = cylinder_values()
        values["rod_diameter_m"] = 0.1
        with self.assertRaises(ValidationError):
            pneumatic_cylinder.Input(**values)

    def test_supply_absolute_pressure_must_exceed_ambient(self) -> None:
        values = cylinder_values()
        values["cylinder_supply_absolute_pressure_pa"] = 100000.0
        with self.assertRaises(ValidationError):
            pneumatic_cylinder.Input(**values)

    def test_missing_candidate_pressure_rating_remains_review_required(self) -> None:
        result = pneumatic_cylinder.calculate(pneumatic_cylinder.Input(**cylinder_values(with_candidate=False)))
        self.assertIsNone(result.candidate_pressure_rating_pass.value)
        self.assertIs(
            result.candidate_pressure_rating_pass.classification,
            ResultClassification.REVIEW_REQUIRED,
        )


class GroupBContractTests(unittest.TestCase):
    def test_calculations_are_exactly_repeatable(self) -> None:
        cases = (
            (synchronous_belt.calculate, synchronous_belt.Input(**belt_values())),
            (motor_drive.calculate, motor_drive.Input(**motor_values())),
            (stepper_motor.calculate, stepper_motor.Input(**stepper_values())),
            (
                pneumatic_cylinder.calculate,
                pneumatic_cylinder.Input(**cylinder_values()),
            ),
        )
        for calculator, data in cases:
            with self.subTest(module=data.__class__.__name__):
                first = calculator(data).model_dump(mode="json")
                second = calculator(data).model_dump(mode="json")
                self.assertEqual(first, second)

    def test_public_contract_and_audit_payload_are_complete(self) -> None:
        cases = (
            (synchronous_belt, synchronous_belt.Input(**belt_values())),
            (motor_drive, motor_drive.Input(**motor_values())),
            (stepper_motor, stepper_motor.Input(**stepper_values())),
            (pneumatic_cylinder, pneumatic_cylinder.Input(**cylinder_values())),
        )
        for module, data in cases:
            with self.subTest(module=module.MODULE_ID):
                result = module.calculate(data)
                self.assertIs(module.Input, data.__class__)
                self.assertIs(module.Result, result.__class__)
                self.assertTrue(module.MODULE_VERSION)
                self.assertTrue(module.CALCULATION_MODEL_VERSION)
                self.assertTrue(module.REPORT_TEMPLATE_VERSION)
                self.assertTrue(result.calculation_steps)
                self.assertTrue(result.assumptions)
                self.assertTrue(result.warnings)
                self.assertTrue(result.unchecked_items)
                self.assertTrue(result.disclaimer)

    def test_common_basis_reference_is_strictly_non_blank(self) -> None:
        values = belt_values()
        values["basis_reference"] = "   "
        with self.assertRaises(ValidationError):
            synchronous_belt.Input(**values)


if __name__ == "__main__":
    unittest.main()
