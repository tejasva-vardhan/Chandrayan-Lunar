# SIH26166 — Pair characterization design (Phase: characterize_pair)

Status: Implementation note for `src/geometry/`  
Companion: Interface Freeze v1, Master spec v3 §8 / §15, TEAM_MODULE_HANDOFF_V1, D-009  
Not a rewrite of the master specification.

This stage answers: **what kind of registration problem is this image pair?**

It exposes measurable pair factors so later experiments can correlate them
with registration performance. It does **not** prove that a pair is easy or
difficult, does **not** select a matcher, and does **not** implement
`route()`.

Throughout this document, distinguish:

| Kind | Meaning |
|---|---|
| **AVAILABLE MEASUREMENT** | A value computed from metadata or arrays that actually exist, using a documented formula. |
| **UNAVAILABLE INFORMATION** | Required input is missing, non-finite, or undefined. Stored as `None` (or omitted from `quality_flags`). Never replaced by a default. |
| **ENGINEERING DESCRIPTOR** | A software quantity useful for tests and later stratification. Not a lunar-validated metric. |
| **SCIENTIFICALLY VALIDATED METRIC** | Formula, units, population, and thresholds frozen against official SIH evaluation and/or measured on Chandrayaan-2 / reference pairs. **No characterization field has this status yet.** |

Do not treat an engineering definition as a scientific freeze because it is
implemented.

## 1. Purpose

Fill `PairCharacterization` on a `RegistrationPair` from information already
present on the source and reference `LunarProduct` objects.

The frozen pipeline surface is:

```
characterize_pair(source: LunarProduct, reference: LunarProduct) -> RegistrationPair
```

The callable is observational. It describes the pair. It does not:

- alter imagery, coordinates, or correspondences;
- load or resample rasters;
- preprocess, match, verify, select control points, refine, register, or evaluate;
- select SIFT / RIFT / LightGlue or any other matcher;
- implement `route()` or adaptive routing thresholds.

## 2. Relationship to v3 architecture

Master spec v3 §8 lists pair quantities computed *as available* before
matching, then used later to classify easy/normal/difficult and to select a
processing path. The same section states that **routing thresholds are
experimental and must be learned or validated rather than invented**.

Interface Freeze v1 places this stage immediately after ingest:

```
ingest → characterize_pair → preprocess → generate_representation → match → …
```

Geometry (D-009) owns the calculations stored on `PairCharacterization`.
The models only store results. Extra model fields are forbidden.

This implementation fills quantities that current software can defend.
Quantities that require SPICE, DEM, overlap masks, or raster arrays stay
unavailable until those inputs exist.

## 3. Input / output

**Input.** Two `LunarProduct` instances. Image arrays are not embedded.
Optional scientific fields on the product stay `None` until a reader extracts
them.

**Output.** A new `RegistrationPair`:

| Field | Behaviour |
|---|---|
| `pair_id` | Engineering identifier `{source.product_id}__{reference.product_id}` |
| `source` / `reference` | The input products, unchanged |
| `characterization` | A `PairCharacterization` object; uncomputable fields are `None` |
| `overlap_mask_uri` | Always `None` (no overlap mask is produced) |

Internal split:

1. `src/geometry/adapters.py` — metadata extraction (`ProductGeometry`, `GeometryProvider`)
2. `src/geometry/measures.py` and `rasters.py` — mathematical characterization
3. `src/geometry/difficulty.py` — descriptive flags; categorical difficulty stays `None`
4. `src/geometry/characterize.py` — public frozen callable

`characterize_pair_with_provider` is **not** a frozen signature. It exists so
a future SPICE adapter can supply `ProductGeometry` without changing
`characterize_pair(source, reference)`.

## 4. Dimensions

`LunarProduct.dimensions` is the source of width, height, and band count.

`image_dimensions(width, height)` returns `(width, height)` only when both
are integers `> 0`. `None`, booleans, zero, and negative extents are
rejected. Dimensions are **not** copied onto `PairCharacterization` (no
such contract field). They remain on the products.

Missing dimensions stay missing. They are not inferred from `raster_uri` or
filenames.

| Status | When |
|---|---|
| AVAILABLE MEASUREMENT | `ImageDimensions` present on the product (Pydantic already requires `width_px > 0`, `height_px > 0`) |
| UNAVAILABLE INFORMATION | `dimensions is None` |

