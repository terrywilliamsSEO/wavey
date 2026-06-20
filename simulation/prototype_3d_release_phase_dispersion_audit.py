"""Read-only dispersion/blur audit for the 41^3 to 51^3 release-phase lift."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import math

import numpy as np

from .config import SimulationConfig, load_json_config, save_json, simulation_config_from_dict
from .prototype_3d import EPSILON, Lattice3D, Prototype3DOptions, _base_3d_config
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import ALL_FACES
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_release_phase_modal_audit import (
    DEFAULT_LIFT_ROOT,
    DEFAULT_POSTMORTEM_ROOT,
    DEFAULT_PROOF_ROOT,
    _autocorr_metrics,
    _detected_peak_rows,
    _peak_rows,
    _peak_width_rows,
    _phase_coherence,
    _spectrum_metrics,
    _timing_metrics,
)
from .prototype_3d_source_sponge import _write_csv


DEFAULT_MODAL_ROOT = "runs/release_phase_modal_audit_3d_20260620_110344"
DEFAULT_CONFIG_PATH = "configs/long_validation_peak_0_92.json"


@dataclass(frozen=True)
class ReleasePhaseDispersionAuditOptions:
    """Options for the read-only release-phase dispersion audit."""

    output_root: str = "runs"
    config_path: str = DEFAULT_CONFIG_PATH
    proof_root: str = DEFAULT_PROOF_ROOT
    lift_root: str = DEFAULT_LIFT_ROOT
    postmortem_root: str = DEFAULT_POSTMORTEM_ROOT
    modal_root: str = DEFAULT_MODAL_ROOT
    reference_source_grid_size: int = 31
    shell_window_radius: float = 5.0
    shell_window_width: float = 4.0
    same_band_relative_tolerance: float = 0.16
    min_strict_major_loss: float = 1.0
    min_loose_recovery: float = 1.0
    min_bandwidth_growth: float = 0.05
    min_tail_radius_shift: float = 0.40
    max_lift_bandwidth_cv: float = 0.02
    max_lift_tail_radius_cv: float = 0.04
    source_area_delta_threshold: float = 0.10
    source_phase_delta_threshold: float = 0.05
    source_width_cell_delta_threshold: float = 0.30
    shell_width_cell_delta_threshold: float = 0.35
    finite_grid_concentration_ratio: float = 1.20


def run_3d_release_phase_dispersion_audit(
    *,
    options: ReleasePhaseDispersionAuditOptions | None = None,
) -> dict[str, Any]:
    """Build a read-only dispersion model from completed proof/lift artifacts."""

    options = options or ReleasePhaseDispersionAuditOptions()
    control_id = datetime.now().strftime("release_phase_dispersion_audit_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    proof_root = Path(options.proof_root)
    lift_root = Path(options.lift_root)
    postmortem_root = Path(options.postmortem_root)
    base_config = simulation_config_from_dict(load_json_config(Path(options.config_path)))

    postmortem_rows = _read_csv(postmortem_root / "release_phase_resolution_postmortem_summary.csv")
    selected = _selected_postmortem_rows(postmortem_rows)
    feature_rows: list[dict[str, Any]] = []
    peak_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    for row in selected:
        variant = str(row.get("variant"))
        source_kind = str(row.get("source_run_kind"))
        run_root = proof_root if source_kind == "proof_pack" else lift_root
        timeseries = _read_csv(run_root / variant / "packet_lifecycle_timeseries.csv")
        events = _read_csv(run_root / variant / "packet_lifecycle_events.csv")
        feature, peaks, phase = _diagnose_variant(row, timeseries, events, options)
        feature_rows.append(feature)
        peak_rows.extend(peaks)
        phase_rows.append(phase)

    source_rows = [_source_geometry_row(base_config, grid, options) for grid in (41, 51)]
    shell_rows = [_shell_window_row(base_config, grid, options) for grid in (41, 51)]
    comparison_rows = _comparison_rows(feature_rows, source_rows, shell_rows, options)
    classification = classify_release_phase_dispersion_audit(comparison_rows, options)
    prediction_rows = _prediction_rows(classification, comparison_rows)

    for row_set in (feature_rows, peak_rows, phase_rows, source_rows, shell_rows, comparison_rows, prediction_rows):
        for row in row_set:
            row["release_phase_dispersion_audit_classification"] = classification["label"]

    summary_csv = root / "dispersion_blur_model_summary.csv"
    feature_csv = root / "dispersion_feature_comparison.csv"
    source_csv = root / "source_discretization_comparison.csv"
    shell_csv = root / "shell_window_scaling_comparison.csv"
    phase_csv = root / "spatial_phase_coherence_audit.csv"
    prediction_csv = root / "dispersion_blur_prediction.csv"
    peak_csv = root / "return_peak_width_comparison.csv"
    report_path = root / "release_phase_dispersion_audit_report.md"
    _write_csv(summary_csv, comparison_rows, _comparison_fields())
    _write_csv(feature_csv, feature_rows, _feature_fields())
    _write_csv(source_csv, source_rows, _source_fields())
    _write_csv(shell_csv, shell_rows, _shell_fields())
    _write_csv(phase_csv, phase_rows, _phase_fields())
    _write_csv(prediction_csv, prediction_rows, _prediction_fields())
    _write_csv(peak_csv, peak_rows, _peak_fields())
    _write_report(report_path, control_id, comparison_rows, feature_rows, source_rows, shell_rows, phase_rows, prediction_rows, classification)
    save_json(
        root / "release_phase_dispersion_audit_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "proof_root": str(proof_root),
            "lift_root": str(lift_root),
            "postmortem_root": str(postmortem_root),
            "modal_root": options.modal_root,
            "summary_rows": comparison_rows,
            "feature_rows": feature_rows,
            "source_rows": source_rows,
            "shell_rows": shell_rows,
            "phase_rows": phase_rows,
            "prediction_rows": prediction_rows,
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": comparison_rows,
        "feature_rows": feature_rows,
        "source_rows": source_rows,
        "shell_rows": shell_rows,
        "phase_rows": phase_rows,
        "prediction_rows": prediction_rows,
        "summary_csv": str(summary_csv),
        "feature_csv": str(feature_csv),
        "source_csv": str(source_csv),
        "shell_csv": str(shell_csv),
        "phase_csv": str(phase_csv),
        "prediction_csv": str(prediction_csv),
        "peak_csv": str(peak_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_release_phase_dispersion_audit(
    comparison_rows: list[dict[str, Any]],
    options: ReleasePhaseDispersionAuditOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the observed 51^3 blur is predictable or safely correctable."""

    options = options or ReleasePhaseDispersionAuditOptions()
    row = comparison_rows[0] if comparison_rows else {}
    same_band = _bool(row.get("same_modal_band"))
    strict_loss = _float(row.get("strict_major_loss"))
    loose_recovery = _float(row.get("lift_loose_to_strict_major_recovery"))
    bandwidth_growth = _float(row.get("spectral_bandwidth_relative_delta"))
    tail_radius_shift = abs(_float(row.get("tail_radius_shift")))
    lift_bandwidth_cv = _float(row.get("lift_bandwidth_cv"))
    lift_tail_radius_cv = _float(row.get("lift_tail_radius_cv"))
    concentration_ratio = _float(row.get("proof_to_lift_concentration_ratio"))
    source_area_delta = abs(_float(row.get("source_effective_area_relative_delta")))
    source_phase_delta = abs(_float(row.get("source_phase_strength_delta")))
    source_width_cell_delta = abs(_float(row.get("source_width_in_dx_relative_delta")))
    shell_width_cell_delta = abs(_float(row.get("shell_width_in_dx_relative_delta")))
    shell_physical_width_delta = abs(_float(row.get("shell_window_width_physical_relative_delta")))
    spatial_phase_available = _bool(row.get("true_spatial_phase_frames_available"))
    blur_present = (
        strict_loss >= options.min_strict_major_loss
        and loose_recovery >= options.min_loose_recovery
        and (bandwidth_growth >= options.min_bandwidth_growth or tail_radius_shift >= options.min_tail_radius_shift)
    )
    blur_consistent = (
        lift_bandwidth_cv <= options.max_lift_bandwidth_cv
        and lift_tail_radius_cv <= options.max_lift_tail_radius_cv
    )
    source_discretization_changed = (
        source_area_delta >= options.source_area_delta_threshold
        or source_phase_delta >= options.source_phase_delta_threshold
        or source_width_cell_delta >= options.source_width_cell_delta_threshold
    )
    shell_window_changed = (
        shell_physical_width_delta > EPSILON
        or shell_width_cell_delta >= options.shell_width_cell_delta_threshold
    )
    checks = {
        "same_modal_band": same_band,
        "strict_major_loss": strict_loss,
        "lift_loose_to_strict_major_recovery": loose_recovery,
        "spectral_bandwidth_relative_delta": bandwidth_growth,
        "tail_radius_shift": tail_radius_shift,
        "lift_bandwidth_cv": lift_bandwidth_cv,
        "lift_tail_radius_cv": lift_tail_radius_cv,
        "proof_to_lift_concentration_ratio": concentration_ratio,
        "source_discretization_changed": source_discretization_changed,
        "source_effective_area_relative_delta": source_area_delta,
        "source_phase_strength_delta": source_phase_delta,
        "source_width_in_dx_relative_delta": source_width_cell_delta,
        "shell_window_changed": shell_window_changed,
        "shell_width_in_dx_relative_delta": shell_width_cell_delta,
        "true_spatial_phase_frames_available": spatial_phase_available,
        "mechanism_candidate": "none",
    }
    if not same_band or concentration_ratio >= options.finite_grid_concentration_ratio:
        return {
            "label": "finite_grid_resonance_likely",
            "reason": "The lifted rows do not preserve the proof modal coincidence strongly enough for a scalable blur model.",
            "checks": checks,
        }
    if blur_present and source_discretization_changed and spatial_phase_available:
        checks["mechanism_candidate"] = "source-discretization source-shaping correction"
        return {
            "label": "source_discretization_correction_supported",
            "reason": "The same modal band survives and the blur aligns with a source discretization change while spatial phase data is available.",
            "checks": checks,
        }
    if blur_present and shell_window_changed and spatial_phase_available:
        checks["mechanism_candidate"] = "shell-window scaling correction"
        return {
            "label": "shell_window_scaling_supported",
            "reason": "The same modal band survives and the observed blur aligns with shell-window sampling changes while spatial phase data is available.",
            "checks": checks,
        }
    if same_band and blur_present and blur_consistent:
        return {
            "label": "scalable_blur_model_supported",
            "reason": "The 51^3 rows preserve the same shell band and show consistent strict-count shrinkage, bandwidth growth, and tail-radius drift, but no safe source-shaped candidate is identified without true spatial phase frames.",
            "checks": checks,
        }
    return {
        "label": "no_safe_next_candidate",
        "reason": "The available read-only artifacts do not isolate a fixable source, shell-window, or scalable blur mechanism.",
        "checks": checks,
    }


