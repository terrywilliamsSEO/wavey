"""One-shot smooth-envelope 51^3 rescue test for the passive release-phase rule."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import math

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig
from .prototype_3d_cutoff_phase_map import _add_control_fields, _variant, threshold_robust_refocusing_scores
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _threshold_like_options
from .prototype_3d_packet_lifecycle import _event_fields, _timeseries_fields
from .prototype_3d_refocusing_engineering import _format, _lifecycle_options
from .prototype_3d_release_phase_modal_audit import _spectrum_metrics
from .prototype_3d_release_phase_resolution_lift import ReleasePhaseResolutionLiftOptions
from .prototype_3d_source_spectrum_design_audit import _source_spectrum_rows
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


DEFAULT_PROOF_REFERENCE_ROOT = "runs/spatial_phase_instrumentation_3d_20260620_170518"
SMOOTH_LIFT_ROLES = ("hard_cutoff_control", "smooth_candidate", "smooth_negative_phase_control")


@dataclass(frozen=True)
class SmoothEnvelopeResolutionLiftOptions(ReleasePhaseResolutionLiftOptions):
    """Options for the fixed three-row smooth-envelope scale test."""

    output_root: str = "runs"
    grid_size: int = 51
    hard_control_cutoff: float = 17.9425
    candidate_cutoff: float = 17.9425
    negative_control_cutoff: float = 17.915
    proof_reference_root: str = DEFAULT_PROOF_REFERENCE_ROOT
    frame_peak_threshold_fraction: float = 0.20
    max_return_frames: int = 12
    radial_phase_bins: int = 12
    angular_theta_bins: int = 8
    angular_polar_bins: int = 4
    target_dominant_shell_frequency: float = 0.012806
    dominant_frequency_tolerance: float = 0.002
    min_source_sideband_reduction: float = 0.90
    max_smooth_source_bandwidth_ratio: float = 0.40
    min_coherence_improvement: float = 0.02
    max_tail_radius_worsening: float = 0.10
    max_work_per_area_relative_error: float = 0.02
    max_post_cutoff_positive_work: float = 1.0e-6
    progress_interval_steps: int = 1000


def run_3d_smooth_envelope_resolution_lift(
    base_config: SimulationConfig,
    *,
    options: SmoothEnvelopeResolutionLiftOptions | None = None,
) -> dict[str, Any]:
    """Run the fixed hard-control / smooth-candidate / smooth-negative-control test."""

    options = options or SmoothEnvelopeResolutionLiftOptions()
    control_id = datetime.now().strftime("smooth_envelope_resolution_lift_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    configs = _variant_plan(base_config, options)
    spatial_options = _spatial_options(options)
    lifecycle_options = _lifecycle_options(options)
    proof_reference = _proof_reference_row(Path(options.proof_reference_root))

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
    source_spectrum_rows: list[dict[str, Any]] = []

    for config in configs:
        target_work_per_area = _calibrate_fixed_variant(base_config, config, options, lifecycle_options)
        result = _run_spatial_phase_variant(config, root, lifecycle_options, spatial_options)
        summary = result["summary"]
        _add_control_fields(summary, config, options, target_work_per_area)
        _add_smooth_fields(summary, config, target_work_per_area, result["threshold_counts"])
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
        source_spectrum_rows.append(_source_spectrum_summary(config, options))

    robust_rows = threshold_robust_refocusing_scores(rows, timeseries_rows, options)
    _merge_robust_counts(rows, robust_rows)
    _add_modal_spectrum_fields(rows, timeseries_rows)
    _merge_source_spectrum(rows, source_spectrum_rows)
    comparison_rows = _comparison_rows(rows, proof_reference, options)
    gate_rows = _gate_rows(rows, comparison_rows, options)
    classification = classify_smooth_envelope_resolution_lift(rows, comparison_rows, gate_rows, options)

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
        source_spectrum_rows,
        comparison_rows,
        gate_rows,
    ):
        for row in row_set:
            row["smooth_envelope_resolution_lift_classification"] = classification["label"]

    summary_csv = root / "smooth_envelope_resolution_lift_summary.csv"
    robust_csv = root / "smooth_envelope_threshold_robust_score.csv"
    comparison_csv = root / "smooth_envelope_spatial_comparison.csv"
    gates_csv = root / "smooth_envelope_resolution_lift_gates.csv"
    source_csv = root / "smooth_envelope_source_spectrum_check.csv"
    threshold_csv = root / "smooth_envelope_event_threshold_counts.csv"
    timeseries_csv = root / "smooth_envelope_lifecycle_timeseries.csv"
    events_csv = root / "smooth_envelope_lifecycle_events.csv"
    frame_index_csv = root / "smooth_envelope_spatial_phase_frame_index.csv"
    displacement_csv = root / "smooth_envelope_shell_displacement_frames.csv"
    velocity_csv = root / "smooth_envelope_shell_velocity_frames.csv"
    radial_frames_csv = root / "smooth_envelope_radial_shell_phase_frames.csv"
    radial_coherence_csv = root / "smooth_envelope_shell_phase_coherence_by_radius.csv"
    angular_csv = root / "smooth_envelope_angular_shell_phase_coherence.csv"
    stability_csv = root / "smooth_envelope_node_antinode_stability_maps.csv"
    drift_csv = root / "smooth_envelope_phase_drift_across_return_peaks.csv"
    report_path = root / "smooth_envelope_resolution_lift_report.md"

    _write_csv(summary_csv, rows, _summary_fields())
    _write_csv(robust_csv, robust_rows, _robust_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_csv(gates_csv, gate_rows, _gate_fields())
    _write_csv(source_csv, source_spectrum_rows, _source_fields())
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
    _write_report(report_path, control_id, rows, comparison_rows, gate_rows, classification, options)

    save_json(
        root / "smooth_envelope_resolution_lift_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "proof_reference_root": options.proof_reference_root,
            "variants": rows,
            "comparison_rows": comparison_rows,
            "gate_rows": gate_rows,
            "source_spectrum_rows": source_spectrum_rows,
            "summary_csv": str(summary_csv),
            "robust_csv": str(robust_csv),
            "comparison_csv": str(comparison_csv),
            "gates_csv": str(gates_csv),
            "source_csv": str(source_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": rows,
        "threshold_robust_rows": robust_rows,
        "comparison_rows": comparison_rows,
        "gate_rows": gate_rows,
        "source_spectrum_rows": source_spectrum_rows,
        "summary_csv": str(summary_csv),
        "robust_csv": str(robust_csv),
        "comparison_csv": str(comparison_csv),
        "gates_csv": str(gates_csv),
        "source_csv": str(source_csv),
        "threshold_csv": str(threshold_csv),
        "timeseries_csv": str(timeseries_csv),
        "events_csv": str(events_csv),
        "frame_index_csv": str(frame_index_csv),
        "radial_frames_csv": str(radial_frames_csv),
        "angular_csv": str(angular_csv),
        "stability_csv": str(stability_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_smooth_envelope_resolution_lift(
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    options: SmoothEnvelopeResolutionLiftOptions | None = None,
) -> dict[str, Any]:
    """Classify whether temporal source-spectrum narrowing rescues the 51^3 lift."""

    options = options or SmoothEnvelopeResolutionLiftOptions()
    candidate = _role_row(rows, "smooth_candidate")
    hard = _role_row(rows, "hard_cutoff_control")
    weak = _role_row(rows, "smooth_negative_phase_control")
    gates = {str(row.get("gate")): _bool(row.get("pass")) for row in gate_rows}
    hard_comparison = _comparison_row(comparison_rows, "smooth_candidate_vs_hard_control")
    proof_comparison = _comparison_row(comparison_rows, "smooth_candidate_toward_41_proof")
    count_improved = (
        _int(candidate.get("conservative_major_peaks")) > _int(hard.get("conservative_major_peaks"))
        and _int(candidate.get("conservative_refocus_peaks")) > _int(hard.get("conservative_refocus_peaks"))
    )
    strict_restored = _int(candidate.get("conservative_major_peaks")) >= 9 and _int(candidate.get("conservative_refocus_peaks")) >= 8
    weak_control_below = _strict_tuple(candidate) > _strict_tuple(weak)
    coherence_improved = all(
        gates.get(name, False)
        for name in (
            "shell_coherence_improved_vs_hard",
            "radial_coherence_improved_vs_hard",
            "angular_coherence_improved_vs_hard",
            "coherence_moves_toward_41_proof",
        )
    )
    hard_gates = all(
        gates.get(name, False)
        for name in (
            "dominant_shell_band_preserved",
            "source_bandwidth_reduced_as_predicted",
            "loose_returns_at_least_11_10",
            "outer_shell_below_1",
            "global_outer_false",
            "no_shell_exit",
            "zero_post_cutoff_work",
            "energy_accounting_clean",
            "tail_radius_shift_not_worse",
        )
    )
    checks = {
        "candidate": candidate.get("variant"),
        "hard_control": hard.get("variant"),
        "negative_control": weak.get("variant"),
        "candidate_strict_count": _count_label(candidate, "conservative"),
        "hard_strict_count": _count_label(hard, "conservative"),
        "weak_strict_count": _count_label(weak, "conservative"),
        "candidate_loose_0p20_count": _count_label(candidate, "0p20"),
        "strict_count_improved_vs_hard": count_improved,
        "strict_9_8_restored": strict_restored,
        "weak_control_below_candidate": weak_control_below,
        "coherence_improved_vs_hard": coherence_improved,
        "hard_gates_pass": hard_gates,
        "shell_coherence_delta_vs_hard": _float(hard_comparison.get("shell_phase_coherence_delta")),
        "radial_coherence_delta_vs_hard": _float(hard_comparison.get("radial_phase_coherence_delta")),
        "angular_coherence_delta_vs_hard": _float(hard_comparison.get("angular_phase_coherence_delta")),
        "proof_distance_reduction_mean": _float(proof_comparison.get("coherence_distance_reduction_mean")),
    }
    if count_improved and not coherence_improved:
        return {
            "label": "count_improved_without_coherence",
            "reason": "The smooth envelope improved strict counts without a matching spatial-coherence recovery, so the result is not a proved scale rescue.",
            "checks": checks,
        }
    if strict_restored and count_improved and coherence_improved and hard_gates and weak_control_below:
        return {
            "label": "smooth_envelope_scale_rescue_supported",
            "reason": "The smooth envelope improved strict refocusing and spatial coherence while preserving the shell band and all cleanliness/accounting gates.",
            "checks": checks,
        }
    if coherence_improved and not strict_restored:
        return {
            "label": "coherence_improved_count_not_restored",
            "reason": "The smooth envelope improved spatial coherence, but did not restore the strict 9/8 refocusing floor.",
            "checks": checks,
        }
    return {
        "label": "smooth_envelope_no_rescue",
        "reason": "The smooth envelope did not jointly improve strict refocusing and spatial coherence under the frozen 51^3 setup.",
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: SmoothEnvelopeResolutionLiftOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    specs = [
        ("hard_cutoff_control", options.hard_control_cutoff, "continuous", "hard"),
        ("smooth_candidate", options.candidate_cutoff, "smooth_sin2", "smooth"),
        ("smooth_negative_phase_control", options.negative_control_cutoff, "smooth_sin2", "smooth_negative"),
    ]
    variants = []
    for role, cutoff, drive_mode, label in specs:
        config = _variant(
            f"smooth_envelope_51_{label}_cutoff_{_safe_float(cutoff)}",
            base,
            options,
            source_width,
            cutoff=float(cutoff),
            frequency=options.fixed_drive_frequency,
            phase_offset=0.0,
            cubic_sign=-1.0,
            family="sign_flip",
            axis="smooth_envelope_resolution_lift",
            cutoff_offset=float(cutoff) - float(base.driver.drive_cutoff_time),
        )
        config.dt = float(base.dt) * options.dt_scale
        config.steps = max(1, int(round(options.physical_duration / max(config.dt, EPSILON))))
        config.drive_mode = drive_mode
        config.second_pulse_center_time = None
        config.second_pulse_duration = 0.0
        config.second_pulse_amplitude_scale = 0.0
        config.second_pulse_phase_offset = 0.0
        config.resonator_enabled = False
        config.resonator_geometry = "none"
        config.resonator_k1 = 0.0
        config.resonator_k3 = 0.0
        config.resonator_damping = 0.0
        config.resonator_coupling = 0.0
        setattr(config, "_prediction_role", role)
        setattr(config, "_envelope_kind", "smooth_sin2_same_release" if drive_mode != "continuous" else "current_hard_cutoff")
        setattr(config, "_target_release_phase", (float(cutoff) * options.fixed_drive_frequency) % 1.0)
        variants.append(config)
    return variants


def _spatial_options(options: SmoothEnvelopeResolutionLiftOptions) -> SpatialPhaseInstrumentationOptions:
    return SpatialPhaseInstrumentationOptions(
        output_root=options.output_root,
        proof_grid_size=41,
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
        proof_cutoff=17.94,
        lift_target_release_phase=(options.candidate_cutoff * options.fixed_drive_frequency) % 1.0,
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
        capture_node_frame_rows=False,
        progress_interval_steps=options.progress_interval_steps,
    )


def _add_smooth_fields(
    row: dict[str, Any],
    config: Prototype3DConfig,
    target_work_per_area: float,
    threshold_rows: list[dict[str, Any]],
) -> None:
    role = getattr(config, "_prediction_role", "")
    row["prediction_role"] = role
    row["envelope_kind"] = getattr(config, "_envelope_kind", "")
    row["target_release_phase"] = getattr(config, "_target_release_phase", None)
    row["dt_variant"] = "quarter_dt"
    row["dt_scale"] = config.dt / 0.04
    row["no_active_second_pulse"] = config.second_pulse_center_time is None and config.second_pulse_duration <= EPSILON
    row["no_resonator_layer"] = not config.resonator_enabled
    row["no_exit"] = not _bool(row.get("shell_exit_detected"))
    row["global_outer_false"] = not _bool(row.get("global_peak_in_outer_window"))
    row["outer_shell"] = row.get("tail_outer_to_shell_mean")
    row["outer_shell_below_1"] = _float(row.get("tail_outer_to_shell_mean")) < 1.0
    row["post_cutoff_positive_work"] = max(0.0, _float(row.get("total_positive_work")) - _float(row.get("primary_positive_work")) - _float(row.get("second_pulse_positive_work")))
    row["work_per_area_relative_error"] = abs(_float(row.get("work_per_source_area")) - target_work_per_area) / max(abs(target_work_per_area), EPSILON)
    row["energy_accounting_clean"] = (
        _float(row.get("post_cutoff_positive_work")) <= 1.0e-6
        and _float(row.get("work_per_area_relative_error")) <= 0.02
        and _bool(row.get("no_active_second_pulse"))
        and _bool(row.get("no_resonator_layer"))
    )
    for threshold_row in threshold_rows:
        if abs(_float(threshold_row.get("peak_threshold_fraction")) - 0.20) <= 1.0e-9:
            row["loose_major_peaks_at_0p20"] = threshold_row.get("major_shell_peak_count")
            row["loose_refocus_peaks_at_0p20"] = threshold_row.get("refocus_peak_count")


def _add_modal_spectrum_fields(rows: list[dict[str, Any]], timeseries_rows: list[dict[str, Any]]) -> None:
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in timeseries_rows:
        by_variant.setdefault(str(row.get("variant")), []).append(row)
    for row in rows:
        series = sorted(by_variant.get(str(row.get("variant")), []), key=lambda item: _float(item.get("time")))
        times = np.asarray([item.get("time") for item in series], dtype=float)
        shell = np.asarray([item.get("shell_window_energy") for item in series], dtype=float)
        post = times > _float(row.get("drive_cutoff_time"))
        spectrum = _spectrum_metrics(times[post], shell[post])
        row["dominant_shell_frequency"] = spectrum.get("dominant_shell_frequency")
        row["modal_spectral_bandwidth"] = spectrum.get("spectral_bandwidth")
        row["modal_spectral_concentration"] = spectrum.get("dominant_spectral_concentration")
        row["modal_spectral_top3_fraction"] = spectrum.get("spectral_top3_fraction")


def _source_spectrum_summary(config: Prototype3DConfig, options: SmoothEnvelopeResolutionLiftOptions) -> dict[str, Any]:
    envelope_kind = getattr(config, "_envelope_kind", "current_hard_cutoff")
    summary, _ = _source_spectrum_rows(
        role=getattr(config, "_prediction_role", config.name),
        cutoff=float(config.drive_cutoff_time),
        drive_frequency=float(config.drive_frequency),
        dt=float(config.dt),
        physical_duration=float(options.physical_duration),
        envelope_kind=envelope_kind,
        far_sideband_multiplier=2.0,
    )
    summary["variant"] = config.name
    summary["prediction_role"] = getattr(config, "_prediction_role", "")
    return summary


def _merge_source_spectrum(rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> None:
    by_variant = {str(row.get("variant")): row for row in source_rows}
    hard = next((row for row in source_rows if row.get("prediction_role") == "hard_cutoff_control"), {})
    hard_bw = _float(hard.get("source_bandwidth"))
    hard_sideband = _float(hard.get("far_sideband_fraction"))
    for row in rows:
        source = by_variant.get(str(row.get("variant")), {})
        row["source_bandwidth"] = source.get("source_bandwidth")
        row["source_far_sideband_fraction"] = source.get("far_sideband_fraction")
        row["source_bandwidth_ratio_to_hard"] = _float(source.get("source_bandwidth")) / max(hard_bw, EPSILON)
        row["source_sideband_reduction_vs_hard"] = (hard_sideband - _float(source.get("far_sideband_fraction"))) / max(hard_sideband, EPSILON)


def _proof_reference_row(root: Path) -> dict[str, Any]:
    rows = _read_csv(root / "spatial_phase_instrumentation_summary.csv")
    return next((row for row in rows if row.get("audit_group") == "proof_41_reference"), rows[0] if rows else {})


def _comparison_rows(
    rows: list[dict[str, Any]],
    proof: dict[str, Any],
    options: SmoothEnvelopeResolutionLiftOptions,
) -> list[dict[str, Any]]:
    hard = _role_row(rows, "hard_cutoff_control")
    candidate = _role_row(rows, "smooth_candidate")
    weak = _role_row(rows, "smooth_negative_phase_control")
    return [
        _pair_comparison("smooth_candidate_vs_hard_control", candidate, hard, proof, options),
        _pair_comparison("smooth_candidate_vs_negative_phase_control", candidate, weak, proof, options),
        _proof_comparison(candidate, hard, proof),
    ]


def _pair_comparison(
    label: str,
    candidate: dict[str, Any],
    control: dict[str, Any],
    proof: dict[str, Any],
    options: SmoothEnvelopeResolutionLiftOptions,
) -> dict[str, Any]:
    return {
        "comparison": label,
        "candidate_variant": candidate.get("variant"),
        "control_variant": control.get("variant"),
        "candidate_role": candidate.get("prediction_role"),
        "control_role": control.get("prediction_role"),
        "candidate_default_count": _count_label(candidate, "default"),
        "control_default_count": _count_label(control, "default"),
        "candidate_strict_count": _count_label(candidate, "conservative"),
        "control_strict_count": _count_label(control, "conservative"),
        "strict_major_delta": _int(candidate.get("conservative_major_peaks")) - _int(control.get("conservative_major_peaks")),
        "strict_refocus_delta": _int(candidate.get("conservative_refocus_peaks")) - _int(control.get("conservative_refocus_peaks")),
        "candidate_loose_0p20_count": _count_label(candidate, "0p20"),
        "control_loose_0p20_count": _count_label(control, "0p20"),
        "shell_phase_coherence_delta": _float(candidate.get("shell_phase_coherence_mean")) - _float(control.get("shell_phase_coherence_mean")),
        "radial_phase_coherence_delta": _float(candidate.get("radial_phase_coherence_mean")) - _float(control.get("radial_phase_coherence_mean")),
        "angular_phase_coherence_delta": _float(candidate.get("angular_phase_coherence_mean")) - _float(control.get("angular_phase_coherence_mean")),
        "candidate_dominant_shell_frequency": candidate.get("dominant_shell_frequency"),
        "control_dominant_shell_frequency": control.get("dominant_shell_frequency"),
        "candidate_source_bandwidth_ratio_to_hard": candidate.get("source_bandwidth_ratio_to_hard"),
        "candidate_source_sideband_reduction_vs_hard": candidate.get("source_sideband_reduction_vs_hard"),
        "candidate_tail_radius_shift_from_proof": _float(candidate.get("tail_packet_radius_mean")) - _float(proof.get("tail_packet_radius_mean")),
        "control_tail_radius_shift_from_proof": _float(control.get("tail_packet_radius_mean")) - _float(proof.get("tail_packet_radius_mean")),
        "candidate_tail_radius_shift_abs_not_worse": abs(_float(candidate.get("tail_packet_radius_mean")) - _float(proof.get("tail_packet_radius_mean"))) <= abs(_float(control.get("tail_packet_radius_mean")) - _float(proof.get("tail_packet_radius_mean"))) + options.max_tail_radius_worsening,
    }


def _proof_comparison(candidate: dict[str, Any], hard: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any]:
    metrics = ("shell_phase_coherence_mean", "radial_phase_coherence_mean", "angular_phase_coherence_mean")
    reductions = []
    out: dict[str, Any] = {
        "comparison": "smooth_candidate_toward_41_proof",
        "candidate_variant": candidate.get("variant"),
        "control_variant": proof.get("variant"),
        "candidate_role": candidate.get("prediction_role"),
        "control_role": "proof_41_reference",
    }
    for metric in metrics:
        hard_distance = abs(_float(proof.get(metric)) - _float(hard.get(metric)))
        candidate_distance = abs(_float(proof.get(metric)) - _float(candidate.get(metric)))
        reduction = hard_distance - candidate_distance
        reductions.append(reduction)
        out[f"{metric}_proof"] = proof.get(metric)
        out[f"{metric}_hard_distance_to_proof"] = hard_distance
        out[f"{metric}_candidate_distance_to_proof"] = candidate_distance
        out[f"{metric}_distance_reduction"] = reduction
    out["coherence_distance_reduction_mean"] = float(np.mean(reductions)) if reductions else 0.0
    out["coherence_moves_toward_41_proof"] = all(value >= 0.0 for value in reductions)
    return out


def _gate_rows(
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: SmoothEnvelopeResolutionLiftOptions,
) -> list[dict[str, Any]]:
    candidate = _role_row(rows, "smooth_candidate")
    hard_comparison = _comparison_row(comparison_rows, "smooth_candidate_vs_hard_control")
    proof_comparison = _comparison_row(comparison_rows, "smooth_candidate_toward_41_proof")
    return [
        _gate("dominant_shell_band_preserved", abs(_float(candidate.get("dominant_shell_frequency")) - options.target_dominant_shell_frequency) <= options.dominant_frequency_tolerance, candidate.get("dominant_shell_frequency"), "dominant shell band remains near 0.012806"),
        _gate("source_bandwidth_reduced_as_predicted", _float(candidate.get("source_sideband_reduction_vs_hard")) >= options.min_source_sideband_reduction and _float(candidate.get("source_bandwidth_ratio_to_hard")) <= options.max_smooth_source_bandwidth_ratio, candidate.get("source_sideband_reduction_vs_hard"), "source sidebands reduced by the smooth envelope"),
        _gate("shell_coherence_improved_vs_hard", _float(hard_comparison.get("shell_phase_coherence_delta")) >= options.min_coherence_improvement, hard_comparison.get("shell_phase_coherence_delta"), "shell phase coherence improves versus hard control"),
        _gate("radial_coherence_improved_vs_hard", _float(hard_comparison.get("radial_phase_coherence_delta")) >= options.min_coherence_improvement, hard_comparison.get("radial_phase_coherence_delta"), "radial phase coherence improves versus hard control"),
        _gate("angular_coherence_improved_vs_hard", _float(hard_comparison.get("angular_phase_coherence_delta")) >= options.min_coherence_improvement, hard_comparison.get("angular_phase_coherence_delta"), "angular phase coherence improves versus hard control"),
        _gate("coherence_moves_toward_41_proof", _bool(proof_comparison.get("coherence_moves_toward_41_proof")), proof_comparison.get("coherence_distance_reduction_mean"), "candidate moves closer to 41^3 proof coherence"),
        _gate("strict_returns_improve_above_hard", _int(candidate.get("conservative_major_peaks")) > _int(_role_row(rows, "hard_cutoff_control").get("conservative_major_peaks")) and _int(candidate.get("conservative_refocus_peaks")) > _int(_role_row(rows, "hard_cutoff_control").get("conservative_refocus_peaks")), _count_label(candidate, "conservative"), "strict counts improve over hard 51^3 control"),
        _gate("loose_returns_at_least_11_10", _int(candidate.get("loose_major_peaks_at_0p20")) >= 11 and _int(candidate.get("loose_refocus_peaks_at_0p20")) >= 10, _count_label(candidate, "0p20"), "loose threshold returns remain at least 11/10"),
        _gate("outer_shell_below_1", _float(candidate.get("outer_shell")) < 1.0, candidate.get("outer_shell"), "outer/shell below 1.0"),
        _gate("global_outer_false", _bool(candidate.get("global_outer_false")), candidate.get("global_outer_false"), "global outer flag false"),
        _gate("no_shell_exit", _bool(candidate.get("no_exit")), candidate.get("no_exit"), "no shell exit"),
        _gate("zero_post_cutoff_work", _float(candidate.get("post_cutoff_positive_work")) <= options.max_post_cutoff_positive_work, candidate.get("post_cutoff_positive_work"), "zero post-cutoff external work"),
        _gate("energy_accounting_clean", _bool(candidate.get("energy_accounting_clean")), candidate.get("work_per_area_relative_error"), "matched work/area and no active additions"),
        _gate("tail_radius_shift_not_worse", _bool(hard_comparison.get("candidate_tail_radius_shift_abs_not_worse")), hard_comparison.get("candidate_tail_radius_shift_from_proof"), "tail-radius shift reduced or not worsened"),
    ]


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: SmoothEnvelopeResolutionLiftOptions,
) -> None:
    lines = [
        f"# 3D Smooth-Envelope Resolution Lift: {control_id}",
        "",
        "## Purpose",
        "",
        "One-shot test of whether reducing source sidebands restores `51^3` spatial coherence and strict refocusing without changing frequency, release phase, grid, lattice, sponge, source geometry, or work per physical source area.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Rows",
        "",
        "| Role | Envelope | Cutoff | Phase | Default | Strict | Loose 0.20 | Shell Coh | Radial Coh | Angular Coh | Dominant Band | Source BW Ratio | Outer/Shell | Exit |",
        "| --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('prediction_role')} | {row.get('envelope_kind')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{_count_label(row, 'default')} | "
            f"{_count_label(row, 'conservative')} | "
            f"{_count_label(row, '0p20')} | "
            f"{_format(row.get('shell_phase_coherence_mean'))} | "
            f"{_format(row.get('radial_phase_coherence_mean'))} | "
            f"{_format(row.get('angular_phase_coherence_mean'))} | "
            f"{_format(row.get('dominant_shell_frequency'))} | "
            f"{_format(row.get('source_bandwidth_ratio_to_hard'))} | "
            f"{_format(row.get('outer_shell'))} | "
            f"{not _bool(row.get('no_exit'))} |"
        )
    lines.extend(
        [
            "",
            "## Spatial Coherence Comparisons",
            "",
            "| Comparison | Strict Delta | Shell Coh Delta | Radial Coh Delta | Angular Coh Delta | Tail Shift Candidate | Tail Shift Control |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
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
            f"{_format(row.get('candidate_tail_radius_shift_from_proof'))} | "
            f"{_format(row.get('control_tail_radius_shift_from_proof'))} |"
        )
    lines.extend(
        [
            "",
            "## Gates",
            "",
            "| Gate | Pass | Value | Reason |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in gate_rows:
        lines.append(f"| {row.get('gate')} | {row.get('pass')} | {_report_value(row.get('value'))} | {row.get('reason')} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Files",
            "",
            "- `smooth_envelope_resolution_lift_report.md`",
            "- `smooth_envelope_resolution_lift_summary.csv`",
            "- `smooth_envelope_threshold_robust_score.csv`",
            "- `smooth_envelope_spatial_comparison.csv`",
            "- `smooth_envelope_source_spectrum_check.csv`",
            "- `smooth_envelope_spatial_phase_frame_index.csv`",
            "- `smooth_envelope_radial_shell_phase_frames.csv`",
            "- `smooth_envelope_angular_shell_phase_coherence.csv`",
            "",
            "## Guardrail",
            "",
            "Do not tune this result after seeing it. If the smooth candidate does not jointly improve strict counts and spatial coherence, archive the scalable passive path for now.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _report_value(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return _format(value)
    except (TypeError, ValueError):
        return str(value)


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "smooth_envelope_scale_rescue_supported":
        return "Source-sideband narrowing restored strict refocusing and spatial coherence under the frozen `51^3` setup. This is first evidence for a scalable passive packet-control rule."
    if label == "coherence_improved_count_not_restored":
        return "The source-spectrum hypothesis improved spatial coherence, but did not restore the strict refocusing sequence. The mechanism is real but insufficient as a one-axis rescue."
    if label == "count_improved_without_coherence":
        return "Strict counts improved without spatial-coherence recovery. Treat this as suspicious and not scale proof."
    return "The smooth-envelope candidate did not rescue the `51^3` scale lift. Archive the scalable passive path unless a new mechanism appears."


def _role_row(rows: list[dict[str, Any]], role: str) -> dict[str, Any]:
    return next((row for row in rows if row.get("prediction_role") == role), {})


def _comparison_row(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    return next((row for row in rows if row.get("comparison") == label), {})


def _gate(gate: str, passed: bool, value: Any, reason: str) -> dict[str, Any]:
    return {"gate": gate, "pass": bool(passed), "value": value, "reason": reason}


def _strict_tuple(row: dict[str, Any]) -> tuple[int, int]:
    return (_int(row.get("conservative_major_peaks")), _int(row.get("conservative_refocus_peaks")))


def _count_label(row: dict[str, Any], kind: str) -> str:
    if kind == "default":
        return f"{_int(row.get('default_major_peaks_at_0p30'))}/{_int(row.get('default_refocus_peaks_at_0p30'))}"
    if kind == "0p20":
        return f"{_int(row.get('loose_major_peaks_at_0p20'))}/{_int(row.get('loose_refocus_peaks_at_0p20'))}"
    return f"{_int(row.get('conservative_major_peaks'))}/{_int(row.get('conservative_refocus_peaks'))}"


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _safe_float(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".").replace(".", "p")


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _summary_fields() -> list[str]:
    return [
        "variant",
        "smooth_envelope_resolution_lift_classification",
        "prediction_role",
        "envelope_kind",
        "family",
        "axis_label",
        "grid_size",
        "dx",
        "dt",
        "dt_scale",
        "drive_mode",
        "drive_frequency",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "target_release_phase",
        "boundary_cubic_phase_sign",
        "target_reference_work_per_source_area",
        "work_per_source_area",
        "work_per_area_relative_error",
        "positive_work_before_cutoff",
        "primary_positive_work",
        "total_positive_work",
        "post_cutoff_positive_work",
        "energy_accounting_clean",
        "source_bandwidth",
        "source_far_sideband_fraction",
        "source_bandwidth_ratio_to_hard",
        "source_sideband_reduction_vs_hard",
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
        "shell_phase_coherence_mean",
        "radial_phase_coherence_mean",
        "angular_phase_coherence_mean",
        "node_phase_stability_mean",
        "instrumented_return_frame_count",
        "dominant_shell_frequency",
        "modal_spectral_bandwidth",
        "modal_spectral_concentration",
        "tail_packet_radius_mean",
        "tail_packet_width_mean",
        "tail_packet_spread_mean",
        "tail_outer_to_shell_mean",
        "outer_shell",
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
        "smooth_envelope_resolution_lift_classification",
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
        "smooth_envelope_resolution_lift_classification",
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
        "candidate_dominant_shell_frequency",
        "control_dominant_shell_frequency",
        "candidate_source_bandwidth_ratio_to_hard",
        "candidate_source_sideband_reduction_vs_hard",
        "candidate_tail_radius_shift_from_proof",
        "control_tail_radius_shift_from_proof",
        "candidate_tail_radius_shift_abs_not_worse",
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
    return ["gate", "smooth_envelope_resolution_lift_classification", "pass", "value", "reason"]


def _source_fields() -> list[str]:
    return [
        "variant",
        "prediction_role",
        "smooth_envelope_resolution_lift_classification",
        "role",
        "envelope_kind",
        "cutoff",
        "release_phase_cycles",
        "drive_frequency",
        "dt",
        "physical_duration",
        "work_proxy_scale",
        "energy_proxy",
        "natural_width",
        "carrier_peak_frequency",
        "carrier_peak_offset",
        "source_bandwidth",
        "source_mean_abs_offset",
        "main_band_fraction",
        "far_sideband_threshold",
        "far_sideband_fraction",
        "far_sideband_concentration",
    ]
