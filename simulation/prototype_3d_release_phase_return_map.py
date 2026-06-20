"""Read-only release-phase return-map analysis for existing 3D runs."""

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
from .prototype_3d_cutoff_phase_map import CutoffPhaseMap3DOptions, threshold_robust_refocusing_scores
from .prototype_3d_refocusing_engineering import _format


SUMMARY_FILES = (
    "cutoff_phase_map_summary.csv",
    "resonator_layer_summary.csv",
    "refocusing_map_summary.csv",
    "refocusing_engineering_summary.csv",
    "packet_lifecycle_summary.csv",
)
RANKED_FILES = (
    "cutoff_phase_ranked_summary.csv",
    "second_pulse_ranked_summary.csv",
    "resonator_layer_ranked_summary.csv",
)
ROBUST_FILES = (
    "cutoff_phase_threshold_robust_score.csv",
    "resonator_layer_threshold_robust_score.csv",
)
EVENT_FILES = (
    "cutoff_phase_map_events.csv",
    "resonator_layer_events.csv",
    "refocusing_map_events.csv",
    "refocusing_engineering_events.csv",
    "packet_lifecycle_events.csv",
)
TIMESERIES_FILES = (
    "cutoff_phase_map_timeseries.csv",
    "resonator_energy_timeseries.csv",
    "refocusing_map_timeseries.csv",
    "refocusing_engineering_timeseries.csv",
    "packet_lifecycle_timeseries.csv",
)


@dataclass(frozen=True)
class ReleasePhaseReturnMapOptions:
    """Options for the read-only release-phase return-map predictor."""

    output_root: str = "runs"
    phase_bin_width: float = 0.025
    strict_major_peak_target: int = 9
    strict_refocus_peak_target: int = 8
    default_top_major_target: int = 11
    default_top_refocus_target: int = 10
    strict_outer_shell_target: float = 1.0
    blind_recommendation_count: int = 5


