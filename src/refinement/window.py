"""Local neighborhood extraction for sub-pixel refinement.

Coordinate convention (same as Correspondence / ControlPoint tuples):
    (x, y) = (column, row). Array index is [y, x].
Integer (x, y) addresses that sample on the raster grid.

Pixel-centre versus pixel-corner origin is not interpreted (Interface Freeze
v1). This module does not add 0.5, wrap, or pad.
"""

from __future__ import annotations

import math

import numpy as np

# Engineering linear-algebra floor for "has structure" checks. Not a scientific
# texture threshold.
_VARIANCE_FLOOR = 1e-12


def extract_window(
    image: np.ndarray, center_x: float, center_y: float, radius: int
) -> np.ndarray | None:
    """Sample a (2*radius+1)^2 window centered at (center_x, center_y).

    Each window sample is bilinearly interpolated from the intensity field.
    At integer centres this equals a crop of the source pixels.

    Returns None when the required sample grid would leave the inclusive
    pixel box [0, W-1] x [0, H-1]. Out-of-bounds windows are not padded,
    wrapped, or filled with zeros (that would fabricate correlation).
    Interior NaN/Inf samples stay non-finite and are handled by the caller.
    """

    if image.ndim != 2:
        return None
    if not math.isfinite(center_x) or not math.isfinite(center_y):
        return None
    height, width = image.shape
    if height < 1 or width < 1:
        return None
    xs = center_x + np.arange(-radius, radius + 1, dtype=float)
    ys = center_y + np.arange(-radius, radius + 1, dtype=float)
    if xs[0] < 0.0 or ys[0] < 0.0 or xs[-1] > width - 1 or ys[-1] > height - 1:
        return None
    grid_x, grid_y = np.meshgrid(xs, ys)
    return bilinear_sample(image, grid_x, grid_y)


def extract_search_stack(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    window_radius: int,
    search_radius: int,
) -> np.ndarray | None:
    """Sample every integer-lag window around a coarse reference location.

    Returns an array of shape (2S+1, 2S+1, 2W+1, 2W+1) where the first two
    axes are lags (dv, du) with origin at (search_radius, search_radius), or
    None if the full search neighborhood would leave the usable image area.

    Boundary policy: the entire search halo must lie inside [0, W-1] x [0, H-1].
    Partial halos are not used (a peak on a truncated surface is not a
    confirmed interior maximum).
    """

    if image.ndim != 2:
        return None
    if not math.isfinite(center_x) or not math.isfinite(center_y):
        return None
    height, width = image.shape
    extent = window_radius + search_radius
    xs = center_x + np.arange(-extent, extent + 1, dtype=float)
    ys = center_y + np.arange(-extent, extent + 1, dtype=float)
    if xs[0] < 0.0 or ys[0] < 0.0 or xs[-1] > width - 1 or ys[-1] > height - 1:
        return None
    grid_x, grid_y = np.meshgrid(xs, ys)
    sampled = bilinear_sample(image, grid_x, grid_y)
    size = 2 * window_radius + 1
    n_lags = 2 * search_radius + 1
    stack = np.empty((n_lags, n_lags, size, size), dtype=float)
    for dv in range(n_lags):
        for du in range(n_lags):
            stack[dv, du] = sampled[dv : dv + size, du : du + size]
    return stack


def bilinear_sample(plane: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear sample of a 2-D plane at coordinates (x, y).

    Samples outside [0, W-1] x [0, H-1], or whose 2x2 neighborhood contains a
    non-finite value, are NaN. This is image sampling, not sub-pixel peak
    estimation.
    """

    height, width = plane.shape
    sampled = np.full(np.shape(x), np.nan, dtype=float)
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    inside = (
        np.isfinite(x_arr)
        & np.isfinite(y_arr)
        & (x_arr >= 0.0)
        & (x_arr <= width - 1)
        & (y_arr >= 0.0)
        & (y_arr <= height - 1)
    )
    if not np.any(inside):
        return sampled
    xs = x_arr[inside]
    ys = y_arr[inside]
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
    finite_neighborhood = (
        np.isfinite(i00) & np.isfinite(i01) & np.isfinite(i10) & np.isfinite(i11)
    )
    placed = np.full(xs.shape, np.nan, dtype=float)
    if np.any(finite_neighborhood):
        wxf = wx[finite_neighborhood]
        wyf = wy[finite_neighborhood]
        placed[finite_neighborhood] = (
            i00[finite_neighborhood] * (1.0 - wyf) * (1.0 - wxf)
            + i01[finite_neighborhood] * (1.0 - wyf) * wxf
            + i10[finite_neighborhood] * wyf * (1.0 - wxf)
            + i11[finite_neighborhood] * wyf * wxf
        )
    sampled[inside] = placed
    return sampled


def has_intensity_structure(window: np.ndarray, min_valid: int) -> bool:
    """True when the window has enough finite pixels and non-zero variance."""

    finite = window[np.isfinite(window)]
    if finite.size < min_valid:
        return False
    centered = finite - finite.mean()
    return bool(np.dot(centered, centered) > _VARIANCE_FLOOR)
