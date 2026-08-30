from pathlib import Path

import pytest

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


def test_all_scientific_operations_are_unimplemented(
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
        verify_matches(correspondences, registration_pair)
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
