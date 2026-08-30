"""Logical scientific operations for the frozen pipeline.

This module is the pipeline import facade. Implementations live in owning
packages; this file re-exports those interfaces so callers and tests can use
`src.pipeline.operations` without depending on matcher or transform details.

Default callables raise NotImplementedError. They must not return fabricated
scientific results.
"""

from src.control_points import select_control_points
from src.evaluation import evaluate
from src.geometry import characterize_pair
from src.ingestion import ingest_product
from src.io.exports import export_result
from src.matching import match
from src.preprocessing import preprocess
from src.refinement import refine_points
from src.registration import register
from src.representation import generate_representation
from src.verification import verify_matches

__all__ = [
    "characterize_pair",
    "evaluate",
    "export_result",
    "generate_representation",
    "ingest_product",
    "match",
    "preprocess",
    "refine_points",
    "register",
    "select_control_points",
    "verify_matches",
]
