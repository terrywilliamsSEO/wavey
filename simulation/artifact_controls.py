"""Targeted artifact controls for long-run mode-shape candidates."""

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
class ArtifactControlOptions:
    output_root: str = "runs"
    frame_interval: int = 20
    window_steps: int = 30
    stronger_sponge_multiplier: float = 2.0
    wider_sponge_multiplier: float = 2.0


def run_artifact_controls(
    base_config: SimulationConfig,
    *,
    options: ArtifactControlOptions | None = None,
    reference_root: str | Path = "runs",
) -> dict[str, Any]:
    """Run sponge-boundary artifact controls and compare diagnostics."""

    options = options or ArtifactControlOptions()
    control_id = datetime.now().strftime("artifact_controls_%Y%m%d_%H%M%S")
    control_root = Path(options.output_root) / control_id
    control_root.mkdir(parents=True, exist_ok=False)

    variants = _build_sponge_variants(base_config, options)
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

    classification = classify_artifact_control_results(rows)
    summary_path = control_root / "artifact_control_summary.csv"
    report_path = control_root / "artifact_control_report.md"
    _write_summary_csv(summary_path, rows)
    _write_report(report_path, control_id, base_config, rows, classification)
    save_json(
        control_root / "artifact_control_summary.json",
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


def classify_artifact_control_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify whether the candidate survives stronger sponge absorption."""

    by_variant = {row["variant"]: row for row in rows}
    baseline = by_variant.get("original")
    stronger = by_variant.get("stronger_sponge")
    wider = by_variant.get("wider_sponge")
    stronger_wider = by_variant.get("stronger_wider_sponge")
    if baseline is None or stronger is None:
        return {
            "label": "inconclusive",
            "reason": "Missing original or stronger sponge control.",
        }

    stronger_preserves = _variant_preserves_signal(baseline, stronger)
    wider_preserves = _variant_preserves_signal(baseline, wider) if wider else False
    stronger_wider_preserves = (
        _variant_preserves_signal(baseline, stronger_wider) if stronger_wider else False
    )
    destructive_count = sum(
        _variant_destroys_signal(baseline, row)
        for row in (stronger, wider, stronger_wider)
        if row is not None
    )

    if stronger_preserves:
        return {
            "label": "survives_stronger_sponge",
            "reason": (
                "The stronger sponge control preserved the breathing detection, retention, angular organization, "
                "and broadly similar timing. Wider controls are reported as secondary checks."
            ),
            "stronger_preserves": True,
            "wider_preserves": wider_preserves,
            "stronger_wider_preserves": stronger_wider_preserves,
        }

    if destructive_count >= 2:
        return {
            "label": "boundary_reflection_likely",
            "reason": (
                "At least two stronger-absorption variants substantially weakened or removed the breathing/angular "
                "tail, making boundary reflection a likely contributor."
            ),
            "stronger_preserves": False,
            "wider_preserves": wider_preserves,
            "stronger_wider_preserves": stronger_wider_preserves,
        }

    if _variant_significantly_changes_signal(baseline, stronger):
        if bool(stronger.get("breathing_detected")) and _ratio(stronger, baseline, "retention_score") >= 0.65:
            reason = (
                "The breathing and retention survived stronger sponge damping, but angular phase organization or "
                "timing changed enough that the full breathing/angular interpretation remains provisional."
            )
        else:
            reason = (
                "The stronger sponge control changed one or more key tail diagnostics enough that the candidate "
                "should remain provisional."
            )
        return {
            "label": "sponge_sensitive",
            "reason": reason,
            "stronger_preserves": False,
            "wider_preserves": wider_preserves,
            "stronger_wider_preserves": stronger_wider_preserves,
        }

    return {
        "label": "inconclusive",
        "reason": "The sponge controls did not clearly preserve or destroy the tail under the current thresholds.",
        "stronger_preserves": False,
        "wider_preserves": wider_preserves,
        "stronger_wider_preserves": stronger_wider_preserves,
    }


def _build_sponge_variants(
    base_config: SimulationConfig,
    options: ArtifactControlOptions,
) -> list[tuple[str, SimulationConfig]]:
    base = copy.deepcopy(base_config)
    base.boundary_mode = "sponge"
    base_strength = float(base.boundary_damping_strength)
    base_width = int(base.boundary_damping_width)
    stronger_strength = max(base_strength * options.stronger_sponge_multiplier, base_strength + 0.04)
    wider_width = min(
        max(base_width + 1, int(round(base_width * options.wider_sponge_multiplier))),
        max(1, base.grid_size // 2 - 1),
    )

    variants: list[tuple[str, SimulationConfig]] = []
    original = copy.deepcopy(base)
    variants.append(("original", original))

    stronger = copy.deepcopy(base)
    stronger.boundary_damping_strength = stronger_strength
    variants.append(("stronger_sponge", stronger))

    wider = copy.deepcopy(base)
    wider.boundary_damping_width = wider_width
    variants.append(("wider_sponge", wider))

    both = copy.deepcopy(base)
    both.boundary_damping_strength = stronger_strength
    both.boundary_damping_width = wider_width
    variants.append(("stronger_wider_sponge", both))
    return variants


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
        "best_energy_well_ratio": float(diagnostics.get("best_energy_well_ratio", 0.0)),
        "best_core_energy": energy.get("best_core_energy"),
        "best_outer_lattice_energy": energy.get("best_outer_lattice_energy"),
        "best_total_energy": energy.get("best_total_energy"),
        "best_core_fraction": energy.get("best_core_fraction"),
        "best_ratio_from_absolute_energy": energy.get("best_ratio_from_absolute_energy"),
        "core_decay_rate_after_cutoff": energy.get("core_decay_rate_after_cutoff"),
        "outer_decay_rate_after_cutoff": energy.get("outer_decay_rate_after_cutoff"),
        "total_decay_rate_after_cutoff": energy.get("total_decay_rate_after_cutoff"),
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
    labels.extend(breathing.get("labels", []))
    if breathing.get("label"):
        labels.append(breathing["label"])
    if transition.get("label"):
        labels.append(transition["label"])
    labels.extend(diagnostics.get("angular_detection", {}).get("labels", []))
    labels.extend(diagnostics.get("reference_comparison", {}).get("labels", []))
    return list(dict.fromkeys(labels))


def _variant_preserves_signal(baseline: dict[str, Any], variant: dict[str, Any] | None) -> bool:
    if variant is None:
        return False
    return (
        bool(variant.get("breathing_detected"))
        and _ratio(variant, baseline, "retention_score") >= 0.65
        and _ratio(variant, baseline, "best_energy_well_ratio") >= 0.45
        and _period_similar(baseline.get("breathing_period"), variant.get("breathing_period"))
        and _time_similar(baseline.get("best_event_time"), variant.get("best_event_time"))
        and float(variant.get("angular_phase_trend_r2") or 0.0) >= 0.55
        and float(variant.get("angular_phase_drift") or 0.0) >= 3.14159
        and float(variant.get("strongest_angular_mode_strength") or 0.0) >= 0.25
    )


def _variant_destroys_signal(baseline: dict[str, Any], variant: dict[str, Any]) -> bool:
    return (
        _ratio(variant, baseline, "retention_score") < 0.4
        or _ratio(variant, baseline, "best_energy_well_ratio") < 0.3
        or (
            not bool(variant.get("breathing_detected"))
            and float(variant.get("angular_phase_trend_r2") or 0.0) < 0.35
        )
    )


def _variant_significantly_changes_signal(baseline: dict[str, Any], variant: dict[str, Any]) -> bool:
    return (
        _ratio(variant, baseline, "retention_score") < 0.65
        or _ratio(variant, baseline, "best_energy_well_ratio") < 0.45
        or not _period_similar(baseline.get("breathing_period"), variant.get("breathing_period"))
        or not _time_similar(baseline.get("best_event_time"), variant.get("best_event_time"))
        or float(variant.get("angular_phase_trend_r2") or 0.0) < 0.55
    )


def _ratio(variant: dict[str, Any], baseline: dict[str, Any], key: str) -> float:
    denom = float(baseline.get(key) or 0.0)
    if denom <= 1e-12:
        return 0.0
    return float(variant.get(key) or 0.0) / denom


def _period_similar(first: Any, second: Any) -> bool:
    if first is None or second is None:
        return False
    first_value = float(first)
    second_value = float(second)
    return abs(first_value - second_value) <= max(0.6, 0.3 * abs(first_value))


def _time_similar(first: Any, second: Any) -> bool:
    if first is None or second is None:
        return False
    first_value = float(first)
    second_value = float(second)
    return abs(first_value - second_value) <= max(6.0, 0.18 * abs(first_value))


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "variant",
        "run_id",
        "path",
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
) -> None:
    lines = [
        f"# Artifact Control Report: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Targeted sponge-boundary controls for the long 0.92 breathing/angular tail candidate. "
            "This report checks whether the signal survives stronger boundary absorption before any broader sweep."
        ),
        "",
        "## Base Configuration",
        "",
        f"- Drive frequency: `{base_config.driver.frequency}`",
        f"- Drive amplitude: `{base_config.driver.amplitude}`",
        f"- Boundary mode: `{base_config.boundary_mode}`",
        f"- Sponge width/strength: `{base_config.boundary_damping_width}` / `{base_config.boundary_damping_strength}`",
        f"- Steps/dt: `{base_config.steps}` / `{base_config.dt}`",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Variant Comparison",
        "",
        "| Variant | Ratio | Retention | Best Time | Breathing | Period | Strength | Cycles | Angular Mode | Angular R^2 | Labels |",
        "| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('best_energy_well_ratio'))} | "
            f"{_format(row.get('retention_score'))} | "
            f"{_format(row.get('best_event_time'))} | "
            f"{row.get('breathing_detected')} | "
            f"{_format(row.get('breathing_period'))} | "
            f"{_format(row.get('breathing_strength'))} | "
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
                "This table separates numerator and denominator effects in the energy-well ratio. "
                "A higher ratio is strongest evidence when core energy stays comparable, not merely when outer-lattice energy falls."
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
            "## Denominator Check",
            "",
            _denominator_interpretation(rows),
            "",
            "## Interpretation",
            "",
            _classification_interpretation(classification),
            "",
            "## Files",
            "",
            "- `artifact_control_summary.csv`",
        ]
    )
    for row in rows:
        lines.append(f"- `{row['variant']}` report: `{row.get('mode_shape_diagnostics_report')}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _denominator_interpretation(rows: list[dict[str, Any]]) -> str:
    baseline = next((row for row in rows if row.get("variant") == "original"), None)
    if baseline is None:
        return "No original baseline row was available, so denominator sensitivity could not be checked."

    baseline_core = float(baseline.get("best_core_energy") or 0.0)
    baseline_outer = float(baseline.get("best_outer_lattice_energy") or 0.0)
    baseline_ratio = float(baseline.get("best_energy_well_ratio") or 0.0)
    if baseline_core <= 0.0 or baseline_outer <= 0.0:
        return "The original baseline has insufficient absolute-energy data for a denominator check."

    notes = []
    for row in rows:
        if row is baseline:
            continue
        core_ratio = float(row.get("best_core_energy") or 0.0) / baseline_core
        outer_ratio = float(row.get("best_outer_lattice_energy") or 0.0) / baseline_outer
        ratio_gain = float(row.get("best_energy_well_ratio") or 0.0) / max(baseline_ratio, 1e-12)
        if ratio_gain > 1.05 and outer_ratio < core_ratio * 0.9:
            notes.append(
                f"`{row['variant']}` improved the ratio partly through a smaller outer-lattice denominator "
                f"(core x{core_ratio:.2f}, outer x{outer_ratio:.2f})."
            )
        elif core_ratio >= 0.75:
            notes.append(
                f"`{row['variant']}` kept best-frame core energy broadly comparable "
                f"(core x{core_ratio:.2f}, outer x{outer_ratio:.2f})."
            )
        else:
            notes.append(
                f"`{row['variant']}` reduced best-frame core energy materially "
                f"(core x{core_ratio:.2f}, outer x{outer_ratio:.2f})."
            )

    return " ".join(notes) if notes else "Only the original baseline was present."


def _classification_interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "survives_stronger_sponge":
        return (
            "The 0.92 tail survives the first stronger-absorption control. This does not prove unusual physics; "
            "it only reduces the chance that the original signal was a simple boundary-reflection artifact."
        )
    if label == "boundary_reflection_likely":
        return (
            "The signal weakened under stronger absorption enough that boundary reflection is a likely contributor. "
            "Do not advance to broader long sweeps until the boundary behavior is understood."
        )
    if label == "sponge_sensitive":
        return (
            "The core breathing and retention may survive stronger absorption, but at least one key angular or timing "
            "diagnostic changed materially. Treat the full breathing/angular interpretation as provisional and inspect "
            "the per-variant diagnostics before choosing another control."
        )
    return "The current controls are not decisive. More targeted numerical checks are needed before broader sweeps."


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
