"""Run the complete EXP-000 real-data baseline through frozen pipeline stages."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import numpy as np

from src.control_points import select_control_points
from src.evaluation import evaluate
from src.geometry import characterize_pair
from src.ingestion import (
    DATA_ROOT_ENV,
    PAIR_01_LROC_ID,
    PAIR_01_OHRC_ID,
    DataRootError,
    configured_data_root,
    find_product,
    ingest_product,
    mmap_product_array,
)
from src.io.exp000.config import (
    DIAGNOSTIC_PREFERRED_SIDE_PX,
    EXPERIMENT_ID,
    FOOTPRINT_SOURCE,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    PAIR_MANIFEST_ID,
    REFINEMENT_OUTCOME_COORDINATES_UPDATED,
    REFINEMENT_OUTCOME_INDETERMINATE,
    REFINEMENT_OUTCOME_NO_POINTS,
    snapshot_software_configuration,
)
from src.io.exp000.diagnostic import (
    control_point_crop_report,
    diagnostic_crop_window,
    projective_fit_residuals,
    warp_diagnostic_crop,
)
from src.io.exports import export_result
from src.matching import match
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult
from src.preprocessing import preprocess
from src.refinement import refine_points
from src.registration import register
from src.registration.result import FLAG_OUTPUT_TOO_LARGE
from src.registration.settings import unvalidated_software_defaults
from src.representation import generate_representation
from src.verification import verify_matches

_REPO_ROOT = Path(__file__).resolve().parents[3]
T = TypeVar("T")


class Exp000Error(RuntimeError):
    """Raised when EXP-000 cannot start or a recorded stage fails."""


def run_exp000(
    *,
    data_root: Path | None = None,
    output_dir: Path | None = None,
    record_path: Path | None = None,
) -> dict[str, Any]:
    """Execute ingest through export for pair 01 and return the experiment record."""

    try:
        root = data_root if data_root is not None else configured_data_root()
    except DataRootError as exc:
        raise Exp000Error(str(exc)) from exc
    if root is None:
        raise Exp000Error(
            f"Set {DATA_ROOT_ENV} to the external demo dataset that contains "
            f"{PAIR_01_OHRC_ID} and {PAIR_01_LROC_ID}."
        )
    if not root.exists() or not root.is_dir():
        raise Exp000Error(f"data root is not an existing directory: {root}")
    ohrc_path = find_product(root, PAIR_01_OHRC_ID)
    lroc_path = find_product(root, PAIR_01_LROC_ID)
    if ohrc_path is None or lroc_path is None:
        _write_start_failure(
            output_dir=output_dir,
            record_path=record_path,
            root=root,
            ohrc_path=ohrc_path,
            lroc_path=lroc_path,
        )
        raise Exp000Error(
            "ingest_product cannot start: EXP-000 pair-01 products were not "
            f"found under {DATA_ROOT_ENV}={root}. "
            f"OHRC {PAIR_01_OHRC_ID}: {ohrc_path}; "
            f"LROC {PAIR_01_LROC_ID}: {lroc_path}."
        )

    out, export_dir, lightweight, record = _prepare_record(
        output_dir=output_dir,
        record_path=record_path,
        ohrc_source_name=ohrc_path.name,
        lroc_source_name=lroc_path.name,
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
        if record["failed_stage"] is None:
            record["failed_stage"] = "ingest_product"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        return _finalize(record, wall_start, out, lightweight)
    return _execute_after_ingest(
        source, reference, record, out, export_dir, lightweight, wall_start
    )


def run_exp000_from_products(
    source: LunarProduct,
    reference: LunarProduct,
    *,
    output_dir: Path,
    record_path: Path,
) -> dict[str, Any]:
    """Run characterize through export on already ingested products.

    Used by tests. The real EXP-000 entry point is run_exp000(), which also
    performs ingest_product on the named pair-01 files.
    """

    out, export_dir, lightweight, record = _prepare_record(
        output_dir=output_dir,
        record_path=record_path,
        ohrc_source_name=source.product_id,
        lroc_source_name=reference.product_id,
    )
    _start_memory_trace()
    wall_start = time.perf_counter()
    record["stages"]["ingest_product"] = {
        "source": _product_report(source),
        "reference": _product_report(reference),
        "note": "products supplied already ingested",
    }
    return _execute_after_ingest(
        source, reference, record, out, export_dir, lightweight, wall_start
    )


def _prepare_record(
    *,
    output_dir: Path | None,
    record_path: Path | None,
    ohrc_source_name: str,
    lroc_source_name: str,
) -> tuple[Path, Path, Path, dict[str, Any]]:
    out = output_dir or (_REPO_ROOT / "outputs" / EXPERIMENT_ID / PAIR_MANIFEST_ID)
    out.mkdir(parents=True, exist_ok=True)
    export_dir = out / "export"
    lightweight = record_path or (
        _REPO_ROOT / "experiments" / EXPERIMENT_ID / "results" / f"{PAIR_MANIFEST_ID}.json"
    )
    lightweight.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "pair_manifest_id": PAIR_MANIFEST_ID,
        "status": "running",
        "failed_stage": None,
        "configuration": snapshot_software_configuration(),
        "dataset": {
            "data_root_env": DATA_ROOT_ENV,
            "ohrc_product_id": PAIR_01_OHRC_ID,
            "lroc_product_id": PAIR_01_LROC_ID,
            "ohrc_source_name": ohrc_source_name,
            "lroc_source_name": lroc_source_name,
            "footprint_source": FOOTPRINT_SOURCE,
            "footprint_provenance": (
                "data/manifests/demo_pairs.yaml declares footprint_source="
                f"{FOOTPRINT_SOURCE} for {PAIR_MANIFEST_ID}; ingest does not "
                "recompute footprints"
            ),
        },
        "stages": {},
        "warnings": [],
        "safety_limit_events": [],
        "runtime_seconds": {},
        "memory": {},
        "reproducibility": _reproducibility(),
    }
    return out, export_dir, lightweight, record


def _write_start_failure(
    *,
    output_dir: Path | None,
    record_path: Path | None,
    root: Path,
    ohrc_path: Path | None,
    lroc_path: Path | None,
) -> None:
    """Record that ingest could not start. Does not invent match or accuracy numbers."""

    lightweight = record_path or (
        _REPO_ROOT / "experiments" / EXPERIMENT_ID / "results" / f"{PAIR_MANIFEST_ID}.json"
    )
    lightweight.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "pair_manifest_id": PAIR_MANIFEST_ID,
        "status": "could_not_start",
        "failed_stage": "ingest_product",
        "configuration": snapshot_software_configuration(),
        "dataset": {
            "data_root_env": DATA_ROOT_ENV,
            "data_root_name": root.name,
            "ohrc_product_id": PAIR_01_OHRC_ID,
            "lroc_product_id": PAIR_01_LROC_ID,
            "ohrc_found": ohrc_path is not None,
            "lroc_found": lroc_path is not None,
            "ohrc_source_name": None if ohrc_path is None else ohrc_path.name,
            "lroc_source_name": None if lroc_path is None else lroc_path.name,
            "footprint_source": FOOTPRINT_SOURCE,
            "footprint_provenance": (
                "data/manifests/demo_pairs.yaml declares footprint_source="
                f"{FOOTPRINT_SOURCE} for {PAIR_MANIFEST_ID}; ingest does not "
                "recompute footprints"
            ),
        },
        "stages": {},
        "warnings": [
            "Pair-01 ingest did not start because one or both products are "
            "missing under the configured data root. No correspondences, "
            "transform, or metrics were produced. Do not substitute previously "
            "observed downstream counts as this run's result."
        ],
        "safety_limit_events": [],
        "failure": (
            f"OHRC {PAIR_01_OHRC_ID} found={ohrc_path is not None}; "
            f"LROC {PAIR_01_LROC_ID} found={lroc_path is not None}"
        ),
        "scientific_interpretation": {
            "what_succeeded": [],
            "what_did_not_succeed": [
                "ingest_product could not start; later frozen stages were not executed"
            ],
            "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
            "do_not_interpret_prior_shaiz_counts_as_this_run": True,
            "limitations": [
                "No independent lunar ground truth.",
                "This record is a start failure, not a matching or registration result.",
            ],
            "recommended_exp001": (
                "After the real pair-01 products are available under "
                f"{DATA_ROOT_ENV}, re-run EXP-000 before opening EXP-001."
            ),
        },
    }
    _write_json(lightweight, payload)
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(output_dir / "record.json", payload)


def _execute_after_ingest(
    source: LunarProduct,
    reference: LunarProduct,
    record: dict[str, Any],
    out: Path,
    export_dir: Path,
    lightweight: Path,
    wall_start: float,
) -> dict[str, Any]:
    try:
        record["failed_stage"] = "ingest_product"
        _require_lroc_mask(reference, record)
        pair = _timed(record, "characterize_pair", lambda: characterize_pair(source, reference))
        record["stages"]["characterize_pair"] = _characterization_report(pair)

        pair, preprocess_report = _timed(
            record, "preprocess", lambda: _preprocess_guarded(pair, record)
        )
        record["stages"]["preprocess"] = preprocess_report

        representation = _timed(
            record, "generate_representation", lambda: generate_representation(pair)
        )
        matching_view = _matching_view_report(representation)
        record["stages"]["generate_representation"] = matching_view

        correspondences = _timed(
            record, "match", lambda image=representation: match(pair, image)
        )
        record["stages"]["match"] = {
            "matcher_id": correspondences.matcher_id,
            "representation_id": correspondences.representation_id,
            "raw_match_count": len(correspondences.matches),
            "status_values": sorted({item.status for item in correspondences.matches}),
            "coordinates": "original_image_pixels_after_matching_view_scale",
            "coordinate_mapping": (
                "x_original = x_matching * stride; y_original = y_matching * stride"
            ),
        }
        del representation

        verified = _timed(
            record, "verify_matches", lambda: verify_matches(correspondences, pair)
        )
        inliers = [item for item in verified.matches if item.status == "inlier"]
        record["stages"]["verify_matches"] = {
            "raw_match_count": len(verified.matches),
            "verified_inlier_count": len(inliers),
            "rejected_count": sum(1 for item in verified.matches if item.status == "rejected"),
            "filtered_count": sum(1 for item in verified.matches if item.status == "filtered"),
            "inlier_ratio": (len(inliers) / len(verified.matches) if verified.matches else None),
            "inlier_residual_min": _finite_min(item.residual for item in inliers),
            "inlier_residual_max": _finite_max(item.residual for item in inliers),
            "residual_meaning": "verification_image_space_transfer_error_pixels",
        }

        control_points = _timed(
            record, "select_control_points", lambda: select_control_points(verified, pair)
        )
        record["stages"]["select_control_points"] = {
            "control_point_count": len(control_points),
            "points": [_point_dump(point) for point in control_points],
        }

        refined = _timed(record, "refine_points", lambda: refine_points(control_points, pair))
        record["stages"]["refine_points"] = _refinement_report(control_points, refined)

        registered = _timed(record, "register", lambda: register(pair, refined, verified))
        register_report = _registration_report(registered)
        if register_report["full_raster_warp_blocked"]:
            _append_safety_event(
                record,
                stage="register",
                event="registration_output_too_large",
                detail={
                    "cap_pixels": unvalidated_software_defaults().max_output_pixels,
                    "action": "full_raster_warp_blocked_diagnostic_crop_only",
                },
            )
        diagnostic = _maybe_diagnostic_crop(pair, registered, refined, out, record)
        register_report["diagnostic_crop"] = diagnostic
        record["stages"]["register"] = register_report

        evaluated = _timed(record, "evaluate", lambda: evaluate(registered, pair))
        record["stages"]["evaluate"] = _evaluation_report(evaluated, refined, registered)

        manifest = _timed(
            record, "export_result", lambda: export_result(evaluated, pair, export_dir)
        )
        record["stages"]["export_result"] = {
            "export_dir": "export",
            "files": {
                "all_matches": _basename(manifest.all_matches),
                "inliers": _basename(manifest.inliers),
                "control_points": _basename(manifest.control_points),
                "transformation": _basename(manifest.transformation),
                "metrics": _basename(manifest.metrics),
                "registration_report": _basename(manifest.registration_report),
                "registered_source": _basename(manifest.registered_source),
            },
        }
        record["status"] = "completed"
        record["scientific_interpretation"] = _interpretation(record)
        return _finalize(record, wall_start, out, lightweight)
    except Exception as exc:
        record["status"] = "failed"
        if record["failed_stage"] is None:
            record["failed_stage"] = "unrecorded"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        return _finalize(record, wall_start, out, lightweight)


def _timed(record: dict[str, Any], stage: str, fn: Callable[[], T]) -> T:
    record["failed_stage"] = stage
    before = tracemalloc.get_traced_memory()[0]
    started = time.perf_counter()
    try:
        value = fn()
    except Exception:
        record["runtime_seconds"][stage] = time.perf_counter() - started
        raise
    record["runtime_seconds"][stage] = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    record["memory"][stage] = {
        "tracemalloc_current_bytes": current,
        "tracemalloc_peak_bytes": peak,
        "tracemalloc_delta_bytes": current - before,
    }
    return value


def _product_pixels(product: LunarProduct) -> int | None:
    if product.dimensions is None:
        return None
    return int(product.dimensions.height_px) * int(product.dimensions.width_px)


def _preprocess_guarded(
    pair: RegistrationPair, record: dict[str, Any]
) -> tuple[RegistrationPair, dict[str, Any]]:
    """Call frozen preprocess only when both rasters fit the existing pixel cap.

    Frozen preprocess materialises each product as float64. Pair 01 exceeds
    the existing 16,777,216-pixel engineering cap, so EXP-000 records an
    identity passthrough instead of raising that cap or rewriting preprocess.
    Matching-view intensity stretch still runs in generate_representation.
    """

    cap = unvalidated_software_defaults().max_output_pixels
    source_pixels = _product_pixels(pair.source)
    reference_pixels = _product_pixels(pair.reference)
    oversize = (
        source_pixels is None
        or reference_pixels is None
        or source_pixels > cap
        or reference_pixels > cap
    )
    if oversize:
        warning = (
            "preprocess identity passthrough: full-raster preprocess would "
            f"materialise source_pixels={source_pixels} and "
            f"reference_pixels={reference_pixels} as float64, which exceeds "
            f"the existing {cap}-pixel engineering cap. Matching-view "
            "intensity representation still applies 2-98 percentile stretch."
        )
        record["warnings"].append(warning)
        _append_safety_event(
            record,
            stage="preprocess",
            event="full_raster_materialization_exceeds_engineering_pixel_cap",
            detail={
                "cap_pixels": cap,
                "source_pixels": source_pixels,
                "reference_pixels": reference_pixels,
                "action": "identity_passthrough",
            },
        )
        return pair, {
            "applied": "identity_passthrough",
            "reason": "full_raster_materialization_exceeds_engineering_pixel_cap",
            "cap_pixels": cap,
            "source_pixels": source_pixels,
            "reference_pixels": reference_pixels,
            "software_defaults_not_executed_on_full_rasters": snapshot_software_configuration()[
                "preprocessing"
            ],
        }
    processed = preprocess(pair)
    return processed, {
        "applied": "preprocess",
        "source_raster_name": _basename(processed.source.raster_uri),
        "reference_raster_name": _basename(processed.reference.raster_uri),
    }


def _require_lroc_mask(reference: LunarProduct, record: dict[str, Any]) -> None:
    ingest = record.setdefault("stages", {}).setdefault("ingest_product", {})
    report = ingest.setdefault("reference", {})
    if reference.mask_uri is None:
        record["warnings"].append("LROC product has no mask_uri")
        report["mask_invalid_pixel_count"] = None
        return
    mask = mmap_product_array(reference.mask_uri)
    array = np.asarray(mask, dtype=bool)
    invalid = int(array.size - np.count_nonzero(array))
    report["mask_invalid_pixel_count"] = invalid
    report["mask_pixel_count"] = int(array.size)
    if invalid == 0:
        record["warnings"].append("LROC invalid-pixel mask contains no invalid pixels")


def _product_report(product: LunarProduct) -> dict[str, Any]:
    dimensions = product.dimensions
    provenance = product.provenance
    coordinates = product.coordinates
    return {
        "product_id": product.product_id,
        "instrument": product.instrument,
        "mission": product.mission,
        "acquisition_time": product.acquisition_time.isoformat()
        if product.acquisition_time is not None
        else None,
        "gsd_meters": product.gsd_meters,
        "radiometric_state": product.radiometric_state,
        "valid_pixel_ratio": product.valid_pixel_ratio,
        "dimensions": None
        if dimensions is None
        else {
            "width_px": dimensions.width_px,
            "height_px": dimensions.height_px,
            "band_count": dimensions.band_count,
            "pixel_count": dimensions.width_px * dimensions.height_px,
        },
        "mask_uri_name": _basename(product.mask_uri),
        "raster_uri_name": _basename(product.raster_uri),
        "coordinates": None
        if coordinates is None
        else {"crs": coordinates.crs, "bbox": coordinates.bbox},
        "illumination_metadata": {
            "sun_vector": None,
            "incidence_angle_degrees": None,
            "emission_angle_degrees": None,
            "phase_angle_degrees": None,
            "sub_solar_azimuth_degrees": None,
            "populated_from_product": False,
            "reason": (
                "LunarProduct has no illumination fields. Current OHRC PDS4 and "
                "LROC PDS3 ingest readers do not extract Sun geometry. SPICE is "
                "not implemented."
            ),
        },
        "provenance": None
        if provenance is None
        else {
            "source_uri": provenance.source_uri,
            "reader": provenance.reader,
            "notes": provenance.notes,
        },
    }


def _characterization_report(pair: RegistrationPair) -> dict[str, Any]:
    char = pair.characterization
    return {
        "pair_id": pair.pair_id,
        "overlap_mask_uri": pair.overlap_mask_uri,
        "characterization": None
        if char is None
        else {
            "sensor_pair": char.sensor_pair,
            "modality": char.modality,
            "gsd_ratio": char.gsd_ratio,
            "acquisition_time_difference_seconds": char.acquisition_time_difference_seconds,
            "sun_angle_difference_degrees": char.sun_angle_difference_degrees,
            "viewing_geometry_difference": char.viewing_geometry_difference,
            "expected_overlap": char.expected_overlap,
            "valid_pixel_ratio": char.valid_pixel_ratio,
            "texture_contrast": char.texture_contrast,
            "difficulty": char.difficulty,
            "quality_flags": list(char.quality_flags),
        },
        "illumination_note": (
            "sun_angle_difference_degrees remains None: LunarProduct has no Sun "
            "vector and SPICE is not implemented"
        ),
    }


def _matching_view_report(representation: Any) -> dict[str, Any]:
    metadata = getattr(representation, "metadata", {}) or {}
    source_view = _jsonable(metadata.get("source_matching_view"))
    reference_view = _jsonable(metadata.get("reference_matching_view"))
    source_mask = metadata.get("source_valid_mask")
    reference_mask = metadata.get("reference_valid_mask")
    return {
        "representation_id": getattr(representation, "representation_id", None),
        "source_matching_view": source_view,
        "reference_matching_view": reference_view,
        "source_valid_mask_shape": None if source_mask is None else list(source_mask.shape),
        "reference_valid_mask_shape": None
        if reference_mask is None
        else list(reference_mask.shape),
        "source_valid_fraction": _mask_fraction(source_mask),
        "reference_valid_fraction": _mask_fraction(reference_mask),
        "lroc_invalid_mask_respected": bool(
            reference_mask is not None and np.any(~np.asarray(reference_mask, dtype=bool))
        ),
        "loader_note": (
            "representation load_array range-normalises integer rasters, including "
            "LROC NULL (-32768); the validity mask is still passed to SIFT"
        ),
        "coordinate_mapping": (
            "x_original = x_matching * stride; y_original = y_matching * stride"
        ),
        "spatial_window": "full_image_stride_decimation_not_a_cropped_window",
    }


def _mask_fraction(mask: Any) -> float | None:
    if mask is None:
        return None
    array = np.asarray(mask, dtype=bool)
    if array.size == 0:
        return None
    return float(np.count_nonzero(array) / array.size)


def _point_dump(point: ControlPoint) -> dict[str, Any]:
    return {
        "source_xy": list(point.source_xy),
        "reference_xy": list(point.reference_xy),
        "residual": point.residual,
        "uncertainty": point.uncertainty,
    }


def _refinement_report(
    original: list[ControlPoint], refined: list[ControlPoint]
) -> dict[str, Any]:
    changed = 0
    for before, after in zip(original, refined, strict=True):
        if before.source_xy != after.source_xy or before.reference_xy != after.reference_xy:
            changed += 1
    outcome = _refinement_outcome(changed, len(refined))
    report: dict[str, Any] = {
        "outcome": outcome,
        "input_count": len(original),
        "output_count": len(refined),
        "coordinates_changed_count": changed,
        "coordinates_unchanged_count": len(refined) - changed,
        "uncertainty_still_none": all(point.uncertainty is None for point in refined),
        "points": [_point_dump(point) for point in refined],
    }
    if outcome == REFINEMENT_OUTCOME_INDETERMINATE:
        report["limitation"] = (
            "refinement outcome = INDETERMINATE: zero coordinates changed and "
            "the frozen ControlPoint contract has no per-point outcome field, so "
            "already-optimal cannot be distinguished from no measurable "
            "improvement. This is not a successful refinement."
        )
    elif outcome == REFINEMENT_OUTCOME_COORDINATES_UPDATED:
        report["limitation"] = (
            "at least one coordinate changed; this is not independently "
            "validated sub-pixel accuracy"
        )
    else:
        report["limitation"] = None
    return report


def _refinement_outcome(changed_count: int, output_count: int) -> str:
    if output_count == 0:
        return REFINEMENT_OUTCOME_NO_POINTS
    if changed_count == 0:
        return REFINEMENT_OUTCOME_INDETERMINATE
    return REFINEMENT_OUTCOME_COORDINATES_UPDATED


def _registration_report(result: RegistrationResult) -> dict[str, Any]:
    transformation = result.transformation
    return {
        "quality_flags": list(result.quality_flags),
        "registered_source_uri": _basename(result.registered_source_uri),
        "full_raster_warp_blocked": FLAG_OUTPUT_TOO_LARGE in result.quality_flags,
        "transformation": None
        if transformation is None
        else {
            "model_name": transformation.model_name,
            "parameters": transformation.parameters,
        },
    }


def _maybe_diagnostic_crop(
    pair: RegistrationPair,
    result: RegistrationResult,
    control_points: list[ControlPoint],
    output_dir: Path,
    record: dict[str, Any],
) -> dict[str, Any]:
    transformation = result.transformation
    if transformation is None or pair.reference.dimensions is None:
        return {"produced": False, "reason": "no_fitted_transform_or_reference_dimensions"}
    if pair.source.raster_uri is None:
        return {"produced": False, "reason": "source_raster_unavailable"}
    if FLAG_OUTPUT_TOO_LARGE not in result.quality_flags and result.registered_source_uri:
        return {
            "produced": False,
            "reason": "full_raster_registration_already_written",
        }

    matrix = np.array(transformation.parameters["matrix"], dtype=float)
    window = diagnostic_crop_window(
        pair.reference.dimensions.height_px,
        pair.reference.dimensions.width_px,
        control_points,
        max_output_pixels=unvalidated_software_defaults().max_output_pixels,
        preferred_side=DIAGNOSTIC_PREFERRED_SIDE_PX,
    )
    fit_residuals = projective_fit_residuals(control_points, matrix)
    inclusion = control_point_crop_report(window, control_points)
    inclusion_fields = {
        "control_points_inside_count": inclusion["inside_count"],
        "control_points_total": inclusion["total_control_points"],
        "control_points_all_included": inclusion["all_included"],
        "control_points_inside_indices": inclusion["inside_indices"],
        "control_points_inside_reference_xy": inclusion["inside_reference_xy"],
        "control_points_not_all_included_reason": inclusion["reason"],
    }
    crop_path = output_dir / "diagnostic_registered_crop.npy"
    try:
        warped = warp_diagnostic_crop(pair.source.raster_uri, matrix, window)
        np.save(crop_path, warped)
        finite = int(np.count_nonzero(np.isfinite(warped)))
        crop_note = {
            "produced": True,
            "path_name": crop_path.name,
            "window": window.as_dict(),
            "finite_pixel_count": finite,
            "finite_pixel_fraction": float(finite / warped.size) if warped.size else None,
            "dtype": str(warped.dtype),
            "projective_fit_residuals_pixels": fit_residuals,
            "projective_fit_residual_min": min(fit_residuals) if fit_residuals else None,
            "projective_fit_residual_max": max(fit_residuals) if fit_residuals else None,
            "interpretation": (
                "Diagnostic crop only. Full-raster registration remains blocked by "
                f"the existing {unvalidated_software_defaults().max_output_pixels}-pixel "
                "cap. Fit residuals on the same control points used to estimate "
                "projective DLT are not independent accuracy. Placement maximises "
                "control-point inclusion inside the capped window."
            ),
            **inclusion_fields,
        }
        if len(control_points) == 4:
            record["warnings"].append(
                "projective DLT was fit from exactly four points; near-zero fit "
                "residuals are expected and are not registration accuracy"
            )
        if inclusion["reason"] is not None:
            record["warnings"].append(
                "diagnostic crop could not include every control point: "
                f"{inclusion['reason']}"
            )
            _append_safety_event(
                record,
                stage="register",
                event="diagnostic_crop_control_point_span_exceeds_capped_window",
                detail={
                    "reason": inclusion["reason"],
                    "inside_count": inclusion["inside_count"],
                    "total_control_points": inclusion["total_control_points"],
                    "window_pixel_count": window.height * window.width,
                    "cap_pixels": unvalidated_software_defaults().max_output_pixels,
                },
            )
        return crop_note
    except Exception as exc:
        record["warnings"].append(f"diagnostic crop failed: {type(exc).__name__}: {exc}")
        return {
            "produced": False,
            "reason": "warp_or_write_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "window": window.as_dict(),
            "projective_fit_residuals_pixels": fit_residuals,
            **inclusion_fields,
        }


def _evaluation_report(
    result: RegistrationResult,
    refined: list[ControlPoint],
    registered: RegistrationResult,
) -> dict[str, Any]:
    metrics = result.metrics
    transformation = registered.transformation
    fit_residuals: list[float] = []
    if transformation is not None:
        matrix = np.array(transformation.parameters["matrix"], dtype=float)
        fit_residuals = projective_fit_residuals(refined, matrix)
    return {
        "metrics": None if metrics is None else metrics.model_dump(mode="json"),
        "verification_rmse_is_not_independent_accuracy": True,
        "independent_ground_truth_used": False,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "independent_accuracy_note": (
            "independent accuracy = NOT VALIDATED. No independent lunar ground "
            "truth, held-out correspondences, or surveyed control exists for "
            "this pair. evaluate().rmse is the RMSE of stored verification "
            "inlier residuals and is not registration accuracy."
        ),
        "projective_dlt_fit_residuals_on_control_points_pixels": fit_residuals,
        "projective_dlt_minimum_points": 4,
        "control_points_used_for_fit": len(refined),
    }


def _interpretation(record: dict[str, Any]) -> dict[str, Any]:
    match_stage = record["stages"].get("match", {})
    verify_stage = record["stages"].get("verify_matches", {})
    register_stage = record["stages"].get("register", {})
    evaluate_stage = record["stages"].get("evaluate", {})
    refine_stage = record["stages"].get("refine_points", {})
    raw = match_stage.get("raw_match_count")
    inliers = verify_stage.get("verified_inlier_count")
    ratio = verify_stage.get("inlier_ratio")
    control_point_count = record["stages"].get("select_control_points", {}).get(
        "control_point_count"
    )
    metrics = evaluate_stage.get("metrics") or {}
    refinement_outcome = refine_stage.get("outcome")
    succeeded = [
        "ingest of declared OHRC PDS4 and LROC PDS3 products",
        "pair characterization from product metadata without inventing SPICE",
        "matching-view SIFT with coordinates restored to original image space",
        "geometric verification and spatially distributed control-point selection",
        "projective_2d_baseline transform fit from selected control points",
        "evaluation metrics from stored verification residuals",
        "export of lightweight match/control-point/transform/metric files",
    ]
    did_not_succeed: list[str] = []
    if register_stage.get("full_raster_warp_blocked"):
        did_not_succeed.append(
            "full-raster registered source is blocked by registration_output_too_large"
        )
    if refinement_outcome == REFINEMENT_OUTCOME_INDETERMINATE:
        did_not_succeed.append(
            "refinement outcome = INDETERMINATE; not a successful refinement"
        )
    elif refinement_outcome == REFINEMENT_OUTCOME_COORDINATES_UPDATED:
        succeeded.append(
            "refinement updated at least one coordinate (not independently validated)"
        )
    return {
        "what_succeeded": succeeded,
        "what_did_not_succeed": did_not_succeed,
        "what_did_not_succeed_as_full_registration": [
            item for item in did_not_succeed if "full-raster" in item
        ],
        "raw_sift_matches": raw,
        "verified_inliers": inliers,
        "inlier_ratio": ratio,
        "control_points": control_point_count,
        "spatial_coverage": metrics.get("spatial_coverage"),
        "refinement_outcome": refinement_outcome,
        "do_not_interpret_four_point_dlt_residuals_as_accuracy": control_point_count == 4,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "bottleneck": _bottleneck(record),
        "limitations": [
            "independent accuracy = NOT VALIDATED: no independent lunar ground "
            "truth or held-out correspondences.",
            "evaluate().rmse is verification inlier residual RMSE, not accuracy.",
            "Four points are the projective DLT minimum; near-zero fitting "
            "residuals are therefore not independent evidence of registration accuracy.",
            "Full-raster registration remains blocked by the 16,777,216-pixel cap.",
            "Diagnostic crop is an engineering window, not a complete registered product.",
            "sun_angle_difference_degrees is None; SPICE is not implemented.",
            "SIFT on a stride-decimated matching view is a software baseline, not D-007.",
        ],
        "recommended_exp001": _recommended_exp001(inliers),
    }


def _recommended_exp001(verified_inliers: int | None) -> str:
    base = (
        "On the same pair and matching-view policy, compare illumination-robust "
        "matchers (RIFT/RIFT2 and one dense/learned candidate) and score them "
        "with an independent held-out correspondence set. Do not treat EXP-000 "
        "inlier ratio or projective DLT fit residuals as the benchmark."
    )
    if verified_inliers == 4:
        return (
            base + " This run produced exactly four verified inliers, the projective "
            "DLT minimum, so matcher yield—not four-point fit residuals—is the "
            "measured bottleneck to address first."
        )
    return base


def _bottleneck(record: dict[str, Any]) -> list[str]:
    """Observed engineering/scientific bottlenecks. Not a redesign proposal."""

    items: list[str] = []
    verify_stage = record["stages"].get("verify_matches", {})
    refine_stage = record["stages"].get("refine_points", {})
    register_stage = record["stages"].get("register", {})
    inliers = verify_stage.get("verified_inlier_count")
    if inliers == 4:
        items.append(
            "verified inliers equal the projective DLT minimum (4); near-zero "
            "fit residuals are therefore not independent accuracy"
        )
    if refine_stage.get("outcome") == REFINEMENT_OUTCOME_INDETERMINATE:
        items.append("refinement outcome = INDETERMINATE")
    if register_stage.get("full_raster_warp_blocked"):
        items.append(
            "full-raster registration blocked by the existing 16,777,216-pixel cap"
        )
    items.append("independent accuracy = NOT VALIDATED")
    return items


def _append_safety_event(
    record: dict[str, Any], *, stage: str, event: str, detail: dict[str, Any]
) -> None:
    record.setdefault("safety_limit_events", []).append(
        {"stage": stage, "event": event, **detail}
    )


def _reproducibility() -> dict[str, Any]:
    return {
        "git_commit": _software_commit(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }


def _software_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _start_memory_trace() -> None:
    if not tracemalloc.is_tracing():
        tracemalloc.start()


def _finalize(
    record: dict[str, Any], wall_start: float, output_dir: Path, lightweight: Path
) -> dict[str, Any]:
    record["runtime_seconds"]["total"] = time.perf_counter() - wall_start
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        record["memory"]["process_tracemalloc_current_bytes"] = current
        record["memory"]["process_tracemalloc_peak_bytes"] = peak
        tracemalloc.stop()
    record["output_files"] = {
        "full_record": "record.json",
        "lightweight_record": _repo_relative(lightweight),
        "export_dir": "export",
        "diagnostic_crop": (
            record.get("stages", {}).get("register", {}).get("diagnostic_crop", {}).get("path_name")
        ),
    }
    if record["failed_stage"] and record["status"] == "completed":
        record["failed_stage"] = None
    full_path = output_dir / "record.json"
    _write_json(full_path, record)
    _write_json(lightweight, _sanitize(record))
    return record


def _sanitize(record: dict[str, Any]) -> dict[str, Any]:
    """Drop machine-specific absolute paths from the committed record."""

    payload = json.loads(json.dumps(record, default=_json_default))
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return value.name
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    return json.loads(json.dumps(value, default=_json_default))


def _basename(uri: str | None) -> str | None:
    if uri is None:
        return None
    return Path(uri).name


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return path.name


def _finite_min(values: Any) -> float | None:
    finite = [float(value) for value in values if value is not None and np.isfinite(value)]
    return min(finite) if finite else None


def _finite_max(values: Any) -> float | None:
    finite = [float(value) for value in values if value is not None and np.isfinite(value)]
    return max(finite) if finite else None
