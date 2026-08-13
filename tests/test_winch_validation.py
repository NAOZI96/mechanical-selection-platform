from __future__ import annotations

import math
import unittest

from pydantic import ValidationError

from app.modules.winch_drum.schema import WinchDrumInput


def valid_values() -> dict[str, object]:
    return {
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
        "assumption_sources": {
            "service_factor": "user_input",
            "pitch_factor": "user_input",
            "brake_safety_factor": "user_input",
            "pulley_efficiency": "user_input",
            "dead_wrap_count": "user_input",
            "minimum_dd_ratio": "user_input",
        },
    }


class WinchValidationTests(unittest.TestCase):
    def assert_invalid(self, field: str, value: object) -> None:
        values = valid_values()
        values[field] = value
        with self.assertRaises(ValidationError, msg=f"{field}={value!r} 应无效"):
            WinchDrumInput(**values)

    def test_zero_and_negative_required_physical_inputs(self) -> None:
        fields = (
            "rated_line_pull_kn",
            "rope_diameter_mm",
            "rope_speed_m_per_min",
            "target_rope_capacity_m",
        )
        for field in fields:
            with self.subTest(field=field, value=0):
                self.assert_invalid(field, 0)
            with self.subTest(field=field, value=-1):
                self.assert_invalid(field, -1)

    def test_efficiency_range(self) -> None:
        for value in (0, -0.1, 1.000001):
            with self.subTest(value=value):
                self.assert_invalid("total_efficiency", value)
        self.assertEqual(WinchDrumInput(**{**valid_values(), "total_efficiency": 1}).total_efficiency, 1)

    def test_all_factors_have_documented_lower_bounds(self) -> None:
        for field in (
            "service_factor",
            "pitch_factor",
            "reeving_ratio",
            "brake_safety_factor",
        ):
            with self.subTest(field=field):
                self.assert_invalid(field, 0.999999)

        source_controlled_values = {
            "service_factor": 1.3,
            "pitch_factor": 1.2,
            "brake_safety_factor": 1.6,
            "pulley_efficiency": 0.9,
            "dead_wrap_count": 4,
            "minimum_dd_ratio": 21,
            "motor_duty_type": "S5",
            "duty_cycle_percent": 50,
            "starts_per_hour": 120,
            "supply_voltage": 440,
            "supply_frequency": 60,
        }
        for field, value in source_controlled_values.items():
            with self.subTest(field=field, source="project_default"):
                values = valid_values()
                values[field] = value
                sources = dict(values["assumption_sources"])  # type: ignore[arg-type]
                sources[field] = "project_default"
                values["assumption_sources"] = sources
                with self.assertRaisesRegex(ValidationError, "必须明确选择"):
                    WinchDrumInput(**values)

                sources[field] = "user_input"
                values["assumption_sources"] = sources
                self.assertEqual(getattr(WinchDrumInput(**values), field), value)

    def test_max_layers_must_be_positive_strict_integer(self) -> None:
        for value in (0, -1, 1.0, 1.5, True, 101):
            with self.subTest(value=value):
                self.assert_invalid("max_layers", value)

    def test_non_finite_values_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                self.assert_invalid("rated_line_pull_kn", value)

    def test_finite_inputs_that_overflow_si_calculations_are_rejected(self) -> None:
        for field in ("rated_line_pull_kn", "rope_speed_m_per_min", "service_factor"):
            with self.subTest(field=field):
                self.assert_invalid(field, 1e308)

    def test_numeric_strings_and_booleans_are_rejected(self) -> None:
        for value in ("100", True, False):
            with self.subTest(value=value):
                self.assert_invalid("rated_line_pull_kn", value)

    def test_optional_dimensions_must_be_positive_when_present(self) -> None:
        for field in ("drum_core_diameter_mm", "drum_face_length_mm"):
            for value in (0, -1):
                with self.subTest(field=field, value=value):
                    self.assert_invalid(field, value)

    def test_face_length_must_leave_room_for_one_turn(self) -> None:
        values = valid_values()
        values.update(
            {
                "drum_face_length_mm": 50,
                "side_margin_mm": 20,
                "rope_diameter_mm": 20,
                "pitch_factor": 1.0,
            }
        )
        with self.assertRaises(ValidationError):
            WinchDrumInput(**values)

    def test_dead_wraps_cannot_exceed_available_turns(self) -> None:
        values = valid_values()
        values["dead_wraps"] = 37
        with self.assertRaises(ValidationError):
            WinchDrumInput(**values)

        values = valid_values()
        values.update({"dead_wraps": 3, "actual_usable_groove_count": 2})
        with self.assertRaises(ValidationError):
            WinchDrumInput(**values)

    def test_frozen_configuration_identifiers_reject_unknown_values(self) -> None:
        self.assert_invalid("brake_basis_type", "rated_force")
        self.assert_invalid("motor_power_series_id", "custom_unreviewed_series")
        self.assert_invalid("transmission_backdrive_type", "unknown_drive")

    def test_backdrive_efficiency_has_no_numeric_default(self) -> None:
        model = WinchDrumInput(**valid_values())
        self.assertIsNone(model.backdrive_efficiency)

        for field in ("approved_core_ratio", "backdrive_efficiency"):
            with self.subTest(field=field, source="project_default"):
                values = valid_values()
                sources = dict(values["assumption_sources"])  # type: ignore[arg-type]
                sources[field] = "project_default"
                values["assumption_sources"] = sources
                if field == "approved_core_ratio":
                    values[field] = 20
                else:
                    values[field] = 0.8
                with self.assertRaisesRegex(ValidationError, "没有项目数值默认"):
                    WinchDrumInput(**values)

                values[field] = None
                with self.assertRaisesRegex(ValidationError, "没有项目数值默认"):
                    WinchDrumInput(**values)

        default_values = valid_values()
        default_values.update(
            {
                "service_factor": 1.25,
                "pitch_factor": 1.10,
                "pulley_efficiency": 0.95,
                "brake_safety_factor": 1.50,
                "minimum_dd_ratio": 20,
            }
        )
        default_values.pop("assumption_sources")
        defaults = WinchDrumInput(**default_values)
        self.assertEqual(defaults.motor_duty_type, "S3")
        self.assertEqual(defaults.duty_cycle_percent, 40)
        self.assertEqual(defaults.starts_per_hour, 60)
        self.assertEqual(defaults.supply_voltage, 380)
        self.assertEqual(defaults.supply_frequency, 50)

    def test_text_fields_are_trimmed_and_not_blank(self) -> None:
        model = WinchDrumInput(**{**valid_values(), "motor_type": "  motor  "})
        self.assertEqual(model.motor_type, "motor")
        self.assert_invalid("duty_class", "   ")

    def test_chinese_record_fields_allow_custom_values_and_enforce_boundaries(self) -> None:
        custom_records = {
            "rope_type": "  项目定制钢丝绳  ",
            "rope_construction": "用户确认结构甲",
            "rope_material": "项目材料牌号甲",
            "load_spectrum": "间歇重载且有冲击",
            "environment_type": "室外潮湿并有盐雾",
        }
        model = WinchDrumInput(**{**valid_values(), **custom_records})
        self.assertEqual(model.rope_type, "项目定制钢丝绳")
        self.assertEqual(model.environment_type, "室外潮湿并有盐雾")

        for field in custom_records:
            with self.subTest(field=field, boundary="blank"):
                self.assert_invalid(field, "   ")
        for field, limit in (
            ("rope_type", 64),
            ("rope_construction", 128),
            ("rope_material", 128),
            ("load_spectrum", 128),
            ("environment_type", 128),
        ):
            with self.subTest(field=field, boundary="too_long"):
                self.assert_invalid(field, "中" * (limit + 1))


if __name__ == "__main__":
    unittest.main()
