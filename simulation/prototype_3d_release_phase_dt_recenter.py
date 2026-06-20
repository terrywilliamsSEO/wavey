"""Half-dt recentering map for the 3D release-phase rule."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig, _calibrate_amplitude
from .prototype_3d_cutoff_phase_map import _add_control_fields, _variant, threshold_robust_refocusing_scores
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _threshold_like_options
from .prototype_3d_packet_lifecycle import _run_lifecycle_variant
from .prototype_3d_refocusing_engineering import _format, _lifecycle_options
from .prototype_3d_release_phase_numerical_validation import (
    ReleasePhaseNumericalValidationOptions,
    _bool,
    _float,
    _int,
    _score_key,
    _strict_clean_pass,
    _strict_count_key,
    _summary_rows,
)
from .prototype_3d_source_sponge import _effective_source_area, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


DEFAULT_RECENTER_CUTOFFS = (
    17.930,
    17.9325,
    17.935,
    17.9375,
    17.940,
    17.9425,
    17.945,
    17.9475,
    17.950,
    17.9225,
    17.915,
)
DEFAULT_RECENTER_ROLES = (
    "recenter_candidate",
    "recenter_candidate",
    "recenter_candidate",
    "recenter_candidate",
    "recenter_candidate",
    "recenter_candidate",
    "recenter_candidate",
    "recenter_candidate",
    "recenter_candidate",
    "low_side_control",
    "weak_negative_control",
)


@dataclass(frozen=True)
class ReleasePhaseDtRecenterOptions(ReleasePhaseNumericalValidationOptions):
    """Options for the fixed half-dt release-phase recentering map."""

    cutoffs: tuple[float, ...] = DEFAULT_RECENTER_CUTOFFS
    prediction_roles: tuple[str, ...] = DEFAULT_RECENTER_ROLES
    dt_scale: float = 0.5
    neighboring_cutoff_gap: float = 0.003
    threshold_free_score_margin: float = 25.0


def run_3d_release_phase_dt_recenter(
    base_config: SimulationConfig,
    *,
    options: ReleasePhaseDtRecenterOptions | None = None,
) -> dict[str, Any]:
    """Run the fixed half-dt recentering map around the surviving release-phase row."""

    options = options or ReleasePhaseDtRecenterOptions()
    control_id = datetime.now().strftime("release_phase_dt_recenter_3d_%Y%m%d_%H%M%S")
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
        _add_recenter_fields(summary, config)
        rows.append(summary)
        timeseries_rows.extend(result["timeseries"])

    robust_rows = _annotated_robust_rows(
        threshold_robust_refocusing_scores(rows, timeseries_rows, options),
        rows,
    )
    summary_rows = _summary_rows(rows, robust_rows, options)
    classification = classify_release_phase_dt_recenter(summary_rows, options)
    for row in summary_rows:
        row["release_phase_dt_recenter_classification"] = classification["label"]
    for row in robust_rows:
        row["release_phase_dt_recenter_classification"] = classification["label"]

    summary_csv = root / "release_phase_dt_recenter_summary.csv"
    threshold_robust_csv = root / "release_phase_dt_recenter_threshold_robust_score.csv"
    report_path = root / "release_phase_dt_recenter_report.md"
    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(threshold_robust_csv, robust_rows, _threshold_robust_fields())
    _write_report(report_path, control_id, summary_rows, robust_rows, classification, options)
    save_json(
        root / "release_phase_dt_recenter_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": rows,
            "summary_rows": summary_rows,
            "threshold_robust_rows": robust_rows,
            "summary_csv": str(summary_csv),
            "threshold_robust_csv": str(threshold_robust_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": rows,
        "summary_rows": summary_rows,
        "threshold_robust_rows": robust_rows,
        "summary_csv": str(summary_csv),
        "threshold_robust_csv": str(threshold_robust_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_release_phase_dt_recenter(
    rows: list[dict[str, Any]],
    options: ReleasePhaseDtRecenterOptions | None = None,
) -> dict[str, Any]:
    """Classify whether half-dt strict refocusing recenters upward."""

    options = options or ReleasePhaseDtRecenterOptions()
    candidate_rows = [row for row in rows if row.get("prediction_role") == "recenter_candidate"]
    low_rows = [row for row in rows if row.get("prediction_role") != "recenter_candidate"]
    clean_rows = [row for row in candidate_rows if _strict_clean_pass(row, options)]
    candidate_best = max(candidate_rows, key=_score_key, default=None)
    low_best = max(low_rows, key=_score_key, default=None)
    low_as_well_or_better = bool(
        low_best
        and candidate_best
        and (_strict_count_key(low_best) >= _strict_count_key(candidate_best) or _score_key(low_best) >= _score_key(candidate_best))
    )
    max_cluster = _max_neighbor_cluster_size(clean_rows, options)
    threshold_free_supports = _threshold_free_order_supports(candidate_rows, low_rows, options)
    checks = {
        "candidate_row_count": len(candidate_rows),
        "low_control_count": len(low_rows),
        "strict_clean_candidate_count": len(clean_rows),
        "max_neighboring_strict_clean_cluster": max_cluster,
        "low_as_well_or_better": low_as_well_or_better,
        "threshold_free_order_supports_candidates": threshold_free_supports,
        "best_candidate": (candidate_best or {}).get("variant"),
        "best_candidate_cutoff": (candidate_best or {}).get("drive_cutoff_time"),
        "best_candidate_score": _score_key(candidate_best),
        "best_low_control": (low_best or {}).get("variant"),
        "best_low_score": _score_key(low_best),
    }
    if low_as_well_or_better:
        return {
            "label": "release_phase_half_dt_failed",
            "reason": "A low-side control performed as well as or better than the best half-dt recenter candidate.",
            "checks": checks,
        }
    if max_cluster >= 2:
        return {
            "label": "release_phase_half_dt_recentered",
            "reason": "Neighboring half-dt cutoffs preserve strict clean 9/8 and outperform the low-side controls.",
            "checks": checks,
        }
    if len(clean_rows) == 1:
        return {
            "label": "release_phase_half_dt_single_row",
            "reason": "Only one half-dt cutoff preserves strict clean 9/8.",
            "checks": checks,
        }
    if threshold_free_supports:
        return {
            "label": "release_phase_half_dt_inconclusive",
            "reason": "Strict event counts degraded, but threshold-free metrics still favor the recenter candidates over low-side controls.",
            "checks": checks,
        }
    return {
        "label": "release_phase_half_dt_failed",
        "reason": "The half-dt strong region disappeared under strict event counts.",
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: ReleasePhaseDtRecenterOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    center = options.cutoff_center if options.cutoff_center is not None else float(base.driver.drive_cutoff_time) + options.cutoff_delta
    variants = []
    for index, cutoff in enumerate(options.cutoffs):
        role = options.prediction_roles[index] if index < len(options.prediction_roles) else f"unlabeled_recenter_{index + 1}"
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
            axis="release_phase_dt_recenter",
            cutoff_offset=float(cutoff) - center,
        )
        config.dt = float(base.dt) * options.dt_scale
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
        setattr(config, "_dt_variant", "half_dt")
        setattr(config, "_dt_scale", options.dt_scale)
        variants.append(config)
    return variants


def _add_recenter_fields(row: dict[str, Any], config: Prototype3DConfig) -> None:
    row["prediction_role"] = getattr(config, "_prediction_role", "unlabeled_recenter")
    row["dt_variant"] = getattr(config, "_dt_variant", "half_dt")
    row["dt_scale"] = getattr(config, "_dt_scale", 0.5)
    row["no_active_second_pulse"] = config.second_pulse_center_time is None and config.second_pulse_duration <= EPSILON
    row["no_resonator_layer"] = not config.resonator_enabled


def _annotated_robust_rows(robust_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_variant = {str(row.get("variant")): row for row in source_rows}
    out = []
    for row in robust_rows:
        source = by_variant.get(str(row.get("variant")), {})
        combined = dict(row)
        combined["prediction_role"] = source.get("prediction_role", "")
        combined["dt_variant"] = source.get("dt_variant", "")
        combined["dt_scale"] = source.get("dt_scale", "")
        combined["dt"] = source.get("dt", "")
        out.append(combined)
    return out


def _max_neighbor_cluster_size(rows: list[dict[str, Any]], options: ReleasePhaseDtRecenterOptions) -> int:
    cutoffs = sorted(_float(row.get("drive_cutoff_time")) for row in rows)
    if not cutoffs:
        return 0
    best = current = 1
    for previous, current_cutoff in zip(cutoffs, cutoffs[1:]):
        if current_cutoff - previous <= options.neighboring_cutoff_gap + 1.0e-9:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def _threshold_free_order_supports(
    candidate_rows: list[dict[str, Any]],
    low_rows: list[dict[str, Any]],
    options: ReleasePhaseDtRecenterOptions,
) -> bool:
    if not candidate_rows or not low_rows:
        return False
    best_candidate = max(candidate_rows, key=_score_key)
    best_low = max(low_rows, key=_score_key)
    score_margin = _score_key(best_candidate) - _score_key(best_low)
    timing_margin = _float(best_candidate.get("return_timing_regularity")) - _float(best_low.get("return_timing_regularity"))
    area_margin = _float(best_candidate.get("post_cutoff_shell_area")) - _float(best_low.get("post_cutoff_shell_area"))
    return score_margin > options.threshold_free_score_margin and timing_margin >= -0.05 and area_margin >= -1.0e-5


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    robust_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ReleasePhaseDtRecenterOptions,
) -> None:
    clean_rows = [row for row in rows if row.get("prediction_role") == "recenter_candidate" and _strict_clean_pass(row, options)]
    clean_cutoffs = [_float(row.get("drive_cutoff_time")) for row in clean_rows]
    clean_phases = [_float(row.get("cutoff_phase_cycles")) for row in clean_rows]
    best = max(rows, key=_score_key, default={})
    lines = [
        f"# 3D Release-Phase Half-dt Recentering: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best row: `{best.get('variant', 'n/a')}`",
        "",
        "## Half-dt Recentered Phase Cluster",
        "",
        "| Role | Cutoff | Phase | Default | Strict 0.35 | Strict 0.40 | Clean | Ret | Outer/Shell | Decay | Score |",
        "| --- | ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(rows, key=lambda item: (_float(item.get("drive_cutoff_time")), str(item.get("prediction_role")))):
        lines.append(
            "| "
            f"{row.get('prediction_role')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{row.get('default_major_peaks_at_0p30')}/{row.get('default_refocus_peaks_at_0p30')} | "
            f"{row.get('strict_major_peaks_at_0p35')}/{row.get('strict_refocus_peaks_at_0p35')} | "
            f"{row.get('strict_major_peaks_at_0p40')}/{row.get('strict_refocus_peaks_at_0p40')} | "
            f"{row.get('strict_clean_pass')} | "
            f"{_format(row.get('retention'))} | "
            f"{_format(row.get('outer_shell'))} | "
            f"{_format(row.get('decay'))} | "
            f"{_format(row.get('conservative_score'))} |"
        )
    lines.extend(
        [
            "",
            "## Comparison to Baseline Blind-Confirmed Cluster",
            "",
            "- Baseline blind-confirmed strong rows were `17.932885` and `17.937885`; both were default 11/10 and strict 9/8.",
            "- The prior half-dt numerical validation kept `17.937885` strict-clean but dropped `17.932885` to strict 8/7.",
            "- This control tests only half dt and asks whether the optimum shifts upward around the surviving row.",
            "",
            "## Strict 9/8 Preservation Window",
            "",
            f"- Strict-clean candidate count: `{len(clean_rows)}`",
            f"- Max neighboring strict-clean cluster size: `{classification.get('checks', {}).get('max_neighboring_strict_clean_cluster', 0)}`",
            f"- Cutoff span: `{_format(min(clean_cutoffs))}-{_format(max(clean_cutoffs))}`" if clean_cutoffs else "- Cutoff span: `none`",
            f"- Phase span: `{_format(min(clean_phases))}-{_format(max(clean_phases))}`" if clean_phases else "- Phase span: `none`",
            "",
            "## Threshold-Free Lifecycle Metrics",
            "",
            "| Role | Cutoff | Shell Area | Tail Area t>=50 | Autocorr | Spectral | Timing Regularity |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(rows, key=lambda item: _score_key(item), reverse=True):
        lines.append(
            "| "
            f"{row.get('prediction_role')} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('post_cutoff_shell_area'))} | "
            f"{_format(row.get('tail_area_after_t50'))} | "
            f"{_format(row.get('shell_energy_autocorrelation'))} | "
            f"{_format(row.get('dominant_spectral_concentration'))} | "
            f"{_format(row.get('return_timing_regularity'))} |"
        )
    lines.extend(
        [
            "",
            "## Recommended Next Numerical Check",
            "",
            _recommendation(classification),
            "",
            "## Files",
            "",
            "- `release_phase_dt_recenter_report.md`",
            "- `release_phase_dt_recenter_summary.csv`",
            "- `release_phase_dt_recenter_threshold_robust_score.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _recommendation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "release_phase_half_dt_recentered":
        return "A future explicitly requested numerical check can use the recentered half-dt window as the quarter-dt target; do not run quarter dt automatically."
    if label == "release_phase_half_dt_single_row":
        return "Do not broaden the map. If requested, repeat or quarter-dt check only the surviving row and its immediate neighbors."
    if label == "release_phase_half_dt_inconclusive":
        return "Inspect threshold-free traces before adding mechanisms; event counts alone are not stable enough for a broader sweep."
    return "Do not run quarter dt yet; the half-dt strict region did not remain strong enough to justify further numerical tightening without a new reason."


def _variant_name(role: str, cutoff: float) -> str:
    safe = f"{cutoff:.6f}".rstrip("0").rstrip(".").replace(".", "p")
    return f"half_dt_{role}_cutoff_{safe}"


def _summary_fields() -> list[str]:
    return [
        "variant",
        "release_phase_dt_recenter_classification",
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


def _threshold_robust_fields() -> list[str]:
    return [
        "variant",
        "release_phase_dt_recenter_classification",
        "prediction_role",
        "dt_variant",
        "dt_scale",
        "dt",
        "drive_cutoff_time",
        "cutoff_phase_cycles",
        "rank",
        "conservative_score",
        "default_threshold_score",
        "min_major_peaks_across_thresholds",
        "median_major_peaks_across_thresholds",
        "min_refocus_peaks_across_thresholds",
        "median_refocus_peaks_across_thresholds",
        "default_major_peaks",
        "default_refocus_peaks",
        "major_peaks_at_0p25",
        "major_peaks_at_0p30",
        "major_peaks_at_0p35",
        "major_peaks_at_0p40",
        "refocus_peaks_at_0p25",
        "refocus_peaks_at_0p30",
        "refocus_peaks_at_0p35",
        "refocus_peaks_at_0p40",
        "retention_median",
        "outer_shell_median",
        "decay_median",
        "no_exit_across_all_thresholds",
        "global_outer_false_across_all_thresholds",
        "threshold_free_shell_energy_area_after_cutoff",
        "threshold_free_tail_energy_area_after_t50",
        "shell_energy_autocorrelation",
        "dominant_spectral_concentration",
        "return_timing_regularity",
    ]
