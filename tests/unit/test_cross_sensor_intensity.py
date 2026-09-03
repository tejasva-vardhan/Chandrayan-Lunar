"""Unit tests for cross-sensor CLAHE representation."""

from __future__ import annotations

import numpy as np

from src.representation._matching_view import build_representation_array
from src.representation.cross_sensor import REPRESENTATION_ID, build_cross_sensor_array


def test_cross_sensor_output_range_and_id(tmp_path) -> None:
    rng = np.random.default_rng(0)
    image = rng.random((64, 64), dtype=np.float32)
    out = build_cross_sensor_array(image)
    assert out.shape == image.shape
    assert out.dtype == np.float32
    assert float(out.min()) >= 0.0
    assert float(out.max()) <= 1.0
    assert REPRESENTATION_ID == "cross_sensor"


def test_cross_sensor_changes_appearance_vs_flat_stretch() -> None:
    # Low-contrast left half, high-contrast right half — CLAHE should lift
    # local contrast differently than global percentile stretch alone.
    image = np.zeros((64, 64), dtype=np.float32)
    image[:, :32] = 0.2 + 0.01 * np.linspace(0, 1, 64)[:, None]
    image[:, 32:] = 0.7 + 0.2 * np.linspace(0, 1, 64)[:, None]
    out = build_cross_sensor_array(image)
    assert not np.allclose(out, image)
    assert float(out[:, :32].std()) > float(image[:, :32].std())


def test_build_representation_array_routes_cross_sensor(tmp_path) -> None:
    path = tmp_path / "tile.npy"
    np.save(path, np.linspace(0, 1, 100, dtype=np.float32).reshape(10, 10))
    out = build_representation_array(str(path), "cross_sensor", stride=1)
    assert out.shape == (10, 10)
    assert out.dtype == np.float32
