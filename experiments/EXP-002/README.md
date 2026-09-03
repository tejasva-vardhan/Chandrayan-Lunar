# EXP-002 — Matching-view scale policy on pair_01_equatorial

Branch: `feature/tejas-exp002-scale-policy` (from latest `main` at `67a4c7c`).

This experiment asks one question: **does using a common physical / GSD-normalised matching scale improve SIFT correspondence yield on pair_01_equatorial?**

It is **not** a matcher freeze (D-007), not a lunar-transform freeze (D-010), and not official SIH evidence (D-011).

## Hypothesis

**H1.** Replacing per-image pixel-budget matching-view strides with a common physical/GSD-normalised matching scale increases the number of geometrically verified SIFT correspondences **beyond the four-point projective DLT minimum**, holding every other EXP-000 stage constant.

**H0.** Common-scale matching views do not move verified yield above that minimum, which would mean residual matching-view scale is not the demonstrated pair-01 correspondence bottleneck.

**Decision rule (fixed before the real-data run).** Variant B counts as improving verified yield only if it produces **strictly more than 4** verified inliers. A count of exactly 4 means RANSAC's consensus set is the minimal sample itself; the near-zero fit residual is an algebraic identity, not evidence.

Do **not** treat four-point DLT residuals as accuracy. Independent accuracy remains **NOT VALIDATED**.

## Pair

Same products as EXP-000 / EXP-001 pair 01:

| Role | Product | Format |
|---|---|---|
| Source | `ch2_ohr_ncp_20210402T0546284043_d_img_d18` | Chandrayaan-2 OHRC PDS4 |
| Reference | `M150368601RC` | LROC NAC CDR PDS3 |
| Manifest id | `pair_01_equatorial` | `data/manifests/demo_pairs.yaml` |

Dataset root: `CHANDRAYAN_DATA_ROOT` (`D:\SIH` when mounted). This session ran from previously ingested raster handles because `D:\SIH` was not mounted: OHRC `data/processed/*.npy` and LROC temp ingestion-cache `.npy`. Array shapes match the EXP-000 ingested products (78175×12000 and 52224×5064). Do not commit raw products.

## Exact run command

```powershell
$env:CHANDRAYAN_DATA_ROOT = "<external demo dataset containing the declared products>"
python scripts/run_exp002.py
```

When the raw products are not mounted, the same pipeline can be started from the already-ingested raster handles via `run_exp002_from_products`.

Lightweight record: `experiments/EXP-002/results/pair_01_equatorial.json`  
Full record: `outputs/EXP-002/` (gitignored)

Exact configuration: [`config.yaml`](config.yaml), authored from `src/io/exp002/config.py`.

## Frozen pipeline (unchanged)

ingest → characterize_pair → preprocess → generate_representation → match → verify_matches → select_control_points → refine_points → register → evaluate

Owning callables are used as-is. Variant A calls frozen `generate_representation(pair)`. Variant B calls `generate_representation_with_settings` with the common-scale settings. Both call frozen `match()`.

EXP-002 does not rewrite verification, control-point selection, refinement, registration, SPICE, frontend, or the 16,777,216-pixel registration cap. Diagnostic rasters are not written.

## What is held constant

Copied from the EXP-000 snapshot (`src/io/exp000/config.py`). Tests assert the fixed block is identical.

| Item | Value |
|---|---|
| Matcher | SIFT (nfeatures=0, nOctaveLayers=3, contrast=0.04, edge=10, sigma=1.6, ratio=0.75, min_matches=4) |
| Matching-view budget | 4,194,304 pixels/image |
| Downsample | `stride_decimation` |
| Coordinate mapping | `x_original = x_matching * stride`, `y_original = y_matching * stride` |
| Representation | difficulty None/easy → intensity (2–98 percentile stretch) |
| Verification | `projective_2d_baseline` + `ransac_style_baseline`, residual_limit=3.0, max_trials=500, rng_seed=0 |
| Control points | grid_bins=8, max_per_cell=1 |
| Refinement | `zncc_parabolic_baseline` (same window/search/ZNCC settings as EXP-000) |
| Registration model | `projective_2d_baseline` |
| Registration cap | 16,777,216 pixels (**not raised**) |
| Preprocess on this pair | identity passthrough (full rasters exceed the cap) |

## Independent variable

| Variant | Scale policy | Stride rule |
|---|---|---|
| A | `per_image_pixel_budget` (EXP-000) | `stride = ceil(sqrt(pixels / 4194304))` independently per image. Expected pair-01 strides: OHRC 15, LROC 8. |
| B | `common_physical_gsd` | `target_gsd = max(gsd_i * pixel_budget_stride_i)`; `stride_i = max(pixel_budget_stride_i, round(target_gsd / gsd_i))`. Still stride-decimation; never exceeds the pixel budget. |

