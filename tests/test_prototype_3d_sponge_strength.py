"""Tests for 3D sponge-strength controls."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d import Prototype3DOptions
from simulation.prototype_3d_sponge_strength import (
    SpongeStrengthControlOptions,
    _variant_plan,
    classify_sponge_strength_control,
)


class Prototype3DSpongeStrengthTests(unittest.TestCase):
    def test_wider_sponge_keeps_source_location_fixed(self) -> None:
        variants = _variant_plan(SimulationConfig(), Prototype3DOptions(grid_size=15), SpongeStrengthControlOptions())
        distances = {variant.name: variant.boundary_source_inner_distance for variant in variants}
        widths = {variant.name: variant.sponge_width for variant in variants}

        self.assertEqual(len(set(distances.values())), 1)
        self.assertGreater(widths["wider_sponge_inner_edge"], widths["baseline_sponge_inner_edge"])
        self.assertGreater(widths["stronger_wider_sponge_inner_edge"], widths["stronger_sponge_inner_edge"])

    def test_variant_plan_changes_only_sponge_settings(self) -> None:
        variants = _variant_plan(SimulationConfig(), Prototype3DOptions(grid_size=15), SpongeStrengthControlOptions())
        baseline = variants[0]

        for variant in variants[1:]:
            self.assertEqual(variant.grid_size, baseline.grid_size)
            self.assertEqual(variant.drive_frequency, baseline.drive_frequency)
            self.assertEqual(variant.drive_cutoff_time, baseline.drive_cutoff_time)
            self.assertEqual(variant.defect_radius, baseline.defect_radius)
            self.assertEqual(variant.boundary_source_width, baseline.boundary_source_width)

    def test_classification_detects_outer_contamination_suppression(self) -> None:
        rows = [
            _row("baseline_sponge_inner_edge", near=2.0, outer=4.0, retention=0.65, global_outer=False),
            _row("stronger_sponge_inner_edge", near=1.8, outer=2.0, retention=0.58, global_outer=False),
        ]

        result = classify_sponge_strength_control(rows, SpongeStrengthControlOptions())

        self.assertEqual(result["label"], "sponge_strength_suppresses_outer_contamination")

    def test_classification_rejects_unretained_transient(self) -> None:
        rows = [
            _row("baseline_sponge_inner_edge", near=2.0, outer=4.0, retention=0.65, global_outer=False),
            _row("stronger_sponge_inner_edge", near=4.0, outer=1.0, retention=0.05, global_outer=False),
        ]

        result = classify_sponge_strength_control(rows, SpongeStrengthControlOptions())

        self.assertEqual(result["label"], "sponge_sensitive")


def _row(
    variant: str,
    *,
    near: float,
    outer: float,
    retention: float,
    global_outer: bool,
) -> dict:
    return {
        "variant": variant,
        "near_shell_peak_fraction_of_work": near,
        "outer_to_near_tail_energy_ratio": outer,
        "late_tail_near_shell_peak_radius_median": 6.5,
        "late_tail_near_shell_peak_radius_range": 2.0,
        "near_shell_tail_retention": retention,
        "first_meaningful_near_shell_arrival_time": 10.0,
        "physical_duration": 56.0,
        "global_peak_in_outer_window": global_outer,
    }


if __name__ == "__main__":
    unittest.main()
