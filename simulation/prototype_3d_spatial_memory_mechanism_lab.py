"""Independent passive spatial-memory mechanism lab for 3D shell returns."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig, _calibrate_amplitude
from .prototype_3d_cutoff_phase_map import threshold_robust_refocusing_scores
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _boundary_config as _interference_boundary_config
from .prototype_3d_interference_diagnostics import _threshold_like_options
from .prototype_3d_refocusing_engineering import _format, _lifecycle_options
from .prototype_3d_source_sponge import _effective_source_area, _write_csv
from .prototype_3d_spatial_phase_instrumentation import (
    SpatialPhaseInstrumentationOptions,
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
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


SPATIAL_MEMORY_VARIANT_ROLES = (
    "neutral_reference",
    "anisotropy_anchor",
    "cubic_degeneracy_split",
    "shell_band_isolation",
    "nonlinear_phase_memory",
    "random_equivalent_control",
)


@dataclass(frozen=True)
class SpatialMemoryMechanismLabOptions(SpatialPhaseInstrumentationOptions):
    """Options for the independent passive spatial-memory mechanism lab."""

    output_root: str = "runs"
    grid_size: int = 41
    lift_grid_size: int = 51
    fixed_cutoff: float = 17.94
    fixed_drive_frequency: float = 0.92
    phase_offset: float = 0.0
    dt_scale: float = 0.25
    mechanism_strength: float = 0.035
    random_seed: int = 9103
    max_post_cutoff_external_work: float = 1.0e-6
    max_work_per_area_relative_error: float = 0.02
    max_outer_shell: float = 1.0
    min_memory_improvement: float = 0.04
    min_control_separation: float = 0.025
    max_random_strength_match_error: float = 0.01
    comb_window_half_width_fraction: float = 0.24
    min_comb_window_half_width: float = 0.75
    run_51_if_supported: bool = True


def run_3d_spatial_memory_mechanism_lab(
    base_config: SimulationConfig,
    *,
    options: SpatialMemoryMechanismLabOptions | None = None,
) -> dict[str, Any]:
    """Run a fixed passive mechanism lab for return-to-return shell-pattern memory."""

    options = options or SpatialMemoryMechanismLabOptions()
    violations = validate_closed_branch_guardrails(options)
    if violations:
        raise ValueError("Spatial memory lab guardrail violation: " + "; ".join(violations))

    control_id = datetime.now().strftime("spatial_memory_mechanism_lab_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    stage_rows, by_return_rows, comparison_rows, artifact_rows = _run_stage(
        base_config,
        options,
        root,
        stage="mechanism_41",
        grid_size=options.grid_size,
        roles=SPATIAL_MEMORY_VARIANT_ROLES,
    )
    classification = classify_spatial_memory_mechanism_lab(stage_rows, comparison_rows, options)

    if classification["label"] == "spatial_memory_mechanism_supported" and options.run_51_if_supported:
        best_role = str(classification.get("best_role") or "")
        follow_roles = ("neutral_reference", best_role, "random_equivalent_control")
        follow_summary, follow_returns, follow_comparison, follow_artifacts = _run_stage(
            base_config,
            options,
            root,
            stage="optional_51_followup",
            grid_size=options.lift_grid_size,
            roles=follow_roles,
        )
        stage_rows.extend(follow_summary)
        by_return_rows.extend(follow_returns)
        comparison_rows.extend(follow_comparison)
        artifact_rows.extend(follow_artifacts)

    for row_set in (stage_rows, by_return_rows, comparison_rows):
        for row in row_set:
            row["spatial_memory_mechanism_classification"] = classification["label"]

    summary_csv = root / "spatial_memory_mechanism_summary.csv"
    by_return_csv = root / "spatial_memory_by_return.csv"
    comparison_csv = root / "mechanism_control_comparison.csv"
    report_path = root / "spatial_memory_mechanism_report.md"
    summary_json = root / "spatial_memory_mechanism_summary.json"
    plots = {
        "pattern_memory": str(root / "pattern_memory_plot.png"),
        "off_comb_energy": str(root / "off_comb_energy_plot.png"),
        "comb_score": str(root / "comb_score_plot.png"),
        "modal_participation": str(root / "modal_participation_plot.png"),
    }

    _write_csv(summary_csv, stage_rows, _summary_fields())
    _write_csv(by_return_csv, by_return_rows, _by_return_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_artifact_csvs(root, artifact_rows)
    _plot_summary_bar(Path(plots["pattern_memory"]), stage_rows, "pattern_memory_score", "Return-To-Return Pattern Memory")
    _plot_summary_bar(Path(plots["off_comb_energy"]), stage_rows, "off_comb_energy_ratio", "Off-Comb Energy Ratio")
    _plot_summary_bar(Path(plots["comb_score"]), stage_rows, "return_timing_comb_score", "Return Timing Comb Score")
    _plot_summary_bar(Path(plots["modal_participation"]), stage_rows, "modal_participation_ratio", "Modal Participation Ratio")
    _write_report(report_path, control_id, classification, stage_rows, comparison_rows, options)
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
        "summary_rows": stage_rows,
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


def validate_closed_branch_guardrails(options: SpatialMemoryMechanismLabOptions) -> list[str]:
    """Return guardrail violations that would turn this lab into old-branch tuning."""

    violations: list[str] = []
    if int(options.grid_size) == 61 or int(options.lift_grid_size) == 61:
        violations.append("61^3 is forbidden")
    if abs(float(options.fixed_cutoff) - 17.94) > 1.0e-9:
        violations.append("cutoff phase/timing tuning is forbidden")
    if abs(float(options.fixed_drive_frequency) - 0.92) > 1.0e-9:
        violations.append("frequency/source-shape tuning is forbidden")
    if int(options.lift_grid_size) != 51:
        violations.append("larger-grid branch should remain the fixed optional 51^3 gate")
    return violations


def build_spatial_memory_variants(
    base_config: SimulationConfig,
    options: SpatialMemoryMechanismLabOptions | None = None,
    *,
    grid_size: int | None = None,
    roles: tuple[str, ...] = SPATIAL_MEMORY_VARIANT_ROLES,
) -> list[Prototype3DConfig]:
    """Construct the fixed mechanism-specific passive variants."""

    options = options or SpatialMemoryMechanismLabOptions()
    grid = int(grid_size or options.grid_size)
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    lifecycle_options = _lifecycle_options(options)
    configs: list[Prototype3DConfig] = []
    for role in roles:
        profile = _profile_for_role(role)
        name = f"spatial_memory_{grid}_{role}"
        config = _interference_boundary_config(name, base_config, lifecycle_options, source_width, "cubic", cubic_sign=-1.0)
        config.grid_size = grid
        config.dt = float(base_config.dt) * float(options.dt_scale)
        config.steps = max(1, int(round(float(options.physical_duration) / max(config.dt, EPSILON))))
        config.drive_cutoff_time = float(options.fixed_cutoff)
        config.drive_frequency = float(options.fixed_drive_frequency)
        config.memory_mechanism_profile = profile
        config.memory_mechanism_strength = float(options.mechanism_strength if profile != "none" else 0.0)
        config.memory_mechanism_seed = int(options.random_seed)
        config.memory_mechanism_shell_radius = float(options.shell_window_radius + 0.5 * _shell_width_from_options(options, config))
        config.memory_mechanism_shell_width = float(_shell_width_from_options(options, config))
        setattr(config, "_spatial_memory_role", role)
        setattr(config, "_spatial_memory_profile", profile)
        setattr(config, "_dt_scale", options.dt_scale)
        configs.append(config)
    return configs


def calculate_profile_strength_match(
    reference_profile: np.ndarray,
    comparison_profile: np.ndarray,
    strength: float,
) -> dict[str, float]:
    """Compare RMS perturbation strength between two normalized profiles."""

    ref = np.asarray(reference_profile, dtype=float)
    cmp = np.asarray(comparison_profile, dtype=float)
    ref_strength = float(abs(strength) * np.sqrt(np.mean(ref**2))) if ref.size else 0.0
    cmp_strength = float(abs(strength) * np.sqrt(np.mean(cmp**2))) if cmp.size else 0.0
    error = abs(cmp_strength - ref_strength) / max(ref_strength, EPSILON)
    return {
        "reference_strength_l2": ref_strength,
        "comparison_strength_l2": cmp_strength,
        "relative_match_error": error,
    }


def calculate_spatial_pattern_memory(displacement_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate sign-insensitive return-to-return shell-pattern memory from node frames."""

    pair_rows = _spatial_memory_pair_rows(displacement_rows)
    scores = [_float(row.get("pattern_memory_score")) for row in pair_rows]
    return {
        "pair_count": len(pair_rows),
        "pattern_memory_score": _mean(scores),
        "pattern_memory_min": min(scores) if scores else 0.0,
        "pattern_memory_std": _std(scores),
        "pair_rows": pair_rows,
    }