## 5. GSD / scale ratio definition

**Convention (Interface Freeze v1, not reversed):**

```
gsd_ratio = source.gsd_meters / reference.gsd_meters
```

| Item | Definition |
|---|---|
| Source GSD unit | metres per pixel (`LunarProduct.gsd_meters`) |
| Reference GSD unit | metres per pixel |
| Ratio unit | dimensionless |
| Domain | both GSD values finite and `> 0` |

A ratio of `1.0` means equal reported GSD. A ratio `> 1` means the source
pixel footprint is larger than the reference (source coarser). This is a
**descriptive measurement**, not a routing threshold.

Missing, zero, negative, or non-finite GSD → `None`. There is no unit
conversion: the contract stores metres only. Invalid or unknown units cannot
appear as a separate field; they are therefore not guessed.

| Status | When |
|---|---|
| AVAILABLE MEASUREMENT | both products have finite GSD `> 0` |
| UNAVAILABLE INFORMATION | either GSD missing or invalid |
| ENGINEERING DESCRIPTOR | yes — software ratio of reported metres/pixel |
| SCIENTIFICALLY VALIDATED METRIC | no — not a lunar scale-difficulty score |

## 6. Sun-angle representation

`LunarProduct` has **no** Sun incidence, azimuth, or Sun-vector field.

**ENGINEERING IMPLEMENTATION DEFINITION** used only when both products
supply a 3-vector Sun direction in the **same unspecified frame**:

```
sun_angle_difference_degrees = atan2(||ŝ_src × ŝ_ref||, ŝ_src · ŝ_ref)
```

in degrees, where hats are unit vectors. Zero-length, wrong-length, or
non-finite vectors → `None`.

This is **not**:

- an incidence/azimuth combination (still unresolved, Interface Freeze v1 §8);
- a frame transformation (SPICE is not implemented);
- a scientifically validated lunar illumination metric.

`ProductMetadataProvider` never fills `sun_vector`, so
`characterize_pair(source, reference)` currently always leaves
`sun_angle_difference_degrees` as `None`. A future SPICE adapter may fill
`ProductGeometry.sun_vector` without changing the frozen callable.

Partial angle information is not completed. Missing components stay missing.

| Status | When |
|---|---|
| AVAILABLE MEASUREMENT | both Sun direction vectors present and valid (provider-injected; not on LunarProduct today) |
| UNAVAILABLE INFORMATION | default `characterize_pair` path; any missing/invalid vector |
| Unresolved | incidence vs azimuth combination; official SIH Sun-angle definition |

## 7. Viewing-geometry representation

`viewing_geometry_difference` is an optional **opaque** contract scalar.
Interface Freeze v1 does not define its unit or formula. v3 leaves the
definition open.

This stage **always stores `None`**, even if look vectors are present on
`ProductGeometry`. Look-vector angular separation is **not** silently written
into this field, because that would invent the definition.

`ProductGeometry.look_vector` is reserved so a future documented definition
can use it without changing the adapter architecture.

| Status | When |
|---|---|
| AVAILABLE MEASUREMENT | never, in this implementation |
| UNAVAILABLE INFORMATION | always |
| Unresolved | unit, formula, and whether DEM/pushbroom geometry is required |

## 8. Valid-pixel definition

Two different fields exist:

| Field | Meaning |
|---|---|
| `LunarProduct.valid_pixel_ratio` | Per-product fraction. Not pair/overlap-aware. Owned by ingestion when a reader computes it. |
| `PairCharacterization.valid_pixel_ratio` | Pair/overlap-aware validity. Geometry owns it. |

**ENGINEERING DESCRIPTOR** for a caller-supplied array (`array_valid_pixel_ratio`):

```
valid = count of finite samples (and mask True, if a mask is provided)
ratio = valid / array.size
```

- NaN and Inf are invalid.
- Zero-valued samples are **valid** (zeros are not a product invalid-pixel
  definition).
- Empty arrays → `None`, not `0.0`.
- All-invalid non-empty arrays → `0.0` (measured).
- Shape-mismatched masks → `None`.

`characterize_pair` does **not** load `raster_uri` or `mask_uri`. Product
file formats are not frozen. Combining the two per-product ratios would
invent pair/overlap-aware validity, so it is not done.

