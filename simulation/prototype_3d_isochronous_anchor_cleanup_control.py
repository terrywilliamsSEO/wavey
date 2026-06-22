"""Fixed 41^3 cleanup control for the isochronous cubic-memory anchor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig
from .prototype_3d_cutoff_phase_map import threshold_robust_refocusing_scores
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _boundary_config as _interference_boundary_config
from .prototype_3d_isochronous_cubic_memory_anchor import (
    IsochronousCubicMemoryAnchorOptions,
    _by_return_fields as _anchor_by_return_fields,
    _summary_fields as _anchor_summary_fields,
)
from .prototype_3d_refocusing_engineering import _lifecycle_options
from .prototype_3d_source_sponge import _write_csv
from .prototype_3d_spatial_memory_mechanism_lab import (
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


ISOCHRONOUS_ANCHOR_CLEANUP_ROLES = (
    "neutral_reference",
    "random_equivalent_0p5x",
    "isochronous_anchor_0p5x_reference",
    "isochronous_anchor_0p5x_smooth_taper",
    "isochronous_anchor_0p5x_wide_smooth_taper",
    "isochronous_anchor_0p5x_weaker_compensation",
    "smooth_radial_compensation_only",
)


@dataclass(frozen=True)
class IsochronousAnchorCleanupOptions(IsochronousCubicMemoryAnchorOptions):
    """Options for the fixed 41^3 isochronous-anchor cleanup control."""

    off_comb_tolerance: float = 0.005


def run_3d_isochronous_anchor_cleanup_control(
    base_config: SimulationConfig,
    *,
    options: IsochronousAnchorCleanupOptions | None = None,
) -> dict[str, Any]:
    """Run the fixed 41^3 isochronous-anchor cleanup control."""

    options = options or IsochronousAnchorCleanupOptions()
    violations = validate_isochronous_anchor_cleanup_guardrails(options)
    if violations:
        raise ValueError("Isochronous anchor cleanup guardrail violation: " + "; ".join(violations))

    control_id = datetime.now().strftime("isochronous_anchor_cleanup_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    summary_rows, by_return_rows, comparison_rows, artifact_rows = _run_cleanup_stage(base_config, options, root)
    classification = classify_isochronous_anchor_cleanup(summary_rows, comparison_rows, options)
    for row_set in (summary_rows, by_return_rows, comparison_rows):
        for row in row_set:
            row["isochronous_anchor_cleanup_classification"] = classification["label"]

    summary_csv = root / "isochronous_anchor_cleanup_summary.csv"
    by_return_csv = root / "isochronous_anchor_cleanup_by_return.csv"
    comparison_csv = root / "isochronous_anchor_cleanup_comparison.csv"
    report_path = root / "isochronous_anchor_cleanup_report.md"
    summary_json = root / "isochronous_anchor_cleanup_summary.json"
    plots = {
        "memory": str(root / "cleanup_memory_plot.png"),
        "strict_count": str(root / "cleanup_strict_count_plot.png"),
        "comb_score": str(root / "cleanup_comb_score_plot.png"),
        "off_comb_energy": str(root / "cleanup_off_comb_energy_plot.png"),
    }

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(by_return_csv, by_return_rows, _by_return_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_artifact_csvs(root, artifact_rows)
    _plot_summary_bar(Path(plots["memory"]), summary_rows, "pattern_memory_score", "Pattern Memory")
    _plot_strict_count(Path(plots["strict_count"]), summary_rows, options)
    _plot_summary_bar(Path(plots["comb_score"]), summary_rows, "return_timing_comb_score", "Return Timing Comb Score")
    _plot_summary_bar(Path(plots["off_comb_energy"]), summary_rows, "off_comb_energy_ratio", "Off-Comb Energy Ratio")
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


def validate_isochronous_anchor_cleanup_guardrails(options: IsochronousAnchorCleanupOptions) -> list[str]:
    """Return guardrail violations for the fixed 41^3 cleanup control."""

    violations: list[str] = []
    if int(options.grid_size) != 41:
        violations.append("isochronous anchor cleanup is fixed to 41^3")
    if abs(float(options.fixed_cutoff) - 17.94) > 1.0e-9:
        violations.append("cutoff phase/timing tuning is forbidden")
    if abs(float(options.fixed_drive_frequency) - 0.92) > 1.0e-9:
        violations.append("frequency/source-shape tuning is forbidden")
    return violations


def build_isochronous_anchor_cleanup_variants(
    base_config: SimulationConfig,
    options: IsochronousAnchorCleanupOptions | None = None,
) -> list[Prototype3DConfig]:
    """Construct the fixed 41^3 cleanup-control variants."""

    options = options or IsochronousAnchorCleanupOptions()
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    lifecycle_options = _lifecycle_options(options)
    configs: list[Prototype3DConfig] = []
    for spec in _variant_specs():
        name = f"isochronous_anchor_cleanup_41_{spec['role']}"
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
        setattr(config, "_cleanup_role", spec["role"])
        setattr(config, "_spatial_memory_role", spec["role"])
        setattr(config, "_spatial_memory_profile", spec["profile"])
        setattr(config, "_mechanism_strength_factor", spec["strength_factor"])
        setattr(config, "_cleanup_kind", spec["kind"])
        setattr(config, "_matched_random_role", spec["matched_random_role"])
        setattr(config, "_dt_scale", options.dt_scale)
        configs.append(config)
    return configs


def classify_isochronous_anchor_cleanup(
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: IsochronousAnchorCleanupOptions | None = None,
) -> dict[str, Any]:
    """Classify the isochronous-anchor cleanup control."""

    options = options or IsochronousAnchorCleanupOptions()
    required_roles = ("neutral_reference", "random_equivalent_0p5x", "isochronous_anchor_0p5x_reference")
    by_role = {str(row.get("mechanism_role")): row for row in rows}
    neutral = by_role.get("neutral_reference")
    missing = [role for role in required_roles if role not in by_role]
    missing.extend([str(row.get("variant")) for row in rows if int(_float(row.get("pattern_memory_pair_count"))) <= 0])
    accounting_failures = [
        str(row.get("variant"))
        for row in rows
        if not _bool(row.get("energy_accounting_clean"))
        or not _bool(row.get("no_post_cutoff_external_work"))
    ]
    required_clean_failures = [
        str(by_role[role].get("variant"))
        for role in required_roles
        if role in by_role and not _bool(by_role[role].get("clean_gates_passed"))
    ]
    checks = {
        "missing_required_artifacts": missing,
        "accounting_failures": accounting_failures,
        "required_clean_gate_failures": required_clean_failures,
        "neutral_pattern_memory": neutral.get("pattern_memory_score") if neutral else None,
        "neutral_comb_score": neutral.get("return_timing_comb_score") if neutral else None,
        "neutral_off_comb_energy": neutral.get("off_comb_energy_ratio") if neutral else None,
        "strict_floor": f"{options.min_strict_major_peaks}/{options.min_strict_refocus_peaks}",
        "max_comb_score_drop": options.max_comb_score_drop,
        "off_comb_tolerance": options.off_comb_tolerance,
    }
    if missing or accounting_failures or required_clean_failures:
        return {
            "label": "invalid_cleanup_test",
            "reason": "Required controls, artifacts, clean gates, or work accounting failed.",
            "checks": checks,
        }

    cleanup_rows = [row for row in comparison_rows if row.get("cleanup_kind") == "cleanup"]
    eligible = [
        row
        for row in cleanup_rows
        if _bool(row.get("matched_random_available"))
        and _bool(row.get("clean_gates_passed"))
        and _bool(row.get("beats_neutral_memory"))
        and _bool(row.get("beats_matched_random_memory"))
        and _bool(row.get("preserves_strict_9_8"))
        and _bool(row.get("comb_near_neutral"))
    ]
    supported = [row for row in eligible if _bool(row.get("off_comb_within_tolerance"))]
    memory_only = [row for row in eligible if not _bool(row.get("off_comb_within_tolerance"))]
    best_pool = supported or memory_only or cleanup_rows or comparison_rows
    best = max(
        best_pool,
        key=lambda row: (
            _bool(row.get("preserves_strict_9_8")),
            _bool(row.get("comb_near_neutral")),
            _bool(row.get("off_comb_within_tolerance")),
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
            "best_comb_delta_vs_neutral": best.get("comb_score_delta_vs_neutral"),
            "best_off_comb_delta_vs_neutral": best.get("off_comb_delta_vs_neutral"),
            "best_preserves_strict_9_8": best.get("preserves_strict_9_8"),
            "best_comb_near_neutral": best.get("comb_near_neutral"),
            "best_off_comb_within_tolerance": best.get("off_comb_within_tolerance"),
        }
    )
    if supported:
        return {
            "label": "isochronous_anchor_cleanup_supported",
            "reason": "A cleanup row preserved memory, strict 9/8, near-neutral comb score, clean gates, and off-comb energy within tolerance of neutral.",
            "best_variant": best.get("variant"),
            "best_role": best.get("mechanism_role"),
            "checks": checks,
        }
    if memory_only:
        return {
            "label": "cleanup_memory_only_tradeoff",
            "reason": "A cleanup row preserved memory, strict 9/8, and near-neutral comb score, but off-comb energy still worsened beyond tolerance.",
            "best_variant": best.get("variant"),
            "best_role": best.get("mechanism_role"),
            "checks": checks,
        }
    return {
        "label": "cleanup_no_signal",
        "reason": "No cleanup row preserved the anchor memory advantage over neutral and matched randomized control with strict 9/8 and near-neutral comb.",
        "best_variant": best.get("variant"),
        "best_role": best.get("mechanism_role"),
        "checks": checks,
    }


def _run_cleanup_stage(
    base_config: SimulationConfig,
    options: IsochronousAnchorCleanupOptions,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    configs = build_isochronous_anchor_cleanup_variants(base_config, options)
    lifecycle_options = _lifecycle_options(options)
    stage_root = root / "isochronous_anchor_cleanup_41"
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
        _add_lab_fields(summary, config, "isochronous_anchor_cleanup_41", target_work_per_area, memory, result, options)
        _add_cleanup_fields(summary, config)
        summary_rows.append(summary)
        for pair in memory["pair_rows"]:
            pair["run_stage"] = "isochronous_anchor_cleanup_41"
            pair["mechanism_role"] = getattr(config, "_cleanup_role", "")
            pair["mechanism_profile"] = getattr(config, "_spatial_memory_profile", "")
            pair["mechanism_strength_factor"] = getattr(config, "_mechanism_strength_factor", 0.0)
            pair["cleanup_kind"] = getattr(config, "_cleanup_kind", "")
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


def _add_cleanup_fields(row: dict[str, Any], config: Prototype3DConfig) -> None:
    row["mechanism_strength_factor"] = getattr(config, "_mechanism_strength_factor", 0.0)
    row["cleanup_kind"] = getattr(config, "_cleanup_kind", "")
    row["matched_random_role"] = getattr(config, "_matched_random_role", "")
    row["matched_random_available"] = bool(row["matched_random_role"])


def _comparison_rows(
    summary_rows: list[dict[str, Any]],
    options: IsochronousAnchorCleanupOptions,
) -> list[dict[str, Any]]:
    neutral = next((row for row in summary_rows if row.get("mechanism_role") == "neutral_reference"), {})
    matched_random = next((row for row in summary_rows if row.get("mechanism_role") == "random_equivalent_0p5x"), {})
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        role = str(row.get("mechanism_role"))
        if role in {"neutral_reference", "random_equivalent_0p5x"}:
            continue
        memory_delta_vs_neutral = _float(row.get("pattern_memory_score")) - _float(neutral.get("pattern_memory_score"))
        memory_delta_vs_random = _float(row.get("pattern_memory_score")) - _float(matched_random.get("pattern_memory_score"))
        comb_delta = _float(row.get("return_timing_comb_score")) - _float(neutral.get("return_timing_comb_score"))
        off_comb_delta = _float(row.get("off_comb_energy_ratio")) - _float(neutral.get("off_comb_energy_ratio"))
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
                "cleanup_kind": row.get("cleanup_kind"),
                "matched_random_role": row.get("matched_random_role"),
                "matched_random_available": bool(matched_random),
                "memory_delta_vs_neutral": memory_delta_vs_neutral,
                "memory_delta_vs_matched_random": memory_delta_vs_random,
                "strict_major_delta_vs_neutral": _int(row.get("conservative_major_peaks")) - _int(neutral.get("conservative_major_peaks")),
                "strict_refocus_delta_vs_neutral": _int(row.get("conservative_refocus_peaks")) - _int(neutral.get("conservative_refocus_peaks")),
                "preserves_strict_9_8": preserves_strict,
                "comb_score_delta_vs_neutral": comb_delta,
                "comb_near_neutral": abs(comb_delta) <= float(options.max_comb_score_drop),
                "off_comb_delta_vs_neutral": off_comb_delta,
                "off_comb_within_tolerance": off_comb_delta <= float(options.off_comb_tolerance) + EPSILON,
                "modal_participation_delta_vs_neutral": _float(row.get("modal_participation_ratio")) - _float(neutral.get("modal_participation_ratio")),
                "clean_gates_passed": row.get("clean_gates_passed"),
                "beats_neutral_memory": memory_delta_vs_neutral > EPSILON,
                "beats_matched_random_memory": bool(matched_random) and memory_delta_vs_random > EPSILON,
            }
        )
    return out


def _write_artifact_csvs(root: Path, artifact_rows: list[dict[str, Any]]) -> None:
    for artifact in artifact_rows:
        rows = list(artifact["rows"])
        if rows:
            _write_csv(root / f"isochronous_anchor_cleanup_{artifact['name']}.csv", rows, list(artifact["fields"]))


def _write_report(
    path: Path,
    control_id: str,
    classification: dict[str, Any],
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: IsochronousAnchorCleanupOptions,
) -> None:
    lines = [
        f"# Isochronous Anchor Cleanup Control: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Guardrails",
        "",
        "- This is a fixed 41^3 passive cleanup control, not a cutoff/source tuning pass.",
        "- Cutoff, frequency, source shape, active pulses, resonators, 51^3, and 61^3 are not tuning surfaces here.",
        f"- Cleanup support requires off-comb energy no more than neutral + `{_format(options.off_comb_tolerance)}`.",
        "",
        "## Summary",
        "",
        "| Variant | Role | Profile | Strength | Memory | Strict | Default | Loose | Comb | Off-comb | Clean |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('variant')} | {row.get('mechanism_role')} | {row.get('mechanism_profile')} | "
            f"{_format(row.get('mechanism_strength_factor'))} | "
            f"{_format(row.get('pattern_memory_score'))} | "
            f"{_int(row.get('conservative_major_peaks'))}/{_int(row.get('conservative_refocus_peaks'))} | "
            f"{_int(row.get('default_major_peaks_at_0p30'))}/{_int(row.get('default_refocus_peaks_at_0p30'))} | "
            f"{_int(row.get('loose_major_peaks_at_0p25'))}/{_int(row.get('loose_refocus_peaks_at_0p25'))} | "
            f"{_format(row.get('return_timing_comb_score'))} | "
            f"{_format(row.get('off_comb_energy_ratio'))} | "
            f"{row.get('clean_gates_passed')} |"
        )
    lines.extend(
        [
            "",
            "## Comparisons",
            "",
            "| Role | Kind | Memory delta vs neutral | Memory delta vs random | Strict 9/8 | Comb near neutral | Off-comb within tolerance | Clean |",
            "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            f"| {row.get('mechanism_role')} | {row.get('cleanup_kind')} | "
            f"{_format(row.get('memory_delta_vs_neutral'))} | "
            f"{_format(row.get('memory_delta_vs_matched_random'))} | "
            f"{row.get('preserves_strict_9_8')} | {row.get('comb_near_neutral')} | "
            f"{row.get('off_comb_within_tolerance')} | {row.get('clean_gates_passed')} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `isochronous_anchor_cleanup_summary.csv`",
            "- `isochronous_anchor_cleanup_by_return.csv`",
            "- `isochronous_anchor_cleanup_comparison.csv`",
            "- `cleanup_memory_plot.png`",
            "- `cleanup_strict_count_plot.png`",
            "- `cleanup_comb_score_plot.png`",
            "- `cleanup_off_comb_energy_plot.png`",
            "",
            "## Interpretation",
            "",
            _interpretation_text(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation_text(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "isochronous_anchor_cleanup_supported":
        return "A fixed cleanup row kept the compensated-memory signal while bringing off-comb energy back near neutral. This is still 41^3-only evidence."
    if label == "cleanup_memory_only_tradeoff":
        return "A cleanup row kept memory, strict count, and comb behavior, but the off-comb penalty remained."
    if label == "cleanup_no_signal":
        return "The fixed cleanup rows did not preserve the memory advantage over neutral and matched randomized control under strict and comb constraints."
    return "The cleanup test was invalid because required controls, artifacts, clean gates, or accounting failed."


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


def _plot_strict_count(path: Path, rows: list[dict[str, Any]], options: IsochronousAnchorCleanupOptions) -> None:
    labels = [str(row.get("mechanism_role")) for row in rows]
    majors = [_float(row.get("conservative_major_peaks")) for row in rows]
    refocus = [_float(row.get("conservative_refocus_peaks")) for row in rows]
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.75), 4), dpi=140)
    x_values = list(range(len(labels)))
    ax.bar([x - 0.18 for x in x_values], majors, width=0.35, label="Strict major")
    ax.bar([x + 0.18 for x in x_values], refocus, width=0.35, label="Strict refocus")
    ax.axhline(float(options.min_strict_major_peaks), color="black", linestyle="--", linewidth=1, alpha=0.45)
    ax.axhline(float(options.min_strict_refocus_peaks), color="black", linestyle=":", linewidth=1, alpha=0.45)
    ax.set_xticks(x_values)
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=6)
    ax.set_title("Strict Return Counts")
    ax.legend(fontsize=7)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _variant_specs() -> list[dict[str, Any]]:
    return [
        _spec("neutral_reference", "none", 0.0, 0.0, "control", ""),
        _spec("random_equivalent_0p5x", "random_equivalent", 0.5, 0.5, "control", ""),
        _spec("isochronous_anchor_0p5x_reference", "isochronous_cubic_anchor", 0.5, 0.5, "reference", "random_equivalent_0p5x"),
        _spec("isochronous_anchor_0p5x_smooth_taper", "isochronous_cubic_anchor_smooth_taper", 0.5, 0.5, "cleanup", "random_equivalent_0p5x"),
        _spec("isochronous_anchor_0p5x_wide_smooth_taper", "isochronous_cubic_anchor_wide_smooth_taper", 0.5, 0.5, "cleanup", "random_equivalent_0p5x"),
        _spec("isochronous_anchor_0p5x_weaker_compensation", "isochronous_cubic_anchor_weaker_compensation", 0.5, 0.5, "cleanup", "random_equivalent_0p5x"),
        _spec("smooth_radial_compensation_only", "smooth_radial_compensation", 0.5, 0.5, "diagnostic", ""),
    ]


def _spec(
    role: str,
    profile: str,
    strength_factor: float,
    signed_factor: float,
    kind: str,
    matched_random_role: str,
) -> dict[str, Any]:
    return {
        "role": role,
        "profile": profile,
        "strength_factor": strength_factor,
        "signed_factor": signed_factor,
        "kind": kind,
        "matched_random_role": matched_random_role,
    }


def _summary_fields() -> list[str]:
    return _replace_anchor_fields(_anchor_summary_fields())


def _by_return_fields() -> list[str]:
    return _replace_anchor_fields(_anchor_by_return_fields())


def _replace_anchor_fields(fields: list[str]) -> list[str]:
    out: list[str] = []
    for field in fields:
        if field == "isochronous_cubic_anchor_classification":
            out.append("isochronous_anchor_cleanup_classification")
        elif field == "anchor_kind":
            out.append("cleanup_kind")
        elif field == "off_comb_not_worse":
            out.append("off_comb_within_tolerance")
        else:
            out.append(field)
    return out


def _comparison_fields() -> list[str]:
    return [
        "isochronous_anchor_cleanup_classification",
        "run_stage",
        "variant",
        "mechanism_role",
        "mechanism_profile",
        "mechanism_strength_factor",
        "cleanup_kind",
        "matched_random_role",
        "matched_random_available",
        "memory_delta_vs_neutral",
        "memory_delta_vs_matched_random",
        "strict_major_delta_vs_neutral",
        "strict_refocus_delta_vs_neutral",
        "preserves_strict_9_8",
        "comb_score_delta_vs_neutral",
        "comb_near_neutral",
        "off_comb_delta_vs_neutral",
        "off_comb_within_tolerance",
        "modal_participation_delta_vs_neutral",
        "clean_gates_passed",
        "beats_neutral_memory",
        "beats_matched_random_memory",
    ]
