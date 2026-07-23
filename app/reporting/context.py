"""Pure snapshot-to-report mapping with no engineering recalculation."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

from .models import ReportContext, ReportInputRow, ReportResultRow

REPORT_CONTEXT_SCHEMA_VERSION = 2

_RESULT_LABELS = {
    "drum_rope_force_n": "换算后卷筒绳端拉力",
    "drum_rope_speed_m_s": "换算后卷筒绳速",
    "design_line_pull_n": "设计绳张力",
    "theoretical_load_power_w": "理论负载功率",
    "minimum_motor_power_w": "最低所需电机功率",
    "suggested_motor_power_w": "建议电机功率档位",
    "used_or_suggested_core_diameter_m": "采用或建议卷筒芯径",
    "used_or_suggested_drum_face_length_m": "采用或建议卷筒面长",
    "low_speed_brake_torque_nm": "低速轴静态制动力矩",
    "high_speed_brake_torque_ref_nm": "高速轴参考制动力矩",
    "ideal_load_force_n": "载荷端理想换算拉力",
    "ideal_load_speed_m_s": "载荷端理想换算速度",
}

_RAW_RESULT_ROWS = (
    ("capacity_satisfied", "目标容绳量是否满足", "", "calculated", ("CAP-006",)),
    ("actual_layers", "实际缠绕层数", "层", "calculated", ("CAP-006",)),
    ("evaluated_layers", "已校核层数", "层", "calculated", ()),
    ("capacity_at_actual_layers_m", "实际层容绳量", "m", "calculated", ("CAP-005",)),
    ("capacity_at_max_layers_m", "允许最大层容绳量", "m", "calculated", ("CAP-005",)),
    ("capacity_margin_m", "容绳余量", "m", "calculated", ("CAP-007",)),
    ("capacity_shortfall_m", "容绳缺口", "m", "calculated", ("CAP-007",)),
    ("empty_working_diameter_m", "空卷工作直径", "m", "calculated", ("SPEED-001",)),
    ("full_working_diameter_m", "满绳工作直径", "m", "calculated", ("SPEED-002",)),
    (
        "max_layer_working_diameter_m",
        "允许最大层工作直径",
        "m",
        "calculated",
        ("SPEED-002",),
    ),
    ("empty_drum_speed_rpm", "空卷目标转速", "r/min", "calculated", ("SPEED-004",)),
    ("full_drum_speed_rpm", "满绳目标转速", "r/min", "calculated", ("SPEED-005",)),
    (
        "max_layer_drum_speed_rpm",
        "允许最大层目标转速",
        "r/min",
        "calculated",
        ("SPEED-005",),
    ),
    ("reference_ratio_empty", "空卷参考速比", "", "preliminary", ("RATIO-001",)),
    ("reference_ratio_full", "满绳参考速比", "", "preliminary", ("RATIO-001",)),
    (
        "reference_ratio_max_layer",
        "允许最大层参考速比",
        "",
        "preliminary",
        ("RATIO-001",),
    ),
    ("reference_ratio_nominal", "名义参考速比", "", "preliminary", ("RATIO-002",)),
)


def build_report_context(
    snapshot: Mapping[str, Any],
    *,
    module_name: str,
) -> ReportContext:
    """Build the persisted DTO from one already-calculated immutable snapshot."""

    results = _mapping(snapshot, "results")
    result_rows: list[ReportResultRow] = []
    for key, item in results.items():
        if not isinstance(item, Mapping) or "classification" not in item:
            continue
        value = item.get("value")
        result_rows.append(
            ReportResultRow(
                key=key,
                label=_RESULT_LABELS.get(key, key),
                value=value,
                display_value=_display(value),
                unit=str(item.get("unit", "")),
                classification=str(item["classification"]),
                formula_ids=tuple(str(formula_id) for formula_id in item.get("formula_ids", ())),
                reason=None if item.get("reason") is None else str(item["reason"]),
            )
        )
    for key, label, unit, classification, formula_ids in _RAW_RESULT_ROWS:
        value = results.get(key)
        if value is None:
            continue
        reason = None
        if key.startswith(("max_layer_working_", "max_layer_drum_", "reference_ratio_max_")):
            reason = "目标容绳量未满足；此值对应允许最大层，不代表满绳状态。"
        result_rows.append(
            ReportResultRow(
                key=key,
                label=label,
                value=value,
                display_value=_display(value),
                unit=unit,
                classification=classification,
                formula_ids=formula_ids,
                reason=reason,
            )
        )

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
        original_inputs=_input_rows(_mapping(snapshot, "input_original")),
        si_inputs=_input_rows(_mapping(snapshot, "input_si")),
        result_rows=tuple(result_rows),
        layer_rows=tuple(dict(row) for row in results.get("layer_details", ())),
        steps=tuple(dict(row) for row in snapshot.get("steps", ())),
        assumptions=tuple(dict(row) for row in snapshot.get("assumptions", ())),
        warnings=tuple(dict(row) for row in snapshot.get("warnings", ())),
        unchecked_items=tuple(str(item) for item in results.get("unchecked_items", ())),
        disclaimer=str(snapshot["disclaimer"]),
    )


def _mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"报告快照缺少对象字段: {key}")
    return value


def _input_rows(values: Mapping[str, Any]) -> tuple[ReportInputRow, ...]:
    return tuple(
        ReportInputRow(
            key=str(key),
            label=str(key),
            value=value,
            display_value=_display(value),
        )
        for key, value in values.items()
    )


def _display(value: Any) -> str:
    if value is None:
        return "待确认"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("报告上下文禁止非有限数")
        return format(value, ".12g")
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
