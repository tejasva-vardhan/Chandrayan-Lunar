"""Synthetic pair-characterization tests. Software math only — not lunar validation.

Constructed GSD values, direction vectors, and arrays check implementation
arithmetic. They are not Chandrayaan-2 / LROC results and are not SIH
evaluator evidence (D-011, D-012).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from src.geometry import characterize_pair
from src.geometry.adapters import ProductGeometry
from src.geometry.characterize import build_characterization
from src.geometry.measures import angular_separation_degrees, gsd_ratio
from src.geometry.rasters import array_valid_pixel_ratio, intensity_standard_deviation
from src.models import LunarProduct
from src.models.common import ImageDimensions

pytestmark = pytest.mark.scientific


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


def test_synthetic_gsd_ratio_matches_source_over_reference() -> None:
    # TEST ONLY constructed metres/pixel. Not a lunar GSD measurement.
    assert gsd_ratio(0.32, 0.64) == pytest.approx(0.5)
    source = LunarProduct(product_id="s", instrument="OHRC", gsd_meters=0.32)
    reference = LunarProduct(product_id="r", instrument="TMC-2", gsd_meters=0.64)
    pair = characterize_pair(source, reference)
    assert pair.characterization is not None
    assert pair.characterization.gsd_ratio == pytest.approx(0.5)


def test_synthetic_orthogonal_sun_vectors_are_90_degrees() -> None:
    # TEST ONLY unit vectors. Frame is unspecified; not a SPICE result.
    assert angular_separation_degrees((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)) == pytest.approx(90.0)
    characterization = build_characterization(
        _geometry(sun_vector=(1.0, 0.0, 0.0)),
        _geometry(product_id="ref", instrument="LRO_NAC", sun_vector=(0.0, 0.0, 1.0)),
    )
    assert characterization.sun_angle_difference_degrees == pytest.approx(90.0)


def test_synthetic_time_difference_and_dimensions_are_preserved() -> None:
    start = datetime(2019, 7, 22, 9, 0, tzinfo=UTC)
    source = LunarProduct(
        product_id="s",
        instrument="OHRC",
        dimensions=ImageDimensions(width_px=64, height_px=32),
        acquisition_time=start,
    )
    reference = LunarProduct(
        product_id="r",
        instrument="OHRC",
        dimensions=ImageDimensions(width_px=128, height_px=64),
        acquisition_time=start + timedelta(hours=2),
    )
    pair = characterize_pair(source, reference)
    assert pair.source.dimensions is not None
    assert pair.source.dimensions.width_px == 64
    assert pair.reference.dimensions is not None
    assert pair.reference.dimensions.height_px == 64
    assert pair.characterization is not None
    assert pair.characterization.acquisition_time_difference_seconds == pytest.approx(7200.0)
    assert pair.characterization.difficulty is None


def test_synthetic_valid_pixel_and_texture_math() -> None:
    # TEST ONLY constructed arrays. Not a lunar texture or mask definition.
    raster = np.array([[0.0, 1.0, math.nan], [2.0, math.inf, 3.0]], dtype=float)
    assert array_valid_pixel_ratio(raster) == pytest.approx(4.0 / 6.0)
    assert intensity_standard_deviation(np.array([4.0, 4.0, 4.0, 4.0])) == pytest.approx(0.0)
    pair = characterize_pair(
        LunarProduct(product_id="s", instrument="OHRC"),
        LunarProduct(product_id="r", instrument="IIRS"),
    )
    assert pair.characterization is not None
    assert pair.characterization.valid_pixel_ratio is None
    assert pair.characterization.texture_contrast is None
    assert pair.characterization.expected_overlap is None
