"""Synthetic evaluation tests. Software validation only — not lunar accuracy.

Constructed statuses, residuals, and coordinates check implementation
arithmetic. They are not Chandrayaan-2 results and are not SIH evaluator
evidence (D-011, D-012).
"""

from __future__ import annotations

import math

import pytest

from src.evaluation import evaluate
from src.models import (
    ControlPoint,
    Correspondence,
    CorrespondenceSet,
    LunarProduct,
    RegistrationPair,
    RegistrationResult,
)
from src.models.common import ImageDimensions

pytestmark = pytest.mark.scientific


def _pair(width: int, height: int) -> RegistrationPair:
    dims = ImageDimensions(width_px=width, height_px=height)
    return RegistrationPair(
        pair_id="synthetic-eval",
        source=LunarProduct(product_id="src", instrument="OHRC", dimensions=dims),
        reference=LunarProduct(product_id="ref", instrument="LRO_NAC", dimensions=dims),
    )


def _result(
    pair: RegistrationPair,
    matches: list[Correspondence],
    control_points: list[ControlPoint] | None = None,
) -> RegistrationResult:
    return RegistrationResult(
        pair_id=pair.pair_id,
        correspondences=CorrespondenceSet(
            pair_id=pair.pair_id, matcher_id="synthetic-generator", matches=matches
        ),
        control_points=list(control_points or []),
    )


def test_synthetic_zero_transfer_error_rmse() -> None:
    # Synthetic stored residuals (TEST ONLY). Not a lunar generating model.
    pair = _pair(32, 32)
    matches = [
        Correspondence(
            source_xy=(float(x), float(y)),
            reference_xy=(float(x), float(y)),
            status="inlier",
            residual=0.0,
        )
        for x, y in ((0, 0), (8, 0), (0, 8), (8, 8))
    ]
    metrics = evaluate(_result(pair, matches), pair).metrics
    assert metrics is not None
    assert metrics.rmse == 0.0
    assert metrics.inlier_count == 4
    assert metrics.inlier_ratio == 1.0


def test_synthetic_known_rmse_and_ratio() -> None:
    pair = _pair(32, 32)
    matches = [
        Correspondence(
            source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0), status="inlier", residual=1.0
        ),
        Correspondence(
            source_xy=(4.0, 0.0), reference_xy=(4.0, 0.0), status="inlier", residual=2.0
        ),
        Correspondence(
            source_xy=(8.0, 0.0), reference_xy=(8.0, 0.0), status="inlier", residual=2.0
        ),
        Correspondence(
            source_xy=(0.0, 4.0),
            reference_xy=(90.0, 90.0),
            status="rejected",
            residual=50.0,
        ),
    ]
    metrics = evaluate(_result(pair, matches), pair).metrics
    assert metrics is not None
    assert metrics.inlier_count == 3
    assert metrics.inlier_ratio == pytest.approx(0.75)
    assert metrics.rmse == pytest.approx(math.sqrt((1.0 + 4.0 + 4.0) / 3.0))


def test_synthetic_known_coverage_box() -> None:
    pair = _pair(100, 50)
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0)),
        ControlPoint(source_xy=(50.0, 0.0), reference_xy=(50.0, 0.0)),
        ControlPoint(source_xy=(0.0, 25.0), reference_xy=(0.0, 25.0)),
        ControlPoint(source_xy=(50.0, 25.0), reference_xy=(50.0, 25.0)),
    ]
    metrics = evaluate(_result(pair, [], points), pair).metrics
    assert metrics is not None
    assert metrics.control_point_count == 4
    # AABB 50 * 25 = 1250; image 100 * 50 = 5000; mean of identical fractions.
    assert metrics.spatial_coverage == pytest.approx(1250.0 / 5000.0)


def test_synthetic_empty_set_does_not_fabricate_perfect_scores() -> None:
    pair = _pair(16, 16)
    metrics = evaluate(_result(pair, []), pair).metrics
    assert metrics is not None
    assert metrics.rmse is None
    assert metrics.inlier_ratio is None
    assert metrics.inlier_count == 0
    assert metrics.spatial_coverage is None
    assert metrics.control_point_count == 0
