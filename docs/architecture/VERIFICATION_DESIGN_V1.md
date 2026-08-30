# SIH26166 — Geometric verification design (Phase 1)

Status: Implementation note for `src/verification/`  
Companion: Interface Freeze v1, Master spec v3 §18, D-010  
Not a rewrite of the master specification.

## Purpose

`verify_matches(correspondences, pair) -> CorrespondenceSet` classifies each
item in `CorrespondenceSet.matches` after validation and robust geometric
consistency checking. `matches` remains the only correspondence collection.

The module does not interpret `matcher_id`. It must work for any matcher
adapter that fills the frozen `Correspondence` fields (SIFT, RIFT/RIFT2,
LightGlue, LoFTR, PWIFT, or another).

## Pipeline surface

The frozen signature is unchanged:

```
verify_matches(correspondences: CorrespondenceSet, pair: RegistrationPair) -> CorrespondenceSet
```

Configurable runs (tests and later experiments) use:

```
verify_correspondences(correspondences, pair, settings: VerificationSettings)
```

`RegistrationPair` is accepted because the freeze requires it. This phase does
not read rasters, masks, GSD, or characterization: pixel origin, mask format,
and those formulas are not defined in freeze v1.

## Separable stages

1. Validation / filtering (`filtering.py`)
2. Candidate geometric model estimation (`geometric_models.py`)
3. Robust outlier rejection (`estimators.py`)
4. Residual calculation (`residuals.py`)
5. Status assignment (`verify.py`)
6. Failure detection (no fitted model → no inliers)

## Estimator / model abstraction

Registry, not a frozen enum:

| `model_id` | Class | Role |
|---|---|---|
| `projective_2d_baseline` | 8-dof 2D projective map (normalized DLT) | TEST / software baseline |
| `affine_2d_baseline` | 6-dof affine map | TEST / software baseline |

| `estimator_id` | Class | Role |
|---|---|---|
| `ransac_style_baseline` | Classic RANSAC over the selected model | TEST / software baseline |

`verify_matches` wires `projective_2d_baseline` + `ransac_style_baseline`.
That pairing is **not** the selected lunar transformation (D-010). Terrain
relief, pushbroom geometry, DEM-assisted models, MAGSAC, and polynomial
families are not implemented. A later experiment may register another
`GeometricModel` / `RobustEstimator` and pass it through `VerificationSettings`.

If a synthetic test generates correspondences from a known map, that map is
a **synthetic generating model**. It is not lunar accuracy.

## Residual semantics

Freeze v1 does not define `Correspondence.residual` unit or formula.

This implementation writes, when a model was actually evaluated on that item:

**image-space transfer error** = Euclidean distance between observed
`reference_xy` and the point obtained by applying the fitted 3×3 matrix to
`source_xy` in homogeneous coordinates.

- Same numeric convention as the input pixel tuples.
- Not metres. Not GSD-scaled. Not a frozen SIH residual.
- Pixel-centre versus pixel-corner is not interpreted here.
- Invalid, duplicate, or not-evaluated items keep `residual=None`.
- Non-finite mapped scale (`|w|` below a numerical floor) yields a non-finite
  residual and is not treated as an inlier.

The residual function is isolated in `residuals.py` so a later frozen
definition can replace it without changing status logic.

## Parameters

**Not** stored in `configs/default.yaml`.

### Engineering vs scientific (explicit)

The frozen callable is `verify_matches(correspondences, pair)` — two
arguments, no settings object. A software default is therefore required so
the pipeline can call it.

These three numbers are **engineering / test defaults for that frozen API
only**:

| Field | Software default | Classification |
|---|---|---|
| `residual_limit` | `3.0` | Engineering default so the two-arg API can run. Compared to image-space transfer error in input pixel units. |
| `max_trials` | `500` | Computational trial budget so RANSAC can terminate. |
| `rng_seed` | `0` | Deterministic sampling for software tests. |

They are **not**:

- SIH thresholds
- lunar-validated parameters
- final scientific parameters
- benchmark results

They must not be copied into `configs/default.yaml`. Experiments and tests
that need a specific limit, budget, or seed must pass `VerificationSettings`
into `verify_correspondences`.

Other `VerificationSettings` fields used by the two-argument callable:

| Field | Software default | Meaning |
|---|---|---|
| `model_id` | `projective_2d_baseline` | Registry label, not a lunar decision |
| `estimator_id` | `ransac_style_baseline` | Registry label, not a MAGSAC/RANSAC freeze |
| `confidence_min` | `None` | No confidence cutoff (refuses to invent one) |

`confidence_min` is optional and experimental. When it is `None`, items with
`confidence=None` still participate. This module does not normalize native
matcher scores.

## Status transitions

Frozen values only: `raw`, `filtered`, `inlier`, `rejected`.

| Condition | Status | Residual |
|---|---|---|
| Non-finite coordinates | `rejected` | `None` |
| Confidence present but not finite or not in `[0, 1]` | `rejected` | `None` |
| Optional `confidence_min` set and confidence below it | `rejected` | `None` |
| Exact duplicate `(source_xy, reference_xy)` after the first | `rejected` | `None` |
| Passed validation; no successful fit yet | `filtered` | `None` |
| Evaluated and residual `<= residual_limit` | `inlier` | transfer error |
| Evaluated and residual `> residual_limit` | `rejected` | transfer error |
| Empty set, too few candidates, or degenerate/failed fit | no `inlier` items (`filtered` if validated) | no fabricated residuals |

Original `source_xy`, `reference_xy`, `confidence`, `pair_id`, `matcher_id`,
and `representation_id` are preserved. The input `CorrespondenceSet` is not
mutated.

## Failure behaviour

Insufficient or degenerate data does not produce inliers. The callable still
returns a `CorrespondenceSet` so the frozen pipeline type holds. That outcome
is not SUCCESS: there is no geometric model and no inlier labels.

Unknown `model_id` / `estimator_id` raise `ValueError` (configuration error).

## Assumptions

- Correspondences are image-pixel pairs as stored by the matcher adapter.
- Exact float-tuple equality is used for duplicates (no invented spatial
  tolerance).
- Image bounds are **not** applied (`LunarProduct.dimensions` may be absent;
  pixel origin is undefined).
- Overlap masks are **not** applied (file format not frozen).
- Algebraic minimum sample counts (3 affine, 4 projective) are model
  requirements, not quality thresholds.

## What remains scientifically open

- Final geometric model for lunar scenes (D-010)
- Final robust estimator (RANSAC vs MAGSAC vs other)
- Residual definition/unit in the freeze
- Validated residual limit, trial policy, and any confidence cutoff
  (`residual_limit=3.0`, `max_trials=500`, and `rng_seed=0` do **not**
  close these; they are two-arg engineering defaults only)
- Whether verification and registration must share a model
- Pixel origin; mask/GSD use inside verification
- Official SIH evaluator behaviour (D-011)

## Dependency

NumPy is required for DLT SVD, least squares, and deterministic RANSAC
sampling. OpenCV and SciPy are not used.
