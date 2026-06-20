"""Spatial shell-phase frame instrumentation for the passive release-phase branch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import math

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Lattice3D, Prototype3DConfig, _calibrate_amplitude, _primary_drive_active, _second_pulse_active
from .prototype_3d_cutoff_phase_map import _add_control_fields, threshold_robust_refocusing_scores
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _phase_vector, _shell_width, _threshold_like_options
from .prototype_3d_packet_lifecycle import (
    PacketLifecycle3DOptions,
    _event_fields,
    _profile_width,
    _summarize_lifecycle,
    _timeseries_fields,
    _weighted_mean,
    _weighted_std,
)
from .prototype_3d_refocusing_engineering import _format, _lifecycle_options
from .prototype_3d_release_phase_proof_pack import (
    ReleasePhaseProofPackOptions,
    _add_proof_fields,
    _variant_plan as _proof_variant_plan,
)
from .prototype_3d_release_phase_resolution_lift import (
    ReleasePhaseResolutionLiftOptions,
    _add_resolution_lift_fields,
    _variant_plan as _lift_variant_plan,
)
from .prototype_3d_source_sponge import _effective_source_area, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area
from .prototype_3d_transport_packet import _radial_flux_density, _radial_profile_sum


@dataclass(frozen=True)
class SpatialPhaseInstrumentationOptions:
    """Options for the fixed two-row spatial phase instrumentation pass."""

    output_root: str = "runs"
    proof_grid_size: int = 41
    lift_grid_size: int = 51
    reference_source_grid_size: int = 31
    physical_duration: float = 96.0
    sample_every: int = 10
    diagnostic_sample_every: int = 4
    radial_bins: int = 40
    shell_window_radius: float = 5.0
    shell_window_width: float | None = 4.0
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    target_work_per_source_area: float | None = None
    fixed_drive_frequency: float = 0.92
    proof_cutoff: float = 17.94
    lift_target_release_phase: float = 0.5071
    dt_scale: float = 0.25
    arrival_threshold_fraction: float = 0.10
    exit_threshold_fraction: float = 0.12
    exit_hold_samples: int = 10
    peak_threshold_fraction: float = 0.30
    frame_peak_threshold_fraction: float = 0.20
    refocus_threshold_fraction: float = 0.35
    min_peak_separation_time: float = 5.0
    min_refocus_count: int = 2
    min_width_growth_fraction: float = 0.30
    min_decay_rate_magnitude: float = 0.01
    max_return_frames: int = 12
    radial_phase_bins: int = 12
    angular_theta_bins: int = 8
    angular_polar_bins: int = 4
    coherence_drop_threshold: float = 0.12
    radial_coherence_drop_threshold: float = 0.12
    angular_coherence_drop_threshold: float = 0.12
    node_stability_drop_threshold: float = 0.10
    width_growth_threshold: float = 0.15
    center_shift_threshold: float = 0.40


def run_3d_spatial_phase_instrumentation(
    base_config: SimulationConfig,
    *,
    options: SpatialPhaseInstrumentationOptions | None = None,
) -> dict[str, Any]:
    """Reproduce the fixed 41^3 proof row and 51^3 failed-lift row with shell phase frames."""

    options = options or SpatialPhaseInstrumentationOptions()
    control_id = datetime.now().strftime("spatial_phase_instrumentation_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    specs = _variant_specs(base_config, options)
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

    for spec in specs:
        config = spec["config"]
        plan_options = spec["options"]
        lifecycle_options = _lifecycle_options(plan_options)
        target_work_per_area = _calibrate_fixed_variant(base_config, config, plan_options, lifecycle_options)
        result = _run_spatial_phase_variant(config, root, lifecycle_options, options)
        summary = result["summary"]
        _add_control_fields(summary, config, plan_options, target_work_per_area)
        spec["annotate"](summary, config)
        summary["audit_group"] = spec["audit_group"]
        summary["source_run_kind"] = spec["source_run_kind"]
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

    robust_rows = threshold_robust_refocusing_scores(rows, timeseries_rows, options) if rows else []
    _merge_robust_counts(rows, robust_rows)
    comparison_rows = _comparison_rows(rows, radial_coherence_rows, angular_rows, options)
    classification = classify_spatial_phase_instrumentation(rows, comparison_rows, options)
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
    ):
        for row in row_set:
            row["spatial_phase_instrumentation_classification"] = classification["label"]

    summary_csv = root / "spatial_phase_instrumentation_summary.csv"
    robust_csv = root / "spatial_phase_threshold_robust_score.csv"
    threshold_csv = root / "spatial_phase_event_threshold_counts.csv"
    timeseries_csv = root / "spatial_phase_lifecycle_timeseries.csv"
    events_csv = root / "spatial_phase_lifecycle_events.csv"
    frame_index_csv = root / "spatial_phase_frame_index.csv"
    displacement_csv = root / "shell_displacement_frames.csv"
    velocity_csv = root / "shell_velocity_frames.csv"
    radial_frames_csv = root / "radial_shell_phase_frames.csv"
    radial_coherence_csv = root / "shell_phase_coherence_by_radius.csv"
    angular_csv = root / "angular_shell_phase_coherence.csv"
    stability_csv = root / "node_antinode_stability_maps.csv"
    drift_csv = root / "phase_drift_across_return_peaks.csv"
    comparison_csv = root / "spatial_phase_41_vs_51_comparison.csv"
    report_path = root / "spatial_phase_instrumentation_report.md"

    _write_csv(summary_csv, rows, _summary_fields())
    _write_csv(robust_csv, robust_rows, _robust_fields())
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
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_report(report_path, control_id, rows, comparison_rows, classification, options)
    save_json(
        root / "spatial_phase_instrumentation_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": rows,
            "comparison_rows": comparison_rows,
            "summary_csv": str(summary_csv),
            "robust_csv": str(robust_csv),
            "threshold_csv": str(threshold_csv),
            "timeseries_csv": str(timeseries_csv),
            "events_csv": str(events_csv),
            "frame_index_csv": str(frame_index_csv),
            "displacement_csv": str(displacement_csv),
            "velocity_csv": str(velocity_csv),
            "radial_frames_csv": str(radial_frames_csv),
            "radial_coherence_csv": str(radial_coherence_csv),
            "angular_csv": str(angular_csv),
            "stability_csv": str(stability_csv),
            "drift_csv": str(drift_csv),
            "comparison_csv": str(comparison_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": rows,
        "comparison_rows": comparison_rows,
        "summary_csv": str(summary_csv),
        "robust_csv": str(robust_csv),
        "threshold_csv": str(threshold_csv),
        "timeseries_csv": str(timeseries_csv),
        "events_csv": str(events_csv),
        "frame_index_csv": str(frame_index_csv),
        "displacement_csv": str(displacement_csv),
        "velocity_csv": str(velocity_csv),
        "radial_frames_csv": str(radial_frames_csv),
        "radial_coherence_csv": str(radial_coherence_csv),
        "angular_csv": str(angular_csv),
        "stability_csv": str(stability_csv),
        "drift_csv": str(drift_csv),
        "comparison_csv": str(comparison_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_spatial_phase_instrumentation(
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: SpatialPhaseInstrumentationOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the 51^3 blur is spatially coherent, decoherent, shifted, or unresolved."""

    options = options or SpatialPhaseInstrumentationOptions()
    comparison = comparison_rows[0] if comparison_rows else {}
    proof = next((row for row in rows if row.get("audit_group") == "proof_41_reference"), {})
    lift = next((row for row in rows if row.get("audit_group") == "failed_lift_51_candidate"), {})
    shell_drop = _float(comparison.get("shell_phase_coherence_drop"))
    radial_drop = _float(comparison.get("radial_phase_coherence_drop"))
    angular_drop = _float(comparison.get("angular_phase_coherence_drop"))
    node_drop = _float(comparison.get("node_phase_stability_drop"))
    width_growth = _float(comparison.get("return_radial_spread_relative_growth"))
    center_shift = abs(_float(comparison.get("return_radial_centroid_shift")))
    strict_loss = _float(comparison.get("strict_major_loss"))
    coherent = (
        shell_drop <= options.coherence_drop_threshold
        and radial_drop <= options.radial_coherence_drop_threshold
        and angular_drop <= options.angular_coherence_drop_threshold
        and node_drop <= options.node_stability_drop_threshold
    )
    decoherent = (
        shell_drop > options.coherence_drop_threshold
        or radial_drop > options.radial_coherence_drop_threshold
        or angular_drop > options.angular_coherence_drop_threshold
        or node_drop > options.node_stability_drop_threshold
    )
    wider = width_growth >= options.width_growth_threshold
    shifted = center_shift >= options.center_shift_threshold
    checks = {
        "proof_variant": proof.get("variant"),
        "lift_variant": lift.get("variant"),
        "proof_default_count": _count_label(proof, default=True),
        "lift_default_count": _count_label(lift, default=True),
        "proof_strict_count": _count_label(proof, default=False),
        "lift_strict_count": _count_label(lift, default=False),
        "strict_major_loss": strict_loss,
        "shell_phase_coherence_drop": shell_drop,
        "radial_phase_coherence_drop": radial_drop,
        "angular_phase_coherence_drop": angular_drop,
        "node_phase_stability_drop": node_drop,
        "return_radial_spread_relative_growth": width_growth,
        "return_radial_centroid_shift": _float(comparison.get("return_radial_centroid_shift")),
        "phase_profile_mean_abs_drift_cycles": _float(comparison.get("radial_phase_profile_mean_abs_drift_cycles")),
        "spatial_profile_coherent": coherent,
        "spatial_profile_decoherent": decoherent,
    }
    if not rows or not comparison_rows:
        return {
            "label": "spatial_phase_instrumentation_inconclusive",
            "reason": "The instrumentation run did not produce both comparison rows.",
            "checks": checks,
        }
    if coherent and wider:
        return {
            "label": "spatial_phase_coherent_blur_supported",
            "reason": "The 51^3 candidate keeps comparable shell phase coherence while return packets are broader, supporting coherent spatial blur rather than phase decoherence.",
            "checks": checks,
        }
    if decoherent:
        return {
            "label": "spatial_phase_decoherence_supported",
            "reason": "The 51^3 candidate loses radial, angular, shell, or node-stability coherence enough to support spatial phase decoherence as the blur mechanism.",
            "checks": checks,
        }
    if coherent and shifted:
        return {
            "label": "spatial_phase_shell_window_alignment_supported",
            "reason": "The 51^3 candidate keeps spatial coherence but shifts its return center enough to implicate radial gate alignment.",
            "checks": checks,
        }
    if strict_loss >= 1.0:
        return {
            "label": "finite_resolution_spatial_mechanism_not_isolated",
            "reason": "Strict counts shrink at 51^3, but the spatial phase frames do not isolate coherence loss, coherent widening, or shell-window shift.",
            "checks": checks,
        }
    return {
        "label": "spatial_phase_instrumentation_inconclusive",
        "reason": "The reproduced rows do not show a clear spatial-phase mechanism distinction.",
        "checks": checks,
    }


