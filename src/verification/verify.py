"""Geometric verification orchestration.

Frozen pipeline surface: verify_matches(correspondences, pair) -> CorrespondenceSet.

Matcher-independent: only Correspondence fields are used. matcher_id is copied
through and never interpreted. RegistrationPair is accepted for the frozen
signature; rasters, masks, GSD, and characterization are not used because
their interpretation is not defined in this freeze.
"""

from __future__ import annotations

import math

import numpy as np

from src.models.correspondence_set import Correspondence, CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.verification.estimators import RobustFit, get_estimator
from src.verification.filtering import classify_correspondences
from src.verification.geometric_models import get_geometric_model
from src.verification.settings import VerificationSettings, unvalidated_software_defaults


def verify_matches(
    correspondences: CorrespondenceSet, pair: RegistrationPair
) -> CorrespondenceSet:
    """Filter and geometrically verify correspondences (frozen two-argument API).

    Uses unvalidated_software_defaults(), including residual_limit=3.0,
    max_trials=500, and rng_seed=0. Those numbers exist only because this
    frozen signature has no settings argument. They are software/test
    defaults, not SIH thresholds, not lunar-validated parameters, not final
    scientific parameters, and not benchmark results.

    The wired model/estimator is a software baseline, not a selected lunar
    model. Call verify_correspondences to supply explicit settings.
    """

    return verify_correspondences(correspondences, pair, unvalidated_software_defaults())


def verify_correspondences(
    correspondences: CorrespondenceSet,
    pair: RegistrationPair,
    settings: VerificationSettings,
) -> CorrespondenceSet:
    """Configurable verification. pair is unused beyond the frozen signature."""

    _ = pair
    model = get_geometric_model(settings.model_id)
    estimator = get_estimator(settings.estimator_id)
    matches = list(correspondences.matches)

    if not matches:
        return correspondences.model_copy(update={"matches": []})

    outcome = classify_correspondences(matches, settings)
    statuses: list[str] = ["raw"] * len(matches)
    residuals: list[float | None] = [None] * len(matches)

    for index in outcome.rejected_indices:
        statuses[index] = "rejected"

    candidate_indices = outcome.candidate_indices
    for index in candidate_indices:
        statuses[index] = "filtered"

    if len(candidate_indices) < model.min_samples:
        # Validated but not geometrically verified. Not inliers.
        return _assemble(correspondences, matches, statuses, residuals)

    source_xy = np.array([matches[i].source_xy for i in candidate_indices], dtype=float)
    reference_xy = np.array([matches[i].reference_xy for i in candidate_indices], dtype=float)
    fit: RobustFit = estimator.estimate(source_xy, reference_xy, model, settings)

    if fit.matrix is None:
        return _assemble(correspondences, matches, statuses, residuals)

    for local, index in enumerate(candidate_indices):
        residual = float(fit.residuals[local])
        residuals[index] = residual if math.isfinite(residual) else None
        statuses[index] = "inlier" if bool(fit.inlier_mask[local]) else "rejected"

    return _assemble(correspondences, matches, statuses, residuals)


def _assemble(
    correspondences: CorrespondenceSet,
    original: list[Correspondence],
    statuses: list[str],
    residuals: list[float | None],
) -> CorrespondenceSet:
    updated = [
        original[i].model_copy(update={"status": statuses[i], "residual": residuals[i]})
        for i in range(len(original))
    ]
    return correspondences.model_copy(update={"matches": updated})
