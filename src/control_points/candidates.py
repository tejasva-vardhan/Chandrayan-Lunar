"""Eligible correspondences for control-point selection.

Verified means Correspondence.status == "inlier" as assigned by
src/verification (VERIFICATION_DESIGN_V1). This module does not re-run
geometric verification. Rejected, filtered, and raw items are not used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.models.correspondence_set import Correspondence


@dataclass(frozen=True, slots=True)
class EligibleCandidate:
    """One inlier that passed coordinate and duplicate checks."""

    index: int
    correspondence: Correspondence


def _finite_xy(xy: tuple[float, float]) -> bool:
    return math.isfinite(xy[0]) and math.isfinite(xy[1])


def eligible_candidates(matches: list[Correspondence]) -> tuple[EligibleCandidate, ...]:
    """Inliers with finite coordinates; first exact (source, reference) kept.

    Duplicate policy matches verification: exact tuple equality, not a spatial
    tolerance. Later exact duplicates are dropped. They are not fabricated
    into extra control points.
    """

    selected: list[EligibleCandidate] = []
    seen: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    for index, item in enumerate(matches):
        if item.status != "inlier":
            continue
        if not _finite_xy(item.source_xy) or not _finite_xy(item.reference_xy):
            continue
        key = (item.source_xy, item.reference_xy)
        if key in seen:
            continue
        seen.add(key)
        selected.append(EligibleCandidate(index=index, correspondence=item))
    return tuple(selected)
