"""Numerical validation for the 3D release-phase rule."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import math

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig, _calibrate_amplitude
from .prototype_3d_cutoff_phase_map import _add_control_fields, _variant, threshold_robust_refocusing_scores
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _threshold_like_options
from .prototype_3d_packet_lifecycle import _run_lifecycle_variant
from .prototype_3d_refocusing_engineering import _format, _lifecycle_options
from .prototype_3d_release_phase_blind_confirmation import ReleasePhaseBlindConfirmationOptions
from .prototype_3d_source_sponge import _effective_source_area, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


DEFAULT_VALIDATION_CUTOFFS = (17.932885, 17.937885, 17.9225, 17.915)
DEFAULT_VALIDATION_ROLES = (
    "predicted_strong",
    "predicted_strong",
    "predicted_low_edge_control",
    "predicted_weak_negative_control",
)


@dataclass(frozen=True)
class ReleasePhaseNumericalValidationOptions(ReleasePhaseBlindConfirmationOptions):
    """Options for baseline/half-dt validation of the blind-confirmed release-phase rule."""

    cutoffs: tuple[float, ...] = DEFAULT_VALIDATION_CUTOFFS
    prediction_roles: tuple[str, ...] = DEFAULT_VALIDATION_ROLES
    include_quarter_dt: bool = False
    strong_score_margin: float = 25.0


def run_3d_release_phase_numerical_validation(
    base_config: SimulationConfig,
    *,
    options: ReleasePhaseNumericalValidationOptions | None = None,
) -> dict[str, Any]:
    """Run baseline and smaller-dt checks for the release-phase predictor."""

    options = options or ReleasePhaseNumericalValidationOptions()
    control_id = datetime.now().strftime("release_phase_numerical_validation_3d_%Y%m%d_%H%M%S")
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
    for config in variants:
        config.drive_amplitude = reference_drive_amplitude
        target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
        _calibrate_amplitude(config, target_work)
        config.steps = max(config.steps, int(round(options.physical_duration / max(config.dt, EPSILON))))
        result = _run_lifecycle_variant(config, root, lifecycle_options)
        summary = result["summary"]
        _add_control_fields(summary, config, options, target_work_per_area)
        _add_validation_fields(summary, config)
        rows.append(summary)
        timeseries_rows.extend(result["timeseries"])

    robust_rows = threshold_robust_refocusing_scores(rows, timeseries_rows, options)
    summary_rows = _summary_rows(rows, robust_rows, options)
    comparison_rows = _comparison_rows(summary_rows)
    classification = classify_release_phase_numerical_validation(summary_rows, comparison_rows, options)
    for row in summary_rows:
        row["release_phase_numerical_validation_classification"] = classification["label"]
    for row in comparison_rows:
        row["release_phase_numerical_validation_classification"] = classification["label"]

    summary_csv = root / "release_phase_numerical_validation_summary.csv"
    comparison_csv = root / "release_phase_numerical_validation_comparison.csv"
    report_path = root / "release_phase_numerical_validation_report.md"
    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_report(report_path, control_id, summary_rows, comparison_rows, classification, options)
    save_json(
        root / "release_phase_numerical_validation_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": rows,
            "summary_rows": summary_rows,
            "comparison_rows": comparison_rows,
            "summary_csv": str(summary_csv),
            "comparison_csv": str(comparison_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": rows,
        "summary_rows": summary_rows,
        "comparison_rows": comparison_rows,
        "summary_csv": str(summary_csv),
        "comparison_csv": str(comparison_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_release_phase_numerical_validation(
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]] | None = None,
    options: ReleasePhaseNumericalValidationOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the half-dt run preserves the release-phase ordering."""

    options = options or ReleasePhaseNumericalValidationOptions()
    half_rows = [row for row in rows if row.get("dt_variant") == "half_dt"]
    strong_rows = [row for row in half_rows if row.get("prediction_role") == "predicted_strong"]
    low_rows = [row for row in half_rows if row.get("prediction_role") != "predicted_strong"]
    strong_clean = bool(strong_rows) and all(_strict_clean_pass(row, options) for row in strong_rows)
    low_best = max(low_rows, key=_score_key, default=None)
    strong_min = min(strong_rows, key=_score_key, default=None)
    strong_best = max(strong_rows, key=_score_key, default=None)
    low_as_well_or_better = bool(
        low_best
        and strong_best
        and (_strict_count_key(low_best) >= _strict_count_key(strong_best) or _score_key(low_best) >= _score_key(strong_best))
    )
    baseline_rows = [row for row in rows if row.get("dt_variant") == "baseline_dt"]
    baseline_by_cutoff = {_cutoff_key(row): row for row in baseline_rows}
    count_changes = [
        row
        for row in half_rows
        if _count_pair(row) != _count_pair(baseline_by_cutoff.get(_cutoff_key(row), {}))
        or _default_pair(row) != _default_pair(baseline_by_cutoff.get(_cutoff_key(row), {}))
    ]
    strong_degraded = any(
        _strict_count_key(row) < _strict_count_key(baseline_by_cutoff.get(_cutoff_key(row), {}))
        for row in strong_rows
    )
    threshold_free_supports = _threshold_free_order_supports(strong_rows, low_rows, options)
    checks = {
        "half_dt_row_count": len(half_rows),
        "half_dt_strong_row_count": len(strong_rows),
        "half_dt_low_control_count": len(low_rows),
        "half_dt_strong_rows_clean": strong_clean,
        "half_dt_low_as_well_or_better": low_as_well_or_better,
        "half_dt_strong_degraded_vs_baseline": strong_degraded,
        "count_changed_vs_baseline_count": len(count_changes),
        "threshold_free_order_supports_strong_rows": threshold_free_supports,
        "half_dt_strong_min_score": _score_key(strong_min),
        "half_dt_strong_best_score": _score_key(strong_best),
        "half_dt_low_best_score": _score_key(low_best),
    }
    if low_as_well_or_better:
        return {
            "label": "release_phase_failed",
            "reason": "A low-side control performed as well as or better than the strong rows under tighter dt.",
            "checks": checks,
        }
    if strong_clean and not strong_degraded:
        return {
            "label": "release_phase_numerically_confirmed",
            "reason": "The near-half-cycle strong rows preserved strict clean refocusing and stayed ahead of low-side controls at half dt.",
            "checks": checks,
        }
    if count_changes and threshold_free_supports:
        return {
            "label": "release_phase_inconclusive",
            "reason": "Event counts changed under half dt, but threshold-free metrics still support the same release-phase ordering.",
            "checks": checks,
        }
    if strong_degraded or not strong_clean:
        return {
            "label": "release_phase_dt_sensitive",
            "reason": "The near-half-cycle strong rows degraded under half dt or failed strict clean refocusing.",
            "checks": checks,
        }
    return {
        "label": "release_phase_inconclusive",
        "reason": "The half-dt rows did not cleanly fit the numerical-confirmation or failure criteria.",
        "checks": checks,
    }


