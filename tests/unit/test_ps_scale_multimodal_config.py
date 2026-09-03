"""Unit tests for PS-SCALE-MULTIMODAL configuration snapshots."""

from __future__ import annotations

from src.io.ps_scale_multimodal.config import (
    EXPECTED_PAIR_02_STRIDES_A,
    EXPECTED_PAIR_02_STRIDES_B,
    PRIMARY_PAIR_ID,
    REPRESENTATION_CROSS_SENSOR,
    REPRESENTATION_INTENSITY,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_C_ID,
    snapshot_fixed_configuration,
    snapshot_variant_configuration,
    variant_a_matching_view_settings,
    variant_b_matching_view_settings,
)
from src.representation.settings import (
    SCALE_POLICY_COMMON_PHYSICAL_GSD,
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
)


def test_variants_pin_scale_and_cross_sensor_levers() -> None:
    variants = snapshot_variant_configuration()
    assert variants[VARIANT_A_ID]["representation_id"] == REPRESENTATION_INTENSITY
    assert variants[VARIANT_A_ID]["scale_policy"] == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    assert variants[VARIANT_B_ID]["representation_id"] == REPRESENTATION_INTENSITY
    assert variants[VARIANT_B_ID]["scale_policy"] == SCALE_POLICY_COMMON_PHYSICAL_GSD
    assert variants[VARIANT_C_ID]["representation_id"] == REPRESENTATION_CROSS_SENSOR
    assert variants[VARIANT_C_ID]["scale_policy"] == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    assert variants[VARIANT_A_ID]["expected_pair_02_strides"] == EXPECTED_PAIR_02_STRIDES_A
    assert variants[VARIANT_B_ID]["expected_pair_02_strides"] == EXPECTED_PAIR_02_STRIDES_B


def test_fixed_configuration_documents_modality_scope() -> None:
    fixed = snapshot_fixed_configuration()
    assert fixed["primary_pair_manifest_id"] == PRIMARY_PAIR_ID
    assert fixed["modality_scope"]["tmc_available"] is False
    assert fixed["modality_scope"]["iirs_available"] is False
    assert "OHRC" in fixed["modality_scope"]["available_instruments_in_demo_dataset"]


def test_matching_view_settings_differ_for_scale_arm() -> None:
    a = variant_a_matching_view_settings()
    b = variant_b_matching_view_settings()
    assert a.scale_policy == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    assert b.scale_policy == SCALE_POLICY_COMMON_PHYSICAL_GSD
    assert b.catalog_gsd_meters_by_instrument == (("LRO_NAC", 0.5),)
