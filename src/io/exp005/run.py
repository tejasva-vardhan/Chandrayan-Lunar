"""EXP-005 existing-refinement ablation on pair_02_mid_equatorial.

Runs the frozen SIFT pipeline once through control-point selection, then:

* Variant A — ``refine_points_with_settings(..., identity_passthrough)``.
* Variant B — frozen ``refine_points()`` (zncc_parabolic_baseline).

Match, verification, RANSAC, representation, and control-point selection are
shared. Diagnostic rasters are not written. Coordinate change is not treated
as accuracy.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from src.control_points import select_control_points
from src.control_points.settings import unvalidated_software_defaults as control_point_defaults
from src.evaluation import evaluate
from src.geometry import characterize_pair
from src.ingestion import (
    DATA_ROOT_ENV,
    DataRootError,
    configured_data_root,
    find_product,
    ingest_product,
)
from src.io.exp000.run import _preprocess_guarded
from src.io.exp001.metrics import (
    coverage,
    inlier_ratio,
    inliers_above_model_minimum,
    occupancy,
    status_counts,
    verified_matches,
)
from src.io.exp001.validation import HeldOutSettings, held_out_validation
from src.io.exp002.run import (
    _arm_timed,
    _evaluation_report,
    _finite_max,
    _finite_min,
    _jsonable,
    _point_dump,
    _product_report,
    _registration_report,
    _reproducibility,
    _start_memory_trace,
    _stop_memory_trace,
    _timed,
    _transform_status,
    _write_json,
)
from src.io.exp005.config import (
    BASELINE_EXPERIMENT_ID,
    DECISION_RULE,
    EXPECTED_PAIR_02_STRIDES,
    EXPERIMENT_ID,
    FOOTPRINT_SOURCE,
    HYPOTHESIS,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    LROC_PRODUCT_ID,
    METHOD_IDENTITY,
    METHOD_ZNCC,
    OHRC_PRODUCT_ID,
    PAIR_MANIFEST_ID,
    SIFT_BASELINE_EXPERIMENT_ID,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_METHOD_ID,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
    variant_a_refinement_settings,
    variant_b_refinement_settings,
)
from src.io.exp005.diagnostics import (
    control_point_held_out,
    displacement_report,
    unselected_verified_checkpoints,
    zncc_acceptance_report,
)
from src.matching import match
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult
from src.refinement import refine_points, refine_points_with_settings
from src.registration import register
from src.representation import generate_representation
from src.verification import verify_matches
from src.verification.geometric_models import get_geometric_model
from src.verification.settings import unvalidated_software_defaults as verification_defaults

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VARIANT_ORDER = (VARIANT_A_ID, VARIANT_B_ID)
_HELD_OUT = HeldOutSettings(folds=5, rng_seed=0)


class Exp005Error(RuntimeError):
    """Raised when EXP-005 cannot start."""


def run_exp005(
    *,
    data_root: Path | None = None,
    output_dir: Path | None = None,
    record_path: Path | None = None,
) -> dict[str, Any]:
    """Run variants A and B on pair 02 and write the experiment record."""

    try:
        root = data_root if data_root is not None else configured_data_root()
    except DataRootError as exc:
        raise Exp005Error(str(exc)) from exc
    if root is None:
        raise Exp005Error(
            f"Set {DATA_ROOT_ENV} to the external demo dataset that contains "
            f"{OHRC_PRODUCT_ID} and {LROC_PRODUCT_ID}."
        )
    if not root.exists() or not root.is_dir():
        raise Exp005Error(f"data root is not an existing directory: {root}")

    ohrc_path = find_product(root, OHRC_PRODUCT_ID)
    lroc_path = find_product(root, LROC_PRODUCT_ID)
    if ohrc_path is None or lroc_path is None:
        raise Exp005Error(
            "ingest_product cannot start: EXP-005 pair-02 products were not "
            f"found under {DATA_ROOT_ENV}={root}. "
            f"OHRC {OHRC_PRODUCT_ID}: {ohrc_path}; "
            f"LROC {LROC_PRODUCT_ID}: {lroc_path}."
        )

    out = output_dir or (_REPO_ROOT / "outputs" / EXPERIMENT_ID / PAIR_MANIFEST_ID)
    lightweight = record_path or (
        _REPO_ROOT / "experiments" / EXPERIMENT_ID / "results" / f"{PAIR_MANIFEST_ID}.json"
    )
    out.mkdir(parents=True, exist_ok=True)
    lightweight.parent.mkdir(parents=True, exist_ok=True)

    record = _new_record()
    record["dataset"].update(
        {
            "ohrc_found": True,
            "lroc_found": True,
            "ohrc_source_name": ohrc_path.name,
            "lroc_source_name": lroc_path.name,
        }
    )

    _start_memory_trace()
    wall_start = time.perf_counter()
    try:
        source, reference = _timed(
            record,
            "ingest_product",
            lambda: (ingest_product(ohrc_path), ingest_product(lroc_path)),
        )
        record["stages"]["ingest_product"] = {
            "source": _product_report(source),
            "reference": _product_report(reference),
        }
    except Exception as exc:
        record["status"] = "failed"
        record["failed_stage"] = "ingest_product"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        return _finalize(record, wall_start, out, lightweight)

    _execute_pair(record, source, reference)
    return _finalize(record, wall_start, out, lightweight)


def run_exp005_from_products(
    source: LunarProduct,
    reference: LunarProduct,
    *,
    output_dir: Path | None = None,
    record_path: Path | None = None,
) -> dict[str, Any]:
    """Run both variants from already ingested products. Used by tests."""

    out = output_dir or (_REPO_ROOT / "outputs" / EXPERIMENT_ID / "synthetic")
    lightweight = record_path or (out / f"{PAIR_MANIFEST_ID}.json")
    out.mkdir(parents=True, exist_ok=True)
    lightweight.parent.mkdir(parents=True, exist_ok=True)
    record = _new_record()
    record["stages"]["ingest_product"] = {
        "source": _product_report(source),
        "reference": _product_report(reference),
        "note": "products supplied already ingested",
    }
    _start_memory_trace()
    wall_start = time.perf_counter()
    _execute_pair(record, source, reference)
    return _finalize(record, wall_start, out, lightweight)


def _execute_pair(
    record: dict[str, Any],
    source: LunarProduct,
    reference: LunarProduct,
) -> None:
    try:
        pair = _timed(record, "characterize_pair", lambda: characterize_pair(source, reference))
        record["stages"]["characterize_pair"] = _characterization_report(pair)
        pair, preprocess_report = _timed(
            record, "preprocess", lambda: _preprocess_guarded(pair, record)
        )
        record["stages"]["preprocess"] = preprocess_report
        representation = _timed(
            record, "generate_representation", lambda: generate_representation(pair)
        )
        record["stages"]["generate_representation"] = _matching_view_report(representation, pair)
        correspondences = _timed(
            record, "match", lambda image=representation: match(pair, image)
        )
        del representation
        record["stages"]["match"] = {
            "matcher_id": correspondences.matcher_id,
            "representation_id": correspondences.representation_id,
            "raw_match_count": len(correspondences.matches),
            "coordinates": "original_image_pixels_after_matching_view_scale",
            "shared_across_variants": True,
        }
        verified = _timed(record, "verify_matches", lambda: verify_matches(correspondences, pair))
        control_points = _timed(
            record, "select_control_points", lambda: select_control_points(verified, pair)
        )
    except Exception as exc:
        record["status"] = "failed"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        return

    model = get_geometric_model(verification_defaults().model_id)
    inliers = verified_matches(list(verified.matches))
    grid_bins = control_point_defaults().grid_bins
    record["stages"]["verify_matches"] = {
        "raw_match_count": len(verified.matches),
        "status_counts": status_counts(list(verified.matches)),
        "verified_inlier_count": len(inliers),
        "rejected_count": status_counts(list(verified.matches))["rejected"],
        "inlier_ratio": inlier_ratio(list(verified.matches)),
        "model_min_samples": model.min_samples,
        "inliers_above_model_minimum": inliers_above_model_minimum(
            list(verified.matches), model.min_samples
        ),
        "exceeds_model_minimum": len(inliers) > model.min_samples,
        "residual_meaning": "verification_image_space_transfer_error_pixels",
        "inlier_residual_min": _finite_min(item.residual for item in inliers),
        "inlier_residual_max": _finite_max(item.residual for item in inliers),
        "shared_across_variants": True,
    }
    record["stages"]["spatial_distribution"] = {
        "verified_match_coverage": coverage(inliers, pair),
        "verified_match_occupancy": occupancy(inliers, pair, grid_bins),
        "shared_across_variants": True,
    }
    record["stages"]["select_control_points"] = {
        "control_point_count": len(control_points),
        "selection_succeeded": len(control_points) >= model.min_samples,
        "points": [_point_dump(point) for point in control_points],
        "shared_across_variants": True,
    }
    record["stages"]["matcher_held_out_validation"] = held_out_validation(
        inliers,
        model_id=verification_defaults().model_id,
        settings=_HELD_OUT,
    )
    record["stages"]["matcher_held_out_validation"]["note"] = (
        "This split is on verified correspondences and does not use refined "
        "coordinates. It is the EXP-001 SIFT control on this pair, identical "
        "for A and B. It is not independent accuracy."
    )

    variants: dict[str, dict[str, Any]] = {}
    for variant_id in _VARIANT_ORDER:
        variants[variant_id] = _run_variant(
            variant_id, pair, verified, control_points, inliers, model
        )

    record["variants"] = variants
    record["comparison"] = _comparison(record, variants)
    record["interpretation"] = _interpretation(record, variants, model.min_samples)
    failed = [
        variant_id for variant_id, arm in variants.items() if arm.get("status") != "completed"
    ]
    if failed:
        record["status"] = "failed"
        record["failed_stage"] = "variant:" + ",".join(failed)
        record["failure"] = "; ".join(
            f"{variant_id}: {variants[variant_id].get('failure')}" for variant_id in failed
        )
        return
    record["status"] = "completed"
    record["failed_stage"] = None


def _run_variant(
    variant_id: str,
    pair: RegistrationPair,
    verified: Any,
    control_points: list[ControlPoint],
    inliers: list[Any],
    model: Any,
) -> dict[str, Any]:
    method_id = VARIANT_METHOD_ID[variant_id]
    arm: dict[str, Any] = {
        "variant_id": variant_id,
        "matcher_id": "sift",
        "method_id": method_id,
        "uses_shared_correspondences": True,
        "uses_shared_control_points": True,
        "runtime_seconds": {},
        "memory": {},
    }
    try:
        if variant_id == VARIANT_A_ID:
            refined = _arm_timed(
                arm,
                "refine_points",
                lambda: refine_points_with_settings(
                    control_points, pair, variant_a_refinement_settings()
                ),
            )
        else:
            refined = _arm_timed(
                arm, "refine_points", lambda: refine_points(control_points, pair)
            )
        registered = _arm_timed(
            arm,
            "register",
            lambda points=refined: register(pair, points, verified),
        )
        evaluated = _arm_timed(
            arm, "evaluate", lambda result=registered: evaluate(result, pair)
        )
        displacement = _arm_timed(
            arm,
            "displacement_report",
            lambda: displacement_report(control_points, refined),
        )
        zncc_report = _arm_timed(
            arm,
            "zncc_acceptance_report",
            lambda: zncc_acceptance_report(
                pair,
                control_points,
                refined,
                variant_b_refinement_settings()
                if variant_id == VARIANT_B_ID
                else variant_a_refinement_settings(),
            ),
        )
        cp_held_out = _arm_timed(
            arm,
            "control_point_held_out",
            lambda points=refined: control_point_held_out(
                points,
                model_id=verification_defaults().model_id,
                settings=_HELD_OUT,
            ),
        )
        checkpoints = _arm_timed(
            arm,
            "unselected_verified_checkpoints",
            lambda result=registered: unselected_verified_checkpoints(
                _transform_matrix(result), inliers, control_points
            ),
        )
    except Exception as exc:
        arm["status"] = "failed"
        arm["failed_stage"] = arm.get("_stage", "unrecorded")
        arm["failure"] = f"{type(exc).__name__}: {exc}"
        arm.pop("_stage", None)
        return arm

    arm["select_control_points"] = {
        "control_point_count": len(control_points),
        "selection_succeeded": len(control_points) >= model.min_samples,
    }
    arm["refine_points"] = displacement
    arm["refine_points"]["method_id"] = method_id
    arm["zncc_acceptance"] = zncc_report
    arm["register"] = _registration_report(registered, model.min_samples, len(refined))
    arm["evaluate"] = _evaluation_report(evaluated)
    arm["control_point_held_out"] = cp_held_out
    arm["unselected_verified_checkpoints"] = checkpoints
    arm["status"] = "completed"
    arm["failed_stage"] = None
    arm.pop("_stage", None)
    arm["runtime_seconds"]["variant_total"] = sum(
        float(value) for value in arm["runtime_seconds"].values()
    )
    return arm


def _matching_view_report(representation: Any, pair: RegistrationPair) -> dict[str, Any]:
    metadata = getattr(representation, "metadata", {}) or {}
    return {
        "representation_id": getattr(representation, "representation_id", None),
        "source_matching_view": _matching_view_side(
            metadata.get("source_matching_view"), pair.source
        ),
        "reference_matching_view": _matching_view_side(
            metadata.get("reference_matching_view"), pair.reference
        ),
        "coordinate_mapping": (
            "x_original = x_matching * stride; y_original = y_matching * stride"
        ),
        "spatial_window": "full_image_stride_decimation_not_a_cropped_window",
        "resampling": "stride_decimation",
        "shared_across_variants": True,
    }


def _matching_view_side(view: Any, product: LunarProduct) -> dict[str, Any]:
    payload = _jsonable(view) if isinstance(view, dict) else {}
    stride = int(payload.get("stride") or 1)
    matching_shape = payload.get("matching_shape") or []
    matching_pixels = None
    if isinstance(matching_shape, list) and len(matching_shape) == 2:
        matching_pixels = int(matching_shape[0]) * int(matching_shape[1])
    payload.update(
        {
            "ingested_gsd_meters": product.gsd_meters,
            "matching_pixel_count": matching_pixels,
            "stride": stride,
        }
    )
    return payload


def _comparison(record: dict[str, Any], variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    shared_verify = record.get("stages", {}).get("verify_matches") or {}
    shared_select = record.get("stages", {}).get("select_control_points") or {}
    rows = []
    for variant_id in _VARIANT_ORDER:
        arm = variants.get(variant_id) or {}
        refine = arm.get("refine_points") or {}
        zncc = arm.get("zncc_acceptance") or {}
        register = arm.get("register") or {}
        unselected = arm.get("unselected_verified_checkpoints") or {}
        cp_held = arm.get("control_point_held_out") or {}
        rows.append(
            {
                "variant": variant_id,
                "method_id": arm.get("method_id"),
                "verified_inliers": shared_verify.get("verified_inlier_count"),
                "control_point_count": shared_select.get("control_point_count"),
                "coordinates_changed_count": refine.get("coordinates_changed_count"),
                "mean_displacement_pixels": refine.get("mean_displacement_pixels"),
                "max_displacement_pixels": refine.get("max_displacement_pixels"),
                "accepted_count": zncc.get("accepted_count"),
                "rejected_count": zncc.get("rejected_count"),
                "unselected_checkpoint_rmse": _rmse(unselected),
                "control_point_held_out_rmse": _rmse(cp_held),
                "transform_status": _transform_status(register),
                "refinement_status": refine.get("outcome"),
                "runtime_seconds": arm.get("runtime_seconds"),
            }
        )
    return {"rows": rows}


def _interpretation(
    record: dict[str, Any], variants: dict[str, dict[str, Any]], min_samples: int
) -> dict[str, Any]:
    shared_verify = record.get("stages", {}).get("verify_matches") or {}
    shared_select = record.get("stages", {}).get("select_control_points") or {}
    shared_view = record.get("stages", {}).get("generate_representation") or {}
    a = variants.get(VARIANT_A_ID) or {}
    b = variants.get(VARIANT_B_ID) or {}
    a_refine = a.get("refine_points") or {}
    b_refine = b.get("refine_points") or {}
    methods_applied = (
        a.get("method_id") == METHOD_IDENTITY and b.get("method_id") == METHOD_ZNCC
    )
    shared_points = bool(
        a.get("uses_shared_control_points") and b.get("uses_shared_control_points")
    )
    independent_variable_applied = bool(methods_applied and shared_points)
    changed = int(b_refine.get("coordinates_changed_count") or 0)
    coordinates_changed = changed > 0
    a_zero_change = int(a_refine.get("coordinates_changed_count") or 0) == 0

    primary_a, primary_label = _primary_held_out(a)
    primary_b, _ = _primary_held_out(b)
    held_out_comparable = primary_a is not None and primary_b is not None
    held_out_improved = bool(held_out_comparable and primary_b < primary_a)
    hypothesis_supported = bool(
        independent_variable_applied
        and a_zero_change
        and coordinates_changed
        and held_out_improved
    )
    source_stride = (shared_view.get("source_matching_view") or {}).get("stride")
    reference_stride = (shared_view.get("reference_matching_view") or {}).get("stride")
    return {
        "primary_metric": (
            "held_out_checkpoint_rmse_strictly_lower_after_measurable_coordinate_change"
        ),
        "held_out_metric_used": primary_label,
        "model_min_samples": min_samples,
        "decision_rule": DECISION_RULE,
        "expected_pair_02_strides": EXPECTED_PAIR_02_STRIDES,
        "observed_strides": {"ohrc": source_stride, "lroc": reference_stride},
        "verified_inliers": shared_verify.get("verified_inlier_count"),
        "control_point_count": shared_select.get("control_point_count"),
        "method_ids_by_variant": {
            VARIANT_A_ID: a.get("method_id"),
            VARIANT_B_ID: b.get("method_id"),
        },
        "coordinates_changed_count_by_variant": {
            VARIANT_A_ID: a_refine.get("coordinates_changed_count"),
            VARIANT_B_ID: b_refine.get("coordinates_changed_count"),
        },
        "mean_displacement_pixels_by_variant": {
            VARIANT_A_ID: a_refine.get("mean_displacement_pixels"),
            VARIANT_B_ID: b_refine.get("mean_displacement_pixels"),
        },
        "max_displacement_pixels_by_variant": {
            VARIANT_A_ID: a_refine.get("max_displacement_pixels"),
            VARIANT_B_ID: b_refine.get("max_displacement_pixels"),
        },
        "held_out_rmse_by_variant": {
            VARIANT_A_ID: primary_a,
            VARIANT_B_ID: primary_b,
        },
        "independent_variable_applied": independent_variable_applied,
        "identity_left_coordinates_unchanged": a_zero_change,
        "coordinates_changed": coordinates_changed,
        "held_out_comparable": held_out_comparable,
        "held_out_improved": held_out_improved,
        "hypothesis_supported": hypothesis_supported,
        "coordinate_change_is_not_accuracy": True,
        "matcher_derived_held_out_is_not_ground_truth": True,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "independent_validation_status": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "four_point_dlt_residuals_are_not_accuracy": True,
        "limitations": _limitations(
            independent_variable_applied,
            a_zero_change,
            coordinates_changed,
            held_out_comparable,
            held_out_improved,
            shared_verify.get("verified_inlier_count"),
            min_samples,
        ),
    }


def _primary_held_out(arm: dict[str, Any]) -> tuple[float | None, str]:
    unselected = _rmse(arm.get("unselected_verified_checkpoints") or {})
    if unselected is not None:
        return unselected, "unselected_verified_checkpoints"
    kfold = _rmse(arm.get("control_point_held_out") or {})
    if kfold is not None:
        return kfold, "control_point_kfold"
    return None, "none"


def _rmse(payload: dict[str, Any]) -> float | None:
    summary = payload.get("checkpoint_transfer_error_pixels") or payload.get(
        "held_out_transfer_error_pixels"
    )
    if not isinstance(summary, dict):
        return None
    value = summary.get("rmse")
    if value is None:
        return None
    return float(value)


def _limitations(
    independent_variable_applied: bool,
    a_zero_change: bool,
    coordinates_changed: bool,
    held_out_comparable: bool,
    held_out_improved: bool,
    verified_count: int | None,
    min_samples: int,
) -> list[str]:
    notes = [
        "Independent accuracy is NOT VALIDATED. There is no surveyed lunar control.",
        "Matcher-derived held-out points are not ground truth.",
        "Coordinate change is not accuracy.",
        "evaluate().rmse is stored verification-inlier residual RMSE and does "
        "not recompute residuals after refinement.",
        "ZNCC + parabolic is a same-modality software baseline, not a "
        "multimodal OHRC/LROC solution.",
        "Overlap is not recomputed from the products. The manifest declares "
        "overlap_status=verified from NASA PDS ODE footprints.",
        "Full-raster registration remains blocked by the existing 16,777,216-pixel cap.",
        "This experiment runs pair_02_mid_equatorial only.",
        "No refinement algorithm, matcher, SIFT, representation, RANSAC, or "
        "registration change was introduced.",
    ]
    if not independent_variable_applied:
        notes.append(
            "Variants did not apply identity vs zncc_parabolic_baseline on the "
            "same selected control points."
        )
    if not a_zero_change:
        notes.append(
            "Variant A (identity) changed coordinates, so the no-refinement "
            "control is invalid."
        )
    if not coordinates_changed:
        notes.append(
            "Variant B changed zero coordinates, so held-out improvement cannot "
            "be attributed to refinement."
        )
    if not held_out_comparable:
        notes.append(
            "The same held-out RMSE could not be compared before vs after "
            "refinement."
        )
    if coordinates_changed and held_out_comparable and not held_out_improved:
        notes.append(
            "Coordinates changed but held-out RMSE did not strictly decrease, "
            "so refinement is not shown to improve geometric consistency."
        )
    if verified_count is not None and verified_count == min_samples:
        notes.append(
            "Verified inliers equal the projective DLT minimum, so the fit is "
            "unfalsifiable."
        )
    return notes


def _transform_matrix(result: RegistrationResult) -> Any:
    transformation = result.transformation
    if transformation is None:
        return None
    matrix = transformation.parameters.get("matrix")
    if matrix is None:
        return None
    return np.array(matrix, dtype=float)


def _characterization_report(pair: RegistrationPair) -> dict[str, Any]:
    char = pair.characterization
    return {
        "pair_id": pair.pair_id,
        "characterization": None
        if char is None
        else {
            "sensor_pair": char.sensor_pair,
            "modality": char.modality,
            "gsd_ratio": char.gsd_ratio,
            "sun_angle_difference_degrees": char.sun_angle_difference_degrees,
            "difficulty": char.difficulty,
            "quality_flags": list(char.quality_flags),
        },
        "illumination_note": (
            "sun_angle_difference_degrees is None: LunarProduct carries no Sun "
            "vector and SPICE is not implemented"
        ),
        "gsd_ratio_note": (
            "characterize_pair leaves gsd_ratio None when either product lacks "
            "ingested gsd_meters; EXP-005 does not invent that pair scalar"
        ),
        "representation_note": (
            "characterize_pair leaves difficulty unset, so frozen "
            "generate_representation selects intensity, matching the EXP-001 "
            "SIFT arm."
        ),
    }


def _new_record() -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "pair_manifest_id": PAIR_MANIFEST_ID,
        "status": "running",
        "failed_stage": None,
        "hypothesis": HYPOTHESIS,
        "decision_rule": DECISION_RULE,
        "inherited_from": BASELINE_EXPERIMENT_ID,
        "sift_baseline_experiment_id": SIFT_BASELINE_EXPERIMENT_ID,
        "fixed_configuration": snapshot_fixed_configuration(),
        "variant_configuration": snapshot_variant_configuration(),
        "dataset": {
            "data_root_env": DATA_ROOT_ENV,
            "footprint_source": FOOTPRINT_SOURCE,
            "ohrc_product_id": OHRC_PRODUCT_ID,
            "lroc_product_id": LROC_PRODUCT_ID,
        },
        "stages": {},
        "variants": {},
        "warnings": [],
        "safety_limit_events": [],
        "runtime_seconds": {},
        "memory": {},
        "reproducibility": _reproducibility(),
    }


def _finalize(
    record: dict[str, Any],
    wall_start: float,
    output_dir: Path,
    lightweight: Path,
) -> dict[str, Any]:
    record["runtime_seconds"]["total"] = time.perf_counter() - wall_start
    _stop_memory_trace(record)
    _write_json(lightweight, record)
    _write_json(output_dir / "record.json", record)
    return record


__all__ = ["Exp005Error", "run_exp005", "run_exp005_from_products"]
