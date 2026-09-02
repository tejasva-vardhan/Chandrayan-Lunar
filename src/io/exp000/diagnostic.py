"""Bounded diagnostic registration crop.

Full-resolution warp of EXP-000 pair 01 is blocked by the existing
``max_output_pixels = 16_777_216`` guard in ``register()``. This module does
not raise that cap. It warps a reference-space window that stays at or below
the same budget, using the already-fitted transform and original-image
coordinates.

Window *size* still starts from ``preferred_side`` and grows to leftover
budget. Window *placement* selects a deterministic maximum-cardinality
control-point cover inside that capped size. Centering on the global
centroid is not used when it would exclude every selected point.

This is diagnostic output, not a claim that the crop is a scientifically
complete registered product.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from src.ingestion.windows import mmap_product_array
from src.models.registration_result import ControlPoint
from src.registration.settings import unvalidated_software_defaults
from src.registration.warp import warp_to_grid
from src.verification.residuals import image_space_transfer_error

_PREFERRED_SIDE = 2048
_REASON_SPAN_EXCEEDS_CAP = (
    "control_point_axis_aligned_span_exceeds_capped_window; "
    "selected the maximum-cardinality subset that fits"
)
_REASON_NONE_FIT = "no_control_point_fits_in_capped_window"
_REASON_NO_FINITE = "no_finite_control_points"


@dataclass(frozen=True, slots=True)
class DiagnosticWindow:
    """Reference-image crop in original pixel coordinates (row=y, col=x)."""

    row: int
    col: int
    height: int
    width: int

    def as_dict(self) -> dict[str, int]:
        return {
            "row": self.row,
            "col": self.col,
            "height": self.height,
            "width": self.width,
            "pixel_count": self.height * self.width,
        }


def diagnostic_crop_window(
    reference_height: int,
    reference_width: int,
    control_points: list[ControlPoint],
    *,
    max_output_pixels: int | None = None,
    preferred_side: int = _PREFERRED_SIDE,
) -> DiagnosticWindow:
    """Choose a capped reference-space window that covers control points.

    Size policy is unchanged: start at ``preferred_side``, then grow to use
    leftover budget without exceeding ``max_output_pixels`` or the image
    bounds. Placement maximises the number of finite ``reference_xy`` points
    that fall inside the window. Ties prefer the tighter cluster, then
    smaller original indices. Slack inside the feasible range is centred on
    the included subset, then clipped so those points stay inside.
    """

    if reference_height < 1 or reference_width < 1:
        raise ValueError("reference dimensions must be positive")
    cap = (
        unvalidated_software_defaults().max_output_pixels
        if max_output_pixels is None
        else max_output_pixels
    )
    if cap < 1:
        raise ValueError("max_output_pixels must be >= 1")

    height, width = _capped_window_size(
        reference_height, reference_width, cap, preferred_side
    )
    points = _finite_reference_points(control_points)
    if not points:
        row, col = _origin_from_center(
            (reference_width - 1) / 2.0,
            (reference_height - 1) / 2.0,
            height,
            width,
            reference_height,
            reference_width,
        )
        return DiagnosticWindow(row=row, col=col, height=height, width=width)

    included = _max_cover_indices(
        points, width, height, reference_width, reference_height
    )
    if not included:
        row, col = _origin_from_center(
            (reference_width - 1) / 2.0,
            (reference_height - 1) / 2.0,
            height,
            width,
            reference_height,
            reference_width,
        )
        return DiagnosticWindow(row=row, col=col, height=height, width=width)

    xs = [points[i][0] for i in included]
    ys = [points[i][1] for i in included]
    row, col = _place_containing_window(
        xs, ys, height, width, reference_height, reference_width
    )
    return DiagnosticWindow(row=row, col=col, height=height, width=width)


def window_contains_xy(window: DiagnosticWindow, xy: tuple[float, float]) -> bool:
    """Return whether ``xy`` (x, y) lies in the inclusive pixel box of *window*."""

    if not _finite_xy(xy):
        return False
    x, y = xy
    return (
        window.col <= x <= window.col + window.width - 1
        and window.row <= y <= window.row + window.height - 1
    )


def control_point_crop_report(
    window: DiagnosticWindow, control_points: list[ControlPoint]
) -> dict[str, object]:
    """Record which selected control points fall inside *window*."""

    inside_indices: list[int] = []
    inside_reference_xy: list[list[float]] = []
    finite_count = 0
    for index, point in enumerate(control_points):
        if not _finite_xy(point.reference_xy):
            continue
        finite_count += 1
        if window_contains_xy(window, point.reference_xy):
            inside_indices.append(index)
            inside_reference_xy.append([float(point.reference_xy[0]), float(point.reference_xy[1])])
    total = len(control_points)
    inside_count = len(inside_indices)
    all_included = inside_count == total
    reason: str | None
    if total == 0 or finite_count == 0:
        reason = None if total == 0 else _REASON_NO_FINITE
        if total == 0:
            all_included = True
    elif all_included:
        reason = None
    elif inside_count == 0:
        reason = _REASON_NONE_FIT
    else:
        reason = _REASON_SPAN_EXCEEDS_CAP
    return {
        "inside_indices": inside_indices,
        "inside_count": inside_count,
        "total_control_points": total,
        "finite_reference_count": finite_count,
        "all_included": all_included,
        "inside_reference_xy": inside_reference_xy,
        "reason": reason,
    }


def crop_translation_matrix(window: DiagnosticWindow) -> np.ndarray:
    """Map reference pixels to crop-local pixels: x' = x - col, y' = y - row."""

    return np.array(
        [
            [1.0, 0.0, -float(window.col)],
            [0.0, 1.0, -float(window.row)],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def warp_diagnostic_crop(
    source_raster_uri: str,
    source_to_reference: np.ndarray,
    window: DiagnosticWindow,
) -> np.ndarray:
    """Warp ``source`` onto ``window`` without materialising the full output grid.

    Source is memory-mapped. The fitted transform is composed with a crop
    translation so ``warp_to_grid`` samples original source coordinates.
    """

    if window.height * window.width > unvalidated_software_defaults().max_output_pixels:
        raise ValueError("diagnostic crop exceeds the existing registration pixel cap")
    source = mmap_product_array(source_raster_uri)
    crop_matrix = crop_translation_matrix(window) @ np.asarray(source_to_reference, dtype=float)
    return warp_to_grid(source, crop_matrix, window.height, window.width)


def projective_fit_residuals(
    control_points: list[ControlPoint], matrix: np.ndarray
) -> list[float]:
    """Transfer error of the fitted matrix on the same points used to fit it.

    For a 4-point projective DLT these values can be numerically tiny. They
    are not independent registration accuracy.
    """

    if not control_points:
        return []
    source = np.array([point.source_xy for point in control_points], dtype=float)
    reference = np.array([point.reference_xy for point in control_points], dtype=float)
    return [float(value) for value in image_space_transfer_error(source, reference, matrix)]


def _capped_window_size(
    reference_height: int,
    reference_width: int,
    cap: int,
    preferred_side: int,
) -> tuple[int, int]:
    """Return (height, width) using the existing preferred-side-then-grow rule."""

    height = min(preferred_side, reference_height, cap)
    height = max(1, height)
    width = min(reference_width, cap // height)
    width = max(1, width)
    height = min(reference_height, cap // width)
    return height, width


def _finite_reference_points(
    control_points: list[ControlPoint],
) -> list[tuple[float, float]]:
    return [
        (float(point.reference_xy[0]), float(point.reference_xy[1]))
        for point in control_points
        if _finite_xy(point.reference_xy)
    ]


def _feasible_origin(
    min_v: float, max_v: float, window: int, image: int
) -> tuple[int, int] | None:
    """Inclusive integer origin range that keeps [min_v, max_v] inside the window."""

    if window < 1 or window > image:
        return None
    low = max(0, int(math.ceil(max_v - (window - 1))))
    high = min(image - window, int(math.floor(min_v)))
    if low > high:
        return None
    return low, high


def _max_cover_indices(
    points: list[tuple[float, float]],
    width: int,
    height: int,
    image_width: int,
    image_height: int,
) -> list[int]:
    """Return indices of a deterministic maximum-cardinality subset that fits."""

    count = len(points)
    if count == 0:
        return []
    best: list[int] = []
    best_key: tuple[object, ...] | None = None
    order_x = sorted(range(count), key=lambda i: (points[i][0], points[i][1], i))
    for left in range(count):
        for right in range(left, count):
            group = order_x[left : right + 1]
            xs = [points[i][0] for i in group]
            if _feasible_origin(min(xs), max(xs), width, image_width) is None:
                continue
            order_y = sorted(group, key=lambda i: (points[i][1], points[i][0], i))
            start = 0
            for end in range(len(order_y)):
                while start <= end and not _subset_fits(
                    [order_y[k] for k in range(start, end + 1)],
                    points,
                    width,
                    height,
                    image_width,
                    image_height,
                ):
                    start += 1
                if start > end:
                    continue
                candidate = [order_y[k] for k in range(start, end + 1)]
                key = _subset_sort_key(candidate, points)
                if best_key is None or key < best_key:
                    best_key = key
                    best = candidate
    return sorted(best)


def _subset_fits(
    indices: list[int],
    points: list[tuple[float, float]],
    width: int,
    height: int,
    image_width: int,
    image_height: int,
) -> bool:
    xs = [points[i][0] for i in indices]
    ys = [points[i][1] for i in indices]
    return (
        _feasible_origin(min(xs), max(xs), width, image_width) is not None
        and _feasible_origin(min(ys), max(ys), height, image_height) is not None
    )


def _subset_sort_key(
    indices: list[int], points: list[tuple[float, float]]
) -> tuple[object, ...]:
    xs = [points[i][0] for i in indices]
    ys = [points[i][1] for i in indices]
    return (
        -len(indices),
        float(max(ys) - min(ys)),
        float(max(xs) - min(xs)),
        tuple(sorted(indices)),
    )


def _place_containing_window(
    xs: list[float],
    ys: list[float],
    height: int,
    width: int,
    image_height: int,
    image_width: int,
) -> tuple[int, int]:
    col_range = _feasible_origin(min(xs), max(xs), width, image_width)
    row_range = _feasible_origin(min(ys), max(ys), height, image_height)
    if col_range is None or row_range is None:
        return _origin_from_center(
            float(np.mean(xs)),
            float(np.mean(ys)),
            height,
            width,
            image_height,
            image_width,
        )
    preferred_col = int(round(float(np.mean(xs)) - width / 2.0))
    preferred_row = int(round(float(np.mean(ys)) - height / 2.0))
    col = min(max(preferred_col, col_range[0]), col_range[1])
    row = min(max(preferred_row, row_range[0]), row_range[1])
    return row, col


def _origin_from_center(
    center_x: float,
    center_y: float,
    height: int,
    width: int,
    image_height: int,
    image_width: int,
) -> tuple[int, int]:
    col = int(round(center_x - width / 2.0))
    row = int(round(center_y - height / 2.0))
    col = min(max(col, 0), image_width - width)
    row = min(max(row, 0), image_height - height)
    return row, col


def _finite_xy(xy: tuple[float, float]) -> bool:
    return bool(np.isfinite(xy[0]) and np.isfinite(xy[1]))
