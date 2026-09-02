"""Export contract for registration outputs (v3 §22 recommended package)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationResult


class ExportManifest(BaseModel):
    """URIs for files listed in the v3 output contract.

    Paths are recorded only after a real exporter writes them.
    Names are logical; this contract does not assume image or table formats.
    """

    model_config = ConfigDict(extra="forbid")

    registered_source: str | None = None
    all_matches: str | None = None
    inliers: str | None = None
    control_points: str | None = None
    transformation: str | None = None
    metrics: str | None = None
    before: str | None = None
    matches_visualization: str | None = None
    overlay: str | None = None
    registration_report: str | None = None


def export_result(
    result: RegistrationResult, pair: RegistrationPair, output_dir: Path
) -> ExportManifest:
    """Write the registration package.

    Writes machine-readable outputs that are already represented by the
    result. It does not copy raw products or fabricate visualizations.

    Verification residuals, when present in metrics, are model-fit transfer
    errors. They are exported for diagnostic traceability only, not as an
    independent registration-accuracy measurement.
    """
    if result.pair_id != pair.pair_id:
        raise ValueError(
            f"result pair_id={result.pair_id!r} does not match pair_id={pair.pair_id!r}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    all_matches = (
        _write_json(
            output_dir / "all_matches.json",
            [item.model_dump(mode="json") for item in result.correspondences.matches],
        )
        if result.correspondences is not None
        else None
    )
    inliers = _write_json(
        output_dir / "inliers.json", [item.model_dump(mode="json") for item in result.inliers]
    )
    control_points = _write_json(
        output_dir / "control_points.json",
        [item.model_dump(mode="json") for item in result.control_points],
    )
    transformation = (
        _write_json(
            output_dir / "transformation.json", result.transformation.model_dump(mode="json")
        )
        if result.transformation is not None
        else None
    )
    metrics = (
        _write_json(output_dir / "metrics.json", result.metrics.model_dump(mode="json"))
        if result.metrics is not None
        else None
    )
    report = _write_json(
        output_dir / "registration_report.json",
        {
            "pair_id": result.pair_id,
            "source_product_id": pair.source.product_id,
            "reference_product_id": pair.reference.product_id,
            "raw_correspondence_count": len(result.correspondences.matches)
            if result.correspondences is not None
            else None,
            "verified_inlier_count": len(result.inliers),
            "control_point_count": len(result.control_points),
            "quality_flags": result.quality_flags,
            "registered_source_uri": result.registered_source_uri,
            "evaluation_limitation": (
                "rmse is derived from verification transfer residuals and is not an "
                "independent registration-accuracy metric"
            ),
            "projective_fit_limitation": _projective_fit_limitation(result),
            "independent_ground_truth_used": False,
            "spatial_coverage_definition": (
                "mean of the source and reference control-point AABB-area fractions: "
                "0.5 * (source_bbox_area / source_image_area + reference_bbox_area / "
                "reference_image_area); this measures extent, not accuracy or uniformity"
            ),
            "control_point_selection_note": (
                "control points copy eligible verified inliers after exact duplicate removal; "
                "selection does not create correspondences or alter the verified set"
            ),
            "refinement_outcome_note": (
                "unchanged coordinates are indeterminate because the current ControlPoint "
                "interface has no per-point refinement outcome field"
            ),
        },
    )
    return ExportManifest(
        registered_source=result.registered_source_uri,
        all_matches=all_matches,
        inliers=inliers,
        control_points=control_points,
        transformation=transformation,
        metrics=metrics,
        registration_report=report,
    )


def _write_json(path: Path, payload: Any) -> str:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def _projective_fit_limitation(result: RegistrationResult) -> str | None:
    transformation = result.transformation
    if transformation is None or transformation.model_name != "projective_2d_baseline":
        return None

    fit_count = len(result.control_points)
    minimum = 4
    if fit_count == minimum:
        return (
            "projective DLT was fit from exactly its four-point minimum; residuals on those "
            "same fit points are expected to be extremely small and are not evidence of "
            "accurate correspondence or registration"
        )
    return (
        f"projective DLT minimum is {minimum} points; this result carries {fit_count} "
        "control points, and verification residuals are not independent accuracy evidence"
    )
