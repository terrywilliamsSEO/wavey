"""Tests for targeted time-step control classification."""

from __future__ import annotations

import unittest

from simulation.numerical_controls import classify_dt_control_results


class DtControlClassificationTests(unittest.TestCase):
    def test_numerically_stable_when_half_step_preserves_key_metrics(self) -> None:
        rows = [
            _row("baseline_dt_0p04", dt=0.04, ratio=0.50, retention=0.87, period=2.667, best_time=47.76),
            _row("half_dt_0p02", dt=0.02, ratio=0.46, retention=0.84, period=3.0, best_time=48.1),
        ]

        result = classify_dt_control_results(rows)

        self.assertEqual(result["label"], "numerically_stable")
        self.assertTrue(all(result["checks"].values()))

    def test_dt_sensitive_when_absolute_core_energy_collapses(self) -> None:
        rows = [
            _row("baseline_dt_0p04", dt=0.04, ratio=0.50, retention=0.87, period=2.667, best_time=47.76),
            _row(
                "half_dt_0p02",
                dt=0.02,
                ratio=0.45,
                retention=0.82,
                period=3.0,
                best_time=48.1,
                core_energy=0.01,
            ),
        ]

        result = classify_dt_control_results(rows)

        self.assertEqual(result["label"], "dt_sensitive")
        self.assertFalse(result["checks"]["absolute_core_energy"])

    def test_metric_core_peak_period_can_rescue_sampled_diagnostic_period(self) -> None:
        rows = [
            _row(
                "baseline_dt_0p04",
                dt=0.04,
                ratio=0.50,
                retention=0.87,
                period=2.667,
                best_time=47.76,
                metric_period=2.55,
            ),
            _row(
                "half_dt_0p02",
                dt=0.02,
                ratio=0.51,
                retention=0.87,
                period=4.0,
                best_time=47.72,
                metric_period=2.98,
            ),
        ]

        result = classify_dt_control_results(rows)

        self.assertEqual(result["label"], "numerically_stable")
        self.assertEqual(result["period_check"]["source"], "metric_core_peak_period")


def _row(
    variant: str,
    *,
    dt: float,
    ratio: float,
    retention: float,
    period: float | None,
    best_time: float,
    core_energy: float = 0.055,
    metric_period: float | None = None,
    breathing: bool = True,
    angular_mode: int = 4,
) -> dict:
    return {
        "variant": variant,
        "dt": dt,
        "best_energy_well_ratio": ratio,
        "retention_score": retention,
        "best_event_time": best_time,
        "best_core_energy": core_energy,
        "metric_core_peak_period_after_cutoff": metric_period,
        "breathing_detected": breathing,
        "breathing_period": period,
        "strongest_angular_mode": angular_mode,
    }


if __name__ == "__main__":
    unittest.main()
