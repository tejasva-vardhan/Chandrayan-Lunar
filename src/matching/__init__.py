"""Matcher portfolio. Owned by Chuba.

Pipeline import surface: match(pair, representation) -> CorrespondenceSet.

The pipeline must not import a specific matcher from this package.
Matcher adapters live behind this function. matcher_id is a label, not a
final algorithm choice (D-007).
"""

from __future__ import annotations

from typing import Any

from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair


def match(pair: RegistrationPair, representation: Any | None = None) -> CorrespondenceSet:
    """Run the wired matcher adapter. Do not assume which adapter is final."""
    raise NotImplementedError(
        f"match is not implemented. pair_id={pair.pair_id} representation={representation!r}"
    )


__all__ = ["match"]
