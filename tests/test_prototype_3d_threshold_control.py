"""Tests for tiny 41^3 3D amplitude and phase threshold controls."""

from __future__ import annotations

import math
import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_threshold_control import (
    ThresholdControl3DOptions,
    _variant_plan,
    classify_threshold_control,
)


class Prototype3DThresholdControlTests(unittest.TestCase):
    def test_variant_plan_targets_sign_flip_41_reference_geometry(self) -> None:
        options = ThresholdControl3DOptions()
        variants = _variant_plan(SimulationConfig(), options)
        by_name = {variant.name: variant for variant in variants}
        reference = by_name["sign_flip_amp_1_0_reference"]
        half_amp = by_name["sign_flip_amp_0_5"]
        phase = by_name["sign_flip_phase_pos_pi_16"]

        self.assertEqual(variants[0].name, "sign_flip_amp_1_0_reference")
        self.assertEqual(reference.grid_size, 41)
        self.assertEqual(reference.boundary_cubic_phase_sign, -1.0)
        self.assertAlmostEqual(reference.boundary_phase_offset, 0.0)
        self.assertAlmostEqual(phase.boundary_phase_offset, math.pi / 16.0)
        self.assertAlmostEqual(half_amp.drive_amplitude, reference.drive_amplitude * 0.5)
        self.assertAlmostEqual(reference.boundary_source_width, 40.0 / 30.0)
        self.assertAlmostEqual(reference.boundary_source_inner_distance, reference.sponge_width)
        self.assertIn("direct_core_41_control", by_name)
        self.assertIn("direct_shell_41_control", by_name)

    def test_variant_plan_can_skip_optional_items(self) -> None:
        options = ThresholdControl3DOptions(
            amplitude_multipliers=(0.5, 0.75, 1.0, 1.25),
            include_direct_core=False,
            include_direct_shell=False,
        )
        variants = _variant_plan(SimulationConfig(), options)
        names = {variant.name for variant in variants}

        self.assertNotIn("sign_flip_amp_1_5", names)
        self.assertNotIn("direct_core_41_control", names)
        self.assertNotIn("direct_shell_41_control", names)

    def test_classification_detects_amplitude_phase_tolerance(self) -> None:
        rows = _base_rows()

        result = classify_threshold_control(rows, ThresholdControl3DOptions())

        self.assertEqual(result["label"], "amplitude_phase_tolerant")

    def test_classification_detects_threshold_below_half_amplitude(self) -> None:
        rows = _base_rows()
        rows[1].update(near_shell_tail_retention=0.10, outer_to_near_tail_energy_ratio=3.0)

        result = classify_threshold_control(rows, ThresholdControl3DOptions())

        self.assertEqual(result["label"], "threshold_below_half_amplitude")

    def test_classification_detects_amplitude_threshold_sensitivity(self) -> None:
        rows = _base_rows()
        rows[2].update(near_shell_tail_retention=0.10, outer_to_near_tail_energy_ratio=3.0)

        result = classify_threshold_control(rows, ThresholdControl3DOptions())

        self.assertEqual(result["label"], "amplitude_threshold_sensitive")

    def test_classification_detects_phase_tuning(self) -> None:
        rows = _base_rows()
        rows[6].update(near_shell_tail_retention=0.10, outer_to_near_tail_energy_ratio=3.0)

        result = classify_threshold_control(rows, ThresholdControl3DOptions())

        self.assertEqual(result["label"], "phase_tuned")

    def test_classification_detects_direct_control_competition(self) -> None:
        rows = _base_rows()
        rows[-1].update(near_shell_tail_retention=0.55, outer_to_near_tail_energy_ratio=1.0)

        result = classify_threshold_control(rows, ThresholdControl3DOptions())

        self.assertEqual(result["label"], "direct_control_competitive")


def _base_rows() -> list[dict]:
    rows = [
        _row("sign_flip_amp_1_0_reference", axis="amplitude", amp=1.0),
        _row("sign_flip_amp_0_5", axis="amplitude", amp=0.5),
        _row("sign_flip_amp_0_75", axis="amplitude", amp=0.75),
        _row("sign_flip_amp_1_25", axis="amplitude", amp=1.25),
        _row("sign_flip_amp_1_5", axis="amplitude", amp=1.5),
        _row("sign_flip_phase_neg_pi_8", axis="phase", phase=-math.pi / 8.0),
        _row("sign_flip_phase_neg_pi_16", axis="phase", phase=-math.pi / 16.0),
        _row("sign_flip_phase_pos_pi_16", axis="phase", phase=math.pi / 16.0),
        _row("sign_flip_phase_pos_pi_8", axis="phase", phase=math.pi / 8.0),
        _row("direct_core_41_control", axis="direct", drive="core", retention=0.001, outer=3.0),
        _row("direct_shell_41_control", axis="direct", drive="shell", retention=0.001, outer=3.0),
    ]
    return rows


def _row(
    variant: str,
    *,
    axis: str,
    amp: float | None = None,
    phase: float = 0.0,
    drive: str = "boundary",
    retention: float = 0.60,
    outer: float = 1.0,
) -> dict:
    return {
        "variant": variant,
        "threshold_axis": axis,
        "threshold_multiplier": amp,
        "drive_location": drive,
        "boundary_phase_offset": phase,
        "near_shell_peak_fraction_of_work": 2.0,
        "near_shell_tail_retention": retention,
        "late_tail_near_shell_peak_radius_median": 5.0,
        "late_tail_near_shell_peak_radius_range": 1.0,
        "outer_to_near_tail_energy_ratio": outer,
        "global_peak_in_outer_window": False,
        "first_meaningful_near_shell_arrival_time": 9.5,
        "stability_warnings": "none",
    }


if __name__ == "__main__":
    unittest.main()
