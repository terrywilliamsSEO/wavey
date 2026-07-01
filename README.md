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

This compares cutoff times `17.8`, `17.9`, `18.0`, `18.1`, and `18.2` for both `phase_offset` and `sign_flip` families. The report ranks rows by major shell-window peaks, refocus peaks, no shell exit, retention, outer/shell below `1.0`, decay rate closest to zero, and global outer false.

Run the passive release-phase island refinement preset with:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --release-phase-island-refinement
```

This keeps frequency fixed at `0.92`, uses `sign_flip_cutoff_minus_0p1` as the comparison reference, and maps cutoff offsets `-0.16`, `-0.14`, `-0.12`, `-0.10`, `-0.08`, `-0.06`, and `-0.04` for both the phase-offset and sign-flip/polarity families. The ranked report now orders rows by major shell-window peaks first, then refocus peaks, no shell exit, retention, outer/shell below `1.0`, decay closest to zero, and global outer false. It also includes a `release phase island stability` section that distinguishes a neighboring timing cluster from a single isolated best point.

Run the ultra-fine passive phase-lock needle map around cutoff `17.94` with:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --phase-lock-needle-map first
```

This is sign-flip-only and keeps the 41^3 neutral-lattice, stronger-sponge, inner-sponge-edge source, frequency `0.92`, matched-work, radius-5 shell-window setup fixed. The first preset maps cutoff offsets `-0.075`, `-0.070`, `-0.065`, `-0.060`, `-0.055`, `-0.050`, and `-0.045` around the same cutoff center. If a future first-pass result is isolated, use the tighter preset:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --phase-lock-needle-map tight
```

The cutoff-phase report includes `phase-lock needle width` and `event-threshold sensitivity audit` sections, plus `cutoff_phase_event_threshold_sensitivity.csv`, so a stronger peak count can be separated from peak-detector threshold sensitivity.

Run the threshold-robust passive refocusing confirmation with:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --threshold-robust-confirmation
```

This is sign-flip-only and maps only the narrow phase-lock cluster plus nearby controls at cutoffs `17.920`, `17.925`, `17.930`, `17.935`, `17.940`, `17.945`, and `17.950`. The report adds a `threshold-robust refocusing score` section that evaluates peak thresholds `0.25`, `0.30`, `0.35`, and `0.40`, ranks rows by conservative score first and default-threshold score second, and includes threshold-free shell-energy area, tail area after `t=50`, autocorrelation, spectral concentration, and return timing regularity.

Run the passive 3D resonator-layer control with:

```powershell
python main.py prototype-3d-resonator-layer-control --config configs\long_validation_peak_0_92.json
```

This is a narrow mechanism test, not a sweep. It keeps the same `41^3` neutral-lattice, stronger-sponge, inner-sponge-edge sign-flip cubic source, frequency `0.92`, matched-work, radius-5 shell-window setup fixed, maps only cutoffs `17.920` through `17.950`, and compares the no-resonator reference, a weak passive boundary-inner-edge resonator layer tuned near/slightly below/slightly above the drive frequency, a moderate-cubic passive resonator layer, a zero-coupling control, and a high-damping control. The resonator is passive: no external drive is applied to its auxiliary oscillator and the report records post-cutoff external work, resonator energy, lattice energy, coupling exchange, and energy-accounting error.

Build the read-only 3D release-phase return-map predictor from existing run artifacts with:

```powershell
python main.py prototype-3d-release-phase-return-map --run-roots runs\cutoff_phase_map_3d_20260619_162240 runs\cutoff_phase_map_3d_20260619_155704 runs\cutoff_phase_map_3d_20260619_145631 runs\resonator_layer_3d_20260619_175949
```

This command does not run new physics. It consumes existing cutoff/refocusing summaries, ranked outputs, threshold-robust scores, events, and timeseries where available, then writes a feature table, phase-bin summary, simple interpretable predictions, and five blind-confirmation cutoff recommendations.

Run the blind confirmation of that release-phase predictor with:

```powershell
python main.py prototype-3d-release-phase-blind-confirmation --config configs\long_validation_peak_0_92.json --cutoffs 17.932885 17.937885 17.9225 17.965 17.915
```

This is a fixed five-row confirmation, not a tuning pass. It keeps the same `41^3` neutral-lattice, stronger-sponge, inner-sponge-edge sign-flip cubic source, frequency `0.92`, matched-work, radius-5 shell-window setup fixed, with no active second pulses and no resonator layer. Current project state: the blind run classified as `release_phase_blind_confirmed`; both predicted strong rows preserved default 11/10 and strict 9/8, while the lower-edge and weak-control rows fell to strict 8/7.

Run the numerical validation of the blind-confirmed phase rule with:

```powershell
python main.py prototype-3d-release-phase-numerical-validation --config configs\long_validation_peak_0_92.json --cutoffs 17.932885 17.937885 17.9225 17.915
```

This is a fixed baseline/half-dt check of the pre-registered strong and lower-side controls, not a tuning pass. It keeps the same `41^3` neutral-lattice, stronger-sponge, inner-sponge-edge sign-flip cubic source, frequency `0.92`, matched-work, radius-5 shell-window setup fixed, with no active second pulses and no resonator layer. Quarter dt is available only through the explicit `--include-quarter-dt` flag. Current project state: the run classified as `release_phase_dt_sensitive`; half dt preserved strict 9/8 at `17.937885` but not at `17.932885`.

Run the fixed half-dt release-phase recentering map with:

```powershell
python main.py prototype-3d-release-phase-dt-recenter --config configs\long_validation_peak_0_92.json
```

This is a fixed half-dt-only map, not a tuning pass. It tests only cutoffs `17.930`, `17.9325`, `17.935`, `17.9375`, `17.940`, `17.9425`, `17.945`, `17.9475`, `17.950`, plus low-side controls `17.9225` and `17.915`, under the same `41^3` neutral-lattice, stronger-sponge, inner-sponge-edge sign-flip cubic source, frequency `0.92`, matched-work, radius-5 shell-window setup. Current project state: the run classified as `release_phase_half_dt_recentered`; half-dt strict 9/8 recentered to cutoffs `17.9375-17.945`.

Run the fixed quarter-dt release-phase proof pack with:

```powershell
python main.py prototype-3d-release-phase-proof-pack --config configs\long_validation_peak_0_92.json
```

This is a proof pack, not a discovery sweep. It tests only the recentered half-dt window at quarter dt: proof candidates `17.9375`, `17.940`, `17.9425`, and `17.945`, immediate controls `17.935` and `17.9475`, and low-side controls `17.9225` and `17.915`. It freezes the candidate card and checks predeclared gates for strict 9/8, no exit, global outer false, outer/shell below `1.0`, stable tail area, stable return timing, stable inward flux, and threshold-free candidate margin. Current project state: `runs\release_phase_proof_pack_3d_20260619_234039` classified as `release_phase_quarter_dt_proof_supported`; proof-candidate cutoffs `17.94-17.945` preserved strict clean 9/8.

Run the controlled release-phase resolution lift with:

