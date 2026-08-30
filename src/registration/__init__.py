"""Image registration. Owned per TEAM_MODULE_HANDOFF_V1.

Pipeline import surface:
register(pair, control_points, correspondences) -> RegistrationResult.

Do not assume homography is the lunar model (D-010). The two-argument
callable uses projective_2d_baseline as an engineering software baseline.
Attach the provided CorrespondenceSet. Do not invent metrics.
"""

from src.registration.register import register, register_with_settings
from src.registration.settings import RegistrationSettings, unvalidated_software_defaults

__all__ = [
    "RegistrationSettings",
    "register",
    "register_with_settings",
    "unvalidated_software_defaults",
]
