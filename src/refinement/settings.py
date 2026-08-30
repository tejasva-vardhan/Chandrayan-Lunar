"""Experimental sub-pixel refinement settings. Not a scientific freeze.

The frozen callable is refine_points(control_points, pair). It has no settings
argument, so software defaults are required for the two-argument API. Those
numbers are engineering/test defaults only.

They are NOT:
  - SIH thresholds
  - lunar-validated parameters
  - final scientific parameters
  - multimodal OHRC/IIRS/TMC-2 refinement settings
  - benchmark results

Do not copy these into configs/default.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Frozen two-argument API: engineering defaults only ---
# refine_points(control_points, pair) has no settings argument.
# These values exist ONLY so that callable can run.
#
# method_id selects a registry entry. It is a software-baseline label, not a
# claim that this is the lunar or multimodal refinement solution (D-006).
UNVALIDATED_SOFTWARE_METHOD_ID = "zncc_parabolic_baseline"

# Template half-width in pixels. Template size is (2 * radius + 1)^2.
# ENGINEERING DEFAULT. Not a scientifically validated window.
UNVALIDATED_SOFTWARE_WINDOW_RADIUS = 7

# Extra pixels searched around the coarse reference location, on each side.
# ENGINEERING DEFAULT. Not a scientifically validated search radius.
UNVALIDATED_SOFTWARE_SEARCH_RADIUS = 3

# Minimum fraction of finite pixels required in a template/search window.
# ENGINEERING DEFAULT. Not an SIH valid-pixel rule.
UNVALIDATED_SOFTWARE_MIN_VALID_PIXEL_FRACTION = 0.75

# Minimum ZNCC value at the discrete peak to treat the peak as meaningful.
# ENGINEERING DEFAULT so unstructured/failed correlation can be rejected.
# Not a scientifically validated match-quality threshold.
UNVALIDATED_SOFTWARE_MIN_PEAK_ZNCC = 0.25

# Fractional ZNCC grid around the discrete integer peak.
# ENGINEERING DEFAULT. Not a scientifically validated sampling policy.
# half-width is in pixels; step is the grid spacing in pixels.
UNVALIDATED_SOFTWARE_FINE_HALF_WIDTH = 1.0
UNVALIDATED_SOFTWARE_FINE_STEP = 0.1


@dataclass(frozen=True, slots=True)
class RefinementSettings:
    """Configuration for one refinement run.

    method_id
        Registry label for a replaceable local refinement method. The
        two-argument API uses zncc_parabolic_baseline as a SAME-MODALITY
        software baseline, not as a final multimodal lunar method.

    window_radius
        Half-width of the local template in pixels. Template side length is
        2 * window_radius + 1. ENGINEERING DEFAULT when used via
        unvalidated_software_defaults(). Not a scientifically validated
        window size.

    search_radius
        Integer half-width of the discrete lag search around the coarse
        reference coordinate. Search side length is 2 * search_radius + 1.
        ENGINEERING DEFAULT. Not a scientifically validated search range.

    min_valid_pixel_fraction
        Minimum fraction of finite pixels required in a sampled window.
        ENGINEERING DEFAULT. Not an official invalid-pixel policy.

    min_peak_zncc
        Minimum zero-mean normalized cross-correlation at the discrete peak.
        ENGINEERING DEFAULT used to reject non-meaningful peaks. Not an SIH
        quality threshold. Only interpreted by methods that compute ZNCC.

    fine_half_width
        Half-width in pixels of the fractional ZNCC grid around the discrete
        peak. ENGINEERING DEFAULT. Not a scientifically validated sampling
        radius.

    fine_step
        Spacing in pixels of that fractional grid. ENGINEERING DEFAULT.
        Not a scientifically validated sampling density.
    """

    method_id: str
    window_radius: int
    search_radius: int
    min_valid_pixel_fraction: float
    min_peak_zncc: float
    fine_half_width: float
    fine_step: float

    def __post_init__(self) -> None:
        if self.window_radius < 1:
            raise ValueError("window_radius must be >= 1")
        if self.search_radius < 1:
            raise ValueError(
                "search_radius must be >= 1 so a discrete peak can have neighbors "
                "for continuous interpolation"
            )
        if not 0.0 < self.min_valid_pixel_fraction <= 1.0:
            raise ValueError("min_valid_pixel_fraction must be in (0, 1]")
        if not -1.0 <= self.min_peak_zncc <= 1.0:
            raise ValueError("min_peak_zncc must be in [-1, 1]")
        if self.fine_step <= 0.0:
            raise ValueError("fine_step must be > 0")
        if self.fine_half_width < self.fine_step:
            raise ValueError("fine_half_width must be >= fine_step")


def unvalidated_software_defaults() -> RefinementSettings:
    """Engineering defaults used by refine_points(control_points, pair).

    These values exist only because the frozen two-argument API cannot accept
    settings. They are not SIH thresholds, not lunar-validated, not a final
    refinement strategy, and not benchmark results.

    Tests and experiments that need a specific method or window must pass
    RefinementSettings into refine_points_with_settings.
    """

    return RefinementSettings(
        method_id=UNVALIDATED_SOFTWARE_METHOD_ID,
        window_radius=UNVALIDATED_SOFTWARE_WINDOW_RADIUS,
        search_radius=UNVALIDATED_SOFTWARE_SEARCH_RADIUS,
        min_valid_pixel_fraction=UNVALIDATED_SOFTWARE_MIN_VALID_PIXEL_FRACTION,
        min_peak_zncc=UNVALIDATED_SOFTWARE_MIN_PEAK_ZNCC,
        fine_half_width=UNVALIDATED_SOFTWARE_FINE_HALF_WIDTH,
        fine_step=UNVALIDATED_SOFTWARE_FINE_STEP,
    )
