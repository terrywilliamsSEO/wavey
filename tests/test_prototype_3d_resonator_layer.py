"""Tests for the passive 3D resonator-layer control."""

from __future__ import annotations

import math
import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d import Lattice3D
from simulation.prototype_3d_resonator_layer import (
    ResonatorLayer3DOptions,
    _variant_plan,
    classify_resonator_layer_control,
    phase_lock_cluster_width,
)


class Prototype3DResonatorLayerTests(unittest.TestCase):
    def test_variant_plan_keeps_fixed_passive_scope(self) -> None:
        base = SimulationConfig()
        options = ResonatorLayer3DOptions()

        variants = _variant_plan(base, options)
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 49)
        self.assertEqual(
            names[:7],
            [
                "no_resonator_reference_cutoff_17p920",
                "no_resonator_reference_cutoff_17p925",
                "no_resonator_reference_cutoff_17p930",
                "no_resonator_reference_cutoff_17p935",
                "no_resonator_reference_cutoff_17p940",
                "no_resonator_reference_cutoff_17p945",
                "no_resonator_reference_cutoff_17p950",
            ],
        )
        self.assertIn("zero_coupling_control_cutoff_17p940", names)
        self.assertIn("high_damping_control_cutoff_17p940", names)
        self.assertEqual([variant.drive_cutoff_time for variant in variants[:7]], list(options.cutoffs))
        self.assertTrue(all(variant.grid_size == 41 for variant in variants))
        self.assertTrue(all(variant.drive_frequency == 0.92 for variant in variants))
        self.assertTrue(all(variant.drive_phase_mode == "cubic" for variant in variants))
        self.assertTrue(all(variant.boundary_cubic_phase_sign == -1.0 for variant in variants))
        self.assertTrue(all(variant.defect_stiffness_multiplier == 1.0 for variant in variants))
        self.assertTrue(all(variant.defect_damping_multiplier == 1.0 for variant in variants))
        self.assertTrue(all(variant.defect_coupling_multiplier == 1.0 for variant in variants))
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(variant.second_pulse_duration == 0.0 for variant in variants))

    def test_resonator_frequency_tuning_uses_drive_frequency(self) -> None:
        base = SimulationConfig()
        options = ResonatorLayer3DOptions()

        tuned = next(
            variant
            for variant in _variant_plan(base, options)
            if variant.name == "boundary_inner_edge_resonator_layer_tuned_cutoff_17p940"
        )

        self.assertAlmostEqual(tuned.resonator_k1, (2.0 * math.pi * 0.92) ** 2)
        self.assertAlmostEqual(tuned.resonator_coupling, options.weak_coupling)
        self.assertAlmostEqual(tuned.resonator_damping, options.low_damping)
        self.assertTrue(tuned.resonator_enabled)

    def test_zero_coupling_control_stays_passive(self) -> None:
        base = SimulationConfig()
        config = next(
            variant
            for variant in _variant_plan(base, ResonatorLayer3DOptions(cutoffs=(17.94,)))
            if variant.name == "zero_coupling_control_cutoff_17p940"
        )
        lattice = Lattice3D(config)

        for step in range(5):
            lattice.step(step * config.dt, config.dt)

        self.assertEqual(lattice.resonator_energy(), 0.0)
        self.assertEqual(lattice.resonator_coupling_energy(), 0.0)
        self.assertEqual(lattice.last_resonator_coupling_power_lattice, 0.0)
        self.assertEqual(lattice.last_resonator_coupling_power_resonator, 0.0)

    def test_cluster_width_counts_decay_matched_strict_rows(self) -> None:
        rows = [
            _summary("ref_a", "no_resonator_reference", 17.93, decay=-0.03),
            _summary("ref_b", "no_resonator_reference", 17.94, decay=-0.03),
            _summary("ref_c", "no_resonator_reference", 17.95, decay=-0.03),
            _summary("res_a", "boundary_inner_edge_resonator_layer_tuned", 17.93, decay=-0.029),
            _summary("res_b", "boundary_inner_edge_resonator_layer_tuned", 17.94, decay=-0.028),
            _summary("res_c", "boundary_inner_edge_resonator_layer_tuned", 17.95, decay=-0.027),
        ]
        robust = [
            _robust("ref_a", 17.93, score=9000.0),
            _robust("ref_b", 17.94, score=9001.0),
            _robust("ref_c", 17.95, score=8000.0, min_major=8, min_refocus=7),
            _robust("res_a", 17.93, score=9002.0),
            _robust("res_b", 17.94, score=9003.0),
            _robust("res_c", 17.95, score=9004.0),
        ]

        width = phase_lock_cluster_width(rows, robust, ResonatorLayer3DOptions())
        classification = classify_resonator_layer_control(rows, robust, ResonatorLayer3DOptions())

        self.assertEqual(width["reference_strict_decay_matched_count"], 2)
        tuned = next(group for group in width["groups"] if group["resonator_variant"] == "boundary_inner_edge_resonator_layer_tuned")
        self.assertEqual(tuned["strict_decay_matched_count"], 3)
        self.assertEqual(classification["label"], "resonator_widens_phase_lock_cluster")


def _summary(variant: str, resonator: str, cutoff: float, *, decay: float) -> dict:
    return {
        "variant": variant,
        "resonator_variant": resonator,
        "drive_cutoff_time": cutoff,
        "post_cutoff_shell_decay_rate": decay,
        "tail_shell_retention": 0.32,
        "tail_outer_to_shell_mean": 0.65,
        "shell_exit_detected": False,
        "global_peak_in_outer_window": False,
        "no_post_cutoff_external_work": True,
        "energy_accounting_passed": True,
    }


def _robust(variant: str, cutoff: float, *, score: float, min_major: int = 9, min_refocus: int = 8) -> dict:
    return {
        "variant": variant,
        "drive_cutoff_time": cutoff,
        "conservative_score": score,
        "default_threshold_score": score,
        "min_major_peaks_across_thresholds": min_major,
        "median_major_peaks_across_thresholds": float(min_major),
        "min_refocus_peaks_across_thresholds": min_refocus,
        "median_refocus_peaks_across_thresholds": float(min_refocus),
        "default_major_peaks": 11,
        "default_refocus_peaks": 10,
        "retention_median": 0.32,
        "outer_shell_median": 0.65,
        "decay_median": -0.03,
        "no_exit_across_all_thresholds": True,
        "global_outer_false_across_all_thresholds": True,
    }


if __name__ == "__main__":
    unittest.main()
