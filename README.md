# Chandrayaan-2 image correspondence

A lunar image-registration system. Given a Chandrayaan-2 **OHRC** product and an **LROC NAC** reference image of the same region, it finds correspondences, estimates a warp, and produces an overlay plus metrics.

The problem is that the two images are taken years apart, at different sun angles, resolutions, and viewing geometry. A naive matcher fails; the pipeline characterises the pair, builds matching views, verifies geometry, refines to subpixel, then registers.

Live demo: https://chandrayan-lunar.vercel.app

**Working path today:** OHRC (PDS4) ↔ LROC NAC (PDS3). TMC-2, IIRS, and a full SPICE camera model are sketched in code and marked planned in the UI; they are not wired as a live registration path.

Raster products are not in git. Point `CHANDRAYAN_DATA_ROOT` at a local product tree. Without it the API still boots; catalog and EXP-000 simply report unavailable.

## Architecture

```
PDS products  →  src/ (scientific core)  →  artifacts / metrics
                      ↑
                 api/  FastAPI jobs
                      ↑
                 frontend/  React workspace
```

`src/` never imports FastAPI. `api/` only orchestrates jobs and serves artifacts. `frontend/` is a Vite + React UI (globe / workspace / results). Tests in `tests/unit/test_no_http_in_scientific_core.py` fail the build if HTTP leaks into the core.

Pipeline stages (`src/pipeline/orchestrator.py`):

| Stage | Module area | What it does |
|---|---|---|
| ingest | `src/ingestion` | PDS4 OHRC zip/xml or PDS3 LROC `.IMG` → `LunarProduct` |
| characterize | `src/geometry` | Overlap, GSD, illumination / viewpoint difficulty |
| preprocess | `src/preprocessing` | Window, intensity, contrast, optional denoise |
| represent | `src/representation` | Intensity, gradient, or structural matching view |
| match | `src/matching` | SIFT baseline; ORB and an in-repo RIFT variant for A/B |
| verify | `src/verification` | Geometric filter on putative matches |
| control points | `src/control_points` | Subset used for the transform |
| refine | `src/refinement` | ZNCC + parabolic peak (subpixel) |
| register | `src/registration` | Warp, overlay, residual diagnostics |
| evaluate / export | `src/evaluation`, `src/io` | Metrics JSON + rasters |

## Features

- Upload or select existing OHRC / LROC products
- Async registration jobs (`POST /registration/jobs`, poll status / result / overlay)
- Experiment log EXP-000 … EXP-006 on declared pairs (matcher, scale, representation, subpixel)
- Capability roadmap in the UI for TMC-2 / IIRS / SPICE (planned)

## HTTP API (`http://127.0.0.1:8000`)

| Method | Path |
|---|---|
| GET | `/health` |
| POST | `/products` |
| GET | `/products`, `/products/catalog`, `/products/exp000` |
| POST | `/registration/jobs` |
| GET | `/registration/jobs/{id}` |
| GET | `/registration/jobs/{id}/result` |
| GET | `/registration/jobs/{id}/metrics` |
| GET | `/registration/jobs/{id}/visualization` |
| GET | `/registration/jobs/{id}/artifacts/{name}` |

## Repository layout

```
src/              scientific core
api/              FastAPI
frontend/         React + Vite
configs/          default.yaml (stage slots, not frozen scientific thresholds)
data/manifests/   pair / product metadata only
experiments/      EXP-000 … EXP-006 records
tests/            unit, integration, synthetic
docs/             architecture and module handoff
scripts/          run_api.py, experiment runners
```

## Experiments

| ID | What was compared |
|---|---|
| EXP-000 | SIFT baseline on a real OHRC / LROC pair |
| EXP-001 | SIFT vs in-repo RIFT vs ORB |
| EXP-002 / 003 | GSD normalisation and scale robustness |
| EXP-004 | Intensity vs gradient vs structural representation |
| EXP-005 | ZNCC + parabolic subpixel |
| EXP-006 | Reciprocal SIFT correspondence quality |

Several records are labelled not independently validated. Treat them as engineering logs, not published accuracy.

## Team

| Person | Owns |
|---|---|
| Tejasva Vardhan Sharma | Architecture, contracts, pipeline, I/O, API |
| Haruto | PDS ingestion, preprocessing |
| Shashwat | Geometry, pair characterization |
| Chuba | Representation, matching |
| Shaiz | Registration, verification, UI |

## Run locally

Python 3.11+, Node.

```bash
python -m pip install -e ".[dev]"
python scripts/run_api.py          # :8000
cd frontend && npm install && npm run dev   # :5173
python -m pytest
```

Optional: `export CHANDRAYAN_DATA_ROOT=/path/to/products`

## License

MIT.
