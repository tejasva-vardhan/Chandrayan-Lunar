"""Engineering settings for matching representations.

These defaults control runtime and memory behaviour only. They are not
scientifically validated lunar-registration thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass

SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET = "per_image_pixel_budget"
SCALE_POLICY_COMMON_PHYSICAL_GSD = "common_physical_gsd"


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
    scale_policy:
        How the integer stride is chosen. The default
        ``per_image_pixel_budget`` is the EXP-000 rule (independent stride
        per image). ``common_physical_gsd`` is pair-aware: both matching
        views are decimated so ``gsd * stride`` is approximately the same
        physical ground scale, still without exceeding the pixel budget.
    catalog_gsd_meters_by_instrument:
        Optional experiment-level GSD fallbacks used only when
        ``LunarProduct.gsd_meters`` is missing. Empty by default so the
        frozen ``generate_representation(pair)`` path never invents a GSD.
        Values here are not written onto ``LunarProduct``.
    relative_stride_factor_by_instrument:
        Optional multipliers applied to the already-selected integer stride
        for named instruments. Empty by default so the frozen
        ``generate_representation(pair)`` path is unchanged. Factor 2.0 is
        approximately 2× additional stride-decimation (coarser matching
        view). Factor 0.5 is approximately 2× finer spatial sampling of the
        same source raster. This changes the pixels SIFT sees; it does not
        invent a metadata GSD. A factor may produce a matching view larger
        than ``max_pixels_per_image``; that is intentional when testing
        finer sampling. Still ``stride_decimation``; never interpolation.
    representation_id_override:
        Optional representation label. ``None`` (default) keeps existing
        ``select_representation_id`` routing so EXP-000/EXP-004 stay
        unchanged. Set to ``"illumination"`` to request the engineering
        illumination-normalization baseline without changing the frozen
        ``generate_representation(pair)`` signature.
    """

    max_pixels_per_image: int = 4_194_304
    downsample_method: str = "stride_decimation"
    scale_policy: str = SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    catalog_gsd_meters_by_instrument: tuple[tuple[str, float], ...] = ()
    relative_stride_factor_by_instrument: tuple[tuple[str, float], ...] = ()
    representation_id_override: str | None = None


def unvalidated_matching_view_defaults() -> MatchingViewSettings:
    """Return the current software default matching-view policy."""
    return MatchingViewSettings()


__all__ = [
    "MatchingViewSettings",
    "SCALE_POLICY_COMMON_PHYSICAL_GSD",
    "SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET",
    "unvalidated_matching_view_defaults",
]
