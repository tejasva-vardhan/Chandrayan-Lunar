"""EXP-001 controlled matcher comparison.

Runs the frozen pipeline once per (pair, matcher) while holding every other
stage constant, and records the metrics needed to decide whether matcher
choice is the correspondence bottleneck.

Control strategy
----------------
``generate_representation`` is called **once per pair** and the resulting
object is handed to every matcher. The matching view, stride, coordinate
scales, and validity masks are therefore the same objects for every arm, not
merely the same configuration. Everything downstream of the matcher uses the
frozen two-argument callables, so no per-matcher threshold exists anywhere.

The preprocessing guard is imported from the EXP-000 runner rather than
reimplemented, so "same preprocessing" is a fact about the code path and not
a claim in a document.

What this module deliberately does not do
-----------------------------------------
- It does not modify any frozen interface, adapter signature, or routing.
- It does not raise or remove the 16,777,216-pixel registration cap.
- It does not write diagnostic rasters. Registration output for these pairs
  is blocked by the existing cap exactly as in EXP-000, and a matcher
  comparison does not need pictures.
- It does not call verification residuals accuracy anywhere.
"""

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
from src.io.exp001.conclusion import scientific_conclusion
from src.io.exp001.config import (
    BASELINE_EXPERIMENT_ID,
    DECISION_RULE,
    EXPERIMENT_ID,
    FOOTPRINT_SOURCE,
    HYPOTHESIS,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    PAIR_REGISTRY,
    PREREGISTERED_EXPECTATIONS,
    PRIMARY_PAIR_ID,
    REFINEMENT_OUTCOME_COORDINATES_UPDATED,
    REFINEMENT_OUTCOME_INDETERMINATE,
    REFINEMENT_OUTCOME_NO_POINTS,
    excluded_matchers,
    snapshot_fixed_configuration,
    snapshot_matcher_configuration,
)
from src.io.exp001.metrics import (
    coverage,
    inlier_ratio,
    inliers_above_model_minimum,
    occupancy,
    status_counts,
    verified_matches,
)
from src.io.exp001.validation import (
    HeldOutSettings,
    cross_matcher_checkpoints,
    held_out_validation,
)
from src.matching.portfolio import PORTFOLIO_MATCHER_IDS, run_matcher
from src.models.correspondence_set import Correspondence
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult
from src.refinement import refine_points
from src.registration import register
from src.registration.result import FLAG_OUTPUT_TOO_LARGE
from src.registration.settings import unvalidated_software_defaults as registration_defaults
from src.representation import generate_representation
from src.verification import verify_matches
from src.verification.geometric_models import get_geometric_model
from src.verification.settings import unvalidated_software_defaults as verification_defaults

_REPO_ROOT = Path(__file__).resolve().parents[3]
T = TypeVar("T")


class Exp001Error(RuntimeError):
    """Raised when EXP-001 cannot start."""


