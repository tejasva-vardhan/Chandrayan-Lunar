"""Exact EXP-001 controlled-comparison configuration.

EXP-001 asks one question: does the choice of matcher materially change
verified correspondence yield for Chandrayaan-2 OHRC <-> LROC imagery?

Everything except the matcher is pinned to the EXP-000 values, so the
comparison is controlled. The fixed block below is imported from EXP-000's
own snapshot rather than retyped, which makes drift between the two
experiments impossible by construction.

None of these values is an SIH threshold, a matcher freeze (D-007), or a
selected lunar transform (D-010). Do not copy them into configs/default.yaml.
"""

from __future__ import annotations

from typing import Any

from src.io.exp000.config import snapshot_software_configuration
from src.matching.portfolio import PORTFOLIO_MATCHER_IDS, matcher_parameters

EXPERIMENT_ID = "EXP-001"
BASELINE_EXPERIMENT_ID = "EXP-000"

# Reporting vocabulary. These are record labels, not frozen model field values.
INDEPENDENT_ACCURACY_NOT_VALIDATED = "NOT VALIDATED"
REFINEMENT_OUTCOME_INDETERMINATE = "INDETERMINATE"
REFINEMENT_OUTCOME_COORDINATES_UPDATED = "COORDINATES_UPDATED"
REFINEMENT_OUTCOME_NO_POINTS = "NO_POINTS"

FOOTPRINT_SOURCE = "NASA PDS ODE"

# Mirrors data/manifests/demo_pairs.yaml. tests/unit/test_exp001_config.py
# parses that manifest and asserts this registry matches it, so the two
# cannot drift.
PAIR_REGISTRY: dict[str, dict[str, str]] = {
    "pair_01_equatorial": {
        "ohrc_product_id": "ch2_ohr_ncp_20210402T0546284043_d_img_d18",
        "lroc_product_id": "M150368601RC",
    },
    "pair_02_mid_equatorial": {
        "ohrc_product_id": "ch2_ohr_ncp_20250612T2229094979_d_img_d18",
        "lroc_product_id": "M1504316436RC",
    },
    "pair_03_south_mid": {
        "ohrc_product_id": "ch2_ohr_ncp_20230302T1959055531_d_img_n18",
        "lroc_product_id": "M106979273RC",
    },
    "pair_04_south_pole": {
        "ohrc_product_id": "ch2_ohr_ncp_20260103T1005176450_d_img_d18",
        "lroc_product_id": "M175153469LC",
    },
}

# pair_01 first: it is the pair EXP-000 ran, so its row is directly
# comparable to the committed baseline. The rest are generalisation
# evidence only and must not be used to choose parameters.
PRIMARY_PAIR_ID = "pair_01_equatorial"
GENERALIZATION_PAIR_IDS: tuple[str, ...] = (
    "pair_02_mid_equatorial",
    "pair_03_south_mid",
    "pair_04_south_pole",
)

HYPOTHESIS = (
    "H1: On Chandrayaan-2 OHRC <-> LROC NAC pairs, replacing the SIFT "
    "baseline with an illumination/appearance-robust matcher materially "
    "increases the number of geometrically verified correspondences beyond "
    "the four-point projective DLT minimum, holding the matching-view "
    "policy, preprocessing, coordinate mapping, geometric model, residual "
    "threshold, RANSAC budget, random seed, control-point policy, and "
    "evaluation procedure constant. "
    "H0: matcher choice does not move verified yield above that minimum, "
    "which would mean the correspondence bottleneck lies elsewhere."
)

PREREGISTERED_EXPECTATIONS = [
    (
        "RIFT is expected to dominate under radiation change. Measured on "
        "synthetic ground truth in tests/scientific/test_synthetic_rift.py: "
        "under contrast reversal RIFT recovers the true shift while SIFT and "
        "ORB lose a usable consensus. Exact raw counts are not part of this "
        "expectation because they depend on the synthetic texture draw."
    ),
    (
        "RIFT is expected to fail under scale change. Its descriptor patch is "
        "a fixed pixel size, so a residual scale difference between the two "
        "matching views is not absorbed. Measured on the same synthetic "
        "harness: at 2x scale RIFT yield collapses while SIFT still returns "
        "matches. This is a stated confounder, not a result."
    ),
    (
        "ORB is expected to be the weakest of the three on real cross-"
        "instrument data: its intensity-comparison descriptor is not designed "
        "for radiation change and its pyramid gives only partial scale "
        "invariance."
    ),
]

# The comparison's decision rule, fixed before any real-data run.
DECISION_RULE = (
    "A matcher counts as improving verified yield only if it produces "
    "strictly more verified inliers than the geometric model's minimum "
    "sample size (4 for projective_2d_baseline). A verified count of exactly "
    "4 means RANSAC's consensus set is the minimal sample itself, no "
    "correspondence corroborated the fit, and the near-zero fit residual is "
    "an algebraic identity rather than evidence."
)


