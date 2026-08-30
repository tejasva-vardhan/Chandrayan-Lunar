# SIH26166 — Team module handoff v1

Status: Active after interface freeze v1
Owner: Tejas (architecture / integration)
Companion: [`INTERFACE_FREEZE_V1.md`](INTERFACE_FREEZE_V1.md)

This is the working agreement for parallel implementation. Scientific requirements remain in the master spec. Canonical field definitions remain in the freeze. This document assigns modules, branches, and review rules so Haruto, Shashwat, Chuba, and Shaiz can implement without repeatedly changing shared interfaces.

Do not treat this file as permission to change frozen contracts.

## 1. Frozen interfaces

These are frozen. Changing them requires an architecture review (section 8).

| Surface | Location |
|---|---|
| `LunarProduct` | `src/models/lunar_product.py` |
| `RegistrationPair`, `PairCharacterization` | `src/models/registration_pair.py` |
| `CorrespondenceSet`, `Correspondence` | `src/models/correspondence_set.py` |
| `RegistrationResult`, `ControlPoint`, `TransformationModel`, `RegistrationMetrics` | `src/models/registration_result.py` |
| `ExportManifest` | `src/io/exports.py` |
| Pipeline operations and signatures | `src/pipeline/operations.py` (facade) and owning packages below |
| Operation order | `ScientificPipeline.run` / `PIPELINE_STAGES` |

Uncomputed scientific values stay `None`. Extra model fields are forbidden. Do not enum sensors, matchers, or transforms. Do not assume homography (D-010). Do not select a final matcher in shared config (D-007).

## 2. How the pipeline is wired

`ScientificPipeline` is scientific-core orchestration only. It does not import HTTP, FastAPI, frontend, database, or cloud libraries.

Default callables are the owning-module interfaces. `src/pipeline/operations.py` re-exports those interfaces. The orchestrator does not import a matcher implementation or a transformation implementation.

When you implement a stage, replace the `NotImplementedError` stub **in your package** and keep the frozen signature. Point your package `__init__.py` at the real callable if you add files. Do not add a parallel function name and expect the pipeline to discover it.

Injection remains available: tests and later integration can pass a `PipelineOperations` object. That is for wiring, not for bypassing unimplemented science.

## 3. Canonical artifact flow

```
LunarProduct
  → RegistrationPair                    # characterize_pair
  → characterized / preprocessed pair   # same RegistrationPair type
  → representation                      # Any; schema not frozen
  → CorrespondenceSet                   # match
  → verified CorrespondenceSet          # verify_matches; statuses on items
  → list[ControlPoint]                  # select_control_points
  → refined list[ControlPoint]          # refine_points
  → RegistrationResult                  # register, then evaluate
  → ExportManifest                      # export_result(result, pair, output_dir)
```

Order:

ingest → characterize_pair → preprocess → generate_representation → match → verify_matches → select_control_points → refine_points → register → evaluate → export_result

`ingest_product` is product-level and runs for source and reference. `preprocess` is pair-aware and runs after characterization.

### Artifact review (no contract change)

The frozen types can represent this flow. One intermediate is intentionally unconstrained:

- **Representation** has no schema. `generate_representation` returns `Any`. That is freeze v1 §8, not a missing field. Chuba owns the object. The pipeline passes it to `match` without interpreting it.

Not blockers (do not add model fields for these):

- Characterized and preprocessed pairs are both `RegistrationPair`. Preprocess may return an updated pair (for example new `raster_uri` values). Preserve `characterization` unless a later decision says otherwise.
- Verified correspondences are the same `CorrespondenceSet`. Use `Correspondence.status`; do not invent a second collection.
- Refined control points are still `list[ControlPoint]`. `ControlPoint.uncertainty` stays `None` until refinement computes a real value.
- `register` must attach the provided `CorrespondenceSet` to `RegistrationResult.correspondences` so evaluate/export see it.

## 4. Module ownership

### HARUTO

Owns: `src/ingestion/`, `src/preprocessing/`, `data/manifests/`

- Ingestion: load, decode, basic validation, invalid-pixel/mask needed to build `LunarProduct`, metadata extraction.
- Preprocessing: pair-aware normalization, orientation when required, scale-aware resampling when required.
- Outputs: `LunarProduct` from ingest; processed `RegistrationPair` from preprocess.
- Must not put scale-aware resampling inside ingest.
- Must not modify shared contracts without review.

Suggested branches: `feature/haruto-ingestion`, `feature/haruto-preprocessing`

### SHASHWAT

Owns: `src/geometry/`

- Geometry engine and SPICE integration.
- Pair characterization. Fill `PairCharacterization` through the existing contract.
- Provide geometry-derived values (GSD ratio, sun-angle difference, viewing-geometry difference, overlap, and similar) only when actually computed. Leave `None` otherwise.
- Owns the meaning of `viewing_geometry_difference` and sun-angle combination when those are defined; document them before filling the fields.
- Must not encode adaptive-routing thresholds in models or `configs/default.yaml`.
- Must not modify shared contracts without review.

Suggested branch: `feature/shashwat-geometry`

