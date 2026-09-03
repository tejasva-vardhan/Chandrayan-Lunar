# EXP-004 — Representation comparison on pair_01_equatorial

Branch: `feature/tejas-exp004-representation-comparison` (from latest `main`, including merged EXP-001, EXP-002, and EXP-003).

This experiment asks one question: **does changing the existing image representation, while keeping everything else fixed, increase verified SIFT correspondences on pair_01?**

EXP-003 showed that changing LROC matching-view scale changed raw SIFT detections but did not move verified inliers above the four-point floor. EXP-004 therefore changes **only** `representation_id`.

It is **not** a matcher freeze (D-007), not a lunar-transform freeze (D-010), and not official SIH evidence (D-011).

## Hypothesis

**H1.** On pair_01_equatorial, replacing the EXP-000 intensity representation with the existing gradient or structural representation, holding matching-view scale, SIFT, Lowe ratio, and geometric verification fixed, increases verified SIFT inlier count.

**H0.** Those representation changes do not increase verified correspondence yield on this pair.

**Decision rule (fixed before the real-data run).** The independent variable is valid only if `representation_id` actually differs across A/B/C (intensity / gradient / structural) while matching-view strides stay at OHRC 15 / LROC 8. Representation is treated as improving verified correspondence only if B or C produces strictly more verified inliers than A.

Do **not** treat four-point DLT residuals as accuracy. Independent accuracy remains **NOT VALIDATED**. One pair cannot establish a superior representation.

## Pair

Same products as EXP-000 / EXP-001 / EXP-002 / EXP-003 pair 01:

| Role | Product | Format |
|---|---|---|
| Source | `ch2_ohr_ncp_20210402T0546284043_d_img_d18` | Chandrayaan-2 OHRC PDS4 |
| Reference | `M150368601RC` | LROC NAC CDR PDS3 |
| Manifest id | `pair_01_equatorial` | `data/manifests/demo_pairs.yaml` |

Dataset root: `CHANDRAYAN_DATA_ROOT` (`D:\SIH` when mounted). This session ran from previously ingested raster handles because `D:\SIH` was not mounted: OHRC `data/processed/*.npy` and LROC temp ingestion-cache `.npy`. Array shapes match the EXP-000 ingested products (78175×12000 and 52224×5064). Do not commit raw products.

## Exact run command

```powershell
$env:CHANDRAYAN_DATA_ROOT = "<external demo dataset containing the declared products>"
python scripts/run_exp004.py
```

When the raw products are not mounted, the same pipeline can be started from the already-ingested raster handles via `run_exp004_from_products`.

Lightweight record: `experiments/EXP-004/results/pair_01_equatorial.json`
Full record: `outputs/EXP-004/` (gitignored)

Exact configuration: [`config.yaml`](config.yaml), authored from `src/io/exp004/config.py`.

## Frozen pipeline (unchanged)

ingest → characterize_pair → preprocess → generate_representation → match → verify_matches → select_control_points → refine_points → register → evaluate

Owning callables are used as-is. All three variants call frozen `generate_representation()`. Variants B and C copy `characterization.difficulty` onto a pair used **only** for representation generation so existing `select_representation_id` routes to gradient / structural. `match()` and later stages keep the original pair. SIFT remains selected for every difficulty.

EXP-004 does not rewrite verification, control-point selection, refinement, registration, SPICE, frontend, or the 16,777,216-pixel registration cap. Diagnostic rasters are not written. SIFT and RANSAC are not retuned per variant. No new representation is invented.

## What is held constant

Copied from the EXP-000 snapshot (`src/io/exp000/config.py`). Tests assert the fixed block is identical.

| Item | Value |
|---|---|
| Matcher | SIFT (nfeatures=0, nOctaveLayers=3, contrast=0.04, edge=10, sigma=1.6, ratio=0.75, min_matches=4) |
| Matching view | EXP-000 pixel-budget stride: OHRC 15, LROC 8 |
| Matching-view budget | 4,194,304 pixels/image |
| Downsample | `stride_decimation` of the source raster |
| Coordinate mapping | `x_original = x_matching * stride`, `y_original = y_matching * stride` |
| Verification | `projective_2d_baseline` + `ransac_style_baseline`, residual_limit=3.0, max_trials=500, rng_seed=0 |
| Control points | grid_bins=8, max_per_cell=1 |
| Refinement | `zncc_parabolic_baseline` (same window/search/ZNCC settings as EXP-000) |
| Registration model | `projective_2d_baseline` |
| Registration cap | 16,777,216 pixels (**not raised**) |
| Preprocess on this pair | identity passthrough (full rasters exceed the cap) |

