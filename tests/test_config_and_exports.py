"""Validation tests for config loading, metrics, and run artifacts."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from simulation.config import (
    DefectConfig,
    DriverConfig,
    SimulationConfig,
    SweepConfig,
    simulation_config_from_dict,
    sweep_config_from_dict,
)
from simulation.metrics import METRIC_FIELDS
from simulation.sweep import generate_sweep_points, run_single_experiment, run_sweep


EXPECTED_RUN_FILES = {
    "config.json",
    "metrics.csv",
    "summary.json",
    "best_energy_density.npy",
    "final_heatmap.png",
    "best_frame.png",
    "energy_well_ratio_plot.png",
    "core_vs_outer_energy_plot.png",
    "core_spectrum_plot.png",
}

EXPECTED_SUMMARY_KEYS = {
    "best_energy_well_ratio",
    "time_of_best_event",
    "retention_score",
    "localization_score",
    "anomaly_score",
    "best_frame_spatial_entropy_normalized",
    "best_frame_participation_fraction",
    "detected_event_labels",
    "plain_language_interpretation",
}


class ConfigAndExportTests(unittest.TestCase):
    def test_simulation_config_from_dict_coerces_driver_sides(self) -> None:
        config = simulation_config_from_dict(
            {
                "grid_size": 17,
                "boundary_mode": "sponge",
                "boundary_damping_width": 3,
                "boundary_damping_strength": 0.12,
                "defect": {"radius": 3},
                "driver": {"sides": ["left", "top"], "phase_mode": "rotating"},
            }
        )

        self.assertEqual(config.grid_size, 17)
        self.assertEqual(config.boundary_mode, "sponge")
        self.assertEqual(config.boundary_damping_width, 3)
        self.assertEqual(config.boundary_damping_strength, 0.12)
        self.assertEqual(config.defect.radius, 3)
        self.assertEqual(config.driver.sides, ("left", "top"))
        self.assertEqual(config.driver.phase_mode, "rotating")

    def test_sweep_config_from_dict_coerces_scan_values(self) -> None:
        sweep = sweep_config_from_dict(
            {
                "max_runs": 2,
                "sampling_mode": "random",
                "report_top_n": 1,
                "drive_frequency": [0.5, 0.7],
                "boundary_mode": ["reflective", "sponge"],
                "boundary_damping_width": [4, 6],
                "phase_mode": ["uniform", "rotating"],
            }
        )

        self.assertEqual(sweep.sampling_mode, "random")
        self.assertEqual(sweep.report_top_n, 1)
        self.assertEqual(sweep.drive_frequency, (0.5, 0.7))
        self.assertEqual(sweep.boundary_mode, ("reflective", "sponge"))
        self.assertEqual(sweep.boundary_damping_width, (4, 6))
        self.assertEqual(sweep.phase_mode, ("uniform", "rotating"))

    def test_single_run_writes_expected_files_and_schemas(self) -> None:
        config = small_export_config()
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_single_experiment(config, output_root=tmp, run_id="schema_check")
            run_dir = Path(tmp) / "schema_check"

            self.assertEqual({path.name for path in run_dir.iterdir()}, EXPECTED_RUN_FILES)
            self.assertEqual(summary["run_id"], "schema_check")

            with (run_dir / "metrics.csv").open("r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                self.assertEqual(reader.fieldnames, METRIC_FIELDS)
                rows = list(reader)
            self.assertEqual(len(rows), config.steps)

            with (run_dir / "summary.json").open("r", encoding="utf-8") as fh:
                saved_summary = json.load(fh)
            self.assertTrue(EXPECTED_SUMMARY_KEYS.issubset(saved_summary))
            self.assertIsInstance(saved_summary["detected_event_labels"], list)

    def test_sweep_ranks_runs_and_writes_sweep_summary(self) -> None:
        base_config = small_export_config()
        sweep_config = SweepConfig(
            max_runs=3,
            drive_frequency=(0.45, 0.6, 0.75),
            drive_amplitude=(0.2,),
            defect_radius=(2,),
            defect_stiffness_multiplier=(0.7,),
            defect_damping_multiplier=(0.8,),
            defect_coupling_multiplier=(0.7,),
            global_damping=(0.03,),
            coupling_strength=(0.8,),
            nonlinear_strength=(0.0,),
            phase_mode=("uniform",),
            export_frame_sequences=True,
            frame_sequence_top_n=1,
            frame_sequence_count=2,
        )

        with tempfile.TemporaryDirectory() as tmp:
            sweep_config.output_root = tmp
            ranked = run_sweep(base_config, sweep_config)

            self.assertEqual(len(ranked), 3)
            self.assertGreaterEqual(ranked[0]["anomaly_score"], ranked[1]["anomaly_score"])
            summary_files = list(Path(tmp).glob("sweep_*_summary.json"))
            self.assertEqual(len(summary_files), 1)
            plan_files = list(Path(tmp).glob("sweep_*_plan.json"))
            self.assertEqual(len(plan_files), 1)
            report_files = list(Path(tmp).glob("sweep_*_report.md"))
            self.assertEqual(len(report_files), 1)
            report_text = report_files[0].read_text(encoding="utf-8")
            self.assertIn("## Top Candidates", report_text)
            self.assertIn("Sampling mode", report_text)
            self.assertIn("core_spectrum_plot.png", report_text)
            self.assertIn("## Frequency Band Analysis", report_text)
            self.assertIn("Band classification", report_text)
            frame_dirs = list(Path(tmp).glob("sweep_*_*/frame_sequence"))
            self.assertEqual(len(frame_dirs), 1)
            self.assertEqual(len(list(frame_dirs[0].glob("frame_*.png"))), 2)

    def test_random_sampling_is_seeded_and_deterministic(self) -> None:
        sweep_config = SweepConfig(
            max_runs=4,
            seed=123,
            sampling_mode="random",
            drive_frequency=(0.45, 0.75, 1.05),
            drive_amplitude=(0.2, 0.5),
            defect_radius=(2, 3),
            defect_stiffness_multiplier=(0.7,),
            defect_damping_multiplier=(0.8,),
            defect_coupling_multiplier=(0.7,),
            global_damping=(0.03,),
            coupling_strength=(0.8,),
            nonlinear_strength=(0.0, 0.08),
            boundary_mode=("reflective", "sponge"),
            phase_mode=("uniform",),
        )
        first = generate_sweep_points(sweep_config)
        second = generate_sweep_points(sweep_config)
        sweep_config.seed = 456
        third = generate_sweep_points(sweep_config)

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertEqual(len(first), 4)
        self.assertEqual(len({tuple(sorted(point.items())) for point in first}), 4)


def small_export_config() -> SimulationConfig:
    return SimulationConfig(
        grid_size=15,
        steps=30,
        dt=0.04,
        global_damping=0.03,
        coupling_strength=0.8,
        defect=DefectConfig(
            radius=2,
            stiffness_multiplier=0.7,
            damping_multiplier=0.8,
            coupling_multiplier=0.7,
            nonlinear_strength=0.0,
        ),
        driver=DriverConfig(
            frequency=0.8,
            amplitude=0.2,
            drive_cutoff_time=0.7,
            phase_mode="uniform",
        ),
    )


if __name__ == "__main__":
    unittest.main()
