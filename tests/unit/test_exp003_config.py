"""EXP-003 configuration tests.

The controlled-experiment claim rests on everything except the LROC
matching-view relative stride being the EXP-000 configuration.
"""

from __future__ import annotations

from src.io.exp000.config import snapshot_software_configuration
from src.io.exp003.config import (
    EXPECTED_PAIR_01_STRIDES,
    EXPERIMENT_ID,
    LROC_INSTRUMENT,
    LROC_PRODUCT_ID,
    OHRC_INSTRUMENT,
    OHRC_PRODUCT_ID,
    PAIR_MANIFEST_ID,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_B_LROC_RELATIVE_STRIDE_FACTOR,
    VARIANT_C_ID,
    VARIANT_C_LROC_RELATIVE_STRIDE_FACTOR,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
    variant_a_matching_view_settings,
    variant_b_matching_view_settings,
    variant_c_matching_view_settings,
)
from src.representation.settings import SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET


def test_fixed_configuration_inherits_every_exp000_stage_setting() -> None:
    baseline = snapshot_software_configuration()
    fixed = snapshot_fixed_configuration()

    for key in (
        "preprocessing",
        "matching_view",
        "sift",
        "verification",
        "control_points",
        "refinement",
        "registration",
        "evaluation",
    ):
        assert fixed[key] == baseline[key], f"{key} diverged from EXP-000"


def test_independent_variable_is_the_lroc_relative_stride() -> None:
    fixed = snapshot_fixed_configuration()
    variants = snapshot_variant_configuration()

    assert fixed["independent_variable"] == "lroc_matching_view_relative_stride_factor"
    assert fixed["ohrc_held_fixed"] is True
    assert fixed["experiment_id"] == EXPERIMENT_ID
    assert fixed["matcher_id"] == "sift"
    assert variants[VARIANT_A_ID]["relative_stride_factor_by_instrument"] == []
    assert variants[VARIANT_B_ID]["relative_stride_factor_by_instrument"][0]["instrument"] == (
        LROC_INSTRUMENT
    )
    assert variants[VARIANT_B_ID]["relative_stride_factor_by_instrument"][0]["factor"] == (
        VARIANT_B_LROC_RELATIVE_STRIDE_FACTOR
    )
    assert variants[VARIANT_C_ID]["relative_stride_factor_by_instrument"][0]["factor"] == (
        VARIANT_C_LROC_RELATIVE_STRIDE_FACTOR
    )


def test_variant_a_is_the_unvalidated_matching_view_default() -> None:
    settings = variant_a_matching_view_settings()
    assert settings.scale_policy == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    assert settings.max_pixels_per_image == 4_194_304
    assert settings.relative_stride_factor_by_instrument == ()


def test_variants_b_and_c_change_only_the_lroc_relative_stride() -> None:
    baseline = variant_a_matching_view_settings()
    variant_b = variant_b_matching_view_settings()
    variant_c = variant_c_matching_view_settings()

    for settings in (variant_b, variant_c):
        assert settings.max_pixels_per_image == baseline.max_pixels_per_image
        assert settings.downsample_method == baseline.downsample_method
        assert settings.scale_policy == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
        assert settings.catalog_gsd_meters_by_instrument == ()
        instruments = [name for name, _factor in settings.relative_stride_factor_by_instrument]
        assert instruments == [LROC_INSTRUMENT]
        assert OHRC_INSTRUMENT not in instruments

    assert variant_b.relative_stride_factor_by_instrument == (
        (LROC_INSTRUMENT, VARIANT_B_LROC_RELATIVE_STRIDE_FACTOR),
    )
    assert variant_c.relative_stride_factor_by_instrument == (
        (LROC_INSTRUMENT, VARIANT_C_LROC_RELATIVE_STRIDE_FACTOR),
    )


def test_expected_pair_01_strides_vary_lroc_only() -> None:
    assert EXPECTED_PAIR_01_STRIDES[VARIANT_A_ID] == {"ohrc": 15, "lroc": 8}
    assert EXPECTED_PAIR_01_STRIDES[VARIANT_B_ID] == {"ohrc": 15, "lroc": 16}
    assert EXPECTED_PAIR_01_STRIDES[VARIANT_C_ID] == {"ohrc": 15, "lroc": 4}


def test_primary_pair_is_the_exp000_pair() -> None:
    baseline = snapshot_software_configuration()
    assert PAIR_MANIFEST_ID == baseline["pair_manifest_id"]
    assert OHRC_PRODUCT_ID == "ch2_ohr_ncp_20210402T0546284043_d_img_d18"
    assert LROC_PRODUCT_ID == "M150368601RC"


def test_registration_cap_is_not_raised() -> None:
    fixed = snapshot_fixed_configuration()
    assert fixed["registration"]["max_output_pixels"] == 16_777_216