Boolean overlap masks are not treated as intensity rasters (True and False
are both finite). Without an overlap-aware numeric valid raster, the pair
field stays `None`.

| Status | When |
|---|---|
| AVAILABLE MEASUREMENT (array helper) | caller supplies a non-empty array |
| UNAVAILABLE INFORMATION (`characterize_pair`) | always, with current LunarProduct handles |
| SCIENTIFICALLY VALIDATED METRIC | no — not a PDS/SIH valid-pixel rule |

## 9. Overlap semantics

Image bounding-box intersection is **not** lunar geographic overlap.

`expected_overlap` is filled only when a caller supplies a finite fraction
in `[0, 1]` from a legitimate overlap mask or geometry-derived overlap.
`ProductMetadataProvider` never supplies that fraction.
`RegistrationPair.overlap_mask_uri` is not created.

`Coordinates.bbox` is ignored for overlap.

| Status | When |
|---|---|
| AVAILABLE MEASUREMENT | only if a future overlap source passes a validated fraction into `build_characterization(..., overlap_fraction=...)` |
| UNAVAILABLE INFORMATION | `characterize_pair` today |

## 10. Texture / contrast descriptors

`PairCharacterization.texture_contrast` is a single optional float. A
pair-level texture scalar is not defined for two images that may differ in
modality, so `characterize_pair` leaves it `None`.

Per-array **ENGINEERING DESCRIPTORS** (not written to the contract field):

| Function | Definition |
|---|---|
| `intensity_standard_deviation` | Population std (`ddof=0`) of finite samples |
| `robust_contrast_iqr` | `p75 − p25` of finite samples |

These are not scientifically validated lunar texture scores. Intensity
statistics are not assumed comparable across OHRC / TMC-2 / IIRS / NAC.

Rasters are not loaded from `raster_uri`.

## 11. Modality handling

`LunarProduct` has `instrument` (required) and no separate modality field.

| Contract field | Rule |
|---|---|
| `sensor_pair` | `"{source.instrument}/{reference.instrument}"` when both identifiers are non-empty |
| `modality` | the same explicit pairing; **not** mapped to optical / spectral / multimodal enums |

Filenames are not parsed. `"unspecified"` is preserved if that is the
stored instrument string; it is not treated as a reserved unknown token.

If either instrument identifier is missing or empty, both labels stay
`None` rather than inventing the missing side.

`quality_flags` may include `multimodal_pair` when the two instrument
strings **differ**. That flag is an engineering observation of string
inequality, not a scientific optical-vs-hyperspectral classification.

## 12. Difficulty representation

`PairCharacterization.difficulty` (`easy` / `normal` / `difficult`) is
**always `None`**.

v3 §8 says routing thresholds must be learned or validated, not invented.
This stage therefore does not assign:

- `scale > 2 → hard`
- `low_valid_pixel_quality` from an arbitrary ratio cutoff
- `strong_scale_difference` from an arbitrary ratio cutoff

`quality_flags` records **availability** and instrument inequality only, in
this fixed order:

1. `scale_difference_available` — `gsd_ratio` was computed (including `1.0`)
2. `illumination_difference_available` — Sun-angle difference was computed
3. `viewing_geometry_difference_available` — not emitted (field stays `None`)
4. `multimodal_pair` — instrument strings differ
5. `acquisition_time_difference_available` — time difference was computed

These flags are ENGINEERING labels for later experiment stratification.
They are not consumed by routing.

No geometry thresholds were added to `configs/default.yaml`.

## 13. Missing-data semantics

| Situation | Result |
|---|---|
| Field not present on `LunarProduct` | `None` |
| Non-finite number (`NaN`, `Inf`) | `None` (except measured all-invalid raster ratio `0.0`) |
| Zero / negative GSD | `None` |
| Mixed timezone-aware and naive acquisition times | `None` (do not assume UTC) |
| Empty raster passed to array helpers | `None` |
| Overlap from bounding boxes | not computed; `expected_overlap` stays `None` |
| Missing Sun / look vectors | corresponding angles stay `None` |

Zero is used only when it is the measured value (identical timestamps,
zero angular separation, all-invalid non-empty raster). Zero is never a
stand-in for missing data.

## 14. Numerical validation

