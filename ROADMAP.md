# WaveEngine Roadmap

This file is the project roadmap and should be updated whenever we complete a meaningful task, change direction, add a new phase, or discover a better next step.

## Current Next Step

Add targeted annulus / near-defect transport controls before broader long sweeps.

Recommended next task: add a narrow transport-control command or extend `core-modal-probe` with annulus / inner-ring / near-boundary source variants using matched injected work. The hardened global breathing detector now reports raw diagnostic-frame peak periods separately from envelope-scale periods, flags `subpeak_overcounting_possible`, and requires retained post-cutoff energy before applying the `breathing_localized_state` label.

## Status

### Done

- Created a Python CLI project.
- Implemented a real 2D coupled oscillator lattice simulation.
- Added a configurable central defect/cavity.
- Added boundary wave emitters with uniform and rotating phase modes.
- Logged per-step metrics to CSV.
- Exported run evidence to `runs/`.
- Added anomaly detection and sweep ranking.
- Added README setup and usage instructions.
- Established this roadmap as the source of truth for next work.
- Added automated validation tests for lattice dynamics, config parsing, metrics schema, run exports, and sweep ranking.
- Added numerical sanity checks for bounded conservative energy, damped energy loss, and defect property application.
- Added repeatable baseline configs in `configs/`.
- Added calibration notes in `docs/calibration.md`.
- Added optional sponge boundary damping with CLI/config support.
- Added a boundary A/B sweep config in `configs/boundary_ab_sweep.json`.
- Added validation coverage for sponge damping behavior.
- Added cross-run nonlinear threshold detection across paired amplitude/frequency sweep neighbors.
- Added a nonlinear threshold probe sweep config in `configs/nonlinear_threshold_probe_sweep.json`.
- Added validation coverage for cross-run threshold annotations.
- Added seeded sweep sampling modes: `hybrid`, `random`, `stratified`, and `grid`.
- Added sweep plan JSON output with exact sampled parameter points.
- Added compact Markdown sweep reports that link top-run evidence files.
- Added a random probe sweep config in `configs/random_probe_sweep.json`.
- Added core spectrum plots to every run.
- Added optional frame-sequence export for top sweep candidates.
- Added an evidence probe sweep config in `configs/evidence_probe_sweep.json`.
- Added a frequency refinement sweep config in `configs/frequency_refinement_sweep.json`.
- Added a frequency band characterization config in `configs/frequency_band_characterization_sweep.json`.
- Added frequency-band analysis sections to sweep Markdown reports.
- Reviewed the related `QuantumFourier-MAgic-1` prototype and identified portable diagnostics to adapt conceptually, not copy directly.
- Added numeric `best_energy_density.npy` exports for every run.
- Added spatial entropy and participation-fraction metrics to per-sample CSV output.
- Added best-frame spatial/radial concentration metrics to run summaries.
- Added frequency-band mode-shape and radial-profile correlation diagnostics to sweep reports.
- Added dense-frequency threshold downweighting when repeated peak/trough patterns indicate band structure rather than an isolated threshold.
- Added `configs/long_validation_peak_0_92.json` for extended validation of the strongest sampled band peak.
- Ran the 0.90-1.08 band characterization with mode diagnostics; the scan classified as `alternating_frequency_response`, not a clean single-shape structured mode.
- Ran the 0.92 long validation; the candidate strengthened over the longer horizon and showed late-time breathing/localization behavior.
- Added single-run time-resolved mode-shape diagnostics via `python main.py diagnose-run`.
- Added targeted energy/displacement frame array capture around cutoff, best event, post-drive tail, and late decay.
- Added frame-to-frame, best-frame, cutoff-frame, and early-tail shape-correlation exports.
- Added radial profile timeseries, radial peak drift plot, and radial profile heatmap exports.
- Added breathing-state detection, mode-transition candidate detection, angular Fourier diagnostics, and short-sweep reference comparisons.
- Ran diagnostics on the long 0.92 validation run; evidence supports a breathing localized state with angular mode structure and a rotating/angularly shifting tail, while a discrete late-mode-transition label remained inconclusive.
- Added `artifact-controls` for targeted sponge-boundary controls without launching broad sweeps.
- Ran original, stronger sponge, wider sponge, and stronger+wider sponge controls for the long 0.92 case.
- Classified the sponge controls as `sponge_sensitive`: breathing and retention survived, but angular phase organization weakened under stronger/wider absorption.
- Added denominator-aware control metrics for absolute core energy, outer-lattice energy, total energy, core fraction, and post-cutoff decay rates.
- Refreshed sponge controls with absolute-energy reporting; the higher wider-sponge ratios are partly denominator-driven, and the stronger+wider case reduces best-frame core energy substantially.
- Added `dt-control` for targeted smaller-time-step validation without launching a broad sweep.
- Ran baseline `dt=0.04` and half-step `dt=0.02` controls for the long 0.92 case; the result classified as `numerically_stable` with a period-source caveat.
- The half-step control preserved best event time, retention, ratio, absolute core energy, and m=4 angular structure.
- Added `grid-control` for a targeted larger-grid matched-proportion control without launching a broad sweep.
- Ran the initial 41-vs-63 grid control at the original physical duration; the larger-grid best event landed at the run end, so the result was end-limited.
- Reran the 63-grid variant with extended physical duration; breathing localization, retention, ratio, core fraction, normalized core density, and m=4 structure survived, but best-event timing shifted later.
- Added fixed-domain physics semantics with `fixed_domain`, `domain_width`, `domain_height`, `dx`, `dy`, physical defect radius, physical core radius, physical sponge width, and physical emitter width.
- Updated fixed-domain coupling force scaling to use `1/dx^2` and `1/dy^2`, with integrated energy scaled by cell area.
- Added dt stability estimates and warnings to run summaries.
- Updated fixed-domain masks, sponge damping, emitters, radial diagnostics, annulus diagnostics, angular diagnostics, and plots to use physical units.
- Added `fixed-domain-grid-control` for true same-domain resolution controls with best-frame resampling to a common physical grid.
- Ran fixed-domain 41/63/81 controls for the long 0.92 candidate; result classified as `resolution_sensitive`.
- Added repository handoff documentation in `AGENTS.md`, `docs/project_state.md`, and `docs/architecture.md`.
- Configured the local Git branch as `main` and added the private GitHub remote through the dedicated `github-wavey` SSH alias.
- Added `resolution-diagnostics` for fixed-domain source, mask, energy-budget, radial-profile, and pairwise mode-shape audits.
- Ran fixed-domain 41/63/81 resolution diagnostics for the long 0.92 candidate; result classified as `mask_discretization_issue`.
- Found that core/defect masks are comparable, injected work per boundary length is within tolerance, breathing period stays stable, and m=4 remains the strongest angular structure, but emitter mask area varies substantially at 63x63.
- Found a secondary coarse-grid signal: the 63x63 and 81x81 radial peaks agree at 3.75 with best radial correlation 0.964, while 41x41 peaks at 10.0.
- Added fractional fixed-domain source coverage and `source_normalization` modes: `per_cell`, `per_length`, `constant_boundary_flux`, and calibrated `constant_total_work`.
- Added `source-normalized-resolution-diagnostics` with source-normalized 41/63/81 variants and legacy `per_cell` reference variants.
- Ran source-normalized fixed-domain diagnostics for the long 0.92 candidate; result classified as `coarse_grid_artifact_likely`.
- Source-normalized 63/81 converge at physical radial peak 10.0 with best radial correlation 0.965; the 41-grid source-normalized peak is 5.0.
- Source-normalized emitter effective area and injected work are controlled across resolutions; legacy `per_cell` results remain reference-only.
- Added `breathing-period-audit` for completed diagnostic runs.
- Ran the audit on `runs\source_normalized_resolution_20260616_215926`; result classified as `peak_detector_overcounts_subpeaks`.
- The 63-grid diagnostic period of 1.689 comes from counting small local maxima; full-resolution metric peaks with 1.5-2.0 minimum separation estimate 2.49-2.91 instead.
- Added direct core drive support with `drive_location` values `boundary`, `core_node`, `core_region`, and `annulus`.
- Added core-drive options for radius, frequency, amplitude, phase, mode, cutoff time, work normalization target, and work-reference mode.
- Added separate boundary/core injected-work accounting and post-cutoff-only best-event summaries for core-modal probes.
- Added `core-modal-probe` for source-normalized fixed-domain 63/81 boundary references plus work-normalized core impulse and burst controls.
- Ran `core-modal-probe` for the long 0.92 candidate in `runs\core_modal_probe_20260616_230134`; result classified as `boundary_transport_required`.
- The boundary references retained breathing with controlled injected work, but direct core impulse/burst did not reproduce the boundary-reference post-cutoff breathing, radial peak, and m=4 structure.
- Hardened `_detect_breathing_state` globally with full-metric envelope-scale peak detection, minimum peak separation, low-amplitude prominence filtering, smoothing, post-cutoff retention gating, raw/envelope period reporting, and `subpeak_overcounting_possible`.
- Reran source-normalized fixed-domain diagnostics in `runs\source_normalized_resolution_20260616_233009`; classification stayed `coarse_grid_artifact_likely`, and 41/63/81 envelope-scale periods reported as 2.547 / 3.040 / 2.850.
- Refreshed `core-modal-probe` in `runs\core_modal_probe_20260616_233711`; classification stayed `boundary_transport_required`, with combined reports now separating diagnostic envelope period, metric min-separated period, and raw diagnostic-frame period.

