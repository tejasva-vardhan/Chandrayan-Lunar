# SIH26166 — Chandrayaan-2 lunar image correspondence

Scientific, geometry-aware, adaptive correspondence and registration for Chandrayaan-2 optical imagery (OHRC, TMC-2, IIRS) against lunar reference imagery.

This repository is the team implementation of Smart India Hackathon 2026 problem statement **SIH26166**.

## Current status

**FACT**

- Foundation plus scientific stages and a thin HTTP/frontend integration layer.
- Canonical contracts, pipeline orchestration, and module ownership remain as frozen in interface freeze v1.
- The scientific core (`src/`) does not import FastAPI/HTTP libraries.
- The HTTP wrapper lives in `api/` and the existing cinematic UI lives in `frontend/`.
- Official SIH dataset and evaluator constraints are **pending/TBD**. Do not treat any local or public lunar product as the official SIH test set.

**DECISION** (from v3.0)

- Final matcher is selected after a small controlled benchmark, not assumed now.
- Internal prototype may use representative authorized/public lunar data, clearly labeled as such.

## Source-of-truth hierarchy

1. Official SIH problem statement and official SIH rules/templates
2. Official ISRO/PRADAN product specifications and supplied Chandrayaan-2 SPICE documentation
3. Official LROC/JAXA product documentation
4. Peer-reviewed research
5. Our measured experiments
6. Engineering inference

A lower-level source cannot silently override a higher-authority requirement.

## Documentation

| Document | Location |
|---|---|
| Master Engineering & Research Specification v3.0 | `docs/master/SIH26166_Master_Engineering_Research_Spec_v3.md` |
| Team work division & implementation plan | `docs/master/SIH26166_Team_Work_Division_and_Implementation_Plan.md` (PDF alongside) |
| Recorded decisions D-001–D-014 | `docs/decisions/D-001_to_D-014.md` |
| Interface freeze v1 | `docs/architecture/INTERFACE_FREEZE_V1.md` |
| Team module handoff v1 | `docs/architecture/TEAM_MODULE_HANDOFF_V1.md` |
| Official SIH guidelines / PS status | `docs/requirements/` |

## Team ownership

| Person | Owns |
|---|---|
| Tejas | Architecture, integration, contracts, `src/models/`, `src/pipeline/`, `src/io/`, `configs/`, `docs/`, `api/` |
| Haruto | PDS/ingestion, preprocessing, manifests |
| Shashwat | SPICE, geometry, pair characterization |
| Chuba | Representation, matching, adaptive routing |
| Shaiz | Verification, control points, refinement, registration, evaluation, UI |

## Development workflow

- One person → one feature/module → one branch → one pull request.
- Keep `main` stable. Do not develop large features on `main`.
- Agree interfaces before large implementations.
- Do not commit raw scientific datasets or credentials unless explicitly permitted.
- Accuracy-affecting scientific changes require benchmarks/validation.
- Architecture changes go into the decision log.

## Local development (frontend + API)

Python 3.11+ and Node/pnpm are required.

### 1. Scientific core + API

```text
python -m pip install -e ".[dev]"
python scripts/run_api.py
```

API listens on `http://127.0.0.1:8000` by default.

Useful endpoints (master spec demo API):

- `GET /health`
- `POST /products` (multipart upload: OHRC `.zip`/`.xml` or LROC `.IMG`)
- `GET /products` (session uploads)
- `GET /products/catalog` (declared products under `CHANDRAYAN_DATA_ROOT`)
- `GET /products/exp000` (resolve real EXP-000 pair_01 paths)
- `POST /registration/jobs`
- `GET /registration/jobs/{id}`
- `GET /registration/jobs/{id}/result`
- `GET /registration/jobs/{id}/metrics`
- `GET /registration/jobs/{id}/artifacts/{name}`

### 2. Frontend

```text
cd frontend
npm install
npm run dev
```

