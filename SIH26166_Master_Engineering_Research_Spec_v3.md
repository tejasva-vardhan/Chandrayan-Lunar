# SIH26166 — Master Engineering & Research Specification v3.0

Status: Pre-implementation / internal-round-ready baseline
Purpose: Single source of truth for the SIH26166 team, repository, experiments, demo and future LLM sessions.

## 1. Executive project decision

We will build a scientific, geometry-aware and adaptive lunar image correspondence/registration system.

The system will not be "one AI model that matches two images." It will be a modular pipeline that combines:
- scientific product handling;
- acquisition/pair characterization;
- illumination-aware representations;
- scale handling;
- optional planetary geometry/SPICE priors;
- a small benchmarked matcher portfolio;
- robust geometric verification;
- spatially uniform control-point selection;
- sub-pixel refinement;
- registration;
- independent validation;
- explainable quality/failure reporting.

The final matcher is not permanently frozen now. We will shortlist and benchmark a small number of justified candidates, then select the best measured trade-off for the actual lunar benchmark.

## 2. Official problem requirements

SIH26166 asks for correspondence between Chandrayaan-2 optical imagery and lunar reference imagery under:
- illumination/Sun-angle variation;
- viewpoint variation;
- scale variation.

Expected outputs include:
- generic correspondence software;
- sub-pixel accuracy of the source image;
- uniformly distributed match points;
- registered product;
- corresponding match points;
- evaluation using metrics such as RMSE, inlier count and inlier ratio.

The official SIH dataset is currently treated as pending/TBD. Do not invent its final format, pairs or evaluator.

## 3. Source-of-truth hierarchy

1. Official SIH problem statement and official SIH rules/templates.
2. Official ISRO/PRADAN product specifications and supplied Chandrayaan-2 SPICE documentation.
3. Official LROC/JAXA product documentation.
4. Peer-reviewed research.
5. Our measured experiments.
6. Engineering inference.

A lower-level source cannot silently override a higher-authority requirement.

## 4. Research status

### Established
- This is a planetary image registration/correspondence problem, not ordinary panorama stitching.
- Illumination, scale, viewpoint, sensor modality, calibration and terrain can affect correspondence.
- LROC NAC is a pushbroom reference sensor and must be processed with its scientific metadata/geometry.
- Chandrayaan-2 OHRC, TMC-2 and IIRS are materially different sensing systems.
- SPICE provides useful spacecraft/instrument geometry information.
- Existing matchers are components/baselines; their performance must be validated on our problem.
- Uniform spatial control points and independently validated sub-pixel refinement are required.

### Experimental
- final matcher;
- final representation;
- exact geometry contribution;
- DEM/orthorectification contribution;
- adaptive routing thresholds;
- exact sub-pixel refinement method;
- best IIRS representation;
- best runtime/accuracy trade-off.

### Pending
- official SIH dataset;
- exact SIH evaluation implementation/constraints;
- final SELENE/Kaguya audit.

## 5. Dataset strategy for the internal round

If the official SIH dataset is not yet available, the team will not wait idle.

Build the prototype using appropriate public/authorized representative lunar products, prioritizing:
- LRO NAC;
- SELENE/Kaguya TC;
- accessible Chandrayaan-2 samples where legally/technically available.

The internal presentation must clearly label this as a representative validation/demo dataset and must not claim it is the official SIH test set.

When the official dataset arrives, only the dataset adapter/manifests and any necessary calibration/format configuration should need adjustment; the scientific core remains unchanged.

## 6. Internal-round demo objective

The demo must show a complete working scientific workflow, not only slides.

Recommended live flow:

1. Select source and reference.
2. Automatically read metadata.
3. Display pair characteristics.
4. Estimate difficulty.
5. Run correspondence.
6. Show raw and verified matches.
7. Show rejected outliers.
8. Show spatial distribution map.
9. Perform sub-pixel refinement.
10. Register source to reference.
11. Display before/after overlay.
12. Display metrics and confidence.
13. Export registered product and control points.

