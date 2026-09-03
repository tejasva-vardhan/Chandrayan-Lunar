"""A/B runner: frozen SIFT vs coarse-to-fine tiled multi-scale SIFT."""

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
from src.io.exp001.config import PAIR_REGISTRY
from src.io.exp001.metrics import (
    inlier_ratio,
    inliers_above_model_minimum,
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
    _refinement_report,
    _registration_report,
    _reproducibility,
    _start_memory_trace,
    _stop_memory_trace,
    _timed,
    _transform_status,
    _write_json,
)
from src.io.exp005.diagnostics import unselected_verified_checkpoints
from src.io.exp006.spatial import (
    repeat_stability,
    residual_distribution,
    spatial_distribution_report,
)
from src.io.ps_correspondence.config import (
    BASELINE_EXPERIMENT_ID,
    DECISION_RULE,
    DECISION_SUPPORTED,
    EXPECTED_PAIR_01_STRIDES,
    EXPECTED_PAIR_02_STRIDES,
    FOLLOW_UP_PAIR_ID,
    FOOTPRINT_SOURCE,
    HYPOTHESIS,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    PRIMARY_PAIR_ID,
    PROTOCOL_COARSE_TO_FINE,
    PROTOCOL_SINGLE_VIEW,
    RECORD_ID,
    RUNTIME_FACTOR_LIMIT,
    SIFT_BASELINE_EXPERIMENT_ID,
    VARIANT_A_ID,
    VARIANT_B_ID,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
)
from src.io.ps_correspondence.decision import apply_decision_rule
from src.matching import match
from src.matching.coarse_to_fine import MATCHER_ID as COARSE_TO_FINE_ID
from src.matching.coarse_to_fine import run_coarse_to_fine_sift
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationResult
from src.refinement import refine_points
from src.registration import register
from src.representation import generate_representation
from src.verification import verify_matches
from src.verification.geometric_models import get_geometric_model
from src.verification.settings import unvalidated_software_defaults as verification_defaults

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VARIANT_ORDER = (VARIANT_A_ID, VARIANT_B_ID)
_HELD_OUT = HeldOutSettings(folds=5, rng_seed=0)
_GEOMETRY_POINT_CAP = 80


class PsCorrespondenceError(RuntimeError):
    """Raised when the PS-closing correspondence run cannot start."""


def run_ps_correspondence(
    *,
    data_root: Path | None = None,
    pair_ids: list[str] | None = None,
    output_dir: Path | None = None,
    record_dir: Path | None = None,
    follow_up_if_supported: bool = True,
) -> dict[str, Any]:
    try:
        root = data_root if data_root is not None else configured_data_root()
    except DataRootError as exc:
        raise PsCorrespondenceError(str(exc)) from exc
    if root is None:
        raise PsCorrespondenceError(
            f"Set {DATA_ROOT_ENV} to the external demo dataset that contains "
            "the products declared in data/manifests/demo_pairs.yaml."
        )
    if not root.exists() or not root.is_dir():
        raise PsCorrespondenceError(f"data root is not an existing directory: {root}")

    requested = list(pair_ids or [PRIMARY_PAIR_ID])
    unknown = [item for item in requested if item not in PAIR_REGISTRY]
    if unknown:
        raise PsCorrespondenceError(
            f"unknown pair ids: {unknown}; known: {sorted(PAIR_REGISTRY)}"
        )

    out = output_dir or (_REPO_ROOT / "outputs" / RECORD_ID)
    records = record_dir or (_REPO_ROOT / "experiments" / RECORD_ID / "results")
    out.mkdir(parents=True, exist_ok=True)
    records.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "record_id": RECORD_ID,
        "hypothesis": HYPOTHESIS,
        "decision_rule": DECISION_RULE,
        "inherited_from": BASELINE_EXPERIMENT_ID,
        "sift_baseline_experiment_id": SIFT_BASELINE_EXPERIMENT_ID,
        "fixed_configuration": snapshot_fixed_configuration(),
        "variant_configuration": snapshot_variant_configuration(),
        "pair_ids": list(requested),
        "pairs": {},
        "reproducibility": _reproducibility(),
    }

    pending = list(requested)
    seen: set[str] = set()
    while pending:
        pair_id = pending.pop(0)
        if pair_id in seen:
            continue
        seen.add(pair_id)
        record = _run_declared_pair(pair_id, root, out / pair_id, records / f"{pair_id}.json")
        summary["pairs"][pair_id] = _pair_summary(record)
        if (
            pair_id == PRIMARY_PAIR_ID
            and follow_up_if_supported
            and FOLLOW_UP_PAIR_ID not in seen
            and (record.get("interpretation") or {}).get("decision") == DECISION_SUPPORTED
        ):
            pending.append(FOLLOW_UP_PAIR_ID)
            if FOLLOW_UP_PAIR_ID not in requested:
                requested.append(FOLLOW_UP_PAIR_ID)
            summary["pair_ids"] = list(requested)
            summary["follow_up_reason"] = (
                "primary pair H1 was SUPPORTED; running the same A/B on "
                f"{FOLLOW_UP_PAIR_ID}"
            )

    summary["primary_decision"] = (summary["pairs"].get(PRIMARY_PAIR_ID) or {}).get(
        "decision"
    )
    summary["follow_up_ran"] = FOLLOW_UP_PAIR_ID in summary["pairs"]
    _write_json(records / "summary.json", summary)
    _write_json(out / "summary.json", summary)
    return summary


