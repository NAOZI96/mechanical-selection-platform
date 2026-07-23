"""Pydantic data models for the winch and drum calculation core.

Display-unit input is validated here and explicitly converted to an immutable
SI model before it reaches the calculator.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)


class ResultClassification(str, Enum):
    """Engineering confidence classification used by calculation outputs."""

    CALCULATED = "calculated"
    PRELIMINARY = "preliminary"
    REVIEW_REQUIRED = "review_required"
    INFORMATIONAL = "informational"


class CalculationStatus(str, Enum):
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"


class WarningSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceStatus(str, Enum):
    PROJECT_SETTING = "项目设定"
    ENGINEERING_EXPERIENCE = "工程经验"
    PENDING_CONFIRMATION = "待确认"


class WarningCode(str, Enum):
    CORE_RULE_MISSING = "W_CORE_RULE_MISSING"
    CORE_UNVERIFIED = "W_CORE_UNVERIFIED"
    CAPACITY_INSUFFICIENT = "W_CAPACITY_INSUFFICIENT"
    FIXED_RATIO_SPEED_VARIATION = "W_FIXED_RATIO_SPEED_VARIATION"
    MOTOR_SELECTION_INCOMPLETE = "W_MOTOR_SELECTION_INCOMPLETE"
    BRAKE_STATIC_ONLY = "W_BRAKE_STATIC_ONLY"
    REVERSE_EFFICIENCY_UNKNOWN = "W_REVERSE_EFFICIENCY_UNKNOWN"
    REVERSE_EFFICIENCY_APPROXIMATED = "W_REVERSE_EFFICIENCY_APPROXIMATED"
    SERVICE_FACTOR_SOURCE = "W_SERVICE_FACTOR_SOURCE"
    PITCH_FACTOR_SOURCE = "W_PITCH_FACTOR_SOURCE"
    DUTY_CLASS_INFO_ONLY = "W_DUTY_CLASS_INFO_ONLY"
    ROPE_STRENGTH_NOT_CHECKED = "W_ROPE_STRENGTH_NOT_CHECKED"
    DRUM_STRUCTURE_NOT_CHECKED = "W_DRUM_STRUCTURE_NOT_CHECKED"
    DEAD_WRAPS_ASSUMED_ZERO = "W_DEAD_WRAPS_ASSUMED_ZERO"


PositiveFloat = Annotated[float, Field(gt=0)]
FactorAtLeastOne = Annotated[float, Field(ge=1)]
PositiveLayerCount = Annotated[StrictInt, Field(ge=1, le=100)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class AssumptionSources(BaseModel):
    """Source status of engineering values supplied by the caller."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    service_factor: SourceStatus = SourceStatus.PENDING_CONFIRMATION
    pitch_factor: SourceStatus = SourceStatus.PENDING_CONFIRMATION
    brake_safety_factor: SourceStatus = SourceStatus.PENDING_CONFIRMATION
    approved_core_ratio: SourceStatus = SourceStatus.PENDING_CONFIRMATION


class WinchDrumInput(BaseModel):
    """Validated user-facing input using the documented display units."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rated_line_pull_kn: PositiveFloat
    rope_diameter_mm: PositiveFloat
    rope_speed_m_per_min: PositiveFloat
    target_rope_capacity_m: PositiveFloat
    service_factor: FactorAtLeastOne
    total_efficiency: Annotated[float, Field(gt=0, le=1)]
    motor_rated_speed_rpm: PositiveFloat
    motor_type: Annotated[str, Field(min_length=1, max_length=64)]
    drum_core_diameter_mm: PositiveFloat | None = None
    drum_face_length_mm: PositiveFloat | None = None
    max_layers: PositiveLayerCount
    pitch_factor: FactorAtLeastOne
    side_margin_mm: Annotated[float, Field(ge=0)]
    reeving_ratio: FactorAtLeastOne
    brake_safety_factor: FactorAtLeastOne
    duty_class: Annotated[str, Field(min_length=1, max_length=64)]
    approved_core_ratio: PositiveFloat | None = None
    dead_wraps: NonNegativeInt = 0
    allow_forward_efficiency_as_reverse_approx: StrictBool = False
    assumption_sources: AssumptionSources = Field(default_factory=AssumptionSources)

    @field_validator(
        "rated_line_pull_kn",
        "rope_diameter_mm",
        "rope_speed_m_per_min",
        "target_rope_capacity_m",
        "service_factor",
        "total_efficiency",
        "motor_rated_speed_rpm",
        "drum_core_diameter_mm",
        "drum_face_length_mm",
        "pitch_factor",
        "side_margin_mm",
        "reeving_ratio",
        "brake_safety_factor",
        "approved_core_ratio",
        mode="before",
    )
    @classmethod
    def reject_non_numeric_or_non_finite(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("必须是有限的 JSON 数值，不能使用布尔值或数值字符串")
        if not math.isfinite(float(value)):
            raise ValueError("必须是有限数，禁止 NaN 或 Infinity")
        return value

    @field_validator("motor_type", "duty_class")
    @classmethod
    def strip_and_require_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_drum_width_when_supplied(self) -> WinchDrumInput:
        if self.drum_face_length_mm is None:
            return self

        usable_width_mm = self.drum_face_length_mm - 2.0 * self.side_margin_mm
        pitch_mm = self.pitch_factor * self.rope_diameter_mm
        if usable_width_mm <= 0:
            raise ValueError("卷筒面长扣除两侧余量后必须大于 0")
        if usable_width_mm + 1e-9 < pitch_mm:
            raise ValueError("卷筒面长扣除两侧余量后必须至少容纳一圈")

        turns = math.floor((usable_width_mm + 1e-9) / pitch_mm)
        if self.dead_wraps > turns:
            raise ValueError("固定死圈数不能超过第一层可容纳的完整圈数")
        return self

    def to_si(self) -> WinchDrumSIInput:
        """Convert display units to the single internal SI representation."""

        return WinchDrumSIInput(
            rated_line_pull_n=self.rated_line_pull_kn * 1000.0,
            rope_diameter_m=self.rope_diameter_mm / 1000.0,
            rope_speed_m_s=self.rope_speed_m_per_min / 60.0,
            target_rope_capacity_m=self.target_rope_capacity_m,
            service_factor=self.service_factor,
            total_efficiency=self.total_efficiency,
            motor_angular_speed_rad_s=self.motor_rated_speed_rpm * 2.0 * math.pi / 60.0,
            motor_type=self.motor_type,
            drum_core_diameter_m=(
                None
                if self.drum_core_diameter_mm is None
                else self.drum_core_diameter_mm / 1000.0
            ),
            drum_face_length_m=(
                None
                if self.drum_face_length_mm is None
                else self.drum_face_length_mm / 1000.0
            ),
            max_layers=self.max_layers,
            pitch_factor=self.pitch_factor,
            side_margin_m=self.side_margin_mm / 1000.0,
            reeving_ratio=self.reeving_ratio,
            brake_safety_factor=self.brake_safety_factor,
            duty_class=self.duty_class,
            approved_core_ratio=self.approved_core_ratio,
            dead_wraps=self.dead_wraps,
            allow_forward_efficiency_as_reverse_approx=(
                self.allow_forward_efficiency_as_reverse_approx
            ),
            assumption_sources=self.assumption_sources,
        )


class WinchDrumSIInput(BaseModel):
    """Immutable internal input; dimensional values are SI except layer counts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rated_line_pull_n: float
    rope_diameter_m: float
    rope_speed_m_s: float
    target_rope_capacity_m: float
    service_factor: float
    total_efficiency: float
    motor_angular_speed_rad_s: float
    motor_type: str
    drum_core_diameter_m: float | None
    drum_face_length_m: float | None
    max_layers: int
    pitch_factor: float
    side_margin_m: float
    reeving_ratio: float
    brake_safety_factor: float
    duty_class: str
    approved_core_ratio: float | None
    dead_wraps: int
    allow_forward_efficiency_as_reverse_approx: bool
    assumption_sources: AssumptionSources


class AssumptionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    value: float | int | bool | str | None
    unit: str | None = None
    source_status: SourceStatus
    note: str


class WarningRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: WarningCode
    severity: WarningSeverity
    message: str
    affected_fields: tuple[str, ...] = ()


class FormulaStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int
    formula_id: str
    expression: str
    variables: dict[str, float | int | str]
    result_value: float | int
    unit: str
    classification: ResultClassification


class ScalarResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: float | None
    unit: str
    classification: ResultClassification
    formula_ids: tuple[str, ...]
    reason: str | None = None

    @model_validator(mode="after")
    def validate_unknown_result_semantics(self) -> ScalarResult:
        if self.value is None:
            if self.classification is not ResultClassification.REVIEW_REQUIRED:
                raise ValueError("未知结果必须标记为 review_required")
            if not self.reason:
                raise ValueError("未知结果必须说明原因")
        return self


class LayerResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    layer_number: int
    center_diameter_m: float
    turn_length_m: float
    full_turns: int
    usable_turns: int
    used_turns: float
    gross_capacity_m: float
    usable_capacity_m: float
    used_capacity_m: float
    cumulative_usable_capacity_m: float
    cumulative_used_capacity_m: float


class DrumCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    core_diameter_m: float
    face_length_m: float
    layer_limit: int
    turns_per_layer: int
    capacity_m: float
    capacity_margin_m: float
    outer_envelope_diameter_m: float
    envelope_proxy_m3: float
    explanation: str


class WinchDrumResult(BaseModel):
    """Complete deterministic calculation result and audit trail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    module_id: str
    module_version: str
    calculation_model_version: str
    status: CalculationStatus
    input_si: WinchDrumSIInput
    design_line_pull_n: ScalarResult
    theoretical_load_power_w: ScalarResult
    minimum_motor_power_w: ScalarResult
    suggested_motor_power_w: ScalarResult
    used_or_suggested_core_diameter_m: ScalarResult
    used_or_suggested_drum_face_length_m: ScalarResult
    pitch_m: float
    usable_width_m: float | None
    turns_per_full_layer: int | None
    layer_details: tuple[LayerResult, ...]
    capacity_satisfied: bool
    actual_layers: int | None
    evaluated_layers: int
    capacity_at_actual_layers_m: float | None
    capacity_at_max_layers_m: float | None
    capacity_margin_m: float | None
    capacity_margin_pct: float | None
    capacity_shortfall_m: float | None
    empty_working_diameter_m: float | None
    full_working_diameter_m: float | None
    empty_drum_speed_rpm: float | None
    full_drum_speed_rpm: float | None
    reference_ratio_empty: float | None
    reference_ratio_full: float | None
    reference_ratio_nominal: float | None
    low_speed_brake_torque_nm: ScalarResult
    high_speed_brake_torque_ref_nm: ScalarResult
    ideal_load_force_n: ScalarResult
    ideal_load_speed_m_s: ScalarResult
    optimizer_candidates: tuple[DrumCandidate, ...]
    selected_candidate: DrumCandidate | None
    calculation_steps: tuple[FormulaStep, ...]
    warnings: tuple[WarningRecord, ...]
    assumptions: tuple[AssumptionRecord, ...]
    disclaimer: str
