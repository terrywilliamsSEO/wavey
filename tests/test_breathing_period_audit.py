"""Tests for breathing-period peak-picking audits."""

from __future__ import annotations

import unittest

from simulation.breathing_period_audit import _classify


class BreathingPeriodAuditTests(unittest.TestCase):
    def test_overcounted_subpeaks_classification(self) -> None:
        rows = [
            _row("source_normalized_grid_63", "diagnostic_frames_current", 1.69),
            _row("source_normalized_grid_63", "metrics_min_sep_1.5", 2.49),
        ]

        result = _classify(rows)

        self.assertEqual(result["label"], "peak_detector_overcounts_subpeaks")

    def test_persistent_short_period_classification(self) -> None:
        rows = [
            _row("source_normalized_grid_63", "diagnostic_frames_current", 1.69),
            _row("source_normalized_grid_63", "metrics_min_sep_1.5", 1.82),
        ]

        result = _classify(rows)

        self.assertEqual(result["label"], "period_anomaly_persists")


def _row(variant: str, source: str, period: float) -> dict:
    return {"variant": variant, "source": source, "period": period}


if __name__ == "__main__":
    unittest.main()
