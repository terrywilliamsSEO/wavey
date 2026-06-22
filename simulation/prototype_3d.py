"""Tiny 3D lattice prototype for shell-breathing checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import SimulationConfig, save_json


EPSILON = 1e-12


@dataclass(frozen=True)
class Prototype3DOptions:
    """Options for the first tiny 3D prototype pass."""

    output_root: str = "runs"
    grid_size: int = 31
    include_dt_control: bool = True
    include_sponge_control: bool = True
    sample_every: int = 2
    radial_bins: int = 24
    min_shell_retention: float = 0.12
    max_shell_radius_range: float = 8.0
    min_radial_similarity: float = 0.55


@dataclass
class Prototype3DConfig:
    """Internal 3D fixed-domain configuration."""

    name: str
    grid_size: int
    steps: int
    dt: float
    domain_size: float
    base_stiffness: float
    coupling_strength: float
    global_damping: float
    nonlinear_strength: float
    defect_radius: float
    defect_stiffness_multiplier: float
    defect_damping_multiplier: float
    defect_coupling_multiplier: float
    sponge_width: float
    sponge_strength: float
    drive_frequency: float
    drive_amplitude: float
    drive_cutoff_time: float
    drive_location: str
    drive_phase_mode: str
    drive_mode: str = "burst"
    drive_chirp_start_frequency: float | None = None
    drive_chirp_end_frequency: float | None = None
    shell_inner_radius: float | None = None
    shell_outer_radius: float | None = None
    boundary_source_inner_distance: float = 0.0
    boundary_source_width: float | None = None
    exclude_source_from_sponge_damping: bool = False
    boundary_faces: tuple[str, ...] = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
    boundary_face_phase_offsets: dict[str, float] | None = None
    boundary_phase_offset: float = 0.0
    boundary_cubic_phase_sign: float = 1.0
    boundary_face_amplitude_scales: dict[str, float] | None = None
    boundary_patch_u_bins: int = 4
    boundary_patch_v_bins: int = 4
    boundary_patch_phase_offsets: dict[str, float] | None = None
    boundary_patch_amplitude_scales: dict[str, float] | None = None
    boundary_random_phase_seed: int | None = None
    defect_inner_radius: float | None = None
    defect_nonlinear_strength: float | None = None
    second_pulse_center_time: float | None = None
    second_pulse_duration: float = 0.0
    second_pulse_amplitude_scale: float = 1.0
    second_pulse_phase_offset: float = 0.0
    resonator_enabled: bool = False
    resonator_geometry: str = "none"
    resonator_k1: float = 0.0
    resonator_k3: float = 0.0
    resonator_damping: float = 0.0
    resonator_coupling: float = 0.0
    memory_mechanism_profile: str = "none"
    memory_mechanism_strength: float = 0.0
    memory_mechanism_seed: int | None = None
    memory_mechanism_shell_radius: float | None = None
    memory_mechanism_shell_width: float | None = None

    @property
    def dx(self) -> float:
        return self.domain_size / float(max(self.grid_size - 1, 1))

    @property
    def cell_volume(self) -> float:
        return self.dx**3

    @property
    def physical_duration(self) -> float:
        return self.steps * self.dt


class Lattice3D:
    """Small semi-implicit 3D oscillator lattice."""

    def __init__(self, config: Prototype3DConfig):
        self.config = config
        n = config.grid_size
        self.u = np.zeros((n, n, n), dtype=float)
        self.v = np.zeros_like(self.u)
        self.coords = _coordinate_payload(config)
        radius = self.coords["radius"]
        self.source = Source3D(config, self.coords)
        if config.defect_inner_radius is None:
            self.defect_mask = radius <= config.defect_radius
        else:
            self.defect_mask = (radius >= config.defect_inner_radius) & (radius <= config.defect_radius)
        self.core_mask = radius <= config.defect_radius + config.dx
        self.sponge_extra = _sponge_extra(config, self.coords)
        if config.exclude_source_from_sponge_damping and np.any(self.source.mask):
            self.sponge_extra = self.sponge_extra.copy()
            self.sponge_extra[self.source.mask] = 0.0
        self.stiffness = np.full_like(self.u, config.base_stiffness)
        self.damping = np.full_like(self.u, config.global_damping) + self.sponge_extra
        self.coupling_multiplier = np.ones_like(self.u)
        self.nonlinear_strength = np.full_like(self.u, config.nonlinear_strength)
        self.stiffness[self.defect_mask] *= config.defect_stiffness_multiplier
        self.damping[self.defect_mask] *= config.defect_damping_multiplier
        self.coupling_multiplier[self.defect_mask] *= config.defect_coupling_multiplier
        if config.defect_nonlinear_strength is not None:
            self.nonlinear_strength[self.defect_mask] = config.defect_nonlinear_strength
        self._apply_memory_mechanism_profile()
        self.resonator_mask = self._resonator_mask()
        self.resonator_q = np.zeros_like(self.u)
        self.resonator_p = np.zeros_like(self.u)
        self.last_resonator_coupling_power_lattice = 0.0
        self.last_resonator_coupling_power_resonator = 0.0
        self.last_resonator_damping_power = 0.0

    def external_force(self, time: float) -> np.ndarray:
        return self.source.force(time)

    def step(self, time: float, dt: float) -> None:
        lap = _laplacian(self.u, self.config.dx)
        force = self.external_force(time)
        resonator_active = bool(np.any(self.resonator_mask))
        if resonator_active:
            mask = self.resonator_mask
            q_before = self.resonator_q[mask].copy()
            p_before = self.resonator_p[mask].copy()
            u_before = self.u[mask].copy()
            v_before = self.v[mask].copy()
            gamma = self.config.resonator_coupling
            lattice_resonator_force = gamma * (q_before - u_before)
        else:
            lattice_resonator_force = np.asarray([], dtype=float)
        acc = (
            self.config.coupling_strength * self.coupling_multiplier * lap
            - self.stiffness * self.u
            - self.nonlinear_strength * self.u**3
            - self.damping * self.v
            + force
        )
        if resonator_active:
            acc[self.resonator_mask] += lattice_resonator_force
        self.v += dt * acc
        self.u += dt * self.v
        if resonator_active:
            mask = self.resonator_mask
            resonator_force = (
                -self.config.resonator_k1 * q_before
                - self.config.resonator_k3 * q_before**3
                - self.config.resonator_damping * p_before
                - lattice_resonator_force
            )
            self.resonator_p[mask] += dt * resonator_force
            self.resonator_q[mask] += dt * self.resonator_p[mask]
            v_mid = 0.5 * (v_before + self.v[mask])
            p_mid = 0.5 * (p_before + self.resonator_p[mask])
            self.last_resonator_coupling_power_lattice = float(np.sum(lattice_resonator_force * v_mid) * self.config.cell_volume)
            self.last_resonator_coupling_power_resonator = float(np.sum((-lattice_resonator_force) * p_mid) * self.config.cell_volume)
            self.last_resonator_damping_power = float(
                np.sum(self.config.resonator_damping * p_mid**2) * self.config.cell_volume
            )
        else:
            self.last_resonator_coupling_power_lattice = 0.0
            self.last_resonator_coupling_power_resonator = 0.0
            self.last_resonator_damping_power = 0.0

    def energy_density(self) -> np.ndarray:
        neighbor_sum = (
            (_shift_edge(self.u, 1, 0) - self.u) ** 2
            + (_shift_edge(self.u, -1, 0) - self.u) ** 2
            + (_shift_edge(self.u, 1, 1) - self.u) ** 2
            + (_shift_edge(self.u, -1, 1) - self.u) ** 2
            + (_shift_edge(self.u, 1, 2) - self.u) ** 2
            + (_shift_edge(self.u, -1, 2) - self.u) ** 2
        )
        return (
            0.5 * self.v**2
            + 0.5 * self.stiffness * self.u**2
            + 0.25 * self.nonlinear_strength * self.u**4
            + 0.25 * self.config.coupling_strength * neighbor_sum
        ) * self.config.cell_volume

    def resonator_energy_density(self) -> np.ndarray:
        out = np.zeros_like(self.u)
        if not np.any(self.resonator_mask):
            return out
        mask = self.resonator_mask
        q = self.resonator_q[mask]
        p = self.resonator_p[mask]
        out[mask] = (
            0.5 * p**2
            + 0.5 * self.config.resonator_k1 * q**2
            + 0.25 * self.config.resonator_k3 * q**4
        ) * self.config.cell_volume
        return out

    def resonator_coupling_energy_density(self) -> np.ndarray:
        out = np.zeros_like(self.u)
        if not np.any(self.resonator_mask):
            return out
        mask = self.resonator_mask
        delta = self.resonator_q[mask] - self.u[mask]
        out[mask] = 0.5 * self.config.resonator_coupling * delta**2 * self.config.cell_volume
        return out

    def resonator_energy(self) -> float:
        return float(np.sum(self.resonator_energy_density()))

    def resonator_coupling_energy(self) -> float:
        return float(np.sum(self.resonator_coupling_energy_density()))

    def _resonator_mask(self) -> np.ndarray:
        if not self.config.resonator_enabled:
            return np.zeros_like(self.u, dtype=bool)
        if self.config.resonator_geometry != "boundary_inner_edge":
            raise ValueError(f"Unsupported 3D resonator geometry: {self.config.resonator_geometry}")
        return self.source.mask.copy()

    def _apply_memory_mechanism_profile(self) -> None:
        profile_name = str(self.config.memory_mechanism_profile or "none")
        strength = float(self.config.memory_mechanism_strength or 0.0)
        if profile_name == "none" or abs(strength) <= EPSILON:
            return
        profile = _memory_mechanism_profile(self.config, self.coords, profile_name)
        if profile_name in {
            "anisotropy_anchor",
            "cubic_degeneracy_split",
            "radial_compensation",
            "isochronous_cubic_anchor",
            "isochronous_cubic_anchor_smooth_taper",
            "isochronous_cubic_anchor_wide_smooth_taper",
            "isochronous_cubic_anchor_weaker_compensation",
            "smooth_radial_compensation",
            "random_equivalent",
        }:
            self.stiffness *= np.clip(1.0 + strength * profile, 0.05, None)
        elif profile_name == "shell_band_isolation":
            shell = np.clip(profile, 0.0, 1.0)
            self.coupling_multiplier *= np.clip(1.0 - 0.5 * strength * shell, 0.05, None)
            self.stiffness *= np.clip(1.0 + 0.5 * strength * shell, 0.05, None)
        elif profile_name == "nonlinear_phase_memory":
            shell = np.clip(profile, 0.0, 1.0)
            self.nonlinear_strength += abs(strength) * shell
        else:
            raise ValueError(f"Unsupported passive memory mechanism profile: {profile_name}")


class Source3D:
    """Boundary, core, or shell forcing for the prototype."""

    def __init__(self, config: Prototype3DConfig, coords: dict[str, np.ndarray]):
        self.config = config
        self.coords = coords
        self.face_coverages = self._face_coverages()
        self.weights = self._weights()
        self.geometric_weights = self._geometric_weights()
        self.mask = self.weights > EPSILON
        self.phase_map = self._phase_map()
        self.boundary_area = self._boundary_area()
        self.source_width = config.boundary_source_width or config.dx
        source_volume = float(np.sum(self.geometric_weights) * config.cell_volume)
        self.effective_area = source_volume / max(self.source_width, EPSILON) if config.drive_location == "boundary" else 0.0
        self.normalization_scale = self.boundary_area / (source_volume + EPSILON) if config.drive_location == "boundary" else 1.0
        self.effective_volume = source_volume

    def _weights(self) -> np.ndarray:
        config = self.config
        radius = self.coords["radius"]
        if config.drive_location == "boundary":
            if not self.face_coverages:
                return np.zeros_like(radius)
            scaled = []
            scales = config.boundary_face_amplitude_scales or {}
            for face, coverage in self.face_coverages.items():
                scaled.append(coverage * float(scales.get(face, 1.0)))
            weights = np.maximum.reduce(scaled)
            patch_scales = config.boundary_patch_amplitude_scales or getattr(config, "_boundary_patch_amplitude_scales", None)
            if patch_scales:
                weights = weights * self._patch_scalar_map(patch_scales, default=1.0)
            return weights
        if config.drive_location == "core":
            return (radius <= config.defect_radius + config.dx).astype(float)
        if config.drive_location == "shell":
            inner = config.shell_inner_radius if config.shell_inner_radius is not None else config.defect_radius + config.dx
            outer = config.shell_outer_radius if config.shell_outer_radius is not None else config.defect_radius + 3.0 * config.dx
            return ((radius >= inner) & (radius <= outer)).astype(float)
        raise ValueError(f"Unsupported 3D drive_location: {config.drive_location}")

    def _geometric_weights(self) -> np.ndarray:
        if self.config.drive_location == "boundary":
            if not self.face_coverages:
                return np.zeros_like(self.coords["radius"])
            return np.maximum.reduce(list(self.face_coverages.values()))
        return self.weights

    def _face_coverages(self) -> dict[str, np.ndarray]:
        config = self.config
        if config.drive_location != "boundary":
            return {}
        start = max(0.0, config.boundary_source_inner_distance)
        width = config.boundary_source_width or config.dx
        coverages: dict[str, np.ndarray] = {}
        for face in _normalize_boundary_faces(config.boundary_faces):
            distance = self.coords["face_distances"][face]
            coverage = _cell_interval_coverage_between(distance, config.dx, start, start + width)
            if start > 0.0:
                coverage = np.where(self.coords["boundary_distance"] >= start, coverage, 0.0)
            coverages[face] = coverage
        return coverages

    def _phase_map(self) -> np.ndarray:
        config = self.config
        if config.drive_phase_mode == "uniform":
            return np.full_like(self.weights, config.boundary_phase_offset)
        if config.drive_phase_mode == "face_offsets":
            return self._face_offset_phase_map(config.boundary_face_phase_offsets or {}) + config.boundary_phase_offset
        if config.drive_phase_mode == "random":
            return self._random_phase_map()
        if config.drive_phase_mode != "cubic":
            raise ValueError(f"Unsupported 3D drive_phase_mode: {config.drive_phase_mode}")
        x = self.coords["x"]
        y = self.coords["y"]
        z = self.coords["z"]
        r = np.maximum(self.coords["radius"], config.dx)
        cubic = (x**4 + y**4 + z**4) / (r**4) - 0.6
        scale = np.max(np.abs(cubic[self.mask])) if np.any(self.mask) else 1.0
        phase_map = config.boundary_phase_offset + config.boundary_cubic_phase_sign * 0.5 * np.pi * cubic / (scale + EPSILON)
        return phase_map + self._patch_phase_offset_map()

    def _random_phase_map(self) -> np.ndarray:
        rng = np.random.default_rng(self.config.boundary_random_phase_seed or 0)
        phase_map = np.zeros_like(self.weights)
        phase_map[self.mask] = rng.uniform(0.0, 2.0 * np.pi, size=int(np.count_nonzero(self.mask)))
        return phase_map + self.config.boundary_phase_offset

    def _face_offset_phase_map(self, offsets: dict[str, float]) -> np.ndarray:
        if not self.face_coverages:
            return np.zeros_like(self.weights)
        real = np.zeros_like(self.weights)
        imag = np.zeros_like(self.weights)
        for face, coverage in self.face_coverages.items():
            phase = float(offsets.get(face, 0.0))
            real += coverage * np.cos(phase)
            imag += coverage * np.sin(phase)
        phase_map = np.zeros_like(self.weights)
        phase_map[self.mask] = np.arctan2(imag[self.mask], real[self.mask])
        return phase_map

    def _patch_scalar_map(self, values: dict[str, float], *, default: float) -> np.ndarray:
        out = np.full_like(self.coords["radius"], float(default), dtype=float)
        if not values or not self.face_coverages:
            return out
        numerator = np.zeros_like(out)
        denominator = np.zeros_like(out)
        for face, coverage in self.face_coverages.items():
            u_bin, v_bin = _boundary_patch_bins(self.config, self.coords, face)
            for patch_id, value in values.items():
                parsed = _parse_boundary_patch_id(patch_id)
                if parsed is None:
                    continue
                patch_face, patch_u, patch_v = parsed
                if patch_face != face:
                    continue
                mask = (u_bin == patch_u) & (v_bin == patch_v)
                weighted = coverage * mask.astype(float)
                numerator += weighted * float(value)
                denominator += weighted
        active = denominator > EPSILON
        out[active] = numerator[active] / denominator[active]
        return out

    def _patch_phase_offset_map(self) -> np.ndarray:
        offsets = self.config.boundary_patch_phase_offsets or getattr(self.config, "_boundary_patch_phase_offsets", None)
        phase_map = np.zeros_like(self.weights)
        if not offsets or not self.face_coverages:
            return phase_map
        real = np.zeros_like(self.weights)
        imag = np.zeros_like(self.weights)
        denominator = np.zeros_like(self.weights)
        for face, coverage in self.face_coverages.items():
            u_bin, v_bin = _boundary_patch_bins(self.config, self.coords, face)
            for patch_id, value in offsets.items():
                parsed = _parse_boundary_patch_id(patch_id)
                if parsed is None:
                    continue
                patch_face, patch_u, patch_v = parsed
                if patch_face != face:
                    continue
                mask = (u_bin == patch_u) & (v_bin == patch_v)
                weighted = coverage * mask.astype(float)
                real += weighted * np.cos(float(value))
                imag += weighted * np.sin(float(value))
                denominator += weighted
        active = denominator > EPSILON
        phase_map[active] = np.arctan2(imag[active], real[active])
        return phase_map

    def _boundary_area(self) -> float:
        if self.config.drive_location != "boundary":
            return 0.0
        return float(len(_normalize_boundary_faces(self.config.boundary_faces))) * self.config.domain_size**2

    def primary_envelope(self, time: float) -> float:
        cutoff = self.config.drive_cutoff_time
        if time > cutoff:
            return 0.0
        if self.config.drive_mode == "continuous":
            return 1.0
        phase = np.clip(time / max(cutoff, EPSILON), 0.0, 1.0)
        return float(np.sin(np.pi * phase) ** 2)

    def second_pulse_envelope(self, time: float) -> float:
        center = self.config.second_pulse_center_time
        duration = self.config.second_pulse_duration
        if center is None or duration <= EPSILON:
            return 0.0
        start = float(center) - 0.5 * float(duration)
        end = float(center) + 0.5 * float(duration)
        if time < start or time > end:
            return 0.0
        phase = np.clip((time - start) / max(duration, EPSILON), 0.0, 1.0)
        return float(np.sin(np.pi * phase) ** 2)

    def envelope(self, time: float) -> float:
        return self.primary_envelope(time) + self.config.second_pulse_amplitude_scale * self.second_pulse_envelope(time)

    def force(self, time: float) -> np.ndarray:
        out = np.zeros_like(self.weights)
        if self.config.drive_amplitude == 0.0 or not np.any(self.mask):
            return out
        primary = self.primary_envelope(time)
        if primary > 0.0:
            out[self.mask] += self._force_values(time, primary, 1.0, 0.0)
        second = self.second_pulse_envelope(time)
        if second > 0.0:
            out[self.mask] += self._force_values(
                time,
                second,
                self.config.second_pulse_amplitude_scale,
                self.config.second_pulse_phase_offset,
            )
        return out

    def _force_values(self, time: float, envelope: float, amplitude_scale: float, phase_offset: float) -> np.ndarray:
        angle = self._drive_angle(time) + self.phase_map[self.mask] + phase_offset
        return (
            self.config.drive_amplitude
            * amplitude_scale
            * self.normalization_scale
            * envelope
            * np.sin(angle)
            * self.weights[self.mask]
        )

    def _drive_angle(self, time: float) -> float:
        if self.config.drive_mode != "chirp":
            return 2.0 * np.pi * self.config.drive_frequency * time
        cutoff = max(self.config.drive_cutoff_time, EPSILON)
        start = self.config.drive_chirp_start_frequency
        end = self.config.drive_chirp_end_frequency
        f0 = float(start if start is not None else self.config.drive_frequency)
        f1 = float(end if end is not None else self.config.drive_frequency)
        k = (f1 - f0) / cutoff
        return 2.0 * np.pi * (f0 * time + 0.5 * k * time**2)


def _second_pulse_bounds(config: Prototype3DConfig) -> tuple[float, float] | None:
    if config.second_pulse_center_time is None or config.second_pulse_duration <= EPSILON:
        return None
    center = float(config.second_pulse_center_time)
    half = 0.5 * float(config.second_pulse_duration)
    return center - half, center + half


def _second_pulse_active(config: Prototype3DConfig, time: float) -> bool:
    bounds = _second_pulse_bounds(config)
    if bounds is None:
        return False
    start, end = bounds
    return start <= time <= end


def _primary_drive_active(config: Prototype3DConfig, time: float) -> bool:
    return time <= config.drive_cutoff_time


def run_3d_prototype(
    base_config: SimulationConfig,
    *,
    options: Prototype3DOptions | None = None,
) -> dict[str, Any]:
    """Run the tiny 3D source-geometry prototype and write reports."""

    options = options or Prototype3DOptions()
    prototype_id = datetime.now().strftime("prototype_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / prototype_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    rows: list[dict[str, Any]] = []
    reference_work = 0.0
    reference_area = 0.0
    reference_row: dict[str, Any] | None = None
    reference_profile: np.ndarray | None = None
    reference_frame: np.ndarray | None = None

    for idx, config in enumerate(variants):
        if idx == 0:
            summary = _run_variant(config, root, options)
            reference_work = float(summary["positive_work_before_cutoff"])
            reference_area = float(summary["boundary_area"])
        else:
            target_work = reference_work
            if config.drive_location == "boundary" and reference_area > EPSILON:
                target_work = (reference_work / reference_area) * max(_source_area(config), EPSILON)
            _calibrate_amplitude(config, target_work)
            summary = _run_variant(config, root, options)

        if reference_profile is None:
            reference_profile = np.asarray(summary["best_radial_profile"], dtype=float)
            reference_frame = np.load(Path(summary["path"]) / "best_shell_energy_density.npy")
            reference_row = summary
            summary["radial_similarity_to_reference"] = 1.0
            summary["best_frame_similarity_to_reference"] = 1.0
        else:
            profile = np.asarray(summary["best_radial_profile"], dtype=float)
            frame = np.load(Path(summary["path"]) / "best_shell_energy_density.npy")
            summary["radial_similarity_to_reference"] = _profile_similarity(reference_profile, profile)
            summary["best_frame_similarity_to_reference"] = _frame_similarity(reference_frame, frame)
        rows.append(summary)

    classification = classify_3d_prototype(rows, options)
    for row in rows:
        row["classification_label"] = classification["label"]

    summary_csv = root / "prototype_3d_summary.csv"
    report_path = root / "prototype_3d_report.md"
    _write_csv(summary_csv, rows, _summary_fields())
    _write_report(report_path, prototype_id, base_config, rows, classification, options)
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": prototype_id,
            "classification": classification,
            "variants": rows,
            "summary_csv": str(summary_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "prototype_id": prototype_id,
        "classification": classification,
        "variants": rows,
        "summary_csv": str(summary_csv),
        "report_path": str(report_path),
        "path": str(root),
        "reference": reference_row,
    }


def classify_3d_prototype(rows: list[dict[str, Any]], options: Prototype3DOptions | None = None) -> dict[str, Any]:
    options = options or Prototype3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No 3D prototype rows were available.", "checks": {}}
    reference = next((row for row in rows if row["variant"] == "boundary_cubic_31"), rows[0])
    boundary_rows = [row for row in rows if row["drive_location"] == "boundary"]
    direct_rows = [row for row in rows if row["drive_location"] != "boundary"]
    cubic_controls = [row for row in boundary_rows if row["variant"].startswith("boundary_cubic_") and row is not reference]
    reference_pass = _shell_success(reference, options)
    direct_successes = [_shell_success(row, options) and _matches_reference(row, options) for row in direct_rows]
    control_successes = [_shell_success(row, options) and _matches_reference(row, options) for row in cubic_controls]
    checks = {
        "reference_shell_breathing": reference_pass,
        "direct_reproduction_count": sum(1 for passed in direct_successes if passed),
        "boundary_control_success_count": sum(1 for passed in control_successes if passed),
        "boundary_control_count": len(cubic_controls),
    }
    if reference_pass and any(direct_successes):
        return {
            "label": "direct_forcing_reproduces_shell",
            "reason": "A direct core or shell forcing variant reproduced the reference-like retained shell breathing.",
            "checks": checks,
        }
    if reference_pass and cubic_controls and not all(control_successes):
        return {
            "label": "sponge_or_dt_sensitive",
            "reason": "The boundary reference showed shell breathing, but a sponge or dt confirmation did not match it.",
            "checks": checks,
        }
    if reference_pass:
        return {
            "label": "boundary_flux_shell_breathing_candidate",
            "reason": "Matched boundary-flux forcing produced retained shell breathing that direct core/shell controls did not reproduce.",
            "checks": checks,
        }
    return {
        "label": "inconclusive",
        "reason": "The 3D boundary reference did not clearly produce retained spherical shell breathing.",
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: Prototype3DOptions) -> list[Prototype3DConfig]:
    base_3d = _base_3d_config("boundary_cubic_31", base, options, "boundary", "cubic")
    variants = [
        base_3d,
        _base_3d_config("boundary_uniform_31", base, options, "boundary", "uniform"),
        _base_3d_config("direct_core_31", base, options, "core", "uniform"),
        _base_3d_config("direct_shell_31", base, options, "shell", "uniform"),
    ]
    if options.include_sponge_control:
        stronger = _base_3d_config("boundary_cubic_stronger_sponge_31", base, options, "boundary", "cubic")
        stronger.sponge_strength *= 2.0
        variants.append(stronger)
    if options.include_dt_control:
        half_dt = _base_3d_config("boundary_cubic_half_dt_31", base, options, "boundary", "cubic")
        half_dt.dt *= 0.5
        half_dt.steps *= 2
        variants.append(half_dt)
    return variants


def _base_3d_config(
    name: str,
    base: SimulationConfig,
    options: Prototype3DOptions,
    drive_location: str,
    phase_mode: str,
) -> Prototype3DConfig:
    domain = float(base.domain_width if base.domain_width is not None else base.grid_size - 1)
    defect_radius = float(base.defect.radius_physical if base.defect.radius_physical is not None else base.defect.radius)
    dx = domain / float(max(options.grid_size - 1, 1))
    return Prototype3DConfig(
        name=name,
        grid_size=options.grid_size,
        steps=base.steps,
        dt=base.dt,
        domain_size=domain,
        base_stiffness=base.base_stiffness,
        coupling_strength=base.coupling_strength,
        global_damping=base.global_damping,
        nonlinear_strength=base.nonlinear_strength,
        defect_radius=defect_radius,
        defect_stiffness_multiplier=base.defect.stiffness_multiplier,
        defect_damping_multiplier=base.defect.damping_multiplier,
        defect_coupling_multiplier=base.defect.coupling_multiplier,
        sponge_width=float(base.boundary_damping_width_physical or base.boundary_damping_width),
        sponge_strength=base.boundary_damping_strength,
        drive_frequency=base.driver.frequency,
        drive_amplitude=base.driver.amplitude,
        drive_cutoff_time=float(base.driver.drive_cutoff_time),
        drive_location=drive_location,
        drive_phase_mode=phase_mode,
        shell_inner_radius=defect_radius + dx,
        shell_outer_radius=defect_radius + 3.0 * dx,
    )


def _memory_mechanism_profile(
    config: Prototype3DConfig,
    coords: dict[str, np.ndarray],
    profile_name: str,
) -> np.ndarray:
    x = coords["x"].astype(float)
    y = coords["y"].astype(float)
    z = coords["z"].astype(float)
    radius = coords["radius"].astype(float)
    active = coords["boundary_distance"] >= config.sponge_width
    scale = max(0.5 * config.domain_size, EPSILON)
    if profile_name == "anisotropy_anchor":
        raw = 0.65 * x / scale - 0.35 * y / scale + 0.20 * z / scale
        return _normalized_active_profile(raw, active)
    if profile_name == "cubic_degeneracy_split":
        return _cubic_degeneracy_profile(config, coords, active)
    if profile_name == "radial_compensation":
        return _radial_compensation_profile(config, coords, active)
    if profile_name == "isochronous_cubic_anchor":
        cubic = _cubic_degeneracy_profile(config, coords, active)
        radial = _radial_compensation_profile(config, coords, active)
        return _normalized_active_profile(cubic + 0.45 * radial, active)
    if profile_name == "isochronous_cubic_anchor_smooth_taper":
        cubic = _cubic_degeneracy_profile(config, coords, active)
        radial = _smooth_radial_compensation_profile(config, coords, active, width_scale=1.0)
        return _normalized_active_profile(cubic + 0.45 * radial, active)
    if profile_name == "isochronous_cubic_anchor_wide_smooth_taper":
        cubic = _cubic_degeneracy_profile(config, coords, active)
        radial = _smooth_radial_compensation_profile(config, coords, active, width_scale=1.6)
        return _normalized_active_profile(cubic + 0.45 * radial, active)
    if profile_name == "isochronous_cubic_anchor_weaker_compensation":
        cubic = _cubic_degeneracy_profile(config, coords, active)
        radial = _smooth_radial_compensation_profile(config, coords, active, width_scale=1.0)
        return _normalized_active_profile(cubic + 0.25 * radial, active)
    if profile_name == "smooth_radial_compensation":
        return _smooth_radial_compensation_profile(config, coords, active, width_scale=1.0)
    if profile_name == "shell_band_isolation":
        center = config.memory_mechanism_shell_radius
        if center is None:
            center = float(config.defect_radius + 2.0 * config.dx)
        width = max(float(config.memory_mechanism_shell_width or (4.0 * config.dx)), config.dx)
        raw = np.exp(-0.5 * ((radius - center) / width) ** 2)
        return _rms_normalized_active_profile(raw, active)
    if profile_name == "nonlinear_phase_memory":
        center = config.memory_mechanism_shell_radius
        if center is None:
            center = float(config.defect_radius + 2.0 * config.dx)
        width = max(float(config.memory_mechanism_shell_width or (4.0 * config.dx)), config.dx)
        raw = np.exp(-0.5 * ((radius - center) / width) ** 2)
        return _rms_normalized_active_profile(raw, active)
    if profile_name == "random_equivalent":
        rng = np.random.default_rng(config.memory_mechanism_seed or 0)
        raw = rng.normal(size=radius.shape)
        return _normalized_active_profile(raw, active)
    raise ValueError(f"Unsupported passive memory mechanism profile: {profile_name}")


def _cubic_degeneracy_profile(
    config: Prototype3DConfig,
    coords: dict[str, np.ndarray],
    active: np.ndarray,
) -> np.ndarray:
    x = coords["x"].astype(float)
    y = coords["y"].astype(float)
    z = coords["z"].astype(float)
    radius = np.maximum(coords["radius"].astype(float), config.dx)
    raw = (x**4 + y**4 + z**4) / np.maximum(radius**4, EPSILON)
    return _normalized_active_profile(raw, active)


def _radial_compensation_profile(
    config: Prototype3DConfig,
    coords: dict[str, np.ndarray],
    active: np.ndarray,
) -> np.ndarray:
    radius = coords["radius"].astype(float)
    center = config.memory_mechanism_shell_radius
    if center is None:
        center = float(config.defect_radius + 2.0 * config.dx)
    width = max(float(config.memory_mechanism_shell_width or (4.0 * config.dx)), config.dx)
    shell = np.exp(-0.5 * ((radius - center) / width) ** 2)
    broad = np.exp(-0.5 * ((radius - center) / max(2.5 * width, config.dx)) ** 2)
    raw = broad - shell
    return _normalized_active_profile(raw, active)


def _smooth_radial_compensation_profile(
    config: Prototype3DConfig,
    coords: dict[str, np.ndarray],
    active: np.ndarray,
    *,
    width_scale: float,
) -> np.ndarray:
    radius = coords["radius"].astype(float)
    center = config.memory_mechanism_shell_radius
    if center is None:
        center = float(config.defect_radius + 2.0 * config.dx)
    width = max(float(config.memory_mechanism_shell_width or (4.0 * config.dx)), config.dx)
    base_width = max(width * float(width_scale), config.dx)
    shell = np.exp(-0.5 * ((radius - center) / base_width) ** 2)
    broad = np.exp(-0.5 * ((radius - center) / max(2.5 * base_width, config.dx)) ** 2)
    support = max(3.0 * base_width, config.dx)
    phase = np.clip(np.abs(radius - center) / support, 0.0, 1.0)
    taper = 0.5 * (1.0 + np.cos(np.pi * phase))
    taper = np.where(np.abs(radius - center) <= support, taper, 0.0)
    raw = (broad - shell) * taper
    return _normalized_active_profile(raw, active)


def _normalized_active_profile(raw: np.ndarray, active: np.ndarray) -> np.ndarray:
    out = np.zeros_like(raw, dtype=float)
    values = np.asarray(raw[active], dtype=float)
    if values.size == 0:
        return out
    centered = values - float(np.mean(values))
    rms = float(np.sqrt(np.mean(centered**2)))
    if rms <= EPSILON:
        return out
    out[active] = centered / rms
    return out


def _rms_normalized_active_profile(raw: np.ndarray, active: np.ndarray) -> np.ndarray:
    out = np.zeros_like(raw, dtype=float)
    values = np.asarray(raw[active], dtype=float)
    if values.size == 0:
        return out
    rms = float(np.sqrt(np.mean(values**2)))
    if rms <= EPSILON:
        return out
    out[active] = values / rms
    return out


def _run_variant(config: Prototype3DConfig, root: Path, options: Prototype3DOptions) -> dict[str, Any]:
    run_dir = root / config.name
    run_dir.mkdir(parents=True, exist_ok=False)
    lattice = Lattice3D(config)
    bins = _radial_bins(config, options.radial_bins)
    samples: list[dict[str, Any]] = []
    radial_rows: list[dict[str, Any]] = []
    cumulative_work = 0.0
    cumulative_positive_work = 0.0
    positive_work_before_cutoff = 0.0
    cumulative_damping_loss = 0.0
    best_shell_peak = -np.inf
    best_energy: np.ndarray | None = None
    best_profile: np.ndarray | None = None
    final_energy: np.ndarray | None = None

    for step in range(config.steps):
        time = step * config.dt
        force = lattice.external_force(time)
        velocity_before = lattice.v.copy()
        lattice.step(time, config.dt)
        velocity_mid = 0.5 * (velocity_before + lattice.v)
        power = float(np.sum(force * velocity_mid) * config.cell_volume)
        damping_power = float(np.sum(lattice.damping * velocity_mid**2) * config.cell_volume)
        cumulative_work += power * config.dt
        cumulative_positive_work += max(0.0, power) * config.dt
        cumulative_damping_loss += damping_power * config.dt
        if time <= config.drive_cutoff_time:
            positive_work_before_cutoff += max(0.0, power) * config.dt

        if step % max(1, options.sample_every) != 0 and step != config.steps - 1:
            continue

        energy = lattice.energy_density()
        final_energy = energy.copy()
        profile = _radial_profile(energy, lattice.coords["radius"], bins)
        shell = _shell_summary(profile, bins, config)
        core_energy = float(np.sum(energy[lattice.core_mask]))
        total_energy = float(np.sum(energy))
        row = {
            "step": step,
            "time": time,
            "core_energy": core_energy,
            "shell_peak_energy": shell["shell_peak_energy"],
            "shell_peak_radius": shell["shell_peak_radius"],
            "total_energy": total_energy,
            "outer_energy": max(total_energy - core_energy, 0.0),
            "positive_work": cumulative_positive_work,
            "damping_loss": cumulative_damping_loss,
        }
        samples.append(row)
        radial_rows.append({"time": time, **{f"bin_{idx}": value for idx, value in enumerate(profile)}})
        if time > config.drive_cutoff_time and shell["shell_peak_energy"] > best_shell_peak:
            best_shell_peak = shell["shell_peak_energy"]
            best_energy = energy.copy()
            best_profile = profile.copy()

    if final_energy is None or not samples:
        raise RuntimeError("3D prototype produced no samples.")
    if best_energy is None or best_profile is None:
        best_energy = final_energy.copy()
        best_profile = _radial_profile(final_energy, lattice.coords["radius"], bins)

    np.save(run_dir / "best_shell_energy_density.npy", best_energy)
    np.save(run_dir / "final_energy_density.npy", final_energy)
    _write_metrics(run_dir / "metrics.csv", samples)
    _write_radial_profiles(run_dir / "radial_profile_timeseries.csv", radial_rows, options.radial_bins)
    _plot_energy(samples, config, run_dir / "energy_timeseries.png")
    _plot_shell(samples, config, run_dir / "shell_peak_timeseries.png")
    _plot_radial_heatmap(radial_rows, bins, run_dir / "radial_profile_heatmap.png")
    _save_midplane(best_energy, run_dir / "best_shell_midplane.png", "Best post-cutoff shell energy midplane")
    _save_midplane(final_energy, run_dir / "final_midplane.png", "Final energy midplane")

    summary = _summarize_variant(config, samples, bins, best_profile, positive_work_before_cutoff, lattice.source)
    summary["path"] = str(run_dir)
    summary["best_radial_profile"] = best_profile.tolist()
    save_json(run_dir / "summary.json", _json_summary(summary))
    return summary


def _summarize_variant(
    config: Prototype3DConfig,
    samples: list[dict[str, Any]],
    bins: np.ndarray,
    best_profile: np.ndarray,
    positive_work_before_cutoff: float,
    source: Source3D,
) -> dict[str, Any]:
    post = [row for row in samples if row["time"] > config.drive_cutoff_time]
    evidence = post if post else samples
    best = max(evidence, key=lambda row: row["shell_peak_energy"])
    shell_values = np.asarray([row["shell_peak_energy"] for row in samples], dtype=float)
    post_shell = np.asarray([row["shell_peak_energy"] for row in post], dtype=float)
    tail_start = max(0, int(post_shell.size * 0.35))
    reference = max(float(np.max(shell_values)) if shell_values.size else 0.0, EPSILON)
    retention = float(np.mean(post_shell[tail_start:]) / reference) if post_shell.size else 0.0
    breathing = _detect_shell_breathing(samples, config)
    radii = np.asarray([row["shell_peak_radius"] for row in post], dtype=float)
    radius_range = float(np.percentile(radii, 90) - np.percentile(radii, 10)) if radii.size else 0.0
    return {
        "variant": config.name,
        "grid_size": config.grid_size,
        "dx": config.dx,
        "dt": config.dt,
        "steps": config.steps,
        "physical_duration": config.physical_duration,
        "drive_location": config.drive_location,
        "drive_phase_mode": config.drive_phase_mode,
        "drive_amplitude": config.drive_amplitude,
        "drive_frequency": config.drive_frequency,
        "drive_mode": config.drive_mode,
        "drive_chirp_start_frequency": config.drive_chirp_start_frequency,
        "drive_chirp_end_frequency": config.drive_chirp_end_frequency,
        "drive_cutoff_time": config.drive_cutoff_time,
        "defect_radius": config.defect_radius,
        "nonlinear_strength": config.nonlinear_strength,
        "defect_stiffness_multiplier": config.defect_stiffness_multiplier,
        "defect_damping_multiplier": config.defect_damping_multiplier,
        "defect_coupling_multiplier": config.defect_coupling_multiplier,
        "defect_inner_radius": config.defect_inner_radius,
        "defect_nonlinear_strength": config.defect_nonlinear_strength,
        "boundary_area": source.boundary_area,
        "boundary_faces": list(_normalize_boundary_faces(config.boundary_faces)),
        "boundary_face_count": len(_normalize_boundary_faces(config.boundary_faces)),
        "boundary_face_phase_offsets": config.boundary_face_phase_offsets or {},
        "boundary_phase_offset": config.boundary_phase_offset,
        "boundary_cubic_phase_sign": config.boundary_cubic_phase_sign,
        "boundary_face_amplitude_scales": config.boundary_face_amplitude_scales or {},
        "boundary_random_phase_seed": config.boundary_random_phase_seed,
        "effective_source_volume": source.effective_volume,
        "effective_source_area": source.effective_area,
        "boundary_source_inner_distance": config.boundary_source_inner_distance,
        "boundary_source_width": source.source_width,
        "exclude_source_from_sponge_damping": config.exclude_source_from_sponge_damping,
        "positive_work_before_cutoff": positive_work_before_cutoff,
        "work_per_boundary_area": positive_work_before_cutoff / (source.boundary_area + EPSILON) if source.boundary_area else 0.0,
        "work_per_source_area": positive_work_before_cutoff / (source.effective_area + EPSILON) if source.effective_area else 0.0,
        "work_per_source_volume": positive_work_before_cutoff / (source.effective_volume + EPSILON) if source.effective_volume else 0.0,
        "best_shell_event_time": best["time"],
        "best_shell_peak_energy": best["shell_peak_energy"],
        "best_shell_peak_radius": best["shell_peak_radius"],
        "post_cutoff_shell_retention": retention,
        "post_cutoff_shell_radius_range": radius_range,
        "post_cutoff_core_energy": best["core_energy"],
        "post_cutoff_total_energy": best["total_energy"],
        "core_fraction_at_best_shell": best["core_energy"] / (best["total_energy"] + EPSILON),
        "shell_breathing_detected": breathing["detected"],
        "shell_breathing_period": breathing["period"],
        "shell_breathing_cycles": breathing["cycles"],
        "shell_breathing_strength": breathing["strength"],
        "best_radial_profile": best_profile.tolist(),
        "radial_similarity_to_reference": None,
        "best_frame_similarity_to_reference": None,
        "classification_label": None,
    }


def _detect_shell_breathing(samples: list[dict[str, Any]], config: Prototype3DConfig) -> dict[str, Any]:
    post = [row for row in samples if row["time"] > config.drive_cutoff_time]
    if len(post) < 6:
        return {"detected": False, "period": None, "cycles": 0, "strength": 0.0}
    times = np.asarray([row["time"] for row in post], dtype=float)
    values = np.asarray([row["shell_peak_energy"] for row in post], dtype=float)
    dynamic = float(np.percentile(values, 90) - np.percentile(values, 10))
    strength = dynamic / (float(np.percentile(values, 90)) + EPSILON)
    min_sep = max(1.5, 0.6 * max(2.0, 2.25 / max(config.drive_frequency, EPSILON)))
    peaks: list[int] = []
    for idx in range(1, values.size - 1):
        if values[idx] <= values[idx - 1] or values[idx] < values[idx + 1]:
            continue
        if values[idx] < np.percentile(values, 55):
            continue
        if peaks and times[idx] - times[peaks[-1]] < min_sep:
            if values[idx] > values[peaks[-1]]:
                peaks[-1] = idx
            continue
        peaks.append(idx)
    if len(peaks) < 3:
        return {"detected": False, "period": None, "cycles": len(peaks), "strength": strength}
    intervals = np.diff(times[peaks])
    period = float(np.median(intervals))
    cv = float(np.std(intervals) / (np.mean(intervals) + EPSILON))
    return {
        "detected": strength >= 0.05 and cv <= 0.8,
        "period": period,
        "cycles": len(peaks),
        "strength": strength,
    }


def _shell_success(row: dict[str, Any], options: Prototype3DOptions) -> bool:
    return (
        bool(row.get("shell_breathing_detected"))
        and float(row.get("post_cutoff_shell_retention") or 0.0) >= options.min_shell_retention
        and float(row.get("post_cutoff_shell_radius_range") or 999.0) <= options.max_shell_radius_range
    )


def _matches_reference(row: dict[str, Any], options: Prototype3DOptions) -> bool:
    return (
        float(row.get("radial_similarity_to_reference") or 0.0) >= options.min_radial_similarity
        or float(row.get("best_frame_similarity_to_reference") or 0.0) >= 0.35
    )


def _calibrate_amplitude(config: Prototype3DConfig, target_work: float) -> None:
    measured = _audit_work(config)
    if measured <= EPSILON or target_work <= EPSILON:
        return
    config.drive_amplitude *= float(np.sqrt(target_work / measured))


def _audit_work(config: Prototype3DConfig) -> float:
    lattice = Lattice3D(config)
    total = 0.0
    for step in range(config.steps):
        time = step * config.dt
        if time > config.drive_cutoff_time:
            break
        force = lattice.external_force(time)
        velocity_before = lattice.v.copy()
        lattice.step(time, config.dt)
        velocity_mid = 0.5 * (velocity_before + lattice.v)
        power = float(np.sum(force * velocity_mid) * config.cell_volume)
        total += max(0.0, power) * config.dt
    return total


def _source_area(config: Prototype3DConfig) -> float:
    return Source3D(config, _coordinate_payload(config)).boundary_area


def _coordinate_payload(config: Prototype3DConfig) -> dict[str, np.ndarray]:
    axis = (np.arange(config.grid_size, dtype=float) - (config.grid_size - 1) / 2.0) * config.dx
    z, y, x = np.meshgrid(axis, axis, axis, indexing="ij")
    radius = np.sqrt(x**2 + y**2 + z**2)
    half = 0.5 * config.domain_size
    face_distances = {
        "x_min": x + half,
        "x_max": half - x,
        "y_min": y + half,
        "y_max": half - y,
        "z_min": z + half,
        "z_max": half - z,
    }
    boundary_distance = np.minimum.reduce(list(face_distances.values()))
    return {"x": x, "y": y, "z": z, "radius": radius, "boundary_distance": boundary_distance, "face_distances": face_distances}


def _normalize_boundary_faces(faces: tuple[str, ...] | list[str] | str | None) -> tuple[str, ...]:
    if faces is None:
        return ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
    if isinstance(faces, str):
        raw = [part.strip() for part in faces.split(",") if part.strip()]
    else:
        raw = [str(face).strip() for face in faces if str(face).strip()]
    aliases = {
        "left": "x_min",
        "right": "x_max",
        "front": "y_min",
        "back": "y_max",
        "bottom": "z_min",
        "top": "z_max",
    }
    valid = {"x_min", "x_max", "y_min", "y_max", "z_min", "z_max"}
    normalized: list[str] = []
    for face in raw:
        canonical = aliases.get(face, face)
        if canonical not in valid:
            raise ValueError(f"Unsupported 3D boundary face: {face}")
        if canonical not in normalized:
            normalized.append(canonical)
    return tuple(normalized)


def _parse_boundary_patch_id(patch_id: str) -> tuple[str, int, int] | None:
    parts = str(patch_id).split(":")
    if len(parts) != 3:
        return None
    face = parts[0]
    try:
        return face, int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _boundary_patch_bins(config: Prototype3DConfig, coords: dict[str, np.ndarray], face: str) -> tuple[np.ndarray, np.ndarray]:
    half = 0.5 * float(config.domain_size)
    u_bins = max(1, int(getattr(config, "boundary_patch_u_bins", 4)))
    v_bins = max(1, int(getattr(config, "boundary_patch_v_bins", 4)))
    if face in {"x_min", "x_max"}:
        u_coord = coords["y"]
        v_coord = coords["z"]
    elif face in {"y_min", "y_max"}:
        u_coord = coords["x"]
        v_coord = coords["z"]
    else:
        u_coord = coords["x"]
        v_coord = coords["y"]
    u_index = np.floor(np.clip((u_coord + half) / max(config.domain_size, EPSILON), 0.0, 1.0 - EPSILON) * u_bins)
    v_index = np.floor(np.clip((v_coord + half) / max(config.domain_size, EPSILON), 0.0, 1.0 - EPSILON) * v_bins)
    return u_index.astype(int), v_index.astype(int)


def _sponge_extra(config: Prototype3DConfig, coords: dict[str, np.ndarray]) -> np.ndarray:
    width = max(config.sponge_width, EPSILON)
    distance = coords["boundary_distance"]
    ramp = np.clip((width - distance) / width, 0.0, 1.0)
    return config.sponge_strength * ramp**2


def _laplacian(u: np.ndarray, dx: float) -> np.ndarray:
    return (
        _shift_edge(u, 1, 0)
        + _shift_edge(u, -1, 0)
        + _shift_edge(u, 1, 1)
        + _shift_edge(u, -1, 1)
        + _shift_edge(u, 1, 2)
        + _shift_edge(u, -1, 2)
        - 6.0 * u
    ) / (dx**2)


def _shift_edge(arr: np.ndarray, shift: int, axis: int) -> np.ndarray:
    shifted = np.empty_like(arr)
    if axis == 0:
        if shift > 0:
            shifted[1:] = arr[:-1]
            shifted[0] = arr[0]
        else:
            shifted[:-1] = arr[1:]
            shifted[-1] = arr[-1]
    elif axis == 1:
        if shift > 0:
            shifted[:, 1:] = arr[:, :-1]
            shifted[:, 0] = arr[:, 0]
        else:
            shifted[:, :-1] = arr[:, 1:]
            shifted[:, -1] = arr[:, -1]
    else:
        if shift > 0:
            shifted[:, :, 1:] = arr[:, :, :-1]
            shifted[:, :, 0] = arr[:, :, 0]
        else:
            shifted[:, :, :-1] = arr[:, :, 1:]
            shifted[:, :, -1] = arr[:, :, -1]
    return shifted


def _cell_interval_coverage(distance: np.ndarray, spacing: float, width: float) -> np.ndarray:
    return _cell_interval_coverage_between(distance, spacing, 0.0, width)


def _cell_interval_coverage_between(distance: np.ndarray, spacing: float, start: float, stop: float) -> np.ndarray:
    lower = np.maximum(distance - 0.5 * spacing, 0.0)
    upper = distance + 0.5 * spacing
    overlap = np.maximum(0.0, np.minimum(upper, stop) - np.maximum(lower, start))
    return np.clip(overlap / max(spacing, EPSILON), 0.0, 1.0)


def _radial_bins(config: Prototype3DConfig, count: int) -> np.ndarray:
    return np.linspace(0.0, np.sqrt(3.0) * config.domain_size / 2.0, count + 1)


def _radial_profile(energy: np.ndarray, radius: np.ndarray, bins: np.ndarray) -> np.ndarray:
    indices = np.clip(np.digitize(radius.ravel(), bins) - 1, 0, len(bins) - 2)
    sums = np.bincount(indices, weights=energy.ravel(), minlength=len(bins) - 1)
    counts = np.bincount(indices, minlength=len(bins) - 1)
    return sums / np.maximum(counts, 1)


def _shell_summary(profile: np.ndarray, bins: np.ndarray, config: Prototype3DConfig) -> dict[str, float]:
    centers = 0.5 * (bins[:-1] + bins[1:])
    shell_mask = centers > config.defect_radius
    if not np.any(shell_mask):
        return {"shell_peak_radius": 0.0, "shell_peak_energy": 0.0}
    shell_values = np.where(shell_mask, profile, -np.inf)
    idx = int(np.argmax(shell_values))
    return {"shell_peak_radius": float(centers[idx]), "shell_peak_energy": float(profile[idx])}


def _profile_similarity(first: np.ndarray, second: np.ndarray) -> float:
    if first.size != second.size:
        size = min(first.size, second.size)
        first = first[:size]
        second = second[:size]
    a = first - np.mean(first)
    b = second - np.mean(second)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= EPSILON:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))


def _frame_similarity(first: np.ndarray | None, second: np.ndarray | None) -> float:
    if first is None or second is None or first.shape != second.shape:
        return 0.0
    a = first.ravel() - float(np.mean(first))
    b = second.ravel() - float(np.mean(second))
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= EPSILON:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))


def _write_metrics(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["step", "time", "core_energy", "shell_peak_energy", "shell_peak_radius", "total_energy", "outer_energy", "positive_work", "damping_loss"]
    _write_csv(path, rows, fields)


def _write_radial_profiles(path: Path, rows: list[dict[str, Any]], bins: int) -> None:
    fields = ["time"] + [f"bin_{idx}" for idx in range(bins)]
    _write_csv(path, rows, fields)


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _summary_fields() -> list[str]:
    return [
        "variant",
        "classification_label",
        "grid_size",
        "dx",
        "dt",
        "steps",
        "physical_duration",
        "drive_location",
        "drive_phase_mode",
        "drive_amplitude",
        "drive_frequency",
        "drive_mode",
        "drive_chirp_start_frequency",
        "drive_chirp_end_frequency",
        "drive_cutoff_time",
        "defect_radius",
        "nonlinear_strength",
        "defect_stiffness_multiplier",
        "defect_damping_multiplier",
        "defect_coupling_multiplier",
        "defect_inner_radius",
        "defect_nonlinear_strength",
        "boundary_area",
        "boundary_faces",
        "boundary_face_count",
        "boundary_face_phase_offsets",
        "boundary_phase_offset",
        "boundary_cubic_phase_sign",
        "boundary_face_amplitude_scales",
        "boundary_random_phase_seed",
        "effective_source_volume",
        "effective_source_area",
        "boundary_source_inner_distance",
        "boundary_source_width",
        "exclude_source_from_sponge_damping",
        "positive_work_before_cutoff",
        "work_per_boundary_area",
        "work_per_source_area",
        "work_per_source_volume",
        "best_shell_event_time",
        "best_shell_peak_energy",
        "best_shell_peak_radius",
        "post_cutoff_shell_retention",
        "post_cutoff_shell_radius_range",
        "post_cutoff_core_energy",
        "post_cutoff_total_energy",
        "core_fraction_at_best_shell",
        "shell_breathing_detected",
        "shell_breathing_period",
        "shell_breathing_cycles",
        "shell_breathing_strength",
        "radial_similarity_to_reference",
        "best_frame_similarity_to_reference",
        "path",
    ]


def _write_report(
    path: Path,
    prototype_id: str,
    base_config: SimulationConfig,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: Prototype3DOptions,
) -> None:
    lines = [
        f"# 3D Prototype Report: {prototype_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny fixed-domain 3D prototype for the narrow question: can matched boundary-flux waves organize around "
            "a spherical defect and produce retained post-cutoff shell breathing?"
        ),
        "",
        "## Base Case",
        "",
        f"- 2D source config grid: `{base_config.grid_size}`",
        f"- 3D grid: `{options.grid_size}^3`",
        f"- Drive frequency: `{base_config.driver.frequency}`",
        f"- Drive cutoff time: `{base_config.driver.drive_cutoff_time}`",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Variant Summary",
        "",
        "| Variant | Drive | Phase | Work/Area | Retention | Shell Period | Cycles | Shell Radius | Radius Range | Core Fraction | Radial Sim | Frame Sim |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row['drive_location']} | "
            f"{row['drive_phase_mode']} | "
            f"{_format(row.get('work_per_boundary_area'))} | "
            f"{_format(row.get('post_cutoff_shell_retention'))} | "
            f"{_format(row.get('shell_breathing_period'))} | "
            f"{row.get('shell_breathing_cycles')} | "
            f"{_format(row.get('best_shell_peak_radius'))} | "
            f"{_format(row.get('post_cutoff_shell_radius_range'))} | "
            f"{_format(row.get('core_fraction_at_best_shell'))} | "
            f"{_format(row.get('radial_similarity_to_reference'))} | "
            f"{_format(row.get('best_frame_similarity_to_reference'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _classification_interpretation(classification),
            "",
            "## Files",
            "",
            "- `prototype_3d_summary.csv`",
            "- `prototype_3d_summary.json`",
        ]
    )
    for row in rows:
        lines.append(f"- `{row['variant']}` run folder: `{row.get('path')}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _classification_interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "boundary_flux_shell_breathing_candidate":
        return (
            "The tiny 3D prototype passes the first narrow check: boundary-flux forcing produced retained shell breathing, "
            "while direct core/shell controls did not reproduce the reference-like shell."
        )
    if label == "direct_forcing_reproduces_shell":
        return "A direct core or shell source reproduced the retained shell, so the effect is not boundary-transport-specific in this prototype."
    if label == "sponge_or_dt_sensitive":
        return "The reference shell response is sensitive to sponge or dt in this first 3D prototype; tighten numerics before interpreting."
    return "The prototype is inconclusive. Do not expand 3D or run broad 2D sweeps until the failure mode is understood."


def _plot_energy(samples: list[dict[str, Any]], config: Prototype3DConfig, path: Path) -> None:
    times = [row["time"] for row in samples]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    ax.plot(times, [row["core_energy"] for row in samples], label="core")
    ax.plot(times, [row["shell_peak_energy"] for row in samples], label="shell peak")
    ax.plot(times, [row["total_energy"] for row in samples], label="total", alpha=0.7)
    ax.axvline(config.drive_cutoff_time, color="#666666", linestyle="--", linewidth=1)
    ax.set_title(f"3D energy metrics: {config.name}")
    ax.set_xlabel("time")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_shell(samples: list[dict[str, Any]], config: Prototype3DConfig, path: Path) -> None:
    times = [row["time"] for row in samples]
    fig, ax1 = plt.subplots(figsize=(8, 4), dpi=140)
    ax1.plot(times, [row["shell_peak_energy"] for row in samples], color="#3366aa", label="shell peak energy")
    ax1.axvline(config.drive_cutoff_time, color="#666666", linestyle="--", linewidth=1)
    ax1.set_xlabel("time")
    ax1.set_ylabel("shell peak energy")
    ax2 = ax1.twinx()
    ax2.plot(times, [row["shell_peak_radius"] for row in samples], color="#aa3377", alpha=0.75, label="shell peak radius")
    ax2.set_ylabel("shell peak radius")
    ax1.set_title(f"3D shell peak: {config.name}")
    ax1.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_radial_heatmap(rows: list[dict[str, Any]], bins: np.ndarray, path: Path) -> None:
    if not rows:
        return
    values = np.asarray([[row.get(f"bin_{idx}", 0.0) for idx in range(len(bins) - 1)] for row in rows], dtype=float)
    times = [row["time"] for row in rows]
    centers = 0.5 * (bins[:-1] + bins[1:])
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    mesh = ax.pcolormesh(times, centers, values.T, shading="auto")
    ax.set_xlabel("time")
    ax.set_ylabel("radius")
    ax.set_title("3D radial energy profile")
    fig.colorbar(mesh, ax=ax, label="mean energy")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _save_midplane(energy: np.ndarray, path: Path, title: str) -> None:
    mid = energy.shape[0] // 2
    fig, ax = plt.subplots(figsize=(5, 4), dpi=140)
    im = ax.imshow(energy[mid], origin="lower", cmap="magma")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _json_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if key != "best_radial_profile"}


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, np.generic):
        return _csv_value(value.item())
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _format(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    return f"{float(value):.6g}"
