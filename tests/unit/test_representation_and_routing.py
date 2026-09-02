"""Unit tests for representation module contracts and routing.

Software validation only — not lunar accuracy or SIH evidence.
"""

from __future__ import annotations

import os
import tempfile

import cv2
import numpy as np
import pytest

from src.models import LunarProduct, RegistrationPair
from src.models.common import ImageDimensions
from src.models.registration_pair import PairCharacterization
from src.representation import (
    MatchingViewSettings,
    RepresentationResult,
    generate_representation,
    generate_representation_with_settings,
)
from src.representation._loader import inspect_array_shape, load_array
from src.representation._matching_view import stride_for_shape
from src.representation.gradient import build_gradient
from src.representation.intensity import build_intensity
from src.representation.structural import build_structural
from src.routing import select_matcher_id, select_representation_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_png(arr: np.ndarray, path: str) -> None:
    u8 = (arr * 255.0).clip(0, 255).astype(np.uint8)
    cv2.imwrite(path, u8)


def _simple_image(h: int = 64, w: int = 64) -> np.ndarray:
    """A simple synthetic image with gradient texture."""
    img = np.zeros((h, w), dtype=np.float32)
    for y in range(h):
        for x in range(w):
            img[y, x] = (x + y) / (h + w)
    return img


def _pair_with_uris(
    src_uri: str | None,
    ref_uri: str | None,
    difficulty: str | None = None,
    pair_id: str = "test-pair",
) -> RegistrationPair:
    dims = ImageDimensions(width_px=64, height_px=64)
    char = PairCharacterization(difficulty=difficulty) if difficulty is not None else None  # type: ignore[arg-type]
    return RegistrationPair(
        pair_id=pair_id,
        source=LunarProduct(
            product_id="s", instrument="OHRC", dimensions=dims, raster_uri=src_uri
        ),
        reference=LunarProduct(
            product_id="r", instrument="LRO_NAC", dimensions=dims, raster_uri=ref_uri
        ),
        characterization=char,
    )


# ---------------------------------------------------------------------------
# _loader tests
# ---------------------------------------------------------------------------

class TestLoader:
    def test_load_uint8_png(self) -> None:
        arr = _simple_image()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "img.png")
            _write_png(arr, path)
            loaded = load_array(path)
        assert loaded.dtype == np.float32
        assert loaded.min() >= 0.0
        assert loaded.max() <= 1.0

    def test_load_raises_on_missing_file(self) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            load_array("/nonexistent/path/image.png")

    def test_load_raises_on_empty_uri(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            load_array("")

    def test_load_shape_is_2d(self) -> None:
        arr = _simple_image(32, 48)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "img.png")
            _write_png(arr, path)
            loaded = load_array(path)
        assert loaded.ndim == 2
        assert loaded.shape == (32, 48)

    def test_load_npy_with_stride_decimation(self) -> None:
        arr = np.arange(64, dtype=np.uint16).reshape(8, 8)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "img.npy")
            np.save(path, arr)
            loaded = load_array(path, stride=2)
        assert loaded.shape == (4, 4)
        assert loaded.dtype == np.float32

    def test_inspect_array_shape_for_npy(self) -> None:
        arr = np.zeros((11, 13), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "img.npy")
            np.save(path, arr)
            shape = inspect_array_shape(path)
        assert shape == (11, 13)


# ---------------------------------------------------------------------------
# Representation sub-module tests
# ---------------------------------------------------------------------------

class TestIntensityRepresentation:
    def test_returns_float32_in_01(self) -> None:
        arr = _simple_image()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "img.png")
            _write_png(arr, path)
            result = build_intensity(path)
        assert result.dtype == np.float32
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_flat_image_does_not_crash(self) -> None:
        flat = np.zeros((32, 32), dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "flat.png")
            _write_png(flat, path)
            result = build_intensity(path)
        assert result.dtype == np.float32
        assert result.shape == (32, 32)


class TestGradientRepresentation:
    def test_returns_float32_in_01(self) -> None:
        arr = _simple_image()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "img.png")
            _write_png(arr, path)
            result = build_gradient(path)
        assert result.dtype == np.float32
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_flat_image_returns_zeros(self) -> None:
        flat = np.zeros((32, 32), dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "flat.png")
            _write_png(flat, path)
            result = build_gradient(path)
        assert float(result.max()) == 0.0


class TestStructuralRepresentation:
    def test_returns_float32_in_01(self) -> None:
        arr = _simple_image()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "img.png")
            _write_png(arr, path)
            result = build_structural(path)
        assert result.dtype == np.float32
        assert result.min() >= 0.0
        assert result.max() <= 1.0


# ---------------------------------------------------------------------------
# generate_representation tests
# ---------------------------------------------------------------------------

