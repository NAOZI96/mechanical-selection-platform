from __future__ import annotations

import ast
import math
import unittest
from pathlib import Path

from app.modules.registry import get_module, list_modules
from app.modules.winch_drum.calculator import calculate
from app.modules.winch_drum.schema import (
    ResultClassification,
    WarningCode,
    WinchDrumInput,
)


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
        "dead_wraps": 0,
        "allow_forward_efficiency_as_reverse_approx": False,
    }
    values.update(overrides)
    return WinchDrumInput(**values)


class WinchCalculatorTests(unittest.TestCase):
    def test_gold_case_a001(self) -> None:
        result = calculate(make_input())

        self.assertEqual(result.calculation_model_version, "winch_drum.calc.1.0.0")
        self.assertAlmostEqual(result.design_line_pull_n.value or 0.0, 120000.0, places=9)
        self.assertAlmostEqual(result.theoretical_load_power_w.value or 0.0, 24000.0, places=9)
        self.assertAlmostEqual(
            result.minimum_motor_power_w.value or 0.0,
            28235.2941176471,
            places=8,
        )
        self.assertAlmostEqual(result.pitch_m, 0.021, places=12)
        self.assertAlmostEqual(result.usable_width_m or 0.0, 0.760, places=12)
        self.assertEqual(result.turns_per_full_layer, 36)
        self.assertEqual(result.actual_layers, 6)
        self.assertAlmostEqual(
            result.capacity_at_max_layers_m or 0.0,
            352.8933589819,
            places=9,
        )
        self.assertAlmostEqual(result.empty_drum_speed_rpm or 0.0, 9.0945681767, places=9)
        self.assertAlmostEqual(result.full_drum_speed_rpm or 0.0, 6.1608365068, places=9)
        self.assertAlmostEqual(result.reference_ratio_nominal or 0.0, 200.1194520337, places=9)
        self.assertAlmostEqual(
            result.low_speed_brake_torque_nm.value or 0.0,
            46500.0,
            places=9,
        )
        self.assertIsNone(result.high_speed_brake_torque_ref_nm.value)
        self.assertEqual(
            result.high_speed_brake_torque_ref_nm.classification,
            ResultClassification.REVIEW_REQUIRED,
        )
        self.assertIn(
            WarningCode.REVERSE_EFFICIENCY_UNKNOWN,
            {warning.code for warning in result.warnings},
        )
        formula_ids = {step.formula_id for step in result.calculation_steps}
        self.assertTrue(
            {
                "UNIT-001",
                "FORCE-001",
                "POWER-002",
                "GEOM-003",
                "CAP-005",
                "SPEED-003",
                "BRAKE-001",
            }
            <= formula_ids
        )
        self.assertTrue(all(warning.code.value.startswith("W_") for warning in result.warnings))
        ratio_steps = [step for step in result.calculation_steps if step.formula_id == "RATIO-001"]
        self.assertEqual(len(ratio_steps), 2)
        self.assertAlmostEqual(ratio_steps[0].result_value, result.reference_ratio_empty or 0.0)
        self.assertAlmostEqual(ratio_steps[1].result_value, result.reference_ratio_full or 0.0)

    def test_si_unit_conversion(self) -> None:
        source = make_input()
        si = source.to_si()

        self.assertEqual(si.rated_line_pull_n, 100000.0)
        self.assertEqual(si.rope_diameter_m, 0.02)
        self.assertEqual(si.rope_speed_m_s, 0.2)
        self.assertEqual(si.target_rope_capacity_m, 300.0)
        self.assertEqual(si.drum_core_diameter_m, 0.4)
        self.assertEqual(si.drum_face_length_m, 0.8)
        self.assertEqual(si.side_margin_m, 0.02)
        self.assertAlmostEqual(si.motor_angular_speed_rad_s, 1470 * 2 * math.pi / 60)

    def test_repeat_execution_is_identical(self) -> None:
        source = make_input()
        first = calculate(source).model_dump(mode="json")
        second = calculate(source).model_dump(mode="json")
        self.assertEqual(first, second)

    def test_service_factor_is_not_reapplied_to_brake(self) -> None:
        base = calculate(make_input(service_factor=1.0))
        increased = calculate(make_input(service_factor=2.0))

        self.assertAlmostEqual(
            (increased.design_line_pull_n.value or 0.0)
            / (base.design_line_pull_n.value or 1.0),
            2.0,
        )
        self.assertEqual(
            increased.low_speed_brake_torque_nm.value,
            base.low_speed_brake_torque_nm.value,
        )

    def test_forward_efficiency_approximation_is_explicit(self) -> None:
        result = calculate(make_input(allow_forward_efficiency_as_reverse_approx=True))
        self.assertAlmostEqual(
            result.high_speed_brake_torque_ref_nm.value or 0.0,
            273.3661410573,
            places=9,
        )
        self.assertIn(
            WarningCode.REVERSE_EFFICIENCY_APPROXIMATED,
            {warning.code for warning in result.warnings},
        )

    def test_registry_exposes_only_winch_drum(self) -> None:
        modules = list_modules()
        self.assertEqual(tuple(module.module_id for module in modules), ("winch_drum",))
        module = get_module("winch_drum")
        self.assertIs(module.input_model, WinchDrumInput)
        self.assertEqual(module.calculation_model_version, "winch_drum.calc.1.0.0")
        self.assertEqual(module.calculate(make_input()).module_id, "winch_drum")

    def test_calculator_has_no_forbidden_framework_imports(self) -> None:
        calculator_path = (
            Path(__file__).parents[1] / "app" / "modules" / "winch_drum" / "calculator.py"
        )
        tree = ast.parse(calculator_path.read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
        self.assertTrue(
            imported_roots.isdisjoint(
                {"fastapi", "jinja2", "sqlite3", "sqlalchemy", "weasyprint", "reportlab", "pypdf"}
            )
        )


if __name__ == "__main__":
    unittest.main()
