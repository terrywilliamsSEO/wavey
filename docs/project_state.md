# Project State

Last updated: 2026-06-20

## One-Screen Summary

WaveEngine is a Python simulation-first experiment engine for a 2D coupled oscillator lattice with a configurable central defect/cavity, boundary drivers, sponge damping, diagnostics, and targeted validation controls. There is no dashboard yet.

The main candidate under study is the long-run drive-frequency `0.92` case from `configs/long_validation_peak_0_92.json`.

Current interpretation:

- The 0.92 candidate shows persistent post-cutoff breathing localization across sponge and time-step controls.
- Legacy fixed-domain `per_cell` source handling is not physically invariant and should be treated as reference-only.
- Source-normalized fixed-domain controls now make emitter effective area and injected work comparable across 41/63/81.
- Under source-normalized fixed-domain controls, 63x63 and 81x81 converge to the same refined physical radial peak at `10.0`, while 41x41 peaks at `5.0`.
- The latest source-normalized diagnostic classified the radial result as `coarse_grid_artifact_likely`.
- The global time-resolved breathing detector is now hardened: reports include raw diagnostic-frame period, hardened envelope-scale period, minimum separation, prominence threshold, smoothing window, retained-energy gating, and `subpeak_overcounting_possible`.
- The refreshed source-normalized 63x63 diagnostic now reports an envelope-scale period of `3.040` while flagging the old raw `1.689` diagnostic-frame period as subpeak overcounting.
- A controlled direct core-modal probe classified the 0.92 candidate as `boundary_transport_required`: source-normalized boundary references retained the 0.92 breathing family, but work-normalized core impulse/burst controls did not reproduce the same post-cutoff breathing, radial peak, and m=4 structure.
- The first targeted source-geometry transport control classified the candidate as `boundary_geometry_sensitive`: boundary left, boundary left-right, and boundary rotating m=4 variants retained breathing under matched work, while direct inner-ring/near-defect annulus variants did not reproduce the reference family.
- The 81x81 transport confirmation also classified as `boundary_geometry_sensitive`; `boundary_rotating_m4_81` became the best non-reference match.
- `annulus_radial_peak_63` produced a retained short-period response, but it did not match the reference period/radial structure closely enough to count as the same family.
- `annulus_radial_peak_81` retained more energy, but still looked like a separate short-period response rather than the reference family.
- Boundary-only work-per-length controls at 63x63 and 81x81 kept the `boundary_geometry_sensitive` classification; `boundary_rotating_m4_81` still reproduced the family after boundary flux density was normalized.
- The first 31^3 3D prototype was `inconclusive` under the original global shell metric: matched boundary-flux cubic forcing did not pass retained shell-energy criteria, and the global shell peak stayed near the outer boundary.
- The 3D failure-mode audit classified the run as `diagnostic_window_issue`: the global shell peak is outer-biased, but a small near-defect shell signal arrives late and should be tracked separately.
- The 3D source/sponge separation control classified as `source_sponge_separation_improves_near_shell`: driving at the inner sponge edge strengthens the retained near-defect shell signal and removes global outer-boundary dominance.
- A deeper inward source creates a huge early near-shell peak but does not retain it, so the current best 3D geometry is `source_at_inner_sponge_edge`, not the deeper gap source.
- The 3D sponge-strength control classified as `sponge_strength_suppresses_outer_contamination`: stronger sponge at the original width preserved the near-defect shell tail while lowering outer/near tail contamination.
- Weak sponge increased outer residue. Wider sponge variants retained the near-shell tail, but because the source location was held fixed, the widened sponge reintroduced full source/sponge overlap and the audit flagged global outer-window dominance.
- The 3D source-geometry control was rerun after clipping all selected face sources to the inner active-domain boundary. It classified again as `boundary_source_geometry_preserves_near_shell`: six-face cubic remains the cleanest retained near-shell boundary case, while uniform/reduced-face/random boundary variants are still global-outer-window flagged.
- Direct core and direct shell controls generated large early near-shell peaks but did not retain them, so they still do not reproduce the retained boundary tail.
- The focused 3D cubic-source control classified as `cubic_phase_structure_not_full_symmetry`: six-face cubic repeated cleanly and sign-flipped cubic stayed clean, while uniform/random phase controls were outer-window flagged.
- Mild cubic symmetry breaks, specifically removing one face and weakening two faces, also stayed clean. This means exact six-face balance is not isolated as the required ingredient at 31^3; the stronger clue is cubic phase structure with phase-timing sensitivity.
- The global phase-offset cubic variant was outer-window flagged, so do not overstate phase robustness.
- The cubic dt/sponge confirmation classified as `cubic_phase_dt_sponge_confirmed`: original cubic and sign-flipped cubic both survived deterministic repeat, half-dt, stronger-sponge, and weak-sponge checks with no global outer flags and no dt warnings.
- `cubic_phase_sign_flip_stronger_sponge` is now the best 3D boundary variant: near peak/work `4.16e-7`, near retention `0.656`, outer/near `0.739`, stable near radius median `5.05`, and arrival time `9.76`.
- The earlier 31^3 `0.75x` sign-flip amplitude-reduced probe stayed clean and motivated the later 41^3 amplitude/phase tolerance check.
- The tiny fixed-domain 31^3 to 41^3 grid confirmation classified as `sign_flip_resolution_lift_confirmed`: the 41^3 sign-flipped cubic stronger-sponge candidate preserved the clean near-shell tail with global outer false, retention `0.578`, outer/near `1.49`, near radius median `5.05`, and no dt warnings.
- The optional 41^3 original-cubic comparator did not pass the same cleanliness check because its outer/near ratio rose to `7.17`, while the 41^3 direct-shell negative control remained transient with retention `5.7e-7`.
- The calibrated 41^3 amplitude/phase threshold control classified as `amplitude_phase_tolerant`: the sign-flip family stayed clean from `0.5x` to `1.5x` amplitude and from `-pi/8` to `+pi/8` phase offset.
- Direct core and direct shell controls in that 41^3 threshold pass remained transient, with near retention around `2.5e-6` and `5.7e-7`.
- The calibrated 41^3 defect-ablation control classified as `defect_radius_sensitive`, not defect-required: the no-defect neutral lattice retained the fixed-window near-shell tail with retention `0.583`, outer/near `1.25`, radius median `5.05`, and global outer false.
- Individual stiffness, coupling, and damping neutralizations stayed close to the reference. The larger-radius variant was the main caution, with retention `0.519` and outer/near `2.01`.
- The radial-window neutral-lattice audit classified as `neutral_lattice_reproduces_shell_tail`: at the key radius-5 window, defect lift was `0.990` for retention and `0.848` for peak/work, with radial-profile correlation `0.981` and no radius shift.
- No scanned stable shell window showed defect lift above `1.5` for both retention and peak/work. The current 3D signal is not defect-dependent yet.
- The tiny stronger/different-defect lift sweep classified as `no_defect_lift_found`: max retention lift was `1.262`, max peak/work lift was `1.170`, and zero windows lifted both metrics above `1.5`.
- The 3D branch should now pivot from "defect well" language to structured boundary transport modes. Use the neutral lattice as the primary reference for the next 3D mechanism control.
- The first neutral-lattice interference diagnostic classified as `interference_supported_standing_weak`: random phase controls lost phase coherence and became outer-window flagged, while cubic phase controls stayed organized, but standing-shell persistence did not clear the stricter threshold.
- The dense two-variant standing-persistence check classified as `coherent_transport_not_standing`: sign-flip and phase-offset cubic variants retained clean shell-window energy and strong temporal/spectral coherence, but settled node/antinode masks, frame-to-mean shell patterns, and radial shell phase did not lock.
- The transport-packet audit classified the same clean cubic variants as `moving_transport_packet_supported`: both showed inward radial group velocity, inward-dominated shell flux, fast shell-window arrival, and near-zero angular drift. Current 3D wording should be structured cubic-boundary interference transport through the shell window, not defect-dependent localization and not a confirmed standing-shell mode.
- The extended packet lifecycle audit classified as `repeated_refocusing_supported`: both clean cubic variants showed multiple post-cutoff shell-window return peaks before eventual exit around `t=75-76`. The phase-offset variant is the current primary refocusing reference.
- The first refocusing-engineering control classified as `refocusing_improved`: a longer cutoff and a slightly higher frequency both improved refocus count, tail retention, decay rate, and outer/shell contamination without global outer-window flags.
- `cutoff_long` is the current best local refocusing variant: nine major shell-window peaks, eight refocus peaks, no detected shell exit, tail retention `0.269`, outer/shell `0.809`, decay `-0.0273`, and global outer false.
- The cutoff-frequency map classified as `local_map_improved_single_axis`: `cutoff_long + frequency_high` did not combine constructively and instead dropped to four major peaks, three refocus peaks, retention `0.0993`, outer/shell `1.70`, and exit at `t=70.4`.
- Current interpretation: cutoff timing and frequency can tune refocusing, but the two knobs are phase/timing coupled rather than independently additive.
- The first cutoff release-phase map classified as `cutoff_timing_improved`: cutoff `18` was sharply better than nearby `+/-0.5` offsets.
- The tighter cutoff/polarity timing map classified as `cutoff_phase_timing_island_supported`: `sign_flip_cutoff_minus_0p1` at cutoff `17.9` and cutoff phase `0.468` cycles reached nine major peaks, eight refocus peaks, retention `0.322`, outer/shell `0.660`, decay `-0.0237`, no exit, and no global outer flag.
- The first timed second-pulse control classified as `second_pulse_contaminated_or_inconclusive`: full-amplitude second pulses increased raw retention but reduced refocus count, worsened decay, and pushed outer/shell above `1.0`.
- The reduced-work phase-matched second-pulse check also classified as `second_pulse_contaminated_or_inconclusive`: 0.1x-0.5x pulses and shorter 1.0-duration pulses still reduced refocus count, worsened decay, pushed outer/shell above `1.0`, and had negative `added_work_efficiency`.
- The travel-time-adjusted first-refocus micro-map also classified as `second_pulse_contaminated_or_inconclusive`: empirical boundary-to-shell travel time was `9.44`, so the first-refocus target launch moved to `t=26.4`, but all active rows still had fewer refocus peaks, worse decay, outer/shell above `1.0`, and negative `added_work_efficiency`.
- The travel-time-adjusted second-refocus micro-map also classified as `second_pulse_contaminated_or_inconclusive`: the second-refocus target launch moved to `t=31.68`, but active rows still failed strict clean criteria. Best ranked active row reached retention `0.491`, but only six/five peaks, outer/shell `1.254`, decay `-0.0455`, and negative `added_work_efficiency`.
- Active second pulses are now shelved until a new mechanism justifies revisiting them; the passive release-phase rule is blind-confirmed around the phase-0.50 pocket with frequency fixed at `0.92`. Half-dt validation showed the original two-row strong pocket was dt-sensitive, and the fixed recentering map then showed the half-dt strict 9/8 window shifts upward to cutoffs `17.9375-17.945`.
- The fixed quarter-dt proof pack classified as `release_phase_quarter_dt_proof_supported`: proof-candidate cutoffs `17.94`, `17.9425`, and `17.945` preserved strict 9/8 with no exit, global outer false, outer/shell below `1.0`, stable tail area, stable return timing, stable inward flux, and positive threshold-free candidate margin. This remains a `41^3` proof-pack result, not a scale-validated claim.
- The controlled recalibrated `51^3` resolution lift classified as `release_phase_resolution_lift_failed`: the phase-targeted candidate at cutoff `17.9425`, phase `0.5071`, and both controls all fell to default 9/8 and conservative strict 7/6. The lifted packet stayed clean by no-exit/global-outer/outer-shell/energy gates, but strict 9/8 preservation and phase separation did not survive the lift.
- The read-only resolution postmortem classified as `resolution_lift_blurred_returns_no_predictive_recalibration`: the `51^3` rows still contain late return humps below frozen gates, but candidate and controls share the same count shrinkage, and timing/radial shifts do not isolate one honest recalibrated retry. Do not run the proposed 51^3 retry unless a new mechanism changes that prediction.
- The spatial phase instrumentation reproduction classified as `spatial_phase_decoherence_supported`: the failed `51^3` candidate loses shell/radial/angular shell phase coherence relative to the `41^3` proof row, while return spread does not grow and radial center shift is small. Treat the scale loss as spatial phase decoherence, not just coherent widening or shell-window misalignment.
- The read-only spatial phase precompensation design classified as `no_safe_phase_correction`: the allowed global/per-face/cubic/harmonic/release-nudge basis explained almost none of the matched shell-sector phase error (`R2=0.00531`) and per-return phase drift was unstable (`1.04098` rad), so no precompensated `51^3` candidate should run from the current frames.
- The read-only source-spectrum design audit classified as `source_spectrum_narrowing_candidate_supported`: the current continuous hard-cutoff source has a nontrivial far sideband fraction (`0.049396`), and a same-frequency/same-cutoff-phase/same-work smooth `sin^2` envelope theoretically reduces it to `0.000516`. It authorized the completed fixed smooth-envelope test, not any broad source-shaping sweep.
- The fixed smooth-envelope `51^3` source-spectrum rescue test classified as `smooth_envelope_no_rescue`: sideband reduction succeeded, but the smooth candidate dropped to default `9/8` and conservative strict `7/6`, worsened shell/radial/angular coherence versus the hard `51^3` control, matched the weak-side smooth control, and worsened tail-radius shift despite clean work/no-exit/global-outer gates.
- The fixed measured boundary phase-conjugate mirror classified as `boundary_phase_conjugate_no_rescue`: a frozen 96-patch boundary mask derived from the `41^3` proof row did not restore the `51^3` scale gate. Candidate, hard control, shuffled-patch, amplitude-only, phase-only, and wrong-return rows all stayed default `9/8`, strict `7/6`, and loose `11/10`; the candidate slightly worsened shell/radial coherence versus hard control and the shuffled patch control did not fail. Clean gates passed, so this is a wavefront-control negative result rather than contamination.
- The read-only modal sparsity audit classified as `common_51_source_signature_supported`: it did not prove a dramatic few-mode-to-broad-wave transition, but hard/smooth/phase-conjugate/shuffled `51^3` controls shared nearly identical sparse-reconstruction/modal-participation signatures and the same strict-count loss. Treat source shaping and patch-level wavefront shaping as exhausted for this branch unless a new mechanism appears.
- The read-only return-family gate audit classified as `return_family_weakened_not_gate_artifact`: timing and comb occupancy remain organized at `51^3`, but off-comb energy is high and rank-normalized return strength/prominence are not compressed enough to explain strict loss as a detector-only artifact. Treat the `51^3` strict drop as real family weakening under the current gate model.
- The read-only off-comb leakage audit classified as `spatial_pattern_scrambling_supported`: radial leakage, modal sideband leakage, and delayed outer/sponge recycling did not separate from proof rows, while source-control spatial-pattern leakage was higher (`0.586679` versus proof `0.495788`). Treat the current `51^3` failure localization as return-to-return spatial-pattern scrambling, not a justification for detector tuning, cutoff tuning, new source masks, or larger grids.
- The passive release-phase island refinement classified as `cutoff_phase_single_point_best`: `sign_flip_cutoff_minus_0p06` at cutoff `17.94` and cutoff phase `0.5048` cycles reached eleven major shell-window peaks, ten refocus peaks, retention `0.314`, outer/shell `0.631`, decay `-0.02396`, no exit, and no global outer flag.
- The ultra-fine passive phase-lock needle map classified as `cutoff_phase_timing_island_supported`, but its new width section classified the optimum as `narrow`, not broad: cutoffs `17.93`, `17.935`, and `17.94` all reached eleven/ten peaks, spanning only `0.01` cutoff units.
- The best ultra-fine row is `sign_flip_cutoff_minus_0p07`: cutoff `17.93`, release phase `0.4956`, eleven major peaks, ten refocus peaks, retention `0.317`, outer/shell `0.639`, no exit, and global outer false.
- The event-threshold sensitivity audit classified the best row as `best_count_threshold_sensitive`: the same best row recounts as 12/11, 11/10, or 9/8 as the major-peak threshold moves from `0.25` to `0.30` to `0.35`. Treat 11/10 as detector-sensitive until event traces or threshold logic are hardened.
- The threshold-robust confirmation classified the same narrow cluster as real enough to continue, but not as threshold-invariant 11/10. Cutoffs `17.93`, `17.935`, and `17.94` preserve a conservative 9/8 count under stricter thresholds `0.35` and `0.40`, while staying no-exit and global-outer false.
- Conservative claim: the phase-lock cluster preserves or improves the clean 9/8 refocusing family under stricter detection, not that 11/10 is threshold-invariant.
- The first passive boundary-inner-edge resonator-layer mechanism test classified as `no_resonator_still_wins`. The no-resonator reference and zero-coupling control preserved the six-cutoff strict 9/8 cluster, but all coupled resonator variants dropped to strict 8/7 despite clean no-exit/global-outer flags and zero post-cutoff external work.
- The read-only release-phase return map classified as `release_phase_predictive_rule_supported`: the best cluster centers near phase `0.500554` cycles, reference-compatible rows preserve strict 9/8 across about `0.491-0.5232` cycles, and default 11/10 rows occupy the narrower `0.4956-0.5048` phase pocket.
- The predictor recommended only a tiny blind confirmation: predicted strong cutoffs `17.932885` and `17.937885`, boundary/edge cutoffs `17.9225` and `17.965`, and weak negative control `17.915`.
- The blind confirmation classified as `release_phase_blind_confirmed`: predicted-strong cutoffs `17.932885` and `17.937885` preserved default 11/10 and strict clean 9/8, lower-edge `17.9225` and weak-control `17.915` fell to strict 8/7, and upper-edge `17.965` stayed strict 9/8 but only default 10/9.
- Do not call this exotic physics.
- Do not run broad long sweeps or broad 3D sweeps. The blind confirmation, half-dt numerical validation, half-dt recentering map, quarter-dt proof pack, requested `51^3` resolution lift, and read-only lift postmortem are complete; do not tune around the pre-registered/recentered/proof/lift cutoffs or expand the resonator layer, traps, rotation, medium shaping, defects, broad grid changes, frequency combinations, or active second-pulse tests without a new mechanism-specific reason.

## Latest Evidence

### Original Long 0.92 Diagnostics

Command:

```powershell
python main.py diagnose-run --config configs\long_validation_peak_0_92.json
```

Representative result:

- Best energy-well ratio: `0.506037`
- Retention score: `0.874573`
- Best event time: `47.76`
- Breathing period: `2.667`
- Breathing cycles: `7`
- Strongest angular mode: `m=4`
- Angular phase trend R^2: `0.891`

Interpretation: strong late post-cutoff breathing/localization candidate, distinct from short-sweep peak references.

### Sponge Artifact Controls

Command:

```powershell
python main.py artifact-controls --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\artifact_controls_20260616_121214\artifact_control_report.md`
- Classification: `sponge_sensitive`
- Breathing and retention survive stronger/wider sponge controls.
- Higher wider-sponge ratios are partly denominator-driven.
- Angular phase coherence is sponge-sensitive.

Important values:

| Variant | Ratio | Retention | Core E | Outer E | Period | Angular R^2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| original | 0.506 | 0.875 | 0.0550 | 0.1087 | 2.667 | 0.891 |
| stronger sponge | 0.554 | 0.882 | 0.0366 | 0.0660 | 3.200 | 0.542 |
| wider sponge | 0.640 | 0.875 | 0.0412 | 0.0643 | 2.667 | 0.006 |
| stronger+wider | 0.809 | 0.881 | 0.0206 | 0.0255 | 3.200 | 0.079 |

### Smaller-dt Control

Command:

```powershell
python main.py dt-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\dt_controls_20260616_121139\dt_control_report.md`
- Classification: `numerically_stable`
- Half-step `dt=0.02` preserved late event, retention, ratio, absolute core energy, and m=4 structure.
- Caveat: diagnostic-frame breathing period reported `4.0`, but full-resolution core-energy peaks estimated `2.98`.

Important values:

| Variant | dt | Ratio | Retention | Best Time | Core E | Period Source |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline | 0.04 | 0.506 | 0.875 | 47.76 | 0.0550 | diagnostic 2.667 |
| half step | 0.02 | 0.510 | 0.871 | 47.72 | 0.0563 | metric-core peak 2.98 |

### Matched-Proportion Larger Grid

Command:

```powershell
python main.py grid-control --config configs\long_validation_peak_0_92.json --larger-physical-duration 86
```

Latest summarized run:

- Local report: `runs\grid_controls_20260616_124645\grid_control_report.md`
- Classification: `grid_resistant_timing_shift`
- Breathing and m=4 structure survived on 63x63 when the larger domain was run longer.
- Best event shifted much later, proving this control confounds grid size with domain/travel distance.

### Fixed-Domain Grid Refinement

Command:

```powershell
python main.py fixed-domain-grid-control --config configs\long_validation_peak_0_92.json --include-81
```

Latest summarized run:

- Local report: `runs\fixed_domain_grid_controls_20260616_150109\fixed_domain_grid_control_report.md`
- Classification: `resolution_sensitive`
- No dt stability warnings.
- Breathing persists at 63x63 and 81x81.
- Physical radial peak shifts inward from `10.0` to `3.75`.
- Retention weakens at 81x81.

