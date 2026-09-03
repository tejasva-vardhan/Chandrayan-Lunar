# EXP-006 — Correspondence quality and spatial distribution

Branch: `feature/tejas-exp006-correspondence-quality` (from latest `main`, including merged EXP-001 through EXP-005).

This experiment asks one question: **can a single correspondence-generation protocol change, applied to the existing SIFT detector/descriptor, produce more reliable and spatially distributed verified correspondences than the EXP-001 one-way SIFT baseline?**

It is **not** a new matcher. It is **not** a matcher freeze (D-007), a lunar-transform freeze (D-010), or official SIH evidence (D-011). It does not rewrite the pipeline, change frozen contracts, add SPICE, or treat synthetic data as lunar accuracy.

## Why this intervention

EXP-001–005 showed that matcher identity, matching-view scale policy, intensity/gradient/structural representations, and existing ZNCC subpixel refinement are not the remaining bottleneck. On `pair_02_mid_equatorial` the EXP-001 SIFT control already exceeds the four-point floor:

- 919 raw matches
- 25 verified inliers (2.72% inlier ratio)
- 11 / 64 source cells and 9 / 64 reference cells occupied
- 11 control points, transform fitted

The SIH26166 objective is correspondence **quality** with **uniformly distributed** match points. The current one-way SIFT path (`BFMatcher` knn, `crossCheck=False`, Lowe ratio 0.75) accepts every source→reference ratio survivor. That floods geometric verification with outliers (894 / 919 rejected). A 2.72% inlier rate is a correspondence-generation problem, not a “try another detector” problem.

**Variant B therefore adds one protocol: reciprocal nearest-neighbour validation.** A Lowe-ratio match is kept only if the same keypoint pair is also a Lowe-ratio match in the reverse direction. Detector, descriptor, Lowe threshold, matching view, representation, RANSAC, and control-point selection stay fixed.

This is the smallest high-value change that is already justified by the research specification (geometric verification is preceded by correspondence validation; SIFT/ASIFT remains the baseline family) and by standard photogrammetric practice (mutual nearest neighbours). It is not a portfolio of algorithms.

Predicted mechanism, fixed before the run:

1. Reciprocal agreement removes one-way accidental matches.
2. The candidate set fed to RANSAC has a higher inlier fraction.
3. A less outlier-dominated consensus can corroborate more verified inliers and can span more of the usable overlap rather than a local cluster.
4. Occupied 8×8 cells are measured, not forced. Spatial caps are not applied at match time, because forcing occupancy would confound quality with a second mechanism.

If B only thins the same crater cluster, or raises raw count without verified-quality and spatial gains, H1 is **NOT SUPPORTED** and parameters are not retuned.

## Hypothesis

**H1.** On `pair_02_mid_equatorial`, adding reciprocal (mutual nearest-neighbour) validation to the EXP-001 SIFT baseline, holding detector, descriptor, Lowe ratio, matching view, representation, and geometric verification fixed, produces a meaningful improvement in verified correspondence quality while maintaining or improving spatial distribution of those verified correspondences.

**H0.** Reciprocal validation does not improve verified quality, or any quality gain comes with worse spatial distribution or an unstable transform.

## Decision rule (fixed before the real-data run)

The independent variable is valid only if variant A is the frozen `match()` one-way SIFT + Lowe-ratio path and variant B is the same SIFT detector/descriptor/Lowe-ratio with reciprocal nearest-neighbour validation, on the same `RepresentationResult`.

B is **SUPPORTED** only if all of the following hold:

1. Verified inliers strictly increase.
2. Inlier ratio does not decrease.
3. Source and reference 8×8 occupied-cell counts are each ≥ A's (spatial distribution maintained or improved).
4. Both variants fit a transform from more than the projective DLT minimum of 4 verified inliers.
5. B match-stage runtime is at most 5× A's.

**Raw match count alone is not success.** Occupied-cell count is the spatial gate. Bounding-box coverage and Clark–Evans *R* are reported but not gated. Matcher-derived held-out RMSE is reported and is **not** accuracy. Independent accuracy remains **NOT VALIDATED**.

Missing critical measurements → **INDETERMINATE**. If the hypothesis fails → **NOT SUPPORTED**. Do not retune until it passes.

## Pair

Primary pair (same products as the EXP-001 SIFT arm that produced 25 verified inliers):