def _variant_specs(base: SimulationConfig, options: SpatialPhaseInstrumentationOptions) -> list[dict[str, Any]]:
    common = {
        "output_root": options.output_root,
        "reference_source_grid_size": options.reference_source_grid_size,
        "physical_duration": options.physical_duration,
        "sample_every": options.sample_every,
        "diagnostic_sample_every": options.diagnostic_sample_every,
        "radial_bins": options.radial_bins,
        "shell_window_radius": options.shell_window_radius,
        "shell_window_width": options.shell_window_width,
        "near_shell_width_dx": options.near_shell_width_dx,
        "sponge_strength_multiplier": options.sponge_strength_multiplier,
        "target_work_per_source_area": options.target_work_per_source_area,
        "fixed_drive_frequency": options.fixed_drive_frequency,
        "arrival_threshold_fraction": options.arrival_threshold_fraction,
        "exit_threshold_fraction": options.exit_threshold_fraction,
        "exit_hold_samples": options.exit_hold_samples,
        "peak_threshold_fraction": options.peak_threshold_fraction,
        "refocus_threshold_fraction": options.refocus_threshold_fraction,
        "min_peak_separation_time": options.min_peak_separation_time,
        "min_refocus_count": options.min_refocus_count,
        "min_width_growth_fraction": options.min_width_growth_fraction,
        "min_decay_rate_magnitude": options.min_decay_rate_magnitude,
    }
    proof_options = ReleasePhaseProofPackOptions(
        **common,
        grid_size=options.proof_grid_size,
        cutoffs=(options.proof_cutoff,),
        prediction_roles=("proof_41_reference",),
        dt_scale=options.dt_scale,
    )
    proof_config = _proof_variant_plan(base, proof_options)[0]
    proof_config.name = f"spatial_phase_41_proof_cutoff_{_safe_float(options.proof_cutoff)}"
    setattr(proof_config, "_prediction_role", "proof_41_reference")

    lift_options = ReleasePhaseResolutionLiftOptions(
        **common,
        grid_size=options.lift_grid_size,
        phase_targets=(options.lift_target_release_phase,),
        prediction_roles=("failed_lift_51_candidate",),
        dt_scale=options.dt_scale,
    )
    lift_config = _lift_variant_plan(base, lift_options)[0]
    lift_config.name = f"spatial_phase_51_lift_candidate_phase_{_safe_float(options.lift_target_release_phase)}"
    setattr(lift_config, "_prediction_role", "failed_lift_51_candidate")

    return [
        {
            "config": proof_config,
            "options": proof_options,
            "annotate": _add_proof_fields,
            "audit_group": "proof_41_reference",
            "source_run_kind": "proof_pack_reproduction",
        },
        {
            "config": lift_config,
            "options": lift_options,
            "annotate": _add_resolution_lift_fields,
            "audit_group": "failed_lift_51_candidate",
            "source_run_kind": "resolution_lift_reproduction",
        },
    ]


def _calibrate_fixed_variant(
    base_config: SimulationConfig,
    config: Prototype3DConfig,
    plan_options: Any,
    lifecycle_options: PacketLifecycle3DOptions,
) -> float:
    source_width = _base_dx(base_config, plan_options.reference_source_grid_size)
    threshold_options = _threshold_like_options(lifecycle_options)
    target_work_per_area = plan_options.target_work_per_source_area or _calibration_work_per_area(
        base_config,
        threshold_options,
        source_width,
    )
    config.drive_amplitude = _calibrated_reference_amplitude(
        base_config,
        threshold_options,
        source_width,
        target_work_per_area,
    )
    target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
    _calibrate_amplitude(config, target_work)
    config.steps = max(config.steps, int(round(plan_options.physical_duration / max(config.dt, EPSILON))))
    return float(target_work_per_area)


