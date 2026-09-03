"""EXP-004 existing-representation comparison.

Runs the frozen SIFT pipeline three times on pair_01_equatorial:

* Variant A — ``generate_representation(pair)``, EXP-000 intensity.
* Variant B — same SIFT path; existing gradient representation via routing.
* Variant C — same SIFT path; existing structural representation via routing.

Matching-view scale stays at the EXP-000 policy (OHRC stride 15, LROC
stride 8). Every other EXP-000 parameter is held constant. Diagnostic
rasters are not written. Four-point DLT residuals are not treated as
accuracy.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

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
from src.io.exp004.config import (
    BASELINE_EXPERIMENT_ID,
    DECISION_RULE,
    EXPECTED_PAIR_01_STRIDES,
    EXPERIMENT_ID,
    FOOTPRINT_SOURCE,
    HYPOTHESIS,
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    LROC_PRODUCT_ID,
    OHRC_PRODUCT_ID,
    PAIR_MANIFEST_ID,
    ROUTING_DIFFICULTY_BY_REPRESENTATION,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_C_ID,
    VARIANT_REPRESENTATION_ID,
    pair_routed_for_representation,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
)
from src.matching import match
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.refinement import refine_points
from src.registration import register
from src.representation import generate_representation
from src.routing import select_representation_id
from src.verification import verify_matches
from src.verification.geometric_models import get_geometric_model
from src.verification.settings import unvalidated_software_defaults as verification_defaults

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VARIANT_ORDER = (VARIANT_A_ID, VARIANT_B_ID, VARIANT_C_ID)


class Exp004Error(RuntimeError):
    """Raised when EXP-004 cannot start."""


def run_exp004(
    *,
    data_root: Path | None = None,
    output_dir: Path | None = None,
    record_path: Path | None = None,
) -> dict[str, Any]:
    """Run variants A, B, and C on pair 01 and write the experiment record."""

    try:
        root = data_root if data_root is not None else configured_data_root()
    except DataRootError as exc:
        raise Exp004Error(str(exc)) from exc
    if root is None:
        raise Exp004Error(
            f"Set {DATA_ROOT_ENV} to the external demo dataset that contains "
            f"{OHRC_PRODUCT_ID} and {LROC_PRODUCT_ID}."
        )
    if not root.exists() or not root.is_dir():
        raise Exp004Error(f"data root is not an existing directory: {root}")

    ohrc_path = find_product(root, OHRC_PRODUCT_ID)
    lroc_path = find_product(root, LROC_PRODUCT_ID)
    if ohrc_path is None or lroc_path is None:
        raise Exp004Error(
            "ingest_product cannot start: EXP-004 pair-01 products were not "
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


def run_exp004_from_products(
    source: LunarProduct,
    reference: LunarProduct,
    *,
    output_dir: Path | None = None,
    record_path: Path | None = None,
) -> dict[str, Any]:
    """Run all three variants from already ingested products. Used by tests."""

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
    for variant_id in _VARIANT_ORDER:
        variants[variant_id] = _run_variant(
            variant_id, pair, VARIANT_REPRESENTATION_ID[variant_id], model
        )

    record["variants"] = variants
    record["comparison"] = _comparison(variants)
    record["interpretation"] = _interpretation(variants, model.min_samples)
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
    representation_id: str,
    model: Any,
) -> dict[str, Any]:
    routed = pair_routed_for_representation(pair, representation_id)
    uses_original_pair = routed is pair
    arm: dict[str, Any] = {
        "variant_id": variant_id,
        "matcher_id": "sift",
        "requested_representation_id": representation_id,
        "routing_difficulty": ROUTING_DIFFICULTY_BY_REPRESENTATION[representation_id],
        "uses_frozen_generate_representation": True,
        "uses_original_pair_for_representation": uses_original_pair,
        "routed_select_representation_id": select_representation_id(routed),
        "runtime_seconds": {},
        "memory": {},
    }
    try:
        if arm["routed_select_representation_id"] != representation_id:
            raise RuntimeError(
                "existing routing did not select the requested representation: "
                f"requested={representation_id!r}, "
                f"select_representation_id={arm['routed_select_representation_id']!r}"
            )
        representation = _arm_timed(
            arm,
            "generate_representation",
            lambda image_pair=routed: generate_representation(image_pair),
        )
        actual_id = getattr(representation, "representation_id", None)
        if actual_id != representation_id:
            raise RuntimeError(
                "generate_representation did not build the requested "
                f"representation: requested={representation_id!r}, "
                f"actual={actual_id!r}"
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
    metadata = getattr(representation, "metadata", {}) or {}

    arm["generate_representation"] = {
        "representation_id": getattr(representation, "representation_id", None),
        "source_matching_view": _matching_view_report(
            metadata.get("source_matching_view"), pair.source
        ),
        "reference_matching_view": _matching_view_report(
            metadata.get("reference_matching_view"), pair.reference
        ),
        "coordinate_mapping": (
            "x_original = x_matching * stride; y_original = y_matching * stride"
        ),
        "spatial_window": "full_image_stride_decimation_not_a_cropped_window",
        "resampling": "stride_decimation",
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


def _matching_view_report(view: Any, product: LunarProduct) -> dict[str, Any]:
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
        source_view = (arm.get("generate_representation") or {}).get("source_matching_view") or {}
        reference_view = (arm.get("generate_representation") or {}).get(
            "reference_matching_view"
        ) or {}
        register = arm.get("register") or {}
        rows.append(
            {
                "variant": variant_id,
                "representation_id": (arm.get("generate_representation") or {}).get(
                    "representation_id"
                )
                or arm.get("requested_representation_id"),
                "routing_difficulty": arm.get("routing_difficulty"),
                "matching_view_dimensions_source": source_view.get("matching_shape"),
                "matching_view_dimensions_reference": reference_view.get("matching_shape"),
                "matching_pixel_count_source": source_view.get("matching_pixel_count"),
                "matching_pixel_count_reference": reference_view.get("matching_pixel_count"),
                "stride_source": source_view.get("stride"),
                "stride_reference": reference_view.get("stride"),
                "resampling": (arm.get("generate_representation") or {}).get("resampling"),
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
    counts: dict[str, Any] = {}
    raw_counts: dict[str, Any] = {}
    representation_ids: dict[str, Any] = {}
    strides: dict[str, dict[str, Any]] = {}
    for variant_id in _VARIANT_ORDER:
        arm = variants.get(variant_id) or {}
        counts[variant_id] = (arm.get("verify_matches") or {}).get("verified_inlier_count")
        raw_counts[variant_id] = (arm.get("match") or {}).get("raw_match_count")
        representation_ids[variant_id] = (arm.get("generate_representation") or {}).get(
            "representation_id"
        ) or arm.get("requested_representation_id")
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
    c_count = counts.get(VARIANT_C_ID)
    expected_ids = [
        VARIANT_REPRESENTATION_ID[VARIANT_A_ID],
        VARIANT_REPRESENTATION_ID[VARIANT_B_ID],
        VARIANT_REPRESENTATION_ID[VARIANT_C_ID],
    ]
    observed_ids = [
        representation_ids.get(VARIANT_A_ID),
        representation_ids.get(VARIANT_B_ID),
        representation_ids.get(VARIANT_C_ID),
    ]
    representation_changed = observed_ids == expected_ids and len(set(observed_ids)) == 3
    strides_fixed = (
        _same_int(
            strides[VARIANT_A_ID]["source"],
            strides[VARIANT_B_ID]["source"],
            strides[VARIANT_C_ID]["source"],
        )
        and _same_int(
            strides[VARIANT_A_ID]["reference"],
            strides[VARIANT_B_ID]["reference"],
            strides[VARIANT_C_ID]["reference"],
        )
    )
    independent_variable_applied = bool(representation_changed and strides_fixed)
    verified_improved = (
        a_count is not None
        and b_count is not None
        and c_count is not None
        and (int(b_count) > int(a_count) or int(c_count) > int(a_count))
    )
    verified_equal = (
        a_count is not None
        and b_count is not None
        and c_count is not None
        and int(a_count) == int(b_count) == int(c_count)
    )
    raw_equal = (
        raw_counts[VARIANT_A_ID] is not None
        and raw_counts[VARIANT_B_ID] is not None
        and raw_counts[VARIANT_C_ID] is not None
        and int(raw_counts[VARIANT_A_ID])
        == int(raw_counts[VARIANT_B_ID])
        == int(raw_counts[VARIANT_C_ID])
    )
    hypothesis_supported = bool(independent_variable_applied and verified_improved)
    return {
        "primary_metric": "verified_inlier_count",
        "model_min_samples": min_samples,
        "decision_rule": DECISION_RULE,
        "expected_pair_01_strides": EXPECTED_PAIR_01_STRIDES,
        "representation_ids_by_variant": representation_ids,
        "verified_inliers_by_variant": counts,
        "raw_matches_by_variant": raw_counts,
        "matching_view_strides_held_fixed": strides_fixed,
        "representation_changed": representation_changed,
        "independent_variable_applied": independent_variable_applied,
        "verified_inliers_improved": verified_improved,
        "verified_inliers_equal_across_variants": verified_equal,
        "raw_matches_equal_across_variants": raw_equal,
        "hypothesis_supported": hypothesis_supported,
        "strides_by_variant": strides,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "four_point_dlt_residuals_are_not_accuracy": True,
        "limitations": _limitations(
            representation_changed,
            strides_fixed,
            verified_equal,
            raw_equal,
            a_count,
            min_samples,
        ),
    }


def _limitations(
    representation_changed: bool,
    strides_fixed: bool,
    verified_equal: bool,
    raw_equal: bool,
    a_count: int | None,
    min_samples: int,
) -> list[str]:
    notes = [
        "Independent accuracy is NOT VALIDATED. There is no surveyed lunar control.",
        "Four-point projective DLT residuals are an algebraic identity, not accuracy.",
        "Overlap is not recomputed from the products. The manifest declares "
        "overlap_status=verified from NASA PDS ODE footprints.",
        "Full-raster registration remains blocked by the existing 16,777,216-pixel cap.",
        "This experiment runs pair_01_equatorial only. It cannot establish a "
        "superior representation.",
        "No new representation, matcher, or SIFT parameter was introduced.",
    ]
    if not representation_changed:
        notes.append(
            "representation_id did not differ across A/B/C as intensity / "
            "gradient / structural, so the independent variable did not change "
            "the images SIFT saw."
        )
    if not strides_fixed:
        notes.append(
            "Matching-view strides were not held at the EXP-000 baseline, so "
            "the comparison is not representation-only."
        )
    if verified_equal and a_count == min_samples:
        notes.append(
            "All variants produced exactly four verified inliers, the projective "
            "DLT minimum, so equal yield is consistent with no representation "
            "gain and also with an unfalsifiable four-point consensus set."
        )
    if not raw_equal:
        notes.append(
            "Raw Lowe-ratio matches changed across variants, so detector-level "
            "correspondence yield is representation-sensitive."
        )
    return notes


def _same_int(*values: Any) -> bool:
    if any(value is None for value in values):
        return False
    first = int(values[0])
    return all(int(value) == first for value in values[1:])


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
            "ingested gsd_meters; EXP-004 does not invent that pair scalar"
        ),
        "representation_note": (
            "characterize_pair leaves difficulty unset, so the frozen "
            "generate_representation path selects intensity. Variants B and C "
            "copy difficulty onto a pair used only for generate_representation."
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


__all__ = ["Exp004Error", "run_exp004", "run_exp004_from_products"]
