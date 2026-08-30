"""Logical scientific operations for the frozen pipeline.

Each function is a contract. Implementations live in the owning module.
These stubs must not return fabricated scientific results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.io.exports import ExportManifest
from src.io.exports import export_result as write_export
from src.models.correspondence_set import CorrespondenceSet
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult


def ingest_product(source: Path) -> LunarProduct:
    """Haruto / ingestion: load, decode, basic validate, mask, extract metadata.

    Pair-aware resampling and orientation do not belong here.
    """
    raise NotImplementedError(f"ingest_product is a contract stub. source={source}")


def characterize_pair(source: LunarProduct, reference: LunarProduct) -> RegistrationPair:
    """Shashwat / geometry: pair characterization. Not implemented in this foundation."""
    raise NotImplementedError(
        "characterize_pair is a contract stub. "
        f"source={source.product_id} reference={reference.product_id}"
    )


def preprocess(pair: RegistrationPair) -> RegistrationPair:
    """Haruto / preprocessing: pair-aware operations.

    Owns normalization, orientation handling when required, and scale-aware
    resampling when required. Do not invent thresholds. Not implemented here.
    """
    raise NotImplementedError(f"preprocess is a contract stub. pair_id={pair.pair_id}")


def generate_representation(pair: RegistrationPair) -> Any:
    """Chuba: representation engine.

    Return type is intentionally unconstrained. Representation choice is experimental (v3 §11).
    Adaptive routing may temporarily live behind representation/matcher orchestration
    and use PairCharacterization. An explicit route() operation is M5, not this freeze.
    """
    raise NotImplementedError(
        f"generate_representation is a contract stub. pair_id={pair.pair_id}"
    )


def match(pair: RegistrationPair, representation: Any | None = None) -> CorrespondenceSet:
    """Chuba: matcher orchestrator.

    Adaptive routing may temporarily live here and use PairCharacterization.
    Do not add route() in this freeze (M5).
    """
    raise NotImplementedError(
        f"match is a contract stub. pair_id={pair.pair_id} representation={representation!r}"
    )


def verify_matches(
    correspondences: CorrespondenceSet, pair: RegistrationPair
) -> CorrespondenceSet:
    """Shaiz: geometric verification. Not implemented in this foundation."""
    raise NotImplementedError(
        f"verify_matches is a contract stub. pair_id={pair.pair_id} "
        f"matcher_id={correspondences.matcher_id}"
    )


def select_control_points(
    correspondences: CorrespondenceSet, pair: RegistrationPair
) -> list[ControlPoint]:
    """Shaiz: spatially uniform control points. Not implemented in this foundation."""
    raise NotImplementedError(
        f"select_control_points is a contract stub. pair_id={pair.pair_id}"
    )


def refine_points(
    control_points: list[ControlPoint], pair: RegistrationPair
) -> list[ControlPoint]:
    """Shaiz: sub-pixel refinement. Not implemented in this foundation."""
    raise NotImplementedError(
        f"refine_points is a contract stub. pair_id={pair.pair_id} n={len(control_points)}"
    )


def register(
    pair: RegistrationPair,
    control_points: list[ControlPoint],
    correspondences: CorrespondenceSet,
) -> RegistrationResult:
    """Shaiz: registration.

    Implementations must attach the provided CorrespondenceSet onto
    RegistrationResult.correspondences. Do not invent inliers, counts, metrics,
    or transformations.
    """
    raise NotImplementedError(f"register is a contract stub. pair_id={pair.pair_id}")


def evaluate(result: RegistrationResult, pair: RegistrationPair) -> RegistrationResult:
    """Shaiz: independent validation.

    Use result.correspondences as the canonical match collection. Do not invent metrics.
    """
    raise NotImplementedError(f"evaluate is a contract stub. pair_id={pair.pair_id}")


def export_result(
    result: RegistrationResult, pair: RegistrationPair, output_dir: Path
) -> ExportManifest:
    """Tejas/io: export wrapper. Delegates to the I/O contract."""
    return write_export(result, pair, output_dir)
