# Agent Handoff Guide

This file is the first stop for any agent entering the project cold. Keep it short, current, and useful.

## Read Order

1. `README.md` for setup, commands, and output artifacts.
2. `ROADMAP.md` for the current next step and full decision log.
3. `docs/project_state.md` for the latest experimental conclusion and caution flags.
4. `docs/architecture.md` for the code map and physics-mode notes.
5. `docs/calibration.md` for numerical expectations and sanity checks.

## Current Rule Of Engagement

- Do not run broad long sweeps; the next step is a small 31^3 3D prototype.
- Treat old pre-fixed-domain results as historical context, not numerically identical baselines.
- Legacy fixed-domain `per_cell` source handling is reference-only because emitter/source geometry was not resolution-invariant.
- The latest source-normalized diagnostic classified the fixed-domain 41/63/81 comparison as `coarse_grid_artifact_likely`: 63x63 and 81x81 converge at physical radial peak 10.0, while 41x41 peaks at 5.0.
- Source-normalized breathing survives and m=4 persists. The global detector now reports envelope-scale periods and flags raw subpeak overcounting; the refreshed 63x63 source-normalized period is 3.040 with `subpeak_overcounting_possible` for the old raw 1.689 diagnostic-frame period.
- The latest core-modal probe classified direct core excitation as `boundary_transport_required`: boundary references at 63/81 retained the 0.92 breathing family with matched work, but core impulse/burst controls did not reproduce the reference post-cutoff breathing/radial/m=4 state.
- The targeted transport-control passes at 63x63 and 81x81 both classified the candidate as `boundary_geometry_sensitive`: boundary left, left-right, and rotating m=4 variants retained breathing, while direct annulus/near-defect drives did not reproduce the reference family.
- Boundary-only work-per-length controls at 63x63 and 81x81 kept the same classification; `boundary_rotating_m4_81` still reproduced the family after boundary flux density was normalized.
- The current next physics step is a small 31^3 3D prototype. Look for retained spherical shell breathing, not just high core energy.
- Keep rotation language cautious: m=4/non-axisymmetric structure often persists, but coherent angular phase is sensitive to sponge and resolution settings.

## Documentation Contract

After every meaningful task, update documentation before final response:

- Update `ROADMAP.md` when a task is completed, a result changes interpretation, or the next step changes.
- Update `docs/project_state.md` when an experiment/control is run, when a classification changes, or when a new caution is discovered.
- Update `README.md` when commands, output files, setup, or user-facing workflows change.
- Update `docs/architecture.md` when module ownership, physics semantics, or control-command behavior changes.
- Keep run artifacts under `runs/`; they are ignored by Git except `runs/.gitkeep`. Summarize important run results in docs so future agents do not need the local artifacts to understand the state.

## Required Verification

Use focused tests while developing, then run the full suite before handing back when feasible:

```powershell
python -m unittest discover -s tests
```

If a long simulation/control was run, include its command, classification, report path, and key values in `docs/project_state.md` and `ROADMAP.md`.

## Git Hygiene

- Keep generated run folders out of commits.
- Commit docs and code together when they describe the same completed task.
- Use the `main` branch unless the user asks for a feature branch.
- Remote is configured as `origin = git@github-wavey:terrywilliamsSEO/wavey.git`.
- SSH key alias is `github-wavey`; the public key must be added to GitHub before pushing.

## Key Commands

```powershell
python main.py fixed-domain-grid-control --config configs\long_validation_peak_0_92.json
python main.py fixed-domain-grid-control --config configs\long_validation_peak_0_92.json --include-81
python main.py resolution-diagnostics --config configs\long_validation_peak_0_92.json
python main.py source-normalized-resolution-diagnostics --config configs\long_validation_peak_0_92.json
python main.py core-modal-probe --config configs\long_validation_peak_0_92.json
python main.py transport-controls --config configs\long_validation_peak_0_92.json
python main.py transport-controls --config configs\long_validation_peak_0_92.json --boundary-only --boundary-match-mode work_per_length --grid-size 81
python main.py breathing-period-audit --control-root runs\source_normalized_resolution_20260616_233009
python main.py dt-control --config configs\long_validation_peak_0_92.json
python main.py artifact-controls --config configs\long_validation_peak_0_92.json
python -m unittest discover -s tests
```