(`pnpm install` / `pnpm dev` also work if pnpm is available.)

Vite serves the UI on `http://127.0.0.1:5173` and proxies `/health`, `/products`, and `/registration` to the API (CORS is also enabled for local origins).

### 3. Both together

Terminal A:

```text
python scripts/run_api.py
```

Terminal B:

```text
cd frontend
npm run dev
```

Open the UI, enter the mission view, use **Run registration** in the workspace with:

- uploaded OHRC PDS4 / LROC PDS3 products, or
- **Select Existing** products discovered under `CHANDRAYAN_DATA_ROOT`, or
- **Load EXP-000 Real Pair** (pair_01 from the data root), or
- advanced local absolute paths readable by the API process.

Unsupported files return a clear backend error. The API never substitutes mock Chandrayaan-2 data.
The static EXP-000 numbers in the results panel are an explicitly labelled regression fixture until a live job completes.

### Tests / lint

```text
python -m pytest
python -m ruff check src tests api
cd frontend
npm test
npm run lint
npm run build
```

## Deployment (Render + Vercel)

This section covers a **demo** deployment. It does not change scientific contracts or invent dataset availability.

See also:

- Backend env template: `.env.example`
- Frontend env template: `frontend/.env.example`

### Backend on Render

| Setting | Value |
|---|---|
| Root directory | repository root (not `frontend/`) |
| Runtime | Python 3.11+ |
| Build command | `pip install -e ".[api]"` |
| Start command | `uvicorn api.app:app --host 0.0.0.0 --port $PORT` |

**Required env vars:** none beyond Render’s `PORT`.

**Optional env vars:**

| Variable | Purpose |
|---|---|
| `CHANDRAYAN_DATA_ROOT` | External scientific products root. If unset, the API still starts; catalog and EXP-000 resolve as unavailable (no fake products). |
| `CHANDRAYAN_API_WORK_ROOT` | Writable uploads/jobs directory (defaults to `<repo>/outputs/api`). Ephemeral on Render. |
| `SIH26166_CORS_ORIGINS` | Comma-separated extra browser origins (add the Vercel URL after it exists). Local Vite origins remain allowed. |

The backend must not depend on Windows paths or `D:\SIH`. Startup and `/health` succeed without a local dataset.

### Frontend on Vercel

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Framework preset | Vite |

**Build-time env vars:**

| Variable | Required? | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | **Yes for production** | Public Render API origin, no trailing slash (example: `https://your-service.onrender.com`). Embedded at build time. |
| `VITE_CESIUM_ION_TOKEN` | No | Cesium ion token for the globe layer. UI loads without it. |

Locally, leave `VITE_API_BASE_URL` unset so the Vite proxy targets `http://127.0.0.1:8000`.

After the Vercel URL exists, set `SIH26166_CORS_ORIGINS` on Render to that origin and redeploy/restart the API.

### Deployed demo limitations (honest)

- Render’s filesystem is **ephemeral**: uploads and job artifacts do not persist across restarts.
- Large Chandrayaan-2 / LROC rasters may exceed free-tier memory/time; existing safety limits and degraded/unavailable paths remain.
- Without mounting real products at `CHANDRAYAN_DATA_ROOT`, **Select Existing** and **Load EXP-000 Real Pair** correctly report unavailable — they do not invent catalog entries.
- Static EXP-000 fixture numbers in the UI remain labelled as a fixture until a live completed job supplies results.

## Configuration

Structural settings live in `configs/default.yaml`. Slots exist for preprocessing, geometry, representation, matcher identity, verification, control points, refinement, registration, evaluation, and export. Scientific thresholds, routing cutoffs, and a final matcher are experimental and are not set here.

## Warning

The official SIH26166 dataset is currently **pending/TBD**. Do not invent its format, pairs, or evaluator. Do not claim official-dataset results from representative data. Verification residual RMSE is a geometric-verification fit diagnostic, not independent registration accuracy.
