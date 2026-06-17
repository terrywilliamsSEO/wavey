"""Boundary emitter models for the lattice."""

from __future__ import annotations

import numpy as np

from .config import DriverConfig, SimulationConfig


VALID_SIDES = {"left", "right", "top", "bottom"}
VALID_SOURCE_NORMALIZATIONS = {"per_cell", "per_length", "constant_total_work", "constant_boundary_flux"}
EPSILON = 1e-12


class BoundaryDriver:
    """Adds external forcing to selected lattice boundaries."""

    def __init__(self, shape: tuple[int, int], config: DriverConfig, sim_config: SimulationConfig | None = None):
        self.shape = shape
        self.config = config
        self.sim_config = sim_config
        if config.source_normalization not in VALID_SOURCE_NORMALIZATIONS:
            raise ValueError(
                "Unsupported source_normalization: "
                f"{config.source_normalization}. Expected one of {sorted(VALID_SOURCE_NORMALIZATIONS)}"
            )
        self.coverage_weights = self._build_coverage_weights(shape, config, sim_config)
        self.mask = self.coverage_weights > EPSILON
        self.normalization_scale = self._normalization_scale(config, sim_config, self.coverage_weights)
        self.effective_driven_area = self._effective_driven_area(sim_config, self.coverage_weights)
        self.effective_driven_length = self._effective_driven_length(config, sim_config, self.coverage_weights)
        self.physical_boundary_length = self._physical_boundary_length(config.sides, sim_config)
        self.phase_map = self._build_phase_map(shape, config, sim_config)

    @staticmethod
    def _build_mask(
        shape: tuple[int, int],
        sides: tuple[str, ...],
        sim_config: SimulationConfig | None = None,
    ) -> np.ndarray:
        if sim_config is None:
            driver_config = DriverConfig(sides=sides)
        else:
            driver_config = DriverConfig(
                sides=sides,
                emitter_width=sim_config.driver.emitter_width,
                emitter_width_physical=sim_config.driver.emitter_width_physical,
                source_normalization=sim_config.driver.source_normalization,
            )
        return BoundaryDriver._build_coverage_weights(shape, driver_config, sim_config) > EPSILON

    @staticmethod
    def _build_coverage_weights(
        shape: tuple[int, int],
        config: DriverConfig,
        sim_config: SimulationConfig | None = None,
    ) -> np.ndarray:
        unknown = set(config.sides) - VALID_SIDES
        if unknown:
            raise ValueError(f"Unknown emitter side(s): {sorted(unknown)}")

        if sim_config is not None and sim_config.fixed_domain and config.source_normalization != "per_cell":
            return BoundaryDriver._build_fractional_weights(shape, config.sides, sim_config)
        return BoundaryDriver._build_hard_weights(shape, config.sides, sim_config)

    @staticmethod
    def _build_hard_weights(
        shape: tuple[int, int],
        sides: tuple[str, ...],
        sim_config: SimulationConfig | None = None,
    ) -> np.ndarray:
        unknown = set(sides) - VALID_SIDES
        if unknown:
            raise ValueError(f"Unknown emitter side(s): {sorted(unknown)}")

        weights = np.zeros(shape, dtype=float)
        if sim_config is not None and sim_config.fixed_domain:
            rows, cols = np.indices(shape, dtype=float)
            width = sim_config.effective_emitter_width
            if "left" in sides:
                weights = np.maximum(weights, (cols * sim_config.dx < width).astype(float))
            if "right" in sides:
                weights = np.maximum(weights, ((shape[1] - 1 - cols) * sim_config.dx < width).astype(float))
            if "top" in sides:
                weights = np.maximum(weights, (rows * sim_config.dy < width).astype(float))
            if "bottom" in sides:
                weights = np.maximum(weights, ((shape[0] - 1 - rows) * sim_config.dy < width).astype(float))
            return weights

        width = max(1, int(sim_config.driver.emitter_width if sim_config is not None else 1))
        if "left" in sides:
            weights[:, :width] = 1.0
        if "right" in sides:
            weights[:, -width:] = 1.0
        if "top" in sides:
            weights[:width, :] = 1.0
        if "bottom" in sides:
            weights[-width:, :] = 1.0
        return weights

    @staticmethod
    def _build_fractional_weights(
        shape: tuple[int, int],
        sides: tuple[str, ...],
        sim_config: SimulationConfig,
    ) -> np.ndarray:
        unknown = set(sides) - VALID_SIDES
        if unknown:
            raise ValueError(f"Unknown emitter side(s): {sorted(unknown)}")

        rows, cols = np.indices(shape, dtype=float)
        width = sim_config.effective_emitter_width
        weights = np.zeros(shape, dtype=float)
        if "left" in sides:
            weights = _coverage_union(weights, _cell_interval_coverage(cols * sim_config.dx, sim_config.dx, width))
        if "right" in sides:
            right_distance = (shape[1] - 1 - cols) * sim_config.dx
            weights = _coverage_union(weights, _cell_interval_coverage(right_distance, sim_config.dx, width))
        if "top" in sides:
            weights = _coverage_union(weights, _cell_interval_coverage(rows * sim_config.dy, sim_config.dy, width))
        if "bottom" in sides:
            bottom_distance = (shape[0] - 1 - rows) * sim_config.dy
            weights = _coverage_union(weights, _cell_interval_coverage(bottom_distance, sim_config.dy, width))
        return np.clip(weights, 0.0, 1.0)

    @staticmethod
    def _normalization_scale(
        config: DriverConfig,
        sim_config: SimulationConfig | None,
        coverage_weights: np.ndarray,
    ) -> float:
        if sim_config is None or not sim_config.fixed_domain or config.source_normalization == "per_cell":
            return 1.0
        if config.source_normalization in {"per_length", "constant_boundary_flux", "constant_total_work"}:
            area = BoundaryDriver._effective_driven_area(sim_config, coverage_weights)
            length = BoundaryDriver._physical_boundary_length(config.sides, sim_config)
            if area <= EPSILON or length <= EPSILON:
                return 1.0
            return length / area
        return 1.0

    @staticmethod
    def _effective_driven_area(sim_config: SimulationConfig | None, coverage_weights: np.ndarray) -> float:
        cell_area = sim_config.cell_area if sim_config is not None else 1.0
        return float(np.sum(coverage_weights) * cell_area)

    @staticmethod
    def _effective_driven_length(
        config: DriverConfig,
        sim_config: SimulationConfig | None,
        coverage_weights: np.ndarray,
    ) -> float:
        if sim_config is None:
            return float(np.sum(coverage_weights))
        width = sim_config.effective_emitter_width
        if width <= EPSILON:
            return 0.0
        return BoundaryDriver._effective_driven_area(sim_config, coverage_weights) / width

    @staticmethod
    def _physical_boundary_length(sides: tuple[str, ...], sim_config: SimulationConfig | None) -> float:
        if sim_config is None:
            return 0.0
        length = 0.0
        if "left" in sides:
            length += sim_config.physical_domain_height
        if "right" in sides:
            length += sim_config.physical_domain_height
        if "top" in sides:
            length += sim_config.physical_domain_width
        if "bottom" in sides:
            length += sim_config.physical_domain_width
        return float(length)

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
        weights = self.coverage_weights[self.mask]
        out[self.mask] = (
            self.config.amplitude
            * envelope
            * self.normalization_scale
            * weights
            * np.sin(omega_t + self.phase_map[self.mask])
        )
        return out


def _cell_interval_coverage(distance: np.ndarray, spacing: float, width: float) -> np.ndarray:
    if spacing <= EPSILON or width <= EPSILON:
        return np.zeros_like(distance, dtype=float)
    lower = np.maximum(distance - 0.5 * spacing, 0.0)
    upper = distance + 0.5 * spacing
    overlap = np.maximum(0.0, np.minimum(upper, width) - lower)
    return np.clip(overlap / spacing, 0.0, 1.0)


def _coverage_union(existing: np.ndarray, new: np.ndarray) -> np.ndarray:
    return 1.0 - (1.0 - existing) * (1.0 - new)
