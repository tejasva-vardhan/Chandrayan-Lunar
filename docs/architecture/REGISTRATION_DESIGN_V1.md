# SIH26166 — Baseline registration design (Phase 3)

Status: Implementation note for `src/registration/`  
Companion: Interface Freeze v1, D-010, VERIFICATION_DESIGN_V1, CONTROL_POINT_SELECTION_DESIGN_V1  
Not a rewrite of the master specification.

This is a **software baseline**. It is not the final lunar transformation,
not SIH-validated, not a sub-pixel method, and not evaluator compliance.

## 1. Purpose

Estimate a replaceable 2D map from selected control points, validate it, and
warp the source raster onto a reference-shaped grid when a raster handle is
available. Produce a `RegistrationResult` with only values that were actually
computed.

## 2. Inputs / outputs

Frozen surface (unchanged):

```
register(pair, control_points, correspondences) -> RegistrationResult
```

Configurable: `register_with_settings(..., settings: RegistrationSettings)`.

- Control points: used for transform estimation. Matching and verification are
  not re-run. Raw matches are not substituted.
- `CorrespondenceSet` is attached as `RegistrationResult.correspondences`.
  `inliers` is a snapshot of matches already labeled `inlier`. Empty if none.
- `metrics`, `confidence_class`, and `provenance` stay unset. Evaluation
  is a later phase.
- `ControlPoint.uncertainty` is not invented.

## 3. Baseline transformation model

Registry (not a frozen enum):

| `model_id` | Algebra | Role |
|---|---|---|
| `projective_2d_baseline` | 8-dof 2D projective map, normalized DLT | SOFTWARE BASELINE |
| `affine_2d_baseline` | 6-dof affine least squares | SOFTWARE BASELINE |

`register()` wires `projective_2d_baseline` because the frozen two-argument
API needs a default and that family is the same coordinate convention as
verification's software baseline. That is **not** a claim that homography is
the correct model for all Chandrayaan-2 scenes (D-010).

DEM, pushbroom, RPC, and polynomial models are not implemented.

## 4. Why it is only a software baseline

- No official SIH dataset or evaluator (D-011).
- No terrain / sensor-model evidence that a global 2D projective map is
  physically adequate.
- Defaults exist only because `register(...)` cannot take a settings object.
- Synthetic tests check software correctness, not lunar accuracy.

## 5. Transformation estimation

Eligible control points: finite coordinates; exact `(source_xy,
reference_xy)` duplicates keep the first.

The selected model is fit by least squares / DLT on **all** eligible points.
RANSAC is not repeated (control points already passed verification and spatial
selection).

## 6. Validation

Engineering safeguards (not SIH thresholds): finite 3×3 matrix, non-zero
norm, `|det|` above `1e-12`, invertible inverse, finite inverse. Failure → no
transform, no warped file.

## 7. Image warping

Inverse mapping: for each output pixel `(x, y)` on the output grid,

```
[u, v, w]^T = inverse(matrix) @ [x, y, 1]^T
sample source at (u/w, v/w)
```

Same pixel-tuple convention as verification. Origin centre vs corner is not
interpreted.

## 8. Interpolation

Bilinear resampling in float64. Out-of-bounds or non-finite homogeneous
scale → NaN. This is **image resampling**, not sub-pixel point refinement
(D-006).

Output grid: reference `.npy` shape when that raster loads; otherwise source
shape. Output is not a radiometric product.

## 9. Numerical safeguards

| Item | Classification |
|---|---|
| Rank / matrix-norm floors `1e-10` / `1e-12` | Engineering linear algebra |
| `|det|` and inverse checks `1e-12` | Engineering invertibility |
| Homogeneous `|w|` floor `1e-12` | Engineering division guard |
| Inverse-map border epsilon `1e-6` | Engineering float guard so integer output pixels that round-trip slightly outside `[0, W-1]` still sample |

## 10. Failure conditions

Typed `RegistrationResult` is always returned (frozen pipeline type). Flags
are engineering labels, not evaluator grades:

| Flag | Meaning |
|---|---|
| `insufficient_control_points` | Fewer unique finite points than the model minimum |
| `degenerate_control_points` | Fit returned None (collinear / rank-deficient) |
| `invalid_transformation` | Failed invertibility / finite checks |
| `source_raster_unavailable` | No `raster_uri` or unreadable path |
| `unsupported_raster_encoding` | Not `.npy` (SIH format is not frozen) |
| `warp_failed` | Warp or write failed after a valid matrix |

No placeholder image is written on failure.

## 11. Assumptions

- Control points are already selected; this module does not improve them.
- Raster URIs, when present, are filesystem paths to NumPy `.npy` arrays
  for this software baseline only.
- Registered file is written next to the source as `{stem}.registered.npy`.
  That is an engineering handle, not the SIH export package (`src/io`).

## 12. Limitations

- 2D projective/affine maps ignore terrain relief and pushbroom geometry.
- `.npy` is not Chandrayaan-2 PDS/GeoTIFF ingestion.
- Bilinear interpolation is not claimed optimal.
- `register` has no `output_dir`; the registered path is derived from the
  source URI.
- Full-pipeline `ScientificPipeline.run` still stops at unimplemented
  `refine_points` unless a double is injected.

## 13. Scientifically unresolved questions

- Final transformation family for lunar scenes (D-010)
- Whether registration and verification must share a model
- Pixel origin; product raster format
- Output CRS / map projection
- Interpolation policy on real products
- RMSE and other metrics (evaluation phase)
- Official SIH evaluator (D-011)