def _run_spatial_phase_variant(
    config: Prototype3DConfig,
    root: Path,
    lifecycle_options: PacketLifecycle3DOptions,
    spatial_options: SpatialPhaseInstrumentationOptions,
) -> dict[str, Any]:
    run_dir = root / config.name
    run_dir.mkdir(parents=True, exist_ok=False)
    lattice = Lattice3D(config)
    coords = lattice.coords
    radius = coords["radius"]
    shell_width = _shell_width(config, lifecycle_options)
    shell_outer = lifecycle_options.shell_window_radius + shell_width
    shell_mask = (radius > lifecycle_options.shell_window_radius) & (radius <= shell_outer)
    outer_mask = radius > shell_outer + shell_width
    active_mask = coords["boundary_distance"] >= config.sponge_width
    radial_bins = np.linspace(0.0, np.sqrt(3.0) * config.domain_size / 2.0, lifecycle_options.radial_bins + 1)
    radial_centers = 0.5 * (radial_bins[:-1] + radial_bins[1:])
    shell_geometry = _shell_geometry(coords, shell_mask, spatial_options)
    radial_phase_bins = np.linspace(lifecycle_options.shell_window_radius, shell_outer, spatial_options.radial_phase_bins + 1)

    timeseries: list[dict[str, Any]] = []
    cumulative_positive_work = 0.0
    primary_positive_work = 0.0
    second_pulse_positive_work = 0.0
    cumulative_inward_flux = 0.0
    cumulative_outward_flux = 0.0
    for step in range(config.steps):
        time = step * config.dt
        force = lattice.external_force(time)
        velocity_before = lattice.v.copy()
        lattice.step(time, config.dt)
        velocity_mid = 0.5 * (velocity_before + lattice.v)
        power = float(np.sum(force * velocity_mid) * config.cell_volume)
        positive_work = max(0.0, power) * config.dt
        cumulative_positive_work += positive_work
        if _primary_drive_active(config, time):
            primary_positive_work += positive_work
        elif _second_pulse_active(config, time):
            second_pulse_positive_work += positive_work

        if step % max(1, lifecycle_options.diagnostic_sample_every) != 0 and step != config.steps - 1:
            continue

        energy = lattice.energy_density()
        flux_density = _radial_flux_density(lattice)
        shell_flux = float(np.sum(flux_density[shell_mask]))
        dt_sample = config.dt * max(1, lifecycle_options.diagnostic_sample_every)
        cumulative_inward_flux += max(0.0, -shell_flux) * dt_sample
        cumulative_outward_flux += max(0.0, shell_flux) * dt_sample
        active_energy = np.where(active_mask, energy, 0.0)
        radial_profile = _radial_profile_sum(active_energy, radius, radial_bins)
        packet_peak_radius = float(radial_centers[int(np.argmax(radial_profile))]) if radial_profile.size else 0.0
        packet_width = _profile_width(radial_centers, radial_profile)
        packet_centroid = _weighted_mean(radius[active_mask], energy[active_mask])
        packet_spread = _weighted_std(radius[active_mask], energy[active_mask], packet_centroid)
        shell_energy = float(np.sum(energy[shell_mask]))
        outer_energy = float(np.sum(energy[outer_mask & active_mask]))
        total_energy = float(np.sum(energy))
        timeseries.append(
            {
                "variant": config.name,
                "time": time,
                "packet_peak_radius": packet_peak_radius,
                "packet_centroid_radius": packet_centroid,
                "packet_radial_width": packet_width,
                "packet_radial_spread": packet_spread,
                "shell_window_energy": shell_energy,
                "outer_active_energy": outer_energy,
                "outer_to_shell_energy": outer_energy / (shell_energy + EPSILON),
                "shell_fraction_of_total": shell_energy / (total_energy + EPSILON),
                "shell_radial_flux": shell_flux,
                "shell_inward_flux": max(0.0, -shell_flux),
                "shell_outward_flux": max(0.0, shell_flux),
                "cumulative_inward_flux": cumulative_inward_flux,
                "cumulative_outward_flux": cumulative_outward_flux,
                "cumulative_positive_work": cumulative_positive_work,
                "primary_positive_work": primary_positive_work,
                "second_pulse_positive_work": second_pulse_positive_work,
            }
        )

    summary, events = _summarize_lifecycle(
        config,
        timeseries,
        primary_positive_work,
        shell_width,
        lifecycle_options,
        total_positive_work=cumulative_positive_work,
        second_pulse_positive_work=second_pulse_positive_work,
    )
    threshold_counts = _threshold_counts(config, timeseries, spatial_options)
    frame_peaks = _frame_peaks(config, timeseries, spatial_options)
    accepted_frames = _capture_peak_frames(config, frame_peaks, shell_geometry, radial_phase_bins, spatial_options)
    frame_index_rows = [_frame_index_row(config, frame) for frame in accepted_frames]
    displacement_rows = _node_frame_rows(config, accepted_frames, shell_geometry, field="u")
    velocity_rows = _node_frame_rows(config, accepted_frames, shell_geometry, field="v")
    radial_frame_rows = _radial_frame_rows(config, accepted_frames, radial_phase_bins)
    radial_coherence_rows = _radial_coherence_rows(config, radial_frame_rows, spatial_options)
    angular_rows = _angular_rows(config, accepted_frames, spatial_options)
    stability_rows = _stability_rows(config, accepted_frames, shell_geometry)
    phase_drift_rows = _phase_drift_rows(config, accepted_frames)
    spatial_summary = _spatial_summary(
        accepted_frames,
        radial_frame_rows,
        radial_coherence_rows,
        angular_rows,
        stability_rows,
        phase_drift_rows,
    )

    _write_csv(run_dir / "packet_lifecycle_timeseries.csv", timeseries, _timeseries_fields())
    _write_csv(run_dir / "packet_lifecycle_events.csv", events, _event_fields())
    _write_csv(run_dir / "spatial_phase_frame_index.csv", frame_index_rows, _frame_index_fields())
    return {
        "summary": summary,
        "timeseries": timeseries,
        "events": events,
        "threshold_counts": threshold_counts,
        "frame_index_rows": frame_index_rows,
        "displacement_rows": displacement_rows,
        "velocity_rows": velocity_rows,
        "radial_frame_rows": radial_frame_rows,
        "radial_coherence_rows": radial_coherence_rows,
        "angular_rows": angular_rows,
        "stability_rows": stability_rows,
        "phase_drift_rows": phase_drift_rows,
        "spatial_summary": spatial_summary,
    }


def _shell_geometry(coords: dict[str, np.ndarray], shell_mask: np.ndarray, options: SpatialPhaseInstrumentationOptions) -> dict[str, np.ndarray]:
    shell_indices = np.flatnonzero(shell_mask.ravel())
    x = coords["x"].ravel()[shell_indices].astype(float)
    y = coords["y"].ravel()[shell_indices].astype(float)
    z = coords["z"].ravel()[shell_indices].astype(float)
    radius = coords["radius"].ravel()[shell_indices].astype(float)
    theta = np.mod(np.arctan2(y, x), 2.0 * math.pi)
    polar = np.arccos(np.clip(z / np.maximum(radius, EPSILON), -1.0, 1.0))
    theta_bin = np.clip((theta / (2.0 * math.pi) * options.angular_theta_bins).astype(int), 0, options.angular_theta_bins - 1)
    polar_bin = np.clip((polar / math.pi * options.angular_polar_bins).astype(int), 0, options.angular_polar_bins - 1)
    octant = (
        (x >= 0.0).astype(int) * 4
        + (y >= 0.0).astype(int) * 2
        + (z >= 0.0).astype(int)
    )
    return {
        "flat_index": shell_indices,
        "x": x,
        "y": y,
        "z": z,
        "radius": radius,
        "theta": theta,
        "polar": polar,
        "theta_bin": theta_bin,
        "polar_bin": polar_bin,
        "octant": octant.astype(int),
    }


def _capture_sample(
    config: Prototype3DConfig,
    lattice: Lattice3D,
    energy: np.ndarray,
    shell_geometry: dict[str, np.ndarray],
    radial_bins: np.ndarray,
    options: SpatialPhaseInstrumentationOptions,
    time: float,
    shell_energy: float,
) -> dict[str, Any]:
    indices = shell_geometry["flat_index"]
    u = lattice.u.ravel()[indices].astype(float).copy()
    v = lattice.v.ravel()[indices].astype(float).copy()
    e = energy.ravel()[indices].astype(float).copy()
    phases = _phase_vector(lattice.u, lattice.v, max(float(config.drive_frequency), EPSILON)).ravel()[indices]
    shell_phase = _weighted_phase(phases, e)
    radial_centroid = _weighted_mean(shell_geometry["radius"], e)
    radial_spread = _weighted_std(shell_geometry["radius"], e, radial_centroid)
    radial_profile = _binned_sum(shell_geometry["radius"], e, radial_bins)
    centers = 0.5 * (radial_bins[:-1] + radial_bins[1:])
    return {
        "variant": config.name,
        "time": float(time),
        "shell_energy": float(shell_energy),
        "geometry": shell_geometry,
        "shell_radius": shell_geometry["radius"],
        "u": u,
        "v": v,
        "energy": e,
        "phase_vector": phases.copy(),
        "phase_angle": np.angle(phases).astype(float),
        "shell_phase_mean_radians": shell_phase["mean_radians"],
        "shell_phase_mean_cycles": shell_phase["mean_cycles"],
        "shell_phase_coherence": shell_phase["coherence"],
        "return_radial_centroid": radial_centroid,
        "return_radial_spread": radial_spread,
        "return_radial_width": _profile_width(centers, radial_profile),
        "return_peak_radius": float(centers[int(np.argmax(radial_profile))]) if radial_profile.size else 0.0,
        "rms_displacement": float(np.sqrt(np.mean(u**2))) if u.size else 0.0,
        "rms_velocity": float(np.sqrt(np.mean(v**2))) if v.size else 0.0,
        "positive_displacement_fraction": float(np.mean(u >= 0.0)) if u.size else 0.0,
        "radial_bins": radial_bins,
        "angular_theta_bins": options.angular_theta_bins,
        "angular_polar_bins": options.angular_polar_bins,
    }


