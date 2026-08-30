"""Replaceable residual definition for verification.

The Interface Freeze does not define Correspondence.residual unit or formula.
This module implements one software residual so inliers can be assigned. It is
not a frozen scientific residual and is not a physical (metre) error.
"""

from __future__ import annotations

import numpy as np

# Numerical floor for the homogeneous scale. Not an inlier threshold.
_HOMOGENEOUS_SCALE_FLOOR = 1e-12


def image_space_transfer_error(
    source_xy: np.ndarray, reference_xy: np.ndarray, matrix: np.ndarray
) -> np.ndarray:
    """Euclidean distance in reference image coordinates after mapping source_xy.

    For each correspondence i:
        [u, v, w]^T = matrix @ [x_source, y_source, 1]^T
        predicted_reference = (u/w, v/w) when |w| is above a numerical floor
        residual_i = hypot(reference_x - predicted_x, reference_y - predicted_y)

    Conventions:
    - Inputs are the same pixel tuples stored on Correspondence (origin centre vs
      corner is owned by ingestion/geometry and is not interpreted here).
    - The result is in those pixel units, not metres, not GSD-scaled.
    - matrix is 3x3. Affine baselines use last row [0, 0, 1].
    - If |w| is below the numerical floor, that residual is +inf (not an inlier).

    Replace this function if a later decision freezes a different residual.
    """

    if source_xy.shape != reference_xy.shape or source_xy.ndim != 2 or source_xy.shape[1] != 2:
        raise ValueError("source_xy and reference_xy must have shape (n, 2)")
    if matrix.shape != (3, 3):
        raise ValueError("matrix must be 3x3")

    n = source_xy.shape[0]
    ones = np.ones((n, 1), dtype=float)
    homogeneous = np.concatenate([source_xy.astype(float, copy=False), ones], axis=1)
    mapped = (matrix @ homogeneous.T).T
    scale = mapped[:, 2]
    predicted = np.full((n, 2), np.inf, dtype=float)
    usable = np.abs(scale) > _HOMOGENEOUS_SCALE_FLOOR
    predicted[usable] = mapped[usable, :2] / scale[usable, np.newaxis]
    delta = predicted - reference_xy.astype(float, copy=False)
    return np.sqrt(np.sum(delta * delta, axis=1))