```powershell
python main.py prototype-3d-release-phase-resolution-lift --config configs\long_validation_peak_0_92.json
```

This is a one-step scale checkpoint, not a resolution sweep. It defaults to one `51^3` candidate plus two fixed controls at quarter dt, recomputing cutoffs from target release phases instead of copying lower-resolution cutoff times. The fixed setup is neutral lattice, same physical domain, stronger sponge, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 physical shell window, no active second pulses, and no resonator layer. Current project state: `runs\release_phase_resolution_lift_3d_20260620_091834` classified as `release_phase_resolution_lift_failed`; the `51^3` candidate and controls all reached default 9/8 and conservative strict 7/6, so do not auto-run `61^3` or tune nearby phases from that result.

Run the read-only postmortem for the failed resolution lift with:

```powershell
python main.py prototype-3d-release-phase-resolution-postmortem
```

This command runs no physics. It compares the `41^3` proof-pack winning rows against the failed `51^3` candidate and controls using existing summary, threshold-robust, event, and timeseries artifacts. It answers whether `51^3` lost returns outright or whether returns moved/blurred below the frozen gate, then writes a one-row recalibration prediction. Current project state: `runs\release_phase_resolution_postmortem_3d_20260620_100043` classified as `resolution_lift_blurred_returns_no_predictive_recalibration`; it recommends no single recalibrated `51^3` retry from the current evidence.

Run the read-only modal audit across the proof pack, failed lift, postmortem, and central-burst contrast with:

```powershell
python main.py prototype-3d-release-phase-modal-audit
```

This command runs no physics. It compares the `41^3` proof-cluster rows, the failed `51^3` candidate and controls, and the central-burst best/repeated-contaminated rows using existing CSV artifacts. It reports shell-energy spectra, spectral concentration/bandwidth, autocorrelation decay, return timing jitter, peak widths, radial group velocity, radial packet width/spread, scalar shell-energy phase locking, neighboring radial-window energy proxies, and loose-vs-strict return-count shrinkage. Current project state: `runs\release_phase_modal_audit_3d_20260620_110344` classified as `resolution_blur_mechanism_supported`; it found the same dominant shell band at `41^3` and `51^3`, but the lifted rows have larger spectral bandwidth, outward tail-radius shift, strict 7/6 shrinkage, and no mechanism-derived retry.

Run the read-only dispersion/blur model with:

```powershell
python main.py prototype-3d-release-phase-dispersion-audit
```

This command runs no physics. It compares `41^3` proof rows against the failed `51^3` lift rows and reconstructs only deterministic source/shell geometry from the baseline config. It reports dominant shell frequency, modal bandwidth, return peak width, return spacing, tail-radius drift, radial packet width/spread, radial group velocity, shell-window leakage, source discretization, shell-window sampling, and spatial-phase-frame availability. Current project state: `runs\release_phase_dispersion_audit_3d_20260620_150931` classified as `scalable_blur_model_supported`: the blur is consistent and predictable across `51^3` rows, but no source-shaped candidate is recommended because true spatial shell phase frames were not stored.

Run the spatial phase instrumentation reproduction with:

```powershell
python main.py prototype-3d-spatial-phase-instrumentation --config configs\long_validation_peak_0_92.json
```

This is an instrumentation-only reproduction, not tuning. It reruns exactly one `41^3` proof row and one failed `51^3` lift candidate with the frozen passive setup, then exports shell displacement/velocity frames, radial and angular shell phase coherence, node/antinode stability maps, phase drift across return peaks, and a `41^3` vs `51^3` comparison. Current project state: `runs\spatial_phase_instrumentation_3d_20260620_170518` classified as `spatial_phase_decoherence_supported`: the `51^3` candidate loses shell/radial/angular phase coherence while radial spread and center shift do not explain the strict-count loss.

Run the read-only spatial phase precompensation design with:

```powershell
python main.py prototype-3d-spatial-phase-precompensation-design
```

This command runs no physics. It consumes the captured spatial phase frames and tries only low-dimensional correction bases: global phase offset, per-face offsets, cubic phase-strength multiplier, cubic sign-flip bias through the same basis, one simple angular harmonic, and a tiny release-phase nudge only if measured phase drift is stable. Current project state: `runs\spatial_phase_precomp_design_3d_20260620_175852` classified as `no_safe_phase_correction`; the low-dimensional fit had R2 `0.00531` and per-return global phase-error std `1.04098` radians, so no precompensated `51^3` candidate should be run from this evidence.

Run the read-only source-spectrum design audit with:

```powershell
python main.py prototype-3d-source-spectrum-design-audit
```

This command runs no physics. It asks whether the current continuous hard-cutoff source window injects carrier sidebands that could plausibly explain the `51^3` modal bandwidth growth and spatial decoherence, and whether a same-frequency, same-cutoff-phase, same-work smooth temporal envelope would theoretically narrow the source spectrum. Current project state: `runs\source_spectrum_design_audit_3d_20260620_181010` classified as `source_spectrum_narrowing_candidate_supported`; it authorized the completed fixed smooth-envelope test, not a sweep.

Run the fixed smooth-envelope `51^3` resolution-lift rescue test with:

```powershell
python main.py prototype-3d-smooth-envelope-resolution-lift --config configs\long_validation_peak_0_92.json
```

This is a fixed three-row physics test, not a source-shape sweep. It compares a same-command hard-cutoff reproduction at cutoff `17.9425`, a same-cutoff smooth `sin^2` candidate, and a smooth weak-side control at cutoff `17.915`, while keeping frequency `0.92`, release phase, work per physical source area, neutral lattice, stronger sponge, sign-flip cubic boundary source, `51^3`, and the radius-5 shell window fixed. Current project state: `runs\smooth_envelope_resolution_lift_3d_20260620_192501` classified as `smooth_envelope_no_rescue`: source sidebands were reduced, but strict counts and shell/radial/angular coherence worsened versus the hard control.

Run the fixed boundary phase-conjugate `51^3` mechanism test with:

```powershell
python main.py prototype-3d-boundary-phase-conjugate-control --config configs\long_validation_peak_0_92.json
```

This is a fixed measured-wavefront test, not patch-mask tuning. It reruns one `41^3` proof row to capture shell phase frames, freezes a coarse 96-patch boundary phase/amplitude candidate before running any `51^3` rows, then compares hard control, phase-conjugate candidate, shuffled-patch phase control, amplitude-only control, phase-only control, and wrong-return-target control at the same cutoff `17.9425`, release phase `0.5071`, frequency `0.92`, work per physical source area, neutral lattice, stronger sponge, sign-flip cubic boundary source, and radius-5 shell window. Current project state: `runs\boundary_phase_conjugate_3d_20260620_212918` classified as `boundary_phase_conjugate_no_rescue`: the candidate stayed default `9/8`, strict `7/6`, and loose `11/10`, did not improve shell/radial/angular coherence, and the shuffled patch control did not fail.

Run the read-only modal sparsity audit with:

```powershell
python main.py prototype-3d-modal-sparsity-audit
```

