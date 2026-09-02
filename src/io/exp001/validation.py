"""Held-out correspondence validation for EXP-001.

Why this module exists
----------------------
EXP-000 reported ``rmse = 4.4e-10`` pixels. That number is the RMSE of the
verification residuals of the very correspondences that were used to fit the
transform, and the fit used exactly four points against a projective model
whose minimum sample size is four. A four-point projective fit passes through
its four points by construction, so the residual is a property of linear
algebra, not of registration accuracy.

This module supplies the only honest alternative available from the data:
split the verified correspondences, fit on one part, and measure transfer
error on the part that was withheld from the fit.

What this does and does not establish
-------------------------------------
It **does** establish whether a fitted transform generalises beyond the
points that produced it. A model that fits four points perfectly but cannot
predict a fifth has not been validated by its residual.

It **does not** establish independent accuracy, and this module never claims
it does. Held-out points are still matcher-derived, and they were selected by
the same RANSAC consensus that produced the fitting points, so their errors
are correlated with the fit. There is no surveyed lunar ground control, no
independent DEM tie point, and no external checkpoint set in this project's
data. Every payload this module returns therefore carries
``independent_accuracy = "NOT VALIDATED"`` regardless of outcome.

``cross_matcher_checkpoints`` is a weaker-correlation variant: it scores one
matcher's transform against correspondences that a *different* matcher found
and verified. Those checkpoints come from an independent detector and
descriptor, so they are not part of the same consensus set, but they are
still algorithmic output rather than ground truth. It is also labelled
``NOT VALIDATED``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.models.correspondence_set import Correspondence
from src.verification.geometric_models import get_geometric_model
from src.verification.residuals import image_space_transfer_error

INDEPENDENT_ACCURACY_NOT_VALIDATED = "NOT VALIDATED"

STATUS_COMPLETED = "HELD_OUT_CROSS_VALIDATION_COMPLETED"
STATUS_INSUFFICIENT = "NOT_POSSIBLE_INSUFFICIENT_VERIFIED_CORRESPONDENCES"
STATUS_NO_USABLE_FOLD = "NOT_POSSIBLE_NO_FOLD_PRODUCED_A_VALID_FIT"
STATUS_NO_CHECKPOINTS = "NOT_POSSIBLE_NO_INDEPENDENT_CHECKPOINTS"
STATUS_NO_TRANSFORM = "NOT_POSSIBLE_NO_FITTED_TRANSFORM"


@dataclass(frozen=True, slots=True)
class HeldOutSettings:
    """Held-out split configuration.

    folds
        Requested number of cross-validation folds. The effective count is
        capped at the number of verified correspondences.
    rng_seed
        Deterministic shuffle seed. Set equal to the verification seed so the
        whole experiment has one random-state story.
    """

    folds: int = 5
    rng_seed: int = 0

    def __post_init__(self) -> None:
        if self.folds < 2:
            raise ValueError("folds must be >= 2")


def held_out_validation(
    correspondences: list[Correspondence],
    *,
    model_id: str,
    settings: HeldOutSettings,
) -> dict[str, Any]:
    """K-fold held-out transfer error over verified correspondences.

    Each fold refits ``model_id`` on the correspondences outside the fold and
    measures image-space transfer error on the correspondences inside it,
    which never touched that fit.
    """

    model = get_geometric_model(model_id)
    usable = [item for item in correspondences if _finite(item)]
    total = len(usable)

    payload: dict[str, Any] = {
        "design": (
            "k-fold split of verified correspondences; transform refitted on "
            "the complement of each fold and scored on the fold itself"
        ),
        "model_id": model_id,
        "model_min_samples": model.min_samples,
        "requested_folds": settings.folds,
        "rng_seed": settings.rng_seed,
        "verified_correspondences_available": total,
        "minimum_required": model.min_samples + 1,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "independent_ground_truth_used": False,
        "why_not_independent_accuracy": (
            "held-out points are matcher-derived and were selected by the same "
            "RANSAC consensus as the fitting points, so their errors are "
            "correlated with the fit; no surveyed lunar control exists"
        ),
    }

    if total < model.min_samples + 1:
        payload["status"] = STATUS_INSUFFICIENT
        payload["reason"] = (
            f"{total} verified correspondences cannot be split into a fit set of "
            f"at least {model.min_samples} and a non-empty held-out set. A "
            f"verified count equal to {model.min_samples} is the model's minimum "
            "sample size, so nothing is left to withhold."
        )
        payload["effective_folds"] = 0
        payload["held_out_point_count"] = 0
        payload["held_out_transfer_error_pixels"] = None
        return payload

    source_xy = np.array([item.source_xy for item in usable], dtype=float)
    reference_xy = np.array([item.reference_xy for item in usable], dtype=float)

    rng = np.random.default_rng(settings.rng_seed)
    order = rng.permutation(total)
    effective_folds = min(settings.folds, total)
    fold_assignment = np.array_split(order, effective_folds)

    errors: list[float] = []
    used_folds = 0
    skipped_folds = 0
    for fold in fold_assignment:
        if fold.size == 0:
            continue
        mask = np.ones(total, dtype=bool)
        mask[fold] = False
        if int(np.count_nonzero(mask)) < model.min_samples:
            skipped_folds += 1
            continue
        matrix = model.fit(source_xy[mask], reference_xy[mask])
        if matrix is None:
            skipped_folds += 1
            continue
        fold_errors = image_space_transfer_error(
            source_xy[fold], reference_xy[fold], matrix
        )
        finite = [float(value) for value in fold_errors if math.isfinite(value)]
        if not finite:
            skipped_folds += 1
            continue
        errors.extend(finite)
        used_folds += 1

    payload["effective_folds"] = effective_folds
    payload["folds_used"] = used_folds
    payload["folds_skipped"] = skipped_folds
    payload["held_out_point_count"] = len(errors)

    if not errors:
        payload["status"] = STATUS_NO_USABLE_FOLD
        payload["reason"] = (
            "every fold either left fewer points than the model minimum or "
            "produced a degenerate fit"
        )
        payload["held_out_transfer_error_pixels"] = None
        return payload

    payload["status"] = STATUS_COMPLETED
    payload["held_out_transfer_error_pixels"] = _error_summary(errors)
    payload["units"] = "original image pixels (reference frame transfer error)"
    return payload


def cross_matcher_checkpoints(
    matrix: np.ndarray | None,
    checkpoints: list[Correspondence],
    *,
    source_matcher_id: str,
    checkpoint_matcher_ids: list[str],
) -> dict[str, Any]:
    """Score one matcher's transform on another matcher's verified points.

    Checkpoints come from a different detector and descriptor, so they are
    not members of the consensus set that produced ``matrix``. They are still
    algorithmic output, not ground truth.
    """

    payload: dict[str, Any] = {
        "design": (
            "transform fitted by one matcher evaluated on correspondences "
            "verified by different matchers"
        ),
        "transform_from_matcher_id": source_matcher_id,
        "checkpoint_matcher_ids": sorted(set(checkpoint_matcher_ids)),
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "independent_ground_truth_used": False,
        "why_not_independent_accuracy": (
            "checkpoints are produced by another matcher, not by surveyed "
            "lunar control; agreement between two algorithms is consistency, "
            "not accuracy"
        ),
    }

    if matrix is None:
        payload["status"] = STATUS_NO_TRANSFORM
        payload["checkpoint_count"] = 0
        payload["checkpoint_transfer_error_pixels"] = None
        return payload

    usable = [item for item in checkpoints if _finite(item)]
    payload["checkpoint_count"] = len(usable)
    if not usable:
        payload["status"] = STATUS_NO_CHECKPOINTS
        payload["reason"] = (
            "no other matcher produced verified correspondences on this pair, "
            "so no cross-matcher checkpoint set exists"
        )
        payload["checkpoint_transfer_error_pixels"] = None
        return payload

    source_xy = np.array([item.source_xy for item in usable], dtype=float)
    reference_xy = np.array([item.reference_xy for item in usable], dtype=float)
    raw = image_space_transfer_error(source_xy, reference_xy, np.asarray(matrix, dtype=float))
    errors = [float(value) for value in raw if math.isfinite(value)]

    if not errors:
        payload["status"] = STATUS_NO_CHECKPOINTS
        payload["reason"] = "all checkpoint transfer errors were non-finite"
        payload["checkpoint_transfer_error_pixels"] = None
        return payload

    payload["status"] = STATUS_COMPLETED
    payload["checkpoint_transfer_error_pixels"] = _error_summary(errors)
    payload["units"] = "original image pixels (reference frame transfer error)"
    return payload


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


def _finite(item: Correspondence) -> bool:
    return (
        math.isfinite(item.source_xy[0])
        and math.isfinite(item.source_xy[1])
        and math.isfinite(item.reference_xy[0])
        and math.isfinite(item.reference_xy[1])
    )


__all__ = [
    "INDEPENDENT_ACCURACY_NOT_VALIDATED",
    "STATUS_COMPLETED",
    "STATUS_INSUFFICIENT",
    "STATUS_NO_CHECKPOINTS",
    "STATUS_NO_TRANSFORM",
    "STATUS_NO_USABLE_FOLD",
    "HeldOutSettings",
    "cross_matcher_checkpoints",
    "held_out_validation",
]
