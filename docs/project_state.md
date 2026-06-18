# Project State

Last updated: 2026-06-18

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
- Do not call this exotic physics.
- Do not run broad long sweeps or broad 3D sweeps. The next step is one tiny neutral-lattice boundary-phase negative control.

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

## Current Next Step

Pivot to structured boundary transport controls:

- Use `41^3`.
- Use the inner-sponge-edge source location and stronger sponge at the original width.
- Use neutral lattice as the primary reference.
- Run only a tiny boundary-phase negative control: sign-flip cubic repeat, same-coverage uniform phase, fixed-seed random phase, global phase offsets, and possibly face-offset controls.
- Keep injected work matched per physical source area.
- Make near-defect shell-window arrival, retention, and radial stability primary 3D metrics.
- Keep global radial peak as an artifact/boundary-residue check.
- Keep the grid tiny until this failure mode is understood.
- Do not expand defect variants again unless there is a specific mechanism-driven design.
- Do not run broad neighboring-frequency long sweeps yet.

## Documentation Must Stay In Sync

When this state changes, update:

- `ROADMAP.md`
- `docs/project_state.md`
- `README.md` if commands or outputs change
- `docs/architecture.md` if physics semantics or module ownership changes
