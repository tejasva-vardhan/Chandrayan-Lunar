"""Wiring-only integration tests for ScientificPipeline.

These tests use doubles to verify orchestration. They are not scientific tests
and must not be cited as matcher, geometry, or registration evidence.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from src.io.exports import ExportManifest
from src.models import (
    ControlPoint,
    CorrespondenceSet,
    LunarProduct,
    RegistrationPair,
    RegistrationResult,
)
from src.pipeline import operations as op_stubs
from src.pipeline.orchestrator import PIPELINE_STAGES, PipelineOperations, ScientificPipeline

pytestmark = pytest.mark.wiring

IMPLEMENTED_STAGES = frozenset(
    {
        "characterize_pair",
        "verify_matches",
        "select_control_points",
        "refine_points",
        "register",
        "evaluate",
    }
)
UNIMPLEMENTED_STAGES = tuple(stage for stage in PIPELINE_STAGES if stage not in IMPLEMENTED_STAGES)

STUBS: dict[str, Callable[..., Any]] = {
    "ingest_product": op_stubs.ingest_product,
    "characterize_pair": op_stubs.characterize_pair,
    "preprocess": op_stubs.preprocess,
    "generate_representation": op_stubs.generate_representation,
    "match": op_stubs.match,
    "verify_matches": op_stubs.verify_matches,
    "select_control_points": op_stubs.select_control_points,
    "refine_points": op_stubs.refine_points,
    "register": op_stubs.register,
    "evaluate": op_stubs.evaluate,
    "export_result": op_stubs.export_result,
}


def _ingest(path: Path) -> LunarProduct:
    return LunarProduct(product_id=path.stem, instrument="unspecified")


def _characterize(source: LunarProduct, reference: LunarProduct) -> RegistrationPair:
    return RegistrationPair(pair_id="wired-pair", source=source, reference=reference)


def _preprocess(pair: RegistrationPair) -> RegistrationPair:
    return pair.model_copy(update={"pair_id": f"{pair.pair_id}-preprocessed"})


def _representation(_pair: RegistrationPair) -> object:
    return {"kind": "wiring-double"}


def _match(pair: RegistrationPair, _representation: Any | None) -> CorrespondenceSet:
    return CorrespondenceSet(pair_id=pair.pair_id, matcher_id="unspecified")


def _verify(correspondences: CorrespondenceSet, _pair: RegistrationPair) -> CorrespondenceSet:
    return correspondences


def _select_cps(_correspondences: CorrespondenceSet, _pair: RegistrationPair) -> list[ControlPoint]:
    return []


def _refine(control_points: list[ControlPoint], _pair: RegistrationPair) -> list[ControlPoint]:
    return control_points


def _register(
    pair: RegistrationPair, _control_points: list[ControlPoint], correspondences: CorrespondenceSet
) -> RegistrationResult:
    return RegistrationResult(pair_id=pair.pair_id, correspondences=correspondences)


def _evaluate(result: RegistrationResult, _pair: RegistrationPair) -> RegistrationResult:
    return result


def _export(
    _result: RegistrationResult, _pair: RegistrationPair, output_dir: Path
) -> ExportManifest:
    return ExportManifest(registration_report=str(output_dir / "registration_report.html"))


DOUBLES: dict[str, Callable[..., Any]] = {
    "ingest_product": _ingest,
    "characterize_pair": _characterize,
    "preprocess": _preprocess,
    "generate_representation": _representation,
    "match": _match,
    "verify_matches": _verify,
    "select_control_points": _select_cps,
    "refine_points": _refine,
    "register": _register,
    "evaluate": _evaluate,
    "export_result": _export,
}

EXPECTED_CALLS = [
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


def _tracked_ops() -> tuple[
    PipelineOperations, list[str], dict[str, tuple[Any, ...]], dict[str, Any]
]:
    calls: list[str] = []
    received: dict[str, tuple[Any, ...]] = {}
    returned: dict[str, Any] = {}

    def tracked(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            received[name] = args
            result = fn(*args, **kwargs)
            returned[name] = result
            return result

        return wrapper

    ops = PipelineOperations(
        **{name: tracked(name, fn) for name, fn in DOUBLES.items()}  # type: ignore[arg-type]
    )
    return ops, calls, received, returned


def test_pipeline_wires_operations_in_order(tmp_paths: tuple[Path, Path, Path]) -> None:
    source_path, reference_path, output_dir = tmp_paths
    ops, calls, received, returned = _tracked_ops()

    result, manifest = ScientificPipeline(ops).run(source_path, reference_path, output_dir)

    assert calls == EXPECTED_CALLS
    assert PIPELINE_STAGES == (
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
    assert calls.index("preprocess") == calls.index("characterize_pair") + 1
    assert calls.index("preprocess") == calls.index("generate_representation") - 1

    characterized = returned["characterize_pair"]
    preprocessed = returned["preprocess"]
    representation = returned["generate_representation"]
    matched = returned["match"]
    verified = returned["verify_matches"]
    selected = returned["select_control_points"]
    refined = returned["refine_points"]
    registered = returned["register"]
    evaluated = returned["evaluate"]

    assert isinstance(characterized, RegistrationPair)
    assert isinstance(preprocessed, RegistrationPair)
    assert isinstance(matched, CorrespondenceSet)
    assert isinstance(verified, CorrespondenceSet)
    assert isinstance(registered, RegistrationResult)
    assert isinstance(evaluated, RegistrationResult)

    assert received["characterize_pair"][0].product_id == source_path.stem
    assert received["characterize_pair"][1].product_id == reference_path.stem
    assert received["preprocess"][0] is characterized
    assert received["generate_representation"][0] is preprocessed
    assert received["match"][0] is preprocessed
    assert received["match"][1] is representation
    assert received["verify_matches"][0] is matched
    assert received["verify_matches"][1] is preprocessed
    assert received["select_control_points"][0] is verified
    assert received["select_control_points"][1] is preprocessed
    assert received["refine_points"][0] is selected
    assert received["register"][0] is preprocessed
    assert received["register"][1] is refined
    assert received["register"][2] is verified
    assert received["evaluate"][0] is registered
    assert received["evaluate"][0].correspondences is verified
    assert received["evaluate"][1] is preprocessed
    assert received["export_result"][0] is evaluated
    assert received["export_result"][0].correspondences is verified
    assert received["export_result"][1] is preprocessed

    assert result.pair_id == "wired-pair-preprocessed"
    assert result.correspondences is verified
    assert result.correspondences is received["register"][2]
    assert result.metrics is None
    assert result.transformation is None
    assert result.inliers == []
    assert result.confidence_class is None
    assert received["export_result"][1].pair_id == "wired-pair-preprocessed"
    assert received["export_result"][1].source.product_id == source_path.stem
    assert received["export_result"][1].reference.product_id == reference_path.stem
    assert manifest.registration_report is not None


def test_wiring_doubles_do_not_produce_scientific_values(
    tmp_paths: tuple[Path, Path, Path],
) -> None:
    source_path, reference_path, output_dir = tmp_paths
    ops, _calls, _received, _returned = _tracked_ops()
    result, manifest = ScientificPipeline(ops).run(source_path, reference_path, output_dir)

    assert result.metrics is None
    assert result.transformation is None
    assert result.registered_source_uri is None
    assert result.inliers == []
    assert result.control_points == []
    assert result.correspondences is not None
    assert result.correspondences.matches == []
    assert manifest.registered_source is None
    assert manifest.metrics is None
    assert manifest.transformation is None


def test_default_pipeline_fails_closed(tmp_paths: tuple[Path, Path, Path]) -> None:
    source_path, reference_path, output_dir = tmp_paths
    with pytest.raises(NotImplementedError):
        ScientificPipeline().run(source_path, reference_path, output_dir)


@pytest.mark.parametrize("fail_at", UNIMPLEMENTED_STAGES)
def test_unimplemented_stage_fails_closed_and_is_not_skipped(
    fail_at: str,
    tmp_paths: tuple[Path, Path, Path],
) -> None:
    source_path, reference_path, output_dir = tmp_paths
    calls: list[str] = []
    fail_index = PIPELINE_STAGES.index(fail_at)

    def wrap(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            return fn(*args, **kwargs)

        return wrapper

    bound: dict[str, Callable[..., Any]] = {}
    for index, name in enumerate(PIPELINE_STAGES):
        fn = STUBS[name] if index >= fail_index else DOUBLES[name]
        bound[name] = wrap(name, fn)

    ops = PipelineOperations(**bound)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        ScientificPipeline(ops).run(source_path, reference_path, output_dir)

    assert fail_at in calls
    for later in PIPELINE_STAGES[fail_index + 1 :]:
        assert later not in calls


def test_implemented_verify_and_control_points_run_then_later_stub_fails_closed(
    tmp_paths: tuple[Path, Path, Path],
) -> None:
    source_path, reference_path, output_dir = tmp_paths
    calls: list[str] = []
    verify_index = PIPELINE_STAGES.index("verify_matches")

    def wrap(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            return fn(*args, **kwargs)

        return wrapper

    bound: dict[str, Callable[..., Any]] = {}
    for index, name in enumerate(PIPELINE_STAGES):
        if name in IMPLEMENTED_STAGES:
            fn = STUBS[name]
        elif index < verify_index:
            fn = DOUBLES[name]
        else:
            fn = STUBS[name]
        bound[name] = wrap(name, fn)

    ops = PipelineOperations(**bound)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        ScientificPipeline(ops).run(source_path, reference_path, output_dir)

    assert "match" in calls
    assert "verify_matches" in calls
    assert "select_control_points" in calls
    assert "refine_points" in calls
    assert "register" in calls
    assert "evaluate" in calls
    assert "export_result" in calls


def test_implemented_register_runs_with_real_refine_points(
    tmp_paths: tuple[Path, Path, Path],
) -> None:
    source_path, reference_path, output_dir = tmp_paths
    calls: list[str] = []

    def wrap(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            return fn(*args, **kwargs)

        return wrapper

    bound: dict[str, Callable[..., Any]] = {}
    for name in PIPELINE_STAGES:
        if name in IMPLEMENTED_STAGES:
            fn = STUBS[name]
        elif PIPELINE_STAGES.index(name) < PIPELINE_STAGES.index("verify_matches"):
            fn = DOUBLES[name]
        else:
            fn = STUBS[name]
        bound[name] = wrap(name, fn)

    ops = PipelineOperations(**bound)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        ScientificPipeline(ops).run(source_path, reference_path, output_dir)

    assert "refine_points" in calls
    assert "register" in calls
    assert "evaluate" in calls
    assert "export_result" in calls


def test_wrong_stage_return_type_fails_closed(tmp_paths: tuple[Path, Path, Path]) -> None:
    source_path, reference_path, output_dir = tmp_paths

    def bad_ingest(_path: Path) -> LunarProduct:
        return "not-a-product"  # type: ignore[return-value]

    bound = dict(DOUBLES)
    bound["ingest_product"] = bad_ingest
    ops = PipelineOperations(**bound)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ingest_product"):
        ScientificPipeline(ops).run(source_path, reference_path, output_dir)


def test_default_pipeline_has_no_http_runtime_dependency() -> None:
    pipeline = ScientificPipeline()
    assert "http" not in type(pipeline).__module__.lower()
    assert pipeline.ops.ingest_product.__module__.startswith("src.")
    assert pipeline.ops.preprocess.__module__.startswith("src.")
    assert pipeline.ops.match.__module__.startswith("src.")
    assert pipeline.ops.register.__module__.startswith("src.")
