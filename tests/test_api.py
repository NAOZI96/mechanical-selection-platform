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
        self.assertEqual(modules[0]["category"], "起重与牵引")
        self.assertEqual(modules[0]["entry_path"], "/modules/winch_drum")
        self.assertIn("逐层容绳", modules[0]["description"])
        schema = self.client.get("/api/v1/modules/winch_drum/schema")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("rated_line_pull_kn", schema.json()["input_schema"]["properties"])

    def test_platform_homepage_separates_available_and_planned_modules(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("船舶与海工绞车智能设计计算平台", response.text)
        self.assertIn("WinchCalc Engineering", response.text)
        self.assertIn("winch drum calculation", response.text)
        self.assertIn("静态制动力矩计算", response.text)
        self.assertIn("工程模块中心", response.text)
        self.assertIn("绞车与卷筒选型助手", response.text)
        self.assertIn('href="/modules/winch_drum"', response.text)
        self.assertIn("data-home-animation", response.text)
        self.assertIn('data-scroll-stage="modules"', response.text)
        self.assertIn('data-scroll-stage="platform"', response.text)
        self.assertIn('data-scroll-stage="extension"', response.text)
        self.assertIn('src="/static/vendor/animejs/anime.umd.min.js"', response.text)
        self.assertIn('src="/static/home-animation.js"', response.text)
        for planned_name in ("机械传动快速校核", "轴与轴承初选", "电机与驱动功率", "气缸选型"):
            self.assertIn(planned_name, response.text)
        self.assertNotIn('href="/modules/transmission_check"', response.text)
        self.assertEqual(self.client.get("/modules/transmission_check").status_code, 404)
        self.assertIn("规划状态只表示产品路线", response.text)

        animation_script = self.client.get("/static/home-animation.js")
        anime_bundle = self.client.get("/static/vendor/animejs/anime.umd.min.js")
        self.assertEqual(animation_script.status_code, 200)
        self.assertEqual(anime_bundle.status_code, 200)
        self.assertIn("prefers-reduced-motion: reduce", animation_script.text)
        self.assertIn("createDrawable", animation_script.text)
        self.assertIn("setupScrollReveals", animation_script.text)
        self.assertIn('trigger.dataset.scrollState = "visible"', animation_script.text)
        self.assertIn(
            'scrollDirection = currentScrollY < previousScrollY ? "up" : "down"',
            animation_script.text,
        )
        self.assertIn('"return-pending"', animation_script.text)
        self.assertIn("@version v4.5.0", anime_bundle.text)

    def test_head_seo_crawler_files_favicon_and_html_404(self) -> None:
        self.assertEqual(self.client.head("/").status_code, 200)
        self.assertEqual(self.client.head("/modules/winch_drum").status_code, 200)
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn("User-agent: *", robots.text)
        self.assertEqual(self.client.get("/sitemap.xml").status_code, 404)
        self.assertEqual(self.client.get("/static/favicon.svg").status_code, 200)

        browser_404 = self.client.get("/missing", headers={"Accept": "text/html"})
        self.assertEqual(browser_404.status_code, 404)
        self.assertIn("请求的资源不存在", browser_404.text)
        self.assertIn("请求 ID", browser_404.text)

        public_database = Path(self.temporary_directory.name) / "public.sqlite3"
        public_url = "https://unit-test-host"
        public_settings = Settings(database_path=public_database, public_base_url=public_url)
        with TestClient(create_app(public_settings)) as public_client:
            homepage = public_client.get("/")
            self.assertIn(f'<link rel="canonical" href="{public_url}/">', homepage.text)
            self.assertIn(f"Sitemap: {public_url}/sitemap.xml", public_client.get("/robots.txt").text)
            sitemap = public_client.get("/sitemap.xml")
            self.assertEqual(sitemap.status_code, 200)
            self.assertIn(f"<loc>{public_url}/modules/winch_drum</loc>", sitemap.text)

    def test_chinese_calculator_page_and_static_assets(self) -> None:
        response = self.client.get("/modules/winch_drum")
        self.assertEqual(response.status_code, 200)
        self.assertIn("绞车卷筒与容绳量计算", response.text)
        self.assertIn("不输出整机“设计合格”结论", response.text)
        self.assertIn('id="design-conclusion"', response.text)
        self.assertIn('id="check-rows"', response.text)
        self.assertIn('name="rated_line_pull_kn"', response.text)
        self.assertIn("测试金样仅用于验证页面和公式", response.text)
        self.assertIn('src="/static/calculator.js"', response.text)
        self.assertIn('href="/#modules">模块中心</a>', response.text)
        script = self.client.get("/static/calculator.js")
        stylesheet = self.client.get("/static/app.css")
        self.assertEqual(script.status_code, 200)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn("warning--${warning.severity}", script.text)
        self.assertIn("review_required", script.text)

    def test_record_fields_use_chinese_defaults_and_selectable_dictionaries(self) -> None:
        page = self.client.get("/modules/winch_drum").text
        for field, value, option_list in (
            ("rope_type", "镀锌钢丝绳", "rope-type-options"),
            ("rope_construction", "6×36-IWRC", "rope-construction-options"),
            ("rope_material", "镀锌钢", "rope-material-options"),
            ("load_spectrum", "中等载荷", "load-spectrum-options"),
            ("environment_type", "室内常温干燥环境", "environment-type-options"),
        ):
            with self.subTest(field=field):
                self.assertIn(f'name="{field}"', page)
                self.assertIn(f'value="{value}"', page)
                self.assertIn(f'list="{option_list}"', page)
                self.assertIn(f'<datalist id="{option_list}">', page)
        self.assertIn("海洋或盐雾环境", page)
        self.assertIn("可从中文备选库选择，也可按实际工况填写", page)

    def test_every_public_input_has_a_form_control_or_explicit_source_wrapper(self) -> None:
        page = self.client.get("/modules/winch_drum").text
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
        self.assertIn(">120000<", report.text)
        self.assertIn("winch_drum.calc.1.2.0", report.text)

    def test_report_actions_chinese_labels_custom_values_and_formula_layout(self) -> None:
        payload = valid_payload()
        custom_records = {
            "rope_type": "项目定制钢丝绳",
            "rope_construction": "用户确认结构甲",
            "rope_material": "项目材料牌号甲",
            "load_spectrum": "间歇重载且有冲击",
            "environment_type": "室外潮湿并有盐雾",
        }
        payload["input"].update(custom_records)  # type: ignore[union-attr]
        created = self.client.post(
            "/api/v1/modules/winch_drum/calculations",
            json=payload,
        ).json()
        self.assertEqual(created["report_template_version"], "winch_drum.report.1.2.0")
        self.assertEqual(created["report_context"]["schema_version"], 3)
        for field, value in custom_records.items():
            self.assertEqual(created["input_original"][field], value)

        report = self.client.get(created["links"]["html_report"])
        self.assertEqual(report.status_code, 200)
        self.assertIn('href="/modules/winch_drum">返回计算页</a>', report.text)
        self.assertIn(f'href="{created["links"]["pdf"]}">下载 PDF</a>', report.text)
        for label in ("输入拉力（kN）", "绳索类型", "载荷谱说明", "环境类型", "理论计算值", "项目设定"):
            self.assertIn(label, report.text)
        for value in custom_records.values():
            self.assertIn(value, report.text)
        self.assertIn('class="formula-card"', report.text)
        self.assertIn("代入值", report.text)
        self.assertIn("计算结果", report.text)
        self.assertIn("F_d = F_r × K_s", report.text)

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
        self.assertIn("winch_drum.calc.1.2.0", text)
        self.assertIn("winch_drum.report.1.2.0", text)
        self.assertIn("120000", text)
        self.assertIn("理论计算值", text)
        self.assertIn("代入值", text)
        self.assertIn("计算结果", text)
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
