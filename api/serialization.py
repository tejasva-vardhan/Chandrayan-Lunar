"""Map scientific models to API DTOs. No scientific invention."""

from __future__ import annotations

from api.schemas import (
    ControlPointDTO,
    CorrespondencePointDTO,
    MetricsDTO,
    ProductInfoDTO,
    RegistrationResultDTO,
    TransformationDTO,
)
from src.io.exports import ExportManifest
from src.models.correspondence_set import Correspondence, CorrespondenceSet
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult


def product_to_dto(product: LunarProduct) -> ProductInfoDTO:
    dims = product.dimensions
    return ProductInfoDTO(
        product_id=product.product_id,
        instrument=product.instrument,
        mission=product.mission,
        width_px=dims.width_px if dims is not None else None,
        height_px=dims.height_px if dims is not None else None,
        gsd_meters=product.gsd_meters,
        acquisition_time=product.acquisition_time.isoformat()
        if product.acquisition_time is not None
        else None,
        raster_uri=product.raster_uri,
    )


def correspondence_to_dto(item: Correspondence) -> CorrespondencePointDTO:
    return CorrespondencePointDTO(
        source_xy=item.source_xy,
        reference_xy=item.reference_xy,
        confidence=item.confidence,
        residual=item.residual,
        status=item.status,
    )


def control_point_to_dto(item: ControlPoint) -> ControlPointDTO:
    return ControlPointDTO(
        source_xy=item.source_xy,
        reference_xy=item.reference_xy,
        residual=item.residual,
        uncertainty=item.uncertainty,
    )


def _counts(correspondences: CorrespondenceSet | None) -> tuple[int, int, int]:
    if correspondences is None:
        return 0, 0, 0
    matches = correspondences.matches
    inliers = sum(1 for item in matches if item.status == "inlier")
    rejected = sum(1 for item in matches if item.status == "rejected")
    return len(matches), inliers, rejected


def _refinement_note(result: RegistrationResult) -> str:
    if not result.control_points:
        return "No control points available for refinement."
    changed = sum(
        1
        for point in result.control_points
        if point.uncertainty is not None  # uncertainty set only when refinement computed it
    )
    if changed == 0:
        return (
            "Refinement outcome indeterminate — ControlPoint interface has no per-point "
            "refinement outcome field; unchanged coordinates are not claimed as successful."
        )
    return f"Refinement attached uncertainty on {changed} control point(s)."


def result_to_dto(
    result: RegistrationResult,
    pair: RegistrationPair,
    *,
    manifest: ExportManifest | None = None,
    runtime_seconds: float | None = None,
) -> RegistrationResultDTO:
    candidates, verified, rejected = _counts(result.correspondences)
    metrics = None
    if result.metrics is not None:
        metrics = MetricsDTO(
            verification_residual_rmse=result.metrics.rmse,
            inlier_count=result.metrics.inlier_count,
            inlier_ratio=result.metrics.inlier_ratio,
            spatial_coverage=result.metrics.spatial_coverage,
            control_point_count=result.metrics.control_point_count,
        )
    transformation = None
    if result.transformation is not None:
        transformation = TransformationDTO(
            model_name=result.transformation.model_name,
            parameters=dict(result.transformation.parameters),
        )
    export = None
    if manifest is not None:
        export = manifest.model_dump(mode="json")
    matches = result.correspondences.matches if result.correspondences is not None else []
    return RegistrationResultDTO(
        pair_id=result.pair_id,
        source=product_to_dto(pair.source),
        reference=product_to_dto(pair.reference),
        candidate_correspondences=candidates,
        verified_inliers=verified,
        rejected_correspondences=rejected,
        correspondences=[correspondence_to_dto(item) for item in matches],
        inliers=[correspondence_to_dto(item) for item in result.inliers],
        control_points=[control_point_to_dto(item) for item in result.control_points],
        metrics=metrics,
        transformation=transformation,
        registered_source_uri=result.registered_source_uri,
        registered_artifact_available=bool(result.registered_source_uri),
        quality_flags=list(result.quality_flags),
        confidence_class=result.confidence_class,
        refinement_note=_refinement_note(result),
        evaluation_limitation=(
            "rmse is derived from verification transfer residuals and is not an "
            "independent registration-accuracy metric"
        ),
        runtime_seconds=runtime_seconds,
        export_manifest=export,
    )
