"""Correspondence validation and pre-geometry filtering.

Does not interpret matcher identity. Does not invent a confidence
normalization. Does not apply an image-bounds test (pixel origin is undefined).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.models.correspondence_set import Correspondence
from src.verification.settings import VerificationSettings


@dataclass(frozen=True, slots=True)
class FilterOutcome:
    """Per-item pre-geometry decision. Order matches CorrespondenceSet.matches."""

    candidate_indices: tuple[int, ...]
    rejected_indices: tuple[int, ...]


def _finite_xy(xy: tuple[float, float]) -> bool:
    return math.isfinite(xy[0]) and math.isfinite(xy[1])


def _confidence_usable(confidence: float | None) -> bool:
    if confidence is None:
        return True
    return math.isfinite(confidence) and 0.0 <= confidence <= 1.0


def classify_correspondences(
    matches: list[Correspondence], settings: VerificationSettings
) -> FilterOutcome:
    """Mark invalid, duplicate, and (optional) low-confidence items as non-candidates.

    Duplicate policy: exact equality of (source_xy, reference_xy). The first
    occurrence may be a candidate; later exact duplicates are rejected. This is
    exact-tuple software deduplication, not a spatial tolerance.

    confidence is None: the optional confidence_min gate is skipped for that item.
    """

    candidate: list[int] = []
    rejected: list[int] = []
    seen: set[tuple[tuple[float, float], tuple[float, float]]] = set()

    for index, item in enumerate(matches):
        if not _finite_xy(item.source_xy) or not _finite_xy(item.reference_xy):
            rejected.append(index)
            continue
        if not _confidence_usable(item.confidence):
            rejected.append(index)
            continue
        if settings.confidence_min is not None and item.confidence is not None:
            if item.confidence < settings.confidence_min:
                rejected.append(index)
                continue
        key = (item.source_xy, item.reference_xy)
        if key in seen:
            rejected.append(index)
            continue
        seen.add(key)
        candidate.append(index)

    return FilterOutcome(candidate_indices=tuple(candidate), rejected_indices=tuple(rejected))
