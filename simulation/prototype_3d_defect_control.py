"""Tiny 41^3 defect-dependence control for the 3D sign-flip source."""

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
    _radial_bins,
    _run_variant,
    _summary_fields as _prototype_summary_fields,
    _write_csv as _write_prototype_csv,
)
from .prototype_3d_audit import (
    Prototype3DFailureAuditOptions,
    _radial_bin_counts,
    run_3d_failure_audit,
)
from .prototype_3d_cubic_confirmation import _stability_summary
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_source_geometry import ALL_FACES
from .prototype_3d_source_sponge import (
    _effective_source_area,
    _float_or,
    _format,
    _merge_rows,
    _ratio,
    _write_csv,
)
from .prototype_3d_threshold_control import (
    _calibrated_reference_amplitude,
    _calibration_work_per_area,
)


@dataclass(frozen=True)
class DefectControl3DOptions:
    """Options for the tiny 41^3 defect-ablation control."""

    output_root: str = "runs"
    grid_size: int = 41
    reference_source_grid_size: int = 31
    sample_every: int = 2
    radial_bins: int = 24
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    smaller_radius_multiplier: float = 0.75
    larger_radius_multiplier: float = 1.25
    target_work_per_source_area: float | None = None
    min_retention: float = 0.45
    max_outer_ratio: float = 2.0
    max_near_radius_range: float = 4.5
    max_radius_shift: float = 4.5
    max_arrival_shift: float = 4.0
    min_near_peak_ratio: float = 0.20
    max_near_peak_ratio: float = 8.0
    material_retention_fraction: float = 0.75
    material_peak_fraction: float = 0.50
    material_radius_shift: float = 1.0
    material_arrival_shift: float = 1.5


