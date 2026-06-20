import unittest

from simulation.prototype_3d_spatial_phase_instrumentation import (
    SpatialPhaseInstrumentationOptions,
    classify_spatial_phase_instrumentation,
)


class SpatialPhaseInstrumentationTests(unittest.TestCase):
    def test_coherent_blur_when_coherence_is_preserved_but_spread_grows(self) -> None:
        result = classify_spatial_phase_instrumentation(
            [_row("proof_41_reference", strict="9/8"), _row("failed_lift_51_candidate", strict="7/6")],
            [
                _comparison(
                    shell_drop=0.02,
                    radial_drop=0.03,
                    angular_drop=0.01,
                    node_drop=0.02,
                    spread_growth=0.30,
                    strict_loss=2,
                )
            ],
            SpatialPhaseInstrumentationOptions(),
        )

        self.assertEqual(result["label"], "spatial_phase_coherent_blur_supported")

    def test_decoherence_when_spatial_phase_drops(self) -> None:
        result = classify_spatial_phase_instrumentation(
            [_row("proof_41_reference", strict="9/8"), _row("failed_lift_51_candidate", strict="7/6")],
            [
                _comparison(
                    shell_drop=0.01,
                    radial_drop=0.20,
                    angular_drop=0.02,
                    node_drop=0.03,
                    spread_growth=0.05,
                    strict_loss=2,
                )
            ],
            SpatialPhaseInstrumentationOptions(),
        )

        self.assertEqual(result["label"], "spatial_phase_decoherence_supported")

    def test_shell_alignment_when_coherent_but_center_shifted(self) -> None:
        result = classify_spatial_phase_instrumentation(
            [_row("proof_41_reference", strict="9/8"), _row("failed_lift_51_candidate", strict="7/6")],
            [
                _comparison(
                    shell_drop=0.02,
                    radial_drop=0.03,
                    angular_drop=0.01,
                    node_drop=0.02,
                    spread_growth=0.05,
                    center_shift=0.55,
                    strict_loss=2,
                )
            ],
            SpatialPhaseInstrumentationOptions(),
        )

        self.assertEqual(result["label"], "spatial_phase_shell_window_alignment_supported")

    def test_unisolated_when_strict_counts_shrink_without_spatial_signal(self) -> None:
        result = classify_spatial_phase_instrumentation(
            [_row("proof_41_reference", strict="9/8"), _row("failed_lift_51_candidate", strict="7/6")],
            [
                _comparison(
                    shell_drop=0.02,
                    radial_drop=0.03,
                    angular_drop=0.01,
                    node_drop=0.02,
                    spread_growth=0.05,
                    strict_loss=2,
                )
            ],
            SpatialPhaseInstrumentationOptions(),
        )

        self.assertEqual(result["label"], "finite_resolution_spatial_mechanism_not_isolated")


def _row(audit_group: str, *, strict: str) -> dict:
    major, refocus = strict.split("/")
    return {
        "audit_group": audit_group,
        "variant": audit_group,
        "default_major_peaks_at_0p30": 10,
        "default_refocus_peaks_at_0p30": 9,
        "conservative_major_peaks": int(major),
        "conservative_refocus_peaks": int(refocus),
    }


def _comparison(
    *,
    shell_drop: float,
    radial_drop: float,
    angular_drop: float,
    node_drop: float,
    spread_growth: float,
    strict_loss: float,
    center_shift: float = 0.0,
) -> dict:
    return {
        "strict_major_loss": strict_loss,
        "shell_phase_coherence_drop": shell_drop,
        "radial_phase_coherence_drop": radial_drop,
        "angular_phase_coherence_drop": angular_drop,
        "node_phase_stability_drop": node_drop,
        "return_radial_spread_relative_growth": spread_growth,
        "return_radial_centroid_shift": center_shift,
        "radial_phase_profile_mean_abs_drift_cycles": 0.02,
    }


if __name__ == "__main__":
    unittest.main()
