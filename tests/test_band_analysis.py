"""Tests for frequency-band mode-shape diagnostics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from simulation.band_analysis import analyze_frequency_band, annotate_frequency_band_context
from simulation.config import DefectConfig, DriverConfig, SimulationConfig, save_json, to_jsonable_config
from simulation.mode_diagnostics import energy_shape_metrics


class BandAnalysisTests(unittest.TestCase):
    def test_same_shape_alternating_peaks_are_classified_as_structured_band(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summaries = _synthetic_frequency_summaries(Path(tmp), with_threshold=False)

            band = analyze_frequency_band(summaries)

            self.assertIsNotNone(band)
            assert band is not None
            self.assertEqual(band["classification"], "structured_resonance_band")
            self.assertGreater(band["mean_adjacent_shape_correlation"], 0.95)
            self.assertGreater(band["mean_adjacent_radial_correlation"], 0.95)

    def test_structured_band_downweights_frequency_threshold_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summaries = _synthetic_frequency_summaries(Path(tmp), with_threshold=True)

            annotated = annotate_frequency_band_context(summaries)
            flagged = next(summary for summary in annotated if summary["run_id"] == "run_002")

            self.assertEqual(flagged["frequency_band_classification"], "structured_resonance_band")
            self.assertTrue(flagged["frequency_band_threshold_downweighted"])
            self.assertNotIn("cross_run_frequency_threshold", flagged["detected_event_labels"])
            self.assertNotIn("nonlinear_threshold_jump", flagged["detected_event_labels"])
            self.assertEqual(flagged["cross_run_anomaly_bonus"], 0.0)
            self.assertEqual(flagged["anomaly_score"], flagged["base_anomaly_score"])


def _synthetic_frequency_summaries(root: Path, *, with_threshold: bool) -> list[dict]:
    frequencies = [0.9, 0.92, 0.94, 0.96, 0.98]
    ratios = [0.07, 0.11, 0.06, 0.1, 0.065]
    base_energy = _ring_energy()
    summaries = []
    for idx, (frequency, ratio) in enumerate(zip(frequencies, ratios), start=1):
        energy = base_energy * (1.0 + ratio)
        summary = _write_synthetic_run(root, f"run_{idx:03d}", frequency, ratio, energy)
        if with_threshold and idx == 2:
            summary["base_anomaly_score"] = 12.0
            summary["anomaly_score"] = 18.0
            summary["cross_run_anomaly_bonus"] = 6.0
            summary["cross_run_threshold_score"] = 0.5
            summary["cross_run_threshold_events"] = ["cross_run_frequency_threshold"]
            summary["cross_run_threshold_details"] = [{"scan_field": "drive_frequency"}]
            summary["detected_event_labels"] = ["cross_run_frequency_threshold", "nonlinear_threshold_jump"]
        summaries.append(summary)
    return summaries


def _write_synthetic_run(root: Path, run_id: str, frequency: float, ratio: float, energy: np.ndarray) -> dict:
    run_dir = root / run_id
    run_dir.mkdir()
    config = SimulationConfig(
        grid_size=energy.shape[0],
        nonlinear_strength=0.08,
        defect=DefectConfig(radius=2),
        driver=DriverConfig(frequency=frequency, amplitude=0.55),
    )
    config_payload = to_jsonable_config(config)
    config_payload["run_id"] = run_id
    save_json(run_dir / "config.json", config_payload)
    energy_path = run_dir / "best_energy_density.npy"
    np.save(energy_path, energy)
    shape_metrics = energy_shape_metrics(energy, config)
    summary = {
        "run_id": run_id,
        "path": str(run_dir),
        "best_energy_density_path": str(energy_path),
        "best_energy_well_ratio": ratio,
        "max_core_energy_fraction": ratio,
        "anomaly_score": ratio * 100.0,
        "base_anomaly_score": ratio * 100.0,
        "spectral_peak_frequency": 0.2,
        "spectral_purity": 0.4,
        "detected_event_labels": [],
        "plain_language_interpretation": "",
        **{f"best_frame_{key}": value for key, value in shape_metrics.items()},
    }
    save_json(run_dir / "summary.json", summary)
    return summary


def _ring_energy() -> np.ndarray:
    rows, cols = np.indices((9, 9), dtype=float)
    radius = np.sqrt((rows - 4.0) ** 2 + (cols - 4.0) ** 2)
    return np.exp(-((radius - 2.0) ** 2) / 0.45) + 0.02


if __name__ == "__main__":
    unittest.main()
