"""Blind confirmation of the 3D release-phase return-map predictor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import math

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig, _calibrate_amplitude
from .prototype_3d_cutoff_phase_map import (
    CutoffPhaseMap3DOptions,
    _add_control_fields,
    _variant,
    threshold_robust_refocusing_scores,
)
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _threshold_like_options
from .prototype_3d_packet_lifecycle import _run_lifecycle_variant
from .prototype_3d_refocusing_engineering import _format, _lifecycle_options
from .prototype_3d_source_sponge import _effective_source_area, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


DEFAULT_CUTOFFS = (17.932885, 17.937885, 17.9225, 17.965, 17.915)
DEFAULT_ROLES = (
    "predicted_strong",
    "predicted_strong",
    "predicted_boundary_edge",
    "predicted_boundary_edge",
    "predicted_weak_negative_control",
)


@dataclass(frozen=True)
class ReleasePhaseBlindConfirmationOptions(CutoffPhaseMap3DOptions):
    """Options for the fixed five-row blind release-phase confirmation."""

    cutoffs: tuple[float, ...] = DEFAULT_CUTOFFS
    prediction_roles: tuple[str, ...] = DEFAULT_ROLES
    fixed_drive_frequency: float = 0.92
    strong_strict_major_target: int = 9
    strong_strict_refocus_target: int = 8
    strong_default_major_target: int = 11
    strong_default_refocus_target: int = 10


def run_3d_release_phase_blind_confirmation(
    base_config: SimulationConfig,
    *,
    options: ReleasePhaseBlindConfirmationOptions | None = None,
) -> dict[str, Any]:
    """Run the five-cutoff blind confirmation from the return-map predictor."""

    options = options or ReleasePhaseBlindConfirmationOptions()
    control_id = datetime.now().strftime("release_phase_blind_confirmation_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    lifecycle_options = _lifecycle_options(options)
    threshold_options = _threshold_like_options(lifecycle_options)
    target_work_per_area = options.target_work_per_source_area or _calibration_work_per_area(
        base_config,
        threshold_options,
        source_width,
    )
    reference_drive_amplitude = _calibrated_reference_amplitude(
        base_config,
        threshold_options,
        source_width,
        target_work_per_area,
    )

    rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for config in variants:
        config.drive_amplitude = reference_drive_amplitude
        target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
        _calibrate_amplitude(config, target_work)
        config.steps = max(config.steps, int(round(options.physical_duration / max(config.dt, EPSILON))))
        result = _run_lifecycle_variant(config, root, lifecycle_options)
        summary = result["summary"]
        _add_control_fields(summary, config, options, target_work_per_area)
        _add_blind_fields(summary, config)
        rows.append(summary)
        timeseries_rows.extend(result["timeseries"])
        event_rows.extend(result["events"])

    robust_rows = threshold_robust_refocusing_scores(rows, timeseries_rows, options)
    summary_rows = _summary_rows(rows, robust_rows, options)
    prediction_check_rows = _prediction_check_rows(summary_rows, options)
    classification = classify_release_phase_blind_confirmation(summary_rows, options)
    for row in summary_rows:
        row["release_phase_blind_confirmation_classification"] = classification["label"]
    for row in prediction_check_rows:
        row["release_phase_blind_confirmation_classification"] = classification["label"]

    summary_csv = root / "release_phase_blind_confirmation_summary.csv"
    prediction_check_csv = root / "release_phase_blind_confirmation_prediction_check.csv"
    report_path = root / "release_phase_blind_confirmation_report.md"
    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(prediction_check_csv, prediction_check_rows, _prediction_check_fields())
    _write_report(report_path, control_id, summary_rows, prediction_check_rows, classification, options)
    save_json(
        root / "release_phase_blind_confirmation_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": rows,
            "summary_rows": summary_rows,
            "prediction_check_rows": prediction_check_rows,
            "summary_csv": str(summary_csv),
            "prediction_check_csv": str(prediction_check_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": rows,
        "summary_rows": summary_rows,
        "prediction_check_rows": prediction_check_rows,
        "summary_csv": str(summary_csv),
        "prediction_check_csv": str(prediction_check_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_release_phase_blind_confirmation(
    rows: list[dict[str, Any]],
    options: ReleasePhaseBlindConfirmationOptions | None = None,
) -> dict[str, Any]:
    """Classify the blind confirmation against the return-map predictions."""

    options = options or ReleasePhaseBlindConfirmationOptions()
    strong_rows = [row for row in rows if row.get("prediction_role") == "predicted_strong"]
    weak_rows = [row for row in rows if row.get("prediction_role") == "predicted_weak_negative_control"]
    edge_rows = [row for row in rows if row.get("prediction_role") == "predicted_boundary_edge"]
    strong_clean = bool(strong_rows) and all(_strict_clean_pass(row, options) for row in strong_rows)
    strong_default = bool(strong_rows) and all(_default_ideal_pass(row, options) for row in strong_rows)
    weak_best = max(weak_rows, key=_score_key, default=None)
    strong_min = min(strong_rows, key=_score_key, default=None)
    strong_max = max(strong_rows, key=_score_key, default=None)
    weak_strict_similar = bool(weak_best and strong_min and _strict_count_key(weak_best) >= _strict_count_key(strong_min))
    weak_as_well_or_better = bool(weak_best and strong_max and _score_key(weak_best) >= _score_key(strong_max))
    default_separates = bool(
        strong_rows
        and weak_best
        and min(_default_count_key(row) for row in strong_rows) > _default_count_key(weak_best)
    )
    threshold_free_similar = bool(weak_best and strong_min and _threshold_free_similar(strong_min, weak_best))
    detector_only = strong_clean and weak_strict_similar and default_separates and threshold_free_similar
    checks = {
        "strong_row_count": len(strong_rows),
        "edge_row_count": len(edge_rows),
        "weak_row_count": len(weak_rows),
        "strong_rows_preserve_strict_9_8": strong_clean,
        "strong_rows_default_11_10": strong_default,
        "weak_strict_similar_to_strong_floor": weak_strict_similar,
        "weak_as_well_or_better_than_strong_best": weak_as_well_or_better,
        "default_separates_strong_from_weak": default_separates,
        "threshold_free_strong_weak_similar": threshold_free_similar,
        "strong_min_conservative_score": _score_key(strong_min) if strong_min else 0.0,
        "strong_max_conservative_score": _score_key(strong_max) if strong_max else 0.0,
        "weak_best_conservative_score": _score_key(weak_best) if weak_best else 0.0,
    }
    if not strong_clean:
        return {
            "label": "release_phase_rule_failed",
            "reason": "At least one predicted strong cutoff failed to preserve the strict clean 9/8 family.",
            "checks": checks,
        }
    if weak_as_well_or_better:
        return {
            "label": "release_phase_rule_failed",
            "reason": "The predicted weak control performed as well as or better than the predicted strong rows.",
            "checks": checks,
        }
    if detector_only:
        return {
            "label": "release_phase_detector_only",
            "reason": "The main separation is visible at the default event threshold but disappears under strict and threshold-free metrics.",
            "checks": checks,
        }
    if weak_strict_similar:
        return {
            "label": "release_phase_rule_partially_confirmed",
            "reason": "Predicted strong rows preserved strict 9/8, but the weak control also reached the strong strict-count floor.",
            "checks": checks,
        }
    return {
        "label": "release_phase_blind_confirmed",
        "reason": "Predicted strong rows preserved strict clean 9/8 and outperformed the predicted weak control.",
        "checks": checks,
    }


def _variant_plan(
    base: SimulationConfig,
    options: ReleasePhaseBlindConfirmationOptions,
) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    center = options.cutoff_center if options.cutoff_center is not None else float(base.driver.drive_cutoff_time) + options.cutoff_delta
    variants = []
    for index, cutoff in enumerate(options.cutoffs):
        role = options.prediction_roles[index] if index < len(options.prediction_roles) else f"unlabeled_prediction_{index + 1}"
        config = _variant(
            _variant_name(role, cutoff),
            base,
            options,
            source_width,
            cutoff=max(1.0, float(cutoff)),
            frequency=options.fixed_drive_frequency,
            phase_offset=0.0,
            cubic_sign=-1.0,
            family="sign_flip",
            axis="blind_confirmation",
            cutoff_offset=float(cutoff) - center,
        )
        config.second_pulse_center_time = None
        config.second_pulse_duration = 0.0
        config.second_pulse_amplitude_scale = 0.0
        config.second_pulse_phase_offset = 0.0
        config.resonator_enabled = False
        config.resonator_geometry = "none"
        config.resonator_k1 = 0.0
        config.resonator_k3 = 0.0
        config.resonator_damping = 0.0
        config.resonator_coupling = 0.0
        setattr(config, "_prediction_role", role)
        variants.append(config)
    return variants


def _add_blind_fields(row: dict[str, Any], config: Prototype3DConfig) -> None:
    role = getattr(config, "_prediction_role", "unlabeled_prediction")
    row["prediction_role"] = role
    row["predicted_strict_major_peaks"] = 8 if role == "predicted_weak_negative_control" else 9
    row["predicted_strict_refocus_peaks"] = 7 if role == "predicted_weak_negative_control" else 8
    row["predicted_default_major_peaks"] = 11 if role == "predicted_strong" else ""
    row["predicted_default_refocus_peaks"] = 10 if role == "predicted_strong" else ""
    row["no_active_second_pulse"] = config.second_pulse_center_time is None and config.second_pulse_duration <= EPSILON
    row["no_resonator_layer"] = not config.resonator_enabled


def _summary_rows(
    rows: list[dict[str, Any]],
    robust_rows: list[dict[str, Any]],
    options: ReleasePhaseBlindConfirmationOptions,
) -> list[dict[str, Any]]:
    robust_by_variant = {str(row.get("variant")): row for row in robust_rows}
    out = []
    for row in rows:
        robust = robust_by_variant.get(str(row.get("variant")), {})
        combined = {
            "variant": row.get("variant"),
            "prediction_role": row.get("prediction_role"),
            "drive_cutoff_time": row.get("drive_cutoff_time"),
            "cutoff_phase_cycles": row.get("cutoff_phase_cycles"),
            "cutoff_phase_radians": row.get("cutoff_phase_radians"),
            "release_phase_label": row.get("cutoff_phase_label"),
            "drive_frequency": row.get("drive_frequency"),
            "grid_size": row.get("grid_size"),
            "dx": row.get("dx"),
            "dt": row.get("dt"),
            "physical_duration": row.get("physical_duration"),
            "work_per_source_area": row.get("work_per_source_area"),
            "target_reference_work_per_source_area": row.get("target_reference_work_per_source_area"),
            "shell_window_radius": row.get("shell_window_radius"),
            "shell_window_width": row.get("shell_window_width"),
            "default_major_peaks_at_0p30": robust.get("major_peaks_at_0p30", row.get("major_shell_peak_count")),
            "default_refocus_peaks_at_0p30": robust.get("refocus_peaks_at_0p30", row.get("refocus_peak_count")),
            "strict_major_peaks_at_0p35": robust.get("major_peaks_at_0p35", ""),
            "strict_refocus_peaks_at_0p35": robust.get("refocus_peaks_at_0p35", ""),
            "strict_major_peaks_at_0p40": robust.get("major_peaks_at_0p40", ""),
            "strict_refocus_peaks_at_0p40": robust.get("refocus_peaks_at_0p40", ""),
            "conservative_major_peaks": min(_int(robust.get("major_peaks_at_0p35")), _int(robust.get("major_peaks_at_0p40"))),
            "conservative_refocus_peaks": min(_int(robust.get("refocus_peaks_at_0p35")), _int(robust.get("refocus_peaks_at_0p40"))),
            "retention": robust.get("retention_median", row.get("tail_shell_retention")),
            "outer_shell": robust.get("outer_shell_median", row.get("tail_outer_to_shell_mean")),
            "decay": robust.get("decay_median", row.get("post_cutoff_shell_decay_rate")),
            "no_exit": robust.get("no_exit_across_all_thresholds", not bool(row.get("shell_exit_detected"))),
            "global_outer_false": robust.get("global_outer_false_across_all_thresholds", not bool(row.get("global_peak_in_outer_window"))),
            "global_peak_in_outer_window": row.get("global_peak_in_outer_window"),
            "threshold_free_shell_energy_area_after_cutoff": robust.get("threshold_free_shell_energy_area_after_cutoff", ""),
            "threshold_free_tail_energy_area_after_t50": robust.get("threshold_free_tail_energy_area_after_t50", ""),
            "shell_energy_autocorrelation": robust.get("shell_energy_autocorrelation", ""),
            "dominant_spectral_concentration": robust.get("dominant_spectral_concentration", ""),
            "return_timing_regularity": robust.get("return_timing_regularity", ""),
            "conservative_score": robust.get("conservative_score", ""),
            "default_threshold_score": robust.get("default_threshold_score", ""),
            "first_shell_arrival_time": row.get("first_shell_arrival_time"),
            "shell_peak_time": row.get("shell_peak_time"),
            "first_refocus_time": row.get("first_refocus_time"),
            "last_refocus_time": row.get("last_refocus_time"),
            "inward_flux_fraction": row.get("inward_flux_fraction"),
            "outward_flux_fraction": row.get("outward_flux_fraction"),
            "predicted_strict_major_peaks": row.get("predicted_strict_major_peaks"),
            "predicted_strict_refocus_peaks": row.get("predicted_strict_refocus_peaks"),
            "predicted_default_major_peaks": row.get("predicted_default_major_peaks"),
            "predicted_default_refocus_peaks": row.get("predicted_default_refocus_peaks"),
            "no_active_second_pulse": row.get("no_active_second_pulse"),
            "no_resonator_layer": row.get("no_resonator_layer"),
        }
        combined["strict_clean_pass"] = _strict_clean_pass(combined, options)
        combined["default_11_10"] = _default_ideal_pass(combined, options)
        out.append(combined)
    return out


def _prediction_check_rows(
    rows: list[dict[str, Any]],
    options: ReleasePhaseBlindConfirmationOptions,
) -> list[dict[str, Any]]:
    out = []
    strong_rows = [row for row in rows if row.get("prediction_role") == "predicted_strong"]
    weak_rows = [row for row in rows if row.get("prediction_role") == "predicted_weak_negative_control"]
    strong_min_score = min((_float(row.get("conservative_score")) for row in strong_rows), default=0.0)
    weak_best_score = max((_float(row.get("conservative_score")) for row in weak_rows), default=0.0)
    for row in rows:
        role = str(row.get("prediction_role"))
        strict_met = _strict_count_key(row) >= (
            _int(row.get("predicted_strict_major_peaks")),
            _int(row.get("predicted_strict_refocus_peaks")),
        )
        clean_met = _strict_clean_pass(row, options)
        default_met = _default_ideal_pass(row, options) if role == "predicted_strong" else ""
        if role == "predicted_weak_negative_control":
            relation = "below_strong_floor" if _float(row.get("conservative_score")) < strong_min_score else "similar_or_above_strong_floor"
        elif role == "predicted_strong":
            relation = "above_weak_control" if _float(row.get("conservative_score")) > weak_best_score else "not_above_weak_control"
        else:
            relation = "edge_case"
        out.append(
            {
                "variant": row.get("variant"),
                "prediction_role": role,
                "drive_cutoff_time": row.get("drive_cutoff_time"),
                "cutoff_phase_cycles": row.get("cutoff_phase_cycles"),
                "predicted_strict_major_peaks": row.get("predicted_strict_major_peaks"),
                "predicted_strict_refocus_peaks": row.get("predicted_strict_refocus_peaks"),
                "predicted_default_major_peaks": row.get("predicted_default_major_peaks"),
                "predicted_default_refocus_peaks": row.get("predicted_default_refocus_peaks"),
                "observed_default_major_peaks": row.get("default_major_peaks_at_0p30"),
                "observed_default_refocus_peaks": row.get("default_refocus_peaks_at_0p30"),
                "observed_conservative_major_peaks": row.get("conservative_major_peaks"),
                "observed_conservative_refocus_peaks": row.get("conservative_refocus_peaks"),
                "observed_strict_0p35": f"{row.get('strict_major_peaks_at_0p35')}/{row.get('strict_refocus_peaks_at_0p35')}",
                "observed_strict_0p40": f"{row.get('strict_major_peaks_at_0p40')}/{row.get('strict_refocus_peaks_at_0p40')}",
                "strict_prediction_met": strict_met,
                "strict_clean_pass": clean_met,
                "default_ideal_met": default_met,
                "strong_weak_relation": relation,
                "conservative_score": row.get("conservative_score"),
                "retention": row.get("retention"),
                "outer_shell": row.get("outer_shell"),
                "decay": row.get("decay"),
                "threshold_free_shell_energy_area_after_cutoff": row.get("threshold_free_shell_energy_area_after_cutoff"),
                "threshold_free_tail_energy_area_after_t50": row.get("threshold_free_tail_energy_area_after_t50"),
                "return_timing_regularity": row.get("return_timing_regularity"),
            }
        )
    return out


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ReleasePhaseBlindConfirmationOptions,
) -> None:
    lines = [
        f"# 3D Release-Phase Blind Confirmation: {control_id}",
        "",
        "## Purpose",
        "",
        "Blind confirmation of the read-only release-phase return-map predictor using only the five recommended cutoffs. No tuning was performed after seeing the result.",
        "",
        "## Fixed Setup",
        "",
        "- `41^3` neutral lattice",
        "- stronger sponge",
        "- inner-sponge-edge sign-flip cubic boundary source",
        "- frequency `0.92`",
        "- matched work per physical source area",
        "- radius-5 shell window",
        "- no active second pulses",
        "- no resonator layer",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Prediction Check",
        "",
        "| Role | Cutoff | Phase | Default | Strict 0.35 | Strict 0.40 | Clean | Relation |",
        "| --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in prediction_rows:
        lines.append(
            "| "
            f"{row.get('prediction_role')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{row.get('observed_default_major_peaks')}/{row.get('observed_default_refocus_peaks')} | "
            f"{row.get('observed_strict_0p35')} | "
            f"{row.get('observed_strict_0p40')} | "
            f"{row.get('strict_clean_pass')} | "
            f"{row.get('strong_weak_relation')} |"
        )
    lines.extend(
        [
            "",
            "## Threshold-Free Metrics",
            "",
            "| Role | Cutoff | Retention | Outer/Shell | Decay | Shell Area | Tail Area | Autocorr | Spectral | Timing Reg |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row.get('prediction_role')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('retention'))} | "
            f"{_format(row.get('outer_shell'))} | "
            f"{_format(row.get('decay'))} | "
            f"{_format(row.get('threshold_free_shell_energy_area_after_cutoff'))} | "
            f"{_format(row.get('threshold_free_tail_energy_area_after_t50'))} | "
            f"{_format(row.get('shell_energy_autocorrelation'))} | "
            f"{_format(row.get('dominant_spectral_concentration'))} | "
            f"{_format(row.get('return_timing_regularity'))} |"
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
            "- `release_phase_blind_confirmation_report.md`",
            "- `release_phase_blind_confirmation_summary.csv`",
            "- `release_phase_blind_confirmation_prediction_check.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "release_phase_blind_confirmed":
        return "The return-map phase rule survived the blind five-cutoff check: predicted strong rows preserved the strict clean 9/8 family and the weak control fell below the strong cluster."
    if label == "release_phase_rule_partially_confirmed":
        return "The predicted strong rows preserved strict 9/8, but the weak control was too similar for a clean separation claim."
    if label == "release_phase_detector_only":
        return "The five-cutoff distinction is mostly a default-threshold event-count distinction; strict and threshold-free metrics are not separating the groups enough."
    return "The blind confirmation did not support the release-phase rule under the strict clean 9/8 criteria."


def _strict_clean_pass(row: dict[str, Any], options: ReleasePhaseBlindConfirmationOptions) -> bool:
    return (
        _int(row.get("conservative_major_peaks")) >= options.strong_strict_major_target
        and _int(row.get("conservative_refocus_peaks")) >= options.strong_strict_refocus_target
        and _float(row.get("outer_shell")) < options.strict_outer_shell_target
        and _bool(row.get("no_exit"))
        and _bool(row.get("global_outer_false"))
    )


def _default_ideal_pass(row: dict[str, Any], options: ReleasePhaseBlindConfirmationOptions) -> bool:
    return (
        _int(row.get("default_major_peaks_at_0p30")) >= options.strong_default_major_target
        and _int(row.get("default_refocus_peaks_at_0p30")) >= options.strong_default_refocus_target
    )


def _threshold_free_similar(strong: dict[str, Any], weak: dict[str, Any]) -> bool:
    return (
        _within_fraction(_float(strong.get("threshold_free_shell_energy_area_after_cutoff")), _float(weak.get("threshold_free_shell_energy_area_after_cutoff")), 0.10)
        and _within_fraction(_float(strong.get("threshold_free_tail_energy_area_after_t50")), _float(weak.get("threshold_free_tail_energy_area_after_t50")), 0.10)
        and abs(_float(strong.get("return_timing_regularity")) - _float(weak.get("return_timing_regularity"))) <= 0.05
    )


def _within_fraction(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance * max(abs(a), EPSILON)


def _strict_count_key(row: dict[str, Any]) -> tuple[int, int]:
    return (_int(row.get("conservative_major_peaks")), _int(row.get("conservative_refocus_peaks")))


def _default_count_key(row: dict[str, Any]) -> tuple[int, int]:
    return (_int(row.get("default_major_peaks_at_0p30")), _int(row.get("default_refocus_peaks_at_0p30")))


def _score_key(row: dict[str, Any] | None) -> float:
    return _float((row or {}).get("conservative_score"))


def _variant_name(role: str, cutoff: float) -> str:
    safe = f"{cutoff:.6f}".rstrip("0").rstrip(".").replace(".", "p")
    return f"{role}_cutoff_{safe}"


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _summary_fields() -> list[str]:
    return [
        "variant",
        "release_phase_blind_confirmation_classification",
        "prediction_role",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "cutoff_phase_radians",
        "release_phase_label",
        "drive_frequency",
        "grid_size",
        "dx",
        "dt",
        "physical_duration",
        "work_per_source_area",
        "target_reference_work_per_source_area",
        "shell_window_radius",
        "shell_window_width",
        "default_major_peaks_at_0p30",
        "default_refocus_peaks_at_0p30",
        "strict_major_peaks_at_0p35",
        "strict_refocus_peaks_at_0p35",
        "strict_major_peaks_at_0p40",
        "strict_refocus_peaks_at_0p40",
        "conservative_major_peaks",
        "conservative_refocus_peaks",
        "retention",
        "outer_shell",
        "decay",
        "no_exit",
        "global_outer_false",
        "global_peak_in_outer_window",
        "threshold_free_shell_energy_area_after_cutoff",
        "threshold_free_tail_energy_area_after_t50",
        "shell_energy_autocorrelation",
        "dominant_spectral_concentration",
        "return_timing_regularity",
        "conservative_score",
        "default_threshold_score",
        "first_shell_arrival_time",
        "shell_peak_time",
        "first_refocus_time",
        "last_refocus_time",
        "inward_flux_fraction",
        "outward_flux_fraction",
        "predicted_strict_major_peaks",
        "predicted_strict_refocus_peaks",
        "predicted_default_major_peaks",
        "predicted_default_refocus_peaks",
        "strict_clean_pass",
        "default_11_10",
        "no_active_second_pulse",
        "no_resonator_layer",
    ]


def _prediction_check_fields() -> list[str]:
    return [
        "variant",
        "release_phase_blind_confirmation_classification",
        "prediction_role",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "predicted_strict_major_peaks",
        "predicted_strict_refocus_peaks",
        "predicted_default_major_peaks",
        "predicted_default_refocus_peaks",
        "observed_default_major_peaks",
        "observed_default_refocus_peaks",
        "observed_conservative_major_peaks",
        "observed_conservative_refocus_peaks",
        "observed_strict_0p35",
        "observed_strict_0p40",
        "strict_prediction_met",
        "strict_clean_pass",
        "default_ideal_met",
        "strong_weak_relation",
        "conservative_score",
        "retention",
        "outer_shell",
        "decay",
        "threshold_free_shell_energy_area_after_cutoff",
        "threshold_free_tail_energy_area_after_t50",
        "return_timing_regularity",
    ]
