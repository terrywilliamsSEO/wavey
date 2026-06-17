# Project State

Last updated: 2026-06-17

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
- Do not call this exotic physics.
- Do not run broad long sweeps. The next step is a small 31^3 3D prototype focused on spherical shell breathing.

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

## Current Next Step

Build a small 3D prototype:

- Start with `31^3`, not a large grid.
- Port only the narrow fixed-domain/sponge/boundary-source semantics needed to test the 2D mechanism in 3D.
- Look for retained spherical shell breathing and shell-radius stability, not just high core energy.
- Keep `boundary_rotating_m4_81` as the 2D source-geometry reference.
- Do not run broad neighboring-frequency long sweeps yet.

## Documentation Must Stay In Sync

When this state changes, update:

- `ROADMAP.md`
- `docs/project_state.md`
- `README.md` if commands or outputs change
- `docs/architecture.md` if physics semantics or module ownership changes
