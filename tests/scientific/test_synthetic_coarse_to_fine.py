"""Synthetic coarse-to-fine matching tests. Not lunar accuracy evidence."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.matching import match
from src.matching.coarse_to_fine import MATCHER_ID, run_coarse_to_fine_sift
from src.matching.settings import CoarseToFineSettings, SiftSettings
from src.matching.sift_adapter import run_sift
from src.models.common import ImageDimensions
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult
from src.verification import verify_matches

pytestmark = pytest.mark.scientific


def _texture(side: int = 256, seed: int = 21) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grid_y, grid_x = np.mgrid[0:side, 0:side].astype(np.float32)
    image = 0.4 + 0.04 * rng.standard_normal((side, side)).astype(np.float32)
    for _ in range(50):
        centre_x = rng.uniform(0, side)
        centre_y = rng.uniform(0, side)
        radius = rng.uniform(5.0, 18.0)
        distance = np.sqrt((grid_x - centre_x) ** 2 + (grid_y - centre_y) ** 2)
        image += 0.3 * np.exp(-(((distance - radius) / 2.5) ** 2))
    image -= image.min()
    image /= max(float(image.max()), 1e-6)
    return image.astype(np.float32)


def _pair_and_rep(
    tmp_path: Path, source: np.ndarray, reference: np.ndarray, stride: int
) -> tuple[RegistrationPair, RepresentationResult]:
    src_path = tmp_path / "source.npy"
    ref_path = tmp_path / "reference.npy"
    np.save(src_path, source)
    np.save(ref_path, reference)
    height, width = source.shape
    dims = ImageDimensions(width_px=width, height_px=height)
    pair = RegistrationPair(
        pair_id="synthetic-ctf",
        source=LunarProduct(
            product_id="src",
            instrument="OHRC",
            mission="Chandrayaan-2",
            raster_uri=str(src_path),
            dimensions=dims,
        ),
        reference=LunarProduct(
            product_id="ref",
            instrument="LRO_NAC",
            mission="LRO",
            raster_uri=str(ref_path),
            dimensions=dims,
        ),
    )
    representation = RepresentationResult(
        array=source[::stride, ::stride],
        representation_id="intensity",
        metadata={
            "reference_array": reference[::stride, ::stride],
            "source_matching_view": {
                "stride": stride,
                "x_scale": float(stride),
                "y_scale": float(stride),
                "original_shape": [height, width],
            },
            "reference_matching_view": {
                "stride": stride,
                "x_scale": float(stride),
                "y_scale": float(stride),
                "original_shape": [height, width],
            },
        },
    )
    return pair, representation


def test_fine_stage_uses_half_the_coarse_stride(tmp_path: Path) -> None:
    source = _texture()
    reference = np.roll(source, 12, axis=1)
    pair, representation = _pair_and_rep(tmp_path, source, reference, stride=2)
    diagnostics: dict[str, object] = {}
    result = run_coarse_to_fine_sift(
        pair,
        representation,
        settings=SiftSettings(),
        coarse_to_fine=CoarseToFineSettings(max_fine_tiles=2, coarse_min_inliers=5),
        diagnostics=diagnostics,
    )
    assert result.matcher_id == MATCHER_ID
    assert all(item.status == "raw" for item in result.matches)
    if diagnostics.get("fine_stage") == "ran":
        assert diagnostics["source_fine_stride"] == 1
        assert diagnostics["reference_fine_stride"] == 1
        assert int(diagnostics["coarse_raw_matches"]) <= len(result.matches)
    else:
        assert diagnostics.get("fine_stage") == "skipped_insufficient_coarse_inliers"


def test_coarse_keys_are_preserved_when_fine_stage_runs(tmp_path: Path) -> None:
    source = _texture(seed=8)
    reference = np.roll(source, 9, axis=1)
    pair, representation = _pair_and_rep(tmp_path, source, reference, stride=2)
    coarse = run_sift(pair, representation, settings=SiftSettings())
    result = run_coarse_to_fine_sift(pair, representation)
    coarse_keys = {(item.source_xy, item.reference_xy) for item in coarse.matches}
    result_keys = {(item.source_xy, item.reference_xy) for item in result.matches}
    assert coarse_keys <= result_keys


def test_downstream_verification_accepts_coarse_to_fine_output(tmp_path: Path) -> None:
    source = _texture(seed=3)
    reference = np.roll(source, 10, axis=1)
    pair, representation = _pair_and_rep(tmp_path, source, reference, stride=2)
    correspondences = run_coarse_to_fine_sift(pair, representation)
    verified = verify_matches(correspondences, pair)
    assert verified.matcher_id == MATCHER_ID
    assert verified.pair_id == pair.pair_id
    assert {item.status for item in verified.matches} <= {"inlier", "rejected", "filtered", "raw"}


def test_frozen_match_still_returns_sift_on_npy_pair(tmp_path: Path) -> None:
    source = _texture(seed=4)
    pair, representation = _pair_and_rep(tmp_path, source, source.copy(), stride=2)
    frozen = match(pair, representation)
    assert frozen.matcher_id == "sift"
