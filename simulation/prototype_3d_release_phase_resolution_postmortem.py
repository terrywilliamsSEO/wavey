"""Read-only postmortem for the 41^3 proof pack versus the 51^3 lift."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import json
import math

import numpy as np

from .config import save_json
from .prototype_3d import EPSILON
from .prototype_3d_cutoff_phase_map import _refocus_count
from .prototype_3d_packet_lifecycle import _major_peaks
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_PROOF_ROOT = "runs/release_phase_proof_pack_3d_20260619_234039"
DEFAULT_LIFT_ROOT = "runs/release_phase_resolution_lift_3d_20260620_091834"


@dataclass(frozen=True)
class ReleasePhaseResolutionPostmortemOptions:
    """Options for the read-only resolution-lift postmortem."""

    output_root: str = "runs"
    proof_root: str = DEFAULT_PROOF_ROOT
    lift_root: str = DEFAULT_LIFT_ROOT
    peak_threshold_fraction: float = 0.30
    refocus_threshold_fraction: float = 0.35
    min_peak_separation_time: float = 5.0
    low_peak_threshold_fraction: float = 0.20
    strict_peak_threshold_fraction: float = 0.40
    phase_match_tolerance: float = 0.003
    radial_shift_predict_threshold: float = 0.75
    timing_shift_predict_threshold: float = 0.75
    tail_area_close_fraction: float = 0.10
    no_retry_reason: str = "No single mechanism-recalibrated retry is recommended by this read-only postmortem."


def run_3d_release_phase_resolution_postmortem(
    *,
    options: ReleasePhaseResolutionPostmortemOptions | None = None,
) -> dict[str, Any]:
    """Compare existing 41^3 proof-pack artifacts against the failed 51^3 lift."""

    options = options or ReleasePhaseResolutionPostmortemOptions()
    proof_root = Path(options.proof_root)
    lift_root = Path(options.lift_root)
    control_id = datetime.now().strftime("release_phase_resolution_postmortem_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    proof = _load_run(proof_root, "proof_pack")
    lift = _load_run(lift_root, "resolution_lift")
    proof_winners = _proof_winners(proof["rows"])
    lift_rows = _lift_rows(lift["rows"])
    diagnostic_rows = [_diagnostic_row(row, "proof_winner", options) for row in proof_winners]
    diagnostic_rows.extend(_diagnostic_row(row, _lift_group(row), options) for row in lift_rows)
    comparison_rows = _comparison_rows(proof_winners, lift_rows, options)
    classification = classify_release_phase_resolution_postmortem(diagnostic_rows, comparison_rows, options)
    prediction_rows = _prediction_rows(classification, diagnostic_rows, comparison_rows, options)
    for row in diagnostic_rows:
        row["release_phase_resolution_postmortem_classification"] = classification["label"]
    for row in comparison_rows:
        row["release_phase_resolution_postmortem_classification"] = classification["label"]
    for row in prediction_rows:
        row["release_phase_resolution_postmortem_classification"] = classification["label"]

    summary_csv = root / "release_phase_resolution_postmortem_summary.csv"
    comparison_csv = root / "release_phase_resolution_peak_comparison.csv"
    prediction_csv = root / "release_phase_resolution_recalibration_prediction.csv"
    report_path = root / "release_phase_resolution_postmortem_report.md"
    _write_csv(summary_csv, diagnostic_rows, _summary_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_csv(prediction_csv, prediction_rows, _prediction_fields())
    _write_report(
        report_path,
        control_id,
        proof_root,
        lift_root,
        diagnostic_rows,
        comparison_rows,
        prediction_rows,
        classification,
        options,
    )
    save_json(
        root / "release_phase_resolution_postmortem_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "proof_root": str(proof_root),
            "lift_root": str(lift_root),
            "summary_rows": diagnostic_rows,
            "comparison_rows": comparison_rows,
            "prediction_rows": prediction_rows,
            "summary_csv": str(summary_csv),
            "comparison_csv": str(comparison_csv),
            "prediction_csv": str(prediction_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": diagnostic_rows,
        "comparison_rows": comparison_rows,
        "prediction_rows": prediction_rows,
        "summary_csv": str(summary_csv),
        "comparison_csv": str(comparison_csv),
        "prediction_csv": str(prediction_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_release_phase_resolution_postmortem(
    rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    options: ReleasePhaseResolutionPostmortemOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the lift failure has a predictable recalibration mechanism."""

    options = options or ReleasePhaseResolutionPostmortemOptions()
    candidate = next((row for row in rows if row.get("group") == "lift_candidate"), {})
    controls = [row for row in rows if row.get("group") == "lift_control"]
    proof = [row for row in rows if row.get("group") == "proof_winner"]
    candidate_comparison = next((row for row in comparisons if row.get("lift_group") == "lift_candidate"), {})
    proof_mean_default = _mean([_float(row.get("major_peaks_at_0p30")) for row in proof])
    proof_mean_strict = _mean([_float(row.get("major_peaks_at_0p40")) for row in proof])
    candidate_default_loss = proof_mean_default - _float(candidate.get("major_peaks_at_0p30"))
    candidate_strict_loss = proof_mean_strict - _float(candidate.get("major_peaks_at_0p40"))
    low_threshold_recovery = _float(candidate.get("major_peaks_at_0p20")) - _float(candidate.get("major_peaks_at_0p30"))
    strict_threshold_loss = _float(candidate.get("major_peaks_at_0p30")) - _float(candidate.get("major_peaks_at_0p40"))
    controls_competitive = bool(controls) and all(
        _float(control.get("major_peaks_at_0p30")) >= _float(candidate.get("major_peaks_at_0p30"))
        and _float(control.get("major_peaks_at_0p40")) >= _float(candidate.get("major_peaks_at_0p40"))
        for control in controls
    )
    tail_close = abs(_float(candidate_comparison.get("tail_area_relative_delta"))) <= options.tail_area_close_fraction
    radial_shift = abs(_float(candidate_comparison.get("tail_packet_radius_delta")))
    peak_radius_shift = abs(_float(candidate_comparison.get("packet_peak_radius_at_shell_peak_delta")))
    arrival_shift = _float(candidate_comparison.get("arrival_time_delta"))
    first_refocus_shift = _float(candidate_comparison.get("first_refocus_time_delta"))
    timing_shift_consistent = (
        abs(arrival_shift) >= options.timing_shift_predict_threshold
        and abs(first_refocus_shift) >= options.timing_shift_predict_threshold
        and math.copysign(1.0, arrival_shift) == math.copysign(1.0, first_refocus_shift)
    )
    radial_shift_predictive = (
        radial_shift >= options.radial_shift_predict_threshold
        and peak_radius_shift >= 0.5 * options.radial_shift_predict_threshold
        and not controls_competitive
    )
    counts = {
        "proof_mean_default_major": proof_mean_default,
        "proof_mean_strict_major": proof_mean_strict,
        "candidate_default_loss": candidate_default_loss,
        "candidate_strict_loss": candidate_strict_loss,
        "candidate_low_threshold_recovery": low_threshold_recovery,
        "candidate_strict_threshold_loss": strict_threshold_loss,
        "controls_competitive": controls_competitive,
        "tail_area_close_to_proof": tail_close,
        "tail_packet_radius_shift": radial_shift,
        "peak_radius_shift": peak_radius_shift,
        "arrival_shift": arrival_shift,
        "first_refocus_shift": first_refocus_shift,
        "timing_shift_consistent": timing_shift_consistent,
        "radial_shift_predictive": radial_shift_predictive,
    }
    if radial_shift_predictive:
        return {
            "label": "resolution_lift_predictable_radial_window_shift",
            "reason": "The lift failure is dominated by a coherent physical radial displacement, so one shell-window-recentered 51^3 retry is predictable.",
            "checks": counts,
        }
    if timing_shift_consistent and not controls_competitive:
        return {
            "label": "resolution_lift_predictable_timing_shift",
            "reason": "Arrival and refocus timing moved coherently without controls matching the candidate, so one cutoff-recalibrated 51^3 retry is predictable.",
            "checks": counts,
        }
    if low_threshold_recovery >= 1.0 and strict_threshold_loss >= 1.0:
        return {
            "label": "resolution_lift_blurred_returns_no_predictive_recalibration",
            "reason": "The 51^3 row still has late return humps below the frozen gates, but controls are competitive and the timing/radial shifts do not isolate one recalibration.",
            "checks": counts,
        }
    if candidate_default_loss >= 1.0:
        return {
            "label": "resolution_lift_returns_lost_no_predictive_recalibration",
            "reason": "The 51^3 row loses default-threshold returns rather than merely shifting them, and no one-step recalibration is supported.",
            "checks": counts,
        }
    return {
        "label": "resolution_lift_inconclusive_no_retry",
        "reason": "The postmortem does not isolate a predictable cutoff or shell-window shift.",
        "checks": counts,
    }


