# SIH26166 — Preprocessing design (Phase: preprocess)

Status: Implementation note for `src/preprocessing/`  
Companion: Interface Freeze v1, Master spec v3 §11–§13, TEAM_MODULE_HANDOFF_V1  
Not a rewrite of the master specification.

This is a **SOFTWARE BASELINE**. It is not a final Chandrayaan-2
preprocessing pipeline, not radiometric calibration, and not official SIH
evaluator evidence (D-011).

Throughout this document, distinguish:

| Kind | Meaning |
|---|---|
| **SOFTWARE PREPROCESSING** | Deterministic array operations on engineering `.npy` handles so later matching can run. |
| **SCIENTIFICALLY VALIDATED LUNAR PREPROCESSING** | A configuration whose benefit is measured on representative lunar pairs against independent metrics. **This baseline does not have that status.** |

Do not treat an engineering default as a scientific freeze because it is
implemented.

## 1. Purpose

Prepare a `RegistrationPair` for downstream representation and matching
without solving correspondence or alignment.

Frozen pipeline surface (unchanged):

```
preprocess(pair: RegistrationPair) -> RegistrationPair
```

The callable does **not**:

- match features (SIFT / RIFT / LightGlue / LoFTR / PWIFT);
- verify correspondences, select control points, refine, or register;
- implement `route()` or GSD-triggered resizing;
- run SPICE, DEM, camera-model, pushbroom, or RPC correction;
- overwrite original scientific rasters.

## 2. Pipeline position

```
ingest → characterize_pair → preprocess → generate_representation → match → …
```

`ingest_product` is product-level. `preprocess` is pair-aware and runs after
characterization (Interface Freeze v1). Characterization is preserved, not
recomputed.

## 3. Baseline preprocessing method

Default `preprocess(pair)` uses `unvalidated_software_defaults()`:

```
raw software raster (.npy)
        ↓
finite / product-mask valid mask
        ↓
optional robust percentile intensity stretch   [ON — ENGINEERING DEFAULT]
        ↓
optional median/IQR contrast                   [OFF]
        ↓
optional nan-aware mean denoise                [OFF]
        ↓
scale hook (identity; never resamples)
        ↓
derived {stem}.preprocessed.npy
```

Ablation factories (same code path, different flags):

| Label | Settings helper | Intensity | Contrast | Denoise | Scale |
|---|---|---|---|---|---|
| A. minimal | `minimal_preprocessing_defaults()` | off | off | off | identity |
| B. intensity | software defaults | on | off | off | identity |
| C. contrast | flags | off | on | off | identity |
| D. denoise | flags | off | off | on | identity |
| E. combinations | any mix | as set | as set | as set | identity |

This implementation does **not** run that ablation or select a winner.

## 4. Mathematical definitions

**Valid set** \(V\) for a plane: finite samples, AND an aligned product mask
when one loads. Image intensity `0` is valid.

**Intensity (percentile stretch), per 2-D plane:**

\[
p_{\mathrm{lo}} = P_{\mathrm{low}}(V),\quad p_{\mathrm{hi}} = P_{\mathrm{high}}(V)
\]

- \(|V|=0\): output all NaN (do not fabricate).
- \(p_{\mathrm{hi}}=p_{\mathrm{lo}}\): valid samples → midpoint
  \((y_{\min}+y_{\max})/2\).
- else (unclipped ENGINEERING DEFAULT):

\[
y = y_{\min} + \frac{x-p_{\mathrm{lo}}}{p_{\mathrm{hi}}-p_{\mathrm{lo}}}(y_{\max}-y_{\min})
\]

Optional `clip_to_output_range` then clips \(y\) to \([y_{\min}, y_{\max}]\).
Clipping is **off** by default because it flattens percentile tails and can
move argmax. Invalid positions stay NaN, not \(0\).

ENGINEERING DEFAULT: low=2, high=98, \([y_{\min},y_{\max}]=[0,1]\).
NumPy default linear percentile interpolation. 3-D arrays are stretched
**per band** so an IIRS cube is not collapsed to grayscale.

**Contrast (optional, off):** \(y=(x-\mathrm{median}(V))/\mathrm{IQR}(V)\).
Constant IQR → leave finite samples unchanged. Output unbounded. Invalid
stay NaN.

**Denoise (optional, off):** odd-square nan-aware mean. Invalid stay NaN
(holes are not filled).

## 5. Invalid-pixel handling

| Class | Meaning in this package |
|---|---|
| valid | finite, and product-mask True when aligned |
| invalid | NaN/Inf, or excluded by an aligned product mask |
| unknown | no raster, unreadable raster, or unalignable mask — no mask is invented |

NaN/Inf never enter percentile, median, or IQR calculations.

Product `mask_uri` (software `.npy`): bool True = valid; numeric finite and
≠0 = valid **in the mask encoding**. That is not a claim that image DN 0 is
no-data.

This is **not** a lunar-specific PDS invalid-pixel product.

## 6. Normalization

See §4 intensity stretch.

| Item | Value |
|---|---|
| Input domain | numeric units stored in the software `.npy` handle |
| Output domain | mapped range of \([p_{\mathrm{lo}}, p_{\mathrm{hi}}]\), default `[0, 1]`; unclipped tails may fall outside |
| Clipping | ENGINEERING DEFAULT off; optional clip flattens tails |
| Invalid behaviour | remain NaN |
| Physical radiance | not assumed |

Label: **engineering image-normalization**, not calibration.

## 7. Contrast handling

Not applied by default. Isolated as `enable_contrast_normalization`.

Reason it exists: later ablation C/E, same pairs and matcher.

