"""Heuristics for ranking unusual localization behavior."""

from __future__ import annotations

from typing import Any

import numpy as np

from .config import SimulationConfig
from .lattice import Lattice2D
from .mode_diagnostics import energy_shape_metrics


EPSILON = 1e-12


def summarize_run(
    run_id: str,
    config: SimulationConfig,
    samples: list[dict[str, Any]],
    best_energy_density: np.ndarray,
) -> dict[str, Any]:
    arrays = _arrays(samples)
    best_idx = int(np.argmax(arrays["energy_well_ratio"])) if arrays["time"].size else 0
    baseline_slice = _baseline_slice(arrays["time"], config.driver.drive_cutoff_time)

    best_ratio = float(arrays["energy_well_ratio"][best_idx])
    baseline_ratio = float(np.median(arrays["energy_well_ratio"][baseline_slice])) if np.any(baseline_slice) else 0.0
    best_time = float(arrays["time"][best_idx])

    retention_score = _retention_score(arrays["time"], arrays["core_energy"], config.driver.drive_cutoff_time)
    localization_score = float(np.max(arrays["localization_index"]))
    baseline_loc = float(np.median(arrays["localization_index"][baseline_slice])) if np.any(baseline_slice) else 0.0
    amplitude_ratio = float(np.max(arrays["center_to_surround_amplitude_ratio"]))
    core_fraction = _core_fraction(arrays["core_energy"], arrays["total_energy"])
    spectral_peak = float(arrays["spectral_peak_frequency"][-1]) if arrays["time"].size else 0.0
    spectral_purity = float(arrays["spectral_purity"][-1]) if arrays["time"].size else 0.0
    q_like_decay = float(arrays["q_like_decay"][-1]) if arrays["time"].size else 0.0
    ring_ratio = _ring_score(best_energy_density, config)
    shape_metrics = energy_shape_metrics(best_energy_density, config)
    rotation_score = _rotation_score(arrays, config)
    breathing_score = _breathing_score(arrays["time"], arrays["core_energy"], config.driver.drive_cutoff_time)
    threshold_score = _threshold_score(arrays["core_energy"], config) if core_fraction > 0.02 else 0.0

    labels: list[str] = []
    if best_ratio > max(1.25, baseline_ratio * 2.5):
        labels.append("energy_well_ratio_spike")
    if retention_score > 0.22 and core_fraction > 0.03:
        labels.append("post_drive_core_retention")
    if localization_score > max(4.0, baseline_loc * 1.7) and (best_ratio > 0.05 or amplitude_ratio > 1.5):
        labels.append("localization_index_spike")
    if amplitude_ratio > 2.5 and core_fraction > 0.03:
        labels.append("central_amplitude_dominance")
    if spectral_purity > 0.28 and spectral_peak > 0.0 and core_fraction > 0.04:
        labels.append("clean_core_resonance")
    if breathing_score > 0.0:
        labels.append("breathing_core_envelope")
    if ring_ratio > 0.0:
        labels.append("ring_energy_pattern")
    if rotation_score > 0.0:
        labels.append("rotating_energy_signature")
    if threshold_score > 0.0:
        labels.append("nonlinear_threshold_jump")

    score = _anomaly_score(
        best_ratio=best_ratio,
        retention_score=retention_score,
        localization_score=localization_score,
        amplitude_ratio=amplitude_ratio,
        spectral_purity=spectral_purity,
        breathing_score=breathing_score,
        ring_score=ring_ratio,
        rotation_score=rotation_score,
        threshold_score=threshold_score,
        core_fraction=core_fraction,
    )

    return {
        "run_id": run_id,
        "best_energy_well_ratio": best_ratio,
        "time_of_best_event": best_time,
        "baseline_energy_well_ratio": baseline_ratio,
        "retention_score": retention_score,
        "localization_score": localization_score,
        "max_center_to_surround_amplitude_ratio": amplitude_ratio,
        "max_core_energy_fraction": core_fraction,
        "spectral_peak_frequency": spectral_peak,
        "spectral_purity": spectral_purity,
        "q_like_decay": q_like_decay,
        "ring_score": ring_ratio,
        "best_frame_spatial_entropy": shape_metrics["spatial_entropy"],
        "best_frame_spatial_entropy_normalized": shape_metrics["spatial_entropy_normalized"],
        "best_frame_participation_fraction": shape_metrics["participation_fraction"],
        "best_frame_radial_entropy_normalized": shape_metrics["radial_entropy_normalized"],
        "best_frame_radial_peak_radius": shape_metrics["radial_peak_radius"],
        "best_frame_radial_concentration": shape_metrics["radial_concentration"],
        "rotation_score": rotation_score,
        "breathing_score": breathing_score,
        "threshold_score": threshold_score,
        "anomaly_score": score,
        "detected_event_labels": labels,
        "plain_language_interpretation": _interpret(labels),
    }


