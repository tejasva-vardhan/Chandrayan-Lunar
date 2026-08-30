"""Unit tests for evaluation. Not lunar accuracy evidence."""

from __future__ import annotations

import math

import pytest

from src.evaluation import evaluate
from src.evaluation.metrics import (
    count_inliers,
    inlier_ratio_from_matches,
    rmse_from_inlier_residuals,
)
from src.models import (
    ControlPoint,
    Correspondence,
    CorrespondenceSet,
    LunarProduct,
    RegistrationPair,
    RegistrationResult,
    TransformationModel,
)
from src.models.common import ImageDimensions
from src.pipeline.operations import evaluate as pipeline_evaluate


def _pair(
    *,
    pair_id: str = "pair-eval",
    source_wh: tuple[int, int] | None = None,
    reference_wh: tuple[int, int] | None = None,
) -> RegistrationPair:
    source_dims = (
        ImageDimensions(width_px=source_wh[0], height_px=source_wh[1])
        if source_wh is not None
        else None
    )
    reference_dims = (
        ImageDimensions(width_px=reference_wh[0], height_px=reference_wh[1])
        if reference_wh is not None
        else None
    )
    return RegistrationPair(
        pair_id=pair_id,
        source=LunarProduct(
            product_id="src-eval", instrument="OHRC", dimensions=source_dims
        ),
        reference=LunarProduct(
            product_id="ref-eval", instrument="LRO_NAC", dimensions=reference_dims
        ),
    )


def _match(
    source_xy: tuple[float, float],
    reference_xy: tuple[float, float],
    *,
    status: str = "raw",
    residual: float | None = None,
) -> Correspondence:
    return Correspondence(
        source_xy=source_xy,
        reference_xy=reference_xy,
        status=status,  # type: ignore[arg-type]
        residual=residual,
    )


def _correspondences(
    pair: RegistrationPair, matches: list[Correspondence]
) -> CorrespondenceSet:
    return CorrespondenceSet(pair_id=pair.pair_id, matcher_id="unspecified", matches=matches)


def _result(
    pair: RegistrationPair,
    *,
    matches: list[Correspondence] | None = None,
    control_points: list[ControlPoint] | None = None,
    inliers: list[Correspondence] | None = None,
    transformation: TransformationModel | None = None,
    quality_flags: list[str] | None = None,
) -> RegistrationResult:
    return RegistrationResult(
        pair_id=pair.pair_id,
        correspondences=_correspondences(pair, list(matches or [])),
        inliers=list(inliers) if inliers is not None else [],
        control_points=list(control_points or []),
        transformation=transformation,
        quality_flags=list(quality_flags or []),
    )


def test_evaluate_is_the_frozen_pipeline_callable() -> None:
    assert pipeline_evaluate is evaluate


def test_empty_correspondence_set(registration_pair: RegistrationPair) -> None:
    result = RegistrationResult(
        pair_id=registration_pair.pair_id,
        correspondences=CorrespondenceSet(
            pair_id=registration_pair.pair_id, matcher_id="unspecified"
        ),
    )
    evaluated = evaluate(result, registration_pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_count == 0
    assert evaluated.metrics.inlier_ratio is None
    assert evaluated.metrics.rmse is None
    assert evaluated.metrics.spatial_coverage is None
    assert evaluated.metrics.control_point_count == 0


def test_missing_correspondence_set_does_not_use_zero_for_unavailable(
    registration_pair: RegistrationPair,
) -> None:
    result = RegistrationResult(pair_id=registration_pair.pair_id)
    evaluated = evaluate(result, registration_pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_count is None
    assert evaluated.metrics.inlier_ratio is None
    assert evaluated.metrics.rmse is None
    assert evaluated.metrics.control_point_count == 0
    assert evaluated.metrics.spatial_coverage is None


def test_zero_error_correspondences() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=0.0),
        _match((1.0, 1.0), (1.0, 1.0), status="inlier", residual=0.0),
        _match((2.0, 2.0), (2.0, 2.0), status="inlier", residual=0.0),
    ]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.rmse == 0.0
    assert evaluated.metrics.inlier_count == 3
    assert evaluated.metrics.inlier_ratio == 1.0


