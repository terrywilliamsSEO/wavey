"""Spatial diagnostics for resonance mode-shape analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .config import SimulationConfig


EPSILON = 1e-12


def spatial_distribution_metrics(energy: np.ndarray) -> dict[str, float]:
    """Measure how concentrated or diffuse a nonnegative energy field is."""

    weights = np.asarray(energy, dtype=float)
    total = float(np.sum(weights))
    if total <= EPSILON:
        return {
            "spatial_entropy": 0.0,
            "spatial_entropy_normalized": 0.0,
            "participation_fraction": 0.0,
        }

    probabilities = weights / total
    positive = probabilities[probabilities > 0.0]
    entropy = float(-np.sum(positive * np.log(positive)))
    max_entropy = float(np.log(probabilities.size)) if probabilities.size > 1 else 1.0
    participation = float(1.0 / (np.sum(probabilities**2) + EPSILON))

    return {
        "spatial_entropy": entropy,
        "spatial_entropy_normalized": float(np.clip(entropy / max_entropy, 0.0, 1.0)),
        "participation_fraction": float(np.clip(participation / probabilities.size, 0.0, 1.0)),
    }


def energy_shape_metrics(energy: np.ndarray, config: SimulationConfig) -> dict[str, float]:
    """Return best-frame shape metrics used for run summaries and band reports."""

    metrics = spatial_distribution_metrics(energy)
    radial = radial_energy_profile(energy, config)
    mass = radial["mass"]
    positive = mass[mass > 0.0]
    if positive.size:
        radial_entropy = float(-np.sum(positive * np.log(positive)))
        max_entropy = float(np.log(mass.size)) if mass.size > 1 else 1.0
        radial_peak_radius = float(radial["radii"][int(np.argmax(mass))])
        radial_concentration = float(np.max(mass))
    else:
        radial_entropy = 0.0
        max_entropy = 1.0
        radial_peak_radius = 0.0
        radial_concentration = 0.0

    metrics.update(
        {
            "radial_entropy_normalized": float(np.clip(radial_entropy / max_entropy, 0.0, 1.0)),
            "radial_peak_radius": radial_peak_radius,
            "radial_concentration": radial_concentration,
        }
    )
    return metrics


def radial_energy_profile(energy: np.ndarray, config: SimulationConfig) -> dict[str, np.ndarray]:
    """Collapse an energy field into normalized radial mass bins."""

    weights = np.asarray(energy, dtype=float)
    rows, cols = np.indices(weights.shape, dtype=float)
    center_row = (weights.shape[0] - 1) / 2.0
    center_col = (weights.shape[1] - 1) / 2.0
    if config.fixed_domain:
        radius = np.sqrt(((rows - center_row) * config.dy) ** 2 + ((cols - center_col) * config.dx) ** 2)
        bin_width = max(config.effective_defect_radius / 4.0, min(config.dx, config.dy))
        bins = np.floor(radius / bin_width).astype(int)
    else:
        radius = np.sqrt((rows - center_row) ** 2 + (cols - center_col) ** 2)
        scaled_radius = radius / max(float(config.defect.radius), 1.0)
        bin_width = 0.25
        bins = np.floor(scaled_radius * 4.0).astype(int)
    mass = np.zeros(int(np.max(bins)) + 1, dtype=float)
    np.add.at(mass, bins.ravel(), weights.ravel())
    total = float(np.sum(mass))
    if total > EPSILON:
        mass = mass / total
    radii = np.arange(mass.size, dtype=float) * bin_width
    return {"radii": radii, "mass": mass}


def load_best_energy_density(summary: dict[str, Any]) -> np.ndarray | None:
    """Load a run's numeric best-frame energy density if present."""

    candidates = []
    if summary.get("best_energy_density_path"):
        candidates.append(Path(summary["best_energy_density_path"]))
    if summary.get("path"):
        candidates.append(Path(summary["path"]) / "best_energy_density.npy")

    for path in candidates:
        if path.exists():
            return np.load(path)
    return None


def shape_correlation(first: np.ndarray | None, second: np.ndarray | None) -> float | None:
    """Pearson correlation between two spatial energy patterns."""

    if first is None or second is None or first.shape != second.shape:
        return None
    a = np.asarray(first, dtype=float).ravel()
    b = np.asarray(second, dtype=float).ravel()
    a = a - float(np.mean(a))
    b = b - float(np.mean(b))
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= EPSILON:
        return None
    return float(np.clip(np.dot(a, b) / denominator, -1.0, 1.0))


def radial_profile_correlation(
    first: np.ndarray | None,
    first_config: SimulationConfig,
    second: np.ndarray | None,
    second_config: SimulationConfig,
) -> float | None:
    """Pearson correlation between normalized radial energy profiles."""

    if first is None or second is None:
        return None
    first_mass = radial_energy_profile(first, first_config)["mass"]
    second_mass = radial_energy_profile(second, second_config)["mass"]
    length = max(first_mass.size, second_mass.size)
    a = np.pad(first_mass, (0, length - first_mass.size))
    b = np.pad(second_mass, (0, length - second_mass.size))
    a = a - float(np.mean(a))
    b = b - float(np.mean(b))
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= EPSILON:
        return None
    return float(np.clip(np.dot(a, b) / denominator, -1.0, 1.0))