| Role | Product | Format |
|---|---|---|
| Source | `ch2_ohr_ncp_20250612T2229094979_d_img_d18` | Chandrayaan-2 OHRC PDS4 |
| Reference | `M1504316436RC` | LROC NAC CDR PDS3 |
| Manifest id | `pair_02_mid_equatorial` | `data/manifests/demo_pairs.yaml` |

Follow-up, only if the primary decision is **SUPPORTED** and runtime stays reasonable:

| Manifest id | Role |
|---|---|
| `pair_01_equatorial` | Hard EXP-000 / EXP-001 control pair (4 SIFT inliers). Same A/B, no retuning. |

Dataset root: `CHANDRAYAN_DATA_ROOT`. Do not commit raw products.

```powershell
$env:CHANDRAYAN_DATA_ROOT = "<external demo dataset containing the declared products>"
python scripts/run_exp006.py
```

Optional:

```powershell
python scripts/run_exp006.py --data-root "<external demo dataset>" --pairs pair_02_mid_equatorial --no-follow-up
```

Lightweight records: `experiments/EXP-006/results/`
Full records: `outputs/EXP-006/` (gitignored)

Exact configuration: [`config.yaml`](config.yaml), authored from `src/io/exp006/config.py`.

## Frozen pipeline (unchanged)

ingest → characterize_pair → preprocess → **generate_representation [shared]** → **match [A vs B]** → verify_matches → select_control_points → refine_points → register → evaluate

`generate_representation` is called once per pair. Variant A calls frozen `match()`. Variant B calls `run_sift(..., require_reciprocal=True)` on the same representation object. `SiftSettings` is unchanged; `require_reciprocal` is a keyword-only adapter flag that `match()` never sets.

EXP-006 does not rewrite verification, control-point selection, refinement, registration, SPICE, frontend, or the 16,777,216-pixel registration cap. Diagnostic rasters are not written. Frozen `CorrespondenceSet` / `RegistrationResult` contracts are not extended; spatial diagnostics live in EXP-006 result records.

## What is held constant

Copied from the EXP-000 snapshot (`src/io/exp000/config.py`). Tests assert the fixed block matches.

| Item | Value |
|---|---|
| Matcher / detector / descriptor | SIFT (nfeatures=0, nOctaveLayers=3, contrast=0.04, edge=10, sigma=1.6) |
| Lowe ratio | 0.75 |
| min_matches | 4 |
| Matching view | EXP-000 pixel-budget stride (pair_02: OHRC 16, LROC 8) |
| Matching-view budget | 4,194,304 pixels/image |
| Downsample | `stride_decimation` of the source raster |
| Coordinate mapping | `x_original = x_matching * stride`, `y_original = y_matching * stride` |
| Representation | difficulty None/easy → intensity (2–98 percentile stretch) |
| Verification | `projective_2d_baseline` + `ransac_style_baseline`, residual_limit=3.0, max_trials=500, rng_seed=0 |
| Control points | grid_bins=8, max_per_cell=1 |
| Refinement | `zncc_parabolic_baseline` |
| Registration model | `projective_2d_baseline` |
| Registration cap | 16,777,216 pixels (**not raised**) |
| Preprocess on these pairs | identity passthrough (full rasters exceed the cap) |

## Independent variable

| Variant | Protocol | Callable | Role |
|---|---|---|---|
| A | `sift_lowe_ratio_one_way` | `match(pair, representation)` | EXP-001 SIFT control |
| B | `sift_lowe_ratio_reciprocal_nn` | `run_sift(..., require_reciprocal=True)` | reciprocal NN + same Lowe ratio |

No parameter was chosen after seeing a real-data result.

## Primary measurements

1. Raw candidate matches
2. Verified inliers
3. Inlier ratio (`inlier_count / len(matches)`)
4. Number of 8×8 grid cells containing verified matches (source and reference)
5. Spatial coverage (verified-match bounding-box area fraction)
6. Maximum verified matches per cell
7. Clark–Evans *R* on full-image area (engineering diagnostic; *R*<1 clustered)
8. Transformation fitted / not fitted
9. Transformation residual distribution (stored verification-inlier residuals)
10. Matcher runtime
11. Memory / process RSS

## Secondary measurements

