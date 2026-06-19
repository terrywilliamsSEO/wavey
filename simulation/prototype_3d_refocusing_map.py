"""Tiny 3D cutoff-frequency refocusing map for the cubic transport packet."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig, _calibrate_amplitude
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _threshold_like_options
from .prototype_3d_packet_lifecycle import (
    _event_fields,
    _plot_flux,
    _plot_lifecycle,
    _plot_radius_width,
    _run_lifecycle_variant,
    _timeseries_fields,
)
from .prototype_3d_refocusing_engineering import (
    RefocusingEngineering3DOptions,
    _add_control_fields,
    _boundary_config,
    _comparison_fields,
    _format,
    _lifecycle_options,
    _score,
    _summary_fields as _engineering_summary_fields,
)
from .prototype_3d_source_sponge import _effective_source_area, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


@dataclass(frozen=True)
class RefocusingMap3DOptions(RefocusingEngineering3DOptions):
    """Options for a tiny cutoff-frequency map around the best refocusing knobs."""

    cutoff_center: float | None = None
    cutoff_step: float = 1.0
    frequency_center: float | None = None
    frequency_step: float = 0.01
    strict_retention_target: float = 0.30
    strict_outer_shell_target: float = 1.0


def run_3d_refocusing_map_control(
    base_config: SimulationConfig,
    *,
    options: RefocusingMap3DOptions | None = None,
) -> dict[str, Any]:
    """Run a tiny cross-shaped cutoff/frequency map around the current 3D refocusing winners."""

    options = options or RefocusingMap3DOptions()
    control_id = datetime.now().strftime("refocusing_map_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _map_variant_plan(base_config, options)
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
        _add_map_fields(summary, config, options, base_config)
        rows.append(summary)
        timeseries_rows.extend(result["timeseries"])
        event_rows.extend(result["events"])

    classification = classify_refocusing_map(rows, options)
    reference = _cutoff_reference_row(rows)
    for row in rows:
        row.update(_comparison_fields(row, reference))
        row["refocusing_map_classification"] = classification["label"]

    summary_csv = root / "refocusing_map_summary.csv"
    timeseries_csv = root / "refocusing_map_timeseries.csv"
    events_csv = root / "refocusing_map_events.csv"
    report_path = root / "refocusing_map_3d_report.md"
    _write_csv(summary_csv, rows, _summary_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(events_csv, event_rows, _event_fields())
    _plot_lifecycle(root / "refocusing_map_shell_energy_plot.png", timeseries_rows, event_rows)
    _plot_radius_width(root / "refocusing_map_radius_width_plot.png", timeseries_rows)
    _plot_flux(root / "refocusing_map_flux_balance_plot.png", timeseries_rows)
    _write_report(report_path, control_id, rows, classification, options)
    save_json(
        root / "refocusing_map_3d_summary.json",
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


def classify_refocusing_map(
    rows: list[dict[str, Any]],
    options: RefocusingMap3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether cutoff/frequency improvements combine constructively."""

    options = options or RefocusingMap3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No refocusing-map rows were available.", "checks": {}}
    cutoff_ref = _cutoff_reference_row(rows)
    frequency_ref = _frequency_reference_row(rows)
    combined = _combined_row(rows)
    checks = {row["variant"]: _row_checks(row, cutoff_ref, frequency_ref, options) for row in rows}

    if combined is not None and _is_strong_combined(combined, cutoff_ref, frequency_ref, options):
        return {
            "label": "combined_constructive_strong",
            "reason": "The combined cutoff/frequency candidate beat both one-axis references while meeting strict retention, exit, outer/shell, and global-outer guards.",
            "best_variant": str(combined.get("variant")),
            "checks": checks,
        }
    if combined is not None and _is_partial_combined(combined, cutoff_ref, options):
        return {
            "label": "combined_constructive_partial",
            "reason": "The combined cutoff/frequency candidate stayed clean and improved at least one refocusing metric over cutoff_long, but missed one or more strict target guards.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    clean_improvements = [
        row for row in rows if row is not cutoff_ref and _is_clean(row, cutoff_ref, options) and _beats_reference(row, cutoff_ref)
    ]
    if clean_improvements:
        best = _best_variant(clean_improvements)
        return {
            "label": "local_map_improved_single_axis",
            "reason": f"The tiny map found a clean local improvement, but the combined candidate was not constructively stronger. Best: {best}.",
            "best_variant": best,
            "checks": checks,
        }
    clean_rows = [row for row in rows if _is_clean(row, cutoff_ref, options)]
    if len(clean_rows) > 1:
        return {
            "label": "local_map_tolerant_no_improvement",
            "reason": "Several cutoff/frequency variants stayed clean, but none beat the cutoff_long reference enough to call tuning constructive.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "refocusing_map_inconclusive",
        "reason": "The tiny cutoff/frequency map did not produce enough clean comparable variants for interpretation.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _map_variant_plan(base: SimulationConfig, options: RefocusingMap3DOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    base_cutoff = float(base.driver.drive_cutoff_time)
    base_frequency = float(base.driver.frequency)
    cutoff_center = options.cutoff_center if options.cutoff_center is not None else base_cutoff + options.cutoff_delta
    frequency_center = options.frequency_center if options.frequency_center is not None else base_frequency + options.frequency_delta
    variants = [
        _variant("phase_offset_reference", base, options, source_width, base_cutoff, base_frequency, "phase_reference"),
        _variant("cutoff_long_reference", base, options, source_width, cutoff_center, base_frequency, "cutoff_reference"),
        _variant("frequency_high_reference", base, options, source_width, base_cutoff, frequency_center, "frequency_reference"),
        _variant(
            "combined_cutoff_long_frequency_high",
            base,
            options,
            source_width,
            cutoff_center,
            frequency_center,
            "combined",
        ),
        _variant(
            "cutoff_low_frequency_high",
            base,
            options,
            source_width,
            max(1.0, cutoff_center - options.cutoff_step),
            frequency_center,
            "cutoff_frequency_map",
        ),
        _variant(
            "cutoff_high_frequency_high",
            base,
            options,
            source_width,
            cutoff_center + options.cutoff_step,
            frequency_center,
            "cutoff_frequency_map",
        ),
        _variant(
            "cutoff_long_frequency_low",
            base,
            options,
            source_width,
            cutoff_center,
            max(0.01, frequency_center - options.frequency_step),
            "cutoff_frequency_map",
        ),
        _variant(
            "cutoff_long_frequency_higher",
            base,
            options,
            source_width,
            cutoff_center,
            frequency_center + options.frequency_step,
            "cutoff_frequency_map",
        ),
    ]
    return variants


def _variant(
    name: str,
    base: SimulationConfig,
    options: RefocusingMap3DOptions,
    source_width: float,
    cutoff: float,
    frequency: float,
    role: str,
) -> Prototype3DConfig:
    config = _boundary_config(
        name,
        base,
        options,
        source_width,
        phase_offset=options.phase_offset,
        cutoff=cutoff,
        frequency=frequency,
        role=role,
    )
    return config


def _add_map_fields(
    row: dict[str, Any],
    config: Prototype3DConfig,
    options: RefocusingMap3DOptions,
    base: SimulationConfig,
) -> None:
    base_cutoff = float(base.driver.drive_cutoff_time)
    base_frequency = float(base.driver.frequency)
    cutoff_center = options.cutoff_center if options.cutoff_center is not None else base_cutoff + options.cutoff_delta
    frequency_center = options.frequency_center if options.frequency_center is not None else base_frequency + options.frequency_delta
    row["map_role"] = getattr(config, "_refocusing_role", "variant")
    row["cutoff_center"] = cutoff_center
    row["frequency_center"] = frequency_center
    row["cutoff_offset_from_center"] = float(config.drive_cutoff_time) - cutoff_center
    row["frequency_offset_from_center"] = float(config.drive_frequency) - frequency_center
    row["combined_candidate"] = row["map_role"] == "combined"


def _cutoff_reference_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("variant") == "cutoff_long_reference"), rows[0] if rows else None)


