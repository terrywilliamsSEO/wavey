# WaveEngine / wavey

WaveEngine, repo name `wavey`, is a simulation-first wave simulation engine for a 2D lattice wave system with a configurable central defect or cavity. It computes the lattice dynamics directly, logs localization metrics every sampled step, ranks unusual runs, and saves evidence files under `runs/`.

There is no dashboard yet. The current project is focused on the physics engine, metrics, parameter sweeps, and evidence export.

Project direction is tracked in [ROADMAP.md](ROADMAP.md).

For future agents or contributors, start with [AGENTS.md](AGENTS.md), then read [docs/project_state.md](docs/project_state.md) and [docs/architecture.md](docs/architecture.md). These files summarize the current experimental state, architecture, and documentation-update contract so the project can be resumed without replaying the whole chat history.

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Run a sweep

```powershell
python main.py sweep
```

The default sweep scans drive frequency, drive amplitude, defect radius, defect stiffness, defect damping, defect coupling, global damping, coupling strength, nonlinear strength, boundary mode, and boundary phase mode. It uses a compact one-factor scan around a baseline, then fills any remaining run budget with deterministic sampled combinations.

Useful shorter verification run:

```powershell
python main.py sweep --max-runs 4 --steps 250 --grid-size 35
```

Sampling modes are available with `--sampling-mode hybrid`, `random`, `stratified`, or `grid`. The default `hybrid` mode does a baseline plus one-factor scans, then fills remaining slots with seeded random combinations.

Run a broader seeded random probe with:

```powershell
python main.py sweep --sweep-config configs\random_probe_sweep.json
```

Run an evidence-focused probe with top-candidate frame export:

```powershell
python main.py sweep --sweep-config configs\evidence_probe_sweep.json
```

Refine around the current frequency-threshold candidate with:

```powershell
python main.py sweep --sweep-config configs\frequency_refinement_sweep.json
```

Characterize the narrower response band with:

```powershell
python main.py sweep --sweep-config configs\frequency_band_characterization_sweep.json
```

Run the long 0.92 validation and mode-shape diagnostics with:

```powershell
python main.py diagnose-run --config configs\long_validation_peak_0_92.json
```

To add diagnostics to an existing run directory instead of running it again:

```powershell
python main.py diagnose-run --run-path runs\run_YYYYMMDD_HHMMSS_xxxxxx --reference-root runs
```

Diagnostic frame arrays are saved as numeric `.npy` files by default. Add `--save-frame-pngs` only when you also want every captured energy/displacement frame rendered as an image.

The time-resolved breathing detector reports raw diagnostic-frame peak periods separately from hardened envelope-scale periods. Classification uses retained post-cutoff energy, smoothed/full-metric envelope peaks, minimum peak separation, and prominence filtering; reports flag `subpeak_overcounting_possible` when tiny local peaks would otherwise overstate the breathing rate.

Run targeted sponge-boundary artifact controls for the long 0.92 candidate with:

```powershell
python main.py artifact-controls --config configs\long_validation_peak_0_92.json
```

This runs the original config, stronger sponge damping, wider sponge boundary, and stronger+wider sponge boundary. It does not launch a broader sweep.

Run the smaller-time-step numerical control with:

```powershell
python main.py dt-control --config configs\long_validation_peak_0_92.json
```

This reruns the long 0.92 case at the baseline `dt` and half `dt` with the same physical duration and drive cutoff time, then compares the same mode-shape diagnostics plus absolute energy and post-cutoff decay metrics.

Run the larger-grid matched-proportion control with:

```powershell
python main.py grid-control --config configs\long_validation_peak_0_92.json
```

If the larger-grid best event lands too close to the end of the run, extend only the larger-grid variant:

```powershell
python main.py grid-control --config configs\long_validation_peak_0_92.json --larger-physical-duration 86
```

This scales the grid, defect radius, and sponge width together, then compares the same diagnostics plus absolute energy, core fraction, and per-cell energy density. It is a historical matched-proportion check that intentionally confounds grid size with physical domain size; prefer fixed-domain controls for true resolution tests.

Run the fixed-domain grid-refinement control with:

```powershell
python main.py fixed-domain-grid-control --config configs\long_validation_peak_0_92.json
```

Optionally include an 81x81 same-domain refinement:

```powershell
python main.py fixed-domain-grid-control --config configs\long_validation_peak_0_92.json --include-81
```

This enables fixed-domain physics for the control variants, keeps the physical domain size, defect radius, sponge width, and emitter strip width fixed, scales the coupling operator by `1/dx^2` and `1/dy^2`, records dt stability guidance, and compares best frames after resampling to a common physical grid.

