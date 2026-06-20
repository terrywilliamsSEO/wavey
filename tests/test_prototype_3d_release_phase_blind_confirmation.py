"""Tests for the 3D release-phase blind confirmation command."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_release_phase_blind_confirmation import (
    ReleasePhaseBlindConfirmationOptions,
    _variant_plan,
    classify_release_phase_blind_confirmation,
)


class Prototype3DReleasePhaseBlindConfirmationTests(unittest.TestCase):
    def test_variant_plan_keeps_fixed_blind_scope(self) -> None:
        options = ReleasePhaseBlindConfirmationOptions()

        variants = _variant_plan(SimulationConfig(), options)

        self.assertEqual(len(variants), 5)
        self.assertEqual([variant.drive_cutoff_time for variant in variants], list(options.cutoffs))
        self.assertEqual([getattr(variant, "_prediction_role") for variant in variants], list(options.prediction_roles))
        self.assertTrue(all(variant.grid_size == 41 for variant in variants))
        self.assertTrue(all(variant.drive_frequency == 0.92 for variant in variants))
        self.assertTrue(all(variant.drive_phase_mode == "cubic" for variant in variants))
        self.assertTrue(all(variant.boundary_cubic_phase_sign == -1.0 for variant in variants))
        self.assertTrue(all(variant.boundary_phase_offset == 0.0 for variant in variants))
        self.assertTrue(all(variant.defect_stiffness_multiplier == 1.0 for variant in variants))
        self.assertTrue(all(variant.defect_damping_multiplier == 1.0 for variant in variants))
        self.assertTrue(all(variant.defect_coupling_multiplier == 1.0 for variant in variants))
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(variant.second_pulse_duration == 0.0 for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))

    def test_classifies_blind_confirmed_when_strong_beats_weak(self) -> None:
        rows = [
            _row("strong_a", "predicted_strong", major=9, refocus=8, score=9811.0),
            _row("strong_b", "predicted_strong", major=9, refocus=8, score=9810.0),
            _row("edge_a", "predicted_boundary_edge", major=9, refocus=8, score=9800.0),
            _row("edge_b", "predicted_boundary_edge", major=9, refocus=8, score=9799.0),
            _row("weak", "predicted_weak_negative_control", major=8, refocus=7, score=8710.0),
        ]

        classification = classify_release_phase_blind_confirmation(rows)

        self.assertEqual(classification["label"], "release_phase_blind_confirmed")

    def test_classifies_partial_when_weak_reaches_strict_floor_but_lower_score(self) -> None:
        rows = [
            _row("strong_a", "predicted_strong", major=9, refocus=8, score=9811.0),
            _row("strong_b", "predicted_strong", major=9, refocus=8, score=9810.0),
            _row("weak", "predicted_weak_negative_control", major=9, refocus=8, score=9800.0),
        ]

        classification = classify_release_phase_blind_confirmation(rows)

        self.assertEqual(classification["label"], "release_phase_rule_partially_confirmed")

    def test_classifies_failed_when_strong_drops_below_strict_floor(self) -> None:
        rows = [
            _row("strong_a", "predicted_strong", major=9, refocus=8, score=9811.0),
            _row("strong_b", "predicted_strong", major=8, refocus=7, score=8700.0),
            _row("weak", "predicted_weak_negative_control", major=8, refocus=7, score=8700.0),
        ]

        classification = classify_release_phase_blind_confirmation(rows)

        self.assertEqual(classification["label"], "release_phase_rule_failed")

    def test_classifies_detector_only_when_only_default_counts_separate(self) -> None:
        rows = [
            _row("strong_a", "predicted_strong", major=9, refocus=8, default=(11, 10), score=9811.0),
            _row("strong_b", "predicted_strong", major=9, refocus=8, default=(11, 10), score=9810.0),
            _row("weak", "predicted_weak_negative_control", major=9, refocus=8, default=(10, 9), score=9800.0),
        ]

        classification = classify_release_phase_blind_confirmation(rows)

        self.assertEqual(classification["label"], "release_phase_detector_only")


def _row(
    variant: str,
    role: str,
    *,
    major: int,
    refocus: int,
    score: float,
    default: tuple[int, int] = (10, 9),
) -> dict:
    return {
        "variant": variant,
        "prediction_role": role,
        "drive_cutoff_time": 17.93,
        "cutoff_phase_cycles": 0.50,
        "default_major_peaks_at_0p30": default[0],
        "default_refocus_peaks_at_0p30": default[1],
        "conservative_major_peaks": major,
        "conservative_refocus_peaks": refocus,
        "retention": 0.31,
        "outer_shell": 0.63,
        "decay": -0.024,
        "no_exit": True,
        "global_outer_false": True,
        "threshold_free_shell_energy_area_after_cutoff": 0.0028,
        "threshold_free_tail_energy_area_after_t50": 0.0012,
        "return_timing_regularity": 0.85,
        "conservative_score": score,
    }


if __name__ == "__main__":
    unittest.main()
