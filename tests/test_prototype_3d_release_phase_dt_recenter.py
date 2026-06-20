"""Tests for half-dt release-phase recentering."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_release_phase_dt_recenter import (
    DEFAULT_RECENTER_CUTOFFS,
    ReleasePhaseDtRecenterOptions,
    _variant_plan,
    classify_release_phase_dt_recenter,
)


class Prototype3DReleasePhaseDtRecenterTests(unittest.TestCase):
    def test_variant_plan_is_fixed_half_dt_only(self) -> None:
        base = SimulationConfig()
        options = ReleasePhaseDtRecenterOptions()

        variants = _variant_plan(base, options)

        self.assertEqual(len(variants), len(DEFAULT_RECENTER_CUTOFFS))
        self.assertEqual([variant.drive_cutoff_time for variant in variants], list(DEFAULT_RECENTER_CUTOFFS))
        self.assertTrue(all(getattr(variant, "_dt_variant") == "half_dt" for variant in variants))
        self.assertTrue(all(getattr(variant, "_dt_scale") == 0.5 for variant in variants))
        self.assertTrue(all(variant.dt == base.dt * 0.5 for variant in variants))
        self.assertTrue(all(variant.grid_size == 41 for variant in variants))
        self.assertTrue(all(variant.drive_frequency == 0.92 for variant in variants))
        self.assertTrue(all(variant.drive_phase_mode == "cubic" for variant in variants))
        self.assertTrue(all(variant.boundary_cubic_phase_sign == -1.0 for variant in variants))
        self.assertTrue(all(variant.boundary_phase_offset == 0.0 for variant in variants))
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(variant.second_pulse_duration == 0.0 for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))

    def test_classifies_recentered_when_neighboring_candidates_are_clean(self) -> None:
        rows = [
            _row("candidate_a", "recenter_candidate", 17.9375, major=9, refocus=8, score=9851.0),
            _row("candidate_b", "recenter_candidate", 17.9400, major=9, refocus=8, score=9850.0),
            _row("candidate_c", "recenter_candidate", 17.9425, major=8, refocus=7, score=8750.0),
            _row("low", "low_side_control", 17.9225, major=8, refocus=7, score=8750.0),
            _row("weak", "weak_negative_control", 17.915, major=8, refocus=7, score=8749.0),
        ]

        classification = classify_release_phase_dt_recenter(rows)

        self.assertEqual(classification["label"], "release_phase_half_dt_recentered")

    def test_classifies_single_row_when_only_one_candidate_is_clean(self) -> None:
        rows = [
            _row("candidate_a", "recenter_candidate", 17.9375, major=9, refocus=8, score=9851.0),
            _row("candidate_b", "recenter_candidate", 17.9400, major=8, refocus=7, score=8750.0),
            _row("low", "low_side_control", 17.9225, major=8, refocus=7, score=8750.0),
        ]

        classification = classify_release_phase_dt_recenter(rows)

        self.assertEqual(classification["label"], "release_phase_half_dt_single_row")

    def test_classifies_failed_when_low_side_matches_best_candidate(self) -> None:
        rows = [
            _row("candidate_a", "recenter_candidate", 17.9375, major=9, refocus=8, score=9851.0),
            _row("candidate_b", "recenter_candidate", 17.9400, major=8, refocus=7, score=8750.0),
            _row("low", "low_side_control", 17.9225, major=9, refocus=8, score=8750.0),
        ]

        classification = classify_release_phase_dt_recenter(rows)

        self.assertEqual(classification["label"], "release_phase_half_dt_failed")

    def test_classifies_inconclusive_when_counts_degrade_but_metrics_order(self) -> None:
        rows = [
            _row("candidate_a", "recenter_candidate", 17.9375, major=8, refocus=7, score=8800.0, area=0.0030, timing=0.80),
            _row("candidate_b", "recenter_candidate", 17.9400, major=8, refocus=7, score=8790.0, area=0.0029, timing=0.78),
            _row("low", "low_side_control", 17.9225, major=7, refocus=6, score=8700.0, area=0.0025, timing=0.75),
        ]

        classification = classify_release_phase_dt_recenter(rows)

        self.assertEqual(classification["label"], "release_phase_half_dt_inconclusive")

    def test_classifies_failed_when_strong_region_disappears(self) -> None:
        rows = [
            _row("candidate_a", "recenter_candidate", 17.9375, major=8, refocus=7, score=8750.0, timing=0.70),
            _row("candidate_b", "recenter_candidate", 17.9400, major=8, refocus=7, score=8749.0, timing=0.70),
            _row("low", "low_side_control", 17.9225, major=8, refocus=7, score=8748.0, timing=0.90),
        ]

        classification = classify_release_phase_dt_recenter(rows)

        self.assertEqual(classification["label"], "release_phase_half_dt_failed")


def _row(
    variant: str,
    role: str,
    cutoff: float,
    *,
    major: int,
    refocus: int,
    score: float,
    area: float = 0.0028,
    timing: float = 0.85,
) -> dict:
    return {
        "variant": variant,
        "prediction_role": role,
        "dt_variant": "half_dt",
        "drive_cutoff_time": cutoff,
        "cutoff_phase_cycles": 0.50,
        "default_major_peaks_at_0p30": major,
        "default_refocus_peaks_at_0p30": refocus,
        "conservative_major_peaks": major,
        "conservative_refocus_peaks": refocus,
        "retention": 0.31,
        "outer_shell": 0.63,
        "decay": -0.024,
        "no_exit": True,
        "global_outer_false": True,
        "post_cutoff_shell_area": area,
        "tail_area_after_t50": 0.0012,
        "shell_energy_autocorrelation": 0.99,
        "dominant_spectral_concentration": 0.74,
        "return_timing_regularity": timing,
        "conservative_score": score,
    }


if __name__ == "__main__":
    unittest.main()
