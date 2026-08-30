"""Unit tests for spatially distributed control-point selection.

These tests check software selection behaviour on synthetic correspondence
clouds. They are not lunar accuracy results and not SIH evaluator evidence.
"""

from __future__ import annotations

import math

import pytest

from src.control_points import (
    ControlPointSettings,
    select_control_points,
    select_control_points_with_settings,
    unvalidated_software_defaults,
)
from src.models import Correspondence, CorrespondenceSet, RegistrationPair
from src.pipeline.operations import select_control_points as pipeline_select


def _settings(**overrides: object) -> ControlPointSettings:
    base: dict[str, object] = dict(
        grid_bins=8,
        max_per_source_cell=1,
        max_per_reference_cell=1,
        max_points=None,
    )
    base.update(overrides)
    return ControlPointSettings(**base)  # type: ignore[arg-type]


def _set(
    pair: RegistrationPair,
    matches: list[Correspondence],
    matcher_id: str = "unspecified",
) -> CorrespondenceSet:
    return CorrespondenceSet(pair_id=pair.pair_id, matcher_id=matcher_id, matches=matches)


def _inlier(
    source_xy: tuple[float, float],
    reference_xy: tuple[float, float],
    *,
    confidence: float | None = 0.5,
    residual: float | None = 0.1,
) -> Correspondence:
    return Correspondence(
        source_xy=source_xy,
        reference_xy=reference_xy,
        confidence=confidence,
        residual=residual,
        status="inlier",
    )


def test_select_control_points_is_the_frozen_pipeline_callable() -> None:
    assert pipeline_select is select_control_points


def test_empty_input(registration_pair: RegistrationPair) -> None:
    result = select_control_points(_set(registration_pair, []), registration_pair)
    assert result == []


def test_no_verified_correspondences(registration_pair: RegistrationPair) -> None:
    matches = [
        Correspondence(source_xy=(0.0, 0.0), reference_xy=(1.0, 1.0), status="raw"),
        Correspondence(source_xy=(10.0, 0.0), reference_xy=(11.0, 1.0), status="filtered"),
        Correspondence(
            source_xy=(20.0, 0.0),
            reference_xy=(21.0, 1.0),
            confidence=0.99,
            status="rejected",
        ),
    ]
    result = select_control_points_with_settings(
        _set(registration_pair, matches), registration_pair, _settings()
    )
    assert result == []


def test_spatially_uniform_correspondences(registration_pair: RegistrationPair) -> None:
    matches = [
        _inlier((float(x), float(y)), (float(x) + 1.0, float(y) + 1.0))
        for x in (0, 50, 100)
        for y in (0, 50, 100)
    ]
    result = select_control_points_with_settings(
        _set(registration_pair, matches), registration_pair, _settings()
    )
    assert len(result) == 9
    selected = {(item.source_xy, item.reference_xy) for item in result}
    expected = {(item.source_xy, item.reference_xy) for item in matches}
    assert selected == expected


def test_strongly_clustered_correspondences(registration_pair: RegistrationPair) -> None:
    cluster = [
        _inlier((10.0, 10.0), (float(i), 10.0), confidence=0.99, residual=0.05)
        for i in range(20)
    ]
    result = select_control_points_with_settings(
        _set(registration_pair, cluster), registration_pair, _settings()
    )
    assert len(result) == 1
    assert result[0].source_xy == (10.0, 10.0)


def test_uneven_spatial_density(registration_pair: RegistrationPair) -> None:
    dense = [
        _inlier((5.0, 5.0), (float(i), 5.0), confidence=0.9)
        for i in range(15)
    ]
    sparse = [
        _inlier((0.0, 100.0), (0.0, 100.0), confidence=0.4),
        _inlier((100.0, 0.0), (100.0, 0.0), confidence=0.4),
    ]
    result = select_control_points_with_settings(
        _set(registration_pair, dense + sparse), registration_pair, _settings()
    )
    sources = [item.source_xy for item in result]
    assert sources.count((5.0, 5.0)) == 1
    assert (0.0, 100.0) in sources
    assert (100.0, 0.0) in sources
    assert len(result) == 3


def test_fewer_points_than_requested(registration_pair: RegistrationPair) -> None:
    matches = [
        _inlier((0.0, 0.0), (1.0, 0.0)),
        _inlier((80.0, 0.0), (81.0, 0.0)),
        _inlier((0.0, 80.0), (1.0, 81.0)),
    ]
    result = select_control_points_with_settings(
        _set(registration_pair, matches),
        registration_pair,
        _settings(max_points=20),
    )
    assert len(result) == 3


def test_duplicate_points(registration_pair: RegistrationPair) -> None:
    first = _inlier((0.0, 0.0), (1.0, 1.0), residual=0.2)
    duplicate = _inlier((0.0, 0.0), (1.0, 1.0), residual=0.01)
    other = _inlier((80.0, 80.0), (81.0, 81.0), residual=0.2)
    result = select_control_points_with_settings(
        _set(registration_pair, [first, duplicate, other]),
        registration_pair,
        _settings(),
    )
    coords = [(item.source_xy, item.reference_xy) for item in result]
    assert coords.count(((0.0, 0.0), (1.0, 1.0))) == 1
    assert ((80.0, 80.0), (81.0, 81.0)) in coords


