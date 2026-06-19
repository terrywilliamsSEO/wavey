"""Tiny 3D cutoff phase/timing map for the cubic refocusing packet."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any
import math

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig, _calibrate_amplitude
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _boundary_config as _interference_boundary_config, _threshold_like_options
from .prototype_3d_packet_lifecycle import (
    _event_fields,
    _major_peaks,
    _plot_flux,
    _plot_lifecycle,
    _plot_radius_width,
    _run_lifecycle_variant,
    _timeseries_fields,
)
from .prototype_3d_refocusing_engineering import (
    RefocusingEngineering3DOptions,
    _comparison_fields,
    _format,
    _lifecycle_options,
    _summary_fields as _engineering_summary_fields,
)
from .prototype_3d_source_sponge import _effective_source_area, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


@dataclass(frozen=True)
class CutoffPhaseMap3DOptions(RefocusingEngineering3DOptions):
    """Options for a tiny cutoff phase/timing map."""

    reference_variant: str = "phase_offset_cutoff_reference"
    cutoff_center: float | None = None
    cutoff_offsets: tuple[float, ...] = (-1.0, -0.5, 0.0, 0.5, 1.0)
    phase_offsets: tuple[float, ...] = (-float(np.pi) / 16.0, 0.0, float(np.pi) / 16.0)
    include_phase_offset_family: bool = True
    include_polarity_family: bool = True
    polarity_cutoff_offsets: tuple[float, ...] = (-0.5, 0.0, 0.5)
    strict_retention_target: float = 0.30
    strict_outer_shell_target: float = 1.0
    timing_cluster_phase_tolerance_cycles: float = 0.12


def run_3d_cutoff_phase_map_control(
    base_config: SimulationConfig,
    *,
    options: CutoffPhaseMap3DOptions | None = None,
) -> dict[str, Any]:
    """Run a tiny cutoff-timing and release-phase map at fixed frequency."""

    options = options or CutoffPhaseMap3DOptions()
    control_id = datetime.now().strftime("cutoff_phase_map_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    lifecycle_options = _lifecycle_options(options)
    threshold_options = _threshold_like_options(lifecycle_options)
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
        result = _run_lifecycle_variant(config, root, lifecycle_options)
        summary = result["summary"]
        _add_control_fields(summary, config, options, target_work_per_area)
        rows.append(summary)
        timeseries_rows.extend(result["timeseries"])
        event_rows.extend(result["events"])

    classification = classify_cutoff_phase_map(rows, options)
    reference = _cutoff_reference_row(rows, options)
    for row in rows:
        row.update(_comparison_fields(row, reference))
        row["cutoff_phase_map_classification"] = classification["label"]

    ranked_rows = _ranked_rows(rows)
    needle_width = phase_lock_needle_width(rows, options)
    threshold_sensitivity_rows = event_threshold_sensitivity_audit(rows, timeseries_rows, options)
    threshold_sensitivity = summarize_event_threshold_sensitivity(threshold_sensitivity_rows)

    summary_csv = root / "cutoff_phase_map_summary.csv"
    ranked_csv = root / "cutoff_phase_ranked_summary.csv"
    threshold_sensitivity_csv = root / "cutoff_phase_event_threshold_sensitivity.csv"
    timeseries_csv = root / "cutoff_phase_map_timeseries.csv"
    events_csv = root / "cutoff_phase_map_events.csv"
    report_path = root / "cutoff_phase_map_3d_report.md"
    _write_csv(summary_csv, rows, _summary_fields())
    _write_csv(ranked_csv, ranked_rows, _ranked_fields())
    _write_csv(threshold_sensitivity_csv, threshold_sensitivity_rows, _threshold_sensitivity_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(events_csv, event_rows, _event_fields())
    _plot_lifecycle(root / "cutoff_phase_shell_energy_plot.png", timeseries_rows, event_rows)
    _plot_radius_width(root / "cutoff_phase_radius_width_plot.png", timeseries_rows)
    _plot_flux(root / "cutoff_phase_flux_balance_plot.png", timeseries_rows)
    _write_report(report_path, control_id, rows, classification, options, needle_width, threshold_sensitivity, threshold_sensitivity_rows)
    save_json(
        root / "cutoff_phase_map_3d_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "phase_lock_needle_width": needle_width,
            "event_threshold_sensitivity": threshold_sensitivity,
            "variants": rows,
            "summary_csv": str(summary_csv),
            "ranked_csv": str(ranked_csv),
            "threshold_sensitivity_csv": str(threshold_sensitivity_csv),
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
        "ranked_csv": str(ranked_csv),
        "threshold_sensitivity_csv": str(threshold_sensitivity_csv),
        "timeseries_csv": str(timeseries_csv),
        "events_csv": str(events_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_cutoff_phase_map(
    rows: list[dict[str, Any]],
    options: CutoffPhaseMap3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether cutoff release phase has a useful timing island."""

    options = options or CutoffPhaseMap3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No cutoff-phase rows were available.", "checks": {}}
    reference = _cutoff_reference_row(rows, options)
    checks = {row["variant"]: _row_checks(row, reference, options) for row in rows}
    clean_rows = [row for row in rows if _is_clean(row, reference, options)]
    improved = [row for row in clean_rows if row is not reference and _beats_reference(row, reference)]
    strong = [row for row in clean_rows if _is_strong(row, options)]
    clustered = _phase_cluster(strong or improved or [reference], options)
    stability = release_phase_island_stability(rows, options)
    polarity_rows = [row for row in clean_rows if row.get("family") == "sign_flip"]
    phase_rows = [row for row in clean_rows if row.get("family") == "phase_offset"]
    best = _best_variant(clean_rows or rows)

    if strong and clustered and stability["is_stable"]:
        return {
            "label": "cutoff_phase_timing_island_supported",
            "reason": "Strong clean timing variants met strict retention/outer guards and the best rows form a neighboring release-phase cluster.",
            "best_variant": best,
            "release_phase_island_stability": stability,
            "checks": checks,
        }
    if strong:
        return {
            "label": "cutoff_phase_single_point_best",
            "reason": "At least one strong clean timing variant met strict guards, but the best rows did not form a neighboring cutoff cluster.",
            "best_variant": best,
            "release_phase_island_stability": stability,
            "checks": checks,
        }
    if improved:
        return {
            "label": "cutoff_timing_improved",
            "reason": f"A nearby release timing improved at least one refocusing metric without violating cleanliness guards. Best: {best}.",
            "best_variant": best,
            "release_phase_island_stability": stability,
            "checks": checks,
        }
    if polarity_rows and phase_rows:
        best_polarity = _best_variant(polarity_rows)
        best_phase = _best_variant(phase_rows)
        if best_polarity != best_phase:
            return {
                "label": "polarity_family_sensitive",
                "reason": "Both polarity families stayed interpretable, but their best rows differ and no timing variant beat the cutoff reference.",
                "best_variant": best,
                "release_phase_island_stability": stability,
                "checks": checks,
            }
    if len(clean_rows) > 1:
        return {
            "label": "cutoff_phase_tolerant_no_improvement",
            "reason": "Nearby cutoff phases stayed clean, but none improved the cutoff_long reference enough to call a timing island.",
            "best_variant": best,
            "release_phase_island_stability": stability,
            "checks": checks,
        }
    return {
        "label": "cutoff_phase_inconclusive",
        "reason": "The cutoff phase map did not produce enough clean comparable rows for interpretation.",
        "best_variant": best,
        "release_phase_island_stability": stability,
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: CutoffPhaseMap3DOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    center = _cutoff_center(base, options)
    frequency = float(base.driver.frequency)
    variants: list[Prototype3DConfig] = []
    if options.include_phase_offset_family:
        for offset in options.cutoff_offsets:
            cutoff = max(1.0, center + offset)
            name = "phase_offset_cutoff_reference" if abs(offset) < EPSILON else _name("phase_offset_cutoff", offset)
            variants.append(
                _variant(
                    name,
                    base,
                    options,
                    source_width,
                    cutoff=cutoff,
                    frequency=frequency,
                    phase_offset=options.phase_offset,
                    cubic_sign=-1.0,
                    family="phase_offset",
                    axis="cutoff",
                    cutoff_offset=offset,
                )
            )
        for phase_delta in options.phase_offsets:
            if abs(phase_delta) < EPSILON:
                continue
            variants.append(
                _variant(
                    _name("phase_offset_delta", phase_delta / math.pi),
                    base,
                    options,
                    source_width,
                    cutoff=center,
                    frequency=frequency,
                    phase_offset=options.phase_offset + phase_delta,
                    cubic_sign=-1.0,
                    family="phase_offset",
                    axis="phase_offset",
                    cutoff_offset=0.0,
                    phase_delta=phase_delta,
                )
            )
    if options.include_polarity_family:
        for offset in options.polarity_cutoff_offsets:
            cutoff = max(1.0, center + offset)
            name = "sign_flip_cutoff_reference" if abs(offset) < EPSILON else _name("sign_flip_cutoff", offset)
            variants.append(
                _variant(
                    name,
                    base,
                    options,
                    source_width,
                    cutoff=cutoff,
                    frequency=frequency,
                    phase_offset=0.0,
                    cubic_sign=-1.0,
                    family="sign_flip",
                    axis="polarity_cutoff",
                    cutoff_offset=offset,
                )
            )
    return variants


def _variant(
    name: str,
    base: SimulationConfig,
    options: CutoffPhaseMap3DOptions,
    source_width: float,
    *,
    cutoff: float,
    frequency: float,
    phase_offset: float,
    cubic_sign: float,
    family: str,
    axis: str,
    cutoff_offset: float,
    phase_delta: float = 0.0,
) -> Prototype3DConfig:
    config = _interference_boundary_config(
        name,
        base,
        _lifecycle_options(options),
        source_width,
        "cubic",
        cubic_sign=cubic_sign,
        phase_offset=phase_offset,
    )
    config.drive_cutoff_time = cutoff
    config.drive_frequency = frequency
    setattr(config, "_cutoff_phase_family", family)
    setattr(config, "_cutoff_phase_axis", axis)
    setattr(config, "_cutoff_offset", cutoff_offset)
    setattr(config, "_phase_delta", phase_delta)
    return config


def _add_control_fields(
    row: dict[str, Any],
    config: Prototype3DConfig,
    options: CutoffPhaseMap3DOptions,
    target_work_per_area: float,
) -> None:
    cutoff_phase = _cutoff_phase_cycles(config)
    row["family"] = getattr(config, "_cutoff_phase_family", "variant")
    row["axis_label"] = getattr(config, "_cutoff_phase_axis", "variant")
    row["cutoff_center"] = _cutoff_center_from_config(config, options)
    row["cutoff_offset_from_center"] = getattr(config, "_cutoff_offset", 0.0)
    row["phase_delta"] = getattr(config, "_phase_delta", 0.0)
    row["target_reference_work_per_source_area"] = target_work_per_area
    row["drive_mode"] = config.drive_mode
    row["drive_frequency"] = config.drive_frequency
    row["drive_cutoff_time"] = config.drive_cutoff_time
    row["boundary_phase_offset"] = config.boundary_phase_offset
    row["boundary_cubic_phase_sign"] = config.boundary_cubic_phase_sign
    row["phase_offset_label"] = _phase_label(config.boundary_phase_offset)
    row["cutoff_phase_cycles"] = cutoff_phase
    row["cutoff_phase_radians"] = 2.0 * math.pi * cutoff_phase
    row["cutoff_phase_label"] = f"{cutoff_phase:.4f} cycles"


def _cutoff_reference_row(
    rows: list[dict[str, Any]],
    options: CutoffPhaseMap3DOptions | None = None,
) -> dict[str, Any] | None:
    if not rows:
        return None
    options = options or CutoffPhaseMap3DOptions()
    preferred = getattr(options, "reference_variant", None)
    if preferred:
        match = next((row for row in rows if row.get("variant") == preferred), None)
        if match is not None:
            return match
    return next((row for row in rows if row.get("variant") == "phase_offset_cutoff_reference"), rows[0])


def _row_checks(
    row: dict[str, Any],
    reference: dict[str, Any] | None,
    options: CutoffPhaseMap3DOptions,
) -> dict[str, Any]:
    return {
        **_comparison_fields(row, reference),
        "clean": _is_clean(row, reference, options),
        "beats_reference": _beats_reference(row, reference),
        "strong": _is_strong(row, options),
        "family": row.get("family"),
        "cutoff_phase_cycles": row.get("cutoff_phase_cycles"),
        "refocus_peak_count": row.get("refocus_peak_count"),
        "major_shell_peak_count": row.get("major_shell_peak_count"),
        "tail_shell_retention": row.get("tail_shell_retention"),
        "tail_outer_to_shell_mean": row.get("tail_outer_to_shell_mean"),
        "shell_exit_detected": row.get("shell_exit_detected"),
    }


def _is_clean(
    row: dict[str, Any] | None,
    reference: dict[str, Any] | None,
    options: CutoffPhaseMap3DOptions,
) -> bool:
    if row is None:
        return False
    reference_retention = float((reference or {}).get("tail_shell_retention") or 0.0)
    min_retention = options.min_retention_ratio * reference_retention if reference_retention > EPSILON else 0.0
    return (
        float(row.get("tail_shell_retention") or 0.0) >= min_retention
        and float(row.get("tail_outer_to_shell_mean") or 999.0) <= options.max_outer_shell_ratio
        and not bool(row.get("global_peak_in_outer_window"))
    )


def _is_strong(row: dict[str, Any], options: CutoffPhaseMap3DOptions) -> bool:
    return (
        float(row.get("tail_shell_retention") or 0.0) >= options.strict_retention_target
        and float(row.get("tail_outer_to_shell_mean") or 999.0) <= options.strict_outer_shell_target
        and not bool(row.get("shell_exit_detected"))
        and not bool(row.get("global_peak_in_outer_window"))
    )


def _beats_reference(row: dict[str, Any] | None, reference: dict[str, Any] | None) -> bool:
    if row is None or reference is None or row is reference or row.get("variant") == reference.get("variant"):
        return False
    ref_major = int(reference.get("major_shell_peak_count") or 0)
    ref_refocus = int(reference.get("refocus_peak_count") or 0)
    ref_retention = float(reference.get("tail_shell_retention") or 0.0)
    ref_outer = float(reference.get("tail_outer_to_shell_mean") or 999.0)
    ref_decay = float(reference.get("post_cutoff_shell_decay_rate") or 0.0)
    row_exit = bool(row.get("shell_exit_detected"))
    ref_exit = bool(reference.get("shell_exit_detected"))
    row_exit_time = row.get("shell_exit_time")
    ref_exit_time = reference.get("shell_exit_time")
    exit_improved = (ref_exit and not row_exit) or (
        row_exit_time is not None and ref_exit_time is not None and float(row_exit_time) > float(ref_exit_time) + 2.0
    )
    return (
        int(row.get("major_shell_peak_count") or 0) > ref_major
        or int(row.get("refocus_peak_count") or 0) > ref_refocus
        or float(row.get("tail_shell_retention") or 0.0) >= ref_retention * 1.05
        or float(row.get("tail_outer_to_shell_mean") or 999.0) <= ref_outer * 0.90
        or float(row.get("post_cutoff_shell_decay_rate") or 0.0) > ref_decay + 0.005
        or exit_improved
    )


def _phase_cluster(rows: list[dict[str, Any] | None], options: CutoffPhaseMap3DOptions) -> bool:
    values = [float(row["cutoff_phase_cycles"]) for row in rows if row and row.get("cutoff_phase_cycles") is not None]
    if len(values) < 2:
        return bool(values)
    values = sorted(values)
    best_span = min(_circular_span(values, start) for start in values)
    return best_span <= options.timing_cluster_phase_tolerance_cycles


def _circular_span(values: list[float], start: float) -> float:
    shifted = sorted(((value - start) % 1.0) for value in values)
    return shifted[-1] - shifted[0]


def phase_lock_needle_width(
    rows: list[dict[str, Any]],
    options: CutoffPhaseMap3DOptions | None = None,
) -> dict[str, Any]:
    """Report how wide the best release-phase peak appears across neighboring cutoffs."""

    options = options or CutoffPhaseMap3DOptions()
    if not rows:
        return {
            "label": "no_rows",
            "reason": "No rows were available for phase-lock needle-width analysis.",
            "best_variant": "n/a",
            "best_cutoff": None,
            "best_release_phase": None,
            "neighboring_within_one_peak_refocus": [],
            "neighboring_within_10pct_retention": [],
            "neighboring_outer_below_1": [],
        }
    ranked = _ranked_rows(rows)
    best = ranked[0]
    best_family = best.get("family")
    best_axis = best.get("axis_label")
    same_family_rows = sorted(
        [
            row
            for row in rows
            if row.get("family") == best_family
            and row.get("axis_label") == best_axis
            and row.get("cutoff_offset_from_center") is not None
        ],
        key=lambda row: float(row.get("cutoff_offset_from_center") or 0.0),
    )
    best_index = next((index for index, row in enumerate(same_family_rows) if row.get("variant") == best.get("variant")), None)
    best_major = int(best.get("major_shell_peak_count") or 0)
    best_refocus = int(best.get("refocus_peak_count") or 0)
    best_retention = float(best.get("tail_shell_retention") or 0.0)
    best_variant = best.get("variant")

    def within_one(row: dict[str, Any]) -> bool:
        return (
            row.get("variant") != best_variant
            and abs(int(row.get("major_shell_peak_count") or 0) - best_major) <= 1
            and abs(int(row.get("refocus_peak_count") or 0) - best_refocus) <= 1
        )

    def within_retention(row: dict[str, Any]) -> bool:
        return row.get("variant") != best_variant and float(row.get("tail_shell_retention") or 0.0) >= 0.90 * best_retention

    def outer_clean(row: dict[str, Any]) -> bool:
        return row.get("variant") != best_variant and float(row.get("tail_outer_to_shell_mean") or 999.0) < options.strict_outer_shell_target

    exact_top = [row for row in same_family_rows if int(row.get("major_shell_peak_count") or 0) == best_major and int(row.get("refocus_peak_count") or 0) == best_refocus]
    within_one_rows = [row for row in same_family_rows if within_one(row)]
    retention_rows = [row for row in same_family_rows if within_retention(row)]
    outer_rows = [row for row in same_family_rows if outer_clean(row)]
    immediate_neighbors = _immediate_neighbors(same_family_rows, best_index)
    immediate_close = [
        row
        for row in immediate_neighbors
        if within_one(row)
        and within_retention(row)
        and float(row.get("tail_outer_to_shell_mean") or 999.0) < options.strict_outer_shell_target
        and not bool(row.get("shell_exit_detected"))
        and not bool(row.get("global_peak_in_outer_window"))
    ]
    exact_neighbor_count = max(0, len(exact_top) - 1)
    exact_top_offsets = _row_offsets(exact_top)
    exact_top_cutoff_width = max(exact_top_offsets) - min(exact_top_offsets) if len(exact_top_offsets) >= 2 else 0.0
    if exact_neighbor_count >= 2 and exact_top_cutoff_width >= 0.025:
        label = "broad"
        reason = "The optimum count is reproduced across a comparatively broad cutoff span."
    elif exact_neighbor_count >= 1:
        label = "narrow"
        reason = "The optimum count is reproduced by neighboring cutoff samples, but only across a narrow cutoff span."
    elif immediate_close:
        label = "narrow"
        reason = "The exact optimum is single-point, but nearest neighbors stay within one peak/refocus, within 10% retention, and outer/shell below 1.0."
    else:
        label = "single_point_isolated"
        reason = "The nearest neighbors do not stay close enough to the best peak/refocus count and retention guards."
    return {
        "label": label,
        "reason": reason,
        "best_variant": best.get("variant"),
        "best_cutoff": best.get("drive_cutoff_time"),
        "best_release_phase": best.get("cutoff_phase_cycles"),
        "best_major_shell_peak_count": best_major,
        "best_refocus_peak_count": best_refocus,
        "best_retention": best_retention,
        "best_outer_shell": best.get("tail_outer_to_shell_mean"),
        "tested_cutoff_offsets": _row_offsets(same_family_rows),
        "exact_top_cutoff_width": exact_top_cutoff_width,
        "exact_top_neighbors": _row_refs([row for row in exact_top if row.get("variant") != best_variant]),
        "neighboring_within_one_peak_refocus": _row_refs(within_one_rows),
        "neighboring_within_10pct_retention": _row_refs(retention_rows),
        "neighboring_outer_below_1": _row_refs(outer_rows),
        "immediate_close_neighbors": _row_refs(immediate_close),
    }


def _immediate_neighbors(rows: list[dict[str, Any]], index: int | None) -> list[dict[str, Any]]:
    if index is None:
        return []
    neighbors = []
    if index > 0:
        neighbors.append(rows[index - 1])
    if index < len(rows) - 1:
        neighbors.append(rows[index + 1])
    return neighbors


def _row_refs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "variant": row.get("variant"),
            "cutoff": row.get("drive_cutoff_time"),
            "release_phase": row.get("cutoff_phase_cycles"),
            "major_peaks": row.get("major_shell_peak_count"),
            "refocus_peaks": row.get("refocus_peak_count"),
            "retention": row.get("tail_shell_retention"),
            "outer_shell": row.get("tail_outer_to_shell_mean"),
        }
        for row in rows
    ]


