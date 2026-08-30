# SIH26166 — Evaluation design (Phase 4)

Status: Implementation note for `src/evaluation/`  
Companion: Interface Freeze v1, Master spec v3 §22, D-011, VERIFICATION_DESIGN_V1, CONTROL_POINT_SELECTION_DESIGN_V1, REGISTRATION_DESIGN_V1  
Not a rewrite of the master specification.

This is a **software baseline** that fills the frozen `RegistrationMetrics`
fields from data already present on `RegistrationResult` and
`RegistrationPair`. It is **not** the official SIH evaluator, **not** a
scientifically validated metric definition, **not** lunar registration
accuracy, and **not** sub-pixel evidence (D-006, D-011).

Throughout this document, distinguish:

| Kind | Meaning |
|---|---|
| **ENGINEERING IMPLEMENTATION DEFINITION** | What this package actually computes, so the frozen `evaluate(result, pair)` API can run. |
| **Engineering / test behaviour** | Fail-closed handling: `None` for unavailable values, bounds, determinism. |
| **SCIENTIFICALLY VALIDATED DEFINITION** | A metric whose formula, units, population, and thresholds have been frozen against the official SIH evaluator and/or measured on Chandrayaan-2 / reference pairs. **None of the current metrics has this status.** |

Do not treat an engineering definition as the final SIH definition because
it is implemented.

## 1. Purpose

Independent evaluation of a registration result and the correspondence /
control-point information attached to it.

Frozen pipeline surface (unchanged):

```
evaluate(result: RegistrationResult, pair: RegistrationPair) -> RegistrationResult
```

The callable returns a copy of `result` with `metrics` set to a
`RegistrationMetrics` object. It does not:

- re-run matching, verification, control-point selection, or registration;
- implement `refine_points` or sub-pixel refinement;
- warp images or compute intensity similarity (NCC, SSIM, …);
- add fields beyond the frozen contract (`rmse`, `inlier_count`,
  `inlier_ratio`, `spatial_coverage`, `control_point_count`);
- set `confidence_class` or invent quality-certificate grades;
- mutate the input `RegistrationResult`;
- change global pipeline order.

`CorrespondenceSet.matches` remains the correspondence source of truth
(Interface Freeze v1 §6). `RegistrationResult.inliers` is a convenience
snapshot and is **not** used to compute metrics.

## 2. Metric definitions (summary)

Canonical minimum from master spec v3 §22 and `RegistrationMetrics`:

| Field | Engineering implementation (this phase) | Scientifically validated? |
|---|---|---|
| `rmse` | RMSE of **stored finite residuals** on matches with `status == "inlier"` | No |
| `inlier_count` | Count of matches with `status == "inlier"` | Count rule follows verification status; the *meaning* of that status is not SIH-frozen |
| `inlier_ratio` | `inlier_count / len(matches)` | No — denominator is open |
| `spatial_coverage` | Mean source/reference AABB-area fraction of selected control points vs product `ImageDimensions` | No — origin, image rectangle, overlap, and uniformity are open |
| `control_point_count` | `len(result.control_points)` | Count of the attached list only |

MAE, median error, P95, runtime, occupied-cell ratio, nearest-neighbour
uniformity, physical (metre) error, and image-similarity scores are **not**
implemented. They are not frozen `RegistrationMetrics` fields.

## 3. Input data for each metric

| Metric | Inputs used | Inputs intentionally unused |
|---|---|---|
| RMSE | `CorrespondenceSet.matches`: `status`, `residual` | `RegistrationResult.inliers` snapshot; `ControlPoint.residual`; `TransformationModel`; rasters |
| Inlier count | `matches[].status` | Snapshot `inliers`; control points; residuals |
| Inlier ratio | `matches[].status` and `len(matches)` | Control-point count; geometrically-evaluated subset (see §6) |
| Coverage | Finite `ControlPoint.source_xy` / `reference_xy`; `pair.source.dimensions` and `pair.reference.dimensions`; matching `pair_id` | Correspondence coordinates; overlap masks; GSD; rasters |
| Control-point count | `result.control_points` (list length) | `matches`; inliers |

