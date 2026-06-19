# Architecture Notes

Last updated: 2026-06-19

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
- `prototype-3d`: tiny fixed-domain 31^3 shell-breathing prototype for the 2D boundary-flux mechanism.
- `prototype-3d-audit`: read-only failure-mode audit for completed tiny 3D prototype runs.
- `prototype-3d-source-sponge-control`: tiny 31^3 source/sponge separation control for the 3D boundary source.
- `prototype-3d-sponge-strength-control`: tiny 31^3 sponge-strength/width control for the inner-sponge-edge 3D boundary source.
- `prototype-3d-source-geometry-control`: tiny 31^3 source-geometry comparison from the stronger-sponge inner-edge 3D setup.
- `prototype-3d-cubic-focus-control`: tiny 31^3 focused control around the clean six-face cubic 3D boundary source.
- `prototype-3d-cubic-confirmation-control`: tiny 31^3 dt/sponge confirmation around the original and sign-flipped cubic 3D boundary phases.
- `prototype-3d-grid-confirmation-control`: tiny fixed-domain 31^3 to 41^3 grid confirmation for the clean sign-flipped cubic 3D source.
- `prototype-3d-threshold-control`: tiny calibrated 41^3 amplitude/phase tolerance check for the clean sign-flipped cubic stronger-sponge 3D source.
- `prototype-3d-defect-control`: tiny calibrated 41^3 defect-ablation control for the clean sign-flipped cubic stronger-sponge 3D source.
- `prototype-3d-radial-window-audit`: tiny 41^3 current-defect vs neutral-lattice radial shell-window audit for defect-lift measurement.
- `prototype-3d-defect-lift-sweep`: tiny 41^3 stronger/different-defect sweep against the neutral-lattice shell-tail baseline.
- `prototype-3d-interference-diagnostics`: tiny 41^3 neutral-lattice phase/interference diagnostic for the structured boundary-transport hypothesis.
- `prototype-3d-standing-persistence`: tiny 41^3 settled shell-pattern persistence check for the two clean neutral cubic variants.
- `prototype-3d-transport-packet-audit`: tiny 41^3 motion/flux audit for the clean neutral cubic shell-window tail.
- `prototype-3d-packet-lifecycle-audit`: extended tiny 41^3 lifecycle audit for whether the clean cubic packet exits, diffuses, stalls, or repeatedly refocuses.
- `prototype-3d-refocusing-engineering-control`: tiny 41^3 source-shaping control that varies phase offset, cutoff timing, frequency, and optional chirp around the clean neutral cubic packet.
- `prototype-3d-refocusing-map-control`: tiny 41^3 cutoff-frequency cross-map around the refocusing winners.
- `prototype-3d-cutoff-phase-map-control`: tiny 41^3 release-phase timing map around cutoff 18, with compact phase-offset and sign-flip/polarity families, passive island-refinement, phase-lock needle, and threshold-robust confirmation presets, ranked cutoff-phase output, release-phase island stability checks, phase-lock needle-width reporting, event-threshold sensitivity auditing, and conservative threshold-robust scoring.
- `prototype-3d-second-pulse-control`: tiny 41^3 active second-pulse control from the best release phase, with no-pulse and passive-extension work-normalized comparators, optional multi-scale/multi-duration reduced-work maps, timing audit output, and travel-time-adjusted micro-map mode.

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
- `simulation/prototype_3d.py`: standalone 3D prototype lattice, spherical/shell defect masks, defect-only nonlinear stiffness, six-face boundary source, cubic/random phase sources, direct core/shell controls, shell/radial diagnostics, and sponge/dt checks. It also owns 3D boundary phase offset, cubic phase sign, random phase seed, per-face amplitude scaling, optional second-pulse forcing, and per-variant defect radius/multiplier fields used by focused controls.
- `simulation/prototype_3d_audit.py`: read-only 3D failure-mode audit that reconstructs source/sponge/defect geometry, separates near-defect shell-window energy from outer radial residue, exports radial snapshots, and classifies completed prototype runs. It reads explicit saved sponge width/strength, defect radius/multiplier, shell-defect, random-phase, and defect-nonlinearity fields when controls vary them.
- `simulation/prototype_3d_source_sponge.py`: tiny 3D source/sponge separation control that moves the boundary source to the inner sponge edge, removes source-cell sponge damping, or places the source deeper inside the domain while matching work per physical source area.
- `simulation/prototype_3d_sponge_strength.py`: tiny 3D sponge-strength control that keeps the best inner-sponge-edge source location fixed while varying weak, baseline, stronger, wider, and stronger+wider sponge settings under matched work per physical source area.
- `simulation/prototype_3d_source_geometry.py`: tiny 3D source-geometry control that compares selected boundary-face sets and phase maps under matched work per physical source area, with direct core/shell controls matched by total work.
- `simulation/prototype_3d_cubic_focus.py`: tiny 3D focused control around six-face cubic source details: deterministic repeat, cubic sign flip, global phase offset, missing face, mild face imbalance, same-coverage uniform phase, fixed-seed random repeats, and direct core/shell controls.
- `simulation/prototype_3d_cubic_confirmation.py`: tiny 3D confirmation control around original and sign-flipped cubic phases, including repeat, half-dt, weak/strong sponge, one amplitude-reduced sign-flip probe, direct core/shell controls, and 3D dt stability estimates.
- `simulation/prototype_3d_grid_confirmation.py`: tiny fixed-domain 3D grid confirmation that lifts only the clean sign-flipped cubic stronger-sponge source from 31^3 to 41^3, with optional original-cubic comparator and one negative control.
- `simulation/prototype_3d_threshold_control.py`: tiny calibrated 41^3 threshold/tolerance control around the sign-flipped cubic stronger-sponge source. It derives the target work per physical source area from the 31^3 reference, calibrates the 41^3 reference, tests explicit amplitude multipliers, work-matches phase offsets, and keeps direct core/shell controls matched by total work.
- `simulation/prototype_3d_defect_control.py`: tiny calibrated 41^3 defect-dependence control around the sign-flipped cubic stronger-sponge source. It matches every variant to the same work per physical source area, ablates defect stiffness/damping/coupling/radius, and adds fixed-window near-shell metrics anchored to the original defect radius.
- `simulation/prototype_3d_radial_window_audit.py`: tiny calibrated 41^3 current-defect vs neutral-lattice audit that scans shell windows by inner radius, exports per-window metrics, radial-profile comparisons, frame similarities, and defect-lift ratios.
- `simulation/prototype_3d_defect_lift_sweep.py`: tiny calibrated 41^3 stronger/different-defect sweep against neutral. It holds the sign-flipped cubic stronger-sponge boundary source fixed, varies only defect parameters, scans shell windows, and classifies only strict retention-plus-peak/work lift with radial-profile difference and no global outer flag.
- `simulation/prototype_3d_interference_diagnostics.py`: tiny calibrated 41^3 neutral-lattice interference diagnostic. It holds the sign-flipped cubic stronger-sponge boundary source family fixed, compares uniform/cubic-offset/random phase controls under matched work per source area, and exports phase coherence, constructive/destructive shell alignment, modal projection proxies, wavefront timing, and standing-shell persistence.
- `simulation/prototype_3d_standing_persistence.py`: tiny calibrated 41^3 settled-pattern confirmation for the two clean neutral cubic variants. It reruns sign-flipped cubic and cubic phase-offset, samples densely after a post-cutoff settling delay, and exports node/antinode stability, radial shell phase stability, shell energy autocorrelation, frame similarity, spectral concentration, and a settled standing score.
- `simulation/prototype_3d_transport_packet.py`: tiny calibrated 41^3 packet-motion audit for the two clean neutral cubic variants. It reruns sign-flipped cubic and cubic phase-offset, then exports shell-window phase velocity, radial group velocity, time-of-flight, inward/outward radial flux, shell centroid displacement, angular drift, shell exit timing, and time-lagged shell-pattern correlation.
- `simulation/prototype_3d_packet_lifecycle.py`: extended calibrated 41^3 lifecycle audit for the two clean neutral cubic variants. It preserves the cutoff but extends the run horizon, tracks packet radius, packet spread/width, shell-window peak returns, shell exit timing, inward/outward flux balance, post-cutoff shell decay, and primary/second-pulse/total positive work when active pulses are present.
- `simulation/prototype_3d_refocusing_engineering.py`: tiny calibrated 41^3 refocusing-engineering control. It reuses lifecycle diagnostics while varying only the winning engineering axes around the neutral cubic packet: phase offset, cutoff timing, fixed frequency, and optional linear chirp. It classifies whether refocus count, return-peak ratio, exit delay, decay rate, and tail retention improve without global outer-window contamination.
- `simulation/prototype_3d_refocusing_map.py`: tiny calibrated 41^3 cutoff-frequency map. It keeps the neutral cubic phase-offset source fixed, compares `cutoff_long`, `frequency_high`, their combined setting, and nearby cutoff/frequency neighbors, then classifies whether the two knobs combine constructively under strict shell-retention and outer-window guards.
- `simulation/prototype_3d_cutoff_phase_map.py`: tiny calibrated 41^3 release-phase timing map. It keeps frequency fixed, varies cutoff near 18, records phase at cutoff, compares small global phase-offset perturbations, includes a compact sign-flip/polarity family, supports passive island-refinement, sign-flip-only phase-lock needle, and threshold-robust confirmation presets, and emits ranked results by major shell-window peaks, refocus peaks, no exit, retention, outer/shell below 1.0, decay closest to zero, and global outer false. Reports include release-phase island stability, phase-lock needle-width, event-threshold sensitivity, and threshold-robust refocusing score sections.
- `simulation/prototype_3d_second_pulse.py`: tiny calibrated 41^3 active second-pulse control. It reads refocus times from the cutoff-phase event CSV, compares timed second-pulse variants against no-pulse and passive-extension controls, supports reduced-work maps over selected roles/amplitude scales/durations, writes a no-pulse timing/phase audit, supports travel-time-adjusted target micro-maps, and ranks by refocus count, cleanliness, retention, outer/shell, decay, global outer flags, clean refocus score, and added-work efficiency.
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
- Use `prototype-3d-source-sponge-control` only after the tiny 3D audit shows source/sponge overlap or global radial-peak contamination.
- Use `prototype-3d-sponge-strength-control` after the source/sponge separation control identifies a retained near-defect source geometry; keep the source location fixed and do not increase grid size.
- Use `prototype-3d-source-geometry-control` after stronger sponge preserves the near-defect shell tail; compare boundary geometry before increasing 3D grid size.
- Use `prototype-3d-cubic-focus-control` after source-geometry controls identify six-face cubic as the cleanest 3D boundary case; isolate which cubic source details survive before any larger grid.
- Use `prototype-3d-cubic-confirmation-control` after the cubic-focus pass identifies clean cubic-phase candidates; confirm half-dt and small sponge robustness before any larger grid.
- Use `prototype-3d-grid-confirmation-control` only after cubic dt/sponge confirmation passes; it is a single-candidate 31^3 to 41^3 lift, not a general 3D sweep.
- Use `prototype-3d-threshold-control` only after the single-candidate 41^3 lift passes; it is a tiny amplitude/phase tolerance check around the calibrated sign-flip candidate, not a general parameter sweep.
- Use `prototype-3d-defect-control` only after the calibrated 41^3 sign-flip candidate passes tolerance checks; it answers whether the retained shell-window tail requires the spherical defect before any broad 3D work.
- Use `prototype-3d-radial-window-audit` after defect ablation suggests neutral-lattice survival; it checks whether the current defect creates lift at any stable shell window before further physics claims.
- Use `prototype-3d-defect-lift-sweep` only after the radial-window audit fails to show current-defect lift; it is the last tiny defect-parameter check before pivoting to structured boundary transport.
- Use `prototype-3d-interference-diagnostics` after defect-lift fails; it tests whether same-work phase randomization disrupts the retained shell tail and whether cubic phase leaves a coherent standing-shell fingerprint.
- Use `prototype-3d-standing-persistence` after interference diagnostics report weak standing persistence; it decides whether the clean cubic shell-window signal remains spatially organized after cutoff or is better treated as coherent transport through the shell window.
- Use `prototype-3d-transport-packet-audit` after standing persistence fails; it decides whether the coherent shell-window tail is moving radially as a transport packet or drifting slowly as a modal structure.
- Use `prototype-3d-packet-lifecycle-audit` after packet motion is confirmed; it decides whether the packet simply passes through, diffuses, stalls, exits, or repeatedly refocuses at the target shell window.
- Use `prototype-3d-refocusing-engineering-control` after repeated refocusing is confirmed; it tests whether small source-shaping changes can increase refocus returns, delay exit, slow decay, and preserve cleanliness. Keep it local to the known clean 41^3 packet.
- Use `prototype-3d-refocusing-map-control` after one-axis cutoff/frequency improvements are found; it asks whether the winning knobs combine constructively. If they do not, return to a single-axis refinement rather than expanding the map.
- Use `prototype-3d-cutoff-phase-map-control` after the cutoff-frequency map fails additivity; it tests whether release phase/cutoff timing and polarity family control refocusing. The `--release-phase-island-refinement` preset checks the broader supported sign-flip timing family; the `--phase-lock-needle-map first|tight` presets are sign-flip-only ultra-fine cutoff checks around the 17.94 pocket; `--threshold-robust-confirmation` is the sign-flip-only conservative-count check for cutoffs 17.920-17.950.
- Use `prototype-3d-second-pulse-control` after the release-phase timing island is established only when testing a specific active-reinjection hypothesis; the current first-refocus and second-refocus maps failed strict clean criteria, so active pulses are shelved unless a new mechanism justifies revisiting them. Judge any future added pulses by clean-score improvement per added work rather than raw retention alone.

