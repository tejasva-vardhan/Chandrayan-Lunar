# EXP-000 — SIFT sanity baseline on real lunar pair 01

Branch: `feature/tejas-exp000-integration` (from `main` at PR #13 / `18dbc50`).

This is a **software baseline**, not official SIH evidence (D-011), not a matcher freeze (D-007), and not a selected lunar transform (D-010).

## Pair

| Role | Product | Format |
|---|---|---|
| Source | `ch2_ohr_ncp_20210402T0546284043_d_img_d18` | Chandrayaan-2 OHRC PDS4 |
| Reference | `M150368601RC` | LROC NAC CDR PDS3 |
| Manifest id | `pair_01_equatorial` | `data/manifests/demo_pairs.yaml` |
| Footprint provenance | NASA PDS ODE | as declared in the demo manifest; ingest does not recompute footprints |

Dataset root: `CHANDRAYAN_DATA_ROOT` (external demo dataset; not in Git).

## Exact run command

```powershell
$env:CHANDRAYAN_DATA_ROOT = "<external demo dataset containing both products>"
python scripts/run_exp000.py
```

Optional:

```powershell
python scripts/run_exp000.py --data-root "<external demo dataset>" --output-dir outputs/EXP-000/pair_01_equatorial --record-path experiments/EXP-000/results/pair_01_equatorial.json
```

Point `CHANDRAYAN_DATA_ROOT` at the external folder that contains **both** pair-01 products. Do not commit raw products or machine-specific paths.

Lightweight record: `experiments/EXP-000/results/pair_01_equatorial.json`  
Diagnostic rasters: `outputs/EXP-000/pair_01_equatorial/` (gitignored; do not commit)

Exact configuration: [`config.yaml`](config.yaml)

## Frozen pipeline (unchanged)

ingest → characterize_pair → preprocess → generate_representation → match → verify_matches → select_control_points → refine_points → register → evaluate → export_result

Owning callables are used as-is. EXP-000 does not rewrite matchers, verification, RIFT, LoFTR, SPICE, or the 16,777,216-pixel registration cap.

## Exact software configuration

Copied from owning-module unvalidated defaults (not SIH thresholds):

| Item | Value |
|---|---|
| Matching-view budget | 4,194,304 pixels/image |
| Downsample | `stride_decimation`, `stride = ceil(sqrt(pixels / 4194304))` |
| Coordinate mapping | `x_original = x_matching * stride`, `y_original = y_matching * stride` |
| Representation routing | difficulty None/easy → intensity (2–98 percentile stretch) |
| SIFT | nfeatures=0, nOctaveLayers=3, contrast=0.04, edge=10, sigma=1.6, ratio=0.75, min_matches=4 |
| Verification | `projective_2d_baseline` + `ransac_style_baseline`, residual_limit=3.0, max_trials=500, rng_seed=0 |
| Control points | grid_bins=8, max_per_cell=1 |
| Refinement | `zncc_parabolic_baseline`, window_radius=7, search=3, min_valid=0.75, min_peak_zncc=0.25, fine 1.0/0.1 |
| Registration model | `projective_2d_baseline` |
| Registration cap | 16,777,216 pixels (**not raised**) |
| Diagnostic crop | bounded window, preferred_side=2048, grows to remaining cap; placement maximises control-point inclusion (not global centroid) |
| Preprocess on pair 01 | identity passthrough (full-raster float64 materialisation exceeds the same cap); matching-view stretch still runs |
| Independent ground truth | none |

LROC invalid-pixel mask is stride-decimated with the matching view and passed to SIFT.

## Distinctions this experiment must keep

1. **Raw SIFT matches** — `Correspondence.status == "raw"` after Lowe ratio test.
2. **Verified matches** — RANSAC-style projective software baseline; inliers vs rejected.
3. **Selected control points** — spatial grid on verified inliers.
4. **Refined points** — ZNCC parabolic baseline; failure preserves original coordinates.
5. **Fitted transformation** — `projective_2d_baseline` DLT on selected/refined points.
6. **Registration output** — full raster blocked by the existing 16,777,216-pixel cap; diagnostic crop only.
7. **Evaluation metrics** — verification residuals vs independent accuracy (none).

Projective DLT residuals on **exactly four** control points are the DLT minimum and **must not** be read as registration accuracy.

`evaluate().rmse` is RMSE of **stored verification inlier residuals**, not independent accuracy.

## Previously observed downstream baseline (Shaiz)

These numbers are a **prior** matching/verification observation. They were not copied into the current record. The current run recomputed every stage from the products found under `CHANDRAYAN_DATA_ROOT`. Because the frozen pipeline is deterministic (`rng_seed=0`, fixed SIFT settings, fixed matching-view policy), an independent re-run on the same pair can reproduce the same counts:

- 36 raw SIFT correspondences
- 4 verified inliers
- 11.11% inlier ratio
- 4 control points
- coverage ≈ 0.23236
- projective DLT residuals ≈ 1e-11 to 1e-9 pixels on the four fit points

## Results from the finalized real pair-01 execution

**Status: `completed`. Failed stage: none.** Real pair-01 execution finished on the products found under `CHANDRAYAN_DATA_ROOT`. Baseline matcher: **SIFT** (software sanity baseline, not an optimality claim).

Command: `$env:CHANDRAYAN_DATA_ROOT = "<external dataset root>"; python scripts/run_exp000.py`

Lightweight record: `experiments/EXP-000/results/pair_01_equatorial.json` (written by this run).

| Stage | Result |
|---|---|
| Discovery | Both products found by existing recursive `find_product` (no discovery-code change) |
| Ingest OHRC | 78175×12000 `uint8`, GSD 0.26 m/px, calibrated, Selenographic bbox from the PDS4 label |
| Ingest LROC | 52224×5064 16-bit LSB integer, null −32768, valid ratio 0.9873617693522907 |
| Characterize | `OHRC/LRO_NAC`; GSD ratio / sun / overlap / pair valid-pixel ratio remain `None` (not invented) |
| Preprocess | identity passthrough (full rasters exceed the 16,777,216-pixel cap) |
| Matching view | OHRC stride 15 → 5212×800; LROC stride 8 → 6528×633; LROC invalid mask respected |
| SIFT | 36 raw correspondences |
| Verify | 4 inliers / 32 rejected; inlier ratio 0.1111111111111111 |
| Control points | 4; spatial coverage 0.2323628740965652 |
| Refinement | 0 of 4 coordinates changed → **indeterminate** (no per-point outcome field) |
| Register | `registration_output_too_large`; transform `projective_2d_baseline` fitted |
| Diagnostic crop | 3313×5064 at row=44867, col=0 (16,777,032 px ≤ cap); **2 of 4** control points inside (maximum that fit); finite pixel fraction ≈ 0.753 |
| Evaluate | RMSE 4.40e-10 of **stored verification inlier residuals**, not independent accuracy |
| Export | lightweight JSON package; `registered_source` is null |
| Runtime | ≈ 93.4 s total (ingest ≈ 46.3 s) |

Do **not** read the four-point DLT residuals or `evaluate().rmse` as registration accuracy. There is no independent ground truth and no held-out correspondence set.

The diagnostic crop is bounded engineering output for inspecting selected control-point alignment. The four control points span ~19,505 LROC rows, which exceeds the 3,313-row cap-limited window, so all four cannot appear in one crop. The window contains the two-point cluster that fits (indices 0 and 2). This is not a complete registered product.

This experiment is a SIFT software-baseline sanity check on real pair 01. It is not a claim that SIFT is optimal and is not SIH performance evidence.

## Recommended EXP-001

Compare illumination-robust matchers (RIFT/RIFT2 and one dense/learned candidate) on the **same pair and matching-view policy**, with an independent held-out correspondence set. Do not treat EXP-000 inlier ratio or four-point DLT residuals as the benchmark.