If `result.correspondences` is `None`, RMSE, inlier count, and inlier ratio
are unavailable. Registration is allowed to attach an empty
`CorrespondenceSet`; that empty set is a measured collection (count 0), not
a missing collection.

## 4. RMSE definition

### ENGINEERING IMPLEMENTATION DEFINITION

Let \(R\) be the list of `Correspondence.residual` values for items in
`CorrespondenceSet.matches` that satisfy **all** of:

1. `status == "inlier"` (verification status; not recalculated here);
2. `residual` is present and finite (`math.isfinite`; not `None`, NaN, or ±Inf);
3. residual is used as stored — **not recomputed** from
   `TransformationModel` or from control points.

Then:

\[
\mathrm{rmse} = \sqrt{\frac{1}{n}\sum_{i=1}^{n} r_i^{2}}
\quad\text{where } n = |R|.
\]

| Item | This implementation |
|---|---|
| Points included | Inlier matches with a finite stored residual |
| Raw matches | Excluded unless their status is `inlier` |
| Verified inliers without residual | Excluded from the sum; they still count in `inlier_count` |
| Rejected items (even with a residual) | Excluded |
| Selected control points | Excluded (different population) |
| Refined points | Not available in this phase; not mixed in |
| Residuals recomputed? | **No** |
| Squared from stored values? | **Yes** |
| Denominator | \(n =\) number of included residuals, not `inlier_count` if some inliers lack a residual, and not \(n-1\) |
| Units | Same as verification residual: **image-space transfer error** in the stored pixel-tuple convention. Not metres. Not GSD-scaled. |

Verification residual semantics (VERIFICATION_DESIGN_V1): Euclidean distance
between observed `reference_xy` and the point obtained by applying the
fitted 3×3 matrix to `source_xy`. Pixel-centre versus pixel-corner is not
interpreted.

If \(n = 0\), `rmse` is `None` (unavailable), **not** 0.

### Why residuals are not recomputed from the registration transform

- `TransformationModel.parameters` is an open JSON map. This freeze does not
  require a 3×3 matrix.
- Verification and registration are **not** required to share a model
  (open in VERIFICATION_DESIGN_V1 and REGISTRATION_DESIGN_V1; D-010).
- RMSE on the same points used to fit a transform is not independent
  validation.
- Image-intensity similarity after warping is a different quantity and is
  not this metric.

### SCIENTIFICALLY VALIDATED DEFINITION

**Not established.** Official SIH RMSE (population, residual formula, units,
independent checkpoints vs fit residuals) is pending (D-011).

## 5. Inlier-count definition

### ENGINEERING IMPLEMENTATION DEFINITION

```
inlier_count = number of Correspondence items in matches whose status is "inlier"
```

This reuses the project's verification status. It does **not** invent a
second inlier test (no residual-limit re-check, no RANSAC re-run).

`RegistrationResult.inliers` is ignored even if its length differs from the
status count. Freeze v1: `matches` is the source of truth.

- `correspondences is None` → `inlier_count is None` (unavailable, not 0)
- `matches == []` → `inlier_count == 0` (measured empty set)

### SCIENTIFICALLY VALIDATED DEFINITION

**Not established.** The engineering default `residual_limit=3.0` used by
`verify_matches` is not an SIH inlier threshold.

## 6. Inlier-ratio definition

This metric is **scientifically open** (Interface Freeze v1 §8: extra
evaluation metrics and evaluator constraints are undefined; D-011).

### Ambiguity (documented, not silently picked as “the” SIH ratio)

Reasonable denominators that the current architecture could support:

| ID | Denominator | Reads as |
|---|---|---|
| **A (implemented)** | `len(CorrespondenceSet.matches)` | Fraction of the canonical correspondence collection labelled inlier |
| B | Count of items with a finite residual (geometrically evaluated) | Robust-estimator inlier rate among scored candidates |
| C | Count of items that passed validation (not invalid/duplicate) | Inlier rate among geometrically eligible candidates |
| D | `control_point_count` | **Rejected** — mixes selected controls with verified matches |

### ENGINEERING IMPLEMENTATION DEFINITION (A)

```
numerator   = inlier_count
denominator = len(matches)
inlier_ratio = numerator / denominator
```

