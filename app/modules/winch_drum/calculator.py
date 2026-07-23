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
    build_assumptions,
)
from .optimizer import centerline_turn_length, search_drum_candidates
from .schema import (
    CalculationStatus,
    DrumCandidate,
    FormulaStep,
    LayerResult,
    ResultClassification,
    ScalarResult,
    SourceStatus,
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
    usable_width_m: float
    capacity_satisfied: bool
    actual_layers: int | None
    capacity_at_actual_layers_m: float | None
    capacity_at_max_layers_m: float
    capacity_margin_m: float | None
    capacity_margin_pct: float | None
    capacity_shortfall_m: float | None


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
        core_diameter_m = data.approved_core_ratio * data.rope_diameter_m
        recorder.add(
            "DRUM-002",
            "D_c,suggested = R_Dd * d",
            {"R_Dd": data.approved_core_ratio, "d": data.rope_diameter_m},
            core_diameter_m,
            "m",
            ResultClassification.PRELIMINARY,
        )
        return core_diameter_m, ResultClassification.PRELIMINARY, None

    return (
        None,
        ResultClassification.REVIEW_REQUIRED,
        "缺少用户给定芯径或经批准的 D/d 规则，不能安全生成芯径数值。",
    )


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
        target_capacity_m=data.target_rope_capacity_m,
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
    turns_per_layer = _turns_per_full_layer(usable_width_m, pitch_m)
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
        "N_full = floor((B_u + epsilon) / p)",
        {"B_u": usable_width_m, "p": pitch_m},
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
    remaining_target_m = data.target_rope_capacity_m
    actual_layers: int | None = None
    capacity_at_actual_layers_m: float | None = None

    for layer_number in range(1, layer_limit + 1):
        center_diameter_m = core_diameter_m + (2 * layer_number - 1) * data.rope_diameter_m
        turn_length_m = centerline_turn_length(
            core_diameter_m, data.rope_diameter_m, pitch_m, layer_number
        )
        usable_turns = (
            turns_per_layer - data.dead_wraps if layer_number == 1 else turns_per_layer
        )
        gross_capacity_m = turns_per_layer * turn_length_m
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

        if actual_layers is None and cumulative_usable_m + 1e-12 >= data.target_rope_capacity_m:
            actual_layers = layer_number
            capacity_at_actual_layers_m = cumulative_usable_m

    capacity_satisfied = actual_layers is not None
    if capacity_satisfied:
        assert capacity_at_actual_layers_m is not None
        capacity_margin_m = capacity_at_actual_layers_m - data.target_rope_capacity_m
        capacity_margin_pct = 100.0 * capacity_margin_m / data.target_rope_capacity_m
        capacity_shortfall_m = None
        recorder.add(
            "CAP-006",
            "z_actual = min(k where L_total,k >= L_t)",
            {"L_t": data.target_rope_capacity_m},
            actual_layers,
            "layer",
        )
        recorder.add(
            "CAP-007",
            "L_margin = L_total,z_actual - L_t",
            {
                "L_total_actual": capacity_at_actual_layers_m,
                "L_t": data.target_rope_capacity_m,
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
        capacity_shortfall_m = data.target_rope_capacity_m - cumulative_usable_m

    return _CapacitySummary(
        layers=tuple(layers),
        turns_per_layer=turns_per_layer,
        usable_width_m=usable_width_m,
        capacity_satisfied=capacity_satisfied,
        actual_layers=actual_layers,
        capacity_at_actual_layers_m=capacity_at_actual_layers_m,
        capacity_at_max_layers_m=cumulative_usable_m,
        capacity_margin_m=capacity_margin_m,
        capacity_margin_pct=capacity_margin_pct,
        capacity_shortfall_m=capacity_shortfall_m,
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
        message=message,
        affected_fields=tuple(affected_fields),
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
                WarningSeverity.MEDIUM,
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

    warnings.append(
        _warning(
            (
                WarningCode.REVERSE_EFFICIENCY_APPROXIMATED
                if data.allow_forward_efficiency_as_reverse_approx and geometry_available
                else WarningCode.REVERSE_EFFICIENCY_UNKNOWN
            ),
            WarningSeverity.HIGH,
            (
                "高速轴参考值用正向效率近似反向效率。"
                if data.allow_forward_efficiency_as_reverse_approx and geometry_available
                else "反向传动效率未知，高速轴制动力矩保持待校核。"
            ),
            "high_speed_brake_torque_ref_nm",
        )
    )

    if data.assumption_sources.service_factor is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            _warning(
                WarningCode.SERVICE_FACTOR_SOURCE,
                WarningSeverity.MEDIUM,
                "使用系数来源待机械工程师确认。",
                "service_factor",
            )
        )
    if data.assumption_sources.pitch_factor is SourceStatus.PENDING_CONFIRMATION:
        warnings.append(
            _warning(
                WarningCode.PITCH_FACTOR_SOURCE,
                WarningSeverity.MEDIUM,
                "排绳节距修正系数来源待机械工程师确认。",
                "pitch_factor",
            )
        )
    warnings.extend(
        (
            _warning(
                WarningCode.DUTY_CLASS_INFO_ONLY,
                WarningSeverity.MEDIUM,
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
    if data.dead_wraps == 0:
        warnings.append(
            _warning(
                WarningCode.DEAD_WRAPS_ASSUMED_ZERO,
                WarningSeverity.MEDIUM,
                "固定死圈按 0 处理，该项目设定待确认。",
                "dead_wraps",
            )
        )
    return tuple(warnings)


def calculate(source: WinchDrumInput) -> WinchDrumResult:
    """Run one deterministic, side-effect-free winch/drum calculation."""

    data = source.to_si()
    recorder = _StepRecorder()
    _record_unit_steps(source, data, recorder)

    design_line_pull_n = data.rated_line_pull_n * data.service_factor
    theoretical_load_power_w = design_line_pull_n * data.rope_speed_m_s
    minimum_motor_power_w = theoretical_load_power_w / data.total_efficiency
    recorder.add(
        "FORCE-001",
        "F_d = F_r * K_s",
        {"F_r": data.rated_line_pull_n, "K_s": data.service_factor},
        design_line_pull_n,
        "N",
    )
    recorder.add(
        "POWER-001",
        "P_load = F_d * v",
        {"F_d": design_line_pull_n, "v": data.rope_speed_m_s},
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

    pitch_m = data.pitch_factor * data.rope_diameter_m
    recorder.add(
        "GEOM-001",
        "p = K_p * d",
        {"K_p": data.pitch_factor, "d": data.rope_diameter_m},
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
    empty_drum_speed_rpm: float | None = None
    full_drum_speed_rpm: float | None = None
    ratio_empty: float | None = None
    ratio_full: float | None = None
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
        working_layer_count = capacity.actual_layers or evaluated_layers
        empty_working_diameter_m = core_diameter_m + data.rope_diameter_m
        full_working_diameter_m = (
            core_diameter_m + (2 * working_layer_count - 1) * data.rope_diameter_m
        )
        empty_drum_speed_rpm = 60.0 * data.rope_speed_m_s / (
            math.pi * empty_working_diameter_m
        )
        full_drum_speed_rpm = 60.0 * data.rope_speed_m_s / (
            math.pi * full_working_diameter_m
        )
        motor_speed_rpm = data.motor_angular_speed_rad_s * 60.0 / (2.0 * math.pi)
        ratio_empty = motor_speed_rpm / empty_drum_speed_rpm
        ratio_full = motor_speed_rpm / full_drum_speed_rpm
        reference_diameter_m = (empty_working_diameter_m + full_working_diameter_m) / 2.0
        reference_drum_speed_rpm = 60.0 * data.rope_speed_m_s / (
            math.pi * reference_diameter_m
        )
        ratio_nominal = motor_speed_rpm / reference_drum_speed_rpm

        recorder.add(
            "SPEED-001",
            "D_work,empty = D_c + d",
            {"D_c": core_diameter_m, "d": data.rope_diameter_m},
            empty_working_diameter_m,
            "m",
        )
        recorder.add(
            "SPEED-002",
            "D_work,full = D_c + (2*z - 1)*d",
            {
                "D_c": core_diameter_m,
                "z": working_layer_count,
                "d": data.rope_diameter_m,
            },
            full_working_diameter_m,
            "m",
        )
        recorder.add(
            "SPEED-003",
            "n_drum = 60*v/(pi*D_work)",
            {"v": data.rope_speed_m_s, "D_work": reference_diameter_m},
            reference_drum_speed_rpm,
            "r/min",
        )
        recorder.add(
            "SPEED-004",
            "n_empty = 60*v/(pi*D_work,empty)",
            {"v": data.rope_speed_m_s, "D_work_empty": empty_working_diameter_m},
            empty_drum_speed_rpm,
            "r/min",
        )
        recorder.add(
            "SPEED-005",
            "n_full = 60*v/(pi*D_work,full)",
            {"v": data.rope_speed_m_s, "D_work_full": full_working_diameter_m},
            full_drum_speed_rpm,
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
            "i_full = n_m/n_full",
            {
                "n_m": motor_speed_rpm,
                "n_full": full_drum_speed_rpm,
            },
            ratio_full,
            "ratio",
            ResultClassification.PRELIMINARY,
        )
        recorder.add(
            "RATIO-002",
            "i_ref = n_m / (60*v/(pi*D_ref))",
            {"n_m": motor_speed_rpm, "v": data.rope_speed_m_s, "D_ref": reference_diameter_m},
            ratio_nominal,
            "ratio",
            ResultClassification.PRELIMINARY,
        )

        low_speed_brake_torque_nm = (
            data.rated_line_pull_n
            * (full_working_diameter_m / 2.0)
            * data.brake_safety_factor
        )
        recorder.add(
            "BRAKE-001",
            "T_brake,low = F_r*(D_work,full/2)*K_b",
            {
                "F_r": data.rated_line_pull_n,
                "D_work_full": full_working_diameter_m,
                "K_b": data.brake_safety_factor,
            },
            low_speed_brake_torque_nm,
            "N*m",
            ResultClassification.PRELIMINARY,
        )
        if data.allow_forward_efficiency_as_reverse_approx:
            high_speed_brake_torque_ref_nm = low_speed_brake_torque_nm / (
                ratio_nominal * data.total_efficiency
            )
            recorder.add(
                "BRAKE-002",
                "T_brake,high,ref = T_brake,low/(i_ref*eta_back)",
                {
                    "T_brake_low": low_speed_brake_torque_nm,
                    "i_ref": ratio_nominal,
                    "eta_back_approx": data.total_efficiency,
                },
                high_speed_brake_torque_ref_nm,
                "N*m",
                ResultClassification.PRELIMINARY,
            )

    ideal_load_force_n = data.reeving_ratio * data.rated_line_pull_n
    ideal_load_speed_m_s = data.rope_speed_m_s / data.reeving_ratio
    recorder.add(
        "REEVE-001",
        "F_load,ideal = M * F_r",
        {"M": data.reeving_ratio, "F_r": data.rated_line_pull_n},
        ideal_load_force_n,
        "N",
        ResultClassification.INFORMATIONAL,
    )
    recorder.add(
        "REEVE-002",
        "v_load,ideal = v/M",
        {"v": data.rope_speed_m_s, "M": data.reeving_ratio},
        ideal_load_speed_m_s,
        "m/s",
        ResultClassification.INFORMATIONAL,
    )

    geometry_available = capacity is not None
    capacity_satisfied = capacity.capacity_satisfied if capacity else False
    speed_varies = bool(
        empty_working_diameter_m is not None
        and full_working_diameter_m is not None
        and not math.isclose(empty_working_diameter_m, full_working_diameter_m)
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
        status=(
            CalculationStatus.COMPLETED_WITH_WARNINGS
            if warnings
            else CalculationStatus.COMPLETED
        ),
        input_si=data,
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
            None,
            "W",
            ResultClassification.REVIEW_REQUIRED,
            ("POWER-003",),
            "缺少经批准的标准功率系列、工作制、启动和热校核。",
        ),
        used_or_suggested_core_diameter_m=_scalar(
            core_diameter_m,
            "m",
            core_classification,
            (
                ("DRUM-001",)
                if data.drum_core_diameter_m is not None
                else (("DRUM-002",) if data.approved_core_ratio is not None else ("DRUM-003",))
            ),
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
        usable_width_m=capacity.usable_width_m if capacity else None,
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
        empty_working_diameter_m=empty_working_diameter_m,
        full_working_diameter_m=full_working_diameter_m,
        empty_drum_speed_rpm=empty_drum_speed_rpm,
        full_drum_speed_rpm=full_drum_speed_rpm,
        reference_ratio_empty=ratio_empty,
        reference_ratio_full=ratio_full,
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
                "反向传动效率或可计算的卷筒几何缺失。",
            )
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
