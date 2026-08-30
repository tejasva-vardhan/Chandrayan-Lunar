"""Unit tests for geometric verification. Not lunar accuracy evidence."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.models import Correspondence, CorrespondenceSet, RegistrationPair
from src.pipeline.operations import verify_matches as pipeline_verify_matches
from src.verification import (
    VerificationSettings,
    unvalidated_software_defaults,
    verify_correspondences,
    verify_matches,
)


def _settings(**overrides: object) -> VerificationSettings:
    base = dict(
        model_id="affine_2d_baseline",
        estimator_id="ransac_style_baseline",
        residual_limit=1.0,
        max_trials=200,
        rng_seed=0,
        confidence_min=None,
    )
    base.update(overrides)
    return VerificationSettings(**base)  # type: ignore[arg-type]


def _translated_grid() -> list[Correspondence]:
    """Synthetic generating model (TEST ONLY): x' = x + 2, y' = y + 1."""

    return [
        Correspondence(
            source_xy=(float(x), float(y)),
            reference_xy=(float(x) + 2.0, float(y) + 1.0),
        )
        for x, y in ((0, 0), (10, 0), (0, 10), (10, 10), (4, 6), (7, 2))
    ]


def _set(
    pair: RegistrationPair, matches: list[Correspondence], matcher_id: str = "unspecified"
) -> CorrespondenceSet:
    return CorrespondenceSet(pair_id=pair.pair_id, matcher_id=matcher_id, matches=matches)


def test_verify_matches_is_the_frozen_pipeline_callable() -> None:
    assert pipeline_verify_matches is verify_matches


def test_empty_correspondence_set_returns_no_inliers(registration_pair: RegistrationPair) -> None:
    empty = _set(registration_pair, [])
    result = verify_matches(empty, registration_pair)
    assert result.matches == []
    assert result.pair_id == empty.pair_id
    assert result.matcher_id == empty.matcher_id


def test_input_correspondence_set_is_not_mutated(registration_pair: RegistrationPair) -> None:
    original = Correspondence(source_xy=(0.0, 0.0), reference_xy=(1.0, 1.0), status="raw")
    correspondences = _set(registration_pair, [original])
    verify_correspondences(correspondences, registration_pair, _settings())
    assert correspondences.matches[0].status == "raw"
    assert correspondences.matches[0].residual is None


def test_identity_fields_are_preserved(registration_pair: RegistrationPair) -> None:
    correspondences = CorrespondenceSet(
        pair_id=registration_pair.pair_id,
        matcher_id="adapter-label-only",
        representation_id="unspecified",
        matches=[Correspondence(source_xy=(1.0, 2.0), reference_xy=(3.0, 4.0))],
    )
    result = verify_correspondences(correspondences, registration_pair, _settings())
    assert result.pair_id == correspondences.pair_id
    assert result.matcher_id == "adapter-label-only"
    assert result.representation_id == "unspecified"
    assert result.matches[0].source_xy == (1.0, 2.0)
    assert result.matches[0].reference_xy == (3.0, 4.0)


def test_matcher_id_is_not_interpreted(registration_pair: RegistrationPair) -> None:
    for matcher_id in ("sift", "rift2", "LightGlue", "loftr-family", "pwift", "custom"):
        correspondences = _set(
            registration_pair,
            [Correspondence(source_xy=(0.0, 0.0), reference_xy=(1.0, 1.0))],
            matcher_id=matcher_id,
        )
        result = verify_correspondences(correspondences, registration_pair, _settings())
        assert result.matcher_id == matcher_id


def test_confidence_none_is_not_rejected_for_missing_score(
    registration_pair: RegistrationPair,
) -> None:
    matches = [
        Correspondence(source_xy=item.source_xy, reference_xy=item.reference_xy, confidence=None)
        for item in _translated_grid()
    ]
    result = verify_correspondences(
        _set(registration_pair, matches), registration_pair, _settings()
    )
    assert all(item.confidence is None for item in result.matches)
    assert any(item.status == "inlier" for item in result.matches)


def test_invalid_confidence_is_rejected_without_pydantic_validation(
    registration_pair: RegistrationPair,
) -> None:
    bad = Correspondence.model_construct(
        source_xy=(0.0, 0.0),
        reference_xy=(1.0, 1.0),
        confidence=2.0,
        residual=None,
        status="raw",
    )
    ok = _translated_grid()
    result = verify_correspondences(
        _set(registration_pair, [bad, *ok]), registration_pair, _settings()
    )
    assert result.matches[0].status == "rejected"
    assert result.matches[0].residual is None


def test_unknown_model_id_fails_clearly(registration_pair: RegistrationPair) -> None:
    correspondences = _set(
        registration_pair,
        [Correspondence(source_xy=(0.0, 0.0), reference_xy=(1.0, 1.0))],
    )
    with pytest.raises(ValueError, match="unknown geometric model_id"):
        verify_correspondences(
            correspondences,
            registration_pair,
            _settings(model_id="homography_as_lunar_model"),
        )


def test_unknown_estimator_id_fails_clearly(registration_pair: RegistrationPair) -> None:
    correspondences = _set(
        registration_pair,
        [Correspondence(source_xy=(0.0, 0.0), reference_xy=(1.0, 1.0))],
    )
    with pytest.raises(ValueError, match="unknown estimator_id"):
        verify_correspondences(
            correspondences,
            registration_pair,
            _settings(estimator_id="magsac_as_final"),
        )


def test_negative_residual_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="residual_limit"):
        VerificationSettings(
            model_id="affine_2d_baseline",
            estimator_id="ransac_style_baseline",
            residual_limit=-0.1,
            max_trials=10,
            rng_seed=0,
        )


def test_affine_and_projective_baselines_are_swappable(registration_pair: RegistrationPair) -> None:
    # Synthetic generating model (TEST ONLY, not a lunar model):
    #   x' = x + 3,  y' = y - 1
    matches = [
        Correspondence(
            source_xy=(float(x), float(y)),
            reference_xy=(float(x) + 3.0, float(y) - 1.0),
        )
        for x, y in ((0, 0), (10, 0), (0, 10), (10, 10), (4, 6), (7, 2))
    ]
    correspondences = _set(registration_pair, matches)
    affine = verify_correspondences(correspondences, registration_pair, _settings())
    projective = verify_correspondences(
        correspondences,
        registration_pair,
        _settings(model_id="projective_2d_baseline"),
    )
    assert all(item.status == "inlier" for item in affine.matches)
    assert all(item.status == "inlier" for item in projective.matches)


def test_two_argument_pipeline_api_uses_software_baseline(
    registration_pair: RegistrationPair,
) -> None:
    # Frozen API defaults residual_limit=3.0, max_trials=500, rng_seed=0.
    # Those are engineering/test values only — not SIH or lunar-validated.
    # Synthetic generating model (TEST ONLY): 3x3 projective map below.
    matrix = np.array(
        [[1.05, 0.02, 10.0], [-0.01, 1.08, -4.0], [0.0002, 0.0001, 1.0]],
        dtype=float,
    )
    matches: list[Correspondence] = []
    for x in range(0, 40, 8):
        for y in range(0, 40, 8):
            mapped = matrix @ np.array([float(x), float(y), 1.0])
            matches.append(
                Correspondence(
                    source_xy=(float(x), float(y)),
                    reference_xy=(float(mapped[0] / mapped[2]), float(mapped[1] / mapped[2])),
                )
            )
    result = verify_matches(_set(registration_pair, matches), registration_pair)
    defaults = unvalidated_software_defaults()
    assert defaults.model_id == "projective_2d_baseline"
    assert defaults.residual_limit == 3.0
    assert defaults.max_trials == 500
    assert defaults.rng_seed == 0
    assert any(item.status == "inlier" for item in result.matches)
    assert all(item.status != "raw" for item in result.matches)


def test_experimental_confidence_min_does_not_apply_when_confidence_is_none(
    registration_pair: RegistrationPair,
) -> None:
    matches = [
        Correspondence(source_xy=item.source_xy, reference_xy=item.reference_xy, confidence=None)
        for item in _translated_grid()
    ]
    result = verify_correspondences(
        _set(registration_pair, matches),
        registration_pair,
        _settings(confidence_min=0.9),
    )
    assert any(item.status == "inlier" for item in result.matches)


def test_residuals_are_python_floats_not_numpy_types(registration_pair: RegistrationPair) -> None:
    result = verify_correspondences(
        _set(registration_pair, _translated_grid()), registration_pair, _settings()
    )
    inliers = [item for item in result.matches if item.status == "inlier"]
    assert inliers
    for item in inliers:
        assert item.residual is not None
        assert type(item.residual) is float
        assert math.isfinite(item.residual)
