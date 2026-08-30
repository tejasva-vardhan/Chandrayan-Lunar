"""Canonical-minimum RegistrationMetrics from available result data.

ENGINEERING IMPLEMENTATION DEFINITIONS only. None of these formulas is a
scientifically validated SIH evaluator definition (D-011). Uncomputed or
undefended values stay None. Zero is used only when it is a measured count
or a measured residual/extent, never as a stand-in for missing data.
"""

from __future__ import annotations

import math

import numpy as np

from src.models.correspondence_set import CorrespondenceSet
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationMetrics, RegistrationResult

_INLIER_STATUS = "inlier"


def compute_registration_metrics(
    result: RegistrationResult, pair: RegistrationPair
) -> RegistrationMetrics:
    """Fill frozen metric fields from result + pair. Do not invent values."""

    correspondences = result.correspondences
    inlier_count = count_inliers(correspondences)
    return RegistrationMetrics(
        rmse=rmse_from_inlier_residuals(correspondences),
        inlier_count=inlier_count,
        inlier_ratio=inlier_ratio_from_matches(correspondences),
        spatial_coverage=spatial_coverage_from_control_points(result, pair),
        control_point_count=len(result.control_points),
    )


def count_inliers(correspondences: CorrespondenceSet | None) -> int | None:
    """Number of Correspondence items whose status is 'inlier'.

    Source of truth is CorrespondenceSet.matches, not RegistrationResult.inliers.
    None correspondences → unavailable (None), not zero.
    Empty matches → 0 (a measured empty set).
    """

    if correspondences is None:
        return None
    return sum(1 for item in correspondences.matches if item.status == _INLIER_STATUS)


def inlier_ratio_from_matches(correspondences: CorrespondenceSet | None) -> float | None:
    """inlier_count / len(matches).

    ENGINEERING IMPLEMENTATION DEFINITION. The SIH inlier-ratio denominator is
    not frozen. Empty matches or missing CorrespondenceSet → None, not 0 or 1.
    """

    if correspondences is None:
        return None
    total = len(correspondences.matches)
    if total == 0:
        return None
    return count_inliers(correspondences) / total


def rmse_from_inlier_residuals(correspondences: CorrespondenceSet | None) -> float | None:
    """RMSE of stored finite inlier residuals. Residuals are not recomputed.

    Included points: matches with status 'inlier' and a finite non-negative
    residual. Formula: sqrt(mean(residual^2)) with denominator = number of
    included residuals. Units: the stored residual's units (verification
    image-space transfer error in input pixel tuples). Missing, non-finite,
    or negative residuals are omitted; if none remain, RMSE is None, not 0.
    """

    if correspondences is None:
        return None
    residuals = [
        item.residual
        for item in correspondences.matches
        if item.status == _INLIER_STATUS and _usable_residual(item.residual)
    ]
    if not residuals:
        return None
    values = np.asarray(residuals, dtype=float)
    return float(np.sqrt(np.mean(np.square(values))))


def spatial_coverage_from_control_points(
    result: RegistrationResult, pair: RegistrationPair
) -> float | None:
    """Mean source/reference AABB-area fraction of selected control points.

    This is spatial *extent* of ControlPoint coordinates against each product's
    ImageDimensions, not uniformity, not a point count, and not full-image
    occupancy of unverified matches.

    Unavailable (None) when:
    - pair_id does not match the result (pair metadata is not trusted)
    - either product lacks dimensions (pixel-origin / image-rectangle
      semantics are not frozen; this module will not invent a denominator)
    - no control point has finite source_xy and reference_xy
    - either image fraction would fall outside [0, 1] (bbox larger than the
      dimension product)

    Normalizing by the control points' own bounding box is refused: that
    ratio is identically 1 for any non-degenerate 2D set and would fabricate
    perfect coverage.
    """

    if result.pair_id != pair.pair_id:
        return None
    source_area = _dimension_area(pair.source)
    reference_area = _dimension_area(pair.reference)
    if source_area is None or reference_area is None:
        return None

    eligible = [
        point
        for point in result.control_points
        if _finite_xy(point.source_xy) and _finite_xy(point.reference_xy)
    ]
    if not eligible:
        return None

    source_fraction = _bbox_area_fraction(
        [point.source_xy[0] for point in eligible],
        [point.source_xy[1] for point in eligible],
        source_area,
    )
    reference_fraction = _bbox_area_fraction(
        [point.reference_xy[0] for point in eligible],
        [point.reference_xy[1] for point in eligible],
        reference_area,
    )
    if source_fraction is None or reference_fraction is None:
        return None
    return 0.5 * (source_fraction + reference_fraction)


def _usable_residual(value: float | None) -> bool:
    """Finite non-negative stored residual. Transfer error cannot be negative."""

    return value is not None and math.isfinite(value) and value >= 0.0


def _finite_xy(xy: tuple[float, float]) -> bool:
    return math.isfinite(xy[0]) and math.isfinite(xy[1])


def _dimension_area(product: LunarProduct) -> float | None:
    dimensions = product.dimensions
    if dimensions is None:
        return None
    return float(dimensions.width_px) * float(dimensions.height_px)


def _bbox_area_fraction(xs: list[float], ys: list[float], image_area: float) -> float | None:
    bbox_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    fraction = bbox_area / image_area
    if not 0.0 <= fraction <= 1.0:
        return None
    return fraction
