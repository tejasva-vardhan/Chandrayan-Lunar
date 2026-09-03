"""Unit tests for the illumination-normalization representation.

Software validation on synthetic arrays only. Not lunar accuracy, not
Sun-angle evidence, and not official SIH evaluator evidence.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.models import LunarProduct, RegistrationPair
from src.models.common import ImageDimensions
from src.models.registration_pair import PairCharacterization
from src.representation import (
    ILLUMINATION_REPRESENTATION_ID,
    MatchingViewSettings,
    generate_representation,
    generate_representation_with_settings,
)
from src.representation.illumination import build_illumination_array
from src.representation.illumination_settings import (
    IlluminationSettings,
    unvalidated_illumination_defaults,
)


def _texture(height: int = 32, width: int = 40) -> np.ndarray:
    """Smooth structured intensity; not a lunar scene."""
    rows = np.arange(height, dtype=np.float64)[:, None]
    cols = np.arange(width, dtype=np.float64)[None, :]
    return 12.0 + 4.0 * np.sin(cols / 5.0) + 3.0 * np.cos(rows / 6.0) + 0.15 * cols


def _settings(**overrides: object) -> IlluminationSettings:
    base = unvalidated_illumination_defaults()
    values = {field: getattr(base, field) for field in base.__dataclass_fields__}
    values.update(overrides)
    return IlluminationSettings(**values)  # type: ignore[arg-type]


class TestIlluminationArray:
    def test_multiplicative_brightness_change(self) -> None:
        image = _texture()
        scaled = 2.75 * image
        left = build_illumination_array(image)
        right = build_illumination_array(scaled)
        assert left.shape == image.shape
        np.testing.assert_allclose(left, right, atol=1e-5, equal_nan=True)

    def test_additive_brightness_change(self) -> None:
        image = _texture()
        shifted = image + 18.0
        left = build_illumination_array(image)
        right = build_illumination_array(shifted)
        np.testing.assert_allclose(left, right, atol=1e-5, equal_nan=True)

    def test_different_dynamic_ranges(self) -> None:
        image = _texture()
        stretched = 850.0 * image - 40.0
        left = build_illumination_array(image)
        right = build_illumination_array(stretched)
        np.testing.assert_allclose(left, right, atol=1e-5, equal_nan=True)

    def test_invalid_nan_and_inf_pixels_are_preserved(self) -> None:
        image = _texture()
        image = image.copy()
        image[2, 3] = np.nan
        image[4, 5] = np.inf
        image[6, 7] = -np.inf
        result = build_illumination_array(image)
        assert np.isnan(result[2, 3])
        assert np.isnan(result[4, 5])
        assert np.isnan(result[6, 7])
        assert np.isfinite(result[8, 9])
        assert result.dtype == np.float32

    def test_product_mask_excludes_pixels(self) -> None:
        image = _texture()
        mask = np.ones(image.shape, dtype=bool)
        mask[10:14, 11:16] = False
        result = build_illumination_array(image, mask)
        assert np.all(np.isnan(result[~mask]))
        assert np.all(np.isfinite(result[mask]))

    def test_constant_image_maps_to_midpoint(self) -> None:
        constant = np.full((24, 24), 7.0, dtype=np.float64)
        result = build_illumination_array(constant)
        assert result.shape == constant.shape
        np.testing.assert_allclose(result, 0.5, atol=1e-6)

    def test_near_constant_image_does_not_crash(self) -> None:
        near = np.full((24, 24), 7.0, dtype=np.float64)
        near[12, 12] = 7.0 + 1e-12
        result = build_illumination_array(near)
        assert result.shape == near.shape
        assert np.all(np.isfinite(result))

    def test_deterministic_output(self) -> None:
        image = _texture()
        image[1, 1] = np.nan
        first = build_illumination_array(image)
        second = build_illumination_array(image.copy())
        np.testing.assert_array_equal(first, second)

    def test_does_not_resize(self) -> None:
        image = _texture(17, 23)
        result = build_illumination_array(image)
        assert result.shape == (17, 23)

    def test_three_dimensional_array_is_processed_per_band(self) -> None:
        band0 = _texture(16, 16)
        band1 = 4.0 * band0 + 9.0
        cube = np.stack([band0, band1], axis=2)
        result = build_illumination_array(cube)
        assert result.shape == (16, 16, 2)
        np.testing.assert_allclose(result[:, :, 0], result[:, :, 1], atol=1e-5)

    def test_unaligned_mask_raises(self) -> None:
        image = _texture(8, 8)
        with pytest.raises(ValueError, match="does not match"):
            build_illumination_array(image, np.ones((7, 8), dtype=bool))

    def test_all_invalid_returns_nan(self) -> None:
        image = np.full((8, 8), np.nan)
        result = build_illumination_array(image)
        assert np.all(np.isnan(result))


class TestIlluminationPipelineWiring:
    def test_generate_representation_default_is_still_intensity(self, tmp_path: Path) -> None:
        image = _texture().astype(np.float32)
        source_path = tmp_path / "src.npy"
        reference_path = tmp_path / "ref.npy"
        np.save(source_path, image)
        np.save(reference_path, image)
        pair = RegistrationPair(
            pair_id="illum-default",
            source=LunarProduct(
                product_id="s",
                instrument="OHRC",
                dimensions=ImageDimensions(width_px=40, height_px=32),
                raster_uri=str(source_path),
            ),
            reference=LunarProduct(
                product_id="r",
                instrument="LRO_NAC",
                dimensions=ImageDimensions(width_px=40, height_px=32),
                raster_uri=str(reference_path),
            ),
        )
        result = generate_representation(pair)
        assert result.representation_id == "intensity"

    def test_override_selects_illumination_without_changing_frozen_signature(
        self, tmp_path: Path
    ) -> None:
        image = _texture().astype(np.float32)
        image[0, 0] = np.nan
        source_path = tmp_path / "src.npy"
        reference_path = tmp_path / "ref.npy"
        np.save(source_path, image)
        np.save(reference_path, image)
        pair = RegistrationPair(
            pair_id="illum-override",
            source=LunarProduct(
                product_id="s",
                instrument="OHRC",
                dimensions=ImageDimensions(width_px=40, height_px=32),
                raster_uri=str(source_path),
            ),
            reference=LunarProduct(
                product_id="r",
                instrument="LRO_NAC",
                dimensions=ImageDimensions(width_px=40, height_px=32),
                raster_uri=str(reference_path),
            ),
        )
        result = generate_representation_with_settings(
            pair,
            MatchingViewSettings(representation_id_override=ILLUMINATION_REPRESENTATION_ID),
        )
        assert result.representation_id == ILLUMINATION_REPRESENTATION_ID
        assert result.array.shape == image.shape
        assert np.isnan(result.array[0, 0])
        assert result.metadata["illumination_baseline"]["solves_lunar_sun_angle"] is False
        mask = result.metadata["source_valid_mask"]
        assert isinstance(mask, np.ndarray)
        assert not bool(mask[0, 0])


def _npy_pair(
    tmp_path: Path,
    image: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    declared_height: int | None = None,
    declared_width: int | None = None,
    difficulty: str | None = None,
) -> RegistrationPair:
    height, width = image.shape
    source_path = tmp_path / "src.npy"
    reference_path = tmp_path / "ref.npy"
    np.save(source_path, image)
    np.save(reference_path, image)
    source_mask_uri: str | None = None
    reference_mask_uri: str | None = None
    if mask is not None:
        source_mask_path = tmp_path / "src-mask.npy"
        reference_mask_path = tmp_path / "ref-mask.npy"
        np.save(source_mask_path, mask)
        np.save(reference_mask_path, mask)
        source_mask_uri = str(source_mask_path)
        reference_mask_uri = str(reference_mask_path)
    dims = ImageDimensions(
        width_px=width if declared_width is None else declared_width,
        height_px=height if declared_height is None else declared_height,
    )
    characterization = (
        PairCharacterization(difficulty=difficulty) if difficulty is not None else None
    )
    return RegistrationPair(
        pair_id="mask-path",
        source=LunarProduct(
            product_id="s",
            instrument="OHRC",
            dimensions=dims,
            raster_uri=str(source_path),
            mask_uri=source_mask_uri,
        ),
        reference=LunarProduct(
            product_id="r",
            instrument="LRO_NAC",
            dimensions=dims,
            raster_uri=str(reference_path),
            mask_uri=reference_mask_uri,
        ),
        characterization=characterization,
    )


class TestExistingRepresentationMaskPath:
    @pytest.mark.parametrize(
        ("difficulty", "representation_id"),
        [
            (None, "intensity"),
            ("normal", "gradient"),
            ("difficult", "structural"),
        ],
    )
    def test_mask_expected_shape_is_loaded_array_not_declared_dimensions(
        self,
        tmp_path: Path,
        difficulty: str | None,
        representation_id: str,
    ) -> None:
        image = _texture(32, 40).astype(np.float32)
        mask = np.ones((32, 40), dtype=np.uint8)
        mask[0, 1] = 0
        pair = _npy_pair(
            tmp_path,
            image,
            mask=mask,
            declared_height=64,
            declared_width=64,
            difficulty=difficulty,
        )
        result = generate_representation(pair)
        assert result.representation_id == representation_id
        source_mask = result.metadata["source_valid_mask"]
        assert isinstance(source_mask, np.ndarray)
        assert source_mask.shape == (32, 40)
        assert not bool(source_mask[0, 1])
        assert bool(source_mask[1, 1])

    @pytest.mark.parametrize("difficulty", [None, "normal", "difficult"])
    def test_malformed_mask_is_checked_against_loaded_array(
        self, tmp_path: Path, difficulty: str | None
    ) -> None:
        image = _texture(32, 40).astype(np.float32)
        pair = _npy_pair(
            tmp_path,
            image,
            mask=np.ones((8, 8), dtype=np.uint8),
            declared_height=64,
            declared_width=64,
            difficulty=difficulty,
        )
        with pytest.raises(ValueError, match="does not match"):
            generate_representation(pair)

    def test_missing_mask_stays_none_for_intensity(self, tmp_path: Path) -> None:
        pair = _npy_pair(tmp_path, _texture().astype(np.float32))
        result = generate_representation(pair)
        assert result.representation_id == "intensity"
        assert result.metadata["source_valid_mask"] is None
        assert result.metadata["reference_valid_mask"] is None

    def test_cross_sensor_override_still_falls_back_to_intensity(self, tmp_path: Path) -> None:
        pair = _npy_pair(tmp_path, _texture().astype(np.float32))
        result = generate_representation_with_settings(
            pair,
            MatchingViewSettings(representation_id_override="cross_sensor"),
        )
        assert result.representation_id == "intensity"


class TestIlluminationMaskPath:
    def test_product_mask_is_applied_to_illumination_array(self, tmp_path: Path) -> None:
        image = _texture().astype(np.float32)
        mask = np.ones(image.shape, dtype=np.uint8)
        mask[5:8, 6:10] = 0
        pair = _npy_pair(tmp_path, image, mask=mask)
        result = generate_representation_with_settings(
            pair,
            MatchingViewSettings(representation_id_override=ILLUMINATION_REPRESENTATION_ID),
        )
        assert result.representation_id == ILLUMINATION_REPRESENTATION_ID
        excluded = mask == 0
        assert np.all(np.isnan(result.array[excluded]))
        source_mask = result.metadata["source_valid_mask"]
        assert isinstance(source_mask, np.ndarray)
        assert source_mask.shape == image.shape
        assert np.array_equal(source_mask, mask.astype(bool))

    def test_malformed_illumination_mask_raises(self, tmp_path: Path) -> None:
        image = _texture(32, 40).astype(np.float32)
        pair = _npy_pair(tmp_path, image, mask=np.ones((8, 8), dtype=np.uint8))
        with pytest.raises(ValueError, match="does not match"):
            generate_representation_with_settings(
                pair,
                MatchingViewSettings(representation_id_override=ILLUMINATION_REPRESENTATION_ID),
            )
