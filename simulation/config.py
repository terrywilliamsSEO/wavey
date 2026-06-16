"""Configuration models for lattice wave experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass
class DefectConfig:
    """Central defect or cavity settings."""

    radius: int = 5
    radius_physical: float | None = None
    stiffness_multiplier: float = 0.55
    damping_multiplier: float = 0.35
    coupling_multiplier: float = 0.55
    nonlinear_strength: float = 0.0


@dataclass
class DriverConfig:
    """Boundary wave emitter settings."""

    sides: tuple[str, ...] = ("left", "right", "top", "bottom")
    frequency: float = 0.95
    amplitude: float = 0.55
    phase_offset: float = 0.0
    mode: str = "continuous"
    drive_cutoff_time: float = 16.0
    phase_mode: str = "uniform"
    rotating_phase_winding: int = 1
    emitter_width: int = 1
    emitter_width_physical: float | None = None


@dataclass
class SimulationConfig:
    """Numerical and physical settings for a single run."""

    grid_size: int = 41
    grid_height: int | None = None
    steps: int = 700
    dt: float = 0.04
    fixed_domain: bool = False
    domain_width: float | None = None
    domain_height: float | None = None
    base_stiffness: float = 1.0
    coupling_strength: float = 0.9
    global_damping: float = 0.02
    nonlinear_strength: float = 0.0
    boundary_mode: str = "reflective"
    boundary_damping_width: int = 6
    boundary_damping_width_physical: float | None = None
    boundary_damping_strength: float = 0.08
    core_radius: int | None = None
    core_radius_physical: float | None = None
    sample_every: int = 1
    defect: DefectConfig = field(default_factory=DefectConfig)
    driver: DriverConfig = field(default_factory=DriverConfig)
    seed: int = 7

    @property
    def effective_core_radius(self) -> int:
        return self.core_radius if self.core_radius is not None else self.defect.radius + 1

    @property
    def nx(self) -> int:
        return int(self.grid_size)

    @property
    def ny(self) -> int:
        return int(self.grid_height if self.grid_height is not None else self.grid_size)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.ny, self.nx)

    @property
    def physical_domain_width(self) -> float:
        if self.domain_width is not None:
            return float(self.domain_width)
        return float(max(self.nx - 1, 1))

    @property
    def physical_domain_height(self) -> float:
        if self.domain_height is not None:
            return float(self.domain_height)
        return float(max(self.ny - 1, 1))

    @property
    def dx(self) -> float:
        if not self.fixed_domain:
            return 1.0
        return self.physical_domain_width / float(max(self.nx - 1, 1))

    @property
    def dy(self) -> float:
        if not self.fixed_domain:
            return 1.0
        return self.physical_domain_height / float(max(self.ny - 1, 1))

    @property
    def cell_area(self) -> float:
        return self.dx * self.dy if self.fixed_domain else 1.0

    @property
    def effective_defect_radius(self) -> float:
        if self.fixed_domain and self.defect.radius_physical is not None:
            return float(self.defect.radius_physical)
        return float(self.defect.radius)

    @property
    def effective_core_radius_value(self) -> float:
        if self.fixed_domain and self.core_radius_physical is not None:
            return float(self.core_radius_physical)
        return float(self.effective_core_radius)

    @property
    def effective_boundary_damping_width(self) -> float:
        if self.fixed_domain and self.boundary_damping_width_physical is not None:
            return float(self.boundary_damping_width_physical)
        return float(self.boundary_damping_width)

    @property
    def effective_emitter_width(self) -> float:
        if self.fixed_domain and self.driver.emitter_width_physical is not None:
            return float(self.driver.emitter_width_physical)
        return float(max(1, self.driver.emitter_width))


@dataclass
class SweepConfig:
    """Sweep settings. The default scans each dimension around a baseline."""

    max_runs: int = 12
    seed: int = 7
    output_root: str = "runs"
    sampling_mode: str = "hybrid"
    report_top_n: int = 10
    export_frame_sequences: bool = False
    frame_sequence_top_n: int = 3
    frame_sequence_count: int = 8
    drive_frequency: tuple[float, ...] = (0.55, 0.75, 0.95, 1.15, 1.35)
    drive_amplitude: tuple[float, ...] = (0.25, 0.55, 0.9)
    defect_radius: tuple[int, ...] = (3, 5, 7)
    defect_stiffness_multiplier: tuple[float, ...] = (0.35, 0.65, 1.4)
    defect_damping_multiplier: tuple[float, ...] = (0.2, 0.75, 1.3)
    defect_coupling_multiplier: tuple[float, ...] = (0.25, 0.6, 1.1)
    global_damping: tuple[float, ...] = (0.01, 0.025, 0.05)
    coupling_strength: tuple[float, ...] = (0.65, 0.95, 1.25)
    nonlinear_strength: tuple[float, ...] = (0.0, 0.08, 0.2)
    boundary_mode: tuple[str, ...] = ("reflective", "sponge")
    boundary_damping_width: tuple[int, ...] = (6,)
    boundary_damping_strength: tuple[float, ...] = (0.08,)
    phase_mode: tuple[str, ...] = ("uniform", "rotating")


def _coerce_tuple(value: Any) -> tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def simulation_config_from_dict(data: dict[str, Any]) -> SimulationConfig:
    data = dict(data)
    defect_data = data.pop("defect", {})
    driver_data = data.pop("driver", {})
    if "sides" in driver_data:
        driver_data["sides"] = tuple(driver_data["sides"])
    return SimulationConfig(
        **data,
        defect=DefectConfig(**defect_data),
        driver=DriverConfig(**driver_data),
    )


def sweep_config_from_dict(data: dict[str, Any]) -> SweepConfig:
    data = dict(data)
    tuple_fields = {
        "drive_frequency",
        "drive_amplitude",
        "defect_radius",
        "defect_stiffness_multiplier",
        "defect_damping_multiplier",
        "defect_coupling_multiplier",
        "global_damping",
        "coupling_strength",
        "nonlinear_strength",
        "boundary_mode",
        "boundary_damping_width",
        "boundary_damping_strength",
        "phase_mode",
    }
    for key in tuple_fields.intersection(data):
        data[key] = _coerce_tuple(data[key])
    return SweepConfig(**data)


def load_json_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: str | Path, data: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def to_jsonable_config(config: SimulationConfig) -> dict[str, Any]:
    return asdict(config)
