"""Frequency-band analysis helpers for sweep reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .config import load_json_config, save_json, simulation_config_from_dict
from .mode_diagnostics import load_best_energy_density, radial_profile_correlation, shape_correlation


FREQUENCY_THRESHOLD_LABEL = "cross_run_frequency_threshold"
STRUCTURED_BAND_LABEL = "structured_resonance_band"
ALTERNATING_RESPONSE_LABEL = "alternating_frequency_response"
NEIGHBOR_THRESHOLD_SENTENCE = (
    "Compared with a neighboring amplitude or frequency sweep run, this configuration showed an abrupt increase "
    "in multiple core-localization metrics, suggesting possible nonlinear threshold behavior."
)


def analyze_frequency_band(ranked: list[dict[str, Any]]) -> dict[str, Any] | None:
    rows = []
    for summary in ranked:
        config_data = load_json_config(Path(summary["path"]) / "config.json")
        driver = config_data.get("driver", {})
        frequency = driver.get("frequency")
        if frequency is None:
            continue
        sim_config = _simulation_config_from_summary(summary)
        rows.append(
            {
                "run_id": summary["run_id"],
                "path": summary["path"],
                "frequency": float(frequency),
                "energy_well_ratio": float(summary.get("best_energy_well_ratio", 0.0)),
                "core_fraction": float(summary.get("max_core_energy_fraction", 0.0)),
                "anomaly_score": float(summary.get("anomaly_score", 0.0)),
                "spectral_peak_frequency": float(summary.get("spectral_peak_frequency", 0.0)),
                "spectral_purity": float(summary.get("spectral_purity", 0.0)),
                "spatial_entropy_normalized": float(summary.get("best_frame_spatial_entropy_normalized", 0.0)),
                "participation_fraction": float(summary.get("best_frame_participation_fraction", 0.0)),
                "radial_peak_radius": float(summary.get("best_frame_radial_peak_radius", 0.0)),
                "radial_concentration": float(summary.get("best_frame_radial_concentration", 0.0)),
                "_energy": load_best_energy_density(summary),
                "_config": sim_config,
            }
        )

    rows = sorted(rows, key=lambda row: row["frequency"])
    if len(rows) < 3:
        return None
    if len({row["frequency"] for row in rows}) != len(rows):
        return None

    max_ratio = max(row["energy_well_ratio"] for row in rows)
    if max_ratio <= 0.0:
        return None

    peaks = []
    troughs = []
    for idx in range(1, len(rows) - 1):
        left = rows[idx - 1]["energy_well_ratio"]
        current = rows[idx]["energy_well_ratio"]
        right = rows[idx + 1]["energy_well_ratio"]
        if current > left and current > right:
            peaks.append(rows[idx])
        if current < left and current < right:
            troughs.append(rows[idx])

    strongest = max(rows, key=lambda row: row["energy_well_ratio"])
    _add_mode_shape_comparisons(rows, strongest)
    half_threshold = max_ratio * 0.5
    above_half = [row for row in rows if row["energy_well_ratio"] >= half_threshold]
    half_power_band = {
        "threshold": half_threshold,
        "min_frequency": min(row["frequency"] for row in above_half),
        "max_frequency": max(row["frequency"] for row in above_half),
        "width": max(row["frequency"] for row in above_half) - min(row["frequency"] for row in above_half),
    }
    adjacent_comparisons = _adjacent_comparisons(rows)
    classification = _classify_band(rows, peaks, troughs, half_power_band, adjacent_comparisons)

    return {
        "strongest_frequency": strongest["frequency"],
        "strongest_run_id": strongest["run_id"],
        "strongest_energy_well_ratio": strongest["energy_well_ratio"],
        "local_peak_count": len(peaks),
        "local_trough_count": len(troughs),
        "local_peaks": peaks,
        "local_troughs": troughs,
        "half_power_band": half_power_band,
        "adjacent_comparisons": adjacent_comparisons,
        "mean_adjacent_shape_correlation": _mean_optional(
            comparison["shape_correlation"] for comparison in adjacent_comparisons
        ),
        "mean_adjacent_radial_correlation": _mean_optional(
            comparison["radial_profile_correlation"] for comparison in adjacent_comparisons
        ),
        "classification": classification,
        "interpretation": _band_interpretation(classification),
        "frequency_thresholds_should_be_downweighted": classification
        in {"structured_resonance_band", "alternating_frequency_response"},
        "rows": rows,
    }


def annotate_frequency_band_context(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach frequency-band context and downweight dense-scan threshold claims."""

    band = analyze_frequency_band(summaries)
    if band is None:
        return summaries

    by_run_id = {summary["run_id"]: summary for summary in summaries}
    peak_freqs = {row["frequency"] for row in band["local_peaks"]}
    trough_freqs = {row["frequency"] for row in band["local_troughs"]}
    for row in band["rows"]:
        summary = by_run_id[row["run_id"]]
        role = "plain"
        if row["run_id"] == band["strongest_run_id"]:
            role = "strongest"
        elif row["frequency"] in peak_freqs:
            role = "peak"
        elif row["frequency"] in trough_freqs:
            role = "trough"
        elif row["energy_well_ratio"] >= band["half_power_band"]["threshold"]:
            role = "within_half_max_band"

        summary["frequency_band_role"] = role
        summary["frequency_band_classification"] = band["classification"]
        summary["mode_shape_correlation_to_strongest"] = _rounded_optional(
            row.get("mode_shape_correlation_to_strongest")
        )
        summary["radial_profile_correlation_to_strongest"] = _rounded_optional(
            row.get("radial_profile_correlation_to_strongest")
        )

        labels = summary.setdefault("detected_event_labels", [])
        if band["classification"] == "structured_resonance_band":
            if STRUCTURED_BAND_LABEL not in labels:
                labels.append(STRUCTURED_BAND_LABEL)
        if band["classification"] == "alternating_frequency_response":
            if ALTERNATING_RESPONSE_LABEL not in labels:
                labels.append(ALTERNATING_RESPONSE_LABEL)

    if band["frequency_thresholds_should_be_downweighted"]:
        for summary in summaries:
            _downweight_frequency_threshold(summary, band)

    for summary in summaries:
        _write_back_summary(summary)

    return summaries


