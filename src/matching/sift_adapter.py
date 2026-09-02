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
    src_mask = _matching_mask(representation, "source", src_arr)
    ref_mask = _matching_mask(representation, "reference", ref_arr)
    src_scale = _matching_view_scale(representation, "source")
    ref_scale = _matching_view_scale(representation, "reference")

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

    kp_src, desc_src = sift.detectAndCompute(src_u8, src_mask)
    kp_ref, desc_ref = sift.detectAndCompute(ref_u8, ref_mask)

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
            src_pt = _map_point_to_original(kp_src[m.queryIdx].pt, src_scale)
            ref_pt = _map_point_to_original(kp_ref[m.trainIdx].pt, ref_scale)
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


def _matching_view_scale(
    representation: RepresentationResult | None,
    role: str,
) -> tuple[float, float]:
    if not isinstance(representation, RepresentationResult):
        return 1.0, 1.0

    view = representation.metadata.get(f"{role}_matching_view")
    if not isinstance(view, dict):
        return 1.0, 1.0

    x_scale = float(view.get("x_scale", 1.0))
    y_scale = float(view.get("y_scale", 1.0))
    if not np.isfinite(x_scale) or not np.isfinite(y_scale) or x_scale <= 0 or y_scale <= 0:
        raise ValueError(f"invalid {role} matching-view coordinate scale")
    return x_scale, y_scale


def _matching_mask(
    representation: RepresentationResult | None,
    role: str,
    array: np.ndarray | None,
) -> np.ndarray | None:
    """Return an OpenCV-compatible validity mask for a matching view."""
    if array is None or not isinstance(representation, RepresentationResult):
        return None

    mask = representation.metadata.get(f"{role}_valid_mask")
    if mask is None:
        return None
    if not isinstance(mask, np.ndarray) or mask.shape != array.shape:
        raise ValueError(f"{role} valid mask does not match its matching view")
    return (mask.astype(np.uint8, copy=False) * 255)


def _map_point_to_original(
    point_xy: tuple[float, float],
    scale_xy: tuple[float, float],
) -> tuple[float, float]:
    x_scale, y_scale = scale_xy
    return float(point_xy[0] * x_scale), float(point_xy[1] * y_scale)