## Independent variable

| Variant | Representation | Existing module | Routing lever | Expected pair-01 strides (OHRC / LROC) |
|---|---|---|---|---|
| A | intensity | `src.representation.intensity` | original pair (`difficulty` unset → intensity) | 15 / 8 |
| B | gradient | `src.representation.gradient` | pair copy `difficulty=normal` | 15 / 8 |
| C | structural | `src.representation.structural` | pair copy `difficulty=difficult` | 15 / 8 |

No parameter was changed after seeing a result.

## EXP-003 context

EXP-003 held representation at intensity and changed LROC matching-view scale. Verified inliers stayed at 4 on every arm. This experiment holds that matching-view policy fixed and changes only the existing representation.

## Results

**Status: `completed`. Failed stage: none.** Variant A reproduced the EXP-000 SIFT counts exactly (36 raw → 4 verified, coverage 0.23236). Variants B and C selected gradient and structural while matching-view strides stayed at 15 / 8, so the independent variable was actually applied.

Independent accuracy = **NOT VALIDATED**.

| Variant | Representation | Matching view (OHRC / LROC) | Stride | Raw | Verified | Inlier ratio | Coverage | CPs | Transform | Refinement | Runtime (variant) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | intensity | 5212×800 / 6528×633 | 15 / 8 | 36 | 4 | 11.11% | 0.23236 | 4 | fitted; full raster blocked by cap | INDETERMINATE | 14.58 s (match 5.10 s) |
| B | gradient | 5212×800 / 6528×633 | 15 / 8 | 0 | 0 | n/a | n/a | 0 | not fitted | NO_POINTS | 1.47 s (match 0.99 s) |
| C | structural | 5212×800 / 6528×633 | 15 / 8 | 5 | 4 | 80.00% | 0.30643 | 4 | fitted; full raster blocked by cap | INDETERMINATE | 24.60 s (match 22.96 s) |

Coverage is verified-match bounding-box area fraction. Variant B/C representation was faster because the OHRC `.npy` handle was already warm from Variant A; match times are the comparable figure. Structural match was slower because SIFT ran on a log-gradient image, not because the matching view was larger.

**Primary metric (verified inliers): A = 4, B = 0, C = 4.** Neither B nor C exceeded A. Under the pre-registered decision rule, **H1 is rejected** on this pair. Intensity is not shown to be the correspondence bottleneck: swapping to the existing gradient or structural representations did not increase verified SIFT correspondences.

Raw Lowe-ratio matches **did** change (36 / 0 / 5). Gradient produced no Lowe matches at all, so there was no geometric verification set. Structural stayed on the four-point DLT floor with five raw matches. Do not read fit residuals as registration accuracy. Do not claim a representation is inferior or superior in general from one pair.

## What this does and does not show

Changing the existing representation **does** change the image SIFT sees (`representation_id` intensity vs gradient vs structural; matching-view shapes stayed 5212×800 and 6528×633). On this pair that did **not** increase verified inlier count. Gradient collapsed raw yield to zero. Structural remained at four verified inliers.

This does not validate registration accuracy. It does not test other pairs. It does not retune SIFT or RANSAC. It does not invent a new representation.

## Limitations / confounders

- independent accuracy = NOT VALIDATED. No surveyed lunar control exists.
- Four-point DLT residuals are an algebraic identity.
- Variant A and C produced exactly four verified inliers, the projective DLT minimum, so C's equal verified yield is unfalsifiable as accuracy.
- Raw Lowe-ratio matches changed (36 / 0 / 5), so detector-level correspondence yield is representation-sensitive even though verified count did not increase.
- Gradient produced zero raw matches on this pair; that is a yield collapse, not an accuracy measurement.
- Overlap is not recomputed from the products.
- Full-raster registration remains blocked by the 16,777,216-pixel cap.
- One pair only. No EXP-005 work was started.

## Distinctions this experiment must keep

1. **Raw matches** — after Lowe ratio test, `status == "raw"`.
2. **Verified matches** — RANSAC-style projective software baseline.
3. **Selected control points** — spatial grid on verified inliers.
4. **Refined points** — ZNCC parabolic baseline; zero change is INDETERMINATE.
5. **Fitted transformation** — DLT on selected/refined points.
6. **Registration output** — full raster blocked by the existing cap.
7. **Evaluation** — verification residuals vs independent accuracy (`NOT VALIDATED`).

Projective DLT residuals on **exactly four** control points are the DLT minimum and **must not** be read as registration accuracy.
