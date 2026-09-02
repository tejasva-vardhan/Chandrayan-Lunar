"""EXP-000 integration helpers. Owned by Tejas (architecture / integration).

Does not implement matchers, SPICE, or new registration models. It records
frozen-stage outputs and a bounded diagnostic crop when the existing
full-raster registration cap blocks the complete warp.
"""

from src.io.exp000.config import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    REFINEMENT_OUTCOME_COORDINATES_UPDATED,
    REFINEMENT_OUTCOME_INDETERMINATE,
    REFINEMENT_OUTCOME_NO_POINTS,
    snapshot_software_configuration,
)
from src.io.exp000.diagnostic import (
    DiagnosticWindow,
    control_point_crop_report,
    diagnostic_crop_window,
    projective_fit_residuals,
    warp_diagnostic_crop,
    window_contains_xy,
)
from src.io.exp000.run import Exp000Error, run_exp000, run_exp000_from_products

__all__ = [
    "DiagnosticWindow",
    "Exp000Error",
    "INDEPENDENT_ACCURACY_NOT_VALIDATED",
    "REFINEMENT_OUTCOME_COORDINATES_UPDATED",
    "REFINEMENT_OUTCOME_INDETERMINATE",
    "REFINEMENT_OUTCOME_NO_POINTS",
    "control_point_crop_report",
    "diagnostic_crop_window",
    "projective_fit_residuals",
    "run_exp000",
    "run_exp000_from_products",
    "snapshot_software_configuration",
    "warp_diagnostic_crop",
    "window_contains_xy",
]
