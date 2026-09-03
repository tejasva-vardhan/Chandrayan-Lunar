"""EXP-005 configuration tests.

The controlled-experiment claim rests on everything except refinement
method_id being the EXP-000 / EXP-001 SIFT configuration.
"""

from __future__ import annotations

from src.io.exp000.config import snapshot_software_configuration
from src.io.exp001.config import PAIR_REGISTRY
from src.io.exp005.config import (
    EXPECTED_PAIR_02_STRIDES,
    EXPERIMENT_ID,
    LROC_PRODUCT_ID,
    METHOD_IDENTITY,
    METHOD_ZNCC,
    OHRC_PRODUCT_ID,
    PAIR_MANIFEST_ID,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_METHOD_ID,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
    variant_a_refinement_settings,
    variant_b_refinement_settings,
)
from src.refinement.settings import unvalidated_software_defaults


def test_fixed_configuration_inherits_every_exp000_stage_setting() -> None:
    baseline = snapshot_software_configuration()
    fixed = snapshot_fixed_configuration()

    for key in (
        "preprocessing",
        "matching_view",
        "sift",
        "verification",
        "control_points",
        "registration",
        "evaluation",
    ):
        assert fixed[key] == baseline[key], f"{key} diverged from EXP-000"

    for key in (
        "window_radius",
        "search_radius",
        "min_valid_pixel_fraction",
        "min_peak_zncc",
        "fine_half_width",
        "fine_step",
    ):
        assert fixed["refinement"][key] == baseline["refinement"][key]
    assert "method_id" not in fixed["refinement"]


def test_independent_variable_is_refinement_method_id() -> None:
    fixed = snapshot_fixed_configuration()
    variants = snapshot_variant_configuration()

    assert fixed["independent_variable"] == "refinement_method_id"
    assert fixed["matching_view_held_fixed"] is True
    assert fixed["experiment_id"] == EXPERIMENT_ID
    assert fixed["matcher_id"] == "sift"
    assert variants[VARIANT_A_ID]["method_id"] == METHOD_IDENTITY
    assert variants[VARIANT_B_ID]["method_id"] == METHOD_ZNCC
    assert VARIANT_METHOD_ID == {
        VARIANT_A_ID: METHOD_IDENTITY,
        VARIANT_B_ID: METHOD_ZNCC,
    }


def test_variant_settings_reuse_existing_methods() -> None:
    identity = variant_a_refinement_settings()
    zncc = variant_b_refinement_settings()
    defaults = unvalidated_software_defaults()

    assert identity.method_id == METHOD_IDENTITY
    assert zncc.method_id == METHOD_ZNCC
    assert zncc == defaults
    assert identity.window_radius == defaults.window_radius
    assert identity.search_radius == defaults.search_radius
    assert identity.min_peak_zncc == defaults.min_peak_zncc


def test_pair_is_exp001_pair_02() -> None:
    entry = PAIR_REGISTRY[PAIR_MANIFEST_ID]
    assert PAIR_MANIFEST_ID == "pair_02_mid_equatorial"
    assert OHRC_PRODUCT_ID == entry["ohrc_product_id"]
    assert LROC_PRODUCT_ID == entry["lroc_product_id"]
    assert OHRC_PRODUCT_ID == "ch2_ohr_ncp_20250612T2229094979_d_img_d18"
    assert LROC_PRODUCT_ID == "M1504316436RC"
    assert EXPECTED_PAIR_02_STRIDES == {"ohrc": 16, "lroc": 8}


def test_registration_cap_is_not_raised() -> None:
    fixed = snapshot_fixed_configuration()
    assert fixed["registration"]["max_output_pixels"] == 16_777_216
