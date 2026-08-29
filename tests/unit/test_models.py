from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models import (
    ControlPoint,
    Correspondence,
    CorrespondenceSet,
    LunarProduct,
    PairCharacterization,
    RegistrationMetrics,
    RegistrationPair,
    RegistrationResult,
    TransformationModel,
)


def test_lunar_product_requires_identity() -> None:
    with pytest.raises(ValidationError):
        LunarProduct(instrument="OHRC")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        LunarProduct(product_id="p1")  # type: ignore[call-arg]


def test_lunar_product_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        LunarProduct(product_id="p1", instrument="OHRC", invented_accuracy=0.1)


def test_lunar_product_optional_scientific_fields_default_unset() -> None:
    product = LunarProduct(product_id="p1", instrument="OHRC")
    assert product.gsd_meters is None
    assert product.acquisition_time is None
    assert product.valid_pixel_ratio is None


def test_lunar_product_rejects_invalid_ratios() -> None:
    with pytest.raises(ValidationError):
        LunarProduct(product_id="p1", instrument="OHRC", valid_pixel_ratio=1.5)


def test_lunar_product_json_roundtrip() -> None:
    product = LunarProduct(
        product_id="p1",
        instrument="TMC-2",
        acquisition_time=datetime(2020, 1, 1, tzinfo=UTC),
    )
    restored = LunarProduct.model_validate_json(product.model_dump_json())
    assert restored == product


def test_registration_pair_requires_source_and_reference() -> None:
    with pytest.raises(ValidationError):
        RegistrationPair(pair_id="pair-1")  # type: ignore[call-arg]


def test_pair_characterization_allows_unset_difficulty() -> None:
    pair = RegistrationPair(
        pair_id="pair-1",
        source=LunarProduct(product_id="s", instrument="OHRC"),
        reference=LunarProduct(product_id="r", instrument="LRO_NAC"),
        characterization=PairCharacterization(),
    )
    assert pair.characterization is not None
    assert pair.characterization.difficulty is None


def test_pair_characterization_rejects_unknown_difficulty() -> None:
    with pytest.raises(ValidationError):
        PairCharacterization(difficulty="impossible")  # type: ignore[arg-type]


def test_registration_pair_json_roundtrip() -> None:
    pair = RegistrationPair(
        pair_id="pair-1",
        source=LunarProduct(product_id="s", instrument="OHRC"),
        reference=LunarProduct(product_id="r", instrument="IIRS"),
    )
    restored = RegistrationPair.model_validate_json(pair.model_dump_json())
    assert restored == pair


def test_correspondence_set_defaults_to_empty_matches() -> None:
    correspondences = CorrespondenceSet(pair_id="pair-1", matcher_id="unspecified")
    assert correspondences.matches == []


def test_correspondence_rejects_confidence_outside_unit_interval() -> None:
    with pytest.raises(ValidationError):
        Correspondence(source_xy=(0.0, 0.0), reference_xy=(1.0, 1.0), confidence=2.0)


def test_correspondence_set_json_roundtrip() -> None:
    correspondences = CorrespondenceSet(
        pair_id="pair-1",
        matcher_id="unspecified",
        matches=[
            Correspondence(source_xy=(1.0, 2.0), reference_xy=(3.0, 4.0), status="raw"),
        ],
    )
    restored = CorrespondenceSet.model_validate_json(correspondences.model_dump_json())
    assert restored == correspondences


def test_registration_metrics_do_not_invent_values() -> None:
    metrics = RegistrationMetrics()
    assert metrics.rmse is None
    assert metrics.inlier_count is None
    assert metrics.inlier_ratio is None


def test_registration_result_json_roundtrip() -> None:
    result = RegistrationResult(
        pair_id="pair-1",
        control_points=[ControlPoint(source_xy=(0.0, 0.0), reference_xy=(1.0, 1.0))],
        transformation=TransformationModel(model_name="unspecified"),
    )
    restored = RegistrationResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_registration_result_requires_pair_id() -> None:
    with pytest.raises(ValidationError):
        RegistrationResult()  # type: ignore[call-arg]
