"""Sub-pixel refinement. Owned per TEAM_MODULE_HANDOFF_V1 (Shaiz package).

Pipeline import surface: refine_points(control_points, pair) -> list[ControlPoint].

Sub-pixel claims require independent validation (D-006). Decimal-valued
coordinates are not evidence of sub-pixel accuracy. ControlPoint.uncertainty
stays None until a scientifically defined value exists; this software
baseline does not invent a unit (Interface Freeze v1).

The two-argument pipeline callable uses a SAME-MODALITY ZNCC + parabolic
peak software baseline, not a multimodal OHRC/IIRS solution.
"""

from src.refinement.refine import refine_points, refine_points_with_settings
from src.refinement.settings import RefinementSettings, unvalidated_software_defaults

__all__ = [
    "RefinementSettings",
    "refine_points",
    "refine_points_with_settings",
    "unvalidated_software_defaults",
]
