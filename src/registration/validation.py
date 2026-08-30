"""Engineering validation of a fitted 3x3 map. Not scientific thresholds."""

from __future__ import annotations

import numpy as np

# Determinant / invertibility floor. Engineering numerical safeguard, not SIH.
_DET_FLOOR = 1e-12
_HOMOGENEOUS_SCALE_FLOOR = 1e-12


def validate_matrix(matrix: np.ndarray) -> np.ndarray | None:
    """Return the matrix if it is finite and invertible; otherwise None."""

    if matrix.shape != (3, 3):
        return None
    if not np.all(np.isfinite(matrix)):
        return None
    if float(np.linalg.norm(matrix)) < _DET_FLOOR:
        return None
    det = float(np.linalg.det(matrix))
    if abs(det) < _DET_FLOOR:
        return None
    try:
        inverse = np.linalg.inv(matrix)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(inverse)):
        return None
    if float(np.max(np.abs(inverse[2, :]))) < _HOMOGENEOUS_SCALE_FLOOR:
        return None
    return matrix


def invert_matrix(matrix: np.ndarray) -> np.ndarray | None:
    validated = validate_matrix(matrix)
    if validated is None:
        return None
    try:
        inverse = np.linalg.inv(validated)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(inverse)):
        return None
    return inverse