This command runs no physics. It consumes the existing `41^3` proof pack, failed `51^3` lift, spatial phase instrumentation, smooth-envelope, and boundary phase-conjugate artifacts, then compares return timing regularity, sparse spectral reconstruction, modal participation ratio, peak width versus modal density, and the hard/smooth/phase-conjugate/shuffled `51^3` controls. Current project state: `runs\modal_sparsity_audit_3d_20260620_231602` classified as `common_51_source_signature_supported`: the dramatic few-mode-to-20-plus-mode split was not proven, but the `51^3` source-shaping controls shared a tight reconstruction/participation signature and the same strict-count loss.

Run the read-only return-family gate audit with:

```powershell
python main.py prototype-3d-return-family-gate-audit
```

This command runs no physics. It consumes the proof pack, failed `51^3` lift, spatial phase instrumentation, smooth-envelope, phase-conjugate, and modal-sparsity artifacts, then asks whether strict `51^3` count loss is a real return-family weakening or a fixed-threshold/gate artifact. Current project state: `runs\return_family_gate_audit_3d_20260621_082543` classified as `return_family_weakened_not_gate_artifact`: return timing and comb occupancy remain coherent, but source-control off-comb energy ratio is high (`1.13162` mean) and rank-normalized strength is not compressed enough to explain the strict loss as a detector-only artifact.

Run the read-only off-comb leakage audit with:

```powershell
python main.py prototype-3d-off-comb-leakage-audit
```

This command runs no physics. It consumes the same proof/lift/spatial/smooth/phase-conjugate/modal-sparsity artifacts plus the return-family gate audit, then localizes the off-comb loss across radial, angular, outer-recycling, modal-sideband, spatial-pattern, and flux channels. Current project state: `runs\off_comb_leakage_audit_3d_20260621_085347` classified as `spatial_pattern_scrambling_supported`: radial leakage, modal sidebands, and delayed outer recycling did not separate from proof rows, while source-control spatial-pattern leakage rose from `0.495788` to `0.586679`.

Run the read-only return-pattern symmetry audit with:

```powershell
python main.py prototype-3d-return-pattern-symmetry-audit
```

This command runs no physics. It consumes the proof/lift/spatial/smooth/phase-conjugate/return-family/off-comb artifacts, then tests whether return-to-return pattern loss is rescued by sign, global phase, cubic rotation/reflection, angular sector shift, penalized sector permutation, or harmonic alignment. Current project state: `runs\return_pattern_symmetry_audit_3d_20260621_091511` classified as `pattern_symmetry_inconclusive`: alignment raises some `51^3` memory scores, but transform stability is low (`0.313696` mean) and source controls do not share one signature (`0.363636` share), so there is no mechanism-derived orientation, hopping, or phase-precession rescue.

Run the read-only passive branch closure report with:

```powershell
python main.py prototype-3d-branch-closure-report
```

This command runs no physics. It compiles the `41^3` proof evidence, failed `51^3` lift, negative source-shaping and patch-mask controls, modal sparsity, gate artifact, off-comb leakage, return-pattern symmetry, active-pulse, resonator, and central-burst evidence into one closure packet. Current project state: `runs\branch_closure_report_3d_20260621_093821` classified as `passive_scale_lift_branch_closed`: the branch is scientifically useful but not breakthrough-ready; the frozen claim is `41^3` structured refocusing, the frozen non-claim is no `51^3` scale validation, and future reopening requires a genuinely new stable spatial-pattern-memory mechanism.

Run the independent passive spatial-memory mechanism lab with:

```powershell
python main.py prototype-3d-spatial-memory-mechanism-lab --config configs\long_validation_peak_0_92.json
```

This is a new research branch, not a rescue of the closed passive scale-lift branch. It starts with a fixed `41^3` passive mechanism test over a neutral reference, weak anisotropy anchor, weak cubic degeneracy-splitting anchor, weak shell-band isolation profile, weak nonlinear phase-memory variant, and randomized equivalent-strength control. The primary metric is return-to-return shell spatial-pattern memory. The command exposes no cutoff/source-shape tuning surface and only runs an optional fixed `51^3` follow-up if the `41^3` mechanism test classifies as `spatial_memory_mechanism_supported`. Current project state: `runs\spatial_memory_mechanism_lab_3d_20260621_103028` classified as `spatial_memory_mechanism_supported` at `41^3`, with `cubic_degeneracy_split` best (`0.645969` memory versus neutral `0.486969` and randomized control `0.505821`), but the gated `51^3` follow-up did not preserve the advantage (`0.544617` versus neutral `0.579914` and randomized control `0.577519`), so this is a mechanism clue rather than scale validation.

Run the fixed 41^3 cubic-memory tradeoff map with:

```powershell
python main.py prototype-3d-cubic-memory-tradeoff-map --config configs\long_validation_peak_0_92.json
```

This command is a mechanism-specific local map, not a continuation of the closed passive scale-lift branch. It keeps the neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic source, frequency `0.92`, cutoff `17.94`, matched work, and radius-5 shell metrics fixed. It tests neutral, cubic degeneracy split strengths `0.25x/0.5x/1.0x/1.5x`, sign-flipped cubic split at `0.5x/1.0x`, and randomized matched-strength controls at `0.5x/1.0x`. It runs `41^3` only by default and does not expose a `51^3`, `61^3`, cutoff, source-shape, active-pulse, or resonator path.

Current project state: `runs\cubic_memory_tradeoff_map_3d_20260621_142657` classified as `memory_only_tradeoff_supported`. The best memory row was `cubic_split_sign_flipped_0p5x` with memory `0.725354` versus neutral `0.486969` and randomized `0.504878`, but it fell to strict/default/loose `6/5`, `7/6`, `8/7`. The standard `1.0x` cubic split reproduced the earlier cleaner memory signal (`0.645969` versus randomized `0.628214`) but stayed at strict/default/loose `8/7`, `9/8`, `10/9`. All clean gates and energy accounting passed; no cubic row achieved `cubic_memory_tradeoff_supported`.

Run the read-only cubic-memory survivor-bias audit with:

```powershell
python main.py prototype-3d-cubic-memory-survivor-bias-audit
```

This command runs no physics. It reads the completed cubic-memory tradeoff map and compares spatial-pattern memory over surviving return peaks, equal first-N return indices, and neutral-predicted return windows with missing-window coverage tracked. Current project state: `runs\cubic_memory_survivor_bias_audit_3d_20260621_150538` classified as `cubic_memory_tradeoff_inconclusive`: standard cubic rows still show some matched-window memory gain, but the highest-memory sign-flipped rows have low neutral-window coverage, so the saved artifacts do not cleanly separate real same-window gain from survivor bias.

Run the fixed 41^3 isochronous cubic-memory anchor test with:

```powershell
python main.py prototype-3d-isochronous-cubic-memory-anchor --config configs\long_validation_peak_0_92.json
```

