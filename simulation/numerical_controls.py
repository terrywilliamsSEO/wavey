"""Targeted numerical controls for long-run mode-shape candidates."""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import SimulationConfig, save_json
from .control_metrics import run_energy_comparison
from .sweep import run_single_experiment
from .time_resolved_diagnostics import DiagnosticOptions, diagnose_existing_run


@dataclass(frozen=True)
class DtControlOptions:
    output_root: str = "runs"
    frame_interval: int = 20
    window_steps: int = 30
    dt_multiplier: float = 0.5
    min_retention: float = 0.75
    min_core_energy_ratio: float = 0.5
    min_energy_well_ratio_fraction: float = 0.3
    expected_period_min: float = 2.2
    expected_period_max: float = 3.6


def run_dt_control(
    base_config: SimulationConfig,
    *,
    options: DtControlOptions | None = None,
    reference_root: str | Path = "runs",
) -> dict[str, Any]:
    """Run the baseline and smaller-dt variants for one long validation case."""

    options = options or DtControlOptions()
    if options.dt_multiplier <= 0.0 or options.dt_multiplier >= 1.0:
        raise ValueError("dt_multiplier must be between 0 and 1 for a smaller-dt control")

    control_id = datetime.now().strftime("dt_controls_%Y%m%d_%H%M%S")
    control_root = Path(options.output_root) / control_id
    control_root.mkdir(parents=True, exist_ok=False)

    variants = _build_dt_variants(base_config, options)
    rows: list[dict[str, Any]] = []
    for variant_name, config in variants:
        summary = run_single_experiment(config, output_root=control_root, run_id=variant_name)
        diagnostics = diagnose_existing_run(
            summary["path"],
            options=DiagnosticOptions(
                frame_interval=_scaled_steps(options.frame_interval, base_config.dt, config.dt),
                window_steps=_scaled_steps(options.window_steps, base_config.dt, config.dt),
                save_frame_pngs=False,
            ),
            reference_root=reference_root,
        )
        rows.append(_summary_row(variant_name, config, summary, diagnostics))

    classification = classify_dt_control_results(rows, options)
    summary_path = control_root / "dt_control_summary.csv"
    report_path = control_root / "dt_control_report.md"
    _write_summary_csv(summary_path, rows)
    _write_report(report_path, control_id, base_config, rows, classification, options)
    save_json(
        control_root / "dt_control_summary.json",
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


def classify_dt_control_results(
    rows: list[dict[str, Any]],
    options: DtControlOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the long candidate survives smaller time steps."""

    options = options or DtControlOptions()
    baseline = next((row for row in rows if row.get("variant", "").startswith("baseline_dt_")), None)
    half_step = next((row for row in rows if row.get("variant", "").startswith("half_dt_")), None)
    if baseline is None or half_step is None:
        return {
            "label": "inconclusive",
            "reason": "Missing baseline or smaller-dt control row.",
            "checks": {},
        }

    period_check = _period_check(baseline, half_step, options)
    checks = {
        "breathing_detected": bool(half_step.get("breathing_detected")),
        "breathing_period": period_check["passed"],
        "retention": float(half_step.get("retention_score") or 0.0) >= options.min_retention,
        "best_event_time": _time_similar(baseline.get("best_event_time"), half_step.get("best_event_time")),
        "angular_mode_m4": int(half_step.get("strongest_angular_mode") or -1) == 4,
        "energy_well_ratio": _ratio(half_step, baseline, "best_energy_well_ratio")
        >= options.min_energy_well_ratio_fraction
        and float(half_step.get("best_energy_well_ratio") or 0.0) > 0.05,
        "absolute_core_energy": _ratio(half_step, baseline, "best_core_energy") >= options.min_core_energy_ratio,
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
            "label": "numerically_stable",
            "reason": (
                "The half-step control preserved breathing, late best-event timing, high retention, m=4 structure, "
                "energy-well ratio, and comparable absolute core energy."
                f"{caveat}"
            ),
            "checks": checks,
            "period_check": period_check,
        }

    critical = {
        "breathing_detected",
        "retention",
        "best_event_time",
        "energy_well_ratio",
        "absolute_core_energy",
    }
    label = "dt_sensitive" if any(name in critical for name in failed) else "inconclusive"
    return {
        "label": label,
        "reason": f"The half-step control failed: {', '.join(failed)}.",
        "checks": checks,
        "period_check": period_check,
    }


def _build_dt_variants(
    base_config: SimulationConfig,
    options: DtControlOptions,
) -> list[tuple[str, SimulationConfig]]:
    baseline = copy.deepcopy(base_config)
    smaller = copy.deepcopy(base_config)
    physical_duration = float(base_config.steps) * float(base_config.dt)
    smaller.dt = float(base_config.dt) * options.dt_multiplier
    smaller.steps = max(1, int(round(physical_duration / smaller.dt)))
    return [
        (f"baseline_dt_{_dt_label(baseline.dt)}", baseline),
        (f"half_dt_{_dt_label(smaller.dt)}", smaller),
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
    return {
        "variant": variant,
        "run_id": summary.get("run_id"),
        "path": summary.get("path"),
        "dt": float(config.dt),
        "steps": int(config.steps),
        "physical_duration": float(config.dt) * float(config.steps),
        "drive_cutoff_time": config.driver.drive_cutoff_time,
        "best_energy_well_ratio": float(diagnostics.get("best_energy_well_ratio", 0.0)),
        "best_core_energy": energy.get("best_core_energy"),
        "best_outer_lattice_energy": energy.get("best_outer_lattice_energy"),
        "best_total_energy": energy.get("best_total_energy"),
        "best_core_fraction": energy.get("best_core_fraction"),
        "best_ratio_from_absolute_energy": energy.get("best_ratio_from_absolute_energy"),
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


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "variant",
        "run_id",
        "path",
        "dt",
        "steps",
        "physical_duration",
        "drive_cutoff_time",
        "best_energy_well_ratio",
        "retention_score",
        "best_event_time",
        "best_core_energy",
        "best_outer_lattice_energy",
        "best_total_energy",
        "best_core_fraction",
        "best_ratio_from_absolute_energy",
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
    options: DtControlOptions,
) -> None:
    lines = [
        f"# Time-Step Control Report: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Targeted smaller-dt numerical control for the long 0.92 breathing/angular tail candidate. "
            "This report checks whether the signal survives stricter integration before any broader long sweep."
        ),
        "",
        "## Base Configuration",
        "",
        f"- Drive frequency: `{base_config.driver.frequency}`",
        f"- Drive amplitude: `{base_config.driver.amplitude}`",
        f"- Drive cutoff time: `{base_config.driver.drive_cutoff_time}`",
        f"- Boundary mode: `{base_config.boundary_mode}`",
        f"- Sponge width/strength: `{base_config.boundary_damping_width}` / `{base_config.boundary_damping_strength}`",
        f"- Baseline steps/dt: `{base_config.steps}` / `{base_config.dt}`",
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
            "| Variant | dt | Steps | Ratio | Retention | Best Time | Breathing | Period | Cycles | Angular Mode | Angular R^2 | Labels |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('dt'))} | "
            f"{row.get('steps')} | "
            f"{_format(row.get('best_energy_well_ratio'))} | "
            f"{_format(row.get('retention_score'))} | "
            f"{_format(row.get('best_event_time'))} | "
            f"{row.get('breathing_detected')} | "
            f"{_format(row.get('breathing_period'))} | "
            f"{row.get('breathing_cycles')} | "
            f"m={row.get('strongest_angular_mode')} ({_format(row.get('strongest_angular_mode_strength'))}) | "
            f"{_format(row.get('angular_phase_trend_r2'))} | "
            f"{_escape(row.get('detected_labels', 'none'))} |"
        )

    lines.extend(
        [
            "",
            "## Absolute Energy Check",
            "",
            (
                "This table compares the absolute numerator and denominator behind the energy-well ratio. "
                "Core energy should remain comparable for a strong smaller-dt pass."
            ),
            "",
            "| Variant | Core E | Outer E | Total E | Core Fraction | Core Decay | Outer Decay | Total Decay |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
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
            f"- Minimum half-step/core-energy ratio: `{options.min_core_energy_ratio}`",
            f"- Minimum half-step/ratio fraction: `{options.min_energy_well_ratio_fraction}`",
            "",
            "## Files",
            "",
            "- `dt_control_summary.csv`",
        ]
    )
    for row in rows:
        lines.append(f"- `{row['variant']}` report: `{row.get('mode_shape_diagnostics_report')}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _classification_interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "numerically_stable":
        return (
            "The candidate passes the smaller-dt control. A careful claim is now: boundary-resistant and "
            "numerically stable post-cutoff breathing localization at 0.92. Rotation should still be phrased "
            "carefully: the tail contains persistent non-axisymmetric angular structure, often m=4, but coherent "
            "rotation is sensitive to sponge settings."
        )
    if label == "dt_sensitive":
        return (
            "The candidate changed under stricter integration enough that the numerical behavior must be understood "
            "before upgrading the claim or running broader long sweeps."
        )
    return "The smaller-dt control is not decisive. Inspect per-variant diagnostics before choosing the next control."


def _period_check(
    baseline: dict[str, Any],
    half_step: dict[str, Any],
    options: DtControlOptions,
) -> dict[str, Any]:
    diagnostic_passed = _period_value_pass(
        baseline.get("breathing_period"),
        half_step.get("breathing_period"),
        options,
    )
    metric_passed = _period_value_pass(
        baseline.get("metric_core_peak_period_after_cutoff"),
        half_step.get("metric_core_peak_period_after_cutoff"),
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
        "diagnostic_period": half_step.get("breathing_period"),
        "metric_core_peak_period": half_step.get("metric_core_peak_period_after_cutoff"),
    }


def _period_value_pass(baseline_period: Any, period: Any, options: DtControlOptions) -> bool:
    if period is None:
        return False
    period_value = float(period)
    if options.expected_period_min <= period_value <= options.expected_period_max:
        return True
    if baseline_period is None:
        return False
    baseline_value = float(baseline_period)
    return abs(period_value - baseline_value) <= max(0.8, 0.35 * abs(baseline_value))


def _time_similar(first: Any, second: Any) -> bool:
    if first is None or second is None:
        return False
    first_value = float(first)
    second_value = float(second)
    return abs(first_value - second_value) <= max(6.0, 0.18 * abs(first_value))


def _ratio(variant: dict[str, Any], baseline: dict[str, Any], key: str) -> float:
    denom = float(baseline.get(key) or 0.0)
    if denom <= 1e-12:
        return 0.0
    return float(variant.get(key) or 0.0) / denom


def _scaled_steps(value: int, baseline_dt: float, variant_dt: float) -> int:
    return max(1, int(round(float(value) * float(baseline_dt) / float(variant_dt))))


def _dt_label(value: float) -> str:
    return f"{value:.6g}".replace("-", "m").replace(".", "p")


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
