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

Dataset root: `CHANDRAYAN_DATA_ROOT` (`D:\SIH` when mounted). **D:\SIH was not mounted during this session.** EXP-001 ran this pair previously (git commit `779caec`). Metrics in the results JSON are derived from that EXP-001 SIFT arm record. When D:\SIH is remounted:

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

EXP-001 (SIFT on pair_02) produced 25 verified inliers, 11 control points, transform fitted. The refinement in EXP-001 was fixed at `zncc_parabolic_baseline` for all matchers. The SIFT arm recorded `coordinates_changed_count = 2` with `outcome = COORDINATES_UPDATED`. This is the source of the Variant B coordinate-change count in this record.

## Results

**Status: data_unavailable.** D:\SIH was not mounted during this session. The metrics below derive from the EXP-001 SIFT arm record (git commit `779caec`). When D:\SIH is remounted and `python scripts/run_exp005.py` is run, the JSON will be overwritten with a live record including displacement magnitudes and per-variant held-out RMSE.

Independent accuracy = **NOT VALIDATED**.

### A vs B table (from EXP-001 SIFT arm + identity derivation)

| Metric | A — identity_passthrough | B — zncc_parabolic_baseline |
|---|---|---|
| Verified inliers (shared) | 25 | 25 |
| Control points (shared) | 11 | 11 |
| Transform fitted | ✓ | ✓ |
| Coordinates changed | **0** | **2** |
| ZNCC accepted / rejected | N/A (identity) | **2 accepted / 9 rejected** |
| ZNCC acceptance rate | — | **18.2% (2/11)** |
| Mean displacement (px) | 0.0 | not stored in EXP-001 |
| Max displacement (px) | 0.0 | not stored in EXP-001 |
| Refinement outcome | INDETERMINATE | COORDINATES_UPDATED |
| Unselected-checkpoint RMSE | REQUIRES_LIVE_RUN | REQUIRES_LIVE_RUN |
| Control-point k-fold RMSE | REQUIRES_LIVE_RUN | REQUIRES_LIVE_RUN |
| evaluate().rmse (fit diag) | 1.6862 px | 1.6862 px |
| Full-raster warp | blocked by 16 MP cap | blocked by 16 MP cap |

`evaluate().rmse` is the RMSE of stored verification residuals and does **not** recompute residuals after refinement. It is a fit diagnostic, not accuracy.

### Shared EXP-001 held-out k-fold (all 25 verified inliers, pre-control-point selection)

This is the k-fold split from EXP-001 which applies equally to A and B because it runs before control-point grid selection. It uses unrefined verification coordinates and is not differentiated by refinement variant.

| Metric | Value |
|---|---|
| Held-out points | 25 |
| Mean transfer error | 1.7389 px |
| Median transfer error | 1.7960 px |
| Min transfer error | 0.3457 px |
| Max transfer error | 3.0981 px |
| RMSE | **1.9044 px** |
| Status | HELD_OUT_CROSS_VALIDATION_COMPLETED |

Independent accuracy = NOT VALIDATED. Held-out points are matcher-derived.

## Number of coordinates changed

**Variant A: 0 coordinates changed** (identity passthrough, by definition).

**Variant B: 2 of 11 coordinates changed** (ZNCC acceptance rate 18.2%). ZNCC rejected 9/11 refinement candidates — each point failed either the `min_peak_zncc = 0.25` threshold or the `min_valid_pixel_fraction = 0.75` requirement, so their coordinates were left at the SIFT keypoint position. Only 2 points passed and received a sub-pixel correction.

## Mean / max displacement

Mean and max displacement in pixels for Variant B are **not recoverable from this record** — EXP-001 stores only the count of changed coordinates, not the before/after coordinate values of those 2 points. A live run of `python scripts/run_exp005.py` (with D:\SIH mounted) will compute and store the displacement magnitudes.

## Held-out metric before vs after refinement

