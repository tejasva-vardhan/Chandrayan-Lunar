"""PS-closing phase 3: scale + cross-sensor optical robustness.

Baseline A is the production coarse-to-fine intensity path.
B applies common-physical-GSD matching views (scale mechanism).
C applies CLAHE cross-sensor intensity (appearance mechanism).

Available demo data is OHRC <-> LROC NAC only. This is cross-instrument
optical correspondence, not OHRC/TMC/IIRS multi-modal validation.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.io.exp000.config import snapshot_software_configuration
from src.io.exp002.config import LROC_NAC_CATALOG_GSD_METERS, LROC_NAC_CATALOG_INSTRUMENT
from src.matching.settings import CoarseToFineSettings
from src.representation.cross_sensor import (
    DEFAULT_CLAHE_CLIP_LIMIT,
    DEFAULT_CLAHE_TILE_GRID,
)
from src.representation.cross_sensor import (
    REPRESENTATION_ID as CROSS_SENSOR_ID,
)
from src.representation.settings import (
    SCALE_POLICY_COMMON_PHYSICAL_GSD,
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
    MatchingViewSettings,
    unvalidated_matching_view_defaults,
)

RECORD_ID = "PS-SCALE-MULTIMODAL"
BASELINE_EXPERIMENT_ID = "EXP-000"
CORRESPONDENCE_RECORD_ID = "PS-CORRESPONDENCE"

INDEPENDENT_ACCURACY_NOT_VALIDATED = "NOT VALIDATED"
DECISION_SUPPORTED = "SUPPORTED"
DECISION_NOT_SUPPORTED = "NOT SUPPORTED"
DECISION_INDETERMINATE = "INDETERMINATE"

FOOTPRINT_SOURCE = "NASA PDS ODE"
PRIMARY_PAIR_ID = "pair_02_mid_equatorial"

VARIANT_A_ID = "A"
VARIANT_B_ID = "B"
VARIANT_C_ID = "C"

PROTOCOL_COARSE_TO_FINE = "sift_coarse_to_fine_tiled_multiscale"
REPRESENTATION_INTENSITY = "intensity"
REPRESENTATION_CROSS_SENSOR = CROSS_SENSOR_ID

# Collapse floor: mechanism maintains a useful set if it keeps at least this
# fraction of A's verified inliers and occupied cells. Fixed before the run.
MAINTAIN_FRACTION = 0.5
MIN_USEFUL_INLIERS_ABOVE_MODEL = 1  # useful means > model min (4) => >= 5
RUNTIME_FACTOR_LIMIT = 12.0
GRID_BINS = 8

# Expected pair_02 strides under each scale policy (documented, not invented).
EXPECTED_PAIR_02_STRIDES_A = {"ohrc": 16, "lroc": 8}
EXPECTED_PAIR_02_STRIDES_B = {"ohrc": 16, "lroc": 9}

# Pair-02 ingested OHRC GSD; LROC gsd_meters is null so catalog 0.5 is used.
PAIR_02_OHRC_GSD_METERS = 0.28
PAIR_02_LROC_CATALOG_GSD_METERS = LROC_NAC_CATALOG_GSD_METERS

SCALE_HYPOTHESIS = (
    "H1-scale: On pair_02_mid_equatorial, the production coarse-to-fine "
    "intensity path maintains a useful verified correspondence set across "
    "the real OHRC/LROC native GSD difference, and applying "
    "common_physical_gsd matching views (B) does not collapse verified "
    "yield, 8x8 occupancy, or transform stability relative to A. "
    "H0-scale: the native GSD gap or GSD-normalised views cause collapse "
    "or unstable geometry."
)

MULTIMODAL_HYPOTHESIS = (
    "H1-cross-sensor: On the same pair, CLAHE cross-sensor intensity (C) "
    "maintains a useful verified correspondence set under OHRC-calibrated "
    "vs LROC Scaled-I/F appearance differences without spatial collapse "
    "or unstable geometry relative to intensity baseline A. "
    "H0-cross-sensor: the appearance adaptation collapses verified quality "
    "or spatial distribution. "
    "This tests cross-instrument optical appearance, not OHRC/TMC/IIRS "
    "multi-modal products (those are not in the current demo dataset)."
)

SCALE_DECISION_RULE = (
    "Scale is SUPPORTED only if: (1) a finite native GSD ratio is reported "
    "from ingested OHRC gsd_meters and LROC catalog fallback 0.5 m/px and "
    "differs from 1 by more than 5%; (2) A and B each produce verified "
    "inliers strictly above the projective DLT minimum; (3) B verified "
    "inliers and source/reference occupied cells are each at least "
    f"{MAINTAIN_FRACTION:g} of A's; (4) both transforms fit from more than "
    "4 inliers; (5) B's scale_policy is common_physical_gsd and observed "
    "strides differ from A's or effective GSDs are recorded. "
    "Raw match count is not success. Independent accuracy remains NOT "
    "VALIDATED. Do not retune."
)

MULTIMODAL_DECISION_RULE = (
    "Cross-sensor is SUPPORTED only if: (1) C uses representation_id "
    f"{CROSS_SENSOR_ID!r} while A uses intensity; (2) A and C each produce "
    "verified inliers strictly above the projective DLT minimum; (3) C "
    "verified inliers and source/reference occupied cells are each at least "
    f"{MAINTAIN_FRACTION:g} of A's; (4) both transforms fit from more than "
    "4 inliers. This is cross-instrument optical robustness, not full "
    "multi-modal OHRC/TMC/IIRS validation. Independent accuracy remains "
    "NOT VALIDATED. Do not retune."
)


def variant_a_matching_view_settings() -> MatchingViewSettings:
    return unvalidated_matching_view_defaults()


def variant_b_matching_view_settings() -> MatchingViewSettings:
    defaults = unvalidated_matching_view_defaults()
    return MatchingViewSettings(
        max_pixels_per_image=defaults.max_pixels_per_image,
        downsample_method=defaults.downsample_method,
        scale_policy=SCALE_POLICY_COMMON_PHYSICAL_GSD,
        catalog_gsd_meters_by_instrument=(
            (LROC_NAC_CATALOG_INSTRUMENT, LROC_NAC_CATALOG_GSD_METERS),
        ),
    )


def variant_c_matching_view_settings() -> MatchingViewSettings:
    return unvalidated_matching_view_defaults()


def snapshot_fixed_configuration() -> dict[str, Any]:
    fixed = dict(snapshot_software_configuration())
    fixed.pop("pair_manifest_id", None)
    matching_view = dict(fixed.get("matching_view") or {})
    matching_view.pop("scale_policy", None)
    fixed["matching_view"] = matching_view
    fixed["record_id"] = RECORD_ID
    fixed["inherited_from"] = BASELINE_EXPERIMENT_ID
    fixed["correspondence_baseline_record_id"] = CORRESPONDENCE_RECORD_ID
    fixed["primary_pair_manifest_id"] = PRIMARY_PAIR_ID
    fixed["matcher_family"] = "sift_coarse_to_fine"
    fixed["independent_variables"] = [
        "matching_view_scale_policy",
        "cross_sensor_intensity_representation",
    ]
    fixed["spatial_grid"] = {
        "grid_bins": GRID_BINS,
        "total_cells": GRID_BINS * GRID_BINS,
        "extent": "full_product_image_dimensions_not_point_bbox",
    }
    fixed["maintain_fraction"] = MAINTAIN_FRACTION
    fixed["runtime_factor_limit"] = RUNTIME_FACTOR_LIMIT
    fixed["modality_scope"] = {
        "available_instruments_in_demo_dataset": ["OHRC", "LRO_NAC"],
        "tmc_available": False,
        "iirs_available": False,
        "claim": (
            "cross-instrument optical correspondence (OHRC <-> LROC NAC), "
            "not full OHRC/TMC/IIRS multi-modal validation"
        ),
    }
    fixed["gsd_sources"] = {
        "ohrc": "ingested LunarProduct.gsd_meters when present",
        "lroc": (
            "catalog fallback 0.5 m/px (Robinson et al. 2010 / LROC SIS) "
            "used only when ingested gsd_meters is missing; not written "
            "onto LunarProduct; not SPICE-derived"
        ),
        "pair_02_expected": {
            "ohrc_gsd_meters": PAIR_02_OHRC_GSD_METERS,
            "lroc_gsd_meters": PAIR_02_LROC_CATALOG_GSD_METERS,
            "native_gsd_ratio_source_over_reference": (
                PAIR_02_OHRC_GSD_METERS / PAIR_02_LROC_CATALOG_GSD_METERS
            ),
        },
    }
    fixed["held_constant"] = [
        "input products and pair manifest",
        "coarse-to-fine tiled multi-scale SIFT correspondence path",
        "SIFT detector/descriptor and Lowe ratio 0.75",
        "matching-view pixel budget 4,194,304",
        "downsample_method stride_decimation",
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
    a_settings = variant_a_matching_view_settings()
    b_settings = variant_b_matching_view_settings()
    return {
        VARIANT_A_ID: {
            "label": "production_coarse_to_fine_intensity",
            "role": "control_production_candidate",
            "protocol_id": PROTOCOL_COARSE_TO_FINE,
            "representation_id": REPRESENTATION_INTENSITY,
            "scale_policy": SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
            "matching_view": {
                "scale_policy": a_settings.scale_policy,
                "max_pixels_per_image": a_settings.max_pixels_per_image,
                "downsample_method": a_settings.downsample_method,
            },
            "expected_pair_02_strides": dict(EXPECTED_PAIR_02_STRIDES_A),
            "coarse_to_fine": ctf,
        },
        VARIANT_B_ID: {
            "label": "coarse_to_fine_common_physical_gsd",
            "role": "scale_mechanism",
            "protocol_id": PROTOCOL_COARSE_TO_FINE,
            "representation_id": REPRESENTATION_INTENSITY,
            "scale_policy": SCALE_POLICY_COMMON_PHYSICAL_GSD,
            "matching_view": {
                "scale_policy": b_settings.scale_policy,
                "max_pixels_per_image": b_settings.max_pixels_per_image,
                "downsample_method": b_settings.downsample_method,
                "catalog_gsd_meters_by_instrument": [
                    {
                        "instrument": name,
                        "gsd_meters": gsd,
                        "used_only_when_ingested_gsd_missing": True,
                        "written_onto_lunar_product": False,
                        "spice_used": False,
                    }
                    for name, gsd in b_settings.catalog_gsd_meters_by_instrument
                ],
            },
            "expected_pair_02_strides": dict(EXPECTED_PAIR_02_STRIDES_B),
            "coarse_to_fine": ctf,
            "note": (
                "Uses known OHRC ingested GSD and LROC catalog GSD; does not "
                "invent a scale factor. Still stride_decimation."
            ),
        },
        VARIANT_C_ID: {
            "label": "coarse_to_fine_cross_sensor_clahe",
            "role": "cross_sensor_appearance_mechanism",
            "protocol_id": PROTOCOL_COARSE_TO_FINE,
            "representation_id": REPRESENTATION_CROSS_SENSOR,
            "scale_policy": SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
            "matching_view": {
                "scale_policy": SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
                "max_pixels_per_image": a_settings.max_pixels_per_image,
                "downsample_method": a_settings.downsample_method,
            },
            "expected_pair_02_strides": dict(EXPECTED_PAIR_02_STRIDES_A),
            "cross_sensor": {
                "method": "percentile_stretch_then_clahe",
                "clahe_clip_limit": DEFAULT_CLAHE_CLIP_LIMIT,
                "clahe_tile_grid": list(DEFAULT_CLAHE_TILE_GRID),
                "sensors_tested": ["OHRC", "LRO_NAC"],
                "not_tested": ["TMC", "IIRS"],
            },
            "coarse_to_fine": ctf,
        },
    }


__all__ = [
    "BASELINE_EXPERIMENT_ID",
    "CORRESPONDENCE_RECORD_ID",
    "DECISION_INDETERMINATE",
    "DECISION_NOT_SUPPORTED",
    "DECISION_SUPPORTED",
    "EXPECTED_PAIR_02_STRIDES_A",
    "EXPECTED_PAIR_02_STRIDES_B",
    "FOOTPRINT_SOURCE",
    "GRID_BINS",
    "INDEPENDENT_ACCURACY_NOT_VALIDATED",
    "MAINTAIN_FRACTION",
    "MIN_USEFUL_INLIERS_ABOVE_MODEL",
    "MULTIMODAL_DECISION_RULE",
    "MULTIMODAL_HYPOTHESIS",
    "PAIR_02_LROC_CATALOG_GSD_METERS",
    "PAIR_02_OHRC_GSD_METERS",
    "PRIMARY_PAIR_ID",
    "PROTOCOL_COARSE_TO_FINE",
    "RECORD_ID",
    "REPRESENTATION_CROSS_SENSOR",
    "REPRESENTATION_INTENSITY",
    "RUNTIME_FACTOR_LIMIT",
    "SCALE_DECISION_RULE",
    "SCALE_HYPOTHESIS",
    "VARIANT_A_ID",
    "VARIANT_B_ID",
    "VARIANT_C_ID",
    "snapshot_fixed_configuration",
    "snapshot_variant_configuration",
    "variant_a_matching_view_settings",
    "variant_b_matching_view_settings",
    "variant_c_matching_view_settings",
]
