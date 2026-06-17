"""Controlled core-modal probes for source-normalized fixed-domain candidates."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .breathing_period_audit import _peak_summary
from .config import SimulationConfig, save_json, to_jsonable_config
from .fixed_domain_controls import _fixed_domain_config, _resample_to_config
from .lattice import Lattice2D
from .metrics import METRIC_FIELDS, add_posthoc_metrics, core_signal, sample_metrics
from .mode_diagnostics import energy_shape_metrics, shape_correlation
from .plots import plot_core_spectrum, plot_core_vs_outer, plot_energy_well_ratio, save_heatmap
from .resolution_diagnostics import (
    _angular_mode_vector_at_best,
    _radial_profile_correlation_on_shared_grid,
    _radial_profile_payload,
    _sponge_mask_and_extra_damping,
)
from .stability import estimate_stability
from .time_resolved_diagnostics import DiagnosticOptions, diagnose_existing_run


EPSILON = 1e-12


@dataclass(frozen=True)
class CoreModalProbeOptions:
    """Options for the default controlled core-modal probe plan."""

    output_root: str = "runs"
    frame_interval: int = 20
    window_steps: int = 30
    source_normalization: str = "constant_total_work"
    reference_grid_size: int = 63
    confirmation_grid_size: int = 81
    min_peak_separation: float = 1.5
    secondary_min_peak_separation: float = 2.0
    peak_percentile: float = 55.0
    min_core_retention: float = 0.15
    min_similarity_to_reference: float = 0.35
    min_radial_similarity_to_reference: float = 0.45
    min_m4_strength: float = 0.08


CORE_PROBE_EXTRA_METRIC_FIELDS = [
    "drive_location",
    "core_drive_mode",
    "boundary_drive_power",
    "core_drive_power",
    "positive_boundary_drive_power",
    "positive_core_drive_power",
    "cumulative_boundary_drive_work",
    "cumulative_core_drive_work",
    "cumulative_positive_boundary_drive_work",
    "cumulative_positive_core_drive_work",
    "cumulative_positive_drive_work",
    "cumulative_damping_loss",
    "cumulative_sponge_damping_loss",
    "sponge_region_energy",
    "energy_residual_estimate",
    "relative_energy_residual_estimate",
]


def run_core_modal_probe(
    base_config: SimulationConfig,
    *,
    options: CoreModalProbeOptions | None = None,
    reference_root: str | Path = "runs",
) -> dict[str, Any]:
    """Run the 63/81 boundary reference and direct core excitation probes."""

    options = options or CoreModalProbeOptions()
    probe_id = datetime.now().strftime("core_modal_probe_%Y%m%d_%H%M%S")
    probe_root = Path(options.output_root) / probe_id
    probe_root.mkdir(parents=True, exist_ok=False)

    rows: list[dict[str, Any]] = []
    configs_by_variant: dict[str, SimulationConfig] = {}

    boundary_63 = _boundary_reference_config(base_config, options.reference_grid_size, options.source_normalization)
    configs_by_variant["boundary_reference_63"] = boundary_63
    summary, diagnostics = _run_and_diagnose(
        "boundary_reference_63",
        boundary_63,
        probe_root,
        options,
        reference_root,
    )
    row = _summary_row("boundary_reference_63", boundary_63, summary, diagnostics, options)
    rows.append(row)
    target_work = float(row.get("injected_work_before_cutoff") or 0.0)

    boundary_81 = _boundary_reference_config(base_config, options.confirmation_grid_size, options.source_normalization)
    _calibrate_drive_amplitude(boundary_81, target_work, drive_kind="boundary")
    configs_by_variant["boundary_reference_81"] = boundary_81
    summary, diagnostics = _run_and_diagnose(
        "boundary_reference_81",
        boundary_81,
        probe_root,
        options,
        reference_root,
    )
    rows.append(_summary_row("boundary_reference_81", boundary_81, summary, diagnostics, options))

    core_variants = [
        ("core_impulse_63", options.reference_grid_size, "impulse"),
        ("core_burst_0p92_63", options.reference_grid_size, "burst"),
        ("core_impulse_81", options.confirmation_grid_size, "impulse"),
        ("core_burst_0p92_81", options.confirmation_grid_size, "burst"),
    ]
    impulse_reference_amplitude: float | None = None
    burst_reference_amplitude: float | None = None
    for variant_name, grid_size, mode in core_variants:
        config = _core_probe_config(base_config, grid_size, mode)
        if mode == "impulse" and impulse_reference_amplitude is not None:
            config.core_drive_amplitude = impulse_reference_amplitude
        if mode == "burst" and burst_reference_amplitude is not None:
            config.core_drive_amplitude = burst_reference_amplitude
        _calibrate_drive_amplitude(config, target_work, drive_kind="core")
        if variant_name == "core_impulse_63":
            impulse_reference_amplitude = config.core_drive_amplitude
        if variant_name == "core_burst_0p92_63":
            burst_reference_amplitude = config.core_drive_amplitude

        configs_by_variant[variant_name] = config
        summary, diagnostics = _run_and_diagnose(variant_name, config, probe_root, options, reference_root)
        rows.append(_summary_row(variant_name, config, summary, diagnostics, options))

    _attach_reference_similarities(rows, configs_by_variant)
    classification = classify_core_modal_probe(rows, options)
    best_core = _best_matching_core_probe(rows)
    for row in rows:
        row["classification_label"] = classification["label"]

    summary_path = probe_root / "core_modal_probe_summary.csv"
    report_path = probe_root / "core_modal_probe_report.md"
    plots_dir = probe_root / "core_modal_probe_comparison_plots"
    plots_dir.mkdir(exist_ok=True)
    _write_csv(summary_path, rows, _summary_fields())
    _write_comparison_plots(rows, plots_dir)
    _write_report(report_path, probe_id, base_config, rows, classification, best_core, plots_dir, options)
    save_json(
        probe_root / "core_modal_probe_summary.json",
        {
            "probe_id": probe_id,
            "classification": classification,
            "best_matching_core_probe": best_core,
            "variants": rows,
            "summary_csv": str(summary_path),
            "report_path": str(report_path),
            "comparison_plots_path": str(plots_dir),
        },
    )
    return {
        "probe_id": probe_id,
        "classification": classification,
        "best_matching_core_probe": best_core,
        "variants": rows,
        "summary_csv": str(summary_path),
        "report_path": str(report_path),
        "comparison_plots_path": str(plots_dir),
        "path": str(probe_root),
    }


def classify_core_modal_probe(
    rows: list[dict[str, Any]],
    options: CoreModalProbeOptions | None = None,
) -> dict[str, Any]:
    """Classify whether direct core excitation supports the reference breathing state."""

    options = options or CoreModalProbeOptions()
    boundary_rows = [row for row in rows if row.get("drive_location") == "boundary"]
    core_rows = [row for row in rows if row.get("drive_location") != "boundary"]
    if not boundary_rows or not core_rows:
        return {"label": "inconclusive", "reason": "Boundary references and core probes are both required.", "checks": {}}

    reference = next((row for row in boundary_rows if row["variant"] == "boundary_reference_63"), boundary_rows[0])
    reference_period = float(reference.get("breathing_period_after_cutoff") or reference.get("raw_diagnostic_frame_period") or 0.0)
    boundary_support = any(bool(row.get("breathing_detected_after_cutoff")) for row in boundary_rows)
    core_successes = [_core_success(row, reference_period, options) for row in core_rows]
    checks = {
        "boundary_reference_breathing": boundary_support,
        "core_probe_success_count": sum(1 for passed in core_successes if passed),
        "core_probe_count": len(core_rows),
        "best_core_probe": (_best_matching_core_probe(rows) or {}).get("variant"),
    }

    if any(core_successes):
        return {
            "label": "intrinsic_defect_breathing_mode_supported",
            "reason": (
                "At least one direct core excitation retained post-cutoff breathing with reference-like period, "
                "radial similarity, and non-axisymmetric m=4 content."
            ),
            "checks": checks,
        }

    active_only_flags = [
        float(row.get("active_core_energy_peak") or 0.0) > 2.0 * float(row.get("post_cutoff_core_energy") or 0.0)
        and float(row.get("post_cutoff_retention") or 0.0) < 0.08
        for row in core_rows
    ]
    checks["active_only_core_probe_count"] = sum(1 for passed in active_only_flags if passed)
    if active_only_flags and all(active_only_flags):
        return {
            "label": "core_forcing_only_artifact",
            "reason": "All direct core probes are elevated mainly during active forcing and do not persist as post-cutoff tails.",
            "checks": checks,
        }

    if boundary_support:
        return {
            "label": "boundary_transport_required",
            "reason": "The boundary reference retains breathing, but direct core excitation did not reproduce the post-cutoff state.",
            "checks": checks,
        }

    return {
        "label": "inconclusive",
        "reason": "The boundary reference and direct core probe evidence are both mixed.",
        "checks": checks,
    }


def _run_and_diagnose(
    variant_name: str,
    config: SimulationConfig,
    probe_root: Path,
    options: CoreModalProbeOptions,
    reference_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = _run_probe_variant(config, output_root=probe_root, run_id=variant_name)
    diagnostics = diagnose_existing_run(
        summary["path"],
        options=DiagnosticOptions(
            frame_interval=options.frame_interval,
            window_steps=options.window_steps,
            save_frame_pngs=False,
        ),
        reference_root=reference_root,
    )
    return summary, diagnostics


def _run_probe_variant(
    config: SimulationConfig,
    *,
    output_root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    lattice = Lattice2D(config)
    sponge_mask, sponge_extra = _sponge_mask_and_extra_damping(config, lattice)
    samples: list[dict[str, Any]] = []
    core_displacement: list[float] = []
    cutoff = _evidence_cutoff(config)
    area = float(config.cell_area)
    dt = float(config.dt)
    initial_total = float(np.sum(lattice.energy_density()))

    cumulative_boundary_work = 0.0
    cumulative_core_work = 0.0
    cumulative_positive_boundary_work = 0.0
    cumulative_positive_core_work = 0.0
    cumulative_positive_boundary_before_cutoff = 0.0
    cumulative_positive_core_before_cutoff = 0.0
    cumulative_damping_loss = 0.0
    cumulative_sponge_damping_loss = 0.0
    peak_boundary_power = 0.0
    peak_core_power = 0.0
    best_ratio = -np.inf
    best_energy_density: np.ndarray | None = None
    final_energy_density: np.ndarray | None = None

    for step in range(config.steps):
        time = step * dt
        boundary_force = lattice.boundary_force(time)
        core_force = lattice.core_force(time)
        velocity_before = lattice.v.copy()
        lattice.step(time, dt)
        velocity_mid = 0.5 * (velocity_before + lattice.v)

        boundary_power = float(np.sum(boundary_force * velocity_mid) * area)
        core_power = float(np.sum(core_force * velocity_mid) * area)
        positive_boundary_power = max(0.0, boundary_power)
        positive_core_power = max(0.0, core_power)
        damping_power = float(np.sum(lattice.damping * velocity_mid**2) * area)
        sponge_power = float(np.sum(sponge_extra * velocity_mid**2) * area)

        cumulative_boundary_work += boundary_power * dt
        cumulative_core_work += core_power * dt
        cumulative_positive_boundary_work += positive_boundary_power * dt
        cumulative_positive_core_work += positive_core_power * dt
        cumulative_damping_loss += damping_power * dt
        cumulative_sponge_damping_loss += sponge_power * dt
        peak_boundary_power = max(peak_boundary_power, positive_boundary_power)
        peak_core_power = max(peak_core_power, positive_core_power)

        if _within_boundary_drive_window(config, time):
            cumulative_positive_boundary_before_cutoff += positive_boundary_power * dt
        if _within_core_drive_window(config, time):
            cumulative_positive_core_before_cutoff += positive_core_power * dt

        if step % max(1, config.sample_every) != 0 and step != config.steps - 1:
            continue

        energy = lattice.energy_density()
        final_energy_density = energy.copy()
        row = sample_metrics(step, time, lattice, energy)
        residual = (
            float(np.sum(energy))
            - initial_total
            - cumulative_boundary_work
            - cumulative_core_work
            + cumulative_damping_loss
        )
        row.update(
            {
                "drive_location": config.drive_location,
                "core_drive_mode": config.core_drive_mode if config.drive_location != "boundary" else "",
                "boundary_drive_power": boundary_power,
                "core_drive_power": core_power,
                "positive_boundary_drive_power": positive_boundary_power,
                "positive_core_drive_power": positive_core_power,
                "cumulative_boundary_drive_work": cumulative_boundary_work,
                "cumulative_core_drive_work": cumulative_core_work,
                "cumulative_positive_boundary_drive_work": cumulative_positive_boundary_work,
                "cumulative_positive_core_drive_work": cumulative_positive_core_work,
                "cumulative_positive_drive_work": cumulative_positive_boundary_work + cumulative_positive_core_work,
                "cumulative_damping_loss": cumulative_damping_loss,
                "cumulative_sponge_damping_loss": cumulative_sponge_damping_loss,
                "sponge_region_energy": float(np.sum(energy[sponge_mask])),
                "energy_residual_estimate": residual,
                "relative_energy_residual_estimate": residual / (abs(float(np.sum(energy))) + abs(initial_total) + EPSILON),
            }
        )
        samples.append(row)
        core_displacement.append(core_signal(lattice))

        if time > cutoff and row["energy_well_ratio"] > best_ratio:
            best_ratio = row["energy_well_ratio"]
            best_energy_density = energy.copy()

    if final_energy_density is None or not samples:
        raise RuntimeError("Simulation produced no metric samples. Check steps and sample_every.")
    if best_energy_density is None:
        best = max(samples, key=lambda row: row["energy_well_ratio"])
        best_ratio = float(best["energy_well_ratio"])
        best_energy_density = final_energy_density.copy()

    add_posthoc_metrics(samples, core_displacement, config)
    summary = _post_cutoff_summary(run_id, config, samples, best_energy_density, cutoff)
    summary["path"] = str(run_dir)
    summary["stability"] = estimate_stability(config)
    summary["total_boundary_drive_work"] = cumulative_positive_boundary_work
    summary["total_core_drive_work"] = cumulative_positive_core_work
    summary["total_boundary_drive_work_before_cutoff"] = cumulative_positive_boundary_before_cutoff
    summary["total_core_drive_work_before_cutoff"] = cumulative_positive_core_before_cutoff
    summary["injected_work_before_cutoff"] = (
        cumulative_positive_boundary_before_cutoff + cumulative_positive_core_before_cutoff
    )
    summary["peak_boundary_drive_power"] = peak_boundary_power
    summary["peak_core_drive_power"] = peak_core_power
    summary["post_cutoff_evidence_start_time"] = cutoff
    summary["core_drive_effective_area"] = float(lattice.core_driver.effective_driven_area)
    summary["core_drive_fractional_coverage_sum"] = float(lattice.core_driver.fractional_coverage_sum)
    if lattice.core_driver.effective_driven_area > EPSILON:
        summary["injected_work_per_core_area"] = cumulative_positive_core_before_cutoff / lattice.core_driver.effective_driven_area
    else:
        summary["injected_work_per_core_area"] = 0.0

    best_energy_path = run_dir / "best_energy_density.npy"
    np.save(best_energy_path, best_energy_density)
    summary["best_energy_density_path"] = str(best_energy_path)

    config_payload = to_jsonable_config(config)
    config_payload["run_id"] = run_id
    save_json(run_dir / "config.json", config_payload)
    _write_metrics_csv(run_dir / "metrics.csv", samples)
    save_json(run_dir / "summary.json", summary)
    save_heatmap(final_energy_density, config, run_dir / "final_heatmap.png", "Final energy density")
    save_heatmap(best_energy_density, config, run_dir / "best_frame.png", "Best post-cutoff core-modal event")
    plot_energy_well_ratio(samples, run_dir / "energy_well_ratio_plot.png")
    plot_core_vs_outer(samples, run_dir / "core_vs_outer_energy_plot.png")
    plot_core_spectrum(core_displacement, config.dt * max(1, config.sample_every), run_dir / "core_spectrum_plot.png")
    _plot_injected_work(samples, run_dir / "injected_work_plot.png")
    _plot_post_cutoff_decay(samples, cutoff, run_dir / "post_cutoff_decay_plot.png")
    return summary


def _post_cutoff_summary(
    run_id: str,
    config: SimulationConfig,
    samples: list[dict[str, Any]],
    best_energy_density: np.ndarray,
    cutoff: float,
) -> dict[str, Any]:
    post = [row for row in samples if float(row["time"]) > cutoff]
    evidence = post if post else samples
    best = max(evidence, key=lambda row: row["energy_well_ratio"])
    arrays = {key: np.asarray([row[key] for row in samples], dtype=float) for key in ("time", "core_energy", "total_energy")}
    post_core = np.asarray([row["core_energy"] for row in post], dtype=float)
    pre_core = np.asarray([row["core_energy"] for row in samples if float(row["time"]) <= cutoff], dtype=float)
    reference_peak = max(
        float(np.max(pre_core)) if pre_core.size else 0.0,
        float(np.max(post_core)) if post_core.size else 0.0,
        EPSILON,
    )
    tail_start = max(0, int(post_core.size * 0.35))
    retention = float(np.mean(post_core[tail_start:]) / reference_peak) if post_core.size else 0.0
    shape_metrics = energy_shape_metrics(best_energy_density, config)
    labels = ["boundary_reference_modal_probe"] if config.drive_location == "boundary" else ["core_excited_modal_probe"]
    if retention > 0.22:
        labels.append("post_cutoff_core_retention")
    if config.drive_location != "boundary":
        labels.append(f"core_drive_{config.core_drive_mode}")
    return {
        "run_id": run_id,
        "best_energy_well_ratio": float(best["energy_well_ratio"]),
        "time_of_best_event": float(best["time"]),
        "post_cutoff_best_event_time": float(best["time"]),
        "baseline_energy_well_ratio": _baseline_ratio(samples, cutoff),
        "retention_score": float(np.clip(retention, 0.0, 1.0)),
        "localization_score": float(max(row["localization_index"] for row in evidence)),
        "max_center_to_surround_amplitude_ratio": float(max(row["center_to_surround_amplitude_ratio"] for row in evidence)),
        "max_core_energy_fraction": float(np.max(arrays["core_energy"] / (arrays["total_energy"] + EPSILON))),
        "spectral_peak_frequency": float(samples[-1].get("spectral_peak_frequency", 0.0)),
        "spectral_purity": float(samples[-1].get("spectral_purity", 0.0)),
        "q_like_decay": float(samples[-1].get("q_like_decay", 0.0)),
        "ring_score": 0.0,
        "best_frame_spatial_entropy": shape_metrics["spatial_entropy"],
        "best_frame_spatial_entropy_normalized": shape_metrics["spatial_entropy_normalized"],
        "best_frame_participation_fraction": shape_metrics["participation_fraction"],
        "best_frame_radial_entropy_normalized": shape_metrics["radial_entropy_normalized"],
        "best_frame_radial_peak_radius": shape_metrics["radial_peak_radius"],
        "best_frame_radial_concentration": shape_metrics["radial_concentration"],
        "rotation_score": 0.0,
        "breathing_score": 0.0,
        "threshold_score": 0.0,
        "anomaly_score": 0.0,
        "detected_event_labels": labels,
        "plain_language_interpretation": (
            "Post-cutoff evidence is measured after direct core forcing turns off."
            if config.drive_location != "boundary"
            else "Boundary reference for the source-normalized fixed-domain modal probe."
        ),
    }


def _summary_row(
    variant: str,
    config: SimulationConfig,
    summary: dict[str, Any],
    diagnostics: dict[str, Any],
    options: CoreModalProbeOptions,
) -> dict[str, Any]:
    metrics_rows = _read_numeric_csv(Path(summary["path"]) / "metrics.csv")
    cutoff = _evidence_cutoff(config)
    post = [row for row in metrics_rows if float(row.get("time", 0.0)) > cutoff]
    active = [row for row in metrics_rows if float(row.get("time", 0.0)) <= cutoff]
    best_post = max(post, key=lambda row: row.get("energy_well_ratio", 0.0)) if post else max(
        metrics_rows, key=lambda row: row.get("energy_well_ratio", 0.0)
    )
    full_metric = _peak_summary(
        metrics_rows,
        cutoff,
        options.peak_percentile,
        min_separation=options.min_peak_separation,
    )
    full_metric_secondary = _peak_summary(
        metrics_rows,
        cutoff,
        options.peak_percentile,
        min_separation=options.secondary_min_peak_separation,
    )
    raw_frame = _diagnostic_frame_peak_summary(summary, cutoff, options)
    envelope_strength = _post_cutoff_envelope_strength(post)
    retention_value = float(summary.get("retention_score") or 0.0)
    peak_breathing_detected = _breathing_detected_from_peak_summary(full_metric, envelope_strength)
    breathing_detected = peak_breathing_detected and (
        config.drive_location == "boundary" or retention_value >= 0.05
    )
    angular = diagnostics.get("angular_detection", {})
    radial = diagnostics.get("radial_drift_summary", {})
    m4 = _m4_summary(summary, cutoff)
    injected_work = float(summary.get("injected_work_before_cutoff") or 0.0)
    core_area = float(summary.get("core_drive_effective_area") or 0.0)
    post_core_peak = float(best_post.get("core_energy", 0.0))
    active_core_peak = float(max((row.get("core_energy", 0.0) for row in active), default=0.0))
    post_outer_peak = float(best_post.get("outer_lattice_energy", 0.0))
    post_total = float(best_post.get("total_energy", 0.0))
    labels = list(summary.get("detected_event_labels", []))
    if config.drive_location != "boundary" and "core_excited_modal_probe" not in labels:
        labels.insert(0, "core_excited_modal_probe")
    labels.extend(_diagnostic_labels(diagnostics))
    return {
        "variant": variant,
        "run_id": summary.get("run_id"),
        "path": summary.get("path"),
        "classification_label": None,
        "grid_size": config.grid_size,
        "dx": config.dx,
        "dy": config.dy,
        "dt": config.dt,
        "steps": config.steps,
        "physical_duration": config.steps * config.dt,
        "drive_location": config.drive_location,
        "source_normalization": config.driver.source_normalization,
        "boundary_drive_frequency": config.driver.frequency,
        "boundary_drive_amplitude": config.driver.amplitude,
        "boundary_drive_cutoff_time": config.driver.drive_cutoff_time,
        "core_drive_mode": "" if config.drive_location == "boundary" else config.core_drive_mode,
        "core_drive_radius_physical": config.effective_core_drive_radius if config.drive_location != "boundary" else 0.0,
        "core_drive_frequency": config.effective_core_drive_frequency if config.drive_location != "boundary" else 0.0,
        "core_drive_amplitude": config.core_drive_amplitude if config.drive_location != "boundary" else 0.0,
        "core_drive_cutoff_time": config.effective_core_drive_cutoff_time if config.drive_location != "boundary" else "",
        "core_drive_effective_area": core_area,
        "core_drive_fractional_coverage_sum": summary.get("core_drive_fractional_coverage_sum"),
        "total_core_drive_work": summary.get("total_core_drive_work"),
        "total_boundary_drive_work": summary.get("total_boundary_drive_work"),
        "injected_work_before_cutoff": injected_work,
        "injected_work_per_core_area": injected_work / (core_area + EPSILON) if core_area > EPSILON else 0.0,
        "injected_work_per_boundary_length": _boundary_work_per_length(config, injected_work),
        "peak_boundary_drive_power": summary.get("peak_boundary_drive_power"),
        "peak_core_drive_power": summary.get("peak_core_drive_power"),
        "post_cutoff_core_energy": post_core_peak,
        "post_cutoff_outer_energy": post_outer_peak,
        "post_cutoff_core_fraction": post_core_peak / (post_total + EPSILON),
        "active_core_energy_peak": active_core_peak,
        "post_cutoff_retention": retention_value,
        "retention_score": retention_value,
        "core_energy_normalized_by_injected_work": post_core_peak / (injected_work + EPSILON),
        "decay_rate_after_cutoff": _post_cutoff_decay_rate(metrics_rows, cutoff, "core_energy"),
        "q_like_decay_measure": samples_last(metrics_rows, "q_like_decay"),
        "best_energy_well_ratio": summary.get("best_energy_well_ratio"),
        "best_event_time": summary.get("time_of_best_event"),
        "breathing_detected_after_cutoff": breathing_detected,
        "breathing_period_after_cutoff": full_metric.get("period"),
        "breathing_period_after_cutoff_min_sep_2": full_metric_secondary.get("period"),
        "raw_diagnostic_frame_period": raw_frame.get("period"),
        "breathing_strength_after_cutoff": envelope_strength,
        "breathing_cycles_after_cutoff": full_metric.get("peak_count", 0),
        "breathing_interval_cv_after_cutoff": full_metric.get("interval_cv"),
        "m4_strength_after_cutoff": m4.get("m4_strength"),
        "angular_phase_trend_r2_after_cutoff": m4.get("m4_phase_trend_r2"),
        "strongest_angular_mode": angular.get("strongest_angular_mode"),
        "strongest_angular_mode_strength": angular.get("strongest_angular_mode_strength"),
        "angular_phase_trend_r2": angular.get("angular_phase_trend_r2"),
        "radial_peak_after_cutoff_physical": radial.get("best_event_radial_peak_radius"),
        "radial_profile_similarity_to_boundary_reference": None,
        "angular_similarity_to_boundary_reference": None,
        "best_frame_similarity_to_boundary_reference": None,
        "detected_labels": ", ".join(dict.fromkeys(labels)) or "none",
        "mode_shape_diagnostics_report": diagnostics.get("report_path"),
    }


def _attach_reference_similarities(rows: list[dict[str, Any]], configs_by_variant: dict[str, SimulationConfig]) -> None:
    reference = next((row for row in rows if row["variant"] == "boundary_reference_63"), None)
    if reference is None:
        return
    reference_config = configs_by_variant[reference["variant"]]
    reference_energy = np.load(Path(reference["path"]) / "best_energy_density.npy")
    reference_radial = _radial_profile_payload(
        reference["variant"],
        reference_config,
        reference_energy,
        reference_energy,
    )["profiles"]["best_event"]
    reference_angular = _angular_mode_vector_at_best(reference)
    for row in rows:
        config = configs_by_variant[row["variant"]]
        energy = np.load(Path(row["path"]) / "best_energy_density.npy")
        row_radial = _radial_profile_payload(row["variant"], config, energy, energy)["profiles"]["best_event"]
        row_angular = _angular_mode_vector_at_best(row)
        if row["variant"] == reference["variant"]:
            row["best_frame_similarity_to_boundary_reference"] = 1.0
            row["radial_profile_similarity_to_boundary_reference"] = 1.0
            row["angular_similarity_to_boundary_reference"] = 1.0
            continue
        resampled = _resample_to_config(energy, config, reference_config)
        row["best_frame_similarity_to_boundary_reference"] = shape_correlation(reference_energy, resampled)
        row["radial_profile_similarity_to_boundary_reference"] = _radial_profile_correlation_on_shared_grid(
            reference_radial,
            row_radial,
        )
        row["angular_similarity_to_boundary_reference"] = _cosine_similarity(reference_angular, row_angular)


def _boundary_reference_config(
    base_config: SimulationConfig,
    grid_size: int,
    source_normalization: str,
) -> SimulationConfig:
    config = _fixed_domain_config(base_config, grid_size, source_normalization=source_normalization)
    config.drive_location = "boundary"
    config.core_drive_amplitude = 0.0
    config.core_drive_mode = "burst"
    config.core_drive_cutoff_time = None
    config.core_drive_frequency = None
    return config


def _core_probe_config(base_config: SimulationConfig, grid_size: int, mode: str) -> SimulationConfig:
    config = _fixed_domain_config(base_config, grid_size, source_normalization="constant_boundary_flux")
    config.drive_location = "core_region"
    config.driver.amplitude = 0.0
    config.core_drive_mode = mode
    config.core_drive_frequency = base_config.driver.frequency
    config.core_drive_amplitude = base_config.driver.amplitude
    config.core_drive_phase = 0.0
    config.core_drive_radius_physical = (
        base_config.core_drive_radius_physical
        if base_config.core_drive_radius_physical is not None
        else config.effective_core_radius_value
    )
    if mode == "impulse":
        config.core_drive_cutoff_time = config.dt
        config.driver.drive_cutoff_time = config.core_drive_cutoff_time
    else:
        config.core_drive_cutoff_time = base_config.driver.drive_cutoff_time
        config.driver.drive_cutoff_time = config.core_drive_cutoff_time
    config.normalize_core_drive_work = True
    config.core_drive_work_reference = "boundary_reference"
    return config


def _calibrate_drive_amplitude(config: SimulationConfig, target_work: float, *, drive_kind: str) -> None:
    if target_work <= EPSILON:
        return
    measured = _audit_injected_work(config, drive_kind)
    if measured <= EPSILON:
        return
    scale = float(np.sqrt(target_work / measured))
    if drive_kind == "boundary":
        config.driver.amplitude *= scale
        if config.driver.source_normalization == "constant_boundary_flux":
            config.driver.source_normalization = "constant_total_work"
    else:
        config.core_drive_amplitude *= scale
        config.normalize_core_drive_work = True
        config.target_core_drive_work = target_work


def _audit_injected_work(config: SimulationConfig, drive_kind: str) -> float:
    lattice = Lattice2D(config)
    area = float(config.cell_area)
    total = 0.0
    for step in range(config.steps):
        time = step * config.dt
        force = lattice.boundary_force(time) if drive_kind == "boundary" else lattice.core_force(time)
        velocity_before = lattice.v.copy()
        lattice.step(time, config.dt)
        velocity_mid = 0.5 * (velocity_before + lattice.v)
        power = float(np.sum(force * velocity_mid) * area)
        if drive_kind == "boundary" and _within_boundary_drive_window(config, time):
            total += max(0.0, power) * config.dt
        if drive_kind == "core" and _within_core_drive_window(config, time):
            total += max(0.0, power) * config.dt
    return total


def _evidence_cutoff(config: SimulationConfig) -> float:
    if config.drive_location == "boundary":
        return float(config.driver.drive_cutoff_time or 0.0)
    return float(config.effective_core_drive_cutoff_time or 0.0)


def _within_boundary_drive_window(config: SimulationConfig, time: float) -> bool:
    cutoff = config.driver.drive_cutoff_time
    return config.drive_location == "boundary" and (cutoff is None or time <= float(cutoff))


def _within_core_drive_window(config: SimulationConfig, time: float) -> bool:
    cutoff = config.effective_core_drive_cutoff_time
    return config.drive_location != "boundary" and (cutoff is None or time <= float(cutoff))


def _boundary_work_per_length(config: SimulationConfig, injected_work: float) -> float:
    if config.drive_location != "boundary":
        return 0.0
    length = float(getattr(Lattice2D(config).driver, "physical_boundary_length", 0.0))
    return injected_work / (length + EPSILON)


def _baseline_ratio(samples: list[dict[str, Any]], cutoff: float) -> float:
    baseline = [row["energy_well_ratio"] for row in samples if row["time"] <= min(cutoff * 0.4, samples[-1]["time"] * 0.3)]
    return float(np.median(baseline)) if baseline else 0.0


def _breathing_detected_from_peak_summary(summary: dict[str, Any], envelope_strength: float) -> bool:
    period = summary.get("period")
    interval_cv = summary.get("interval_cv")
    return (
        period is not None
        and int(summary.get("peak_count") or 0) >= 3
        and float(interval_cv if interval_cv is not None else 99.0) <= 0.75
        and envelope_strength >= 0.08
    )


def _post_cutoff_envelope_strength(rows: list[dict[str, float]]) -> float:
    values = np.asarray([row.get("core_energy", 0.0) for row in rows], dtype=float)
    if values.size < 3 or float(np.percentile(values, 90)) <= EPSILON:
        return 0.0
    return float((np.percentile(values, 90) - np.percentile(values, 10)) / (np.percentile(values, 90) + EPSILON))


def _diagnostic_frame_peak_summary(
    summary: dict[str, Any],
    cutoff: float,
    options: CoreModalProbeOptions,
) -> dict[str, Any]:
    frame_path = Path(summary["path"]) / "mode_shape_diagnostics" / "frame_mode_diagnostics.csv"
    if not frame_path.exists():
        return {}
    return _peak_summary(_read_numeric_csv(frame_path), cutoff, options.peak_percentile)


def _m4_summary(summary: dict[str, Any], cutoff: float) -> dict[str, float]:
    path = Path(summary["path"]) / "mode_shape_diagnostics" / "angular_mode_timeseries.csv"
    if not path.exists():
        return {"m4_strength": 0.0, "m4_phase_trend_r2": 0.0}
    rows = [row for row in _read_numeric_csv(path) if float(row.get("time", 0.0)) > cutoff]
    if len(rows) < 3:
        return {"m4_strength": 0.0, "m4_phase_trend_r2": 0.0}
    strengths = np.asarray([row.get("m4_strength", 0.0) for row in rows], dtype=float)
    phases = np.unwrap(np.asarray([row.get("m4_phase", 0.0) for row in rows], dtype=float))
    return {
        "m4_strength": float(np.median(strengths)),
        "m4_phase_trend_r2": _phase_trend_r2([row.get("time", 0.0) for row in rows], phases),
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


def _post_cutoff_decay_rate(rows: list[dict[str, float]], cutoff: float, key: str) -> float:
    post = [row for row in rows if row.get("time", 0.0) > cutoff and row.get(key, 0.0) > EPSILON]
    if len(post) < 8:
        return 0.0
    times = np.asarray([row["time"] - cutoff for row in post], dtype=float)
    values = np.asarray([row[key] for row in post], dtype=float)
    if np.max(values) <= EPSILON:
        return 0.0
    slope, _intercept = np.polyfit(times, np.log(np.maximum(values, EPSILON)), 1)
    return float(slope)


def _core_success(row: dict[str, Any], reference_period: float, options: CoreModalProbeOptions) -> bool:
    if not bool(row.get("breathing_detected_after_cutoff")):
        return False
    if float(row.get("post_cutoff_retention") or 0.0) < options.min_core_retention:
        return False
    period = float(row.get("breathing_period_after_cutoff") or 0.0)
    if reference_period > EPSILON and abs(period - reference_period) > max(0.8, 0.35 * reference_period):
        return False
    radial_similarity = float(row.get("radial_profile_similarity_to_boundary_reference") or 0.0)
    frame_similarity = float(row.get("best_frame_similarity_to_boundary_reference") or 0.0)
    if radial_similarity < options.min_radial_similarity_to_reference and frame_similarity < options.min_similarity_to_reference:
        return False
    return float(row.get("m4_strength_after_cutoff") or 0.0) >= options.min_m4_strength


def _best_matching_core_probe(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    core_rows = [row for row in rows if row.get("drive_location") != "boundary"]
    if not core_rows:
        return None
    best = max(core_rows, key=_core_match_score)
    return {
        "variant": best["variant"],
        "score": _core_match_score(best),
        "retention": best.get("post_cutoff_retention"),
        "period": best.get("breathing_period_after_cutoff"),
        "radial_similarity": best.get("radial_profile_similarity_to_boundary_reference"),
        "frame_similarity": best.get("best_frame_similarity_to_boundary_reference"),
        "m4_strength": best.get("m4_strength_after_cutoff"),
    }


def _core_match_score(row: dict[str, Any]) -> float:
    return float(
        0.35 * float(row.get("post_cutoff_retention") or 0.0)
        + 0.25 * max(float(row.get("radial_profile_similarity_to_boundary_reference") or 0.0), 0.0)
        + 0.20 * max(float(row.get("best_frame_similarity_to_boundary_reference") or 0.0), 0.0)
        + 0.20 * float(row.get("m4_strength_after_cutoff") or 0.0)
    )


def _cosine_similarity(first: np.ndarray | None, second: np.ndarray | None) -> float | None:
    if first is None or second is None:
        return None
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator <= EPSILON:
        return None
    return float(np.clip(np.dot(first, second) / denominator, -1.0, 1.0))


def samples_last(rows: list[dict[str, float]], key: str) -> float:
    if not rows:
        return 0.0
    return float(rows[-1].get(key, 0.0))


def _diagnostic_labels(diagnostics: dict[str, Any]) -> list[str]:
    labels = []
    breathing = diagnostics.get("breathing_detection", {})
    transition = diagnostics.get("mode_transition_detection", {})
    if breathing.get("label"):
        labels.append(breathing["label"])
    if transition.get("label"):
        labels.append(transition["label"])
    labels.extend(diagnostics.get("angular_detection", {}).get("labels", []))
    labels.extend(diagnostics.get("reference_comparison", {}).get("labels", []))
    return labels


def _plot_injected_work(samples: list[dict[str, Any]], path: Path) -> None:
    times = [row["time"] for row in samples]
    boundary = [row.get("cumulative_positive_boundary_drive_work", 0.0) for row in samples]
    core = [row.get("cumulative_positive_core_drive_work", 0.0) for row in samples]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    ax.plot(times, boundary, label="boundary injected work", color="#3366aa", linewidth=1.3)
    ax.plot(times, core, label="core injected work", color="#aa3377", linewidth=1.3)
    ax.plot(times, np.asarray(boundary) + np.asarray(core), label="total injected work", color="#222222", linewidth=1.0)
    ax.set_title("Injected work accounting")
    ax.set_xlabel("time")
    ax.set_ylabel("positive work")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_post_cutoff_decay(samples: list[dict[str, Any]], cutoff: float, path: Path) -> None:
    times = [row["time"] for row in samples]
    core = [row["core_energy"] for row in samples]
    outer = [row["outer_lattice_energy"] for row in samples]
    total = [row["total_energy"] for row in samples]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    ax.plot(times, core, label="core energy", color="#117733", linewidth=1.4)
    ax.plot(times, outer, label="outer energy", color="#3366aa", linewidth=1.1)
    ax.plot(times, total, label="total energy", color="#222222", linewidth=1.0, alpha=0.8)
    ax.axvline(cutoff, color="#666666", linestyle="--", linewidth=1.0, label="evidence cutoff")
    ax.set_title("Post-cutoff decay context")
    ax.set_xlabel("time")
    ax.set_ylabel("energy")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_comparison_plots(rows: list[dict[str, Any]], plots_dir: Path) -> None:
    _bar_plot(rows, "post_cutoff_retention", plots_dir / "post_cutoff_retention_by_variant.png", "Post-cutoff retention")
    _bar_plot(
        rows,
        "core_energy_normalized_by_injected_work",
        plots_dir / "normalized_core_energy_by_variant.png",
        "Post-cutoff core energy / injected work",
    )
    _bar_plot(rows, "breathing_period_after_cutoff", plots_dir / "breathing_period_by_variant.png", "Breathing period")
    _bar_plot(rows, "radial_peak_after_cutoff_physical", plots_dir / "radial_peak_by_variant.png", "Radial peak")
    _bar_plot(rows, "m4_strength_after_cutoff", plots_dir / "m4_strength_by_variant.png", "m=4 strength")
    labels = [row["variant"] for row in rows]
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(10, 4), dpi=140)
    ax.plot(x, [float(row.get("radial_profile_similarity_to_boundary_reference") or 0.0) for row in rows], marker="o", label="radial")
    ax.plot(x, [float(row.get("best_frame_similarity_to_boundary_reference") or 0.0) for row in rows], marker="o", label="frame")
    ax.plot(x, [float(row.get("angular_similarity_to_boundary_reference") or 0.0) for row in rows], marker="o", label="angular")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylim(-1.05, 1.05)
    ax.set_title("Similarity to boundary_reference_63")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots_dir / "similarity_to_boundary_reference.png")
    plt.close(fig)


def _bar_plot(rows: list[dict[str, Any]], key: str, path: Path, title: str) -> None:
    labels = [row["variant"] for row in rows]
    values = [float(row.get(key) or 0.0) for row in rows]
    fig, ax = plt.subplots(figsize=(10, 4), dpi=140)
    ax.bar(np.arange(len(rows)), values, color="#3366aa")
    ax.set_xticks(np.arange(len(rows)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_report(
    path: Path,
    probe_id: str,
    base_config: SimulationConfig,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    best_core: dict[str, Any] | None,
    plots_dir: Path,
    options: CoreModalProbeOptions,
) -> None:
    answers = _report_answers(rows, best_core)
    lines = [
        f"# Core-Modal Probe Report: {probe_id}",
        "",
        "## Purpose",
        "",
        (
            "Controlled core-excited modal probe for the source-normalized fixed-domain 0.92 candidate. "
            "The main evidence window is post-cutoff only; active direct forcing is reported as drive work, not as anomaly evidence."
        ),
        "",
        "## Base Case",
        "",
        f"- Source config grid: `{base_config.grid_size}`",
        f"- Reference drive frequency: `{base_config.driver.frequency}`",
        f"- Boundary cutoff time: `{base_config.driver.drive_cutoff_time}`",
        f"- Source normalization for boundary references: `{options.source_normalization}`",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best matching core-probe run: `{(best_core or {}).get('variant', 'n/a')}`",
        "",
        "## Direct Answers",
        "",
    ]
    for answer in answers:
        lines.append(f"- {answer}")

    lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| Variant | Grid | Drive | Work Before Cutoff | Retention | Period min_sep=1.5 | Raw frame period | Breathing | Radial Peak | m4 | Radial Sim | Frame Sim |",
            "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        drive = row["drive_location"] if row["drive_location"] == "boundary" else f"{row['drive_location']}:{row['core_drive_mode']}"
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('grid_size')} | "
            f"{drive} | "
            f"{_format(row.get('injected_work_before_cutoff'))} | "
            f"{_format(row.get('post_cutoff_retention'))} | "
            f"{_format(row.get('breathing_period_after_cutoff'))} | "
            f"{_format(row.get('raw_diagnostic_frame_period'))} | "
            f"{row.get('breathing_detected_after_cutoff')} | "
            f"{_format(row.get('radial_peak_after_cutoff_physical'))} | "
            f"{_format(row.get('m4_strength_after_cutoff'))} | "
            f"{_format(row.get('radial_profile_similarity_to_boundary_reference'))} | "
            f"{_format(row.get('best_frame_similarity_to_boundary_reference'))} |"
        )

    lines.extend(
        [
            "",
            "## Work Accounting",
            "",
            "| Variant | Boundary Work | Core Work | Work / Core Area | Work / Boundary Length | Peak Boundary Power | Peak Core Power |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('total_boundary_drive_work'))} | "
            f"{_format(row.get('total_core_drive_work'))} | "
            f"{_format(row.get('injected_work_per_core_area'))} | "
            f"{_format(row.get('injected_work_per_boundary_length'))} | "
            f"{_format(row.get('peak_boundary_drive_power'))} | "
            f"{_format(row.get('peak_core_drive_power'))} |"
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
            "- `core_modal_probe_summary.csv`",
            f"- Comparison plots: `{plots_dir}`",
        ]
    )
    for row in rows:
        lines.append(f"- `{row['variant']}` mode diagnostics: `{row.get('mode_shape_diagnostics_report')}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _report_answers(rows: list[dict[str, Any]], best_core: dict[str, Any] | None) -> list[str]:
    core_rows = [row for row in rows if row.get("drive_location") != "boundary"]
    boundary = next((row for row in rows if row.get("variant") == "boundary_reference_63"), rows[0] if rows else {})
    best_variant = (best_core or {}).get("variant", "n/a")
    direct_breathing = [row["variant"] for row in core_rows if row.get("breathing_detected_after_cutoff")]
    impulse_rows = [row for row in core_rows if row.get("core_drive_mode") == "impulse"]
    return [
        (
            "Direct core excitation produced post-cutoff breathing in "
            f"`{', '.join(direct_breathing) or 'no core variants'}` under the min-separated metric detector."
        ),
        (
            "Core impulse natural-ringing periods were "
            f"`{', '.join(_format(row.get('breathing_period_after_cutoff')) for row in impulse_rows) or 'n/a'}`."
        ),
        (
            f"The primary boundary-reference period is `{_format(boundary.get('breathing_period_after_cutoff'))}`; "
            f"best core match `{best_variant}` has period `{_format((best_core or {}).get('period'))}`."
        ),
        (
            f"Best core match radial similarity is `{_format((best_core or {}).get('radial_similarity'))}` "
            f"and frame similarity is `{_format((best_core or {}).get('frame_similarity'))}`."
        ),
        (
            "m=4 content under core excitation is "
            f"`{', '.join(f'{row['variant']}={_format(row.get('m4_strength_after_cutoff'))}' for row in core_rows)}`."
        ),
        (
            "All direct core runs report injected work separately and normalize against the boundary_reference_63 pre-cutoff work target."
        ),
        (
            "Evidence rows use post-cutoff best events, so active core forcing does not count as the retained tail."
        ),
        (
            "High-frequency probes were not run in this default controlled pass."
        ),
    ]


def _classification_interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "intrinsic_defect_breathing_mode_supported":
        return (
            "The result supports a defect-supported localized breathing mode under controlled direct core excitation. "
            "This does not establish broader physics claims; it says the post-cutoff retained breathing is not only a boundary-transport artifact."
        )
    if label == "boundary_transport_required":
        return (
            "The current controlled core excitation did not reproduce the source-normalized fixed-domain reference tail, "
            "so the 0.92 state appears to require boundary-driven transport under these settings."
        )
    if label == "core_forcing_only_artifact":
        return "The direct core signal is mostly active forcing response and does not survive cutoff strongly enough to count."
    if label == "high_frequency_numerical_artifact":
        return "High-frequency core forcing would need smaller-dt confirmation before interpretation."
    if label == "nonlinear_core_threshold_candidate":
        return "A repeatable threshold-like direct core response would need amplitude and smaller-dt controls before stronger wording."
    return "The evidence is mixed. Inspect per-run reports before changing the roadmap toward broader sweeps."


def _write_metrics_csv(path: Path, samples: list[dict[str, Any]]) -> None:
    fields = METRIC_FIELDS + [field for field in CORE_PROBE_EXTRA_METRIC_FIELDS if field not in METRIC_FIELDS]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in samples:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _read_numeric_csv(path: Path) -> list[dict[str, float]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        rows = []
        for row in csv.DictReader(fh):
            converted: dict[str, float] = {}
            for key, value in row.items():
                try:
                    converted[key] = float(value)
                except (TypeError, ValueError):
                    pass
            rows.append(converted)
        return rows


def _summary_fields() -> list[str]:
    return [
        "variant",
        "run_id",
        "path",
        "classification_label",
        "grid_size",
        "dx",
        "dy",
        "dt",
        "steps",
        "physical_duration",
        "drive_location",
        "source_normalization",
        "boundary_drive_frequency",
        "boundary_drive_amplitude",
        "boundary_drive_cutoff_time",
        "core_drive_mode",
        "core_drive_radius_physical",
        "core_drive_frequency",
        "core_drive_amplitude",
        "core_drive_cutoff_time",
        "core_drive_effective_area",
        "core_drive_fractional_coverage_sum",
        "total_core_drive_work",
        "total_boundary_drive_work",
        "injected_work_before_cutoff",
        "injected_work_per_core_area",
        "injected_work_per_boundary_length",
        "peak_boundary_drive_power",
        "peak_core_drive_power",
        "post_cutoff_core_energy",
        "post_cutoff_outer_energy",
        "post_cutoff_core_fraction",
        "active_core_energy_peak",
        "post_cutoff_retention",
        "retention_score",
        "core_energy_normalized_by_injected_work",
        "decay_rate_after_cutoff",
        "q_like_decay_measure",
        "best_energy_well_ratio",
        "best_event_time",
        "breathing_detected_after_cutoff",
        "breathing_period_after_cutoff",
        "breathing_period_after_cutoff_min_sep_2",
        "raw_diagnostic_frame_period",
        "breathing_strength_after_cutoff",
        "breathing_cycles_after_cutoff",
        "breathing_interval_cv_after_cutoff",
        "m4_strength_after_cutoff",
        "angular_phase_trend_r2_after_cutoff",
        "strongest_angular_mode",
        "strongest_angular_mode_strength",
        "angular_phase_trend_r2",
        "radial_peak_after_cutoff_physical",
        "radial_profile_similarity_to_boundary_reference",
        "angular_similarity_to_boundary_reference",
        "best_frame_similarity_to_boundary_reference",
        "detected_labels",
        "mode_shape_diagnostics_report",
    ]


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, np.generic):
        return _csv_value(value.item())
    return value


def _format(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    return f"{float(value):.6g}"
