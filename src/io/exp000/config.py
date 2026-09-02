"""Exact EXP-000 software-baseline configuration.

These values are copied from the owning modules' unvalidated software
defaults. They are recorded here so the experiment is reproducible. They
are not SIH thresholds, not a matcher freeze (D-007), and not a selected
lunar transform (D-010). Do not copy them into configs/default.yaml.
"""

from __future__ import annotations

from dataclasses import asdict

from src.control_points.settings import unvalidated_software_defaults as control_point_defaults
from src.matching.settings import SiftSettings
from src.preprocessing.settings import unvalidated_software_defaults as preprocessing_defaults
from src.refinement.settings import unvalidated_software_defaults as refinement_defaults
from src.registration.settings import unvalidated_software_defaults as registration_defaults
from src.representation.settings import unvalidated_matching_view_defaults
from src.verification.settings import unvalidated_software_defaults as verification_defaults

EXPERIMENT_ID = "EXP-000"
PAIR_MANIFEST_ID = "pair_01_equatorial"
FOOTPRINT_SOURCE = "NASA PDS ODE"

# Diagnostic registered crop: stay inside the existing registration output cap.
# preferred_side is an engineering window, not a scientifically validated crop.
DIAGNOSTIC_PREFERRED_SIDE_PX = 2048

# Explicit experiment-record vocabulary. These are reporting labels, not
# frozen LunarProduct / RegistrationResult field values.
INDEPENDENT_ACCURACY_NOT_VALIDATED = "NOT VALIDATED"
REFINEMENT_OUTCOME_INDETERMINATE = "INDETERMINATE"
REFINEMENT_OUTCOME_COORDINATES_UPDATED = "COORDINATES_UPDATED"
REFINEMENT_OUTCOME_NO_POINTS = "NO_POINTS"


def snapshot_software_configuration() -> dict[str, object]:
    """Return the exact parameter set EXP-000 will execute."""

    matching_view = unvalidated_matching_view_defaults()
    preprocessing = preprocessing_defaults()
    verification = verification_defaults()
    control_points = control_point_defaults()
    refinement = refinement_defaults()
    registration = registration_defaults()
    sift = SiftSettings()
    return {
        "experiment_id": EXPERIMENT_ID,
        "pair_manifest_id": PAIR_MANIFEST_ID,
        "footprint_source": FOOTPRINT_SOURCE,
        "matcher_id": "sift",
        "representation_routing": (
            "select_representation_id: difficulty None/easy -> intensity; "
            "characterize_pair currently leaves difficulty unset"
        ),
        "preprocessing": asdict(preprocessing),
        "matching_view": {
            "max_pixels_per_image": matching_view.max_pixels_per_image,
            "downsample_method": matching_view.downsample_method,
            "spatial_window": "full_image_stride_decimation_not_a_cropped_window",
            "coordinate_mapping": (
                "x_original = x_matching * x_scale; "
                "y_original = y_matching * y_scale; "
                "x_scale = y_scale = stride"
            ),
        },
        "sift": asdict(sift),
        "verification": asdict(verification),
        "control_points": asdict(control_points),
        "refinement": asdict(refinement),
        "registration": {
            "model_id": registration.model_id,
            "max_output_pixels": registration.max_output_pixels,
            "role": "software_baseline_not_d010_lunar_model",
        },
        "diagnostic_registration_crop": {
            "strategy": "bounded_reference_window_maximum_control_point_cover",
            "preferred_side_px": DIAGNOSTIC_PREFERRED_SIDE_PX,
            "max_output_pixels": registration.max_output_pixels,
            "note": (
                "Full-raster warp remains blocked by the existing "
                f"{registration.max_output_pixels}-pixel cap. Window size starts "
                "at preferred_side and grows to leftover budget. Placement "
                "maximises finite control-point inclusion inside that cap and "
                "does not change the fitted transform or original-image "
                "correspondence coordinates."
            ),
        },
        "evaluation": {
            "rmse": "sqrt(mean(stored inlier verification residuals^2)); not independent accuracy",
            "inlier_ratio_denominator": "len(CorrespondenceSet.matches)",
            "spatial_coverage": (
                "0.5 * (source_cp_bbox_area / source_image_area + "
                "reference_cp_bbox_area / reference_image_area)"
            ),
            "independent_ground_truth": False,
            "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        },
    }
