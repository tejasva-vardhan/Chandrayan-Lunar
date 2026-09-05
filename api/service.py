"""In-process registration job service wrapping ScientificPipeline."""

from __future__ import annotations

import shutil
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from api.catalog import (
    PAIR_01_MANIFEST_ID,
    catalog_product_id,
    instrument_hint_for,
    public_path_label,
    resolve_data_root_products,
    resolve_exp000_paths,
)
from api.errors import ApiError, classify_pipeline_exception
from api.preprocess_guard import PREPROCESS_IDENTITY_FLAG, guarded_preprocess
from api.preview import ensure_job_previews
from api.schemas import (
    CatalogStatusResponse,
    Exp000PairResponse,
    JobResultResponse,
    JobStatus,
    JobStatusResponse,
    PreviewCropDTO,
    ProductSummary,
    ProductUploadResponse,
    RegistrationResultDTO,
    VisualizationResponse,
)
from api.serialization import result_to_dto
from src.ingestion.data_root import DATA_ROOT_ENV, PAIR_01_LROC_ID, PAIR_01_OHRC_ID, DataRootError
from src.io.exports import ExportManifest
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationResult
from src.pipeline.orchestrator import PIPELINE_STAGES, PipelineOperations, ScientificPipeline

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORK_ROOT_ENV = "CHANDRAYAN_API_WORK_ROOT"


def _default_work_root() -> Path:
    """Prefer CHANDRAYAN_API_WORK_ROOT when set; else repo ``outputs/api``.

    On ephemeral hosts (for example Render) this directory is writable but not
    durable across restarts. Scientific datasets are never assumed to live here.
    """

    import os

    raw = os.environ.get(_WORK_ROOT_ENV)
    if raw and raw.strip():
        return Path(raw).expanduser()
    return _REPO_ROOT / "outputs" / "api"

