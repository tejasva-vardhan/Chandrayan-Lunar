"""Adaptive routing. Owned by Chuba.

An explicit route() pipeline operation is not part of interface freeze v1 (M5).
Until then, routing logic lives behind generate_representation and match via the
two helper functions below.

Routing decisions
-----------------
difficulty=None or "easy"   -> intensity representation, sift matcher
difficulty="normal"         -> gradient representation, sift matcher
difficulty="difficult"      -> structural representation, sift matcher
                               (LightGlue/LoFTR integration is a future experiment)

These mappings are NOT final. They are unvalidated software defaults. The
controlled benchmark (EXP-001) will determine the real routing policy.

Do not encode numeric thresholds (gsd_ratio cut-offs, sun-angle cut-offs) here.
Those are experimental and must be evidence-driven (master spec §8).
"""

from __future__ import annotations

from src.models.registration_pair import RegistrationPair


def select_representation_id(pair: RegistrationPair) -> str:
    """Return a representation_id string based on pair characterization.

    This is an internal routing helper, not a frozen pipeline operation.

    Parameters
    ----------
    pair:
        The RegistrationPair. pair.characterization may be None.

    Returns
    -------
    str
        One of "intensity", "gradient", "structural".
        The string is a label only; it does not endorse a final method (D-007).
    """
    difficulty = None
    if pair.characterization is not None:
        difficulty = pair.characterization.difficulty

    if difficulty == "difficult":
        return "structural"
    if difficulty == "normal":
        return "gradient"
    # easy or unknown — default to intensity baseline
    return "intensity"


def select_matcher_id(pair: RegistrationPair) -> str:
    """Return a matcher_id string based on pair characterization.

    This is an internal routing helper, not a frozen pipeline operation.

    Parameters
    ----------
    pair:
        The RegistrationPair. pair.characterization may be None.

    Returns
    -------
    str
        A matcher label string. "sift" is the only implemented adapter.
        Future adapters: "rift", "lightglue", "loftr".
        The string is a label only; final selection requires EXP-001 (D-007).
    """
    # All difficulty levels route to SIFT until the benchmark selects another.
    # When LightGlue/LoFTR adapters are implemented, update this function.
    return "sift"


__all__ = ["select_matcher_id", "select_representation_id"]