def _selected_postmortem_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        group = str(row.get("group"))
        if group == "proof_winner":
            out.append({**row, "audit_group": "proof_cluster", "source_run_kind": "proof_pack"})
        elif group == "lift_candidate":
            out.append({**row, "audit_group": "lift_candidate", "source_run_kind": "resolution_lift"})
        elif group == "lift_control":
            out.append({**row, "audit_group": "lift_control", "source_run_kind": "resolution_lift"})
    return out


def _diagnose_variant(
    row: dict[str, Any],
    timeseries: list[dict[str, Any]],
    events: list[dict[str, Any]],
    options: ReleasePhaseDispersionAuditOptions,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    variant = str(row.get("variant"))
    group = str(row.get("audit_group"))
    cutoff = _float(row.get("drive_cutoff_time"))
    times = _array(ts.get("time") for ts in timeseries)
    shell = _array(ts.get("shell_window_energy") for ts in timeseries)
    radius = _array(ts.get("packet_peak_radius") for ts in timeseries)
    centroid = _array(ts.get("packet_centroid_radius") for ts in timeseries)
    width = _array(ts.get("packet_radial_width") for ts in timeseries)
    spread = _array(ts.get("packet_radial_spread") for ts in timeseries)
    outer_ratio = _array(ts.get("outer_to_shell_energy") for ts in timeseries)
    shell_fraction = _array(ts.get("shell_fraction_of_total") for ts in timeseries)
    post_mask = times > cutoff if times.size else np.asarray([], dtype=bool)
    tail_mask = times >= 50.0 if times.size else np.asarray([], dtype=bool)
    spectrum = _spectrum_metrics(times[post_mask], shell[post_mask])
    autocorr = _autocorr_metrics(times[post_mask], shell[post_mask])
    peaks = _peak_rows(events)
    if not peaks and times.size:
        peaks = _detected_peak_rows(times, shell, cutoff)
    timing = _timing_metrics(peaks)
    peak_width_rows = _peak_width_rows(variant, group, times, shell, peaks, spectrum["dominant_shell_frequency"])
    shell_peak_time = _float(row.get("shell_peak_time"))
    shell_peak_idx = int(np.argmin(np.abs(times - shell_peak_time))) if times.size else 0
    radial_group_velocity = _slope(times[post_mask], centroid[post_mask]) if times.size else 0.0
    tail_radius = _mean(radius[tail_mask])
    shell_peak_radius = float(radius[shell_peak_idx]) if radius.size else 0.0
    tail_radius_drift = tail_radius - shell_peak_radius
    feature = {
        "variant": variant,
        "audit_group": group,
        "source_run_kind": row.get("source_run_kind"),
        "grid_size": row.get("grid_size"),
        "drive_cutoff_time": cutoff,
        "cutoff_phase_cycles": row.get("cutoff_phase_cycles"),
        "loose_major_peaks": row.get("major_peaks_at_0p20"),
        "loose_refocus_peaks": row.get("refocus_peaks_at_0p20"),
        "default_major_peaks": row.get("major_peaks_at_0p30"),
        "default_refocus_peaks": row.get("refocus_peaks_at_0p30"),
        "strict_major_peaks": row.get("major_peaks_at_0p40"),
        "strict_refocus_peaks": row.get("refocus_peaks_at_0p40"),
        "dominant_shell_frequency": spectrum["dominant_shell_frequency"],
        "dominant_spectral_concentration": spectrum["dominant_spectral_concentration"],
        "spectral_bandwidth": spectrum["spectral_bandwidth"],
        "spectral_top3_fraction": spectrum["spectral_top3_fraction"],
        "autocorrelation_decay_time": autocorr["autocorrelation_decay_time"],
        "lag1_autocorrelation": autocorr["lag1_autocorrelation"],
        "mean_return_peak_width": _mean(row_.get("peak_width_time") for row_ in peak_width_rows),
        "return_peak_width_cv": _cv(row_.get("peak_width_time") for row_ in peak_width_rows),
        "mean_inter_peak_spacing": timing["mean_inter_peak_spacing"],
        "return_timing_jitter": timing["return_timing_jitter"],
        "return_timing_regularity": timing["return_timing_regularity"],
        "peak_amplitude_decay": timing["peak_amplitude_decay"],
        "first_peak_energy": timing["first_peak_energy"],
        "last_peak_energy": timing["last_peak_energy"],
        "last_to_first_peak_ratio": timing["last_to_first_peak_ratio"],
        "radial_group_velocity": radial_group_velocity,
        "tail_radius_mean": tail_radius,
        "shell_peak_radius": shell_peak_radius,
        "tail_radius_drift_from_shell_peak": tail_radius_drift,
        "tail_radius_velocity": _slope(times[tail_mask], radius[tail_mask]) if times.size else 0.0,
        "tail_centroid_velocity": _slope(times[tail_mask], centroid[tail_mask]) if times.size else 0.0,
        "tail_packet_width_mean": _mean(width[tail_mask]),
        "tail_packet_width_velocity": _slope(times[tail_mask], width[tail_mask]) if times.size else 0.0,
        "tail_packet_spread_mean": _mean(spread[tail_mask]),
        "tail_packet_spread_velocity": _slope(times[tail_mask], spread[tail_mask]) if times.size else 0.0,
        "tail_outer_to_shell_mean": _mean(outer_ratio[tail_mask]),
        "tail_shell_fraction_mean": _mean(shell_fraction[tail_mask]),
        "post_cutoff_shell_area": row.get("post_cutoff_shell_area"),
        "tail_area_after_t50": row.get("tail_area_after_t50"),
        "no_exit": row.get("no_exit"),
        "global_outer_false": row.get("global_outer_false"),
        "spatial_phase_frames_available": False,
        "scalar_return_phase_locking_proxy": _phase_coherence(peaks, spectrum["dominant_shell_frequency"]),
    }
    phase = {
        "variant": variant,
        "audit_group": group,
        "true_spatial_phase_frames_available": False,
        "scalar_return_phase_locking_proxy": feature["scalar_return_phase_locking_proxy"],
        "phase_metric_used": "scalar shell-energy return phase proxy",
        "required_for_source_shaping": True,
        "notes": "Existing proof/lift artifacts store scalar shell timeseries but no spatial u/v shell phase frames.",
    }
    return feature, peak_width_rows, phase


def _source_geometry_row(
    base: SimulationConfig,
    grid_size: int,
    options: ReleasePhaseDispersionAuditOptions,
) -> dict[str, Any]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    config = _base_3d_config(f"source_geometry_{grid_size}", base, Prototype3DOptions(grid_size=grid_size), "boundary", "cubic")
    config.defect_stiffness_multiplier = 1.0
    config.defect_damping_multiplier = 1.0
    config.defect_coupling_multiplier = 1.0
    config.sponge_strength *= 3.0
    config.boundary_source_inner_distance = config.sponge_width
    config.boundary_source_width = source_width
    config.boundary_faces = ALL_FACES
    config.boundary_cubic_phase_sign = -1.0
    lattice = Lattice3D(config)
    source = lattice.source
    weights = source.geometric_weights[source.mask]
    phases = source.phase_map[source.mask]
    phase_vector = np.sum(weights * np.exp(1.0j * phases)) / max(float(np.sum(weights)), EPSILON) if weights.size else 0.0
    return {
        "grid_size": grid_size,
        "dx": config.dx,
        "domain_size": config.domain_size,
        "source_width_physical": source.source_width,
        "source_width_in_dx": source.source_width / max(config.dx, EPSILON),
        "source_inner_distance": config.boundary_source_inner_distance,
        "source_inner_distance_in_dx": config.boundary_source_inner_distance / max(config.dx, EPSILON),
        "source_cell_count": int(np.sum(source.mask)),
        "source_geometric_weight_sum": float(np.sum(source.geometric_weights)),
        "effective_source_area": source.effective_area,
        "effective_source_volume": source.effective_volume,
        "boundary_area": source.boundary_area,
        "source_area_fraction_of_boundary": source.effective_area / max(source.boundary_area, EPSILON),
        "source_phase_circular_strength": float(abs(phase_vector)),
        "source_phase_spread_proxy": math.sqrt(max(0.0, -2.0 * math.log(max(float(abs(phase_vector)), EPSILON)))),
    }


def _shell_window_row(
    base: SimulationConfig,
    grid_size: int,
    options: ReleasePhaseDispersionAuditOptions,
) -> dict[str, Any]:
    config = _base_3d_config(f"shell_window_{grid_size}", base, Prototype3DOptions(grid_size=grid_size), "boundary", "cubic")
    lattice = Lattice3D(config)
    radius = lattice.coords["radius"]
    shell_inner = options.shell_window_radius
    shell_outer = options.shell_window_radius + options.shell_window_width
    shell_mask = (radius > shell_inner) & (radius <= shell_outer)
    inner_neighbor_mask = (radius > max(0.0, shell_inner - options.shell_window_width)) & (radius <= shell_inner)
    outer_neighbor_mask = (radius > shell_outer) & (radius <= shell_outer + options.shell_window_width)
    return {
        "grid_size": grid_size,
        "dx": config.dx,
        "shell_window_radius": options.shell_window_radius,
        "shell_window_width_physical": options.shell_window_width,
        "shell_window_width_in_dx": options.shell_window_width / max(config.dx, EPSILON),
        "shell_inner_radius": shell_inner,
        "shell_outer_radius": shell_outer,
        "shell_cell_count": int(np.sum(shell_mask)),
        "shell_cell_volume": float(np.sum(shell_mask) * config.cell_volume),
        "inner_neighbor_cell_count": int(np.sum(inner_neighbor_mask)),
        "outer_neighbor_cell_count": int(np.sum(outer_neighbor_mask)),
        "neighbor_window_data_available": False,
        "notes": "Existing lifecycle artifacts do not store per-neighbor radial-window energy; this row records deterministic shell sampling geometry.",
    }


def _comparison_rows(
    features: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    shell_rows: list[dict[str, Any]],
    options: ReleasePhaseDispersionAuditOptions,
) -> list[dict[str, Any]]:
    proof = [row for row in features if row.get("audit_group") == "proof_cluster"]
    lift = [row for row in features if str(row.get("audit_group", "")).startswith("lift_")]
    source_by_grid = {int(_float(row.get("grid_size"))): row for row in source_rows}
    shell_by_grid = {int(_float(row.get("grid_size"))): row for row in shell_rows}
    proof_freq = _mean(row.get("dominant_shell_frequency") for row in proof)
    lift_freq = _mean(row.get("dominant_shell_frequency") for row in lift)
    proof_conc = _mean(row.get("dominant_spectral_concentration") for row in proof)
    lift_conc = _mean(row.get("dominant_spectral_concentration") for row in lift)
    proof_bandwidth = _mean(row.get("spectral_bandwidth") for row in proof)
    lift_bandwidth = _mean(row.get("spectral_bandwidth") for row in lift)
    proof_strict = _mean(row.get("strict_major_peaks") for row in proof)
    lift_strict = _mean(row.get("strict_major_peaks") for row in lift)
    lift_loose = _mean(row.get("loose_major_peaks") for row in lift)
    proof_tail_radius = _mean(row.get("tail_radius_mean") for row in proof)
    lift_tail_radius = _mean(row.get("tail_radius_mean") for row in lift)
    proof_width = _mean(row.get("mean_return_peak_width") for row in proof)
    lift_width = _mean(row.get("mean_return_peak_width") for row in lift)
    source41 = source_by_grid.get(41, {})
    source51 = source_by_grid.get(51, {})
    shell41 = shell_by_grid.get(41, {})
    shell51 = shell_by_grid.get(51, {})
    row = {
        "comparison": "proof_41_vs_lift_51",
        "proof_row_count": len(proof),
        "lift_row_count": len(lift),
        "proof_dominant_frequency_mean": proof_freq,
        "lift_dominant_frequency_mean": lift_freq,
        "same_modal_band": _same_band(proof_freq, lift_freq, options),
        "proof_spectral_concentration_mean": proof_conc,
        "lift_spectral_concentration_mean": lift_conc,
        "proof_to_lift_concentration_ratio": proof_conc / max(lift_conc, EPSILON),
        "proof_bandwidth_mean": proof_bandwidth,
        "lift_bandwidth_mean": lift_bandwidth,
        "spectral_bandwidth_relative_delta": _relative_delta(lift_bandwidth, proof_bandwidth),
        "lift_bandwidth_cv": _cv(row.get("spectral_bandwidth") for row in lift),
        "proof_return_peak_width_mean": proof_width,
        "lift_return_peak_width_mean": lift_width,
        "return_peak_width_relative_delta": _relative_delta(lift_width, proof_width),
        "proof_tail_radius_mean": proof_tail_radius,
        "lift_tail_radius_mean": lift_tail_radius,
        "tail_radius_shift": lift_tail_radius - proof_tail_radius,
        "lift_tail_radius_cv": _cv(row.get("tail_radius_mean") for row in lift),
        "proof_tail_packet_width_mean": _mean(row.get("tail_packet_width_mean") for row in proof),
        "lift_tail_packet_width_mean": _mean(row.get("tail_packet_width_mean") for row in lift),
        "tail_packet_width_relative_delta": _relative_delta(
            _mean(row.get("tail_packet_width_mean") for row in lift),
            _mean(row.get("tail_packet_width_mean") for row in proof),
        ),
        "proof_radial_group_velocity_mean": _mean(row.get("radial_group_velocity") for row in proof),
        "lift_radial_group_velocity_mean": _mean(row.get("radial_group_velocity") for row in lift),
        "proof_outer_shell_mean": _mean(row.get("tail_outer_to_shell_mean") for row in proof),
        "lift_outer_shell_mean": _mean(row.get("tail_outer_to_shell_mean") for row in lift),
        "strict_major_loss": proof_strict - lift_strict,
        "lift_loose_to_strict_major_recovery": lift_loose - lift_strict,
        "source_effective_area_relative_delta": _relative_delta(_float(source51.get("effective_source_area")), _float(source41.get("effective_source_area"))),
        "source_width_in_dx_relative_delta": _relative_delta(_float(source51.get("source_width_in_dx")), _float(source41.get("source_width_in_dx"))),
        "source_phase_strength_delta": _float(source51.get("source_phase_circular_strength")) - _float(source41.get("source_phase_circular_strength")),
        "shell_window_width_physical_relative_delta": _relative_delta(_float(shell51.get("shell_window_width_physical")), _float(shell41.get("shell_window_width_physical"))),
        "shell_width_in_dx_relative_delta": _relative_delta(_float(shell51.get("shell_window_width_in_dx")), _float(shell41.get("shell_window_width_in_dx"))),
        "true_spatial_phase_frames_available": all(_bool(row.get("spatial_phase_frames_available")) for row in features) if features else False,
        "safe_source_shaping_candidate": "none",
    }
    return [row]


def _prediction_rows(classification: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    row = rows[0] if rows else {}
    label = classification["label"]
    candidate = "none"
    reason = "No new physics candidate is recommended from this read-only audit."
    if label == "source_discretization_correction_supported":
        candidate = "single source-discretization correction candidate"
        reason = "Source discretization is isolated and true spatial phase data is available."
    elif label == "shell_window_scaling_supported":
        candidate = "single shell-window scaling correction candidate"
        reason = "Shell-window scaling is isolated and true spatial phase data is available."
    elif label == "scalable_blur_model_supported":
        reason = "Blur is predictable across the 51^3 rows, but true spatial shell phase frames are missing, so do not launch a source-shaped candidate yet."
    elif label == "finite_grid_resonance_likely":
        reason = "Treat the 41^3 proof as a likely finite-grid modal coincidence until a new mechanism appears."
    return [
        {
            "recommendation": candidate,
            "classification": label,
            "specific_mechanism": classification.get("checks", {}).get("mechanism_candidate", "none"),
            "reason": reason,
            "same_modal_band": row.get("same_modal_band"),
            "bandwidth_delta": row.get("spectral_bandwidth_relative_delta"),
            "tail_radius_shift": row.get("tail_radius_shift"),
            "spatial_phase_frames_required": True,
        }
    ]


def _write_report(
    path: Path,
    control_id: str,
    comparison_rows: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    shell_rows: list[dict[str, Any]],
    phase_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    classification: dict[str, Any],
) -> None:
    row = comparison_rows[0] if comparison_rows else {}
    checks = classification.get("checks", {})
    lines = [
        f"# Release Phase Dispersion Audit: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only dispersion/blur model for the quarter-dt 41^3 release-phase proof cluster versus the failed 51^3 resolution lift. No new physics was run.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Mechanism-derived next candidate: `{checks.get('mechanism_candidate', 'none')}`",
        "",
        "## Blur Model Checks",
        "",
        f"- Same modal band: `{row.get('same_modal_band')}`",
        f"- Proof/lift dominant frequency: `{_format(row.get('proof_dominant_frequency_mean'))}` / `{_format(row.get('lift_dominant_frequency_mean'))}`",
        f"- Bandwidth relative delta: `{_format(row.get('spectral_bandwidth_relative_delta'))}`",
        f"- Tail radius shift: `{_format(row.get('tail_radius_shift'))}`",
        f"- Strict major loss: `{_format(row.get('strict_major_loss'))}`",
        f"- Lift loose-to-strict major recovery: `{_format(row.get('lift_loose_to_strict_major_recovery'))}`",
        f"- Lift bandwidth CV: `{_format(row.get('lift_bandwidth_cv'))}`",
        f"- Lift tail-radius CV: `{_format(row.get('lift_tail_radius_cv'))}`",
        f"- True spatial phase frames available: `{row.get('true_spatial_phase_frames_available')}`",
        "",
        "## Feature Comparison",
        "",
        "| Group | Variant | Grid | Loose | Default | Strict | Freq | Bandwidth | Peak Width | Tail Radius | Outer/Shell |",
        "| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for feature in feature_rows:
        lines.append(
            "| "
            f"{feature.get('audit_group')} | {feature.get('variant')} | {feature.get('grid_size')} | "
            f"{feature.get('loose_major_peaks')}/{feature.get('loose_refocus_peaks')} | "
            f"{feature.get('default_major_peaks')}/{feature.get('default_refocus_peaks')} | "
            f"{feature.get('strict_major_peaks')}/{feature.get('strict_refocus_peaks')} | "
            f"{_format(feature.get('dominant_shell_frequency'))} | "
            f"{_format(feature.get('spectral_bandwidth'))} | "
            f"{_format(feature.get('mean_return_peak_width'))} | "
            f"{_format(feature.get('tail_radius_mean'))} | "
            f"{_format(feature.get('tail_outer_to_shell_mean'))} |"
        )
    lines.extend(
        [
            "",
            "## Source And Shell Sampling",
            "",
            "| Grid | dx | Source Width/dx | Source Cells | Source Area | Phase Strength | Shell Width/dx | Shell Cells |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    shell_by_grid = {row.get("grid_size"): row for row in shell_rows}
    for source in source_rows:
        shell = shell_by_grid.get(source.get("grid_size"), {})
        lines.append(
            "| "
            f"{source.get('grid_size')} | {_format(source.get('dx'))} | "
            f"{_format(source.get('source_width_in_dx'))} | {source.get('source_cell_count')} | "
            f"{_format(source.get('effective_source_area'))} | "
            f"{_format(source.get('source_phase_circular_strength'))} | "
            f"{_format(shell.get('shell_window_width_in_dx'))} | {shell.get('shell_cell_count')} |"
        )
    lines.extend(
        [
            "",
            "## Spatial Phase Gap",
            "",
            "The existing proof and lift artifacts do not store spatial shell phase frames. This audit therefore uses scalar shell-energy return phase locking only as a proxy and blocks any source-shaped candidate recommendation that would require true spatial phase pre-compensation.",
            "",
            "## Prediction",
            "",
        ]
    )
    for prediction in prediction_rows:
        lines.append(f"- `{prediction.get('recommendation')}`: {prediction.get('reason')}")
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `release_phase_dispersion_audit_report.md`",
            "- `dispersion_blur_model_summary.csv`",
            "- `dispersion_feature_comparison.csv`",
            "- `source_discretization_comparison.csv`",
            "- `shell_window_scaling_comparison.csv`",
            "- `spatial_phase_coherence_audit.csv`",
            "- `dispersion_blur_prediction.csv`",
            "- `return_peak_width_comparison.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _array(values: Any) -> np.ndarray:
    return np.asarray([_float(value) for value in values], dtype=float)


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes"}


def _mean(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    return float(np.mean(parsed)) if parsed.size else 0.0


def _cv(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    if parsed.size == 0:
        return 0.0
    mean = float(np.mean(parsed))
    return float(np.std(parsed) / max(abs(mean), EPSILON))


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 3 or y.size < 3 or float(np.ptp(x)) <= EPSILON:
        return 0.0
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)


def _relative_delta(value: float, reference: float) -> float:
    return (value - reference) / max(abs(reference), EPSILON)


def _same_band(proof_freq: float, lift_freq: float, options: ReleasePhaseDispersionAuditOptions) -> bool:
    if proof_freq <= EPSILON or lift_freq <= EPSILON:
        return False
    return abs(lift_freq - proof_freq) / max(abs(proof_freq), EPSILON) <= options.same_band_relative_tolerance


def _comparison_fields() -> list[str]:
    return [
        "comparison",
        "release_phase_dispersion_audit_classification",
        "proof_row_count",
        "lift_row_count",
        "proof_dominant_frequency_mean",
        "lift_dominant_frequency_mean",
        "same_modal_band",
        "proof_spectral_concentration_mean",
        "lift_spectral_concentration_mean",
        "proof_to_lift_concentration_ratio",
        "proof_bandwidth_mean",
        "lift_bandwidth_mean",
        "spectral_bandwidth_relative_delta",
        "lift_bandwidth_cv",
        "proof_return_peak_width_mean",
        "lift_return_peak_width_mean",
        "return_peak_width_relative_delta",
        "proof_tail_radius_mean",
        "lift_tail_radius_mean",
        "tail_radius_shift",
        "lift_tail_radius_cv",
        "proof_tail_packet_width_mean",
        "lift_tail_packet_width_mean",
        "tail_packet_width_relative_delta",
        "proof_radial_group_velocity_mean",
        "lift_radial_group_velocity_mean",
        "proof_outer_shell_mean",
        "lift_outer_shell_mean",
        "strict_major_loss",
        "lift_loose_to_strict_major_recovery",
        "source_effective_area_relative_delta",
        "source_width_in_dx_relative_delta",
        "source_phase_strength_delta",
        "shell_window_width_physical_relative_delta",
        "shell_width_in_dx_relative_delta",
        "true_spatial_phase_frames_available",
        "safe_source_shaping_candidate",
    ]


def _feature_fields() -> list[str]:
    return [
        "variant",
        "release_phase_dispersion_audit_classification",
        "audit_group",
        "source_run_kind",
        "grid_size",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "loose_major_peaks",
        "loose_refocus_peaks",
        "default_major_peaks",
        "default_refocus_peaks",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "dominant_shell_frequency",
        "dominant_spectral_concentration",
        "spectral_bandwidth",
        "spectral_top3_fraction",
        "autocorrelation_decay_time",
        "lag1_autocorrelation",
        "mean_return_peak_width",
        "return_peak_width_cv",
        "mean_inter_peak_spacing",
        "return_timing_jitter",
        "return_timing_regularity",
        "peak_amplitude_decay",
        "first_peak_energy",
        "last_peak_energy",
        "last_to_first_peak_ratio",
        "radial_group_velocity",
        "tail_radius_mean",
        "shell_peak_radius",
        "tail_radius_drift_from_shell_peak",
        "tail_radius_velocity",
        "tail_centroid_velocity",
        "tail_packet_width_mean",
        "tail_packet_width_velocity",
        "tail_packet_spread_mean",
        "tail_packet_spread_velocity",
        "tail_outer_to_shell_mean",
        "tail_shell_fraction_mean",
        "post_cutoff_shell_area",
        "tail_area_after_t50",
        "no_exit",
        "global_outer_false",
        "spatial_phase_frames_available",
        "scalar_return_phase_locking_proxy",
    ]


def _source_fields() -> list[str]:
    return [
        "grid_size",
        "release_phase_dispersion_audit_classification",
        "dx",
        "domain_size",
        "source_width_physical",
        "source_width_in_dx",
        "source_inner_distance",
        "source_inner_distance_in_dx",
        "source_cell_count",
        "source_geometric_weight_sum",
        "effective_source_area",
        "effective_source_volume",
        "boundary_area",
        "source_area_fraction_of_boundary",
        "source_phase_circular_strength",
        "source_phase_spread_proxy",
    ]


def _shell_fields() -> list[str]:
    return [
        "grid_size",
        "release_phase_dispersion_audit_classification",
        "dx",
        "shell_window_radius",
        "shell_window_width_physical",
        "shell_window_width_in_dx",
        "shell_inner_radius",
        "shell_outer_radius",
        "shell_cell_count",
        "shell_cell_volume",
        "inner_neighbor_cell_count",
        "outer_neighbor_cell_count",
        "neighbor_window_data_available",
        "notes",
    ]


def _phase_fields() -> list[str]:
    return [
        "variant",
        "release_phase_dispersion_audit_classification",
        "audit_group",
        "true_spatial_phase_frames_available",
        "scalar_return_phase_locking_proxy",
        "phase_metric_used",
        "required_for_source_shaping",
        "notes",
    ]


def _prediction_fields() -> list[str]:
    return [
        "recommendation",
        "release_phase_dispersion_audit_classification",
        "classification",
        "specific_mechanism",
        "reason",
        "same_modal_band",
        "bandwidth_delta",
        "tail_radius_shift",
        "spatial_phase_frames_required",
    ]


def _peak_fields() -> list[str]:
    return [
        "variant",
        "release_phase_dispersion_audit_classification",
        "audit_group",
        "peak_index",
        "peak_time",
        "peak_energy",
        "previous_interval",
        "peak_width_time",
        "phase_at_dominant_frequency_cycles",
    ]