def _add_mode_shape_comparisons(rows: list[dict[str, Any]], strongest: dict[str, Any]) -> None:
    for row in rows:
        row["mode_shape_correlation_to_strongest"] = shape_correlation(row["_energy"], strongest["_energy"])
        row["radial_profile_correlation_to_strongest"] = radial_profile_correlation(
            row["_energy"],
            row["_config"],
            strongest["_energy"],
            strongest["_config"],
        )


def _adjacent_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons = []
    for first, second in zip(rows, rows[1:]):
        comparisons.append(
            {
                "from_frequency": first["frequency"],
                "to_frequency": second["frequency"],
                "shape_correlation": shape_correlation(first["_energy"], second["_energy"]),
                "radial_profile_correlation": radial_profile_correlation(
                    first["_energy"],
                    first["_config"],
                    second["_energy"],
                    second["_config"],
                ),
                "energy_well_ratio_delta": second["energy_well_ratio"] - first["energy_well_ratio"],
            }
        )
    return comparisons


def _classify_band(
    rows: list[dict[str, Any]],
    peaks: list[dict[str, Any]],
    troughs: list[dict[str, Any]],
    half_power_band: dict[str, float],
    adjacent_comparisons: list[dict[str, Any]],
) -> str:
    steps = np.diff([row["frequency"] for row in rows])
    median_step = float(np.median(steps)) if steps.size else 0.0
    dense_scan = len(rows) >= 5 and median_step > 0.0 and median_step <= 0.05
    alternating_response = len(peaks) + len(troughs) >= 3
    broad_band = median_step > 0.0 and half_power_band["width"] >= 3.0 * median_step
    mean_shape = _mean_optional(comparison["shape_correlation"] for comparison in adjacent_comparisons)
    mean_radial = _mean_optional(comparison["radial_profile_correlation"] for comparison in adjacent_comparisons)
    similar_shapes = (mean_shape is not None and mean_shape >= 0.55) or (
        mean_radial is not None and mean_radial >= 0.75
    )

    if dense_scan and alternating_response and broad_band and similar_shapes:
        return "structured_resonance_band"
    if dense_scan and alternating_response:
        return "alternating_frequency_response"
    if len(peaks) <= 1 and median_step > 0.0 and half_power_band["width"] <= 2.0 * median_step:
        return "isolated_or_unresolved_peak"
    return "broad_frequency_response"


