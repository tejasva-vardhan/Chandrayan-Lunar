# PS-closing phase 3 — scale + cross-sensor optical robustness

Not EXP-007. Two small adaptations on the frozen coarse-to-fine correspondence path.

## Data / modality scope

Only OHRC and LROC NAC exist in the current demo dataset (`D:\SIH\Main`). TMC and IIRS are **not** available. This experiment is **cross-instrument optical** correspondence, not OHRC/TMC/IIRS multi-modal validation.

Primary pair `pair_02_mid_equatorial` (same overlapping scene as PS-CORRESPONDENCE):

| Role | Product | Instrument | GSD |
|---|---|---|---|
| Source | `ch2_ohr_ncp_20250612T2229094979_d_img_d18` | Chandrayaan-2 OHRC | **0.28 m/px ingested** |
| Reference | `M1504316436RC` | LRO NAC | ingested `gsd_meters=null`; **catalog 0.5 m/px** (Robinson 2010 / LROC SIS; not SPICE) |

Native GSD ratio (source/reference) = **0.56** (~1.8×). This is the real scale gap on the overlapping pair. It is not a synthetic resampling factor and is not a cross-pair comparison.

## Mechanisms

**A (control):** production coarse-to-fine SIFT + intensity + `per_image_pixel_budget` (OHRC stride 16 / LROC stride 8).

**B (scale):** same coarse-to-fine + intensity, but `common_physical_gsd` matching views using ingested OHRC GSD and LROC catalog 0.5 m/px. Observed pair_02 strides **16 / 9**. Effective matching GSD ≈ 4.48 / 4.50 m. Still stride-decimation; no invented scale factor.

**C (cross-sensor):** same coarse-to-fine + pixel-budget strides as A, but `cross_sensor` representation = percentile stretch then OpenCV CLAHE. Tests OHRC calibrated intensity vs LROC Scaled I/F appearance, not hyperspectral fusion.

Downstream verification, RANSAC, transform, spatial diagnostics, and control-point selection are unchanged.

```powershell
$env:CHANDRAYAN_DATA_ROOT = "<external demo dataset containing the declared products>"
python scripts/run_ps_scale_multimodal.py
```

## Results

**Scale: SUPPORTED.** **Cross-sensor optical: SUPPORTED.** Independent accuracy remains **NOT VALIDATED**. Parameters were not retuned.

| Metric | A — production | B — common GSD | C — CLAHE |
|---|---|---|---|
| Representation | intensity | intensity | cross_sensor |
| Scale policy | per_image_pixel_budget | common_physical_gsd | per_image_pixel_budget |
| Strides (OHRC / LROC) | 16 / 8 | 16 / 9 | 16 / 8 |
| Native GSD (m/px) | 0.28 / 0.5 | 0.28 / 0.5 | 0.28 / 0.5 |
| Effective matching GSD (m) | 4.48 / 4.0† | 4.48 / 4.50 | 4.48 / 4.0† |
| Raw matches | 1630 | 1584 | 1532 |
| Verified inliers | 72 | 99 | 55 |
| Inlier ratio | 4.42% | 6.25% | 3.59% |
| Source occupied cells / 64 | 23 | 15 | 21 |
| Reference occupied cells / 64 | 14 | 10 | 17 |
| Verified bbox coverage | 0.407 | 0.220 | 0.631 |
| Max verified / source cell | 11 | 21 | 12 |
| Source concentration | 0.153 | 0.212 | 0.218 |
| Control points | 23 | 25 | 16 |
| Transform | fitted (full raster blocked) | fitted (full raster blocked) | fitted (full raster blocked) |
| Residual RMSE / median / max (px) | 2.081 / 2.080 / 3.000 | 1.973 / 1.845 / 2.984 | 1.770 / 1.481 / 2.950 |
| Held-out RMSE (px) | 2.086 | 2.018 | 1.932 |
| Match runtime | 28.3 s | 30.2 s | 81.9 s |
| Match RSS delta | +40.0 MB | +10.8 MB | −47.9 MB |
| Deterministic repeat | yes | yes | yes |

† LROC ingested GSD is null; 4.0 m = catalog 0.5 m × stride 8, reported for comparison only. A's matching-view policy does not consume that catalog GSD.

Wall time 327 s including ingest. Match-stage tracemalloc peaks ≈ 176–185 MB.

B increased verified inliers (72→99) and aligned effective GSD, but occupancy contracted (23→15 / 14→10) and coverage fell (0.407→0.220). That is still above the pre-registered 50% maintain floor; it is **not** a claim of improved spatial uniformity.

C kept a useful set (55 inliers, occupancy 21 / 17) with **higher** reference occupancy and coverage than A. CLAHE is slower.

## What this does and does not show

Demonstrated: coarse-to-fine remains useful across the real OHRC 0.28 / LROC 0.5 m GSD gap; GSD-normalised strides (16/9) do not collapse the set; CLAHE cross-sensor intensity does not collapse the set under OHRC↔LROC radiometric appearance differences.

Not demonstrated: TMC/IIRS multi-modal registration; general lunar scale invariance; that resampling proves scale invariance; independent accuracy. Matcher-derived held-out RMSE is not ground truth.
