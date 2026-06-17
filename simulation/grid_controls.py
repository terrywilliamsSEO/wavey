"""Targeted larger-grid controls for long-run mode-shape candidates."""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import SimulationConfig, save_json
from .control_metrics import run_energy_comparison
from .lattice import Lattice2D
from .sweep import run_single_experiment
from .time_resolved_diagnostics import DiagnosticOptions, diagnose_existing_run


@dataclass(frozen=True)
class GridControlOptions:
    output_root: str = "runs"
    frame_interval: int = 20
    window_steps: int = 30
    grid_scale: float = 1.5
    larger_grid_size: int | None = None
    larger_physical_duration: float | None = None
    min_retention: float = 0.75
    min_energy_well_ratio_fraction: float = 0.3
    min_core_fraction_ratio: float = 0.5
    min_core_density_ratio: float = 0.25
    expected_period_min: float = 2.2
    expected_period_max: float = 3.6


def run_grid_control(
    base_config: SimulationConfig,
    *,
    options: GridControlOptions | None = None,
    reference_root: str | Path = "runs",
) -> dict[str, Any]:
    """Run the baseline and larger-grid matched-proportion variants."""

    options = options or GridControlOptions()
    control_id = datetime.now().strftime("grid_controls_%Y%m%d_%H%M%S")
    control_root = Path(options.output_root) / control_id
    control_root.mkdir(parents=True, exist_ok=False)

    variants = _build_grid_variants(base_config, options)
    rows: list[dict[str, Any]] = []
    for variant_name, config in variants:
        summary = run_single_experiment(config, output_root=control_root, run_id=variant_name)
        diagnostics = diagnose_existing_run(
            summary["path"],
            options=DiagnosticOptions(
                frame_interval=options.frame_interval,
                window_steps=options.window_steps,
                save_frame_pngs=False,
            ),
            reference_root=reference_root,
        )
        rows.append(_summary_row(variant_name, config, summary, diagnostics))

    classification = classify_grid_control_results(rows, options)
    summary_path = control_root / "grid_control_summary.csv"
    report_path = control_root / "grid_control_report.md"
    _write_summary_csv(summary_path, rows)
    _write_report(report_path, control_id, base_config, rows, classification, options)
    save_json(
        control_root / "grid_control_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": rows,
            "summary_csv": str(summary_path),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": rows,
        "summary_csv": str(summary_path),
        "report_path": str(report_path),
        "path": str(control_root),
    }


