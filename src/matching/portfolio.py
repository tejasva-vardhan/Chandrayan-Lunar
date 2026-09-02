"""Explicit matcher dispatch for controlled experiments.

The frozen pipeline surface is ``match(pair, representation)``, which asks
``src.routing.select_matcher_id`` which adapter to use and currently always
answers ``"sift"``. A matcher comparison cannot go through that surface,
because the whole point is to choose the matcher rather than let routing
choose it.

This module therefore adds an experiment-facing entry point beside the frozen
one. It does not modify ``match()``, ``select_matcher_id``, or any adapter
signature. Production code keeps using ``match()``; only EXP-001 and its tests
use ``run_matcher``. ``run_matcher("sift", ...)`` is asserted to return exactly
what ``match()`` returns, so the baseline arm of the comparison really is the
EXP-000 code path.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.matching.orb_adapter import run_orb
from src.matching.rift_adapter import run_rift
from src.matching.settings import OrbSettings, RiftSettings, SiftSettings
from src.matching.sift_adapter import run_sift
from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult

MATCHER_SIFT = "sift"
MATCHER_RIFT = "rift"
MATCHER_ORB = "orb"

# Order is the EXP-001 reporting order: baseline first, then the
# illumination/appearance-robust candidates.
PORTFOLIO_MATCHER_IDS: tuple[str, ...] = (MATCHER_SIFT, MATCHER_RIFT, MATCHER_ORB)


def default_settings(matcher_id: str) -> Any:
    """Return the documented default settings object for one matcher."""

    if matcher_id == MATCHER_SIFT:
        return SiftSettings()
    if matcher_id == MATCHER_RIFT:
        return RiftSettings()
    if matcher_id == MATCHER_ORB:
        return OrbSettings()
    raise ValueError(_unknown_message(matcher_id))


def matcher_parameters(matcher_id: str) -> dict[str, Any]:
    """JSON-ready snapshot of a matcher's native parameters, for the record."""

    return asdict(default_settings(matcher_id))


def run_matcher(
    matcher_id: str,
    pair: RegistrationPair,
    representation: RepresentationResult | None = None,
    settings: Any | None = None,
) -> CorrespondenceSet:
    """Run one named adapter directly.

    Parameters
    ----------
    matcher_id:
        One of ``PORTFOLIO_MATCHER_IDS``.
    pair:
        The source/reference pair.
    representation:
        Output of ``generate_representation()``. EXP-001 builds this once per
        pair and reuses it for every matcher, so the matching view, stride,
        coordinate mapping, and validity masks are provably identical across
        the comparison.
    settings:
        Matcher-native settings. Defaults to ``default_settings(matcher_id)``.

    Returns
    -------
    CorrespondenceSet
        Raw correspondences in original image pixel coordinates.

    Raises
    ------
    ValueError
        If matcher_id has no registered adapter.
    """

    resolved = settings if settings is not None else default_settings(matcher_id)

    if matcher_id == MATCHER_SIFT:
        return run_sift(pair, representation, settings=resolved)
    if matcher_id == MATCHER_RIFT:
        return run_rift(pair, representation, settings=resolved)
    if matcher_id == MATCHER_ORB:
        return run_orb(pair, representation, settings=resolved)
    raise ValueError(_unknown_message(matcher_id))


def _unknown_message(matcher_id: str) -> str:
    known = ", ".join(PORTFOLIO_MATCHER_IDS)
    return f"No adapter registered for matcher_id={matcher_id!r}; known: {known}"


__all__ = [
    "MATCHER_ORB",
    "MATCHER_RIFT",
    "MATCHER_SIFT",
    "PORTFOLIO_MATCHER_IDS",
    "default_settings",
    "matcher_parameters",
    "run_matcher",
]
