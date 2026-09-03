"""Exact EXP-003 matching-view scale-robustness configuration.

EXP-003 asks one question: is the existing SIFT correspondence pipeline
robust when the LROC matching-view scale is deliberately changed relative
to the EXP-000 baseline, with the OHRC view held fixed?

EXP-002 showed that its common-GSD policy was a no-op on pair 01 (OHRC
stride 15 / LROC stride 8). These variants therefore change the integer
stride actually applied to the LROC raster so SIFT sees a different image.

Everything except the LROC matching-view relative stride is pinned to
EXP-000. SIFT is unchanged. No new matcher is introduced. SPICE is not used.
"""

from __future__ import annotations

from typing import Any

from src.io.exp000.config import snapshot_software_configuration
from src.representation.settings import (
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
    MatchingViewSettings,
    unvalidated_matching_view_defaults,
)

EXPERIMENT_ID = "EXP-003"
BASELINE_EXPERIMENT_ID = "EXP-000"

INDEPENDENT_ACCURACY_NOT_VALIDATED = "NOT VALIDATED"
REFINEMENT_OUTCOME_INDETERMINATE = "INDETERMINATE"
REFINEMENT_OUTCOME_COORDINATES_UPDATED = "COORDINATES_UPDATED"
REFINEMENT_OUTCOME_NO_POINTS = "NO_POINTS"

FOOTPRINT_SOURCE = "NASA PDS ODE"
PAIR_MANIFEST_ID = "pair_01_equatorial"
OHRC_PRODUCT_ID = "ch2_ohr_ncp_20210402T0546284043_d_img_d18"
LROC_PRODUCT_ID = "M150368601RC"
OHRC_INSTRUMENT = "OHRC"
LROC_INSTRUMENT = "LRO_NAC"

VARIANT_A_ID = "A"
VARIANT_B_ID = "B"
VARIANT_C_ID = "C"

# Relative to the EXP-000 per-image pixel-budget stride (LROC 8 on pair 01).
# 2.0 -> stride 16 (approximately 2x additional spatial downscaling).
# 0.5 -> stride 4 (approximately 2x finer spatial sampling).
VARIANT_B_LROC_RELATIVE_STRIDE_FACTOR = 2.0
VARIANT_C_LROC_RELATIVE_STRIDE_FACTOR = 0.5

EXPECTED_PAIR_01_STRIDES = {
    VARIANT_A_ID: {"ohrc": 15, "lroc": 8},
    VARIANT_B_ID: {"ohrc": 15, "lroc": 16},
    VARIANT_C_ID: {"ohrc": 15, "lroc": 4},
}

HYPOTHESIS = (
    "H1: On pair_01_equatorial, the existing SIFT correspondence pipeline is "
    "scale-robust: after approximately 2x additional LROC matching-view "
    "downscaling and approximately 2x finer LROC sampling, with OHRC held at "
    "the EXP-000 stride, verified inlier counts remain equal to the EXP-000 "
    "baseline. "
    "H0: those relative LROC scale changes materially affect verified "
    "correspondence yield on this pair."
)

DECISION_RULE = (
    "The independent variable is valid only if LROC matching-view strides "
    "actually differ across A/B/C while the OHRC stride stays at the EXP-000 "
    "baseline. Scale robustness is supported only if verified inlier counts "
    "for B and C both equal A. Any difference in verified inliers is a "
    "material effect and rejects scale robustness on this pair. Four-point "
    "DLT residuals are not accuracy. Independent accuracy remains NOT "
    "VALIDATED. One pair cannot establish general SIFT scale invariance."
)


def variant_a_matching_view_settings() -> MatchingViewSettings:
    """EXP-000 matching-view policy. Independent per-image pixel-budget stride."""

    return unvalidated_matching_view_defaults()


def variant_b_matching_view_settings() -> MatchingViewSettings:
    """LROC matching view coarsened by approximately 2x. OHRC unchanged."""

    defaults = unvalidated_matching_view_defaults()
    return MatchingViewSettings(
        max_pixels_per_image=defaults.max_pixels_per_image,
        downsample_method=defaults.downsample_method,
        scale_policy=SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
        relative_stride_factor_by_instrument=(
            (LROC_INSTRUMENT, VARIANT_B_LROC_RELATIVE_STRIDE_FACTOR),
        ),
    )


def variant_c_matching_view_settings() -> MatchingViewSettings:
    """LROC matching view sampled approximately 2x finer. OHRC unchanged.

    Pair-01 LROC stride 4 exceeds the 4,194,304-pixel matching-view budget.
    That overrun is required so the independent variable actually changes;
    the registration output cap is not raised.
    """

    defaults = unvalidated_matching_view_defaults()
    return MatchingViewSettings(
        max_pixels_per_image=defaults.max_pixels_per_image,
        downsample_method=defaults.downsample_method,
        scale_policy=SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
        relative_stride_factor_by_instrument=(
            (LROC_INSTRUMENT, VARIANT_C_LROC_RELATIVE_STRIDE_FACTOR),
        ),
    )


