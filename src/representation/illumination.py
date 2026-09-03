"""Illumination-normalization representation (engineering baseline).

SOFTWARE BASELINE only. This module does **not** establish that lunar
Sun-angle variation is solved. It does not use SPICE, incidence/azimuth
geometry, Chandrayaan-2 product sizes, GSD, or band counts.

Pipeline
--------
generic numeric array + optional product mask
        ↓
finite-value valid mask (image 0 remains valid)
        ↓
optional robust percentile intensity stretch
        ↓
optional nan-aware local z-score (relative contrast)
        ↓
optional robust stretch of finite outputs onto [output_low, output_high]

Invalid samples stay NaN. Output shape equals input shape. No resampling.

Invariance claims are limited to synthetic global affine brightness changes
on constructed arrays. Spatially complex photometric effects, terrain
shadowing, and cross-sensor radiometry are out of scope.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

from src.representation.illumination_settings import (
    IlluminationSettings,
    unvalidated_illumination_defaults,
)


def _finite_product_mask(product_mask: np.ndarray) -> np.ndarray:
    array = np.asarray(product_mask)
    if array.dtype == bool:
        return array
    return np.isfinite(array) & (array != 0)


def valid_mask(array: np.ndarray, product_mask: np.ndarray | None = None) -> np.ndarray:
    """True where the sample is finite and included by an aligned product mask.

    Image intensity 0 is valid. An unalignable product mask raises rather
    than being silently ignored.
    """

    valid = np.isfinite(array)
    if product_mask is None:
        return valid
    mask = _finite_product_mask(product_mask)
    if mask.shape == array.shape:
        return valid & mask
    if array.ndim == 3 and mask.ndim == 2 and mask.shape == array.shape[:2]:
        return valid & np.broadcast_to(mask[:, :, np.newaxis], array.shape)
    raise ValueError(
        "product mask shape does not match array: "
        f"mask={mask.shape}, array={array.shape}"
    )


def _stretch_plane(
    plane: np.ndarray,
    valid: np.ndarray,
    low_percentile: float,
    high_percentile: float,
    output_low: float,
    output_high: float,
    clip_to_output_range: bool,
) -> np.ndarray:
    out = np.full(plane.shape, np.nan, dtype=np.float64)
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
    scaled = (plane.astype(np.float64) - p_lo) / span
    mapped = output_low + scaled * (output_high - output_low)
    if clip_to_output_range:
        mapped = np.clip(mapped, output_low, output_high)
    out[valid] = mapped[valid]
    return out


def _percentile_stretch(
    array: np.ndarray,
    valid: np.ndarray,
    settings: IlluminationSettings,
) -> np.ndarray:
    if array.ndim == 2:
        return _stretch_plane(
            array,
            valid,
            settings.intensity_low_percentile,
            settings.intensity_high_percentile,
            settings.output_low,
            settings.output_high,
            settings.clip_to_output_range,
        )
    planes = [
        _stretch_plane(
            array[:, :, band],
            valid[:, :, band] if valid.ndim == 3 else valid,
            settings.intensity_low_percentile,
            settings.intensity_high_percentile,
            settings.output_low,
            settings.output_high,
            settings.clip_to_output_range,
        )
        for band in range(array.shape[2])
    ]
    return np.stack(planes, axis=2)


def _local_mean_std(
    plane: np.ndarray,
    valid: np.ndarray,
    window_size: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    valid_f = valid.astype(np.float64)
    filled = np.where(valid, plane.astype(np.float64), 0.0)
    area = float(window_size * window_size)
    sum_x = ndimage.uniform_filter(filled, size=window_size, mode="constant", cval=0.0) * area
    sum_x2 = (
        ndimage.uniform_filter(filled * filled, size=window_size, mode="constant", cval=0.0)
        * area
    )
    count = ndimage.uniform_filter(valid_f, size=window_size, mode="constant", cval=0.0) * area
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = sum_x / count
        variance = np.maximum(sum_x2 / count - mean * mean, 0.0)
        std = np.sqrt(variance)
    insufficient = count < 0.5
    mean = np.where(insufficient, np.nan, mean)
    std = np.where(insufficient, np.nan, std)
    return mean, std, count


def _local_contrast_plane(
    plane: np.ndarray,
    valid: np.ndarray,
    settings: IlluminationSettings,
) -> np.ndarray:
    out = np.full(plane.shape, np.nan, dtype=np.float64)
    if not np.any(valid):
        return out
    if settings.local_window_size == 1:
        out[valid] = plane[valid]
        return out

    mean, std, count = _local_mean_std(plane, valid, settings.local_window_size)
    midpoint = 0.5 * (settings.output_low + settings.output_high)
    usable = (
        valid
        & np.isfinite(mean)
        & np.isfinite(std)
        & (count >= settings.min_local_count)
        & (std > settings.min_local_std)
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        z_score = (plane.astype(np.float64) - mean) / std
    out[valid] = midpoint
    out[usable] = z_score[usable]
    return out


def _local_contrast(
    array: np.ndarray, valid: np.ndarray, settings: IlluminationSettings
) -> np.ndarray:
    if array.ndim == 2:
        return _local_contrast_plane(array, valid, settings)
    planes = [
        _local_contrast_plane(
            array[:, :, band],
            valid[:, :, band] if valid.ndim == 3 else valid,
            settings,
        )
        for band in range(array.shape[2])
    ]
    return np.stack(planes, axis=2)


def build_illumination_array(
    array: np.ndarray,
    product_mask: np.ndarray | None = None,
    settings: IlluminationSettings | None = None,
) -> np.ndarray:
    """Return an illumination-normalized float32 array.

    Parameters
    ----------
    array:
        Generic 2-D (H, W) or 3-D (H, W, C) numeric image. Band count is not
        assumed. The array is never resized.
    product_mask:
        Optional validity mask. bool True / numeric non-zero finite = valid.
        A 2-D mask may apply to every band of a 3-D array. Other mismatches
        raise ValueError.
    settings:
        IlluminationSettings. If None, uses unvalidated engineering defaults.

    Returns
    -------
    np.ndarray
        float32, same shape as ``array``. Invalid positions are NaN.
    """

    cfg = settings or unvalidated_illumination_defaults()
    source = np.asarray(array)
    if source.ndim not in (2, 3):
        raise ValueError(
            f"illumination representation requires a 2-D or 3-D array, got {source.ndim}D"
        )

    valid = valid_mask(source, product_mask)
    current = np.full(source.shape, np.nan, dtype=np.float64)
    current[valid] = source.astype(np.float64)[valid]

    if cfg.enable_robust_intensity:
        current = _percentile_stretch(current, valid, cfg)

    if cfg.enable_local_contrast:
        current = _local_contrast(current, np.isfinite(current) & valid, cfg)

    if cfg.enable_output_stretch:
        stretch_valid = np.isfinite(current) & valid
        current = _percentile_stretch(current, stretch_valid, cfg)

    out = np.full(source.shape, np.nan, dtype=np.float32)
    keep = np.isfinite(current) & valid
    out[keep] = current[keep].astype(np.float32)
    return out


__all__ = [
    "build_illumination_array",
    "valid_mask",
]
