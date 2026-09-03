# SIH26166 — Illumination-normalization representation (engineering baseline)

Status: Implementation note for `src/representation/illumination.py`  
Companion: Interface Freeze v1, Master spec v3 §11–§12, TEAM_MODULE_HANDOFF_V1  
Not a rewrite of the master specification.

This is a **SOFTWARE BASELINE**. It is **not**:

- a solution to lunar Sun-angle / incidence variation;
- radiometric calibration;
- SPICE-based photometric correction;
- phase congruency;
- a final representation choice (D-007);
- official SIH evaluator evidence (D-011).

Throughout this document, distinguish:

| Kind | Meaning |
|---|---|
| **ENGINEERING ILLUMINATION NORMALIZATION** | Deterministic array operations that reduce global gain/bias and local contrast drift on generic numeric images. |
| **SCIENTIFICALLY VALIDATED LUNAR ILLUMINATION ROBUSTNESS** | A measured improvement on representative lunar pairs against independent metrics under documented Sun-angle differences. **This baseline does not have that status.** |

Do not treat an implemented engineering default as a scientific freeze.

## 1. Purpose

Provide a representation that later matching can consume when an experiment
asks for controlled photometric normalization (v3 §12 option 5).

Frozen pipeline surface (unchanged):

```
generate_representation(pair: RegistrationPair) -> Any
```

The illumination baseline is **not** the default routed representation.
Default routing remains:

- easy / missing characterization → `intensity`
- normal → `gradient`
- difficult → `structural`

Request this baseline without changing the frozen one-argument signature:

```
generate_representation_with_settings(
    pair,
    MatchingViewSettings(representation_id_override="illumination"),
)
```

The callable does **not**:

- match, verify, select control points, refine, or register;
- run SPICE, DEM, or camera models;
- resample or silently resize;
- invent Chandrayaan-2 dimensions, GSD, bands, or routing thresholds.

## 2. Pipeline position

```
ingest → characterize_pair → preprocess → generate_representation → match → …
```

`preprocess` remains pair-aware product-handle normalization (Haruto).
This module is a **representation** (Chuba). It operates on generic arrays
and masks after matching-view stride decimation, if any.

`generate_representation` still returns `RepresentationResult` (`Any` on
the frozen surface). `match` is unchanged.

## 3. Method

Default `build_illumination_array(array, mask)` uses
`unvalidated_illumination_defaults()`:

```
numeric array
        ↓
finite ∩ aligned product-mask valid set
        ↓
optional robust percentile intensity stretch     [ON]
        ↓
optional nan-aware local z-score                  [ON]
        ↓
optional robust stretch of finite outputs         [ON]
        ↓
float32 array, invalid samples = NaN
```

Parameters live in `IlluminationSettings`. They are not written into
`configs/default.yaml`.

## 4. Mathematical definitions

**Valid set** \(V\): finite samples, AND an aligned product mask when one
is supplied. Image intensity `0` is valid. Unalignable masks raise; they
are not ignored.

**Robust intensity (percentile stretch), per 2-D plane:** same construction
as software preprocessing: \(p_{\mathrm{lo}}=P_{\mathrm{low}}(V)\),
\(p_{\mathrm{hi}}=P_{\mathrm{high}}(V)\). Empty \(V\) → all NaN. Constant
range → output midpoint. Otherwise affine map onto
\([y_{\min}, y_{\max}]\) (ENGINEERING DEFAULT \([0,1]\)). Clipping is off
by default.

**Local / relative contrast, per plane:** nan-aware window mean \(\mu\)
and standard deviation \(\sigma\) via a uniform filter on finite samples
only. For a valid pixel with enough neighbours and \(\sigma > \sigma_{\min}\):

\[
z = (x - \mu) / \sigma
\]

Otherwise a valid pixel is mapped to the output midpoint (near-constant
neighbourhood). Invalid pixels stay NaN; holes are not filled.

Window size is an odd **pixel** count (ENGINEERING DEFAULT 15). It is not
a GSD and not a Chandrayaan-2 raster dimension.

**Output stretch:** the same percentile map applied to finite \(z\) values
so uint8 matcher adapters see a bounded domain. This is an engineering
convenience, not illumination invariance of SIFT.

3-D arrays are processed **per band**. Band count is not hardcoded.

## 5. What this can and cannot show

On **synthetic** arrays this baseline is intended to be approximately
invariant to:

- global multiplicative brightness (\(a \cdot I\), \(a>0\));
- global additive brightness (\(I + b\));
- different linear dynamic ranges.

It does **not** establish:

- robustness to real lunar Sun-angle, azimuth, or incidence fields;
- invariance to spatially complex shadowing or terrain-coupled photometry;
- OHRC ↔ LROC ↔ SELENE radiometric equivalence;
- that EXP-002 / EXP-004 should switch default routing to this method.

Those claims require a later measured experiment on authorized pairs.

## 6. Invalid-pixel handling

| Class | Meaning |
|---|---|
| valid | finite, and product-mask True when aligned |
| invalid | NaN/Inf, or excluded by an aligned product mask |

Invalid positions remain NaN in the output. Finite-sample statistics never
include them. When this representation is selected, the matching validity
mask is the product mask intersected with finite outputs so SIFT does not
treat NaN-as-zero as a keypoint.

## 7. Shape and scale

Output shape equals input shape. This function never interpolates or
resizes. Matching-view stride decimation, when used, is the existing
explicit `MatchingViewSettings` policy on `generate_representation`, not
a hidden resize inside illumination.

## 8. Tests

`tests/unit/test_illumination_representation.py` uses constructed NumPy
arrays only. It is software validation, not lunar accuracy and not SIH
evidence.

## 9. Unresolved research questions

- Does this representation increase verified inliers under documented
  Sun-angle difference versus `intensity` / `gradient` / `structural`?
- Should local contrast be on or off for multimodal pairs?
- What window size, if any, is justified in metres rather than pixels
  once GSD geometry is defined?
- Interaction with preprocess percentile stretch (double stretch).
