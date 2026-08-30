# SIH26166 — Sub-pixel control-point refinement design (Phase 5)

Status: Implementation note for `src/refinement/`  
Companion: Interface Freeze v1, Master spec v3 §20, D-006, CONTROL_POINT_SELECTION_DESIGN_V1, REGISTRATION_DESIGN_V1  
Not a rewrite of the master specification.

**This implementation is a software baseline and does not establish lunar
sub-pixel accuracy.**

A decimal-valued coordinate is **not** evidence of sub-pixel accuracy.
This stage estimates a continuous-valued displacement from local image
evidence and checks that estimate against synthetic ground truth. It does
not validate Chandrayaan-2 / LROC / IIRS products and is not official SIH
evaluator evidence (D-006, D-011).

## 1. Purpose

Improve the coordinate **precision** of already selected control points
without changing correspondence identity.

Pipeline position (frozen, unchanged):

```
select_control_points
        ↓
refine_points
        ↓
register
```

Coarse control point → local image neighborhood → sub-pixel displacement
estimate → refined control point → optional uncertainty → later
registration.

This stage does **not**:

- rematch points or create new correspondences;
- change a matcher identity (ControlPoint has no `matcher_id`);
- rerun RANSAC or change inlier status;
- replace the selected control-point population;
- call `register()`;
- implement `route()` or adaptive method selection;
- claim multimodal OHRC ↔ IIRS / TMC-2 refinement.

## 2. Definition of sub-pixel refinement

**Sub-pixel refinement** here means: given a coarse correspondence
`(source_xy, reference_xy)`, estimate a **continuous** displacement
` (dx, dy) ` from local image evidence, and write

```
refined.reference_xy = (reference_xy[0] + dx, reference_xy[1] + dy)
refined.source_xy    = source_xy    # template origin, unchanged
```

The displacement must come from maximizing a documented local similarity
objective on sampled image neighborhoods, then locating that objective's
peak in continuous lag coordinates.

The following are **not** sub-pixel refinement:

- returning the coarse coordinate unchanged and calling it refined;
- adding an arbitrary decimal such as `(+0.001, +0.001)`;
- writing a float because the type is `float`;
- bilinear *image warping* during registration (REGISTRATION_DESIGN_V1 §8).

## 3. Precision versus accuracy

| Term | Meaning in this package |
|---|---|
| **Coordinate precision** | The numeric resolution of the reported coordinate (a continuous value, not snapped to the integer pixel grid). The fine ZNCC grid step is 0.1 px (ENGINEERING DEFAULT); the 2-D quadratic vertex is not quantized to that step. Precision is **not** a performance claim. |
| **Coordinate accuracy** | Agreement with an independent truth: `error = (dx_hat, dy_hat) − (dx, dy)`. Synthetic tests measure software accuracy against a declared generating translation. Lunar accuracy is **not** measured. |

Decimal output can have high precision and low accuracy. Passing a
synthetic Euclidean bound demonstrates software recovery of a known
shift. It does **not** demonstrate lunar sub-pixel accuracy (D-006).

## 4. Input / output

Frozen pipeline surface (unchanged):

```
refine_points(control_points: list[ControlPoint], pair: RegistrationPair)
    -> list[ControlPoint]
```

Note: the orchestrator calls `refine_points(control_points, pair)`, not
`(pair, control_points)`. This design follows the frozen signature.

Configurable runs:

```
refine_points_with_settings(control_points, pair, settings: RefinementSettings)
```

| Input | Use |
|---|---|
| `control_points` | Selected population from `select_control_points`. Order and count are preserved. |
| `pair.source.raster_uri` / `pair.reference.raster_uri` | Software `.npy` intensity handles (same engineering convention as registration). Not SIH/PDS ingestion. |
| `pair.characterization` | **Not read.** Adaptive routing is out of scope. Modality is not guessed. |

Each output `ControlPoint`:

- is 1:1 with the input list (same index = same correspondence);
- copies `residual` from the input (verification transfer error; **not**
  recomputed);
- sets `uncertainty` to `None` on success (see §9);
- on failure is a copy of the original point (coordinates unchanged).

The input list and input objects are not mutated. `register` is not called.

## 5. Baseline algorithm

Registry (not a frozen enum):

| `method_id` | Role |
|---|---|
| `zncc_parabolic_baseline` | SAME-MODALITY / SOFTWARE BASELINE. Zero-mean NCC, integer-lag search, fractional-lag ZNCC, 2-D quadratic peak. |
| `identity_passthrough` | Ablation hook: return points unchanged. Not a sub-pixel method. |