Important values:

| Grid | dx | Ratio | Retention | Best Time | Breathing | Period | Radial Peak | m=4 Strength | Similarity |
| ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 41 | 1.000 | 0.506 | 0.875 | 47.76 | true | 2.667 | 10.00 | 0.361 | 1.000 |
| 63 | 0.645 | 0.400 | 0.783 | 41.84 | true | 2.632 | 3.75 | 0.231 | 0.674 |
| 81 | 0.500 | 0.318 | 0.716 | 38.20 | true | 2.993 | 3.75 | 0.231 | 0.560 |

Current legacy conclusion: the 0.92 breathing localization survives as a phenomenon, but legacy `per_cell` radial structure and retention were confounded by source discretization. Use the source-normalized diagnostic below as the current fixed-domain resolution-control result.

### Resolution-Sensitivity Diagnostics

Command:

```powershell
python main.py resolution-diagnostics --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\resolution_diagnostics_20260616_161612\resolution_diagnostics_report.md`
- Classification: `mask_discretization_issue`
- Primary finding: core/defect masks are comparable, but the emitter/source mask is not physically invariant at 63x63.
- Source work per physical boundary length is within tolerance but elevated at 63x63.
- Secondary finding: 63x63 and 81x81 radial profiles converge inward, so the 41-grid radial peak likely has a coarse-grid component once the emitter issue is controlled.

Important values:

| Grid | dx | Ratio | Retention | Best Time | Period | Radial Peak | m=4 Strength | Work/Length | Emitter Area |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 41 | 1.000 | 0.506 | 0.875 | 47.76 | 2.667 | 10.00 | 0.361 | 0.159 | 160.0 |
| 63 | 0.645 | 0.400 | 0.783 | 41.84 | 2.632 | 3.75 | 0.231 | 0.206 | 203.1 |
| 81 | 0.500 | 0.318 | 0.716 | 38.20 | 2.993 | 3.75 | 0.231 | 0.163 | 158.0 |

Pairwise best radial correlations:

| Pair | Spatial Corr | Best Radial Corr | Tail Radial Corr | Radial Peak Shift |
| --- | ---: | ---: | ---: | ---: |
| 41 vs 63 | 0.739 | 0.878 | 0.609 | 6.25 |
| 41 vs 81 | 0.613 | 0.830 | 0.525 | 6.25 |
| 63 vs 81 | 0.675 | 0.964 | 0.722 | 0.00 |

Legacy conclusion: the old `per_cell` source made the emitter area and injected work non-invariant, especially at 63x63. Treat this run as the diagnostic that motivated source normalization, not as the main resolution-control result.

### Source-Normalized Resolution Diagnostics

Command:

```powershell
python main.py source-normalized-resolution-diagnostics --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\source_normalized_resolution_20260616_233009\source_normalized_resolution_report.md`
- Source normalization: `constant_total_work`
- Classification: `coarse_grid_artifact_likely`
- Primary finding: source geometry and injected work are now comparable across 41/63/81.
- Refined result: 63x63 and 81x81 converge at physical radial peak `10.0`, not the legacy `3.75`.
- 41x41 source-normalized peak is `5.0`, making the coarse grid the outlier under the controlled source.
- Detector update: the 63-grid raw diagnostic-frame period is still `1.689`, but the hardened envelope-scale period is `3.040` and the run is flagged `subpeak_overcounting_possible`.

Important source audit values:

| Grid | Source Amp | Effective Area | Effective Length | Injected Work | Work/Length |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 41 | 0.550 | 160.0 | 160.0 | 13.6886 | 0.085554 |
| 63 | 0.436 | 158.6 | 158.6 | 13.6886 | 0.085554 |
| 81 | 0.449 | 158.0 | 158.0 | 13.6886 | 0.085554 |

Important mode values:

| Grid | Ratio | Retention | Best Time | Envelope Period | Raw Frame Period | Radial Peak | m=4 Strength |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 41 | 0.485 | 0.829 | 52.00 | 2.547 | n/a | 5.00 | 0.303 |
| 63 | 0.324 | 0.863 | 44.24 | 3.040 | 1.689 | 10.00 | 0.124 |
| 81 | 0.328 | 0.853 | 43.64 | 2.850 | 2.566 | 10.00 | 0.116 |

Pairwise source-normalized radial correlations:

| Pair | Spatial Corr | Best Radial Corr | Tail Radial Corr | Radial Peak Shift |
| --- | ---: | ---: | ---: | ---: |
| 41 vs 63 | 0.713 | 0.920 | 0.855 | 5.00 |
| 41 vs 81 | 0.639 | 0.944 | 0.712 | 5.00 |
| 63 vs 81 | 0.728 | 0.965 | 0.820 | 0.00 |

### Breathing-Period Audit

Command:

```powershell
python main.py breathing-period-audit --control-root runs\source_normalized_resolution_20260616_215926
```

Latest summarized run:

- Local report: `runs\source_normalized_resolution_20260616_215926\breathing_period_audit\breathing_period_audit_report.md`
- Classification: `peak_detector_overcounts_subpeaks`
- Answer to the 63-grid question: the period `1.689` comes from counting small local maxima on a broad post-cutoff core-energy plateau.
- Full-resolution metric peaks with minimum separation recover envelope-scale periods:
  - `min_sep=1.5`: period `2.491`
  - `min_sep=2.0`: period `2.907`
  - `min_sep=2.5`: period `3.736`

Important values:

| Grid | Current Diagnostic Period | Metric Same Detector | Metric min_sep 1.5 | Metric min_sep 2.0 |
| ---: | ---: | ---: | ---: | ---: |
| 41 | 2.640 | 3.290 | 3.290 | 3.290 |
| 63 | 1.689 | 1.557 | 2.491 | 2.907 |
| 81 | 2.566 | 1.370 | 3.080 | 3.080 |

Current conclusion: the source-normalized 63-grid run does not clearly have a true doubled-frequency breathing envelope. The hardened detector treats the `1.689` value as raw subpeak overcounting and uses envelope-scale periods for breathing classification.

### Core-Modal Probe

Command:

```powershell
python main.py core-modal-probe --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\core_modal_probe_20260616_233711\core_modal_probe_report.md`
- Summary CSV: `runs\core_modal_probe_20260616_233711\core_modal_probe_summary.csv`
- Classification: `boundary_transport_required`
- Best matching core-probe run: `core_impulse_63`
- All variants were normalized to the `boundary_reference_63` pre-cutoff injected work, about `21.8221`.

Important values:

| Variant | Grid | Drive | Work | Retention | Diagnostic Envelope Period | Metric min_sep 1.5 | Raw Frame Period | Radial Peak | m4 Strength | Radial Sim | Frame Sim |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boundary_reference_63 | 63 | boundary | 21.822 | 0.863 | 3.040 | 2.491 | 1.689 | 10.00 | 0.124 | 1.000 | 1.000 |
| boundary_reference_81 | 81 | boundary | 21.822 | 0.853 | 2.850 | 3.080 | 2.566 | 10.00 | 0.116 | 0.965 | 0.721 |
| core_impulse_63 | 63 | core impulse | 21.822 | 0.449 | n/a | 22.32 | n/a | 3.75 | 0.0177 | 0.285 | 0.497 |
| core_burst_0p92_63 | 63 | core burst | 21.822 | 0.000006 | n/a | 3.090 | 1.900 | 1.25 | 0.0228 | 0.293 | 0.409 |
| core_impulse_81 | 81 | core impulse | 21.822 | 0.448 | n/a | 10.96 | 10.80 | 5.00 | 0.0084 | 0.294 | 0.495 |
| core_burst_0p92_81 | 81 | core burst | 21.822 | 0.000067 | n/a | 1.692 | 1.290 | 6.25 | 0.423 | 0.328 | 0.169 |

Interpretation:

- Boundary references reproduce the source-normalized 63/81 breathing family with matched injected work.
- Direct core impulse leaves a retained slow natural ringing tail, but it does not match the reference period, radial structure, or m=4 strength.
- Direct core bursts at 0.92 show tiny post-cutoff peak timing measurements but essentially no retained energy, so they are not counted as retained breathing.
- The immediate conclusion is cautious: under these work-normalized direct-core settings, the 0.92 retained breathing state appears to require boundary-driven transport.

### Transport Controls

Command:

```powershell
python main.py transport-controls --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\transport_controls_20260617_093201\transport_control_report.md`
- Summary CSV: `runs\transport_controls_20260617_093201\transport_control_summary.csv`
- Classification: `boundary_geometry_sensitive`
- Matched work target: `21.8221` before cutoff for every variant.
- Best non-reference match: `boundary_left_right_63`

Important values:

| Variant | Drive | Work | Retention | Envelope Period | Metric min_sep 1.5 | Raw Period | Radial Peak | m4 Strength | Radial Sim | Frame Sim |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boundary_reference_63 | boundary four-side | 21.822 | 0.863 | 3.040 | 2.491 | 1.689 | 10.00 | 0.124 | 1.000 | 1.000 |
| boundary_left_63 | boundary one-side | 21.823 | 0.816 | 2.860 | 3.024 | 1.990 | 11.25 | 0.186 | 0.982 | 0.368 |
| boundary_left_right_63 | boundary two-side | 21.822 | 0.795 | 1.960 | 2.976 | 2.072 | 5.00 | 0.234 | 0.978 | 0.644 |
| boundary_rotating_m4_63 | boundary rotating m4 | 21.823 | 0.866 | 3.400 | 2.513 | 1.860 | 10.00 | 0.226 | 0.945 | 0.355 |
| inner_ring_interface_63 | annulus burst | 21.822 | 0.0000015 | 2.200 | 2.730 | 1.293 | 5.00 | 0.195 | 0.525 | 0.370 |
| annulus_near_defect_63 | annulus burst | 21.822 | 0.000125 | 2.160 | 3.136 | 1.032 | 8.75 | 0.440 | 0.756 | 0.326 |
| annulus_radial_peak_63 | annulus burst | 21.822 | 0.264 | n/a | 1.831 | 1.457 | 7.50 | 0.194 | 0.810 | 0.465 |
| annulus_sector_one_side_63 | annulus sector | 21.822 | 0.000172 | n/a | 2.165 | 1.150 | 7.50 | 0.169 | 0.618 | 0.205 |
| annulus_rotating_m4_63 | annulus rotating m4 | 21.824 | 0.000214 | 4.720 | 2.360 | 2.000 | 8.75 | 0.397 | 0.821 | 0.340 |

Interpretation:

- Four-side boundary drive is not uniquely required: one-side, two-side, and rotating m=4 boundary variants all retained breathing under matched injected work.
- Boundary geometry matters. The best non-reference match was the left-right boundary source, with high radial similarity and better frame similarity than the other boundary variants.
- Direct inner/interface annulus and near-defect annulus sources produced m=4 content but almost no retained post-cutoff energy, so they do not reproduce the reference family.
- The radial-peak annulus source retained some energy, but its period and radial peak do not match the reference family; treat it as a possible separate forcing response, not a pass.
- This result was confirmed at 81x81 below.

### 81x81 Transport Confirmation

Command:

```powershell
python main.py transport-controls --config configs\long_validation_peak_0_92.json --grid-size 81
```

Latest summarized run:

- Local report: `runs\transport_controls_20260617_094822\transport_control_report.md`
- Summary CSV: `runs\transport_controls_20260617_094822\transport_control_summary.csv`
- Classification: `boundary_geometry_sensitive`
- Matched work target: `20.5277` before cutoff for every variant.
- Best non-reference match: `boundary_rotating_m4_81`

Important values:

| Variant | Drive | Work | Retention | Envelope Period | Metric min_sep 1.5 | Raw Period | Radial Peak | m4 Strength | Radial Sim | Frame Sim |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boundary_reference_81 | boundary four-side | 20.528 | 0.853 | 2.850 | 3.080 | 2.566 | 10.00 | 0.116 | 1.000 | 1.000 |
| boundary_left_81 | boundary one-side | 20.528 | 0.795 | 1.800 | 2.528 | 3.112 | 10.00 | 0.104 | 0.952 | 0.365 |
| boundary_left_right_81 | boundary two-side | 20.528 | 0.786 | 2.260 | 2.184 | 2.593 | 10.00 | 0.094 | 0.958 | 0.465 |
| boundary_rotating_m4_81 | boundary rotating m4 | 20.527 | 0.891 | 2.627 | 2.147 | 1.775 | 10.00 | 0.219 | 0.890 | 0.329 |
| inner_ring_interface_81 | annulus burst | 20.528 | 0.000528 | 1.640 | 1.704 | 0.580 | 6.25 | 0.328 | 0.265 | 0.101 |
| annulus_near_defect_81 | annulus burst | 20.528 | 0.0456 | n/a | 1.824 | 1.324 | 8.75 | 0.255 | 0.495 | 0.107 |
| annulus_radial_peak_81 | annulus burst | 20.528 | 0.506 | 1.707 | 1.712 | 1.771 | 6.25 | 0.0497 | 0.731 | 0.251 |
| annulus_sector_one_side_81 | annulus sector | 20.528 | 0.101 | 1.680 | 1.707 | 0.756 | 6.25 | 0.165 | 0.343 | 0.069 |
| annulus_rotating_m4_81 | annulus rotating m4 | 20.530 | 0.0492 | n/a | 1.756 | 1.698 | 8.75 | 0.274 | 0.501 | 0.107 |

Interpretation:

- The boundary-geometry classification survived fixed-domain refinement from 63x63 to 81x81.
- `boundary_rotating_m4_81` became the best non-reference match and had higher retention than the four-side uniform reference, but lower frame similarity. Treat this as boundary-geometry sensitivity, not proof of coherent rotation.
- One-side and two-side boundary variants still retained breathing and the refined radial peak at 10.0.
- Direct annulus variants still do not reproduce the reference family. `annulus_radial_peak_81` is a stronger retained short-period response, but it has period near 1.71, radial peak 6.25, weak m4, and low frame similarity.
- New confound: one-side and two-side boundary variants match total injected work, so work per physical boundary length is higher than in four-side variants. The next control should normalize boundary flux density.

### Boundary Work-Per-Length Controls

Commands:

```powershell
python main.py transport-controls --config configs\long_validation_peak_0_92.json --boundary-only --boundary-match-mode work_per_length --grid-size 63
python main.py transport-controls --config configs\long_validation_peak_0_92.json --boundary-only --boundary-match-mode work_per_length --grid-size 81
```

Latest summarized runs:

- 63x63 report: `runs\transport_controls_20260617_115911\transport_control_report.md`
- 81x81 report: `runs\transport_controls_20260617_120129\transport_control_report.md`
- Classification for both: `boundary_geometry_sensitive`

Important 63x63 values:

| Variant | Boundary Length | Work | Work/Length | Core E | Retention | Metric Period | Radial Peak | m4 | Radial Sim | Frame Sim |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boundary_reference_63 | 160 | 21.822 | 0.136388 | 0.0404 | 0.863 | 2.491 | 10.00 | 0.124 | 1.000 | 1.000 |
| boundary_left_63 | 40 | 5.456 | 0.136388 | 0.00984 | 0.816 | 3.024 | 11.25 | 0.186 | 0.982 | 0.368 |
| boundary_left_right_63 | 80 | 10.911 | 0.136388 | 0.0190 | 0.795 | 2.976 | 5.00 | 0.234 | 0.978 | 0.644 |
| boundary_rotating_m4_63 | 160 | 21.823 | 0.136392 | 0.114 | 0.866 | 2.513 | 10.00 | 0.226 | 0.945 | 0.355 |

Important 81x81 values:

| Variant | Boundary Length | Work | Work/Length | Core E | Retention | Metric Period | Radial Peak | m4 | Radial Sim | Frame Sim |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boundary_reference_81 | 160 | 20.528 | 0.128298 | 0.0431 | 0.853 | 3.080 | 10.00 | 0.116 | 1.000 | 1.000 |
| boundary_left_81 | 40 | 5.132 | 0.128298 | 0.0113 | 0.795 | 2.528 | 10.00 | 0.104 | 0.952 | 0.365 |
| boundary_left_right_81 | 80 | 10.264 | 0.128298 | 0.0232 | 0.786 | 2.184 | 10.00 | 0.094 | 0.958 | 0.465 |
| boundary_rotating_m4_81 | 160 | 20.527 | 0.128295 | 0.131 | 0.891 | 2.147 | 10.00 | 0.219 | 0.890 | 0.329 |

Interpretation:

- Work per physical boundary length is now controlled across one-side, two-side, and four-side boundary variants.
- The one-side and two-side responses did not disappear when their total work was reduced to match flux density; their absolute core energies dropped roughly with total work, but retention and radial similarity remained high.
- `boundary_rotating_m4_81` still reproduces the retained family and remains the strongest refined-grid non-reference match under this control.
- The 2D boundary mechanism is strong enough to justify a small 3D prototype, but not a broad 2D sweep.

### 3D Prototype

Command:

```powershell
python main.py prototype-3d --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\prototype_3d_20260617_152319\prototype_3d_report.md`
- Summary CSV: `runs\prototype_3d_20260617_152319\prototype_3d_summary.csv`
- Classification: `inconclusive`
- Grid: `31^3`
- Question tested: can matched boundary-flux waves organize around a spherical defect and produce retained post-cutoff shell breathing?

Important values:

| Variant | Drive | Phase | Work/Area | Shell Retention | Shell Period | Shell Radius | Radius Range | Core Fraction | Radial Sim |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| boundary_cubic_31 | boundary | cubic | 0.01119 | 0.00000128 | 3.36 | 31.03 | 21.65 | 0.0000011 | 1.000 |
| boundary_uniform_31 | boundary | uniform | 0.01119 | 0.00000186 | 2.40 | 25.26 | 15.88 | 0.0000028 | 0.000 |
| direct_core_31 | core | uniform | n/a | 0.00000358 | 3.36 | 5.05 | 0.00 | 0.744 | 0.000 |
| direct_shell_31 | shell | uniform | n/a | 0.00000128 | 2.56 | 6.50 | 2.89 | 0.190 | 0.000 |
| boundary_cubic_stronger_sponge_31 | boundary | cubic | 0.01119 | 0.00000091 | 2.84 | 31.03 | 21.65 | 0.0000010 | 0.000 |
| boundary_cubic_half_dt_31 | boundary | cubic | 0.01119 | 0.00000129 | 3.32 | 31.03 | 21.65 | 0.0000010 | 0.000 |

Interpretation:

- The first 3D prototype did not reproduce the 2D pattern.
- The cubic boundary reference showed tiny oscillations, but retained shell energy under the original global-shell metric was essentially zero and the global shell peak sat near the outer boundary, not around the spherical defect.
- Direct core forcing concentrated energy in the core, but that is explicitly not the success condition.
- Direct shell forcing did not create retained boundary-reference-like shell breathing.
- Stronger sponge and half-dt variants did not rescue the boundary cubic shell response.
- Future 3D reports should distinguish global radial-peak behavior from near-defect shell-window behavior.

### 3D Failure-Mode Audit

Command:

```powershell
python main.py prototype-3d-audit --run-path runs\prototype_3d_20260617_152319 --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\prototype_3d_20260617_152319\failure_mode_audit\prototype_3d_failure_audit_report.md`
- Summary CSV: `runs\prototype_3d_20260617_152319\failure_mode_audit\prototype_3d_failure_audit_summary.csv`
- Classification: `diagnostic_window_issue`
- Purpose: read the saved 31^3 prototype artifacts and separate near-defect shell transport from outer-boundary radial residue.

Important boundary-reference values:

| Metric | Value |
| --- | ---: |
| source/sponge overlap | 1.000 |
| high-sponge source overlap | 1.000 |
| global shell peak radius | 31.03 |
| near-defect shell peak/work fraction | 2.13e-8 |
| near-defect shell tail fraction of radial energy | 0.0758 |
| near-defect shell tail retention | 0.875 |
| outer-to-near tail energy ratio | 8.56 |
| first meaningful near-shell arrival time | 37.68 |

Interpretation:

- The original 3D shell metric was too global: it selected outer radial residue as the shell peak.
- A small near-defect shell signal does arrive late and retains within the near-shell window, but it is much weaker than the outer radial-window energy.
- Boundary source cells are entirely inside the sponge layer in the current 3D prototype; this is a geometry/numerics concern before any bigger 3D run.
- Stronger sponge and half-dt variants preserved the same audit pattern, so increasing grid size is not the next move.

### 3D Source/Sponge Separation Control

Command:

```powershell
python main.py prototype-3d-source-sponge-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\source_sponge_3d_20260617_161103\source_sponge_control_report.md`
- Summary CSV: `runs\source_sponge_3d_20260617_161103\source_sponge_control_summary.csv`
- Classification: `source_sponge_separation_improves_near_shell`
- Best variant: `source_at_inner_sponge_edge`
- Work matching: injected work per physical source area held at about `0.011957`.

Important values:

| Variant | Source d | Source/Sponge | Near Peak/Work | Near Retention | Near Radius Range | Outer/Near Tail | Global Peak R | Global Outer | Arrival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| source_at_outer_boundary_inside_sponge | 0 | 1.000 | 2.13e-8 | 0.875 | 0.00 | 8.56 | 31.03 | true | 37.68 |
| source_at_inner_sponge_edge | 6 | ~0 | 1.87e-7 | 0.699 | 0.00 | 3.88 | 13.71 | false | 10.16 |
| source_excluded_from_sponge_damping | 0 | 0.000 | 3.77e-8 | 0.835 | 1.44 | 10.84 | 19.49 | true | 34.24 |
| source_inside_domain_gap_from_sponge | 10 | 0.000 | 2.23e-2 | 0.0000078 | 4.33 | 3.04 | 9.38 | false | 3.04 |

Interpretation:

- Separating the boundary source from the sponge by moving it to the inner sponge edge strengthens the retained near-defect shell signal by about `8.8x` per unit source-area work.
- The inner-edge variant also reduces outer/near tail contamination by more than half and no longer lets the global shell peak sit in the outer window.
- Merely excluding current outer-boundary source cells from sponge damping is not enough; it leaves global outer-boundary dominance and worsens outer/near tail ratio.
- Moving the source deeper inside the domain creates a large early near-shell peak, but the post-cutoff near-shell tail does not retain, so it is not the current success case.

### 3D Sponge-Strength Control

Command:

```powershell
python main.py prototype-3d-sponge-strength-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\sponge_strength_3d_20260617_163440\sponge_strength_control_report.md`
- Summary CSV: `runs\sponge_strength_3d_20260617_163440\sponge_strength_control_summary.csv`
- Classification: `sponge_strength_suppresses_outer_contamination`
- Best variant: `stronger_sponge_inner_edge`
- Work matching: injected work per physical source area held at about `0.105044`.
- Source location: fixed at physical distance `6.0` from the outer boundary for every variant.

Important values:

| Variant | Sponge x | Width x | Source/Sponge | Near Peak/Work | Near Retention | Near Radius Range | Outer/Near Tail | Global Peak R | Global Outer | Arrival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| baseline_sponge_inner_edge | 1.0 | 1.0 | ~0 | 1.87e-7 | 0.699 | 0.00 | 3.88 | 13.71 | false | 10.16 |
| weak_sponge_inner_edge | 0.5 | 1.0 | ~0 | 1.87e-7 | 0.719 | 0.00 | 4.88 | 13.71 | false | 10.16 |
| stronger_sponge_inner_edge | 2.0 | 1.0 | ~0 | 1.86e-7 | 0.681 | 0.00 | 2.94 | 13.71 | false | 10.16 |
| wider_sponge_inner_edge | 1.0 | 2.0 | 1.00 | 1.71e-7 | 0.685 | 0.00 | 5.11 | 13.71 | true | 10.08 |
| stronger_wider_sponge_inner_edge | 2.0 | 2.0 | 1.00 | 1.57e-7 | 0.671 | 0.00 | 3.82 | 13.71 | true | 10.08 |

Interpretation:

- Stronger sponge at the original width is the cleanest result: it keeps the retained near-defect shell signal, preserves stable near radius and sensible arrival time, and lowers outer/near tail contamination from `3.88` to `2.94`.
- Weak sponge behaves as expected: near retention remains meaningful, but outer/near residue rises to `4.88`.
- Wider sponge is not clean under the fixed-source-location rule. It does not collapse near retention, but the widened damping region covers the driven layer (`source/sponge = 1.00`) and the audit flags the global peak as inside the expanded outer window.
- This supports a tiny 31^3 source-geometry comparison next, using the stronger-sponge inner-edge setup. It does not justify a larger 3D grid yet.

### 3D Source-Geometry Control

Command:

```powershell
python main.py prototype-3d-source-geometry-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\source_geometry_3d_20260618_092029\source_geometry_control_report.md`
- Summary CSV: `runs\source_geometry_3d_20260618_092029\source_geometry_control_summary.csv`
- Classification: `boundary_source_geometry_preserves_near_shell`
- Best boundary variant: `six_face_rotating_cubic_phase`
- Work matching: boundary variants held at about `0.105044` injected work per physical source area.
- Source/sponge overlap: `0` for all boundary variants after explicit face sources were clipped to the inner active-domain boundary.
- Rerun answer: one-face, two-face, and four-face variants still global-outer flag after clipping, so their outer-window contamination is not explained only by source/sponge/corner overlap.

Important values:

| Variant | Role | Faces | Near Peak/Work | Near Retention | Near Radius Range | Outer/Near Tail | Global Outer | Arrival |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| six_face_rotating_cubic_phase | coherent boundary | 6 | 1.86e-7 | 0.681 | 0.00 | 2.94 | false | 10.16 |
| six_face_uniform | baseline boundary | 6 | 1.76e-7 | 0.682 | 1.44 | 1.09 | true | 9.20 |
| one_face | coherent boundary | 1 | 1.40e-7 | 0.811 | 2.89 | 1.31 | true | 8.80 |
| two_opposite_faces | coherent boundary | 2 | 1.42e-7 | 0.769 | 2.89 | 1.35 | true | 8.80 |
| four_side_faces | coherent boundary | 4 | 1.59e-7 | 0.725 | 1.44 | 1.21 | true | 9.04 |
| phased_opposite_faces | coherent boundary | 2 | 1.51e-7 | 0.773 | 2.89 | 1.27 | true | 9.04 |
| random_phase_faces | random control | 6 | 6.30e-7 | 0.831 | 1.44 | 1.34 | true | 9.60 |
| direct_core_control | direct control | n/a | 6.53e-2 | 0.0000030 | 0.00 | 0.72 | false | 3.20 |
| direct_shell_control | direct control | n/a | 9.52e-2 | 0.00000069 | 4.33 | 3.91 | false | 3.20 |

Interpretation:

- Six-face cubic remains the cleanest boundary geometry because it preserves the retained near-shell tail and avoids global outer-window dominance.
- None of the tested source geometries produced a stronger clean retained tail than six-face cubic.
- Uniform, reduced-face, phased-opposite, and random-phase boundary variants can retain near-shell energy, but their global shell peak is still flagged in the outer window even with source/sponge overlap confirmed at `0`.
- The random-phase control produced the largest near peak/work among boundary variants, but it is not a clean pass because it is global-outer-window flagged.
- Direct core and direct shell forcing produce large early near-shell peak/work values but near retention collapses to about `1e-6`, so they are transient controls rather than retained shell-tail reproductions.

### 3D Cubic-Focus Control

Command:

```powershell
python main.py prototype-3d-cubic-focus-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\cubic_focus_3d_20260618_101501\cubic_focus_control_report.md`
- Summary CSV: `runs\cubic_focus_3d_20260618_101501\cubic_focus_control_summary.csv`
- Classification: `cubic_phase_structure_not_full_symmetry`
- Best boundary variant: `cubic_phase_sign_flip`
- Work matching: boundary variants held at about `0.105044` injected work per physical source area.
- Source/sponge overlap: `0` for all boundary variants.

Important values:

| Variant | Role | Faces | Phase | Sign/Offset | Near Peak/Work | Near Retention | Near Radius Range | Outer/Near Tail | Global Outer | Arrival |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| six_face_cubic_reference | reference | 6 | cubic | +1 / 0 | 1.86e-7 | 0.681 | 0.00 | 2.94 | false | 10.16 |
| six_face_cubic_repeat | repeat | 6 | cubic | +1 / 0 | 1.86e-7 | 0.681 | 0.00 | 2.94 | false | 10.16 |
| cubic_phase_sign_flip | cubic perturbation | 6 | cubic | -1 / 0 | 4.16e-7 | 0.666 | 1.44 | 0.877 | false | 9.76 |
| cubic_phase_offset | cubic perturbation | 6 | cubic | +1 / 1.571 | 1.82e-7 | 0.773 | 0.00 | 2.93 | true | 9.44 |
| cubic_missing_z_max_face | symmetry break | 5 | cubic | +1 / 0 | 1.74e-7 | 0.705 | 0.00 | 3.08 | false | 10.08 |
| cubic_face_imbalance | symmetry break | 6 | cubic | +1 / 0 | 1.82e-7 | 0.685 | 0.00 | 2.98 | false | 10.16 |
| six_face_uniform_same_coverage | non-cubic control | 6 | uniform | n/a | 1.76e-7 | 0.682 | 1.44 | 1.09 | true | 9.20 |
| random_phase_seed_31092_a/b | random control | 6 | face offsets | fixed seed | 6.30e-7 | 0.831 | 1.44 | 1.34 | true | 9.60 |
| direct_core_control | direct control | n/a | uniform | n/a | 6.53e-2 | 0.0000030 | 0.00 | 0.72 | false | 3.20 |
| direct_shell_control | direct control | n/a | uniform | n/a | 9.52e-2 | 0.00000069 | 4.33 | 3.91 | false | 3.20 |

Interpretation:

- Six-face cubic repeated exactly, so the previous clean case is reproducible under this deterministic setup.
- The sign-flipped cubic phase was the strongest clean boundary variant in near peak/work and outer/near tail ratio.
- Uniform and random phase controls are not clean passes because their global shell peak is still in the outer window, even though random phase has a high near peak/work value.
- Removing one face and adding mild face-amplitude imbalance did not dirty the cubic case. Perfect six-face balance is therefore not isolated as the required mechanism at 31^3.
- The global phase-offset cubic case was outer-window flagged, so phase timing is sensitive.
- Direct core/shell controls remain transient: they spike near-shell energy early but do not retain it post-cutoff.

### 3D Cubic dt/Sponge Confirmation

Command:

```powershell
python main.py prototype-3d-cubic-confirmation-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\cubic_confirmation_3d_20260618_110234\cubic_confirmation_control_report.md`
- Summary CSV: `runs\cubic_confirmation_3d_20260618_110234\cubic_confirmation_control_summary.csv`
- Classification: `cubic_phase_dt_sponge_confirmed`
- Best boundary variant: `cubic_phase_sign_flip_stronger_sponge`
- Baseline sponge: `2x` original 3D sponge strength; stronger confirmation variant: `3x` original.
- Work matching: boundary confirmation variants held at about `0.105044` injected work per physical source area, except the explicit amplitude-reduced probe.
- Stability: no dt warnings for any variant.

Important values:

| Variant | Role | dt | Sponge x vs baseline | Work/Area | Near Peak/Work | Near Retention | Near Radius Median | Near Radius Range | Outer/Near Tail | Global Outer | Arrival |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| six_face_cubic_reference | reference | 0.04 | 1.00 | 0.1050 | 1.86e-7 | 0.681 | 9.38 | 0.00 | 2.94 | false | 10.16 |
| six_face_cubic_half_dt | half dt | 0.02 | 1.00 | 0.1050 | 1.85e-7 | 0.681 | 9.38 | 0.00 | 2.95 | false | 10.16 |
| six_face_cubic_stronger_sponge | stronger sponge | 0.04 | 1.50 | 0.1050 | 1.85e-7 | 0.675 | 9.38 | 0.00 | 2.58 | false | 10.16 |
| six_face_cubic_weak_sponge | weak sponge | 0.04 | 0.75 | 0.1050 | 1.86e-7 | 0.688 | 9.38 | 0.00 | 3.30 | false | 10.16 |
| cubic_phase_sign_flip_reference | reference | 0.04 | 1.00 | 0.1050 | 4.16e-7 | 0.666 | 5.05 | 1.44 | 0.877 | false | 9.76 |
| cubic_phase_sign_flip_half_dt | half dt | 0.02 | 1.00 | 0.1050 | 4.14e-7 | 0.670 | 5.05 | 1.44 | 0.881 | false | 9.72 |
| cubic_phase_sign_flip_stronger_sponge | stronger sponge | 0.04 | 1.50 | 0.1050 | 4.16e-7 | 0.656 | 5.05 | 1.44 | 0.739 | false | 9.76 |
| cubic_phase_sign_flip_weak_sponge | weak sponge | 0.04 | 0.75 | 0.1050 | 4.17e-7 | 0.679 | 5.05 | 1.44 | 1.01 | false | 9.76 |
| cubic_phase_sign_flip_amplitude_reduced | amplitude reduced | 0.04 | 1.00 | 0.0591 | 4.16e-7 | 0.666 | 5.05 | 1.44 | 0.877 | false | 9.76 |
| direct_core_control | direct control | 0.04 | 1.00 | n/a | 6.53e-2 | 0.0000030 | 5.05 | 0.00 | 0.72 | false | 3.20 |
| direct_shell_control | direct control | 0.04 | 1.00 | n/a | 9.52e-2 | 0.00000069 | 5.05 | 4.33 | 3.91 | false | 3.20 |

Interpretation:

- The clean cubic-phase family survived stricter integration: half-dt preserved near peak/work, retention, arrival, radius, and outer/near tail metrics.
- Stronger sponge improved the sign-flip outer/near ratio from `0.877` to `0.739` while keeping retention above `0.65`.
- Weak sponge stayed clean but raised outer/near residue, especially for the original cubic phase.
- Direct core and shell forcing remain transient, so the boundary-transport distinction still holds in this 3D confirmation.
- The 0.75 amplitude-reduced sign-flip probe did not expose a threshold. The grid-confirmation and 41^3 threshold controls below supersede this as the current 3D reference path.

### 3D Grid Confirmation

Command:

```powershell
python main.py prototype-3d-grid-confirmation-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\grid_confirmation_3d_20260618_112610\grid_confirmation_3d_report.md`
- Summary CSV: `runs\grid_confirmation_3d_20260618_112610\grid_confirmation_3d_summary.csv`
- Classification: `sign_flip_resolution_lift_confirmed`
- Best variant: `sign_flip_stronger_sponge_31` by score, but the key candidate is `sign_flip_stronger_sponge_41`.
- Physical controls: same domain, defect physical radius, sponge width, source inner-edge distance, source physical width, drive frequency, cutoff time, stronger sponge, and work per physical source area.
- Stability: no dt warnings.

Important values:

| Variant | Grid | dx | Work/Area | Near Peak/Work | Near Retention | Near Radius Median | Near Radius Range | Outer/Near Tail | Global Outer | Arrival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| sign_flip_stronger_sponge_31 | 31 | 1.333 | 0.1050 | 4.16e-7 | 0.656 | 5.05 | 1.44 | 0.739 | false | 9.76 |
| sign_flip_stronger_sponge_41 | 41 | 1.000 | 0.1050 | 2.03e-7 | 0.578 | 5.05 | 0.00 | 1.49 | false | 9.36 |
| original_cubic_stronger_sponge_41 | 41 | 1.000 | 0.1050 | 7.05e-8 | 0.617 | 5.05 | 2.89 | 7.17 | false | 10.24 |
| direct_shell_41_negative_control | 41 | 1.000 | n/a | 9.79e-2 | 0.00000057 | 5.05 | 0.00 | 9.08 | false | 3.20 |

Interpretation:

- The clean sign-flipped cubic near-shell tail survives one controlled 3D resolution lift from 31^3 to 41^3.
- The 41^3 near peak/work is lower by about half, but remains the same order of magnitude and the retention remains meaningful.
- The 41^3 outer/near tail ratio worsens from `0.739` to `1.49`, but remains within the current controlled threshold and global outer remains false.
- The near-shell radius stays fixed at `5.05`, with tighter late-tail radius range at 41^3.
- Direct shell forcing at 41^3 is still transient, so direct local shell injection does not reproduce the retained boundary tail.
- Original cubic at 41^3 is not clean under the same criterion; sign-flip should remain the primary 3D reference.
- This was not permission for a broad 3D sweep. It only justified the tiny 41^3 threshold/phase check below.

### 3D Amplitude/Phase Threshold Control

Command:

```powershell
python main.py prototype-3d-threshold-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\threshold_control_3d_20260618_124524\threshold_control_3d_report.md`
- Summary CSV: `runs\threshold_control_3d_20260618_124524\threshold_control_3d_summary.csv`
- Classification: `amplitude_phase_tolerant`
- Best variant by score: `sign_flip_phase_neg_pi_8`
- Calibration: 41^3 reference was calibrated to the 31^3 sign-flip stronger-sponge target work per source area, `0.105027`.
- Stability: no dt warnings.

Important amplitude values:

| Variant | Amp x | Work/Area | Near Peak/Work | Near Retention | Outer/Near Tail | Global Outer | Arrival |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| sign_flip_amp_0_5 | 0.50 | 0.0263 | 2.03e-7 | 0.578 | 1.49 | false | 9.36 |
| sign_flip_amp_0_75 | 0.75 | 0.0591 | 2.03e-7 | 0.578 | 1.49 | false | 9.36 |
| sign_flip_amp_1_0_reference | 1.00 | 0.1050 | 2.03e-7 | 0.578 | 1.49 | false | 9.36 |
| sign_flip_amp_1_25 | 1.25 | 0.1641 | 2.03e-7 | 0.578 | 1.49 | false | 9.36 |
| sign_flip_amp_1_5 | 1.50 | 0.2363 | 2.03e-7 | 0.578 | 1.49 | false | 9.36 |

Important phase values:

| Variant | Phase | Work/Area | Near Peak/Work | Near Retention | Outer/Near Tail | Global Outer | Arrival |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| sign_flip_phase_neg_pi_8 | -pi/8 | 0.1050 | 2.05e-7 | 0.583 | 1.35 | false | 9.36 |
| sign_flip_phase_neg_pi_16 | -pi/16 | 0.1050 | 2.06e-7 | 0.573 | 1.42 | false | 9.36 |
| sign_flip_phase_pos_pi_16 | +pi/16 | 0.1050 | 1.96e-7 | 0.598 | 1.53 | false | 9.36 |
| sign_flip_phase_pos_pi_8 | +pi/8 | 0.1050 | 1.86e-7 | 0.635 | 1.56 | false | 9.36 |

Direct controls:

| Variant | Near Peak/Work | Near Retention | Outer/Near Tail | Global Outer | Arrival |
| --- | ---: | ---: | ---: | --- | ---: |
| direct_core_41_control | 6.22e-2 | 0.0000025 | 1.46 | false | 3.20 |
| direct_shell_41_control | 9.79e-2 | 0.00000057 | 9.08 | false | 3.20 |

Interpretation:

- The calibrated 41^3 sign-flip family did not show a lower-amplitude collapse across the tested `0.5x` to `1.5x` drive range.
- Normalized near-shell metrics were nearly invariant across amplitude, which is more consistent with a robust linear-ish transport family than a sharp threshold inside this tested range.
- Small phase offsets did not destroy the signal; even `+/-pi/8` stayed clean under matched work per physical source area.
- Direct core and direct shell controls remained transient, so the boundary-transport distinction still holds at 41^3.
- This strengthens the 3D candidate but still does not justify a broad 3D sweep.

### 3D Defect Dependence Control

Command:

```powershell
python main.py prototype-3d-defect-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\defect_control_3d_20260618_133637\defect_control_3d_report.md`
- Summary CSV: `runs\defect_control_3d_20260618_133637\defect_control_3d_summary.csv`
- Classification: `defect_radius_sensitive`
- Work matching: every variant was matched to the calibrated target work per physical source area, `0.105027`.
- Main comparison window: fixed physical near-shell window anchored to the original radius, `5.0` to `9.0`.
- Stability: no dt warnings.

Important fixed-window values:

| Variant | Radius x | k x | damping x | coupling x | Peak/Work | Retention | Radius Median | Radius Range | Outer/Near | Global Outer | Arrival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| current_defect_reference | 1.00 | 0.65 | 0.75 | 0.60 | 2.03e-7 | 0.578 | 5.05 | 0.00 | 1.49 | false | 9.36 |
| no_defect_neutral_lattice | 1.00 | 1.00 | 1.00 | 1.00 | 2.39e-7 | 0.583 | 5.05 | 1.44 | 1.25 | false | 9.68 |
| defect_stiffness_multiplier_1_0 | 1.00 | 1.00 | 0.75 | 0.60 | 2.04e-7 | 0.576 | 5.05 | 0.00 | 1.44 | false | 9.36 |
| defect_coupling_multiplier_1_0 | 1.00 | 0.65 | 0.75 | 1.00 | 2.32e-7 | 0.548 | 5.05 | 1.44 | 1.39 | false | 9.60 |
| defect_damping_multiplier_1_0 | 1.00 | 0.65 | 1.00 | 0.60 | 2.02e-7 | 0.556 | 5.05 | 0.00 | 1.54 | false | 9.36 |
| smaller_defect_radius | 0.75 | 0.65 | 0.75 | 0.60 | 2.22e-7 | 0.568 | 5.05 | 1.44 | 1.41 | false | 9.52 |
| larger_defect_radius | 1.25 | 0.65 | 0.75 | 0.60 | 1.78e-7 | 0.519 | 5.05 | 1.44 | 2.01 | false | 9.20 |

Interpretation:

- This does not support the stronger claim that the retained near-shell tail requires the spherical defect/cavity.
- The no-defect neutral lattice preserved the fixed-window tail and even lowered outer/near residue relative to the current-defect reference.
- Individual stiffness, coupling, and damping ablations did not collapse the signal.
- Larger defect radius mildly weakens/contaminates the tail by pushing outer/near just above the current threshold, so the pattern is radius-sensitive, but not defect-required under this control.
- Current best wording: boundary-driven, cubic-phase retained shell-window transport at 41^3, with some defect-radius sensitivity. Do not call it defect-localized yet.

