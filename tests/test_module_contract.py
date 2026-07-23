from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from app.core.config import Settings
from app.main import create_app
from app.modules.catalog import build_module_catalog
from app.modules.registry import ModuleDefinition, ModuleRegistry
from app.persistence.database import initialize_database
from app.reporting.context import build_report_context
from app.reporting.models import ReportContext, ReportResultRow


class DummyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int


class DummyResult(BaseModel):
    module_id: str = "dummy_module"
    module_version: str = "1.0.0"
    calculation_model_version: str = "dummy.calc.1.0.0"
    status: str = "completed"
    input_si: dict[str, int]
    assumptions: list[object] = []
    calculation_steps: list[object] = []
    warnings: list[object] = []
    disclaimer: str = "仅用于模块契约测试。"
    doubled_value: int


def calculate_dummy(data: BaseModel) -> BaseModel:
    if not isinstance(data, DummyInput):
        raise TypeError
    return DummyResult(input_si={"value": data.value}, doubled_value=data.value * 2)


def build_dummy_report_context(snapshot: dict[str, object]) -> ReportContext:
    context = build_report_context(snapshot, module_name="测试模块")
    doubled_value = int(snapshot["results"]["doubled_value"])
    return context.model_copy(
        update={
            "result_rows": (
                ReportResultRow(
                    key="doubled_value",
                    label="加倍值",
                    value=doubled_value,
                    display_value=str(doubled_value),
                    unit="",
                    classification="calculated",
                    formula_ids=("DUMMY-001",),
                ),
            )
        }
    )


class ModuleContractTests(unittest.TestCase):
    def test_registered_module_replaces_matching_roadmap_placeholder(self) -> None:
        registry = ModuleRegistry()
        registry.register(
            ModuleDefinition(
                module_id="transmission_check",
                module_name="机械传动快速校核",
                module_version="1.0.0",
                calculation_model_version="transmission.calc.1.0.0",
                report_template_version="transmission.report.1.0.0",
                input_model=DummyInput,
                result_model=DummyResult,
                calculate=calculate_dummy,
                build_report_context=build_dummy_report_context,
                summary="测试注册后的目录提升。",
                category="传动系统",
                web_template="calculator.html",
                catalog_order=20,
            )
        )
        matching_items = [item for item in build_module_catalog(registry) if item.module_id == "transmission_check"]
        self.assertEqual(len(matching_items), 1)
        self.assertEqual(matching_items[0].status, "available")
        self.assertEqual(matching_items[0].entry_path, "/modules/transmission_check")

    def test_dummy_module_runs_through_generic_service_without_core_changes(self) -> None:
        registry = ModuleRegistry()
        registry.register(
            ModuleDefinition(
                module_id="dummy_module",
                module_name="测试模块",
                module_version="1.0.0",
                calculation_model_version="dummy.calc.1.0.0",
                report_template_version="dummy.report.1.0.0",
                input_model=DummyInput,
                result_model=DummyResult,
                calculate=calculate_dummy,
                build_report_context=build_dummy_report_context,
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "dummy.sqlite3"
            initialize_database(database_path)
            with TestClient(create_app(Settings(database_path=database_path), registry)) as client:
                modules = client.get("/api/v1/modules").json()
                module_page = client.get("/modules/dummy_module")
                created_response = client.post(
                    "/api/v1/modules/dummy_module/calculations",
                    json={"input": {"value": 7}},
                )
                self.assertEqual(created_response.status_code, 201, created_response.text)
                created = created_response.json()
                fetched = client.get(created["links"]["self"]).json()
                report = client.get(created["links"]["html_report"])
        self.assertEqual([module["module_id"] for module in modules], ["dummy_module"])
        self.assertEqual(module_page.status_code, 501)
        self.assertEqual(created["results"]["doubled_value"], 14)
        self.assertEqual(fetched, created)
        self.assertEqual(report.status_code, 200)
        self.assertIn("加倍值", report.text)
        self.assertIn(">14<", report.text)

    def test_registry_rejects_duplicate_and_incomplete_modules(self) -> None:
        registry = ModuleRegistry()
        definition = ModuleDefinition(
            module_id="dummy_module",
            module_name="测试模块",
            module_version="1.0.0",
            calculation_model_version="dummy.calc.1.0.0",
            report_template_version="dummy.report.1.0.0",
            input_model=DummyInput,
            result_model=DummyResult,
            calculate=calculate_dummy,
            build_report_context=build_dummy_report_context,
        )
        registry.register(definition)
        with self.assertRaises(ValueError):
            registry.register(definition)


if __name__ == "__main__":
    unittest.main()
