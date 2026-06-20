"""Tests for the release-phase resolution-lift checkpoint."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_release_phase_resolution_lift import (
    RESOLUTION_LIFT_PHASES,
    ReleasePhaseResolutionLiftOptions,
    _cutoff_from_phase,
    _gate_rows,
    _variant_plan,
    classify_release_phase_resolution_lift,
)


class Prototype3DReleasePhaseResolutionLiftTests(unittest.TestCase):
    def test_variant_plan_is_single_lift_plus_two_controls(self) -> None:
        base = SimulationConfig()
        options = ReleasePhaseResolutionLiftOptions()

        variants = _variant_plan(base, options)

        self.assertEqual(len(variants), 3)
        self.assertEqual([getattr(variant, "_prediction_role") for variant in variants], list(options.prediction_roles))
        self.assertEqual([getattr(variant, "_target_release_phase") for variant in variants], list(RESOLUTION_LIFT_PHASES))
        self.assertTrue(all(variant.grid_size == 51 for variant in variants))
        self.assertTrue(all(variant.dt == base.dt * 0.25 for variant in variants))
        self.assertTrue(all(variant.drive_frequency == 0.92 for variant in variants))
        self.assertTrue(all(variant.drive_phase_mode == "cubic" for variant in variants))
        self.assertTrue(all(variant.boundary_cubic_phase_sign == -1.0 for variant in variants))
        self.assertTrue(all(variant.boundary_phase_offset == 0.0 for variant in variants))
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))

    def test_cutoffs_are_recomputed_from_target_phase(self) -> None:
        options = ReleasePhaseResolutionLiftOptions()

        cutoffs = [_cutoff_from_phase(phase, options) for phase in RESOLUTION_LIFT_PHASES]

        self.assertAlmostEqual(cutoffs[0], 17.9425)
        self.assertAlmostEqual(cutoffs[1], 17.9375)
        self.assertAlmostEqual(cutoffs[2], 17.915)

    def test_classifies_supported_when_candidate_passes_and_controls_do_not(self) -> None:
        rows = [
            _row("candidate", "candidate", 9, 8, 9850.0, tail=0.00123, timing=0.84, spectral=0.74),
            _row("low", "low_side_phase_control", 8, 7, 8750.0, tail=0.00124, timing=0.57, spectral=0.75),
            _row("weak", "weak_negative_phase_control", 8, 7, 8740.0, tail=0.00125, timing=0.57, spectral=0.75),
        ]
        gates = _gate_rows(rows, ReleasePhaseResolutionLiftOptions())

        classification = classify_release_phase_resolution_lift(rows, gates)

        self.assertEqual(classification["label"], "release_phase_resolution_lift_supported")

    def test_classifies_controls_competitive_when_control_matches_count(self) -> None:
        rows = [
            _row("candidate", "candidate", 9, 8, 9850.0, tail=0.00123, timing=0.84, spectral=0.74),
            _row("control", "low_side_phase_control", 9, 8, 9800.0, tail=0.00124, timing=0.84, spectral=0.74),
        ]
        gates = _gate_rows(rows, ReleasePhaseResolutionLiftOptions())

        classification = classify_release_phase_resolution_lift(rows, gates)

        self.assertEqual(classification["label"], "release_phase_resolution_lift_controls_competitive")

    def test_classifies_failed_when_candidate_loses_strict_floor(self) -> None:
        rows = [
            _row("candidate", "candidate", 8, 7, 8750.0, tail=0.00123, timing=0.84, spectral=0.74),
            _row("control", "low_side_phase_control", 8, 7, 8700.0, tail=0.00124, timing=0.57, spectral=0.75),
        ]
        gates = _gate_rows(rows, ReleasePhaseResolutionLiftOptions())

        classification = classify_release_phase_resolution_lift(rows, gates)

        self.assertEqual(classification["label"], "release_phase_resolution_lift_failed")


def _row(
    variant: str,
    role: str,
    major: int,
    refocus: int,
    score: float,
    *,
    tail: float,
    timing: float,
    spectral: float,
) -> dict:
    return {
        "variant": variant,
        "prediction_role": role,
        "target_release_phase": 0.5071,
        "dt_variant": "quarter_dt",
        "dt_scale": 0.25,
        "dt": 0.01,
        "drive_cutoff_time": 17.9425,
        "cutoff_phase_cycles": 0.5071,
        "drive_frequency": 0.92,
        "grid_size": 51,
        "work_per_source_area": 0.105,
        "target_reference_work_per_source_area": 0.105,
        "work_per_area_relative_error": 0.0,
        "added_positive_work": 0.0,
        "energy_accounting_clean": True,
        "default_major_peaks_at_0p30": major,
        "default_refocus_peaks_at_0p30": refocus,
        "conservative_major_peaks": major,
        "conservative_refocus_peaks": refocus,
        "retention": 0.31,
        "outer_shell": 0.63,
        "decay": -0.024,
        "no_exit": True,
        "global_outer_false": True,
        "post_cutoff_shell_area": 0.00286,
        "tail_area_after_t50": tail,
        "shell_energy_autocorrelation": 0.99997,
        "dominant_spectral_concentration": spectral,
        "return_timing_regularity": timing,
        "conservative_score": score,
        "default_threshold_score": score + 1000.0,
        "inward_flux_fraction": 0.823,
        "outward_flux_fraction": 0.177,
        "strict_clean_pass": major >= 9 and refocus >= 8,
        "no_active_second_pulse": True,
        "no_resonator_layer": True,
    }


if __name__ == "__main__":
    unittest.main()
