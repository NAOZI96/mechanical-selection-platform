"""Pure snapshot-to-report mapping with no engineering recalculation."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Any

from .models import ReportContext, ReportInputRow, ReportResultRow

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
    "failed": "计算失败",
}

_SOURCE_STATUS_LABELS = {
    "project_default": "项目设定",
    "user_input": "用户输入",
    "standard_confirmed": "标准已确认",
    "manufacturer_data": "制造商数据",
    "pending_confirmation": "待确认",
}

_INPUT_LABELS = {
    "rated_line_pull_kn": "输入拉力（kN）",
    "rated_line_pull_n": "输入拉力（N）",
    "rope_diameter_mm": "绳索直径（mm）",
    "rope_diameter_m": "绳索直径（m）",
    "rope_speed_m_per_min": "输入绳速（m/min）",
    "rope_speed_m_s": "输入绳速（m/s）",
    "target_rope_capacity_m": "目标有效工作绳长（m）",
    "force_input_location": "拉力输入位置",
    "speed_input_location": "速度输入位置",
    "force_input_type": "拉力类型",
    "service_factor": "使用系数 Ks",
    "total_efficiency": "传动总效率",
    "motor_rated_speed_rpm": "电机额定转速（r/min）",
    "motor_angular_speed_rad_s": "电机角速度（rad/s）",
    "motor_type": "电机类型",
    "drum_core_diameter_mm": "卷筒芯径（mm）",
    "drum_core_diameter_m": "卷筒芯径（m）",
    "drum_face_length_mm": "卷筒面长（mm）",
    "drum_face_length_m": "卷筒面长（m）",
    "max_layers": "最大缠绕层数",
    "pitch_factor": "排绳节距系数 Kp",
    "side_margin_mm": "单侧余量（mm）",
    "side_margin_m": "单侧余量（m）",
    "reeving_ratio": "滑轮倍率",
    "pulley_efficiency": "滑轮效率",
    "actual_groove_pitch_mm": "实际槽距（mm）",
    "actual_groove_pitch_m": "实际槽距（m）",
    "actual_usable_groove_count": "实际可用槽数",
    "brake_safety_factor": "制动安全系数 Kb",
    "duty_class": "工作级别或工况说明",
    "approved_core_ratio": "已批准 D/d 比",
    "minimum_dd_ratio": "项目初选 D/d 比",
    "dead_wrap_count": "固定死圈数",
    "termination_allowance_m": "绳端安装预留（m）",
    "rope_type": "绳索类型",
    "rope_construction": "绳索结构",
    "rope_material": "绳索材料",
    "load_spectrum": "载荷谱说明",
    "environment_type": "环境类型",
    "brake_basis_type": "制动计算基准",
    "brake_installation_shaft": "制动器安装轴",
    "backdrive_efficiency": "反向效率",
    "transmission_backdrive_type": "传动反驱类型",
    "allow_forward_efficiency_as_reverse_approx": "允许正向效率近似反向效率",
    "motor_duty_type": "电机工作制",
    "duty_cycle_percent": "负载持续率（%）",
    "starts_per_hour": "每小时启动次数",
    "supply_voltage": "供电电压（V）",
    "supply_frequency": "供电频率（Hz）",
    "motor_power_series_id": "电机功率系列",
    "assumption_sources": "参数来源状态",
    "location": "输入位置",
}

_ENUM_VALUE_LABELS = {
    "load_end": "载荷端",
    "drum_rope_end": "卷筒绳端",
    "rated": "额定拉力",
    "design": "设计拉力",
    "maximum": "最大拉力",
    "design_force": "设计绳张力",
    "drum_or_low_speed": "卷筒轴或低速轴",
    "high_speed": "高速轴",
    "reversible": "允许反驱",
    "self_locking": "自锁传动",
    "worm": "蜗杆传动",
    "non_reversible": "不可逆传动",
    "backdrive_prohibited": "禁止反驱",
    "project_default_iec_kw": "项目设定 IEC kW 档位表",
    **_SOURCE_STATUS_LABELS,
}

_ENUM_DISPLAY_FIELDS = {
    "force_input_location",
    "speed_input_location",
    "force_input_type",
    "brake_basis_type",
    "brake_installation_shaft",
    "transmission_backdrive_type",
    "motor_power_series_id",
    "location",
}

_ASSUMPTION_LABELS = {
    "force_and_speed_basis": "拉力与速度换算基准",
    "service_factor": "使用系数",
    "pitch_factor": "排绳节距系数",
    "brake_safety_factor": "制动安全系数",
    "brake_basis_type": "制动计算基准",
    "dead_wraps": "固定死圈",
    "regular_level_winding": "规则排绳假设",
    "geometry_optimizer": "几何初选器",
    "reverse_efficiency_approximation": "反向效率近似",
    "backdrive_efficiency": "反向效率",
    "pulley_efficiency": "滑轮效率",
    "minimum_dd_ratio": "项目初选 D/d 比",
    "motor_power_series_id": "电机功率系列",
}

_UNCHECKED_LABELS = {
    "rope_strength": "绳索强度",
    "rope_termination_strength": "绳端连接强度",
    "drum_structure_strength": "卷筒结构强度",
    "dynamic_braking": "动态制动",
    "emergency_braking": "应急制动",
    "brake_thermal_capacity": "制动器热容量",
    "motor_starting_torque": "电机启动转矩",
    "motor_thermal_capacity": "电机热容量",
    "manufacturer_confirmation": "制造商确认",
    "standard_clause_confirmation": "适用标准条款确认",
}

_FORMULA_GROUP_LABELS = {
    "UNIT": "单位换算",
    "REEVE": "滑轮组换算",
    "FORCE": "设计拉力",
    "POWER": "功率",
    "GEOM": "卷筒几何",
    "DRUM": "卷筒初选",
    "WIDTH": "卷筒面长",
    "CAP": "逐层容绳量",
    "SPEED": "卷筒转速",
    "RATIO": "参考速比",
    "BRAKE": "静态制动",
}

_UNIT_LABELS = {
    "N*m": "N·m",
    "layer": "层",
    "turn": "圈",
    "m/turn": "m/圈",
    "ratio": "无量纲",
}

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
                unit=_unit_label(item.get("unit", "")),
                classification=str(item["classification"]),
                classification_label=_CLASSIFICATION_LABELS.get(
                    str(item["classification"]),
                    str(item["classification"]),
                ),
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
                unit=_unit_label(unit),
                classification=classification,
                classification_label=_CLASSIFICATION_LABELS.get(classification, classification),
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
        status_label=_STATUS_LABELS.get(str(snapshot["status"]), str(snapshot["status"])),
        original_inputs=_input_rows(_mapping(snapshot, "input_original")),
        si_inputs=_input_rows(_mapping(snapshot, "input_si")),
        result_rows=tuple(result_rows),
        layer_rows=tuple(dict(row) for row in results.get("layer_details", ())),
        steps=_formula_rows(snapshot.get("steps", ())),
        assumptions=_assumption_rows(snapshot.get("assumptions", ())),
        warnings=_warning_rows(snapshot.get("warnings", ())),
        unchecked_items=tuple(
            _UNCHECKED_LABELS.get(str(item), str(item)) for item in results.get("unchecked_items", ())
        ),
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
            label=_INPUT_LABELS.get(str(key), str(key)),
            value=value,
            display_value=_display(value, key=str(key)),
        )
        for key, value in values.items()
    )


def _formula_rows(rows: Any) -> tuple[dict[str, Any], ...]:
    formatted: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        formula_id = str(row.get("formula_id", ""))
        row["group_label"] = _FORMULA_GROUP_LABELS.get(formula_id.partition("-")[0], "公式")
        row["expression_display"] = _formula_expression(str(row.get("expression", "")))
        variables = row.get("variables", {})
        row["variables_display"] = (
            tuple(
                {
                    "label": _formula_variable_label(str(name)),
                    "value": _display(value, key=str(name)),
                }
                for name, value in variables.items()
            )
            if isinstance(variables, Mapping)
            else ()
        )
        row["result_display"] = _display(row.get("result_value"))
        row["unit_display"] = _unit_label(row.get("unit", ""))
        classification = str(row.get("classification", ""))
        row["classification_label"] = _CLASSIFICATION_LABELS.get(classification, classification)
        formatted.append(row)
    return tuple(formatted)


def _assumption_rows(rows: Any) -> tuple[dict[str, Any], ...]:
    formatted: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        key = str(row.get("key", ""))
        source_status = str(row.get("source_status", ""))
        row["key_display"] = _ASSUMPTION_LABELS.get(key, _INPUT_LABELS.get(key, key))
        row["source_status_display"] = _SOURCE_STATUS_LABELS.get(source_status, source_status)
        row["value_display"] = _display(row.get("value"), key=key)
        row["unit_display"] = "圈" if row.get("unit") == "turn" else str(row.get("unit") or "")
        formatted.append(row)
    return tuple(formatted)


def _warning_rows(rows: Any) -> tuple[dict[str, Any], ...]:
    severity_labels = {
        "info": "提示",
        "warning": "警告",
        "high": "高风险",
        "blocking": "阻断",
    }
    formatted: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        severity = str(row.get("severity", ""))
        row["severity_label"] = severity_labels.get(severity, severity)
        formatted.append(row)
    return tuple(formatted)


def _formula_expression(expression: str) -> str:
    if expression == "z_actual = min(k where L_total,k >= L_t)":
        return "z_actual = 满足 L_total,k ≥ L_t 的最小 k"
    formatted = expression.replace(
        " when input is at load end",
        "（载荷端输入时）",
    )
    formatted = formatted.replace("sqrt", "√").replace("pi", "π").replace("eta", "η")
    formatted = formatted.replace("floor", "向下取整").replace("sum", "求和")
    formatted = formatted.replace(">=", "≥").replace("<=", "≤")
    formatted = formatted.replace("*", " × ").replace("/", " ÷ ")
    return re.sub(r"\s+", " ", formatted).strip()


def _formula_variable_label(key: str) -> str:
    if key in _INPUT_LABELS:
        return _INPUT_LABELS[key]
    return key.replace("eta_", "η_").replace("epsilon", "ε").replace("pi", "π")


def _display(value: Any, *, key: str | None = None) -> str:
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
        if key == "force_and_speed_basis" and "/" in value:
            return " / ".join(_ENUM_VALUE_LABELS.get(part, part) for part in value.split("/"))
        if key in _ENUM_DISPLAY_FIELDS:
            return _ENUM_VALUE_LABELS.get(value, value)
        return value
    if isinstance(value, Mapping):
        if key == "assumption_sources":
            return "；".join(
                f"{_INPUT_LABELS.get(str(item_key), str(item_key))}："
                f"{_SOURCE_STATUS_LABELS.get(str(item_value), str(item_value))}"
                for item_key, item_value in value.items()
            )
        return "；".join(
            f"{_INPUT_LABELS.get(str(item_key), str(item_key))}：{_display(item_value, key=str(item_key))}"
            for item_key, item_value in value.items()
        )
    if isinstance(value, (list, tuple)):
        return "、".join(_display(item) for item in value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _unit_label(value: Any) -> str:
    raw = "" if value is None else str(value)
    return _UNIT_LABELS.get(raw, raw)
