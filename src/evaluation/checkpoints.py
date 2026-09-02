"""Independent checkpoint evaluation for the software baseline.

Checkpoints are supplied outside the frozen pipeline because the canonical
models intentionally have no ground-truth field.  They must not duplicate
fit correspondences or selected control points.  This prevents the evaluator
from relabelling fit residuals as independent evidence, but it does not prove
the supplied coordinates are physical lunar ground truth.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from src.models.registration_result import RegistrationResult


@dataclass(frozen=True, slots=True)
class EvaluationCheckpoint:
    """A held-out source/reference pixel-coordinate observation."""

    checkpoint_id: str
    source_xy: tuple[float, float]
    reference_xy: tuple[float, float]


def independent_checkpoint_residuals(
    result: RegistrationResult,
    checkpoints: Iterable[EvaluationCheckpoint],
) -> list[float] | None:
    """Return residuals for held-out checkpoints, or None when unavailable.

    The baseline can evaluate only an explicit 3x3 transform matrix.  Unknown,
    malformed, non-finite, or overlapping checkpoint populations fail closed.
    """

    matrix = _matrix_from_result(result)
    if matrix is None:
        return None

    checkpoint_list = list(checkpoints)
    if not checkpoint_list or _overlaps_fit_population(result, checkpoint_list):
        return None

    residuals: list[float] = []
    for checkpoint in checkpoint_list:
        if not checkpoint.checkpoint_id or not _finite_xy(checkpoint.source_xy):
            return None
        if not _finite_xy(checkpoint.reference_xy):
            return None
        mapped = matrix @ np.array([*checkpoint.source_xy, 1.0], dtype=float)
        if not math.isfinite(float(mapped[2])) or abs(float(mapped[2])) <= 1e-12:
            return None
        predicted = mapped[:2] / mapped[2]
        residual = float(np.linalg.norm(predicted - np.asarray(checkpoint.reference_xy)))
        if not math.isfinite(residual):
            return None
        residuals.append(residual)
    return residuals


def _matrix_from_result(result: RegistrationResult) -> np.ndarray | None:
    if result.transformation is None:
        return None
    raw_matrix = result.transformation.parameters.get("matrix")
    try:
        matrix = np.asarray(raw_matrix, dtype=float)
    except (TypeError, ValueError):
        return None
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        return None
    return matrix


def _overlaps_fit_population(
    result: RegistrationResult, checkpoints: list[EvaluationCheckpoint]) -> bool:
    fit_pairs = {
        (item.source_xy, item.reference_xy)
        for item in (result.correspondences.matches if result.correspondences else [])
    }
    fit_pairs.update((item.source_xy, item.reference_xy) for item in result.control_points)
    return any((item.source_xy, item.reference_xy) in fit_pairs for item in checkpoints)


def _finite_xy(value: tuple[float, float]) -> bool:
    return math.isfinite(value[0]) and math.isfinite(value[1])
