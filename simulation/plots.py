"""Evidence plot generation."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np

from .config import SimulationConfig


def save_heatmap(
    energy_density: np.ndarray,
    config: SimulationConfig,
    path: str | Path,
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(7, 6), dpi=140)
    im = ax.imshow(energy_density, origin="upper", cmap="magma")
    center_x = (config.nx - 1) / 2.0
    center_y = (config.ny - 1) / 2.0
    radius_scale = 1.0 / config.dx if config.fixed_domain else 1.0
    defect_circle = Circle(
        (center_x, center_y),
        config.effective_defect_radius * radius_scale,
        edgecolor="cyan",
        facecolor="none",
        linewidth=1.6,
        linestyle="--",
        label="defect radius",
    )
    core_circle = Circle(
        (center_x, center_y),
        config.effective_core_radius_value * radius_scale,
        edgecolor="white",
        facecolor="none",
        linewidth=1.0,
        alpha=0.85,
        label="metric core",
    )
    ax.add_patch(defect_circle)
    ax.add_patch(core_circle)
    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(loc="upper right", fontsize=7)
    fig.colorbar(im, ax=ax, label="energy density")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_energy_well_ratio(samples: list[dict], path: str | Path) -> None:
    times = [row["time"] for row in samples]
    ratios = [row["energy_well_ratio"] for row in samples]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    ax.plot(times, ratios, color="#7a1fa2", linewidth=1.5)
    ax.set_title("Energy well ratio")
    ax.set_xlabel("time")
    ax.set_ylabel("core energy / outer energy")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_core_vs_outer(samples: list[dict], path: str | Path) -> None:
    times = [row["time"] for row in samples]
    core = [row["core_energy"] for row in samples]
    outer = [row["outer_lattice_energy"] for row in samples]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    ax.plot(times, core, label="core energy", color="#117733", linewidth=1.5)
    ax.plot(times, outer, label="outer lattice energy", color="#3366aa", linewidth=1.2)
    ax.set_title("Core vs outer energy")
    ax.set_xlabel("time")
    ax.set_ylabel("energy")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_core_spectrum(
    core_displacement: list[float],
    sample_dt: float,
    path: str | Path,
) -> None:
    values = np.asarray(core_displacement, dtype=float)
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)

    if values.size >= 8 and np.max(np.abs(values - np.mean(values))) > 1e-12:
        start = values.size // 5
        windowed = (values[start:] - np.mean(values[start:])) * np.hanning(values.size - start)
        spectrum = np.abs(np.fft.rfft(windowed)) ** 2
        freqs = np.fft.rfftfreq(windowed.size, sample_dt)
        if spectrum.size:
            spectrum[0] = 0.0
        ax.plot(freqs, spectrum, color="#b24a0b", linewidth=1.4)
        if spectrum.size > 1 and np.max(spectrum) > 0.0:
            peak_idx = int(np.argmax(spectrum))
            ax.axvline(freqs[peak_idx], color="#333333", linestyle="--", linewidth=1.0)
            ax.text(
                freqs[peak_idx],
                np.max(spectrum) * 0.92,
                f"peak {freqs[peak_idx]:.3g}",
                rotation=90,
                va="top",
                ha="right",
                fontsize=8,
            )
    else:
        ax.plot([0.0], [0.0], marker="o", color="#b24a0b")
        ax.text(0.5, 0.5, "No core oscillation signal", transform=ax.transAxes, ha="center", va="center")

    ax.set_title("Core displacement spectrum")
    ax.set_xlabel("frequency")
    ax.set_ylabel("power")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
