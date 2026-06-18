"""Tests for tiny 3D fixed-domain grid confirmation controls."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_grid_confirmation import (
    GridConfirmation3DOptions,
    _variant_plan,
    classify_grid_confirmation_control,
)


class Prototype3DGridConfirmationTests(unittest.TestCase):
    def test_variant_plan_keeps_physical_source_width_from_baseline(self) -> None:
        options = GridConfirmation3DOptions()
        variants = _variant_plan(SimulationConfig(), options)
        by_name = {variant.name: variant for variant in variants}

        reference = by_name["sign_flip_stronger_sponge_31"]
        refined = by_name["sign_flip_stronger_sponge_41"]

        self.assertEqual(reference.grid_size, 31)
        self.assertEqual(refined.grid_size, 41)
        self.assertEqual(reference.boundary_cubic_phase_sign, -1.0)
        self.assertEqual(refined.boundary_cubic_phase_sign, -1.0)
        self.assertAlmostEqual(refined.domain_size, reference.domain_size)
        self.assertAlmostEqual(refined.defect_radius, reference.defect_radius)
        self.assertAlmostEqual(refined.sponge_width, reference.sponge_width)
        self.assertAlmostEqual(refined.boundary_source_inner_distance, reference.boundary_source_inner_distance)
        self.assertAlmostEqual(refined.boundary_source_width, reference.boundary_source_width)
        self.assertGreater(reference.dx, refined.dx)
        self.assertIn("original_cubic_stronger_sponge_41", by_name)
        self.assertIn("direct_shell_41_negative_control", by_name)

    def test_variant_plan_can_use_uniform_negative_control(self) -> None:
        options = GridConfirmation3DOptions(negative_control="uniform_phase")
        variants = _variant_plan(SimulationConfig(), options)
        by_name = {variant.name: variant for variant in variants}

        self.assertIn("uniform_phase_41_negative_control", by_name)
        self.assertEqual(by_name["uniform_phase_41_negative_control"].drive_phase_mode, "uniform")

    def test_classification_detects_full_resolution_lift(self) -> None:
        rows = [
            _row("sign_flip_stronger_sponge_31", grid=31, near=4.0, retention=0.65, outer=0.8),
            _row("sign_flip_stronger_sponge_41", grid=41, near=3.0, retention=0.60, outer=1.1),
            _row("original_cubic_stronger_sponge_41", grid=41, near=2.0, retention=0.58, outer=1.6),
            _row("direct_shell_41_negative_control", grid=41, near=50.0, retention=0.001, outer=2.0, family="direct_control"),
        ]

        result = classify_grid_confirmation_control(rows, GridConfirmation3DOptions())

        self.assertEqual(result["label"], "cubic_phase_resolution_lift_confirmed")

    def test_classification_detects_sign_flip_only_lift(self) -> None:
        rows = [
            _row("sign_flip_stronger_sponge_31", grid=31, near=4.0, retention=0.65, outer=0.8),
            _row("sign_flip_stronger_sponge_41", grid=41, near=3.0, retention=0.60, outer=1.1),
            _row("original_cubic_stronger_sponge_41", grid=41, near=0.1, retention=0.10, outer=9.0, global_outer=True),
            _row("direct_shell_41_negative_control", grid=41, near=50.0, retention=0.001, outer=2.0, family="direct_control"),
        ]

        result = classify_grid_confirmation_control(rows, GridConfirmation3DOptions())

        self.assertEqual(result["label"], "sign_flip_resolution_lift_confirmed")

    def test_classification_detects_resolution_sensitivity(self) -> None:
        rows = [
            _row("sign_flip_stronger_sponge_31", grid=31, near=4.0, retention=0.65, outer=0.8),
            _row("sign_flip_stronger_sponge_41", grid=41, near=0.1, retention=0.10, outer=9.0, global_outer=True),
            _row("direct_shell_41_negative_control", grid=41, near=50.0, retention=0.001, outer=2.0, family="direct_control"),
        ]

        result = classify_grid_confirmation_control(rows, GridConfirmation3DOptions())

        self.assertEqual(result["label"], "resolution_sensitive")

    def test_classification_detects_negative_competition(self) -> None:
        rows = [
            _row("sign_flip_stronger_sponge_31", grid=31, near=4.0, retention=0.65, outer=0.8),
            _row("sign_flip_stronger_sponge_41", grid=41, near=3.0, retention=0.60, outer=1.1),
            _row("direct_shell_41_negative_control", grid=41, near=4.0, retention=0.55, outer=1.0, family="direct_control"),
        ]

        result = classify_grid_confirmation_control(rows, GridConfirmation3DOptions())

        self.assertEqual(result["label"], "negative_control_competitive")


def _row(
    variant: str,
    *,
    grid: int,
    near: float,
    retention: float,
    outer: float,
    family: str = "cubic_phase_sign_flip",
    global_outer: bool = False,
) -> dict:
    return {
        "variant": variant,
        "grid_size": grid,
        "drive_location": "shell" if family == "direct_control" else "boundary",
        "grid_confirmation_family": family,
        "near_shell_peak_fraction_of_work": near,
        "near_shell_tail_retention": retention,
        "late_tail_near_shell_peak_radius_median": 5.0,
        "late_tail_near_shell_peak_radius_range": 1.0,
        "outer_to_near_tail_energy_ratio": outer,
        "global_peak_in_outer_window": global_outer,
        "first_meaningful_near_shell_arrival_time": 10.0,
        "stability_warnings": "none",
    }


if __name__ == "__main__":
    unittest.main()
