"""Boundary emitter models for the lattice."""

from __future__ import annotations

import numpy as np

from .config import DriverConfig, SimulationConfig


VALID_SIDES = {"left", "right", "top", "bottom"}


class BoundaryDriver:
    """Adds external forcing to selected lattice boundaries."""

    def __init__(self, shape: tuple[int, int], config: DriverConfig, sim_config: SimulationConfig | None = None):
        self.shape = shape
        self.config = config
        self.sim_config = sim_config
        self.mask = self._build_mask(shape, config.sides, sim_config)
        self.phase_map = self._build_phase_map(shape, config, sim_config)

    @staticmethod
    def _build_mask(
        shape: tuple[int, int],
        sides: tuple[str, ...],
        sim_config: SimulationConfig | None = None,
    ) -> np.ndarray:
        unknown = set(sides) - VALID_SIDES
        if unknown:
            raise ValueError(f"Unknown emitter side(s): {sorted(unknown)}")

        mask = np.zeros(shape, dtype=bool)
        if sim_config is not None and sim_config.fixed_domain:
            rows, cols = np.indices(shape, dtype=float)
            width = sim_config.effective_emitter_width
            if "left" in sides:
                mask |= cols * sim_config.dx < width
            if "right" in sides:
                mask |= (shape[1] - 1 - cols) * sim_config.dx < width
            if "top" in sides:
                mask |= rows * sim_config.dy < width
            if "bottom" in sides:
                mask |= (shape[0] - 1 - rows) * sim_config.dy < width
            return mask

        width = max(1, int(sim_config.driver.emitter_width if sim_config is not None else 1))
        if "left" in sides:
            mask[:, :width] = True
        if "right" in sides:
            mask[:, -width:] = True
        if "top" in sides:
            mask[:width, :] = True
        if "bottom" in sides:
            mask[-width:, :] = True
        return mask

    @staticmethod
    def _build_phase_map(
        shape: tuple[int, int],
        config: DriverConfig,
        sim_config: SimulationConfig | None = None,
    ) -> np.ndarray:
        if config.phase_mode == "uniform":
            return np.full(shape, config.phase_offset, dtype=float)
        if config.phase_mode != "rotating":
            raise ValueError(f"Unsupported phase_mode: {config.phase_mode}")

        rows, cols = np.indices(shape, dtype=float)
        cy = (shape[0] - 1) / 2.0
        cx = (shape[1] - 1) / 2.0
        if sim_config is not None and sim_config.fixed_domain:
            theta = np.arctan2((rows - cy) * sim_config.dy, (cols - cx) * sim_config.dx)
        else:
            theta = np.arctan2(rows - cy, cols - cx)
        return config.phase_offset + config.rotating_phase_winding * theta

    def envelope(self, time: float) -> float:
        cutoff = self.config.drive_cutoff_time
        if cutoff is not None and time > cutoff:
            return 0.0

        if self.config.mode == "continuous":
            return 1.0

        if self.config.mode == "pulsed":
            duration = cutoff if cutoff is not None and cutoff > 0 else 1.0 / max(self.config.frequency, 1e-9)
            phase = np.clip(time / duration, 0.0, 1.0)
            return float(np.sin(np.pi * phase) ** 2)

        raise ValueError(f"Unsupported driver mode: {self.config.mode}")

    def force(self, time: float) -> np.ndarray:
        out = np.zeros(self.shape, dtype=float)
        envelope = self.envelope(time)
        if envelope == 0.0 or self.config.amplitude == 0.0:
            return out

        omega_t = 2.0 * np.pi * self.config.frequency * time
        out[self.mask] = (
            self.config.amplitude
            * envelope
            * np.sin(omega_t + self.phase_map[self.mask])
        )
        return out
