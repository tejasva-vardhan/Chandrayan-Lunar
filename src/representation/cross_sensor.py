"""Cross-sensor optical appearance normalisation.

OHRC (Chandrayaan-2 calibrated intensity) and LROC NAC (Scaled I/F) are both
single-band optical products, but they differ in radiometric units, dynamic
range, and acquisition conditions. This module does **not** claim hyperspectral
or OHRC/TMC/IIRS multi-modal support.

Pipeline: percentile stretch (same as intensity) then OpenCV CLAHE so each
sensor's matching view has locally adaptive contrast before SIFT. No new
dependencies; no learned models.
"""

from __future__ import annotations

import cv2
import numpy as np

from src.representation.intensity import build_intensity_array

REPRESENTATION_ID = "cross_sensor"
DEFAULT_CLAHE_CLIP_LIMIT = 2.0
DEFAULT_CLAHE_TILE_GRID = (8, 8)


def build_cross_sensor_array(
    img: np.ndarray,
    *,
    lo_pct: float = 2.0,
    hi_pct: float = 98.0,
    clip_limit: float = DEFAULT_CLAHE_CLIP_LIMIT,
    tile_grid: tuple[int, int] = DEFAULT_CLAHE_TILE_GRID,
) -> np.ndarray:
    """Return float32 [0, 1] cross-sensor-normalised intensity."""
    stretched = build_intensity_array(img, lo_pct=lo_pct, hi_pct=hi_pct)
    if stretched.size == 0:
        return stretched.astype(np.float32)
    u8 = np.clip(np.rint(stretched * 255.0), 0, 255).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=tuple(tile_grid))
    equalised = clahe.apply(u8)
    return (equalised.astype(np.float32) / 255.0).astype(np.float32)


__all__ = [
    "DEFAULT_CLAHE_CLIP_LIMIT",
    "DEFAULT_CLAHE_TILE_GRID",
    "REPRESENTATION_ID",
    "build_cross_sensor_array",
]
