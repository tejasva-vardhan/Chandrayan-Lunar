# SIH26166 — Control-point selection design (Phase 2)

Status: Implementation note for `src/control_points/`  
Companion: Interface Freeze v1, Master spec v3 §19, D-005, VERIFICATION_DESIGN_V1  
Not a rewrite of the master specification.

This is a **baseline** spatial selector. The final strategy must be validated
on real Chandrayaan-2 / reference pairs. This document does not claim
optimality, sub-pixel accuracy, lunar registration accuracy, or SIH
evaluator compliance.

## 1. Purpose

Select a geometrically verified and spatially distributed set of
`ControlPoint` objects from a verified `CorrespondenceSet`.

A high-confidence cluster is not a sufficient control set (D-005).

## 2. Inputs / outputs

Frozen pipeline surface (unchanged):

```
select_control_points(correspondences: CorrespondenceSet, pair: RegistrationPair)
    -> list[ControlPoint]
```

Configurable runs:

```
select_control_points_with_settings(correspondences, pair, settings: ControlPointSettings)
```

`RegistrationPair` is accepted because the freeze requires it. This phase
does not read rasters, masks, GSD, or product dimensions: pixel origin and
image-format conventions are not defined in freeze v1. Extent is taken from
eligible correspondence coordinates only.

Verified correspondences are those with `Correspondence.status == "inlier"`
as assigned by `src/verification` (VERIFICATION_DESIGN_V1). Geometric
verification is not re-run. `rejected`, `filtered`, and `raw` items are not
selected. Non-finite coordinates are skipped. Exact `(source_xy,
reference_xy)` duplicates keep the first inlier only.

Each `ControlPoint` copies `source_xy` and `reference_xy` from the chosen
correspondence. `residual` is copied when it is already a finite value on
that correspondence. `uncertainty` is always `None` (no unit is frozen;
refinement owns a later real value).

`matcher_id` is not interpreted.

## 3. Spatial-selection strategy

Engineering baseline: independent axis-aligned grids on the **source**
bounding box and the **reference** bounding box of the eligible set.

1. Collect eligible inliers.
2. Compute min/max x and y on source_xy and on reference_xy.
3. Divide each axis into `grid_bins` equal bins (degenerate span → one bin).
4. Assign each candidate a source cell `(row, col)` and a reference cell
   `(row, col)`.
5. Walk candidates in quality order (section 4).
6. Accept a candidate only if its source cell is under
   `max_per_source_cell` and its reference cell is under
   `max_per_reference_cell`, and the optional `max_points` cap is not reached.

This is **not** “take the top N by confidence”. A dense cluster occupies few
source cells and is capped. Occupied cells elsewhere still contribute.

`grid_bins` is not a scientifically optimal cell count. The tiling is not
claimed to be uniform on the full image, because the full image extent is
not used.

## 4. Candidate quality ordering

No new composite score. Lexicographic order, smaller tuple first:

1. Finite residual present, then missing residual.
2. Smaller residual when both have a finite residual.
3. Finite confidence present, then missing confidence.
4. Larger confidence when both have a finite confidence.
5. Original index in `matches` (tie-break).

Missing confidence is **not** treated as `0.0`. Missing residual is **not**
treated as a numeric error of zero or of infinity; it is a separate group.

## 5. Deterministic tie-breaking

Identical input and `ControlPointSettings` produce the same list. There is
no RNG. Ties at the same residual/confidence group use the original
`CorrespondenceSet.matches` index.

## 6. Configuration

**Not** stored in `configs/default.yaml`.

### Engineering vs scientific (explicit)

The frozen callable has two arguments, so it must pick software values.

| Field | Two-arg software default | Classification |
|---|---|---|
| `grid_bins` | `8` | Engineering tiling so the two-arg API can run. Not an SIH cell count. |
| `max_per_source_cell` | `1` | Engineering cap against source-image clustering. |
| `max_per_reference_cell` | `1` | Engineering cap against reference-image clustering. |
| `max_points` | `None` | No extra global cap. Not a validated “needed N”. |

These values are **not** SIH thresholds, lunar-validated parameters, a final
scientific strategy, or benchmark results. Experiments must pass
`ControlPointSettings` into `select_control_points_with_settings`.

## 7. Edge cases

| Case | Behaviour |
|---|---|
| Empty `matches` | `[]` |
| No inliers | `[]` |
| Fewer eligible than `max_points` | Return all that pass spatial caps; do not fabricate |
| All inliers clustered (degenerate source extent) | One source cell; at most `max_per_source_cell` points |
| Exact duplicates | First inlier kept; later dropped |
| Non-finite coordinates | Skipped |
| Missing confidence / residual | Still eligible; ranking groups as in §4 |
| Highly uneven density | Occupied cells outside the dense region can still be selected |
| Degenerate/small extent | All points map to bin 0 on that axis |

## 8. Assumptions

- `status == "inlier"` is the verified set from Phase 1.
- Coordinates are the image-pixel tuples already stored; origin is not
  interpreted.
- Exact float-tuple equality is used for duplicates (no invented tolerance).
- Spatial “uniformity across the images” is approximated by occupancy caps on
  the **correspondence bounding boxes**, not the full raster.

## 9. Engineering defaults

See §6. They exist only for the frozen two-argument API.

## 10. Scientifically unresolved questions

- Grid vs quadtree vs other spatial diversity methods (v3 §19).
- Validated bin count, per-cell cap, and target control-point count.
- Whether occupancy should use full image dimensions once origin is defined.
- Occupied-cell ratio / nearest-neighbour uniformity as evaluation metrics
  (those fields are not on `ControlPoint`; evaluation is a later phase).
- How to use overlap masks once format is defined.
- Official SIH evaluator behaviour (D-011).

## 11. Limitations

- Bounding-box grids cannot represent uncovered regions of the full image.
- If every inlier lies in a tiny cluster, the selector cannot invent
  well-spread points that do not exist.
- One-per-cell is a software cap, not a proof of uniformity.
- Residual copied onto `ControlPoint` is the verification transfer error, not
  a new physical uncertainty.
- This baseline is matcher-independent only in that it reads frozen
  `Correspondence` fields.

Do not cite synthetic spatial tests as lunar accuracy or SIH evaluator
results.
