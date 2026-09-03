"""Exact EXP-005 subpixel-refinement ablation configuration.

EXP-005 asks one question: does the existing ZNCC + parabolic refinement
produce measurable, reproducible coordinate changes that improve held-out
geometric consistency on pair_02_mid_equatorial?

The pair is the EXP-001 SIFT arm that already exceeded the four-point floor
(25 verified inliers). Everything except the refinement method is pinned to
that EXP-001 / EXP-000 SIFT configuration. No new matcher, representation,
RANSAC, or refinement algorithm is introduced. SPICE is not used.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from src.io.exp000.config import snapshot_software_configuration
from src.io.exp001.config import PAIR_REGISTRY
from src.refinement.settings import RefinementSettings, unvalidated_software_defaults

EXPERIMENT_ID = "EXP-005"
BASELINE_EXPERIMENT_ID = "EXP-000"
SIFT_BASELINE_EXPERIMENT_ID = "EXP-001"

INDEPENDENT_ACCURACY_NOT_VALIDATED = "NOT VALIDATED"
REFINEMENT_OUTCOME_INDETERMINATE = "INDETERMINATE"
REFINEMENT_OUTCOME_COORDINATES_UPDATED = "COORDINATES_UPDATED"
REFINEMENT_OUTCOME_NO_POINTS = "NO_POINTS"

FOOTPRINT_SOURCE = "NASA PDS ODE"
PAIR_MANIFEST_ID = "pair_02_mid_equatorial"
OHRC_PRODUCT_ID = PAIR_REGISTRY[PAIR_MANIFEST_ID]["ohrc_product_id"]
LROC_PRODUCT_ID = PAIR_REGISTRY[PAIR_MANIFEST_ID]["lroc_product_id"]
OHRC_INSTRUMENT = "OHRC"
LROC_INSTRUMENT = "LRO_NAC"

VARIANT_A_ID = "A"
VARIANT_B_ID = "B"

METHOD_IDENTITY = "identity_passthrough"
METHOD_ZNCC = "zncc_parabolic_baseline"

VARIANT_METHOD_ID = {
    VARIANT_A_ID: METHOD_IDENTITY,
    VARIANT_B_ID: METHOD_ZNCC,
}

# EXP-001 SIFT arm on this pair used these matching-view strides. They are
# held fixed; they are not the independent variable.
EXPECTED_PAIR_02_STRIDES = {"ohrc": 16, "lroc": 8}

HYPOTHESIS = (
    "H1: On pair_02_mid_equatorial, with the EXP-001 SIFT configuration held "
    "fixed, the existing ZNCC + parabolic refinement produces measurable "
    "coordinate changes relative to identity passthrough and those changes "
    "strictly reduce held-out image-space transfer error on the same "
    "matcher-derived checkpoints. "
    "H0: the existing refinement either does not change coordinates, or the "
    "changes do not improve held-out geometric consistency."
)

DECISION_RULE = (
    "The independent variable is valid only if variant A uses "
    "identity_passthrough and variant B uses zncc_parabolic_baseline on the "
    "same selected control points (shared match, verification, and "
    "control-point selection). Coordinate change is measured, not assumed. "
    "Refinement is treated as improving held-out geometric consistency only "
    "if B changes at least one coordinate and the same held-out checkpoint "
    "RMSE is strictly lower for B than for A. Coordinate change alone is not "
    "accuracy. Matcher-derived held-out points are not ground truth. "
    "Independent accuracy remains NOT VALIDATED. One pair cannot validate "
    "sub-pixel accuracy."
)


def variant_a_refinement_settings() -> RefinementSettings:
    """Ablation: no subpixel update. Window/search fields are unused."""

    return replace(unvalidated_software_defaults(), method_id=METHOD_IDENTITY)


def variant_b_refinement_settings() -> RefinementSettings:
    """Existing frozen two-argument refine_points() software baseline."""

    return unvalidated_software_defaults()


def snapshot_fixed_configuration() -> dict[str, Any]:
    """Everything held constant across variants, imported from EXP-000."""

    fixed = dict(snapshot_software_configuration())
    fixed.pop("pair_manifest_id", None)
    refinement = dict(fixed["refinement"])
    refinement.pop("method_id", None)
    fixed["refinement"] = refinement
    fixed["experiment_id"] = EXPERIMENT_ID
    fixed["inherited_from"] = BASELINE_EXPERIMENT_ID
    fixed["sift_baseline_experiment_id"] = SIFT_BASELINE_EXPERIMENT_ID
    fixed["pair_manifest_id"] = PAIR_MANIFEST_ID
    fixed["matcher_id"] = "sift"
    fixed["independent_variable"] = "refinement_method_id"
    fixed["matching_view_held_fixed"] = True
    fixed["expected_pair_02_strides"] = dict(EXPECTED_PAIR_02_STRIDES)
    fixed["held_out_validation"] = {
        "design": (
            "same verified-inlier checkpoints scored on the transform fitted "
            "from unrefined vs refined control points; k-fold on control-point "
            "coordinates is recorded as a secondary split"
        ),
        "folds": 5,
        "rng_seed": 0,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "note": (
            "held-out transfer error is not independent accuracy; checkpoints "
            "are matcher-derived and there is no surveyed lunar control"
        ),
    }
    fixed["held_constant"] = [
        "input products and pair manifest (pair_02_mid_equatorial)",
        "matcher_id sift and all SiftSettings (EXP-001 SIFT arm)",
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
        "ZNCC window/search/min_peak settings when the ZNCC method runs",
        "registration model and the 16,777,216-pixel output cap",
        "evaluation metric definitions",
        "Lowe ratio threshold 0.75 and min_matches 4",
    ]
    return fixed


def snapshot_variant_configuration() -> dict[str, Any]:
    """The independent variable, recorded before interpreting any result."""

    defaults = unvalidated_software_defaults()
    shared_zncc = {
        "window_radius": defaults.window_radius,
        "search_radius": defaults.search_radius,
        "min_valid_pixel_fraction": defaults.min_valid_pixel_fraction,
        "min_peak_zncc": defaults.min_peak_zncc,
        "fine_half_width": defaults.fine_half_width,
        "fine_step": defaults.fine_step,
    }
    return {
        VARIANT_A_ID: {
            "label": "no_subpixel_refinement",
            "method_id": METHOD_IDENTITY,
            "role": "ablation_no_refinement",
            "callable": "refine_points_with_settings(..., identity_passthrough)",
            "notes": (
                "Identity passthrough is the designed ablation hook. It is "
                "not a sub-pixel method and is not cited as refinement "
                "accuracy."
            ),
        },
        VARIANT_B_ID: {
            "label": "existing_zncc_parabolic_baseline",
            "method_id": METHOD_ZNCC,
            "role": "same_modality_software_baseline",
            "callable": "refine_points(control_points, pair)",
            "zncc_settings": shared_zncc,
            "notes": (
                "Frozen two-argument refine_points() path. Algorithm is not "
                "redesigned for this experiment."
            ),
        },
    }


__all__ = [
    "BASELINE_EXPERIMENT_ID",
    "DECISION_RULE",
    "EXPERIMENT_ID",
    "EXPECTED_PAIR_02_STRIDES",
    "FOOTPRINT_SOURCE",
    "HYPOTHESIS",
    "INDEPENDENT_ACCURACY_NOT_VALIDATED",
    "LROC_INSTRUMENT",
    "LROC_PRODUCT_ID",
    "METHOD_IDENTITY",
    "METHOD_ZNCC",
    "OHRC_INSTRUMENT",
    "OHRC_PRODUCT_ID",
    "PAIR_MANIFEST_ID",
    "REFINEMENT_OUTCOME_COORDINATES_UPDATED",
    "REFINEMENT_OUTCOME_INDETERMINATE",
    "REFINEMENT_OUTCOME_NO_POINTS",
    "SIFT_BASELINE_EXPERIMENT_ID",
    "VARIANT_A_ID",
    "VARIANT_B_ID",
    "VARIANT_METHOD_ID",
    "snapshot_fixed_configuration",
    "snapshot_variant_configuration",
    "variant_a_refinement_settings",
    "variant_b_refinement_settings",
]
