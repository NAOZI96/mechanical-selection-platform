"""Pydantic data models for the winch and drum calculation core.

Display-unit input is validated here and explicitly converted to an immutable
SI model before it reaches the calculator.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, Any

from pydantic import (
    AliasChoices,
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
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    BLOCKING = "blocking"


class SourceStatus(str, Enum):
    PROJECT_DEFAULT = "project_default"
    USER_INPUT = "user_input"
    STANDARD_CONFIRMED = "standard_confirmed"
    MANUFACTURER_DATA = "manufacturer_data"
    PENDING_CONFIRMATION = "pending_confirmation"

    # Backward-compatible names used by the Phase 1 implementation.
    PROJECT_SETTING = "project_default"
    ENGINEERING_EXPERIENCE = "pending_confirmation"


class ForceInputLocation(str, Enum):
    DRUM_ROPE_END = "drum_rope_end"
    LOAD_END = "load_end"


class SpeedInputLocation(str, Enum):
    DRUM_ROPE_END = "drum_rope_end"
    LOAD_END = "load_end"


class ForceInputType(str, Enum):
    RATED = "rated"
    DESIGN = "design"
    MAXIMUM = "maximum"


class BrakeBasisType(str, Enum):
    DESIGN_FORCE = "design_force"


class BrakeInstallationShaft(str, Enum):
    DRUM_OR_LOW_SPEED = "drum_or_low_speed"
    MOTOR_HIGH_SPEED = "motor_high_speed"
    OTHER = "other"


class TransmissionBackdriveType(str, Enum):
    REVERSIBLE = "reversible"
    SELF_LOCKING = "self_locking"
    WORM = "worm"
    NON_REVERSIBLE = "non_reversible"
    BACKDRIVE_PROHIBITED = "backdrive_prohibited"


class MotorPowerSeriesId(str, Enum):
    PROJECT_DEFAULT_IEC_KW = "project_default_iec_kw"


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
    PULLEY_EFFICIENCY_DEFAULT = "W_PULLEY_EFFICIENCY_DEFAULT"
    DEAD_WRAP_BELOW_DEFAULT = "W_DEAD_WRAP_BELOW_DEFAULT"
    ROPE_DIAMETER_OUTSIDE_VALIDATED_RANGE = "W_ROPE_DIAMETER_OUTSIDE_VALIDATED_RANGE"
    DD_PROJECT_DEFAULT = "W_DD_PROJECT_DEFAULT"
    DYNAMIC_BRAKE_NOT_CHECKED = "W_DYNAMIC_BRAKE_NOT_CHECKED"
    BACKDRIVE_EFFICIENCY_APPROXIMATED = "W_REVERSE_EFFICIENCY_APPROXIMATED"
    MOTOR_THERMAL_NOT_CHECKED = "W_MOTOR_THERMAL_NOT_CHECKED"
    STANDARD_CLAUSE_NOT_CONFIRMED = "W_STANDARD_CLAUSE_NOT_CONFIRMED"


PositiveFloat = Annotated[float, Field(gt=0)]
DdRatio = Annotated[float, Field(gt=1)]
FactorAtLeastOne = Annotated[float, Field(ge=1)]
PositiveLayerCount = Annotated[StrictInt, Field(ge=1, le=100)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
DeadWrapCount = Annotated[StrictInt, Field(ge=2, le=8)]


class AssumptionSources(BaseModel):
    """Source status of engineering values supplied by the caller."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    service_factor: SourceStatus = SourceStatus.PROJECT_DEFAULT
    pitch_factor: SourceStatus = SourceStatus.PROJECT_DEFAULT
    brake_safety_factor: SourceStatus = SourceStatus.PROJECT_DEFAULT
    approved_core_ratio: SourceStatus = SourceStatus.PENDING_CONFIRMATION
    pulley_efficiency: SourceStatus = SourceStatus.PROJECT_DEFAULT
    dead_wrap_count: SourceStatus = SourceStatus.PROJECT_DEFAULT
    minimum_dd_ratio: SourceStatus = SourceStatus.PROJECT_DEFAULT
    backdrive_efficiency: SourceStatus = SourceStatus.PENDING_CONFIRMATION
    motor_duty_type: SourceStatus = SourceStatus.PROJECT_DEFAULT
    starts_per_hour: SourceStatus = SourceStatus.PROJECT_DEFAULT
    supply_voltage: SourceStatus = SourceStatus.PROJECT_DEFAULT
    supply_frequency: SourceStatus = SourceStatus.PROJECT_DEFAULT


