"""Version identifiers and report vocabulary for the pneumatic-cylinder module."""

MODULE_ID = "pneumatic_cylinder"
MODULE_NAME = "气缸选型"
MODULE_VERSION = "1.0.0"
CALCULATION_MODEL_VERSION = "pneumatic_cylinder.calc.1.0.0"
REPORT_TEMPLATE_VERSION = "pneumatic_cylinder.report.1.0.0"

DISCLAIMER = (
    "本结果是双作用单杆气缸的理论力和理想等温耗气量初选，不构成气缸、阀岛或供气系统的采购放行依据。"
    "输入压力应为气缸接口处可用绝对压力；本模型不计算管路和阀压降，也不包含死腔、泄漏、缓冲、"
    "动态背压、流量与速度、活塞杆稳定性、安装偏载及适用标准校核，须由气动和机械工程师复核。"
)

INPUT_LABELS = {
    "basis_source_status": "计算依据来源状态",
    "basis_reference": "计算依据或数据版本",
    "bore_diameter_m": "缸径",
    "rod_diameter_m": "活塞杆直径",
    "stroke_m": "行程",
    "cylinder_supply_absolute_pressure_pa": "气缸接口供气绝压",
    "ambient_absolute_pressure_pa": "环境绝压",
    "reference_absolute_pressure_pa": "标准体积参考绝压",
    "extension_load_force_n": "伸出负载力",
    "retraction_load_force_n": "缩回负载力",
    "load_safety_factor": "负载安全系数",
    "cycle_frequency_hz": "完整循环频率",
    "candidate_max_supply_absolute_pressure_pa": "候选气缸最大供气绝压",
    "candidate_data_source_status": "候选气缸数据来源状态",
    "candidate_reference": "候选气缸数据版本",
}

RESULT_LABELS = {
    "extension_effective_area_m2": "伸出有效面积",
    "retraction_effective_area_m2": "缩回有效面积",
    "pressure_differential_pa": "有效压差",
    "theoretical_extension_force_n": "理论伸出力",
    "theoretical_retraction_force_n": "理论缩回力",
    "required_extension_force_n": "伸出安全需求力",
    "required_retraction_force_n": "缩回安全需求力",
    "extension_force_margin_n": "伸出力余量",
    "retraction_force_margin_n": "缩回力余量",
    "extension_force_pass": "伸出力校核",
    "retraction_force_pass": "缩回力校核",
    "extension_chamber_volume_m3": "伸出腔扫掠体积",
    "retraction_chamber_volume_m3": "缩回腔扫掠体积",
    "chamber_volume_per_cycle_m3": "单循环腔体扫掠体积",
    "reference_air_volume_per_cycle_m3": "单循环参考状态耗气体积",
    "reference_air_consumption_m3_per_min": "每分钟参考状态耗气量",
    "candidate_pressure_rating_pass": "候选气缸压力额定校核",
}

UNCHECKED_LABELS = {
    "pipe_and_valve_pressure_drop": "管路、接头和阀的压降",
    "dynamic_back_pressure": "排气背压和运动过程压力变化",
    "flow_speed_and_cycle_time": "阀流量、气缸速度和实际循环时间",
    "dead_volume_leakage_temperature": "死腔、泄漏及温度修正",
    "cushioning_and_impact": "端部缓冲、冲击和动载荷",
    "rod_buckling_and_mounting": "活塞杆屈曲、安装偏载和导向",
    "materials_environment_standards": "材料、环境适应性及适用标准",
}

ASSUMPTION_LABELS = {
    "calculation_basis": "计算依据",
    "single_rod_double_acting": "双作用单杆结构",
    "cylinder_port_pressure": "气缸接口压力口径",
    "load_safety_factor": "负载安全系数",
    "full_cycle": "完整伸缩循环",
    "ideal_reference_volume": "理想参考体积折算",
    "candidate_data": "候选气缸数据",
}
