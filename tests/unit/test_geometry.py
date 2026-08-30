"""Unit tests for pair characterization. Not lunar validation."""

from __future__ import annotations

import ast
import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from src.geometry import characterize_pair
from src.geometry.adapters import ProductGeometry, geometry_from_product
from src.geometry.characterize import (
    build_characterization,
    characterize_pair_with_provider,
)
from src.geometry.difficulty import (
    FLAG_ACQUISITION_TIME_DIFFERENCE_AVAILABLE,
    FLAG_ILLUMINATION_DIFFERENCE_AVAILABLE,
    FLAG_MULTIMODAL_PAIR,
    FLAG_SCALE_DIFFERENCE_AVAILABLE,
    FLAG_VIEWING_GEOMETRY_DIFFERENCE_AVAILABLE,
    categorical_difficulty,
    quality_flags,
)
from src.geometry.measures import (
    acquisition_time_difference_seconds,
    angular_separation_degrees,
    expected_overlap,
    gsd_ratio,
    image_dimensions,
    pair_id_for,
    pair_modality_label,
    sensor_pair_label,
    sun_angle_difference_degrees,
    viewing_geometry_difference,
)
from src.geometry.rasters import (
    array_valid_pixel_ratio,
    intensity_standard_deviation,
    pair_valid_pixel_ratio,
    robust_contrast_iqr,
)
from src.models import LunarProduct, RegistrationPair
from src.models.common import Coordinates, ImageDimensions
from src.pipeline.operations import characterize_pair as pipeline_characterize


def _product(**overrides: object) -> LunarProduct:
    values: dict[str, object] = {"product_id": "src", "instrument": "OHRC"}
    values.update(overrides)
    return LunarProduct(**values)  # type: ignore[arg-type]


def _geometry(**overrides: object) -> ProductGeometry:
    values: dict[str, object] = {
        "product_id": "src",
        "instrument": "OHRC",
        "mission": None,
        "width_px": None,
        "height_px": None,
        "band_count": None,
        "gsd_meters": None,
        "acquisition_time": None,
        "product_valid_pixel_ratio": None,
        "raster_uri": None,
        "mask_uri": None,
        "sun_vector": None,
        "look_vector": None,
        "terrain_available": False,
    }
    values.update(overrides)
    return ProductGeometry(**values)  # type: ignore[arg-type]


def test_characterize_pair_is_the_frozen_pipeline_callable() -> None:
    assert pipeline_characterize is characterize_pair


def test_valid_image_dimensions_are_extracted() -> None:
    assert image_dimensions(128, 64) == (128, 64)
    product = _product(dimensions=ImageDimensions(width_px=320, height_px=240, band_count=1))
    geometry = geometry_from_product(product)
    assert geometry.width_px == 320
    assert geometry.height_px == 240
    assert geometry.band_count == 1


def test_invalid_and_missing_dimensions_are_not_fabricated() -> None:
    assert image_dimensions(None, 10) is None
    assert image_dimensions(10, None) is None
    assert image_dimensions(0, 10) is None
    assert image_dimensions(-4, 10) is None
    assert image_dimensions(10, 0) is None
    assert image_dimensions(True, 8) is None
    geometry = geometry_from_product(_product())
    assert geometry.width_px is None
    assert geometry.height_px is None


def test_valid_gsd_ratio_uses_source_over_reference() -> None:
    # Interface Freeze v1: source GSD / reference GSD, not the reverse.
    assert gsd_ratio(10.0, 5.0) == 2.0
    assert gsd_ratio(5.0, 10.0) == 0.5
    source = _product(product_id="s", gsd_meters=2.0)
    reference = _product(product_id="r", instrument="LRO_NAC", gsd_meters=1.0)
    pair = characterize_pair(source, reference)
    assert pair.characterization is not None
    assert pair.characterization.gsd_ratio == 2.0


def test_missing_gsd_leaves_ratio_unavailable() -> None:
    assert gsd_ratio(None, 1.0) is None
    assert gsd_ratio(1.0, None) is None
    assert gsd_ratio(None, None) is None
    pair = characterize_pair(_product(product_id="s"), _product(product_id="r", instrument="TMC-2"))
    assert pair.characterization is not None
    assert pair.characterization.gsd_ratio is None
    assert FLAG_SCALE_DIFFERENCE_AVAILABLE not in pair.characterization.quality_flags