Limitations: does **not** make OHRC/TMC-2/IIRS/NAC radiometrically
equivalent. A contrast map that helps same-modality pairs may harm
multimodal pairs.

## 8. Denoising

Optional `enable_denoise` with odd kernel (ENGINEERING DEFAULT 3). Off in
`preprocess(pair)`.

- Kernel: square nan-aware mean via sliding windows (NumPy only).
- Why it may help: suppress isolated spikes.
- How it may hurt: low-pass smoothing can shift peaks and weaken edges;
  feature localization can degrade.

No OpenCV/SciPy filter.

## 9. Scale handling

**No resampling.** `PairCharacterization.gsd_ratio` is descriptive
(Interface Freeze v1). Pixel origin is undefined. `apply_scale_hook`
accepts `gsd_ratio` and `enable_scale_normalization` and returns the array
unchanged.

There is no rule `GSD ratio > 2 → resize`. Matcher scale robustness is a
later benchmark, not a preprocessing claim. This baseline does not claim
scale invariance.

## 10. Geometric-normalization boundary

Preprocessing may change sample **values**, not sample **geometry**.

Forbidden here: affine/projective warp, homography, RANSAC, registration,
SPICE, DEM. Output shape equals input shape. Product `coordinates` are
copied, not rewritten.

Warping belongs to `register` (REGISTRATION_DESIGN_V1).

## 11. Output / raster handling

Image arrays are not embedded (Freeze v1). Derived imagery uses the existing
`LunarProduct.raster_uri` handle.

| Case | Behaviour |
|---|---|
| Readable `.npy` 2-D/3-D | write `{stem}.preprocessed.npy` beside the original; point `raster_uri` at it |
| Missing URI / missing file | leave that product unchanged |
| Unsupported encoding (not `.npy`) | leave that product unchanged |
| Write failure | leave that product unchanged |

Original files are not overwritten. Recoverability:

- `product_id`, instrument, mission, dimensions, GSD, coordinates, mask URI,
  radiometric_state, characterization, `pair_id`, `overlap_mask_uri` preserved;
- `Provenance.source_uri` kept if already set (ingestion product URI);
  otherwise set to the original raster URI;
- `Provenance.notes` records `preprocessed_from=<original raster uri>` and
  which optional steps ran.

No frozen model fields were added.

## 12. Immutability

The input `RegistrationPair` is not mutated. The callable returns
`pair.model_copy(update={...})` with copied `LunarProduct` objects when a
derived raster is written. Tests assert the original `.npy` bytes/values
and the input model dump are unchanged.

## 13. Engineering defaults

Used only because `preprocess(pair)` cannot take a settings object.
**Not** scientifically validated thresholds. **Not** copied into
`configs/default.yaml` (`preprocessing: {}` remains empty).

| Setting | Default | Role |
|---|---|---|
| `enable_intensity_normalization` | True | bounded numeric domain for later matching |
| percentiles | 2, 98 | robust range; outliers do not set the scale |
| output range | [0, 1] | mapped values of p2 and p98 |
| clip_to_output_range | False | preserve peak uniqueness |
| contrast / denoise / scale | False | optional ablation hooks |

Independent of matcher identity.

## 14. Multimodal limitations

Intensity and contrast operate per image (and per band). They do **not**
solve multimodal registration. OHRC↔OHRC behaviour is not evidence for
OHRC↔IIRS. Different modalities are not assumed comparable after stretch.

## 15. Synthetic validation

`tests/unit/test_preprocessing.py` and
`tests/scientific/test_synthetic_preprocessing.py` check software behaviour
on constructed arrays: finite/NaN/Inf, constants, empty valid regions,
known stretch, identity preservation, no GSD resize, peak location under a
monotonic map. They are **not** lunar accuracy results.

## 16. Future ablation plan

On the **same** image pairs and **same** downstream matcher / verification /
evaluation, compare A–E (§3) for:

- verified correspondence count and inlier ratio;
- registration RMSE, spatial coverage;
- independent checkpoint error;
- illumination, scale, and multimodal robustness.

Do not select a final preprocessing configuration until those measurements
exist. Do not claim improvement from this baseline.

## 17. Real lunar validation plan

After ingestion can supply real product rasters (not only `.npy` handles):

- confirm original PDS/GeoTIFF files remain untouched;
- compare matcher/evaluation metrics with A vs B vs C vs D vs E;
- treat IIRS cubes as multi-band (do not force grayscale);
- re-evaluate percentile choices on actual DN/radiance histograms.

Until official SIH data arrives (D-011), that work uses authorized
representative data only (D-012) and is not evaluator compliance.

## 18. Scientific limitations

- `.npy` is not Chandrayaan-2 PDS/GeoTIFF ingestion.
- Percentile stretch is not radiometric calibration.
- 2–98 percentiles are unvalidated engineering choices.
- Per-band stretch is not IIRS spectral reduction (v3 §14).
- No orientation correction, no scale-aware resampling, no photometric
  model, no illumination normalization beyond the optional contrast hook.
- `valid_pixel_ratio` on the product is not recomputed (ingestion metadata
  is preserved).
- Pixel origin remains undefined (Freeze v1 §8).

## 19. Unresolved research questions

- Which of A–E actually improves lunar registration metrics (§16)?
- Official SIH product format and invalid-pixel definition (D-011).
- Whether percentile stretch helps or hurts multimodal pairs.
- Justified GSD resampling kernel once pixel geometry is defined.
- Whether orientation/flip/rotation belongs here or in ingest.
- Interaction with representation (gradient / phase / IIRS PCA) — some
  representations may want raw DN, not [0, 1] stretch.
- Whether a shared pair-level normalization (joint histogram) is ever
  defensible across sensors.
