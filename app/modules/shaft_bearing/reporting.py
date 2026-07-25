"""Snapshot-only report mapping for shaft and bearing results."""

from __future__ import annotations

from typing import Any

from app.modules.engineering_common import build_engineering_report_context
from app.reporting.models import ReportContext

from .calculator import MODULE_NAME

_INPUT_LABELS = {
    "basis_source_status": "计算依据来源状态",
    "basis_reference": "计算依据或数据版本",
    "bearing_radial_load_n": "轴承径向载荷 Fr（N）",
    "bearing_axial_load_n": "轴承轴向载荷 Fa（N）",
    "bearing_speed_rpm": "轴承转速（r/min）",
    "bearing_angular_speed_rad_s": "轴承角速度（rad/s）",
    "basic_dynamic_load_rating_n": "基本额定动载荷 C（N）",
    "dynamic_rating_source_status": "C 来源状态",
    "dynamic_rating_reference": "C 型号及依据",
    "radial_factor_x": "径向载荷系数 X",
    "radial_factor_x_source_status": "X 来源状态",
    "radial_factor_x_reference": "X 选取依据",
    "axial_factor_y": "轴向载荷系数 Y",
    "axial_factor_y_source_status": "Y 来源状态",
    "axial_factor_y_reference": "Y 选取依据",
    "life_exponent_p": "寿命指数 p",
    "life_exponent_source_status": "p 来源状态",
    "life_exponent_reference": "p 选取依据",
    "shaft_diameter_mm": "实心圆轴直径（mm）",
    "shaft_diameter_m": "实心圆轴直径（m）",
    "shaft_bending_moment_nm": "轴截面弯矩（N·m）",
    "shaft_torque_nm": "轴截面扭矩（N·m）",
    "allowable_von_mises_stress_mpa": "候选许用应力（MPa）",
    "allowable_von_mises_stress_pa": "候选许用应力（Pa）",
    "allowable_stress_source_status": "许用应力来源状态",
    "allowable_stress_reference": "许用应力依据",
}

_RESULT_LABELS = {
    "equivalent_dynamic_load_n": "轴承当量动载荷",
    "bearing_l10_million_revolutions": "轴承基本额定寿命 L10",
    "bearing_l10_life_hours": "轴承基本额定寿命（小时）",
    "shaft_bending_stress_pa": "轴名义弯曲应力",
    "shaft_torsional_shear_stress_pa": "轴名义扭转剪应力",
    "shaft_von_mises_stress_pa": "轴名义 von Mises 应力",
    "allowable_stress_utilization": "候选许用应力利用率",
    "allowable_stress_margin_pa": "候选许用应力余量",
    "allowable_stress_satisfied": "候选许用应力是否满足",
}

INPUT_LABELS = _INPUT_LABELS
RESULT_LABELS = _RESULT_LABELS

_UNCHECKED_LABELS = {
    "bearing_static_safety": "轴承静安全",
    "bearing_reliability_adjustment": "轴承可靠度修正",
    "lubrication_contamination_and_temperature": "润滑、污染与温度",
    "bearing_clearance_fit_and_misalignment": "轴承游隙、配合与不对中",
    "variable_load_spectrum": "变载荷谱",
    "shaft_fatigue_and_stress_concentration": "轴疲劳与应力集中",
    "keyway_step_fillet_and_fit": "键槽、台阶、圆角与配合",
    "shaft_deflection_and_alignment": "轴挠度与对中",
    "critical_speed_and_vibration": "临界转速与振动",
    "material_surface_and_size_effects": "材料、表面与尺寸效应",
    "standard_clause_confirmation": "适用标准条款确认",
    "manufacturer_application_approval": "制造商应用确认",
}

_ASSUMPTION_LABELS = {
    "calculation_basis": "计算依据",
    "bearing_dynamic_rating_c": "轴承基本额定动载荷 C",
    "bearing_radial_factor_x": "径向载荷系数 X",
    "bearing_axial_factor_y": "轴向载荷系数 Y",
    "bearing_life_exponent_p": "寿命指数 p",
    "solid_circular_shaft_nominal_stress": "实心圆轴名义应力模型",
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


build_shaft_bearing_report_context = build_report_context

__all__ = [
    "ASSUMPTION_LABELS",
    "INPUT_LABELS",
    "RESULT_LABELS",
    "UNCHECKED_LABELS",
    "build_report_context",
    "build_shaft_bearing_report_context",
]