def test_invalid_gsd_does_not_produce_a_ratio() -> None:
    assert gsd_ratio(0.0, 1.0) is None
    assert gsd_ratio(-2.0, 1.0) is None
    assert gsd_ratio(1.0, 0.0) is None
    assert gsd_ratio(float("inf"), 1.0) is None
    assert gsd_ratio(1.0, float("nan")) is None
    assert gsd_ratio(float("-inf"), float("inf")) is None


def test_finite_and_non_finite_geometry_metadata() -> None:
    assert angular_separation_degrees((1.0, 0.0, 0.0), (float("nan"), 0.0, 0.0)) is None
    assert angular_separation_degrees((1.0, 0.0, 0.0), (float("inf"), 0.0, 0.0)) is None
    assert angular_separation_degrees((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)) is None
    assert expected_overlap(float("nan")) is None
    assert expected_overlap(float("inf")) is None
    assert expected_overlap(-0.1) is None
    assert expected_overlap(1.1) is None
    assert acquisition_time_difference_seconds(None, datetime(2020, 1, 1, tzinfo=UTC)) is None


def test_known_angular_separation_from_vector_metadata() -> None:
    assert angular_separation_degrees((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)) == pytest.approx(0.0)
    assert angular_separation_degrees((2.0, 0.0, 0.0), (5.0, 0.0, 0.0)) == pytest.approx(0.0)
    assert angular_separation_degrees((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)) == pytest.approx(90.0)
    assert angular_separation_degrees((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)) == pytest.approx(180.0)
    characterization = build_characterization(
        _geometry(sun_vector=(1.0, 0.0, 0.0)),
        _geometry(product_id="ref", instrument="LRO_NAC", sun_vector=(0.0, 1.0, 0.0)),
    )
    assert characterization.sun_angle_difference_degrees == pytest.approx(90.0)
    assert FLAG_ILLUMINATION_DIFFERENCE_AVAILABLE in characterization.quality_flags


def test_missing_sun_metadata_leaves_sun_angle_unavailable() -> None:
    assert sun_angle_difference_degrees(None, (1.0, 0.0, 0.0)) is None
    pair = characterize_pair(_product(product_id="s"), _product(product_id="r", instrument="IIRS"))
    assert pair.characterization is not None
    assert pair.characterization.sun_angle_difference_degrees is None
    assert FLAG_ILLUMINATION_DIFFERENCE_AVAILABLE not in pair.characterization.quality_flags
    product_geometry = geometry_from_product(_product())
    assert product_geometry.sun_vector is None


def test_viewing_geometry_difference_stays_unavailable() -> None:
    assert viewing_geometry_difference((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)) is None
    characterization = build_characterization(
        _geometry(look_vector=(0.0, 0.0, 1.0)),
        _geometry(product_id="ref", look_vector=(1.0, 0.0, 0.0)),
    )
    assert characterization.viewing_geometry_difference is None
    assert FLAG_VIEWING_GEOMETRY_DIFFERENCE_AVAILABLE not in characterization.quality_flags


def test_valid_pixel_ratio_of_finite_samples() -> None:
    array = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    assert array_valid_pixel_ratio(array) == 1.0
    partial = np.array([[1.0, math.nan], [3.0, 4.0]], dtype=float)
    assert array_valid_pixel_ratio(partial) == pytest.approx(0.75)
    masked = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    mask = np.array([[True, False], [True, True]])
    assert array_valid_pixel_ratio(masked, mask) == pytest.approx(0.75)


def test_nan_inf_and_zero_raster_handling() -> None:
    array = np.array([[0.0, math.nan], [math.inf, 1.0]], dtype=float)
    # Zeros are valid. NaN and Inf are not.
    assert array_valid_pixel_ratio(array) == pytest.approx(0.5)
    zeros = np.zeros((2, 2), dtype=float)
    assert array_valid_pixel_ratio(zeros) == 1.0


def test_empty_raster_valid_pixel_ratio_is_unavailable() -> None:
    assert array_valid_pixel_ratio(None) is None
    assert array_valid_pixel_ratio(np.array([], dtype=float)) is None
    assert array_valid_pixel_ratio(np.zeros((0, 4), dtype=float)) is None
    mismatched = np.ones((2, 2), dtype=float)
    assert array_valid_pixel_ratio(mismatched, np.ones((1, 2), dtype=bool)) is None


