"""Version identifiers and reporting vocabulary for the synchronous-belt module."""

MODULE_ID = "synchronous_belt"
MODULE_NAME = "同步带传动选型"
MODULE_VERSION = "1.0.0"
CALCULATION_MODEL_VERSION = "synchronous_belt.calc.1.0.0"
REPORT_TEMPLATE_VERSION = "synchronous_belt.report.1.0.1"

DISCLAIMER = (
    "本结果仅用于同步带传动的运动学、几何和载荷初选，不构成制造、采购或安全认证依据。"
    "带型与齿形兼容性、标准节线长度、带宽及齿剪切能力、预紧力、轴承载荷、疲劳寿命、"
    "环境降额和制造商选型程序仍须由具备资质的工程师及供应商复核。"
)

INPUT_LABELS = {
    "basis_source_status": "计算依据来源状态",
    "basis_reference": "计算依据或数据版本",
    "driver_teeth": "主动轮齿数",
    "driven_teeth": "从动轮齿数",
    "belt_pitch_m": "同步带节距",
    "driver_angular_speed_rad_s": "主动轮角速度",
    "transmitted_power_w": "传递功率",
    "service_factor": "使用系数",
    "center_distance_m": "中心距",
    "manufacturer_allowable_effective_tension_n": "制造商许用有效圆周力",
    "manufacturer_max_belt_speed_m_s": "制造商最大带速",
    "candidate_data_source_status": "候选数据来源状态",
    "candidate_reference": "候选带数据版本",
}

RESULT_LABELS = {
    "speed_ratio": "传动比",
    "driven_angular_speed_rad_s": "从动轮角速度",
    "driver_pitch_diameter_m": "主动轮节径",
    "driven_pitch_diameter_m": "从动轮节径",
    "belt_speed_m_s": "带速",
    "design_power_w": "设计功率",
    "effective_circumferential_force_n": "有效圆周力",
    "approximate_open_belt_length_m": "近似开式带长",
    "small_pulley_wrap_angle_rad": "小带轮包角",
    "small_pulley_engaged_teeth": "小带轮啮合齿数",
    "allowable_tension_pass": "许用有效圆周力校核",
    "maximum_speed_pass": "最大带速校核",
}

UNCHECKED_LABELS = {
    "belt_profile_compatibility": "带型、齿形与带轮槽形兼容性",
    "catalog_pitch_length": "制造商标准节线长度与张紧行程",
    "belt_width_and_tooth_capacity": "带宽、齿剪切及许用功率",
    "pretension_and_bearing_load": "预紧力、轴载荷与轴承载荷",
    "fatigue_life": "带体与抗拉层疲劳寿命",
    "environmental_derating": "温度、粉尘、油污等环境降额",
}

ASSUMPTION_LABELS = {
    "calculation_basis": "计算依据",
    "service_factor": "使用系数",
    "pitch_geometry": "节径几何关系",
    "open_belt_length_model": "开式带长近似模型",
    "candidate_data": "候选带制造商数据",
}
