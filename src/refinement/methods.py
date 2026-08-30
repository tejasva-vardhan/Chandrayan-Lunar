"""Replaceable local refinement methods.

The registry is not a frozen enum. The two-argument pipeline callable wires
``zncc_parabolic_baseline`` as a SAME-MODALITY / SOFTWARE BASELINE.

This is not:
  - the final lunar sub-pixel method (D-006)
  - a multimodal OHRC ↔ IIRS / TMC-2 solution
  - permission to add adaptive routing (route() is out of scope)

A later experiment may register another method and pass it through
RefinementSettings. Identity passthrough exists so a future ablation can
compare NO REFINEMENT vs the current baseline vs a future method without
changing the frozen refine_points signature.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from src.models.registration_result import ControlPoint
from src.refinement.settings import RefinementSettings


class RefinementMethod(ABC):
    """Local refinement of one control point. Does not rematch correspondences."""

    method_id: str
    role: str
    requires_rasters: bool

    @abstractmethod
    def refine_point(
        self,
        source: np.ndarray | None,
        reference: np.ndarray | None,
        point: ControlPoint,
        settings: RefinementSettings,
    ) -> ControlPoint | None:
        """Return a refined point, or None when refinement did not succeed.

        None means failure: the orchestrator preserves the original point.
        Implementations must not rematch, must not drop the correspondence,
        and must not invent coordinates.
        """


def get_refinement_method(method_id: str) -> RefinementMethod:
    """Look up a registered method. Unknown ids are configuration errors."""

    # Lazy imports keep the ABC module free of implementation cycles.
    from src.refinement.identity import IdentityPassthrough
    from src.refinement.zncc import ZnccParabolicBaseline

    registry: dict[str, type[RefinementMethod]] = {
        IdentityPassthrough.method_id: IdentityPassthrough,
        ZnccParabolicBaseline.method_id: ZnccParabolicBaseline,
    }
    try:
        cls = registry[method_id]
    except KeyError as exc:
        known = ", ".join(sorted(registry))
        raise ValueError(f"unknown refinement method_id={method_id!r}; known: {known}") from exc
    return cls()
