from pathlib import Path

import pytest

import src.control_points as control_points
import src.evaluation as evaluation
import src.geometry as geometry
import src.ingestion as ingestion
import src.io.exports as io_exports
import src.matching as matching
import src.preprocessing as preprocessing
import src.refinement as refinement
import src.registration as registration
import src.representation as representation
import src.verification as verification
from src.io import export_result as io_export_result
from src.models import (
    ControlPoint,
    CorrespondenceSet,
    LunarProduct,
    RegistrationPair,
    RegistrationResult,
)
from src.pipeline.operations import (
    characterize_pair,
    evaluate,
    export_result,
    generate_representation,
    ingest_product,
    match,
    preprocess,
    refine_points,
    register,
    select_control_points,
    verify_matches,
)


def test_unimplemented_scientific_operations_fail_closed(
    tmp_path: Path,
    registration_pair: RegistrationPair,
) -> None:
    result = RegistrationResult(pair_id="pair-001")

    with pytest.raises(NotImplementedError):
        ingest_product(tmp_path / "missing")
    with pytest.raises(NotImplementedError):
        generate_representation(registration_pair)
    with pytest.raises(NotImplementedError):
        match(registration_pair)
    with pytest.raises(NotImplementedError):
        export_result(result, registration_pair, tmp_path)
    with pytest.raises(NotImplementedError):
        io_export_result(result, registration_pair, tmp_path)


def test_characterize_pair_is_implemented_and_does_not_invent_values(
    source_product: LunarProduct,
    reference_product: LunarProduct,
) -> None:
    pair = characterize_pair(source_product, reference_product)
    assert isinstance(pair, RegistrationPair)
    assert pair.source == source_product
    assert pair.reference == reference_product
    assert pair.characterization is not None
    assert pair.characterization.gsd_ratio is None
    assert pair.characterization.sun_angle_difference_degrees is None
    assert pair.characterization.viewing_geometry_difference is None
    assert pair.characterization.expected_overlap is None
    assert pair.characterization.valid_pixel_ratio is None
    assert pair.characterization.texture_contrast is None
    assert pair.characterization.difficulty is None
    assert pair.overlap_mask_uri is None
    assert pair.characterization.sensor_pair == "OHRC/LRO_NAC"
    assert pair.characterization.modality == "OHRC/LRO_NAC"


def test_preprocess_is_implemented_and_fail_closed_without_rasters(
    registration_pair: RegistrationPair,
) -> None:
    result = preprocess(registration_pair)
    assert isinstance(result, RegistrationPair)
    assert result is not registration_pair
    assert result.pair_id == registration_pair.pair_id
    assert result.source.product_id == registration_pair.source.product_id
    assert result.reference.product_id == registration_pair.reference.product_id
    assert result.source.raster_uri is None
    assert result.characterization == registration_pair.characterization


def test_verify_matches_is_implemented_and_fail_closed_on_empty(
    registration_pair: RegistrationPair,
) -> None:
    correspondences = CorrespondenceSet(pair_id="pair-001", matcher_id="unspecified")
    result = verify_matches(correspondences, registration_pair)
    assert result.matches == []
    assert result.pair_id == correspondences.pair_id


def test_select_control_points_is_implemented_and_fail_closed_on_empty(
    registration_pair: RegistrationPair,
) -> None:
    correspondences = CorrespondenceSet(pair_id="pair-001", matcher_id="unspecified")
    result = select_control_points(correspondences, registration_pair)
    assert result == []


def test_evaluate_is_implemented_and_fail_closed_on_empty(
    registration_pair: RegistrationPair,
) -> None:
    result = RegistrationResult(pair_id="pair-001")
    evaluated = evaluate(result, registration_pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.rmse is None
    assert evaluated.metrics.inlier_count is None
    assert evaluated.metrics.inlier_ratio is None
    assert evaluated.metrics.spatial_coverage is None
    assert evaluated.metrics.control_point_count == 0
    assert result.metrics is None


def test_refine_points_is_implemented_and_fail_closed_on_empty(
    registration_pair: RegistrationPair,
) -> None:
    assert refine_points([], registration_pair) == []
    point = ControlPoint(source_xy=(5.0, 6.0), reference_xy=(7.0, 8.0), residual=0.3)
    preserved = refine_points([point], registration_pair)
    assert len(preserved) == 1
    assert preserved[0].source_xy == point.source_xy
    assert preserved[0].reference_xy == point.reference_xy
    assert preserved[0].residual == point.residual
    assert preserved[0].uncertainty is None


def test_register_is_implemented_and_fail_closed_on_empty(
    registration_pair: RegistrationPair,
) -> None:
    correspondences = CorrespondenceSet(pair_id="pair-001", matcher_id="unspecified")
    result = register(registration_pair, [], correspondences)
    assert result.transformation is None
    assert result.registered_source_uri is None
    assert result.metrics is None
    assert result.correspondences is correspondences


def test_owning_modules_fail_closed_with_the_same_callables(
    tmp_path: Path,
    source_product: LunarProduct,
    reference_product: LunarProduct,
    registration_pair: RegistrationPair,
) -> None:
    correspondences = CorrespondenceSet(pair_id="pair-001", matcher_id="unspecified")
    result = RegistrationResult(pair_id="pair-001")

    assert ingest_product is ingestion.ingest_product
    assert characterize_pair is geometry.characterize_pair
    assert preprocess is preprocessing.preprocess
    assert generate_representation is representation.generate_representation
    assert match is matching.match
    assert verify_matches is verification.verify_matches
    assert select_control_points is control_points.select_control_points
    assert refine_points is refinement.refine_points
    assert register is registration.register
    assert evaluate is evaluation.evaluate
    assert export_result is io_exports.export_result

    with pytest.raises(NotImplementedError):
        ingestion.ingest_product(tmp_path / "missing")
    characterized = geometry.characterize_pair(source_product, reference_product)
    assert characterized.characterization is not None
    assert characterized.characterization.difficulty is None
    preprocessed = preprocessing.preprocess(registration_pair)
    assert preprocessed.pair_id == registration_pair.pair_id
    assert preprocessed.source.raster_uri is None
    with pytest.raises(NotImplementedError):
        representation.generate_representation(registration_pair)
    with pytest.raises(NotImplementedError):
        matching.match(registration_pair)
    verified = verification.verify_matches(correspondences, registration_pair)
    assert verified.matches == []
    selected = control_points.select_control_points(correspondences, registration_pair)
    assert selected == []
    refined = refinement.refine_points([], registration_pair)
    assert refined == []
    registered = registration.register(registration_pair, [], correspondences)
    assert registered.transformation is None
    assert registered.correspondences is correspondences
    evaluated = evaluation.evaluate(result, registration_pair)
    assert evaluated.metrics is not None
    assert evaluated.metrics.rmse is None
    assert evaluated.metrics.inlier_count is None
    assert evaluated.metrics.inlier_ratio is None
    with pytest.raises(NotImplementedError):
        io_exports.export_result(result, registration_pair, tmp_path)
