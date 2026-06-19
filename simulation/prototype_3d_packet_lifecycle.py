"""Extended 3D packet lifecycle audit for clean cubic shell-window transport."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Lattice3D, Prototype3DConfig, _calibrate_amplitude
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _shell_width, _threshold_like_options
from .prototype_3d_source_sponge import _effective_source_area, _format, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area
from .prototype_3d_transport_packet import (
    _radial_flux_density,
    _radial_profile_sum,
    _variant_plan as _packet_variant_plan,
)


@dataclass(frozen=True)
class PacketLifecycle3DOptions:
    """Options for an extended packet lifecycle audit."""

    output_root: str = "runs"
    grid_size: int = 41
    reference_source_grid_size: int = 31
    physical_duration: float = 96.0
    sample_every: int = 10
    diagnostic_sample_every: int = 4
    radial_bins: int = 40
    shell_window_radius: float = 5.0
    shell_window_width: float | None = None
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    target_work_per_source_area: float | None = None
    phase_offset: float = 0.5 * float(np.pi)
    arrival_threshold_fraction: float = 0.10
    exit_threshold_fraction: float = 0.12
    exit_hold_samples: int = 10
    peak_threshold_fraction: float = 0.30
    refocus_threshold_fraction: float = 0.35
    min_peak_separation_time: float = 5.0
    min_refocus_count: int = 2
    min_width_growth_fraction: float = 0.30
    min_decay_rate_magnitude: float = 0.01


def run_3d_packet_lifecycle_audit(
    base_config: SimulationConfig,
    *,
    options: PacketLifecycle3DOptions | None = None,
) -> dict[str, Any]:
    """Run a longer two-variant audit to classify packet lifecycle."""

    options = options or PacketLifecycle3DOptions()
    control_id = datetime.now().strftime("packet_lifecycle_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    threshold_options = _threshold_like_options(options)
    target_work_per_area = options.target_work_per_source_area or _calibration_work_per_area(
        base_config,
        threshold_options,
        source_width,
    )
    reference_drive_amplitude = _calibrated_reference_amplitude(
        base_config,
        threshold_options,
        source_width,
        target_work_per_area,
    )

    rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for config in variants:
        config.drive_amplitude = reference_drive_amplitude
        target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
        _calibrate_amplitude(config, target_work)
        config.steps = max(config.steps, int(round(options.physical_duration / max(config.dt, EPSILON))))
        result = _run_lifecycle_variant(config, root, options)
        rows.append(result["summary"])
        timeseries_rows.extend(result["timeseries"])
        event_rows.extend(result["events"])

    classification = classify_packet_lifecycle(rows, options)
    for row in rows:
        row["packet_lifecycle_classification"] = classification["label"]

    summary_csv = root / "packet_lifecycle_summary.csv"
    timeseries_csv = root / "packet_lifecycle_timeseries.csv"
    events_csv = root / "packet_lifecycle_events.csv"
    report_path = root / "packet_lifecycle_3d_report.md"
    _write_csv(summary_csv, rows, _summary_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(events_csv, event_rows, _event_fields())
    _plot_lifecycle(root / "shell_energy_lifecycle_plot.png", timeseries_rows, event_rows)
    _plot_radius_width(root / "packet_radius_width_plot.png", timeseries_rows)
    _plot_flux(root / "radial_flux_balance_plot.png", timeseries_rows)
    _write_report(report_path, control_id, rows, classification, options)
    save_json(
        root / "packet_lifecycle_3d_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": rows,
            "summary_csv": str(summary_csv),
            "timeseries_csv": str(timeseries_csv),
            "events_csv": str(events_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": rows,
        "summary_csv": str(summary_csv),
        "timeseries_csv": str(timeseries_csv),
        "events_csv": str(events_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_packet_lifecycle(
    rows: list[dict[str, Any]],
    options: PacketLifecycle3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether packets pass through, diffuse, stall, or refocus."""

    options = options or PacketLifecycle3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No packet lifecycle rows were available.", "checks": {}}
    row_labels = {row["variant"]: _classify_row(row, options) for row in rows}
    checks = {
        row["variant"]: {
            "major_peak_count": row.get("major_shell_peak_count"),
            "refocus_peak_count": row.get("refocus_peak_count"),
            "shell_exit_detected": row.get("shell_exit_detected"),
            "width_growth_fraction": row.get("packet_width_growth_fraction"),
            "shell_decay_rate": row.get("post_cutoff_shell_decay_rate"),
            "inward_flux_fraction": row.get("inward_flux_fraction"),
            "outward_flux_fraction": row.get("outward_flux_fraction"),
        }
        for row in rows
    }
    labels = set(row_labels.values())
    if labels == {"repeated_refocusing"}:
        return {
            "label": "repeated_refocusing_supported",
            "reason": "Both clean cubic variants show multiple post-cutoff shell-window peaks consistent with repeated refocusing.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if "repeated_refocusing" in labels:
        return {
            "label": "mixed_refocusing",
            "reason": "At least one clean cubic variant shows repeated shell-window refocusing while the other follows a different lifecycle.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if labels == {"single_pass"}:
        return {
            "label": "single_pass_transport",
            "reason": "Both clean cubic variants show one dominant shell-window passage followed by exit or decay.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if labels == {"diffusive_decay"}:
        return {
            "label": "diffusive_transport_tail",
            "reason": "Both clean cubic variants lose shell-window organization through spreading and decay rather than repeated refocusing.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if labels == {"stalled_or_retained"}:
        return {
            "label": "stalled_or_retained_packet",
            "reason": "Both clean cubic variants remain in or near the shell window without clear exit or repeated refocus peaks.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "mixed_lifecycle",
        "reason": f"Clean cubic variants show different lifecycle labels: {row_labels}.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: PacketLifecycle3DOptions) -> list[Prototype3DConfig]:
    return _packet_variant_plan(base, options)


def _run_lifecycle_variant(
    config: Prototype3DConfig,
    root: Path,
    options: PacketLifecycle3DOptions,
) -> dict[str, Any]:
    run_dir = root / config.name
    run_dir.mkdir(parents=True, exist_ok=False)
    lattice = Lattice3D(config)
    coords = lattice.coords
    radius = coords["radius"]
    shell_width = _shell_width(config, options)
    shell_outer = options.shell_window_radius + shell_width
    shell_mask = (radius > options.shell_window_radius) & (radius <= shell_outer)
    outer_mask = radius > shell_outer + shell_width
    active_mask = coords["boundary_distance"] >= config.sponge_width
    bins = np.linspace(0.0, np.sqrt(3.0) * config.domain_size / 2.0, options.radial_bins + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    timeseries: list[dict[str, Any]] = []
    cumulative_positive_work = 0.0
    cumulative_inward_flux = 0.0
    cumulative_outward_flux = 0.0

    for step in range(config.steps):
        time = step * config.dt
        force = lattice.external_force(time)
        velocity_before = lattice.v.copy()
        lattice.step(time, config.dt)
        velocity_mid = 0.5 * (velocity_before + lattice.v)
        power = float(np.sum(force * velocity_mid) * config.cell_volume)
        if time <= config.drive_cutoff_time:
            cumulative_positive_work += max(0.0, power) * config.dt
        if step % max(1, options.diagnostic_sample_every) != 0 and step != config.steps - 1:
            continue

        energy = lattice.energy_density()
        flux_density = _radial_flux_density(lattice)
        shell_flux = float(np.sum(flux_density[shell_mask]))
        dt_sample = config.dt * max(1, options.diagnostic_sample_every)
        cumulative_inward_flux += max(0.0, -shell_flux) * dt_sample
        cumulative_outward_flux += max(0.0, shell_flux) * dt_sample
        active_energy = np.where(active_mask, energy, 0.0)
        radial_profile = _radial_profile_sum(active_energy, radius, bins)
        packet_peak_radius = float(centers[int(np.argmax(radial_profile))]) if radial_profile.size else 0.0
        packet_width = _profile_width(centers, radial_profile)
        packet_centroid = _weighted_mean(radius[active_mask], energy[active_mask])
        packet_spread = _weighted_std(radius[active_mask], energy[active_mask], packet_centroid)
        shell_energy = float(np.sum(energy[shell_mask]))
        outer_energy = float(np.sum(energy[outer_mask & active_mask]))
        total_energy = float(np.sum(energy))
        timeseries.append(
            {
                "variant": config.name,
                "time": time,
                "packet_peak_radius": packet_peak_radius,
                "packet_centroid_radius": packet_centroid,
                "packet_radial_width": packet_width,
                "packet_radial_spread": packet_spread,
                "shell_window_energy": shell_energy,
                "outer_active_energy": outer_energy,
                "outer_to_shell_energy": outer_energy / (shell_energy + EPSILON),
                "shell_fraction_of_total": shell_energy / (total_energy + EPSILON),
                "shell_radial_flux": shell_flux,
                "shell_inward_flux": max(0.0, -shell_flux),
                "shell_outward_flux": max(0.0, shell_flux),
                "cumulative_inward_flux": cumulative_inward_flux,
                "cumulative_outward_flux": cumulative_outward_flux,
            }
        )

    summary, events = _summarize_lifecycle(config, timeseries, cumulative_positive_work, shell_width, options)
    _write_csv(run_dir / "packet_lifecycle_timeseries.csv", timeseries, _timeseries_fields())
    _write_csv(run_dir / "packet_lifecycle_events.csv", events, _event_fields())
    return {"summary": summary, "timeseries": timeseries, "events": events}


def _summarize_lifecycle(
    config: Prototype3DConfig,
    rows: list[dict[str, Any]],
    positive_work_before_cutoff: float,
    shell_width: float,
    options: PacketLifecycle3DOptions,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not rows:
        return {"variant": config.name}, []
    times = np.asarray([row["time"] for row in rows], dtype=float)
    shell = np.asarray([row["shell_window_energy"] for row in rows], dtype=float)
    radius = np.asarray([row["packet_peak_radius"] for row in rows], dtype=float)
    centroid = np.asarray([row["packet_centroid_radius"] for row in rows], dtype=float)
    width = np.asarray([row["packet_radial_width"] for row in rows], dtype=float)
    spread = np.asarray([row["packet_radial_spread"] for row in rows], dtype=float)
    post_mask = times > config.drive_cutoff_time
    post_indices = np.flatnonzero(post_mask)
    peak_idx = int(np.argmax(shell))
    peak_shell = float(shell[peak_idx])
    arrival_threshold = max(options.arrival_threshold_fraction * peak_shell, positive_work_before_cutoff * 1.0e-8)
    arrival_idx = _first_index(shell >= arrival_threshold)
    exit_threshold = max(options.exit_threshold_fraction * peak_shell, arrival_threshold)
    exit_idx = _exit_index(shell, peak_idx, exit_threshold, options.exit_hold_samples)
    peaks = _major_peaks(times, shell, post_indices, options)
    events = _event_rows(config.name, times, shell, peaks, arrival_idx, exit_idx)
    tail_start = int(max(0, shell.size * 0.65))
    radial_velocity, radial_r2 = _linear_fit(times[post_indices], centroid[post_indices])
    width_velocity, width_r2 = _linear_fit(times[post_indices], spread[post_indices])
    shell_decay_rate, shell_decay_r2 = _decay_rate(times, shell, peak_idx)
    width_growth_fraction = (float(np.mean(spread[tail_start:])) - float(spread[peak_idx])) / (abs(float(spread[peak_idx])) + EPSILON)
    flux_in = float(rows[-1]["cumulative_inward_flux"])
    flux_out = float(rows[-1]["cumulative_outward_flux"])
    flux_total = flux_in + flux_out + EPSILON
    first_peak = peaks[0] if peaks else None
    later_peaks = peaks[1:] if len(peaks) > 1 else []
    refocus_peaks = [
        peak
        for peak in later_peaks
        if peak["energy"] >= options.refocus_threshold_fraction * max(first_peak["energy"] if first_peak else peak_shell, EPSILON)
    ]
    summary = {
        "variant": config.name,
        "grid_size": config.grid_size,
        "dx": config.dx,
        "dt": config.dt,
        "physical_duration": config.physical_duration,
        "drive_cutoff_time": config.drive_cutoff_time,
        "drive_phase_mode": config.drive_phase_mode,
        "boundary_phase_offset": config.boundary_phase_offset,
        "boundary_cubic_phase_sign": config.boundary_cubic_phase_sign,
        "positive_work_before_cutoff": positive_work_before_cutoff,
        "work_per_source_area": positive_work_before_cutoff / max(_effective_source_area(config), EPSILON),
        "shell_window_radius": options.shell_window_radius,
        "shell_window_width": shell_width,
        "first_shell_arrival_time": float(times[arrival_idx]) if arrival_idx is not None else None,
        "shell_peak_time": float(times[peak_idx]),
        "shell_peak_energy": peak_shell,
        "shell_peak_fraction_of_work": peak_shell / (positive_work_before_cutoff + EPSILON),
        "shell_exit_time": float(times[exit_idx]) if exit_idx is not None else None,
        "shell_exit_detected": exit_idx is not None,
        "shell_dwell_time": float(times[exit_idx] - times[arrival_idx]) if exit_idx is not None and arrival_idx is not None else None,
        "major_shell_peak_count": len(peaks),
        "refocus_peak_count": len(refocus_peaks),
        "first_refocus_time": refocus_peaks[0]["time"] if refocus_peaks else None,
        "last_refocus_time": refocus_peaks[-1]["time"] if refocus_peaks else None,
        "refocus_peak_ratio_max": max([peak["energy"] for peak in refocus_peaks], default=0.0) / (first_peak["energy"] + EPSILON) if first_peak else 0.0,
        "packet_peak_radius_at_shell_peak": float(radius[peak_idx]),
        "packet_centroid_radius_at_shell_peak": float(centroid[peak_idx]),
        "packet_width_at_shell_peak": float(width[peak_idx]),
        "packet_spread_at_shell_peak": float(spread[peak_idx]),
        "tail_packet_radius_mean": _mean(radius[tail_start:].tolist()),
        "tail_packet_width_mean": _mean(width[tail_start:].tolist()),
        "tail_packet_spread_mean": _mean(spread[tail_start:].tolist()),
        "packet_width_growth_fraction": width_growth_fraction,
        "post_cutoff_radial_velocity": radial_velocity,
        "post_cutoff_radial_velocity_r2": radial_r2,
        "post_cutoff_width_velocity": width_velocity,
        "post_cutoff_width_velocity_r2": width_r2,
        "post_cutoff_shell_decay_rate": shell_decay_rate,
        "post_cutoff_shell_decay_r2": shell_decay_r2,
        "tail_shell_retention": _mean(shell[tail_start:].tolist()) / (peak_shell + EPSILON),
        "tail_outer_to_shell_mean": _mean([row["outer_to_shell_energy"] for row in rows[tail_start:]]),
        "cumulative_inward_flux": flux_in,
        "cumulative_outward_flux": flux_out,
        "inward_flux_fraction": flux_in / flux_total,
        "outward_flux_fraction": flux_out / flux_total,
        "lifecycle_label": _classify_row_from_values(len(peaks), len(refocus_peaks), exit_idx is not None, width_growth_fraction, shell_decay_rate, options),
    }
    return summary, events


def _classify_row(row: dict[str, Any], options: PacketLifecycle3DOptions) -> str:
    return _classify_row_from_values(
        int(row.get("major_shell_peak_count") or 0),
        int(row.get("refocus_peak_count") or 0),
        bool(row.get("shell_exit_detected")),
        float(row.get("packet_width_growth_fraction") or 0.0),
        float(row.get("post_cutoff_shell_decay_rate") or 0.0),
        options,
    )


def _classify_row_from_values(
    peak_count: int,
    refocus_count: int,
    exited: bool,
    width_growth: float,
    decay_rate: float,
    options: PacketLifecycle3DOptions,
) -> str:
    if peak_count >= options.min_refocus_count and refocus_count >= 1:
        return "repeated_refocusing"
    if exited or peak_count <= 1:
        return "single_pass"
    if width_growth >= options.min_width_growth_fraction and decay_rate <= -options.min_decay_rate_magnitude:
        return "diffusive_decay"
    return "stalled_or_retained"


def _major_peaks(
    times: np.ndarray,
    values: np.ndarray,
    post_indices: np.ndarray,
    options: PacketLifecycle3DOptions,
) -> list[dict[str, Any]]:
    if values.size < 3 or post_indices.size == 0:
        return []
    peak_value = float(np.max(values[post_indices]))
    threshold = max(options.peak_threshold_fraction * peak_value, EPSILON)
    candidates = []
    post_set = set(int(idx) for idx in post_indices)
    for idx in range(1, values.size - 1):
        if idx not in post_set:
            continue
        if values[idx] >= threshold and values[idx] >= values[idx - 1] and values[idx] >= values[idx + 1]:
            candidates.append({"index": idx, "time": float(times[idx]), "energy": float(values[idx])})
    accepted: list[dict[str, Any]] = []
    for peak in sorted(candidates, key=lambda item: item["energy"], reverse=True):
        if all(abs(peak["time"] - other["time"]) >= options.min_peak_separation_time for other in accepted):
            accepted.append(peak)
    return sorted(accepted, key=lambda item: item["time"])


def _event_rows(
    variant: str,
    times: np.ndarray,
    shell: np.ndarray,
    peaks: list[dict[str, Any]],
    arrival_idx: int | None,
    exit_idx: int | None,
) -> list[dict[str, Any]]:
    rows = []
    if arrival_idx is not None:
        rows.append({"variant": variant, "event": "arrival", "time": float(times[arrival_idx]), "energy": float(shell[arrival_idx]), "peak_rank": None})
    for rank, peak in enumerate(peaks, start=1):
        rows.append({"variant": variant, "event": "shell_peak", "time": peak["time"], "energy": peak["energy"], "peak_rank": rank})
    if exit_idx is not None:
        rows.append({"variant": variant, "event": "exit", "time": float(times[exit_idx]), "energy": float(shell[exit_idx]), "peak_rank": None})
    return rows


def _profile_width(centers: np.ndarray, profile: np.ndarray) -> float:
    if profile.size == 0:
        return 0.0
    peak = float(np.max(profile))
    if peak <= EPSILON:
        return 0.0
    mask = profile >= 0.5 * peak
    if not np.any(mask):
        return 0.0
    selected = centers[mask]
    return float(np.max(selected) - np.min(selected))


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= EPSILON:
        return 0.0
    return float(np.sum(values * weights) / total)


def _weighted_std(values: np.ndarray, weights: np.ndarray, mean: float) -> float:
    total = float(np.sum(weights))
    if total <= EPSILON:
        return 0.0
    return float(np.sqrt(np.sum(weights * (values - mean) ** 2) / total))


def _linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if x.size < 3 or y.size < 3 or float(np.ptp(x)) <= EPSILON:
        return 0.0, 0.0
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    return float(slope), float(np.clip(1.0 - ss_res / (ss_tot + EPSILON), 0.0, 1.0))


def _decay_rate(times: np.ndarray, values: np.ndarray, peak_idx: int) -> tuple[float, float]:
    if values.size - peak_idx < 6:
        return 0.0, 0.0
    x = times[peak_idx:]
    y = np.log(np.maximum(values[peak_idx:], EPSILON))
    return _linear_fit(x, y)


def _first_index(mask: np.ndarray) -> int | None:
    indices = np.flatnonzero(mask)
    return int(indices[0]) if indices.size else None


def _exit_index(values: np.ndarray, peak_idx: int, threshold: float, hold_samples: int) -> int | None:
    hold = max(1, int(hold_samples))
    for idx in range(peak_idx + 1, values.size):
        if np.all(values[idx : min(values.size, idx + hold)] <= threshold):
            return idx
    return None


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(max(rows, key=_lifecycle_score).get("variant", "n/a"))


def _lifecycle_score(row: dict[str, Any]) -> float:
    retention = float(row.get("tail_shell_retention") or 0.0)
    refocus = 1.0 + float(row.get("refocus_peak_count") or 0.0)
    outer = max(float(row.get("tail_outer_to_shell_mean") or 999.0), 0.25)
    return retention * refocus / outer


def _mean(values: list[Any]) -> float:
    parsed = [float(value) for value in values if value is not None]
    return float(np.mean(parsed)) if parsed else 0.0


def _plot_lifecycle(path: Path, rows: list[dict[str, Any]], events: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(9, 4), dpi=140)
    for variant in _variants(rows):
        subset = [row for row in rows if row["variant"] == variant]
        ax.plot([row["time"] for row in subset], [row["shell_window_energy"] for row in subset], label=variant)
        for event in [event for event in events if event["variant"] == variant]:
            if event["event"] == "shell_peak":
                ax.scatter([event["time"]], [event["energy"]], s=18)
    ax.set_xlabel("time")
    ax.set_ylabel("shell-window energy")
    ax.set_title("Shell-Window Lifecycle")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_radius_width(path: Path, rows: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), dpi=140, sharex=True)
    for variant in _variants(rows):
        subset = [row for row in rows if row["variant"] == variant]
        axes[0].plot([row["time"] for row in subset], [row["packet_peak_radius"] for row in subset], label=f"{variant} peak")
        axes[0].plot([row["time"] for row in subset], [row["packet_centroid_radius"] for row in subset], linestyle="--", label=f"{variant} centroid")
        axes[1].plot([row["time"] for row in subset], [row["packet_radial_spread"] for row in subset], label=variant)
    axes[0].set_ylabel("radius")
    axes[1].set_ylabel("radial spread")
    axes[1].set_xlabel("time")
    axes[0].set_title("Packet Radius And Spread")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_flux(path: Path, rows: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), dpi=140, sharex=True)
    for variant in _variants(rows):
        subset = [row for row in rows if row["variant"] == variant]
        axes[0].plot([row["time"] for row in subset], [row["shell_inward_flux"] for row in subset], label=f"{variant} inward")
        axes[0].plot([row["time"] for row in subset], [row["shell_outward_flux"] for row in subset], linestyle="--", label=f"{variant} outward")
        axes[1].plot([row["time"] for row in subset], [row["cumulative_inward_flux"] for row in subset], label=f"{variant} cumulative inward")
        axes[1].plot([row["time"] for row in subset], [row["cumulative_outward_flux"] for row in subset], linestyle="--", label=f"{variant} cumulative outward")
    axes[0].set_ylabel("sample flux")
    axes[1].set_ylabel("cumulative flux")
    axes[1].set_xlabel("time")
    axes[0].set_title("Radial Flux Balance")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _variants(rows: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        variant = str(row["variant"])
        if variant not in seen:
            seen.append(variant)
    return seen


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: PacketLifecycle3DOptions,
) -> None:
    lines = [
        f"# 3D Packet Lifecycle Audit: {control_id}",
        "",
        "## Purpose",
        "",
        "Extended two-variant audit for whether the cubic shell-window packet exits, stalls, diffuses, reflects, or repeatedly refocuses.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Lifecycle | Peaks | Refocus | Ret | Outer/Shell | Arrival | Exit | Decay | Radius V | Width Growth | In Flux |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('lifecycle_label')} | "
            f"{row.get('major_shell_peak_count')} | "
            f"{row.get('refocus_peak_count')} | "
            f"{_format(row.get('tail_shell_retention'))} | "
            f"{_format(row.get('tail_outer_to_shell_mean'))} | "
            f"{_format(row.get('first_shell_arrival_time'))} | "
            f"{row.get('shell_exit_detected')} | "
            f"{_format(row.get('post_cutoff_shell_decay_rate'))} | "
            f"{_format(row.get('post_cutoff_radial_velocity'))} | "
            f"{_format(row.get('packet_width_growth_fraction'))} | "
            f"{_format(row.get('inward_flux_fraction'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Files",
            "",
            "- `packet_lifecycle_summary.csv`",
            "- `packet_lifecycle_timeseries.csv`",
            "- `packet_lifecycle_events.csv`",
            "- `shell_energy_lifecycle_plot.png`",
            "- `packet_radius_width_plot.png`",
            "- `radial_flux_balance_plot.png`",
            "",
            "## Next Step",
            "",
            _next_step(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "repeated_refocusing_supported":
        return "The cubic phase creates repeated shell-window returns. The next phase should focus on retention/refocusing engineering."
    if label == "mixed_refocusing":
        return "Only one cubic phase condition clearly refocuses. The next phase should isolate which phase timing causes return peaks."
    if label == "single_pass_transport":
        return "The packet mostly passes through once. The next phase should focus on transport steering and slowing."
    if label == "diffusive_transport_tail":
        return "The packet spreads and decays instead of returning cleanly. The next phase should test whether phase shaping can reduce diffusion."
    if label == "stalled_or_retained_packet":
        return "The packet stays in or near the shell window without clean return peaks. The next phase should separate stalled retention from unresolved slow decay."
    return "Lifecycle differs across clean cubic variants; inspect the event ledger before adding new controls."


def _next_step(classification: dict[str, Any]) -> str:
    if classification["label"] in {"repeated_refocusing_supported", "mixed_refocusing"}:
        return "Run one tiny refocusing-engineering control around the variant with the strongest return peaks."
    if classification["label"] == "single_pass_transport":
        return "Run one tiny phase-shaping control scored on slowing or steering the one-pass packet."
    return "Run one tiny phase-shaping control with packet width/spread as a primary metric."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "packet_lifecycle_classification",
        "lifecycle_label",
        "grid_size",
        "dx",
        "dt",
        "physical_duration",
        "drive_cutoff_time",
        "drive_phase_mode",
        "boundary_phase_offset",
        "boundary_cubic_phase_sign",
        "positive_work_before_cutoff",
        "work_per_source_area",
        "shell_window_radius",
        "shell_window_width",
        "first_shell_arrival_time",
        "shell_peak_time",
        "shell_peak_energy",
        "shell_peak_fraction_of_work",
        "shell_exit_time",
        "shell_exit_detected",
        "shell_dwell_time",
        "major_shell_peak_count",
        "refocus_peak_count",
        "first_refocus_time",
        "last_refocus_time",
        "refocus_peak_ratio_max",
        "packet_peak_radius_at_shell_peak",
        "packet_centroid_radius_at_shell_peak",
        "packet_width_at_shell_peak",
        "packet_spread_at_shell_peak",
        "tail_packet_radius_mean",
        "tail_packet_width_mean",
        "tail_packet_spread_mean",
        "packet_width_growth_fraction",
        "post_cutoff_radial_velocity",
        "post_cutoff_radial_velocity_r2",
        "post_cutoff_width_velocity",
        "post_cutoff_width_velocity_r2",
        "post_cutoff_shell_decay_rate",
        "post_cutoff_shell_decay_r2",
        "tail_shell_retention",
        "tail_outer_to_shell_mean",
        "cumulative_inward_flux",
        "cumulative_outward_flux",
        "inward_flux_fraction",
        "outward_flux_fraction",
    ]


def _timeseries_fields() -> list[str]:
    return [
        "variant",
        "time",
        "packet_peak_radius",
        "packet_centroid_radius",
        "packet_radial_width",
        "packet_radial_spread",
        "shell_window_energy",
        "outer_active_energy",
        "outer_to_shell_energy",
        "shell_fraction_of_total",
        "shell_radial_flux",
        "shell_inward_flux",
        "shell_outward_flux",
        "cumulative_inward_flux",
        "cumulative_outward_flux",
    ]


def _event_fields() -> list[str]:
    return ["variant", "event", "time", "energy", "peak_rank"]
