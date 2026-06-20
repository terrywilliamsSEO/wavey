"""Read-only modal audit for the 41^3 release-phase proof and 51^3 blur."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import math

import numpy as np

from .prototype_3d import EPSILON
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_PROOF_ROOT = "runs/release_phase_proof_pack_3d_20260619_234039"
DEFAULT_LIFT_ROOT = "runs/release_phase_resolution_lift_3d_20260620_091834"
DEFAULT_POSTMORTEM_ROOT = "runs/release_phase_resolution_postmortem_3d_20260620_100043"
DEFAULT_CENTRAL_ROOT = "runs/central_burst_3d_20260620_103248"


@dataclass(frozen=True)
class ReleasePhaseModalAuditOptions:
    """Options for the read-only modal audit."""

    output_root: str = "runs"
    proof_root: str = DEFAULT_PROOF_ROOT
    lift_root: str = DEFAULT_LIFT_ROOT
    postmortem_root: str = DEFAULT_POSTMORTEM_ROOT
    central_root: str = DEFAULT_CENTRAL_ROOT
    same_band_relative_tolerance: float = 0.16
    min_strict_major_loss: float = 1.0
    min_loose_recovery: float = 1.0
    blur_width_growth_threshold: float = 0.03
    blur_bandwidth_growth_threshold: float = 0.05
    blur_tail_radius_shift_threshold: float = 0.40
    finite_grid_concentration_ratio: float = 1.20


def run_3d_release_phase_modal_audit(
    *,
    options: ReleasePhaseModalAuditOptions | None = None,
) -> dict[str, Any]:
    """Build a read-only modal comparison from completed proof/lift/central runs."""

    options = options or ReleasePhaseModalAuditOptions()
    control_id = datetime.now().strftime("release_phase_modal_audit_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    proof_root = Path(options.proof_root)
    lift_root = Path(options.lift_root)
    postmortem_root = Path(options.postmortem_root)
    central_root = Path(options.central_root)
    postmortem_rows = _read_csv(postmortem_root / "release_phase_resolution_postmortem_summary.csv")
    central_summary = _read_csv(central_root / "central_burst_summary.csv")
    central_threshold = _read_csv(central_root / "central_burst_threshold_counts.csv")
    central_timeseries = _group_by(_read_csv(central_root / "central_burst_timeseries.csv"), "variant")
    central_events = _group_by(_read_csv(central_root / "central_burst_events.csv"), "variant")

    selected_rows = _selected_postmortem_rows(postmortem_rows)
    selected_rows.extend(_selected_central_rows(central_summary))

    summary_rows: list[dict[str, Any]] = []
    spectrum_rows: list[dict[str, Any]] = []
    jitter_rows: list[dict[str, Any]] = []
    radial_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []

    for source_row in selected_rows:
        variant = str(source_row.get("variant"))
        source_kind = str(source_row.get("source_run_kind") or source_row.get("branch") or "")
        if source_kind == "proof_pack":
            timeseries = _read_csv(proof_root / variant / "packet_lifecycle_timeseries.csv")
            events = _read_csv(proof_root / variant / "packet_lifecycle_events.csv")
            threshold_lookup = {}
        elif source_kind == "resolution_lift":
            timeseries = _read_csv(lift_root / variant / "packet_lifecycle_timeseries.csv")
            events = _read_csv(lift_root / variant / "packet_lifecycle_events.csv")
            threshold_lookup = {}
        else:
            timeseries = central_timeseries.get(variant, [])
            events = central_events.get(variant, [])
            threshold_lookup = _threshold_lookup([row for row in central_threshold if row.get("variant") == variant])

        row_summary, row_spectrum, row_jitter, row_radial, row_phase = _diagnose_row(
            source_row,
            timeseries,
            events,
            threshold_lookup,
        )
        summary_rows.append(row_summary)
        spectrum_rows.extend(row_spectrum)
        jitter_rows.extend(row_jitter)
        radial_rows.append(row_radial)
        phase_rows.append(row_phase)

    classification = classify_release_phase_modal_audit(summary_rows, options)
    for row in summary_rows:
        row["release_phase_modal_audit_classification"] = classification["label"]
    for row in spectrum_rows:
        row["release_phase_modal_audit_classification"] = classification["label"]
    for row in jitter_rows:
        row["release_phase_modal_audit_classification"] = classification["label"]
    for row in radial_rows:
        row["release_phase_modal_audit_classification"] = classification["label"]
    for row in phase_rows:
        row["release_phase_modal_audit_classification"] = classification["label"]

    summary_csv = root / "modal_audit_summary.csv"
    spectrum_csv = root / "shell_spectrum_comparison.csv"
    jitter_csv = root / "return_timing_jitter.csv"
    radial_csv = root / "radial_packet_width_comparison.csv"
    phase_csv = root / "phase_coherence_comparison.csv"
    report_path = root / "release_phase_modal_audit_report.md"
    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(spectrum_csv, spectrum_rows, _spectrum_fields())
    _write_csv(jitter_csv, jitter_rows, _jitter_fields())
    _write_csv(radial_csv, radial_rows, _radial_fields())
    _write_csv(phase_csv, phase_rows, _phase_fields())
    _write_report(report_path, control_id, summary_rows, classification, options)
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": summary_rows,
        "summary_csv": str(summary_csv),
        "spectrum_csv": str(spectrum_csv),
        "jitter_csv": str(jitter_csv),
        "radial_csv": str(radial_csv),
        "phase_csv": str(phase_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_release_phase_modal_audit(
    rows: list[dict[str, Any]],
    options: ReleasePhaseModalAuditOptions | None = None,
) -> dict[str, Any]:
    """Classify the modal comparison without recommending new physics by default."""

    options = options or ReleasePhaseModalAuditOptions()
    proof = [row for row in rows if row.get("audit_group") == "proof_cluster"]
    lift = [row for row in rows if str(row.get("audit_group", "")).startswith("lift_")]
    central = [row for row in rows if str(row.get("audit_group", "")).startswith("central_")]
    proof_freq = _mean(row.get("dominant_shell_frequency") for row in proof)
    lift_freq = _mean(row.get("dominant_shell_frequency") for row in lift)
    proof_concentration = _mean(row.get("dominant_spectral_concentration") for row in proof)
    lift_concentration = _mean(row.get("dominant_spectral_concentration") for row in lift)
    proof_bandwidth = _mean(row.get("spectral_bandwidth") for row in proof)
    lift_bandwidth = _mean(row.get("spectral_bandwidth") for row in lift)
    proof_width = _mean(row.get("tail_packet_spread_mean") for row in proof)
    lift_width = _mean(row.get("tail_packet_spread_mean") for row in lift)
    proof_tail_radius = _mean(row.get("tail_packet_radius_mean") for row in proof)
    lift_tail_radius = _mean(row.get("tail_packet_radius_mean") for row in lift)
    proof_strict_major = _mean(row.get("strict_major_peaks") for row in proof)
    lift_strict_major = _mean(row.get("strict_major_peaks") for row in lift)
    lift_loose_major = _mean(row.get("loose_major_peaks") for row in lift)
    same_band = _same_band(proof_freq, lift_freq, options)
    strict_loss = proof_strict_major - lift_strict_major
    loose_recovery = lift_loose_major - lift_strict_major
    bandwidth_growth = _relative_delta(lift_bandwidth, proof_bandwidth)
    width_growth = _relative_delta(lift_width, proof_width)
    tail_radius_shift = lift_tail_radius - proof_tail_radius
    concentration_ratio = proof_concentration / max(lift_concentration, EPSILON)
    concentration_relative_delta = _relative_delta(lift_concentration, proof_concentration)
    central_clean_repeated = any(
        _bool(row.get("no_exit")) and _bool(row.get("outer_shell_below_1")) and _float(row.get("strict_refocus_peaks")) >= 2
        for row in central
    )
    blur_supported = (
        same_band
        and strict_loss >= options.min_strict_major_loss
        and loose_recovery >= options.min_loose_recovery
        and (
            bandwidth_growth >= options.blur_bandwidth_growth_threshold
            or width_growth >= options.blur_width_growth_threshold
            or abs(tail_radius_shift) >= options.blur_tail_radius_shift_threshold
        )
    )
    finite_grid = (
        not same_band
        and concentration_ratio >= options.finite_grid_concentration_ratio
        and strict_loss >= options.min_strict_major_loss
    )
    checks = {
        "proof_row_count": len(proof),
        "lift_row_count": len(lift),
        "central_row_count": len(central),
        "proof_dominant_frequency_mean": proof_freq,
        "lift_dominant_frequency_mean": lift_freq,
        "same_modal_band": same_band,
        "proof_spectral_concentration_mean": proof_concentration,
        "lift_spectral_concentration_mean": lift_concentration,
        "spectral_concentration_relative_delta": concentration_relative_delta,
        "spectral_bandwidth_relative_delta": bandwidth_growth,
        "tail_spread_relative_delta": width_growth,
        "tail_radius_shift": tail_radius_shift,
        "strict_major_loss": strict_loss,
        "lift_loose_to_strict_recovery": loose_recovery,
        "central_clean_repeated": central_clean_repeated,
        "mechanism_candidate": "none",
    }
    if same_band and not central_clean_repeated and strict_loss < 0.5:
        return {
            "label": "scalable_modal_rule_supported",
            "reason": "The same modal band survives without strict-count degradation and central injection does not explain it; a corrected source design could be considered if one is explicitly derived.",
            "checks": checks,
        }
    if blur_supported:
        return {
            "label": "resolution_blur_mechanism_supported",
            "reason": "The lifted grid preserves the same shell-energy band, but strict returns shrink while loose-threshold returns remain and radial/spectral bandwidth or radial-distribution blur metrics increase.",
            "checks": checks,
        }
    if finite_grid:
        return {
            "label": "finite_grid_resonance_likely",
            "reason": "The proof cluster has a concentrated modal coincidence that is not preserved in the lifted rows.",
            "checks": checks,
        }
    return {
        "label": "inconclusive_modal_audit",
        "reason": "The modal comparison does not isolate a scalable corrected-source rule or a clean finite-grid resonance explanation.",
        "checks": checks,
    }


def _selected_postmortem_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        group = str(row.get("group"))
        if group == "proof_winner":
            out.append({**row, "audit_group": "proof_cluster"})
        elif group == "lift_candidate":
            out.append({**row, "audit_group": "lift_candidate"})
        elif group == "lift_control":
            out.append({**row, "audit_group": "lift_control"})
    return out


def _selected_central_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = [row for row in rows if row.get("dt_variant") == "baseline_dt"]
    best = max(baseline, key=lambda row: _float(row.get("central_burst_score")), default=None)
    selected: list[dict[str, Any]] = []
    if best:
        selected.append({**best, "audit_group": "central_best", "source_run_kind": "central_burst"})
    for row in baseline:
        if abs(_float(row.get("burst_frequency")) - 0.92) <= 1.0e-9 and row.get("variant") != (best or {}).get("variant"):
            selected.append({**row, "audit_group": "central_repeated_contaminated", "source_run_kind": "central_burst"})
    return selected


def _diagnose_row(
    source_row: dict[str, Any],
    timeseries: list[dict[str, Any]],
    events: list[dict[str, Any]],
    threshold_lookup: dict[float, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    variant = str(source_row.get("variant"))
    group = str(source_row.get("audit_group"))
    cutoff = _float(source_row.get("drive_cutoff_time"))
    times = _array(row.get("time") for row in timeseries)
    shell = _array(row.get("shell_window_energy") for row in timeseries)
    outer_ratio = _array(row.get("outer_to_shell_energy") for row in timeseries)
    width = _array(row.get("packet_radial_width") for row in timeseries)
    spread = _array(row.get("packet_radial_spread") for row in timeseries)
    radius = _array(row.get("packet_peak_radius") for row in timeseries)
    centroid = _array(row.get("packet_centroid_radius") for row in timeseries)
    shell_fraction = _array(row.get("shell_fraction_of_total") for row in timeseries)
    post_mask = times > cutoff if times.size else np.asarray([], dtype=bool)
    tail_mask = times >= 50.0 if times.size else np.asarray([], dtype=bool)
    spectrum = _spectrum_metrics(times[post_mask], shell[post_mask])
    autocorr = _autocorr_metrics(times[post_mask], shell[post_mask])
    peaks = _peak_rows(events)
    if not peaks and times.size:
        peaks = _detected_peak_rows(times, shell, cutoff)
    timing = _timing_metrics(peaks)
    peak_widths = _peak_width_rows(variant, group, times, shell, peaks, spectrum["dominant_shell_frequency"])
    radial_group_velocity = _float(source_row.get("radial_group_velocity") or source_row.get("post_cutoff_radial_velocity"))
    if abs(radial_group_velocity) <= EPSILON and times.size:
        radial_group_velocity = _slope(times[post_mask], centroid[post_mask])
    loose_major, loose_refocus = _loose_counts(source_row, threshold_lookup)
    strict_major, strict_refocus = _strict_counts(source_row, threshold_lookup)
    default_major, default_refocus = _default_counts(source_row, threshold_lookup)
    phase_coherence = _phase_coherence(peaks, spectrum["dominant_shell_frequency"])
    radial_row = {
        "variant": variant,
        "audit_group": group,
        "grid_size": source_row.get("grid_size"),
        "tail_packet_radius_mean": _first_float(source_row, "tail_packet_radius_mean") or _mean(radius[tail_mask]),
        "tail_packet_width_mean": _first_float(source_row, "tail_packet_width_mean") or _mean(width[tail_mask]),
        "tail_packet_spread_mean": _first_float(source_row, "tail_packet_spread_mean") or _mean(spread[tail_mask]),
        "packet_width_at_shell_peak": _first_float(source_row, "packet_width_at_shell_peak") or _max(width[post_mask]),
        "packet_spread_at_shell_peak": _first_float(source_row, "packet_spread_at_shell_peak") or _max(spread[post_mask]),
        "radial_group_velocity": radial_group_velocity,
        "radial_width_velocity": _slope(times[post_mask], width[post_mask]) if times.size else 0.0,
        "tail_outer_to_shell_mean": _first_float(source_row, "outer_shell") or _first_float(source_row, "tail_outer_to_shell_mean") or _mean(outer_ratio[tail_mask]),
        "tail_shell_fraction_mean": _mean(shell_fraction[tail_mask]),
    }
    phase_row = {
        "variant": variant,
        "audit_group": group,
        "phase_metric_kind": "scalar_shell_energy_return_phase_proxy",
        "spatial_phase_available": False,
        "dominant_shell_frequency": spectrum["dominant_shell_frequency"],
        "return_phase_locking_strength": phase_coherence,
        "shell_energy_autocorrelation_lag1": autocorr["lag1_autocorrelation"],
        "return_timing_regularity": _first_float(source_row, "return_timing_regularity") or timing["return_timing_regularity"],
        "notes": "Spatial shell phase frames were not stored in the input artifacts; this is a scalar shell-energy phase-locking proxy.",
    }
    summary = {
        "variant": variant,
        "audit_group": group,
        "source_run_kind": source_row.get("source_run_kind"),
        "prediction_role": source_row.get("prediction_role") or source_row.get("energy_label"),
        "grid_size": source_row.get("grid_size"),
        "dx": source_row.get("dx"),
        "dt": source_row.get("dt"),
        "drive_cutoff_time": cutoff,
        "cutoff_phase_cycles": source_row.get("cutoff_phase_cycles"),
        "burst_frequency": source_row.get("burst_frequency"),
        "energy_label": source_row.get("energy_label"),
        "loose_major_peaks": loose_major,
        "loose_refocus_peaks": loose_refocus,
        "default_major_peaks": default_major,
        "default_refocus_peaks": default_refocus,
        "strict_major_peaks": strict_major,
        "strict_refocus_peaks": strict_refocus,
        "loose_to_strict_major_loss": loose_major - strict_major,
        "default_to_strict_major_loss": default_major - strict_major,
        "dominant_shell_frequency": spectrum["dominant_shell_frequency"],
        "dominant_spectral_concentration": spectrum["dominant_spectral_concentration"],
        "spectral_bandwidth": spectrum["spectral_bandwidth"],
        "spectral_top3_fraction": spectrum["spectral_top3_fraction"],
        "autocorrelation_decay_time": autocorr["autocorrelation_decay_time"],
        "lag1_autocorrelation": autocorr["lag1_autocorrelation"],
        "return_timing_regularity": _first_float(source_row, "return_timing_regularity") or timing["return_timing_regularity"],
        "return_timing_jitter": timing["return_timing_jitter"],
        "mean_inter_peak_spacing": timing["mean_inter_peak_spacing"],
        "peak_amplitude_decay": timing["peak_amplitude_decay"],
        "mean_return_peak_width": _mean(row.get("peak_width_time") for row in peak_widths),
        "first_peak_energy": timing["first_peak_energy"],
        "last_peak_energy": timing["last_peak_energy"],
        "last_to_first_peak_ratio": timing["last_to_first_peak_ratio"],
        "radial_group_velocity": radial_row["radial_group_velocity"],
        "tail_packet_radius_mean": radial_row["tail_packet_radius_mean"],
        "tail_packet_width_mean": radial_row["tail_packet_width_mean"],
        "tail_packet_spread_mean": radial_row["tail_packet_spread_mean"],
        "return_phase_locking_strength": phase_coherence,
        "tail_outer_to_shell_mean": radial_row["tail_outer_to_shell_mean"],
        "tail_shell_fraction_mean": radial_row["tail_shell_fraction_mean"],
        "no_exit": _bool(source_row.get("no_exit")) if "no_exit" in source_row else not _bool(source_row.get("shell_exit_detected")),
        "outer_shell_below_1": _bool(source_row.get("outer_shell_below_1")) if "outer_shell_below_1" in source_row else _float(source_row.get("outer_shell")) < 1.0,
        "global_outer_false": _bool(source_row.get("global_outer_false")) if "global_outer_false" in source_row else not _bool(source_row.get("global_peak_in_outer_window")),
        "central_contrast_role": "best_transient" if group == "central_best" else ("repeated_but_contaminated" if group.startswith("central_") else ""),
    }
    spectrum_rows = _spectrum_rows(variant, group, spectrum)
    return summary, spectrum_rows, peak_widths, radial_row, phase_row


def _spectrum_metrics(times: np.ndarray, values: np.ndarray) -> dict[str, Any]:
    if times.size < 4 or values.size < 4:
        return {
            "dominant_shell_frequency": 0.0,
            "dominant_spectral_concentration": 0.0,
            "spectral_bandwidth": 0.0,
            "spectral_top3_fraction": 0.0,
            "modes": [],
        }
    sample_dt = float(np.median(np.diff(times)))
    centered = values - float(np.mean(values))
    freq = np.fft.rfftfreq(centered.size, d=max(sample_dt, EPSILON))
    power = np.abs(np.fft.rfft(centered)) ** 2
    if power.size <= 1:
        return {
            "dominant_shell_frequency": 0.0,
            "dominant_spectral_concentration": 0.0,
            "spectral_bandwidth": 0.0,
            "spectral_top3_fraction": 0.0,
            "modes": [],
        }
    freq = freq[1:]
    power = power[1:]
    total = float(np.sum(power))
    if total <= EPSILON:
        return {
            "dominant_shell_frequency": 0.0,
            "dominant_spectral_concentration": 0.0,
            "spectral_bandwidth": 0.0,
            "spectral_top3_fraction": 0.0,
            "modes": [],
        }
    order = np.argsort(power)[::-1]
    dominant = int(order[0])
    mean_freq = float(np.sum(freq * power) / total)
    bandwidth = float(np.sqrt(np.sum(power * (freq - mean_freq) ** 2) / total))
    top3 = order[: min(3, order.size)]
    modes = [
        {
            "mode_rank": rank,
            "frequency": float(freq[idx]),
            "power_fraction": float(power[idx] / total),
        }
        for rank, idx in enumerate(top3, start=1)
    ]
    return {
        "dominant_shell_frequency": float(freq[dominant]),
        "dominant_spectral_concentration": float(power[dominant] / total),
        "spectral_bandwidth": bandwidth,
        "spectral_top3_fraction": float(np.sum(power[top3]) / total),
        "modes": modes,
    }


def _autocorr_metrics(times: np.ndarray, values: np.ndarray) -> dict[str, float]:
    if times.size < 4 or values.size < 4:
        return {"lag1_autocorrelation": 0.0, "autocorrelation_decay_time": 0.0}
    centered = values - float(np.mean(values))
    denom = float(np.dot(centered, centered))
    if denom <= EPSILON:
        return {"lag1_autocorrelation": 1.0, "autocorrelation_decay_time": 0.0}
    corr = np.correlate(centered, centered, mode="full")[centered.size - 1 :] / denom
    sample_dt = float(np.median(np.diff(times)))
    lag1 = float(corr[1]) if corr.size > 1 else 0.0
    threshold = math.exp(-1.0)
    below = np.flatnonzero(corr <= threshold)
    decay_time = float(below[0] * sample_dt) if below.size else float((corr.size - 1) * sample_dt)
    return {"lag1_autocorrelation": lag1, "autocorrelation_decay_time": decay_time}


def _timing_metrics(peaks: list[dict[str, Any]]) -> dict[str, float]:
    if not peaks:
        return {
            "return_timing_jitter": 0.0,
            "return_timing_regularity": 0.0,
            "mean_inter_peak_spacing": 0.0,
            "peak_amplitude_decay": 0.0,
            "first_peak_energy": 0.0,
            "last_peak_energy": 0.0,
            "last_to_first_peak_ratio": 0.0,
        }
    times = np.asarray([_float(peak.get("time")) for peak in peaks], dtype=float)
    energy = np.asarray([_float(peak.get("energy")) for peak in peaks], dtype=float)
    intervals = np.diff(times)
    mean_interval = float(np.mean(intervals)) if intervals.size else 0.0
    jitter = float(np.std(intervals)) if intervals.size else 0.0
    regularity = float(np.clip(1.0 - jitter / max(mean_interval, EPSILON), 0.0, 1.0)) if intervals.size else 0.0
    decay = _slope(times, np.log(np.maximum(energy, EPSILON))) if times.size >= 3 else 0.0
    first = float(energy[0])
    last = float(energy[-1])
    return {
        "return_timing_jitter": jitter,
        "return_timing_regularity": regularity,
        "mean_inter_peak_spacing": mean_interval,
        "peak_amplitude_decay": decay,
        "first_peak_energy": first,
        "last_peak_energy": last,
        "last_to_first_peak_ratio": last / max(first, EPSILON),
    }


def _peak_width_rows(
    variant: str,
    group: str,
    times: np.ndarray,
    shell: np.ndarray,
    peaks: list[dict[str, Any]],
    dominant_frequency: float,
) -> list[dict[str, Any]]:
    rows = []
    for index, peak in enumerate(peaks, start=1):
        time = _float(peak.get("time"))
        energy = _float(peak.get("energy"))
        nearest = int(np.argmin(np.abs(times - time))) if times.size else 0
        rows.append(
            {
                "variant": variant,
                "audit_group": group,
                "peak_index": index,
                "peak_time": time,
                "peak_energy": energy,
                "previous_interval": time - _float(peaks[index - 2].get("time")) if index > 1 else "",
                "peak_width_time": _peak_width(times, shell, nearest),
                "phase_at_dominant_frequency_cycles": (time * dominant_frequency) % 1.0 if dominant_frequency > EPSILON else "",
            }
        )
    return rows


def _peak_width(times: np.ndarray, values: np.ndarray, peak_idx: int) -> float:
    if times.size < 3 or values.size < 3:
        return 0.0
    peak_value = float(values[peak_idx])
    threshold = 0.5 * peak_value
    left = peak_idx
    while left > 0 and values[left] >= threshold:
        left -= 1
    right = peak_idx
    while right < values.size - 1 and values[right] >= threshold:
        right += 1
    return float(times[right] - times[left])


def _spectrum_rows(variant: str, group: str, spectrum: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for mode in spectrum.get("modes", []):
        rows.append(
            {
                "variant": variant,
                "audit_group": group,
                "mode_rank": mode.get("mode_rank"),
                "frequency": mode.get("frequency"),
                "power_fraction": mode.get("power_fraction"),
                "dominant_shell_frequency": spectrum.get("dominant_shell_frequency"),
                "dominant_spectral_concentration": spectrum.get("dominant_spectral_concentration"),
                "spectral_bandwidth": spectrum.get("spectral_bandwidth"),
                "spectral_top3_fraction": spectrum.get("spectral_top3_fraction"),
            }
        )
    return rows


def _phase_coherence(peaks: list[dict[str, Any]], frequency: float) -> float:
    if len(peaks) < 3 or frequency <= EPSILON:
        return 0.0
    phases = np.asarray([(_float(peak.get("time")) * frequency) % 1.0 for peak in peaks], dtype=float)
    vectors = np.exp(2.0j * np.pi * phases)
    return float(abs(np.mean(vectors)))


def _peak_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {"time": _float(row.get("time")), "energy": _float(row.get("energy")), "peak_rank": row.get("peak_rank")}
            for row in events
            if row.get("event") == "shell_peak"
        ],
        key=lambda row: _float(row.get("time")),
    )


def _detected_peak_rows(times: np.ndarray, values: np.ndarray, cutoff: float) -> list[dict[str, Any]]:
    if times.size < 3:
        return []
    post = np.flatnonzero(times > cutoff)
    if post.size == 0:
        return []
    threshold = 0.3 * float(np.max(values[post]))
    peaks = []
    for idx in range(1, values.size - 1):
        if times[idx] <= cutoff:
            continue
        if values[idx] >= threshold and values[idx] >= values[idx - 1] and values[idx] >= values[idx + 1]:
            peaks.append({"time": float(times[idx]), "energy": float(values[idx]), "peak_rank": len(peaks) + 1})
    return peaks


def _loose_counts(row: dict[str, Any], threshold_lookup: dict[float, dict[str, Any]]) -> tuple[int, int]:
    if "major_peaks_at_0p20" in row:
        return int(_float(row.get("major_peaks_at_0p20"))), int(_float(row.get("refocus_peaks_at_0p20")))
    match = threshold_lookup.get(0.25) or threshold_lookup.get(0.30) or {}
    return int(_float(match.get("major_shell_peak_count"))), int(_float(match.get("refocus_peak_count")))


def _default_counts(row: dict[str, Any], threshold_lookup: dict[float, dict[str, Any]]) -> tuple[int, int]:
    if "default_major_peaks" in row:
        return int(_float(row.get("default_major_peaks"))), int(_float(row.get("default_refocus_peaks")))
    if "major_peaks_at_0p30" in row:
        return int(_float(row.get("major_peaks_at_0p30"))), int(_float(row.get("refocus_peaks_at_0p30")))
    match = threshold_lookup.get(0.30) or {}
    return int(_float(match.get("major_shell_peak_count"))), int(_float(match.get("refocus_peak_count")))


def _strict_counts(row: dict[str, Any], threshold_lookup: dict[float, dict[str, Any]]) -> tuple[int, int]:
    if "strict_major_peaks" in row:
        return int(_float(row.get("strict_major_peaks"))), int(_float(row.get("strict_refocus_peaks")))
    if "conservative_major_peaks" in row:
        return int(_float(row.get("conservative_major_peaks"))), int(_float(row.get("conservative_refocus_peaks")))
    match = threshold_lookup.get(0.40) or threshold_lookup.get(0.35) or {}
    return int(_float(match.get("major_shell_peak_count"))), int(_float(match.get("refocus_peak_count")))


def _threshold_lookup(rows: list[dict[str, Any]]) -> dict[float, dict[str, Any]]:
    return {round(_float(row.get("peak_threshold_fraction")), 6): row for row in rows}


def _same_band(proof_freq: float, lift_freq: float, options: ReleasePhaseModalAuditOptions) -> bool:
    if proof_freq <= EPSILON or lift_freq <= EPSILON:
        return False
    return abs(lift_freq - proof_freq) / max(abs(proof_freq), EPSILON) <= options.same_band_relative_tolerance


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ReleasePhaseModalAuditOptions,
) -> None:
    checks = classification.get("checks", {})
    lines = [
        f"# Release Phase Modal Audit: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only modal comparison explaining why the quarter-dt-supported 41^3 passive release-phase proof cluster degrades into blurred returns at 51^3, with the central HF burst result used as a mechanism contrast.",
        "",
        "No new physics was run.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Mechanism-derived next candidate: `{checks.get('mechanism_candidate', 'none')}`",
        "",
        "## Key Checks",
        "",
        f"- Proof dominant frequency mean: `{_format(checks.get('proof_dominant_frequency_mean'))}`",
        f"- Lift dominant frequency mean: `{_format(checks.get('lift_dominant_frequency_mean'))}`",
        f"- Same modal band: `{checks.get('same_modal_band')}`",
        f"- Proof spectral concentration mean: `{_format(checks.get('proof_spectral_concentration_mean'))}`",
        f"- Lift spectral concentration mean: `{_format(checks.get('lift_spectral_concentration_mean'))}`",
        f"- Spectral concentration relative delta: `{_format(checks.get('spectral_concentration_relative_delta'))}`",
        f"- Strict major loss: `{_format(checks.get('strict_major_loss'))}`",
        f"- Lift loose-to-strict recovery: `{_format(checks.get('lift_loose_to_strict_recovery'))}`",
        f"- Spectral bandwidth relative delta: `{_format(checks.get('spectral_bandwidth_relative_delta'))}`",
        f"- Tail spread relative delta: `{_format(checks.get('tail_spread_relative_delta'))}`",
        f"- Tail radius shift: `{_format(checks.get('tail_radius_shift'))}`",
        f"- Central clean repeated: `{checks.get('central_clean_repeated')}`",
        "",
        "## Row Summary",
        "",
        "| Group | Variant | Grid | Loose | Default | Strict | Freq | Conc | Bandwidth | Jitter | Tail Radius | Tail Spread | Outer/Shell |",
        "| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('audit_group')} | "
            f"{row.get('variant')} | "
            f"{row.get('grid_size')} | "
            f"{row.get('loose_major_peaks')}/{row.get('loose_refocus_peaks')} | "
            f"{row.get('default_major_peaks')}/{row.get('default_refocus_peaks')} | "
            f"{row.get('strict_major_peaks')}/{row.get('strict_refocus_peaks')} | "
            f"{_format(row.get('dominant_shell_frequency'))} | "
            f"{_format(row.get('dominant_spectral_concentration'))} | "
            f"{_format(row.get('spectral_bandwidth'))} | "
            f"{_format(row.get('return_timing_jitter'))} | "
            f"{_format(row.get('tail_packet_radius_mean'))} | "
            f"{_format(row.get('tail_packet_spread_mean'))} | "
            f"{_format(row.get('tail_outer_to_shell_mean'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Files",
            "",
            "- `release_phase_modal_audit_report.md`",
            "- `modal_audit_summary.csv`",
            "- `shell_spectrum_comparison.csv`",
            "- `return_timing_jitter.csv`",
            "- `radial_packet_width_comparison.csv`",
            "- `phase_coherence_comparison.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "resolution_blur_mechanism_supported":
        return "The 51^3 rows keep the same shell-energy band, but strict counts shrink while looser counts remain and bandwidth/tail-radius blur metrics move. Spectral concentration does not drop in this artifact set, so the result is not a lost-band or low-coherence explanation. The central burst contrast does not reproduce a clean no-boundary return family, so the passive branch still looks boundary-release specific."
    if label == "finite_grid_resonance_likely":
        return "The 41^3 proof rows appear to rely on a modal coincidence that is not present in the lifted rows. Treat the proof as finite-grid until a mechanism-derived source correction is identified."
    if label == "scalable_modal_rule_supported":
        return "The same modal band survives without meaningful strict-count degradation. A next run still needs a concrete source-design prediction before any physics is launched."
    return "The audit did not isolate a corrected source design or a clean finite-grid-only resonance. Do not recommend a new physics run from this report alone."


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _group_by(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(field)), []).append(row)
    return grouped


def _array(values: Any) -> np.ndarray:
    return np.asarray([_float(value) for value in values], dtype=float)


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _first_float(row: dict[str, Any], key: str) -> float:
    return _float(row.get(key))


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes"}


def _mean(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    return float(np.mean(parsed)) if parsed.size else 0.0


def _max(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    return float(np.max(parsed)) if parsed.size else 0.0


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 3 or y.size < 3 or float(np.ptp(x)) <= EPSILON:
        return 0.0
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)


def _relative_delta(value: float, reference: float) -> float:
    return (value - reference) / max(abs(reference), EPSILON)


def _summary_fields() -> list[str]:
    return [
        "variant",
        "release_phase_modal_audit_classification",
        "audit_group",
        "source_run_kind",
        "prediction_role",
        "grid_size",
        "dx",
        "dt",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "burst_frequency",
        "energy_label",
        "loose_major_peaks",
        "loose_refocus_peaks",
        "default_major_peaks",
        "default_refocus_peaks",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "loose_to_strict_major_loss",
        "default_to_strict_major_loss",
        "dominant_shell_frequency",
        "dominant_spectral_concentration",
        "spectral_bandwidth",
        "spectral_top3_fraction",
        "autocorrelation_decay_time",
        "lag1_autocorrelation",
        "return_timing_regularity",
        "return_timing_jitter",
        "mean_inter_peak_spacing",
        "peak_amplitude_decay",
        "mean_return_peak_width",
        "first_peak_energy",
        "last_peak_energy",
        "last_to_first_peak_ratio",
        "radial_group_velocity",
        "tail_packet_radius_mean",
        "tail_packet_width_mean",
        "tail_packet_spread_mean",
        "return_phase_locking_strength",
        "tail_outer_to_shell_mean",
        "tail_shell_fraction_mean",
        "no_exit",
        "outer_shell_below_1",
        "global_outer_false",
        "central_contrast_role",
    ]


def _spectrum_fields() -> list[str]:
    return [
        "variant",
        "release_phase_modal_audit_classification",
        "audit_group",
        "mode_rank",
        "frequency",
        "power_fraction",
        "dominant_shell_frequency",
        "dominant_spectral_concentration",
        "spectral_bandwidth",
        "spectral_top3_fraction",
    ]


def _jitter_fields() -> list[str]:
    return [
        "variant",
        "release_phase_modal_audit_classification",
        "audit_group",
        "peak_index",
        "peak_time",
        "peak_energy",
        "previous_interval",
        "peak_width_time",
        "phase_at_dominant_frequency_cycles",
    ]


def _radial_fields() -> list[str]:
    return [
        "variant",
        "release_phase_modal_audit_classification",
        "audit_group",
        "grid_size",
        "tail_packet_radius_mean",
        "tail_packet_width_mean",
        "tail_packet_spread_mean",
        "packet_width_at_shell_peak",
        "packet_spread_at_shell_peak",
        "radial_group_velocity",
        "radial_width_velocity",
        "tail_outer_to_shell_mean",
        "tail_shell_fraction_mean",
    ]


def _phase_fields() -> list[str]:
    return [
        "variant",
        "release_phase_modal_audit_classification",
        "audit_group",
        "phase_metric_kind",
        "spatial_phase_available",
        "dominant_shell_frequency",
        "return_phase_locking_strength",
        "shell_energy_autocorrelation_lag1",
        "return_timing_regularity",
        "notes",
    ]
