"""Software raster handles for baseline preprocessing.

SIH/product file formats are not frozen. This module reads and writes NumPy
``.npy`` arrays as an engineering handle so preprocessing can be tested
without assuming PDS, GeoTIFF, or the official SIH dataset.

This is the same software-raster convention used by baseline refinement
and registration. It is not an ingestion reader and not the export package.
Preprocessing does not import ``src.registration`` or ``src.refinement``
(those stages run later).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ENGINEERING_RASTER_SUFFIX = ".npy"

RASTER_UNAVAILABLE = "raster_unavailable"
RASTER_UNSUPPORTED = "unsupported_raster_encoding"


def load_software_raster(uri: str | None) -> tuple[np.ndarray | None, str | None]:
    """Load a software-baseline .npy raster, or explain why it cannot be used.

    Returns (array, None) on success. Returns (None, reason) on failure.
    Reasons are engineering labels only.
    """

    if uri is None or uri == "":
        return None, RASTER_UNAVAILABLE
    path = Path(uri)
    if path.suffix.lower() != ENGINEERING_RASTER_SUFFIX:
        return None, RASTER_UNSUPPORTED
    try:
        array = np.load(path)
    except (OSError, ValueError):
        return None, RASTER_UNAVAILABLE
    if array.ndim not in (2, 3) or array.size == 0:
        return None, RASTER_UNSUPPORTED
    return np.asarray(array, dtype=float), None


def save_software_raster(uri: str, array: np.ndarray) -> str | None:
    """Write a float array as .npy. Returns the path, or None on failure."""

    path = Path(uri)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, np.asarray(array, dtype=float))
    except OSError:
        return None
    return str(path)


def preprocessed_uri_for(source_uri: str) -> str:
    """Derived raster path next to the original. Does not overwrite it."""

    source = Path(source_uri)
    return str(source.with_name(f"{source.stem}.preprocessed{ENGINEERING_RASTER_SUFFIX}"))