def _frequency_reference_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("variant") == "frequency_high_reference"), None)


def _combined_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("combined_candidate")), None)


def _row_checks(
    row: dict[str, Any],
    cutoff_ref: dict[str, Any] | None,
    frequency_ref: dict[str, Any] | None,
    options: RefocusingMap3DOptions,
) -> dict[str, Any]:
    return {
        **_comparison_fields(row, cutoff_ref),
        "clean": _is_clean(row, cutoff_ref, options),
        "beats_cutoff_reference": _beats_reference(row, cutoff_ref),
        "beats_frequency_reference": _beats_reference(row, frequency_ref),
        "strong_combined": _is_strong_combined(row, cutoff_ref, frequency_ref, options),
        "partial_combined": _is_partial_combined(row, cutoff_ref, options),
        "refocus_peak_count": row.get("refocus_peak_count"),
        "major_shell_peak_count": row.get("major_shell_peak_count"),
        "tail_shell_retention": row.get("tail_shell_retention"),
        "tail_outer_to_shell_mean": row.get("tail_outer_to_shell_mean"),
        "shell_exit_detected": row.get("shell_exit_detected"),
        "global_peak_in_outer_window": row.get("global_peak_in_outer_window"),
    }


def _is_clean(
    row: dict[str, Any] | None,
    cutoff_ref: dict[str, Any] | None,
    options: RefocusingMap3DOptions,
) -> bool:
    if row is None:
        return False
    reference_retention = float((cutoff_ref or {}).get("tail_shell_retention") or 0.0)
    min_retention = options.min_retention_ratio * reference_retention if reference_retention > EPSILON else 0.0
    return (
        float(row.get("tail_shell_retention") or 0.0) >= min_retention
        and float(row.get("tail_outer_to_shell_mean") or 999.0) <= options.max_outer_shell_ratio
        and not bool(row.get("global_peak_in_outer_window"))
    )


