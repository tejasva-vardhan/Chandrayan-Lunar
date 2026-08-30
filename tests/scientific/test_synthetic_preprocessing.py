"""Synthetic preprocessing tests. Software validation only — not lunar accuracy.

Constructed arrays check finite masking, percentile stretch, and structure
preservation. They are not Chandrayaan-2 results and are not SIH evidence
(D-011, D-012).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.models import LunarProduct, PairCharacterization, RegistrationPair
from src.preprocessing import (
    preprocess,
    preprocess_with_settings,
    unvalidated_software_defaults,
)
from src.preprocessing.raster import load_software_raster
from src.preprocessing.settings import PreprocessingSettings

pytestmark = pytest.mark.scientific


def _settings(**overrides: object) -> PreprocessingSettings:
    base = unvalidated_software_defaults()
    values = {field: getattr(base, field) for field in base.__dataclass_fields__}
    values.update(overrides)
    return PreprocessingSettings(**values)  # type: ignore[arg-type]


def _pair(tmp_path: Path, source: np.ndarray, reference: np.ndarray) -> RegistrationPair:
    source_uri = str(tmp_path / "source.npy")
    reference_uri = str(tmp_path / "reference.npy")
    np.save(source_uri, source)
    np.save(reference_uri, reference)
    return RegistrationPair(
        pair_id="synthetic-pre",
        source=LunarProduct(product_id="src", instrument="OHRC", raster_uri=source_uri),
        reference=LunarProduct(
            product_id="ref", instrument="LRO_NAC", raster_uri=reference_uri
        ),
    )


def _load(uri: str | None) -> np.ndarray:
    array, error = load_software_raster(uri)
    assert error is None
    assert array is not None
    return array


def test_synthetic_linear_stretch_matches_closed_form(tmp_path: Path) -> None:
    # TEST ONLY constructed DN-like values. Not a lunar radiometric product.
    source = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=float)
    pair = _pair(tmp_path, source, source)
    result = preprocess_with_settings(
        pair,
        _settings(intensity_low_percentile=0.0, intensity_high_percentile=100.0),
    )
    expected = (source - 10.0) / 30.0
    np.testing.assert_allclose(_load(result.source.raster_uri), expected)


def test_synthetic_gaussian_peak_location_is_preserved(tmp_path: Path) -> None:
    y, x = np.mgrid[0:32, 0:32]
    blob = np.exp(-((x - 19.0) ** 2 + (y - 11.0) ** 2) / (2 * 3.0**2))
    pair = _pair(tmp_path, blob, blob)
    result = preprocess(pair)
    out = _load(result.source.raster_uri)
    assert np.unravel_index(int(np.argmax(blob)), blob.shape) == np.unravel_index(
        int(np.nanargmax(out)), out.shape
    )
    assert out.shape == blob.shape
    assert np.all(np.isfinite(out))


def test_synthetic_invalid_pixels_stay_invalid(tmp_path: Path) -> None:
    raster = np.array([[0.0, 1.0, math.nan], [2.0, math.inf, 3.0]], dtype=float)
    pair = _pair(tmp_path, raster, np.ones_like(raster))
    result = preprocess_with_settings(
        pair,
        _settings(intensity_low_percentile=0.0, intensity_high_percentile=100.0),
    )
    out = _load(result.source.raster_uri)
    assert math.isnan(out[0, 2])
    assert math.isnan(out[1, 1])
    assert np.isfinite(out[0, 0])
    # Zero intensity is valid and participates in the stretch.
    assert out[0, 0] == pytest.approx(0.0)


def test_synthetic_gsd_ratio_does_not_resize(tmp_path: Path) -> None:
    source = np.arange(16, dtype=float).reshape(4, 4)
    reference = np.arange(36, dtype=float).reshape(6, 6)
    pair = _pair(tmp_path, source, reference)
    pair = pair.model_copy(update={"characterization": PairCharacterization(gsd_ratio=3.0)})
    result = preprocess_with_settings(
        pair,
        _settings(enable_scale_normalization=True, enable_intensity_normalization=False),
    )
    assert _load(result.source.raster_uri).shape == (4, 4)
    assert _load(result.reference.raster_uri).shape == (6, 6)
    np.testing.assert_allclose(_load(result.source.raster_uri), source)
