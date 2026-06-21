import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_boundary_phase_conjugate import (
    PHASE_CONJUGATE_ROLES,
    BoundaryPhaseConjugateOptions,
    _gate_rows,
    _variant_plan,
    classify_boundary_phase_conjugate,
)


class BoundaryPhaseConjugateControlTests(unittest.TestCase):
    def test_variant_plan_freezes_candidate_and_controls(self) -> None:
        options = BoundaryPhaseConjugateOptions(patch_u_bins=2, patch_v_bins=2)
        design = _design(options, phase=0.1)
        wrong = _design(options, phase=-0.1)
        shuffled = _design(options, phase=0.2)

        variants = _variant_plan(SimulationConfig(), options, design, wrong, shuffled)

        self.assertEqual([getattr(variant, "_prediction_role") for variant in variants], list(PHASE_CONJUGATE_ROLES))
        self.assertEqual([getattr(variant, "_patch_mode") for variant in variants], ["none", "phase_amp", "phase_amp", "amp_only", "phase_only", "phase_amp"])
        self.assertTrue(all(variant.grid_size == 51 for variant in variants))
        self.assertTrue(all(variant.drive_frequency == 0.92 for variant in variants))
        self.assertTrue(all(variant.drive_phase_mode == "cubic" for variant in variants))
        self.assertTrue(all(variant.boundary_cubic_phase_sign == -1.0 for variant in variants))
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))
        self.assertIsNone(variants[0].boundary_patch_phase_offsets)
        self.assertIsNone(variants[0].boundary_patch_amplitude_scales)
        self.assertIsNotNone(variants[1].boundary_patch_phase_offsets)
        self.assertIsNotNone(variants[1].boundary_patch_amplitude_scales)
        self.assertIsNone(variants[3].boundary_patch_phase_offsets)
        self.assertIsNotNone(variants[3].boundary_patch_amplitude_scales)
        self.assertIsNotNone(variants[4].boundary_patch_phase_offsets)
        self.assertIsNone(variants[4].boundary_patch_amplitude_scales)

    def test_supported_requires_strict_recovery_coherence_and_shuffled_failure(self) -> None:
        rows = [
            _row("hard", "hard_51_control", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("candidate", "phase_conjugate_candidate", 9, 8, shell=0.66, radial=0.71, angular=0.67),
            _row("shuffled", "shuffled_patch_phase_control", 7, 6, shell=0.59, radial=0.65, angular=0.60),
            _row("amp", "amplitude_only_control", 7, 6, shell=0.59, radial=0.65, angular=0.60),
            _row("phase", "phase_only_control", 8, 7, shell=0.60, radial=0.66, angular=0.61),
            _row("wrong", "wrong_return_target_control", 7, 6, shell=0.59, radial=0.65, angular=0.60),
        ]
        comparisons = _comparisons(shell_delta=0.08, radial_delta=0.07, angular_delta=0.08, proof_reduction=0.05)
        gates = _gate_rows(rows, comparisons, BoundaryPhaseConjugateOptions())

        result = classify_boundary_phase_conjugate(rows, comparisons, gates)

        self.assertEqual(result["label"], "boundary_phase_conjugate_supported")

    def test_count_improved_without_coherence_is_suspicious(self) -> None:
        rows = [
            _row("hard", "hard_51_control", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("candidate", "phase_conjugate_candidate", 9, 8, shell=0.58, radial=0.64, angular=0.59),
            _row("shuffled", "shuffled_patch_phase_control", 7, 6, shell=0.59, radial=0.65, angular=0.60),
        ]
        comparisons = _comparisons(shell_delta=0.0, radial_delta=0.0, angular_delta=0.0, proof_reduction=-0.01)
        gates = _gate_rows(rows, comparisons, BoundaryPhaseConjugateOptions())

        result = classify_boundary_phase_conjugate(rows, comparisons, gates)

        self.assertEqual(result["label"], "count_improved_without_coherence")

    def test_coherence_improved_count_not_restored(self) -> None:
        rows = [
            _row("hard", "hard_51_control", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("candidate", "phase_conjugate_candidate", 8, 7, shell=0.66, radial=0.71, angular=0.67),
            _row("shuffled", "shuffled_patch_phase_control", 7, 6, shell=0.59, radial=0.65, angular=0.60),
        ]
        comparisons = _comparisons(shell_delta=0.08, radial_delta=0.07, angular_delta=0.08, proof_reduction=0.05)
        gates = _gate_rows(rows, comparisons, BoundaryPhaseConjugateOptions())

        result = classify_boundary_phase_conjugate(rows, comparisons, gates)

        self.assertEqual(result["label"], "coherence_improved_count_not_restored")

    def test_no_rescue_when_candidate_does_not_improve(self) -> None:
        rows = [
            _row("hard", "hard_51_control", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("candidate", "phase_conjugate_candidate", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("shuffled", "shuffled_patch_phase_control", 7, 6, shell=0.59, radial=0.65, angular=0.60),
        ]
        comparisons = _comparisons(shell_delta=0.0, radial_delta=0.0, angular_delta=0.0, proof_reduction=-0.01)
        gates = _gate_rows(rows, comparisons, BoundaryPhaseConjugateOptions())

        result = classify_boundary_phase_conjugate(rows, comparisons, gates)

        self.assertEqual(result["label"], "boundary_phase_conjugate_no_rescue")


def _row(
    variant: str,
    role: str,
    major: int,
    refocus: int,
    *,
    shell: float,
    radial: float,
    angular: float,
) -> dict:
    return {
        "variant": variant,
        "prediction_role": role,
        "default_major_peaks_at_0p30": major,
        "default_refocus_peaks_at_0p30": refocus,
        "conservative_major_peaks": major,
        "conservative_refocus_peaks": refocus,
        "loose_major_peaks_at_0p20": 11,
        "loose_refocus_peaks_at_0p20": 10,
        "shell_phase_coherence_mean": shell,
        "radial_phase_coherence_mean": radial,
        "angular_phase_coherence_mean": angular,
        "outer_shell": 0.65,
        "global_outer_false": True,
        "no_exit": True,
        "post_cutoff_positive_work": 0.0,
        "energy_accounting_clean": True,
        "work_per_area_relative_error": 0.0,
    }


def _comparisons(*, shell_delta: float, radial_delta: float, angular_delta: float, proof_reduction: float) -> list[dict]:
    return [
        {
            "comparison": "candidate_vs_hard_control",
            "shell_phase_coherence_delta": shell_delta,
            "radial_phase_coherence_delta": radial_delta,
            "angular_phase_coherence_delta": angular_delta,
        },
        {
            "comparison": "candidate_toward_41_proof",
            "coherence_moves_toward_41_proof": proof_reduction >= 0.0,
            "coherence_distance_reduction_mean": proof_reduction,
        },
    ]


def _design(options: BoundaryPhaseConjugateOptions, *, phase: float) -> dict:
    phase_offsets = {}
    amplitude_scales = {}
    for face in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"):
        for u_bin in range(options.patch_u_bins):
            for v_bin in range(options.patch_v_bins):
                patch_id = f"{face}:{u_bin}:{v_bin}"
                phase_offsets[patch_id] = phase
                amplitude_scales[patch_id] = 1.0
    return {"phase_offsets": phase_offsets, "amplitude_scales": amplitude_scales}


if __name__ == "__main__":
    unittest.main()
