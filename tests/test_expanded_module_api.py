from __future__ import annotations

import ast
import copy
import io
import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfReader

from app.core.config import Settings
from app.main import create_app
from app.modules.engineering_common import ScalarResult
from app.modules.expanded_registry import EXPANDED_MODULE_SPECS


class ExpandedModuleApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        settings = Settings(
            database_path=root / "expanded.sqlite3",
            reports_dir=root / "reports",
        )
        self.client_context = TestClient(create_app(settings))
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    def test_eight_modules_run_through_schema_page_snapshot_html_and_pdf(self) -> None:
        for spec in EXPANDED_MODULE_SPECS:
            with self.subTest(module_id=spec.module_id):
                page = self.client.get(f"/modules/{spec.module_id}")
                self.assertEqual(page.status_code, 200)
                self.assertIn(spec.module_name, page.text)
                self.assertIn("data-engineering-workbench", page.text)
                self.assertIn('content="noindex,nofollow"', page.text)
                self.assertIn('data-release-status="internal_testing"', page.text)
                self.assertIn("内部测试（internal_testing）", page.text)

                schema_response = self.client.get(f"/api/v1/modules/{spec.module_id}/schema")
                self.assertEqual(schema_response.status_code, 200)
                schema = schema_response.json()
                self.assertEqual(schema["release_status"], "internal_testing")
                expected_example = spec.input_model.model_validate(dict(spec.example_input)).model_dump(mode="json")
                self.assertEqual(schema["example_input"], expected_example)
                self.assertTrue(schema["result_labels"])
                self.assertTrue(schema["unchecked_labels"])
                self.assertTrue(schema["assumption_labels"])

                created_response = self.client.post(
                    f"/api/v1/modules/{spec.module_id}/calculations",
                    json={"input": dict(spec.example_input)},
                )
                self.assertEqual(created_response.status_code, 201, created_response.text)
                snapshot = created_response.json()
                self.assertEqual(snapshot["module_id"], spec.module_id)
                self.assertEqual(snapshot["module_version"], "1.0.0")
                self.assertEqual(snapshot["calculation_model_version"], spec.calculation_model_version)
                self.assertTrue(snapshot["steps"])
                self.assertTrue(snapshot["warnings"])
                self.assertTrue(snapshot["results"]["unchecked_items"])
                self.assertTrue(
                    any(boundary in snapshot["disclaimer"] for boundary in ("不构成", "不得", "不能", "不等同")),
                    snapshot["disclaimer"],
                )

                fetched = self.client.get(snapshot["links"]["self"])
                self.assertEqual(fetched.status_code, 200)
                self.assertEqual(fetched.json(), snapshot)

                html_report = self.client.get(snapshot["links"]["html_report"])
                self.assertEqual(html_report.status_code, 200)
                self.assertIn(spec.module_name, html_report.text)
                self.assertIn(spec.calculation_model_version, html_report.text)
                self.assertNotIn("逐层容绳明细", html_report.text)
                if spec.module_id == "transmission_check":
                    self.assertIn("第 1 级传动比", html_report.text)
                    self.assertNotIn(">stage_1_ratio<", html_report.text)

                pdf = self.client.get(snapshot["links"]["pdf"])
                self.assertEqual(pdf.status_code, 200, pdf.text)
                self.assertEqual(pdf.headers["content-type"], "application/pdf")
                self.assertTrue(pdf.content.startswith(b"%PDF-"))
                self.assertGreater(len(pdf.content), 1000)
                pdf_reader = PdfReader(io.BytesIO(pdf.content))
                self.assertGreaterEqual(len(pdf_reader.pages), 1)
                pdf_text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
                compact_pdf_text = "".join(pdf_text.split())
                self.assertIn(spec.calculation_model_version, compact_pdf_text)
                self.assertIn(spec.report_template_version, compact_pdf_text)
                self.assertIn("免责声明", compact_pdf_text)
                self.assertIn("".join(snapshot["disclaimer"].split())[:24], compact_pdf_text)

    def test_nested_stage_example_and_generic_json_editor_contract(self) -> None:
        schema = self.client.get("/api/v1/modules/transmission_check/schema").json()
        stage_schema = schema["input_schema"]["properties"]["stages"]
        self.assertEqual(stage_schema["type"], "array")
        self.assertEqual(len(schema["example_input"]["stages"]), 2)

        script = self.client.get("/static/engineering-calculator.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn('document.createElement("textarea")', script.text)
        self.assertIn("JSON.parse(raw)", script.text)
        self.assertIn("JSON.stringify(value, null, 2)", script.text)
        self.assertNotIn("Number.parseInt", script.text)
        self.assertIn("Number.isInteger(integerValue)", script.text)
        self.assertIn("Number.isFinite(numericValue)", script.text)
        self.assertIn("assumptionDisplayLabel(assumption.key)", script.text)
        self.assertIn("uncheckedLabels[value] || value", script.text)

        cylinder_properties = self.client.get("/api/v1/modules/pneumatic_cylinder/schema").json()["input_schema"][
            "properties"
        ]
        self.assertEqual(cylinder_properties["cylinder_supply_absolute_pressure_pa"]["unit"], "Pa")
        belt_properties = self.client.get("/api/v1/modules/synchronous_belt/schema").json()["input_schema"][
            "properties"
        ]
        self.assertEqual(belt_properties["manufacturer_max_belt_speed_m_s"]["unit"], "m/s")
        lead_properties = self.client.get("/api/v1/modules/lead_screw/schema").json()["input_schema"]["properties"]
        self.assertEqual(lead_properties["lead_mm_per_revolution"]["unit"], "mm/r")

    def test_each_module_rejects_missing_required_provenance(self) -> None:
        for spec in EXPANDED_MODULE_SPECS:
            with self.subTest(module_id=spec.module_id):
                invalid = dict(spec.example_input)
                invalid.pop("basis_reference")
                response = self.client.post(
                    f"/api/v1/modules/{spec.module_id}/calculations",
                    json={"input": invalid},
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_each_module_rejects_non_strict_and_non_finite_numeric_input(self) -> None:
        representative_fields = {
            "transmission_check": "input_speed_rpm",
            "gear_drive": "module_mm",
            "shaft_bearing": "bearing_speed_rpm",
            "lead_screw": "axial_force_n",
            "synchronous_belt": "belt_pitch_m",
            "motor_drive": "segment_1_duration_s",
            "stepper_motor": "target_load_speed_rad_s",
            "pneumatic_cylinder": "bore_diameter_m",
        }
        for spec in EXPANDED_MODULE_SPECS:
            for invalid_value in ("1.0", True, float("nan"), float("inf")):
                with self.subTest(module_id=spec.module_id, invalid_value=invalid_value):
                    invalid = copy.deepcopy(dict(spec.example_input))
                    invalid[representative_fields[spec.module_id]] = invalid_value
                    with self.assertRaises(ValidationError):
                        spec.input_model.model_validate(invalid)

    def test_every_non_null_scalar_result_references_a_recorded_formula(self) -> None:
        for spec in EXPANDED_MODULE_SPECS:
            result = spec.calculate(spec.input_model.model_validate(dict(spec.example_input)))
            recorded_ids = {step.formula_id for step in result.calculation_steps}
            self.assertEqual(len(recorded_ids), len(result.calculation_steps))
            for field_name, value in result:
                if not isinstance(value, ScalarResult) or value.value is None:
                    continue
                with self.subTest(module_id=spec.module_id, field=field_name):
                    self.assertTrue(value.formula_ids)
                    self.assertTrue(set(value.formula_ids).issubset(recorded_ids))

    def test_formula_inventory_matches_runtime_specification_and_matrix(self) -> None:
        project_root = Path(__file__).parents[1]
        specification = (project_root / "docs" / "EXPANDED_MODULES_CALCULATION_SPEC.md").read_text(encoding="utf-8")
        matrix = (project_root / "docs" / "EXPANDED_FORMULA_TEST_MATRIX.md").read_text(encoding="utf-8")
        total_formula_instances = 0

        for spec in EXPANDED_MODULE_SPECS:
            payload = copy.deepcopy(dict(spec.example_input))
            if spec.module_id == "transmission_check":
                stages = list(payload["stages"])
                stages.extend(
                    (
                        {**stages[0], "stage_name": "stage-3", "ratio": 2.0, "efficiency": 0.98},
                        {**stages[1], "stage_name": "stage-4", "ratio": 5.0, "efficiency": 0.97},
                    )
                )
                payload["stages"] = stages
                payload["candidate_rated_output_torque_nm"] = 12_000.0

            result = spec.calculate(spec.input_model.model_validate(payload))
            runtime_ids = {step.formula_id for step in result.calculation_steps}
            self.assertEqual(len(runtime_ids), len(result.calculation_steps))
            total_formula_instances += len(runtime_ids)

            for document_name, document in (("specification", specification), ("matrix", matrix)):
                section = re.search(
                    rf"^## \d+\. `{re.escape(spec.module_id)}`.*?(?=^## \d+\. |\Z)",
                    document,
                    flags=re.MULTILINE | re.DOTALL,
                )
                self.assertIsNotNone(section, f"{document_name} 缺少 {spec.module_id} 章节")
                documented_ids = set(re.findall(r"`([A-Z][A-Z0-9_]*-\d{3})`", section.group(0)))
                self.assertEqual(documented_ids, runtime_ids, f"{document_name} 的公式清单发生漂移")

        self.assertEqual(total_formula_instances, 126)

    def test_candidate_exceedance_and_failure_paths_are_explicit(self) -> None:
        failure_cases = {
            "transmission_check": (
                {"candidate_rated_output_torque_nm": 1.0},
                {"candidate_torque_satisfied"},
                {"CANDIDATE_TORQUE_EXCEEDED"},
            ),
            "gear_drive": (
                {"allowable_tangential_force_n": 1.0, "maximum_pitch_line_speed_m_s": 0.1},
                {"tangential_force_satisfied", "pitch_line_speed_satisfied"},
                {"ALLOWABLE_FORCE_EXCEEDED", "MAXIMUM_SPEED_EXCEEDED"},
            ),
            "shaft_bearing": (
                {"allowable_von_mises_stress_mpa": 1.0},
                {"allowable_stress_satisfied"},
                {"ALLOWABLE_STRESS_EXCEEDED"},
            ),
            "lead_screw": (
                {
                    "friction_coefficient": 0.01,
                    "axial_force_n": 100_000.0,
                    "candidate_allowable_axial_load_n": 1_000.0,
                },
                {"self_locking", "euler_buckling_satisfied", "candidate_axial_load_satisfied"},
                {"NOT_SELF_LOCKING", "EULER_CRITICAL_LOAD_EXCEEDED", "CANDIDATE_AXIAL_LOAD_EXCEEDED"},
            ),
            "synchronous_belt": (
                {
                    "manufacturer_allowable_effective_tension_n": 1.0,
                    "manufacturer_max_belt_speed_m_s": 0.1,
                },
                {"allowable_tension_pass", "maximum_speed_pass"},
                {"BELT_ALLOWABLE_TENSION_EXCEEDED", "BELT_MAX_SPEED_EXCEEDED"},
            ),
            "motor_drive": (
                {
                    "candidate_rated_torque_n_m": 1.0,
                    "candidate_peak_torque_n_m": 1.0,
                    "candidate_max_speed_rad_s": 1.0,
                    "candidate_rated_power_w": 1.0,
                },
                {
                    "candidate_rated_torque_pass",
                    "candidate_peak_torque_pass",
                    "candidate_speed_pass",
                    "candidate_rated_power_pass",
                },
                {
                    "MOTOR_CHECK_001_FAILED",
                    "MOTOR_CHECK_002_FAILED",
                    "MOTOR_CHECK_003_FAILED",
                    "MOTOR_CHECK_004_FAILED",
                },
            ),
            "stepper_motor": (
                {"candidate_curve_point_torque_n_m": 0.1, "candidate_allowable_inertia_ratio": 0.1},
                {"candidate_curve_torque_pass", "candidate_inertia_ratio_pass"},
                {"STEP_CURVE_POINT_FAILED", "STEP_INERTIA_LIMIT_FAILED"},
            ),
            "pneumatic_cylinder": (
                {
                    "extension_load_force_n": 5_000.0,
                    "retraction_load_force_n": 4_000.0,
                    "candidate_max_supply_absolute_pressure_pa": 650_000.0,
                },
                {"extension_force_pass", "retraction_force_pass", "candidate_pressure_rating_pass"},
                {"CYL_EXTENSION_FORCE_FAILED", "CYL_RETRACTION_FORCE_FAILED", "CYL_PRESSURE_RATING_FAILED"},
            ),
        }

        specs = {spec.module_id: spec for spec in EXPANDED_MODULE_SPECS}
        for module_id, (changes, expected_false_fields, expected_warning_codes) in failure_cases.items():
            with self.subTest(module_id=module_id):
                spec = specs[module_id]
                payload = copy.deepcopy(dict(spec.example_input))
                payload.update(changes)
                result = spec.calculate(spec.input_model.model_validate(payload))
                for field_name in expected_false_fields:
                    scalar = getattr(result, field_name)
                    self.assertIsInstance(scalar, ScalarResult)
                    self.assertIs(scalar.value, False)
                    self.assertIn(scalar.classification.value, {"calculated", "preliminary"})
                warning_codes = {warning.code for warning in result.warnings}
                self.assertTrue(expected_warning_codes.issubset(warning_codes))
                severe_codes = {
                    warning.code for warning in result.warnings if warning.severity.value in {"high", "blocking"}
                }
                self.assertTrue(expected_warning_codes.issubset(severe_codes))

    def test_expanded_calculators_have_no_web_database_or_pdf_dependencies(self) -> None:
        project_root = Path(__file__).parents[1]
        forbidden_roots = {
            "fastapi",
            "jinja2",
            "sqlite3",
            "sqlalchemy",
            "weasyprint",
            "reportlab",
            "pypdf",
            "httpx",
            "requests",
        }
        for spec in EXPANDED_MODULE_SPECS:
            with self.subTest(module_id=spec.module_id):
                calculator_path = project_root / "app" / "modules" / spec.module_id / "calculator.py"
                tree = ast.parse(calculator_path.read_text(encoding="utf-8"))
                imported_roots: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported_roots.update(alias.name.split(".")[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported_roots.add(node.module.split(".")[0])
                self.assertTrue(imported_roots.isdisjoint(forbidden_roots), imported_roots & forbidden_roots)


if __name__ == "__main__":
    unittest.main()
