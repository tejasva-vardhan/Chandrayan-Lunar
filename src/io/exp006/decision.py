"""Pre-registered EXP-006 decision rule.

This module applies the rule written in the README and config before the
real-data run. It does not look at raw match count as a success criterion
and it does not treat held-out RMSE as accuracy.
"""

from __future__ import annotations

from typing import Any

from src.io.exp006.config import (
    DECISION_INDETERMINATE,
    DECISION_NOT_SUPPORTED,
    DECISION_RULE,
    DECISION_SUPPORTED,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    PROTOCOL_ONE_WAY,
    PROTOCOL_RECIPROCAL,
    RUNTIME_FACTOR_LIMIT,
    VARIANT_A_ID,
    VARIANT_B_ID,
)


def apply_decision_rule(
    *,
    independent_variable_applied: bool,
    verified_inliers_a: int | None,
    verified_inliers_b: int | None,
    inlier_ratio_a: float | None,
    inlier_ratio_b: float | None,
    source_occupied_a: int | None,
    source_occupied_b: int | None,
    reference_occupied_a: int | None,
    reference_occupied_b: int | None,
    transform_fitted_a: bool | None,
    transform_fitted_b: bool | None,
    min_samples: int,
    match_runtime_a: float | None = None,
    match_runtime_b: float | None = None,
    runtime_factor_limit: float = RUNTIME_FACTOR_LIMIT,
) -> dict[str, Any]:
    """Return the gated quality / spatial / stability decision.

    Missing critical measurements produce INDETERMINATE rather than a
    silent false negative. Raw match count is deliberately unused.
    """

    quality_improved, quality_reason = _quality_improved(
        verified_inliers_a, verified_inliers_b, inlier_ratio_a, inlier_ratio_b
    )
    spatial_ok, spatial_reason = _spatial_maintained_or_improved(
        source_occupied_a,
        source_occupied_b,
        reference_occupied_a,
        reference_occupied_b,
    )
    transform_stable, transform_reason = _transform_stable(
        transform_fitted_a,
        transform_fitted_b,
        verified_inliers_a,
        verified_inliers_b,
        min_samples,
    )
    runtime_ok, runtime_reason = _runtime_acceptable(
        match_runtime_a, match_runtime_b, runtime_factor_limit
    )

    critical_missing = _critical_missing(
        verified_inliers_a,
        verified_inliers_b,
        inlier_ratio_a,
        inlier_ratio_b,
        source_occupied_a,
        source_occupied_b,
        reference_occupied_a,
        reference_occupied_b,
    )

    if not independent_variable_applied:
        decision = DECISION_INDETERMINATE
        reason = (
            "variants did not apply one-way SIFT vs reciprocal SIFT on the "
            "same representation"
        )
    elif critical_missing:
        decision = DECISION_INDETERMINATE
        reason = "critical verified-quality or spatial measurements are missing"
    elif quality_improved and spatial_ok and transform_stable and runtime_ok:
        decision = DECISION_SUPPORTED
        reason = (
            "verified inliers increased, inlier ratio did not fall, spatial "
            "occupancy was maintained or improved, transform stayed above "
            "the model minimum, and match runtime stayed within the "
            f"{runtime_factor_limit:g}x limit"
        )
    else:
        decision = DECISION_NOT_SUPPORTED
        reason = "; ".join(
            item
            for item in (
                None if quality_improved else quality_reason,
                None if spatial_ok else spatial_reason,
                None if transform_stable else transform_reason,
                None if runtime_ok else runtime_reason,
            )
            if item
        )

    return {
        "decision": decision,
        "hypothesis_supported": decision == DECISION_SUPPORTED,
        "decision_reason": reason,
        "decision_rule": DECISION_RULE,
        "quality_improved": quality_improved,
        "quality_reason": quality_reason,
        "spatial_maintained_or_improved": spatial_ok,
        "spatial_reason": spatial_reason,
        "transform_stable": transform_stable,
        "transform_reason": transform_reason,
        "runtime_acceptable": runtime_ok,
        "runtime_reason": runtime_reason,
        "critical_measurements_missing": critical_missing,
        "independent_variable_applied": independent_variable_applied,
        "raw_match_count_is_not_success": True,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "verified_inliers_by_variant": {
            VARIANT_A_ID: verified_inliers_a,
            VARIANT_B_ID: verified_inliers_b,
        },
        "inlier_ratio_by_variant": {
            VARIANT_A_ID: inlier_ratio_a,
            VARIANT_B_ID: inlier_ratio_b,
        },
        "source_occupied_cells_by_variant": {
            VARIANT_A_ID: source_occupied_a,
            VARIANT_B_ID: source_occupied_b,
        },
        "reference_occupied_cells_by_variant": {
            VARIANT_A_ID: reference_occupied_a,
            VARIANT_B_ID: reference_occupied_b,
        },
        "expected_protocols": {
            VARIANT_A_ID: PROTOCOL_ONE_WAY,
            VARIANT_B_ID: PROTOCOL_RECIPROCAL,
        },
    }


