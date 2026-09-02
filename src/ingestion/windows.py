"""Memory-mapped window access for ingested software rasters.

These helpers read a rectangular window from a ``.npy`` handle without
loading the full array into Python RAM. They do not run matching or
registration.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.models.lunar_product import LunarProduct


def mmap_product_array(uri: str) -> np.ndarray:
    """Memory-map a software ``.npy`` raster or mask."""

    if not uri:
        raise ValueError("raster/mask uri is empty")
    path = Path(uri)
    if path.suffix.lower() != ".npy":
        raise ValueError(f"window access requires a .npy handle, got {path.suffix!r}")
    if not path.exists():
        raise FileNotFoundError(f"raster/mask uri does not exist: {path}")
    try:
        array = np.load(path, mmap_mode="r")
    except (OSError, ValueError) as exc:
        raise ValueError(f"could not memory-map {path}") from exc
    if array.ndim != 2:
        raise ValueError(f"window access requires a 2-D array, got shape {array.shape}")
    return array


def read_product_window(
    uri: str,
    row: int,
    col: int,
    height: int,
    width: int,
) -> np.ndarray:
    """Copy one rectangular window from a memory-mapped ``.npy`` handle."""

    if height <= 0 or width <= 0:
        raise ValueError("window height and width must be positive")
    if row < 0 or col < 0:
        raise ValueError("window origin must be non-negative")

    array = mmap_product_array(uri)
    row_end = row + height
    col_end = col + width
    if row_end > array.shape[0] or col_end > array.shape[1]:
        raise ValueError(
            "window exceeds raster bounds: "
            f"requested=({row}:{row_end}, {col}:{col_end}) shape={array.shape}"
        )
    return np.array(array[row:row_end, col:col_end], copy=True)


def read_lunar_product_window(
    product: LunarProduct,
    row: int,
    col: int,
    height: int,
    width: int,
) -> np.ndarray:
    """Read a window from an ingested product's raster handle."""

    if product.raster_uri is None:
        raise ValueError(f"product {product.product_id!r} has no raster_uri")
    return read_product_window(product.raster_uri, row, col, height, width)
