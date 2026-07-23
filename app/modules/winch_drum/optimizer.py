"""Finite, explainable geometry candidate search for the winch drum.

The optimizer does not invent a minimum D/d ratio. A core diameter must come
from user input or from an explicitly supplied approved_core_ratio. It then
enumerates only the finite layer limits 1..max_layers.
"""

from __future__ import annotations

import math

from .assumptions import MAX_OPTIMIZER_CANDIDATES
from .schema import DrumCandidate


def centerline_turn_length(core_diameter_m: float, rope_diameter_m: float, pitch_m: float, layer: int) -> float:
    """Return the helical rope-centreline length of one turn on a layer."""

    center_diameter_m = core_diameter_m + (2 * layer - 1) * rope_diameter_m
    return math.hypot(math.pi * center_diameter_m, pitch_m)


def capacity_for_uniform_turns(
    *,
    core_diameter_m: float,
    rope_diameter_m: float,
    pitch_m: float,
    layer_limit: int,
    turns_per_layer: int,
    dead_wraps: int,
) -> float:
    """Calculate usable capacity for one finite candidate combination."""

    total_m = 0.0
    for layer in range(1, layer_limit + 1):
        turn_length_m = centerline_turn_length(core_diameter_m, rope_diameter_m, pitch_m, layer)
        usable_turns = turns_per_layer - dead_wraps if layer == 1 else turns_per_layer
        total_m += max(0, usable_turns) * turn_length_m
    return total_m


def required_uniform_turns(
    *,
    core_diameter_m: float,
    rope_diameter_m: float,
    pitch_m: float,
    target_capacity_m: float,
    layer_limit: int,
    dead_wraps: int,
) -> int:
    """Solve the minimum integer turns without an unbounded loop."""

    turn_lengths = tuple(
        centerline_turn_length(core_diameter_m, rope_diameter_m, pitch_m, layer) for layer in range(1, layer_limit + 1)
    )
    numerator = target_capacity_m + dead_wraps * turn_lengths[0]
    raw_turns = numerator / sum(turn_lengths)
    turns = max(1, dead_wraps, math.ceil(raw_turns - 1e-12))

    # A single guarded correction handles floating-point proximity to an integer;
    # this is not an open-ended iteration.
    capacity_m = capacity_for_uniform_turns(
        core_diameter_m=core_diameter_m,
        rope_diameter_m=rope_diameter_m,
        pitch_m=pitch_m,
        layer_limit=layer_limit,
        turns_per_layer=turns,
        dead_wraps=dead_wraps,
    )
    if capacity_m + 1e-12 < target_capacity_m:
        turns += 1
    return turns


def search_drum_candidates(
    *,
    core_diameter_m: float,
    rope_diameter_m: float,
    pitch_m: float,
    target_capacity_m: float,
    side_margin_m: float,
    max_layers: int,
    dead_wraps: int,
) -> tuple[DrumCandidate, ...]:
    """Enumerate and rank a finite set of geometric candidates.

    The ranking proxy is ``face_length * outer_envelope_diameter**2``. It is a
    transparent geometric compactness proxy, not mass, cost, strength, or a
    product recommendation.
    """

    candidate_count = min(max_layers, MAX_OPTIMIZER_CANDIDATES)
    candidates: list[DrumCandidate] = []

    for layer_limit in range(1, candidate_count + 1):
        turns = required_uniform_turns(
            core_diameter_m=core_diameter_m,
            rope_diameter_m=rope_diameter_m,
            pitch_m=pitch_m,
            target_capacity_m=target_capacity_m,
            layer_limit=layer_limit,
            dead_wraps=dead_wraps,
        )
        face_length_m = turns * pitch_m + 2.0 * side_margin_m
        capacity_m = capacity_for_uniform_turns(
            core_diameter_m=core_diameter_m,
            rope_diameter_m=rope_diameter_m,
            pitch_m=pitch_m,
            layer_limit=layer_limit,
            turns_per_layer=turns,
            dead_wraps=dead_wraps,
        )
        outer_envelope_diameter_m = core_diameter_m + 2.0 * layer_limit * rope_diameter_m
        envelope_proxy_m3 = face_length_m * outer_envelope_diameter_m**2
        candidates.append(
            DrumCandidate(
                core_diameter_m=core_diameter_m,
                face_length_m=face_length_m,
                layer_limit=layer_limit,
                turns_per_layer=turns,
                capacity_m=capacity_m,
                capacity_margin_m=capacity_m - target_capacity_m,
                outer_envelope_diameter_m=outer_envelope_diameter_m,
                envelope_proxy_m3=envelope_proxy_m3,
                explanation=(f"候选层数={layer_limit}，最少完整圈数={turns}；按面长×外包络直径²的几何代理量排序。"),
            )
        )

    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.envelope_proxy_m3,
                candidate.face_length_m,
                candidate.outer_envelope_diameter_m,
                candidate.layer_limit,
            ),
        )
    )