Run fixed-domain resolution-sensitivity diagnostics with:

```powershell
python main.py resolution-diagnostics --config configs\long_validation_peak_0_92.json
```

This reruns the 41x41, 63x63, and 81x81 same-domain variants, then audits source normalization, mask/area equivalence, energy budgets, radial profiles, and pairwise mode-shape similarity before any broad long sweeps.

Run source-normalized fixed-domain resolution diagnostics with:

```powershell
python main.py source-normalized-resolution-diagnostics --config configs\long_validation_peak_0_92.json
```

This uses fractional fixed-domain emitter coverage plus calibrated `constant_total_work` source normalization for the main 41x41, 63x63, and 81x81 variants, and includes legacy `per_cell` variants as reference-only comparisons.

Audit breathing-period peak picking for completed diagnostic runs with:

```powershell
python main.py breathing-period-audit --control-root runs\source_normalized_resolution_YYYYMMDD_HHMMSS
```

This reads existing `metrics.csv` and `mode_shape_diagnostics/frame_mode_diagnostics.csv` files, compares the current diagnostic-frame period against full-resolution metric peaks, and reports whether short periods are caused by local subpeak overcounting.

Run the controlled core-modal probe with:

```powershell
python main.py core-modal-probe --config configs\long_validation_peak_0_92.json
```

This reruns the source-normalized fixed-domain 63x63 and 81x81 boundary references, then runs work-normalized direct core impulse and core burst probes. It logs boundary-drive work and core-drive work separately, uses post-cutoff-only best events, applies minimum-separated full-metric breathing checks, and writes a combined classification report.

Run targeted source-geometry transport controls with:

```powershell
python main.py transport-controls --config configs\long_validation_peak_0_92.json
```

This runs a source-normalized 63x63 boundary reference plus matched-work boundary-geometry and annulus/near-defect source variants. It tests one-side versus symmetric boundary drive, rotating boundary phase, inner-ring/interface drive, near-defect annulus drive, radial-peak annulus drive, one-sided annulus sector drive, and rotating annulus phase before any broad long sweeps.

Run the same transport-control plan at a refined fixed-domain grid with:

```powershell
python main.py transport-controls --config configs\long_validation_peak_0_92.json --grid-size 81
```

Run boundary-only transport controls with matched work per physical boundary length using:

```powershell
python main.py transport-controls --config configs\long_validation_peak_0_92.json --boundary-only --boundary-match-mode work_per_length --grid-size 81
```

Run the tiny 31^3 3D shell-breathing prototype with:

```powershell
python main.py prototype-3d --config configs\long_validation_peak_0_92.json
```

This is not a general 3D engine. It is a small fixed-domain prototype that tests whether matched boundary-flux waves can organize around a spherical defect and produce retained post-cutoff shell breathing. Success is judged by retained shell energy, shell/radial breathing, shell peak stability, source-geometry similarity, direct core/shell controls, and sponge/dt checks, not by high core energy alone.

## Run one simulation

```powershell
python main.py run --steps 900 --grid-size 49
```

You can provide a JSON config:

```powershell
python main.py run --config path\to\config.json
```

Repeatable configs are available in `configs/`:

```powershell
python main.py run --config configs\control_no_drive.json
python main.py run --config configs\baseline_uniform_defect.json
python main.py run --config configs\baseline_uniform_defect_sponge.json
python main.py run --config configs\rotating_phase_probe.json
```

Boundary behavior can also be overridden from the CLI:

```powershell
python main.py run --boundary-mode sponge --boundary-damping-width 6 --boundary-damping-strength 0.08
```

Run the boundary A/B sweep with:

```powershell
python main.py sweep --sweep-config configs\boundary_ab_sweep.json
```

Run a nonlinear amplitude-threshold probe with:

```powershell
python main.py sweep --sweep-config configs\nonlinear_threshold_probe_sweep.json
```

## Validation

Run the validation suite with:

```powershell
python -m unittest discover -s tests
```

Calibration notes live in [docs/calibration.md](docs/calibration.md).

## Outputs

Each run is saved in:

```text
runs/run_or_sweep_id/
```

Each run folder contains:

- `config.json`
- `metrics.csv`
- `summary.json`
- `best_energy_density.npy`
- `final_heatmap.png`
- `best_frame.png`
- `energy_well_ratio_plot.png`
- `core_vs_outer_energy_plot.png`
- `core_spectrum_plot.png`

When frame-sequence export is enabled for a sweep, top candidates also include:

- `frame_sequence/frame_000.png`, `frame_001.png`, and so on

