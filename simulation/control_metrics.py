"""Shared metrics for targeted control comparisons."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np


EPSILON = 1e-12


def run_energy_comparison(run_path: str | Path, cutoff_time: float | None) -> dict[str, float | None]:
    """Return absolute-energy fields for a completed run."""

    rows = _read_metric_rows(Path(run_path) / "metrics.csv")
    if not rows:
        return {}
    best = max(rows, key=lambda row: row.get("energy_well_ratio", 0.0))
    total = float(best.get("total_energy", 0.0))
    core = float(best.get("core_energy", 0.0))
    outer = float(best.get("outer_lattice_energy", 0.0))
    core_peak_stats = _post_cutoff_peak_stats(rows, cutoff_time, "core_energy")
    return {
        "best_core_energy": core,
        "best_outer_lattice_energy": outer,
        "best_total_energy": total,
        "best_core_fraction": core / (total + EPSILON),
        "best_ratio_from_absolute_energy": core / (outer + EPSILON),
        "core_decay_rate_after_cutoff": _post_cutoff_decay_rate(rows, cutoff_time, "core_energy"),
        "outer_decay_rate_after_cutoff": _post_cutoff_decay_rate(rows, cutoff_time, "outer_lattice_energy"),
        "total_decay_rate_after_cutoff": _post_cutoff_decay_rate(rows, cutoff_time, "total_energy"),
        "metric_core_peak_period_after_cutoff": core_peak_stats["period"],
        "metric_core_peak_cycles_after_cutoff": core_peak_stats["cycles"],
        "metric_core_peak_interval_cv_after_cutoff": core_peak_stats["interval_cv"],
    }


def _read_metric_rows(path: Path) -> list[dict[str, float]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        rows = []
        for row in csv.DictReader(fh):
            converted = {}
            for key, value in row.items():
                try:
                    converted[key] = float(value)
                except (TypeError, ValueError):
                    pass
            rows.append(converted)
        return rows


def _post_cutoff_decay_rate(rows: list[dict[str, float]], cutoff_time: float | None, key: str) -> float:
    if cutoff_time is None:
        return 0.0
    post = [row for row in rows if row.get("time", 0.0) > cutoff_time and row.get(key, 0.0) > EPSILON]
    if len(post) < 8:
        return 0.0

    times = np.asarray([row["time"] - cutoff_time for row in post], dtype=float)
    values = np.asarray([row[key] for row in post], dtype=float)
    peak_indices = _local_peaks(values)
    if peak_indices.size >= 4:
        times = times[peak_indices]
        values = values[peak_indices]

    if times.size < 4 or np.max(values) <= EPSILON:
        return 0.0
    slope, _intercept = np.polyfit(times, np.log(np.maximum(values, EPSILON)), 1)
    return float(slope)


def _post_cutoff_peak_stats(
    rows: list[dict[str, float]],
    cutoff_time: float | None,
    key: str,
) -> dict[str, float | None]:
    if cutoff_time is None:
        return {"period": None, "cycles": 0.0, "interval_cv": None}
    post = [row for row in rows if row.get("time", 0.0) > cutoff_time and row.get(key, 0.0) > EPSILON]
    if len(post) < 8:
        return {"period": None, "cycles": 0.0, "interval_cv": None}

    times = np.asarray([row["time"] for row in post], dtype=float)
    values = np.asarray([row[key] for row in post], dtype=float)
    peak_indices = _local_peaks(values)
    if peak_indices.size:
        strong_cutoff = np.percentile(values, 55)
        peak_indices = peak_indices[values[peak_indices] >= strong_cutoff]
    intervals = np.diff(times[peak_indices]) if peak_indices.size >= 2 else np.array([])
    if not intervals.size:
        return {"period": None, "cycles": float(peak_indices.size), "interval_cv": None}
    return {
        "period": float(np.mean(intervals)),
        "cycles": float(peak_indices.size),
        "interval_cv": float(np.std(intervals) / (np.mean(intervals) + EPSILON)),
    }


def _local_peaks(values: np.ndarray) -> np.ndarray:
    if values.size < 3:
        return np.array([], dtype=int)
    return np.where((values[1:-1] > values[:-2]) & (values[1:-1] > values[2:]))[0] + 1
