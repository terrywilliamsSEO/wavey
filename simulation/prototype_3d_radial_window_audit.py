"""Radial-window audit for neutral-vs-defect 3D shell tails."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import (
    EPSILON,
    Prototype3DConfig,
    Prototype3DOptions,
    _base_3d_config,
    _calibrate_amplitude,
    _coordinate_payload,
    _radial_bins,
    _run_variant,
    _summary_fields as _prototype_summary_fields,
    _write_csv as _write_prototype_csv,
)
from .prototype_3d_audit import Prototype3DFailureAuditOptions, _radial_bin_counts, run_3d_failure_audit
from .prototype_3d_cubic_confirmation import _stability_summary
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_source_geometry import ALL_FACES
from .prototype_3d_source_sponge import _effective_source_area, _format, _merge_rows, _ratio, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


@dataclass(frozen=True)
class RadialWindowAudit3DOptions:
    """Options for the tiny 41^3 radial-window neutral-lattice audit."""

    output_root: str = "runs"
    grid_size: int = 41
    reference_source_grid_size: int = 31
    sample_every: int = 2
    radial_bins: int = 24
    window_radii: tuple[float, ...] = (2.5, 3.5, 5.0, 6.5, 8.0, 10.0, 12.0)
    window_width: float | None = None
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    target_work_per_source_area: float | None = None
    min_retention: float = 0.45
    max_outer_ratio: float = 2.0
    max_radius_range: float = 4.5
    strong_lift_threshold: float = 1.5
    near_unity_min: float = 0.67
    near_unity_max: float = 1.5


def run_3d_radial_window_audit(
    base_config: SimulationConfig,
    *,
    options: RadialWindowAudit3DOptions | None = None,
) -> dict[str, Any]:
    """Run current-defect and neutral-lattice sign-flip cases, then scan shell windows."""

    options = options or RadialWindowAudit3DOptions()
    control_id = datetime.now().strftime("radial_window_audit_3d_%Y%m%d_%H%M%S")
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
    rows: list[dict[str, Any]] = []
    configs_by_variant: dict[str, Prototype3DConfig] = {}

    for config in variants:
        config.drive_amplitude = reference_drive_amplitude
        target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
        _calibrate_amplitude(config, target_work)
        summary = _run_variant(config, root, _prototype_options(config, options))
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
                "label": "radial_window_audit_3d",
                "reason": "Tiny radial-window audit comparing current-defect and neutral-lattice sign-flip cases.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "radial_window_audit_3d_report.md"),
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
    window_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    window_data: dict[tuple[str, float], dict[str, Any]] = {}
    for row in control_rows:
        config = configs_by_variant[row["variant"]]
        scanned = _scan_windows(row, config, options)
        window_rows.extend(scanned["rows"])
        profile_rows.extend(scanned["profiles"])
        window_data.update({(item["variant"], float(item["window_radius"])): item for item in scanned["rows"]})

    comparison_rows = _comparison_rows(control_rows, configs_by_variant, window_data, options)
    classification = classify_radial_window_audit(comparison_rows, options)
    for row in comparison_rows:
        row["radial_window_audit_classification"] = classification["label"]

    variant_windows_csv = root / "radial_window_variant_metrics.csv"
    comparison_csv = root / "radial_window_comparison.csv"
    profile_csv = root / "radial_window_profile_comparison.csv"
    summary_csv = root / "radial_window_audit_3d_summary.csv"
    report_path = root / "radial_window_audit_3d_report.md"
    _write_csv(variant_windows_csv, window_rows, _variant_window_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_csv(profile_csv, profile_rows, _profile_fields())
    _write_csv(summary_csv, comparison_rows, _comparison_fields())
    _write_report(report_path, control_id, comparison_rows, classification, options, audit)
    save_json(
        root / "radial_window_audit_3d_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": control_rows,
            "window_comparisons": comparison_rows,
            "summary_csv": str(summary_csv),
            "comparison_csv": str(comparison_csv),
            "variant_windows_csv": str(variant_windows_csv),
            "profile_csv": str(profile_csv),
            "report_path": str(report_path),
            "audit_report_path": audit["report_path"],
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": control_rows,
        "window_comparisons": comparison_rows,
        "summary_csv": str(summary_csv),
        "comparison_csv": str(comparison_csv),
        "variant_windows_csv": str(variant_windows_csv),
        "profile_csv": str(profile_csv),
        "report_path": str(report_path),
        "audit_report_path": audit["report_path"],
        "path": str(root),
    }


def classify_radial_window_audit(
    comparison_rows: list[dict[str, Any]],
    options: RadialWindowAudit3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether radial-window behavior shows defect lift."""

    options = options or RadialWindowAudit3DOptions()
    if not comparison_rows:
        return {"label": "inconclusive", "reason": "No radial-window comparison rows were available.", "checks": {}}
    reference_radius = _closest_radius(comparison_rows, 5.0)
    reference_row = next((row for row in comparison_rows if float(row["window_radius"]) == reference_radius), comparison_rows[0])
    strong_lift_rows = [
        row
        for row in comparison_rows
        if bool(row.get("defect_window_clean"))
        and float(row.get("defect_lift_retention") or 0.0) >= options.strong_lift_threshold
        and float(row.get("defect_lift_peak_work") or 0.0) >= options.strong_lift_threshold
    ]
    neutral_reproduces_reference = (
        bool(reference_row.get("neutral_window_clean"))
        and options.near_unity_min <= float(reference_row.get("defect_lift_retention") or 0.0) <= options.near_unity_max
        and options.near_unity_min <= float(reference_row.get("defect_lift_peak_work") or 0.0) <= options.near_unity_max
        and abs(float(reference_row.get("arrival_time_shift") or 0.0)) <= 1.5
        and abs(float(reference_row.get("radius_median_shift") or 0.0)) <= 1.5
    )
    checks = {
        "reference_window_radius": reference_radius,
        "reference_window": reference_row,
        "strong_lift_windows": [row["window_radius"] for row in strong_lift_rows],
        "neutral_reproduces_reference_window": neutral_reproduces_reference,
    }
    if strong_lift_rows:
        return {
            "label": "defect_lift_detected",
            "reason": "At least one stable radial window showed defect retention and peak/work lift above threshold.",
            "best_window_radius": _best_window(comparison_rows),
            "checks": checks,
        }
    if neutral_reproduces_reference:
        return {
            "label": "neutral_lattice_reproduces_shell_tail",
            "reason": "The neutral lattice reproduced the radius-5 shell-window tail with defect-lift values near 1.0.",
            "best_window_radius": _best_window(comparison_rows),
            "checks": checks,
        }
    return {
        "label": "cubic_boundary_shell_tail_not_defect_dependent_yet",
        "reason": "No stable radial window showed strong defect lift; the neutral/current comparison remains mixed or near unity.",
        "best_window_radius": _best_window(comparison_rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: RadialWindowAudit3DOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    return [
        _boundary_config("current_defect_reference", base, options, source_width),
        _boundary_config(
            "neutral_lattice_reference",
            base,
            options,
            source_width,
            stiffness_multiplier=1.0,
            damping_multiplier=1.0,
            coupling_multiplier=1.0,
        ),
    ]


def _boundary_config(
    name: str,
    base: SimulationConfig,
    options: RadialWindowAudit3DOptions,
    source_width: float,
    *,
    stiffness_multiplier: float | None = None,
    damping_multiplier: float | None = None,
    coupling_multiplier: float | None = None,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, Prototype3DOptions(grid_size=options.grid_size), "boundary", "cubic")
    config.sponge_strength *= options.sponge_strength_multiplier
    config.boundary_source_inner_distance = config.sponge_width
    config.boundary_source_width = source_width
    config.boundary_faces = ALL_FACES
    config.boundary_cubic_phase_sign = -1.0
    if stiffness_multiplier is not None:
        config.defect_stiffness_multiplier = stiffness_multiplier
    if damping_multiplier is not None:
        config.defect_damping_multiplier = damping_multiplier
    if coupling_multiplier is not None:
        config.defect_coupling_multiplier = coupling_multiplier
    return config


def _prototype_options(config: Prototype3DConfig, options: RadialWindowAudit3DOptions) -> Prototype3DOptions:
    return Prototype3DOptions(
        output_root=options.output_root,
        grid_size=config.grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        include_dt_control=False,
        include_sponge_control=False,
    )


def _threshold_like_options(options: RadialWindowAudit3DOptions) -> Any:
    from .prototype_3d_threshold_control import ThresholdControl3DOptions

    return ThresholdControl3DOptions(
        output_root=options.output_root,
        grid_size=options.grid_size,
        reference_source_grid_size=options.reference_source_grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        near_shell_width_dx=options.near_shell_width_dx,
        sponge_strength_multiplier=options.sponge_strength_multiplier,
    )


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    reference_config: Prototype3DConfig,
    options: RadialWindowAudit3DOptions,
    target_work_per_area: float,
) -> None:
    summary["radial_window_role"] = "neutral_lattice" if config.name.startswith("neutral") else "current_defect"
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    original_sponge_strength = reference_config.sponge_strength / max(options.sponge_strength_multiplier, EPSILON)
    summary["sponge_strength_multiplier_vs_original"] = config.sponge_strength / max(original_sponge_strength, EPSILON)
    summary["sponge_width_multiplier"] = config.sponge_width / max(reference_config.sponge_width, EPSILON)
    summary["source_width_physical_reference"] = reference_config.boundary_source_width
    summary["target_reference_work_per_source_area"] = target_work_per_area
    summary["calibration_source_grid_size"] = options.reference_source_grid_size
    summary.update(_stability_summary(config))


def _scan_windows(
    summary_row: dict[str, Any],
    config: Prototype3DConfig,
    options: RadialWindowAudit3DOptions,
) -> dict[str, list[dict[str, Any]]]:
    run_dir = Path(str(summary_row["path"]))
    radial_rows = _read_numeric_csv(run_dir / "radial_profile_timeseries.csv")
    metrics_rows = _read_numeric_csv(run_dir / "metrics.csv")
    bins = _radial_bins(config, options.radial_bins)
    centers = 0.5 * (bins[:-1] + bins[1:])
    counts = _radial_bin_counts(config, bins)
    profiles = np.asarray(
        [[item.get(f"bin_{idx}", 0.0) for idx in range(options.radial_bins)] for item in radial_rows],
        dtype=float,
    )
    totals_by_bin = profiles * counts[np.newaxis, :]
    times = np.asarray([item["time"] for item in radial_rows], dtype=float)
    total_energy = np.sum(totals_by_bin, axis=1)
    post_indices = np.flatnonzero(times > config.drive_cutoff_time)
    tail_indices = _tail_indices(post_indices, 0.35)
    work = float(summary_row.get("positive_work_before_cutoff") or 0.0)
    window_width = _window_width(config, options)
    rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    for radius in options.window_radii:
        window_mask = (centers > radius) & (centers <= radius + window_width)
        outer_start = 0.5 * config.domain_size - config.sponge_width
        outer_mask = centers >= outer_start
        shell_energy = np.sum(totals_by_bin[:, window_mask], axis=1)
        outer_energy = np.sum(totals_by_bin[:, outer_mask], axis=1)
        peak_idx = np.argmax(np.where(window_mask, profiles, -np.inf), axis=1)
        peak_radius = centers[peak_idx]
        peak_energy = float(np.max(shell_energy)) if shell_energy.size else 0.0
        peak_time_index = int(np.argmax(shell_energy)) if shell_energy.size else 0
        arrival_threshold = max(peak_energy * 0.10, work * 1e-8)
        arrival_candidates = np.flatnonzero(shell_energy >= arrival_threshold)
        arrival = None
        if arrival_candidates.size and peak_energy / (work + EPSILON) >= 1e-8:
            arrival = float(times[arrival_candidates[0]])
        tail_shell = _mean_at(shell_energy, tail_indices)
        tail_outer = _mean_at(outer_energy, tail_indices)
        tail_total = _mean_at(total_energy, tail_indices)
        tail_profile = _mean_profile(totals_by_bin, tail_indices)
        profile_norm = _normalize(tail_profile)
        row = {
            "variant": summary_row["variant"],
            "radial_window_role": summary_row.get("radial_window_role"),
            "window_radius": radius,
            "window_outer_radius": radius + window_width,
            "window_width": window_width,
            "window_bin_count": int(np.count_nonzero(window_mask)),
            "positive_work_before_cutoff": work,
            "work_per_source_area": summary_row.get("work_per_source_area"),
            "shell_peak_fraction_of_work": peak_energy / (work + EPSILON),
            "shell_peak_time": float(times[peak_time_index]) if shell_energy.size else None,
            "shell_peak_radius_at_peak_time": float(peak_radius[peak_time_index]) if shell_energy.size else None,
            "shell_tail_fraction_of_total": tail_shell / (tail_total + EPSILON),
            "shell_tail_retention": tail_shell / (peak_energy + EPSILON),
            "outer_tail_mean_energy": tail_outer,
            "outer_to_shell_tail_energy_ratio": tail_outer / (tail_shell + EPSILON),
            "first_meaningful_shell_arrival_time": arrival,
            "late_tail_shell_peak_radius_median": _median_at(peak_radius, tail_indices),
            "late_tail_shell_peak_radius_range": _range_at(peak_radius, tail_indices),
            "variant_global_peak_in_outer_window": bool(summary_row.get("global_peak_in_outer_window")),
            "window_clean": (
                tail_shell / (peak_energy + EPSILON) >= options.min_retention
                and tail_outer / (tail_shell + EPSILON) <= options.max_outer_ratio
                and _range_at(peak_radius, tail_indices) <= options.max_radius_range
                and arrival is not None
                and not bool(summary_row.get("global_peak_in_outer_window"))
            ),
            "total_tail_mean_energy": tail_total,
            "metrics_total_tail_mean_energy": _metrics_tail_mean(metrics_rows, tail_indices),
            "tail_profile": tail_profile,
            "tail_profile_normalized": profile_norm,
        }
        for idx, center in enumerate(centers):
            profile_rows.append(
                {
                    "variant": summary_row["variant"],
                    "window_radius": radius,
                    "bin_index": idx,
                    "bin_center": float(center),
                    "in_window": bool(window_mask[idx]),
                    "tail_profile_energy": float(tail_profile[idx]),
                    "tail_profile_normalized": float(profile_norm[idx]),
                }
            )
        row["_tail_profile"] = tail_profile
        row["_tail_profile_normalized"] = profile_norm
        rows.append(row)
    return {"rows": rows, "profiles": profile_rows}


def _comparison_rows(
    control_rows: list[dict[str, Any]],
    configs_by_variant: dict[str, Prototype3DConfig],
    window_data: dict[tuple[str, float], dict[str, Any]],
    options: RadialWindowAudit3DOptions,
) -> list[dict[str, Any]]:
    defect_name = "current_defect_reference"
    neutral_name = "neutral_lattice_reference"
    defect_config = configs_by_variant[defect_name]
    neutral_config = configs_by_variant[neutral_name]
    defect_best = np.load(Path(str(_row_by_variant(control_rows, defect_name)["path"])) / "best_shell_energy_density.npy")
    neutral_best = np.load(Path(str(_row_by_variant(control_rows, neutral_name)["path"])) / "best_shell_energy_density.npy")
    coords = _coordinate_payload(defect_config)
    radius_grid = coords["radius"]
    window_width = _window_width(defect_config, options)
    rows = []
    for radius in options.window_radii:
        defect = window_data[(defect_name, float(radius))]
        neutral = window_data[(neutral_name, float(radius))]
        window_mask_3d = (radius_grid > radius) & (radius_grid <= radius + window_width)
        defect_profile = _profile_for(defect_name, radius, window_data)
        neutral_profile = _profile_for(neutral_name, radius, window_data)
        rows.append(
            {
                "window_radius": radius,
                "window_outer_radius": radius + window_width,
                "defect_retention": defect["shell_tail_retention"],
                "neutral_retention": neutral["shell_tail_retention"],
                "defect_lift_retention": _safe_ratio(defect["shell_tail_retention"], neutral["shell_tail_retention"]),
                "defect_peak_work": defect["shell_peak_fraction_of_work"],
                "neutral_peak_work": neutral["shell_peak_fraction_of_work"],
                "defect_lift_peak_work": _safe_ratio(defect["shell_peak_fraction_of_work"], neutral["shell_peak_fraction_of_work"]),
                "defect_outer_near": defect["outer_to_shell_tail_energy_ratio"],
                "neutral_outer_near": neutral["outer_to_shell_tail_energy_ratio"],
                "defect_lift_outer_near": _safe_ratio(defect["outer_to_shell_tail_energy_ratio"], neutral["outer_to_shell_tail_energy_ratio"]),
                "defect_tail_fraction": defect["shell_tail_fraction_of_total"],
                "neutral_tail_fraction": neutral["shell_tail_fraction_of_total"],
                "defect_lift_tail_fraction": _safe_ratio(defect["shell_tail_fraction_of_total"], neutral["shell_tail_fraction_of_total"]),
                "defect_radius_median": defect["late_tail_shell_peak_radius_median"],
                "neutral_radius_median": neutral["late_tail_shell_peak_radius_median"],
                "radius_median_shift": _shift(defect["late_tail_shell_peak_radius_median"], neutral["late_tail_shell_peak_radius_median"]),
                "defect_radius_range": defect["late_tail_shell_peak_radius_range"],
                "neutral_radius_range": neutral["late_tail_shell_peak_radius_range"],
                "defect_lift_radius_range": _safe_ratio(defect["late_tail_shell_peak_radius_range"], neutral["late_tail_shell_peak_radius_range"]),
                "defect_arrival_time": defect["first_meaningful_shell_arrival_time"],
                "neutral_arrival_time": neutral["first_meaningful_shell_arrival_time"],
                "arrival_time_shift": _shift(defect["first_meaningful_shell_arrival_time"], neutral["first_meaningful_shell_arrival_time"]),
                "defect_window_clean": defect["window_clean"],
                "neutral_window_clean": neutral["window_clean"],
                "defect_global_outer": defect["variant_global_peak_in_outer_window"],
                "neutral_global_outer": neutral["variant_global_peak_in_outer_window"],
                "radial_profile_correlation": _corr(defect_profile, neutral_profile),
                "window_radial_profile_correlation": _corr(
                    _window_profile_slice(defect_profile, defect_config, radius, window_width, options),
                    _window_profile_slice(neutral_profile, neutral_config, radius, window_width, options),
                ),
                "best_frame_similarity": _corr(defect_best.ravel(), neutral_best.ravel()),
                "window_best_frame_similarity": _corr(defect_best[window_mask_3d], neutral_best[window_mask_3d]),
            }
        )
    return rows


def _profile_for(variant: str, radius: float, window_data: dict[tuple[str, float], dict[str, Any]]) -> np.ndarray:
    return np.asarray(window_data[(variant, float(radius))]["_tail_profile_normalized"], dtype=float)


def _window_profile_slice(
    profile: np.ndarray,
    config: Prototype3DConfig,
    radius: float,
    window_width: float,
    options: RadialWindowAudit3DOptions,
) -> np.ndarray:
    bins = _radial_bins(config, options.radial_bins)
    centers = 0.5 * (bins[:-1] + bins[1:])
    mask = (centers > radius) & (centers <= radius + window_width)
    return profile[mask]


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: RadialWindowAudit3DOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Radial-Window Neutral-Lattice Audit: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny 41^3 audit for the question: is the sign-flip retained shell tail a defect effect, "
            "or a generic cubic-boundary shell pattern that appears near radius 5?"
        ),
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best window radius: `{_format(classification.get('best_window_radius'))}`",
        "",
        "## Window Comparison",
        "",
        "| Radius | Def Ret | Neu Ret | Lift Ret | Def Peak/Work | Neu Peak/Work | Lift Peak | Def Outer/Near | Neu Outer/Near | Radius Shift | Arrival Shift | Radial Corr | Frame Sim | Clean D/N |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{_format(row.get('window_radius'))} | "
            f"{_format(row.get('defect_retention'))} | "
            f"{_format(row.get('neutral_retention'))} | "
            f"{_format(row.get('defect_lift_retention'))} | "
            f"{_format(row.get('defect_peak_work'))} | "
            f"{_format(row.get('neutral_peak_work'))} | "
            f"{_format(row.get('defect_lift_peak_work'))} | "
            f"{_format(row.get('defect_outer_near'))} | "
            f"{_format(row.get('neutral_outer_near'))} | "
            f"{_format(row.get('radius_median_shift'))} | "
            f"{_format(row.get('arrival_time_shift'))} | "
            f"{_format(row.get('radial_profile_correlation'))} | "
            f"{_format(row.get('window_best_frame_similarity'))} | "
            f"{row.get('defect_window_clean')}/{row.get('neutral_window_clean')} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Controls Held Fixed",
            "",
            f"- Grid size: `{options.grid_size}^3`",
            "- Source: calibrated sign-flipped cubic boundary source at the inner sponge edge.",
            "- Current-defect and neutral-lattice variants are matched by injected work per physical source area.",
            "- Drive frequency, cutoff time, physical domain, source geometry, sponge width, and sponge strength are fixed.",
            f"- Shell windows use the requested radius as inner edge and width `{_format(_window_width_from_options(options))}`.",
            "",
            "## Files",
            "",
            "- `radial_window_audit_3d_summary.csv`",
            "- `radial_window_comparison.csv`",
            "- `radial_window_variant_metrics.csv`",
            "- `radial_window_profile_comparison.csv`",
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
    if label == "defect_lift_detected":
        return "A stable radial window showed meaningful defect lift. Stay targeted and verify with one stronger/different defect before reviving defect-localization language."
    if label == "neutral_lattice_reproduces_shell_tail":
        return "The neutral lattice reproduced the key shell-window tail with defect-lift values near 1.0. Treat the current result as cubic-boundary shell transport, not defect-dependent localization."
    return "No stable radial window produced strong defect lift. Keep claims conservative and continue with targeted boundary-phase negative controls."