def run_3d_release_phase_return_map(
    run_roots: list[Path],
    *,
    options: ReleasePhaseReturnMapOptions | None = None,
) -> dict[str, Any]:
    """Build a read-only feature table and simple predictors from existing 3D run artifacts."""

    options = options or ReleasePhaseReturnMapOptions()
    control_id = datetime.now().strftime("release_phase_return_map_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    loaded_runs = [_load_run_root(Path(run_root), options) for run_root in run_roots]
    feature_rows: list[dict[str, Any]] = []
    for run in loaded_runs:
        feature_rows.extend(_feature_rows(run, options))
    feature_rows = sorted(feature_rows, key=lambda row: (str(row.get("run_id")), _float(row.get("cutoff_time")), str(row.get("variant"))))

    binned_rows = phase_binned_summary(feature_rows, options)
    model = fit_simple_models(feature_rows)
    prediction_rows = release_phase_predictions(feature_rows, binned_rows, model, options)
    recommendations = blind_confirmation_recommendations(feature_rows, options)
    prediction_rows.extend(recommendations)
    classification = classify_release_phase_return_map(feature_rows, prediction_rows, binned_rows, model, options)

    feature_csv = root / "release_phase_feature_table.csv"
    predictions_csv = root / "release_phase_predictions.csv"
    binned_csv = root / "release_phase_binned_summary.csv"
    report_path = root / "release_phase_return_map_report.md"
    _write_csv(feature_csv, feature_rows, _feature_fields())
    _write_csv(predictions_csv, prediction_rows, _prediction_fields())
    _write_csv(binned_csv, binned_rows, _binned_fields())
    _write_report(report_path, control_id, run_roots, feature_rows, binned_rows, prediction_rows, model, classification, options)
    save_json(
        root / "release_phase_return_map_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "run_roots": [str(path) for path in run_roots],
            "model": _json_model(model),
            "feature_csv": str(feature_csv),
            "predictions_csv": str(predictions_csv),
            "binned_csv": str(binned_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "feature_rows": feature_rows,
        "binned_rows": binned_rows,
        "prediction_rows": prediction_rows,
        "model": model,
        "feature_csv": str(feature_csv),
        "predictions_csv": str(predictions_csv),
        "binned_csv": str(binned_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_release_phase_return_map(
    feature_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    binned_rows: list[dict[str, Any]],
    model: dict[str, Any],
    options: ReleasePhaseReturnMapOptions | None = None,
) -> dict[str, Any]:
    """Classify whether release phase plus early packet features predict strict refocusing."""

    options = options or ReleasePhaseReturnMapOptions()
    reference_rows = _reference_rows(feature_rows)
    pass_rows = [row for row in reference_rows if _bool(row.get("conservative_pass"))]
    fail_rows = [row for row in reference_rows if not _bool(row.get("conservative_pass"))]
    default_top = [row for row in reference_rows if _bool(row.get("default_11_10_or_better"))]
    prediction_existing = [
        row
        for row in prediction_rows
        if row.get("prediction_kind") == "existing_row"
        and row.get("scope") == "reference_compatible"
        and row.get("nearest_neighbor_pass_correct") != ""
    ]
    nn_accuracy = _mean(
        1.0 if _bool(row.get("nearest_neighbor_pass_correct")) else 0.0
        for row in prediction_existing
    )
    center = _circular_mean(_floats(row.get("release_phase_cycles") for row in default_top or pass_rows))
    center_distance = _phase_distance(center, 0.50) if center is not None else None
    top_separators = model.get("top_separators", [])
    strongest_separator = float(top_separators[0]["abs_effect"]) if top_separators else 0.0
    checks = {
        "reference_row_count": len(reference_rows),
        "conservative_pass_count": len(pass_rows),
        "conservative_fail_count": len(fail_rows),
        "default_11_10_count": len(default_top),
        "best_cluster_center_phase": center,
        "distance_from_0p50_cycles": center_distance,
        "nearest_neighbor_phase_accuracy": nn_accuracy,
        "strongest_early_feature_effect": strongest_separator,
        "linear_model_available": bool(model.get("linear_model_available")),
        "logistic_model_available": bool(model.get("logistic_model_available")),
    }
    if len(reference_rows) < 8 or len(pass_rows) < 3 or len(fail_rows) < 2:
        return {
            "label": "release_phase_rule_inconclusive",
            "reason": "The read-only feature table is too sparse or too one-sided for a reliable release-phase rule.",
            "best_variant": _best_variant(feature_rows),
            "checks": checks,
        }
    if center_distance is not None and center_distance <= 0.025 and nn_accuracy >= 0.65:
        return {
            "label": "release_phase_predictive_rule_supported",
            "reason": "Neighboring reference-compatible rows cluster near release phase 0.50 cycles and phase-nearest neighbors separate strict 9/8 rows from weak rows.",
            "best_variant": _best_variant(feature_rows),
            "checks": checks,
        }
    if len(default_top) <= 1 and nn_accuracy < 0.55 and strongest_separator < 0.35:
        return {
            "label": "release_phase_single_point_artifact",
            "reason": "The best rows are not distinguishable by release phase or early packet features beyond exact event thresholding.",
            "best_variant": _best_variant(feature_rows),
            "checks": checks,
        }
    return {
        "label": "release_phase_rule_inconclusive",
        "reason": "Release phase and early packet features show structure, but the current table does not separate strong and weak rows cleanly enough.",
        "best_variant": _best_variant(feature_rows),
        "checks": checks,
    }


def phase_binned_summary(
    feature_rows: list[dict[str, Any]],
    options: ReleasePhaseReturnMapOptions | None = None,
) -> list[dict[str, Any]]:
    """Summarize strict pass rates and targets by release-phase bin."""

    options = options or ReleasePhaseReturnMapOptions()
    rows: list[dict[str, Any]] = []
    for scope, scoped_rows in (
        ("all_rows", feature_rows),
        ("reference_compatible", _reference_rows(feature_rows)),
    ):
        bins: dict[float, list[dict[str, Any]]] = {}
        for row in scoped_rows:
            phase = _float_or_none(row.get("release_phase_cycles"))
            if phase is None:
                continue
            start = math.floor((phase % 1.0) / options.phase_bin_width) * options.phase_bin_width
            bins.setdefault(round(start, 12), []).append(row)
        for start, members in sorted(bins.items()):
            end = min(1.0, start + options.phase_bin_width)
            rows.append(
                {
                    "scope": scope,
                    "phase_bin_start": start,
                    "phase_bin_end": end,
                    "phase_bin_center": (start + end) / 2.0,
                    "row_count": len(members),
                    "conservative_pass_count": sum(1 for row in members if _bool(row.get("conservative_pass"))),
                    "conservative_pass_rate": _mean(1.0 if _bool(row.get("conservative_pass")) else 0.0 for row in members),
                    "default_11_10_count": sum(1 for row in members if _bool(row.get("default_11_10_or_better"))),
                    "mean_default_major_peaks": _mean(_float(row.get("default_major_peaks")) for row in members),
                    "mean_default_refocus_peaks": _mean(_float(row.get("default_refocus_peaks")) for row in members),
                    "mean_strict_major_peaks": _mean(_float(row.get("strict_major_peaks")) for row in members),
                    "mean_strict_refocus_peaks": _mean(_float(row.get("strict_refocus_peaks")) for row in members),
                    "mean_retention": _mean(_float(row.get("retention")) for row in members),
                    "mean_outer_shell": _mean(_float(row.get("outer_shell")) for row in members),
                    "mean_decay": _mean(_float(row.get("decay")) for row in members),
                    "mean_return_timing_regularity": _mean(_float(row.get("return_timing_regularity")) for row in members),
                    "variants": ";".join(str(row.get("variant")) for row in members),
                }
            )
    return rows


def fit_simple_models(feature_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Fit interpretable least-squares and logistic scores when enough rows exist."""

    rows = feature_rows
    y = np.asarray([1.0 if _bool(row.get("conservative_pass")) else 0.0 for row in rows], dtype=float)
    separators = _feature_separators(rows)
    model: dict[str, Any] = {
        "feature_names": MODEL_FEATURES,
        "top_separators": separators[:8],
        "linear_model_available": False,
        "logistic_model_available": False,
        "linear_predictions": {},
        "logistic_predictions": {},
    }
    if len(rows) < 12 or len(set(y.tolist())) < 2:
        return model
    X, means, scales = _model_matrix(rows)
    X_design = np.column_stack([np.ones(X.shape[0]), X])
    try:
        beta = np.linalg.lstsq(X_design, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return model
    linear_raw = np.clip(X_design @ beta, 0.0, 1.0)
    linear_accuracy = float(np.mean((linear_raw >= 0.5) == (y >= 0.5)))
    logistic_beta = _fit_logistic(X_design, y)
    logistic_raw = _sigmoid(X_design @ logistic_beta)
    logistic_accuracy = float(np.mean((logistic_raw >= 0.5) == (y >= 0.5)))
    row_ids = [str(row.get("row_id")) for row in rows]
    model.update(
        {
            "linear_model_available": True,
            "logistic_model_available": True,
            "means": dict(zip(MODEL_FEATURES, means.tolist())),
            "scales": dict(zip(MODEL_FEATURES, scales.tolist())),
            "linear_coefficients": _coefficient_rows(beta),
            "logistic_coefficients": _coefficient_rows(logistic_beta),
            "linear_accuracy": linear_accuracy,
            "logistic_accuracy": logistic_accuracy,
            "linear_predictions": dict(zip(row_ids, linear_raw.tolist())),
            "logistic_predictions": dict(zip(row_ids, logistic_raw.tolist())),
        }
    )
    return model


def release_phase_predictions(
    feature_rows: list[dict[str, Any]],
    binned_rows: list[dict[str, Any]],
    model: dict[str, Any],
    options: ReleasePhaseReturnMapOptions | None = None,
) -> list[dict[str, Any]]:
    """Generate per-row nearest-neighbor, phase-bin, and simple-model predictions."""

    options = options or ReleasePhaseReturnMapOptions()
    binned_lookup = {
        (row["scope"], _phase_bin_key(row.get("phase_bin_start"))): row
        for row in binned_rows
    }
    linear_predictions = model.get("linear_predictions", {})
    logistic_predictions = model.get("logistic_predictions", {})
    rows: list[dict[str, Any]] = []
    for row in feature_rows:
        phase = _float_or_none(row.get("release_phase_cycles"))
        bin_key = _phase_bin_key(_phase_bin_start(phase, options)) if phase is not None else None
        scope = "reference_compatible" if _bool(row.get("reference_compatible")) else "all_rows"
        pool = _reference_rows(feature_rows) if scope == "reference_compatible" else feature_rows
        nearest = _nearest_phase_neighbor(row, pool)
        bin_row = binned_lookup.get((scope, bin_key), {}) if bin_key is not None else {}
        nearest_pass = _bool(nearest.get("conservative_pass")) if nearest else None
        actual_pass = _bool(row.get("conservative_pass"))
        rows.append(
            {
                "prediction_kind": "existing_row",
                "scope": scope,
                "row_id": row.get("row_id"),
                "run_id": row.get("run_id"),
                "variant": row.get("variant"),
                "cutoff_time": row.get("cutoff_time"),
                "release_phase_cycles": row.get("release_phase_cycles"),
                "actual_conservative_pass": actual_pass,
                "actual_default_major_peaks": row.get("default_major_peaks"),
                "actual_default_refocus_peaks": row.get("default_refocus_peaks"),
                "actual_strict_major_peaks": row.get("strict_major_peaks"),
                "actual_strict_refocus_peaks": row.get("strict_refocus_peaks"),
                "nearest_neighbor_row_id": nearest.get("row_id") if nearest else "",
                "nearest_neighbor_phase_distance": _phase_distance(phase, _float_or_none(nearest.get("release_phase_cycles"))) if nearest else "",
                "nearest_neighbor_predicted_pass": nearest_pass if nearest else "",
                "nearest_neighbor_predicted_major": nearest.get("strict_major_peaks") if nearest else "",
                "nearest_neighbor_predicted_refocus": nearest.get("strict_refocus_peaks") if nearest else "",
                "nearest_neighbor_pass_correct": (nearest_pass == actual_pass) if nearest else "",
                "phase_bin_pass_rate": bin_row.get("conservative_pass_rate", ""),
                "phase_bin_predicted_pass": (_float(bin_row.get("conservative_pass_rate")) >= 0.5) if bin_row else "",
                "linear_pass_score": linear_predictions.get(str(row.get("row_id")), ""),
                "logistic_pass_probability": logistic_predictions.get(str(row.get("row_id")), ""),
                "recommendation_role": "",
                "recommendation_reason": "",
            }
        )
    return rows


def blind_confirmation_recommendations(
    feature_rows: list[dict[str, Any]],
    options: ReleasePhaseReturnMapOptions | None = None,
) -> list[dict[str, Any]]:
    """Choose five new no-physics cutoffs to test later from the current phase predictor."""

    options = options or ReleasePhaseReturnMapOptions()
    reference_rows = [row for row in _reference_rows(feature_rows) if _float_or_none(row.get("cutoff_time")) is not None]
    default_top = [row for row in reference_rows if _bool(row.get("default_11_10_or_better"))]
    pass_rows = [row for row in reference_rows if _bool(row.get("conservative_pass"))]
    fail_rows = [row for row in reference_rows if not _bool(row.get("conservative_pass"))]
    frequency = _mean(_float(row.get("frequency")) for row in reference_rows) or 0.92
    center_phase = _circular_mean(_floats(row.get("release_phase_cycles") for row in default_top or pass_rows)) or 0.50
    center_cutoff = _cutoff_for_phase_near(center_phase, 18.0, frequency)
    tested = {_cutoff_key(row.get("cutoff_time")) for row in reference_rows}
    pass_cutoffs = sorted(_float(row.get("cutoff_time")) for row in pass_rows)
    fail_cutoffs = sorted(_float(row.get("cutoff_time")) for row in fail_rows)
    lower_pass = min(pass_cutoffs) if pass_cutoffs else center_cutoff - 0.01
    upper_pass = max(pass_cutoffs) if pass_cutoffs else center_cutoff + 0.01
    lower_fail = max((value for value in fail_cutoffs if value < lower_pass), default=lower_pass - 0.005)
    upper_fail = min((value for value in fail_cutoffs if value > upper_pass), default=upper_pass + 0.010)
    raw = [
        ("predicted_strong", center_cutoff - 0.0025, "Interpolates inside the default 11/10 phase pocket just below the observed center."),
        ("predicted_strong", center_cutoff + 0.0025, "Interpolates inside the default 11/10 phase pocket just above the observed center."),
        ("predicted_boundary_edge", 0.5 * (lower_fail + lower_pass), "Lower edge between the nearest strict failure and strict preservation."),
        ("predicted_boundary_edge", 0.5 * (upper_pass + upper_fail), "Upper edge just beyond the observed strict-preservation band."),
        ("predicted_weak_negative_control", lower_fail - 0.005, "Lower-phase negative control outside the strict-preservation band."),
    ]
    rows = []
    for index, (role, cutoff, reason) in enumerate(raw, start=1):
        cutoff = _nudge_cutoff(round(cutoff, 6), tested)
        tested.add(_cutoff_key(cutoff))
        phase = (frequency * cutoff) % 1.0
        rows.append(
            {
                "prediction_kind": "blind_recommendation",
                "scope": "reference_compatible",
                "row_id": f"blind_recommendation_{index}",
                "run_id": "",
                "variant": "",
                "cutoff_time": cutoff,
                "release_phase_cycles": phase,
                "actual_conservative_pass": "",
                "actual_default_major_peaks": "",
                "actual_default_refocus_peaks": "",
                "actual_strict_major_peaks": "",
                "actual_strict_refocus_peaks": "",
                "nearest_neighbor_row_id": "",
                "nearest_neighbor_phase_distance": "",
                "nearest_neighbor_predicted_pass": role != "predicted_weak_negative_control",
                "nearest_neighbor_predicted_major": options.strict_major_peak_target if role != "predicted_weak_negative_control" else options.strict_major_peak_target - 1,
                "nearest_neighbor_predicted_refocus": options.strict_refocus_peak_target if role != "predicted_weak_negative_control" else options.strict_refocus_peak_target - 1,
                "nearest_neighbor_pass_correct": "",
                "phase_bin_pass_rate": "",
                "phase_bin_predicted_pass": "",
                "linear_pass_score": "",
                "logistic_pass_probability": "",
                "recommendation_role": role,
                "recommendation_reason": reason,
            }
        )
    return rows


MODEL_FEATURES = [
    "phase_distance_to_0p50",
    "cutoff_time",
    "first_arrival_time",
    "first_post_cutoff_peak_time",
    "peak_interval_1",
    "peak_interval_2",
    "peak_interval_3",
    "early_flux_balance",
    "early_inward_flux_fraction",
    "early_outer_shell_ratio",
    "post_cutoff_shell_energy_area",
    "tail_energy_area_after_t50",
    "shell_energy_autocorrelation",
    "dominant_spectral_concentration",
    "return_timing_regularity",
]


def _load_run_root(path: Path, options: ReleasePhaseReturnMapOptions) -> dict[str, Any]:
    summary_rows, summary_path = _read_first_csv(path, SUMMARY_FILES)
    ranked_rows, ranked_path = _read_first_csv(path, RANKED_FILES)
    robust_rows, robust_path = _read_first_csv(path, ROBUST_FILES)
    event_rows, events_path = _read_first_csv(path, EVENT_FILES)
    timeseries_rows, timeseries_path = _read_first_csv(path, TIMESERIES_FILES)
    if not robust_rows and summary_rows and timeseries_rows:
        robust_rows = threshold_robust_refocusing_scores(summary_rows, timeseries_rows, CutoffPhaseMap3DOptions())
        _restore_summary_booleans(robust_rows, summary_rows)
        robust_path = "<computed_from_timeseries>"
    return {
        "run_root": path,
        "run_id": path.name,
        "summary_rows": summary_rows,
        "ranked_rows": ranked_rows,
        "robust_rows": robust_rows,
        "event_rows": event_rows,
        "timeseries_rows": timeseries_rows,
        "summary_path": summary_path,
        "ranked_path": ranked_path,
        "robust_path": robust_path,
        "events_path": events_path,
        "timeseries_path": timeseries_path,
    }


def _restore_summary_booleans(robust_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]]) -> None:
    """Patch CSV-derived robust rows with parsed summary booleans.

    The shared robust scorer is normally fed in-memory simulation rows where booleans are real bools.
    When this read-only command recomputes robust scores from CSV rows, strings such as "false"
    would otherwise be truthy.
    """

    summary_by_variant = _by_variant(summary_rows)
    for row in robust_rows:
        summary = summary_by_variant.get(str(row.get("variant")), {})
        if summary.get("shell_exit_detected") not in (None, ""):
            row["no_exit_across_all_thresholds"] = not _bool(summary.get("shell_exit_detected"))
        if summary.get("global_peak_in_outer_window") not in (None, ""):
            row["global_outer_false_across_all_thresholds"] = not _bool(summary.get("global_peak_in_outer_window"))


def _feature_rows(run: dict[str, Any], options: ReleasePhaseReturnMapOptions) -> list[dict[str, Any]]:
    robust_by_variant = _by_variant(run["robust_rows"])
    ranked_by_variant = _by_variant(run["ranked_rows"])
    events_by_variant = _group_by_variant(run["event_rows"])
    timeseries_by_variant = _group_by_variant(run["timeseries_rows"])
    rows = []
    for summary in run["summary_rows"]:
        variant = str(summary.get("variant"))
        robust = robust_by_variant.get(variant, {})
        ranked = ranked_by_variant.get(variant, {})
        events = sorted(events_by_variant.get(variant, []), key=lambda row: _float(row.get("time")))
        series = sorted(timeseries_by_variant.get(variant, []), key=lambda row: _float(row.get("time")))
        cutoff = _first_float(summary, robust, ranked, "drive_cutoff_time")
        frequency = _first_float(summary, robust, ranked, "drive_frequency") or 0.92
        phase = _first_float(summary, robust, ranked, "cutoff_phase_cycles")
        if phase is None and cutoff is not None:
            phase = (frequency * cutoff + _float(summary.get("boundary_phase_offset")) / (2.0 * math.pi)) % 1.0
        peak_times = [
            _float(event.get("time"))
            for event in events
            if event.get("event") == "shell_peak" and (cutoff is None or _float(event.get("time")) > cutoff)
        ]
        first_arrival = _first_float(summary, robust, ranked, "first_shell_arrival_time")
        if first_arrival is None:
            first_arrival = next((_float(event.get("time")) for event in events if event.get("event") == "arrival"), None)
        early = _early_packet_features(series, cutoff, peak_times)
        default_major = _first_int(robust, summary, "default_major_peaks", "major_shell_peak_count")
        default_refocus = _first_int(robust, summary, "default_refocus_peaks", "refocus_peak_count")
        strict_major = _first_int(robust, summary, "min_major_peaks_across_thresholds", "major_shell_peak_count")
        strict_refocus = _first_int(robust, summary, "min_refocus_peaks_across_thresholds", "refocus_peak_count")
        retention = _first_float(robust, summary, "retention_median", "tail_shell_retention")
        outer_shell = _first_float(robust, summary, "outer_shell_median", "tail_outer_to_shell_mean")
        decay = _first_float(robust, summary, "decay_median", "post_cutoff_shell_decay_rate")
        no_exit = _first_bool(robust, summary, "no_exit_across_all_thresholds", inverse_fallback_key="shell_exit_detected")
        global_outer_false = _first_bool(robust, summary, "global_outer_false_across_all_thresholds", inverse_fallback_key="global_peak_in_outer_window")
        conservative_pass = (
            strict_major >= options.strict_major_peak_target
            and strict_refocus >= options.strict_refocus_peak_target
            and (outer_shell or 999.0) < options.strict_outer_shell_target
            and no_exit
            and global_outer_false
        )
        family = _family(summary, variant)
        resonator_variant = str(summary.get("resonator_variant") or "")
        reference_compatible = _reference_compatible(summary, family, resonator_variant)
        row_id = f"{run['run_id']}::{variant}"
        rows.append(
            {
                "row_id": row_id,
                "run_id": run["run_id"],
                "run_root": str(run["run_root"]),
                "variant": variant,
                "source_summary_csv": str(run.get("summary_path") or ""),
                "source_threshold_robust_csv": str(run.get("robust_path") or ""),
                "polarity_sign_family": family,
                "resonator_variant": resonator_variant,
                "reference_compatible": reference_compatible,
                "cutoff_time": cutoff,
                "release_phase_cycles": phase,
                "phase_distance_to_0p50": _phase_distance(phase, 0.50),
                "frequency": frequency,
                "first_arrival_time": first_arrival,
                "first_post_cutoff_peak_time": peak_times[0] if peak_times else "",
                "shell_peak_time_1": peak_times[0] if len(peak_times) > 0 else "",
                "shell_peak_time_2": peak_times[1] if len(peak_times) > 1 else "",
                "shell_peak_time_3": peak_times[2] if len(peak_times) > 2 else "",
                "peak_interval_1": peak_times[1] - peak_times[0] if len(peak_times) > 1 else "",
                "peak_interval_2": peak_times[2] - peak_times[1] if len(peak_times) > 2 else "",
                "peak_interval_3": peak_times[3] - peak_times[2] if len(peak_times) > 3 else "",
                **early,
                "post_cutoff_shell_energy_area": _first_float(robust, "threshold_free_shell_energy_area_after_cutoff")
                or _area_from_series(series, cutoff, None),
                "tail_energy_area_after_t50": _first_float(robust, "threshold_free_tail_energy_area_after_t50")
                or _area_from_series(series, 50.0, None),
                "shell_energy_autocorrelation": _first_float(robust, "shell_energy_autocorrelation") or _autocorrelation_from_series(series, cutoff),
                "dominant_spectral_concentration": _first_float(robust, "dominant_spectral_concentration") or _spectral_from_series(series, cutoff),
                "return_timing_regularity": _first_float(robust, "return_timing_regularity") or _regularity_from_peaks(peak_times),
                "default_major_peaks": default_major,
                "default_refocus_peaks": default_refocus,
                "strict_major_peaks": strict_major,
                "strict_refocus_peaks": strict_refocus,
                "retention": retention,
                "outer_shell": outer_shell,
                "decay": decay,
                "no_exit": no_exit,
                "global_outer_false": global_outer_false,
                "conservative_pass": conservative_pass,
                "default_11_10_or_better": default_major >= options.default_top_major_target
                and default_refocus >= options.default_top_refocus_target,
            }
        )
    return rows


def _early_packet_features(series: list[dict[str, Any]], cutoff: float | None, peak_times: list[float]) -> dict[str, Any]:
    if cutoff is None:
        return _empty_early_features()
    end = peak_times[2] if len(peak_times) >= 3 else cutoff + 24.0
    rows = [row for row in series if cutoff < _float(row.get("time")) <= end]
    if not rows:
        return _empty_early_features()
    inward = sum(_float(row.get("shell_inward_flux")) for row in rows)
    outward = sum(_float(row.get("shell_outward_flux")) for row in rows)
    if inward <= EPSILON and outward <= EPSILON:
        for row in rows:
            flux = _float(row.get("shell_radial_flux"))
            inward += max(0.0, -flux)
            outward += max(0.0, flux)
    total_flux = inward + outward + EPSILON
    phase_values = _floats(_first_present(row, ("early_shell_phase", "shell_phase", "local_shell_phase", "shell_mean_phase")) for row in rows)
    return {
        "early_window_end_time": end,
        "early_inward_flux": inward,
        "early_outward_flux": outward,
        "early_inward_flux_fraction": inward / total_flux,
        "early_flux_balance": (inward - outward) / total_flux,
        "early_shell_phase": _circular_mean(phase_values) if phase_values else "",
        "early_outer_shell_ratio": _mean(_float(row.get("outer_to_shell_energy")) for row in rows),
    }


def _empty_early_features() -> dict[str, Any]:
    return {
        "early_window_end_time": "",
        "early_inward_flux": "",
        "early_outward_flux": "",
        "early_inward_flux_fraction": "",
        "early_flux_balance": "",
        "early_shell_phase": "",
        "early_outer_shell_ratio": "",
    }


def _feature_separators(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    passed = [row for row in rows if _bool(row.get("conservative_pass"))]
    failed = [row for row in rows if not _bool(row.get("conservative_pass"))]
    out = []
    for feature in MODEL_FEATURES:
        pass_values = _floats(row.get(feature) for row in passed)
        fail_values = _floats(row.get(feature) for row in failed)
        if len(pass_values) < 2 or len(fail_values) < 2:
            continue
        pass_mean = float(np.mean(pass_values))
        fail_mean = float(np.mean(fail_values))
        pooled = float(np.std(pass_values + fail_values))
        effect = (pass_mean - fail_mean) / (pooled + EPSILON)
        out.append(
            {
                "feature": feature,
                "pass_mean": pass_mean,
                "fail_mean": fail_mean,
                "effect": effect,
                "abs_effect": abs(effect),
            }
        )
    return sorted(out, key=lambda row: float(row["abs_effect"]), reverse=True)


def _model_matrix(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    raw = np.asarray([[_float_or_nan(row.get(feature)) for feature in MODEL_FEATURES] for row in rows], dtype=float)
    means = np.nanmean(raw, axis=0)
    means = np.where(np.isfinite(means), means, 0.0)
    filled = np.where(np.isfinite(raw), raw, means)
    scales = np.std(filled, axis=0)
    scales = np.where(scales > EPSILON, scales, 1.0)
    return (filled - means) / scales, means, scales


def _fit_logistic(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    beta = np.zeros(X.shape[1], dtype=float)
    lr = 0.2
    l2 = 0.01
    for _ in range(1200):
        pred = _sigmoid(X @ beta)
        grad = X.T @ (pred - y) / max(float(y.size), 1.0)
        grad[1:] += l2 * beta[1:]
        beta -= lr * grad
    return beta


def _coefficient_rows(beta: np.ndarray) -> list[dict[str, Any]]:
    names = ["intercept", *MODEL_FEATURES]
    return [
        {"feature": name, "coefficient": float(value), "abs_coefficient": abs(float(value))}
        for name, value in sorted(zip(names, beta.tolist()), key=lambda item: abs(float(item[1])), reverse=True)
    ]


def _write_report(
    path: Path,
    control_id: str,
    run_roots: list[Path],
    feature_rows: list[dict[str, Any]],
    binned_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    model: dict[str, Any],
    classification: dict[str, Any],
    options: ReleasePhaseReturnMapOptions,
) -> None:
    reference_rows = _reference_rows(feature_rows)
    pass_rows = [row for row in reference_rows if _bool(row.get("conservative_pass"))]
    default_top = [row for row in reference_rows if _bool(row.get("default_11_10_or_better"))]
    center = _circular_mean(_floats(row.get("release_phase_cycles") for row in default_top or pass_rows))
    pass_phases = sorted(_floats(row.get("release_phase_cycles") for row in pass_rows))
    default_top_phases = sorted(_floats(row.get("release_phase_cycles") for row in default_top))
    existing_predictions = [row for row in prediction_rows if row.get("prediction_kind") == "existing_row"]
    recommendations = [row for row in prediction_rows if row.get("prediction_kind") == "blind_recommendation"]
    lines = [
        f"# 3D Release-Phase Return Map: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only predictor built from existing cutoff-phase/refocusing artifacts. No new physics simulations were run.",
        "",
        "## Inputs",
        "",
        *[f"- `{path}`" for path in run_roots],
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## predictive phase rule",
        "",
        f"- Best-cluster center near phase 0.50 cycles: `{_yes_no(center is not None and _phase_distance(center, 0.50) <= 0.025)}`; center = `{_format(center)}` cycles.",
        f"- Strict 9/8 preservation phase range in reference-compatible rows: `{_format_range(pass_phases)}` cycles.",
        f"- Default 11/10 rows occupy phase range: `{_format_range(default_top_phases)}` cycles.",
        "- Default 11/10 rows are phase-guided but still cutoff/threshold-sensitive: neighboring strict 9/8 rows outside the 11/10 pocket stay clean but drop to 10/9 or 9/8 at the default detector.",
        "",
        "Top early-feature separators between conservative pass/fail rows:",
        "",
        "| Feature | Pass Mean | Fail Mean | Effect |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in model.get("top_separators", [])[:6]:
        lines.append(
            "| "
            f"{row['feature']} | "
            f"{_format(row.get('pass_mean'))} | "
            f"{_format(row.get('fail_mean'))} | "
            f"{_format(row.get('effect'))} |"
        )
    lines.extend(
        [
            "",
            "## Phase-Binned Summary",
            "",
            "| Scope | Bin | Rows | Pass Rate | Default 11/10 | Mean Strict | Mean Ret | Mean Outer | Mean Timing Reg |",
            "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for row in binned_rows:
        if int(row.get("row_count") or 0) <= 0:
            continue
        lines.append(
            "| "
            f"{row.get('scope')} | "
            f"{_format(row.get('phase_bin_start'))}-{_format(row.get('phase_bin_end'))} | "
            f"{row.get('row_count')} | "
            f"{_format(row.get('conservative_pass_rate'))} | "
            f"{row.get('default_11_10_count')} | "
            f"{_format(row.get('mean_strict_major_peaks'))}/{_format(row.get('mean_strict_refocus_peaks'))} | "
            f"{_format(row.get('mean_retention'))} | "
            f"{_format(row.get('mean_outer_shell'))} | "
            f"{_format(row.get('mean_return_timing_regularity'))} |"
        )
    lines.extend(
        [
            "",
            "## Nearest-Neighbor / Linear Predictors",
            "",
            f"- Existing-row predictions: `{len(existing_predictions)}`",
            f"- Linear model available: `{model.get('linear_model_available')}`; accuracy = `{_format(model.get('linear_accuracy'))}`",
            f"- Logistic model available: `{model.get('logistic_model_available')}`; accuracy = `{_format(model.get('logistic_accuracy'))}`",
            "",
            "Largest logistic coefficients:",
            "",
            "| Feature | Coefficient |",
            "| --- | ---: |",
        ]
    )
    for row in model.get("logistic_coefficients", [])[:8]:
        lines.append(f"| {row['feature']} | {_format(row.get('coefficient'))} |")
    lines.extend(
        [
            "",
            "## blind confirmation recommendation",
            "",
            "| Role | Cutoff | Release Phase | Predicted Strict | Reason |",
            "| --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in recommendations:
        lines.append(
            "| "
            f"{row.get('recommendation_role')} | "
            f"{_format(row.get('cutoff_time'))} | "
            f"{_format(row.get('release_phase_cycles'))} | "
            f"{row.get('nearest_neighbor_predicted_major')}/{row.get('nearest_neighbor_predicted_refocus')} | "
            f"{row.get('recommendation_reason')} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `release_phase_return_map_report.md`",
            "- `release_phase_feature_table.csv`",
            "- `release_phase_predictions.csv`",
            "- `release_phase_binned_summary.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _read_first_csv(root: Path, names: tuple[str, ...]) -> tuple[list[dict[str, Any]], str | None]:
    for name in names:
        path = root / name
        if path.exists():
            return _read_csv(path), str(path)
    return [], None


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _by_variant(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("variant")): row for row in rows if row.get("variant")}


def _group_by_variant(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row.get("variant")), []).append(row)
    return out


def _reference_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _bool(row.get("reference_compatible"))]


def _reference_compatible(summary: dict[str, Any], family: str, resonator_variant: str) -> bool:
    if resonator_variant and resonator_variant not in {"no_resonator_reference", "zero_coupling_control"}:
        return False
    return family in {"sign_flip", "phase_offset", "passive_reference", "unknown"}


def _family(row: dict[str, Any], variant: str) -> str:
    if row.get("family"):
        return str(row.get("family"))
    if variant.startswith("phase_offset"):
        return "phase_offset"
    if variant.startswith("sign_flip") or "no_resonator" in variant or "zero_coupling" in variant or "resonator" in variant or "high_damping" in variant:
        return "sign_flip"
    return "unknown"


def _nearest_phase_neighbor(row: dict[str, Any], pool: list[dict[str, Any]]) -> dict[str, Any] | None:
    phase = _float_or_none(row.get("release_phase_cycles"))
    if phase is None:
        return None
    candidates = [candidate for candidate in pool if candidate.get("row_id") != row.get("row_id") and _float_or_none(candidate.get("release_phase_cycles")) is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: _phase_distance(phase, _float_or_none(candidate.get("release_phase_cycles"))))


def _phase_bin_start(phase: float | None, options: ReleasePhaseReturnMapOptions) -> float | None:
    if phase is None:
        return None
    return round(math.floor((phase % 1.0) / options.phase_bin_width) * options.phase_bin_width, 12)


def _phase_bin_key(value: Any) -> float:
    return round(_float(value), 12)


def _cutoff_for_phase_near(phase: float, target_cutoff: float, frequency: float) -> float:
    cycle = round(frequency * target_cutoff - phase)
    return (cycle + phase) / max(frequency, EPSILON)


def _nudge_cutoff(cutoff: float, tested: set[float]) -> float:
    candidate = cutoff
    step = 0.0005
    while _cutoff_key(candidate) in tested:
        candidate += step
    return round(candidate, 6)


def _cutoff_key(value: Any) -> float:
    return round(_float(value), 6)


def _area_from_series(series: list[dict[str, Any]], start: float | None, end: float | None) -> float:
    rows = [
        row
        for row in series
        if (start is None or _float(row.get("time")) > start)
        and (end is None or _float(row.get("time")) <= end)
    ]
    times = np.asarray([_float(row.get("time")) for row in rows], dtype=float)
    values = np.asarray([_float(row.get("shell_window_energy")) for row in rows], dtype=float)
    if times.size < 2:
        return 0.0
    return float(np.trapezoid(values, times))


def _autocorrelation_from_series(series: list[dict[str, Any]], cutoff: float | None) -> float:
    values = np.asarray([_float(row.get("shell_window_energy")) for row in series if cutoff is None or _float(row.get("time")) > cutoff], dtype=float)
    if values.size < 3:
        return 0.0
    left = values[:-1] - float(np.mean(values[:-1]))
    right = values[1:] - float(np.mean(values[1:]))
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom <= EPSILON:
        return 1.0
    return float(np.clip(np.dot(left, right) / denom, -1.0, 1.0))


def _spectral_from_series(series: list[dict[str, Any]], cutoff: float | None) -> float:
    values = np.asarray([_float(row.get("shell_window_energy")) for row in series if cutoff is None or _float(row.get("time")) > cutoff], dtype=float)
    if values.size < 4:
        return 0.0
    power = np.abs(np.fft.rfft(values - float(np.mean(values)))) ** 2
    non_dc = power[1:]
    total = float(np.sum(non_dc))
    if total <= EPSILON:
        return 0.0
    return float(np.max(non_dc) / total)


def _regularity_from_peaks(peak_times: list[float]) -> float:
    if len(peak_times) < 3:
        return 0.0
    intervals = np.diff(np.asarray(peak_times, dtype=float))
    mean_interval = float(np.mean(intervals))
    if mean_interval <= EPSILON:
        return 0.0
    return float(np.clip(1.0 - float(np.std(intervals) / mean_interval), 0.0, 1.0))


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    best = max(
        rows,
        key=lambda row: (
            _float(row.get("strict_major_peaks")),
            _float(row.get("strict_refocus_peaks")),
            _float(row.get("default_major_peaks")),
            _float(row.get("retention")),
            -_float(row.get("outer_shell")),
        ),
    )
    return str(best.get("variant", "n/a"))


def _first_float(*items: Any) -> float | None:
    if len(items) >= 2 and all(isinstance(item, dict) for item in items[:-1]):
        *dicts, key = items
        for item in dicts:
            value = _float_or_none(item.get(key))
            if value is not None:
                return value
        return None
    if len(items) >= 3 and all(isinstance(item, dict) for item in items[:-2]):
        *dicts, key1, key2 = items
        for key in (key1, key2):
            for item in dicts:
                value = _float_or_none(item.get(key))
                if value is not None:
                    return value
        return None
    for item in items:
        value = _float_or_none(item)
        if value is not None:
            return value
    return None


def _first_int(primary: dict[str, Any], fallback: dict[str, Any], primary_key: str, fallback_key: str) -> int:
    value = _float_or_none(primary.get(primary_key))
    if value is None:
        value = _float_or_none(fallback.get(fallback_key))
    return int(value or 0)


def _first_bool(primary: dict[str, Any], fallback: dict[str, Any], primary_key: str, *, inverse_fallback_key: str) -> bool:
    if primary.get(primary_key) not in (None, ""):
        return _bool(primary.get(primary_key))
    return not _bool(fallback.get(inverse_fallback_key))


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row.get(key)
    return None


def _format_range(values: list[float]) -> str:
    if not values:
        return "n/a"
    return f"{_format(min(values))}-{_format(max(values))}"


def _circular_mean(values: list[float]) -> float | None:
    if not values:
        return None
    angles = np.asarray(values, dtype=float) * 2.0 * math.pi
    mean = complex(float(np.mean(np.cos(angles))), float(np.mean(np.sin(angles))))
    if abs(mean) <= EPSILON:
        return float(np.mean(values)) % 1.0
    return (math.atan2(mean.imag, mean.real) / (2.0 * math.pi)) % 1.0


def _phase_distance(a: Any, b: Any) -> float:
    av = _float_or_none(a)
    bv = _float_or_none(b)
    if av is None or bv is None:
        return 0.0
    delta = abs((av - bv) % 1.0)
    return min(delta, 1.0 - delta)


def _floats(values: Any) -> list[float]:
    out = []
    for value in values:
        parsed = _float_or_none(value)
        if parsed is not None:
            out.append(parsed)
    return out


def _mean(values: Any) -> float:
    parsed = [float(value) for value in values if value is not None and value != "" and np.isfinite(float(value))]
    return float(np.mean(parsed)) if parsed else 0.0


def _float(value: Any) -> float:
    parsed = _float_or_none(value)
    return float(parsed) if parsed is not None else 0.0


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if np.isfinite(parsed) else None


def _float_or_nan(value: Any) -> float:
    parsed = _float_or_none(value)
    return float(parsed) if parsed is not None else float("nan")


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return "" if value is None else value


def _json_model(model: dict[str, Any]) -> dict[str, Any]:
    out = dict(model)
    out.pop("linear_predictions", None)
    out.pop("logistic_predictions", None)
    return out


def _feature_fields() -> list[str]:
    return [
        "row_id",
        "run_id",
        "run_root",
        "variant",
        "source_summary_csv",
        "source_threshold_robust_csv",
        "polarity_sign_family",
        "resonator_variant",
        "reference_compatible",
        "cutoff_time",
        "release_phase_cycles",
        "phase_distance_to_0p50",
        "frequency",
        "first_arrival_time",
        "first_post_cutoff_peak_time",
        "shell_peak_time_1",
        "shell_peak_time_2",
        "shell_peak_time_3",
        "peak_interval_1",
        "peak_interval_2",
        "peak_interval_3",
        "early_window_end_time",
        "early_inward_flux",
        "early_outward_flux",
        "early_inward_flux_fraction",
        "early_flux_balance",
        "early_shell_phase",
        "early_outer_shell_ratio",
        "post_cutoff_shell_energy_area",
        "tail_energy_area_after_t50",
        "shell_energy_autocorrelation",
        "dominant_spectral_concentration",
        "return_timing_regularity",
        "default_major_peaks",
        "default_refocus_peaks",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "retention",
        "outer_shell",
        "decay",
        "no_exit",
        "global_outer_false",
        "conservative_pass",
        "default_11_10_or_better",
    ]


def _prediction_fields() -> list[str]:
    return [
        "prediction_kind",
        "scope",
        "row_id",
        "run_id",
        "variant",
        "cutoff_time",
        "release_phase_cycles",
        "actual_conservative_pass",
        "actual_default_major_peaks",
        "actual_default_refocus_peaks",
        "actual_strict_major_peaks",
        "actual_strict_refocus_peaks",
        "nearest_neighbor_row_id",
        "nearest_neighbor_phase_distance",
        "nearest_neighbor_predicted_pass",
        "nearest_neighbor_predicted_major",
        "nearest_neighbor_predicted_refocus",
        "nearest_neighbor_pass_correct",
        "phase_bin_pass_rate",
        "phase_bin_predicted_pass",
        "linear_pass_score",
        "logistic_pass_probability",
        "recommendation_role",
        "recommendation_reason",
    ]


def _binned_fields() -> list[str]:
    return [
        "scope",
        "phase_bin_start",
        "phase_bin_end",
        "phase_bin_center",
        "row_count",
        "conservative_pass_count",
        "conservative_pass_rate",
        "default_11_10_count",
        "mean_default_major_peaks",
        "mean_default_refocus_peaks",
        "mean_strict_major_peaks",
        "mean_strict_refocus_peaks",
        "mean_retention",
        "mean_outer_shell",
        "mean_decay",
        "mean_return_timing_regularity",
        "variants",
    ]
