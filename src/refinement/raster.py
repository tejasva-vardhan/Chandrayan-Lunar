"""Software raster handles for baseline refinement.

SIH/product file formats are not frozen. This module reads NumPy ``.npy``
arrays as an engineering handle so refinement can be tested without assuming
PDS, GeoTIFF, or the official SIH dataset.

This is the same software-raster convention used by baseline registration.
It is not an ingestion reader, not the export package, and not future SIH
ingestion. Refinement does not import ``src.registration`` (refinement runs
before registration in the frozen pipeline).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ENGINEERING_RASTER_SUFFIX = ".npy"

# Load outcomes. These are internal labels, not RegistrationResult quality_flags
# and not SIH evaluator vocabulary. The frozen refine_points return type cannot
# carry per-point flags, so both failure kinds preserve original coordinates.
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


def as_intensity(array: np.ndarray) -> np.ndarray | None:
    """Reduce a software raster to a 2D intensity field.

    2-D arrays are returned as float64. 3-D arrays are treated as (H, W, C)
    matching registration's warp convention and averaged over the last axis.

    Averaging bands is an ENGINEERING DEFAULT so the same-modality ZNCC
    baseline can run on multi-band .npy handles. It is not radiometric
    calibration and not a multimodal fusion method.
    """

    if array.ndim == 2:
        return np.asarray(array, dtype=float)
    if array.ndim == 3:
        if array.shape[0] < 1 or array.shape[1] < 1:
            return None
        return np.mean(np.asarray(array, dtype=float), axis=2)
    return None
