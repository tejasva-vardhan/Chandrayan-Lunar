"""Synthetic ground-truth characterisation of the RIFT adapter.

These tests exist so EXP-001 can state what its RIFT implementation actually
does instead of assuming the published behaviour. Every case has a known
transform, so recovery is measured, not asserted by reputation.

Marked ``scientific``: synthetic measurement, not official SIH evidence.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.matching.orb_adapter import run_orb
from src.matching.phase_congruency import LogGaborSettings, phase_congruency
from src.matching.rift_adapter import run_rift
from src.matching.settings import RiftSettings
from src.matching.sift_adapter import run_sift
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult

pytestmark = pytest.mark.scientific

_SIDE = 512
_SHIFT_X = 21
_SHIFT_Y = 13


def _textured_image(side: int = _SIDE, seed: int = 7) -> np.ndarray:
    """Crater-like blobs over correlated noise: lunar-ish, fully synthetic."""

    rng = np.random.default_rng(seed)
    grid_y, grid_x = np.mgrid[0:side, 0:side].astype(np.float32)
    image = 0.35 + 0.05 * rng.standard_normal((side, side)).astype(np.float32)
    for _ in range(60):
        centre_x = rng.uniform(0, side)
        centre_y = rng.uniform(0, side)
        radius = rng.uniform(6.0, 26.0)
        amplitude = rng.uniform(0.15, 0.45)
        distance = np.sqrt((grid_x - centre_x) ** 2 + (grid_y - centre_y) ** 2)
        rim = np.exp(-(((distance - radius) / 3.0) ** 2))
        bowl = np.exp(-((distance / radius) ** 2)) * 0.6
        image += amplitude * (rim - bowl)
    image -= image.min()
    image /= max(float(image.max()), 1e-6)
    return image.astype(np.float32)


def _pair_and_representation(
    source: np.ndarray, reference: np.ndarray
) -> tuple[RegistrationPair, RepresentationResult]:
    pair = RegistrationPair(
        pair_id="synthetic_rift",
        source=LunarProduct(product_id="src", instrument="OHRC", mission="Chandrayaan-2"),
        reference=LunarProduct(product_id="ref", instrument="LRO_NAC", mission="LRO"),
    )
    representation = RepresentationResult(
        array=source,
        representation_id="intensity",
        metadata={"reference_array": reference},
    )
    return pair, representation


def _recovered_translations(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
    pair, representation = _pair_and_representation(source, reference)
    result = run_rift(pair, representation, RiftSettings())
    if not result.matches:
        return np.empty((0, 2), dtype=float)
    return np.array(
        [
            (
                item.reference_xy[0] - item.source_xy[0],
                item.reference_xy[1] - item.source_xy[1],
            )
            for item in result.matches
        ],
        dtype=float,
    )


def _modal_translation(deltas: np.ndarray, tolerance: float = 2.0) -> tuple[int, np.ndarray]:
    """Largest cluster of translations within ``tolerance`` pixels."""

    if deltas.shape[0] == 0:
        return 0, np.array([np.nan, np.nan])
    best_count = 0
    best_centre = np.array([np.nan, np.nan])
    for candidate in deltas:
        near = np.abs(deltas - candidate).max(axis=1) <= tolerance
        count = int(near.sum())
        if count > best_count:
            best_count = count
            best_centre = deltas[near].mean(axis=0)
    return best_count, best_centre


def _shift(image: np.ndarray, dx: int, dy: int) -> np.ndarray:
    return np.roll(np.roll(image, dy, axis=0), dx, axis=1)


def test_phase_congruency_is_invariant_to_contrast_reversal_and_gain() -> None:
    """The property RIFT depends on: PC does not care about radiometry."""

    image = _textured_image()
    reversed_image = (1.0 - (image * 0.55 + 0.2)).astype(np.float32)

    original = phase_congruency(image, LogGaborSettings())
    altered = phase_congruency(reversed_image, LogGaborSettings())

    correlation = float(
        np.corrcoef(original.max_moment.ravel(), altered.max_moment.ravel())[0, 1]
    )
    agreement = float((original.maximum_index_map == altered.maximum_index_map).mean())

    assert correlation > 0.99
    assert agreement > 0.99


def test_rift_recovers_pure_translation() -> None:
    """Baseline capability: identical radiometry, known integer shift."""

    source = _textured_image()
    reference = _shift(source, _SHIFT_X, _SHIFT_Y)

    deltas = _recovered_translations(source, reference)
    count, centre = _modal_translation(deltas)

    assert count >= 10, f"only {count} agreeing correspondences from {len(deltas)} matches"
    assert abs(centre[0] - _SHIFT_X) <= 2.0
    assert abs(centre[1] - _SHIFT_Y) <= 2.0


def test_rift_recovers_translation_under_contrast_reversal() -> None:
    """The radiation-insensitivity claim, measured on inverted radiometry."""

    source = _textured_image()
    shifted = _shift(source, _SHIFT_X, _SHIFT_Y)
    reference = (1.0 - (shifted * 0.55 + 0.2)).astype(np.float32)

    deltas = _recovered_translations(source, reference)
    count, centre = _modal_translation(deltas)

    assert count >= 10, f"only {count} agreeing correspondences from {len(deltas)} matches"
    assert abs(centre[0] - _SHIFT_X) <= 2.0
    assert abs(centre[1] - _SHIFT_Y) <= 2.0


def test_rift_recovers_translation_under_nonlinear_gamma() -> None:
    """Radiometric non-linearity, the realistic illumination-difference case."""

    source = _textured_image()
    shifted = _shift(source, _SHIFT_X, _SHIFT_Y)
    reference = np.power(np.clip(shifted, 0.0, 1.0), 2.2).astype(np.float32)

    deltas = _recovered_translations(source, reference)
    count, centre = _modal_translation(deltas)

    assert count >= 10, f"only {count} agreeing correspondences from {len(deltas)} matches"
    assert abs(centre[0] - _SHIFT_X) <= 2.0
    assert abs(centre[1] - _SHIFT_Y) <= 2.0


def test_rift_yield_collapses_under_scale_change() -> None:
    """Documented limitation: the fixed descriptor patch is not scale invariant.

    EXP-001's matching views differ in effective ground sample distance, so
    this measured failure mode is a stated confounder of the comparison, not
    an incidental detail.
    """

    import cv2

    source = _textured_image()
    scaled = cv2.resize(source, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)

    same_scale = _recovered_translations(source, _shift(source, _SHIFT_X, _SHIFT_Y))
    cross_scale = _recovered_translations(source, scaled.astype(np.float32))

    same_count, _ = _modal_translation(same_scale)
    cross_count, _ = _modal_translation(cross_scale)

    assert same_count >= 10
    assert cross_count < same_count


def test_rift_beats_sift_and_orb_under_contrast_reversal() -> None:
    """Radiation-insensitivity comparison used as a preregistered expectation."""

    source = _textured_image()
    shifted = _shift(source, _SHIFT_X, _SHIFT_Y)
    reference = (1.0 - (shifted * 0.55 + 0.2)).astype(np.float32)
    pair, representation = _pair_and_representation(source, reference)

    rift = run_rift(pair, representation)
    sift = run_sift(pair, representation)
    orb = run_orb(pair, representation)
    rift_deltas = np.array(
        [
            (
                item.reference_xy[0] - item.source_xy[0],
                item.reference_xy[1] - item.source_xy[1],
            )
            for item in rift.matches
        ],
        dtype=float,
    )
    rift_count, centre = _modal_translation(rift_deltas)

    assert rift_count >= 10
    assert abs(centre[0] - _SHIFT_X) <= 2.0
    assert abs(centre[1] - _SHIFT_Y) <= 2.0
    assert len(rift.matches) > len(sift.matches)
    assert len(rift.matches) > len(orb.matches)


def test_sift_survives_scale_change_better_than_rift() -> None:
    """The matching-view scale confounder, measured rather than assumed."""

    import cv2

    source = _textured_image()
    scaled = cv2.resize(source, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)
    pair, representation = _pair_and_representation(source, scaled.astype(np.float32))

    assert len(run_sift(pair, representation).matches) > len(
        run_rift(pair, representation).matches
    )
