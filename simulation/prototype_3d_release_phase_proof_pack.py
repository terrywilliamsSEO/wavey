"""Quarter-dt proof pack for the passive 3D release-phase rule."""

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
from .prototype_3d_release_phase_dt_recenter import _annotated_robust_rows, _max_neighbor_cluster_size
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


PROOF_PACK_CUTOFFS = (
    17.935,
    17.9375,
    17.940,
    17.9425,
    17.945,
    17.9475,
    17.9225,
    17.915,
)
PROOF_PACK_ROLES = (
    "lower_immediate_control",
    "proof_candidate",
    "proof_candidate",
    "proof_candidate",
    "proof_candidate",
    "upper_immediate_control",
    "low_side_control",
    "weak_negative_control",
)


@dataclass(frozen=True)
class ReleasePhaseProofPackOptions(ReleasePhaseNumericalValidationOptions):
    """Options for the fixed quarter-dt proof pack."""

    cutoffs: tuple[float, ...] = PROOF_PACK_CUTOFFS
    prediction_roles: tuple[str, ...] = PROOF_PACK_ROLES
    dt_scale: float = 0.25
    neighboring_cutoff_gap: float = 0.003
    min_neighboring_strict_clean_count: int = 2
    max_tail_area_cv: float = 0.03
    max_return_timing_range: float = 0.08
    max_inward_flux_range: float = 0.02
    threshold_free_score_margin: float = 25.0


