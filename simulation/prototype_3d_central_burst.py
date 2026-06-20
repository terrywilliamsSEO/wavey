"""Central high-frequency burst branch for 3D neutral-lattice scattering."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any
import math

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Lattice3D, Prototype3DConfig, Prototype3DOptions, _base_3d_config
from .prototype_3d_cutoff_phase_map import (
    _area,
    _dominant_spectral_concentration,
    _lag1_autocorrelation,
    _refocus_count,
    _return_timing_regularity,
)
from .prototype_3d_interference_diagnostics import _shell_width
from .prototype_3d_packet_lifecycle import (
    PacketLifecycle3DOptions,
    _decay_rate,
    _event_rows,
    _exit_index,
    _linear_fit,
    _major_peaks,
    _profile_width,
    _weighted_mean,
    _weighted_std,
)
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv
from .prototype_3d_transport_packet import _radial_flux_density, _radial_profile_sum


CENTRAL_BURST_FREQUENCIES = (0.92, 1.84, 3.68, 5.52, 7.36)
CENTRAL_BURST_ENERGY_LABELS = ("low", "medium", "high", "extreme")
CENTRAL_BURST_ACCELERATION_SCALES = (0.05, 0.15, 0.35, 0.75)


@dataclass(frozen=True)
class CentralBurst3DOptions:
    """Options for the first central HF scattering branch control."""

    output_root: str = "runs"
    grid_size: int = 41
    physical_duration: float = 96.0
    sample_every: int = 10
    diagnostic_sample_every: int = 4
    radial_bins: int = 40
    shell_window_radius: float = 5.0
    shell_window_width: float | None = None
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    burst_duration: float = 6.0
    burst_radius: float = 1.0
    frequencies: tuple[float, ...] = CENTRAL_BURST_FREQUENCIES
    energy_labels: tuple[str, ...] = CENTRAL_BURST_ENERGY_LABELS
    burst_acceleration_scales: tuple[float, ...] = CENTRAL_BURST_ACCELERATION_SCALES
    include_half_dt_check: bool = True
    event_thresholds: tuple[float, ...] = (0.25, 0.30, 0.35, 0.40)
    peak_threshold_fraction: float = 0.30
    refocus_threshold_fraction: float = 0.35
    arrival_threshold_fraction: float = 0.10
    exit_threshold_fraction: float = 0.12
    exit_hold_samples: int = 10
    min_peak_separation_time: float = 5.0
    min_repeated_major_peaks: int = 3
    min_repeated_refocus_peaks: int = 2
    min_ring_major_peaks: int = 2
    min_ring_retention: float = 0.08
    min_clean_retention: float = 0.12
    max_outer_shell_ratio: float = 1.0
    max_energy_accounting_error: float = 0.25
    max_stable_abs_state: float = 1.0e6


def run_3d_central_burst_control(
    base_config: SimulationConfig,
    *,
    options: CentralBurst3DOptions | None = None,
) -> dict[str, Any]:
    """Run a firewalled central high-frequency burst ladder plus one half-dt check."""

    options = options or CentralBurst3DOptions()
    control_id = datetime.now().strftime("central_burst_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    baseline_configs = _variant_plan(base_config, options)
    summary_rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    energy_rows: list[dict[str, Any]] = []

    for config in baseline_configs:
        result = _run_burst_variant(config, root, options)
        summary_rows.append(result["summary"])
        timeseries_rows.extend(result["timeseries"])
        event_rows.extend(result["events"])
        threshold_rows.extend(result["threshold_counts"])
        energy_rows.append(result["energy_audit"])

    best_baseline = _best_row(summary_rows)
    if options.include_half_dt_check and best_baseline:
        half_config = _config_from_row(base_config, best_baseline, options, dt_scale=0.5, role="half_dt")
        half_result = _run_burst_variant(half_config, root, options)
        summary_rows.append(half_result["summary"])
        timeseries_rows.extend(half_result["timeseries"])
        event_rows.extend(half_result["events"])
        threshold_rows.extend(half_result["threshold_counts"])
        energy_rows.append(half_result["energy_audit"])

    classification = classify_central_burst(summary_rows, options)
    for row in summary_rows:
        row["central_burst_classification"] = classification["label"]
    for row in threshold_rows:
        row["central_burst_classification"] = classification["label"]
    for row in energy_rows:
        row["central_burst_classification"] = classification["label"]

    summary_csv = root / "central_burst_summary.csv"
    threshold_csv = root / "central_burst_threshold_counts.csv"
    timeseries_csv = root / "central_burst_timeseries.csv"
    events_csv = root / "central_burst_events.csv"
    energy_csv = root / "central_burst_energy_audit.csv"
    report_path = root / "central_burst_report.md"
    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(threshold_csv, threshold_rows, _threshold_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(events_csv, event_rows, _event_fields())
    _write_csv(energy_csv, energy_rows, _energy_fields())
    _write_report(report_path, control_id, summary_rows, threshold_rows, energy_rows, classification, options)
    save_json(
        root / "central_burst_summary.json",
        {
            "control_id": control_id,
            "branch": "central_hf_scattering_branch",
            "classification": classification,
            "variants": summary_rows,
            "summary_csv": str(summary_csv),
            "threshold_csv": str(threshold_csv),
            "timeseries_csv": str(timeseries_csv),
            "events_csv": str(events_csv),
            "energy_csv": str(energy_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "branch": "central_hf_scattering_branch",
        "classification": classification,
        "variants": summary_rows,
        "summary_csv": str(summary_csv),
        "threshold_csv": str(threshold_csv),
        "timeseries_csv": str(timeseries_csv),
        "events_csv": str(events_csv),
        "energy_csv": str(energy_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_central_burst(
    rows: list[dict[str, Any]],
    options: CentralBurst3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether central HF injection produced clean refocusing or a threshold pattern."""

    options = options or CentralBurst3DOptions()
    baseline = [row for row in rows if row.get("dt_variant") == "baseline_dt"]
    half = [row for row in rows if row.get("dt_variant") == "half_dt"]
    best = _best_row(baseline)
    half_row = half[0] if half else None
    low_rows = [row for row in baseline if row.get("energy_label") == "low"]
    medium_rows = [row for row in baseline if row.get("energy_label") == "medium"]
    high_rows = [row for row in baseline if row.get("energy_label") in {"high", "extreme"}]
    low_disperses = bool(low_rows) and all(not _ringing(row, options) for row in low_rows)
    medium_rings = any(_ringing(row, options) for row in medium_rows)
    high_refocuses = any(_clean_repeated(row, options) for row in high_rows)
    half_survives = bool(half_row) and _clean_repeated(half_row, options)
    any_clean_repeated = any(_clean_repeated(row, options) for row in baseline)
    any_repeated = any(_repeated(row, options) for row in baseline)
    checks = {
        "baseline_row_count": len(baseline),
        "half_dt_row_count": len(half),
        "best_variant": (best or {}).get("variant"),
        "best_frequency": (best or {}).get("burst_frequency"),
        "best_energy_label": (best or {}).get("energy_label"),
        "best_default_count": _count_label(best, "0p30"),
        "best_strict_count": _count_label(best, "0p35"),
        "best_score": _score(best),
        "low_energy_disperses": low_disperses,
        "medium_energy_rings": medium_rings,
        "high_or_extreme_refocuses": high_refocuses,
        "half_dt_best_check_survives": half_survives,
        "any_clean_repeated_baseline": any_clean_repeated,
        "any_repeated_baseline": any_repeated,
    }
    if low_disperses and medium_rings and high_refocuses and half_survives:
        return {
            "label": "central_burst_nonlinear_threshold_candidate",
            "reason": "The ladder separates low-energy dispersion from higher-energy retained/refocusing behavior, and the best row survives the half-dt check.",
            "best_variant": (best or {}).get("variant", "n/a"),
            "checks": checks,
        }
    if any_clean_repeated and half_survives:
        return {
            "label": "central_burst_refocusing_supported",
            "reason": "A no-boundary-drive central burst produced repeated clean shell-window returns and survived the half-dt check.",
            "best_variant": (best or {}).get("variant", "n/a"),
            "checks": checks,
        }
    if any_clean_repeated and not half_survives:
        return {
            "label": "central_burst_dt_sensitive",
            "reason": "At least one baseline row produced clean repeated returns, but the selected best row did not survive the half-dt check cleanly.",
            "best_variant": (best or {}).get("variant", "n/a"),
            "checks": checks,
        }
    return {
        "label": "central_burst_transient",
        "reason": "The central burst ladder did not produce repeated clean shell-window returns; treat any early shell spike as transient unless future mechanism evidence changes.",
        "best_variant": (best or {}).get("variant", "n/a"),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: CentralBurst3DOptions) -> list[Prototype3DConfig]:
    variants: list[Prototype3DConfig] = []
    for frequency in options.frequencies:
        for label, scale in zip(options.energy_labels, options.burst_acceleration_scales):
            variants.append(_config(base, options, frequency, label, scale, dt_scale=1.0, role="baseline_dt"))
    return variants