The presenter should explicitly state when a result is low-confidence or when the official SIH dataset is unavailable.

## 7. High-level architecture

DATA SOURCES
  OHRC / TMC-2 / IIRS / LRO NAC / SELENE
          |
          v
PRODUCT INGESTION + VALIDATION
          |
          v
CANONICAL PRODUCT MODEL
          |
          +-----------------------+
          |                       |
          v                       v
IMAGE/PREPROCESSING          GEOMETRY ENGINE
          |                       |
          +-----------+-----------+
                      v
               PAIR CHARACTERIZER
                      |
                      v
               OVERLAP + MASKS
                      |
                      v
            REPRESENTATION ENGINE
                      |
                      v
            MATCHER ORCHESTRATOR
                      |
                      v
            CORRESPONDENCE FILTER
                      |
                      v
            GEOMETRIC VERIFICATION
                      |
                      v
             SPATIAL CONTROL POINTS
                      |
                      v
              SUB-PIXEL REFINEMENT
                      |
                      v
                REGISTRATION
                      |
                      v
             INDEPENDENT VALIDATION
                      |
             +--------+--------+
             |                 |
             v                 v
     REGISTERED PRODUCT   REPORT/METRICS
             |
             v
          EXPORT/UI

## 8. Pair characterization and adaptive routing

Before matching, compute as available:
- source/reference sensor pair;
- GSD/resolution ratio;
- acquisition-time difference;
- Sun-angle difference;
- viewing geometry difference;
- expected overlap;
- valid-pixel ratio;
- texture/contrast statistics;
- image dimensions;
- modality;
- quality flags.

Use these values to classify a pair as easy/normal/difficult and select a candidate processing path.

Example:

NORMAL OPTICAL
 -> fast/local matcher

LARGE SCALE GAP
 -> scale-aware preprocessing + stronger matcher

LARGE ILLUMINATION/MODALITY GAP
 -> structural/phase/multimodal representation + robust matcher

EXTREME/LOW-CONFIDENCE
 -> alternate route + explicit failure/low-confidence result

Routing thresholds are experimental and must be learned/validated rather than invented.

## 9. Matcher shortlist

Do not implement a large zoo.

### Baseline
- SIFT/ASIFT where useful.

### Multimodal/illumination
- RIFT/RIFT2.

### Modern learned
- LightGlue.

### Difficult/dense
- LoFTR-family or one other strong dense candidate.

### Specialized illumination
- PWIFT or a comparable current method if its data/model requirements are practical.

A paper can justify putting a method into the shortlist. A controlled benchmark decides whether it becomes the final method.

## 10. Decision strategy for the final algorithm

Use a two-stage decision.

Stage A — literature screening:
- relevance to lunar/planetary data;
- illumination robustness;
- scale robustness;
- cross-modal capability;
- compute requirements;
- reproducibility/availability.

Stage B — small controlled benchmark:
- 3–5 serious candidates;
- same image pairs;
- same masks/preprocessing policy where applicable;
- same geometric verification;
- same evaluation protocol.

Choose using a multi-objective score based on:
- registration accuracy;
- inlier quality;
- spatial coverage;
- robustness;
- runtime;
- memory;
- implementation complexity.

Do not claim "best algorithm" globally. Say "best measured method on our benchmark" unless a source proves a narrower claim.

## 11. Representation engine

Candidate representations:
- calibrated intensity;
- gradient/edge;
- phase congruency;
- normalized structural image;
- learned features;
- IIRS selected bands;
- IIRS PCA/low-dimensional spectral representation.

Representation choice is part of the experiment.

## 12. Illumination robustness

Pipeline options:
1. use calibrated data;
2. preserve valid masks;
3. structural/gradient representation;
4. phase-congruency representation;
5. controlled photometric normalization;
6. multimodal descriptor/matcher.

Do not apply aggressive normalization without measuring whether it damages useful information.

## 13. Scale robustness

Explicitly model:
- native GSD ratio;
- sensor resolution;
- image pyramid;
- resampling;
- feature scale.

