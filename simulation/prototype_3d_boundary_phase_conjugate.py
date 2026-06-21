"""Patch-level boundary phase-conjugate control for the 3D release-phase branch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import math
import random

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig
from .prototype_3d_cutoff_phase_map import _add_control_fields, _variant, threshold_robust_refocusing_scores
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_packet_lifecycle import _event_fields, _timeseries_fields
from .prototype_3d_refocusing_engineering import _format, _lifecycle_options
from .prototype_3d_release_phase_proof_pack import ReleasePhaseProofPackOptions, _variant_plan as _proof_variant_plan
from .prototype_3d_release_phase_resolution_lift import ReleasePhaseResolutionLiftOptions
from .prototype_3d_source_sponge import _write_csv
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
from .prototype_3d_smooth_envelope_resolution_lift import _float, _int, _bool, _report_value


PHASE_CONJUGATE_ROLES = (
    "hard_51_control",
    "phase_conjugate_candidate",
    "shuffled_patch_phase_control",
    "amplitude_only_control",
    "phase_only_control",
    "wrong_return_target_control",
)


@dataclass(frozen=True)
class BoundaryPhaseConjugateOptions(ReleasePhaseResolutionLiftOptions):
    """Options for one fixed boundary phase-conjugate mechanism test."""

    output_root: str = "runs"
    proof_grid_size: int = 41
    grid_size: int = 51
    proof_cutoff: float = 17.94
    lift_cutoff: float = 17.9425
    negative_control_cutoff: float = 17.915
    dt_scale: float = 0.25
    shell_window_width: float | None = 4.0
    patch_u_bins: int = 4
    patch_v_bins: int = 4
    target_return_count: int = 4
    wrong_return_rank: int = 4
    patch_amplitude_strength: float = 0.30
    min_patch_amplitude_scale: float = 0.75
    max_patch_amplitude_scale: float = 1.25
    shuffled_seed: int = 5103
    frame_peak_threshold_fraction: float = 0.20
    max_return_frames: int = 4
    radial_phase_bins: int = 12
    angular_theta_bins: int = 8
    angular_polar_bins: int = 4
    progress_interval_steps: int = 1000
    min_coherence_improvement: float = 0.02
    max_work_per_area_relative_error: float = 0.02
    max_post_cutoff_positive_work: float = 1.0e-6


def run_3d_boundary_phase_conjugate_control(
    base_config: SimulationConfig,
    *,
    options: BoundaryPhaseConjugateOptions | None = None,
) -> dict[str, Any]:
    """Run a fixed patch-level phase-conjugate 51^3 mechanism test."""

    options = options or BoundaryPhaseConjugateOptions()
    control_id = datetime.now().strftime("boundary_phase_conjugate_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    lifecycle_options = _lifecycle_options(options)
    proof_config, proof_options = _proof_variant(base_config, options)
    proof_spatial_options = _spatial_options(options, capture_node_frames=True)
    target_work_per_area = _calibrate_fixed_variant(base_config, proof_config, proof_options, lifecycle_options)
    proof_result = _run_spatial_phase_variant(proof_config, root, lifecycle_options, proof_spatial_options)
    proof_summary = proof_result["summary"]
    _add_control_fields(proof_summary, proof_config, proof_options, target_work_per_area)
    proof_summary.update(proof_result["spatial_summary"])
    proof_summary["prediction_role"] = "proof_41_design_source"
    proof_robust_rows = threshold_robust_refocusing_scores([proof_summary], proof_result["timeseries"], proof_options)
    _merge_robust_counts([proof_summary], proof_robust_rows)

    design = _phase_conjugate_design(
        proof_result["frame_index_rows"],
        proof_result["angular_rows"],
        options,
        target_ranks=tuple(range(1, int(options.target_return_count) + 1)),
        design_role="phase_conjugate_candidate",
    )
    wrong_design = _phase_conjugate_design(
        proof_result["frame_index_rows"],
        proof_result["angular_rows"],
        options,
        target_ranks=(int(options.wrong_return_rank),),
        design_role="wrong_return_target_control",
    )
    shuffled_design = _shuffled_phase_design(design, options)
    _write_design_artifacts(root, control_id, design, wrong_design, shuffled_design, proof_summary, options)

    configs = _variant_plan(base_config, options, design, wrong_design, shuffled_design)
    spatial_options = _spatial_options(options, capture_node_frames=False)

    rows: list[dict[str, Any]] = []
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

    for config in configs:
        target_work_per_area = _calibrate_fixed_variant(base_config, config, options, lifecycle_options)
        result = _run_spatial_phase_variant(config, root, lifecycle_options, spatial_options)
        summary = result["summary"]
        _add_control_fields(summary, config, options, target_work_per_area)
        _add_phase_conjugate_fields(summary, config, target_work_per_area, result["threshold_counts"], options)
        summary.update(result["spatial_summary"])
        rows.append(summary)
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

    robust_rows = threshold_robust_refocusing_scores(rows, timeseries_rows, options)
    _merge_robust_counts(rows, robust_rows)
    comparison_rows = _comparison_rows(rows, proof_summary, options)
    gate_rows = _gate_rows(rows, comparison_rows, options)
    classification = classify_boundary_phase_conjugate(rows, comparison_rows, gate_rows, options)

    for row_set in (
        rows,
        robust_rows,
        threshold_rows,
        frame_rows,
        displacement_rows,
        velocity_rows,
        radial_frame_rows,
        radial_coherence_rows,
        angular_rows,
        stability_rows,
        drift_rows,
        comparison_rows,
        gate_rows,
    ):
        for row in row_set:
            row["boundary_phase_conjugate_classification"] = classification["label"]

    summary_csv = root / "boundary_phase_conjugate_summary.csv"
    robust_csv = root / "boundary_phase_conjugate_threshold_robust_score.csv"
    comparison_csv = root / "boundary_phase_conjugate_spatial_comparison.csv"
    gates_csv = root / "boundary_phase_conjugate_gates.csv"
    threshold_csv = root / "boundary_phase_conjugate_event_threshold_counts.csv"
    timeseries_csv = root / "boundary_phase_conjugate_lifecycle_timeseries.csv"
    events_csv = root / "boundary_phase_conjugate_lifecycle_events.csv"
    frame_index_csv = root / "boundary_phase_conjugate_spatial_phase_frame_index.csv"
    displacement_csv = root / "boundary_phase_conjugate_shell_displacement_frames.csv"
    velocity_csv = root / "boundary_phase_conjugate_shell_velocity_frames.csv"
    radial_frames_csv = root / "boundary_phase_conjugate_radial_shell_phase_frames.csv"
    radial_coherence_csv = root / "boundary_phase_conjugate_shell_phase_coherence_by_radius.csv"
    angular_csv = root / "boundary_phase_conjugate_angular_shell_phase_coherence.csv"
    stability_csv = root / "boundary_phase_conjugate_node_antinode_stability_maps.csv"
    drift_csv = root / "boundary_phase_conjugate_phase_drift_across_return_peaks.csv"
    proof_frame_index_csv = root / "boundary_phase_conjugate_proof_spatial_phase_frame_index.csv"
    proof_displacement_csv = root / "boundary_phase_conjugate_proof_shell_displacement_frames.csv"
    proof_velocity_csv = root / "boundary_phase_conjugate_proof_shell_velocity_frames.csv"
    report_path = root / "boundary_phase_conjugate_report.md"

    _write_csv(summary_csv, rows, _summary_fields())
    _write_csv(robust_csv, robust_rows, _robust_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_csv(gates_csv, gate_rows, _gate_fields())
    _write_csv(threshold_csv, threshold_rows, _threshold_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(events_csv, event_rows, _event_fields())
    _write_csv(frame_index_csv, frame_rows, _frame_index_fields())
    _write_csv(displacement_csv, displacement_rows, _node_frame_fields("u"))
    _write_csv(velocity_csv, velocity_rows, _node_frame_fields("v"))
    _write_csv(radial_frames_csv, radial_frame_rows, _radial_frame_fields())
    _write_csv(radial_coherence_csv, radial_coherence_rows, _radial_coherence_fields())
    _write_csv(angular_csv, angular_rows, _angular_fields())
    _write_csv(stability_csv, stability_rows, _stability_fields())
    _write_csv(drift_csv, drift_rows, _drift_fields())
    _write_csv(proof_frame_index_csv, proof_result["frame_index_rows"], _frame_index_fields())
    _write_csv(proof_displacement_csv, proof_result["displacement_rows"], _node_frame_fields("u"))
    _write_csv(proof_velocity_csv, proof_result["velocity_rows"], _node_frame_fields("v"))
    _write_report(report_path, control_id, proof_summary, rows, comparison_rows, gate_rows, classification, options)

    save_json(
        root / "boundary_phase_conjugate_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "proof_summary": proof_summary,
            "variants": rows,
            "comparison_rows": comparison_rows,
            "gate_rows": gate_rows,
            "summary_csv": str(summary_csv),
            "robust_csv": str(robust_csv),
            "comparison_csv": str(comparison_csv),
            "gates_csv": str(gates_csv),
            "proof_frame_index_csv": str(proof_frame_index_csv),
            "proof_displacement_csv": str(proof_displacement_csv),
            "proof_velocity_csv": str(proof_velocity_csv),
            "report_path": str(report_path),
            "candidate_json": str(root / "boundary_phase_conjugate_candidate.json"),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "proof_summary": proof_summary,
        "variants": rows,
        "comparison_rows": comparison_rows,
        "gate_rows": gate_rows,
        "summary_csv": str(summary_csv),
        "robust_csv": str(robust_csv),
        "comparison_csv": str(comparison_csv),
        "gates_csv": str(gates_csv),
        "frame_index_csv": str(frame_index_csv),
        "proof_frame_index_csv": str(proof_frame_index_csv),
        "proof_displacement_csv": str(proof_displacement_csv),
        "proof_velocity_csv": str(proof_velocity_csv),
        "report_path": str(report_path),
        "candidate_json": str(root / "boundary_phase_conjugate_candidate.json"),
        "path": str(root),
    }


def classify_boundary_phase_conjugate(
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    options: BoundaryPhaseConjugateOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the patch-level phase-conjugate source rescues 51^3."""

    options = options or BoundaryPhaseConjugateOptions()
    candidate = _role_row(rows, "phase_conjugate_candidate")
    hard = _role_row(rows, "hard_51_control")
    shuffled = _role_row(rows, "shuffled_patch_phase_control")
    gates = {str(row.get("gate")): _bool(row.get("pass")) for row in gate_rows}
    count_improved = _strict_tuple(candidate) > _strict_tuple(hard)
    strict_restored = _int(candidate.get("conservative_major_peaks")) >= 9 and _int(candidate.get("conservative_refocus_peaks")) >= 8
    coherence_improved = all(
        gates.get(name, False)
        for name in (
            "shell_coherence_improved_vs_hard",
            "radial_coherence_improved_vs_hard",
            "angular_coherence_improved_vs_hard",
        )
    )
    clean = all(
        gates.get(name, False)
        for name in (
            "outer_shell_below_1",
            "global_outer_false",
            "no_shell_exit",
            "zero_post_cutoff_work",
            "energy_accounting_clean",
        )
    )
    shuffled_fails = _strict_tuple(shuffled) < _strict_tuple(candidate)
    checks = {
        "candidate": candidate.get("variant"),
        "hard_control": hard.get("variant"),
        "shuffled_control": shuffled.get("variant"),
        "candidate_strict_count": _count_label(candidate, "strict"),
        "hard_strict_count": _count_label(hard, "strict"),
        "shuffled_strict_count": _count_label(shuffled, "strict"),
        "count_improved": count_improved,
        "strict_restored": strict_restored,
        "coherence_improved": coherence_improved,
        "clean_gates": clean,
        "shuffled_fails": shuffled_fails,
    }
    if strict_restored and count_improved and coherence_improved and clean and shuffled_fails:
        return {
            "label": "boundary_phase_conjugate_supported",
            "reason": "The patch-level phase-conjugate boundary source restored strict 9/8-or-better returns and improved spatial coherence versus the hard 51^3 control, while the shuffled patch control failed.",
            "checks": checks,
        }
    if count_improved and not coherence_improved:
        return {
            "label": "count_improved_without_coherence",
            "reason": "Strict counts improved, but shell/radial/angular coherence did not improve, so this is not a proven phase-conjugate rescue.",
            "checks": checks,
        }
    if coherence_improved and not strict_restored:
        return {
            "label": "coherence_improved_count_not_restored",
            "reason": "Patch-level phase conjugation improved spatial coherence, but did not restore the strict 9/8 refocusing floor.",
            "checks": checks,
        }
    return {
        "label": "boundary_phase_conjugate_no_rescue",
        "reason": "The patch-level phase-conjugate source did not jointly improve strict refocusing and spatial coherence under the frozen 51^3 setup.",
        "checks": checks,
    }


