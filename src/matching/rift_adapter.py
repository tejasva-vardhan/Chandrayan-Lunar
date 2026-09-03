"""RIFT matcher adapter (radiation-variation insensitive feature transform).

Implements the same adapter shape as the SIFT baseline:
    run_rift(pair, representation, settings) -> CorrespondenceSet

RIFT replaces intensity gradients with phase congruency and the Maximum Index
Map (MIM), which are invariant to contrast, brightness, and contrast reversal.
That is the property EXP-001 is testing: whether an illumination/appearance
robust matcher recovers more verified correspondences than SIFT on
OHRC <-> LROC pairs.

Algorithm
---------
1. Phase congruency over a log-Gabor bank (see ``phase_congruency``), giving
   maximum/minimum moment maps and the MIM.
2. FAST corner detection on both moment maps, merged and capped by response.
3. Per keypoint, a ``grid x grid`` spatial histogram of MIM index values,
   giving a ``grid * grid * n_orient`` descriptor, SIFT-style normalised.
4. Rotation handling: rotating an image permutes the log-Gabor orientation
   channels cyclically, which for this descriptor is exactly a cyclic
   permutation of its channel axis. All ``n_orient`` permutations of the
   source descriptors are matched against the reference descriptors and the
   permutation yielding the most ratio-test survivors is returned.
5. Brute-force L2 matching with Lowe's ratio test, using the same ratio
   threshold as the SIFT baseline so the comparison stays controlled.

Implemented limitations (measured by ``tests/scientific/test_synthetic_rift.py``)
--------------------------------------------------------------------------------
- **Not scale invariant.** The descriptor patch is a fixed pixel size, so a
  residual scale difference between the two matching views is not absorbed.
  SIFT, by contrast, is scale invariant. This is a real confounder for
  OHRC <-> LROC and is recorded in the EXP-001 limitations.
- **Rotation is handled in the orientation-channel axis only.** The spatial
  layout of the descriptor grid is not resampled at the candidate angle, so
  rotation tolerance is partial rather than exact. The synthetic tests
  measure how much rotation actually survives instead of asserting a claim.

Reference
---------
Li, J., Hu, Q., Ai, M. (2020). RIFT: Multi-modal image matching based on
radiation-variation insensitive feature transform. IEEE Transactions on
Image Processing 29, 3296-3310.
"""

from __future__ import annotations

import numpy as np

from src.matching.phase_congruency import PhaseCongruencyResult, phase_congruency
from src.matching.settings import RiftSettings
from src.matching.shared import (
    correspondences_from_matches,
    empty_set,
    matching_mask,
    matching_view_scale,
    representation_arrays,
)
from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult

MATCHER_ID = "rift"


def run_rift(
    pair: RegistrationPair,
    representation: RepresentationResult | None,
    settings: RiftSettings | None = None,
) -> CorrespondenceSet:
    """Run the RIFT adapter and return a raw CorrespondenceSet.

    Coordinates are mapped back to original image pixels with the same
    matching-view scale rule the SIFT adapter uses, so downstream stages see
    the same coordinate convention regardless of matcher.
    """

    cfg = settings or RiftSettings()
    source_array, reference_array = representation_arrays(pair, representation)
    if source_array is None or reference_array is None:
        return empty_set(pair, MATCHER_ID, representation)

    source_mask = matching_mask(representation, "source", source_array)
    reference_mask = matching_mask(representation, "reference", reference_array)
    source_scale = matching_view_scale(representation, "source")
    reference_scale = matching_view_scale(representation, "reference")

    source_pc = phase_congruency(source_array, cfg.log_gabor)
    reference_pc = phase_congruency(reference_array, cfg.log_gabor)

    source_points = _detect_keypoints(source_pc, source_mask, cfg)
    reference_points = _detect_keypoints(reference_pc, reference_mask, cfg)
    if len(source_points) < 2 or len(reference_points) < 2:
        return empty_set(pair, MATCHER_ID, representation)

    source_descriptors = _describe(source_pc, source_points, cfg)
    reference_descriptors = _describe(reference_pc, reference_points, cfg)
    if source_descriptors.shape[0] < 2 or reference_descriptors.shape[0] < 2:
        return empty_set(pair, MATCHER_ID, representation)

    best = _match_over_rotations(source_descriptors, reference_descriptors, cfg)
    if best is None or len(best[0]) < cfg.min_matches:
        return empty_set(pair, MATCHER_ID, representation)

    pairs, distances, _ = best
    return correspondences_from_matches(
        pair=pair,
        matcher_id=MATCHER_ID,
        representation=representation,
        source_xy=source_points[pairs[:, 0]],
        reference_xy=reference_points[pairs[:, 1]],
        distances=distances,
        source_scale=source_scale,
        reference_scale=reference_scale,
    )


