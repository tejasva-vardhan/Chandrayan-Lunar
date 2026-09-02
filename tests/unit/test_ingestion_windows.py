"""Unit tests for memory-mapped ingestion window access."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.ingestion.windows import mmap_product_array, read_product_window
from src.models import LunarProduct
from src.models.common import ImageDimensions


def test_read_product_window_does_not_require_full_copy(tmp_path: Path) -> None:
    raster = np.arange(200, dtype=np.int16).reshape(10, 20)
    path = tmp_path / "strip.npy"
    np.save(path, raster)

    mapped = mmap_product_array(str(path))
    window = read_product_window(str(path), row=2, col=4, height=3, width=5)

    assert isinstance(mapped, np.memmap)
    assert window.shape == (3, 5)
    assert np.array_equal(window, raster[2:5, 4:9])
    assert window.nbytes == 3 * 5 * raster.dtype.itemsize
    assert window.nbytes < raster.nbytes


def test_read_product_window_rejects_out_of_bounds(tmp_path: Path) -> None:
    path = tmp_path / "small.npy"
    np.save(path, np.zeros((4, 4), dtype=np.uint8))

    with pytest.raises(ValueError, match="exceeds raster bounds"):
        read_product_window(str(path), row=2, col=2, height=4, width=4)


def test_lunar_product_window_requires_raster_uri() -> None:
    product = LunarProduct(
        product_id="no-raster",
        instrument="OHRC",
        dimensions=ImageDimensions(width_px=8, height_px=8),
    )
    from src.ingestion.windows import read_lunar_product_window

    with pytest.raises(ValueError, match="no raster_uri"):
        read_lunar_product_window(product, 0, 0, 1, 1)
