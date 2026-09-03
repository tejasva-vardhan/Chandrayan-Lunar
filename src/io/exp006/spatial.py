"""EXP-006 spatial-distribution diagnostics.

These measurements live in the experiment layer. They do not add fields to
CorrespondenceSet or RegistrationResult. Occupied-cell geometry reuses the
EXP-001 8x8 full-image occupancy rule so A/B numbers are comparable to the
committed pair_02 SIFT control (11 / 64 source cells, 9 / 64 reference).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from src.io.exp001.metrics import coverage, occupancy
from src.models.correspondence_set import Correspondence
from src.models.registration_pair import RegistrationPair

_INLIER_STATUS = "inlier"


def spatial_distribution_report(
    points: list[Correspondence],
    pair: RegistrationPair,
    grid_bins: int,
) -> dict[str, Any]:
    """Coverage, occupancy, per-cell density, and Clark-Evans R.

    Cells are defined over product ImageDimensions, not the points' own
    bounding box. Clark-Evans R uses the same full-image area, so a tight
    cluster in a large raster scores as clustered (R < 1). This is an
    engineering diagnostic, not a frozen SIH uniformity metric.
    """

    eligible = [item for item in points if _finite(item)]
    occ = occupancy(eligible, pair, grid_bins)
    source_shape = _dimensions(pair, "source")
    reference_shape = _dimensions(pair, "reference")
    source_cells = _cell_report(
        [item.source_xy for item in eligible], source_shape, grid_bins
    )
    reference_cells = _cell_report(
        [item.reference_xy for item in eligible], reference_shape, grid_bins
    )
    return {
        "grid_bins": grid_bins,
        "total_cells": grid_bins * grid_bins,
        "point_count": len(eligible),
        "verified_match_coverage": coverage(eligible, pair),
        "verified_match_occupancy": occ,
        "source": source_cells,
        "reference": reference_cells,
        "spans_usable_overlap_proxy": bool(
            source_cells.get("spans_multiple_rows")
            and source_cells.get("spans_multiple_cols")
            and reference_cells.get("spans_multiple_rows")
            and reference_cells.get("spans_multiple_cols")
        ),
        "extent_rule": "full_product_image_dimensions_not_point_bbox",
        "uniformity_metric": (
            "clark_evans_R = mean_nn / (0.5 * sqrt(image_area / n)); "
            "R<1 clustered, R~1 random, R>1 dispersed. No edge correction."
        ),
        "limitation": (
            "occupied-cell ratio and Clark-Evans R are experiment diagnostics, "
            "not proof of uniform coverage of the true OHRC/LROC overlap; "
            "overlap is not recomputed from the products"
        ),
    }


def residual_distribution(points: list[Correspondence]) -> dict[str, Any]:
    """Stored verification-inlier residual summary. Residuals are not recomputed."""

    values = [
        float(item.residual)
        for item in points
        if item.status == _INLIER_STATUS
        and item.residual is not None
        and math.isfinite(item.residual)
        and item.residual >= 0.0
    ]
    payload: dict[str, Any] = {
        "count": len(values),
        "min": None,
        "max": None,
        "mean": None,
        "median": None,
        "p95": None,
        "rmse": None,
        "units": "verification_image_space_transfer_error_pixels",
        "not_accuracy": True,
    }
    if not values:
        return payload
    array = np.asarray(values, dtype=float)
    payload.update(
        {
            "min": float(array.min()),
            "max": float(array.max()),
            "mean": float(array.mean()),
            "median": float(np.median(array)),
            "p95": float(np.quantile(array, 0.95)),
            "rmse": float(np.sqrt(np.mean(np.square(array)))),
        }
    )
    return payload


def correspondence_fingerprint(
    matches: list[Correspondence],
) -> list[tuple[float, float, float, float]]:
    """Deterministic ordered identity of a raw correspondence list."""

    return [
        (
            float(item.source_xy[0]),
            float(item.source_xy[1]),
            float(item.reference_xy[0]),
            float(item.reference_xy[1]),
        )
        for item in matches
    ]


def repeat_stability(
    first: list[Correspondence], second: list[Correspondence]
) -> dict[str, Any]:
    """Whether two deterministic match calls produced the same point set."""

    left = correspondence_fingerprint(first)
    right = correspondence_fingerprint(second)
    return {
        "repeat_count": 2,
        "raw_match_count_first": len(left),
        "raw_match_count_second": len(right),
        "raw_counts_equal": len(left) == len(right),
        "coordinates_equal": left == right,
        "deterministic": left == right,
    }


def _cell_report(
    points: list[tuple[float, float]],
    shape: tuple[int, int] | None,
    grid_bins: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "occupied_cells": None,
        "occupied_fraction": None,
        "max_matches_per_cell": None,
        "concentration": None,
        "occupied_rows": None,
        "occupied_cols": None,
        "spans_multiple_rows": None,
        "spans_multiple_cols": None,
        "clark_evans_r": None,
        "mean_nearest_neighbour_px": None,
        "cell_counts_row_major": None,
    }
    if shape is None:
        return payload

    total = grid_bins * grid_bins
    counts = [0] * total
    cells: list[tuple[int, int]] = []
    for xy in points:
        row, col = _cell(xy, shape, grid_bins)
        cells.append((row, col))
        counts[row * grid_bins + col] += 1

    occupied = {cell for cell in cells}
    occupied_rows = {row for row, _col in occupied}
    occupied_cols = {col for _row, col in occupied}
    max_count = max(counts) if points else 0
    payload.update(
        {
            "occupied_cells": len(occupied),
            "occupied_fraction": len(occupied) / total,
            "max_matches_per_cell": max_count,
            "concentration": (max_count / len(points)) if points else None,
            "occupied_rows": len(occupied_rows),
            "occupied_cols": len(occupied_cols),
            "spans_multiple_rows": len(occupied_rows) >= 2,
            "spans_multiple_cols": len(occupied_cols) >= 2,
            "cell_counts_row_major": counts,
        }
    )
    nn = _clark_evans(points, float(shape[0] * shape[1]))
    payload.update(nn)
    return payload


def _clark_evans(points: list[tuple[float, float]], area: float) -> dict[str, Any]:
    if len(points) < 2 or area <= 0.0:
        return {"clark_evans_r": None, "mean_nearest_neighbour_px": None}
    coords = np.asarray(points, dtype=float)
    differences = coords[:, None, :] - coords[None, :, :]
    distances = np.sqrt(np.sum(np.square(differences), axis=2))
    np.fill_diagonal(distances, np.inf)
    nearest = distances.min(axis=1)
    finite = nearest[np.isfinite(nearest)]
    if finite.size == 0:
        return {"clark_evans_r": None, "mean_nearest_neighbour_px": None}
    mean_nn = float(finite.mean())
    expected = 0.5 * math.sqrt(area / len(points))
    if expected <= 0.0:
        return {"clark_evans_r": None, "mean_nearest_neighbour_px": mean_nn}
    return {
        "clark_evans_r": mean_nn / expected,
        "mean_nearest_neighbour_px": mean_nn,
    }


def _cell(xy: tuple[float, float], shape: tuple[int, int], grid_bins: int) -> tuple[int, int]:
    """Same full-image binning as ``src.io.exp001.metrics.occupancy``."""

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


def _finite(item: Correspondence) -> bool:
    return (
        math.isfinite(item.source_xy[0])
        and math.isfinite(item.source_xy[1])
        and math.isfinite(item.reference_xy[0])
        and math.isfinite(item.reference_xy[1])
    )


__all__ = [
    "correspondence_fingerprint",
    "repeat_stability",
    "residual_distribution",
    "spatial_distribution_report",
]
