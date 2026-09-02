"""Calibrated-intensity representation.

Loads the image from the LunarProduct raster_uri and returns a float32 array
in [0, 1] after percentile-stretch normalisation.

This is the simplest baseline representation. It preserves absolute radiometric
information and lets the matcher operate on intensity directly. Use it for
same-modality, similar-illumination pairs (easy/normal difficulty).

Illumination caveat: percentile stretch reduces the impact of saturated/dark
extremes but does not compensate for large Sun-angle differences. For difficult
illumination pairs, prefer gradient or structural representations.
"""

from __future__ import annotations

import numpy as np

from src.representation._loader import load_array


def build_intensity(raster_uri: str, *, lo_pct: float = 2.0, hi_pct: float = 98.0) -> np.ndarray:
    """Load image and return percentile-stretched float32 array in [0, 1]."""
    return build_intensity_array(load_array(raster_uri), lo_pct=lo_pct, hi_pct=hi_pct)


def build_intensity_array(
    img: np.ndarray,
    *,
    lo_pct: float = 2.0,
    hi_pct: float = 98.0,
) -> np.ndarray:
    """Load image and return percentile-stretched float32 array in [0, 1].

    Parameters
    ----------
    raster_uri:
        Filesystem path or URI to the single-band raster file.
    lo_pct, hi_pct:
        Percentile range used for contrast stretching. Defaults (2, 98) clip
        the darkest and brightest 2 % of pixels to reduce sensor saturation
        artefacts. Do not tune these without measuring the effect on matching.

    Returns
    -------
    np.ndarray
        float32 array, shape (H, W), values in [0, 1].
    """
    lo = float(np.percentile(img, lo_pct))
    hi = float(np.percentile(img, hi_pct))

    if hi <= lo:
        # Flat image — return as-is rather than divide by zero.
        return img

    stretched = (img - lo) / (hi - lo)
    return np.clip(stretched, 0.0, 1.0).astype(np.float32)
