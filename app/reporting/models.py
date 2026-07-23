"""Immutable report data-transfer objects shared by HTML and PDF renderers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ReportInputRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    key: str
    label: str
    value: Any
    display_value: str


class ReportResultRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    key: str
    label: str
    value: float | int | bool | str | None
    display_value: str
    unit: str
    classification: str
    formula_ids: tuple[str, ...]
    reason: str | None = None


class ReportContext(BaseModel):
    """Stable, fully materialized context persisted with each calculation."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: int
    title: str
    calculation_id: str
    module_id: str
    module_name: str
    module_version: str
    calculation_model_version: str
    report_template_version: str
    calculation_created_at: str
    status: str
    original_inputs: tuple[ReportInputRow, ...]
    si_inputs: tuple[ReportInputRow, ...]
    result_rows: tuple[ReportResultRow, ...]
    layer_rows: tuple[dict[str, Any], ...]
    steps: tuple[dict[str, Any], ...]
    assumptions: tuple[dict[str, Any], ...]
    warnings: tuple[dict[str, Any], ...]
    unchecked_items: tuple[str, ...]
    disclaimer: str