def _variant_plan(
    base: SimulationConfig,
    options: ReleasePhaseNumericalValidationOptions,
) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    center = options.cutoff_center if options.cutoff_center is not None else float(base.driver.drive_cutoff_time) + options.cutoff_delta
    dt_variants = [("baseline_dt", 1.0), ("half_dt", 0.5)]
    if options.include_quarter_dt:
        dt_variants.append(("quarter_dt", 0.25))
    variants = []
    for dt_variant, dt_scale in dt_variants:
        for index, cutoff in enumerate(options.cutoffs):
            role = options.prediction_roles[index] if index < len(options.prediction_roles) else f"unlabeled_prediction_{index + 1}"
            config = _variant(
                _variant_name(dt_variant, role, cutoff),
                base,
                options,
                source_width,
                cutoff=max(1.0, float(cutoff)),
                frequency=options.fixed_drive_frequency,
                phase_offset=0.0,
                cubic_sign=-1.0,
                family="sign_flip",
                axis="release_phase_dt_validation",
                cutoff_offset=float(cutoff) - center,
            )
            config.dt = float(base.dt) * dt_scale
            config.steps = max(1, int(round(options.physical_duration / max(config.dt, EPSILON))))
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
            setattr(config, "_dt_variant", dt_variant)
            setattr(config, "_dt_scale", dt_scale)
            variants.append(config)
    return variants


