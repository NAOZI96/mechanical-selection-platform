"""Version identifiers and report labels for the motor-drive module."""

MODULE_ID = "motor_drive"
MODULE_NAME = "电机与驱动功率选型"
MODULE_VERSION = "1.0.0"
CALCULATION_MODEL_VERSION = "motor_drive.calc.1.0.0"
REPORT_TEMPLATE_VERSION = "motor_drive.report.1.0.0"

DISCLAIMER = (
    "本结果是基于两个明确稳态工作段的传动折算和电机初选，不构成电机、驱动器或制动单元的采购放行依据。"
    "启动与减速瞬态、负载惯量、再生能量、工作制分类、热模型、供电条件以及制造商完整转矩-转速曲线"
    "均未在本模型中校核，须由电气和机械专业工程师结合供应商数据复核。"
)

INPUT_LABELS = {
    "basis_source_status": "计算依据来源状态",
    "basis_reference": "计算依据或数据版本",
    "segment_1_load_torque_n_m": "工作段1负载侧转矩",
    "segment_1_load_speed_rad_s": "工作段1负载侧角速度",
    "segment_1_duration_s": "工作段1持续时间",
    "segment_2_load_torque_n_m": "工作段2负载侧转矩",
    "segment_2_load_speed_rad_s": "工作段2负载侧角速度",
    "segment_2_duration_s": "工作段2持续时间",
    "transmission_ratio_motor_to_load": "电机侧/负载侧转速比",
    "transmission_efficiency": "正向传动效率",
    "service_factor": "使用系数",
    "declared_duty": "用户声明工作制",
    "candidate_rated_torque_n_m": "候选电机额定转矩",
    "candidate_peak_torque_n_m": "候选电机峰值转矩",
    "candidate_max_speed_rad_s": "候选电机最大角速度",
    "candidate_rated_power_w": "候选电机额定功率",
    "candidate_data_source_status": "候选电机数据来源状态",
    "candidate_reference": "候选电机数据版本",
}

RESULT_LABELS = {
    "segment_1_motor_torque_n_m": "工作段1电机侧转矩",
    "segment_2_motor_torque_n_m": "工作段2电机侧转矩",
    "segment_1_motor_speed_rad_s": "工作段1电机角速度",
    "segment_2_motor_speed_rad_s": "工作段2电机角速度",
    "continuous_motor_torque_n_m": "周期平均连续转矩",
    "peak_motor_torque_n_m": "两段峰值转矩",
    "rms_motor_torque_n_m": "周期RMS转矩",
    "required_continuous_torque_n_m": "计入使用系数的连续转矩",
    "required_peak_torque_n_m": "计入使用系数的峰值转矩",
    "required_rms_torque_n_m": "计入使用系数的RMS转矩",
    "required_power_w": "所需机械功率",
    "maximum_motor_speed_rad_s": "最大电机角速度",
    "candidate_rated_torque_pass": "候选额定转矩校核",
    "candidate_peak_torque_pass": "候选峰值转矩校核",
    "candidate_speed_pass": "候选最高转速校核",
    "candidate_rated_power_pass": "候选额定功率校核",
}

UNCHECKED_LABELS = {
    "acceleration_and_deceleration": "启动、加速和减速瞬态转矩",
    "reflected_inertia": "负载惯量与传动惯量折算",
    "duty_and_thermal_model": "工作制分类及电机/驱动器热模型",
    "manufacturer_torque_speed_curve": "制造商完整转矩-转速曲线",
    "regeneration_and_braking": "再生能量、制动电阻与失电制动",
    "supply_and_drive_compatibility": "电源、驱动器及电机电气兼容性",
}

ASSUMPTION_LABELS = {
    "calculation_basis": "计算依据",
    "two_segment_cycle": "两段工作循环",
    "transmission_ratio_definition": "传动比定义",
    "transmission_efficiency": "正向传动效率",
    "service_factor": "使用系数",
    "declared_duty": "用户声明工作制",
    "candidate_data": "候选电机数据",
}