def _quality_improved(
    inliers_a: int | None,
    inliers_b: int | None,
    ratio_a: float | None,
    ratio_b: float | None,
) -> tuple[bool, str]:
    if inliers_a is None or inliers_b is None or ratio_a is None or ratio_b is None:
        return False, "verified inlier count or inlier ratio is unavailable"
    if inliers_b <= inliers_a:
        return False, (
            f"verified inliers did not increase ({inliers_b} <= {inliers_a})"
        )
    if ratio_b < ratio_a:
        return False, (
            f"inlier ratio decreased ({ratio_b:.6f} < {ratio_a:.6f})"
        )
    return True, (
        f"verified inliers {inliers_a} -> {inliers_b} and inlier ratio "
        f"{ratio_a:.6f} -> {ratio_b:.6f}"
    )


def _spatial_maintained_or_improved(
    source_a: int | None,
    source_b: int | None,
    reference_a: int | None,
    reference_b: int | None,
) -> tuple[bool, str]:
    if any(value is None for value in (source_a, source_b, reference_a, reference_b)):
        return False, "occupied-cell counts are unavailable"
    assert source_a is not None and source_b is not None
    assert reference_a is not None and reference_b is not None
    if source_b < source_a or reference_b < reference_a:
        return False, (
            "occupied cells decreased "
            f"(source {source_a} -> {source_b}, "
            f"reference {reference_a} -> {reference_b})"
        )
    return True, (
        f"source occupied cells {source_a} -> {source_b}, "
        f"reference occupied cells {reference_a} -> {reference_b}"
    )


def _transform_stable(
    fitted_a: bool | None,
    fitted_b: bool | None,
    inliers_a: int | None,
    inliers_b: int | None,
    min_samples: int,
) -> tuple[bool, str]:
    if fitted_a is None or fitted_b is None or inliers_a is None or inliers_b is None:
        return False, "transform or verified-inlier status is unavailable"
    if not fitted_a or not fitted_b:
        return False, (
            f"transform fitted A={fitted_a} B={fitted_b}; both must remain fitted"
        )
    if inliers_a <= min_samples or inliers_b <= min_samples:
        return False, (
            "a variant is at or below the projective DLT minimum "
            f"({min_samples}), so the fit is unfalsifiable"
        )
    return True, (
        f"both variants fitted a transform from more than {min_samples} "
        "verified inliers"
    )


def _runtime_acceptable(
    runtime_a: float | None,
    runtime_b: float | None,
    limit: float,
) -> tuple[bool, str]:
    if runtime_a is None or runtime_b is None:
        return True, "match runtime was not measured; runtime gate skipped"
    if runtime_a < 0 or runtime_b < 0:
        return False, "match runtime is negative"
    ceiling = limit * runtime_a
    if runtime_b > ceiling:
        return False, (
            f"B match runtime {runtime_b:.3f}s exceeds {limit:g}x A "
            f"({ceiling:.3f}s)"
        )
    return True, (
        f"B match runtime {runtime_b:.3f}s is within {limit:g}x A "
        f"({runtime_a:.3f}s)"
    )


def _critical_missing(
    inliers_a: int | None,
    inliers_b: int | None,
    ratio_a: float | None,
    ratio_b: float | None,
    source_a: int | None,
    source_b: int | None,
    reference_a: int | None,
    reference_b: int | None,
) -> bool:
    return any(
        value is None
        for value in (
            inliers_a,
            inliers_b,
            ratio_a,
            ratio_b,
            source_a,
            source_b,
            reference_a,
            reference_b,
        )
    )


__all__ = ["apply_decision_rule"]
