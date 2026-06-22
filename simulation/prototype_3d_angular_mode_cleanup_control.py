"""Fixed 41^3 angular-mode cleanup control for the isochronous anchor."""

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


ANGULAR_MODE_CLEANUP_ROLES = (
    "neutral_reference",
    "random_equivalent_0p5x",
    "isochronous_anchor_0p5x_reference",
    "angular_cleanup_only_weak",
    "anchor_0p5x_weak_angular_cleanup",
    "anchor_0p5x_medium_angular_cleanup",
    "anchor_0p5x_cubic_preserving_angular_cleanup",
    "randomized_matched_damping_control",
)


@dataclass(frozen=True)
class AngularModeCleanupOptions(IsochronousCubicMemoryAnchorOptions):
    """Options for the fixed 41^3 angular-mode cleanup control."""

    angular_cleanup_strength: float = 0.006
    medium_cleanup_multiplier: float = 2.0
    anchor_strength_factor: float = 0.5
    min_off_comb_reduction: float = 0.0


def run_3d_angular_mode_cleanup_control(
    base_config: SimulationConfig,
    *,
    options: AngularModeCleanupOptions | None = None,
) -> dict[str, Any]:
    """Run the fixed 41^3 angular-mode cleanup control."""

    options = options or AngularModeCleanupOptions()
    violations = validate_angular_mode_cleanup_guardrails(options)
    if violations:
        raise ValueError("Angular-mode cleanup guardrail violation: " + "; ".join(violations))

    control_id = datetime.now().strftime("angular_mode_cleanup_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    summary_rows, by_return_rows, comparison_rows, spectrum_rows, artifact_rows = _run_angular_mode_cleanup_stage(base_config, options, root)
    classification = classify_angular_mode_cleanup(summary_rows, comparison_rows, options)
    for row_set in (summary_rows, by_return_rows, comparison_rows, spectrum_rows):
        for row in row_set:
            row["angular_mode_cleanup_classification"] = classification["label"]

    summary_csv = root / "angular_mode_cleanup_summary.csv"
    by_return_csv = root / "angular_mode_cleanup_by_return.csv"
    comparison_csv = root / "angular_mode_cleanup_comparison.csv"
    spectrum_csv = root / "angular_mode_spectrum.csv"
    report_path = root / "angular_mode_cleanup_report.md"
    summary_json = root / "angular_mode_cleanup_summary.json"
    plots = {
        "memory": str(root / "angular_cleanup_memory_plot.png"),
        "strict_count": str(root / "angular_cleanup_strict_count_plot.png"),
        "comb_score": str(root / "angular_cleanup_comb_score_plot.png"),
        "off_comb_energy": str(root / "angular_cleanup_off_comb_energy_plot.png"),
        "angular_mode_spectrum": str(root / "angular_mode_spectrum_plot.png"),
    }

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(by_return_csv, by_return_rows, _by_return_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_csv(spectrum_csv, spectrum_rows, _spectrum_fields())
    _write_artifact_csvs(root, artifact_rows)
    _plot_summary_bar(Path(plots["memory"]), summary_rows, "pattern_memory_score", "Pattern Memory")
    _plot_strict_count(Path(plots["strict_count"]), summary_rows, options)
    _plot_summary_bar(Path(plots["comb_score"]), summary_rows, "return_timing_comb_score", "Return Timing Comb Score")
    _plot_summary_bar(Path(plots["off_comb_energy"]), summary_rows, "off_comb_energy_ratio", "Off-Comb Energy Ratio")
    _plot_angular_mode_spectrum(Path(plots["angular_mode_spectrum"]), spectrum_rows)
    _write_report(report_path, control_id, classification, summary_rows, comparison_rows, options)
    save_json(
        summary_json,
        {
            "control_id": control_id,
            "classification": classification,
            "summary_csv": str(summary_csv),
            "by_return_csv": str(by_return_csv),
            "comparison_csv": str(comparison_csv),
            "angular_mode_spectrum_csv": str(spectrum_csv),
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
        "angular_mode_spectrum_rows": spectrum_rows,
        "summary_csv": str(summary_csv),
        "by_return_csv": str(by_return_csv),
        "comparison_csv": str(comparison_csv),
        "angular_mode_spectrum_csv": str(spectrum_csv),
        "report_path": str(report_path),
        "summary_json": str(summary_json),
        "plots": plots,
        "path": str(root),
    }


def validate_angular_mode_cleanup_guardrails(options: AngularModeCleanupOptions) -> list[str]:
    """Return guardrail violations for the fixed 41^3 angular cleanup control."""

    violations: list[str] = []
    if int(options.grid_size) != 41:
        violations.append("angular-mode cleanup control is fixed to 41^3")
    if abs(float(options.fixed_cutoff) - 17.94) > 1.0e-9:
        violations.append("cutoff phase/timing tuning is forbidden")
    if abs(float(options.fixed_drive_frequency) - 0.92) > 1.0e-9:
        violations.append("frequency/source-shape tuning is forbidden")
    if float(options.angular_cleanup_strength) <= 0.0:
        violations.append("angular cleanup strength must stay positive for the fixed damping-shell test")
    return violations


def build_angular_mode_cleanup_variants(
    base_config: SimulationConfig,
    options: AngularModeCleanupOptions | None = None,
) -> list[Prototype3DConfig]:
    """Construct the fixed 41^3 angular-mode cleanup variants."""

    options = options or AngularModeCleanupOptions()
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    lifecycle_options = _lifecycle_options(options)
    configs: list[Prototype3DConfig] = []
    for spec in _variant_specs(options):
        name = f"angular_mode_cleanup_41_{spec['role']}"
        config = _interference_boundary_config(name, base_config, lifecycle_options, source_width, "cubic", cubic_sign=-1.0)
        config.grid_size = int(options.grid_size)
        config.dt = float(base_config.dt) * float(options.dt_scale)
        config.steps = max(1, int(round(float(options.physical_duration) / max(config.dt, EPSILON))))
        config.drive_cutoff_time = float(options.fixed_cutoff)
        config.drive_frequency = float(options.fixed_drive_frequency)
        config.memory_mechanism_profile = str(spec["profile"])
        config.memory_mechanism_strength = float(spec["memory_strength"])
        config.memory_mechanism_seed = int(options.random_seed) + int(spec["seed_offset"])
        config.memory_mechanism_shell_radius = float(options.shell_window_radius + 0.5 * _shell_width_from_options(options, config))
        config.memory_mechanism_shell_width = float(_shell_width_from_options(options, config))
        setattr(config, "_angular_cleanup_role", spec["role"])
        setattr(config, "_spatial_memory_role", spec["role"])
        setattr(config, "_spatial_memory_profile", spec["profile"])
        setattr(config, "_mechanism_strength_factor", spec["mechanism_strength_factor"])
        setattr(config, "_anchor_strength_factor", spec["anchor_strength_factor"])
        setattr(config, "_anchor_memory_strength", float(options.mechanism_strength) * float(spec["anchor_strength_factor"]))
        setattr(config, "_angular_cleanup_strength_factor", spec["angular_strength_factor"])
        setattr(config, "_angular_cleanup_strength", spec["angular_cleanup_strength"])
        setattr(config, "_angular_cleanup_kind", spec["kind"])
        setattr(config, "_matched_random_role", spec["matched_random_role"])
        setattr(config, "_dt_scale", options.dt_scale)
        configs.append(config)
    return configs


def classify_angular_mode_cleanup(
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: AngularModeCleanupOptions | None = None,
) -> dict[str, Any]:
    """Classify the angular-mode cleanup control."""

    options = options or AngularModeCleanupOptions()
    required_roles = (
        "neutral_reference",
        "random_equivalent_0p5x",
        "isochronous_anchor_0p5x_reference",
        "randomized_matched_damping_control",
    )
    by_role = {str(row.get("mechanism_role")): row for row in rows}
    neutral = by_role.get("neutral_reference")
    anchor = by_role.get("isochronous_anchor_0p5x_reference")
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
        "anchor_off_comb_energy": anchor.get("off_comb_energy_ratio") if anchor else None,
        "strict_floor": f"{options.min_strict_major_peaks}/{options.min_strict_refocus_peaks}",
        "max_comb_score_drop": options.max_comb_score_drop,
        "min_off_comb_reduction": options.min_off_comb_reduction,
    }
    if missing or accounting_failures or required_clean_failures:
        return {
            "label": "invalid_angular_cleanup_test",
            "reason": "Required controls, artifacts, clean gates, or work accounting failed.",
            "checks": checks,
        }

    cleanup_rows = [row for row in comparison_rows if row.get("angular_cleanup_kind") == "cleanup"]
    memory_signal = [
        row
        for row in cleanup_rows
        if _bool(row.get("clean_gates_passed"))
        and _bool(row.get("beats_neutral_memory"))
        and _bool(row.get("beats_random_0p5_memory"))
        and _bool(row.get("beats_random_damping_memory"))
    ]
    supported = [
        row
        for row in memory_signal
        if _bool(row.get("preserves_strict_9_8"))
        and _bool(row.get("comb_near_neutral"))
        and _bool(row.get("off_comb_reduced_vs_anchor"))
    ]
    memory_only = [
        row
        for row in memory_signal
        if not (
            _bool(row.get("preserves_strict_9_8"))
            and _bool(row.get("comb_near_neutral"))
            and _bool(row.get("off_comb_reduced_vs_anchor"))
        )
    ]
    best_pool = supported or memory_only or cleanup_rows or comparison_rows
    best = max(
        best_pool,
        key=lambda row: (
            _bool(row.get("off_comb_reduced_vs_anchor")),
            _bool(row.get("preserves_strict_9_8")),
            _bool(row.get("comb_near_neutral")),
            _float(row.get("memory_delta_vs_neutral")),
            _float(row.get("memory_delta_vs_random_0p5")),
        ),
        default={},
    )
    checks.update(
        {
            "best_role": best.get("mechanism_role"),
            "best_memory_delta_vs_neutral": best.get("memory_delta_vs_neutral"),
            "best_memory_delta_vs_random_0p5": best.get("memory_delta_vs_random_0p5"),
            "best_memory_delta_vs_random_damping": best.get("memory_delta_vs_random_damping"),
            "best_comb_delta_vs_neutral": best.get("comb_score_delta_vs_neutral"),
            "best_off_comb_delta_vs_anchor": best.get("off_comb_delta_vs_anchor"),
            "best_preserves_strict_9_8": best.get("preserves_strict_9_8"),
            "best_comb_near_neutral": best.get("comb_near_neutral"),
            "best_off_comb_reduced_vs_anchor": best.get("off_comb_reduced_vs_anchor"),
        }
    )
    if supported:
        return {
            "label": "angular_cleanup_supported",
            "reason": "A fixed angular cleanup row beat neutral and both randomized controls on memory, preserved strict 9/8 and near-neutral comb, reduced off-comb versus the anchor reference, and passed clean gates.",
            "best_variant": best.get("variant"),
            "best_role": best.get("mechanism_role"),
            "checks": checks,
        }
    if memory_only:
        return {
            "label": "angular_cleanup_memory_only_tradeoff",
            "reason": "An angular cleanup row preserved a memory advantage over controls, but strict count, comb score, or off-comb reduction still traded down.",
            "best_variant": best.get("variant"),
            "best_role": best.get("mechanism_role"),
            "checks": checks,
        }
    return {
        "label": "angular_cleanup_no_signal",
        "reason": "No angular cleanup row beat neutral and randomized controls on spatial-pattern memory.",
        "best_variant": best.get("variant"),
        "best_role": best.get("mechanism_role"),
        "checks": checks,
    }


def _run_angular_mode_cleanup_stage(
    base_config: SimulationConfig,
    options: AngularModeCleanupOptions,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    configs = build_angular_mode_cleanup_variants(base_config, options)
    lifecycle_options = _lifecycle_options(options)
    stage_root = root / "angular_mode_cleanup_41"
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
        _add_lab_fields(summary, config, "angular_mode_cleanup_41", target_work_per_area, memory, result, options)
        _add_angular_cleanup_fields(summary, config)
        summary_rows.append(summary)
        for pair in memory["pair_rows"]:
            pair["run_stage"] = "angular_mode_cleanup_41"
            pair["mechanism_role"] = getattr(config, "_angular_cleanup_role", "")
            pair["mechanism_profile"] = getattr(config, "_spatial_memory_profile", "")
            pair["mechanism_strength_factor"] = getattr(config, "_mechanism_strength_factor", 0.0)
            pair["anchor_strength_factor"] = getattr(config, "_anchor_strength_factor", 0.0)
            pair["angular_cleanup_strength_factor"] = getattr(config, "_angular_cleanup_strength_factor", 0.0)
            pair["angular_cleanup_kind"] = getattr(config, "_angular_cleanup_kind", "")
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
    spectrum_rows = _angular_mode_spectrum_rows(summary_rows, angular_rows)
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
    return summary_rows, by_return_rows, comparison_rows, spectrum_rows, artifact_rows


def _add_angular_cleanup_fields(row: dict[str, Any], config: Prototype3DConfig) -> None:
    row["mechanism_strength_factor"] = getattr(config, "_mechanism_strength_factor", 0.0)
    row["anchor_strength_factor"] = getattr(config, "_anchor_strength_factor", 0.0)
    row["angular_cleanup_strength_factor"] = getattr(config, "_angular_cleanup_strength_factor", 0.0)
    row["angular_cleanup_strength"] = getattr(config, "_angular_cleanup_strength", 0.0)
    row["angular_cleanup_kind"] = getattr(config, "_angular_cleanup_kind", "")
    row["matched_random_role"] = getattr(config, "_matched_random_role", "")
    row["matched_random_available"] = bool(row["matched_random_role"])


def _comparison_rows(
    summary_rows: list[dict[str, Any]],
    options: AngularModeCleanupOptions,
) -> list[dict[str, Any]]:
    neutral = next((row for row in summary_rows if row.get("mechanism_role") == "neutral_reference"), {})
    random_0p5 = next((row for row in summary_rows if row.get("mechanism_role") == "random_equivalent_0p5x"), {})
    anchor = next((row for row in summary_rows if row.get("mechanism_role") == "isochronous_anchor_0p5x_reference"), {})
    random_damping = next((row for row in summary_rows if row.get("mechanism_role") == "randomized_matched_damping_control"), {})
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        role = str(row.get("mechanism_role"))
        if role == "neutral_reference":
            continue
        memory_delta_vs_neutral = _float(row.get("pattern_memory_score")) - _float(neutral.get("pattern_memory_score"))
        memory_delta_vs_random_0p5 = _float(row.get("pattern_memory_score")) - _float(random_0p5.get("pattern_memory_score"))
        memory_delta_vs_random_damping = _float(row.get("pattern_memory_score")) - _float(random_damping.get("pattern_memory_score"))
        memory_delta_vs_anchor = _float(row.get("pattern_memory_score")) - _float(anchor.get("pattern_memory_score"))
        comb_delta = _float(row.get("return_timing_comb_score")) - _float(neutral.get("return_timing_comb_score"))
        off_comb_delta_neutral = _float(row.get("off_comb_energy_ratio")) - _float(neutral.get("off_comb_energy_ratio"))
        off_comb_delta_anchor = _float(row.get("off_comb_energy_ratio")) - _float(anchor.get("off_comb_energy_ratio"))
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
                "anchor_strength_factor": row.get("anchor_strength_factor"),
                "angular_cleanup_strength_factor": row.get("angular_cleanup_strength_factor"),
                "angular_cleanup_strength": row.get("angular_cleanup_strength"),
                "angular_cleanup_kind": row.get("angular_cleanup_kind"),
                "matched_random_role": row.get("matched_random_role"),
                "matched_random_available": bool(random_0p5) and bool(random_damping),
                "memory_delta_vs_neutral": memory_delta_vs_neutral,
                "memory_delta_vs_random_0p5": memory_delta_vs_random_0p5,
                "memory_delta_vs_random_damping": memory_delta_vs_random_damping,
                "memory_delta_vs_anchor": memory_delta_vs_anchor,
                "strict_major_delta_vs_neutral": _int(row.get("conservative_major_peaks")) - _int(neutral.get("conservative_major_peaks")),
                "strict_refocus_delta_vs_neutral": _int(row.get("conservative_refocus_peaks")) - _int(neutral.get("conservative_refocus_peaks")),
                "preserves_strict_9_8": preserves_strict,
                "comb_score_delta_vs_neutral": comb_delta,
                "comb_near_neutral": abs(comb_delta) <= float(options.max_comb_score_drop),
                "off_comb_delta_vs_neutral": off_comb_delta_neutral,
                "off_comb_delta_vs_anchor": off_comb_delta_anchor,
                "off_comb_reduced_vs_anchor": off_comb_delta_anchor <= -float(options.min_off_comb_reduction) - EPSILON,
                "modal_participation_delta_vs_neutral": _float(row.get("modal_participation_ratio")) - _float(neutral.get("modal_participation_ratio")),
                "clean_gates_passed": row.get("clean_gates_passed"),
                "beats_neutral_memory": memory_delta_vs_neutral > EPSILON,
                "beats_random_0p5_memory": bool(random_0p5) and memory_delta_vs_random_0p5 > EPSILON,
                "beats_random_damping_memory": bool(random_damping) and memory_delta_vs_random_damping > EPSILON,
            }
        )
    return out


def _angular_mode_spectrum_rows(summary_rows: list[dict[str, Any]], angular_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary_by_variant = {str(row.get("variant")): row for row in summary_rows}
    grouped: dict[str, dict[tuple[str, str], dict[str, float]]] = {}
    for row in angular_rows:
        variant = str(row.get("variant"))
        polar = str(row.get("polar_bin"))
        theta = str(row.get("theta_bin"))
        if polar == "octant":
            continue
        key = (polar, theta)
        bucket = grouped.setdefault(variant, {}).setdefault(key, {"energy": 0.0, "coherence_energy": 0.0})
        energy = _float(row.get("shell_energy"))
        bucket["energy"] += energy
        bucket["coherence_energy"] += energy * _float(row.get("phase_coherence"))
    out: list[dict[str, Any]] = []
    for variant, sectors in grouped.items():
        energies = np.asarray([bucket["energy"] for bucket in sectors.values()], dtype=float)
        total = float(np.sum(energies))
        participation = float((np.sum(energies) ** 2) / max(float(np.sum(energies**2)), EPSILON)) if energies.size else 0.0
        dominant_fraction = float(np.max(energies) / max(total, EPSILON)) if energies.size else 0.0
        coherence_weighted = (
            float(sum(bucket["coherence_energy"] for bucket in sectors.values()) / max(total, EPSILON))
            if sectors
            else 0.0
        )
        summary = summary_by_variant.get(variant, {})
        out.append(
            {
                "variant": variant,
                "mechanism_role": summary.get("mechanism_role"),
                "mechanism_profile": summary.get("mechanism_profile"),
                "angular_cleanup_kind": summary.get("angular_cleanup_kind"),
                "angular_sector_count": len(sectors),
                "angular_sector_participation": participation,
                "angular_dominant_sector_fraction": dominant_fraction,
                "angular_energy_weighted_phase_coherence": coherence_weighted,
                "pattern_memory_score": summary.get("pattern_memory_score"),
                "off_comb_energy_ratio": summary.get("off_comb_energy_ratio"),
            }
        )
    return out


def _write_artifact_csvs(root: Path, artifact_rows: list[dict[str, Any]]) -> None:
    for artifact in artifact_rows:
        rows = list(artifact["rows"])
        if rows:
            _write_csv(root / f"angular_mode_cleanup_{artifact['name']}.csv", rows, list(artifact["fields"]))


def _write_report(
    path: Path,
    control_id: str,
    classification: dict[str, Any],
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: AngularModeCleanupOptions,
) -> None:
    lines = [
        f"# Angular-Mode Cleanup Control: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Guardrails",
        "",
        "- This is a fixed 41^3 passive angular-cleanup mechanism test, not a taper-tuning pass.",
        "- Cutoff, frequency, source shape, active pulses, resonators, default 51^3, and 61^3 are not tuning surfaces here.",
        "- Support requires memory above neutral, random 0.5x, and randomized damping controls; strict 9/8; near-neutral comb; and off-comb reduction versus the anchor reference.",
        "",
        "## Summary",
        "",
        "| Variant | Role | Profile | Anchor factor | Damping strength | Memory | Strict | Default | Loose | Comb | Off-comb | Clean |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('variant')} | {row.get('mechanism_role')} | {row.get('mechanism_profile')} | "
            f"{_format(row.get('anchor_strength_factor'))} | "
            f"{_format(row.get('angular_cleanup_strength'))} | "
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
            "| Role | Kind | Memory delta vs neutral | vs random 0.5x | vs random damping | Strict 9/8 | Comb near neutral | Off-comb reduced vs anchor | Clean |",
            "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            f"| {row.get('mechanism_role')} | {row.get('angular_cleanup_kind')} | "
            f"{_format(row.get('memory_delta_vs_neutral'))} | "
            f"{_format(row.get('memory_delta_vs_random_0p5'))} | "
            f"{_format(row.get('memory_delta_vs_random_damping'))} | "
            f"{row.get('preserves_strict_9_8')} | {row.get('comb_near_neutral')} | "
            f"{row.get('off_comb_reduced_vs_anchor')} | {row.get('clean_gates_passed')} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `angular_mode_cleanup_summary.csv`",
            "- `angular_mode_cleanup_by_return.csv`",
            "- `angular_mode_cleanup_comparison.csv`",
            "- `angular_mode_spectrum.csv`",
            "- `angular_cleanup_memory_plot.png`",
            "- `angular_cleanup_strict_count_plot.png`",
            "- `angular_cleanup_comb_score_plot.png`",
            "- `angular_cleanup_off_comb_energy_plot.png`",
            "- `angular_mode_spectrum_plot.png`",
            "",
            "## Interpretation",
            "",
            _interpretation_text(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation_text(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "angular_cleanup_supported":
        return "The fixed angular cleanup mechanism kept the compensated-memory signal and reduced off-comb relative to the anchor without sacrificing strict count or comb timing at 41^3."
    if label == "angular_cleanup_memory_only_tradeoff":
        return "The fixed angular cleanup rows kept a memory signal, but strict count, comb timing, or off-comb cleanup remained incomplete."
    if label == "angular_cleanup_no_signal":
        return "The fixed angular cleanup rows did not preserve a memory advantage over neutral and randomized controls."
    return "The angular cleanup test was invalid because required controls, artifacts, clean gates, or accounting failed."


def _plot_summary_bar(path: Path, rows: list[dict[str, Any]], key: str, title: str) -> None:
    labels = [str(row.get("mechanism_role")) for row in rows]
    values = [_float(row.get(key)) for row in rows]
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.8), 4), dpi=140)
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=6)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_strict_count(path: Path, rows: list[dict[str, Any]], options: AngularModeCleanupOptions) -> None:
    labels = [str(row.get("mechanism_role")) for row in rows]
    majors = [_float(row.get("conservative_major_peaks")) for row in rows]
    refocus = [_float(row.get("conservative_refocus_peaks")) for row in rows]
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.8), 4), dpi=140)
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


