import unittest

from simulation.prototype_3d_release_phase_resolution_postmortem import (
    ReleasePhaseResolutionPostmortemOptions,
    classify_release_phase_resolution_postmortem,
)


class ReleasePhaseResolutionPostmortemTests(unittest.TestCase):
    def test_blurred_returns_do_not_predict_retry_when_controls_are_competitive(self) -> None:
        rows = [
            _row("proof_winner", major_30=10, major_40=9),
            _row("proof_winner", major_30=10, major_40=9),
            _row("lift_candidate", major_20=11, major_30=9, major_40=7),
            _row("lift_control", major_20=11, major_30=9, major_40=7),
            _row("lift_control", major_20=11, major_30=9, major_40=7),
        ]
        comparisons = [
            {
                "lift_group": "lift_candidate",
                "tail_area_relative_delta": -0.05,
                "tail_packet_radius_delta": 1.1,
                "packet_peak_radius_at_shell_peak_delta": 0.0,
                "arrival_time_delta": -0.88,
                "first_refocus_time_delta": 1.2,
            }
        ]

        result = classify_release_phase_resolution_postmortem(rows, comparisons, ReleasePhaseResolutionPostmortemOptions())

        self.assertEqual(result["label"], "resolution_lift_blurred_returns_no_predictive_recalibration")
        self.assertTrue(result["checks"]["controls_competitive"])
        self.assertEqual(result["checks"]["candidate_low_threshold_recovery"], 2)

    def test_coherent_timing_shift_predicts_single_cutoff_retry_when_controls_do_not_match(self) -> None:
        rows = [
            _row("proof_winner", major_30=10, major_40=9),
            _row("lift_candidate", major_20=10, major_30=10, major_40=9),
            _row("lift_control", major_20=8, major_30=8, major_40=7),
        ]
        comparisons = [
            {
                "lift_group": "lift_candidate",
                "tail_area_relative_delta": -0.04,
                "tail_packet_radius_delta": 0.2,
                "packet_peak_radius_at_shell_peak_delta": 0.0,
                "arrival_time_delta": 1.0,
                "first_refocus_time_delta": 1.2,
            }
        ]

        result = classify_release_phase_resolution_postmortem(rows, comparisons, ReleasePhaseResolutionPostmortemOptions())

        self.assertEqual(result["label"], "resolution_lift_predictable_timing_shift")
        self.assertFalse(result["checks"]["controls_competitive"])
        self.assertTrue(result["checks"]["timing_shift_consistent"])

    def test_coherent_radial_shift_predicts_shell_window_retry(self) -> None:
        rows = [
            _row("proof_winner", major_30=10, major_40=9),
            _row("lift_candidate", major_20=10, major_30=10, major_40=9),
            _row("lift_control", major_20=8, major_30=8, major_40=7),
        ]
        comparisons = [
            {
                "lift_group": "lift_candidate",
                "tail_area_relative_delta": -0.04,
                "tail_packet_radius_delta": 1.0,
                "packet_peak_radius_at_shell_peak_delta": 0.8,
                "arrival_time_delta": -0.2,
                "first_refocus_time_delta": 0.1,
            }
        ]

        result = classify_release_phase_resolution_postmortem(rows, comparisons, ReleasePhaseResolutionPostmortemOptions())

        self.assertEqual(result["label"], "resolution_lift_predictable_radial_window_shift")
        self.assertTrue(result["checks"]["radial_shift_predictive"])


def _row(group: str, *, major_20: int | None = None, major_30: int, major_40: int) -> dict:
    return {
        "group": group,
        "major_peaks_at_0p20": major_20 if major_20 is not None else major_30,
        "major_peaks_at_0p30": major_30,
        "major_peaks_at_0p40": major_40,
    }


if __name__ == "__main__":
    unittest.main()
