"""Tests for the matching-view scale policy added for EXP-002.

Software validation only. Not lunar accuracy or SIH evidence.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from src.models import LunarProduct, RegistrationPair
from src.models.common import ImageDimensions
from src.representation import (
    MatchingViewSettings,
    generate_representation,
    generate_representation_with_settings,
)
from src.representation._matching_view import (
    common_scale_stride,
    determine_matching_view,
    determine_pair_matching_views,
    resolve_matching_gsd,
    stride_for_shape,
)
from src.representation.settings import (
    SCALE_POLICY_COMMON_PHYSICAL_GSD,
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
)


def _dims(height: int, width: int) -> ImageDimensions:
    return ImageDimensions(width_px=width, height_px=height, band_count=1)


def _product(
    product_id: str,
    instrument: str,
    height: int,
    width: int,
    *,
    gsd_meters: float | None = None,
    raster_uri: str | None = "unused.npy",
) -> LunarProduct:
    return LunarProduct(
        product_id=product_id,
        instrument=instrument,
        dimensions=_dims(height, width),
        gsd_meters=gsd_meters,
        raster_uri=raster_uri,
    )


def test_default_settings_remain_per_image_pixel_budget() -> None:
    settings = MatchingViewSettings()
    assert settings.scale_policy == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    assert settings.max_pixels_per_image == 4_194_304
    assert settings.downsample_method == "stride_decimation"
    assert settings.catalog_gsd_meters_by_instrument == ()


def test_per_image_policy_ignores_gsd_difference() -> None:
    source = _product("s", "OHRC", 96, 96, gsd_meters=0.25)
    reference = _product("r", "LRO_NAC", 96, 96, gsd_meters=0.5)
    settings = MatchingViewSettings(max_pixels_per_image=1_024)
    source_view, reference_view = determine_pair_matching_views(source, reference, settings)

    assert source_view["stride"] == reference_view["stride"] == 3
    assert "effective_gsd_meters" not in source_view
    assert "scale_policy" not in source_view


def test_common_scale_coarsens_the_finer_gsd_image() -> None:
    source = _product("s", "OHRC", 96, 96, gsd_meters=0.25)
    reference = _product("r", "LRO_NAC", 96, 96, gsd_meters=0.5)
    settings = MatchingViewSettings(
        max_pixels_per_image=1_024,
        scale_policy=SCALE_POLICY_COMMON_PHYSICAL_GSD,
    )
    source_view, reference_view = determine_pair_matching_views(source, reference, settings)

    assert source_view["stride"] == 6
    assert reference_view["stride"] == 3
    assert source_view["matching_shape"] == [16, 16]
    assert reference_view["matching_shape"] == [32, 32]
    assert source_view["effective_gsd_meters"] == pytest.approx(1.5)
    assert reference_view["effective_gsd_meters"] == pytest.approx(1.5)
    assert source_view["gsd_source"] == "ingested_lunar_product_gsd_meters"
    assert source_view["pixel_budget_stride"] == 3


def test_common_scale_never_exceeds_the_pixel_budget() -> None:
    source = _product("s", "OHRC", 90, 90, gsd_meters=0.25)
    reference = _product("r", "LRO_NAC", 90, 90, gsd_meters=0.5)
    settings = MatchingViewSettings(
        max_pixels_per_image=1_024,
        scale_policy=SCALE_POLICY_COMMON_PHYSICAL_GSD,
    )
    source_view, reference_view = determine_pair_matching_views(source, reference, settings)
    for view in (source_view, reference_view):
        height, width = view["matching_shape"]
        assert int(height) * int(width) <= 1_024


def test_common_scale_requires_gsd_and_does_not_invent_one() -> None:
    source = _product("s", "OHRC", 64, 64, gsd_meters=0.26)
    reference = _product("r", "LRO_NAC", 64, 64, gsd_meters=None)
    settings = MatchingViewSettings(scale_policy=SCALE_POLICY_COMMON_PHYSICAL_GSD)
    with pytest.raises(ValueError, match="SPICE is not used"):
        determine_pair_matching_views(source, reference, settings)


def test_catalog_gsd_is_used_only_when_ingested_gsd_is_missing() -> None:
    source = _product("s", "OHRC", 96, 96, gsd_meters=0.25)
    reference = _product("r", "LRO_NAC", 96, 96, gsd_meters=None)
    settings = MatchingViewSettings(
        max_pixels_per_image=1_024,
        scale_policy=SCALE_POLICY_COMMON_PHYSICAL_GSD,
        catalog_gsd_meters_by_instrument=(("LRO_NAC", 0.5),),
    )
    source_view, reference_view = determine_pair_matching_views(source, reference, settings)

    assert source_view["gsd_source"] == "ingested_lunar_product_gsd_meters"
    assert reference_view["gsd_source"] == "catalog_gsd_meters_by_instrument"
    assert reference_view["gsd_meters"] == pytest.approx(0.5)
    assert source_view["stride"] == 6
    assert reference_view["stride"] == 3
    assert reference.gsd_meters is None


def test_ingested_gsd_wins_over_catalog_fallback() -> None:
    product = _product("r", "LRO_NAC", 64, 64, gsd_meters=0.8)
    settings = MatchingViewSettings(catalog_gsd_meters_by_instrument=(("LRO_NAC", 0.5),))
    gsd, origin = resolve_matching_gsd(product, settings)
    assert gsd == pytest.approx(0.8)
    assert origin == "ingested_lunar_product_gsd_meters"


def test_single_product_helper_rejects_pair_aware_policy() -> None:
    product = _product("s", "OHRC", 64, 64, gsd_meters=0.26)
    settings = MatchingViewSettings(scale_policy=SCALE_POLICY_COMMON_PHYSICAL_GSD)
    with pytest.raises(ValueError, match="pair-aware"):
        determine_matching_view(product, settings)


def test_pair_01_catalog_gsd_selects_the_exp000_integer_strides() -> None:
    """With OHRC 0.26 m/px and LROC catalog 0.5 m/px the budget strides already
    equalise physical scale, so common-scale must not invent a different pair.
    """

    source = _product("ohrc", "OHRC", 78_175, 12_000, gsd_meters=0.26)
    reference = _product("lroc", "LRO_NAC", 52_224, 5_064, gsd_meters=None)
    budget = 4_194_304
    assert stride_for_shape(78_175, 12_000, budget) == 15
    assert stride_for_shape(52_224, 5_064, budget) == 8
    settings = MatchingViewSettings(
        max_pixels_per_image=budget,
        scale_policy=SCALE_POLICY_COMMON_PHYSICAL_GSD,
        catalog_gsd_meters_by_instrument=(("LRO_NAC", 0.5),),
    )
    source_view, reference_view = determine_pair_matching_views(source, reference, settings)
    assert source_view["stride"] == 15
    assert reference_view["stride"] == 8
    assert source_view["matching_shape"] == [5212, 800]
    assert reference_view["matching_shape"] == [6528, 633]
    assert source_view["effective_gsd_meters"] == pytest.approx(3.9)
    assert reference_view["effective_gsd_meters"] == pytest.approx(4.0)


def test_common_scale_stride_is_at_least_the_budget_stride() -> None:
    assert common_scale_stride(96, 96, 0.25, 1.5, 1_024) == 6
    assert common_scale_stride(96, 96, 0.5, 1.5, 1_024) == 3


def test_generate_representation_default_path_does_not_require_gsd() -> None:
    arr = np.arange(96 * 96, dtype=np.uint16).reshape(96, 96)
    with tempfile.TemporaryDirectory() as tmp:
        src_path = os.path.join(tmp, "src.npy")
        ref_path = os.path.join(tmp, "ref.npy")
        np.save(src_path, arr)
        np.save(ref_path, arr)
        pair = RegistrationPair(
            pair_id="default-scale",
            source=_product("s", "OHRC", 96, 96, gsd_meters=0.25, raster_uri=src_path),
            reference=_product(
                "r", "LRO_NAC", 96, 96, gsd_meters=None, raster_uri=ref_path
            ),
        )
        result = generate_representation_with_settings(
            pair, MatchingViewSettings(max_pixels_per_image=1_024)
        )
        default = generate_representation(pair)

    source_view = result.metadata["source_matching_view"]
    reference_view = result.metadata["reference_matching_view"]
    assert source_view["stride"] == reference_view["stride"] == 3
    assert "effective_gsd_meters" not in source_view
    assert default.metadata["source_matching_view"]["stride"] == 1


def test_generate_representation_common_scale_decimates_arrays() -> None:
    arr = np.arange(96 * 96, dtype=np.uint16).reshape(96, 96)
    with tempfile.TemporaryDirectory() as tmp:
        src_path = os.path.join(tmp, "src.npy")
        ref_path = os.path.join(tmp, "ref.npy")
        np.save(src_path, arr)
        np.save(ref_path, arr)
        pair = RegistrationPair(
            pair_id="common-scale",
            source=_product("s", "OHRC", 96, 96, gsd_meters=0.25, raster_uri=src_path),
            reference=_product(
                "r", "LRO_NAC", 96, 96, gsd_meters=0.5, raster_uri=ref_path
            ),
        )
        result = generate_representation_with_settings(
            pair,
            MatchingViewSettings(
                max_pixels_per_image=1_024,
                scale_policy=SCALE_POLICY_COMMON_PHYSICAL_GSD,
            ),
        )

    assert result.array.shape == (16, 16)
    assert result.metadata["reference_array"].shape == (32, 32)
    assert result.metadata["source_matching_view"]["stride"] == 6
    assert result.metadata["reference_matching_view"]["stride"] == 3