def test_known_nonzero_residuals() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=3.0),
        _match((1.0, 0.0), (1.0, 0.0), status="inlier", residual=4.0),
    ]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    # sqrt((9 + 16) / 2) = sqrt(12.5)
    assert evaluated.metrics.rmse == pytest.approx(math.sqrt(12.5))


def test_rmse_uses_only_inlier_stored_residuals() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=0.0),
        _match((1.0, 0.0), (1.0, 0.0), status="rejected", residual=1000.0),
        _match((2.0, 0.0), (2.0, 0.0), status="raw", residual=50.0),
        _match((3.0, 0.0), (3.0, 0.0), status="filtered", residual=25.0),
    ]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.rmse == 0.0
    assert evaluated.metrics.inlier_count == 1


def test_rmse_is_not_taken_from_control_points() -> None:
    pair = _pair()
    inlier = _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=0.0)
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0), residual=99.0),
        ControlPoint(source_xy=(5.0, 5.0), reference_xy=(5.0, 5.0), residual=99.0),
    ]
    evaluated = evaluate(_result(pair, matches=[inlier], control_points=points), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.rmse == 0.0
    assert evaluated.metrics.control_point_count == 2


def test_known_inlier_count() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=1.0),
        _match((1.0, 0.0), (1.0, 0.0), status="inlier", residual=1.0),
        _match((2.0, 0.0), (2.0, 0.0), status="rejected", residual=8.0),
        _match((3.0, 0.0), (3.0, 0.0), status="filtered"),
        _match((4.0, 0.0), (4.0, 0.0), status="raw"),
    ]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_count == 2
    assert evaluated.metrics.inlier_count <= len(matches)


def test_inlier_count_uses_matches_not_snapshot() -> None:
    pair = _pair()
    inlier = _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=1.0)
    rejected = _match((1.0, 0.0), (1.0, 0.0), status="rejected", residual=9.0)
    extra_snapshot = _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=1.0)
    result = _result(
        pair,
        matches=[inlier, rejected],
        inliers=[inlier, extra_snapshot],
    )
    evaluated = evaluate(result, pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_count == 1
    assert len(result.inliers) == 2


def test_known_inlier_ratio() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=0.5),
        _match((1.0, 0.0), (1.0, 0.0), status="inlier", residual=0.5),
        _match((2.0, 0.0), (2.0, 0.0), status="rejected", residual=4.0),
        _match((3.0, 0.0), (3.0, 0.0), status="rejected", residual=5.0),
    ]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_ratio == 0.5


def test_zero_denominator_inlier_ratio_is_unavailable() -> None:
    pair = _pair()
    evaluated = evaluate(_result(pair, matches=[]), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_ratio is None
    assert inlier_ratio_from_matches(_correspondences(pair, [])) is None
    assert inlier_ratio_from_matches(None) is None


def test_all_rejected_ratio_is_zero_not_unavailable() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="rejected", residual=4.0),
        _match((1.0, 0.0), (1.0, 0.0), status="rejected", residual=5.0),
    ]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_count == 0
    assert evaluated.metrics.inlier_ratio == 0.0
    assert evaluated.metrics.rmse is None