def selected_rotation_index(
    source: np.ndarray,
    reference: np.ndarray,
    settings: RiftSettings,
) -> int | None:
    """Rotation permutation RIFT would select for two images. Diagnostics only."""

    cfg = settings
    source_pc = phase_congruency(np.asarray(source, dtype=np.float32), cfg.log_gabor)
    reference_pc = phase_congruency(np.asarray(reference, dtype=np.float32), cfg.log_gabor)
    source_points = _detect_keypoints(source_pc, None, cfg)
    reference_points = _detect_keypoints(reference_pc, None, cfg)
    if len(source_points) < 2 or len(reference_points) < 2:
        return None
    best = _match_over_rotations(
        _describe(source_pc, source_points, cfg),
        _describe(reference_pc, reference_points, cfg),
        cfg,
    )
    return None if best is None else best[2]


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _detect_keypoints(
    result: PhaseCongruencyResult,
    mask: np.ndarray | None,
    settings: RiftSettings,
) -> np.ndarray:
    """FAST keypoints on both phase-congruency moment maps, merged by response.

    The maximum moment behaves as an edge map and the minimum moment as a
    corner map, so RIFT samples both.
    """

    import cv2

    detector = cv2.FastFeatureDetector_create(
        threshold=settings.fast_threshold, nonmaxSuppression=True
    )
    margin = settings.patch_size // 2
    height, width = result.max_moment.shape

    collected: dict[tuple[int, int], float] = {}
    for moment in (result.max_moment, result.min_moment):
        image = _to_uint8(moment)
        for keypoint in detector.detect(image, mask):
            x = int(round(keypoint.pt[0]))
            y = int(round(keypoint.pt[1]))
            if x < margin or y < margin or x >= width - margin or y >= height - margin:
                continue
            if mask is not None and not mask[y, x]:
                continue
            key = (x, y)
            response = float(keypoint.response)
            if response > collected.get(key, -np.inf):
                collected[key] = response

    if not collected:
        return np.empty((0, 2), dtype=np.float32)

    # Deterministic ordering: strongest response first, then raster order.
    ordered = sorted(collected.items(), key=lambda item: (-item[1], item[0][1], item[0][0]))
    if settings.max_keypoints > 0:
        ordered = ordered[: settings.max_keypoints]
    return np.array([[x, y] for (x, y), _ in ordered], dtype=np.float32)


def _to_uint8(array: np.ndarray) -> np.ndarray:
    """Min-max scale a moment map into uint8 for the FAST detector."""

    finite = np.isfinite(array)
    if not finite.any():
        return np.zeros(array.shape, dtype=np.uint8)
    low = float(array[finite].min())
    high = float(array[finite].max())
    if high - low <= 0.0:
        return np.zeros(array.shape, dtype=np.uint8)
    scaled = (array - low) / (high - low)
    return (np.clip(scaled, 0.0, 1.0) * 255.0).astype(np.uint8)


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------


def _describe(
    result: PhaseCongruencyResult,
    points_xy: np.ndarray,
    settings: RiftSettings,
) -> np.ndarray:
    """MIM spatial-histogram descriptors, shape (n_points, grid^2 * n_orient).

    Cell histograms come from per-channel integral images so every keypoint
    and cell is computed with four array lookups instead of a Python loop.
    """

    if points_xy.shape[0] == 0:
        return np.zeros((0, _descriptor_length(settings, result.n_orient)), dtype=np.float32)

    grid = settings.descriptor_grid
    patch = settings.patch_size
    cell = patch // grid
    n_orient = result.n_orient

    integrals = _channel_integrals(result.maximum_index_map, n_orient)

    xs = points_xy[:, 0].astype(np.int64)
    ys = points_xy[:, 1].astype(np.int64)
    origin_x = xs - patch // 2
    origin_y = ys - patch // 2

    offsets = np.arange(grid + 1, dtype=np.int64) * cell
    # (n_points, grid+1) cell boundaries, then broadcast to (n_points, grid+1, grid+1).
    row_bounds = origin_y[:, None] + offsets[None, :]
    col_bounds = origin_x[:, None] + offsets[None, :]

    top = row_bounds[:, :-1, None]
    bottom = row_bounds[:, 1:, None]
    left = col_bounds[:, None, :-1]
    right = col_bounds[:, None, 1:]

    counts = (
        integrals[:, bottom, right]
        - integrals[:, top, right]
        - integrals[:, bottom, left]
        + integrals[:, top, left]
    )
    # counts: (n_orient, n_points, grid, grid) -> (n_points, grid, grid, n_orient)
    descriptors = np.transpose(counts, (1, 2, 3, 0)).reshape(points_xy.shape[0], -1)
    return _normalise(descriptors.astype(np.float32))