This command tests whether a weak cubic degeneracy split plus a fixed smooth radial compensation profile can preserve spatial-pattern memory while keeping return timing/comb score closer to the neutral reference. It runs a fixed `41^3` row set only: neutral reference, standard cubic split `0.5x/1.0x`, radial compensation only, isochronous cubic anchor `0.5x/1.0x`, and randomized matched-strength controls `0.5x/1.0x`. It does not expose cutoff tuning, `51^3`, `61^3`, source shaping, active pulses, resonators, or old-branch rescue logic. Current project state: `runs\isochronous_cubic_anchor_3d_20260621_184841` classified as `memory_only_anchor_tradeoff`: `isochronous_anchor_0p5x` improved memory (`0.631984` versus neutral `0.486969` and randomized `0.480804`) while preserving strict `9/8` and near-neutral comb, but off-comb energy worsened (`0.170717` versus neutral `0.156175`).

Run the fixed 41^3 isochronous-anchor cleanup control with:

```powershell
python main.py prototype-3d-isochronous-anchor-cleanup-control --config configs\long_validation_peak_0_92.json
```

This command tests only whether fixed smooth-taper cleanup profiles can keep the `isochronous_anchor_0p5x` memory/strict/comb gains while reducing the small off-comb penalty. It runs seven fixed `41^3` rows: neutral reference, randomized matched `0.5x`, current `isochronous_anchor_0p5x` reference, smooth taper, wide smooth taper, weaker compensation, and smooth radial compensation only. It does not tune cutoff, frequency, source, `51^3`, `61^3`, active pulses, resonators, or source shaping. Current result: `runs\isochronous_anchor_cleanup_3d_20260621_193641` classified as `cleanup_memory_only_tradeoff`. Wide smooth taper kept the memory/strict/comb gains (`0.631012`, strict `9/8`, comb `0.724866`) but off-comb stayed high (`0.171705`). Smooth taper reduced off-comb (`0.126083`) but dropped to strict `8/7` and comb `0.506173`.

Run the fixed 41^3 angular-mode cleanup control with:

```powershell
python main.py prototype-3d-angular-mode-cleanup-control --config configs\long_validation_peak_0_92.json
```

This command tests a different passive cleanup mechanism for the `isochronous_anchor_0p5x` off-comb penalty: weak angular high-mode damping on the shell, with a cubic-preserving variant and a randomized matched damping control. It runs eight fixed `41^3` rows: neutral reference, randomized equivalent `0.5x`, current `isochronous_anchor_0p5x` reference, weak angular cleanup only, anchor plus weak cleanup, anchor plus medium cleanup, anchor plus cubic-preserving cleanup, and randomized matched damping. It does not tune cutoff, frequency, source, `51^3`, `61^3`, active pulses, resonators, or taper profiles. Current result: `runs\angular_mode_cleanup_3d_20260621_210741` classified as `angular_cleanup_memory_only_tradeoff`. The best cleanup row, `anchor_0p5x_weak_angular_cleanup`, kept memory above neutral and both randomized controls (`0.601371` versus neutral `0.486969`, random `0.480804`, and random damping `0.538221`) and kept comb near neutral (`0.697852`), but dropped to strict `7/6` and raised off-comb to `0.204026` versus the anchor reference `0.170717`.

Run the fixed 41^3 sacred-geometry memory anchor test with:

```powershell
python main.py prototype-3d-sacred-geometry-memory-anchor --config configs\long_validation_peak_0_92.json
```

This command tests high-symmetry non-cubic passive geometry anchors, interpreted scientifically as icosahedral, dodecahedral, golden-ratio double-shell, and hex/flower shell stiffness patterns near the shell window. It runs seven fixed `41^3` rows: neutral reference, current `isochronous_anchor_0p5x` reference, icosahedral shell anchor, dodecahedral shell anchor, golden-ratio double-shell anchor, hex/flower shell projection anchor, and randomized matched-strength control. It keeps cutoff `17.94`, frequency `0.92`, source/work/sponge/shell setup fixed and does not tune cutoff/source/frequency, run `51^3`, run `61^3`, add source shaping, active pulses, or resonators. Current result: `runs\sacred_geometry_memory_anchor_3d_20260701_154048` classified as `sacred_geometry_memory_only_tradeoff`. The best row, `golden_ratio_double_shell_anchor`, reached memory `0.690023` versus neutral `0.486969`, randomized `0.508704`, and anchor reference `0.631984`, and reduced off-comb to `0.094257` versus anchor `0.170717`, but dropped to strict `7/6` and comb `0.546204`.

Run the fixed 41^3 golden/cubic hybrid anchor test with:

```powershell
python main.py prototype-3d-golden-cubic-hybrid-anchor --config configs\long_validation_peak_0_92.json
```

This command combines the complementary previous mechanisms: the `isochronous_anchor_0p5x` timing scaffold that preserved strict `9/8` and near-neutral comb, plus weak golden-ratio double-shell spatial/off-comb cleaning that reduced off-comb but lost strict/comb timing by itself. It runs seven fixed `41^3` rows: neutral reference, `isochronous_anchor_0p5x` reference, golden-ratio double-shell reference, three golden/cubic hybrid rows, and one randomized matched-strength hybrid control. It keeps cutoff `17.94`, frequency `0.92`, source/work/sponge/shell setup fixed and does not tune cutoff/source/frequency, run `51^3`, run `61^3`, add source shaping, active pulses, or resonators. Current result: `runs\golden_cubic_hybrid_anchor_3d_20260701_162316` classified as `hybrid_memory_only_tradeoff`. The best hybrid row, `hybrid_cubic_0p5x_golden_0p5x`, reached memory `0.600682` versus neutral `0.486969` and randomized `0.508722`, reduced off-comb to `0.072402` versus anchor `0.170717`, and passed clean gates, but dropped to strict/default/loose `7/6`, `9/8`, `10/9` with comb `0.584586`. No row achieved `golden_cubic_hybrid_supported`.

Run the firewalled central high-frequency scattering branch with:

```powershell
python main.py prototype-3d-central-burst-control --config configs\long_validation_peak_0_92.json
```

This is not a phase-rule improvement command. It disables boundary drive, active second pulses, resonators, and defect variants, then runs a neutral `41^3` central tiny-radius velocity-burst ladder across frequencies `0.92`, `1.84`, `3.68`, `5.52`, `7.36` and energy labels `low`, `medium`, `high`, `extreme`. It automatically half-dt checks the best baseline row. Current project state: `runs\central_burst_3d_20260620_103248` classified as `central_burst_transient`; the cleanest row and half-dt check produced only `1/0` returns, while the `0.92` repeated-count rows exited and had high outer/shell contamination.

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

It did not beat the no-pulse reference. Active reinjection is shelved unless a new mechanism changes the premise; the passive release-phase rule has since been blind-confirmed, half-dt recentered, and quarter-dt proof-packed, so do not tune nearby cutoffs based on the confirmation result.

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
- `cutoff_phase_event_threshold_sensitivity.csv`
- `cutoff_phase_threshold_robust_score.csv`
- `cutoff_phase_map_3d_summary.json`
- `cutoff_phase_map_3d_report.md`
- `cutoff_phase_map_timeseries.csv`
- `cutoff_phase_map_events.csv`
- `cutoff_phase_shell_energy_plot.png`
- `cutoff_phase_radius_width_plot.png`
- `cutoff_phase_flux_balance_plot.png`
- one lifecycle run folder per cutoff/phase/polarity timing variant

