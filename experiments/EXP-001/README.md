# EXP-001 — Controlled matcher comparison on real OHRC ↔ LROC pairs

Branch: `feature/tejas-exp001-matcher-comparison` (from latest `main` at `779caec`).

This experiment asks one question: **does matcher choice materially increase geometrically verified correspondence yield** for Chandrayaan-2 OHRC ↔ LROC imagery, holding the EXP-000 pipeline constant?

It is **not** a matcher freeze (D-007), not a lunar-transform freeze (D-010), and not official SIH evidence (D-011).

## Hypothesis

**H1.** Replacing the SIFT baseline with an illumination/appearance-robust matcher increases the number of geometrically verified correspondences **beyond the four-point projective DLT minimum**, holding matching-view policy, preprocessing, coordinate mapping, geometric model, residual threshold, RANSAC budget, random seed, control-point policy, and evaluation procedure constant.

**H0.** Matcher choice does not move verified yield above that minimum, which would mean the correspondence bottleneck lies elsewhere.

**Decision rule (fixed before the real-data run).** A matcher counts as improving verified yield only if it produces **strictly more than 4** verified inliers. A count of exactly 4 means RANSAC's consensus set is the minimal sample itself; the near-zero fit residual is an algebraic identity, not evidence.

## Pairs

| Pair | OHRC | LROC | Role |
|---|---|---|---|
| `pair_01_equatorial` | `ch2_ohr_ncp_20210402T0546284043_d_img_d18` | `M150368601RC` | Primary. Same products as EXP-000. |
| `pair_02_mid_equatorial` | `ch2_ohr_ncp_20250612T2229094979_d_img_d18` | `M1504316436RC` | Generalisation only |
| `pair_03_south_mid` | `ch2_ohr_ncp_20230302T1959055531_d_img_n18` | `M106979273RC` | Generalisation only |
| `pair_04_south_pole` | `ch2_ohr_ncp_20260103T1005176450_d_img_d18` | `M175153469LC` | Generalisation only |

Manifest: `data/manifests/demo_pairs.yaml`. Dataset root: `CHANDRAYAN_DATA_ROOT`. Do not commit raw products.

Additional pairs were run only after the implementation was stable on pair 01. They were **not** used to choose or retune matcher parameters.

## Exact run command

```powershell
$env:CHANDRAYAN_DATA_ROOT = "<external demo dataset containing the declared products>"
python scripts/run_exp001.py --pairs pair_01_equatorial pair_02_mid_equatorial pair_03_south_mid pair_04_south_pole
```

Optional:

```powershell
python scripts/run_exp001.py --data-root "<external demo dataset>" --pairs pair_01_equatorial --output-dir outputs/EXP-001 --record-dir experiments/EXP-001/results
```

Lightweight records: `experiments/EXP-001/results/`  
Full records: `outputs/EXP-001/` (gitignored)

Exact configuration: [`config.yaml`](config.yaml), authored from `src/io/exp001/config.py`.

## Frozen pipeline (unchanged)

ingest → characterize_pair → preprocess → generate_representation → match → verify_matches → select_control_points → refine_points → register → evaluate

Owning callables are used as-is. The frozen `match()` surface still routes to SIFT. EXP-001 calls `src.matching.portfolio.run_matcher` so the matcher can be chosen without rewriting routing. `generate_representation` is called **once per pair**; the same `RepresentationResult` object is handed to every matcher.

EXP-001 does not rewrite verification, control-point selection, refinement, registration, SPICE, frontend, or the 16,777,216-pixel registration cap. Diagnostic rasters are not written; the comparison does not need pictures.

## What is held constant

Copied from the EXP-000 snapshot (`src/io/exp000/config.py`). Tests assert the fixed block is identical.

