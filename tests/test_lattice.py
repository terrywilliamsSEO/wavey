"""Numerical sanity tests for the lattice engine."""

from __future__ import annotations

import unittest

import numpy as np

from simulation.config import DefectConfig, DriverConfig, SimulationConfig
from simulation.lattice import Lattice2D


def quiet_config(*, damping: float) -> SimulationConfig:
    return SimulationConfig(
        grid_size=21,
        steps=400,
        dt=0.01,
        base_stiffness=1.0,
        coupling_strength=0.7,
        global_damping=damping,
        nonlinear_strength=0.0,
        defect=DefectConfig(
            radius=2,
            stiffness_multiplier=1.0,
            damping_multiplier=1.0,
            coupling_multiplier=1.0,
            nonlinear_strength=0.0,
        ),
        driver=DriverConfig(amplitude=0.0, drive_cutoff_time=0.0),
    )


class LatticeSanityTests(unittest.TestCase):
    def test_no_drive_no_damping_energy_is_bounded(self) -> None:
        config = quiet_config(damping=0.0)
        lattice = Lattice2D(config)
        lattice.u[config.grid_size // 2, config.grid_size // 2] = 0.2

        energies = []
        for step in range(config.steps):
            energies.append(float(np.sum(lattice.energy_density())))
            lattice.step(step * config.dt, config.dt)

        initial = energies[0]
        span = max(energies) - min(energies)
        final_drift = abs(energies[-1] - initial)

        self.assertGreater(initial, 0.0)
        self.assertLess(span / initial, 0.03)
        self.assertLess(final_drift / initial, 0.01)

    def test_damping_reduces_total_energy(self) -> None:
        config = quiet_config(damping=0.06)
        config.dt = 0.02
        config.steps = 200
        lattice = Lattice2D(config)
        lattice.u[config.grid_size // 2, config.grid_size // 2] = 0.2

        energies = []
        for step in range(config.steps):
            energies.append(float(np.sum(lattice.energy_density())))
            lattice.step(step * config.dt, config.dt)

        self.assertLess(energies[-1], energies[0] * 0.85)
        self.assertLessEqual(max(energies), energies[0] * 1.001)

    def test_defect_region_modifies_local_properties(self) -> None:
        config = SimulationConfig(
            grid_size=15,
            base_stiffness=2.0,
            coupling_strength=1.4,
            global_damping=0.1,
            nonlinear_strength=0.03,
            defect=DefectConfig(
                radius=2,
                stiffness_multiplier=0.5,
                damping_multiplier=0.25,
                coupling_multiplier=0.75,
                nonlinear_strength=0.2,
            ),
            driver=DriverConfig(amplitude=0.0),
        )
        lattice = Lattice2D(config)
        center = config.grid_size // 2
        corner = (0, 0)

        self.assertTrue(lattice.masks.defect[center, center])
        self.assertFalse(lattice.masks.defect[corner])
        self.assertAlmostEqual(lattice.stiffness[center, center], 1.0)
        self.assertAlmostEqual(lattice.damping[center, center], 0.025)
        self.assertAlmostEqual(lattice.coupling[center, center], 1.05)
        self.assertAlmostEqual(lattice.nonlinear[center, center], 0.23)
        self.assertAlmostEqual(lattice.stiffness[corner], 2.0)
        self.assertAlmostEqual(lattice.damping[corner], 0.1)
        self.assertAlmostEqual(lattice.coupling[corner], 1.4)
        self.assertAlmostEqual(lattice.nonlinear[corner], 0.03)

    def test_sponge_boundary_increases_edge_damping_without_touching_center_defect(self) -> None:
        config = SimulationConfig(
            grid_size=21,
            global_damping=0.1,
            boundary_mode="sponge",
            boundary_damping_width=4,
            boundary_damping_strength=0.2,
            defect=DefectConfig(
                radius=2,
                stiffness_multiplier=1.0,
                damping_multiplier=0.25,
                coupling_multiplier=1.0,
                nonlinear_strength=0.0,
            ),
            driver=DriverConfig(amplitude=0.0),
        )
        lattice = Lattice2D(config)
        center = config.grid_size // 2

        self.assertAlmostEqual(lattice.damping[center, center], 0.025)
        self.assertAlmostEqual(lattice.damping[0, 0], 0.3)
        self.assertGreater(lattice.damping[1, center], lattice.damping[4, center])
        self.assertAlmostEqual(lattice.damping[4, center], 0.1)


if __name__ == "__main__":
    unittest.main()
