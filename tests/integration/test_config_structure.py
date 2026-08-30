"""Wiring tests: structural configuration slots exist without scientific policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.pipeline.orchestrator import PIPELINE_STAGES

pytestmark = pytest.mark.wiring

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "default.yaml"

REQUIRED_SECTIONS = (
    "preprocessing:",
    "geometry:",
    "representation:",
    "matching:",
    "verification:",
    "control_points:",
    "refinement:",
    "registration:",
    "evaluation:",
    "export:",
)

BANNED_POLICY_TOKENS = (
    "sift",
    "asift",
    "rift",
    "lightglue",
    "loftr",
    "pwift",
    "homography",
    "ransac",
    "magsac",
    "threshold",
)


def test_default_config_has_structural_sections() -> None:
    text = CONFIG_PATH.read_text(encoding="utf-8")
    missing = [section for section in REQUIRED_SECTIONS if section not in text]
    assert missing == []
    assert "matcher_id:" in text
    assert "representation_id:" in text
    assert "model_name:" in text


def test_default_config_pipeline_order_matches_freeze() -> None:
    text = CONFIG_PATH.read_text(encoding="utf-8")
    names: list[str] = []
    in_operations = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "operations:":
            in_operations = True
            continue
        if in_operations:
            if stripped.startswith("- "):
                names.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("#"):
                break
    assert names == list(PIPELINE_STAGES)


def test_default_config_does_not_select_matcher_or_invent_thresholds() -> None:
    text = CONFIG_PATH.read_text(encoding="utf-8")
    active = "\n".join(line.split("#", 1)[0].strip().lower() for line in text.splitlines())
    present = [token for token in BANNED_POLICY_TOKENS if token in active]
    assert present == []
    assert "matcher_id: null" in text
    assert "model_name: null" in text
    assert "representation_id: null" in text