Current fixed-domain caution: `source-normalized-resolution-diagnostics` fixed emitter geometry/work comparability for the 0.92 candidate and classified the radial result as `coarse_grid_artifact_likely`. The global breathing detector now flags raw subpeak overcounting and reports envelope-scale periods. `core-modal-probe` classified the direct-core test as `boundary_transport_required`. The 63x63 and 81x81 `transport-controls` passes classified the candidate as `boundary_geometry_sensitive`, and the boundary-only work-per-length controls kept that classification after boundary flux density was normalized. `boundary_rotating_m4_81` still reproduces the family, which justified the first small 3D prototype.

Current 3D caution: the first `prototype-3d` run was `inconclusive` under the original global shell metric. `prototype-3d-audit` classified the run as `diagnostic_window_issue`: the global shell peak is outer-biased, while a small near-defect shell signal arrives late and should be tracked separately. `prototype-3d-source-sponge-control` showed that the inner-sponge-edge source strengthens the retained near-defect shell signal without global outer-boundary dominance. `prototype-3d-sponge-strength-control` then showed that stronger sponge at the original width lowers outer/near tail contamination while preserving the near-shell tail. `prototype-3d-source-geometry-control` classified the source-geometry set as `boundary_source_geometry_preserves_near_shell`: six-face cubic remained the cleanest retained near-shell case, while uniform/reduced-face/random boundary variants were global-outer-window flagged and direct core/shell forcing was not retained. `prototype-3d-cubic-focus-control` then classified the focused cubic set as `cubic_phase_structure_not_full_symmetry`: six-face cubic repeated, sign-flipped cubic stayed clean, uniform/random phases stayed outer-flagged, and mild cubic symmetry breaks stayed clean. `prototype-3d-cubic-confirmation-control` then classified the family as `cubic_phase_dt_sponge_confirmed`: original and sign-flipped cubic phases survived repeat, half-dt, stronger-sponge, and weak-sponge checks with no dt warnings, while direct controls remained transient. `prototype-3d-grid-confirmation-control` then classified the one-step lift as `sign_flip_resolution_lift_confirmed`: sign-flipped cubic survived at 41^3, original cubic did not pass the same cleanliness criterion, and direct shell stayed transient. `prototype-3d-threshold-control` then classified the calibrated 41^3 tolerance pass as `amplitude_phase_tolerant`: 0.5x-1.5x amplitude and +/-pi/8 phase offsets stayed clean, while direct core/shell controls remained transient. `prototype-3d-defect-control` then classified the defect-ablation pass as `defect_radius_sensitive`: the neutral lattice preserved the fixed-window tail, while larger radius mildly worsened outer/near contamination. `prototype-3d-radial-window-audit` then classified the current-defect vs neutral-lattice scan as `neutral_lattice_reproduces_shell_tail`: radius-5 defect lift was 0.990 for retention and 0.848 for peak/work. `prototype-3d-defect-lift-sweep` then classified stronger/different defects as `no_defect_lift_found`: no window lifted both retention and peak/work above 1.5. `prototype-3d-interference-diagnostics` then classified the neutral-lattice phase controls as `interference_supported_standing_weak`: random phase controls outer-flagged and lost phase coherence, but standing-shell persistence stayed below threshold. `prototype-3d-standing-persistence` then classified the two clean cubic variants as `coherent_transport_not_standing`: shell energy remains temporally coherent, but settled node/antinode masks and frame-to-mean shell patterns do not lock. `prototype-3d-transport-packet-audit` then classified the same clean cubic variants as `moving_transport_packet_supported`: radial group velocity is inward, inward shell flux is about 0.78 of total radial flux, and angular drift is near zero. `prototype-3d-packet-lifecycle-audit` then classified the extended runs as `repeated_refocusing_supported`: both clean cubic variants show multiple post-cutoff shell-window return peaks before exiting near t=75-76. `prototype-3d-refocusing-engineering-control` then classified the first source-shaping control as `refocusing_improved`: longer cutoff and slightly higher frequency improved refocus count, retention, decay rate, and outer/shell contamination without global outer-window flags. `prototype-3d-refocusing-map-control` then classified the cutoff-frequency map as `local_map_improved_single_axis`: the combined cutoff-long/frequency-high setting degraded return count and retention, so the knobs are not simply additive. `prototype-3d-cutoff-phase-map-control` then classified the tighter release-timing map as `cutoff_phase_timing_island_supported`: sign-flip cutoff 17.9, cutoff phase 0.468 cycles, retention 0.322, outer/shell 0.660, no exit, and global outer false was the best ranked row. `prototype-3d-second-pulse-control` then classified full-amplitude, reduced-work, first-refocus travel-time, and second-refocus travel-time active pulses as `second_pulse_contaminated_or_inconclusive`; active pulses can raise raw retention but reduce clean return count, worsen decay, push outer/shell above 1.0, and produce negative added-work efficiency. The passive release-phase refinement in `runs\cutoff_phase_map_3d_20260619_145631` classified as `cutoff_phase_single_point_best`, the ultra-fine follow-up in `runs\cutoff_phase_map_3d_20260619_155704` found neighboring 11/10 support across cutoffs 17.93-17.94, and the threshold-robust confirmation in `runs\cutoff_phase_map_3d_20260619_162240` showed those rows conservatively preserve 9/8 under stricter thresholds. Current 3D wording should be structured boundary-interference transport/refocusing, not defect-dependent localization or standing-shell mode. Also describe the new top result as a narrow phase-lock needle, not a broad timing island, and do not claim 11/10 is threshold-invariant.

## Generated Artifacts

Run artifacts live in `runs/` and are ignored by Git except `runs/.gitkeep`.

Each important run/control result must be summarized in `ROADMAP.md` and `docs/project_state.md`, because future agents may not have local run artifacts after cloning.

## Test Suite

Main validation command:

```powershell
python -m unittest discover -s tests
```

The suite includes lattice sanity, config/export schema, sweep behavior, time-resolved diagnostics, and classification logic for all targeted controls.
