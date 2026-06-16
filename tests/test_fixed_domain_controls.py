"""Tests for fixed-domain grid-refinement controls."""

from __future__ import annotations

import unittest

from simulation.config import DefectConfig, DriverConfig, SimulationConfig
from simulation.fixed_domain_controls import classify_fixed_domain_grid_results
from simulation.lattice import Lattice2D


class FixedDomainControlTests(unittest.TestCase):
    def test_fixed_domain_refines_dx_without_changing_physical_masks(self) -> None:
        coarse = _fixed_config(41)
        refined = _fixed_config(63)

        self.assertAlmostEqual(coarse.dx, 1.0)
        self.assertAlmostEqual(refined.dx, 40.0 / 62.0)

        coarse_lattice = Lattice2D(coarse)
        refined_lattice = Lattice2D(refined)

        self.assertGreater(refined_lattice.masks.core.sum(), coarse_lattice.masks.core.sum())
        self.assertAlmostEqual(coarse.effective_defect_radius, refined.effective_defect_radius)
        self.assertAlmostEqual(coarse.effective_boundary_damping_width, refined.effective_boundary_damping_width)
        self.assertGreater(refined_lattice.driver.mask.sum(), coarse_lattice.driver.mask.sum())

    def test_fixed_domain_resolution_resistant_classification(self) -> None:
        rows = [
            _row("fixed_domain_grid_41", ratio=0.50, retention=0.86, best_time=48.0, radial_peak=5.0),
            _row("fixed_domain_grid_63", ratio=0.47, retention=0.82, best_time=49.0, radial_peak=5.5),
        ]

        result = classify_fixed_domain_grid_results(rows)

        self.assertEqual(result["label"], "fixed_domain_resolution_resistant")
        self.assertTrue(all(result["checks"].values()))

    def test_resolution_sensitive_when_timing_shifts(self) -> None:
        rows = [
            _row("fixed_domain_grid_41", ratio=0.50, retention=0.86, best_time=48.0, radial_peak=5.0),
            _row("fixed_domain_grid_63", ratio=0.47, retention=0.82, best_time=70.0, radial_peak=5.5),
        ]

        result = classify_fixed_domain_grid_results(rows)

        self.assertEqual(result["label"], "resolution_sensitive")
        self.assertFalse(result["checks"]["best_event_time"])


def _fixed_config(grid_size: int) -> SimulationConfig:
    return SimulationConfig(
        grid_size=grid_size,
        fixed_domain=True,
        domain_width=40.0,
        domain_height=40.0,
        boundary_mode="sponge",
        boundary_damping_width=6,
        boundary_damping_width_physical=6.0,
        defect=DefectConfig(radius=5, radius_physical=5.0),
        core_radius=6,
        core_radius_physical=6.0,
        driver=DriverConfig(amplitude=0.0, emitter_width_physical=1.0),
    )


def _row(
    variant: str,
    *,
    ratio: float,
    retention: float,
    best_time: float,
    radial_peak: float,
) -> dict:
    return {
        "variant": variant,
        "fixed_domain": True,
        "best_energy_well_ratio": ratio,
        "retention_score": retention,
        "best_event_time": best_time,
        "best_core_fraction": 0.34,
        "best_event_radial_peak_radius_physical": radial_peak,
        "best_frame_similarity_to_baseline": 0.7,
        "breathing_detected": True,
        "breathing_period": 2.7,
        "dt_to_hard_limit_ratio": 0.2,
    }


if __name__ == "__main__":
    unittest.main()