def classify_spatial_memory_mechanism_lab(
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: SpatialMemoryMechanismLabOptions | None = None,
) -> dict[str, Any]:
    """Classify whether any passive mechanism improves spatial-pattern memory."""

    options = options or SpatialMemoryMechanismLabOptions()
    stage_rows = [row for row in rows if row.get("run_stage") == "mechanism_41"] or rows
    neutral = next((row for row in stage_rows if row.get("mechanism_role") == "neutral_reference"), None)
    random_control = next((row for row in stage_rows if row.get("mechanism_role") == "random_equivalent_control"), None)
    mechanism_rows = [
        row
        for row in stage_rows
        if row.get("mechanism_role") not in {"neutral_reference", "random_equivalent_control"}
    ]
    missing = []
    if neutral is None:
        missing.append("neutral_reference")
    if random_control is None:
        missing.append("random_equivalent_control")
    missing.extend([str(row.get("variant")) for row in stage_rows if int(_float(row.get("pattern_memory_pair_count"))) <= 0])
    control_separation_failed = any(_float(row.get("random_strength_match_error")) > options.max_random_strength_match_error for row in stage_rows)
    invalid_controls = [
        str(row.get("variant"))
        for row in (neutral, random_control)
        if row is not None
        and (
            not _bool(row.get("energy_accounting_clean"))
            or not _bool(row.get("no_post_cutoff_external_work"))
            or not _bool(row.get("global_outer_false"))
        )
    ]
    checks = {
        "missing_required_artifacts": missing,
        "invalid_controls": invalid_controls,
        "control_separation_failed": control_separation_failed,
        "neutral_pattern_memory": neutral.get("pattern_memory_score") if neutral else None,
        "random_pattern_memory": random_control.get("pattern_memory_score") if random_control else None,
        "min_memory_improvement": options.min_memory_improvement,
        "min_control_separation": options.min_control_separation,
    }
    if missing or invalid_controls or control_separation_failed:
        return {
            "label": "invalid_mechanism_test",
            "reason": "Required reference/control artifacts or clean-control guardrails failed.",
            "checks": checks,
        }
    best_comparison = max(
        comparison_rows,
        key=lambda row: (
            _float(row.get("memory_delta_vs_neutral")),
            _bool(row.get("clean_gates_passed")),
            _float(row.get("memory_delta_vs_random_control")),
        ),
        default={},
    )
    best_role = str(best_comparison.get("mechanism_role") or "")
    best_row = next((row for row in mechanism_rows if row.get("mechanism_role") == best_role), None)
    checks.update(
        {
            "best_role": best_role,
            "best_memory_delta_vs_neutral": best_comparison.get("memory_delta_vs_neutral"),
            "best_memory_delta_vs_random_control": best_comparison.get("memory_delta_vs_random_control"),
            "best_clean_gates_passed": best_comparison.get("clean_gates_passed"),
        }
    )
    improves = _float(best_comparison.get("memory_delta_vs_neutral")) >= options.min_memory_improvement
    beats_random = _float(best_comparison.get("memory_delta_vs_random_control")) >= options.min_control_separation
    clean = _bool(best_comparison.get("clean_gates_passed"))
    if improves and beats_random and clean:
        return {
            "label": "spatial_memory_mechanism_supported",
            "reason": "A passive mechanism improved return-to-return spatial-pattern memory versus neutral and randomized equivalent-strength controls while preserving clean gates.",
            "best_variant": best_comparison.get("variant"),
            "best_role": best_role,
            "checks": checks,
        }
    if improves and beats_random and best_row is not None:
        return {
            "label": "spatial_memory_partial_signal",
            "reason": "A passive mechanism improved pattern memory and separated from the randomized control, but return purity or clean gates were incomplete.",
            "best_variant": best_comparison.get("variant"),
            "best_role": best_role,
            "checks": checks,
        }
    return {
        "label": "no_spatial_memory_mechanism_found",
        "reason": "No passive mechanism improved spatial-pattern memory beyond the neutral reference and randomized equivalent-strength control.",
        "best_variant": best_comparison.get("variant"),
        "best_role": best_role,
        "checks": checks,
    }


