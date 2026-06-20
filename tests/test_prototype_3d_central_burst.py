import unittest

from simulation.config import DefectConfig, DriverConfig, SimulationConfig
from simulation.prototype_3d_central_burst import (
    CentralBurst3DOptions,
    _variant_plan,
    classify_central_burst,
)


class CentralBurst3DTests(unittest.TestCase):
    def test_variant_plan_is_firewalled_central_ladder(self) -> None:
        options = CentralBurst3DOptions(
            frequencies=(0.92, 1.84),
            energy_labels=("low", "high"),
            burst_acceleration_scales=(0.05, 0.35),
        )

        variants = _variant_plan(_base_config(), options)

        self.assertEqual(len(variants), 4)
        for config in variants:
            self.assertEqual(config.grid_size, 41)
            self.assertEqual(config.drive_location, "core")
            self.assertEqual(config.drive_amplitude, 0.0)
            self.assertEqual(config.defect_stiffness_multiplier, 1.0)
            self.assertEqual(config.defect_damping_multiplier, 1.0)
            self.assertEqual(config.defect_coupling_multiplier, 1.0)
            self.assertIsNone(config.second_pulse_center_time)
            self.assertEqual(config.second_pulse_duration, 0.0)
            self.assertFalse(config.resonator_enabled)

    def test_threshold_candidate_requires_half_dt_survival(self) -> None:
        rows = [
            _row("low", major=1, refocus=0, retention=0.02),
            _row("medium", major=2, refocus=1, retention=0.10),
            _row("high", major=3, refocus=2, retention=0.20),
            _row("high", major=3, refocus=2, retention=0.19, dt_variant="half_dt"),
        ]

        result = classify_central_burst(rows, CentralBurst3DOptions())

        self.assertEqual(result["label"], "central_burst_nonlinear_threshold_candidate")
        self.assertTrue(result["checks"]["low_energy_disperses"])
        self.assertTrue(result["checks"]["half_dt_best_check_survives"])

    def test_baseline_returns_without_half_dt_are_dt_sensitive(self) -> None:
        rows = [
            _row("high", major=3, refocus=2, retention=0.20),
            _row("high", major=1, refocus=0, retention=0.05, dt_variant="half_dt"),
        ]

        result = classify_central_burst(rows, CentralBurst3DOptions())

        self.assertEqual(result["label"], "central_burst_dt_sensitive")

    def test_transient_when_no_repeated_returns(self) -> None:
        rows = [
            _row("low", major=1, refocus=0, retention=0.02),
            _row("medium", major=2, refocus=0, retention=0.04),
            _row("high", major=2, refocus=1, retention=0.05),
        ]

        result = classify_central_burst(rows, CentralBurst3DOptions())

        self.assertEqual(result["label"], "central_burst_transient")


def _row(
    energy_label: str,
    *,
    major: int,
    refocus: int,
    retention: float,
    dt_variant: str = "baseline_dt",
) -> dict:
    return {
        "variant": f"{dt_variant}_{energy_label}",
        "dt_variant": dt_variant,
        "energy_label": energy_label,
        "burst_frequency": 3.68,
        "major_peaks_at_0p30": major,
        "refocus_peaks_at_0p30": refocus,
        "strict_major_peaks_at_0p35": major,
        "strict_refocus_peaks_at_0p35": refocus,
        "strict_major_peaks_at_0p40": major,
        "strict_refocus_peaks_at_0p40": refocus,
        "conservative_major_peaks": major,
        "conservative_refocus_peaks": refocus,
        "tail_shell_retention": retention,
        "tail_outer_to_shell_mean": 0.5,
        "shell_exit_detected": False,
        "global_peak_in_outer_window": False,
        "energy_accounting_clean": True,
        "state_stable": True,
        "no_boundary_drive": True,
        "return_timing_regularity": 0.5,
        "dominant_spectral_concentration": 0.5,
        "post_burst_decay": -0.02,
    }


def _base_config() -> SimulationConfig:
    return SimulationConfig(
        grid_size=41,
        steps=100,
        dt=0.04,
        domain_width=40.0,
        base_stiffness=1.0,
        coupling_strength=0.95,
        global_damping=0.02,
        nonlinear_strength=0.08,
        boundary_damping_width=6,
        boundary_damping_width_physical=6.0,
        boundary_damping_strength=0.08,
        defect=DefectConfig(radius=5, radius_physical=5.0),
        driver=DriverConfig(frequency=0.92, amplitude=0.55, drive_cutoff_time=16.0),
    )


if __name__ == "__main__":
    unittest.main()
