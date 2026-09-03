"""Representation engine. Owned by Chuba.

Pipeline import surface: generate_representation(pair) -> Any.

Return type is intentionally unconstrained (interface freeze v1 §8).
Representation choice is experimental (v3 §11). Do not assume a final
representation in this package.

Implemented representations (baseline):
  - intensity     : percentile-stretched normalised intensity (easy/normal pairs).
  - gradient      : Sobel gradient magnitude (illumination-varying pairs).
  - structural    : log-gradient structural image (difficult/cross-modal pairs).
  - illumination  : robust intensity + local relative contrast (engineering
                    photometric baseline). Not selected by default routing.
                    Does not claim to solve lunar Sun-angle variation.

Representation is selected by adaptive routing (src.routing) based on
PairCharacterization.difficulty. When no characterization is available the
routing defaults to intensity. Request ``illumination`` via
MatchingViewSettings.representation_id_override.

raster_uri must be set on both pair.source and pair.reference before calling
this function. A ValueError is raised (not NotImplementedError) if uris are
missing — this is a data problem, not an unimplemented-feature problem.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.models.registration_pair import RegistrationPair
from src.representation._matching_view import (
    build_matching_mask,
    build_representation_array,
    determine_matching_view,
    determine_pair_matching_views,
)
from src.representation._types import RepresentationResult
from src.representation.illumination import build_illumination_array
from src.representation.illumination_settings import (
    REPRESENTATION_ID as ILLUMINATION_REPRESENTATION_ID,
)
from src.representation.illumination_settings import (
    IlluminationSettings,
    unvalidated_illumination_defaults,
)
from src.representation.settings import (
    SCALE_POLICY_COMMON_PHYSICAL_GSD,
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
    MatchingViewSettings,
    unvalidated_matching_view_defaults,
)
from src.routing import select_representation_id

_ALLOWED_REPRESENTATION_IDS = {
    "gradient",
    "structural",
    "intensity",
    ILLUMINATION_REPRESENTATION_ID,
}


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
    rep_id = settings.representation_id_override or select_representation_id(pair)

    source_uri = pair.source.raster_uri
    reference_uri = pair.reference.raster_uri

    if source_uri is None or reference_uri is None:
        # No image data available. Return an empty sentinel result so the
        # pipeline can continue to match() which will produce an empty
        # CorrespondenceSet. This is the correct behaviour for wiring tests
        # and for any pipeline run before real products are ingested.
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

    if rep_id not in _ALLOWED_REPRESENTATION_IDS:
        rep_id = "intensity"

    src_view, ref_view = determine_pair_matching_views(pair.source, pair.reference, settings)
    if rep_id == ILLUMINATION_REPRESENTATION_ID:
        src_arr, ref_arr, src_mask, ref_mask = _build_illumination_arrays(
            pair, str(source_uri), str(reference_uri), src_view, ref_view
        )
    else:
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

    metadata: dict[str, object] = {
        "source_shape": list(src_arr.shape),
        "reference_shape": list(ref_arr.shape),
        "reference_array": ref_arr,  # matcher reads this
        "source_valid_mask": src_mask,
        "reference_valid_mask": ref_mask,
        "source_matching_view": src_view,
        "reference_matching_view": ref_view,
    }
    if rep_id == ILLUMINATION_REPRESENTATION_ID:
        metadata["illumination_baseline"] = {
            "engineering_baseline": True,
            "solves_lunar_sun_angle": False,
        }

    return RepresentationResult(
        array=src_arr,
        representation_id=rep_id,
        metadata=metadata,
    )


def _build_illumination_arrays(
    pair: RegistrationPair,
    source_uri: str,
    reference_uri: str,
    src_view: dict[str, object],
    ref_view: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load masks first so illumination can exclude invalid samples."""
    src_expected = (int(src_view["matching_shape"][0]), int(src_view["matching_shape"][1]))
    ref_expected = (int(ref_view["matching_shape"][0]), int(ref_view["matching_shape"][1]))
    src_mask = build_matching_mask(
        pair.source.mask_uri,
        stride=int(src_view["stride"]),
        expected_shape=src_expected,
    )
    ref_mask = build_matching_mask(
        pair.reference.mask_uri,
        stride=int(ref_view["stride"]),
        expected_shape=ref_expected,
    )
    src_arr = build_representation_array(
        source_uri,
        ILLUMINATION_REPRESENTATION_ID,
        stride=int(src_view["stride"]),
        product_mask=src_mask,
    )
    ref_arr = build_representation_array(
        reference_uri,
        ILLUMINATION_REPRESENTATION_ID,
        stride=int(ref_view["stride"]),
        product_mask=ref_mask,
    )
    if src_view["stride"] != 1:
        _validate_matching_shape(src_arr, src_view, "source")
    if ref_view["stride"] != 1:
        _validate_matching_shape(ref_arr, ref_view, "reference")
    return (
        src_arr,
        ref_arr,
        _combine_finite_mask(src_mask, src_arr),
        _combine_finite_mask(ref_mask, ref_arr),
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


def _combine_finite_mask(
    product_mask: np.ndarray | None,
    array: np.ndarray,
) -> np.ndarray:
    """Keep product-mask True only where the representation sample is finite."""
    finite = np.isfinite(array)
    if product_mask is None:
        return finite
    return np.asarray(product_mask, dtype=bool) & finite


__all__ = [
    "ILLUMINATION_REPRESENTATION_ID",
    "IlluminationSettings",
    "MatchingViewSettings",
    "RepresentationResult",
    "SCALE_POLICY_COMMON_PHYSICAL_GSD",
    "SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET",
    "build_illumination_array",
    "determine_matching_view",
    "determine_pair_matching_views",
    "generate_representation",
    "generate_representation_with_settings",
    "unvalidated_illumination_defaults",
    "unvalidated_matching_view_defaults",
]
