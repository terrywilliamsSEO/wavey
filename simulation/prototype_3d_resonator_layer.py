"""Passive 3D boundary-inner-edge resonator layer control."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import math

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Lattice3D, Prototype3DConfig, _calibrate_amplitude, _primary_drive_active
from .prototype_3d_cutoff_phase_map import (
    CutoffPhaseMap3DOptions,
    _cutoff_phase_cycles,
    _threshold_robust_fields,
    threshold_robust_refocusing_scores,
)
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _boundary_config as _interference_boundary_config
from .prototype_3d_interference_diagnostics import _shell_width, _threshold_like_options
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
from .prototype_3d_source_sponge import _effective_source_area, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area
from .prototype_3d_transport_packet import _radial_flux_density, _radial_profile_sum


@dataclass(frozen=True)
class ResonatorLayer3DOptions(CutoffPhaseMap3DOptions):
    """Options for the first passive resonator-layer mechanism test."""

    phase_offset: float = 0.0
    reference_variant: str = "no_resonator_reference_cutoff_17p940"
    fixed_drive_frequency: float = 0.92
    cutoffs: tuple[float, ...] = (17.920, 17.925, 17.930, 17.935, 17.940, 17.945, 17.950)
    weak_coupling: float = 0.04
    low_damping: float = 0.01
    high_damping: float = 0.20
    moderate_cubic_k3: float = 0.25
    below_frequency_scale: float = 0.98
    above_frequency_scale: float = 1.02
    strict_major_peak_target: int = 9
    strict_refocus_peak_target: int = 8
    energy_balance_relative_tolerance: float = 0.25


@dataclass(frozen=True)
class _ResonatorVariant:
    name: str
    role: str
    geometry: str
    enabled: bool
    coupling: float
    damping: float
    k1: float
    k3: float
    tuning_frequency: float | None


def run_3d_resonator_layer_control(
    base_config: SimulationConfig,
    *,
    options: ResonatorLayer3DOptions | None = None,
) -> dict[str, Any]:
    """Run a narrow passive nonlinear resonator layer control around the phase-lock cluster."""

    options = options or ResonatorLayer3DOptions()
    control_id = datetime.now().strftime("resonator_layer_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    lifecycle_options = _lifecycle_options(options)
    threshold_options = _threshold_like_options(lifecycle_options)
    target_work_per_area = options.target_work_per_source_area or _calibration_work_per_area(
        base_config,
        threshold_options,
        source_width,
    )
    reference_drive_amplitude = _calibrated_reference_amplitude(
        base_config,
        threshold_options,
        source_width,
        target_work_per_area,
    )

    rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    energy_rows: list[dict[str, Any]] = []
    coupling_rows: list[dict[str, Any]] = []
    for config in variants:
        config.drive_amplitude = reference_drive_amplitude
        target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
        _calibrate_amplitude(config, target_work)
        config.steps = max(config.steps, int(round(options.physical_duration / max(config.dt, EPSILON))))
        result = _run_resonator_variant(config, lifecycle_options, options)
        summary = result["summary"]
        _add_control_fields(summary, config, options, target_work_per_area)
        rows.append(summary)
        timeseries_rows.extend(result["timeseries"])
        event_rows.extend(result["events"])
        energy_rows.extend(result["energy_timeseries"])
        coupling_rows.extend(result["coupling_timeseries"])

    robust_rows = _enrich_threshold_rows(threshold_robust_refocusing_scores(rows, timeseries_rows, options), rows)
    cluster_width = phase_lock_cluster_width(rows, robust_rows, options)
    classification = classify_resonator_layer_control(rows, robust_rows, options)
    for row in rows:
        row["resonator_layer_classification"] = classification["label"]

    summary_csv = root / "resonator_layer_summary.csv"
    threshold_csv = root / "resonator_layer_threshold_robust_score.csv"
    timeseries_csv = root / "resonator_energy_timeseries.csv"
    coupling_csv = root / "coupling_exchange_timeseries.csv"
    events_csv = root / "resonator_layer_events.csv"
    report_path = root / "resonator_layer_report.md"
    _write_csv(summary_csv, rows, _summary_fields())
    _write_csv(threshold_csv, robust_rows, _threshold_fields())
    _write_csv(timeseries_csv, energy_rows, _energy_timeseries_fields())
    _write_csv(coupling_csv, coupling_rows, _coupling_timeseries_fields())
    _write_csv(events_csv, event_rows, _event_fields())
    _write_report(report_path, control_id, rows, robust_rows, cluster_width, classification)
    save_json(
        root / "resonator_layer_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "phase_lock_cluster_width": cluster_width,
            "variants": rows,
            "threshold_robust_refocusing_scores": robust_rows,
            "summary_csv": str(summary_csv),
            "threshold_robust_csv": str(threshold_csv),
            "energy_timeseries_csv": str(timeseries_csv),
            "coupling_exchange_csv": str(coupling_csv),
            "events_csv": str(events_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": rows,
        "threshold_robust_scores": robust_rows,
        "phase_lock_cluster_width": cluster_width,
        "summary_csv": str(summary_csv),
        "threshold_robust_csv": str(threshold_csv),
        "energy_timeseries_csv": str(timeseries_csv),
        "coupling_exchange_csv": str(coupling_csv),
        "events_csv": str(events_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_resonator_layer_control(
    rows: list[dict[str, Any]],
    robust_rows: list[dict[str, Any]],
    options: ResonatorLayer3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the passive layer widens, improves, contaminates, or loses to reference."""

    options = options or ResonatorLayer3DOptions()
    if not rows or not robust_rows:
        return {"label": "inconclusive", "reason": "No resonator-layer rows were available.", "checks": {}}
    cluster_width = phase_lock_cluster_width(rows, robust_rows, options)
    checks = {
        "phase_lock_cluster_width": cluster_width,
        "energy_accounting_failures": [
            row["variant"]
            for row in rows
            if not bool(row.get("energy_accounting_passed"))
        ],
    }
    if checks["energy_accounting_failures"]:
        return {
            "label": "energy_accounting_failed",
            "reason": "At least one resonator row failed the passive resonator energy-balance tolerance.",
            "best_variant": _best_robust_variant(robust_rows),
            "checks": checks,
        }

    reference_count = int(cluster_width.get("reference_strict_decay_matched_count") or 0)
    widening_groups = [
        group
        for group in cluster_width.get("groups", [])
        if group.get("resonator_variant") != "no_resonator_reference"
        and int(group.get("strict_decay_matched_count") or 0) > reference_count
    ]
    if widening_groups:
        best_group = max(widening_groups, key=lambda group: int(group.get("strict_decay_matched_count") or 0))
        return {
            "label": "resonator_widens_phase_lock_cluster",
            "reason": (
                "A passive resonator layer preserved strict 9/8 refocusing at more clean neighboring cutoffs "
                "than the no-resonator reference without post-cutoff external work."
            ),
            "best_variant": best_group.get("best_variant"),
            "checks": checks,
        }

    if _has_clean_secondary_improvement(rows, robust_rows, options, reference_count):
        best = _best_nonreference_robust(rows, robust_rows)
        return {
            "label": "resonator_improves_refocusing",
            "reason": "A passive resonator row improved a conservative refocusing metric without narrowing the strict cluster or increasing contamination.",
            "best_variant": best.get("variant") if best else _best_robust_variant(robust_rows),
            "checks": checks,
        }

    if _has_contamination(rows, robust_rows):
        return {
            "label": "resonator_contaminates",
            "reason": "At least one resonator row raised raw retention while worsening outer/shell, decay, exit/global flags, or conservative score.",
            "best_variant": _best_robust_variant(robust_rows),
            "checks": checks,
        }

    return {
        "label": "no_resonator_still_wins",
        "reason": "The passive resonator layer did not widen the strict cluster or beat the no-resonator conservative score.",
        "best_variant": _best_robust_variant(robust_rows),
        "checks": checks,
    }