def _run_stage(
    base_config: SimulationConfig,
    options: SpatialMemoryMechanismLabOptions,
    root: Path,
    *,
    stage: str,
    grid_size: int,
    roles: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    configs = build_spatial_memory_variants(base_config, options, grid_size=grid_size, roles=roles)
    lifecycle_options = _lifecycle_options(options)
    stage_root = root / stage
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
        _add_lab_fields(summary, config, stage, target_work_per_area, memory, result, options)
        summary_rows.append(summary)
        for pair in memory["pair_rows"]:
            pair["run_stage"] = stage
            pair["mechanism_role"] = getattr(config, "_spatial_memory_role", "")
            pair["mechanism_profile"] = getattr(config, "_spatial_memory_profile", "")
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
        metrics = _comb_and_modal_metrics(str(row.get("variant")), timeseries_rows, event_rows, options)
        row.update(metrics)
        _add_clean_gate_fields(row, options)
    comparison_rows = _comparison_rows(summary_rows)
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


def _add_lab_fields(
    row: dict[str, Any],
    config: Prototype3DConfig,
    stage: str,
    target_work_per_area: float,
    memory: dict[str, Any],
    result: dict[str, Any],
    options: SpatialMemoryMechanismLabOptions,
) -> None:
    row.update(result["spatial_summary"])
    role = getattr(config, "_spatial_memory_role", "")
    profile = getattr(config, "_spatial_memory_profile", "")
    profile_strength = abs(float(config.memory_mechanism_strength or 0.0))
    row["run_stage"] = stage
    row["mechanism_role"] = role
    row["mechanism_profile"] = profile
    row["mechanism_strength"] = config.memory_mechanism_strength
    row["random_seed"] = config.memory_mechanism_seed
    row["dt_scale"] = getattr(config, "_dt_scale", options.dt_scale)
    row["drive_frequency"] = config.drive_frequency
    row["drive_cutoff_time"] = config.drive_cutoff_time
    row["target_reference_work_per_source_area"] = target_work_per_area
    row["work_per_area_relative_error"] = abs(_float(row.get("primary_work_per_source_area")) - target_work_per_area) / max(target_work_per_area, EPSILON)
    row["post_cutoff_external_positive_work"] = max(
        0.0,
        _float(row.get("total_positive_work")) - _float(row.get("primary_positive_work")) - _float(row.get("second_pulse_positive_work")),
    )
    row["no_post_cutoff_external_work"] = row["post_cutoff_external_positive_work"] <= options.max_post_cutoff_external_work
    row["energy_accounting_clean"] = (
        row["work_per_area_relative_error"] <= options.max_work_per_area_relative_error
        and row["no_post_cutoff_external_work"]
        and _float(row.get("second_pulse_positive_work")) <= options.max_post_cutoff_external_work
    )
    row["pattern_memory_pair_count"] = memory["pair_count"]
    row["pattern_memory_score"] = memory["pattern_memory_score"]
    row["pattern_memory_min"] = memory["pattern_memory_min"]
    row["pattern_memory_std"] = memory["pattern_memory_std"]
    row["profile_strength_l2"] = profile_strength
    row["random_strength_match_error"] = 0.0


def _comparison_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    neutral_by_stage = {
        str(row.get("run_stage")): row
        for row in summary_rows
        if row.get("mechanism_role") == "neutral_reference"
    }
    random_by_stage = {
        str(row.get("run_stage")): row
        for row in summary_rows
        if row.get("mechanism_role") == "random_equivalent_control"
    }
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        role = row.get("mechanism_role")
        if role in {"neutral_reference", "random_equivalent_control"}:
            continue
        stage = str(row.get("run_stage"))
        neutral = neutral_by_stage.get(stage, {})
        random_control = random_by_stage.get(stage, {})
        out.append(
            {
                "run_stage": stage,
                "variant": row.get("variant"),
                "mechanism_role": role,
                "mechanism_profile": row.get("mechanism_profile"),
                "grid_size": row.get("grid_size"),
                "memory_delta_vs_neutral": _float(row.get("pattern_memory_score")) - _float(neutral.get("pattern_memory_score")),
                "memory_delta_vs_random_control": _float(row.get("pattern_memory_score")) - _float(random_control.get("pattern_memory_score")),
                "strict_major_delta_vs_neutral": _int(row.get("conservative_major_peaks")) - _int(neutral.get("conservative_major_peaks")),
                "comb_score_delta_vs_neutral": _float(row.get("return_timing_comb_score")) - _float(neutral.get("return_timing_comb_score")),
                "off_comb_delta_vs_neutral": _float(row.get("off_comb_energy_ratio")) - _float(neutral.get("off_comb_energy_ratio")),
                "modal_participation_delta_vs_neutral": _float(row.get("modal_participation_ratio")) - _float(neutral.get("modal_participation_ratio")),
                "clean_gates_passed": row.get("clean_gates_passed"),
                "beats_neutral_memory": _float(row.get("pattern_memory_score")) > _float(neutral.get("pattern_memory_score")),
                "beats_random_memory": _float(row.get("pattern_memory_score")) > _float(random_control.get("pattern_memory_score")),
            }
        )
    return out


def _spatial_memory_pair_rows(displacement_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frames: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in displacement_rows:
        frame_id = str(row.get("frame_id") or row.get("frame_index") or "")
        if not frame_id:
            continue
        key = (str(row.get("variant")), frame_id)
        frames.setdefault(key, []).append(row)
    by_variant: dict[str, list[tuple[str, list[dict[str, Any]]]]] = {}
    for (variant, frame_id), rows in frames.items():
        by_variant.setdefault(variant, []).append((frame_id, rows))
    out: list[dict[str, Any]] = []
    for variant, frame_items in by_variant.items():
        sorted_frames = sorted(frame_items, key=lambda item: (_float(item[1][0].get("peak_rank")), _float(item[1][0].get("time"))))
        for (left_id, left_rows), (right_id, right_rows) in zip(sorted_frames, sorted_frames[1:]):
            left = {int(_float(row.get("node_index"))): _float(row.get("u")) for row in left_rows}
            right = {int(_float(row.get("node_index"))): _float(row.get("u")) for row in right_rows}
            common = sorted(set(left) & set(right))
            if not common:
                continue
            left_vec = np.asarray([left[idx] for idx in common], dtype=float)
            right_vec = np.asarray([right[idx] for idx in common], dtype=float)
            signed = _cosine_similarity(left_vec, right_vec)
            score = abs(signed)
            out.append(
                {
                    "variant": variant,
                    "from_frame_id": left_id,
                    "to_frame_id": right_id,
                    "from_peak_rank": left_rows[0].get("peak_rank"),
                    "to_peak_rank": right_rows[0].get("peak_rank"),
                    "from_time": left_rows[0].get("time"),
                    "to_time": right_rows[0].get("time"),
                    "signed_similarity": signed,
                    "pattern_memory_score": score,
                    "matched_node_count": len(common),
                }
            )
    return out


def _comb_and_modal_metrics(
    variant: str,
    timeseries_rows: list[dict[str, Any]],
    event_rows: list[dict[str, Any]],
    options: SpatialMemoryMechanismLabOptions,
) -> dict[str, Any]:
    rows = [row for row in timeseries_rows if row.get("variant") == variant]
    events = [row for row in event_rows if row.get("variant") == variant and row.get("event") == "shell_peak"]
    if not rows:
        return {"return_timing_comb_score": 0.0, "off_comb_energy_ratio": 0.0, "modal_participation_ratio": 0.0}
    times = np.asarray([_float(row.get("time")) for row in rows], dtype=float)
    shell = np.asarray([_float(row.get("shell_window_energy")) for row in rows], dtype=float)
    peak_times = np.asarray([_float(row.get("time")) for row in events], dtype=float)
    post = times > options.fixed_cutoff
    total = float(np.trapz(shell[post], times[post])) if np.count_nonzero(post) >= 2 else float(np.sum(shell[post]))
    if peak_times.size >= 2:
        periods = np.diff(peak_times)
        period = float(np.median(periods))
        period_cv = float(np.std(periods) / max(abs(np.mean(periods)), EPSILON)) if periods.size else 0.0
        half_width = max(float(options.min_comb_window_half_width), float(options.comb_window_half_width_fraction) * period)
        on_mask = np.zeros_like(times, dtype=bool)
        for peak_time in peak_times:
            on_mask |= np.abs(times - peak_time) <= half_width
        on_mask &= post
        on_area = float(np.trapz(shell[on_mask], times[on_mask])) if np.count_nonzero(on_mask) >= 2 else float(np.sum(shell[on_mask]))
        on_fraction = on_area / max(total, EPSILON)
        occupancy = min(1.0, peak_times.size / max(_int(max((row.get("peak_rank") for row in events), default=peak_times.size)), 1))
        comb_score = max(0.0, on_fraction * occupancy * (1.0 - min(period_cv, 1.0)))
    else:
        on_area = 0.0
        comb_score = 0.0
    off_comb = max(total - on_area, 0.0) / max(on_area, EPSILON)
    post_shell = shell[post]
    if post_shell.size >= 4:
        centered = post_shell - float(np.mean(post_shell))
        power = np.abs(np.fft.rfft(centered)) ** 2
        power = power[1:] if power.size > 1 else power
        participation = float((np.sum(power) ** 2) / max(np.sum(power**2), EPSILON)) if power.size else 0.0
    else:
        participation = 0.0
    return {
        "return_timing_comb_score": comb_score,
        "off_comb_energy_ratio": off_comb,
        "modal_participation_ratio": participation,
    }


def _add_clean_gate_fields(row: dict[str, Any], options: SpatialMemoryMechanismLabOptions) -> None:
    row["no_exit"] = not _bool(row.get("shell_exit_detected"))
    row["global_outer_false"] = not _bool(row.get("global_peak_in_outer_window"))
    row["outer_shell_below_gate"] = _float(row.get("tail_outer_to_shell_mean")) <= options.max_outer_shell
    row["clean_gates_passed"] = (
        _bool(row.get("no_exit"))
        and _bool(row.get("global_outer_false"))
        and _bool(row.get("outer_shell_below_gate"))
        and _bool(row.get("energy_accounting_clean"))
    )


def _write_artifact_csvs(root: Path, artifact_rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, tuple[list[dict[str, Any]], list[str]]] = {}
    for artifact in artifact_rows:
        name = str(artifact["name"])
        rows = list(artifact["rows"])
        fields = list(artifact["fields"])
        current_rows, current_fields = grouped.get(name, ([], fields))
        current_rows.extend(rows)
        grouped[name] = (current_rows, current_fields)
    for name, (rows, fields) in grouped.items():
        if not rows:
            continue
        _write_csv(root / f"spatial_memory_{name}.csv", rows, fields)


def _write_report(
    path: Path,
    control_id: str,
    classification: dict[str, Any],
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: SpatialMemoryMechanismLabOptions,
) -> None:
    lines = [
        f"# Spatial Memory Mechanism Lab: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Guardrails",
        "",
        "- This is an independent passive mechanism lab, not a rescue of the closed passive scale-lift branch.",
        "- Cutoff, drive frequency, source shape, active pulses, and 61^3 are not tuning surfaces here.",
        "- Optional 51^3 follow-up only runs if the fixed 41^3 mechanism test is supported.",
        "",
        "## Summary",
        "",
        "| Stage | Variant | Role | Memory | Strict | Default | Loose | Comb | Off-comb | Modal PR | Clean |",
        "| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('run_stage')} | {row.get('variant')} | {row.get('mechanism_role')} | "
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
            "## Mechanism Comparisons",
            "",
            "| Stage | Mechanism | Memory delta vs neutral | Memory delta vs random | Clean |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            f"| {row.get('run_stage')} | {row.get('mechanism_role')} | "
            f"{_format(row.get('memory_delta_vs_neutral'))} | "
            f"{_format(row.get('memory_delta_vs_random_control'))} | "
            f"{row.get('clean_gates_passed')} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `spatial_memory_mechanism_summary.csv`",
            "- `spatial_memory_by_return.csv`",
            "- `mechanism_control_comparison.csv`",
            "- `pattern_memory_plot.png`",
            "- `off_comb_energy_plot.png`",
            "- `comb_score_plot.png`",
            "- `modal_participation_plot.png`",
            "",
            "## Interpretation",
            "",
            _interpretation_text(classification, options),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation_text(classification: dict[str, Any], options: SpatialMemoryMechanismLabOptions) -> str:
    label = classification["label"]
    if label == "spatial_memory_mechanism_supported":
        return "A passive lattice profile improved raw return-to-return spatial identity while preserving clean gates and beating the randomized equivalent-strength control. This is only a mechanism clue, not a scale-validation claim."
    if label == "spatial_memory_partial_signal":
        return "A memory signal appeared, but return purity or clean gates were incomplete. Do not promote this to a scale branch without a new fixed follow-up design."
    if label == "no_spatial_memory_mechanism_found":
        return "The fixed mechanism set did not separate from neutral and randomized controls. Do not tune cutoff phase, source shape, or grid size from this result."
    return "The lab did not produce a valid mechanism test because required artifacts or guardrails failed."


def _plot_summary_bar(path: Path, rows: list[dict[str, Any]], key: str, title: str) -> None:
    if not rows:
        return
    labels = [str(row.get("mechanism_role")) for row in rows]
    values = [_float(row.get(key)) for row in rows]
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.9), 4), dpi=140)
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _profile_for_role(role: str) -> str:
    mapping = {
        "neutral_reference": "none",
        "anisotropy_anchor": "anisotropy_anchor",
        "cubic_degeneracy_split": "cubic_degeneracy_split",
        "shell_band_isolation": "shell_band_isolation",
        "nonlinear_phase_memory": "nonlinear_phase_memory",
        "random_equivalent_control": "random_equivalent",
    }
    if role not in mapping:
        raise ValueError(f"Unsupported spatial memory mechanism role: {role}")
    return mapping[role]