def run_ps_correspondence_from_products(
    source: LunarProduct,
    reference: LunarProduct,
    *,
    pair_manifest_id: str = PRIMARY_PAIR_ID,
    output_dir: Path | None = None,
    record_path: Path | None = None,
) -> dict[str, Any]:
    out = output_dir or (_REPO_ROOT / "outputs" / RECORD_ID / "synthetic")
    lightweight = record_path or (out / f"{pair_manifest_id}.json")
    out.mkdir(parents=True, exist_ok=True)
    lightweight.parent.mkdir(parents=True, exist_ok=True)
    record = _new_record(pair_manifest_id)
    record["stages"]["ingest_product"] = {
        "source": _product_report(source),
        "reference": _product_report(reference),
        "note": "products supplied already ingested",
    }
    _start_memory_trace()
    wall_start = time.perf_counter()
    _execute_pair(record, source, reference)
    return _finalize(record, wall_start, out, lightweight)


def _run_declared_pair(
    pair_id: str, root: Path, output_dir: Path, record_path: Path
) -> dict[str, Any]:
    entry = PAIR_REGISTRY[pair_id]
    ohrc_path = find_product(root, entry["ohrc_product_id"])
    lroc_path = find_product(root, entry["lroc_product_id"])
    if ohrc_path is None or lroc_path is None:
        raise PsCorrespondenceError(
            "ingest_product cannot start: products were not found "
            f"under {DATA_ROOT_ENV}={root}. pair={pair_id} "
            f"OHRC {entry['ohrc_product_id']}: {ohrc_path}; "
            f"LROC {entry['lroc_product_id']}: {lroc_path}."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record = _new_record(pair_id)
    record["dataset"].update(
        {
            "ohrc_found": True,
            "lroc_found": True,
            "ohrc_product_id": entry["ohrc_product_id"],
            "lroc_product_id": entry["lroc_product_id"],
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
        return _finalize(record, wall_start, output_dir, record_path)

    _execute_pair(record, source, reference)
    return _finalize(record, wall_start, output_dir, record_path)


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
        record["stages"]["generate_representation"] = _matching_view_report(
            representation, pair
        )
    except Exception as exc:
        record["status"] = "failed"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        return

    model = get_geometric_model(verification_defaults().model_id)
    variants: dict[str, dict[str, Any]] = {}
    for variant_id in _VARIANT_ORDER:
        variants[variant_id] = _run_variant(variant_id, pair, representation, model)

    record["variants"] = variants
    record["comparison"] = _comparison(variants)
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
    representation: Any,
    model: Any,
) -> dict[str, Any]:
    protocol_id = (
        PROTOCOL_SINGLE_VIEW if variant_id == VARIANT_A_ID else PROTOCOL_COARSE_TO_FINE
    )
    diagnostics: dict[str, Any] = {}
    arm: dict[str, Any] = {
        "variant_id": variant_id,
        "protocol_id": protocol_id,
        "uses_shared_representation": True,
        "uses_frozen_match_surface": variant_id == VARIANT_A_ID,
        "runtime_seconds": {},
        "memory": {},
    }

    def _match_once() -> Any:
        if variant_id == VARIANT_A_ID:
            return match(pair, representation)
        return run_coarse_to_fine_sift(pair, representation, diagnostics=diagnostics)

    try:
        correspondences = _arm_timed(arm, "match", _match_once)
        repeat = _arm_timed(arm, "match_repeat", _match_once)
        verified = _arm_timed(
            arm,
            "verify_matches",
            lambda matches=correspondences: verify_matches(matches, pair),
        )
        control_points = _arm_timed(
            arm,
            "select_control_points",
            lambda items=verified: select_control_points(items, pair),
        )
        refined = _arm_timed(
            arm, "refine_points", lambda points=control_points: refine_points(points, pair)
        )
        registered = _arm_timed(
            arm,
            "register",
            lambda points=refined, matches=verified: register(pair, points, matches),
        )
        evaluated = _arm_timed(
            arm, "evaluate", lambda result=registered: evaluate(result, pair)
        )
    except Exception as exc:
        arm["status"] = "failed"
        arm["failed_stage"] = arm.get("_stage", "unrecorded")
        arm["failure"] = f"{type(exc).__name__}: {exc}"
        arm.pop("_stage", None)
        return arm

    inliers = verified_matches(list(verified.matches))
    grid_bins = control_point_defaults().grid_bins
    spatial = spatial_distribution_report(inliers, pair, grid_bins)
    arm["matcher_id"] = correspondences.matcher_id
    arm["match"] = {
        "matcher_id": correspondences.matcher_id,
        "protocol_id": protocol_id,
        "representation_id": correspondences.representation_id,
        "raw_match_count": len(correspondences.matches),
        "coordinates": "original_image_pixels_after_matching_view_scale",
        "repeat_stability": repeat_stability(
            list(correspondences.matches), list(repeat.matches)
        ),
        "coarse_to_fine_diagnostics": dict(diagnostics) if diagnostics else None,
    }
    arm["verify_matches"] = {
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
        "residual_distribution": residual_distribution(inliers),
    }
    arm["spatial_distribution"] = spatial
    arm["geometry_inspection"] = _geometry_inspection(inliers, spatial)
    arm["select_control_points"] = {
        "control_point_count": len(control_points),
        "selection_succeeded": len(control_points) >= model.min_samples,
        "points": [_point_dump(point) for point in control_points],
    }
    arm["refine_points"] = _refinement_report(control_points, refined)
    arm["register"] = _registration_report(registered, model.min_samples, len(refined))
    arm["evaluate"] = _evaluation_report(evaluated)
    arm["matcher_held_out_validation"] = held_out_validation(
        inliers,
        model_id=verification_defaults().model_id,
        settings=_HELD_OUT,
    )
    arm["unselected_verified_checkpoints"] = unselected_verified_checkpoints(
        _transform_matrix(registered), inliers, control_points
    )
    arm["status"] = "completed"
    arm["failed_stage"] = None
    arm.pop("_stage", None)
    arm["runtime_seconds"]["variant_total"] = sum(
        float(value) for value in arm["runtime_seconds"].values()
    )
    return arm


def _geometry_inspection(inliers: list[Any], spatial: dict[str, Any]) -> dict[str, Any]:
    source = spatial.get("source") or {}
    points = [
        {
            "source_xy": [float(item.source_xy[0]), float(item.source_xy[1])],
            "reference_xy": [float(item.reference_xy[0]), float(item.reference_xy[1])],
            "residual": None if item.residual is None else float(item.residual),
        }
        for item in inliers[:_GEOMETRY_POINT_CAP]
    ]
    return {
        "verified_inlier_count": len(inliers),
        "points_recorded": len(points),
        "points_truncated": len(inliers) > _GEOMETRY_POINT_CAP,
        "inliers": points,
        "source_occupied_rows": source.get("occupied_rows"),
        "source_occupied_cols": source.get("occupied_cols"),
        "source_cell_counts_row_major": source.get("cell_counts_row_major"),
        "note": (
            "coordinates are original-image pixels; occupancy is the full-image "
            "8x8 grid, not the inlier bounding box"
        ),
    }


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


def _comparison(variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for variant_id in _VARIANT_ORDER:
        arm = variants.get(variant_id) or {}
        spatial = arm.get("spatial_distribution") or {}
        source = spatial.get("source") or {}
        occupancy = spatial.get("verified_match_occupancy") or {}
        verify = arm.get("verify_matches") or {}
        register = arm.get("register") or {}
        residuals = verify.get("residual_distribution") or {}
        held = arm.get("matcher_held_out_validation") or {}
        match_stage = arm.get("match") or {}
        rows.append(
            {
                "variant": variant_id,
                "protocol_id": arm.get("protocol_id"),
                "matcher_id": arm.get("matcher_id"),
                "raw_matches": match_stage.get("raw_match_count"),
                "verified_inliers": verify.get("verified_inlier_count"),
                "inlier_ratio": verify.get("inlier_ratio"),
                "source_occupied_cells": occupancy.get("source_occupied_cells"),
                "reference_occupied_cells": occupancy.get("reference_occupied_cells"),
                "source_max_matches_per_cell": source.get("max_matches_per_cell"),
                "source_concentration": source.get("concentration"),
                "verified_match_coverage": spatial.get("verified_match_coverage"),
                "control_point_count": (arm.get("select_control_points") or {}).get(
                    "control_point_count"
                ),
                "transform_status": _transform_status(register),
                "transform_fitted": register.get("transform_fitted"),
                "residual_rmse": residuals.get("rmse"),
                "residual_median": residuals.get("median"),
                "residual_max": residuals.get("max"),
                "held_out_rmse": _rmse(held),
                "match_runtime_seconds": (arm.get("runtime_seconds") or {}).get("match"),
                "variant_runtime_seconds": (arm.get("runtime_seconds") or {}).get(
                    "variant_total"
                ),
                "match_rss_delta_bytes": ((arm.get("memory") or {}).get("match") or {}).get(
                    "process_rss_delta_bytes"
                ),
                "deterministic": (match_stage.get("repeat_stability") or {}).get(
                    "deterministic"
                ),
            }
        )
    geometry = _spatial_delta(variants)
    return {"rows": rows, "spatial_delta": geometry}


def _spatial_delta(variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    a = (variants.get(VARIANT_A_ID) or {}).get("spatial_distribution") or {}
    b = (variants.get(VARIANT_B_ID) or {}).get("spatial_distribution") or {}
    a_src = ((a.get("source") or {}).get("cell_counts_row_major")) or []
    b_src = ((b.get("source") or {}).get("cell_counts_row_major")) or []
    a_cells = {index for index, count in enumerate(a_src) if count}
    b_cells = {index for index, count in enumerate(b_src) if count}
    return {
        "source_cells_gained": sorted(b_cells - a_cells),
        "source_cells_lost": sorted(a_cells - b_cells),
        "source_cells_shared": sorted(a_cells & b_cells),
    }


def _interpretation(
    record: dict[str, Any], variants: dict[str, dict[str, Any]], min_samples: int
) -> dict[str, Any]:
    a = variants.get(VARIANT_A_ID) or {}
    b = variants.get(VARIANT_B_ID) or {}
    independent_variable_applied = bool(
        a.get("protocol_id") == PROTOCOL_SINGLE_VIEW
        and b.get("protocol_id") == PROTOCOL_COARSE_TO_FINE
        and a.get("uses_frozen_match_surface")
        and a.get("uses_shared_representation")
        and b.get("uses_shared_representation")
        and a.get("matcher_id") == "sift"
        and b.get("matcher_id") == COARSE_TO_FINE_ID
    )
    decision = apply_decision_rule(
        independent_variable_applied=independent_variable_applied,
        verified_inliers_a=_verified(a),
        verified_inliers_b=_verified(b),
        source_occupied_a=_occupied(a, "source"),
        source_occupied_b=_occupied(b, "source"),
        reference_occupied_a=_occupied(a, "reference"),
        reference_occupied_b=_occupied(b, "reference"),
        transform_fitted_a=(a.get("register") or {}).get("transform_fitted"),
        transform_fitted_b=(b.get("register") or {}).get("transform_fitted"),
        min_samples=min_samples,
        match_runtime_a=(a.get("runtime_seconds") or {}).get("match"),
        match_runtime_b=(b.get("runtime_seconds") or {}).get("match"),
        runtime_factor_limit=RUNTIME_FACTOR_LIMIT,
    )
    shared_view = record.get("stages", {}).get("generate_representation") or {}
    pair_id = record.get("pair_manifest_id")
    expected = (
        EXPECTED_PAIR_02_STRIDES
        if pair_id == PRIMARY_PAIR_ID
        else EXPECTED_PAIR_01_STRIDES
        if pair_id == FOLLOW_UP_PAIR_ID
        else None
    )
    decision.update(
        {
            "model_min_samples": min_samples,
            "expected_strides": expected,
            "observed_strides": {
                "ohrc": (shared_view.get("source_matching_view") or {}).get("stride"),
                "lroc": (shared_view.get("reference_matching_view") or {}).get("stride"),
            },
            "independent_validation_status": INDEPENDENT_ACCURACY_NOT_VALIDATED,
            "limitations": [
                "Independent accuracy is NOT VALIDATED.",
                "Matcher-derived held-out points are not ground truth.",
                "Raw match count is not a success criterion.",
                "Inlier ratio is reported, not gated.",
                "Occupied-cell ratio is an engineering diagnostic, not a frozen "
                "SIH uniformity score.",
                "Overlap is not recomputed from the products.",
                "Full-raster registration remains blocked by the 16,777,216-pixel cap.",
                "If H1 is not supported, parameters are not retuned.",
            ],
        }
    )
    return decision


def _verified(arm: dict[str, Any]) -> int | None:
    value = (arm.get("verify_matches") or {}).get("verified_inlier_count")
    return None if value is None else int(value)


def _occupied(arm: dict[str, Any], role: str) -> int | None:
    occupancy = (arm.get("spatial_distribution") or {}).get("verified_match_occupancy") or {}
    value = occupancy.get(f"{role}_occupied_cells")
    return None if value is None else int(value)


def _rmse(payload: dict[str, Any]) -> float | None:
    summary = payload.get("held_out_transfer_error_pixels")
    if not isinstance(summary, dict):
        return None
    value = summary.get("rmse")
    if value is None:
        return None
    return float(value)


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
    }


def _pair_summary(record: dict[str, Any]) -> dict[str, Any]:
    interpretation = record.get("interpretation") or {}
    return {
        "pair_manifest_id": record.get("pair_manifest_id"),
        "status": record.get("status"),
        "decision": interpretation.get("decision"),
        "hypothesis_supported": interpretation.get("hypothesis_supported"),
        "quality_improved": interpretation.get("quality_improved"),
        "spatial_maintained_or_improved": interpretation.get(
            "spatial_maintained_or_improved"
        ),
        "transform_stable": interpretation.get("transform_stable"),
        "comparison": record.get("comparison"),
    }


def _new_record(pair_manifest_id: str) -> dict[str, Any]:
    entry = PAIR_REGISTRY.get(pair_manifest_id, {})
    return {
        "record_id": RECORD_ID,
        "pair_manifest_id": pair_manifest_id,
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
            "ohrc_product_id": entry.get("ohrc_product_id"),
            "lroc_product_id": entry.get("lroc_product_id"),
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


__all__ = [
    "PsCorrespondenceError",
    "run_ps_correspondence",
    "run_ps_correspondence_from_products",
]
