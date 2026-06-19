"""Tests for 3D refocusing-engineering controls."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_refocusing_engineering import (
    RefocusingEngineering3DOptions,
    _variant_plan,
    classify_refocusing_engineering,
)


class Prototype3DRefocusingEngineeringTests(unittest.TestCase):
    def test_variant_plan_is_tiny_one_axis_control(self) -> None:
        options = RefocusingEngineering3DOptions(include_chirp=True)
        variants = _variant_plan(SimulationConfig(), options)
        names = [variant.name for variant in variants]
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual(
            names,
            [
                "sign_flip_reference",
                "phase_offset_reference",
                "phase_offset_minus_delta",
                "phase_offset_plus_delta",
                "cutoff_short",
                "cutoff_long",
                "frequency_low",
                "frequency_high",
                "chirp_low_to_high",
            ],
        )
        for variant in variants:
            self.assertEqual(variant.grid_size, 41)
            self.assertEqual(variant.drive_phase_mode, "cubic")
            self.assertAlmostEqual(variant.boundary_cubic_phase_sign, -1.0)
            self.assertEqual(variant.boundary_source_inner_distance, variant.sponge_width)
            self.assertAlmostEqual(variant.defect_stiffness_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_damping_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_coupling_multiplier, 1.0)
        self.assertAlmostEqual(by_name["phase_offset_reference"].boundary_phase_offset, options.phase_offset)
        self.assertAlmostEqual(by_name["phase_offset_minus_delta"].boundary_phase_offset, options.phase_offset - options.phase_delta)
        self.assertAlmostEqual(by_name["cutoff_short"].drive_cutoff_time, 14.0)
        self.assertAlmostEqual(by_name["cutoff_long"].drive_cutoff_time, 18.0)
        self.assertEqual(by_name["chirp_low_to_high"].drive_mode, "chirp")

    def test_classification_detects_clean_improvement(self) -> None:
        rows = [
            _row("phase_offset_reference", refocus=5, ratio=2.0, exit_time=76.0, retention=0.13),
            _row("phase_offset_plus_delta", refocus=6, ratio=2.1, exit_time=77.0, retention=0.12),
        ]

        result = classify_refocusing_engineering(rows, RefocusingEngineering3DOptions())

        self.assertEqual(result["label"], "refocusing_improved")
        self.assertEqual(result["best_variant"], "phase_offset_plus_delta")

    def test_classification_allows_tolerant_without_improvement(self) -> None:
        rows = [
            _row("phase_offset_reference", refocus=5, ratio=2.0, exit_time=76.0, retention=0.13),
            _row("phase_offset_plus_delta", refocus=5, ratio=2.02, exit_time=76.5, retention=0.12),
        ]

        result = classify_refocusing_engineering(rows, RefocusingEngineering3DOptions())

        self.assertEqual(result["label"], "refocusing_tolerant_no_improvement")


def _row(
    variant: str,
    *,
    refocus: int,
    ratio: float,
    exit_time: float,
    retention: float,
    outer_shell: float = 1.5,
    global_outer: bool = False,
    decay: float = -0.05,
) -> dict:
    return {
        "variant": variant,
        "refocus_peak_count": refocus,
        "major_shell_peak_count": refocus + 1,
        "refocus_peak_ratio_max": ratio,
        "shell_exit_time": exit_time,
        "tail_shell_retention": retention,
        "tail_outer_to_shell_mean": outer_shell,
        "global_peak_in_outer_window": global_outer,
        "post_cutoff_shell_decay_rate": decay,
    }


if __name__ == "__main__":
    unittest.main()
