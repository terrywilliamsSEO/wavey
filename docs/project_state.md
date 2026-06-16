# Project State

Last updated: 2026-06-16

## One-Screen Summary

WaveEngine is a Python simulation-first experiment engine for a 2D coupled oscillator lattice with a configurable central defect/cavity, boundary drivers, sponge damping, diagnostics, and targeted validation controls. There is no dashboard yet.

The main candidate under study is the long-run drive-frequency `0.92` case from `configs/long_validation_peak_0_92.json`.

Current interpretation:

- The 0.92 candidate shows persistent post-cutoff breathing localization across sponge and time-step controls.
- The candidate is not yet fixed-domain resolution-resistant.
- Under true fixed-domain refinement, breathing persists, but the physical radial peak shifts inward and retention weakens at 81x81.
- Do not call this exotic physics.
- Do not run broad long sweeps until the fixed-domain resolution sensitivity is understood.

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

Current conclusion: the 0.92 breathing localization survives as a phenomenon, but the radial structure and retention are resolution-sensitive under fixed-domain physics. Next work should diagnose source normalization, radial profile behavior, and fixed-domain injection scaling before any broad search.

## Current Next Step

Diagnose fixed-domain resolution sensitivity:

- Review boundary source normalization across 41/63/81 grids.
- Inspect radial profile heatmaps and best-frame resampled similarity.
- Decide whether fixed-domain source amplitude should be normalized by emitter area, edge length, or cell area.
- Run a small source-normalization control if needed.

## Documentation Must Stay In Sync

When this state changes, update:

- `ROADMAP.md`
- `docs/project_state.md`
- `README.md` if commands or outputs change
- `docs/architecture.md` if physics semantics or module ownership changes