def test_pair_valid_pixel_ratio_does_not_combine_product_ratios() -> None:
    assert pair_valid_pixel_ratio(source_product_ratio=0.9, reference_product_ratio=0.8) is None
    source = _product(product_id="s", valid_pixel_ratio=0.9)
    reference = _product(product_id="r", instrument="TMC-2", valid_pixel_ratio=0.1)
    pair = characterize_pair(source, reference)
    assert pair.characterization is not None
    assert pair.characterization.valid_pixel_ratio is None
    numeric_overlap = np.array([[1.0, math.nan], [1.0, 1.0]], dtype=float)
    assert pair_valid_pixel_ratio(overlap_mask=numeric_overlap) == pytest.approx(0.75)
    assert pair_valid_pixel_ratio(overlap_mask=np.array([[True, False], [True, True]])) is None


def test_deterministic_texture_statistics() -> None:
    constant = np.array([[3.0, 3.0], [3.0, 3.0]], dtype=float)
    assert intensity_standard_deviation(constant) == pytest.approx(0.0)
    two = np.array([0.0, 2.0], dtype=float)
    assert intensity_standard_deviation(two) == pytest.approx(1.0)
    assert robust_contrast_iqr(np.array([1.0, 2.0, 3.0, 4.0], dtype=float)) == pytest.approx(1.5)
    with_nan = np.array([1.0, math.nan, 1.0, math.inf], dtype=float)
    assert intensity_standard_deviation(with_nan) == pytest.approx(0.0)
    assert intensity_standard_deviation(np.array([math.nan, math.inf])) is None
    assert intensity_standard_deviation(np.array([], dtype=float)) is None
    pair = characterize_pair(_product(product_id="s"), _product(product_id="r", instrument="IIRS"))
    assert pair.characterization is not None
    assert pair.characterization.texture_contrast is None


def test_missing_modality_is_not_invented() -> None:
    assert pair_modality_label(None, "OHRC") is None
    assert pair_modality_label("OHRC", None) is None
    assert pair_modality_label("", "OHRC") is None
    assert sensor_pair_label(None, None) is None


def test_explicit_modality_is_preserved() -> None:
    pair = characterize_pair(
        _product(product_id="s", instrument="OHRC"),
        _product(product_id="r", instrument="IIRS"),
    )
    assert pair.characterization is not None
    assert pair.characterization.sensor_pair == "OHRC/IIRS"
    assert pair.characterization.modality == "OHRC/IIRS"
    assert FLAG_MULTIMODAL_PAIR in pair.characterization.quality_flags
    same = characterize_pair(
        _product(product_id="s", instrument="OHRC"),
        _product(product_id="r", instrument="OHRC"),
    )
    assert same.characterization is not None
    assert same.characterization.modality == "OHRC/OHRC"
    assert FLAG_MULTIMODAL_PAIR not in same.characterization.quality_flags


def test_missing_overlap_is_not_invented_from_bbox() -> None:
    overlapping = Coordinates(crs="IAU_Moon", bbox=(0.0, 0.0, 2.0, 2.0))
    source = _product(product_id="s", coordinates=overlapping)
    reference = _product(product_id="r", instrument="LRO_NAC", coordinates=overlapping)
    pair = characterize_pair(source, reference)
    assert pair.characterization is not None
    assert pair.characterization.expected_overlap is None
    assert pair.overlap_mask_uri is None
    ignored = expected_overlap(
        None, source_bbox=overlapping.bbox, reference_bbox=overlapping.bbox
    )
    assert ignored is None
    assert expected_overlap(0.4) == pytest.approx(0.4)


def test_pair_characterization_is_deterministic() -> None:
    source = _product(
        product_id="s",
        instrument="OHRC",
        gsd_meters=1.5,
        acquisition_time=datetime(2020, 1, 1, tzinfo=UTC),
        dimensions=ImageDimensions(width_px=16, height_px=8),
    )
    reference = _product(
        product_id="r",
        instrument="TMC-2",
        gsd_meters=3.0,
        acquisition_time=datetime(2020, 1, 2, tzinfo=UTC),
        dimensions=ImageDimensions(width_px=32, height_px=16),
    )
    first = characterize_pair(source, reference)
    second = characterize_pair(source, reference)
    assert first.model_dump() == second.model_dump()
    assert first.characterization is not None
    assert first.characterization.quality_flags == second.characterization.quality_flags


