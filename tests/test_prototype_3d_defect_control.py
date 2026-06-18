"""Tests for tiny 41^3 3D defect-dependence controls."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_defect_control import (
    DefectControl3DOptions,
    _variant_plan,
    classify_defect_control,
)


class Prototype3DDefectControlTests(unittest.TestCase):
    def test_variant_plan_neutralizes_and_resizes_defect_only(self) -> None:
        options = DefectControl3DOptions()
        variants = _variant_plan(SimulationConfig(), options)
        by_name = {variant.name: variant for variant in variants}
        reference = by_name["current_defect_reference"]
        neutral = by_name["no_defect_neutral_lattice"]

        self.assertEqual(reference.grid_size, 41)
        self.assertEqual(reference.boundary_cubic_phase_sign, -1.0)
        self.assertAlmostEqual(reference.boundary_source_inner_distance, reference.sponge_width)
        self.assertAlmostEqual(reference.boundary_source_width, 40.0 / 30.0)
        self.assertAlmostEqual(neutral.defect_radius, reference.defect_radius)
        self.assertAlmostEqual(neutral.defect_stiffness_multiplier, 1.0)
        self.assertAlmostEqual(neutral.defect_damping_multiplier, 1.0)
        self.assertAlmostEqual(neutral.defect_coupling_multiplier, 1.0)
        self.assertAlmostEqual(by_name["defect_stiffness_multiplier_1_0"].defect_stiffness_multiplier, 1.0)
        self.assertAlmostEqual(by_name["defect_coupling_multiplier_1_0"].defect_coupling_multiplier, 1.0)
        self.assertAlmostEqual(by_name["defect_damping_multiplier_1_0"].defect_damping_multiplier, 1.0)
        self.assertAlmostEqual(by_name["smaller_defect_radius"].defect_radius, reference.defect_radius * 0.75)
        self.assertAlmostEqual(by_name["larger_defect_radius"].defect_radius, reference.defect_radius * 1.25)

    def test_classification_detects_defect_dependence(self) -> None:
        rows = _base_rows()
        rows[1].update(fixed_near_shell_tail_retention=0.10, fixed_outer_to_near_tail_energy_ratio=3.0)

        result = classify_defect_control(rows, DefectControl3DOptions())

        self.assertEqual(result["label"], "defect_dependent_retained_shell_mode")

    def test_classification_detects_defect_independence(self) -> None:
        rows = _base_rows()

        result = classify_defect_control(rows, DefectControl3DOptions())

        self.assertEqual(result["label"], "defect_independent_boundary_standing_wave")

    def test_classification_detects_property_sensitivity(self) -> None:
        rows = _base_rows()
        rows[2].update(fixed_near_shell_tail_retention=0.10, fixed_outer_to_near_tail_energy_ratio=3.0)

        result = classify_defect_control(rows, DefectControl3DOptions())

        self.assertEqual(result["label"], "defect_property_sensitive")

    def test_classification_detects_radius_sensitivity(self) -> None:
        rows = _base_rows()
        rows[-1].update(fixed_late_tail_near_shell_peak_radius_median=7.0)

        result = classify_defect_control(rows, DefectControl3DOptions())

        self.assertEqual(result["label"], "defect_radius_sensitive")

    def test_classification_detects_reference_failure(self) -> None:
        rows = _base_rows()
        rows[0].update(fixed_near_shell_tail_retention=0.10, fixed_outer_to_near_tail_energy_ratio=3.0)

        result = classify_defect_control(rows, DefectControl3DOptions())

        self.assertEqual(result["label"], "reference_not_reproduced")


def _base_rows() -> list[dict]:
    return [
        _row("current_defect_reference"),
        _row("no_defect_neutral_lattice"),
        _row("defect_stiffness_multiplier_1_0"),
        _row("defect_coupling_multiplier_1_0"),
        _row("defect_damping_multiplier_1_0"),
        _row("smaller_defect_radius"),
        _row("larger_defect_radius"),
    ]


def _row(variant: str) -> dict:
    return {
        "variant": variant,
        "fixed_near_shell_peak_fraction_of_work": 2.0e-7,
        "fixed_near_shell_tail_retention": 0.60,
        "fixed_late_tail_near_shell_peak_radius_median": 5.0,
        "fixed_late_tail_near_shell_peak_radius_range": 1.0,
        "fixed_outer_to_near_tail_energy_ratio": 1.0,
        "fixed_global_peak_in_outer_window": False,
        "fixed_first_meaningful_near_shell_arrival_time": 9.5,
        "stability_warnings": "none",
    }


if __name__ == "__main__":
    unittest.main()
