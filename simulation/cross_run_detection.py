"""Cross-run threshold detection for parameter sweeps."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

from .config import load_json_config, save_json


EPSILON = 1e-12
SCAN_FIELDS = ("drive_amplitude", "drive_frequency")


def annotate_cross_run_thresholds(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate sweep summaries when neighboring runs show abrupt threshold jumps.

    This pass compares pairs of runs that differ only by drive amplitude or drive
    frequency. It is intentionally separate from single-run detection because a
    threshold claim needs a neighbor for context.
    """

    annotated = [deepcopy(summary) for summary in summaries]
    records = [_record(summary) for summary in annotated]

    for summary in annotated:
        summary.setdefault("base_anomaly_score", summary.get("anomaly_score", 0.0))
        summary["anomaly_score"] = float(summary["base_anomaly_score"])
        summary["cross_run_threshold_score"] = 0.0
        summary["cross_run_anomaly_bonus"] = 0.0
        summary["cross_run_threshold_events"] = []
        summary["cross_run_threshold_details"] = []

    for scan_field in SCAN_FIELDS:
        for group in _groups(records, scan_field).values():
            if len(group) < 2:
                continue
            ordered = sorted(group, key=lambda record: record["flat"][scan_field])
            for lower, upper in zip(ordered, ordered[1:]):
                event = _compare_neighbors(lower, upper, scan_field)
                if event is None:
                    continue
                _apply_event(event)

    for summary in annotated:
        bonus = float(summary["cross_run_anomaly_bonus"])
        if bonus > 0.0:
            summary["anomaly_score"] = float(round(float(summary["base_anomaly_score"]) + bonus, 3))
            _append_threshold_interpretation(summary)
        _write_back_summary(summary)

    return annotated


def _record(summary: dict[str, Any]) -> dict[str, Any]:
    config = load_json_config(Path(summary["path"]) / "config.json")
    return {"summary": summary, "config": config, "flat": _flatten_config(config)}


def _flatten_config(config: dict[str, Any]) -> dict[str, Any]:
    defect = config.get("defect", {})
    driver = config.get("driver", {})
    return {
        "grid_size": config.get("grid_size"),
        "steps": config.get("steps"),
        "dt": config.get("dt"),
        "base_stiffness": config.get("base_stiffness"),
        "coupling_strength": config.get("coupling_strength"),
        "global_damping": config.get("global_damping"),
        "nonlinear_strength": config.get("nonlinear_strength", 0.0),
        "boundary_mode": config.get("boundary_mode", "reflective"),
        "boundary_damping_width": config.get("boundary_damping_width", 0),
        "boundary_damping_strength": config.get("boundary_damping_strength", 0.0),
        "defect_radius": defect.get("radius"),
        "defect_stiffness_multiplier": defect.get("stiffness_multiplier"),
        "defect_damping_multiplier": defect.get("damping_multiplier"),
        "defect_coupling_multiplier": defect.get("coupling_multiplier"),
        "defect_nonlinear_strength": defect.get("nonlinear_strength", 0.0),
        "driver_sides": tuple(driver.get("sides", ())),
        "driver_frequency": driver.get("frequency"),
        "driver_amplitude": driver.get("amplitude"),
        "driver_phase_offset": driver.get("phase_offset", 0.0),
        "driver_mode": driver.get("mode", "continuous"),
        "driver_drive_cutoff_time": driver.get("drive_cutoff_time"),
        "driver_phase_mode": driver.get("phase_mode", "uniform"),
        "driver_rotating_phase_winding": driver.get("rotating_phase_winding", 1),
        "drive_frequency": driver.get("frequency"),
        "drive_amplitude": driver.get("amplitude"),
    }


def _groups(records: list[dict[str, Any]], scan_field: str) -> dict[tuple[tuple[str, Any], ...], list[dict[str, Any]]]:
    groups: dict[tuple[tuple[str, Any], ...], list[dict[str, Any]]] = {}
    excluded = {scan_field, f"driver_{scan_field.removeprefix('drive_')}"}
    for record in records:
        flat = record["flat"]
        if flat.get(scan_field) is None:
            continue
        if _total_nonlinearity(flat) <= 0.0:
            continue
        signature = tuple(
            sorted(
                (key, _normalized(value))
                for key, value in flat.items()
                if key not in excluded
            )
        )
        groups.setdefault(signature, []).append(record)
    return groups


