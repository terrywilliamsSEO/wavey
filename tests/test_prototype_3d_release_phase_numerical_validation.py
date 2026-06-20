"""Tests for release-phase numerical validation."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_release_phase_numerical_validation import (
    ReleasePhaseNumericalValidationOptions,
    _variant_plan,
    classify_release_phase_numerical_validation,
)


class Prototype3DReleasePhaseNumericalValidationTests(unittest.TestCase):
    def test_variant_plan_keeps_fixed_numerical_scope(self) -> None:
        base = SimulationConfig()
        options = ReleasePhaseNumericalValidationOptions()

        variants = _variant_plan(base, options)

        self.assertEqual(len(variants), 8)
        self.assertEqual([variant.drive_cutoff_time for variant in variants[:4]], list(options.cutoffs))
        self.assertEqual([variant.drive_cutoff_time for variant in variants[4:]], list(options.cutoffs))
        self.assertEqual([getattr(variant, "_dt_variant") for variant in variants[:4]], ["baseline_dt"] * 4)
        self.assertEqual([getattr(variant, "_dt_variant") for variant in variants[4:]], ["half_dt"] * 4)
        self.assertTrue(all(variant.grid_size == 41 for variant in variants))
        self.assertTrue(all(variant.drive_frequency == 0.92 for variant in variants))
        self.assertTrue(all(variant.drive_phase_mode == "cubic" for variant in variants))
        self.assertTrue(all(variant.boundary_cubic_phase_sign == -1.0 for variant in variants))
        self.assertTrue(all(variant.boundary_phase_offset == 0.0 for variant in variants))
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(variant.second_pulse_duration == 0.0 for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))
        self.assertEqual(variants[0].dt, base.dt)
        self.assertEqual(variants[4].dt, base.dt * 0.5)

    def test_variant_plan_quarter_dt_is_explicit(self) -> None:
        options = ReleasePhaseNumericalValidationOptions(include_quarter_dt=True)

        variants = _variant_plan(SimulationConfig(), options)

        self.assertEqual(len(variants), 12)
        self.assertEqual([getattr(variant, "_dt_variant") for variant in variants[8:]], ["quarter_dt"] * 4)
        self.assertEqual(variants[8].dt, SimulationConfig().dt * 0.25)

    def test_classifies_numerically_confirmed_when_half_dt_preserves_order(self) -> None:
        rows = [
            _row("base_strong_a", "predicted_strong", "baseline_dt", 17.932885, major=9, refocus=8, score=9811.0),
            _row("base_strong_b", "predicted_strong", "baseline_dt", 17.937885, major=9, refocus=8, score=9810.0),
            _row("base_low", "predicted_low_edge_control", "baseline_dt", 17.9225, major=8, refocus=7, score=8700.0),
            _row("half_strong_a", "predicted_strong", "half_dt", 17.932885, major=9, refocus=8, score=9801.0),
            _row("half_strong_b", "predicted_strong", "half_dt", 17.937885, major=9, refocus=8, score=9800.0),
            _row("half_low", "predicted_low_edge_control", "half_dt", 17.9225, major=8, refocus=7, score=8700.0),
        ]

        classification = classify_release_phase_numerical_validation(rows)

        self.assertEqual(classification["label"], "release_phase_numerically_confirmed")

    def test_classifies_failed_when_low_control_matches_half_dt_strict_floor(self) -> None:
        rows = [
            _row("base_strong", "predicted_strong", "baseline_dt", 17.932885, major=9, refocus=8, score=9811.0),
            _row("base_low", "predicted_low_edge_control", "baseline_dt", 17.9225, major=8, refocus=7, score=8700.0),
            _row("half_strong", "predicted_strong", "half_dt", 17.932885, major=9, refocus=8, score=9800.0),
            _row("half_low", "predicted_low_edge_control", "half_dt", 17.9225, major=9, refocus=8, score=8700.0),
        ]

        classification = classify_release_phase_numerical_validation(rows)

        self.assertEqual(classification["label"], "release_phase_failed")

    def test_classifies_dt_sensitive_when_half_dt_strong_degrades(self) -> None:
        rows = [
            _row("base_strong", "predicted_strong", "baseline_dt", 17.932885, major=9, refocus=8, score=9811.0),
            _row("base_low", "predicted_low_edge_control", "baseline_dt", 17.9225, major=8, refocus=7, score=8700.0),
            _row("half_strong", "predicted_strong", "half_dt", 17.932885, major=8, refocus=7, score=8700.0, timing=0.70),
            _row("half_low", "predicted_low_edge_control", "half_dt", 17.9225, major=7, refocus=6, score=8690.0, timing=0.90),
        ]

        classification = classify_release_phase_numerical_validation(rows)

        self.assertEqual(classification["label"], "release_phase_dt_sensitive")

    def test_classifies_inconclusive_when_counts_shift_but_threshold_free_order_holds(self) -> None:
        rows = [
            _row("base_strong", "predicted_strong", "baseline_dt", 17.932885, major=10, refocus=9, score=10900.0),
            _row("base_low", "predicted_low_edge_control", "baseline_dt", 17.9225, major=8, refocus=7, score=8700.0),
            _row("half_strong", "predicted_strong", "half_dt", 17.932885, major=9, refocus=8, score=9800.0, timing=0.90),
            _row("half_low", "predicted_low_edge_control", "half_dt", 17.9225, major=8, refocus=7, score=8700.0, timing=0.86),
        ]

        classification = classify_release_phase_numerical_validation(rows)

        self.assertEqual(classification["label"], "release_phase_inconclusive")


def _row(
    variant: str,
    role: str,
    dt_variant: str,
    cutoff: float,
    *,
    major: int,
    refocus: int,
    score: float,
    default: tuple[int, int] = (10, 9),
    timing: float = 0.85,
) -> dict:
    return {
        "variant": variant,
        "prediction_role": role,
        "dt_variant": dt_variant,
        "drive_cutoff_time": cutoff,
        "cutoff_phase_cycles": 0.50,
        "default_major_peaks_at_0p30": default[0],
        "default_refocus_peaks_at_0p30": default[1],
        "conservative_major_peaks": major,
        "conservative_refocus_peaks": refocus,
        "retention": 0.31,
        "outer_shell": 0.63,
        "decay": -0.024,
        "no_exit": True,
        "global_outer_false": True,
        "post_cutoff_shell_area": 0.0028,
        "tail_area_after_t50": 0.0012,
        "return_timing_regularity": timing,
        "conservative_score": score,
    }


if __name__ == "__main__":
    unittest.main()
