"""End-to-end orchestration. Scientific steps are injected; this module does not compute them."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.io.exports import ExportManifest
from src.models.correspondence_set import CorrespondenceSet
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult
from src.pipeline import operations


@dataclass(frozen=True)
class PipelineOperations:
    ingest_product: Callable[[Path], LunarProduct]
    characterize_pair: Callable[[LunarProduct, LunarProduct], RegistrationPair]
    generate_representation: Callable[[RegistrationPair], Any]
    match: Callable[[RegistrationPair, Any | None], CorrespondenceSet]
    verify_matches: Callable[[CorrespondenceSet, RegistrationPair], CorrespondenceSet]
    select_control_points: Callable[[CorrespondenceSet, RegistrationPair], list[ControlPoint]]
    refine_points: Callable[[list[ControlPoint], RegistrationPair], list[ControlPoint]]
    register: Callable[[RegistrationPair, list[ControlPoint]], RegistrationResult]
    evaluate: Callable[[RegistrationResult, RegistrationPair], RegistrationResult]
    export_result: Callable[[RegistrationResult, Path], ExportManifest]


def default_operations() -> PipelineOperations:
    return PipelineOperations(
        ingest_product=operations.ingest_product,
        characterize_pair=operations.characterize_pair,
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
    """Runs the logical operations in specification order.

    HTTP is not used. Callers inject implementations; defaults raise NotImplementedError.
    """

    def __init__(self, ops: PipelineOperations | None = None) -> None:
        self.ops = ops or default_operations()

    def run(
        self,
        source_path: Path,
        reference_path: Path,
        output_dir: Path,
    ) -> tuple[RegistrationResult, ExportManifest]:
        source = self.ops.ingest_product(source_path)
        reference = self.ops.ingest_product(reference_path)
        pair = self.ops.characterize_pair(source, reference)
        representation = self.ops.generate_representation(pair)
        correspondences = self.ops.match(pair, representation)
        verified = self.ops.verify_matches(correspondences, pair)
        control_points = self.ops.select_control_points(verified, pair)
        refined = self.ops.refine_points(control_points, pair)
        registered = self.ops.register(pair, refined)
        evaluated = self.ops.evaluate(registered, pair)
        manifest = self.ops.export_result(evaluated, output_dir)
        return evaluated, manifest
