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
from src.models import CorrespondenceSet, LunarProduct, RegistrationPair, RegistrationResult
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
    source_product: LunarProduct,
    reference_product: LunarProduct,
    registration_pair: RegistrationPair,
) -> None:
    correspondences = CorrespondenceSet(pair_id="pair-001", matcher_id="unspecified")
    result = RegistrationResult(pair_id="pair-001")

    with pytest.raises(NotImplementedError):
        ingest_product(tmp_path / "missing")
    with pytest.raises(NotImplementedError):
        characterize_pair(source_product, reference_product)
    with pytest.raises(NotImplementedError):
        preprocess(registration_pair)
    with pytest.raises(NotImplementedError):
        generate_representation(registration_pair)
    with pytest.raises(NotImplementedError):
        match(registration_pair)
    with pytest.raises(NotImplementedError):
        select_control_points(correspondences, registration_pair)
    with pytest.raises(NotImplementedError):
        refine_points([], registration_pair)
    with pytest.raises(NotImplementedError):
        register(registration_pair, [], correspondences)
    with pytest.raises(NotImplementedError):
        evaluate(result, registration_pair)
    with pytest.raises(NotImplementedError):
        export_result(result, registration_pair, tmp_path)
    with pytest.raises(NotImplementedError):
        io_export_result(result, registration_pair, tmp_path)


def test_verify_matches_is_implemented_and_fail_closed_on_empty(
    registration_pair: RegistrationPair,
) -> None:
    correspondences = CorrespondenceSet(pair_id="pair-001", matcher_id="unspecified")
    result = verify_matches(correspondences, registration_pair)
    assert result.matches == []
    assert result.pair_id == correspondences.pair_id


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
    with pytest.raises(NotImplementedError):
        geometry.characterize_pair(source_product, reference_product)
    with pytest.raises(NotImplementedError):
        preprocessing.preprocess(registration_pair)
    with pytest.raises(NotImplementedError):
        representation.generate_representation(registration_pair)
    with pytest.raises(NotImplementedError):
        matching.match(registration_pair)
    verified = verification.verify_matches(correspondences, registration_pair)
    assert verified.matches == []
    with pytest.raises(NotImplementedError):
        control_points.select_control_points(correspondences, registration_pair)
    with pytest.raises(NotImplementedError):
        refinement.refine_points([], registration_pair)
    with pytest.raises(NotImplementedError):
        registration.register(registration_pair, [], correspondences)
    with pytest.raises(NotImplementedError):
        evaluation.evaluate(result, registration_pair)
    with pytest.raises(NotImplementedError):
        io_exports.export_result(result, registration_pair, tmp_path)
