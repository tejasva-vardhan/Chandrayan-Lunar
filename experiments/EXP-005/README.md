# EXP-005 — Subpixel Refinement Ablation on pair_02_mid_equatorial

Branch: `feature/tejas-exp005-subpixel-refinement` (from latest `main`, including merged EXP-001 through EXP-004).

This experiment asks one question: **does the existing ZNCC + parabolic subpixel refinement produce measurable, reproducible coordinate changes that improve held-out geometric consistency on pair_02_mid_equatorial?**

It is **not** a redesign of the refinement algorithm. It is **not** a new matcher. It is **not** a change to SIFT, representation, RANSAC, registration, SPICE, or frontend.

## Hypothesis

**H1.** On pair_02_mid_equatorial, with the EXP-001 SIFT configuration held fixed, the existing ZNCC + parabolic refinement produces measurable coordinate changes relative to identity passthrough, and those changes strictly reduce held-out image-space transfer error on the same matcher-derived checkpoints.

**H0.** The existing refinement either does not change coordinates, or the changes do not improve held-out geometric consistency.

**Decision rule (fixed before the real-data run).** Refinement is treated as improving held-out geometric consistency only if Variant B changes at least one coordinate **and** the same held-out checkpoint RMSE is strictly lower for B than for A. Coordinate change alone is not accuracy. Matcher-derived held-out points are not ground truth. Independent accuracy remains **NOT VALIDATED**. One pair cannot validate sub-pixel accuracy.

## Pair

Same products as EXP-001 pair_02:

| Role | Product | Format |
|---|---|---|
| Source | `ch2_ohr_ncp_20250612T2229094979_d_img_d18` | Chandrayaan-2 OHRC PDS4 |
| Reference | `M1504316436RC` | LROC NAC CDR PDS3 |
| Manifest id | `pair_02_mid_equatorial` | `data/manifests/demo_pairs.yaml` |

Dataset root: `CHANDRAYAN_DATA_ROOT` = `D:\SIH`.

```powershell
$env:CHANDRAYAN_DATA_ROOT = "D:\SIH"
python scripts/run_exp005.py
```

Lightweight record: `experiments/EXP-005/results/pair_02_mid_equatorial.json`
Full record: `outputs/EXP-005/` (gitignored)

Exact configuration: [`config.yaml`](config.yaml), authored from `src/io/exp005/config.py`.

## Frozen pipeline (unchanged)

ingest → characterize_pair → preprocess → **generate_representation → match → verify_matches → select_control_points [shared]** → **refine_points [A vs B]** → register → evaluate

Match, verification, RANSAC, representation, and control-point selection are shared across variants. Only the refinement callable differs.

## What is held constant

Inherited from EXP-000 snapshot. Tests assert the fixed block matches.

| Item | Value |
|---|---|
| Matcher | SIFT (nfeatures=0, nOctaveLayers=3, contrast=0.04, edge=10, sigma=1.6, ratio=0.75, min_matches=4) |
| Matching view | EXP-000 pixel-budget stride: OHRC 16, LROC 8 (pair_02 specific) |
| Matching-view budget | 4,194,304 pixels/image |
| Downsample | `stride_decimation` of the source raster |
| Coordinate mapping | `x_original = x_matching * stride`, `y_original = y_matching * stride` |
| Verification | `projective_2d_baseline` + `ransac_style_baseline`, residual_limit=3.0, max_trials=500, rng_seed=0 |
| Control points | grid_bins=8, max_per_cell=1 |
| Registration model | `projective_2d_baseline` |
| Registration cap | 16,777,216 pixels (**not raised**) |
| Preprocess on this pair | identity passthrough (full rasters exceed the cap) |
| ZNCC window_radius | 7 |
| ZNCC search_radius | 3 |
| ZNCC min_peak_zncc | 0.25 |
| ZNCC min_valid_pixel_fraction | 0.75 |
| ZNCC fine_half_width | 1.0 |
| ZNCC fine_step | 0.1 |

## Independent variable

| Variant | Refinement | Callable | Role |
|---|---|---|---|
| A | identity passthrough | `refine_points_with_settings(..., identity_passthrough)` | ablation, no refinement |
| B | existing ZNCC + parabolic baseline | `refine_points(control_points, pair)` (frozen defaults) | same-modality software baseline |

