"""Synthetic registration tests. Software validation only — not lunar accuracy."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.models import ControlPoint, CorrespondenceSet, LunarProduct, RegistrationPair
from src.registration import register

pytestmark = pytest.mark.scientific


def _pair(tmp_path: Path, source: np.ndarray, reference: np.ndarray) -> RegistrationPair:
    source_uri = str(tmp_path / "source.npy")
    reference_uri = str(tmp_path / "reference.npy")
    np.save(source_uri, source)
    np.save(reference_uri, reference)
    return RegistrationPair(
        pair_id="synthetic-reg",
        source=LunarProduct(product_id="src", instrument="OHRC", raster_uri=source_uri),
        reference=LunarProduct(
            product_id="ref", instrument="LRO_NAC", raster_uri=reference_uri
        ),
    )


def _empty_matches(pair: RegistrationPair) -> CorrespondenceSet:
    return CorrespondenceSet(pair_id=pair.pair_id, matcher_id="synthetic-generator")


def _index_image(height: int, width: int) -> np.ndarray:
    rows = np.arange(height, dtype=float)[:, None]
    cols = np.arange(width, dtype=float)[None, :]
    return rows * width + cols


def _identity_points(width: int, height: int) -> list[ControlPoint]:
    xmax = float(width - 1)
    ymax = float(height - 1)
    return [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0)),
        ControlPoint(source_xy=(xmax, 0.0), reference_xy=(xmax, 0.0)),
        ControlPoint(source_xy=(0.0, ymax), reference_xy=(0.0, ymax)),
        ControlPoint(source_xy=(xmax, ymax), reference_xy=(xmax, ymax)),
        ControlPoint(source_xy=(xmax / 2.0, ymax / 2.0), reference_xy=(xmax / 2.0, ymax / 2.0)),
    ]


def test_synthetic_identity_warp(tmp_path: Path) -> None:
    # Synthetic generating model (TEST ONLY): identity map. Not a lunar model.
    image = _index_image(24, 20)
    pair = _pair(tmp_path, image, image)
    result = register(pair, _identity_points(20, 24), _empty_matches(pair))
    assert result.transformation is not None
    warped = np.load(result.registered_source_uri)
    np.testing.assert_allclose(warped, image, atol=1e-5)


def test_synthetic_known_translation_warp(tmp_path: Path) -> None:
    # Synthetic generating model (TEST ONLY): x' = x + 3, y' = y.
    height, width = 20, 24
    image = _index_image(height, width)
    pair = _pair(tmp_path, image, image)
    shift = 3.0
    points = [
        ControlPoint(source_xy=(x, y), reference_xy=(x + shift, y))
        for x, y in ((2.0, 2.0), (18.0, 2.0), (2.0, 16.0), (18.0, 16.0), (8.0, 10.0))
    ]
    result = register(pair, points, _empty_matches(pair))
    assert result.transformation is not None
    warped = np.load(result.registered_source_uri)
    assert warped.shape == (height, width)
    interior = warped[:, 3:]
    expected = image[:, : width - 3]
    finite = np.isfinite(interior)
    assert np.all(finite)
    np.testing.assert_allclose(interior[finite], expected[finite], atol=1e-4)
    assert np.all(np.isnan(warped[:, :3]))
