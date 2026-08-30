"""Replaceable robust estimators for correspondence verification.

Master spec v3 §18 allows a RANSAC/MAGSAC-style method where justified. This
package implements one RANSAC-style baseline so software tests can run. It is
not a selected scientific estimator. MAGSAC and other estimators are not
implemented; they can be added behind the same registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from src.verification.geometric_models import GeometricModel
from src.verification.settings import VerificationSettings


@dataclass(frozen=True, slots=True)
class RobustFit:
    """Outcome of robust estimation. matrix is None when estimation failed."""

    matrix: np.ndarray | None
    inlier_mask: np.ndarray
    residuals: np.ndarray


class RobustEstimator(ABC):
    estimator_id: str
    role: str

    @abstractmethod
    def estimate(
        self,
        source_xy: np.ndarray,
        reference_xy: np.ndarray,
        model: GeometricModel,
        settings: VerificationSettings,
    ) -> RobustFit:
        """Classify candidates. Never marks inliers when a model cannot be fit."""


class RansacStyleBaseline(RobustEstimator):
    """Classic RANSAC over a GeometricModel. TEST/BASELINE ESTIMATOR.

    Sampling uses numpy Generator(settings.rng_seed). Inlier test is
    residual <= settings.residual_limit using the residual in residuals.py.
    After the best consensus set is found, the model is refit on those
    inliers when their count is at least model.min_samples.

    residual_limit, max_trials, and rng_seed are caller-supplied engineering
    settings. The values 3.0, 500, and 0 appear only as
    unvalidated_software_defaults() for the frozen two-argument API; this
    estimator does not treat those values as SIH or lunar-validated.

    This is not MAGSAC, not LO-RANSAC, and not a claim of optimality.
    """

    estimator_id = "ransac_style_baseline"
    role = "test_generating_or_software_baseline"

    def estimate(
        self,
        source_xy: np.ndarray,
        reference_xy: np.ndarray,
        model: GeometricModel,
        settings: VerificationSettings,
    ) -> RobustFit:
        n = source_xy.shape[0]
        empty_mask = np.zeros(n, dtype=bool)
        infinite = np.full(n, np.inf, dtype=float)
        if n < model.min_samples:
            return RobustFit(matrix=None, inlier_mask=empty_mask, residuals=infinite)

        rng = np.random.default_rng(settings.rng_seed)
        best_mask: np.ndarray | None = None
        best_count = -1
        best_matrix: np.ndarray | None = None

        for _ in range(settings.max_trials):
            sample = rng.choice(n, size=model.min_samples, replace=False)
            fitted = model.fit(source_xy[sample], reference_xy[sample])
            if fitted is None:
                continue
            residuals = model.residuals(source_xy, reference_xy, fitted)
            mask = residuals <= settings.residual_limit
            count = int(np.count_nonzero(mask))
            if count > best_count:
                best_count = count
                best_mask = mask
                best_matrix = fitted

        if best_matrix is None or best_mask is None or best_count < model.min_samples:
            return RobustFit(matrix=None, inlier_mask=empty_mask, residuals=infinite)

        refit = model.fit(source_xy[best_mask], reference_xy[best_mask])
        matrix = best_matrix if refit is None else refit
        residuals = model.residuals(source_xy, reference_xy, matrix)
        mask = residuals <= settings.residual_limit
        if int(np.count_nonzero(mask)) < model.min_samples:
            return RobustFit(matrix=None, inlier_mask=empty_mask, residuals=infinite)
        return RobustFit(matrix=matrix, inlier_mask=mask, residuals=residuals)


def get_estimator(estimator_id: str) -> RobustEstimator:
    registry: dict[str, type[RobustEstimator]] = {
        RansacStyleBaseline.estimator_id: RansacStyleBaseline,
    }
    try:
        cls = registry[estimator_id]
    except KeyError as exc:
        known = ", ".join(sorted(registry))
        raise ValueError(f"unknown estimator_id={estimator_id!r}; known: {known}") from exc
    return cls()