Test same-scale, moderate-scale and large-scale cases.

Do not call a method scale-invariant merely because images were resized.

## 14. IIRS strategy

IIRS is treated as a distinct spectral sensing modality.

Candidate:
IIRS cube -> quality/mask -> selected bands or spectral reduction -> structural representation -> correspondence.

Compare:
- selected informative bands;
- PCA/low-dimensional representation;
- spectral statistics;
- structural/gradient representation.

Do not force the entire IIRS cube through an ordinary grayscale-camera pipeline.

## 15. Geometry/SPICE layer

Geometry is an auxiliary prior and validation layer.

Progression:
1. parse product metadata;
2. access available SPICE;
3. establish sensor/camera model;
4. compute coarse geometry/overlap where reliable;
5. constrain/search correspondence where useful;
6. estimate residual image-space alignment;
7. validate independently.

Where practical, investigate established planetary sensor-model tooling such as ALE/CSM rather than reimplementing spacecraft geometry.

Do not assume a global homography is physically correct for every lunar scene.

## 16. LROC reference processing

Use official scientific LROC products.

Where further processing is required, LROC documentation supports using NAC EDR as a practical starting point. Respect:
- pushbroom acquisition;
- camera orientation;
- summing mode;
- calibration;
- SPICE quality;
- projection;
- terrain model.

QuickMap is an exploration/candidate-region tool, not a scientific ingestion dependency.

## 17. Terrain/DEM strategy

DEM-assisted processing is optional and experimental.

Use terrain information when:
- terrain relief is significant;
- viewing geometry makes planar assumptions weak;
- a reliable DEM is available.

Compare:
- image-only;
- geometry-only;
- geometry + DEM.

Keep the simplest configuration that gives a validated benefit.

## 18. Geometric verification

raw correspondences
 -> confidence filtering
 -> duplicate/invalid removal
 -> robust model estimation
 -> RANSAC/MAGSAC-style method where justified
 -> inliers
 -> residual analysis
 -> failure detection

The transformation model is selected based on scene geometry and benchmark evidence.

## 19. Spatially uniform control points

This is a first-class SIH requirement.

Do not keep only the top-confidence clustered points.

Use:
image -> grid/quadtree -> candidate points -> quality ranking -> spatial diversity constraint -> final control points.

Report:
- occupied-cell ratio;
- coverage;
- density distribution;
- nearest-neighbour or equivalent uniformity statistics.

## 20. Sub-pixel refinement

coarse correspondence
 -> local neighborhood
 -> correlation/phase/local optimization
 -> sub-pixel coordinate
 -> uncertainty
 -> robust final refit

Evidence required:
- synthetic known displacement;
- independent real checkpoints;
- comparison against unrefined points.

Report pixel error and physical error where geometry supports it.

## 21. Failure handling

Success requires:
- enough correspondences;
- geometric consistency;
- acceptable residuals;
- sufficient spatial coverage;
- independent quality checks.

If not:
- retry with controlled alternative;
- or return LOW_CONFIDENCE/FAILED with reasons.

Never hide a bad registration.

## 22. Output contract

Minimum:
- registered source image;
- all matches;
- verified/inlier matches;
- selected control points;
- transformation/model;
- RMSE;
- inlier count;
- inlier ratio;
- spatial coverage;
- quality flags;
- processing provenance.

Recommended demo package:
registered_source.tif
all_matches.csv
inliers.csv
control_points.csv
transformation.json
metrics.json
before.png
matches.png
overlay.png
registration_report.html

Final SIH exporter remains configurable.

## 23. Internal-round extra-value features

These are not fake "extra features"; each is directly connected to the PS.

### Feature 1 — Automatic challenge profile
Show:
- Sun-angle difference;
- scale ratio;
- sensor pair;
- estimated overlap;
- quality;
- difficulty.

### Feature 2 — Explainable match viewer
Show:
- accepted matches;
- rejected matches;
- confidence;
- geometric residuals.

### Feature 3 — Uniformity/coverage map
Show how control points cover the image.