### In Progress

- Targeted boundary-transport mechanism controls.

### Next

- Add annulus drive and inner-ring drive variants with matched injected work.
- Add closer-boundary / near-defect source variants to test transport distance.
- Add one-side versus symmetric source variants to test interference geometry.
- Add rotating versus non-rotating phase variants to test whether angular injection seeds m=4.
- Keep the source-normalized 63/81 refined radial convergence as the current cleaner fixed-domain interpretation, with raw subpeak-overcounting flags noted separately from envelope periods.
- Keep the angular/rotating-tail claim provisional because coherent phase trend is sponge-sensitive and direct core excitation did not reproduce the reference m=4 tail.
- Do not run neighboring-frequency long controls until the transport-mechanism controls are understood.

## Phases

### Phase 1: Validation And Calibration

Goal: make the engine trustworthy enough that future anomaly candidates mean something.

Deliverables:

- Test suite for lattice dynamics, config parsing, metrics, and export files.
- Reproducible baseline configs.
- Small benchmark sweep command.
- Notes on expected numerical behavior and known limitations.

### Phase 2: Physics And Search Improvements

Goal: broaden the experiment space after the baseline engine is tested.

Possible work:

- Absorbing or sponge boundary conditions.
- More emitter profiles.
- Better nonlinear threshold detection across paired sweep runs.
- Latin-hypercube or random sweep sampling.
- More robust Q-like decay fitting.
- Optional animation export for interesting runs.