No parameter was changed after seeing any result.

## EXP-001 context

EXP-001 (SIFT on pair_02) produced 25 verified inliers, 11 control points, transform fitted. Refinement in EXP-001 was fixed at `zncc_parabolic_baseline` for all matchers. The SIFT arm recorded `coordinates_changed_count = 2` with `outcome = COORDINATES_UPDATED`. EXP-005 repeats this on the same pair with an explicit A/B ablation so both unrefined and refined held-out RMSE are directly measurable.

## Results

**Status: `completed`. Failed stage: none.**
Live run at git commit `91fd3c8d7e1355c4dbd10f4e9108d3f328d18c87`, platform Windows-11-10.0.26200.

Independent accuracy = **NOT VALIDATED**.

### A vs B table (live measurements)

| Metric | A — identity_passthrough | B — zncc_parabolic_baseline |
|---|---|---|
| Raw matches (shared) | 919 | 919 |
| Verified inliers (shared) | 25 | 25 |
| Inlier ratio (shared) | 2.72% | 2.72% |
| Control points (shared) | 11 | 11 |
| Transform fitted | ✓ | ✓ |
| **Coordinates changed** | **0** | **2** |
| ZNCC accepted / rejected | N/A | **2 / 9** |
| ZNCC acceptance rate | — | **18.2% (2/11)** |
| Mean displacement (px) | 0.0 | **0.439** |
| Max displacement (px) | 0.0 | **2.732** |
| Refinement outcome | INDETERMINATE | COORDINATES_UPDATED |
| **Unselected-checkpoint RMSE** (14 pts, primary) | **2.124 px** | **2.221 px** |
| Control-point k-fold RMSE (11 pts, secondary) | 1.782 px | 3.542 px |
| Fit diagnostic RMSE (not accuracy) | 1.686 px | 1.686 px |
| Variant runtime | 0.015 s | 1.309 s |
| Full-raster warp | blocked (16 MP cap) | blocked (16 MP cap) |

`Fit diagnostic RMSE` = RMSE of stored verification-inlier residuals from the points used to fit the transform. It does **not** recompute residuals after refinement and is **not** accuracy.

### Shared pre-selection k-fold (all 25 verified inliers — identical for A and B)

| Metric | Value |
|---|---|
| Held-out points | 25 |
| Mean transfer error | 1.739 px |
| Median transfer error | 1.796 px |
| Min / Max | 0.346 / 3.098 px |
| RMSE | **1.904 px** |

Uses unrefined coordinates; applies equally to both variants. Not differentiated by refinement.

## Number of coordinates changed

**Variant A: 0** (identity passthrough, by definition). **Variant B: 2 of 11** control points received sub-pixel corrections from ZNCC. Nine points were rejected by the refinement guard (ZNCC < 0.25 at the keypoint patch).

### Per-point ZNCC detail (Variant B)

| Index | Accepted | ZNCC before | ZNCC after | Displacement (px) | Estimated (dx, dy) |
|---|---|---|---|---|---|
| 0 | ✗ | −0.272 | −0.272 | 0.0 | — |
| 1 | ✗ | +0.216 | +0.216 | 0.0 | — |
| 2 | ✗ | −0.198 | −0.198 | 0.0 | — |
| 3 | ✓ | +0.255 | **+0.357** | **2.097** | (−1.294, +1.650) |
| 4 | ✗ | +0.162 | +0.162 | 0.0 | — |
| 5 | ✗ | −0.016 | −0.016 | 0.0 | — |
| 6 | ✓ | +0.242 | **+0.462** | **2.732** | (+2.370, −1.359) |
| 7 | ✗ | −0.246 | −0.246 | 0.0 | — |
| 8 | ✗ | −0.028 | −0.028 | 0.0 | — |
| 9 | ✗ | −0.182 | −0.182 | 0.0 | — |
| 10 | ✗ | −0.226 | −0.226 | 0.0 | — |

Rejection reason for 9/11 points: the ZNCC value at the SIFT keypoint position itself was below `min_peak_zncc = 0.25`. Eight of the nine had negative ZNCC — the intensity patches at those locations have no meaningful correlation structure in the matching view. One additional point (index 1) had ZNCC = 0.216, just below threshold. The frozen `ControlPoint` contract does not expose a per-point rejection code; rejection reasons are inferred from the stored ZNCC values.

