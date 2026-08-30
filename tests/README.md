# Tests

This tree separates **wiring** from **science**. Wiring tests prove that modules connect. They are not evidence that a matcher, geometry engine, or registration method works.

| Directory | Purpose | Evidence class |
|---|---|---|
| `unit/` | Canonical contracts, stub fail-closed behaviour, scientific-core import rules | Not scientific |
| `integration/` | Pipeline order, object flow, config structure, module boundaries. Marked `pytest.mark.wiring` | Not scientific |
| `scientific/` | Reserved for synthetic ground truth, independent checkpoints, and measured matcher/registration tests | Scientific — add when an owner implements a real method |
| `regression/` | Reserved for fixed benchmark pairs and metric tolerances | Scientific / regression — add later |

Integration tests may use doubles only for wiring. Doubles must not invent RMSE, inliers, transformations, or other scientific values.

Do not cite `tests/integration/` results as SIH accuracy claims.
