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

Audit a completed 3D prototype for near-defect shell transport, global radial-peak bias, and source/sponge overlap with:

```powershell
python main.py prototype-3d-audit --run-path runs\prototype_3d_YYYYMMDD_HHMMSS --config configs\long_validation_peak_0_92.json
```

This is read-only with respect to the simulation itself: it consumes the saved prototype profiles and writes a failure-mode audit under the existing prototype run folder.

Run the tiny 31^3 source/sponge separation control with:

```powershell
python main.py prototype-3d-source-sponge-control --config configs\long_validation_peak_0_92.json
```

This keeps injected work matched per physical source area across source-placement variants and judges success using near-defect shell-window metrics, not the global shell peak alone.

Run the tiny 31^3 sponge-strength control for the best separated source geometry with:

```powershell
python main.py prototype-3d-sponge-strength-control --config configs\long_validation_peak_0_92.json
```

This keeps the source at the original inner-sponge-edge location, matches injected work per physical source area, and varies only weak, baseline, stronger, wider, and stronger+wider sponge settings.

Run the tiny 31^3 source-geometry control from the stronger-sponge inner-edge setup with:

```powershell
python main.py prototype-3d-source-geometry-control --config configs\long_validation_peak_0_92.json
```

This tests six-face uniform, one-face, two-opposite-face, four-side-face, six-face cubic phase, phased-opposite-face, and random-phase boundary sources, plus direct core/shell comparators, all at matched injected work.

Run the tiny 31^3 focused six-face cubic control with:

```powershell
python main.py prototype-3d-cubic-focus-control --config configs\long_validation_peak_0_92.json
```

This repeats the six-face cubic source, flips the cubic phase sign, applies a global phase offset, removes one face, slightly imbalances face amplitudes, compares uniform six-face coverage, repeats a fixed-seed random phase, and keeps direct core/shell controls as reference-only comparators.

Run the tiny 31^3 cubic dt/sponge confirmation with:

```powershell
python main.py prototype-3d-cubic-confirmation-control --config configs\long_validation_peak_0_92.json
```

This confirms the original cubic and sign-flipped cubic boundary phases with deterministic repeats, half-dt variants, stronger/weaker sponge variants around the current stronger-sponge baseline, one sign-flip amplitude-reduced probe, and direct core/shell reference controls.

Run the tiny fixed-domain 31^3 to 41^3 3D grid confirmation with:

```powershell
python main.py prototype-3d-grid-confirmation-control --config configs\long_validation_peak_0_92.json
```

This is a single-candidate resolution lift, not a 3D sweep. It compares the 31^3 sign-flipped cubic stronger-sponge reference with a 41^3 sign-flipped cubic candidate, an optional 41^3 original-cubic comparator, and one 41^3 negative control under matched physical domain, defect, source geometry, sponge settings, and injected work per physical source area.

Run the tiny calibrated 41^3 amplitude/phase threshold check with:

```powershell
python main.py prototype-3d-threshold-control --config configs\long_validation_peak_0_92.json
```

This is also not a 3D sweep. It starts from the calibrated 41^3 sign-flipped cubic stronger-sponge source, tests only a small set of amplitude multipliers and global phase offsets, and keeps direct core/shell controls as transient reference checks.

Run the tiny calibrated 41^3 defect-dependence check with:

```powershell
python main.py prototype-3d-defect-control --config configs\long_validation_peak_0_92.json
```

This checks whether the retained near-shell tail requires the spherical defect. It keeps the calibrated sign-flipped cubic stronger-sponge source fixed, matches work per physical source area, compares neutral and partially neutralized defect variants, and reports a fixed physical near-shell window anchored to the original defect radius.

Run the tiny 41^3 radial-window neutral-lattice audit with:

```powershell
python main.py prototype-3d-radial-window-audit --config configs\long_validation_peak_0_92.json
```

