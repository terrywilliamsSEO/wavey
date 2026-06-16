"""Time-resolved mode-shape diagnostics for single validation runs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import SimulationConfig, load_json_config, save_json, simulation_config_from_dict
from .lattice import Lattice2D
from .mode_diagnostics import radial_energy_profile, radial_profile_correlation, shape_correlation
from .mode_diagnostics import spatial_distribution_metrics
from .plots import save_heatmap


EPSILON = 1e-12


@dataclass
class DiagnosticOptions:
    frame_interval: int = 20
    window_steps: int = 30
    reference_frequencies: tuple[float, ...] = (0.92, 0.98, 1.04, 1.08)
    save_frame_pngs: bool = False


def diagnose_existing_run(
    run_dir: str | Path,
    *,
    options: DiagnosticOptions | None = None,
    reference_root: str | Path | None = None,
) -> dict[str, Any]:
    """Generate time-resolved mode-shape diagnostics for an existing run."""

    options = options or DiagnosticOptions()
    run_dir = Path(run_dir)
    config_data = load_json_config(run_dir / "config.json")
    config_data.pop("run_id", None)
    config = simulation_config_from_dict(config_data)
    summary = load_json_config(run_dir / "summary.json")
    samples = _read_metrics(run_dir / "metrics.csv")
    if not samples:
        raise RuntimeError(f"No metrics found for diagnostic run: {run_dir}")

    diagnostics_dir = run_dir / "mode_shape_diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)

    target_steps = _diagnostic_steps(config, samples, options)
    frames = _capture_diagnostic_frames(config, run_dir, diagnostics_dir, target_steps, options)
    frame_rows, radial_rows, radial_bins = _analyze_frames(config, frames, samples)
    _write_csv(diagnostics_dir / "frame_mode_diagnostics.csv", frame_rows)
    _write_csv(diagnostics_dir / "radial_profile_timeseries.csv", radial_rows)
    _write_frame_timestamps(diagnostics_dir / "frame_timestamps.csv", frames)

    angular_rows = _angular_mode_rows(config, frames, frame_rows)
    _write_csv(diagnostics_dir / "angular_mode_timeseries.csv", angular_rows)

    references = _find_reference_summaries(
        reference_root if reference_root is not None else run_dir.parent,
        options.reference_frequencies,
        exclude_run_dir=run_dir,
    )
    reference_rows = _reference_comparison_rows(config, frames, references)
    if reference_rows:
        _write_csv(diagnostics_dir / "reference_mode_comparison.csv", reference_rows)

    plots = _write_plots(diagnostics_dir, frame_rows, radial_rows, radial_bins, angular_rows, reference_rows, summary, config)
    breathing = _detect_breathing_state(frame_rows, radial_rows, config)
    transition = _detect_mode_transition(frame_rows, radial_rows, config)
    angular = _detect_angular_modes(angular_rows, config)
    reference = _detect_reference_relationship(reference_rows, summary)

    labels = _diagnostic_labels(breathing, transition, angular, reference)
    for label in labels:
        if label not in summary.setdefault("detected_event_labels", []):
            summary["detected_event_labels"].append(label)

    diagnostic_summary = {
        "run_id": summary.get("run_id"),
        "diagnostics_path": str(diagnostics_dir),
        "frame_count": len(frame_rows),
        "best_energy_well_ratio": float(summary.get("best_energy_well_ratio", 0.0)),
        "retention_score": float(summary.get("retention_score", 0.0)),
        "cutoff_frame_time": _special_frame_time(frame_rows, "cutoff"),
        "early_tail_frame_time": _special_frame_time(frame_rows, "early_tail"),
        "best_frame_time": _special_frame_time(frame_rows, "best"),
        "correlation_summary": _correlation_summary(frame_rows),
        "radial_drift_summary": _radial_drift_summary(frame_rows),
        "breathing_detection": breathing,
        "mode_transition_detection": transition,
        "angular_detection": angular,
        "reference_comparison": reference,
        "plots": plots,
    }
    report_path = _write_report(run_dir, diagnostics_dir, summary, config, diagnostic_summary)
    diagnostic_summary["report_path"] = str(report_path)

    summary["mode_shape_diagnostics"] = diagnostic_summary
    summary["mode_shape_diagnostics_report"] = str(report_path)
    summary["plain_language_interpretation"] = _updated_interpretation(
        summary.get("plain_language_interpretation", ""),
        breathing,
        transition,
        angular,
        reference,
    )
    save_json(run_dir / "summary.json", summary)
    save_json(diagnostics_dir / "mode_shape_diagnostics_summary.json", diagnostic_summary)
    return diagnostic_summary


def _read_metrics(path: Path) -> list[dict[str, float]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        rows = []
        for row in csv.DictReader(fh):
            converted: dict[str, float] = {}
            for key, value in row.items():
                if key == "max_amplitude_location":
                    continue
                try:
                    converted[key] = float(value)
                except (TypeError, ValueError):
                    pass
            rows.append(converted)
        return rows


def _diagnostic_steps(
    config: SimulationConfig,
    samples: list[dict[str, float]],
    options: DiagnosticOptions,
) -> list[int]:
    interval = max(1, int(options.frame_interval))
    window = max(1, int(options.window_steps))
    local_stride = max(1, interval // 5)
    steps = {0, config.steps - 1}
    steps.update(range(0, config.steps, interval))

    best_sample = max(samples, key=lambda row: row.get("energy_well_ratio", 0.0))
    best_step = int(best_sample["step"])
    cutoff_time = config.driver.drive_cutoff_time
    cutoff_step = _nearest_sample_step(samples, cutoff_time if cutoff_time is not None else 0.0)
    end_step = config.steps - 1
    early_tail_step = cutoff_step + max(interval, int((end_step - cutoff_step) * 0.1))

    for center in {cutoff_step, best_step, early_tail_step, end_step}:
        start = max(0, center - window)
        stop = min(config.steps - 1, center + window)
        steps.update(range(start, stop + 1, local_stride))

    if cutoff_step < end_step:
        for fraction in (0.25, 0.5, 0.75, 0.9, 1.0):
            steps.add(int(round(cutoff_step + (end_step - cutoff_step) * fraction)))
        late_start = int(round(cutoff_step + (end_step - cutoff_step) * 0.75))
        steps.update(range(late_start, end_step + 1, max(1, interval // 2)))

    return sorted(step for step in steps if 0 <= step < config.steps)


def _nearest_sample_step(samples: list[dict[str, float]], time: float) -> int:
    return int(min(samples, key=lambda row: abs(row.get("time", 0.0) - time)).get("step", 0.0))


def _capture_diagnostic_frames(
    config: SimulationConfig,
    run_dir: Path,
    diagnostics_dir: Path,
    target_steps: list[int],
    options: DiagnosticOptions,
) -> list[dict[str, Any]]:
    energy_npy_dir = diagnostics_dir / "energy_frames_npy"
    displacement_npy_dir = diagnostics_dir / "displacement_frames_npy"
    energy_png_dir = diagnostics_dir / "energy_frames"
    displacement_png_dir = diagnostics_dir / "displacement_frames"
    for directory in (energy_npy_dir, displacement_npy_dir, energy_png_dir, displacement_png_dir):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)

    target_lookup = set(target_steps)
    lattice = Lattice2D(config)
    frames: list[dict[str, Any]] = []
    frame_index = 0
    for step in range(config.steps):
        time = step * config.dt
        lattice.step(time, config.dt)
        if step not in target_lookup:
            continue

        energy = lattice.energy_density()
        displacement = lattice.u.copy()
        energy_path = energy_npy_dir / f"energy_{frame_index:04d}.npy"
        displacement_path = displacement_npy_dir / f"displacement_{frame_index:04d}.npy"
        np.save(energy_path, energy)
        np.save(displacement_path, displacement)

        energy_png_path = energy_png_dir / f"energy_{frame_index:04d}.png"
        displacement_png_path = displacement_png_dir / f"displacement_{frame_index:04d}.png"
        if options.save_frame_pngs:
            save_heatmap(energy, config, energy_png_path, f"Energy t={time:.3f}")
            _save_signed_heatmap(displacement, config, displacement_png_path, f"Displacement t={time:.3f}")

        frames.append(
            {
                "frame_index": frame_index,
                "step": step,
                "time": float(time),
                "energy": energy,
                "displacement": displacement,
                "energy_path": str(energy_path),
                "displacement_path": str(displacement_path),
                "energy_png_path": str(energy_png_path) if options.save_frame_pngs else "",
                "displacement_png_path": str(displacement_png_path) if options.save_frame_pngs else "",
            }
        )
        frame_index += 1
    return frames


def _save_signed_heatmap(values: np.ndarray, config: SimulationConfig, path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 6), dpi=120)
    limit = float(np.max(np.abs(values))) if values.size else 1.0
    if limit <= EPSILON:
        limit = 1.0
    im = ax.imshow(values, origin="upper", cmap="coolwarm", vmin=-limit, vmax=limit)
    center_x = (config.nx - 1) / 2.0
    center_y = (config.ny - 1) / 2.0
    radius_scale = 1.0 / config.dx if config.fixed_domain else 1.0
    circle = plt.Circle(
        (center_x, center_y),
        config.effective_defect_radius * radius_scale,
        edgecolor="black",
        facecolor="none",
        linestyle="--",
    )
    ax.add_patch(circle)
    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    fig.colorbar(im, ax=ax, label="displacement")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _analyze_frames(
    config: SimulationConfig,
    frames: list[dict[str, Any]],
    samples: list[dict[str, float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[float]]:
    best_time = float(max(samples, key=lambda row: row.get("energy_well_ratio", 0.0)).get("time", 0.0))
    cutoff_time = config.driver.drive_cutoff_time if config.driver.drive_cutoff_time is not None else 0.0
    end_time = float(samples[-1].get("time", 0.0))
    early_tail_time = cutoff_time + max(config.dt, (end_time - cutoff_time) * 0.1)

    best_frame = _nearest_frame(frames, best_time)
    cutoff_frame = _nearest_frame(frames, cutoff_time)
    early_tail_frame = _nearest_frame(frames, early_tail_time)

    previous_energy = None
    frame_rows: list[dict[str, Any]] = []
    radial_rows: list[dict[str, Any]] = []
    max_radial_bins = 0
    radial_bins: list[float] = []
    radial_profiles = []

    for frame in frames:
        energy = frame["energy"]
        radial = radial_energy_profile(energy, config)
        radial_profiles.append(radial["mass"])
        if radial["mass"].size > max_radial_bins:
            max_radial_bins = radial["mass"].size
            radial_bins = [float(value) for value in radial["radii"]]

        frame_row = _frame_metrics(config, frame, radial)
        frame_row.update(
            {
                "corr_prev_frame": shape_correlation(energy, previous_energy) if previous_energy is not None else None,
                "corr_to_best_frame": shape_correlation(energy, best_frame["energy"]),
                "corr_to_cutoff_frame": shape_correlation(energy, cutoff_frame["energy"]),
                "corr_to_early_tail_frame": shape_correlation(energy, early_tail_frame["energy"]),
                "special_frame": _special_frame_label(frame, best_frame, cutoff_frame, early_tail_frame),
            }
        )
        frame_rows.append(frame_row)
        previous_energy = energy

    best_profile = radial_energy_profile(best_frame["energy"], config)["mass"]
    cutoff_profile = radial_energy_profile(cutoff_frame["energy"], config)["mass"]
    previous_profile = None
    for frame, profile in zip(frames, radial_profiles):
        padded = np.pad(profile, (0, max_radial_bins - profile.size))
        row = {
            "time": frame["time"],
            "frame_index": frame["frame_index"],
            "corr_prev_profile": _profile_correlation(profile, previous_profile) if previous_profile is not None else None,
            "corr_to_best_profile": _profile_correlation(profile, best_profile),
            "corr_to_cutoff_profile": _profile_correlation(profile, cutoff_profile),
        }
        for idx, value in enumerate(padded):
            row[f"radius_{radial_bins[idx]:.2f}"] = float(value)
        radial_rows.append(row)
        previous_profile = profile

    return frame_rows, radial_rows, radial_bins


def _nearest_frame(frames: list[dict[str, Any]], time: float) -> dict[str, Any]:
    return min(frames, key=lambda frame: abs(float(frame["time"]) - time))


def _special_frame_label(
    frame: dict[str, Any],
    best_frame: dict[str, Any],
    cutoff_frame: dict[str, Any],
    early_tail_frame: dict[str, Any],
) -> str:
    labels = []
    if frame["frame_index"] == cutoff_frame["frame_index"]:
        labels.append("cutoff")
    if frame["frame_index"] == early_tail_frame["frame_index"]:
        labels.append("early_tail")
    if frame["frame_index"] == best_frame["frame_index"]:
        labels.append("best")
    return ",".join(labels)


def _frame_metrics(config: SimulationConfig, frame: dict[str, Any], radial: dict[str, np.ndarray]) -> dict[str, Any]:
    energy = frame["energy"]
    masks = Lattice2D._build_masks(config)
    total = float(np.sum(energy))
    core_energy = float(np.sum(energy[masks.core]))
    outer_energy = float(np.sum(energy[masks.outer]))
    radial_mass = radial["mass"]
    radial_peak_idx = int(np.argmax(radial_mass)) if radial_mass.size else 0
    radial_peak_radius = float(radial["radii"][radial_peak_idx]) if radial["radii"].size else 0.0
    radial_peak_value = float(radial_mass[radial_peak_idx]) if radial_mass.size else 0.0
    annulus_fraction = _annulus_fraction(energy, config, radial_peak_radius)
    spatial = spatial_distribution_metrics(energy)
    return {
        "time": frame["time"],
        "frame_index": frame["frame_index"],
        "step": frame["step"],
        "core_energy": core_energy,
        "outer_lattice_energy": outer_energy,
        "energy_well_ratio": core_energy / (outer_energy + EPSILON),
        "spatial_entropy": spatial["spatial_entropy"],
        "participation_fraction": spatial["participation_fraction"],
        "radial_peak_radius": radial_peak_radius,
        "radial_peak_value": radial_peak_value,
        "core_fraction": core_energy / (total + EPSILON),
        "annulus_fraction": annulus_fraction,
        "outer_fraction": outer_energy / (total + EPSILON),
    }


def _annulus_fraction(energy: np.ndarray, config: SimulationConfig, radial_peak_radius: float) -> float:
    rows, cols = np.indices(energy.shape, dtype=float)
    center_row = (energy.shape[0] - 1) / 2.0
    center_col = (energy.shape[1] - 1) / 2.0
    if config.fixed_domain:
        radius = np.sqrt(((rows - center_row) * config.dy) ** 2 + ((cols - center_col) * config.dx) ** 2)
        width = max(min(config.dx, config.dy), config.effective_defect_radius * 0.25)
        mask = np.abs(radius - radial_peak_radius) <= width
    else:
        radius = np.sqrt((rows - center_row) ** 2 + (cols - center_col) ** 2)
        peak_cells = radial_peak_radius * max(float(config.defect.radius), 1.0)
        width = max(1.0, config.defect.radius * 0.25)
        mask = np.abs(radius - peak_cells) <= width
    return float(np.sum(energy[mask]) / (np.sum(energy) + EPSILON))


def _profile_correlation(first: np.ndarray | None, second: np.ndarray | None) -> float | None:
    if first is None or second is None:
        return None
    length = max(first.size, second.size)
    a = np.pad(first, (0, length - first.size))
    b = np.pad(second, (0, length - second.size))
    a = a - float(np.mean(a))
    b = b - float(np.mean(b))
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= EPSILON:
        return None
    return float(np.clip(np.dot(a, b) / denominator, -1.0, 1.0))


def _angular_mode_rows(
    config: SimulationConfig,
    frames: list[dict[str, Any]],
    frame_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows, cols = np.indices(config.shape, dtype=float)
    center_row = (config.ny - 1) / 2.0
    center_col = (config.nx - 1) / 2.0
    if config.fixed_domain:
        y = (rows - center_row) * config.dy
        x = (cols - center_col) * config.dx
        radius = np.sqrt(y**2 + x**2)
        theta = np.arctan2(y, x)
        angular_width = max(min(config.dx, config.dy), config.effective_defect_radius * 0.25)
    else:
        radius = np.sqrt((rows - center_row) ** 2 + (cols - center_col) ** 2)
        theta = np.arctan2(rows - center_row, cols - center_col)
        angular_width = max(1.0, config.defect.radius * 0.25)

    out = []
    for frame, frame_row in zip(frames, frame_rows):
        energy = frame["energy"]
        if config.fixed_domain:
            peak_radius = float(frame_row["radial_peak_radius"])
        else:
            peak_radius = float(frame_row["radial_peak_radius"]) * max(float(config.defect.radius), 1.0)
        mask = np.abs(radius - peak_radius) <= angular_width
        if not np.any(mask) or float(np.sum(energy[mask])) <= EPSILON:
            mask = Lattice2D._build_masks(config).ring
        weights = energy[mask]
        angles = theta[mask]
        total = float(np.sum(weights))
        row: dict[str, Any] = {
            "time": frame["time"],
            "frame_index": frame["frame_index"],
            "radial_peak_radius": frame_row["radial_peak_radius"],
            "m0_strength": 1.0 if total > EPSILON else 0.0,
        }
        dominant_mode = 0
        dominant_strength = 0.0
        for mode in range(1, 5):
            if total <= EPSILON:
                component = 0.0 + 0.0j
            else:
                component = np.sum(weights * np.exp(1j * mode * angles)) / (total + EPSILON)
            strength = float(np.abs(component))
            phase = float(np.angle(component))
            row[f"m{mode}_strength"] = strength
            row[f"m{mode}_phase"] = phase
            if strength > dominant_strength:
                dominant_strength = strength
                dominant_mode = mode
        row["dominant_mode"] = dominant_mode
        row["dominant_strength"] = dominant_strength
        row["angular_phase"] = row.get(f"m{dominant_mode}_phase", 0.0) if dominant_mode else 0.0
        out.append(row)
    return out


def _find_reference_summaries(
    reference_root: str | Path,
    reference_frequencies: tuple[float, ...],
    *,
    exclude_run_dir: Path,
) -> list[dict[str, Any]]:
    root = Path(reference_root)
    target = {round(float(freq), 8) for freq in reference_frequencies}
    summaries: list[dict[str, Any]] = []
    for summary_path in sorted(root.glob("sweep_*_summary.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        data = load_json_config(summary_path)
        runs = data.get("runs", [])
        by_freq = {}
        for summary in runs:
            run_path = Path(summary.get("path", ""))
            if run_path.resolve() == exclude_run_dir.resolve():
                continue
            config_path = run_path / "config.json"
            if not config_path.exists():
                continue
            config = load_json_config(config_path)
            freq = config.get("driver", {}).get("frequency")
            if freq is None:
                continue
            rounded = round(float(freq), 8)
            if rounded in target and (run_path / "best_energy_density.npy").exists():
                by_freq[rounded] = summary
        if by_freq:
            summaries = [by_freq[freq] for freq in sorted(by_freq)]
            break
    return summaries


def _reference_comparison_rows(
    config: SimulationConfig,
    frames: list[dict[str, Any]],
    references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    reference_payloads = []
    for reference in references:
        path = Path(reference["path"])
        config_data = load_json_config(path / "config.json")
        config_data.pop("run_id", None)
        ref_config = simulation_config_from_dict(config_data)
        energy = np.load(path / "best_energy_density.npy")
        frequency = float(load_json_config(path / "config.json")["driver"]["frequency"])
        reference_payloads.append((reference, ref_config, energy, frequency))

    for frame in frames:
        for reference, ref_config, ref_energy, frequency in reference_payloads:
            rows.append(
                {
                    "time": frame["time"],
                    "frame_index": frame["frame_index"],
                    "reference_frequency": frequency,
                    "reference_run_id": reference["run_id"],
                    "shape_correlation": shape_correlation(frame["energy"], ref_energy),
                    "radial_profile_correlation": radial_profile_correlation(
                        frame["energy"],
                        config,
                        ref_energy,
                        ref_config,
                    ),
                }
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})


def _write_frame_timestamps(path: Path, frames: list[dict[str, Any]]) -> None:
    rows = [
        {
            "frame_index": frame["frame_index"],
            "step": frame["step"],
            "time": frame["time"],
            "energy_path": frame["energy_path"],
            "displacement_path": frame["displacement_path"],
            "energy_png_path": frame["energy_png_path"],
            "displacement_png_path": frame["displacement_png_path"],
        }
        for frame in frames
    ]
    _write_csv(path, rows)


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    return value


def _write_plots(
    diagnostics_dir: Path,
    frame_rows: list[dict[str, Any]],
    radial_rows: list[dict[str, Any]],
    radial_bins: list[float],
    angular_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    config: SimulationConfig,
) -> dict[str, str]:
    plots = {
        "frame_correlation_plot": str(diagnostics_dir / "frame_correlation_plot.png"),
        "radial_peak_drift_plot": str(diagnostics_dir / "radial_peak_drift_plot.png"),
        "radial_profile_heatmap": str(diagnostics_dir / "radial_profile_heatmap.png"),
        "angular_mode_plot": str(diagnostics_dir / "angular_mode_plot.png"),
    }
    _plot_frame_correlations(frame_rows, summary, config, Path(plots["frame_correlation_plot"]))
    _plot_radial_peak_drift(frame_rows, summary, config, Path(plots["radial_peak_drift_plot"]))
    _plot_radial_profile_heatmap(radial_rows, radial_bins, Path(plots["radial_profile_heatmap"]), config)
    _plot_angular_modes(angular_rows, summary, config, Path(plots["angular_mode_plot"]))
    if reference_rows:
        plots["reference_mode_comparison_plot"] = str(diagnostics_dir / "reference_mode_comparison_plot.png")
        _plot_reference_comparison(reference_rows, summary, config, Path(plots["reference_mode_comparison_plot"]))
    return plots


def _plot_frame_correlations(
    frame_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    config: SimulationConfig,
    path: Path,
) -> None:
    times = [row["time"] for row in frame_rows]
    fig, ax = plt.subplots(figsize=(9, 4), dpi=140)
    for key, label in (
        ("corr_prev_frame", "previous frame"),
        ("corr_to_best_frame", "best frame"),
        ("corr_to_cutoff_frame", "cutoff frame"),
        ("corr_to_early_tail_frame", "early tail"),
    ):
        values = [np.nan if row[key] is None else row[key] for row in frame_rows]
        ax.plot(times, values, linewidth=1.3, label=label)
    _annotate_cutoff_best(ax, summary, config)
    ax.set_title("Frame mode-shape correlation")
    ax.set_xlabel("time")
    ax.set_ylabel("correlation")
    ax.set_ylim(-1.05, 1.05)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_radial_peak_drift(
    frame_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    config: SimulationConfig,
    path: Path,
) -> None:
    times = [row["time"] for row in frame_rows]
    radii = [row["radial_peak_radius"] for row in frame_rows]
    ratios = [row["energy_well_ratio"] for row in frame_rows]
    fig, ax = plt.subplots(figsize=(9, 4), dpi=140)
    ax.plot(times, radii, color="#3366aa", linewidth=1.4, label="radial peak radius")
    ax.set_xlabel("time")
    ax.set_ylabel(_radial_radius_label(config))
    ax.grid(True, alpha=0.25)
    ax2 = ax.twinx()
    ax2.plot(times, ratios, color="#aa3377", linewidth=1.0, alpha=0.7, label="energy-well ratio")
    ax2.set_ylabel("energy-well ratio")
    _annotate_cutoff_best(ax, summary, config)
    ax.set_title("Radial peak drift")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_radial_profile_heatmap(
    radial_rows: list[dict[str, Any]],
    radial_bins: list[float],
    path: Path,
    config: SimulationConfig,
) -> None:
    matrix = []
    times = []
    for row in radial_rows:
        times.append(row["time"])
        matrix.append([row.get(f"radius_{radius:.2f}", 0.0) for radius in radial_bins])
    values = np.asarray(matrix, dtype=float)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=140)
    extent = [min(radial_bins), max(radial_bins), max(times), min(times)] if radial_bins and times else None
    im = ax.imshow(values, aspect="auto", cmap="magma", extent=extent)
    ax.set_title("Radial energy profile over time")
    ax.set_xlabel(_radial_radius_label(config))
    ax.set_ylabel("time")
    fig.colorbar(im, ax=ax, label="normalized radial energy")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_angular_modes(
    angular_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    config: SimulationConfig,
    path: Path,
) -> None:
    times = [row["time"] for row in angular_rows]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), dpi=140, sharex=True)
    for mode in range(1, 5):
        ax1.plot(times, [row[f"m{mode}_strength"] for row in angular_rows], label=f"m={mode}", linewidth=1.2)
    ax1.set_title("Angular Fourier mode strengths")
    ax1.set_ylabel("strength")
    ax1.grid(True, alpha=0.25)
    ax1.legend(ncol=4, fontsize=8)
    dominant_phase = [row["angular_phase"] for row in angular_rows]
    ax2.plot(times, np.unwrap(dominant_phase), color="#117733", linewidth=1.2)
    _annotate_cutoff_best(ax2, summary, config)
    ax2.set_xlabel("time")
    ax2.set_ylabel("dominant phase")
    ax2.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_reference_comparison(
    reference_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    config: SimulationConfig,
    path: Path,
) -> None:
    frequencies = sorted({float(row["reference_frequency"]) for row in reference_rows})
    fig, ax = plt.subplots(figsize=(9, 4), dpi=140)
    for frequency in frequencies:
        rows = [row for row in reference_rows if float(row["reference_frequency"]) == frequency]
        ax.plot(
            [row["time"] for row in rows],
            [row["shape_correlation"] for row in rows],
            linewidth=1.2,
            label=f"{frequency:g} shape",
        )
    _annotate_cutoff_best(ax, summary, config)
    ax.set_title("Correlation to short-sweep peak references")
    ax.set_xlabel("time")
    ax.set_ylabel("shape correlation")
    ax.set_ylim(-1.05, 1.05)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _radial_radius_label(config: SimulationConfig) -> str:
    return "radial peak radius (physical units)" if config.fixed_domain else "radial peak radius / defect radius"


def _annotate_cutoff_best(ax: Any, summary: dict[str, Any], config: SimulationConfig) -> None:
    cutoff = config.driver.drive_cutoff_time
    if cutoff is not None:
        ax.axvline(cutoff, color="#555555", linestyle="--", linewidth=0.9, alpha=0.8)
    if "time_of_best_event" in summary:
        ax.axvline(float(summary["time_of_best_event"]), color="#aa3377", linestyle=":", linewidth=1.1, alpha=0.9)


def _detect_breathing_state(frame_rows: list[dict[str, Any]], radial_rows: list[dict[str, Any]], config: SimulationConfig) -> dict[str, Any]:
    post = [row for row in frame_rows if row["time"] > (config.driver.drive_cutoff_time or 0.0)]
    if len(post) < 8:
        return {"status": "inconclusive", "reason": "not enough post-cutoff frames", "label": None}
    values = np.asarray([row["core_energy"] for row in post], dtype=float)
    times = np.asarray([row["time"] for row in post], dtype=float)
    peaks = _local_peaks(values)
    if peaks.size:
        strong_cutoff = np.percentile(values, 55)
        peaks = peaks[values[peaks] >= strong_cutoff]
    intervals = np.diff(times[peaks]) if peaks.size >= 2 else np.array([])
    period = float(np.mean(intervals)) if intervals.size else None
    interval_cv = float(np.std(intervals) / (np.mean(intervals) + EPSILON)) if intervals.size else None
    envelope_strength = float((np.percentile(values, 90) - np.percentile(values, 10)) / (np.percentile(values, 90) + EPSILON))
    radial_values = np.asarray([row["radial_peak_radius"] for row in post], dtype=float)
    radial_range = float(np.max(radial_values) - np.min(radial_values)) if radial_values.size else 0.0
    profile_corrs = [
        float(row["corr_prev_profile"])
        for row in radial_rows
        if row.get("corr_prev_profile") not in (None, "") and row["time"] > (config.driver.drive_cutoff_time or 0.0)
    ]
    profile_coherence = float(np.nanmean(profile_corrs)) if profile_corrs else 0.0

    cycle_count = int(peaks.size)
    score = float(
        np.clip(envelope_strength, 0.0, 1.0) * 0.45
        + np.clip(radial_range / 0.75, 0.0, 1.0) * 0.25
        + np.clip((profile_coherence + 1.0) / 2.0, 0.0, 1.0) * 0.2
        + np.clip(cycle_count / 4.0, 0.0, 1.0) * 0.1
    )
    consistent = interval_cv is not None and interval_cv <= 0.65
    detected = cycle_count >= 3 and envelope_strength >= 0.2 and profile_coherence >= 0.35 and consistent
    return {
        "status": "detected" if detected else "inconclusive",
        "label": "breathing_localized_state" if detected else None,
        "estimated_period": period,
        "breathing_strength_score": score,
        "detected_cycles": cycle_count,
        "interval_cv": interval_cv,
        "core_envelope_strength": envelope_strength,
        "radial_peak_range": radial_range,
        "mean_radial_profile_correlation": profile_coherence,
    }


def _local_peaks(values: np.ndarray) -> np.ndarray:
    if values.size < 3:
        return np.array([], dtype=int)
    return np.where((values[1:-1] > values[:-2]) & (values[1:-1] > values[2:]))[0] + 1


def _detect_mode_transition(frame_rows: list[dict[str, Any]], radial_rows: list[dict[str, Any]], config: SimulationConfig) -> dict[str, Any]:
    post_indices = [idx for idx, row in enumerate(frame_rows) if row["time"] > (config.driver.drive_cutoff_time or 0.0)]
    if len(post_indices) < 10:
        return {"status": "inconclusive", "reason": "not enough post-cutoff frames", "label": None}

    best_candidate = None
    for idx in post_indices[3:-3]:
        before = frame_rows[max(0, idx - 5) : idx]
        after = frame_rows[idx : min(len(frame_rows), idx + 6)]
        pre_cutoff_corr = _mean(row["corr_to_cutoff_frame"] for row in before)
        post_cutoff_corr = _mean(row["corr_to_cutoff_frame"] for row in after)
        pre_best_corr = _mean(row["corr_to_best_frame"] for row in before)
        post_best_corr = _mean(row["corr_to_best_frame"] for row in after)
        prev_corr = frame_rows[idx].get("corr_prev_frame")
        entropy_shift = abs(_mean(row["spatial_entropy"] for row in after) - _mean(row["spatial_entropy"] for row in before))
        radial_shift = abs(_mean(row["radial_peak_radius"] for row in after) - _mean(row["radial_peak_radius"] for row in before))
        cutoff_drop = pre_cutoff_corr - post_cutoff_corr
        best_rise = post_best_corr - pre_best_corr
        sharpness = max(0.0, cutoff_drop) + max(0.0, best_rise) + np.clip(radial_shift / 0.75, 0.0, 1.0) * 0.35
        if prev_corr is not None and prev_corr < 0.45:
            sharpness += 0.25
        if entropy_shift > 0.12:
            sharpness += 0.15
        candidate = {
            "transition_time": frame_rows[idx]["time"],
            "pre_transition_avg_cutoff_corr": pre_cutoff_corr,
            "post_transition_avg_cutoff_corr": post_cutoff_corr,
            "pre_transition_avg_best_corr": pre_best_corr,
            "post_transition_avg_best_corr": post_best_corr,
            "transition_sharpness_score": float(np.clip(sharpness, 0.0, 1.0)),
            "radial_peak_shift": radial_shift,
            "entropy_shift": entropy_shift,
        }
        if best_candidate is None or candidate["transition_sharpness_score"] > best_candidate["transition_sharpness_score"]:
            best_candidate = candidate

    if best_candidate is None:
        return {"status": "inconclusive", "label": None}
    detected = (
        best_candidate["transition_sharpness_score"] >= 0.55
        and best_candidate["post_transition_avg_best_corr"] > best_candidate["pre_transition_avg_best_corr"] + 0.12
        and best_candidate["post_transition_avg_cutoff_corr"] < best_candidate["pre_transition_avg_cutoff_corr"] - 0.12
    )
    best_candidate["status"] = "detected" if detected else "inconclusive"
    best_candidate["label"] = "late_mode_transition" if detected else None
    return best_candidate


def _detect_angular_modes(angular_rows: list[dict[str, Any]], config: SimulationConfig) -> dict[str, Any]:
    post = [row for row in angular_rows if row["time"] > (config.driver.drive_cutoff_time or 0.0)]
    if len(post) < 5:
        return {"status": "inconclusive", "labels": [], "reason": "not enough post-cutoff angular samples"}
    strengths = {mode: np.asarray([row[f"m{mode}_strength"] for row in post], dtype=float) for mode in range(1, 5)}
    median_strengths = {mode: float(np.median(values)) for mode, values in strengths.items()}
    strongest_mode = max(median_strengths, key=median_strengths.get)
    strongest_strength = median_strengths[strongest_mode]
    max_nonzero = strongest_strength
    labels = []
    if max_nonzero < 0.25:
        labels.append("ring_mode_persistence")
    if strongest_strength >= 0.35:
        labels.append("angular_mode_structure")

    phases = np.asarray([row[f"m{strongest_mode}_phase"] for row in post], dtype=float)
    unwrapped = np.unwrap(phases)
    drift = float(np.max(unwrapped) - np.min(unwrapped)) if unwrapped.size else 0.0
    trend_r2 = _phase_trend_r2([row["time"] for row in post], unwrapped)
    if strongest_strength >= 0.28 and drift >= np.pi and trend_r2 >= 0.55:
        labels.append("rotating_tail_mode")

    return {
        "status": "detected" if labels else "inconclusive",
        "labels": labels,
        "strongest_angular_mode": int(strongest_mode),
        "strongest_angular_mode_strength": strongest_strength,
        "median_mode_strengths": median_strengths,
        "angular_phase_drift": drift,
        "angular_phase_trend_r2": trend_r2,
    }


def _phase_trend_r2(times: list[float], phases: np.ndarray) -> float:
    if len(times) < 3 or phases.size < 3:
        return 0.0
    x = np.asarray(times, dtype=float)
    y = np.asarray(phases, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    prediction = slope * x + intercept
    total = float(np.sum((y - np.mean(y)) ** 2))
    if total <= EPSILON:
        return 0.0
    residual = float(np.sum((y - prediction) ** 2))
    return float(np.clip(1.0 - residual / total, 0.0, 1.0))


def _detect_reference_relationship(reference_rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    if not reference_rows:
        return {"status": "not_available", "labels": [], "reason": "no reference best-frame arrays found"}
    best_time = float(summary.get("time_of_best_event", 0.0))
    rows_at_best = _nearest_reference_rows(reference_rows, best_time)
    if not rows_at_best:
        return {"status": "inconclusive", "labels": []}
    best_reference = max(rows_at_best, key=lambda row: row["shape_correlation"] if row["shape_correlation"] is not None else -2.0)
    max_shape = float(best_reference["shape_correlation"] or 0.0)
    max_radial = max(float(row["radial_profile_correlation"] or 0.0) for row in rows_at_best)
    labels = []
    if max_shape < 0.5 and max_radial < 0.7:
        labels.append("long_tail_distinct_from_short_peak")

    all_times = sorted({float(row["time"]) for row in reference_rows})
    late_times = all_times[int(len(all_times) * 0.65) :] if all_times else []
    late_rows = [row for row in reference_rows if float(row["time"]) in set(late_times)]
    if late_rows:
        by_freq: dict[float, list[float]] = {}
        for row in late_rows:
            by_freq.setdefault(float(row["reference_frequency"]), []).append(float(row["shape_correlation"] or 0.0))
        best_late_freq = max(by_freq, key=lambda freq: np.mean(by_freq[freq]))
        if abs(best_late_freq - 0.92) > 1e-8 and np.mean(by_freq[best_late_freq]) >= 0.55:
            labels.append("transitioned_toward_neighbor_band_mode")
    return {
        "status": "detected" if labels else "inconclusive",
        "labels": labels,
        "best_event_reference_frequency": float(best_reference["reference_frequency"]),
        "best_event_shape_correlation": max_shape,
        "best_event_max_radial_correlation": max_radial,
    }


def _nearest_reference_rows(reference_rows: list[dict[str, Any]], time: float) -> list[dict[str, Any]]:
    nearest_time = min({float(row["time"]) for row in reference_rows}, key=lambda value: abs(value - time))
    return [row for row in reference_rows if abs(float(row["time"]) - nearest_time) <= EPSILON]


def _diagnostic_labels(
    breathing: dict[str, Any],
    transition: dict[str, Any],
    angular: dict[str, Any],
    reference: dict[str, Any],
) -> list[str]:
    labels = []
    if breathing.get("label"):
        labels.append(breathing["label"])
    if transition.get("label"):
        labels.append(transition["label"])
    labels.extend(angular.get("labels", []))
    labels.extend(reference.get("labels", []))
    return labels


def _mean(values: Iterable[Any]) -> float:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return 0.0
    return float(np.mean(numeric))


def _correlation_summary(frame_rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "mean_corr_prev_frame": _mean(row["corr_prev_frame"] for row in frame_rows),
        "min_corr_prev_frame": min(float(row["corr_prev_frame"]) for row in frame_rows if row["corr_prev_frame"] is not None),
        "best_event_corr_to_cutoff": _special_frame_value(frame_rows, "best", "corr_to_cutoff_frame"),
        "best_event_corr_to_early_tail": _special_frame_value(frame_rows, "best", "corr_to_early_tail_frame"),
    }


def _radial_drift_summary(frame_rows: list[dict[str, Any]]) -> dict[str, float]:
    radii = [float(row["radial_peak_radius"]) for row in frame_rows]
    return {
        "min_radial_peak_radius": min(radii),
        "max_radial_peak_radius": max(radii),
        "radial_peak_radius_range": max(radii) - min(radii),
        "mean_radial_peak_radius": float(np.mean(radii)),
        "best_event_radial_peak_radius": _special_frame_value(frame_rows, "best", "radial_peak_radius"),
    }


def _special_frame_value(frame_rows: list[dict[str, Any]], label: str, key: str) -> float:
    for row in frame_rows:
        labels = str(row.get("special_frame", "")).split(",")
        if label in labels and row.get(key) is not None:
            return float(row[key])
    return 0.0


def _special_frame_time(frame_rows: list[dict[str, Any]], label: str) -> float | None:
    for row in frame_rows:
        labels = str(row.get("special_frame", "")).split(",")
        if label in labels:
            return float(row["time"])
    return None


def _write_report(
    run_dir: Path,
    diagnostics_dir: Path,
    summary: dict[str, Any],
    config: SimulationConfig,
    diagnostics: dict[str, Any],
) -> Path:
    report_path = diagnostics_dir / "mode_shape_diagnostics_report.md"
    breathing = diagnostics["breathing_detection"]
    transition = diagnostics["mode_transition_detection"]
    angular = diagnostics["angular_detection"]
    reference = diagnostics["reference_comparison"]
    radial_units = "physical units" if config.fixed_domain else "defect radii"
    transition_time_label = (
        "Estimated transition time"
        if transition.get("status") == "detected"
        else "Strongest transition-candidate time"
    )
    lines = [
        f"# Mode Shape Diagnostics: {summary.get('run_id', run_dir.name)}",
        "",
        "## Run",
        "",
        f"- Path: `{run_dir}`",
        f"- Drive frequency: `{config.driver.frequency}`",
        f"- Drive cutoff time: `{config.driver.drive_cutoff_time}`",
        f"- Best event time: `{summary.get('time_of_best_event')}`",
        f"- Best energy-well ratio: `{float(summary.get('best_energy_well_ratio', 0.0)):.6g}`",
        f"- Retention score: `{float(summary.get('retention_score', 0.0)):.6g}`",
        f"- Diagnostic frames: `{diagnostics['frame_count']}`",
        "",
        "## Correlation Summary",
        "",
        f"- Mean previous-frame correlation: `{diagnostics['correlation_summary']['mean_corr_prev_frame']:.3f}`",
        f"- Minimum previous-frame correlation: `{diagnostics['correlation_summary']['min_corr_prev_frame']:.3f}`",
        f"- Best-frame correlation to cutoff frame: `{diagnostics['correlation_summary']['best_event_corr_to_cutoff']:.3f}`",
        f"- Best-frame correlation to early-tail frame: `{diagnostics['correlation_summary']['best_event_corr_to_early_tail']:.3f}`",
        "",
        "## Radial Drift",
        "",
        f"- Radial peak radius range: `{diagnostics['radial_drift_summary']['radial_peak_radius_range']:.3f}` {radial_units}",
        f"- Min/max radial peak radius: `{diagnostics['radial_drift_summary']['min_radial_peak_radius']:.3f}` / `{diagnostics['radial_drift_summary']['max_radial_peak_radius']:.3f}`",
        "",
        "## Breathing Detection",
        "",
        f"- Status: `{breathing.get('status')}`",
        f"- Estimated period: `{_format_optional(breathing.get('estimated_period'))}`",
        f"- Breathing strength score: `{_format_optional(breathing.get('breathing_strength_score'))}`",
        f"- Detected cycles: `{breathing.get('detected_cycles', 0)}`",
        "",
        "## Mode Transition Detection",
        "",
        f"- Status: `{transition.get('status')}`",
        f"- {transition_time_label}: `{_format_optional(transition.get('transition_time'))}`",
        f"- Transition sharpness score: `{_format_optional(transition.get('transition_sharpness_score'))}`",
        f"- Pre/post cutoff correlation: `{_format_optional(transition.get('pre_transition_avg_cutoff_corr'))}` / `{_format_optional(transition.get('post_transition_avg_cutoff_corr'))}`",
        f"- Pre/post best correlation: `{_format_optional(transition.get('pre_transition_avg_best_corr'))}` / `{_format_optional(transition.get('post_transition_avg_best_corr'))}`",
        "",
        "## Angular / Rotation",
        "",
        f"- Status: `{angular.get('status')}`",
        f"- Labels: `{', '.join(angular.get('labels', [])) or 'none'}`",
        f"- Strongest angular mode: `{angular.get('strongest_angular_mode', 'n/a')}`",
        f"- Strongest angular mode strength: `{_format_optional(angular.get('strongest_angular_mode_strength'))}`",
        f"- Angular phase drift: `{_format_optional(angular.get('angular_phase_drift'))}`",
        f"- Angular phase trend R^2: `{_format_optional(angular.get('angular_phase_trend_r2'))}`",
        "",
        "## Reference Comparison",
        "",
        f"- Status: `{reference.get('status')}`",
        f"- Labels: `{', '.join(reference.get('labels', [])) or 'none'}`",
        f"- Best-event reference frequency: `{_format_optional(reference.get('best_event_reference_frequency'))}`",
        f"- Best-event shape correlation: `{_format_optional(reference.get('best_event_shape_correlation'))}`",
        f"- Best-event max radial correlation: `{_format_optional(reference.get('best_event_max_radial_correlation'))}`",
        "",
        "## Interpretation",
        "",
        _diagnostic_interpretation(breathing, transition, angular, reference),
        "",
        "## Files",
        "",
        "- `frame_mode_diagnostics.csv`",
        "- `frame_correlation_plot.png`",
        "- `radial_profile_timeseries.csv`",
        "- `radial_peak_drift_plot.png`",
        "- `radial_profile_heatmap.png`",
        "- `angular_mode_timeseries.csv`",
        "- `angular_mode_plot.png`",
    ]
    if (diagnostics_dir / "reference_mode_comparison.csv").exists():
        lines.append("- `reference_mode_comparison.csv`")
        lines.append("- `reference_mode_comparison_plot.png`")
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def _diagnostic_interpretation(
    breathing: dict[str, Any],
    transition: dict[str, Any],
    angular: dict[str, Any],
    reference: dict[str, Any],
) -> str:
    sentences = []
    if breathing.get("status") == "detected":
        sentences.append(
            "Core energy shows repeated post-cutoff envelope peaks while radial profiles remain coherent enough to support a breathing localized state."
        )
    if transition.get("status") == "detected":
        sentences.append(
            "Correlation structure changes after cutoff and later aligns more strongly with the best-event frame, supporting a late-time mode transition."
        )
    if "ring_mode_persistence" in angular.get("labels", []):
        sentences.append("Low nonzero angular Fourier strength supports a mostly ring-like post-drive tail.")
    if "angular_mode_structure" in angular.get("labels", []):
        sentences.append("Angular Fourier components indicate persistent non-axisymmetric structure in the tail.")
    if "rotating_tail_mode" in angular.get("labels", []):
        sentences.append("Angular phase drift suggests a rotating or angularly shifting tail mode.")
    if "long_tail_distinct_from_short_peak" in reference.get("labels", []):
        sentences.append("The best long-run frame remains weakly correlated with available short-sweep peak references, so it should be treated as a distinct late-time state.")
    if not sentences:
        return "The evidence is inconclusive: diagnostics did not strongly separate stable retention, transition, breathing, or rotation."
    return " ".join(sentences)


def _updated_interpretation(
    existing: str,
    breathing: dict[str, Any],
    transition: dict[str, Any],
    angular: dict[str, Any],
    reference: dict[str, Any],
) -> str:
    sentence = _diagnostic_interpretation(breathing, transition, angular, reference)
    if sentence in existing:
        return existing
    return f"{existing} {sentence}".strip()


def _format_optional(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"
