"""Read-only failure-mode audit for tiny 3D prototype runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import (
    EPSILON,
    Lattice3D,
    Prototype3DConfig,
    _coordinate_payload,
    _radial_bins,
)


@dataclass(frozen=True)
class Prototype3DFailureAuditOptions:
    """Options for auditing a completed 3D prototype run."""

    output_dir: Path | None = None
    radial_bins: int = 24
    near_shell_width_dx: float = 4.0
    tail_fraction: float = 0.35
    meaningful_work_fraction: float = 1e-8


def run_3d_failure_audit(
    prototype_root: Path,
    base_config: SimulationConfig,
    *,
    options: Prototype3DFailureAuditOptions | None = None,
) -> dict[str, Any]:
    """Audit a completed tiny 3D prototype run without rerunning physics."""

    options = options or Prototype3DFailureAuditOptions()
    prototype_root = Path(prototype_root)
    output_dir = options.output_dir or prototype_root / "failure_mode_audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    variants = _load_variants(prototype_root)
    summary_rows: list[dict[str, Any]] = []
    geometry_rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []

    for row in variants:
        config = _config_from_summary(row, base_config)
        run_dir = _run_dir(row, prototype_root)
        geometry = _geometry_audit(config)
        window = _window_audit(run_dir, config, row, options)
        variant_summary = {**_basic_variant_fields(row), **geometry, **window["summary"]}
        variant_summary["variant_classification"] = classify_3d_failure_variant(variant_summary, options)
        summary_rows.append(variant_summary)
        geometry_rows.append({"variant": row["variant"], **geometry})
        timeseries_rows.extend({"variant": row["variant"], **item} for item in window["timeseries"])
        snapshot_rows.extend({"variant": row["variant"], **item} for item in window["snapshots"])
        _plot_window_timeseries(
            output_dir / f"{row['variant']}_shell_window_timeseries.png",
            row["variant"],
            window["timeseries"],
            float(row.get("drive_cutoff_time") or config.drive_cutoff_time),
        )

    classification = classify_3d_failure_audit(summary_rows, options)
    for row in summary_rows:
        row["audit_classification"] = classification["label"]

    summary_csv = output_dir / "prototype_3d_failure_audit_summary.csv"
    geometry_csv = output_dir / "prototype_3d_geometry_audit.csv"
    timeseries_csv = output_dir / "prototype_3d_shell_window_timeseries.csv"
    snapshots_csv = output_dir / "prototype_3d_radial_snapshots.csv"
    report_path = output_dir / "prototype_3d_failure_audit_report.md"

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(geometry_csv, geometry_rows, _geometry_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(snapshots_csv, snapshot_rows, _snapshot_fields())
    _plot_reference_snapshots(snapshot_rows, output_dir / "boundary_cubic_radial_snapshots.png")
    _write_report(report_path, prototype_root, summary_rows, classification, options)
    save_json(
        output_dir / "prototype_3d_failure_audit_summary.json",
        {
            "prototype_root": str(prototype_root),
            "classification": classification,
            "variants": summary_rows,
            "summary_csv": str(summary_csv),
            "geometry_csv": str(geometry_csv),
            "timeseries_csv": str(timeseries_csv),
            "snapshots_csv": str(snapshots_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "prototype_root": str(prototype_root),
        "classification": classification,
        "variants": summary_rows,
        "summary_csv": str(summary_csv),
        "geometry_csv": str(geometry_csv),
        "timeseries_csv": str(timeseries_csv),
        "snapshots_csv": str(snapshots_csv),
        "report_path": str(report_path),
        "path": str(output_dir),
    }


def classify_3d_failure_audit(
    rows: list[dict[str, Any]],
    options: Prototype3DFailureAuditOptions | None = None,
) -> dict[str, Any]:
    """Classify the reference failure mode from audit rows."""

    options = options or Prototype3DFailureAuditOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No 3D audit rows were available.", "checks": {}}
    reference = next((row for row in rows if row["variant"] == "boundary_cubic_31"), rows[0])
    checks = _failure_checks(reference, options)
    if checks["boundary_source_inside_sponge"] and checks["outer_tail_dominates"] and checks["global_peak_outer"]:
        return {
            "label": "boundary_layer_trapped",
            "reason": (
                "The reference boundary source sits inside the sponge layer and its post-cutoff radial energy is "
                "dominated by outer-window residue rather than a near-defect shell."
            ),
            "checks": checks,
        }
    if checks["near_shell_tiny_vs_work"] and not checks["meaningful_near_shell_arrival"]:
        return {
            "label": "no_defect_shell_arrival",
            "reason": "The boundary reference did not deliver meaningful retained energy into the near-defect shell window.",
            "checks": checks,
        }
    if checks["meaningful_near_shell_arrival"] and checks["near_shell_not_retained"]:
        return {
            "label": "near_defect_shell_present_but_not_retained",
            "reason": "Energy reached the near-defect shell window, but the post-cutoff tail did not retain it.",
            "checks": checks,
        }
    if checks["global_peak_outer"] and checks["near_tail_fraction_nontrivial"]:
        return {
            "label": "diagnostic_window_issue",
            "reason": "The global shell peak is outer-biased, but near-defect shell energy is nontrivial enough to audit separately.",
            "checks": checks,
        }
    return {
        "label": "inconclusive",
        "reason": "The failure-mode audit did not isolate one dominant 3D failure mechanism.",
        "checks": checks,
    }


def classify_3d_failure_variant(
    row: dict[str, Any],
    options: Prototype3DFailureAuditOptions | None = None,
) -> str:
    """Classify one 3D variant's shell-window behavior."""

    options = options or Prototype3DFailureAuditOptions()
    checks = _failure_checks(row, options)
    if checks["boundary_source_inside_sponge"] and checks["outer_tail_dominates"] and checks["global_peak_outer"]:
        return "boundary_layer_trapped"
    if checks["near_shell_tiny_vs_work"] and not checks["meaningful_near_shell_arrival"]:
        return "no_defect_shell_arrival"
    if checks["meaningful_near_shell_arrival"] and checks["near_shell_not_retained"]:
        return "near_defect_shell_present_but_not_retained"
    if checks["global_peak_outer"] and checks["near_tail_fraction_nontrivial"]:
        return "diagnostic_window_issue"
    return "inconclusive"


