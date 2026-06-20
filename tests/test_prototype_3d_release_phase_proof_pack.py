"""Tests for the release-phase quarter-dt proof pack."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_release_phase_proof_pack import (
    PROOF_PACK_CUTOFFS,
    ReleasePhaseProofPackOptions,
    _gate_rows,
    _variant_plan,
    classify_release_phase_proof_pack,
)


class Prototype3DReleasePhaseProofPackTests(unittest.TestCase):
    def test_variant_plan_is_fixed_quarter_dt_only(self) -> None:
        base = SimulationConfig()
        options = ReleasePhaseProofPackOptions()

        variants = _variant_plan(base, options)

        self.assertEqual(len(variants), len(PROOF_PACK_CUTOFFS))
        self.assertEqual([variant.drive_cutoff_time for variant in variants], list(PROOF_PACK_CUTOFFS))
        self.assertTrue(all(getattr(variant, "_dt_variant") == "quarter_dt" for variant in variants))
        self.assertTrue(all(getattr(variant, "_dt_scale") == 0.25 for variant in variants))
        self.assertTrue(all(variant.dt == base.dt * 0.25 for variant in variants))
        self.assertTrue(all(variant.grid_size == 41 for variant in variants))
        self.assertTrue(all(variant.drive_frequency == 0.92 for variant in variants))
        self.assertTrue(all(variant.drive_phase_mode == "cubic" for variant in variants))
        self.assertTrue(all(variant.boundary_cubic_phase_sign == -1.0 for variant in variants))
        self.assertTrue(all(variant.boundary_phase_offset == 0.0 for variant in variants))
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(variant.second_pulse_duration == 0.0 for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))

    def test_classifies_proof_supported_with_strict_cluster_and_gates(self) -> None:
        rows = [
            _row("candidate_a", "proof_candidate", 17.9375, major=9, refocus=8, score=9851.0, tail=0.00120, timing=0.84, inward=0.82),
            _row("candidate_b", "proof_candidate", 17.9400, major=9, refocus=8, score=9850.0, tail=0.00121, timing=0.83, inward=0.821),
            _row("control", "lower_immediate_control", 17.935, major=8, refocus=7, score=8750.0, tail=0.00122, timing=0.57, inward=0.82),
        ]
        gates = _gate_rows(rows, ReleasePhaseProofPackOptions())

        classification = classify_release_phase_proof_pack(rows, gates)

        self.assertEqual(classification["label"], "release_phase_quarter_dt_proof_supported")

    def test_classifies_single_row_when_only_one_strict_candidate_survives(self) -> None:
        rows = [
            _row("candidate_a", "proof_candidate", 17.9375, major=9, refocus=8, score=9851.0, tail=0.00120, timing=0.84, inward=0.82),
            _row("candidate_b", "proof_candidate", 17.9400, major=8, refocus=7, score=8800.0, tail=0.00120, timing=0.83, inward=0.821),
            _row("control", "lower_immediate_control", 17.935, major=8, refocus=7, score=8750.0, tail=0.00122, timing=0.57, inward=0.82),
        ]
        gates = _gate_rows(rows, ReleasePhaseProofPackOptions())

        classification = classify_release_phase_proof_pack(rows, gates)

        self.assertEqual(classification["label"], "release_phase_quarter_dt_single_row")

    def test_classifies_threshold_free_supported_when_counts_degrade(self) -> None:
        rows = [
            _row("candidate_a", "proof_candidate", 17.9375, major=8, refocus=7, score=8800.0, tail=0.00120, timing=0.84, inward=0.82),
            _row("candidate_b", "proof_candidate", 17.9400, major=8, refocus=7, score=8790.0, tail=0.00121, timing=0.83, inward=0.821),
            _row("control", "lower_immediate_control", 17.935, major=7, refocus=6, score=8700.0, tail=0.00122, timing=0.57, inward=0.82),
        ]
        gates = _gate_rows(rows, ReleasePhaseProofPackOptions())

        classification = classify_release_phase_proof_pack(rows, gates)

        self.assertEqual(classification["label"], "release_phase_quarter_dt_threshold_free_supported")

    def test_classifies_failed_when_controls_match_best_candidate(self) -> None:
        rows = [
            _row("candidate_a", "proof_candidate", 17.9375, major=9, refocus=8, score=9851.0, tail=0.00120, timing=0.84, inward=0.82),
            _row("candidate_b", "proof_candidate", 17.9400, major=9, refocus=8, score=9850.0, tail=0.00121, timing=0.83, inward=0.821),
            _row("control", "weak_negative_control", 17.915, major=9, refocus=8, score=8750.0, tail=0.00122, timing=0.57, inward=0.82),
        ]
        gates = _gate_rows(rows, ReleasePhaseProofPackOptions())

        classification = classify_release_phase_proof_pack(rows, gates)

        self.assertEqual(classification["label"], "release_phase_quarter_dt_failed")


def _row(
    variant: str,
    role: str,
    cutoff: float,
    *,
    major: int,
    refocus: int,
    score: float,
    tail: float,
    timing: float,
    inward: float,
) -> dict:
    return {
        "variant": variant,
        "prediction_role": role,
        "dt_variant": "quarter_dt",
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
        "post_cutoff_shell_area": 0.0028,
        "tail_area_after_t50": tail,
        "shell_energy_autocorrelation": 0.99,
        "dominant_spectral_concentration": 0.74,
        "return_timing_regularity": timing,
        "inward_flux_fraction": inward,
        "outward_flux_fraction": 1.0 - inward,
        "conservative_score": score,
    }


if __name__ == "__main__":
    unittest.main()