The cutoff-phase report includes a `release phase island stability` section when stability checks are available. It also reports `phase-lock needle width`, an event-threshold sensitivity audit for the best row and nearest neighbors, and a `threshold-robust refocusing score` section for conservative cross-threshold ranking.

When `prototype-3d-resonator-layer-control` is used, the control folder includes:

- `resonator_layer_report.md`
- `resonator_layer_summary.csv`
- `resonator_layer_threshold_robust_score.csv`
- `resonator_energy_timeseries.csv`
- `coupling_exchange_timeseries.csv`
- `resonator_layer_events.csv`
- `resonator_layer_summary.json`

The resonator-layer report includes `threshold-robust refocusing score`, `phase-lock cluster width`, `resonator energy accounting`, `contamination audit`, and `best conservative row` sections. Current project state: the first passive layer run classified as `no_resonator_still_wins`; no-resonator and zero-coupling preserved the strict six-cutoff 9/8 cluster, while coupled resonator rows dropped to strict 8/7 despite zero post-cutoff external work and passing energy accounting.

When `prototype-3d-release-phase-return-map` is used, the analysis folder includes:

- `release_phase_return_map_report.md`
- `release_phase_feature_table.csv`
- `release_phase_predictions.csv`
- `release_phase_binned_summary.csv`
- `release_phase_return_map_summary.json`

The report includes `predictive phase rule` and `blind confirmation recommendation` sections. Current project state: the read-only return map classified as `release_phase_predictive_rule_supported`; the best cluster centers near phase `0.500554` cycles, strict 9/8 preservation spans about `0.491-0.5232` cycles in reference-compatible rows, and default 11/10 rows occupy the narrower `0.4956-0.5048` phase pocket.

When `prototype-3d-release-phase-blind-confirmation` is used, the control folder includes:

- `release_phase_blind_confirmation_report.md`
- `release_phase_blind_confirmation_summary.csv`
- `release_phase_blind_confirmation_prediction_check.csv`
- `release_phase_blind_confirmation_summary.json`
- one lifecycle run folder per tested cutoff

The blind-confirmation report includes fixed-setup, prediction-check, and threshold-free metric sections. Current project state: `runs\release_phase_blind_confirmation_3d_20260619_210435` classified as `release_phase_blind_confirmed`.

When `prototype-3d-release-phase-numerical-validation` is used, the control folder includes:

- `release_phase_numerical_validation_report.md`
- `release_phase_numerical_validation_summary.csv`
- `release_phase_numerical_validation_comparison.csv`
- `release_phase_numerical_validation_summary.json`
- one lifecycle run folder per cutoff/dt variant

The numerical-validation report includes baseline/half-dt rows, strict 0.35/0.40 counts, threshold-free metrics, and dt-comparison deltas. Current project state: `runs\release_phase_numerical_validation_3d_20260619_214240` classified as `release_phase_dt_sensitive`.

When `prototype-3d-release-phase-dt-recenter` is used, the control folder includes:

- `release_phase_dt_recenter_report.md`
- `release_phase_dt_recenter_summary.csv`
- `release_phase_dt_recenter_threshold_robust_score.csv`
- `release_phase_dt_recenter_summary.json`
- one lifecycle run folder per tested cutoff

The dt-recenter report includes `half-dt recentered phase cluster`, `comparison to baseline blind-confirmed cluster`, `strict 9/8 preservation window`, `threshold-free lifecycle metrics`, and `recommended next numerical check` sections. Current project state: `runs\release_phase_dt_recenter_3d_20260619_220833` classified as `release_phase_half_dt_recentered`.

When `prototype-3d-release-phase-proof-pack` is used, the control folder includes:

- `candidate_card.md`
- `release_phase_proof_pack_report.md`
- `release_phase_proof_pack_summary.csv`
- `release_phase_proof_pack_threshold_robust_score.csv`
- `release_phase_proof_pack_gates.csv`
- `release_phase_proof_pack_summary.json`
- one lifecycle run folder per tested cutoff

The proof-pack report includes the frozen candidate setup, threshold-robust rows, phase-rule gates, threshold-free lifecycle metrics, and a recommendation for the next numerical scale check. Current project state: `runs\release_phase_proof_pack_3d_20260619_234039` classified as `release_phase_quarter_dt_proof_supported`.

When `prototype-3d-release-phase-resolution-lift` is used, the control folder includes:

- `release_phase_resolution_lift_report.md`
- `release_phase_resolution_lift_summary.csv`
- `release_phase_resolution_lift_threshold_robust_score.csv`
- `release_phase_resolution_lift_gates.csv`
- `release_phase_resolution_lift_summary.json`
- one lifecycle run folder per tested grid/phase row

The resolution-lift report includes fixed setup, pass/fail gates, threshold-robust rows, threshold-free lifecycle metrics, energy-accounting fields, and the final classification. Current project state: `runs\release_phase_resolution_lift_3d_20260620_091834` classified as `release_phase_resolution_lift_failed`.

When `prototype-3d-release-phase-resolution-postmortem` is used, the read-only output folder includes:

- `release_phase_resolution_postmortem_report.md`
- `release_phase_resolution_postmortem_summary.csv`
- `release_phase_resolution_peak_comparison.csv`
- `release_phase_resolution_recalibration_prediction.csv`
- `release_phase_resolution_postmortem_summary.json`

The postmortem report includes event-threshold shrinkage, arrival/refocus timing shifts, peak amplitudes, tail area, autocorrelation, spectral concentration, radial group velocity, shell-window radial alignment, packet width/spread, return phases, and a recalibration recommendation. Current project state: `runs\release_phase_resolution_postmortem_3d_20260620_100043` recommends `no_recalibrated_retry`.

When `prototype-3d-release-phase-modal-audit` is used, the read-only output folder includes:

- `release_phase_modal_audit_report.md`
- `modal_audit_summary.csv`
- `shell_spectrum_comparison.csv`
- `return_timing_jitter.csv`
- `radial_packet_width_comparison.csv`
- `phase_coherence_comparison.csv`

The modal audit report compares the `41^3` proof cluster, failed `51^3` lift rows, and central HF burst contrast without running physics. Current project state: `runs\release_phase_modal_audit_3d_20260620_110344` classified as `resolution_blur_mechanism_supported`: same dominant shell band, larger `51^3` bandwidth, outward tail-radius shift, loose-return recovery, strict-count shrinkage, and no mechanism-derived next candidate.

When `prototype-3d-release-phase-dispersion-audit` is used, the read-only output folder includes:

- `release_phase_dispersion_audit_report.md`
- `dispersion_blur_model_summary.csv`
- `dispersion_feature_comparison.csv`
- `source_discretization_comparison.csv`
- `shell_window_scaling_comparison.csv`
- `spatial_phase_coherence_audit.csv`
- `dispersion_blur_prediction.csv`
- `return_peak_width_comparison.csv`
- `release_phase_dispersion_audit_summary.json`

