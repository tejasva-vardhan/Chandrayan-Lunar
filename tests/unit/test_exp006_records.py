"""Committed EXP-006 record checks against the EXP-001 SIFT control.

These tests read experiment JSON already in the repository. They do not
ingest rasters and they are not official SIH evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.io.exp006.config import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    PRIMARY_PAIR_ID,
    PROTOCOL_ONE_WAY,
    PROTOCOL_RECIPROCAL,
    VARIANT_A_ID,
    VARIANT_B_ID,
)

_REPO = Path(__file__).resolve().parents[2]
_EXP001 = _REPO / "experiments" / "EXP-001" / "results" / f"{PRIMARY_PAIR_ID}.json"
_EXP006 = _REPO / "experiments" / "EXP-006" / "results" / f"{PRIMARY_PAIR_ID}.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_variant_a_reproduces_exp001_sift_yield() -> None:
    baseline = _load(_EXP001)["matchers"]["sift"]
    current = _load(_EXP006)
    variant_a = current["variants"][VARIANT_A_ID]

    assert variant_a["uses_frozen_match_surface"] is True
    assert variant_a["protocol_id"] == PROTOCOL_ONE_WAY
    assert variant_a["match"]["raw_match_count"] == baseline["match"]["raw_match_count"] == 919
    assert (
        variant_a["verify_matches"]["verified_inlier_count"]
        == baseline["verify_matches"]["verified_inlier_count"]
        == 25
    )
    assert variant_a["verify_matches"]["inlier_ratio"] == baseline["verify_matches"]["inlier_ratio"]
    occupancy = variant_a["spatial_distribution"]["verified_match_occupancy"]
    baseline_occ = baseline["spatial_distribution"]["verified_match_occupancy"]
    assert occupancy["source_occupied_cells"] == baseline_occ["source_occupied_cells"] == 11
    assert occupancy["reference_occupied_cells"] == baseline_occ["reference_occupied_cells"] == 9
    assert (
        variant_a["spatial_distribution"]["verified_match_coverage"]
        == baseline["spatial_distribution"]["verified_match_coverage"]
    )
    assert current["stages"]["generate_representation"]["source_matching_view"]["stride"] == 16
    assert current["stages"]["generate_representation"]["reference_matching_view"]["stride"] == 8


def test_reciprocal_does_not_support_h1_on_pair_02() -> None:
    current = _load(_EXP006)
    variant_b = current["variants"][VARIANT_B_ID]
    interpretation = current["interpretation"]

    assert variant_b["protocol_id"] == PROTOCOL_RECIPROCAL
    assert variant_b["require_reciprocal"] is True
    assert variant_b["matcher_id"] == "sift"
    assert variant_b["match"]["raw_match_count"] == 788
    assert variant_b["verify_matches"]["verified_inlier_count"] == 25
    assert interpretation["independent_variable_applied"] is True
    assert interpretation["quality_improved"] is False
    assert interpretation["spatial_maintained_or_improved"] is False
    assert interpretation["transform_stable"] is True
    assert interpretation["decision"] == "NOT SUPPORTED"
    assert interpretation["hypothesis_supported"] is False
    assert interpretation["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert interpretation["raw_match_count_is_not_success"] is True
    assert current["status"] == "completed"
