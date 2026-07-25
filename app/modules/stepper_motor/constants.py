"""Version identifiers and report vocabulary for the stepper-motor module."""

MODULE_ID = "stepper_motor"
MODULE_NAME = "步进电机选型"
MODULE_VERSION = "1.0.0"
CALCULATION_MODEL_VERSION = "stepper_motor.calc.1.0.0"
REPORT_TEMPLATE_VERSION = "stepper_motor.report.1.0.0"

DISCLAIMER = (
    "本结果是基于刚性传动、恒加速度和单一稳态负载转矩的步进电机初选，不构成电机或驱动器采购放行依据。"
    "当前正向传动效率只用于稳态负载转矩折算，负载惯性加速过程的传动损耗模型尚未确认。"
    "完整加速路径转矩-转速曲线、共振与失步风险、驱动电压电流、热容量、定位精度、传动间隙与柔性、"
    "制动和保持安全仍须通过制造商数据、详细运动仿真及样机试验复核。"
)

INPUT_LABELS = {
    "basis_source_status": "计算依据来源状态",
    "basis_reference": "计算依据或数据版本",
    "load_inertia_kg_m2": "负载侧转动惯量",
    "motor_rotor_inertia_kg_m2": "电机转子惯量",
    "transmission_ratio_motor_to_load": "电机侧/负载侧转速比",
    "transmission_efficiency": "正向传动效率",
    "target_load_speed_rad_s": "目标负载角速度",
    "acceleration_time_s": "加速时间",
    "steady_load_torque_n_m": "负载侧稳态转矩",
    "service_factor": "使用系数",
    "full_steps_per_revolution": "每转整步数",
    "microstep_divisor": "微步细分数",
    "candidate_curve_point_speed_rad_s": "候选曲线工作点角速度",
    "candidate_curve_point_torque_n_m": "候选曲线工作点可用转矩",
    "curve_point_speed_tolerance_rad_s": "曲线工作点速度匹配容差",
    "candidate_allowable_inertia_ratio": "候选允许惯量比",
    "candidate_data_source_status": "候选数据来源状态",
    "candidate_reference": "候选电机/驱动器数据版本",
}

RESULT_LABELS = {
    "reflected_load_inertia_kg_m2": "负载惯量折算值",
    "total_motor_side_inertia_kg_m2": "电机侧总惯量",
    "working_motor_speed_rad_s": "工作角速度",
    "motor_angular_acceleration_rad_s2": "电机角加速度",
    "inertial_acceleration_torque_n_m": "惯性加速转矩",
    "steady_motor_torque_n_m": "电机侧稳态转矩",
    "acceleration_motor_torque_n_m": "加速阶段电机转矩",
    "required_steady_torque_n_m": "计入使用系数的稳态转矩",
    "required_peak_torque_n_m": "所需峰值转矩",
    "pulse_frequency_hz": "驱动脉冲频率",
    "inertia_ratio": "负载/转子惯量比",
    "candidate_curve_torque_pass": "候选曲线工作点转矩校核",
    "candidate_inertia_ratio_pass": "候选允许惯量比校核",
}

UNCHECKED_LABELS = {
    "full_torque_speed_curve": "完整加速路径转矩-转速曲线",
    "resonance_and_step_loss": "低频/中频共振及失步风险",
    "driver_electrical_conditions": "驱动电压、电流和绕组接法",
    "motor_thermal_capacity": "电机与驱动器热容量",
    "positioning_accuracy": "定位精度、细分线性与编码器需求",
    "transmission_compliance": "传动间隙、扭转柔性与机械共振",
    "acceleration_transmission_loss_model": "负载惯性加速过程的传动损耗模型",
    "holding_and_braking": "停机保持、垂直轴制动与失电安全",
}

ASSUMPTION_LABELS = {
    "calculation_basis": "计算依据",
    "transmission_ratio_definition": "传动比定义",
    "rigid_transmission": "刚性传动模型",
    "constant_acceleration": "恒加速度模型",
    "transmission_efficiency": "正向传动效率",
    "service_factor": "使用系数",
    "pulse_command": "脉冲指令参数",
    "candidate_data": "候选电机/驱动器数据",
}