def _add_validation_fields(row: dict[str, Any], config: Prototype3DConfig) -> None:
    row["prediction_role"] = getattr(config, "_prediction_role", "unlabeled_prediction")
    row["dt_variant"] = getattr(config, "_dt_variant", "baseline_dt")
    row["dt_scale"] = getattr(config, "_dt_scale", 1.0)
    row["no_active_second_pulse"] = config.second_pulse_center_time is None and config.second_pulse_duration <= EPSILON
    row["no_resonator_layer"] = not config.resonator_enabled


def _summary_rows(
    rows: list[dict[str, Any]],
    robust_rows: list[dict[str, Any]],
    options: ReleasePhaseNumericalValidationOptions,
) -> list[dict[str, Any]]:
    robust_by_variant = {str(row.get("variant")): row for row in robust_rows}
    out = []
    for row in rows:
        robust = robust_by_variant.get(str(row.get("variant")), {})
        combined = {
            "variant": row.get("variant"),
            "prediction_role": row.get("prediction_role"),
            "dt_variant": row.get("dt_variant"),
            "dt_scale": row.get("dt_scale"),
            "dt": row.get("dt"),
            "drive_cutoff_time": row.get("drive_cutoff_time"),
            "cutoff_phase_cycles": row.get("cutoff_phase_cycles"),
            "cutoff_phase_radians": row.get("cutoff_phase_radians"),
            "drive_frequency": row.get("drive_frequency"),
            "grid_size": row.get("grid_size"),
            "physical_duration": row.get("physical_duration"),
            "work_per_source_area": row.get("work_per_source_area"),
            "target_reference_work_per_source_area": row.get("target_reference_work_per_source_area"),
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
            "post_cutoff_shell_area": robust.get("threshold_free_shell_energy_area_after_cutoff", ""),
            "tail_area_after_t50": robust.get("threshold_free_tail_energy_area_after_t50", ""),
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
            "no_active_second_pulse": row.get("no_active_second_pulse"),
            "no_resonator_layer": row.get("no_resonator_layer"),
        }
        combined["strict_clean_pass"] = _strict_clean_pass(combined, options)
        out.append(combined)
    return out


