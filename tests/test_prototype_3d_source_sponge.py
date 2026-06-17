"""Tests for 3D source/sponge separation controls."""

from __future__ import annotations

import unittest

import numpy as np

from simulation.config import SimulationConfig
from simulation.prototype_3d import Lattice3D, Prototype3DOptions
from simulation.prototype_3d_source_sponge import (
    SourceSpongeControlOptions,
    _variant_plan,
    classify_source_sponge_control,
)


class Prototype3DSourceSpongeTests(unittest.TestCase):
    def test_inner_sponge_edge_source_reduces_sponge_overlap(self) -> None:
        variants = _variant_plan(SimulationConfig(), Prototype3DOptions(grid_size=15), SourceSpongeControlOptions())

        reference = Lattice3D(variants[0])
        inner = Lattice3D(variants[1])
        reference_overlap = float(np.mean(reference.sponge_extra[reference.source.mask] > 0.0))
        inner_overlap = float(np.mean(inner.sponge_extra[inner.source.mask] > 0.0))

        self.assertGreater(reference_overlap, inner_overlap)

    def test_excluded_source_cells_are_not_sponge_damped(self) -> None:
        variants = _variant_plan(SimulationConfig(), Prototype3DOptions(grid_size=15), SourceSpongeControlOptions())
        excluded = Lattice3D(variants[2])

        self.assertTrue(np.allclose(excluded.sponge_extra[excluded.source.mask], 0.0))

    def test_classification_detects_clean_near_shell_improvement(self) -> None:
        rows = [
            _row("source_at_outer_boundary_inside_sponge", near=1.0, outer=8.0, global_outer=True),
            _row("source_at_inner_sponge_edge", near=2.0, outer=2.0, global_outer=False),
        ]

        result = classify_source_sponge_control(rows, SourceSpongeControlOptions())

        self.assertEqual(result["label"], "source_sponge_separation_improves_near_shell")


def _row(variant: str, *, near: float, outer: float, global_outer: bool) -> dict:
    return {
        "variant": variant,
        "near_shell_peak_fraction_of_work": near,
        "outer_to_near_tail_energy_ratio": outer,
        "late_tail_near_shell_peak_radius_range": 2.0,
        "near_shell_tail_retention": 0.5,
        "first_meaningful_near_shell_arrival_time": 10.0,
        "physical_duration": 56.0,
        "global_peak_in_outer_window": global_outer,
    }


if __name__ == "__main__":
    unittest.main()