The dispersion audit report asks whether the `51^3` blur is predictable enough to justify a mechanism-derived correction. Current project state: `runs\release_phase_dispersion_audit_3d_20260620_150931` classified as `scalable_blur_model_supported`, but the prediction row remains `none` because true spatial shell phase frames are missing.

When `prototype-3d-spatial-phase-instrumentation` is used, the control folder includes:

- `spatial_phase_instrumentation_report.md`
- `spatial_phase_instrumentation_summary.csv`
- `spatial_phase_threshold_robust_score.csv`
- `spatial_phase_event_threshold_counts.csv`
- `spatial_phase_lifecycle_timeseries.csv`
- `spatial_phase_lifecycle_events.csv`
- `spatial_phase_frame_index.csv`
- `shell_displacement_frames.csv`
- `shell_velocity_frames.csv`
- `radial_shell_phase_frames.csv`
- `shell_phase_coherence_by_radius.csv`
- `angular_shell_phase_coherence.csv`
- `node_antinode_stability_maps.csv`
- `phase_drift_across_return_peaks.csv`
- `spatial_phase_41_vs_51_comparison.csv`
- `spatial_phase_instrumentation_summary.json`

The spatial-phase instrumentation report captures true shell displacement/velocity frames at loose return peaks while preserving default/strict event scoring. Current project state: `runs\spatial_phase_instrumentation_3d_20260620_170518` classified as `spatial_phase_decoherence_supported`. The later phase-precompensation design rejected spatial correction, while the later source-spectrum audit supports only a narrow temporal smoothing candidate.

When `prototype-3d-spatial-phase-precompensation-design` is used, the control folder includes:

- `phase_precompensation_design_report.md`
- `phase_error_modes.csv`
- `recommended_candidate.json`
- `rejected_overfit_corrections.csv`
- `spatial_phase_precompensation_design_summary.json`

The precompensation design report is a gate, not a physics run. Current project state: `runs\spatial_phase_precomp_design_3d_20260620_175852` classified as `no_safe_phase_correction`, with `recommended_candidate.json` marked `"recommended": false`.

When `prototype-3d-source-spectrum-design-audit` is used, the control folder includes:

- `source_spectrum_design_audit_report.md`
- `source_spectrum_summary.csv`
- `source_envelope_spectrum.csv`
- `smooth_envelope_candidate.json`
- `rejected_source_spectrum_options.csv`
- `source_spectrum_design_audit_summary.json`

The source-spectrum design report is a theory gate, not a physics run. Current project state: `runs\source_spectrum_design_audit_3d_20260620_181010` classified as `source_spectrum_narrowing_candidate_supported`: hard-cutoff far sideband fraction was `0.049396`, the same-release smooth envelope reduced it to `0.000516`, and `smooth_envelope_candidate.json` authorized the now-completed fixed smooth-envelope test.

When `prototype-3d-smooth-envelope-resolution-lift` is used, the control folder includes:

- `smooth_envelope_resolution_lift_report.md`
- `smooth_envelope_resolution_lift_summary.csv`
- `smooth_envelope_threshold_robust_score.csv`
- `smooth_envelope_spatial_comparison.csv`
- `smooth_envelope_resolution_lift_gates.csv`
- `smooth_envelope_source_spectrum_check.csv`
- `smooth_envelope_event_threshold_counts.csv`
- `smooth_envelope_lifecycle_timeseries.csv`
- `smooth_envelope_lifecycle_events.csv`
- `smooth_envelope_spatial_phase_frame_index.csv`
- `smooth_envelope_radial_shell_phase_frames.csv`
- `smooth_envelope_shell_phase_coherence_by_radius.csv`
- `smooth_envelope_angular_shell_phase_coherence.csv`
- `smooth_envelope_node_antinode_stability_maps.csv`
- `smooth_envelope_phase_drift_across_return_peaks.csv`
- `smooth_envelope_resolution_lift_summary.json`

The smooth-envelope rescue report is a physics result, not a design gate. Current project state: `runs\smooth_envelope_resolution_lift_3d_20260620_192501` classified as `smooth_envelope_no_rescue`: source bandwidth ratio fell to `0.301083`, but the candidate dropped to default `9/8` and strict `7/6`, coherence moved away from the hard-control and `41^3` proof values, and the weak-side smooth control performed similarly.

When `prototype-3d-boundary-phase-conjugate-control` is used, the control folder includes:

- `boundary_phase_conjugate_report.md`
- `boundary_phase_conjugate_summary.csv`
- `boundary_phase_conjugate_threshold_robust_score.csv`
- `boundary_phase_conjugate_spatial_comparison.csv`
- `boundary_phase_conjugate_gates.csv`
- `boundary_phase_conjugate_event_threshold_counts.csv`
- `boundary_phase_conjugate_lifecycle_timeseries.csv`
- `boundary_phase_conjugate_lifecycle_events.csv`
- `boundary_phase_conjugate_spatial_phase_frame_index.csv`
- `boundary_phase_conjugate_proof_spatial_phase_frame_index.csv`
- `boundary_phase_conjugate_proof_shell_displacement_frames.csv`
- `boundary_phase_conjugate_proof_shell_velocity_frames.csv`
- `boundary_phase_conjugate_shell_phase_coherence_by_radius.csv`
- `boundary_phase_conjugate_angular_shell_phase_coherence.csv`
- `boundary_phase_conjugate_design.csv`
- `boundary_phase_conjugate_candidate.json`
- `boundary_phase_conjugate_summary.json`

The boundary phase-conjugate report is a fixed mechanism result. Current project state: `runs\boundary_phase_conjugate_3d_20260620_212918` classified as `boundary_phase_conjugate_no_rescue`: the 96-patch candidate did not improve strict `7/6` counts or shell/radial/angular coherence versus the hard `51^3` control, while clean no-exit/global-outer/work gates passed.

When `prototype-3d-modal-sparsity-audit` is used, the control folder includes:

- `modal_sparsity_audit_report.md`
- `modal_sparsity_summary.csv`
- `sparse_spectral_reconstruction.csv`
- `modal_participation_ratio.csv`
- `return_timing_width_comparison.csv`
- `peak_width_modal_density_relation.csv`
- `modal_sparsity_audit_summary.json`

The modal sparsity audit is read-only. Current project state: `runs\modal_sparsity_audit_3d_20260620_231602` classified as `common_51_source_signature_supported`: proof rows averaged `9` modes for 99% reconstruction, all `51^3` rows averaged `17.46`, and the source-control modal-participation CV was only `0.00242`, so the fixed source-shaping attempts do not separate from the hard `51^3` failure.

When `prototype-3d-return-family-gate-audit` is used, the control folder includes:

