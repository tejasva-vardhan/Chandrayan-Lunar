"""Spatially distributed control-point selection.

Frozen pipeline surface:
select_control_points(correspondences, pair) -> list[ControlPoint].

Consumes CorrespondenceSet after geometric verification. Does not re-run
verification, does not interpret matcher_id, and does not invent uncertainty.
"""

from __future__ import annotations

import math

from src.control_points.candidates import eligible_candidates
from src.control_points.ranking import quality_sort_key
from src.control_points.settings import ControlPointSettings, unvalidated_software_defaults
from src.control_points.spatial import assign_cells
from src.models.correspondence_set import Correspondence, CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint


def select_control_points(
    correspondences: CorrespondenceSet, pair: RegistrationPair
) -> list[ControlPoint]:
    """Select spatially distributed control points (frozen two-argument API).

    Uses unvalidated_software_defaults(): grid_bins=8, max_per_source_cell=1,
    max_per_reference_cell=1, max_points=None. Those numbers exist only because
    this frozen signature has no settings argument. They are software/test
    defaults, not SIH thresholds, not lunar-validated parameters, not a final
    spatial strategy, and not benchmark results.

    Call select_control_points_with_settings to supply explicit settings.
    """

    return select_control_points_with_settings(
        correspondences, pair, unvalidated_software_defaults()
    )


def select_control_points_with_settings(
    correspondences: CorrespondenceSet,
    pair: RegistrationPair,
    settings: ControlPointSettings,
) -> list[ControlPoint]:
    """Configurable selection. pair is unused beyond the frozen signature."""

    _ = pair
    candidates = eligible_candidates(list(correspondences.matches))
    if not candidates:
        return []

    cells = assign_cells(candidates, settings.grid_bins)
    ordered = sorted(range(len(candidates)), key=lambda i: quality_sort_key(candidates[i]))

    source_count: dict[tuple[int, int], int] = {}
    reference_count: dict[tuple[int, int], int] = {}
    selected: list[ControlPoint] = []

    for local in ordered:
        if settings.max_points is not None and len(selected) >= settings.max_points:
            break
        source_row, source_col, reference_row, reference_col = cells[local]
        source_key = (source_row, source_col)
        reference_key = (reference_row, reference_col)
        if source_count.get(source_key, 0) >= settings.max_per_source_cell:
            continue
        if reference_count.get(reference_key, 0) >= settings.max_per_reference_cell:
            continue
        selected.append(_to_control_point(candidates[local].correspondence))
        source_count[source_key] = source_count.get(source_key, 0) + 1
        reference_count[reference_key] = reference_count.get(reference_key, 0) + 1

    return selected


def _to_control_point(item: Correspondence) -> ControlPoint:
    residual = item.residual
    if residual is not None and math.isfinite(residual):
        copied_residual: float | None = float(residual)
    else:
        copied_residual = None
    return ControlPoint(
        source_xy=item.source_xy,
        reference_xy=item.reference_xy,
        residual=copied_residual,
        uncertainty=None,
    )