- Control-point count
- Unselected-checkpoint RMSE and k-fold RMSE (matcher-derived; **not** accuracy)
- Occupied-cell span (multiple rows and columns as an overlap-span proxy)
- Repeat-match determinism (two match calls, same coordinates)

## Spatial analysis

Uses the existing EXP-001 8×8 occupancy rule: cells are defined on **full product dimensions**, not the points' bounding box, so a tight cluster cannot be rescaled into “full coverage”.

Report for each variant:

- occupied cells / 64 (source and reference)
- coverage
- matches per cell (`cell_counts_row_major`)
- concentration = max(cell count) / n
- whether occupied cells span more than one row **and** more than one column

A result with more matches in the same crater is not treated as better.

## Results

**Status: `completed`. Failed stage: none. Decision: `NOT SUPPORTED`.**

Live run at git working tree on branch `feature/tejas-exp006-correspondence-quality`, platform Windows-11-10.0.26200. Follow-up on `pair_01_equatorial` was **not** run because the primary decision was not SUPPORTED.

Independent accuracy = **NOT VALIDATED**. Parameters were **not** retuned after seeing the result.

Variant A reproduced the EXP-001 SIFT control on this pair exactly: 919 raw → 25 verified, coverage 0.50844, source occupancy 11/64, reference occupancy 9/64, held-out RMSE 1.904 px.

### A vs B table (live measurements, pair_02_mid_equatorial)

| Metric | A — one-way SIFT | B — reciprocal NN |
|---|---|---|
| Protocol | `sift_lowe_ratio_one_way` | `sift_lowe_ratio_reciprocal_nn` |
| Raw matches | **919** | **788** |
| Verified inliers | **25** | **25** |
| Inlier ratio | 2.72% | 3.17% |
| Source occupied cells / 64 | **11** (17.2%) | **10** (15.6%) |
| Reference occupied cells / 64 | **9** (14.1%) | **10** (15.6%) |
| Max verified matches / source cell | 7 | 9 |
| Source concentration (max/n) | 0.28 | 0.36 |
| Source Clark–Evans *R* | 0.506 | 0.347 |
| Reference Clark–Evans *R* | 0.366 | 0.248 |
| Verified-match bbox coverage | 0.508 | 0.189 |
| Occupied source rows × cols | 4 × 7 | 3 × 8 |
| Spans multiple rows and cols | yes | yes |
| Control points | 11 | 15 |
| Transform | fitted (full raster blocked) | fitted (full raster blocked) |
| Inlier residual RMSE / median / max | 1.686 / 1.687 / 2.654 px | 1.742 / 1.347 / 2.863 px |
| K-fold held-out RMSE (25 pts) | 1.904 px | 2.212 px |
| Unselected-checkpoint RMSE | 2.221 px (14 pts) | 1.959 px (10 pts) |
| Match runtime | 4.344 s | 3.915 s |
| Variant runtime | 8.574 s | 9.130 s |
| Match RSS delta | +49.4 MB | +2.9 MB |
| Repeat-match deterministic | yes (919=919) | yes (788=788) |

`Fit` / verification residuals are **not** accuracy. Held-out RMSE is matcher-derived and **not** independent accuracy.

Total wall time 67.1 s. Peak process RSS after the run ~95 MB. Reciprocal matching did not explode runtime or memory; B's first match call was within 5× of A (actually slightly faster). RSS deltas are allocator-noisy, as in EXP-001.

### Did B improve verified correspondence quality?

**No.** Verified inliers stayed at 25. Reciprocal filtering removed 131 raw matches (919 → 788) and raised inlier ratio from 2.72% to 3.17%, but the decision rule requires a **strict increase in verified inliers**. Ratio improvement without more corroborated inliers is not treated as success. RANSAC still found a 25-point consensus.

### Did B improve spatial distribution?

**No.** Source occupied cells fell 11 → 10. Reference occupied cells rose 9 → 10, but the gate requires **both** sides to be ≥ A. Coverage collapsed 0.508 → 0.189. Clark–Evans *R* fell on both images (more clustered). Max matches per source cell rose 7 → 9 (concentration 0.28 → 0.36). Occupied source rows fell 4 → 3.

Control-point count rose 11 → 15. That is **not** better spatial distribution of verified matches. Control-point selection tiles the *correspondence bounding box*, so a tighter cluster is rescaled onto the 8×8 selection grid and can yield more selected points. Full-image occupancy is the SIH-relevant spatial measurement here, and it did not improve.