| Item | Value |
|---|---|
| Matching-view budget | 4,194,304 pixels/image |
| Downsample | `stride_decimation`, `stride = ceil(sqrt(pixels / 4194304))` |
| Coordinate mapping | `x_original = x_matching * stride`, `y_original = y_matching * stride` |
| Representation | difficulty None/easy → intensity (2–98 percentile stretch) |
| Verification | `projective_2d_baseline` + `ransac_style_baseline`, residual_limit=3.0, max_trials=500, rng_seed=0 |
| Control points | grid_bins=8, max_per_cell=1 |
| Refinement | `zncc_parabolic_baseline` (same window/search/ZNCC settings as EXP-000) |
| Registration model | `projective_2d_baseline` |
| Registration cap | 16,777,216 pixels (**not raised**) |
| Protocol parameters | Lowe ratio=0.75, min_matches=4, every adapter |
| Preprocess on these pairs | identity passthrough (full rasters exceed the cap) |

On pair 01 the shared matching view is the EXP-000 view: OHRC stride 15 → 5212×800; LROC stride 8 → 6528×633.

## Matcher-specific parameters (fixed before the first real-data run)

| Matcher | Native parameters | Notes |
|---|---|---|
| SIFT | nfeatures=0, nOctaveLayers=3, contrast=0.04, edge=10, sigma=1.6 | EXP-000 baseline. Same adapter path. |
| RIFT | log-Gabor 4×6, FAST threshold 10, max_keypoints=20000, patch=96, grid=6 | In-repository over numpy+scipy. No new dependency. Not scale invariant. |
| ORB | nfeatures=20000, scaleFactor=1.2, nlevels=8, edge=31, WTA_K=2, patch=31, FAST=20 | OpenCV default except the feature cap, raised for parity with unlimited SIFT. |

No parameter was changed after seeing a result. Poor matches were not discarded by hand.

## Candidates considered and not run

| Candidate | Status | Reason |
|---|---|---|
| RIFT/RIFT2 via PyPI | no reliable package; implemented in-repo instead | PyPI `rift` is LIGO software; `rift2` does not exist |
| LoFTR / LightGlue | **blocked; not run, not simulated** | Network-downloaded unpinned weights; designed for ~640 px inputs, so would require a different matching-view stride; torch+kornia is a multi-GB addition to a four-package dependency set |
| AKAZE / KAZE / BRISK | unavailable | absent from opencv-python-headless 5.0.0.93 |

## Independent validation

EXP-000 had no independent ground truth. This experiment adds the only honest split the data supports:

1. **K-fold held-out transfer error** on verified correspondences when there are at least 5 (model minimum + 1). Fit on the complement of each fold; score the withheld fold.
2. **Cross-matcher checkpoints**: one matcher's fitted transform scored on another matcher's verified points.

Both are still matcher-derived. They are **not** independent accuracy.

**independent accuracy = NOT VALIDATED** on every arm, every pair, including pair 02 where held-out RMSE could be computed.

Do not read verification residuals, four-point DLT fit residuals, or held-out transfer error as registration accuracy.

### Held-out k-fold transfer error

Possible only where verified count ≥ 5, which is why ten of twelve arms report `NOT_POSSIBLE_INSUFFICIENT_VERIFIED_CORRESPONDENCES`.

| Pair | Matcher | Held-out points | RMSE | Median | Max |
|---|---|---|---|---|---|
| pair_02_mid_equatorial | SIFT | 25 | 1.904 px | 1.860 px | 3.098 px |
| pair_02_mid_equatorial | ORB | 24 | 2.222 px | 2.004 px | 3.966 px |

### Cross-matcher checkpoints

Each fitted transform scored against correspondences a *different* matcher found and verified. These checkpoints come from an independent detector and descriptor, so they sit outside the consensus set that produced the transform.

| Pair | Transform from | Checkpoints | RMSE | Median |
|---|---|---|---|---|
| pair_01_equatorial | SIFT | 4 (ORB) | **35,694.96 px** | 34,577 px |
| pair_02_mid_equatorial | SIFT | 24 (ORB) | 62.95 px | 60.50 px |
| pair_02_mid_equatorial | ORB | 25 (SIFT) | 61.32 px | 58.74 px |
| pair_04_south_pole | SIFT | 4 (ORB) | **60,414.88 px** | 58,986 px |
| pair_04_south_pole | ORB | 4 (SIFT) | **20,782.68 px** | 20,062 px |