def test_missing_confidence(registration_pair: RegistrationPair) -> None:
    matches = [
        _inlier((0.0, 0.0), (1.0, 0.0), confidence=None),
        _inlier((80.0, 80.0), (81.0, 81.0), confidence=None),
    ]
    result = select_control_points_with_settings(
        _set(registration_pair, matches), registration_pair, _settings()
    )
    assert len(result) == 2


def test_missing_residual(registration_pair: RegistrationPair) -> None:
    matches = [
        _inlier((0.0, 0.0), (1.0, 0.0), residual=None),
        _inlier((80.0, 80.0), (81.0, 81.0), residual=None),
    ]
    result = select_control_points_with_settings(
        _set(registration_pair, matches), registration_pair, _settings()
    )
    assert len(result) == 2
    assert all(item.residual is None for item in result)


def test_deterministic_repeated_selection(registration_pair: RegistrationPair) -> None:
    matches = [
        _inlier((float(x), float(y)), (float(x) + 2.0, float(y)))
        for x in (0, 40, 80)
        for y in (0, 40, 80)
    ]
    correspondences = _set(registration_pair, matches)
    settings = _settings()
    first = select_control_points_with_settings(correspondences, registration_pair, settings)
    second = select_control_points_with_settings(correspondences, registration_pair, settings)
    assert [(p.source_xy, p.reference_xy) for p in first] == [
        (p.source_xy, p.reference_xy) for p in second
    ]


def test_source_reference_coordinate_preservation(registration_pair: RegistrationPair) -> None:
    item = _inlier((12.5, 33.25), (40.0, 8.75), residual=0.4)
    result = select_control_points_with_settings(
        _set(registration_pair, [item]), registration_pair, _settings()
    )
    assert len(result) == 1
    assert result[0].source_xy == (12.5, 33.25)
    assert result[0].reference_xy == (40.0, 8.75)
    assert result[0].residual == 0.4


def test_control_point_uncertainty_remains_none(registration_pair: RegistrationPair) -> None:
    result = select_control_points_with_settings(
        _set(registration_pair, [_inlier((0.0, 0.0), (1.0, 1.0))]),
        registration_pair,
        _settings(),
    )
    assert result[0].uncertainty is None


def test_high_confidence_cluster_does_not_dominate(
    registration_pair: RegistrationPair,
) -> None:
    cluster = [
        _inlier((50.0, 50.0), (40.0 + float(i), 50.0), confidence=0.99, residual=0.02)
        for i in range(25)
    ]
    spread = [
        _inlier((0.0, 0.0), (0.0, 0.0), confidence=0.2, residual=0.4),
        _inlier((100.0, 0.0), (100.0, 0.0), confidence=0.2, residual=0.4),
        _inlier((0.0, 100.0), (0.0, 100.0), confidence=0.2, residual=0.4),
        _inlier((100.0, 100.0), (100.0, 100.0), confidence=0.2, residual=0.4),
    ]
    result = select_control_points_with_settings(
        _set(registration_pair, cluster + spread), registration_pair, _settings()
    )
    cluster_count = sum(1 for item in result if item.source_xy == (50.0, 50.0))
    spread_sources = {item.source_xy for item in result} - {(50.0, 50.0)}
    assert cluster_count == 1
    assert spread_sources == {(0.0, 0.0), (100.0, 0.0), (0.0, 100.0), (100.0, 100.0)}
    assert len(result) == 5


def test_non_finite_inlier_is_skipped(registration_pair: RegistrationPair) -> None:
    bad = Correspondence.model_construct(
        source_xy=(math.inf, 0.0),
        reference_xy=(1.0, 1.0),
        confidence=0.9,
        residual=0.1,
        status="inlier",
    )
    good = _inlier((8.0, 8.0), (9.0, 9.0))
    result = select_control_points_with_settings(
        _set(registration_pair, [bad, good]), registration_pair, _settings()
    )
    assert len(result) == 1
    assert result[0].source_xy == (8.0, 8.0)


def test_two_argument_api_uses_engineering_defaults(
    registration_pair: RegistrationPair,
) -> None:
    defaults = unvalidated_software_defaults()
    assert defaults.grid_bins == 8
    assert defaults.max_per_source_cell == 1
    assert defaults.max_per_reference_cell == 1
    assert defaults.max_points is None
    matches = [
        _inlier((0.0, 0.0), (1.0, 0.0)),
        _inlier((80.0, 80.0), (81.0, 81.0)),
    ]
    result = select_control_points(_set(registration_pair, matches), registration_pair)
    assert len(result) == 2
    assert all(item.uncertainty is None for item in result)


def test_invalid_grid_bins_fails_clearly() -> None:
    with pytest.raises(ValueError, match="grid_bins"):
        ControlPointSettings(
            grid_bins=0,
            max_per_source_cell=1,
            max_per_reference_cell=1,
        )


def test_matcher_id_is_not_interpreted(registration_pair: RegistrationPair) -> None:
    matches = [_inlier((0.0, 0.0), (1.0, 1.0))]
    for matcher_id in ("sift", "rift2", "LightGlue", "custom"):
        result = select_control_points_with_settings(
            _set(registration_pair, matches, matcher_id=matcher_id),
            registration_pair,
            _settings(),
        )
        assert len(result) == 1
