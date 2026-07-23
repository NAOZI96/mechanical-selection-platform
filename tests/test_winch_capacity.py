from __future__ import annotations

import unittest

from app.modules.winch_drum.calculator import calculate
from app.modules.winch_drum.schema import ResultClassification, WarningCode, WinchDrumInput


def make_input(**overrides: object) -> WinchDrumInput:
    values: dict[str, object] = {
        "rated_line_pull_kn": 100,
        "rope_diameter_mm": 20,
        "rope_speed_m_per_min": 12,
        "target_rope_capacity_m": 300,
        "service_factor": 1.2,
        "total_efficiency": 0.85,
        "motor_rated_speed_rpm": 1470,
        "motor_type": "三相异步电动机",
        "drum_core_diameter_mm": 400,
        "drum_face_length_mm": 800,
        "max_layers": 6,
        "pitch_factor": 1.05,
        "side_margin_mm": 20,
        "reeving_ratio": 1,
        "brake_safety_factor": 1.5,
        "duty_class": "测试工况，仅提示",
    }
    values.update(overrides)
    return WinchDrumInput(**values)


class WinchCapacityTests(unittest.TestCase):
    def test_layer_by_layer_discrete_capacity(self) -> None:
        result = calculate(make_input())
        expected_diameters = (0.42, 0.46, 0.50, 0.54, 0.58, 0.62)
        expected_capacities = (
            47.5068965982,
            52.0302669750,
            56.5537210266,
            61.0772401619,
            65.6008109173,
            70.1244233030,
        )

        self.assertEqual(len(result.layer_details), 6)
        previous_cumulative = 0.0
        for layer, expected_diameter, expected_capacity in zip(
            result.layer_details, expected_diameters, expected_capacities, strict=True
        ):
            self.assertAlmostEqual(layer.center_diameter_m, expected_diameter, places=12)
            self.assertEqual(layer.full_turns, 36)
            self.assertAlmostEqual(layer.usable_capacity_m, expected_capacity, places=9)
            self.assertGreater(layer.cumulative_usable_capacity_m, previous_cumulative)
            previous_cumulative = layer.cumulative_usable_capacity_m

    def test_single_layer_winding(self) -> None:
        result = calculate(make_input(target_rope_capacity_m=40, max_layers=1))
        self.assertTrue(result.capacity_satisfied)
        self.assertEqual(result.actual_layers, 1)
        self.assertEqual(result.evaluated_layers, 1)
        self.assertEqual(len(result.layer_details), 1)
        self.assertAlmostEqual(result.empty_working_diameter_m or 0.0, 0.42)
        self.assertAlmostEqual(result.full_working_diameter_m or 0.0, 0.42)

    def test_multi_layer_winding(self) -> None:
        result = calculate(make_input(target_rope_capacity_m=100))
        self.assertTrue(result.capacity_satisfied)
        self.assertEqual(result.actual_layers, 3)
        self.assertAlmostEqual(result.full_working_diameter_m or 0.0, 0.50)
        self.assertGreater(result.layer_details[2].used_turns, 0.0)
        self.assertEqual(result.layer_details[3].used_turns, 0.0)

    def test_target_capacity_cannot_be_met(self) -> None:
        result = calculate(make_input(target_rope_capacity_m=1000))
        self.assertFalse(result.capacity_satisfied)
        self.assertIsNone(result.actual_layers)
        self.assertIsNone(result.capacity_at_actual_layers_m)
        self.assertEqual(result.evaluated_layers, 6)
        self.assertAlmostEqual(
            result.capacity_shortfall_m or 0.0,
            1000.0 - 352.8933589819464,
            places=9,
        )
        self.assertIn(
            WarningCode.CAPACITY_INSUFFICIENT,
            {warning.code for warning in result.warnings},
        )

    def test_user_dimensions_are_checked_without_optimization(self) -> None:
        result = calculate(make_input())
        self.assertEqual(result.optimizer_candidates, ())
        self.assertIsNone(result.selected_candidate)
        self.assertEqual(
            result.used_or_suggested_core_diameter_m.classification,
            ResultClassification.CALCULATED,
        )
        self.assertEqual(
            result.used_or_suggested_drum_face_length_m.classification,
            ResultClassification.CALCULATED,
        )
        self.assertTrue(result.capacity_satisfied)

    def test_automatic_finite_geometry_search(self) -> None:
        result = calculate(
            make_input(
                drum_core_diameter_mm=None,
                drum_face_length_mm=None,
                approved_core_ratio=20,
            )
        )

        self.assertIsNotNone(result.selected_candidate)
        self.assertGreater(len(result.optimizer_candidates), 0)
        self.assertLessEqual(len(result.optimizer_candidates), 6)
        self.assertEqual(
            {candidate.layer_limit for candidate in result.optimizer_candidates},
            set(range(1, 7)),
        )
        self.assertEqual(
            result.used_or_suggested_core_diameter_m.classification,
            ResultClassification.PRELIMINARY,
        )
        self.assertEqual(
            result.used_or_suggested_drum_face_length_m.classification,
            ResultClassification.PRELIMINARY,
        )
        self.assertTrue(result.capacity_satisfied)
        self.assertGreaterEqual(
            result.capacity_at_max_layers_m or 0.0,
            300.0,
        )
        self.assertIn("几何代理量", result.selected_candidate.explanation if result.selected_candidate else "")

    def test_missing_core_rule_does_not_invent_geometry(self) -> None:
        result = calculate(
            make_input(
                drum_core_diameter_mm=None,
                drum_face_length_mm=None,
                approved_core_ratio=None,
            )
        )
        self.assertIsNone(result.used_or_suggested_core_diameter_m.value)
        self.assertEqual(result.layer_details, ())
        self.assertEqual(result.optimizer_candidates, ())
        self.assertIn(
            WarningCode.CORE_RULE_MISSING,
            {warning.code for warning in result.warnings},
        )

    def test_dead_wraps_reduce_only_first_layer_usable_capacity(self) -> None:
        without_dead_wraps = calculate(make_input(dead_wraps=0))
        with_dead_wraps = calculate(make_input(dead_wraps=2))

        turn_length_first = without_dead_wraps.layer_details[0].turn_length_m
        self.assertAlmostEqual(
            without_dead_wraps.layer_details[0].usable_capacity_m
            - with_dead_wraps.layer_details[0].usable_capacity_m,
            2 * turn_length_first,
            places=12,
        )
        self.assertEqual(
            without_dead_wraps.layer_details[1].usable_capacity_m,
            with_dead_wraps.layer_details[1].usable_capacity_m,
        )


if __name__ == "__main__":
    unittest.main()
