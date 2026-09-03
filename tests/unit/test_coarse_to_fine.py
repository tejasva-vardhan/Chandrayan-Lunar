"""Unit tests for coarse-to-fine SIFT. Software validation only."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.io.ps_correspondence.decision import apply_decision_rule
from src.matching import match
from src.matching.coarse_to_fine import (
    MATCHER_ID,
    _offset_matches,
    _source_windows,
    run_coarse_to_fine_sift,
)
from src.matching.settings import CoarseToFineSettings, SiftSettings
from src.matching.sift_adapter import run_sift
from src.models.correspondence_set import Correspondence
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.representation._loader import load_strided_mask_window, load_strided_window
from src.representation._types import RepresentationResult


def _image(seed: int = 5, side: int = 320) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grid_y, grid_x = np.mgrid[0:side, 0:side].astype(np.float32)
    image = 0.4 + 0.04 * rng.standard_normal((side, side)).astype(np.float32)
    for _ in range(40):
        centre_x = rng.uniform(0, side)
        centre_y = rng.uniform(0, side)
        radius = rng.uniform(5.0, 18.0)
        distance = np.sqrt((grid_x - centre_x) ** 2 + (grid_y - centre_y) ** 2)
        image += 0.3 * np.exp(-(((distance - radius) / 2.5) ** 2))
    image -= image.min()
    image /= max(float(image.max()), 1e-6)
    return image.astype(np.float32)


def _pair() -> RegistrationPair:
    return RegistrationPair(
        pair_id="ctf-pair",
        source=LunarProduct(product_id="src", instrument="OHRC", mission="Chandrayaan-2"),
        reference=LunarProduct(product_id="ref", instrument="LRO_NAC", mission="LRO"),
    )


def _representation(source: np.ndarray, reference: np.ndarray) -> RepresentationResult:
    return RepresentationResult(
        array=source,
        representation_id="intensity",
        metadata={"reference_array": reference},
    )


def test_frozen_match_is_unchanged_single_view_sift() -> None:
    source = _image()
    reference = np.roll(source, 11, axis=1)
    pair = _pair()
    representation = _representation(source, reference)
    frozen = match(pair, representation)
    default = run_sift(pair, representation, settings=SiftSettings())
    assert frozen.matcher_id == "sift"
    assert len(frozen.matches) == len(default.matches)
    for left, right in zip(frozen.matches, default.matches, strict=True):
        assert left.source_xy == right.source_xy
        assert left.reference_xy == right.reference_xy


def test_coarse_to_fine_without_rasters_keeps_coarse_matches() -> None:
    source = _image()
    reference = np.roll(source, 11, axis=1)
    pair = _pair()
    representation = _representation(source, reference)
    coarse = run_sift(pair, representation, settings=SiftSettings())
    diagnostics: dict[str, object] = {}
    result = run_coarse_to_fine_sift(
        pair, representation, diagnostics=diagnostics
    )
    assert result.matcher_id == MATCHER_ID
    assert diagnostics["fine_stage"] == "skipped_no_raster_uri"
    coarse_keys = {(item.source_xy, item.reference_xy) for item in coarse.matches}
    result_keys = {(item.source_xy, item.reference_xy) for item in result.matches}
    assert coarse_keys == result_keys
    assert all(item.status == "raw" for item in result.matches)


def test_coarse_to_fine_is_deterministic_on_in_memory_views() -> None:
    source = _image(seed=9)
    reference = np.roll(source, 8, axis=0)
    pair = _pair()
    representation = _representation(source, reference)
    first = run_coarse_to_fine_sift(pair, representation)
    second = run_coarse_to_fine_sift(pair, representation)
    assert len(first.matches) == len(second.matches)
    for left, right in zip(first.matches, second.matches, strict=True):
        assert left.source_xy == right.source_xy
        assert left.reference_xy == right.reference_xy


def test_offset_matches_adds_tile_origin() -> None:
    item = Correspondence(source_xy=(3.5, 4.25), reference_xy=(1.0, 2.0), status="raw")
    offset = _offset_matches([item], source_col=10, source_row=20, reference_col=5, reference_row=7)
    assert offset[0].source_xy == (13.5, 24.25)
    assert offset[0].reference_xy == (6.0, 9.0)
    assert offset[0].status == "raw"


def test_source_windows_respect_pixel_budget_and_tile_cap() -> None:
    cfg = CoarseToFineSettings(max_pixels_per_tile=100, max_fine_tiles=3, fine_stride_factor=0.5)
    windows = _source_windows((0, 0, 80, 400), stride=2, cfg=cfg)
    assert 1 <= len(windows) <= 3
    for row, col, height, width in windows:
        match_h = (height + 1) // 2
        match_w = (width + 1) // 2
        assert match_h * match_w <= cfg.max_pixels_per_tile + 4


def test_strided_window_loader_matches_full_slice(tmp_path: Path) -> None:
    raster = np.arange(200, dtype=np.uint16).reshape(10, 20)
    path = tmp_path / "strip.npy"
    np.save(path, raster)
    window = load_strided_window(str(path), row=2, col=4, height=4, width=6, stride=2)
    expected = (raster[2:6:2, 4:10:2].astype(np.float32) / 65535.0)
    assert window.shape == (2, 3)
    np.testing.assert_allclose(window, expected)


def test_strided_mask_window_is_boolean(tmp_path: Path) -> None:
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[2:6, 2:6] = 1
    path = tmp_path / "mask.npy"
    np.save(path, mask)
    window = load_strided_mask_window(str(path), row=2, col=2, height=4, width=4, stride=1)
    assert window.dtype == bool
    assert bool(window.all())


def test_decision_requires_inlier_and_occupancy_gains() -> None:
    supported = apply_decision_rule(
        independent_variable_applied=True,
        verified_inliers_a=25,
        verified_inliers_b=40,
        source_occupied_a=11,
        source_occupied_b=14,
        reference_occupied_a=9,
        reference_occupied_b=12,
        transform_fitted_a=True,
        transform_fitted_b=True,
        min_samples=4,
        match_runtime_a=4.0,
        match_runtime_b=20.0,
    )
    assert supported["decision"] == "SUPPORTED"

    not_supported = apply_decision_rule(
        independent_variable_applied=True,
        verified_inliers_a=25,
        verified_inliers_b=25,
        source_occupied_a=11,
        source_occupied_b=11,
        reference_occupied_a=9,
        reference_occupied_b=9,
        transform_fitted_a=True,
        transform_fitted_b=True,
        min_samples=4,
        match_runtime_a=4.0,
        match_runtime_b=6.0,
    )
    assert not_supported["decision"] == "NOT SUPPORTED"
    assert not_supported["quality_improved"] is False