The per-variant unselected-checkpoint RMSE (14 verified inliers not selected as control points, scored against the transform fitted on the 11 control points) and the control-point k-fold RMSE **require a live run**. They are recorded as `REQUIRES_LIVE_RUN` in the JSON.

The shared EXP-001 k-fold (RMSE = 1.9044 px on 25 inliers) applies to both variants before any refinement differentiation and does not answer whether refinement improved held-out error.

## Did refinement produce measurable improvement?

**Coordinates changed: YES** — 2 of 11 coordinates were updated by ZNCC (B ≠ A by coordinate count).

**Held-out improvement: CANNOT DETERMINE from this record** — the per-variant held-out RMSE comparison (A vs B on 14 unselected inliers or k-fold on 11 control points) requires a live run.

Under the pre-registered decision rule, **H1 cannot be evaluated** without the live per-variant held-out RMSE. The coordinate-change signal is present (2/11 = 18.2% of control points updated by ZNCC), but whether those changes reduce held-out geometric error requires running both variants live.

## Independent validation status

**Independent accuracy = NOT VALIDATED.** There is no surveyed lunar control in this project's data. Matcher-derived held-out points are not ground truth. ZNCC acceptance does not equal accuracy improvement.

## Limitations

1. **Independent accuracy is NOT VALIDATED.** No surveyed lunar control exists.
2. **Matcher-derived held-out points are not ground truth.**
3. **Coordinate change is not accuracy.** 2 coordinates changed; this is not evidence of improved registration.
4. `evaluate().rmse` is stored verification-inlier residual RMSE and does **not** recompute residuals after refinement.
5. ZNCC + parabolic is a same-modality software baseline. It compares OHRC intensity patches with LROC intensity patches at 16 px / 8 px stride resolution respectively. It is not a multimodal OHRC/LROC solution.
6. Overlap is not recomputed from the products. The manifest declares `overlap_status=verified` from NASA PDS ODE footprints.
7. Full-raster registration remains blocked by the existing 16,777,216-pixel cap.
8. This experiment runs pair_02_mid_equatorial only.
9. **D:\SIH was not mounted.** Displacement magnitudes and per-variant held-out RMSE require a live run.
10. 9/11 ZNCC refinement attempts were rejected (81.8% rejection rate). The per-point rejection reason (below min_peak_zncc vs below min_valid_pixel_fraction) is not recoverable from EXP-001 data.
11. No refinement algorithm, matcher, SIFT, representation, RANSAC, or registration change was introduced. This is validation of the existing baseline, not improvement.

## What this does and does not show

The existing ZNCC + parabolic refinement **does** update coordinates on pair_02 — 2 of 11 control points received a sub-pixel correction (18.2% acceptance rate). The remaining 9 were rejected by the ZNCC threshold or valid-pixel-fraction guard, leaving their coordinates at the SIFT keypoint position.

Whether those 2 coordinate updates reduce held-out geometric transfer error is **not determined** by this record. That question requires a live A vs B run (identity vs ZNCC) with the unselected-verified-checkpoint scorer active on the same 14 remaining inliers.

This does not validate registration accuracy. It does not test other pairs. It does not retune SIFT, RANSAC, or ZNCC. It does not invent a new refinement method.

## Distinctions this experiment must keep

1. **Raw matches** — after Lowe ratio test, `status == "raw"`.
2. **Verified matches** — RANSAC-style projective software baseline.
3. **Selected control points** — spatial grid on verified inliers.
4. **Refined points** — ZNCC parabolic baseline; zero change is INDETERMINATE.
5. **Fitted transformation** — DLT on selected / refined points.
6. **Registration output** — full raster blocked by the existing cap.
7. **Evaluation** — verification residuals vs independent accuracy (`NOT VALIDATED`).

Projective DLT residuals are a fit diagnostic. Coordinate change is not accuracy. ZNCC acceptance is not accuracy.
