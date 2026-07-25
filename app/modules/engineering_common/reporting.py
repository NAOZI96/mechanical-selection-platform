"""Snapshot-only report mapping for non-winch engineering modules."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Any

from app.reporting.models import ReportContext, ReportInputRow, ReportResultRow

REPORT_CONTEXT_SCHEMA_VERSION = 3

_CLASSIFICATION_LABELS = {
    "calculated": "理论计算值",
    "preliminary": "初选值",
    "review_required": "待校核值",
    "informational": "信息值",
}

_STATUS_LABELS = {
    "completed": "计算完成",
    "completed_with_warnings": "计算完成（有警告）",
}

_SOURCE_STATUS_LABELS = {
    "user_input": "用户输入",
    "project_setting": "项目设定",
    "standard_confirmed": "标准已确认",
    "manufacturer_data": "制造商数据",
    "pending_confirmation": "待确认",
}

_SEVERITY_LABELS = {
    "info": "提示",
    "warning": "警告",
    "high": "高风险",
    "blocking": "阻断",
}

_UNIT_LABELS = {
    "N*m": "N·m",
    "N*m^2": "N·m²",
    "kg*m^2": "kg·m²",
    "rad/s": "rad/s",
    "rad/s^2": "rad/s²",
    "rev/min": "r/min",
    "rpm": "r/min",
    "m3": "m³",
    "m3/min": "m³/min",
    "m^2": "m²",
    "m^3": "m³",
    "m^3/min": "m³/min",
    "m4": "m⁴",
    "10^6 rev": "10⁶ r",
}


def build_engineering_report_context(
    snapshot: Mapping[str, Any],
    module_name: str,
    input_labels: Mapping[str, str],
    result_labels: Mapping[str, str],
    unchecked_labels: Mapping[str, str] | None = None,
    assumption_labels: Mapping[str, str] | None = None,
) -> ReportContext:
    """Materialize a report from one saved snapshot without recalculation."""

    results = _mapping(snapshot, "results")
    result_rows: list[ReportResultRow] = []
    for key, item in results.items():
        if not isinstance(item, Mapping) or "classification" not in item:
            continue
        classification = str(item["classification"])
        value = item.get("value")
        result_rows.append(
            ReportResultRow(
                key=str(key),
                label=result_labels.get(str(key), str(key)),
                value=value,
                display_value=_display(value),
                unit=_UNIT_LABELS.get(str(item.get("unit", "")), str(item.get("unit", ""))),
                classification=classification,
                classification_label=_CLASSIFICATION_LABELS.get(classification, classification),
                formula_ids=tuple(str(formula_id) for formula_id in item.get("formula_ids", ())),
                reason=None if item.get("reason") is None else str(item["reason"]),
            )
        )

    original_inputs = _input_rows(_mapping(snapshot, "input_original"), input_labels)
    si_inputs = _input_rows(_mapping(snapshot, "input_si"), input_labels)
    steps = tuple(_formula_row(row) for row in snapshot.get("steps", ()))
    assumptions = tuple(_assumption_row(row, assumption_labels or {}) for row in snapshot.get("assumptions", ()))
    warnings = tuple(_warning_row(row) for row in snapshot.get("warnings", ()))
    unchecked_map = unchecked_labels or {}
    unchecked = tuple(unchecked_map.get(str(item), str(item)) for item in results.get("unchecked_items", ()))

    return ReportContext(
        schema_version=REPORT_CONTEXT_SCHEMA_VERSION,
        title=f"{module_name}计算报告",
        calculation_id=str(snapshot["calculation_id"]),
        module_id=str(snapshot["module_id"]),
        module_name=module_name,
        module_version=str(snapshot["module_version"]),
        calculation_model_version=str(snapshot["calculation_model_version"]),
        report_template_version=str(snapshot["report_template_version"]),
        calculation_created_at=str(snapshot["created_at"]),
        status=str(snapshot["status"]),
        status_label=_STATUS_LABELS.get(str(snapshot["status"]), str(snapshot["status"])),
        original_inputs=original_inputs,
        si_inputs=si_inputs,
        result_rows=tuple(result_rows),
        layer_rows=(),
        steps=steps,
        assumptions=assumptions,
        warnings=warnings,
        unchecked_items=unchecked,
        disclaimer=str(snapshot["disclaimer"]),
    )


def _mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"报告快照缺少对象字段: {key}")
    return value


def _input_rows(values: Mapping[str, Any], labels: Mapping[str, str]) -> tuple[ReportInputRow, ...]:
    return tuple(
        ReportInputRow(
            key=str(key),
            label=labels.get(str(key), str(key)),
            value=value,
            display_value=_display(value),
        )
        for key, value in values.items()
    )


def _formula_row(source: Any) -> dict[str, Any]:
    row = dict(source)
    formula_id = str(row.get("formula_id", ""))
    row["group_label"] = _formula_group_label(formula_id)
    row["expression_display"] = str(row.get("expression", ""))
    variables = row.get("variables", {})
    row["variables_display"] = (
        tuple({"label": str(name), "value": _display(value)} for name, value in variables.items())
        if isinstance(variables, Mapping)
        else ()
    )
    row["result_display"] = _display(row.get("result_value"))
    row["unit_display"] = _UNIT_LABELS.get(str(row.get("unit", "")), str(row.get("unit", "")))
    classification = str(row.get("classification", ""))
    row["classification_label"] = _CLASSIFICATION_LABELS.get(classification, classification)
    return row


def _assumption_row(source: Any, labels: Mapping[str, str]) -> dict[str, Any]:
    row = dict(source)
    key = str(row.get("key", ""))
    source_status = str(row.get("source_status", ""))
    row["key_display"] = labels.get(key, _dynamic_assumption_label(key))
    row["source_status_display"] = _SOURCE_STATUS_LABELS.get(source_status, source_status)
    row["value_display"] = _display(row.get("value"))
    row["unit_display"] = _UNIT_LABELS.get(str(row.get("unit") or ""), str(row.get("unit") or ""))
    return row


def _dynamic_assumption_label(key: str) -> str:
    stage_parameter = re.fullmatch(r"stage_(\d+)_(ratio|efficiency)", key)
    if stage_parameter is None:
        return key
    stage_number, parameter = stage_parameter.groups()
    parameter_label = "传动比" if parameter == "ratio" else "正向效率"
    return f"第 {stage_number} 级{parameter_label}"


def _warning_row(source: Any) -> dict[str, Any]:
    row = dict(source)
    severity = str(row.get("severity", ""))
    row["severity_label"] = _SEVERITY_LABELS.get(severity, severity)
    return row


def _formula_group_label(formula_id: str) -> str:
    prefix = formula_id.partition("-")[0].rsplit("_", 1)[-1]
    labels = {
        "UNIT": "单位换算",
        "KIN": "运动学",
        "POWER": "功率",
        "TORQUE": "转矩",
        "GEOM": "几何",
        "FORCE": "载荷与力",
        "LIFE": "寿命",
        "STRESS": "应力",
        "BUCKLING": "稳定性",
        "INERTIA": "惯量",
        "PRESSURE": "压力",
        "AIR": "耗气量",
        "CHECK": "候选校核",
    }
    return labels.get(prefix, prefix or "公式")


def _display(value: Any) -> str:
    if value is None:
        return "待校核"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("报告值必须为有限数")
        if value == 0:
            return "0"
        magnitude = abs(value)
        if magnitude >= 1.0e8 or magnitude < 1.0e-5:
            return f"{value:.8e}"
        return f"{value:.10g}"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
