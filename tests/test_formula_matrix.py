from __future__ import annotations

import math
import re
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.modules.winch_drum.calculator import calculate
from app.modules.winch_drum.schema import ResultClassification
from tests.test_winch_calculator import make_input

EXPECTED_FORMULA_IDS = {
    "UNIT-001",
    "UNIT-002",
    "UNIT-003",
    "UNIT-004",
    "UNIT-005",
    "UNIT-006",
    "FORCE-001",
    "POWER-001",
    "POWER-002",
    "POWER-003",
    "DRUM-001",
    "DRUM-002",
    "GEOM-001",
    "GEOM-002",
    "GEOM-003",
    "GEOM-004",
    "CAP-001",
    "CAP-002",
    "CAP-003",
    "CAP-004",
    "CAP-005",
    "CAP-006",
    "CAP-007",
    "CAP-008",
    "WIDTH-001",
    "WIDTH-002",
    "SPEED-001",
    "SPEED-002",
    "SPEED-003",
    "SPEED-004",
    "SPEED-005",
    "RATIO-001",
    "RATIO-002",
    "BRAKE-001",
    "BRAKE-002",
    "REEVE-001",
    "REEVE-002",
}


def step_values(result, formula_id: str) -> list[float | int]:
    return [step.result_value for step in result.calculation_steps if step.formula_id == formula_id]


