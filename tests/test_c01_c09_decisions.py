from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.modules.winch_drum.calculator import calculate
from app.modules.winch_drum.schema import WarningCode
from tests.test_winch_calculator import make_input


class DecisionRegressionTests(unittest.TestCase):
    def test_load_end_and_mixed_input_conversion(self) -> None:
        both_load = calculate(
            make_input(
                force_input_location="load_end",
                speed_input_location="load_end",
                reeving_ratio=4,
                pulley_efficiency=0.8,
            )
        )
        self.assertAlmostEqual(both_load.drum_rope_force_n.value or 0, 31_250.0)
        self.assertAlmostEqual(both_load.drum_rope_speed_m_s.value or 0, 0.8)
        mixed = calculate(
            make_input(
                force_input_location="load_end",
                speed_input_location="drum_rope_end",
                reeving_ratio=4,
                pulley_efficiency=0.8,
            )
        )
        self.assertAlmostEqual(mixed.drum_rope_force_n.value or 0, 31_250.0)
        self.assertAlmostEqual(mixed.drum_rope_speed_m_s.value or 0, 0.2)

    def test_pulley_efficiency_and_default_warning(self) -> None:
        for invalid in (0, -0.1, 1.01):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                make_input(pulley_efficiency=invalid)
        result = calculate(
            make_input(
                force_input_location="load_end",
                reeving_ratio=2,
                pulley_efficiency=0.95,
            )
        )
        self.assertIn(
            WarningCode.PULLEY_EFFICIENCY_DEFAULT,
            {warning.code for warning in result.warnings},
        )

    def test_actual_pitch_and_groove_count_precedence(self) -> None:
        result = calculate(make_input(actual_groove_pitch_mm=25, actual_usable_groove_count=20))
        self.assertEqual(result.pitch_basis, "actual_groove_pitch")
        self.assertEqual(result.theoretical_turns_per_layer, 30)
        self.assertEqual(result.final_turns_per_layer, 20)
        self.assertEqual(result.turns_basis, "actual_usable_groove_count")
        steps = {step.formula_id: step for step in result.calculation_steps}
        self.assertEqual(steps["GEOM-001"].expression, "p = p_actual")
        self.assertEqual(steps["GEOM-003"].expression, "N_used = N_actual")

    def test_dead_wrap_and_termination_storage_accounting(self) -> None:
        result = calculate(make_input(dead_wraps=3, termination_allowance_m=5))
        self.assertAlmostEqual(
            result.required_total_storage_m or 0,
            300 + (result.dead_wrap_length_m or 0) + 5,
        )
        self.assertAlmostEqual(
            result.available_work_rope_length_m or 0,
            (result.capacity_at_max_layers_m or 0) - 5,
        )

    def test_dd_uses_first_layer_rope_center_diameter(self) -> None:
        result = calculate(make_input(drum_core_diameter_mm=400, rope_diameter_mm=20))
        self.assertAlmostEqual(result.dd_ratio_first_layer or 0, 21.0)
        outside_primary = calculate(make_input(rope_diameter_mm=40, drum_core_diameter_mm=800))
        self.assertIn(
            WarningCode.ROPE_DIAMETER_OUTSIDE_VALIDATED_RANGE,
            {warning.code for warning in outside_primary.warnings},
        )
        for invalid in (3.9, 64.1):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                make_input(rope_diameter_mm=invalid)

    def test_dd_below_project_minimum_reports_values_and_required_core(self) -> None:
        result = calculate(
            make_input(
                rope_diameter_mm=20,
                drum_core_diameter_mm=300,
                minimum_dd_ratio=18,
            )
        )
        warning = next(warning for warning in result.warnings if warning.code is WarningCode.DD_RATIO_BELOW_MINIMUM)
        self.assertEqual(warning.severity.value, "high")
        self.assertIn("D/d = 16.000", warning.message)
        self.assertIn("最小值 18.000", warning.message)
        self.assertIn("绳中心直径应不小于 360.000 mm", warning.message)
        self.assertIn("卷筒芯径应不小于 340.000 mm", warning.message)

    def test_service_factor_applies_only_to_rated_force(self) -> None:
        rated = calculate(make_input(force_input_type="rated", service_factor=1.5))
        design = calculate(make_input(force_input_type="design", service_factor=1.5))
        maximum = calculate(make_input(force_input_type="maximum", service_factor=1.5))
        self.assertTrue(rated.service_factor_applied)
        self.assertFalse(design.service_factor_applied)
        self.assertFalse(maximum.service_factor_applied)
        self.assertAlmostEqual(
            (rated.design_line_pull_n.value or 0) / (design.design_line_pull_n.value or 1),
            1.5,
        )

    def test_brake_factor_and_backdrive_formula_each_apply_once(self) -> None:
        result = calculate(
            make_input(
                service_factor=1.25,
                brake_safety_factor=1.5,
                backdrive_efficiency=0.8,
            )
        )
        expected_low = 100_000 * 1.25 * 0.31 * 1.5
        self.assertAlmostEqual(result.low_speed_brake_torque_nm.value or 0, expected_low)
        self.assertAlmostEqual(
            result.high_speed_brake_torque_ref_nm.value or 0,
            expected_low * 0.8 / (result.reference_ratio_nominal or 1),
        )

    def test_prohibited_backdrive_cannot_use_forward_approximation(self) -> None:
        with self.assertRaises(ValidationError):
            make_input(
                backdrive_efficiency=None,
                allow_forward_efficiency_as_reverse_approx=True,
                transmission_backdrive_type="worm",
            )
        result = calculate(
            make_input(
                backdrive_efficiency=0.8,
                transmission_backdrive_type="worm",
            )
        )
        self.assertIsNone(result.high_speed_brake_torque_ref_nm.value)
        self.assertEqual(
            result.high_speed_brake_torque_ref_nm.classification.value,
            "review_required",
        )

    def test_motor_series_selection_and_overflow(self) -> None:
        selected = calculate(
            make_input(
                rated_line_pull_kn=1,
                rope_speed_m_per_min=60,
                service_factor=1,
                total_efficiency=1,
            )
        )
        self.assertEqual(selected.suggested_motor_power_w.value, 1100.0)
        overflow = calculate(
            make_input(
                rated_line_pull_kn=1000,
                rope_speed_m_per_min=600,
                service_factor=1,
                total_efficiency=0.5,
            )
        )
        self.assertIsNone(overflow.suggested_motor_power_w.value)
        self.assertEqual(overflow.motor_selection_status, "out_of_configured_range")

    def test_warning_contract_and_repeatability(self) -> None:
        first = calculate(make_input()).model_dump(mode="json")
        second = calculate(make_input()).model_dump(mode="json")
        self.assertEqual(first, second)
        for warning in first["warnings"]:
            self.assertTrue(
                {"code", "severity", "title", "message", "affected_result", "recommended_action"} <= warning.keys()
            )
        rank = {"blocking": 0, "high": 1, "warning": 2, "info": 3}
        severities = [rank[warning["severity"]] for warning in first["warnings"]]
        self.assertEqual(severities, sorted(severities))


if __name__ == "__main__":
    unittest.main()
