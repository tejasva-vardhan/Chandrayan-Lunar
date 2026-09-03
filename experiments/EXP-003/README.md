# EXP-003 — Scale robustness on pair_01_equatorial

Branch: `feature/tejas-exp003-scale-robustness` (from latest `main`, including merged EXP-001 and EXP-002).

This experiment asks one question: **is the existing SIFT correspondence pipeline robust when the relative scale of the LROC matching view is deliberately changed, with OHRC held fixed?**

EXP-002 showed that its proposed common-GSD policy was a **no-op** on pair 01 (OHRC stride 15 / LROC stride 8 remained unchanged). EXP-003 therefore changes the integer stride actually applied to the LROC raster so SIFT sees a different image.

It is **not** a matcher freeze (D-007), not a lunar-transform freeze (D-010), and not official SIH evidence (D-011).

## Hypothesis

**H1.** On pair_01_equatorial, approximately 2× additional LROC matching-view downscaling and approximately 2× finer LROC sampling, with OHRC held at the EXP-000 stride, leave verified SIFT inlier counts equal to the EXP-000 baseline.

**H0.** Those relative LROC scale changes materially affect verified correspondence yield on this pair.

**Decision rule (fixed before the real-data run).** The independent variable is valid only if LROC matching-view strides actually differ across A/B/C while the OHRC stride stays at 15. Scale robustness is supported only if verified inlier counts for B and C both equal A. Any difference in verified inliers is a material effect and rejects scale robustness on this pair.

Do **not** treat four-point DLT residuals as accuracy. Independent accuracy remains **NOT VALIDATED**. One pair cannot establish general SIFT scale invariance.

## Pair

Same products as EXP-000 / EXP-001 / EXP-002 pair 01:

| Role | Product | Format |
|---|---|---|
| Source | `ch2_ohr_ncp_20210402T0546284043_d_img_d18` | Chandrayaan-2 OHRC PDS4 |
| Reference | `M150368601RC` | LROC NAC CDR PDS3 |
| Manifest id | `pair_01_equatorial` | `data/manifests/demo_pairs.yaml` |

Dataset root: `CHANDRAYAN_DATA_ROOT` (`D:\SIH` when mounted). This session ran from previously ingested raster handles because `D:\SIH` was not mounted: OHRC `data/processed/*.npy` and LROC temp ingestion-cache `.npy`. Array shapes match the EXP-000 ingested products (78175×12000 and 52224×5064). Do not commit raw products.

## Exact run command

```powershell
$env:CHANDRAYAN_DATA_ROOT = "<external demo dataset containing the declared products>"
python scripts/run_exp003.py
```

When the raw products are not mounted, the same pipeline can be started from the already-ingested raster handles via `run_exp003_from_products`.

Lightweight record: `experiments/EXP-003/results/pair_01_equatorial.json`
Full record: `outputs/EXP-003/` (gitignored)

Exact configuration: [`config.yaml`](config.yaml), authored from `src/io/exp003/config.py`.

## Frozen pipeline (unchanged)

ingest → characterize_pair → preprocess → generate_representation → match → verify_matches → select_control_points → refine_points → register → evaluate

Owning callables are used as-is. Variant A calls frozen `generate_representation(pair)`. Variants B and C call `generate_representation_with_settings` with a relative LROC stride factor. All three call frozen `match()`.

EXP-003 does not rewrite verification, control-point selection, refinement, registration, SPICE, frontend, or the 16,777,216-pixel registration cap. Diagnostic rasters are not written. SIFT and RANSAC are not retuned per variant.

## What is held constant

Copied from the EXP-000 snapshot (`src/io/exp000/config.py`). Tests assert the fixed block is identical.

| Item | Value |
|---|---|
| Matcher | SIFT (nfeatures=0, nOctaveLayers=3, contrast=0.04, edge=10, sigma=1.6, ratio=0.75, min_matches=4) |
| OHRC matching view | EXP-000 pixel-budget stride 15 |
| Matching-view budget | 4,194,304 pixels/image on the baseline / coarsened arms |
| Downsample | `stride_decimation` of the source raster (the pixels SIFT sees change; metadata GSD is not the intervention) |
| Coordinate mapping | `x_original = x_matching * stride`, `y_original = y_matching * stride` |
| Representation | difficulty None/easy → intensity (2–98 percentile stretch) |
| Verification | `projective_2d_baseline` + `ransac_style_baseline`, residual_limit=3.0, max_trials=500, rng_seed=0 |
| Control points | grid_bins=8, max_per_cell=1 |
| Refinement | `zncc_parabolic_baseline` (same window/search/ZNCC settings as EXP-000) |
| Registration model | `projective_2d_baseline` |
| Registration cap | 16,777,216 pixels (**not raised**) |
| Preprocess on this pair | identity passthrough (full rasters exceed the cap) |

## Independent variable

