"""In-process registration job service wrapping ScientificPipeline."""

from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.errors import ApiError, classify_pipeline_exception
from api.schemas import (
    JobResultResponse,
    JobStatus,
    JobStatusResponse,
    ProductSummary,
    ProductUploadResponse,
    RegistrationResultDTO,
)
from api.serialization import result_to_dto
from src.io.exports import ExportManifest
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationResult
from src.pipeline.orchestrator import PIPELINE_STAGES, PipelineOperations, ScientificPipeline

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_WORK_ROOT = _REPO_ROOT / "outputs" / "api"


@dataclass
class _JobRecord:
    job_id: str
    source_path: Path
    reference_path: Path
    output_dir: Path
    status: JobStatus = "queued"
    current_stage: str | None = None
    completed_stages: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
    result_dto: RegistrationResultDTO | None = None
    result: RegistrationResult | None = None
    pair: RegistrationPair | None = None
    manifest: ExportManifest | None = None
    created_at: str = field(default_factory=lambda: _now())
    updated_at: str = field(default_factory=lambda: _now())
    runtime_seconds: float | None = None
    wall_start: float | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RegistrationService:
    """Thin application service: store uploads, run pipeline, expose job state."""

    def __init__(
        self,
        *,
        work_root: Path | None = None,
        ops: PipelineOperations | None = None,
        run_inline: bool = False,
    ) -> None:
        self.work_root = Path(work_root) if work_root is not None else _DEFAULT_WORK_ROOT
        self.products_dir = self.work_root / "products"
        self.jobs_dir = self.work_root / "jobs"
        self.products_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._ops = ops
        self._run_inline = run_inline
        self._lock = threading.RLock()
        self._jobs: dict[str, _JobRecord] = {}
        self._products: dict[str, ProductSummary] = {}

    def list_products(self) -> list[ProductSummary]:
        with self._lock:
            return list(self._products.values())

    def register_local_path(self, path: Path, *, origin: str = "path") -> ProductSummary:
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            raise ApiError(
                code="missing_input",
                message=f"Product path does not exist: {resolved}",
                status_code=400,
            )
        product_id = f"path-{uuid.uuid4().hex[:12]}"
        summary = ProductSummary(
            product_id=product_id,
            path=str(resolved),
            origin=origin if origin in {"upload", "path", "data_root"} else "path",
            filename=resolved.name,
        )
        with self._lock:
            self._products[product_id] = summary
        return summary

    def store_upload(self, *, filename: str, data: bytes) -> ProductUploadResponse:
        if not filename.strip():
            raise ApiError(code="invalid_input", message="Uploaded file must have a name.")
        if not data:
            raise ApiError(code="invalid_input", message="Uploaded file is empty.")
        product_id = f"upload-{uuid.uuid4().hex[:12]}"
        target_dir = self.products_dir / product_id
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name
        target = target_dir / safe_name
        target.write_bytes(data)
        summary = ProductSummary(
            product_id=product_id,
            path=str(target.resolve()),
            origin="upload",
            filename=safe_name,
        )
        with self._lock:
            self._products[product_id] = summary
        return ProductUploadResponse(
            product_id=product_id,
            stored_path=str(target.resolve()),
            filename=safe_name,
            bytes=len(data),
        )

    def create_job(
        self,
        *,
        source_product_id: str | None = None,
        reference_product_id: str | None = None,
        source_path: str | None = None,
        reference_path: str | None = None,
    ) -> JobStatusResponse:
        source = self._resolve_input(
            product_id=source_product_id, path=source_path, role="source"
        )
        reference = self._resolve_input(
            product_id=reference_product_id, path=reference_path, role="reference"
        )
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        output_dir = self.jobs_dir / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        record = _JobRecord(
            job_id=job_id,
            source_path=source,
            reference_path=reference,
            output_dir=output_dir,
        )
        with self._lock:
            self._jobs[job_id] = record
        if self._run_inline:
            self._execute_job(job_id)
        else:
            thread = threading.Thread(
                target=self._execute_job, args=(job_id,), name=f"reg-{job_id}", daemon=True
            )
            thread.start()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> JobStatusResponse:
        record = self._require_job(job_id)
        return JobStatusResponse(
            job_id=record.job_id,
            status=record.status,
            current_stage=record.current_stage,
            completed_stages=list(record.completed_stages),
            stages=list(PIPELINE_STAGES),
            error=record.error,
            created_at=record.created_at,
            updated_at=record.updated_at,
            runtime_seconds=record.runtime_seconds,
        )

    def get_result(self, job_id: str) -> JobResultResponse:
        record = self._require_job(job_id)
        if record.status == "queued" or record.status == "running":
            raise ApiError(
                code="result_not_ready",
                message=f"Job {job_id} is still {record.status}.",
                status_code=409,
            )
        return JobResultResponse(
            job_id=record.job_id,
            status=record.status,
            result=record.result_dto,
            error=record.error,
        )

    def get_metrics(self, job_id: str) -> dict[str, Any]:
        payload = self.get_result(job_id)
        if payload.result is None:
            raise ApiError(
                code="result_unavailable",
                message=f"No metrics for job {job_id}.",
                status_code=404,
                details=payload.error,
            )
        metrics = payload.result.metrics
        if metrics is None:
            raise ApiError(
                code="result_unavailable",
                message=f"Job {job_id} completed without metrics.",
                status_code=404,
            )
        return metrics.model_dump(mode="json")

    def resolve_artifact(self, job_id: str, name: str) -> Path:
        record = self._require_job(job_id)
        if record.status != "completed" or record.result is None:
            raise ApiError(
                code="result_unavailable",
                message=f"Artifact unavailable for job {job_id}.",
                status_code=404,
                details=record.error,
            )
        mapping: dict[str, str | None] = {}
        if record.manifest is not None:
            mapping.update(record.manifest.model_dump(mode="json"))
        mapping["registered_source"] = record.result.registered_source_uri
        uri = mapping.get(name)
        if not uri:
            raise ApiError(
                code="artifact_unavailable",
                message=f"Artifact {name!r} is not available for job {job_id}.",
                status_code=404,
            )
        path = Path(uri)
        if not path.is_file():
            raise ApiError(
                code="artifact_unavailable",
                message=f"Artifact file missing: {path}",
                status_code=404,
            )
        return path

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
            self._products.clear()
        if self.work_root.exists():
            shutil.rmtree(self.work_root, ignore_errors=True)
        self.products_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_input(
        self, *, product_id: str | None, path: str | None, role: str
    ) -> Path:
        if product_id and path:
            raise ApiError(
                code="invalid_input",
                message=f"Provide only one of {role}_product_id or {role}_path.",
            )
        if product_id:
            with self._lock:
                summary = self._products.get(product_id)
            if summary is None:
                raise ApiError(
                    code="invalid_input",
                    message=f"Unknown {role} product_id={product_id!r}. Upload it first.",
                )
            resolved = Path(summary.path)
        elif path:
            resolved = Path(path).expanduser().resolve()
        else:
            raise ApiError(
                code="invalid_input",
                message=f"Missing {role} input. Provide {role}_product_id or {role}_path.",
            )
        if not resolved.exists():
            raise ApiError(
                code="missing_input",
                message=f"{role} path does not exist: {resolved}",
            )
        return resolved

    def _require_job(self, job_id: str) -> _JobRecord:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            raise ApiError(
                code="invalid_input",
                message=f"Unknown job_id={job_id!r}.",
                status_code=404,
            )
        return record

    def _touch(self, record: _JobRecord, **updates: Any) -> None:
        with self._lock:
            for key, value in updates.items():
                setattr(record, key, value)
            record.updated_at = _now()

    def _execute_job(self, job_id: str) -> None:
        record = self._require_job(job_id)
        self._touch(record, status="running", wall_start=time.perf_counter(), current_stage=None)
        captured: dict[str, Any] = {"pair": None}
        pipeline = ScientificPipeline(self._capturing_ops(captured))

        def on_stage(stage: str) -> None:
            completed = list(record.completed_stages)
            if record.current_stage and record.current_stage not in completed:
                completed.append(record.current_stage)
            self._touch(record, current_stage=stage, completed_stages=completed)

        try:
            result, manifest = pipeline.run(
                record.source_path,
                record.reference_path,
                record.output_dir,
                on_stage=on_stage,
            )
            pair = captured["pair"]
            if not isinstance(pair, RegistrationPair):
                raise RuntimeError("pipeline completed without capturing RegistrationPair")
            runtime = None
            if record.wall_start is not None:
                runtime = time.perf_counter() - record.wall_start
            dto = result_to_dto(result, pair, manifest=manifest, runtime_seconds=runtime)
            completed = list(PIPELINE_STAGES)
            self._touch(
                record,
                status="completed",
                current_stage=None,
                completed_stages=completed,
                result=result,
                result_dto=dto,
                pair=pair,
                manifest=manifest,
                runtime_seconds=runtime,
                error=None,
            )
            self._annotate_scientific_outcome(record)
        except Exception as exc:  # noqa: BLE001 — boundary: convert to API error payload
            api_error = classify_pipeline_exception(exc)
            runtime = None
            if record.wall_start is not None:
                runtime = time.perf_counter() - record.wall_start
            completed = list(record.completed_stages)
            if record.current_stage and record.current_stage not in completed:
                completed.append(record.current_stage)
            self._touch(
                record,
                status="failed",
                completed_stages=completed,
                runtime_seconds=runtime,
                error={
                    "code": api_error.code,
                    "message": api_error.message,
                    "details": api_error.details or {},
                    "failed_stage": record.current_stage,
                },
            )

    def _capturing_ops(self, captured: dict[str, Any]) -> PipelineOperations:
        from src.pipeline.orchestrator import default_operations

        base = self._ops or default_operations()

        def preprocess(pair: RegistrationPair) -> RegistrationPair:
            out = base.preprocess(pair)
            captured["pair"] = out
            return out

        def characterize(source, reference) -> RegistrationPair:
            pair = base.characterize_pair(source, reference)
            captured["pair"] = pair
            return pair

        return PipelineOperations(
            ingest_product=base.ingest_product,
            characterize_pair=characterize,
            preprocess=preprocess,
            generate_representation=base.generate_representation,
            match=base.match,
            verify_matches=base.verify_matches,
            select_control_points=base.select_control_points,
            refine_points=base.refine_points,
            register=base.register,
            evaluate=base.evaluate,
            export_result=base.export_result,
        )

    def _annotate_scientific_outcome(self, record: _JobRecord) -> None:
        dto = record.result_dto
        result = record.result
        if dto is None or result is None:
            return
        notes: list[str] = []
        if dto.candidate_correspondences == 0:
            notes.append("no_correspondences")
        if dto.verified_inliers == 0 and dto.candidate_correspondences > 0:
            notes.append("insufficient_verified_matches")
        for flag in result.quality_flags:
            if flag not in notes:
                notes.append(flag)
        if notes:
            dto.quality_flags = list(dict.fromkeys([*dto.quality_flags, *notes]))
