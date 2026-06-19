# Agent Handoff Guide

This file is the first stop for any agent entering the project cold. Keep it short, current, and useful.

## Read Order

1. `README.md` for setup, commands, and output artifacts.
2. `ROADMAP.md` for the current next step and full decision log.
3. `docs/project_state.md` for the latest experimental conclusion and caution flags.
4. `docs/architecture.md` for the code map and physics-mode notes.
5. `docs/calibration.md` for numerical expectations and sanity checks.

## Current Rule Of Engagement

- Do not run broad long sweeps or broad 3D sweeps; active second-pulse controls are shelved for now, and the current conservative interpretation is the narrow passive phase-lock cluster at cutoff 17.93-17.94 preserves or improves the clean 9/8 refocusing family under stricter detection. Do not add traps, rotation, medium shaping, defects, grid changes, frequency combinations, active reinjection, or broad sweeps.
- Treat old pre-fixed-domain results as historical context, not numerically identical baselines.
- Legacy fixed-domain `per_cell` source handling is reference-only because emitter/source geometry was not resolution-invariant.
- The latest source-normalized diagnostic classified the fixed-domain 41/63/81 comparison as `coarse_grid_artifact_likely`: 63x63 and 81x81 converge at physical radial peak 10.0, while 41x41 peaks at 5.0.
- Source-normalized breathing survives and m=4 persists. The global detector now reports envelope-scale periods and flags raw subpeak overcounting; the refreshed 63x63 source-normalized period is 3.040 with `subpeak_overcounting_possible` for the old raw 1.689 diagnostic-frame period.
- The latest core-modal probe classified direct core excitation as `boundary_transport_required`: boundary references at 63/81 retained the 0.92 breathing family with matched work, but core impulse/burst controls did not reproduce the reference post-cutoff breathing/radial/m=4 state.
- The targeted transport-control passes at 63x63 and 81x81 both classified the candidate as `boundary_geometry_sensitive`: boundary left, left-right, and rotating m=4 variants retained breathing, while direct annulus/near-defect drives did not reproduce the reference family.
- Boundary-only work-per-length controls at 63x63 and 81x81 kept the same classification; `boundary_rotating_m4_81` still reproduced the family after boundary flux density was normalized.
- The first 31^3 3D prototype classified as `inconclusive`: boundary cubic forcing did not pass the original global shell-retention success metric, and the global shell peak stayed near the outer boundary.
- The 3D failure-mode audit classified the prototype as `diagnostic_window_issue`: the global shell peak was outer-biased, but a small near-defect shell signal arrived late and retained within its local window.
- The 3D source/sponge separation control classified as `source_sponge_separation_improves_near_shell`: driving at the inner sponge edge strengthened the retained near-defect shell window without global outer-boundary dominance.
- `source_inside_domain_gap_from_sponge` produced a huge early near-shell peak, but its post-cutoff near-shell retention collapsed, so treat it as a transient control rather than the best geometry.
- The 3D sponge-strength control classified as `sponge_strength_suppresses_outer_contamination`: stronger sponge at the original width preserved the near-shell tail and reduced outer/near tail contamination from 3.88 to 2.94, while weak sponge increased outer residue and wider sponge reintroduced full source/sponge overlap.
- The 3D source-geometry control classified as `boundary_source_geometry_preserves_near_shell` again when rerun in `runs\source_geometry_3d_20260618_092029`: six-face cubic remained the cleanest boundary case, while uniform/reduced-face/random boundary variants were global-outer-window flagged even with source/sponge overlap confirmed at zero. Direct core/shell forcing was transient rather than retained.
- The focused 3D cubic-source control classified as `cubic_phase_structure_not_full_symmetry` in `runs\cubic_focus_3d_20260618_101501`: six-face cubic repeated cleanly, sign-flipped cubic was the best clean boundary variant, uniform/random phase controls were global-outer-window flagged, and direct core/shell forcing was transient.
- Mild cubic symmetry breaks stayed clean in that focused control, so perfect six-face balance is not isolated as the required ingredient. The stronger clue is cubic phase structure, with phase timing still sensitive because the global phase-offset variant was outer-window flagged.
- The 3D cubic dt/sponge confirmation classified as `cubic_phase_dt_sponge_confirmed` in `runs\cubic_confirmation_3d_20260618_110234`: original cubic and sign-flipped cubic survived deterministic repeat, half-dt, stronger-sponge, and weak-sponge checks with no global outer flags and no dt warnings. Direct core/shell controls remained transient.
- `cubic_phase_sign_flip_stronger_sponge` is now the best 3D boundary variant: near peak/work 4.16e-7, near retention 0.656, outer/near 0.739, near radius median 5.05, and arrival time 9.76.
- The 0.75 amplitude-reduced sign-flip probe stayed clean, so the first grid-size lift was allowed as a single-candidate check only.
- The tiny fixed-domain 31^3 to 41^3 grid confirmation classified as `sign_flip_resolution_lift_confirmed` in `runs\grid_confirmation_3d_20260618_112610`: 41^3 sign-flipped cubic stayed clean with near retention 0.578, outer/near 1.49, near peak/work 2.03e-7, near radius median 5.05, arrival time 9.36, global outer false, and no dt warnings.
- The optional 41^3 original cubic comparator did not pass the same cleanliness check because outer/near rose to 7.17. The 41^3 direct-shell negative control was transient with near retention 5.7e-7.
- The calibrated 41^3 amplitude/phase threshold control classified as `amplitude_phase_tolerant` in `runs\threshold_control_3d_20260618_124524`: 0.5x-1.5x amplitude and -pi/8 to +pi/8 phase offsets stayed clean, with global outer false and no dt warnings.
- The calibrated 41^3 reference matched target work/area 0.105027 and kept near retention 0.578, outer/near 1.49, near peak/work 2.03e-7, and arrival 9.36. Direct core/shell controls stayed transient with near retention about 2.5e-6 and 5.7e-7.
- The calibrated 41^3 defect-ablation control classified as `defect_radius_sensitive` in `runs\defect_control_3d_20260618_133637`: the no-defect neutral lattice preserved the fixed-window tail with retention 0.583, outer/near 1.25, radius median 5.05, global outer false, and no dt warnings.
- Individual stiffness/coupling/damping neutralizations stayed close to the current-defect reference. The larger-radius variant was the main caution, with retention 0.519 and outer/near 2.01.
- The radial-window neutral-lattice audit classified as `neutral_lattice_reproduces_shell_tail` in `runs\radial_window_audit_3d_20260618_152906`: at radius 5, defect lift was 0.990 for retention and 0.848 for peak/work, with radial-profile correlation 0.981 and no radius shift.
- No stable scanned shell window showed defect lift above 1.5 for both retention and peak/work.
- The stronger/different-defect lift sweep classified as `no_defect_lift_found` in `runs\defect_lift_sweep_3d_20260618_163154`: max retention lift was 1.262, max peak/work lift was 1.170, and zero windows lifted both metrics above 1.5.
- The neutral-lattice interference diagnostic classified as `interference_supported_standing_weak` in `runs\interference_diagnostics_3d_20260618_175806`: cubic sign-flip stayed clean with coherence 0.409 and outer/near 1.25, random phase controls outer-flagged with coherence 0.013-0.018 and outer/near 5.76-6.32, but cubic standing persistence was only 0.515 versus the 0.60 threshold.
- The dense standing-persistence check classified as `coherent_transport_not_standing` in `runs\standing_persistence_3d_20260618_190944`: sign-flip and phase-offset cubic variants stayed clean and temporally coherent, but settled node/antinode stability, frame-to-mean shell similarity, and radial shell phase stability did not lock.
- The transport-packet audit classified the same clean cubic variants as `moving_transport_packet_supported` in `runs\transport_packet_3d_20260618_193704`: sign-flip radial group velocity -0.238, inward flux fraction 0.781, arrival 9.28; phase-offset radial group velocity -0.232, inward flux fraction 0.787, arrival 8.48; both had near-zero angular drift and no shell exit detected.
- The extended lifecycle audit classified the same clean cubic variants as `repeated_refocusing_supported` in `runs\packet_lifecycle_3d_20260618_195923`: sign-flip produced five major post-cutoff shell-window peaks and four refocus peaks before exit at t=74.72; phase-offset produced six major peaks and five refocus peaks before exit at t=76.00.
- The 3D refocusing-engineering control classified as `refocusing_improved` in `runs\refocusing_engineering_3d_20260618_202513`: `cutoff_long` produced nine major shell-window peaks, eight refocus peaks, tail retention 0.269, outer/shell 0.809, decay -0.0273, no detected shell exit, and no global outer-window flag. `frequency_high` also stayed clean with eight major peaks, seven refocus peaks, retention 0.257, outer/shell 0.686, and no detected shell exit.
- The tiny cutoff-frequency map classified as `local_map_improved_single_axis` in `runs\refocusing_map_3d_20260618_204404`: `combined_cutoff_long_frequency_high` did not combine constructively. It dropped to four major peaks, three refocus peaks, retention 0.0993, outer/shell 1.70, and exit at t=70.4. `cutoff_long_reference` remains the best return-count/retention row; `frequency_high_reference` remains the cleanest low-outer row.
- The first cutoff release-phase map classified as `cutoff_timing_improved` in `runs\cutoff_phase_map_3d_20260619_085647`: cutoff 18 was sharply better than +/-0.5 offsets, but strict timing-island classification did not trigger because retention stayed just below 0.30.
- The tighter cutoff/polarity timing map classified as `cutoff_phase_timing_island_supported` in `runs\cutoff_phase_map_3d_20260619_104211`: sign-flip cutoff 17.9 was the best ranked row with cutoff phase 0.468 cycles, nine major peaks, eight refocus peaks, retention 0.322, outer/shell 0.660, decay -0.0237, no shell exit, and no global outer flag. The sign-flip strong rows clustered at cutoff phases 0.376-0.468 cycles.
- The passive release-phase island refinement classified as `cutoff_phase_single_point_best` in `runs\cutoff_phase_map_3d_20260619_145631`: `sign_flip_cutoff_minus_0p06` at cutoff 17.94 and cutoff phase 0.5048 cycles reached eleven major peaks, ten refocus peaks, retention 0.314, outer/shell 0.631, decay -0.02396, no shell exit, and no global outer flag. The new stability section rejected it as a stable island because no neighboring row reproduced 11/10.
- The ultra-fine passive phase-lock needle map classified as `cutoff_phase_timing_island_supported` in `runs\cutoff_phase_map_3d_20260619_155704`, but the width section classified the optimum as `narrow`: `sign_flip_cutoff_minus_0p07`, `sign_flip_cutoff_minus_0p065`, and `sign_flip_cutoff_minus_0p06` all reached 11/10 across cutoff 17.93-17.94, an exact-top width of only 0.01.
- The event-threshold sensitivity audit for that ultra-fine run classified the best count as `best_count_threshold_sensitive`: the best row recounts as 12/11, 11/10, or 9/8 when the major-peak threshold shifts from 0.25 to 0.30 to 0.35. Treat 11/10 as detector-sensitive until event traces or threshold logic are hardened.
- The threshold-robust confirmation in `runs\cutoff_phase_map_3d_20260619_162240` classified the narrow cluster as real enough to continue, but not as threshold-invariant 11/10. Cutoffs 17.93, 17.935, and 17.94 count as 12/11 at peak threshold 0.25, 11/10 at 0.30, and 9/8 at 0.35 and 0.40, with no exit and global outer false.
- Conservative wording: the cluster preserves or improves the clean 9/8 refocusing family under stricter detection; do not state that 11/10 is threshold-invariant.
- Do not phrase the 3D candidate as defect-required localization or a confirmed standing-shell mode. Better wording: structured boundary-interference shell-window transport/refocusing at 41^3.
- The first active second-pulse control classified as `second_pulse_contaminated_or_inconclusive` in `runs\second_pulse_3d_20260619_112731`: all full-amplitude second-pulse variants reduced the clean refocus count below the 9/8 reference, worsened decay, and pushed outer/shell above 1.0. Phase-matched/opposite-polarity pulses raised raw retention to about 0.56 but injected about 108 extra positive-work units and did not extend the clean sequence.
- The reduced-work phase-matched second-pulse check classified as `second_pulse_contaminated_or_inconclusive` in `runs\second_pulse_3d_20260619_115332`: 0.1x-0.5x pulses and shorter 1.0-duration pulses still reduced refocus count to 4-5, pushed outer/shell above 1.20, worsened decay to roughly -0.043 to -0.046, and had negative `added_work_efficiency`.
- The first-refocus travel-time second-pulse micro-map classified as `second_pulse_contaminated_or_inconclusive` in `runs\second_pulse_3d_20260619_125050`: empirical boundary-to-shell travel time was 9.44, first-refocus ideal launch was t=26.4, and all active rows still had fewer refocus peaks, outer/shell above 1.0, worse decay, and negative `added_work_efficiency`.
- The second-refocus travel-time second-pulse micro-map classified as `second_pulse_contaminated_or_inconclusive` in `runs\second_pulse_3d_20260619_135358`: second-refocus ideal launch was t=31.68, no-pulse reference stayed best at 9/8 peaks, retention 0.322, outer/shell 0.660, and decay -0.0237; the best ranked active row reached retention 0.491 but only 6/5 peaks, outer/shell 1.254, decay -0.0455, and negative `added_work_efficiency`.
- The current next physics step should keep the same fixed setup and use the conservative 9/8 threshold-robust floor for any passive narrow-needle continuation. Keep 41^3, neutral lattice, stronger sponge, inner-sponge-edge source, matched primary work per physical source area, frequency 0.92, and radius-5 shell metrics fixed.
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
python main.py prototype-3d --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-audit --run-path runs\prototype_3d_20260617_152319 --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-source-sponge-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-sponge-strength-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-source-geometry-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-cubic-focus-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-cubic-confirmation-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-grid-confirmation-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-threshold-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-defect-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-radial-window-audit --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-defect-lift-sweep --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-interference-diagnostics --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-standing-persistence --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-transport-packet-audit --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-packet-lifecycle-audit --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-refocusing-engineering-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-refocusing-map-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --cutoff-offsets -0.2 -0.1 0 0.1 0.2 --phase-offset-deltas 0 --polarity-cutoff-offsets -0.2 -0.1 0 0.1 0.2
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --release-phase-island-refinement
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --phase-lock-needle-map first
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --threshold-robust-confirmation
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-amplitude-scale 0.5
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-amplitude-scales 0.1 0.2 0.35 0.5 --second-pulse-durations 2.0 1.0 --second-pulse-roles phase_matched
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-micro-map --micro-map-targets first_refocus --launch-time-offsets -0.8 -0.4 0 0.4 0.8 --second-pulse-phase-modes matched opposite plus_pi_4 minus_pi_4 --second-pulse-amplitude-scales 0.1 0.2
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-micro-map --micro-map-targets second_refocus --launch-time-offsets -0.8 -0.4 0 0.4 0.8 --second-pulse-phase-modes matched opposite plus_pi_4 minus_pi_4 --second-pulse-amplitude-scales 0.1 0.2
python main.py breathing-period-audit --control-root runs\source_normalized_resolution_20260616_233009
python main.py dt-control --config configs\long_validation_peak_0_92.json
python main.py artifact-controls --config configs\long_validation_peak_0_92.json
python -m unittest discover -s tests
```