GSD sources, in order:

1. Ingested `LunarProduct.gsd_meters` when present (OHRC pair 01: 0.26 m/px).
2. Experiment-level LROC NAC catalog GSD **0.5 m/px** when ingested GSD is missing. This is not written onto `LunarProduct`, is not SPICE, and is used only because the NAC CDR label has no resolution, altitude, or pointing geometry. Pair-01 LROC is SCIENCE MISSION 2011-01-22 with `CROSSTRACK_SUMMING=1`.

No parameter was changed after seeing a result.

## EXP-001 context

On this pair, matcher choice did not explain the bottleneck (SIFT 36 raw → 4 verified; ORB 69 raw → 4 verified; RIFT 0). EXP-001 named different per-image strides (15 vs 8) as a remaining scale confounder. This experiment holds SIFT constant and isolates that scale policy.

## Results

**Status: `completed`. Failed stage: none.** Variant A reproduced the EXP-000 SIFT counts exactly (36 raw → 4 verified, coverage 0.23236). Variant B selected the **same integer strides** (OHRC 15, LROC 8) and the same correspondences.

Independent accuracy = **NOT VALIDATED**.

| Variant | Matching view (OHRC / LROC) | Stride | Resampling | Effective GSD (m/px) | Raw | Verified | Inlier ratio | Coverage | CPs | Transform | Refinement | Runtime (variant) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 5212×800 / 6528×633 | 15 / 8 | stride_decimation | 3.9 / 4.0 | 36 | 4 | 11.11% | 0.23236 | 4 | fitted; full raster blocked by cap | INDETERMINATE | 16.92 s (match 4.80 s) |
| B | 5212×800 / 6528×633 | 15 / 8 | stride_decimation | 3.9 / 4.0 | 36 | 4 | 11.11% | 0.23236 | 4 | fitted; full raster blocked by cap | INDETERMINATE | 6.35 s (match 4.83 s) |

Coverage is verified-match bounding-box area fraction, identical to EXP-000 control-point coverage on this four-point set. Variant B representation was faster only because the same `.npy` handles were already warm from Variant A; match times are the comparable figure.

OHRC effective GSD = 0.26 m/px ingested × stride 15. LROC effective GSD = 0.5 m/px catalog × stride 8. Integer rounding cannot improve on |3.9 − 4.0| = 0.1 m/px without violating the 4,194,304-pixel budget.

**Primary metric (verified inliers): A = 4, B = 4.** Variant B does not move above the four-inlier DLT minimum. Verified inliers did not improve. **H1 is not supported.**

The four-point DLT fit is unfalsifiable on both arms. Do not read fit residuals as registration accuracy.

## What this does and does not show

The EXP-001 stride gap (15 vs 8) is already the integer GSD-normalised pair for OHRC 0.26 m/px and LROC NAC catalog 0.5 m/px under the existing pixel budget. Common-scale matching views are a no-op on this pair, so residual matching-view scale is **not** a demonstrated additional correspondence bottleneck beyond what EXP-000 already ran.

This does not measure true LROC GSD from SPICE or from the CDR label (none is present). If the actual NAC GSD were far from 0.5 m/px, the common-scale strides would change. It also does not validate registration accuracy.

## Limitations / confounders

- independent accuracy = NOT VALIDATED. No surveyed lunar control exists.
- Four-point DLT residuals are an algebraic identity.
- LROC ingested `gsd_meters` is None. Variant B used the documented mapping-orbit catalog value 0.5 m/px; that value is not written onto `LunarProduct` and is not SPICE-derived.
- Integer GSD-normalised strides matched the per-image pixel-budget strides, so the independent variable did not change the matching views.
- Overlap is not recomputed from the products.
- Full-raster registration remains blocked by the 16,777,216-pixel cap.
- One pair only. No EXP-003 work was started.

## Distinctions this experiment must keep

1. **Raw matches** — after Lowe ratio test, `status == "raw"`.
2. **Verified matches** — RANSAC-style projective software baseline.
3. **Selected control points** — spatial grid on verified inliers.
4. **Refined points** — ZNCC parabolic baseline; zero change is INDETERMINATE.
5. **Fitted transformation** — DLT on selected/refined points.
6. **Registration output** — full raster blocked by the existing cap.
7. **Evaluation** — verification residuals vs independent accuracy (`NOT VALIDATED`).

Projective DLT residuals on **exactly four** control points are the DLT minimum and **must not** be read as registration accuracy.
