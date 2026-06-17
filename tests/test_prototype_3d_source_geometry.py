"""Tests for 3D source-geometry controls."""

from __future__ import annotations

import unittest

import numpy as np

from simulation.config import SimulationConfig
from simulation.prototype_3d import Lattice3D, Prototype3DOptions
from simulation.prototype_3d_source_geometry import (
    ALL_FACES,
    SourceGeometryControlOptions,
    _random_face_offsets,
    _variant_plan,
    classify_source_geometry_control,
)


class Prototype3DSourceGeometryTests(unittest.TestCase):
    def test_one_face_source_uses_one_boundary_face(self) -> None:
        variants = _variant_plan(SimulationConfig(), Prototype3DOptions(grid_size=15), SourceGeometryControlOptions())
        all_faces = variants[0]
        one_face = next(variant for variant in variants if variant.name == "one_face")

        all_lattice = Lattice3D(all_faces)
        one_lattice = Lattice3D(one_face)

        self.assertEqual(all_lattice.source.boundary_area, 6.0 * all_faces.domain_size**2)
        self.assertEqual(one_lattice.source.boundary_area, one_face.domain_size**2)
        self.assertLess(one_lattice.source.effective_area, all_lattice.source.effective_area)
        self.assertEqual(one_face.boundary_faces, ("x_min",))

    def test_variant_plan_uses_cleaned_stronger_sponge_setup(self) -> None:
        variants = _variant_plan(SimulationConfig(), Prototype3DOptions(grid_size=15), SourceGeometryControlOptions())
        reference = variants[0]
        uniform = next(variant for variant in variants if variant.name == "six_face_uniform")
        reference_lattice = Lattice3D(reference)
        source_overlap = float(np.mean(reference_lattice.sponge_extra[reference_lattice.source.mask] > 0.0))

        self.assertEqual(reference.name, "six_face_rotating_cubic_phase")
        self.assertEqual(reference.boundary_faces, ALL_FACES)
        self.assertEqual(reference.boundary_source_inner_distance, 6.0)
        self.assertEqual(reference.sponge_strength, 0.16)
        self.assertEqual(uniform.boundary_faces, ALL_FACES)
        self.assertAlmostEqual(source_overlap, 0.0)
        for variant in variants:
            self.assertEqual(variant.grid_size, reference.grid_size)
            self.assertEqual(variant.drive_cutoff_time, reference.drive_cutoff_time)
            self.assertEqual(variant.defect_radius, reference.defect_radius)

    def test_random_face_offsets_are_deterministic(self) -> None:
        first = _random_face_offsets(123)
        second = _random_face_offsets(123)

        self.assertEqual(first, second)
        self.assertEqual(set(first), set(ALL_FACES))
        self.assertTrue(all(0.0 <= value <= 2.0 * np.pi for value in first.values()))

    def test_classification_detects_boundary_phase_improvement(self) -> None:
        rows = [
            _row("six_face_uniform", near=2.0, retention=0.60, outer=3.0, role="baseline_boundary"),
            _row("six_face_rotating_cubic_phase", near=2.6, retention=0.62, outer=2.5, role="coherent_boundary"),
            _row("random_phase_faces", near=1.0, retention=0.40, outer=3.0, role="random_phase_control"),
            _row("direct_core_control", near=0.5, retention=0.30, outer=3.0, role="direct_control"),
            _row("direct_shell_control", near=0.4, retention=0.30, outer=3.0, role="direct_control"),
        ]

        result = classify_source_geometry_control(rows, SourceGeometryControlOptions())

        self.assertEqual(result["label"], "boundary_phase_geometry_strengthens_near_shell")

    def test_classification_flags_direct_competition(self) -> None:
        rows = [
            _row("six_face_uniform", near=2.0, retention=0.60, outer=3.0, role="baseline_boundary"),
            _row("six_face_rotating_cubic_phase", near=2.6, retention=0.62, outer=2.5, role="coherent_boundary"),
            _row("direct_shell_control", near=2.7, retention=0.63, outer=2.4, role="direct_control"),
        ]

        result = classify_source_geometry_control(rows, SourceGeometryControlOptions())

        self.assertEqual(result["label"], "direct_local_forcing_competitive")

    def test_outer_contaminated_uniform_baseline_uses_absolute_outer_limit(self) -> None:
        rows = [
            _row("six_face_uniform", near=2.0, retention=0.60, outer=1.0, role="baseline_boundary", global_outer=True),
            _row("six_face_rotating_cubic_phase", near=2.1, retention=0.62, outer=2.9, role="coherent_boundary"),
        ]

        result = classify_source_geometry_control(rows, SourceGeometryControlOptions())

        self.assertEqual(result["label"], "boundary_source_geometry_preserves_near_shell")


def _row(
    variant: str,
    *,
    near: float,
    retention: float,
    outer: float,
    role: str,
    global_outer: bool = False,
) -> dict:
    return {
        "variant": variant,
        "source_geometry_role": role,
        "near_shell_peak_fraction_of_work": near,
        "near_shell_tail_retention": retention,
        "outer_to_near_tail_energy_ratio": outer,
        "late_tail_near_shell_peak_radius_range": 0.0,
        "first_meaningful_near_shell_arrival_time": 10.0,
        "physical_duration": 56.0,
        "global_peak_in_outer_window": global_outer,
    }


if __name__ == "__main__":
    unittest.main()