def _shell_width_from_options(options: SpatialMemoryMechanismLabOptions, config: Prototype3DConfig) -> float:
    if options.shell_window_width is not None:
        return float(options.shell_window_width)
    return float(options.near_shell_width_dx * config.dx)


def _calibration_target_work_per_area(
    base_config: SimulationConfig,
    options: SpatialMemoryMechanismLabOptions,
) -> float:
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    threshold_options = _threshold_like_options(_lifecycle_options(options))
    if options.target_work_per_source_area is not None:
        return float(options.target_work_per_source_area)
    reference = _calibrated_reference_amplitude(base_config, threshold_options, source_width, _calibration_work_per_area(base_config, threshold_options, source_width))
    _ = reference
    return _calibration_work_per_area(base_config, threshold_options, source_width)


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom <= EPSILON:
        return 0.0
    value = float(np.dot(left, right) / denom)
    return max(-1.0, min(1.0, value))


def _mean(values: list[Any]) -> float:
    parsed = [_float(value) for value in values if value not in (None, "")]
    return float(np.mean(parsed)) if parsed else 0.0


def _std(values: list[Any]) -> float:
    parsed = [_float(value) for value in values if value not in (None, "")]
    return float(np.std(parsed)) if parsed else 0.0


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _int(value: Any) -> int:
    return int(round(_float(value)))


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def _summary_fields() -> list[str]:
    return [
        "variant",
        "spatial_memory_mechanism_classification",
        "run_stage",
        "mechanism_role",
        "mechanism_profile",
        "mechanism_strength",
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
        "spatial_memory_mechanism_classification",
        "run_stage",
        "mechanism_role",
        "mechanism_profile",
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
        "spatial_memory_mechanism_classification",
        "run_stage",
        "variant",
        "mechanism_role",
        "mechanism_profile",
        "grid_size",
        "memory_delta_vs_neutral",
        "memory_delta_vs_random_control",
        "strict_major_delta_vs_neutral",
        "comb_score_delta_vs_neutral",
        "off_comb_delta_vs_neutral",
        "modal_participation_delta_vs_neutral",
        "clean_gates_passed",
        "beats_neutral_memory",
        "beats_random_memory",
    ]


