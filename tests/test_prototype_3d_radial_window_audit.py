"""Tests for 3D radial-window neutral-lattice audits."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_radial_window_audit import (
    RadialWindowAudit3DOptions,
    _variant_plan,
    classify_radial_window_audit,
)


class Prototype3DRadialWindowAuditTests(unittest.TestCase):
    def test_variant_plan_runs_current_and_neutral_lattices(self) -> None:
        options = RadialWindowAudit3DOptions()
        variants = _variant_plan(SimulationConfig(), options)
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual([variant.name for variant in variants], ["current_defect_reference", "neutral_lattice_reference"])
        self.assertEqual(by_name["current_defect_reference"].grid_size, 41)
        self.assertEqual(by_name["current_defect_reference"].boundary_cubic_phase_sign, -1.0)
        self.assertAlmostEqual(by_name["current_defect_reference"].boundary_source_width, 40.0 / 30.0)
        self.assertAlmostEqual(by_name["neutral_lattice_reference"].defect_stiffness_multiplier, 1.0)
        self.assertAlmostEqual(by_name["neutral_lattice_reference"].defect_damping_multiplier, 1.0)
        self.assertAlmostEqual(by_name["neutral_lattice_reference"].defect_coupling_multiplier, 1.0)

    def test_classification_detects_neutral_reproduction(self) -> None:
        rows = [
            _row(2.5, lift_retention=1.1, lift_peak=1.1),
            _row(5.0, lift_retention=1.0, lift_peak=1.0),
            _row(8.0, lift_retention=0.9, lift_peak=1.2),
        ]

        result = classify_radial_window_audit(rows, RadialWindowAudit3DOptions())

        self.assertEqual(result["label"], "neutral_lattice_reproduces_shell_tail")

    def test_classification_detects_defect_lift(self) -> None:
        rows = [
            _row(2.5, lift_retention=1.1, lift_peak=1.1),
            _row(5.0, lift_retention=1.0, lift_peak=1.0),
            _row(8.0, lift_retention=1.7, lift_peak=1.6),
        ]

        result = classify_radial_window_audit(rows, RadialWindowAudit3DOptions())

        self.assertEqual(result["label"], "defect_lift_detected")

    def test_classification_keeps_mixed_results_conservative(self) -> None:
        rows = [
            _row(2.5, lift_retention=1.1, lift_peak=1.1),
            _row(5.0, lift_retention=0.4, lift_peak=0.4),
        ]

        result = classify_radial_window_audit(rows, RadialWindowAudit3DOptions())

        self.assertEqual(result["label"], "cubic_boundary_shell_tail_not_defect_dependent_yet")


def _row(radius: float, *, lift_retention: float, lift_peak: float) -> dict:
    return {
        "window_radius": radius,
        "defect_retention": 0.60 * lift_retention,
        "neutral_retention": 0.60,
        "defect_lift_retention": lift_retention,
        "defect_peak_work": 2.0e-7 * lift_peak,
        "neutral_peak_work": 2.0e-7,
        "defect_lift_peak_work": lift_peak,
        "defect_window_clean": True,
        "neutral_window_clean": True,
        "arrival_time_shift": 0.2,
        "radius_median_shift": 0.0,
    }


if __name__ == "__main__":
    unittest.main()
