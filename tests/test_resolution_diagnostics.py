"""Tests for fixed-domain resolution-sensitivity diagnostics."""

from __future__ import annotations

import unittest

from simulation.resolution_diagnostics import classify_resolution_diagnostics


class ResolutionDiagnosticsClassificationTests(unittest.TestCase):
    def test_coarse_grid_artifact_when_refined_grids_converge(self) -> None:
        result = classify_resolution_diagnostics(
            [
                _row("fixed_domain_grid_41", 41, retention=0.875, period=2.667, radial_peak=10.0),
                _row("fixed_domain_grid_63", 63, retention=0.783, period=2.632, radial_peak=3.75),
                _row("fixed_domain_grid_81", 81, retention=0.716, period=2.993, radial_peak=3.75),
            ],
            _source_rows(0.10, 0.11, 0.10),
            _mask_rows(112.0, 113.0, 112.5),
            [
                _pair("fixed_domain_grid_41", "fixed_domain_grid_63", spatial=0.25, radial=0.20, shift=6.25),
                _pair("fixed_domain_grid_41", "fixed_domain_grid_81", spatial=0.20, radial=0.18, shift=6.25),
                _pair("fixed_domain_grid_63", "fixed_domain_grid_81", spatial=0.62, radial=0.88, shift=0.0),
            ],
        )

        self.assertEqual(result["label"], "coarse_grid_artifact_likely")
        self.assertTrue(result["checks"]["refined_radial_profiles_converge"])
        self.assertTrue(result["checks"]["coarse_peak_differs_from_refined"])

    def test_source_normalization_takes_priority_when_work_varies(self) -> None:
        result = classify_resolution_diagnostics(
            [
                _row("fixed_domain_grid_41", 41, retention=0.875, period=2.667, radial_peak=10.0),
                _row("fixed_domain_grid_63", 63, retention=0.783, period=2.632, radial_peak=3.75),
                _row("fixed_domain_grid_81", 81, retention=0.716, period=2.993, radial_peak=3.75),
            ],
            _source_rows(0.10, 0.20, 0.28),
            _mask_rows(112.0, 113.0, 112.5),
            [_pair("fixed_domain_grid_63", "fixed_domain_grid_81", spatial=0.62, radial=0.88, shift=0.0)],
        )

        self.assertEqual(result["label"], "source_normalization_issue")
        self.assertFalse(result["checks"]["source_work_comparable"])

    def test_true_resolution_sensitive_when_refined_profiles_do_not_converge(self) -> None:
        result = classify_resolution_diagnostics(
            [
                _row("fixed_domain_grid_41", 41, retention=0.90, period=2.7, radial_peak=5.0),
                _row("fixed_domain_grid_63", 63, retention=0.78, period=2.9, radial_peak=7.0),
                _row("fixed_domain_grid_81", 81, retention=0.65, period=3.1, radial_peak=9.0),
            ],
            _source_rows(0.10, 0.11, 0.10),
            _mask_rows(112.0, 113.0, 112.5),
            [
                _pair("fixed_domain_grid_41", "fixed_domain_grid_63", spatial=0.25, radial=0.45, shift=2.0),
                _pair("fixed_domain_grid_63", "fixed_domain_grid_81", spatial=0.22, radial=0.40, shift=2.0),
            ],
        )

        self.assertEqual(result["label"], "true_resolution_sensitive")


def _row(variant: str, grid_size: int, *, retention: float, period: float, radial_peak: float) -> dict:
    return {
        "variant": variant,
        "grid_size": grid_size,
        "retention_score": retention,
        "breathing_detected": True,
        "breathing_period": period,
        "strongest_angular_mode": 4,
        "radial_peak_radius": radial_peak,
    }


def _source_rows(*work_per_length: float) -> list[dict]:
    return [
        {
            "variant": f"fixed_domain_grid_{grid}",
            "injected_work_per_physical_boundary_length": value,
        }
        for grid, value in zip((41, 63, 81), work_per_length)
    ]


def _mask_rows(*core_areas: float) -> list[dict]:
    return [
        {
            "variant": f"fixed_domain_grid_{grid}",
            "defect_physical_area": 78.5,
            "core_physical_area": core_area,
            "sponge_physical_area": 760.0,
            "emitter_physical_area_from_mask": 160.0,
        }
        for grid, core_area in zip((41, 63, 81), core_areas)
    ]


def _pair(first: str, second: str, *, spatial: float, radial: float, shift: float) -> dict:
    return {
        "first_variant": first,
        "second_variant": second,
        "best_spatial_correlation": spatial,
        "best_radial_correlation": radial,
        "tail_radial_correlation": radial,
        "angular_mode_similarity": 0.92,
        "best_radial_peak_shift": shift,
    }


if __name__ == "__main__":
    unittest.main()
