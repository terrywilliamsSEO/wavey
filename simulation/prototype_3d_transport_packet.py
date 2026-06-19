"""3D transport-packet diagnostics for clean cubic shell-window tails."""

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
from .prototype_3d import (
    EPSILON,
    Lattice3D,
    Prototype3DConfig,
    Prototype3DOptions,
    _calibrate_amplitude,
    _radial_bins,
    _run_variant,
    _summary_fields as _prototype_summary_fields,
    _write_csv as _write_prototype_csv,
)
from .prototype_3d_audit import Prototype3DFailureAuditOptions, run_3d_failure_audit
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _phase_vector, _shell_width, _threshold_like_options, _weighted_coherence, _weighted_phase_mean
from .prototype_3d_source_sponge import _effective_source_area, _format, _merge_rows, _write_csv
from .prototype_3d_standing_persistence import _variant_plan as _standing_variant_plan
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


@dataclass(frozen=True)
class TransportPacket3DOptions:
    """Options for a tiny 3D coherent-transport packet audit."""

    output_root: str = "runs"
    grid_size: int = 41
    reference_source_grid_size: int = 31
    sample_every: int = 10
    diagnostic_sample_every: int = 4
    radial_bins: int = 32
    shell_window_radius: float = 5.0
    shell_window_width: float | None = None
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    target_work_per_source_area: float | None = None
    phase_offset: float = 0.5 * float(np.pi)
    arrival_threshold_fraction: float = 0.10
    exit_threshold_fraction: float = 0.15
    exit_hold_samples: int = 5
    max_lag_samples: int = 80
    min_abs_radial_group_velocity: float = 0.05
    min_directional_flux_fraction: float = 0.60
    max_stationary_radial_velocity: float = 0.03
    min_phase_or_angular_drift_rate: float = 0.02