| Variant | LROC relative stride factor | Expected pair-01 strides (OHRC / LROC) | Matching-view rule |
|---|---|---|---|
| A | none (frozen EXP-000 path) | 15 / 8 | `stride = ceil(sqrt(pixels / 4194304))` independently per image |
| B | 2.0 | 15 / 16 | LROC stride = `round(pixel_budget_stride * 2)`; OHRC unchanged |
| C | 0.5 | 15 / 4 | LROC stride = `round(pixel_budget_stride * 0.5)`; OHRC unchanged |

Variant C's pair-01 LROC view (stride 4) exceeds the 4,194,304-pixel matching-view budget. That overrun is required so SIFT actually sees a finer raster. The registration output cap is not raised.

No parameter was changed after seeing a result.

## EXP-002 context

EXP-002's common-GSD policy selected the same integer strides as EXP-000 on this pair, so it did not test scale robustness. This experiment holds SIFT constant and forces a real relative-scale change on LROC only.

## Results

**Status: `completed`. Failed stage: none.** Variant A reproduced the EXP-000 SIFT counts exactly (36 raw → 4 verified, coverage 0.23236). Variants B and C changed the LROC matching view (stride 16 and 4) while OHRC stayed at stride 15, so the independent variable was actually applied.

Independent accuracy = **NOT VALIDATED**.

| Variant | Matching view (OHRC / LROC) | Stride | Resampling | Raw | Verified | Inlier ratio | Coverage | CPs | Transform | Refinement | Runtime (variant) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 5212×800 / 6528×633 | 15 / 8 | stride_decimation | 36 | 4 | 11.11% | 0.23236 | 4 | fitted; full raster blocked by cap | INDETERMINATE | 14.79 s (match 4.79 s) |
| B | 5212×800 / 3264×317 | 15 / 16 | stride_decimation | 45 | 4 | 8.89% | 0.42571 | 4 | fitted; full raster blocked by cap | COORDINATES_UPDATED | 3.45 s (match 1.48 s) |
| C | 5212×800 / 13056×1266 | 15 / 4 | stride_decimation | 11 | 4 | 36.36% | 0.21051 | 4 | fitted; full raster blocked by cap | COORDINATES_UPDATED | 29.33 s (match 25.54 s) |

Coverage is verified-match bounding-box area fraction. Variant C's LROC view is 16,528,896 pixels, which exceeds the 4,194,304 matching-view budget; that overrun is required so SIFT sees a finer raster. Variant B representation was faster because the OHRC `.npy` handle was already warm from Variant A; match times are the comparable figure.

**Primary metric (verified inliers): A = 4, B = 4, C = 4.** Verified inlier **count** did not change. Under the pre-registered decision rule, **H1 is supported** on that count. The four-point DLT fit remains unfalsifiable on every arm.

Raw Lowe-ratio matches **did** change (36 / 45 / 11), and coverage / refinement differ, so the four inliers are not the same correspondence set. Detector-level yield is not scale-invariant. Do not read fit residuals as registration accuracy. Do not claim general SIFT scale invariance from one pair.

## What this does and does not show

Relative LROC matching-view scale **does** change the image SIFT sees (strides 8 vs 16 vs 4, matching-view shapes 6528×633 vs 3264×317 vs 13056×1266). On this pair that did **not** move verified inlier count off the four-point DLT minimum. It **did** change raw match count, inlier ratio, spatial coverage, and whether refinement updated coordinates.

This does not validate registration accuracy. It does not test other pairs. It does not retune SIFT or RANSAC.

## Limitations / confounders

- independent accuracy = NOT VALIDATED. No surveyed lunar control exists.
- Four-point DLT residuals are an algebraic identity.
- All three arms produced exactly four verified inliers, so equal verified yield is consistent with robustness and also with an unfalsifiable four-point consensus set.
- Raw Lowe-ratio matches changed (36 / 45 / 11), so detector-level correspondence yield is not scale-invariant even when verified counts are equal.
- Variant C exceeds the 4,194,304-pixel matching-view budget; the registration output cap was not raised.
- Overlap is not recomputed from the products.
- Full-raster registration remains blocked by the 16,777,216-pixel cap.
- One pair only. No EXP-004 work was started.

## Distinctions this experiment must keep

1. **Raw matches** — after Lowe ratio test, `status == "raw"`.
2. **Verified matches** — RANSAC-style projective software baseline.
3. **Selected control points** — spatial grid on verified inliers.
4. **Refined points** — ZNCC parabolic baseline; zero change is INDETERMINATE.
5. **Fitted transformation** — DLT on selected/refined points.
6. **Registration output** — full raster blocked by the existing cap.
7. **Evaluation** — verification residuals vs independent accuracy (`NOT VALIDATED`).

Projective DLT residuals on **exactly four** control points are the DLT minimum and **must not** be read as registration accuracy.