class WinchDrumInput(BaseModel):
    """Validated user-facing input using the documented display units."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    rated_line_pull_kn: PositiveFloat
    rope_diameter_mm: PositiveFloat
    rope_speed_m_per_min: PositiveFloat
    target_rope_capacity_m: PositiveFloat
    force_input_location: ForceInputLocation = ForceInputLocation.LOAD_END
    speed_input_location: SpeedInputLocation = SpeedInputLocation.LOAD_END
    force_input_type: ForceInputType = ForceInputType.RATED
    service_factor: FactorAtLeastOne = 1.25
    total_efficiency: Annotated[float, Field(gt=0, le=1)]
    motor_rated_speed_rpm: PositiveFloat
    motor_type: Annotated[str, Field(min_length=1, max_length=64)]
    drum_core_diameter_mm: PositiveFloat | None = None
    drum_face_length_mm: PositiveFloat | None = None
    max_layers: PositiveLayerCount
    pitch_factor: FactorAtLeastOne = 1.10
    side_margin_mm: Annotated[float, Field(ge=0)]
    reeving_ratio: FactorAtLeastOne
    pulley_efficiency: Annotated[float, Field(gt=0, le=1)] = 0.95
    actual_groove_pitch_mm: PositiveFloat | None = None
    actual_usable_groove_count: PositiveLayerCount | None = None
    brake_safety_factor: FactorAtLeastOne = 1.50
    duty_class: Annotated[str, Field(min_length=1, max_length=64)]
    approved_core_ratio: DdRatio | None = None
    minimum_dd_ratio: DdRatio = 20.0
    dead_wrap_count: DeadWrapCount = Field(
        default=3,
        validation_alias=AliasChoices("dead_wrap_count", "dead_wraps"),
    )
    termination_allowance_m: Annotated[float, Field(ge=0)] = 0.0
    rope_type: Annotated[str, Field(min_length=1, max_length=64)] = "galvanized_steel_wire_rope"
    rope_construction: Annotated[str, Field(min_length=1, max_length=128)] = "6x36_IWRC"
    rope_material: Annotated[str, Field(min_length=1, max_length=128)] = "galvanized_steel"
    load_spectrum: Annotated[str, Field(min_length=1, max_length=128)] = "medium_load"
    environment_type: Annotated[str, Field(min_length=1, max_length=128)] = "indoor_normal"
    brake_basis_type: BrakeBasisType = BrakeBasisType.DESIGN_FORCE
    brake_installation_shaft: BrakeInstallationShaft = BrakeInstallationShaft.DRUM_OR_LOW_SPEED
    backdrive_efficiency: Annotated[float, Field(gt=0, le=1)] | None = None
    transmission_backdrive_type: TransmissionBackdriveType = TransmissionBackdriveType.REVERSIBLE
    allow_forward_efficiency_as_reverse_approx: StrictBool = False
    motor_duty_type: Annotated[str, Field(min_length=1, max_length=32)] = "S3"
    duty_cycle_percent: Annotated[float, Field(gt=0, le=100)] = 40.0
    starts_per_hour: Annotated[StrictInt, Field(ge=0, le=10000)] = 60
    supply_voltage: PositiveFloat = 380.0
    supply_frequency: PositiveFloat = 50.0
    motor_power_series_id: MotorPowerSeriesId = MotorPowerSeriesId.PROJECT_DEFAULT_IEC_KW
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
        "pulley_efficiency",
        "actual_groove_pitch_mm",
        "termination_allowance_m",
        "minimum_dd_ratio",
        "backdrive_efficiency",
        "duty_cycle_percent",
        "supply_voltage",
        "supply_frequency",
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

    @field_validator(
        "motor_type",
        "duty_class",
        "rope_type",
        "rope_construction",
        "rope_material",
        "load_spectrum",
        "environment_type",
        "motor_duty_type",
    )
    @classmethod
    def strip_and_require_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_drum_width_when_supplied(self) -> WinchDrumInput:
        if not 4.0 <= self.rope_diameter_mm <= 64.0:
            raise ValueError("钢丝绳直径必须在软件允许范围 4～64 mm 内")
        if self.actual_usable_groove_count is not None and self.dead_wrap_count > self.actual_usable_groove_count:
            raise ValueError("固定死圈数不能超过实际可用槽数")
        if self.drum_face_length_mm is None:
            return self

        usable_width_mm = self.drum_face_length_mm - 2.0 * self.side_margin_mm
        pitch_mm = self.actual_groove_pitch_mm or self.pitch_factor * self.rope_diameter_mm
        if usable_width_mm <= 0:
            raise ValueError("卷筒面长扣除两侧余量后必须大于 0")
        if usable_width_mm + 1e-9 < pitch_mm:
            raise ValueError("卷筒面长扣除两侧余量后必须至少容纳一圈")

        turns = math.floor((usable_width_mm + 1e-9) / pitch_mm)
        if self.actual_usable_groove_count is not None and self.actual_usable_groove_count > turns:
            raise ValueError("实际可用槽数与卷筒有效面宽及槽距不一致")
        if self.dead_wrap_count > turns:
            raise ValueError("固定死圈数不能超过第一层可容纳的完整圈数")
        return self

    @model_validator(mode="after")
    def validate_backdrive_approximation(self) -> WinchDrumInput:
        prohibited = {
            TransmissionBackdriveType.SELF_LOCKING,
            TransmissionBackdriveType.WORM,
            TransmissionBackdriveType.NON_REVERSIBLE,
            TransmissionBackdriveType.BACKDRIVE_PROHIBITED,
        }
        if self.allow_forward_efficiency_as_reverse_approx and self.transmission_backdrive_type in prohibited:
            raise ValueError("自锁、蜗杆或禁止反驱机构不得采用正向效率近似反向效率")
        return self

    @model_validator(mode="after")
    def validate_computational_range(self) -> WinchDrumInput:
        """Reject finite inputs whose documented SI operations overflow float."""

        force_n = self.rated_line_pull_kn * 1000.0
        if self.force_input_location is ForceInputLocation.LOAD_END:
            force_n /= self.reeving_ratio * self.pulley_efficiency
        speed_m_s = self.rope_speed_m_per_min / 60.0
        if self.speed_input_location is SpeedInputLocation.LOAD_END:
            speed_m_s *= self.reeving_ratio
        applied_service_factor = self.service_factor if self.force_input_type is ForceInputType.RATED else 1.0
        design_force_n = force_n * applied_service_factor
        required_power_w = design_force_n * speed_m_s / self.total_efficiency
        motor_speed_rad_s = self.motor_rated_speed_rpm * 2.0 * math.pi / 60.0
        core_diameter_m = (
            self.drum_core_diameter_mm / 1000.0
            if self.drum_core_diameter_mm is not None
            else (self.approved_core_ratio or self.minimum_dd_ratio - 1.0) * self.rope_diameter_mm / 1000.0
        )
        maximum_working_diameter_m = core_diameter_m + (2 * self.max_layers - 1) * self.rope_diameter_mm / 1000.0
        brake_torque_nm = design_force_n * maximum_working_diameter_m * self.brake_safety_factor / 2.0
        if not all(
            math.isfinite(value)
            for value in (
                force_n,
                speed_m_s,
                design_force_n,
                required_power_w,
                motor_speed_rad_s,
                core_diameter_m,
                maximum_working_diameter_m,
                brake_torque_nm,
            )
        ):
            raise ValueError("输入组合在 SI 换算或确定性计算中超出数值范围")
        return self

    @property
    def dead_wraps(self) -> int:
        """Compatibility accessor for the Phase 1 calculator and callers."""

        return self.dead_wrap_count

    def to_si(self) -> WinchDrumSIInput:
        """Convert display units to the single internal SI representation."""

        return WinchDrumSIInput(
            rated_line_pull_n=self.rated_line_pull_kn * 1000.0,
            rope_diameter_m=self.rope_diameter_mm / 1000.0,
            rope_speed_m_s=self.rope_speed_m_per_min / 60.0,
            target_rope_capacity_m=self.target_rope_capacity_m,
            service_factor=self.service_factor,
            force_input_location=self.force_input_location,
            speed_input_location=self.speed_input_location,
            force_input_type=self.force_input_type,
            total_efficiency=self.total_efficiency,
            motor_angular_speed_rad_s=self.motor_rated_speed_rpm * 2.0 * math.pi / 60.0,
            motor_type=self.motor_type,
            drum_core_diameter_m=(None if self.drum_core_diameter_mm is None else self.drum_core_diameter_mm / 1000.0),
            drum_face_length_m=(None if self.drum_face_length_mm is None else self.drum_face_length_mm / 1000.0),
            max_layers=self.max_layers,
            pitch_factor=self.pitch_factor,
            side_margin_m=self.side_margin_mm / 1000.0,
            reeving_ratio=self.reeving_ratio,
            pulley_efficiency=(
                1.0
                if self.reeving_ratio == 1 and self.assumption_sources.pulley_efficiency is SourceStatus.PROJECT_DEFAULT
                else self.pulley_efficiency
            ),
            actual_groove_pitch_m=(
                None if self.actual_groove_pitch_mm is None else self.actual_groove_pitch_mm / 1000.0
            ),
            actual_usable_groove_count=self.actual_usable_groove_count,
            brake_safety_factor=self.brake_safety_factor,
            duty_class=self.duty_class,
            approved_core_ratio=self.approved_core_ratio,
            minimum_dd_ratio=self.minimum_dd_ratio,
            dead_wrap_count=self.dead_wrap_count,
            termination_allowance_m=self.termination_allowance_m,
            rope_type=self.rope_type,
            rope_construction=self.rope_construction,
            rope_material=self.rope_material,
            load_spectrum=self.load_spectrum,
            environment_type=self.environment_type,
            brake_basis_type=self.brake_basis_type,
            brake_installation_shaft=self.brake_installation_shaft,
            backdrive_efficiency=self.backdrive_efficiency,
            transmission_backdrive_type=self.transmission_backdrive_type,
            allow_forward_efficiency_as_reverse_approx=(self.allow_forward_efficiency_as_reverse_approx),
            motor_duty_type=self.motor_duty_type,
            duty_cycle_percent=self.duty_cycle_percent,
            starts_per_hour=self.starts_per_hour,
            supply_voltage=self.supply_voltage,
            supply_frequency=self.supply_frequency,
            motor_power_series_id=self.motor_power_series_id,
            assumption_sources=self.assumption_sources,
        )


class WinchDrumSIInput(BaseModel):
    """Immutable internal input; dimensional values are SI except layer counts."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    rated_line_pull_n: float
    rope_diameter_m: float
    rope_speed_m_s: float
    target_rope_capacity_m: float
    service_factor: float
    force_input_location: ForceInputLocation
    speed_input_location: SpeedInputLocation
    force_input_type: ForceInputType
    total_efficiency: float
    motor_angular_speed_rad_s: float
    motor_type: str
    drum_core_diameter_m: float | None
    drum_face_length_m: float | None
    max_layers: int
    pitch_factor: float
    side_margin_m: float
    reeving_ratio: float
    pulley_efficiency: float
    actual_groove_pitch_m: float | None
    actual_usable_groove_count: int | None
    brake_safety_factor: float
    duty_class: str
    approved_core_ratio: float | None
    minimum_dd_ratio: float
    dead_wrap_count: int
    termination_allowance_m: float
    rope_type: str
    rope_construction: str
    rope_material: str
    load_spectrum: str
    environment_type: str
    brake_basis_type: BrakeBasisType
    brake_installation_shaft: BrakeInstallationShaft
    backdrive_efficiency: float | None
    transmission_backdrive_type: TransmissionBackdriveType
    allow_forward_efficiency_as_reverse_approx: bool
    motor_duty_type: str
    duty_cycle_percent: float
    starts_per_hour: int
    supply_voltage: float
    supply_frequency: float
    motor_power_series_id: MotorPowerSeriesId
    assumption_sources: AssumptionSources

    @property
    def dead_wraps(self) -> int:
        return self.dead_wrap_count


class AssumptionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    key: str
    value: float | int | bool | str | None
    unit: str | None = None
    source_status: SourceStatus
    note: str


class WarningRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    code: WarningCode
    severity: WarningSeverity
    title: str
    message: str
    affected_result: tuple[str, ...] = ()
    recommended_action: str

    @property
    def affected_fields(self) -> tuple[str, ...]:
        return self.affected_result


class FormulaStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    sequence: int
    formula_id: str
    expression: str
    variables: dict[str, float | int | str]
    result_value: float | int
    unit: str
    classification: ResultClassification


class ScalarResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

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
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

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
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

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

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    module_id: str
    module_version: str
    calculation_model_version: str
    status: CalculationStatus
    input_si: WinchDrumSIInput
    drum_rope_force_n: ScalarResult
    drum_rope_speed_m_s: ScalarResult
    service_factor_applied: bool
    design_line_pull_n: ScalarResult
    theoretical_load_power_w: ScalarResult
    minimum_motor_power_w: ScalarResult
    suggested_motor_power_w: ScalarResult
    used_or_suggested_core_diameter_m: ScalarResult
    used_or_suggested_drum_face_length_m: ScalarResult
    pitch_m: float
    pitch_basis: str
    usable_width_m: float | None
    theoretical_turns_per_layer: int | None
    final_turns_per_layer: int | None
    turns_basis: str | None
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
    dead_wrap_length_m: float | None
    required_total_storage_m: float | None
    theoretical_total_capacity_m: float | None
    available_work_rope_length_m: float | None
    dd_ratio_first_layer: float | None
    empty_working_diameter_m: float | None
    full_working_diameter_m: float | None
    max_layer_working_diameter_m: float | None
    empty_drum_speed_rpm: float | None
    full_drum_speed_rpm: float | None
    max_layer_drum_speed_rpm: float | None
    reference_ratio_empty: float | None
    reference_ratio_full: float | None
    reference_ratio_max_layer: float | None
    reference_ratio_nominal: float | None
    low_speed_brake_torque_nm: ScalarResult
    high_speed_brake_torque_ref_nm: ScalarResult
    motor_selection_status: str
    unchecked_items: tuple[str, ...]
    ideal_load_force_n: ScalarResult
    ideal_load_speed_m_s: ScalarResult
    optimizer_candidates: tuple[DrumCandidate, ...]
    selected_candidate: DrumCandidate | None
    calculation_steps: tuple[FormulaStep, ...]
    warnings: tuple[WarningRecord, ...]
    assumptions: tuple[AssumptionRecord, ...]
    disclaimer: str
