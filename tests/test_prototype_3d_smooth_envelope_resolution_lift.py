import unittest

from simulation.prototype_3d_smooth_envelope_resolution_lift import (
    SmoothEnvelopeResolutionLiftOptions,
    _gate_rows,
    classify_smooth_envelope_resolution_lift,
)


class SmoothEnvelopeResolutionLiftTests(unittest.TestCase):
    def test_scale_rescue_requires_counts_and_coherence(self) -> None:
        rows = [
            _row("hard", "hard_cutoff_control", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("candidate", "smooth_candidate", 9, 8, shell=0.66, radial=0.71, angular=0.67),
            _row("weak", "smooth_negative_phase_control", 8, 7, shell=0.60, radial=0.66, angular=0.61),
        ]
        comparisons = _comparisons(shell_delta=0.08, radial_delta=0.07, angular_delta=0.08, proof_reduction=0.05)
        gates = _gate_rows(rows, comparisons, SmoothEnvelopeResolutionLiftOptions())

        result = classify_smooth_envelope_resolution_lift(rows, comparisons, gates)

        self.assertEqual(result["label"], "smooth_envelope_scale_rescue_supported")

    def test_coherence_improved_count_not_restored(self) -> None:
        rows = [
            _row("hard", "hard_cutoff_control", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("candidate", "smooth_candidate", 8, 7, shell=0.66, radial=0.71, angular=0.67),
            _row("weak", "smooth_negative_phase_control", 7, 6, shell=0.60, radial=0.66, angular=0.61),
        ]
        comparisons = _comparisons(shell_delta=0.08, radial_delta=0.07, angular_delta=0.08, proof_reduction=0.05)
        gates = _gate_rows(rows, comparisons, SmoothEnvelopeResolutionLiftOptions())

        result = classify_smooth_envelope_resolution_lift(rows, comparisons, gates)

        self.assertEqual(result["label"], "coherence_improved_count_not_restored")

    def test_count_improved_without_coherence_is_suspicious(self) -> None:
        rows = [
            _row("hard", "hard_cutoff_control", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("candidate", "smooth_candidate", 9, 8, shell=0.58, radial=0.64, angular=0.59),
            _row("weak", "smooth_negative_phase_control", 8, 7, shell=0.60, radial=0.66, angular=0.61),
        ]
        comparisons = _comparisons(shell_delta=0.0, radial_delta=0.0, angular_delta=0.0, proof_reduction=-0.01)
        gates = _gate_rows(rows, comparisons, SmoothEnvelopeResolutionLiftOptions())

        result = classify_smooth_envelope_resolution_lift(rows, comparisons, gates)

        self.assertEqual(result["label"], "count_improved_without_coherence")

    def test_no_rescue_when_neither_count_nor_coherence_improves(self) -> None:
        rows = [
            _row("hard", "hard_cutoff_control", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("candidate", "smooth_candidate", 7, 6, shell=0.58, radial=0.64, angular=0.59),
            _row("weak", "smooth_negative_phase_control", 7, 6, shell=0.60, radial=0.66, angular=0.61),
        ]
        comparisons = _comparisons(shell_delta=0.0, radial_delta=0.0, angular_delta=0.0, proof_reduction=-0.01)
        gates = _gate_rows(rows, comparisons, SmoothEnvelopeResolutionLiftOptions())

        result = classify_smooth_envelope_resolution_lift(rows, comparisons, gates)

        self.assertEqual(result["label"], "smooth_envelope_no_rescue")


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
        "dominant_shell_frequency": 0.012806,
        "source_sideband_reduction_vs_hard": 0.98 if role != "hard_cutoff_control" else 0.0,
        "source_bandwidth_ratio_to_hard": 0.30 if role != "hard_cutoff_control" else 1.0,
        "outer_shell": 0.65,
        "global_outer_false": True,
        "no_exit": True,
        "post_cutoff_positive_work": 0.0,
        "energy_accounting_clean": True,
        "tail_packet_radius_mean": 8.0,
    }


def _comparisons(*, shell_delta: float, radial_delta: float, angular_delta: float, proof_reduction: float) -> list[dict]:
    return [
        {
            "comparison": "smooth_candidate_vs_hard_control",
            "shell_phase_coherence_delta": shell_delta,
            "radial_phase_coherence_delta": radial_delta,
            "angular_phase_coherence_delta": angular_delta,
            "candidate_tail_radius_shift_abs_not_worse": True,
            "candidate_tail_radius_shift_from_proof": 0.0,
        },
        {
            "comparison": "smooth_candidate_toward_41_proof",
            "coherence_moves_toward_41_proof": proof_reduction >= 0.0,
            "coherence_distance_reduction_mean": proof_reduction,
        },
    ]


if __name__ == "__main__":
    unittest.main()