def _comparison_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline_by_cutoff = {
        _cutoff_key(row): row
        for row in rows
        if row.get("dt_variant") == "baseline_dt"
    }
    out = []
    for row in rows:
        if row.get("dt_variant") == "baseline_dt":
            continue
        baseline = baseline_by_cutoff.get(_cutoff_key(row), {})
        out.append(
            {
                "variant": row.get("variant"),
                "prediction_role": row.get("prediction_role"),
                "drive_cutoff_time": row.get("drive_cutoff_time"),
                "cutoff_phase_cycles": row.get("cutoff_phase_cycles"),
                "dt_variant": row.get("dt_variant"),
                "dt": row.get("dt"),
                "baseline_dt": baseline.get("dt", ""),
                "baseline_default_count": _count_label(baseline, default=True),
                "dt_default_count": _count_label(row, default=True),
                "baseline_strict_count": _count_label(baseline, default=False),
                "dt_strict_count": _count_label(row, default=False),
                "default_major_delta": _int(row.get("default_major_peaks_at_0p30")) - _int(baseline.get("default_major_peaks_at_0p30")),
                "default_refocus_delta": _int(row.get("default_refocus_peaks_at_0p30")) - _int(baseline.get("default_refocus_peaks_at_0p30")),
                "strict_major_delta": _int(row.get("conservative_major_peaks")) - _int(baseline.get("conservative_major_peaks")),
                "strict_refocus_delta": _int(row.get("conservative_refocus_peaks")) - _int(baseline.get("conservative_refocus_peaks")),
                "retention_delta": _float(row.get("retention")) - _float(baseline.get("retention")),
                "outer_shell_delta": _float(row.get("outer_shell")) - _float(baseline.get("outer_shell")),
                "decay_delta": _float(row.get("decay")) - _float(baseline.get("decay")),
                "post_cutoff_shell_area_delta": _float(row.get("post_cutoff_shell_area")) - _float(baseline.get("post_cutoff_shell_area")),
                "tail_area_after_t50_delta": _float(row.get("tail_area_after_t50")) - _float(baseline.get("tail_area_after_t50")),
                "timing_regularity_delta": _float(row.get("return_timing_regularity")) - _float(baseline.get("return_timing_regularity")),
                "baseline_strict_clean_pass": baseline.get("strict_clean_pass", ""),
                "dt_strict_clean_pass": row.get("strict_clean_pass"),
                "conservative_score_delta": _float(row.get("conservative_score")) - _float(baseline.get("conservative_score")),
            }
        )
    return out