def _arrays(samples: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    keys = [
        "time",
        "core_energy",
        "total_energy",
        "energy_well_ratio",
        "localization_index",
        "center_to_surround_amplitude_ratio",
        "spectral_peak_frequency",
        "spectral_purity",
        "q_like_decay",
        "angular_energy_phase",
        "angular_coherence",
    ]
    return {key: np.array([row[key] for row in samples], dtype=float) for key in keys}


def _core_fraction(core_energy: np.ndarray, total_energy: np.ndarray) -> float:
    valid = total_energy > EPSILON
    if not np.any(valid):
        return 0.0
    return float(np.max(core_energy[valid] / (total_energy[valid] + EPSILON)))


def _baseline_slice(times: np.ndarray, cutoff: float | None) -> np.ndarray:
    if times.size == 0:
        return np.array([], dtype=bool)
    if cutoff is None:
        return times <= np.percentile(times, 25)
    return times <= min(cutoff * 0.4, np.percentile(times, 30))


def _retention_score(times: np.ndarray, core_energy: np.ndarray, cutoff: float | None) -> float:
    if times.size == 0:
        return 0.0
    if cutoff is None:
        return 0.0
    pre = core_energy[times <= cutoff]
    post = core_energy[times > cutoff]
    if pre.size == 0 or post.size == 0:
        return 0.0
    reference = max(float(np.max(pre)), float(np.max(post)), EPSILON)
    tail_start = max(0, int(post.size * 0.35))
    retained = float(np.mean(post[tail_start:]) / reference)
    return float(np.clip(retained, 0.0, 1.0))


def _breathing_score(times: np.ndarray, core_energy: np.ndarray, cutoff: float | None) -> float:
    if core_energy.size < 12:
        return 0.0
    if cutoff is not None:
        mask = times > cutoff * 0.35
        series = core_energy[mask]
    else:
        series = core_energy
    if series.size < 12 or np.max(series) <= EPSILON:
        return 0.0

    centered = series - np.mean(series)
    if np.std(centered) <= EPSILON:
        return 0.0

    peaks = np.where((series[1:-1] > series[:-2]) & (series[1:-1] > series[2:]))[0] + 1
    strong_peaks = peaks[series[peaks] > np.percentile(series, 70)]
    if strong_peaks.size < 3:
        return 0.0

    intervals = np.diff(strong_peaks)
    if intervals.size == 0 or np.mean(intervals) <= 0:
        return 0.0
    regularity = float(np.std(intervals) / np.mean(intervals))
    envelope_depth = float((np.percentile(series, 90) - np.percentile(series, 20)) / (np.max(series) + EPSILON))
    if regularity < 0.55 and envelope_depth > 0.25:
        return float(np.clip(envelope_depth * (1.0 - regularity), 0.0, 1.0))
    return 0.0


def _ring_score(best_energy_density: np.ndarray, config: SimulationConfig) -> float:
    masks = Lattice2D._build_masks(config)
    core = masks.core
    ring = masks.ring
    outer = masks.outer
    if not np.any(core) or not np.any(ring) or not np.any(outer):
        return 0.0
    core_mean = float(np.mean(best_energy_density[core]))
    ring_mean = float(np.mean(best_energy_density[ring]))
    outer_mean = float(np.mean(best_energy_density[outer]))
    if ring_mean > core_mean * 0.8 and ring_mean > outer_mean * 2.0:
        return float(np.clip(ring_mean / (max(core_mean, outer_mean) + EPSILON), 0.0, 3.0) / 3.0)
    return 0.0


def _rotation_score(arrays: dict[str, np.ndarray], config: SimulationConfig) -> float:
    if config.driver.phase_mode != "rotating":
        return 0.0
    phase = arrays["angular_energy_phase"]
    coherence = arrays["angular_coherence"]
    mask = coherence > 0.12
    if int(np.sum(mask)) < 10:
        return 0.0
    unwrapped = np.unwrap(phase[mask])
    drift = float(np.max(unwrapped) - np.min(unwrapped))
    if drift > np.pi:
        return float(np.clip(drift / (2.0 * np.pi), 0.0, 1.0))
    return 0.0


def _threshold_score(core_energy: np.ndarray, config: SimulationConfig) -> float:
    nonlinear = config.nonlinear_strength + config.defect.nonlinear_strength
    if nonlinear <= 0.0 or core_energy.size < 8:
        return 0.0
    peak = float(np.max(core_energy))
    if peak <= 1e-8:
        return 0.0
    diffs = np.abs(np.diff(core_energy))
    active_diffs = diffs[core_energy[:-1] > peak * 0.1]
    if active_diffs.size < 6:
        return 0.0
    median = float(np.median(active_diffs)) + EPSILON
    jump = float(np.max(active_diffs) / median)
    if jump > 12.0:
        return float(np.clip((jump - 12.0) / 30.0, 0.0, 1.0))
    return 0.0


def _anomaly_score(**parts: float) -> float:
    ratio_score = np.clip(np.log1p(parts["best_ratio"]) / np.log1p(8.0), 0.0, 1.0)
    core_presence = np.clip(parts["core_fraction"] * 8.0, 0.0, 1.0)
    retention = np.clip(parts["retention_score"], 0.0, 1.0) * core_presence
    localization = np.clip(parts["localization_score"] / 9.0, 0.0, 1.0) * max(ratio_score, core_presence)
    amplitude = np.clip(parts["amplitude_ratio"] / 6.0, 0.0, 1.0) * core_presence
    spectral = np.clip(parts["spectral_purity"] / 0.45, 0.0, 1.0) * core_presence
    breathing = np.clip(parts["breathing_score"], 0.0, 1.0) * core_presence
    ring = np.clip(parts["ring_score"], 0.0, 1.0)
    rotation = np.clip(parts["rotation_score"], 0.0, 1.0)
    threshold = np.clip(parts["threshold_score"], 0.0, 1.0)

    score = (
        0.23 * ratio_score
        + 0.18 * retention
        + 0.15 * localization
        + 0.14 * amplitude
        + 0.11 * spectral
        + 0.07 * breathing
        + 0.05 * ring
        + 0.04 * threshold
        + 0.03 * rotation
    )
    return float(round(100.0 * score, 3))


def _interpret(labels: list[str]) -> str:
    if not labels:
        return "No strong localization event was detected in this run; treat it as a baseline or low-interest configuration."

    sentences = []
    if "energy_well_ratio_spike" in labels:
        sentences.append("Core energy rose while outer lattice energy stayed comparatively low, suggesting localized defect resonance.")
    if "post_drive_core_retention" in labels:
        sentences.append("Core energy remained elevated after the drive shut off, suggesting high-retention artificial energy-well behavior.")
    if "breathing_core_envelope" in labels:
        sentences.append("Energy oscillated in the defect region with a repeating envelope, suggesting breathing localized energy behavior.")
    if "ring_energy_pattern" in labels:
        sentences.append("Energy concentrated in an annulus around the defect, suggesting ring-like localization around the central cavity.")
    if "rotating_energy_signature" in labels:
        sentences.append("The angular energy centroid drifted under rotating boundary phase drive, suggesting possible rotating localization.")
    if "nonlinear_threshold_jump" in labels:
        sentences.append("Core energy changed abruptly in a nonlinear run, suggesting a possible threshold response.")
    if "clean_core_resonance" in labels:
        sentences.append("The core displacement spectrum had a clear dominant peak, suggesting a coherent central resonance.")
    if "central_amplitude_dominance" in labels and not sentences:
        sentences.append("The center amplitude was much higher than nearby lattice amplitudes, suggesting central localization.")
    return " ".join(sentences)
