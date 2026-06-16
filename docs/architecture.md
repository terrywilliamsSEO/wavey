# Architecture Notes

Last updated: 2026-06-16

## Entry Point

`main.py` defines the CLI. Current important commands:

- `run`: one simulation.
- `sweep`: parameter sweep.
- `diagnose-run`: mode-shape diagnostics for one run.
- `artifact-controls`: targeted sponge-boundary controls.
- `dt-control`: targeted smaller-time-step controls.
- `grid-control`: larger matched-proportion grid control.
- `fixed-domain-grid-control`: true same-domain grid-refinement control.
- `resolution-diagnostics`: fixed-domain source, mask, energy-budget, radial-profile, and mode-shape resolution audit.

## Core Modules

- `simulation/config.py`: dataclasses for simulation, sweep, defect, and driver config. Also owns fixed-domain helpers: `nx`, `ny`, `dx`, `dy`, physical radii, cell area, and shape.
- `simulation/lattice.py`: 2D oscillator lattice, masks, sponge damping, coupling force, semi-implicit Euler step, and energy density.
- `simulation/drivers.py`: boundary emitter masks and phase maps.
- `simulation/metrics.py`: per-step metrics and post-hoc spectral/retention estimates.
- `simulation/anomaly_detection.py`: run-level summary and event labels.
- `simulation/mode_diagnostics.py`: radial profiles, shape correlations, spatial distribution metrics.
- `simulation/time_resolved_diagnostics.py`: diagnostic frame capture, radial/angular diagnostics, reports, and plots.
- `simulation/control_metrics.py`: absolute energy, decay rate, and post-cutoff core-peak metrics shared by controls.
- `simulation/artifact_controls.py`: sponge-boundary artifact controls.
- `simulation/numerical_controls.py`: smaller-dt controls.
- `simulation/grid_controls.py`: matched-proportion larger-grid controls.
- `simulation/fixed_domain_controls.py`: same-domain grid-refinement controls with best-frame resampling.
- `simulation/resolution_diagnostics.py`: fixed-domain resolution-sensitivity audits for source normalization, mask areas, energy budgets, radial profiles, and pairwise best-frame/mode-shape similarity.
- `simulation/stability.py`: conservative dt guidance for current `dx`/`dy`.
- `simulation/reporting.py` and `simulation/band_analysis.py`: sweep-level reporting and frequency-band analysis.

## Fixed-Domain Semantics

Fixed-domain mode is opt-in with `fixed_domain: true`.

When enabled:

- `dx = domain_width / (nx - 1)`
- `dy = domain_height / (ny - 1)`
- Defect radius can be specified as `defect.radius_physical`.
- Core radius can be specified as `core_radius_physical`.
- Sponge width can be specified as `boundary_damping_width_physical`.
- Emitter strip width can be specified as `driver.emitter_width_physical`.
- Lattice coupling force scales by `1/dx^2` and `1/dy^2`.
- Energy density integrates onsite/kinetic/nonlinear/coupling contributions with cell area.
- Masks, sponge damping, phase maps, radial profiles, annulus masks, and angular masks use physical distances.
- Time-resolved radial diagnostics report physical radii.

Historical non-fixed-domain configs still work and retain cell-unit semantics.

## Validation Controls

Targeted controls are intentionally narrow. They run one candidate through a small number of variants, generate the normal run artifacts, then generate mode-shape diagnostics and a combined report.

Controls should be preferred over broad sweeps while validating one candidate:

- Use `artifact-controls` to test boundary absorption.
- Use `dt-control` to test time-step sensitivity.
- Use `grid-control` only for historical matched-proportion domain scaling.
- Use `fixed-domain-grid-control` for true resolution checks.
- Use `resolution-diagnostics` when a fixed-domain resolution check changes radial structure, retention, timing, or source/mask comparability.

Current fixed-domain caution: `resolution-diagnostics` found the 0.92 candidate's emitter/source mask area is not physically invariant across 41/63/81 grids. Fix or control emitter/source discretization before broad long sweeps.

## Generated Artifacts

Run artifacts live in `runs/` and are ignored by Git except `runs/.gitkeep`.

Each important run/control result must be summarized in `ROADMAP.md` and `docs/project_state.md`, because future agents may not have local run artifacts after cloning.

## Test Suite

Main validation command:

```powershell
python -m unittest discover -s tests
```

The suite includes lattice sanity, config/export schema, sweep behavior, time-resolved diagnostics, and classification logic for all targeted controls.
