"""Committed EXP-001 record checks against the EXP-000 baseline.

These tests read the experiment JSON already in the repository. They do not
ingest rasters and they are not official SIH evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.io.exp001.config import INDEPENDENT_ACCURACY_NOT_VALIDATED, PRIMARY_PAIR_ID
from src.io.exp001.run import rebuild_summary

_REPO = Path(__file__).resolve().parents[2]
_EXP000 = _REPO / "experiments" / "EXP-000" / "results" / f"{PRIMARY_PAIR_ID}.json"
_EXP001 = _REPO / "experiments" / "EXP-001" / "results"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_exp001_sift_pair_01_reproduces_the_exp000_baseline_counts() -> None:
    baseline = _load(_EXP000)["scientific_interpretation"]
    current = _load(_EXP001 / f"{PRIMARY_PAIR_ID}.json")
    sift = current["matchers"]["sift"]

    assert sift["match"]["raw_match_count"] == baseline["raw_sift_matches"] == 36
    assert sift["verify_matches"]["verified_inlier_count"] == baseline["verified_inliers"] == 4
    assert sift["verify_matches"]["inlier_ratio"] == baseline["inlier_ratio"]
    assert sift["select_control_points"]["control_point_count"] == baseline["control_points"] == 4
    assert (
        sift["spatial_distribution"]["verified_match_coverage"]
        == baseline["spatial_coverage"]
    )
    assert sift["refine_points"]["outcome"] == baseline["refinement_outcome"]
    assert current["interpretation"]["independent_accuracy"] == (
        INDEPENDENT_ACCURACY_NOT_VALIDATED
    )
    assert current["stages"]["generate_representation"]["shared_across_matchers"] is True
    assert current["stages"]["generate_representation"]["source_matching_view"]["stride"] == 15
    assert current["stages"]["generate_representation"]["reference_matching_view"]["stride"] == 8


def test_exp001_pair_records_label_independent_accuracy_not_validated() -> None:
    for path in _EXP001.glob("pair_*.json"):
        record = _load(path)
        assert record["interpretation"]["independent_accuracy"] == (
            INDEPENDENT_ACCURACY_NOT_VALIDATED
        )
        for arm in record["matchers"].values():
            assert arm["evaluate"]["independent_accuracy"] == (
                INDEPENDENT_ACCURACY_NOT_VALIDATED
            )
            assert arm["held_out_validation"]["independent_accuracy"] == (
                INDEPENDENT_ACCURACY_NOT_VALIDATED
            )


def test_rebuild_summary_preserves_the_exp000_reference_row(tmp_path: Path) -> None:
    for path in _EXP001.glob("pair_*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())

    summary = rebuild_summary(record_dir=tmp_path)

    assert summary["comparison_rows"][0]["role"] == "EXP-000_baseline_reference"
    assert summary["comparison_rows"][0]["raw"] == 36
    assert summary["comparison_rows"][0]["verified"] == 4
    assert summary["scientific_conclusion"]["globally_superior_matcher"] is None
    assert summary["scientific_conclusion"]["h1_supported_on_primary_pair"] is False
    assert summary["scientific_conclusion"]["independent_accuracy"] == (
        INDEPENDENT_ACCURACY_NOT_VALIDATED
    )
    exp001_rows = [row for row in summary["comparison_rows"] if row.get("role") == "exp001"]
    assert [row["matcher"] for row in exp001_rows[:3]] == ["sift", "rift", "orb"]
