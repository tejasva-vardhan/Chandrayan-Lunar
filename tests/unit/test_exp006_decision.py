"""Pre-registered EXP-006 decision-rule tests. Not lunar accuracy evidence."""

from __future__ import annotations

from src.io.exp006.config import (
    DECISION_INDETERMINATE,
    DECISION_NOT_SUPPORTED,
    DECISION_SUPPORTED,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
)
from src.io.exp006.decision import apply_decision_rule


def _ok(**overrides: object) -> dict:
    payload = dict(
        independent_variable_applied=True,
        verified_inliers_a=25,
        verified_inliers_b=30,
        inlier_ratio_a=0.027,
        inlier_ratio_b=0.12,
        source_occupied_a=11,
        source_occupied_b=14,
        reference_occupied_a=9,
        reference_occupied_b=11,
        transform_fitted_a=True,
        transform_fitted_b=True,
        min_samples=4,
        match_runtime_a=3.0,
        match_runtime_b=4.5,
    )
    payload.update(overrides)
    return apply_decision_rule(**payload)  # type: ignore[arg-type]


def test_supported_requires_quality_and_spatial_and_stability() -> None:
    result = _ok()
    assert result["decision"] == DECISION_SUPPORTED
    assert result["hypothesis_supported"] is True
    assert result["quality_improved"] is True
    assert result["spatial_maintained_or_improved"] is True
    assert result["transform_stable"] is True
    assert result["runtime_acceptable"] is True
    assert result["raw_match_count_is_not_success"] is True
    assert result["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED


def test_equal_inliers_is_not_supported_even_if_ratio_rises() -> None:
    result = _ok(verified_inliers_b=25, inlier_ratio_b=0.2)
    assert result["decision"] == DECISION_NOT_SUPPORTED
    assert result["quality_improved"] is False


def test_more_inliers_with_collapsed_ratio_is_not_supported() -> None:
    result = _ok(verified_inliers_b=40, inlier_ratio_b=0.01)
    assert result["decision"] == DECISION_NOT_SUPPORTED
    assert result["quality_improved"] is False


def test_spatial_concentration_is_not_supported() -> None:
    result = _ok(source_occupied_b=8)
    assert result["decision"] == DECISION_NOT_SUPPORTED
    assert result["spatial_maintained_or_improved"] is False


def test_minimal_sample_fit_is_not_stable() -> None:
    result = _ok(verified_inliers_a=4, verified_inliers_b=8, inlier_ratio_a=0.1)
    assert result["transform_stable"] is False
    assert result["decision"] == DECISION_NOT_SUPPORTED


def test_runtime_blowup_is_not_supported() -> None:
    result = _ok(match_runtime_b=16.0)
    assert result["runtime_acceptable"] is False
    assert result["decision"] == DECISION_NOT_SUPPORTED


def test_missing_occupancy_is_indeterminate() -> None:
    result = _ok(source_occupied_b=None)
    assert result["decision"] == DECISION_INDETERMINATE
    assert result["critical_measurements_missing"] is True
    assert result["hypothesis_supported"] is False


def test_wrong_independent_variable_is_indeterminate() -> None:
    result = _ok(independent_variable_applied=False)
    assert result["decision"] == DECISION_INDETERMINATE
    assert result["independent_variable_applied"] is False
