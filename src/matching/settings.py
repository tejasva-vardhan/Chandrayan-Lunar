"""Matcher settings.

Settings are software defaults only. Do not treat these as SIH-validated
or lunar-validated parameters. The controlled benchmark (EXP-000, EXP-001)
will determine whether these defaults are appropriate.

EXP-001 fairness rule
---------------------
``ratio_threshold`` and ``min_matches`` are deliberately identical across
every adapter. They are protocol parameters of the comparison, not matcher
parameters, so holding them constant is what makes the yields comparable.
Only genuinely matcher-native parameters differ between the classes below,
and every one of them was fixed before any matcher was run on real data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.matching.phase_congruency import LogGaborSettings

# Held constant across all EXP-001 matchers. Lowe (2004) standard value.
SHARED_RATIO_THRESHOLD = 0.75

# Minimum raw matches an adapter must produce before returning a result.
# Equal to the projective DLT minimum sample size.
SHARED_MIN_MATCHES = 4


@dataclass
class SiftSettings:
    """Tunable SIFT parameters.

    nfeatures:
        Maximum number of features to retain per image. 0 = no limit.
        Increase for high-resolution images; decrease for speed.
    n_octave_layers:
        Number of layers per octave in the scale-space pyramid.
        OpenCV default is 3.
    contrast_threshold:
        Filter threshold for weak features in low-contrast regions.
        Lower = more features (noisier). OpenCV default 0.04.
    edge_threshold:
        Filter threshold for edge-like regions.
        Higher = more features retained near edges. OpenCV default 10.
    sigma:
        Gaussian sigma applied to the input image at the first octave.
        OpenCV default 1.6.
    ratio_threshold:
        Lowe's ratio test threshold. Matches where
        best_dist / second_best_dist > ratio_threshold are discarded.
        0.75 is the standard Lowe (2004) value; lower = stricter.
    min_matches:
        Minimum number of raw matches required before returning an empty set.
        If fewer raw matches exist after ratio test, an empty CorrespondenceSet
        is returned with a quality flag.
    """

    nfeatures: int = 0
    n_octave_layers: int = 3
    contrast_threshold: float = 0.04
    edge_threshold: float = 10.0
    sigma: float = 1.6
    ratio_threshold: float = SHARED_RATIO_THRESHOLD
    min_matches: int = SHARED_MIN_MATCHES


@dataclass(frozen=True, slots=True)
class RiftSettings:
    """RIFT parameters. Published defaults, fixed before the EXP-001 run.

    log_gabor:
        Phase-congruency filter bank. ``n_orient`` also sets the number of
        MIM channels and therefore the descriptor's channel count.
    fast_threshold:
        FAST intensity threshold applied to the min-max scaled phase
        congruency moment maps. OpenCV's default is 10.
    max_keypoints:
        Cap on retained keypoints per image, strongest response first.
        Chosen to be generous rather than selective; 0 disables the cap.
    patch_size:
        Side length in pixels of the square MIM patch described per
        keypoint. RIFT's published value is 96.
    descriptor_grid:
        Number of cells per descriptor axis. RIFT's published value is 6,
        giving a 6*6*n_orient descriptor (216 dimensions at n_orient=6).
    ratio_threshold, min_matches:
        Held identical to every other adapter. See the module docstring.
    """

    log_gabor: LogGaborSettings = field(default_factory=LogGaborSettings)
    fast_threshold: int = 10
    max_keypoints: int = 20000
    patch_size: int = 96
    descriptor_grid: int = 6
    ratio_threshold: float = SHARED_RATIO_THRESHOLD
    min_matches: int = SHARED_MIN_MATCHES

    def __post_init__(self) -> None:
        if self.patch_size <= 0 or self.descriptor_grid <= 0:
            raise ValueError("patch_size and descriptor_grid must be positive")
        if self.patch_size % self.descriptor_grid:
            raise ValueError("patch_size must be divisible by descriptor_grid")
        if self.max_keypoints < 0:
            raise ValueError("max_keypoints must be >= 0")


@dataclass(frozen=True, slots=True)
class OrbSettings:
    """ORB parameters. OpenCV defaults except the feature cap.

    nfeatures:
        OpenCV's default of 500 would cap ORB far below the unlimited
        detection SIFT gets from ``nfeatures=0``, which would make the
        comparison unfair by construction rather than by measurement. It is
        raised to 20000 for approximate parity with RIFT's keypoint cap.
        Chosen before the first real-data run and not revisited afterwards.
    scale_factor, n_levels:
        Image pyramid geometry. OpenCV defaults.
    edge_threshold, patch_size:
        Border size excluded from detection and the descriptor patch size.
        OpenCV defaults; they must stay equal.
    wta_k:
        Points used per rBRIEF comparison. 2 keeps the descriptor binary and
        Hamming-matchable.
    fast_threshold:
        FAST intensity threshold. OpenCV default.
    ratio_threshold, min_matches:
        Held identical to every other adapter. See the module docstring.
    """

    nfeatures: int = 20000
    scale_factor: float = 1.2
    n_levels: int = 8
    edge_threshold: int = 31
    wta_k: int = 2
    patch_size: int = 31
    fast_threshold: int = 20
    ratio_threshold: float = SHARED_RATIO_THRESHOLD
    min_matches: int = SHARED_MIN_MATCHES

    def __post_init__(self) -> None:
        if self.nfeatures <= 0:
            raise ValueError("nfeatures must be > 0")
        if self.scale_factor <= 1.0:
            raise ValueError("scale_factor must be > 1")
        if self.n_levels < 1:
            raise ValueError("n_levels must be >= 1")


@dataclass(frozen=True, slots=True)
class CoarseToFineSettings:
    """Fixed engineering defaults for tiled multi-scale SIFT.

    These values were chosen before the pair_02 run. They are not SIH
    thresholds and must not be retuned after seeing a real-data result.
    """

    fine_stride_factor: float = 0.5
    max_pixels_per_tile: int = 4_194_304
    max_fine_tiles: int = 4
    bbox_expand_fraction: float = 0.25
    tile_overlap_fraction: float = 0.125
    reference_margin_fraction: float = 0.20
    reference_margin_min_px: int = 256
    max_matches_per_tile: int = 200
    dedup_radius_px: float = 8.0
    coarse_min_inliers: int = 5
    min_tile_matching_side: int = 32

    def __post_init__(self) -> None:
        if self.fine_stride_factor <= 0.0 or self.fine_stride_factor > 1.0:
            raise ValueError("fine_stride_factor must be in (0, 1]")
        if self.max_pixels_per_tile <= 0:
            raise ValueError("max_pixels_per_tile must be positive")
        if self.max_fine_tiles < 1:
            raise ValueError("max_fine_tiles must be >= 1")
        if self.bbox_expand_fraction < 0.0:
            raise ValueError("bbox_expand_fraction must be >= 0")
        if not 0.0 <= self.tile_overlap_fraction < 1.0:
            raise ValueError("tile_overlap_fraction must be in [0, 1)")
        if self.reference_margin_fraction < 0.0:
            raise ValueError("reference_margin_fraction must be >= 0")
        if self.reference_margin_min_px < 0:
            raise ValueError("reference_margin_min_px must be >= 0")
        if self.max_matches_per_tile < 1:
            raise ValueError("max_matches_per_tile must be >= 1")
        if self.dedup_radius_px < 0.0:
            raise ValueError("dedup_radius_px must be >= 0")
        if self.coarse_min_inliers < 5:
            raise ValueError("coarse_min_inliers must be >= 5")
        if self.min_tile_matching_side < 1:
            raise ValueError("min_tile_matching_side must be >= 1")