def test_known_control_point_count() -> None:
    pair = _pair()
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(1.0, 1.0)),
        ControlPoint(source_xy=(2.0, 3.0), reference_xy=(4.0, 5.0)),
        ControlPoint(source_xy=(6.0, 7.0), reference_xy=(8.0, 9.0)),
    ]
    evaluated = evaluate(_result(pair, control_points=points), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.control_point_count == 3


def test_control_point_count_is_not_correspondence_count() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=0.0),
        _match((1.0, 0.0), (1.0, 0.0), status="inlier", residual=0.0),
        _match((2.0, 0.0), (2.0, 0.0), status="inlier", residual=0.0),
    ]
    points = [ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0))]
    evaluated = evaluate(_result(pair, matches=matches, control_points=points), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_count == 3
    assert evaluated.metrics.control_point_count == 1


def test_known_spatial_coverage() -> None:
    pair = _pair(source_wh=(100, 80), reference_wh=(100, 80))
    points = [
        ControlPoint(source_xy=(10.0, 10.0), reference_xy=(10.0, 10.0)),
        ControlPoint(source_xy=(30.0, 10.0), reference_xy=(30.0, 10.0)),
        ControlPoint(source_xy=(10.0, 50.0), reference_xy=(10.0, 50.0)),
        ControlPoint(source_xy=(30.0, 50.0), reference_xy=(30.0, 50.0)),
    ]
    evaluated = evaluate(_result(pair, control_points=points), pair)
    assert evaluated.metrics is not None
    # source and reference AABB both 20 * 40 = 800; image area 100 * 80 = 8000
    assert evaluated.metrics.spatial_coverage == pytest.approx(800.0 / 8000.0)


def test_coverage_is_none_without_dimensions() -> None:
    pair = _pair()
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0)),
        ControlPoint(source_xy=(10.0, 10.0), reference_xy=(10.0, 10.0)),
    ]
    evaluated = evaluate(_result(pair, control_points=points), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.spatial_coverage is None
    assert evaluated.metrics.control_point_count == 2


def test_coverage_is_none_when_only_one_image_has_dimensions() -> None:
    pair = _pair(source_wh=(100, 100), reference_wh=None)
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0)),
        ControlPoint(source_xy=(10.0, 10.0), reference_xy=(10.0, 10.0)),
    ]
    evaluated = evaluate(_result(pair, control_points=points), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.spatial_coverage is None


def test_coverage_zero_for_coincident_points() -> None:
    pair = _pair(source_wh=(50, 50), reference_wh=(50, 50))
    points = [
        ControlPoint(source_xy=(5.0, 5.0), reference_xy=(7.0, 7.0)),
        ControlPoint(source_xy=(5.0, 5.0), reference_xy=(7.0, 7.0)),
    ]
    evaluated = evaluate(_result(pair, control_points=points), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.spatial_coverage == 0.0


def test_coverage_none_when_bbox_exceeds_dimension_product() -> None:
    pair = _pair(source_wh=(10, 10), reference_wh=(10, 10))
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0)),
        ControlPoint(source_xy=(20.0, 20.0), reference_xy=(1.0, 1.0)),
    ]
    evaluated = evaluate(_result(pair, control_points=points), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.spatial_coverage is None


def test_coverage_none_on_pair_id_mismatch() -> None:
    pair = _pair(pair_id="pair-a", source_wh=(100, 100), reference_wh=(100, 100))
    other = _pair(pair_id="pair-b", source_wh=(100, 100), reference_wh=(100, 100))
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0)),
        ControlPoint(source_xy=(10.0, 10.0), reference_xy=(10.0, 10.0)),
    ]
    result = RegistrationResult(
        pair_id=pair.pair_id,
        control_points=points,
        correspondences=CorrespondenceSet(pair_id=pair.pair_id, matcher_id="unspecified"),
    )
    evaluated = evaluate(result, other)
    assert evaluated.metrics is not None
    assert evaluated.metrics.spatial_coverage is None
    assert evaluated.metrics.control_point_count == 2


def test_coverage_is_not_a_point_count_or_uniformity_claim() -> None:
    pair = _pair(source_wh=(100, 100), reference_wh=(100, 100))
    clustered = [
        ControlPoint(source_xy=(1.0, 1.0), reference_xy=(1.0, 1.0)),
        ControlPoint(source_xy=(2.0, 1.0), reference_xy=(2.0, 1.0)),
        ControlPoint(source_xy=(1.0, 2.0), reference_xy=(1.0, 2.0)),
        ControlPoint(source_xy=(2.0, 2.0), reference_xy=(2.0, 2.0)),
    ]
    evaluated = evaluate(_result(pair, control_points=clustered), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.spatial_coverage == pytest.approx(1.0 / 10000.0)
    assert evaluated.metrics.spatial_coverage != evaluated.metrics.control_point_count
    assert evaluated.metrics.spatial_coverage != 1.0


def test_missing_residual_values() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=None),
        _match((1.0, 0.0), (1.0, 0.0), status="inlier", residual=None),
    ]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_count == 2
    assert evaluated.metrics.rmse is None


