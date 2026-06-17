"""Tests for boundary source geometry and normalization."""

from __future__ import annotations

import unittest

from simulation.config import DriverConfig, SimulationConfig
from simulation.lattice import Lattice2D


class BoundaryDriverNormalizationTests(unittest.TestCase):
    def test_fractional_fixed_domain_source_area_is_resolution_invariant(self) -> None:
        areas = []
        lengths = []
        for grid_size in (41, 63, 81):
            config = _fixed_domain_source_config(grid_size, source_normalization="constant_boundary_flux")
            driver = Lattice2D(config).driver
            areas.append(driver.effective_driven_area)
            lengths.append(driver.effective_driven_length)

        self.assertLess((max(areas) - min(areas)) / (sum(areas) / len(areas)), 0.05)
        self.assertLess((max(lengths) - min(lengths)) / (sum(lengths) / len(lengths)), 0.05)

    def test_legacy_per_cell_keeps_hard_source_mask(self) -> None:
        coarse = Lattice2D(_fixed_domain_source_config(41, source_normalization="per_cell")).driver
        middle = Lattice2D(_fixed_domain_source_config(63, source_normalization="per_cell")).driver
        refined = Lattice2D(_fixed_domain_source_config(81, source_normalization="per_cell")).driver

        self.assertAlmostEqual(coarse.effective_driven_area, 160.0)
        self.assertGreater(middle.effective_driven_area, coarse.effective_driven_area * 1.2)
        self.assertAlmostEqual(refined.effective_driven_area, 158.0)


def _fixed_domain_source_config(grid_size: int, *, source_normalization: str) -> SimulationConfig:
    return SimulationConfig(
        grid_size=grid_size,
        fixed_domain=True,
        domain_width=40.0,
        domain_height=40.0,
        driver=DriverConfig(
            amplitude=0.0,
            emitter_width_physical=1.0,
            source_normalization=source_normalization,
        ),
    )


if __name__ == "__main__":
    unittest.main()
