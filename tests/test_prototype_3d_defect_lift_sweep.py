"""Tests for tiny 41^3 3D defect-lift sweeps."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_defect_lift_sweep import (
    DefectLiftSweep3DOptions,
    _variant_plan,
    classify_defect_lift_sweep,
)


class Prototype3DDefectLiftSweepTests(unittest.TestCase):
    def test_variant_plan_keeps_boundary_source_fixed_and_varies_defects(self) -> None:
        options = DefectLiftSweep3DOptions()
        variants = _variant_plan(SimulationConfig(), options)
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual(variants[0].name, "neutral_lattice_baseline")
        self.assertIn("current_defect_reference", by_name)
        self.assertIn("stiff_inclusion_k2_0", by_name)
        self.assertIn("very_soft_cavity_k0_15", by_name)
        self.assertIn("thin_shell_wall", by_name)
        self.assertIn("nonlinear_defect_only", by_name)

        reference = by_name["current_defect_reference"]
        for variant in variants:
            self.assertEqual(variant.grid_size, 41)
            self.assertEqual(variant.drive_location, "boundary")
            self.assertEqual(variant.drive_phase_mode, "cubic")
            self.assertEqual(variant.boundary_cubic_phase_sign, -1.0)
            self.assertAlmostEqual(variant.boundary_source_inner_distance, variant.sponge_width)
            self.assertAlmostEqual(variant.boundary_source_width, 40.0 / 30.0)
            self.assertEqual(variant.boundary_faces, reference.boundary_faces)

        self.assertAlmostEqual(by_name["neutral_lattice_baseline"].defect_stiffness_multiplier, 1.0)
        self.assertAlmostEqual(by_name["neutral_lattice_baseline"].defect_damping_multiplier, 1.0)
        self.assertAlmostEqual(by_name["neutral_lattice_baseline"].defect_coupling_multiplier, 1.0)
        self.assertAlmostEqual(by_name["small_radius_r0_5"].defect_radius, reference.defect_radius * 0.5)
        self.assertAlmostEqual(by_name["large_radius_r1_5"].defect_radius, reference.defect_radius * 1.5)
        self.assertIsNotNone(by_name["thin_shell_wall"].defect_inner_radius)
        self.assertAlmostEqual(by_name["nonlinear_defect_only"].nonlinear_strength, 0.0)
        self.assertGreater(by_name["nonlinear_defect_only"].defect_nonlinear_strength or 0.0, 0.0)

    def test_classification_requires_all_strict_success_conditions(self) -> None:
        rows = [
            _comparison_row("soft", lift_retention=1.8, lift_peak=1.7, profile_corr=0.94),
            _comparison_row("dirty", lift_retention=2.1, lift_peak=2.0, profile_corr=0.90, global_outer=True),
            _comparison_row("same_profile", lift_retention=2.0, lift_peak=1.9, profile_corr=0.99),
        ]
        rows[0]["strict_success"] = True

        result = classify_defect_lift_sweep(rows, DefectLiftSweep3DOptions())

        self.assertEqual(result["label"], "defect_lift_found")
        self.assertEqual(result["best_variant"], "soft")

    def test_classification_pivots_when_no_variant_beats_neutral(self) -> None:
        rows = [
            _comparison_row("soft", lift_retention=1.4, lift_peak=1.7, profile_corr=0.90),
            _comparison_row("dirty", lift_retention=2.0, lift_peak=2.0, profile_corr=0.90, global_outer=True),
            _comparison_row("same_profile", lift_retention=2.0, lift_peak=2.0, profile_corr=0.99),
        ]

        result = classify_defect_lift_sweep(rows, DefectLiftSweep3DOptions())

        self.assertEqual(result["label"], "no_defect_lift_found")


def _comparison_row(
    variant: str,
    *,
    lift_retention: float,
    lift_peak: float,
    profile_corr: float,
    global_outer: bool = False,
) -> dict:
    return {
        "variant": variant,
        "window_radius": 5.0,
        "defect_retention": 0.50 * lift_retention,
        "neutral_retention": 0.50,
        "defect_lift_retention": lift_retention,
        "defect_peak_work": 2.0e-7 * lift_peak,
        "neutral_peak_work": 2.0e-7,
        "defect_lift_peak_work": lift_peak,
        "defect_window_clean": not global_outer,
        "defect_global_outer": global_outer,
        "radial_profile_correlation": profile_corr,
        "window_radial_profile_correlation": profile_corr,
        "strict_success": False,
    }


if __name__ == "__main__":
    unittest.main()
