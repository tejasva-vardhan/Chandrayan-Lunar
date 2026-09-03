"""Exact EXP-006 correspondence-quality A/B configuration.

EXP-006 asks one question: does reciprocal nearest-neighbour validation on
the existing SIFT detector/descriptor produce more reliable and spatially
distributed verified correspondences than the EXP-001 one-way SIFT baseline
on pair_02_mid_equatorial?

Everything except the correspondence-validation protocol is pinned to the
EXP-001 SIFT / EXP-000 configuration. No new matcher, representation,
RANSAC, refinement, SPICE, or frontend change is introduced. Frozen
CorrespondenceSet / RegistrationResult contracts are not extended.
"""

from __future__ import annotations

from typing import Any

from src.io.exp000.config import snapshot_software_configuration
from src.io.exp001.config import PAIR_REGISTRY

EXPERIMENT_ID = "EXP-006"
BASELINE_EXPERIMENT_ID = "EXP-000"
SIFT_BASELINE_EXPERIMENT_ID = "EXP-001"

INDEPENDENT_ACCURACY_NOT_VALIDATED = "NOT VALIDATED"
DECISION_SUPPORTED = "SUPPORTED"
DECISION_NOT_SUPPORTED = "NOT SUPPORTED"
DECISION_INDETERMINATE = "INDETERMINATE"

FOOTPRINT_SOURCE = "NASA PDS ODE"
PRIMARY_PAIR_ID = "pair_02_mid_equatorial"
FOLLOW_UP_PAIR_ID = "pair_01_equatorial"

OHRC_PRODUCT_ID = PAIR_REGISTRY[PRIMARY_PAIR_ID]["ohrc_product_id"]
LROC_PRODUCT_ID = PAIR_REGISTRY[PRIMARY_PAIR_ID]["lroc_product_id"]
OHRC_INSTRUMENT = "OHRC"
LROC_INSTRUMENT = "LRO_NAC"

VARIANT_A_ID = "A"
VARIANT_B_ID = "B"

PROTOCOL_ONE_WAY = "sift_lowe_ratio_one_way"
PROTOCOL_RECIPROCAL = "sift_lowe_ratio_reciprocal_nn"

VARIANT_PROTOCOL_ID = {
    VARIANT_A_ID: PROTOCOL_ONE_WAY,
    VARIANT_B_ID: PROTOCOL_RECIPROCAL,
}

# EXP-001 SIFT arm strides. Held fixed; not the independent variable.
EXPECTED_PAIR_02_STRIDES = {"ohrc": 16, "lroc": 8}
EXPECTED_PAIR_01_STRIDES = {"ohrc": 15, "lroc": 8}

# Reciprocal matching adds one reverse knnMatch. 5x is a generous ceiling
# so a ~2x expected cost cannot be read as a failure, while a pathological
# blow-up still fails the pre-registered runtime gate.
RUNTIME_FACTOR_LIMIT = 5.0

GRID_BINS = 8

HYPOTHESIS = (
    "H1: On pair_02_mid_equatorial, adding reciprocal (mutual nearest-neighbour) "
    "validation to the EXP-001 SIFT baseline, holding detector, descriptor, "
    "Lowe ratio, matching view, representation, and geometric verification "
    "fixed, produces a meaningful improvement in verified correspondence "
    "quality while maintaining or improving spatial distribution of those "
    "verified correspondences. "
    "H0: reciprocal validation does not improve verified quality, or any "
    "quality gain comes with worse spatial distribution or an unstable "
    "transform."
)

DECISION_RULE = (
    "The independent variable is valid only if variant A is the frozen "
    "match() one-way SIFT + Lowe-ratio path and variant B is the same SIFT "
    "detector/descriptor/Lowe-ratio with reciprocal nearest-neighbour "
    "validation, on the same RepresentationResult. "
    "B is SUPPORTED only if all of the following hold: "
    "(1) verified inliers strictly increase, "
    "(2) inlier ratio does not decrease, "
    "(3) source and reference 8x8 occupied-cell counts are each >= A's "
    "(spatial distribution maintained or improved), "
    "(4) both variants fit a transform from more than the projective DLT "
    "minimum of 4 verified inliers, "
    "(5) B match-stage runtime is at most 5x A's. "
    "Raw match count alone is not success. Occupied-cell count is the "
    "spatial gate; bounding-box coverage and Clark-Evans R are reported "
    "but not gated. Matcher-derived held-out RMSE is reported and is not "
    "accuracy. Independent accuracy remains NOT VALIDATED. "
    "Missing critical measurements make the decision INDETERMINATE. "
    "If the hypothesis fails, report NOT SUPPORTED and do not retune."
)


