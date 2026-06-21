import unittest

import numpy as np

from simulation.prototype_3d_off_comb_leakage_audit import (
    OffCombLeakageAuditOptions,
    calculate_angular_sector_coherence,
    calculate_modal_sideband_leakage,
    calculate_outer_off_comb_correlation,
    calculate_radial_leakage_ratio,
    classify_off_comb_leakage_audit,
)


class OffCombLeakageAuditTests(unittest.TestCase):
    def test_radial_leakage_ratio(self) -> None:
        self.assertAlmostEqual(calculate_radial_leakage_ratio(10.0, 2.5), 0.25)
        self.assertGreater(calculate_radial_leakage_ratio(0.0, 1.0), 1.0e6)

    def test_angular_sector_coherence(self) -> None:
        coherent = calculate_angular_sector_coherence([0.1, 0.1, 0.1], [1.0, 2.0, 1.0])
        split = calculate_angular_sector_coherence([0.0, 0.5], [1.0, 1.0])

        self.assertAlmostEqual(coherent, 1.0)
        self.assertLess(split, 1.0e-12)

    def test_outer_off_comb_correlation_finds_positive_lag(self) -> None:
        outer = np.asarray([0.0, 1.0, 0.0, 2.0, 0.0, 3.0, 0.0])
        off_comb = np.asarray([0.0, 0.0, 1.0, 0.0, 2.0, 0.0, 3.0])

        result = calculate_outer_off_comb_correlation(outer, off_comb, max_lag_samples=2)

        self.assertEqual(result["best_lag_samples"], 1.0)
        self.assertGreater(result["best_correlation"], 0.99)

    def test_modal_sideband_leakage(self) -> None:
        frequencies = np.asarray([0.9, 1.0, 1.1, 1.6])
        power = np.asarray([2.0, 8.0, 2.0, 8.0])

        result = calculate_modal_sideband_leakage(
            frequencies,
            power,
            center_frequency=1.0,
            center_half_width=0.02,
            sideband_half_width=0.15,
        )

        self.assertAlmostEqual(result["center_power_fraction"], 0.4)
        self.assertAlmostEqual(result["sideband_power_fraction"], 0.2)
        self.assertAlmostEqual(result["sideband_to_center_ratio"], 0.5)

    def test_mixed_leakage_classification(self) -> None:
        rows = [
            self._row("proof_pack", "proof_candidate", "proof_41", 41, 9, 0.3, 0.8, 0.1, 0.1, 0.2),
            self._row("proof_pack", "upper_immediate_control", "proof_41", 41, 9, 0.3, 0.8, 0.1, 0.1, 0.2),
            self._row("resolution_lift", "candidate", "lift_51", 51, 7, 0.6, 0.55, 0.4, 0.2, 0.5),
            self._row("smooth_envelope", "hard_cutoff_control", "smooth_51", 51, 7, 0.62, 0.56, 0.4, 0.2, 0.5),
            self._row("smooth_envelope", "smooth_candidate", "smooth_51", 51, 7, 0.61, 0.54, 0.4, 0.2, 0.5),
        ]

        result = classify_off_comb_leakage_audit(rows, OffCombLeakageAuditOptions())

        self.assertEqual(result["label"], "mixed_leakage_supported")
        self.assertIn("radial_leakage_supported", result["checks"]["supported_channels"])
        self.assertIn("angular_leakage_supported", result["checks"]["supported_channels"])

    def test_missing_artifacts_classification(self) -> None:
        result = classify_off_comb_leakage_audit([], OffCombLeakageAuditOptions())

        self.assertEqual(result["label"], "insufficient_artifacts")

    def _row(
        self,
        artifact_source: str,
        prediction_role: str,
        audit_group: str,
        grid_size: int,
        strict_major: int,
        radial: float,
        angular: float,
        outer: float,
        modal: float,
        pattern: float,
    ) -> dict[str, object]:
        return {
            "artifact_source": artifact_source,
            "prediction_role": prediction_role,
            "audit_group": audit_group,
            "grid_size": grid_size,
            "strict_major_peaks": strict_major,
            "strict_refocus_peaks": max(strict_major - 1, 0),
            "radial_leakage_ratio": radial,
            "angular_sector_coherence_mean": angular,
            "outer_off_comb_best_correlation": outer,
            "modal_sideband_fraction": modal,
            "spatial_pattern_leakage_score": pattern,
            "off_return_outward_flux_fraction": 0.2,
        }


if __name__ == "__main__":
    unittest.main()
