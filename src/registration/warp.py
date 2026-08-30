"""Inverse-mapped bilinear warping. Engineering resampling, not sub-pixel refinement."""

from __future__ import annotations

import numpy as np

from src.registration.validation import invert_matrix

_HOMOGENEOUS_SCALE_FLOOR = 1e-12
# Inverse-mapped integer pixels can sit slightly outside [0, W-1] after DLT.
# Engineering float guard, not a scientific interpolation threshold.
_BOUNDS_EPS = 1e-6


def warp_to_grid(source: np.ndarray, matrix: np.ndarray, height: int, width: int) -> np.ndarray:
    """Resample source onto an output grid of shape (height, width[, bands]).

    matrix maps source pixel (x, y) to reference pixel (x', y') in the same
    tuple convention as ControlPoint / Correspondence (origin not interpreted).

    For each output pixel (x, y) on the reference grid:
        [u, v, w] = inverse(matrix) @ [x, y, 1]
        sample source at (u/w, v/w) with bilinear interpolation.

    Out of bounds or non-finite inverse scale → NaN. Coordinates within
    1e-6 of the inclusive pixel box [0, W-1] × [0, H-1] are treated as
    inside (engineering float guard after DLT inverse).
    Interpolation is bilinear. That is image resampling, not sub-pixel
    control-point refinement (D-006).

    Output is float64. Not a radiometric product. Not scientifically optimal.
    """

    inverse = invert_matrix(matrix)
    if inverse is None:
        raise ValueError("cannot warp with a non-invertible transformation")
    if height < 1 or width < 1:
        raise ValueError("output grid must be at least 1x1")

    columns, rows = np.meshgrid(np.arange(width, dtype=float), np.arange(height, dtype=float))
    homogeneous = np.stack([columns, rows, np.ones_like(columns)], axis=0).reshape(3, -1)
    mapped = inverse @ homogeneous
    scale = mapped[2]
    usable = np.abs(scale) > _HOMOGENEOUS_SCALE_FLOOR
    src_x = np.full(scale.shape, np.nan, dtype=float)
    src_y = np.full(scale.shape, np.nan, dtype=float)
    src_x[usable] = mapped[0, usable] / scale[usable]
    src_y[usable] = mapped[1, usable] / scale[usable]
    src_x = src_x.reshape(height, width)
    src_y = src_y.reshape(height, width)
    return _bilinear_sample(source, src_x, src_y)


def _bilinear_sample(source: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    if source.ndim == 2:
        return _bilinear_plane(source, x, y)
    if source.ndim == 3:
        bands = [
            _bilinear_plane(source[:, :, band], x, y) for band in range(source.shape[2])
        ]
        return np.stack(bands, axis=2)
    raise ValueError(f"source must be 2D or 3D; got shape={source.shape}")


def _bilinear_plane(plane: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    height, width = plane.shape
    sampled = np.full(x.shape, np.nan, dtype=float)
    inside = (
        np.isfinite(x)
        & np.isfinite(y)
        & (x >= -_BOUNDS_EPS)
        & (x <= width - 1 + _BOUNDS_EPS)
        & (y >= -_BOUNDS_EPS)
        & (y <= height - 1 + _BOUNDS_EPS)
    )
    if not np.any(inside):
        return sampled
    xs = np.clip(x[inside], 0.0, width - 1)
    ys = np.clip(y[inside], 0.0, height - 1)
    x0 = np.floor(xs).astype(int)
    y0 = np.floor(ys).astype(int)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    wx = xs - x0
    wy = ys - y0
    i00 = plane[y0, x0]
    i01 = plane[y0, x1]
    i10 = plane[y1, x0]
    i11 = plane[y1, x1]
    sampled[inside] = (
        i00 * (1.0 - wy) * (1.0 - wx)
        + i01 * (1.0 - wy) * wx
        + i10 * wy * (1.0 - wx)
        + i11 * wy * wx
    )
    return sampled
