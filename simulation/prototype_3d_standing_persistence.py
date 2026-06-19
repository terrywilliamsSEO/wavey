"""Standing-shell persistence confirmation for neutral cubic 3D shell tails."""

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
from .prototype_3d import (
    EPSILON,
    Lattice3D,
    Prototype3DConfig,
    Prototype3DOptions,
    _calibrate_amplitude,
    _run_variant,
    _summary_fields as _prototype_summary_fields,
    _write_csv as _write_prototype_csv,
)
from .prototype_3d_audit import Prototype3DFailureAuditOptions, run_3d_failure_audit
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import (
    _boundary_config as _interference_boundary_config,
    _phase_vector,
    _shell_width,
    _threshold_like_options,
    _weighted_coherence,
    _weighted_phase_mean,
)
from .prototype_3d_source_sponge import _effective_source_area, _format, _merge_rows, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


@dataclass(frozen=True)
class StandingPersistence3DOptions:
    """Options for a tiny standing-shell persistence confirmation."""

    output_root: str = "runs"
    grid_size: int = 41
    reference_source_grid_size: int = 31
    sample_every: int = 10
    diagnostic_sample_every: int = 4
    radial_bins: int = 24
    shell_window_radius: float = 5.0
    shell_window_width: float | None = None
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    target_work_per_source_area: float | None = None
    phase_offset: float = 0.5 * float(np.pi)
    settle_after_cutoff: float = 8.0
    node_quantile: float = 0.20
    min_standing_score: float = 0.60
    min_node_antinode_stability: float = 0.55
    min_frame_similarity: float = 0.55
    min_phase_stability: float = 0.25
    min_spectral_concentration: float = 0.20