def _proof_variant(base: SimulationConfig, options: BoundaryPhaseConjugateOptions) -> tuple[Prototype3DConfig, ReleasePhaseProofPackOptions]:
    proof_options = ReleasePhaseProofPackOptions(
        output_root=options.output_root,
        grid_size=options.proof_grid_size,
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
        fixed_drive_frequency=options.fixed_drive_frequency,
        cutoffs=(options.proof_cutoff,),
        prediction_roles=("proof_41_design_source",),
        dt_scale=options.dt_scale,
    )
    config = _proof_variant_plan(base, proof_options)[0]
    config.name = f"phase_conjugate_41_proof_cutoff_{_safe_float(options.proof_cutoff)}"
    return config, proof_options


def _variant_plan(
    base: SimulationConfig,
    options: BoundaryPhaseConjugateOptions,
    design: dict[str, Any],
    wrong_design: dict[str, Any],
    shuffled_design: dict[str, Any],
) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    specs = [
        ("hard_51_control", options.lift_cutoff, None, None, "hard"),
        ("phase_conjugate_candidate", options.lift_cutoff, design, "phase_amp", "candidate"),
        ("shuffled_patch_phase_control", options.lift_cutoff, shuffled_design, "phase_amp", "shuffled"),
        ("amplitude_only_control", options.lift_cutoff, design, "amp_only", "amplitude_only"),
        ("phase_only_control", options.lift_cutoff, design, "phase_only", "phase_only"),
        ("wrong_return_target_control", options.lift_cutoff, wrong_design, "phase_amp", "wrong_return"),
    ]
    variants = []
    for role, cutoff, patch_design, patch_mode, label in specs:
        config = _variant(
            f"phase_conjugate_51_{label}_cutoff_{_safe_float(cutoff)}",
            base,
            options,
            source_width,
            cutoff=float(cutoff),
            frequency=options.fixed_drive_frequency,
            phase_offset=0.0,
            cubic_sign=-1.0,
            family="sign_flip",
            axis="boundary_phase_conjugate",
            cutoff_offset=float(cutoff) - float(base.driver.drive_cutoff_time),
        )
        config.dt = float(base.dt) * options.dt_scale
        config.steps = max(1, int(round(options.physical_duration / max(config.dt, EPSILON))))
        config.second_pulse_center_time = None
        config.second_pulse_duration = 0.0
        config.second_pulse_amplitude_scale = 0.0
        config.second_pulse_phase_offset = 0.0
        config.resonator_enabled = False
        config.boundary_patch_u_bins = options.patch_u_bins
        config.boundary_patch_v_bins = options.patch_v_bins
        if patch_design and patch_mode in {"phase_amp", "phase_only"}:
            config.boundary_patch_phase_offsets = dict(patch_design["phase_offsets"])
        if patch_design and patch_mode in {"phase_amp", "amp_only"}:
            config.boundary_patch_amplitude_scales = dict(patch_design["amplitude_scales"])
        setattr(config, "_prediction_role", role)
        setattr(config, "_patch_mode", patch_mode or "none")
        setattr(config, "_patch_count", len(patch_design["phase_offsets"]) if patch_design else 0)
        setattr(config, "_target_release_phase", (float(cutoff) * options.fixed_drive_frequency) % 1.0)
        variants.append(config)
    return variants