def phase_lock_cluster_width(
    rows: list[dict[str, Any]],
    robust_rows: list[dict[str, Any]],
    options: ResonatorLayer3DOptions | None = None,
) -> dict[str, Any]:
    """Count strict, clean 9/8 rows by resonator variant and cutoff neighborhood."""

    options = options or ResonatorLayer3DOptions()
    summary_by_variant = {str(row.get("variant")): row for row in rows}
    reference_by_cutoff = {
        _cutoff_key(row.get("drive_cutoff_time")): row
        for row in rows
        if row.get("resonator_variant") == "no_resonator_reference"
    }
    groups = []
    for resonator_variant in _ordered_resonator_variants(rows):
        group_robust = [
            row
            for row in robust_rows
            if summary_by_variant.get(str(row.get("variant")), {}).get("resonator_variant") == resonator_variant
        ]
        strict_rows = []
        strict_decay_rows = []
        for robust in group_robust:
            summary = summary_by_variant.get(str(robust.get("variant")), {})
            if not _strict_clean_row(summary, robust, options):
                continue
            strict_rows.append(robust)
            reference = reference_by_cutoff.get(_cutoff_key(summary.get("drive_cutoff_time")))
            if resonator_variant == "no_resonator_reference" or _decay_no_worse(summary, reference):
                strict_decay_rows.append(robust)
        strict_cutoffs = sorted(float(row.get("drive_cutoff_time") or 0.0) for row in strict_rows)
        strict_decay_cutoffs = sorted(float(row.get("drive_cutoff_time") or 0.0) for row in strict_decay_rows)
        best = max(group_robust, key=lambda row: float(row.get("conservative_score") or 0.0), default=None)
        groups.append(
            {
                "resonator_variant": resonator_variant,
                "strict_count": len(strict_rows),
                "strict_decay_matched_count": len(strict_decay_rows),
                "strict_cutoffs": strict_cutoffs,
                "strict_decay_matched_cutoffs": strict_decay_cutoffs,
                "strict_cutoff_width": _cutoff_span(strict_cutoffs),
                "strict_decay_matched_cutoff_width": _cutoff_span(strict_decay_cutoffs),
                "best_variant": best.get("variant") if best else "n/a",
                "best_conservative_score": best.get("conservative_score") if best else 0.0,
            }
        )
    reference_group = next((group for group in groups if group["resonator_variant"] == "no_resonator_reference"), None)
    return {
        "reference_strict_count": int((reference_group or {}).get("strict_count") or 0),
        "reference_strict_decay_matched_count": int((reference_group or {}).get("strict_decay_matched_count") or 0),
        "groups": groups,
    }


