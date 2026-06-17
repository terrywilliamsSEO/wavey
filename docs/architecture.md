# Architecture Notes

Last updated: 2026-06-17

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
- `source-normalized-resolution-diagnostics`: source-normalized fixed-domain resolution audit with legacy `per_cell` reference variants.
- `breathing-period-audit`: read-only peak-picking audit for completed diagnostic runs.
- `core-modal-probe`: controlled source-normalized fixed-domain boundary references plus direct core excitation probes.
- `transport-controls`: targeted matched-work boundary-geometry and annulus/near-defect source controls.

## Core Modules

- `simulation/config.py`: dataclasses for simulation, sweep, defect, driver config, and direct core-drive options. Also owns fixed-domain helpers: `nx`, `ny`, `dx`, `dy`, physical radii, cell area, and shape.
- `simulation/lattice.py`: 2D oscillator lattice, masks, sponge damping, coupling force, semi-implicit Euler step, energy density, and separate boundary/core external force paths.
- `simulation/drivers.py`: boundary emitter coverage weights, source normalization, masks, phase maps, and direct core/annulus drive masks.
- `simulation/metrics.py`: per-step metrics and post-hoc spectral/retention estimates.
- `simulation/anomaly_detection.py`: run-level summary and event labels.
- `simulation/mode_diagnostics.py`: radial profiles, shape correlations, spatial distribution metrics.
- `simulation/time_resolved_diagnostics.py`: diagnostic frame capture, radial/angular diagnostics, hardened breathing detection, reports, and plots.
- `simulation/breathing_period_audit.py`: compares current diagnostic breathing periods with full-resolution metric peak periods and minimum-separated peak periods.
- `simulation/control_metrics.py`: absolute energy, decay rate, and post-cutoff core-peak metrics shared by controls.
- `simulation/artifact_controls.py`: sponge-boundary artifact controls.
- `simulation/numerical_controls.py`: smaller-dt controls.
- `simulation/grid_controls.py`: matched-proportion larger-grid controls.
- `simulation/fixed_domain_controls.py`: same-domain grid-refinement controls with best-frame resampling.
- `simulation/resolution_diagnostics.py`: fixed-domain resolution-sensitivity audits for source normalization, mask areas, energy budgets, radial profiles, and pairwise best-frame/mode-shape similarity.
- `simulation/core_modal_probe.py`: controlled direct-core modal probe orchestration, separate drive-work accounting, post-cutoff-only summaries, minimum-separated breathing checks, comparison plots, and classification.
- `simulation/transport_controls.py`: narrow source-geometry mechanism controls that compare boundary one-side/two-side/rotating variants with inner-ring, near-defect annulus, radial-peak annulus, sector, and rotating annulus drives under matched injected work.
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
- Fixed-domain emitters support fractional source coverage weights for physically comparable source geometry.
- `driver.source_normalization` supports `per_cell`, `per_length`, `constant_boundary_flux`, and `constant_total_work`.
- `drive_location` supports `boundary`, `core_node`, `core_region`, and `annulus`.
- Direct core drives support `burst`, `impulse`, `chirp`, and `continuous` modes with separate work accounting from boundary drives.
- Direct annulus/core-region drives support physical inner/outer annulus radii, optional angular sectors, and uniform or rotating spatial phase maps.
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
- Use `source-normalized-resolution-diagnostics` after source/mask comparability fails; its main variants use calibrated source-normalized coverage and its legacy `per_cell` variants are reference-only.
- Use `breathing-period-audit` when a diagnostic breathing period appears too short or inconsistent with neighboring controls.
- Use `core-modal-probe` to test whether direct core excitation reproduces the source-normalized fixed-domain boundary-reference tail before any broad long sweeps.
- Use `transport-controls` to test which source geometry excites the retained family after direct core excitation fails.

Current fixed-domain caution: `source-normalized-resolution-diagnostics` fixed emitter geometry/work comparability for the 0.92 candidate and classified the radial result as `coarse_grid_artifact_likely`. The global breathing detector now flags raw subpeak overcounting and reports envelope-scale periods. `core-modal-probe` classified the direct-core test as `boundary_transport_required`. The first `transport-controls` pass classified the candidate as `boundary_geometry_sensitive`: direct annulus/near-defect drives did not reproduce the reference family, while boundary left, left-right, and rotating m=4 variants retained breathing under matched work. Confirm boundary-geometry sensitivity at 81x81 before broad long sweeps.

## Generated Artifacts

Run artifacts live in `runs/` and are ignored by Git except `runs/.gitkeep`.

Each important run/control result must be summarized in `ROADMAP.md` and `docs/project_state.md`, because future agents may not have local run artifacts after cloning.

## Test Suite

Main validation command:

```powershell
python -m unittest discover -s tests
```

The suite includes lattice sanity, config/export schema, sweep behavior, time-resolved diagnostics, and classification logic for all targeted controls.