def _config_from_row(
    base: SimulationConfig,
    row: dict[str, Any],
    options: CentralBurst3DOptions,
    *,
    dt_scale: float,
    role: str,
) -> Prototype3DConfig:
    return _config(
        base,
        options,
        float(row.get("burst_frequency") or 0.0),
        str(row.get("energy_label") or "unknown"),
        float(row.get("burst_acceleration_scale") or 0.0),
        dt_scale=dt_scale,
        role=role,
    )


def _config(
    base: SimulationConfig,
    options: CentralBurst3DOptions,
    frequency: float,
    energy_label: str,
    acceleration_scale: float,
    *,
    dt_scale: float,
    role: str,
) -> Prototype3DConfig:
    name = _variant_name(role, frequency, energy_label)
    config = _base_3d_config(
        name,
        base,
        Prototype3DOptions(grid_size=options.grid_size),
        "core",
        "uniform",
    )
    config.steps = max(1, int(round(options.physical_duration / max(base.dt * dt_scale, EPSILON))))
    config.dt = float(base.dt) * dt_scale
    config.drive_frequency = float(frequency)
    config.drive_amplitude = 0.0
    config.drive_cutoff_time = float(options.burst_duration)
    config.drive_location = "core"
    config.drive_phase_mode = "uniform"
    config.drive_mode = "central_velocity_burst"
    config.defect_stiffness_multiplier = 1.0
    config.defect_damping_multiplier = 1.0
    config.defect_coupling_multiplier = 1.0
    config.defect_inner_radius = None
    config.defect_nonlinear_strength = None
    config.sponge_strength *= options.sponge_strength_multiplier
    config.second_pulse_center_time = None
    config.second_pulse_duration = 0.0
    config.second_pulse_amplitude_scale = 0.0
    config.second_pulse_phase_offset = 0.0
    config.resonator_enabled = False
    config.resonator_geometry = "none"
    config.resonator_k1 = 0.0
    config.resonator_k3 = 0.0
    config.resonator_damping = 0.0
    config.resonator_coupling = 0.0
    setattr(config, "_central_burst_frequency", float(frequency))
    setattr(config, "_central_burst_energy_label", str(energy_label))
    setattr(config, "_central_burst_acceleration_scale", float(acceleration_scale))
    setattr(config, "_central_burst_dt_variant", role)
    setattr(config, "_central_burst_dt_scale", dt_scale)
    return config