def _plot_angular_mode_spectrum(path: Path, rows: list[dict[str, Any]]) -> None:
    labels = [str(row.get("mechanism_role")) for row in rows]
    participation = [_float(row.get("angular_sector_participation")) for row in rows]
    dominant = [_float(row.get("angular_dominant_sector_fraction")) for row in rows]
    fig, ax1 = plt.subplots(figsize=(max(8, len(labels) * 0.8), 4.5), dpi=140)
    x_values = np.arange(len(labels), dtype=float)
    ax1.bar(x_values - 0.18, participation, width=0.35, label="Sector participation")
    ax1.set_ylabel("Angular sector participation")
    ax1.set_xticks(x_values)
    ax1.set_xticklabels(labels, rotation=35, ha="right", fontsize=6)
    ax1.grid(True, axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.bar(x_values + 0.18, dominant, width=0.35, color="tab:orange", alpha=0.75, label="Dominant fraction")
    ax2.set_ylabel("Dominant sector fraction")
    ax1.set_title("Angular-Mode Spectrum Proxy")
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _variant_specs(options: AngularModeCleanupOptions) -> list[dict[str, Any]]:
    weak = float(options.angular_cleanup_strength)
    medium = weak * float(options.medium_cleanup_multiplier)
    anchor_strength = float(options.mechanism_strength) * float(options.anchor_strength_factor)
    return [
        _spec("neutral_reference", "none", 0.0, 0.0, 0.0, "control", "", 0),
        _spec("random_equivalent_0p5x", "random_equivalent", anchor_strength, 0.5, 0.0, "control", "", 0),
        _spec("isochronous_anchor_0p5x_reference", "isochronous_cubic_anchor", anchor_strength, 0.5, 0.0, "reference", "random_equivalent_0p5x", 0),
        _spec("angular_cleanup_only_weak", "angular_high_mode_cleanup", weak, 0.0, 1.0, "diagnostic", "randomized_matched_damping_control", 0),
        _spec("anchor_0p5x_weak_angular_cleanup", "isochronous_anchor_angular_cleanup", weak, 0.5, 1.0, "cleanup", "random_equivalent_0p5x", 0),
        _spec("anchor_0p5x_medium_angular_cleanup", "isochronous_anchor_medium_angular_cleanup", medium, 0.5, float(options.medium_cleanup_multiplier), "cleanup", "random_equivalent_0p5x", 0),
        _spec("anchor_0p5x_cubic_preserving_angular_cleanup", "isochronous_anchor_cubic_preserving_angular_cleanup", weak, 0.5, 1.0, "cleanup", "random_equivalent_0p5x", 0),
        _spec("randomized_matched_damping_control", "random_angular_cleanup", weak, 0.0, 1.0, "random_damping", "", 9001),
    ]


def _spec(
    role: str,
    profile: str,
    memory_strength: float,
    anchor_strength_factor: float,
    angular_strength_factor: float,
    kind: str,
    matched_random_role: str,
    seed_offset: int,
) -> dict[str, Any]:
    return {
        "role": role,
        "profile": profile,
        "memory_strength": memory_strength,
        "mechanism_strength_factor": anchor_strength_factor if anchor_strength_factor else angular_strength_factor,
        "anchor_strength_factor": anchor_strength_factor,
        "angular_strength_factor": angular_strength_factor,
        "angular_cleanup_strength": memory_strength if angular_strength_factor else 0.0,
        "kind": kind,
        "matched_random_role": matched_random_role,
        "seed_offset": seed_offset,
    }


def _summary_fields() -> list[str]:
    return _replace_anchor_fields(_anchor_summary_fields())


def _by_return_fields() -> list[str]:
    return _replace_anchor_fields(_anchor_by_return_fields())


def _replace_anchor_fields(fields: list[str]) -> list[str]:
    out: list[str] = []
    for field in fields:
        if field == "isochronous_cubic_anchor_classification":
            out.append("angular_mode_cleanup_classification")
        elif field == "anchor_kind":
            out.append("angular_cleanup_kind")
        elif field == "off_comb_not_worse":
            out.append("off_comb_reduced_vs_anchor")
        else:
            out.append(field)
        if field == "mechanism_strength_factor":
            out.extend(["anchor_strength_factor", "angular_cleanup_strength_factor", "angular_cleanup_strength"])
    return out


def _comparison_fields() -> list[str]:
    return [
        "angular_mode_cleanup_classification",
        "run_stage",
        "variant",
        "mechanism_role",
        "mechanism_profile",
        "mechanism_strength_factor",
        "anchor_strength_factor",
        "angular_cleanup_strength_factor",
        "angular_cleanup_strength",
        "angular_cleanup_kind",
        "matched_random_role",
        "matched_random_available",
        "memory_delta_vs_neutral",
        "memory_delta_vs_random_0p5",
        "memory_delta_vs_random_damping",
        "memory_delta_vs_anchor",
        "strict_major_delta_vs_neutral",
        "strict_refocus_delta_vs_neutral",
        "preserves_strict_9_8",
        "comb_score_delta_vs_neutral",
        "comb_near_neutral",
        "off_comb_delta_vs_neutral",
        "off_comb_delta_vs_anchor",
        "off_comb_reduced_vs_anchor",
        "modal_participation_delta_vs_neutral",
        "clean_gates_passed",
        "beats_neutral_memory",
        "beats_random_0p5_memory",
        "beats_random_damping_memory",
    ]


def _spectrum_fields() -> list[str]:
    return [
        "angular_mode_cleanup_classification",
        "variant",
        "mechanism_role",
        "mechanism_profile",
        "angular_cleanup_kind",
        "angular_sector_count",
        "angular_sector_participation",
        "angular_dominant_sector_fraction",
        "angular_energy_weighted_phase_coherence",
        "pattern_memory_score",
        "off_comb_energy_ratio",
    ]