def run_exp001(
    *,
    data_root: Path | None = None,
    pair_ids: list[str] | None = None,
    matcher_ids: list[str] | None = None,
    output_dir: Path | None = None,
    record_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the controlled comparison over the requested pairs and matchers."""

    try:
        root = data_root if data_root is not None else configured_data_root()
    except DataRootError as exc:
        raise Exp001Error(str(exc)) from exc
    if root is None:
        raise Exp001Error(
            f"Set {DATA_ROOT_ENV} to the external demo dataset that contains the "
            "products declared in data/manifests/demo_pairs.yaml."
        )
    if not root.exists() or not root.is_dir():
        raise Exp001Error(f"data root is not an existing directory: {root}")

    requested_pairs = list(pair_ids or [PRIMARY_PAIR_ID])
    unknown = [item for item in requested_pairs if item not in PAIR_REGISTRY]
    if unknown:
        raise Exp001Error(f"unknown pair ids: {unknown}; known: {sorted(PAIR_REGISTRY)}")

    requested_matchers = list(matcher_ids or PORTFOLIO_MATCHER_IDS)
    unknown_matchers = [
        item for item in requested_matchers if item not in PORTFOLIO_MATCHER_IDS
    ]
    if unknown_matchers:
        raise Exp001Error(
            f"unknown matcher ids: {unknown_matchers}; known: {list(PORTFOLIO_MATCHER_IDS)}"
        )

    out = output_dir or (_REPO_ROOT / "outputs" / EXPERIMENT_ID)
    records = record_dir or (_REPO_ROOT / "experiments" / EXPERIMENT_ID / "results")
    out.mkdir(parents=True, exist_ok=True)
    records.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": HYPOTHESIS,
        "decision_rule": DECISION_RULE,
        "preregistered_expectations": PREREGISTERED_EXPECTATIONS,
        "excluded_matchers": excluded_matchers(),
        "fixed_configuration": snapshot_fixed_configuration(),
        "matcher_configuration": snapshot_matcher_configuration(),
        "matcher_ids": requested_matchers,
        "pair_ids": requested_pairs,
        "reproducibility": _reproducibility(),
        "pairs": {},
    }

    for pair_id in requested_pairs:
        record = _run_pair(pair_id, root, requested_matchers)
        _write_json(records / f"{pair_id}.json", record)
        _write_json(out / f"{pair_id}.json", record)
        summary["pairs"][pair_id] = _pair_summary(record)

    summary["comparison_rows"] = _comparison_rows(summary)
    summary["scientific_conclusion"] = scientific_conclusion(summary)
    _write_json(records / "summary.json", summary)
    _write_json(out / "summary.json", summary)
    return summary


def rebuild_summary(
    *,
    pair_ids: list[str] | None = None,
    record_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Rebuild summary.json from already-written pair records.

    Used when the comparison-table or conclusion wording changes without a
    new matcher run. Pair records are not rewritten.
    """

    records = record_dir or (_REPO_ROOT / "experiments" / EXPERIMENT_ID / "results")
    out = output_dir or (_REPO_ROOT / "outputs" / EXPERIMENT_ID)
    requested = list(pair_ids or list(PAIR_REGISTRY))
    summary: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": HYPOTHESIS,
        "decision_rule": DECISION_RULE,
        "preregistered_expectations": PREREGISTERED_EXPECTATIONS,
        "excluded_matchers": excluded_matchers(),
        "fixed_configuration": snapshot_fixed_configuration(),
        "matcher_configuration": snapshot_matcher_configuration(),
        "matcher_ids": list(PORTFOLIO_MATCHER_IDS),
        "pair_ids": requested,
        "reproducibility": None,
        "pairs": {},
    }
    for pair_id in requested:
        path = records / f"{pair_id}.json"
        if not path.is_file():
            raise Exp001Error(f"missing pair record: {path}")
        record = json.loads(path.read_text(encoding="utf-8"))
        if summary["reproducibility"] is None:
            summary["reproducibility"] = record.get("reproducibility")
        summary["pairs"][pair_id] = _pair_summary(record)
    summary["comparison_rows"] = _comparison_rows(summary)
    summary["scientific_conclusion"] = scientific_conclusion(summary)
    _write_json(records / "summary.json", summary)
    if output_dir is not None:
        out.mkdir(parents=True, exist_ok=True)
        _write_json(out / "summary.json", summary)
    return summary


