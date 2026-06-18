"""Tests for focused six-face cubic 3D source controls."""

from __future__ import annotations

import unittest

import numpy as np

from simulation.config import SimulationConfig
from simulation.prototype_3d import Lattice3D, Prototype3DOptions
from simulation.prototype_3d_cubic_focus import (
    CubicFocusControlOptions,
    _variant_plan,
    classify_cubic_focus_control,
)
from simulation.prototype_3d_source_geometry import ALL_FACES


class Prototype3DCubicFocusTests(unittest.TestCase):
    def test_variant_plan_narrows_around_six_face_cubic(self) -> None:
        options = CubicFocusControlOptions(phase_offset=1.25, random_phase_seed=123)
        variants = _variant_plan(SimulationConfig(), Prototype3DOptions(grid_size=15), options)
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual(by_name["six_face_cubic_reference"].boundary_faces, ALL_FACES)
        self.assertEqual(by_name["six_face_cubic_repeat"].boundary_faces, ALL_FACES)
        self.assertEqual(by_name["six_face_cubic_reference"].drive_phase_mode, "cubic")
        self.assertEqual(by_name["cubic_phase_sign_flip"].boundary_cubic_phase_sign, -1.0)
        self.assertEqual(by_name["cubic_phase_offset"].boundary_phase_offset, 1.25)
        self.assertEqual(by_name["cubic_missing_z_max_face"].boundary_faces, ALL_FACES[:-1])
        self.assertEqual(by_name["six_face_uniform_same_coverage"].drive_phase_mode, "uniform")
        self.assertIn("random_phase_seed_123_a", by_name)
        self.assertIn("random_phase_seed_123_b", by_name)
        self.assertEqual(
            by_name["random_phase_seed_123_a"].boundary_face_phase_offsets,
            by_name["random_phase_seed_123_b"].boundary_face_phase_offsets,
        )
        self.assertIn("direct_core_control", by_name)
        self.assertIn("direct_shell_control", by_name)

    def test_face_imbalance_keeps_geometric_source_area_fixed(self) -> None:
        variants = _variant_plan(SimulationConfig(), Prototype3DOptions(grid_size=15), CubicFocusControlOptions())
        reference = next(variant for variant in variants if variant.name == "six_face_cubic_reference")
        imbalance = next(variant for variant in variants if variant.name == "cubic_face_imbalance")

        reference_source = Lattice3D(reference).source
        imbalance_source = Lattice3D(imbalance).source

        self.assertAlmostEqual(reference_source.effective_area, imbalance_source.effective_area)
        self.assertLess(float(np.sum(imbalance_source.weights)), float(np.sum(reference_source.weights)))

    def test_classification_detects_clean_cubic_phase_family(self) -> None:
        rows = [
            _row("six_face_cubic_reference", clean=True, near=2.0),
            _row("six_face_cubic_repeat", clean=True, near=1.95),
            _row("cubic_phase_sign_flip", clean=True, near=1.8),
            _row("cubic_phase_offset", clean=True, near=1.7),
            _row("cubic_missing_z_max_face", clean=False, global_outer=True),
            _row("cubic_face_imbalance", clean=False, global_outer=True),
            _row("six_face_uniform_same_coverage", clean=False, global_outer=True),
            _row("random_phase_seed_31092_a", clean=False, global_outer=True),
            _row("random_phase_seed_31092_b", clean=False, global_outer=True),
            _row("direct_core_control", clean=False, transient=True),
            _row("direct_shell_control", clean=False, transient=True),
        ]

        result = classify_cubic_focus_control(rows, CubicFocusControlOptions())

        self.assertEqual(result["label"], "cubic_phase_family_clean")

    def test_classification_detects_phase_sensitive_exact_cubic(self) -> None:
        rows = [
            _row("six_face_cubic_reference", clean=True, near=2.0),
            _row("six_face_cubic_repeat", clean=True, near=1.95),
            _row("cubic_phase_sign_flip", clean=False, global_outer=True),
            _row("cubic_phase_offset", clean=True, near=1.7),
            _row("cubic_missing_z_max_face", clean=False, global_outer=True),
            _row("cubic_face_imbalance", clean=False, global_outer=True),
            _row("six_face_uniform_same_coverage", clean=False, global_outer=True),
            _row("random_phase_seed_31092_a", clean=False, global_outer=True),
            _row("random_phase_seed_31092_b", clean=False, global_outer=True),
            _row("direct_core_control", clean=False, transient=True),
            _row("direct_shell_control", clean=False, transient=True),
        ]

        result = classify_cubic_focus_control(rows, CubicFocusControlOptions())

        self.assertEqual(result["label"], "exact_cubic_clean_but_phase_sensitive")

    def test_classification_detects_cubic_structure_without_full_symmetry(self) -> None:
        rows = [
            _row("six_face_cubic_reference", clean=True, near=2.0),
            _row("six_face_cubic_repeat", clean=True, near=1.95),
            _row("cubic_phase_sign_flip", clean=True, near=2.5),
            _row("cubic_phase_offset", clean=False, global_outer=True),
            _row("cubic_missing_z_max_face", clean=True, near=1.8),
            _row("cubic_face_imbalance", clean=True, near=1.8),
            _row("six_face_uniform_same_coverage", clean=False, global_outer=True),
            _row("random_phase_seed_31092_a", clean=False, global_outer=True),
            _row("random_phase_seed_31092_b", clean=False, global_outer=True),
            _row("direct_core_control", clean=False, transient=True),
            _row("direct_shell_control", clean=False, transient=True),
        ]

        result = classify_cubic_focus_control(rows, CubicFocusControlOptions())

        self.assertEqual(result["label"], "cubic_phase_structure_not_full_symmetry")
        self.assertEqual(result["best_variant"], "cubic_phase_sign_flip")

    def test_classification_rejects_non_reproducible_reference(self) -> None:
        rows = [
            _row("six_face_cubic_reference", clean=True, near=2.0),
            _row("six_face_cubic_repeat", clean=False, near=0.5),
        ]

        result = classify_cubic_focus_control(rows, CubicFocusControlOptions())

        self.assertEqual(result["label"], "six_face_cubic_not_reproducible")


def _row(
    variant: str,
    *,
    clean: bool,
    near: float = 1.0,
    global_outer: bool = False,
    transient: bool = False,
) -> dict:
    retention = 0.02 if transient else (0.60 if clean else 0.20)
    outer = 2.0 if clean else 8.0
    return {
        "variant": variant,
        "near_shell_peak_fraction_of_work": near,
        "near_shell_tail_retention": retention,
        "outer_to_near_tail_energy_ratio": outer,
        "late_tail_near_shell_peak_radius_range": 2.0 if clean else 7.0,
        "first_meaningful_near_shell_arrival_time": 10.0,
        "physical_duration": 56.0,
        "global_peak_in_outer_window": global_outer,
    }


if __name__ == "__main__":
    unittest.main()
