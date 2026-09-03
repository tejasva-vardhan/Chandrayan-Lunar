# PS-closing phase 1 — coarse-to-fine correspondence core

Not EXP-007. One candidate correspondence path for SIH26166, compared with the frozen EXP-001 SIFT control.

## Mechanism

**Coarse-to-fine tiled multi-scale SIFT** (`src/matching/coarse_to_fine.py`).

- **A (control):** frozen `match()` = EXP-001 one-way SIFT on the pixel-budget matching view.
- **B:** same coarse SIFT, then additional SIFT on geometrically paired tiles at half the coarse stride. Coarse matches are kept. Downstream verification, transform, spatial diagnostics, seed, and pair are unchanged.

## Why this addresses the PS

The PS needs correspondences under scale and viewpoint change, with uniformly distributed points. EXP-001–006 showed the bottleneck is not matcher identity, representation, reciprocal protocol, or ZNCC. Pair_02 still matches on OHRC stride 16 / LROC stride 8, so fine texture never reaches SIFT. Multi-scale tiled search restores some of that texture inside the overlap implied by the coarse consensus, without a full-resolution SIFT or a learned matcher.

## Why not the obvious alternatives

- SIFT/Lowe/reciprocal retune: already NOT SUPPORTED.
- ORB/RIFT swap: EXP-001.
- ASIFT on the same coarse view: affine cost without restoring discarded pixels.
- LightGlue/LoFTR: heavyweight download/GPU stack, blocked.

**Expected cost:** one coarse SIFT plus at most four tiles, each within the existing 4,194,304-pixel budget. Runtime gate: B match ≤ 12× A.

## Hypothesis

H1: On `pair_02_mid_equatorial`, multi-scale tiled SIFT plus the existing geometric verification recovers more verified inliers and maintains or improves 8×8 occupancy versus the single matching-view SIFT baseline.

H0: it does not, or the transform becomes unstable, or runtime is pathological.

Raw match count is not success. Inlier ratio is reported, not gated (B is allowed to add local candidates). Parameters are not retuned after the run.

```powershell
$env:CHANDRAYAN_DATA_ROOT = "<external demo dataset containing the declared products>"
python scripts/run_ps_correspondence.py
```

## Results

**Primary pair `pair_02_mid_equatorial`: SUPPORTED.** Independent accuracy remains **NOT VALIDATED**. Parameters were not retuned.

| Metric | A — frozen SIFT | B — coarse-to-fine |
|---|---|---|
| Raw matches | 919 | 1630 |
| Verified inliers | 25 | **72** |
| Inlier ratio | 2.72% | 4.42% |
| Source occupied cells / 64 | 11 | **23** |
| Reference occupied cells / 64 | 9 | **14** |
| Verified bbox coverage | 0.508 | 0.407 |
| Max verified / source cell | 7 | 11 |
| Source concentration | 0.28 | 0.153 |
| Control points | 11 | 23 |
| Transform | fitted (full raster blocked) | fitted (full raster blocked) |
| Residual RMSE / median / max | 1.686 / 1.687 / 2.654 px | 2.081 / 2.080 / 3.000 px |
| Held-out RMSE | 1.904 px | 2.086 px |
| Match runtime | 9.95 s | 74.0 s (7.4× A) |
| Deterministic repeat | yes | yes |

Fine stage ran: coarse 919 → 25 inliers, 4 tiles at OHRC stride 8 / LROC stride 4, 711 novel fine matches added.

**Follow-up `pair_01_equatorial`: NOT SUPPORTED.** A and B both 36 raw → 4 verified (projective DLT floor). Fine stage skipped (`coarse_min_inliers=5`). This path cannot bootstrap when the coarse consensus is only four points.

Do not treat residuals or held-out RMSE as registration accuracy.