def _run_burst_variant(
    config: Prototype3DConfig,
    root: Path,
    options: CentralBurst3DOptions,
) -> dict[str, Any]:
    run_dir = root / config.name
    run_dir.mkdir(parents=True, exist_ok=False)
    lattice = Lattice3D(config)
    radius = lattice.coords["radius"]
    shell_width = _shell_width(config, options)
    shell_outer = options.shell_window_radius + shell_width
    shell_mask = (radius > options.shell_window_radius) & (radius <= shell_outer)
    outer_mask = radius > shell_outer + shell_width
    active_mask = lattice.coords["boundary_distance"] >= config.sponge_width
    burst_mask = radius <= max(float(options.burst_radius), 0.5 * config.dx)
    if not np.any(burst_mask):
        burst_mask = radius <= config.dx
    burst_weights = _burst_weights(radius, burst_mask, max(float(options.burst_radius), config.dx))
    bins = np.linspace(0.0, np.sqrt(3.0) * config.domain_size / 2.0, options.radial_bins + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])

    timeseries: list[dict[str, Any]] = []
    cumulative_net_work = 0.0
    cumulative_positive_work = 0.0
    cumulative_damping_loss = 0.0
    cumulative_inward_flux = 0.0
    cumulative_outward_flux = 0.0
    max_abs_displacement = 0.0
    max_abs_velocity = 0.0
    stopped_early = False

    for step in range(config.steps):
        time = step * config.dt
        work_delta = _apply_velocity_burst(lattice, burst_mask, burst_weights, time, config.dt, options)
        cumulative_net_work += work_delta
        cumulative_positive_work += max(0.0, work_delta)
        velocity_before = lattice.v.copy()
        lattice.step(time, config.dt)
        velocity_mid = 0.5 * (velocity_before + lattice.v)
        damping_power = float(np.sum(lattice.damping * velocity_mid**2) * config.cell_volume)
        cumulative_damping_loss += damping_power * config.dt
        max_abs_displacement = max(max_abs_displacement, float(np.max(np.abs(lattice.u))))
        max_abs_velocity = max(max_abs_velocity, float(np.max(np.abs(lattice.v))))
        if not np.isfinite(max_abs_displacement + max_abs_velocity) or max(max_abs_displacement, max_abs_velocity) > options.max_stable_abs_state:
            stopped_early = True
            break
        if step % max(1, options.diagnostic_sample_every) != 0 and step != config.steps - 1:
            continue
        energy = lattice.energy_density()
        total_energy = float(np.sum(energy))
        flux_density = _radial_flux_density(lattice)
        shell_flux = float(np.sum(flux_density[shell_mask]))
        sample_dt = config.dt * max(1, options.diagnostic_sample_every)
        cumulative_inward_flux += max(0.0, -shell_flux) * sample_dt
        cumulative_outward_flux += max(0.0, shell_flux) * sample_dt
        active_energy = np.where(active_mask, energy, 0.0)
        profile = _radial_profile_sum(active_energy, radius, bins)
        peak_radius = float(centers[int(np.argmax(profile))]) if profile.size else 0.0
        shell_energy = float(np.sum(energy[shell_mask]))
        outer_energy = float(np.sum(energy[outer_mask & active_mask]))
        centroid = _weighted_mean(radius[active_mask], energy[active_mask])
        spread = _weighted_std(radius[active_mask], energy[active_mask], centroid)
        timeseries.append(
            {
                "variant": config.name,
                "time": time,
                "dt_variant": getattr(config, "_central_burst_dt_variant", "baseline_dt"),
                "burst_frequency": getattr(config, "_central_burst_frequency", config.drive_frequency),
                "energy_label": getattr(config, "_central_burst_energy_label", ""),
                "burst_acceleration_scale": getattr(config, "_central_burst_acceleration_scale", 0.0),
                "shell_window_energy": shell_energy,
                "outer_active_energy": outer_energy,
                "outer_to_shell_energy": outer_energy / (shell_energy + EPSILON),
                "shell_fraction_of_total": shell_energy / (total_energy + EPSILON),
                "packet_peak_radius": peak_radius,
                "packet_centroid_radius": centroid,
                "packet_radial_width": _profile_width(centers, profile),
                "packet_radial_spread": spread,
                "shell_radial_flux": shell_flux,
                "shell_inward_flux": max(0.0, -shell_flux),
                "shell_outward_flux": max(0.0, shell_flux),
                "cumulative_inward_flux": cumulative_inward_flux,
                "cumulative_outward_flux": cumulative_outward_flux,
                "cumulative_positive_work": cumulative_positive_work,
                "cumulative_net_work": cumulative_net_work,
                "cumulative_damping_loss": cumulative_damping_loss,
                "total_lattice_energy": total_energy,
                "max_abs_displacement": max_abs_displacement,
                "max_abs_velocity": max_abs_velocity,
            }
        )

    if not timeseries:
        timeseries.append(_empty_timeseries_row(config, cumulative_positive_work, cumulative_net_work, cumulative_damping_loss))
    summary, events, threshold_counts, energy_audit = _summarize_variant(
        config,
        timeseries,
        cumulative_positive_work,
        cumulative_net_work,
        cumulative_damping_loss,
        burst_mask,
        shell_width,
        stopped_early,
        options,
    )
    _write_csv(run_dir / "central_burst_timeseries.csv", timeseries, _timeseries_fields())
    _write_csv(run_dir / "central_burst_events.csv", events, _event_fields())
    return {
        "summary": summary,
        "timeseries": timeseries,
        "events": events,
        "threshold_counts": threshold_counts,
        "energy_audit": energy_audit,
    }


