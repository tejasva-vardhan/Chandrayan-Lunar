"""EXP-005 refinement diagnostics.

These measurements live in the experiment layer. They do not extend
ControlPoint, Correspondence, or CorrespondenceSet. Acceptance, ZNCC, and
displacements are reconstructed from the existing refine_points outputs and
from the existing estimate_zncc_displacement / zncc callables.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from src.io.exp001.validation import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    STATUS_NO_CHECKPOINTS,
    STATUS_NO_TRANSFORM,
    HeldOutSettings,
    held_out_validation,
)
from src.io.exp005.config import (
    REFINEMENT_OUTCOME_COORDINATES_UPDATED,
    REFINEMENT_OUTCOME_INDETERMINATE,
    REFINEMENT_OUTCOME_NO_POINTS,
)
from src.models.correspondence_set import Correspondence
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint
from src.refinement.raster import as_intensity, load_software_raster
from src.refinement.settings import RefinementSettings, unvalidated_software_defaults
from src.refinement.window import extract_window
from src.refinement.zncc import estimate_zncc_displacement, zncc
from src.verification.residuals import image_space_transfer_error

_WHY_NOT_ACCURACY = (
    "held-out points are matcher-derived and were selected by the same "
    "RANSAC consensus as the fitting points, so their errors are correlated "
    "with the fit; no surveyed lunar control exists"
)


def coordinate_displacement_px(before: ControlPoint, after: ControlPoint) -> float:
    """Euclidean change of the refined reference coordinate, plus source drift."""

    source = math.hypot(
        after.source_xy[0] - before.source_xy[0],
        after.source_xy[1] - before.source_xy[1],
    )
    reference = math.hypot(
        after.reference_xy[0] - before.reference_xy[0],
        after.reference_xy[1] - before.reference_xy[1],
    )
    return float(math.hypot(source, reference))


def coordinates_changed(before: ControlPoint, after: ControlPoint) -> bool:
    return before.source_xy != after.source_xy or before.reference_xy != after.reference_xy


def displacement_report(
    original: list[ControlPoint], refined: list[ControlPoint]
) -> dict[str, Any]:
    """Count changes and summarise displacements. Does not claim accuracy."""

    displacements = [
        coordinate_displacement_px(before, after)
        for before, after in zip(original, refined, strict=True)
    ]
    changed_flags = [
        coordinates_changed(before, after)
        for before, after in zip(original, refined, strict=True)
    ]
    changed = int(sum(changed_flags))
    changed_values = [value for value, flag in zip(displacements, changed_flags) if flag]
    if not refined:
        outcome = REFINEMENT_OUTCOME_NO_POINTS
    elif changed == 0:
        outcome = REFINEMENT_OUTCOME_INDETERMINATE
    else:
        outcome = REFINEMENT_OUTCOME_COORDINATES_UPDATED
    return {
        "outcome": outcome,
        "input_count": len(original),
        "output_count": len(refined),
        "coordinates_changed_count": changed,
        "mean_displacement_pixels": _mean(displacements),
        "mean_displacement_among_changed_pixels": _mean(changed_values),
        "max_displacement_pixels": _max(displacements),
        "per_point_displacement_pixels": displacements,
        "limitation": (
            "INDETERMINATE means zero coordinates changed; the frozen "
            "ControlPoint contract has no per-point outcome field, so "
            "already-optimal cannot be distinguished from no measurable "
            "improvement. Coordinate change is not accuracy."
        )
        if outcome == REFINEMENT_OUTCOME_INDETERMINATE
        else (
            "Coordinate change is not evidence of improved accuracy. Held-out "
            "geometric consistency must be compared separately."
        ),
        "points_before": [_point_dump(point) for point in original],
        "points_after": [_point_dump(point) for point in refined],
    }


def zncc_acceptance_report(
    pair: RegistrationPair,
    original: list[ControlPoint],
    refined: list[ControlPoint],
    settings: RefinementSettings | None = None,
) -> dict[str, Any]:
    """Recompute existing ZNCC estimates for reporting only.

    Does not replace refine_points(). Failure to load rasters is recorded;
    counts are then unavailable rather than invented.
    """

    settings = settings or unvalidated_software_defaults()
    payload: dict[str, Any] = {
        "method_id": settings.method_id,
        "accepted_count": None,
        "rejected_count": None,
        "zncc_unavailable_count": 0,
        "points": [],
        "available": False,
    }
    if settings.method_id != "zncc_parabolic_baseline":
        payload["note"] = (
            "ZNCC acceptance is only defined for zncc_parabolic_baseline; "
            "identity passthrough does not estimate a peak."
        )
        return payload
    if not original:
        payload["accepted_count"] = 0
        payload["rejected_count"] = 0
        payload["available"] = True
        return payload

    source, reference, load_error = _load_intensity(pair)
    if source is None or reference is None:
        payload["note"] = load_error or "software rasters were not available"
        return payload

    accepted = 0
    rejected = 0
    unavailable = 0
    rows: list[dict[str, Any]] = []
    for index, (before, after) in enumerate(zip(original, refined, strict=True)):
        estimate = estimate_zncc_displacement(
            source,
            reference,
            before.source_xy,
            before.reference_xy,
            settings,
        )
        zncc_before = _zncc_at(
            source, reference, before.source_xy, before.reference_xy, settings
        )
        zncc_after = _zncc_at(
            source, reference, after.source_xy, after.reference_xy, settings
        )
        if estimate is None:
            rejected += 1
            accepted_flag = False
            dx = dy = None
        else:
            accepted += 1
            accepted_flag = True
            dx, dy = float(estimate[0]), float(estimate[1])
        if zncc_before is None and zncc_after is None:
            unavailable += 1
        rows.append(
            {
                "index": index,
                "accepted": accepted_flag,
                "estimated_dx": dx,
                "estimated_dy": dy,
                "observed_displacement_pixels": coordinate_displacement_px(before, after),
                "zncc_at_original_reference": zncc_before,
                "zncc_at_refined_reference": zncc_after,
            }
        )
    payload.update(
        {
            "available": True,
            "accepted_count": accepted,
            "rejected_count": rejected,
            "zncc_unavailable_count": unavailable,
            "points": rows,
        }
    )
    return payload


def control_point_held_out(
    points: list[ControlPoint], *, model_id: str, settings: HeldOutSettings
) -> dict[str, Any]:
    """K-fold held-out transfer error on control-point coordinates.

    Variant A and B must pass the same-length lists in the same order with
    the same rng_seed so the fold assignment is identical. Coordinates may
    differ after refinement. This is still matcher-derived, not ground truth.
    """

    wrapped = [_as_correspondence(point) for point in points]
    payload = held_out_validation(wrapped, model_id=model_id, settings=settings)
    payload["design"] = (
        "k-fold split of selected control-point coordinates; transform "
        "refitted on the complement of each fold and scored on the fold "
        "itself. Fold assignment is by point index, so unrefined vs refined "
        "lists of equal length share the same split."
    )
    payload["population"] = "selected_control_points"
    payload["independent_accuracy"] = INDEPENDENT_ACCURACY_NOT_VALIDATED
    payload["why_not_independent_accuracy"] = _WHY_NOT_ACCURACY
    return payload


def unselected_verified_checkpoints(
    matrix: np.ndarray | None,
    inliers: list[Correspondence],
    control_points: list[ControlPoint],
) -> dict[str, Any]:
    """Score the fitted transform on verified inliers that were not selected.

    The checkpoint identities are the same for A and B because selection
    happens before refinement. Only the fitted matrix differs.
    """

    selected = {(point.source_xy, point.reference_xy) for point in control_points}
    checkpoints = [
        item for item in inliers if (item.source_xy, item.reference_xy) not in selected
    ]
    payload: dict[str, Any] = {
        "design": (
            "transform fitted from selected control points, scored on verified "
            "inliers that were not selected as control points. Checkpoint "
            "identities are identical across refinement variants."
        ),
        "checkpoint_count": len(checkpoints),
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "independent_ground_truth_used": False,
        "why_not_independent_accuracy": _WHY_NOT_ACCURACY,
        "units": "original image pixels (reference frame transfer error)",
    }
    if matrix is None:
        payload["status"] = STATUS_NO_TRANSFORM
        payload["checkpoint_transfer_error_pixels"] = None
        return payload
    if not checkpoints:
        payload["status"] = STATUS_NO_CHECKPOINTS
        payload["reason"] = (
            "every verified inlier was selected as a control point, so no "
            "unselected checkpoint set remains"
        )
        payload["checkpoint_transfer_error_pixels"] = None
        return payload

    source_xy = np.array([item.source_xy for item in checkpoints], dtype=float)
    reference_xy = np.array([item.reference_xy for item in checkpoints], dtype=float)
    raw = image_space_transfer_error(source_xy, reference_xy, np.asarray(matrix, dtype=float))
    errors = [float(value) for value in raw if math.isfinite(value)]
    if not errors:
        payload["status"] = STATUS_NO_CHECKPOINTS
        payload["reason"] = "all unselected checkpoint transfer errors were non-finite"
        payload["checkpoint_transfer_error_pixels"] = None
        return payload
    payload["status"] = "HELD_OUT_CROSS_VALIDATION_COMPLETED"
    payload["held_out_point_count"] = len(errors)
    payload["checkpoint_transfer_error_pixels"] = _error_summary(errors)
    return payload


def _load_intensity(
    pair: RegistrationPair,
) -> tuple[np.ndarray | None, np.ndarray | None, str | None]:
    source_array, source_error = load_software_raster(pair.source.raster_uri)
    reference_array, reference_error = load_software_raster(pair.reference.raster_uri)
    if source_array is None or reference_array is None:
        return None, None, source_error or reference_error
    source = as_intensity(source_array)
    reference = as_intensity(reference_array)
    if source is None or reference is None:
        return None, None, "intensity conversion failed"
    return source, reference, None


def _zncc_at(
    source: np.ndarray,
    reference: np.ndarray,
    source_xy: tuple[float, float],
    reference_xy: tuple[float, float],
    settings: RefinementSettings,
) -> float | None:
    template = extract_window(source, source_xy[0], source_xy[1], settings.window_radius)
    patch = extract_window(
        reference, reference_xy[0], reference_xy[1], settings.window_radius
    )
    if template is None or patch is None:
        return None
    min_valid = max(4, int(math.ceil(settings.min_valid_pixel_fraction * template.size)))
    return zncc(template, patch, min_valid)


def _as_correspondence(point: ControlPoint) -> Correspondence:
    return Correspondence(
        source_xy=point.source_xy,
        reference_xy=point.reference_xy,
        residual=point.residual,
        status="inlier",
    )


def _point_dump(point: ControlPoint) -> dict[str, Any]:
    return {
        "source_xy": list(point.source_xy),
        "reference_xy": list(point.reference_xy),
        "residual": point.residual,
    }


def _error_summary(errors: list[float]) -> dict[str, float]:
    values = np.asarray(errors, dtype=float)
    return {
        "count": int(values.size),
        "min": float(values.min()),
        "median": float(np.median(values)),
        "mean": float(values.mean()),
        "max": float(values.max()),
        "rmse": float(np.sqrt(np.mean(np.square(values)))),
    }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _max(values: list[float]) -> float | None:
    if not values:
        return None
    return float(max(values))


__all__ = [
    "control_point_held_out",
    "coordinate_displacement_px",
    "coordinates_changed",
    "displacement_report",
    "unselected_verified_checkpoints",
    "zncc_acceptance_report",
]