**This is the most important measurement in the experiment.** On pair 01 both SIFT and ORB reported verification residuals of order 1e-10 px, yet their two transforms disagree by **35,695 pixels**. Two "perfect" four-point fits of the same scene are mutually inconsistent by tens of thousands of pixels. The near-zero residual EXP-000 reported carries no information about correctness.

Even where the pipeline genuinely works, the gap is instructive: on pair 02 within-matcher held-out error is ~2 px while cross-matcher error is ~62 px. The more independent the checkpoint, the worse the error looks — and neither number is accuracy.

## Comparison table

Matcher | Pair | Raw | Verified | Inlier Ratio | Coverage | CPs | Transform | Refinement | Runtime (match) | Validation
---|---|---|---|---|---|---|---|---|---|---
SIFT (EXP-000 reference) | pair_01_equatorial | 36 | 4 | 11.11% | 0.23236 | 4 | fitted | INDETERMINATE | 4.52 s | NOT VALIDATED
SIFT | pair_01_equatorial | 36 | 4 | 11.11% | 0.23236 | 4 | fitted | INDETERMINATE | 4.39 s | NOT_POSSIBLE (4 inliers)
RIFT | pair_01_equatorial | 0 | 0 | — | — | 0 | no | NO_POINTS | 41.58 s | NOT_POSSIBLE
ORB | pair_01_equatorial | 69 | 4 | 5.80% | 0.25568 | 3 | no (3 CPs) | INDETERMINATE | 1.21 s | NOT_POSSIBLE (4 inliers)
SIFT | pair_02_mid_equatorial | 919 | 25 | 2.72% | 0.50844 | 11 | fitted | COORDINATES_UPDATED | 2.91 s | held-out RMSE 1.90 px (NOT VALIDATED)
RIFT | pair_02_mid_equatorial | 0 | 0 | — | — | 0 | no | NO_POINTS | 35.81 s | NOT_POSSIBLE
ORB | pair_02_mid_equatorial | 945 | 24 | 2.54% | 0.28108 | 17 | fitted | COORDINATES_UPDATED | 1.14 s | held-out RMSE 2.22 px (NOT VALIDATED)
SIFT | pair_03_south_mid | 26 | 0 | 0% | — | 0 | no | NO_POINTS | 2.57 s | NOT_POSSIBLE
RIFT | pair_03_south_mid | 0 | 0 | — | — | 0 | no | NO_POINTS | 35.99 s | NOT_POSSIBLE
ORB | pair_03_south_mid | 32 | 4 | 12.50% | 0.23282 | 4 | fitted | COORDINATES_UPDATED | 1.06 s | NOT_POSSIBLE (4 inliers)
SIFT | pair_04_south_pole | 13 | 4 | 30.77% | 0.21176 | 4 | fitted | COORDINATES_UPDATED | 2.60 s | NOT_POSSIBLE (4 inliers)
RIFT | pair_04_south_pole | 0 | 0 | — | — | 0 | no | NO_POINTS | 34.34 s | NOT_POSSIBLE
ORB | pair_04_south_pole | 14 | 4 | 28.57% | 0.26815 | 4 | fitted | COORDINATES_UPDATED | 1.12 s | NOT_POSSIBLE (4 inliers)

Coverage is verified-match bounding-box area fraction, not control-point coverage. Full-raster registration remained blocked by the existing 16,777,216-pixel cap whenever a transform was fitted.

**Memory.** Match-stage process RSS delta was −1.9 to +8.5 MB for SIFT and ORB and −3.5 to +15.6 MB for RIFT; peak process RSS was 117–253 MB per pair. RSS is the primary figure because `tracemalloc` sees only Python allocations and would systematically understate OpenCV's C++ work relative to RIFT's numpy work. The deltas are allocator-noisy and occasionally negative, so they bound the matchers' working set rather than measuring it precisely. No matcher was close to a memory limit; memory is not the constraint here.