def _variant_plan(base: SimulationConfig, options: ResonatorLayer3DOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    variants = []
    for resonator in _resonator_variants(options):
        for cutoff in options.cutoffs:
            config = _boundary_config(_variant_name(resonator.name, cutoff), base, options, source_width, cutoff)
            config.resonator_enabled = resonator.enabled
            config.resonator_geometry = resonator.geometry
            config.resonator_coupling = resonator.coupling
            config.resonator_damping = resonator.damping
            config.resonator_k1 = resonator.k1
            config.resonator_k3 = resonator.k3
            setattr(config, "_resonator_variant", resonator.name)
            setattr(config, "_resonator_role", resonator.role)
            setattr(config, "_resonator_tuning_frequency", resonator.tuning_frequency)
            setattr(config, "_cutoff_offset_from_center", float(cutoff) - 18.0)
            variants.append(config)
    return variants


def _resonator_variants(options: ResonatorLayer3DOptions) -> list[_ResonatorVariant]:
    tuned = float(options.fixed_drive_frequency)
    below = tuned * options.below_frequency_scale
    above = tuned * options.above_frequency_scale
    tuned_k1 = _frequency_to_k1(tuned)
    return [
        _ResonatorVariant("no_resonator_reference", "reference", "none", False, 0.0, 0.0, 0.0, 0.0, None),
        _ResonatorVariant(
            "boundary_inner_edge_resonator_layer_tuned",
            "boundary_inner_edge_resonator_layer",
            "boundary_inner_edge",
            True,
            options.weak_coupling,
            options.low_damping,
            tuned_k1,
            0.0,
            tuned,
        ),
        _ResonatorVariant(
            "boundary_inner_edge_resonator_layer_below",
            "boundary_inner_edge_resonator_layer",
            "boundary_inner_edge",
            True,
            options.weak_coupling,
            options.low_damping,
            _frequency_to_k1(below),
            0.0,
            below,
        ),
        _ResonatorVariant(
            "boundary_inner_edge_resonator_layer_above",
            "boundary_inner_edge_resonator_layer",
            "boundary_inner_edge",
            True,
            options.weak_coupling,
            options.low_damping,
            _frequency_to_k1(above),
            0.0,
            above,
        ),
        _ResonatorVariant(
            "boundary_inner_edge_resonator_layer_moderate_cubic",
            "boundary_inner_edge_resonator_layer",
            "boundary_inner_edge",
            True,
            options.weak_coupling,
            options.low_damping,
            tuned_k1,
            options.moderate_cubic_k3,
            tuned,
        ),
        _ResonatorVariant(
            "zero_coupling_control",
            "zero_coupling_control",
            "boundary_inner_edge",
            True,
            0.0,
            options.low_damping,
            tuned_k1,
            0.0,
            tuned,
        ),
        _ResonatorVariant(
            "high_damping_control",
            "high_damping_control",
            "boundary_inner_edge",
            True,
            options.weak_coupling,
            options.high_damping,
            tuned_k1,
            0.0,
            tuned,
        ),
    ]


def _boundary_config(
    name: str,
    base: SimulationConfig,
    options: ResonatorLayer3DOptions,
    source_width: float,
    cutoff: float,
) -> Prototype3DConfig:
    config = _interference_boundary_config(name, base, _lifecycle_options(options), source_width, "cubic", cubic_sign=-1.0, phase_offset=0.0)
    config.drive_cutoff_time = float(cutoff)
    config.drive_frequency = float(options.fixed_drive_frequency)
    config.second_pulse_center_time = None
    config.second_pulse_duration = 0.0
    config.second_pulse_amplitude_scale = 0.0
    return config


def _run_resonator_variant(
    config: Prototype3DConfig,
    lifecycle_options: PacketLifecycle3DOptions,
    options: ResonatorLayer3DOptions,
) -> dict[str, Any]:
    lattice = Lattice3D(config)
    coords = lattice.coords
    radius = coords["radius"]
    shell_width = _shell_width(config, lifecycle_options)
    shell_outer = lifecycle_options.shell_window_radius + shell_width
    shell_mask = (radius > lifecycle_options.shell_window_radius) & (radius <= shell_outer)
    outer_mask = radius > shell_outer + shell_width
    active_mask = coords["boundary_distance"] >= config.sponge_width
    bins = np.linspace(0.0, np.sqrt(3.0) * config.domain_size / 2.0, lifecycle_options.radial_bins + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    timeseries: list[dict[str, Any]] = []
    energy_rows: list[dict[str, Any]] = []
    coupling_rows: list[dict[str, Any]] = []
    cumulative_positive_work = 0.0
    primary_positive_work = 0.0
    post_cutoff_external_positive_work = 0.0
    cumulative_inward_flux = 0.0
    cumulative_outward_flux = 0.0
    cumulative_coupling_to_lattice = 0.0
    cumulative_coupling_to_resonator = 0.0
    cumulative_positive_coupling_to_lattice = 0.0
    cumulative_positive_coupling_to_resonator = 0.0
    cumulative_resonator_damping_loss = 0.0
    initial_resonator_energy = lattice.resonator_energy()

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
        else:
            post_cutoff_external_positive_work += positive_work
        coupling_lattice = lattice.last_resonator_coupling_power_lattice
        coupling_resonator = lattice.last_resonator_coupling_power_resonator
        damping_power = lattice.last_resonator_damping_power
        cumulative_coupling_to_lattice += coupling_lattice * config.dt
        cumulative_coupling_to_resonator += coupling_resonator * config.dt
        cumulative_positive_coupling_to_lattice += max(0.0, coupling_lattice) * config.dt
        cumulative_positive_coupling_to_resonator += max(0.0, coupling_resonator) * config.dt
        cumulative_resonator_damping_loss += damping_power * config.dt
        if step % max(1, lifecycle_options.diagnostic_sample_every) != 0 and step != config.steps - 1:
            continue

        energy = lattice.energy_density()
        resonator_energy_density = lattice.resonator_energy_density()
        coupling_energy_density = lattice.resonator_coupling_energy_density()
        flux_density = _radial_flux_density(lattice)
        shell_flux = float(np.sum(flux_density[shell_mask]))
        dt_sample = config.dt * max(1, lifecycle_options.diagnostic_sample_every)
        cumulative_inward_flux += max(0.0, -shell_flux) * dt_sample
        cumulative_outward_flux += max(0.0, shell_flux) * dt_sample
        active_energy = np.where(active_mask, energy, 0.0)
        radial_profile = _radial_profile_sum(active_energy, radius, bins)
        packet_peak_radius = float(centers[int(np.argmax(radial_profile))]) if radial_profile.size else 0.0
        packet_width = _profile_width(centers, radial_profile)
        packet_centroid = _weighted_mean(radius[active_mask], energy[active_mask])
        packet_spread = _weighted_std(radius[active_mask], energy[active_mask], packet_centroid)
        shell_energy = float(np.sum(energy[shell_mask]))
        outer_energy = float(np.sum(energy[outer_mask & active_mask]))
        lattice_energy = float(np.sum(energy))
        resonator_energy = float(np.sum(resonator_energy_density))
        coupling_energy = float(np.sum(coupling_energy_density))
        combined_energy = lattice_energy + resonator_energy + coupling_energy
        base = {
            "variant": config.name,
            "resonator_variant": getattr(config, "_resonator_variant", "no_resonator_reference"),
            "time": time,
            "drive_cutoff_time": config.drive_cutoff_time,
            "lattice_energy": lattice_energy,
            "resonator_energy": resonator_energy,
            "resonator_coupling_energy": coupling_energy,
            "combined_energy": combined_energy,
            "resonator_fraction_of_combined": resonator_energy / (combined_energy + EPSILON),
            "coupling_power_to_lattice": coupling_lattice,
            "coupling_power_to_resonator": coupling_resonator,
            "resonator_damping_power": damping_power,
            "cumulative_coupling_to_lattice": cumulative_coupling_to_lattice,
            "cumulative_coupling_to_resonator": cumulative_coupling_to_resonator,
            "cumulative_positive_coupling_to_lattice": cumulative_positive_coupling_to_lattice,
            "cumulative_positive_coupling_to_resonator": cumulative_positive_coupling_to_resonator,
            "cumulative_resonator_damping_loss": cumulative_resonator_damping_loss,
            "cumulative_positive_work": cumulative_positive_work,
            "primary_positive_work": primary_positive_work,
            "post_cutoff_external_positive_work": post_cutoff_external_positive_work,
        }
        packet_row = {
            **base,
            "packet_peak_radius": packet_peak_radius,
            "packet_centroid_radius": packet_centroid,
            "packet_radial_width": packet_width,
            "packet_radial_spread": packet_spread,
            "shell_window_energy": shell_energy,
            "outer_active_energy": outer_energy,
            "outer_to_shell_energy": outer_energy / (shell_energy + EPSILON),
            "shell_fraction_of_total": shell_energy / (lattice_energy + EPSILON),
            "shell_radial_flux": shell_flux,
            "shell_inward_flux": max(0.0, -shell_flux),
            "shell_outward_flux": max(0.0, shell_flux),
            "cumulative_inward_flux": cumulative_inward_flux,
            "cumulative_outward_flux": cumulative_outward_flux,
            "second_pulse_positive_work": 0.0,
        }
        timeseries.append(packet_row)
        energy_rows.append(packet_row)
        coupling_rows.append(base)

    summary, events = _summarize_lifecycle(
        config,
        timeseries,
        primary_positive_work,
        shell_width,
        lifecycle_options,
        total_positive_work=cumulative_positive_work,
        second_pulse_positive_work=0.0,
    )
    energy_summary = _energy_summary(
        energy_rows,
        initial_resonator_energy,
        cumulative_coupling_to_lattice,
        cumulative_coupling_to_resonator,
        cumulative_positive_coupling_to_lattice,
        cumulative_positive_coupling_to_resonator,
        cumulative_resonator_damping_loss,
        post_cutoff_external_positive_work,
        options,
    )
    summary.update(energy_summary)
    return {
        "summary": summary,
        "timeseries": timeseries,
        "events": events,
        "energy_timeseries": energy_rows,
        "coupling_timeseries": coupling_rows,
    }


def _energy_summary(
    rows: list[dict[str, Any]],
    initial_resonator_energy: float,
    cumulative_coupling_to_lattice: float,
    cumulative_coupling_to_resonator: float,
    cumulative_positive_coupling_to_lattice: float,
    cumulative_positive_coupling_to_resonator: float,
    cumulative_resonator_damping_loss: float,
    post_cutoff_external_positive_work: float,
    options: ResonatorLayer3DOptions,
) -> dict[str, Any]:
    if not rows:
        return {
            "post_cutoff_external_positive_work": post_cutoff_external_positive_work,
            "energy_accounting_passed": False,
            "energy_accounting_relative_error": 1.0,
        }
    tail = rows[max(0, int(len(rows) * 0.65)) :]
    final = rows[-1]
    final_resonator_energy = float(final.get("resonator_energy") or 0.0)
    resonator_delta = final_resonator_energy - initial_resonator_energy
    expected_delta = cumulative_coupling_to_resonator - cumulative_resonator_damping_loss
    balance_error = abs(resonator_delta - expected_delta)
    balance_scale = max(
        abs(resonator_delta),
        abs(cumulative_coupling_to_resonator),
        abs(cumulative_resonator_damping_loss),
        max(float(row.get("resonator_energy") or 0.0) for row in rows),
        EPSILON,
    )
    relative_error = balance_error / balance_scale
    return {
        "lattice_energy_final": final.get("lattice_energy"),
        "lattice_energy_tail_mean": _mean_value(row.get("lattice_energy") for row in tail),
        "resonator_energy_initial": initial_resonator_energy,
        "resonator_energy_final": final_resonator_energy,
        "resonator_energy_peak": max(float(row.get("resonator_energy") or 0.0) for row in rows),
        "resonator_energy_tail_mean": _mean_value(row.get("resonator_energy") for row in tail),
        "resonator_coupling_energy_peak": max(float(row.get("resonator_coupling_energy") or 0.0) for row in rows),
        "combined_energy_final": final.get("combined_energy"),
        "cumulative_coupling_to_lattice": cumulative_coupling_to_lattice,
        "cumulative_coupling_to_resonator": cumulative_coupling_to_resonator,
        "cumulative_positive_coupling_to_lattice": cumulative_positive_coupling_to_lattice,
        "cumulative_positive_coupling_to_resonator": cumulative_positive_coupling_to_resonator,
        "cumulative_resonator_damping_loss": cumulative_resonator_damping_loss,
        "post_cutoff_external_positive_work": post_cutoff_external_positive_work,
        "no_post_cutoff_external_work": abs(post_cutoff_external_positive_work) <= 1.0e-9,
        "resonator_energy_balance_error": balance_error,
        "energy_accounting_relative_error": relative_error,
        "energy_accounting_passed": relative_error <= options.energy_balance_relative_tolerance,
    }


def _add_control_fields(
    row: dict[str, Any],
    config: Prototype3DConfig,
    options: ResonatorLayer3DOptions,
    target_work_per_area: float,
) -> None:
    row["family"] = "sign_flip"
    row["axis_label"] = "resonator_layer"
    row["resonator_variant"] = getattr(config, "_resonator_variant", "no_resonator_reference")
    row["resonator_role"] = getattr(config, "_resonator_role", "reference")
    row["resonator_geometry"] = config.resonator_geometry
    row["resonator_enabled"] = config.resonator_enabled
    row["resonator_node_count"] = int(np.count_nonzero(Lattice3D(config).resonator_mask)) if config.resonator_enabled else 0
    row["resonator_k1"] = config.resonator_k1
    row["resonator_k3"] = config.resonator_k3
    row["resonator_damping"] = config.resonator_damping
    row["resonator_coupling"] = config.resonator_coupling
    row["resonator_tuning_frequency"] = getattr(config, "_resonator_tuning_frequency", None)
    row["target_reference_work_per_source_area"] = target_work_per_area
    row["drive_mode"] = config.drive_mode
    row["drive_frequency"] = config.drive_frequency
    row["drive_cutoff_time"] = config.drive_cutoff_time
    row["boundary_phase_offset"] = config.boundary_phase_offset
    row["boundary_cubic_phase_sign"] = config.boundary_cubic_phase_sign
    row["cutoff_phase_cycles"] = _cutoff_phase_cycles(config)
    row["cutoff_offset_from_center"] = getattr(config, "_cutoff_offset_from_center", config.drive_cutoff_time - 18.0)
    row["outer_shell_below_1"] = float(row.get("tail_outer_to_shell_mean") or 999.0) < 1.0
    row["strict_9_8_default_clean"] = (
        int(row.get("major_shell_peak_count") or 0) >= options.strict_major_peak_target
        and int(row.get("refocus_peak_count") or 0) >= options.strict_refocus_peak_target
        and float(row.get("tail_outer_to_shell_mean") or 999.0) < options.strict_outer_shell_target
        and not bool(row.get("shell_exit_detected"))
        and not bool(row.get("global_peak_in_outer_window"))
        and bool(row.get("no_post_cutoff_external_work"))
    )


def _enrich_threshold_rows(rows: list[dict[str, Any]], summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary_by_variant = {str(row.get("variant")): row for row in summaries}
    enriched = []
    for row in rows:
        summary = summary_by_variant.get(str(row.get("variant")), {})
        enriched.append(
            {
                **row,
                "resonator_variant": summary.get("resonator_variant"),
                "resonator_role": summary.get("resonator_role"),
                "resonator_coupling": summary.get("resonator_coupling"),
                "resonator_damping": summary.get("resonator_damping"),
                "resonator_k1": summary.get("resonator_k1"),
                "resonator_k3": summary.get("resonator_k3"),
                "post_cutoff_external_positive_work": summary.get("post_cutoff_external_positive_work"),
                "energy_accounting_passed": summary.get("energy_accounting_passed"),
            }
        )
    return enriched


def _has_clean_secondary_improvement(
    rows: list[dict[str, Any]],
    robust_rows: list[dict[str, Any]],
    options: ResonatorLayer3DOptions,
    reference_count: int,
) -> bool:
    cluster = phase_lock_cluster_width(rows, robust_rows, options)
    non_narrowing = {
        group["resonator_variant"]
        for group in cluster["groups"]
        if group["resonator_variant"] != "no_resonator_reference"
        and int(group.get("strict_decay_matched_count") or 0) >= reference_count
    }
    if not non_narrowing:
        return False
    summary_by_variant = {str(row.get("variant")): row for row in rows}
    reference_by_cutoff = {
        _cutoff_key(row.get("drive_cutoff_time")): row
        for row in rows
        if row.get("resonator_variant") == "no_resonator_reference"
    }
    robust_by_variant = {str(row.get("variant")): row for row in robust_rows}
    for row in rows:
        if row.get("resonator_variant") not in non_narrowing:
            continue
        robust = robust_by_variant.get(str(row.get("variant")))
        reference = reference_by_cutoff.get(_cutoff_key(row.get("drive_cutoff_time")))
        if robust is None or reference is None or not _strict_clean_row(row, robust, options) or not _decay_no_worse(row, reference):
            continue
        reference_robust = robust_by_variant.get(str(reference.get("variant")), {})
        if (
            int(robust.get("min_refocus_peaks_across_thresholds") or 0) > int(reference_robust.get("min_refocus_peaks_across_thresholds") or 0)
            or float(row.get("tail_shell_retention") or 0.0) >= 1.02 * float(reference.get("tail_shell_retention") or 0.0)
            or float(row.get("post_cutoff_shell_decay_rate") or 0.0) > float(reference.get("post_cutoff_shell_decay_rate") or 0.0) + 0.001
            or float(robust.get("return_timing_regularity") or 0.0) > float(reference_robust.get("return_timing_regularity") or 0.0) + 0.02
            or float(robust.get("conservative_score") or 0.0) > float(reference_robust.get("conservative_score") or 0.0)
        ):
            return True
    return bool(summary_by_variant) and False


def _has_contamination(rows: list[dict[str, Any]], robust_rows: list[dict[str, Any]]) -> bool:
    robust_by_variant = {str(row.get("variant")): row for row in robust_rows}
    reference_by_cutoff = {
        _cutoff_key(row.get("drive_cutoff_time")): row
        for row in rows
        if row.get("resonator_variant") == "no_resonator_reference"
    }
    for row in rows:
        if row.get("resonator_variant") == "no_resonator_reference":
            continue
        reference = reference_by_cutoff.get(_cutoff_key(row.get("drive_cutoff_time")))
        if reference is None:
            continue
        retention_rose = float(row.get("tail_shell_retention") or 0.0) > 1.02 * float(reference.get("tail_shell_retention") or 0.0)
        if not retention_rose:
            continue
        robust = robust_by_variant.get(str(row.get("variant")), {})
        reference_robust = robust_by_variant.get(str(reference.get("variant")), {})
        if (
            float(row.get("tail_outer_to_shell_mean") or 999.0) > float(reference.get("tail_outer_to_shell_mean") or 999.0) + 0.05
            or float(row.get("post_cutoff_shell_decay_rate") or 0.0) < float(reference.get("post_cutoff_shell_decay_rate") or 0.0) - 0.005
            or bool(row.get("shell_exit_detected"))
            or bool(row.get("global_peak_in_outer_window"))
            or float(robust.get("conservative_score") or 0.0) < float(reference_robust.get("conservative_score") or 0.0)
        ):
            return True
    return False


def _strict_clean_row(summary: dict[str, Any], robust: dict[str, Any], options: ResonatorLayer3DOptions) -> bool:
    return (
        int(robust.get("min_major_peaks_across_thresholds") or 0) >= options.strict_major_peak_target
        and int(robust.get("min_refocus_peaks_across_thresholds") or 0) >= options.strict_refocus_peak_target
        and float(robust.get("outer_shell_median") or 999.0) < options.strict_outer_shell_target
        and bool(robust.get("no_exit_across_all_thresholds"))
        and bool(robust.get("global_outer_false_across_all_thresholds"))
        and bool(summary.get("no_post_cutoff_external_work"))
        and bool(summary.get("energy_accounting_passed"))
    )


def _decay_no_worse(row: dict[str, Any], reference: dict[str, Any] | None) -> bool:
    if reference is None:
        return False
    return float(row.get("post_cutoff_shell_decay_rate") or 0.0) >= float(reference.get("post_cutoff_shell_decay_rate") or 0.0) - 1.0e-9


def _best_nonreference_robust(rows: list[dict[str, Any]], robust_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    summaries = {str(row.get("variant")): row for row in rows}
    candidates = [
        row
        for row in robust_rows
        if summaries.get(str(row.get("variant")), {}).get("resonator_variant") != "no_resonator_reference"
    ]
    return max(candidates, key=lambda row: float(row.get("conservative_score") or 0.0), default=None)


def _best_robust_variant(rows: list[dict[str, Any]]) -> str:
    best = max(rows, key=lambda row: float(row.get("conservative_score") or 0.0), default=None)
    return str((best or {}).get("variant", "n/a"))


def _ordered_resonator_variants(rows: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        variant = str(row.get("resonator_variant"))
        if variant not in seen:
            seen.append(variant)
    return seen


def _cutoff_key(value: Any) -> float:
    return round(float(value or 0.0), 6)


def _cutoff_span(values: list[float]) -> float:
    return max(values) - min(values) if len(values) >= 2 else 0.0


def _frequency_to_k1(frequency: float) -> float:
    return float((2.0 * math.pi * frequency) ** 2)


def _variant_name(resonator_name: str, cutoff: float) -> str:
    return f"{resonator_name}_cutoff_{_cutoff_label(cutoff)}"


def _cutoff_label(cutoff: float) -> str:
    return f"{cutoff:.3f}".replace(".", "p")


def _mean_value(values: Any) -> float:
    parsed = [float(value) for value in values if value is not None]
    return float(np.mean(parsed)) if parsed else 0.0


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    robust_rows: list[dict[str, Any]],
    cluster_width: dict[str, Any],
    classification: dict[str, Any],
) -> None:
    best = max(robust_rows, key=lambda row: float(row.get("conservative_score") or 0.0), default={})
    best_summary = next((row for row in rows if row.get("variant") == best.get("variant")), {})
    lines = [
        f"# 3D Resonator Layer Control: {control_id}",
        "",
        "## Purpose",
        "",
        "Small passive nonlinear boundary-inner-edge resonator test around the confirmed 41^3 neutral-lattice phase-lock cluster.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## threshold-robust refocusing score",
        "",
        "Rows are ranked by conservative cross-threshold score first, then default-threshold score.",
        "",
        "| Rank | Variant | Resonator | Cutoff | Phase | Min Peaks | Median Peaks | Min Refocus | Median Refocus | Default | Ret Med | Outer Med | Decay Med | No Exit All | Global Outer False All | Timing Regularity | Conservative | Default Score |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |",
    ]
    for row in robust_rows:
        lines.append(
            "| "
            f"{row.get('rank')} | "
            f"{row.get('variant')} | "
            f"{row.get('resonator_variant')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{_format(row.get('min_major_peaks_across_thresholds'))} | "
            f"{_format(row.get('median_major_peaks_across_thresholds'))} | "
            f"{_format(row.get('min_refocus_peaks_across_thresholds'))} | "
            f"{_format(row.get('median_refocus_peaks_across_thresholds'))} | "
            f"{row.get('default_major_peaks')}/{row.get('default_refocus_peaks')} | "
            f"{_format(row.get('retention_median'))} | "
            f"{_format(row.get('outer_shell_median'))} | "
            f"{_format(row.get('decay_median'))} | "
            f"{row.get('no_exit_across_all_thresholds')} | "
            f"{row.get('global_outer_false_across_all_thresholds')} | "
            f"{_format(row.get('return_timing_regularity'))} | "
            f"{_format(row.get('conservative_score'))} | "
            f"{_format(row.get('default_threshold_score'))} |"
        )
    lines.extend(
        [
            "",
            "## phase-lock cluster width",
            "",
            "| Resonator | Strict Cutoffs | Strict Count | Decay-Matched Strict Cutoffs | Decay-Matched Count | Width | Best Variant |",
            "| --- | --- | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for group in cluster_width.get("groups", []):
        lines.append(
            "| "
            f"{group.get('resonator_variant')} | "
            f"{_format_cutoff_list(group.get('strict_cutoffs'))} | "
            f"{group.get('strict_count')} | "
            f"{_format_cutoff_list(group.get('strict_decay_matched_cutoffs'))} | "
            f"{group.get('strict_decay_matched_count')} | "
            f"{_format(group.get('strict_decay_matched_cutoff_width'))} | "
            f"{group.get('best_variant')} |"
        )
    lines.extend(
        [
            "",
            "## resonator energy accounting",
            "",
            "| Variant | Resonator | k1 | k3 | gamma | damping | Res Peak | Res Tail | Coupling Peak | Coupling To Res | Res Damping Loss | Balance Error | Balance Rel | Passed | Post-Cutoff Work |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row.get('variant')} | "
            f"{row.get('resonator_variant')} | "
            f"{_format(row.get('resonator_k1'))} | "
            f"{_format(row.get('resonator_k3'))} | "
            f"{_format(row.get('resonator_coupling'))} | "
            f"{_format(row.get('resonator_damping'))} | "
            f"{_format(row.get('resonator_energy_peak'))} | "
            f"{_format(row.get('resonator_energy_tail_mean'))} | "
            f"{_format(row.get('resonator_coupling_energy_peak'))} | "
            f"{_format(row.get('cumulative_coupling_to_resonator'))} | "
            f"{_format(row.get('cumulative_resonator_damping_loss'))} | "
            f"{_format(row.get('resonator_energy_balance_error'))} | "
            f"{_format(row.get('energy_accounting_relative_error'))} | "
            f"{row.get('energy_accounting_passed')} | "
            f"{_format(row.get('post_cutoff_external_positive_work'))} |"
        )
    lines.extend(
        [
            "",
            "## contamination audit",
            "",
            "| Variant | Resonator | Peaks | Refocus | Retention | Outer/Shell | Decay | Exit | Global Outer | No Post-Cutoff Work | Energy OK |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row.get('variant')} | "
            f"{row.get('resonator_variant')} | "
            f"{row.get('major_shell_peak_count')} | "
            f"{row.get('refocus_peak_count')} | "
            f"{_format(row.get('tail_shell_retention'))} | "
            f"{_format(row.get('tail_outer_to_shell_mean'))} | "
            f"{_format(row.get('post_cutoff_shell_decay_rate'))} | "
            f"{row.get('shell_exit_detected')} | "
            f"{row.get('global_peak_in_outer_window')} | "
            f"{row.get('no_post_cutoff_external_work')} | "
            f"{row.get('energy_accounting_passed')} |"
        )
    lines.extend(
        [
            "",
            "## best conservative row",
            "",
            f"- Variant: `{best.get('variant', 'n/a')}`",
            f"- Resonator: `{best.get('resonator_variant', 'n/a')}`",
            f"- Cutoff: `{_format(best.get('drive_cutoff_time'))}`",
            f"- Release phase: `{_format(best.get('cutoff_phase_cycles'))}` cycles",
            f"- Conservative/default scores: `{_format(best.get('conservative_score'))}` / `{_format(best.get('default_threshold_score'))}`",
            f"- Strict/default counts: `{best.get('min_major_peaks_across_thresholds')}/{best.get('min_refocus_peaks_across_thresholds')}` / `{best.get('default_major_peaks')}/{best.get('default_refocus_peaks')}`",
            f"- Retention, outer/shell, decay: `{_format(best_summary.get('tail_shell_retention'))}`, `{_format(best_summary.get('tail_outer_to_shell_mean'))}`, `{_format(best_summary.get('post_cutoff_shell_decay_rate'))}`",
            f"- Post-cutoff external work: `{_format(best_summary.get('post_cutoff_external_positive_work'))}`",
            "",
            "## Files",
            "",
            "- `resonator_layer_report.md`",
            "- `resonator_layer_summary.csv`",
            "- `resonator_layer_threshold_robust_score.csv`",
            "- `resonator_energy_timeseries.csv`",
            "- `coupling_exchange_timeseries.csv`",
            "- `resonator_layer_events.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _format_cutoff_list(values: Any) -> str:
    if not values:
        return "none"
    return ", ".join(_format(value) for value in values)


def _summary_fields() -> list[str]:
    return [
        "variant",
        "resonator_layer_classification",
        "resonator_variant",
        "resonator_role",
        "resonator_geometry",
        "resonator_enabled",
        "resonator_node_count",
        "resonator_k1",
        "resonator_k3",
        "resonator_damping",
        "resonator_coupling",
        "resonator_tuning_frequency",
        "grid_size",
        "dx",
        "dt",
        "physical_duration",
        "drive_mode",
        "drive_frequency",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "cutoff_offset_from_center",
        "boundary_phase_offset",
        "boundary_cubic_phase_sign",
        "positive_work_before_cutoff",
        "primary_positive_work",
        "post_cutoff_external_positive_work",
        "no_post_cutoff_external_work",
        "work_per_source_area",
        "target_reference_work_per_source_area",
        "shell_window_radius",
        "shell_window_width",
        "first_shell_arrival_time",
        "shell_peak_time",
        "shell_peak_energy",
        "shell_exit_time",
        "shell_exit_detected",
        "major_shell_peak_count",
        "refocus_peak_count",
        "first_refocus_time",
        "last_refocus_time",
        "refocus_peak_ratio_max",
        "tail_shell_retention",
        "tail_outer_to_shell_mean",
        "outer_shell_below_1",
        "post_cutoff_shell_decay_rate",
        "post_cutoff_shell_decay_r2",
        "global_peak_in_outer_window",
        "packet_width_growth_fraction",
        "inward_flux_fraction",
        "outward_flux_fraction",
        "lifecycle_label",
        "lattice_energy_final",
        "lattice_energy_tail_mean",
        "resonator_energy_initial",
        "resonator_energy_final",
        "resonator_energy_peak",
        "resonator_energy_tail_mean",
        "resonator_coupling_energy_peak",
        "combined_energy_final",
        "cumulative_coupling_to_lattice",
        "cumulative_coupling_to_resonator",
        "cumulative_positive_coupling_to_lattice",
        "cumulative_positive_coupling_to_resonator",
        "cumulative_resonator_damping_loss",
        "resonator_energy_balance_error",
        "energy_accounting_relative_error",
        "energy_accounting_passed",
        "strict_9_8_default_clean",
    ]


def _threshold_fields() -> list[str]:
    return [
        "resonator_variant",
        "resonator_role",
        "resonator_coupling",
        "resonator_damping",
        "resonator_k1",
        "resonator_k3",
        "post_cutoff_external_positive_work",
        "energy_accounting_passed",
        *_threshold_robust_fields(),
    ]


def _energy_timeseries_fields() -> list[str]:
    return [
        *_timeseries_fields(),
        "resonator_variant",
        "drive_cutoff_time",
        "lattice_energy",
        "resonator_energy",
        "resonator_coupling_energy",
        "combined_energy",
        "resonator_fraction_of_combined",
        "coupling_power_to_lattice",
        "coupling_power_to_resonator",
        "resonator_damping_power",
        "cumulative_coupling_to_lattice",
        "cumulative_coupling_to_resonator",
        "cumulative_positive_coupling_to_lattice",
        "cumulative_positive_coupling_to_resonator",
        "cumulative_resonator_damping_loss",
        "post_cutoff_external_positive_work",
    ]


def _coupling_timeseries_fields() -> list[str]:
    return [
        "variant",
        "resonator_variant",
        "time",
        "drive_cutoff_time",
        "coupling_power_to_lattice",
        "coupling_power_to_resonator",
        "resonator_damping_power",
        "cumulative_coupling_to_lattice",
        "cumulative_coupling_to_resonator",
        "cumulative_positive_coupling_to_lattice",
        "cumulative_positive_coupling_to_resonator",
        "cumulative_resonator_damping_loss",
        "post_cutoff_external_positive_work",
    ]
