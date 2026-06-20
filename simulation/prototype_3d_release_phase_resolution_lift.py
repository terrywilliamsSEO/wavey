"""Single-resolution lift for the passive 3D release-phase rule."""

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
from .prototype_3d_release_phase_dt_recenter import _annotated_robust_rows
from .prototype_3d_release_phase_numerical_validation import (
    _bool,
    _float,
    _int,
    _score_key,
    _strict_clean_pass,
    _strict_count_key,
    _summary_rows,
)
from .prototype_3d_release_phase_proof_pack import ReleasePhaseProofPackOptions
from .prototype_3d_source_sponge import _effective_source_area, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


RESOLUTION_LIFT_PHASES = (0.5071, 0.5025, 0.4818)
RESOLUTION_LIFT_ROLES = ("candidate", "low_side_phase_control", "weak_negative_phase_control")


@dataclass(frozen=True)
class ReleasePhaseResolutionLiftOptions(ReleasePhaseProofPackOptions):
    """Options for the fixed release-phase resolution lift."""

    grid_size: int = 51
    phase_targets: tuple[float, ...] = RESOLUTION_LIFT_PHASES
    prediction_roles: tuple[str, ...] = RESOLUTION_LIFT_ROLES
    phase_cycle_index: int = 16
    dt_scale: float = 0.25
    shell_window_width: float | None = 4.0
    proof_tail_area_reference: float = 0.00122720436614
    proof_autocorrelation_reference: float = 0.999972228504
    proof_spectral_reference: float = 0.740828640542
    proof_timing_reference: float = 0.839131774079
    max_tail_area_relative_delta: float = 0.35
    max_autocorrelation_drop: float = 0.01
    max_spectral_relative_delta: float = 0.25
    max_return_timing_delta: float = 0.20
    max_work_per_area_relative_error: float = 0.02
    max_added_positive_work: float = 1.0e-6


def run_3d_release_phase_resolution_lift(
    base_config: SimulationConfig,
    *,
    options: ReleasePhaseResolutionLiftOptions | None = None,
) -> dict[str, Any]:
    """Run one recalibrated resolution lift plus two phase controls."""

    options = options or ReleasePhaseResolutionLiftOptions()
    control_id = datetime.now().strftime("release_phase_resolution_lift_3d_%Y%m%d_%H%M%S")
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
        _add_resolution_lift_fields(summary, config)
        rows.append(summary)
        timeseries_rows.extend(result["timeseries"])

    robust_rows = _annotated_robust_rows(
        threshold_robust_refocusing_scores(rows, timeseries_rows, options),
        rows,
    )
    summary_rows = _summary_rows(rows, robust_rows, options)
    _add_accounting_fields(summary_rows, rows, options)
    gate_rows = _gate_rows(summary_rows, options)
    classification = classify_release_phase_resolution_lift(summary_rows, gate_rows, options)
    for row in summary_rows:
        row["release_phase_resolution_lift_classification"] = classification["label"]
    for row in robust_rows:
        row["release_phase_resolution_lift_classification"] = classification["label"]
    for row in gate_rows:
        row["release_phase_resolution_lift_classification"] = classification["label"]

    summary_csv = root / "release_phase_resolution_lift_summary.csv"
    threshold_robust_csv = root / "release_phase_resolution_lift_threshold_robust_score.csv"
    gates_csv = root / "release_phase_resolution_lift_gates.csv"
    report_path = root / "release_phase_resolution_lift_report.md"
    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(threshold_robust_csv, robust_rows, _threshold_robust_fields())
    _write_csv(gates_csv, gate_rows, _gate_fields())
    _write_report(report_path, control_id, summary_rows, gate_rows, classification, options)
    save_json(
        root / "release_phase_resolution_lift_summary.json",
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
        "path": str(root),
    }


