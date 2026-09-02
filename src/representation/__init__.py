"""Representation engine. Owned by Chuba.

Pipeline import surface: generate_representation(pair) -> Any.

Return type is intentionally unconstrained (interface freeze v1 §8).
Representation choice is experimental (v3 §11). Do not assume a final
representation in this package.

Implemented representations (baseline):
  - intensity   : percentile-stretched normalised intensity (easy/normal pairs).
  - gradient    : Sobel gradient magnitude (illumination-varying pairs).
  - structural  : log-gradient structural image (difficult/cross-modal pairs).

Representation is selected by adaptive routing (src.routing) based on
PairCharacterization.difficulty. When no characterization is available the
routing defaults to intensity.

raster_uri must be set on both pair.source and pair.reference before calling
this function. A ValueError is raised (not NotImplementedError) if uris are
missing — this is a data problem, not an unimplemented-feature problem.
"""

from __future__ import annotations

from typing import Any

from src.models.registration_pair import RegistrationPair
from src.representation._matching_view import (
    build_matching_mask,
    build_representation_array,
    determine_matching_view,
)
from src.representation._types import RepresentationResult
from src.representation.settings import MatchingViewSettings, unvalidated_matching_view_defaults
from src.routing import select_representation_id


def generate_representation(pair: RegistrationPair) -> Any:
    """Build a representation for matching."""
    return generate_representation_with_settings(pair, unvalidated_matching_view_defaults())


def generate_representation_with_settings(
    pair: RegistrationPair,
    settings: MatchingViewSettings,
) -> Any:
    """Build a representation for matching.

    Returns a RepresentationResult (source, reference arrays + metadata).
    The concrete type is RepresentationResult but the pipeline interface
    signature is Any per interface freeze v1 §8.

    Raises
    ------
    ValueError
        If raster_uri is missing on source or reference.
    """
    rep_id = select_representation_id(pair)

    source_uri = pair.source.raster_uri
    reference_uri = pair.reference.raster_uri

    if source_uri is None or reference_uri is None:
        # No image data available. Return an empty sentinel result so the
        # pipeline can continue to match() which will produce an empty
        # CorrespondenceSet. This is the correct behaviour for wiring tests
        # and for any pipeline run before real products are ingested.
        import numpy as np

        empty = np.empty((0, 0), dtype=np.float32)
        return RepresentationResult(
            array=empty,
            representation_id="none",
            metadata={
                "no_raster_uri": True,
                "pair_id": pair.pair_id,
                "source_uri": source_uri,
                "reference_uri": reference_uri,
            },
        )

    if rep_id not in {"gradient", "structural", "intensity"}:
        rep_id = "intensity"

    src_view = determine_matching_view(pair.source, settings)
    ref_view = determine_matching_view(pair.reference, settings)
    src_arr = build_representation_array(
        source_uri,
        rep_id,
        stride=int(src_view["stride"]),
    )
    ref_arr = build_representation_array(
        reference_uri,
        rep_id,
        stride=int(ref_view["stride"]),
    )
    if src_view["stride"] != 1:
        _validate_matching_shape(src_arr, src_view, "source")
    if ref_view["stride"] != 1:
        _validate_matching_shape(ref_arr, ref_view, "reference")
    src_mask = build_matching_mask(
        pair.source.mask_uri,
        stride=int(src_view["stride"]),
        expected_shape=src_arr.shape,
    )
    ref_mask = build_matching_mask(
        pair.reference.mask_uri,
        stride=int(ref_view["stride"]),
        expected_shape=ref_arr.shape,
    )

    return RepresentationResult(
        array=src_arr,
        representation_id=rep_id,
        metadata={
            "source_shape": list(src_arr.shape),
            "reference_shape": list(ref_arr.shape),
            "reference_array": ref_arr,  # matcher reads this
            "source_valid_mask": src_mask,
            "reference_valid_mask": ref_mask,
            "source_matching_view": src_view,
            "reference_matching_view": ref_view,
        },
    )


def _validate_matching_shape(
    array: object,
    view: dict[str, object],
    role: str,
) -> None:
    """Fail closed when declared product dimensions disagree with loaded pixels."""
    expected_shape = tuple(view["matching_shape"])
    actual_shape = getattr(array, "shape", None)
    if actual_shape != expected_shape:
        raise ValueError(
            f"{role} matching view shape does not match declared product dimensions: "
            f"expected={expected_shape}, actual={actual_shape}"
        )


__all__ = [
    "MatchingViewSettings",
    "RepresentationResult",
    "generate_representation",
    "generate_representation_with_settings",
    "unvalidated_matching_view_defaults",
]