class TestGenerateRepresentation:
    def test_raises_value_error_when_raster_uri_missing(
        self, registration_pair: RegistrationPair
    ) -> None:
        """Missing raster_uri returns empty sentinel RepresentationResult, not an error."""
        result = generate_representation(registration_pair)
        assert isinstance(result, RepresentationResult)
        assert result.representation_id == "none"
        assert result.metadata.get("no_raster_uri") is True

    def test_returns_representation_result_type(self) -> None:
        arr = _simple_image()
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.png")
            ref_path = os.path.join(tmp, "ref.png")
            _write_png(arr, src_path)
            _write_png(arr, ref_path)
            pair = _pair_with_uris(src_path, ref_path)
            result = generate_representation(pair)
        assert isinstance(result, RepresentationResult)

    def test_result_has_reference_array_in_metadata(self) -> None:
        arr = _simple_image()
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.png")
            ref_path = os.path.join(tmp, "ref.png")
            _write_png(arr, src_path)
            _write_png(arr, ref_path)
            pair = _pair_with_uris(src_path, ref_path)
            result = generate_representation(pair)
        assert "reference_array" in result.metadata
        ref_arr = result.metadata["reference_array"]
        assert isinstance(ref_arr, np.ndarray)

    def test_difficult_pair_selects_structural(self) -> None:
        arr = _simple_image()
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.png")
            ref_path = os.path.join(tmp, "ref.png")
            _write_png(arr, src_path)
            _write_png(arr, ref_path)
            pair = _pair_with_uris(src_path, ref_path, difficulty="difficult")
            result = generate_representation(pair)
        assert result.representation_id == "structural"

    def test_normal_pair_selects_gradient(self) -> None:
        arr = _simple_image()
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.png")
            ref_path = os.path.join(tmp, "ref.png")
            _write_png(arr, src_path)
            _write_png(arr, ref_path)
            pair = _pair_with_uris(src_path, ref_path, difficulty="normal")
            result = generate_representation(pair)
        assert result.representation_id == "gradient"

    def test_no_characterization_selects_intensity(self) -> None:
        arr = _simple_image()
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.png")
            ref_path = os.path.join(tmp, "ref.png")
            _write_png(arr, src_path)
            _write_png(arr, ref_path)
            pair = _pair_with_uris(src_path, ref_path, difficulty=None)
            result = generate_representation(pair)
        assert result.representation_id == "intensity"

    def test_small_images_preserve_full_resolution_behavior(self) -> None:
        arr = _simple_image(32, 40)
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.png")
            ref_path = os.path.join(tmp, "ref.png")
            _write_png(arr, src_path)
            _write_png(arr, ref_path)
            pair = _pair_with_uris(src_path, ref_path)
            result = generate_representation_with_settings(
                pair,
                MatchingViewSettings(max_pixels_per_image=10_000),
            )
        source_view = result.metadata["source_matching_view"]
        reference_view = result.metadata["reference_matching_view"]
        assert isinstance(source_view, dict)
        assert isinstance(reference_view, dict)
        assert source_view["policy"] == "full_resolution"
        assert reference_view["policy"] == "full_resolution"
        assert source_view["stride"] == 1
        assert reference_view["stride"] == 1
        assert result.array.shape == (32, 40)
        assert result.metadata["reference_array"].shape == (32, 40)

    def test_large_images_use_deterministic_matching_view(self) -> None:
        arr = np.arange(96 * 96, dtype=np.uint16).reshape(96, 96)
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.npy")
            ref_path = os.path.join(tmp, "ref.npy")
            np.save(src_path, arr)
            np.save(ref_path, arr)
            dims = ImageDimensions(width_px=96, height_px=96)
            pair = RegistrationPair(
                pair_id="large-view",
                source=LunarProduct(
                    product_id="src",
                    instrument="OHRC",
                    dimensions=dims,
                    raster_uri=src_path,
                ),
                reference=LunarProduct(
                    product_id="ref",
                    instrument="LRO_NAC",
                    dimensions=dims,
                    raster_uri=ref_path,
                ),
            )
            result = generate_representation_with_settings(
                pair,
                MatchingViewSettings(max_pixels_per_image=1_024),
            )
        source_view = result.metadata["source_matching_view"]
        assert isinstance(source_view, dict)
        assert source_view["policy"] == "stride_decimation"
        assert source_view["stride"] == 3
        assert source_view["matching_shape"] == [32, 32]
        assert result.array.shape == (32, 32)

    def test_representation_does_not_overwrite_original_raster(self) -> None:
        arr = np.arange(128 * 128, dtype=np.uint16).reshape(128, 128)
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.npy")
            ref_path = os.path.join(tmp, "ref.npy")
            np.save(src_path, arr)
            np.save(ref_path, arr)
            before = open(src_path, "rb").read()
            dims = ImageDimensions(width_px=128, height_px=128)
            pair = RegistrationPair(
                pair_id="preserve-raster",
                source=LunarProduct(
                    product_id="src",
                    instrument="OHRC",
                    dimensions=dims,
                    raster_uri=src_path,
                ),
                reference=LunarProduct(
                    product_id="ref",
                    instrument="LRO_NAC",
                    dimensions=dims,
                    raster_uri=ref_path,
                ),
            )
            generate_representation_with_settings(
                pair,
                MatchingViewSettings(max_pixels_per_image=1_024),
            )
            after = open(src_path, "rb").read()
        assert after == before

    def test_matching_view_decimates_product_valid_mask(self) -> None:
        arr = np.arange(96 * 96, dtype=np.uint16).reshape(96, 96)
        valid_mask = np.ones((96, 96), dtype=np.uint8)
        valid_mask[::3, ::3] = 0
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.npy")
            ref_path = os.path.join(tmp, "ref.npy")
            src_mask_path = os.path.join(tmp, "src-mask.npy")
            ref_mask_path = os.path.join(tmp, "ref-mask.npy")
            np.save(src_path, arr)
            np.save(ref_path, arr)
            np.save(src_mask_path, valid_mask)
            np.save(ref_mask_path, valid_mask)
            dims = ImageDimensions(width_px=96, height_px=96)
            pair = RegistrationPair(
                pair_id="masked-view",
                source=LunarProduct(
                    product_id="src",
                    instrument="OHRC",
                    dimensions=dims,
                    raster_uri=src_path,
                    mask_uri=src_mask_path,
                ),
                reference=LunarProduct(
                    product_id="ref",
                    instrument="LRO_NAC",
                    dimensions=dims,
                    raster_uri=ref_path,
                    mask_uri=ref_mask_path,
                ),
            )
            result = generate_representation_with_settings(
                pair,
                MatchingViewSettings(max_pixels_per_image=1_024),
            )

        source_mask = result.metadata["source_valid_mask"]
        assert isinstance(source_mask, np.ndarray)
        assert source_mask.shape == (32, 32)
        assert not source_mask.any()

    def test_large_non_npy_raster_fails_closed(self) -> None:
        arr = _simple_image(96, 96)
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "src.png")
            ref_path = os.path.join(tmp, "ref.png")
            _write_png(arr, src_path)
            _write_png(arr, ref_path)
            dims = ImageDimensions(width_px=96, height_px=96)
            pair = RegistrationPair(
                pair_id="unsafe-large-view",
                source=LunarProduct(
                    product_id="src", instrument="OHRC", dimensions=dims, raster_uri=src_path
                ),
                reference=LunarProduct(
                    product_id="ref", instrument="LRO_NAC", dimensions=dims, raster_uri=ref_path
                ),
            )
            with pytest.raises(ValueError, match="memory-mapped .npy"):
                generate_representation_with_settings(
                    pair,
                    MatchingViewSettings(max_pixels_per_image=1_024),
                )


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------

