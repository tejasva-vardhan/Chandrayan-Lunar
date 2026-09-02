"""Evidence-only EXP-001 conclusion.

The wording is assembled from the measured yields. It never names a globally
superior matcher and never treats a verification residual as accuracy.
"""

from __future__ import annotations

from typing import Any

from src.io.exp001.config import (
    DECISION_RULE,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    PRIMARY_PAIR_ID,
)

_MODEL_MIN = 4


def scientific_conclusion(summary: dict[str, Any]) -> dict[str, Any]:
    """Derive the experiment-level conclusion from recorded pair yields."""

    pair_ids = list(summary.get("pair_ids") or summary.get("pairs", {}))
    matcher_ids = list(summary.get("matcher_ids") or [])
    pairs = summary.get("pairs") or {}

    yields_by_pair: dict[str, dict[str, int | None]] = {}
    exceeded_pairs: list[str] = []
    exceeded_by_matcher: dict[str, list[str]] = {matcher_id: [] for matcher_id in matcher_ids}

    for pair_id in pair_ids:
        interpretation = (pairs.get(pair_id) or {}).get("interpretation") or {}
        yields = interpretation.get("verified_inliers_by_matcher") or {}
        yields_by_pair[pair_id] = yields
        if interpretation.get("any_matcher_exceeds_model_minimum"):
            exceeded_pairs.append(pair_id)
        above = interpretation.get("exceeds_model_minimum_by_matcher") or {}
        for matcher_id in matcher_ids:
            if above.get(matcher_id):
                exceeded_by_matcher[matcher_id].append(pair_id)

    primary = (pairs.get(PRIMARY_PAIR_ID) or {}).get("interpretation") or {}
    primary_exceeds = bool(primary.get("any_matcher_exceeds_model_minimum"))
    primary_yields = primary.get("verified_inliers_by_matcher") or {}
    consistent = [
        matcher_id
        for matcher_id, ids in exceeded_by_matcher.items()
        if ids and len(ids) == len(pair_ids)
    ]

    zero_yield = []
    for matcher_id in matcher_ids:
        if not matcher_id:
            continue
        counts = [
            (yields_by_pair.get(pair_id) or {}).get(matcher_id) for pair_id in pair_ids
        ]
        if all(count in {0, None} for count in counts):
            zero_yield.append(matcher_id)

    return {
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "decision_rule": DECISION_RULE,
        "h1_supported_on_primary_pair": primary_exceeds,
        "primary_pair_id": PRIMARY_PAIR_ID,
        "primary_pair_verified_inliers_by_matcher": primary_yields,
        "pairs_where_any_matcher_exceeds_model_minimum": exceeded_pairs,
        "matchers_that_exceeded_on_every_tested_pair": consistent,
        "matchers_with_zero_verified_inliers_on_every_tested_pair": zero_yield,
        "globally_superior_matcher": None,
        "globally_superior_matcher_claim": (
            "not claimed; yields are pair-dependent and the primary pair stays "
            f"at the {_MODEL_MIN}-inlier projective DLT minimum"
        ),
        "statement": _statement(
            primary_exceeds=primary_exceeds,
            primary_yields=primary_yields,
            exceeded_pairs=exceeded_pairs,
            consistent=consistent,
            zero_yield=zero_yield,
            pair_count=len(pair_ids),
        ),
        "recommended_exp002": _recommended_exp002(primary_exceeds, exceeded_pairs, zero_yield),
        "limitations": [
            "independent accuracy = NOT VALIDATED: no surveyed lunar ground control.",
            "Held-out transfer error, when available, is still matcher-derived and "
            "is not independent accuracy.",
            "Four-point projective DLT residuals are an algebraic identity.",
            "RIFT is not scale invariant; matching views use a per-image stride, "
            "so residual scale is a stated confounder of that arm.",
            "LoFTR / LightGlue were not run (reproducibility, matching-view "
            "control, and dependency-weight blockers).",
            "One or four pairs cannot freeze a matcher (D-007).",
            "Full-raster registration remains blocked by the 16,777,216-pixel cap.",
            "SPICE is not implemented; sun-angle difference remains None.",
        ],
    }


def _statement(
    *,
    primary_exceeds: bool,
    primary_yields: dict[str, Any],
    exceeded_pairs: list[str],
    consistent: list[str],
    zero_yield: list[str],
    pair_count: int,
) -> str:
    primary_counts = ", ".join(
        f"{matcher_id}={count}" for matcher_id, count in sorted(primary_yields.items())
    )
    if primary_exceeds:
        head = (
            f"On {PRIMARY_PAIR_ID}, at least one matcher exceeded the "
            f"{_MODEL_MIN}-inlier projective DLT minimum ({primary_counts})."
        )
    else:
        head = (
            f"On {PRIMARY_PAIR_ID}, the EXP-000 pair, no compared matcher "
            f"produced strictly more than {_MODEL_MIN} verified inliers "
            f"({primary_counts}). H1 is not supported on the controlled primary pair."
        )

    if exceeded_pairs:
        generalisation = (
            f" Across {pair_count} pairs, a matcher exceeded the model minimum "
            f"on: {', '.join(exceeded_pairs)}."
        )
    else:
        generalisation = (
            f" Across {pair_count} pairs, no matcher exceeded the model minimum."
        )

    if consistent:
        consistency = (
            f" The improvement is not a global ranking: {consistent} exceeded "
            "the minimum on every tested pair, but that still does not select "
            "a final matcher."
        )
    else:
        consistency = (
            " No matcher exceeded the model minimum on every tested pair, so "
            "the improvement is not consistent across pairs."
        )

    if zero_yield:
        zeros = (
            f" {', '.join(zero_yield)} produced zero verified inliers on every "
            "tested pair and therefore did not move the correspondence bottleneck."
        )
    else:
        zeros = ""

    return head + generalisation + consistency + zeros


def _recommended_exp002(
    primary_exceeds: bool,
    exceeded_pairs: list[str],
    zero_yield: list[str],
) -> str:
    rift_failed = "rift" in zero_yield
    scale_note = (
        " RIFT's zero yield is the predicted consequence of a fixed-size "
        "descriptor on matching views whose per-image stride leaves a residual "
        "scale (pair_01: OHRC stride 15 vs LROC stride 8)."
        if rift_failed
        else ""
    )
    if primary_exceeds:
        return (
            "Hold the winning primary-pair matcher constant and isolate the "
            "matching-view scale policy before introducing another matcher "
            "family." + scale_note
        )
    return (
        "Hold the SIFT baseline constant and isolate the matching-view scale "
        "policy on pair_01: replace per-image stride with a common-scale "
        "(or GSD-normalised) matching view, keep every other EXP-000 setting, "
        "and test whether verified yield moves above the four-inlier floor. "
        "Do not introduce another matcher family until that confounder has "
        "been measured. pair_02 already shows that SIFT and ORB can exceed "
        "the floor when the pair is more matchable, so the next bottleneck "
        "to isolate is the matching-view geometry, not detector identity "
        "among {SIFT, ORB, this RIFT}." + scale_note
    )


__all__ = ["scientific_conclusion"]
