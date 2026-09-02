"""Matcher-comparison metrics for EXP-001.

These are experiment-layer measurements. They do not change
``src.evaluation``, and the EXP-000 metric definitions are reused unchanged
wherever they already answer the question.

Two additions are needed for a matcher comparison that EXP-000 did not need:

``verified_match_coverage``
    EXP-000 reports coverage of the *selected control points*. Control-point
    selection caps one point per grid cell, so its coverage is partly a
    property of the selection grid rather than of the matcher. A matcher
    comparison also needs the spread of the verified correspondences
    themselves, before selection. The formula is deliberately the same
    bounding-box-area fraction ``src.evaluation.metrics`` uses, so the two
    numbers are directly comparable.

``occupancy``
    Bounding-box area says nothing about clustering: four points at the
    corners of an image and four thousand points at those same corners score
    identically. Occupancy counts how many cells of the same 8x8 grid used by
    control-point selection contain at least one verified match. It separates
    "spread out" from "spread out and dense".

``inliers_above_model_minimum``
    The single most important number in this experiment. A projective fit
    needs four points. When RANSAC returns exactly four inliers, the
    consensus set is the minimal sample itself and *no* correspondence
    corroborated it, so the fit is unfalsifiable. Verified counts must be
    read relative to that floor, not against zero.
"""

from __future__ import annotations

import math
from typing import Any

from src.models.correspondence_set import Correspondence
from src.models.registration_pair import RegistrationPair

_INLIER_STATUS = "inlier"


def verified_matches(matches: list[Correspondence]) -> list[Correspondence]:
    return [item for item in matches if item.status == _INLIER_STATUS]


def status_counts(matches: list[Correspondence]) -> dict[str, int]:
    """Count every correspondence status present, including zero-count states."""

    counts = {"raw": 0, "filtered": 0, "inlier": 0, "rejected": 0}
    for item in matches:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def inlier_ratio(matches: list[Correspondence]) -> float | None:
    """Verified inliers over all raw correspondences. None when there are none.

    Same denominator as ``src.evaluation.metrics.inlier_ratio_from_matches``.
    """

    if not matches:
        return None
    return len(verified_matches(matches)) / len(matches)


def inliers_above_model_minimum(matches: list[Correspondence], min_samples: int) -> int:
    """Verified inliers beyond the geometric model's minimum sample size.

    Zero or negative means the verified set carries no corroborating evidence
    at all: the transform passes through its own defining points and nothing
    else agrees with it.
    """

    return len(verified_matches(matches)) - min_samples


def coverage(
    points: list[Correspondence],
    pair: RegistrationPair,
) -> float | None:
    """Mean source/reference bounding-box area fraction of the given points.

    Mirrors ``src.evaluation.metrics.spatial_coverage_from_control_points`` so
    verified-match coverage and control-point coverage are comparable.
    Returns None when either product lacks dimensions or no point is finite.
    """

    source_area = _dimension_area(pair, "source")
    reference_area = _dimension_area(pair, "reference")
    if source_area is None or reference_area is None:
        return None

    eligible = [item for item in points if _finite(item)]
    if not eligible:
        return None

    source_fraction = _bbox_area_fraction(
        [item.source_xy[0] for item in eligible],
        [item.source_xy[1] for item in eligible],
        source_area,
    )
    reference_fraction = _bbox_area_fraction(
        [item.reference_xy[0] for item in eligible],
        [item.reference_xy[1] for item in eligible],
        reference_area,
    )
    if source_fraction is None or reference_fraction is None:
        return None
    return 0.5 * (source_fraction + reference_fraction)


def occupancy(
    points: list[Correspondence],
    pair: RegistrationPair,
    grid_bins: int,
) -> dict[str, Any]:
    """Occupied-cell counts on a ``grid_bins`` x ``grid_bins`` image grid.

    Cells are defined over the full image extent from product dimensions, not
    over the points' own bounding box, so an occupancy of 2/64 cannot be
    inflated into "full coverage" by rescaling to the points themselves.
    """

    payload: dict[str, Any] = {
        "grid_bins": grid_bins,
        "total_cells": grid_bins * grid_bins,
        "source_occupied_cells": None,
        "reference_occupied_cells": None,
        "source_occupied_fraction": None,
        "reference_occupied_fraction": None,
    }

    source_shape = _dimensions(pair, "source")
    reference_shape = _dimensions(pair, "reference")
    eligible = [item for item in points if _finite(item)]
    if not eligible:
        return payload

    if source_shape is not None:
        cells = {
            _cell(item.source_xy, source_shape, grid_bins) for item in eligible
        }
        payload["source_occupied_cells"] = len(cells)
        payload["source_occupied_fraction"] = len(cells) / (grid_bins * grid_bins)
    if reference_shape is not None:
        cells = {
            _cell(item.reference_xy, reference_shape, grid_bins) for item in eligible
        }
        payload["reference_occupied_cells"] = len(cells)
        payload["reference_occupied_fraction"] = len(cells) / (grid_bins * grid_bins)
    return payload


def _cell(
    xy: tuple[float, float], shape: tuple[int, int], grid_bins: int
) -> tuple[int, int]:
    height, width = shape
    column = min(grid_bins - 1, max(0, int(xy[0] / max(width, 1) * grid_bins)))
    row = min(grid_bins - 1, max(0, int(xy[1] / max(height, 1) * grid_bins)))
    return row, column


def _dimensions(pair: RegistrationPair, role: str) -> tuple[int, int] | None:
    product = pair.source if role == "source" else pair.reference
    dimensions = product.dimensions
    if dimensions is None:
        return None
    return int(dimensions.height_px), int(dimensions.width_px)


def _dimension_area(pair: RegistrationPair, role: str) -> float | None:
    shape = _dimensions(pair, role)
    if shape is None:
        return None
    return float(shape[0]) * float(shape[1])


def _bbox_area_fraction(
    xs: list[float], ys: list[float], image_area: float
) -> float | None:
    bbox_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    fraction = bbox_area / image_area
    if not 0.0 <= fraction <= 1.0:
        return None
    return fraction


def _finite(item: Correspondence) -> bool:
    return (
        math.isfinite(item.source_xy[0])
        and math.isfinite(item.source_xy[1])
        and math.isfinite(item.reference_xy[0])
        and math.isfinite(item.reference_xy[1])
    )


__all__ = [
    "coverage",
    "inlier_ratio",
    "inliers_above_model_minimum",
    "occupancy",
    "status_counts",
    "verified_matches",
]
