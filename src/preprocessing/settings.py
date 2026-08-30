"""Experimental preprocessing settings. Not a scientific freeze.

The frozen callable is preprocess(pair). It has no settings argument, so
software defaults are required for the two-argument API. Those values are
engineering/test defaults only.

They are NOT:
  - SIH thresholds
  - lunar-validated parameters
  - a final Chandrayaan-2 preprocessing configuration
  - multimodal OHRC/IIRS/TMC-2 radiometric calibration
  - matcher-specific policy

Do not copy these into configs/default.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Frozen one-argument API: engineering defaults only ---
# preprocess(pair) has no settings argument. These values exist ONLY so
# that callable can run.

# Percentile stretch of finite samples onto [0, 1]. ENGINEERING DEFAULT
# so a matcher sees a bounded numeric domain. Not a scientifically
# validated lunar radiometric transform.
UNVALIDATED_SOFTWARE_ENABLE_INTENSITY = True
UNVALIDATED_SOFTWARE_INTENSITY_LOW_PERCENTILE = 2.0
UNVALIDATED_SOFTWARE_INTENSITY_HIGH_PERCENTILE = 98.0
UNVALIDATED_SOFTWARE_OUTPUT_LOW = 0.0
UNVALIDATED_SOFTWARE_OUTPUT_HIGH = 1.0
# Clipping tails onto the output endpoints flattens peaks (argmax can move).
# Off by default so the stretch stays strictly monotonic on finite samples.
# Outliers may fall slightly outside [0, 1]. ENGINEERING DEFAULT.
UNVALIDATED_SOFTWARE_CLIP_TO_OUTPUT_RANGE = False

# Optional robust contrast (median / IQR). Off for the software baseline.
# Not a claim that contrast enhancement helps lunar matching.
UNVALIDATED_SOFTWARE_ENABLE_CONTRAST = False

# Optional 3x3 finite-neighbor mean. Off: smoothing can harm localization.
UNVALIDATED_SOFTWARE_ENABLE_DENOISE = False
UNVALIDATED_SOFTWARE_DENOISE_KERNEL_SIZE = 3

# Scale resampling is not implemented. This flag must never silently resize.
UNVALIDATED_SOFTWARE_ENABLE_SCALE = False


@dataclass(frozen=True, slots=True)
class PreprocessingSettings:
    """Configuration for one preprocessing run.

    enable_intensity_normalization
        Percentile stretch of finite samples using [output_low, output_high]
        as the mapped range of [p_lo, p_hi]. ENGINEERING DEFAULT when used
        via unvalidated_software_defaults(). Not radiometric calibration.
        Not multimodal equalization.

    intensity_low_percentile / intensity_high_percentile
        Finite-sample percentiles that define the input range of the stretch.
        ENGINEERING DEFAULT 2 and 98 so extreme outliers do not set the
        scale. Not SIH or lunar-validated.

    output_low / output_high
        Mapped output values of p_lo and p_hi. ENGINEERING DEFAULT [0, 1].

    clip_to_output_range
        If True, clip after the stretch. ENGINEERING DEFAULT False: clipping
        flattens percentile tails and can destroy peak uniqueness.

    enable_contrast_normalization
        Optional median/IQR scaling. Off by default. Not a scientifically
        validated contrast method. Does not make sensors equivalent.

    enable_denoise
        Optional odd-square nan-aware mean filter. Off by default because
        smoothing can shift feature peaks.

    denoise_kernel_size
        Odd window side length for the optional mean filter. ENGINEERING
        DEFAULT 3. Not a validated denoising kernel.

    enable_scale_normalization
        Explicit scale-resampling hook. This baseline never resamples,
        even when True: pixel origin and GSD geometry are undefined.
        GSD ratio from characterization is not a resize trigger.
    """

    enable_intensity_normalization: bool
    intensity_low_percentile: float
    intensity_high_percentile: float
    output_low: float
    output_high: float
    clip_to_output_range: bool
    enable_contrast_normalization: bool
    enable_denoise: bool
    denoise_kernel_size: int
    enable_scale_normalization: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.intensity_low_percentile < self.intensity_high_percentile <= 100.0:
            raise ValueError("intensity percentiles must satisfy 0 <= low < high <= 100")
        if not (self.output_high > self.output_low):
            raise ValueError("output_high must be > output_low")
        if self.denoise_kernel_size < 1 or self.denoise_kernel_size % 2 == 0:
            raise ValueError("denoise_kernel_size must be an odd integer >= 1")


def unvalidated_software_defaults() -> PreprocessingSettings:
    """Engineering defaults used by preprocess(pair).

    Intensity percentile stretch is on and unclipped; contrast, denoise,
    and scale resampling are off. These are not SIH thresholds and not a
    final lunar preprocessing configuration.
    """

    return PreprocessingSettings(
        enable_intensity_normalization=UNVALIDATED_SOFTWARE_ENABLE_INTENSITY,
        intensity_low_percentile=UNVALIDATED_SOFTWARE_INTENSITY_LOW_PERCENTILE,
        intensity_high_percentile=UNVALIDATED_SOFTWARE_INTENSITY_HIGH_PERCENTILE,
        output_low=UNVALIDATED_SOFTWARE_OUTPUT_LOW,
        output_high=UNVALIDATED_SOFTWARE_OUTPUT_HIGH,
        clip_to_output_range=UNVALIDATED_SOFTWARE_CLIP_TO_OUTPUT_RANGE,
        enable_contrast_normalization=UNVALIDATED_SOFTWARE_ENABLE_CONTRAST,
        enable_denoise=UNVALIDATED_SOFTWARE_ENABLE_DENOISE,
        denoise_kernel_size=UNVALIDATED_SOFTWARE_DENOISE_KERNEL_SIZE,
        enable_scale_normalization=UNVALIDATED_SOFTWARE_ENABLE_SCALE,
    )


def minimal_preprocessing_defaults() -> PreprocessingSettings:
    """Ablation A: finite-mask pass-through only. No optional transforms."""

    return PreprocessingSettings(
        enable_intensity_normalization=False,
        intensity_low_percentile=UNVALIDATED_SOFTWARE_INTENSITY_LOW_PERCENTILE,
        intensity_high_percentile=UNVALIDATED_SOFTWARE_INTENSITY_HIGH_PERCENTILE,
        output_low=UNVALIDATED_SOFTWARE_OUTPUT_LOW,
        output_high=UNVALIDATED_SOFTWARE_OUTPUT_HIGH,
        clip_to_output_range=UNVALIDATED_SOFTWARE_CLIP_TO_OUTPUT_RANGE,
        enable_contrast_normalization=False,
        enable_denoise=False,
        denoise_kernel_size=UNVALIDATED_SOFTWARE_DENOISE_KERNEL_SIZE,
        enable_scale_normalization=False,
    )
