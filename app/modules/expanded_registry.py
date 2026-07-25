"""Registration metadata for the eight controlled engineering worksheets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.reporting.models import ReportContext

from . import (
    gear_drive,
    lead_screw,
    motor_drive,
    pneumatic_cylinder,
    shaft_bearing,
    stepper_motor,
    synchronous_belt,
    transmission_check,
)
from .gear_drive.reporting import (
    ASSUMPTION_LABELS as GEAR_ASSUMPTION_LABELS,
)
from .gear_drive.reporting import (
    INPUT_LABELS as GEAR_INPUT_LABELS,
)
from .gear_drive.reporting import (
    RESULT_LABELS as GEAR_RESULT_LABELS,
)
from .gear_drive.reporting import (
    UNCHECKED_LABELS as GEAR_UNCHECKED_LABELS,
)
from .lead_screw.reporting import (
    ASSUMPTION_LABELS as LEAD_SCREW_ASSUMPTION_LABELS,
)
from .lead_screw.reporting import (
    INPUT_LABELS as LEAD_SCREW_INPUT_LABELS,
)
from .lead_screw.reporting import (
    RESULT_LABELS as LEAD_SCREW_RESULT_LABELS,
)
from .lead_screw.reporting import (
    UNCHECKED_LABELS as LEAD_SCREW_UNCHECKED_LABELS,
)
from .motor_drive.constants import (
    ASSUMPTION_LABELS as MOTOR_ASSUMPTION_LABELS,
)
from .motor_drive.constants import (
    INPUT_LABELS as MOTOR_INPUT_LABELS,
)
from .motor_drive.constants import (
    RESULT_LABELS as MOTOR_RESULT_LABELS,
)
from .motor_drive.constants import (
    UNCHECKED_LABELS as MOTOR_UNCHECKED_LABELS,
)
from .pneumatic_cylinder.constants import (
    ASSUMPTION_LABELS as CYLINDER_ASSUMPTION_LABELS,
)
from .pneumatic_cylinder.constants import (
    INPUT_LABELS as CYLINDER_INPUT_LABELS,
)
from .pneumatic_cylinder.constants import (
    RESULT_LABELS as CYLINDER_RESULT_LABELS,
)
from .pneumatic_cylinder.constants import (
    UNCHECKED_LABELS as CYLINDER_UNCHECKED_LABELS,
)
from .shaft_bearing.reporting import (
    ASSUMPTION_LABELS as SHAFT_BEARING_ASSUMPTION_LABELS,
)
from .shaft_bearing.reporting import (
    INPUT_LABELS as SHAFT_BEARING_INPUT_LABELS,
)
from .shaft_bearing.reporting import (
    RESULT_LABELS as SHAFT_BEARING_RESULT_LABELS,
)
from .shaft_bearing.reporting import (
    UNCHECKED_LABELS as SHAFT_BEARING_UNCHECKED_LABELS,
)
from .stepper_motor.constants import (
    ASSUMPTION_LABELS as STEPPER_ASSUMPTION_LABELS,
)
from .stepper_motor.constants import (
    INPUT_LABELS as STEPPER_INPUT_LABELS,
)
from .stepper_motor.constants import (
    RESULT_LABELS as STEPPER_RESULT_LABELS,
)
from .stepper_motor.constants import (
    UNCHECKED_LABELS as STEPPER_UNCHECKED_LABELS,
)
from .synchronous_belt.constants import (
    ASSUMPTION_LABELS as BELT_ASSUMPTION_LABELS,
)
from .synchronous_belt.constants import (
    INPUT_LABELS as BELT_INPUT_LABELS,
)
from .synchronous_belt.constants import (
    RESULT_LABELS as BELT_RESULT_LABELS,
)
from .synchronous_belt.constants import (
    UNCHECKED_LABELS as BELT_UNCHECKED_LABELS,
)
from .transmission_check.reporting import (
    ASSUMPTION_LABELS as TRANSMISSION_ASSUMPTION_LABELS,
)
from .transmission_check.reporting import (
    INPUT_LABELS as TRANSMISSION_INPUT_LABELS,
)
from .transmission_check.reporting import (
    RESULT_LABELS as TRANSMISSION_RESULT_LABELS,
)
from .transmission_check.reporting import (
    UNCHECKED_LABELS as TRANSMISSION_UNCHECKED_LABELS,
)


@dataclass(frozen=True)
class ExpandedModuleSpec:
    """Registry-ready metadata without a dependency on the central registry type."""

    module_id: str
    module_name: str
    module_version: str
    calculation_model_version: str
    report_template_version: str
    input_model: type[BaseModel]
    result_model: type[BaseModel]
    calculate: Callable[[Any], BaseModel]
    build_report_context: Callable[[dict[str, Any]], ReportContext]
    summary: str
    category: str
    icon_key: str
    capabilities: tuple[str, ...]
    catalog_order: int
    input_labels: tuple[tuple[str, str], ...]
    result_labels: tuple[tuple[str, str], ...]
    unchecked_labels: tuple[tuple[str, str], ...]
    assumption_labels: tuple[tuple[str, str], ...]
    example_input: tuple[tuple[str, object], ...]


def _label_pairs(values: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(values.items())


EXPANDED_MODULE_SPECS: tuple[ExpandedModuleSpec, ...] = (
    ExpandedModuleSpec(
        module_id=transmission_check.MODULE_ID,
        module_name=transmission_check.MODULE_NAME,
        module_version=transmission_check.MODULE_VERSION,
        calculation_model_version=transmission_check.CALCULATION_MODEL_VERSION,
        report_template_version=transmission_check.REPORT_TEMPLATE_VERSION,
        input_model=transmission_check.Input,
        result_model=transmission_check.Result,
        calculate=transmission_check.calculate,
        build_report_context=transmission_check.build_report_context,
        summary="核算 1～4 级正向稳态传动链的速比、效率、转速、转矩、功率与候选额定转矩。",
        category="传动系统",
        icon_key="transmission",
        capabilities=("1～4 级传动链", "逐级功率审计", "候选额定转矩校核", "HTML / PDF 报告"),
        catalog_order=20,
        input_labels=_label_pairs(TRANSMISSION_INPUT_LABELS),
        result_labels=_label_pairs(TRANSMISSION_RESULT_LABELS),
        unchecked_labels=_label_pairs(TRANSMISSION_UNCHECKED_LABELS),
        assumption_labels=_label_pairs(TRANSMISSION_ASSUMPTION_LABELS),
        example_input=(
            ("basis_source_status", "user_input"),
            ("basis_reference", "验证算例 TC-A-001（非项目参数）"),
            ("input_speed_rpm", 1500.0),
            ("input_torque_nm", 100.0),
            (
                "stages",
                (
                    {
                        "stage_name": "一级",
                        "ratio": 3.0,
                        "efficiency": 0.95,
                        "ratio_source_status": "user_input",
                        "ratio_reference": "验证算例齿数商",
                        "efficiency_source_status": "user_input",
                        "efficiency_reference": "验证算例效率",
                    },
                    {
                        "stage_name": "二级",
                        "ratio": 4.0,
                        "efficiency": 0.9,
                        "ratio_source_status": "user_input",
                        "ratio_reference": "验证算例齿数商",
                        "efficiency_source_status": "user_input",
                        "efficiency_reference": "验证算例效率",
                    },
                ),
            ),
            ("candidate_rated_output_torque_nm", 1100.0),
            ("candidate_source_status", "user_input"),
            ("candidate_reference", "验证算例额定值（非产品数据）"),
        ),
    ),
    ExpandedModuleSpec(
        module_id=gear_drive.MODULE_ID,
        module_name=gear_drive.MODULE_NAME,
        module_version=gear_drive.MODULE_VERSION,
        calculation_model_version=gear_drive.CALCULATION_MODEL_VERSION,
        report_template_version=gear_drive.REPORT_TEMPLATE_VERSION,
        input_model=gear_drive.Input,
        result_model=gear_drive.Result,
        calculate=gear_drive.calculate,
        build_report_context=gear_drive.build_report_context,
        summary="计算标准直齿外啮合基础几何、名义啮合力、节线速度及用户提供的候选限值。",
        category="传动系统",
        icon_key="gear",
        capabilities=("节圆基础几何", "名义啮合力", "候选限值校核", "HTML / PDF 报告"),
        catalog_order=30,
        input_labels=_label_pairs(GEAR_INPUT_LABELS),
        result_labels=_label_pairs(GEAR_RESULT_LABELS),
        unchecked_labels=_label_pairs(GEAR_UNCHECKED_LABELS),
        assumption_labels=_label_pairs(GEAR_ASSUMPTION_LABELS),
        example_input=(
            ("basis_source_status", "user_input"),
            ("basis_reference", "验证算例 GD-A-001（非设计参数）"),
            ("module_mm", 4.0),
            ("pinion_teeth", 20),
            ("gear_teeth", 60),
            ("pressure_angle_deg", 20.0),
            ("input_speed_rpm", 1200.0),
            ("input_torque_nm", 100.0),
            ("mesh_efficiency", 0.97),
            ("allowable_tangential_force_n", 3000.0),
            ("allowable_tangential_force_source_status", "user_input"),
            ("allowable_tangential_force_reference", "验证算例限值（非产品数据）"),
            ("maximum_pitch_line_speed_m_s", 8.0),
            ("maximum_pitch_line_speed_source_status", "user_input"),
            ("maximum_pitch_line_speed_reference", "验证算例限值（非产品数据）"),
        ),
    ),
    ExpandedModuleSpec(
        module_id=shaft_bearing.MODULE_ID,
        module_name=shaft_bearing.MODULE_NAME,
        module_version=shaft_bearing.MODULE_VERSION,
        calculation_model_version=shaft_bearing.CALCULATION_MODEL_VERSION,
        report_template_version=shaft_bearing.REPORT_TEMPLATE_VERSION,
        input_model=shaft_bearing.Input,
        result_model=shaft_bearing.Result,
        calculate=shaft_bearing.calculate,
        build_report_context=shaft_bearing.build_report_context,
        summary="计算用户给定 X、Y、p 下的轴承基本额定寿命，以及实心圆轴弯扭名义应力。",
        category="轴系部件",
        icon_key="bearing",
        capabilities=("轴承 L10 基本寿命", "实心轴名义应力", "许用应力校核", "HTML / PDF 报告"),
        catalog_order=40,
        input_labels=_label_pairs(SHAFT_BEARING_INPUT_LABELS),
        result_labels=_label_pairs(SHAFT_BEARING_RESULT_LABELS),
        unchecked_labels=_label_pairs(SHAFT_BEARING_UNCHECKED_LABELS),
        assumption_labels=_label_pairs(SHAFT_BEARING_ASSUMPTION_LABELS),
        example_input=(
            ("basis_source_status", "user_input"),
            ("basis_reference", "验证算例 SB-A-001（非项目参数）"),
            ("bearing_radial_load_n", 5000.0),
            ("bearing_axial_load_n", 1000.0),
            ("bearing_speed_rpm", 600.0),
            ("basic_dynamic_load_rating_n", 44000.0),
            ("dynamic_rating_source_status", "user_input"),
            ("dynamic_rating_reference", "验证算例额定值（非产品数据）"),
            ("radial_factor_x", 0.56),
            ("radial_factor_x_source_status", "user_input"),
            ("radial_factor_x_reference", "验证算例 X"),
            ("axial_factor_y", 1.6),
            ("axial_factor_y_source_status", "user_input"),
            ("axial_factor_y_reference", "验证算例 Y"),
            ("life_exponent_p", 3.0),
            ("life_exponent_source_status", "user_input"),
            ("life_exponent_reference", "验证算例 p"),
            ("shaft_diameter_mm", 50.0),
            ("shaft_bending_moment_nm", 500.0),
            ("shaft_torque_nm", 300.0),
            ("allowable_von_mises_stress_mpa", 120.0),
            ("allowable_stress_source_status", "user_input"),
            ("allowable_stress_reference", "验证算例许用值（非材料数据）"),
        ),
    ),
    ExpandedModuleSpec(
        module_id=lead_screw.MODULE_ID,
        module_name=lead_screw.MODULE_NAME,
        module_version=lead_screw.MODULE_VERSION,
        calculation_model_version=lead_screw.CALCULATION_MODEL_VERSION,
        report_template_version=lead_screw.REPORT_TEMPLATE_VERSION,
        input_model=lead_screw.Input,
        result_model=lead_screw.Result,
        calculate=lead_screw.calculate,
        build_report_context=lead_screw.build_report_context,
        summary="按等效方牙模型计算提升/下降转矩、效率、自锁、功率和 Euler 理论临界载荷。",
        category="直线传动",
        icon_key="screw",
        capabilities=("等效方牙转矩", "自锁与效率", "Euler 理论校核", "HTML / PDF 报告"),
        catalog_order=50,
        input_labels=_label_pairs(LEAD_SCREW_INPUT_LABELS),
        result_labels=_label_pairs(LEAD_SCREW_RESULT_LABELS),
        unchecked_labels=_label_pairs(LEAD_SCREW_UNCHECKED_LABELS),
        assumption_labels=_label_pairs(LEAD_SCREW_ASSUMPTION_LABELS),
        example_input=(
            ("basis_source_status", "user_input"),
            ("basis_reference", "验证算例 LS-A-001（非项目参数）"),
            ("axial_force_n", 10000.0),
            ("mean_thread_diameter_mm", 30.0),
            ("root_diameter_mm", 24.0),
            ("lead_mm_per_revolution", 6.0),
            ("friction_coefficient", 0.12),
            ("friction_source_status", "user_input"),
            ("friction_reference", "验证算例摩擦值"),
            ("rotational_speed_rpm", 300.0),
            ("youngs_modulus_gpa", 210.0),
            ("youngs_modulus_source_status", "user_input"),
            ("youngs_modulus_reference", "验证算例弹性模量"),
            ("unsupported_length_mm", 600.0),
            ("effective_length_factor", 1.0),
            ("effective_length_factor_source_status", "user_input"),
            ("effective_length_factor_reference", "验证算例两端铰支模型"),
            ("candidate_allowable_axial_load_n", 15000.0),
            ("candidate_source_status", "user_input"),
            ("candidate_reference", "验证算例许用值（非产品数据）"),
        ),
    ),
    ExpandedModuleSpec(
        module_id=synchronous_belt.MODULE_ID,
        module_name=synchronous_belt.MODULE_NAME,
        module_version=synchronous_belt.MODULE_VERSION,
        calculation_model_version=synchronous_belt.CALCULATION_MODEL_VERSION,
        report_template_version=synchronous_belt.REPORT_TEMPLATE_VERSION,
        input_model=synchronous_belt.Input,
        result_model=synchronous_belt.Result,
        calculate=synchronous_belt.calculate,
        build_report_context=synchronous_belt.build_report_context,
        summary="计算同步带速比、节径、带速、设计功率、圆周力、近似带长与啮合齿数。",
        category="挠性传动",
        icon_key="belt",
        capabilities=("节径与速比", "开式带长近似", "制造商限值接口", "HTML / PDF 报告"),
        catalog_order=60,
        input_labels=_label_pairs(BELT_INPUT_LABELS),
        result_labels=_label_pairs(BELT_RESULT_LABELS),
        unchecked_labels=_label_pairs(BELT_UNCHECKED_LABELS),
        assumption_labels=_label_pairs(BELT_ASSUMPTION_LABELS),
        example_input=(
            ("basis_source_status", "user_input"),
            ("basis_reference", "验证算例 BELT-GOLD-001（非产品参数）"),
            ("driver_teeth", 20),
            ("driven_teeth", 40),
            ("belt_pitch_m", 0.01),
            ("driver_angular_speed_rad_s", 100.0),
            ("transmitted_power_w", 2000.0),
            ("service_factor", 1.5),
            ("center_distance_m", 0.5),
            ("manufacturer_allowable_effective_tension_n", 1000.0),
            ("manufacturer_max_belt_speed_m_s", 4.0),
            ("candidate_data_source_status", "user_input"),
            ("candidate_reference", "验证算例限值（非制造商数据）"),
        ),
    ),
    ExpandedModuleSpec(
        module_id=motor_drive.MODULE_ID,
        module_name=motor_drive.MODULE_NAME,
        module_version=motor_drive.MODULE_VERSION,
        calculation_model_version=motor_drive.CALCULATION_MODEL_VERSION,
        report_template_version=motor_drive.REPORT_TEMPLATE_VERSION,
        input_model=motor_drive.Input,
        result_model=motor_drive.Result,
        calculate=motor_drive.calculate,
        build_report_context=motor_drive.build_report_context,
        summary="按两个明确稳态工作段折算连续、峰值和 RMS 转矩、功率及候选标量额定值。",
        category="驱动与执行",
        icon_key="motor",
        capabilities=("两段循环折算", "RMS 转矩", "候选额定值比较", "HTML / PDF 报告"),
        catalog_order=70,
        input_labels=_label_pairs(MOTOR_INPUT_LABELS),
        result_labels=_label_pairs(MOTOR_RESULT_LABELS),
        unchecked_labels=_label_pairs(MOTOR_UNCHECKED_LABELS),
        assumption_labels=_label_pairs(MOTOR_ASSUMPTION_LABELS),
        example_input=(
            ("basis_source_status", "user_input"),
            ("basis_reference", "验证算例 MOTOR-GOLD-001（非项目参数）"),
            ("segment_1_load_torque_n_m", 100.0),
            ("segment_1_load_speed_rad_s", 10.0),
            ("segment_1_duration_s", 4.0),
            ("segment_2_load_torque_n_m", 50.0),
            ("segment_2_load_speed_rad_s", 5.0),
            ("segment_2_duration_s", 6.0),
            ("transmission_ratio_motor_to_load", 5.0),
            ("transmission_efficiency", 0.8),
            ("service_factor", 1.2),
            ("declared_duty", "验证算例两段循环，工作制待供应商确认"),
            ("candidate_rated_torque_n_m", 25.0),
            ("candidate_peak_torque_n_m", 35.0),
            ("candidate_max_speed_rad_s", 60.0),
            ("candidate_rated_power_w", 2000.0),
            ("candidate_data_source_status", "user_input"),
            ("candidate_reference", "验证算例额定值（非制造商数据）"),
        ),
    ),
    ExpandedModuleSpec(
        module_id=stepper_motor.MODULE_ID,
        module_name=stepper_motor.MODULE_NAME,
        module_version=stepper_motor.MODULE_VERSION,
        calculation_model_version=stepper_motor.CALCULATION_MODEL_VERSION,
        report_template_version=stepper_motor.REPORT_TEMPLATE_VERSION,
        input_model=stepper_motor.Input,
        result_model=stepper_motor.Result,
        calculate=stepper_motor.calculate,
        build_report_context=stepper_motor.build_report_context,
        summary="计算刚性传动下的惯量折算、恒加速转矩、脉冲频率和用户提供的曲线工作点。",
        category="驱动与执行",
        icon_key="stepper",
        capabilities=("惯量折算", "恒加速转矩", "曲线工作点校核", "HTML / PDF 报告"),
        catalog_order=80,
        input_labels=_label_pairs(STEPPER_INPUT_LABELS),
        result_labels=_label_pairs(STEPPER_RESULT_LABELS),
        unchecked_labels=_label_pairs(STEPPER_UNCHECKED_LABELS),
        assumption_labels=_label_pairs(STEPPER_ASSUMPTION_LABELS),
        example_input=(
            ("basis_source_status", "user_input"),
            ("basis_reference", "验证算例 STEP-GOLD-001（非项目参数）"),
            ("load_inertia_kg_m2", 0.02),
            ("motor_rotor_inertia_kg_m2", 0.001),
            ("transmission_ratio_motor_to_load", 4.0),
            ("transmission_efficiency", 0.8),
            ("target_load_speed_rad_s", 5.0),
            ("acceleration_time_s", 2.0),
            ("steady_load_torque_n_m", 8.0),
            ("service_factor", 1.5),
            ("full_steps_per_revolution", 200),
            ("microstep_divisor", 16),
            ("candidate_curve_point_speed_rad_s", 20.0),
            ("candidate_curve_point_torque_n_m", 4.0),
            ("curve_point_speed_tolerance_rad_s", 0.0),
            ("candidate_allowable_inertia_ratio", 2.0),
            ("candidate_data_source_status", "user_input"),
            ("candidate_reference", "验证算例曲线点（非制造商数据）"),
        ),
    ),
    ExpandedModuleSpec(
        module_id=pneumatic_cylinder.MODULE_ID,
        module_name=pneumatic_cylinder.MODULE_NAME,
        module_version=pneumatic_cylinder.MODULE_VERSION,
        calculation_model_version=pneumatic_cylinder.CALCULATION_MODEL_VERSION,
        report_template_version=pneumatic_cylinder.REPORT_TEMPLATE_VERSION,
        input_model=pneumatic_cylinder.Input,
        result_model=pneumatic_cylinder.Result,
        calculate=pneumatic_cylinder.calculate,
        build_report_context=pneumatic_cylinder.build_report_context,
        summary="计算双作用单杆气缸理论伸缩力、负载余量、扫掠体积和理想参考状态耗气量。",
        category="驱动与执行",
        icon_key="cylinder",
        capabilities=("伸缩理论力", "负载余量", "参考状态耗气量", "HTML / PDF 报告"),
        catalog_order=90,
        input_labels=_label_pairs(CYLINDER_INPUT_LABELS),
        result_labels=_label_pairs(CYLINDER_RESULT_LABELS),
        unchecked_labels=_label_pairs(CYLINDER_UNCHECKED_LABELS),
        assumption_labels=_label_pairs(CYLINDER_ASSUMPTION_LABELS),
        example_input=(
            ("basis_source_status", "user_input"),
            ("basis_reference", "验证算例 CYL-GOLD-001（非项目参数）"),
            ("bore_diameter_m", 0.1),
            ("rod_diameter_m", 0.04),
            ("stroke_m", 0.5),
            ("cylinder_supply_absolute_pressure_pa", 700000.0),
            ("ambient_absolute_pressure_pa", 100000.0),
            ("reference_absolute_pressure_pa", 100000.0),
            ("extension_load_force_n", 3000.0),
            ("retraction_load_force_n", 2000.0),
            ("load_safety_factor", 1.2),
            ("cycle_frequency_hz", 1.0 / 6.0),
            ("candidate_max_supply_absolute_pressure_pa", 1000000.0),
            ("candidate_data_source_status", "user_input"),
            ("candidate_reference", "验证算例压力额定值（非制造商数据）"),
        ),
    ),
)


__all__ = ["EXPANDED_MODULE_SPECS", "ExpandedModuleSpec"]
