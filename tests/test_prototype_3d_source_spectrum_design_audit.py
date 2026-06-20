import unittest

from simulation.prototype_3d_source_spectrum_design_audit import (
    SourceSpectrumDesignAuditOptions,
    classify_source_spectrum_design_audit,
)


class SourceSpectrumDesignAuditTests(unittest.TestCase):
    def test_supports_candidate_when_hard_sidebands_are_plausible_and_smooth_reduces_them(self) -> None:
        result = classify_source_spectrum_design_audit(
            _summary(
                same_band=True,
                modal_growth=0.29,
                coherence_drop=0.14,
                hard_sideband=0.05,
                smooth_sideband=0.001,
                sideband_reduction=0.98,
                bandwidth_ratio=0.30,
            ),
            SourceSpectrumDesignAuditOptions(),
        )

        self.assertEqual(result["label"], "source_spectrum_narrowing_candidate_supported")

    def test_archives_when_source_sidebands_are_too_small(self) -> None:
        result = classify_source_spectrum_design_audit(
            _summary(
                same_band=True,
                modal_growth=0.29,
                coherence_drop=0.14,
                hard_sideband=0.002,
                smooth_sideband=0.001,
                sideband_reduction=0.50,
                bandwidth_ratio=0.80,
            ),
            SourceSpectrumDesignAuditOptions(),
        )

        self.assertEqual(result["label"], "source_spectrum_not_supported_archive")

    def test_archives_when_smoothing_does_not_reduce_sidebands(self) -> None:
        result = classify_source_spectrum_design_audit(
            _summary(
                same_band=True,
                modal_growth=0.29,
                coherence_drop=0.14,
                hard_sideband=0.05,
                smooth_sideband=0.04,
                sideband_reduction=0.20,
                bandwidth_ratio=0.90,
            ),
            SourceSpectrumDesignAuditOptions(),
        )

        self.assertEqual(result["label"], "source_spectrum_not_supported_archive")

    def test_inconclusive_when_same_band_loss_is_not_established(self) -> None:
        result = classify_source_spectrum_design_audit(
            _summary(
                same_band=False,
                modal_growth=0.29,
                coherence_drop=0.14,
                hard_sideband=0.05,
                smooth_sideband=0.001,
                sideband_reduction=0.98,
                bandwidth_ratio=0.30,
            ),
            SourceSpectrumDesignAuditOptions(),
        )

        self.assertEqual(result["label"], "source_spectrum_inconclusive")


def _summary(
    *,
    same_band: bool,
    modal_growth: float,
    coherence_drop: float,
    hard_sideband: float,
    smooth_sideband: float,
    sideband_reduction: float,
    bandwidth_ratio: float,
) -> dict:
    return {
        "same_modal_band": same_band,
        "observed_modal_bandwidth_relative_delta": modal_growth,
        "strict_major_loss": 2,
        "shell_phase_coherence_drop": coherence_drop,
        "radial_phase_coherence_drop": coherence_drop,
        "angular_phase_coherence_drop": coherence_drop,
        "phase_precompensation_classification": "no_safe_phase_correction",
        "current_source_envelope": "continuous_hard_cutoff",
        "hard_far_sideband_fraction_mean": hard_sideband,
        "smooth_far_sideband_fraction_mean": smooth_sideband,
        "smoothing_far_sideband_reduction_fraction": sideband_reduction,
        "smooth_to_hard_source_bandwidth_ratio": bandwidth_ratio,
        "hard_source_bandwidth_relative_delta_41_to_51": 0.0,
    }


if __name__ == "__main__":
    unittest.main()
