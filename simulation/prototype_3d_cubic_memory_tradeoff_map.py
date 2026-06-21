"""Fixed 41^3 cubic-degeneracy spatial-memory tradeoff map."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig
from .prototype_3d_cutoff_phase_map import threshold_robust_refocusing_scores
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _boundary_config as _interference_boundary_config
from .prototype_3d_refocusing_engineering import _lifecycle_options
from .prototype_3d_source_sponge import _write_csv
from .prototype_3d_spatial_memory_mechanism_lab import (
    SpatialMemoryMechanismLabOptions,
    _add_clean_gate_fields,
    _add_lab_fields,
    _bool,
    _calibration_target_work_per_area,
    _comb_and_modal_metrics,
    _event_fields,
    _float,
    _format,
    _int,
    _robust_fields,
    _shell_width_from_options,
    _timeseries_fields,
    calculate_spatial_pattern_memory,
)
from .prototype_3d_spatial_phase_instrumentation import (
    _angular_fields,
    _calibrate_fixed_variant,
    _drift_fields,
    _frame_index_fields,
    _merge_robust_counts,
    _node_frame_fields,
    _radial_coherence_fields,
    _radial_frame_fields,
    _run_spatial_phase_variant,
    _stability_fields,
    _threshold_fields,
)


CUBIC_MEMORY_TRADEOFF_ROLES = (
    "neutral_reference",
    "cubic_split_0p25x",
    "cubic_split_0p5x",
    "cubic_split_1p0x",
    "cubic_split_1p5x",
    "cubic_split_sign_flipped_0p5x",
    "cubic_split_sign_flipped_1p0x",
    "random_equivalent_0p5x",
    "random_equivalent_1p0x",
)


@dataclass(frozen=True)
class CubicMemoryTradeoffMapOptions(SpatialMemoryMechanismLabOptions):
    """Options for the fixed 41^3 cubic-memory tradeoff map."""

    output_root: str = "runs"
    grid_size: int = 41
    fixed_cutoff: float = 17.94
    fixed_drive_frequency: float = 0.92
    dt_scale: float = 0.25
    mechanism_strength: float = 0.035
    random_seed: int = 9203
    min_strict_major_peaks: int = 9
    min_strict_refocus_peaks: int = 8


def run_3d_cubic_memory_tradeoff_map(
    base_config: SimulationConfig,
    *,
    options: CubicMemoryTradeoffMapOptions | None = None,
) -> dict[str, Any]:
    """Run the fixed 41^3 cubic-degeneracy strength/orientation tradeoff map."""

    options = options or CubicMemoryTradeoffMapOptions()
    violations = validate_cubic_memory_tradeoff_guardrails(options)
    if violations:
        raise ValueError("Cubic memory tradeoff guardrail violation: " + "; ".join(violations))

    control_id = datetime.now().strftime("cubic_memory_tradeoff_map_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    summary_rows, by_return_rows, comparison_rows, artifact_rows = _run_tradeoff_stage(base_config, options, root)
    classification = classify_cubic_memory_tradeoff(summary_rows, comparison_rows, options)
    for row_set in (summary_rows, by_return_rows, comparison_rows):
        for row in row_set:
            row["cubic_memory_tradeoff_classification"] = classification["label"]

    summary_csv = root / "cubic_memory_tradeoff_summary.csv"
    by_return_csv = root / "cubic_memory_by_return.csv"
    comparison_csv = root / "cubic_tradeoff_control_comparison.csv"
    report_path = root / "cubic_memory_tradeoff_report.md"
    summary_json = root / "cubic_memory_tradeoff_summary.json"
    plots = {
        "memory_vs_strict_count": str(root / "memory_vs_strict_count_plot.png"),
        "off_comb_energy": str(root / "off_comb_energy_plot.png"),
        "comb_score": str(root / "comb_score_plot.png"),
        "modal_participation": str(root / "modal_participation_plot.png"),
    }

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(by_return_csv, by_return_rows, _by_return_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_artifact_csvs(root, artifact_rows)
    _plot_memory_vs_strict(Path(plots["memory_vs_strict_count"]), summary_rows)
    _plot_summary_bar(Path(plots["off_comb_energy"]), summary_rows, "off_comb_energy_ratio", "Off-Comb Energy Ratio")
    _plot_summary_bar(Path(plots["comb_score"]), summary_rows, "return_timing_comb_score", "Return Timing Comb Score")
    _plot_summary_bar(Path(plots["modal_participation"]), summary_rows, "modal_participation_ratio", "Modal Participation Ratio")
    _write_report(report_path, control_id, classification, summary_rows, comparison_rows, options)
    save_json(
        summary_json,
        {
            "control_id": control_id,
            "classification": classification,
            "summary_csv": str(summary_csv),
            "by_return_csv": str(by_return_csv),
            "comparison_csv": str(comparison_csv),
            "report_path": str(report_path),
            "plots": plots,
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": summary_rows,
        "by_return_rows": by_return_rows,
        "comparison_rows": comparison_rows,
        "summary_csv": str(summary_csv),
        "by_return_csv": str(by_return_csv),
        "comparison_csv": str(comparison_csv),
        "report_path": str(report_path),
        "summary_json": str(summary_json),
        "plots": plots,
        "path": str(root),
    }


def validate_cubic_memory_tradeoff_guardrails(options: CubicMemoryTradeoffMapOptions) -> list[str]:
    """Return guardrail violations for this 41^3-only mechanism map."""

    violations: list[str] = []
    if int(options.grid_size) != 41:
        violations.append("cubic memory tradeoff map is fixed to 41^3")
    if abs(float(options.fixed_cutoff) - 17.94) > 1.0e-9:
        violations.append("cutoff phase/timing tuning is forbidden")
    if abs(float(options.fixed_drive_frequency) - 0.92) > 1.0e-9:
        violations.append("frequency/source-shape tuning is forbidden")
    return violations


def build_cubic_memory_tradeoff_variants(
    base_config: SimulationConfig,
    options: CubicMemoryTradeoffMapOptions | None = None,
) -> list[Prototype3DConfig]:
    """Construct the fixed 41^3 cubic tradeoff variant map."""

    options = options or CubicMemoryTradeoffMapOptions()
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    lifecycle_options = _lifecycle_options(options)
    configs: list[Prototype3DConfig] = []
    for spec in _variant_specs():
        name = f"cubic_memory_tradeoff_41_{spec['role']}"
        config = _interference_boundary_config(name, base_config, lifecycle_options, source_width, "cubic", cubic_sign=-1.0)
        config.grid_size = int(options.grid_size)
        config.dt = float(base_config.dt) * float(options.dt_scale)
        config.steps = max(1, int(round(float(options.physical_duration) / max(config.dt, EPSILON))))
        config.drive_cutoff_time = float(options.fixed_cutoff)
        config.drive_frequency = float(options.fixed_drive_frequency)
        config.memory_mechanism_profile = str(spec["profile"])
        config.memory_mechanism_strength = float(options.mechanism_strength) * float(spec["signed_factor"])
        config.memory_mechanism_seed = int(options.random_seed)
        config.memory_mechanism_shell_radius = float(options.shell_window_radius + 0.5 * _shell_width_from_options(options, config))
        config.memory_mechanism_shell_width = float(_shell_width_from_options(options, config))
        setattr(config, "_tradeoff_role", spec["role"])
        setattr(config, "_spatial_memory_role", spec["role"])
        setattr(config, "_spatial_memory_profile", spec["profile"])
        setattr(config, "_mechanism_strength_factor", spec["strength_factor"])
        setattr(config, "_split_orientation", spec["orientation"])
        setattr(config, "_matched_random_role", spec["matched_random_role"])
        setattr(config, "_dt_scale", options.dt_scale)
        configs.append(config)
    return configs


def classify_cubic_memory_tradeoff(
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: CubicMemoryTradeoffMapOptions | None = None,
) -> dict[str, Any]:
    """Classify the cubic-memory tradeoff map."""

    options = options or CubicMemoryTradeoffMapOptions()
    neutral = next((row for row in rows if row.get("mechanism_role") == "neutral_reference"), None)
    random_controls = [row for row in rows if str(row.get("mechanism_role")).startswith("random_equivalent")]
    missing: list[str] = []
    if neutral is None:
        missing.append("neutral_reference")
    for role in ("random_equivalent_0p5x", "random_equivalent_1p0x"):
        if not any(row.get("mechanism_role") == role for row in rows):
            missing.append(role)
    missing.extend([str(row.get("variant")) for row in rows if int(_float(row.get("pattern_memory_pair_count"))) <= 0])
    accounting_failures = [
        str(row.get("variant"))
        for row in rows
        if not _bool(row.get("energy_accounting_clean")) or not _bool(row.get("no_post_cutoff_external_work"))
    ]
    control_failures = [
        str(row.get("variant"))
        for row in ([neutral] if neutral is not None else []) + random_controls
        if row is not None and not _bool(row.get("clean_gates_passed"))
    ]
    checks = {
        "missing_required_artifacts": missing,
        "accounting_failures": accounting_failures,
        "control_clean_gate_failures": control_failures,
        "neutral_pattern_memory": neutral.get("pattern_memory_score") if neutral else None,
        "strict_floor": f"{options.min_strict_major_peaks}/{options.min_strict_refocus_peaks}",
    }
    if missing or accounting_failures or control_failures:
        return {
            "label": "invalid_tradeoff",
            "reason": "Required controls, artifacts, clean gates, or work accounting failed.",
            "checks": checks,
        }

    eligible = [
        row
        for row in comparison_rows
        if _bool(row.get("matched_random_available"))
        and _bool(row.get("clean_gates_passed"))
        and _bool(row.get("beats_neutral_memory"))
        and _bool(row.get("beats_matched_random_memory"))
    ]
    support = [row for row in eligible if _bool(row.get("preserves_strict_9_8"))]
    memory_only = [row for row in eligible if not _bool(row.get("preserves_strict_9_8"))]
    best_pool = support or memory_only or comparison_rows
    best = max(
        best_pool,
        key=lambda row: (
            _bool(row.get("preserves_strict_9_8")),
            _float(row.get("memory_delta_vs_neutral")),
            _float(row.get("memory_delta_vs_matched_random")),
        ),
        default={},
    )
    checks.update(
        {
            "best_role": best.get("mechanism_role"),
            "best_memory_delta_vs_neutral": best.get("memory_delta_vs_neutral"),
            "best_memory_delta_vs_matched_random": best.get("memory_delta_vs_matched_random"),
            "best_preserves_strict_9_8": best.get("preserves_strict_9_8"),
        }
    )
    if support:
        return {
            "label": "cubic_memory_tradeoff_supported",
            "reason": "A cubic split row improved spatial memory versus neutral and matched randomized control while preserving strict 9/8 and clean gates.",
            "best_variant": best.get("variant"),
            "best_role": best.get("mechanism_role"),
            "checks": checks,
        }
    if memory_only:
        return {
            "label": "memory_only_tradeoff_supported",
            "reason": "Cubic split improved spatial memory versus neutral and matched randomized control, but strict count stayed below the neutral 9/8 floor.",
            "best_variant": best.get("variant"),
            "best_role": best.get("mechanism_role"),
            "checks": checks,
        }
    return {
        "label": "no_cubic_tradeoff",
        "reason": "No cubic split row beat both neutral and matched randomized controls on spatial memory.",
        "best_variant": best.get("variant"),
        "best_role": best.get("mechanism_role"),
        "checks": checks,
    }


def _run_tradeoff_stage(
    base_config: SimulationConfig,
    options: CubicMemoryTradeoffMapOptions,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    configs = build_cubic_memory_tradeoff_variants(base_config, options)
    lifecycle_options = _lifecycle_options(options)
    stage_root = root / "cubic_memory_41"
    stage_root.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    by_return_rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    displacement_rows: list[dict[str, Any]] = []
    velocity_rows: list[dict[str, Any]] = []
    radial_frame_rows: list[dict[str, Any]] = []
    radial_coherence_rows: list[dict[str, Any]] = []
    angular_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    drift_rows: list[dict[str, Any]] = []
    target_work_per_area = _calibration_target_work_per_area(base_config, options)

    for config in configs:
        _calibrate_fixed_variant(base_config, config, options, lifecycle_options)
        result = _run_spatial_phase_variant(config, stage_root, lifecycle_options, options)
        memory = calculate_spatial_pattern_memory(result["displacement_rows"])
        summary = result["summary"]
        _add_lab_fields(summary, config, "cubic_memory_41", target_work_per_area, memory, result, options)
        _add_tradeoff_fields(summary, config)
        summary_rows.append(summary)
        for pair in memory["pair_rows"]:
            pair["run_stage"] = "cubic_memory_41"
            pair["mechanism_role"] = getattr(config, "_tradeoff_role", "")
            pair["mechanism_profile"] = getattr(config, "_spatial_memory_profile", "")
            pair["mechanism_strength_factor"] = getattr(config, "_mechanism_strength_factor", 0.0)
            pair["split_orientation"] = getattr(config, "_split_orientation", "")
            by_return_rows.append(pair)
        timeseries_rows.extend(result["timeseries"])
        event_rows.extend(result["events"])
        threshold_rows.extend(result["threshold_counts"])
        frame_rows.extend(result["frame_index_rows"])
        displacement_rows.extend(result["displacement_rows"])
        velocity_rows.extend(result["velocity_rows"])
        radial_frame_rows.extend(result["radial_frame_rows"])
        radial_coherence_rows.extend(result["radial_coherence_rows"])
        angular_rows.extend(result["angular_rows"])
        stability_rows.extend(result["stability_rows"])
        drift_rows.extend(result["phase_drift_rows"])

    robust_rows = threshold_robust_refocusing_scores(summary_rows, timeseries_rows, options) if summary_rows else []
    _merge_robust_counts(summary_rows, robust_rows)
    for row in summary_rows:
        row.update(_comb_and_modal_metrics(str(row.get("variant")), timeseries_rows, event_rows, options))
        _add_clean_gate_fields(row, options)
    comparison_rows = _comparison_rows(summary_rows, options)
    artifact_rows = [
        {"name": "threshold", "rows": threshold_rows, "fields": _threshold_fields()},
        {"name": "frames", "rows": frame_rows, "fields": _frame_index_fields()},
        {"name": "displacement", "rows": displacement_rows, "fields": _node_frame_fields("u")},
        {"name": "velocity", "rows": velocity_rows, "fields": _node_frame_fields("v")},
        {"name": "radial_frames", "rows": radial_frame_rows, "fields": _radial_frame_fields()},
        {"name": "radial_coherence", "rows": radial_coherence_rows, "fields": _radial_coherence_fields()},
        {"name": "angular", "rows": angular_rows, "fields": _angular_fields()},
        {"name": "stability", "rows": stability_rows, "fields": _stability_fields()},
        {"name": "drift", "rows": drift_rows, "fields": _drift_fields()},
        {"name": "timeseries", "rows": timeseries_rows, "fields": _timeseries_fields()},
        {"name": "events", "rows": event_rows, "fields": _event_fields()},
        {"name": "robust", "rows": robust_rows, "fields": _robust_fields()},
    ]
    return summary_rows, by_return_rows, comparison_rows, artifact_rows


def _add_tradeoff_fields(row: dict[str, Any], config: Prototype3DConfig) -> None:
    row["mechanism_strength_factor"] = getattr(config, "_mechanism_strength_factor", 0.0)
    row["absolute_mechanism_strength"] = abs(_float(config.memory_mechanism_strength))
    row["split_orientation"] = getattr(config, "_split_orientation", "")
    row["matched_random_role"] = getattr(config, "_matched_random_role", "")
    row["matched_random_available"] = bool(row["matched_random_role"])


def _comparison_rows(summary_rows: list[dict[str, Any]], options: CubicMemoryTradeoffMapOptions) -> list[dict[str, Any]]:
    neutral = next((row for row in summary_rows if row.get("mechanism_role") == "neutral_reference"), {})
    random_by_role = {
        str(row.get("mechanism_role")): row
        for row in summary_rows
        if str(row.get("mechanism_role")).startswith("random_equivalent")
    }
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        role = str(row.get("mechanism_role"))
        if role == "neutral_reference" or role.startswith("random_equivalent"):
            continue
        matched_role = str(row.get("matched_random_role") or "")
        matched_random = random_by_role.get(matched_role, {})
        matched_available = bool(matched_random)
        memory_delta_vs_neutral = _float(row.get("pattern_memory_score")) - _float(neutral.get("pattern_memory_score"))
        memory_delta_vs_random = (
            _float(row.get("pattern_memory_score")) - _float(matched_random.get("pattern_memory_score"))
            if matched_available
            else 0.0
        )
        preserves_strict = (
            _int(row.get("conservative_major_peaks")) >= int(options.min_strict_major_peaks)
            and _int(row.get("conservative_refocus_peaks")) >= int(options.min_strict_refocus_peaks)
        )
        out.append(
            {
                "run_stage": row.get("run_stage"),
                "variant": row.get("variant"),
                "mechanism_role": role,
                "mechanism_profile": row.get("mechanism_profile"),
                "mechanism_strength_factor": row.get("mechanism_strength_factor"),
                "split_orientation": row.get("split_orientation"),
                "matched_random_role": matched_role,
                "matched_random_available": matched_available,
                "memory_delta_vs_neutral": memory_delta_vs_neutral,
                "memory_delta_vs_matched_random": memory_delta_vs_random,
                "strict_major_delta_vs_neutral": _int(row.get("conservative_major_peaks")) - _int(neutral.get("conservative_major_peaks")),
                "strict_refocus_delta_vs_neutral": _int(row.get("conservative_refocus_peaks")) - _int(neutral.get("conservative_refocus_peaks")),
                "preserves_strict_9_8": preserves_strict,
                "comb_score_delta_vs_neutral": _float(row.get("return_timing_comb_score")) - _float(neutral.get("return_timing_comb_score")),
                "off_comb_delta_vs_neutral": _float(row.get("off_comb_energy_ratio")) - _float(neutral.get("off_comb_energy_ratio")),
                "modal_participation_delta_vs_neutral": _float(row.get("modal_participation_ratio")) - _float(neutral.get("modal_participation_ratio")),
                "clean_gates_passed": row.get("clean_gates_passed"),
                "beats_neutral_memory": memory_delta_vs_neutral > EPSILON,
                "beats_matched_random_memory": matched_available and memory_delta_vs_random > EPSILON,
            }
        )
    return out


def _write_artifact_csvs(root: Path, artifact_rows: list[dict[str, Any]]) -> None:
    for artifact in artifact_rows:
        name = str(artifact["name"])
        rows = list(artifact["rows"])
        if rows:
            _write_csv(root / f"cubic_memory_{name}.csv", rows, list(artifact["fields"]))


def _write_report(
    path: Path,
    control_id: str,
    classification: dict[str, Any],
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: CubicMemoryTradeoffMapOptions,
) -> None:
    lines = [
        f"# Cubic Memory Tradeoff Map: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Guardrails",
        "",
        "- This is an independent 41^3 cubic-memory tradeoff map, not a closed-branch rescue.",
        "- Cutoff phase, frequency, source shape, active pulses, resonators, 51^3, and 61^3 are not tuning surfaces here.",
        "",
        "## Summary",
        "",
        "| Variant | Role | Strength | Orientation | Memory | Strict | Default | Loose | Comb | Off-comb | Modal PR | Clean |",
        "| --- | --- | ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('variant')} | {row.get('mechanism_role')} | "
            f"{_format(row.get('mechanism_strength_factor'))} | {row.get('split_orientation')} | "
            f"{_format(row.get('pattern_memory_score'))} | "
            f"{_int(row.get('conservative_major_peaks'))}/{_int(row.get('conservative_refocus_peaks'))} | "
            f"{_int(row.get('default_major_peaks_at_0p30'))}/{_int(row.get('default_refocus_peaks_at_0p30'))} | "
            f"{_int(row.get('loose_major_peaks_at_0p25'))}/{_int(row.get('loose_refocus_peaks_at_0p25'))} | "
            f"{_format(row.get('return_timing_comb_score'))} | "
            f"{_format(row.get('off_comb_energy_ratio'))} | "
            f"{_format(row.get('modal_participation_ratio'))} | "
            f"{row.get('clean_gates_passed')} |"
        )
    lines.extend(
        [
            "",
            "## Matched-Control Comparisons",
            "",
            "| Role | Matched random | Memory delta vs neutral | Memory delta vs matched random | Strict floor | Clean |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            f"| {row.get('mechanism_role')} | {row.get('matched_random_role') or 'n/a'} | "
            f"{_format(row.get('memory_delta_vs_neutral'))} | "
            f"{_format(row.get('memory_delta_vs_matched_random'))} | "
            f"{row.get('preserves_strict_9_8')} | {row.get('clean_gates_passed')} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `cubic_memory_tradeoff_summary.csv`",
            "- `cubic_memory_by_return.csv`",
            "- `cubic_tradeoff_control_comparison.csv`",
            "- `memory_vs_strict_count_plot.png`",
            "- `off_comb_energy_plot.png`",
            "- `comb_score_plot.png`",
            "- `modal_participation_plot.png`",
            "",
            "## Interpretation",
            "",
            _interpretation_text(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation_text(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "cubic_memory_tradeoff_supported":
        return "A local cubic-degeneracy setting preserved the 41^3 memory advantage while keeping strict 9/8 or better. This is still a 41^3 mechanism result, not scale validation."
    if label == "memory_only_tradeoff_supported":
        return "Cubic splitting improved spatial memory against matched controls, but the strict 9/8 return-count tradeoff remains unresolved."
    if label == "no_cubic_tradeoff":
        return "No fixed cubic split row beat both neutral and matched randomized controls on spatial memory. Do not tune cutoff phase, source shape, or grid size from this result."
    return "The tradeoff map is invalid because required artifacts, clean gates, or work accounting failed."


def _plot_memory_vs_strict(path: Path, rows: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=140)
    for row in rows:
        x = _float(row.get("conservative_major_peaks")) + 0.08 * _float(row.get("conservative_refocus_peaks"))
        y = _float(row.get("pattern_memory_score"))
        ax.scatter([x], [y], s=45)
        ax.annotate(str(row.get("mechanism_role")), (x, y), fontsize=6, xytext=(3, 3), textcoords="offset points")
    ax.axvline(9.0 + 0.08 * 8.0, color="black", linestyle="--", linewidth=1, alpha=0.55)
    ax.set_xlabel("Strict count proxy: major + 0.08*refocus")
    ax.set_ylabel("Return-to-return pattern memory")
    ax.set_title("Cubic Memory vs Strict Return Count")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_summary_bar(path: Path, rows: list[dict[str, Any]], key: str, title: str) -> None:
    labels = [str(row.get("mechanism_role")) for row in rows]
    values = [_float(row.get(key)) for row in rows]
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.75), 4), dpi=140)
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=6)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _variant_specs() -> list[dict[str, Any]]:
    return [
        _spec("neutral_reference", "none", 0.0, 0.0, "neutral", ""),
        _spec("cubic_split_0p25x", "cubic_degeneracy_split", 0.25, 0.25, "standard", ""),
        _spec("cubic_split_0p5x", "cubic_degeneracy_split", 0.5, 0.5, "standard", "random_equivalent_0p5x"),
        _spec("cubic_split_1p0x", "cubic_degeneracy_split", 1.0, 1.0, "standard", "random_equivalent_1p0x"),
        _spec("cubic_split_1p5x", "cubic_degeneracy_split", 1.5, 1.5, "standard", ""),
        _spec("cubic_split_sign_flipped_0p5x", "cubic_degeneracy_split", 0.5, -0.5, "sign_flipped", "random_equivalent_0p5x"),
        _spec("cubic_split_sign_flipped_1p0x", "cubic_degeneracy_split", 1.0, -1.0, "sign_flipped", "random_equivalent_1p0x"),
        _spec("random_equivalent_0p5x", "random_equivalent", 0.5, 0.5, "random", ""),
        _spec("random_equivalent_1p0x", "random_equivalent", 1.0, 1.0, "random", ""),
    ]


def _spec(
    role: str,
    profile: str,
    strength_factor: float,
    signed_factor: float,
    orientation: str,
    matched_random_role: str,
) -> dict[str, Any]:
    return {
        "role": role,
        "profile": profile,
        "strength_factor": strength_factor,
        "signed_factor": signed_factor,
        "orientation": orientation,
        "matched_random_role": matched_random_role,
    }


def _summary_fields() -> list[str]:
    return [
        "variant",
        "cubic_memory_tradeoff_classification",
        "run_stage",
        "mechanism_role",
        "mechanism_profile",
        "mechanism_strength_factor",
        "mechanism_strength",
        "absolute_mechanism_strength",
        "split_orientation",
        "matched_random_role",
        "matched_random_available",
        "random_seed",
        "grid_size",
        "dx",
        "dt",
        "dt_scale",
        "drive_frequency",
        "drive_cutoff_time",
        "target_reference_work_per_source_area",
        "primary_work_per_source_area",
        "work_per_area_relative_error",
        "post_cutoff_external_positive_work",
        "no_post_cutoff_external_work",
        "energy_accounting_clean",
        "pattern_memory_pair_count",
        "pattern_memory_score",
        "pattern_memory_min",
        "pattern_memory_std",
        "instrumented_return_frame_count",
        "conservative_major_peaks",
        "conservative_refocus_peaks",
        "default_major_peaks_at_0p30",
        "default_refocus_peaks_at_0p30",
        "loose_major_peaks_at_0p25",
        "loose_refocus_peaks_at_0p25",
        "return_timing_comb_score",
        "off_comb_energy_ratio",
        "shell_phase_coherence_mean",
        "radial_phase_coherence_mean",
        "angular_phase_coherence_mean",
        "modal_participation_ratio",
        "tail_outer_to_shell_mean",
        "no_exit",
        "global_outer_false",
        "outer_shell_below_gate",
        "clean_gates_passed",
        "profile_strength_l2",
        "random_strength_match_error",
    ]


def _by_return_fields() -> list[str]:
    return [
        "variant",
        "cubic_memory_tradeoff_classification",
        "run_stage",
        "mechanism_role",
        "mechanism_profile",
        "mechanism_strength_factor",
        "split_orientation",
        "from_frame_id",
        "to_frame_id",
        "from_peak_rank",
        "to_peak_rank",
        "from_time",
        "to_time",
        "signed_similarity",
        "pattern_memory_score",
        "matched_node_count",
    ]


def _comparison_fields() -> list[str]:
    return [
        "cubic_memory_tradeoff_classification",
        "run_stage",
        "variant",
        "mechanism_role",
        "mechanism_profile",
        "mechanism_strength_factor",
        "split_orientation",
        "matched_random_role",
        "matched_random_available",
        "memory_delta_vs_neutral",
        "memory_delta_vs_matched_random",
        "strict_major_delta_vs_neutral",
        "strict_refocus_delta_vs_neutral",
        "preserves_strict_9_8",
        "comb_score_delta_vs_neutral",
        "off_comb_delta_vs_neutral",
        "modal_participation_delta_vs_neutral",
        "clean_gates_passed",
        "beats_neutral_memory",
        "beats_matched_random_memory",
    ]
