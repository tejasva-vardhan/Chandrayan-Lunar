"""Pre-registered scale and cross-sensor decision rules."""

from __future__ import annotations

import math
from typing import Any

from src.io.ps_scale_multimodal.config import (
    DECISION_INDETERMINATE,
    DECISION_NOT_SUPPORTED,
    DECISION_SUPPORTED,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    MAINTAIN_FRACTION,
    MULTIMODAL_DECISION_RULE,
    PROTOCOL_COARSE_TO_FINE,
    REPRESENTATION_CROSS_SENSOR,
    REPRESENTATION_INTENSITY,
    SCALE_DECISION_RULE,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_C_ID,
)
from src.representation.settings import (
    SCALE_POLICY_COMMON_PHYSICAL_GSD,
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
)


def native_gsd_ratio(
    source_gsd_meters: float | None, reference_gsd_meters: float | None
) -> float | None:
    """Return source_gsd / reference_gsd when both are finite and positive."""
    source = _finite_positive(source_gsd_meters)
    reference = _finite_positive(reference_gsd_meters)
    if source is None or reference is None:
        return None
    return source / reference


def apply_scale_decision(
    *,
    independent_variable_applied: bool,
    native_gsd_ratio_value: float | None,
    verified_inliers_a: int | None,
    verified_inliers_b: int | None,
    source_occupied_a: int | None,
    source_occupied_b: int | None,
    reference_occupied_a: int | None,
    reference_occupied_b: int | None,
    transform_fitted_a: bool | None,
    transform_fitted_b: bool | None,
    min_samples: int,
    maintain_fraction: float = MAINTAIN_FRACTION,
) -> dict[str, Any]:
    useful_a, useful_a_reason = _useful_set(verified_inliers_a, min_samples)
    useful_b, useful_b_reason = _useful_set(verified_inliers_b, min_samples)
    maintained, maintain_reason = _maintained(
        verified_inliers_a,
        verified_inliers_b,
        source_occupied_a,
        source_occupied_b,
        reference_occupied_a,
        reference_occupied_b,
        maintain_fraction,
    )
    transform_ok, transform_reason = _transform_stable(
        transform_fitted_a,
        transform_fitted_b,
        verified_inliers_a,
        verified_inliers_b,
        min_samples,
    )
    gsd_ok, gsd_reason = _gsd_ratio_ok(native_gsd_ratio_value)
    critical_missing = any(
        value is None
        for value in (
            verified_inliers_a,
            verified_inliers_b,
            source_occupied_a,
            source_occupied_b,
            reference_occupied_a,
            reference_occupied_b,
            native_gsd_ratio_value,
        )
    )

    if not independent_variable_applied:
        decision = DECISION_INDETERMINATE
        reason = (
            "scale variants did not apply per_image_pixel_budget (A) vs "
            "common_physical_gsd (B) on coarse-to-fine intensity"
        )
    elif critical_missing:
        decision = DECISION_INDETERMINATE
        reason = "critical scale measurements are missing"
    elif not gsd_ok:
        decision = DECISION_INDETERMINATE
        reason = gsd_reason
    elif useful_a and useful_b and maintained and transform_ok:
        decision = DECISION_SUPPORTED
        reason = (
            "native GSD ratio is material; A and B each keep a useful verified "
            "set; B maintains quality/spatial occupancy vs A; transforms stable"
        )
    else:
        decision = DECISION_NOT_SUPPORTED
        reason = "; ".join(
            item
            for item in (
                None if useful_a else useful_a_reason,
                None if useful_b else useful_b_reason,
                None if maintained else maintain_reason,
                None if transform_ok else transform_reason,
            )
            if item
        )

    return {
        "decision": decision,
        "hypothesis_supported": decision == DECISION_SUPPORTED,
        "decision_reason": reason,
        "decision_rule": SCALE_DECISION_RULE,
        "challenge": "scale",
        "native_gsd_ratio": native_gsd_ratio_value,
        "native_gsd_ratio_ok": gsd_ok,
        "native_gsd_ratio_reason": gsd_reason,
        "useful_set_a": useful_a,
        "useful_set_b": useful_b,
        "maintained_vs_baseline": maintained,
        "maintain_reason": maintain_reason,
        "transform_stable": transform_ok,
        "transform_reason": transform_reason,
        "critical_measurements_missing": critical_missing,
        "independent_variable_applied": independent_variable_applied,
        "maintain_fraction": maintain_fraction,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "verified_inliers_by_variant": {
            VARIANT_A_ID: verified_inliers_a,
            VARIANT_B_ID: verified_inliers_b,
        },
        "expected_scale_policies": {
            VARIANT_A_ID: SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
            VARIANT_B_ID: SCALE_POLICY_COMMON_PHYSICAL_GSD,
        },
    }