### Did the transformation remain stable?

**Yes.** Both variants fitted a projective transform from 25 verified inliers (21 above the four-point floor). Full-raster warp remained blocked by the 16,777,216-pixel cap. B's k-fold held-out RMSE was worse (2.212 vs 1.904 px); that is reported, not gated, and is still not accuracy.

### Decision

**NOT SUPPORTED.**

Independent variable applied: yes (frozen `match()` vs `run_sift(..., require_reciprocal=True)` on the same representation, strides OHRC 16 / LROC 8).

Failed gates: verified inliers did not increase (25 ≤ 25); source occupied cells decreased (11 → 10).

Transform remained stable. Runtime was acceptable. No follow-up pair was run.

## Limitations

1. Independent accuracy is **NOT VALIDATED**. No surveyed lunar control exists.
2. Matcher-derived held-out points are not ground truth.
3. Reciprocal nearest-neighbour agreement is not accuracy.
4. Occupied-cell ratio and Clark–Evans *R* are experiment diagnostics, not a frozen SIH uniformity score. Clark–Evans uses full-image area with no edge correction.
5. Overlap is not recomputed from the products. The manifest declares `overlap_status=verified` from NASA PDS ODE footprints.
6. Stride decimation remains aggressive (OHRC 16, LROC 8). Reciprocal matching cannot recover texture discarded before matching.
7. One pair. The 25-inlier set is large enough to measure change, not large enough to generalise.
8. Control-point count uses a bbox-relative grid and must not be read as full-image uniformity.
9. Full-raster registration remains blocked by the existing 16,777,216-pixel cap.
10. Parameters were not retuned after the negative result.

## Distinctions this experiment must keep

1. **Raw matches** — after Lowe ratio, and after reciprocal NN for B; `status == "raw"`.
2. **Verified matches** — RANSAC-style projective software baseline.
3. **Selected control points** — spatial grid on verified inliers.
4. **Refined points** — ZNCC parabolic baseline; held constant, not the independent variable.
5. **Fitted transformation** — DLT on selected / refined points.
6. **Registration output** — full raster blocked by the existing cap.
7. **Evaluation** — verification residuals vs independent accuracy (`NOT VALIDATED`).

Projective DLT residuals are a fit diagnostic. Reciprocal agreement is not accuracy. Occupied-cell count is not proof of uniform overlap coverage. Held-out RMSE from matcher-derived points is not independent accuracy.

## Next correspondence core (PS-closing phase 1)

EXP-006 does **not** continue into EXP-007. Reciprocal SIFT was NOT SUPPORTED. The remaining correspondence bottleneck named here is still **single matching-view stride**: pair_02 OHRC 16 / LROC 8 discards texture before SIFT runs, and one-way vs reciprocal protocol changes cannot recover it.

**Selected mechanism (one path):** coarse-to-fine tiled multi-scale SIFT.

1. Coarse: frozen EXP-001 matching view + one-way SIFT (control A).
2. Fit the existing projective RANSAC baseline on those coarse matches to get a search prior. This is candidate generation, not a change to downstream verification.
3. Tile the expanded coarse-inlier bbox and rematch SIFT at half the coarse stride (`fine_stride_factor=0.5`) on corresponding windows.
4. Union coarse matches with new fine matches (coarse set is never dropped). Downstream `verify_matches` is unchanged.

**Why this, not the obvious alternatives**

| Option | Why not |
|---|---|
| Another SIFT / Lowe / reciprocal tweak | Already rejected by EXP-001 and EXP-006 |
| Matcher swap (ORB/RIFT) | EXP-001: pair variation >> matcher variation |
| ASIFT affine warps on the same coarse view | Costly; does not restore discarded fine pixels |
| LightGlue / LoFTR | Heavyweight learned stack; blocked in EXP-001 |
| Full-image finer stride | Exceeds the 4,194,304-pixel matching-view budget |

**Expected cost:** 1 coarse SIFT + ≤4 fine tiles, each ≤ the existing pixel budget. Match runtime target ≤ 12× control A.

**Hypothesis:** searching/matching at multiple spatial scales and then verifying candidates geometrically recovers more reliable and spatially distributed correspondences than the single matching-view SIFT baseline.

Implementation and A/B record: `src/matching/coarse_to_fine.py`, `experiments/PS-CORRESPONDENCE/`.
