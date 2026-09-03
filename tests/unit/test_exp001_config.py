"""EXP-001 configuration tests.

The controlled-experiment claim rests on the fixed configuration really being
the EXP-000 configuration, and on the pair registry really being the committed
manifest. Both are asserted here rather than asserted in prose.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.io.exp000.config import snapshot_software_configuration
from src.io.exp001.config import (
    EXPERIMENT_ID,
    GENERALIZATION_PAIR_IDS,
    PAIR_REGISTRY,
    PRIMARY_PAIR_ID,
    excluded_matchers,
    snapshot_fixed_configuration,
    snapshot_matcher_configuration,
)
from src.matching.portfolio import PORTFOLIO_MATCHER_IDS

_MANIFEST = Path(__file__).resolve().parents[2] / "data" / "manifests" / "demo_pairs.yaml"


def test_pair_registry_matches_the_committed_manifest() -> None:
    """The registry may not silently drift from data/manifests/demo_pairs.yaml."""

    declared = _declared_pairs(_MANIFEST.read_text(encoding="utf-8"))

    assert PAIR_REGISTRY == declared


def _declared_pairs(text: str) -> dict[str, dict[str, str]]:
    try:
        import yaml
    except ImportError:
        yaml = None
    if yaml is not None:
        manifest = yaml.safe_load(text)
        return {
            entry["pair_id"]: {
                "ohrc_product_id": entry["ohrc_product"],
                "lroc_product_id": entry["lroc_product"],
            }
            for entry in manifest["demo_pairs"]
        }

    declared: dict[str, dict[str, str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("pair_id:"):
            current = line.split(":", 1)[1].strip()
            declared[current] = {}
        elif current is not None and line.startswith("ohrc_product:"):
            declared[current]["ohrc_product_id"] = line.split(":", 1)[1].strip()
        elif current is not None and line.startswith("lroc_product:"):
            declared[current]["lroc_product_id"] = line.split(":", 1)[1].strip()
    return declared


def test_primary_pair_is_the_exp000_pair() -> None:
    """pair_01 must stay first so its row is comparable to the baseline."""

    assert PRIMARY_PAIR_ID == snapshot_software_configuration()["pair_manifest_id"]
    assert PRIMARY_PAIR_ID not in GENERALIZATION_PAIR_IDS
    assert set(GENERALIZATION_PAIR_IDS) | {PRIMARY_PAIR_ID} == set(PAIR_REGISTRY)


def test_fixed_configuration_inherits_every_exp000_stage_setting() -> None:
    baseline = snapshot_software_configuration()
    fixed = snapshot_fixed_configuration()

    for key in (
        "preprocessing",
        "matching_view",
        "verification",
        "control_points",
        "refinement",
        "registration",
        "evaluation",
    ):
        assert fixed[key] == baseline[key], f"{key} diverged from EXP-000"


def test_fixed_configuration_excludes_the_independent_variable() -> None:
    """The matcher is what varies, so it cannot appear as a fixed parameter."""

    fixed = snapshot_fixed_configuration()

    assert "matcher_id" not in fixed
    assert "sift" not in fixed
    assert fixed["independent_variable"] == "matcher_id"
    assert fixed["experiment_id"] == EXPERIMENT_ID


def test_registration_cap_is_not_raised() -> None:
    fixed = snapshot_fixed_configuration()

    assert fixed["registration"]["max_output_pixels"] == 16_777_216


def test_verification_settings_are_the_frozen_defaults() -> None:
    fixed = snapshot_fixed_configuration()["verification"]

    assert fixed["model_id"] == "projective_2d_baseline"
    assert fixed["estimator_id"] == "ransac_style_baseline"
    assert fixed["residual_limit"] == 3.0
    assert fixed["max_trials"] == 500
    assert fixed["rng_seed"] == 0


def test_matcher_configuration_covers_every_compared_matcher() -> None:
    configuration = snapshot_matcher_configuration()

    assert set(configuration) == set(PORTFOLIO_MATCHER_IDS)
    json.dumps(configuration)


def test_excluded_matchers_state_a_reason_for_every_rejection() -> None:
    """A comparison that omits a candidate must say why it omitted it."""

    excluded = excluded_matchers()

    assert excluded
    for entry in excluded:
        assert entry["candidate"]
        assert entry["status"]
        assert len(entry["detail"]) > 80
    candidates = " ".join(entry["candidate"] for entry in excluded)
    assert "RIFT" in candidates
    assert "LoFTR" in candidates or "LightGlue" in candidates
