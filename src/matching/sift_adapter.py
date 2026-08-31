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

References
----------
- Lowe, D.G. (2004). Distinctive image features from scale-invariant keypoints.
  IJCV 60(2), 91–110.
"""

from __future__ import annotations

import numpy as np

from src.matching.settings import SiftSettings
from src.models.correspondence_set import Correspondence, CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult


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
    src_arr, ref_arr = _get_arrays(pair, representation)

    if src_arr is None or ref_arr is None:
        # No image data available (missing raster_uri, non-RepresentationResult double).
        # Return empty set — not a crash condition, caller should handle LOW_CONFIDENCE.
        return CorrespondenceSet(
            pair_id=pair.pair_id,
            matcher_id="sift",
            matches=[],
            representation_id=_rep_id(representation),
        )

    # Convert to uint8 for SIFT.
    src_u8 = _to_uint8(src_arr)
    ref_u8 = _to_uint8(ref_arr)

    # --- Detect and describe ---
    sift = cv2.SIFT_create(
        nfeatures=cfg.nfeatures,
        nOctaveLayers=cfg.n_octave_layers,
        contrastThreshold=cfg.contrast_threshold,
        edgeThreshold=cfg.edge_threshold,
        sigma=cfg.sigma,
    )

    kp_src, desc_src = sift.detectAndCompute(src_u8, None)
    kp_ref, desc_ref = sift.detectAndCompute(ref_u8, None)

    quality_flags: list[str] = []

    if desc_src is None or desc_ref is None or len(kp_src) < 2 or len(kp_ref) < 2:
        quality_flags.append("insufficient_keypoints")
        return CorrespondenceSet(
            pair_id=pair.pair_id,
            matcher_id="sift",
            matches=[],
            representation_id=_rep_id(representation),
        )

    # --- Match with BFMatcher + ratio test ---
    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    raw_matches = bf.knnMatch(desc_src, desc_ref, k=2)

    good: list[tuple[float, tuple[float, float], tuple[float, float]]] = []
    for match_pair in raw_matches:
        if len(match_pair) < 2:
            continue
        m, n = match_pair
        if m.distance < cfg.ratio_threshold * n.distance:
            src_pt = kp_src[m.queryIdx].pt  # (x, y) pixel coordinates
            ref_pt = kp_ref[m.trainIdx].pt
            good.append((m.distance, src_pt, ref_pt))

    if len(good) < cfg.min_matches:
        quality_flags.append(f"too_few_matches_after_ratio_test:{len(good)}")
        return CorrespondenceSet(
            pair_id=pair.pair_id,
            matcher_id="sift",
            matches=[],
            representation_id=_rep_id(representation),
        )

    # --- Normalise confidence ---
    distances = np.array([d for d, _, _ in good], dtype=np.float32)
    max_dist = float(distances.max())

    correspondences: list[Correspondence] = []
    for dist, src_pt, ref_pt in good:
        if max_dist > 0.0:
            # confidence: closer match → higher confidence
            conf: float | None = float(1.0 - dist / max_dist)
            conf = max(0.0, min(1.0, conf))
        else:
            conf = None  # All distances are 0 — cannot normalise meaningfully.

        correspondences.append(
            Correspondence(
                source_xy=(float(src_pt[0]), float(src_pt[1])),
                reference_xy=(float(ref_pt[0]), float(ref_pt[1])),
                confidence=conf,
                status="raw",
            )
        )

    return CorrespondenceSet(
        pair_id=pair.pair_id,
        matcher_id="sift",
        matches=correspondences,
        representation_id=_rep_id(representation),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_arrays(
    pair: RegistrationPair,
    representation: RepresentationResult | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (source_array, reference_array) as float32.

    Accepts a RepresentationResult or falls back to loading from raster_uri.
    If representation is a non-RepresentationResult object (e.g. a wiring
    double or future adapter type), it is treated as if it were None and the
    loader fallback is used.
    """
    if isinstance(representation, RepresentationResult):
        # Skip the sentinel result returned when raster_uri was absent.
        if representation.metadata.get("no_raster_uri"):
            return None, None  # type: ignore[return-value]

        src_arr = representation.array
        ref_arr = representation.metadata.get("reference_array")
        if ref_arr is None:
            raise ValueError(
                "RepresentationResult.metadata['reference_array'] is missing. "
                "generate_representation() should populate this key."
            )
        return src_arr, ref_arr  # type: ignore[return-value]

    # Fallback: load intensity from raster_uri directly.
    source_uri = pair.source.raster_uri
    reference_uri = pair.reference.raster_uri
    if source_uri is None or reference_uri is None:
        # Cannot load images — caller handles the None return by returning empty set.
        return None, None  # type: ignore[return-value]
    from src.representation._loader import load_array

    return load_array(source_uri), load_array(reference_uri)


def _to_uint8(arr: np.ndarray) -> np.ndarray:
    """Convert float32 [0, 1] array to uint8 [0, 255] for OpenCV."""
    return (arr * 255.0).clip(0, 255).astype(np.uint8)


def _rep_id(representation: RepresentationResult | None) -> str | None:
    return representation.representation_id if representation is not None else None