### Feature 4 — Before/after registration
Show source, reference, overlay/blend and error visualization.

### Feature 5 — Quality certificate
Example fields:
- inlier ratio;
- RMSE;
- number of control points;
- coverage;
- confidence class;
- failure flags.

Numbers must come from actual computation.

### Feature 6 — Automatic failure detection
Explain why a result was rejected or marked low-confidence.

### Feature 7 — Multi-reference consistency
Where data permits:
Chandrayaan-2 -> LRO
and independently cross-check against SELENE.

This should be presented as validation/generalization, not as a requirement that every production job use three references.

## 24. Technology stack

Core:
- Python 3.11+
- NumPy
- SciPy
- OpenCV
- scikit-image

AI:
- PyTorch
- official/research implementations for selected models

Scientific/geospatial:
- GDAL
- Rasterio
- xarray
- h5py as required
- SpiceyPy

Planetary:
- NAIF SPICE
- ISIS/ALE/CSM where justified

Backend:
- FastAPI
- Pydantic
- Uvicorn

Frontend:
- React
- TypeScript

Testing/quality:
- pytest
- Ruff
- mypy where practical
- pre-commit

Config:
- YAML
- JSON

Data/experiments:
- CSV/Parquet
- SQLite only if experiment metadata needs it

Deployment:
- Docker
- CUDA where available

Version control:
- Git/GitHub

Do not add Kubernetes/Kafka/Redis/PostgreSQL/microservices unless a real requirement appears.

## 25. Repository structure

sih26166/
  docs/
    master/
    research/
    architecture/
    decisions/
    experiments/
  configs/
  data/
    raw/
    interim/
    processed/
    external/
    manifests/
  src/
    ingestion/
    models/
    geometry/
    preprocessing/
    representation/
    matching/
    verification/
    control_points/
    refinement/
    registration/
    evaluation/
    routing/
    pipeline/
    io/
    utils/
  experiments/
    EXP-000/
    EXP-001/
  tests/
    unit/
    integration/
    regression/
    scientific/
  scripts/
  api/
  frontend/
  outputs/
  pyproject.toml
  Dockerfile
  README.md

## 26. Internal scientific API

ingest_product()
characterize_pair()
generate_representation()
match()
verify_matches()
select_control_points()
refine_points()
register()
evaluate()
export_result()

HTTP is a wrapper only; the scientific core must work without HTTP.

## 27. Demo API

POST /products
POST /registration/jobs
GET /registration/jobs/{id}
GET /registration/jobs/{id}/result
GET /registration/jobs/{id}/metrics
GET /registration/jobs/{id}/visualization

## 28. Testing

Unit:
- product parsing;
- metadata normalization;
- masks;
- coordinate conversion;
- resampling;
- point selection.

Integration:
- complete ingestion;
- geometry;
- matcher;
- registration;
- export.

Regression:
- fixed benchmark pairs;
- metric tolerances;
- expected failures.

Scientific:
- synthetic ground truth;
- independent checkpoints;
- cross-region holdout;
- cross-sensor validation.

## 29. Reproducibility

Every experiment records:
- dataset manifest;
- pair IDs;
- configuration;
- matcher;
- representation;
- geometry mode;
- refinement;
- software commit;
- model/version;
- hardware;
- runtime;
- random seed where relevant.

Save raw metrics, correspondence files, transformations, logs and visualizations.

## 30. Security/robustness

- validate input files;
- restrict filesystem access;
- limit job/image sizes;
- never execute arbitrary uploaded content;
- isolate external scientific tools;
- keep secrets out of Git;
- pin demo dependencies;
- checksum scientific inputs.

## 31. Team contribution workflow

Suggested:
- main = stable;
- feature/<module>;
- experiment/<id>;
- optional develop branch.

PR must include:
- objective;
- changed modules;
- tests;
- benchmark impact;
- scientific rationale;
- documentation.

No silent architecture changes.

## 32. Workstream split

A — PDS/data ingestion
B — SPICE/geometry
C — representations/matching
D — registration/refinement
E — evaluation/experiments
F — backend/UI
G — documentation/demo