Zero denominator (`matches` empty or `correspondences is None`): `None`,
not 0 and not 1.

A is fully determined from frozen fields, internally consistent with
`inlier_count`, and does not invent a second eligibility filter. B and C
would be defensible later if the evaluator is defined that way; they are
**not** computed in this phase.

### SCIENTIFICALLY VALIDATED DEFINITION

**Not established.** The chosen denominator is **not** the final SIH
definition.

## 7. Coverage definition

SIH asks for correspondence / control points that maintain uniform
distribution **across the images**. Coverage **must not** mean “number of
points”.

Coverage (extent) is **not** uniformity (how evenly points fill a region).
This phase implements a coverage baseline only. Occupied-cell ratio,
quadtree statistics, and nearest-neighbour spacing are **not** computed
and must not be inferred from `spatial_coverage`.

### Why a sophisticated uniformity score is not implemented

Intentionally unfrozen (Interface Freeze v1 §8, CONTROL_POINT_SELECTION_DESIGN_V1):

- pixel-centre vs pixel-corner;
- full-image spatial coordinate semantics;
- overlap-mask behaviour;
- final uniformity metric.

### ENGINEERING IMPLEMENTATION DEFINITION

Eligible control points: items in `result.control_points` with finite
`source_xy` and finite `reference_xy`.

When **all** of the following hold:

- `pair.pair_id == result.pair_id`;
- `pair.source.dimensions` and `pair.reference.dimensions` are present
  (`width_px > 0`, `height_px > 0`);
- at least one eligible control point exists;

compute axis-aligned bounding-box (AABB) area on each image:

```
source_bbox_area     = (max x − min x) * (max y − min y)   of source_xy
reference_bbox_area  = same for reference_xy
source_image_area    = width_px * height_px   of source.dimensions
reference_image_area = width_px * height_px   of reference.dimensions
source_fraction      = source_bbox_area / source_image_area
reference_fraction   = reference_bbox_area / reference_image_area
spatial_coverage     = 0.5 * (source_fraction + reference_fraction)
```

If either fraction is outside `[0, 1]` (control-point bbox larger than the
dimension product), `spatial_coverage` is `None` — the value is not clamped
to fake validity.

`ImageDimensions` are used only as a stored width×height product. This does
**not** freeze pixel origin. Coordinates are the stored tuples; they are
not shifted by 0.5. Overlap masks are not applied.

**Refused:** dividing the control-point AABB by itself. That ratio is 1 for
any non-degenerate 2D set and would fabricate perfect coverage.

**Refused:** treating `control_point_count` as coverage.

Degenerate sets (one point, or zero height or width) yield AABB area 0 and
therefore `spatial_coverage == 0.0` when dimensions are available. That is
a measured zero extent, not a missing value.

When dimensions are absent, `spatial_coverage` is `None`. The current
pipeline often has no established dimension semantics; unavailability is
preferred to an invented denominator.

### SCIENTIFICALLY VALIDATED DEFINITION

**Not established.** This AABB fraction is not proof of uniform spatial
distribution across the images, not occupied-cell ratio (v3 §19), and not
the official SIH coverage metric.

## 8. Control-point-count definition

### ENGINEERING IMPLEMENTATION DEFINITION

```
control_point_count = len(result.control_points)
```

The attached selected list, including any non-finite coordinate items if
present. Raw correspondences and inliers are **not** counted unless they
were copied into that list by a previous stage.

Empty list → `0` (measured empty selection), not `None`. The frozen field
is always a list; “not yet selected” cannot be distinguished from
“selected none”.

### SCIENTIFICALLY VALIDATED DEFINITION

Not applicable beyond counting the list. A scientifically required *N* is
not frozen.

## 9. Unavailable-data behaviour