def _row_offsets(rows: list[dict[str, Any]]) -> list[float]:
    return [
        round(float(row.get("cutoff_offset_from_center") or 0.0), 12)
        for row in rows
        if row.get("cutoff_offset_from_center") is not None
    ]


def event_threshold_sensitivity_audit(
    rows: list[dict[str, Any]],
    timeseries_rows: list[dict[str, Any]],
    options: CutoffPhaseMap3DOptions | None = None,
) -> list[dict[str, Any]]:
    """Recount lifecycle peaks for the best row and nearest neighbors across event thresholds."""

    options = options or CutoffPhaseMap3DOptions()
    if not rows or not timeseries_rows:
        return []
    ranked = _ranked_rows(rows)
    best = ranked[0]
    same_family_rows = sorted(
        [
            row
            for row in rows
            if row.get("family") == best.get("family")
            and row.get("axis_label") == best.get("axis_label")
            and row.get("cutoff_offset_from_center") is not None
        ],
        key=lambda row: float(row.get("cutoff_offset_from_center") or 0.0),
    )
    best_index = next((index for index, row in enumerate(same_family_rows) if row.get("variant") == best.get("variant")), None)
    neighbors = _immediate_neighbors(same_family_rows, best_index)
    target_rows = [*(neighbors[:1]), best, *(neighbors[1:])]
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in timeseries_rows:
        by_variant.setdefault(str(row.get("variant")), []).append(row)
    peak_thresholds = _threshold_values(options.peak_threshold_fraction, 0.05, minimum=0.05)
    refocus_thresholds = _threshold_values(options.refocus_threshold_fraction, 0.05, minimum=0.05)
    audit_rows: list[dict[str, Any]] = []
    for target in target_rows:
        variant = str(target.get("variant"))
        series = sorted(by_variant.get(variant, []), key=lambda item: float(item.get("time") or 0.0))
        if not series:
            continue
        times = np.asarray([row["time"] for row in series], dtype=float)
        shell = np.asarray([row["shell_window_energy"] for row in series], dtype=float)
        post_indices = np.flatnonzero(times > float(target.get("drive_cutoff_time") or 0.0))
        baseline_major = int(target.get("major_shell_peak_count") or 0)
        baseline_refocus = int(target.get("refocus_peak_count") or 0)
        relation = "best" if target is best else ("lower_neighbor" if float(target.get("cutoff_offset_from_center") or 0.0) < float(best.get("cutoff_offset_from_center") or 0.0) else "upper_neighbor")
        for peak_threshold in peak_thresholds:
            for refocus_threshold in refocus_thresholds:
                threshold_options = replace(
                    options,
                    peak_threshold_fraction=peak_threshold,
                    refocus_threshold_fraction=refocus_threshold,
                )
                peaks = _major_peaks(times, shell, post_indices, threshold_options)
                refocus_count = _refocus_count(peaks, refocus_threshold)
                major_count = len(peaks)
                audit_rows.append(
                    {
                        "variant": variant,
                        "relation_to_best": relation,
                        "drive_cutoff_time": target.get("drive_cutoff_time"),
                        "cutoff_phase_cycles": target.get("cutoff_phase_cycles"),
                        "peak_threshold_fraction": peak_threshold,
                        "refocus_threshold_fraction": refocus_threshold,
                        "major_shell_peak_count": major_count,
                        "refocus_peak_count": refocus_count,
                        "baseline_major_shell_peak_count": baseline_major,
                        "baseline_refocus_peak_count": baseline_refocus,
                        "matches_baseline_counts": major_count == baseline_major and refocus_count == baseline_refocus,
                        "within_one_of_baseline": abs(major_count - baseline_major) <= 1 and abs(refocus_count - baseline_refocus) <= 1,
                    }
                )
    return audit_rows