def classify_grid_control_results(
    rows: list[dict[str, Any]],
    options: GridControlOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the candidate survives a larger matched-proportion grid."""

    options = options or GridControlOptions()
    baseline = next((row for row in rows if row.get("variant", "").startswith("baseline_grid_")), None)
    larger = next((row for row in rows if row.get("variant", "").startswith("larger_grid_")), None)
    if baseline is None or larger is None:
        return {
            "label": "inconclusive",
            "reason": "Missing baseline or larger-grid control row.",
            "checks": {},
        }

    period_check = _period_check(baseline, larger, options)
    checks = {
        "breathing_detected": bool(larger.get("breathing_detected")),
        "breathing_period": period_check["passed"],
        "retention": float(larger.get("retention_score") or 0.0) >= options.min_retention,
        "best_event_time": _time_similar(baseline.get("best_event_time"), larger.get("best_event_time")),
        "angular_mode_m4": int(larger.get("strongest_angular_mode") or -1) == 4,
        "energy_well_ratio": _ratio(larger, baseline, "best_energy_well_ratio")
        >= options.min_energy_well_ratio_fraction
        and float(larger.get("best_energy_well_ratio") or 0.0) > 0.05,
        "core_fraction": _ratio(larger, baseline, "best_core_fraction") >= options.min_core_fraction_ratio,
        "core_energy_density": _ratio(larger, baseline, "best_core_energy_density") >= options.min_core_density_ratio,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if not failed:
        caveat = ""
        if period_check["source"] == "metric_core_peak_period":
            caveat = (
                " The breathing-period pass uses full-resolution core-energy peaks because the diagnostic-frame "
                "period estimate shifted outside the target window."
            )
        return {
            "label": "grid_resistant",
            "reason": (
                "The larger-grid control preserved breathing, late best-event timing, high retention, m=4 structure, "
                "energy-well ratio, core fraction, and normalized core-energy density."
                f"{caveat}"
            ),
            "checks": checks,
            "period_check": period_check,
        }

    if failed == ["best_event_time"]:
        return {
            "label": "grid_resistant_timing_shift",
            "reason": (
                "The larger-grid control preserved the breathing, retention, m=4 structure, energy-well ratio, "
                "core fraction, and normalized core-energy density, but the best event shifted later."
            ),
            "checks": checks,
            "period_check": period_check,
        }

    critical = {
        "breathing_detected",
        "retention",
        "best_event_time",
        "energy_well_ratio",
        "core_fraction",
        "core_energy_density",
    }
    if _is_end_limited(larger) and any(name in critical for name in failed):
        return {
            "label": "inconclusive_end_limited",
            "reason": (
                f"The larger-grid control failed: {', '.join(failed)}, but its best event landed at the run end. "
                "Rerun the larger-grid case with a longer physical duration before deciding whether this is true grid sensitivity."
            ),
            "checks": checks,
            "period_check": period_check,
        }

    label = "grid_sensitive" if any(name in critical for name in failed) else "inconclusive"
    return {
        "label": label,
        "reason": f"The larger-grid control failed: {', '.join(failed)}.",
        "checks": checks,
        "period_check": period_check,
    }


def _build_grid_variants(
    base_config: SimulationConfig,
    options: GridControlOptions,
) -> list[tuple[str, SimulationConfig]]:
    baseline = copy.deepcopy(base_config)
    larger = copy.deepcopy(base_config)
    if options.larger_grid_size is not None:
        target_grid = _odd_grid_size(options.larger_grid_size)
    else:
        target_grid = _odd_grid_size(int(round(base_config.grid_size * options.grid_scale)))
    if target_grid <= base_config.grid_size:
        raise ValueError("larger_grid_size or grid_scale must produce a grid larger than the baseline")

    scale = target_grid / float(base_config.grid_size)
    larger.grid_size = target_grid
    larger.defect.radius = max(1, int(round(base_config.defect.radius * scale)))
    if base_config.core_radius is not None:
        larger.core_radius = max(1, int(round(base_config.core_radius * scale)))
    larger.boundary_damping_width = min(
        max(1, int(round(base_config.boundary_damping_width * scale))),
        max(1, larger.grid_size // 2 - 1),
    )
    if options.larger_physical_duration is not None:
        larger.steps = max(1, int(round(float(options.larger_physical_duration) / float(larger.dt))))
    return [
        (f"baseline_grid_{baseline.grid_size}", baseline),
        (f"larger_grid_{larger.grid_size}", larger),
    ]


def _summary_row(
    variant: str,
    config: SimulationConfig,
    summary: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    breathing = diagnostics.get("breathing_detection", {})
    angular = diagnostics.get("angular_detection", {})
    radial = diagnostics.get("radial_drift_summary", {})
    correlation = diagnostics.get("correlation_summary", {})
    labels = _diagnostic_labels(diagnostics)
    energy = run_energy_comparison(summary.get("path", ""), config.driver.drive_cutoff_time)
    counts = _mask_counts(config)
    core_count = max(1, counts["core_cell_count"])
    outer_count = max(1, counts["outer_cell_count"])
    total_count = max(1, counts["total_cell_count"])
    best_core = energy.get("best_core_energy")
    best_outer = energy.get("best_outer_lattice_energy")
    best_total = energy.get("best_total_energy")
    return {
        "variant": variant,
        "run_id": summary.get("run_id"),
        "path": summary.get("path"),
        "grid_size": int(config.grid_size),
        "defect_radius": int(config.defect.radius),
        "boundary_damping_width": int(config.boundary_damping_width),
        "dt": float(config.dt),
        "steps": int(config.steps),
        "physical_duration": float(config.dt) * float(config.steps),
        "drive_cutoff_time": config.driver.drive_cutoff_time,
        **counts,
        "best_energy_well_ratio": float(diagnostics.get("best_energy_well_ratio", 0.0)),
        "best_core_energy": best_core,
        "best_outer_lattice_energy": best_outer,
        "best_total_energy": best_total,
        "best_core_fraction": energy.get("best_core_fraction"),
        "best_ratio_from_absolute_energy": energy.get("best_ratio_from_absolute_energy"),
        "best_core_energy_density": _density(best_core, core_count),
        "best_outer_energy_density": _density(best_outer, outer_count),
        "best_total_energy_density": _density(best_total, total_count),
        "core_decay_rate_after_cutoff": energy.get("core_decay_rate_after_cutoff"),
        "outer_decay_rate_after_cutoff": energy.get("outer_decay_rate_after_cutoff"),
        "total_decay_rate_after_cutoff": energy.get("total_decay_rate_after_cutoff"),
        "metric_core_peak_period_after_cutoff": energy.get("metric_core_peak_period_after_cutoff"),
        "metric_core_peak_cycles_after_cutoff": energy.get("metric_core_peak_cycles_after_cutoff"),
        "metric_core_peak_interval_cv_after_cutoff": energy.get("metric_core_peak_interval_cv_after_cutoff"),
        "retention_score": float(diagnostics.get("retention_score", 0.0)),
        "best_event_time": float(summary.get("time_of_best_event", 0.0)),
        "breathing_detected": breathing.get("status") == "detected",
        "breathing_period": breathing.get("estimated_period"),
        "breathing_strength": breathing.get("breathing_strength_score"),
        "breathing_cycles": breathing.get("detected_cycles", 0),
        "strongest_angular_mode": angular.get("strongest_angular_mode"),
        "strongest_angular_mode_strength": angular.get("strongest_angular_mode_strength"),
        "angular_phase_drift": angular.get("angular_phase_drift"),
        "angular_phase_trend_r2": angular.get("angular_phase_trend_r2"),
        "radial_peak_radius_range": radial.get("radial_peak_radius_range"),
        "mean_previous_frame_correlation": correlation.get("mean_corr_prev_frame"),
        "minimum_previous_frame_correlation": correlation.get("min_corr_prev_frame"),
        "detected_labels": ", ".join(labels) or "none",
        "mode_shape_diagnostics_report": diagnostics.get("report_path"),
    }


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "variant",
        "run_id",
        "path",
        "grid_size",
        "defect_radius",
        "boundary_damping_width",
        "dt",
        "steps",
        "physical_duration",
        "drive_cutoff_time",
        "core_cell_count",
        "outer_cell_count",
        "total_cell_count",
        "best_energy_well_ratio",
        "retention_score",
        "best_event_time",
        "best_core_energy",
        "best_outer_lattice_energy",
        "best_total_energy",
        "best_core_fraction",
        "best_ratio_from_absolute_energy",
        "best_core_energy_density",
        "best_outer_energy_density",
        "best_total_energy_density",
        "core_decay_rate_after_cutoff",
        "outer_decay_rate_after_cutoff",
        "total_decay_rate_after_cutoff",
        "metric_core_peak_period_after_cutoff",
        "metric_core_peak_cycles_after_cutoff",
        "metric_core_peak_interval_cv_after_cutoff",
        "breathing_detected",
        "breathing_period",
        "breathing_strength",
        "breathing_cycles",
        "strongest_angular_mode",
        "strongest_angular_mode_strength",
        "angular_phase_drift",
        "angular_phase_trend_r2",
        "radial_peak_radius_range",
        "mean_previous_frame_correlation",
        "minimum_previous_frame_correlation",
        "detected_labels",
        "mode_shape_diagnostics_report",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _write_report(
    path: Path,
    control_id: str,
    base_config: SimulationConfig,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: GridControlOptions,
) -> None:
    lines = [
        f"# Grid Control Report: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Targeted larger-grid matched-proportion control for the long 0.92 breathing/angular tail candidate. "
            "This is a discrete larger-grid check, not a full continuum grid-refinement proof because the engine has no explicit dx parameter yet."
        ),
        "",
        "## Base Configuration",
        "",
        f"- Drive frequency: `{base_config.driver.frequency}`",
        f"- Drive amplitude: `{base_config.driver.amplitude}`",
        f"- Drive cutoff time: `{base_config.driver.drive_cutoff_time}`",
        f"- Boundary mode: `{base_config.boundary_mode}`",
        f"- Baseline grid/defect/sponge width: `{base_config.grid_size}` / `{base_config.defect.radius}` / `{base_config.boundary_damping_width}`",
        f"- Steps/dt: `{base_config.steps}` / `{base_config.dt}`",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Pass Checks",
        "",
        "| Check | Passed |",
        "| --- | --- |",
    ]
    for name, passed in classification.get("checks", {}).items():
        lines.append(f"| `{name}` | `{passed}` |")

    lines.extend(
        [
            "",
            "## Period Check",
            "",
            f"- Source used for pass/fail: `{classification.get('period_check', {}).get('source', 'n/a')}`",
            "",
            "| Variant | Diagnostic Period | Diagnostic Cycles | Metric Core-Peak Period | Metric Core-Peak Cycles | Metric Interval CV |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('breathing_period'))} | "
            f"{row.get('breathing_cycles')} | "
            f"{_format(row.get('metric_core_peak_period_after_cutoff'))} | "
            f"{_format(row.get('metric_core_peak_cycles_after_cutoff'))} | "
            f"{_format(row.get('metric_core_peak_interval_cv_after_cutoff'))} |"
        )

    lines.extend(
        [
            "",
            "## Variant Comparison",
            "",
            "| Variant | Grid | Defect | Sponge Width | Steps | End Time | Ratio | Retention | Best Time | Breathing | Period | Angular Mode | Angular R^2 | Labels |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('grid_size')} | "
            f"{row.get('defect_radius')} | "
            f"{row.get('boundary_damping_width')} | "
            f"{row.get('steps')} | "
            f"{_format(row.get('physical_duration'))} | "
            f"{_format(row.get('best_energy_well_ratio'))} | "
            f"{_format(row.get('retention_score'))} | "
            f"{_format(row.get('best_event_time'))} | "
            f"{row.get('breathing_detected')} | "
            f"{_format(row.get('breathing_period'))} | "
            f"m={row.get('strongest_angular_mode')} ({_format(row.get('strongest_angular_mode_strength'))}) | "
            f"{_format(row.get('angular_phase_trend_r2'))} | "
            f"{_escape(row.get('detected_labels', 'none'))} |"
        )

    lines.extend(
        [
            "",
            "## Energy And Density Check",
            "",
            (
                "Absolute energy is shown, but the larger-grid row should also be read through core fraction and "
                "per-cell density because the scaled defect/core contains a different number of cells."
            ),
            "",
            "| Variant | Core E | Outer E | Total E | Core Fraction | Core Density | Outer Density | Total Density | Core Decay | Outer Decay | Total Decay |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('best_core_energy'))} | "
            f"{_format(row.get('best_outer_lattice_energy'))} | "
            f"{_format(row.get('best_total_energy'))} | "
            f"{_format(row.get('best_core_fraction'))} | "
            f"{_format(row.get('best_core_energy_density'))} | "
            f"{_format(row.get('best_outer_energy_density'))} | "
            f"{_format(row.get('best_total_energy_density'))} | "
            f"{_format(row.get('core_decay_rate_after_cutoff'))} | "
            f"{_format(row.get('outer_decay_rate_after_cutoff'))} | "
            f"{_format(row.get('total_decay_rate_after_cutoff'))} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _classification_interpretation(classification),
            "",
            "## Criteria",
            "",
            f"- Retention minimum: `{options.min_retention}`",
            f"- Expected breathing-period window: `{options.expected_period_min}` to `{options.expected_period_max}`",
            f"- Minimum larger-grid/ratio fraction: `{options.min_energy_well_ratio_fraction}`",
            f"- Minimum larger-grid/core-fraction ratio: `{options.min_core_fraction_ratio}`",
            f"- Minimum larger-grid/core-density ratio: `{options.min_core_density_ratio}`",
            "",
            "## Files",
            "",
            "- `grid_control_summary.csv`",
        ]
    )
    for row in rows:
        lines.append(f"- `{row['variant']}` report: `{row.get('mode_shape_diagnostics_report')}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _classification_interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "grid_resistant":
        return (
            "The candidate passes this larger-grid matched-proportion control. A careful claim is now: boundary-resistant, "
            "time-step stable, and larger-grid-resistant post-cutoff breathing localization at 0.92 in the current discrete model. "
            "Rotation remains provisional because coherent angular phase trend was sponge-sensitive."
        )
    if label == "grid_resistant_timing_shift":
        return (
            "The larger-grid extended-duration run preserved the breathing localization and m=4 structure, but the strongest "
            "event shifted later. This supports structural survival on the larger grid, while timing remains sensitive to "
            "domain/grid scaling in the current discrete model."
        )
    if label == "grid_sensitive":
        return (
            "The candidate changed under the larger-grid control enough that spatial-resolution or domain-scaling behavior "
            "must be understood before broader long sweeps."
        )
    if label == "inconclusive_end_limited":
        return (
            "The larger-grid run reached its strongest localization at the end of the simulation, leaving too little post-best "
            "tail to judge breathing persistence. Extend only the larger-grid duration before treating this as a true grid failure."
        )
    return "The larger-grid control is not decisive. Inspect per-variant diagnostics before choosing the next control."


def _period_check(
    baseline: dict[str, Any],
    larger: dict[str, Any],
    options: GridControlOptions,
) -> dict[str, Any]:
    diagnostic_passed = _period_value_pass(
        baseline.get("breathing_period"),
        larger.get("breathing_period"),
        options,
    )
    metric_passed = _period_value_pass(
        baseline.get("metric_core_peak_period_after_cutoff"),
        larger.get("metric_core_peak_period_after_cutoff"),
        options,
    )
    if diagnostic_passed:
        source = "diagnostic_breathing_period"
    elif metric_passed:
        source = "metric_core_peak_period"
    else:
        source = "none"
    return {
        "passed": diagnostic_passed or metric_passed,
        "source": source,
        "diagnostic_passed": diagnostic_passed,
        "metric_passed": metric_passed,
        "diagnostic_period": larger.get("breathing_period"),
        "metric_core_peak_period": larger.get("metric_core_peak_period_after_cutoff"),
    }


def _period_value_pass(baseline_period: Any, period: Any, options: GridControlOptions) -> bool:
    if period is None:
        return False
    period_value = float(period)
    if options.expected_period_min <= period_value <= options.expected_period_max:
        return True
    if baseline_period is None:
        return False
    baseline_value = float(baseline_period)
    return abs(period_value - baseline_value) <= max(0.8, 0.35 * abs(baseline_value))


def _diagnostic_labels(diagnostics: dict[str, Any]) -> list[str]:
    labels = []
    breathing = diagnostics.get("breathing_detection", {})
    transition = diagnostics.get("mode_transition_detection", {})
    labels.extend(breathing.get("labels", []))
    if breathing.get("label"):
        labels.append(breathing["label"])
    if transition.get("label"):
        labels.append(transition["label"])
    labels.extend(diagnostics.get("angular_detection", {}).get("labels", []))
    labels.extend(diagnostics.get("reference_comparison", {}).get("labels", []))
    return list(dict.fromkeys(labels))


def _mask_counts(config: SimulationConfig) -> dict[str, int]:
    masks = Lattice2D._build_masks(config)
    return {
        "core_cell_count": int(masks.core.sum()),
        "outer_cell_count": int(masks.outer.sum()),
        "total_cell_count": int(config.grid_size * config.grid_size),
    }


def _density(value: Any, count: int) -> float | None:
    if value is None:
        return None
    return float(value) / max(1, count)


def _odd_grid_size(value: int) -> int:
    value = max(3, int(value))
    return value if value % 2 == 1 else value + 1


def _time_similar(first: Any, second: Any) -> bool:
    if first is None or second is None:
        return False
    first_value = float(first)
    second_value = float(second)
    return abs(first_value - second_value) <= max(6.0, 0.18 * abs(first_value))


def _is_end_limited(row: dict[str, Any]) -> bool:
    duration = row.get("physical_duration")
    best_time = row.get("best_event_time")
    dt = float(row.get("dt") or 0.0)
    if duration is None or best_time is None:
        return False
    margin = max(1.0, 10.0 * dt)
    return float(duration) - float(best_time) <= margin


def _ratio(variant: dict[str, Any], baseline: dict[str, Any], key: str) -> float:
    denom = float(baseline.get(key) or 0.0)
    if denom <= 1e-12:
        return 0.0
    return float(variant.get(key) or 0.0) / denom


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    return value


def _format(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.6g}"


def _escape(value: str) -> str:
    return str(value).replace("|", "\\|")