def snapshot_fixed_configuration() -> dict[str, Any]:
    """Everything held constant across matchers.

    Imported from the EXP-000 snapshot so the two experiments cannot diverge.
    The EXP-000 ``matcher_id`` and ``sift`` keys are removed here because the
    matcher is the independent variable, not a fixed parameter; per-matcher
    parameters are reported by ``snapshot_matcher_configuration``.
    """

    fixed = dict(snapshot_software_configuration())
    fixed.pop("matcher_id", None)
    fixed.pop("sift", None)
    fixed.pop("pair_manifest_id", None)
    fixed["experiment_id"] = EXPERIMENT_ID
    fixed["inherited_from"] = BASELINE_EXPERIMENT_ID
    fixed["held_constant"] = [
        "input products and pair manifest",
        "matching-view policy (stride_decimation, 4,194,304 pixels per image)",
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
        "Lowe ratio threshold 0.75 and min_matches 4 in every adapter",
    ]
    fixed["independent_variable"] = "matcher_id"
    fixed["single_representation_per_pair"] = (
        "generate_representation is called once per pair and the identical "
        "RepresentationResult object is passed to every matcher, so the "
        "matching view, stride, validity masks, and coordinate scales are the "
        "same objects rather than merely the same settings"
    )
    fixed["held_out_validation"] = {
        "design": "k-fold split of verified correspondences",
        "folds": 5,
        "rng_seed": 0,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "note": (
            "held-out transfer error is not independent accuracy; there is no "
            "surveyed lunar control in this project's data"
        ),
    }
    return fixed


def snapshot_matcher_configuration() -> dict[str, Any]:
    """Native parameters of every matcher in the comparison.

    Recorded before interpreting any result. No parameter here was changed
    after seeing a matcher's output.
    """

    return {
        matcher_id: matcher_parameters(matcher_id)
        for matcher_id in PORTFOLIO_MATCHER_IDS
    }


def excluded_matchers() -> list[dict[str, str]]:
    """Candidates considered and rejected, with the reason each was rejected.

    Recording the rejections matters as much as recording the results: a
    comparison that quietly omits the strongest candidate class is not a fair
    comparison, so the blocker is stated instead of being papered over.
    """

    return [
        {
            "candidate": "RIFT / RIFT2 via an existing package",
            "status": "no reliable dependency; implemented in-repository instead",
            "detail": (
                "No maintained PyPI distribution of the RIFT image matcher "
                "exists. The PyPI project named 'rift' is LIGO "
                "gravitational-wave parameter estimation software and is "
                "unrelated; 'rift2' does not exist. 'phasepack' is an "
                "unmaintained phase-congruency port. RIFT was therefore "
                "implemented directly over numpy and scipy, which are already "
                "project dependencies, and validated against synthetic ground "
                "truth in tests/scientific/test_synthetic_rift.py."
            ),
        },
        {
            "candidate": "LoFTR / LightGlue (dense or learned matching)",
            "status": "blocked; not run, not simulated",
            "detail": (
                "Three independent blockers. (1) Reproducibility: kornia's "
                "LoFTR and LightGlue download pretrained weights from the "
                "network at first use, so a run is not hermetic and the "
                "weights are not version-pinned by the dependency. "
                "(2) Experimental control: both are built for inputs of "
                "roughly 640 pixels per side and LoFTR's attention cost grows "
                "quadratically with pixel count. The EXP-000 matching views "
                "are 5212x800 and 6528x633, so running them would require "
                "changing the matching-view stride for one matcher only, "
                "which is exactly the confound this experiment is designed to "
                "exclude. (3) Weight: torch plus kornia is a multi-gigabyte "
                "addition to a project whose current dependency set is four "
                "packages. Faking the arm or bolting on a fragile dependency "
                "would be worse than reporting the blocker."
            ),
        },
        {
            "candidate": "AKAZE / KAZE / BRISK",
            "status": "unavailable in the installed OpenCV build",
            "detail": (
                "opencv-python-headless 5.0.0.93 on this environment exposes "
                "SIFT, ORB, FAST, GFTT, and MSER only; AKAZE, KAZE, and BRISK "
                "are absent from the cv2 namespace. ORB is therefore the "
                "available second OpenCV detector/descriptor family."
            ),
        },
    ]


__all__ = [
    "BASELINE_EXPERIMENT_ID",
    "DECISION_RULE",
    "EXPERIMENT_ID",
    "FOOTPRINT_SOURCE",
    "GENERALIZATION_PAIR_IDS",
    "HYPOTHESIS",
    "INDEPENDENT_ACCURACY_NOT_VALIDATED",
    "PAIR_REGISTRY",
    "PREREGISTERED_EXPECTATIONS",
    "PRIMARY_PAIR_ID",
    "REFINEMENT_OUTCOME_COORDINATES_UPDATED",
    "REFINEMENT_OUTCOME_INDETERMINATE",
    "REFINEMENT_OUTCOME_NO_POINTS",
    "excluded_matchers",
    "snapshot_fixed_configuration",
    "snapshot_matcher_configuration",
]