def _load_run(root: Path, kind: str) -> dict[str, Any]:
    summary_csv = _first_existing(
        root,
        (
            "release_phase_proof_pack_summary.csv",
            "release_phase_resolution_lift_summary.csv",
        ),
    )
    robust_csv = _first_existing(
        root,
        (
            "release_phase_proof_pack_threshold_robust_score.csv",
            "release_phase_resolution_lift_threshold_robust_score.csv",
        ),
    )
    summary_json = _first_existing(
        root,
        (
            "release_phase_proof_pack_summary.json",
            "release_phase_resolution_lift_summary.json",
        ),
    )
    rows = _read_csv(summary_csv)
    robust_by_variant = {str(row.get("variant")): row for row in _read_csv(robust_csv)}
    raw_by_variant = _raw_variants(summary_json)
    merged = []
    for row in rows:
        variant = str(row.get("variant"))
        combined = {
            **raw_by_variant.get(variant, {}),
            **robust_by_variant.get(variant, {}),
            **row,
            "source_run_kind": kind,
            "source_root": str(root),
        }
        variant_dir = root / variant
        combined["events"] = _read_csv(variant_dir / "packet_lifecycle_events.csv")
        combined["timeseries"] = _read_csv(variant_dir / "packet_lifecycle_timeseries.csv")
        merged.append(combined)
    return {"rows": merged}


