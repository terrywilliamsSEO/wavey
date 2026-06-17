"""Fixed-domain grid-refinement controls for long-run candidates."""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .config import SimulationConfig, save_json
from .control_metrics import run_energy_comparison
from .lattice import Lattice2D
from .mode_diagnostics import shape_correlation
from .stability import estimate_stability
from .sweep import run_single_experiment
from .time_resolved_diagnostics import DiagnosticOptions, diagnose_existing_run


@dataclass(frozen=True)
class FixedDomainGridControlOptions:
    output_root: str = "runs"
    frame_interval: int = 20
    window_steps: int = 30
    refined_grid_size: int = 63
    include_81: bool = False
    min_retention: float = 0.75
    min_core_fraction_ratio: float = 0.75
    min_energy_well_ratio_fraction: float = 0.5
    min_best_frame_similarity: float = 0.35
    max_radial_peak_shift: float = 1.5
    expected_period_min: float = 2.0
    expected_period_max: float = 3.8


def run_fixed_domain_grid_control(
    base_config: SimulationConfig,
    *,
    options: FixedDomainGridControlOptions | None = None,
    reference_root: str | Path = "runs",
) -> dict[str, Any]:
    """Run fixed-domain grid-resolution controls for one candidate."""

    options = options or FixedDomainGridControlOptions()
    control_id = datetime.now().strftime("fixed_domain_grid_controls_%Y%m%d_%H%M%S")
    control_root = Path(options.output_root) / control_id
    control_root.mkdir(parents=True, exist_ok=False)

    variants = _build_fixed_domain_variants(base_config, options)
    rows: list[dict[str, Any]] = []
    configs_by_variant: dict[str, SimulationConfig] = {}
    for variant_name, config in variants:
        configs_by_variant[variant_name] = config
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

    _add_best_frame_similarities(rows, configs_by_variant)
    classification = classify_fixed_domain_grid_results(rows, options)
    summary_path = control_root / "fixed_domain_grid_control_summary.csv"
    report_path = control_root / "fixed_domain_grid_control_report.md"
    _write_summary_csv(summary_path, rows)
    _write_report(report_path, control_id, base_config, rows, classification, options)
    save_json(
        control_root / "fixed_domain_grid_control_summary.json",
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


def classify_fixed_domain_grid_results(
    rows: list[dict[str, Any]],
    options: FixedDomainGridControlOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the candidate survives true fixed-domain refinement."""

    options = options or FixedDomainGridControlOptions()
    baseline = next((row for row in rows if row.get("variant", "").startswith("fixed_domain_grid_41")), None)
    refined = next((row for row in rows if row.get("variant", "").startswith(f"fixed_domain_grid_{options.refined_grid_size}")), None)
    if baseline is None or refined is None:
        return {"label": "scaling_inconclusive", "reason": "Missing baseline or refined fixed-domain row.", "checks": {}}

    if _has_hard_dt_warning(refined) or _has_hard_dt_warning(baseline):
        return {
            "label": "unstable_due_to_dt",
            "reason": "At least one fixed-domain variant exceeded the hard dt stability estimate.",
            "checks": {"dt_stability": False},
        }

    if not bool(baseline.get("fixed_domain")) or not bool(refined.get("fixed_domain")):
        return {
            "label": "implementation_needs_physics_scaling_review",
            "reason": "A fixed-domain control row was not actually marked fixed_domain=true.",
            "checks": {"fixed_domain_enabled": False},
        }

    period_check = _period_check(baseline, refined, options)
    checks = {
        "breathing_detected": bool(refined.get("breathing_detected")),
        "breathing_period": period_check["passed"],
        "retention": float(refined.get("retention_score") or 0.0) >= options.min_retention,
        "best_event_time": _time_similar(baseline.get("best_event_time"), refined.get("best_event_time")),
        "energy_well_ratio": _ratio(refined, baseline, "best_energy_well_ratio") >= options.min_energy_well_ratio_fraction,
        "core_fraction": _ratio(refined, baseline, "best_core_fraction") >= options.min_core_fraction_ratio,
        "physical_radial_peak": _physical_radial_peak_similar(baseline, refined, options),
        "best_frame_similarity": float(refined.get("best_frame_similarity_to_baseline") or 0.0)
        >= options.min_best_frame_similarity,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if not failed:
        return {
            "label": "fixed_domain_resolution_resistant",
            "reason": (
                "The refined same-domain run preserved breathing, retention, core fraction, physical radial structure, "
                "best-frame similarity, and best-event timing."
            ),
            "checks": checks,
            "period_check": period_check,
        }

    critical = {"breathing_detected", "retention", "best_event_time", "physical_radial_peak"}
    label = "resolution_sensitive" if any(name in critical for name in failed) else "scaling_inconclusive"
    return {
        "label": label,
        "reason": f"The refined same-domain control failed: {', '.join(failed)}.",
        "checks": checks,
        "period_check": period_check,
    }


def _build_fixed_domain_variants(
    base_config: SimulationConfig,
    options: FixedDomainGridControlOptions,
) -> list[tuple[str, SimulationConfig]]:
    baseline = _fixed_domain_config(base_config, base_config.grid_size)
    refined = _fixed_domain_config(base_config, options.refined_grid_size)
    variants = [(f"fixed_domain_grid_{baseline.grid_size}", baseline), (f"fixed_domain_grid_{refined.grid_size}", refined)]
    if options.include_81:
        grid_81 = _fixed_domain_config(base_config, 81)
        variants.append((f"fixed_domain_grid_{grid_81.grid_size}", grid_81))
    return variants


def _fixed_domain_config(
    base_config: SimulationConfig,
    grid_size: int,
    *,
    source_normalization: str | None = None,
) -> SimulationConfig:
    config = copy.deepcopy(base_config)
    domain_width = float(base_config.domain_width if base_config.domain_width is not None else base_config.grid_size - 1)
    base_height = base_config.grid_height if base_config.grid_height is not None else base_config.grid_size
    domain_height = float(base_config.domain_height if base_config.domain_height is not None else base_height - 1)
    defect_radius_physical = (
        float(base_config.defect.radius_physical)
        if base_config.defect.radius_physical is not None
        else float(base_config.defect.radius)
    )
    core_radius_physical = (
        float(base_config.core_radius_physical)
        if base_config.core_radius_physical is not None
        else float(base_config.effective_core_radius)
    )
    sponge_width_physical = (
        float(base_config.boundary_damping_width_physical)
        if base_config.boundary_damping_width_physical is not None
        else float(base_config.boundary_damping_width)
    )
    emitter_width_physical = (
        float(base_config.driver.emitter_width_physical)
        if base_config.driver.emitter_width_physical is not None
        else float(max(1, base_config.driver.emitter_width))
    )

    config.fixed_domain = True
    config.domain_width = domain_width
    config.domain_height = domain_height
    config.grid_size = _odd_grid_size(grid_size)
    config.grid_height = config.grid_size
    config.defect.radius_physical = defect_radius_physical
    config.core_radius_physical = core_radius_physical
    config.boundary_damping_width_physical = sponge_width_physical
    config.driver.emitter_width_physical = emitter_width_physical
    if source_normalization is not None:
        config.driver.source_normalization = source_normalization
    elif config.driver.source_normalization == "per_cell":
        config.driver.source_normalization = "constant_boundary_flux"
    config.defect.radius = max(1, int(round(defect_radius_physical / min(config.dx, config.dy))))
    config.core_radius = max(1, int(round(core_radius_physical / min(config.dx, config.dy))))
    config.boundary_damping_width = max(1, int(round(sponge_width_physical / min(config.dx, config.dy))))
    return config


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
    stability = summary.get("stability", estimate_stability(config))
    return {
        "variant": variant,
        "run_id": summary.get("run_id"),
        "path": summary.get("path"),
        "fixed_domain": bool(config.fixed_domain),
        "grid_size": int(config.grid_size),
        "domain_width": float(config.physical_domain_width),
        "domain_height": float(config.physical_domain_height),
        "dx": float(config.dx),
        "dy": float(config.dy),
        "defect_radius_physical": float(config.effective_defect_radius),
        "core_radius_physical": float(config.effective_core_radius_value),
        "boundary_damping_width_physical": float(config.effective_boundary_damping_width),
        "emitter_width_physical": float(config.effective_emitter_width),
        "dt": float(config.dt),
        "steps": int(config.steps),
        "physical_duration": float(config.dt) * float(config.steps),
        "drive_cutoff_time": config.driver.drive_cutoff_time,
        **counts,
        "recommended_dt_max": stability.get("recommended_dt_max"),
        "hard_stability_dt_max": stability.get("hard_stability_dt_max"),
        "dt_to_recommended_ratio": stability.get("dt_to_recommended_ratio"),
        "dt_to_hard_limit_ratio": stability.get("dt_to_hard_limit_ratio"),
        "stability_warnings": " | ".join(stability.get("warnings", [])) or "none",
        "best_energy_well_ratio": float(diagnostics.get("best_energy_well_ratio", 0.0)),
        "retention_score": float(diagnostics.get("retention_score", 0.0)),
        "best_event_time": float(summary.get("time_of_best_event", 0.0)),
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
        "breathing_detected": breathing.get("status") == "detected",
        "breathing_period": breathing.get("estimated_period"),
        "breathing_strength": breathing.get("breathing_strength_score"),
        "breathing_cycles": breathing.get("detected_cycles", 0),
        "best_event_radial_peak_radius_physical": radial.get("best_event_radial_peak_radius"),
        "radial_peak_radius_range_physical": radial.get("radial_peak_radius_range"),
        "strongest_angular_mode": angular.get("strongest_angular_mode"),
        "strongest_angular_mode_strength": angular.get("strongest_angular_mode_strength"),
        "angular_phase_drift": angular.get("angular_phase_drift"),
        "angular_phase_trend_r2": angular.get("angular_phase_trend_r2"),
        "mean_previous_frame_correlation": correlation.get("mean_corr_prev_frame"),
        "minimum_previous_frame_correlation": correlation.get("min_corr_prev_frame"),
        "detected_labels": ", ".join(labels) or "none",
        "mode_shape_diagnostics_report": diagnostics.get("report_path"),
        "best_frame_similarity_to_baseline": None,
    }


def _add_best_frame_similarities(rows: list[dict[str, Any]], configs_by_variant: dict[str, SimulationConfig]) -> None:
    baseline = rows[0] if rows else None
    if baseline is None:
        return
    baseline_energy = _load_best_frame(baseline)
    baseline_config = configs_by_variant[baseline["variant"]]
    if baseline_energy is None:
        return
    for row in rows:
        energy = _load_best_frame(row)
        config = configs_by_variant[row["variant"]]
        if energy is None:
            row["best_frame_similarity_to_baseline"] = None
            continue
        if row is baseline:
            row["best_frame_similarity_to_baseline"] = 1.0
            continue
        resampled = _resample_to_config(energy, config, baseline_config)
        row["best_frame_similarity_to_baseline"] = shape_correlation(baseline_energy, resampled)


def _load_best_frame(row: dict[str, Any]) -> np.ndarray | None:
    path = Path(str(row.get("path", ""))) / "best_energy_density.npy"
    if not path.exists():
        return None
    return np.load(path)


def _resample_to_config(energy: np.ndarray, source: SimulationConfig, target: SimulationConfig) -> np.ndarray:
    target_rows, target_cols = np.indices(target.shape, dtype=float)
    x = (target_cols - (target.nx - 1) / 2.0) * target.dx
    y = (target_rows - (target.ny - 1) / 2.0) * target.dy
    source_col = x / source.dx + (source.nx - 1) / 2.0
    source_row = y / source.dy + (source.ny - 1) / 2.0
    return _bilinear_sample(energy, source_row, source_col)


def _bilinear_sample(values: np.ndarray, row: np.ndarray, col: np.ndarray) -> np.ndarray:
    row = np.clip(row, 0.0, values.shape[0] - 1.0)
    col = np.clip(col, 0.0, values.shape[1] - 1.0)
    r0 = np.floor(row).astype(int)
    c0 = np.floor(col).astype(int)
    r1 = np.clip(r0 + 1, 0, values.shape[0] - 1)
    c1 = np.clip(c0 + 1, 0, values.shape[1] - 1)
    wr = row - r0
    wc = col - c0
    top = values[r0, c0] * (1.0 - wc) + values[r0, c1] * wc
    bottom = values[r1, c0] * (1.0 - wc) + values[r1, c1] * wc
    return top * (1.0 - wr) + bottom * wr


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "variant",
        "run_id",
        "path",
        "fixed_domain",
        "grid_size",
        "domain_width",
        "domain_height",
        "dx",
        "dy",
        "defect_radius_physical",
        "core_radius_physical",
        "boundary_damping_width_physical",
        "emitter_width_physical",
        "dt",
        "steps",
        "physical_duration",
        "drive_cutoff_time",
        "core_cell_count",
        "outer_cell_count",
        "total_cell_count",
        "recommended_dt_max",
        "hard_stability_dt_max",
        "dt_to_recommended_ratio",
        "dt_to_hard_limit_ratio",
        "stability_warnings",
        "best_energy_well_ratio",
        "retention_score",
        "best_event_time",
        "best_core_energy",
        "best_outer_lattice_energy",
        "best_total_energy",
        "best_core_fraction",
        "best_ratio_from_absolute_energy",
        "breathing_detected",
        "breathing_period",
        "breathing_strength",
        "breathing_cycles",
        "best_event_radial_peak_radius_physical",
        "radial_peak_radius_range_physical",
        "strongest_angular_mode",
        "strongest_angular_mode_strength",
        "angular_phase_drift",
        "angular_phase_trend_r2",
        "best_frame_similarity_to_baseline",
        "core_decay_rate_after_cutoff",
        "outer_decay_rate_after_cutoff",
        "total_decay_rate_after_cutoff",
        "metric_core_peak_period_after_cutoff",
        "metric_core_peak_cycles_after_cutoff",
        "metric_core_peak_interval_cv_after_cutoff",
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
    options: FixedDomainGridControlOptions,
) -> None:
    lines = [
        f"# Fixed-Domain Grid Control Report: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "True fixed-domain grid-refinement control for the long 0.92 breathing-localization candidate. "
            "The physical domain, defect radius, sponge width, and emitter width are held fixed while grid resolution changes."
        ),
        "",
        "## Base Reinterpretation",
        "",
        f"- Original configured grid: `{base_config.grid_size}`",
        f"- Fixed physical domain: `{rows[0].get('domain_width') if rows else 'n/a'}` x `{rows[0].get('domain_height') if rows else 'n/a'}`",
        f"- Drive frequency/amplitude: `{base_config.driver.frequency}` / `{base_config.driver.amplitude}`",
        f"- Drive cutoff time: `{base_config.driver.drive_cutoff_time}`",
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
            "## Stability",
            "",
            "| Variant | dx | dy | dt | Recommended dt max | Hard dt max | Warnings |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('dx'))} | "
            f"{_format(row.get('dy'))} | "
            f"{_format(row.get('dt'))} | "
            f"{_format(row.get('recommended_dt_max'))} | "
            f"{_format(row.get('hard_stability_dt_max'))} | "
            f"{_escape(row.get('stability_warnings', 'none'))} |"
        )

    lines.extend(
        [
            "",
            "## Variant Comparison",
            "",
            "| Variant | Grid | Ratio | Retention | Best Time | Breathing | Period | Cycles | Core Fraction | Radial Peak | Angular Mode | Angular R^2 | Best-Frame Similarity |",
            "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('grid_size')} | "
            f"{_format(row.get('best_energy_well_ratio'))} | "
            f"{_format(row.get('retention_score'))} | "
            f"{_format(row.get('best_event_time'))} | "
            f"{row.get('breathing_detected')} | "
            f"{_format(row.get('breathing_period'))} | "
            f"{row.get('breathing_cycles')} | "
            f"{_format(row.get('best_core_fraction'))} | "
            f"{_format(row.get('best_event_radial_peak_radius_physical'))} | "
            f"m={row.get('strongest_angular_mode')} ({_format(row.get('strongest_angular_mode_strength'))}) | "
            f"{_format(row.get('angular_phase_trend_r2'))} | "
            f"{_format(row.get('best_frame_similarity_to_baseline'))} |"
        )

    lines.extend(
        [
            "",
            "## Energy",
            "",
            "| Variant | Core E | Outer E | Total E | Core Decay | Outer Decay | Total Decay |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('best_core_energy'))} | "
            f"{_format(row.get('best_outer_lattice_energy'))} | "
            f"{_format(row.get('best_total_energy'))} | "
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
            f"- Core-fraction ratio minimum: `{options.min_core_fraction_ratio}`",
            f"- Energy-well-ratio fraction minimum: `{options.min_energy_well_ratio_fraction}`",
            f"- Best-frame similarity minimum: `{options.min_best_frame_similarity}`",
            f"- Physical radial peak shift maximum: `{options.max_radial_peak_shift}`",
            "",
            "## Files",
            "",
            "- `fixed_domain_grid_control_summary.csv`",
        ]
    )
    for row in rows:
        lines.append(f"- `{row['variant']}` report: `{row.get('mode_shape_diagnostics_report')}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _classification_interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "fixed_domain_resolution_resistant":
        return (
            "The 0.92 candidate survives true same-domain grid refinement under the current fixed-domain physics scaling. "
            "This supports resolution-resistant breathing localization; rotation should still be phrased carefully because sponge controls remain phase-sensitive."
        )
    if label == "resolution_sensitive":
        return (
            "The same-domain refined run changed key timing, breathing, retention, or physical radial structure enough that the candidate remains resolution-sensitive."
        )
    if label == "unstable_due_to_dt":
        return "The refined run cannot be interpreted until it is rerun with a smaller dt."
    if label == "implementation_needs_physics_scaling_review":
        return "The control detected an implementation-level fixed-domain setup issue; review scaling before interpreting the run."
    return "The same-domain refinement evidence is mixed. Inspect the per-variant diagnostics before broader sweeps."


def _period_check(
    baseline: dict[str, Any],
    refined: dict[str, Any],
    options: FixedDomainGridControlOptions,
) -> dict[str, Any]:
    diagnostic_passed = _period_value_pass(baseline.get("breathing_period"), refined.get("breathing_period"), options)
    metric_passed = _period_value_pass(
        baseline.get("metric_core_peak_period_after_cutoff"),
        refined.get("metric_core_peak_period_after_cutoff"),
        options,
    )
    if diagnostic_passed:
        source = "diagnostic_breathing_period"
    elif metric_passed:
        source = "metric_core_peak_period"
    else:
        source = "none"
    return {"passed": diagnostic_passed or metric_passed, "source": source}


def _period_value_pass(baseline_period: Any, period: Any, options: FixedDomainGridControlOptions) -> bool:
    if period is None:
        return False
    period_value = float(period)
    if options.expected_period_min <= period_value <= options.expected_period_max:
        return True
    if baseline_period is None:
        return False
    baseline_value = float(baseline_period)
    return abs(period_value - baseline_value) <= max(0.8, 0.35 * abs(baseline_value))


def _physical_radial_peak_similar(
    baseline: dict[str, Any],
    refined: dict[str, Any],
    options: FixedDomainGridControlOptions,
) -> bool:
    first = baseline.get("best_event_radial_peak_radius_physical")
    second = refined.get("best_event_radial_peak_radius_physical")
    if first is None or second is None:
        return False
    return abs(float(first) - float(second)) <= options.max_radial_peak_shift


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


def _has_hard_dt_warning(row: dict[str, Any]) -> bool:
    return float(row.get("dt_to_hard_limit_ratio") or 0.0) > 1.0


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
        "total_cell_count": int(config.nx * config.ny),
    }


def _odd_grid_size(value: int) -> int:
    value = max(3, int(value))
    return value if value % 2 == 1 else value + 1


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
