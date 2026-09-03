"""ORB matcher adapter.

Implements the same adapter shape as the SIFT baseline:
    run_orb(pair, representation, settings) -> CorrespondenceSet

ORB is included in EXP-001 as a zero-new-dependency third data point. It is
already available in the project's existing OpenCV dependency, it uses a
completely different detector (oriented FAST) and descriptor family (binary
rBRIEF, Hamming distance) from both SIFT and RIFT, and it is rotation aware.
Its role is to test whether *any* change of detector/descriptor moves verified
correspondence yield, not to be a proposed final matcher.

ORB is only partially scale invariant (an image pyramid, no continuous scale
selection) and its intensity-comparison descriptor is not designed for
radiation change, so it is expected to be weaker than SIFT on this data.
Recording that expectation before running is part of the controlled protocol.

Reference
---------
Rublee, E., Rabaud, V., Konolige, K., Bradski, G. (2011). ORB: An efficient
alternative to SIFT or SURF. ICCV, 2564-2571.
"""

from __future__ import annotations

import numpy as np

from src.matching.settings import OrbSettings
from src.matching.shared import (
    correspondences_from_matches,
    empty_set,
    matching_mask,
    matching_view_scale,
    representation_arrays,
    to_uint8,
)
from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult

MATCHER_ID = "orb"


def run_orb(
    pair: RegistrationPair,
    representation: RepresentationResult | None,
    settings: OrbSettings | None = None,
) -> CorrespondenceSet:
    """Run the ORB adapter and return a raw CorrespondenceSet."""

    import cv2

    cfg = settings or OrbSettings()
    source_array, reference_array = representation_arrays(pair, representation)
    if source_array is None or reference_array is None:
        return empty_set(pair, MATCHER_ID, representation)

    source_mask = matching_mask(representation, "source", source_array)
    reference_mask = matching_mask(representation, "reference", reference_array)
    source_scale = matching_view_scale(representation, "source")
    reference_scale = matching_view_scale(representation, "reference")

    detector = cv2.ORB_create(
        nfeatures=cfg.nfeatures,
        scaleFactor=cfg.scale_factor,
        nlevels=cfg.n_levels,
        edgeThreshold=cfg.edge_threshold,
        firstLevel=0,
        WTA_K=cfg.wta_k,
        patchSize=cfg.patch_size,
        fastThreshold=cfg.fast_threshold,
    )

    source_keypoints, source_descriptors = detector.detectAndCompute(
        to_uint8(source_array), source_mask
    )
    reference_keypoints, reference_descriptors = detector.detectAndCompute(
        to_uint8(reference_array), reference_mask
    )

    if (
        source_descriptors is None
        or reference_descriptors is None
        or len(source_keypoints) < 2
        or len(reference_keypoints) < 2
    ):
        return empty_set(pair, MATCHER_ID, representation)

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    knn = matcher.knnMatch(source_descriptors, reference_descriptors, k=2)

    source_points: list[tuple[float, float]] = []
    reference_points: list[tuple[float, float]] = []
    distances: list[float] = []
    for candidates in knn:
        if len(candidates) < 2:
            continue
        nearest, second = candidates
        if nearest.distance < cfg.ratio_threshold * second.distance:
            source_points.append(source_keypoints[nearest.queryIdx].pt)
            reference_points.append(reference_keypoints[nearest.trainIdx].pt)
            distances.append(float(nearest.distance))

    if len(distances) < cfg.min_matches:
        return empty_set(pair, MATCHER_ID, representation)

    return correspondences_from_matches(
        pair=pair,
        matcher_id=MATCHER_ID,
        representation=representation,
        source_xy=np.array(source_points, dtype=np.float64),
        reference_xy=np.array(reference_points, dtype=np.float64),
        distances=np.array(distances, dtype=np.float64),
        source_scale=source_scale,
        reference_scale=reference_scale,
    )


__all__ = ["MATCHER_ID", "run_orb"]