def _frame_peaks(
    config: Prototype3DConfig,
    timeseries: list[dict[str, Any]],
    options: SpatialPhaseInstrumentationOptions,
) -> list[dict[str, Any]]:
    if not timeseries:
        return []
    times = np.asarray([row["time"] for row in timeseries], dtype=float)
    shell = np.asarray([row["shell_window_energy"] for row in timeseries], dtype=float)
    post_indices = np.flatnonzero(times > config.drive_cutoff_time)
    peaks = _major_peaks_for_threshold(
        times,
        shell,
        post_indices,
        options.frame_peak_threshold_fraction,
        options.min_peak_separation_time,
    )
    peaks = peaks[: max(1, int(options.max_return_frames))]
    for rank, peak in enumerate(peaks, start=1):
        peak["peak_rank"] = rank
        peak["frame_id"] = f"{config.name}_return_{rank:02d}"
        peak["frame_threshold_fraction"] = options.frame_peak_threshold_fraction
    return peaks


def _capture_peak_frames(
    config: Prototype3DConfig,
    peaks: list[dict[str, Any]],
    shell_geometry: dict[str, np.ndarray],
    radial_phase_bins: np.ndarray,
    options: SpatialPhaseInstrumentationOptions,
) -> list[dict[str, Any]]:
    if not peaks:
        return []
    lattice = Lattice3D(config)
    target_by_step = {int(round(float(peak["time"]) / max(config.dt, EPSILON))): peak for peak in peaks}
    frames: list[dict[str, Any]] = []
    for step in range(config.steps):
        time = step * config.dt
        lattice.step(time, config.dt)
        peak = target_by_step.get(step)
        if peak is None:
            continue
        energy = lattice.energy_density()
        frame = _capture_sample(
            config,
            lattice,
            energy,
            shell_geometry,
            radial_phase_bins,
            options,
            time,
            float(peak["energy"]),
        )
        frame["frame_id"] = peak["frame_id"]
        frame["peak_rank"] = peak["peak_rank"]
        frame["frame_threshold_fraction"] = peak["frame_threshold_fraction"]
        frames.append(frame)
        if len(frames) >= len(peaks):
            break
    return frames


def _threshold_counts(config: Prototype3DConfig, timeseries: list[dict[str, Any]], options: SpatialPhaseInstrumentationOptions) -> list[dict[str, Any]]:
    if not timeseries:
        return []
    times = np.asarray([row["time"] for row in timeseries], dtype=float)
    shell = np.asarray([row["shell_window_energy"] for row in timeseries], dtype=float)
    post_indices = np.flatnonzero(times > config.drive_cutoff_time)
    rows = []
    for threshold in (0.20, 0.25, 0.30, 0.35, 0.40):
        peaks = _major_peaks_for_threshold(times, shell, post_indices, threshold, options.min_peak_separation_time)
        rows.append(
            {
                "variant": config.name,
                "grid_size": config.grid_size,
                "peak_threshold_fraction": threshold,
                "major_shell_peak_count": len(peaks),
                "refocus_peak_count": _refocus_count(peaks, options.refocus_threshold_fraction),
            }
        )
    return rows


def _major_peaks_for_threshold(
    times: np.ndarray,
    values: np.ndarray,
    post_indices: np.ndarray,
    threshold_fraction: float,
    min_peak_separation_time: float,
) -> list[dict[str, Any]]:
    if values.size < 3 or post_indices.size == 0:
        return []
    peak_value = float(np.max(values[post_indices]))
    threshold = max(float(threshold_fraction) * peak_value, EPSILON)
    post_set = set(int(idx) for idx in post_indices)
    candidates = []
    for idx in range(1, values.size - 1):
        if idx not in post_set:
            continue
        if values[idx] >= threshold and values[idx] >= values[idx - 1] and values[idx] >= values[idx + 1]:
            candidates.append({"index": idx, "time": float(times[idx]), "energy": float(values[idx])})
    accepted: list[dict[str, Any]] = []
    for peak in sorted(candidates, key=lambda item: item["energy"], reverse=True):
        if all(abs(peak["time"] - other["time"]) >= min_peak_separation_time for other in accepted):
            accepted.append(peak)
    return sorted(accepted, key=lambda item: item["time"])


def _refocus_count(peaks: list[dict[str, Any]], refocus_threshold_fraction: float) -> int:
    if len(peaks) <= 1:
        return 0
    first = float(peaks[0]["energy"])
    return sum(1 for peak in peaks[1:] if float(peak["energy"]) >= refocus_threshold_fraction * max(first, EPSILON))


def _frame_index_row(config: Prototype3DConfig, frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant": config.name,
        "grid_size": config.grid_size,
        "frame_id": frame.get("frame_id"),
        "peak_rank": frame.get("peak_rank"),
        "time": frame.get("time"),
        "shell_energy": frame.get("shell_energy"),
        "shell_phase_mean_cycles": frame.get("shell_phase_mean_cycles"),
        "shell_phase_coherence": frame.get("shell_phase_coherence"),
        "return_peak_radius": frame.get("return_peak_radius"),
        "return_radial_centroid": frame.get("return_radial_centroid"),
        "return_radial_spread": frame.get("return_radial_spread"),
        "return_radial_width": frame.get("return_radial_width"),
        "rms_displacement": frame.get("rms_displacement"),
        "rms_velocity": frame.get("rms_velocity"),
        "positive_displacement_fraction": frame.get("positive_displacement_fraction"),
    }


def _node_frame_rows(
    config: Prototype3DConfig,
    frames: list[dict[str, Any]],
    shell_geometry: dict[str, np.ndarray],
    *,
    field: str,
) -> list[dict[str, Any]]:
    rows = []
    value_key = field
    for frame in frames:
        values = frame[value_key]
        for local_index, flat_index in enumerate(shell_geometry["flat_index"]):
            rows.append(
                {
                    "variant": config.name,
                    "grid_size": config.grid_size,
                    "frame_id": frame.get("frame_id"),
                    "peak_rank": frame.get("peak_rank"),
                    "time": frame.get("time"),
                    "node_index": int(flat_index),
                    "x": float(shell_geometry["x"][local_index]),
                    "y": float(shell_geometry["y"][local_index]),
                    "z": float(shell_geometry["z"][local_index]),
                    "radius": float(shell_geometry["radius"][local_index]),
                    "theta": float(shell_geometry["theta"][local_index]),
                    "polar": float(shell_geometry["polar"][local_index]),
                    field: float(values[local_index]),
                }
            )
    return rows


def _radial_frame_rows(config: Prototype3DConfig, frames: list[dict[str, Any]], radial_bins: np.ndarray) -> list[dict[str, Any]]:
    rows = []
    for frame in frames:
        shell_radius = frame["shell_radius"]
        bin_index = np.clip(np.digitize(shell_radius, radial_bins) - 1, 0, len(radial_bins) - 2)
        for idx in range(len(radial_bins) - 1):
            mask = bin_index == idx
            weights = frame["energy"][mask]
            phase = _weighted_phase(frame["phase_vector"][mask], weights)
            rows.append(
                {
                    "variant": config.name,
                    "grid_size": config.grid_size,
                    "frame_id": frame.get("frame_id"),
                    "peak_rank": frame.get("peak_rank"),
                    "time": frame.get("time"),
                    "radial_bin": idx,
                    "radial_bin_inner": float(radial_bins[idx]),
                    "radial_bin_outer": float(radial_bins[idx + 1]),
                    "radial_bin_center": float(0.5 * (radial_bins[idx] + radial_bins[idx + 1])),
                    "node_count": int(np.sum(mask)),
                    "shell_energy": float(np.sum(weights)),
                    "phase_mean_cycles": phase["mean_cycles"],
                    "phase_coherence": phase["coherence"],
                    "mean_displacement": float(np.mean(frame["u"][mask])) if np.any(mask) else 0.0,
                    "mean_velocity": float(np.mean(frame["v"][mask])) if np.any(mask) else 0.0,
                    "rms_displacement": float(np.sqrt(np.mean(frame["u"][mask] ** 2))) if np.any(mask) else 0.0,
                    "rms_velocity": float(np.sqrt(np.mean(frame["v"][mask] ** 2))) if np.any(mask) else 0.0,
                }
            )
    return rows