### 3D Radial-Window Neutral-Lattice Audit

Command:

```powershell
python main.py prototype-3d-radial-window-audit --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\radial_window_audit_3d_20260618_152906\radial_window_audit_3d_report.md`
- Summary CSV: `runs\radial_window_audit_3d_20260618_152906\radial_window_audit_3d_summary.csv`
- Comparison CSV: `runs\radial_window_audit_3d_20260618_152906\radial_window_comparison.csv`
- Profile CSV: `runs\radial_window_audit_3d_20260618_152906\radial_window_profile_comparison.csv`
- Classification: `neutral_lattice_reproduces_shell_tail`
- Shell-window semantics: requested radius is the inner shell-window edge; default width is `4.0` physical units at 41^3.
- Stability: no dt warnings.

Important window comparisons:

| Radius | Def Ret | Neu Ret | Lift Ret | Def Peak/Work | Neu Peak/Work | Lift Peak | Def Outer/Near | Neu Outer/Near | Radius Shift | Arrival Shift | Radial Corr | Clean D/N |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2.5 | 0.712 | 0.616 | 1.156 | 1.70e-7 | 2.12e-7 | 0.801 | 1.44 | 1.33 | 0.00 | 0.32 | 0.981 | true/true |
| 3.5 | 0.712 | 0.616 | 1.156 | 1.70e-7 | 2.12e-7 | 0.801 | 1.44 | 1.33 | 0.00 | 0.32 | 0.981 | true/true |
| 5.0 | 0.578 | 0.583 | 0.990 | 2.03e-7 | 2.39e-7 | 0.848 | 1.49 | 1.25 | 0.00 | 0.32 | 0.981 | true/true |
| 6.5 | 0.351 | 0.380 | 0.923 | 2.13e-7 | 2.03e-7 | 1.051 | 2.33 | 2.25 | 0.00 | 0.16 | 0.981 | false/false |
| 8.0 | 0.300 | 0.329 | 0.911 | 2.42e-7 | 2.42e-7 | 1.000 | 2.40 | 2.18 | 1.44 | 0.00 | 0.981 | false/false |
| 10.0 | 0.000006 | 0.000007 | 0.910 | 0.0215 | 0.0215 | 1.000 | 1.26 | 1.14 | 0.00 | 0.00 | 0.981 | false/false |
| 12.0 | 0.000003 | 0.000003 | 0.968 | 0.0457 | 0.0457 | 1.000 | 1.17 | 1.13 | 0.00 | 0.00 | 0.981 | false/false |

Interpretation:

- The radius-5 window directly answers the prior defect-ablation concern: defect lift is approximately unity, not enhanced.
- The lower windows at 2.5 and 3.5 are retained and clean, but the neutral lattice still produces comparable or stronger peak/work.
- Outer windows at 10 and 12 show high peak/work but near-zero retention, so they are transient/outer-window artifacts rather than useful retained shell candidates.
- Radial profile correlation is high across comparisons, reinforcing that current defect and neutral lattice are producing the same broad radial transport pattern.
- Current classification: `neutral_lattice_reproduces_shell_tail`.

### 3D Defect-Lift Sweep

Command:

```powershell
python main.py prototype-3d-defect-lift-sweep --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\defect_lift_sweep_3d_20260618_163154\defect_lift_sweep_3d_report.md`
- Summary CSV: `runs\defect_lift_sweep_3d_20260618_163154\defect_lift_sweep_summary.csv`
- Comparison CSV: `runs\defect_lift_sweep_3d_20260618_163154\defect_lift_window_comparison.csv`
- Classification: `no_defect_lift_found`
- Strict success rule: defect_lift_retention > `1.5`, defect_lift_peak_work > `1.5`, radial or window profile differs from neutral, global outer false, and clean retained shell window.
- Windows lifting both retention and peak/work above `1.5`: `0`

Key near-misses:

| Variant | Radius | Lift Ret | Lift Peak | Retention | Peak/Work | Outer/Near | Radial Corr | Global Outer | Success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| current_defect_reference | 2.5 | 1.156 | 0.801 | 0.712 | 1.70e-7 | 1.44 | 0.981 | false | false |
| low_damping_defect_d0_05 | 2.5 | 1.251 | 0.874 | 0.770 | 1.85e-7 | 1.23 | 0.972 | false | false |
| high_coupling_inclusion_c1_5 | 6.5 | 1.262 | 1.007 | 0.480 | 2.04e-7 | 1.93 | 0.950 | false | false |
| low_coupling_cavity_c0_25 | 6.5 | 0.799 | 1.170 | 0.304 | 2.37e-7 | 2.87 | 0.890 | false | false |

Interpretation:

- Stronger/softer/coupling/damping/radius/shell/nonlinear defect variants did not create actual lift over the neutral-lattice cubic-boundary shell tail.
- The low-damping variant improved retention somewhat, but peak/work dropped below neutral and the global radial profile stayed highly similar.
- The strongest peak/work near-miss came with weaker retention and high outer/near contamination, so it does not satisfy the retained near-shell success rule.
- Current best wording: structured cubic-boundary shell-window transport at 41^3, not defect-well localization.

### 3D Interference Diagnostics

Command:

```powershell
python main.py prototype-3d-interference-diagnostics --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\interference_diagnostics_3d_20260618_175806\interference_diagnostics_3d_report.md`
- Summary CSV: `runs\interference_diagnostics_3d_20260618_175806\interference_diagnostics_summary.csv`
- Phase CSV: `runs\interference_diagnostics_3d_20260618_175806\phase_coherence_timeseries.csv`
- Modal CSV: `runs\interference_diagnostics_3d_20260618_175806\modal_projection_timeseries.csv`
- Wavefront CSV: `runs\interference_diagnostics_3d_20260618_175806\wavefront_timeseries.csv`
- Classification: `interference_supported_standing_weak`

Important values:

| Variant | Phase | Near Ret | Outer/Near | Global Outer | Coherence | Standing | Cubic Proj | Constructive | Destructive | Arrival | Wavefront Cross |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| neutral_cubic_sign_flip_reference | cubic | 0.583 | 1.25 | false | 0.409 | 0.515 | 0.146 | 0.634 | 0.186 | 9.6 | 17.6 |
| neutral_uniform_same_coverage | uniform | 0.515 | 2.15 | false | 0.320 | 0.527 | 0.192 | 0.574 | 0.231 | 9.6 | 18.4 |
| neutral_cubic_phase_offset | cubic | 0.758 | 1.07 | false | 0.426 | 0.533 | 0.187 | 0.611 | 0.142 | 8.8 | 16.0 |
| neutral_random_phase_seed_31092 | random | 0.876 | 6.32 | true | 0.013 | 0.469 | 0.004 | 0.336 | 0.322 | 14.4 | n/a |
| neutral_random_phase_seed_41092 | random | 0.867 | 5.76 | true | 0.018 | 0.462 | 0.004 | 0.345 | 0.325 | 14.4 | n/a |

Interpretation:

- Same-work per-cell random phase controls do not reproduce the clean shell-window family: they retain energy, but it is outer-dominated and incoherent.
- Cubic sign-flip and cubic phase-offset variants retain clean shell-window behavior with much higher phase coherence and cubic/modal projection proxies.
- Uniform same-coverage is borderline: it keeps some retention but exceeds the outer/near cleanliness limit, so it does not isolate a clean retained shell.
- Standing-shell persistence is below the current threshold (`0.515` and `0.533` versus `0.60`), so the strongest claim should wait.
- This motivated the denser standing-persistence check below; standing-shell language should wait for settled spatial-locking evidence.

### 3D Standing-Shell Persistence

Command:

```powershell
python main.py prototype-3d-standing-persistence --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\standing_persistence_3d_20260618_190944\standing_persistence_3d_report.md`
- Summary CSV: `runs\standing_persistence_3d_20260618_190944\standing_persistence_summary.csv`
- Timeseries CSV: `runs\standing_persistence_3d_20260618_190944\standing_persistence_timeseries.csv`
- Autocorrelation CSV: `runs\standing_persistence_3d_20260618_190944\shell_energy_autocorrelation.csv`
- Classification: `coherent_transport_not_standing`

Important values:

| Variant | Retention | Outer/Near | Global Outer | Standing | Node/Anti | To Mean | F2F | Phase Stability | Spectral | Lag1 AC | Period |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| neutral_cubic_sign_flip_reference | 0.583 | 1.25 | false | 0.446 | 0.306 | 0.250 | 0.802 | 0.0066 | 0.867 | 0.994 | 32.16 |
| neutral_cubic_phase_offset | 0.758 | 1.07 | false | 0.362 | 0.287 | 0.133 | 0.728 | 0.0092 | 0.652 | 0.977 | 32.16 |

Interpretation:

- Both clean cubic variants still pass the basic retained-shell cleanliness checks: global outer flag false, controlled outer/near tail ratio, and meaningful shell-window retention.
- The shell-window energy time series is very coherent: lag-1 autocorrelation is high and the dominant spectral fraction is strong.
- The settled spatial pattern does not lock: node/antinode stability is low, similarity to the settled mean pattern is low, and radial shell phase stability is near zero.
- Treat the result as a coherent structured boundary transport packet through the shell window, not as a confirmed standing-shell mode.
- Do not use standing-shell language unless a future check passes settled spatial-locking metrics.

### 3D Transport-Packet Audit

Command:

```powershell
python main.py prototype-3d-transport-packet-audit --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\transport_packet_3d_20260618_193704\transport_packet_3d_report.md`
- Summary CSV: `runs\transport_packet_3d_20260618_193704\transport_packet_summary.csv`
- Timeseries CSV: `runs\transport_packet_3d_20260618_193704\transport_packet_timeseries.csv`
- Lag correlation CSV: `runs\transport_packet_3d_20260618_193704\packet_lag_correlation.csv`
- Classification: `moving_transport_packet_supported`

Important values:

| Variant | Retention | Outer/Near | Arrival | Peak Time | Exit | Radial V | R2 | TOF V | In Flux | Out Flux | Phase V | Angular Drift | F2F |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| neutral_cubic_sign_flip_reference | 0.496 | 1.82 | 9.28 | 31.52 | false | -0.238 | 0.614 | 1.11 | 0.781 | 0.219 | 1.336 | 0.000 | 0.486 |
| neutral_cubic_phase_offset | 0.674 | 1.49 | 8.48 | 35.04 | false | -0.232 | 0.669 | 1.22 | 0.787 | 0.213 | 1.333 | 0.000 | 0.416 |

Interpretation:

- The shell-window tail is better described as a moving inward transport packet than as a slowly rotating or drifting modal structure.
- Inward shell flux dominates roughly 78% of the shell radial flux proxy in both variants.
- Radial group velocity is consistently inward and comparable across the two clean cubic variants.
- No shell-window exit was detected within the current run window, so the packet either remains/recycles in the measured region or decays without dropping below the exit threshold before the run ends.
- Angular drift is near zero by the shell-centroid proxy; the important motion is radial transport plus shell-window phase advance.
- The next useful question is whether boundary phase shaping can slow, redirect, or repeatedly refocus this packet without reintroducing outer-boundary contamination.

### 3D Packet Lifecycle Audit

Command:

```powershell
python main.py prototype-3d-packet-lifecycle-audit --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\packet_lifecycle_3d_20260618_195923\packet_lifecycle_3d_report.md`
- Summary CSV: `runs\packet_lifecycle_3d_20260618_195923\packet_lifecycle_summary.csv`
- Timeseries CSV: `runs\packet_lifecycle_3d_20260618_195923\packet_lifecycle_timeseries.csv`
- Events CSV: `runs\packet_lifecycle_3d_20260618_195923\packet_lifecycle_events.csv`
- Classification: `repeated_refocusing_supported`
- Extended duration: `t=96`, with drive cutoff still at `t=16`

Important values:

| Variant | Peaks | Refocus | Retention | Outer/Shell | Arrival | Exit | Decay | Radius V | Width Growth | In Flux |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| neutral_cubic_sign_flip_reference | 5 | 4 | 0.116 | 1.50 | 9.28 | true, 74.72 | -0.0517 | -0.0142 | -0.114 | 0.700 |
| neutral_cubic_phase_offset | 6 | 5 | 0.132 | 1.78 | 8.48 | true, 76.00 | -0.0541 | -0.0174 | -0.004 | 0.701 |

Event highlights:

- Sign-flip shell-window peaks at `t=20.80`, `31.52`, `37.76`, `43.20`, and `51.36`.
- Phase-offset shell-window peaks at `t=16.48`, `21.92`, `29.28`, `35.04`, `45.28`, and `52.00`.
- Later return peaks can exceed the first post-cutoff peak; phase-offset has the strongest max refocus ratio, about `2.01`.

Interpretation:

- The cubic phase does not merely create a one-pass shell-window transit. It creates repeated shell-window returns before the packet finally exits/decays below threshold.
- This moves the 3D branch from generic transport steering toward retention/refocusing engineering.
- The phase-offset variant is the current best reference because it produced more major peaks, more refocus peaks, and the stronger refocus ratio.
- The result remains neutral-lattice and not defect-dependent.

### 3D Refocusing-Engineering Control

Command:

```powershell
python main.py prototype-3d-refocusing-engineering-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\refocusing_engineering_3d_20260618_202513\refocusing_engineering_3d_report.md`
- Summary CSV: `runs\refocusing_engineering_3d_20260618_202513\refocusing_engineering_summary.csv`
- Timeseries CSV: `runs\refocusing_engineering_3d_20260618_202513\refocusing_engineering_timeseries.csv`
- Events CSV: `runs\refocusing_engineering_3d_20260618_202513\refocusing_engineering_events.csv`
- Classification: `refocusing_improved`
- Best variant: `cutoff_long`
- Setup: `41^3`, neutral lattice, stronger sponge, inner-sponge-edge source, matched work per physical source area `0.105027`, radius-5 shell window, extended duration `t=96`

Important values:

| Variant | Axis | Cutoff | Freq | Peaks | Refocus | Ratio | Exit | Retention | Outer/Shell | Decay | In Flux | Global Outer |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| sign_flip_reference | sign flip | 16 | 0.92 | 5 | 4 | 1.793 | true, 74.72 | 0.116 | 1.504 | -0.0517 | 0.700 | false |
| phase_offset_reference | phase ref | 16 | 0.92 | 6 | 5 | 2.006 | true, 76.00 | 0.132 | 1.780 | -0.0541 | 0.701 | false |
| phase_offset_minus_delta | phase | 16 | 0.92 | 7 | 6 | 1.826 | true, 76.96 | 0.142 | 1.734 | -0.0518 | 0.709 | false |
| phase_offset_plus_delta | phase | 16 | 0.92 | 5 | 4 | 2.191 | true, 75.20 | 0.121 | 1.814 | -0.0565 | 0.694 | false |
| cutoff_short | cutoff | 14 | 0.92 | 5 | 4 | 2.423 | false | 0.196 | 0.770 | -0.0314 | 0.771 | false |
| cutoff_long | cutoff | 18 | 0.92 | 9 | 8 | 2.308 | false | 0.269 | 0.809 | -0.0273 | 0.813 | false |
| frequency_low | frequency | 16 | 0.90 | 6 | 5 | 2.315 | true, 89.44 | 0.142 | 1.138 | -0.0381 | 0.742 | false |
| frequency_high | frequency | 16 | 0.94 | 8 | 7 | 2.058 | false | 0.257 | 0.686 | -0.0288 | 0.814 | false |
| chirp_low_to_high | chirp | 16 | 0.92 | 6 | 5 | 1.668 | true, 75.36 | 0.121 | 1.841 | -0.0563 | 0.704 | false |

Interpretation:

- The result answers the current engineering question positively: small source timing/frequency changes can improve post-cutoff return count and delay or remove shell-window exit under this run horizon.
- `cutoff_long` is the strongest single-axis result because it adds three refocus peaks over the phase-offset reference, doubles tail retention, cuts the outer/shell ratio by more than half, and slows the fitted decay rate.
- `frequency_high` is also important because it achieves seven refocus peaks with the lowest outer/shell ratio in this set.
- Phase offsets around the reference stayed clean, but did not beat the cutoff/frequency winners.
- The chirp variant did not improve the reference under this simple low-to-high chirp.
- This remains neutral-lattice structured boundary refocusing, not defect localization and not a confirmed standing-shell mode.

### 3D Cutoff-Frequency Refocusing Map

Command:

```powershell
python main.py prototype-3d-refocusing-map-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\refocusing_map_3d_20260618_204404\refocusing_map_3d_report.md`
- Summary CSV: `runs\refocusing_map_3d_20260618_204404\refocusing_map_summary.csv`
- Timeseries CSV: `runs\refocusing_map_3d_20260618_204404\refocusing_map_timeseries.csv`
- Events CSV: `runs\refocusing_map_3d_20260618_204404\refocusing_map_events.csv`
- Classification: `local_map_improved_single_axis`
- Setup: `41^3`, neutral lattice, stronger sponge, inner-sponge-edge source, matched work per physical source area `0.105027`, radius-5 shell window, extended duration `t=96`

Important values:

| Variant | Cutoff | Freq | Peaks | Refocus | Ratio | Exit | Retention | Outer/Shell | Decay | In Flux | Global Outer |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| phase_offset_reference | 16 | 0.92 | 6 | 5 | 2.006 | true, 76.00 | 0.132 | 1.780 | -0.0541 | 0.701 | false |
| cutoff_long_reference | 18 | 0.92 | 9 | 8 | 2.308 | false | 0.269 | 0.809 | -0.0273 | 0.813 | false |
| frequency_high_reference | 16 | 0.94 | 8 | 7 | 2.058 | false | 0.257 | 0.686 | -0.0288 | 0.814 | false |
| combined_cutoff_long_frequency_high | 18 | 0.94 | 4 | 3 | 2.201 | true, 70.40 | 0.0993 | 1.695 | -0.0484 | 0.702 | false |
| cutoff_low_frequency_high | 17 | 0.94 | 4 | 3 | 1.908 | true, 76.64 | 0.127 | 1.364 | -0.0512 | 0.707 | false |
| cutoff_high_frequency_high | 19 | 0.94 | 6 | 5 | 2.809 | false | 0.235 | 0.720 | -0.0313 | 0.792 | false |
| cutoff_long_frequency_low | 18 | 0.93 | 7 | 6 | 2.422 | false | 0.224 | 1.033 | -0.0315 | 0.800 | false |
| cutoff_long_frequency_higher | 18 | 0.95 | 5 | 4 | 1.718 | true, 71.52 | 0.114 | 2.385 | -0.0546 | 0.701 | false |

Interpretation:

- The obvious combined test failed: `cutoff_long + frequency_high` did not produce more than nine peaks, did not reach retention above `0.3`, did not avoid exit, and did not keep outer/shell below `1`.
- This argues against treating cutoff and frequency as independent additive knobs.
- `cutoff_long_reference` remains the best return-count and retention row.
- `frequency_high_reference` remains the cleanest low-outer-residue row, but adding it to cutoff `18` disrupts the return sequence.
- The next control should be single-axis and timing-focused rather than another two-knob map.

### 3D Cutoff Release-Phase Timing Map