Sweep-level ranking is also saved as `runs/sweep_YYYYMMDD_HHMMSS_summary.json`.

Sweeps also write:

- `sweep_YYYYMMDD_HHMMSS_plan.json`, the exact sampled parameter points
- `sweep_YYYYMMDD_HHMMSS_report.md`, a compact Markdown report linking top-run evidence

When `diagnose-run` is used, the run also includes `mode_shape_diagnostics/` with:

- `frame_mode_diagnostics.csv`
- `frame_correlation_plot.png`
- `radial_profile_timeseries.csv`
- `radial_peak_drift_plot.png`
- `radial_profile_heatmap.png`
- `angular_mode_timeseries.csv`
- `angular_mode_plot.png`
- optional `reference_mode_comparison.csv` and `reference_mode_comparison_plot.png`
- `mode_shape_diagnostics_report.md`

When `artifact-controls` is used, the control folder includes:

- `artifact_control_summary.csv`
- `artifact_control_summary.json`
- `artifact_control_report.md`
- one diagnosed run folder per control variant

When `dt-control` is used, the control folder includes:

- `dt_control_summary.csv`
- `dt_control_summary.json`
- `dt_control_report.md`
- one diagnosed run folder per time-step variant

When `grid-control` is used, the control folder includes:

- `grid_control_summary.csv`
- `grid_control_summary.json`
- `grid_control_report.md`
- one diagnosed run folder per grid variant

When `fixed-domain-grid-control` is used, the control folder includes:

- `fixed_domain_grid_control_summary.csv`
- `fixed_domain_grid_control_summary.json`
- `fixed_domain_grid_control_report.md`
- one diagnosed run folder per fixed-domain grid variant

When `resolution-diagnostics` is used, the diagnostic folder includes:

- `resolution_diagnostics_summary.csv`
- `resolution_diagnostics_summary.json`
- `source_audit.csv`
- `mask_area_audit.csv`
- `energy_budget_audit.csv`
- `radial_profile_comparison.csv`
- `resolution_diagnostics_report.md`
- one diagnosed run folder per fixed-domain grid variant

When `source-normalized-resolution-diagnostics` is used, the diagnostic folder includes:

- `source_normalized_resolution_summary.csv`
- `source_normalized_resolution_summary.json`
- `source_audit_comparison.csv`
- `injected_work_comparison.csv`
- `mask_area_audit.csv`
- `energy_budget_audit.csv`
- `radial_profile_comparison.csv`
- `source_normalized_resolution_report.md`
- diagnosed source-normalized run folders plus legacy `per_cell` reference run folders

When `breathing-period-audit` is used, the output folder includes:

- `breathing_period_audit_summary.csv`
- `breathing_period_peak_times.csv`
- `breathing_period_audit_report.md`

When `core-modal-probe` is used, the probe folder includes:

- `core_modal_probe_summary.csv`
- `core_modal_probe_summary.json`
- `core_modal_probe_report.md`
- `core_modal_probe_comparison_plots/`
- one diagnosed run folder per boundary/core probe variant

Each core-modal run folder also includes:

- `injected_work_plot.png`
- `post_cutoff_decay_plot.png`
- the normal run plots and `mode_shape_diagnostics/` artifacts

When `transport-controls` is used, the control folder includes:

- `transport_control_summary.csv`
- `transport_control_summary.json`
- `transport_control_report.md`
- `transport_control_comparison_plots/`
- one diagnosed run folder per source-geometry variant

When `prototype-3d` is used, the prototype folder includes:

- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- `prototype_3d_report.md`
- one run folder per 3D variant with `metrics.csv`, `radial_profile_timeseries.csv`, shell/energy plots, midplane images, and saved energy arrays

## Metrics

`metrics.csv` records:

- time
- core energy
- outer lattice energy
- total energy
- energy well ratio
- max amplitude and location
- localization index, implemented as a normalized inverse participation ratio
- spatial entropy and participation fraction
- post-cutoff core retention
- Q-like decay estimate
- spectral peak frequency in the core
- additional ring and angular-energy diagnostics used for event detection

## Detection and ranking

`summary.json` includes:

- best energy well ratio
- time of best event
- retention score
- localization score
- anomaly score
- detected event labels
- plain-language interpretation

The anomaly score combines high energy-well ratio, post-drive retention, localization index, central amplitude dominance, spectral purity, breathing behavior, ring formation, rotating-energy signature, within-run nonlinear jumps, and cross-run threshold jumps across neighboring amplitude or frequency sweep runs.

The engine does not hard-code interesting results. Event labels and scores are computed from the simulated lattice state and saved metrics.