def _first_existing(root: Path, names: tuple[str, ...]) -> Path:
    for name in names:
        path = root / name
        if path.exists():
            return path
    raise FileNotFoundError(f"None of {names} found under {root}")


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _raw_variants(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(row.get("variant")): row for row in data.get("variants", [])}


def _proof_winners(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    winners = [
        row
        for row in rows
        if row.get("prediction_role") == "proof_candidate"
        and _int(row.get("conservative_major_peaks")) >= 9
        and _int(row.get("conservative_refocus_peaks")) >= 8
    ]
    if winners:
        return sorted(winners, key=lambda row: _float(row.get("drive_cutoff_time")))
    return sorted(
        [row for row in rows if row.get("prediction_role") == "proof_candidate"],
        key=lambda row: _float(row.get("conservative_score")),
        reverse=True,
    )[:3]


def _lift_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {"candidate": 0, "low_side_phase_control": 1, "weak_negative_phase_control": 2}
    return sorted(rows, key=lambda row: order.get(str(row.get("prediction_role")), 99))


def _lift_group(row: dict[str, Any]) -> str:
    return "lift_candidate" if row.get("prediction_role") == "candidate" else "lift_control"


def _diagnostic_row(row: dict[str, Any], group: str, options: ReleasePhaseResolutionPostmortemOptions) -> dict[str, Any]:
    thresholds = _threshold_counts(row, options)
    events = [event for event in row.get("events", []) if event.get("event") == "shell_peak"]
    events = sorted(events, key=lambda event: _float(event.get("time")))
    peak_energies = [_float(event.get("energy")) for event in events]
    max_peak = max(peak_energies, default=0.0)
    intervals = np.diff(np.asarray([_float(event.get("time")) for event in events], dtype=float)) if len(events) > 1 else np.asarray([])
    shell_center = _float(row.get("shell_window_radius")) + 0.5 * _float(row.get("shell_window_width"))
    return {
        "group": group,
        "source_run_kind": row.get("source_run_kind"),
        "variant": row.get("variant"),
        "prediction_role": row.get("prediction_role"),
        "grid_size": row.get("grid_size"),
        "dx": row.get("dx"),
        "dt": row.get("dt"),
        "drive_cutoff_time": row.get("drive_cutoff_time"),
        "cutoff_phase_cycles": row.get("cutoff_phase_cycles"),
        "drive_frequency": row.get("drive_frequency"),
        "shell_window_radius": row.get("shell_window_radius"),
        "shell_window_width": row.get("shell_window_width"),
        "shell_window_center": shell_center,
        "default_major_peaks": row.get("default_major_peaks_at_0p30") or row.get("default_major_peaks"),
        "default_refocus_peaks": row.get("default_refocus_peaks_at_0p30") or row.get("default_refocus_peaks"),
        "strict_major_peaks": row.get("conservative_major_peaks") or row.get("min_major_peaks_across_thresholds"),
        "strict_refocus_peaks": row.get("conservative_refocus_peaks") or row.get("min_refocus_peaks_across_thresholds"),
        "major_peaks_at_0p15": thresholds.get(0.15, {}).get("major"),
        "major_peaks_at_0p20": thresholds.get(0.20, {}).get("major"),
        "major_peaks_at_0p25": thresholds.get(0.25, {}).get("major"),
        "major_peaks_at_0p30": thresholds.get(0.30, {}).get("major"),
        "major_peaks_at_0p35": thresholds.get(0.35, {}).get("major"),
        "major_peaks_at_0p40": thresholds.get(0.40, {}).get("major"),
        "refocus_peaks_at_0p15": thresholds.get(0.15, {}).get("refocus"),
        "refocus_peaks_at_0p20": thresholds.get(0.20, {}).get("refocus"),
        "refocus_peaks_at_0p25": thresholds.get(0.25, {}).get("refocus"),
        "refocus_peaks_at_0p30": thresholds.get(0.30, {}).get("refocus"),
        "refocus_peaks_at_0p35": thresholds.get(0.35, {}).get("refocus"),
        "refocus_peaks_at_0p40": thresholds.get(0.40, {}).get("refocus"),
        "arrival_time": row.get("first_shell_arrival_time"),
        "shell_peak_time": row.get("shell_peak_time"),
        "first_refocus_time": row.get("first_refocus_time"),
        "last_refocus_time": row.get("last_refocus_time"),
        "peak_count_from_events": len(events),
        "peak1_time": _event_value(events, 0, "time"),
        "peak2_time": _event_value(events, 1, "time"),
        "peak3_time": _event_value(events, 2, "time"),
        "peak1_energy": _event_value(events, 0, "energy"),
        "peak2_energy": _event_value(events, 1, "energy"),
        "peak3_energy": _event_value(events, 2, "energy"),
        "peak1_ratio_to_max": _ratio(_event_value(events, 0, "energy"), max_peak),
        "peak2_ratio_to_max": _ratio(_event_value(events, 1, "energy"), max_peak),
        "peak3_ratio_to_max": _ratio(_event_value(events, 2, "energy"), max_peak),
        "last_peak_time": _event_value(events, -1, "time"),
        "last_peak_energy": _event_value(events, -1, "energy"),
        "last_peak_ratio_to_max": _ratio(_event_value(events, -1, "energy"), max_peak),
        "first_interval": float(intervals[0]) if intervals.size >= 1 else None,
        "second_interval": float(intervals[1]) if intervals.size >= 2 else None,
        "third_interval": float(intervals[2]) if intervals.size >= 3 else None,
        "mean_inter_peak_spacing": float(np.mean(intervals)) if intervals.size else None,
        "inter_peak_spacing_cv": float(np.std(intervals) / max(float(np.mean(intervals)), EPSILON)) if intervals.size else None,
        "return1_phase_cycles": _phase_at_time(row, _event_value(events, 0, "time")),
        "return2_phase_cycles": _phase_at_time(row, _event_value(events, 1, "time")),
        "return3_phase_cycles": _phase_at_time(row, _event_value(events, 2, "time")),
        "tail_area_after_t50": row.get("tail_area_after_t50") or row.get("threshold_free_tail_energy_area_after_t50"),
        "post_cutoff_shell_area": row.get("post_cutoff_shell_area") or row.get("threshold_free_shell_energy_area_after_cutoff"),
        "shell_energy_autocorrelation": row.get("shell_energy_autocorrelation"),
        "dominant_spectral_concentration": row.get("dominant_spectral_concentration"),
        "return_timing_regularity": row.get("return_timing_regularity"),
        "radial_group_velocity": row.get("post_cutoff_radial_velocity"),
        "radial_group_velocity_r2": row.get("post_cutoff_radial_velocity_r2"),
        "packet_peak_radius_at_shell_peak": row.get("packet_peak_radius_at_shell_peak"),
        "packet_centroid_radius_at_shell_peak": row.get("packet_centroid_radius_at_shell_peak"),
        "packet_peak_alignment_delta": _float(row.get("packet_peak_radius_at_shell_peak")) - shell_center,
        "packet_centroid_alignment_delta": _float(row.get("packet_centroid_radius_at_shell_peak")) - shell_center,
        "packet_width_at_shell_peak": row.get("packet_width_at_shell_peak"),
        "packet_spread_at_shell_peak": row.get("packet_spread_at_shell_peak"),
        "tail_packet_radius_mean": row.get("tail_packet_radius_mean"),
        "tail_packet_width_mean": row.get("tail_packet_width_mean"),
        "tail_packet_spread_mean": row.get("tail_packet_spread_mean"),
        "tail_packet_alignment_delta": _float(row.get("tail_packet_radius_mean")) - shell_center,
        "packet_width_growth_fraction": row.get("packet_width_growth_fraction"),
        "post_cutoff_width_velocity": row.get("post_cutoff_width_velocity"),
        "inward_flux_fraction": row.get("inward_flux_fraction"),
        "outward_flux_fraction": row.get("outward_flux_fraction"),
        "retention": row.get("retention") or row.get("tail_shell_retention"),
        "outer_shell": row.get("outer_shell") or row.get("tail_outer_to_shell_mean"),
        "decay": row.get("decay") or row.get("post_cutoff_shell_decay_rate"),
        "no_exit": row.get("no_exit") if row.get("no_exit") is not None else not _bool(row.get("shell_exit_detected")),
        "global_outer_false": row.get("global_outer_false") if row.get("global_outer_false") is not None else not _bool(row.get("global_peak_in_outer_window")),
        "near_miss_returns_below_default_gate": max(0, _int(thresholds.get(0.20, {}).get("major")) - _int(thresholds.get(0.30, {}).get("major"))),
        "strict_threshold_shrinkage": max(0, _int(thresholds.get(0.30, {}).get("major")) - _int(thresholds.get(0.40, {}).get("major"))),
    }


def _threshold_counts(row: dict[str, Any], options: ReleasePhaseResolutionPostmortemOptions) -> dict[float, dict[str, int]]:
    series = sorted(row.get("timeseries", []), key=lambda item: _float(item.get("time")))
    if not series:
        return {}
    times = np.asarray([_float(item.get("time")) for item in series], dtype=float)
    shell = np.asarray([_float(item.get("shell_window_energy")) for item in series], dtype=float)
    post_indices = np.flatnonzero(times > _float(row.get("drive_cutoff_time")))
    counts: dict[float, dict[str, int]] = {}
    for threshold in (0.15, 0.20, 0.25, 0.30, 0.35, 0.40):
        threshold_options = dataclass_replace_threshold(options, threshold)
        peaks = _major_peaks(times, shell, post_indices, threshold_options)
        counts[threshold] = {"major": len(peaks), "refocus": _refocus_count(peaks, options.refocus_threshold_fraction)}
    return counts


class dataclass_replace_threshold:
    """Small adapter exposing only the fields _major_peaks needs."""

    def __init__(self, options: ReleasePhaseResolutionPostmortemOptions, peak_threshold: float) -> None:
        self.peak_threshold_fraction = peak_threshold
        self.min_peak_separation_time = options.min_peak_separation_time


def _comparison_rows(
    proof_winners: list[dict[str, Any]],
    lift_rows: list[dict[str, Any]],
    options: ReleasePhaseResolutionPostmortemOptions,
) -> list[dict[str, Any]]:
    proof_diagnostics = [_diagnostic_row(row, "proof_winner", options) for row in proof_winners]
    proof_mean = _mean_row(proof_diagnostics)
    rows = []
    for lift in lift_rows:
        lift_diag = _diagnostic_row(lift, _lift_group(lift), options)
        matched = _phase_matched_row(lift_diag, proof_diagnostics) or proof_mean
        row = {
            "lift_variant": lift_diag.get("variant"),
            "lift_group": lift_diag.get("group"),
            "lift_phase": lift_diag.get("cutoff_phase_cycles"),
            "comparison_reference": matched.get("variant", "proof_winner_mean"),
            "reference_phase": matched.get("cutoff_phase_cycles"),
            "arrival_time_delta": _float(lift_diag.get("arrival_time")) - _float(matched.get("arrival_time")),
            "first_refocus_time_delta": _float(lift_diag.get("first_refocus_time")) - _float(matched.get("first_refocus_time")),
            "last_peak_time_delta": _float(lift_diag.get("last_peak_time")) - _float(matched.get("last_peak_time")),
            "mean_inter_peak_spacing_delta": _float(lift_diag.get("mean_inter_peak_spacing")) - _float(matched.get("mean_inter_peak_spacing")),
            "default_major_delta": _float(lift_diag.get("major_peaks_at_0p30")) - _float(matched.get("major_peaks_at_0p30")),
            "strict_major_delta": _float(lift_diag.get("major_peaks_at_0p40")) - _float(matched.get("major_peaks_at_0p40")),
            "low_threshold_major_delta": _float(lift_diag.get("major_peaks_at_0p20")) - _float(matched.get("major_peaks_at_0p20")),
            "tail_area_relative_delta": _relative_delta(_float(lift_diag.get("tail_area_after_t50")), _float(matched.get("tail_area_after_t50"))),
            "autocorrelation_delta": _float(lift_diag.get("shell_energy_autocorrelation")) - _float(matched.get("shell_energy_autocorrelation")),
            "spectral_concentration_delta": _float(lift_diag.get("dominant_spectral_concentration")) - _float(matched.get("dominant_spectral_concentration")),
            "return_timing_regularity_delta": _float(lift_diag.get("return_timing_regularity")) - _float(matched.get("return_timing_regularity")),
            "radial_group_velocity_delta": _float(lift_diag.get("radial_group_velocity")) - _float(matched.get("radial_group_velocity")),
            "packet_peak_radius_at_shell_peak_delta": _float(lift_diag.get("packet_peak_radius_at_shell_peak")) - _float(matched.get("packet_peak_radius_at_shell_peak")),
            "packet_centroid_radius_at_shell_peak_delta": _float(lift_diag.get("packet_centroid_radius_at_shell_peak")) - _float(matched.get("packet_centroid_radius_at_shell_peak")),
            "tail_packet_radius_delta": _float(lift_diag.get("tail_packet_radius_mean")) - _float(matched.get("tail_packet_radius_mean")),
            "tail_packet_spread_delta": _float(lift_diag.get("tail_packet_spread_mean")) - _float(matched.get("tail_packet_spread_mean")),
            "width_growth_delta": _float(lift_diag.get("packet_width_growth_fraction")) - _float(matched.get("packet_width_growth_fraction")),
            "near_miss_returns_below_default_gate": lift_diag.get("near_miss_returns_below_default_gate"),
            "strict_threshold_shrinkage": lift_diag.get("strict_threshold_shrinkage"),
        }
        row["failure_mode_hint"] = _failure_mode_hint(row)
        rows.append(row)
    return rows


def _mean_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    keys = set().union(*(row.keys() for row in rows))
    mean: dict[str, Any] = {"variant": "proof_winner_mean"}
    for key in keys:
        values = [_float(row.get(key)) for row in rows if _is_number(row.get(key))]
        if values:
            mean[key] = _mean(values)
    return mean


def _phase_matched_row(lift_row: dict[str, Any], proof_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    phase = _float(lift_row.get("cutoff_phase_cycles"))
    if not proof_rows:
        return None
    return min(proof_rows, key=lambda row: abs(_float(row.get("cutoff_phase_cycles")) - phase))


def _failure_mode_hint(row: dict[str, Any]) -> str:
    if _float(row.get("near_miss_returns_below_default_gate")) >= 1.0 and _float(row.get("strict_threshold_shrinkage")) >= 1.0:
        return "returns_present_but_below_frozen_gates"
    if _float(row.get("default_major_delta")) < 0.0:
        return "default_returns_missing"
    if abs(_float(row.get("tail_packet_radius_delta"))) > 0.75:
        return "radial_tail_shift"
    return "no_single_dominant_shift"


def _prediction_rows(
    classification: dict[str, Any],
    rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    options: ReleasePhaseResolutionPostmortemOptions,
) -> list[dict[str, Any]]:
    candidate = next((row for row in rows if row.get("group") == "lift_candidate"), {})
    candidate_comparison = next((row for row in comparisons if row.get("lift_group") == "lift_candidate"), {})
    label = classification["label"]
    if label == "resolution_lift_predictable_timing_shift":
        shift = _float(candidate_comparison.get("first_refocus_time_delta"))
        cutoff = max(1.0, _float(candidate.get("drive_cutoff_time")) - shift)
        return [
            _prediction_row("predicted_candidate", cutoff, candidate.get("shell_window_radius"), "cutoff shifted by first-refocus timing delta"),
            _prediction_row("low_side_phase_control", cutoff - 0.005, candidate.get("shell_window_radius"), "fixed two-control low-side phase"),
            _prediction_row("weak_negative_phase_control", 17.915, candidate.get("shell_window_radius"), "old failing-side weak control"),
        ]
    if label == "resolution_lift_predictable_radial_window_shift":
        shell_width = _float(candidate.get("shell_window_width"))
        shifted_radius = max(0.0, _float(candidate.get("tail_packet_radius_mean")) - 0.5 * shell_width)
        return [
            _prediction_row("predicted_candidate", candidate.get("drive_cutoff_time"), shifted_radius, "shell window recentered from lifted tail packet radius"),
            _prediction_row("low_side_phase_control", _float(candidate.get("drive_cutoff_time")) - 0.005, shifted_radius, "fixed two-control low-side phase"),
            _prediction_row("weak_negative_phase_control", 17.915, shifted_radius, "old failing-side weak control"),
        ]
    return [
        {
            "recommendation": "no_recalibrated_retry",
            "predicted_cutoff": None,
            "predicted_shell_window_radius": None,
            "predicted_shell_window_width": candidate.get("shell_window_width"),
            "fixed_frequency": candidate.get("drive_frequency"),
            "reason": options.no_retry_reason,
        }
    ]


def _prediction_row(role: str, cutoff: Any, shell_radius: Any, reason: str) -> dict[str, Any]:
    return {
        "recommendation": role,
        "predicted_cutoff": cutoff,
        "predicted_shell_window_radius": shell_radius,
        "predicted_shell_window_width": 4.0,
        "fixed_frequency": 0.92,
        "reason": reason,
    }


def _write_report(
    path: Path,
    control_id: str,
    proof_root: Path,
    lift_root: Path,
    rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ReleasePhaseResolutionPostmortemOptions,
) -> None:
    proof_rows = [row for row in rows if row.get("group") == "proof_winner"]
    lift_rows = [row for row in rows if str(row.get("group", "")).startswith("lift")]
    lines = [
        f"# Release-Phase Resolution Postmortem: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- 41^3 proof root: `{proof_root}`",
        f"- 51^3 lift root: `{lift_root}`",
        "",
        "## Event Count And Threshold Audit",
        "",
        "| Group | Role | Cutoff | Phase | p=0.20 | p=0.30 | p=0.40 | Near-Miss | Strict Shrink | Last Peak |",
        "| --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('group')} | "
            f"{row.get('prediction_role')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{row.get('major_peaks_at_0p20')}/{row.get('refocus_peaks_at_0p20')} | "
            f"{row.get('major_peaks_at_0p30')}/{row.get('refocus_peaks_at_0p30')} | "
            f"{row.get('major_peaks_at_0p40')}/{row.get('refocus_peaks_at_0p40')} | "
            f"{row.get('near_miss_returns_below_default_gate')} | "
            f"{row.get('strict_threshold_shrinkage')} | "
            f"{_format(row.get('last_peak_time'))} |"
        )
    lines.extend(
        [
            "",
            "## Timing, Phase, And Amplitude",
            "",
            "| Group | Cutoff | Arrival | First Refocus | Mean Spacing | CV | P1 Ratio | P2 Ratio | P3 Ratio | Return Phases |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        phases = ", ".join(_format(row.get(key)) for key in ("return1_phase_cycles", "return2_phase_cycles", "return3_phase_cycles"))
        lines.append(
            "| "
            f"{row.get('group')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('arrival_time'))} | "
            f"{_format(row.get('first_refocus_time'))} | "
            f"{_format(row.get('mean_inter_peak_spacing'))} | "
            f"{_format(row.get('inter_peak_spacing_cv'))} | "
            f"{_format(row.get('peak1_ratio_to_max'))} | "
            f"{_format(row.get('peak2_ratio_to_max'))} | "
            f"{_format(row.get('peak3_ratio_to_max'))} | "
            f"{phases} |"
        )
    lines.extend(
        [
            "",
            "## Threshold-Free And Radial Metrics",
            "",
            "| Group | Cutoff | Tail Area | Autocorr | Spectral | Timing Reg | Radial V | Shell Align Peak | Tail Radius | Tail Spread | Inward Flux |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row.get('group')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('tail_area_after_t50'))} | "
            f"{_format(row.get('shell_energy_autocorrelation'))} | "
            f"{_format(row.get('dominant_spectral_concentration'))} | "
            f"{_format(row.get('return_timing_regularity'))} | "
            f"{_format(row.get('radial_group_velocity'))} | "
            f"{_format(row.get('packet_peak_alignment_delta'))} | "
            f"{_format(row.get('tail_packet_radius_mean'))} | "
            f"{_format(row.get('tail_packet_spread_mean'))} | "
            f"{_format(row.get('inward_flux_fraction'))} |"
        )
    lines.extend(
        [
            "",
            "## 51^3 Versus Proof Reference",
            "",
            "| Lift Row | Reference | Arrival dT | First Refocus dT | Last Peak dT | Default dPeaks | Strict dPeaks | Tail Area d | Tail Radius d | Failure Hint |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in comparisons:
        lines.append(
            "| "
            f"{row.get('lift_group')} | "
            f"{row.get('comparison_reference')} | "
            f"{_format(row.get('arrival_time_delta'))} | "
            f"{_format(row.get('first_refocus_time_delta'))} | "
            f"{_format(row.get('last_peak_time_delta'))} | "
            f"{_format(row.get('default_major_delta'))} | "
            f"{_format(row.get('strict_major_delta'))} | "
            f"{_format(row.get('tail_area_relative_delta'))} | "
            f"{_format(row.get('tail_packet_radius_delta'))} | "
            f"{row.get('failure_mode_hint')} |"
        )
    lines.extend(
        [
            "",
            "## Did 51^3 Lose Returns Or Move/Blur Them?",
            "",
            _interpretation(classification),
            "",
            "## Recalibration Prediction",
            "",
            "| Recommendation | Cutoff | Shell Radius | Shell Width | Frequency | Reason |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in predictions:
        lines.append(
            "| "
            f"{row.get('recommendation')} | "
            f"{_format(row.get('predicted_cutoff'))} | "
            f"{_format(row.get('predicted_shell_window_radius'))} | "
            f"{_format(row.get('predicted_shell_window_width'))} | "
            f"{_format(row.get('fixed_frequency'))} | "
            f"{row.get('reason')} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `release_phase_resolution_postmortem_report.md`",
            "- `release_phase_resolution_postmortem_summary.csv`",
            "- `release_phase_resolution_peak_comparison.csv`",
            "- `release_phase_resolution_recalibration_prediction.csv`",
            "- `release_phase_resolution_postmortem_summary.json`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "resolution_lift_predictable_radial_window_shift":
        return "The lifted packet appears physically displaced relative to the frozen shell window; one shell-window-recentered retry is justified by the postmortem."
    if label == "resolution_lift_predictable_timing_shift":
        return "The lifted packet shows a coherent arrival/refocus timing shift; one cutoff-recalibrated retry is justified by the postmortem."
    if label == "resolution_lift_blurred_returns_no_predictive_recalibration":
        return "The 51^3 run did not simply erase the packet: late return humps remain below the frozen event gates. But the same shrinkage appears in the controls, and the timing/radial shifts do not isolate one predicted recalibration. Freeze the 51^3 result as a clean scale failure for now."
    if label == "resolution_lift_returns_lost_no_predictive_recalibration":
        return "The 51^3 run loses default-threshold returns relative to the proof pack and the postmortem does not find a single predictive correction."
    return "The comparison is inconclusive and does not justify a physics retry."


def _event_value(events: list[dict[str, Any]], index: int, key: str) -> float | None:
    if not events:
        return None
    try:
        return _float(events[index].get(key))
    except IndexError:
        return None


def _phase_at_time(row: dict[str, Any], time: Any) -> float | None:
    if time is None:
        return None
    return (_float(row.get("drive_frequency")) * _float(time)) % 1.0


def _ratio(value: Any, denom: float) -> float | None:
    if denom <= EPSILON or value is None:
        return None
    return _float(value) / denom


def _relative_delta(value: float, reference: float) -> float:
    return (value - reference) / max(abs(reference), EPSILON)


def _mean(values: list[float]) -> float:
    parsed = [value for value in values if math.isfinite(value)]
    return float(np.mean(parsed)) if parsed else 0.0


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return value not in (None, "")
    except (TypeError, ValueError):
        return False


def _float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _summary_fields() -> list[str]:
    return [
        "group",
        "release_phase_resolution_postmortem_classification",
        "source_run_kind",
        "variant",
        "prediction_role",
        "grid_size",
        "dx",
        "dt",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "drive_frequency",
        "shell_window_radius",
        "shell_window_width",
        "shell_window_center",
        "default_major_peaks",
        "default_refocus_peaks",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "major_peaks_at_0p15",
        "major_peaks_at_0p20",
        "major_peaks_at_0p25",
        "major_peaks_at_0p30",
        "major_peaks_at_0p35",
        "major_peaks_at_0p40",
        "refocus_peaks_at_0p15",
        "refocus_peaks_at_0p20",
        "refocus_peaks_at_0p25",
        "refocus_peaks_at_0p30",
        "refocus_peaks_at_0p35",
        "refocus_peaks_at_0p40",
        "arrival_time",
        "shell_peak_time",
        "first_refocus_time",
        "last_refocus_time",
        "peak_count_from_events",
        "peak1_time",
        "peak2_time",
        "peak3_time",
        "peak1_energy",
        "peak2_energy",
        "peak3_energy",
        "peak1_ratio_to_max",
        "peak2_ratio_to_max",
        "peak3_ratio_to_max",
        "last_peak_time",
        "last_peak_energy",
        "last_peak_ratio_to_max",
        "first_interval",
        "second_interval",
        "third_interval",
        "mean_inter_peak_spacing",
        "inter_peak_spacing_cv",
        "return1_phase_cycles",
        "return2_phase_cycles",
        "return3_phase_cycles",
        "tail_area_after_t50",
        "post_cutoff_shell_area",
        "shell_energy_autocorrelation",
        "dominant_spectral_concentration",
        "return_timing_regularity",
        "radial_group_velocity",
        "radial_group_velocity_r2",
        "packet_peak_radius_at_shell_peak",
        "packet_centroid_radius_at_shell_peak",
        "packet_peak_alignment_delta",
        "packet_centroid_alignment_delta",
        "packet_width_at_shell_peak",
        "packet_spread_at_shell_peak",
        "tail_packet_radius_mean",
        "tail_packet_width_mean",
        "tail_packet_spread_mean",
        "tail_packet_alignment_delta",
        "packet_width_growth_fraction",
        "post_cutoff_width_velocity",
        "inward_flux_fraction",
        "outward_flux_fraction",
        "retention",
        "outer_shell",
        "decay",
        "no_exit",
        "global_outer_false",
        "near_miss_returns_below_default_gate",
        "strict_threshold_shrinkage",
    ]


def _comparison_fields() -> list[str]:
    return [
        "release_phase_resolution_postmortem_classification",
        "lift_variant",
        "lift_group",
        "lift_phase",
        "comparison_reference",
        "reference_phase",
        "arrival_time_delta",
        "first_refocus_time_delta",
        "last_peak_time_delta",
        "mean_inter_peak_spacing_delta",
        "default_major_delta",
        "strict_major_delta",
        "low_threshold_major_delta",
        "tail_area_relative_delta",
        "autocorrelation_delta",
        "spectral_concentration_delta",
        "return_timing_regularity_delta",
        "radial_group_velocity_delta",
        "packet_peak_radius_at_shell_peak_delta",
        "packet_centroid_radius_at_shell_peak_delta",
        "tail_packet_radius_delta",
        "tail_packet_spread_delta",
        "width_growth_delta",
        "near_miss_returns_below_default_gate",
        "strict_threshold_shrinkage",
        "failure_mode_hint",
    ]


def _prediction_fields() -> list[str]:
    return [
        "release_phase_resolution_postmortem_classification",
        "recommendation",
        "predicted_cutoff",
        "predicted_shell_window_radius",
        "predicted_shell_window_width",
        "fixed_frequency",
        "reason",
    ]