`refine_points()` wires `zncc_parabolic_baseline` because the frozen
two-argument API needs a default.

**Why this is an appropriate software baseline**

- ZNCC is a standard local similarity with a closed-form objective and
  invariance to affine intensity (gain/bias).
- Integer-lag search plus a fractional-lag re-evaluation is a documented
  way to estimate a continuous displacement from image neighborhoods.
- A 2-D quadratic of the fine 3×3 is a simple, justified continuous-peak
  estimator (SOFTWARE BASELINE, not a final scientific interpolator).
- NumPy only. Replaceable via `RefinementSettings.method_id` so a later
  ablation can swap methods without changing the frozen signature.

It is **not** permanently hard-coded as the only algorithm. It is **not**
claimed to be optimal, multimodal, or lunar-validated.

## 6. Mathematical objective

SAME-MODALITY / SOFTWARE BASELINE objective: **zero-mean normalized
cross-correlation (ZNCC)** over co-valid finite pixels.

Let \(T\) be the source template and \(P\) a reference patch of the same
shape. Let \(V\) be the set of indices where both are finite. Let
\(n = |V|\), \(\mu_T\) and \(\mu_P\) the means on \(V\):

\[
\mathrm{ZNCC}(T,P)
= \frac{\sum_{i \in V} (T_i-\mu_T)(P_i-\mu_P)}
       {\sqrt{\sum_{i \in V} (T_i-\mu_T)^2}\,
        \sqrt{\sum_{i \in V} (P_i-\mu_P)^2}}.
\]

Undefined (that lag is skipped) when \(n\) is below the valid-pixel
requirement or either centred vector has near-zero variance.

This is **not** raw SSD/MSE. SSD/MSE is intensity-scale sensitive and is
not claimed as a multimodal solution.

The estimated displacement is the lag \((\widehat{\mathrm{d}x},
\widehat{\mathrm{d}y})\) that maximises ZNCC in continuous coordinates
around the coarse reference location.

## 7. Local window / search strategy

Coordinate convention (same as Correspondence / ControlPoint):

- `(x, y)` = `(column, row)`; array index is `[y, x]`.
- Integer `(x, y)` addresses that sample on the raster grid.
- Pixel-centre versus pixel-corner is **not** interpreted (Interface
  Freeze v1). This module does not add 0.5.

Template: window of side `2 * window_radius + 1`, centred at `source_xy`,
sampled by bilinear interpolation (at integer centres this equals a crop).

Integer search: lags \(u, v \in \{-\texttt{search\_radius},\ldots,
+\texttt{search\_radius}\}\). The reference window at lag \((u,v)\) is
centred at `(reference_x + u, reference_y + v)`.

Fractional search: after the discrete peak \((u^\ast, v^\ast)\), ZNCC is
re-evaluated on a grid of offsets
\(k \cdot \texttt{fine\_step}\) with
\(|k \cdot \texttt{fine\_step}| \le \texttt{fine\_half\_width}\).

| Setting | Two-arg software default | Classification |
|---|---|---|
| `window_radius` | `7` (15×15 template) | ENGINEERING DEFAULT |
| `search_radius` | `3` | ENGINEERING DEFAULT |
| `fine_half_width` | `1.0` px | ENGINEERING DEFAULT |
| `fine_step` | `0.1` px | ENGINEERING DEFAULT |
| `min_valid_pixel_fraction` | `0.75` | ENGINEERING DEFAULT |
| `min_peak_zncc` | `0.25` | ENGINEERING DEFAULT |

These values exist only because `refine_points(control_points, pair)`
cannot take a settings object. They are **not** SIH thresholds, lunar-
validated windows, or multimodal parameters. Do not copy them into
`configs/default.yaml`. Experiments must pass `RefinementSettings`.

**Boundary behaviour.** The full integer search halo must lie inside the
inclusive pixel box `[0, W-1] × [0, H-1]`. There is no wrap, no zero-pad,
and no replication (those would fabricate correlation). If the halo does
not fit, that point is not refined.

**Invalid / NaN / Inf pixels.** Non-finite samples are excluded from ZNCC.
A bilinear sample whose 2×2 neighborhood contains a non-finite value is
NaN.

**Minimum valid pixels.** `max(4, ceil(min_valid_pixel_fraction * window_size))`.
The template itself must also have non-zero variance.

3-D software rasters are treated as `(H, W, C)` (registration warp
convention) and averaged over the last axis. That band mean is an
ENGINEERING DEFAULT so the same-modality baseline can run; it is not
radiometric calibration.