This reruns only the current-defect and neutral-lattice sign-flip cases, scans fixed shell windows at selected radii, and reports defect-lift ratios, radial-profile correlations, shell stability, arrival times, and frame similarity.

Run the tiny 41^3 stronger/different-defect lift sweep with:

```powershell
python main.py prototype-3d-defect-lift-sweep --config configs\long_validation_peak_0_92.json
```

This keeps the calibrated sign-flipped cubic stronger-sponge source fixed, uses the neutral lattice as the baseline, varies only hand-picked defect parameters, and requires strict lift in both retention and peak/work before calling a defect effect. If it finds no lift, the 3D interpretation should pivot toward structured boundary transport modes.

Run the tiny neutral-lattice 3D interference diagnostic with:

```powershell
python main.py prototype-3d-interference-diagnostics --config configs\long_validation_peak_0_92.json
```

This keeps the 41^3 neutral-lattice sign-flipped cubic stronger-sponge setup fixed, matches work per physical source area, and compares cubic phase with same-coverage uniform, cubic phase-offset, and deterministic per-cell random phase controls. It exports phase coherence, constructive/destructive alignment, modal projection proxies, wavefront timing, randomization controls, and standing-shell persistence diagnostics.

Run the tiny neutral-lattice 3D standing-shell persistence check with:

```powershell
python main.py prototype-3d-standing-persistence --config configs\long_validation_peak_0_92.json
```

This reruns only the two clean cubic variants, sign-flipped cubic and cubic phase-offset, with dense settled post-cutoff shell-window diagnostics. It measures node/antinode stability, radial shell phase stability, shell energy autocorrelation, frame-to-frame and frame-to-mean shell similarity, spectral concentration, and a settled standing score after transients have had time to clear.

Run the tiny neutral-lattice 3D transport-packet audit with:

```powershell
python main.py prototype-3d-transport-packet-audit --config configs\long_validation_peak_0_92.json
```

This reruns the same two clean cubic variants and asks whether the shell-window tail is a moving wavefront / transport packet or a slowly drifting modal structure. It exports shell-window phase velocity, radial group velocity, angular drift, time-of-flight, inward/outward radial flux, centroid-displacement motion proxies, shell exit timing, and time-lagged shell-pattern correlations.

Run the extended 3D packet lifecycle audit with:

```powershell
python main.py prototype-3d-packet-lifecycle-audit --config configs\long_validation_peak_0_92.json
```

This extends the clean cubic packet run while preserving the drive cutoff. It tracks packet radius, radial spread/width, shell-window energy peaks, shell exit timing, inward/outward flux balance, and post-cutoff shell decay to decide whether the packet simply passes through, diffuses, stalls, or repeatedly refocuses near the target shell window.

Run the tiny 3D refocusing-engineering control with:

```powershell
python main.py prototype-3d-refocusing-engineering-control --config configs\long_validation_peak_0_92.json
```

This keeps the validated 41^3 neutral-lattice cubic packet setup fixed, matches work per physical source area, and varies only small source-shaping axes: cubic phase offset, cutoff timing, drive frequency, and an optional low-to-high chirp. It scores refocus peak count, refocus ratio, shell exit time, tail retention, shell peak/work, outer/shell residue, global outer-window flags, inward/outward flux balance, and post-cutoff decay.

Run the tiny 3D cutoff-frequency refocusing map with:

```powershell
python main.py prototype-3d-refocusing-map-control --config configs\long_validation_peak_0_92.json
```

This is a two-knob local map, not a broad sweep. It keeps the 41^3 neutral-lattice cubic packet setup fixed and compares `cutoff_long`, `frequency_high`, their combined setting, and a few nearby cutoff/frequency neighbors under matched work per physical source area.

