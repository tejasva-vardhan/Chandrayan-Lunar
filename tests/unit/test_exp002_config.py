"""EXP-002 configuration tests.

The controlled-experiment claim rests on everything except the matching-view
scale policy being the EXP-000 configuration.
"""

from __future__ import annotations

from src.io.exp000.config import snapshot_software_configuration
from src.io.exp002.config import (
    EXPERIMENT_ID,
    LROC_NAC_CATALOG_GSD_METERS,
    LROC_PRODUCT_ID,
    OHRC_PRODUCT_ID,
    PAIR_MANIFEST_ID,
    VARIANT_A_ID,
    VARIANT_B_ID,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
    variant_a_matching_view_settings,
    variant_b_matching_view_settings,
)
from src.representation.settings import (
    SCALE_POLICY_COMMON_PHYSICAL_GSD,
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
)


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


def test_independent_variable_is_the_scale_policy() -> None:
    fixed = snapshot_fixed_configuration()
    variants = snapshot_variant_configuration()

    assert fixed["independent_variable"] == "matching_view_scale_policy"
    assert fixed["experiment_id"] == EXPERIMENT_ID
    assert fixed["matcher_id"] == "sift"
    assert variants[VARIANT_A_ID]["scale_policy"] == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    assert variants[VARIANT_B_ID]["scale_policy"] == SCALE_POLICY_COMMON_PHYSICAL_GSD


def test_variant_a_is_the_unvalidated_matching_view_default() -> None:
    settings = variant_a_matching_view_settings()
    assert settings.scale_policy == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    assert settings.max_pixels_per_image == 4_194_304
    assert settings.catalog_gsd_meters_by_instrument == ()


def test_variant_b_changes_only_the_scale_policy() -> None:
    baseline = variant_a_matching_view_settings()
    settings = variant_b_matching_view_settings()

    assert settings.max_pixels_per_image == baseline.max_pixels_per_image
    assert settings.downsample_method == baseline.downsample_method
    assert settings.scale_policy == SCALE_POLICY_COMMON_PHYSICAL_GSD
    assert settings.catalog_gsd_meters_by_instrument == (
        ("LRO_NAC", LROC_NAC_CATALOG_GSD_METERS),
    )
    assert LROC_NAC_CATALOG_GSD_METERS == 0.5


def test_primary_pair_is_the_exp000_pair() -> None:
    baseline = snapshot_software_configuration()
    assert PAIR_MANIFEST_ID == baseline["pair_manifest_id"]
    assert OHRC_PRODUCT_ID == "ch2_ohr_ncp_20210402T0546284043_d_img_d18"
    assert LROC_PRODUCT_ID == "M150368601RC"


def test_registration_cap_is_not_raised() -> None:
    fixed = snapshot_fixed_configuration()
    assert fixed["registration"]["max_output_pixels"] == 16_777_216
