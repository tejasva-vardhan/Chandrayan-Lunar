"""Focused synthetic safety tests for the EXP-000 SIFT baseline.

These are engineering-contract checks. They make no lunar-performance or
scientific-accuracy claim.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.matching import match
from src.matching.sift_adapter import run_sift
from src.models import LunarProduct, RegistrationPair
from src.representation import RepresentationResult


def _pair() -> RegistrationPair:
    return RegistrationPair(
        pair_id="synthetic-sift-safety",
        source=LunarProduct(product_id="source", instrument="OHRC"),
        reference=LunarProduct(product_id="reference", instrument="LRO_NAC"),
    )


def _representation(
    source: np.ndarray,
    reference: np.ndarray,
    **metadata: object,
) -> RepresentationResult:
    return RepresentationResult(
        array=source,
        representation_id="intensity",
        metadata={"reference_array": reference, **metadata},
    )


def _textured_image(seed: int = 17, side: int = 320) -> np.ndarray:
    """Create deterministic, feature-rich imagery for matcher contract tests."""
    rng = np.random.default_rng(seed)
    grid_y, grid_x = np.mgrid[0:side, 0:side].astype(np.float32)
    image = 0.35 + 0.03 * rng.standard_normal((side, side)).astype(np.float32)
    for _ in range(45):
        centre_x = rng.uniform(18.0, side - 18.0)
        centre_y = rng.uniform(18.0, side - 18.0)
        radius = rng.uniform(5.0, 18.0)
        distance = np.hypot(grid_x - centre_x, grid_y - centre_y)
        image += rng.uniform(0.2, 0.5) * np.exp(-((distance - radius) / 2.5) ** 2)
    image -= image.min()
    image /= max(float(image.max()), 1e-6)
    return image.astype(np.float32)


def _largest_consensus(
    values: np.ndarray,
    *,
    tolerance: float,
) -> tuple[int, np.ndarray]:
    """Return the largest Chebyshev-distance consensus cluster."""
    best_count = 0
    best_centre = np.array([np.nan, np.nan])
    for candidate in values:
        members = np.max(np.abs(values - candidate), axis=1) <= tolerance
        count = int(members.sum())
        if count > best_count:
            best_count = count
            best_centre = values[members].mean(axis=0)
    return best_count, best_centre


def test_empty_synthetic_images_return_an_empty_correspondence_set() -> None:
    result = run_sift(
        _pair(),
        _representation(
            np.empty((0, 0), dtype=np.float32),
            np.empty((0, 0), dtype=np.float32),
        ),
    )

    assert result.pair_id == "synthetic-sift-safety"
    assert result.matcher_id == "sift"
    assert result.representation_id == "intensity"
    assert result.matches == []


def test_non_finite_synthetic_images_fail_before_opencv() -> None:
    image = np.zeros((32, 32), dtype=np.float32)
    image[0, 0] = np.nan

    with pytest.raises(ValueError, match="finite"):
        run_sift(_pair(), _representation(image, np.zeros((32, 32), dtype=np.float32)))


def test_invalid_mask_shape_fails_before_feature_detection() -> None:
    image = np.zeros((32, 32), dtype=np.float32)
    representation = _representation(
        image,
        image,
        source_valid_mask=np.ones((31, 32), dtype=bool),
    )

    with pytest.raises(ValueError, match="valid mask"):
        run_sift(_pair(), representation)


def test_sift_recovers_the_direction_of_a_synthetic_translation() -> None:
    """A software-only check of recovered direction on known synthetic pixels."""
    source = _textured_image()
    shift_x, shift_y = 13, -9
    reference = np.roll(np.roll(source, shift_y, axis=0), shift_x, axis=1)

    result = match(_pair(), _representation(source, reference))

    assert len(result.matches) >= 4
    displacements = np.array(
        [
            (
                item.reference_xy[0] - item.source_xy[0],
                item.reference_xy[1] - item.source_xy[1],
            )
            for item in result.matches
        ]
    )
    count, displacement = _largest_consensus(displacements, tolerance=2.0)

    assert count >= 4
    assert displacement[0] > 0.0
    assert displacement[1] < 0.0
    assert np.allclose(displacement, (shift_x, shift_y), atol=2.0)


def test_sift_matches_are_geometrically_consistent_for_a_synthetic_scale() -> None:
    """Engineering-only scale check; it does not establish lunar scale invariance."""
    import cv2

    source = _textured_image(seed=23)
    scale = 1.25
    reference = cv2.resize(source, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)

    result = match(_pair(), _representation(source, reference.astype(np.float32)))

    assert len(result.matches) >= 4
    residuals = np.array(
        [
            (
                item.reference_xy[0] - scale * item.source_xy[0],
                item.reference_xy[1] - scale * item.source_xy[1],
            )
            for item in result.matches
        ]
    )
    count, offset = _largest_consensus(residuals, tolerance=3.0)

    assert count >= 4
    assert np.linalg.norm(offset) <= 3.0


def test_featureless_non_empty_images_return_an_empty_correspondence_set() -> None:
    image = np.full((64, 64), 0.5, dtype=np.float32)

    result = match(_pair(), _representation(image, image))

    assert result.matcher_id == "sift"
    assert result.matches == []