Run the tiny 3D cutoff release-phase timing map with:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json
```

This keeps frequency fixed and asks whether refocusing quality clusters around source release timing. It varies cutoff time near the winning cutoff, small global phase-offset perturbations at the winning cutoff, and a compact sign-flip/polarity family while reporting phase at cutoff.

Run the tighter cutoff/polarity timing check with:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --cutoff-offsets -0.2 -0.1 0 0.1 0.2 --phase-offset-deltas 0 --polarity-cutoff-offsets -0.2 -0.1 0 0.1 0.2
```

This compares cutoff times `17.8`, `17.9`, `18.0`, `18.1`, and `18.2` for both `phase_offset` and `sign_flip` families. The report ranks rows by refocus peaks, no shell exit, retention, outer/shell below `1.0`, decay rate closest to zero, and global outer false.

Run the tiny 3D second-pulse control with:

```powershell
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json
```

This starts from the best sign-flip release phase, reads refocus times from the cutoff-phase events CSV, and compares no second pulse, first-refocus timing, preload timing, second-refocus timing, opposite-polarity, phase-matched, phase-offset, and passive-extension variants. Use `--second-pulse-amplitude-scale` or `--second-pulse-duration` for a single reduced-work follow-up. Current project state: active second-pulse controls are reference/historical only, because full-amplitude, reduced-work, first-refocus travel-time, and second-refocus travel-time variants all failed strict clean-refocus criteria.

Run a reduced-work second-pulse map with:

```powershell
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-amplitude-scales 0.1 0.2 0.35 0.5 --second-pulse-durations 2.0 1.0 --second-pulse-roles phase_matched
```

The multi-value options create a compact map over selected second-pulse roles, amplitudes, and durations. The ranked report includes `clean_refocus_score` and `added_work_efficiency`, where added-work efficiency measures the clean-score improvement per unit of second-pulse work.

Run a travel-time-adjusted second-pulse timing/phase micro-map with:

```powershell
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-micro-map --micro-map-targets first_refocus --launch-time-offsets -0.8 -0.4 0 0.4 0.8 --second-pulse-phase-modes matched opposite plus_pi_4 minus_pi_4 --second-pulse-amplitude-scales 0.1 0.2
```

Micro-map mode first runs the no-pulse reference, writes `second_pulse_timing_audit.csv`, estimates boundary-to-shell travel time from the reference arrival, then launches second pulses at `target_peak_time - travel_time + offset`.

The completed second-refocus reference micro-map used:

```powershell
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-micro-map --micro-map-targets second_refocus --launch-time-offsets -0.8 -0.4 0 0.4 0.8 --second-pulse-phase-modes matched opposite plus_pi_4 minus_pi_4 --second-pulse-amplitude-scales 0.1 0.2
```

It did not beat the no-pulse reference; return to passive release-phase/cutoff engineering before revisiting active reinjection.

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

When `prototype-3d-audit` is used, the prototype folder also includes `failure_mode_audit/` with:

- `prototype_3d_failure_audit_summary.csv`
- `prototype_3d_geometry_audit.csv`
- `prototype_3d_shell_window_timeseries.csv`
- `prototype_3d_radial_snapshots.csv`
- `prototype_3d_failure_audit_report.md`

When `prototype-3d-source-sponge-control` is used, the control folder includes:

- `source_sponge_control_summary.csv`
- `source_sponge_control_summary.json`
- `source_sponge_control_report.md`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per source-placement variant
- `failure_mode_audit/` with the near-defect shell-window audit artifacts

When `prototype-3d-sponge-strength-control` is used, the control folder includes:

- `sponge_strength_control_summary.csv`
- `sponge_strength_control_summary.json`
- `sponge_strength_control_report.md`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per sponge-strength/width variant
- `failure_mode_audit/` with the near-defect shell-window audit artifacts

When `prototype-3d-source-geometry-control` is used, the control folder includes:

- `source_geometry_control_summary.csv`
- `source_geometry_control_summary.json`
- `source_geometry_control_report.md`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per source-geometry variant
- `failure_mode_audit/` with the near-defect shell-window audit artifacts