### CHUBA

Owns: `src/representation/`, `src/matching/`, `src/routing/`

- Representation engine. Output is passed through to `match`; schema is not frozen.
- Matching through `match(pair, representation) -> CorrespondenceSet`.
- Adaptive matcher routing. An explicit `route()` pipeline stage is **not** in this freeze (M5). Temporary routing may live behind representation or match and may read `PairCharacterization`.
- Outputs: `CorrespondenceSet`. `matcher_id` is a label for the wired adapter, not a claim that the final matcher is decided.
- Must not assume the final matcher is already decided (D-007). Do not import SIFT, RIFT, LightGlue, LoFTR, PWIFT, or any other adapter into `src/pipeline/`.
- Must not modify shared contracts without review.

Suggested branches: `feature/chuba-representation`, `feature/chuba-matching`

### SHAIZ

Owns: `src/verification/`, `src/control_points/`, `src/refinement/`, `src/registration/`, `src/evaluation/`, and later UI (`frontend/`, with HTTP only as a wrapper)

- Verification: update correspondence statuses; `matches` remains the source of truth.
- Control points: spatially uniform selection (D-005).
- Refinement: sub-pixel only with independent validation later (D-006).
- Registration: must not assume homography (D-010). Use `TransformationModel.model_name` as an open label.
- Evaluation: fill `RegistrationMetrics` only with measured values.
- UI after the scientific pipeline works.
- Must not invent inliers, counts, metrics, or transformations in stubs.
- Must not modify shared contracts without review.

Suggested branches: `feature/shaiz-verification`, `feature/shaiz-control-points`, `feature/shaiz-refinement`, `feature/shaiz-registration`, `feature/shaiz-evaluation`

### TEJAS

Owns: `src/models/`, `src/pipeline/`, `src/io/`, `configs/`, `docs/`, repository standards, architecture consistency, integration tests

- Contracts, orchestration, configuration structure, export contract, team handoff.
- Integration tests in `tests/integration/` are wiring tests, not scientific evidence.
- Does not implement scientific algorithms.

Working branch for this integration layer: `feature/tejas-integration`

## 5. Branch ownership

- `main` stays stable. Do not develop features on `main`.
- One person → one feature/module → one branch → one pull request.
- Named feature branches as in section 4. Experiment work uses `experiment/<id>` when a benchmark is the point of the change.
- Do not commit raw scientific datasets or credentials unless explicitly permitted.

## 6. PR expectations

Every PR must include:

- objective;
- changed modules;
- tests;
- benchmark impact (required when accuracy is affected; write “none — wiring/docs only” when that is true);
- scientific rationale (or “not applicable — no scientific change”);
- documentation updates when behaviour or ownership changes.

PRs that only replace a `NotImplementedError` stub with a real implementation in the owned package should not edit frozen models, pipeline signatures, or other people's packages except by agreement.

## 7. Configuration

`configs/default.yaml` is structural. It has slots for:

- preprocessing
- geometry
- representation (`representation_id`, unset)
- matcher selection (`matcher_id`, unset — not a final choice)
- verification
- control points
- refinement
- registration (`model_name`, unset — not a homography default)
- evaluation
- export

Do not invent scientific thresholds or routing cutoffs in this file. Local or experiment configs may try adapter names later; that is not a freeze of the final matcher. Do not put those names into `configs/default.yaml`.

## 8. When architectural changes require review

Propose the change, record it in the decision log, update the interface freeze, then implement.

Review is required before anyone:

- adds or removes pipeline operations (including adding `route()` before M5);
- changes operation signatures;
- adds required scientific fields to canonical models;
- enums sensors, matchers, or transforms;
- assumes homography as the lunar model;
- puts HTTP, FastAPI, frontend, database, or cloud clients in `src/`;
- encodes routing thresholds or accuracy requirements in contracts;
- claims sub-pixel accuracy without independent validation;
- treats representative lunar data as the official SIH test set.

Tejas reviews those PRs. Do not silently change interfaces.

## 9. Failure handling for unimplemented science

Unimplemented stages must raise `NotImplementedError`. The pipeline must not skip a stage or emit placeholder scientific outputs.

Wiring tests may use doubles. Those doubles are not scientific results.

## 10. Tests

| Directory | Meaning |
|---|---|
| `tests/unit/` | Contract and stub tests. Not scientific evidence. |
| `tests/integration/` | Pipeline wiring tests (`pytest.mark.wiring`). Not scientific evidence. |
| `tests/scientific/` | Reserved for measured scientific validation. Empty until owners add it. |
| `tests/regression/` | Reserved for fixed-pair metric tolerances. |

Do not cite wiring-test `CorrespondenceSet` objects, empty match lists, or unset metrics as algorithm performance.

## 11. Out of scope for this handoff

Do not implement in the integration layer, and do not wait on Tejas to implement:

- SIFT, RIFT/RIFT2, LightGlue, LoFTR, PWIFT
- SPICE calculations
- image preprocessing algorithms
- registration algorithms
- sub-pixel refinement
- frontend, FastAPI, Docker, database, cloud infrastructure

Do not download datasets into git.