def run_3d_release_phase_proof_pack(
    base_config: SimulationConfig,
    *,
    options: ReleasePhaseProofPackOptions | None = None,
) -> dict[str, Any]:
    """Run the fixed quarter-dt proof pack around the recentered half-dt window."""

    options = options or ReleasePhaseProofPackOptions()
    control_id = datetime.now().strftime("release_phase_proof_pack_3d_%Y%m%d_%H%M%S")
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
        _add_proof_fields(summary, config)
        rows.append(summary)
        timeseries_rows.extend(result["timeseries"])

    robust_rows = _annotated_robust_rows(
        threshold_robust_refocusing_scores(rows, timeseries_rows, options),
        rows,
    )
    summary_rows = _summary_rows(rows, robust_rows, options)
    gate_rows = _gate_rows(summary_rows, options)
    classification = classify_release_phase_proof_pack(summary_rows, gate_rows, options)
    for row in summary_rows:
        row["release_phase_proof_pack_classification"] = classification["label"]
    for row in robust_rows:
        row["release_phase_proof_pack_classification"] = classification["label"]
    for row in gate_rows:
        row["release_phase_proof_pack_classification"] = classification["label"]

    summary_csv = root / "release_phase_proof_pack_summary.csv"
    threshold_robust_csv = root / "release_phase_proof_pack_threshold_robust_score.csv"
    gates_csv = root / "release_phase_proof_pack_gates.csv"
    report_path = root / "release_phase_proof_pack_report.md"
    candidate_card_path = root / "candidate_card.md"
    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(threshold_robust_csv, robust_rows, _threshold_robust_fields())
    _write_csv(gates_csv, gate_rows, _gate_fields())
    _write_candidate_card(candidate_card_path, control_id, summary_rows, options)
    _write_report(report_path, control_id, summary_rows, robust_rows, gate_rows, classification, options)
    save_json(
        root / "release_phase_proof_pack_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": rows,
            "summary_rows": summary_rows,
            "threshold_robust_rows": robust_rows,
            "gate_rows": gate_rows,
            "summary_csv": str(summary_csv),
            "threshold_robust_csv": str(threshold_robust_csv),
            "gates_csv": str(gates_csv),
            "report_path": str(report_path),
            "candidate_card_path": str(candidate_card_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": rows,
        "summary_rows": summary_rows,
        "threshold_robust_rows": robust_rows,
        "gate_rows": gate_rows,
        "summary_csv": str(summary_csv),
        "threshold_robust_csv": str(threshold_robust_csv),
        "gates_csv": str(gates_csv),
        "report_path": str(report_path),
        "candidate_card_path": str(candidate_card_path),
        "path": str(root),
    }


def classify_release_phase_proof_pack(
    rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]] | None = None,
    options: ReleasePhaseProofPackOptions | None = None,
) -> dict[str, Any]:
    """Classify the quarter-dt proof pack against frozen gates."""

    options = options or ReleasePhaseProofPackOptions()
    candidate_rows = [row for row in rows if row.get("prediction_role") == "proof_candidate"]
    weak_control_rows = [row for row in rows if row.get("prediction_role") in {"low_side_control", "weak_negative_control"}]
    clean_rows = [row for row in candidate_rows if _strict_clean_pass(row, options)]
    candidate_best = max(candidate_rows, key=_score_key, default=None)
    weak_control_best = max(weak_control_rows, key=_score_key, default=None)
    max_cluster = _max_neighbor_cluster_size(clean_rows, options)
    weak_controls_as_well_or_better = bool(
        weak_control_best
        and candidate_best
        and (
            _strict_count_key(weak_control_best) >= _strict_count_key(candidate_best)
            or _score_key(weak_control_best) >= _score_key(candidate_best)
        )
    )
    gates = {str(row.get("gate")): _bool(row.get("pass")) for row in (gate_rows or _gate_rows(rows, options))}
    threshold_free_supported = all(
        gates.get(name, False)
        for name in ("stable_tail_area", "stable_return_timing", "stable_inward_flux", "threshold_free_candidate_margin")
    )
    strict_cluster_supported = max_cluster >= options.min_neighboring_strict_clean_count
    checks = {
        "candidate_row_count": len(candidate_rows),
        "weak_control_row_count": len(weak_control_rows),
        "strict_clean_candidate_count": len(clean_rows),
        "max_neighboring_strict_clean_cluster": max_cluster,
        "weak_controls_as_well_or_better": weak_controls_as_well_or_better,
        "threshold_free_supported": threshold_free_supported,
        "best_candidate": (candidate_best or {}).get("variant"),
        "best_candidate_cutoff": (candidate_best or {}).get("drive_cutoff_time"),
        "best_candidate_score": _score_key(candidate_best),
        "best_weak_control": (weak_control_best or {}).get("variant"),
        "best_weak_control_score": _score_key(weak_control_best),
    }
    if strict_cluster_supported and threshold_free_supported and not weak_controls_as_well_or_better:
        return {
            "label": "release_phase_quarter_dt_proof_supported",
            "reason": "Quarter dt preserves a neighboring strict-clean cluster and passes the threshold-free stability gates.",
            "checks": checks,
        }
    if len(clean_rows) == 1 and threshold_free_supported and not weak_controls_as_well_or_better:
        return {
            "label": "release_phase_quarter_dt_single_row",
            "reason": "Quarter dt preserves only one strict-clean row, though threshold-free gates still support the candidate family.",
            "checks": checks,
        }
    if threshold_free_supported and not weak_controls_as_well_or_better:
        return {
            "label": "release_phase_quarter_dt_threshold_free_supported",
            "reason": "Strict event counts degraded, but threshold-free proof metrics still favor the candidate family.",
            "checks": checks,
        }
    return {
        "label": "release_phase_quarter_dt_failed",
        "reason": "Quarter dt did not preserve strict-clean support or threshold-free candidate separation.",
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: ReleasePhaseProofPackOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    center = options.cutoff_center if options.cutoff_center is not None else float(base.driver.drive_cutoff_time) + options.cutoff_delta
    variants = []
    for index, cutoff in enumerate(options.cutoffs):
        role = options.prediction_roles[index] if index < len(options.prediction_roles) else f"unlabeled_proof_{index + 1}"
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
            axis="release_phase_proof_pack",
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
        setattr(config, "_dt_variant", "quarter_dt")
        setattr(config, "_dt_scale", options.dt_scale)
        variants.append(config)
    return variants


def _add_proof_fields(row: dict[str, Any], config: Prototype3DConfig) -> None:
    row["prediction_role"] = getattr(config, "_prediction_role", "unlabeled_proof")
    row["dt_variant"] = getattr(config, "_dt_variant", "quarter_dt")
    row["dt_scale"] = getattr(config, "_dt_scale", 0.25)
    row["no_active_second_pulse"] = config.second_pulse_center_time is None and config.second_pulse_duration <= EPSILON
    row["no_resonator_layer"] = not config.resonator_enabled


def _gate_rows(rows: list[dict[str, Any]], options: ReleasePhaseProofPackOptions) -> list[dict[str, Any]]:
    candidate_rows = [row for row in rows if row.get("prediction_role") == "proof_candidate"]
    weak_control_rows = [row for row in rows if row.get("prediction_role") in {"low_side_control", "weak_negative_control"}]
    clean_rows = [row for row in candidate_rows if _strict_clean_pass(row, options)]
    proof_rows = clean_rows if clean_rows else candidate_rows
    best_candidate = max(candidate_rows, key=_score_key, default={})
    best_weak_control = max(weak_control_rows, key=_score_key, default={})
    tail_cv = _coefficient_of_variation([_float(row.get("tail_area_after_t50")) for row in proof_rows])
    timing_range = _value_range([_float(row.get("return_timing_regularity")) for row in proof_rows])
    inward_range = _value_range([_float(row.get("inward_flux_fraction")) for row in proof_rows])
    score_margin = _score_key(best_candidate) - _score_key(best_weak_control)
    return [
        _gate("strict_neighboring_9_8", _max_neighbor_cluster_size(clean_rows, options) >= options.min_neighboring_strict_clean_count, _max_neighbor_cluster_size(clean_rows, options), f">={options.min_neighboring_strict_clean_count}"),
        _gate("no_exit", bool(clean_rows) and all(_bool(row.get("no_exit")) for row in clean_rows), "all clean rows", "true"),
        _gate("global_outer_false", bool(clean_rows) and all(_bool(row.get("global_outer_false")) for row in clean_rows), "all clean rows", "true"),
        _gate("outer_shell_below_1", bool(clean_rows) and all(_float(row.get("outer_shell")) < 1.0 for row in clean_rows), "all clean rows", "<1.0"),
        _gate("stable_tail_area", bool(proof_rows) and tail_cv <= options.max_tail_area_cv, tail_cv, f"<={options.max_tail_area_cv}"),
        _gate("stable_return_timing", bool(proof_rows) and timing_range <= options.max_return_timing_range, timing_range, f"<={options.max_return_timing_range}"),
        _gate("stable_inward_flux", bool(proof_rows) and inward_range <= options.max_inward_flux_range, inward_range, f"<={options.max_inward_flux_range}"),
        _gate("threshold_free_candidate_margin", score_margin > options.threshold_free_score_margin, score_margin, f">{options.threshold_free_score_margin}"),
    ]


def _gate(name: str, passed: bool, value: Any, threshold: str) -> dict[str, Any]:
    return {"gate": name, "pass": passed, "value": value, "threshold": threshold}


def _write_candidate_card(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    options: ReleasePhaseProofPackOptions,
) -> None:
    candidates = [row for row in rows if row.get("prediction_role") == "proof_candidate"]
    phases = [_float(row.get("cutoff_phase_cycles")) for row in candidates]
    lines = [
        "# Frozen Candidate Card",
        "",
        f"- Proof pack: `{control_id}`",
        "- Grid: `41^3`",
        "- Lattice: neutral",
        "- Source: inner-sponge-edge sign-flip cubic boundary source",
        "- Sponge: stronger sponge at original width",
        f"- Frequency: `{options.fixed_drive_frequency}`",
        "- Work: matched per physical source area",
        "- Shell metric: radius-5 shell window",
        "- Active second pulses: none",
        "- Resonator layer: none",
        f"- Quarter-dt proof cutoffs: `{_format(min(options.cutoffs))}-{_format(max(options.cutoffs))}` with fixed preselected controls",
        f"- Candidate phase span: `{_format(min(phases))}-{_format(max(phases))}`" if phases else "- Candidate phase span: `not run`",
        "",
        "## Frozen Gates",
        "",
        "- Strict event floor: `9/8` at thresholds `0.35` and `0.40`",
        "- No shell exit",
        "- Global outer flag false",
        "- Outer/shell below `1.0`",
        f"- Tail-area coefficient of variation at or below `{options.max_tail_area_cv}`",
        f"- Return-timing regularity range at or below `{options.max_return_timing_range}`",
        f"- Inward-flux fraction range at or below `{options.max_inward_flux_range}`",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    robust_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ReleasePhaseProofPackOptions,
) -> None:
    best = max(rows, key=_score_key, default={})
    clean = [row for row in rows if row.get("prediction_role") == "proof_candidate" and _strict_clean_pass(row, options)]
    clean_cutoffs = [_float(row.get("drive_cutoff_time")) for row in clean]
    clean_phases = [_float(row.get("cutoff_phase_cycles")) for row in clean]
    lines = [
        f"# 3D Release-Phase Proof Pack: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best row: `{best.get('variant', 'n/a')}`",
        "",
        "## Frozen Candidate Card",
        "",
        "- `41^3`, neutral lattice, stronger sponge, inner-sponge-edge sign-flip cubic boundary source.",
        f"- Frequency `{options.fixed_drive_frequency}`, matched work per physical source area, radius-5 shell window.",
        "- No active second pulses, no resonator layer, no defects/traps/medium changes/grid expansion.",
        "- Candidate rule: release phase near half-cycle; quarter-dt check is limited to the half-dt recentered window and fixed controls.",
        "",
        "## Pre-registered Gates",
        "",
        "| Gate | Pass | Value | Threshold |",
        "| --- | --- | ---: | --- |",
    ]
    for row in gate_rows:
        lines.append(f"| {row.get('gate')} | {row.get('pass')} | {_format_any(row.get('value'))} | {row.get('threshold')} |")
    lines.extend(
        [
            "",
            "## Numerical Settlement",
            "",
            f"- Strict-clean candidate count: `{len(clean)}`",
            f"- Strict-clean cutoff span: `{_format(min(clean_cutoffs))}-{_format(max(clean_cutoffs))}`" if clean_cutoffs else "- Strict-clean cutoff span: `none`",
            f"- Strict-clean phase span: `{_format(min(clean_phases))}-{_format(max(clean_phases))}`" if clean_phases else "- Strict-clean phase span: `none`",
            "",
            "| Role | Cutoff | Phase | Default | Strict 0.35 | Strict 0.40 | Clean | Ret | Outer/Shell | Decay |",
            "| --- | ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(rows, key=lambda item: _float(item.get("drive_cutoff_time"))):
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
            f"{_format(row.get('decay'))} |"
        )
    lines.extend(
        [
            "",
            "## Threshold-Free Phase, Flux, and Return Timing",
            "",
            "| Role | Cutoff | Shell Area | Tail Area t>=50 | Autocorr | Spectral | Timing Regularity | Inward Flux | Outward Flux |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
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
            f"{_format(row.get('return_timing_regularity'))} | "
            f"{_format(row.get('inward_flux_fraction'))} | "
            f"{_format(row.get('outward_flux_fraction'))} |"
        )
    lines.extend(
        [
            "",
            "## Scale-Test Gate",
            "",
            _scale_recommendation(classification),
            "",
            "## Files",
            "",
            "- `candidate_card.md`",
            "- `release_phase_proof_pack_report.md`",
            "- `release_phase_proof_pack_summary.csv`",
            "- `release_phase_proof_pack_threshold_robust_score.csv`",
            "- `release_phase_proof_pack_gates.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _scale_recommendation(classification: dict[str, Any]) -> str:
    if classification["label"] == "release_phase_quarter_dt_proof_supported":
        return "Quarter dt supports the recentered passive pocket. The next step, only if requested, is one resolution lift with release phase recalibrated by the rule, not a copied cutoff and not a sweep."
    if classification["label"] == "release_phase_quarter_dt_single_row":
        return "Quarter dt leaves only one strict-clean row. Repeat or inspect threshold-free traces before any scale lift."
    if classification["label"] == "release_phase_quarter_dt_threshold_free_supported":
        return "Threshold-free metrics favor the candidate family, but event-count support is not settled enough for a scale lift."
    return "Do not scale. The quarter-dt proof pack did not support the passive phase pocket."


def _variant_name(role: str, cutoff: float) -> str:
    safe = f"{cutoff:.6f}".rstrip("0").rstrip(".").replace(".", "p")
    return f"quarter_dt_{role}_cutoff_{safe}"


def _coefficient_of_variation(values: list[float]) -> float:
    values = [value for value in values if math.isfinite(value) and value > 0.0]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance) / max(mean, EPSILON)


def _value_range(values: list[float]) -> float:
    values = [value for value in values if math.isfinite(value)]
    if len(values) < 2:
        return 0.0
    return max(values) - min(values)


def _format_any(value: Any) -> str:
    if isinstance(value, (int, float)):
        return _format(value)
    return str(value)


def _summary_fields() -> list[str]:
    return [
        "variant",
        "release_phase_proof_pack_classification",
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
        "release_phase_proof_pack_classification",
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


def _gate_fields() -> list[str]:
    return ["gate", "release_phase_proof_pack_classification", "pass", "value", "threshold"]
