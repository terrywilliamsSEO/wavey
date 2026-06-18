"""Tests for the tiny 3D shell-breathing prototype."""

from __future__ import annotations

import unittest

import numpy as np

from simulation.prototype_3d import (
    Lattice3D,
    Prototype3DConfig,
    Prototype3DOptions,
    _detect_shell_breathing,
    classify_3d_prototype,
)


class Prototype3DTests(unittest.TestCase):
    def test_boundary_cubic_phase_varies_on_source(self) -> None:
        lattice = Lattice3D(_small_3d_config("boundary", "cubic"))
        phases = lattice.source.phase_map[lattice.source.mask]

        self.assertGreater(phases.size, 0)
        self.assertGreater(float(np.std(phases)), 0.0)

    def test_lattice_step_produces_finite_energy(self) -> None:
        config = _small_3d_config("boundary", "uniform")
        lattice = Lattice3D(config)

        for step in range(5):
            lattice.step(step * config.dt, config.dt)

        self.assertTrue(np.all(np.isfinite(lattice.energy_density())))

    def test_shell_defect_mask_can_leave_center_neutral(self) -> None:
        config = _small_3d_config("boundary", "uniform")
        config.defect_radius = 2.0
        config.defect_inner_radius = 1.0
        lattice = Lattice3D(config)
        center = config.grid_size // 2

        self.assertFalse(bool(lattice.defect_mask[center, center, center]))
        self.assertGreater(int(np.count_nonzero(lattice.defect_mask)), 0)

    def test_defect_only_nonlinearity_applies_inside_defect_mask(self) -> None:
        config = _small_3d_config("boundary", "uniform")
        config.nonlinear_strength = 0.0
        config.defect_nonlinear_strength = 0.7
        lattice = Lattice3D(config)

        self.assertAlmostEqual(float(np.max(lattice.nonlinear_strength[lattice.defect_mask])), 0.7)
        self.assertAlmostEqual(float(np.max(lattice.nonlinear_strength[~lattice.defect_mask])), 0.0)

    def test_shell_breathing_detector_detects_periodic_shell_energy(self) -> None:
        samples = []
        for idx in range(80):
            time = idx * 0.2
            value = 1.0 + 0.4 * np.sin(2.0 * np.pi * time / 2.4)
            samples.append({"time": time, "shell_peak_energy": float(value)})

        result = _detect_shell_breathing(samples, _small_3d_config("boundary", "uniform"))

        self.assertTrue(result["detected"])
        self.assertGreaterEqual(result["cycles"], 3)

    def test_classification_detects_boundary_shell_candidate(self) -> None:
        rows = [
            _row("boundary_cubic_31", "boundary", retention=0.5, radial_sim=1.0, frame_sim=1.0),
            _row("direct_core_31", "core", retention=0.02, radial_sim=0.1, frame_sim=0.1, detected=False),
            _row("direct_shell_31", "shell", retention=0.03, radial_sim=0.2, frame_sim=0.1, detected=False),
            _row("boundary_cubic_stronger_sponge_31", "boundary", retention=0.4, radial_sim=0.8, frame_sim=0.5),
            _row("boundary_cubic_half_dt_31", "boundary", retention=0.4, radial_sim=0.8, frame_sim=0.5),
        ]

        result = classify_3d_prototype(rows, Prototype3DOptions())

        self.assertEqual(result["label"], "boundary_flux_shell_breathing_candidate")


def _small_3d_config(location: str, phase: str) -> Prototype3DConfig:
    return Prototype3DConfig(
        name="test",
        grid_size=9,
        steps=20,
        dt=0.04,
        domain_size=8.0,
        base_stiffness=1.0,
        coupling_strength=0.8,
        global_damping=0.02,
        nonlinear_strength=0.02,
        defect_radius=1.5,
        defect_stiffness_multiplier=0.7,
        defect_damping_multiplier=0.8,
        defect_coupling_multiplier=0.7,
        sponge_width=2.0,
        sponge_strength=0.08,
        drive_frequency=0.9,
        drive_amplitude=0.2,
        drive_cutoff_time=0.6,
        drive_location=location,
        drive_phase_mode=phase,
        shell_inner_radius=2.0,
        shell_outer_radius=3.0,
    )


def _row(
    variant: str,
    drive: str,
    *,
    retention: float,
    radial_sim: float,
    frame_sim: float,
    detected: bool = True,
) -> dict:
    return {
        "variant": variant,
        "drive_location": drive,
        "shell_breathing_detected": detected,
        "post_cutoff_shell_retention": retention,
        "post_cutoff_shell_radius_range": 2.0,
        "radial_similarity_to_reference": radial_sim,
        "best_frame_similarity_to_reference": frame_sim,
    }


if __name__ == "__main__":
    unittest.main()
