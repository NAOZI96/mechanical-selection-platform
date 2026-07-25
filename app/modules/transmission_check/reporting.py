"""Snapshot-only report mapping for transmission-chain results."""

from __future__ import annotations

from typing import Any

from app.modules.engineering_common import build_engineering_report_context
from app.reporting.models import ReportContext

from .calculator import MODULE_NAME

_INPUT_LABELS = {
    "basis_source_status": "计算依据来源状态",
    "basis_reference": "计算依据或数据版本",
    "input_speed_rpm": "输入转速（r/min）",
    "input_angular_speed_rad_s": "输入角速度（rad/s）",
    "input_torque_nm": "输入转矩（N·m）",
    "stages": "传动级参数",
    "candidate_rated_output_torque_nm": "候选额定输出转矩（N·m）",
    "candidate_source_status": "候选数据来源状态",
    "candidate_reference": "候选型号及额定值依据",
}

_RESULT_LABELS = {
    "total_ratio": "总传动比",
    "total_efficiency": "总正向效率",
    "input_power_w": "输入功率",
    "output_speed_rad_s": "输出角速度",
    "output_torque_nm": "输出转矩",
    "output_power_w": "输出功率",
    "candidate_torque_utilization": "候选额定转矩利用率",
    "candidate_torque_margin_nm": "候选额定转矩余量",
    "candidate_torque_satisfied": "候选额定转矩是否满足",
}

INPUT_LABELS = _INPUT_LABELS
RESULT_LABELS = _RESULT_LABELS

_UNCHECKED_LABELS = {
    "dynamic_and_peak_torque": "动态及峰值转矩",
    "load_spectrum_and_fatigue": "载荷谱与疲劳",
    "gear_belt_chain_strength": "齿轮、带或链强度",
    "shaft_coupling_key_strength": "轴、联轴器及键强度",
    "bearing_life": "轴承寿命",
    "thermal_capacity_and_lubrication": "热容量与润滑",
    "backdrive_and_braking": "反驱与制动",
    "torsional_vibration": "扭转振动",
    "standard_clause_confirmation": "适用标准条款确认",
    "manufacturer_application_approval": "制造商应用确认",
}

_ASSUMPTION_LABELS = {
    "calculation_basis": "计算依据",
    "ratio_definition": "传动比方向定义",
    "steady_power_flow": "稳态正向功率流",
}

UNCHECKED_LABELS = _UNCHECKED_LABELS
ASSUMPTION_LABELS = _ASSUMPTION_LABELS


def build_report_context(snapshot: dict[str, Any]) -> ReportContext:
    return build_engineering_report_context(
        snapshot,
        module_name=MODULE_NAME,
        input_labels=_INPUT_LABELS,
        result_labels=_RESULT_LABELS,
        unchecked_labels=_UNCHECKED_LABELS,
        assumption_labels=_ASSUMPTION_LABELS,
    )


build_transmission_check_report_context = build_report_context

__all__ = [
    "ASSUMPTION_LABELS",
    "INPUT_LABELS",
    "RESULT_LABELS",
    "UNCHECKED_LABELS",
    "build_report_context",
    "build_transmission_check_report_context",
]
