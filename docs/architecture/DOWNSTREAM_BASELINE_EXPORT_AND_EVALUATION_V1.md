# Downstream Baseline: Export and Evaluation

## Scope

This document describes a software-baseline downstream package. It does not
establish lunar registration accuracy, scale robustness, or sub-pixel validity.

## Evaluation separation

`verify_matches` labels fit correspondences and may attach fit residuals.
Those residuals remain verification diagnostics. They are not used as
`RegistrationMetrics.rmse` by `evaluate(result, pair)`.

The frozen pipeline call has no checkpoint argument and canonical models have
no ground-truth field. Therefore normal pipeline evaluation reports `rmse=None`
and adds the engineering flag `evaluation_unavailable`.

`evaluate_with_checkpoints(result, pair, checkpoints)` is an optional boundary
for an externally supplied, held-out `EvaluationCheckpoint` collection. It
computes RMSE only when all of these conditions hold:

- the result declares a finite 3x3 transform matrix;
- checkpoint coordinates are finite and the collection is non-empty;
- no checkpoint coordinate pair duplicates a correspondence or selected control
  point used in the fit population.

This prevents accidental reuse of fit points. It cannot establish that supplied
coordinates are physical lunar ground truth; their provenance and independence
must be demonstrated by a later experiment protocol.

## Portable export package

`export_result(result, pair, output_dir)` writes package-relative files only:

- `registered_source.<suffix>` when the registered output exists and can be copied;
- `correspondences.json`, `inliers.json`, `control_points.json` when data exists;
- `transformation.json` and `metrics.json` when data exists;
- always `registration_report.json` with status/failure flags, available
  configuration labels, portable product metadata, provenance, and the manifest.

The report omits raster/mask paths and reduces absolute provenance paths to a
filename. It does not invent absent outputs or metrics. Export warnings describe
copy failures without changing the registration result.
