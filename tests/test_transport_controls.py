"""Tests for targeted source-geometry transport controls."""

from __future__ import annotations

import math
import unittest

import numpy as np

from simulation.config import DefectConfig, DriverConfig, SimulationConfig, simulation_config_from_dict
from simulation.lattice import Lattice2D
from simulation.transport_controls import classify_transport_controls


class TransportControlTests(unittest.TestCase):
    def test_direct_drive_geometry_config_parses_flat_options(self) -> None:
        config = simulation_config_from_dict(
            {
                "drive_location": "annulus",
                "core_drive_phase_mode": "rotating",
                "core_drive_rotating_phase_winding": 4,
                "core_drive_inner_radius_physical": 5.5,
                "core_drive_outer_radius_physical": 8.5,
                "core_drive_angle_center": 0.0,
                "core_drive_angle_width": math.pi / 2.0,
            }
        )

        self.assertEqual(config.drive_location, "annulus")
        self.assertEqual(config.core_drive_phase_mode, "rotating")
        self.assertEqual(config.core_drive_rotating_phase_winding, 4)
        self.assertAlmostEqual(config.core_drive_inner_radius_physical or 0.0, 5.5)
        self.assertAlmostEqual(config.core_drive_outer_radius_physical or 0.0, 8.5)
        self.assertAlmostEqual(config.core_drive_angle_width or 0.0, math.pi / 2.0)

    def test_annulus_sector_is_smaller_than_full_annulus(self) -> None:
        full = _annulus_config()
        sector = _annulus_config()
        sector.core_drive_angle_center = 0.0
        sector.core_drive_angle_width = math.pi / 2.0

        full_lattice = Lattice2D(full)
        sector_lattice = Lattice2D(sector)

        self.assertGreater(full_lattice.core_driver.effective_driven_area, 0.0)
        self.assertGreater(sector_lattice.core_driver.effective_driven_area, 0.0)
        self.assertLess(sector_lattice.core_driver.effective_driven_area, full_lattice.core_driver.effective_driven_area)

    def test_rotating_annulus_phase_varies_spatially(self) -> None:
        config = _annulus_config()
        config.core_drive_phase_mode = "rotating"
        config.core_drive_rotating_phase_winding = 4
        lattice = Lattice2D(config)

        force = lattice.core_force(0.3)
        active_force = force[lattice.core_driver.mask]

        self.assertGreater(active_force.size, 0)
        self.assertGreater(float(np.std(active_force)), 0.0)

    def test_transport_classification_detects_annulus_success(self) -> None:
        rows = [
            _row("boundary_reference_63", "boundary", retention=0.85, period=3.0, radial_sim=1.0, frame_sim=1.0),
            _row("annulus_near_defect_63", "annulus", retention=0.35, period=3.1, radial_sim=0.7, frame_sim=0.6),
        ]

        result = classify_transport_controls(rows)

        self.assertEqual(result["label"], "annulus_transport_supported")


def _annulus_config() -> SimulationConfig:
    return SimulationConfig(
        grid_size=41,
        steps=80,
        dt=0.04,
        fixed_domain=True,
        domain_width=40.0,
        domain_height=40.0,
        boundary_mode="sponge",
        boundary_damping_width=6,
        boundary_damping_width_physical=6.0,
        boundary_damping_strength=0.08,
        drive_location="annulus",
        core_drive_inner_radius_physical=6.0,
        core_drive_outer_radius_physical=9.0,
        core_drive_frequency=0.92,
        core_drive_amplitude=0.4,
        core_drive_mode="burst",
        core_drive_cutoff_time=16.0,
        defect=DefectConfig(radius=5, radius_physical=5.0),
        driver=DriverConfig(amplitude=0.0, drive_cutoff_time=16.0),
    )


def _row(
    variant: str,
    drive_location: str,
    *,
    retention: float,
    period: float,
    radial_sim: float,
    frame_sim: float,
) -> dict:
    return {
        "variant": variant,
        "drive_location": drive_location,
        "breathing_detected_after_cutoff": True,
        "diagnostic_envelope_period": 3.0 if drive_location == "boundary" else period,
        "breathing_period_after_cutoff": period,
        "post_cutoff_retention": retention,
        "radial_profile_similarity_to_boundary_reference": radial_sim,
        "best_frame_similarity_to_boundary_reference": frame_sim,
        "m4_strength_after_cutoff": 0.2,
    }


if __name__ == "__main__":
    unittest.main()
