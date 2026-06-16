"""Tests for targeted artifact-control classification."""

from __future__ import annotations

import unittest

from simulation.artifact_controls import classify_artifact_control_results


class ArtifactControlClassificationTests(unittest.TestCase):
    def test_survives_stronger_sponge_when_key_metrics_preserve(self) -> None:
        rows = [
            _row("original", ratio=0.5, retention=0.88, period=2.7, best_time=48.0, r2=0.89),
            _row("stronger_sponge", ratio=0.32, retention=0.72, period=2.9, best_time=50.0, r2=0.74),
            _row("wider_sponge", ratio=0.30, retention=0.70, period=2.8, best_time=49.0, r2=0.71),
            _row("stronger_wider_sponge", ratio=0.25, retention=0.60, period=3.0, best_time=51.0, r2=0.65),
        ]

        result = classify_artifact_control_results(rows)

        self.assertEqual(result["label"], "survives_stronger_sponge")
        self.assertTrue(result["stronger_preserves"])

    def test_boundary_reflection_likely_when_absorption_destroys_signal(self) -> None:
        rows = [
            _row("original", ratio=0.5, retention=0.88, period=2.7, best_time=48.0, r2=0.89),
            _row("stronger_sponge", ratio=0.08, retention=0.20, period=None, best_time=30.0, r2=0.1, breathing=False),
            _row("wider_sponge", ratio=0.09, retention=0.25, period=None, best_time=31.0, r2=0.2, breathing=False),
            _row("stronger_wider_sponge", ratio=0.07, retention=0.18, period=None, best_time=32.0, r2=0.1, breathing=False),
        ]

        result = classify_artifact_control_results(rows)

        self.assertEqual(result["label"], "boundary_reflection_likely")


def _row(
    variant: str,
    *,
    ratio: float,
    retention: float,
    period: float | None,
    best_time: float,
    r2: float,
    breathing: bool = True,
) -> dict:
    return {
        "variant": variant,
        "best_energy_well_ratio": ratio,
        "retention_score": retention,
        "best_event_time": best_time,
        "breathing_detected": breathing,
        "breathing_period": period,
        "strongest_angular_mode_strength": 0.36 if breathing else 0.05,
        "angular_phase_drift": 15.0 if breathing else 0.2,
        "angular_phase_trend_r2": r2,
    }


if __name__ == "__main__":
    unittest.main()
