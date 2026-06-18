# Agent Handoff Guide

This file is the first stop for any agent entering the project cold. Keep it short, current, and useful.

## Read Order

1. `README.md` for setup, commands, and output artifacts.
2. `ROADMAP.md` for the current next step and full decision log.
3. `docs/project_state.md` for the latest experimental conclusion and caution flags.
4. `docs/architecture.md` for the code map and physics-mode notes.
5. `docs/calibration.md` for numerical expectations and sanity checks.

## Current Rule Of Engagement

- Do not run broad long sweeps or broad 3D sweeps; the next step is one dense 41^3 two-variant standing-shell persistence confirmation.
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
- Do not phrase the 3D candidate as defect-required localization. Better wording: structured boundary-interference shell-window transport at 41^3, with standing-shell persistence still unconfirmed.
- The current next physics step is one dense 41^3 two-variant standing persistence confirmation: neutral cubic sign-flip repeat plus one deterministic random-phase negative control. Do not widen into a grid, source-geometry sweep, or more defect-parameter fishing.
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
python main.py breathing-period-audit --control-root runs\source_normalized_resolution_20260616_233009
python main.py dt-control --config configs\long_validation_peak_0_92.json
python main.py artifact-controls --config configs\long_validation_peak_0_92.json
python -m unittest discover -s tests
```
