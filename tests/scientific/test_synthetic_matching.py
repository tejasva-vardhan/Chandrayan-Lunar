"""Synthetic matching tests for the SIFT adapter. Software validation only.

These tests use synthetic numpy arrays and are NOT lunar-accuracy results.
They are not SIH evaluator evidence (D-011, D-012).

What is tested
--------------
- match() returns a valid CorrespondenceSet (contract compliance).
- SIFT finds matches on two identical synthetic images (trivial case).
- SIFT finds matches when one image is a shifted version of the other.
- match() gracefully returns an empty set when raster_uri is missing (no crash).
- match() returns correct pair_id and matcher_id.
- Confidence values are in [0, 1] or None.
- All returned status values are "raw" (verification is a separate stage).

What is NOT tested here
-----------------------
- Lunar accuracy on real Chandrayaan-2 or LRO products.
- Final matcher selection (D-007).
- Lowe ratio threshold optimality.
"""

from __future__ import annotations

import os
import tempfile

import cv2
import numpy as np
import pytest

from src.matching import match
from src.matching.shared import map_point_to_original
from src.matching.sift_adapter import SiftSettings, run_sift
from src.models import CorrespondenceSet, LunarProduct, RegistrationPair
from src.models.common import ImageDimensions
from src.representation._types import RepresentationResult

pytestmark = pytest.mark.scientific


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synthetic_image(height: int = 256, width: int = 256, seed: int = 0) -> np.ndarray:
    """Create a synthetic float32 image with random blobs (repeatable texture)."""
    rng = np.random.default_rng(seed)
    img = np.zeros((height, width), dtype=np.float32)
    # Add blobs for texture
    for _ in range(30):
        cx = int(rng.integers(20, width - 20))
        cy = int(rng.integers(20, height - 20))
        r = int(rng.integers(8, 25))
        cv2.circle(img, (cx, cy), r, float(rng.uniform(0.2, 1.0)), -1)
    # Add Gaussian noise
    img += rng.normal(0, 0.02, img.shape).astype(np.float32)
    return np.clip(img, 0.0, 1.0).astype(np.float32)


def _write_png(arr: np.ndarray, path: str) -> None:
    """Write float32 [0,1] array to PNG file."""
    u8 = (arr * 255.0).clip(0, 255).astype(np.uint8)
    cv2.imwrite(path, u8)


def _pair_from_arrays(
    src_arr: np.ndarray,
    ref_arr: np.ndarray,
    tmp_dir: str,
    pair_id: str = "test-pair",
) -> tuple[RegistrationPair, RepresentationResult]:
    """Save arrays to temp PNG files and build pair + representation."""
    src_path = os.path.join(tmp_dir, "source.png")
    ref_path = os.path.join(tmp_dir, "reference.png")
    _write_png(src_arr, src_path)
    _write_png(ref_arr, ref_path)

    dims = ImageDimensions(width_px=src_arr.shape[1], height_px=src_arr.shape[0])
    pair = RegistrationPair(
        pair_id=pair_id,
        source=LunarProduct(
            product_id="src-synth", instrument="OHRC", dimensions=dims, raster_uri=src_path
        ),
        reference=LunarProduct(
            product_id="ref-synth", instrument="LRO_NAC", dimensions=dims, raster_uri=ref_path
        ),
    )
    representation = RepresentationResult(
        array=src_arr,
        representation_id="intensity",
        metadata={"reference_array": ref_arr},
    )
    return pair, representation


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_match_returns_correspondence_set_type(registration_pair: RegistrationPair) -> None:
    """match() always returns a CorrespondenceSet, never raises on missing raster_uri."""
    # No raster_uri set — SIFT adapter should return empty set, not crash.
    result = match(registration_pair)
    assert isinstance(result, CorrespondenceSet)


def test_match_pair_id_and_matcher_id(registration_pair: RegistrationPair) -> None:
    """CorrespondenceSet carries correct pair_id and matcher_id="sift"."""
    result = match(registration_pair)
    assert result.pair_id == registration_pair.pair_id
    assert result.matcher_id == "sift"


def test_sift_on_identical_images_finds_matches() -> None:
    """SIFT must find matches when source and reference are the same image."""
    arr = _synthetic_image(256, 256, seed=42)
    with tempfile.TemporaryDirectory() as tmp:
        pair, rep = _pair_from_arrays(arr, arr.copy(), tmp, pair_id="identical-pair")
        cs = run_sift(pair, rep, settings=SiftSettings(min_matches=4))
    # Identical images should give many matches.
    assert isinstance(cs, CorrespondenceSet)
    assert len(cs.matches) >= 4, (
        f"Expected >=4 matches on identical images, got {len(cs.matches)}"
    )