def classify_release_phase_resolution_lift(
    rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]] | None = None,
    options: ReleasePhaseResolutionLiftOptions | None = None,
) -> dict[str, Any]:
    """Classify the single-grid release-phase lift against frozen gates."""

    options = options or ReleasePhaseResolutionLiftOptions()
    candidate = _candidate_row(rows)
    controls = _control_rows(rows)
    gates = {str(row.get("gate")): _bool(row.get("pass")) for row in (gate_rows or _gate_rows(rows, options))}
    candidate_clean = all(
        gates.get(name, False)
        for name in ("candidate_strict_9_8", "candidate_no_exit", "candidate_global_outer_false", "candidate_outer_shell_below_1")
    )
    threshold_free_close = all(
        gates.get(name, False)
        for name in (
            "tail_area_close_to_proof",
            "autocorrelation_close_to_proof",
            "spectral_concentration_close_to_proof",
            "return_timing_close_to_proof",
            "threshold_free_candidate_margin",
        )
    )
    controls_below = gates.get("controls_below_candidate", False)
    energy_clean = gates.get("energy_accounting_clean", False)
    checks = {
        "candidate": (candidate or {}).get("variant"),
        "candidate_cutoff": (candidate or {}).get("drive_cutoff_time"),
        "candidate_phase": (candidate or {}).get("cutoff_phase_cycles"),
        "candidate_score": _score_key(candidate),
        "candidate_strict_count": _strict_count_key(candidate or {}),
        "control_count": len(controls),
        "best_control_score": max((_score_key(row) for row in controls), default=0.0),
        "candidate_clean": candidate_clean,
        "threshold_free_close": threshold_free_close,
        "controls_below": controls_below,
        "energy_clean": energy_clean,
    }
    if candidate_clean and threshold_free_close and controls_below and energy_clean:
        return {
            "label": "release_phase_resolution_lift_supported",
            "reason": "The lifted-grid candidate preserves strict clean refocusing and passes threshold-free, control, and energy-accounting gates.",
            "checks": checks,
        }
    if candidate_clean and controls_below and energy_clean:
        return {
            "label": "release_phase_resolution_lift_event_supported_threshold_free_unsettled",
            "reason": "The lifted-grid candidate preserves strict counts, but threshold-free closeness to the proof pack is not fully settled.",
            "checks": checks,
        }
    if candidate_clean and energy_clean:
        return {
            "label": "release_phase_resolution_lift_controls_competitive",
            "reason": "The lifted-grid candidate is strict-clean, but phase controls are too competitive to isolate the release-phase rule.",
            "checks": checks,
        }
    if threshold_free_close and controls_below and energy_clean:
        return {
            "label": "release_phase_resolution_lift_inconclusive",
            "reason": "Threshold-free metrics favor the lifted candidate, but strict 9/8 did not survive.",
            "checks": checks,
        }
    return {
        "label": "release_phase_resolution_lift_failed",
        "reason": "The lifted-grid candidate did not preserve the proof-pack pass gates.",
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: ReleasePhaseResolutionLiftOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    variants = []
    for index, phase in enumerate(options.phase_targets):
        role = options.prediction_roles[index] if index < len(options.prediction_roles) else f"phase_control_{index + 1}"
        cutoff = _cutoff_from_phase(float(phase), options)
        config = _variant(
            _variant_name(options.grid_size, role, float(phase)),
            base,
            options,
            source_width,
            cutoff=cutoff,
            frequency=options.fixed_drive_frequency,
            phase_offset=0.0,
            cubic_sign=-1.0,
            family="sign_flip",
            axis="release_phase_resolution_lift",
            cutoff_offset=cutoff - float(base.driver.drive_cutoff_time),
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
        setattr(config, "_target_release_phase", float(phase))
        setattr(config, "_dt_variant", "quarter_dt")
        setattr(config, "_dt_scale", options.dt_scale)
        variants.append(config)
    return variants


def _cutoff_from_phase(phase: float, options: ReleasePhaseResolutionLiftOptions) -> float:
    return (float(options.phase_cycle_index) + phase) / max(float(options.fixed_drive_frequency), EPSILON)


def _add_resolution_lift_fields(row: dict[str, Any], config: Prototype3DConfig) -> None:
    row["prediction_role"] = getattr(config, "_prediction_role", "unlabeled_resolution_lift")
    row["target_release_phase"] = getattr(config, "_target_release_phase", None)
    row["dt_variant"] = getattr(config, "_dt_variant", "quarter_dt")
    row["dt_scale"] = getattr(config, "_dt_scale", 0.25)
    row["no_active_second_pulse"] = config.second_pulse_center_time is None and config.second_pulse_duration <= EPSILON
    row["no_resonator_layer"] = not config.resonator_enabled


def _add_accounting_fields(
    summary_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    options: ReleasePhaseResolutionLiftOptions,
) -> None:
    raw_by_variant = {str(row.get("variant")): row for row in raw_rows}
    for row in summary_rows:
        raw = raw_by_variant.get(str(row.get("variant")), {})
        row["target_release_phase"] = raw.get("target_release_phase")
        added = _float(raw.get("added_positive_work"))
        work_per_area = _float(row.get("work_per_source_area"))
        target_work = _float(row.get("target_reference_work_per_source_area"))
        work_error = abs(work_per_area - target_work) / max(abs(target_work), EPSILON)
        row["added_positive_work"] = added
        row["energy_accounting_clean"] = (
            added <= options.max_added_positive_work
            and work_error <= options.max_work_per_area_relative_error
            and _bool(row.get("no_active_second_pulse"))
            and _bool(row.get("no_resonator_layer"))
        )
        row["work_per_area_relative_error"] = work_error


def _gate_rows(rows: list[dict[str, Any]], options: ReleasePhaseResolutionLiftOptions) -> list[dict[str, Any]]:
    candidate = _candidate_row(rows) or {}
    controls = _control_rows(rows)
    best_control = max(controls, key=_score_key, default={})
    candidate_score = _score_key(candidate)
    control_score = _score_key(best_control)
    tail_delta = _relative_delta(_float(candidate.get("tail_area_after_t50")), options.proof_tail_area_reference)
    autocorr_drop = options.proof_autocorrelation_reference - _float(candidate.get("shell_energy_autocorrelation"))
    spectral_delta = _relative_delta(_float(candidate.get("dominant_spectral_concentration")), options.proof_spectral_reference)
    timing_delta = abs(_float(candidate.get("return_timing_regularity")) - options.proof_timing_reference)
    return [
        _gate("candidate_strict_9_8", _strict_clean_pass(candidate, options), _count_label(candidate), ">=9/8 plus clean guards"),
        _gate("candidate_no_exit", _bool(candidate.get("no_exit")), candidate.get("no_exit"), "true"),
        _gate("candidate_global_outer_false", _bool(candidate.get("global_outer_false")), candidate.get("global_outer_false"), "true"),
        _gate("candidate_outer_shell_below_1", _float(candidate.get("outer_shell")) < 1.0, candidate.get("outer_shell"), "<1.0"),
        _gate("controls_below_candidate", _controls_below_candidate(candidate, controls), _control_value(candidate, best_control), "controls below candidate"),
        _gate("tail_area_close_to_proof", tail_delta <= options.max_tail_area_relative_delta, tail_delta, f"<={options.max_tail_area_relative_delta} relative"),
        _gate("autocorrelation_close_to_proof", autocorr_drop <= options.max_autocorrelation_drop, autocorr_drop, f"drop<={options.max_autocorrelation_drop}"),
        _gate("spectral_concentration_close_to_proof", spectral_delta <= options.max_spectral_relative_delta, spectral_delta, f"<={options.max_spectral_relative_delta} relative"),
        _gate("return_timing_close_to_proof", timing_delta <= options.max_return_timing_delta, timing_delta, f"<={options.max_return_timing_delta}"),
        _gate("threshold_free_candidate_margin", candidate_score - control_score > options.threshold_free_score_margin, candidate_score - control_score, f">{options.threshold_free_score_margin}"),
        _gate("energy_accounting_clean", _bool(candidate.get("energy_accounting_clean")), _energy_value(candidate), "no post-cutoff work and matched work/area"),
    ]


def _candidate_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("prediction_role") == "candidate"), None)


