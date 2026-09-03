"""Serialization boundary tests for API DTOs."""

from __future__ import annotations

from api.serialization import result_to_dto
from src.io.exports import ExportManifest
from src.models.common import ImageDimensions
from src.models.correspondence_set import Correspondence, CorrespondenceSet
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationMetrics, RegistrationResult


def test_result_dto_labels_verification_rmse_not_accuracy() -> None:
    source = LunarProduct(
        product_id="src",
        instrument="OHRC",
        dimensions=ImageDimensions(width_px=100, height_px=80),
    )
    reference = LunarProduct(
        product_id="ref",
        instrument="LRO_NAC",
        dimensions=ImageDimensions(width_px=100, height_px=80),
    )
    matches = [
        Correspondence(
            source_xy=(10.0, 10.0),
            reference_xy=(12.0, 11.0),
            residual=0.5,
            status="inlier",
        ),
        Correspondence(
            source_xy=(20.0, 20.0),
            reference_xy=(40.0, 40.0),
            residual=9.0,
            status="rejected",
        ),
    ]
    correspondences = CorrespondenceSet(
        pair_id="pair-a", matcher_id="sift", matches=matches
    )
    result = RegistrationResult(
        pair_id="pair-a",
        correspondences=correspondences,
        inliers=[matches[0]],
        metrics=RegistrationMetrics(
            rmse=0.5,
            inlier_count=1,
            inlier_ratio=0.5,
            spatial_coverage=0.1,
            control_point_count=0,
        ),
        quality_flags=["not_independently_validated"],
    )
    pair = RegistrationPair(pair_id="pair-a", source=source, reference=reference)
    dto = result_to_dto(
        result,
        pair,
        manifest=ExportManifest(metrics="metrics.json"),
        runtime_seconds=1.25,
    )
    assert dto.candidate_correspondences == 2
    assert dto.verified_inliers == 1
    assert dto.rejected_correspondences == 1
    assert dto.metrics is not None
    assert dto.metrics.verification_residual_rmse == 0.5
    assert dto.metrics.verification_residual_rmse_label == "Verification residual RMSE"
    assert "independent" in dto.metrics.independent_accuracy_claim.lower()
    assert dto.runtime_seconds == 1.25