def test_sift_on_shifted_image_finds_matches() -> None:
    """SIFT finds matches when reference is a translated crop of the source."""
    src = _synthetic_image(300, 300, seed=7)
    # Shift by 20 pixels: take a crop from the same region.
    ref = src[10:300, 10:300]  # smaller — simulate translation
    ref = cv2.resize(ref, (300, 300))  # resize back to same dimensions

    with tempfile.TemporaryDirectory() as tmp:
        pair, rep = _pair_from_arrays(src, ref.astype(np.float32), tmp, pair_id="shifted-pair")
        cs = run_sift(pair, rep, settings=SiftSettings(min_matches=4))

    assert isinstance(cs, CorrespondenceSet)
    assert len(cs.matches) >= 4, (
        f"Expected matches on shifted image, got {len(cs.matches)}"
    )


def test_sift_confidence_in_valid_range() -> None:
    """All non-None confidence values must be in [0, 1]."""
    arr = _synthetic_image(256, 256, seed=3)
    with tempfile.TemporaryDirectory() as tmp:
        pair, rep = _pair_from_arrays(arr, arr.copy(), tmp, pair_id="conf-test")
        cs = run_sift(pair, rep, settings=SiftSettings())
    for m in cs.matches:
        if m.confidence is not None:
            assert 0.0 <= m.confidence <= 1.0, (
                f"confidence out of range: {m.confidence}"
            )


def test_sift_all_statuses_are_raw() -> None:
    """All matches returned by the adapter must have status='raw'.

    Verification (inlier/rejected assignment) is Shaiz's stage.
    """
    arr = _synthetic_image(256, 256, seed=9)
    with tempfile.TemporaryDirectory() as tmp:
        pair, rep = _pair_from_arrays(arr, arr.copy(), tmp, pair_id="status-test")
        cs = run_sift(pair, rep, settings=SiftSettings())
    for m in cs.matches:
        assert m.status == "raw", f"Expected status='raw', got {m.status!r}"


def test_sift_empty_image_returns_empty_set() -> None:
    """SIFT on a flat (no-texture) image returns empty matches, does not crash."""
    flat = np.zeros((128, 128), dtype=np.float32)
    with tempfile.TemporaryDirectory() as tmp:
        pair, rep = _pair_from_arrays(flat, flat.copy(), tmp, pair_id="flat-pair")
        cs = run_sift(pair, rep, settings=SiftSettings())
    assert isinstance(cs, CorrespondenceSet)
    assert cs.matches == []


def test_sift_no_raster_uri_returns_empty_set(registration_pair: RegistrationPair) -> None:
    """match() with no raster_uri and no representation returns empty set gracefully."""
    # registration_pair fixture has no raster_uri set.
    cs = match(registration_pair)
    assert isinstance(cs, CorrespondenceSet)
    assert cs.matches == []
    assert cs.matcher_id == "sift"


def test_sift_coordinates_are_within_image_bounds() -> None:
    """All match coordinates must be within the image dimensions."""
    h, w = 256, 256
    arr = _synthetic_image(h, w, seed=11)
    with tempfile.TemporaryDirectory() as tmp:
        pair, rep = _pair_from_arrays(arr, arr.copy(), tmp, pair_id="bounds-test")
        cs = run_sift(pair, rep, settings=SiftSettings())
    for m in cs.matches:
        sx, sy = m.source_xy
        rx, ry = m.reference_xy
        assert 0 <= sx < w, f"source_xy x={sx} out of bounds (width={w})"
        assert 0 <= sy < h, f"source_xy y={sy} out of bounds (height={h})"
        assert 0 <= rx < w, f"reference_xy x={rx} out of bounds (width={w})"
        assert 0 <= ry < h, f"reference_xy y={ry} out of bounds (height={h})"


def test_matching_view_coordinate_mapping_is_deterministic() -> None:
    assert map_point_to_original((10.5, 4.25), (8.0, 8.0)) == (84.0, 34.0)


def test_sift_outputs_original_coordinate_system_for_scaled_views() -> None:
    arr = _synthetic_image(256, 256, seed=21)
    with tempfile.TemporaryDirectory() as tmp:
        pair, rep = _pair_from_arrays(arr, arr.copy(), tmp, pair_id="scaled-view")
        rep.metadata["source_matching_view"] = {
            "x_scale": 4.0,
            "y_scale": 4.0,
            "stride": 4,
            "policy": "stride_decimation",
        }
        rep.metadata["reference_matching_view"] = {
            "x_scale": 4.0,
            "y_scale": 4.0,
            "stride": 4,
            "policy": "stride_decimation",
        }
        rep.array = rep.array[::4, ::4]
        rep.metadata["reference_array"] = rep.metadata["reference_array"][::4, ::4]
        cs = run_sift(pair, rep, settings=SiftSettings(min_matches=4))
    assert cs.matches
    for match_item in cs.matches:
        assert 0.0 <= match_item.source_xy[0] < 256
        assert 0.0 <= match_item.source_xy[1] < 256
        assert 0.0 <= match_item.reference_xy[0] < 256
        assert 0.0 <= match_item.reference_xy[1] < 256