def run_3d_defect_control(
    base_config: SimulationConfig,
    *,
    options: DefectControl3DOptions | None = None,
) -> dict[str, Any]:
    """Run a focused 41^3 defect-dependence check around the sign-flip source."""

    options = options or DefectControl3DOptions()
    control_id = datetime.now().strftime("defect_control_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    reference_config = variants[0]
    reference_radius = reference_config.defect_radius
    reference_dx = reference_config.dx
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    target_work_per_area = options.target_work_per_source_area or _calibration_work_per_area(
        base_config,
        _threshold_like_options(options),
        source_width,
    )
    reference_drive_amplitude = _calibrated_reference_amplitude(
        base_config,
        _threshold_like_options(options),
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
                "label": "defect_control_3d",
                "reason": "Tiny 41^3 defect-dependence check around the sign-flipped cubic source.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "defect_control_3d_report.md"),
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
    for row in control_rows:
        config = configs_by_variant[row["variant"]]
        row.update(_fixed_window_metrics(row, config, reference_radius, reference_dx, options))
    classification = classify_defect_control(control_rows, options)
    for row in control_rows:
        row["defect_control_classification"] = classification["label"]

    summary_csv = root / "defect_control_3d_summary.csv"
    report_path = root / "defect_control_3d_report.md"
    _write_csv(summary_csv, control_rows, _summary_fields())
    _write_report(
        report_path,
        control_id,
        control_rows,
        classification,
        options,
        audit,
        reference_radius,
        reference_dx,
    )
    save_json(
        root / "defect_control_3d_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": control_rows,
            "summary_csv": str(summary_csv),
            "report_path": str(report_path),
            "audit_report_path": audit["report_path"],
            "fixed_window_reference_radius": reference_radius,
            "fixed_window_reference_dx": reference_dx,
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": control_rows,
        "summary_csv": str(summary_csv),
        "report_path": str(report_path),
        "audit_report_path": audit["report_path"],
        "path": str(root),
    }


def classify_defect_control(
    rows: list[dict[str, Any]],
    options: DefectControl3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the retained 41^3 near-shell tail depends on the defect."""

    options = options or DefectControl3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No 3D defect-control rows were available.", "checks": {}}
    by_variant = {row["variant"]: row for row in rows}
    reference = by_variant.get("current_defect_reference")
    hard_dt_warnings = [row["variant"] for row in rows if _has_hard_dt_warning(row)]
    checks = {
        "reference": _row_checks(reference, reference, options),
        "no_defect": _row_checks(by_variant.get("no_defect_neutral_lattice"), reference, options),
        "stiffness_neutral": _row_checks(by_variant.get("defect_stiffness_multiplier_1_0"), reference, options),
        "coupling_neutral": _row_checks(by_variant.get("defect_coupling_multiplier_1_0"), reference, options),
        "damping_neutral": _row_checks(by_variant.get("defect_damping_multiplier_1_0"), reference, options),
        "smaller_radius": _row_checks(by_variant.get("smaller_defect_radius"), reference, options),
        "larger_radius": _row_checks(by_variant.get("larger_defect_radius"), reference, options),
        "hard_dt_warnings": hard_dt_warnings,
    }
    if hard_dt_warnings:
        return {
            "label": "unstable_due_to_dt",
            "reason": f"At least one 41^3 defect-control variant exceeded the hard dt estimate: {', '.join(hard_dt_warnings)}.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not checks["reference"].get("clean", False):
        return {
            "label": "reference_not_reproduced",
            "reason": "The current-defect sign-flip reference did not reproduce the clean retained near-shell tail.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }

    no_defect_changed = _materially_changed(checks["no_defect"], checks["reference"], options)
    property_changed = any(
        _materially_changed(checks[name], checks["reference"], options)
        for name in ("stiffness_neutral", "coupling_neutral", "damping_neutral")
    )
    radius_changed = any(
        _materially_changed(checks[name], checks["reference"], options)
        for name in ("smaller_radius", "larger_radius")
    )
    if no_defect_changed:
        return {
            "label": "defect_dependent_retained_shell_mode",
            "reason": "Neutralizing the defect changed, weakened, or shifted the fixed-window retained near-shell tail.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not no_defect_changed and not property_changed and not radius_changed:
        return {
            "label": "defect_independent_boundary_standing_wave",
            "reason": "The retained near-shell tail survived nearly unchanged when the defect was neutralized and when defect parameters were perturbed.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if property_changed:
        return {
            "label": "defect_property_sensitive",
            "reason": "The fully neutral defect remained similar, but at least one individual defect-property ablation changed the tail.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if radius_changed:
        return {
            "label": "defect_radius_sensitive",
            "reason": "The fully neutral defect remained similar, but changing the defect radius shifted or weakened the tail.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "inconclusive",
        "reason": "The defect-control metrics were mixed and did not isolate defect dependence.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: DefectControl3DOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    reference_radius = _base_defect_radius(base)
    variants = [
        _boundary_config("current_defect_reference", base, options, source_width),
        _boundary_config(
            "no_defect_neutral_lattice",
            base,
            options,
            source_width,
            stiffness_multiplier=1.0,
            damping_multiplier=1.0,
            coupling_multiplier=1.0,
        ),
        _boundary_config("defect_stiffness_multiplier_1_0", base, options, source_width, stiffness_multiplier=1.0),
        _boundary_config("defect_coupling_multiplier_1_0", base, options, source_width, coupling_multiplier=1.0),
        _boundary_config("defect_damping_multiplier_1_0", base, options, source_width, damping_multiplier=1.0),
        _boundary_config(
            "smaller_defect_radius",
            base,
            options,
            source_width,
            defect_radius=reference_radius * options.smaller_radius_multiplier,
        ),
        _boundary_config(
            "larger_defect_radius",
            base,
            options,
            source_width,
            defect_radius=reference_radius * options.larger_radius_multiplier,
        ),
    ]
    return variants


def _prototype_options(config: Prototype3DConfig, options: DefectControl3DOptions) -> Prototype3DOptions:
    return Prototype3DOptions(
        output_root=options.output_root,
        grid_size=config.grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        include_dt_control=False,
        include_sponge_control=False,
    )


def _boundary_config(
    name: str,
    base: SimulationConfig,
    options: DefectControl3DOptions,
    source_width: float,
    *,
    defect_radius: float | None = None,
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
    if defect_radius is not None:
        config.defect_radius = defect_radius
        config.shell_inner_radius = defect_radius + config.dx
        config.shell_outer_radius = defect_radius + 3.0 * config.dx
    if stiffness_multiplier is not None:
        config.defect_stiffness_multiplier = stiffness_multiplier
    if damping_multiplier is not None:
        config.defect_damping_multiplier = damping_multiplier
    if coupling_multiplier is not None:
        config.defect_coupling_multiplier = coupling_multiplier
    return config


def _threshold_like_options(options: DefectControl3DOptions) -> Any:
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


def _base_defect_radius(base: SimulationConfig) -> float:
    return float(base.defect.radius_physical if base.defect.radius_physical is not None else base.defect.radius)


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    reference_config: Prototype3DConfig,
    options: DefectControl3DOptions,
    target_work_per_area: float,
) -> None:
    summary["defect_control_role"] = _role(config.name)
    summary["defect_radius_multiplier"] = config.defect_radius / max(reference_config.defect_radius, EPSILON)
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    original_sponge_strength = reference_config.sponge_strength / max(options.sponge_strength_multiplier, EPSILON)
    summary["sponge_strength_multiplier_vs_original"] = config.sponge_strength / max(original_sponge_strength, EPSILON)
    summary["sponge_width_multiplier"] = config.sponge_width / max(reference_config.sponge_width, EPSILON)
    summary["source_width_physical_reference"] = reference_config.boundary_source_width
    summary["target_reference_work_per_source_area"] = target_work_per_area
    summary["calibration_source_grid_size"] = options.reference_source_grid_size
    summary.update(_stability_summary(config))


def _role(variant: str) -> str:
    if variant == "current_defect_reference":
        return "reference"
    if variant == "no_defect_neutral_lattice":
        return "neutral_lattice"
    if variant.endswith("_1_0"):
        return "property_ablation"
    if variant.endswith("_radius"):
        return "radius_ablation"
    return "unknown"


def _fixed_window_metrics(
    row: dict[str, Any],
    config: Prototype3DConfig,
    reference_radius: float,
    reference_dx: float,
    options: DefectControl3DOptions,
) -> dict[str, Any]:
    radial_rows = _read_numeric_csv(Path(str(row["path"])) / "radial_profile_timeseries.csv")
    if not radial_rows:
        return {}
    bins = _radial_bins(config, options.radial_bins)
    centers = 0.5 * (bins[:-1] + bins[1:])
    counts = _radial_bin_counts(config, bins)
    near_mask = (centers > reference_radius) & (centers <= reference_radius + options.near_shell_width_dx * reference_dx)
    outer_start = max(reference_radius, 0.5 * config.domain_size - config.sponge_width)
    outer_mask = centers >= outer_start
    profiles = np.asarray(
        [[item.get(f"bin_{idx}", 0.0) for idx in range(options.radial_bins)] for item in radial_rows],
        dtype=float,
    )
    totals_by_bin = profiles * counts[np.newaxis, :]
    times = np.asarray([item["time"] for item in radial_rows], dtype=float)
    total_energy = np.sum(totals_by_bin, axis=1)
    near_energy = np.sum(totals_by_bin[:, near_mask], axis=1)
    outer_energy = np.sum(totals_by_bin[:, outer_mask], axis=1)
    near_peak_idx = np.argmax(np.where(near_mask, profiles, -np.inf), axis=1)
    near_peak_radius = centers[near_peak_idx]
    global_peak_idx = np.argmax(np.where(centers > reference_radius, profiles, -np.inf), axis=1)
    global_peak_radius = centers[global_peak_idx]
    post_indices = np.flatnonzero(times > config.drive_cutoff_time)
    tail_indices = _tail_indices(post_indices, 0.35)
    work = float(row.get("positive_work_before_cutoff") or 0.0)
    near_peak = float(np.max(near_energy)) if near_energy.size else 0.0
    near_peak_time_index = int(np.argmax(near_energy)) if near_energy.size else 0
    arrival_threshold = max(near_peak * 0.10, work * 1e-8)
    arrival_candidates = np.flatnonzero(near_energy >= arrival_threshold)
    meaningful_arrival = None
    if arrival_candidates.size and near_peak / (work + EPSILON) >= 1e-8:
        meaningful_arrival = float(times[arrival_candidates[0]])
    tail_near = _mean_at(near_energy, tail_indices)
    tail_outer = _mean_at(outer_energy, tail_indices)
    tail_total = _mean_at(total_energy, tail_indices)
    tail_global = _median_at(global_peak_radius, tail_indices)
    return {
        "fixed_window_reference_radius": reference_radius,
        "fixed_window_inner_radius": reference_radius,
        "fixed_window_outer_radius": reference_radius + options.near_shell_width_dx * reference_dx,
        "fixed_near_shell_peak_fraction_of_work": near_peak / (work + EPSILON),
        "fixed_near_shell_peak_time": float(times[near_peak_time_index]) if near_energy.size else None,
        "fixed_near_shell_peak_radius_at_peak_time": float(near_peak_radius[near_peak_time_index]) if near_energy.size else None,
        "fixed_near_shell_tail_fraction_of_total": tail_near / (tail_total + EPSILON),
        "fixed_near_shell_tail_retention": tail_near / (near_peak + EPSILON),
        "fixed_outer_to_near_tail_energy_ratio": tail_outer / (tail_near + EPSILON),
        "fixed_first_meaningful_near_shell_arrival_time": meaningful_arrival,
        "fixed_late_tail_near_shell_peak_radius_median": _median_at(near_peak_radius, tail_indices),
        "fixed_late_tail_near_shell_peak_radius_range": _range_at(near_peak_radius, tail_indices),
        "fixed_late_tail_global_peak_radius_median": tail_global,
        "fixed_global_peak_in_outer_window": bool(tail_global is not None and tail_global >= outer_start),
    }


def _row_checks(
    row: dict[str, Any] | None,
    reference: dict[str, Any] | None,
    options: DefectControl3DOptions,
) -> dict[str, Any]:
    if row is None:
        return {}
    retention = _float_or(row.get("fixed_near_shell_tail_retention"), 0.0)
    outer_ratio = _float_or(row.get("fixed_outer_to_near_tail_energy_ratio"), 999.0)
    radius_range = _float_or(row.get("fixed_late_tail_near_shell_peak_radius_range"), 999.0)
    arrival = row.get("fixed_first_meaningful_near_shell_arrival_time")
    near_peak_ratio = _ratio(
        row.get("fixed_near_shell_peak_fraction_of_work"),
        reference.get("fixed_near_shell_peak_fraction_of_work") if reference else None,
    )
    radius_shift = _shift(
        row.get("fixed_late_tail_near_shell_peak_radius_median"),
        reference.get("fixed_late_tail_near_shell_peak_radius_median") if reference else None,
    )
    arrival_shift = _shift(arrival, reference.get("fixed_first_meaningful_near_shell_arrival_time") if reference else None)
    global_outer = bool(row.get("fixed_global_peak_in_outer_window"))
    clean = (
        retention >= options.min_retention
        and outer_ratio <= options.max_outer_ratio
        and not global_outer
        and options.min_near_peak_ratio <= near_peak_ratio <= options.max_near_peak_ratio
        and radius_range <= options.max_near_radius_range
        and (radius_shift is None or radius_shift <= options.max_radius_shift)
        and arrival is not None
        and (arrival_shift is None or arrival_shift <= options.max_arrival_shift)
        and not _has_hard_dt_warning(row)
    )
    return {
        "variant": row.get("variant"),
        "clean": clean,
        "retention": retention,
        "outer_ratio": outer_ratio,
        "global_outer": global_outer,
        "near_peak_ratio_to_reference": near_peak_ratio,
        "radius_range": radius_range,
        "radius_shift": radius_shift,
        "arrival_shift": arrival_shift,
        "hard_dt_warning": _has_hard_dt_warning(row),
    }


def _materially_changed(
    check: dict[str, Any],
    reference_check: dict[str, Any],
    options: DefectControl3DOptions,
) -> bool:
    if not check:
        return False
    ref_retention = float(reference_check.get("retention") or 0.0)
    return (
        not check.get("clean", False)
        or float(check.get("retention") or 0.0) < options.material_retention_fraction * ref_retention
        or float(check.get("near_peak_ratio_to_reference") or 0.0) < options.material_peak_fraction
        or float(check.get("radius_shift") or 0.0) > options.material_radius_shift
        or float(check.get("arrival_shift") or 0.0) > options.material_arrival_shift
    )


def _shift(first: Any, second: Any) -> float | None:
    if first in (None, "") or second in (None, ""):
        return None
    return abs(float(first) - float(second))


def _has_hard_dt_warning(row: dict[str, Any]) -> bool:
    warnings = str(row.get("stability_warnings") or "")
    return "hard" in warnings.lower() and warnings.lower() != "none"


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(max(rows, key=_score).get("variant", "n/a"))


def _score(row: dict[str, Any]) -> float:
    near_peak = float(row.get("fixed_near_shell_peak_fraction_of_work") or 0.0)
    retention = float(row.get("fixed_near_shell_tail_retention") or 0.0)
    outer_ratio = max(float(row.get("fixed_outer_to_near_tail_energy_ratio") or 999.0), 0.25)
    range_penalty = max(float(row.get("fixed_late_tail_near_shell_peak_radius_range") or 1.0), 1.0)
    outer_factor = 0.5 if bool(row.get("fixed_global_peak_in_outer_window")) else 1.0
    return near_peak * retention * outer_factor / (outer_ratio * range_penalty)


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: DefectControl3DOptions,
    audit: dict[str, Any],
    reference_radius: float,
    reference_dx: float,
) -> None:
    lines = [
        f"# 3D Defect Dependence Control: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny 41^3 defect-ablation control around the calibrated sign-flipped cubic stronger-sponge "
            "boundary source. This checks whether the retained near-shell tail requires the spherical defect."
        ),
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Fixed-Window Variant Summary",
        "",
        "| Variant | Role | Radius x | k x | c x | coupling x | Work/Area | Peak/Work | Retention | Radius Median | Radius Range | Outer/Near | Global Outer? | Arrival | dt Warning |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('defect_control_role')} | "
            f"{_format(row.get('defect_radius_multiplier'))} | "
            f"{_format(row.get('defect_stiffness_multiplier'))} | "
            f"{_format(row.get('defect_damping_multiplier'))} | "
            f"{_format(row.get('defect_coupling_multiplier'))} | "
            f"{_format(row.get('work_per_source_area'))} | "
            f"{_format(row.get('fixed_near_shell_peak_fraction_of_work'))} | "
            f"{_format(row.get('fixed_near_shell_tail_retention'))} | "
            f"{_format(row.get('fixed_late_tail_near_shell_peak_radius_median'))} | "
            f"{_format(row.get('fixed_late_tail_near_shell_peak_radius_range'))} | "
            f"{_format(row.get('fixed_outer_to_near_tail_energy_ratio'))} | "
            f"{row.get('fixed_global_peak_in_outer_window')} | "
            f"{_format(row.get('fixed_first_meaningful_near_shell_arrival_time'))} | "
            f"{row.get('stability_warnings')} |"
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
            f"- Target work per physical source area: `{_format(options.target_work_per_source_area or rows[0].get('target_reference_work_per_source_area'))}`",
            "- Boundary variants are matched by injected work per physical source area.",
            "- Drive frequency, cutoff time, physical domain, source geometry, sponge width, and sponge strength are fixed.",
            f"- Main comparison uses a fixed near-shell window from radius `{_format(reference_radius)}` to `{_format(reference_radius + options.near_shell_width_dx * reference_dx)}`.",
            "- The failure-mode audit still reports variant-relative defect-window metrics for radius-change context.",
            "",
            "## Files",
            "",
            "- `defect_control_3d_summary.csv`",
            "- `defect_control_3d_summary.json`",
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
    if label == "defect_dependent_retained_shell_mode":
        return "The neutral-lattice ablation changed the retained near-shell tail, supporting defect dependence for this boundary-driven 3D candidate."
    if label == "defect_independent_boundary_standing_wave":
        return "The neutral lattice and defect perturbations preserved the tail, so this looks more like a cubic-boundary standing-wave transport pattern than a defect-localized mode."
    if label == "defect_property_sensitive":
        return "The fully neutral lattice stayed similar, but individual defect-property ablations changed the tail. Interpret cautiously and isolate the property next."
    if label == "defect_radius_sensitive":
        return "The fully neutral lattice stayed similar, but changing defect radius shifted or weakened the tail. Interpret as radius sensitivity, not full defect requirement."
    if label == "reference_not_reproduced":
        return "The current-defect reference did not reproduce the clean 41^3 tail, so this pass cannot answer defect dependence."
    if label == "unstable_due_to_dt":
        return "A hard dt warning appeared. Re-run with smaller dt before interpreting defect dependence."
    return "The defect-control result is mixed. Keep the next step targeted."


def _next_step(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "defect_dependent_retained_shell_mode":
        return "Do not broad sweep yet; next run one tiny 41^3 half-dt confirmation for the current-defect reference and neutral-lattice ablation."
    if label == "defect_independent_boundary_standing_wave":
        return "Do not broad sweep yet; reframe the candidate as boundary/cubic transport and test one negative boundary-phase control at 41^3."
    if label in {"defect_property_sensitive", "defect_radius_sensitive"}:
        return "Stay at 41^3 and isolate only the sensitive defect parameter before broader 3D work."
    return "Resolve this defect-control confound before any broad 3D sweep."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "defect_control_classification",
        "defect_control_role",
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
        "defect_radius",
        "defect_radius_multiplier",
        "defect_stiffness_multiplier",
        "defect_damping_multiplier",
        "defect_coupling_multiplier",
        "boundary_faces",
        "boundary_face_count",
        "boundary_phase_offset",
        "boundary_cubic_phase_sign",
        "sponge_strength",
        "sponge_strength_multiplier_vs_original",
        "sponge_width",
        "sponge_width_multiplier",
        "boundary_source_inner_distance",
        "boundary_source_width",
        "source_width_physical_reference",
        "calibration_source_grid_size",
        "target_reference_work_per_source_area",
        "effective_source_area",
        "positive_work_before_cutoff",
        "work_per_source_area",
        "source_sponge_overlap_fraction",
        "source_high_sponge_overlap_fraction",
        "source_mean_sponge_fraction_of_max",
        "fixed_window_reference_radius",
        "fixed_window_inner_radius",
        "fixed_window_outer_radius",
        "fixed_near_shell_peak_fraction_of_work",
        "fixed_near_shell_peak_time",
        "fixed_near_shell_peak_radius_at_peak_time",
        "fixed_first_meaningful_near_shell_arrival_time",
        "fixed_near_shell_tail_fraction_of_total",
        "fixed_near_shell_tail_retention",
        "fixed_late_tail_near_shell_peak_radius_median",
        "fixed_late_tail_near_shell_peak_radius_range",
        "fixed_late_tail_global_peak_radius_median",
        "fixed_outer_to_near_tail_energy_ratio",
        "fixed_global_peak_in_outer_window",
        "near_shell_peak_fraction_of_work",
        "near_shell_tail_retention",
        "late_tail_near_shell_peak_radius_median",
        "late_tail_near_shell_peak_radius_range",
        "outer_to_near_tail_energy_ratio",
        "global_shell_peak_radius",
        "global_peak_in_outer_window",
        "post_cutoff_shell_retention",
        "shell_breathing_detected",
        "shell_breathing_period",
        "recommended_dt_max",
        "hard_stability_dt_max",
        "dt_to_recommended_ratio",
        "dt_to_hard_limit_ratio",
        "stability_warnings",
        "path",
    ]


def _read_numeric_csv(path: Path) -> list[dict[str, float]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        rows: list[dict[str, float]] = []
        for row in csv.DictReader(fh):
            parsed: dict[str, float] = {}
            for key, value in row.items():
                try:
                    parsed[key] = float(value)
                except (TypeError, ValueError):
                    parsed[key] = 0.0
            rows.append(parsed)
        return rows


def _tail_indices(indices: np.ndarray, tail_fraction: float) -> np.ndarray:
    if indices.size == 0:
        return indices
    start = int(indices.size * (1.0 - tail_fraction))
    return indices[start:]


def _mean_at(values: np.ndarray, indices: np.ndarray) -> float:
    if indices.size == 0:
        return 0.0
    return float(np.mean(values[indices]))


def _median_at(values: np.ndarray, indices: np.ndarray) -> float | None:
    if indices.size == 0:
        return None
    return float(np.median(values[indices]))


def _range_at(values: np.ndarray, indices: np.ndarray) -> float:
    if indices.size == 0:
        return 0.0
    selected = values[indices]
    return float(np.percentile(selected, 90) - np.percentile(selected, 10))
