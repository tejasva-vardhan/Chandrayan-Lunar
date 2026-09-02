"""EXP-001 conclusion tests. Not lunar accuracy evidence."""

from __future__ import annotations

from src.io.exp001.conclusion import scientific_conclusion
from src.io.exp001.config import INDEPENDENT_ACCURACY_NOT_VALIDATED, PRIMARY_PAIR_ID


def _arm(count: int) -> dict[str, object]:
    return {
        "interpretation": {
            "any_matcher_exceeds_model_minimum": count > 4,
            "exceeds_model_minimum_by_matcher": {
                "sift": count > 4,
                "rift": False,
                "orb": count > 4,
            },
            "verified_inliers_by_matcher": {"sift": count, "rift": 0, "orb": count},
        }
    }


def test_conclusion_never_names_a_global_winner() -> None:
    summary = {
        "pair_ids": [PRIMARY_PAIR_ID],
        "matcher_ids": ["sift", "rift", "orb"],
        "pairs": {PRIMARY_PAIR_ID: _arm(4)},
    }

    payload = scientific_conclusion(summary)

    assert payload["globally_superior_matcher"] is None
    assert payload["h1_supported_on_primary_pair"] is False
    assert payload["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert "NOT VALIDATED" in payload["limitations"][0]


def test_conclusion_reports_inconsistent_cross_pair_improvement() -> None:
    summary = {
        "pair_ids": [PRIMARY_PAIR_ID, "pair_02_mid_equatorial"],
        "matcher_ids": ["sift", "rift", "orb"],
        "pairs": {
            PRIMARY_PAIR_ID: _arm(4),
            "pair_02_mid_equatorial": _arm(25),
        },
    }

    payload = scientific_conclusion(summary)

    assert payload["h1_supported_on_primary_pair"] is False
    assert payload["pairs_where_any_matcher_exceeds_model_minimum"] == [
        "pair_02_mid_equatorial"
    ]
    assert payload["matchers_that_exceeded_on_every_tested_pair"] == []
    assert "rift" in payload["matchers_with_zero_verified_inliers_on_every_tested_pair"]
    assert "not consistent" in payload["statement"]
    assert "matching-view scale" in payload["recommended_exp002"]
    assert payload["globally_superior_matcher"] is None


def test_conclusion_does_not_treat_held_out_error_as_accuracy() -> None:
    payload = scientific_conclusion(
        {
            "pair_ids": [PRIMARY_PAIR_ID],
            "matcher_ids": ["sift"],
            "pairs": {PRIMARY_PAIR_ID: _arm(25)},
        }
    )

    assert payload["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert any("not independent accuracy" in item for item in payload["limitations"])