- `return_family_gate_report.md`
- `return_family_gate_summary.csv`
- `return_window_occupancy.csv`
- `threshold_crossing_table.csv`
- `return_amplitude_by_index.csv`
- `return_family_gate_summary.json`
- `indexed_return_strength_plot.png`
- `threshold_crossings_plot.png`
- `comb_score_plot.png`
- `off_comb_energy_ratio_plot.png`

The return-family gate audit is read-only. Current project state: `runs\return_family_gate_audit_3d_20260621_082543` classified as `return_family_weakened_not_gate_artifact`: strict major count drops by `1.63333` on average, period timing remains coherent, occupancy is preserved relative to proof, but off-comb energy is too high and late-return area survival is lower, so strict loss should not be treated as a pure fixed-threshold artifact.

When `prototype-3d-off-comb-leakage-audit` is used, the control folder includes:

- `off_comb_leakage_report.md`
- `off_comb_leakage_summary.csv`
- `radial_leakage_by_window.csv`
- `angular_leakage_by_sector.csv`
- `outer_recycling_correlation.csv`
- `modal_sideband_leakage.csv`
- `spatial_pattern_leakage.csv`
- `off_comb_leakage_summary.json`
- `radial_leakage_plot.png`
- `angular_coherence_plot.png`
- `outer_recycling_plot.png`
- `modal_sidebands_plot.png`
- `pattern_similarity_decay_plot.png`

The off-comb leakage audit is read-only. Current project state: `runs\off_comb_leakage_audit_3d_20260621_085347` classified as `spatial_pattern_scrambling_supported`: the strongest supported separator is return-to-return spatial-pattern leakage, not radial drift, modal sidebands, or outer-window recycling. Treat this as failure localization, not permission to tune detector gates or source masks.

When `prototype-3d-return-pattern-symmetry-audit` is used, the control folder includes:

- `return_pattern_symmetry_report.md`
- `return_pattern_symmetry_summary.csv`
- `return_pair_alignment.csv`
- `transform_stability.csv`
- `harmonic_pattern_similarity.csv` when angular sector artifacts are available
- `return_pattern_symmetry_summary.json`
- `raw_vs_aligned_similarity_plot.png`
- `transform_stability_plot.png`
- `symmetry_rescue_margin_plot.png`

The return-pattern symmetry audit is read-only. Current project state: `runs\return_pattern_symmetry_audit_3d_20260621_091511` classified as `pattern_symmetry_inconclusive`: sign/phase/sector/harmonic alignment can improve some saved `51^3` return-pair similarities, but the chosen transforms are unstable and source controls do not share a coherent transform signature. Treat this as no permission to run orientation-drift, cubic-hopping, phase-precession, source-mask, cutoff, detector, or larger-grid follow-ups.

When `prototype-3d-branch-closure-report` is used, the control folder includes:

- `branch_closure_report.md`
- `branch_closure_summary.csv`
- `branch_closure_evidence_chain.csv`
- `branch_closure_claims.csv`
- `branch_closure_forbidden_paths.csv`
- `branch_closure_reopen_criteria.csv`
- `branch_closure_summary.json`

The branch-closure report is read-only. Current project state: `runs\branch_closure_report_3d_20260621_093821` classified as `passive_scale_lift_branch_closed`: keep the `41^3` proof claim, keep the `51^3` non-claim, treat the failure explanation as organized timing with lost spatial-pattern identity/return-family purity, and do not run cutoff tuning, source shaping, patch masks, smooth envelopes, active pulses, resonators, central bursts, `61^3`, detector retuning, or symmetry-lock runs from the current evidence.

When `prototype-3d-spatial-memory-mechanism-lab` is used, the control folder includes:

- `spatial_memory_mechanism_report.md`
- `spatial_memory_mechanism_summary.csv`
- `spatial_memory_by_return.csv`
- `mechanism_control_comparison.csv`
- `spatial_memory_mechanism_summary.json`
- `pattern_memory_plot.png`
- `off_comb_energy_plot.png`
- `comb_score_plot.png`
- `modal_participation_plot.png`
- supporting spatial-frame, threshold, lifecycle, event, and coherence CSVs prefixed with `spatial_memory_`

The spatial-memory mechanism lab is a separate passive research branch. It must not be described as a direct `51^3` rescue unless a fixed mechanism first improves `41^3` return-to-return spatial-pattern memory, preserves clean gates, and beats the randomized equivalent-strength control.

When `prototype-3d-cubic-memory-tradeoff-map` is used, the control folder includes:

- `cubic_memory_tradeoff_report.md`
- `cubic_memory_tradeoff_summary.csv`
- `cubic_memory_by_return.csv`
- `cubic_tradeoff_control_comparison.csv`
- `cubic_memory_tradeoff_summary.json`
- `memory_vs_strict_count_plot.png`
- `off_comb_energy_plot.png`
- `comb_score_plot.png`
- `modal_participation_plot.png`
- supporting spatial-frame, threshold, lifecycle, event, and coherence CSVs prefixed with `cubic_memory_`

The cubic-memory tradeoff map is `41^3` only by default. It asks whether cubic degeneracy splitting can keep the spatial-memory advantage while preserving strict `9/8`; it does not authorize cutoff tuning, `51^3`, `61^3`, source shaping, active pulses, or resonators.

Current result: `runs\cubic_memory_tradeoff_map_3d_20260621_142657` classified as `memory_only_tradeoff_supported`. Cubic splitting can improve spatial-pattern memory against neutral and matched randomized controls, but the tested local strengths/orientations did not preserve the strict `9/8` floor.

When `prototype-3d-cubic-memory-survivor-bias-audit` is used, the audit folder includes:

- `cubic_memory_survivor_bias_report.md`
- `cubic_memory_survivor_bias_summary.csv`
- `matched_return_memory.csv`
- `memory_by_return_index.csv`
- `cubic_memory_survivor_bias_summary.json`
- `memory_by_return_index_plot.png`
- `matched_window_memory_plot.png`
- `memory_vs_strict_count_plot.png`

The survivor-bias audit is read-only. Current result: `runs\cubic_memory_survivor_bias_audit_3d_20260621_150538` classified as `cubic_memory_tradeoff_inconclusive`: standard cubic `0.5x` kept a matched neutral-window gain (`0.561309` versus neutral `0.486969` and randomized `0.504878`) with `0.818182` pair coverage, while sign-flipped `0.5x` had the largest surviving memory (`0.725354`) but only `0.454545` neutral-window pair coverage. Treat the cubic memory gain as partially real but not free of survivor-window inflation.

When `prototype-3d-isochronous-cubic-memory-anchor` is used, the control folder includes:

- `isochronous_cubic_anchor_report.md`
- `isochronous_cubic_anchor_summary.csv`
- `isochronous_cubic_anchor_by_return.csv`
- `isochronous_anchor_control_comparison.csv`
- `isochronous_cubic_anchor_summary.json`
- `memory_vs_strict_count_plot.png`
- `off_comb_energy_plot.png`
- `comb_score_plot.png`
- `modal_participation_plot.png`
- supporting spatial-frame, threshold, lifecycle, event, and coherence CSVs prefixed with `isochronous_anchor_`

