"""Export contract for registration outputs (v3 §22 recommended package)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path, PureWindowsPath
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationResult


class ExportManifest(BaseModel):
    """URIs for files listed in the v3 output contract.

    Paths are recorded only after a real exporter writes them.
    Names are logical; this contract does not assume image or table formats.
    """

    model_config = ConfigDict(extra="forbid")

    registered_source: str | None = None
    all_matches: str | None = None
    inliers: str | None = None
    control_points: str | None = None
    transformation: str | None = None
    metrics: str | None = None
    before: str | None = None
    matches_visualization: str | None = None
    overlay: str | None = None
    registration_report: str | None = None


def export_result(
    result: RegistrationResult, pair: RegistrationPair, output_dir: Path
) -> ExportManifest:
    """Write a portable, reproducible software-baseline result package.

    The manifest records package-relative POSIX paths.  Raw input paths are
    intentionally excluded so the package is portable and does not disclose
    machine-specific locations.  Missing outputs remain absent rather than
    being replaced with placeholders.
    """

    package = Path(output_dir)
    package.mkdir(parents=True, exist_ok=True)
    manifest = ExportManifest()
    warnings: list[str] = []

    if result.registered_source_uri:
        copied = _copy_registered_source(result.registered_source_uri, package, warnings)
        if copied is not None:
            manifest = manifest.model_copy(update={"registered_source": copied})

    if result.correspondences is not None:
        all_matches = "correspondences.json"
        _write_json(package / all_matches, result.correspondences.model_dump(mode="json"))
        manifest = manifest.model_copy(update={"all_matches": all_matches})
    if result.inliers:
        inliers = "inliers.json"
        _write_json(package / inliers, [item.model_dump(mode="json") for item in result.inliers])
        manifest = manifest.model_copy(update={"inliers": inliers})
    if result.control_points:
        control_points = "control_points.json"
        _write_json(
            package / control_points,
            [item.model_dump(mode="json") for item in result.control_points],
        )
        manifest = manifest.model_copy(update={"control_points": control_points})
    if result.transformation is not None:
        transformation = "transformation.json"
        _write_json(package / transformation, result.transformation.model_dump(mode="json"))
        manifest = manifest.model_copy(update={"transformation": transformation})
    if result.metrics is not None:
        metrics = "metrics.json"
        _write_json(package / metrics, result.metrics.model_dump(mode="json"))
        manifest = manifest.model_copy(update={"metrics": metrics})

    report = "registration_report.json"
    _write_json(package / report, _report(result, pair, manifest, warnings))
    return manifest.model_copy(update={"registration_report": report})


def _copy_registered_source(uri: str, package: Path, warnings: list[str]) -> str | None:
    source = Path(uri)
    if not source.is_file():
        warnings.append("registered_source_unavailable_for_export")
        return None
    suffix = source.suffix if source.suffix else ".bin"
    destination = package / f"registered_source{suffix.lower()}"
    try:
        shutil.copyfile(source, destination)
    except OSError:
        warnings.append("registered_source_copy_failed")
        return None
    return destination.name


def _report(
    result: RegistrationResult,
    pair: RegistrationPair,
    manifest: ExportManifest,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "package_format": "sih26166_registration_baseline_v1",
        "pair": {
            "pair_id": pair.pair_id,
            "source": _portable_product(pair.source.model_dump(mode="json")),
            "reference": _portable_product(pair.reference.model_dump(mode="json")),
            "characterization": (
                pair.characterization.model_dump(mode="json") if pair.characterization else None
            ),
        },
        "status": {
            "quality_flags": result.quality_flags,
            "registered_output_available": manifest.registered_source is not None,
            "evaluation_available": result.metrics is not None and result.metrics.rmse is not None,
            "export_warnings": warnings,
        },
        "configuration": {
            "matcher_id": result.correspondences.matcher_id if result.correspondences else None,
            "representation_id": (
                result.correspondences.representation_id if result.correspondences else None
            ),
            "transformation_model": (
                result.transformation.model_name if result.transformation else None
            ),
        },
        "manifest": manifest.model_dump(mode="json"),
        "provenance": _portable_provenance(result.provenance.model_dump(mode="json"))
        if result.provenance
        else None,
    }


def _portable_product(product: dict[str, Any]) -> dict[str, Any]:
    product.pop("raster_uri", None)
    product.pop("mask_uri", None)
    provenance = product.get("provenance")
    if isinstance(provenance, dict):
        product["provenance"] = _portable_provenance(provenance)
    return product


def _portable_provenance(provenance: dict[str, Any]) -> dict[str, Any]:
    source_uri = provenance.get("source_uri")
    if isinstance(source_uri, str):
        if _is_machine_absolute_path(source_uri):
            provenance["source_uri"] = PureWindowsPath(source_uri).name or Path(source_uri).name
    return provenance


def _is_machine_absolute_path(value: str) -> bool:
    """Recognize local absolute paths from either Windows or POSIX hosts."""

    return Path(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
