# SIH26166 — Interface freeze v1

Status: Frozen for parallel implementation
Owner: Tejas (architecture / integration)
Scope: Canonical contracts, pipeline operations, export stub
Not in scope: scientific algorithms, datasets, HTTP API, frontend

This freeze is the handoff surface for Haruto, Shashwat, Chuba, Shaiz, and later LLM sessions. Scientific detail remains in the master spec. Changing anything below requires an architecture decision (decision log + this document).

## 1. Canonical contracts

Four models, plus supporting types, live in `src/models/`. Extra fields are forbidden. Uncomputed scientific values stay `None`. Do not invent measurements, units, thresholds, or accuracy claims.

| Contract | Module | Produced / filled by |
|---|---|---|
| `LunarProduct` | `lunar_product.py` | Haruto / ingestion |
| `RegistrationPair` + `PairCharacterization` | `registration_pair.py` | Shashwat / geometry (pair); Haruto may return an updated pair from preprocess |
| `CorrespondenceSet` + `Correspondence` | `correspondence_set.py` | Chuba / matching; Shaiz updates statuses during verification |
| `RegistrationResult` | `registration_result.py` | Shaiz / verification, control points, refinement, registration, evaluation |

Supporting types: `ControlPoint`, `TransformationModel`, `RegistrationMetrics`, `ExportManifest`.

Image arrays are not embedded. Products and overlap use URI handles (`raster_uri`, `mask_uri`, `overlap_mask_uri`).

## 2. Module ownership

| Package | Owner | Allowed at this freeze |
|---|---|---|
| `src/models/`, `src/pipeline/`, `src/io/`, `docs/`, `configs/` | Tejas | Contract and orchestration only |
| `src/ingestion/` | Haruto | Product load, decode, basic validation, invalid-pixel/mask needed to build `LunarProduct`, metadata extraction |
| `src/preprocessing/` | Haruto | Pair-aware normalization, orientation, scale-aware resampling when required |
| `src/geometry/` | Shashwat | SPICE/geometry engine; pair characterization calculations |
| `src/representation/`, `src/matching/`, `src/routing/` | Chuba | Representations, matcher adapters, temporary routing behind those steps |
| `src/verification/`, `src/control_points/`, `src/refinement/`, `src/registration/`, `src/evaluation/` | Shaiz | Verify, control points, refine, register, evaluate |
| `api/`, `frontend/` | later | HTTP is a wrapper only |

The scientific core (`src/`) must not import HTTP libraries. Implementations are injected into `PipelineOperations`; default stubs raise `NotImplementedError`.

## 3. Canonical data flow

```
ingest source
ingest reference
→ characterize_pair
→ preprocess
→ generate_representation
→ match
→ verify_matches
→ select_control_points
→ refine_points
→ register(pair, control_points, verified_correspondences)
→ evaluate
→ export_result(result, pair, output_dir)
```

`ScientificPipeline.run` calls operations in this order. The verified `CorrespondenceSet` is passed into `register` and must be attached to `RegistrationResult.correspondences` so evaluate/export see real correspondence data.

`ingest_product(path) -> LunarProduct` is product-level. `preprocess(pair) -> RegistrationPair` is pair-aware. Do not put scale-aware resampling inside ingest.

## 4. Field conventions

**Instrument / mission / modality / matcher_id / representation_id / model_name** are open strings. Do not enum sensors, matchers, or transforms.

**Coordinates.** `Correspondence.source_xy` / `reference_xy` and `ControlPoint.source_xy` / `reference_xy` are image pixel coordinates. Pixel-centre versus pixel-corner origin is not defined in this freeze. Ingestion/geometry will define it when real products are read.

**GSD.** `LunarProduct.gsd_meters` is optional product GSD in metres when a reader extracts it. `PairCharacterization.gsd_ratio` is **source GSD / reference GSD** when both values are known. It is a descriptive measurement, not a routing threshold.

**Sun-angle.** `sun_angle_difference_degrees` is an optional geometry-derived difference. Do not invent an incidence/azimuth combination until geometry defines one.

**Viewing geometry.** `viewing_geometry_difference` is an optional opaque geometry-derived scalar. This contract does not define unit or formula. It must remain `None` until geometry defines and documents it.

**Ownership of pair scalars.** Shashwat/geometry owns the calculations. The models only store results.

**Overlap.** `RegistrationPair.overlap_mask_uri` is optional pair-specific overlap / valid correspondence region. Product `mask_uri` is per-product valid pixels. Do not generate a mask in the contract layer.

**Control point uncertainty.** `ControlPoint.uncertainty` is optional. No unit is assigned. Leave `None` until refinement computes a real value.

**Transformation parameters.** `TransformationModel.parameters` is an open JSON-serializable object map. Model names are unrestricted. Do not assume homography (D-010).

## 5. Preprocessing ownership

Ingestion owns: loading, decoding, basic validation, invalid-pixel/mask handling required to construct `LunarProduct`, metadata extraction.

Preprocessing owns pair-aware operations: normalization, orientation when required, scale-aware resampling when required.

Do not invent preprocessing thresholds in models or `configs/default.yaml`.

## 6. Correspondence source of truth

`CorrespondenceSet.matches` is the canonical correspondence collection.

`RegistrationResult.inliers` is a convenience snapshot/subset of that collection. If `inliers` is non-empty, `correspondences` must be present and each inlier must appear in `matches` by `(source_xy, reference_xy)`.

Do not fabricate inliers, counts, metrics, or transformations in stubs or tests.

## 7. Confidence normalization

`Correspondence.confidence` is optional and, when set, must lie in `[0, 1]`.

It is an **adapter-normalized** confidence, not the raw native matcher score or distance. A matcher adapter may leave it `None` when a meaningful normalization has not been defined. A raw score field is not part of this freeze.

## 8. Intentionally undefined

- Official SIH dataset format, pairs, and evaluator (D-011)
- Pixel origin (centre vs corner)
- Unit and formula for `viewing_geometry_difference`
- Incidence vs azimuth combination for sun-angle difference
- Control-point uncertainty unit
- Representation object schema (`generate_representation` returns `Any`)
- Final matcher, representation, geometry mode, DEM use, sub-pixel method
- Adaptive-routing thresholds and an explicit `route()` operation (M5)
- Extra evaluation metrics beyond the v3 §22 minimum
- Image/table file formats for export (logical names only)
- HTTP API and frontend

## 9. Changes that require an architecture decision

Do not silently:

- add or remove pipeline operations
- change operation signatures
- add required scientific fields
- enum sensors, matchers, or transforms
- assume homography as the lunar model
- put HTTP in `src/`
- encode routing thresholds or accuracy requirements in contracts
- claim sub-pixel accuracy without independent validation
- treat representative lunar data as the official SIH test set

Propose the change, record it in the decision log, update this freeze document, then implement.