def _band_interpretation(classification: str) -> str:
    if classification == "structured_resonance_band":
        return (
            "Neighboring peak and trough runs retain similar spatial/radial mode shapes, so the frequency scan "
            "looks like a structured resonance band with amplitude modulation rather than independent threshold events."
        )
    if classification == "alternating_frequency_response":
        return (
            "The dense frequency scan alternates between peaks and troughs. Treat neighbor jumps as band structure "
            "until a longer validation run proves a true threshold."
        )
    if classification == "isolated_or_unresolved_peak":
        return "The response is narrow at the sampled resolution; a finer local scan is needed before calling it isolated."
    return "The response spans multiple sampled frequencies, suggesting a broad resonance region."


def _downweight_frequency_threshold(summary: dict[str, Any], band: dict[str, Any]) -> None:
    events = list(summary.get("cross_run_threshold_events", []))
    if FREQUENCY_THRESHOLD_LABEL not in events:
        return

    remaining_events = [event for event in events if event != FREQUENCY_THRESHOLD_LABEL]
    details = list(summary.get("cross_run_threshold_details", []))
    frequency_details = [detail for detail in details if detail.get("scan_field") == "drive_frequency"]
    remaining_details = [detail for detail in details if detail.get("scan_field") != "drive_frequency"]

    summary["frequency_band_threshold_downweighted"] = True
    summary["frequency_band_threshold_reason"] = band["interpretation"]
    summary["downweighted_cross_run_threshold_details"] = frequency_details
    summary["cross_run_threshold_events"] = remaining_events
    summary["cross_run_threshold_details"] = remaining_details

    labels = summary.setdefault("detected_event_labels", [])
    if FREQUENCY_THRESHOLD_LABEL in labels:
        labels.remove(FREQUENCY_THRESHOLD_LABEL)
    if not remaining_events and float(summary.get("threshold_score", 0.0)) <= 0.0 and "nonlinear_threshold_jump" in labels:
        labels.remove("nonlinear_threshold_jump")

    if not remaining_events:
        summary["cross_run_threshold_score"] = 0.0
        summary["cross_run_anomaly_bonus"] = 0.0
        summary["anomaly_score"] = float(summary.get("base_anomaly_score", summary.get("anomaly_score", 0.0)))

    sentence = (
        "Dense frequency-band diagnostics downweighted a neighboring-frequency threshold flag because the response "
        "appears to belong to a resonance band."
    )
    existing = summary.get("plain_language_interpretation", "")
    existing = " ".join(existing.replace(NEIGHBOR_THRESHOLD_SENTENCE, "").split())
    if sentence not in existing:
        summary["plain_language_interpretation"] = f"{existing} {sentence}".strip()


def _simulation_config_from_summary(summary: dict[str, Any]):
    data = load_json_config(Path(summary["path"]) / "config.json")
    data.pop("run_id", None)
    return simulation_config_from_dict(data)


def _mean_optional(values: Any) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return float(np.mean(numeric))


def _rounded_optional(value: Any) -> float | None:
    if value is None:
        return None
    return float(round(float(value), 6))


def _write_back_summary(summary: dict[str, Any]) -> None:
    if summary.get("path"):
        save_json(Path(summary["path"]) / "summary.json", summary)
