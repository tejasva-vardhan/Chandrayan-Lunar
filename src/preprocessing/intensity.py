"""Robust finite-sample percentile intensity normalization.

ENGINEERING IMAGE-NORMALIZATION. Not physical radiance. Not a claim that
OHRC and IIRS become radiometrically equivalent.

Input domain
    Finite samples of the current raster, in whatever numeric units the
    software .npy handle stores. NaN/Inf never enter percentile math.

Output domain
    Approximately [output_low, output_high], ENGINEERING DEFAULT [0, 1],
    with invalid samples remaining NaN. Unclipped tails may fall slightly
    outside that interval.

Formula (per 2-D plane)
    p_lo = percentile(finite samples, low)
    p_hi = percentile(finite samples, high)
    If no finite samples: all-NaN output (do not fabricate).
    If p_hi == p_lo (constant valid region): map valid samples to the
    midpoint (output_low + output_high) / 2.
    Else: y = (x - p_lo) / (p_hi - p_lo)
          y = output_low + y * (output_high - output_low)
          optional clip to [output_low, output_high]

Clipping
    Off by default. When enabled, values outside [p_lo, p_hi] snap to the
    output endpoints, which flattens tails and can move argmax. Invalid
    pixels are never clipped to 0; they stay NaN.

3-D rasters
    Each band is stretched independently so an IIRS cube is not collapsed
    to grayscale. That is not spectral calibration.
"""

from __future__ import annotations

import math

import numpy as np


def _stretch_plane(
    plane: np.ndarray,
    valid: np.ndarray,
    low_percentile: float,
    high_percentile: float,
    output_low: float,
    output_high: float,
    clip_to_output_range: bool,
) -> np.ndarray:
    out = np.full(plane.shape, np.nan, dtype=float)
    samples = plane[valid]
    if samples.size == 0:
        return out
    p_lo = float(np.percentile(samples, low_percentile))
    p_hi = float(np.percentile(samples, high_percentile))
    if not math.isfinite(p_lo) or not math.isfinite(p_hi):
        return out
    midpoint = 0.5 * (output_low + output_high)
    span = p_hi - p_lo
    if span == 0.0:
        out[valid] = midpoint
        return out
    scaled = (plane.astype(float) - p_lo) / span
    mapped = output_low + scaled * (output_high - output_low)
    if clip_to_output_range:
        mapped = np.clip(mapped, output_low, output_high)
    out[valid] = mapped[valid]
    return out


def percentile_stretch(
    array: np.ndarray,
    valid: np.ndarray,
    *,
    low_percentile: float,
    high_percentile: float,
    output_low: float,
    output_high: float,
    clip_to_output_range: bool = False,
) -> np.ndarray:
    """Percentile-stretch finite samples. Invalid positions stay NaN."""

    if array.ndim == 2:
        return _stretch_plane(
            array,
            valid,
            low_percentile,
            high_percentile,
            output_low,
            output_high,
            clip_to_output_range,
        )
    planes = [
        _stretch_plane(
            array[:, :, band],
            valid[:, :, band] if valid.ndim == 3 else valid,
            low_percentile,
            high_percentile,
            output_low,
            output_high,
            clip_to_output_range,
        )
        for band in range(array.shape[2])
    ]
    return np.stack(planes, axis=2)
