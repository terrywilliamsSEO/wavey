"""Tests for single-run time-resolved mode diagnostics."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from simulation.config import DefectConfig, DriverConfig, SimulationConfig
from simulation.sweep import run_single_experiment
from simulation.time_resolved_diagnostics import DiagnosticOptions, _detect_breathing_state, diagnose_existing_run


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

    def test_breathing_detector_reports_raw_and_envelope_periods(self) -> None:
        config = _detector_config()
        metric_rows = _metric_rows_with_subpeaks()
        frame_rows = _frame_rows_from_metrics(metric_rows, config.driver.drive_cutoff_time or 0.0)
        radial_rows = _radial_rows(frame_rows)

        result = _detect_breathing_state(frame_rows, radial_rows, config, metric_rows)

        self.assertEqual(result["status"], "detected")
        self.assertTrue(result["subpeak_overcounting_possible"])
        self.assertIn("subpeak_overcounting_possible", result["labels"])
        self.assertIsNotNone(result["raw_peak_period"])
        self.assertIsNotNone(result["envelope_period"])
        self.assertLess(result["raw_peak_period"], result["envelope_period"])
        self.assertGreaterEqual(result["min_peak_separation"], 1.5)

    def test_breathing_detector_requires_retained_post_cutoff_energy(self) -> None:
        config = _detector_config()
        metric_rows = _metric_rows_with_subpeaks(post_scale=0.01, pre_peak=10.0)
        frame_rows = _frame_rows_from_metrics(metric_rows, config.driver.drive_cutoff_time or 0.0)
        radial_rows = _radial_rows(frame_rows)

        result = _detect_breathing_state(frame_rows, radial_rows, config, metric_rows)

        self.assertEqual(result["status"], "inconclusive")
        self.assertIsNone(result["label"])
        self.assertLess(result["post_cutoff_retention"], 0.05)


def _detector_config() -> SimulationConfig:
    return SimulationConfig(
        grid_size=15,
        dt=0.1,
        steps=120,
        driver=DriverConfig(frequency=0.92, amplitude=0.0, drive_cutoff_time=1.0),
    )


def _metric_rows_with_subpeaks(*, post_scale: float = 1.0, pre_peak: float = 1.0) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    cutoff = 1.0
    for idx in range(120):
        time = idx * 0.1
        if time <= cutoff:
            core = pre_peak * (0.5 + 0.5 * time / cutoff)
        else:
            phase = time - cutoff
            broad = 1.0 + 0.45 * np.sin(2.0 * np.pi * phase / 2.6)
            subpeak = 0.32 * np.sin(2.0 * np.pi * phase / 1.2)
            core = post_scale * (broad + subpeak)
        rows.append({"time": time, "core_energy": core})
    return rows


def _frame_rows_from_metrics(rows: list[dict[str, float]], cutoff: float) -> list[dict[str, float]]:
    frame_rows = []
    for idx, row in enumerate(rows):
        time = float(row["time"])
        if time <= cutoff and idx % 5 != 0:
            continue
        if time > cutoff and idx % 2 != 0:
            continue
        frame_rows.append(
            {
                "time": time,
                "core_energy": float(row["core_energy"]),
                "radial_peak_radius": 5.0 + 0.4 * np.sin(time),
            }
        )
    return frame_rows


def _radial_rows(frame_rows: list[dict[str, float]]) -> list[dict[str, float]]:
    return [{"time": row["time"], "corr_prev_profile": 0.86} for row in frame_rows]


if __name__ == "__main__":
    unittest.main()
