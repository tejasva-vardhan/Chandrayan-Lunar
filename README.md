# SIH26166 — Chandrayaan-2 lunar image correspondence

Scientific, geometry-aware, adaptive correspondence and registration for Chandrayaan-2 optical imagery (OHRC, TMC-2, IIRS) against lunar reference imagery.

This repository is the team implementation of Smart India Hackathon 2026 problem statement **SIH26166**.

## Current status

**FACT**

- Foundation only: documentation, canonical data contracts, pipeline interfaces, and tests for those contracts.
- No matcher, SPICE, sub-pixel, frontend, or HTTP scientific core is implemented yet.
- Official SIH dataset and evaluator constraints are **pending/TBD**. Do not treat any local or public lunar product as the official SIH test set.

**DECISION** (from v3.0)

- Final matcher is selected after a small controlled benchmark, not assumed now.
- Internal prototype may use representative authorized/public lunar data, clearly labeled as such.

## Source-of-truth hierarchy

1. Official SIH problem statement and official SIH rules/templates
2. Official ISRO/PRADAN product specifications and supplied Chandrayaan-2 SPICE documentation
3. Official LROC/JAXA product documentation
4. Peer-reviewed research
5. Our measured experiments
6. Engineering inference

A lower-level source cannot silently override a higher-authority requirement.

## Documentation

| Document | Location |
|---|---|
| Master Engineering & Research Specification v3.0 | `docs/master/SIH26166_Master_Engineering_Research_Spec_v3.md` |
| Team work division & implementation plan | `docs/master/SIH26166_Team_Work_Division_and_Implementation_Plan.md` (PDF alongside) |
| Recorded decisions D-001–D-014 | `docs/decisions/D-001_to_D-014.md` |
| Interface freeze v1 | `docs/architecture/INTERFACE_FREEZE_V1.md` |
| Official SIH guidelines / PS status | `docs/requirements/` |

## Team ownership

| Person | Owns |
|---|---|
| Tejas | Architecture, integration, contracts, `src/models/`, `src/pipeline/`, `src/io/`, `configs/`, `docs/` |
| Haruto | PDS/ingestion, preprocessing, manifests |
| Shashwat | SPICE, geometry, pair characterization |
| Chuba | Representation, matching, adaptive routing |
| Shaiz | Verification, control points, refinement, registration, evaluation, UI |

## Development workflow

- One person → one feature/module → one branch → one pull request.
- Keep `main` stable. Do not develop large features on `main`.
- Agree interfaces before large implementations.
- Do not commit raw scientific datasets or credentials unless explicitly permitted.
- Accuracy-affecting scientific changes require benchmarks/validation.
- Architecture changes go into the decision log.

## Current MVP target

The first scientific milestone (not implemented in this foundation) is:

real lunar data → `LunarProduct` → SIFT baseline → `CorrespondenceSet` → robust geometric verification → registration → basic metrics → registered image

## Configuration

Structural settings live in `configs/default.yaml`. Scientific thresholds and routing cutoffs are experimental and are not invented here.

## Development setup

Python 3.11+ is required.

```text
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
```

## Warning

The official SIH26166 dataset is currently **pending/TBD**. Do not invent its format, pairs, or evaluator. Do not claim official-dataset results from representative data.
