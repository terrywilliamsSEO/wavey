"""Boundary emitter models for the lattice."""

from __future__ import annotations

import numpy as np

from .config import DriverConfig, SimulationConfig


VALID_SIDES = {"left", "right", "top", "bottom"}
VALID_SOURCE_NORMALIZATIONS = {"per_cell", "per_length", "constant_total_work", "constant_boundary_flux"}
VALID_DRIVE_LOCATIONS = {"boundary", "core_node", "core_region", "annulus"}
VALID_CORE_DRIVE_MODES = {"burst", "impulse", "chirp", "continuous"}
VALID_CORE_PHASE_MODES = {"uniform", "rotating"}
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


class CoreDriver:
    """Adds direct forcing to core or annular physical regions."""

    def __init__(self, shape: tuple[int, int], sim_config: SimulationConfig, masks: object):
        self.shape = shape
        self.config = sim_config
        if sim_config.drive_location not in VALID_DRIVE_LOCATIONS:
            raise ValueError(
                f"Unsupported drive_location: {sim_config.drive_location}. "
                f"Expected one of {sorted(VALID_DRIVE_LOCATIONS)}"
            )
        if sim_config.core_drive_mode not in VALID_CORE_DRIVE_MODES:
            raise ValueError(
                f"Unsupported core_drive_mode: {sim_config.core_drive_mode}. "
                f"Expected one of {sorted(VALID_CORE_DRIVE_MODES)}"
            )
        if sim_config.core_drive_phase_mode not in VALID_CORE_PHASE_MODES:
            raise ValueError(
                f"Unsupported core_drive_phase_mode: {sim_config.core_drive_phase_mode}. "
                f"Expected one of {sorted(VALID_CORE_PHASE_MODES)}"
            )
        self.coverage_weights = self._build_coverage_weights(shape, sim_config, masks)
        self.mask = self.coverage_weights > EPSILON
        self.effective_driven_area = float(np.sum(self.coverage_weights) * sim_config.cell_area)
        self.fractional_coverage_sum = float(np.sum(self.coverage_weights))
        self.normalization_scale = 1.0
        self.phase_map = self._build_phase_map(shape, sim_config)

    @staticmethod
    def _build_coverage_weights(
        shape: tuple[int, int],
        config: SimulationConfig,
        masks: object,
    ) -> np.ndarray:
        if config.drive_location == "boundary":
            return np.zeros(shape, dtype=float)

        if config.drive_location == "core_node":
            weights = np.zeros(shape, dtype=float)
            weights[shape[0] // 2, shape[1] // 2] = 1.0
            return weights

        if config.drive_location == "annulus":
            if config.fixed_domain:
                inner = (
                    float(config.core_drive_inner_radius_physical)
                    if config.core_drive_inner_radius_physical is not None
                    else config.effective_defect_radius + 1.0
                )
                outer = (
                    float(config.core_drive_outer_radius_physical)
                    if config.core_drive_outer_radius_physical is not None
                    else config.effective_defect_radius + max(3.0, config.effective_defect_radius * 0.8)
                )
                weights = _fractional_radial_band_weights(shape, config, inner, outer)
                return _apply_angular_sector(weights, shape, config)
            return np.asarray(getattr(masks, "ring"), dtype=float)

        if config.drive_location == "core_region":
            if config.fixed_domain:
                weights = _fractional_radial_region_weights(shape, config, config.effective_core_drive_radius)
                return _apply_angular_sector(weights, shape, config)
            weights = np.asarray(getattr(masks, "radius") <= config.effective_core_drive_radius, dtype=float)
            return _apply_angular_sector(weights, shape, config)

        raise AssertionError(f"Unhandled drive_location: {config.drive_location}")

    @staticmethod
    def _build_phase_map(shape: tuple[int, int], config: SimulationConfig) -> np.ndarray:
        if config.core_drive_phase_mode == "uniform":
            return np.full(shape, config.core_drive_phase, dtype=float)
        if config.core_drive_phase_mode != "rotating":
            raise ValueError(f"Unsupported core_drive_phase_mode: {config.core_drive_phase_mode}")

        rows, cols = np.indices(shape, dtype=float)
        center_row = (shape[0] - 1) / 2.0
        center_col = (shape[1] - 1) / 2.0
        if config.fixed_domain:
            theta = np.arctan2((rows - center_row) * config.dy, (cols - center_col) * config.dx)
        else:
            theta = np.arctan2(rows - center_row, cols - center_col)
        return config.core_drive_phase + float(config.core_drive_rotating_phase_winding) * theta

    def envelope(self, time: float) -> float:
        mode = self.config.core_drive_mode
        cutoff = self.config.effective_core_drive_cutoff_time
        if mode == "impulse":
            return 1.0 if time < max(self.config.dt, EPSILON) else 0.0
        if cutoff is not None and time > cutoff:
            return 0.0
        if mode == "continuous":
            return 1.0
        if mode in {"burst", "chirp"}:
            duration = cutoff if cutoff is not None and cutoff > 0.0 else 1.0 / max(
                self.config.effective_core_drive_frequency, EPSILON
            )
            phase = np.clip(time / duration, 0.0, 1.0)
            return float(np.sin(np.pi * phase) ** 2)
        raise ValueError(f"Unsupported core_drive_mode: {mode}")

    def _base_angle(self, time: float) -> float:
        mode = self.config.core_drive_mode
        if mode == "impulse":
            return 0.0
        frequency = max(self.config.effective_core_drive_frequency, EPSILON)
        if mode == "chirp":
            cutoff = self.config.effective_core_drive_cutoff_time
            duration = cutoff if cutoff is not None and cutoff > 0.0 else max(time, self.config.dt)
            target_frequency = max(frequency * 2.0, frequency)
            sweep_rate = (target_frequency - frequency) / duration
            return float(2.0 * np.pi * (frequency * time + 0.5 * sweep_rate * time * time))
        return float(2.0 * np.pi * frequency * time)

    def force(self, time: float) -> np.ndarray:
        out = np.zeros(self.shape, dtype=float)
        if self.config.drive_location == "boundary" or self.config.core_drive_amplitude == 0.0:
            return out
        envelope = self.envelope(time)
        if envelope == 0.0 or not np.any(self.mask):
            return out
        phase = self._base_angle(time) + self.phase_map[self.mask]
        if self.config.core_drive_mode == "impulse":
            waveform = np.cos(phase)
        else:
            waveform = np.sin(phase)
        out[self.mask] = (
            self.config.core_drive_amplitude
            * self.normalization_scale
            * envelope
            * waveform
            * self.coverage_weights[self.mask]
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


def _fractional_radial_region_weights(
    shape: tuple[int, int],
    config: SimulationConfig,
    radius: float,
    *,
    samples_per_axis: int = 5,
) -> np.ndarray:
    return _fractional_radial_band_weights(shape, config, 0.0, radius, samples_per_axis=samples_per_axis)


def _fractional_radial_band_weights(
    shape: tuple[int, int],
    config: SimulationConfig,
    inner_radius: float,
    outer_radius: float,
    *,
    samples_per_axis: int = 5,
) -> np.ndarray:
    weights = np.zeros(shape, dtype=float)
    if outer_radius <= inner_radius or outer_radius <= 0.0:
        return weights

    offsets = (np.arange(samples_per_axis, dtype=float) + 0.5) / samples_per_axis - 0.5
    rows, cols = np.indices(shape, dtype=float)
    center_row = (shape[0] - 1) / 2.0
    center_col = (shape[1] - 1) / 2.0
    hit_count = np.zeros(shape, dtype=float)
    for row_offset in offsets:
        for col_offset in offsets:
            y = (rows + row_offset - center_row) * config.dy
            x = (cols + col_offset - center_col) * config.dx
            radius = np.sqrt(y**2 + x**2)
            hit_count += ((radius >= inner_radius) & (radius <= outer_radius)).astype(float)
    weights = hit_count / float(samples_per_axis * samples_per_axis)
    return np.clip(weights, 0.0, 1.0)


def _apply_angular_sector(weights: np.ndarray, shape: tuple[int, int], config: SimulationConfig) -> np.ndarray:
    width = config.core_drive_angle_width
    if width is None:
        return weights
    width = float(width)
    if width <= 0.0:
        return np.zeros_like(weights, dtype=float)
    if width >= 2.0 * np.pi:
        return weights

    center = float(config.core_drive_angle_center or 0.0)
    rows, cols = np.indices(shape, dtype=float)
    center_row = (shape[0] - 1) / 2.0
    center_col = (shape[1] - 1) / 2.0
    if config.fixed_domain:
        theta = np.arctan2((rows - center_row) * config.dy, (cols - center_col) * config.dx)
    else:
        theta = np.arctan2(rows - center_row, cols - center_col)
    delta = np.angle(np.exp(1j * (theta - center)))
    return np.where(np.abs(delta) <= 0.5 * width, weights, 0.0)
