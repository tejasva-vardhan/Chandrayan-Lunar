from pathlib import Path
from typing import Any

import pytest

from src.io.exports import ExportManifest
from src.models import (
    CorrespondenceSet,
    LunarProduct,
    RegistrationPair,
    RegistrationResult,
)
from src.pipeline.orchestrator import PipelineOperations, ScientificPipeline


def _ingest(path: Path) -> LunarProduct:
    return LunarProduct(product_id=path.stem, instrument="unspecified")


def _characterize(source: LunarProduct, reference: LunarProduct) -> RegistrationPair:
    return RegistrationPair(pair_id="wired-pair", source=source, reference=reference)


def _preprocess(pair: RegistrationPair) -> RegistrationPair:
    return pair


def _representation(_pair: RegistrationPair) -> None:
    return None


def _match(pair: RegistrationPair, _representation: Any | None) -> CorrespondenceSet:
    return CorrespondenceSet(pair_id=pair.pair_id, matcher_id="unspecified")


def _verify(correspondences: CorrespondenceSet, _pair: RegistrationPair) -> CorrespondenceSet:
    return correspondences


def _select_cps(_correspondences: CorrespondenceSet, _pair: RegistrationPair) -> list:
    return []


def _refine(control_points: list, _pair: RegistrationPair) -> list:
    return control_points


def _register(
    pair: RegistrationPair, _control_points: list, correspondences: CorrespondenceSet
) -> RegistrationResult:
    return RegistrationResult(pair_id=pair.pair_id, correspondences=correspondences)


def _evaluate(result: RegistrationResult, _pair: RegistrationPair) -> RegistrationResult:
    return result


def _export(
    _result: RegistrationResult, _pair: RegistrationPair, output_dir: Path
) -> ExportManifest:
    return ExportManifest(registration_report=str(output_dir / "registration_report.html"))


def test_pipeline_wires_operations_in_order(tmp_paths: tuple[Path, Path, Path]) -> None:
    source_path, reference_path, output_dir = tmp_paths
    calls: list[str] = []
    register_correspondences: list[CorrespondenceSet] = []
    exported_pairs: list[RegistrationPair] = []

    def tracked(name: str, fn):  # noqa: ANN001
        def wrapper(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            calls.append(name)
            if name == "register":
                register_correspondences.append(args[2])
            if name == "export_result":
                exported_pairs.append(args[1])
            return fn(*args, **kwargs)

        return wrapper

    ops = PipelineOperations(
        ingest_product=tracked("ingest_product", _ingest),
        characterize_pair=tracked("characterize_pair", _characterize),
        preprocess=tracked("preprocess", _preprocess),
        generate_representation=tracked("generate_representation", _representation),
        match=tracked("match", _match),
        verify_matches=tracked("verify_matches", _verify),
        select_control_points=tracked("select_control_points", _select_cps),
        refine_points=tracked("refine_points", _refine),
        register=tracked("register", _register),
        evaluate=tracked("evaluate", _evaluate),
        export_result=tracked("export_result", _export),
    )

    result, manifest = ScientificPipeline(ops).run(source_path, reference_path, output_dir)

    assert calls == [
        "ingest_product",
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
    ]
    assert calls.index("preprocess") == calls.index("characterize_pair") + 1
    assert calls.index("preprocess") == calls.index("generate_representation") - 1
    assert result.pair_id == "wired-pair"
    assert result.metrics is None
    assert result.correspondences is not None
    assert result.correspondences is register_correspondences[0]
    assert result.correspondences.pair_id == "wired-pair"
    assert exported_pairs[0].pair_id == "wired-pair"
    assert exported_pairs[0].source.product_id == source_path.stem
    assert exported_pairs[0].reference.product_id == reference_path.stem
    assert manifest.registration_report is not None


def test_default_pipeline_fails_closed(tmp_paths: tuple[Path, Path, Path]) -> None:
    source_path, reference_path, output_dir = tmp_paths
    with pytest.raises(NotImplementedError):
        ScientificPipeline().run(source_path, reference_path, output_dir)


def test_default_pipeline_has_no_http_runtime_dependency() -> None:
    pipeline = ScientificPipeline()
    assert "http" not in type(pipeline).__module__.lower()
    assert pipeline.ops.ingest_product.__module__.startswith("src.")
    assert pipeline.ops.preprocess.__module__.startswith("src.")