def _is_strong_combined(
    row: dict[str, Any] | None,
    cutoff_ref: dict[str, Any] | None,
    frequency_ref: dict[str, Any] | None,
    options: RefocusingMap3DOptions,
) -> bool:
    if row is None or not bool(row.get("combined_candidate")):
        return False
    reference_major = max(
        int((cutoff_ref or {}).get("major_shell_peak_count") or 0),
        int((frequency_ref or {}).get("major_shell_peak_count") or 0),
    )
    reference_refocus = max(
        int((cutoff_ref or {}).get("refocus_peak_count") or 0),
        int((frequency_ref or {}).get("refocus_peak_count") or 0),
    )
    return (
        _is_clean(row, cutoff_ref, options)
        and int(row.get("major_shell_peak_count") or 0) > reference_major
        and int(row.get("refocus_peak_count") or 0) > reference_refocus
        and float(row.get("tail_shell_retention") or 0.0) >= options.strict_retention_target
        and float(row.get("tail_outer_to_shell_mean") or 999.0) <= options.strict_outer_shell_target
        and not bool(row.get("shell_exit_detected"))
    )


def _is_partial_combined(
    row: dict[str, Any] | None,
    cutoff_ref: dict[str, Any] | None,
    options: RefocusingMap3DOptions,
) -> bool:
    return bool(row and row.get("combined_candidate") and _is_clean(row, cutoff_ref, options) and _beats_reference(row, cutoff_ref))


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


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(max(rows, key=_score).get("variant", "n/a"))


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: RefocusingMap3DOptions,
) -> None:
    lines = [
        f"# 3D Refocusing Cutoff-Frequency Map: {control_id}",
        "",
        "## Purpose",
        "",
        "Tiny two-knob map asking whether the winning cutoff and frequency changes combine constructively.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Role | Cutoff | Freq | Peaks | Refocus | Ratio | Exit | Ret | Outer/Shell | Decay | Global Outer |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        exit_label = "false" if not bool(row.get("shell_exit_detected")) else _format(row.get("shell_exit_time"))
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('map_role')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('drive_frequency'))} | "
            f"{row.get('major_shell_peak_count')} | "
            f"{row.get('refocus_peak_count')} | "
            f"{_format(row.get('refocus_peak_ratio_max'))} | "
            f"{exit_label} | "
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
            "- `refocusing_map_summary.csv`",
            "- `refocusing_map_timeseries.csv`",
            "- `refocusing_map_events.csv`",
            "- `refocusing_map_shell_energy_plot.png`",
            "- `refocusing_map_radius_width_plot.png`",
            "- `refocusing_map_flux_balance_plot.png`",
            "",
            "## Next Step",
            "",
            _next_step(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "combined_constructive_strong":
        return "The cutoff and frequency knobs combine constructively under strict guards. This is evidence for tunable refocusing rather than a one-off source setting."
    if label == "combined_constructive_partial":
        return "The combined cutoff/frequency variant improves at least one refocusing metric while staying clean, but it does not meet all strict targets."
    if label == "local_map_improved_single_axis":
        return "The local map found improvement, but the combined knob setting is not yet better than the best one-axis timing/frequency setting."
    if label == "local_map_tolerant_no_improvement":
        return "The packet tolerates nearby cutoff/frequency changes, but this map did not improve the cutoff_long reference."
    return "The cutoff/frequency map is inconclusive; inspect the event table before adding any variants."


def _next_step(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "combined_constructive_strong":
        return "Repeat the combined candidate with half-dt or a tiny phase-offset check before increasing grid size."
    if label in {"combined_constructive_partial", "local_map_improved_single_axis"}:
        return "Run one narrower local refinement around the best clean row only."
    return "Return to cutoff_long as the reference and inspect the event/flux traces before adding more parameters."


def _summary_fields() -> list[str]:
    base_fields = [field for field in _engineering_summary_fields() if field not in {"variant", "refocusing_engineering_classification"}]
    return [
        "variant",
        "refocusing_map_classification",
        "map_role",
        "combined_candidate",
        "cutoff_center",
        "frequency_center",
        "cutoff_offset_from_center",
        "frequency_offset_from_center",
        *base_fields,
    ]
