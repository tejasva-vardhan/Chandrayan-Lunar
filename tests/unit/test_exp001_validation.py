"""Held-out validation tests.

The point of this module is to make sure EXP-001 cannot repeat EXP-000's
central reporting error: quoting a four-point fit residual as if it measured
accuracy. These tests assert both that held-out scoring works when there is
enough evidence and that it refuses to produce a number when there is not.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.io.exp001.validation import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    STATUS_COMPLETED,
    STATUS_INSUFFICIENT,
    STATUS_NO_CHECKPOINTS,
    STATUS_NO_TRANSFORM,
    HeldOutSettings,
    cross_matcher_checkpoints,
    held_out_validation,
)
from src.models.correspondence_set import Correspondence

_MODEL_ID = "projective_2d_baseline"
_MIN_SAMPLES = 4


def _affine_correspondences(
    count: int, *, jitter: float = 0.0, seed: int = 0
) -> list[Correspondence]:
    """Correspondences consistent with a known similarity transform."""

    rng = np.random.default_rng(seed)
    points = rng.uniform(0.0, 1000.0, size=(count, 2))
    matrix = np.array([[1.03, -0.06, 25.0], [0.06, 1.03, -14.0], [0.0, 0.0, 1.0]])
    homogeneous = np.concatenate([points, np.ones((count, 1))], axis=1)
    mapped = (matrix @ homogeneous.T).T
    mapped = mapped[:, :2] / mapped[:, 2:3]
    if jitter:
        mapped = mapped + rng.normal(0.0, jitter, size=mapped.shape)
    return [
        Correspondence(
            source_xy=(float(points[i, 0]), float(points[i, 1])),
            reference_xy=(float(mapped[i, 0]), float(mapped[i, 1])),
            status="inlier",
        )
        for i in range(count)
    ]


def test_exactly_the_model_minimum_cannot_be_validated() -> None:
    """Four inliers against a four-point model leave nothing to hold out."""

    payload = held_out_validation(
        _affine_correspondences(_MIN_SAMPLES),
        model_id=_MODEL_ID,
        settings=HeldOutSettings(),
    )

    assert payload["status"] == STATUS_INSUFFICIENT
    assert payload["held_out_transfer_error_pixels"] is None
    assert payload["held_out_point_count"] == 0
    assert payload["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert "minimum sample size" in payload["reason"]


def test_fewer_than_the_model_minimum_cannot_be_validated() -> None:
    payload = held_out_validation(
        _affine_correspondences(2), model_id=_MODEL_ID, settings=HeldOutSettings()
    )

    assert payload["status"] == STATUS_INSUFFICIENT
    assert payload["held_out_transfer_error_pixels"] is None


def test_consistent_correspondences_produce_small_held_out_error() -> None:
    """A transform that generalises should predict points it never saw."""

    payload = held_out_validation(
        _affine_correspondences(40), model_id=_MODEL_ID, settings=HeldOutSettings()
    )

    assert payload["status"] == STATUS_COMPLETED
    assert payload["held_out_point_count"] == 40
    assert payload["held_out_transfer_error_pixels"]["rmse"] < 1e-6


def test_noisy_correspondences_produce_larger_held_out_error_than_clean_ones() -> None:
    """Held-out error must actually respond to correspondence quality."""

    clean = held_out_validation(
        _affine_correspondences(40, seed=1),
        model_id=_MODEL_ID,
        settings=HeldOutSettings(),
    )
    noisy = held_out_validation(
        _affine_correspondences(40, jitter=3.0, seed=1),
        model_id=_MODEL_ID,
        settings=HeldOutSettings(),
    )

    assert clean["status"] == noisy["status"] == STATUS_COMPLETED
    clean_rmse = clean["held_out_transfer_error_pixels"]["rmse"]
    noisy_rmse = noisy["held_out_transfer_error_pixels"]["rmse"]
    assert noisy_rmse > clean_rmse
    assert noisy_rmse > 1.0


def test_held_out_error_is_not_the_fitting_residual() -> None:
    """The five-point case: a fit residual near zero but a real held-out error.

    With five noisy correspondences a projective model still very nearly
    interpolates, so the fitting residual is tiny. Held-out scoring removes a
    point from the fit and exposes the error the residual concealed.
    """

    from src.verification.geometric_models import get_geometric_model

    correspondences = _affine_correspondences(5, jitter=4.0, seed=5)
    source = np.array([item.source_xy for item in correspondences])
    reference = np.array([item.reference_xy for item in correspondences])
    model = get_geometric_model(_MODEL_ID)
    matrix = model.fit(source, reference)
    assert matrix is not None
    fitting_residual = float(np.sqrt(np.mean(model.residuals(source, reference, matrix) ** 2)))

    payload = held_out_validation(
        correspondences, model_id=_MODEL_ID, settings=HeldOutSettings()
    )

    assert payload["status"] == STATUS_COMPLETED
    assert payload["held_out_transfer_error_pixels"]["rmse"] > fitting_residual


def test_held_out_validation_is_deterministic() -> None:
    correspondences = _affine_correspondences(30, jitter=1.0, seed=9)
    first = held_out_validation(
        correspondences, model_id=_MODEL_ID, settings=HeldOutSettings()
    )
    second = held_out_validation(
        correspondences, model_id=_MODEL_ID, settings=HeldOutSettings()
    )

    assert first["held_out_transfer_error_pixels"] == second["held_out_transfer_error_pixels"]


def test_held_out_validation_never_claims_independent_accuracy() -> None:
    for count in (0, 4, 40):
        payload = held_out_validation(
            _affine_correspondences(count) if count else [],
            model_id=_MODEL_ID,
            settings=HeldOutSettings(),
        )
        assert payload["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
        assert payload["independent_ground_truth_used"] is False


def test_folds_must_be_at_least_two() -> None:
    with pytest.raises(ValueError, match="folds"):
        HeldOutSettings(folds=1)


def test_cross_matcher_checkpoints_score_a_foreign_correspondence_set() -> None:
    matrix = np.array([[1.03, -0.06, 25.0], [0.06, 1.03, -14.0], [0.0, 0.0, 1.0]])
    payload = cross_matcher_checkpoints(
        matrix,
        _affine_correspondences(12, seed=4),
        source_matcher_id="sift",
        checkpoint_matcher_ids=["rift", "rift"],
    )

    assert payload["status"] == STATUS_COMPLETED
    assert payload["checkpoint_count"] == 12
    assert payload["checkpoint_matcher_ids"] == ["rift"]
    assert payload["checkpoint_transfer_error_pixels"]["rmse"] < 1e-6
    assert payload["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED


def test_cross_matcher_checkpoints_without_a_transform() -> None:
    payload = cross_matcher_checkpoints(
        None,
        _affine_correspondences(5),
        source_matcher_id="orb",
        checkpoint_matcher_ids=["sift"],
    )

    assert payload["status"] == STATUS_NO_TRANSFORM
    assert payload["checkpoint_transfer_error_pixels"] is None


def test_cross_matcher_checkpoints_without_checkpoints() -> None:
    matrix = np.eye(3)
    payload = cross_matcher_checkpoints(
        matrix, [], source_matcher_id="sift", checkpoint_matcher_ids=[]
    )

    assert payload["status"] == STATUS_NO_CHECKPOINTS
    assert payload["checkpoint_transfer_error_pixels"] is None
