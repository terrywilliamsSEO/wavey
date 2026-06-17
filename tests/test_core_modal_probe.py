"""Tests for controlled core-modal probe support."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from simulation.config import DefectConfig, DriverConfig, SimulationConfig, simulation_config_from_dict
from simulation.core_modal_probe import (
    CoreModalProbeOptions,
    _breathing_detected_from_peak_summary,
    _post_cutoff_summary,
    _run_probe_variant,
    _write_report,
    classify_core_modal_probe,
)
from simulation.breathing_period_audit import _peak_summary
from simulation.lattice import Lattice2D


class CoreModalProbeTests(unittest.TestCase):
    def test_core_drive_config_parses_flat_options(self) -> None:
        config = simulation_config_from_dict(
            {
                "grid_size": 21,
                "drive_location": "core_region",
                "core_drive_radius_physical": 4.5,
                "core_drive_frequency": 0.92,
                "core_drive_amplitude": 0.4,
                "core_drive_phase": 0.25,
                "core_drive_mode": "burst",
                "core_drive_cutoff_time": 12.0,
                "normalize_core_drive_work": True,
                "target_core_drive_work": 1.5,
                "core_drive_work_reference": "boundary_reference",
            }
        )

        self.assertEqual(config.drive_location, "core_region")
        self.assertAlmostEqual(config.effective_core_drive_radius, 4.5)
        self.assertAlmostEqual(config.effective_core_drive_frequency, 0.92)
        self.assertAlmostEqual(config.core_drive_amplitude, 0.4)
        self.assertEqual(config.core_drive_mode, "burst")
        self.assertAlmostEqual(config.effective_core_drive_cutoff_time or 0.0, 12.0)
        self.assertTrue(config.normalize_core_drive_work)

    def test_core_drive_force_is_separate_from_boundary_drive(self) -> None:
        config = _small_core_config()
        lattice = Lattice2D(config)

        self.assertAlmostEqual(float(np.sum(np.abs(lattice.boundary_force(0.0)))), 0.0)
        self.assertGreater(float(np.sum(np.abs(lattice.core_force(0.0)))), 0.0)
        self.assertGreater(lattice.core_driver.effective_driven_area, 0.0)

    def test_core_probe_work_accounting_separates_core_and_boundary(self) -> None:
        config = _small_core_config()
        with tempfile.TemporaryDirectory() as tmp:
            summary = _run_probe_variant(config, output_root=tmp, run_id="core_work_check")

            self.assertGreater(summary["total_core_drive_work"], 0.0)
            self.assertAlmostEqual(summary["total_boundary_drive_work"], 0.0)
            self.assertGreater(summary["injected_work_per_core_area"], 0.0)
            self.assertTrue((Path(summary["path"]) / "injected_work_plot.png").exists())
            self.assertTrue((Path(summary["path"]) / "post_cutoff_decay_plot.png").exists())

    def test_post_cutoff_summary_ignores_active_forcing_peak(self) -> None:
        samples = []
        for idx, time in enumerate([0.0, 0.4, 0.8, 1.2]):
            samples.append(
                {
                    "time": time,
                    "energy_well_ratio": 99.0 if time <= 0.5 else 2.0 + idx,
                    "core_energy": 10.0 if time <= 0.5 else 1.0 + idx,
                    "total_energy": 12.0 + idx,
                    "localization_index": 1.0 + idx,
                    "center_to_surround_amplitude_ratio": 1.0,
                    "spectral_peak_frequency": 0.0,
                    "spectral_purity": 0.0,
                    "q_like_decay": 0.0,
                }
            )
        summary = _post_cutoff_summary("synthetic", _small_core_config(), samples, np.ones((9, 9)), cutoff=0.5)

        self.assertEqual(summary["post_cutoff_best_event_time"], 1.2)
        self.assertLess(summary["best_energy_well_ratio"], 99.0)

    def test_min_separated_breathing_detection_filters_subpeaks(self) -> None:
        rows = []
        values = [
            0.1,
            1.0,
            0.35,
            0.85,
            0.2,
            0.25,
            1.1,
            0.4,
            0.9,
            0.25,
            0.2,
            1.05,
            0.35,
            0.8,
            0.15,
        ]
        for idx, value in enumerate(values):
            rows.append({"time": float(idx) * 0.5, "core_energy": value})

        raw = _peak_summary(rows, cutoff=0.0, percentile=20.0)
        separated = _peak_summary(rows, cutoff=0.0, percentile=20.0, min_separation=1.4)

        self.assertGreater(raw["peak_count"], separated["peak_count"])
        self.assertTrue(_breathing_detected_from_peak_summary(separated, envelope_strength=0.5))

    def test_classification_high_retention_core_match(self) -> None:
        rows = [
            _classification_row("boundary_reference_63", "boundary", retention=0.8, period=2.7, radial_sim=1.0, frame_sim=1.0),
            _classification_row("core_burst_0p92_63", "core_region", retention=0.35, period=2.8, radial_sim=0.72, frame_sim=0.55),
        ]

        result = classify_core_modal_probe(rows)

        self.assertEqual(result["label"], "intrinsic_defect_breathing_mode_supported")

    def test_classification_no_core_retention(self) -> None:
        rows = [
            _classification_row("boundary_reference_63", "boundary", retention=0.8, period=2.7, radial_sim=1.0, frame_sim=1.0),
            _classification_row(
                "core_impulse_63",
                "core_region",
                retention=0.02,
                period=None,
                radial_sim=0.1,
                frame_sim=0.05,
                active_peak=10.0,
                post_peak=1.0,
                breathing=False,
            ),
        ]

        result = classify_core_modal_probe(rows)

        self.assertEqual(result["label"], "core_forcing_only_artifact")

    def test_report_generation(self) -> None:
        rows = [
            _classification_row("boundary_reference_63", "boundary", retention=0.8, period=2.7, radial_sim=1.0, frame_sim=1.0),
            _classification_row("core_burst_0p92_63", "core_region", retention=0.35, period=2.8, radial_sim=0.72, frame_sim=0.55),
        ]
        classification = classify_core_modal_probe(rows)
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "core_modal_probe_report.md"
            _write_report(
                report_path,
                "probe_test",
                _small_core_config(),
                rows,
                classification,
                {"variant": "core_burst_0p92_63", "period": 2.8, "radial_similarity": 0.72, "frame_similarity": 0.55},
                Path(tmp) / "plots",
                CoreModalProbeOptions(),
            )

            text = report_path.read_text(encoding="utf-8")
        self.assertIn("Core-Modal Probe Report", text)
        self.assertIn("intrinsic_defect_breathing_mode_supported", text)


def _small_core_config() -> SimulationConfig:
    return SimulationConfig(
        grid_size=15,
        steps=40,
        dt=0.04,
        fixed_domain=True,
        domain_width=14.0,
        domain_height=14.0,
        boundary_mode="sponge",
        boundary_damping_width=2,
        boundary_damping_width_physical=2.0,
        boundary_damping_strength=0.08,
        drive_location="core_region",
        core_radius_physical=3.0,
        core_drive_radius_physical=3.0,
        core_drive_amplitude=0.3,
        core_drive_mode="impulse",
        core_drive_cutoff_time=0.04,
        defect=DefectConfig(radius=2, radius_physical=2.0),
        driver=DriverConfig(amplitude=0.0, drive_cutoff_time=0.04),
    )


def _classification_row(
    variant: str,
    drive_location: str,
    *,
    retention: float,
    period: float | None,
    radial_sim: float,
    frame_sim: float,
    active_peak: float = 1.0,
    post_peak: float = 1.0,
    breathing: bool = True,
) -> dict:
    return {
        "variant": variant,
        "drive_location": drive_location,
        "core_drive_mode": "burst" if drive_location != "boundary" else "",
        "breathing_detected_after_cutoff": breathing,
        "breathing_period_after_cutoff": period,
        "post_cutoff_retention": retention,
        "radial_profile_similarity_to_boundary_reference": radial_sim,
        "best_frame_similarity_to_boundary_reference": frame_sim,
        "m4_strength_after_cutoff": 0.2,
        "active_core_energy_peak": active_peak,
        "post_cutoff_core_energy": post_peak,
    }


if __name__ == "__main__":
    unittest.main()