def run_exp001_pair_from_products(
    pair_id: str,
    source: Any,
    reference: Any,
    *,
    matcher_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Run one pair from already-ingested products. Used by tests."""

    record = _new_record(pair_id)
    record["stages"]["ingest_product"] = {
        "source": _product_report(source),
        "reference": _product_report(reference),
        "note": "products supplied already ingested",
    }
    _execute_pair(record, source, reference, list(matcher_ids or PORTFOLIO_MATCHER_IDS))
    return record


# ---------------------------------------------------------------------------
# Per-pair execution
# ---------------------------------------------------------------------------


def _run_pair(pair_id: str, root: Path, matcher_ids: list[str]) -> dict[str, Any]:
    entry = PAIR_REGISTRY[pair_id]
    record = _new_record(pair_id)
    record["dataset"].update(
        {
            "ohrc_product_id": entry["ohrc_product_id"],
            "lroc_product_id": entry["lroc_product_id"],
        }
    )

    ohrc_path = find_product(root, entry["ohrc_product_id"])
    lroc_path = find_product(root, entry["lroc_product_id"])
    record["dataset"]["ohrc_found"] = ohrc_path is not None
    record["dataset"]["lroc_found"] = lroc_path is not None
    record["dataset"]["ohrc_source_name"] = None if ohrc_path is None else ohrc_path.name
    record["dataset"]["lroc_source_name"] = None if lroc_path is None else lroc_path.name

    if ohrc_path is None or lroc_path is None:
        record["status"] = "could_not_start"
        record["failed_stage"] = "ingest_product"
        record["failure"] = (
            f"OHRC {entry['ohrc_product_id']} found={ohrc_path is not None}; "
            f"LROC {entry['lroc_product_id']} found={lroc_path is not None}"
        )
        record["warnings"].append(
            "Pair products were not found under the configured data root. No "
            "correspondences, transform, or metrics were produced for this pair."
        )
        return record

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
        record["runtime_seconds"]["total"] = time.perf_counter() - wall_start
        return record

    _execute_pair(record, source, reference, matcher_ids)
    record["runtime_seconds"]["total"] = time.perf_counter() - wall_start
    _stop_memory_trace(record)
    return record


def _execute_pair(
    record: dict[str, Any],
    source: Any,
    reference: Any,
    matcher_ids: list[str],
) -> None:
    """Shared stages once, then one arm per matcher."""

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
        record["stages"]["generate_representation"] = _matching_view_report(representation)
    except Exception as exc:
        record["status"] = "failed"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        return

    model = get_geometric_model(verification_defaults().model_id)
    arms: dict[str, dict[str, Any]] = {}
    verified_by_matcher: dict[str, list[Correspondence]] = {}
    matrix_by_matcher: dict[str, np.ndarray | None] = {}

    for matcher_id in matcher_ids:
        arm, verified, matrix = _run_matcher_arm(
            matcher_id, pair, representation, model, record
        )
        arms[matcher_id] = arm
        verified_by_matcher[matcher_id] = verified
        matrix_by_matcher[matcher_id] = matrix

    del representation

    for matcher_id in matcher_ids:
        checkpoints: list[Correspondence] = []
        contributors: list[str] = []
        for other_id, items in verified_by_matcher.items():
            if other_id == matcher_id or not items:
                continue
            checkpoints.extend(items)
            contributors.append(other_id)
        arms[matcher_id]["cross_matcher_validation"] = cross_matcher_checkpoints(
            matrix_by_matcher[matcher_id],
            checkpoints,
            source_matcher_id=matcher_id,
            checkpoint_matcher_ids=contributors,
        )

    record["matchers"] = arms
    record["status"] = "completed"
    record["failed_stage"] = None
    record["interpretation"] = _interpretation(record, model.min_samples)


def _run_matcher_arm(
    matcher_id: str,
    pair: RegistrationPair,
    representation: Any,
    model: Any,
    record: dict[str, Any],
) -> tuple[dict[str, Any], list[Correspondence], np.ndarray | None]:
    """One matcher through match -> verify -> select -> refine -> register -> evaluate."""

    arm: dict[str, Any] = {
        "matcher_id": matcher_id,
        "runtime_seconds": {},
        "memory": {},
    }
    try:
        correspondences = _arm_timed(
            arm,
            "match",
            lambda: run_matcher(matcher_id, pair, representation),
        )
    except Exception as exc:
        arm["status"] = "failed"
        arm["failed_stage"] = "match"
        arm["failure"] = f"{type(exc).__name__}: {exc}"
        return arm, [], None

    arm["match"] = {
        "matcher_id": correspondences.matcher_id,
        "representation_id": correspondences.representation_id,
        "raw_match_count": len(correspondences.matches),
        "coordinates": "original_image_pixels_after_matching_view_scale",
    }

    try:
        verified = _arm_timed(arm, "verify_matches", lambda: verify_matches(correspondences, pair))
        control_points = _arm_timed(
            arm, "select_control_points", lambda: select_control_points(verified, pair)
        )
        refined = _arm_timed(arm, "refine_points", lambda: refine_points(control_points, pair))
        registered = _arm_timed(arm, "register", lambda: register(pair, refined, verified))
        evaluated = _arm_timed(arm, "evaluate", lambda: evaluate(registered, pair))
    except Exception as exc:
        arm["status"] = "failed"
        arm["failed_stage"] = arm.get("_stage", "unrecorded")
        arm["failure"] = f"{type(exc).__name__}: {exc}"
        return arm, [], None

    inliers = verified_matches(list(verified.matches))
    grid_bins = control_point_defaults().grid_bins

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
    }
    arm["spatial_distribution"] = {
        "verified_match_coverage": coverage(inliers, pair),
        "verified_match_occupancy": occupancy(inliers, pair, grid_bins),
        "control_point_coverage_note": (
            "control-point coverage is reported by the frozen evaluate() stage "
            "under 'evaluate.metrics.spatial_coverage'"
        ),
    }
    arm["select_control_points"] = {
        "control_point_count": len(control_points),
        "selection_succeeded": len(control_points) >= model.min_samples,
        "points": [_point_dump(point) for point in control_points],
    }
    arm["refine_points"] = _refinement_report(control_points, refined)
    arm["register"] = _registration_report(registered, model.min_samples, len(refined))
    arm["evaluate"] = _evaluation_report(evaluated)

    arm["held_out_validation"] = held_out_validation(
        inliers,
        model_id=verification_defaults().model_id,
        settings=HeldOutSettings(folds=5, rng_seed=verification_defaults().rng_seed),
    )
    arm["status"] = "completed"
    arm["failed_stage"] = None
    arm.pop("_stage", None)

    matrix = _transform_matrix(registered)
    _accumulate_pair_runtime(record, arm)
    return arm, inliers, matrix


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _transform_matrix(result: RegistrationResult) -> np.ndarray | None:
    transformation = result.transformation
    if transformation is None:
        return None
    matrix = transformation.parameters.get("matrix")
    if matrix is None:
        return None
    return np.array(matrix, dtype=float)


def _registration_report(
    result: RegistrationResult, min_samples: int, fit_point_count: int
) -> dict[str, Any]:
    transformation = result.transformation
    report: dict[str, Any] = {
        "quality_flags": list(result.quality_flags),
        "transform_fitted": transformation is not None,
        "full_raster_warp_blocked": FLAG_OUTPUT_TOO_LARGE in result.quality_flags,
        "max_output_pixels": registration_defaults().max_output_pixels,
        "registered_source_uri": None
        if result.registered_source_uri is None
        else Path(result.registered_source_uri).name,
        "model_name": None if transformation is None else transformation.model_name,
        "control_points_used_for_fit": fit_point_count,
    }
    if transformation is not None and fit_point_count == min_samples:
        report["minimal_sample_fit"] = True
        report["minimal_sample_warning"] = (
            f"the transform was fitted from exactly {min_samples} points, the "
            "projective DLT minimum, so its fit residuals are an algebraic "
            "identity and carry no information about registration accuracy"
        )
    else:
        report["minimal_sample_fit"] = False
    return report


def _evaluation_report(result: RegistrationResult) -> dict[str, Any]:
    metrics = result.metrics
    return {
        "metrics": None if metrics is None else metrics.model_dump(mode="json"),
        "rmse_meaning": (
            "RMSE of stored verification inlier residuals on the points used "
            "to fit the transform; this is a fit diagnostic, not accuracy"
        ),
        "independent_ground_truth_used": False,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
    }


def _refinement_report(
    original: list[ControlPoint], refined: list[ControlPoint]
) -> dict[str, Any]:
    changed = 0
    for before, after in zip(original, refined, strict=True):
        if before.source_xy != after.source_xy or before.reference_xy != after.reference_xy:
            changed += 1
    if not refined:
        outcome = REFINEMENT_OUTCOME_NO_POINTS
    elif changed == 0:
        outcome = REFINEMENT_OUTCOME_INDETERMINATE
    else:
        outcome = REFINEMENT_OUTCOME_COORDINATES_UPDATED
    return {
        "outcome": outcome,
        "input_count": len(original),
        "output_count": len(refined),
        "coordinates_changed_count": changed,
        "limitation": (
            "INDETERMINATE means zero coordinates changed; the frozen "
            "ControlPoint contract has no per-point outcome field, so "
            "already-optimal cannot be distinguished from no measurable "
            "improvement. This is not a successful refinement."
        )
        if outcome == REFINEMENT_OUTCOME_INDETERMINATE
        else None,
    }


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
    }


def _matching_view_report(representation: Any) -> dict[str, Any]:
    metadata = getattr(representation, "metadata", {}) or {}
    return {
        "representation_id": getattr(representation, "representation_id", None),
        "source_matching_view": _jsonable(metadata.get("source_matching_view")),
        "reference_matching_view": _jsonable(metadata.get("reference_matching_view")),
        "shared_across_matchers": True,
        "coordinate_mapping": (
            "x_original = x_matching * stride; y_original = y_matching * stride"
        ),
        "spatial_window": "full_image_stride_decimation_not_a_cropped_window",
    }


def _product_report(product: Any) -> dict[str, Any]:
    dimensions = getattr(product, "dimensions", None)
    return {
        "product_id": product.product_id,
        "instrument": product.instrument,
        "mission": product.mission,
        "gsd_meters": getattr(product, "gsd_meters", None),
        "valid_pixel_ratio": getattr(product, "valid_pixel_ratio", None),
        "dimensions": None
        if dimensions is None
        else {
            "width_px": dimensions.width_px,
            "height_px": dimensions.height_px,
            "pixel_count": dimensions.width_px * dimensions.height_px,
        },
    }


def _point_dump(point: ControlPoint) -> dict[str, Any]:
    return {
        "source_xy": list(point.source_xy),
        "reference_xy": list(point.reference_xy),
        "residual": point.residual,
    }


def _interpretation(record: dict[str, Any], min_samples: int) -> dict[str, Any]:
    arms = record.get("matchers", {})
    yields = {
        matcher_id: arm.get("verify_matches", {}).get("verified_inlier_count")
        for matcher_id, arm in arms.items()
    }
    above = {
        matcher_id: arm.get("verify_matches", {}).get("exceeds_model_minimum")
        for matcher_id, arm in arms.items()
    }
    scored = {
        matcher_id: count for matcher_id, count in yields.items() if count is not None
    }
    if scored:
        best_count = max(scored.values())
        leaders = sorted(mid for mid, count in scored.items() if count == best_count)
    else:
        best_count = None
        leaders = []
    any_above = any(bool(value) for value in above.values())

    return {
        "verified_inliers_by_matcher": yields,
        "exceeds_model_minimum_by_matcher": above,
        # A tie is reported as a tie. Naming one winner out of a tie at the
        # model minimum would read as a finding where there is none.
        "highest_verified_yield_matchers": leaders,
        "highest_verified_yield_count": best_count,
        "highest_verified_yield_is_tied": len(leaders) > 1,
        "highest_verified_yield_matcher": leaders[0] if len(leaders) == 1 else None,
        "any_matcher_exceeds_model_minimum": any_above,
        "model_min_samples": min_samples,
        "decision_rule": DECISION_RULE,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "single_pair_caveat": (
            "one pair cannot establish a globally superior matcher; these "
            "counts are evidence about this pair only"
        ),
    }


def _pair_summary(record: dict[str, Any]) -> dict[str, Any]:
    arms = record.get("matchers", {})
    return {
        "status": record.get("status"),
        "failed_stage": record.get("failed_stage"),
        "failure": record.get("failure"),
        "matchers": {
            matcher_id: {
                "status": arm.get("status"),
                "raw": arm.get("match", {}).get("raw_match_count"),
                "verified": arm.get("verify_matches", {}).get("verified_inlier_count"),
                "rejected": arm.get("verify_matches", {}).get("rejected_count"),
                "inlier_ratio": arm.get("verify_matches", {}).get("inlier_ratio"),
                "exceeds_model_minimum": arm.get("verify_matches", {}).get(
                    "exceeds_model_minimum"
                ),
                "verified_match_coverage": arm.get("spatial_distribution", {}).get(
                    "verified_match_coverage"
                ),
                "control_point_coverage": (
                    (arm.get("evaluate", {}).get("metrics") or {}).get("spatial_coverage")
                ),
                "control_points": arm.get("select_control_points", {}).get(
                    "control_point_count"
                ),
                "transform_fitted": arm.get("register", {}).get("transform_fitted"),
                "refinement_outcome": arm.get("refine_points", {}).get("outcome"),
                "registration_status": (
                    "blocked_by_pixel_cap"
                    if arm.get("register", {}).get("full_raster_warp_blocked")
                    else arm.get("register", {}).get("registered_source_uri")
                ),
                "held_out_status": arm.get("held_out_validation", {}).get("status"),
                "held_out_rmse_pixels": (
                    (arm.get("held_out_validation", {}) or {}).get(
                        "held_out_transfer_error_pixels"
                    )
                    or {}
                ).get("rmse"),
                "cross_matcher_status": arm.get("cross_matcher_validation", {}).get("status"),
                "runtime_seconds": arm.get("runtime_seconds", {}),
                "memory": arm.get("memory", {}),
            }
            for matcher_id, arm in arms.items()
        },
        "interpretation": record.get("interpretation"),
    }


def _comparison_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [_exp000_reference_row()]
    for pair_id, pair_summary in summary["pairs"].items():
        arms = pair_summary.get("matchers", {})
        ordered = [matcher_id for matcher_id in PORTFOLIO_MATCHER_IDS if matcher_id in arms]
        ordered.extend(matcher_id for matcher_id in arms if matcher_id not in ordered)
        for matcher_id in ordered:
            arm = arms[matcher_id]
            memory = (arm.get("memory") or {}).get("match") or {}
            rows.append(
                {
                    "role": "exp001",
                    "experiment_id": EXPERIMENT_ID,
                    "matcher": matcher_id,
                    "pair": pair_id,
                    "raw": arm.get("raw"),
                    "verified": arm.get("verified"),
                    "inlier_ratio": arm.get("inlier_ratio"),
                    "verified_match_coverage": arm.get("verified_match_coverage"),
                    "control_point_coverage": arm.get("control_point_coverage"),
                    "control_points": arm.get("control_points"),
                    "transform_fitted": arm.get("transform_fitted"),
                    "refinement": arm.get("refinement_outcome"),
                    "registration": arm.get("registration_status"),
                    "runtime_seconds_match": arm.get("runtime_seconds", {}).get("match"),
                    "match_rss_bytes": memory.get("process_rss_bytes"),
                    "validation": arm.get("held_out_status"),
                    "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
                }
            )
    return rows


def _exp000_reference_row() -> dict[str, Any]:
    """Preserve the committed EXP-000 SIFT row as the comparison reference."""

    path = (
        _REPO_ROOT
        / "experiments"
        / BASELINE_EXPERIMENT_ID
        / "results"
        / f"{PRIMARY_PAIR_ID}.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    science = payload["scientific_interpretation"]
    stages = payload["stages"]
    return {
        "role": "EXP-000_baseline_reference",
        "experiment_id": BASELINE_EXPERIMENT_ID,
        "matcher": "sift",
        "pair": PRIMARY_PAIR_ID,
        "raw": science["raw_sift_matches"],
        "verified": science["verified_inliers"],
        "inlier_ratio": science["inlier_ratio"],
        "verified_match_coverage": science["spatial_coverage"],
        "control_point_coverage": science["spatial_coverage"],
        "control_points": science["control_points"],
        "transform_fitted": True,
        "refinement": science["refinement_outcome"],
        "registration": "blocked_by_pixel_cap",
        "runtime_seconds_match": payload["runtime_seconds"]["match"],
        "match_rss_bytes": payload.get("memory", {}).get("match", {}).get(
            "tracemalloc_current_bytes"
        ),
        "validation": stages["evaluate"]["independent_accuracy"],
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
    }


# ---------------------------------------------------------------------------
# Instrumentation
# ---------------------------------------------------------------------------


def _new_record(pair_id: str) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "pair_manifest_id": pair_id,
        "status": "running",
        "failed_stage": None,
        "hypothesis": HYPOTHESIS,
        "fixed_configuration": snapshot_fixed_configuration(),
        "matcher_configuration": snapshot_matcher_configuration(),
        "dataset": {
            "data_root_env": DATA_ROOT_ENV,
            "footprint_source": FOOTPRINT_SOURCE,
        },
        "stages": {},
        "matchers": {},
        "warnings": [],
        "safety_limit_events": [],
        "runtime_seconds": {},
        "memory": {},
        "reproducibility": _reproducibility(),
    }


def _timed(record: dict[str, Any], stage: str, fn: Callable[[], T]) -> T:
    record["failed_stage"] = stage
    started = time.perf_counter()
    before = _memory_snapshot()
    try:
        value = fn()
    except Exception:
        record["runtime_seconds"][stage] = time.perf_counter() - started
        raise
    record["runtime_seconds"][stage] = time.perf_counter() - started
    record["memory"][stage] = _memory_delta(before)
    return value


def _arm_timed(arm: dict[str, Any], stage: str, fn: Callable[[], T]) -> T:
    arm["_stage"] = stage
    started = time.perf_counter()
    before = _memory_snapshot()
    try:
        value = fn()
    except Exception:
        arm["runtime_seconds"][stage] = time.perf_counter() - started
        raise
    arm["runtime_seconds"][stage] = time.perf_counter() - started
    arm["memory"][stage] = _memory_delta(before)
    return value


def _accumulate_pair_runtime(record: dict[str, Any], arm: dict[str, Any]) -> None:
    total = sum(float(value) for value in arm["runtime_seconds"].values())
    arm["runtime_seconds"]["arm_total"] = total
    record["runtime_seconds"].setdefault("matcher_arms", {})[arm["matcher_id"]] = total


def _memory_snapshot() -> dict[str, int | None]:
    """Process RSS plus tracemalloc.

    Process RSS is the primary figure because tracemalloc only sees Python
    allocations. OpenCV's SIFT and ORB allocate in C++, so a tracemalloc-only
    comparison would systematically understate them relative to RIFT's numpy
    work and would not be a fair measurement.
    """

    rss = _process_rss_bytes()
    traced = None
    if tracemalloc.is_tracing():
        traced = tracemalloc.get_traced_memory()[0]
        # Without this the recorded peak is a process-wide high-water mark and
        # every stage after the largest one inherits its number.
        tracemalloc.reset_peak()
    return {"rss_bytes": rss, "tracemalloc_bytes": traced}


def _memory_delta(before: dict[str, int | None]) -> dict[str, Any]:
    after_rss = _process_rss_bytes()
    payload: dict[str, Any] = {
        "process_rss_bytes": after_rss,
        "process_rss_delta_bytes": (
            None
            if after_rss is None or before["rss_bytes"] is None
            else after_rss - before["rss_bytes"]
        ),
        "memory_source": "psutil_process_rss" if after_rss is not None else "tracemalloc_only",
        "memory_source_note": (
            "process RSS is the primary figure; tracemalloc sees only Python "
            "allocations and would understate OpenCV's C++ allocations"
        ),
    }
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        payload["tracemalloc_current_bytes"] = current
        payload["tracemalloc_stage_peak_bytes"] = peak
    return payload


def _process_rss_bytes() -> int | None:
    try:
        import psutil
    except ImportError:
        return None
    try:
        return int(psutil.Process().memory_info().rss)
    except Exception:
        return None


def _start_memory_trace() -> None:
    if not tracemalloc.is_tracing():
        tracemalloc.start()


def _stop_memory_trace(record: dict[str, Any]) -> None:
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        record["memory"]["process_tracemalloc_current_bytes"] = current
        record["memory"]["process_tracemalloc_peak_bytes"] = peak
        tracemalloc.stop()
    record["memory"]["process_rss_bytes"] = _process_rss_bytes()


def _reproducibility() -> dict[str, Any]:
    return {
        "git_commit": _software_commit(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "opencv_version": _opencv_version(),
    }


def _opencv_version() -> str | None:
    try:
        import cv2
    except ImportError:
        return None
    return str(cv2.__version__)


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
    return completed.stdout.strip() or None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n"
    )


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


def _finite_min(values: Any) -> float | None:
    finite = [float(v) for v in values if v is not None and np.isfinite(v)]
    return min(finite) if finite else None


def _finite_max(values: Any) -> float | None:
    finite = [float(v) for v in values if v is not None and np.isfinite(v)]
    return max(finite) if finite else None


__all__ = ["Exp001Error", "rebuild_summary", "run_exp001", "run_exp001_pair_from_products"]