## 8. Continuous peak estimation

```
integer-lag ZNCC surface
        ↓
discrete peak (u*, v*), must be interior to the integer search
        ↓
ZNCC re-evaluated on a fractional-lag grid around (u*, v*)
        ↓
discrete peak of the fine grid
        ↓
2-D quadratic vertex of the fine 3×3  (fallback: fine-grid argmax)
        ↓
(dx, dy) added to the coarse reference coordinate
```

The 2-D quadratic on a 3×3 neighborhood in index units \((x,y)\in\{-1,0,1\}\)
is

\[
f(x,y) = A x^2 + B y^2 + C x y + D x + E y + F
\]

fitted by least squares. The vertex solves the 2×2 Hessian system. It is
accepted only when the Hessian is negative definite and the vertex lies
in \((-1,1)^2\). Index units are then scaled by `fine_step` to pixels.

Independent 1-D three-point parabolas on the *integer* ZNCC surface are
**not** used as the production estimator: they are biased when the
correlation peak is asymmetric or diagonally elongated. The 1-D formula
remains in `peak.py` as a documented primitive and unit-test target.

This continuous step is a SOFTWARE BASELINE. It is not a final scientific
interpolator (sinc, Foroosh phase, ISIS-style, etc.).

## 9. Uncertainty semantics

`ControlPoint.uncertainty` is optional. Interface Freeze v1 assigns **no
unit**.

This baseline **leaves `uncertainty` as `None` on successful refinement.**

A peak-curvature number can be computed from the quadratic Hessian, but
it is **not** a calibrated 1-σ pixel error, not metres, and not an SIH
uncertainty definition. Writing that number onto the frozen field would
fabricate a scientifically undefined quantity.

| Outcome | `uncertainty` |
|---|---|
| Refinement succeeded | `None` (not invented) |
| Refinement failed | copied from the original point (usually `None` from selection) |
| Original had a stale value and refinement succeeded | `None` (old value no longer applies; no replacement is defined) |

**SCIENTIFICALLY VALIDATED UNCERTAINTY: not established.**

A later experiment may map peak curvature and ZNCC to a calibrated pixel
σ using synthetic residuals, then document a unit before filling the
field.

## 10. Failure handling

A point is **not** refined when:

- source or reference raster URI is missing, unreadable, or not `.npy`;
- raster rank is not 2-D or `(H, W, C)`;
- coordinates are non-finite;
- the template or the full integer search halo leaves the usable image
  area;
- the template has too few finite pixels or no intensity structure;
- no finite ZNCC value exists;
- the discrete peak is below `min_peak_zncc`;
- the discrete peak lies on the integer-search border (not a confirmed
  interior maximum);
- the fractional-grid peak is missing or non-finite;
- the refined coordinate would be non-finite.

**Behaviour:** return a copy of the original `ControlPoint`. Do not
drop the point, do not invent a coordinate, do not convert failure into
a successful refinement.

The frozen return type is `list[ControlPoint]`. There is no per-point
success flag on the contract. Failure is expressed by **unchanged
coordinates**, not by a fabricated refined point. Unknown `method_id` is
a configuration error (`ValueError`), not a silent fallback.

Empty input → `[]` (nothing to refine; rasters are not required).

## 11. Boundary handling

| Case | Behaviour |
|---|---|
| Template would sample outside `[0, W-1]×[0, H-1]` | fail, preserve original |
| Integer search halo would sample outside that box | fail, preserve original |
| Fractional lag would sample outside | that lag is skipped (`NaN` on the fine surface) |
| Discrete peak on the integer-search edge | fail, preserve original |
| Wrap / pad / replicate | **not used** |

## 12. Multimodal limitation

The SIH problem is **multimodal**. OHRC, TMC-2, IIRS, and reference
imagery can differ substantially in radiometry and spectrum.

`zncc_parabolic_baseline` is labelled:

**SAME-MODALITY / SOFTWARE BASELINE**

It is **not** a solution for OHRC ↔ IIRS refinement (or any other
cross-modal pair). ZNCC assumes comparable local intensity structure
up to gain and bias. That assumption fails when the modalities do not
share that structure.

The registry can later add a modality-robust objective (phase
correlation, mutual information, RIFT-style descriptors, etc.). This
phase does **not** implement those methods and does **not** read
`PairCharacterization.modality` (no guessing, no `route()`).

## 13. Synthetic validation methodology

Official SIH data are not available. Software tests use **mathematically
controlled synthetic images** with a declared generating translation.

**Generating model (TEST ONLY, not a lunar model):**

