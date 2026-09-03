"""Exact EXP-004 representation-comparison configuration.

EXP-004 asks one question: does changing the existing image representation,
while keeping everything else fixed, increase verified SIFT correspondences
on pair_01_equatorial?

EXP-003 showed that changing LROC matching-view scale changed raw SIFT
detections but did not move verified inliers above the four-point floor.
This experiment therefore changes only representation_id.

Everything except representation_id is pinned to EXP-000. SIFT is unchanged.
No new representation, matcher, or algorithm is introduced. SPICE is not used.
"""

from __future__ import annotations

from typing import Any

from src.io.exp000.config import snapshot_software_configuration
from src.models.registration_pair import PairCharacterization, RegistrationPair

EXPERIMENT_ID = "EXP-004"
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

REPRESENTATION_INTENSITY = "intensity"
REPRESENTATION_GRADIENT = "gradient"
REPRESENTATION_STRUCTURAL = "structural"

VARIANT_REPRESENTATION_ID = {
    VARIANT_A_ID: REPRESENTATION_INTENSITY,
    VARIANT_B_ID: REPRESENTATION_GRADIENT,
    VARIANT_C_ID: REPRESENTATION_STRUCTURAL,
}

# Existing src.routing.select_representation_id mapping, used as a lever so
# frozen generate_representation() builds the requested existing module.
# Variant A does not copy the pair: characterize_pair leaves difficulty unset,
# which already routes to intensity.
ROUTING_DIFFICULTY_BY_REPRESENTATION = {
    REPRESENTATION_INTENSITY: None,
    REPRESENTATION_GRADIENT: "normal",
    REPRESENTATION_STRUCTURAL: "difficult",
}

EXPECTED_PAIR_01_STRIDES = {
    VARIANT_A_ID: {"ohrc": 15, "lroc": 8},
    VARIANT_B_ID: {"ohrc": 15, "lroc": 8},
    VARIANT_C_ID: {"ohrc": 15, "lroc": 8},
}

HYPOTHESIS = (
    "H1: On pair_01_equatorial, replacing the EXP-000 intensity representation "
    "with the existing gradient or structural representation, holding matching-"
    "view scale, SIFT parameters, Lowe ratio, and geometric verification "
    "fixed, increases the number of geometrically verified SIFT "
    "correspondences. "
    "H0: those representation changes do not increase verified correspondence "
    "yield on this pair, which would mean intensity is not shown to be the "
    "pair-01 bottleneck."
)

DECISION_RULE = (
    "The independent variable is valid only if representation_id actually "
    "differs across A/B/C (intensity / gradient / structural) while matching-"
    "view strides stay at the EXP-000 baseline (OHRC 15 / LROC 8). "
    "Representation is treated as improving verified correspondence only if B "
    "or C produces strictly more verified inliers than A. Equal verified "
    "counts mean intensity is not shown to be the bottleneck on this pair. "
    "Four-point DLT residuals are not accuracy. Independent accuracy remains "
    "NOT VALIDATED. One pair cannot establish a superior representation."
)


def pair_routed_for_representation(
    pair: RegistrationPair, representation_id: str
) -> RegistrationPair:
    """Return a pair copy that existing routing maps to *representation_id*.

    Variant A (intensity) returns the original pair so the frozen EXP-000
    path is used. Variants B and C copy only ``characterization.difficulty``
    onto a new pair object. The caller's pair is not mutated. Later pipeline
    stages should keep using the original pair.
    """

    if representation_id not in ROUTING_DIFFICULTY_BY_REPRESENTATION:
        raise ValueError(
            "unsupported representation_id: "
            f"{representation_id!r}; expected one of "
            f"{sorted(ROUTING_DIFFICULTY_BY_REPRESENTATION)}"
        )
    if representation_id == REPRESENTATION_INTENSITY:
        return pair

    difficulty = ROUTING_DIFFICULTY_BY_REPRESENTATION[representation_id]
    char = pair.characterization
    if char is None:
        new_char = PairCharacterization(difficulty=difficulty)
    else:
        new_char = char.model_copy(update={"difficulty": difficulty})
    return pair.model_copy(update={"characterization": new_char})


