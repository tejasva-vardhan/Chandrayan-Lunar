"""Matcher portfolio contract tests.

The comparison in EXP-001 is only controlled if every adapter shares the
non-matcher parts of the protocol. These tests pin that down.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.matching import match
from src.matching.portfolio import (
    PORTFOLIO_MATCHER_IDS,
    default_settings,
    matcher_parameters,
    run_matcher,
)
from src.matching.settings import (
    SHARED_MIN_MATCHES,
    SHARED_RATIO_THRESHOLD,
    OrbSettings,
    RiftSettings,
    SiftSettings,
)
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult


def _image(seed: int = 3, side: int = 320) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grid_y, grid_x = np.mgrid[0:side, 0:side].astype(np.float32)
    image = 0.4 + 0.04 * rng.standard_normal((side, side)).astype(np.float32)
    for _ in range(35):
        centre_x = rng.uniform(0, side)
        centre_y = rng.uniform(0, side)
        radius = rng.uniform(5.0, 20.0)
        distance = np.sqrt((grid_x - centre_x) ** 2 + (grid_y - centre_y) ** 2)
        image += 0.3 * np.exp(-(((distance - radius) / 2.5) ** 2))
    image -= image.min()
    image /= max(float(image.max()), 1e-6)
    return image.astype(np.float32)


def _pair() -> RegistrationPair:
    return RegistrationPair(
        pair_id="portfolio-pair",
        source=LunarProduct(product_id="src", instrument="OHRC", mission="Chandrayaan-2"),
        reference=LunarProduct(product_id="ref", instrument="LRO_NAC", mission="LRO"),
    )


def _representation(
    source: np.ndarray,
    reference: np.ndarray,
    *,
    source_stride: float = 1.0,
    reference_stride: float = 1.0,
) -> RepresentationResult:
    return RepresentationResult(
        array=source,
        representation_id="intensity",
        metadata={
            "reference_array": reference,
            "source_matching_view": {"x_scale": source_stride, "y_scale": source_stride},
            "reference_matching_view": {
                "x_scale": reference_stride,
                "y_scale": reference_stride,
            },
        },
    )


def test_portfolio_exposes_the_three_compared_matchers() -> None:
    assert PORTFOLIO_MATCHER_IDS == ("sift", "rift", "orb")


def test_unknown_matcher_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="No adapter registered"):
        run_matcher("loftr", _pair(), None)
    with pytest.raises(ValueError, match="No adapter registered"):
        default_settings("loftr")


def test_every_adapter_shares_the_protocol_parameters() -> None:
    """Ratio threshold and min_matches are protocol, not matcher, parameters."""

    for settings in (SiftSettings(), RiftSettings(), OrbSettings()):
        assert settings.ratio_threshold == SHARED_RATIO_THRESHOLD
        assert settings.min_matches == SHARED_MIN_MATCHES


def test_sift_through_portfolio_equals_the_frozen_match_surface() -> None:
    """The baseline arm must be the EXP-000 code path, not a lookalike."""

    source = _image()
    reference = np.roll(source, 9, axis=1)
    pair = _pair()
    representation = _representation(source, reference)

    frozen = match(pair, representation)
    portfolio = run_matcher("sift", pair, representation)

    assert frozen.matcher_id == portfolio.matcher_id == "sift"
    assert len(frozen.matches) == len(portfolio.matches)
    for left, right in zip(frozen.matches, portfolio.matches, strict=True):
        assert left.source_xy == right.source_xy
        assert left.reference_xy == right.reference_xy
        assert left.confidence == right.confidence


@pytest.mark.parametrize("matcher_id", PORTFOLIO_MATCHER_IDS)
def test_adapters_label_themselves_and_the_representation(matcher_id: str) -> None:
    source = _image()
    reference = np.roll(source, 7, axis=0)
    pair = _pair()
    representation = _representation(source, reference)

    result = run_matcher(matcher_id, pair, representation)

    assert result.matcher_id == matcher_id
    assert result.pair_id == "portfolio-pair"
    assert result.representation_id == "intensity"
    assert all(item.status == "raw" for item in result.matches)


@pytest.mark.parametrize("matcher_id", PORTFOLIO_MATCHER_IDS)
def test_adapters_apply_the_matching_view_coordinate_scale(matcher_id: str) -> None:
    """Every adapter must return original-image pixels, not matching-view pixels."""

    source = _image()
    reference = np.roll(source, 7, axis=0)
    pair = _pair()

    unscaled = run_matcher(matcher_id, pair, _representation(source, reference))
    scaled = run_matcher(
        matcher_id,
        pair,
        _representation(source, reference, source_stride=4.0, reference_stride=8.0),
    )

    assert unscaled.matches, f"{matcher_id} produced no matches on the synthetic pair"
    assert len(unscaled.matches) == len(scaled.matches)
    for plain, mapped in zip(unscaled.matches, scaled.matches, strict=True):
        assert mapped.source_xy[0] == pytest.approx(plain.source_xy[0] * 4.0)
        assert mapped.source_xy[1] == pytest.approx(plain.source_xy[1] * 4.0)
        assert mapped.reference_xy[0] == pytest.approx(plain.reference_xy[0] * 8.0)
        assert mapped.reference_xy[1] == pytest.approx(plain.reference_xy[1] * 8.0)


@pytest.mark.parametrize("matcher_id", PORTFOLIO_MATCHER_IDS)
def test_adapters_return_empty_set_without_image_data(matcher_id: str) -> None:
    """Missing rasters are a data condition, not a crash."""

    pair = _pair()
    result = run_matcher(matcher_id, pair, None)

    assert result.matches == []
    assert result.matcher_id == matcher_id


@pytest.mark.parametrize("matcher_id", PORTFOLIO_MATCHER_IDS)
def test_adapters_are_deterministic(matcher_id: str) -> None:
    source = _image()
    reference = np.roll(source, 11, axis=1)
    pair = _pair()
    representation = _representation(source, reference)

    first = run_matcher(matcher_id, pair, representation)
    second = run_matcher(matcher_id, pair, representation)

    assert [item.model_dump() for item in first.matches] == [
        item.model_dump() for item in second.matches
    ]


@pytest.mark.parametrize("matcher_id", PORTFOLIO_MATCHER_IDS)
def test_matcher_parameters_are_json_ready(matcher_id: str) -> None:
    import json

    payload = matcher_parameters(matcher_id)

    assert isinstance(payload, dict)
    assert payload["ratio_threshold"] == SHARED_RATIO_THRESHOLD
    json.dumps(payload)


@pytest.mark.parametrize("matcher_id", PORTFOLIO_MATCHER_IDS)
def test_adapters_respect_the_validity_mask(matcher_id: str) -> None:
    """Masked-out regions must not produce correspondences."""

    source = _image()
    reference = np.roll(source, 5, axis=1)
    mask = np.zeros(source.shape, dtype=bool)
    mask[:160, :] = True

    representation = RepresentationResult(
        array=source,
        representation_id="intensity",
        metadata={
            "reference_array": reference,
            "source_valid_mask": mask,
            "reference_valid_mask": np.ones(reference.shape, dtype=bool),
        },
    )
    result = run_matcher(matcher_id, _pair(), representation)

    assert result.matches, f"{matcher_id} produced no matches inside the valid region"
    assert all(item.source_xy[1] < 160 for item in result.matches)


def test_rift_rejects_an_indivisible_descriptor_grid() -> None:
    with pytest.raises(ValueError, match="divisible"):
        RiftSettings(patch_size=100, descriptor_grid=6)


def test_orb_rejects_a_non_positive_feature_cap() -> None:
    with pytest.raises(ValueError, match="nfeatures"):
        OrbSettings(nfeatures=0)
