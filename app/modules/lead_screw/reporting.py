"""Snapshot-only report mapping for lead-screw results."""

from __future__ import annotations

from typing import Any

from app.modules.engineering_common import build_engineering_report_context
from app.reporting.models import ReportContext

from .calculator import MODULE_NAME

_INPUT_LABELS = {
    "basis_source_status": "计算依据来源状态",
    "basis_reference": "计算依据或数据版本",
    "axial_force_n": "轴向载荷（N）",
    "mean_thread_diameter_mm": "等效螺纹中径（mm）",
    "mean_thread_diameter_m": "等效螺纹中径（m）",
    "root_diameter_mm": "螺纹根径（mm）",
    "root_diameter_m": "螺纹根径（m）",
    "lead_mm_per_revolution": "导程（mm/rev）",
    "lead_m_per_revolution": "导程（m/rev）",
    "friction_coefficient": "螺纹摩擦系数",
    "friction_source_status": "摩擦系数来源状态",
    "friction_reference": "摩擦系数依据",
    "rotational_speed_rpm": "丝杠转速（r/min）",
    "angular_speed_rad_s": "丝杠角速度（rad/s）",
    "youngs_modulus_gpa": "弹性模量（GPa）",
    "youngs_modulus_pa": "弹性模量（Pa）",
    "youngs_modulus_source_status": "弹性模量来源状态",
    "youngs_modulus_reference": "弹性模量依据",
    "unsupported_length_mm": "受压无支撑长度（mm）",
    "unsupported_length_m": "受压无支撑长度（m）",
    "effective_length_factor": "有效长度系数 K",
    "effective_length_factor_source_status": "有效长度系数来源状态",
    "effective_length_factor_reference": "有效长度系数依据",
    "candidate_allowable_axial_load_n": "候选产品许用轴向载荷（N）",
    "candidate_source_status": "候选数据来源状态",
    "candidate_reference": "候选型号及许用载荷依据",
}

_RESULT_LABELS = {
    "lead_angle_rad": "导程角",
    "raising_torque_nm": "提升转矩",
    "lowering_torque_nm": "下降保持转矩",
    "raising_efficiency": "提升效率",
    "linear_speed_m_s": "直线速度",
    "raising_input_power_w": "提升输入功率",
    "self_locking": "等效螺纹是否自锁",
    "root_second_moment_area_m4": "根径截面惯性矩",
    "euler_critical_load_n": "Euler 理论临界载荷",
    "buckling_utilization": "Euler 临界载荷利用率",
    "euler_buckling_satisfied": "Euler 理论校核是否满足",
    "candidate_axial_load_utilization": "候选许用轴向载荷利用率",
    "candidate_axial_load_margin_n": "候选许用轴向载荷余量",
    "candidate_axial_load_satisfied": "候选许用轴向载荷是否满足",
}

INPUT_LABELS = _INPUT_LABELS
RESULT_LABELS = _RESULT_LABELS

_UNCHECKED_LABELS = {
    "actual_thread_form_correction": "实际牙型修正",
    "collar_and_thrust_bearing_friction": "止推端面或轴承摩擦",
    "thread_and_nut_strength": "螺纹与螺母强度",
    "contact_pressure_and_wear": "接触压强与磨损",
    "pv_limit_lubrication_and_thermal": "PV 限值、润滑与热",
    "fatigue_and_duty_cycle": "疲劳与工作制",
    "critical_speed_and_whirl": "临界转速与甩动",
    "euler_slenderness_and_initial_imperfection": "Euler 细长比与初始缺陷",
    "buckling_safety_factor_and_standard_clause": "屈曲安全系数与标准条款",
    "mounting_alignment_and_lateral_load": "安装对中与侧向载荷",
    "manufacturer_application_approval": "制造商应用确认",
}

_ASSUMPTION_LABELS = {
    "calculation_basis": "计算依据",
    "equivalent_square_thread": "等效方牙模型",
    "thread_friction_coefficient": "螺纹摩擦系数",
    "youngs_modulus": "弹性模量",
    "effective_length_factor": "有效长度系数",
    "euler_centered_elastic_column": "Euler 轴心弹性直杆模型",
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


build_lead_screw_report_context = build_report_context

__all__ = [
    "ASSUMPTION_LABELS",
    "INPUT_LABELS",
    "RESULT_LABELS",
    "UNCHECKED_LABELS",
    "build_lead_screw_report_context",
    "build_report_context",
]
