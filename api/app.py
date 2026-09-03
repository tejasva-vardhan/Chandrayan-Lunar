"""FastAPI application: thin HTTP wrapper around RegistrationService."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from api.errors import ApiError
from api.schemas import (
    CreateJobRequest,
    HealthResponse,
    JobResultResponse,
    JobStatusResponse,
    ProductSummary,
    ProductUploadResponse,
    VisualizationResponse,
)
from api.service import RegistrationService
from src.pipeline.orchestrator import PIPELINE_STAGES


def create_app(service: RegistrationService | None = None) -> FastAPI:
    app = FastAPI(
        title="SIH26166 Registration API",
        description=(
            "HTTP wrapper around the scientific registration pipeline. "
            "Scientific algorithms remain in src/; this layer does not reimplement them."
        ),
        version="0.1.0",
    )
    app.state.service = service or RegistrationService()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details or {},
            },
        )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(pipeline_stages=list(PIPELINE_STAGES))

    @app.post("/products", response_model=ProductUploadResponse)
    async def upload_product(file: UploadFile = File(...)) -> ProductUploadResponse:
        data = await file.read()
        return app.state.service.store_upload(
            filename=file.filename or "upload.bin",
            data=data,
        )

    @app.get("/products", response_model=list[ProductSummary])
    def list_products() -> list[ProductSummary]:
        return app.state.service.list_products()

    @app.post("/registration/jobs", response_model=JobStatusResponse)
    def create_job(body: CreateJobRequest) -> JobStatusResponse:
        return app.state.service.create_job(
            source_product_id=body.source_product_id,
            reference_product_id=body.reference_product_id,
            source_path=body.source_path,
            reference_path=body.reference_path,
        )

    @app.get("/registration/jobs/{job_id}", response_model=JobStatusResponse)
    def get_job(job_id: str) -> JobStatusResponse:
        return app.state.service.get_job(job_id)

    @app.get("/registration/jobs/{job_id}/result", response_model=JobResultResponse)
    def get_result(job_id: str) -> JobResultResponse:
        return app.state.service.get_result(job_id)

    @app.get("/registration/jobs/{job_id}/metrics")
    def get_metrics(job_id: str) -> dict[str, Any]:
        return app.state.service.get_metrics(job_id)

    @app.get("/registration/jobs/{job_id}/visualization", response_model=VisualizationResponse)
    def get_visualization(job_id: str) -> VisualizationResponse:
        return app.state.service.get_visualization(job_id)

    @app.get("/registration/jobs/{job_id}/artifacts/{name}")
    def get_artifact(job_id: str, name: str) -> FileResponse:
        path = app.state.service.resolve_artifact(job_id, name)
        return FileResponse(path, filename=Path(path).name)

    return app