| Situation | Field | Value |
|---|---|---|
| `correspondences is None` | `rmse`, `inlier_count`, `inlier_ratio` | `None` |
| Empty `matches` | `inlier_count` | `0` |
| Empty `matches` | `inlier_ratio`, `rmse` | `None` |
| Inliers exist but none have a finite residual | `rmse` | `None` |
| Non-finite / negative stored residual | that item | omitted from RMSE |
| `pair_id` mismatch | `spatial_coverage` | `None` |
| Missing source or reference `dimensions` | `spatial_coverage` | `None` |
| No finite control-point coordinates | `spatial_coverage` | `None` |
| AABB fraction outside `[0, 1]` | `spatial_coverage` | `None` |
| Empty `control_points` | `control_point_count` | `0` |
| Empty `control_points` | `spatial_coverage` | `None` |

**Never** substitute `0` for unavailable RMSE or ratio. **Never** substitute
`1` for “perfect” coverage, ratio, or RMSE when data are missing.

## 10. Bounds / validation

Produced values satisfy the frozen Pydantic constraints:

- `rmse` is `None` or `>= 0` (squares of finite residuals; negative RMSE is
  impossible here);
- `inlier_count` is `None` or `>= 0` and, when `matches` exists,
  `inlier_count <= len(matches)`;
- `inlier_ratio` is `None` or in `[0, 1]`;
- `spatial_coverage` is `None` or in `[0, 1]`;
- `control_point_count >= 0`.

Inconsistent snapshot vs `matches` does not raise: `matches` wins.
`evaluate` still returns a typed `RegistrationResult` so the frozen pipeline
type holds. `quality_flags` from registration are preserved; this phase does
not add evaluator grades.

Geometric correspondence residual is **not** claimed to represent
pixel-level image similarity or overall registration quality.

## 11. Synthetic-test interpretation

`tests/unit/test_evaluation.py` and
`tests/scientific/test_synthetic_evaluation.py` use constructed residuals,
statuses, coordinates, and dimensions.

They validate **implementation arithmetic and fail-closed behaviour**.

They are **not**:

- lunar scientific results;
- Chandrayaan-2 / LROC accuracy;
- official SIH evaluator scores;
- evidence of sub-pixel performance;
- a claim that the engineering denominators are scientifically optimal.

## 12. Scientific limitations

- RMSE is verification-inlier **transfer-error** RMSE, not independent
  checkpoint error, not physical error, not warped-image error.
- Inlier labels inherit verification’s unvalidated residual limit.
- Inlier ratio uses one of several defensible denominators.
- Coverage uses width×height only when dimensions are present; origin and
  overlap remain undefined. AABB area is zero for collinear axis-aligned
  sets even if they span one image axis.
- Control-point selection itself uses correspondence bounding boxes, not
  the full raster (CONTROL_POINT_SELECTION_DESIGN_V1). Evaluation coverage
  against `ImageDimensions` can therefore be small even after “spatial”
  selection.
- No intensity metric, no GSD scaling, no DEM/pushbroom model (D-010).
- `refine_points` is still unimplemented; the default pipeline still stops
  there unless a double is injected. Evaluation does not bypass that stage.

## 13. Unresolved SIH evaluation questions

- Official dataset, pairs, and evaluator implementation (D-011).
- RMSE population (all matches vs inliers vs independent checkpoints vs
  registration-transform residuals) and units (pixels vs metres).
- Inlier-ratio denominator (A/B/C above, or evaluator-specific).
- Pixel origin; whether coverage must use the overlap mask; full-image vs
  valid-pixel denominator.
- Uniformity statistic (occupied-cell ratio, nearest neighbour, quadtree).
- Whether verification and registration must share a geometric model.
- Thresholds for `confidence_class` / quality certificate (v3 §23 Feature 5).
- Whether image-similarity after warp is required by the evaluator.

## 14. Future metrics that should be experimentally evaluated

Not added to the frozen contract in this phase:

- MAE, median residual, P95 residual;
- occupied-cell ratio and nearest-neighbour uniformity (v3 §19);
- RMSE recomputed from a documented registration transform on a **held-out**
  checkpoint set;
- GSD-scaled / metre residuals when geometry defines the conversion;
- intensity similarity on the registered raster (separate from geometric
  residual);
- runtime / memory (engineering, not accuracy);
- official SIH evaluator outputs when released;
- `confidence_class` policy backed by measured thresholds.

Those require experiments on actual Chandrayaan-2 / reference datasets and,
where applicable, the official evaluator. They must not be silently encoded
in `configs/default.yaml`.
