"""Discrete ZNCC peak location and quadratic continuous refinement.

SOFTWARE BASELINE peak interpolation. This is not a final scientific
sub-pixel estimator and not lunar accuracy (D-006).
"""

from __future__ import annotations

import math

import numpy as np

# Engineering floor on the second finite difference of the ZNCC peak.
# Below this, the 1-D parabola is treated as flat / undefined.
_CURVATURE_FLOOR = 1e-12


def discrete_peak_index(surface: np.ndarray) -> tuple[int, int] | None:
    """Return (row, col) of the maximum finite value, or None if none exist.

    numpy.nanargmax is deterministic (first maximum in C-order). That is a
    software tie-break, not a scientific peak-selection policy.
    """

    if surface.size == 0 or not np.any(np.isfinite(surface)):
        return None
    flat = int(np.nanargmax(surface))
    row, col = np.unravel_index(flat, surface.shape)
    return int(row), int(col)


def parabolic_offset(left: float, peak: float, right: float) -> float | None:
    """1-D quadratic interpolation of a discrete maximum.

    Samples are at x = -1, 0, +1. The vertex offset is

        delta = 0.5 * (left - right) / (left - 2*peak + right)

    This is the standard three-point parabolic interpolator used as an
    engineering sub-pixel peak estimator (e.g. around a correlation maximum).

    Returns None when:
    - any sample is non-finite
    - the second difference is not strictly concave-down
    - the vertex falls outside (-1, 1)  (numerically invalid for this stencil)
    """

    if not (math.isfinite(left) and math.isfinite(peak) and math.isfinite(right)):
        return None
    denom = left - 2.0 * peak + right
    if not math.isfinite(denom) or denom >= -_CURVATURE_FLOOR:
        return None
    offset = 0.5 * (left - right) / denom
    if not math.isfinite(offset) or abs(offset) >= 1.0:
        return None
    return float(offset)


def quadratic_offset_2d(neighborhood: np.ndarray) -> tuple[float, float] | None:
    """Least-squares 2-D quadratic vertex of a 3x3 neighborhood.

    Fit
        f(x, y) = A x^2 + B y^2 + C x y + D x + E y + F
    on x, y in {-1, 0, 1} with neighborhood[row, col] at (x=col-1, y=row-1).

    The vertex of that paraboloid is an engineering continuous-peak estimate.
    It is not a calibrated sub-pixel accuracy claim (D-006).

    Returns (delta_col, delta_row) in index units, or None when the fit is
    not a finite interior maximum.
    """

    if neighborhood.shape != (3, 3) or not np.all(np.isfinite(neighborhood)):
        return None
    ys, xs = np.mgrid[-1:2, -1:2]
    x = xs.ravel().astype(float)
    y = ys.ravel().astype(float)
    z = neighborhood.ravel().astype(float)
    design = np.column_stack((x * x, y * y, x * y, x, y, np.ones(9)))
    try:
        params, _, _, _ = np.linalg.lstsq(design, z, rcond=None)
    except np.linalg.LinAlgError:
        return None
    if params.size != 6 or not np.all(np.isfinite(params)):
        return None
    a, b, c, d, e, _constant = (float(v) for v in params)
    hessian = np.array([[2.0 * a, c], [c, 2.0 * b]], dtype=float)
    det = hessian[0, 0] * hessian[1, 1] - hessian[0, 1] * hessian[1, 0]
    if det <= _CURVATURE_FLOOR or hessian[0, 0] >= 0.0 or hessian[1, 1] >= 0.0:
        return None
    try:
        offset = np.linalg.solve(hessian, np.array([-d, -e], dtype=float))
    except np.linalg.LinAlgError:
        return None
    dx = float(offset[0])
    dy = float(offset[1])
    if not math.isfinite(dx) or not math.isfinite(dy) or abs(dx) >= 1.0 or abs(dy) >= 1.0:
        return None
    return dx, dy


def refine_peak_subpixel(
    surface: np.ndarray, peak_row: int, peak_col: int
) -> tuple[float, float] | None:
    """2-D quadratic offset of an interior discrete peak.

    The discrete peak must be strictly interior so a 3x3 neighborhood exists.
    A border peak is not interpolated: it may not be a true maximum of the
    underlying continuous surface.

    Returns (delta_col, delta_row) to add to the integer peak, or None.
    """

    rows, cols = surface.shape
    if peak_row <= 0 or peak_row >= rows - 1 or peak_col <= 0 or peak_col >= cols - 1:
        return None
    neighborhood = surface[peak_row - 1 : peak_row + 2, peak_col - 1 : peak_col + 2]
    return quadratic_offset_2d(neighborhood)
