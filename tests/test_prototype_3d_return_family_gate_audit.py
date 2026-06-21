import unittest

from simulation.prototype_3d_return_family_gate_audit import (
    ReturnFamilyGateAuditOptions,
    build_return_windows,
    build_threshold_crossing_rows,
    calculate_comb_score,
    calculate_off_comb_energy_ratio,
    classify_return_family_gate_audit,
)


class ReturnFamilyGateAuditTests(unittest.TestCase):
    def test_predicted_return_windows_from_early_peaks(self) -> None:
        options = ReturnFamilyGateAuditOptions(
            early_interval_count=3,
            window_half_width_fraction=0.2,
            min_window_half_width=0.5,
            max_return_windows=5,
        )

        result = build_return_windows([20.0, 26.0, 32.0, 38.0], max_time=50.0, options=options)

        self.assertAlmostEqual(result["period"], 6.0)
        self.assertAlmostEqual(result["period_cv"], 0.0)
        self.assertEqual(len(result["windows"]), 5)
        self.assertAlmostEqual(result["windows"][0]["window_start"], 18.8)
        self.assertAlmostEqual(result["windows"][1]["predicted_time"], 26.0)

    def test_comb_score_uses_occupancy_energy_and_timing(self) -> None:
        score = calculate_comb_score(0.8, 0.75, 0.1)

        self.assertAlmostEqual(score, 0.54)

    def test_threshold_crossing_table_uses_artifact_and_event_counts(self) -> None:
        rows = build_threshold_crossing_rows(
            variant="row",
            artifact_source="unit",
            audit_group="test",
            row={
                "major_peaks_at_0p20": "11",
                "refocus_peaks_at_0p20": "10",
                "major_peaks_at_0p30": "9",
                "refocus_peaks_at_0p30": "8",
            },
            peaks=[
                {"time": 1.0, "energy": 10.0},
                {"time": 2.0, "energy": 4.0},
                {"time": 3.0, "energy": 2.0},
            ],
            thresholds=(0.20, 0.30, 0.40),
        )

        self.assertEqual(rows[0]["artifact_major_peaks"], 11)
        self.assertEqual(rows[1]["artifact_refocus_peaks"], 8)
        self.assertEqual(rows[0]["event_peak_crossing_count"], 3)
        self.assertEqual(rows[2]["event_peak_crossing_count"], 2)

    def test_off_comb_energy_ratio(self) -> None:
        self.assertAlmostEqual(calculate_off_comb_energy_ratio(10.0, 8.0), 0.25)
        self.assertGreater(calculate_off_comb_energy_ratio(10.0, 0.0), 1.0e6)

    def test_classifies_gate_artifact_when_comb_survives_and_amplitude_compresses(self) -> None:
        rows = [
            self._row("proof_pack", "proof_candidate", "proof_41", 41, 9, 0.95, 0.75, 0.20, 0.05, 1.0, 1.0),
            self._row("proof_pack", "upper_immediate_control", "proof_41", 41, 9, 0.95, 0.75, 0.20, 0.05, 1.0, 1.0),
            self._row("resolution_lift", "candidate", "lift_51", 51, 7, 0.90, 0.70, 0.25, 0.04, 0.65, 0.70),
            self._row("smooth_envelope", "hard_cutoff_control", "smooth_51", 51, 8, 0.88, 0.69, 0.25, 0.04, 0.66, 0.70),
            self._row("smooth_envelope", "smooth_candidate", "smooth_51", 51, 7, 0.89, 0.70, 0.25, 0.04, 0.64, 0.70),
            self._row("boundary_phase_conjugate", "phase_conjugate_candidate", "phase_51", 51, 7, 0.89, 0.70, 0.25, 0.04, 0.65, 0.70),
            self._row("boundary_phase_conjugate", "shuffled_patch_phase_control", "phase_51", 51, 7, 0.88, 0.69, 0.25, 0.04, 0.65, 0.70),
        ]

        result = classify_return_family_gate_audit(rows, ReturnFamilyGateAuditOptions())

        self.assertEqual(result["label"], "return_family_survives_gate_artifact_supported")

    def test_classifies_real_weakening_when_occupancy_lost(self) -> None:
        rows = [
            self._row("proof_pack", "proof_candidate", "proof_41", 41, 9, 0.95, 0.75, 0.20, 0.05, 1.0, 1.0),
            self._row("proof_pack", "upper_immediate_control", "proof_41", 41, 9, 0.95, 0.75, 0.20, 0.05, 1.0, 1.0),
            self._row("resolution_lift", "candidate", "lift_51", 51, 7, 0.45, 0.25, 0.30, 0.05, 0.8, 0.8),
            self._row("smooth_envelope", "hard_cutoff_control", "smooth_51", 51, 7, 0.48, 0.25, 0.30, 0.05, 0.8, 0.8),
            self._row("smooth_envelope", "smooth_candidate", "smooth_51", 51, 7, 0.45, 0.25, 0.30, 0.05, 0.8, 0.8),
            self._row("boundary_phase_conjugate", "phase_conjugate_candidate", "phase_51", 51, 7, 0.45, 0.25, 0.30, 0.05, 0.8, 0.8),
        ]

        result = classify_return_family_gate_audit(rows, ReturnFamilyGateAuditOptions())

        self.assertEqual(result["label"], "return_family_weakened_not_gate_artifact")

    def test_missing_artifacts_classification(self) -> None:
        result = classify_return_family_gate_audit([], ReturnFamilyGateAuditOptions())

        self.assertEqual(result["label"], "insufficient_artifacts")

    def _row(
        self,
        artifact_source: str,
        prediction_role: str,
        audit_group: str,
        grid_size: int,
        strict_major: int,
        occupancy: float,
        comb_score: float,
        off_comb: float,
        period_cv: float,
        strength: float,
        prominence: float,
    ) -> dict[str, object]:
        return {
            "artifact_source": artifact_source,
            "prediction_role": prediction_role,
            "audit_group": audit_group,
            "grid_size": grid_size,
            "strict_major_peaks": strict_major,
            "strict_refocus_peaks": max(strict_major - 1, 0),
            "return_window_occupancy_fraction": occupancy,
            "return_comb_score": comb_score,
            "off_comb_energy_ratio": off_comb,
            "predicted_return_period_cv": period_cv,
            "mean_rank_normalized_return_strength": strength,
            "mean_peak_prominence_ratio": prominence,
            "late_return_area_survival_fraction": 0.8,
        }


if __name__ == "__main__":
    unittest.main()
