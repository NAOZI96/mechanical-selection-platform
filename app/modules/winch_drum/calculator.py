"""Pure deterministic calculation core for winch and drum selection.

This module intentionally has no FastAPI, Jinja2, SQLite, filesystem, clock,
network, or PDF dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .assumptions import (
    CALCULATION_MODEL_VERSION,
    DISCLAIMER,
    MODULE_ID,
    MODULE_VERSION,
    MOTOR_POWER_SERIES_KW,
    build_assumptions,
)
from .optimizer import centerline_turn_length, search_drum_candidates
from .schema import (
    CalculationStatus,
    DrumCandidate,
    ForceInputLocation,
    ForceInputType,
    FormulaStep,
    LayerResult,
    ResultClassification,
    ScalarResult,
    SourceStatus,
    SpeedInputLocation,
    TransmissionBackdriveType,
    WarningCode,
    WarningRecord,
    WarningSeverity,
    WinchDrumInput,
    WinchDrumResult,
    WinchDrumSIInput,
)


@dataclass
class _StepRecorder:
    steps: list[FormulaStep] = field(default_factory=list)

    def add(
        self,
        formula_id: str,
        expression: str,
        variables: dict[str, float | int | str],
        result_value: float | int,
        unit: str,
        classification: ResultClassification = ResultClassification.CALCULATED,
    ) -> None:
        self.steps.append(
            FormulaStep(
                sequence=len(self.steps) + 1,
                formula_id=formula_id,
                expression=expression,
                variables=variables,
                result_value=result_value,
                unit=unit,
                classification=classification,
            )
        )


@dataclass(frozen=True)
class _CapacitySummary:
    layers: tuple[LayerResult, ...]
    turns_per_layer: int
    theoretical_turns_per_layer: int
    turns_basis: str
    usable_width_m: float
    capacity_satisfied: bool
    actual_layers: int | None
    capacity_at_actual_layers_m: float | None
    capacity_at_max_layers_m: float
    capacity_margin_m: float | None
    capacity_margin_pct: float | None
    capacity_shortfall_m: float | None
    dead_wrap_length_m: float
    theoretical_total_capacity_m: float
    available_work_rope_length_m: float


def _scalar(
    value: float | None,
    unit: str,
    classification: ResultClassification,
    formula_ids: tuple[str, ...],
    reason: str | None = None,
) -> ScalarResult:
    return ScalarResult(
        value=value,
        unit=unit,
        classification=classification,
        formula_ids=formula_ids,
        reason=reason,
    )


def _record_unit_steps(source: WinchDrumInput, data: WinchDrumSIInput, recorder: _StepRecorder) -> None:
    recorder.add(
        "UNIT-001",
        "F_r = rated_line_pull_kn * 1000",
        {"rated_line_pull_kn": source.rated_line_pull_kn},
        data.rated_line_pull_n,
        "N",
    )
    recorder.add(
        "UNIT-002",
        "d = rope_diameter_mm / 1000",
        {"rope_diameter_mm": source.rope_diameter_mm},
        data.rope_diameter_m,
        "m",
    )
    recorder.add(
        "UNIT-003",
        "v = rope_speed_m_per_min / 60",
        {"rope_speed_m_per_min": source.rope_speed_m_per_min},
        data.rope_speed_m_s,
        "m/s",
    )
    if data.drum_core_diameter_m is not None:
        recorder.add(
            "UNIT-004",
            "D_c = drum_core_diameter_mm / 1000",
            {"drum_core_diameter_mm": source.drum_core_diameter_mm or 0.0},
            data.drum_core_diameter_m,
            "m",
        )
    if data.drum_face_length_m is not None:
        recorder.add(
            "UNIT-005",
            "B = drum_face_length_mm / 1000",
            {"drum_face_length_mm": source.drum_face_length_mm or 0.0},
            data.drum_face_length_m,
            "m",
        )
    recorder.add(
        "UNIT-006",
        "b = side_margin_mm / 1000",
        {"side_margin_mm": source.side_margin_mm},
        data.side_margin_m,
        "m",
    )


def _resolve_core_diameter(
    data: WinchDrumSIInput, recorder: _StepRecorder
) -> tuple[float | None, ResultClassification, str | None]:
    if data.drum_core_diameter_m is not None:
        recorder.add(
            "DRUM-001",
            "D_c,used = D_c,input",
            {"D_c_input": data.drum_core_diameter_m},
            data.drum_core_diameter_m,
            "m",
        )
        return data.drum_core_diameter_m, ResultClassification.CALCULATED, None

    if data.approved_core_ratio is not None:
        core_diameter_m = (data.approved_core_ratio - 1.0) * data.rope_diameter_m
        recorder.add(
            "DRUM-002",
            "D_c,suggested = (R_Dd - 1) * d",
            {"R_Dd": data.approved_core_ratio, "d": data.rope_diameter_m},
            core_diameter_m,
            "m",
            ResultClassification.PRELIMINARY,
        )
        return core_diameter_m, ResultClassification.PRELIMINARY, None

    core_diameter_m = (data.minimum_dd_ratio - 1.0) * data.rope_diameter_m
    recorder.add(
        "DRUM-002",
        "D_c,suggested = (R_Dd - 1) * d",
        {"R_Dd": data.minimum_dd_ratio, "d": data.rope_diameter_m},
        core_diameter_m,
        "m",
        ResultClassification.PRELIMINARY,
    )
    return core_diameter_m, ResultClassification.PRELIMINARY, None


def _resolve_geometry(
    data: WinchDrumSIInput,
    core_diameter_m: float | None,
    pitch_m: float,
    recorder: _StepRecorder,
) -> tuple[
    float | None,
    int,
    tuple[DrumCandidate, ...],
    DrumCandidate | None,
    ResultClassification,
    str | None,
]:
    if data.drum_face_length_m is not None:
        return (
            data.drum_face_length_m,
            data.max_layers,
            (),
            None,
            ResultClassification.CALCULATED,
            None,
        )

    if core_diameter_m is None:
        return (
            None,
            0,
            (),
            None,
            ResultClassification.REVIEW_REQUIRED,
            "缺少可确认的芯径，无法执行卷筒几何候选搜索。",
        )

    candidates = search_drum_candidates(
        core_diameter_m=core_diameter_m,
        rope_diameter_m=data.rope_diameter_m,
        pitch_m=pitch_m,
        target_capacity_m=data.target_rope_capacity_m + data.termination_allowance_m,
        side_margin_m=data.side_margin_m,
        max_layers=data.max_layers,
        dead_wraps=data.dead_wraps,
    )
    selected = candidates[0]
    recorder.add(
        "WIDTH-001",
        "B_u,min = N_req * p",
        {"N_req": selected.turns_per_layer, "p": pitch_m},
        selected.turns_per_layer * pitch_m,
        "m",
        ResultClassification.PRELIMINARY,
    )
    recorder.add(
        "WIDTH-002",
        "B_suggested = B_u,min + 2*b",
        {
            "B_u_min": selected.turns_per_layer * pitch_m,
            "b": data.side_margin_m,
        },
        selected.face_length_m,
        "m",
        ResultClassification.PRELIMINARY,
    )
    return (
        selected.face_length_m,
        selected.layer_limit,
        candidates,
        selected,
        ResultClassification.PRELIMINARY,
        None,
    )


def _turns_per_full_layer(usable_width_m: float, pitch_m: float) -> int:
    epsilon_m = max(abs(usable_width_m), abs(pitch_m), 1.0) * 1e-12
    return math.floor((usable_width_m + epsilon_m) / pitch_m)


def _calculate_layered_capacity(
    *,
    data: WinchDrumSIInput,
    core_diameter_m: float,
    face_length_m: float,
    layer_limit: int,
    pitch_m: float,
    recorder: _StepRecorder,
) -> _CapacitySummary:
    usable_width_m = face_length_m - 2.0 * data.side_margin_m
    theoretical_turns_per_layer = _turns_per_full_layer(usable_width_m, pitch_m)
    turns_per_layer = data.actual_usable_groove_count or theoretical_turns_per_layer
    turns_basis = (
        "actual_usable_groove_count"
        if data.actual_usable_groove_count is not None
        else ("actual_groove_pitch" if data.actual_groove_pitch_m is not None else "theoretical_pitch")
    )
    if turns_per_layer < 1:
        raise ValueError("卷筒可用宽度不足以容纳一圈")
    if data.dead_wraps > turns_per_layer:
        raise ValueError("固定死圈数不能超过第一层完整圈数")

    recorder.add(
        "GEOM-002",
        "B_u = B - 2*b",
        {"B": face_length_m, "b": data.side_margin_m},
        usable_width_m,
        "m",
    )
    recorder.add(
        "GEOM-003",
        ("N_used = N_actual" if data.actual_usable_groove_count is not None else "N_full = floor((B_u + epsilon) / p)"),
        (
            {"N_actual": data.actual_usable_groove_count}
            if data.actual_usable_groove_count is not None
            else {"B_u": usable_width_m, "p": pitch_m}
        ),
        turns_per_layer,
        "turn",
    )
    recorder.add(
        "GEOM-004",
        "B_used = N_full * p",
        {"N_full": turns_per_layer, "p": pitch_m},
        turns_per_layer * pitch_m,
        "m",
    )

    layers: list[LayerResult] = []
    cumulative_usable_m = 0.0
    cumulative_used_m = 0.0
    required_usable_capacity_m = data.target_rope_capacity_m + data.termination_allowance_m
    remaining_target_m = required_usable_capacity_m
    actual_layers: int | None = None
    capacity_at_actual_layers_m: float | None = None

    theoretical_total_capacity_m = 0.0
    dead_wrap_length_m = 0.0
    for layer_number in range(1, layer_limit + 1):
        center_diameter_m = core_diameter_m + (2 * layer_number - 1) * data.rope_diameter_m
        turn_length_m = centerline_turn_length(core_diameter_m, data.rope_diameter_m, pitch_m, layer_number)
        usable_turns = turns_per_layer - data.dead_wraps if layer_number == 1 else turns_per_layer
        gross_capacity_m = turns_per_layer * turn_length_m
        theoretical_total_capacity_m += gross_capacity_m
        if layer_number == 1:
            dead_wrap_length_m = data.dead_wrap_count * turn_length_m
        usable_capacity_m = usable_turns * turn_length_m
        used_capacity_m = min(max(remaining_target_m, 0.0), usable_capacity_m)
        used_turns = used_capacity_m / turn_length_m

        cumulative_usable_m += usable_capacity_m
        cumulative_used_m += used_capacity_m
        remaining_target_m -= used_capacity_m

        recorder.add(
            "CAP-001",
            "D_j = D_c + (2*j - 1)*d",
            {"D_c": core_diameter_m, "j": layer_number, "d": data.rope_diameter_m},
            center_diameter_m,
            "m",
        )
        recorder.add(
            "CAP-002",
            "l_turn,j = sqrt((pi*D_j)^2 + p^2)",
            {"D_j": center_diameter_m, "p": pitch_m},
            turn_length_m,
            "m/turn",
        )
        recorder.add(
            "CAP-003",
            "L_layer,j,gross = N_full * l_turn,j",
            {"N_full": turns_per_layer, "l_turn_j": turn_length_m},
            gross_capacity_m,
            "m",
        )
        recorder.add(
            "CAP-004",
            "L_layer,j,usable = usable_turns * l_turn,j",
            {"usable_turns": usable_turns, "l_turn_j": turn_length_m},
            usable_capacity_m,
            "m",
        )
        recorder.add(
            "CAP-005",
            "L_total,k = sum(L_layer,j,usable)",
            {"k": layer_number, "L_layer_usable": usable_capacity_m},
            cumulative_usable_m,
            "m",
        )

        layers.append(
            LayerResult(
                layer_number=layer_number,
                center_diameter_m=center_diameter_m,
                turn_length_m=turn_length_m,
                full_turns=turns_per_layer,
                usable_turns=usable_turns,
                used_turns=used_turns,
                gross_capacity_m=gross_capacity_m,
                usable_capacity_m=usable_capacity_m,
                used_capacity_m=used_capacity_m,
                cumulative_usable_capacity_m=cumulative_usable_m,
                cumulative_used_capacity_m=cumulative_used_m,
            )
        )

        if actual_layers is None and cumulative_usable_m + 1e-12 >= required_usable_capacity_m:
            actual_layers = layer_number
            capacity_at_actual_layers_m = cumulative_usable_m

    capacity_satisfied = actual_layers is not None
    if capacity_satisfied:
        assert capacity_at_actual_layers_m is not None
        capacity_margin_m = capacity_at_actual_layers_m - data.termination_allowance_m - data.target_rope_capacity_m
        capacity_margin_pct = 100.0 * capacity_margin_m / data.target_rope_capacity_m
        capacity_shortfall_m = None
        recorder.add(
            "CAP-006",
            "z_actual = min(k where L_total,k >= L_t)",
            {"L_t": required_usable_capacity_m},
            actual_layers,
            "layer",
        )
        recorder.add(
            "CAP-007",
            "L_margin = L_total,z_actual - L_t",
            {
                "L_total_actual": capacity_at_actual_layers_m,
                "L_t": required_usable_capacity_m,
            },
            capacity_margin_m,
            "m",
        )
        recorder.add(
            "CAP-008",
            "capacity_margin_pct = 100*L_margin/L_t",
            {"L_margin": capacity_margin_m, "L_t": data.target_rope_capacity_m},
            capacity_margin_pct,
            "%",
        )
    else:
        capacity_margin_m = None
        capacity_margin_pct = None
        capacity_shortfall_m = required_usable_capacity_m - cumulative_usable_m

    return _CapacitySummary(
        layers=tuple(layers),
        turns_per_layer=turns_per_layer,
        theoretical_turns_per_layer=theoretical_turns_per_layer,
        turns_basis=turns_basis,
        usable_width_m=usable_width_m,
        capacity_satisfied=capacity_satisfied,
        actual_layers=actual_layers,
        capacity_at_actual_layers_m=capacity_at_actual_layers_m,
        capacity_at_max_layers_m=cumulative_usable_m,
        capacity_margin_m=capacity_margin_m,
        capacity_margin_pct=capacity_margin_pct,
        capacity_shortfall_m=capacity_shortfall_m,
        dead_wrap_length_m=dead_wrap_length_m,
        theoretical_total_capacity_m=theoretical_total_capacity_m,
        available_work_rope_length_m=max(0.0, cumulative_usable_m - data.termination_allowance_m),
    )


def _warning(
    code: WarningCode,
    severity: WarningSeverity,
    message: str,
    *affected_fields: str,
) -> WarningRecord:
    return WarningRecord(
        code=code,
        severity=severity,
        title=code.value,
        message=message,
        affected_result=tuple(affected_fields),
        recommended_action="由机械工程师结合适用标准、工况或制造商数据复核。",
    )


def _build_warnings(
    data: WinchDrumSIInput,
    *,
    core_diameter_m: float | None,
    capacity_satisfied: bool,
    geometry_available: bool,
    speed_varies: bool,
) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = []
    if core_diameter_m is None:
        warnings.append(
            _warning(
                WarningCode.CORE_RULE_MISSING,
                WarningSeverity.HIGH,
                "芯径和经批准的 D/d 规则均缺失。",
                "drum_core_diameter_mm",
                "approved_core_ratio",
            )
        )
    elif data.drum_core_diameter_m is not None or (
        data.approved_core_ratio is not None
        and data.assumption_sources.approved_core_ratio is SourceStatus.PENDING_CONFIRMATION
    ):
        warnings.append(
            _warning(
                WarningCode.CORE_UNVERIFIED,
                WarningSeverity.HIGH,
                "采用的芯径或 D/d 规则尚未完成绳型、弯曲比和适用标准核验。",
                "drum_core_diameter_mm",
            )
        )

    if geometry_available and not capacity_satisfied:
        warnings.append(
            _warning(
                WarningCode.CAPACITY_INSUFFICIENT,
                WarningSeverity.HIGH,
                "最大评估层数下的逐层离散容量小于目标容绳量。",
                "target_rope_capacity_m",
                "max_layers",
            )
        )
    if speed_varies:
        warnings.append(
            _warning(
                WarningCode.FIXED_RATIO_SPEED_VARIATION,
                WarningSeverity.WARNING,
                "固定速比与固定电机转速不能同时保持空卷和满卷绳速恒定。",
                "motor_rated_speed_rpm",
            )
        )

    warnings.append(
        _warning(
            WarningCode.MOTOR_SELECTION_INCOMPLETE,
            WarningSeverity.HIGH,
            "缺少工作制、启动、过载、热容量和标准功率系列校核。",
            "minimum_motor_power_w",
        )
    )
    if geometry_available:
        warnings.append(
            _warning(
                WarningCode.BRAKE_STATIC_ONLY,
                WarningSeverity.HIGH,
                "制动力矩仅为静态保持参考，未覆盖动态和热容量。",
                "low_speed_brake_torque_nm",
            )
        )

    backdrive_prohibited = data.transmission_backdrive_type in {
        TransmissionBackdriveType.SELF_LOCKING,
        TransmissionBackdriveType.WORM,
        TransmissionBackdriveType.NON_REVERSIBLE,
        TransmissionBackdriveType.BACKDRIVE_PROHIBITED,
    }
    if data.allow_forward_efficiency_as_reverse_approx and geometry_available and not backdrive_prohibited:
        warnings.append(
            _warning(
                WarningCode.REVERSE_EFFICIENCY_APPROXIMATED,
                WarningSeverity.HIGH,
                "反向效率暂采用正向效率近似，高速轴制动力矩仅供初选。",
                "high_speed_brake_torque_ref_nm",
            )
        )
    elif data.backdrive_efficiency is None or backdrive_prohibited:
        warnings.append(
            _warning(
                WarningCode.REVERSE_EFFICIENCY_UNKNOWN,
                WarningSeverity.HIGH,
                (
                    "传动被声明为自锁、不可逆或禁止反驱，高速轴制动力矩保持待校核。"
                    if backdrive_prohibited
                    else "反向传动效率未知，高速轴制动力矩保持待校核。"
                ),
                "high_speed_brake_torque_ref_nm",
            )
        )

    if data.assumption_sources.service_factor is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            _warning(
                WarningCode.SERVICE_FACTOR_SOURCE,
                WarningSeverity.WARNING,
                "使用系数来源待机械工程师确认。",
                "service_factor",
            )
        )
    if data.assumption_sources.pitch_factor is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            _warning(
                WarningCode.PITCH_FACTOR_SOURCE,
                WarningSeverity.WARNING,
                "排绳节距修正系数来源待机械工程师确认。",
                "pitch_factor",
            )
        )
    warnings.extend(
        (
            _warning(
                WarningCode.DUTY_CLASS_INFO_ONLY,
                WarningSeverity.WARNING,
                "工作级别仅记录和提示，未自动映射任何系数。",
                "duty_class",
            ),
            _warning(
                WarningCode.ROPE_STRENGTH_NOT_CHECKED,
                WarningSeverity.HIGH,
                "缆绳强度和破断拉力未校核。",
                "rope_diameter_mm",
            ),
            _warning(
                WarningCode.DRUM_STRUCTURE_NOT_CHECKED,
                WarningSeverity.HIGH,
                "卷筒筒体、法兰、焊缝、轴和轴承结构未校核。",
            ),
        )
    )
    if data.dead_wrap_count < 3:
        warnings.append(
            _warning(
                WarningCode.DEAD_WRAP_BELOW_DEFAULT,
                WarningSeverity.HIGH,
                "固定死圈数低于项目初选默认值 3 圈。",
                "dead_wrap_count",
            )
        )
    if data.reeving_ratio > 1 and (data.assumption_sources.pulley_efficiency is SourceStatus.PROJECT_DEFAULT):
        warnings.append(
            _warning(
                WarningCode.PULLEY_EFFICIENCY_DEFAULT,
                WarningSeverity.WARNING,
                "滑轮效率采用项目初选默认值 0.95。",
                "pulley_efficiency",
            )
        )
    if not 0.006 <= data.rope_diameter_m <= 0.032:
        warnings.append(
            _warning(
                WarningCode.ROPE_DIAMETER_OUTSIDE_VALIDATED_RANGE,
                WarningSeverity.WARNING,
                "钢丝绳直径超出当前主要验证范围 6～32 mm。",
                "rope_diameter_m",
            )
        )
    if data.assumption_sources.minimum_dd_ratio is SourceStatus.PROJECT_DEFAULT:
        warnings.append(
            _warning(
                WarningCode.DD_PROJECT_DEFAULT,
                WarningSeverity.WARNING,
                "D/d 采用项目初选默认值，尚未按具体标准确认。",
                "minimum_dd_ratio",
            )
        )
    warnings.extend(
        (
            _warning(
                WarningCode.DYNAMIC_BRAKE_NOT_CHECKED,
                WarningSeverity.HIGH,
                "当前仅完成静态保持制动力矩初选，未完成动态和热容量校核。",
                "low_speed_brake_torque_nm",
            ),
            _warning(
                WarningCode.MOTOR_THERMAL_NOT_CHECKED,
                WarningSeverity.HIGH,
                "电机启动、工作制和热容量尚未完成制造商校核。",
                "suggested_motor_power_w",
            ),
            _warning(
                WarningCode.STANDARD_CLAUSE_NOT_CONFIRMED,
                WarningSeverity.WARNING,
                "适用标准版本、条款号和页码尚未通过正式文本确认。",
            ),
        )
    )
    severity_order = {
        WarningSeverity.BLOCKING: 0,
        WarningSeverity.HIGH: 1,
        WarningSeverity.WARNING: 2,
        WarningSeverity.INFO: 3,
    }
    return tuple(sorted(warnings, key=lambda item: (severity_order[item.severity], item.code.value)))


def calculate(source: WinchDrumInput) -> WinchDrumResult:
    """Run one deterministic, side-effect-free winch/drum calculation."""

    data = source.to_si()
    recorder = _StepRecorder()
    _record_unit_steps(source, data, recorder)

    drum_rope_force_n = (
        data.rated_line_pull_n
        if data.force_input_location is ForceInputLocation.DRUM_ROPE_END
        else data.rated_line_pull_n / (data.reeving_ratio * data.pulley_efficiency)
    )
    drum_rope_speed_m_s = (
        data.rope_speed_m_s
        if data.speed_input_location is SpeedInputLocation.DRUM_ROPE_END
        else data.reeving_ratio * data.rope_speed_m_s
    )
    service_factor_applied = data.force_input_type is ForceInputType.RATED
    applied_service_factor = data.service_factor if service_factor_applied else 1.0
    design_line_pull_n = drum_rope_force_n * applied_service_factor
    theoretical_load_power_w = design_line_pull_n * drum_rope_speed_m_s
    minimum_motor_power_w = theoretical_load_power_w / data.total_efficiency
    recorder.add(
        "REEVE-001",
        "F_drum = F_input/(m*eta_pulley) when input is at load end",
        {
            "F_input": data.rated_line_pull_n,
            "m": data.reeving_ratio,
            "eta_pulley": data.pulley_efficiency,
            "location": data.force_input_location.value,
        },
        drum_rope_force_n,
        "N",
    )
    recorder.add(
        "REEVE-002",
        "v_drum = m*v_input when input is at load end",
        {
            "v_input": data.rope_speed_m_s,
            "m": data.reeving_ratio,
            "location": data.speed_input_location.value,
        },
        drum_rope_speed_m_s,
        "m/s",
    )
    recorder.add(
        "FORCE-001",
        "F_d = F_r * K_s",
        {"F_reference": drum_rope_force_n, "K_s_applied": applied_service_factor},
        design_line_pull_n,
        "N",
    )
    recorder.add(
        "POWER-001",
        "P_load = F_d * v",
        {"F_d": design_line_pull_n, "v_drum": drum_rope_speed_m_s},
        theoretical_load_power_w,
        "W",
    )
    recorder.add(
        "POWER-002",
        "P_motor_min = P_load / eta",
        {"P_load": theoretical_load_power_w, "eta": data.total_efficiency},
        minimum_motor_power_w,
        "W",
    )

    pitch_m = data.actual_groove_pitch_m or data.pitch_factor * data.rope_diameter_m
    pitch_basis = "actual_groove_pitch" if data.actual_groove_pitch_m is not None else "pitch_factor"
    recorder.add(
        "GEOM-001",
        "p = p_actual" if data.actual_groove_pitch_m is not None else "p = K_p * d",
        (
            {"p_actual": data.actual_groove_pitch_m}
            if data.actual_groove_pitch_m is not None
            else {"K_p": data.pitch_factor, "d": data.rope_diameter_m}
        ),
        pitch_m,
        "m",
    )
    core_diameter_m, core_classification, core_reason = _resolve_core_diameter(data, recorder)
    (
        face_length_m,
        evaluated_layers,
        optimizer_candidates,
        selected_candidate,
        face_classification,
        face_reason,
    ) = _resolve_geometry(data, core_diameter_m, pitch_m, recorder)

    capacity: _CapacitySummary | None = None
    empty_working_diameter_m: float | None = None
    full_working_diameter_m: float | None = None
    max_layer_working_diameter_m: float | None = None
    empty_drum_speed_rpm: float | None = None
    full_drum_speed_rpm: float | None = None
    max_layer_drum_speed_rpm: float | None = None
    ratio_empty: float | None = None
    ratio_full: float | None = None
    ratio_max_layer: float | None = None
    ratio_nominal: float | None = None
    low_speed_brake_torque_nm: float | None = None
    high_speed_brake_torque_ref_nm: float | None = None

    if core_diameter_m is not None and face_length_m is not None:
        capacity = _calculate_layered_capacity(
            data=data,
            core_diameter_m=core_diameter_m,
            face_length_m=face_length_m,
            layer_limit=evaluated_layers,
            pitch_m=pitch_m,
            recorder=recorder,
        )
        outer_layer_count = capacity.actual_layers or evaluated_layers
        empty_working_diameter_m = core_diameter_m + data.rope_diameter_m
        outer_working_diameter_m = core_diameter_m + (2 * outer_layer_count - 1) * data.rope_diameter_m
        empty_drum_speed_rpm = 60.0 * drum_rope_speed_m_s / (math.pi * empty_working_diameter_m)
        outer_drum_speed_rpm = 60.0 * drum_rope_speed_m_s / (math.pi * outer_working_diameter_m)
        motor_speed_rpm = data.motor_angular_speed_rad_s * 60.0 / (2.0 * math.pi)
        ratio_empty = motor_speed_rpm / empty_drum_speed_rpm
        ratio_outer = motor_speed_rpm / outer_drum_speed_rpm
        if capacity.capacity_satisfied:
            full_working_diameter_m = outer_working_diameter_m
            full_drum_speed_rpm = outer_drum_speed_rpm
            ratio_full = ratio_outer
        else:
            max_layer_working_diameter_m = outer_working_diameter_m
            max_layer_drum_speed_rpm = outer_drum_speed_rpm
            ratio_max_layer = ratio_outer
        reference_diameter_m = (empty_working_diameter_m + outer_working_diameter_m) / 2.0
        reference_drum_speed_rpm = 60.0 * drum_rope_speed_m_s / (math.pi * reference_diameter_m)
        ratio_nominal = motor_speed_rpm / reference_drum_speed_rpm
        outer_label = "full" if capacity.capacity_satisfied else "max_layer"

        recorder.add(
            "SPEED-001",
            "D_work,empty = D_c + d",
            {"D_c": core_diameter_m, "d": data.rope_diameter_m},
            empty_working_diameter_m,
            "m",
        )
        recorder.add(
            "SPEED-002",
            f"D_work,{outer_label} = D_c + (2*z - 1)*d",
            {
                "D_c": core_diameter_m,
                "z": outer_layer_count,
                "d": data.rope_diameter_m,
            },
            outer_working_diameter_m,
            "m",
        )
        recorder.add(
            "SPEED-003",
            "n_drum = 60*v/(pi*D_work)",
            {"v": drum_rope_speed_m_s, "D_work": reference_diameter_m},
            reference_drum_speed_rpm,
            "r/min",
        )
        recorder.add(
            "SPEED-004",
            "n_empty = 60*v/(pi*D_work,empty)",
            {"v": drum_rope_speed_m_s, "D_work_empty": empty_working_diameter_m},
            empty_drum_speed_rpm,
            "r/min",
        )
        recorder.add(
            "SPEED-005",
            f"n_{outer_label} = 60*v/(pi*D_work,{outer_label})",
            {"v": drum_rope_speed_m_s, f"D_work_{outer_label}": outer_working_diameter_m},
            outer_drum_speed_rpm,
            "r/min",
        )
        recorder.add(
            "RATIO-001",
            "i_empty = n_m/n_empty",
            {
                "n_m": motor_speed_rpm,
                "n_empty": empty_drum_speed_rpm,
            },
            ratio_empty,
            "ratio",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "RATIO-001",
            f"i_{outer_label} = n_m/n_{outer_label}",
            {
                "n_m": motor_speed_rpm,
                f"n_{outer_label}": outer_drum_speed_rpm,
            },
            ratio_outer,
            "ratio",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "RATIO-002",
            "i_ref = n_m / (60*v/(pi*D_ref))",
            {"n_m": motor_speed_rpm, "v": drum_rope_speed_m_s, "D_ref": reference_diameter_m},
            ratio_nominal,
            "ratio",
            ResultClassification.PRELIMINARY,
        )

        low_speed_brake_torque_nm = design_line_pull_n * (outer_working_diameter_m / 2.0) * data.brake_safety_factor
        recorder.add(
            "BRAKE-001",
            f"T_brake,low = F_design*(D_work,{outer_label}/2)*K_b",
            {
                "F_design": design_line_pull_n,
                f"D_work_{outer_label}": outer_working_diameter_m,
                "K_b": data.brake_safety_factor,
            },
            low_speed_brake_torque_nm,
            "N*m",
            ResultClassification.PRELIMINARY,
        )
        backdrive_prohibited = data.transmission_backdrive_type in {
            TransmissionBackdriveType.SELF_LOCKING,
            TransmissionBackdriveType.WORM,
            TransmissionBackdriveType.NON_REVERSIBLE,
            TransmissionBackdriveType.BACKDRIVE_PROHIBITED,
        }
        effective_backdrive_efficiency = None if backdrive_prohibited else data.backdrive_efficiency
        if (
            effective_backdrive_efficiency is None
            and data.allow_forward_efficiency_as_reverse_approx
            and not backdrive_prohibited
        ):
            effective_backdrive_efficiency = data.total_efficiency
        if effective_backdrive_efficiency is not None:
            high_speed_brake_torque_ref_nm = low_speed_brake_torque_nm * effective_backdrive_efficiency / ratio_nominal
            recorder.add(
                "BRAKE-002",
                "T_brake,high,ref = T_brake,low*eta_back/i_ref",
                {
                    "T_brake_low": low_speed_brake_torque_nm,
                    "i_ref": ratio_nominal,
                    "eta_back": effective_backdrive_efficiency,
                },
                high_speed_brake_torque_ref_nm,
                "N*m",
                ResultClassification.PRELIMINARY,
            )

    ideal_load_force_n = drum_rope_force_n * data.reeving_ratio * data.pulley_efficiency
    ideal_load_speed_m_s = drum_rope_speed_m_s / data.reeving_ratio

    suggested_motor_power_kw = next(
        (power_kw for power_kw in MOTOR_POWER_SERIES_KW if power_kw * 1000.0 + 1e-12 >= minimum_motor_power_w),
        None,
    )
    suggested_motor_power_w = None if suggested_motor_power_kw is None else suggested_motor_power_kw * 1000.0
    motor_selection_status = (
        "out_of_configured_range" if suggested_motor_power_w is None else "selected_from_configured_series"
    )

    geometry_available = capacity is not None
    capacity_satisfied = capacity.capacity_satisfied if capacity else False
    speed_varies = bool(
        empty_working_diameter_m is not None
        and (full_working_diameter_m is not None or max_layer_working_diameter_m is not None)
        and not math.isclose(
            empty_working_diameter_m,
            full_working_diameter_m or max_layer_working_diameter_m or empty_working_diameter_m,
        )
    )
    warnings = _build_warnings(
        data,
        core_diameter_m=core_diameter_m,
        capacity_satisfied=capacity_satisfied,
        geometry_available=geometry_available,
        speed_varies=speed_varies,
    )

    return WinchDrumResult(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        status=(CalculationStatus.COMPLETED_WITH_WARNINGS if warnings else CalculationStatus.COMPLETED),
        input_si=data,
        drum_rope_force_n=_scalar(
            drum_rope_force_n,
            "N",
            ResultClassification.CALCULATED,
            ("REEVE-001",),
        ),
        drum_rope_speed_m_s=_scalar(
            drum_rope_speed_m_s,
            "m/s",
            ResultClassification.CALCULATED,
            ("REEVE-002",),
        ),
        service_factor_applied=service_factor_applied,
        design_line_pull_n=_scalar(
            design_line_pull_n,
            "N",
            ResultClassification.CALCULATED,
            ("FORCE-001",),
        ),
        theoretical_load_power_w=_scalar(
            theoretical_load_power_w,
            "W",
            ResultClassification.CALCULATED,
            ("POWER-001",),
        ),
        minimum_motor_power_w=_scalar(
            minimum_motor_power_w,
            "W",
            ResultClassification.CALCULATED,
            ("POWER-002",),
        ),
        suggested_motor_power_w=_scalar(
            suggested_motor_power_w,
            "W",
            (
                ResultClassification.PRELIMINARY
                if suggested_motor_power_w is not None
                else ResultClassification.REVIEW_REQUIRED
            ),
            ("POWER-003",),
            (None if suggested_motor_power_w is not None else "所需功率超出当前项目配置功率系列。"),
        ),
        used_or_suggested_core_diameter_m=_scalar(
            core_diameter_m,
            "m",
            core_classification,
            (("DRUM-001",) if data.drum_core_diameter_m is not None else ("DRUM-002",)),
            core_reason,
        ),
        used_or_suggested_drum_face_length_m=_scalar(
            face_length_m,
            "m",
            face_classification,
            ("GEOM-002",) if data.drum_face_length_m is not None else ("WIDTH-001", "WIDTH-002"),
            face_reason,
        ),
        pitch_m=pitch_m,
        pitch_basis=pitch_basis,
        usable_width_m=capacity.usable_width_m if capacity else None,
        theoretical_turns_per_layer=(capacity.theoretical_turns_per_layer if capacity else None),
        final_turns_per_layer=capacity.turns_per_layer if capacity else None,
        turns_basis=capacity.turns_basis if capacity else None,
        turns_per_full_layer=capacity.turns_per_layer if capacity else None,
        layer_details=capacity.layers if capacity else (),
        capacity_satisfied=capacity_satisfied,
        actual_layers=capacity.actual_layers if capacity else None,
        evaluated_layers=evaluated_layers,
        capacity_at_actual_layers_m=(capacity.capacity_at_actual_layers_m if capacity else None),
        capacity_at_max_layers_m=(capacity.capacity_at_max_layers_m if capacity else None),
        capacity_margin_m=capacity.capacity_margin_m if capacity else None,
        capacity_margin_pct=capacity.capacity_margin_pct if capacity else None,
        capacity_shortfall_m=capacity.capacity_shortfall_m if capacity else None,
        dead_wrap_length_m=capacity.dead_wrap_length_m if capacity else None,
        required_total_storage_m=(
            data.target_rope_capacity_m + capacity.dead_wrap_length_m + data.termination_allowance_m
            if capacity
            else None
        ),
        theoretical_total_capacity_m=(capacity.theoretical_total_capacity_m if capacity else None),
        available_work_rope_length_m=(capacity.available_work_rope_length_m if capacity else None),
        dd_ratio_first_layer=(
            (core_diameter_m + data.rope_diameter_m) / data.rope_diameter_m if core_diameter_m is not None else None
        ),
        empty_working_diameter_m=empty_working_diameter_m,
        full_working_diameter_m=full_working_diameter_m,
        max_layer_working_diameter_m=max_layer_working_diameter_m,
        empty_drum_speed_rpm=empty_drum_speed_rpm,
        full_drum_speed_rpm=full_drum_speed_rpm,
        max_layer_drum_speed_rpm=max_layer_drum_speed_rpm,
        reference_ratio_empty=ratio_empty,
        reference_ratio_full=ratio_full,
        reference_ratio_max_layer=ratio_max_layer,
        reference_ratio_nominal=ratio_nominal,
        low_speed_brake_torque_nm=(
            _scalar(
                low_speed_brake_torque_nm,
                "N*m",
                ResultClassification.PRELIMINARY,
                ("BRAKE-001",),
            )
            if low_speed_brake_torque_nm is not None
            else _scalar(
                None,
                "N*m",
                ResultClassification.REVIEW_REQUIRED,
                ("BRAKE-001",),
                "缺少可计算的卷筒几何。",
            )
        ),
        high_speed_brake_torque_ref_nm=(
            _scalar(
                high_speed_brake_torque_ref_nm,
                "N*m",
                ResultClassification.PRELIMINARY,
                ("BRAKE-002",),
            )
            if high_speed_brake_torque_ref_nm is not None
            else _scalar(
                None,
                "N*m",
                ResultClassification.REVIEW_REQUIRED,
                ("BRAKE-002",),
                (
                    "传动被声明为自锁、不可逆或禁止反驱，不能生成高速轴反驱参考值。"
                    if data.transmission_backdrive_type
                    in {
                        TransmissionBackdriveType.SELF_LOCKING,
                        TransmissionBackdriveType.WORM,
                        TransmissionBackdriveType.NON_REVERSIBLE,
                        TransmissionBackdriveType.BACKDRIVE_PROHIBITED,
                    }
                    else "反向传动效率或可计算的卷筒几何缺失。"
                ),
            )
        ),
        motor_selection_status=motor_selection_status,
        unchecked_items=(
            "rope_strength",
            "rope_termination_strength",
            "drum_structure_strength",
            "dynamic_braking",
            "emergency_braking",
            "brake_thermal_capacity",
            "motor_starting_torque",
            "motor_thermal_capacity",
            "manufacturer_confirmation",
            "standard_clause_confirmation",
        ),
        ideal_load_force_n=_scalar(
            ideal_load_force_n,
            "N",
            ResultClassification.INFORMATIONAL,
            ("REEVE-001",),
        ),
        ideal_load_speed_m_s=_scalar(
            ideal_load_speed_m_s,
            "m/s",
            ResultClassification.INFORMATIONAL,
            ("REEVE-002",),
        ),
        optimizer_candidates=optimizer_candidates,
        selected_candidate=selected_candidate,
        calculation_steps=tuple(recorder.steps),
        warnings=warnings,
        assumptions=build_assumptions(data, geometry_optimized=selected_candidate is not None),
        disclaimer=DISCLAIMER,
    )
