"""Engineering settings for the illumination-normalization representation.

These values exist so the representation can run without inventing
sensor-specific constants at call sites. They are not scientifically
validated lunar Sun-angle corrections and must not be copied into
``configs/default.yaml`` as routing thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass

REPRESENTATION_ID = "illumination"

# Robust global stretch of finite samples. ENGINEERING DEFAULT only.
UNVALIDATED_ENABLE_ROBUST_INTENSITY = True
UNVALIDATED_INTENSITY_LOW_PERCENTILE = 2.0
UNVALIDATED_INTENSITY_HIGH_PERCENTILE = 98.0
UNVALIDATED_OUTPUT_LOW = 0.0
UNVALIDATED_OUTPUT_HIGH = 1.0
UNVALIDATED_CLIP_TO_OUTPUT_RANGE = False

# Local relative contrast (nan-aware z-score). ENGINEERING DEFAULT on.
# Window size is an odd pixel count, not a GSD, band count, or CH-2 size.
UNVALIDATED_ENABLE_LOCAL_CONTRAST = True
UNVALIDATED_LOCAL_WINDOW_SIZE = 15
UNVALIDATED_MIN_LOCAL_STD = 1e-6
UNVALIDATED_MIN_LOCAL_COUNT = 2.0

# Map local-contrast values onto the same output interval as intensity.
UNVALIDATED_ENABLE_OUTPUT_STRETCH = True


@dataclass(frozen=True, slots=True)
class IlluminationSettings:
    """Configuration for one illumination-normalization run.

    enable_robust_intensity
        Finite-sample percentile stretch before local contrast. Handles
        global gain/bias and differing numeric ranges. Not calibration.

    intensity_low_percentile / intensity_high_percentile
        Finite-sample percentiles that define the input range of the stretch.
        ENGINEERING DEFAULT 2 and 98. Not SIH or lunar-validated.

    output_low / output_high
        Mapped output values of the chosen percentiles. ENGINEERING DEFAULT
        [0, 1]. Used by the global stretch and by the optional output stretch.

    clip_to_output_range
        If True, clip after each stretch. ENGINEERING DEFAULT False so
        percentile tails are not flattened into a constant.

    enable_local_contrast
        Nan-aware local z-score. Intended to reduce spatially varying
        multiplicative/additive brightness. Does not model lunar incidence
        geometry or SPICE Sun angles.

    local_window_size
        Odd square window in pixels. Not a ground-sample distance and not a
        Chandrayaan-2 dimension.

    min_local_std
        Standard-deviation floor. Neighborhoods below this are treated as
        near-constant and mapped to the output midpoint.

    min_local_count
        Minimum finite samples in a window required to compute local stats.
        Below this, the centre pixel is treated as near-constant if valid.

    enable_output_stretch
        After local contrast, percentile-stretch finite z-scores onto
        [output_low, output_high] so downstream uint8 adapters see a bounded
        domain. Not a claim that SIFT then becomes illumination-invariant.
    """

    enable_robust_intensity: bool
    intensity_low_percentile: float
    intensity_high_percentile: float
    output_low: float
    output_high: float
    clip_to_output_range: bool
    enable_local_contrast: bool
    local_window_size: int
    min_local_std: float
    min_local_count: float
    enable_output_stretch: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.intensity_low_percentile < self.intensity_high_percentile <= 100.0:
            raise ValueError("intensity percentiles must satisfy 0 <= low < high <= 100")
        if not (self.output_high > self.output_low):
            raise ValueError("output_high must be > output_low")
        if self.local_window_size < 1 or self.local_window_size % 2 == 0:
            raise ValueError("local_window_size must be an odd integer >= 1")
        if not (self.min_local_std >= 0.0):
            raise ValueError("min_local_std must be >= 0")
        if not (self.min_local_count >= 1.0):
            raise ValueError("min_local_count must be >= 1")


def unvalidated_illumination_defaults() -> IlluminationSettings:
    """Engineering defaults used by the illumination representation."""

    return IlluminationSettings(
        enable_robust_intensity=UNVALIDATED_ENABLE_ROBUST_INTENSITY,
        intensity_low_percentile=UNVALIDATED_INTENSITY_LOW_PERCENTILE,
        intensity_high_percentile=UNVALIDATED_INTENSITY_HIGH_PERCENTILE,
        output_low=UNVALIDATED_OUTPUT_LOW,
        output_high=UNVALIDATED_OUTPUT_HIGH,
        clip_to_output_range=UNVALIDATED_CLIP_TO_OUTPUT_RANGE,
        enable_local_contrast=UNVALIDATED_ENABLE_LOCAL_CONTRAST,
        local_window_size=UNVALIDATED_LOCAL_WINDOW_SIZE,
        min_local_std=UNVALIDATED_MIN_LOCAL_STD,
        min_local_count=UNVALIDATED_MIN_LOCAL_COUNT,
        enable_output_stretch=UNVALIDATED_ENABLE_OUTPUT_STRETCH,
    )


__all__ = [
    "IlluminationSettings",
    "REPRESENTATION_ID",
    "unvalidated_illumination_defaults",
]
