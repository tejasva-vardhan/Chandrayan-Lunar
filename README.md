# Chandrayaan-2 image correspondence

Team project: register Chandrayaan-2 OHRC images against LROC reference imagery under different illumination and viewing geometry.

TMC-2, IIRS, and SPICE geometry are designed in the repository and marked planned in the UI. They are not a live registration path yet.

The scientific core (`src/`) does not import HTTP libraries. The API lives in `api/` and the UI lives in `frontend/`.

## Team

| Person | Owns |
|---|---|
| Tejasva Vardhan Sharma | Architecture, contracts, pipeline, I/O, API |
| Haruto | PDS ingestion and preprocessing |
| Shashwat | Geometry and pair characterization |
| Chuba | Representation and matching |
| Shaiz | Registration, verification, and UI |

## Run locally

Python 3.11+ and Node are required.

```bash
python -m pip install -e ".[dev]"
python scripts/run_api.py
```

API: http://127.0.0.1:8000

```bash
cd frontend
npm install
npm run dev
```

UI: http://127.0.0.1:5173

Official evaluation data is not in this repository. Catalog and EXP-000 paths need `CHANDRAYAN_DATA_ROOT`. Without it the API still starts; it does not invent products.

```bash
python -m pytest
```

## License

MIT.
