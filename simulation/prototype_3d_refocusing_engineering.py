"""Tiny 3D refocusing-engineering control for the cubic transport packet."""

from __future__ import annotations

from dataclasses import dataclass
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
    PacketLifecycle3DOptions,
    _event_fields,
    _plot_flux,
    _plot_lifecycle,
    _plot_radius_width,
    _run_lifecycle_variant,
    _timeseries_fields,
)
from .prototype_3d_source_sponge import _effective_source_area, _format, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


@dataclass(frozen=True)
class RefocusingEngineering3DOptions:
    """Options for a tiny refocusing-engineering control."""

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
    phase_delta: float = float(np.pi) / 16.0
    cutoff_delta: float = 2.0
    frequency_delta: float = 0.02
    include_chirp: bool = True
    arrival_threshold_fraction: float = 0.10
    exit_threshold_fraction: float = 0.12
    exit_hold_samples: int = 10
    peak_threshold_fraction: float = 0.30
    refocus_threshold_fraction: float = 0.35
    min_peak_separation_time: float = 5.0
    min_refocus_count: int = 2
    min_width_growth_fraction: float = 0.30
    min_decay_rate_magnitude: float = 0.01
    min_retention_ratio: float = 0.80
    max_outer_shell_ratio: float = 2.25
    min_refocus_ratio_improvement: float = 0.05
    min_exit_delay: float = 2.0