def _spatial_options(options: BoundaryPhaseConjugateOptions, *, capture_node_frames: bool) -> SpatialPhaseInstrumentationOptions:
    return SpatialPhaseInstrumentationOptions(
        output_root=options.output_root,
        proof_grid_size=options.proof_grid_size,
        lift_grid_size=options.grid_size,
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
        fixed_drive_frequency=options.fixed_drive_frequency,
        proof_cutoff=options.proof_cutoff,
        lift_target_release_phase=(options.lift_cutoff * options.fixed_drive_frequency) % 1.0,
        dt_scale=options.dt_scale,
        arrival_threshold_fraction=options.arrival_threshold_fraction,
        exit_threshold_fraction=options.exit_threshold_fraction,
        exit_hold_samples=options.exit_hold_samples,
        peak_threshold_fraction=options.peak_threshold_fraction,
        frame_peak_threshold_fraction=options.frame_peak_threshold_fraction,
        refocus_threshold_fraction=options.refocus_threshold_fraction,
        min_peak_separation_time=options.min_peak_separation_time,
        min_refocus_count=options.min_refocus_count,
        min_width_growth_fraction=options.min_width_growth_fraction,
        min_decay_rate_magnitude=options.min_decay_rate_magnitude,
        max_return_frames=options.max_return_frames,
        radial_phase_bins=options.radial_phase_bins,
        angular_theta_bins=options.angular_theta_bins,
        angular_polar_bins=options.angular_polar_bins,
        capture_node_frame_rows=capture_node_frames,
        progress_interval_steps=options.progress_interval_steps,
    )


