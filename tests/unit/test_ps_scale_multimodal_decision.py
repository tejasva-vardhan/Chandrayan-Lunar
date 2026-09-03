"""Unit tests for PS-SCALE-MULTIMODAL decision rules."""

from __future__ import annotations

from src.io.ps_scale_multimodal.config import (
    DECISION_INDETERMINATE,
    DECISION_NOT_SUPPORTED,
    DECISION_SUPPORTED,
)
from src.io.ps_scale_multimodal.decision import (
    apply_cross_sensor_decision,
    apply_scale_decision,
)


def _scale_kwargs(**overrides):
    base = {
        "independent_variable_applied": True,
        "native_gsd_ratio_value": 0.56,
        "verified_inliers_a": 72,
        "verified_inliers_b": 70,
        "source_occupied_a": 23,
        "source_occupied_b": 22,
        "reference_occupied_a": 14,
        "reference_occupied_b": 13,
        "transform_fitted_a": True,
        "transform_fitted_b": True,
        "min_samples": 4,
    }
    base.update(overrides)
    return base


def _cross_kwargs(**overrides):
    base = {
        "independent_variable_applied": True,
        "verified_inliers_a": 72,
        "verified_inliers_c": 60,
        "source_occupied_a": 23,
        "source_occupied_c": 20,
        "reference_occupied_a": 14,
        "reference_occupied_c": 12,
        "transform_fitted_a": True,
        "transform_fitted_c": True,
        "min_samples": 4,
    }
    base.update(overrides)
    return base


def test_scale_supported_when_maintained() -> None:
    result = apply_scale_decision(**_scale_kwargs())
    assert result["decision"] == DECISION_SUPPORTED


def test_scale_not_supported_on_collapse() -> None:
    result = apply_scale_decision(**_scale_kwargs(verified_inliers_b=10))
    assert result["decision"] == DECISION_NOT_SUPPORTED


def test_scale_indeterminate_without_material_gsd_ratio() -> None:
    result = apply_scale_decision(**_scale_kwargs(native_gsd_ratio_value=1.01))
    assert result["decision"] == DECISION_INDETERMINATE


def test_cross_sensor_supported_when_maintained() -> None:
    result = apply_cross_sensor_decision(**_cross_kwargs())
    assert result["decision"] == DECISION_SUPPORTED


def test_cross_sensor_not_supported_at_dlt_floor() -> None:
    result = apply_cross_sensor_decision(**_cross_kwargs(verified_inliers_c=4))
    assert result["decision"] == DECISION_NOT_SUPPORTED


def test_cross_sensor_indeterminate_when_variable_not_applied() -> None:
    result = apply_cross_sensor_decision(**_cross_kwargs(independent_variable_applied=False))
    assert result["decision"] == DECISION_INDETERMINATE
