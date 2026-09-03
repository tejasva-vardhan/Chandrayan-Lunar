"""Exact EXP-002 matching-view scale-policy configuration.

EXP-002 asks one question: does a common physical / GSD-normalised matching
scale increase verified SIFT correspondences on pair_01_equatorial beyond
the four-point projective DLT minimum?

Everything except the matching-view scale policy is pinned to EXP-000.
SIFT is unchanged. No new matcher is introduced. SPICE is not used.

The LROC NAC catalog GSD is an experiment-level fallback used only when
``LunarProduct.gsd_meters`` is missing. It is not written onto the ingested
product and is not a SPICE-derived per-image measurement.
"""

from __future__ import annotations

from typing import Any

from src.io.exp000.config import snapshot_software_configuration
from src.representation.settings import (
    SCALE_POLICY_COMMON_PHYSICAL_GSD,
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
    MatchingViewSettings,
    unvalidated_matching_view_defaults,
)

EXPERIMENT_ID = "EXP-002"
BASELINE_EXPERIMENT_ID = "EXP-000"

INDEPENDENT_ACCURACY_NOT_VALIDATED = "NOT VALIDATED"
REFINEMENT_OUTCOME_INDETERMINATE = "INDETERMINATE"
REFINEMENT_OUTCOME_COORDINATES_UPDATED = "COORDINATES_UPDATED"
REFINEMENT_OUTCOME_NO_POINTS = "NO_POINTS"

FOOTPRINT_SOURCE = "NASA PDS ODE"
PAIR_MANIFEST_ID = "pair_01_equatorial"
OHRC_PRODUCT_ID = "ch2_ohr_ncp_20210402T0546284043_d_img_d18"
LROC_PRODUCT_ID = "M150368601RC"

# Robinson et al. 2010 / LROC SIS: NAC IFOV 10 µrad from the 50 km mapping
# orbit is 0.5 m/pixel. Pair-01 LROC is SCIENCE MISSION, 2011-01-22,
# CROSSTRACK_SUMMING=1 (unsummed). This is catalog instrument scale, not an
# ingested product field and not a SPICE reconstruction.
LROC_NAC_CATALOG_GSD_METERS = 0.5
LROC_NAC_CATALOG_INSTRUMENT = "LRO_NAC"

VARIANT_A_ID = "A"
VARIANT_B_ID = "B"

HYPOTHESIS = (
    "H1: On pair_01_equatorial, replacing per-image pixel-budget matching-view "
    "strides with a common physical/GSD-normalised matching scale increases "
    "the number of geometrically verified SIFT correspondences beyond the "
    "four-point projective DLT minimum, holding every other EXP-000 stage "
    "constant. "
    "H0: common-scale matching views do not move verified yield above that "
    "minimum, which would mean residual matching-view scale is not the "
    "demonstrated pair-01 correspondence bottleneck."
)

DECISION_RULE = (
    "Variant B counts as improving verified yield only if it produces "
    "strictly more verified inliers than the geometric model's minimum "
    "sample size (4 for projective_2d_baseline). A verified count of exactly "
    "4 means RANSAC's consensus set is the minimal sample itself. Four-point "
    "DLT residuals are not accuracy. Independent accuracy remains NOT VALIDATED."
)


def variant_a_matching_view_settings() -> MatchingViewSettings:
    """EXP-000 matching-view policy. Independent per-image pixel-budget stride."""

    return unvalidated_matching_view_defaults()


def variant_b_matching_view_settings() -> MatchingViewSettings:
    """Common-scale policy. Same budget and stride-decimation as EXP-000."""

    defaults = unvalidated_matching_view_defaults()
    return MatchingViewSettings(
        max_pixels_per_image=defaults.max_pixels_per_image,
        downsample_method=defaults.downsample_method,
        scale_policy=SCALE_POLICY_COMMON_PHYSICAL_GSD,
        catalog_gsd_meters_by_instrument=(
            (LROC_NAC_CATALOG_INSTRUMENT, LROC_NAC_CATALOG_GSD_METERS),
        ),
    )


def snapshot_fixed_configuration() -> dict[str, Any]:
    """Everything held constant across variants, imported from EXP-000."""

    fixed = dict(snapshot_software_configuration())
    fixed.pop("pair_manifest_id", None)
    matching_view = dict(fixed["matching_view"])
    matching_view.pop("scale_policy", None)
    fixed["matching_view"] = matching_view
    fixed["experiment_id"] = EXPERIMENT_ID
    fixed["inherited_from"] = BASELINE_EXPERIMENT_ID
    fixed["pair_manifest_id"] = PAIR_MANIFEST_ID
    fixed["independent_variable"] = "matching_view_scale_policy"
    fixed["held_constant"] = [
        "input products and pair manifest",
        "matcher_id sift and all SiftSettings",
        "matching-view pixel budget 4,194,304",
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
    return {
        VARIANT_A_ID: {
            "label": "existing_exp000_matching_view_policy",
            "scale_policy": SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
            "max_pixels_per_image": baseline.max_pixels_per_image,
            "downsample_method": baseline.downsample_method,
            "catalog_gsd_meters_by_instrument": [],
            "stride_rule": "stride = ceil(sqrt(pixels / 4194304)) independently per image",
            "expected_pair_01_strides": {"ohrc": 15, "lroc": 8},
            "representation_callable": "generate_representation(pair)",
        },
        VARIANT_B_ID: {
            "label": "common_physical_gsd_matching_view",
            "scale_policy": variant_b.scale_policy,
            "max_pixels_per_image": variant_b.max_pixels_per_image,
            "downsample_method": variant_b.downsample_method,
            "catalog_gsd_meters_by_instrument": [
                {
                    "instrument": name,
                    "gsd_meters": gsd,
                    "used_only_when_ingested_gsd_missing": True,
                    "written_onto_lunar_product": False,
                    "spice_used": False,
                    "provenance": (
                        "LROC NAC mapping-orbit catalog GSD 0.5 m/pixel "
                        "(10 µrad IFOV from 50 km). Pair-01 LROC is SCIENCE "
                        "MISSION 2011-01-22 with CROSSTRACK_SUMMING=1."
                    ),
                }
                for name, gsd in variant_b.catalog_gsd_meters_by_instrument
            ],
            "stride_rule": (
                "target_gsd = max(gsd_i * pixel_budget_stride_i); "
                "stride_i = max(pixel_budget_stride_i, round(target_gsd / gsd_i))"
            ),
            "representation_callable": "generate_representation_with_settings",
        },
    }


__all__ = [
    "BASELINE_EXPERIMENT_ID",
    "DECISION_RULE",
    "EXPERIMENT_ID",
    "FOOTPRINT_SOURCE",
    "HYPOTHESIS",
    "INDEPENDENT_ACCURACY_NOT_VALIDATED",
    "LROC_NAC_CATALOG_GSD_METERS",
    "LROC_NAC_CATALOG_INSTRUMENT",
    "LROC_PRODUCT_ID",
    "OHRC_PRODUCT_ID",
    "PAIR_MANIFEST_ID",
    "REFINEMENT_OUTCOME_COORDINATES_UPDATED",
    "REFINEMENT_OUTCOME_INDETERMINATE",
    "REFINEMENT_OUTCOME_NO_POINTS",
    "VARIANT_A_ID",
    "VARIANT_B_ID",
    "snapshot_fixed_configuration",
    "snapshot_variant_configuration",
    "variant_a_matching_view_settings",
    "variant_b_matching_view_settings",
]