def run_3d_transport_packet_audit(
    base_config: SimulationConfig,
    *,
    options: TransportPacket3DOptions | None = None,
) -> dict[str, Any]:
    """Run the two clean cubic variants and diagnose packet-like shell-window motion."""

    options = options or TransportPacket3DOptions()
    control_id = datetime.now().strftime("transport_packet_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    reference_config = variants[0]
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
    prototype_options = Prototype3DOptions(
        output_root=options.output_root,
        grid_size=options.grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        include_dt_control=False,
        include_sponge_control=False,
    )

    rows: list[dict[str, Any]] = []
    configs_by_variant: dict[str, Prototype3DConfig] = {}
    for config in variants:
        config.drive_amplitude = reference_drive_amplitude
        target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
        _calibrate_amplitude(config, target_work)
        summary = _run_variant(config, root, prototype_options)
        _add_control_fields(summary, config, reference_config, options, target_work_per_area)
        summary["classification_label"] = None
        rows.append(summary)
        configs_by_variant[config.name] = config

    prototype_summary_csv = root / "prototype_3d_summary.csv"
    _write_prototype_csv(prototype_summary_csv, rows, _prototype_summary_fields())
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": control_id,
            "classification": {
                "label": "transport_packet_3d",
                "reason": "Two-variant neutral cubic shell-window transport-packet audit.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "transport_packet_3d_report.md"),
        },
    )

    audit = run_3d_failure_audit(
        root,
        base_config,
        options=Prototype3DFailureAuditOptions(
            output_dir=root / "failure_mode_audit",
            radial_bins=options.radial_bins,
            near_shell_width_dx=options.near_shell_width_dx,
        ),
    )
    control_rows = _merge_rows(rows, audit["variants"])
    diagnostic_rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    lag_rows: list[dict[str, Any]] = []
    for row in control_rows:
        config = configs_by_variant[row["variant"]]
        diagnostics = _run_packet_diagnostics(config, root, row, options)
        diagnostic_rows.append(diagnostics["summary"])
        timeseries_rows.extend(diagnostics["timeseries"])
        lag_rows.extend(diagnostics["lag_correlation"])

    combined_rows = _combine_rows(control_rows, diagnostic_rows)
    classification = classify_transport_packet(combined_rows, options)
    for row in combined_rows:
        row["transport_packet_classification"] = classification["label"]

    summary_csv = root / "transport_packet_summary.csv"
    timeseries_csv = root / "transport_packet_timeseries.csv"
    lag_csv = root / "packet_lag_correlation.csv"
    report_path = root / "transport_packet_3d_report.md"
    _write_csv(summary_csv, combined_rows, _summary_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(lag_csv, lag_rows, _lag_fields())
    _plot_timeseries(root / "shell_energy_and_flux_plot.png", timeseries_rows, ("shell_window_energy", "shell_radial_flux"), "Shell Energy And Radial Flux")
    _plot_timeseries(root / "radial_motion_plot.png", timeseries_rows, ("active_radial_centroid", "active_radial_peak_radius", "shell_centroid_radius"), "Radial Motion")
    _plot_timeseries(root / "phase_angular_drift_plot.png", timeseries_rows, ("shell_phase_unwrapped", "cumulative_angular_drift"), "Phase And Angular Drift")
    _plot_lag_correlation(root / "packet_lag_correlation_plot.png", lag_rows)
    _write_report(report_path, control_id, combined_rows, classification, options, audit)
    save_json(
        root / "transport_packet_3d_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": combined_rows,
            "summary_csv": str(summary_csv),
            "timeseries_csv": str(timeseries_csv),
            "lag_correlation_csv": str(lag_csv),
            "report_path": str(report_path),
            "audit_report_path": audit["report_path"],
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": combined_rows,
        "summary_csv": str(summary_csv),
        "timeseries_csv": str(timeseries_csv),
        "lag_correlation_csv": str(lag_csv),
        "report_path": str(report_path),
        "audit_report_path": audit["report_path"],
        "path": str(root),
    }


def classify_transport_packet(
    rows: list[dict[str, Any]],
    options: TransportPacket3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the clean shell tail behaves like packet motion or modal drift."""

    options = options or TransportPacket3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No transport-packet rows were available.", "checks": {}}
    checks = {row["variant"]: _row_checks(row, options) for row in rows}
    moving = [row for row in rows if _transport_like(row, options)]
    drifting = [row for row in rows if _drift_like(row, options)]
    if len(moving) == len(rows) and not drifting:
        return {
            "label": "moving_transport_packet_supported",
            "reason": "Both clean cubic variants show directional radial motion, flux, or shell-window exit timing consistent with a moving transport packet.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if len(drifting) == len(rows) and not moving:
        return {
            "label": "drifting_modal_structure_supported",
            "reason": "Both clean cubic variants show little radial transport but persistent phase or angular drift, consistent with a drifting modal structure.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if moving or drifting:
        return {
            "label": "mixed_transport_and_drift",
            "reason": "The clean cubic variants show both transport-like motion and drift-like modal signatures; treat the shell tail as a moving coherent structure until follow-up separates them.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "packet_motion_inconclusive",
        "reason": "The audit did not find enough directional motion, exit timing, or modal drift to distinguish packet transport from a weak coherent tail.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: TransportPacket3DOptions) -> list[Prototype3DConfig]:
    return _standing_variant_plan(base, options)


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    reference_config: Prototype3DConfig,
    options: TransportPacket3DOptions,
    target_work_per_area: float,
) -> None:
    summary["packet_role"] = "cubic_reference" if config.name == "neutral_cubic_sign_flip_reference" else "cubic_phase_offset_control"
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    original_sponge_strength = reference_config.sponge_strength / max(options.sponge_strength_multiplier, EPSILON)
    summary["sponge_strength_multiplier_vs_original"] = config.sponge_strength / max(original_sponge_strength, EPSILON)
    summary["source_width_physical_reference"] = reference_config.boundary_source_width
    summary["target_reference_work_per_source_area"] = target_work_per_area
    summary["calibration_source_grid_size"] = options.reference_source_grid_size


def _run_packet_diagnostics(
    config: Prototype3DConfig,
    root: Path,
    summary_row: dict[str, Any],
    options: TransportPacket3DOptions,
) -> dict[str, Any]:
    diag_dir = root / "transport_packet" / config.name
    diag_dir.mkdir(parents=True, exist_ok=True)
    lattice = Lattice3D(config)
    coords = lattice.coords
    radius = coords["radius"]
    shell_width = _shell_width(config, options)
    shell_outer = options.shell_window_radius + shell_width
    shell_mid = options.shell_window_radius + 0.5 * shell_width
    shell_mask = (radius > options.shell_window_radius) & (radius <= shell_outer)
    non_sponge_mask = coords["boundary_distance"] >= config.sponge_width
    omega = 2.0 * np.pi * max(config.drive_frequency, EPSILON)
    bins = _radial_bins(config, options.radial_bins)
    centers = 0.5 * (bins[:-1] + bins[1:])
    source_radius = _weighted_mean(radius, lattice.source.geometric_weights)

    rows: list[dict[str, Any]] = []
    frames: list[np.ndarray] = []
    directions: list[np.ndarray] = []
    phases: list[float] = []
    for step in range(config.steps):
        time = step * config.dt
        lattice.step(time, config.dt)
        if step % max(1, options.diagnostic_sample_every) != 0 and step != config.steps - 1:
            continue
        energy = lattice.energy_density()
        phase_vector = _phase_vector(lattice.u, lattice.v, omega)
        flux_density = _radial_flux_density(lattice)
        profile = _radial_profile_sum(energy, radius, bins)
        active_peak_radius = float(centers[int(np.argmax(profile))]) if profile.size else 0.0
        active_energy = energy[non_sponge_mask]
        active_radius = radius[non_sponge_mask]
        active_centroid = _weighted_mean(active_radius, active_energy)
        shell_energy = float(np.sum(energy[shell_mask]))
        shell_values = energy[shell_mask].astype(float).ravel()
        shell_phase = _weighted_phase_mean(phase_vector[shell_mask], energy[shell_mask])
        shell_coherence = _weighted_coherence(phase_vector[shell_mask], energy[shell_mask])
        shell_centroid = _centroid(coords, energy, shell_mask)
        direction = _unit(shell_centroid)
        shell_flux = float(np.sum(flux_density[shell_mask]))
        frames.append(shell_values)
        directions.append(direction)
        phases.append(shell_phase)
        rows.append(
            {
                "variant": config.name,
                "time": time,
                "shell_window_energy": shell_energy,
                "shell_fraction_of_total": shell_energy / (float(np.sum(energy)) + EPSILON),
                "active_radial_centroid": active_centroid,
                "active_radial_peak_radius": active_peak_radius,
                "shell_centroid_x": float(shell_centroid[0]),
                "shell_centroid_y": float(shell_centroid[1]),
                "shell_centroid_z": float(shell_centroid[2]),
                "shell_centroid_radius": float(np.linalg.norm(shell_centroid)),
                "shell_phase": shell_phase,
                "shell_phase_coherence": shell_coherence,
                "shell_radial_flux": shell_flux,
                "shell_inward_flux": max(0.0, -shell_flux),
                "shell_outward_flux": max(0.0, shell_flux),
            }
        )

    if not rows:
        return {"summary": {"variant": config.name}, "timeseries": [], "lag_correlation": []}

    _add_motion_derivatives(rows, frames, directions, phases)
    lag_rows, lag_summary = _lag_correlation_rows(config.name, frames, config.dt * options.diagnostic_sample_every, options.max_lag_samples)
    summary = _packet_summary(config, rows, lag_summary, summary_row, source_radius, shell_mid, shell_width, options)
    _plot_midplane_path(diag_dir / "shell_centroid_path.png", rows, config)
    return {"summary": summary, "timeseries": rows, "lag_correlation": lag_rows}


def _packet_summary(
    config: Prototype3DConfig,
    rows: list[dict[str, Any]],
    lag_summary: dict[str, float],
    summary_row: dict[str, Any],
    source_radius: float,
    shell_mid: float,
    shell_width: float,
    options: TransportPacket3DOptions,
) -> dict[str, Any]:
    times = np.asarray([row["time"] for row in rows], dtype=float)
    shell_energy = np.asarray([row["shell_window_energy"] for row in rows], dtype=float)
    active_centroid = np.asarray([row["active_radial_centroid"] for row in rows], dtype=float)
    peak_idx = int(np.argmax(shell_energy))
    peak_energy = float(shell_energy[peak_idx])
    threshold = max(options.arrival_threshold_fraction * peak_energy, float(summary_row.get("positive_work_before_cutoff") or 0.0) * 1.0e-8)
    arrival_idx = _first_index(shell_energy >= threshold)
    exit_idx = _exit_index(shell_energy, peak_idx, max(options.exit_threshold_fraction * peak_energy, threshold), options.exit_hold_samples)
    arrival_time = float(times[arrival_idx]) if arrival_idx is not None else None
    peak_time = float(times[peak_idx])
    exit_time = float(times[exit_idx]) if exit_idx is not None else None
    dwell_time = (exit_time - arrival_time) if exit_time is not None and arrival_time is not None else None
    fit_stop = peak_idx if arrival_idx is None else max(peak_idx, arrival_idx + 2)
    fit_start_time = 0.0 if arrival_time is None else max(0.0, arrival_time - 18.0)
    fit_mask = (times >= fit_start_time) & (np.arange(times.size) <= fit_stop)
    radial_group_velocity, radial_group_r2 = _linear_fit(times[fit_mask], active_centroid[fit_mask])
    phase_velocity, phase_velocity_r2 = _linear_fit(times, np.unwrap(np.asarray([row["shell_phase"] for row in rows], dtype=float)))
    total_inward_flux = float(np.sum([row["shell_inward_flux"] for row in rows]))
    total_outward_flux = float(np.sum([row["shell_outward_flux"] for row in rows]))
    flux_total = total_inward_flux + total_outward_flux + EPSILON
    inward_fraction = total_inward_flux / flux_total
    outward_fraction = total_outward_flux / flux_total
    boundary_to_shell_distance = max(0.0, source_radius - shell_mid)
    time_of_flight_velocity = boundary_to_shell_distance / arrival_time if arrival_time and arrival_time > EPSILON else None
    expected_crossing_time = shell_width / abs(radial_group_velocity) if abs(radial_group_velocity) > EPSILON else None
    exit_delay_ratio = dwell_time / expected_crossing_time if dwell_time is not None and expected_crossing_time and expected_crossing_time > EPSILON else None
    frame_similarities = [row.get("frame_to_frame_similarity") for row in rows if row.get("frame_to_frame_similarity") is not None]
    displacement_speeds = [row.get("centroid_displacement_speed") for row in rows if row.get("centroid_displacement_speed") is not None]
    angular_steps = [row.get("angular_step") for row in rows if row.get("angular_step") is not None]
    radial_speeds = [row.get("shell_centroid_radial_speed") for row in rows if row.get("shell_centroid_radial_speed") is not None]
    phase_velocities = [row.get("shell_phase_velocity") for row in rows if row.get("shell_phase_velocity") is not None]
    return {
        "variant": config.name,
        "packet_role": summary_row.get("packet_role"),
        "drive_phase_mode": config.drive_phase_mode,
        "boundary_phase_offset": config.boundary_phase_offset,
        "boundary_cubic_phase_sign": config.boundary_cubic_phase_sign,
        "work_per_source_area": summary_row.get("work_per_source_area"),
        "positive_work_before_cutoff": summary_row.get("positive_work_before_cutoff"),
        "near_shell_tail_retention": summary_row.get("near_shell_tail_retention"),
        "outer_to_near_tail_energy_ratio": summary_row.get("outer_to_near_tail_energy_ratio"),
        "global_peak_in_outer_window": summary_row.get("global_peak_in_outer_window"),
        "shell_window_radius": options.shell_window_radius,
        "shell_window_width": shell_width,
        "source_radius_mean": source_radius,
        "boundary_to_shell_distance": boundary_to_shell_distance,
        "first_shell_arrival_time": arrival_time,
        "shell_peak_time": peak_time,
        "shell_exit_time": exit_time,
        "shell_exit_detected": exit_time is not None,
        "shell_dwell_time": dwell_time,
        "time_of_flight_velocity": time_of_flight_velocity,
        "radial_group_velocity": radial_group_velocity,
        "radial_group_velocity_r2": radial_group_r2,
        "expected_shell_crossing_time": expected_crossing_time,
        "exit_delay_ratio": exit_delay_ratio,
        "mean_shell_radial_speed": _mean_abs(radial_speeds),
        "mean_centroid_displacement_speed": _mean_abs(displacement_speeds),
        "mean_angular_drift_rate": _mean_abs([step / (config.dt * options.diagnostic_sample_every) for step in angular_steps]),
        "cumulative_angular_drift": rows[-1].get("cumulative_angular_drift"),
        "shell_phase_velocity": phase_velocity,
        "shell_phase_velocity_r2": phase_velocity_r2,
        "mean_abs_shell_phase_velocity": _mean_abs(phase_velocities),
        "mean_shell_phase_coherence": _mean([row.get("shell_phase_coherence") for row in rows]),
        "mean_shell_radial_flux": _mean([row.get("shell_radial_flux") for row in rows]),
        "mean_inward_flux": _mean([row.get("shell_inward_flux") for row in rows]),
        "mean_outward_flux": _mean([row.get("shell_outward_flux") for row in rows]),
        "inward_flux_fraction": inward_fraction,
        "outward_flux_fraction": outward_fraction,
        "mean_frame_to_frame_similarity": _mean(frame_similarities),
        "min_frame_to_frame_similarity": _min(frame_similarities),
        "lag1_shell_pattern_similarity": lag_summary["lag1"],
        "peak_lag_shell_pattern_similarity": lag_summary["peak"],
        "peak_lag_time": lag_summary["peak_lag_time"],
        "shell_energy_peak": peak_energy,
        "shell_energy_tail_mean": _mean(shell_energy[int(max(0, shell_energy.size * 0.65)) :].tolist()),
    }


def _row_checks(row: dict[str, Any], options: TransportPacket3DOptions) -> dict[str, Any]:
    return {
        "radial_group_velocity": row.get("radial_group_velocity"),
        "inward_flux_fraction": row.get("inward_flux_fraction"),
        "outward_flux_fraction": row.get("outward_flux_fraction"),
        "shell_exit_detected": row.get("shell_exit_detected"),
        "mean_angular_drift_rate": row.get("mean_angular_drift_rate"),
        "shell_phase_velocity": row.get("shell_phase_velocity"),
    }


def _transport_like(row: dict[str, Any], options: TransportPacket3DOptions) -> bool:
    radial_velocity = abs(float(row.get("radial_group_velocity") or 0.0))
    directional_flux = max(float(row.get("inward_flux_fraction") or 0.0), float(row.get("outward_flux_fraction") or 0.0))
    return (
        bool(row.get("shell_exit_detected"))
        or radial_velocity >= options.min_abs_radial_group_velocity
        or directional_flux >= options.min_directional_flux_fraction
    )


def _drift_like(row: dict[str, Any], options: TransportPacket3DOptions) -> bool:
    radial_velocity = abs(float(row.get("radial_group_velocity") or 0.0))
    phase_velocity = abs(float(row.get("shell_phase_velocity") or 0.0))
    angular_drift = abs(float(row.get("mean_angular_drift_rate") or 0.0))
    return (
        not bool(row.get("shell_exit_detected"))
        and radial_velocity <= options.max_stationary_radial_velocity
        and max(phase_velocity, angular_drift) >= options.min_phase_or_angular_drift_rate
    )


def _combine_rows(control_rows: list[dict[str, Any]], diagnostic_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics = {row["variant"]: row for row in diagnostic_rows}
    return [{**row, **diagnostics.get(row["variant"], {})} for row in control_rows]


def _add_motion_derivatives(rows: list[dict[str, Any]], frames: list[np.ndarray], directions: list[np.ndarray], phases: list[float]) -> None:
    unwrapped = np.unwrap(np.asarray(phases, dtype=float))
    cumulative_angle = 0.0
    for idx, row in enumerate(rows):
        row["shell_phase_unwrapped"] = float(unwrapped[idx])
        if idx == 0:
            row["shell_phase_velocity"] = None
            row["frame_to_frame_similarity"] = None
            row["centroid_displacement_speed"] = None
            row["shell_centroid_radial_speed"] = None
            row["angular_step"] = None
            row["cumulative_angular_drift"] = 0.0
            continue
        dt = max(float(row["time"]) - float(rows[idx - 1]["time"]), EPSILON)
        row["shell_phase_velocity"] = float((unwrapped[idx] - unwrapped[idx - 1]) / dt)
        row["frame_to_frame_similarity"] = _corr(frames[idx - 1], frames[idx])
        prev_centroid = np.asarray(
            [rows[idx - 1]["shell_centroid_x"], rows[idx - 1]["shell_centroid_y"], rows[idx - 1]["shell_centroid_z"]],
            dtype=float,
        )
        centroid = np.asarray([row["shell_centroid_x"], row["shell_centroid_y"], row["shell_centroid_z"]], dtype=float)
        row["centroid_displacement_speed"] = float(np.linalg.norm(centroid - prev_centroid) / dt)
        row["shell_centroid_radial_speed"] = float((row["shell_centroid_radius"] - rows[idx - 1]["shell_centroid_radius"]) / dt)
        angular_step = _angle_between(directions[idx - 1], directions[idx])
        cumulative_angle += angular_step
        row["angular_step"] = angular_step
        row["cumulative_angular_drift"] = cumulative_angle


def _radial_flux_density(lattice: Lattice3D) -> np.ndarray:
    grad_z, grad_y, grad_x = np.gradient(lattice.u, lattice.config.dx, edge_order=1)
    coords = lattice.coords
    radius = np.maximum(coords["radius"], EPSILON)
    radial_gradient = (grad_x * coords["x"] + grad_y * coords["y"] + grad_z * coords["z"]) / radius
    return -lattice.config.coupling_strength * lattice.v * radial_gradient * lattice.config.cell_volume


def _radial_profile_sum(energy: np.ndarray, radius: np.ndarray, bins: np.ndarray) -> np.ndarray:
    indices = np.clip(np.digitize(radius.ravel(), bins) - 1, 0, len(bins) - 2)
    return np.bincount(indices, weights=energy.ravel(), minlength=len(bins) - 1)


def _centroid(coords: dict[str, np.ndarray], energy: np.ndarray, mask: np.ndarray) -> np.ndarray:
    weights = energy[mask]
    total = float(np.sum(weights))
    if total <= EPSILON:
        return np.zeros(3, dtype=float)
    return np.asarray(
        [
            float(np.sum(coords["x"][mask] * weights) / total),
            float(np.sum(coords["y"][mask] * weights) / total),
            float(np.sum(coords["z"][mask] * weights) / total),
        ],
        dtype=float,
    )


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= EPSILON:
        return 0.0
    return float(np.sum(values * weights) / total)


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= EPSILON:
        return np.zeros_like(vector)
    return vector / norm


def _angle_between(first: np.ndarray, second: np.ndarray) -> float:
    if np.linalg.norm(first) <= EPSILON or np.linalg.norm(second) <= EPSILON:
        return 0.0
    return float(np.arccos(np.clip(float(np.dot(first, second)), -1.0, 1.0)))


def _linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if x.size < 3 or y.size < 3:
        return 0.0, 0.0
    if float(np.ptp(x)) <= EPSILON or float(np.ptp(y)) <= EPSILON:
        return 0.0, 0.0
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r2 = 1.0 - ss_res / (ss_tot + EPSILON)
    return float(slope), float(np.clip(r2, 0.0, 1.0))


def _first_index(mask: np.ndarray) -> int | None:
    indices = np.flatnonzero(mask)
    return int(indices[0]) if indices.size else None


def _exit_index(values: np.ndarray, peak_idx: int, threshold: float, hold_samples: int) -> int | None:
    hold = max(1, int(hold_samples))
    for idx in range(peak_idx + 1, values.size):
        if np.all(values[idx : min(values.size, idx + hold)] <= threshold):
            return idx
    return None


def _lag_correlation_rows(variant: str, frames: list[np.ndarray], dt: float, max_lag: int) -> tuple[list[dict[str, Any]], dict[str, float]]:
    rows = []
    if len(frames) < 3:
        return rows, {"lag1": 0.0, "peak": 0.0, "peak_lag_time": 0.0}
    limit = min(max(2, max_lag), len(frames) - 1)
    for lag in range(1, limit + 1):
        values = [_corr(frames[idx], frames[idx + lag]) for idx in range(0, len(frames) - lag)]
        rows.append(
            {
                "variant": variant,
                "lag_index": lag,
                "lag_time": lag * dt,
                "mean_shell_pattern_correlation": _mean(values),
                "min_shell_pattern_correlation": _min(values),
            }
        )
    peak = max(rows[1:], key=lambda row: row["mean_shell_pattern_correlation"], default={"mean_shell_pattern_correlation": 0.0, "lag_time": 0.0})
    return rows, {"lag1": rows[0]["mean_shell_pattern_correlation"], "peak": peak["mean_shell_pattern_correlation"], "peak_lag_time": peak["lag_time"]}


def _corr(first: np.ndarray, second: np.ndarray) -> float:
    first = np.asarray(first, dtype=float).ravel()
    second = np.asarray(second, dtype=float).ravel()
    if first.size == 0 or second.size == 0 or first.size != second.size:
        return 0.0
    first = first - float(np.mean(first))
    second = second - float(np.mean(second))
    denom = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denom <= EPSILON:
        return 0.0
    return float(np.clip(np.dot(first, second) / denom, -1.0, 1.0))


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(max(rows, key=_packet_score).get("variant", "n/a"))


def _packet_score(row: dict[str, Any]) -> float:
    retention = float(row.get("near_shell_tail_retention") or 0.0)
    directional_flux = max(float(row.get("inward_flux_fraction") or 0.0), float(row.get("outward_flux_fraction") or 0.0))
    motion = abs(float(row.get("radial_group_velocity") or 0.0)) + float(row.get("mean_centroid_displacement_speed") or 0.0)
    outer = max(float(row.get("outer_to_near_tail_energy_ratio") or 999.0), 0.25)
    outer_penalty = 0.5 if bool(row.get("global_peak_in_outer_window")) else 1.0
    return retention * (0.5 + directional_flux) * (0.5 + motion) * outer_penalty / outer


def _mean(values: list[Any]) -> float:
    parsed = [float(value) for value in values if value is not None]
    return float(np.mean(parsed)) if parsed else 0.0


def _mean_abs(values: list[Any]) -> float:
    parsed = [abs(float(value)) for value in values if value is not None]
    return float(np.mean(parsed)) if parsed else 0.0


def _min(values: list[Any]) -> float:
    parsed = [float(value) for value in values if value is not None]
    return float(np.min(parsed)) if parsed else 0.0


def _plot_timeseries(path: Path, rows: list[dict[str, Any]], keys: tuple[str, ...], title: str) -> None:
    fig, axes = plt.subplots(len(keys), 1, figsize=(8, max(3, 2.4 * len(keys))), dpi=140, sharex=True)
    if len(keys) == 1:
        axes = [axes]
    for ax, key in zip(axes, keys):
        for variant in _variants(rows):
            subset = [row for row in rows if row["variant"] == variant]
            ax.plot([row["time"] for row in subset], [row.get(key) or 0.0 for row in subset], label=variant)
        ax.set_ylabel(key)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7)
    axes[0].set_title(title)
    axes[-1].set_xlabel("time")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_lag_correlation(path: Path, rows: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    for variant in _variants(rows):
        subset = [row for row in rows if row["variant"] == variant]
        ax.plot([row["lag_time"] for row in subset], [row["mean_shell_pattern_correlation"] for row in subset], label=variant)
    ax.set_xlabel("lag time")
    ax.set_ylabel("mean shell-pattern correlation")
    ax.set_title("Time-Lagged Shell-Pattern Similarity")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_midplane_path(path: Path, rows: list[dict[str, Any]], config: Prototype3DConfig) -> None:
    fig, ax = plt.subplots(figsize=(5, 5), dpi=140)
    xs = [row["shell_centroid_x"] for row in rows]
    ys = [row["shell_centroid_y"] for row in rows]
    sc = ax.scatter(xs, ys, c=[row["time"] for row in rows], s=10, cmap="viridis")
    ax.set_xlim(-0.5 * config.domain_size, 0.5 * config.domain_size)
    ax.set_ylim(-0.5 * config.domain_size, 0.5 * config.domain_size)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(f"Shell centroid midplane path: {config.name}")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04, label="time")
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
    options: TransportPacket3DOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Transport-Packet Audit: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny two-variant audit for the question: is the shell-window tail a moving wavefront / "
            "transport packet, or a slowly rotating / drifting modal structure?"
        ),
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Ret | Outer/Near | Arrival | Exit | Dwell | Radial V | Flux In | Flux Out | Phase V | Angular Drift | F2F | Lag Peak |",
        "| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('near_shell_tail_retention'))} | "
            f"{_format(row.get('outer_to_near_tail_energy_ratio'))} | "
            f"{_format(row.get('first_shell_arrival_time'))} | "
            f"{row.get('shell_exit_detected')} | "
            f"{_format(row.get('shell_dwell_time'))} | "
            f"{_format(row.get('radial_group_velocity'))} | "
            f"{_format(row.get('inward_flux_fraction'))} | "
            f"{_format(row.get('outward_flux_fraction'))} | "
            f"{_format(row.get('shell_phase_velocity'))} | "
            f"{_format(row.get('mean_angular_drift_rate'))} | "
            f"{_format(row.get('mean_frame_to_frame_similarity'))} | "
            f"{_format(row.get('peak_lag_shell_pattern_similarity'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Diagnostics",
            "",
            "- Shell-window phase velocity is the fitted slope of unwrapped shell quadrature phase.",
            "- Radial group velocity is the fitted pre-peak slope of active-domain radial energy centroid.",
            "- Shell radial flux is a wave-equation proxy: positive values are outward and negative values are inward.",
            "- Angular drift tracks the energy-weighted shell centroid direction on the sphere.",
            "- Frame-to-frame displacement uses shell-centroid speed and shell-pattern correlation as an optical-flow-style proxy.",
            "- Exit timing checks whether shell energy drops below the post-peak threshold for consecutive samples.",
            "",
            "## Files",
            "",
            "- `transport_packet_summary.csv`",
            "- `transport_packet_timeseries.csv`",
            "- `packet_lag_correlation.csv`",
            "- `shell_energy_and_flux_plot.png`",
            "- `radial_motion_plot.png`",
            "- `phase_angular_drift_plot.png`",
            "- `packet_lag_correlation_plot.png`",
            "- `transport_packet/<variant>/shell_centroid_path.png`",
            "- `prototype_3d_summary.csv`",
            "- `prototype_3d_summary.json`",
            f"- failure-mode audit report: `{audit['report_path']}`",
            "",
            "## Next Step",
            "",
            _next_step(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "moving_transport_packet_supported":
        return "The clean cubic shell-window tail behaves primarily like a moving transport packet. The next goal is to shape boundary interference to slow, redirect, or repeatedly refocus it."
    if label == "drifting_modal_structure_supported":
        return "The clean cubic shell-window tail behaves more like a drifting modal structure than a radially moving packet. The next goal is to identify the drift symmetry and test whether boundary phase can lock it."
    if label == "mixed_transport_and_drift":
        return "The clean cubic shell-window tail has both packet-motion and modal-drift signatures. Treat it as a moving coherent structure and isolate radial transport from angular/phase drift next."
    return "The current diagnostics do not distinguish packet transport from modal drift strongly enough for a physics claim."


def _next_step(classification: dict[str, Any]) -> str:
    if classification["label"] == "moving_transport_packet_supported":
        return "Run a tiny phase-shaping control that tries to slow or refocus the same packet without broadening grid size or defect parameters."
    if classification["label"] == "drifting_modal_structure_supported":
        return "Run a tiny phase-locking control around cubic phase offset/sign to see whether the drift can be stabilized."
    if classification["label"] == "mixed_transport_and_drift":
        return "Add one targeted phase-shaping control that separately scores radial slowing and angular drift reduction."
    return "Inspect packet diagnostics manually before adding controls; do not broaden the sweep."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "transport_packet_classification",
        "packet_role",
        "grid_size",
        "dx",
        "dt",
        "drive_phase_mode",
        "boundary_phase_offset",
        "boundary_cubic_phase_sign",
        "work_per_source_area",
        "positive_work_before_cutoff",
        "near_shell_tail_retention",
        "outer_to_near_tail_energy_ratio",
        "global_peak_in_outer_window",
        "shell_window_radius",
        "shell_window_width",
        "source_radius_mean",
        "boundary_to_shell_distance",
        "first_shell_arrival_time",
        "shell_peak_time",
        "shell_exit_time",
        "shell_exit_detected",
        "shell_dwell_time",
        "time_of_flight_velocity",
        "radial_group_velocity",
        "radial_group_velocity_r2",
        "expected_shell_crossing_time",
        "exit_delay_ratio",
        "mean_shell_radial_speed",
        "mean_centroid_displacement_speed",
        "mean_angular_drift_rate",
        "cumulative_angular_drift",
        "shell_phase_velocity",
        "shell_phase_velocity_r2",
        "mean_abs_shell_phase_velocity",
        "mean_shell_phase_coherence",
        "mean_shell_radial_flux",
        "mean_inward_flux",
        "mean_outward_flux",
        "inward_flux_fraction",
        "outward_flux_fraction",
        "mean_frame_to_frame_similarity",
        "min_frame_to_frame_similarity",
        "lag1_shell_pattern_similarity",
        "peak_lag_shell_pattern_similarity",
        "peak_lag_time",
        "shell_energy_peak",
        "shell_energy_tail_mean",
        "path",
    ]


def _timeseries_fields() -> list[str]:
    return [
        "variant",
        "time",
        "shell_window_energy",
        "shell_fraction_of_total",
        "active_radial_centroid",
        "active_radial_peak_radius",
        "shell_centroid_x",
        "shell_centroid_y",
        "shell_centroid_z",
        "shell_centroid_radius",
        "shell_phase",
        "shell_phase_unwrapped",
        "shell_phase_velocity",
        "shell_phase_coherence",
        "shell_radial_flux",
        "shell_inward_flux",
        "shell_outward_flux",
        "frame_to_frame_similarity",
        "centroid_displacement_speed",
        "shell_centroid_radial_speed",
        "angular_step",
        "cumulative_angular_drift",
    ]


def _lag_fields() -> list[str]:
    return ["variant", "lag_index", "lag_time", "mean_shell_pattern_correlation", "min_shell_pattern_correlation"]
