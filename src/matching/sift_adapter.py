"""SIFT/ASIFT matcher adapter. Owned by Chuba.

Implements the frozen pipeline interface:
    match(pair, representation) -> CorrespondenceSet

This adapter is a BASELINE, not the final method (D-007). Performance on
actual Chandrayaan-2 / LRO pairs must be measured in EXP-000 before drawing
any conclusions.

Algorithm
---------
1. Obtain source and reference arrays from the RepresentationResult.
2. Convert to uint8 (SIFT operates on uint8 in OpenCV).
3. Detect keypoints and compute descriptors with cv2.SIFT.
4. Match descriptors using BFMatcher (L2 norm) with k=2 nearest neighbours.
5. Apply Lowe's ratio test (Lowe 2004, IJCV) to filter ambiguous matches.
6. Normalise distance-based confidence to [0, 1].
7. Return a CorrespondenceSet with all raw matches (status="raw").

Verification (RANSAC etc.) is Shaiz's responsibility via src.verification.

Array access, mask handling, matching-view coordinate mapping, and confidence
normalisation live in src.matching.shared so that every EXP-001 adapter uses
one identical implementation of each. Behaviour is unchanged.

References
----------
- Lowe, D.G. (2004). Distinctive image features from scale-invariant keypoints.
  IJCV 60(2), 91-110.
"""

from __future__ import annotations

import numpy as np

from src.matching.settings import SiftSettings
from src.matching.shared import (
    correspondences_from_matches,
    empty_set,
    map_point_to_original,
    matching_mask,
    matching_view_scale,
    representation_arrays,
    to_uint8,
)
from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult

MATCHER_ID = "sift"


def run_sift(
    pair: RegistrationPair,
    representation: RepresentationResult | None,
    settings: SiftSettings | None = None,
) -> CorrespondenceSet:
    """Run the SIFT adapter and return a raw CorrespondenceSet.

    Parameters
    ----------
    pair:
        The source/reference pair. Used only for pair_id and raster URIs
        (fallback when representation is None).
    representation:
        Output of generate_representation(). Must be a RepresentationResult
        with source array in .array and reference array in .metadata["reference_array"].
        If None, the adapter loads intensity arrays directly from raster_uri.
    settings:
        SiftSettings instance. If None, uses software defaults.

    Returns
    -------
    CorrespondenceSet
        All raw matches after Lowe's ratio test. status="raw" on all items.
        Empty matches list if fewer than settings.min_matches survive.

    Raises
    ------
    ValueError
        If raster_uri is missing and representation is also None (cannot load images).
    ImportError
        If OpenCV is not installed (cv2 import fails).
    """
    try:
        import cv2
    except ImportError as exc:
        raise ImportError(
            "opencv-python-headless is required for the SIFT adapter. "
            "Install it: pip install opencv-python-headless"
        ) from exc

    cfg = settings or SiftSettings()

    # --- Obtain image arrays ---
    src_arr, ref_arr = representation_arrays(pair, representation)
    src_mask = matching_mask(representation, "source", src_arr)
    ref_mask = matching_mask(representation, "reference", ref_arr)
    src_scale = matching_view_scale(representation, "source")
    ref_scale = matching_view_scale(representation, "reference")

    if src_arr is None or ref_arr is None:
        # No image data available (missing raster_uri, non-RepresentationResult double).
        # Return empty set — not a crash condition, caller should handle LOW_CONFIDENCE.
        return empty_set(pair, MATCHER_ID, representation)

    # Convert to uint8 for SIFT.
    src_u8 = to_uint8(src_arr)
    ref_u8 = to_uint8(ref_arr)

    # --- Detect and describe ---
    sift = cv2.SIFT_create(
        nfeatures=cfg.nfeatures,
        nOctaveLayers=cfg.n_octave_layers,
        contrastThreshold=cfg.contrast_threshold,
        edgeThreshold=cfg.edge_threshold,
        sigma=cfg.sigma,
    )

    kp_src, desc_src = sift.detectAndCompute(src_u8, src_mask)
    kp_ref, desc_ref = sift.detectAndCompute(ref_u8, ref_mask)

    if desc_src is None or desc_ref is None or len(kp_src) < 2 or len(kp_ref) < 2:
        return empty_set(pair, MATCHER_ID, representation)

    # --- Match with BFMatcher + ratio test ---
    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    raw_matches = bf.knnMatch(desc_src, desc_ref, k=2)

    source_points: list[tuple[float, float]] = []
    reference_points: list[tuple[float, float]] = []
    distances: list[float] = []
    for match_pair in raw_matches:
        if len(match_pair) < 2:
            continue
        m, n = match_pair
        if m.distance < cfg.ratio_threshold * n.distance:
            source_points.append(kp_src[m.queryIdx].pt)
            reference_points.append(kp_ref[m.trainIdx].pt)
            distances.append(float(m.distance))

    if len(distances) < cfg.min_matches:
        return empty_set(pair, MATCHER_ID, representation)

    return correspondences_from_matches(
        pair=pair,
        matcher_id=MATCHER_ID,
        representation=representation,
        source_xy=np.array(source_points, dtype=np.float64),
        reference_xy=np.array(reference_points, dtype=np.float64),
        distances=np.array(distances, dtype=np.float64),
        source_scale=src_scale,
        reference_scale=ref_scale,
    )


def _map_point_to_original(
    point_xy: tuple[float, float],
    scale_xy: tuple[float, float],
) -> tuple[float, float]:
    """Kept for the existing synthetic matching tests. Prefer ``map_point_to_original``."""

    return map_point_to_original(point_xy, scale_xy)


__all__ = ["MATCHER_ID", "SiftSettings", "run_sift"]
