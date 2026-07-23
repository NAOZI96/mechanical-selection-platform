"""Versioned assumptions and non-numeric engineering boundaries.

No unverified mechanical standard, D/d ratio, safety factor, or product series
is defined here. Numeric engineering factors remain explicit user input.
"""

from __future__ import annotations

from .schema import AssumptionRecord, SourceStatus, WinchDrumSIInput

MODULE_ID = "winch_drum"
MODULE_NAME = "绞车与卷筒选型助手"
MODULE_VERSION = "1.1.0"
CALCULATION_MODEL_VERSION = "winch_drum.calc.1.1.0"
REPORT_TEMPLATE_VERSION = "winch_drum.report.1.2.0"

MOTOR_POWER_SERIES_KW = (
    0.12,
    0.18,
    0.25,
    0.37,
    0.55,
    0.75,
    1.1,
    1.5,
    2.2,
    3.0,
    4.0,
    5.5,
    7.5,
    11.0,
    15.0,
    18.5,
    22.0,
    30.0,
    37.0,
    45.0,
    55.0,
    75.0,
    90.0,
    110.0,
    132.0,
    160.0,
    200.0,
    250.0,
    315.0,
)

DISCLAIMER = (
    "本结果为基于所填数据和所列假设的工程计算与初选辅助结果，不构成制造、"
    "采购、施工或安全认证依据。缆绳强度、卷筒结构、制动动态与热容量、"
    "传动系统、工作制、环境条件及适用标准仍须由具备资质的工程师和供应商复核。"
)

MAX_OPTIMIZER_CANDIDATES = 100


def build_assumptions(data: WinchDrumSIInput, geometry_optimized: bool) -> tuple[AssumptionRecord, ...]:
    """Create the auditable assumption list used by this calculation."""

    records = [
        AssumptionRecord(
            key="force_and_speed_basis",
            value=f"{data.force_input_location.value}/{data.speed_input_location.value}",
            source_status=SourceStatus.USER_INPUT,
            note="原始输入按所选位置换算为卷筒绳端参数后再计算。",
        ),
        AssumptionRecord(
            key="service_factor",
            value=data.service_factor,
            source_status=data.assumption_sources.service_factor,
            note="只在额定拉力输入时用于形成设计拉力；后续公式不再次乘用。",
        ),
        AssumptionRecord(
            key="pitch_factor",
            value=data.pitch_factor,
            source_status=data.assumption_sources.pitch_factor,
            note="用于 p=K_p*d；绳槽和排绳适用性仍需复核。",
        ),
        AssumptionRecord(
            key="brake_safety_factor",
            value=data.brake_safety_factor,
            source_status=data.assumption_sources.brake_safety_factor,
            note=(
                "按已冻结的 design_force 口径，以设计绳张力为静态保持基准；"
                "使用系数只在额定拉力换算为设计拉力时作用一次，制动安全系数另作用一次。"
            ),
        ),
        AssumptionRecord(
            key="brake_basis_type",
            value=data.brake_basis_type.value,
            source_status=SourceStatus.PROJECT_DEFAULT,
            note="当前模型只支持冻结的 design_force 制动基准，不接受其他静默口径。",
        ),
        AssumptionRecord(
            key="dead_wraps",
            value=data.dead_wrap_count,
            unit="turn",
            source_status=(data.assumption_sources.dead_wrap_count),
            note="固定死圈计入总储绳量，不计入目标有效工作绳长。",
        ),
        AssumptionRecord(
            key="regular_level_winding",
            value=True,
            source_status=SourceStatus.PROJECT_SETTING,
            note="按规则密排、无交叉压陷和无弹性压缩的绳中心线螺旋模型计算。",
        ),
        AssumptionRecord(
            key="geometry_optimizer",
            value=geometry_optimized,
            source_status=SourceStatus.PROJECT_SETTING,
            note=(
                "优化器只比较 1..max_layers 的有限几何组合，按圆柱包络代理量排序；"
                "结果是几何初选，不是结构或标准符合性结论。"
            ),
        ),
    ]

    if data.approved_core_ratio is not None:
        records.append(
            AssumptionRecord(
                key="approved_core_ratio",
                value=data.approved_core_ratio,
                source_status=data.assumption_sources.approved_core_ratio,
                note="用于 D_c=R_Dd*d；其来源和适用绳型必须由机械工程师确认。",
            )
        )

    records.append(
        AssumptionRecord(
            key="reverse_efficiency_approximation",
            value=data.allow_forward_efficiency_as_reverse_approx,
            source_status=SourceStatus.PROJECT_SETTING,
            note=("false 时高速轴制动力矩保持待校核；true 时仅以正向总效率作近似参考。"),
        )
    )
    records.append(
        AssumptionRecord(
            key="backdrive_efficiency",
            value=data.backdrive_efficiency,
            source_status=data.assumption_sources.backdrive_efficiency,
            note=("仅在用户明确提供且传动允许反驱时使用；缺失、自锁、不可逆或禁止反驱时，高速轴制动力矩保持待校核。"),
        )
    )
    records.extend(
        (
            AssumptionRecord(
                key="pulley_efficiency",
                value=data.pulley_efficiency,
                source_status=data.assumption_sources.pulley_efficiency,
                note="仅用于载荷端拉力向卷筒绳端拉力的正向换算。",
            ),
            AssumptionRecord(
                key="minimum_dd_ratio",
                value=data.minimum_dd_ratio,
                source_status=data.assumption_sources.minimum_dd_ratio,
                note="项目初选默认值，不代表标准强制值。",
            ),
            AssumptionRecord(
                key="motor_power_series_id",
                value=data.motor_power_series_id.value,
                source_status=SourceStatus.PROJECT_DEFAULT,
                note="功率档位为项目配置；选档不代表启动、过载或热容量合格。",
            ),
        )
    )
    return tuple(records)