- GSD ratio uses Python float division after finite-positive checks.
- Angular separation uses `atan2` of cross-product magnitude and dot
  product (stable at 0° and 180°).
- Time difference is `abs((t_source − t_reference).total_seconds())`.
- Raster ratios and statistics use NumPy finite masks. Population std uses
  `ddof=0`.
- Characterization is deterministic for the same inputs (`quality_flags`
  order is fixed).

## 15. SPICE extension point

SPICE is **not implemented**. `spiceypy` is not a dependency. Kernels are
not parsed.

Extension without changing characterization architecture:

- `GeometryProvider.for_product(product) -> ProductGeometry`
- `ProductGeometry.sun_vector` / `look_vector` currently `None`
- `characterize_pair_with_provider(source, reference, provider)`

A future SPICE adapter should provide vectors in a **documented common
frame**. This package does not transform frames.

## 16. DEM extension point

DEM / terrain is **not implemented**.

`ProductGeometry.terrain_available` is always `False` from the product
adapter. No DEM is read, sampled, or used to invent viewing geometry or
overlap. The boolean exists so a future terrain adapter can mark
availability without adding frozen contract fields.

## 17. Why routing is not implemented

v3 §8 routing examples (normal optical → fast matcher, large scale gap →
stronger matcher, …) depend on thresholds that the specification says must
be learned from experiments such as:

- Sun-angle difference → registration performance
- scale ratio → registration performance
- modality → registration performance
- viewing geometry → registration performance
- texture / quality → registration performance

Interface Freeze v1 §8: adaptive-routing thresholds and an explicit
`route()` operation are intentionally undefined (M5). `src/routing/`
remains empty of `route()`. This stage does not import matchers and does
not write `matcher_id`.

## 18. Scientific limitations

- No Chandrayaan-2 / LROC / IIRS pair has been characterized against
  independent truth.
- Sun-angle math is unused on the default path because products have no
  Sun metadata.
- Viewing geometry is undefined by contract.
- Overlap is not estimated from map projection, SPICE, or DEM.
- Texture helpers are not a lunar texture model and are not attached to
  the pair contract field.
- `multimodal_pair` is not a validated multimodal taxonomy.
- `pair_id` is an engineering string, not a dataset identifier.
- Pixel origin (centre vs corner) remains undefined (Freeze v1 §8).

## 19. Engineering defaults, if any

There are **no numeric characterization defaults**.

The only engineering choices that are not scientific measurements:

- `pair_id` formatting (`{source}__{reference}`);
- `sensor_pair` / `modality` string formatting (`source/reference`);
- `quality_flags` vocabulary and order;
- population std (`ddof=0`) and IQR percentiles for optional array helpers.

No values were added under `geometry:` in `configs/default.yaml`.

## 20. Unresolved research questions

- Official SIH pair list, evaluator, and required characterization fields
  (D-011).
- Incidence vs azimuth combination for Sun-angle difference.
- Exact `viewing_geometry_difference` unit and formula.
- Pixel origin; whether GSD is pixel-centre or pixel-corner sampling
  distance.
- Legitimate lunar overlap definition (projected intersection, valid-pixel
  intersection, SPICE footprint, …).
- Whether pair `valid_pixel_ratio` should use overlap-mask area, source
  valid ∩ reference valid, or another population.
- Whether a pair-level `texture_contrast` scalar should exist at all for
  multimodal pairs.
- Which `quality_flags` (if any) correlate with registration failure.
- Frame and time ephemeris for Sun and camera vectors (SPICE / ALE / CSM).
- When DEM actually improves viewing-geometry or overlap estimates (v3 §17).

## 21. Future real-data validation

After ingestion can populate GSD, times, dimensions, and (later) SPICE
vectors on real products, experiments should record these characterization
fields beside registration metrics **without** turning them into routing
cutoffs until correlations are measured.

Suggested later checks (not claimed by this implementation):

- reported GSD ratio vs independently documented product GSD;
- SPICE Sun-vector separation vs labelled illumination difference;
- overlap fraction vs an independently produced overlap mask;
- characterization determinism on the same PDS products.

Until then, tests in `tests/unit/test_geometry.py` and
`tests/scientific/test_synthetic_pair_characterization.py` are
**mathematical tests of the software**, not lunar validation.
