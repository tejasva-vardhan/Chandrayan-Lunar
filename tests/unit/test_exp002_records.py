"""Committed EXP-002 record checks against the EXP-000 baseline.

These tests read the experiment JSON already in the repository. They do not
ingest rasters and they are not official SIH evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.io.exp002.config import INDEPENDENT_ACCURACY_NOT_VALIDATED, PAIR_MANIFEST_ID

_REPO = Path(__file__).resolve().parents[2]
_EXP000 = _REPO / "experiments" / "EXP-000" / "results" / f"{PAIR_MANIFEST_ID}.json"
_EXP002 = _REPO / "experiments" / "EXP-002" / "results" / f"{PAIR_MANIFEST_ID}.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_variant_a_reproduces_the_exp000_sift_counts() -> None:
    baseline = _load(_EXP000)["scientific_interpretation"]
    current = _load(_EXP002)
    variant_a = current["variants"]["A"]

    assert variant_a["uses_frozen_generate_representation"] is True
    assert variant_a["match"]["raw_match_count"] == baseline["raw_sift_matches"] == 36
    assert variant_a["verify_matches"]["verified_inlier_count"] == baseline["verified_inliers"] == 4
    assert variant_a["verify_matches"]["inlier_ratio"] == baseline["inlier_ratio"]
    assert (
        variant_a["select_control_points"]["control_point_count"]
        == baseline["control_points"]
        == 4
    )
    assert (
        variant_a["spatial_distribution"]["verified_match_coverage"]
        == baseline["spatial_coverage"]
    )
    assert variant_a["generate_representation"]["source_matching_view"]["stride"] == 15
    assert variant_a["generate_representation"]["reference_matching_view"]["stride"] == 8


def test_variant_b_did_not_change_pair_01_strides_or_yield() -> None:
    current = _load(_EXP002)
    variant_a = current["variants"]["A"]
    variant_b = current["variants"]["B"]
    interpretation = current["interpretation"]

    assert variant_b["generate_representation"]["source_matching_view"]["stride"] == 15
    assert variant_b["generate_representation"]["reference_matching_view"]["stride"] == 8
    assert variant_b["match"]["raw_match_count"] == variant_a["match"]["raw_match_count"]
    assert (
        variant_b["verify_matches"]["verified_inlier_count"]
        == variant_a["verify_matches"]["verified_inlier_count"]
        == 4
    )
    assert interpretation["matching_view_strides_changed"] is False
    assert interpretation["verified_inliers_improved"] is False
    assert interpretation["hypothesis_supported"] is False
    assert interpretation["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert interpretation["four_point_dlt_residuals_are_not_accuracy"] is True