def _channel_integrals(index_map: np.ndarray, n_orient: int) -> np.ndarray:
    """Summed-area tables for each MIM channel, shape (n_orient, H+1, W+1)."""

    height, width = index_map.shape
    integrals = np.zeros((n_orient, height + 1, width + 1), dtype=np.float32)
    for channel in range(n_orient):
        occupancy = (index_map == channel).astype(np.float32)
        np.cumsum(occupancy, axis=0, out=occupancy)
        np.cumsum(occupancy, axis=1, out=occupancy)
        integrals[channel, 1:, 1:] = occupancy
    return integrals


def _normalise(descriptors: np.ndarray) -> np.ndarray:
    """SIFT-style L2 normalise, clip dominant bins, renormalise."""

    norms = np.linalg.norm(descriptors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    descriptors = descriptors / norms
    np.clip(descriptors, 0.0, 0.2, out=descriptors)
    norms = np.linalg.norm(descriptors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return (descriptors / norms).astype(np.float32)


def _descriptor_length(settings: RiftSettings, n_orient: int) -> int:
    return settings.descriptor_grid * settings.descriptor_grid * n_orient


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _match_over_rotations(
    source_descriptors: np.ndarray,
    reference_descriptors: np.ndarray,
    settings: RiftSettings,
) -> tuple[np.ndarray, np.ndarray, int] | None:
    """Ratio-test match under every channel permutation; keep the best one.

    Selection rule is fixed before the experiment: the permutation with the
    most ratio-test survivors wins, ties broken by the smallest index. The
    rule reads only matcher-internal counts, never verification outcomes.
    """

    n_orient = settings.log_gabor.n_orient
    best: tuple[np.ndarray, np.ndarray, int] | None = None
    best_count = -1

    for shift in range(n_orient):
        rotated = _permute_channels(source_descriptors, shift, settings, n_orient)
        pairs, distances = _ratio_test_match(
            rotated, reference_descriptors, settings.ratio_threshold
        )
        count = len(pairs)
        if count > best_count:
            best_count = count
            best = (pairs, distances, shift)

    if best is None or best_count <= 0:
        return None
    return best


def _permute_channels(
    descriptors: np.ndarray, shift: int, settings: RiftSettings, n_orient: int
) -> np.ndarray:
    """Cyclically permute the orientation axis of every descriptor cell.

    Rotating an image by ``shift * 180 / n_orient`` degrees maps log-Gabor
    orientation channel ``c`` to ``(c + shift) mod n_orient``, so the rotated
    descriptor is a channel roll of the unrotated one. No re-description is
    needed.
    """

    if shift == 0:
        return descriptors
    cells = settings.descriptor_grid * settings.descriptor_grid
    reshaped = descriptors.reshape(descriptors.shape[0], cells, n_orient)
    return np.roll(reshaped, shift, axis=2).reshape(descriptors.shape[0], -1)


def _ratio_test_match(
    source_descriptors: np.ndarray,
    reference_descriptors: np.ndarray,
    ratio_threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Brute-force L2 knn match with Lowe's ratio test."""

    import cv2

    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    knn = matcher.knnMatch(source_descriptors, reference_descriptors, k=2)

    indices: list[tuple[int, int]] = []
    distances: list[float] = []
    for candidates in knn:
        if len(candidates) < 2:
            continue
        nearest, second = candidates
        if nearest.distance < ratio_threshold * second.distance:
            indices.append((nearest.queryIdx, nearest.trainIdx))
            distances.append(float(nearest.distance))

    if not indices:
        return np.empty((0, 2), dtype=np.int64), np.empty((0,), dtype=np.float32)
    return np.array(indices, dtype=np.int64), np.array(distances, dtype=np.float32)


__all__ = ["MATCHER_ID", "run_rift", "selected_rotation_index"]