**Inlier ratio ranks these pairs backwards and should not be read as a quality score.** SIFT on pair 04 has the highest ratio in the table (30.77%) and is worthless — 4 inliers at the algebraic minimum. SIFT on pair 02 has the *lowest* (2.72%) and is the only arm that produced real corroborated correspondence. A high ratio here means a small denominator, not a good match. The count above the model minimum is the meaningful quantity.

**Near-zero residuals are themselves a degeneracy signal.** Every minimal-sample arm shows verified-inlier residuals of 1e-13 to 1e-10 px. The two genuine arms on pair 02 show 0.30–2.73 px. An all-but-zero residual set is the signature of an unfalsifiable fit and is cheap to detect.

The EXP-001 SIFT arm on pair 01 reproduced the EXP-000 counts exactly (36 raw → 4 verified, coverage 0.23236). That is the control check that the baseline arm is the EXP-000 code path.

## Pair-by-pair interpretation

**pair_01_equatorial (primary).** SIFT 4, ORB 4, RIFT 0. Tie at the DLT minimum. ORB found more raw matches (69 vs 36) but the same 4 inliers, and control-point selection collapsed those 4 inliers to 3 points, so no transform was fitted. No matcher exceeded the decision-rule floor. H1 is not supported on the EXP-000 pair.

**pair_02_mid_equatorial.** SIFT 25, ORB 24, RIFT 0. Both SIFT and ORB exceed the floor. Held-out transfer RMSE is 1.90 px (SIFT) and 2.22 px (ORB). Those numbers are still matcher-derived. Highest verified yield is SIFT by one inlier. This pair is more matchable than pair 01; it is generalisation evidence, not a reason to retune.

**pair_03_south_mid.** SIFT 0, ORB 4, RIFT 0. ORB reaches the DLT minimum; SIFT does not. Neither exceeds the floor.

**pair_04_south_pole.** SIFT 4, ORB 4, RIFT 0. Tie at the DLT minimum.

## What this does and does not show

Highest verified-match yield on the primary pair is a **tie** (SIFT = ORB = 4). Across all four pairs the single highest cell is SIFT on pair 02 (25). That improvement is **not consistent** across pairs. RIFT produced 0 verified inliers on every real pair.

No matcher is claimed to be globally superior.

The in-repository RIFT implementation is not a failed install: on synthetic contrast reversal it recovers the known shift while SIFT and ORB do not. On synthetic 2× scale it collapses, as pre-registered. The real-data zero is therefore read as the predicted scale-confounder of a fixed 96-pixel descriptor on matching views whose per-image stride is different (pair 01: 15 vs 8), not as a silent crash.

## Limitations / confounders

- independent accuracy = NOT VALIDATED. No surveyed lunar control exists.
- Held-out RMSE, when computed, is not accuracy.
- Four-point DLT residuals are an algebraic identity.
- Matching-view stride is per image, so residual scale remains between OHRC and LROC views. RIFT cannot absorb that; SIFT can.
- LoFTR / LightGlue were not run. Changing the matching-view stride for one matcher only was refused as a confound.
- `sun_angle_difference_degrees` is None. SPICE is not implemented.
- **LROC ground sample distance is `None` on all four pairs**, so the OHRC↔LROC scale ratio — the confounder that most plausibly explains RIFT's zero — cannot be measured from the ingested products, only named. The NAC CDR labels carry `LINE_EXPOSURE_DURATION` but no resolution, altitude, or pointing geometry.
- **Overlap is never recomputed from the data.** `demo_pairs.yaml` declares `overlap_status: verified` from NASA PDS ODE footprints, but ingestion does not recompute footprints and `expected_overlap` stays `None`. A pair with little true overlap and a pair with a genuinely hard matching problem are indistinguishable in these records.
- **Stride decimation is aggressive.** Matching runs at strides of 15–18 (OHRC) and 6–8 (LROC), i.e. on 4.2 M pixels of a 0.94–1.2 G pixel product. Fine texture that any matcher would need is discarded before matching begins.
- **Control-point selection interacts with yield and is part of the outcome.** ORB on pair 01 had 4 verified inliers but only 3 control points, because two fell in the same 8×8 grid cell; that alone blocked its transform fit. Selection is not a neutral pass-through.
- Full-raster registration remains blocked by the 16,777,216-pixel cap.
- Four pairs, one scene each, no repeated measurement and no error bars. `characterize_pair` leaves `difficulty`, `gsd_ratio`, and `sun_angle_difference_degrees` unset, so pairs cannot be stratified by difficulty. Four pairs cannot freeze a matcher (D-007).