def _radial_coherence_rows(
    config: Prototype3DConfig,
    radial_rows: list[dict[str, Any]],
    options: SpatialPhaseInstrumentationOptions,
) -> list[dict[str, Any]]:
    rows = []
    for radial_bin in range(options.radial_phase_bins):
        subset = [row for row in radial_rows if row["variant"] == config.name and int(row["radial_bin"]) == radial_bin]
        phases = [_float(row.get("phase_mean_cycles")) for row in subset]
        rows.append(
            {
                "variant": config.name,
                "grid_size": config.grid_size,
                "radial_bin": radial_bin,
                "radial_bin_center": _mean([row.get("radial_bin_center") for row in subset]),
                "frame_count": len(subset),
                "phase_coherence_mean": _mean([row.get("phase_coherence") for row in subset]),
                "phase_coherence_min": _min([row.get("phase_coherence") for row in subset]),
                "phase_coherence_max": _max([row.get("phase_coherence") for row in subset]),
                "phase_drift_std_cycles": _circular_std(phases),
                "shell_energy_mean": _mean([row.get("shell_energy") for row in subset]),
                "rms_displacement_mean": _mean([row.get("rms_displacement") for row in subset]),
            }
        )
    return rows


def _angular_rows(
    config: Prototype3DConfig,
    frames: list[dict[str, Any]],
    options: SpatialPhaseInstrumentationOptions,
) -> list[dict[str, Any]]:
    rows = []
    for frame in frames:
        geometry = frame.get("geometry")
        if geometry is None:
            continue
        theta_bin = geometry["theta_bin"]
        polar_bin = geometry["polar_bin"]
        for pbin in range(options.angular_polar_bins):
            for tbin in range(options.angular_theta_bins):
                mask = (theta_bin == tbin) & (polar_bin == pbin)
                weights = frame["energy"][mask]
                phase = _weighted_phase(frame["phase_vector"][mask], weights)
                rows.append(
                    {
                        "variant": config.name,
                        "grid_size": config.grid_size,
                        "frame_id": frame.get("frame_id"),
                        "peak_rank": frame.get("peak_rank"),
                        "time": frame.get("time"),
                        "polar_bin": pbin,
                        "theta_bin": tbin,
                        "node_count": int(np.sum(mask)),
                        "shell_energy": float(np.sum(weights)),
                        "phase_mean_cycles": phase["mean_cycles"],
                        "phase_coherence": phase["coherence"],
                        "rms_displacement": float(np.sqrt(np.mean(frame["u"][mask] ** 2))) if np.any(mask) else 0.0,
                        "rms_velocity": float(np.sqrt(np.mean(frame["v"][mask] ** 2))) if np.any(mask) else 0.0,
                    }
                )
        for octant in range(8):
            mask = geometry["octant"] == octant
            weights = frame["energy"][mask]
            phase = _weighted_phase(frame["phase_vector"][mask], weights)
            rows.append(
                {
                    "variant": config.name,
                    "grid_size": config.grid_size,
                    "frame_id": frame.get("frame_id"),
                    "peak_rank": frame.get("peak_rank"),
                    "time": frame.get("time"),
                    "polar_bin": "octant",
                    "theta_bin": octant,
                    "node_count": int(np.sum(mask)),
                    "shell_energy": float(np.sum(weights)),
                    "phase_mean_cycles": phase["mean_cycles"],
                    "phase_coherence": phase["coherence"],
                    "rms_displacement": float(np.sqrt(np.mean(frame["u"][mask] ** 2))) if np.any(mask) else 0.0,
                    "rms_velocity": float(np.sqrt(np.mean(frame["v"][mask] ** 2))) if np.any(mask) else 0.0,
                }
            )
    return rows


