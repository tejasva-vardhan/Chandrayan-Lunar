"""Tests for relative matching-view stride variants used by EXP-003.

Software validation only. Not lunar accuracy or SIH evidence.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from src.io.exp003.config import (
    EXPECTED_PAIR_01_STRIDES,
    LROC_INSTRUMENT,
    OHRC_INSTRUMENT,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_C_ID,
    variant_a_matching_view_settings,
    variant_b_matching_view_settings,
    variant_c_matching_view_settings,
)
from src.models import LunarProduct, RegistrationPair
from src.models.common import ImageDimensions
from src.representation import (
    generate_representation,
    generate_representation_with_settings,
)
from src.representation._matching_view import (
    apply_relative_stride,
    determine_pair_matching_views,
    matching_shape_for_stride,
    stride_for_shape,
)
from src.representation.settings import MatchingViewSettings


def _dims(height: int, width: int) -> ImageDimensions:
    return ImageDimensions(width_px=width, height_px=height, band_count=1)


def _product(
    product_id: str,
    instrument: str,
    height: int,
    width: int,
    *,
    raster_uri: str | None = "unused.npy",
) -> LunarProduct:
    return LunarProduct(
        product_id=product_id,
        instrument=instrument,
        dimensions=_dims(height, width),
        raster_uri=raster_uri,
    )


def test_apply_relative_stride_rounds_the_pair_01_lroc_factors() -> None:
    assert apply_relative_stride(8, 2.0) == 16
    assert apply_relative_stride(8, 0.5) == 4
    assert apply_relative_stride(8, 1.0) == 8
    assert apply_relative_stride(1, 0.5) == 1


def test_apply_relative_stride_rejects_non_positive_factors() -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        apply_relative_stride(8, 0.0)
    with pytest.raises(ValueError, match="finite and positive"):
        apply_relative_stride(8, -2.0)


def test_pair_01_variant_strides_keep_ohrc_fixed_and_change_lroc() -> None:
    source = _product("ohrc", OHRC_INSTRUMENT, 78_175, 12_000)
    reference = _product("lroc", LROC_INSTRUMENT, 52_224, 5_064)
    budget = 4_194_304
    assert stride_for_shape(78_175, 12_000, budget) == 15
    assert stride_for_shape(52_224, 5_064, budget) == 8

    views = {
        VARIANT_A_ID: determine_pair_matching_views(
            source, reference, variant_a_matching_view_settings()
        ),
        VARIANT_B_ID: determine_pair_matching_views(
            source, reference, variant_b_matching_view_settings()
        ),
        VARIANT_C_ID: determine_pair_matching_views(
            source, reference, variant_c_matching_view_settings()
        ),
    }

    for variant_id, (source_view, reference_view) in views.items():
        expected = EXPECTED_PAIR_01_STRIDES[variant_id]
        assert source_view["stride"] == expected["ohrc"]
        assert reference_view["stride"] == expected["lroc"]
        assert source_view["matching_shape"] == list(
            matching_shape_for_stride(78_175, 12_000, expected["ohrc"])
        )
        assert reference_view["matching_shape"] == list(
            matching_shape_for_stride(52_224, 5_064, expected["lroc"])
        )

    assert views[VARIANT_A_ID][0]["stride"] == views[VARIANT_B_ID][0]["stride"]
    assert views[VARIANT_A_ID][0]["stride"] == views[VARIANT_C_ID][0]["stride"]
    assert views[VARIANT_A_ID][1]["stride"] != views[VARIANT_B_ID][1]["stride"]
    assert views[VARIANT_A_ID][1]["stride"] != views[VARIANT_C_ID][1]["stride"]
    assert views[VARIANT_B_ID][1]["stride"] != views[VARIANT_C_ID][1]["stride"]

    assert "relative_stride_factor" not in views[VARIANT_A_ID][1]
    assert views[VARIANT_B_ID][1]["relative_stride_factor"] == 2.0
    assert views[VARIANT_B_ID][1]["baseline_stride"] == 8
    assert views[VARIANT_B_ID][1]["exceeds_max_pixels_per_image"] is False
    assert views[VARIANT_C_ID][1]["relative_stride_factor"] == 0.5
    assert views[VARIANT_C_ID][1]["baseline_stride"] == 8
    assert views[VARIANT_C_ID][1]["exceeds_max_pixels_per_image"] is True


def test_relative_factor_does_not_change_ohrc_when_only_lroc_is_listed() -> None:
    source = _product("s", OHRC_INSTRUMENT, 96, 96)
    reference = _product("r", LROC_INSTRUMENT, 96, 96)
    settings = MatchingViewSettings(
        max_pixels_per_image=1_024,
        relative_stride_factor_by_instrument=((LROC_INSTRUMENT, 2.0),),
    )
    source_view, reference_view = determine_pair_matching_views(source, reference, settings)
    assert source_view["stride"] == 3
    assert reference_view["stride"] == 6
    assert "relative_stride_factor" not in source_view
    assert reference_view["relative_stride_factor"] == 2.0


def test_generate_representation_applies_relative_stride_to_arrays() -> None:
    arr = np.arange(96 * 96, dtype=np.uint16).reshape(96, 96)
    with tempfile.TemporaryDirectory() as tmp:
        src_path = os.path.join(tmp, "src.npy")
        ref_path = os.path.join(tmp, "ref.npy")
        np.save(src_path, arr)
        np.save(ref_path, arr)
        pair = RegistrationPair(
            pair_id="relative-scale",
            source=_product("s", OHRC_INSTRUMENT, 96, 96, raster_uri=src_path),
            reference=_product("r", LROC_INSTRUMENT, 96, 96, raster_uri=ref_path),
        )
        coarsened = generate_representation_with_settings(
            pair,
            MatchingViewSettings(
                max_pixels_per_image=1_024,
                relative_stride_factor_by_instrument=((LROC_INSTRUMENT, 2.0),),
            ),
        )
        finer = generate_representation_with_settings(
            pair,
            MatchingViewSettings(
                max_pixels_per_image=1_024,
                relative_stride_factor_by_instrument=((LROC_INSTRUMENT, 0.5),),
            ),
        )
        default = generate_representation(pair)

    assert coarsened.array.shape == (32, 32)
    assert coarsened.metadata["reference_array"].shape == (16, 16)
    assert finer.array.shape == (32, 32)
    assert finer.metadata["reference_array"].shape == (48, 48)
    assert default.metadata["source_matching_view"]["stride"] == 1
    assert default.metadata["reference_matching_view"]["stride"] == 1
    assert coarsened.array.shape != coarsened.metadata["reference_array"].shape
    assert finer.metadata["reference_array"].shape != coarsened.metadata["reference_array"].shape
