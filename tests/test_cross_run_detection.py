"""Tests for comparative cross-run threshold annotations."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simulation.config import save_json
from simulation.cross_run_detection import annotate_cross_run_thresholds


class CrossRunDetectionTests(unittest.TestCase):
    def test_amplitude_neighbor_jump_adds_threshold_annotation_and_bonus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            low = write_fake_run(
                tmp,
                run_id="low_amp",
                amplitude=0.2,
                frequency=0.9,
                best_ratio=0.02,
                core_fraction=0.025,
                retention=0.1,
                anomaly=5.0,
            )
            high = write_fake_run(
                tmp,
                run_id="high_amp",
                amplitude=0.8,
                frequency=0.9,
                best_ratio=0.08,
                core_fraction=0.08,
                retention=0.34,
                anomaly=16.0,
            )

            annotated = {item["run_id"]: item for item in annotate_cross_run_thresholds([low, high])}
            high_summary = annotated["high_amp"]
            low_summary = annotated["low_amp"]

            self.assertIn("cross_run_amplitude_threshold", high_summary["detected_event_labels"])
            self.assertIn("nonlinear_threshold_jump", high_summary["detected_event_labels"])
            self.assertGreater(high_summary["cross_run_threshold_score"], 0.0)
            self.assertGreater(high_summary["anomaly_score"], high_summary["base_anomaly_score"])
            self.assertEqual(low_summary["cross_run_threshold_score"], 0.0)

            saved = json.loads((Path(high_summary["path"]) / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("cross_run_amplitude_threshold", saved["cross_run_threshold_events"])

    def test_linear_neighbors_do_not_get_nonlinear_threshold_annotation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            low = write_fake_run(
                tmp,
                run_id="linear_low",
                amplitude=0.2,
                frequency=0.9,
                best_ratio=0.01,
                core_fraction=0.01,
                retention=0.05,
                anomaly=2.0,
                nonlinear=0.0,
            )
            high = write_fake_run(
                tmp,
                run_id="linear_high",
                amplitude=0.8,
                frequency=0.9,
                best_ratio=0.1,
                core_fraction=0.1,
                retention=0.4,
                anomaly=20.0,
                nonlinear=0.0,
            )

            annotated = {item["run_id"]: item for item in annotate_cross_run_thresholds([low, high])}

            self.assertNotIn("cross_run_amplitude_threshold", annotated["linear_high"]["detected_event_labels"])
            self.assertEqual(annotated["linear_high"]["cross_run_threshold_score"], 0.0)


def write_fake_run(
    root: str,
    *,
    run_id: str,
    amplitude: float,
    frequency: float,
    best_ratio: float,
    core_fraction: float,
    retention: float,
    anomaly: float,
    nonlinear: float = 0.08,
) -> dict:
    run_dir = Path(root) / run_id
    run_dir.mkdir()
    save_json(
        run_dir / "config.json",
        {
            "run_id": run_id,
            "grid_size": 21,
            "steps": 100,
            "dt": 0.04,
            "base_stiffness": 1.0,
            "coupling_strength": 0.9,
            "global_damping": 0.02,
            "nonlinear_strength": nonlinear,
            "boundary_mode": "reflective",
            "boundary_damping_width": 6,
            "boundary_damping_strength": 0.08,
            "defect": {
                "radius": 3,
                "stiffness_multiplier": 0.65,
                "damping_multiplier": 0.75,
                "coupling_multiplier": 0.6,
                "nonlinear_strength": 0.0,
            },
            "driver": {
                "sides": ["left", "right", "top", "bottom"],
                "frequency": frequency,
                "amplitude": amplitude,
                "phase_offset": 0.0,
                "mode": "continuous",
                "drive_cutoff_time": 8.0,
                "phase_mode": "uniform",
                "rotating_phase_winding": 1,
            },
            "seed": 7,
        },
    )
    summary = {
        "run_id": run_id,
        "path": str(run_dir),
        "best_energy_well_ratio": best_ratio,
        "time_of_best_event": 1.0,
        "retention_score": retention,
        "localization_score": 7.0,
        "max_core_energy_fraction": core_fraction,
        "anomaly_score": anomaly,
        "detected_event_labels": [],
        "plain_language_interpretation": "Synthetic summary for cross-run threshold test.",
    }
    save_json(run_dir / "summary.json", summary)
    return summary


if __name__ == "__main__":
    unittest.main()
