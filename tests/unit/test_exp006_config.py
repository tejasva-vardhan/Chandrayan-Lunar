"""EXP-006 configuration tests.

The controlled-experiment claim rests on everything except the
correspondence-validation protocol being the EXP-000 / EXP-001 SIFT
configuration. Reciprocal matching must not appear as a SiftSettings field.
"""

from __future__ import annotations

from dataclasses import asdict

from src.io.exp000.config import snapshot_software_configuration
from src.io.exp001.config import PAIR_REGISTRY
from src.io.exp006.config import (
    EXPECTED_PAIR_01_STRIDES,
    EXPECTED_PAIR_02_STRIDES,
    EXPERIMENT_ID,
    FOLLOW_UP_PAIR_ID,
    LROC_PRODUCT_ID,
    OHRC_PRODUCT_ID,
    PRIMARY_PAIR_ID,
    PROTOCOL_ONE_WAY,
    PROTOCOL_RECIPROCAL,
    RUNTIME_FACTOR_LIMIT,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_PROTOCOL_ID,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
)
from src.matching.settings import SiftSettings


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


def test_sift_settings_do_not_grow_a_reciprocal_field() -> None:
    fixed = snapshot_fixed_configuration()
    assert "require_reciprocal" not in asdict(SiftSettings())
    assert "require_reciprocal" not in fixed["sift"]


def test_independent_variable_is_correspondence_validation_protocol() -> None:
    fixed = snapshot_fixed_configuration()
    variants = snapshot_variant_configuration()

    assert fixed["independent_variable"] == "correspondence_validation_protocol"
    assert fixed["matching_view_held_fixed"] is True
    assert fixed["experiment_id"] == EXPERIMENT_ID
    assert fixed["matcher_id"] == "sift"
    assert variants[VARIANT_A_ID]["protocol_id"] == PROTOCOL_ONE_WAY
    assert variants[VARIANT_B_ID]["protocol_id"] == PROTOCOL_RECIPROCAL
    assert variants[VARIANT_A_ID]["require_reciprocal"] is False
    assert variants[VARIANT_B_ID]["require_reciprocal"] is True
    assert VARIANT_PROTOCOL_ID == {
        VARIANT_A_ID: PROTOCOL_ONE_WAY,
        VARIANT_B_ID: PROTOCOL_RECIPROCAL,
    }
    assert RUNTIME_FACTOR_LIMIT == 5.0


def test_primary_pair_is_exp001_pair_02() -> None:
    entry = PAIR_REGISTRY[PRIMARY_PAIR_ID]
    assert PRIMARY_PAIR_ID == "pair_02_mid_equatorial"
    assert FOLLOW_UP_PAIR_ID == "pair_01_equatorial"
    assert OHRC_PRODUCT_ID == entry["ohrc_product_id"]
    assert LROC_PRODUCT_ID == entry["lroc_product_id"]
    assert OHRC_PRODUCT_ID == "ch2_ohr_ncp_20250612T2229094979_d_img_d18"
    assert LROC_PRODUCT_ID == "M1504316436RC"
    assert EXPECTED_PAIR_02_STRIDES == {"ohrc": 16, "lroc": 8}
    assert EXPECTED_PAIR_01_STRIDES == {"ohrc": 15, "lroc": 8}


def test_registration_cap_is_not_raised() -> None:
    fixed = snapshot_fixed_configuration()
    assert fixed["registration"]["max_output_pixels"] == 16_777_216
    assert fixed["spatial_grid"]["grid_bins"] == 8
    assert fixed["spatial_grid"]["total_cells"] == 64