def apply_cross_sensor_decision(
    *,
    independent_variable_applied: bool,
    verified_inliers_a: int | None,
    verified_inliers_c: int | None,
    source_occupied_a: int | None,
    source_occupied_c: int | None,
    reference_occupied_a: int | None,
    reference_occupied_c: int | None,
    transform_fitted_a: bool | None,
    transform_fitted_c: bool | None,
    min_samples: int,
    maintain_fraction: float = MAINTAIN_FRACTION,
) -> dict[str, Any]:
    useful_a, useful_a_reason = _useful_set(verified_inliers_a, min_samples)
    useful_c, useful_c_reason = _useful_set(verified_inliers_c, min_samples)
    maintained, maintain_reason = _maintained(
        verified_inliers_a,
        verified_inliers_c,
        source_occupied_a,
        source_occupied_c,
        reference_occupied_a,
        reference_occupied_c,
        maintain_fraction,
    )
    transform_ok, transform_reason = _transform_stable(
        transform_fitted_a,
        transform_fitted_c,
        verified_inliers_a,
        verified_inliers_c,
        min_samples,
    )
    critical_missing = any(
        value is None
        for value in (
            verified_inliers_a,
            verified_inliers_c,
            source_occupied_a,
            source_occupied_c,
            reference_occupied_a,
            reference_occupied_c,
        )
    )

    if not independent_variable_applied:
        decision = DECISION_INDETERMINATE
        reason = (
            "cross-sensor variants did not apply intensity (A) vs "
            f"{REPRESENTATION_CROSS_SENSOR} (C) on coarse-to-fine"
        )
    elif critical_missing:
        decision = DECISION_INDETERMINATE
        reason = "critical cross-sensor measurements are missing"
    elif useful_a and useful_c and maintained and transform_ok:
        decision = DECISION_SUPPORTED
        reason = (
            "A and C each keep a useful verified set; C maintains "
            "quality/spatial occupancy vs A under cross-sensor CLAHE; "
            "transforms stable"
        )
    else:
        decision = DECISION_NOT_SUPPORTED
        reason = "; ".join(
            item
            for item in (
                None if useful_a else useful_a_reason,
                None if useful_c else useful_c_reason,
                None if maintained else maintain_reason,
                None if transform_ok else transform_reason,
            )
            if item
        )

    return {
        "decision": decision,
        "hypothesis_supported": decision == DECISION_SUPPORTED,
        "decision_reason": reason,
        "decision_rule": MULTIMODAL_DECISION_RULE,
        "challenge": "cross_sensor_optical",
        "modality_claim": (
            "cross-instrument optical (OHRC <-> LROC NAC); not "
            "OHRC/TMC/IIRS multi-modal validation"
        ),
        "useful_set_a": useful_a,
        "useful_set_c": useful_c,
        "maintained_vs_baseline": maintained,
        "maintain_reason": maintain_reason,
        "transform_stable": transform_ok,
        "transform_reason": transform_reason,
        "critical_measurements_missing": critical_missing,
        "independent_variable_applied": independent_variable_applied,
        "maintain_fraction": maintain_fraction,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "verified_inliers_by_variant": {
            VARIANT_A_ID: verified_inliers_a,
            VARIANT_C_ID: verified_inliers_c,
        },
        "expected_representations": {
            VARIANT_A_ID: REPRESENTATION_INTENSITY,
            VARIANT_C_ID: REPRESENTATION_CROSS_SENSOR,
        },
        "expected_protocol": PROTOCOL_COARSE_TO_FINE,
    }


def _useful_set(inliers: int | None, min_samples: int) -> tuple[bool, str]:
    if inliers is None:
        return False, "verified inlier count is unavailable"
    if inliers <= min_samples:
        return False, (
            f"verified inliers {inliers} are at or below the projective DLT "
            f"minimum ({min_samples}); set is not useful/falsifiable"
        )
    return True, f"verified inliers {inliers} exceed model minimum {min_samples}"


def _maintained(
    inliers_a: int | None,
    inliers_b: int | None,
    source_a: int | None,
    source_b: int | None,
    reference_a: int | None,
    reference_b: int | None,
    fraction: float,
) -> tuple[bool, str]:
    if any(
        value is None
        for value in (inliers_a, inliers_b, source_a, source_b, reference_a, reference_b)
    ):
        return False, "maintain comparison measurements are unavailable"
    assert inliers_a is not None and inliers_b is not None
    assert source_a is not None and source_b is not None
    assert reference_a is not None and reference_b is not None
    floor_inliers = math.ceil(fraction * inliers_a)
    floor_source = math.ceil(fraction * source_a)
    floor_reference = math.ceil(fraction * reference_a)
    if inliers_b < floor_inliers:
        return False, (
            f"verified inliers collapsed ({inliers_b} < {floor_inliers} = "
            f"{fraction:g} * {inliers_a})"
        )
    if source_b < floor_source or reference_b < floor_reference:
        return False, (
            "occupied cells collapsed "
            f"(source {source_a} -> {source_b}, "
            f"reference {reference_a} -> {reference_b}; "
            f"floors {floor_source}/{floor_reference})"
        )
    return True, (
        f"maintained vs A within {fraction:g}: inliers {inliers_a}->{inliers_b}, "
        f"source cells {source_a}->{source_b}, "
        f"reference cells {reference_a}->{reference_b}"
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
            f"transform fitted A={fitted_a} other={fitted_b}; both must remain fitted"
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


def _gsd_ratio_ok(ratio: float | None) -> tuple[bool, str]:
    if ratio is None:
        return False, "native GSD ratio is unavailable"
    if not math.isfinite(ratio) or ratio <= 0.0:
        return False, f"native GSD ratio is not finite/positive: {ratio!r}"
    if abs(ratio - 1.0) <= 0.05:
        return False, (
            f"native GSD ratio {ratio:.4f} is within 5% of 1; scale challenge "
            "is not material on this pair"
        )
    return True, f"native GSD ratio {ratio:.4f} differs from 1 by more than 5%"


def _finite_positive(value: float | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


__all__ = [
    "apply_cross_sensor_decision",
    "apply_scale_decision",
    "native_gsd_ratio",
]
