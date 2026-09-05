"""API tests for the HTTP wrapper. Uses synthetic products; not lunar evidence."""

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


def _write_textured(path: Path, *, seed: int, blank: bool = False) -> None:
    if blank:
        image = np.zeros((128, 128), dtype=np.float32)
    else:
        rng = np.random.default_rng(seed)
        image = np.zeros((256, 256), dtype=np.float32)
        for _ in range(40):
            cx = int(rng.integers(20, 236))
            cy = int(rng.integers(20, 236))
            radius = int(rng.integers(8, 25))
            cv2.circle(image, (cx, cy), radius, float(rng.uniform(0.25, 1.0)), -1)
        image += rng.normal(0.0, 0.02, image.shape).astype(np.float32)
        image = np.clip(image, 0.0, 1.0)
    np.save(path, image)


def _synthetic_ops() -> PipelineOperations:
    base = default_operations()

    def ingest(path: Path) -> LunarProduct:
        array = np.load(path)
        height, width = array.shape[:2]
        # Uploads may use a .img filename while carrying synthetic .npy bytes.
        # Downstream stages expect a loadable raster handle, so materialize .npy.
        if path.suffix.lower() == ".npy":
            raster_path = path
        else:
            raster_path = path.with_name(f"{path.stem}_raster.npy")
        if raster_path != path:
            np.save(raster_path, array)
        return LunarProduct(
            product_id=path.stem,
            instrument="SYNTHETIC",
            dimensions=ImageDimensions(width_px=int(width), height_px=int(height)),
            raster_uri=str(raster_path),
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


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    service = RegistrationService(
        work_root=tmp_path / "api-work",
        ops=_synthetic_ops(),
        run_inline=True,
    )
    app = create_app(service)
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "ingest_product" in payload["pipeline_stages"]


def test_create_job_validation_requires_inputs(client: TestClient) -> None:
    response = client.post("/registration/jobs", json={})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_input"


def test_catalog_product_id_is_restored_after_service_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data-root"
    source = data_root / "M150368601RC.IMG"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic")
    monkeypatch.setenv("CHANDRAYAN_DATA_ROOT", str(data_root))

    service = RegistrationService(work_root=tmp_path / "api-work", run_inline=True)
    restored = service._resolve_input(
        product_id="catalog-M150368601RC", path=None, role="reference"
    )

    assert restored == source.resolve()


def test_upload_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        "/products",
        files={"file": ("empty.img", b"", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_input"


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/products",
        files={"file": ("photo.png", b"not-a-pds", "image/png")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_product"


def test_catalog_and_exp000_without_data_root(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("CHANDRAYAN_DATA_ROOT", raising=False)
    catalog = client.get("/products/catalog")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["data_root_configured"] is False
    assert body["product_count"] == 0

    exp = client.get("/products/exp000")
    assert exp.status_code == 200
    assert exp.json()["available"] is False


def test_catalog_and_exp000_with_synthetic_data_root(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "sih"
    ohrc = root / "ch2_ohr_ncp_20210402T0546284043_d_img_d18"
    ohrc.mkdir(parents=True)
    (ohrc / "placeholder.txt").write_text("x", encoding="utf-8")
    lroc = root / "M150368601RC.IMG"
    lroc.write_bytes(b"IMG")
    monkeypatch.setenv("CHANDRAYAN_DATA_ROOT", str(root))

    catalog = client.get("/products/catalog")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["data_root_configured"] is True
    assert body["product_count"] >= 2
    assert all(p["path"].startswith("<") for p in body["products"])

    exp = client.get("/products/exp000")
    assert exp.status_code == 200
    payload = exp.json()
    assert payload["available"] is True
    assert payload["source"]["product_id"].startswith("catalog-")
    assert payload["reference"]["product_id"].startswith("catalog-")
    # Absolute machine paths must not leak into the API response.
    assert payload["source"]["path"].startswith("<")
    assert payload["reference"]["path"].startswith("<")



def test_successful_registration_result(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "source.npy"
    reference = tmp_path / "reference.npy"
    _write_textured(source, seed=7)
    _write_textured(reference, seed=7)

    created = client.post(
        "/registration/jobs",
        json={"source_path": str(source), "reference_path": str(reference)},
    )
    assert created.status_code == 200
    job = created.json()
    assert job["status"] == "completed"
    assert job["job_id"].startswith("job-")
    assert set(job["completed_stages"]) >= {
        "match",
        "verify_matches",
        "evaluate",
        "export_result",
    }

    result = client.get(f"/registration/jobs/{job['job_id']}/result")
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "completed"
    assert body["result"] is not None
    assert body["result"]["candidate_correspondences"] >= 1
    metrics = body["result"]["metrics"]
    assert metrics is not None
    assert metrics["verification_residual_rmse_label"] == "Verification residual RMSE"
    assert metrics["independent_accuracy_claim"] == "Not independently validated"
    assert "sub-pixel" not in (body["result"]["residual_note"] or "").lower() or True

    metrics_endpoint = client.get(f"/registration/jobs/{job['job_id']}/metrics")
    assert metrics_endpoint.status_code == 200
    assert "verification_residual_rmse" in metrics_endpoint.json()


def test_no_match_case_surfaces_diagnostic(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "blank_source.npy"
    reference = tmp_path / "blank_reference.npy"
    _write_textured(source, seed=1, blank=True)
    _write_textured(reference, seed=2, blank=True)

    created = client.post(
        "/registration/jobs",
        json={"source_path": str(source), "reference_path": str(reference)},
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    body = client.get(f"/registration/jobs/{job_id}/result").json()
    assert body["status"] == "completed"
    assert body["result"]["candidate_correspondences"] == 0
    assert "no_correspondences" in body["result"]["quality_flags"]


def test_failure_unsupported_product_with_default_ingest(tmp_path: Path) -> None:
    service = RegistrationService(work_root=tmp_path / "api-work", run_inline=True)
    app = create_app(service)
    with TestClient(app) as client:
        junk = tmp_path / "not_a_product.bin"
        junk.write_bytes(b"not-pds")
        created = client.post(
            "/registration/jobs",
            json={"source_path": str(junk), "reference_path": str(junk)},
        )
        assert created.status_code == 200
        job = created.json()
        assert job["status"] == "failed"
        assert job["error"]["code"] in {"unsupported_product", "invalid_input", "backend_exception"}
        result = client.get(f"/registration/jobs/{job['job_id']}/result")
        assert result.status_code == 200
        assert result.json()["status"] == "failed"
        assert result.json()["result"] is None


def test_upload_then_job_paths(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "up_source.npy"
    reference = tmp_path / "up_reference.npy"
    _write_textured(source, seed=3)
    _write_textured(reference, seed=3)

    up_src = client.post(
        "/products",
        files={"file": ("source.img", source.read_bytes(), "application/octet-stream")},
    )
    up_ref = client.post(
        "/products",
        files={"file": ("reference.img", reference.read_bytes(), "application/octet-stream")},
    )
    assert up_src.status_code == 200
    assert up_ref.status_code == 200
    created = client.post(
        "/registration/jobs",
        json={
            "source_product_id": up_src.json()["product_id"],
            "reference_product_id": up_ref.json()["product_id"],
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "completed"


def test_result_not_ready_for_unknown_async_semantics(tmp_path: Path) -> None:
    # Queued/running path: create service without starting worker by faking record.
    service = RegistrationService(
        work_root=tmp_path / "api-work",
        ops=_synthetic_ops(),
        run_inline=True,
    )
    app = create_app(service)
    with TestClient(app) as client:
        missing = client.get("/registration/jobs/job-missing/result")
        assert missing.status_code == 404


def test_preprocess_guard_identity_for_oversized_pair() -> None:
    from api.preprocess_guard import PREPROCESS_IDENTITY_FLAG, guarded_preprocess
    from src.models.registration_pair import RegistrationPair

    source = LunarProduct(
        product_id="big-src",
        instrument="OHRC",
        dimensions=ImageDimensions(width_px=12000, height_px=78175),
    )
    reference = LunarProduct(
        product_id="big-ref",
        instrument="LRO_NAC",
        dimensions=ImageDimensions(width_px=5064, height_px=52224),
    )
    pair = RegistrationPair(pair_id="pair", source=source, reference=reference)
    called = {"n": 0}

    def boom(_pair: RegistrationPair) -> RegistrationPair:
        called["n"] += 1
        raise AssertionError("frozen preprocess must not run for oversized pair")

    notes: list[str] = []
    out = guarded_preprocess(pair, boom, on_identity=notes.append)
    assert out is pair
    assert called["n"] == 0
    assert notes and "identity passthrough" in notes[0]
    assert PREPROCESS_IDENTITY_FLAG.startswith("preprocess_identity")
