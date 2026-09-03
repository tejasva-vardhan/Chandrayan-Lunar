"""End-to-end API smoke: HTTP → ScientificPipeline → RegistrationResult DTO.

Uses synthetic .npy products with a path-only ingest adapter. Downstream stages
are the real scientific implementations (not HTTP mocks).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.service import RegistrationService
from src.models.common import ImageDimensions
from src.models.lunar_product import LunarProduct
from src.pipeline.orchestrator import PipelineOperations, default_operations

pytestmark = pytest.mark.wiring


def _ops() -> PipelineOperations:
    base = default_operations()

    def ingest(path: Path) -> LunarProduct:
        array = np.load(path)
        h, w = array.shape[:2]
        return LunarProduct(
            product_id=path.stem,
            instrument="SYNTHETIC",
            dimensions=ImageDimensions(width_px=int(w), height_px=int(h)),
            raster_uri=str(path),
        )

    return PipelineOperations(
        ingest_product=ingest,
        characterize_pair=base.characterize_pair,
        preprocess=base.preprocess,
        generate_representation=base.generate_representation,
        match=base.match,
        verify_matches=base.verify_matches,
        select_control_points=base.select_control_points,
        refine_points=base.refine_points,
        register=base.register,
        evaluate=base.evaluate,
        export_result=base.export_result,
    )


def test_http_to_pipeline_smoke(tmp_path: Path) -> None:
    rng = np.random.default_rng(11)
    image = np.zeros((256, 256), dtype=np.float32)
    for _ in range(35):
        cv2.circle(
            image,
            (int(rng.integers(20, 236)), int(rng.integers(20, 236))),
            int(rng.integers(8, 24)),
            float(rng.uniform(0.3, 1.0)),
            -1,
        )
    image = np.clip(image + rng.normal(0, 0.02, image.shape).astype(np.float32), 0, 1)
    source = tmp_path / "smoke_source.npy"
    reference = tmp_path / "smoke_reference.npy"
    np.save(source, image)
    np.save(reference, image)

    service = RegistrationService(
        work_root=tmp_path / "api-work",
        ops=_ops(),
        run_inline=True,
    )
    app = create_app(service)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        created = client.post(
            "/registration/jobs",
            json={"source_path": str(source), "reference_path": str(reference)},
        )
        assert created.status_code == 200
        job = created.json()
        assert job["status"] == "completed"
        assert job["runtime_seconds"] is not None

        status = client.get(f"/registration/jobs/{job['job_id']}")
        assert status.json()["completed_stages"][-1] == "export_result"

        result = client.get(f"/registration/jobs/{job['job_id']}/result").json()
        assert result["result"]["pair_id"]
        assert result["result"]["candidate_correspondences"] >= 4
        assert result["result"]["metrics"]["verification_residual_rmse_label"] == (
            "Verification residual RMSE"
        )
        # Prove export artifacts were written by the real export_result stage.
        report = result["result"]["export_manifest"]["registration_report"]
        assert report is not None
        assert Path(report).is_file()
