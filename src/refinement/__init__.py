"""Sub-pixel refinement. Owned by Shaiz.

Pipeline import surface: refine_points(control_points, pair) -> list[ControlPoint].

Sub-pixel claims require independent validation (D-006). Do not invent
uncertainty units; leave ControlPoint.uncertainty unset until a real value
is computed.
"""

from __future__ import annotations

from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint


def refine_points(
    control_points: list[ControlPoint], pair: RegistrationPair
) -> list[ControlPoint]:
    """Refine control-point coordinates. Do not invent sub-pixel claims."""
    raise NotImplementedError(
        f"refine_points is not implemented. pair_id={pair.pair_id} n={len(control_points)}"
    )


__all__ = ["refine_points"]
