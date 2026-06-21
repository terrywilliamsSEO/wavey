import unittest

import numpy as np

from simulation.prototype_3d_return_pattern_symmetry_audit import (
    ReturnPatternSymmetryAuditOptions,
    align_circular_sector_shift,
    calculate_phase_aligned_similarity,
    calculate_sign_aligned_similarity,
    calculate_transform_stability,
    classify_return_pattern_symmetry_audit,
    enumerate_cubic_transforms,
)


class ReturnPatternSymmetryAuditTests(unittest.TestCase):
    def test_cubic_transform_enumeration_counts_proper_and_reflected(self) -> None:
        proper = enumerate_cubic_transforms(include_reflections=False)
        reflected = enumerate_cubic_transforms(include_reflections=True)

        self.assertEqual(len(proper), 24)
        self.assertEqual(len(reflected), 48)
        self.assertTrue(all(int(round(np.linalg.det(item["matrix"]))) == 1 for item in proper))
        self.assertEqual(sum(1 for item in reflected if item["determinant"] == -1), 24)

    def test_sign_and_phase_aligned_similarity(self) -> None:
        left = np.asarray([1.0, -2.0, 3.0])
        right = -left

        self.assertAlmostEqual(calculate_sign_aligned_similarity(left, right), 1.0)

        complex_left = np.asarray([1.0 + 0.0j, 0.0 + 2.0j])
        complex_right = complex_left * 1.0j
        self.assertAlmostEqual(calculate_phase_aligned_similarity(complex_left, complex_right), 1.0)

    def test_circular_sector_shift_alignment(self) -> None:
        left = np.asarray([[1.0, 0.0, 0.0, 0.0], [0.0, 2.0, 0.0, 0.0]], dtype=complex)
        right = np.roll(left, shift=1, axis=1)

        result = align_circular_sector_shift(left, right)

        self.assertAlmostEqual(result["similarity"], 1.0)
        self.assertEqual(result["shift"], 3)

    def test_transform_stability_scoring(self) -> None:
        stable = calculate_transform_stability(["identity", "identity", "identity"])
        hopping = calculate_transform_stability(["identity", "rot_x", "rot_y", "identity"])

        self.assertAlmostEqual(stable["stability_score"], 1.0)
        self.assertLess(hopping["stability_score"], 0.6)

    def test_classification_true_scrambling_when_alignment_does_not_rescue(self) -> None:
        rows = [
            self._row("proof", 41, "proof_candidate", 0.66, 0.68, 0.02, 0.02, 0.0, 0.8, "identity"),
            self._row("hard", 51, "hard_cutoff_control", 0.52, 0.54, 0.02, 0.02, 0.0, 0.8, "identity"),
            self._row("smooth", 51, "smooth_candidate", 0.51, 0.53, 0.02, 0.02, 0.0, 0.8, "identity"),
            self._row("pc", 51, "phase_conjugate_candidate", 0.50, 0.53, 0.03, 0.03, 0.0, 0.8, "identity"),
        ]

        result = classify_return_pattern_symmetry_audit(rows, ReturnPatternSymmetryAuditOptions())

        self.assertEqual(result["label"], "true_spatial_scrambling_supported")

    def test_classification_orientation_drift_when_stable_spatial_rescue(self) -> None:
        rows = [
            self._row("proof", 41, "proof_candidate", 0.66, 0.68, 0.02, 0.02, 0.0, 0.9, "rot_+x_+y_+z"),
            self._row("hard", 51, "hard_cutoff_control", 0.50, 0.62, 0.12, 0.01, 0.12, 0.9, "rot_+x_-z_+y"),
            self._row("smooth", 51, "smooth_candidate", 0.51, 0.63, 0.12, 0.01, 0.12, 0.9, "rot_+x_-z_+y"),
            self._row("pc", 51, "phase_conjugate_candidate", 0.49, 0.61, 0.12, 0.01, 0.12, 0.9, "rot_+x_-z_+y"),
        ]

        result = classify_return_pattern_symmetry_audit(rows, ReturnPatternSymmetryAuditOptions())

        self.assertEqual(result["label"], "orientation_drift_supported")

    def test_missing_artifacts_classification(self) -> None:
        result = classify_return_pattern_symmetry_audit([], ReturnPatternSymmetryAuditOptions())

        self.assertEqual(result["label"], "insufficient_artifacts")

    def _row(
        self,
        variant: str,
        grid_size: int,
        role: str,
        raw: float,
        aligned: float,
        rescue: float,
        phase_rescue: float,
        spatial_rescue: float,
        stability: float,
        signature: str,
    ) -> dict[str, object]:
        return {
            "variant": variant,
            "grid_size": grid_size,
            "prediction_role": role,
            "available_artifact_kind": "sector_frames",
            "raw_pattern_memory_score": raw,
            "best_symmetry_aligned_memory_score": aligned,
            "symmetry_rescue_margin": rescue,
            "phase_or_sign_rescue_margin": phase_rescue,
            "spatial_transform_rescue_margin": spatial_rescue,
            "transform_stability_score": stability,
            "dominant_transform_signature": signature,
        }


if __name__ == "__main__":
    unittest.main()