1. Build a periodic band-limited texture (sum of sinusoids with integer
   numbers of cycles on a 96×96 grid).
2. Translate it by a known `(dx, dy)` with an FFT phase ramp so a
   feature at `(x, y)` appears at `(x+dx, y+dy)`.
3. Place coarse control points at interior integer locations with
   `reference_xy == source_xy` (identity), so any recovered offset must
   come from the shifted imagery.
4. Estimate \((\widehat{\mathrm{d}x}, \widehat{\mathrm{d}y})\).
5. Compute `error_x = dx_hat - dx`, `error_y = dy_hat - dy`, and
   Euclidean error.

**SOFTWARE TEST TOLERANCE:** 0.15 px Euclidean.

Chosen from this construction (default window 7, search 3, fine grid
1.0 / 0.1, 2-D quadratic). Observed worst Euclidean error among the
tested shifts was about **0.05 px**. The bound is 0.15 px: three times
that observed worst case and 1.5 times the 0.1 px fine-grid step. It is
not tightened to 0.05 to invent an impressive figure, and it is **not**
lunar accuracy.

Synthetic error **must not** be reported as lunar sub-pixel accuracy.

The FFT generating model is independent of the spatial ZNCC estimator
(different algorithm family). Tests still use the same pixel-tuple
convention. That is software validation, not scientific independence
on real lunar checkpoints (§15).

## 14. Ablation plan

**Not implemented in this phase.** The code is structured so a later
experiment can compare:

```
NO REFINEMENT                 identity_passthrough
        vs
CURRENT BASELINE              zncc_parabolic_baseline
        vs
FUTURE MULTIMODAL / PHASE / ISIS-STYLE METHOD
                              additional registry entry
```

How:

- pass `RefinementSettings(method_id=...)` into
  `refine_points_with_settings`;
- keep the same selected control points;
- run `register` afterwards as a **separate** stage;
- evaluate with independent checkpoints (not the refinement objective
  on the same windows).

Do not cite the identity method as refinement accuracy.

## 15. Real-data validation plan

When authorized Chandrayaan-2 / reference products exist:

1. Do **not** score refinement with the same ZNCC windows used to
   estimate the displacement (that reuses the training objective).
2. Hold out independent checkpoints: trusted geometric/SPICE
   correspondences, a spatially disjoint control subset, or an
   official evaluator set when released (D-011).
3. Report pixel error and, where geometry supports it, physical error
   (master spec v3 §20).
4. Compare no-refinement vs this baseline vs any later method on those
   **held-out** points.
5. Treat representative public lunar data (D-012) as representative
   only, never as the official SIH test set.

Until that exists, only synthetic software tests are valid evidence,
and only of implementation behaviour.

## 16. Scientific limitations

- Same-modality ZNCC does not solve multimodal refinement.
- Local translation is assumed inside the window. Scale, rotation,
  relief, and pushbroom geometry are not modelled (D-010).
- `source_xy` is the template origin and is not itself refined.
- Verification `residual` is copied and becomes slightly stale after
  the reference coordinate moves. This stage does not own a residual
  formula.
- `.npy` handles are not Chandrayaan-2 PDS/GeoTIFF ingestion.
- Engineering window/search/fine-grid values are unvalidated.
- Uncertainty is not scientifically defined.
- Pixel origin (centre vs corner) remains unfrozen.
- Success on FFT-shifted sinusoids is not lunar sub-pixel accuracy.

## 17. Unresolved research questions

- Which local objective is robust for OHRC ↔ TMC-2 and OHRC ↔ IIRS.
- Whether source, reference, or both coordinates should be refined.
- Validated window, search, and fine-grid parameters on real products.
- A calibrated uncertainty (unit, formula, coverage).
- Independent checkpoint protocol for real lunar pairs (D-006).
- Interaction with DEM / SPICE / pushbroom models (D-009, D-010).
- Official SIH evaluator definition of sub-pixel accuracy (D-011).
- Whether verification, refinement, and registration must share a
  geometric model.

## 18. Future candidate methods

Not implemented now (separate stages / later experiments):

- phase correlation / Foroosh-style sub-pixel phase
- ISIS-style or other photogrammetric local registration
- mutual information or modality-robust metrics
- RIFT / RIFT2, LightGlue, LoFTR (matcher family, not this stage)
- Lucas–Kanade / inverse-compositional local alignment
- sinc / upsampled-correlation peak finding
- adaptive method routing from pair characterization (`route()` is
  out of scope for this freeze)

The registry in `src/refinement/methods.py` is the extension point.
