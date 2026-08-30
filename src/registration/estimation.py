"""Control-point filtering and transform estimation. No matching or verification."""

from __future__ import annotations

import math

import numpy as np

from src.models.registration_result import ControlPoint
from src.registration.models import TransformModel


def eligible_control_points(points: list[ControlPoint]) -> tuple[ControlPoint, ...]:
    """Finite unique (source_xy, reference_xy); first occurrence kept."""

    selected: list[ControlPoint] = []
    seen: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    for item in points:
        if not _finite_xy(item.source_xy) or not _finite_xy(item.reference_xy):
            continue
        key = (item.source_xy, item.reference_xy)
        if key in seen:
            continue
        seen.add(key)
        selected.append(item)
    return tuple(selected)


def estimate_matrix(
    points: tuple[ControlPoint, ...], model: TransformModel
) -> np.ndarray | None:
    """Least-squares fit of the selected model on all eligible control points.

    RANSAC is not repeated here; control points are assumed already selected.
    """

    if len(points) < model.min_samples:
        return None
    source = np.array([item.source_xy for item in points], dtype=float)
    reference = np.array([item.reference_xy for item in points], dtype=float)
    return model.fit(source, reference)


def _finite_xy(xy: tuple[float, float]) -> bool:
    return math.isfinite(xy[0]) and math.isfinite(xy[1])