def _phase_conjugate_design(
    frame_rows: list[dict[str, Any]],
    angular_rows: list[dict[str, Any]],
    options: BoundaryPhaseConjugateOptions,
    *,
    target_ranks: tuple[int, ...],
    design_role: str,
) -> dict[str, Any]:
    sector_table = _sector_phase_table(angular_rows, target_ranks)
    phase_offsets: dict[str, float] = {}
    amplitude_scales: dict[str, float] = {}
    faces = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
    for face in faces:
        for u_bin in range(options.patch_u_bins):
            for v_bin in range(options.patch_v_bins):
                patch_id = f"{face}:{u_bin}:{v_bin}"
                polar_bin, theta_bin = _patch_direction_bins(face, u_bin, v_bin, options)
                sector = sector_table.get((polar_bin, theta_bin), {})
                phase_cycles = _float(sector.get("phase_cycles"))
                energy_ratio = _float_or(sector.get("energy_ratio"), 1.0)
                phase_offsets[patch_id] = _wrap_radians(-2.0 * math.pi * phase_cycles)
                scale = 1.0 + options.patch_amplitude_strength * (energy_ratio - 1.0)
                amplitude_scales[patch_id] = float(
                    min(options.max_patch_amplitude_scale, max(options.min_patch_amplitude_scale, scale))
                )
    phase_offsets = _remove_global_phase(phase_offsets)
    return {
        "design_role": design_role,
        "target_peak_ranks": target_ranks,
        "proof_frame_count": len(frame_rows),
        "patch_u_bins": options.patch_u_bins,
        "patch_v_bins": options.patch_v_bins,
        "patch_count": len(phase_offsets),
        "phase_offsets": phase_offsets,
        "amplitude_scales": amplitude_scales,
        "design_rows": _design_rows(design_role, phase_offsets, amplitude_scales, sector_table, options),
    }


def _sector_phase_table(angular_rows: list[dict[str, Any]], target_ranks: tuple[int, ...]) -> dict[tuple[int, int], dict[str, float]]:
    accum: dict[tuple[int, int], dict[str, float]] = {}
    for row in angular_rows:
        rank = _int(row.get("peak_rank"))
        if rank not in target_ranks:
            continue
        energy = max(_float(row.get("shell_energy")), 0.0)
        if energy <= EPSILON:
            continue
        key = (_int(row.get("polar_bin")), _int(row.get("theta_bin")))
        phase = 2.0 * math.pi * _float(row.get("phase_mean_cycles"))
        item = accum.setdefault(key, {"real": 0.0, "imag": 0.0, "energy": 0.0})
        item["real"] += energy * math.cos(phase)
        item["imag"] += energy * math.sin(phase)
        item["energy"] += energy
    mean_energy = float(np.mean([item["energy"] for item in accum.values()])) if accum else 1.0
    out: dict[tuple[int, int], dict[str, float]] = {}
    for key, item in accum.items():
        phase = math.atan2(item["imag"], item["real"])
        out[key] = {
            "phase_cycles": (phase / (2.0 * math.pi)) % 1.0,
            "coherence": math.hypot(item["real"], item["imag"]) / max(item["energy"], EPSILON),
            "energy": item["energy"],
            "energy_ratio": item["energy"] / max(mean_energy, EPSILON),
        }
    return out


def _patch_direction_bins(face: str, u_bin: int, v_bin: int, options: BoundaryPhaseConjugateOptions) -> tuple[int, int]:
    half = 1.0
    u = -half + (u_bin + 0.5) * (2.0 * half / max(options.patch_u_bins, 1))
    v = -half + (v_bin + 0.5) * (2.0 * half / max(options.patch_v_bins, 1))
    if face == "x_min":
        x, y, z = -half, u, v
    elif face == "x_max":
        x, y, z = half, u, v
    elif face == "y_min":
        x, y, z = u, -half, v
    elif face == "y_max":
        x, y, z = u, half, v
    elif face == "z_min":
        x, y, z = u, v, -half
    else:
        x, y, z = u, v, half
    radius = max(math.sqrt(x * x + y * y + z * z), EPSILON)
    theta = math.atan2(y, x) % (2.0 * math.pi)
    polar = math.acos(max(-1.0, min(1.0, z / radius)))
    theta_bin = min(options.angular_theta_bins - 1, max(0, int(theta / (2.0 * math.pi) * options.angular_theta_bins)))
    polar_bin = min(options.angular_polar_bins - 1, max(0, int(polar / math.pi * options.angular_polar_bins)))
    return polar_bin, theta_bin