class FormulaMatrixTests(unittest.TestCase):
    """Trace each published formula to independent normal/boundary/unavailable evidence."""

    def test_formula_inventory_matches_spec_implementation_and_matrix(self) -> None:
        project_root = Path(__file__).parents[1]
        spec_text = (project_root / "docs" / "CALCULATION_SPEC.md").read_text(encoding="utf-8")
        calculator_text = (project_root / "app" / "modules" / "winch_drum" / "calculator.py").read_text(
            encoding="utf-8"
        )
        matrix_text = (project_root / "docs" / "FORMULA_TEST_MATRIX.md").read_text(encoding="utf-8")
        spec_ids = set(re.findall(r"`([A-Z]+-\d{3})`", spec_text))
        implementation_ids = set(re.findall(r'"([A-Z]+-\d{3})"', calculator_text))
        matrix_ids = set(re.findall(r"`([A-Z]+-\d{3})`", matrix_text))
        self.assertEqual(spec_ids, EXPECTED_FORMULA_IDS)
        self.assertEqual(implementation_ids, EXPECTED_FORMULA_IDS)
        self.assertEqual(matrix_ids, EXPECTED_FORMULA_IDS)

    def test_unit_formulas_normal_zero_margin_and_invalid_inputs(self) -> None:
        result = calculate(make_input(side_margin_mm=0))
        expected = {
            "UNIT-001": 100_000.0,
            "UNIT-002": 0.02,
            "UNIT-003": 0.2,
            "UNIT-004": 0.4,
            "UNIT-005": 0.8,
            "UNIT-006": 0.0,
        }
        for formula_id, expected_value in expected.items():
            with self.subTest(formula_id=formula_id):
                self.assertAlmostEqual(float(step_values(result, formula_id)[0]), expected_value, places=12)

        for field in ("rated_line_pull_kn", "rope_diameter_mm", "rope_speed_m_per_min"):
            with self.subTest(invalid_field=field), self.assertRaises(ValidationError):
                make_input(**{field: 0})
        for field in ("drum_core_diameter_mm", "drum_face_length_mm"):
            with self.subTest(invalid_field=field), self.assertRaises(ValidationError):
                make_input(**{field: 0})
        with self.assertRaises(ValidationError):
            make_input(side_margin_mm=-1)

    def test_force_and_power_normal_boundary_and_unavailable_suggestion(self) -> None:
        result = calculate(
            make_input(
                rated_line_pull_kn=1,
                rope_speed_m_per_min=60,
                service_factor=1,
                total_efficiency=1,
                target_rope_capacity_m=1,
                max_layers=1,
            )
        )
        self.assertEqual(step_values(result, "FORCE-001"), [1000.0])
        self.assertEqual(step_values(result, "POWER-001"), [1000.0])
        self.assertEqual(step_values(result, "POWER-002"), [1000.0])
        self.assertEqual(result.suggested_motor_power_w.value, 1100.0)
        self.assertEqual(result.suggested_motor_power_w.formula_ids, ("POWER-003",))
        self.assertEqual(
            result.suggested_motor_power_w.classification,
            ResultClassification.PRELIMINARY,
        )
        with self.assertRaises(ValidationError):
            make_input(service_factor=0.999999)
        with self.assertRaises(ValidationError):
            make_input(total_efficiency=0)

    def test_drum_rule_paths_and_invalid_ratio(self) -> None:
        supplied = calculate(make_input())
        self.assertEqual(step_values(supplied, "DRUM-001"), [0.4])

        approved = calculate(make_input(drum_core_diameter_mm=None, approved_core_ratio=20))
        self.assertEqual(step_values(approved, "DRUM-002"), [0.38])
        self.assertEqual(
            approved.used_or_suggested_core_diameter_m.classification,
            ResultClassification.PRELIMINARY,
        )

        unavailable = calculate(
            make_input(
                drum_core_diameter_mm=None,
                drum_face_length_mm=None,
                approved_core_ratio=None,
            )
        )
        self.assertEqual(unavailable.used_or_suggested_core_diameter_m.value, 0.38)
        self.assertEqual(unavailable.used_or_suggested_core_diameter_m.formula_ids, ("DRUM-002",))
        with self.assertRaises(ValidationError):
            make_input(drum_core_diameter_mm=None, approved_core_ratio=0)

    def test_geometry_formulas_normal_exact_one_turn_and_invalid_width(self) -> None:
        normal = calculate(make_input())
        self.assertAlmostEqual(float(step_values(normal, "GEOM-001")[0]), 0.021, places=12)
        self.assertAlmostEqual(float(step_values(normal, "GEOM-002")[0]), 0.76, places=12)
        self.assertEqual(step_values(normal, "GEOM-003"), [36])
        self.assertAlmostEqual(float(step_values(normal, "GEOM-004")[0]), 0.756, places=12)

        one_turn = calculate(
            make_input(
                target_rope_capacity_m=1,
                rope_diameter_mm=20,
                pitch_factor=1,
                drum_face_length_mm=80,
                side_margin_mm=20,
                max_layers=1,
                dead_wraps=2,
            )
        )
        self.assertAlmostEqual(float(step_values(one_turn, "GEOM-001")[0]), 0.02, places=12)
        self.assertAlmostEqual(float(step_values(one_turn, "GEOM-002")[0]), 0.04, places=12)
        self.assertEqual(step_values(one_turn, "GEOM-003"), [2])
        self.assertAlmostEqual(float(step_values(one_turn, "GEOM-004")[0]), 0.04, places=12)
        with self.assertRaises(ValidationError):
            make_input(
                rope_diameter_mm=20,
                pitch_factor=1,
                drum_face_length_mm=59,
                side_margin_mm=20,
            )

    def test_layer_capacity_formulas_against_independent_first_layer_arithmetic(self) -> None:
        result = calculate(make_input(dead_wraps=2))
        expected_center_diameter = 0.4 + 0.02
        expected_turn_length = math.sqrt((math.pi * expected_center_diameter) ** 2 + 0.021**2)
        expected_gross = 36 * expected_turn_length
        expected_usable = 34 * expected_turn_length
        self.assertAlmostEqual(float(step_values(result, "CAP-001")[0]), expected_center_diameter, places=12)
        self.assertAlmostEqual(float(step_values(result, "CAP-002")[0]), expected_turn_length, places=12)
        self.assertAlmostEqual(float(step_values(result, "CAP-003")[0]), expected_gross, places=12)
        self.assertAlmostEqual(float(step_values(result, "CAP-004")[0]), expected_usable, places=12)
        self.assertAlmostEqual(float(step_values(result, "CAP-005")[0]), expected_usable, places=12)

        with self.assertRaises(ValidationError):
            make_input(dead_wraps=9)

    def test_capacity_closure_exact_target_and_insufficient_path(self) -> None:
        first_layer_capacity = 43.547988548353246
        exact = calculate(make_input(target_rope_capacity_m=first_layer_capacity))
        self.assertEqual(step_values(exact, "CAP-006"), [1])
        self.assertAlmostEqual(float(step_values(exact, "CAP-007")[0]), 0.0, places=12)
        self.assertAlmostEqual(float(step_values(exact, "CAP-008")[0]), 0.0, places=12)

        insufficient = calculate(make_input(target_rope_capacity_m=1000))
        formula_ids = {step.formula_id for step in insufficient.calculation_steps}
        self.assertTrue({"CAP-006", "CAP-007", "CAP-008"}.isdisjoint(formula_ids))
        self.assertIsNone(insufficient.actual_layers)
        self.assertAlmostEqual(
            insufficient.capacity_shortfall_m or 0.0,
            1000.0 - 348.9344509320961,
            places=9,
        )

    def test_width_formulas_normal_boundary_and_unavailable_path(self) -> None:
        result = calculate(make_input(drum_face_length_mm=None))
        self.assertEqual(result.selected_candidate.turns_per_layer if result.selected_candidate else None, 32)
        self.assertAlmostEqual(float(step_values(result, "WIDTH-001")[0]), 0.672, places=12)
        self.assertAlmostEqual(float(step_values(result, "WIDTH-002")[0]), 0.712, places=12)

        unavailable = calculate(
            make_input(
                drum_core_diameter_mm=None,
                drum_face_length_mm=None,
                approved_core_ratio=None,
            )
        )
        formula_ids = {step.formula_id for step in unavailable.calculation_steps}
        self.assertTrue({"WIDTH-001", "WIDTH-002"} <= formula_ids)
        self.assertIsNotNone(unavailable.used_or_suggested_drum_face_length_m.value)

    def test_speed_and_ratio_formulas_normal_one_layer_and_unavailable_path(self) -> None:
        result = calculate(make_input())
        expected = {
            "SPEED-001": [0.42],
            "SPEED-002": [0.62],
            "SPEED-003": [7.345612758087477],
            "SPEED-004": [9.094568176679733],
            "SPEED-005": [6.1608365067830455],
            "RATIO-001": [161.63494202719488, 238.60396204014478],
            "RATIO-002": [200.11945203366983],
        }
        for formula_id, expected_values in expected.items():
            with self.subTest(formula_id=formula_id):
                actual_values = step_values(result, formula_id)
                self.assertEqual(len(actual_values), len(expected_values))
                for actual, expected_value in zip(actual_values, expected_values, strict=True):
                    self.assertAlmostEqual(float(actual), expected_value, places=9)

        one_layer = calculate(make_input(target_rope_capacity_m=40, max_layers=1))
        self.assertAlmostEqual(one_layer.empty_working_diameter_m or 0.0, 0.42, places=12)
        self.assertAlmostEqual(one_layer.full_working_diameter_m or 0.0, 0.42, places=12)
        self.assertAlmostEqual(
            one_layer.reference_ratio_empty or 0.0,
            one_layer.reference_ratio_full or 0.0,
            places=12,
        )

        unavailable = calculate(
            make_input(
                drum_core_diameter_mm=None,
                drum_face_length_mm=None,
                approved_core_ratio=None,
            )
        )
        formula_ids = {step.formula_id for step in unavailable.calculation_steps}
        self.assertTrue(any(item.startswith(("SPEED-", "RATIO-")) for item in formula_ids))
        self.assertIsNotNone(unavailable.empty_drum_speed_rpm)

    def test_brake_formulas_normal_boundary_approximation_and_unavailable_path(self) -> None:
        normal = calculate(make_input())
        self.assertEqual(step_values(normal, "BRAKE-001"), [55_800.0])
        self.assertEqual(step_values(normal, "BRAKE-002"), [])
        self.assertIsNone(normal.high_speed_brake_torque_ref_nm.value)

        minimum_factor = calculate(make_input(brake_safety_factor=1))
        self.assertEqual(step_values(minimum_factor, "BRAKE-001"), [37_200.0])

        approved_approximation = calculate(make_input(allow_forward_efficiency_as_reverse_approx=True))
        self.assertAlmostEqual(
            float(step_values(approved_approximation, "BRAKE-002")[0]),
            237.0084442966592,
            places=9,
        )

        unavailable = calculate(
            make_input(
                drum_core_diameter_mm=None,
                drum_face_length_mm=None,
                approved_core_ratio=None,
            )
        )
        self.assertTrue(step_values(unavailable, "BRAKE-001"))
        self.assertIsNotNone(unavailable.low_speed_brake_torque_nm.value)
        with self.assertRaises(ValidationError):
            make_input(brake_safety_factor=0.999999)

    def test_reeving_formulas_boundary_scaling_and_invalid_ratio(self) -> None:
        boundary = calculate(make_input(reeving_ratio=1))
        self.assertEqual(step_values(boundary, "REEVE-001"), [100_000.0])
        self.assertEqual(step_values(boundary, "REEVE-002"), [0.2])

        four_part = calculate(
            make_input(
                reeving_ratio=4,
                force_input_location="load_end",
                speed_input_location="load_end",
                pulley_efficiency=1,
            )
        )
        self.assertEqual(step_values(four_part, "REEVE-001"), [25_000.0])
        self.assertEqual(step_values(four_part, "REEVE-002"), [0.8])
        with self.assertRaises(ValidationError):
            make_input(reeving_ratio=0.999999)


if __name__ == "__main__":
    unittest.main()
