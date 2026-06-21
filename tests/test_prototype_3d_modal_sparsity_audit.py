import unittest

import numpy as np

from simulation.prototype_3d_modal_sparsity_audit import (
    ModalSparsityAuditOptions,
    _sparse_spectrum,
    classify_modal_sparsity_audit,
)


class ModalSparsityAuditTests(unittest.TestCase):
    def test_sparse_spectrum_detects_few_mode_signal(self) -> None:
        times = np.arange(0.0, 120.0, 0.05)
        values = (
            1.5 * np.sin(2.0 * np.pi * (8.0 / 120.0) * times)
            + 0.75 * np.sin(2.0 * np.pi * (15.0 / 120.0) * times + 0.3)
            + 0.2 * np.sin(2.0 * np.pi * (25.0 / 120.0) * times)
        )

        spectrum = _sparse_spectrum(times, values)

        self.assertLessEqual(spectrum["modes_for_99pct"], 3)
        self.assertLess(spectrum["modal_participation_ratio"], 3.0)
        self.assertGreater(spectrum["top3_power_fraction"], 0.99)

    def test_classifier_marks_common_source_shaping_dead_end(self) -> None:
        options = ModalSparsityAuditOptions()
        rows = [
            self._row("proof_41", "proof_pack", "proof_candidate", 41, 9, 6, 4.0, 6.0, 0.8),
            self._row("proof_41", "proof_pack", "proof_candidate", 41, 9, 7, 4.4, 6.1, 0.8),
            self._row("proof_41", "proof_pack", "upper_immediate_control", 41, 9, 7, 4.5, 6.1, 0.8),
            self._row("lift_51", "resolution_lift", "candidate", 51, 7, 24, 18.0, 6.2, 0.9),
            self._row("smooth_51", "smooth_envelope", "hard_cutoff_control", 51, 7, 25, 18.3, 6.2, 0.9),
            self._row("smooth_51", "smooth_envelope", "smooth_envelope_candidate", 51, 7, 24, 18.1, 6.2, 0.9),
            self._row("phase_51", "boundary_phase_conjugate", "hard_51_control", 51, 7, 25, 18.2, 6.2, 0.9),
            self._row("phase_51", "boundary_phase_conjugate", "phase_conjugate_candidate", 51, 7, 24, 18.1, 6.2, 0.9),
            self._row("phase_51", "boundary_phase_conjugate", "shuffled_patch_phase_control", 51, 7, 25, 18.2, 6.2, 0.9),
        ]

        result = classify_modal_sparsity_audit(rows, options)

        self.assertEqual(result["label"], "source_shaping_modal_dead_end_supported")
        self.assertTrue(result["checks"]["source_controls_same_signature"])

    def test_classifier_reports_source_variant_difference(self) -> None:
        rows = [
            self._row("proof_41", "proof_pack", "proof_candidate", 41, 9, 6, 4.0, 6.0, 0.8),
            self._row("proof_41", "proof_pack", "proof_candidate", 41, 9, 7, 4.4, 6.1, 0.8),
            self._row("lift_51", "resolution_lift", "candidate", 51, 7, 24, 18.0, 6.2, 0.9),
            self._row("smooth_51", "smooth_envelope", "hard_cutoff_control", 51, 7, 25, 18.3, 6.2, 0.9),
            self._row("smooth_51", "smooth_envelope", "smooth_envelope_candidate", 51, 9, 6, 4.0, 6.2, 0.8),
            self._row("phase_51", "boundary_phase_conjugate", "phase_conjugate_candidate", 51, 7, 25, 18.2, 6.2, 0.9),
            self._row("phase_51", "boundary_phase_conjugate", "shuffled_patch_phase_control", 51, 7, 25, 18.2, 6.2, 0.9),
        ]

        result = classify_modal_sparsity_audit(rows, ModalSparsityAuditOptions())

        self.assertEqual(result["label"], "source_variant_modal_difference_supported")

    def test_classifier_can_report_common_blur_without_99_mode_split(self) -> None:
        rows = [
            self._row("proof_41", "proof_pack", "proof_candidate", 41, 9, 12, 7.0, 6.0, 0.7),
            self._row("proof_41", "proof_pack", "proof_candidate", 41, 9, 12, 7.1, 6.0, 0.7),
            self._row("lift_51", "resolution_lift", "candidate", 51, 7, 14, 8.0, 6.1, 0.9),
            self._row("smooth_51", "smooth_envelope", "hard_cutoff_control", 51, 7, 14, 8.1, 6.1, 0.9),
            self._row("smooth_51", "smooth_envelope", "smooth_envelope_candidate", 51, 7, 14, 8.1, 6.1, 0.9),
            self._row("phase_51", "boundary_phase_conjugate", "phase_conjugate_candidate", 51, 7, 14, 8.1, 6.1, 0.9),
            self._row("phase_51", "boundary_phase_conjugate", "shuffled_patch_phase_control", 51, 7, 14, 8.1, 6.1, 0.9),
        ]

        result = classify_modal_sparsity_audit(rows, ModalSparsityAuditOptions())

        self.assertEqual(result["label"], "common_51_blur_signature_supported")

    def test_classifier_reports_common_source_signature_without_broad_density(self) -> None:
        rows = [
            self._row("proof_41", "proof_pack", "proof_candidate", 41, 9, 9, 1.7, 6.5, 0.8),
            self._row("proof_41", "proof_pack", "proof_candidate", 41, 9, 9, 1.7, 6.5, 0.8),
            self._row("lift_51", "resolution_lift", "candidate", 51, 7, 18, 1.4, 6.1, 0.7),
            self._row("smooth_51", "smooth_envelope", "hard_cutoff_control", 51, 8, 16, 1.4, 6.1, 0.7),
            self._row("smooth_51", "smooth_envelope", "smooth_envelope_candidate", 51, 7, 18, 1.4, 6.1, 0.7),
            self._row("phase_51", "boundary_phase_conjugate", "phase_conjugate_candidate", 51, 7, 17, 1.4, 6.1, 0.7),
            self._row("phase_51", "boundary_phase_conjugate", "shuffled_patch_phase_control", 51, 7, 17, 1.4, 6.1, 0.7),
        ]

        result = classify_modal_sparsity_audit(rows, ModalSparsityAuditOptions())

        self.assertEqual(result["label"], "common_51_source_signature_supported")

    def _row(
        self,
        audit_group: str,
        artifact_source: str,
        prediction_role: str,
        grid_size: int,
        strict_major: int,
        modes99: int,
        participation: float,
        period: float,
        width: float,
    ) -> dict[str, object]:
        return {
            "audit_group": audit_group,
            "artifact_source": artifact_source,
            "prediction_role": prediction_role,
            "grid_size": grid_size,
            "strict_major_peaks": strict_major,
            "strict_refocus_peaks": max(strict_major - 1, 0),
            "modes_for_99pct": modes99,
            "modal_participation_ratio": participation,
            "mean_return_period": period,
            "mean_peak_width_time": width,
        }


if __name__ == "__main__":
    unittest.main()
