"""Image registration. Owned by Shaiz.

Pipeline import surface:
register(pair, control_points, correspondences) -> RegistrationResult.

Do not assume homography or any other specific transformation (D-010).
TransformationModel.model_name is an unconstrained label.
Attach the provided CorrespondenceSet to RegistrationResult.correspondences.
Do not invent inliers, counts, metrics, or transformations.
"""

from __future__ import annotations

from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult


def register(
    pair: RegistrationPair,
    control_points: list[ControlPoint],
    correspondences: CorrespondenceSet,
) -> RegistrationResult:
    """Estimate a transform and produce a RegistrationResult."""
    raise NotImplementedError(f"register is not implemented. pair_id={pair.pair_id}")


__all__ = ["register"]