def _threshold_free_order_supports(
    strong_rows: list[dict[str, Any]],
    low_rows: list[dict[str, Any]],
    options: ReleasePhaseNumericalValidationOptions,
) -> bool:
    if not strong_rows or not low_rows:
        return False
    strong_min = min(_float(row.get("return_timing_regularity")) for row in strong_rows)
    low_max = max(_float(row.get("return_timing_regularity")) for row in low_rows)
    score_margin = min(_score_key(row) for row in strong_rows) - max(_score_key(row) for row in low_rows)
    return strong_min >= low_max - 0.05 and score_margin > options.strong_score_margin


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ReleasePhaseNumericalValidationOptions,
) -> None:
    lines = [
        f"# 3D Release-Phase Numerical Validation: {control_id}",
        "",
        "## Purpose",
        "",
        "Numerical validation of the blind-confirmed release-phase rule using only baseline and smaller-dt variants for the preselected cutoffs.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Quarter dt included: `{options.include_quarter_dt}`",
        "",
        "## Summary",
        "",
        "| dt | Role | Cutoff | Phase | Default | Strict 0.35 | Strict 0.40 | Clean | Ret | Outer/Shell | Decay |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dt_variant')} | "
            f"{row.get('prediction_role')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{row.get('default_major_peaks_at_0p30')}/{row.get('default_refocus_peaks_at_0p30')} | "
            f"{row.get('strict_major_peaks_at_0p35')}/{row.get('strict_refocus_peaks_at_0p35')} | "
            f"{row.get('strict_major_peaks_at_0p40')}/{row.get('strict_refocus_peaks_at_0p40')} | "
            f"{row.get('strict_clean_pass')} | "
            f"{_format(row.get('retention'))} | "
            f"{_format(row.get('outer_shell'))} | "
            f"{_format(row.get('decay'))} |"
        )
    lines.extend(
        [
            "",
            "## dt Comparison",
            "",
            "| dt | Role | Cutoff | Baseline Default | dt Default | Baseline Strict | dt Strict | Score Delta | Ret Delta | Area Delta |",
            "| --- | --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            "| "
            f"{row.get('dt_variant')} | "
            f"{row.get('prediction_role')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{row.get('baseline_default_count')} | "
            f"{row.get('dt_default_count')} | "
            f"{row.get('baseline_strict_count')} | "
            f"{row.get('dt_strict_count')} | "
            f"{_format(row.get('conservative_score_delta'))} | "
            f"{_format(row.get('retention_delta'))} | "
            f"{_format(row.get('post_cutoff_shell_area_delta'))} |"
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
            "- `release_phase_numerical_validation_report.md`",
            "- `release_phase_numerical_validation_summary.csv`",
            "- `release_phase_numerical_validation_comparison.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "release_phase_numerically_confirmed":
        return "The half-dt rows preserve the release-phase ordering and strict clean refocusing for the near-half-cycle strong cutoffs."
    if label == "release_phase_dt_sensitive":
        return "The half-dt rows changed the strong-cutoff behavior enough that the release-phase rule should not be treated as numerically settled."
    if label == "release_phase_failed":
        return "The low-side controls matched or beat the strong rows under tighter dt, undermining the release-phase rule."
    return "The event counts changed under tighter dt, but threshold-free metrics still support the same ordering; inspect the CSV before adding mechanisms."


def _strict_clean_pass(row: dict[str, Any], options: ReleasePhaseNumericalValidationOptions) -> bool:
    return (
        _int(row.get("conservative_major_peaks")) >= options.strong_strict_major_target
        and _int(row.get("conservative_refocus_peaks")) >= options.strong_strict_refocus_target
        and _float(row.get("outer_shell")) < options.strict_outer_shell_target
        and _bool(row.get("no_exit"))
        and _bool(row.get("global_outer_false"))
    )


def _strict_count_key(row: dict[str, Any]) -> tuple[int, int]:
    return (_int(row.get("conservative_major_peaks")), _int(row.get("conservative_refocus_peaks")))


def _count_pair(row: dict[str, Any]) -> tuple[int, int]:
    return (_int(row.get("conservative_major_peaks")), _int(row.get("conservative_refocus_peaks")))


def _default_pair(row: dict[str, Any]) -> tuple[int, int]:
    return (_int(row.get("default_major_peaks_at_0p30")), _int(row.get("default_refocus_peaks_at_0p30")))


def _count_label(row: dict[str, Any], *, default: bool) -> str:
    if default:
        return f"{_int(row.get('default_major_peaks_at_0p30'))}/{_int(row.get('default_refocus_peaks_at_0p30'))}"
    return f"{_int(row.get('conservative_major_peaks'))}/{_int(row.get('conservative_refocus_peaks'))}"


def _score_key(row: dict[str, Any] | None) -> float:
    return _float((row or {}).get("conservative_score"))


def _cutoff_key(row: dict[str, Any]) -> float:
    return round(_float(row.get("drive_cutoff_time")), 6)


def _variant_name(dt_variant: str, role: str, cutoff: float) -> str:
    safe = f"{cutoff:.6f}".rstrip("0").rstrip(".").replace(".", "p")
    return f"{dt_variant}_{role}_cutoff_{safe}"


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
        "release_phase_numerical_validation_classification",
        "prediction_role",
        "dt_variant",
        "dt_scale",
        "dt",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "cutoff_phase_radians",
        "drive_frequency",
        "grid_size",
        "physical_duration",
        "work_per_source_area",
        "target_reference_work_per_source_area",
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
        "post_cutoff_shell_area",
        "tail_area_after_t50",
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
        "strict_clean_pass",
        "no_active_second_pulse",
        "no_resonator_layer",
    ]


def _comparison_fields() -> list[str]:
    return [
        "variant",
        "release_phase_numerical_validation_classification",
        "prediction_role",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "dt_variant",
        "dt",
        "baseline_dt",
        "baseline_default_count",
        "dt_default_count",
        "baseline_strict_count",
        "dt_strict_count",
        "default_major_delta",
        "default_refocus_delta",
        "strict_major_delta",
        "strict_refocus_delta",
        "retention_delta",
        "outer_shell_delta",
        "decay_delta",
        "post_cutoff_shell_area_delta",
        "tail_area_after_t50_delta",
        "timing_regularity_delta",
        "baseline_strict_clean_pass",
        "dt_strict_clean_pass",
        "conservative_score_delta",
    ]
