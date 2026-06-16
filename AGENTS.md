# Agent Handoff Guide

This file is the first stop for any agent entering the project cold. Keep it short, current, and useful.

## Read Order

1. `README.md` for setup, commands, and output artifacts.
2. `ROADMAP.md` for the current next step and full decision log.
3. `docs/project_state.md` for the latest experimental conclusion and caution flags.
4. `docs/architecture.md` for the code map and physics-mode notes.
5. `docs/calibration.md` for numerical expectations and sanity checks.

## Current Rule Of Engagement

- Do not run broad long sweeps until the fixed-domain resolution sensitivity is understood.
- Treat old pre-fixed-domain results as historical context, not numerically identical baselines.
- The current 0.92 candidate has persistent breathing under multiple controls, but it is fixed-domain resolution-sensitive because radial structure shifts inward at finer grids.
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
python main.py dt-control --config configs\long_validation_peak_0_92.json
python main.py artifact-controls --config configs\long_validation_peak_0_92.json
python -m unittest discover -s tests
```