def summarize_event_threshold_sensitivity(audit_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not audit_rows:
        return {"label": "not_computed", "reason": "No event-threshold sensitivity rows were available.", "variants": []}
    summaries = []
    for variant in _unique_variants(audit_rows):
        rows = [row for row in audit_rows if row.get("variant") == variant]
        match_count = sum(1 for row in rows if row.get("matches_baseline_counts"))
        within_one_count = sum(1 for row in rows if row.get("within_one_of_baseline"))
        major_counts = [int(row.get("major_shell_peak_count") or 0) for row in rows]
        refocus_counts = [int(row.get("refocus_peak_count") or 0) for row in rows]
        summaries.append(
            {
                "variant": variant,
                "relation_to_best": rows[0].get("relation_to_best"),
                "baseline_major_shell_peak_count": rows[0].get("baseline_major_shell_peak_count"),
                "baseline_refocus_peak_count": rows[0].get("baseline_refocus_peak_count"),
                "scenario_count": len(rows),
                "matching_scenario_count": match_count,
                "within_one_scenario_count": within_one_count,
                "major_peak_count_range": [min(major_counts), max(major_counts)],
                "refocus_peak_count_range": [min(refocus_counts), max(refocus_counts)],
            }
        )
    best_summary = next((row for row in summaries if row.get("relation_to_best") == "best"), summaries[0])
    if best_summary["matching_scenario_count"] == best_summary["scenario_count"]:
        label = "best_count_threshold_robust"
        reason = "The best row keeps the same major/refocus counts across all tested peak and refocus thresholds."
    elif best_summary["within_one_scenario_count"] == best_summary["scenario_count"]:
        label = "best_count_threshold_sensitive_within_one"
        reason = "The best row shifts under thresholds, but all tested counts remain within one peak/refocus of baseline."
    else:
        label = "best_count_threshold_sensitive"
        reason = "The best row's peak/refocus counts change by more than one under tested event thresholds."
    return {"label": label, "reason": reason, "variants": summaries}


def _threshold_values(center: float, delta: float, *, minimum: float) -> list[float]:
    return _unique_sorted([max(minimum, center - delta), center, center + delta])


def _refocus_count(peaks: list[dict[str, Any]], refocus_threshold_fraction: float) -> int:
    if len(peaks) <= 1:
        return 0
    first_peak_energy = max(float(peaks[0].get("energy") or 0.0), EPSILON)
    threshold = refocus_threshold_fraction * first_peak_energy
    return sum(1 for peak in peaks[1:] if float(peak.get("energy") or 0.0) >= threshold)


def _unique_variants(rows: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        variant = str(row.get("variant"))
        if variant not in seen:
            seen.append(variant)
    return seen


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(_ranked_rows(rows)[0].get("variant", "n/a"))


def _ranked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for rank, row in enumerate(sorted(rows, key=_rank_key, reverse=True), start=1):
        ranked.append(
            {
                "rank": rank,
                "outer_shell_below_1": float(row.get("tail_outer_to_shell_mean") or 999.0) < 1.0,
                **row,
            }
        )
    return ranked


def _rank_key(row: dict[str, Any]) -> tuple[float, ...]:
    decay = float(row.get("post_cutoff_shell_decay_rate") or 0.0)
    return (
        float(row.get("major_shell_peak_count") or 0.0),
        float(row.get("refocus_peak_count") or 0.0),
        0.0 if bool(row.get("shell_exit_detected")) else 1.0,
        float(row.get("tail_shell_retention") or 0.0),
        1.0 if float(row.get("tail_outer_to_shell_mean") or 999.0) < 1.0 else 0.0,
        -abs(decay),
        0.0 if bool(row.get("global_peak_in_outer_window")) else 1.0,
    )


def release_phase_island_stability(
    rows: list[dict[str, Any]],
    options: CutoffPhaseMap3DOptions | None = None,
) -> dict[str, Any]:
    """Check whether the best release-phase rows are neighboring cutoff samples."""

    options = options or CutoffPhaseMap3DOptions()
    if not rows:
        return {
            "label": "no_rows",
            "is_stable": False,
            "reason": "No cutoff-phase rows were available.",
            "candidate_variants": [],
            "candidate_offsets": [],
            "neighboring_offset_pairs": [],
        }
    ranked = _ranked_rows(rows)
    best = ranked[0]
    best_family = best.get("family")
    best_axis = best.get("axis_label")
    best_major = int(best.get("major_shell_peak_count") or 0)
    best_refocus = int(best.get("refocus_peak_count") or 0)
    best_retention = float(best.get("tail_shell_retention") or 0.0)
    retention_floor = max(options.strict_retention_target, 0.90 * best_retention)

    same_family_rows = [
        row
        for row in rows
        if row.get("family") == best_family and row.get("axis_label") == best_axis
    ]
    candidate_rows = [
        row
        for row in same_family_rows
        if int(row.get("major_shell_peak_count") or 0) == best_major
        and int(row.get("refocus_peak_count") or 0) == best_refocus
        and not bool(row.get("shell_exit_detected"))
        and not bool(row.get("global_peak_in_outer_window"))
        and float(row.get("tail_shell_retention") or 0.0) >= retention_floor
        and float(row.get("tail_outer_to_shell_mean") or 999.0) <= options.strict_outer_shell_target
    ]
    tested_offsets = _unique_sorted(
        row.get("cutoff_offset_from_center")
        for row in same_family_rows
        if row.get("cutoff_offset_from_center") is not None
    )
    candidate_offsets = _unique_sorted(row.get("cutoff_offset_from_center") for row in candidate_rows)
    best_offset = best.get("cutoff_offset_from_center")
    offset_index = {offset: index for index, offset in enumerate(tested_offsets)}
    neighboring_pairs: list[list[float]] = []
    for left, right in zip(candidate_offsets, candidate_offsets[1:]):
        if abs(offset_index.get(right, -99) - offset_index.get(left, 99)) == 1:
            neighboring_pairs.append([left, right])
    best_has_neighbor = any(best_offset in pair for pair in neighboring_pairs)
    if neighboring_pairs and best_has_neighbor:
        return {
            "label": "neighboring_cluster_supported",
            "is_stable": True,
            "reason": "The best-quality rows include neighboring cutoff offsets in the same family, so the best point is not isolated.",
            "best_variant": best.get("variant"),
            "best_family": best_family,
            "best_axis": best_axis,
            "best_cutoff_offset_from_center": best_offset,
            "tested_offsets": tested_offsets,
            "candidate_variants": [row.get("variant") for row in sorted(candidate_rows, key=_rank_key, reverse=True)],
            "candidate_offsets": candidate_offsets,
            "neighboring_offset_pairs": neighboring_pairs,
            "retention_floor": retention_floor,
        }
    if len(candidate_offsets) > 1:
        reason = "Best-quality rows exist at multiple cutoff offsets, but the winning point lacks a neighboring best-quality sample."
        label = "cluster_away_from_best"
    elif candidate_offsets:
        reason = "Only one best-quality cutoff sample met the strict neighboring-cluster guards."
        label = "single_point_best"
    else:
        reason = "No row met the strict best-quality guards for a release-phase cluster."
        label = "no_best_quality_cluster"
    return {
        "label": label,
        "is_stable": False,
        "reason": reason,
        "best_variant": best.get("variant"),
        "best_family": best_family,
        "best_axis": best_axis,
        "best_cutoff_offset_from_center": best_offset,
        "tested_offsets": tested_offsets,
        "candidate_variants": [row.get("variant") for row in sorted(candidate_rows, key=_rank_key, reverse=True)],
        "candidate_offsets": candidate_offsets,
        "neighboring_offset_pairs": neighboring_pairs,
        "retention_floor": retention_floor,
    }


def _unique_sorted(values: Any) -> list[float]:
    return sorted({round(float(value), 12) for value in values if value is not None})


def _cutoff_phase_cycles(config: Prototype3DConfig) -> float:
    return (float(config.drive_frequency) * float(config.drive_cutoff_time) + float(config.boundary_phase_offset) / (2.0 * math.pi)) % 1.0


def _cutoff_center(base: SimulationConfig, options: CutoffPhaseMap3DOptions) -> float:
    return options.cutoff_center if options.cutoff_center is not None else float(base.driver.drive_cutoff_time) + options.cutoff_delta


def _cutoff_center_from_config(config: Prototype3DConfig, options: CutoffPhaseMap3DOptions) -> float:
    if options.cutoff_center is not None:
        return options.cutoff_center
    return float(config.drive_cutoff_time) - float(getattr(config, "_cutoff_offset", 0.0))


def _phase_label(value: float) -> str:
    return f"{value / math.pi:+.4f}pi"


def _name(prefix: str, value: float) -> str:
    sign = "plus" if value > 0 else "minus"
    safe = str(abs(value)).replace(".", "p")
    return f"{prefix}_{sign}_{safe}"


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: CutoffPhaseMap3DOptions,
    needle_width: dict[str, Any] | None = None,
    threshold_sensitivity: dict[str, Any] | None = None,
    threshold_sensitivity_rows: list[dict[str, Any]] | None = None,
) -> None:
    lines = [
        f"# 3D Cutoff Phase Timing Map: {control_id}",
        "",
        "## Purpose",
        "",
        "Tiny timing map asking whether retained refocusing clusters around a source release phase.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Ranked Results",
        "",
        "Ranking priority: major shell-window peaks, refocus peaks, no shell exit, retention, outer/shell below 1.0, decay rate closest to zero, global outer flag false.",
        "",
        "| Rank | Variant | Family | Cutoff | Phase At Cutoff | Peaks | Refocus | Exit | Ret | Outer/Shell | <1.0 | Decay | Global Outer |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | ---: | --- |",
    ]
    for row in _ranked_rows(rows):
        exit_label = "false" if not bool(row.get("shell_exit_detected")) else _format(row.get("shell_exit_time"))
        lines.append(
            "| "
            f"{row['rank']} | "
            f"{row['variant']} | "
            f"{row.get('family')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{row.get('major_shell_peak_count')} | "
            f"{row.get('refocus_peak_count')} | "
            f"{exit_label} | "
            f"{_format(row.get('tail_shell_retention'))} | "
            f"{_format(row.get('tail_outer_to_shell_mean'))} | "
            f"{row.get('outer_shell_below_1')} | "
            f"{_format(row.get('post_cutoff_shell_decay_rate'))} | "
            f"{row.get('global_peak_in_outer_window')} |"
        )
    lines.extend(
        [
            "",
        "## Variant Summary",
        "",
        "| Variant | Family | Axis | Cutoff | Phase At Cutoff | Phase Offset | Peaks | Refocus | Exit | Ret | Outer/Shell | Decay | Global Outer |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        exit_label = "false" if not bool(row.get("shell_exit_detected")) else _format(row.get("shell_exit_time"))
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('family')} | "
            f"{row.get('axis_label')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{row.get('phase_offset_label')} | "
            f"{row.get('major_shell_peak_count')} | "
            f"{row.get('refocus_peak_count')} | "
            f"{exit_label} | "
            f"{_format(row.get('tail_shell_retention'))} | "
            f"{_format(row.get('tail_outer_to_shell_mean'))} | "
            f"{_format(row.get('post_cutoff_shell_decay_rate'))} | "
            f"{row.get('global_peak_in_outer_window')} |"
        )
    lines.extend(
        [
            "",
            "## release phase island stability",
            "",
            *_stability_lines(classification.get("release_phase_island_stability", {}), rows),
            "",
            "## phase-lock needle width",
            "",
            *_needle_width_lines(needle_width or phase_lock_needle_width(rows, options)),
            "",
            "## event-threshold sensitivity audit",
            "",
            *_threshold_sensitivity_lines(threshold_sensitivity or {}, threshold_sensitivity_rows or []),
            "",
            "## Interpretation",
            "",
            _interpretation(classification, needle_width or {}, threshold_sensitivity or {}),
            "",
            "## Files",
            "",
            "- `cutoff_phase_map_summary.csv`",
            "- `cutoff_phase_ranked_summary.csv`",
            "- `cutoff_phase_event_threshold_sensitivity.csv`",
            "- `cutoff_phase_map_timeseries.csv`",
            "- `cutoff_phase_map_events.csv`",
            "- `cutoff_phase_shell_energy_plot.png`",
            "- `cutoff_phase_radius_width_plot.png`",
            "- `cutoff_phase_flux_balance_plot.png`",
            "",
            "## Next Step",
            "",
            _next_step(classification, needle_width or {}, threshold_sensitivity or {}),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(
    classification: dict[str, Any],
    needle_width: dict[str, Any] | None = None,
    threshold_sensitivity: dict[str, Any] | None = None,
) -> str:
    label = classification["label"]
    if label == "cutoff_phase_timing_island_supported":
        if (needle_width or {}).get("label") == "narrow" or "sensitive" in str((threshold_sensitivity or {}).get("label", "")):
            return "Refocusing is release-phase sensitive, but the current optimum should be described as a narrow phase-lock needle until event-threshold robustness improves."
        return "Refocusing appears release-phase sensitive, with strong clean rows forming a neighboring cutoff cluster. This supports passive timing-engineered refocusing."
    if label == "cutoff_phase_single_point_best":
        return "A strong passive release-phase row exists, but this report treats it as an isolated point until neighboring cutoffs reproduce the top behavior."
    if label == "cutoff_timing_improved":
        return "A nearby cutoff timing improves the reference, but the strict phase-island criteria are not yet met."
    if label == "polarity_family_sensitive":
        return "The polarity/sign-flip family changes the response, but this control did not improve the phase-offset cutoff reference."
    if label == "cutoff_phase_tolerant_no_improvement":
        return "Nearby cutoff phases are tolerated, but no better timing island emerged in this tiny map."
    return "The cutoff phase map is inconclusive; inspect the event table before adding variants."


def _next_step(
    classification: dict[str, Any],
    needle_width: dict[str, Any] | None = None,
    threshold_sensitivity: dict[str, Any] | None = None,
) -> str:
    label = classification["label"]
    if label == "cutoff_phase_timing_island_supported":
        if (needle_width or {}).get("label") == "narrow" or "sensitive" in str((threshold_sensitivity or {}).get("label", "")):
            return "Audit the shell-event traces and peak-detection thresholds around the narrow passive needle before claiming a robust 11/10 timing island; keep active second pulses shelved."
        return "Use the neighboring passive release-phase cluster as the reference for any next passive cutoff-only check; keep active second pulses shelved unless a new mechanism changes the premise."
    if label == "cutoff_phase_single_point_best":
        return "Run a tighter passive cutoff-only refinement around the isolated best point before treating it as a stable island."
    if label == "cutoff_timing_improved":
        return "Run one narrower cutoff-only map around the best timing row."
    if label == "polarity_family_sensitive":
        return "Run a tiny polarity-only control around the best family before adding rotation or medium changes."
    return "Hold the current cutoff_long reference and inspect phase/flux traces before expanding controls."


def _stability_lines(stability: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    if not stability:
        return ["- Result: `not_computed`", "- Reason: release-phase island stability was not computed."]
    lines = [
        f"- Result: `{stability.get('label')}`",
        f"- Reason: {stability.get('reason')}",
        f"- Best family/axis: `{stability.get('best_family')}` / `{stability.get('best_axis')}`",
        f"- Best cutoff offset: `{_format(stability.get('best_cutoff_offset_from_center'))}`",
        f"- Candidate offsets: `{_format_sequence(stability.get('candidate_offsets', []))}`",
        f"- Neighboring pairs: `{_format_pairs(stability.get('neighboring_offset_pairs', []))}`",
        "",
        "| Candidate Variant | Cutoff Offset | Cutoff | Phase At Cutoff | Peaks | Refocus | Ret | Outer/Shell |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    by_variant = {row.get("variant"): row for row in rows}
    for variant in stability.get("candidate_variants", []):
        row = by_variant.get(variant)
        if row is None:
            continue
        lines.append(
            "| "
            f"{variant} | "
            f"{_format(row.get('cutoff_offset_from_center'))} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{row.get('major_shell_peak_count')} | "
            f"{row.get('refocus_peak_count')} | "
            f"{_format(row.get('tail_shell_retention'))} | "
            f"{_format(row.get('tail_outer_to_shell_mean'))} |"
        )
    if not stability.get("candidate_variants"):
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
    return lines


def _format_sequence(values: list[Any]) -> str:
    if not values:
        return "n/a"
    return ", ".join(_format(value) for value in values)


def _format_pairs(values: list[list[Any]]) -> str:
    if not values:
        return "n/a"
    return "; ".join(f"{_format(pair[0])}, {_format(pair[1])}" for pair in values if len(pair) == 2)


def _needle_width_lines(needle_width: dict[str, Any]) -> list[str]:
    return [
        f"- Result: `{needle_width.get('label', 'not_computed')}`",
        f"- Reason: {needle_width.get('reason', 'n/a')}",
        f"- Best cutoff: `{_format(needle_width.get('best_cutoff'))}`",
        f"- Best release phase: `{_format(needle_width.get('best_release_phase'))}`",
        f"- Exact-top cutoff width: `{_format(needle_width.get('exact_top_cutoff_width'))}`",
        f"- Neighboring rows within 1 peak / 1 refocus peak: `{_format_ref_list(needle_width.get('neighboring_within_one_peak_refocus', []))}`",
        f"- Neighboring rows within 10% retention: `{_format_ref_list(needle_width.get('neighboring_within_10pct_retention', []))}`",
        f"- Neighboring rows with outer/shell below 1.0: `{_format_ref_list(needle_width.get('neighboring_outer_below_1', []))}`",
    ]


def _format_ref_list(values: list[dict[str, Any]]) -> str:
    if not values:
        return "n/a"
    return ", ".join(
        f"{item.get('variant')}@{_format(item.get('cutoff'))}"
        for item in values
    )


def _threshold_sensitivity_lines(
    threshold_sensitivity: dict[str, Any],
    threshold_sensitivity_rows: list[dict[str, Any]],
) -> list[str]:
    if not threshold_sensitivity:
        return ["- Result: `not_computed`", "- Reason: event-threshold sensitivity was not computed."]
    lines = [
        f"- Result: `{threshold_sensitivity.get('label')}`",
        f"- Reason: {threshold_sensitivity.get('reason')}",
        "",
        "| Variant | Relation | Baseline Peaks | Baseline Refocus | Match Scenarios | Within-One Scenarios | Peak Range | Refocus Range |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for summary in threshold_sensitivity.get("variants", []):
        lines.append(
            "| "
            f"{summary.get('variant')} | "
            f"{summary.get('relation_to_best')} | "
            f"{summary.get('baseline_major_shell_peak_count')} | "
            f"{summary.get('baseline_refocus_peak_count')} | "
            f"{summary.get('matching_scenario_count')}/{summary.get('scenario_count')} | "
            f"{summary.get('within_one_scenario_count')}/{summary.get('scenario_count')} | "
            f"{_format_range(summary.get('major_peak_count_range'))} | "
            f"{_format_range(summary.get('refocus_peak_count_range'))} |"
        )
    best_rows = [row for row in threshold_sensitivity_rows if row.get("relation_to_best") == "best"]
    if best_rows:
        lines.extend(
            [
                "",
                "| Best Variant Peak Threshold | Refocus Threshold | Peaks | Refocus | Matches Baseline |",
                "| ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for row in best_rows:
            lines.append(
                "| "
                f"{_format(row.get('peak_threshold_fraction'))} | "
                f"{_format(row.get('refocus_threshold_fraction'))} | "
                f"{row.get('major_shell_peak_count')} | "
                f"{row.get('refocus_peak_count')} | "
                f"{row.get('matches_baseline_counts')} |"
            )
    return lines


def _format_range(value: Any) -> str:
    if not value or len(value) != 2:
        return "n/a"
    return f"{value[0]}-{value[1]}"


def _summary_fields() -> list[str]:
    base_fields = [
        field
        for field in _engineering_summary_fields()
        if field not in {"variant", "refocusing_engineering_classification", "axis_label", "refocusing_role"}
    ]
    return [
        "variant",
        "cutoff_phase_map_classification",
        "family",
        "axis_label",
        "cutoff_center",
        "cutoff_offset_from_center",
        "phase_delta",
        "boundary_cubic_phase_sign",
        "cutoff_phase_cycles",
        "cutoff_phase_radians",
        "cutoff_phase_label",
        *base_fields,
    ]


def _ranked_fields() -> list[str]:
    return [
        "rank",
        "variant",
        "family",
        "axis_label",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "cutoff_phase_radians",
        "phase_offset_label",
        "major_shell_peak_count",
        "refocus_peak_count",
        "shell_exit_detected",
        "shell_exit_time",
        "tail_shell_retention",
        "tail_outer_to_shell_mean",
        "outer_shell_below_1",
        "post_cutoff_shell_decay_rate",
        "global_peak_in_outer_window",
        "cutoff_phase_map_classification",
    ]


def _threshold_sensitivity_fields() -> list[str]:
    return [
        "variant",
        "relation_to_best",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "peak_threshold_fraction",
        "refocus_threshold_fraction",
        "major_shell_peak_count",
        "refocus_peak_count",
        "baseline_major_shell_peak_count",
        "baseline_refocus_peak_count",
        "matches_baseline_counts",
        "within_one_of_baseline",
    ]