# Formats accepted by default ingest_product (LROC PDS3 .IMG, OHRC PDS4 .zip/.xml).
ALLOWED_UPLOAD_SUFFIXES = {".img", ".zip", ".xml"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024 * 1024  # 8 GiB hard cap for multipart uploads


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
    warnings: list[str] = field(default_factory=list)
    preview_paths: dict[str, str] = field(default_factory=dict)
    preview_meta: dict[str, Any] = field(default_factory=dict)


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
        self.work_root = Path(work_root) if work_root is not None else _default_work_root()
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
            return [self._public_summary(item) for item in self._products.values()]

    def list_catalog(self) -> CatalogStatusResponse:
        """List demo_pairs products found under CHANDRAYAN_DATA_ROOT."""

        try:
            root, found = resolve_data_root_products()
        except DataRootError as exc:
            return CatalogStatusResponse(
                data_root_configured=False,
                product_count=0,
                products=[],
                message=str(exc),
            )
        if root is None:
            return CatalogStatusResponse(
                data_root_configured=False,
                product_count=0,
                products=[],
                message=(
                    f"{DATA_ROOT_ENV} is not set. Configure it to enable "
                    "SELECT EXISTING PRODUCT from the local SIH dataset."
                ),
            )
        products = [
            self._ensure_catalog_product(logical_id, path, data_root=root)
            for logical_id, path in found
        ]
        return CatalogStatusResponse(
            data_root_configured=True,
            product_count=len(products),
            products=[self._public_summary(item) for item in products],
            message=(
                None
                if products
                else "Data root is configured but no declared products were found."
            ),
        )

    def resolve_exp000_pair(self) -> Exp000PairResponse:
        """Register the real EXP-000 pair_01 products from the data root."""

        try:
            root, ohrc, lroc = resolve_exp000_paths()
        except DataRootError as exc:
            return Exp000PairResponse(available=False, message=str(exc))
        if root is None:
            return Exp000PairResponse(
                available=False,
                message=(
                    f"{DATA_ROOT_ENV} is not set. "
                    "Set it to the external SIH dataset root to load the real EXP-000 pair."
                ),
            )
        if ohrc is None or lroc is None:
            missing = []
            if ohrc is None:
                missing.append("OHRC pair_01 product")
            if lroc is None:
                missing.append("LROC pair_01 product")
            return Exp000PairResponse(
                available=False,
                message=(
                    f"EXP-000 products not found under {DATA_ROOT_ENV}: "
                    + ", ".join(missing)
                ),
            )
        source = self._ensure_catalog_product(PAIR_01_OHRC_ID, ohrc, data_root=root)
        reference = self._ensure_catalog_product(PAIR_01_LROC_ID, lroc, data_root=root)
        return Exp000PairResponse(
            available=True,
            pair_id=PAIR_01_MANIFEST_ID,
            source=self._public_summary(source),
            reference=self._public_summary(reference),
            message=None,
        )

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
            logical_id=resolved.name,
            instrument_hint=instrument_hint_for(resolved.stem),
        )
        with self._lock:
            self._products[product_id] = summary
        return self._public_summary(summary)

    def store_upload(self, *, filename: str, data: bytes) -> ProductUploadResponse:
        safe_name = self._validate_upload_filename(filename)
        if not data:
            raise ApiError(code="invalid_input", message="Uploaded file is empty.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ApiError(
                code="invalid_input",
                message=f"Uploaded file exceeds the {MAX_UPLOAD_BYTES} byte limit.",
            )
        product_id, target = self._prepare_upload_target(safe_name)
        try:
            target.write_bytes(data)
            return self._commit_upload(product_id, target, safe_name, len(data))
        except Exception:
            shutil.rmtree(target.parent, ignore_errors=True)
            raise

    def store_upload_stream(
        self, *, filename: str, stream: BinaryIO, chunk_size: int = 1024 * 1024
    ) -> ProductUploadResponse:
        """Stream an upload to disk without holding the full raster in memory."""

        safe_name = self._validate_upload_filename(filename)
        product_id, target = self._prepare_upload_target(safe_name)
        size = 0
        try:
            with target.open("wb") as out:
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise ApiError(
                            code="invalid_input",
                            message=f"Uploaded file exceeds the {MAX_UPLOAD_BYTES} byte limit.",
                        )
                    out.write(chunk)
            if size == 0:
                raise ApiError(code="invalid_input", message="Uploaded file is empty.")
            return self._commit_upload(product_id, target, safe_name, size)
        except Exception:
            shutil.rmtree(target.parent, ignore_errors=True)
            raise

    def store_upload_chunks(
        self, *, filename: str, chunks: Iterator[bytes]
    ) -> ProductUploadResponse:
        safe_name = self._validate_upload_filename(filename)
        product_id, target = self._prepare_upload_target(safe_name)
        size = 0
        try:
            with target.open("wb") as out:
                for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise ApiError(
                            code="invalid_input",
                            message=f"Uploaded file exceeds the {MAX_UPLOAD_BYTES} byte limit.",
                        )
                    out.write(chunk)
            if size == 0:
                raise ApiError(code="invalid_input", message="Uploaded file is empty.")
            return self._commit_upload(product_id, target, safe_name, size)
        except Exception:
            shutil.rmtree(target.parent, ignore_errors=True)
            raise

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
        if record.status == "completed" and record.result is not None and record.pair is not None:
            self._attach_preview_metadata(record)
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

    def get_visualization(self, job_id: str) -> VisualizationResponse:
        record = self._require_job(job_id)
        if record.status != "completed" or record.result is None or record.pair is None:
            raise ApiError(
                code="result_unavailable",
                message=f"Visualization unavailable for job {job_id}.",
                status_code=404,
                details=record.error,
            )
        meta = self._ensure_previews(record)
        if not meta.get("available"):
            return VisualizationResponse(
                available=False,
                mode=str(meta.get("mode") or "unavailable"),
                reference_url=None,
                registered_source_url=None,
                note=str(meta.get("note") or "Overlay preview unavailable."),
            )
        return VisualizationResponse(
            available=True,
            mode=str(meta.get("mode") or "diagnostic_crop"),
            reference_url=f"/registration/jobs/{job_id}/artifacts/preview_reference",
            registered_source_url=(
                f"/registration/jobs/{job_id}/artifacts/preview_registered"
            ),
            note=str(meta.get("note") or ""),
        )

    def resolve_artifact(self, job_id: str, name: str) -> Path:
        record = self._require_job(job_id)
        if record.status != "completed" or record.result is None:
            raise ApiError(
                code="result_unavailable",
                message=f"Artifact unavailable for job {job_id}.",
                status_code=404,
                details=record.error,
            )
        if name in {"preview_reference", "preview_registered", "preview_source"}:
            self._ensure_previews(record)
            mapped = record.preview_paths.get(name)
            if not mapped:
                raise ApiError(
                    code="artifact_unavailable",
                    message=f"Preview artifact {name!r} is not available for job {job_id}.",
                    status_code=404,
                )
            path = Path(mapped)
            if not path.is_file():
                raise ApiError(
                    code="artifact_unavailable",
                    message=f"Preview file missing: {path.name}",
                    status_code=404,
                )
            return path

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
                message=f"Artifact file missing: {path.name}",
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
        pipeline = ScientificPipeline(self._capturing_ops(captured, record))

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
            # Keep status=running while diagnostic previews build so clients do
            # not snapshot result.preview_available=false and skip the overlay.
            self._touch(
                record,
                result=result,
                result_dto=dto,
                pair=pair,
                manifest=manifest,
                completed_stages=completed,
                runtime_seconds=runtime,
                error=None,
            )
            self._annotate_scientific_outcome(record)
            self._attach_preview_metadata(record)
            self._touch(
                record,
                status="completed",
                current_stage=None,
                completed_stages=completed,
                runtime_seconds=runtime,
                error=None,
            )
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

    def _ensure_previews(self, record: _JobRecord) -> dict[str, Any]:
        if (
            record.preview_meta.get("available")
            and record.preview_paths
            and (
                record.preview_meta.get("source_crop") is not None
                or record.preview_meta.get("reference_crop") is not None
            )
        ):
            return record.preview_meta
        if record.pair is None or record.result is None:
            return {
                "available": False,
                "mode": "unavailable",
                "note": "Overlay preview unavailable.",
            }
        # If PNG paths already exist but crop meta is missing, rebuild meta only.
        if record.preview_meta.get("available") and record.preview_paths:
            try:
                refreshed = ensure_job_previews(record.pair, record.result, record.output_dir)
                record.preview_meta = {
                    **record.preview_meta,
                    "source_crop": refreshed.get("source_crop"),
                    "reference_crop": refreshed.get("reference_crop"),
                    "mode": refreshed.get("mode", record.preview_meta.get("mode")),
                    "note": refreshed.get("note", record.preview_meta.get("note")),
                }
                return record.preview_meta
            except Exception:  # noqa: BLE001
                return record.preview_meta
        try:
            meta = ensure_job_previews(record.pair, record.result, record.output_dir)
        except Exception as exc:  # noqa: BLE001 — preview is best-effort viewing aid
            meta = {
                "available": False,
                "mode": "unavailable",
                "note": f"Overlay preview failed: {exc}",
                "reference_path": None,
                "registered_path": None,
            }
        paths: dict[str, str] = {}
        ref = meta.get("reference_path")
        reg = meta.get("registered_path")
        src = meta.get("source_path")
        if ref is not None:
            paths["preview_reference"] = str(ref)
        if reg is not None:
            paths["preview_registered"] = str(reg)
        if src is not None:
            paths["preview_source"] = str(src)
        record.preview_paths = paths
        record.preview_meta = {
            "available": bool(meta.get("available")),
            "mode": meta.get("mode"),
            "note": meta.get("note"),
            "source_crop": meta.get("source_crop"),
            "reference_crop": meta.get("reference_crop"),
        }
        return record.preview_meta

    def _attach_preview_metadata(self, record: _JobRecord) -> None:
        meta = self._ensure_previews(record)
        dto = record.result_dto
        if dto is None:
            return
        dto.preview_available = bool(meta.get("available"))
        dto.preview_mode = str(meta.get("mode")) if meta.get("mode") else None
        dto.preview_note = str(meta.get("note")) if meta.get("note") else None
        src_crop = meta.get("source_crop")
        ref_crop = meta.get("reference_crop")
        dto.preview_source_crop = (
            PreviewCropDTO.model_validate(src_crop) if isinstance(src_crop, dict) else None
        )
        dto.preview_reference_crop = (
            PreviewCropDTO.model_validate(ref_crop) if isinstance(ref_crop, dict) else None
        )

    def _capturing_ops(self, captured: dict[str, Any], record: _JobRecord) -> PipelineOperations:
        from src.pipeline.orchestrator import default_operations

        base = self._ops or default_operations()

        def preprocess(pair: RegistrationPair) -> RegistrationPair:
            def on_identity(warning: str) -> None:
                record.warnings.append(warning)
                captured["preprocess_identity"] = True

            out = guarded_preprocess(pair, base.preprocess, on_identity=on_identity)
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
        if any("identity passthrough" in warning for warning in record.warnings):
            notes.append(PREPROCESS_IDENTITY_FLAG)
        if notes:
            dto.quality_flags = list(dict.fromkeys([*dto.quality_flags, *notes]))
        if record.warnings and dto.evaluation_limitation is None:
            dto.evaluation_limitation = record.warnings[0]
        elif record.warnings:
            dto.evaluation_limitation = (
                f"{dto.evaluation_limitation} | {record.warnings[0]}"
                if dto.evaluation_limitation
                else record.warnings[0]
            )

    def _ensure_catalog_product(
        self,
        logical_id: str,
        path: Path,
        *,
        data_root: Path,
    ) -> ProductSummary:
        product_id = catalog_product_id(logical_id)
        resolved = path.expanduser().resolve()
        summary = ProductSummary(
            product_id=product_id,
            path=str(resolved),
            origin="data_root",
            filename=path.name,
            logical_id=logical_id,
            instrument_hint=instrument_hint_for(logical_id),
        )
        with self._lock:
            self._products[product_id] = summary
        # Attach public label only on copies returned to callers.
        _ = data_root
        return summary

    def _public_summary(self, summary: ProductSummary) -> ProductSummary:
        """Return a copy safe for HTTP (no absolute local filesystem paths)."""

        if summary.origin == "data_root":
            try:
                root, _ = resolve_data_root_products()
            except DataRootError:
                root = None
            label = public_path_label(Path(summary.path), data_root=root)
            return summary.model_copy(update={"path": label})
        if summary.origin == "upload":
            return summary.model_copy(
                update={"path": f"<upload>/{summary.filename or summary.product_id}"}
            )
        # Explicit path inputs may still be needed by power-user clients; redact to basename.
        return summary.model_copy(update={"path": Path(summary.path).name})

    def begin_upload(self, filename: str) -> tuple[str, Path]:
        """Validate filename and reserve an on-disk upload target."""

        safe_name = self._validate_upload_filename(filename)
        return self._prepare_upload_target(safe_name)

    def finish_upload(
        self, *, product_id: str, target: Path, filename: str, nbytes: int
    ) -> ProductUploadResponse:
        if nbytes <= 0:
            raise ApiError(code="invalid_input", message="Uploaded file is empty.")
        return self._commit_upload(product_id, target, filename, nbytes)

    def _validate_upload_filename(self, filename: str) -> str:
        if not filename or not filename.strip():
            raise ApiError(code="invalid_input", message="Uploaded file must have a name.")
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            allowed = ", ".join(sorted(ALLOWED_UPLOAD_SUFFIXES))
            raise ApiError(
                code="unsupported_product",
                message=(
                    f"Unsupported upload extension {suffix!r}. "
                    f"Accepted product packages: {allowed} "
                    "(OHRC PDS4 .zip/.xml with sibling imagery, or LROC PDS3 .IMG)."
                ),
            )
        return safe_name

    def _prepare_upload_target(self, safe_name: str) -> tuple[str, Path]:
        product_id = f"upload-{uuid.uuid4().hex[:12]}"
        target_dir = self.products_dir / product_id
        target_dir.mkdir(parents=True, exist_ok=True)
        return product_id, target_dir / safe_name

    def _commit_upload(
        self, product_id: str, target: Path, safe_name: str, nbytes: int
    ) -> ProductUploadResponse:
        summary = ProductSummary(
            product_id=product_id,
            path=str(target.resolve()),
            origin="upload",
            filename=safe_name,
            logical_id=Path(safe_name).stem,
            instrument_hint=instrument_hint_for(Path(safe_name).stem),
        )
        with self._lock:
            self._products[product_id] = summary
        return ProductUploadResponse(
            product_id=product_id,
            stored_path=f"<upload>/{safe_name}",
            filename=safe_name,
            bytes=nbytes,
        )
