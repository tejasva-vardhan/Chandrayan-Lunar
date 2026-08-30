"""Geometric verification. Owned per TEAM_MODULE_HANDOFF_V1 (Shaiz package).

Pipeline import surface: verify_matches(correspondences, pair) -> CorrespondenceSet.

CorrespondenceSet.matches remains the source of truth. Statuses are updated
on those items; a second correspondence collection is not created.

The geometric model and robust estimator are replaceable. The two-argument
pipeline callable uses an unvalidated software baseline, not a selected
lunar model (D-010). residual_limit=3.0, max_trials=500, and rng_seed=0
on that callable are engineering defaults for the frozen signature only;
they are not SIH or lunar-validated parameters.
"""

from src.verification.settings import VerificationSettings, unvalidated_software_defaults
from src.verification.verify import verify_correspondences, verify_matches

__all__ = [
    "VerificationSettings",
    "unvalidated_software_defaults",
    "verify_correspondences",
    "verify_matches",
]
