"""Spatially uniform control points. Owned by Shaiz.

Pipeline import surface: select_control_points(correspondences, pair) -> list[ControlPoint].

Spatial distribution is first-class (D-005). Do not keep only clustered
top-confidence points.
"""

from __future__ import annotations

from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint


def select_control_points(
    correspondences: CorrespondenceSet, pair: RegistrationPair
) -> list[ControlPoint]:
    """Select spatially distributed control points from verified correspondences."""
    raise NotImplementedError(
        f"select_control_points is not implemented. pair_id={pair.pair_id}"
    )


__all__ = ["select_control_points"]