### Phase 3: Evidence Review Tools

Goal: make promising runs easier to inspect without building a full dashboard yet.

Possible work:

- Markdown or HTML report generation per sweep.
- Top-run comparison table.
- Spectral plots for the core.
- Saved frame sequences for best candidates.

### Phase 4: Dashboard

Goal: add an interactive dashboard only after the engine can produce trustworthy candidates.

Possible work:

- Browse sweep results.
- Compare top runs.
- Open plots and summaries.
- Launch configured sweeps from the UI.

## Update Log

- 2026-06-16: Created roadmap after the initial experiment engine MVP was implemented.
- 2026-06-16: Marked roadmap creation complete; set validation and calibration as the active next phase.
- 2026-06-16: Completed the initial validation and calibration layer; tests pass with `python -m unittest discover -s tests`.
- 2026-06-16: Verified `configs/control_no_drive.json` produces zero anomaly score and no event labels.
- 2026-06-16: Verified `configs/baseline_uniform_defect.json` produces a modest retention candidate for comparison.
- 2026-06-16: Set absorbing boundary conditions as the recommended next physics improvement.
- 2026-06-16: Added `boundary_mode` with reflective and sponge options plus sponge width/strength settings.
- 2026-06-16: Added `configs/baseline_uniform_defect_sponge.json` and `configs/boundary_ab_sweep.json`.
- 2026-06-16: Ran the boundary A/B sweep; the sponge baseline ranked above the reflective baseline for the current reference configuration.
- 2026-06-16: Set cross-run nonlinear threshold detection as the next Phase 2 task.
- 2026-06-16: Added post-sweep cross-run threshold annotations for neighboring amplitude/frequency runs with nonlinear terms enabled.
- 2026-06-16: Added tests for comparative threshold annotations and verified that linear neighbor jumps are not labeled as nonlinear thresholds.
- 2026-06-16: Ran `configs/nonlinear_threshold_probe_sweep.json`; no cross-run threshold was detected because normalized core metrics stayed nearly flat across the tested amplitudes.
- 2026-06-16: Set broader seeded sweep sampling and Markdown sweep reporting as the next Phase 2 task.
- 2026-06-16: Added seeded `hybrid`, `random`, `stratified`, and `grid` sweep sampling modes.
- 2026-06-16: Added `sweep_*_plan.json` output to preserve exact sampled parameter records.
- 2026-06-16: Added `sweep_*_report.md` output with links to top-run evidence files.
- 2026-06-16: Added `configs/random_probe_sweep.json` and verified a short random probe generated plan, summary, and report files.
- 2026-06-16: Set core spectral plots and optional frame-sequence export as the next evidence review task.
- 2026-06-16: Added `core_spectrum_plot.png` export for every run and optional top-candidate `frame_sequence/` export.
- 2026-06-16: Ran `configs/evidence_probe_sweep.json`; the 0.95 drive-frequency run ranked highest and triggered `cross_run_frequency_threshold` against neighboring 0.75 and 1.15 runs.
- 2026-06-16: Visual evidence showed a clean core spectral peak near 0.223 and ring-like energy concentration around the defect boundary.
- 2026-06-16: Updated the next step to a narrow frequency-refinement sweep around the 0.95 drive candidate.
- 2026-06-16: Ran `configs/frequency_refinement_sweep.json`; 0.95 remained strongest, but 1.05 was also strong, indicating a structured response band rather than a single isolated frequency.
- 2026-06-16: Added `configs/frequency_band_characterization_sweep.json` to map 0.90 to 1.08 at finer spacing.
- 2026-06-16: Ran `configs/frequency_band_characterization_sweep.json`; strongest sampled frequency was 0.92, with additional peaks near 0.98 and 1.04 and troughs near 0.94, 1.00, and 1.06.
- 2026-06-16: Added frequency-band analysis to sweep reports, including strongest sampled frequency, half-maximum band, local peaks, and local troughs.
- 2026-06-16: Updated the next step to modal/band diagnostics because the response pattern looks like structured resonance-band behavior rather than isolated one-frequency threshold behavior.
- 2026-06-16: Reviewed `C:\Users\terry\OneDrive\Documents\wavetesting\QuantumFourier-MAgic-1`; decided to pull diagnostic ideas such as entropy, phase/coherence-style summaries, and mode-shape comparison, while leaving the speculative field-memory claims, UI stack, and storage/quantum language out of WaveEngine.
- 2026-06-16: Added numeric best-frame exports, spatial entropy, participation fraction, radial concentration, and mode-shape/radial-profile sweep diagnostics.
- 2026-06-16: Added dense-frequency threshold downweighting so repeated peak/trough scans do not keep overclaiming nonlinear threshold behavior.
- 2026-06-16: Ran `configs/frequency_band_characterization_sweep.json` again; strongest sampled frequency stayed 0.92, half-maximum band stayed 0.92 to 1.08, and the new classifier marked the scan as `alternating_frequency_response`.
- 2026-06-16: The 0.92, 0.98, 1.04, and 1.08 high-response frames had strong radial similarity to the strongest 0.92 frame, while troughs at 0.94, 1.00, and 1.06 were more diffuse and weakly correlated.
- 2026-06-16: Added and ran `configs/long_validation_peak_0_92.json`; the long 0.92 validation reached energy-well ratio 0.506, retention 0.875, and a breathing-core-envelope label, with best event at t=47.76.
- 2026-06-16: Compared the short and long 0.92 best frames; low spatial correlation (0.244) and moderate radial correlation (0.548) suggest a late-time mode transition or breathing-state change rather than the exact short-sweep frame persisting unchanged.
- 2026-06-16: Updated the next step to time-resolved mode-shape diagnostics around the long 0.92 run's best event and post-drive tail.
- 2026-06-16: Added `diagnose-run` for single-run time-resolved mode-shape diagnostics, including frame snapshots, correlation CSVs, radial profile exports, angular Fourier exports, reference comparisons, plots, and a Markdown report.
- 2026-06-16: Ran diagnostics on `runs\run_20260616_111525_687942`; captured 148 diagnostic frames and found mean previous-frame correlation 0.914, best-frame correlation to cutoff -0.187, and best-frame correlation to early tail -0.044.
- 2026-06-16: Diagnostic report detected `breathing_localized_state` with estimated period 2.667 and seven detected cycles.
- 2026-06-16: Angular diagnostics detected persistent m=4 structure with median strength 0.361 and angular phase trend R^2 0.891, resulting in `angular_mode_structure` and `rotating_tail_mode` labels.
- 2026-06-16: Reference comparison marked the long best frame as `long_tail_distinct_from_short_peak`; best-event shape correlation to the short 0.92 reference was 0.243 and max radial correlation was 0.542.
- 2026-06-16: Mode-transition detection remained inconclusive; strongest candidate time was 44.0, but cutoff-frame correlation did not drop enough under the current criteria.
- 2026-06-16: Updated the next step to targeted artifact controls for the 0.92 long-run breathing/angular tail.
- 2026-06-16: Added `python main.py artifact-controls --config configs\long_validation_peak_0_92.json`.
- 2026-06-16: Ran artifact controls in `runs\artifact_controls_20260616_114237`; result classified as `sponge_sensitive`.
- 2026-06-16: Stronger sponge preserved high retention and breathing: ratio 0.554, retention 0.882, breathing period 3.2, six cycles, and best event time 47.76.
- 2026-06-16: Wider sponge and stronger+wider sponge also preserved breathing/retention, but angular phase trend R^2 fell sharply in wider controls, so the rotating/angular-tail interpretation remains provisional.
- 2026-06-16: Updated the next step to a smaller-`dt` numerical stability control before any broader long sweep.
- 2026-06-16: Added absolute-energy and post-cutoff decay-rate comparison fields to targeted control reports.
- 2026-06-16: Refreshed sponge controls in `runs\artifact_controls_20260616_121214`; result stayed `sponge_sensitive`.
- 2026-06-16: The refreshed sponge controls showed that wider-sponge ratio gains are partly denominator-driven: original core/outer energy was 0.0550/0.1087, wider sponge was 0.0412/0.0643, and stronger+wider sponge was 0.0206/0.0255.
- 2026-06-16: Added `python main.py dt-control --config configs\long_validation_peak_0_92.json`.
- 2026-06-16: Ran dt controls in `runs\dt_controls_20260616_121139`; result classified as `numerically_stable`.
- 2026-06-16: Half-step `dt=0.02` preserved the late event and localization: ratio 0.510, retention 0.871, best event time 47.72, core energy 0.0563, outer energy 0.1103, total energy 0.1665, and m=4 strength 0.349.
- 2026-06-16: The half-step diagnostic-frame breathing period estimated 4.0, but full-resolution core-energy peak timing estimated 2.98, so the dt-control pass uses the metric-core-peak period with a sampling caveat.
- 2026-06-16: Updated the next step to one larger-grid matched-proportion control before any broader long-run sweep.
- 2026-06-16: Added `python main.py grid-control --config configs\long_validation_peak_0_92.json`.
- 2026-06-16: Ran the first grid control in `runs\grid_controls_20260616_124224`; the 63-grid variant reached its best event at t=55.96, essentially the end of the original t=56 run, so the no-breathing result was treated as end-limited.
- 2026-06-16: Added `--larger-physical-duration` to `grid-control` and reran the larger-grid control with t=86 in `runs\grid_controls_20260616_124645`.
- 2026-06-16: The extended 63-grid run classified as `grid_resistant_timing_shift`: ratio 0.531, retention 0.806, best event time 74.68, core fraction 0.347, core density 0.000171, breathing period 2.128, 11 cycles, and m=4 strength 0.370.
- 2026-06-16: Updated the next step to fixed-domain grid-refinement support, because the current matched-proportion grid control preserves the structure but shifts timing later under domain/grid scaling.
- 2026-06-16: Added fixed-domain configuration semantics, including physical domain size, `dx`/`dy`, physical defect/core/sponge/emitter widths, fixed-domain Laplacian scaling, cell-area energy integration, and dt stability guidance.
- 2026-06-16: Updated fixed-domain radial diagnostics to report physical units and added same-domain best-frame resampling for grid-control similarity checks.
- 2026-06-16: Added `python main.py fixed-domain-grid-control --config configs\long_validation_peak_0_92.json`.
- 2026-06-16: Ran fixed-domain 41-vs-63 control in `runs\fixed_domain_grid_controls_20260616_145923`; breathing, retention, best-event timing, core fraction, and best-frame similarity passed, but the physical radial peak shifted from 10.0 to 3.75.
- 2026-06-16: Ran optional fixed-domain 81 control in `runs\fixed_domain_grid_controls_20260616_150109`; breathing persisted, but ratio fell to 0.318, retention fell to 0.716, core fraction fell to 0.241, and the physical radial peak remained 3.75.
- 2026-06-16: Classified the fixed-domain refinement result as `resolution_sensitive`; updated the next step to diagnose source normalization and radial-structure sensitivity before broader long sweeps.
- 2026-06-16: Created a dedicated local SSH key for the private GitHub repo `terrywilliamsSEO/wavey` and added an SSH config alias `github-wavey`.
- 2026-06-16: Added `AGENTS.md`, `docs/project_state.md`, and `docs/architecture.md` so future agents can audit state, understand commands, and maintain docs without needing the chat transcript.
- 2026-06-16: Added `python main.py resolution-diagnostics --config configs\long_validation_peak_0_92.json`.
- 2026-06-16: Ran resolution diagnostics in `runs\resolution_diagnostics_20260616_161612`; result classified as `mask_discretization_issue` because emitter physical area from the source mask varies across fixed-domain resolutions.
- 2026-06-16: The resolution diagnostic found source work per physical boundary length remained within tolerance (relative range 0.264), core area was comparable (relative range 0.0447), breathing period stayed stable at 2.67/2.63/2.99, and strongest angular mode stayed m=4.
- 2026-06-16: The same diagnostic found 63/81 refined radial structure converging inward: radial peak 3.75 for both, best radial correlation 0.964, compared with the 41-grid radial peak at 10.0.
- 2026-06-16: Added fractional fixed-domain emitter coverage and source normalization modes for physically controlled source geometry.
- 2026-06-16: Added `python main.py source-normalized-resolution-diagnostics --config configs\long_validation_peak_0_92.json`.
- 2026-06-16: Ran source-normalized diagnostics in `runs\source_normalized_resolution_20260616_215926`; result classified as `coarse_grid_artifact_likely`.
- 2026-06-16: In the calibrated source-normalized run, emitter effective area range was 0.0126, injected work per physical boundary length range was 2.9e-06, and the legacy 63-grid source-work anomaly was removed.
- 2026-06-16: Source-normalized 63/81 refined grids converged at physical radial peak 10.0 with best radial correlation 0.965; the 41-grid source-normalized radial peak was 5.0.
- 2026-06-16: Breathing survived and m=4 persisted under source normalization, but the 63-grid diagnostic breathing period was short at 1.689, so the next step is a targeted breathing-period audit rather than a broad sweep.
- 2026-06-16: Added `python main.py breathing-period-audit --control-root runs\source_normalized_resolution_20260616_215926`.
- 2026-06-16: The breathing audit classified the 63-grid short period as `peak_detector_overcounts_subpeaks`: the existing diagnostic-frame detector counted ten peaks with period 1.689, while full-resolution metric peaks with minimum separation 1.5 estimated 2.491 and minimum separation 2.0 estimated 2.907.
- 2026-06-16: Updated the next step to harden `_detect_breathing_state` before any broad long sweeps.
- 2026-06-16: Added direct core/annulus drive support, separate boundary/core work accounting, post-cutoff-only core-modal summaries, and `python main.py core-modal-probe --config configs\long_validation_peak_0_92.json`.
- 2026-06-16: Ran core-modal probe in `runs\core_modal_probe_20260616_230134`; boundary references at 63/81 retained breathing with equal injected work, but direct core impulse/burst controls did not reproduce the reference post-cutoff breathing/radial/m=4 state.
- 2026-06-16: Classified the core-modal result as `boundary_transport_required`; best matching core probe was `core_impulse_63`, but it had slow natural ringing period 22.32, radial similarity 0.285, and m=4 strength 0.0177.
- 2026-06-16: Updated the next step to harden the global breathing detector first, then run narrow boundary-transport mechanism controls rather than broad neighboring-frequency long sweeps.
- 2026-06-17: Hardened the global time-resolved breathing detector with raw/envelope period reporting, minimum separation, smoothing, prominence filtering, subpeak-overcounting labels, and retained-energy gating.
- 2026-06-17: Reran source-normalized fixed-domain diagnostics in `runs\source_normalized_resolution_20260616_233009`; classification stayed `coarse_grid_artifact_likely`, while the 63-grid period now reports an envelope-scale 3.040 with `subpeak_overcounting_possible` instead of overclaiming the raw 1.689 subpeak period.
- 2026-06-17: Refreshed core-modal probe in `runs\core_modal_probe_20260616_233711`; classification stayed `boundary_transport_required`, and the combined report now separates diagnostic envelope period from metric min-separated and raw diagnostic-frame periods.
- 2026-06-17: Updated the next step to targeted annulus / near-defect transport controls before any broad long sweeps.
