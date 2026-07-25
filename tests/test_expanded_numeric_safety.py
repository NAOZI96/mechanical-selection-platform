from __future__ import annotations

import copy
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.modules.expanded_registry import EXPANDED_MODULE_SPECS

TINY_POSITIVE = 5e-324


def numerically_unsafe_examples() -> Iterator[tuple[str, dict[str, object]]]:
    """Yield schema-shaped inputs whose derived float arithmetic would underflow."""

    specs = {spec.module_id: spec for spec in EXPANDED_MODULE_SPECS}
    for module_id, field_updates in (
        ("gear_drive", {"input_speed_rpm": TINY_POSITIVE}),
        ("shaft_bearing", {"bearing_speed_rpm": TINY_POSITIVE}),
        ("lead_screw", {"rotational_speed_rpm": TINY_POSITIVE}),
        ("synchronous_belt", {"belt_pitch_m": TINY_POSITIVE}),
        (
            "motor_drive",
            {
                "transmission_ratio_motor_to_load": TINY_POSITIVE,
                "transmission_efficiency": TINY_POSITIVE,
            },
        ),
        ("stepper_motor", {"transmission_ratio_motor_to_load": TINY_POSITIVE}),
        (
            "pneumatic_cylinder",
            {"reference_absolute_pressure_pa": TINY_POSITIVE},
        ),
    ):
        values = copy.deepcopy(dict(specs[module_id].example_input))
        values.update(field_updates)
        yield module_id, values

    transmission_values = copy.deepcopy(dict(specs["transmission_check"].example_input))
    stages = [dict(stage) for stage in transmission_values["stages"]]
    stages[0]["ratio"] = TINY_POSITIVE
    stages[1]["ratio"] = TINY_POSITIVE
    transmission_values["stages"] = stages
    yield "transmission_check", transmission_values


class ExpandedNumericSafetyTests(unittest.TestCase):
    def test_each_input_rejects_unsafe_derived_float_arithmetic(self) -> None:
        specs = {spec.module_id: spec for spec in EXPANDED_MODULE_SPECS}

        for module_id, values in numerically_unsafe_examples():
            with self.subTest(module_id=module_id):
                with self.assertRaises(ValidationError):
                    specs[module_id].input_model.model_validate(values)

    def test_each_unsafe_numeric_input_returns_api_422(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(
                database_path=root / "numeric-safety.sqlite3",
                reports_dir=root / "reports",
            )
            with TestClient(create_app(settings)) as client:
                for module_id, values in numerically_unsafe_examples():
                    with self.subTest(module_id=module_id):
                        response = client.post(
                            f"/api/v1/modules/{module_id}/calculations",
                            json={"input": values},
                        )
                        self.assertEqual(response.status_code, 422, response.text)
                        self.assertEqual(
                            response.json()["error"]["code"],
                            "VALIDATION_ERROR",
                        )


if __name__ == "__main__":
    unittest.main()