When `prototype-3d-cubic-focus-control` is used, the control folder includes:

- `cubic_focus_control_summary.csv`
- `cubic_focus_control_summary.json`
- `cubic_focus_control_report.md`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per cubic-focus variant
- `failure_mode_audit/` with the near-defect shell-window audit artifacts

When `prototype-3d-cubic-confirmation-control` is used, the control folder includes:

- `cubic_confirmation_control_summary.csv`
- `cubic_confirmation_control_summary.json`
- `cubic_confirmation_control_report.md`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per cubic-confirmation variant
- `failure_mode_audit/` with the near-defect shell-window audit artifacts

When `prototype-3d-grid-confirmation-control` is used, the control folder includes:

- `grid_confirmation_3d_summary.csv`
- `grid_confirmation_3d_summary.json`
- `grid_confirmation_3d_report.md`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per grid-confirmation variant
- `failure_mode_audit/` with the near-defect shell-window audit artifacts

When `prototype-3d-threshold-control` is used, the control folder includes:

- `threshold_control_3d_summary.csv`
- `threshold_control_3d_summary.json`
- `threshold_control_3d_report.md`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per threshold-control variant
- `failure_mode_audit/` with the near-defect shell-window audit artifacts

When `prototype-3d-defect-control` is used, the control folder includes:

- `defect_control_3d_summary.csv`
- `defect_control_3d_summary.json`
- `defect_control_3d_report.md`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per defect-control variant
- `failure_mode_audit/` with the variant-relative shell-window audit artifacts

When `prototype-3d-radial-window-audit` is used, the control folder includes:

- `radial_window_audit_3d_summary.csv`
- `radial_window_audit_3d_summary.json`
- `radial_window_comparison.csv`
- `radial_window_variant_metrics.csv`
- `radial_window_profile_comparison.csv`
- `radial_window_audit_3d_report.md`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per radial-window variant
- `failure_mode_audit/` with the variant-relative shell-window audit artifacts

When `prototype-3d-defect-lift-sweep` is used, the control folder includes:

- `defect_lift_sweep_summary.csv`
- `defect_lift_sweep_3d_summary.json`
- `defect_lift_sweep_3d_report.md`
- `defect_lift_window_comparison.csv`
- `defect_lift_profile_comparison.csv`
- `defect_lift_variant_window_metrics.csv`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per defect-lift variant
- `failure_mode_audit/` with the variant-relative shell-window audit artifacts

When `prototype-3d-interference-diagnostics` is used, the control folder includes:

- `interference_diagnostics_summary.csv`
- `interference_diagnostics_3d_summary.json`
- `interference_diagnostics_3d_report.md`
- `phase_coherence_timeseries.csv`
- `modal_projection_timeseries.csv`
- `wavefront_timeseries.csv`
- `phase_coherence_plot.png`
- `modal_projection_plot.png`
- `wavefront_shell_energy_plot.png`
- `interference_diagnostics/<variant>/phase_alignment_midplane.png`
- `interference_diagnostics/<variant>/shell_energy_midplane.png`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per phase-control variant
- `failure_mode_audit/` with the variant-relative shell-window audit artifacts

When `prototype-3d-standing-persistence` is used, the control folder includes:

- `standing_persistence_summary.csv`
- `standing_persistence_3d_summary.json`
- `standing_persistence_3d_report.md`
- `standing_persistence_timeseries.csv`
- `shell_energy_autocorrelation.csv`
- `shell_pattern_similarity_plot.png`
- `shell_phase_stability_plot.png`
- `shell_energy_autocorrelation_plot.png`
- `standing_persistence/<variant>/mean_shell_pattern.png`
- `standing_persistence/<variant>/antinode_mask.png`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per clean cubic variant
- `failure_mode_audit/` with the variant-relative shell-window audit artifacts

