# Calibration Notes

These notes describe the current validation expectations for WaveEngine. They are not claims about real hardware or physical discovery; they are guardrails for interpreting the simulation output.

## Control Run

Use:

```powershell
python main.py run --config configs\control_no_drive.json
```

Expected behavior:

- total energy remains zero or near numerical zero
- no localization event labels should appear
- anomaly score should be near zero

This checks that the engine is not inventing energy or hard-coding anomalies.

## Baseline Uniform Defect Run

Use:

```powershell
python main.py run --config configs\baseline_uniform_defect.json
```

Expected behavior:

- energy enters from the boundaries and propagates inward
- the central defect may show modest retention or resonance labels
- anomaly score should be interpreted comparatively, not absolutely
- saved heatmaps should visibly mark the defect and metric core

This run is useful as a repeatable reference while tuning metrics.

## Sponge Boundary A/B Check

Use:

```powershell
python main.py run --config configs\baseline_uniform_defect.json
python main.py run --config configs\baseline_uniform_defect_sponge.json
```

Or run the paired sweep:

```powershell
python main.py sweep --sweep-config configs\boundary_ab_sweep.json
```

Expected behavior:

- the reflective config preserves the original free-edge behavior
- the sponge config adds a damping ramp near the lattice boundary
- central defect parameters should remain unchanged
- edge reflections should be reduced in the sponge run, but core metrics may also change because less reflected energy returns inward

This comparison is useful before interpreting central retention as a true defect effect.

## Nonlinear Threshold Probe

Use:

```powershell
python main.py sweep --sweep-config configs\nonlinear_threshold_probe_sweep.json
```

Expected behavior:

- the sweep varies drive amplitude while keeping the other parameters fixed
- nonlinear terms are enabled
- the sweep summary may add `cross_run_amplitude_threshold` when a neighboring amplitude run shows an abrupt increase in multiple core-localization metrics
- `nonlinear_threshold_jump` should be treated as a comparative hypothesis, not a proof of a physical discontinuity

## Random Probe Sweep

Use:

```powershell
python main.py sweep --sweep-config configs\random_probe_sweep.json
```

Expected behavior:

- the sampled parameter points are controlled by the sweep seed
- `sweep_*_plan.json` records the exact sampled points
- `sweep_*_report.md` links the top candidates and their evidence plots
- changing the seed should change the sampled parameter combinations

## Evidence Probe Sweep

Use:

```powershell
python main.py sweep --sweep-config configs\evidence_probe_sweep.json
```

Expected behavior:

- each run exports `core_spectrum_plot.png`
- the top-ranked candidate exports a `frame_sequence/` folder with a short heatmap sequence
- the Markdown sweep report links the spectrum and frame-sequence evidence

## Frequency Refinement Sweep

Use:

```powershell
python main.py sweep --sweep-config configs\frequency_refinement_sweep.json
```

Expected behavior:

- the sweep narrows around the current 0.95 drive-frequency candidate
- each run shares the same defect, damping, coupling, nonlinearity, and sponge boundary settings
- this should help distinguish a real frequency-localized response from a coarse three-point sweep artifact

## Frequency Band Characterization Sweep

Use:

```powershell
python main.py sweep --sweep-config configs\frequency_band_characterization_sweep.json
```

Expected behavior:

- the sweep maps the 0.90 to 1.08 drive-frequency band at finer spacing
- compare whether the strongest response is a single local maximum or a broad band
- if the response has multiple peaks, prioritize band characterization over one-point threshold claims
- sweep reports include a frequency-band analysis section when enough frequency points are present

## Rotating Phase Probe

Use:

```powershell
python main.py run --config configs\rotating_phase_probe.json
```

Expected behavior:

- angular diagnostics become relevant because the boundary phase varies around the lattice
- rotating-energy labels should only appear if the angular energy centroid shows coherent drift
- ring and rotation labels should be treated as hypotheses for review, not conclusions

## Current Validation Checks

The test suite checks:

- no-drive/no-damping energy stays bounded for a small perturbation
- damped unforced motion loses energy
- defect masks modify local stiffness, damping, coupling, and nonlinear values
- config loaders preserve nested values and coerce JSON arrays to tuples where needed
- single runs export all required evidence files
- metrics CSV and summary JSON schemas remain stable
- sweep results are ranked and a sweep summary file is written
- sponge boundary damping increases edge damping without touching a centered defect
- cross-run threshold annotations require nonlinear terms and paired amplitude/frequency neighbors

Run all validation checks with:

```powershell
python -m unittest discover -s tests
```

## Known Limitations

- The integrator is semi-implicit Euler, so conservative systems are expected to have bounded numerical energy oscillation, not exact conservation.
- The current anomaly score is a heuristic ranking tool. It helps prioritize evidence review but does not prove a physical anomaly.
- Cross-run nonlinear threshold labels are comparative hypotheses. They show abrupt metric changes between neighboring sweep runs, not proof of a physical discontinuity.
