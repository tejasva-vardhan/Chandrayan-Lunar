"""Experimental verification settings. Not a scientific freeze.

These values are software defaults for a replaceable baseline estimator.
They are not validated on lunar imagery, not SIH evaluator constraints, and
not a selected geometric model (D-010, D-011).

Do not copy these into configs/default.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerificationSettings:
    """Configuration for one verification run.

    model_id / estimator_id select registry entries. They are labels for the
    wired baseline, not a claim that the method is the lunar solution.

    residual_limit
        Compared to image-space transfer error (see residuals.py). Same
        numeric convention as Correspondence coordinates (input pixel tuples).
        Not metres. Any numeric value supplied here is a run-time engineering
        setting, not an SIH threshold and not a lunar-validated parameter.

    max_trials
        Computational budget for the robust estimator. Engineering only;
        not a validated iteration policy and not a benchmark result.

    rng_seed
        Software determinism for sampling. Not a scientific parameter.

    confidence_min
        Optional gate on adapter-normalized Correspondence.confidence.
        None (the default) means do not filter by confidence, so verification
        still runs when confidence is None. Any numeric value is experimental
        and is not a validated cutoff.
    """

    model_id: str
    estimator_id: str
    residual_limit: float
    max_trials: int
    rng_seed: int
    confidence_min: float | None = None

    def __post_init__(self) -> None:
        if self.residual_limit < 0.0:
            raise ValueError("residual_limit must be >= 0")
        if self.max_trials < 1:
            raise ValueError("max_trials must be >= 1")
        if self.confidence_min is not None and not 0.0 <= self.confidence_min <= 1.0:
            raise ValueError("confidence_min must be None or in [0, 1]")


# --- Frozen two-argument API: engineering defaults only ---
# verify_matches(correspondences, pair) has no settings argument, so it must
# pick software values. The three numbers below exist ONLY for that reason.
#
# They are NOT:
#   - SIH thresholds
#   - lunar-validated parameters
#   - final scientific parameters
#   - benchmark results
#
# Do not copy them into configs/default.yaml. Replace them for any real
# experiment by calling verify_correspondences(..., settings).
UNVALIDATED_SOFTWARE_MODEL_ID = "projective_2d_baseline"
UNVALIDATED_SOFTWARE_ESTIMATOR_ID = "ransac_style_baseline"
UNVALIDATED_SOFTWARE_RESIDUAL_LIMIT = 3.0  # engineering default, not SIH
UNVALIDATED_SOFTWARE_MAX_TRIALS = 500  # engineering default, not SIH
UNVALIDATED_SOFTWARE_RNG_SEED = 0  # software determinism, not a scientific seed


def unvalidated_software_defaults() -> VerificationSettings:
    """Engineering defaults used by verify_matches(correspondences, pair).

    residual_limit=3.0, max_trials=500, and rng_seed=0 are required only because
    the frozen two-argument API cannot accept settings. They are software/test
    defaults, not SIH thresholds, not lunar-validated parameters, not final
    scientific parameters, and not benchmark results.

    Tests and experiments that depend on a specific model or limit should pass
    VerificationSettings to verify_correspondences instead.
    """

    return VerificationSettings(
        model_id=UNVALIDATED_SOFTWARE_MODEL_ID,
        estimator_id=UNVALIDATED_SOFTWARE_ESTIMATOR_ID,
        residual_limit=UNVALIDATED_SOFTWARE_RESIDUAL_LIMIT,
        max_trials=UNVALIDATED_SOFTWARE_MAX_TRIALS,
        rng_seed=UNVALIDATED_SOFTWARE_RNG_SEED,
        confidence_min=None,
    )
