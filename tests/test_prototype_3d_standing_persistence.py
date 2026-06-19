"""Tests for 3D standing-shell persistence diagnostics."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_standing_persistence import (
    StandingPersistence3DOptions,
    _variant_plan,
    classify_standing_persistence,
)


class Prototype3DStandingPersistenceTests(unittest.TestCase):
    def test_variant_plan_uses_two_clean_cubic_variants(self) -> None:
        options = StandingPersistence3DOptions()
        variants = _variant_plan(SimulationConfig(), options)
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual([variant.name for variant in variants], ["neutral_cubic_sign_flip_reference", "neutral_cubic_phase_offset"])
        for variant in variants:
            self.assertEqual(variant.grid_size, 41)
            self.assertEqual(variant.boundary_faces, ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"))
            self.assertEqual(variant.boundary_source_inner_distance, variant.sponge_width)
            self.assertAlmostEqual(variant.boundary_source_width, 40.0 / 30.0)
            self.assertEqual(variant.drive_phase_mode, "cubic")
            self.assertAlmostEqual(variant.boundary_cubic_phase_sign, -1.0)
            self.assertAlmostEqual(variant.defect_stiffness_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_damping_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_coupling_multiplier, 1.0)
        self.assertAlmostEqual(by_name["neutral_cubic_sign_flip_reference"].boundary_phase_offset, 0.0)
        self.assertAlmostEqual(by_name["neutral_cubic_phase_offset"].boundary_phase_offset, options.phase_offset)

    def test_classification_confirms_when_both_variants_pass(self) -> None:
        rows = [_row("neutral_cubic_sign_flip_reference", pass_metrics=True), _row("neutral_cubic_phase_offset", pass_metrics=True)]

        result = classify_standing_persistence(rows, StandingPersistence3DOptions())

        self.assertEqual(result["label"], "standing_shell_persistence_confirmed")

    def test_classification_marks_mixed_when_only_one_variant_passes(self) -> None:
        rows = [
            _row("neutral_cubic_sign_flip_reference", pass_metrics=True),
            _row("neutral_cubic_phase_offset", pass_metrics=False, phase_stability=0.35),
        ]

        result = classify_standing_persistence(rows, StandingPersistence3DOptions())

        self.assertEqual(result["label"], "standing_persistence_mixed")
        self.assertEqual(result["best_variant"], "neutral_cubic_sign_flip_reference")

    def test_classification_distinguishes_coherent_transport_from_standing(self) -> None:
        rows = [
            _row("neutral_cubic_sign_flip_reference", pass_metrics=False, phase_stability=0.40),
            _row("neutral_cubic_phase_offset", pass_metrics=False, phase_stability=0.32),
        ]

        result = classify_standing_persistence(rows, StandingPersistence3DOptions())

        self.assertEqual(result["label"], "coherent_transport_not_standing")


def _row(variant: str, *, pass_metrics: bool, phase_stability: float | None = None) -> dict:
    if pass_metrics:
        return {
            "variant": variant,
            "standing_score": 0.72,
            "node_antinode_stability": 0.66,
            "frame_similarity_to_mean_mean": 0.70,
            "frame_to_frame_similarity_mean": 0.68,
            "radial_shell_phase_stability": 0.42 if phase_stability is None else phase_stability,
            "shell_energy_spectral_concentration": 0.31,
        }
    return {
        "variant": variant,
        "standing_score": 0.46,
        "node_antinode_stability": 0.38,
        "frame_similarity_to_mean_mean": 0.43,
        "frame_to_frame_similarity_mean": 0.41,
        "radial_shell_phase_stability": 0.10 if phase_stability is None else phase_stability,
        "shell_energy_spectral_concentration": 0.17,
    }


if __name__ == "__main__":
    unittest.main()
