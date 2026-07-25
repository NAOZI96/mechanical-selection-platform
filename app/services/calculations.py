"""Calculation orchestration without embedding engineering formulas."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.modules.registry import ModuleDefinition
from app.persistence.repository import CalculationRepository


class CalculationService:
    def __init__(
        self,
        repository: CalculationRepository,
        module_lookup: Callable[[str], ModuleDefinition],
    ) -> None:
        self._repository = repository
        self._module_lookup = module_lookup

    def create(self, module_id: str, raw_input: dict[str, Any], request_id: str) -> dict[str, Any]:
        module = self._module_lookup(module_id)
        validated_input = module.input_model.model_validate(raw_input)
        result = module.calculate(validated_input)
        if not isinstance(result, module.result_model):
            raise TypeError(f"模块 {module_id} 返回了错误的结果模型")
        result_data = result.model_dump(mode="json")
        input_original = validated_input.model_dump(mode="json")
        input_si = result_data.pop("input_si")
        assumptions = result_data.pop("assumptions")
        steps = result_data.pop("calculation_steps")
        warnings = result_data.pop("warnings")
        result_data.pop("module_id")
        result_data.pop("module_version")
        result_data.pop("calculation_model_version")
        status = result_data.pop("status")
        disclaimer = result_data.pop("disclaimer")
        calculation_id = str(uuid4())
        snapshot = {
            "calculation_id": calculation_id,
            "module_id": module.module_id,
            "module_version": module.module_version,
            "calculation_model_version": module.calculation_model_version,
            "report_template_version": module.report_template_version,
            "release_status": module.release_status,
            "status": status,
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "input_original": input_original,
            "input_si": input_si,
            "assumptions": assumptions,
            "results": result_data,
            "steps": steps,
            "warnings": warnings,
            "disclaimer": disclaimer,
            "snapshot_schema_version": 4,
            "links": {
                "self": f"/api/v1/calculations/{calculation_id}",
                "html_report": f"/calculations/{calculation_id}/report",
                "pdf": f"/api/v1/calculations/{calculation_id}/report.pdf",
            },
        }
        snapshot["report_context"] = module.build_report_context(snapshot).model_dump(mode="json")
        input_hash = _input_hash(input_si, module.calculation_model_version)
        self._repository.create(snapshot, input_hash, request_id)
        return snapshot

    def get(self, calculation_id: str) -> dict[str, Any] | None:
        return self._repository.get(calculation_id)


def _input_hash(input_si: dict[str, Any], model_version: str) -> str:
    canonical = json.dumps(
        {"calculation_model_version": model_version, "input_si": input_si},
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