Command:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --cutoff-offsets -0.2 -0.1 0 0.1 0.2 --phase-offset-deltas 0 --polarity-cutoff-offsets -0.2 -0.1 0 0.1 0.2
```

Latest summarized run:

- Local report: `runs\cutoff_phase_map_3d_20260619_104211\cutoff_phase_map_3d_report.md`
- Summary CSV: `runs\cutoff_phase_map_3d_20260619_104211\cutoff_phase_map_summary.csv`
- Ranked CSV: `runs\cutoff_phase_map_3d_20260619_104211\cutoff_phase_ranked_summary.csv`
- Timeseries CSV: `runs\cutoff_phase_map_3d_20260619_104211\cutoff_phase_map_timeseries.csv`
- Events CSV: `runs\cutoff_phase_map_3d_20260619_104211\cutoff_phase_map_events.csv`
- Classification: `cutoff_phase_timing_island_supported`
- Best variant: `sign_flip_cutoff_minus_0p1`
- Setup: `41^3`, neutral lattice, stronger sponge, inner-sponge-edge source, matched work per physical source area `0.105027`, frequency `0.92`, radius-5 shell window, extended duration `t=96`

Important values:

| Variant | Family | Cutoff | Phase At Cutoff | Peaks | Refocus | Exit | Retention | Outer/Shell | Decay | In Flux | Global Outer |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| phase_offset_cutoff_minus_0p2 | phase_offset | 17.8 | 0.626 | 8 | 7 | false | 0.237 | 0.640 | -0.0331 | 0.799 | false |
| phase_offset_cutoff_minus_0p1 | phase_offset | 17.9 | 0.718 | 9 | 8 | false | 0.251 | 0.676 | -0.0299 | 0.808 | false |
| phase_offset_cutoff_reference | phase_offset | 18.0 | 0.810 | 9 | 8 | false | 0.269 | 0.809 | -0.0273 | 0.813 | false |
| phase_offset_cutoff_plus_0p1 | phase_offset | 18.1 | 0.902 | 9 | 8 | false | 0.269 | 0.901 | -0.0274 | 0.812 | false |
| phase_offset_cutoff_plus_0p2 | phase_offset | 18.2 | 0.994 | 8 | 7 | false | 0.243 | 0.914 | -0.0299 | 0.799 | false |
| sign_flip_cutoff_minus_0p2 | sign_flip | 17.8 | 0.376 | 9 | 8 | false | 0.317 | 0.714 | -0.0243 | 0.811 | false |
| sign_flip_cutoff_minus_0p1 | sign_flip | 17.9 | 0.468 | 9 | 8 | false | 0.322 | 0.660 | -0.0237 | 0.810 | false |
| sign_flip_cutoff_reference | sign_flip | 18.0 | 0.560 | 9 | 8 | false | 0.296 | 0.594 | -0.0249 | 0.811 | false |
| sign_flip_cutoff_plus_0p1 | sign_flip | 18.1 | 0.652 | 7 | 6 | false | 0.255 | 0.606 | -0.0275 | 0.784 | false |
| sign_flip_cutoff_plus_0p2 | sign_flip | 18.2 | 0.744 | 7 | 6 | true, 93.76 | 0.214 | 0.815 | -0.0316 | 0.755 | false |

Interpretation:

- The tighter map upgraded the release-timing result to `cutoff_phase_timing_island_supported`.
- The best rows are in the sign-flip family. The strongest cluster is cutoff phases `0.376-0.468` cycles, with retention above `0.30`, outer/shell below `1.0`, no exit, and no global outer flag.
- `phase_offset` is also clean around cutoff `18`, but it remains below the strict retention target and ranks below the sign-flip rows.
- The result supports a phase-release mechanism: cubic boundary drive plus the correct cutoff/release phase produces repeated post-cutoff refocusing and delayed shell-window exit.
- This was still passive boundary-interference refocusing, not a trap. It motivated the timed second-pulse control below rather than defects, rotation, medium gradients, or grid expansion.

### 3D Second-Pulse Control

Command:

```powershell
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\second_pulse_3d_20260619_112731\second_pulse_report.md`
- Summary CSV: `runs\second_pulse_3d_20260619_112731\second_pulse_summary.csv`
- Ranked CSV: `runs\second_pulse_3d_20260619_112731\second_pulse_ranked_summary.csv`
- Timeseries CSV: `runs\second_pulse_3d_20260619_112731\second_pulse_timeseries.csv`
- Events CSV: `runs\second_pulse_3d_20260619_112731\second_pulse_events.csv`
- Classification: `second_pulse_contaminated_or_inconclusive`
- Reference: `no_second_pulse`, equivalent to `sign_flip_cutoff_minus_0p1` with cutoff `17.9`, cutoff phase `0.468` cycles, and no active second pulse.

Important values:

| Variant | Role | Center | Phase At Center | Peaks | Refocus | Exit | Retention | Efficiency | Added Work | Gain/Added Work | Outer/Shell | Decay | Global Outer |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| no_second_pulse | reference | n/a | n/a | 9 | 8 | false | 0.322 | 5.16e-8 | 0.0 | n/a | 0.660 | -0.0237 | false |
| phase_matched_second | phase_matched | 35.84 | 0.468 | 6 | 5 | false | 0.561 | 0.00288 | 108.24 | 0.0154 | 1.213 | -0.0460 | false |
| opposite_polarity_second | opposite_polarity | 35.84 | 0.473 | 6 | 5 | false | 0.560 | 0.00289 | 107.83 | 0.0154 | 1.204 | -0.0460 | false |
| second_at_second_refocus | second_refocus | 41.12 | 0.830 | 6 | 4 | false | 0.674 | 0.00305 | 117.29 | 0.0153 | 1.260 | -0.0733 | false |
| second_at_first_refocus | first_refocus | 35.84 | 0.973 | 6 | 4 | false | 0.558 | 0.00288 | 107.91 | 0.0154 | 1.206 | -0.0460 | false |
| phase_offset_second | phase_offset_control | 35.84 | 0.223 | 5 | 3 | false | 0.535 | 0.00254 | 113.09 | 0.0131 | 1.024 | -0.0426 | false |
| second_before_first_refocus | preload_first_refocus | 34.84 | 0.053 | 4 | 2 | false | 0.517 | 0.00275 | 106.08 | 0.0149 | 1.061 | -0.0457 | false |
| extended_first_pulse_same_duration | passive_extension | n/a | n/a | 5 | 4 | true, 80.0 | 0.160 | 1.18e-8 | 51.85 | -3.48e-7 | 1.479 | -0.0443 | true |

Interpretation:

- Full-amplitude second pulses are not a clean active-retention win.
- The phase-matched and opposite-polarity pulses injected roughly `108` extra positive-work units and raised raw retention, but they reduced the clean sequence from nine/eight peaks to six/five peaks.
- Every active second-pulse variant missed at least one strict success criterion: no variant produced more than nine major peaks, more than eight refocus peaks, slower decay than `-0.0237`, and outer/shell below `1.0`.
- The passive extension comparator was worse: it exited, global-outer flagged, and had negative return gain per added work.
- The next test should reduce second-pulse work rather than add traps or new media: use smaller `--second-pulse-amplitude-scale` and/or shorter `--second-pulse-duration`.

### 3D Reduced-Work Second-Pulse Check

Command:

```powershell
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-amplitude-scales 0.1 0.2 0.35 0.5 --second-pulse-durations 2.0 1.0 --second-pulse-roles phase_matched
```

Latest summarized run:

- Local report: `runs\second_pulse_3d_20260619_115332\second_pulse_report.md`
- Summary CSV: `runs\second_pulse_3d_20260619_115332\second_pulse_summary.csv`
- Ranked CSV: `runs\second_pulse_3d_20260619_115332\second_pulse_ranked_summary.csv`
- Timeseries CSV: `runs\second_pulse_3d_20260619_115332\second_pulse_timeseries.csv`
- Events CSV: `runs\second_pulse_3d_20260619_115332\second_pulse_events.csv`
- Classification: `second_pulse_contaminated_or_inconclusive`
- Best ranked row: `no_second_pulse`

Important values:

| Variant | Scale | Duration | Peaks | Refocus | Exit | Retention | Added Work | Added Work Eff | Outer/Shell | Decay | Global Outer |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| no_second_pulse | 1.0 | 0.0 | 9 | 8 | false | 0.322 | 0.00 | n/a | 0.660 | -0.0237 | false |
| phase_matched_second_scale_0p5_duration_2p0 | 0.5 | 2.0 | 6 | 5 | false | 0.562 | 27.05 | -0.248 | 1.213 | -0.0460 | false |
| phase_matched_second_scale_0p35_duration_2p0 | 0.35 | 2.0 | 6 | 5 | false | 0.563 | 13.25 | -0.506 | 1.212 | -0.0460 | false |
| phase_matched_second_scale_0p1_duration_2p0 | 0.1 | 2.0 | 6 | 5 | false | 0.569 | 1.08 | -6.189 | 1.207 | -0.0459 | false |
| phase_matched_second_scale_0p5_duration_1p0 | 0.5 | 1.0 | 5 | 4 | false | 0.388 | 14.70 | -0.587 | 1.248 | -0.0435 | false |
| phase_matched_second_scale_0p1_duration_1p0 | 0.1 | 1.0 | 5 | 4 | false | 0.393 | 0.59 | -14.637 | 1.248 | -0.0435 | false |
| extended_first_pulse_duration_1p0 | n/a | 1.0 | 6 | 5 | false | 0.238 | 25.92 | -0.275 | 1.249 | -0.0323 | false |
| extended_first_pulse_duration_2p0 | n/a | 2.0 | 5 | 4 | true, 80.0 | 0.160 | 51.85 | -0.258 | 1.479 | -0.0443 | true |

Interpretation:

- Reduced second-pulse work did not repair the active-pulse problem.
- Raw retention can rise above the no-pulse reference, but every active reduced-work row loses clean refocus count and keeps outer/shell above `1.0`.
- `added_work_efficiency` is negative for every active reduced-work row; smaller pulses are not simply gentler wins because they still disturb the return sequence.
- Shortening the pulse from duration `2.0` to `1.0` lowers the return count further, so the failure is not just "pulse too long."
- The current evidence points to a timing/phase interaction: a pulse centered at the first refocus peak disrupts the clean release-phase cycle even at low added work.
- Next active-pulse work should inspect timeseries/phase traces or run a tiny center/phase-offset micro-map before adding any new trapping, medium, rotation, defect, or grid mechanism.

### 3D First-Refocus Travel-Time Second-Pulse Micro-Map

Command:

```powershell
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-micro-map --micro-map-targets first_refocus --launch-time-offsets -0.8 -0.4 0 0.4 0.8 --second-pulse-phase-modes matched opposite plus_pi_4 minus_pi_4 --second-pulse-amplitude-scales 0.1 0.2
```

Latest summarized run:

- Local report: `runs\second_pulse_3d_20260619_125050\second_pulse_report.md`
- Summary CSV: `runs\second_pulse_3d_20260619_125050\second_pulse_summary.csv`
- Ranked CSV: `runs\second_pulse_3d_20260619_125050\second_pulse_ranked_summary.csv`
- Timeseries CSV: `runs\second_pulse_3d_20260619_125050\second_pulse_timeseries.csv`
- Events CSV: `runs\second_pulse_3d_20260619_125050\second_pulse_events.csv`
- Timing audit CSV: `runs\second_pulse_3d_20260619_125050\second_pulse_timing_audit.csv`
- Classification: `second_pulse_contaminated_or_inconclusive`

No-pulse timing audit:

| Peak | Time | Flux Dir | Motion | Shell Phase | Travel | Ideal Launch | Source Phase |
| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| 1 | 20.80 | inward | inbound | 0.774 | 9.44 | 11.36 | 0.451 |
| 2 | 35.84 | inward | inbound | 0.960 | 9.44 | 26.40 | 0.288 |
| 3 | 41.12 | inward | outbound | 0.052 | 9.44 | 31.68 | 0.146 |
| 4 | 46.40 | inward | inbound | 0.100 | 9.44 | 36.96 | 0.003 |
| 5 | 52.80 | inward | outbound | 0.186 | 9.44 | 43.36 | 0.891 |
| 6 | 58.88 | inward | outbound | 0.229 | 9.44 | 49.44 | 0.485 |
| 7 | 64.48 | outward | inbound | 0.245 | 9.44 | 55.04 | 0.637 |
| 8 | 70.24 | outward | outbound | 0.265 | 9.44 | 60.80 | 0.936 |
| 9 | 78.40 | outward | inbound | 0.353 | 9.44 | 68.96 | 0.443 |

Important values:

| Variant | Launch Offset | Phase Mode | Scale | Center | Peaks | Refocus | Retention | Outer/Shell | Decay | Added Work Eff |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_second_pulse | n/a | n/a | n/a | n/a | 9 | 8 | 0.322 | 0.660 | -0.0237 | n/a |
| micro_first_refocus_launch_0p8_opposite_scale_0p2 | 0.8 | opposite | 0.2 | 27.2 | 6 | 5 | 0.373 | 1.327 | -0.0430 | -1.658 |
| micro_first_refocus_launch_0p4_opposite_scale_0p2 | 0.4 | opposite | 0.2 | 26.8 | 6 | 5 | 0.364 | 1.330 | -0.0427 | -1.662 |
| micro_first_refocus_launch_0p0_opposite_scale_0p2 | 0.0 | opposite | 0.2 | 26.4 | 6 | 5 | 0.355 | 1.336 | -0.0425 | -1.667 |
| micro_first_refocus_launch_0p8_opposite_scale_0p1 | 0.8 | opposite | 0.1 | 27.2 | 6 | 5 | 0.377 | 1.316 | -0.0426 | -6.628 |
| micro_first_refocus_launch_0p8_plus_pi_4_scale_0p2 | 0.8 | plus_pi_4 | 0.2 | 27.2 | 4 | 2 | 0.342 | 1.124 | -0.0438 | -2.639 |

Interpretation:

- Travel-time adjustment was the right diagnostic step, but it did not rescue active reinjection at the first refocus target.
- The first-refocus ideal launch moved from the shell peak time `35.84` back to `26.4`; tested centers were `25.6`, `26.0`, `26.4`, `26.8`, and `27.2`.
- Opposite-phase launches were the least bad active family, especially at later offsets, but they still cut the clean sequence from nine/eight peaks to six/five peaks.
- No active row kept outer/shell below `1.0`, no active row improved decay beyond `-0.0237`, and every active row had negative `added_work_efficiency`.
- The active pulse appears to create an additional packet that disrupts the already tuned release-phase cycle, even when launched early enough to arrive near the target shell peak.
- This motivated exactly one final active-pulse check at the second refocus peak; that follow-up also failed, so active second pulses are now shelved.

### 3D Second-Refocus Travel-Time Second-Pulse Micro-Map

Command:

```powershell
python main.py prototype-3d-second-pulse-control --config configs\long_validation_peak_0_92.json --second-pulse-micro-map --micro-map-targets second_refocus --launch-time-offsets -0.8 -0.4 0 0.4 0.8 --second-pulse-phase-modes matched opposite plus_pi_4 minus_pi_4 --second-pulse-amplitude-scales 0.1 0.2
```

Latest summarized run:

- Local report: `runs\second_pulse_3d_20260619_135358\second_pulse_report.md`
- Summary CSV: `runs\second_pulse_3d_20260619_135358\second_pulse_summary.csv`
- Ranked CSV: `runs\second_pulse_3d_20260619_135358\second_pulse_ranked_summary.csv`
- Timeseries CSV: `runs\second_pulse_3d_20260619_135358\second_pulse_timeseries.csv`
- Events CSV: `runs\second_pulse_3d_20260619_135358\second_pulse_events.csv`
- Timing audit CSV: `runs\second_pulse_3d_20260619_135358\second_pulse_timing_audit.csv`
- Classification: `second_pulse_contaminated_or_inconclusive`

Timing audit reference:

- Empirical boundary-to-shell travel time: `9.44`
- Second-refocus peak time: `41.12`
- Second-refocus ideal launch time: `31.68`
- Local shell phase at the second-refocus peak: `0.0515`
- Shell radial flux at the second-refocus peak: inward
- Packet motion proxy at the second-refocus peak: outbound

Important values:

| Variant | Launch Offset | Phase Mode | Scale | Center | Peaks | Refocus | Retention | Outer/Shell | Decay | Added Work Eff |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_second_pulse | n/a | n/a | n/a | n/a | 9 | 8 | 0.322 | 0.660 | -0.0237 | n/a |
| micro_second_refocus_launch_0p8_opposite_scale_0p2 | 0.8 | opposite | 0.2 | 32.48 | 6 | 5 | 0.491 | 1.254 | -0.0455 | -1.595 |
| micro_second_refocus_launch_0p8_minus_pi_4_scale_0p2 | 0.8 | minus_pi_4 | 0.2 | 32.48 | 6 | 4 | 0.501 | 1.314 | -0.0421 | -1.645 |
| micro_second_refocus_launch_0p4_opposite_scale_0p2 | 0.4 | opposite | 0.2 | 32.08 | 5 | 4 | 0.491 | 1.255 | -0.0455 | -2.057 |
| micro_second_refocus_launch_0p0_opposite_scale_0p2 | 0.0 | opposite | 0.2 | 31.68 | 5 | 4 | 0.490 | 1.258 | -0.0454 | -2.059 |

Interpretation:

- Targeting the second refocus peak did not rescue active reinjection.
- Active rows can raise raw retention above the no-pulse reference, but they do so by injecting another packet that reduces clean return count, worsens decay, and pushes outer/shell above `1.0`.
- The no-pulse reference remains the best strict row: nine/eight peaks, no exit, outer/shell `0.660`, decay `-0.0237`, and global outer false.
- Both first-refocus and second-refocus travel-time micro-maps failed with negative `added_work_efficiency`, so active second pulses are shelved for now.
- The next work should return to passive release-phase/cutoff engineering around the already supported timing island.

### 3D Passive Release-Phase Island Refinement

Command:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --release-phase-island-refinement
```

Latest summarized run:

- Local report: `runs\cutoff_phase_map_3d_20260619_145631\cutoff_phase_map_3d_report.md`
- Summary CSV: `runs\cutoff_phase_map_3d_20260619_145631\cutoff_phase_map_summary.csv`
- Ranked CSV: `runs\cutoff_phase_map_3d_20260619_145631\cutoff_phase_ranked_summary.csv`
- Timeseries CSV: `runs\cutoff_phase_map_3d_20260619_145631\cutoff_phase_map_timeseries.csv`
- Events CSV: `runs\cutoff_phase_map_3d_20260619_145631\cutoff_phase_map_events.csv`
- Classification: `cutoff_phase_single_point_best`
- Stability result: `single_point_best`
- Best variant: `sign_flip_cutoff_minus_0p06`
- Setup: `41^3`, neutral lattice, stronger sponge, inner-sponge-edge source, matched work per physical source area `0.105027`, frequency `0.92`, radius-5 shell window, extended duration `t=96`

Important values:

| Variant | Family | Cutoff | Phase At Cutoff | Peaks | Refocus | Exit | Retention | Outer/Shell | Decay | Global Outer |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| sign_flip_cutoff_minus_0p06 | sign_flip | 17.94 | 0.5048 | 11 | 10 | false | 0.314 | 0.631 | -0.02396 | false |
| sign_flip_cutoff_minus_0p04 | sign_flip | 17.96 | 0.5232 | 10 | 9 | false | 0.309 | 0.618 | -0.02424 | false |
| sign_flip_cutoff_minus_0p14 | sign_flip | 17.86 | 0.4312 | 9 | 8 | false | 0.325 | 0.686 | -0.02361 | false |
| sign_flip_cutoff_minus_0p12 | sign_flip | 17.88 | 0.4496 | 9 | 8 | false | 0.325 | 0.674 | -0.02360 | false |
| sign_flip_cutoff_minus_0p1 | sign_flip | 17.90 | 0.4680 | 9 | 8 | false | 0.322 | 0.660 | -0.02365 | false |
| phase_offset_cutoff_minus_0p04 | phase_offset | 17.96 | 0.7732 | 9 | 8 | false | 0.263 | 0.754 | -0.02810 | false |

Interpretation:

- The preset tested cutoff offsets `-0.16`, `-0.14`, `-0.12`, `-0.10`, `-0.08`, `-0.06`, and `-0.04` for both the phase-offset and sign-flip/polarity families, with `sign_flip_cutoff_minus_0p1` as the comparison reference.
- The sign-flip family stayed clean across the whole tested pocket: no shell exit, outer/shell below `1.0`, and no global outer-window flag.
- The new best point is cutoff `17.94`, phase `0.5048` cycles. It improves the clean sequence from the prior nine/eight reference to eleven/ten peaks while keeping retention above `0.30`.
- The new stability section deliberately does not call this a stable island yet. Only the `-0.06` row reproduced the 11/10 count; the adjacent `-0.04` row dropped to 10/9 and the earlier clean plateau stayed at 9/8.
- This motivated the ultra-fine passive cutoff-only follow-up below. Active second pulses remain shelved.

### 3D Ultra-Fine Phase-Lock Needle Refinement