def _apply_velocity_burst(
    lattice: Lattice3D,
    mask: np.ndarray,
    weights: np.ndarray,
    time: float,
    dt: float,
    options: CentralBurst3DOptions,
) -> float:
    if time > options.burst_duration:
        return 0.0
    scale = float(getattr(lattice.config, "_central_burst_acceleration_scale", 0.0))
    frequency = float(getattr(lattice.config, "_central_burst_frequency", lattice.config.drive_frequency))
    phase = np.clip(time / max(float(options.burst_duration), EPSILON), 0.0, 1.0)
    envelope = float(np.sin(np.pi * phase) ** 2)
    if envelope <= EPSILON or scale == 0.0:
        return 0.0
    before = lattice.v[mask].copy()
    kick = scale * envelope * math.sin(2.0 * math.pi * frequency * time) * dt * weights[mask]
    lattice.v[mask] += kick
    after = lattice.v[mask]
    return float(0.5 * np.sum(after**2 - before**2) * lattice.config.cell_volume)


def _summarize_variant(
    config: Prototype3DConfig,
    rows: list[dict[str, Any]],
    positive_work: float,
    net_work: float,
    damping_loss: float,
    burst_mask: np.ndarray,
    shell_width: float,
    stopped_early: bool,
    options: CentralBurst3DOptions,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    times = np.asarray([row["time"] for row in rows], dtype=float)
    shell = np.asarray([row["shell_window_energy"] for row in rows], dtype=float)
    outer_ratio = np.asarray([row["outer_to_shell_energy"] for row in rows], dtype=float)
    radius = np.asarray([row["packet_peak_radius"] for row in rows], dtype=float)
    centroid = np.asarray([row["packet_centroid_radius"] for row in rows], dtype=float)
    spread = np.asarray([row["packet_radial_spread"] for row in rows], dtype=float)
    post_indices = np.flatnonzero(times > config.drive_cutoff_time)
    peak_idx = int(post_indices[np.argmax(shell[post_indices])]) if post_indices.size else int(np.argmax(shell))
    peak_shell = float(shell[peak_idx]) if shell.size else 0.0
    arrival_threshold = max(options.arrival_threshold_fraction * peak_shell, positive_work * 1.0e-8)
    arrival_idx = _first_index(shell >= arrival_threshold)
    exit_threshold = max(options.exit_threshold_fraction * peak_shell, arrival_threshold)
    exit_idx = _exit_index(shell, peak_idx, exit_threshold, options.exit_hold_samples)
    event_options = _lifecycle_options(options)
    default_peaks = _major_peaks(times, shell, post_indices, event_options)
    events = _event_rows(config.name, times, shell, default_peaks, arrival_idx, exit_idx)
    threshold_counts = _threshold_counts(config, times, shell, post_indices, options)
    default = _threshold_row(threshold_counts, 0.30)
    strict_035 = _threshold_row(threshold_counts, 0.35)
    strict_040 = _threshold_row(threshold_counts, 0.40)
    tail_start = int(max(0, shell.size * 0.65))
    post_mask = times > config.drive_cutoff_time
    tail_mask = times >= 50.0
    radial_velocity, radial_r2 = _linear_fit(times[post_indices], centroid[post_indices]) if post_indices.size else (0.0, 0.0)
    width_velocity, width_r2 = _linear_fit(times[post_indices], spread[post_indices]) if post_indices.size else (0.0, 0.0)
    decay, decay_r2 = _decay_rate(times, shell, peak_idx)
    flux_in = float(rows[-1].get("cumulative_inward_flux") or 0.0)
    flux_out = float(rows[-1].get("cumulative_outward_flux") or 0.0)
    flux_total = flux_in + flux_out + EPSILON
    final_energy = float(rows[-1].get("total_lattice_energy") or 0.0)
    accounting_error = abs(final_energy + damping_loss - net_work) / max(positive_work, EPSILON)
    tail_shell_mean = _mean(shell[tail_start:])
    tail_outer_shell = _mean(outer_ratio[tail_start:])
    max_state = max(float(rows[-1].get("max_abs_displacement") or 0.0), float(rows[-1].get("max_abs_velocity") or 0.0))
    summary = {
        "variant": config.name,
        "branch": "central_hf_scattering_branch",
        "dt_variant": getattr(config, "_central_burst_dt_variant", "baseline_dt"),
        "dt_scale": getattr(config, "_central_burst_dt_scale", 1.0),
        "grid_size": config.grid_size,
        "dx": config.dx,
        "dt": config.dt,
        "physical_duration": config.physical_duration,
        "drive_cutoff_time": config.drive_cutoff_time,
        "burst_duration": options.burst_duration,
        "burst_radius": options.burst_radius,
        "burst_source_node_count": int(np.count_nonzero(burst_mask)),
        "burst_source_volume": float(np.count_nonzero(burst_mask) * config.cell_volume),
        "burst_frequency": getattr(config, "_central_burst_frequency", config.drive_frequency),
        "energy_label": getattr(config, "_central_burst_energy_label", ""),
        "burst_acceleration_scale": getattr(config, "_central_burst_acceleration_scale", 0.0),
        "boundary_drive_enabled": False,
        "no_boundary_drive": True,
        "no_active_second_pulse": True,
        "no_resonator_layer": True,
        "neutral_lattice": True,
        "positive_burst_work": positive_work,
        "net_burst_work": net_work,
        "damping_loss": damping_loss,
        "final_lattice_energy": final_energy,
        "energy_accounting_error": accounting_error,
        "energy_accounting_clean": accounting_error <= options.max_energy_accounting_error,
        "max_abs_displacement": float(rows[-1].get("max_abs_displacement") or 0.0),
        "max_abs_velocity": float(rows[-1].get("max_abs_velocity") or 0.0),
        "stopped_early": stopped_early,
        "state_stable": not stopped_early and max_state <= options.max_stable_abs_state,
        "shell_window_radius": options.shell_window_radius,
        "shell_window_width": shell_width,
        "first_shell_arrival_time": float(times[arrival_idx]) if arrival_idx is not None else None,
        "shell_peak_time": float(times[peak_idx]) if times.size else None,
        "shell_peak_energy": peak_shell,
        "near_shell_peak_per_work": peak_shell / (positive_work + EPSILON),
        "shell_exit_time": float(times[exit_idx]) if exit_idx is not None else None,
        "shell_exit_detected": exit_idx is not None,
        "major_peaks_at_0p30": int(default.get("major_shell_peak_count") or 0),
        "refocus_peaks_at_0p30": int(default.get("refocus_peak_count") or 0),
        "strict_major_peaks_at_0p35": int(strict_035.get("major_shell_peak_count") or 0),
        "strict_refocus_peaks_at_0p35": int(strict_035.get("refocus_peak_count") or 0),
        "strict_major_peaks_at_0p40": int(strict_040.get("major_shell_peak_count") or 0),
        "strict_refocus_peaks_at_0p40": int(strict_040.get("refocus_peak_count") or 0),
        "conservative_major_peaks": min(int(strict_035.get("major_shell_peak_count") or 0), int(strict_040.get("major_shell_peak_count") or 0)),
        "conservative_refocus_peaks": min(int(strict_035.get("refocus_peak_count") or 0), int(strict_040.get("refocus_peak_count") or 0)),
        "tail_shell_retention": tail_shell_mean / (peak_shell + EPSILON),
        "tail_outer_to_shell_mean": tail_outer_shell,
        "outer_shell_below_1": tail_outer_shell < 1.0,
        "global_peak_in_outer_window": float(radius[peak_idx]) >= max(config.defect_radius, 0.5 * config.domain_size - config.sponge_width),
        "packet_peak_radius_at_shell_peak": float(radius[peak_idx]) if radius.size else 0.0,
        "tail_packet_radius_mean": _mean(radius[tail_start:]),
        "packet_spread_at_shell_peak": float(spread[peak_idx]) if spread.size else 0.0,
        "tail_packet_spread_mean": _mean(spread[tail_start:]),
        "radial_packet_width_at_shell_peak": float(rows[peak_idx].get("packet_radial_width") or 0.0) if rows else 0.0,
        "radial_packet_width_tail_mean": _mean([row.get("packet_radial_width") for row in rows[tail_start:]]),
        "radial_group_velocity": radial_velocity,
        "radial_group_velocity_r2": radial_r2,
        "radial_width_velocity": width_velocity,
        "radial_width_velocity_r2": width_r2,
        "inward_flux_fraction": flux_in / flux_total,
        "outward_flux_fraction": flux_out / flux_total,
        "post_burst_decay": decay,
        "post_burst_decay_r2": decay_r2,
        "post_burst_shell_area": _area(times[post_mask], shell[post_mask]),
        "tail_area_after_t50": _area(times[tail_mask], shell[tail_mask]),
        "shell_energy_autocorrelation": _lag1_autocorrelation(shell[post_mask]),
        "dominant_spectral_concentration": _dominant_spectral_concentration(shell[post_mask]),
        "return_timing_regularity": _return_timing_regularity(times, shell, post_indices, event_options),
    }
    summary["central_burst_score"] = _score(summary)
    energy_audit = {
        "variant": config.name,
        "dt_variant": summary["dt_variant"],
        "positive_burst_work": positive_work,
        "net_burst_work": net_work,
        "damping_loss": damping_loss,
        "final_lattice_energy": final_energy,
        "energy_accounting_error": accounting_error,
        "energy_accounting_clean": summary["energy_accounting_clean"],
        "max_abs_displacement": summary["max_abs_displacement"],
        "max_abs_velocity": summary["max_abs_velocity"],
        "stopped_early": stopped_early,
    }
    return summary, events, threshold_counts, energy_audit


def _threshold_counts(
    config: Prototype3DConfig,
    times: np.ndarray,
    shell: np.ndarray,
    post_indices: np.ndarray,
    options: CentralBurst3DOptions,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_options = _lifecycle_options(options)
    for threshold in options.event_thresholds:
        event_options = replace(base_options, peak_threshold_fraction=float(threshold))
        peaks = _major_peaks(times, shell, post_indices, event_options)
        rows.append(
            {
                "variant": config.name,
                "dt_variant": getattr(config, "_central_burst_dt_variant", "baseline_dt"),
                "burst_frequency": getattr(config, "_central_burst_frequency", config.drive_frequency),
                "energy_label": getattr(config, "_central_burst_energy_label", ""),
                "peak_threshold_fraction": float(threshold),
                "major_shell_peak_count": len(peaks),
                "refocus_peak_count": _refocus_count(peaks, options.refocus_threshold_fraction),
            }
        )
    return rows


def _lifecycle_options(options: CentralBurst3DOptions) -> PacketLifecycle3DOptions:
    return PacketLifecycle3DOptions(
        output_root=options.output_root,
        grid_size=options.grid_size,
        physical_duration=options.physical_duration,
        sample_every=options.sample_every,
        diagnostic_sample_every=options.diagnostic_sample_every,
        radial_bins=options.radial_bins,
        shell_window_radius=options.shell_window_radius,
        shell_window_width=options.shell_window_width,
        near_shell_width_dx=options.near_shell_width_dx,
        sponge_strength_multiplier=options.sponge_strength_multiplier,
        arrival_threshold_fraction=options.arrival_threshold_fraction,
        exit_threshold_fraction=options.exit_threshold_fraction,
        exit_hold_samples=options.exit_hold_samples,
        peak_threshold_fraction=options.peak_threshold_fraction,
        refocus_threshold_fraction=options.refocus_threshold_fraction,
        min_peak_separation_time=options.min_peak_separation_time,
    )


def _burst_weights(radius: np.ndarray, mask: np.ndarray, burst_radius: float) -> np.ndarray:
    weights = np.zeros_like(radius)
    weights[mask] = np.exp(-((radius[mask] / max(burst_radius, EPSILON)) ** 2))
    maximum = float(np.max(weights[mask])) if np.any(mask) else 1.0
    return weights / max(maximum, EPSILON)


def _clean_repeated(row: dict[str, Any] | None, options: CentralBurst3DOptions) -> bool:
    if row is None:
        return False
    return (
        _repeated(row, options)
        and bool(row.get("no_boundary_drive"))
        and bool(row.get("energy_accounting_clean"))
        and bool(row.get("state_stable"))
        and not bool(row.get("shell_exit_detected"))
        and not bool(row.get("global_peak_in_outer_window"))
        and float(row.get("tail_outer_to_shell_mean") or 999.0) < options.max_outer_shell_ratio
        and float(row.get("tail_shell_retention") or 0.0) >= options.min_clean_retention
    )


def _repeated(row: dict[str, Any] | None, options: CentralBurst3DOptions) -> bool:
    if row is None:
        return False
    return (
        int(row.get("conservative_major_peaks") or 0) >= options.min_repeated_major_peaks
        and int(row.get("conservative_refocus_peaks") or 0) >= options.min_repeated_refocus_peaks
    )


def _ringing(row: dict[str, Any] | None, options: CentralBurst3DOptions) -> bool:
    if row is None:
        return False
    return (
        int(row.get("major_peaks_at_0p30") or 0) >= options.min_ring_major_peaks
        or float(row.get("tail_shell_retention") or 0.0) >= options.min_ring_retention
    )


def _score(row: dict[str, Any] | None) -> float:
    if not row:
        return 0.0
    major = float(row.get("conservative_major_peaks") or 0.0)
    refocus = float(row.get("conservative_refocus_peaks") or 0.0)
    default_major = float(row.get("major_peaks_at_0p30") or 0.0)
    default_refocus = float(row.get("refocus_peaks_at_0p30") or 0.0)
    retention = float(row.get("tail_shell_retention") or 0.0)
    outer = max(float(row.get("tail_outer_to_shell_mean") or 999.0), 0.1)
    clean = 1.0 if bool(row.get("energy_accounting_clean")) and not bool(row.get("global_peak_in_outer_window")) else 0.0
    no_exit = 1.0 if not bool(row.get("shell_exit_detected")) else 0.0
    regularity = float(row.get("return_timing_regularity") or 0.0)
    spectral = float(row.get("dominant_spectral_concentration") or 0.0)
    decay_penalty = abs(float(row.get("post_burst_decay") or 0.0))
    return (
        1000.0 * major
        + 100.0 * refocus
        + 20.0 * default_major
        + 5.0 * default_refocus
        + 20.0 * clean
        + 10.0 * no_exit
        + 10.0 * retention
        + 2.0 * regularity
        + 2.0 * spectral
        - decay_penalty
    ) / (1.0 + max(0.0, outer))


def _best_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(rows, key=_score, default=None)


def _threshold_row(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    return next((row for row in rows if abs(float(row.get("peak_threshold_fraction") or 0.0) - threshold) <= 1.0e-9), {})


def _count_label(row: dict[str, Any] | None, suffix: str) -> str:
    if not row:
        return "0/0"
    if suffix == "0p35":
        return f"{int(row.get('strict_major_peaks_at_0p35') or 0)}/{int(row.get('strict_refocus_peaks_at_0p35') or 0)}"
    return f"{int(row.get('major_peaks_at_0p30') or 0)}/{int(row.get('refocus_peaks_at_0p30') or 0)}"


def _mean(values: Any) -> float:
    parsed = np.asarray([float(value) for value in values if value is not None], dtype=float)
    return float(np.mean(parsed)) if parsed.size else 0.0


def _first_index(mask: np.ndarray) -> int | None:
    indices = np.flatnonzero(mask)
    return int(indices[0]) if indices.size else None


def _variant_name(role: str, frequency: float, energy_label: str) -> str:
    freq = f"{frequency:.3f}".rstrip("0").rstrip(".").replace(".", "p")
    safe_role = role.replace(" ", "_")
    return f"{safe_role}_central_hf_{freq}_{energy_label}"


def _empty_timeseries_row(
    config: Prototype3DConfig,
    positive_work: float,
    net_work: float,
    damping_loss: float,
) -> dict[str, Any]:
    return {
        "variant": config.name,
        "time": 0.0,
        "dt_variant": getattr(config, "_central_burst_dt_variant", "baseline_dt"),
        "burst_frequency": getattr(config, "_central_burst_frequency", config.drive_frequency),
        "energy_label": getattr(config, "_central_burst_energy_label", ""),
        "burst_acceleration_scale": getattr(config, "_central_burst_acceleration_scale", 0.0),
        "shell_window_energy": 0.0,
        "outer_active_energy": 0.0,
        "outer_to_shell_energy": 0.0,
        "shell_fraction_of_total": 0.0,
        "packet_peak_radius": 0.0,
        "packet_centroid_radius": 0.0,
        "packet_radial_width": 0.0,
        "packet_radial_spread": 0.0,
        "shell_radial_flux": 0.0,
        "shell_inward_flux": 0.0,
        "shell_outward_flux": 0.0,
        "cumulative_inward_flux": 0.0,
        "cumulative_outward_flux": 0.0,
        "cumulative_positive_work": positive_work,
        "cumulative_net_work": net_work,
        "cumulative_damping_loss": damping_loss,
        "total_lattice_energy": 0.0,
        "max_abs_displacement": 0.0,
        "max_abs_velocity": 0.0,
    }


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    threshold_rows: list[dict[str, Any]],
    energy_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: CentralBurst3DOptions,
) -> None:
    baseline = [row for row in rows if row.get("dt_variant") == "baseline_dt"]
    half = [row for row in rows if row.get("dt_variant") == "half_dt"]
    ranked = sorted(rows, key=_score, reverse=True)
    lines = [
        f"# Central HF Scattering Branch: {control_id}",
        "",
        "## Purpose",
        "",
        "Firewalled mechanism branch: test whether a direct central high-frequency velocity burst can create self-organized shell returns, threshold behavior, or a retained remnant without boundary phase release.",
        "",
        "This is not an improvement to the passive release-phase rule.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Ladder Results",
        "",
        "| Rank | Variant | dt | f | Energy | Work | Default | Strict 0.35 | Strict 0.40 | Ret | Outer/Shell | Exit | Global Outer | E Err | Score |",
        "| ---: | --- | --- | ---: | --- | ---: | --- | --- | --- | ---: | ---: | --- | --- | ---: | ---: |",
    ]
    for rank, row in enumerate(ranked, start=1):
        lines.append(
            "| "
            f"{rank} | "
            f"{row.get('variant')} | "
            f"{row.get('dt_variant')} | "
            f"{_format(row.get('burst_frequency'))} | "
            f"{row.get('energy_label')} | "
            f"{_format(row.get('positive_burst_work'))} | "
            f"{row.get('major_peaks_at_0p30')}/{row.get('refocus_peaks_at_0p30')} | "
            f"{row.get('strict_major_peaks_at_0p35')}/{row.get('strict_refocus_peaks_at_0p35')} | "
            f"{row.get('strict_major_peaks_at_0p40')}/{row.get('strict_refocus_peaks_at_0p40')} | "
            f"{_format(row.get('tail_shell_retention'))} | "
            f"{_format(row.get('tail_outer_to_shell_mean'))} | "
            f"{row.get('shell_exit_detected')} | "
            f"{row.get('global_peak_in_outer_window')} | "
            f"{_format(row.get('energy_accounting_error'))} | "
            f"{_format(row.get('central_burst_score'))} |"
        )
    lines.extend(
        [
            "",
            "## Threshold Counts",
            "",
            "| Variant | Threshold | Major | Refocus |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in threshold_rows:
        lines.append(
            "| "
            f"{row.get('variant')} | "
            f"{_format(row.get('peak_threshold_fraction'))} | "
            f"{row.get('major_shell_peak_count')} | "
            f"{row.get('refocus_peak_count')} |"
        )
    lines.extend(
        [
            "",
            "## Energy Accounting",
            "",
            "| Variant | Work+ | Net Work | Damping Loss | Final Energy | Error | Clean | Max |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
        ]
    )
    for row in energy_rows:
        lines.append(
            "| "
            f"{row.get('variant')} | "
            f"{_format(row.get('positive_burst_work'))} | "
            f"{_format(row.get('net_burst_work'))} | "
            f"{_format(row.get('damping_loss'))} | "
            f"{_format(row.get('final_lattice_energy'))} | "
            f"{_format(row.get('energy_accounting_error'))} | "
            f"{row.get('energy_accounting_clean')} | "
            f"{_format(max(float(row.get('max_abs_displacement') or 0.0), float(row.get('max_abs_velocity') or 0.0)))} |"
        )
    lines.extend(
        [
            "",
            "## Half-dt Check",
            "",
        ]
    )
    if half:
        row = half[0]
        lines.append(
            f"- Checked `{row.get('variant')}` at half dt: default `{row.get('major_peaks_at_0p30')}/{row.get('refocus_peaks_at_0p30')}`, strict `{row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')}`, clean repeated `{_clean_repeated(row, options)}`."
        )
    else:
        lines.append("- Half-dt check was disabled.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification, baseline, half),
            "",
            "## Files",
            "",
            "- `central_burst_summary.csv`",
            "- `central_burst_threshold_counts.csv`",
            "- `central_burst_timeseries.csv`",
            "- `central_burst_events.csv`",
            "- `central_burst_energy_audit.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any], baseline: list[dict[str, Any]], half: list[dict[str, Any]]) -> str:
    label = classification["label"]
    if label == "central_burst_nonlinear_threshold_candidate":
        return "The first ladder shows the desired nonlinear-threshold shape. The next step should be a tiny confirmation around the winning frequency/energy, not a broad sweep."
    if label == "central_burst_refocusing_supported":
        return "A central burst can produce clean repeated shell-window returns without boundary phase release. Confirm the local mechanism before adding defects or resonators."
    if label == "central_burst_dt_sensitive":
        return "The baseline ladder shows return structure, but the best row is not numerically settled. Treat the branch as suggestive only until a tighter, predicted dt check passes."
    return "The central burst response is transient under this ladder: early shell energy is not enough unless repeated clean returns survive the threshold and half-dt gates."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "central_burst_classification",
        "branch",
        "dt_variant",
        "dt_scale",
        "grid_size",
        "dx",
        "dt",
        "physical_duration",
        "drive_cutoff_time",
        "burst_duration",
        "burst_radius",
        "burst_source_node_count",
        "burst_source_volume",
        "burst_frequency",
        "energy_label",
        "burst_acceleration_scale",
        "boundary_drive_enabled",
        "no_boundary_drive",
        "no_active_second_pulse",
        "no_resonator_layer",
        "neutral_lattice",
        "positive_burst_work",
        "net_burst_work",
        "damping_loss",
        "final_lattice_energy",
        "energy_accounting_error",
        "energy_accounting_clean",
        "max_abs_displacement",
        "max_abs_velocity",
        "stopped_early",
        "state_stable",
        "shell_window_radius",
        "shell_window_width",
        "first_shell_arrival_time",
        "shell_peak_time",
        "shell_peak_energy",
        "near_shell_peak_per_work",
        "shell_exit_time",
        "shell_exit_detected",
        "major_peaks_at_0p30",
        "refocus_peaks_at_0p30",
        "strict_major_peaks_at_0p35",
        "strict_refocus_peaks_at_0p35",
        "strict_major_peaks_at_0p40",
        "strict_refocus_peaks_at_0p40",
        "conservative_major_peaks",
        "conservative_refocus_peaks",
        "tail_shell_retention",
        "tail_outer_to_shell_mean",
        "outer_shell_below_1",
        "global_peak_in_outer_window",
        "packet_peak_radius_at_shell_peak",
        "tail_packet_radius_mean",
        "packet_spread_at_shell_peak",
        "tail_packet_spread_mean",
        "radial_packet_width_at_shell_peak",
        "radial_packet_width_tail_mean",
        "radial_group_velocity",
        "radial_group_velocity_r2",
        "radial_width_velocity",
        "radial_width_velocity_r2",
        "inward_flux_fraction",
        "outward_flux_fraction",
        "post_burst_decay",
        "post_burst_decay_r2",
        "post_burst_shell_area",
        "tail_area_after_t50",
        "shell_energy_autocorrelation",
        "dominant_spectral_concentration",
        "return_timing_regularity",
        "central_burst_score",
    ]


def _timeseries_fields() -> list[str]:
    return [
        "variant",
        "time",
        "dt_variant",
        "burst_frequency",
        "energy_label",
        "burst_acceleration_scale",
        "shell_window_energy",
        "outer_active_energy",
        "outer_to_shell_energy",
        "shell_fraction_of_total",
        "packet_peak_radius",
        "packet_centroid_radius",
        "packet_radial_width",
        "packet_radial_spread",
        "shell_radial_flux",
        "shell_inward_flux",
        "shell_outward_flux",
        "cumulative_inward_flux",
        "cumulative_outward_flux",
        "cumulative_positive_work",
        "cumulative_net_work",
        "cumulative_damping_loss",
        "total_lattice_energy",
        "max_abs_displacement",
        "max_abs_velocity",
    ]


def _event_fields() -> list[str]:
    return ["variant", "event", "time", "energy", "peak_rank"]


def _threshold_fields() -> list[str]:
    return [
        "variant",
        "central_burst_classification",
        "dt_variant",
        "burst_frequency",
        "energy_label",
        "peak_threshold_fraction",
        "major_shell_peak_count",
        "refocus_peak_count",
    ]


def _energy_fields() -> list[str]:
    return [
        "variant",
        "central_burst_classification",
        "dt_variant",
        "positive_burst_work",
        "net_burst_work",
        "damping_loss",
        "final_lattice_energy",
        "energy_accounting_error",
        "energy_accounting_clean",
        "max_abs_displacement",
        "max_abs_velocity",
        "stopped_early",
    ]
