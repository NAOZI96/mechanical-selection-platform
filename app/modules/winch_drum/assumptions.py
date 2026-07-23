"""Versioned assumptions and non-numeric engineering boundaries.

No unverified mechanical standard, D/d ratio, safety factor, or product series
is defined here. Numeric engineering factors remain explicit user input.
"""

from __future__ import annotations

from .schema import AssumptionRecord, SourceStatus, WinchDrumSIInput

MODULE_ID = "winch_drum"
MODULE_NAME = "绞车与卷筒选型助手"
MODULE_VERSION = "1.0.0"
CALCULATION_MODEL_VERSION = "winch_drum.calc.1.0.0"

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
            value="卷筒绳端",
            source_status=SourceStatus.PROJECT_SETTING,
            note="额定拉力和绳速均按卷筒处绳端量解释。",
        ),
        AssumptionRecord(
            key="service_factor",
            value=data.service_factor,
            source_status=data.assumption_sources.service_factor,
            note="仅用于设计拉力和驱动功率，不重复用于制动力矩。",
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
            note="以额定绳张力为静态保持基准，不再乘使用系数。",
        ),
        AssumptionRecord(
            key="dead_wraps",
            value=data.dead_wraps,
            unit="turn",
            source_status=(
                SourceStatus.PENDING_CONFIRMATION
                if data.dead_wraps == 0
                else SourceStatus.PROJECT_SETTING
            ),
            note="固定死圈仅占用第一层空间；0 圈是假设且需要机械工程师确认。",
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
            note=(
                "false 时高速轴制动力矩保持待校核；true 时仅以正向总效率作近似参考。"
            ),
        )
    )
    return tuple(records)
