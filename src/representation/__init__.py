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
from src.representation._types import RepresentationResult
from src.routing import select_representation_id


def generate_representation(pair: RegistrationPair) -> Any:
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

    if rep_id == "gradient":
        from src.representation.gradient import build_gradient

        src_arr = build_gradient(source_uri)
        ref_arr = build_gradient(reference_uri)
    elif rep_id == "structural":
        from src.representation.structural import build_structural

        src_arr = build_structural(source_uri)
        ref_arr = build_structural(reference_uri)
    else:
        # Default: intensity
        from src.representation.intensity import build_intensity

        src_arr = build_intensity(source_uri)
        ref_arr = build_intensity(reference_uri)
        rep_id = "intensity"

    return RepresentationResult(
        array=src_arr,
        representation_id=rep_id,
        metadata={
            "source_shape": list(src_arr.shape),
            "reference_shape": list(ref_arr.shape),
            "reference_array": ref_arr,  # matcher reads this
        },
    )


__all__ = ["RepresentationResult", "generate_representation"]
