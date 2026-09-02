"""Engineering settings for matching representations.

These defaults control runtime and memory behaviour only. They are not
scientifically validated lunar-registration thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchingViewSettings:
    """Runtime policy for representation arrays consumed by matchers.

    max_pixels_per_image:
        Soft per-image cap for the derived matching view passed into SIFT.
        Images larger than this are deterministically decimated before
        representation generation so OpenCV does not build a full-resolution
        scale-space pyramid on very large rasters.
    downsample_method:
        Engineering label for the derived-view strategy. Only
        ``"stride_decimation"`` is implemented in this baseline.
    """

    max_pixels_per_image: int = 4_194_304
    downsample_method: str = "stride_decimation"


def unvalidated_matching_view_defaults() -> MatchingViewSettings:
    """Return the current software default matching-view policy."""
    return MatchingViewSettings()


__all__ = ["MatchingViewSettings", "unvalidated_matching_view_defaults"]
