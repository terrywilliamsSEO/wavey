"""Read-only modal sparsity audit for 41^3 proof versus 51^3 scale-loss artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import json
import math

import numpy as np

from .prototype_3d import EPSILON
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_PROOF_ROOT = "runs/release_phase_proof_pack_3d_20260619_234039"
DEFAULT_LIFT_ROOT = "runs/release_phase_resolution_lift_3d_20260620_091834"
DEFAULT_SPATIAL_PHASE_ROOT = "runs/spatial_phase_instrumentation_3d_20260620_170518"
DEFAULT_SMOOTH_ROOT = "runs/smooth_envelope_resolution_lift_3d_20260620_192501"
DEFAULT_PHASE_CONJUGATE_ROOT = "runs/boundary_phase_conjugate_3d_20260620_212918"


@dataclass(frozen=True)
class ModalSparsityAuditOptions:
    """Options for the read-only modal sparsity / beat reconstruction audit."""

    output_root: str = "runs"
    proof_root: str = DEFAULT_PROOF_ROOT
    lift_root: str = DEFAULT_LIFT_ROOT
    spatial_phase_root: str = DEFAULT_SPATIAL_PHASE_ROOT
    smooth_root: str = DEFAULT_SMOOTH_ROOT
    phase_conjugate_root: str = DEFAULT_PHASE_CONJUGATE_ROOT
    max_reported_modes: int = 40
    few_mode_99_threshold: int = 8
    broad_mode_99_threshold: int = 20
    broad_participation_threshold: float = 12.0
    min_strict_major_loss: float = 1.0
    preserved_period_relative_tolerance: float = 0.15
    blurred_peak_width_growth: float = 0.10
    source_signature_cv_threshold: float = 0.12


def run_3d_modal_sparsity_audit(
    *,
    options: ModalSparsityAuditOptions | None = None,
) -> dict[str, Any]:
    """Compare modal sparsity and return beat structure from existing artifacts only."""

    options = options or ModalSparsityAuditOptions()
    control_id = datetime.now().strftime("modal_sparsity_audit_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    records = _load_records(options)
    summary_rows: list[dict[str, Any]] = []
    reconstruction_rows: list[dict[str, Any]] = []
    participation_rows: list[dict[str, Any]] = []
    timing_rows: list[dict[str, Any]] = []

    for record in records:
        row, reconstruction, participation, timing = _diagnose_record(record, options)
        summary_rows.append(row)
        reconstruction_rows.extend(reconstruction)
        participation_rows.append(participation)
        timing_rows.append(timing)

    relation_rows = _relation_rows(summary_rows)
    classification = classify_modal_sparsity_audit(summary_rows, options)
    for collection in (summary_rows, reconstruction_rows, participation_rows, timing_rows, relation_rows):
        for row in collection:
            row["modal_sparsity_audit_classification"] = classification["label"]

    summary_csv = root / "modal_sparsity_summary.csv"
    reconstruction_csv = root / "sparse_spectral_reconstruction.csv"
    participation_csv = root / "modal_participation_ratio.csv"
    timing_csv = root / "return_timing_width_comparison.csv"
    relation_csv = root / "peak_width_modal_density_relation.csv"
    report_path = root / "modal_sparsity_audit_report.md"
    summary_json = root / "modal_sparsity_audit_summary.json"

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(reconstruction_csv, reconstruction_rows, _reconstruction_fields())
    _write_csv(participation_csv, participation_rows, _participation_fields())
    _write_csv(timing_csv, timing_rows, _timing_fields())
    _write_csv(relation_csv, relation_rows, _relation_fields())
    _write_report(report_path, control_id, summary_rows, relation_rows, classification, options)
    summary_json.write_text(
        json.dumps(
            {
                "control_id": control_id,
                "classification": classification,
                "row_count": len(summary_rows),
                "summary_csv": str(summary_csv),
                "reconstruction_csv": str(reconstruction_csv),
                "participation_csv": str(participation_csv),
                "timing_csv": str(timing_csv),
                "relation_csv": str(relation_csv),
                "report_path": str(report_path),
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
        "relation_rows": relation_rows,
        "summary_csv": str(summary_csv),
        "reconstruction_csv": str(reconstruction_csv),
        "participation_csv": str(participation_csv),
        "timing_csv": str(timing_csv),
        "relation_csv": str(relation_csv),
        "report_path": str(report_path),
        "summary_json": str(summary_json),
        "path": str(root),
    }


def classify_modal_sparsity_audit(
    rows: list[dict[str, Any]],
    options: ModalSparsityAuditOptions | None = None,
) -> dict[str, Any]:
    """Classify the modal sparsity comparison without recommending a new physics run."""

    options = options or ModalSparsityAuditOptions()
    proof = _proof_rows(rows)
    scale_51 = _scale_rows(rows)
    source_controls = _source_control_rows(rows)
    proof_modes_99 = _mean(row.get("modes_for_99pct") for row in proof)
    scale_modes_99 = _mean(row.get("modes_for_99pct") for row in scale_51)
    proof_participation = _mean(row.get("modal_participation_ratio") for row in proof)
    scale_participation = _mean(row.get("modal_participation_ratio") for row in scale_51)
    proof_strict = _mean(row.get("strict_major_peaks") for row in proof)
    scale_strict = _mean(row.get("strict_major_peaks") for row in scale_51)
    strict_loss = proof_strict - scale_strict
    proof_period = _mean(row.get("mean_return_period") for row in proof)
    scale_period = _mean(row.get("mean_return_period") for row in scale_51)
    proof_peak_width = _mean(row.get("mean_peak_width_time") for row in proof)
    scale_peak_width = _mean(row.get("mean_peak_width_time") for row in scale_51)
    period_preserved = _relative_abs_delta(scale_period, proof_period) <= options.preserved_period_relative_tolerance
    peak_width_growth = _relative_delta(scale_peak_width, proof_peak_width)
    source_modes_cv = _cv(row.get("modes_for_99pct") for row in source_controls)
    source_participation_cv = _cv(row.get("modal_participation_ratio") for row in source_controls)
    source_strict_span = _span(row.get("strict_major_peaks") for row in source_controls)
    proof_few_mode = proof_modes_99 > 0.0 and proof_modes_99 <= options.few_mode_99_threshold
    scale_broad = (
        scale_modes_99 >= options.broad_mode_99_threshold
        or scale_participation >= options.broad_participation_threshold
    )
    source_controls_same_signature = (
        len(source_controls) >= 4
        and source_modes_cv <= options.source_signature_cv_threshold
        and source_participation_cv <= options.source_signature_cv_threshold
        and source_strict_span <= 1.0
    )
    blur_signature = (
        period_preserved
        and strict_loss >= options.min_strict_major_loss
        and (peak_width_growth >= options.blurred_peak_width_growth or scale_broad)
    )
    checks = {
        "proof_row_count": len(proof),
        "scale_51_row_count": len(scale_51),
        "source_control_row_count": len(source_controls),
        "proof_modes_for_99pct_mean": proof_modes_99,
        "scale_51_modes_for_99pct_mean": scale_modes_99,
        "proof_modal_participation_mean": proof_participation,
        "scale_51_modal_participation_mean": scale_participation,
        "proof_strict_major_mean": proof_strict,
        "scale_51_strict_major_mean": scale_strict,
        "strict_major_loss": strict_loss,
        "proof_mean_return_period": proof_period,
        "scale_51_mean_return_period": scale_period,
        "period_preserved": period_preserved,
        "proof_mean_peak_width": proof_peak_width,
        "scale_51_mean_peak_width": scale_peak_width,
        "peak_width_relative_growth": peak_width_growth,
        "source_modes_for_99pct_cv": source_modes_cv,
        "source_participation_cv": source_participation_cv,
        "source_strict_major_span": source_strict_span,
        "proof_few_mode": proof_few_mode,
        "scale_broad": scale_broad,
        "source_controls_same_signature": source_controls_same_signature,
        "mechanism_candidate": "none",
    }
    if proof_few_mode and scale_broad and source_controls_same_signature and strict_loss >= options.min_strict_major_loss:
        return {
            "label": "source_shaping_modal_dead_end_supported",
            "reason": "The 41^3 proof rows are few-mode sparse while the 51^3 hard, smooth, phase-conjugate, and shuffled controls share a broad high-participation signature and the same strict-count loss.",
            "checks": checks,
        }
    if source_controls and not source_controls_same_signature:
        return {
            "label": "source_variant_modal_difference_supported",
            "reason": "At least one 51^3 source variant has a materially different modal participation or strict-count signature.",
            "checks": checks,
        }
    if proof_few_mode and scale_broad and strict_loss >= options.min_strict_major_loss:
        return {
            "label": "few_mode_41_broad_51_supported",
            "reason": "The proof rows reconstruct with few modes, while 51^3 rows require many more participating frequencies and lose strict returns.",
            "checks": checks,
        }
    if blur_signature and source_controls_same_signature:
        return {
            "label": "common_51_blur_signature_supported",
            "reason": "The 51^3 rows preserve the return period but share widened or high-participation peaks across source-shaping controls.",
            "checks": checks,
        }
    if source_controls_same_signature and strict_loss >= options.min_strict_major_loss:
        return {
            "label": "common_51_source_signature_supported",
            "reason": "The 51^3 hard, smooth, phase-conjugate, and shuffled controls share a tight modal participation/reconstruction signature and the same strict-count loss, even though the artifact set does not prove a broad-wave modal-density jump.",
            "checks": checks,
        }
    return {
        "label": "modal_sparsity_inconclusive",
        "reason": "The existing artifacts do not cleanly separate few-mode proof behavior from broad 51^3 transport, or the source-control comparison is too sparse.",
        "checks": checks,
    }


def _load_records(options: ModalSparsityAuditOptions) -> list[dict[str, Any]]:
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
            audit_group_field="audit_group",
            fallback_audit_group="spatial_phase",
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
    return [record for record in records if record.get("timeseries")]


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
    options: ModalSparsityAuditOptions,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    row = record["summary"]
    variant = record["variant"]
    artifact_source = record["artifact_source"]
    audit_group = record["audit_group"]
    cutoff = _float(row.get("drive_cutoff_time"))
    times = _array(ts.get("time") for ts in record["timeseries"])
    shell = _array(ts.get("shell_window_energy") for ts in record["timeseries"])
    post_mask = times > cutoff if times.size else np.asarray([], dtype=bool)
    post_times = times[post_mask]
    post_shell = shell[post_mask]
    spectral = _sparse_spectrum(post_times, post_shell)
    peaks = _peak_rows(record["events"])
    timing = _timing_metrics(peaks, times, shell, spectral["dominant_frequency"])
    counts = _count_metrics(row)
    strict_major_loss_from_loose = counts["loose_major_peaks"] - counts["strict_major_peaks"]
    role = str(row.get("prediction_role") or row.get("patch_mode") or row.get("audit_group") or "")
    summary = {
        "variant": variant,
        "artifact_source": artifact_source,
        "audit_group": audit_group,
        "prediction_role": role,
        "grid_size": row.get("grid_size"),
        "dt": row.get("dt"),
        "drive_cutoff_time": cutoff,
        "cutoff_phase_cycles": row.get("cutoff_phase_cycles") or row.get("target_release_phase"),
        "default_major_peaks": counts["default_major_peaks"],
        "default_refocus_peaks": counts["default_refocus_peaks"],
        "strict_major_peaks": counts["strict_major_peaks"],
        "strict_refocus_peaks": counts["strict_refocus_peaks"],
        "loose_major_peaks": counts["loose_major_peaks"],
        "loose_refocus_peaks": counts["loose_refocus_peaks"],
        "loose_to_strict_major_loss": strict_major_loss_from_loose,
        "dominant_frequency": spectral["dominant_frequency"],
        "dominant_period": 1.0 / spectral["dominant_frequency"] if spectral["dominant_frequency"] > EPSILON else 0.0,
        "spectral_bandwidth": spectral["spectral_bandwidth"],
        "dominant_power_fraction": spectral["dominant_power_fraction"],
        "top3_power_fraction": spectral["top3_power_fraction"],
        "top8_power_fraction": spectral["top8_power_fraction"],
        "top20_power_fraction": spectral["top20_power_fraction"],
        "modes_for_90pct": spectral["modes_for_90pct"],
        "modes_for_95pct": spectral["modes_for_95pct"],
        "modes_for_99pct": spectral["modes_for_99pct"],
        "modal_participation_ratio": spectral["modal_participation_ratio"],
        "spectral_entropy": spectral["spectral_entropy"],
        "mean_return_period": timing["mean_return_period"],
        "return_period_cv": timing["return_period_cv"],
        "return_timing_regularity": timing["return_timing_regularity"],
        "return_period_to_dominant_period_ratio": timing["return_period_to_dominant_period_ratio"],
        "mean_peak_width_time": timing["mean_peak_width_time"],
        "peak_width_cv": timing["peak_width_cv"],
        "peak_amplitude_decay": timing["peak_amplitude_decay"],
        "peak_count_from_events": timing["peak_count_from_events"],
        "shell_phase_coherence_mean": _first(row, "shell_phase_coherence_mean"),
        "radial_phase_coherence_mean": _first(row, "radial_phase_coherence_mean"),
        "angular_phase_coherence_mean": _first(row, "angular_phase_coherence_mean"),
        "outer_shell": _first(row, "outer_shell", "tail_outer_to_shell_mean", "outer_shell_median"),
        "no_exit": _bool(row.get("no_exit")) if "no_exit" in row else not _bool(row.get("shell_exit_detected")),
        "global_outer_false": _bool(row.get("global_outer_false")) if "global_outer_false" in row else not _bool(row.get("global_peak_in_outer_window")),
    }
    reconstruction_rows = _reconstruction_rows(variant, artifact_source, audit_group, spectral, options)
    participation_row = {
        "variant": variant,
        "artifact_source": artifact_source,
        "audit_group": audit_group,
        "grid_size": row.get("grid_size"),
        "modal_participation_ratio": spectral["modal_participation_ratio"],
        "spectral_entropy": spectral["spectral_entropy"],
        "modes_for_90pct": spectral["modes_for_90pct"],
        "modes_for_95pct": spectral["modes_for_95pct"],
        "modes_for_99pct": spectral["modes_for_99pct"],
        "dominant_power_fraction": spectral["dominant_power_fraction"],
        "top8_power_fraction": spectral["top8_power_fraction"],
        "top20_power_fraction": spectral["top20_power_fraction"],
        "strict_major_peaks": counts["strict_major_peaks"],
        "strict_refocus_peaks": counts["strict_refocus_peaks"],
    }
    timing_row = {
        "variant": variant,
        "artifact_source": artifact_source,
        "audit_group": audit_group,
        "grid_size": row.get("grid_size"),
        "mean_return_period": timing["mean_return_period"],
        "return_period_cv": timing["return_period_cv"],
        "return_timing_regularity": timing["return_timing_regularity"],
        "mean_peak_width_time": timing["mean_peak_width_time"],
        "peak_width_cv": timing["peak_width_cv"],
        "dominant_period": summary["dominant_period"],
        "return_period_to_dominant_period_ratio": timing["return_period_to_dominant_period_ratio"],
        "strict_major_peaks": counts["strict_major_peaks"],
        "strict_refocus_peaks": counts["strict_refocus_peaks"],
        "peak_amplitude_decay": timing["peak_amplitude_decay"],
        "peak_count_from_events": timing["peak_count_from_events"],
    }
    return summary, reconstruction_rows, participation_row, timing_row


def _sparse_spectrum(times: np.ndarray, values: np.ndarray) -> dict[str, Any]:
    if times.size < 4 or values.size < 4:
        return _empty_spectrum()
    sample_dt = float(np.median(np.diff(times)))
    centered = values - float(np.mean(values))
    total_signal = float(np.dot(centered, centered))
    if total_signal <= EPSILON:
        return _empty_spectrum()
    freq = np.fft.rfftfreq(centered.size, d=max(sample_dt, EPSILON))
    coeff = np.fft.rfft(centered)
    power = np.abs(coeff) ** 2
    if power.size <= 1:
        return _empty_spectrum()
    freq = freq[1:]
    power = power[1:]
    total_power = float(np.sum(power))
    if total_power <= EPSILON:
        return _empty_spectrum()
    order = np.argsort(power)[::-1]
    sorted_power = power[order]
    sorted_freq = freq[order]
    fractions = sorted_power / total_power
    cumulative = np.cumsum(fractions)
    participation = float(1.0 / max(float(np.sum(fractions**2)), EPSILON))
    entropy = float(-np.sum(fractions * np.log(np.maximum(fractions, EPSILON))) / math.log(max(fractions.size, 2)))
    mean_freq = float(np.sum(freq * power) / total_power)
    bandwidth = float(np.sqrt(np.sum(power * (freq - mean_freq) ** 2) / total_power))
    return {
        "dominant_frequency": float(sorted_freq[0]),
        "spectral_bandwidth": bandwidth,
        "dominant_power_fraction": float(fractions[0]),
        "top3_power_fraction": _top_fraction(fractions, 3),
        "top8_power_fraction": _top_fraction(fractions, 8),
        "top20_power_fraction": _top_fraction(fractions, 20),
        "modes_for_90pct": _modes_for(cumulative, 0.90),
        "modes_for_95pct": _modes_for(cumulative, 0.95),
        "modes_for_99pct": _modes_for(cumulative, 0.99),
        "modal_participation_ratio": participation,
        "spectral_entropy": entropy,
        "modes": [
            {
                "mode_rank": index + 1,
                "frequency": float(sorted_freq[index]),
                "power_fraction": float(fractions[index]),
                "cumulative_power_fraction": float(cumulative[index]),
            }
            for index in range(sorted_freq.size)
        ],
    }


def _empty_spectrum() -> dict[str, Any]:
    return {
        "dominant_frequency": 0.0,
        "spectral_bandwidth": 0.0,
        "dominant_power_fraction": 0.0,
        "top3_power_fraction": 0.0,
        "top8_power_fraction": 0.0,
        "top20_power_fraction": 0.0,
        "modes_for_90pct": 0,
        "modes_for_95pct": 0,
        "modes_for_99pct": 0,
        "modal_participation_ratio": 0.0,
        "spectral_entropy": 0.0,
        "modes": [],
    }


def _timing_metrics(
    peaks: list[dict[str, Any]],
    times: np.ndarray,
    shell: np.ndarray,
    dominant_frequency: float,
) -> dict[str, float]:
    if not peaks:
        return {
            "mean_return_period": 0.0,
            "return_period_cv": 0.0,
            "return_timing_regularity": 0.0,
            "return_period_to_dominant_period_ratio": 0.0,
            "mean_peak_width_time": 0.0,
            "peak_width_cv": 0.0,
            "peak_amplitude_decay": 0.0,
            "peak_count_from_events": 0.0,
        }
    peak_times = np.asarray([_float(peak.get("time")) for peak in peaks], dtype=float)
    peak_energy = np.asarray([_float(peak.get("energy")) for peak in peaks], dtype=float)
    intervals = np.diff(peak_times)
    mean_period = float(np.mean(intervals)) if intervals.size else 0.0
    period_cv = float(np.std(intervals) / max(mean_period, EPSILON)) if intervals.size else 0.0
    widths = np.asarray([_peak_width_at_time(times, shell, peak_time) for peak_time in peak_times], dtype=float)
    mean_width = float(np.mean(widths)) if widths.size else 0.0
    width_cv = float(np.std(widths) / max(mean_width, EPSILON)) if widths.size else 0.0
    decay = _slope(peak_times, np.log(np.maximum(peak_energy, EPSILON))) if peak_times.size >= 3 else 0.0
    dominant_period = 1.0 / dominant_frequency if dominant_frequency > EPSILON else 0.0
    return {
        "mean_return_period": mean_period,
        "return_period_cv": period_cv,
        "return_timing_regularity": float(np.clip(1.0 - period_cv, 0.0, 1.0)) if intervals.size else 0.0,
        "return_period_to_dominant_period_ratio": mean_period / max(dominant_period, EPSILON) if dominant_period > EPSILON else 0.0,
        "mean_peak_width_time": mean_width,
        "peak_width_cv": width_cv,
        "peak_amplitude_decay": decay,
        "peak_count_from_events": float(len(peaks)),
    }


def _peak_width_at_time(times: np.ndarray, values: np.ndarray, peak_time: float) -> float:
    if times.size < 3 or values.size < 3:
        return 0.0
    idx = int(np.argmin(np.abs(times - peak_time)))
    peak_value = float(values[idx])
    if peak_value <= EPSILON:
        return 0.0
    half_height = 0.5 * peak_value
    left = idx
    while left > 0 and values[left] >= half_height:
        left -= 1
    right = idx
    while right < values.size - 1 and values[right] >= half_height:
        right += 1
    return float(times[right] - times[left])


def _relation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    families = [
        ("all_rows", rows),
        ("proof_41", _proof_rows(rows)),
        ("scale_51", _scale_rows(rows)),
        ("source_controls_51", _source_control_rows(rows)),
    ]
    for family, family_rows in families:
        out.append(
            {
                "comparison_family": family,
                "row_count": len(family_rows),
                "strict_major_vs_modes_for_99pct_corr": _corr(
                    [row.get("strict_major_peaks") for row in family_rows],
                    [row.get("modes_for_99pct") for row in family_rows],
                ),
                "strict_major_vs_modal_participation_corr": _corr(
                    [row.get("strict_major_peaks") for row in family_rows],
                    [row.get("modal_participation_ratio") for row in family_rows],
                ),
                "strict_major_vs_peak_width_corr": _corr(
                    [row.get("strict_major_peaks") for row in family_rows],
                    [row.get("mean_peak_width_time") for row in family_rows],
                ),
                "peak_width_vs_modal_participation_corr": _corr(
                    [row.get("mean_peak_width_time") for row in family_rows],
                    [row.get("modal_participation_ratio") for row in family_rows],
                ),
                "mean_modes_for_99pct": _mean(row.get("modes_for_99pct") for row in family_rows),
                "mean_modal_participation_ratio": _mean(row.get("modal_participation_ratio") for row in family_rows),
                "mean_peak_width_time": _mean(row.get("mean_peak_width_time") for row in family_rows),
                "mean_strict_major_peaks": _mean(row.get("strict_major_peaks") for row in family_rows),
            }
        )
    return out


def _proof_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("audit_group") == "proof_41" and row.get("prediction_role") in {"proof_candidate", "upper_immediate_control"}
    ] or [row for row in rows if row.get("audit_group") == "proof_41"]


def _scale_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if int(_float(row.get("grid_size"))) == 51]


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


def _reconstruction_rows(
    variant: str,
    artifact_source: str,
    audit_group: str,
    spectral: dict[str, Any],
    options: ModalSparsityAuditOptions,
) -> list[dict[str, Any]]:
    rows = []
    for mode in spectral["modes"][: max(0, options.max_reported_modes)]:
        rows.append(
            {
                "variant": variant,
                "artifact_source": artifact_source,
                "audit_group": audit_group,
                "mode_rank": mode["mode_rank"],
                "frequency": mode["frequency"],
                "power_fraction": mode["power_fraction"],
                "cumulative_power_fraction": mode["cumulative_power_fraction"],
                "modes_for_90pct": spectral["modes_for_90pct"],
                "modes_for_95pct": spectral["modes_for_95pct"],
                "modes_for_99pct": spectral["modes_for_99pct"],
                "modal_participation_ratio": spectral["modal_participation_ratio"],
            }
        )
    return rows


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


def _top_fraction(fractions: np.ndarray, count: int) -> float:
    return float(np.sum(fractions[: min(count, fractions.size)])) if fractions.size else 0.0


def _modes_for(cumulative: np.ndarray, target: float) -> int:
    if cumulative.size == 0:
        return 0
    found = np.flatnonzero(cumulative >= target)
    return int(found[0] + 1) if found.size else int(cumulative.size)


def _mean(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    return float(np.mean(parsed)) if parsed.size else 0.0


def _cv(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    mean = float(np.mean(parsed)) if parsed.size else 0.0
    return float(np.std(parsed) / max(abs(mean), EPSILON)) if parsed.size else 0.0


def _span(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    return float(np.max(parsed) - np.min(parsed)) if parsed.size else 0.0


def _relative_delta(value: float, reference: float) -> float:
    return (value - reference) / max(abs(reference), EPSILON)


def _relative_abs_delta(value: float, reference: float) -> float:
    return abs(value - reference) / max(abs(reference), EPSILON)


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 3 or y.size < 3 or float(np.ptp(x)) <= EPSILON:
        return 0.0
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)


def _corr(x_values: Any, y_values: Any) -> float:
    x = np.asarray([_float(value) for value in x_values], dtype=float)
    y = np.asarray([_float(value) for value in y_values], dtype=float)
    if x.size < 3 or y.size < 3 or float(np.std(x)) <= EPSILON or float(np.std(y)) <= EPSILON:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _summary_fields() -> list[str]:
    return [
        "variant",
        "modal_sparsity_audit_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "grid_size",
        "dt",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "default_major_peaks",
        "default_refocus_peaks",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "loose_major_peaks",
        "loose_refocus_peaks",
        "loose_to_strict_major_loss",
        "dominant_frequency",
        "dominant_period",
        "spectral_bandwidth",
        "dominant_power_fraction",
        "top3_power_fraction",
        "top8_power_fraction",
        "top20_power_fraction",
        "modes_for_90pct",
        "modes_for_95pct",
        "modes_for_99pct",
        "modal_participation_ratio",
        "spectral_entropy",
        "mean_return_period",
        "return_period_cv",
        "return_timing_regularity",
        "return_period_to_dominant_period_ratio",
        "mean_peak_width_time",
        "peak_width_cv",
        "peak_amplitude_decay",
        "peak_count_from_events",
        "shell_phase_coherence_mean",
        "radial_phase_coherence_mean",
        "angular_phase_coherence_mean",
        "outer_shell",
        "no_exit",
        "global_outer_false",
    ]


def _reconstruction_fields() -> list[str]:
    return [
        "variant",
        "modal_sparsity_audit_classification",
        "artifact_source",
        "audit_group",
        "mode_rank",
        "frequency",
        "power_fraction",
        "cumulative_power_fraction",
        "modes_for_90pct",
        "modes_for_95pct",
        "modes_for_99pct",
        "modal_participation_ratio",
    ]


def _participation_fields() -> list[str]:
    return [
        "variant",
        "modal_sparsity_audit_classification",
        "artifact_source",
        "audit_group",
        "grid_size",
        "modal_participation_ratio",
        "spectral_entropy",
        "modes_for_90pct",
        "modes_for_95pct",
        "modes_for_99pct",
        "dominant_power_fraction",
        "top8_power_fraction",
        "top20_power_fraction",
        "strict_major_peaks",
        "strict_refocus_peaks",
    ]


def _timing_fields() -> list[str]:
    return [
        "variant",
        "modal_sparsity_audit_classification",
        "artifact_source",
        "audit_group",
        "grid_size",
        "mean_return_period",
        "return_period_cv",
        "return_timing_regularity",
        "mean_peak_width_time",
        "peak_width_cv",
        "dominant_period",
        "return_period_to_dominant_period_ratio",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "peak_amplitude_decay",
        "peak_count_from_events",
    ]


def _relation_fields() -> list[str]:
    return [
        "comparison_family",
        "modal_sparsity_audit_classification",
        "row_count",
        "strict_major_vs_modes_for_99pct_corr",
        "strict_major_vs_modal_participation_corr",
        "strict_major_vs_peak_width_corr",
        "peak_width_vs_modal_participation_corr",
        "mean_modes_for_99pct",
        "mean_modal_participation_ratio",
        "mean_peak_width_time",
        "mean_strict_major_peaks",
    ]


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    relation_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ModalSparsityAuditOptions,
) -> None:
    checks = classification.get("checks", {})
    source_rows = _source_control_rows(rows)
    lines = [
        f"# Modal Sparsity Audit: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only comparison of existing 41^3 proof-pack, 51^3 lift, spatial-phase, smooth-envelope, and boundary phase-conjugate artifacts. The audit asks whether the 41^3 return family is a sparse few-mode beat packet, and whether failed 51^3 source-shaping controls share the same broad modal/blur signature.",
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
        f"- Proof modes for 99% reconstruction mean: `{_format(checks.get('proof_modes_for_99pct_mean'))}`",
        f"- 51^3 modes for 99% reconstruction mean: `{_format(checks.get('scale_51_modes_for_99pct_mean'))}`",
        f"- Proof modal participation mean: `{_format(checks.get('proof_modal_participation_mean'))}`",
        f"- 51^3 modal participation mean: `{_format(checks.get('scale_51_modal_participation_mean'))}`",
        f"- Strict major loss: `{_format(checks.get('strict_major_loss'))}`",
        f"- Return period preserved: `{checks.get('period_preserved')}`",
        f"- Peak-width relative growth: `{_format(checks.get('peak_width_relative_growth'))}`",
        f"- Source-control modes CV: `{_format(checks.get('source_modes_for_99pct_cv'))}`",
        f"- Source-control participation CV: `{_format(checks.get('source_participation_cv'))}`",
        f"- Source controls same signature: `{checks.get('source_controls_same_signature')}`",
        "",
        "## Control Comparison",
        "",
        "| Source | Role | Grid | Loose | Default | Strict | Modes 90/95/99 | Participation | Period | Width | Coherence shell/radial/angular |",
        "| --- | --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in source_rows:
        lines.append(
            "| "
            f"{row.get('artifact_source')} | "
            f"{row.get('prediction_role')} | "
            f"{row.get('grid_size')} | "
            f"{row.get('loose_major_peaks')}/{row.get('loose_refocus_peaks')} | "
            f"{row.get('default_major_peaks')}/{row.get('default_refocus_peaks')} | "
            f"{row.get('strict_major_peaks')}/{row.get('strict_refocus_peaks')} | "
            f"{row.get('modes_for_90pct')}/{row.get('modes_for_95pct')}/{row.get('modes_for_99pct')} | "
            f"{_format(row.get('modal_participation_ratio'))} | "
            f"{_format(row.get('mean_return_period'))} | "
            f"{_format(row.get('mean_peak_width_time'))} | "
            f"{_format(row.get('shell_phase_coherence_mean'))}/{_format(row.get('radial_phase_coherence_mean'))}/{_format(row.get('angular_phase_coherence_mean'))} |"
        )
    lines.extend(
        [
            "",
            "## Row Summary",
            "",
            "| Group | Source | Variant | Grid | Strict | Modes 99 | Participation | Period | Width |",
            "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row.get('audit_group')} | "
            f"{row.get('artifact_source')} | "
            f"{row.get('variant')} | "
            f"{row.get('grid_size')} | "
            f"{row.get('strict_major_peaks')}/{row.get('strict_refocus_peaks')} | "
            f"{row.get('modes_for_99pct')} | "
            f"{_format(row.get('modal_participation_ratio'))} | "
            f"{_format(row.get('mean_return_period'))} | "
            f"{_format(row.get('mean_peak_width_time'))} |"
        )
    lines.extend(
        [
            "",
            "## Peak Width Versus Modal Density",
            "",
            "| Family | Rows | Strict vs modes corr | Strict vs participation corr | Strict vs width corr | Width vs participation corr |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in relation_rows:
        lines.append(
            "| "
            f"{row.get('comparison_family')} | "
            f"{row.get('row_count')} | "
            f"{_format(row.get('strict_major_vs_modes_for_99pct_corr'))} | "
            f"{_format(row.get('strict_major_vs_modal_participation_corr'))} | "
            f"{_format(row.get('strict_major_vs_peak_width_corr'))} | "
            f"{_format(row.get('peak_width_vs_modal_participation_corr'))} |"
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
            "- `modal_sparsity_audit_report.md`",
            "- `modal_sparsity_summary.csv`",
            "- `sparse_spectral_reconstruction.csv`",
            "- `modal_participation_ratio.csv`",
            "- `return_timing_width_comparison.csv`",
            "- `peak_width_modal_density_relation.csv`",
            "- `modal_sparsity_audit_summary.json`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "source_shaping_modal_dead_end_supported":
        return "The proof rows are sparse enough to look like a few-mode beat packet, while the 51^3 hard/smooth/phase-conjugate/shuffled controls share a high-participation modal signature and the same strict-count shrinkage. This supports archiving source shaping for this branch unless a genuinely new mechanism appears."
    if label == "few_mode_41_broad_51_supported":
        return "The proof rows are much more spectrally sparse than the 51^3 rows, but the source-control comparison is not uniform enough to declare every shaping path exhausted from this audit alone."
    if label == "common_51_blur_signature_supported":
        return "The 51^3 controls preserve the return timing period but share a blurred/high-participation signature. That points to scale-level blur rather than a single bad source variant."
    if label == "common_51_source_signature_supported":
        return "The source-shaped 51^3 rows do not separate from the hard 51^3 control in sparse reconstruction, modal participation, or strict counts. This supports treating smooth-envelope and patch-level wavefront shaping as exhausted for the current branch, while stopping short of claiming a fully broad-wave modal-density transition."
    if label == "source_variant_modal_difference_supported":
        return "One source variant changes modal participation or strict-count behavior enough to stand apart. Treat this as diagnostic evidence only; this read-only audit does not authorize a new physics run by itself."
    return "The sparse reconstruction and modal participation tables do not isolate a strong mechanism. Keep the branch archived unless a new mechanism-specific prediction appears."
