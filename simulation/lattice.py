"""2D coupled oscillator lattice implementation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SimulationConfig
from .drivers import BoundaryDriver


@dataclass
class LatticeMasks:
    defect: np.ndarray
    core: np.ndarray
    outer: np.ndarray
    ring: np.ndarray
    rows: np.ndarray
    cols: np.ndarray
    radius: np.ndarray
    theta: np.ndarray


class Lattice2D:
    """Finite-difference lattice of locally coupled damped oscillators."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.shape = config.shape
        self.u = np.zeros(self.shape, dtype=float)
        self.v = np.zeros(self.shape, dtype=float)
        self.masks = self._build_masks(config)
        self.stiffness = np.full(self.shape, config.base_stiffness, dtype=float)
        self.damping = np.full(self.shape, config.global_damping, dtype=float)
        self.coupling = np.full(self.shape, config.coupling_strength, dtype=float)
        self.nonlinear = np.full(self.shape, config.nonlinear_strength, dtype=float)
        self._apply_defect(config)
        self._apply_boundary_damping(config)
        self.driver = BoundaryDriver(self.shape, config.driver, config)

    @staticmethod
    def _build_masks(config: SimulationConfig) -> LatticeMasks:
        rows, cols = np.indices(config.shape, dtype=float)
        cy = (config.ny - 1) / 2.0
        cx = (config.nx - 1) / 2.0
        if config.fixed_domain:
            y = (rows - cy) * config.dy
            x = (cols - cx) * config.dx
            radius = np.sqrt(y**2 + x**2)
            theta = np.arctan2(y, x)
            defect_radius = config.effective_defect_radius
            core_radius = config.effective_core_radius_value
            ring_margin = 1.0
            ring_width = max(3.0, defect_radius * 0.8)
        else:
            radius = np.sqrt((rows - cy) ** 2 + (cols - cx) ** 2)
            theta = np.arctan2(rows - cy, cols - cx)
            defect_radius = float(config.defect.radius)
            core_radius = float(config.effective_core_radius)
            ring_margin = 1.0
            ring_width = max(3.0, defect_radius * 0.8)
        defect = radius <= defect_radius
        core = radius <= core_radius
        outer = ~core
        ring_inner = defect_radius + ring_margin
        ring_outer = defect_radius + ring_width
        ring = (radius >= ring_inner) & (radius <= ring_outer)
        return LatticeMasks(defect, core, outer, ring, rows, cols, radius, theta)

    def _apply_defect(self, config: SimulationConfig) -> None:
        mask = self.masks.defect
        self.stiffness[mask] *= config.defect.stiffness_multiplier
        self.damping[mask] *= config.defect.damping_multiplier
        self.coupling[mask] *= config.defect.coupling_multiplier
        self.nonlinear[mask] += config.defect.nonlinear_strength

    def _apply_boundary_damping(self, config: SimulationConfig) -> None:
        if config.boundary_mode == "reflective":
            return
        if config.boundary_mode != "sponge":
            raise ValueError(f"Unsupported boundary_mode: {config.boundary_mode}")

        width = config.effective_boundary_damping_width
        strength = float(config.boundary_damping_strength)
        if width <= 0 or strength <= 0.0:
            return

        if config.fixed_domain:
            edge_distance = np.minimum.reduce(
                [
                    self.masks.rows * config.dy,
                    self.masks.cols * config.dx,
                    (config.ny - 1 - self.masks.rows) * config.dy,
                    (config.nx - 1 - self.masks.cols) * config.dx,
                ]
            )
        else:
            edge_distance = np.minimum.reduce(
                [
                    self.masks.rows,
                    self.masks.cols,
                    config.ny - 1 - self.masks.rows,
                    config.nx - 1 - self.masks.cols,
                ]
            )
        zone = edge_distance < width
        ramp = np.zeros(self.shape, dtype=float)
        ramp[zone] = ((width - edge_distance[zone]) / width) ** 2
        self.damping += strength * ramp

    def coupling_force(self) -> np.ndarray:
        """Compute divergence of variable edge-coupling displacement gradients."""

        force = np.zeros_like(self.u)

        dy2 = self.config.dy**2 if self.config.fixed_domain else 1.0
        dx2 = self.config.dx**2 if self.config.fixed_domain else 1.0

        vertical_c = 0.5 * (self.coupling[:-1, :] + self.coupling[1:, :])
        vertical_diff = self.u[1:, :] - self.u[:-1, :]
        force[:-1, :] += vertical_c * vertical_diff / dy2
        force[1:, :] -= vertical_c * vertical_diff / dy2

        horizontal_c = 0.5 * (self.coupling[:, :-1] + self.coupling[:, 1:])
        horizontal_diff = self.u[:, 1:] - self.u[:, :-1]
        force[:, :-1] += horizontal_c * horizontal_diff / dx2
        force[:, 1:] -= horizontal_c * horizontal_diff / dx2

        return force

    def acceleration(self, time: float) -> np.ndarray:
        restoring = -self.stiffness * self.u
        nonlinear = -self.nonlinear * (self.u ** 3)
        damping = -self.damping * self.v
        return restoring + nonlinear + damping + self.coupling_force() + self.driver.force(time)

    def step(self, time: float, dt: float) -> None:
        # Semi-implicit Euler is stable for the small dt values used by the default sweeps.
        self.v += dt * self.acceleration(time)
        self.u += dt * self.v

    def energy_density(self) -> np.ndarray:
        area = self.config.cell_area
        dx2 = self.config.dx**2 if self.config.fixed_domain else 1.0
        dy2 = self.config.dy**2 if self.config.fixed_domain else 1.0

        kinetic = 0.5 * self.v ** 2 * area
        onsite = 0.5 * self.stiffness * self.u ** 2 * area
        nonlinear = 0.25 * self.nonlinear * self.u ** 4 * area
        density = kinetic + onsite + nonlinear

        vertical_c = 0.5 * (self.coupling[:-1, :] + self.coupling[1:, :])
        vertical_e = 0.5 * vertical_c * ((self.u[1:, :] - self.u[:-1, :]) ** 2 / dy2) * area
        density[:-1, :] += 0.5 * vertical_e
        density[1:, :] += 0.5 * vertical_e

        horizontal_c = 0.5 * (self.coupling[:, :-1] + self.coupling[:, 1:])
        horizontal_e = 0.5 * horizontal_c * ((self.u[:, 1:] - self.u[:, :-1]) ** 2 / dx2) * area
        density[:, :-1] += 0.5 * horizontal_e
        density[:, 1:] += 0.5 * horizontal_e

        return density
