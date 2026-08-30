"""Synthetic correspondence tests for geometric verification.

These tests use declared synthetic generating models. They are not lunar
accuracy results and are not SIH evaluator evidence (D-011, D-012).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.models import Correspondence, CorrespondenceSet, RegistrationPair
from src.verification import VerificationSettings, verify_correspondences

pytestmark = pytest.mark.scientific

# TEST GENERATING MODEL ONLY — not a lunar transformation (D-010).
# Affine: x' = 1.2 x + 0.1 y + 5 ;  y' = -0.05 x + 1.1 y + 8
SYNTHETIC_AFFINE_GENERATING_MODEL = np.array(
    [[1.2, 0.1, 5.0], [-0.05, 1.1, 8.0], [0.0, 0.0, 1.0]],
    dtype=float,
)

# TEST GENERATING MODEL ONLY — not a lunar transformation (D-010).
SYNTHETIC_PROJECTIVE_GENERATING_MODEL = np.array(
    [[1.05, 0.02, 10.0], [-0.01, 1.08, -4.0], [0.0002, 0.0001, 1.0]],
    dtype=float,
)


def _map_xy(xy: tuple[float, float], matrix: np.ndarray) -> tuple[float, float]:
    mapped = matrix @ np.array([xy[0], xy[1], 1.0], dtype=float)
    return (float(mapped[0] / mapped[2]), float(mapped[1] / mapped[2]))


def _settings(**overrides: object) -> VerificationSettings:
    base = dict(
        model_id="affine_2d_baseline",
        estimator_id="ransac_style_baseline",
        residual_limit=1.0,
        max_trials=300,
        rng_seed=0,
        confidence_min=None,
    )
    base.update(overrides)
    return VerificationSettings(**base)  # type: ignore[arg-type]


def _correspondences(
    pair: RegistrationPair, matches: list[Correspondence], matcher_id: str = "synthetic-generator"
) -> CorrespondenceSet:
    return CorrespondenceSet(pair_id=pair.pair_id, matcher_id=matcher_id, matches=matches)


def _grid_inliers(matrix: np.ndarray, n: int = 12) -> list[Correspondence]:
    matches: list[Correspondence] = []
    count = 0
    for x in range(0, 50, 10):
        for y in range(0, 40, 10):
            src = (float(x), float(y))
            matches.append(Correspondence(source_xy=src, reference_xy=_map_xy(src, matrix)))
            count += 1
            if count >= n:
                return matches
    return matches


def test_clear_inliers_and_outliers(registration_pair: RegistrationPair) -> None:
    inliers = _grid_inliers(SYNTHETIC_AFFINE_GENERATING_MODEL, n=10)
    outliers = [
        Correspondence(source_xy=(3.0, 4.0), reference_xy=(80.0, -60.0)),
        Correspondence(source_xy=(15.0, 8.0), reference_xy=(-40.0, 90.0)),
        Correspondence(source_xy=(22.0, 18.0), reference_xy=(5.0, -70.0)),
    ]
    result = verify_correspondences(
        _correspondences(registration_pair, inliers + outliers),
        registration_pair,
        _settings(),
    )
    statuses = [item.status for item in result.matches]
    assert statuses[: len(inliers)] == ["inlier"] * len(inliers)
    assert statuses[len(inliers) :] == ["rejected"] * len(outliers)
    for item in result.matches[: len(inliers)]:
        assert item.residual is not None
        assert item.residual <= 1.0
    for item in result.matches[len(inliers) :]:
        assert item.residual is not None
        assert item.residual > 1.0


def test_all_valid_inlier_correspondences(registration_pair: RegistrationPair) -> None:
    matches = _grid_inliers(SYNTHETIC_AFFINE_GENERATING_MODEL, n=12)
    result = verify_correspondences(
        _correspondences(registration_pair, matches), registration_pair, _settings()
    )
    assert all(item.status == "inlier" for item in result.matches)
    assert all(item.residual is not None and item.residual <= 1.0 for item in result.matches)


def test_insufficient_correspondences(registration_pair: RegistrationPair) -> None:
    matches = _grid_inliers(SYNTHETIC_AFFINE_GENERATING_MODEL, n=2)
    result = verify_correspondences(
        _correspondences(registration_pair, matches), registration_pair, _settings()
    )
    assert [item.status for item in result.matches] == ["filtered", "filtered"]
    assert all(item.residual is None for item in result.matches)


def test_duplicate_coordinates(registration_pair: RegistrationPair) -> None:
    inliers = _grid_inliers(SYNTHETIC_AFFINE_GENERATING_MODEL, n=8)
    duplicate = Correspondence(
        source_xy=inliers[0].source_xy,
        reference_xy=inliers[0].reference_xy,
        confidence=0.5,
    )
    result = verify_correspondences(
        _correspondences(registration_pair, [*inliers, duplicate]),
        registration_pair,
        _settings(),
    )
    assert result.matches[-1].status == "rejected"
    assert result.matches[-1].residual is None
    assert result.matches[-1].source_xy == inliers[0].source_xy
    assert result.matches[0].status == "inlier"


def test_non_finite_coordinates(registration_pair: RegistrationPair) -> None:
    inliers = _grid_inliers(SYNTHETIC_AFFINE_GENERATING_MODEL, n=8)
    invalid = [
        Correspondence(source_xy=(math.inf, 0.0), reference_xy=(1.0, 1.0)),
        Correspondence(source_xy=(0.0, 0.0), reference_xy=(math.nan, 1.0)),
    ]
    result = verify_correspondences(
        _correspondences(registration_pair, inliers + invalid),
        registration_pair,
        _settings(),
    )
    assert result.matches[-2].status == "rejected"
    assert result.matches[-1].status == "rejected"
    assert result.matches[-2].residual is None
    assert result.matches[-1].residual is None
    assert any(item.status == "inlier" for item in result.matches[:-2])


def test_degenerate_geometry(registration_pair: RegistrationPair) -> None:
    # All source points on a line (and mapped by the affine generating model).
    # Algebraically degenerate for a 2D affine/projective sample.
    matches = [
        Correspondence(
            source_xy=(float(i), 0.0),
            reference_xy=_map_xy((float(i), 0.0), SYNTHETIC_AFFINE_GENERATING_MODEL),
        )
        for i in range(8)
    ]
    result = verify_correspondences(
        _correspondences(registration_pair, matches), registration_pair, _settings()
    )
    assert all(item.status == "filtered" for item in result.matches)
    assert all(item.residual is None for item in result.matches)
    assert not any(item.status == "inlier" for item in result.matches)


def test_confidence_none_with_outliers(registration_pair: RegistrationPair) -> None:
    inliers = [
        Correspondence(source_xy=item.source_xy, reference_xy=item.reference_xy, confidence=None)
        for item in _grid_inliers(SYNTHETIC_AFFINE_GENERATING_MODEL, n=10)
    ]
    outliers = [
        Correspondence(source_xy=(3.0, 4.0), reference_xy=(80.0, -60.0), confidence=None),
    ]
    result = verify_correspondences(
        _correspondences(registration_pair, inliers + outliers),
        registration_pair,
        _settings(),
    )
    assert [item.status for item in result.matches[:10]] == ["inlier"] * 10
    assert result.matches[-1].status == "rejected"


def test_invalid_confidence(registration_pair: RegistrationPair) -> None:
    inliers = _grid_inliers(SYNTHETIC_AFFINE_GENERATING_MODEL, n=8)
    bad = Correspondence.model_construct(
        source_xy=(1.0, 1.0),
        reference_xy=_map_xy((1.0, 1.0), SYNTHETIC_AFFINE_GENERATING_MODEL),
        confidence=-0.2,
        residual=None,
        status="raw",
    )
    result = verify_correspondences(
        _correspondences(registration_pair, [bad, *inliers]),
        registration_pair,
        _settings(),
    )
    assert result.matches[0].status == "rejected"
    assert result.matches[0].confidence == -0.2
    assert any(item.status == "inlier" for item in result.matches[1:])


def test_deterministic_behavior(registration_pair: RegistrationPair) -> None:
    inliers = _grid_inliers(SYNTHETIC_AFFINE_GENERATING_MODEL, n=10)
    outliers = [Correspondence(source_xy=(3.0, 4.0), reference_xy=(80.0, -60.0))]
    correspondences = _correspondences(registration_pair, inliers + outliers)
    settings = _settings(rng_seed=17)
    first = verify_correspondences(correspondences, registration_pair, settings)
    second = verify_correspondences(correspondences, registration_pair, settings)
    assert [item.status for item in first.matches] == [item.status for item in second.matches]
    assert [item.residual for item in first.matches] == [item.residual for item in second.matches]


def test_status_transitions_from_raw(registration_pair: RegistrationPair) -> None:
    inliers = _grid_inliers(SYNTHETIC_AFFINE_GENERATING_MODEL, n=8)
    outlier = Correspondence(source_xy=(3.0, 4.0), reference_xy=(80.0, -60.0), status="raw")
    duplicate = Correspondence(source_xy=inliers[0].source_xy, reference_xy=inliers[0].reference_xy)
    invalid = Correspondence(source_xy=(math.inf, 0.0), reference_xy=(0.0, 0.0))
    result = verify_correspondences(
        _correspondences(registration_pair, [*inliers, outlier, duplicate, invalid]),
        registration_pair,
        _settings(),
    )
    assert all(item.status == "raw" for item in inliers)  # inputs unchanged
    assert [item.status for item in result.matches[:8]] == ["inlier"] * 8
    assert result.matches[8].status == "rejected"
    assert result.matches[9].status == "rejected"
    assert result.matches[10].status == "rejected"
    assert not any(item.status == "raw" for item in result.matches)


def test_projective_generating_model_with_projective_baseline(
    registration_pair: RegistrationPair,
) -> None:
    matches = _grid_inliers(SYNTHETIC_PROJECTIVE_GENERATING_MODEL, n=12)
    outliers = [Correspondence(source_xy=(6.0, 7.0), reference_xy=(200.0, -150.0))]
    result = verify_correspondences(
        _correspondences(registration_pair, matches + outliers),
        registration_pair,
        _settings(model_id="projective_2d_baseline"),
    )
    assert all(item.status == "inlier" for item in result.matches[:12])
    assert result.matches[-1].status == "rejected"