When `prototype-3d-transport-packet-audit` is used, the control folder includes:

- `transport_packet_summary.csv`
- `transport_packet_3d_summary.json`
- `transport_packet_3d_report.md`
- `transport_packet_timeseries.csv`
- `packet_lag_correlation.csv`
- `shell_energy_and_flux_plot.png`
- `radial_motion_plot.png`
- `phase_angular_drift_plot.png`
- `packet_lag_correlation_plot.png`
- `transport_packet/<variant>/shell_centroid_path.png`
- `prototype_3d_summary.csv`
- `prototype_3d_summary.json`
- one run folder per clean cubic variant
- `failure_mode_audit/` with the variant-relative shell-window audit artifacts

When `prototype-3d-packet-lifecycle-audit` is used, the control folder includes:

- `packet_lifecycle_summary.csv`
- `packet_lifecycle_3d_summary.json`
- `packet_lifecycle_3d_report.md`
- `packet_lifecycle_timeseries.csv`
- `packet_lifecycle_events.csv`
- `shell_energy_lifecycle_plot.png`
- `packet_radius_width_plot.png`
- `radial_flux_balance_plot.png`
- one lifecycle timeseries/event CSV pair per clean cubic variant

When `prototype-3d-refocusing-engineering-control` is used, the control folder includes:

- `refocusing_engineering_summary.csv`
- `refocusing_engineering_3d_summary.json`
- `refocusing_engineering_3d_report.md`
- `refocusing_engineering_timeseries.csv`
- `refocusing_engineering_events.csv`
- `refocusing_shell_energy_plot.png`
- `refocusing_radius_width_plot.png`
- `refocusing_flux_balance_plot.png`
- one lifecycle run folder per tiny source-shaping variant

When `prototype-3d-refocusing-map-control` is used, the control folder includes:

- `refocusing_map_summary.csv`
- `refocusing_map_3d_summary.json`
- `refocusing_map_3d_report.md`
- `refocusing_map_timeseries.csv`
- `refocusing_map_events.csv`
- `refocusing_map_shell_energy_plot.png`
- `refocusing_map_radius_width_plot.png`
- `refocusing_map_flux_balance_plot.png`
- one lifecycle run folder per cutoff/frequency map variant

When `prototype-3d-cutoff-phase-map-control` is used, the control folder includes:

- `cutoff_phase_map_summary.csv`
- `cutoff_phase_ranked_summary.csv`
- `cutoff_phase_map_3d_summary.json`
- `cutoff_phase_map_3d_report.md`
- `cutoff_phase_map_timeseries.csv`
- `cutoff_phase_map_events.csv`
- `cutoff_phase_shell_energy_plot.png`
- `cutoff_phase_radius_width_plot.png`
- `cutoff_phase_flux_balance_plot.png`
- one lifecycle run folder per cutoff/phase/polarity timing variant

When `prototype-3d-second-pulse-control` is used, the control folder includes:

- `second_pulse_summary.csv`
- `second_pulse_ranked_summary.csv`
- `second_pulse_3d_summary.json`
- `second_pulse_report.md`
- `second_pulse_timeseries.csv`
- `second_pulse_events.csv`
- `second_pulse_timing_audit.csv`
- `second_pulse_shell_energy_plot.png`
- `second_pulse_radius_width_plot.png`
- `second_pulse_flux_balance_plot.png`
- one lifecycle run folder per second-pulse timing/phase variant

The second-pulse summary and ranked CSV include active-pulse work accounting plus `clean_refocus_score`, `clean_refocus_score_delta`, and `added_work_efficiency` for comparing second pulses against the no-pulse reference without rewarding extra injected work by itself.

`second_pulse_timing_audit.csv` is especially useful for active-pulse work. It records no-pulse shell peak times, radial flux direction, packet motion proxy, local shell phase, estimated boundary-to-shell travel time, ideal launch time, and source phase at launch.

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
