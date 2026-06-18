"""Tests for 3D boundary-interference diagnostics."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_interference_diagnostics import (
    InterferenceDiagnostics3DOptions,
    _variant_plan,
    classify_interference_diagnostics,
)


class Prototype3DInterferenceDiagnosticsTests(unittest.TestCase):
    def test_variant_plan_uses_neutral_lattice_and_phase_controls(self) -> None:
        options = InterferenceDiagnostics3DOptions()
        variants = _variant_plan(SimulationConfig(), options)
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual(variants[0].name, "neutral_cubic_sign_flip_reference")
        self.assertIn("neutral_uniform_same_coverage", by_name)
        self.assertIn("neutral_cubic_phase_offset", by_name)
        self.assertIn("neutral_random_phase_seed_31092", by_name)
        self.assertIn("neutral_random_phase_seed_41092", by_name)
        for variant in variants:
            self.assertEqual(variant.grid_size, 41)
            self.assertEqual(variant.boundary_faces, ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"))
            self.assertEqual(variant.boundary_source_inner_distance, variant.sponge_width)
            self.assertAlmostEqual(variant.boundary_source_width, 40.0 / 30.0)
            self.assertAlmostEqual(variant.defect_stiffness_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_damping_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_coupling_multiplier, 1.0)
        self.assertEqual(by_name["neutral_cubic_sign_flip_reference"].drive_phase_mode, "cubic")
        self.assertAlmostEqual(by_name["neutral_cubic_sign_flip_reference"].boundary_cubic_phase_sign, -1.0)
        self.assertEqual(by_name["neutral_random_phase_seed_31092"].drive_phase_mode, "random")
        self.assertEqual(by_name["neutral_random_phase_seed_31092"].boundary_random_phase_seed, 31092)

    def test_classification_supports_interference_when_random_controls_fail(self) -> None:
        rows = [
            _row("neutral_cubic_sign_flip_reference", clean=True, coherence=0.50, standing=0.80),
            _row("neutral_uniform_same_coverage", clean=False, coherence=0.20, standing=0.40, global_outer=True),
            _row("neutral_random_phase_seed_31092", clean=False, coherence=0.20, standing=0.40, global_outer=True),
            _row("neutral_random_phase_seed_41092", clean=False, coherence=0.18, standing=0.35, retention=0.20),
        ]

        result = classify_interference_diagnostics(rows, InterferenceDiagnostics3DOptions())

        self.assertEqual(result["label"], "structured_boundary_interference_supported")

    def test_classification_refuses_when_random_phase_survives(self) -> None:
        rows = [
            _row("neutral_cubic_sign_flip_reference", clean=True, coherence=0.50, standing=0.80),
            _row("neutral_random_phase_seed_31092", clean=True, coherence=0.45, standing=0.75),
        ]

        result = classify_interference_diagnostics(rows, InterferenceDiagnostics3DOptions())

        self.assertEqual(result["label"], "phase_randomization_survives")

    def test_classification_keeps_standing_persistence_caveat(self) -> None:
        rows = [
            _row("neutral_cubic_sign_flip_reference", clean=True, coherence=0.50, standing=0.52),
            _row("neutral_random_phase_seed_31092", clean=False, coherence=0.05, standing=0.40, global_outer=True),
        ]

        result = classify_interference_diagnostics(rows, InterferenceDiagnostics3DOptions())

        self.assertEqual(result["label"], "interference_supported_standing_weak")


def _row(
    variant: str,
    *,
    clean: bool,
    coherence: float,
    standing: float,
    global_outer: bool = False,
    retention: float | None = None,
) -> dict:
    value = 0.60 if clean else 0.20
    return {
        "variant": variant,
        "near_shell_tail_retention": value if retention is None else retention,
        "outer_to_near_tail_energy_ratio": 1.2 if clean else 3.0,
        "global_peak_in_outer_window": global_outer,
        "tail_phase_coherence_mean": coherence,
        "standing_shell_persistence": standing,
        "near_shell_peak_fraction_of_work": 2.0e-7,
    }


if __name__ == "__main__":
    unittest.main()
