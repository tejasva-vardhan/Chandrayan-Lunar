"""Wiring tests: pipeline imports module interfaces, not implementations."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import src.control_points as control_points
import src.evaluation as evaluation
import src.geometry as geometry
import src.ingestion as ingestion
import src.io.exports as exports
import src.matching as matching
import src.preprocessing as preprocessing
import src.refinement as refinement
import src.registration as registration
import src.representation as representation
import src.verification as verification
from src.pipeline import operations
from src.pipeline.orchestrator import default_operations

pytestmark = pytest.mark.wiring

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "src" / "pipeline"
BANNED_ALGORITHM_NAMES = re.compile(
    r"\b(sift|asift|rift2?|lightglue|loftr|pwift|homography)\b",
    re.IGNORECASE,
)


def test_operations_facade_binds_to_owning_module_interfaces() -> None:
    assert operations.ingest_product is ingestion.ingest_product
    assert operations.characterize_pair is geometry.characterize_pair
    assert operations.preprocess is preprocessing.preprocess
    assert operations.generate_representation is representation.generate_representation
    assert operations.match is matching.match
    assert operations.verify_matches is verification.verify_matches
    assert operations.select_control_points is control_points.select_control_points
    assert operations.refine_points is refinement.refine_points
    assert operations.register is registration.register
    assert operations.evaluate is evaluation.evaluate
    assert operations.export_result is exports.export_result


def test_default_operations_use_module_interfaces() -> None:
    ops = default_operations()
    assert ops.ingest_product is ingestion.ingest_product
    assert ops.characterize_pair is geometry.characterize_pair
    assert ops.preprocess is preprocessing.preprocess
    assert ops.generate_representation is representation.generate_representation
    assert ops.match is matching.match
    assert ops.verify_matches is verification.verify_matches
    assert ops.select_control_points is control_points.select_control_points
    assert ops.refine_points is refinement.refine_points
    assert ops.register is registration.register
    assert ops.evaluate is evaluation.evaluate
    assert ops.export_result is exports.export_result


def test_pipeline_package_does_not_name_matchers_or_transforms() -> None:
    offenders: list[str] = []
    for py_file in PIPELINE_ROOT.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        match = BANNED_ALGORITHM_NAMES.search(text)
        if match:
            offenders.append(f"{py_file.relative_to(REPO_ROOT)}: {match.group(0)}")
    assert offenders == []


def test_pipeline_package_does_not_import_http_or_infra() -> None:
    forbidden = {
        "fastapi",
        "flask",
        "django",
        "starlette",
        "requests",
        "httpx",
        "aiohttp",
        "uvicorn",
        "sqlalchemy",
        "psycopg",
        "psycopg2",
        "asyncpg",
        "pymongo",
        "redis",
        "boto3",
        "botocore",
    }
    offenders: list[str] = []
    for py_file in PIPELINE_ROOT.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        overlap = roots & forbidden
        if overlap:
            offenders.append(f"{py_file}: {sorted(overlap)}")
    assert offenders == []


def test_orchestrator_does_not_swallow_unimplemented_stages() -> None:
    source = (PIPELINE_ROOT / "orchestrator.py").read_text(encoding="utf-8")
    run_body = source.split("def run", 1)[1]
    assert "except NotImplementedError" not in source
    assert "except Exception" not in run_body
