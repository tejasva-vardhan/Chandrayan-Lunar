"""Spatially uniform control points. Owned per TEAM_MODULE_HANDOFF_V1.

Pipeline import surface: select_control_points(correspondences, pair) -> list[ControlPoint].

Spatial distribution is first-class (D-005). Do not keep only clustered
top-confidence points. The two-argument pipeline callable uses engineering
grid/cap defaults (grid_bins=8, max-per-cell=1), not SIH or lunar-validated
parameters.
"""

from src.control_points.select import select_control_points, select_control_points_with_settings
from src.control_points.settings import ControlPointSettings, unvalidated_software_defaults

__all__ = [
    "ControlPointSettings",
    "select_control_points",
    "select_control_points_with_settings",
    "unvalidated_software_defaults",
]
