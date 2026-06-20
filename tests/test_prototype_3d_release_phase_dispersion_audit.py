import unittest

from simulation.prototype_3d_release_phase_dispersion_audit import (
    ReleasePhaseDispersionAuditOptions,
    classify_release_phase_dispersion_audit,
)


class ReleasePhaseDispersionAuditTests(unittest.TestCase):
    def test_scalable_blur_model_when_same_band_and_blur_is_consistent(self) -> None:
        result = classify_release_phase_dispersion_audit(
            [
                _comparison(
                    same_band=True,
                    strict_loss=2,
                    loose_recovery=4,
                    bandwidth_delta=0.29,
                    tail_shift=1.2,
                    lift_bandwidth_cv=0.004,
                    lift_tail_radius_cv=0.02,
                    spatial_phase=False,
                )
            ],
            ReleasePhaseDispersionAuditOptions(),
        )

        self.assertEqual(result["label"], "scalable_blur_model_supported")
        self.assertEqual(result["checks"]["mechanism_candidate"], "none")

    def test_source_discretization_requires_spatial_phase_frames(self) -> None:
        result = classify_release_phase_dispersion_audit(
            [
                _comparison(
                    same_band=True,
                    strict_loss=2,
                    loose_recovery=4,
                    bandwidth_delta=0.29,
                    tail_shift=1.2,
                    lift_bandwidth_cv=0.004,
                    lift_tail_radius_cv=0.02,
                    source_area_delta=0.18,
                    spatial_phase=True,
                )
            ],
            ReleasePhaseDispersionAuditOptions(),
        )

        self.assertEqual(result["label"], "source_discretization_correction_supported")
        self.assertIn("source", result["checks"]["mechanism_candidate"])

    def test_shell_window_scaling_requires_spatial_phase_frames(self) -> None:
        result = classify_release_phase_dispersion_audit(
            [
                _comparison(
                    same_band=True,
                    strict_loss=2,
                    loose_recovery=4,
                    bandwidth_delta=0.29,
                    tail_shift=1.2,
                    lift_bandwidth_cv=0.004,
                    lift_tail_radius_cv=0.02,
                    shell_width_cell_delta=0.5,
                    spatial_phase=True,
                )
            ],
            ReleasePhaseDispersionAuditOptions(),
        )

        self.assertEqual(result["label"], "shell_window_scaling_supported")

    def test_finite_grid_when_modal_band_not_preserved(self) -> None:
        result = classify_release_phase_dispersion_audit(
            [
                _comparison(
                    same_band=False,
                    strict_loss=2,
                    loose_recovery=1,
                    bandwidth_delta=0.01,
                    tail_shift=0.1,
                    lift_bandwidth_cv=0.004,
                    lift_tail_radius_cv=0.02,
                    concentration_ratio=1.0,
                )
            ],
            ReleasePhaseDispersionAuditOptions(),
        )

        self.assertEqual(result["label"], "finite_grid_resonance_likely")

    def test_no_safe_candidate_when_blur_is_not_consistent(self) -> None:
        result = classify_release_phase_dispersion_audit(
            [
                _comparison(
                    same_band=True,
                    strict_loss=2,
                    loose_recovery=4,
                    bandwidth_delta=0.29,
                    tail_shift=1.2,
                    lift_bandwidth_cv=0.20,
                    lift_tail_radius_cv=0.15,
                    spatial_phase=False,
                )
            ],
            ReleasePhaseDispersionAuditOptions(),
        )

        self.assertEqual(result["label"], "no_safe_next_candidate")


def _comparison(
    *,
    same_band: bool,
    strict_loss: float,
    loose_recovery: float,
    bandwidth_delta: float,
    tail_shift: float,
    lift_bandwidth_cv: float,
    lift_tail_radius_cv: float,
    concentration_ratio: float = 0.9,
    source_area_delta: float = 0.0,
    source_phase_delta: float = 0.0,
    source_width_cell_delta: float = 0.0,
    shell_width_cell_delta: float = 0.0,
    shell_width_physical_delta: float = 0.0,
    spatial_phase: bool = False,
) -> dict:
    return {
        "same_modal_band": same_band,
        "strict_major_loss": strict_loss,
        "lift_loose_to_strict_major_recovery": loose_recovery,
        "spectral_bandwidth_relative_delta": bandwidth_delta,
        "tail_radius_shift": tail_shift,
        "lift_bandwidth_cv": lift_bandwidth_cv,
        "lift_tail_radius_cv": lift_tail_radius_cv,
        "proof_to_lift_concentration_ratio": concentration_ratio,
        "source_effective_area_relative_delta": source_area_delta,
        "source_phase_strength_delta": source_phase_delta,
        "source_width_in_dx_relative_delta": source_width_cell_delta,
        "shell_width_in_dx_relative_delta": shell_width_cell_delta,
        "shell_window_width_physical_relative_delta": shell_width_physical_delta,
        "true_spatial_phase_frames_available": spatial_phase,
    }


if __name__ == "__main__":
    unittest.main()