def _next_step(classification: dict[str, Any]) -> str:
    if classification["label"] == "defect_lift_detected":
        return "Run one tiny stronger/different-defect confirmation at the lifted window; do not broad sweep."
    return "Run one tiny neutral-lattice non-cubic boundary-phase negative control at 41^3; do not broad sweep."


def _closest_radius(rows: list[dict[str, Any]], target: float) -> float:
    return min((float(row["window_radius"]) for row in rows), key=lambda value: abs(value - target))


def _best_window(rows: list[dict[str, Any]]) -> float:
    pool = [row for row in rows if bool(row.get("defect_window_clean"))] or rows
    best = max(pool, key=lambda row: float(row.get("defect_peak_work") or 0.0) * float(row.get("defect_retention") or 0.0))
    return float(best["window_radius"])


def _window_width(config: Prototype3DConfig, options: RadialWindowAudit3DOptions) -> float:
    return float(options.window_width) if options.window_width is not None else options.near_shell_width_dx * config.dx


def _window_width_from_options(options: RadialWindowAudit3DOptions) -> float:
    if options.window_width is not None:
        return float(options.window_width)
    return options.near_shell_width_dx * (40.0 / float(max(options.grid_size - 1, 1)))


def _row_by_variant(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    for row in rows:
        if row["variant"] == variant:
            return row
    raise KeyError(variant)


def _read_numeric_csv(path: Path) -> list[dict[str, float]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        parsed_rows: list[dict[str, float]] = []
        for row in csv.DictReader(fh):
            parsed: dict[str, float] = {}
            for key, value in row.items():
                try:
                    parsed[key] = float(value)
                except (TypeError, ValueError):
                    parsed[key] = 0.0
            parsed_rows.append(parsed)
        return parsed_rows


def _tail_indices(indices: np.ndarray, tail_fraction: float) -> np.ndarray:
    if indices.size == 0:
        return indices
    start = int(indices.size * (1.0 - tail_fraction))
    return indices[start:]


def _mean_at(values: np.ndarray, indices: np.ndarray) -> float:
    if indices.size == 0:
        return 0.0
    return float(np.mean(values[indices]))


def _mean_profile(profiles: np.ndarray, indices: np.ndarray) -> np.ndarray:
    if indices.size == 0:
        return np.zeros(profiles.shape[1], dtype=float)
    return np.mean(profiles[indices, :], axis=0)


def _median_at(values: np.ndarray, indices: np.ndarray) -> float | None:
    if indices.size == 0:
        return None
    return float(np.median(values[indices]))


def _range_at(values: np.ndarray, indices: np.ndarray) -> float:
    if indices.size == 0:
        return 0.0
    selected = values[indices]
    return float(np.percentile(selected, 90) - np.percentile(selected, 10))


def _metrics_tail_mean(metrics_rows: list[dict[str, float]], indices: np.ndarray) -> float:
    if not metrics_rows or indices.size == 0:
        return 0.0
    values = np.asarray([row.get("total_energy", 0.0) for row in metrics_rows], dtype=float)
    valid = indices[indices < values.size]
    if valid.size == 0:
        return 0.0
    return float(np.mean(values[valid]))


def _normalize(values: np.ndarray) -> np.ndarray:
    total = float(np.sum(values))
    if total <= EPSILON:
        return np.zeros_like(values)
    return values / total


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
    return float(np.dot(first, second) / denom)


def _safe_ratio(first: Any, second: Any) -> float:
    return float(first or 0.0) / (float(second or 0.0) + EPSILON)


def _shift(first: Any, second: Any) -> float | None:
    if first in (None, "") or second in (None, ""):
        return None
    return abs(float(first) - float(second))


def _variant_window_fields() -> list[str]:
    return [
        "variant",
        "radial_window_role",
        "window_radius",
        "window_outer_radius",
        "window_width",
        "window_bin_count",
        "positive_work_before_cutoff",
        "work_per_source_area",
        "shell_peak_fraction_of_work",
        "shell_peak_time",
        "shell_peak_radius_at_peak_time",
        "shell_tail_fraction_of_total",
        "shell_tail_retention",
        "outer_tail_mean_energy",
        "outer_to_shell_tail_energy_ratio",
        "first_meaningful_shell_arrival_time",
        "late_tail_shell_peak_radius_median",
        "late_tail_shell_peak_radius_range",
        "window_clean",
        "variant_global_peak_in_outer_window",
        "total_tail_mean_energy",
        "metrics_total_tail_mean_energy",
    ]


def _comparison_fields() -> list[str]:
    return [
        "window_radius",
        "window_outer_radius",
        "radial_window_audit_classification",
        "defect_retention",
        "neutral_retention",
        "defect_lift_retention",
        "defect_peak_work",
        "neutral_peak_work",
        "defect_lift_peak_work",
        "defect_outer_near",
        "neutral_outer_near",
        "defect_lift_outer_near",
        "defect_tail_fraction",
        "neutral_tail_fraction",
        "defect_lift_tail_fraction",
        "defect_radius_median",
        "neutral_radius_median",
        "radius_median_shift",
        "defect_radius_range",
        "neutral_radius_range",
        "defect_lift_radius_range",
        "defect_arrival_time",
        "neutral_arrival_time",
        "arrival_time_shift",
        "defect_window_clean",
        "neutral_window_clean",
        "defect_global_outer",
        "neutral_global_outer",
        "radial_profile_correlation",
        "window_radial_profile_correlation",
        "best_frame_similarity",
        "window_best_frame_similarity",
    ]


def _profile_fields() -> list[str]:
    return [
        "variant",
        "window_radius",
        "bin_index",
        "bin_center",
        "in_window",
        "tail_profile_energy",
        "tail_profile_normalized",
    ]
