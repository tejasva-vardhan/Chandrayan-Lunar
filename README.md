# Chandrayaan-2 image correspondence

Team project: find corresponding points between a Chandrayaan-2 OHRC image and an LROC NAC reference image, then estimate a registration (warp) so the two can be overlaid.

The live path is **OHRC ↔ LROC**. TMC-2, IIRS, and SPICE geometry are designed in the repo and marked planned in the UI. They are not a live registration path yet.

Official SIH evaluation data is not in this repository. Raster products stay outside git (`CHANDRAYAN_DATA_ROOT`). Without that mount the API still starts and does not invent catalog products.

## What the pipeline does

A pair of lunar products goes through fixed stages in `src/pipeline/orchestrator.py`:

1. **Ingest** — PDS4 OHRC zip/xml or PDS3 LROC `.IMG` into a `LunarProduct`
2. **Characterize** — overlap, scale, and viewing geometry for the pair
3. **Preprocess** — windowing, intensity, contrast, optional denoise
4. **Represent** — intensity / gradient / structural views for matching
5. **Match** — correspondence (SIFT is the working baseline; ORB and an in-repo RIFT variant exist for experiments)
6. **Verify** — geometric filtering of matches
7. **Control points** — subset used for the transform
8. **Refine** — subpixel (ZNCC + parabolic peak)
9. **Register** — estimated warp and overlay
10. **Evaluate / export** — metrics and artifacts

The scientific core (`src/`) does not import FastAPI or other HTTP libraries. Tests under `tests/unit/test_no_http_in_scientific_core.py` enforce that. HTTP lives in `api/` (FastAPI). The UI lives in `frontend/` (React + Vite).

## What is live vs planned

| Capability | Status |
|---|---|
| OHRC ingest (PDS4) | Live |
| LROC NAC ingest (PDS3) | Live |
| OHRC ↔ LROC registration through the pipeline | Live |
| Experiment records EXP-000 … EXP-006 | Recorded on real or declared pairs; several results are labelled **not independently validated** |
| TMC-2, IIRS, SPICE camera model | Interfaces / UI roadmap only |

Demo UI (ephemeral hosting): https://chandrayan-lunar.vercel.app

## Experiments

Records live under `experiments/`. They are software baselines, not official SIH scores.

| ID | Question |
|---|---|
| EXP-000 | SIFT sanity baseline on a real OHRC / LROC pair |
| EXP-001 | SIFT vs in-repo RIFT vs ORB on the same protocol |
| EXP-002 / EXP-003 | GSD / scale policy and scale robustness |
| EXP-004 | Intensity vs gradient vs structural representation |
| EXP-005 | ZNCC + parabolic subpixel refinement |
| EXP-006 | Reciprocal SIFT correspondence quality |

## Repository layout

```
src/            Scientific core (ingestion, geometry, matching, registration)
api/            FastAPI wrapper (upload, catalog, registration jobs)
frontend/       React UI
configs/        Default pipeline YAML
data/manifests  Product / pair manifests (no rasters)
experiments/    Dated experiment records
tests/          Unit, integration, and synthetic scientific tests
docs/           Architecture notes and team handoff
```

## HTTP API

Default: http://127.0.0.1:8000

- `GET /health`
- `POST /products` — upload OHRC or LROC product
- `GET /products`, `GET /products/catalog`, `GET /products/exp000`
- `POST /registration/jobs`
- `GET /registration/jobs/{id}` and `/result`, `/metrics`, `/visualization`, `/artifacts/{name}`

## Team

| Person | Owns |
|---|---|
| Tejasva Vardhan Sharma | Architecture, contracts, pipeline, I/O, API |
| Haruto | PDS ingestion and preprocessing |
| Shashwat | Geometry and pair characterization |
| Chuba | Representation and matching |
| Shaiz | Registration, verification, and UI |

## Run locally

Python 3.11+ and Node.

```bash
python -m pip install -e ".[dev]"
python scripts/run_api.py
```

```bash
cd frontend
npm install
npm run dev
```

API: http://127.0.0.1:8000 · UI: http://127.0.0.1:5173

```bash
python -m pytest
```

## License

MIT.