## Mean / max displacement (Variant B, live)

- **Mean over all 11 points: 0.439 px** (9 zeros, 2 non-zero)
- **Mean over 2 changed points only: 2.414 px**
- **Max displacement: 2.732 px** (point index 6)

## Held-out metric before vs after

Primary metric: **unselected-checkpoint RMSE** — 14 verified inliers not selected as control points, scored against the transform fitted on the 11 control points (unrefined for A, refined for B). The same 14 checkpoints are used for both variants.

| | A (identity) | B (ZNCC) | Δ |
|---|---|---|---|
| Unselected-checkpoint RMSE (primary) | **2.124 px** | **2.221 px** | B worse by **+0.097 px** |
| Control-point k-fold RMSE (secondary) | 1.782 px | 3.542 px | B worse by **+1.760 px** |

**B did not reduce the held-out RMSE on either metric.** Under the pre-registered decision rule, **H1 is NOT SUPPORTED**.

## Did refinement produce measurable improvement?

**Coordinate change: YES** — 2 of 11 coordinates were measurably updated (confirmed `COORDINATES_UPDATED`, B ≠ A). This is not in question.

**Held-out geometric improvement: NO.** Unselected-checkpoint RMSE is 2.221 px for B vs 2.124 px for A — B is worse by 0.097 px. The control-point k-fold RMSE is also worse for B (3.542 vs 1.782 px). Neither metric shows improvement.

Do not interpret this as "refinement is harmful." With only 2 of 11 coordinates changed and 14 held-out checkpoints, the signal is too small to attribute the direction of change to refinement vs sampling noise. The pre-registered conclusion is: **refinement is not shown to improve held-out geometric consistency on this pair**.

## Independent validation status

**Independent accuracy = NOT VALIDATED.** No surveyed lunar control exists. All held-out points are matcher-derived (SIFT + RANSAC). ZNCC acceptance rate (18.2%) and coordinate displacement are not accuracy measurements.

## Limitations

1. **Independent accuracy is NOT VALIDATED.** No surveyed lunar control exists.
2. **Matcher-derived held-out points are not ground truth.** All 14 unselected-checkpoint and 11 k-fold points are produced by SIFT + RANSAC, not by independent geodetic survey.
3. **Coordinate change is not accuracy.** 2 coordinates changed; this does not imply improved registration.
4. `evaluate().rmse` is stored verification-inlier residual RMSE and does **not** recompute residuals after refinement.
5. ZNCC + parabolic is a same-modality intensity comparison at the 16 px / 8 px stride scale. Sub-pixel corrections at this scale are sub-stride-pixel, not sub-GSD-pixel (OHRC GSD ≈ 0.28 m).
6. Only 2/11 ZNCC attempts were accepted (18.2%). 8 of the 9 rejected points had negative ZNCC at the keypoint patch, meaning the intensity patches had no usable correlation structure in the matching view.
7. With only 2 changed coordinates and 14 held-out checkpoints, the sample is too small to separate refinement effect from sampling noise. The held-out error difference (0.097 px) is not significant given this sample size.
8. Overlap is not recomputed from the products.
9. Full-raster registration remains blocked by the 16,777,216-pixel cap.
10. Pair_02_mid_equatorial only. No algorithm was changed. This is validation of the existing baseline, not improvement.

## Distinctions this experiment must keep

1. **Raw matches** — after Lowe ratio test, `status == "raw"`.
2. **Verified matches** — RANSAC-style projective software baseline.
3. **Selected control points** — spatial grid on verified inliers.
4. **Refined points** — ZNCC parabolic baseline; zero change is INDETERMINATE.
5. **Fitted transformation** — DLT on selected / refined points.
6. **Registration output** — full raster blocked by the existing cap.
7. **Evaluation** — verification residuals vs independent accuracy (`NOT VALIDATED`).

Projective DLT residuals are a fit diagnostic. Coordinate change is not accuracy. ZNCC acceptance is not accuracy. Held-out RMSE from matcher-derived points is not independent accuracy.