def _failure_checks(row: dict[str, Any], options: Prototype3DFailureAuditOptions) -> dict[str, bool]:
    return {
        "boundary_source_inside_sponge": (
            row.get("drive_location") == "boundary"
            and float(row.get("source_sponge_overlap_fraction") or 0.0) >= 0.95
        ),
        "outer_tail_dominates": float(row.get("outer_to_near_tail_energy_ratio") or 0.0) >= 10.0,
        "global_peak_outer": bool(row.get("global_peak_in_outer_window")),
        "near_shell_tiny_vs_work": (
            float(row.get("near_shell_peak_fraction_of_work") or 0.0) < options.meaningful_work_fraction
        ),
        "meaningful_near_shell_arrival": row.get("first_meaningful_near_shell_arrival_time") is not None,
        "near_shell_not_retained": float(row.get("near_shell_tail_retention") or 0.0) < 0.05,
        "near_tail_fraction_nontrivial": float(row.get("near_shell_tail_fraction_of_total") or 0.0) >= 0.05,
    }


def _load_variants(prototype_root: Path) -> list[dict[str, Any]]:
    summary_path = prototype_root / "prototype_3d_summary.json"
    if summary_path.exists():
        with summary_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [dict(row) for row in data.get("variants", [])]
    csv_path = prototype_root / "prototype_3d_summary.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"No prototype summary found under {prototype_root}")
    with csv_path.open("r", newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _config_from_summary(row: dict[str, Any], base: SimulationConfig) -> Prototype3DConfig:
    grid_size = int(float(row["grid_size"]))
    dx = float(row["dx"])
    domain_size = dx * float(max(grid_size - 1, 1))
    defect_radius = float(base.defect.radius_physical if base.defect.radius_physical is not None else base.defect.radius)
    sponge_width = float(row.get("sponge_width") or base.boundary_damping_width_physical or base.boundary_damping_width)
    sponge_strength = float(row.get("sponge_strength") or base.boundary_damping_strength)
    if "sponge_strength" not in row and str(row.get("variant", "")).endswith("stronger_sponge_31"):
        sponge_strength *= 2.0
    return Prototype3DConfig(
        name=str(row["variant"]),
        grid_size=grid_size,
        steps=int(float(row["steps"])),
        dt=float(row["dt"]),
        domain_size=domain_size,
        base_stiffness=base.base_stiffness,
        coupling_strength=base.coupling_strength,
        global_damping=base.global_damping,
        nonlinear_strength=base.nonlinear_strength,
        defect_radius=defect_radius,
        defect_stiffness_multiplier=base.defect.stiffness_multiplier,
        defect_damping_multiplier=base.defect.damping_multiplier,
        defect_coupling_multiplier=base.defect.coupling_multiplier,
        sponge_width=sponge_width,
        sponge_strength=sponge_strength,
        drive_frequency=float(row.get("drive_frequency") or base.driver.frequency),
        drive_amplitude=float(row.get("drive_amplitude") or base.driver.amplitude),
        drive_cutoff_time=float(row.get("drive_cutoff_time") or base.driver.drive_cutoff_time),
        drive_location=str(row.get("drive_location") or "boundary"),
        drive_phase_mode=str(row.get("drive_phase_mode") or "uniform"),
        shell_inner_radius=defect_radius + dx,
        shell_outer_radius=defect_radius + 3.0 * dx,
        boundary_source_inner_distance=float(row.get("boundary_source_inner_distance") or 0.0),
        boundary_source_width=float(row.get("boundary_source_width") or dx),
        exclude_source_from_sponge_damping=_bool(row.get("exclude_source_from_sponge_damping")),
    )


def _run_dir(row: dict[str, Any], prototype_root: Path) -> Path:
    raw = Path(str(row.get("path") or ""))
    if raw.exists():
        return raw
    return prototype_root / str(row["variant"])


def _geometry_audit(config: Prototype3DConfig) -> dict[str, Any]:
    lattice = Lattice3D(config)
    source_weights = lattice.source.weights
    source_mask = source_weights > EPSILON
    source_weight_sum = float(np.sum(source_weights))
    sponge_mask = lattice.sponge_extra > EPSILON
    high_sponge_mask = lattice.sponge_extra >= 0.5 * max(config.sponge_strength, EPSILON)
    weighted_sponge = float(np.sum(source_weights * lattice.sponge_extra) / (source_weight_sum + EPSILON))
    source_overlap = float(np.sum(source_weights[sponge_mask]) / (source_weight_sum + EPSILON))
    high_source_overlap = float(np.sum(source_weights[high_sponge_mask]) / (source_weight_sum + EPSILON))
    radius = lattice.coords["radius"]
    near_inner = config.defect_radius
    near_outer = config.defect_radius + 4.0 * config.dx
    outer_start = max(config.defect_radius, 0.5 * config.domain_size - config.sponge_width)
    outer_corner_start = 0.5 * config.domain_size
    return {
        "grid_size": config.grid_size,
        "dx": config.dx,
        "domain_size": config.domain_size,
        "defect_radius": config.defect_radius,
        "sponge_width": config.sponge_width,
        "sponge_strength": config.sponge_strength,
        "drive_location": config.drive_location,
        "drive_phase_mode": config.drive_phase_mode,
        "boundary_source_inner_distance": config.boundary_source_inner_distance,
        "boundary_source_width": config.boundary_source_width or config.dx,
        "exclude_source_from_sponge_damping": config.exclude_source_from_sponge_damping,
        "source_cell_count": int(np.count_nonzero(source_mask)),
        "source_weight_sum": source_weight_sum,
        "effective_source_volume": float(source_weight_sum * config.cell_volume),
        "effective_source_area": lattice.source.effective_area,
        "source_sponge_overlap_fraction": source_overlap,
        "source_high_sponge_overlap_fraction": high_source_overlap,
        "source_mean_sponge_extra": weighted_sponge,
        "source_max_sponge_extra": float(np.max(lattice.sponge_extra[source_mask])) if np.any(source_mask) else 0.0,
        "source_mean_sponge_fraction_of_max": weighted_sponge / max(config.sponge_strength, EPSILON),
        "defect_cell_count": int(np.count_nonzero(lattice.defect_mask)),
        "defect_volume": float(np.count_nonzero(lattice.defect_mask) * config.cell_volume),
        "near_shell_inner_radius": near_inner,
        "near_shell_outer_radius": near_outer,
        "near_shell_cell_count": int(np.count_nonzero((radius > near_inner) & (radius <= near_outer))),
        "near_shell_volume": float(np.count_nonzero((radius > near_inner) & (radius <= near_outer)) * config.cell_volume),
        "outer_sponge_radial_start": outer_start,
        "outer_corner_radial_start": outer_corner_start,
        "sponge_cell_count": int(np.count_nonzero(sponge_mask)),
        "sponge_volume": float(np.count_nonzero(sponge_mask) * config.cell_volume),
    }


def _window_audit(
    run_dir: Path,
    config: Prototype3DConfig,
    summary_row: dict[str, Any],
    options: Prototype3DFailureAuditOptions,
) -> dict[str, Any]:
    radial_rows = _read_numeric_csv(run_dir / "radial_profile_timeseries.csv")
    metrics_rows = _read_numeric_csv(run_dir / "metrics.csv")
    bins = _radial_bins(config, options.radial_bins)
    centers = 0.5 * (bins[:-1] + bins[1:])
    counts = _radial_bin_counts(config, bins)
    near_mask = (centers > config.defect_radius) & (centers <= config.defect_radius + options.near_shell_width_dx * config.dx)
    outer_mask = centers >= max(config.defect_radius, 0.5 * config.domain_size - config.sponge_width)
    outer_corner_mask = centers >= 0.5 * config.domain_size
    profiles = np.asarray(
        [[row.get(f"bin_{idx}", 0.0) for idx in range(options.radial_bins)] for row in radial_rows],
        dtype=float,
    )
    totals_by_bin = profiles * counts[np.newaxis, :]
    times = np.asarray([row["time"] for row in radial_rows], dtype=float)
    total_radial_energy = np.sum(totals_by_bin, axis=1)
    near_energy = np.sum(totals_by_bin[:, near_mask], axis=1)
    outer_energy = np.sum(totals_by_bin[:, outer_mask], axis=1)
    outer_corner_energy = np.sum(totals_by_bin[:, outer_corner_mask], axis=1)
    mean_peak_idx = np.argmax(np.where(centers > config.defect_radius, profiles, -np.inf), axis=1)
    global_peak_radius = centers[mean_peak_idx]
    near_peak_idx = np.argmax(np.where(near_mask, profiles, -np.inf), axis=1)
    near_peak_radius = centers[near_peak_idx]
    post_mask = times > config.drive_cutoff_time
    post_indices = np.flatnonzero(post_mask)
    tail_indices = _tail_indices(post_indices, options.tail_fraction)
    work = float(summary_row.get("positive_work_before_cutoff") or 0.0)
    near_peak = float(np.max(near_energy)) if near_energy.size else 0.0
    near_peak_time_index = int(np.argmax(near_energy)) if near_energy.size else 0
    arrival_threshold = max(near_peak * 0.10, work * options.meaningful_work_fraction)
    arrival_candidates = np.flatnonzero(near_energy >= arrival_threshold)
    meaningful_arrival = None
    if arrival_candidates.size and near_peak / (work + EPSILON) >= options.meaningful_work_fraction:
        meaningful_arrival = float(times[arrival_candidates[0]])
    tail_near = _mean_at(near_energy, tail_indices)
    tail_outer = _mean_at(outer_energy, tail_indices)
    tail_outer_corner = _mean_at(outer_corner_energy, tail_indices)
    tail_total = _mean_at(total_radial_energy, tail_indices)
    peak_global_radius = float(summary_row.get("best_shell_peak_radius") or 0.0)
    summary = {
        "near_shell_peak_energy": near_peak,
        "near_shell_peak_time": float(times[near_peak_time_index]) if near_energy.size else None,
        "near_shell_peak_radius_at_peak_time": float(near_peak_radius[near_peak_time_index]) if near_energy.size else None,
        "near_shell_peak_fraction_of_work": near_peak / (work + EPSILON),
        "near_shell_energy_at_cutoff": _nearest_value(times, near_energy, config.drive_cutoff_time),
        "near_shell_tail_mean_energy": tail_near,
        "near_shell_tail_fraction_of_total": tail_near / (tail_total + EPSILON),
        "near_shell_tail_retention": tail_near / (near_peak + EPSILON),
        "outer_shell_tail_mean_energy": tail_outer,
        "outer_corner_tail_mean_energy": tail_outer_corner,
        "outer_tail_fraction_of_total": tail_outer / (tail_total + EPSILON),
        "outer_corner_tail_fraction_of_total": tail_outer_corner / (tail_total + EPSILON),
        "outer_to_near_tail_energy_ratio": tail_outer / (tail_near + EPSILON),
        "outer_corner_to_near_tail_energy_ratio": tail_outer_corner / (tail_near + EPSILON),
        "first_meaningful_near_shell_arrival_time": meaningful_arrival,
        "global_shell_peak_radius": peak_global_radius,
        "global_peak_in_outer_window": peak_global_radius >= max(config.defect_radius, 0.5 * config.domain_size - config.sponge_width),
        "post_cutoff_global_peak_radius_median": _median_at(global_peak_radius, post_indices),
        "late_tail_global_peak_radius_median": _median_at(global_peak_radius, tail_indices),
        "post_cutoff_near_shell_peak_radius_median": _median_at(near_peak_radius, post_indices),
        "late_tail_near_shell_peak_radius_median": _median_at(near_peak_radius, tail_indices),
        "late_tail_near_shell_peak_radius_range": _range_at(near_peak_radius, tail_indices),
        "total_radial_tail_mean_energy": tail_total,
        "metrics_total_tail_mean_energy": _metrics_tail_mean(metrics_rows, tail_indices),
    }
    return {
        "summary": summary,
        "timeseries": _window_timeseries(
            times,
            near_energy,
            outer_energy,
            outer_corner_energy,
            total_radial_energy,
            global_peak_radius,
            near_peak_radius,
        ),
        "snapshots": _snapshot_rows(times, profiles, totals_by_bin, centers, config, options),
    }


def _radial_bin_counts(config: Prototype3DConfig, bins: np.ndarray) -> np.ndarray:
    radius = _coordinate_payload(config)["radius"]
    indices = np.clip(np.digitize(radius.ravel(), bins) - 1, 0, len(bins) - 2)
    return np.bincount(indices, minlength=len(bins) - 1).astype(float)


def _read_numeric_csv(path: Path) -> list[dict[str, float]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        rows = []
        for row in csv.DictReader(fh):
            rows.append({key: _float(value) for key, value in row.items()})
        return rows


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _tail_indices(post_indices: np.ndarray, tail_fraction: float) -> np.ndarray:
    if post_indices.size == 0:
        return post_indices
    start = int(post_indices.size * max(0.0, min(0.95, 1.0 - tail_fraction)))
    return post_indices[start:]


def _mean_at(values: np.ndarray, indices: np.ndarray) -> float:
    if indices.size == 0:
        return 0.0
    return float(np.mean(values[indices]))


def _median_at(values: np.ndarray, indices: np.ndarray) -> float | None:
    if indices.size == 0:
        return None
    return float(np.median(values[indices]))


def _range_at(values: np.ndarray, indices: np.ndarray) -> float | None:
    if indices.size == 0:
        return None
    selected = values[indices]
    return float(np.percentile(selected, 90) - np.percentile(selected, 10))


def _nearest_value(times: np.ndarray, values: np.ndarray, target: float) -> float | None:
    if times.size == 0:
        return None
    idx = int(np.argmin(np.abs(times - target)))
    return float(values[idx])


def _metrics_tail_mean(metrics_rows: list[dict[str, float]], tail_indices: np.ndarray) -> float:
    if not metrics_rows or tail_indices.size == 0:
        return 0.0
    values = np.asarray([row.get("total_energy", 0.0) for row in metrics_rows], dtype=float)
    safe = tail_indices[tail_indices < values.size]
    if safe.size == 0:
        return 0.0
    return float(np.mean(values[safe]))


def _window_timeseries(
    times: np.ndarray,
    near: np.ndarray,
    outer: np.ndarray,
    outer_corner: np.ndarray,
    total: np.ndarray,
    peak_radius: np.ndarray,
    near_peak_radius: np.ndarray,
) -> list[dict[str, Any]]:
    rows = []
    for idx, time in enumerate(times):
        rows.append(
            {
                "time": float(time),
                "near_shell_energy": float(near[idx]),
                "outer_shell_energy": float(outer[idx]),
                "outer_corner_energy": float(outer_corner[idx]),
                "total_radial_energy": float(total[idx]),
                "near_shell_fraction": float(near[idx] / (total[idx] + EPSILON)),
                "outer_shell_fraction": float(outer[idx] / (total[idx] + EPSILON)),
                "outer_corner_fraction": float(outer_corner[idx] / (total[idx] + EPSILON)),
                "global_peak_radius": float(peak_radius[idx]),
                "near_shell_peak_radius": float(near_peak_radius[idx]),
            }
        )
    return rows


def _snapshot_rows(
    times: np.ndarray,
    profiles: np.ndarray,
    totals_by_bin: np.ndarray,
    centers: np.ndarray,
    config: Prototype3DConfig,
    options: Prototype3DFailureAuditOptions,
) -> list[dict[str, Any]]:
    targets = {
        "pre_cutoff": max(0.0, config.drive_cutoff_time - 2.0),
        "cutoff": config.drive_cutoff_time,
        "early_tail": config.drive_cutoff_time + 2.0,
        "late_tail": times[-1] if times.size else config.physical_duration,
    }
    rows: list[dict[str, Any]] = []
    for label, target in targets.items():
        if times.size == 0:
            continue
        idx = int(np.argmin(np.abs(times - target)))
        for bin_idx, center in enumerate(centers):
            rows.append(
                {
                    "snapshot": label,
                    "target_time": target,
                    "actual_time": float(times[idx]),
                    "bin_index": bin_idx,
                    "radius": float(center),
                    "mean_energy": float(profiles[idx, bin_idx]),
                    "total_bin_energy": float(totals_by_bin[idx, bin_idx]),
                    "window": _window_name(float(center), config, options),
                }
            )
    return rows


def _window_name(radius: float, config: Prototype3DConfig, options: Prototype3DFailureAuditOptions) -> str:
    if radius <= config.defect_radius:
        return "defect_core"
    if radius <= config.defect_radius + options.near_shell_width_dx * config.dx:
        return "near_defect_shell"
    if radius >= 0.5 * config.domain_size:
        return "outer_corner"
    if radius >= max(config.defect_radius, 0.5 * config.domain_size - config.sponge_width):
        return "outer_sponge_radial"
    return "middle_domain"


def _basic_variant_fields(row: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "variant",
        "grid_size",
        "dx",
        "dt",
        "steps",
        "physical_duration",
        "drive_location",
        "drive_phase_mode",
        "drive_amplitude",
        "drive_frequency",
        "drive_cutoff_time",
        "boundary_source_inner_distance",
        "boundary_source_width",
        "exclude_source_from_sponge_damping",
        "positive_work_before_cutoff",
        "work_per_boundary_area",
        "work_per_source_area",
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
    ]
    return {field: row.get(field) for field in fields}


def _plot_window_timeseries(path: Path, variant: str, rows: list[dict[str, Any]], cutoff_time: float) -> None:
    if not rows:
        return
    times = [row["time"] for row in rows]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    ax.plot(times, [row["near_shell_energy"] for row in rows], label="near defect shell")
    ax.plot(times, [row["outer_shell_energy"] for row in rows], label="outer radial window")
    ax.plot(times, [row["outer_corner_energy"] for row in rows], label="outer corner window")
    ax.axvline(cutoff_time, color="#666666", linestyle="--", linewidth=1)
    ax.set_yscale("symlog", linthresh=1e-12)
    ax.set_xlabel("time")
    ax.set_ylabel("window energy")
    ax.set_title(f"3D shell-window audit: {variant}")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_reference_snapshots(rows: list[dict[str, Any]], path: Path) -> None:
    ref_rows = [row for row in rows if row["variant"] == "boundary_cubic_31"]
    if not ref_rows:
        return
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    for label in ("pre_cutoff", "cutoff", "early_tail", "late_tail"):
        subset = [row for row in ref_rows if row["snapshot"] == label]
        if not subset:
            continue
        ax.plot([row["radius"] for row in subset], [row["total_bin_energy"] for row in subset], label=label)
    ax.set_yscale("symlog", linthresh=1e-12)
    ax.set_xlabel("radius")
    ax.set_ylabel("total radial-bin energy")
    ax.set_title("Boundary cubic radial snapshots")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_report(
    path: Path,
    prototype_root: Path,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: Prototype3DFailureAuditOptions,
) -> None:
    reference = next((row for row in rows if row["variant"] == "boundary_cubic_31"), rows[0] if rows else {})
    lines = [
        f"# 3D Failure-Mode Audit: {prototype_root.name}",
        "",
        "## Purpose",
        "",
        (
            "Read-only audit of the completed 31^3 prototype. The goal is to separate true near-defect "
            "spherical shell organization from outer-boundary radial residue."
        ),
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Reference Findings",
        "",
        f"- Boundary source overlap with sponge: `{_format(reference.get('source_sponge_overlap_fraction'))}`",
        f"- Boundary source high-sponge overlap: `{_format(reference.get('source_high_sponge_overlap_fraction'))}`",
        f"- Global shell peak radius: `{_format(reference.get('global_shell_peak_radius'))}`",
        f"- Near-defect shell peak energy: `{_format(reference.get('near_shell_peak_energy'))}`",
        f"- Near-defect peak/work fraction: `{_format(reference.get('near_shell_peak_fraction_of_work'))}`",
        f"- Near-defect tail fraction of total radial energy: `{_format(reference.get('near_shell_tail_fraction_of_total'))}`",
        f"- Outer-to-near tail energy ratio: `{_format(reference.get('outer_to_near_tail_energy_ratio'))}`",
        f"- First meaningful near-shell arrival: `{_format(reference.get('first_meaningful_near_shell_arrival_time'))}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Drive | Source/Sponge | Global Peak R | Near Peak/Work | Near Tail Frac | Outer/Near Tail | Arrival | Variant Class |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('drive_location')}/{row.get('drive_phase_mode')} | "
            f"{_format(row.get('source_sponge_overlap_fraction'))} | "
            f"{_format(row.get('global_shell_peak_radius'))} | "
            f"{_format(row.get('near_shell_peak_fraction_of_work'))} | "
            f"{_format(row.get('near_shell_tail_fraction_of_total'))} | "
            f"{_format(row.get('outer_to_near_tail_energy_ratio'))} | "
            f"{_format(row.get('first_meaningful_near_shell_arrival_time'))} | "
            f"{row.get('variant_classification')} |"
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
            "- `prototype_3d_failure_audit_summary.csv`",
            "- `prototype_3d_geometry_audit.csv`",
            "- `prototype_3d_shell_window_timeseries.csv`",
            "- `prototype_3d_radial_snapshots.csv`",
            "- `boundary_cubic_radial_snapshots.png`",
            "",
            "## Next Step",
            "",
            (
                "Keep 3D tiny. Before increasing grid size, run a source/sponge separation control: place the "
                "boundary flux at the inner edge of the sponge or exclude the driven layer from sponge damping, "
                "then recheck near-defect shell-window arrival and retention."
            ),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "boundary_layer_trapped":
        return (
            "The first 3D failure is most consistent with source/sponge geometry and outer-boundary residue. "
            "The reported shell breathing peaks are not evidence of retained breathing around the spherical defect."
        )
    if label == "no_defect_shell_arrival":
        return (
            "The boundary source does not appear to move meaningful energy into the near-defect shell window. "
            "The next control should test transport geometry, not larger grids."
        )
    if label == "near_defect_shell_present_but_not_retained":
        return "A near-defect shell response appears transient but not retained; focus on damping/transport controls."
    if label == "diagnostic_window_issue":
        return "The global radial peak is outer-biased; near-defect shell metrics should drive future 3D classifications."
    return "The audit remains inconclusive. Keep the prototype small and add only targeted 3D controls."


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _summary_fields() -> list[str]:
    return [
        "variant",
        "audit_classification",
        "variant_classification",
        "grid_size",
        "dx",
        "dt",
        "drive_location",
        "drive_phase_mode",
        "boundary_source_inner_distance",
        "boundary_source_width",
        "exclude_source_from_sponge_damping",
        "source_sponge_overlap_fraction",
        "source_high_sponge_overlap_fraction",
        "source_mean_sponge_fraction_of_max",
        "positive_work_before_cutoff",
        "work_per_source_area",
        "best_shell_peak_radius",
        "global_shell_peak_radius",
        "global_peak_in_outer_window",
        "near_shell_peak_energy",
        "near_shell_peak_time",
        "near_shell_peak_radius_at_peak_time",
        "near_shell_peak_fraction_of_work",
        "near_shell_energy_at_cutoff",
        "near_shell_tail_mean_energy",
        "near_shell_tail_fraction_of_total",
        "near_shell_tail_retention",
        "outer_shell_tail_mean_energy",
        "outer_corner_tail_mean_energy",
        "outer_tail_fraction_of_total",
        "outer_corner_tail_fraction_of_total",
        "outer_to_near_tail_energy_ratio",
        "outer_corner_to_near_tail_energy_ratio",
        "first_meaningful_near_shell_arrival_time",
        "post_cutoff_global_peak_radius_median",
        "late_tail_global_peak_radius_median",
        "post_cutoff_near_shell_peak_radius_median",
        "late_tail_near_shell_peak_radius_median",
        "late_tail_near_shell_peak_radius_range",
        "post_cutoff_shell_retention",
        "shell_breathing_detected",
        "shell_breathing_period",
        "shell_breathing_cycles",
    ]


def _geometry_fields() -> list[str]:
    return [
        "variant",
        "grid_size",
        "dx",
        "domain_size",
        "defect_radius",
        "sponge_width",
        "sponge_strength",
        "drive_location",
        "drive_phase_mode",
        "boundary_source_inner_distance",
        "boundary_source_width",
        "exclude_source_from_sponge_damping",
        "source_cell_count",
        "source_weight_sum",
        "effective_source_volume",
        "effective_source_area",
        "source_sponge_overlap_fraction",
        "source_high_sponge_overlap_fraction",
        "source_mean_sponge_extra",
        "source_max_sponge_extra",
        "source_mean_sponge_fraction_of_max",
        "defect_cell_count",
        "defect_volume",
        "near_shell_inner_radius",
        "near_shell_outer_radius",
        "near_shell_cell_count",
        "near_shell_volume",
        "outer_sponge_radial_start",
        "outer_corner_radial_start",
        "sponge_cell_count",
        "sponge_volume",
    ]


def _timeseries_fields() -> list[str]:
    return [
        "variant",
        "time",
        "near_shell_energy",
        "outer_shell_energy",
        "outer_corner_energy",
        "total_radial_energy",
        "near_shell_fraction",
        "outer_shell_fraction",
        "outer_corner_fraction",
        "global_peak_radius",
        "near_shell_peak_radius",
    ]


def _snapshot_fields() -> list[str]:
    return [
        "variant",
        "snapshot",
        "target_time",
        "actual_time",
        "bin_index",
        "radius",
        "mean_energy",
        "total_bin_energy",
        "window",
    ]


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, np.generic):
        return _csv_value(value.item())
    return value


def _format(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    if isinstance(value, bool):
        return str(value).lower()
    return f"{float(value):.6g}"
