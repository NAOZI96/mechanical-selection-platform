from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.core.config import Settings
from app.main import create_app


def valid_payload() -> dict[str, object]:
    return {
        "input": {
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
            "force_input_location": "drum_rope_end",
            "speed_input_location": "drum_rope_end",
            "pulley_efficiency": 1,
            "brake_safety_factor": 1.5,
            "duty_class": "测试工况，仅提示",
            "dead_wraps": 3,
            "backdrive_efficiency": None,
            "allow_forward_efficiency_as_reverse_approx": False,
        }
    }


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "api.sqlite3"
        reports_dir = Path(self.temporary_directory.name) / "reports"
        self.client_context = TestClient(create_app(Settings(database_path=database_path, reports_dir=reports_dir)))
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    def test_health_module_discovery_and_schema(self) -> None:
        self.assertEqual(self.client.get("/health/live").json(), {"status": "live"})
        self.assertEqual(self.client.get("/health/ready").json(), {"status": "ready"})
        modules = self.client.get("/api/v1/modules").json()
        self.assertEqual([module["module_id"] for module in modules], ["winch_drum"])
        schema = self.client.get("/api/v1/modules/winch_drum/schema")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("rated_line_pull_kn", schema.json()["input_schema"]["properties"])

    def test_chinese_calculator_page_and_static_assets(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("绞车与卷筒计算", response.text)
        self.assertIn('name="rated_line_pull_kn"', response.text)
        self.assertIn("测试金样仅用于验证页面和公式", response.text)
        self.assertIn('src="/static/calculator.js"', response.text)
        self.assertEqual(self.client.get("/modules/winch_drum").status_code, 200)
        script = self.client.get("/static/calculator.js")
        stylesheet = self.client.get("/static/app.css")
        self.assertEqual(script.status_code, 200)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn("warning--${warning.severity}", script.text)
        self.assertIn("review_required", script.text)

    def test_every_public_input_has_a_form_control_or_explicit_source_wrapper(self) -> None:
        page = self.client.get("/").text
        form_names = set(re.findall(r'name="([^"]+)"', page))
        schema = self.client.get("/api/v1/modules/winch_drum/schema").json()["input_schema"]
        aliases = {"dead_wrap_count": "dead_wraps"}
        missing = {
            field
            for field in schema["properties"]
            if field != "assumption_sources" and aliases.get(field, field) not in form_names
        }
        self.assertEqual(missing, set())
        for source_field in (
            "source_service_factor",
            "source_pitch_factor",
            "source_brake_safety_factor",
            "source_approved_core_ratio",
            "source_minimum_dd_ratio",
            "source_pulley_efficiency",
            "source_dead_wrap_count",
            "source_backdrive_efficiency",
        ):
            self.assertIn(source_field, form_names)

    def test_post_get_and_html_use_the_same_saved_snapshot(self) -> None:
        created_response = self.client.post(
            "/api/v1/modules/winch_drum/calculations",
            json=valid_payload(),
        )
        self.assertEqual(created_response.status_code, 201, created_response.text)
        created = created_response.json()
        calculation_id = created["calculation_id"]
        fetched = self.client.get(f"/api/v1/calculations/{calculation_id}").json()
        self.assertEqual(fetched, created)
        self.assertEqual(fetched["results"]["design_line_pull_n"]["value"], 120000.0)
        report = self.client.get(f"/calculations/{calculation_id}/report")
        self.assertEqual(report.status_code, 200)
        self.assertIn("120000.0", report.text)
        self.assertIn("winch_drum.calc.1.1.0", report.text)

    def test_validation_unknown_module_and_missing_record(self) -> None:
        invalid = valid_payload()
        invalid["input"]["total_efficiency"] = 0  # type: ignore[index]
        response = self.client.post("/api/v1/modules/winch_drum/calculations", json=invalid)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(self.client.get("/api/v1/modules/missing/schema").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/calculations/missing").status_code, 404)

        overflow = valid_payload()
        overflow["input"]["rated_line_pull_kn"] = 1e308  # type: ignore[index]
        overflow_response = self.client.post(
            "/api/v1/modules/winch_drum/calculations",
            json=overflow,
        )
        self.assertEqual(overflow_response.status_code, 422)

    def test_pdf_endpoint_generates_and_reuses_a_valid_chinese_report(self) -> None:
        created = self.client.post(
            "/api/v1/modules/winch_drum/calculations",
            json=valid_payload(),
        ).json()
        first = self.client.get(created["links"]["pdf"])
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.headers["content-type"], "application/pdf")
        self.assertTrue(first.content.startswith(b"%PDF-"))
        self.assertEqual(first.headers["etag"].strip('"'), first.headers["x-report-sha256"])

        pdf_path = Path(self.temporary_directory.name) / "downloaded.pdf"
        pdf_path.write_bytes(first.content)
        reader = PdfReader(pdf_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("绞车与卷筒选型助手计算报告", text)
        self.assertIn("winch_drum.calc.1.1.0", text)
        self.assertIn("120000", text)
        self.assertIn("免责声明", text)

        second = self.client.get(created["links"]["pdf"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.content, first.content)
        temporary_files = list((Path(self.temporary_directory.name) / "reports" / ".tmp").glob("*"))
        self.assertEqual(temporary_files, [])

    def test_insufficient_capacity_report_uses_max_layer_not_full_rope_terms(self) -> None:
        payload = valid_payload()
        payload["input"]["target_rope_capacity_m"] = 1000  # type: ignore[index]
        created = self.client.post(
            "/api/v1/modules/winch_drum/calculations",
            json=payload,
        ).json()
        results = created["results"]
        self.assertIsNone(results["full_working_diameter_m"])
        self.assertIsNotNone(results["max_layer_working_diameter_m"])
        report = self.client.get(created["links"]["html_report"])
        self.assertEqual(report.status_code, 200)
        self.assertIn("允许最大层工作直径", report.text)
        self.assertIn("不代表满绳状态", report.text)

    def test_security_headers_are_present(self) -> None:
        response = self.client.get("/health/live")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertIn("default-src 'self'", response.headers["content-security-policy"])

    def test_request_body_limit_returns_controlled_error(self) -> None:
        database_path = Path(self.temporary_directory.name) / "limited.sqlite3"
        settings = Settings(database_path=database_path, request_body_limit_bytes=32)
        with TestClient(create_app(settings)) as limited_client:
            response = limited_client.post(
                "/api/v1/modules/winch_drum/calculations",
                json=valid_payload(),
            )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_TOO_LARGE")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    def test_chunked_body_without_content_length_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/modules/winch_drum/calculations",
            headers={"Content-Type": "application/json"},
            content=(chunk for chunk in (b'{"input":', b"{}}")),
        )
        self.assertEqual(response.status_code, 411)
        self.assertEqual(response.json()["error"]["code"], "CONTENT_LENGTH_REQUIRED")


if __name__ == "__main__":
    unittest.main()
