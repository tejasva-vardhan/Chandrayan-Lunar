"""Unit tests for software-baseline preprocessing. Not lunar validation."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.geometry import characterize_pair
from src.models import LunarProduct, PairCharacterization, RegistrationPair
from src.models.common import Coordinates, ImageDimensions, Provenance
from src.pipeline.operations import preprocess as pipeline_preprocess
from src.preprocessing import (
    PreprocessingSettings,
    minimal_preprocessing_defaults,
    preprocess,
    preprocess_with_settings,
    unvalidated_software_defaults,
)
from src.preprocessing.intensity import percentile_stretch
from src.preprocessing.mask import valid_mask
from src.preprocessing.raster import load_software_raster


def _settings(**overrides: object) -> PreprocessingSettings:
    base = unvalidated_software_defaults()
    values = {field: getattr(base, field) for field in base.__dataclass_fields__}
    values.update(overrides)
    return PreprocessingSettings(**values)  # type: ignore[arg-type]


def _full_range() -> PreprocessingSettings:
    return _settings(intensity_low_percentile=0.0, intensity_high_percentile=100.0)


def _pair(
    tmp_path: Path | None = None,
    *,
    source: np.ndarray | None = None,
    reference: np.ndarray | None = None,
    source_name: str = "source.npy",
    reference_name: str = "reference.npy",
    source_uri: str | None | bool = True,
    reference_uri: str | None | bool = True,
    characterization: PairCharacterization | None = None,
) -> RegistrationPair:
    source_path: str | None
    reference_path: str | None
    if source_uri is True:
        if tmp_path is None or source is None:
            raise ValueError("source array and tmp_path required")
        source_path = str(tmp_path / source_name)
        np.save(source_path, source)
    elif source_uri is False:
        source_path = None
    else:
        source_path = source_uri
    if reference_uri is True:
        if tmp_path is None or reference is None:
            raise ValueError("reference array and tmp_path required")
        reference_path = str(tmp_path / reference_name)
        np.save(reference_path, reference)
    elif reference_uri is False:
        reference_path = None
    else:
        reference_path = reference_uri
    return RegistrationPair(
        pair_id="pair-pre",
        source=LunarProduct(
            product_id="src-001",
            instrument="OHRC",
            raster_uri=source_path,
            dimensions=ImageDimensions(width_px=8, height_px=8)
            if source is not None
            else None,
            coordinates=Coordinates(crs="IAU_Moon", bbox=(0.0, 0.0, 1.0, 1.0)),
        ),
        reference=LunarProduct(
            product_id="ref-001",
            instrument="LRO_NAC",
            raster_uri=reference_path,
            dimensions=ImageDimensions(width_px=8, height_px=8)
            if reference is not None
            else None,
        ),
        characterization=characterization,
    )


def _load(uri: str | None) -> np.ndarray:
    array, error = load_software_raster(uri)
    assert error is None
    assert array is not None
    return array


def test_preprocess_is_the_frozen_pipeline_callable() -> None:
    assert pipeline_preprocess is preprocess


def test_finite_image_remains_finite(tmp_path: Path) -> None:
    source = np.arange(16, dtype=float).reshape(4, 4)
    pair = _pair(tmp_path, source=source, reference=source + 1.0)
    result = preprocess_with_settings(pair, _full_range())
    out = _load(result.source.raster_uri)
    assert np.all(np.isfinite(out))
    assert out.shape == source.shape


def test_nan_and_inf_never_enter_output_as_numbers(tmp_path: Path) -> None:
    source = np.array([[1.0, math.nan], [math.inf, 3.0]], dtype=float)
    pair = _pair(tmp_path, source=source, reference=np.ones((2, 2)))
    result = preprocess_with_settings(pair, _full_range())
    out = _load(result.source.raster_uri)
    assert math.isnan(out[0, 1])
    assert math.isnan(out[1, 0])
    assert np.isfinite(out[0, 0])
    assert np.isfinite(out[1, 1])
    assert not np.any(np.isinf(out))


def test_constant_image_maps_to_output_midpoint(tmp_path: Path) -> None:
    source = np.full((3, 3), 7.0)
    pair = _pair(tmp_path, source=source, reference=source)
    result = preprocess_with_settings(pair, _full_range())
    out = _load(result.source.raster_uri)
    np.testing.assert_allclose(out, 0.5)


def test_empty_valid_pixels_do_not_fabricate_values(tmp_path: Path) -> None:
    source = np.full((2, 2), np.nan)
    pair = _pair(tmp_path, source=source, reference=np.ones((2, 2)))
    result = preprocess_with_settings(pair, _full_range())
    out = _load(result.source.raster_uri)
    assert np.all(np.isnan(out))
    assert out.shape == (2, 2)


def test_known_full_range_normalization_output(tmp_path: Path) -> None:
    source = np.array([[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]], dtype=float)
    pair = _pair(tmp_path, source=source, reference=source)
    result = preprocess_with_settings(pair, _full_range())
    expected = source / 5.0
    np.testing.assert_allclose(_load(result.source.raster_uri), expected)


def test_robust_normalization_uses_finite_percentiles() -> None:
    plane = np.array([[0.0, 50.0, 100.0], [math.nan, math.inf, 50.0]], dtype=float)
    valid = valid_mask(plane)
    out = percentile_stretch(
        plane,
        valid,
        low_percentile=0.0,
        high_percentile=100.0,
        output_low=0.0,
        output_high=1.0,
    )
    assert math.isnan(out[1, 0])
    assert math.isnan(out[1, 1])
    np.testing.assert_allclose(out[0, 0], 0.0)
    np.testing.assert_allclose(out[0, 2], 1.0)
    np.testing.assert_allclose(out[0, 1], 0.5)


def test_normalization_does_not_fabricate_pixels(tmp_path: Path) -> None:
    source = np.array([[0.0, math.nan], [2.0, 4.0]], dtype=float)
    original_invalid = ~np.isfinite(source)
    pair = _pair(tmp_path, source=source, reference=np.ones((2, 2)))
    result = preprocess_with_settings(pair, _full_range())
    out = _load(result.source.raster_uri)
    assert np.all(np.isnan(out[original_invalid]))
    assert np.all(np.isfinite(out[~original_invalid]))
    assert out.shape == source.shape


def test_zeros_are_valid_intensity(tmp_path: Path) -> None:
    source = np.zeros((2, 2), dtype=float)
    pair = _pair(tmp_path, source=source, reference=np.ones((2, 2)))
    result = preprocess_with_settings(pair, _full_range())
    np.testing.assert_allclose(_load(result.source.raster_uri), 0.5)


def test_source_and_reference_identity_preserved(tmp_path: Path) -> None:
    source = np.arange(9, dtype=float).reshape(3, 3)
    pair = _pair(tmp_path, source=source, reference=source + 3.0)
    result = preprocess(pair)
    assert result.pair_id == pair.pair_id
    assert result.source.product_id == "src-001"
    assert result.reference.product_id == "ref-001"
    assert result.source.instrument == "OHRC"
    assert result.reference.instrument == "LRO_NAC"


def test_pair_characterization_is_preserved(tmp_path: Path) -> None:
    source = np.arange(9, dtype=float).reshape(3, 3)
    products = (
        LunarProduct(product_id="s", instrument="OHRC", gsd_meters=1.0),
        LunarProduct(product_id="r", instrument="TMC-2", gsd_meters=2.0),
    )
    characterized = characterize_pair(*products)
    pair = _pair(
        tmp_path,
        source=source,
        reference=source + 1.0,
        characterization=characterized.characterization,
    )
    result = preprocess(pair)
    assert result.characterization is not None
    assert result.characterization == pair.characterization
    assert result.characterization.gsd_ratio == pytest.approx(0.5)


def test_output_is_deterministic(tmp_path: Path) -> None:
    source = np.array([[1.0, 8.0], [3.0, 5.0]], dtype=float)
    pair = _pair(tmp_path, source=source, reference=source)
    first = preprocess(pair)
    second = preprocess(pair)
    np.testing.assert_array_equal(_load(first.source.raster_uri), _load(second.source.raster_uri))
    assert first.model_dump() == second.model_dump()


def test_original_input_pair_and_raster_remain_unchanged(tmp_path: Path) -> None:
    source = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    pair = _pair(tmp_path, source=source, reference=source)
    original_uri = pair.source.raster_uri
    original_dump = pair.model_dump()
    result = preprocess(pair)
    assert pair.model_dump() == original_dump
    assert result is not pair
    assert result.source.raster_uri != original_uri
    np.testing.assert_array_equal(np.load(original_uri), source)  # type: ignore[arg-type]


def test_missing_raster_uri_is_identity(registration_pair: RegistrationPair) -> None:
    result = preprocess(registration_pair)
    assert result is not registration_pair
    assert result.source.raster_uri is None
    assert result.reference.raster_uri is None
    assert result.pair_id == registration_pair.pair_id
    assert result.source.product_id == registration_pair.source.product_id


def test_invalid_raster_uri_leaves_product_unchanged(tmp_path: Path) -> None:
    missing = str(tmp_path / "absent.npy")
    pair = _pair(tmp_path, source=np.ones((2, 2)), reference_uri=missing)
    result = preprocess(pair)
    assert result.reference.raster_uri == missing
    assert result.source.raster_uri != pair.source.raster_uri


def test_unsupported_raster_encoding_leaves_product_unchanged(tmp_path: Path) -> None:
    bogus = tmp_path / "source.png"
    bogus.write_bytes(b"not-a-raster")
    pair = RegistrationPair(
        pair_id="pair-pre",
        source=LunarProduct(product_id="src", instrument="OHRC", raster_uri=str(bogus)),
        reference=LunarProduct(product_id="ref", instrument="LRO_NAC", raster_uri=str(bogus)),
    )
    result = preprocess(pair)
    assert result.source.raster_uri == str(bogus)
    assert result.reference.raster_uri == str(bogus)


def test_optional_contrast_and_denoise_and_minimal(tmp_path: Path) -> None:
    source = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=float)
    pair = _pair(tmp_path, source=source, reference=source)
    minimal = preprocess_with_settings(pair, minimal_preprocessing_defaults())
    np.testing.assert_allclose(_load(minimal.source.raster_uri), source)
    contrast = preprocess_with_settings(
        pair,
        _settings(
            enable_intensity_normalization=False,
            enable_contrast_normalization=True,
        ),
    )
    contrast_out = _load(contrast.source.raster_uri)
    assert contrast_out.shape == source.shape
    np.testing.assert_allclose(np.median(contrast_out), 0.0, atol=1e-12)
    denoised = preprocess_with_settings(
        pair,
        _settings(enable_intensity_normalization=False, enable_denoise=True),
    )
    denoise_out = _load(denoised.source.raster_uri)
    assert denoise_out.shape == source.shape
    assert np.all(np.isfinite(denoise_out))


def test_scale_ratio_does_not_trigger_resampling(tmp_path: Path) -> None:
    source = np.arange(16, dtype=float).reshape(4, 4)
    reference = np.arange(64, dtype=float).reshape(8, 8)
    pair = RegistrationPair(
        pair_id="pair-pre",
        source=LunarProduct(product_id="src-001", instrument="OHRC", raster_uri=None),
        reference=LunarProduct(product_id="ref-001", instrument="LRO_NAC", raster_uri=None),
        characterization=PairCharacterization(gsd_ratio=4.0),
    )
    src_uri = str(tmp_path / "source.npy")
    ref_uri = str(tmp_path / "reference.npy")
    np.save(src_uri, source)
    np.save(ref_uri, reference)
    pair = pair.model_copy(
        update={
            "source": pair.source.model_copy(update={"raster_uri": src_uri}),
            "reference": pair.reference.model_copy(update={"raster_uri": ref_uri}),
        }
    )
    result = preprocess_with_settings(
        pair,
        _settings(enable_scale_normalization=True, enable_intensity_normalization=False),
    )
    assert _load(result.source.raster_uri).shape == (4, 4)
    assert _load(result.reference.raster_uri).shape == (8, 8)


def test_preprocessing_does_not_modify_coordinates(tmp_path: Path) -> None:
    source = np.ones((3, 3), dtype=float)
    pair = _pair(tmp_path, source=source, reference=source)
    result = preprocess(pair)
    assert result.source.coordinates == pair.source.coordinates
    assert result.source.dimensions == pair.source.dimensions
    assert result.source.gsd_meters == pair.source.gsd_meters


def test_preprocessing_does_not_perform_registration(tmp_path: Path) -> None:
    source = np.arange(9, dtype=float).reshape(3, 3)
    pair = _pair(tmp_path, source=source, reference=source[::-1])
    result = preprocess_with_settings(pair, _full_range())
    out = _load(result.source.raster_uri)
    assert out.shape == (3, 3)
    assert result.overlap_mask_uri == pair.overlap_mask_uri
    # Monotonic stretch: argmax location is unchanged (not a warp).
    assert np.unravel_index(int(np.argmax(source)), source.shape) == np.unravel_index(
        int(np.nanargmax(out)), out.shape
    )


def test_existing_provenance_source_uri_is_not_overwritten(tmp_path: Path) -> None:
    source = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    src_uri = str(tmp_path / "source.npy")
    np.save(src_uri, source)
    pair = RegistrationPair(
        pair_id="pair-pre",
        source=LunarProduct(
            product_id="src-001",
            instrument="OHRC",
            raster_uri=src_uri,
            provenance=Provenance(source_uri="pds://original-product"),
        ),
        reference=LunarProduct(product_id="ref-001", instrument="LRO_NAC"),
    )
    result = preprocess(pair)
    assert result.source.provenance is not None
    assert result.source.provenance.source_uri == "pds://original-product"
    assert result.source.provenance.notes is not None
    assert src_uri in result.source.provenance.notes


def test_pipeline_integration(registration_pair: RegistrationPair) -> None:
    result = pipeline_preprocess(registration_pair)
    assert isinstance(result, RegistrationPair)
    assert result.pair_id == registration_pair.pair_id
    assert result.characterization == registration_pair.characterization


def test_multiband_cube_is_not_collapsed(tmp_path: Path) -> None:
    cube = np.stack(
        [np.array([[1.0, 2.0], [3.0, 4.0]]), np.array([[10.0, 20.0], [30.0, 40.0]])],
        axis=2,
    )
    pair = _pair(tmp_path, source=cube, reference=cube)
    result = preprocess_with_settings(pair, _full_range())
    out = _load(result.source.raster_uri)
    assert out.shape == (2, 2, 2)
    np.testing.assert_allclose(out[:, :, 0], (cube[:, :, 0] - 1.0) / 3.0)
    np.testing.assert_allclose(out[:, :, 1], (cube[:, :, 1] - 10.0) / 30.0)


def test_product_mask_does_not_treat_image_zeros_as_invalid(tmp_path: Path) -> None:
    source = np.array([[0.0, 2.0], [4.0, 6.0]], dtype=float)
    mask = np.array([[True, True], [True, False]])
    src_uri = str(tmp_path / "source.npy")
    mask_uri = str(tmp_path / "source_mask.npy")
    np.save(src_uri, source)
    np.save(mask_uri, mask)
    pair = RegistrationPair(
        pair_id="pair-pre",
        source=LunarProduct(
            product_id="src-001", instrument="OHRC", raster_uri=src_uri, mask_uri=mask_uri
        ),
        reference=LunarProduct(product_id="ref-001", instrument="LRO_NAC"),
    )
    result = preprocess_with_settings(pair, _full_range())
    out = _load(result.source.raster_uri)
    assert math.isnan(out[1, 1])
    assert np.isfinite(out[0, 0])
    np.testing.assert_allclose(out[0, 0], 0.0)