## Conclusion

On the EXP-000 pair, matcher choice among {SIFT, this RIFT, ORB} did **not** move verified yield above the four-inlier projective DLT minimum. Matcher identity is not the demonstrated correspondence bottleneck on that controlled pair.

On one of three generalisation pairs, SIFT and ORB both exceeded the floor with nearly equal yield. The effect is pair-dependent, not a ranking of algorithms.

The decisive comparison is between the two sources of variation. SIFT's verified count across pairs is 4, **25**, 0, 4. The spread *between matchers within* any one pair is at most 1 (25 vs 24 on pair 02) or a tie at the meaningless minimum. The spread *between pairs for a single matcher* is 0 to 25. Between-pair variation exceeds between-matcher variation by more than an order of magnitude, so **H0 is not rejected**: the correspondence bottleneck for this data lies in pair-level geometry and overlap, not in the detector/descriptor.

That the same frozen stages yield 4 inliers on pair 01 and 25 on pair 02 also rules out the harness as the explanation. The pipeline is capable; the pairing is the constraint.

## Recommended EXP-002

The evidence points at the pair, not the matcher, so EXP-002 should stop varying the matcher and start measuring the thing that varied by an order of magnitude.

**Primary — quantify and control overlap and relative scale before matching.** Compute each pair's actual footprint intersection from the products' own geometry rather than trusting the manifest's declared `overlap_status`, and populate `gsd_ratio` so the OHRC/LROC scale difference becomes a measured quantity instead of an unknown. The testable prediction is that verified yield tracks true overlap area and inverse scale ratio, which pair 02's isolated success already suggests.

Two supporting arms follow directly from measurements above, and both are cheap:

- **Hold SIFT constant and isolate the matching-view scale policy on pair 01.** Replace per-image stride with a common-scale (GSD-normalised) matching view, keep every other EXP-000 setting, and test whether verified yield moves above the four-inlier floor. This deliberately changes the stride, which is exactly why it belongs in a new experiment with its own control rather than inside EXP-001. It also converts RIFT's uninterpretable zero into an actual test of radiation-robust matching.
- **Adopt `verified > min_samples` as a hard gate and cross-matcher disagreement as a standing diagnostic.** A 35,695-pixel disagreement between two "perfect" near-zero-residual fits should never have been reportable as success. Any future result whose transform is fitted from exactly `min_samples` points should be rejected automatically.

What EXP-002 should **not** do: add more matchers. Three structurally unrelated detector/descriptor families already gave the same answer on the same data.

## Distinctions this experiment must keep

1. **Raw matches** — after Lowe ratio test, `status == "raw"`.
2. **Verified matches** — RANSAC-style projective software baseline.
3. **Selected control points** — spatial grid on verified inliers.
4. **Refined points** — ZNCC parabolic baseline; zero change is INDETERMINATE.
5. **Fitted transformation** — DLT on selected/refined points.
6. **Registration output** — full raster blocked by the existing cap.
7. **Evaluation** — verification residuals vs independent accuracy (`NOT VALIDATED`).
8. **Held-out / cross-matcher scores** — consistency checks, not accuracy.
