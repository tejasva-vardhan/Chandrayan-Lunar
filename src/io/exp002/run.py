"""EXP-002 matching-view scale-policy comparison.

Runs the frozen pipeline twice on pair_01_equatorial:

* Variant A — ``generate_representation(pair)``, the EXP-000 per-image
  pixel-budget matching view (OHRC stride 15, LROC stride 8).
* Variant B — the same SIFT path with the matching-view scale chosen so
  both images represent approximately the same physical ground scale.

Every other EXP-000 parameter is held constant. Diagnostic rasters are not
written. Four-point DLT residuals are not treated as accuracy.
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
from src.io.exp001.metrics import (
    coverage,
    inlier_ratio,
    inliers_above_model_minimum,
    occupancy,
    status_counts,
    verified_matches,
)
from src.io.exp002.config import (
    BASELINE_EXPERIMENT_ID,
    DECISION_RULE,
    EXPERIMENT_ID,
    FOOTPRINT_SOURCE,
    HYPOTHESIS,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    LROC_PRODUCT_ID,
    OHRC_PRODUCT_ID,
    PAIR_MANIFEST_ID,
    REFINEMENT_OUTCOME_COORDINATES_UPDATED,
    REFINEMENT_OUTCOME_INDETERMINATE,
    REFINEMENT_OUTCOME_NO_POINTS,
    VARIANT_A_ID,
    VARIANT_B_ID,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
    variant_a_matching_view_settings,
    variant_b_matching_view_settings,
)
from src.matching import match
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult
from src.refinement import refine_points
from src.registration import register
from src.registration.result import FLAG_OUTPUT_TOO_LARGE
from src.registration.settings import unvalidated_software_defaults as registration_defaults
from src.representation import generate_representation, generate_representation_with_settings
from src.representation._matching_view import resolve_matching_gsd
from src.representation.settings import MatchingViewSettings
from src.verification import verify_matches
from src.verification.geometric_models import get_geometric_model
from src.verification.settings import unvalidated_software_defaults as verification_defaults

_REPO_ROOT = Path(__file__).resolve().parents[3]
T = TypeVar("T")
_MODEL_MIN = 4


class Exp002Error(RuntimeError):
    """Raised when EXP-002 cannot start."""


def run_exp002(
    *,
    data_root: Path | None = None,
    output_dir: Path | None = None,
    record_path: Path | None = None,
) -> dict[str, Any]:
    """Run variants A and B on pair 01 and write the experiment record."""

    try:
        root = data_root if data_root is not None else configured_data_root()
    except DataRootError as exc:
        raise Exp002Error(str(exc)) from exc
    if root is None:
        raise Exp002Error(
            f"Set {DATA_ROOT_ENV} to the external demo dataset that contains "
            f"{OHRC_PRODUCT_ID} and {LROC_PRODUCT_ID}."
        )
    if not root.exists() or not root.is_dir():
        raise Exp002Error(f"data root is not an existing directory: {root}")

    ohrc_path = find_product(root, OHRC_PRODUCT_ID)
    lroc_path = find_product(root, LROC_PRODUCT_ID)
    if ohrc_path is None or lroc_path is None:
        raise Exp002Error(
            "ingest_product cannot start: EXP-002 pair-01 products were not "
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


def run_exp002_from_products(
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
    except Exception as exc:
        record["status"] = "failed"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        return

    model = get_geometric_model(verification_defaults().model_id)
    variants: dict[str, dict[str, Any]] = {}
    for variant_id, settings, use_frozen_default in (
        (VARIANT_A_ID, variant_a_matching_view_settings(), True),
        (VARIANT_B_ID, variant_b_matching_view_settings(), False),
    ):
        variants[variant_id] = _run_variant(
            variant_id, pair, settings, model, use_frozen_default
        )

    record["variants"] = variants
    record["comparison"] = _comparison(variants)
    record["interpretation"] = _interpretation(variants, model.min_samples)
    failed = [
        variant_id
        for variant_id, arm in variants.items()
        if arm.get("status") != "completed"
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
    settings: MatchingViewSettings,
    model: Any,
    use_frozen_default: bool,
) -> dict[str, Any]:
    arm: dict[str, Any] = {
        "variant_id": variant_id,
        "matcher_id": "sift",
        "scale_policy": settings.scale_policy,
        "uses_frozen_generate_representation": use_frozen_default,
        "runtime_seconds": {},
        "memory": {},
    }
    try:
        representation = _arm_timed(
            arm,
            "generate_representation",
            lambda: (
                generate_representation(pair)
                if use_frozen_default
                else generate_representation_with_settings(pair, settings)
            ),
        )
        correspondences = _arm_timed(
            arm, "match", lambda image=representation: match(pair, image)
        )
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
    reporting_settings = variant_b_matching_view_settings()
    metadata = getattr(representation, "metadata", {}) or {}

    arm["generate_representation"] = {
        "representation_id": getattr(representation, "representation_id", None),
        "source_matching_view": _matching_view_report(
            metadata.get("source_matching_view"), pair.source, reporting_settings
        ),
        "reference_matching_view": _matching_view_report(
            metadata.get("reference_matching_view"), pair.reference, reporting_settings
        ),
        "coordinate_mapping": (
            "x_original = x_matching * stride; y_original = y_matching * stride"
        ),
        "spatial_window": "full_image_stride_decimation_not_a_cropped_window",
        "resampling": settings.downsample_method,
    }
    del representation

    arm["match"] = {
        "matcher_id": correspondences.matcher_id,
        "representation_id": correspondences.representation_id,
        "raw_match_count": len(correspondences.matches),
        "coordinates": "original_image_pixels_after_matching_view_scale",
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
    }
    arm["spatial_distribution"] = {
        "verified_match_coverage": coverage(inliers, pair),
        "verified_match_occupancy": occupancy(inliers, pair, grid_bins),
    }
    arm["select_control_points"] = {
        "control_point_count": len(control_points),
        "selection_succeeded": len(control_points) >= model.min_samples,
        "points": [_point_dump(point) for point in control_points],
    }
    arm["refine_points"] = _refinement_report(control_points, refined)
    arm["register"] = _registration_report(registered, model.min_samples, len(refined))
    arm["evaluate"] = _evaluation_report(evaluated)
    arm["status"] = "completed"
    arm["failed_stage"] = None
    arm.pop("_stage", None)
    arm["runtime_seconds"]["variant_total"] = sum(
        float(value) for value in arm["runtime_seconds"].values()
    )
    return arm


def _matching_view_report(
    view: Any,
    product: LunarProduct,
    reporting_settings: MatchingViewSettings,
) -> dict[str, Any]:
    payload = _jsonable(view) if isinstance(view, dict) else {}
    stride = int(payload.get("stride") or 1)
    ingested = product.gsd_meters
    gsd_used: float | None
    gsd_source: str
    try:
        gsd_used, gsd_source = resolve_matching_gsd(product, reporting_settings)
    except ValueError:
        gsd_used, gsd_source = None, "unavailable"
    effective = None if gsd_used is None else float(gsd_used) * float(stride)
    payload.update(
        {
            "ingested_gsd_meters": ingested,
            "gsd_meters_used": gsd_used,
            "gsd_source": payload.get("gsd_source", gsd_source),
            "effective_gsd_meters": payload.get("effective_gsd_meters", effective),
        }
    )
    return payload


def _comparison(variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for variant_id in (VARIANT_A_ID, VARIANT_B_ID):
        arm = variants.get(variant_id) or {}
        source_view = (arm.get("generate_representation") or {}).get("source_matching_view") or {}
        reference_view = (arm.get("generate_representation") or {}).get(
            "reference_matching_view"
        ) or {}
        register = arm.get("register") or {}
        rows.append(
            {
                "variant": variant_id,
                "scale_policy": arm.get("scale_policy"),
                "matching_view_dimensions_source": source_view.get("matching_shape"),
                "matching_view_dimensions_reference": reference_view.get("matching_shape"),
                "stride_source": source_view.get("stride"),
                "stride_reference": reference_view.get("stride"),
                "resampling": (arm.get("generate_representation") or {}).get("resampling"),
                "effective_gsd_source": source_view.get("effective_gsd_meters"),
                "effective_gsd_reference": reference_view.get("effective_gsd_meters"),
                "raw_matches": (arm.get("match") or {}).get("raw_match_count"),
                "verified_inliers": (arm.get("verify_matches") or {}).get(
                    "verified_inlier_count"
                ),
                "inlier_ratio": (arm.get("verify_matches") or {}).get("inlier_ratio"),
                "spatial_coverage": (arm.get("spatial_distribution") or {}).get(
                    "verified_match_coverage"
                ),
                "control_point_count": (arm.get("select_control_points") or {}).get(
                    "control_point_count"
                ),
                "transform_status": _transform_status(register),
                "refinement_status": (arm.get("refine_points") or {}).get("outcome"),
                "runtime_seconds": arm.get("runtime_seconds"),
            }
        )
    return {"rows": rows}


def _interpretation(variants: dict[str, dict[str, Any]], min_samples: int) -> dict[str, Any]:
    counts = {}
    strides = {}
    for variant_id in (VARIANT_A_ID, VARIANT_B_ID):
        arm = variants.get(variant_id) or {}
        counts[variant_id] = (arm.get("verify_matches") or {}).get("verified_inlier_count")
        source_view = (arm.get("generate_representation") or {}).get("source_matching_view") or {}
        reference_view = (arm.get("generate_representation") or {}).get(
            "reference_matching_view"
        ) or {}
        strides[variant_id] = {
            "source": source_view.get("stride"),
            "reference": reference_view.get("stride"),
        }

    a_count = counts.get(VARIANT_A_ID)
    b_count = counts.get(VARIANT_B_ID)
    improved = (
        a_count is not None and b_count is not None and int(b_count) > int(a_count)
    )
    b_exceeds = b_count is not None and int(b_count) > min_samples
    strides_changed = strides.get(VARIANT_A_ID) != strides.get(VARIANT_B_ID)
    return {
        "primary_metric": "verified_inlier_count",
        "model_min_samples": min_samples,
        "decision_rule": DECISION_RULE,
        "verified_inliers_by_variant": counts,
        "verified_inliers_improved": improved,
        "variant_b_exceeds_model_minimum": b_exceeds,
        "hypothesis_supported": b_exceeds,
        "matching_view_strides_changed": strides_changed,
        "strides_by_variant": strides,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "four_point_dlt_residuals_are_not_accuracy": True,
        "limitations": _limitations(strides_changed, b_count),
    }


def _limitations(strides_changed: bool, b_count: int | None) -> list[str]:
    notes = [
        "Independent accuracy is NOT VALIDATED. There is no surveyed lunar control.",
        "Four-point projective DLT residuals are an algebraic identity, not accuracy.",
        "LROC ingested gsd_meters is None. Variant B may use the documented "
        "LROC NAC catalog GSD 0.5 m/pixel; that value is not written onto "
        "LunarProduct and is not SPICE-derived.",
        "Overlap is not recomputed from the products. The manifest declares "
        "overlap_status=verified from NASA PDS ODE footprints.",
        "Full-raster registration remains blocked by the existing 16,777,216-pixel cap.",
        "This experiment runs pair_01_equatorial only.",
    ]
    if not strides_changed:
        notes.append(
            "Integer GSD-normalised strides under the 4,194,304-pixel budget "
            "matched the per-image pixel-budget strides, so the independent "
            "variable did not change the matching views on this pair."
        )
    if b_count == _MODEL_MIN:
        notes.append(
            "Variant B produced exactly four verified inliers, the projective "
            "DLT minimum, so the fit is unfalsifiable."
        )
    return notes


def _transform_status(register: dict[str, Any]) -> str:
    if register.get("full_raster_warp_blocked"):
        if register.get("transform_fitted"):
            return "fitted_full_raster_blocked_by_pixel_cap"
        return "blocked_by_pixel_cap"
    if register.get("transform_fitted"):
        return "fitted"
    return "not_fitted"


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
        "minimal_sample_fit": bool(
            transformation is not None and fit_point_count == min_samples
        ),
    }
    if report["minimal_sample_fit"]:
        report["minimal_sample_warning"] = (
            f"the transform was fitted from exactly {min_samples} points, the "
            "projective DLT minimum, so its fit residuals are an algebraic "
            "identity and carry no information about registration accuracy"
        )
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
        "gsd_ratio_note": (
            "characterize_pair leaves gsd_ratio None when either product lacks "
            "ingested gsd_meters; EXP-002 does not invent that pair scalar"
        ),
    }


def _product_report(product: LunarProduct) -> dict[str, Any]:
    dimensions = product.dimensions
    return {
        "product_id": product.product_id,
        "instrument": product.instrument,
        "mission": product.mission,
        "gsd_meters": product.gsd_meters,
        "valid_pixel_ratio": product.valid_pixel_ratio,
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


def _new_record() -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "pair_manifest_id": PAIR_MANIFEST_ID,
        "status": "running",
        "failed_stage": None,
        "hypothesis": HYPOTHESIS,
        "decision_rule": DECISION_RULE,
        "inherited_from": BASELINE_EXPERIMENT_ID,
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


def _memory_snapshot() -> dict[str, int | None]:
    rss = _process_rss_bytes()
    traced = None
    if tracemalloc.is_tracing():
        traced = tracemalloc.get_traced_memory()[0]
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
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
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


__all__ = ["Exp002Error", "run_exp002", "run_exp002_from_products"]
