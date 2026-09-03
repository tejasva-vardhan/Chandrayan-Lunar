"""PS-closing phase 1 correspondence A/B configuration.

Independent variable: frozen single-view SIFT vs coarse-to-fine tiled
multi-scale SIFT. Everything else is the EXP-001 SIFT / EXP-000 snapshot.
Not EXP-007. Not a matcher freeze (D-007). Not SIH evidence.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.io.exp000.config import snapshot_software_configuration
from src.matching.settings import CoarseToFineSettings

RECORD_ID = "PS-CORRESPONDENCE"
BASELINE_EXPERIMENT_ID = "EXP-000"
SIFT_BASELINE_EXPERIMENT_ID = "EXP-001"

INDEPENDENT_ACCURACY_NOT_VALIDATED = "NOT VALIDATED"
DECISION_SUPPORTED = "SUPPORTED"
DECISION_NOT_SUPPORTED = "NOT SUPPORTED"
DECISION_INDETERMINATE = "INDETERMINATE"

FOOTPRINT_SOURCE = "NASA PDS ODE"
PRIMARY_PAIR_ID = "pair_02_mid_equatorial"
FOLLOW_UP_PAIR_ID = "pair_01_equatorial"

VARIANT_A_ID = "A"
VARIANT_B_ID = "B"

PROTOCOL_SINGLE_VIEW = "sift_single_matching_view"
PROTOCOL_COARSE_TO_FINE = "sift_coarse_to_fine_tiled_multiscale"

EXPECTED_PAIR_02_STRIDES = {"ohrc": 16, "lroc": 8}
EXPECTED_PAIR_01_STRIDES = {"ohrc": 15, "lroc": 8}

# Four fine tiles plus coarse SIFT. 12x is slack around a ~5x pixel budget
# and is fixed before the run.
RUNTIME_FACTOR_LIMIT = 12.0
GRID_BINS = 8

HYPOTHESIS = (
    "H1: On pair_02_mid_equatorial, a coarse-to-fine tiled multi-scale SIFT "
    "path that searches at half the matching-view stride inside the coarse "
    "geometric overlap, then uses the same downstream geometric verification, "
    "recovers more verified inliers and maintains or improves 8x8 occupancy "
    "versus the EXP-001 single matching-view SIFT baseline. "
    "H0: multi-scale tiled search does not improve verified quality and "
    "spatial occupancy, or the transform becomes unstable, or runtime is "
    "pathological."
)

DECISION_RULE = (
    "The independent variable is valid only if variant A is frozen match() "
    "one-way SIFT on the shared RepresentationResult and variant B is "
    "run_coarse_to_fine_sift on that same representation. "
    "B is SUPPORTED only if: (1) verified inliers strictly increase, "
    "(2) source and reference 8x8 occupied-cell counts are each >= A's, "
    "(3) both variants fit a transform from more than 4 verified inliers, "
    "(4) B match-stage runtime is at most 12x A's. "
    "Raw match count is not success. Inlier ratio is reported, not gated, "
    "because B is allowed to add local candidates. Bounding-box coverage "
    "and Clark-Evans R are reported, not gated. Matcher-derived held-out "
    "RMSE is not accuracy. Independent accuracy remains NOT VALIDATED. "
    "Missing critical measurements make the decision INDETERMINATE. "
    "If H1 fails, report NOT SUPPORTED and do not retune."
)


def snapshot_fixed_configuration() -> dict[str, Any]:
    fixed = dict(snapshot_software_configuration())
    fixed.pop("pair_manifest_id", None)
    fixed["record_id"] = RECORD_ID
    fixed["inherited_from"] = BASELINE_EXPERIMENT_ID
    fixed["sift_baseline_experiment_id"] = SIFT_BASELINE_EXPERIMENT_ID
    fixed["primary_pair_manifest_id"] = PRIMARY_PAIR_ID
    fixed["follow_up_pair_manifest_id"] = FOLLOW_UP_PAIR_ID
    fixed["matcher_family"] = "sift"
    fixed["independent_variable"] = "correspondence_generation_path"
    fixed["matching_view_held_fixed_for_control"] = True
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
    }
    fixed["held_constant"] = [
        "input products and pair manifest for a given pair",
        "SIFT detector and descriptor (EXP-001 SIFT arm)",
        "Lowe ratio 0.75 and min_matches 4",
        "coarse matching-view policy per_image_pixel_budget",
        "matching-view pixel budget 4,194,304",
        "downsample_method stride_decimation",
        "preprocessing identity passthrough above the 16,777,216-pixel cap",
        "intensity representation routing",
        "downstream geometric model projective_2d_baseline",
        "downstream estimator ransac_style_baseline",
        "verification residual_limit 3.0, max_trials 500, rng_seed 0",
        "control-point selection grid_bins 8, max 1 point per cell",
        "refinement zncc_parabolic_baseline",
        "registration model and the 16,777,216-pixel output cap",
    ]
    return fixed


def snapshot_variant_configuration() -> dict[str, Any]:
    ctf = asdict(CoarseToFineSettings())
    return {
        VARIANT_A_ID: {
            "label": "exp001_sift_single_matching_view",
            "protocol_id": PROTOCOL_SINGLE_VIEW,
            "role": "control_existing_sift_baseline",
            "callable": "match(pair, representation)",
        },
        VARIANT_B_ID: {
            "label": "sift_coarse_to_fine_tiled_multiscale",
            "protocol_id": PROTOCOL_COARSE_TO_FINE,
            "role": "candidate_correspondence_core",
            "callable": "run_coarse_to_fine_sift(pair, representation)",
            "coarse_to_fine": ctf,
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
    "FOLLOW_UP_PAIR_ID",
    "FOOTPRINT_SOURCE",
    "GRID_BINS",
    "HYPOTHESIS",
    "INDEPENDENT_ACCURACY_NOT_VALIDATED",
    "PRIMARY_PAIR_ID",
    "PROTOCOL_COARSE_TO_FINE",
    "PROTOCOL_SINGLE_VIEW",
    "RECORD_ID",
    "RUNTIME_FACTOR_LIMIT",
    "SIFT_BASELINE_EXPERIMENT_ID",
    "VARIANT_A_ID",
    "VARIANT_B_ID",
    "snapshot_fixed_configuration",
    "snapshot_variant_configuration",
]