def _stability_rows(
    config: Prototype3DConfig,
    frames: list[dict[str, Any]],
    shell_geometry: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    if not frames:
        return []
    u_stack = np.vstack([frame["u"] for frame in frames])
    phase_stack = np.vstack([frame["phase_vector"] for frame in frames])
    rms = np.sqrt(np.mean(u_stack**2, axis=0))
    lower = float(np.quantile(rms, 0.25)) if rms.size else 0.0
    upper = float(np.quantile(rms, 0.75)) if rms.size else 0.0
    rows = []
    for local_index, flat_index in enumerate(shell_geometry["flat_index"]):
        signs = np.sign(u_stack[:, local_index])
        phase_coherence = float(abs(np.mean(phase_stack[:, local_index]))) if phase_stack.size else 0.0
        value = float(rms[local_index])
        if value >= upper:
            label = "antinode"
        elif value <= lower:
            label = "node"
        else:
            label = "transition"
        rows.append(
            {
                "variant": config.name,
                "grid_size": config.grid_size,
                "node_index": int(flat_index),
                "x": float(shell_geometry["x"][local_index]),
                "y": float(shell_geometry["y"][local_index]),
                "z": float(shell_geometry["z"][local_index]),
                "radius": float(shell_geometry["radius"][local_index]),
                "theta": float(shell_geometry["theta"][local_index]),
                "polar": float(shell_geometry["polar"][local_index]),
                "node_antinode_label": label,
                "rms_displacement_over_returns": value,
                "mean_abs_displacement": float(np.mean(np.abs(u_stack[:, local_index]))),
                "sign_consistency": float(abs(np.mean(signs))) if signs.size else 0.0,
                "phase_coherence_over_returns": phase_coherence,
                "frame_count": len(frames),
            }
        )
    return rows


def _phase_drift_rows(config: Prototype3DConfig, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for left, right in zip(frames, frames[1:]):
        rows.append(
            {
                "variant": config.name,
                "grid_size": config.grid_size,
                "from_peak_rank": left.get("peak_rank"),
                "to_peak_rank": right.get("peak_rank"),
                "from_time": left.get("time"),
                "to_time": right.get("time"),
                "time_delta": float(right["time"] - left["time"]),
                "from_phase_cycles": left.get("shell_phase_mean_cycles"),
                "to_phase_cycles": right.get("shell_phase_mean_cycles"),
                "phase_drift_cycles": _cycle_delta(left.get("shell_phase_mean_cycles"), right.get("shell_phase_mean_cycles")),
                "from_shell_phase_coherence": left.get("shell_phase_coherence"),
                "to_shell_phase_coherence": right.get("shell_phase_coherence"),
                "energy_ratio": float(right["shell_energy"] / (left["shell_energy"] + EPSILON)),
                "radial_centroid_delta": float(right["return_radial_centroid"] - left["return_radial_centroid"]),
                "radial_spread_delta": float(right["return_radial_spread"] - left["return_radial_spread"]),
            }
        )
    return rows


def _spatial_summary(
    frames: list[dict[str, Any]],
    radial_frame_rows: list[dict[str, Any]],
    radial_coherence_rows: list[dict[str, Any]],
    angular_rows: list[dict[str, Any]],
    stability_rows: list[dict[str, Any]],
    drift_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    frame_count = len(frames)
    shell_phase_values = [frame.get("shell_phase_coherence") for frame in frames]
    radial_frames = [row.get("phase_coherence") for row in radial_frame_rows if _float(row.get("shell_energy")) > 0.0]
    angular_frames = [row.get("phase_coherence") for row in angular_rows if _float(row.get("shell_energy")) > 0.0]
    node_rows = [row for row in stability_rows if row.get("node_antinode_label") == "node"]
    antinode_rows = [row for row in stability_rows if row.get("node_antinode_label") == "antinode"]
    return {
        "instrumented_return_frame_count": frame_count,
        "instrumented_frame_threshold_fraction": frames[0].get("frame_threshold_fraction") if frames else None,
        "shell_phase_coherence_mean": _mean(shell_phase_values),
        "shell_phase_coherence_min": _min(shell_phase_values),
        "shell_phase_coherence_max": _max(shell_phase_values),
        "radial_phase_coherence_mean": _mean(radial_frames),
        "angular_phase_coherence_mean": _mean(angular_frames),
        "node_phase_stability_mean": _mean([row.get("phase_coherence_over_returns") for row in stability_rows]),
        "node_sign_consistency_mean": _mean([row.get("sign_consistency") for row in stability_rows]),
        "node_region_phase_stability_mean": _mean([row.get("phase_coherence_over_returns") for row in node_rows]),
        "antinode_phase_stability_mean": _mean([row.get("phase_coherence_over_returns") for row in antinode_rows]),
        "return_phase_drift_std_cycles": _std([row.get("phase_drift_cycles") for row in drift_rows]),
        "return_phase_drift_abs_mean_cycles": _mean([abs(_float(row.get("phase_drift_cycles"))) for row in drift_rows]),
        "return_radial_centroid_mean": _mean([frame.get("return_radial_centroid") for frame in frames]),
        "return_radial_spread_mean": _mean([frame.get("return_radial_spread") for frame in frames]),
        "return_radial_width_mean": _mean([frame.get("return_radial_width") for frame in frames]),
        "return_peak_radius_mean": _mean([frame.get("return_peak_radius") for frame in frames]),
        "return_peak_energy_decay_per_return": _linear_slope(
            [float(frame.get("peak_rank") or 0.0) for frame in frames],
            [math.log(max(float(frame.get("shell_energy") or 0.0), EPSILON)) for frame in frames],
        ),
    }


def _merge_robust_counts(rows: list[dict[str, Any]], robust_rows: list[dict[str, Any]]) -> None:
    robust_by_variant = {str(row.get("variant")): row for row in robust_rows}
    for row in rows:
        robust = robust_by_variant.get(str(row.get("variant")), {})
        row["loose_major_peaks_at_0p25"] = robust.get("major_peaks_at_0p25")
        row["loose_refocus_peaks_at_0p25"] = robust.get("refocus_peaks_at_0p25")
        row["default_major_peaks_at_0p30"] = robust.get("major_peaks_at_0p30")
        row["default_refocus_peaks_at_0p30"] = robust.get("refocus_peaks_at_0p30")
        row["strict_major_peaks_at_0p35"] = robust.get("major_peaks_at_0p35")
        row["strict_refocus_peaks_at_0p35"] = robust.get("refocus_peaks_at_0p35")
        row["strict_major_peaks_at_0p40"] = robust.get("major_peaks_at_0p40")
        row["strict_refocus_peaks_at_0p40"] = robust.get("refocus_peaks_at_0p40")
        row["conservative_major_peaks"] = min(_int(robust.get("major_peaks_at_0p35")), _int(robust.get("major_peaks_at_0p40")))
        row["conservative_refocus_peaks"] = min(_int(robust.get("refocus_peaks_at_0p35")), _int(robust.get("refocus_peaks_at_0p40")))
        row["threshold_free_tail_area_after_t50"] = robust.get("threshold_free_tail_energy_area_after_t50")
        row["threshold_free_shell_area_after_cutoff"] = robust.get("threshold_free_shell_energy_area_after_cutoff")
        row["shell_energy_autocorrelation"] = robust.get("shell_energy_autocorrelation")
        row["dominant_spectral_concentration"] = robust.get("dominant_spectral_concentration")
        row["return_timing_regularity"] = robust.get("return_timing_regularity")


def _comparison_rows(
    rows: list[dict[str, Any]],
    radial_coherence_rows: list[dict[str, Any]],
    angular_rows: list[dict[str, Any]],
    options: SpatialPhaseInstrumentationOptions,
) -> list[dict[str, Any]]:
    proof = next((row for row in rows if row.get("audit_group") == "proof_41_reference"), None)
    lift = next((row for row in rows if row.get("audit_group") == "failed_lift_51_candidate"), None)
    if proof is None or lift is None:
        return []
    radial_phase_drift = _radial_phase_profile_drift(proof["variant"], lift["variant"], radial_coherence_rows)
    angular_delta = _angular_coherence_delta(proof["variant"], lift["variant"], angular_rows)
    proof_spread = _float(proof.get("return_radial_spread_mean"))
    lift_spread = _float(lift.get("return_radial_spread_mean"))
    return [
        {
            "comparison": "41_proof_vs_51_failed_lift",
            "proof_variant": proof.get("variant"),
            "lift_variant": lift.get("variant"),
            "proof_grid_size": proof.get("grid_size"),
            "lift_grid_size": lift.get("grid_size"),
            "proof_cutoff": proof.get("drive_cutoff_time"),
            "lift_cutoff": lift.get("drive_cutoff_time"),
            "proof_phase": proof.get("cutoff_phase_cycles"),
            "lift_phase": lift.get("cutoff_phase_cycles"),
            "proof_default_count": _count_label(proof, default=True),
            "lift_default_count": _count_label(lift, default=True),
            "proof_strict_count": _count_label(proof, default=False),
            "lift_strict_count": _count_label(lift, default=False),
            "strict_major_loss": _int(proof.get("conservative_major_peaks")) - _int(lift.get("conservative_major_peaks")),
            "strict_refocus_loss": _int(proof.get("conservative_refocus_peaks")) - _int(lift.get("conservative_refocus_peaks")),
            "proof_shell_phase_coherence_mean": proof.get("shell_phase_coherence_mean"),
            "lift_shell_phase_coherence_mean": lift.get("shell_phase_coherence_mean"),
            "shell_phase_coherence_drop": _float(proof.get("shell_phase_coherence_mean")) - _float(lift.get("shell_phase_coherence_mean")),
            "proof_radial_phase_coherence_mean": proof.get("radial_phase_coherence_mean"),
            "lift_radial_phase_coherence_mean": lift.get("radial_phase_coherence_mean"),
            "radial_phase_coherence_drop": _float(proof.get("radial_phase_coherence_mean")) - _float(lift.get("radial_phase_coherence_mean")),
            "proof_angular_phase_coherence_mean": proof.get("angular_phase_coherence_mean"),
            "lift_angular_phase_coherence_mean": lift.get("angular_phase_coherence_mean"),
            "angular_phase_coherence_drop": _float(proof.get("angular_phase_coherence_mean")) - _float(lift.get("angular_phase_coherence_mean")),
            "angular_sector_coherence_delta": angular_delta,
            "proof_node_phase_stability_mean": proof.get("node_phase_stability_mean"),
            "lift_node_phase_stability_mean": lift.get("node_phase_stability_mean"),
            "node_phase_stability_drop": _float(proof.get("node_phase_stability_mean")) - _float(lift.get("node_phase_stability_mean")),
            "proof_return_radial_centroid_mean": proof.get("return_radial_centroid_mean"),
            "lift_return_radial_centroid_mean": lift.get("return_radial_centroid_mean"),
            "return_radial_centroid_shift": _float(lift.get("return_radial_centroid_mean")) - _float(proof.get("return_radial_centroid_mean")),
            "proof_return_radial_spread_mean": proof.get("return_radial_spread_mean"),
            "lift_return_radial_spread_mean": lift.get("return_radial_spread_mean"),
            "return_radial_spread_relative_growth": (lift_spread - proof_spread) / max(abs(proof_spread), EPSILON),
            "proof_return_radial_width_mean": proof.get("return_radial_width_mean"),
            "lift_return_radial_width_mean": lift.get("return_radial_width_mean"),
            "return_radial_width_delta": _float(lift.get("return_radial_width_mean")) - _float(proof.get("return_radial_width_mean")),
            "radial_phase_profile_mean_abs_drift_cycles": radial_phase_drift,
            "frame_peak_threshold_fraction": options.frame_peak_threshold_fraction,
        }
    ]


def _radial_phase_profile_drift(proof_variant: str, lift_variant: str, rows: list[dict[str, Any]]) -> float:
    proof = {int(row["radial_bin"]): _float(row.get("phase_drift_std_cycles")) for row in rows if row.get("variant") == proof_variant}
    lift = {int(row["radial_bin"]): _float(row.get("phase_drift_std_cycles")) for row in rows if row.get("variant") == lift_variant}
    bins = sorted(set(proof) & set(lift))
    if not bins:
        return 0.0
    return _mean([abs(proof[idx] - lift[idx]) for idx in bins])


def _angular_coherence_delta(proof_variant: str, lift_variant: str, rows: list[dict[str, Any]]) -> float:
    proof = _mean([row.get("phase_coherence") for row in rows if row.get("variant") == proof_variant and row.get("polar_bin") != "octant"])
    lift = _mean([row.get("phase_coherence") for row in rows if row.get("variant") == lift_variant and row.get("polar_bin") != "octant"])
    return proof - lift


def _weighted_phase(phase_vector: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    if phase_vector.size == 0:
        return {"mean_radians": 0.0, "mean_cycles": 0.0, "coherence": 0.0}
    total = float(np.sum(weights))
    if total <= EPSILON:
        weights = np.ones_like(np.real(phase_vector), dtype=float)
        total = float(np.sum(weights))
    mean = np.sum(weights * phase_vector) / max(total, EPSILON)
    angle = float(np.angle(mean))
    return {
        "mean_radians": angle,
        "mean_cycles": (angle / (2.0 * math.pi)) % 1.0,
        "coherence": float(abs(mean)),
    }


def _binned_sum(values: np.ndarray, weights: np.ndarray, bins: np.ndarray) -> np.ndarray:
    indices = np.clip(np.digitize(values, bins) - 1, 0, len(bins) - 2)
    return np.bincount(indices, weights=weights, minlength=len(bins) - 1).astype(float)


def _cycle_delta(left: Any, right: Any) -> float:
    delta = (_float(right) - _float(left) + 0.5) % 1.0 - 0.5
    return float(delta)


def _circular_std(cycles: list[float]) -> float:
    values = [float(value) for value in cycles if math.isfinite(float(value))]
    if not values:
        return 0.0
    vector = np.exp(2.0j * math.pi * np.asarray(values, dtype=float))
    strength = abs(np.mean(vector))
    return float(math.sqrt(max(0.0, -2.0 * math.log(max(strength, EPSILON)))) / (2.0 * math.pi))


def _linear_slope(x_values: list[float], y_values: list[float]) -> float:
    if len(x_values) < 2 or len(y_values) < 2:
        return 0.0
    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    if float(np.ptp(x)) <= EPSILON:
        return 0.0
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)


def _mean(values: list[Any]) -> float:
    parsed = [_float(value) for value in values if value is not None and math.isfinite(_float(value))]
    return float(np.mean(parsed)) if parsed else 0.0


def _min(values: list[Any]) -> float:
    parsed = [_float(value) for value in values if value is not None and math.isfinite(_float(value))]
    return float(np.min(parsed)) if parsed else 0.0


def _max(values: list[Any]) -> float:
    parsed = [_float(value) for value in values if value is not None and math.isfinite(_float(value))]
    return float(np.max(parsed)) if parsed else 0.0


def _std(values: list[Any]) -> float:
    parsed = [_float(value) for value in values if value is not None and math.isfinite(_float(value))]
    return float(np.std(parsed)) if parsed else 0.0


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


def _count_label(row: dict[str, Any], *, default: bool) -> str:
    if default:
        return f"{_int(row.get('default_major_peaks_at_0p30'))}/{_int(row.get('default_refocus_peaks_at_0p30'))}"
    return f"{_int(row.get('conservative_major_peaks'))}/{_int(row.get('conservative_refocus_peaks'))}"


def _safe_float(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".").replace(".", "p")


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: SpatialPhaseInstrumentationOptions,
) -> None:
    comparison = comparison_rows[0] if comparison_rows else {}
    lines = [
        f"# 3D Spatial Phase Instrumentation: {control_id}",
        "",
        "## Purpose",
        "",
        "Instrumentation-only reproduction of one `41^3` quarter-dt proof row and one `51^3` failed-lift candidate. The physics setup is frozen: neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area, radius-5 shell window, no active second pulses, and no resonator layer.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Reproduction Rows",
        "",
        "| Group | Grid | Cutoff | Phase | Default | Strict | Frames | Shell Coh | Radial Coh | Angular Coh | Node Stability | Return Center | Return Spread |",
        "| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('audit_group')} | "
            f"{row.get('grid_size')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{_count_label(row, default=True)} | "
            f"{_count_label(row, default=False)} | "
            f"{row.get('instrumented_return_frame_count')} | "
            f"{_format(row.get('shell_phase_coherence_mean'))} | "
            f"{_format(row.get('radial_phase_coherence_mean'))} | "
            f"{_format(row.get('angular_phase_coherence_mean'))} | "
            f"{_format(row.get('node_phase_stability_mean'))} | "
            f"{_format(row.get('return_radial_centroid_mean'))} | "
            f"{_format(row.get('return_radial_spread_mean'))} |"
        )
    lines.extend(
        [
            "",
            "## 41 vs 51 Spatial Phase Comparison",
            "",
            "| Strict Loss | Shell Coh Drop | Radial Coh Drop | Angular Coh Drop | Node Stability Drop | Center Shift | Spread Growth | Radial Phase Drift |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| "
            f"{_format(comparison.get('strict_major_loss'))} | "
            f"{_format(comparison.get('shell_phase_coherence_drop'))} | "
            f"{_format(comparison.get('radial_phase_coherence_drop'))} | "
            f"{_format(comparison.get('angular_phase_coherence_drop'))} | "
            f"{_format(comparison.get('node_phase_stability_drop'))} | "
            f"{_format(comparison.get('return_radial_centroid_shift'))} | "
            f"{_format(comparison.get('return_radial_spread_relative_growth'))} | "
            f"{_format(comparison.get('radial_phase_profile_mean_abs_drift_cycles'))} |",
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Files",
            "",
            "- `spatial_phase_instrumentation_report.md`",
            "- `spatial_phase_instrumentation_summary.csv`",
            "- `spatial_phase_threshold_robust_score.csv`",
            "- `spatial_phase_event_threshold_counts.csv`",
            "- `spatial_phase_frame_index.csv`",
            "- `shell_displacement_frames.csv`",
            "- `shell_velocity_frames.csv`",
            "- `radial_shell_phase_frames.csv`",
            "- `shell_phase_coherence_by_radius.csv`",
            "- `angular_shell_phase_coherence.csv`",
            "- `node_antinode_stability_maps.csv`",
            "- `phase_drift_across_return_peaks.csv`",
            "- `spatial_phase_41_vs_51_comparison.csv`",
            "",
            "## Next Step",
            "",
            _next_step(classification),
            "",
            "## Guardrail",
            "",
            f"Frame capture used a loose return-frame threshold of `{options.frame_peak_threshold_fraction}` only to store evidence around below-gate returns; the event classification remains based on the default and strict thresholds.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "spatial_phase_coherent_blur_supported":
        return "The lifted row looks like the same spatial phase packet broadening at higher resolution. This would point future work toward bandwidth narrowing or smoother source envelopes, but it still does not authorize a source-shaped run by itself."
    if label == "spatial_phase_decoherence_supported":
        return "The lifted row loses spatial phase organization across shell sectors, radii, or node/antinode maps. Any future source candidate would need a mechanism-derived phase pre-compensation argument first."
    if label == "spatial_phase_shell_window_alignment_supported":
        return "The lifted row keeps spatial coherence but shifts its radial center. A future correction would need to be framed as a shell-window/radial-gate alignment check rather than cutoff tuning."
    if label == "finite_resolution_spatial_mechanism_not_isolated":
        return "The lifted row still loses strict returns, but these frames do not isolate whether width, phase, or radial alignment is the cause. Treat the passive branch as a finite-resolution controlled mode until a sharper mechanism appears."
    return "The frame capture did not settle the spatial phase mechanism. Do not add source shaping, cutoff tuning, or larger grids from this result alone."


def _next_step(classification: dict[str, Any]) -> str:
    if classification["label"] == "spatial_phase_coherent_blur_supported":
        return "Archive this as evidence for coherent blur; a future source-shaped candidate still needs an explicit bandwidth-narrowing design before any physics run."
    if classification["label"] == "spatial_phase_decoherence_supported":
        return "Analyze the sector/radius phase maps before designing any phase pre-compensation candidate."
    if classification["label"] == "spatial_phase_shell_window_alignment_supported":
        return "Use the frame maps to check whether the frozen shell gate is measuring the same physical packet before proposing any correction."
    return "No new physics run is recommended by this instrumentation pass."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "audit_group",
        "source_run_kind",
        "prediction_role",
        "grid_size",
        "dx",
        "dt",
        "dt_variant",
        "dt_scale",
        "physical_duration",
        "drive_frequency",
        "drive_cutoff_time",
        "target_release_phase",
        "cutoff_phase_cycles",
        "cutoff_phase_radians",
        "target_reference_work_per_source_area",
        "work_per_source_area",
        "primary_positive_work",
        "second_pulse_positive_work",
        "added_positive_work",
        "total_positive_work",
        "shell_window_radius",
        "shell_window_width",
        "first_shell_arrival_time",
        "shell_peak_time",
        "shell_peak_energy",
        "shell_exit_detected",
        "major_shell_peak_count",
        "refocus_peak_count",
        "loose_major_peaks_at_0p25",
        "loose_refocus_peaks_at_0p25",
        "default_major_peaks_at_0p30",
        "default_refocus_peaks_at_0p30",
        "strict_major_peaks_at_0p35",
        "strict_refocus_peaks_at_0p35",
        "strict_major_peaks_at_0p40",
        "strict_refocus_peaks_at_0p40",
        "conservative_major_peaks",
        "conservative_refocus_peaks",
        "tail_shell_retention",
        "tail_outer_to_shell_mean",
        "post_cutoff_shell_decay_rate",
        "threshold_free_tail_area_after_t50",
        "threshold_free_shell_area_after_cutoff",
        "shell_energy_autocorrelation",
        "dominant_spectral_concentration",
        "return_timing_regularity",
        "instrumented_return_frame_count",
        "instrumented_frame_threshold_fraction",
        "shell_phase_coherence_mean",
        "shell_phase_coherence_min",
        "shell_phase_coherence_max",
        "radial_phase_coherence_mean",
        "angular_phase_coherence_mean",
        "node_phase_stability_mean",
        "node_sign_consistency_mean",
        "node_region_phase_stability_mean",
        "antinode_phase_stability_mean",
        "return_phase_drift_std_cycles",
        "return_phase_drift_abs_mean_cycles",
        "return_radial_centroid_mean",
        "return_radial_spread_mean",
        "return_radial_width_mean",
        "return_peak_radius_mean",
        "return_peak_energy_decay_per_return",
    ]


def _robust_fields() -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "rank",
        "major_peaks_at_0p25",
        "major_peaks_at_0p30",
        "major_peaks_at_0p35",
        "major_peaks_at_0p40",
        "refocus_peaks_at_0p25",
        "refocus_peaks_at_0p30",
        "refocus_peaks_at_0p35",
        "refocus_peaks_at_0p40",
        "retention_median",
        "outer_shell_median",
        "decay_median",
        "no_exit_across_all_thresholds",
        "global_outer_false_across_all_thresholds",
        "threshold_free_shell_energy_area_after_cutoff",
        "threshold_free_tail_energy_area_after_t50",
        "shell_energy_autocorrelation",
        "dominant_spectral_concentration",
        "return_timing_regularity",
        "conservative_score",
        "default_threshold_score",
    ]


def _threshold_fields() -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "grid_size",
        "peak_threshold_fraction",
        "major_shell_peak_count",
        "refocus_peak_count",
    ]


def _frame_index_fields() -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "grid_size",
        "frame_id",
        "peak_rank",
        "time",
        "shell_energy",
        "shell_phase_mean_cycles",
        "shell_phase_coherence",
        "return_peak_radius",
        "return_radial_centroid",
        "return_radial_spread",
        "return_radial_width",
        "rms_displacement",
        "rms_velocity",
        "positive_displacement_fraction",
    ]


