"""Tests for the tiny 3D cutoff phase/timing map."""

from __future__ import annotations

import math
import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_cutoff_phase_map import (
    CutoffPhaseMap3DOptions,
    _cutoff_phase_cycles,
    _variant_plan,
    classify_cutoff_phase_map,
)


class Prototype3DCutoffPhaseMapTests(unittest.TestCase):
    def test_variant_plan_keeps_tiny_timing_scope(self) -> None:
        base = SimulationConfig()
        base.driver.frequency = 0.92
        base.driver.drive_cutoff_time = 16.0
        options = CutoffPhaseMap3DOptions()

        variants = _variant_plan(base, options)
        names = [variant.name for variant in variants]
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual(
            names,
            [
                "phase_offset_cutoff_minus_1p0",
                "phase_offset_cutoff_minus_0p5",
                "phase_offset_cutoff_reference",
                "phase_offset_cutoff_plus_0p5",
                "phase_offset_cutoff_plus_1p0",
                "phase_offset_delta_minus_0p0625",
                "phase_offset_delta_plus_0p0625",
                "sign_flip_cutoff_minus_0p5",
                "sign_flip_cutoff_reference",
                "sign_flip_cutoff_plus_0p5",
            ],
        )
        self.assertEqual(len(variants), 10)
        self.assertAlmostEqual(by_name["phase_offset_cutoff_reference"].drive_cutoff_time, 18.0)
        self.assertAlmostEqual(by_name["phase_offset_cutoff_reference"].drive_frequency, 0.92)
        self.assertAlmostEqual(by_name["phase_offset_cutoff_reference"].boundary_phase_offset, 0.5 * math.pi)
        self.assertAlmostEqual(by_name["sign_flip_cutoff_reference"].boundary_phase_offset, 0.0)
        for variant in variants:
            self.assertEqual(variant.grid_size, 41)
            self.assertEqual(variant.drive_phase_mode, "cubic")
            self.assertAlmostEqual(variant.boundary_cubic_phase_sign, -1.0)
            self.assertAlmostEqual(variant.defect_stiffness_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_damping_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_coupling_multiplier, 1.0)

    def test_cutoff_phase_includes_global_phase_offset(self) -> None:
        base = SimulationConfig()
        base.driver.frequency = 0.92
        options = CutoffPhaseMap3DOptions()
        variant = _variant_plan(base, options)[2]

        phase = _cutoff_phase_cycles(variant)

        self.assertAlmostEqual(phase, (0.92 * 18.0 + 0.25) % 1.0)

    def test_classification_detects_strong_timing_island(self) -> None:
        rows = [
            _row("phase_offset_cutoff_reference", peaks=9, refocus=8, retention=0.269, outer=0.809, phase=0.81),
            _row("phase_offset_cutoff_plus_0p5", peaks=10, refocus=9, retention=0.32, outer=0.70, phase=0.86),
        ]

        result = classify_cutoff_phase_map(rows, CutoffPhaseMap3DOptions())

        self.assertEqual(result["label"], "cutoff_phase_timing_island_supported")
        self.assertEqual(result["best_variant"], "phase_offset_cutoff_plus_0p5")

    def test_classification_reports_tolerant_without_improvement(self) -> None:
        rows = [
            _row("phase_offset_cutoff_reference", peaks=9, refocus=8, retention=0.269, outer=0.809, phase=0.81),
            _row("phase_offset_cutoff_plus_0p5", peaks=8, refocus=7, retention=0.25, outer=0.82, phase=0.86),
        ]

        result = classify_cutoff_phase_map(rows, CutoffPhaseMap3DOptions())

        self.assertEqual(result["label"], "cutoff_phase_tolerant_no_improvement")


def _row(
    variant: str,
    *,
    peaks: int,
    refocus: int,
    retention: float,
    outer: float,
    phase: float,
    family: str = "phase_offset",
    exit_detected: bool = False,
    global_outer: bool = False,
) -> dict:
    return {
        "variant": variant,
        "family": family,
        "major_shell_peak_count": peaks,
        "refocus_peak_count": refocus,
        "refocus_peak_ratio_max": 2.0,
        "tail_shell_retention": retention,
        "tail_outer_to_shell_mean": outer,
        "shell_exit_detected": exit_detected,
        "shell_exit_time": None if not exit_detected else 74.0,
        "post_cutoff_shell_decay_rate": -0.03,
        "global_peak_in_outer_window": global_outer,
        "cutoff_phase_cycles": phase,
    }


if __name__ == "__main__":
    unittest.main()