def _remove_global_phase(offsets: dict[str, float]) -> dict[str, float]:
    if not offsets:
        return offsets
    real = sum(math.cos(value) for value in offsets.values())
    imag = sum(math.sin(value) for value in offsets.values())
    mean = math.atan2(imag, real)
    return {key: _wrap_radians(value - mean) for key, value in offsets.items()}


def _shuffled_phase_design(design: dict[str, Any], options: BoundaryPhaseConjugateOptions) -> dict[str, Any]:
    keys = list(design["phase_offsets"].keys())
    values = [design["phase_offsets"][key] for key in keys]
    rng = random.Random(options.shuffled_seed)
    rng.shuffle(values)
    shuffled = dict(design)
    shuffled["design_role"] = "shuffled_patch_phase_control"
    shuffled["phase_offsets"] = dict(zip(keys, values))
    shuffled["design_rows"] = _design_rows(
        "shuffled_patch_phase_control",
        shuffled["phase_offsets"],
        shuffled["amplitude_scales"],
        {},
        options,
    )
    return shuffled


def _design_rows(
    role: str,
    phase_offsets: dict[str, float],
    amplitude_scales: dict[str, float],
    sector_table: dict[tuple[int, int], dict[str, float]],
    options: BoundaryPhaseConjugateOptions,
) -> list[dict[str, Any]]:
    rows = []
    for patch_id, phase in phase_offsets.items():
        face, u_bin, v_bin = patch_id.split(":")
        polar_bin, theta_bin = _patch_direction_bins(face, int(u_bin), int(v_bin), options)
        sector = sector_table.get((polar_bin, theta_bin), {})
        rows.append(
            {
                "design_role": role,
                "patch_id": patch_id,
                "face": face,
                "u_bin": u_bin,
                "v_bin": v_bin,
                "polar_bin": polar_bin,
                "theta_bin": theta_bin,
                "phase_offset_radians": phase,
                "phase_offset_cycles": (phase / (2.0 * math.pi)) % 1.0,
                "amplitude_scale": amplitude_scales.get(patch_id, 1.0),
                "source_sector_phase_cycles": sector.get("phase_cycles"),
                "source_sector_coherence": sector.get("coherence"),
                "source_sector_energy_ratio": sector.get("energy_ratio"),
            }
        )
    return rows


def _write_design_artifacts(
    root: Path,
    control_id: str,
    design: dict[str, Any],
    wrong_design: dict[str, Any],
    shuffled_design: dict[str, Any],
    proof_summary: dict[str, Any],
    options: BoundaryPhaseConjugateOptions,
) -> None:
    rows = design["design_rows"] + wrong_design["design_rows"] + shuffled_design["design_rows"]
    _write_csv(root / "boundary_phase_conjugate_design.csv", rows, _design_fields())
    save_json(
        root / "boundary_phase_conjugate_candidate.json",
        {
            "control_id": control_id,
            "candidate_role": "phase_conjugate_candidate",
            "frozen_before_51_run": True,
            "proof_variant": proof_summary.get("variant"),
            "proof_cutoff": options.proof_cutoff,
            "lift_cutoff": options.lift_cutoff,
            "patch_u_bins": options.patch_u_bins,
            "patch_v_bins": options.patch_v_bins,
            "target_return_count": options.target_return_count,
            "phase_offsets": design["phase_offsets"],
            "amplitude_scales": design["amplitude_scales"],
            "wrong_return_phase_offsets": wrong_design["phase_offsets"],
            "shuffled_phase_offsets": shuffled_design["phase_offsets"],
        },
    )


def _add_phase_conjugate_fields(
    row: dict[str, Any],
    config: Prototype3DConfig,
    target_work_per_area: float,
    threshold_rows: list[dict[str, Any]],
    options: BoundaryPhaseConjugateOptions,
) -> None:
    row["prediction_role"] = getattr(config, "_prediction_role", "unlabeled")
    row["patch_mode"] = getattr(config, "_patch_mode", "none")
    row["patch_count"] = getattr(config, "_patch_count", 0)
    row["target_reference_work_per_source_area"] = target_work_per_area
    row["retention"] = row.get("tail_shell_retention")
    row["outer_shell"] = row.get("tail_outer_to_shell_mean")
    row["decay"] = row.get("post_cutoff_shell_decay_rate")
    row["outer_shell_below_1"] = _float(row.get("outer_shell")) < 1.0
    row["no_exit"] = not _bool(row.get("shell_exit_detected"))
    row["global_outer_false"] = not _bool(row.get("global_peak_in_outer_window"))
    row["work_per_area_relative_error"] = abs(_float(row.get("work_per_source_area")) - target_work_per_area) / max(
        abs(target_work_per_area), EPSILON
    )
    row["post_cutoff_positive_work"] = max(0.0, _float(row.get("total_positive_work")) - _float(row.get("primary_positive_work")))
    row["energy_accounting_clean"] = (
        row["work_per_area_relative_error"] <= options.max_work_per_area_relative_error
        and row["post_cutoff_positive_work"] <= options.max_post_cutoff_positive_work
    )
    by_threshold = {str(item.get("peak_threshold_fraction")): item for item in threshold_rows}
    for label, threshold in (("loose_0p20", "0.2"), ("default_0p30", "0.3"), ("strict_0p35", "0.35"), ("strict_0p40", "0.4")):
        item = by_threshold.get(threshold, {})
        row[f"{label}_major_peaks"] = item.get("major_shell_peak_count")
        row[f"{label}_refocus_peaks"] = item.get("refocus_peak_count")
    row["loose_major_peaks_at_0p20"] = row.get("loose_0p20_major_peaks")
    row["loose_refocus_peaks_at_0p20"] = row.get("loose_0p20_refocus_peaks")