class TestRouting:
    def _pair(self, difficulty: str | None) -> RegistrationPair:
        char = PairCharacterization(difficulty=difficulty) if difficulty is not None else None  # type: ignore[arg-type]
        return RegistrationPair(
            pair_id="route-test",
            source=LunarProduct(product_id="s", instrument="OHRC"),
            reference=LunarProduct(product_id="r", instrument="LRO_NAC"),
            characterization=char,
        )

    def test_no_characterization_selects_intensity(self) -> None:
        pair = RegistrationPair(
            pair_id="p",
            source=LunarProduct(product_id="s", instrument="OHRC"),
            reference=LunarProduct(product_id="r", instrument="LRO_NAC"),
        )
        assert select_representation_id(pair) == "intensity"

    def test_easy_selects_intensity(self) -> None:
        assert select_representation_id(self._pair("easy")) == "intensity"

    def test_normal_selects_gradient(self) -> None:
        assert select_representation_id(self._pair("normal")) == "gradient"

    def test_difficult_selects_structural(self) -> None:
        assert select_representation_id(self._pair("difficult")) == "structural"

    def test_matcher_id_is_sift_for_all_difficulties(self) -> None:
        """All difficulty levels route to SIFT until EXP-001 selects another."""
        for difficulty in (None, "easy", "normal", "difficult"):
            pair = self._pair(difficulty)
            assert select_matcher_id(pair) == "sift", (
                f"Expected 'sift' for difficulty={difficulty}"
            )


class TestMatchingViewPolicy:
    def test_stride_policy_preserves_small_images(self) -> None:
        assert stride_for_shape(512, 512, 4_194_304) == 1

    def test_stride_policy_scales_large_images_by_pixel_budget(self) -> None:
        assert stride_for_shape(52_224, 5_064, 4_194_304) == 8