def test_partial_missing_residuals_use_finite_subset() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=2.0),
        _match((1.0, 0.0), (1.0, 0.0), status="inlier", residual=None),
        _match((2.0, 0.0), (2.0, 0.0), status="inlier", residual=math.nan),
        _match((3.0, 0.0), (3.0, 0.0), status="inlier", residual=math.inf),
    ]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.inlier_count == 4
    assert evaluated.metrics.rmse == pytest.approx(2.0)


def test_negative_residual_is_omitted_from_rmse() -> None:
    pair = _pair()
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=-3.0),
        _match((1.0, 0.0), (1.0, 0.0), status="inlier", residual=6.0),
    ]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.rmse == pytest.approx(6.0)
    assert evaluated.metrics.rmse >= 0.0


def test_metric_bounds() -> None:
    pair = _pair(source_wh=(40, 40), reference_wh=(40, 40))
    matches = [
        _match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=1.0),
        _match((1.0, 0.0), (1.0, 0.0), status="rejected", residual=2.0),
        _match((2.0, 0.0), (2.0, 0.0), status="filtered"),
    ]
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0)),
        ControlPoint(source_xy=(10.0, 20.0), reference_xy=(10.0, 20.0)),
    ]
    evaluated = evaluate(_result(pair, matches=matches, control_points=points), pair)
    metrics = evaluated.metrics
    assert metrics is not None
    assert metrics.inlier_count is not None and 0 <= metrics.inlier_count <= len(matches)
    assert metrics.inlier_ratio is not None and 0.0 <= metrics.inlier_ratio <= 1.0
    assert metrics.rmse is not None and metrics.rmse >= 0.0
    assert metrics.spatial_coverage is not None and 0.0 <= metrics.spatial_coverage <= 1.0
    assert metrics.control_point_count >= 0


def test_deterministic_evaluation() -> None:
    pair = _pair(source_wh=(80, 60), reference_wh=(80, 60))
    matches = [
        _match((0.0, 0.0), (1.0, 1.0), status="inlier", residual=1.25),
        _match((4.0, 2.0), (5.0, 3.0), status="inlier", residual=0.75),
        _match((8.0, 4.0), (9.0, 5.0), status="rejected", residual=9.0),
    ]
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(1.0, 1.0), residual=1.25),
        ControlPoint(source_xy=(4.0, 2.0), reference_xy=(5.0, 3.0), residual=0.75),
    ]
    result = _result(pair, matches=matches, control_points=points, inliers=matches[:2])
    first = evaluate(result, pair)
    second = evaluate(result, pair)
    assert first.metrics == second.metrics
    assert first.metrics is not None
    third = evaluate(result, pair)
    assert third.metrics == first.metrics


def test_input_result_is_not_mutated() -> None:
    pair = _pair()
    matches = [_match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=1.0)]
    result = _result(pair, matches=matches)
    assert result.metrics is None
    evaluated = evaluate(result, pair)
    assert result.metrics is None
    assert evaluated.metrics is not None
    assert evaluated.correspondences is result.correspondences


def test_preserves_non_metric_fields() -> None:
    pair = _pair()
    matches = [_match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=0.0)]
    transformation = TransformationModel(
        model_name="projective_2d_baseline",
        parameters={"role": "software_baseline"},
    )
    result = _result(
        pair,
        matches=matches,
        transformation=transformation,
        quality_flags=["source_raster_unavailable"],
    )
    evaluated = evaluate(result, pair)
    assert evaluated.transformation == transformation
    assert evaluated.quality_flags == ["source_raster_unavailable"]
    assert evaluated.confidence_class is None
    assert evaluated.provenance is None
    assert evaluated.pair_id == result.pair_id


def test_does_not_treat_missing_rmse_as_success() -> None:
    pair = _pair()
    matches = [_match((0.0, 0.0), (0.0, 0.0), status="inlier", residual=None)]
    evaluated = evaluate(_result(pair, matches=matches), pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.rmse is None
    assert evaluated.confidence_class is None


def test_helper_unavailable_paths() -> None:
    assert count_inliers(None) is None
    assert rmse_from_inlier_residuals(None) is None
    assert count_inliers(CorrespondenceSet(pair_id="p", matcher_id="m")) == 0