def _normalized(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, list):
        return tuple(_normalized(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_normalized(item) for item in value)
    return value


def _total_nonlinearity(flat: dict[str, Any]) -> float:
    return float(flat.get("nonlinear_strength") or 0.0) + float(flat.get("defect_nonlinear_strength") or 0.0)


def _compare_neighbors(
    first: dict[str, Any],
    second: dict[str, Any],
    scan_field: str,
) -> dict[str, Any] | None:
    first_summary = first["summary"]
    second_summary = second["summary"]
    first_evidence = _evidence_strength(first_summary)
    second_evidence = _evidence_strength(second_summary)
    high, low = (second, first) if second_evidence >= first_evidence else (first, second)

    high_summary = high["summary"]
    low_summary = low["summary"]
    triggered = _triggered_metrics(high_summary, low_summary)
    if not triggered:
        return None

    threshold_score = min(1.0, 0.2 + 0.18 * len(triggered) + _evidence_delta(high_summary, low_summary))
    if threshold_score < 0.45:
        return None

    return {
        "target": high_summary,
        "scan_field": scan_field,
        "label": f"cross_run_{scan_field.replace('drive_', '')}_threshold",
        "threshold_score": float(round(threshold_score, 3)),
        "bonus": float(round(12.0 * threshold_score, 3)),
        "detail": {
            "scan_field": scan_field,
            "run_id": high_summary["run_id"],
            "neighbor_run_id": low_summary["run_id"],
            "value": high["flat"][scan_field],
            "neighbor_value": low["flat"][scan_field],
            "triggered_metrics": triggered,
            "best_energy_well_ratio": high_summary.get("best_energy_well_ratio", 0.0),
            "neighbor_best_energy_well_ratio": low_summary.get("best_energy_well_ratio", 0.0),
            "max_core_energy_fraction": high_summary.get("max_core_energy_fraction", 0.0),
            "neighbor_max_core_energy_fraction": low_summary.get("max_core_energy_fraction", 0.0),
            "retention_score": high_summary.get("retention_score", 0.0),
            "neighbor_retention_score": low_summary.get("retention_score", 0.0),
            "base_anomaly_score": high_summary.get("base_anomaly_score", high_summary.get("anomaly_score", 0.0)),
            "neighbor_anomaly_score": low_summary.get("base_anomaly_score", low_summary.get("anomaly_score", 0.0)),
        },
    }


def _evidence_strength(summary: dict[str, Any]) -> float:
    ratio = float(summary.get("best_energy_well_ratio", 0.0))
    core_fraction = float(summary.get("max_core_energy_fraction", 0.0))
    retention = float(summary.get("retention_score", 0.0))
    anomaly = float(summary.get("base_anomaly_score", summary.get("anomaly_score", 0.0)))
    return (
        0.35 * np.clip(np.log1p(max(ratio, 0.0)) / np.log1p(0.5), 0.0, 1.0)
        + 0.25 * np.clip(core_fraction / 0.15, 0.0, 1.0)
        + 0.20 * np.clip(retention / 0.5, 0.0, 1.0)
        + 0.20 * np.clip(anomaly / 35.0, 0.0, 1.0)
    )


def _triggered_metrics(high: dict[str, Any], low: dict[str, Any]) -> list[str]:
    triggered = []
    if _jump(high, low, "best_energy_well_ratio", factor=1.6, absolute=0.015, floor=0.025):
        triggered.append("best_energy_well_ratio")
    if _jump(high, low, "max_core_energy_fraction", factor=1.45, absolute=0.01, floor=0.03):
        triggered.append("max_core_energy_fraction")
    if _jump(high, low, "retention_score", factor=1.45, absolute=0.12, floor=0.2):
        triggered.append("retention_score")

    high_score = float(high.get("base_anomaly_score", high.get("anomaly_score", 0.0)))
    low_score = float(low.get("base_anomaly_score", low.get("anomaly_score", 0.0)))
    if high_score >= 8.0 and high_score - low_score >= 5.0:
        triggered.append("anomaly_score")

    has_core_evidence = (
        float(high.get("max_core_energy_fraction", 0.0)) >= 0.03
        or float(high.get("best_energy_well_ratio", 0.0)) >= 0.035
        or high_score >= 10.0
    )
    if not has_core_evidence or len(triggered) < 2:
        return []
    return triggered


def _jump(
    high: dict[str, Any],
    low: dict[str, Any],
    key: str,
    *,
    factor: float,
    absolute: float,
    floor: float,
) -> bool:
    high_value = float(high.get(key, 0.0))
    low_value = float(low.get(key, 0.0))
    return high_value >= floor and high_value - low_value >= absolute and high_value >= low_value * factor


def _evidence_delta(high: dict[str, Any], low: dict[str, Any]) -> float:
    delta = _evidence_strength(high) - _evidence_strength(low)
    return float(np.clip(delta, 0.0, 0.35))


def _apply_event(event: dict[str, Any]) -> None:
    summary = event["target"]
    labels = summary.setdefault("detected_event_labels", [])
    if event["label"] not in labels:
        labels.append(event["label"])
    if "nonlinear_threshold_jump" not in labels:
        labels.append("nonlinear_threshold_jump")

    details = summary.setdefault("cross_run_threshold_details", [])
    details.append(event["detail"])
    summary["cross_run_threshold_events"] = sorted(
        set(summary.get("cross_run_threshold_events", []) + [event["label"]])
    )
    summary["cross_run_threshold_score"] = max(
        float(summary.get("cross_run_threshold_score", 0.0)),
        event["threshold_score"],
    )
    summary["cross_run_anomaly_bonus"] = max(
        float(summary.get("cross_run_anomaly_bonus", 0.0)),
        event["bonus"],
    )


def _append_threshold_interpretation(summary: dict[str, Any]) -> None:
    sentence = (
        "Compared with a neighboring amplitude or frequency sweep run, this configuration showed an abrupt increase "
        "in multiple core-localization metrics, suggesting possible nonlinear threshold behavior."
    )
    existing = summary.get("plain_language_interpretation", "")
    if sentence not in existing:
        summary["plain_language_interpretation"] = f"{existing} {sentence}".strip()


def _write_back_summary(summary: dict[str, Any]) -> None:
    save_json(Path(summary["path"]) / "summary.json", summary)
