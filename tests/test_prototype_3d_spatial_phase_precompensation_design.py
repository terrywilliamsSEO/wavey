import unittest

from simulation.prototype_3d_spatial_phase_precompensation_design import (
    SpatialPhasePrecompensationDesignOptions,
    classify_spatial_phase_precompensation_design,
)


class SpatialPhasePrecompensationDesignTests(unittest.TestCase):
    def test_supports_candidate_when_low_dimensional_fit_is_stable(self) -> None:
        result = classify_spatial_phase_precompensation_design(
            _summary(samples=160, r2=0.20, peak_std=0.20),
            [],
            SpatialPhasePrecompensationDesignOptions(),
        )

        self.assertEqual(result["label"], "phase_precomp_candidate_supported")
        self.assertTrue(result["checks"]["safe_magnitude"])
        self.assertTrue(result["checks"]["temporally_stable"])

    def test_rejects_when_phase_error_is_not_low_dimensional(self) -> None:
        result = classify_spatial_phase_precompensation_design(
            _summary(samples=160, r2=0.03, peak_std=0.90),
            [
                {
                    "correction": "cell_by_cell_phase_mask",
                    "status": "rejected",
                    "risk_level": "high",
                }
            ],
            SpatialPhasePrecompensationDesignOptions(),
        )

        self.assertEqual(result["label"], "no_safe_phase_correction")

    def test_inconclusive_when_sample_count_is_too_low(self) -> None:
        result = classify_spatial_phase_precompensation_design(
            _summary(samples=12, r2=0.25, peak_std=0.10),
            [],
            SpatialPhasePrecompensationDesignOptions(),
        )

        self.assertEqual(result["label"], "inconclusive_phase_design")

    def test_inconclusive_when_magnitude_exceeds_first_pass_bounds(self) -> None:
        result = classify_spatial_phase_precompensation_design(
            _summary(samples=160, r2=0.20, peak_std=0.20, global_offset=0.80),
            [],
            SpatialPhasePrecompensationDesignOptions(),
        )

        self.assertEqual(result["label"], "inconclusive_phase_design")
        self.assertFalse(result["checks"]["safe_magnitude"])


def _summary(
    *,
    samples: int,
    r2: float,
    peak_std: float,
    global_offset: float = 0.05,
    max_face: float = 0.05,
    cubic_delta: float = 0.05,
    harmonic: float = 0.05,
    release_nudge: float = 0.001,
) -> dict:
    return {
        "matched_sector_samples": samples,
        "low_dimensional_model_r2": r2,
        "per_peak_global_phase_error_std_radians": peak_std,
        "recommended_global_phase_offset_radians": global_offset,
        "recommended_max_face_phase_offset_radians": max_face,
        "recommended_cubic_multiplier_delta": cubic_delta,
        "recommended_angular_harmonic_amplitude_radians": harmonic,
        "recommended_release_phase_nudge_cycles": release_nudge,
        "recommended_cubic_phase_strength_multiplier": 1.0 + cubic_delta,
    }


if __name__ == "__main__":
    unittest.main()