def _node_frame_fields(value_field: str) -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "grid_size",
        "frame_id",
        "peak_rank",
        "time",
        "node_index",
        "x",
        "y",
        "z",
        "radius",
        "theta",
        "polar",
        value_field,
    ]


def _radial_frame_fields() -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "grid_size",
        "frame_id",
        "peak_rank",
        "time",
        "radial_bin",
        "radial_bin_inner",
        "radial_bin_outer",
        "radial_bin_center",
        "node_count",
        "shell_energy",
        "phase_mean_cycles",
        "phase_coherence",
        "mean_displacement",
        "mean_velocity",
        "rms_displacement",
        "rms_velocity",
    ]


def _radial_coherence_fields() -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "grid_size",
        "radial_bin",
        "radial_bin_center",
        "frame_count",
        "phase_coherence_mean",
        "phase_coherence_min",
        "phase_coherence_max",
        "phase_drift_std_cycles",
        "shell_energy_mean",
        "rms_displacement_mean",
    ]


def _angular_fields() -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "grid_size",
        "frame_id",
        "peak_rank",
        "time",
        "polar_bin",
        "theta_bin",
        "node_count",
        "shell_energy",
        "phase_mean_cycles",
        "phase_coherence",
        "rms_displacement",
        "rms_velocity",
    ]


