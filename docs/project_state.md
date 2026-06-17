# Project State

Last updated: 2026-06-16

## One-Screen Summary

WaveEngine is a Python simulation-first experiment engine for a 2D coupled oscillator lattice with a configurable central defect/cavity, boundary drivers, sponge damping, diagnostics, and targeted validation controls. There is no dashboard yet.

The main candidate under study is the long-run drive-frequency `0.92` case from `configs/long_validation_peak_0_92.json`.

Current interpretation:

- The 0.92 candidate shows persistent post-cutoff breathing localization across sponge and time-step controls.
- Legacy fixed-domain `per_cell` source handling is not physically invariant and should be treated as reference-only.
- Source-normalized fixed-domain controls now make emitter effective area and injected work comparable across 41/63/81.
- Under source-normalized fixed-domain controls, 63x63 and 81x81 converge to the same refined physical radial peak at `10.0`, while 41x41 peaks at `5.0`.
- The latest source-normalized diagnostic classified the radial result as `coarse_grid_artifact_likely`.
- The 63x63 short breathing period was audited and traced to peak-detector overcounting of small subpeaks on a broad core-energy plateau.
- Do not call this exotic physics.
- Do not run broad long sweeps until the breathing detector is hardened against subpeak overcounting.

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

- Local report: `runs\source_normalized_resolution_20260616_215926\source_normalized_resolution_report.md`
- Source normalization: `constant_total_work`
- Classification: `coarse_grid_artifact_likely`
- Primary finding: source geometry and injected work are now comparable across 41/63/81.
- Refined result: 63x63 and 81x81 converge at physical radial peak `10.0`, not the legacy `3.75`.
- 41x41 source-normalized peak is `5.0`, making the coarse grid the outlier under the controlled source.
- Caveat: the 63-grid diagnostic breathing period is short at `1.689`, so breathing-period stability needs a targeted audit.

Important source audit values:

| Grid | Source Amp | Effective Area | Effective Length | Injected Work | Work/Length |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 41 | 0.550 | 160.0 | 160.0 | 13.6886 | 0.085554 |
| 63 | 0.436 | 158.6 | 158.6 | 13.6886 | 0.085554 |
| 81 | 0.449 | 158.0 | 158.0 | 13.6886 | 0.085554 |

Important mode values:

| Grid | Ratio | Retention | Best Time | Period | Radial Peak | m=4 Strength |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 41 | 0.485 | 0.829 | 52.00 | 2.640 | 5.00 | 0.303 |
| 63 | 0.324 | 0.863 | 44.24 | 1.689 | 10.00 | 0.124 |
| 81 | 0.328 | 0.853 | 43.64 | 2.566 | 10.00 | 0.116 |

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

Current conclusion: the source-normalized 63-grid run does not clearly have a true doubled-frequency breathing envelope. The current detector overcounts subpeaks; future breathing detection should require peak separation and/or prominence.

## Current Next Step

Harden breathing-period detection:

- Add minimum-separation and/or prominence logic to `_detect_breathing_state`.
- Re-run source-normalized diagnostics or diagnose the existing 63-grid run after detector changes.
- Do not run broad neighboring-frequency long sweeps yet.

## Documentation Must Stay In Sync

When this state changes, update:

- `ROADMAP.md`
- `docs/project_state.md`
- `README.md` if commands or outputs change
- `docs/architecture.md` if physics semantics or module ownership changes