def _timeseries_fields() -> list[str]:
    return [
        "variant",
        "time",
        "packet_peak_radius",
        "packet_centroid_radius",
        "packet_radial_width",
        "packet_radial_spread",
        "shell_window_energy",
        "outer_active_energy",
        "outer_to_shell_energy",
        "shell_fraction_of_total",
        "shell_radial_flux",
        "shell_inward_flux",
        "shell_outward_flux",
        "cumulative_inward_flux",
        "cumulative_outward_flux",
        "cumulative_positive_work",
        "primary_positive_work",
        "second_pulse_positive_work",
    ]


def _event_fields() -> list[str]:
    return ["variant", "event", "time", "energy", "peak_rank"]


def _robust_fields() -> list[str]:
    return [
        "variant",
        "rank",
        "conservative_score",
        "default_threshold_score",
        "major_peaks_at_0p25",
        "major_peaks_at_0p30",
        "major_peaks_at_0p35",
        "major_peaks_at_0p40",
        "refocus_peaks_at_0p25",
        "refocus_peaks_at_0p30",
        "refocus_peaks_at_0p35",
        "refocus_peaks_at_0p40",
        "threshold_free_shell_energy_area_after_cutoff",
        "threshold_free_tail_energy_area_after_t50",
        "shell_energy_autocorrelation",
        "dominant_spectral_concentration",
        "return_timing_regularity",
    ]
