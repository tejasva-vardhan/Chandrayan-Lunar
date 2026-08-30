"""Identity / no-op refinement. Ablation hook only.

This method returns each control point unchanged. It does not read rasters
and does not estimate a displacement. It exists so a later experiment can
compare:

    NO REFINEMENT  vs  CURRENT BASELINE  vs  FUTURE METHOD

without changing the frozen refine_points signature.

It is NOT a sub-pixel method. It must not be cited as refinement accuracy.
"""

from __future__ import annotations

import numpy as np

from src.models.registration_result import ControlPoint
from src.refinement.methods import RefinementMethod
from src.refinement.settings import RefinementSettings


class IdentityPassthrough(RefinementMethod):
    method_id = "identity_passthrough"
    role = "ablation_no_refinement"
    requires_rasters = False

    def refine_point(
        self,
        source: np.ndarray | None,
        reference: np.ndarray | None,
        point: ControlPoint,
        settings: RefinementSettings,
    ) -> ControlPoint | None:
        _ = source, reference, settings
        return point.model_copy()
