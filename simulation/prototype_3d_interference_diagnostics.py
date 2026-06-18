"""3D boundary-interference diagnostics for neutral-lattice shell tails."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import (
    EPSILON,
    Lattice3D,
    Prototype3DConfig,
    Prototype3DOptions,
    _base_3d_config,
    _calibrate_amplitude,
    _coordinate_payload,
    _radial_bins,
    _run_variant,
    _summary_fields as _prototype_summary_fields,
    _write_csv as _write_prototype_csv,
)
from .prototype_3d_audit import Prototype3DFailureAuditOptions, run_3d_failure_audit
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_source_geometry import ALL_FACES
from .prototype_3d_source_sponge import _effective_source_area, _format, _merge_rows, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


@dataclass(frozen=True)
class InterferenceDiagnostics3DOptions:
    """Options for a tiny neutral-lattice boundary-interference diagnostic."""

    output_root: str = "runs"
    grid_size: int = 41
    reference_source_grid_size: int = 31
    sample_every: int = 10
    diagnostic_sample_every: int = 20
    radial_bins: int = 24
    shell_window_radius: float = 5.0
    shell_window_width: float | None = None
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    target_work_per_source_area: float | None = None
    random_phase_seeds: tuple[int, ...] = (31092, 41092)
    phase_offset: float = 0.5 * float(np.pi)
    min_retention: float = 0.45
    max_outer_ratio: float = 2.0
    min_tail_phase_coherence: float = 0.25
    min_standing_persistence: float = 0.60
    min_coherence_lift_over_random: float = 1.20


def run_3d_interference_diagnostics(
    base_config: SimulationConfig,
    *,
    options: InterferenceDiagnostics3DOptions | None = None,
) -> dict[str, Any]:
    """Run neutral-lattice phase controls and export phase/interference diagnostics."""

    options = options or InterferenceDiagnostics3DOptions()
    control_id = datetime.now().strftime("interference_diagnostics_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    reference_config = variants[0]
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    threshold_options = _threshold_like_options(options)
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

    prototype_options = Prototype3DOptions(
        output_root=options.output_root,
        grid_size=options.grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        include_dt_control=False,
        include_sponge_control=False,
    )
    rows: list[dict[str, Any]] = []
    configs_by_variant: dict[str, Prototype3DConfig] = {}
    for config in variants:
        config.drive_amplitude = reference_drive_amplitude
        target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
        _calibrate_amplitude(config, target_work)
        summary = _run_variant(config, root, prototype_options)
        _add_control_fields(summary, config, reference_config, options, target_work_per_area)
        summary["classification_label"] = None
        rows.append(summary)
        configs_by_variant[config.name] = config

    prototype_summary_csv = root / "prototype_3d_summary.csv"
    _write_prototype_csv(prototype_summary_csv, rows, _prototype_summary_fields())
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": control_id,
            "classification": {
                "label": "interference_diagnostics_3d",
                "reason": "Neutral-lattice boundary phase controls with phase/interference diagnostics.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "interference_diagnostics_3d_report.md"),
        },
    )

    audit = run_3d_failure_audit(
        root,
        base_config,
        options=Prototype3DFailureAuditOptions(
            output_dir=root / "failure_mode_audit",
            radial_bins=options.radial_bins,
            near_shell_width_dx=options.near_shell_width_dx,
        ),
    )
    control_rows = _merge_rows(rows, audit["variants"])

    diagnostic_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    modal_rows: list[dict[str, Any]] = []
    wavefront_rows: list[dict[str, Any]] = []
    for row in control_rows:
        config = configs_by_variant[row["variant"]]
        diagnostics = _run_phase_diagnostics(config, root, row, options)
        diagnostic_rows.append(diagnostics["summary"])
        phase_rows.extend(diagnostics["phase_rows"])
        modal_rows.extend(diagnostics["modal_rows"])
        wavefront_rows.extend(diagnostics["wavefront_rows"])

    combined_rows = _combine_rows(control_rows, diagnostic_rows)
    classification = classify_interference_diagnostics(combined_rows, options)
    for row in combined_rows:
        row["interference_classification"] = classification["label"]

    summary_csv = root / "interference_diagnostics_summary.csv"
    phase_csv = root / "phase_coherence_timeseries.csv"
    modal_csv = root / "modal_projection_timeseries.csv"
    wavefront_csv = root / "wavefront_timeseries.csv"
    report_path = root / "interference_diagnostics_3d_report.md"
    _write_csv(summary_csv, combined_rows, _summary_fields())
    _write_csv(phase_csv, phase_rows, _phase_fields())
    _write_csv(modal_csv, modal_rows, _modal_fields())
    _write_csv(wavefront_csv, wavefront_rows, _wavefront_fields())
    _plot_phase_coherence(root / "phase_coherence_plot.png", phase_rows)
    _plot_wavefront(root / "wavefront_shell_energy_plot.png", wavefront_rows, options)
    _plot_modal(root / "modal_projection_plot.png", modal_rows)
    _write_report(report_path, control_id, combined_rows, classification, options, audit)
    save_json(
        root / "interference_diagnostics_3d_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": combined_rows,
            "summary_csv": str(summary_csv),
            "phase_csv": str(phase_csv),
            "modal_csv": str(modal_csv),
            "wavefront_csv": str(wavefront_csv),
            "report_path": str(report_path),
            "audit_report_path": audit["report_path"],
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": combined_rows,
        "summary_csv": str(summary_csv),
        "phase_csv": str(phase_csv),
        "modal_csv": str(modal_csv),
        "wavefront_csv": str(wavefront_csv),
        "report_path": str(report_path),
        "audit_report_path": audit["report_path"],
        "path": str(root),
    }


def classify_interference_diagnostics(
    rows: list[dict[str, Any]],
    options: InterferenceDiagnostics3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether phase randomization supports a boundary-interference mechanism."""

    options = options or InterferenceDiagnostics3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No interference diagnostic rows were available.", "checks": {}}
    reference = next((row for row in rows if row["variant"] == "neutral_cubic_sign_flip_reference"), rows[0])
    random_rows = [row for row in rows if str(row.get("variant", "")).startswith("neutral_random_phase_seed_")]
    uniform = next((row for row in rows if row.get("variant") == "neutral_uniform_same_coverage"), None)
    offset = next((row for row in rows if row.get("variant") == "neutral_cubic_phase_offset"), None)
    reference_shell_clean = _shell_transport_clean(reference, options)
    reference_clean = _clean_shell(reference, options)
    random_clean = [row for row in random_rows if _clean_shell(row, options)]
    random_best_coherence = max((float(row.get("tail_phase_coherence_mean") or 0.0) for row in random_rows), default=0.0)
    reference_coherence = float(reference.get("tail_phase_coherence_mean") or 0.0)
    coherence_lift = reference_coherence / (random_best_coherence + EPSILON)
    random_outer_or_collapsed = all(
        bool(row.get("global_peak_in_outer_window"))
        or float(row.get("near_shell_tail_retention") or 0.0) < options.min_retention
        or float(row.get("outer_to_near_tail_energy_ratio") or 999.0) > options.max_outer_ratio
        for row in random_rows
    )
    checks = {
        "reference_clean": reference_clean,
        "reference_shell_clean": reference_shell_clean,
        "reference_tail_phase_coherence": reference_coherence,
        "reference_standing_persistence": reference.get("standing_shell_persistence"),
        "reference_cubic_projection": reference.get("tail_cubic_projection_mean"),
        "random_clean_count": len(random_clean),
        "random_best_tail_phase_coherence": random_best_coherence,
        "coherence_lift_over_random": coherence_lift,
        "uniform_clean": _clean_shell(uniform, options) if uniform else False,
        "offset_clean": _clean_shell(offset, options) if offset else False,
    }
    if not reference_shell_clean:
        return {
            "label": "reference_not_reproduced",
            "reason": "The neutral sign-flip cubic reference did not reproduce a clean retained shell tail.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if random_rows and random_outer_or_collapsed and coherence_lift >= options.min_coherence_lift_over_random:
        if not reference_clean:
            return {
                "label": "interference_supported_standing_weak",
                "reason": "Same-work random phase controls collapsed or became outer-contaminated and phase coherence dropped, but the cubic reference did not pass the standing-shell persistence threshold.",
                "best_variant": reference["variant"],
                "checks": checks,
            }
        return {
            "label": "structured_boundary_interference_supported",
            "reason": "The cubic reference retained a coherent standing shell while same-work random phase controls collapsed or became outer-contaminated.",
            "best_variant": reference["variant"],
            "checks": checks,
        }
    if random_clean:
        return {
            "label": "phase_randomization_survives",
            "reason": "At least one same-work random phase control retained a clean shell tail, so cubic-phase interference is not isolated yet.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if coherence_lift < options.min_coherence_lift_over_random:
        return {
            "label": "phase_coherence_not_distinct",
            "reason": "The cubic reference did not show enough phase-coherence lift over random phase controls.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "interference_inconclusive",
        "reason": "The phase controls changed the shell tail, but not enough criteria aligned to isolate interference.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: InterferenceDiagnostics3DOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    variants = [
        _boundary_config("neutral_cubic_sign_flip_reference", base, options, source_width, "cubic", cubic_sign=-1.0),
        _boundary_config("neutral_uniform_same_coverage", base, options, source_width, "uniform"),
        _boundary_config(
            "neutral_cubic_phase_offset",
            base,
            options,
            source_width,
            "cubic",
            cubic_sign=-1.0,
            phase_offset=options.phase_offset,
        ),
    ]
    for seed in options.random_phase_seeds:
        variants.append(
            _boundary_config(
                f"neutral_random_phase_seed_{seed}",
                base,
                options,
                source_width,
                "random",
                random_seed=seed,
            )
        )
    return variants


def _boundary_config(
    name: str,
    base: SimulationConfig,
    options: InterferenceDiagnostics3DOptions,
    source_width: float,
    phase_mode: str,
    *,
    cubic_sign: float = 1.0,
    phase_offset: float = 0.0,
    random_seed: int | None = None,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, Prototype3DOptions(grid_size=options.grid_size), "boundary", phase_mode)
    config.defect_stiffness_multiplier = 1.0
    config.defect_damping_multiplier = 1.0
    config.defect_coupling_multiplier = 1.0
    config.defect_inner_radius = None
    config.defect_nonlinear_strength = None
    config.sponge_strength *= options.sponge_strength_multiplier
    config.boundary_source_inner_distance = config.sponge_width
    config.boundary_source_width = source_width
    config.boundary_faces = ALL_FACES
    config.boundary_cubic_phase_sign = cubic_sign
    config.boundary_phase_offset = phase_offset
    config.boundary_random_phase_seed = random_seed
    return config


def _threshold_like_options(options: InterferenceDiagnostics3DOptions) -> Any:
    from .prototype_3d_threshold_control import ThresholdControl3DOptions

    return ThresholdControl3DOptions(
        output_root=options.output_root,
        grid_size=options.grid_size,
        reference_source_grid_size=options.reference_source_grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        near_shell_width_dx=options.near_shell_width_dx,
        sponge_strength_multiplier=options.sponge_strength_multiplier,
    )


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    reference_config: Prototype3DConfig,
    options: InterferenceDiagnostics3DOptions,
    target_work_per_area: float,
) -> None:
    summary["interference_role"] = _interference_role(config.name)
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    original_sponge_strength = reference_config.sponge_strength / max(options.sponge_strength_multiplier, EPSILON)
    summary["sponge_strength_multiplier_vs_original"] = config.sponge_strength / max(original_sponge_strength, EPSILON)
    summary["source_width_physical_reference"] = reference_config.boundary_source_width
    summary["target_reference_work_per_source_area"] = target_work_per_area
    summary["calibration_source_grid_size"] = options.reference_source_grid_size


def _interference_role(variant: str) -> str:
    if variant == "neutral_cubic_sign_flip_reference":
        return "cubic_reference"
    if variant == "neutral_uniform_same_coverage":
        return "uniform_phase_control"
    if variant == "neutral_cubic_phase_offset":
        return "cubic_phase_offset_control"
    if variant.startswith("neutral_random_phase_seed_"):
        return "random_phase_control"
    return "control"


def _run_phase_diagnostics(
    config: Prototype3DConfig,
    root: Path,
    summary_row: dict[str, Any],
    options: InterferenceDiagnostics3DOptions,
) -> dict[str, Any]:
    diag_dir = root / "interference_diagnostics" / config.name
    diag_dir.mkdir(parents=True, exist_ok=True)
    lattice = Lattice3D(config)
    coords = lattice.coords
    radius = coords["radius"]
    bins = _radial_bins(config, options.radial_bins)
    centers = 0.5 * (bins[:-1] + bins[1:])
    counts = _radial_bin_counts(radius, bins)
    shell_width = _shell_width(config, options)
    shell_inner = options.shell_window_radius
    shell_outer = shell_inner + shell_width
    shell_mask = (radius > shell_inner) & (radius <= shell_outer)
    outer_start = max(config.defect_radius, 0.5 * config.domain_size - config.sponge_width)
    outer_mask = radius >= outer_start
    active_peak_limit = max(shell_outer, 0.5 * config.domain_size - config.sponge_width)
    modal_mask = radius <= active_peak_limit
    cubic_basis = _normalized_basis(_cubic_basis(coords), modal_mask)
    shell_basis = _normalized_basis(np.exp(-0.5 * ((radius - 0.5 * (shell_inner + shell_outer)) / max(0.5 * shell_width, EPSILON)) ** 2), modal_mask)
    omega = 2.0 * np.pi * max(config.drive_frequency, EPSILON)

    phase_rows: list[dict[str, Any]] = []
    modal_rows: list[dict[str, Any]] = []
    wavefront_rows: list[dict[str, Any]] = []
    shell_vectors: list[np.ndarray] = []
    post_shell_vectors: list[np.ndarray] = []
    post_indices: list[int] = []
    best_snapshot: dict[str, Any] | None = None
    cumulative_positive_work = 0.0
    positive_work_before_cutoff = 0.0

    for step in range(config.steps):
        time = step * config.dt
        force = lattice.external_force(time)
        velocity_before = lattice.v.copy()
        lattice.step(time, config.dt)
        velocity_mid = 0.5 * (velocity_before + lattice.v)
        power = float(np.sum(force * velocity_mid) * config.cell_volume)
        cumulative_positive_work += max(0.0, power) * config.dt
        if time <= config.drive_cutoff_time:
            positive_work_before_cutoff += max(0.0, power) * config.dt
        if step % max(1, options.diagnostic_sample_every) != 0 and step != config.steps - 1:
            continue

        energy = lattice.energy_density()
        phase_vector = _phase_vector(lattice.u, lattice.v, omega)
        shell_energy = float(np.sum(energy[shell_mask]))
        total_energy = float(np.sum(energy))
        outer_energy = float(np.sum(energy[outer_mask]))
        shell_phase = _weighted_phase_mean(phase_vector[shell_mask], energy[shell_mask])
        alignment = _alignment(phase_vector, shell_phase)
        constructive = float(np.sum(energy[shell_mask & (alignment > 0.5)]) / (shell_energy + EPSILON))
        destructive = float(np.sum(energy[shell_mask & (alignment < -0.5)]) / (shell_energy + EPSILON))
        shell_coherence = _weighted_coherence(phase_vector[shell_mask], energy[shell_mask])
        outer_coherence = _weighted_coherence(phase_vector[outer_mask], energy[outer_mask])
        radial_sums = _radial_sums(energy, radius, bins)
        active_bins = centers <= active_peak_limit
        peak_idx = int(np.argmax(np.where(active_bins, radial_sums / np.maximum(counts, 1.0), -np.inf)))
        active_peak_radius = float(centers[peak_idx])
        cubic_projection = _basis_projection(lattice.u, cubic_basis, modal_mask)
        shell_projection = _basis_projection(lattice.u, shell_basis, modal_mask)
        fft_summary = _fft_summary(lattice.u)
        shell_vector = energy[shell_mask].astype(float).ravel()
        shell_vectors.append(shell_vector)
        if time > config.drive_cutoff_time:
            post_indices.append(len(wavefront_rows))
            post_shell_vectors.append(shell_vector)
            if best_snapshot is None or shell_energy > best_snapshot["shell_energy"]:
                best_snapshot = {
                    "time": time,
                    "shell_energy": shell_energy,
                    "energy": energy.copy(),
                    "alignment": alignment.copy(),
                }
        phase_rows.append(
            {
                "variant": config.name,
                "time": time,
                "shell_phase_coherence": shell_coherence,
                "outer_phase_coherence": outer_coherence,
                "constructive_shell_energy_fraction": constructive,
                "destructive_shell_energy_fraction": destructive,
                "shell_mean_phase": shell_phase,
                "shell_energy": shell_energy,
                "total_energy": total_energy,
                "outer_to_shell_energy_ratio": outer_energy / (shell_energy + EPSILON),
            }
        )
        modal_rows.append(
            {
                "variant": config.name,
                "time": time,
                "cubic_projection": cubic_projection,
                "shell_projection": shell_projection,
                "dominant_fft_mode": fft_summary["dominant_fft_mode"],
                "dominant_fft_fraction": fft_summary["dominant_fft_fraction"],
                "top8_fft_fraction": fft_summary["top8_fft_fraction"],
            }
        )
        wavefront_rows.append(
            {
                "variant": config.name,
                "time": time,
                "shell_window_energy": shell_energy,
                "shell_window_fraction_of_total": shell_energy / (total_energy + EPSILON),
                "active_radial_peak_radius": active_peak_radius,
                "outer_energy": outer_energy,
                "outer_to_shell_energy_ratio": outer_energy / (shell_energy + EPSILON),
                "cumulative_positive_work": cumulative_positive_work,
            }
        )

    summary = _diagnostic_summary(
        config,
        summary_row,
        phase_rows,
        modal_rows,
        wavefront_rows,
        post_indices,
        post_shell_vectors,
        positive_work_before_cutoff,
        options,
    )
    if best_snapshot is not None:
        _plot_midplane(
            diag_dir / "phase_alignment_midplane.png",
            best_snapshot["alignment"],
            f"{config.name} phase alignment at t={best_snapshot['time']:.2f}",
            cmap="coolwarm",
            vmin=-1.0,
            vmax=1.0,
        )
        _plot_midplane(
            diag_dir / "shell_energy_midplane.png",
            np.log10(best_snapshot["energy"] + EPSILON),
            f"{config.name} log shell energy at t={best_snapshot['time']:.2f}",
            cmap="magma",
        )
    return {"summary": summary, "phase_rows": phase_rows, "modal_rows": modal_rows, "wavefront_rows": wavefront_rows}


def _diagnostic_summary(
    config: Prototype3DConfig,
    summary_row: dict[str, Any],
    phase_rows: list[dict[str, Any]],
    modal_rows: list[dict[str, Any]],
    wavefront_rows: list[dict[str, Any]],
    post_indices: list[int],
    post_shell_vectors: list[np.ndarray],
    positive_work_before_cutoff: float,
    options: InterferenceDiagnostics3DOptions,
) -> dict[str, Any]:
    if not wavefront_rows:
        return {"variant": config.name}
    shell_energy = np.asarray([row["shell_window_energy"] for row in wavefront_rows], dtype=float)
    times = np.asarray([row["time"] for row in wavefront_rows], dtype=float)
    post = np.asarray(post_indices, dtype=int)
    tail = _tail_indices(post, 0.35)
    peak_idx = int(np.argmax(shell_energy))
    peak_shell = float(shell_energy[peak_idx])
    arrival_threshold = max(0.10 * peak_shell, positive_work_before_cutoff * 1.0e-8)
    arrival_candidates = np.flatnonzero(shell_energy >= arrival_threshold)
    wavefront_radius = np.asarray([row["active_radial_peak_radius"] for row in wavefront_rows], dtype=float)
    shell_outer = options.shell_window_radius + _shell_width(config, options)
    crossing_candidates = np.flatnonzero(
        (times <= config.drive_cutoff_time + 8.0)
        & (wavefront_radius <= shell_outer)
        & (shell_energy >= arrival_threshold)
    )
    phase_tail = [phase_rows[idx] for idx in tail if idx < len(phase_rows)]
    modal_tail = [modal_rows[idx] for idx in tail if idx < len(modal_rows)]
    wave_tail = [wavefront_rows[idx] for idx in tail if idx < len(wavefront_rows)]
    return {
        "variant": config.name,
        "interference_role": summary_row.get("interference_role"),
        "drive_phase_mode": config.drive_phase_mode,
        "boundary_phase_offset": config.boundary_phase_offset,
        "boundary_cubic_phase_sign": config.boundary_cubic_phase_sign,
        "boundary_random_phase_seed": config.boundary_random_phase_seed,
        "work_per_source_area": summary_row.get("work_per_source_area"),
        "positive_work_before_cutoff": positive_work_before_cutoff,
        "shell_window_radius": options.shell_window_radius,
        "shell_window_width": _shell_width(config, options),
        "shell_peak_energy": peak_shell,
        "shell_peak_time": float(times[peak_idx]),
        "shell_peak_fraction_of_work": peak_shell / (positive_work_before_cutoff + EPSILON),
        "shell_tail_retention": _mean([row["shell_window_energy"] for row in wave_tail]) / (peak_shell + EPSILON),
        "shell_tail_fraction_of_total": _mean([row["shell_window_fraction_of_total"] for row in wave_tail]),
        "tail_phase_coherence_mean": _mean([row["shell_phase_coherence"] for row in phase_tail]),
        "tail_phase_coherence_max": _max([row["shell_phase_coherence"] for row in phase_tail]),
        "tail_constructive_fraction_mean": _mean([row["constructive_shell_energy_fraction"] for row in phase_tail]),
        "tail_destructive_fraction_mean": _mean([row["destructive_shell_energy_fraction"] for row in phase_tail]),
        "tail_outer_to_shell_ratio_mean": _mean([row["outer_to_shell_energy_ratio"] for row in wave_tail]),
        "first_meaningful_shell_arrival_time": float(times[arrival_candidates[0]]) if arrival_candidates.size else None,
        "wavefront_shell_crossing_time": float(times[crossing_candidates[0]]) if crossing_candidates.size else None,
        "standing_shell_persistence": _standing_persistence(post_shell_vectors),
        "tail_cubic_projection_mean": _mean([row["cubic_projection"] for row in modal_tail]),
        "tail_shell_projection_mean": _mean([row["shell_projection"] for row in modal_tail]),
        "tail_dominant_fft_fraction_mean": _mean([row["dominant_fft_fraction"] for row in modal_tail]),
        "tail_top8_fft_fraction_mean": _mean([row["top8_fft_fraction"] for row in modal_tail]),
        "dominant_tail_fft_mode": _mode_vote([row["dominant_fft_mode"] for row in modal_tail]),
    }


def _combine_rows(control_rows: list[dict[str, Any]], diagnostic_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics = {row["variant"]: row for row in diagnostic_rows}
    combined = []
    for row in control_rows:
        combined.append({**row, **diagnostics.get(row["variant"], {})})
    return combined


def _clean_shell(row: dict[str, Any] | None, options: InterferenceDiagnostics3DOptions) -> bool:
    return (
        _shell_transport_clean(row, options)
        and float((row or {}).get("tail_phase_coherence_mean") or 0.0) >= options.min_tail_phase_coherence
        and float((row or {}).get("standing_shell_persistence") or 0.0) >= options.min_standing_persistence
    )


def _shell_transport_clean(row: dict[str, Any] | None, options: InterferenceDiagnostics3DOptions) -> bool:
    if row is None:
        return False
    return (
        float(row.get("near_shell_tail_retention") or row.get("shell_tail_retention") or 0.0) >= options.min_retention
        and float(row.get("outer_to_near_tail_energy_ratio") or row.get("tail_outer_to_shell_ratio_mean") or 999.0) <= options.max_outer_ratio
        and not bool(row.get("global_peak_in_outer_window"))
    )


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(max(rows, key=_interference_score).get("variant", "n/a"))


def _interference_score(row: dict[str, Any]) -> float:
    retention = float(row.get("near_shell_tail_retention") or row.get("shell_tail_retention") or 0.0)
    peak = float(row.get("near_shell_peak_fraction_of_work") or row.get("shell_peak_fraction_of_work") or 0.0)
    coherence = float(row.get("tail_phase_coherence_mean") or 0.0)
    standing = float(row.get("standing_shell_persistence") or 0.0)
    outer = max(float(row.get("outer_to_near_tail_energy_ratio") or row.get("tail_outer_to_shell_ratio_mean") or 999.0), 0.25)
    outer_penalty = 0.5 if bool(row.get("global_peak_in_outer_window")) else 1.0
    return retention * peak * (0.5 + coherence) * (0.5 + standing) * outer_penalty / outer


def _phase_vector(u: np.ndarray, v: np.ndarray, omega: float) -> np.ndarray:
    z = u - 1j * v / max(omega, EPSILON)
    mag = np.abs(z)
    out = np.ones_like(z, dtype=complex)
    mask = mag > EPSILON
    out[mask] = z[mask] / mag[mask]
    return out


def _weighted_phase_mean(phase_vector: np.ndarray, weights: np.ndarray) -> float:
    total = np.sum(weights)
    if total <= EPSILON:
        return 0.0
    mean = np.sum(weights * phase_vector) / total
    return float(np.angle(mean))


def _weighted_coherence(phase_vector: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= EPSILON:
        return 0.0
    return float(np.abs(np.sum(weights * phase_vector)) / total)


def _alignment(phase_vector: np.ndarray, shell_phase: float) -> np.ndarray:
    return np.real(phase_vector * np.exp(-1j * shell_phase))


def _cubic_basis(coords: dict[str, np.ndarray]) -> np.ndarray:
    x = coords["x"]
    y = coords["y"]
    z = coords["z"]
    radius = np.maximum(coords["radius"], EPSILON)
    return (x**4 + y**4 + z**4) / (radius**4) - 0.6


def _normalized_basis(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.zeros_like(values, dtype=float)
    selected = values[mask].astype(float)
    selected = selected - float(np.mean(selected))
    norm = float(np.linalg.norm(selected))
    if norm <= EPSILON:
        return out
    out[mask] = selected / norm
    return out


def _basis_projection(u: np.ndarray, basis: np.ndarray, mask: np.ndarray) -> float:
    selected = u[mask].astype(float)
    selected = selected - float(np.mean(selected))
    norm = float(np.linalg.norm(selected))
    if norm <= EPSILON:
        return 0.0
    return float(abs(np.dot(selected / norm, basis[mask])))


def _fft_summary(u: np.ndarray) -> dict[str, Any]:
    spectrum = np.abs(np.fft.fftn(u)) ** 2
    flat = spectrum.ravel()
    if flat.size <= 1:
        return {"dominant_fft_mode": "n/a", "dominant_fft_fraction": 0.0, "top8_fft_fraction": 0.0}
    flat[0] = 0.0
    total = float(np.sum(flat))
    if total <= EPSILON:
        return {"dominant_fft_mode": "n/a", "dominant_fft_fraction": 0.0, "top8_fft_fraction": 0.0}
    top_idx = int(np.argmax(flat))
    top8 = np.partition(flat, -min(8, flat.size))[-min(8, flat.size) :]
    return {
        "dominant_fft_mode": str(tuple(int(value) for value in np.unravel_index(top_idx, spectrum.shape))),
        "dominant_fft_fraction": float(flat[top_idx] / total),
        "top8_fft_fraction": float(np.sum(top8) / total),
    }


def _radial_bin_counts(radius: np.ndarray, bins: np.ndarray) -> np.ndarray:
    indices = np.clip(np.digitize(radius.ravel(), bins) - 1, 0, len(bins) - 2)
    return np.bincount(indices, minlength=len(bins) - 1).astype(float)


def _radial_sums(energy: np.ndarray, radius: np.ndarray, bins: np.ndarray) -> np.ndarray:
    indices = np.clip(np.digitize(radius.ravel(), bins) - 1, 0, len(bins) - 2)
    return np.bincount(indices, weights=energy.ravel(), minlength=len(bins) - 1).astype(float)


def _standing_persistence(vectors: list[np.ndarray]) -> float:
    if len(vectors) < 3:
        return 0.0
    stacked = np.vstack([_normalize_vector(vector) for vector in vectors])
    mean = _normalize_vector(np.mean(stacked, axis=0))
    if np.linalg.norm(mean) <= EPSILON:
        return 0.0
    return float(np.mean([_corr(row, mean) for row in stacked]))


def _normalize_vector(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float).ravel()
    values = values - float(np.mean(values))
    norm = float(np.linalg.norm(values))
    if norm <= EPSILON:
        return np.zeros_like(values)
    return values / norm


def _corr(first: np.ndarray, second: np.ndarray) -> float:
    first = _normalize_vector(first)
    second = _normalize_vector(second)
    denom = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denom <= EPSILON:
        return 0.0
    return float(np.clip(np.dot(first, second) / denom, -1.0, 1.0))


def _tail_indices(post_indices: np.ndarray, tail_fraction: float) -> np.ndarray:
    if post_indices.size == 0:
        return post_indices
    start = int(post_indices.size * max(0.0, min(0.95, 1.0 - tail_fraction)))
    return post_indices[start:]


def _shell_width(config: Prototype3DConfig, options: InterferenceDiagnostics3DOptions) -> float:
    return options.shell_window_width if options.shell_window_width is not None else options.near_shell_width_dx * config.dx


def _mean(values: list[Any]) -> float:
    parsed = [float(value) for value in values if value is not None]
    return float(np.mean(parsed)) if parsed else 0.0


def _max(values: list[Any]) -> float:
    parsed = [float(value) for value in values if value is not None]
    return float(np.max(parsed)) if parsed else 0.0


def _mode_vote(values: list[str]) -> str:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    if not counts:
        return "n/a"
    return max(counts, key=counts.get)


def _plot_midplane(path: Path, values: np.ndarray, title: str, *, cmap: str, vmin: float | None = None, vmax: float | None = None) -> None:
    mid = values.shape[0] // 2
    fig, ax = plt.subplots(figsize=(5, 4), dpi=140)
    im = ax.imshow(values[mid], origin="lower", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_title(title)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_phase_coherence(path: Path, rows: list[dict[str, Any]]) -> None:
    _plot_timeseries(path, rows, "shell_phase_coherence", "Shell Phase Coherence", "phase coherence")


def _plot_wavefront(path: Path, rows: list[dict[str, Any]], options: InterferenceDiagnostics3DOptions) -> None:
    fig, ax1 = plt.subplots(figsize=(8, 4), dpi=140)
    ax2 = ax1.twinx()
    for variant in _variants(rows):
        subset = [row for row in rows if row["variant"] == variant]
        times = [row["time"] for row in subset]
        ax1.plot(times, [row["shell_window_energy"] for row in subset], label=f"{variant} shell")
        ax2.plot(times, [row["active_radial_peak_radius"] for row in subset], linestyle="--", alpha=0.45)
    ax1.axvline(16.0, color="black", linestyle=":", linewidth=1.0)
    shell_width = options.shell_window_width if options.shell_window_width is not None else options.near_shell_width_dx * (40.0 / float(max(options.grid_size - 1, 1)))
    ax2.axhspan(options.shell_window_radius, options.shell_window_radius + shell_width, color="gray", alpha=0.08)
    ax1.set_xlabel("time")
    ax1.set_ylabel("shell-window energy")
    ax2.set_ylabel("active radial peak radius")
    ax1.set_title("3D shell energy and inward wavefront proxy")
    ax1.grid(True, alpha=0.25)
    ax1.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_modal(path: Path, rows: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    for variant in _variants(rows):
        subset = [row for row in rows if row["variant"] == variant]
        ax.plot([row["time"] for row in subset], [row["cubic_projection"] for row in subset], label=f"{variant} cubic")
    ax.set_xlabel("time")
    ax.set_ylabel("projection")
    ax.set_title("Cubic modal projection proxy")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_timeseries(path: Path, rows: list[dict[str, Any]], key: str, title: str, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    for variant in _variants(rows):
        subset = [row for row in rows if row["variant"] == variant]
        ax.plot([row["time"] for row in subset], [row[key] for row in subset], label=variant)
    ax.set_xlabel("time")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _variants(rows: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        variant = str(row["variant"])
        if variant not in seen:
            seen.append(variant)
    return seen


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: InterferenceDiagnostics3DOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Interference Diagnostics: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny 41^3 neutral-lattice control for the question: is the retained shell tail a structured "
            "boundary-interference mode selected by cubic phase geometry?"
        ),
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Role | Phase | Work/Area | Near Ret | Outer/Near | Global Outer | Tail Coherence | Standing | Cubic Proj | Arrival |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('interference_role')} | "
            f"{row.get('drive_phase_mode')} | "
            f"{_format(row.get('work_per_source_area'))} | "
            f"{_format(row.get('near_shell_tail_retention'))} | "
            f"{_format(row.get('outer_to_near_tail_energy_ratio'))} | "
            f"{row.get('global_peak_in_outer_window')} | "
            f"{_format(row.get('tail_phase_coherence_mean'))} | "
            f"{_format(row.get('standing_shell_persistence'))} | "
            f"{_format(row.get('tail_cubic_projection_mean'))} | "
            f"{_format(row.get('first_meaningful_shell_arrival_time'))} |"
        )
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            "- Phase coherence uses displacement/velocity quadrature phase weighted by shell-window energy.",
            "- Constructive/destructive fractions split shell energy by alignment with the shell mean phase.",
            "- Modal decomposition is a proxy: cubic-harmonic projection plus FFT modal concentration, not a full lattice eigenbasis solve.",
            "- Wavefront analysis tracks the active-domain radial energy peak and shell-window arrival time.",
            "- Standing persistence is the mean correlation of late-tail shell energy maps with their late-tail mean pattern.",
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Files",
            "",
            "- `interference_diagnostics_summary.csv`",
            "- `phase_coherence_timeseries.csv`",
            "- `modal_projection_timeseries.csv`",
            "- `wavefront_timeseries.csv`",
            "- `phase_coherence_plot.png`",
            "- `modal_projection_plot.png`",
            "- `wavefront_shell_energy_plot.png`",
            "- `interference_diagnostics/<variant>/phase_alignment_midplane.png`",
            "- `interference_diagnostics/<variant>/shell_energy_midplane.png`",
            "- `prototype_3d_summary.csv`",
            "- `prototype_3d_summary.json`",
            f"- failure-mode audit report: `{audit['report_path']}`",
            "",
            "## Next Step",
            "",
            _next_step(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "structured_boundary_interference_supported":
        return "Same-work phase randomization disrupted the clean retained shell while the cubic reference kept coherent standing-shell structure. This supports, but does not yet prove, a structured boundary-interference mechanism."
    if label == "interference_supported_standing_weak":
        return "Same-work phase randomization disrupted the shell and removed phase coherence, but the standing-shell persistence metric is below threshold. This supports boundary-interference as central, with a persistence caveat."
    if label == "phase_randomization_survives":
        return "A scrambled phase control also retained a clean shell tail, so cubic-phase interference is not isolated as the mechanism."
    if label == "phase_coherence_not_distinct":
        return "The cubic reference did not show enough coherence lift over random controls. Treat interference as unproven."
    if label == "reference_not_reproduced":
        return "The reference failed in the neutral-lattice rerun; resolve reproducibility before interpreting phase diagnostics."
    return "The interference diagnostics are mixed. Keep claims conservative and add only one targeted negative control if needed."


def _next_step(classification: dict[str, Any]) -> str:
    if classification["label"] == "structured_boundary_interference_supported":
        return "Run one repeat/half-dt confirmation of the neutral cubic reference plus one random-phase negative control before strengthening the claim."
    if classification["label"] == "interference_supported_standing_weak":
        return "Repeat only the neutral cubic reference and one random-phase control with denser post-cutoff snapshots to verify standing-shell persistence."
    if classification["label"] == "phase_randomization_survives":
        return "Inspect whether the random-phase retained shell has the same modal fingerprint; do not claim cubic-phase selection yet."
    return "Stay at 41^3 and resolve the phase-control ambiguity before any broad 3D work."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "interference_classification",
        "interference_role",
        "grid_size",
        "dx",
        "dt",
        "drive_phase_mode",
        "boundary_phase_offset",
        "boundary_cubic_phase_sign",
        "boundary_random_phase_seed",
        "work_per_source_area",
        "positive_work_before_cutoff",
        "near_shell_peak_fraction_of_work",
        "near_shell_tail_retention",
        "outer_to_near_tail_energy_ratio",
        "global_peak_in_outer_window",
        "shell_window_radius",
        "shell_window_width",
        "shell_peak_energy",
        "shell_peak_time",
        "shell_peak_fraction_of_work",
        "shell_tail_retention",
        "shell_tail_fraction_of_total",
        "tail_phase_coherence_mean",
        "tail_phase_coherence_max",
        "tail_constructive_fraction_mean",
        "tail_destructive_fraction_mean",
        "tail_outer_to_shell_ratio_mean",
        "first_meaningful_shell_arrival_time",
        "wavefront_shell_crossing_time",
        "standing_shell_persistence",
        "tail_cubic_projection_mean",
        "tail_shell_projection_mean",
        "tail_dominant_fft_fraction_mean",
        "tail_top8_fft_fraction_mean",
        "dominant_tail_fft_mode",
        "path",
    ]


def _phase_fields() -> list[str]:
    return [
        "variant",
        "time",
        "shell_phase_coherence",
        "outer_phase_coherence",
        "constructive_shell_energy_fraction",
        "destructive_shell_energy_fraction",
        "shell_mean_phase",
        "shell_energy",
        "total_energy",
        "outer_to_shell_energy_ratio",
    ]


def _modal_fields() -> list[str]:
    return [
        "variant",
        "time",
        "cubic_projection",
        "shell_projection",
        "dominant_fft_mode",
        "dominant_fft_fraction",
        "top8_fft_fraction",
    ]


def _wavefront_fields() -> list[str]:
    return [
        "variant",
        "time",
        "shell_window_energy",
        "shell_window_fraction_of_total",
        "active_radial_peak_radius",
        "outer_energy",
        "outer_to_shell_energy_ratio",
        "cumulative_positive_work",
    ]
