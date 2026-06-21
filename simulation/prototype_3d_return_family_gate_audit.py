"""Read-only return-family gate audit for 41^3 proof versus 51^3 strict-count loss."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .prototype_3d import EPSILON
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_PROOF_ROOT = "runs/release_phase_proof_pack_3d_20260619_234039"
DEFAULT_LIFT_ROOT = "runs/release_phase_resolution_lift_3d_20260620_091834"
DEFAULT_SPATIAL_PHASE_ROOT = "runs/spatial_phase_instrumentation_3d_20260620_170518"
DEFAULT_SMOOTH_ROOT = "runs/smooth_envelope_resolution_lift_3d_20260620_192501"
DEFAULT_PHASE_CONJUGATE_ROOT = "runs/boundary_phase_conjugate_3d_20260620_212918"
DEFAULT_MODAL_SPARSITY_ROOT = "runs/modal_sparsity_audit_3d_20260620_231602"


@dataclass(frozen=True)
class ReturnFamilyGateAuditOptions:
    """Options for the read-only return-family gate audit."""

    output_root: str = "runs"
    proof_root: str = DEFAULT_PROOF_ROOT
    lift_root: str = DEFAULT_LIFT_ROOT
    spatial_phase_root: str = DEFAULT_SPATIAL_PHASE_ROOT
    smooth_root: str = DEFAULT_SMOOTH_ROOT
    phase_conjugate_root: str = DEFAULT_PHASE_CONJUGATE_ROOT
    modal_sparsity_root: str = DEFAULT_MODAL_SPARSITY_ROOT
    early_interval_count: int = 4
    window_half_width_fraction: float = 0.24
    min_window_half_width: float = 0.75
    max_return_windows: int = 12
    local_background_period_fraction: float = 0.50
    low_off_comb_ratio: float = 0.45
    high_off_comb_ratio: float = 0.75
    min_occupancy_fraction: float = 0.78
    min_comb_score_ratio: float = 0.70
    amplitude_compression_threshold: float = 0.85
    min_strict_major_loss: float = 1.0
    period_cv_threshold: float = 0.14
    thresholds: tuple[float, ...] = (0.20, 0.25, 0.30, 0.35, 0.40)


def run_3d_return_family_gate_audit(
    *,
    options: ReturnFamilyGateAuditOptions | None = None,
) -> dict[str, Any]:
    """Analyze whether 51^3 strict-count loss is return-family loss or gate artifact."""

    options = options or ReturnFamilyGateAuditOptions()
    control_id = datetime.now().strftime("return_family_gate_audit_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    records = _load_records(options)
    if not records:
        classification = classify_return_family_gate_audit([], options)
        return _write_empty_outputs(root, control_id, classification)

    summary_rows: list[dict[str, Any]] = []
    occupancy_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    amplitude_rows: list[dict[str, Any]] = []

    for record in records:
        summary, occupancy, thresholds, amplitudes = _diagnose_record(record, options)
        summary_rows.append(summary)
        occupancy_rows.extend(occupancy)
        threshold_rows.extend(thresholds)
        amplitude_rows.extend(amplitudes)

    _add_rank_normalized_strength(summary_rows, amplitude_rows)
    classification = classify_return_family_gate_audit(summary_rows, options)
    for collection in (summary_rows, occupancy_rows, threshold_rows, amplitude_rows):
        for row in collection:
            row["return_family_gate_classification"] = classification["label"]

    summary_csv = root / "return_family_gate_summary.csv"
    occupancy_csv = root / "return_window_occupancy.csv"
    threshold_csv = root / "threshold_crossing_table.csv"
    amplitude_csv = root / "return_amplitude_by_index.csv"
    report_path = root / "return_family_gate_report.md"
    summary_json = root / "return_family_gate_summary.json"
    plots = {
        "indexed_return_strength_plot": root / "indexed_return_strength_plot.png",
        "threshold_crossings_plot": root / "threshold_crossings_plot.png",
        "comb_score_plot": root / "comb_score_plot.png",
        "off_comb_energy_ratio_plot": root / "off_comb_energy_ratio_plot.png",
    }

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(occupancy_csv, occupancy_rows, _occupancy_fields())
    _write_csv(threshold_csv, threshold_rows, _threshold_fields())
    _write_csv(amplitude_csv, amplitude_rows, _amplitude_fields())
    _write_plots(plots, summary_rows, threshold_rows, amplitude_rows)
    _write_report(report_path, control_id, summary_rows, classification, plots, options)
    summary_json.write_text(
        json.dumps(
            {
                "control_id": control_id,
                "classification": classification,
                "row_count": len(summary_rows),
                "summary_csv": str(summary_csv),
                "occupancy_csv": str(occupancy_csv),
                "threshold_csv": str(threshold_csv),
                "amplitude_csv": str(amplitude_csv),
                "report_path": str(report_path),
                "plots": {key: str(value) for key, value in plots.items()},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": summary_rows,
        "occupancy_rows": occupancy_rows,
        "threshold_rows": threshold_rows,
        "amplitude_rows": amplitude_rows,
        "summary_csv": str(summary_csv),
        "occupancy_csv": str(occupancy_csv),
        "threshold_csv": str(threshold_csv),
        "amplitude_csv": str(amplitude_csv),
        "report_path": str(report_path),
        "summary_json": str(summary_json),
        "plots": {key: str(value) for key, value in plots.items()},
        "path": str(root),
    }


def classify_return_family_gate_audit(
    rows: list[dict[str, Any]],
    options: ReturnFamilyGateAuditOptions | None = None,
) -> dict[str, Any]:
    """Classify strict-count loss as gate artifact, real weakening, inconclusive, or missing."""

    options = options or ReturnFamilyGateAuditOptions()
    proof = _proof_rows(rows)
    controls_51 = _source_control_rows(rows)
    if not proof or len(controls_51) < 3:
        return {
            "label": "insufficient_artifacts",
            "reason": "Required proof and 51^3 source-control timeseries/events were not available.",
            "checks": {
                "proof_row_count": len(proof),
                "source_control_row_count": len(controls_51),
                "mechanism_candidate": "none",
            },
        }

    proof_strict = _mean(row.get("strict_major_peaks") for row in proof)
    control_strict = _mean(row.get("strict_major_peaks") for row in controls_51)
    strict_loss = proof_strict - control_strict
    proof_occupancy = _mean(row.get("return_window_occupancy_fraction") for row in proof)
    control_occupancy = _mean(row.get("return_window_occupancy_fraction") for row in controls_51)
    proof_comb = _mean(row.get("return_comb_score") for row in proof)
    control_comb = _mean(row.get("return_comb_score") for row in controls_51)
    control_off_comb = _mean(row.get("off_comb_energy_ratio") for row in controls_51)
    control_period_cv = _mean(row.get("predicted_return_period_cv") for row in controls_51)
    control_strength = _mean(row.get("mean_rank_normalized_return_strength") for row in controls_51)
    proof_strength = _mean(row.get("mean_rank_normalized_return_strength") for row in proof)
    strength_ratio = control_strength / max(proof_strength, EPSILON)
    control_late_survival = _mean(row.get("late_return_area_survival_fraction") for row in controls_51)
    proof_late_survival = _mean(row.get("late_return_area_survival_fraction") for row in proof)
    control_prominence = _mean(row.get("mean_peak_prominence_ratio") for row in controls_51)
    proof_prominence = _mean(row.get("mean_peak_prominence_ratio") for row in proof)
    prominence_ratio = control_prominence / max(proof_prominence, EPSILON)
    occupancy_preserved = (
        control_occupancy >= options.min_occupancy_fraction
        or control_occupancy >= 0.85 * max(proof_occupancy, EPSILON)
    )
    comb_preserved = control_comb >= options.min_comb_score_ratio * max(proof_comb, EPSILON)
    timing_coherent = control_period_cv <= options.period_cv_threshold
    off_comb_low = control_off_comb <= options.low_off_comb_ratio
    amplitude_compressed = strength_ratio <= options.amplitude_compression_threshold or prominence_ratio <= options.amplitude_compression_threshold
    lost_occupancy = control_occupancy < 0.65 * max(proof_occupancy, EPSILON)
    high_off_comb = control_off_comb >= options.high_off_comb_ratio
    checks = {
        "proof_row_count": len(proof),
        "source_control_row_count": len(controls_51),
        "proof_strict_major_mean": proof_strict,
        "source_control_strict_major_mean": control_strict,
        "strict_major_loss": strict_loss,
        "proof_occupancy_mean": proof_occupancy,
        "source_control_occupancy_mean": control_occupancy,
        "proof_comb_score_mean": proof_comb,
        "source_control_comb_score_mean": control_comb,
        "source_control_off_comb_energy_ratio_mean": control_off_comb,
        "source_control_period_cv_mean": control_period_cv,
        "rank_normalized_strength_ratio": strength_ratio,
        "prominence_ratio": prominence_ratio,
        "proof_late_survival_mean": proof_late_survival,
        "source_control_late_survival_mean": control_late_survival,
        "occupancy_preserved": occupancy_preserved,
        "comb_preserved": comb_preserved,
        "timing_coherent": timing_coherent,
        "off_comb_low": off_comb_low,
        "amplitude_compressed": amplitude_compressed,
        "mechanism_candidate": "none",
    }
    if (
        strict_loss >= options.min_strict_major_loss
        and occupancy_preserved
        and comb_preserved
        and timing_coherent
        and off_comb_low
        and amplitude_compressed
    ):
        return {
            "label": "return_family_survives_gate_artifact_supported",
            "reason": "The 51^3 rows preserve return-window occupancy, comb timing, and low off-comb energy; strict-count loss is most consistent with amplitude/prominence compression against fixed gates.",
            "checks": checks,
        }
    if strict_loss >= options.min_strict_major_loss and (lost_occupancy or high_off_comb):
        return {
            "label": "return_family_weakened_not_gate_artifact",
            "reason": "The 51^3 rows lose predicted return-window occupancy or move too much energy off the return comb, so the strict-count loss is a real return-family degradation.",
            "checks": checks,
        }
    return {
        "label": "return_family_inconclusive",
        "reason": "Existing artifacts show strict-count loss, but occupancy/off-comb/prominence metrics do not cleanly separate gate artifact from real return-family weakening.",
        "checks": checks,
    }


def build_return_windows(
    peak_times: list[float],
    *,
    max_time: float,
    options: ReturnFamilyGateAuditOptions | None = None,
) -> dict[str, Any]:
    """Construct predicted return windows from early post-cutoff peak times."""

    options = options or ReturnFamilyGateAuditOptions()
    clean_times = [float(time) for time in peak_times if math.isfinite(float(time))]
    if len(clean_times) < 2:
        return {"period": 0.0, "period_cv": 0.0, "windows": []}
    interval_count = min(options.early_interval_count, len(clean_times) - 1)
    early_intervals = np.diff(np.asarray(clean_times[: interval_count + 1], dtype=float))
    period = float(np.median(early_intervals)) if early_intervals.size else 0.0
    period_cv = float(np.std(early_intervals) / max(abs(period), EPSILON)) if early_intervals.size else 0.0
    if period <= EPSILON:
        return {"period": 0.0, "period_cv": 0.0, "windows": []}
    half_width = max(options.min_window_half_width, options.window_half_width_fraction * period)
    windows = []
    center = clean_times[0]
    index = 1
    while center <= max_time + half_width and index <= options.max_return_windows:
        windows.append(
            {
                "return_index": index,
                "predicted_time": center,
                "window_start": center - half_width,
                "window_end": center + half_width,
                "window_half_width": half_width,
            }
        )
        center += period
        index += 1
    return {"period": period, "period_cv": period_cv, "windows": windows}


def calculate_comb_score(occupancy_fraction: float, on_comb_energy_fraction: float, period_cv: float) -> float:
    """Score a return comb by occupancy, on-comb energy, and timing regularity."""

    timing = float(np.clip(1.0 - period_cv, 0.0, 1.0))
    return float(np.clip(occupancy_fraction, 0.0, 1.0) * np.clip(on_comb_energy_fraction, 0.0, 1.0) * timing)


def calculate_off_comb_energy_ratio(total_energy: float, on_comb_energy: float) -> float:
    """Return off/on comb energy ratio with a stable zero guard."""

    return max(total_energy - on_comb_energy, 0.0) / max(on_comb_energy, EPSILON)


def build_threshold_crossing_rows(
    *,
    variant: str,
    artifact_source: str,
    audit_group: str,
    row: dict[str, Any],
    peaks: list[dict[str, Any]],
    thresholds: tuple[float, ...],
) -> list[dict[str, Any]]:
    """Build threshold crossing rows from artifact counts plus event amplitudes."""

    max_peak = max((_float(peak.get("energy")) for peak in peaks), default=0.0)
    out = []
    for threshold in thresholds:
        suffix = _threshold_suffix(threshold)
        artifact_major = _first(
            row,
            f"loose_major_peaks_at_{suffix}",
            f"major_peaks_at_{suffix}",
            f"default_major_peaks_at_{suffix}",
            f"strict_major_peaks_at_{suffix}",
        )
        artifact_refocus = _first(
            row,
            f"loose_refocus_peaks_at_{suffix}",
            f"refocus_peaks_at_{suffix}",
            f"default_refocus_peaks_at_{suffix}",
            f"strict_refocus_peaks_at_{suffix}",
        )
        peak_crossing = sum(1 for peak in peaks if max_peak > EPSILON and _float(peak.get("energy")) >= threshold * max_peak)
        out.append(
            {
                "variant": variant,
                "artifact_source": artifact_source,
                "audit_group": audit_group,
                "threshold": threshold,
                "artifact_major_peaks": int(artifact_major) if artifact_major > 0 else "",
                "artifact_refocus_peaks": int(artifact_refocus) if artifact_refocus > 0 else "",
                "event_peak_crossing_count": peak_crossing,
                "max_peak_energy": max_peak,
                "threshold_energy": threshold * max_peak,
            }
        )
    return out


def _load_records(options: ReturnFamilyGateAuditOptions) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    records.extend(
        _records_from_row_folders(
            root=Path(options.proof_root),
            summary_name="release_phase_proof_pack_summary.csv",
            threshold_name="release_phase_proof_pack_threshold_robust_score.csv",
            artifact_source="proof_pack",
            audit_group="proof_41",
        )
    )
    records.extend(
        _records_from_row_folders(
            root=Path(options.lift_root),
            summary_name="release_phase_resolution_lift_summary.csv",
            threshold_name="release_phase_resolution_lift_threshold_robust_score.csv",
            artifact_source="resolution_lift",
            audit_group="lift_51",
        )
    )
    records.extend(
        _records_from_aggregate(
            root=Path(options.spatial_phase_root),
            summary_name="spatial_phase_instrumentation_summary.csv",
            threshold_name="spatial_phase_threshold_robust_score.csv",
            timeseries_name="spatial_phase_lifecycle_timeseries.csv",
            events_name="spatial_phase_lifecycle_events.csv",
            artifact_source="spatial_phase_instrumentation",
            fallback_audit_group="spatial_phase",
            audit_group_field="audit_group",
        )
    )
    records.extend(
        _records_from_aggregate(
            root=Path(options.smooth_root),
            summary_name="smooth_envelope_resolution_lift_summary.csv",
            threshold_name="smooth_envelope_threshold_robust_score.csv",
            timeseries_name="smooth_envelope_lifecycle_timeseries.csv",
            events_name="smooth_envelope_lifecycle_events.csv",
            artifact_source="smooth_envelope",
            fallback_audit_group="smooth_51",
        )
    )
    records.extend(
        _records_from_aggregate(
            root=Path(options.phase_conjugate_root),
            summary_name="boundary_phase_conjugate_summary.csv",
            threshold_name="boundary_phase_conjugate_threshold_robust_score.csv",
            timeseries_name="boundary_phase_conjugate_lifecycle_timeseries.csv",
            events_name="boundary_phase_conjugate_lifecycle_events.csv",
            artifact_source="boundary_phase_conjugate",
            fallback_audit_group="phase_conjugate_51",
        )
    )
    modal_by_variant = {row.get("variant"): row for row in _read_csv(Path(options.modal_sparsity_root) / "modal_sparsity_summary.csv")}
    for record in records:
        record["modal_sparsity"] = modal_by_variant.get(record["variant"], {})
    return [record for record in records if record.get("timeseries") and record.get("events")]


def _records_from_row_folders(
    *,
    root: Path,
    summary_name: str,
    threshold_name: str,
    artifact_source: str,
    audit_group: str,
) -> list[dict[str, Any]]:
    summary_rows = _merge_threshold_rows(root / summary_name, root / threshold_name)
    records = []
    for row in summary_rows:
        variant = str(row.get("variant"))
        records.append(
            {
                "artifact_source": artifact_source,
                "audit_group": audit_group,
                "variant": variant,
                "summary": row,
                "timeseries": _read_csv(root / variant / "packet_lifecycle_timeseries.csv"),
                "events": _read_csv(root / variant / "packet_lifecycle_events.csv"),
            }
        )
    return records


def _records_from_aggregate(
    *,
    root: Path,
    summary_name: str,
    threshold_name: str,
    timeseries_name: str,
    events_name: str,
    artifact_source: str,
    fallback_audit_group: str,
    audit_group_field: str | None = None,
) -> list[dict[str, Any]]:
    summary_rows = _merge_threshold_rows(root / summary_name, root / threshold_name)
    timeseries_by_variant = _group_by(_read_csv(root / timeseries_name), "variant")
    events_by_variant = _group_by(_read_csv(root / events_name), "variant")
    records = []
    for row in summary_rows:
        variant = str(row.get("variant"))
        records.append(
            {
                "artifact_source": artifact_source,
                "audit_group": str(row.get(audit_group_field or "")) or fallback_audit_group,
                "variant": variant,
                "summary": row,
                "timeseries": timeseries_by_variant.get(variant, []),
                "events": events_by_variant.get(variant, []),
            }
        )
    return records


def _diagnose_record(
    record: dict[str, Any],
    options: ReturnFamilyGateAuditOptions,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    row = record["summary"]
    variant = record["variant"]
    artifact_source = record["artifact_source"]
    audit_group = record["audit_group"]
    role = str(row.get("prediction_role") or row.get("patch_mode") or row.get("audit_group") or "")
    grid_size = int(_first(row, "grid_size"))
    times = _array(ts.get("time") for ts in record["timeseries"])
    shell = _array(ts.get("shell_window_energy") for ts in record["timeseries"])
    cutoff = _first(row, "drive_cutoff_time")
    peaks = [peak for peak in _peak_rows(record["events"]) if _float(peak.get("time")) > cutoff]
    max_time = float(np.max(times)) if times.size else 0.0
    comb = build_return_windows([_float(peak.get("time")) for peak in peaks], max_time=max_time, options=options)
    occupancy_rows, amplitude_rows, window_stats = _window_rows(
        variant=variant,
        artifact_source=artifact_source,
        audit_group=audit_group,
        times=times,
        shell=shell,
        peaks=peaks,
        windows=comb["windows"],
        period=comb["period"],
        options=options,
    )
    total_post_energy = _integrate(times[times > cutoff], shell[times > cutoff]) if times.size else 0.0
    on_comb_energy = sum(_float(win.get("window_energy")) for win in occupancy_rows)
    off_comb_ratio = calculate_off_comb_energy_ratio(total_post_energy, on_comb_energy)
    on_comb_fraction = on_comb_energy / max(total_post_energy, EPSILON)
    occupancy_fraction = _mean(win.get("occupied") for win in occupancy_rows)
    comb_score = calculate_comb_score(occupancy_fraction, on_comb_fraction, comb["period_cv"])
    counts = _count_metrics(row)
    threshold_rows = build_threshold_crossing_rows(
        variant=variant,
        artifact_source=artifact_source,
        audit_group=audit_group,
        row=row,
        peaks=peaks,
        thresholds=options.thresholds,
    )
    summary = {
        "variant": variant,
        "artifact_source": artifact_source,
        "audit_group": audit_group,
        "prediction_role": role,
        "grid_size": grid_size,
        "dt": row.get("dt"),
        "drive_cutoff_time": cutoff,
        "cutoff_phase_cycles": row.get("cutoff_phase_cycles") or row.get("target_release_phase"),
        "strict_major_peaks": counts["strict_major_peaks"],
        "strict_refocus_peaks": counts["strict_refocus_peaks"],
        "default_major_peaks": counts["default_major_peaks"],
        "default_refocus_peaks": counts["default_refocus_peaks"],
        "loose_major_peaks": counts["loose_major_peaks"],
        "loose_refocus_peaks": counts["loose_refocus_peaks"],
        "predicted_return_period": comb["period"],
        "predicted_return_period_cv": comb["period_cv"],
        "predicted_window_count": len(comb["windows"]),
        "occupied_window_count": sum(1 for win in occupancy_rows if _bool(win.get("occupied"))),
        "return_window_occupancy_fraction": occupancy_fraction,
        "return_comb_score": comb_score,
        "on_comb_energy": on_comb_energy,
        "post_cutoff_energy": total_post_energy,
        "on_comb_energy_fraction": on_comb_fraction,
        "off_comb_energy": max(total_post_energy - on_comb_energy, 0.0),
        "off_comb_energy_ratio": off_comb_ratio,
        "mean_peak_prominence_ratio": _mean(win.get("prominence_ratio") for win in amplitude_rows),
        "mean_peak_prominence_over_background": _mean(win.get("prominence_over_background") for win in amplitude_rows),
        "mean_return_peak_energy": _mean(win.get("peak_energy") for win in amplitude_rows),
        "mean_rank_normalized_return_strength": "",
        "amplitude_compression_vs_41": "",
        "early_window_energy": window_stats["early_window_energy"],
        "late_window_energy": window_stats["late_window_energy"],
        "late_return_area_survival_fraction": window_stats["late_return_area_survival_fraction"],
        "tail_area_after_t50": _first(row, "threshold_free_tail_area_after_t50", "tail_area_after_t50", "threshold_free_tail_energy_area_after_t50"),
        "modal_modes_for_99pct": _first(record.get("modal_sparsity", {}), "modes_for_99pct"),
        "modal_participation_ratio": _first(record.get("modal_sparsity", {}), "modal_participation_ratio"),
        "no_exit": _bool(row.get("no_exit")) if "no_exit" in row else not _bool(row.get("shell_exit_detected")),
        "global_outer_false": _bool(row.get("global_outer_false")) if "global_outer_false" in row else not _bool(row.get("global_peak_in_outer_window")),
    }
    return summary, occupancy_rows, threshold_rows, amplitude_rows


def _window_rows(
    *,
    variant: str,
    artifact_source: str,
    audit_group: str,
    times: np.ndarray,
    shell: np.ndarray,
    peaks: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    period: float,
    options: ReturnFamilyGateAuditOptions,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    occupancy_rows = []
    amplitude_rows = []
    peak_times = np.asarray([_float(peak.get("time")) for peak in peaks], dtype=float)
    peak_energy = np.asarray([_float(peak.get("energy")) for peak in peaks], dtype=float)
    for window in windows:
        start = _float(window.get("window_start"))
        end = _float(window.get("window_end"))
        center = _float(window.get("predicted_time"))
        mask = (times >= start) & (times <= end) if times.size else np.asarray([], dtype=bool)
        window_energy = _integrate(times[mask], shell[mask])
        peak_mask = (peak_times >= start) & (peak_times <= end) if peak_times.size else np.asarray([], dtype=bool)
        occupied = bool(np.any(peak_mask))
        if occupied:
            local_idx = int(np.argmax(peak_energy[peak_mask]))
            candidate_indices = np.flatnonzero(peak_mask)
            peak_idx = int(candidate_indices[local_idx])
            peak_time = float(peak_times[peak_idx])
            peak_value = float(peak_energy[peak_idx])
        elif mask.any():
            idxs = np.flatnonzero(mask)
            peak_idx_ts = int(idxs[np.argmax(shell[mask])])
            peak_time = float(times[peak_idx_ts])
            peak_value = float(shell[peak_idx_ts])
        else:
            peak_time = 0.0
            peak_value = 0.0
        background = _local_background(times, shell, center, period, start, end, options)
        prominence_ratio = peak_value / max(background, EPSILON)
        prominence_over_background = (peak_value - background) / max(peak_value, EPSILON) if peak_value > EPSILON else 0.0
        row = {
            "variant": variant,
            "artifact_source": artifact_source,
            "audit_group": audit_group,
            "return_index": window["return_index"],
            "predicted_time": center,
            "window_start": start,
            "window_end": end,
            "window_half_width": window["window_half_width"],
            "occupied": occupied,
            "peak_time": peak_time,
            "peak_time_error": peak_time - center if peak_time else "",
            "peak_energy": peak_value,
            "local_background_energy": background,
            "prominence_ratio": prominence_ratio,
            "prominence_over_background": prominence_over_background,
            "window_energy": window_energy,
        }
        occupancy_rows.append(row)
        amplitude_rows.append(
            {
                **row,
                "row_peak_fraction_of_max": "",
                "proof_reference_rank_fraction": "",
                "rank_normalized_return_strength": "",
            }
        )
    early = [row for row in occupancy_rows if int(row["return_index"]) <= 3]
    late = [row for row in occupancy_rows if int(row["return_index"]) >= 6 or _float(row.get("predicted_time")) >= 50.0]
    early_energy = _mean(row.get("window_energy") for row in early)
    late_energy = _mean(row.get("window_energy") for row in late)
    stats = {
        "early_window_energy": early_energy,
        "late_window_energy": late_energy,
        "late_return_area_survival_fraction": late_energy / max(early_energy, EPSILON) if early else 0.0,
    }
    return occupancy_rows, amplitude_rows, stats


def _add_rank_normalized_strength(summary_rows: list[dict[str, Any]], amplitude_rows: list[dict[str, Any]]) -> None:
    variant_max: dict[str, float] = {}
    for row in amplitude_rows:
        variant = str(row.get("variant"))
        variant_max[variant] = max(variant_max.get(variant, 0.0), _float(row.get("peak_energy")))
    for row in amplitude_rows:
        row["row_peak_fraction_of_max"] = _float(row.get("peak_energy")) / max(variant_max.get(str(row.get("variant")), 0.0), EPSILON)
    proof_reference: dict[int, float] = {}
    for index in sorted({int(_float(row.get("return_index"))) for row in amplitude_rows}):
        proof_values = [
            _float(row.get("row_peak_fraction_of_max"))
            for row in amplitude_rows
            if int(_float(row.get("return_index"))) == index and row.get("audit_group") == "proof_41"
        ]
        if proof_values:
            proof_reference[index] = float(np.median(proof_values))
    strengths_by_variant: dict[str, list[float]] = {}
    for row in amplitude_rows:
        index = int(_float(row.get("return_index")))
        reference = proof_reference.get(index, 0.0)
        strength = _float(row.get("row_peak_fraction_of_max")) / max(reference, EPSILON) if reference > EPSILON else 0.0
        row["proof_reference_rank_fraction"] = reference
        row["rank_normalized_return_strength"] = strength
        strengths_by_variant.setdefault(str(row.get("variant")), []).append(strength)
    proof_strength = _mean(
        strength
        for row in amplitude_rows
        if row.get("audit_group") == "proof_41"
        for strength in [_float(row.get("rank_normalized_return_strength"))]
    )
    for row in summary_rows:
        strengths = strengths_by_variant.get(str(row.get("variant")), [])
        mean_strength = _mean(strengths)
        row["mean_rank_normalized_return_strength"] = mean_strength
        row["amplitude_compression_vs_41"] = mean_strength / max(proof_strength, EPSILON) if proof_strength > EPSILON else 0.0


def _local_background(
    times: np.ndarray,
    shell: np.ndarray,
    center: float,
    period: float,
    start: float,
    end: float,
    options: ReturnFamilyGateAuditOptions,
) -> float:
    if times.size == 0 or period <= EPSILON:
        return 0.0
    span = options.local_background_period_fraction * period
    outer = (times >= center - span) & (times <= center + span)
    inner = (times >= start) & (times <= end)
    background = shell[outer & ~inner]
    if background.size == 0:
        return float(np.median(shell[outer])) if np.any(outer) else 0.0
    return float(np.median(background))


def _integrate(times: np.ndarray, values: np.ndarray) -> float:
    if times.size < 2 or values.size < 2:
        return 0.0
    return float(np.trapz(values, times))


def _proof_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("audit_group") == "proof_41" and row.get("prediction_role") in {"proof_candidate", "upper_immediate_control"}
    ] or [row for row in rows if row.get("audit_group") == "proof_41"]


def _source_control_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = {
        "resolution_lift:candidate",
        "smooth_envelope:hard_cutoff_control",
        "smooth_envelope:smooth_candidate",
        "smooth_envelope:smooth_envelope_candidate",
        "boundary_phase_conjugate:hard_51_control",
        "boundary_phase_conjugate:phase_conjugate_candidate",
        "boundary_phase_conjugate:shuffled_patch_phase_control",
    }
    selected = []
    for row in rows:
        key = f"{row.get('artifact_source')}:{row.get('prediction_role')}"
        if key in wanted:
            selected.append(row)
    return selected


def _merge_threshold_rows(summary_path: Path, threshold_path: Path) -> list[dict[str, Any]]:
    summary_rows = _read_csv(summary_path)
    threshold_by_variant = {row.get("variant"): row for row in _read_csv(threshold_path)}
    merged = []
    for row in summary_rows:
        threshold = threshold_by_variant.get(row.get("variant"), {})
        merged.append({**threshold, **row})
    return merged


def _count_metrics(row: dict[str, Any]) -> dict[str, int]:
    return {
        "default_major_peaks": int(_first(row, "default_major_peaks_at_0p30", "default_major_peaks", "major_peaks_at_0p30", "major_shell_peak_count")),
        "default_refocus_peaks": int(_first(row, "default_refocus_peaks_at_0p30", "default_refocus_peaks", "refocus_peaks_at_0p30", "refocus_peak_count")),
        "strict_major_peaks": int(_first(row, "conservative_major_peaks", "strict_major_peaks", "min_major_peaks_across_thresholds", "strict_major_peaks_at_0p40", "major_peaks_at_0p40")),
        "strict_refocus_peaks": int(_first(row, "conservative_refocus_peaks", "strict_refocus_peaks", "min_refocus_peaks_across_thresholds", "strict_refocus_peaks_at_0p40", "refocus_peaks_at_0p40")),
        "loose_major_peaks": int(_first(row, "loose_major_peaks_at_0p20", "major_peaks_at_0p20", "loose_major_peaks_at_0p25", "major_peaks_at_0p25", "default_major_peaks_at_0p30", "default_major_peaks")),
        "loose_refocus_peaks": int(_first(row, "loose_refocus_peaks_at_0p20", "refocus_peaks_at_0p20", "loose_refocus_peaks_at_0p25", "refocus_peaks_at_0p25", "default_refocus_peaks_at_0p30", "default_refocus_peaks")),
    }


def _threshold_suffix(threshold: float) -> str:
    return f"{threshold:.2f}".replace(".", "p")


def _peak_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {"time": _float(row.get("time")), "energy": _float(row.get("energy"))}
            for row in events
            if row.get("event") == "shell_peak"
        ],
        key=lambda row: row["time"],
    )


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


def _first(row: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return _float(value)
    return 0.0


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes"}


def _mean(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    return float(np.mean(parsed)) if parsed.size else 0.0


def _write_empty_outputs(root: Path, control_id: str, classification: dict[str, Any]) -> dict[str, Any]:
    summary_csv = root / "return_family_gate_summary.csv"
    occupancy_csv = root / "return_window_occupancy.csv"
    threshold_csv = root / "threshold_crossing_table.csv"
    amplitude_csv = root / "return_amplitude_by_index.csv"
    report_path = root / "return_family_gate_report.md"
    _write_csv(summary_csv, [], _summary_fields())
    _write_csv(occupancy_csv, [], _occupancy_fields())
    _write_csv(threshold_csv, [], _threshold_fields())
    _write_csv(amplitude_csv, [], _amplitude_fields())
    report_path.write_text(
        f"# Return Family Gate Audit: {control_id}\n\n"
        f"- Result: `{classification['label']}`\n"
        f"- Reason: {classification['reason']}\n",
        encoding="utf-8",
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": [],
        "occupancy_rows": [],
        "threshold_rows": [],
        "amplitude_rows": [],
        "summary_csv": str(summary_csv),
        "occupancy_csv": str(occupancy_csv),
        "threshold_csv": str(threshold_csv),
        "amplitude_csv": str(amplitude_csv),
        "report_path": str(report_path),
        "plots": {},
        "path": str(root),
    }


def _write_plots(
    plots: dict[str, Path],
    summary_rows: list[dict[str, Any]],
    threshold_rows: list[dict[str, Any]],
    amplitude_rows: list[dict[str, Any]],
) -> None:
    _plot_indexed_return_strength(plots["indexed_return_strength_plot"], amplitude_rows)
    _plot_threshold_crossings(plots["threshold_crossings_plot"], threshold_rows)
    _plot_summary_bar(plots["comb_score_plot"], summary_rows, "return_comb_score", "Return Comb Score")
    _plot_summary_bar(plots["off_comb_energy_ratio_plot"], summary_rows, "off_comb_energy_ratio", "Off-Comb Energy Ratio")


def _plot_indexed_return_strength(path: Path, rows: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(9, 4), dpi=140)
    for variant in _plot_variants(rows):
        subset = [row for row in rows if row.get("variant") == variant]
        ax.plot(
            [int(_float(row.get("return_index"))) for row in subset],
            [_float(row.get("rank_normalized_return_strength")) for row in subset],
            marker="o",
            linewidth=1.2,
            label=_short_label(variant),
        )
    ax.set_xlabel("Return index")
    ax.set_ylabel("Strength vs 41^3 proof median")
    ax.set_title("Indexed Return Strength")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_threshold_crossings(path: Path, rows: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(9, 4), dpi=140)
    for variant in _plot_variants(rows):
        subset = [row for row in rows if row.get("variant") == variant]
        ax.plot(
            [_float(row.get("threshold")) for row in subset],
            [_float(row.get("artifact_major_peaks") or row.get("event_peak_crossing_count")) for row in subset],
            marker="o",
            linewidth=1.2,
            label=_short_label(variant),
        )
    ax.set_xlabel("Peak threshold fraction")
    ax.set_ylabel("Major peak count")
    ax.set_title("Threshold Crossings")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_summary_bar(path: Path, rows: list[dict[str, Any]], key: str, title: str) -> None:
    selected = _source_control_rows(rows) or rows
    labels = [_short_label(str(row.get("variant"))) for row in selected]
    values = [_float(row.get(key)) for row in selected]
    fig, ax = plt.subplots(figsize=(max(7, len(labels) * 0.8), 4), dpi=140)
    ax.bar(range(len(labels)), values, color="#4477aa")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_variants(rows: list[dict[str, Any]]) -> list[str]:
    wanted = [
        "quarter_dt_proof_candidate_cutoff_17p94",
        "resolution_lift_51_candidate_phase_0p5071",
        "smooth_envelope_51_hard_cutoff_17p9425",
        "smooth_envelope_51_smooth_cutoff_17p9425",
        "phase_conjugate_51_hard_cutoff_17p9425",
        "phase_conjugate_51_candidate_cutoff_17p9425",
        "phase_conjugate_51_shuffled_cutoff_17p9425",
    ]
    variants = []
    available = {str(row.get("variant")) for row in rows}
    for variant in wanted:
        if variant in available:
            variants.append(variant)
    for variant in sorted(available):
        if variant not in variants and len(variants) < 8:
            variants.append(variant)
    return variants


def _short_label(variant: str) -> str:
    replacements = {
        "quarter_dt_proof_candidate_cutoff_17p94": "41 proof",
        "resolution_lift_51_candidate_phase_0p5071": "51 lift",
        "smooth_envelope_51_hard_cutoff_17p9425": "smooth hard",
        "smooth_envelope_51_smooth_cutoff_17p9425": "smooth",
        "phase_conjugate_51_hard_cutoff_17p9425": "pc hard",
        "phase_conjugate_51_candidate_cutoff_17p9425": "pc candidate",
        "phase_conjugate_51_shuffled_cutoff_17p9425": "pc shuffled",
    }
    return replacements.get(variant, variant.replace("_cutoff_17p9425", "").replace("_phase_0p5071", "")[:28])


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    plots: dict[str, Path],
    options: ReturnFamilyGateAuditOptions,
) -> None:
    checks = classification.get("checks", {})
    control_rows = _source_control_rows(rows)
    lines = [
        f"# Return Family Gate Audit: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only audit of whether the 51^3 strict-count loss is a true loss of the return family or a fixed-threshold / strict-event-gate artifact. No new physics was run.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Mechanism-derived next candidate: `{checks.get('mechanism_candidate', 'none')}`",
        "",
        "## Key Checks",
        "",
        f"- Proof strict major mean: `{_format(checks.get('proof_strict_major_mean'))}`",
        f"- 51^3 source-control strict major mean: `{_format(checks.get('source_control_strict_major_mean'))}`",
        f"- Strict major loss: `{_format(checks.get('strict_major_loss'))}`",
        f"- Proof occupancy mean: `{_format(checks.get('proof_occupancy_mean'))}`",
        f"- 51^3 source-control occupancy mean: `{_format(checks.get('source_control_occupancy_mean'))}`",
        f"- Proof comb score mean: `{_format(checks.get('proof_comb_score_mean'))}`",
        f"- 51^3 source-control comb score mean: `{_format(checks.get('source_control_comb_score_mean'))}`",
        f"- 51^3 off-comb energy ratio mean: `{_format(checks.get('source_control_off_comb_energy_ratio_mean'))}`",
        f"- 51^3 period CV mean: `{_format(checks.get('source_control_period_cv_mean'))}`",
        f"- Rank-normalized strength ratio: `{_format(checks.get('rank_normalized_strength_ratio'))}`",
        f"- Prominence ratio: `{_format(checks.get('prominence_ratio'))}`",
        "",
        "## Source-Control Comparison",
        "",
        "| Source | Role | Grid | Loose | Default | Strict | Occupancy | Comb | Off-comb | Strength | Prominence | Late survival |",
        "| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in control_rows:
        lines.append(
            "| "
            f"{row.get('artifact_source')} | "
            f"{row.get('prediction_role')} | "
            f"{row.get('grid_size')} | "
            f"{row.get('loose_major_peaks')}/{row.get('loose_refocus_peaks')} | "
            f"{row.get('default_major_peaks')}/{row.get('default_refocus_peaks')} | "
            f"{row.get('strict_major_peaks')}/{row.get('strict_refocus_peaks')} | "
            f"{_format(row.get('return_window_occupancy_fraction'))} | "
            f"{_format(row.get('return_comb_score'))} | "
            f"{_format(row.get('off_comb_energy_ratio'))} | "
            f"{_format(row.get('mean_rank_normalized_return_strength'))} | "
            f"{_format(row.get('mean_peak_prominence_ratio'))} | "
            f"{_format(row.get('late_return_area_survival_fraction'))} |"
        )
    lines.extend(
        [
            "",
            "## Row Summary",
            "",
            "| Group | Source | Variant | Strict | Period | Period CV | Occupancy | Comb | Off-comb | Strength |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row.get('audit_group')} | "
            f"{row.get('artifact_source')} | "
            f"{row.get('variant')} | "
            f"{row.get('strict_major_peaks')}/{row.get('strict_refocus_peaks')} | "
            f"{_format(row.get('predicted_return_period'))} | "
            f"{_format(row.get('predicted_return_period_cv'))} | "
            f"{_format(row.get('return_window_occupancy_fraction'))} | "
            f"{_format(row.get('return_comb_score'))} | "
            f"{_format(row.get('off_comb_energy_ratio'))} | "
            f"{_format(row.get('mean_rank_normalized_return_strength'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Plots",
            "",
        ]
    )
    for label, plot in plots.items():
        lines.append(f"- `{plot.name}`")
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `return_family_gate_report.md`",
            "- `return_family_gate_summary.csv`",
            "- `return_window_occupancy.csv`",
            "- `threshold_crossing_table.csv`",
            "- `return_amplitude_by_index.csv`",
            "- `return_family_gate_summary.json`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "return_family_survives_gate_artifact_supported":
        return "The 51^3 rows remain organized on the predicted return comb with low off-comb energy. The strict-count loss is best read as fixed-gate sensitivity caused by compressed amplitude/prominence, not disappearance of the return family."
    if label == "return_family_weakened_not_gate_artifact":
        return "The 51^3 rows lose enough predicted-window occupancy or move enough energy off the comb that the strict-count drop should be treated as a real weakening of the return family."
    if label == "insufficient_artifacts":
        return "The audit could not find enough saved timeseries/events to compare proof and 51^3 source-control rows."
    return "The audit does not cleanly separate strict-gate artifact from real family weakening. Do not use it to justify tuning or new source variants."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "return_family_gate_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "grid_size",
        "dt",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "default_major_peaks",
        "default_refocus_peaks",
        "loose_major_peaks",
        "loose_refocus_peaks",
        "predicted_return_period",
        "predicted_return_period_cv",
        "predicted_window_count",
        "occupied_window_count",
        "return_window_occupancy_fraction",
        "return_comb_score",
        "on_comb_energy",
        "post_cutoff_energy",
        "on_comb_energy_fraction",
        "off_comb_energy",
        "off_comb_energy_ratio",
        "mean_peak_prominence_ratio",
        "mean_peak_prominence_over_background",
        "mean_return_peak_energy",
        "mean_rank_normalized_return_strength",
        "amplitude_compression_vs_41",
        "early_window_energy",
        "late_window_energy",
        "late_return_area_survival_fraction",
        "tail_area_after_t50",
        "modal_modes_for_99pct",
        "modal_participation_ratio",
        "no_exit",
        "global_outer_false",
    ]


def _occupancy_fields() -> list[str]:
    return [
        "variant",
        "return_family_gate_classification",
        "artifact_source",
        "audit_group",
        "return_index",
        "predicted_time",
        "window_start",
        "window_end",
        "window_half_width",
        "occupied",
        "peak_time",
        "peak_time_error",
        "peak_energy",
        "local_background_energy",
        "prominence_ratio",
        "prominence_over_background",
        "window_energy",
    ]


def _threshold_fields() -> list[str]:
    return [
        "variant",
        "return_family_gate_classification",
        "artifact_source",
        "audit_group",
        "threshold",
        "artifact_major_peaks",
        "artifact_refocus_peaks",
        "event_peak_crossing_count",
        "max_peak_energy",
        "threshold_energy",
    ]


def _amplitude_fields() -> list[str]:
    return [
        "variant",
        "return_family_gate_classification",
        "artifact_source",
        "audit_group",
        "return_index",
        "predicted_time",
        "window_start",
        "window_end",
        "occupied",
        "peak_time",
        "peak_time_error",
        "peak_energy",
        "row_peak_fraction_of_max",
        "proof_reference_rank_fraction",
        "rank_normalized_return_strength",
        "local_background_energy",
        "prominence_ratio",
        "prominence_over_background",
        "window_energy",
    ]
