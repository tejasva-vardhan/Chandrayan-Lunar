"""Axis-aligned grid over correspondence bounding boxes.

Extent is computed from candidate pixel tuples, not from product dimensions.
Pixel-centre versus pixel-corner is not interpreted (freeze v1). This tiling
is an engineering baseline, not a scientifically optimal partition.
"""

from __future__ import annotations

from src.control_points.candidates import EligibleCandidate


def axis_bin(value: float, lower: float, upper: float, bins: int) -> int:
    """Map value into [0, bins). Degenerate span (upper <= lower) → bin 0."""

    if bins < 1:
        raise ValueError("bins must be >= 1")
    if upper <= lower:
        return 0
    scaled = (value - lower) / (upper - lower) * bins
    index = int(scaled)
    if index >= bins:
        return bins - 1
    if index < 0:
        return 0
    return index


def extent(values: list[float]) -> tuple[float, float]:
    return (min(values), max(values))


def assign_cells(
    candidates: tuple[EligibleCandidate, ...], bins: int
) -> tuple[tuple[int, int, int, int], ...]:
    """Return (source_row, source_col, reference_row, reference_col) per candidate.

    Rows are y-bins, columns are x-bins. Both images use the same bin count.
    """

    if not candidates:
        return ()
    source_x = [item.correspondence.source_xy[0] for item in candidates]
    source_y = [item.correspondence.source_xy[1] for item in candidates]
    reference_x = [item.correspondence.reference_xy[0] for item in candidates]
    reference_y = [item.correspondence.reference_xy[1] for item in candidates]
    source_x_extent = extent(source_x)
    source_y_extent = extent(source_y)
    reference_x_extent = extent(reference_x)
    reference_y_extent = extent(reference_y)
    cells: list[tuple[int, int, int, int]] = []
    for item in candidates:
        sx, sy = item.correspondence.source_xy
        rx, ry = item.correspondence.reference_xy
        cells.append(
            (
                axis_bin(sy, source_y_extent[0], source_y_extent[1], bins),
                axis_bin(sx, source_x_extent[0], source_x_extent[1], bins),
                axis_bin(ry, reference_y_extent[0], reference_y_extent[1], bins),
                axis_bin(rx, reference_x_extent[0], reference_x_extent[1], bins),
            )
        )
    return tuple(cells)
