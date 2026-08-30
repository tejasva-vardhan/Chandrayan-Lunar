"""End-to-end orchestration. Scientific steps are injected; this module does not compute them."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import src.pipeline.operations as operations
from src.io.exports import ExportManifest
from src.models.correspondence_set import CorrespondenceSet
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult

T = TypeVar("T")

PIPELINE_STAGES: tuple[str, ...] = (
    "ingest_product",
    "characterize_pair",
    "preprocess",
    "generate_representation",
    "match",
    "verify_matches",
    "select_control_points",
    "refine_points",
    "register",
    "evaluate",
    "export_result",
)


def _expect(value: object, expected: type[T], stage: str) -> T:
    if not isinstance(value, expected):
        raise TypeError(
            f"{stage} must return {expected.__name__}; got {type(value).__name__}. "
            "Do not skip stages or return placeholder scientific outputs."
        )
    return value


def _expect_control_points(value: object, stage: str) -> list[ControlPoint]:
    if not isinstance(value, list) or not all(isinstance(item, ControlPoint) for item in value):
        raise TypeError(
            f"{stage} must return list[ControlPoint]; got {type(value).__name__}. "
            "Do not skip stages or return placeholder scientific outputs."
        )
    return value


@dataclass(frozen=True)
class PipelineOperations:
    ingest_product: Callable[[Path], LunarProduct]
    characterize_pair: Callable[[LunarProduct, LunarProduct], RegistrationPair]
    preprocess: Callable[[RegistrationPair], RegistrationPair]
    generate_representation: Callable[[RegistrationPair], Any]
    match: Callable[[RegistrationPair, Any | None], CorrespondenceSet]
    verify_matches: Callable[[CorrespondenceSet, RegistrationPair], CorrespondenceSet]
    select_control_points: Callable[[CorrespondenceSet, RegistrationPair], list[ControlPoint]]
    refine_points: Callable[[list[ControlPoint], RegistrationPair], list[ControlPoint]]
    register: Callable[
        [RegistrationPair, list[ControlPoint], CorrespondenceSet], RegistrationResult
    ]
    evaluate: Callable[[RegistrationResult, RegistrationPair], RegistrationResult]
    export_result: Callable[[RegistrationResult, RegistrationPair, Path], ExportManifest]


def default_operations() -> PipelineOperations:
    return PipelineOperations(
        ingest_product=operations.ingest_product,
        characterize_pair=operations.characterize_pair,
        preprocess=operations.preprocess,
        generate_representation=operations.generate_representation,
        match=operations.match,
        verify_matches=operations.verify_matches,
        select_control_points=operations.select_control_points,
        refine_points=operations.refine_points,
        register=operations.register,
        evaluate=operations.evaluate,
        export_result=operations.export_result,
    )


class ScientificPipeline:
    """Runs the frozen operation order.

    HTTP, databases, and cloud services are not used. Callers inject
    implementations; defaults raise NotImplementedError.

    The verified CorrespondenceSet is passed to register and remains on the
    result for evaluate/export. Do not fabricate scientific values here.
    This orchestrator does not select a matcher or a transformation model.
    """

    def __init__(self, ops: PipelineOperations | None = None) -> None:
        self.ops = ops or default_operations()

    def run(
        self,
        source_path: Path,
        reference_path: Path,
        output_dir: Path,
    ) -> tuple[RegistrationResult, ExportManifest]:
        source = _expect(self.ops.ingest_product(source_path), LunarProduct, "ingest_product")
        reference = _expect(self.ops.ingest_product(reference_path), LunarProduct, "ingest_product")
        pair = _expect(
            self.ops.characterize_pair(source, reference),
            RegistrationPair,
            "characterize_pair",
        )
        pair = _expect(self.ops.preprocess(pair), RegistrationPair, "preprocess")
        representation = self.ops.generate_representation(pair)
        correspondences = _expect(
            self.ops.match(pair, representation), CorrespondenceSet, "match"
        )
        verified = _expect(
            self.ops.verify_matches(correspondences, pair),
            CorrespondenceSet,
            "verify_matches",
        )
        control_points = _expect_control_points(
            self.ops.select_control_points(verified, pair),
            "select_control_points",
        )
        refined = _expect_control_points(
            self.ops.refine_points(control_points, pair),
            "refine_points",
        )
        registered = _expect(
            self.ops.register(pair, refined, verified),
            RegistrationResult,
            "register",
        )
        evaluated = _expect(
            self.ops.evaluate(registered, pair),
            RegistrationResult,
            "evaluate",
        )
        manifest = _expect(
            self.ops.export_result(evaluated, pair, output_dir),
            ExportManifest,
            "export_result",
        )
        return evaluated, manifest
