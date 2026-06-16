"""Tests for single-run time-resolved mode diagnostics."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from simulation.config import DefectConfig, DriverConfig, SimulationConfig
from simulation.sweep import run_single_experiment
from simulation.time_resolved_diagnostics import DiagnosticOptions, diagnose_existing_run


class TimeResolvedDiagnosticsTests(unittest.TestCase):
    def test_diagnose_existing_run_writes_required_artifacts(self) -> None:
        config = SimulationConfig(
            grid_size=15,
            steps=60,
            dt=0.04,
            global_damping=0.03,
            coupling_strength=0.8,
            nonlinear_strength=0.04,
            boundary_mode="sponge",
            boundary_damping_width=3,
            boundary_damping_strength=0.08,
            defect=DefectConfig(
                radius=2,
                stiffness_multiplier=0.7,
                damping_multiplier=0.8,
                coupling_multiplier=0.7,
            ),
            driver=DriverConfig(
                frequency=0.92,
                amplitude=0.2,
                drive_cutoff_time=0.8,
                phase_mode="uniform",
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_single_experiment(config, output_root=tmp, run_id="diagnostic_check")
            diagnostics = diagnose_existing_run(
                summary["path"],
                options=DiagnosticOptions(frame_interval=8, window_steps=6, save_frame_pngs=False),
                reference_root=tmp,
            )

            diag_dir = Path(diagnostics["diagnostics_path"])
            expected_files = {
                "frame_mode_diagnostics.csv",
                "radial_profile_timeseries.csv",
                "frame_timestamps.csv",
                "angular_mode_timeseries.csv",
                "frame_correlation_plot.png",
                "radial_peak_drift_plot.png",
                "radial_profile_heatmap.png",
                "angular_mode_plot.png",
                "mode_shape_diagnostics_report.md",
                "mode_shape_diagnostics_summary.json",
            }
            self.assertTrue(expected_files.issubset({path.name for path in diag_dir.iterdir()}))

            with (diag_dir / "frame_mode_diagnostics.csv").open("r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            self.assertGreater(len(rows), 3)
            self.assertIn("corr_to_best_frame", reader.fieldnames)
            self.assertIn("radial_peak_radius", reader.fieldnames)
            self.assertIn("annulus_fraction", reader.fieldnames)

            report_text = (diag_dir / "mode_shape_diagnostics_report.md").read_text(encoding="utf-8")
            self.assertIn("## Breathing Detection", report_text)
            self.assertIn("## Mode Transition Detection", report_text)
            self.assertIn("## Angular / Rotation", report_text)


if __name__ == "__main__":
    unittest.main()
