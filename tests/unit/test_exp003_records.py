"""Committed EXP-003 record checks against the EXP-000 baseline.

These tests read the experiment JSON already in the repository. They do not
ingest rasters and they are not official SIH evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.io.exp003.config import INDEPENDENT_ACCURACY_NOT_VALIDATED, PAIR_MANIFEST_ID

_REPO = Path(__file__).resolve().parents[2]
_EXP000 = _REPO / "experiments" / "EXP-000" / "results" / f"{PAIR_MANIFEST_ID}.json"
_EXP003 = _REPO / "experiments" / "EXP-003" / "results" / f"{PAIR_MANIFEST_ID}.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_variant_a_reproduces_the_exp000_sift_counts() -> None:
    baseline = _load(_EXP000)["scientific_interpretation"]
    current = _load(_EXP003)
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


def test_variants_change_lroc_scale_but_not_verified_inlier_count() -> None:
    current = _load(_EXP003)
    variant_a = current["variants"]["A"]
    variant_b = current["variants"]["B"]
    variant_c = current["variants"]["C"]
    interpretation = current["interpretation"]

    assert variant_a["generate_representation"]["source_matching_view"]["stride"] == 15
    assert variant_b["generate_representation"]["source_matching_view"]["stride"] == 15
    assert variant_c["generate_representation"]["source_matching_view"]["stride"] == 15
    assert variant_a["generate_representation"]["reference_matching_view"]["stride"] == 8
    assert variant_b["generate_representation"]["reference_matching_view"]["stride"] == 16
    assert variant_c["generate_representation"]["reference_matching_view"]["stride"] == 4
    assert variant_c["generate_representation"]["reference_matching_view"][
        "exceeds_max_pixels_per_image"
    ] is True

    assert variant_a["verify_matches"]["verified_inlier_count"] == 4
    assert variant_b["verify_matches"]["verified_inlier_count"] == 4
    assert variant_c["verify_matches"]["verified_inlier_count"] == 4
    assert variant_a["match"]["raw_match_count"] == 36
    assert variant_b["match"]["raw_match_count"] == 45
    assert variant_c["match"]["raw_match_count"] == 11

    assert interpretation["independent_variable_applied"] is True
    assert interpretation["ohrc_stride_held_fixed"] is True
    assert interpretation["lroc_matching_view_scale_changed"] is True
    assert interpretation["verified_inliers_equal_across_variants"] is True
    assert interpretation["raw_matches_equal_across_variants"] is False
    assert interpretation["scale_changes_materially_affect_verified_yield"] is False
    assert interpretation["hypothesis_supported"] is True
    assert interpretation["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert interpretation["four_point_dlt_residuals_are_not_accuracy"] is True
