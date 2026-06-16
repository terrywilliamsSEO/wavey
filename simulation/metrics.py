"""Metric extraction and CSV persistence."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np

from .config import SimulationConfig
from .lattice import Lattice2D
from .mode_diagnostics import spatial_distribution_metrics


EPSILON = 1e-12


METRIC_FIELDS = [
    "step",
    "time",
    "core_energy",
    "outer_lattice_energy",
    "total_energy",
    "energy_well_ratio",
    "max_amplitude",
    "max_amplitude_location",
    "max_amplitude_row",
    "max_amplitude_col",
    "localization_index",
    "spatial_entropy",
    "spatial_entropy_normalized",
    "participation_fraction",
    "core_retention_after_drive_cutoff",
    "q_like_decay",
    "spectral_peak_frequency",
    "spectral_purity",
    "center_to_surround_amplitude_ratio",
    "ring_energy_ratio",
    "angular_energy_phase",
    "angular_coherence",
]


def sample_metrics(step: int, time: float, lattice: Lattice2D, energy: np.ndarray) -> dict[str, Any]:
    masks = lattice.masks
    core_energy = float(np.sum(energy[masks.core]))
    outer_energy = float(np.sum(energy[masks.outer]))
    total_energy = core_energy + outer_energy
    ratio = core_energy / (outer_energy + EPSILON)

    abs_u = np.abs(lattice.u)
    max_index = np.unravel_index(int(np.argmax(abs_u)), lattice.shape)
    max_amp = float(abs_u[max_index])

    if total_energy > EPSILON:
        localization = float(energy.size * np.sum(energy ** 2) / ((np.sum(energy) ** 2) + EPSILON))
    else:
        localization = 0.0
    spatial_metrics = spatial_distribution_metrics(energy)

    core_amp = float(np.mean(abs_u[masks.core])) if np.any(masks.core) else 0.0
    surround_mask = masks.ring if np.any(masks.ring) else masks.outer
    surround_amp = float(np.mean(abs_u[surround_mask])) if np.any(surround_mask) else 0.0
    amp_ratio = core_amp / (surround_amp + EPSILON)

    core_mean_e = float(np.mean(energy[masks.core])) if np.any(masks.core) else 0.0
    ring_mean_e = float(np.mean(energy[masks.ring])) if np.any(masks.ring) else 0.0
    ring_ratio = ring_mean_e / (core_mean_e + EPSILON)

    phase, coherence = angular_energy_phase(energy, masks.ring, masks.theta)

    return {
        "step": step,
        "time": time,
        "core_energy": core_energy,
        "outer_lattice_energy": outer_energy,
        "total_energy": total_energy,
        "energy_well_ratio": ratio,
        "max_amplitude": max_amp,
        "max_amplitude_location": f"{max_index[0]},{max_index[1]}",
        "max_amplitude_row": int(max_index[0]),
        "max_amplitude_col": int(max_index[1]),
        "localization_index": localization,
        "spatial_entropy": spatial_metrics["spatial_entropy"],
        "spatial_entropy_normalized": spatial_metrics["spatial_entropy_normalized"],
        "participation_fraction": spatial_metrics["participation_fraction"],
        "core_retention_after_drive_cutoff": 0.0,
        "q_like_decay": 0.0,
        "spectral_peak_frequency": 0.0,
        "spectral_purity": 0.0,
        "center_to_surround_amplitude_ratio": amp_ratio,
        "ring_energy_ratio": ring_ratio,
        "angular_energy_phase": phase,
        "angular_coherence": coherence,
    }


def angular_energy_phase(energy: np.ndarray, mask: np.ndarray, theta: np.ndarray) -> tuple[float, float]:
    if not np.any(mask):
        return 0.0, 0.0
    weights = energy[mask]
    total = float(np.sum(weights))
    if total <= EPSILON:
        return 0.0, 0.0
    x = float(np.sum(weights * np.cos(theta[mask])))
    y = float(np.sum(weights * np.sin(theta[mask])))
    phase = float(np.arctan2(y, x))
    coherence = float(np.sqrt(x * x + y * y) / (total + EPSILON))
    return phase, coherence


def core_signal(lattice: Lattice2D) -> float:
    return float(np.mean(lattice.u[lattice.masks.core]))


def add_posthoc_metrics(
    samples: list[dict[str, Any]],
    core_displacement: list[float],
    config: SimulationConfig,
) -> dict[str, float]:
    if not samples:
        return {"spectral_peak_frequency": 0.0, "spectral_purity": 0.0, "q_like_decay": 0.0}

    times = np.array([row["time"] for row in samples], dtype=float)
    core_energy = np.array([row["core_energy"] for row in samples], dtype=float)
    cutoff = config.driver.drive_cutoff_time
    if cutoff is None:
        cutoff = times[-1] + config.dt

    pre_mask = times <= cutoff
    pre_peak = float(np.max(core_energy[pre_mask])) if np.any(pre_mask) else float(np.max(core_energy))
    post_peak = float(np.max(core_energy[times > cutoff])) if np.any(times > cutoff) else 0.0
    reference_peak = max(pre_peak, post_peak, EPSILON)

    retention_series = np.where(times > cutoff, core_energy / reference_peak, 0.0)

    sample_dt = config.dt * max(1, config.sample_every)
    peak_frequency, spectral_purity = estimate_spectral_peak(core_displacement, sample_dt)
    q_like = estimate_q_like_decay(times, core_energy, cutoff, peak_frequency, reference_peak)

    for idx, row in enumerate(samples):
        row["core_retention_after_drive_cutoff"] = float(retention_series[idx])
        row["spectral_peak_frequency"] = peak_frequency
        row["spectral_purity"] = spectral_purity
        row["q_like_decay"] = q_like

    return {
        "spectral_peak_frequency": peak_frequency,
        "spectral_purity": spectral_purity,
        "q_like_decay": q_like,
    }


def estimate_spectral_peak(signal: list[float], dt: float) -> tuple[float, float]:
    values = np.asarray(signal, dtype=float)
    if values.size < 8:
        return 0.0, 0.0

    start = values.size // 5
    values = values[start:] - np.mean(values[start:])
    if np.max(np.abs(values)) <= EPSILON:
        return 0.0, 0.0

    window = np.hanning(values.size)
    spectrum = np.abs(np.fft.rfft(values * window)) ** 2
    freqs = np.fft.rfftfreq(values.size, dt)
    if spectrum.size <= 1:
        return 0.0, 0.0

    spectrum[0] = 0.0
    peak_idx = int(np.argmax(spectrum))
    total_power = float(np.sum(spectrum))
    if total_power <= EPSILON:
        return 0.0, 0.0
    purity = float(spectrum[peak_idx] / total_power)
    return float(freqs[peak_idx]), purity


def estimate_q_like_decay(
    times: np.ndarray,
    core_energy: np.ndarray,
    cutoff: float,
    peak_frequency: float,
    reference_peak: float,
) -> float:
    post_mask = (times > cutoff) & (core_energy > reference_peak * 0.02)
    if int(np.sum(post_mask)) < 6 or peak_frequency <= 0.0:
        return 0.0

    x = times[post_mask] - cutoff
    y = np.log(np.maximum(core_energy[post_mask], EPSILON))
    slope, _intercept = np.polyfit(x, y, 1)
    if slope >= 0:
        tail_start = max(0, int(core_energy[post_mask].size * 0.65))
        tail_fraction = float(np.mean(core_energy[post_mask][tail_start:]) / max(reference_peak, EPSILON))
        return 999.0 if tail_fraction > 0.35 else 0.0
    tau = -1.0 / slope
    return float(max(0.0, min(999.0, np.pi * peak_frequency * tau)))


def write_metrics_csv(path: str | Path, samples: list[dict[str, Any]]) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=METRIC_FIELDS)
        writer.writeheader()
        for row in samples:
            writer.writerow({field: row.get(field, "") for field in METRIC_FIELDS})