The isochronous cubic-memory anchor is a small fixed `41^3` mechanism test. It asks whether radial compensation can decouple the cubic memory gain from strict-count, comb, and off-comb penalties; it does not authorize cutoff tuning, `51^3`, `61^3`, source shaping, active pulses, or resonators. Current result: `runs\isochronous_cubic_anchor_3d_20260621_184841` classified as `memory_only_anchor_tradeoff`, not full `isochronous_cubic_anchor_supported`, because the best anchor kept strict count and comb but did not keep off-comb energy at or below neutral.

When `prototype-3d-isochronous-anchor-cleanup-control` is used, the control folder includes:

- `isochronous_anchor_cleanup_report.md`
- `isochronous_anchor_cleanup_summary.csv`
- `isochronous_anchor_cleanup_by_return.csv`
- `isochronous_anchor_cleanup_comparison.csv`
- `isochronous_anchor_cleanup_summary.json`
- `cleanup_memory_plot.png`
- `cleanup_strict_count_plot.png`
- `cleanup_comb_score_plot.png`
- `cleanup_off_comb_energy_plot.png`
- supporting spatial-frame, threshold, lifecycle, event, and coherence CSVs prefixed with `isochronous_anchor_cleanup_`

The cleanup control is a fixed `41^3` follow-up to the incomplete isochronous-anchor decoupling result. It asks whether smoothing/tapering the compensation can keep memory above neutral/random, preserve strict `9/8`, keep comb near neutral, and reduce off-comb to neutral plus a fixed tolerance. Current result: `runs\isochronous_anchor_cleanup_3d_20260621_193641` classified as `cleanup_memory_only_tradeoff`, not `isochronous_anchor_cleanup_supported`: cleanup rows split into off-comb-clean but strict/comb-damaged rows, and memory/strict/comb-preserving but off-comb-dirty rows.

When `prototype-3d-angular-mode-cleanup-control` is used, the control folder includes:

- `angular_mode_cleanup_report.md`
- `angular_mode_cleanup_summary.csv`
- `angular_mode_cleanup_by_return.csv`
- `angular_mode_cleanup_comparison.csv`
- `angular_mode_cleanup_summary.json`
- `angular_mode_spectrum.csv`
- `angular_cleanup_memory_plot.png`
- `angular_cleanup_strict_count_plot.png`
- `angular_cleanup_comb_score_plot.png`
- `angular_cleanup_off_comb_energy_plot.png`
- `angular_mode_spectrum_plot.png`
- supporting spatial-frame, threshold, lifecycle, event, and coherence CSVs prefixed with `angular_mode_cleanup_`

The angular-mode cleanup control is a fixed `41^3` mechanism follow-up to the incomplete isochronous-anchor decoupling result. It asks whether weak passive shell damping of high-angular components can reduce off-comb versus the anchor reference while keeping memory above neutral/randomized controls, preserving strict `9/8`, and keeping comb near neutral. It is not a taper continuation, not a closed-branch rescue, and not a default `51^3` path. Current result: `runs\angular_mode_cleanup_3d_20260621_210741` classified as `angular_cleanup_memory_only_tradeoff`, not `angular_cleanup_supported`: the cleanup rows preserved a memory signal but reduced strict counts and worsened off-comb rather than cleaning it.

When `prototype-3d-sacred-geometry-memory-anchor` is used, the control folder includes:

- `sacred_geometry_anchor_report.md`
- `sacred_geometry_anchor_summary.csv`
- `sacred_geometry_by_return.csv`
- `sacred_geometry_control_comparison.csv`
- `sacred_geometry_anchor_summary.json`
- `sacred_geometry_pattern_similarity.csv`
- `sacred_geometry_memory_plot.png`
- `sacred_geometry_strict_count_plot.png`
- `sacred_geometry_comb_score_plot.png`
- `sacred_geometry_off_comb_energy_plot.png`
- `sacred_geometry_pattern_similarity_plot.png`
- supporting spatial-frame, threshold, lifecycle, event, and coherence CSVs prefixed with `sacred_geometry_`

The sacred-geometry memory anchor is a fixed `41^3` mechanism follow-up to the incomplete off-comb decoupling problem. It asks whether quasi-isotropic non-cubic shell stiffness patterns can preserve spatial-pattern memory while reducing off-comb versus the `isochronous_anchor_0p5x` reference. It is not a source-shape, cutoff, frequency, active-pulse, resonator, default `51^3`, or `61^3` path. Current result: `runs\sacred_geometry_memory_anchor_3d_20260701_154048` classified as `sacred_geometry_memory_only_tradeoff`, not `sacred_geometry_anchor_supported`: non-cubic anchors improved memory and reduced off-comb, but did not preserve strict `9/8` or near-neutral comb.

When `prototype-3d-golden-cubic-hybrid-anchor` is used, the control folder includes:

- `golden_cubic_hybrid_report.md`
- `golden_cubic_hybrid_summary.csv`
- `golden_cubic_hybrid_by_return.csv`
- `golden_cubic_hybrid_control_comparison.csv`
- `golden_cubic_hybrid_mechanism_comparison.csv`
- `golden_cubic_hybrid_summary.json`
- `golden_cubic_hybrid_memory_plot.png`
- `golden_cubic_hybrid_strict_count_plot.png`
- `golden_cubic_hybrid_comb_score_plot.png`
- `golden_cubic_hybrid_off_comb_energy_plot.png`
- `golden_cubic_hybrid_mechanism_comparison_plot.png`
- supporting spatial-frame, threshold, lifecycle, event, and coherence CSVs prefixed with `golden_cubic_hybrid_`

The golden/cubic hybrid anchor is a fixed `41^3` mechanism follow-up to the split between isochronous timing support and golden-ratio off-comb cleanup. It asks whether a weak golden-ratio double-shell cleaner can be added to the isochronous cubic scaffold without losing strict `9/8` or near-neutral comb timing. It is not a source-shape, cutoff, frequency, active-pulse, resonator, default `51^3`, or `61^3` path. The first run in `runs\golden_cubic_hybrid_anchor_3d_20260701_162316` classified as `hybrid_memory_only_tradeoff`: hybrid rows preserved a memory signal and reduced off-comb below the isochronous anchor, but strict return count and near-neutral comb timing traded down. The report is `runs\golden_cubic_hybrid_anchor_3d_20260701_162316\golden_cubic_hybrid_report.md`.

When `prototype-3d-central-burst-control` is used, the control folder includes:

- `central_burst_report.md`
- `central_burst_summary.csv`
- `central_burst_threshold_counts.csv`
- `central_burst_timeseries.csv`
- `central_burst_events.csv`
- `central_burst_energy_audit.csv`
- `central_burst_summary.json`
- one per-variant central-burst folder with local timeseries/events

The central-burst report tracks energy accounting error, max displacement/velocity, near-shell peak/work, shell retention, thresholded return counts, outer/shell, global outer flag, radial packet width/spread, inward/outward flux, post-burst decay, threshold-free shell/tail area, autocorrelation, spectral concentration, return timing regularity, and the automatic half-dt check.

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
