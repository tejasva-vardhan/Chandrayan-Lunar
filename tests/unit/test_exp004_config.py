"""EXP-004 configuration tests.

The controlled-experiment claim rests on everything except representation_id
being the EXP-000 configuration.
"""

from __future__ import annotations

from src.io.exp000.config import snapshot_software_configuration
from src.io.exp004.config import (
    EXPECTED_PAIR_01_STRIDES,
    EXPERIMENT_ID,
    LROC_PRODUCT_ID,
    OHRC_PRODUCT_ID,
    PAIR_MANIFEST_ID,
    REPRESENTATION_GRADIENT,
    REPRESENTATION_INTENSITY,
    REPRESENTATION_STRUCTURAL,
    ROUTING_DIFFICULTY_BY_REPRESENTATION,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_C_ID,
    VARIANT_REPRESENTATION_ID,
    pair_routed_for_representation,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
)
from src.models import LunarProduct, RegistrationPair
from src.models.registration_pair import PairCharacterization
from src.routing import select_matcher_id, select_representation_id


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


def test_independent_variable_is_representation_id() -> None:
    fixed = snapshot_fixed_configuration()
    variants = snapshot_variant_configuration()

    assert fixed["independent_variable"] == "representation_id"
    assert fixed["matching_view_held_fixed"] is True
    assert fixed["experiment_id"] == EXPERIMENT_ID
    assert fixed["matcher_id"] == "sift"
    assert variants[VARIANT_A_ID]["representation_id"] == REPRESENTATION_INTENSITY
    assert variants[VARIANT_B_ID]["representation_id"] == REPRESENTATION_GRADIENT
    assert variants[VARIANT_C_ID]["representation_id"] == REPRESENTATION_STRUCTURAL
    assert VARIANT_REPRESENTATION_ID == {
        VARIANT_A_ID: REPRESENTATION_INTENSITY,
        VARIANT_B_ID: REPRESENTATION_GRADIENT,
        VARIANT_C_ID: REPRESENTATION_STRUCTURAL,
    }


def test_existing_routing_maps_each_variant_representation() -> None:
    assert ROUTING_DIFFICULTY_BY_REPRESENTATION[REPRESENTATION_INTENSITY] is None
    assert ROUTING_DIFFICULTY_BY_REPRESENTATION[REPRESENTATION_GRADIENT] == "normal"
    assert ROUTING_DIFFICULTY_BY_REPRESENTATION[REPRESENTATION_STRUCTURAL] == "difficult"

    pair = RegistrationPair(
        pair_id="route-test",
        source=LunarProduct(product_id="s", instrument="OHRC"),
        reference=LunarProduct(product_id="r", instrument="LRO_NAC"),
        characterization=PairCharacterization(sensor_pair="OHRC/LRO_NAC", difficulty=None),
    )
    intensity = pair_routed_for_representation(pair, REPRESENTATION_INTENSITY)
    gradient = pair_routed_for_representation(pair, REPRESENTATION_GRADIENT)
    structural = pair_routed_for_representation(pair, REPRESENTATION_STRUCTURAL)

    assert intensity is pair
    assert pair.characterization is not None
    assert pair.characterization.difficulty is None
    assert select_representation_id(intensity) == REPRESENTATION_INTENSITY
    assert select_representation_id(gradient) == REPRESENTATION_GRADIENT
    assert select_representation_id(structural) == REPRESENTATION_STRUCTURAL
    assert gradient.characterization is not None
    assert structural.characterization is not None
    assert gradient.characterization.difficulty == "normal"
    assert structural.characterization.difficulty == "difficult"
    assert gradient.characterization.sensor_pair == "OHRC/LRO_NAC"
    assert select_matcher_id(gradient) == "sift"
    assert select_matcher_id(structural) == "sift"
    assert select_matcher_id(pair) == "sift"


def test_expected_pair_01_strides_stay_at_exp000() -> None:
    assert EXPECTED_PAIR_01_STRIDES[VARIANT_A_ID] == {"ohrc": 15, "lroc": 8}
    assert EXPECTED_PAIR_01_STRIDES[VARIANT_B_ID] == {"ohrc": 15, "lroc": 8}
    assert EXPECTED_PAIR_01_STRIDES[VARIANT_C_ID] == {"ohrc": 15, "lroc": 8}


def test_primary_pair_is_the_exp000_pair() -> None:
    baseline = snapshot_software_configuration()
    assert PAIR_MANIFEST_ID == baseline["pair_manifest_id"]
    assert OHRC_PRODUCT_ID == "ch2_ohr_ncp_20210402T0546284043_d_img_d18"
    assert LROC_PRODUCT_ID == "M150368601RC"


def test_registration_cap_is_not_raised() -> None:
    fixed = snapshot_fixed_configuration()
    assert fixed["registration"]["max_output_pixels"] == 16_777_216
