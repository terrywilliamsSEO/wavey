import unittest

from simulation.prototype_3d_release_phase_modal_audit import (
    ReleasePhaseModalAuditOptions,
    classify_release_phase_modal_audit,
)


class ReleasePhaseModalAuditTests(unittest.TestCase):
    def test_resolution_blur_when_same_band_and_loose_returns_remain(self) -> None:
        rows = [
            _row("proof_cluster", freq=0.156, concentration=0.82, bandwidth=0.020, spread=4.0, radius=6.2, strict=9, loose=9),
            _row("proof_cluster", freq=0.157, concentration=0.80, bandwidth=0.021, spread=4.1, radius=6.3, strict=9, loose=9),
            _row("lift_candidate", freq=0.158, concentration=0.70, bandwidth=0.024, spread=4.4, radius=7.4, strict=7, loose=11),
            _row("lift_control", freq=0.159, concentration=0.69, bandwidth=0.023, spread=4.3, radius=7.3, strict=7, loose=11),
        ]

        result = classify_release_phase_modal_audit(rows, ReleasePhaseModalAuditOptions())

        self.assertEqual(result["label"], "resolution_blur_mechanism_supported")
        self.assertTrue(result["checks"]["same_modal_band"])
        self.assertGreaterEqual(result["checks"]["strict_major_loss"], 1.0)

    def test_finite_grid_when_proof_band_is_not_preserved(self) -> None:
        rows = [
            _row("proof_cluster", freq=0.156, concentration=0.84, bandwidth=0.020, spread=4.0, radius=6.2, strict=9, loose=9),
            _row("lift_candidate", freq=0.220, concentration=0.52, bandwidth=0.030, spread=4.2, radius=6.4, strict=7, loose=8),
            _row("lift_control", freq=0.225, concentration=0.50, bandwidth=0.031, spread=4.2, radius=6.4, strict=7, loose=8),
        ]

        result = classify_release_phase_modal_audit(rows, ReleasePhaseModalAuditOptions())

        self.assertEqual(result["label"], "finite_grid_resonance_likely")
        self.assertFalse(result["checks"]["same_modal_band"])

    def test_scalable_modal_rule_requires_no_strict_loss(self) -> None:
        rows = [
            _row("proof_cluster", freq=0.156, concentration=0.80, bandwidth=0.020, spread=4.0, radius=6.2, strict=9, loose=9),
            _row("lift_candidate", freq=0.157, concentration=0.78, bandwidth=0.021, spread=4.1, radius=6.3, strict=9, loose=9),
        ]

        result = classify_release_phase_modal_audit(rows, ReleasePhaseModalAuditOptions())

        self.assertEqual(result["label"], "scalable_modal_rule_supported")
        self.assertEqual(result["checks"]["mechanism_candidate"], "none")


def _row(
    group: str,
    *,
    freq: float,
    concentration: float,
    bandwidth: float,
    spread: float,
    radius: float,
    strict: int,
    loose: int,
) -> dict:
    return {
        "audit_group": group,
        "dominant_shell_frequency": freq,
        "dominant_spectral_concentration": concentration,
        "spectral_bandwidth": bandwidth,
        "tail_packet_spread_mean": spread,
        "tail_packet_radius_mean": radius,
        "strict_major_peaks": strict,
        "loose_major_peaks": loose,
        "strict_refocus_peaks": max(0, strict - 1),
        "loose_refocus_peaks": max(0, loose - 1),
        "no_exit": True,
        "outer_shell_below_1": True,
    }


if __name__ == "__main__":
    unittest.main()
