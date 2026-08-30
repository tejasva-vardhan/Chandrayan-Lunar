"""Software raster handles for baseline registration.

SIH/product file formats are not frozen. This module reads and writes NumPy
``.npy`` arrays as an engineering handle so warping can be tested without
assuming PDS, GeoTIFF, or the official SIH dataset.

This is not an ingestion reader and not the export package.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ENGINEERING_RASTER_SUFFIX = ".npy"


def load_raster(uri: str) -> np.ndarray:
    path = Path(uri)
    if path.suffix.lower() != ENGINEERING_RASTER_SUFFIX:
        raise ValueError(
            "software-baseline raster encoding is NumPy .npy only; "
            f"got suffix={path.suffix!r} uri={uri}"
        )
    array = np.load(path)
    if array.ndim not in (2, 3):
        raise ValueError(f"raster must be 2D or 3D; got shape={array.shape}")
    return np.asarray(array, dtype=float)


def save_raster(uri: str, array: np.ndarray) -> str:
    path = Path(uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, array)
    return str(path)


def registered_uri_for(source_uri: str) -> str:
    source = Path(source_uri)
    return str(source.with_name(f"{source.stem}.registered{ENGINEERING_RASTER_SUFFIX}"))
