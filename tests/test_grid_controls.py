"""Tests for targeted larger-grid control classification."""

from __future__ import annotations

import unittest

from simulation.grid_controls import classify_grid_control_results


class GridControlClassificationTests(unittest.TestCase):
    def test_grid_resistant_when_larger_grid_preserves_key_metrics(self) -> None:
        rows = [
            _row(
                "baseline_grid_41",
                grid_size=41,
                ratio=0.50,
                retention=0.87,
                period=2.667,
                best_time=47.76,
                core_fraction=0.34,
                core_density=0.00068,
            ),
            _row(
                "larger_grid_61",
                grid_size=61,
                ratio=0.44,
                retention=0.83,
                period=3.0,
                best_time=48.5,
                core_fraction=0.30,
                core_density=0.00045,
            ),
        ]

        result = classify_grid_control_results(rows)

        self.assertEqual(result["label"], "grid_resistant")
        self.assertTrue(all(result["checks"].values()))

    def test_grid_sensitive_when_core_density_collapses(self) -> None:
        rows = [
            _row(
                "baseline_grid_41",
                grid_size=41,
                ratio=0.50,
                retention=0.87,
                period=2.667,
                best_time=47.76,
                core_fraction=0.34,
                core_density=0.00068,
            ),
            _row(
                "larger_grid_61",
                grid_size=61,
                ratio=0.40,
                retention=0.82,
                period=3.0,
                best_time=48.5,
                core_fraction=0.30,
                core_density=0.00010,
            ),
        ]

        result = classify_grid_control_results(rows)

        self.assertEqual(result["label"], "grid_sensitive")
        self.assertFalse(result["checks"]["core_energy_density"])

    def test_end_limited_when_best_event_lands_at_run_end(self) -> None:
        rows = [
            _row(
                "baseline_grid_41",
                grid_size=41,
                ratio=0.50,
                retention=0.87,
                period=2.667,
                best_time=47.76,
                core_fraction=0.34,
                core_density=0.00068,
                physical_duration=56.0,
            ),
            _row(
                "larger_grid_63",
                grid_size=63,
                ratio=0.35,
                retention=0.45,
                period=8.68,
                best_time=55.96,
                core_fraction=0.26,
                core_density=0.00019,
                breathing=False,
                physical_duration=56.0,
                metric_period=3.52,
            ),
        ]

        result = classify_grid_control_results(rows)

        self.assertEqual(result["label"], "inconclusive_end_limited")

    def test_timing_shift_when_only_best_event_time_fails(self) -> None:
        rows = [
            _row(
                "baseline_grid_41",
                grid_size=41,
                ratio=0.50,
                retention=0.87,
                period=2.667,
                best_time=47.76,
                core_fraction=0.34,
                core_density=0.00068,
                physical_duration=56.0,
            ),
            _row(
                "larger_grid_63",
                grid_size=63,
                ratio=0.53,
                retention=0.81,
                period=2.4,
                best_time=74.68,
                core_fraction=0.35,
                core_density=0.00020,
                physical_duration=86.0,
            ),
        ]

        result = classify_grid_control_results(rows)

        self.assertEqual(result["label"], "grid_resistant_timing_shift")


def _row(
    variant: str,
    *,
    grid_size: int,
    ratio: float,
    retention: float,
    period: float | None,
    best_time: float,
    core_fraction: float,
    core_density: float,
    physical_duration: float = 56.0,
    metric_period: float | None = None,
    breathing: bool = True,
    angular_mode: int = 4,
) -> dict:
    return {
        "variant": variant,
        "grid_size": grid_size,
        "best_energy_well_ratio": ratio,
        "retention_score": retention,
        "best_event_time": best_time,
        "best_core_fraction": core_fraction,
        "best_core_energy_density": core_density,
        "physical_duration": physical_duration,
        "dt": 0.04,
        "metric_core_peak_period_after_cutoff": metric_period,
        "breathing_detected": breathing,
        "breathing_period": period,
        "strongest_angular_mode": angular_mode,
    }


if __name__ == "__main__":
    unittest.main()