Every workstream owns tests and documentation.

## 33. Experiment roadmap

EXP-000: SIFT sanity baseline.
EXP-001: shortlist matcher comparison.
EXP-002: Sun-angle robustness.
EXP-003: scale robustness.
EXP-004: IIRS representation comparison.
EXP-005: sub-pixel refinement.
EXP-006: spatial-control-point ablation.
EXP-007: adaptive routing.
EXP-008: geometry assistance.
EXP-009: cross-region/generalization.
EXP-010: official SIH dataset evaluation.

## 34. MVP

MVP must be small and reliable:

OHRC
 +
LRO NAC
 -> reader
 -> normalization
 -> SIFT
 -> robust verification
 -> registration
 -> metrics
 -> registered product + matches

Then add research improvements one at a time.

## 35. Milestones

M0: requirements/data audit.
M1: canonical data layer.
M2: working OHRC/LRO baseline.
M3: matcher benchmark.
M4: illumination/scale/multimodal/geometry/refinement improvements.
M5: adaptive routing and failure handling.
M6: official SIH dataset integration.
M7: internal/final demo and submission.

## 36. Definition of Done

A scientific feature is complete only when:
- implemented;
- tested;
- documented;
- reproducible;
- benchmarked when accuracy is affected;
- failure behavior defined;
- provenance recorded.

The demo is ready when:
- baseline works reliably;
- improvements are measured;
- failure cases are handled;
- metrics are reproducible;
- outputs match organizer requirements.

## 37. Decision log

D-001 Scientific-product-first architecture.
D-002 Modular matcher interface.
D-003 LROC EDR preferred starting reference where further processing is required.
D-004 QuickMap is exploration only.
D-005 Spatial distribution is first-class.
D-006 Sub-pixel claims require independent validation.
D-007 Final matcher selected by small controlled benchmark.
D-008 Avoid unnecessary distributed infrastructure.
D-009 Geometry is a dedicated scientific layer.
D-010 Do not force homography as a universal lunar model.
D-011 Official SIH dataset/evaluator constraints remain open.
D-012 Internal demo can use representative authorized data before official SIH data arrives.
D-013 Add challenge profiling, explainable matches, coverage map, quality certificate and failure detection because they directly demonstrate PS requirements.
D-014 Multi-reference validation is an optional validation feature, not a mandatory production dependency.

## 38. Future LLM/team handoff rules

Before changing anything:
1. read this document;
2. identify source-backed facts;
3. identify assumptions;
4. inspect the source document when an exact specification is needed;
5. propose the change;
6. benchmark/test it;
7. update the decision log;
8. version the document if architecture changes.

Never:
- invent SIH constraints;
- claim an existing algorithm as novel;
- claim "best" without scope and evidence;
- claim sub-pixel accuracy without validation;
- use screenshots/web maps as scientific products;
- silently change interfaces;
- add infrastructure without a concrete need.

## 39. Current status

RESEARCH: broad audit sufficient for implementation; remaining work is targeted experimentation.
REQUIREMENTS: official PS understood; actual dataset/evaluator constraints pending.
ARCHITECTURE: defined at system/module/interface level.
TECH STACK: defined.
MVP: ready to implement.
INTERNAL DEMO: can proceed using representative authorized data.
FINAL MATCHER: intentionally selected after a small benchmark.
OFFICIAL SIH INTEGRATION: pending dataset release.

## 40. Immediate execution plan

1. Finish/record SELENE TC audit.
2. Create repository and this document under docs/master/.
3. Build product manifest schema.
4. Build canonical LunarProduct and readers.
5. Acquire a small representative pilot set.
6. Run EXP-000.
7. Produce first real registered image and metrics.
8. Run the 3–5 method shortlist benchmark.
9. Select the measured winner.
10. Add the scientifically useful "extra-value" features.
11. Integrate geometry/SPICE and sub-pixel refinement.
12. Validate independently.
13. Replace pilot manifests with official SIH data when released.