Command:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --phase-lock-needle-map first
```

Latest summarized run:

- Local report: `runs\cutoff_phase_map_3d_20260619_155704\cutoff_phase_map_3d_report.md`
- Summary CSV: `runs\cutoff_phase_map_3d_20260619_155704\cutoff_phase_map_summary.csv`
- Ranked CSV: `runs\cutoff_phase_map_3d_20260619_155704\cutoff_phase_ranked_summary.csv`
- Threshold sensitivity CSV: `runs\cutoff_phase_map_3d_20260619_155704\cutoff_phase_event_threshold_sensitivity.csv`
- Timeseries CSV: `runs\cutoff_phase_map_3d_20260619_155704\cutoff_phase_map_timeseries.csv`
- Events CSV: `runs\cutoff_phase_map_3d_20260619_155704\cutoff_phase_map_events.csv`
- Classification: `cutoff_phase_timing_island_supported`
- Phase-lock needle width: `narrow`
- Event-threshold sensitivity: `best_count_threshold_sensitive`
- Best variant: `sign_flip_cutoff_minus_0p07`
- Setup: sign-flip-only, `41^3`, neutral lattice, stronger sponge, inner-sponge-edge source, matched work per physical source area `0.105027`, frequency `0.92`, radius-5 shell window, extended duration `t=96`

Important values:

| Variant | Cutoff | Phase At Cutoff | Peaks | Refocus | Exit | Retention | Outer/Shell | Decay | Global Outer |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| sign_flip_cutoff_minus_0p07 | 17.930 | 0.4956 | 11 | 10 | false | 0.316689 | 0.638587 | -0.0238625 | false |
| sign_flip_cutoff_minus_0p065 | 17.935 | 0.5002 | 11 | 10 | false | 0.315527 | 0.635010 | -0.0239098 | false |
| sign_flip_cutoff_minus_0p06 | 17.940 | 0.5048 | 11 | 10 | false | 0.314310 | 0.631459 | -0.0239602 | false |
| sign_flip_cutoff_minus_0p075 | 17.925 | 0.4910 | 10 | 9 | false | 0.317795 | 0.642182 | -0.0238185 | false |
| sign_flip_cutoff_minus_0p055 | 17.945 | 0.5094 | 10 | 9 | false | 0.313041 | 0.627938 | -0.0240138 | false |
| sign_flip_cutoff_minus_0p05 | 17.950 | 0.5140 | 10 | 9 | false | 0.311697 | 0.624454 | -0.0241133 | false |
| sign_flip_cutoff_minus_0p045 | 17.955 | 0.5186 | 10 | 9 | false | 0.310258 | 0.621015 | -0.0241740 | false |

Needle-width and sensitivity details:

- The release-phase island stability section now sees a neighboring exact-top cluster at cutoff offsets `-0.07`, `-0.065`, and `-0.06`.
- The `phase-lock needle width` section classifies that cluster as `narrow`, because the exact-top cutoff width is only `0.01`.
- Every tested neighboring row stayed within one peak/refocus, within 10% retention, and below outer/shell `1.0`, but the exact 11/10 count only spans `17.93-17.94`.
- The event-threshold sensitivity audit counted the best row as 12/11 at major-peak threshold `0.25`, 11/10 at `0.30`, and 9/8 at `0.35`, independent of the refocus threshold values tested (`0.30`, `0.35`, `0.40`).
- The nearest 17.935 neighbor shows the same sensitivity profile, while the 17.925 lower neighbor stays within one count across all tested threshold scenarios.

Interpretation:

- The previous `17.94` single-point result is not alone once the cutoff grid is refined, so it should no longer be described as an isolated point.
- The support is still too narrow to call a broad timing island. Best wording: possible narrow phase-lock needle in the sign-flip release phase.
- Because the 11/10 count shifts by more than one under event-threshold changes, treat the peak count as detector-sensitive until event traces or peak-picking thresholds are audited more directly.
- The requested tighter map was not run, because the first ultra-fine map already showed neighboring 11/10 support rather than an isolated best row.

### 3D Threshold-Robust Refocusing Confirmation

Command:

```powershell
python main.py prototype-3d-cutoff-phase-map-control --config configs\long_validation_peak_0_92.json --threshold-robust-confirmation
```

Latest summarized run:

- Local report: `runs\cutoff_phase_map_3d_20260619_162240\cutoff_phase_map_3d_report.md`
- Summary CSV: `runs\cutoff_phase_map_3d_20260619_162240\cutoff_phase_map_summary.csv`
- Ranked CSV: `runs\cutoff_phase_map_3d_20260619_162240\cutoff_phase_ranked_summary.csv`
- Threshold sensitivity CSV: `runs\cutoff_phase_map_3d_20260619_162240\cutoff_phase_event_threshold_sensitivity.csv`
- Threshold-robust score CSV: `runs\cutoff_phase_map_3d_20260619_162240\cutoff_phase_threshold_robust_score.csv`
- Timeseries CSV: `runs\cutoff_phase_map_3d_20260619_162240\cutoff_phase_map_timeseries.csv`
- Events CSV: `runs\cutoff_phase_map_3d_20260619_162240\cutoff_phase_map_events.csv`
- Classification: `cutoff_phase_timing_island_supported`
- Setup: sign-flip-only, cutoffs `17.920`, `17.925`, `17.930`, `17.935`, `17.940`, `17.945`, `17.950`; `41^3`, neutral lattice, stronger sponge, inner-sponge-edge source, matched work per physical source area `0.105027`, frequency `0.92`, radius-5 shell window, extended duration `t=96`

Threshold-robust score highlights:

| Rank | Variant | Cutoff | Default Count | Min Count | Median Count | Retention | Outer/Shell | Decay | No Exit | Global Outer | Area Post-Cutoff | Tail Area t>50 | Autocorr | Spectral | Timing Reg |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | sign_flip_cutoff_minus_0p07 | 17.930 | 11/10 | 9/8 | 10/9 | 0.316689 | 0.638587 | -0.0238625 | true | true | 0.00288028 | 0.00124038 | 0.999523 | 0.745103 | 0.851084 |
| 2 | sign_flip_cutoff_minus_0p065 | 17.935 | 11/10 | 9/8 | 10/9 | 0.315527 | 0.635010 | -0.0239098 | true | true | 0.00287693 | 0.00123643 | 0.999522 | 0.742981 | 0.851084 |
| 3 | sign_flip_cutoff_minus_0p06 | 17.940 | 11/10 | 9/8 | 10/9 | 0.314310 | 0.631459 | -0.0239602 | true | true | 0.00287285 | 0.00123206 | 0.999521 | 0.740908 | 0.846999 |
| 4 | sign_flip_cutoff_minus_0p075 | 17.925 | 10/9 | 9/8 | 9.5/8.5 | 0.317795 | 0.642182 | -0.0238185 | true | true | 0.00288290 | 0.00124389 | 0.999525 | 0.747277 | 0.830852 |
| 7 | sign_flip_cutoff_minus_0p08 | 17.920 | 9/8 | 8/7 | 8.5/7.5 | 0.318843 | 0.645792 | -0.0237779 | true | true | 0.00288480 | 0.00124696 | 0.999526 | 0.749503 | 0.571249 |

Peak/refocus counts by peak threshold:

| Cutoff | 0.25 | 0.30 | 0.35 | 0.40 |
| ---: | --- | --- | --- | --- |
| 17.930 | 12/11 | 11/10 | 9/8 | 9/8 |
| 17.935 | 12/11 | 11/10 | 9/8 | 9/8 |
| 17.940 | 12/11 | 11/10 | 9/8 | 9/8 |
| 17.925 | 11/10 | 10/9 | 9/8 | 9/8 |
| 17.945 | 12/11 | 10/9 | 9/8 | 9/8 |
| 17.950 | 12/11 | 10/9 | 9/8 | 9/8 |
| 17.920 | 10/9 | 9/8 | 8/7 | 8/7 |

Interpretation:

- The phase-lock cluster is real enough to continue because neighboring cutoffs reproduce the default 11/10 count.
- The exact peak/refocus count is threshold-sensitive. The top cluster moves from 12/11 to 11/10 to 9/8 as the peak threshold tightens.
- Conservative claim: the cluster preserves or improves the clean 9/8 refocusing family under stricter detection, not that 11/10 is threshold-invariant.
- The threshold-free shell-energy areas, tail areas, autocorrelation, spectral concentration, and timing regularity stay tightly clustered across the top 17.93-17.94 rows, supporting a real narrow release-phase packet/refocusing structure behind the threshold-sensitive event count.

### Passive Resonator Layer Control

Command:

```powershell
python main.py prototype-3d-resonator-layer-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\resonator_layer_3d_20260619_175949\resonator_layer_report.md`
- Summary CSV: `runs\resonator_layer_3d_20260619_175949\resonator_layer_summary.csv`
- Threshold-robust score CSV: `runs\resonator_layer_3d_20260619_175949\resonator_layer_threshold_robust_score.csv`
- Resonator energy timeseries CSV: `runs\resonator_layer_3d_20260619_175949\resonator_energy_timeseries.csv`
- Coupling exchange timeseries CSV: `runs\resonator_layer_3d_20260619_175949\coupling_exchange_timeseries.csv`
- Classification: `no_resonator_still_wins`
- Setup: `41^3`, neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 shell window, no active second pulses, cutoffs `17.920` through `17.950`

Highlights:

| Group | Strict 9/8 Cutoffs | Best Default Count | Best Strict Count | Best Retention | Best Outer/Shell | Best Decay |
| --- | --- | --- | --- | ---: | ---: | ---: |
| no_resonator_reference | 17.925, 17.930, 17.935, 17.940, 17.945, 17.950 | 11/10 | 9/8 | 0.316689 | 0.638587 | -0.0238625 |
| zero_coupling_control | 17.925, 17.930, 17.935, 17.940, 17.945, 17.950 | 11/10 | 9/8 | 0.316689 | 0.638587 | -0.0238625 |
| coupled resonator layer variants | none | 10/9 | 8/7 | 0.291557 | 0.658466-0.659886 | about -0.026316 |

Interpretation:

- The passive resonator layer did not widen or stabilize the phase-lock cluster. The coupled tuned, slightly-below, slightly-above, moderate-cubic, and high-damping variants all reduced the conservative cross-threshold count from 9/8 to 8/7.
- Energy accounting passed for all rows, and post-cutoff external work was exactly zero in the summaries. This is a passive negative mechanism test, not an active-work contamination result.
- The no-resonator reference remains the current best conservative row: `no_resonator_reference_cutoff_17p930`, cutoff `17.93`, release phase `0.4956` cycles, default 11/10, strict 9/8, retention `0.316689`, outer/shell `0.638587`, decay `-0.0238625`, no exit, and global outer false.
- Do not expand this resonator-layer family unless a new mechanism specifies why a different passive coupling geometry or parameter scale should avoid the observed strict-count degradation.

### Release-Phase Return-Map Predictor

Command:

```powershell
python main.py prototype-3d-release-phase-return-map --run-roots runs\cutoff_phase_map_3d_20260619_162240 runs\cutoff_phase_map_3d_20260619_155704 runs\cutoff_phase_map_3d_20260619_145631 runs\resonator_layer_3d_20260619_175949
```

Latest summarized run:

- Local report: `runs\release_phase_return_map_3d_20260619_205221\release_phase_return_map_report.md`
- Feature table: `runs\release_phase_return_map_3d_20260619_205221\release_phase_feature_table.csv`
- Predictions CSV: `runs\release_phase_return_map_3d_20260619_205221\release_phase_predictions.csv`
- Binned summary CSV: `runs\release_phase_return_map_3d_20260619_205221\release_phase_binned_summary.csv`
- Classification: `release_phase_predictive_rule_supported`
- Inputs: `runs\cutoff_phase_map_3d_20260619_162240`, `runs\cutoff_phase_map_3d_20260619_155704`, `runs\cutoff_phase_map_3d_20260619_145631`, and `runs\resonator_layer_3d_20260619_175949`

Predictive rule:

- Best-cluster center near phase `0.50`: yes; center `0.500554` cycles.
- Reference-compatible strict 9/8 preservation range: about `0.491-0.5232` cycles.
- Default 11/10 range: `0.4956-0.5048` cycles.
- The 11/10 rows are predictable as a narrow phase-guided pocket, but the exact count remains threshold/cutoff sensitive; the conservative claim stays strict 9/8 preservation.
- Top separating features included shell-energy autocorrelation, dominant spectral concentration, early outer/shell ratio, tail area after `t=50`, cutoff time, and return timing regularity.

Blind confirmation recommendation:

| Role | Cutoff | Phase | Predicted Strict |
| --- | ---: | ---: | --- |
| predicted strong | 17.932885 | 0.498254 | 9/8 |
| predicted strong | 17.937885 | 0.502854 | 9/8 |
| boundary/edge | 17.9225 | 0.4887 | 9/8 |
| boundary/edge | 17.965 | 0.5278 | 9/8 |
| weak negative control | 17.915 | 0.4818 | 8/7 |

Interpretation:

- This was read-only: no new physics was run.
- The result supports a phase/early-packet rule for separating the strict 9/8 cluster from weaker rows, while preserving the existing caution that 11/10 is not threshold-invariant.
- Any next physics should be limited to the five cutoffs above under the same fixed setup.

### Release-Phase Blind Confirmation

Command:

```powershell
python main.py prototype-3d-release-phase-blind-confirmation --config configs\long_validation_peak_0_92.json --cutoffs 17.932885 17.937885 17.9225 17.965 17.915
```

Latest summarized run:

- Local report: `runs\release_phase_blind_confirmation_3d_20260619_210435\release_phase_blind_confirmation_report.md`
- Summary CSV: `runs\release_phase_blind_confirmation_3d_20260619_210435\release_phase_blind_confirmation_summary.csv`
- Prediction-check CSV: `runs\release_phase_blind_confirmation_3d_20260619_210435\release_phase_blind_confirmation_prediction_check.csv`
- Classification: `release_phase_blind_confirmed`
- Setup: `41^3`, neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 shell window, no active second pulses, no resonator layer

Blind results:

| Role | Cutoff | Phase | Default Count | Strict 0.35 | Strict 0.40 | Retention | Outer/Shell | Decay |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: |
| predicted strong | 17.932885 | 0.498254 | 11/10 | 9/8 | 9/8 | 0.316025 | 0.636520 | -0.0238894 |
| predicted strong | 17.937885 | 0.502854 | 11/10 | 9/8 | 9/8 | 0.314831 | 0.632958 | -0.0239385 |
| lower boundary/edge | 17.9225 | 0.4887 | 9/8 | 8/7 | 8/7 | 0.318327 | 0.643986 | -0.0237978 |
| upper boundary/edge | 17.965 | 0.5278 | 10/9 | 9/8 | 9/8 | 0.307245 | 0.614321 | -0.0243047 |
| weak negative control | 17.915 | 0.4818 | 9/8 | 8/7 | 8/7 | 0.319825 | 0.649397 | -0.0237408 |

Interpretation:

- The return-map rule survived the blind check: the two predicted strong rows preserved the strict clean 9/8 family and default 11/10, while the predicted weak control fell below the strong cluster.
- The lower edge also failed strict 9/8, while the upper edge stayed strict 9/8 without default 11/10. This sharpens the picture: the default 11/10 pocket is narrower than the strict 9/8 band and appears centered near phase 0.50 cycles.
- Do not tune around this result. Treat it as confirmation of the narrow release-phase phase-lock rule, not permission for broad cutoff sweeps.

### Release-Phase Numerical Validation

Command:

```powershell
python main.py prototype-3d-release-phase-numerical-validation --config configs\long_validation_peak_0_92.json --cutoffs 17.932885 17.937885 17.9225 17.915
```

Latest summarized run:

- Local report: `runs\release_phase_numerical_validation_3d_20260619_214240\release_phase_numerical_validation_report.md`
- Summary CSV: `runs\release_phase_numerical_validation_3d_20260619_214240\release_phase_numerical_validation_summary.csv`
- Comparison CSV: `runs\release_phase_numerical_validation_3d_20260619_214240\release_phase_numerical_validation_comparison.csv`
- Classification: `release_phase_dt_sensitive`
- Setup: baseline dt and half dt only, `41^3`, neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 shell window, no active second pulses, no resonator layer

Numerical-validation results:

| dt | Role | Cutoff | Phase | Default Count | Strict 0.35 | Strict 0.40 | Retention | Outer/Shell | Decay |
| --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: |
| baseline | predicted strong | 17.932885 | 0.498254 | 11/10 | 9/8 | 9/8 | 0.316025 | 0.636520 | -0.0238894 |
| baseline | predicted strong | 17.937885 | 0.502854 | 11/10 | 9/8 | 9/8 | 0.314831 | 0.632958 | -0.0239385 |
| baseline | low edge | 17.9225 | 0.4887 | 9/8 | 8/7 | 8/7 | 0.318327 | 0.643986 | -0.0237978 |
| baseline | weak control | 17.915 | 0.4818 | 9/8 | 8/7 | 8/7 | 0.319825 | 0.649397 | -0.0237408 |
| half dt | predicted strong | 17.932885 | 0.498254 | 9/8 | 8/7 | 8/7 | 0.316014 | 0.637538 | -0.0238887 |
| half dt | predicted strong | 17.937885 | 0.502854 | 10/9 | 9/8 | 9/8 | 0.314784 | 0.633998 | -0.0239382 |
| half dt | low edge | 17.9225 | 0.4887 | 9/8 | 8/7 | 8/7 | 0.318383 | 0.644932 | -0.0237966 |
| half dt | weak control | 17.915 | 0.4818 | 9/8 | 8/7 | 8/7 | 0.319927 | 0.650275 | -0.0237394 |

Interpretation:

- Baseline dt reproduced the blind-confirmed phase split.
- Half dt did not preserve the full two-row strong pocket: `17.937885` remained strict-clean at 9/8, but `17.932885` dropped to the low-control 8/7 family.
- The rule remains a useful phase predictor at baseline dt, but the lower half-cycle strong point is numerically sensitive. Do not claim the 17.932885/17.937885 pair is half-dt invariant.
- Quarter dt was not run in this command because baseline plus half dt exposed sensitivity first; the later proof pack below targets only the recentered half-dt window and immediate controls.

### Release-Phase Half-dt Recentering

Command:

```powershell
python main.py prototype-3d-release-phase-dt-recenter --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\release_phase_dt_recenter_3d_20260619_220833\release_phase_dt_recenter_report.md`
- Summary CSV: `runs\release_phase_dt_recenter_3d_20260619_220833\release_phase_dt_recenter_summary.csv`
- Threshold-robust CSV: `runs\release_phase_dt_recenter_3d_20260619_220833\release_phase_dt_recenter_threshold_robust_score.csv`
- Classification: `release_phase_half_dt_recentered`
- Setup: half dt only, `41^3`, neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 shell window, no active second pulses, no resonator layer

Half-dt recentering results:

| Role | Cutoff | Phase | Default Count | Strict 0.35 | Strict 0.40 | Retention | Outer/Shell | Decay |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: |
| recenter candidate | 17.930 | 0.4956 | 9/8 | 8/7 | 8/7 | 0.316698 | 0.639588 | -0.0238616 |
| recenter candidate | 17.9325 | 0.4979 | 9/8 | 8/7 | 8/7 | 0.316106 | 0.637812 | -0.0238850 |
| recenter candidate | 17.935 | 0.5002 | 9/8 | 8/7 | 8/7 | 0.315500 | 0.636038 | -0.0239092 |
| recenter candidate | 17.9375 | 0.5025 | 10/9 | 9/8 | 9/8 | 0.314881 | 0.634270 | -0.0239343 |
| recenter candidate | 17.940 | 0.5048 | 10/9 | 9/8 | 9/8 | 0.314247 | 0.632506 | -0.0239601 |
| recenter candidate | 17.9425 | 0.5071 | 10/9 | 9/8 | 9/8 | 0.313600 | 0.630750 | -0.0239868 |
| recenter candidate | 17.945 | 0.5094 | 10/9 | 9/8 | 9/8 | 0.312942 | 0.629005 | -0.0240143 |
| recenter candidate | 17.9475 | 0.5117 | 9/8 | 8/7 | 8/7 | 0.312271 | 0.627272 | -0.0240425 |
| recenter candidate | 17.950 | 0.5140 | 9/8 | 8/7 | 8/7 | 0.311588 | 0.625551 | -0.0240714 |
| low-side control | 17.9225 | 0.4887 | 9/8 | 8/7 | 8/7 | 0.318383 | 0.644932 | -0.0237966 |
| weak control | 17.915 | 0.4818 | 9/8 | 8/7 | 8/7 | 0.319927 | 0.650275 | -0.0237394 |

Interpretation:

- The half-dt optimum did not disappear. It shifted upward from the baseline-dt pocket into the half-dt strict-clean window `17.9375-17.945`, phase `0.5025-0.5094`.
- The best conservative row was `17.9375`; all four strict-clean rows in the recentered window had default 10/9, strict 9/8, no exit, global outer false, and outer/shell below 1.0.
- Lower-side controls and the adjacent lower/upper outside rows remained strict 8/7, so the recentering is not a detector-only tie with the weak controls.
- This result motivated a proof pack rather than another discovery sweep: quarter dt should only target the recentered window and immediate controls.

### Release-Phase Quarter-dt Proof Pack

Command:

```powershell
python main.py prototype-3d-release-phase-proof-pack --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\release_phase_proof_pack_3d_20260619_234039\release_phase_proof_pack_report.md`
- Candidate card: `runs\release_phase_proof_pack_3d_20260619_234039\candidate_card.md`
- Summary CSV: `runs\release_phase_proof_pack_3d_20260619_234039\release_phase_proof_pack_summary.csv`
- Threshold-robust CSV: `runs\release_phase_proof_pack_3d_20260619_234039\release_phase_proof_pack_threshold_robust_score.csv`
- Gates CSV: `runs\release_phase_proof_pack_3d_20260619_234039\release_phase_proof_pack_gates.csv`
- Classification: `release_phase_quarter_dt_proof_supported`
- Setup: quarter dt only, `41^3`, neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 shell window, no active second pulses, no resonator layer

Frozen candidate card:

- Grid: `41^3`
- Lattice: neutral
- Source: inner-sponge-edge sign-flip cubic boundary source
- Sponge: stronger sponge at original width
- Frequency: `0.92`
- Work: matched per physical source area
- Shell metric: radius-5 shell window
- Active second pulses: none
- Resonator layer: none
- Candidate phase span: `0.5025-0.5094`

Quarter-dt proof-pack results:

| Role | Cutoff | Phase | Default Count | Strict 0.35 | Strict 0.40 | Retention | Outer/Shell | Tail Area t>50 | Timing Reg | Inward Flux | Strict Clean |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| lower immediate control | 17.935 | 0.5002 | 9/8 | 8/7 | 8/7 | 0.315418 | 0.636549 | 0.00123400 | 0.571049 | 0.823798 | false |
| proof candidate | 17.9375 | 0.5025 | 9/8 | 8/7 | 8/7 | 0.314791 | 0.634787 | 0.00123185 | 0.571049 | 0.823526 | false |
| proof candidate | 17.940 | 0.5048 | 10/9 | 9/8 | 9/8 | 0.314149 | 0.633032 | 0.00122960 | 0.840291 | 0.823256 | true |
| proof candidate | 17.9425 | 0.5071 | 10/9 | 9/8 | 9/8 | 0.313495 | 0.631284 | 0.00122724 | 0.839147 | 0.822984 | true |
| proof candidate | 17.945 | 0.5094 | 10/9 | 9/8 | 9/8 | 0.312828 | 0.629546 | 0.00122477 | 0.837958 | 0.822710 | true |
| upper immediate control | 17.9475 | 0.5117 | 10/9 | 9/8 | 9/8 | 0.312149 | 0.627818 | 0.00122221 | 0.838416 | 0.822431 | true |
| low-side control | 17.9225 | 0.4887 | 9/8 | 8/7 | 8/7 | 0.318335 | 0.645414 | 0.00124311 | 0.569388 | 0.825093 | false |
| weak control | 17.915 | 0.4818 | 9/8 | 8/7 | 8/7 | 0.319880 | 0.650734 | 0.00124726 | 0.569388 | 0.825835 | false |

Gate results:

| Gate | Value | Threshold | Pass |
| --- | ---: | --- | --- |
| strict neighboring 9/8 | 3 | >=2 | true |
| no exit | all clean rows | true | true |
| global outer false | all clean rows | true | true |
| outer/shell below 1.0 | all clean rows | <1.0 | true |
| stable tail area | 0.001605 | <=0.03 | true |
| stable return timing | 0.002333 | <=0.08 | true |
| stable inward flux | 0.000545 | <=0.02 | true |
| threshold-free candidate margin | 1100.496 | >25.0 | true |

Interpretation:

- The quarter-dt proof pack supports the passive release-phase rule at the stricter time step: the strict-clean proof-candidate cluster is `17.94-17.945`, phase `0.5048-0.5094`.
- The lower immediate/proof rows and low-side controls stay strict 8/7, so the result is not a threshold-only tie with the weak side.
- The upper immediate control at `17.9475` also stays strict 9/8. Treat it as compatible upper support, not permission to keep sweeping.
- The headline claim should be threshold-free stability plus conservative strict 9/8 preservation. Default 10/9 at quarter dt is useful, but do not claim the older default 11/10 count is time-step invariant.
- The next physics step was the requested one-step resolution lift with release phase recalibrated by this rule. It failed strict proof gates at `51^3`, so do not copy cutoffs blindly across resolution or auto-run a larger grid.

### Release-Phase Resolution Lift

Command:

```powershell
python main.py prototype-3d-release-phase-resolution-lift --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\release_phase_resolution_lift_3d_20260620_091834\release_phase_resolution_lift_report.md`
- Summary CSV: `runs\release_phase_resolution_lift_3d_20260620_091834\release_phase_resolution_lift_summary.csv`
- Threshold-robust CSV: `runs\release_phase_resolution_lift_3d_20260620_091834\release_phase_resolution_lift_threshold_robust_score.csv`
- Gates CSV: `runs\release_phase_resolution_lift_3d_20260620_091834\release_phase_resolution_lift_gates.csv`
- Classification: `release_phase_resolution_lift_failed`
- Setup: quarter dt only, `51^3`, neutral lattice, same physical domain, stronger sponge with same physical-width/strength rule, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 physical shell window, no active second pulses, no resonator layer

Resolution-lift rows:

| Role | Target Phase | Cutoff | Actual Phase | Default Count | Strict 0.35 | Strict 0.40 | Conservative | Retention | Outer/Shell | Tail Area t>50 | Timing Reg | Inward Flux |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| candidate | 0.5071 | 17.9425 | 0.5071 | 9/8 | 8/7 | 7/6 | 7/6 | 0.237233 | 0.692066 | 0.00116718 | 0.868792 | 0.802287 |
| low-side phase control | 0.5025 | 17.9375 | 0.5025 | 9/8 | 8/7 | 7/6 | 7/6 | 0.238003 | 0.695279 | 0.00116987 | 0.867345 | 0.802835 |
| weak negative phase control | 0.4818 | 17.915 | 0.4818 | 9/8 | 8/7 | 7/6 | 7/6 | 0.241008 | 0.710234 | 0.00117793 | 0.868441 | 0.804990 |

Gate results:

| Gate | Value | Threshold | Pass |
| --- | --- | --- | --- |
| candidate strict 9/8 | 7/6 | >=9/8 plus clean guards | false |
| no exit | true | true | true |
| global outer false | true | true | true |
| candidate outer/shell below 1.0 | 0.692066 | <1.0 | true |
| controls below candidate | candidate 7/6 / best control 7/6 | controls below candidate | false |
| tail area close to proof | 0.0489149 | <=0.35 relative | true |
| autocorrelation close to proof | 0.0000666 drop | drop<=0.01 | true |
| spectral concentration close to proof | 0.117124 | <=0.25 relative | true |
| return timing close to proof | 0.0296601 | <=0.2 | true |
| threshold-free candidate margin | -0.0265578 | >25.0 | false |
| energy accounting clean | added_work=0, work_error=1.6002e-07 | no post-cutoff work and matched work/area | true |

Interpretation:

- The `41^3` passive release-phase proof remains real within its numerical setting, but the strict 9/8 phase-separated pocket did not survive this controlled `51^3` lift.
- This was not active contamination: the candidate had no shell exit, global outer false, outer/shell below `1.0`, zero post-cutoff external work, and matched work per physical source area.
- Threshold-free lifecycle metrics remained close to the proof reference, so a clean packet still exists at `51^3`; what failed is the stronger conservative refocusing count and separation from controls.
- Do not auto-run `61^3`, tune nearby `51^3` phases, or add mechanisms from this result. The read-only failure-mode postmortem is complete and did not recommend a retry; any future grid step needs a new explicit mechanism.

### Release-Phase Resolution Postmortem

Command:

```powershell
python main.py prototype-3d-release-phase-resolution-postmortem
```

Latest summarized run:

- Local report: `runs\release_phase_resolution_postmortem_3d_20260620_100043\release_phase_resolution_postmortem_report.md`
- Summary CSV: `runs\release_phase_resolution_postmortem_3d_20260620_100043\release_phase_resolution_postmortem_summary.csv`
- Peak comparison CSV: `runs\release_phase_resolution_postmortem_3d_20260620_100043\release_phase_resolution_peak_comparison.csv`
- Recalibration prediction CSV: `runs\release_phase_resolution_postmortem_3d_20260620_100043\release_phase_resolution_recalibration_prediction.csv`
- Classification: `resolution_lift_blurred_returns_no_predictive_recalibration`
- Inputs: `runs\release_phase_proof_pack_3d_20260619_234039` versus `runs\release_phase_resolution_lift_3d_20260620_091834`

Postmortem result:

| Group | Cutoff | Phase | 0.20 Count | 0.30 Count | 0.40 Count | Last Peak | Tail Area | Radial V | Tail Radius |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| 41^3 proof winners | 17.94-17.945 | 0.5048-0.5094 | 12/11 | 10/9 | 9/8 | 78.2 | ~0.001227 | ~-0.075 | ~6.32 |
| 51^3 candidate | 17.9425 | 0.5071 | 11/10 | 9/8 | 7/6 | 69.36 | 0.001167 | -0.0578 | 7.416 |
| 51^3 controls | 17.9375, 17.915 | 0.5025, 0.4818 | 11/10 | 9/8 | 7/6 | 69.36-69.4 | 0.001170-0.001178 | -0.0582 to -0.0602 | 7.449-7.763 |

Interpretation:

- The `51^3` run did not simply lose all returns: the candidate still has 11/10 at the looser 0.20 peak detector, while the frozen/default/strict gates count only 9/8 and 7/6.
- This is below-gate blur/shrinkage plus early termination of accepted peaks, not shell exit or active contamination.
- The candidate arrives earlier by about `0.88`, first refocus moves later by about `1.2`, and the tail radius shifts outward by about `1.09`, but the shell-peak radius does not shift and both controls show the same pattern.
- The postmortem prediction is `no_recalibrated_retry`; do not run the one-candidate 51^3 retry from this evidence alone.

### Release-Phase Modal Audit

Command:

```powershell
python main.py prototype-3d-release-phase-modal-audit
```

Latest summarized run:

- Local report: `runs\release_phase_modal_audit_3d_20260620_110344\release_phase_modal_audit_report.md`
- Summary CSV: `runs\release_phase_modal_audit_3d_20260620_110344\modal_audit_summary.csv`
- Shell spectrum CSV: `runs\release_phase_modal_audit_3d_20260620_110344\shell_spectrum_comparison.csv`
- Return timing CSV: `runs\release_phase_modal_audit_3d_20260620_110344\return_timing_jitter.csv`
- Radial packet CSV: `runs\release_phase_modal_audit_3d_20260620_110344\radial_packet_width_comparison.csv`
- Phase coherence CSV: `runs\release_phase_modal_audit_3d_20260620_110344\phase_coherence_comparison.csv`
- Classification: `resolution_blur_mechanism_supported`
- Inputs: `runs\release_phase_proof_pack_3d_20260619_234039`, `runs\release_phase_resolution_lift_3d_20260620_091834`, `runs\release_phase_resolution_postmortem_3d_20260620_100043`, and `runs\central_burst_3d_20260620_103248`

Modal-audit comparison:

| Group | Rows | Dominant Freq | Conc | Bandwidth | Loose | Default | Strict | Tail Radius | Outer/Shell |
| --- | --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: |
| 41^3 proof cluster | 17.94-17.945 | 0.012807 | 0.740-0.742 | 0.1180 | 12/11 | 10/9 | 9/8 | 6.317-6.329 | 0.630-0.633 |
| 51^3 candidate/control rows | 17.9425, 17.9375, 17.915 | 0.012801-0.012807 | 0.828-0.838 | 0.1519-0.1529 | 11/10 | 9/8 | 7/6 | 7.416-7.763 | 0.692-0.710 |
| central best transient | 5.52 medium burst | 0 | 0 | 0 | 1/0 | 1/0 | 1/0 | 14.819 | 0.0179 |
| central 0.92 repeated contaminated | low-extreme burst | 0.011101 | 0.637 | 0.0220 | 4/2 | 4/2 | 3/2 | 15.143 | 6.85-6.86 |

Interpretation:

- The `51^3` lift did not lose the shell-energy band. Proof and lift rows share a dominant frequency near `0.012807`.
- The lifted rows did lose strict refocusing quality: proof rows are strict 9/8, while the `51^3` candidate and controls are strict 7/6.
- Loose-threshold recovery persists at `51^3`: candidate/control rows still show 11/10 at the loose detector, matching the postmortem's below-gate return finding.
- The blur evidence is spectral/radial rather than a simple low-coherence collapse: `51^3` spectral concentration is higher, but bandwidth grows by `0.290751` relative to proof and tail radius shifts outward by `1.21855`.
- The central HF contrast does not explain the passive branch. The cleanest central burst is transient, and the 0.92 repeated rows are shell-exiting and outer/shell contaminated.
- The audit identifies no mechanism-derived next candidate. Do not run a new `51^3` retry, larger grid, or central-burst expansion from this report alone.

### Release-Phase Dispersion Audit

Command:

```powershell
python main.py prototype-3d-release-phase-dispersion-audit
```

Latest summarized run:

- Local report: `runs\release_phase_dispersion_audit_3d_20260620_150931\release_phase_dispersion_audit_report.md`
- Summary CSV: `runs\release_phase_dispersion_audit_3d_20260620_150931\dispersion_blur_model_summary.csv`
- Feature CSV: `runs\release_phase_dispersion_audit_3d_20260620_150931\dispersion_feature_comparison.csv`
- Source discretization CSV: `runs\release_phase_dispersion_audit_3d_20260620_150931\source_discretization_comparison.csv`
- Shell-window scaling CSV: `runs\release_phase_dispersion_audit_3d_20260620_150931\shell_window_scaling_comparison.csv`
- Spatial phase audit CSV: `runs\release_phase_dispersion_audit_3d_20260620_150931\spatial_phase_coherence_audit.csv`
- Prediction CSV: `runs\release_phase_dispersion_audit_3d_20260620_150931\dispersion_blur_prediction.csv`
- Classification: `scalable_blur_model_supported`
- Inputs: `runs\release_phase_proof_pack_3d_20260619_234039`, `runs\release_phase_resolution_lift_3d_20260620_091834`, `runs\release_phase_resolution_postmortem_3d_20260620_100043`, and deterministic geometry reconstructed from `configs\long_validation_peak_0_92.json`

Dispersion/blur checks:

| Check | Value |
| --- | ---: |
| Proof dominant frequency mean | 0.0128074 |
| Lift dominant frequency mean | 0.0128052 |
| Lift bandwidth relative delta | 0.290751 |
| Lift bandwidth CV | 0.002802 |
| Tail radius shift | 1.39071 |
| Lift tail-radius CV | 0.01655 |
| Strict major loss | 2 |
| Lift loose-to-strict recovery | 4 |
| Source effective-area relative delta | 0.0505 |
| Source phase-strength delta | -0.0020 |
| Source width/dx relative delta | 0.25 |
| Shell width/dx relative delta | 0.25 |
| True spatial phase frames available | false |

Geometry comparison:

| Grid | dx | Source Width/dx | Source Cells | Effective Source Area | Phase Strength | Shell Width/dx | Shell Cells |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 41 | 1.0 | 1.333 | 8764 | 4463 | 0.8255 | 4.0 | 2556 |
| 51 | 0.8 | 1.667 | 13084 | 4237.568 | 0.8235 | 5.0 | 5010 |

Interpretation:

- The `51^3` blur is predictable across the candidate and controls: same modal band, consistent bandwidth growth, consistent tail-radius drift, strict 7/6 shrinkage, and loose 11/10 recovery.
- This is not currently a source-discretization correction: effective source area changed by only about `5%`, source phase circular strength barely changed, and physical source width stayed fixed.
- This is not currently a shell-window scaling correction: the shell window stayed physically fixed at radius `5` and width `4`; the different width in cells is expected from finer `dx`.
- The blocker is spatial phase data. Existing lifecycle artifacts do not store true shell phase frames, so the audit cannot design phase pre-compensation or source apodization safely.
- Prediction from this dispersion audit alone remained `none`: it did not authorize a source-shaped `51^3` candidate. Later spatial-frame and source-spectrum audits narrowed the remaining source-shaped option to temporal smoothing only.

### Spatial Phase Instrumentation

Command:

```powershell
python main.py prototype-3d-spatial-phase-instrumentation --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\spatial_phase_instrumentation_3d_20260620_170518\spatial_phase_instrumentation_report.md`
- Summary CSV: `runs\spatial_phase_instrumentation_3d_20260620_170518\spatial_phase_instrumentation_summary.csv`
- Frame index CSV: `runs\spatial_phase_instrumentation_3d_20260620_170518\spatial_phase_frame_index.csv`
- Shell displacement frames: `runs\spatial_phase_instrumentation_3d_20260620_170518\shell_displacement_frames.csv`
- Shell velocity frames: `runs\spatial_phase_instrumentation_3d_20260620_170518\shell_velocity_frames.csv`
- Radial phase frames: `runs\spatial_phase_instrumentation_3d_20260620_170518\radial_shell_phase_frames.csv`
- Shell phase by radius: `runs\spatial_phase_instrumentation_3d_20260620_170518\shell_phase_coherence_by_radius.csv`
- Angular phase CSV: `runs\spatial_phase_instrumentation_3d_20260620_170518\angular_shell_phase_coherence.csv`
- Node/antinode stability CSV: `runs\spatial_phase_instrumentation_3d_20260620_170518\node_antinode_stability_maps.csv`
- Phase drift CSV: `runs\spatial_phase_instrumentation_3d_20260620_170518\phase_drift_across_return_peaks.csv`
- Comparison CSV: `runs\spatial_phase_instrumentation_3d_20260620_170518\spatial_phase_41_vs_51_comparison.csv`
- Classification: `spatial_phase_decoherence_supported`

Fixed reproduction setup:

- `41^3` proof row: cutoff `17.94`, phase `0.5048`, quarter dt.
- `51^3` failed-lift candidate: cutoff `17.9425`, phase `0.5071`, quarter dt.
- Neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 shell window, no active second pulses, no resonator layer.
- Loose frame-capture threshold `0.20` was used only to store below-gate return evidence; default/strict event scoring remains unchanged.

Spatial phase comparison:

| Metric | 41^3 proof | 51^3 lift | Delta |
| --- | ---: | ---: | ---: |
| Default count | 10/9 | 9/8 | -1/-1 |
| Strict count | 9/8 | 7/6 | -2/-2 |
| Shell phase coherence mean | 0.738741 | 0.591512 | -0.147229 |
| Radial phase coherence mean | 0.795901 | 0.653694 | -0.142207 |
| Angular phase coherence mean | 0.739392 | 0.600653 | -0.138739 |
| Node phase stability mean | 0.362924 | 0.366907 | +0.00398 |
| Return radial centroid mean | 6.97064 | 7.05765 | +0.0870 |
| Return radial spread mean | 1.16086 | 1.14198 | -0.0163 relative |

Interpretation:

- The `51^3` candidate loses spatial phase organization across the shell, radial bins, and angular/spherical sectors.
- The failure is not explained by a wider coherent packet: return spread is slightly lower at `51^3`.
- The failure is not primarily shell-window centering: radial centroid shift is only about `0.087`.
- This result alone did not authorize source shaping, new cutoff tuning, `61^3`, central-burst expansion, defects, resonators, active pulses, or shell rings. The later phase-precompensation design rejected spatial precompensation; the later source-spectrum audit supports only temporal smoothing as a narrow separate gate.

### Spatial Phase Precompensation Design

Command:

```powershell
python main.py prototype-3d-spatial-phase-precompensation-design
```

Latest summarized run:

- Local report: `runs\spatial_phase_precomp_design_3d_20260620_175852\phase_precompensation_design_report.md`
- Phase-error modes CSV: `runs\spatial_phase_precomp_design_3d_20260620_175852\phase_error_modes.csv`
- Candidate JSON: `runs\spatial_phase_precomp_design_3d_20260620_175852\recommended_candidate.json`
- Rejected corrections CSV: `runs\spatial_phase_precomp_design_3d_20260620_175852\rejected_overfit_corrections.csv`
- Classification: `no_safe_phase_correction`

Design constraints:

- Read-only analysis of `runs\spatial_phase_instrumentation_3d_20260620_170518`.
- Allowed basis: global phase offset, per-face phase offsets, cubic phase-strength multiplier, one angular harmonic, and a tiny release-phase nudge only if measured phase drift is stable.
- Forbidden/rejected: cell-by-cell phase masks, broad cutoff tuning, frequency sweep, high-order angular harmonics, unstable release-phase nudge, and low-dimensional candidate when the fit is not explanatory.

Fit result:

| Metric | Value |
| --- | ---: |
| Matched shell-sector samples | 352 |
| Low-dimensional model R2 | 0.00530876 |
| Weighted RMSE | 0.975624 |
| Per-return global phase-error std | 1.04098 rad |
| Recommended global offset | -0.203649 rad |
| Max face offset | 0.0506322 rad |
| Cubic strength multiplier | 0.97664 |
| Angular harmonic amplitude | 0.0642295 rad |
| Release-phase nudge | 0 |
| Candidate recommended | false |

Interpretation:

- The 51^3 phase loss is real, but the captured error does not collapse into a stable low-dimensional boundary correction.
- Per-return global phase errors swing too much to justify even a small release-phase nudge.
- The precompensated `51^3` candidate was intentionally not run because the required `phase_precomp_candidate_supported` gate did not pass.

### Source Spectrum Design Audit

Command:

```powershell
python main.py prototype-3d-source-spectrum-design-audit
```

Latest summarized run:

- Local report: `runs\source_spectrum_design_audit_3d_20260620_181010\source_spectrum_design_audit_report.md`
- Summary CSV: `runs\source_spectrum_design_audit_3d_20260620_181010\source_spectrum_summary.csv`
- Source spectrum CSV: `runs\source_spectrum_design_audit_3d_20260620_181010\source_envelope_spectrum.csv`
- Candidate JSON: `runs\source_spectrum_design_audit_3d_20260620_181010\smooth_envelope_candidate.json`
- Rejected options CSV: `runs\source_spectrum_design_audit_3d_20260620_181010\rejected_source_spectrum_options.csv`
- Classification: `source_spectrum_narrowing_candidate_supported`

Design constraints:

- Read-only analysis only; no physics was run.
- Uses the existing dispersion audit, spatial phase instrumentation, and failed precompensation design artifacts.
- Keeps frequency `0.92`, cutoff/release phase, neutral lattice, grid target, source geometry, and total work proxy fixed.
- Tests only the theoretical spectrum effect of replacing the current continuous hard-cutoff envelope with a same-release smooth `sin^2` envelope.
- Rejects frequency sweeps, cutoff tuning, increased work, spatial phase precompensation, central burst, resonators, defects, and broad source-shape sweeps.

Source-spectrum result:

| Metric | Hard cutoff | Smooth same-release |
| --- | ---: | ---: |
| 41^3 release phase | 0.5048 | 0.5048 |
| 51^3 release phase | 0.5071 | 0.5071 |
| Source bandwidth mean | 0.106874 | 0.0321803 |
| Far sideband fraction mean | 0.0493964 | 0.000516074 |
| Smooth/hard bandwidth ratio | n/a | 0.301104 |
| Sideband reduction | n/a | 0.989552 |
| Work-proxy scale | 1.0 | about 1.633 |

Context folded into the classification:

| Existing evidence | Value |
| --- | ---: |
| Same modal band at 41^3/51^3 | true |
| Observed modal bandwidth growth | 0.290751 |
| Strict major loss | 2 |
| Max spatial coherence drop | 0.147229 |
| Phase precompensation classification | no_safe_phase_correction |
| Hard source spectrum delta from 41^3 to 51^3 | 0 |

Interpretation:

- The source-spectrum route was tested in `runs\smooth_envelope_resolution_lift_3d_20260620_192501` and failed the joint proof gates.
- The smooth `sin^2` envelope reduced source bandwidth to `0.301083` of the hard-control bandwidth and reduced sidebands by `0.989553`, but it produced a weaker retained shell packet: default `9/8`, strict `7/6`, loose `11/10`, and threshold-free shell/tail areas near `0.00306` / `0.00117`.
- The same-command hard control at the same cutoff/phase still failed strict 9/8 scale proof, but it was better than the smooth candidate: default `12/11`, strict `8/7`, loose `12/11`, and shell/radial/angular coherence `0.765266` / `0.812159` / `0.771228`.
- Do not continue with smooth-envelope variants, cutoff tuning, frequency tuning, spatial phase precompensation, source geometry changes, grid-size escalation, or medium changes from this result.

### Boundary Phase-Conjugate Control

Command:

```powershell
python main.py prototype-3d-boundary-phase-conjugate-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\boundary_phase_conjugate_3d_20260620_212918\boundary_phase_conjugate_report.md`
- Summary CSV: `runs\boundary_phase_conjugate_3d_20260620_212918\boundary_phase_conjugate_summary.csv`
- Threshold-robust CSV: `runs\boundary_phase_conjugate_3d_20260620_212918\boundary_phase_conjugate_threshold_robust_score.csv`
- Spatial comparison CSV: `runs\boundary_phase_conjugate_3d_20260620_212918\boundary_phase_conjugate_spatial_comparison.csv`
- Candidate JSON: `runs\boundary_phase_conjugate_3d_20260620_212918\boundary_phase_conjugate_candidate.json`
- Classification: `boundary_phase_conjugate_no_rescue`

Fixed setup:

- 41^3 proof row used only to derive the shell phase pattern.
- 51^3 hard control, phase-conjugate candidate, shuffled-patch phase control, amplitude-only control, phase-only control, and wrong-return-target control.
- Neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source.
- Frequency `0.92`, cutoff `17.9425`, release phase `0.5071`, matched work per physical source area, radius-5 shell window, quarter dt.
- No active second pulses, no resonator, no defects/traps/medium changes, no grid or cutoff tuning after seeing the result.
- Boundary mask is deliberately coarse: `6` faces x `4` x `4` patches = `96` patches, frozen before 51^3 rows run.

Result summary:

| Row | Default | Strict | Loose 0.20 | Shell Coh | Radial Coh | Angular Coh | Outer/Shell | Exit | Global Outer |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| hard control | 9/8 | 7/6 | 11/10 | 0.497980 | 0.564139 | 0.512359 | 0.692066 | false | false |
| phase-conjugate candidate | 9/8 | 7/6 | 11/10 | 0.495393 | 0.560093 | 0.513604 | 0.691673 | false | false |
| shuffled patch control | 9/8 | 7/6 | 11/10 | 0.495189 | 0.559831 | 0.513422 | 0.692670 | false | false |
| amplitude-only control | 9/8 | 7/6 | 11/10 | 0.495996 | 0.560556 | 0.514064 | 0.690480 | false | false |
| phase-only control | 9/8 | 7/6 | 11/10 | 0.497618 | 0.563974 | 0.512359 | 0.693785 | false | false |
| wrong-return control | 9/8 | 7/6 | 11/10 | 0.495892 | 0.560622 | 0.513578 | 0.689568 | false | false |

Interpretation:

- The measured boundary mirror did not restore strict 9/8 at 51^3 and did not improve spatial coherence toward the 41^3 proof row.
- The candidate slightly worsened shell and radial coherence versus the hard control; angular coherence improved only by about `0.00125`, below the predeclared gate.
- Shuffled patches did not fail, so the measured patch wavefront did not show a meaningful phase-conjugate signal in this basis.
- Cleanliness gates passed: no shell exit, global outer false, outer/shell below `1.0`, zero post-cutoff work, and matched work/area error around `3.5e-8`.
- This is a clean negative mechanism test, not active contamination. Do not continue into patch-mask tuning, higher patch counts, cell-by-cell masks, new source-shape variants, cutoff tuning, or larger-grid escalation from this result.

### Modal Sparsity Audit

Command:

```powershell
python main.py prototype-3d-modal-sparsity-audit
```

Latest summarized run:

- Local report: `runs\modal_sparsity_audit_3d_20260620_231602\modal_sparsity_audit_report.md`
- Summary CSV: `runs\modal_sparsity_audit_3d_20260620_231602\modal_sparsity_summary.csv`
- Sparse reconstruction CSV: `runs\modal_sparsity_audit_3d_20260620_231602\sparse_spectral_reconstruction.csv`
- Modal participation CSV: `runs\modal_sparsity_audit_3d_20260620_231602\modal_participation_ratio.csv`
- Timing/width CSV: `runs\modal_sparsity_audit_3d_20260620_231602\return_timing_width_comparison.csv`
- Peak-width/modal-density CSV: `runs\modal_sparsity_audit_3d_20260620_231602\peak_width_modal_density_relation.csv`
- Classification: `common_51_source_signature_supported`

Inputs:

- `runs\release_phase_proof_pack_3d_20260619_234039`
- `runs\release_phase_resolution_lift_3d_20260620_091834`
- `runs\spatial_phase_instrumentation_3d_20260620_170518`
- `runs\smooth_envelope_resolution_lift_3d_20260620_192501`
- `runs\boundary_phase_conjugate_3d_20260620_212918`

Key checks:

| Metric | 41^3 proof mean | 51^3 mean/control value |
| --- | ---: | ---: |
| Modes for 99% reconstruction | 9 | 17.4615 |
| Modal participation ratio | 1.7086 | 1.42156 |
| Strict major peaks | 8.8 | 7.07692 |
| Mean return period | 6.54178 | 6.07755 |
| Mean peak width | 67.5005 | 58.5318 |
| Source-control modes-for-99% CV | n/a | 0.06217 |
| Source-control participation CV | n/a | 0.00242 |

Control comparison:

| Control | Strict | Modes 90/95/99 | Participation | Period |
| --- | --- | --- | ---: | ---: |
| `51^3` release-lift candidate | 7/6 | 2/3/18 | 1.42908 | 6.055 |
| smooth-envelope hard control | 8/7 | 2/2/15 | 1.42664 | 6.33818 |
| smooth-envelope candidate | 7/6 | 2/3/18 | 1.42908 | 6.055 |
| phase-conjugate hard control | 7/6 | 2/3/18 | 1.42908 | 6.055 |
| phase-conjugate candidate | 7/6 | 2/3/17 | 1.42071 | 6.055 |
| shuffled patch control | 7/6 | 2/3/17 | 1.42220 | 6.055 |

Interpretation:

- The audit did not support the dramatic hypothesis that the `41^3` proof needs only `3-8` modes while `51^3` requires `20+`; the proof mean was `9`, and the `51^3` mean was below `20`.
- Return timing stayed beat-like: mean period shifted by about `7%`, within the audit tolerance, so the `51^3` rows mostly preserve return spacing.
- The half-height peak-width metric did not show `51^3` peak smearing; width decreased in this scalar metric, so the strict loss is not explained by simple wider scalar shell-energy peaks.
- The source-shaping conclusion is still strong: hard `51^3`, smooth-envelope, phase-conjugate, and shuffled-patch rows share a tight reconstruction/participation signature and the same strict-count loss. This supports treating smooth-envelope/source-shape/patch-mask work as exhausted for now.

### Return Family Gate Audit

Command:

```powershell
python main.py prototype-3d-return-family-gate-audit
```

Latest summarized run:

- Local report: `runs\return_family_gate_audit_3d_20260621_082543\return_family_gate_report.md`
- Summary CSV: `runs\return_family_gate_audit_3d_20260621_082543\return_family_gate_summary.csv`
- Return-window occupancy CSV: `runs\return_family_gate_audit_3d_20260621_082543\return_window_occupancy.csv`
- Threshold crossing CSV: `runs\return_family_gate_audit_3d_20260621_082543\threshold_crossing_table.csv`
- Return amplitude CSV: `runs\return_family_gate_audit_3d_20260621_082543\return_amplitude_by_index.csv`
- Plots: `indexed_return_strength_plot.png`, `threshold_crossings_plot.png`, `comb_score_plot.png`, `off_comb_energy_ratio_plot.png`
- Classification: `return_family_weakened_not_gate_artifact`

Inputs:

- `runs\release_phase_proof_pack_3d_20260619_234039`
- `runs\release_phase_resolution_lift_3d_20260620_091834`
- `runs\spatial_phase_instrumentation_3d_20260620_170518`
- `runs\smooth_envelope_resolution_lift_3d_20260620_192501`
- `runs\boundary_phase_conjugate_3d_20260620_212918`
- `runs\modal_sparsity_audit_3d_20260620_231602`

Key checks:

| Metric | 41^3 proof mean | 51^3 source-control mean |
| --- | ---: | ---: |
| Strict major peaks | 8.8 | 7.16667 |
| Return-window occupancy | 0.416667 | 0.555556 |
| Return comb score | 0.147618 | 0.226582 |
| Off-comb energy ratio | n/a | 1.13162 |
| Return period CV | n/a | 0.130895 |
| Rank-normalized strength ratio | n/a | 0.934342 |
| Prominence ratio | n/a | 1.01468 |
| Late return area survival | 0.653425 | 0.491263 |

Control comparison:

| Control | Strict | Occupancy | Comb | Off-comb | Strength |
| --- | --- | ---: | ---: | ---: | ---: |
| `51^3` release-lift candidate | 7/6 | 0.583333 | 0.238097 | 1.12830 | 0.891581 |
| smooth-envelope hard control | 8/7 | 0.416667 | 0.168857 | 1.14954 | 1.06421 |
| smooth-envelope candidate | 7/6 | 0.583333 | 0.238097 | 1.12830 | 0.891581 |
| phase-conjugate hard control | 7/6 | 0.583333 | 0.238097 | 1.12830 | 0.891581 |
| phase-conjugate candidate | 7/6 | 0.583333 | 0.238168 | 1.12767 | 0.893709 |
| shuffled patch control | 7/6 | 0.583333 | 0.238177 | 1.12759 | 0.892441 |

Interpretation:

- The strict `51^3` count loss is not a pure fixed-threshold artifact under this comb-window model.
- Timing remains coherent and occupancy is preserved relative to the proof rows, so the return family does not simply vanish.
- The separator is energy placement: source-control off-comb energy is high, late-return area survival is lower, and rank-normalized strength/prominence are not compressed enough to explain the strict loss as amplitude-only gate sensitivity.
- This supports treating the `51^3` passive scale-lift degradation as real return-family weakening, not as permission to tune detector thresholds, cutoffs, source shapes, or patch masks.

### Off-Comb Leakage Audit

Command:

```powershell
python main.py prototype-3d-off-comb-leakage-audit
```

Latest summarized run:

- Local report: `runs\off_comb_leakage_audit_3d_20260621_085347\off_comb_leakage_report.md`
- Summary CSV: `runs\off_comb_leakage_audit_3d_20260621_085347\off_comb_leakage_summary.csv`
- Radial leakage CSV: `runs\off_comb_leakage_audit_3d_20260621_085347\radial_leakage_by_window.csv`
- Angular leakage CSV: `runs\off_comb_leakage_audit_3d_20260621_085347\angular_leakage_by_sector.csv`
- Outer recycling CSV: `runs\off_comb_leakage_audit_3d_20260621_085347\outer_recycling_correlation.csv`
- Modal sideband CSV: `runs\off_comb_leakage_audit_3d_20260621_085347\modal_sideband_leakage.csv`
- Spatial pattern CSV: `runs\off_comb_leakage_audit_3d_20260621_085347\spatial_pattern_leakage.csv`
- Plots: `radial_leakage_plot.png`, `angular_coherence_plot.png`, `outer_recycling_plot.png`, `modal_sidebands_plot.png`, `pattern_similarity_decay_plot.png`
- Classification: `spatial_pattern_scrambling_supported`

Inputs:

- `runs\release_phase_proof_pack_3d_20260619_234039`
- `runs\release_phase_resolution_lift_3d_20260620_091834`
- `runs\spatial_phase_instrumentation_3d_20260620_170518`
- `runs\smooth_envelope_resolution_lift_3d_20260620_192501`
- `runs\boundary_phase_conjugate_3d_20260620_212918`
- `runs\modal_sparsity_audit_3d_20260620_231602`
- `runs\return_family_gate_audit_3d_20260621_082543`

Key checks:

| Leakage channel | 41^3 proof mean | 51^3 source-control mean | Supported? |
| --- | ---: | ---: | --- |
| Radial leakage ratio | 2.27848 | 2.22865 | no |
| Angular sector coherence | 0.991908 | 0.966652 | no |
| Outer/off-comb correlation | 0 | 0 | no |
| Modal sideband fraction | 0.0611077 | 0.0328853 | no |
| Spatial-pattern leakage | 0.495788 | 0.586679 | yes |
| Off-return outward flux fraction | 0.12857 | 0.156926 | tracked, not classifier-dominant |

Interpretation:

- The gate audit showed the strict-count loss is real; this audit localizes the strongest supported leakage channel to return-to-return spatial-pattern scrambling.
- The audit does not support a radial-window miss, delayed outer/sponge recycling, or modal-sideband leakage as the primary separator under the saved artifacts.
- The hard `51^3`, smooth-envelope, phase-conjugate, and shuffled-patch rows remain grouped as source-shaping failures. Do not turn this localization into a detector threshold change, source-mask fit, cutoff retune, or `61^3` escalation.

### Central HF Scattering Branch

Command:

```powershell
python main.py prototype-3d-central-burst-control --config configs\long_validation_peak_0_92.json
```

Latest summarized run:

- Local report: `runs\central_burst_3d_20260620_103248\central_burst_report.md`
- Summary CSV: `runs\central_burst_3d_20260620_103248\central_burst_summary.csv`
- Threshold-count CSV: `runs\central_burst_3d_20260620_103248\central_burst_threshold_counts.csv`
- Timeseries CSV: `runs\central_burst_3d_20260620_103248\central_burst_timeseries.csv`
- Events CSV: `runs\central_burst_3d_20260620_103248\central_burst_events.csv`
- Energy audit CSV: `runs\central_burst_3d_20260620_103248\central_burst_energy_audit.csv`
- Classification: `central_burst_transient`

Fixed setup:

- Neutral `41^3` lattice.
- Same physical domain and stronger sponge.
- No boundary drive.
- No active second pulse.
- No resonator layer.
- No defect variants.
- Central tiny-radius velocity burst.
- Frequency ladder: `0.92`, `1.84`, `3.68`, `5.52`, `7.36`.
- Energy ladder: `low`, `medium`, `high`, `extreme`.

Result summary:

| Row | Frequency | Energy | Work+ | Default | Conservative | Retention | Outer/Shell | Exit | Global Outer | Energy Error |
| --- | ---: | --- | ---: | --- | --- | ---: | ---: | --- | --- | ---: |
| best clean-low-outer | 5.52 | medium | 0.000351 | 1/0 | 1/0 | 0.001224 | 0.01786 | true | false | 0.0113 |
| half-dt check | 5.52 | medium | 0.000405 | 1/0 | 1/0 | 0.001233 | 0.01842 | true | false | 0.00432 |
| repeated-count example | 0.92 | low | 0.000332 | 4/2 | 3/2 | 0.00785 | 6.85 | true | false | 0.0510 |

Interpretation:

- This branch is separate from the passive release-phase rule and should not be described as an improvement to it.
- The cleanest central burst produced only a single post-burst shell-window peak, and its half-dt check repeated that single-pass result.
- The 0.92 rows produced repeated event counts, but they exited the shell window and had heavy outer/shell contamination, so they are not clean central refocusing.
- Energy accounting was clean across the ladder; the negative result is physical/diagnostic rather than accounting contamination.
- Do not broaden the central frequency/energy ladder, add defect variants, add resonators, add active pulses, or add boundary release to rescue this branch without a new mechanism-specific reason.

## Current Next Step

Run no new physics unless explicitly requested. The blind confirmation, half-dt numerical validation, fixed half-dt recentering map, quarter-dt proof pack, one-step `51^3` resolution lift, read-only postmortem, first central HF scattering ladder, read-only modal audit, read-only dispersion audit, spatial phase instrumentation reproduction, precompensation design, source-spectrum design audit, smooth-envelope `51^3` rescue test, measured boundary phase-conjugate mirror, read-only modal sparsity audit, read-only return-family gate audit, and read-only off-comb leakage audit are complete, so do not tune nearby cutoffs or broaden controls based on those results:

- Use `41^3`.
- Use the inner-sponge-edge source location and stronger sponge at the original width.
- Use neutral lattice as the primary reference.
- Treat the frozen proof-pack setup as canonical at `41^3`: neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 shell window, no active second pulses, no resonator layer.
- Use 9/8 as the conservative robust-count floor for the top cluster; do not claim 11/10 is threshold-invariant.
- Treat the failed `51^3` lift as a spatial phase decoherence/scale-loss problem unless new evidence says otherwise. The captured sector/radius phase maps did not produce a safe low-dimensional precompensation design, the smooth-envelope source-spectrum test did not rescue count or coherence, the measured patch-level boundary phase-conjugate mirror also failed the joint count/coherence gates, the modal sparsity audit found the source-shaped `51^3` rows share the same modal reconstruction/participation signature, the return-family gate audit classified the strict loss as real family weakening rather than a pure threshold artifact, and the off-comb leakage audit localized the strongest supported separator to spatial-pattern scrambling.
- Treat the confirmed strong pocket as centered near phase 0.50 cycles at baseline dt, the half-dt strict-clean window as shifted upward to `17.9375-17.945`, and the quarter-dt proof span as `17.94-17.945` with phase `0.5048-0.5094`.
- Keep primary injected work matched per physical source area.
- Do not repeat active second-pulse tests; direct-at-peak, reduced-work, first-refocus travel-time, and second-refocus travel-time pulses all disturbed the clean cycle.
- Do not expand passive boundary-inner-edge resonator variants yet; the first passive layer pass was energy-accounted but reduced strict counts.
- Track phase at cutoff for every row.
- Make near-shell arrival, refocus count, refocus ratio, tail retention, decay, radial stability, and flux balance primary 3D metrics.
- Rank by major shell-window peak count, refocus count, no shell exit, retention, outer/shell below `1.0`, decay closest to zero, global outer false, and phase at cutoff.
- Keep global radial peak as an artifact/boundary-residue check.
- Keep the grid tiny. The proof-motivated `51^3` scale check failed strict gates, and the postmortem did not recommend a recalibrated retry, so do not escalate to `61^3` without a new explicit mechanism.
- The modal audit supports a `resolution_blur_mechanism_supported` interpretation: the `51^3` rows retain the same dominant shell-energy band as the `41^3` proof cluster, but strict returns shrink, bandwidth grows, and tail radius moves outward. It does not identify a mechanism-derived source correction.
- Current conservative state: `41^3` passive release-phase proof supported; scalable passive packet-control law not established.
- Do not expand defect variants again unless there is a specific mechanism-driven design.
- Do not add traps, rotation, medium shaping, defects, frequency combinations, active second pulses, source-shape sweeps, modal-sparsity-derived source variants, return-gate-derived detector tuning, off-comb-derived source masks, or patch-mask tuning. The release-phase-recalibrated `51^3` candidate plus controls has already been run and failed strict gates; the postmortem says no single retry is predicted, smooth temporal narrowing failed, measured phase-conjugate patches failed, the modal sparsity audit did not identify a separating source-control signature, the return-family gate audit did not support detector-only rescue, and the off-comb leakage audit did not identify a safe correction axis. Any future scale check should be explicitly justified, not automatic.
- Keep `central_hf_scattering_branch` firewalled. The first pass classified as `central_burst_transient`; any future central-scattering work needs a specific new mechanism rather than a wider ladder.
- Do not run broad neighboring-frequency long sweeps yet.

## Documentation Must Stay In Sync

When this state changes, update:

- `ROADMAP.md`
- `docs/project_state.md`
- `README.md` if commands or outputs change
- `docs/architecture.md` if physics semantics or module ownership changes
