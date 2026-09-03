"""EXP-003 matching-view scale-robustness comparison.

Runs the frozen SIFT pipeline three times on pair_01_equatorial:

* Variant A — ``generate_representation(pair)``, the EXP-000 matching view
  (OHRC stride 15, LROC stride 8).
* Variant B — same SIFT path; LROC matching view coarsened by approximately
  2x additional stride-decimation (expected pair-01 LROC stride 16).
* Variant C — same SIFT path; LROC matching view sampled approximately 2x
  finer (expected pair-01 LROC stride 4).

OHRC stays at the EXP-000 stride. Every other EXP-000 parameter is held
constant. Diagnostic rasters are not written. Four-point DLT residuals are
not treated as accuracy.
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
from src.io.exp003.config import (
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
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_C_ID,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
    variant_a_matching_view_settings,
    variant_b_matching_view_settings,
    variant_c_matching_view_settings,
)
from src.matching import match
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.refinement import refine_points
from src.registration import register
from src.representation import generate_representation, generate_representation_with_settings
from src.representation.settings import MatchingViewSettings
from src.verification import verify_matches
from src.verification.geometric_models import get_geometric_model
from src.verification.settings import unvalidated_software_defaults as verification_defaults

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VARIANT_ORDER = (VARIANT_A_ID, VARIANT_B_ID, VARIANT_C_ID)


class Exp003Error(RuntimeError):
    """Raised when EXP-003 cannot start."""


def run_exp003(
    *,
    data_root: Path | None = None,
    output_dir: Path | None = None,
    record_path: Path | None = None,
) -> dict[str, Any]:
    """Run variants A, B, and C on pair 01 and write the experiment record."""

    try:
        root = data_root if data_root is not None else configured_data_root()
    except DataRootError as exc:
        raise Exp003Error(str(exc)) from exc
    if root is None:
        raise Exp003Error(
            f"Set {DATA_ROOT_ENV} to the external demo dataset that contains "
            f"{OHRC_PRODUCT_ID} and {LROC_PRODUCT_ID}."
        )
    if not root.exists() or not root.is_dir():
        raise Exp003Error(f"data root is not an existing directory: {root}")

    ohrc_path = find_product(root, OHRC_PRODUCT_ID)
    lroc_path = find_product(root, LROC_PRODUCT_ID)
    if ohrc_path is None or lroc_path is None:
        raise Exp003Error(
            "ingest_product cannot start: EXP-003 pair-01 products were not "
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


def run_exp003_from_products(
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
    for variant_id, settings, use_frozen_default in (
        (VARIANT_A_ID, variant_a_matching_view_settings(), True),
        (VARIANT_B_ID, variant_b_matching_view_settings(), False),
        (VARIANT_C_ID, variant_c_matching_view_settings(), False),
    ):
        variants[variant_id] = _run_variant(
            variant_id, pair, settings, model, use_frozen_default
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
    settings: MatchingViewSettings,
    model: Any,
    use_frozen_default: bool,
) -> dict[str, Any]:
    arm: dict[str, Any] = {
        "variant_id": variant_id,
        "matcher_id": "sift",
        "scale_policy": settings.scale_policy,
        "relative_stride_factor_by_instrument": [
            {"instrument": name, "factor": factor}
            for name, factor in settings.relative_stride_factor_by_instrument
        ],
        "uses_frozen_generate_representation": use_frozen_default,
        "runtime_seconds": {},
        "memory": {},
    }
    try:
        representation = _arm_timed(
            arm,
            "generate_representation",
            lambda settings=settings, frozen=use_frozen_default: (
                generate_representation(pair)
                if frozen
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
                "relative_stride_factor_by_instrument": arm.get(
                    "relative_stride_factor_by_instrument"
                ),
                "matching_view_dimensions_source": source_view.get("matching_shape"),
                "matching_view_dimensions_reference": reference_view.get("matching_shape"),
                "matching_pixel_count_source": source_view.get("matching_pixel_count"),
                "matching_pixel_count_reference": reference_view.get("matching_pixel_count"),
                "stride_source": source_view.get("stride"),
                "stride_reference": reference_view.get("stride"),
                "baseline_stride_reference": reference_view.get("baseline_stride"),
                "relative_stride_factor_reference": reference_view.get(
                    "relative_stride_factor"
                ),
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
    strides: dict[str, dict[str, Any]] = {}
    for variant_id in _VARIANT_ORDER:
        arm = variants.get(variant_id) or {}
        counts[variant_id] = (arm.get("verify_matches") or {}).get("verified_inlier_count")
        raw_counts[variant_id] = (arm.get("match") or {}).get("raw_match_count")
        source_view = (arm.get("generate_representation") or {}).get("source_matching_view") or {}
        reference_view = (arm.get("generate_representation") or {}).get(
            "reference_matching_view"
        ) or {}
        strides[variant_id] = {
            "source": source_view.get("stride"),
            "reference": reference_view.get("stride"),
            "reference_matching_shape": reference_view.get("matching_shape"),
        }

    a_count = counts.get(VARIANT_A_ID)
    b_count = counts.get(VARIANT_B_ID)
    c_count = counts.get(VARIANT_C_ID)
    ohrc_fixed = _same_int(
        strides[VARIANT_A_ID]["source"],
        strides[VARIANT_B_ID]["source"],
        strides[VARIANT_C_ID]["source"],
    )
    lroc_changed = (
        strides[VARIANT_A_ID]["reference"] != strides[VARIANT_B_ID]["reference"]
        and strides[VARIANT_A_ID]["reference"] != strides[VARIANT_C_ID]["reference"]
        and strides[VARIANT_B_ID]["reference"] != strides[VARIANT_C_ID]["reference"]
    )
    verified_equal = (
        a_count is not None
        and b_count is not None
        and c_count is not None
        and int(a_count) == int(b_count) == int(c_count)
    )
    material_verified = (
        a_count is not None
        and b_count is not None
        and c_count is not None
        and not verified_equal
    )
    raw_equal = (
        raw_counts[VARIANT_A_ID] is not None
        and raw_counts[VARIANT_B_ID] is not None
        and raw_counts[VARIANT_C_ID] is not None
        and int(raw_counts[VARIANT_A_ID])
        == int(raw_counts[VARIANT_B_ID])
        == int(raw_counts[VARIANT_C_ID])
    )
    hypothesis_supported = bool(ohrc_fixed and lroc_changed and verified_equal)
    return {
        "primary_metric": "verified_inlier_count",
        "model_min_samples": min_samples,
        "decision_rule": DECISION_RULE,
        "expected_pair_01_strides": EXPECTED_PAIR_01_STRIDES,
        "verified_inliers_by_variant": counts,
        "raw_matches_by_variant": raw_counts,
        "ohrc_stride_held_fixed": ohrc_fixed,
        "lroc_matching_view_scale_changed": lroc_changed,
        "independent_variable_applied": bool(ohrc_fixed and lroc_changed),
        "verified_inliers_equal_across_variants": verified_equal,
        "raw_matches_equal_across_variants": raw_equal,
        "scale_changes_materially_affect_verified_yield": material_verified,
        "hypothesis_supported": hypothesis_supported,
        "strides_by_variant": strides,
        "independent_accuracy": INDEPENDENT_ACCURACY_NOT_VALIDATED,
        "four_point_dlt_residuals_are_not_accuracy": True,
        "limitations": _limitations(
            ohrc_fixed,
            lroc_changed,
            verified_equal,
            raw_equal,
            a_count,
            min_samples,
        ),
    }


def _limitations(
    ohrc_fixed: bool,
    lroc_changed: bool,
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
        "This experiment runs pair_01_equatorial only. It cannot establish general "
        "SIFT scale invariance.",
        "Variant C may exceed the 4,194,304-pixel matching-view budget so the "
        "LROC image SIFT sees is actually finer than baseline. The registration "
        "output cap is not raised.",
    ]
    if not ohrc_fixed:
        notes.append("OHRC matching-view stride was not held fixed, so the comparison is invalid.")
    if not lroc_changed:
        notes.append(
            "LROC matching-view strides did not differ across A/B/C, so the "
            "independent variable did not change the images SIFT saw."
        )
    if verified_equal and a_count == min_samples:
        notes.append(
            "All variants produced exactly four verified inliers, the projective "
            "DLT minimum, so equal yield is consistent with robustness and also "
            "with an unfalsifiable four-point consensus set."
        )
    if not raw_equal:
        notes.append(
            "Raw Lowe-ratio matches changed across variants, so detector-level "
            "correspondence yield is not scale-invariant even when verified "
            "inlier counts are equal."
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
            "ingested gsd_meters; EXP-003 does not invent that pair scalar and "
            "does not use catalog GSD as the independent variable"
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


__all__ = ["Exp003Error", "run_exp003", "run_exp003_from_products"]
