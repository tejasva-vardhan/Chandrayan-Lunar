"""Matcher portfolio. Owned by Chuba.

Pipeline import surface: match(pair, representation) -> CorrespondenceSet.

The pipeline must not import a specific matcher from this package.
Matcher adapters live behind this function. matcher_id is a label, not a
final algorithm choice (D-007).

Implemented adapters
--------------------
sift  — SIFT baseline (EXP-000). Wired through this frozen surface.

EXP-001 comparison adapters live behind ``src.matching.portfolio.run_matcher``
and are deliberately *not* selected here (D-007):
rift  — in-repository RIFT (phase congruency + MIM).
orb   — ORB (oriented FAST + rBRIEF).

Blocked for EXP-001 (see experiments/EXP-001): LightGlue, LoFTR.

The adapter selected by this function is determined by
src.routing.select_matcher_id(), which currently always returns ``sift``.
"""

from __future__ import annotations

from typing import Any

from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.routing import select_matcher_id


def match(pair: RegistrationPair, representation: Any | None = None) -> CorrespondenceSet:
    """Run the wired matcher adapter. Do not assume which adapter is final.

    Parameters
    ----------
    pair:
        The source/reference pair.
    representation:
        Optional RepresentationResult from generate_representation().
        When provided, the adapter uses its arrays directly.
        When None, adapters that need image data load from raster_uri.

    Returns
    -------
    CorrespondenceSet
        Raw correspondences (status="raw"). Verification is Shaiz's stage.

    Raises
    ------
    ValueError
        If the selected matcher_id has no registered adapter.
    """
    matcher_id = select_matcher_id(pair)

    if matcher_id == "sift":
        from src.matching.sift_adapter import SiftSettings, run_sift

        return run_sift(pair, representation, settings=SiftSettings())

    # Future adapters:
    # if matcher_id == "rift":
    #     from src.matching.rift_adapter import run_rift
    #     return run_rift(pair, representation)
    # if matcher_id == "lightglue":
    #     from src.matching.lightglue_adapter import run_lightglue
    #     return run_lightglue(pair, representation)

    raise ValueError(
        f"No adapter registered for matcher_id={matcher_id!r}. "
        f"pair_id={pair.pair_id}. "
        f"Add the adapter to src/matching/ and wire it in match()."
    )


__all__ = ["match"]
