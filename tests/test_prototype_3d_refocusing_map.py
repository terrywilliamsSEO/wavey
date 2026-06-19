"""Tests for the tiny 3D cutoff-frequency refocusing map."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_refocusing_map import (
    RefocusingMap3DOptions,
    _map_variant_plan,
    classify_refocusing_map,
)


class Prototype3DRefocusingMapTests(unittest.TestCase):
    def test_variant_plan_is_tiny_cross_map(self) -> None:
        options = RefocusingMap3DOptions()
        base = SimulationConfig()
        base.driver.frequency = 0.92
        base.driver.drive_cutoff_time = 16.0
        variants = _map_variant_plan(base, options)
        names = [variant.name for variant in variants]
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual(
            names,
            [
                "phase_offset_reference",
                "cutoff_long_reference",
                "frequency_high_reference",
                "combined_cutoff_long_frequency_high",
                "cutoff_low_frequency_high",
                "cutoff_high_frequency_high",
                "cutoff_long_frequency_low",
                "cutoff_long_frequency_higher",
            ],
        )
        self.assertEqual(len(variants), 8)
        self.assertAlmostEqual(by_name["cutoff_long_reference"].drive_cutoff_time, 18.0)
        self.assertAlmostEqual(by_name["cutoff_long_reference"].drive_frequency, 0.92)
        self.assertAlmostEqual(by_name["frequency_high_reference"].drive_cutoff_time, 16.0)
        self.assertAlmostEqual(by_name["frequency_high_reference"].drive_frequency, 0.94)
        self.assertAlmostEqual(by_name["combined_cutoff_long_frequency_high"].drive_cutoff_time, 18.0)
        self.assertAlmostEqual(by_name["combined_cutoff_long_frequency_high"].drive_frequency, 0.94)
        for variant in variants:
            self.assertEqual(variant.grid_size, 41)
            self.assertEqual(variant.drive_phase_mode, "cubic")
            self.assertAlmostEqual(variant.boundary_cubic_phase_sign, -1.0)
            self.assertAlmostEqual(variant.boundary_phase_offset, options.phase_offset)
            self.assertAlmostEqual(variant.defect_stiffness_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_damping_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_coupling_multiplier, 1.0)

    def test_classification_detects_strong_combined_result(self) -> None:
        rows = [
            _row("cutoff_long_reference", "cutoff_reference", peaks=9, refocus=8, retention=0.27, outer=0.81, exit_detected=False),
            _row("frequency_high_reference", "frequency_reference", peaks=8, refocus=7, retention=0.25, outer=0.68, exit_detected=False),
            _row("combined_cutoff_long_frequency_high", "combined", peaks=10, refocus=9, retention=0.32, outer=0.70, exit_detected=False, combined=True),
        ]

        result = classify_refocusing_map(rows, RefocusingMap3DOptions())

        self.assertEqual(result["label"], "combined_constructive_strong")
        self.assertEqual(result["best_variant"], "combined_cutoff_long_frequency_high")

    def test_classification_reports_single_axis_when_combined_does_not_win(self) -> None:
        rows = [
            _row("cutoff_long_reference", "cutoff_reference", peaks=9, refocus=8, retention=0.27, outer=0.81, exit_detected=False),
            _row("frequency_high_reference", "frequency_reference", peaks=8, refocus=7, retention=0.25, outer=0.68, exit_detected=False),
            _row("combined_cutoff_long_frequency_high", "combined", peaks=8, refocus=7, retention=0.22, outer=1.1, exit_detected=False, combined=True),
            _row("cutoff_high_frequency_high", "cutoff_frequency_map", peaks=9, refocus=8, retention=0.31, outer=0.75, exit_detected=False),
        ]

        result = classify_refocusing_map(rows, RefocusingMap3DOptions())

        self.assertEqual(result["label"], "local_map_improved_single_axis")
        self.assertEqual(result["best_variant"], "cutoff_high_frequency_high")


def _row(
    variant: str,
    role: str,
    *,
    peaks: int,
    refocus: int,
    retention: float,
    outer: float,
    exit_detected: bool,
    combined: bool = False,
    ratio: float = 2.0,
    decay: float = -0.03,
    global_outer: bool = False,
) -> dict:
    return {
        "variant": variant,
        "map_role": role,
        "combined_candidate": combined,
        "major_shell_peak_count": peaks,
        "refocus_peak_count": refocus,
        "refocus_peak_ratio_max": ratio,
        "tail_shell_retention": retention,
        "tail_outer_to_shell_mean": outer,
        "shell_exit_detected": exit_detected,
        "shell_exit_time": None if not exit_detected else 80.0,
        "post_cutoff_shell_decay_rate": decay,
        "global_peak_in_outer_window": global_outer,
    }


if __name__ == "__main__":
    unittest.main()