def snapshot_fixed_configuration() -> dict[str, Any]:
    """Everything held constant across variants, imported from EXP-000."""

    fixed = dict(snapshot_software_configuration())
    fixed.pop("pair_manifest_id", None)
    fixed["experiment_id"] = EXPERIMENT_ID
    fixed["inherited_from"] = BASELINE_EXPERIMENT_ID
    fixed["sift_baseline_experiment_id"] = SIFT_BASELINE_EXPERIMENT_ID
    fixed["primary_pair_manifest_id"] = PRIMARY_PAIR_ID
    fixed["follow_up_pair_manifest_id"] = FOLLOW_UP_PAIR_ID
    fixed["matcher_id"] = "sift"
    fixed["independent_variable"] = "correspondence_validation_protocol"
    fixed["matching_view_held_fixed"] = True
    fixed["expected_pair_02_strides"] = dict(EXPECTED_PAIR_02_STRIDES)
    fixed["expected_pair_01_strides"] = dict(EXPECTED_PAIR_01_STRIDES)
    fixed["spatial_grid"] = {
        "grid_bins": GRID_BINS,
        "total_cells": GRID_BINS * GRID_BINS,
        "extent": "full_product_image_dimensions_not_point_bbox",
        "same_grid_as_control_point_selection": True,
    }
    fixed["runtime_factor_limit"] = RUNTIME_FACTOR_LIMIT
    fixed["held_out_validation"] = {
        "design": "k-fold split of verified correspondences per variant",
        "folds": 5,
        "rng_seed": 0,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "note": (
            "held-out transfer error is not independent accuracy; checkpoints "
            "are matcher-derived and there is no surveyed lunar control"
        ),
    }
    fixed["held_constant"] = [
        "input products and pair manifest for a given pair",
        "matcher_id sift and all SiftSettings (EXP-001 SIFT arm)",
        "SIFT detector and descriptor (nfeatures=0, nOctaveLayers=3, "
        "contrast=0.04, edge=10, sigma=1.6)",
        "Lowe ratio threshold 0.75 and min_matches 4",
        "matching-view policy per_image_pixel_budget",
        "matching-view pixel budget 4,194,304",
        "downsample_method stride_decimation",
        "preprocessing (identity passthrough above the 16,777,216-pixel cap)",
        "intensity representation routing",
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
    ]
    return fixed


def snapshot_variant_configuration() -> dict[str, Any]:
    """The independent variable, recorded before interpreting any result."""

    return {
        VARIANT_A_ID: {
            "label": "exp001_sift_one_way_lowe_ratio",
            "protocol_id": PROTOCOL_ONE_WAY,
            "role": "control_existing_sift_baseline",
            "callable": "match(pair, representation)",
            "require_reciprocal": False,
            "notes": (
                "Frozen pipeline match() path. One-way BFMatcher knn (k=2) "
                "plus Lowe ratio 0.75. This is the EXP-001 SIFT control."
            ),
        },
        VARIANT_B_ID: {
            "label": "sift_lowe_ratio_reciprocal_nn",
            "protocol_id": PROTOCOL_RECIPROCAL,
            "role": "correspondence_quality_intervention",
            "callable": "run_sift(..., require_reciprocal=True)",
            "require_reciprocal": True,
            "notes": (
                "Same SIFT keypoints and descriptors as A. A match is kept "
                "only if it survives Lowe's ratio test in both directions "
                "and the two keypoints are mutual nearest neighbours. Not a "
                "new detector or descriptor."
            ),
        },
    }


__all__ = [
    "BASELINE_EXPERIMENT_ID",
    "DECISION_INDETERMINATE",
    "DECISION_NOT_SUPPORTED",
    "DECISION_RULE",
    "DECISION_SUPPORTED",
    "EXPECTED_PAIR_01_STRIDES",
    "EXPECTED_PAIR_02_STRIDES",
    "EXPERIMENT_ID",
    "FOLLOW_UP_PAIR_ID",
    "FOOTPRINT_SOURCE",
    "GRID_BINS",
    "HYPOTHESIS",
    "INDEPENDENT_ACCURACY_NOT_VALIDATED",
    "LROC_INSTRUMENT",
    "LROC_PRODUCT_ID",
    "OHRC_INSTRUMENT",
    "OHRC_PRODUCT_ID",
    "PRIMARY_PAIR_ID",
    "PROTOCOL_ONE_WAY",
    "PROTOCOL_RECIPROCAL",
    "RUNTIME_FACTOR_LIMIT",
    "SIFT_BASELINE_EXPERIMENT_ID",
    "VARIANT_A_ID",
    "VARIANT_B_ID",
    "VARIANT_PROTOCOL_ID",
    "snapshot_fixed_configuration",
    "snapshot_variant_configuration",
]
