"""Geometric verification. Owned by Shaiz.

Pipeline import surface: verify_matches(correspondences, pair) -> CorrespondenceSet.

CorrespondenceSet.matches remains the source of truth. Update statuses on those
items; do not invent a second correspondence collection.
"""

from __future__ import annotations

from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair


def verify_matches(
    correspondences: CorrespondenceSet, pair: RegistrationPair
) -> CorrespondenceSet:
    """Filter and geometrically verify correspondences."""
    raise NotImplementedError(
        f"verify_matches is not implemented. pair_id={pair.pair_id} "
        f"matcher_id={correspondences.matcher_id}"
    )


__all__ = ["verify_matches"]