def _control_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("prediction_role") != "candidate"]


def _controls_below_candidate(candidate: dict[str, Any], controls: list[dict[str, Any]]) -> bool:
    if not candidate or not controls:
        return False
    candidate_count = _strict_count_key(candidate)
    candidate_score = _score_key(candidate)
    return all(_strict_count_key(row) < candidate_count and _score_key(row) < candidate_score for row in controls)


def _control_value(candidate: dict[str, Any], best_control: dict[str, Any]) -> str:
    return f"candidate {_count_label(candidate)} / best control {_count_label(best_control)}"


def _energy_value(candidate: dict[str, Any]) -> str:
    return (
        f"added_work={_format(candidate.get('added_positive_work'))}, "
        f"work_error={_format(candidate.get('work_per_area_relative_error'))}"
    )


def _gate(name: str, passed: bool, value: Any, threshold: str) -> dict[str, Any]:
    return {"gate": name, "pass": passed, "value": value, "threshold": threshold}


def _relative_delta(value: float, reference: float) -> float:
    return abs(value - reference) / max(abs(reference), EPSILON)


def _count_label(row: dict[str, Any]) -> str:
    return f"{_int(row.get('conservative_major_peaks'))}/{_int(row.get('conservative_refocus_peaks'))}"


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ReleasePhaseResolutionLiftOptions,
) -> None:
    candidate = _candidate_row(rows) or {}
    lines = [
        f"# 3D Release-Phase Resolution Lift: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Candidate: `{candidate.get('variant', 'n/a')}`",
        f"- Grid: `{options.grid_size}^3`",
        "",
        "## Fixed Setup",
        "",
        "- Neutral lattice, same physical domain, stronger sponge with the same physical width/strength rule.",
        "- Inner-sponge-edge sign-flip cubic boundary source, frequency `0.92`, matched work per physical source area.",
        "- Radius-5 physical shell window with physical width `4.0`, no active second pulses, no resonator layer.",
        "",
        "## Gates",
        "",
        "| Gate | Pass | Value | Threshold |",
        "| --- | --- | --- | --- |",
    ]
    for row in gate_rows:
        lines.append(f"| {row.get('gate')} | {row.get('pass')} | {_format_any(row.get('value'))} | {row.get('threshold')} |")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Role | Grid | Target Phase | Cutoff | Actual Phase | Default | Strict | Clean | Ret | Outer/Shell | Tail Area | Timing | Energy Clean |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row.get('prediction_role')} | "
            f"{row.get('grid_size')} | "
            f"{_format(row.get('target_release_phase'))} | "
            f"{_format(row.get('drive_cutoff_time'))} | "
            f"{_format(row.get('cutoff_phase_cycles'))} | "
            f"{row.get('default_major_peaks_at_0p30')}/{row.get('default_refocus_peaks_at_0p30')} | "
            f"{row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')} | "
            f"{row.get('strict_clean_pass')} | "
            f"{_format(row.get('retention'))} | "
            f"{_format(row.get('outer_shell'))} | "
            f"{_format(row.get('tail_area_after_t50'))} | "
            f"{_format(row.get('return_timing_regularity'))} | "
            f"{row.get('energy_accounting_clean')} |"
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
            "- `release_phase_resolution_lift_report.md`",
            "- `release_phase_resolution_lift_summary.csv`",
            "- `release_phase_resolution_lift_threshold_robust_score.csv`",
            "- `release_phase_resolution_lift_gates.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "release_phase_resolution_lift_supported":
        return "The passive phase rule survives this controlled resolution lift. The next step should be documentation and a decision about whether one higher grid is justified; do not broaden into a sweep."
    if label == "release_phase_resolution_lift_event_supported_threshold_free_unsettled":
        return "The event-count floor survives, but threshold-free lifecycle metrics moved enough that the result should be treated as numerically unsettled."
    if label == "release_phase_resolution_lift_controls_competitive":
        return "The lifted candidate is clean, but controls are competitive; the phase rule is not isolated at this grid."
    if label == "release_phase_resolution_lift_inconclusive":
        return "Threshold-free metrics still favor the candidate, but strict 9/8 did not survive; inspect event traces before any further scale change."
    return "The controlled resolution lift failed the proof gates. Do not add mechanisms or scale further from this result."


def _variant_name(grid_size: int, role: str, phase: float) -> str:
    safe_phase = f"{phase:.4f}".replace(".", "p")
    return f"resolution_lift_{grid_size}_{role}_phase_{safe_phase}"


def _format_any(value: Any) -> str:
    if isinstance(value, (int, float)):
        return _format(value)
    return str(value)


def _summary_fields() -> list[str]:
    return [
        "variant",
        "release_phase_resolution_lift_classification",
        "prediction_role",
        "target_release_phase",
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
        "work_per_area_relative_error",
        "added_positive_work",
        "energy_accounting_clean",
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
        "release_phase_resolution_lift_classification",
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
    return ["gate", "release_phase_resolution_lift_classification", "pass", "value", "threshold"]