def run_3d_standing_persistence_control(
    base_config: SimulationConfig,
    *,
    options: StandingPersistence3DOptions | None = None,
) -> dict[str, Any]:
    """Run the two clean cubic variants with dense post-cutoff persistence diagnostics."""

    options = options or StandingPersistence3DOptions()
    control_id = datetime.now().strftime("standing_persistence_3d_%Y%m%d_%H%M%S")
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
                "label": "standing_persistence_3d",
                "reason": "Two-variant neutral cubic standing-shell persistence confirmation.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "standing_persistence_3d_report.md"),
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
    timeseries_rows: list[dict[str, Any]] = []
    autocorrelation_rows: list[dict[str, Any]] = []
    for row in control_rows:
        config = configs_by_variant[row["variant"]]
        diagnostics = _run_standing_diagnostics(config, root, row, options)
        diagnostic_rows.append(diagnostics["summary"])
        timeseries_rows.extend(diagnostics["timeseries"])
        autocorrelation_rows.extend(diagnostics["autocorrelation"])

    combined_rows = _combine_rows(control_rows, diagnostic_rows)
    classification = classify_standing_persistence(combined_rows, options)
    for row in combined_rows:
        row["standing_persistence_classification"] = classification["label"]

    summary_csv = root / "standing_persistence_summary.csv"
    timeseries_csv = root / "standing_persistence_timeseries.csv"
    autocorrelation_csv = root / "shell_energy_autocorrelation.csv"
    report_path = root / "standing_persistence_3d_report.md"
    _write_csv(summary_csv, combined_rows, _summary_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(autocorrelation_csv, autocorrelation_rows, _autocorrelation_fields())
    _plot_timeseries(root / "shell_pattern_similarity_plot.png", timeseries_rows, "frame_similarity_to_mean", "Shell Pattern Similarity")
    _plot_timeseries(root / "shell_phase_stability_plot.png", timeseries_rows, "shell_phase_coherence", "Shell Phase Coherence")
    _plot_autocorrelation(root / "shell_energy_autocorrelation_plot.png", autocorrelation_rows)
    _write_report(report_path, control_id, combined_rows, classification, options, audit)
    save_json(
        root / "standing_persistence_3d_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": combined_rows,
            "summary_csv": str(summary_csv),
            "timeseries_csv": str(timeseries_csv),
            "autocorrelation_csv": str(autocorrelation_csv),
            "report_path": str(report_path),
            "audit_report_path": audit["report_path"],
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": combined_rows,
        "summary_csv": str(summary_csv),
        "timeseries_csv": str(timeseries_csv),
        "autocorrelation_csv": str(autocorrelation_csv),
        "report_path": str(report_path),
        "audit_report_path": audit["report_path"],
        "path": str(root),
    }


def classify_standing_persistence(
    rows: list[dict[str, Any]],
    options: StandingPersistence3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether post-cutoff shell patterns are standing or merely passing through."""

    options = options or StandingPersistence3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No standing-persistence rows were available.", "checks": {}}
    passing = [row for row in rows if _standing_pass(row, options)]
    checks = {
        row["variant"]: {
            "standing_score": row.get("standing_score"),
            "node_antinode_stability": row.get("node_antinode_stability"),
            "frame_similarity_mean": row.get("frame_similarity_to_mean_mean"),
            "phase_stability": row.get("radial_shell_phase_stability"),
            "spectral_concentration": row.get("shell_energy_spectral_concentration"),
        }
        for row in rows
    }
    if len(passing) == len(rows):
        return {
            "label": "standing_shell_persistence_confirmed",
            "reason": "Both clean cubic variants preserved settled post-cutoff node/antinode structure, shell phase stability, frame similarity, and shell-energy spectral concentration.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if passing:
        return {
            "label": "standing_persistence_mixed",
            "reason": f"Only {', '.join(row['variant'] for row in passing)} passed the settled standing-shell criteria.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if any(
        float(row.get("radial_shell_phase_stability") or 0.0) >= options.min_phase_stability
        or float(row.get("frame_to_frame_similarity_mean") or 0.0) >= options.min_frame_similarity
        or float(row.get("shell_energy_spectral_concentration") or 0.0) >= options.min_spectral_concentration
        for row in rows
    ):
        return {
            "label": "coherent_transport_not_standing",
            "reason": "The cubic variants retained temporal coherence in the shell window, but settled node/antinode and frame-to-mean spatial metrics did not pass the standing-shell criteria.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "standing_persistence_not_supported",
        "reason": "The settled post-cutoff shell windows did not preserve a stable spatial or phase pattern.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: StandingPersistence3DOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    return [
        _interference_boundary_config("neutral_cubic_sign_flip_reference", base, options, source_width, "cubic", cubic_sign=-1.0),
        _interference_boundary_config(
            "neutral_cubic_phase_offset",
            base,
            options,
            source_width,
            "cubic",
            cubic_sign=-1.0,
            phase_offset=options.phase_offset,
        ),
    ]


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    reference_config: Prototype3DConfig,
    options: StandingPersistence3DOptions,
    target_work_per_area: float,
) -> None:
    summary["standing_role"] = "cubic_reference" if config.name == "neutral_cubic_sign_flip_reference" else "cubic_phase_offset_control"
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    original_sponge_strength = reference_config.sponge_strength / max(options.sponge_strength_multiplier, EPSILON)
    summary["sponge_strength_multiplier_vs_original"] = config.sponge_strength / max(original_sponge_strength, EPSILON)
    summary["source_width_physical_reference"] = reference_config.boundary_source_width
    summary["target_reference_work_per_source_area"] = target_work_per_area
    summary["calibration_source_grid_size"] = options.reference_source_grid_size


def _run_standing_diagnostics(
    config: Prototype3DConfig,
    root: Path,
    summary_row: dict[str, Any],
    options: StandingPersistence3DOptions,
) -> dict[str, Any]:
    diag_dir = root / "standing_persistence" / config.name
    diag_dir.mkdir(parents=True, exist_ok=True)
    lattice = Lattice3D(config)
    radius = lattice.coords["radius"]
    shell_width = _shell_width(config, options)
    shell_mask = (radius > options.shell_window_radius) & (radius <= options.shell_window_radius + shell_width)
    omega = 2.0 * np.pi * max(config.drive_frequency, EPSILON)
    settle_time = config.drive_cutoff_time + options.settle_after_cutoff
    frames: list[np.ndarray] = []
    phases: list[float] = []
    phase_coherence: list[float] = []
    shell_energy: list[float] = []
    times: list[float] = []
    timeseries: list[dict[str, Any]] = []

    for step in range(config.steps):
        time = step * config.dt
        lattice.step(time, config.dt)
        if time < settle_time:
            continue
        if step % max(1, options.diagnostic_sample_every) != 0 and step != config.steps - 1:
            continue
        energy = lattice.energy_density()
        shell_values = energy[shell_mask].astype(float).ravel()
        phase_vector = _phase_vector(lattice.u, lattice.v, omega)
        shell_phase = _weighted_phase_mean(phase_vector[shell_mask], energy[shell_mask])
        coherence = _weighted_coherence(phase_vector[shell_mask], energy[shell_mask])
        frames.append(shell_values)
        phases.append(shell_phase)
        phase_coherence.append(coherence)
        shell_energy.append(float(np.sum(shell_values)))
        times.append(time)

    if not frames:
        return {"summary": {"variant": config.name}, "timeseries": [], "autocorrelation": []}

    frame_matrix = np.vstack(frames)
    mean_pattern = np.mean(frame_matrix, axis=0)
    antinode_mask, node_mask = _node_antinode_masks(mean_pattern, options)
    antinode_jaccards = []
    node_jaccards = []
    similarity_to_mean = []
    frame_to_frame = []
    node_antinode_contrast = []
    for idx, frame in enumerate(frame_matrix):
        frame_antinode, frame_node = _node_antinode_masks(frame, options)
        antinode_jaccards.append(_jaccard(frame_antinode, antinode_mask))
        node_jaccards.append(_jaccard(frame_node, node_mask))
        similarity_to_mean.append(_corr(frame, mean_pattern))
        if idx > 0:
            frame_to_frame.append(_corr(frame_matrix[idx - 1], frame))
        node_mean = float(np.mean(frame[node_mask])) if np.any(node_mask) else 0.0
        antinode_mean = float(np.mean(frame[antinode_mask])) if np.any(antinode_mask) else 0.0
        node_antinode_contrast.append((antinode_mean - node_mean) / (abs(antinode_mean) + abs(node_mean) + EPSILON))

    unwrapped_phase = np.unwrap(np.asarray(phases, dtype=float))
    radial_shell_phase_stability = float(abs(np.mean(np.exp(1j * np.asarray(phases, dtype=float)))))
    autocorr_rows, autocorr_summary = _autocorrelation_rows(config.name, shell_energy, config.dt * options.diagnostic_sample_every)
    spectral = _spectral_summary(shell_energy, config.dt * options.diagnostic_sample_every)
    frame_similarity_mean = _mean(similarity_to_mean)
    frame_to_frame_mean = _mean(frame_to_frame)
    node_antinode_stability = 0.5 * (_mean(antinode_jaccards) + _mean(node_jaccards))
    pattern_persistence = frame_similarity_mean
    standing_score = float(
        np.mean(
            [
                max(0.0, frame_similarity_mean),
                max(0.0, frame_to_frame_mean),
                max(0.0, node_antinode_stability),
                max(0.0, radial_shell_phase_stability),
                max(0.0, spectral["shell_energy_spectral_concentration"]),
            ]
        )
    )

    for idx, time in enumerate(times):
        timeseries.append(
            {
                "variant": config.name,
                "time": time,
                "shell_energy": shell_energy[idx],
                "shell_phase": phases[idx],
                "shell_phase_coherence": phase_coherence[idx],
                "frame_similarity_to_mean": similarity_to_mean[idx],
                "frame_to_frame_similarity": frame_to_frame[idx - 1] if idx > 0 else None,
                "antinode_jaccard": antinode_jaccards[idx],
                "node_jaccard": node_jaccards[idx],
                "node_antinode_contrast": node_antinode_contrast[idx],
            }
        )

    _plot_shell_pattern(diag_dir / "mean_shell_pattern.png", mean_pattern, shell_mask, radius.shape, "Mean settled shell pattern")
    _plot_shell_pattern(diag_dir / "antinode_mask.png", antinode_mask.astype(float), shell_mask, radius.shape, "Settled antinode mask")
    summary = {
        "variant": config.name,
        "standing_role": summary_row.get("standing_role"),
        "settle_time": settle_time,
        "settled_frame_count": len(frames),
        "shell_window_radius": options.shell_window_radius,
        "shell_window_width": shell_width,
        "work_per_source_area": summary_row.get("work_per_source_area"),
        "positive_work_before_cutoff": summary_row.get("positive_work_before_cutoff"),
        "mean_settled_shell_energy": _mean(shell_energy),
        "shell_energy_cv": _cv(shell_energy),
        "shell_energy_autocorrelation_lag1": autocorr_summary["lag1"],
        "shell_energy_autocorrelation_peak": autocorr_summary["peak"],
        "shell_energy_autocorrelation_peak_lag_time": autocorr_summary["peak_lag_time"],
        **spectral,
        "radial_shell_phase_stability": radial_shell_phase_stability,
        "radial_shell_phase_range": float(np.max(unwrapped_phase) - np.min(unwrapped_phase)) if unwrapped_phase.size else 0.0,
        "tail_phase_coherence_mean": _mean(phase_coherence),
        "tail_phase_coherence_min": _min(phase_coherence),
        "node_antinode_stability": node_antinode_stability,
        "antinode_jaccard_mean": _mean(antinode_jaccards),
        "node_jaccard_mean": _mean(node_jaccards),
        "node_antinode_contrast_mean": _mean(node_antinode_contrast),
        "frame_similarity_to_mean_mean": frame_similarity_mean,
        "frame_similarity_to_mean_min": _min(similarity_to_mean),
        "frame_to_frame_similarity_mean": frame_to_frame_mean,
        "frame_to_frame_similarity_min": _min(frame_to_frame),
        "pattern_persistence": pattern_persistence,
        "standing_score": standing_score,
    }
    return {"summary": summary, "timeseries": timeseries, "autocorrelation": autocorr_rows}


def _standing_pass(row: dict[str, Any], options: StandingPersistence3DOptions) -> bool:
    return (
        float(row.get("standing_score") or 0.0) >= options.min_standing_score
        and float(row.get("node_antinode_stability") or 0.0) >= options.min_node_antinode_stability
        and float(row.get("frame_similarity_to_mean_mean") or 0.0) >= options.min_frame_similarity
        and float(row.get("frame_to_frame_similarity_mean") or 0.0) >= options.min_frame_similarity
        and float(row.get("radial_shell_phase_stability") or 0.0) >= options.min_phase_stability
        and float(row.get("shell_energy_spectral_concentration") or 0.0) >= options.min_spectral_concentration
    )


def _combine_rows(control_rows: list[dict[str, Any]], diagnostic_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics = {row["variant"]: row for row in diagnostic_rows}
    return [{**row, **diagnostics.get(row["variant"], {})} for row in control_rows]


def _node_antinode_masks(values: np.ndarray, options: StandingPersistence3DOptions) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, dtype=float).ravel()
    if values.size == 0:
        return np.zeros(0, dtype=bool), np.zeros(0, dtype=bool)
    q = min(max(options.node_quantile, 0.05), 0.45)
    low = float(np.quantile(values, q))
    high = float(np.quantile(values, 1.0 - q))
    return values >= high, values <= low


def _jaccard(first: np.ndarray, second: np.ndarray) -> float:
    union = np.count_nonzero(first | second)
    if union == 0:
        return 0.0
    return float(np.count_nonzero(first & second) / union)


def _corr(first: np.ndarray, second: np.ndarray) -> float:
    first = np.asarray(first, dtype=float).ravel()
    second = np.asarray(second, dtype=float).ravel()
    if first.size == 0 or second.size == 0 or first.size != second.size:
        return 0.0
    first = first - float(np.mean(first))
    second = second - float(np.mean(second))
    denom = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denom <= EPSILON:
        return 0.0
    return float(np.clip(np.dot(first, second) / denom, -1.0, 1.0))


def _autocorrelation_rows(variant: str, values: list[float], dt: float) -> tuple[list[dict[str, Any]], dict[str, float]]:
    data = np.asarray(values, dtype=float)
    if data.size < 3:
        return [], {"lag1": 0.0, "peak": 0.0, "peak_lag_time": 0.0}
    data = data - float(np.mean(data))
    denom = float(np.dot(data, data))
    rows = []
    for lag in range(1, min(data.size, 80)):
        corr = float(np.dot(data[:-lag], data[lag:]) / (denom + EPSILON))
        rows.append({"variant": variant, "lag_index": lag, "lag_time": lag * dt, "autocorrelation": corr})
    lag1 = rows[0]["autocorrelation"] if rows else 0.0
    positive = [row for row in rows if row["lag_index"] > 1]
    peak = max(positive, key=lambda row: row["autocorrelation"], default={"autocorrelation": 0.0, "lag_time": 0.0})
    return rows, {"lag1": lag1, "peak": float(peak["autocorrelation"]), "peak_lag_time": float(peak["lag_time"])}


def _spectral_summary(values: list[float], dt: float) -> dict[str, float]:
    data = np.asarray(values, dtype=float)
    if data.size < 6:
        return {
            "shell_energy_spectral_concentration": 0.0,
            "shell_energy_top3_spectral_fraction": 0.0,
            "shell_energy_dominant_period": 0.0,
        }
    data = data - float(np.mean(data))
    power = np.abs(np.fft.rfft(data)) ** 2
    freqs = np.fft.rfftfreq(data.size, d=dt)
    power[0] = 0.0
    total = float(np.sum(power))
    if total <= EPSILON:
        return {
            "shell_energy_spectral_concentration": 0.0,
            "shell_energy_top3_spectral_fraction": 0.0,
            "shell_energy_dominant_period": 0.0,
        }
    peak_idx = int(np.argmax(power))
    top_count = min(3, power.size)
    top3 = np.partition(power, -top_count)[-top_count:]
    dominant_freq = float(freqs[peak_idx])
    return {
        "shell_energy_spectral_concentration": float(power[peak_idx] / total),
        "shell_energy_top3_spectral_fraction": float(np.sum(top3) / total),
        "shell_energy_dominant_period": 1.0 / dominant_freq if dominant_freq > EPSILON else 0.0,
    }


def _plot_shell_pattern(path: Path, shell_values: np.ndarray, shell_mask: np.ndarray, shape: tuple[int, ...], title: str) -> None:
    volume = np.zeros(shape, dtype=float)
    volume[shell_mask] = shell_values
    mid = shape[0] // 2
    fig, ax = plt.subplots(figsize=(5, 4), dpi=140)
    im = ax.imshow(volume[mid], origin="lower", cmap="magma")
    ax.set_title(title)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_timeseries(path: Path, rows: list[dict[str, Any]], key: str, title: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    for variant in _variants(rows):
        subset = [row for row in rows if row["variant"] == variant]
        ax.plot([row["time"] for row in subset], [row.get(key) or 0.0 for row in subset], label=variant)
    ax.set_xlabel("time")
    ax.set_ylabel(key)
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_autocorrelation(path: Path, rows: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    for variant in _variants(rows):
        subset = [row for row in rows if row["variant"] == variant]
        ax.plot([row["lag_time"] for row in subset], [row["autocorrelation"] for row in subset], label=variant)
    ax.set_xlabel("lag time")
    ax.set_ylabel("autocorrelation")
    ax.set_title("Settled Shell Energy Autocorrelation")
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


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(max(rows, key=lambda row: float(row.get("standing_score") or 0.0)).get("variant", "n/a"))


def _mean(values: list[Any]) -> float:
    parsed = [float(value) for value in values if value is not None]
    return float(np.mean(parsed)) if parsed else 0.0


def _min(values: list[Any]) -> float:
    parsed = [float(value) for value in values if value is not None]
    return float(np.min(parsed)) if parsed else 0.0


def _cv(values: list[Any]) -> float:
    parsed = np.asarray([float(value) for value in values if value is not None], dtype=float)
    if parsed.size == 0:
        return 0.0
    return float(np.std(parsed) / (abs(np.mean(parsed)) + EPSILON))


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: StandingPersistence3DOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Standing-Shell Persistence: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny two-variant confirmation for the question: does the shell-window pattern remain spatially "
            "organized after cutoff, or is it just a coherent transport tail passing through?"
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
        "| Variant | Standing | Node/Anti | To Mean | F2F | Phase Stability | Spectral | Lag1 AC | Period | Frames |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('standing_score'))} | "
            f"{_format(row.get('node_antinode_stability'))} | "
            f"{_format(row.get('frame_similarity_to_mean_mean'))} | "
            f"{_format(row.get('frame_to_frame_similarity_mean'))} | "
            f"{_format(row.get('radial_shell_phase_stability'))} | "
            f"{_format(row.get('shell_energy_spectral_concentration'))} | "
            f"{_format(row.get('shell_energy_autocorrelation_lag1'))} | "
            f"{_format(row.get('shell_energy_dominant_period'))} | "
            f"{row.get('settled_frame_count')} |"
        )
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            "- Node/antinode stability uses settled-frame overlap with the mean settled shell pattern.",
            "- Radial shell phase stability uses the mean resultant length of shell-window quadrature phase after settling.",
            "- Frame-to-frame and frame-to-mean similarities are shell-window energy-pattern correlations after settling.",
            "- Spectral concentration is the dominant FFT power fraction of the settled shell-window energy time series.",
            "- Standing score averages frame-to-mean, frame-to-frame, node/antinode stability, phase stability, and spectral concentration.",
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Files",
            "",
            "- `standing_persistence_summary.csv`",
            "- `standing_persistence_timeseries.csv`",
            "- `shell_energy_autocorrelation.csv`",
            "- `shell_pattern_similarity_plot.png`",
            "- `shell_phase_stability_plot.png`",
            "- `shell_energy_autocorrelation_plot.png`",
            "- `standing_persistence/<variant>/mean_shell_pattern.png`",
            "- `standing_persistence/<variant>/antinode_mask.png`",
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
    if label == "standing_shell_persistence_confirmed":
        return "The settled post-cutoff shell pattern remains spatially organized in both cubic variants. This supports standing-shell language for the cubic boundary-interference family."
    if label == "standing_persistence_mixed":
        return "Only one cubic variant preserves settled spatial organization. Treat standing-shell persistence as phase-condition dependent."
    if label == "coherent_transport_not_standing":
        return "The variants retain temporal coherence in the shell window, but settled spatial-pattern metrics do not support a standing shell. Treat the signal as coherent transport until a stricter repeat says otherwise."
    return "The settled post-cutoff shell pattern did not preserve stable organization under these criteria."


def _next_step(classification: dict[str, Any]) -> str:
    if classification["label"] == "standing_shell_persistence_confirmed":
        return "Run one half-dt repeat of the stronger cubic variant before strengthening the standing-shell claim."
    if classification["label"] == "standing_persistence_mixed":
        return "Repeat the passing cubic variant once, with the same dense settled diagnostics, before interpreting phase dependence."
    return "Do not broaden. Inspect whether the tail is a coherent transport packet, and avoid standing-shell language for now."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "standing_persistence_classification",
        "standing_role",
        "grid_size",
        "dx",
        "dt",
        "drive_phase_mode",
        "boundary_phase_offset",
        "boundary_cubic_phase_sign",
        "work_per_source_area",
        "positive_work_before_cutoff",
        "near_shell_tail_retention",
        "outer_to_near_tail_energy_ratio",
        "global_peak_in_outer_window",
        "settle_time",
        "settled_frame_count",
        "shell_window_radius",
        "shell_window_width",
        "mean_settled_shell_energy",
        "shell_energy_cv",
        "shell_energy_autocorrelation_lag1",
        "shell_energy_autocorrelation_peak",
        "shell_energy_autocorrelation_peak_lag_time",
        "shell_energy_spectral_concentration",
        "shell_energy_top3_spectral_fraction",
        "shell_energy_dominant_period",
        "radial_shell_phase_stability",
        "radial_shell_phase_range",
        "tail_phase_coherence_mean",
        "tail_phase_coherence_min",
        "node_antinode_stability",
        "antinode_jaccard_mean",
        "node_jaccard_mean",
        "node_antinode_contrast_mean",
        "frame_similarity_to_mean_mean",
        "frame_similarity_to_mean_min",
        "frame_to_frame_similarity_mean",
        "frame_to_frame_similarity_min",
        "pattern_persistence",
        "standing_score",
        "path",
    ]


def _timeseries_fields() -> list[str]:
    return [
        "variant",
        "time",
        "shell_energy",
        "shell_phase",
        "shell_phase_coherence",
        "frame_similarity_to_mean",
        "frame_to_frame_similarity",
        "antinode_jaccard",
        "node_jaccard",
        "node_antinode_contrast",
    ]


def _autocorrelation_fields() -> list[str]:
    return ["variant", "lag_index", "lag_time", "autocorrelation"]