def run_3d_refocusing_engineering_control(
    base_config: SimulationConfig,
    *,
    options: RefocusingEngineering3DOptions | None = None,
) -> dict[str, Any]:
    """Run one-axis phase/cutoff/frequency controls scored by lifecycle refocusing metrics."""

    options = options or RefocusingEngineering3DOptions()
    control_id = datetime.now().strftime("refocusing_engineering_3d_%Y%m%d_%H%M%S")
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

    classification = classify_refocusing_engineering(rows, options)
    reference = _reference_row(rows)
    for row in rows:
        row.update(_comparison_fields(row, reference))
        row["refocusing_engineering_classification"] = classification["label"]

    summary_csv = root / "refocusing_engineering_summary.csv"
    timeseries_csv = root / "refocusing_engineering_timeseries.csv"
    events_csv = root / "refocusing_engineering_events.csv"
    report_path = root / "refocusing_engineering_3d_report.md"
    _write_csv(summary_csv, rows, _summary_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(events_csv, event_rows, _event_fields())
    _plot_lifecycle(root / "refocusing_shell_energy_plot.png", timeseries_rows, event_rows)
    _plot_radius_width(root / "refocusing_radius_width_plot.png", timeseries_rows)
    _plot_flux(root / "refocusing_flux_balance_plot.png", timeseries_rows)
    _write_report(report_path, control_id, rows, classification, options)
    save_json(
        root / "refocusing_engineering_3d_summary.json",
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


def classify_refocusing_engineering(
    rows: list[dict[str, Any]],
    options: RefocusingEngineering3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether one-axis phase/cutoff/frequency changes improved refocusing."""

    options = options or RefocusingEngineering3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No refocusing-engineering rows were available.", "checks": {}}
    reference = _reference_row(rows)
    checks = {row["variant"]: _row_checks(row, reference, options) for row in rows}
    improvements = [row for row in rows if _is_improvement(row, reference, options)]
    clean = [row for row in rows if _is_clean(row, reference, options)]
    if improvements:
        best = _best_variant(improvements)
        return {
            "label": "refocusing_improved",
            "reason": f"At least one tiny phase/cutoff/frequency variant improved refocusing without violating contamination or retention guards. Best: {best}.",
            "best_variant": best,
            "checks": checks,
        }
    if len(clean) > 1:
        return {
            "label": "refocusing_tolerant_no_improvement",
            "reason": "Several variants remained clean, but none improved refocus count, late return strength, exit delay, or decay enough to beat the phase-offset reference.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "refocusing_sensitive_or_inconclusive",
        "reason": "The tiny variants either degraded refocusing or did not stay clean enough for interpretation.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: RefocusingEngineering3DOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    base_frequency = float(base.driver.frequency)
    base_cutoff = float(base.driver.drive_cutoff_time)
    variants = [
        _boundary_config("sign_flip_reference", base, options, source_width, phase_offset=0.0, role="sign_flip_reference"),
        _boundary_config("phase_offset_reference", base, options, source_width, phase_offset=options.phase_offset, role="phase_reference"),
        _boundary_config(
            "phase_offset_minus_delta",
            base,
            options,
            source_width,
            phase_offset=options.phase_offset - options.phase_delta,
            role="phase_offset",
        ),
        _boundary_config(
            "phase_offset_plus_delta",
            base,
            options,
            source_width,
            phase_offset=options.phase_offset + options.phase_delta,
            role="phase_offset",
        ),
        _boundary_config(
            "cutoff_short",
            base,
            options,
            source_width,
            phase_offset=options.phase_offset,
            cutoff=max(1.0, base_cutoff - options.cutoff_delta),
            role="cutoff",
        ),
        _boundary_config(
            "cutoff_long",
            base,
            options,
            source_width,
            phase_offset=options.phase_offset,
            cutoff=base_cutoff + options.cutoff_delta,
            role="cutoff",
        ),
        _boundary_config(
            "frequency_low",
            base,
            options,
            source_width,
            phase_offset=options.phase_offset,
            frequency=max(0.01, base_frequency - options.frequency_delta),
            role="frequency",
        ),
        _boundary_config(
            "frequency_high",
            base,
            options,
            source_width,
            phase_offset=options.phase_offset,
            frequency=base_frequency + options.frequency_delta,
            role="frequency",
        ),
    ]
    if options.include_chirp:
        chirp = _boundary_config(
            "chirp_low_to_high",
            base,
            options,
            source_width,
            phase_offset=options.phase_offset,
            role="chirp",
        )
        chirp.drive_mode = "chirp"
        chirp.drive_chirp_start_frequency = max(0.01, base_frequency - options.frequency_delta)
        chirp.drive_chirp_end_frequency = base_frequency + options.frequency_delta
        variants.append(chirp)
    return variants


def _boundary_config(
    name: str,
    base: SimulationConfig,
    options: RefocusingEngineering3DOptions,
    source_width: float,
    *,
    phase_offset: float,
    role: str,
    cutoff: float | None = None,
    frequency: float | None = None,
) -> Prototype3DConfig:
    config = _interference_boundary_config(name, base, _lifecycle_options(options), source_width, "cubic", cubic_sign=-1.0, phase_offset=phase_offset)
    if cutoff is not None:
        config.drive_cutoff_time = cutoff
    if frequency is not None:
        config.drive_frequency = frequency
    config.name = name
    setattr(config, "_refocusing_role", role)
    return config


def _lifecycle_options(options: RefocusingEngineering3DOptions) -> PacketLifecycle3DOptions:
    return PacketLifecycle3DOptions(
        output_root=options.output_root,
        grid_size=options.grid_size,
        reference_source_grid_size=options.reference_source_grid_size,
        physical_duration=options.physical_duration,
        sample_every=options.sample_every,
        diagnostic_sample_every=options.diagnostic_sample_every,
        radial_bins=options.radial_bins,
        shell_window_radius=options.shell_window_radius,
        shell_window_width=options.shell_window_width,
        near_shell_width_dx=options.near_shell_width_dx,
        sponge_strength_multiplier=options.sponge_strength_multiplier,
        target_work_per_source_area=options.target_work_per_source_area,
        phase_offset=options.phase_offset,
        arrival_threshold_fraction=options.arrival_threshold_fraction,
        exit_threshold_fraction=options.exit_threshold_fraction,
        exit_hold_samples=options.exit_hold_samples,
        peak_threshold_fraction=options.peak_threshold_fraction,
        refocus_threshold_fraction=options.refocus_threshold_fraction,
        min_peak_separation_time=options.min_peak_separation_time,
        min_refocus_count=options.min_refocus_count,
        min_width_growth_fraction=options.min_width_growth_fraction,
        min_decay_rate_magnitude=options.min_decay_rate_magnitude,
    )


def _add_control_fields(
    row: dict[str, Any],
    config: Prototype3DConfig,
    options: RefocusingEngineering3DOptions,
    target_work_per_area: float,
) -> None:
    row["refocusing_role"] = getattr(config, "_refocusing_role", "variant")
    row["target_reference_work_per_source_area"] = target_work_per_area
    row["drive_mode"] = config.drive_mode
    row["drive_frequency"] = config.drive_frequency
    row["drive_cutoff_time"] = config.drive_cutoff_time
    row["boundary_phase_offset"] = config.boundary_phase_offset
    row["phase_offset_label"] = _phase_label(config.boundary_phase_offset)
    row["drive_chirp_start_frequency"] = config.drive_chirp_start_frequency
    row["drive_chirp_end_frequency"] = config.drive_chirp_end_frequency
    row["axis_label"] = row["refocusing_role"]


def _reference_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("variant") == "phase_offset_reference"), rows[0] if rows else None)


def _comparison_fields(row: dict[str, Any], reference: dict[str, Any] | None) -> dict[str, Any]:
    if reference is None:
        return {}
    return {
        "delta_refocus_peak_count": int(row.get("refocus_peak_count") or 0) - int(reference.get("refocus_peak_count") or 0),
        "delta_major_shell_peak_count": int(row.get("major_shell_peak_count") or 0) - int(reference.get("major_shell_peak_count") or 0),
        "delta_exit_time": _delta(row.get("shell_exit_time"), reference.get("shell_exit_time")),
        "refocus_ratio_lift": _ratio(row.get("refocus_peak_ratio_max"), reference.get("refocus_peak_ratio_max")),
        "retention_lift": _ratio(row.get("tail_shell_retention"), reference.get("tail_shell_retention")),
        "decay_rate_delta": _delta(row.get("post_cutoff_shell_decay_rate"), reference.get("post_cutoff_shell_decay_rate")),
        "outer_shell_ratio_delta": _delta(row.get("tail_outer_to_shell_mean"), reference.get("tail_outer_to_shell_mean")),
    }


def _row_checks(row: dict[str, Any], reference: dict[str, Any] | None, options: RefocusingEngineering3DOptions) -> dict[str, Any]:
    return {
        **_comparison_fields(row, reference),
        "clean": _is_clean(row, reference, options),
        "improved": _is_improvement(row, reference, options),
        "refocus_peak_count": row.get("refocus_peak_count"),
        "refocus_peak_ratio_max": row.get("refocus_peak_ratio_max"),
        "tail_shell_retention": row.get("tail_shell_retention"),
        "tail_outer_to_shell_mean": row.get("tail_outer_to_shell_mean"),
        "global_peak_in_outer_window": row.get("global_peak_in_outer_window"),
    }


def _is_clean(row: dict[str, Any], reference: dict[str, Any] | None, options: RefocusingEngineering3DOptions) -> bool:
    if row is None:
        return False
    reference_retention = float((reference or {}).get("tail_shell_retention") or 0.0)
    min_retention = options.min_retention_ratio * reference_retention if reference_retention > EPSILON else 0.0
    return (
        float(row.get("tail_shell_retention") or 0.0) >= min_retention
        and float(row.get("tail_outer_to_shell_mean") or 999.0) <= options.max_outer_shell_ratio
        and not bool(row.get("global_peak_in_outer_window"))
    )


def _is_improvement(row: dict[str, Any], reference: dict[str, Any] | None, options: RefocusingEngineering3DOptions) -> bool:
    if reference is None or row is reference or row.get("variant") == reference.get("variant"):
        return False
    if not _is_clean(row, reference, options):
        return False
    ref_count = int(reference.get("refocus_peak_count") or 0)
    count = int(row.get("refocus_peak_count") or 0)
    ref_ratio = float(reference.get("refocus_peak_ratio_max") or 0.0)
    ratio = float(row.get("refocus_peak_ratio_max") or 0.0)
    exit_delta = _delta(row.get("shell_exit_time"), reference.get("shell_exit_time")) or 0.0
    decay_delta = _delta(row.get("post_cutoff_shell_decay_rate"), reference.get("post_cutoff_shell_decay_rate")) or 0.0
    return (
        count > ref_count
        or ratio >= ref_ratio * (1.0 + options.min_refocus_ratio_improvement)
        or exit_delta >= options.min_exit_delay
        or decay_delta > 0.005
    )


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(max(rows, key=_score).get("variant", "n/a"))


def _score(row: dict[str, Any]) -> float:
    refocus = float(row.get("refocus_peak_count") or 0.0)
    ratio = float(row.get("refocus_peak_ratio_max") or 0.0)
    retention = float(row.get("tail_shell_retention") or 0.0)
    outer = max(float(row.get("tail_outer_to_shell_mean") or 999.0), 0.25)
    decay = float(row.get("post_cutoff_shell_decay_rate") or 0.0)
    decay_bonus = 1.0 / (1.0 + max(0.0, -decay))
    clean_bonus = 0.5 if bool(row.get("global_peak_in_outer_window")) else 1.0
    return (1.0 + refocus) * (1.0 + ratio) * (0.25 + retention) * decay_bonus * clean_bonus / outer


def _phase_label(value: float) -> str:
    return f"{value / math.pi:+.4f}pi"


def _ratio(value: Any, reference: Any) -> float | None:
    if value is None or reference is None:
        return None
    return float(value) / (float(reference) + EPSILON)


def _delta(value: Any, reference: Any) -> float | None:
    if value is None or reference is None:
        return None
    return float(value) - float(reference)


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: RefocusingEngineering3DOptions,
) -> None:
    lines = [
        f"# 3D Refocusing Engineering Control: {control_id}",
        "",
        "## Purpose",
        "",
        "Tiny one-axis control for whether boundary phase/cutoff/frequency shaping can improve repeated shell-window refocusing.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Axis | Phase | Cutoff | Freq | Mode | Refocus | Ratio | Exit | Ret | Outer/Shell | Decay | Global Outer |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('axis_label')} | "
            f"{row.get('phase_offset_label')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('drive_frequency'))} | "
            f"{row.get('drive_mode')} | "
            f"{row.get('refocus_peak_count')} | "
            f"{_format(row.get('refocus_peak_ratio_max'))} | "
            f"{_format(row.get('shell_exit_time'))} | "
            f"{_format(row.get('tail_shell_retention'))} | "
            f"{_format(row.get('tail_outer_to_shell_mean'))} | "
            f"{_format(row.get('post_cutoff_shell_decay_rate'))} | "
            f"{row.get('global_peak_in_outer_window')} |"
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
            "- `refocusing_engineering_summary.csv`",
            "- `refocusing_engineering_timeseries.csv`",
            "- `refocusing_engineering_events.csv`",
            "- `refocusing_shell_energy_plot.png`",
            "- `refocusing_radius_width_plot.png`",
            "- `refocusing_flux_balance_plot.png`",
            "",
            "## Next Step",
            "",
            _next_step(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    if classification["label"] == "refocusing_improved":
        return "At least one tiny source-shaping variant improved repeated refocusing without adding outer-window contamination. Continue with a second tiny refinement around that variant."
    if classification["label"] == "refocusing_tolerant_no_improvement":
        return "The packet refocusing family tolerates small source-shaping changes, but this first set did not beat the phase-offset reference."
    return "The first refocusing-engineering controls did not produce a clean improvement; inspect the event ledger before adding variants."


def _next_step(classification: dict[str, Any]) -> str:
    if classification["label"] == "refocusing_improved":
        return "Run a second tiny local refinement around the best variant, varying only its winning axis."
    return "Keep the phase-offset reference as primary and test one narrower phase/cutoff axis next."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "refocusing_engineering_classification",
        "axis_label",
        "refocusing_role",
        "grid_size",
        "dx",
        "dt",
        "physical_duration",
        "drive_mode",
        "drive_frequency",
        "drive_chirp_start_frequency",
        "drive_chirp_end_frequency",
        "drive_cutoff_time",
        "boundary_phase_offset",
        "phase_offset_label",
        "positive_work_before_cutoff",
        "work_per_source_area",
        "target_reference_work_per_source_area",
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
        "delta_refocus_peak_count",
        "delta_major_shell_peak_count",
        "delta_exit_time",
        "refocus_ratio_lift",
        "retention_lift",
        "decay_rate_delta",
        "outer_shell_ratio_delta",
        "global_peak_in_outer_window",
        "packet_width_growth_fraction",
        "post_cutoff_radial_velocity",
        "post_cutoff_shell_decay_rate",
        "post_cutoff_shell_decay_r2",
        "tail_shell_retention",
        "tail_outer_to_shell_mean",
        "inward_flux_fraction",
        "outward_flux_fraction",
        "lifecycle_label",
    ]