def _comparison_rows(
    rows: list[dict[str, Any]],
    proof_summary: dict[str, Any],
    options: BoundaryPhaseConjugateOptions,
) -> list[dict[str, Any]]:
    candidate = _role_row(rows, "phase_conjugate_candidate")
    comparisons = []
    for role, label in (
        ("hard_51_control", "candidate_vs_hard_control"),
        ("shuffled_patch_phase_control", "candidate_vs_shuffled_patch_control"),
        ("amplitude_only_control", "candidate_vs_amplitude_only_control"),
        ("phase_only_control", "candidate_vs_phase_only_control"),
        ("wrong_return_target_control", "candidate_vs_wrong_return_target_control"),
    ):
        control = _role_row(rows, role)
        comparisons.append(_comparison(label, candidate, control))
    comparisons.append(_proof_distance_comparison(candidate, _role_row(rows, "hard_51_control"), proof_summary))
    return comparisons


def _comparison(label: str, candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    return {
        "comparison": label,
        "candidate_variant": candidate.get("variant"),
        "control_variant": control.get("variant"),
        "candidate_role": candidate.get("prediction_role"),
        "control_role": control.get("prediction_role"),
        "candidate_default_count": _count_label(candidate, "default"),
        "control_default_count": _count_label(control, "default"),
        "candidate_strict_count": _count_label(candidate, "strict"),
        "control_strict_count": _count_label(control, "strict"),
        "strict_major_delta": _int(candidate.get("conservative_major_peaks")) - _int(control.get("conservative_major_peaks")),
        "strict_refocus_delta": _int(candidate.get("conservative_refocus_peaks")) - _int(control.get("conservative_refocus_peaks")),
        "candidate_loose_0p20_count": _count_label(candidate, "loose"),
        "control_loose_0p20_count": _count_label(control, "loose"),
        "shell_phase_coherence_delta": _float(candidate.get("shell_phase_coherence_mean")) - _float(control.get("shell_phase_coherence_mean")),
        "radial_phase_coherence_delta": _float(candidate.get("radial_phase_coherence_mean")) - _float(control.get("radial_phase_coherence_mean")),
        "angular_phase_coherence_delta": _float(candidate.get("angular_phase_coherence_mean")) - _float(control.get("angular_phase_coherence_mean")),
    }


def _proof_distance_comparison(candidate: dict[str, Any], hard: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any]:
    metrics = ("shell_phase_coherence_mean", "radial_phase_coherence_mean", "angular_phase_coherence_mean")
    row = {
        "comparison": "candidate_toward_41_proof",
        "candidate_variant": candidate.get("variant"),
        "control_variant": proof.get("variant"),
        "candidate_role": candidate.get("prediction_role"),
        "control_role": "proof_41_design_source",
    }
    reductions = []
    for metric in metrics:
        proof_value = _float(proof.get(metric))
        hard_distance = abs(_float(hard.get(metric)) - proof_value)
        candidate_distance = abs(_float(candidate.get(metric)) - proof_value)
        reduction = hard_distance - candidate_distance
        reductions.append(reduction)
        row[f"{metric}_proof"] = proof_value
        row[f"{metric}_hard_distance_to_proof"] = hard_distance
        row[f"{metric}_candidate_distance_to_proof"] = candidate_distance
        row[f"{metric}_distance_reduction"] = reduction
    row["coherence_distance_reduction_mean"] = float(np.mean(reductions)) if reductions else 0.0
    row["coherence_moves_toward_41_proof"] = row["coherence_distance_reduction_mean"] >= 0.0
    return row


def _gate_rows(rows: list[dict[str, Any]], comparison_rows: list[dict[str, Any]], options: BoundaryPhaseConjugateOptions) -> list[dict[str, Any]]:
    candidate = _role_row(rows, "phase_conjugate_candidate")
    shuffled = _role_row(rows, "shuffled_patch_phase_control")
    hard_comparison = _comparison_row(comparison_rows, "candidate_vs_hard_control")
    proof_comparison = _comparison_row(comparison_rows, "candidate_toward_41_proof")
    return [
        _gate("candidate_strict_9_8", _int(candidate.get("conservative_major_peaks")) >= 9 and _int(candidate.get("conservative_refocus_peaks")) >= 8, _count_label(candidate, "strict"), "candidate restores strict 9/8 or better"),
        _gate("strict_returns_improve_above_hard", _strict_tuple(candidate) > _strict_tuple(_role_row(rows, "hard_51_control")), _count_label(candidate, "strict"), "strict counts improve over hard 51^3 control"),
        _gate("shell_coherence_improved_vs_hard", _float(hard_comparison.get("shell_phase_coherence_delta")) >= options.min_coherence_improvement, hard_comparison.get("shell_phase_coherence_delta"), "shell phase coherence improves versus hard control"),
        _gate("radial_coherence_improved_vs_hard", _float(hard_comparison.get("radial_phase_coherence_delta")) >= options.min_coherence_improvement, hard_comparison.get("radial_phase_coherence_delta"), "radial phase coherence improves versus hard control"),
        _gate("angular_coherence_improved_vs_hard", _float(hard_comparison.get("angular_phase_coherence_delta")) >= options.min_coherence_improvement, hard_comparison.get("angular_phase_coherence_delta"), "angular phase coherence improves versus hard control"),
        _gate("coherence_moves_toward_41_proof", _bool(proof_comparison.get("coherence_moves_toward_41_proof")), proof_comparison.get("coherence_distance_reduction_mean"), "candidate moves closer to 41^3 proof coherence"),
        _gate("shuffled_patch_control_fails", _strict_tuple(shuffled) < _strict_tuple(candidate), _count_label(shuffled, "strict"), "shuffled patch phase control stays below candidate"),
        _gate("outer_shell_below_1", _float(candidate.get("outer_shell")) < 1.0, candidate.get("outer_shell"), "outer/shell below 1.0"),
        _gate("global_outer_false", _bool(candidate.get("global_outer_false")), candidate.get("global_outer_false"), "global outer flag false"),
        _gate("no_shell_exit", _bool(candidate.get("no_exit")), candidate.get("no_exit"), "no shell exit"),
        _gate("zero_post_cutoff_work", _float(candidate.get("post_cutoff_positive_work")) <= options.max_post_cutoff_positive_work, candidate.get("post_cutoff_positive_work"), "zero post-cutoff external work"),
        _gate("energy_accounting_clean", _bool(candidate.get("energy_accounting_clean")), candidate.get("work_per_area_relative_error"), "matched work/area and no active additions"),
    ]


def _write_report(
    path: Path,
    control_id: str,
    proof_summary: dict[str, Any],
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: BoundaryPhaseConjugateOptions,
) -> None:
    lines = [
        f"# 3D Boundary Phase-Conjugate Control: {control_id}",
        "",
        "## Purpose",
        "",
        "Test whether a patch-level boundary wavefront derived from the 41^3 proof shell phase can restore 51^3 strict refocusing and spatial coherence without changing frequency, release phase, grid, lattice, sponge, source geometry, or work per physical source area.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Proof Design Source",
        "",
        f"- Proof row: `{proof_summary.get('variant')}`",
        f"- Proof strict count: {_count_label(proof_summary, 'strict')}",
        f"- Proof shell/radial/angular coherence: {_format(proof_summary.get('shell_phase_coherence_mean'))} / {_format(proof_summary.get('radial_phase_coherence_mean'))} / {_format(proof_summary.get('angular_phase_coherence_mean'))}",
        f"- Boundary patches: `{6 * options.patch_u_bins * options.patch_v_bins}`",
        "",
        "## Rows",
        "",
        "| Role | Patch Mode | Cutoff | Default | Strict | Loose 0.20 | Shell Coh | Radial Coh | Angular Coh | Outer/Shell | Exit |",
        "| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('prediction_role')} | "
            f"{row.get('patch_mode')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_count_label(row, 'default')} | "
            f"{_count_label(row, 'strict')} | "
            f"{_count_label(row, 'loose')} | "
            f"{_format(row.get('shell_phase_coherence_mean'))} | "
            f"{_format(row.get('radial_phase_coherence_mean'))} | "
            f"{_format(row.get('angular_phase_coherence_mean'))} | "
            f"{_format(row.get('outer_shell'))} | "
            f"{row.get('shell_exit_detected')} |"
        )
    lines.extend(
        [
            "",
            "## Comparisons",
            "",
            "| Comparison | Strict Delta | Shell Coh Delta | Radial Coh Delta | Angular Coh Delta | Proof Distance Reduction |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            "| "
            f"{row.get('comparison')} | "
            f"{row.get('strict_major_delta', '')}/{row.get('strict_refocus_delta', '')} | "
            f"{_format(row.get('shell_phase_coherence_delta'))} | "
            f"{_format(row.get('radial_phase_coherence_delta'))} | "
            f"{_format(row.get('angular_phase_coherence_delta'))} | "
            f"{_format(row.get('coherence_distance_reduction_mean'))} |"
        )
    lines.extend(["", "## Gates", "", "| Gate | Pass | Value | Reason |", "| --- | --- | ---: | --- |"])
    for row in gate_rows:
        lines.append(f"| {row.get('gate')} | {row.get('pass')} | {_report_value(row.get('value'))} | {row.get('reason')} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Guardrail",
            "",
            "Do not tune this result after seeing it. A pass requires both strict-count recovery and spatial-coherence recovery, with shuffled patch control failing.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "boundary_phase_conjugate_supported":
        return "Patch-level boundary phase conjugation restored the scale-lift proof gate and is the first evidence for a scalable boundary wavefront-control rule."
    if label == "coherence_improved_count_not_restored":
        return "The patch wavefront improved coherence but did not restore strict returns. The mechanism is real but insufficient in this first basis."
    if label == "count_improved_without_coherence":
        return "Counts improved without coherence recovery. Treat this as suspicious, not phase-conjugate proof."
    return "Patch-level boundary phase conjugation did not rescue the 51^3 scale lift under the frozen setup."


def _role_row(rows: list[dict[str, Any]], role: str) -> dict[str, Any]:
    return next((row for row in rows if row.get("prediction_role") == role), {})


def _comparison_row(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    return next((row for row in rows if row.get("comparison") == label), {})


def _gate(gate: str, passed: bool, value: Any, reason: str) -> dict[str, Any]:
    return {"gate": gate, "pass": bool(passed), "value": value, "reason": reason}


def _strict_tuple(row: dict[str, Any]) -> tuple[int, int]:
    return (_int(row.get("conservative_major_peaks")), _int(row.get("conservative_refocus_peaks")))


def _float_or(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _count_label(row: dict[str, Any], kind: str) -> str:
    if kind == "default":
        return f"{row.get('default_major_peaks_at_0p30') or row.get('default_0p30_major_peaks')}/{row.get('default_refocus_peaks_at_0p30') or row.get('default_0p30_refocus_peaks')}"
    if kind == "loose":
        return f"{row.get('loose_major_peaks_at_0p20') or row.get('loose_0p20_major_peaks')}/{row.get('loose_refocus_peaks_at_0p20') or row.get('loose_0p20_refocus_peaks')}"
    return f"{row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')}"


def _safe_float(value: float) -> str:
    return str(float(value)).replace("-", "minus_").replace(".", "p")


def _wrap_radians(value: float) -> float:
    return (float(value) + math.pi) % (2.0 * math.pi) - math.pi


def _summary_fields() -> list[str]:
    return [
        "variant",
        "boundary_phase_conjugate_classification",
        "prediction_role",
        "patch_mode",
        "patch_count",
        "family",
        "axis_label",
        "grid_size",
        "dx",
        "dt",
        "drive_frequency",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "target_reference_work_per_source_area",
        "work_per_source_area",
        "work_per_area_relative_error",
        "positive_work_before_cutoff",
        "primary_positive_work",
        "total_positive_work",
        "post_cutoff_positive_work",
        "energy_accounting_clean",
        "default_major_peaks_at_0p30",
        "default_refocus_peaks_at_0p30",
        "strict_major_peaks_at_0p35",
        "strict_refocus_peaks_at_0p35",
        "strict_major_peaks_at_0p40",
        "strict_refocus_peaks_at_0p40",
        "conservative_major_peaks",
        "conservative_refocus_peaks",
        "loose_major_peaks_at_0p20",
        "loose_refocus_peaks_at_0p20",
        "loose_major_peaks_at_0p25",
        "loose_refocus_peaks_at_0p25",
        "retention",
        "shell_phase_coherence_mean",
        "radial_phase_coherence_mean",
        "angular_phase_coherence_mean",
        "node_phase_stability_mean",
        "instrumented_return_frame_count",
        "outer_shell",
        "decay",
        "outer_shell_below_1",
        "no_exit",
        "global_outer_false",
        "shell_exit_detected",
        "global_peak_in_outer_window",
        "threshold_free_shell_area_after_cutoff",
        "threshold_free_tail_area_after_t50",
        "shell_energy_autocorrelation",
        "dominant_spectral_concentration",
        "return_timing_regularity",
    ]


def _robust_fields() -> list[str]:
    return [
        "variant",
        "boundary_phase_conjugate_classification",
        "rank",
        "conservative_score",
        "default_threshold_score",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "min_major_peaks_across_thresholds",
        "median_major_peaks_across_thresholds",
        "min_refocus_peaks_across_thresholds",
        "median_refocus_peaks_across_thresholds",
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


def _comparison_fields() -> list[str]:
    return [
        "comparison",
        "boundary_phase_conjugate_classification",
        "candidate_variant",
        "control_variant",
        "candidate_role",
        "control_role",
        "candidate_default_count",
        "control_default_count",
        "candidate_strict_count",
        "control_strict_count",
        "strict_major_delta",
        "strict_refocus_delta",
        "candidate_loose_0p20_count",
        "control_loose_0p20_count",
        "shell_phase_coherence_delta",
        "radial_phase_coherence_delta",
        "angular_phase_coherence_delta",
        "shell_phase_coherence_mean_proof",
        "shell_phase_coherence_mean_hard_distance_to_proof",
        "shell_phase_coherence_mean_candidate_distance_to_proof",
        "shell_phase_coherence_mean_distance_reduction",
        "radial_phase_coherence_mean_proof",
        "radial_phase_coherence_mean_hard_distance_to_proof",
        "radial_phase_coherence_mean_candidate_distance_to_proof",
        "radial_phase_coherence_mean_distance_reduction",
        "angular_phase_coherence_mean_proof",
        "angular_phase_coherence_mean_hard_distance_to_proof",
        "angular_phase_coherence_mean_candidate_distance_to_proof",
        "angular_phase_coherence_mean_distance_reduction",
        "coherence_distance_reduction_mean",
        "coherence_moves_toward_41_proof",
    ]


def _gate_fields() -> list[str]:
    return ["gate", "boundary_phase_conjugate_classification", "pass", "value", "reason"]


def _design_fields() -> list[str]:
    return [
        "design_role",
        "patch_id",
        "face",
        "u_bin",
        "v_bin",
        "polar_bin",
        "theta_bin",
        "phase_offset_radians",
        "phase_offset_cycles",
        "amplitude_scale",
        "source_sector_phase_cycles",
        "source_sector_coherence",
        "source_sector_energy_ratio",
    ]


def _threshold_fields() -> list[str]:
    return [
        "variant",
        "boundary_phase_conjugate_classification",
        "grid_size",
        "peak_threshold_fraction",
        "major_shell_peak_count",
        "refocus_peak_count",
    ]
