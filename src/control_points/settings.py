"""Experimental control-point selection settings. Not a scientific freeze.

The frozen callable is select_control_points(correspondences, pair). It has
no settings argument, so software defaults are required for the two-argument
API. Those numbers are engineering/test defaults only.

They are NOT:
  - SIH thresholds
  - lunar-validated parameters
  - final scientific parameters
  - benchmark results

Do not copy these into configs/default.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControlPointSettings:
    """Configuration for one control-point selection run.

    grid_bins
        Number of equal bins on each axis of the source extent and of the
        reference extent. Engineering tiling only. Not a scientifically
        optimal cell count (D-005 requires spatial distribution; it does
        not freeze a grid size).

    max_per_source_cell
        Maximum selected points whose source_xy fall in the same source bin.
        Engineering cap so a cluster cannot dominate.

    max_per_reference_cell
        Same cap on the reference image grid. Accounts for distribution on
        both images without adding contract fields.

    max_points
        Optional global cap after spatial caps. None means no extra cap.
        Not a validated "how many control points lunar scenes need".
    """

    grid_bins: int
    max_per_source_cell: int
    max_per_reference_cell: int
    max_points: int | None = None

    def __post_init__(self) -> None:
        if self.grid_bins < 1:
            raise ValueError("grid_bins must be >= 1")
        if self.max_per_source_cell < 1:
            raise ValueError("max_per_source_cell must be >= 1")
        if self.max_per_reference_cell < 1:
            raise ValueError("max_per_reference_cell must be >= 1")
        if self.max_points is not None and self.max_points < 1:
            raise ValueError("max_points must be None or >= 1")


# --- Frozen two-argument API: engineering defaults only ---
# select_control_points(correspondences, pair) has no settings argument.
# These values exist ONLY so that callable can run.
UNVALIDATED_SOFTWARE_GRID_BINS = 8  # engineering default, not SIH
UNVALIDATED_SOFTWARE_MAX_PER_SOURCE_CELL = 1  # engineering default, not SIH
UNVALIDATED_SOFTWARE_MAX_PER_REFERENCE_CELL = 1  # engineering default, not SIH


def unvalidated_software_defaults() -> ControlPointSettings:
    """Engineering defaults used by select_control_points(correspondences, pair).

    grid_bins=8 and max-per-cell=1 exist only because the frozen two-argument
    API cannot accept settings. They are not SIH thresholds, not
    lunar-validated, not a final spatial strategy, and not benchmark results.

    Tests and experiments that need a specific tiling or cap should pass
    ControlPointSettings to select_control_points_with_settings.
    """

    return ControlPointSettings(
        grid_bins=UNVALIDATED_SOFTWARE_GRID_BINS,
        max_per_source_cell=UNVALIDATED_SOFTWARE_MAX_PER_SOURCE_CELL,
        max_per_reference_cell=UNVALIDATED_SOFTWARE_MAX_PER_REFERENCE_CELL,
        max_points=None,
    )
