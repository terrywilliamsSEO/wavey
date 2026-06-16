"""Single-run and sweep orchestration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any
import copy
import random

import numpy as np

from .anomaly_detection import summarize_run
from .band_analysis import annotate_frequency_band_context
from .config import SimulationConfig, SweepConfig, save_json, to_jsonable_config
from .config import load_json_config, simulation_config_from_dict
from .cross_run_detection import annotate_cross_run_thresholds
from .lattice import Lattice2D
from .metrics import add_posthoc_metrics, core_signal, sample_metrics, write_metrics_csv
from .plots import plot_core_spectrum, plot_core_vs_outer, plot_energy_well_ratio, save_heatmap
from .reporting import write_sweep_report
from .stability import estimate_stability


VALID_SAMPLING_MODES = {"hybrid", "random", "stratified", "grid"}


def run_single_experiment(
    config: SimulationConfig,
    output_root: str | Path = "runs",
    run_id: str | None = None,
) -> dict[str, Any]:
    run_id = run_id or _new_run_id()
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    lattice = Lattice2D(config)
    samples: list[dict[str, Any]] = []
    core_displacement: list[float] = []
    best_ratio = -np.inf
    best_energy_density: np.ndarray | None = None
    final_energy_density: np.ndarray | None = None

    for step in range(config.steps):
        time = step * config.dt
        lattice.step(time, config.dt)

        if step % config.sample_every != 0:
            continue

        energy = lattice.energy_density()
        final_energy_density = energy.copy()
        row = sample_metrics(step, time, lattice, energy)
        samples.append(row)
        core_displacement.append(core_signal(lattice))

        if row["energy_well_ratio"] > best_ratio:
            best_ratio = row["energy_well_ratio"]
            best_energy_density = energy.copy()

    if final_energy_density is None or best_energy_density is None:
        raise RuntimeError("Simulation produced no metric samples. Check steps and sample_every.")

    add_posthoc_metrics(samples, core_displacement, config)
    summary = summarize_run(run_id, config, samples, best_energy_density)
    summary["path"] = str(run_dir)
    summary["stability"] = estimate_stability(config)
    best_energy_path = run_dir / "best_energy_density.npy"
    np.save(best_energy_path, best_energy_density)
    summary["best_energy_density_path"] = str(best_energy_path)

    config_payload = to_jsonable_config(config)
    config_payload["run_id"] = run_id
    save_json(run_dir / "config.json", config_payload)
    write_metrics_csv(run_dir / "metrics.csv", samples)
    save_json(run_dir / "summary.json", summary)
    save_heatmap(final_energy_density, config, run_dir / "final_heatmap.png", "Final energy density")
    save_heatmap(best_energy_density, config, run_dir / "best_frame.png", "Best energy-well event")
    plot_energy_well_ratio(samples, run_dir / "energy_well_ratio_plot.png")
    plot_core_vs_outer(samples, run_dir / "core_vs_outer_energy_plot.png")
    plot_core_spectrum(core_displacement, config.dt * max(1, config.sample_every), run_dir / "core_spectrum_plot.png")

    return summary


def run_sweep(base_config: SimulationConfig, sweep_config: SweepConfig) -> list[dict[str, Any]]:
    output_root = Path(sweep_config.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    sweep_id = datetime.now().strftime("sweep_%Y%m%d_%H%M%S")
    points = generate_sweep_points(sweep_config)
    configs = [_apply_point(base_config, point, sweep_config.seed + idx) for idx, point in enumerate(points)]
    plan_path = output_root / f"{sweep_id}_plan.json"
    save_json(
        plan_path,
        {
            "sweep_id": sweep_id,
            "sampling_mode": sweep_config.sampling_mode,
            "seed": sweep_config.seed,
            "max_runs": sweep_config.max_runs,
            "run_count": len(points),
            "points": points,
        },
    )

    summaries = []
    for idx, config in enumerate(configs, start=1):
        run_id = f"{sweep_id}_{idx:03d}"
        summary = run_single_experiment(config, output_root=output_root, run_id=run_id)
        summaries.append(summary)

    annotated = annotate_cross_run_thresholds(summaries)
    annotated = annotate_frequency_band_context(annotated)
    ranked = sorted(annotated, key=lambda item: item["anomaly_score"], reverse=True)
    export_top_frame_sequences(ranked, sweep_config)
    summary_path = output_root / f"{sweep_id}_summary.json"
    save_json(
        summary_path,
        {
            "sweep_id": sweep_id,
            "sampling_mode": sweep_config.sampling_mode,
            "seed": sweep_config.seed,
            "run_count": len(ranked),
            "plan_path": str(plan_path),
            "runs": ranked,
        },
    )
    report_path = write_sweep_report(output_root, sweep_id, ranked, sweep_config, plan_path, summary_path)
    summary_payload = {
        "sweep_id": sweep_id,
        "sampling_mode": sweep_config.sampling_mode,
        "seed": sweep_config.seed,
        "run_count": len(ranked),
        "plan_path": str(plan_path),
        "report_path": str(report_path),
        "runs": ranked,
    }
    save_json(summary_path, summary_payload)
    return ranked


def export_top_frame_sequences(ranked: list[dict[str, Any]], sweep_config: SweepConfig) -> None:
    if not sweep_config.export_frame_sequences:
        return
    top_n = min(max(0, sweep_config.frame_sequence_top_n), len(ranked))
    for summary in ranked[:top_n]:
        run_dir = Path(summary["path"])
        config_data = load_json_config(run_dir / "config.json")
        config_data.pop("run_id", None)
        config = simulation_config_from_dict(config_data)
        frame_paths = export_frame_sequence(config, run_dir, sweep_config.frame_sequence_count)
        summary["frame_sequence_path"] = str(run_dir / "frame_sequence")
        summary["frame_sequence_frames"] = [str(path) for path in frame_paths]
        save_json(run_dir / "summary.json", summary)


def export_frame_sequence(config: SimulationConfig, run_dir: str | Path, frame_count: int) -> list[Path]:
    run_dir = Path(run_dir)
    frame_dir = run_dir / "frame_sequence"
    frame_dir.mkdir(parents=True, exist_ok=True)
    count = min(max(0, int(frame_count)), config.steps)
    if count == 0:
        return []

    target_steps = sorted(set(int(step) for step in np.linspace(0, config.steps - 1, count)))
    target_lookup = set(target_steps)
    lattice = Lattice2D(config)
    paths: list[Path] = []
    frame_index = 0
    for step in range(config.steps):
        time = step * config.dt
        lattice.step(time, config.dt)
        if step not in target_lookup:
            continue
        energy = lattice.energy_density()
        path = frame_dir / f"frame_{frame_index:03d}.png"
        save_heatmap(energy, config, path, f"Energy frame t={time:.3f}")
        paths.append(path)
        frame_index += 1
    return paths


def generate_sweep_configs(base_config: SimulationConfig, sweep_config: SweepConfig) -> list[SimulationConfig]:
    return [
        _apply_point(base_config, point, sweep_config.seed + idx)
        for idx, point in enumerate(generate_sweep_points(sweep_config))
    ]


def generate_sweep_points(sweep_config: SweepConfig) -> list[dict[str, Any]]:
    space = _parameter_space(sweep_config)
    mode = sweep_config.sampling_mode
    if mode not in VALID_SAMPLING_MODES:
        raise ValueError(f"Unsupported sampling_mode: {mode}. Expected one of {sorted(VALID_SAMPLING_MODES)}")
    if sweep_config.max_runs <= 0:
        return []

    if mode == "hybrid":
        return _hybrid_points(space, sweep_config)
    if mode == "random":
        return _random_points(space, sweep_config)
    if mode == "stratified":
        return _stratified_points(space, sweep_config)
    if mode == "grid":
        return _grid_points(space, sweep_config)

    raise AssertionError(f"Unhandled sampling mode: {mode}")


def _hybrid_points(space: dict[str, tuple[Any, ...]], sweep_config: SweepConfig) -> list[dict[str, Any]]:
    baseline = {key: values[len(values) // 2] for key, values in space.items()}
    baseline["phase_mode"] = space["phase_mode"][0]
    baseline["boundary_mode"] = space["boundary_mode"][0]

    candidates: list[dict[str, Any]] = [dict(baseline)]
    for key, values in space.items():
        for value in values:
            point = dict(baseline)
            point[key] = value
            if point not in candidates:
                candidates.append(point)

    rng = random.Random(sweep_config.seed)
    all_random = [dict(zip(space.keys(), values)) for values in product(*space.values())]
    rng.shuffle(all_random)
    for point in all_random:
        if len(candidates) >= sweep_config.max_runs:
            break
        if point not in candidates:
            candidates.append(point)

    return candidates[: sweep_config.max_runs]


def _random_points(space: dict[str, tuple[Any, ...]], sweep_config: SweepConfig) -> list[dict[str, Any]]:
    points = _all_grid_points(space)
    rng = random.Random(sweep_config.seed)
    rng.shuffle(points)
    return points[: sweep_config.max_runs]


def _stratified_points(space: dict[str, tuple[Any, ...]], sweep_config: SweepConfig) -> list[dict[str, Any]]:
    rng = random.Random(sweep_config.seed)
    shuffled_values: dict[str, list[Any]] = {}
    offsets: dict[str, int] = {}
    for key, values in space.items():
        shuffled = list(values)
        rng.shuffle(shuffled)
        shuffled_values[key] = shuffled
        offsets[key] = rng.randrange(len(shuffled)) if shuffled else 0

    points: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    attempts = max(sweep_config.max_runs * 4, sweep_config.max_runs + 8)
    keys = list(space)
    for idx in range(attempts):
        point = {}
        for key in keys:
            values = shuffled_values[key]
            point[key] = values[(idx + offsets[key]) % len(values)]
        signature = _point_signature(point)
        if signature not in seen:
            points.append(point)
            seen.add(signature)
        if len(points) >= sweep_config.max_runs:
            return points

    for point in _random_points(space, sweep_config):
        signature = _point_signature(point)
        if signature not in seen:
            points.append(point)
            seen.add(signature)
        if len(points) >= sweep_config.max_runs:
            break
    return points


def _grid_points(space: dict[str, tuple[Any, ...]], sweep_config: SweepConfig) -> list[dict[str, Any]]:
    return _all_grid_points(space)[: sweep_config.max_runs]


def _all_grid_points(space: dict[str, tuple[Any, ...]]) -> list[dict[str, Any]]:
    return [dict(zip(space.keys(), values)) for values in product(*space.values())]


def _point_signature(point: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(point.items()))


def _parameter_space(sweep_config: SweepConfig) -> dict[str, tuple[Any, ...]]:
    return {
        "drive_frequency": tuple(sweep_config.drive_frequency),
        "drive_amplitude": tuple(sweep_config.drive_amplitude),
        "defect_radius": tuple(sweep_config.defect_radius),
        "defect_stiffness_multiplier": tuple(sweep_config.defect_stiffness_multiplier),
        "defect_damping_multiplier": tuple(sweep_config.defect_damping_multiplier),
        "defect_coupling_multiplier": tuple(sweep_config.defect_coupling_multiplier),
        "global_damping": tuple(sweep_config.global_damping),
        "coupling_strength": tuple(sweep_config.coupling_strength),
        "nonlinear_strength": tuple(sweep_config.nonlinear_strength),
        "boundary_mode": tuple(sweep_config.boundary_mode),
        "boundary_damping_width": tuple(sweep_config.boundary_damping_width),
        "boundary_damping_strength": tuple(sweep_config.boundary_damping_strength),
        "phase_mode": tuple(sweep_config.phase_mode),
    }


def _apply_point(base_config: SimulationConfig, point: dict[str, Any], seed: int) -> SimulationConfig:
    config = copy.deepcopy(base_config)
    config.seed = seed
    config.driver = replace(
        config.driver,
        frequency=float(point["drive_frequency"]),
        amplitude=float(point["drive_amplitude"]),
        phase_mode=str(point["phase_mode"]),
    )
    config.defect = replace(
        config.defect,
        radius=int(point["defect_radius"]),
        stiffness_multiplier=float(point["defect_stiffness_multiplier"]),
        damping_multiplier=float(point["defect_damping_multiplier"]),
        coupling_multiplier=float(point["defect_coupling_multiplier"]),
    )
    config.global_damping = float(point["global_damping"])
    config.coupling_strength = float(point["coupling_strength"])
    config.nonlinear_strength = float(point["nonlinear_strength"])
    config.boundary_mode = str(point["boundary_mode"])
    config.boundary_damping_width = int(point["boundary_damping_width"])
    config.boundary_damping_strength = float(point["boundary_damping_strength"])
    return config


def _new_run_id() -> str:
    return datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