def _stability_fields() -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "grid_size",
        "node_index",
        "x",
        "y",
        "z",
        "radius",
        "theta",
        "polar",
        "node_antinode_label",
        "rms_displacement_over_returns",
        "mean_abs_displacement",
        "sign_consistency",
        "phase_coherence_over_returns",
        "frame_count",
    ]


def _drift_fields() -> list[str]:
    return [
        "variant",
        "spatial_phase_instrumentation_classification",
        "grid_size",
        "from_peak_rank",
        "to_peak_rank",
        "from_time",
        "to_time",
        "time_delta",
        "from_phase_cycles",
        "to_phase_cycles",
        "phase_drift_cycles",
        "from_shell_phase_coherence",
        "to_shell_phase_coherence",
        "energy_ratio",
        "radial_centroid_delta",
        "radial_spread_delta",
    ]


def _comparison_fields() -> list[str]:
    return [
        "comparison",
        "spatial_phase_instrumentation_classification",
        "proof_variant",
        "lift_variant",
        "proof_grid_size",
        "lift_grid_size",
        "proof_cutoff",
        "lift_cutoff",
        "proof_phase",
        "lift_phase",
        "proof_default_count",
        "lift_default_count",
        "proof_strict_count",
        "lift_strict_count",
        "strict_major_loss",
        "strict_refocus_loss",
        "proof_shell_phase_coherence_mean",
        "lift_shell_phase_coherence_mean",
        "shell_phase_coherence_drop",
        "proof_radial_phase_coherence_mean",
        "lift_radial_phase_coherence_mean",
        "radial_phase_coherence_drop",
        "proof_angular_phase_coherence_mean",
        "lift_angular_phase_coherence_mean",
        "angular_phase_coherence_drop",
        "angular_sector_coherence_delta",
        "proof_node_phase_stability_mean",
        "lift_node_phase_stability_mean",
        "node_phase_stability_drop",
        "proof_return_radial_centroid_mean",
        "lift_return_radial_centroid_mean",
        "return_radial_centroid_shift",
        "proof_return_radial_spread_mean",
        "lift_return_radial_spread_mean",
        "return_radial_spread_relative_growth",
        "proof_return_radial_width_mean",
        "lift_return_radial_width_mean",
        "return_radial_width_delta",
        "radial_phase_profile_mean_abs_drift_cycles",
        "frame_peak_threshold_fraction",
    ]