def snapshot_fixed_configuration() -> dict[str, Any]:
    """Everything held constant across variants, imported from EXP-000."""

    fixed = dict(snapshot_software_configuration())
    fixed.pop("pair_manifest_id", None)
    matching_view = dict(fixed["matching_view"])
    matching_view.pop("scale_policy", None)
    matching_view.pop("relative_stride_factor_by_instrument", None)
    matching_view.pop("catalog_gsd_meters_by_instrument", None)
    fixed["matching_view"] = matching_view
    fixed["experiment_id"] = EXPERIMENT_ID
    fixed["inherited_from"] = BASELINE_EXPERIMENT_ID
    fixed["pair_manifest_id"] = PAIR_MANIFEST_ID
    fixed["independent_variable"] = "lroc_matching_view_relative_stride_factor"
    fixed["ohrc_held_fixed"] = True
    fixed["held_constant"] = [
        "input products and pair manifest",
        "matcher_id sift and all SiftSettings",
        "OHRC matching-view stride (EXP-000 pixel-budget stride 15 on pair 01)",
        "matching-view pixel budget 4,194,304 on the baseline / coarsened arms",
        "downsample_method stride_decimation",
        "preprocessing (identity passthrough above the 16,777,216-pixel cap)",
        "representation routing and intensity percentile stretch",
        "coordinate mapping back to original image pixels",
        "geometric model projective_2d_baseline",
        "robust estimator ransac_style_baseline",
        "verification residual_limit 3.0",
        "RANSAC max_trials 500",
        "rng_seed 0",
        "control-point selection grid_bins 8, max 1 point per cell",
        "refinement zncc_parabolic_baseline",
        "registration model and the 16,777,216-pixel output cap",
        "evaluation metric definitions",
        "Lowe ratio threshold 0.75 and min_matches 4",
    ]
    return fixed


def snapshot_variant_configuration() -> dict[str, Any]:
    """The independent variable, recorded before interpreting any result."""

    baseline = unvalidated_matching_view_defaults()
    variant_b = variant_b_matching_view_settings()
    variant_c = variant_c_matching_view_settings()
    return {
        VARIANT_A_ID: {
            "label": "exp000_baseline_matching_view",
            "scale_policy": SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
            "max_pixels_per_image": baseline.max_pixels_per_image,
            "downsample_method": baseline.downsample_method,
            "relative_stride_factor_by_instrument": [],
            "stride_rule": (
                "stride = ceil(sqrt(pixels / 4194304)) independently per image"
            ),
            "expected_pair_01_strides": EXPECTED_PAIR_01_STRIDES[VARIANT_A_ID],
            "representation_callable": "generate_representation(pair)",
        },
        VARIANT_B_ID: {
            "label": "lroc_downscaled_2x_relative_to_baseline",
            "scale_policy": variant_b.scale_policy,
            "max_pixels_per_image": variant_b.max_pixels_per_image,
            "downsample_method": variant_b.downsample_method,
            "relative_stride_factor_by_instrument": [
                {
                    "instrument": name,
                    "factor": factor,
                    "applied_to_ohrc": False,
                }
                for name, factor in variant_b.relative_stride_factor_by_instrument
            ],
            "stride_rule": (
                "LROC stride = max(1, round(pixel_budget_stride * 2.0)); "
                "OHRC stride unchanged"
            ),
            "expected_pair_01_strides": EXPECTED_PAIR_01_STRIDES[VARIANT_B_ID],
            "representation_callable": "generate_representation_with_settings",
        },
        VARIANT_C_ID: {
            "label": "lroc_upsampled_2x_relative_to_baseline",
            "scale_policy": variant_c.scale_policy,
            "max_pixels_per_image": variant_c.max_pixels_per_image,
            "downsample_method": variant_c.downsample_method,
            "relative_stride_factor_by_instrument": [
                {
                    "instrument": name,
                    "factor": factor,
                    "applied_to_ohrc": False,
                    "may_exceed_matching_view_pixel_budget": True,
                }
                for name, factor in variant_c.relative_stride_factor_by_instrument
            ],
            "stride_rule": (
                "LROC stride = max(1, round(pixel_budget_stride * 0.5)); "
                "OHRC stride unchanged. Pair-01 LROC stride 4 exceeds the "
                "4,194,304-pixel matching-view budget so SIFT actually sees "
                "a finer raster; the registration output cap is not raised."
            ),
            "expected_pair_01_strides": EXPECTED_PAIR_01_STRIDES[VARIANT_C_ID],
            "representation_callable": "generate_representation_with_settings",
        },
    }


__all__ = [
    "BASELINE_EXPERIMENT_ID",
    "DECISION_RULE",
    "EXPERIMENT_ID",
    "EXPECTED_PAIR_01_STRIDES",
    "FOOTPRINT_SOURCE",
    "HYPOTHESIS",
    "INDEPENDENT_ACCURACY_NOT_VALIDATED",
    "LROC_INSTRUMENT",
    "LROC_PRODUCT_ID",
    "OHRC_INSTRUMENT",
    "OHRC_PRODUCT_ID",
    "PAIR_MANIFEST_ID",
    "REFINEMENT_OUTCOME_COORDINATES_UPDATED",
    "REFINEMENT_OUTCOME_INDETERMINATE",
    "REFINEMENT_OUTCOME_NO_POINTS",
    "VARIANT_A_ID",
    "VARIANT_B_ID",
    "VARIANT_C_ID",
    "VARIANT_B_LROC_RELATIVE_STRIDE_FACTOR",
    "VARIANT_C_LROC_RELATIVE_STRIDE_FACTOR",
    "snapshot_fixed_configuration",
    "snapshot_variant_configuration",
    "variant_a_matching_view_settings",
    "variant_b_matching_view_settings",
    "variant_c_matching_view_settings",
]