def test_characterize_pair_does_not_invent_scientific_values() -> None:
    source = _product(product_id="src-001", instrument="OHRC", mission="Chandrayaan-2")
    reference = _product(product_id="ref-001", instrument="LRO_NAC", mission="LRO")
    before_source = source.model_dump()
    before_reference = reference.model_dump()
    pair = characterize_pair(source, reference)
    assert isinstance(pair, RegistrationPair)
    assert pair.pair_id == pair_id_for("src-001", "ref-001")
    assert pair.source == source
    assert pair.reference == reference
    assert source.model_dump() == before_source
    assert reference.model_dump() == before_reference
    characterization = pair.characterization
    assert characterization is not None
    assert characterization.gsd_ratio is None
    assert characterization.acquisition_time_difference_seconds is None
    assert characterization.sun_angle_difference_degrees is None
    assert characterization.viewing_geometry_difference is None
    assert characterization.expected_overlap is None
    assert characterization.valid_pixel_ratio is None
    assert characterization.texture_contrast is None
    assert characterization.difficulty is None
    assert pair.overlap_mask_uri is None
    assert characterization.sensor_pair == "OHRC/LRO_NAC"
    assert characterization.modality == "OHRC/LRO_NAC"


def test_difficulty_does_not_create_scientific_thresholds() -> None:
    assert categorical_difficulty() is None
    flags = quality_flags(
        gsd_ratio=10.0,
        sun_angle_difference_degrees=90.0,
        viewing_geometry_difference=None,
        source_instrument="OHRC",
        reference_instrument="IIRS",
        acquisition_time_difference_seconds=60.0,
    )
    assert "easy" not in flags
    assert "normal" not in flags
    assert "difficult" not in flags
    assert "hard" not in flags
    assert "strong_scale_difference" not in flags
    assert "low_valid_pixel_quality" not in flags
    assert flags == [
        FLAG_SCALE_DIFFERENCE_AVAILABLE,
        FLAG_ILLUMINATION_DIFFERENCE_AVAILABLE,
        FLAG_MULTIMODAL_PAIR,
        FLAG_ACQUISITION_TIME_DIFFERENCE_AVAILABLE,
    ]
    pair = characterize_pair(
        _product(product_id="s", gsd_meters=50.0),
        _product(product_id="r", instrument="LRO_NAC", gsd_meters=0.5),
    )
    assert pair.characterization is not None
    assert pair.characterization.difficulty is None
    assert pair.characterization.gsd_ratio == pytest.approx(100.0)


def test_acquisition_time_difference_when_both_times_exist() -> None:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    later = start + timedelta(seconds=90)
    assert acquisition_time_difference_seconds(later, start) == pytest.approx(90.0)
    naive = datetime(2020, 1, 1)
    assert acquisition_time_difference_seconds(start, naive) is None
    pair = characterize_pair(
        _product(product_id="s", acquisition_time=start),
        _product(product_id="r", instrument="TMC-2", acquisition_time=later),
    )
    assert pair.characterization is not None
    assert pair.characterization.acquisition_time_difference_seconds == pytest.approx(90.0)


def test_spice_provider_extension_point_does_not_change_frozen_signature(
    source_product: LunarProduct, reference_product: LunarProduct
) -> None:
    class _SunProvider:
        def for_product(self, product: LunarProduct) -> ProductGeometry:
            base = geometry_from_product(product)
            if product.product_id == source_product.product_id:
                return replace(base, sun_vector=(1.0, 0.0, 0.0))
            return replace(base, sun_vector=(0.0, 1.0, 0.0))

    injected = characterize_pair_with_provider(source_product, reference_product, _SunProvider())
    default = characterize_pair(source_product, reference_product)
    assert injected.characterization is not None
    assert injected.characterization.sun_angle_difference_degrees == pytest.approx(90.0)
    assert default.characterization is not None
    assert default.characterization.sun_angle_difference_degrees is None
    assert characterize_pair.__code__.co_varnames[:2] == ("source", "reference")
    assert characterize_pair.__code__.co_argcount == 2


def test_existing_pipeline_integration(
    source_product: LunarProduct, reference_product: LunarProduct
) -> None:
    pair = pipeline_characterize(source_product, reference_product)
    assert isinstance(pair, RegistrationPair)
    assert pair.source.product_id == source_product.product_id
    assert pair.reference.product_id == reference_product.product_id
    assert pair.characterization is not None
    assert pair.characterization.difficulty is None


def test_geometry_package_does_not_import_spice_or_routing() -> None:
    geometry_root = Path(__file__).resolve().parents[2] / "src" / "geometry"
    forbidden = {"spiceypy", "spice"}
    offenders: list[str] = []
    for py_file in geometry_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        overlap = roots & forbidden
        if overlap:
            offenders.append(f"{py_file.name}: {sorted(overlap)}")
        text = py_file.read_text(encoding="utf-8")
        if "src.routing" in text or "src.matching" in text:
            offenders.append(f"{py_file.name}: routing/matching import")
    assert offenders == []