def snapshot_fixed_configuration() -> dict[str, Any]:
    """Everything held constant across variants, imported from EXP-000."""

    fixed = dict(snapshot_software_configuration())
    fixed.pop("pair_manifest_id", None)
    fixed.pop("representation_routing", None)
    matching_view = dict(fixed["matching_view"])
    matching_view.pop("scale_policy", None)
    matching_view.pop("relative_stride_factor_by_instrument", None)
    matching_view.pop("catalog_gsd_meters_by_instrument", None)
    fixed["matching_view"] = matching_view
    fixed["experiment_id"] = EXPERIMENT_ID
    fixed["inherited_from"] = BASELINE_EXPERIMENT_ID
    fixed["pair_manifest_id"] = PAIR_MANIFEST_ID
    fixed["independent_variable"] = "representation_id"
    fixed["matching_view_held_fixed"] = True
    fixed["expected_pair_01_strides"] = {"ohrc": 15, "lroc": 8}
    fixed["held_constant"] = [
        "input products and pair manifest",
        "matcher_id sift and all SiftSettings",
        "matching-view policy per_image_pixel_budget (OHRC stride 15, LROC stride 8 on pair 01)",
        "matching-view pixel budget 4,194,304",
        "downsample_method stride_decimation",
        "preprocessing (identity passthrough above the 16,777,216-pixel cap)",
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

    return {
        VARIANT_A_ID: {
            "label": "exp000_intensity_representation",
            "representation_id": REPRESENTATION_INTENSITY,
            "module": "src.representation.intensity",
            "builder": "build_intensity_array",
            "routing_difficulty": ROUTING_DIFFICULTY_BY_REPRESENTATION[REPRESENTATION_INTENSITY],
            "routing_rule": "difficulty None/easy -> intensity",
            "pair_for_generate_representation": "original_pair",
            "expected_pair_01_strides": EXPECTED_PAIR_01_STRIDES[VARIANT_A_ID],
            "representation_callable": "generate_representation(pair)",
        },
        VARIANT_B_ID: {
            "label": "existing_gradient_representation",
            "representation_id": REPRESENTATION_GRADIENT,
            "module": "src.representation.gradient",
            "builder": "build_gradient_array",
            "routing_difficulty": ROUTING_DIFFICULTY_BY_REPRESENTATION[REPRESENTATION_GRADIENT],
            "routing_rule": "difficulty normal -> gradient",
            "pair_for_generate_representation": (
                "copy with characterization.difficulty=normal; original pair is not mutated"
            ),
            "expected_pair_01_strides": EXPECTED_PAIR_01_STRIDES[VARIANT_B_ID],
            "representation_callable": "generate_representation(pair)",
        },
        VARIANT_C_ID: {
            "label": "existing_structural_representation",
            "representation_id": REPRESENTATION_STRUCTURAL,
            "module": "src.representation.structural",
            "builder": "build_structural_array",
            "routing_difficulty": ROUTING_DIFFICULTY_BY_REPRESENTATION[REPRESENTATION_STRUCTURAL],
            "routing_rule": "difficulty difficult -> structural",
            "pair_for_generate_representation": (
                "copy with characterization.difficulty=difficult; original pair is not mutated"
            ),
            "expected_pair_01_strides": EXPECTED_PAIR_01_STRIDES[VARIANT_C_ID],
            "representation_callable": "generate_representation(pair)",
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
    "REPRESENTATION_GRADIENT",
    "REPRESENTATION_INTENSITY",
    "REPRESENTATION_STRUCTURAL",
    "ROUTING_DIFFICULTY_BY_REPRESENTATION",
    "VARIANT_A_ID",
    "VARIANT_B_ID",
    "VARIANT_C_ID",
    "VARIANT_REPRESENTATION_ID",
    "pair_routed_for_representation",
    "snapshot_fixed_configuration",
    "snapshot_variant_configuration",
]
