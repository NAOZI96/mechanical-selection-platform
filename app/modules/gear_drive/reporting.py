"""Snapshot-only report mapping for spur-gear results."""

from __future__ import annotations

from typing import Any

from app.modules.engineering_common import build_engineering_report_context
from app.reporting.models import ReportContext

from .calculator import MODULE_NAME

_INPUT_LABELS = {
    "basis_source_status": "计算依据来源状态",
    "basis_reference": "计算依据或数据版本",
    "module_mm": "模数（mm）",
    "module_m": "模数（m）",
    "pinion_teeth": "小齿轮齿数",
    "gear_teeth": "大齿轮齿数",
    "pressure_angle_deg": "压力角（deg）",
    "pressure_angle_rad": "压力角（rad）",
    "input_speed_rpm": "小齿轮转速（r/min）",
    "input_angular_speed_rad_s": "小齿轮角速度（rad/s）",
    "input_torque_nm": "小齿轮输入转矩（N·m）",
    "mesh_efficiency": "啮合正向效率",
    "allowable_tangential_force_n": "制造商许用切向力（N）",
    "allowable_tangential_force_source_status": "许用切向力来源状态",
    "allowable_tangential_force_reference": "许用切向力依据",
    "maximum_pitch_line_speed_m_s": "制造商最大节线速度（m/s）",
    "maximum_pitch_line_speed_source_status": "最大节线速度来源状态",
    "maximum_pitch_line_speed_reference": "最大节线速度依据",
}

_RESULT_LABELS = {
    "pinion_pitch_diameter_m": "小齿轮节圆直径",
    "gear_pitch_diameter_m": "大齿轮节圆直径",
    "center_distance_m": "中心距",
    "transmission_ratio": "传动比",
    "tangential_force_n": "名义切向力",
    "radial_force_n": "名义径向力",
    "pitch_line_speed_m_s": "节线速度",
    "output_speed_rad_s": "输出角速度",
    "output_torque_nm": "输出转矩",
    "output_power_w": "输出功率",
    "tangential_force_utilization": "许用切向力利用率",
    "tangential_force_satisfied": "许用切向力是否满足",
    "pitch_line_speed_utilization": "最大节线速度利用率",
    "pitch_line_speed_satisfied": "最大节线速度是否满足",
}

INPUT_LABELS = _INPUT_LABELS
RESULT_LABELS = _RESULT_LABELS

_UNCHECKED_LABELS = {
    "tooth_root_bending_strength": "齿根弯曲强度",
    "tooth_contact_strength": "齿面接触强度",
    "scuffing_pitting_and_wear": "胶合、点蚀与磨损",
    "materials_and_heat_treatment": "材料与热处理",
    "face_width_and_load_distribution": "齿宽与载荷分布",
    "dynamic_load_and_accuracy_grade": "动载与精度等级",
    "profile_shift_backlash_and_modification": "变位、侧隙与修形",
    "lubrication_and_thermal_balance": "润滑与热平衡",
    "shaft_bearing_and_housing": "轴、轴承与箱体",
    "standard_clause_confirmation": "适用标准条款确认",
    "manufacturer_application_approval": "制造商应用确认",
}

_ASSUMPTION_LABELS = {
    "calculation_basis": "计算依据",
    "gear_mesh_type": "齿轮啮合类型",
    "mesh_efficiency": "啮合正向效率",
    "allowable_tangential_force": "候选许用切向力",
    "maximum_pitch_line_speed": "候选最大节线速度",
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


build_gear_drive_report_context = build_report_context

__all__ = [
    "ASSUMPTION_LABELS",
    "INPUT_LABELS",
    "RESULT_LABELS",
    "UNCHECKED_LABELS",
    "build_gear_drive_report_context",
    "build_report_context",
]
