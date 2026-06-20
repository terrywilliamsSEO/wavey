"""Read-only source-spectrum design audit for the 51^3 release-phase lift."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import json
import math

import numpy as np

from .config import load_json_config, save_json, simulation_config_from_dict
from .prototype_3d import EPSILON
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_CONFIG_PATH = "configs/long_validation_peak_0_92.json"
DEFAULT_DISPERSION_ROOT = "runs/release_phase_dispersion_audit_3d_20260620_150931"
DEFAULT_SPATIAL_PHASE_ROOT = "runs/spatial_phase_instrumentation_3d_20260620_170518"
DEFAULT_PRECOMP_ROOT = "runs/spatial_phase_precomp_design_3d_20260620_175852"


@dataclass(frozen=True)
class SourceSpectrumDesignAuditOptions:
    """Options for the read-only source-spectrum design audit."""

    output_root: str = "runs"
    config_path: str = DEFAULT_CONFIG_PATH
    dispersion_root: str = DEFAULT_DISPERSION_ROOT
    spatial_phase_root: str = DEFAULT_SPATIAL_PHASE_ROOT
    precomp_root: str = DEFAULT_PRECOMP_ROOT
    physical_duration: float = 96.0
    dt_scale: float = 0.25
    proof_cutoff: float = 17.94
    lift_cutoff: float = 17.9425
    drive_frequency: float | None = None
    phase_cycle_index: int = 16
    far_sideband_multiplier: float = 2.0
    min_modal_bandwidth_growth: float = 0.05
    min_spatial_coherence_drop: float = 0.10
    min_current_far_sideband_fraction: float = 0.01
    min_smoothing_sideband_reduction: float = 0.50
    max_smooth_bandwidth_ratio: float = 1.05


def run_3d_source_spectrum_design_audit(
    *,
    options: SourceSpectrumDesignAuditOptions | None = None,
) -> dict[str, Any]:
    """Ask whether source-spectrum narrowing is a plausible next design route."""

    options = options or SourceSpectrumDesignAuditOptions()
    control_id = datetime.now().strftime("source_spectrum_design_audit_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    base_config = simulation_config_from_dict(load_json_config(Path(options.config_path)))
    drive_frequency = float(options.drive_frequency if options.drive_frequency is not None else base_config.driver.frequency)
    dt = float(base_config.dt) * float(options.dt_scale)
    drive_mode = str(base_config.driver.mode)

    dispersion_rows = _read_csv(Path(options.dispersion_root) / "dispersion_blur_model_summary.csv")
    spatial_rows = _read_csv(Path(options.spatial_phase_root) / "spatial_phase_41_vs_51_comparison.csv")
    precomp_summary = _read_json(Path(options.precomp_root) / "spatial_phase_precompensation_design_summary.json")

    source_rows: list[dict[str, Any]] = []
    spectrum_rows: list[dict[str, Any]] = []
    for role, cutoff in (("proof_41", options.proof_cutoff), ("lift_51", options.lift_cutoff)):
        for envelope_kind in ("current_hard_cutoff", "smooth_sin2_same_release"):
            source_summary, spectrum = _source_spectrum_rows(
                role=role,
                cutoff=float(cutoff),
                drive_frequency=drive_frequency,
                dt=dt,
                physical_duration=float(options.physical_duration),
                envelope_kind=envelope_kind,
                far_sideband_multiplier=float(options.far_sideband_multiplier),
            )
            source_rows.append(source_summary)
            spectrum_rows.extend(spectrum)

    summary_row = _summary_row(source_rows, dispersion_rows, spatial_rows, precomp_summary, drive_mode, options)
    rejected_rows = _rejected_rows(summary_row, options)
    classification = classify_source_spectrum_design_audit(summary_row, options)
    summary_row["candidate_gate"] = "supported" if classification["label"] == "source_spectrum_narrowing_candidate_supported" else "blocked"
    candidate = _candidate_payload(summary_row, classification, options, drive_frequency)

    for row_set in (source_rows, spectrum_rows, rejected_rows):
        for row in row_set:
            row["source_spectrum_design_audit_classification"] = classification["label"]
    summary_row["source_spectrum_design_audit_classification"] = classification["label"]

    report_path = root / "source_spectrum_design_audit_report.md"
    summary_csv = root / "source_spectrum_summary.csv"
    spectrum_csv = root / "source_envelope_spectrum.csv"
    candidate_json = root / "smooth_envelope_candidate.json"
    rejected_csv = root / "rejected_source_spectrum_options.csv"
    _write_csv(summary_csv, [summary_row], _summary_fields())
    _write_csv(spectrum_csv, spectrum_rows, _spectrum_fields())
    _write_csv(rejected_csv, rejected_rows, _rejected_fields())
    save_json(candidate_json, candidate)
    _write_report(report_path, control_id, summary_row, source_rows, rejected_rows, candidate, classification, options)
    save_json(
        root / "source_spectrum_design_audit_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "config_path": options.config_path,
            "dispersion_root": options.dispersion_root,
            "spatial_phase_root": options.spatial_phase_root,
            "precomp_root": options.precomp_root,
            "summary_row": summary_row,
            "source_rows": source_rows,
            "rejected_rows": rejected_rows,
            "candidate": candidate,
            "report_path": str(report_path),
            "summary_csv": str(summary_csv),
            "spectrum_csv": str(spectrum_csv),
            "candidate_json": str(candidate_json),
            "rejected_csv": str(rejected_csv),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_row": summary_row,
        "source_rows": source_rows,
        "rejected_rows": rejected_rows,
        "candidate": candidate,
        "report_path": str(report_path),
        "summary_csv": str(summary_csv),
        "spectrum_csv": str(spectrum_csv),
        "candidate_json": str(candidate_json),
        "rejected_csv": str(rejected_csv),
        "path": str(root),
    }


def classify_source_spectrum_design_audit(
    summary: dict[str, Any],
    options: SourceSpectrumDesignAuditOptions | None = None,
) -> dict[str, Any]:
    """Classify whether a smoother source envelope is theoretically justified."""

    options = options or SourceSpectrumDesignAuditOptions()
    same_band = _bool(summary.get("same_modal_band"))
    modal_growth = _float(summary.get("observed_modal_bandwidth_relative_delta"))
    strict_loss = _float(summary.get("strict_major_loss"))
    coherence_drop = max(
        _float(summary.get("shell_phase_coherence_drop")),
        _float(summary.get("radial_phase_coherence_drop")),
        _float(summary.get("angular_phase_coherence_drop")),
    )
    precomp_failed = str(summary.get("phase_precompensation_classification")) == "no_safe_phase_correction"
    current_hard = str(summary.get("current_source_envelope")) == "continuous_hard_cutoff"
    hard_sideband = _float(summary.get("hard_far_sideband_fraction_mean"))
    smooth_sideband = _float(summary.get("smooth_far_sideband_fraction_mean"))
    sideband_reduction = _float(summary.get("smoothing_far_sideband_reduction_fraction"))
    smooth_bandwidth_ratio = _float(summary.get("smooth_to_hard_source_bandwidth_ratio"))
    checks = {
        "same_modal_band": same_band,
        "observed_modal_bandwidth_relative_delta": modal_growth,
        "strict_major_loss": strict_loss,
        "max_spatial_coherence_drop": coherence_drop,
        "phase_precompensation_failed": precomp_failed,
        "current_source_envelope": summary.get("current_source_envelope"),
        "hard_far_sideband_fraction_mean": hard_sideband,
        "smooth_far_sideband_fraction_mean": smooth_sideband,
        "smoothing_far_sideband_reduction_fraction": sideband_reduction,
        "smooth_to_hard_source_bandwidth_ratio": smooth_bandwidth_ratio,
        "hard_source_spectrum_delta_41_to_51": _float(summary.get("hard_source_bandwidth_relative_delta_41_to_51")),
    }
    if not same_band or strict_loss <= 0.0:
        return {
            "label": "source_spectrum_inconclusive",
            "reason": "The existing artifacts do not isolate same-band strict-count loss well enough for a source-spectrum design gate.",
            "checks": checks,
        }
    plausible_problem = (
        modal_growth >= options.min_modal_bandwidth_growth
        and coherence_drop >= options.min_spatial_coherence_drop
        and precomp_failed
        and current_hard
        and hard_sideband >= options.min_current_far_sideband_fraction
    )
    plausible_fix = (
        sideband_reduction >= options.min_smoothing_sideband_reduction
        and smooth_bandwidth_ratio <= options.max_smooth_bandwidth_ratio
    )
    if plausible_problem and plausible_fix:
        return {
            "label": "source_spectrum_narrowing_candidate_supported",
            "reason": "The current rectangular source window has substantial carrier sidebands, and a same-cutoff smooth envelope sharply narrows the source spectrum without changing frequency, release phase, or total work proxy.",
            "checks": checks,
        }
    return {
        "label": "source_spectrum_not_supported_archive",
        "reason": "The source spectrum does not provide a safe theoretical mechanism for the 51^3 bandwidth growth and phase decoherence.",
        "checks": checks,
    }


def _source_spectrum_rows(
    *,
    role: str,
    cutoff: float,
    drive_frequency: float,
    dt: float,
    physical_duration: float,
    envelope_kind: str,
    far_sideband_multiplier: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    times = np.arange(0.0, physical_duration + 0.5 * dt, dt)
    hard = _source_waveform(times, cutoff, drive_frequency, "current_hard_cutoff")
    wave = _source_waveform(times, cutoff, drive_frequency, envelope_kind)
    scale = 1.0
    if envelope_kind != "current_hard_cutoff":
        scale = math.sqrt(float(np.sum(hard**2)) / max(float(np.sum(wave**2)), EPSILON))
        wave = wave * scale
    freqs = np.fft.rfftfreq(times.size, dt)
    power = np.abs(np.fft.rfft(wave)) ** 2
    power[0] = 0.0
    total = max(float(np.sum(power)), EPSILON)
    offset = np.abs(freqs - drive_frequency)
    natural_width = 1.0 / max(cutoff, EPSILON)
    far_band = far_sideband_multiplier * natural_width
    bandwidth = math.sqrt(float(np.sum(power * offset**2)) / total)
    mean_offset = float(np.sum(power * offset)) / total
    far_fraction = float(np.sum(power[offset > far_band])) / total
    main_fraction = float(np.sum(power[offset <= natural_width])) / total
    peak_frequency = float(freqs[int(np.argmax(power))])
    energy_proxy = float(np.sum(wave**2) * dt)
    summary = {
        "role": role,
        "envelope_kind": envelope_kind,
        "cutoff": cutoff,
        "release_phase_cycles": (cutoff * drive_frequency) % 1.0,
        "drive_frequency": drive_frequency,
        "dt": dt,
        "physical_duration": physical_duration,
        "work_proxy_scale": scale,
        "energy_proxy": energy_proxy,
        "natural_width": natural_width,
        "carrier_peak_frequency": peak_frequency,
        "carrier_peak_offset": peak_frequency - drive_frequency,
        "source_bandwidth": bandwidth,
        "source_mean_abs_offset": mean_offset,
        "main_band_fraction": main_fraction,
        "far_sideband_threshold": far_band,
        "far_sideband_fraction": far_fraction,
        "far_sideband_concentration": 1.0 - far_fraction,
    }
    rows = []
    for freq, value, off in zip(freqs, power / total, offset):
        rows.append(
            {
                "role": role,
                "envelope_kind": envelope_kind,
                "cutoff": cutoff,
                "drive_frequency": drive_frequency,
                "frequency": float(freq),
                "offset_from_carrier": float(freq - drive_frequency),
                "abs_offset_from_carrier": float(off),
                "normalized_power": float(value),
                "inside_natural_band": bool(off <= natural_width),
                "inside_far_sideband_threshold": bool(off <= far_band),
            }
        )
    return summary, rows


def _source_waveform(times: np.ndarray, cutoff: float, drive_frequency: float, envelope_kind: str) -> np.ndarray:
    active = times <= cutoff
    carrier = np.sin(2.0 * math.pi * drive_frequency * times)
    if envelope_kind == "smooth_sin2_same_release":
        phase = np.clip(times / max(cutoff, EPSILON), 0.0, 1.0)
        envelope = np.sin(math.pi * phase) ** 2
        return np.where(active, envelope * carrier, 0.0)
    return np.where(active, carrier, 0.0)


def _summary_row(
    source_rows: list[dict[str, Any]],
    dispersion_rows: list[dict[str, Any]],
    spatial_rows: list[dict[str, Any]],
    precomp_summary: dict[str, Any],
    drive_mode: str,
    options: SourceSpectrumDesignAuditOptions,
) -> dict[str, Any]:
    current = _rows_by_role_and_kind(source_rows, "current_hard_cutoff")
    smooth = _rows_by_role_and_kind(source_rows, "smooth_sin2_same_release")
    hard_mean_far = _mean([row.get("far_sideband_fraction") for row in current.values()])
    smooth_mean_far = _mean([row.get("far_sideband_fraction") for row in smooth.values()])
    hard_mean_bw = _mean([row.get("source_bandwidth") for row in current.values()])
    smooth_mean_bw = _mean([row.get("source_bandwidth") for row in smooth.values()])
    dispersion = dispersion_rows[0] if dispersion_rows else {}
    spatial = spatial_rows[0] if spatial_rows else {}
    precomp_classification = (precomp_summary.get("classification") or {}).get("label", "")
    return {
        "summary": "source_spectrum_design_audit",
        "current_source_envelope": "continuous_hard_cutoff" if drive_mode == "continuous" else drive_mode,
        "proposed_smooth_envelope": "smooth_sin2_same_release",
        "drive_frequency": _float(next(iter(current.values()), {}).get("drive_frequency")),
        "proof_cutoff": options.proof_cutoff,
        "lift_cutoff": options.lift_cutoff,
        "proof_release_phase_cycles": _float(current.get("proof_41", {}).get("release_phase_cycles")),
        "lift_release_phase_cycles": _float(current.get("lift_51", {}).get("release_phase_cycles")),
        "dt": _float(next(iter(current.values()), {}).get("dt")),
        "hard_source_bandwidth_mean": hard_mean_bw,
        "smooth_source_bandwidth_mean": smooth_mean_bw,
        "smooth_to_hard_source_bandwidth_ratio": smooth_mean_bw / max(hard_mean_bw, EPSILON),
        "hard_far_sideband_fraction_mean": hard_mean_far,
        "smooth_far_sideband_fraction_mean": smooth_mean_far,
        "smoothing_far_sideband_reduction_fraction": (hard_mean_far - smooth_mean_far) / max(hard_mean_far, EPSILON),
        "hard_source_bandwidth_relative_delta_41_to_51": _relative_delta(
            _float(current.get("lift_51", {}).get("source_bandwidth")),
            _float(current.get("proof_41", {}).get("source_bandwidth")),
        ),
        "hard_far_sideband_relative_delta_41_to_51": _relative_delta(
            _float(current.get("lift_51", {}).get("far_sideband_fraction")),
            _float(current.get("proof_41", {}).get("far_sideband_fraction")),
        ),
        "same_modal_band": dispersion.get("same_modal_band", ""),
        "observed_modal_bandwidth_relative_delta": dispersion.get("spectral_bandwidth_relative_delta", ""),
        "proof_spectral_concentration_mean": dispersion.get("proof_spectral_concentration_mean", ""),
        "lift_spectral_concentration_mean": dispersion.get("lift_spectral_concentration_mean", ""),
        "strict_major_loss": dispersion.get("strict_major_loss", ""),
        "lift_loose_to_strict_major_recovery": dispersion.get("lift_loose_to_strict_major_recovery", ""),
        "shell_phase_coherence_drop": spatial.get("shell_phase_coherence_drop", ""),
        "radial_phase_coherence_drop": spatial.get("radial_phase_coherence_drop", ""),
        "angular_phase_coherence_drop": spatial.get("angular_phase_coherence_drop", ""),
        "phase_precompensation_classification": precomp_classification,
        "phase_precompensation_model_r2": ((precomp_summary.get("classification") or {}).get("checks") or {}).get("low_dimensional_model_r2", ""),
        "candidate_gate": "pending_classification",
    }


def _rejected_rows(summary: dict[str, Any], options: SourceSpectrumDesignAuditOptions) -> list[dict[str, Any]]:
    rows = [
        _rejected("frequency_sweep", "frequency", "high", "Forbidden; this audit keeps the carrier frequency fixed at 0.92."),
        _rejected("cutoff_tuning", "release_phase", "high", "Forbidden; this audit keeps the same cutoff/release phase and only changes temporal envelope shape."),
        _rejected("increase_total_work", "work", "high", "Forbidden; any future smooth-envelope candidate must match total work per physical source area."),
        _rejected("spatial_phase_precompensation", "spatial_phase", "medium", "The prior low-dimensional precompensation design classified as no safe correction."),
        _rejected("central_burst_or_resonator", "new_mechanism", "high", "Forbidden for this branch; this is only a source-spectrum design audit."),
    ]
    if _float(summary.get("smoothing_far_sideband_reduction_fraction")) < options.min_smoothing_sideband_reduction:
        rows.append(_rejected("smooth_temporal_envelope", "temporal_spectrum", "medium", "The smooth envelope does not reduce far sideband energy enough to justify a candidate."))
    return rows


def _candidate_payload(
    summary: dict[str, Any],
    classification: dict[str, Any],
    options: SourceSpectrumDesignAuditOptions,
    drive_frequency: float,
) -> dict[str, Any]:
    supported = classification["label"] == "source_spectrum_narrowing_candidate_supported"
    return {
        "classification": classification["label"],
        "recommended": supported,
        "reason": classification["reason"],
        "source": "prototype-3d-source-spectrum-design-audit",
        "candidate_type": "51^3 smooth temporal source envelope" if supported else "none",
        "grid_size": 51,
        "drive_frequency": drive_frequency,
        "cutoff": options.lift_cutoff,
        "target_release_phase": (options.lift_cutoff * drive_frequency) % 1.0,
        "envelope": "smooth_sin2_same_release",
        "total_work_policy": "match current work per physical source area",
        "frequency_changed": False,
        "cutoff_phase_changed": False,
        "spatial_phase_precompensation": False,
        "expected_source_far_sideband_reduction_fraction": summary.get("smoothing_far_sideband_reduction_fraction"),
        "expected_source_bandwidth_ratio": summary.get("smooth_to_hard_source_bandwidth_ratio"),
        "required_controls_if_run_later": [
            "51^3 original hard-cutoff source at same cutoff/phase",
            "51^3 smooth-envelope wrong-phase or over-smoothed control",
        ],
    }


def _write_report(
    path: Path,
    control_id: str,
    summary: dict[str, Any],
    source_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    candidate: dict[str, Any],
    classification: dict[str, Any],
    options: SourceSpectrumDesignAuditOptions,
) -> None:
    lines = [
        f"# 3D Source Spectrum Design Audit: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only source-spectrum audit for the failed `51^3` release-phase lift. This command does not run physics and does not tune cutoff, frequency, spatial phase, defects, resonators, central burst, or medium properties.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Candidate recommended: `{candidate.get('recommended')}`",
        "",
        "## Summary",
        "",
        "| Current envelope | Smooth envelope | Modal bandwidth growth | Max coherence drop | Hard far sideband | Smooth far sideband | Sideband reduction | Source bandwidth ratio |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| "
        f"{summary.get('current_source_envelope')} | "
        f"{summary.get('proposed_smooth_envelope')} | "
        f"{_format(summary.get('observed_modal_bandwidth_relative_delta'))} | "
        f"{_format(max(_float(summary.get('shell_phase_coherence_drop')), _float(summary.get('radial_phase_coherence_drop')), _float(summary.get('angular_phase_coherence_drop'))))} | "
        f"{_format(summary.get('hard_far_sideband_fraction_mean'))} | "
        f"{_format(summary.get('smooth_far_sideband_fraction_mean'))} | "
        f"{_format(summary.get('smoothing_far_sideband_reduction_fraction'))} | "
        f"{_format(summary.get('smooth_to_hard_source_bandwidth_ratio'))} |",
        "",
        "## Source Window Comparison",
        "",
        "| Role | Envelope | Cutoff | Release Phase | Bandwidth | Far Sideband | Scale |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in source_rows:
        lines.append(
            "| "
            f"{row.get('role')} | {row.get('envelope_kind')} | "
            f"{_format(row.get('cutoff'))} | "
            f"{_format(row.get('release_phase_cycles'))} | "
            f"{_format(row.get('source_bandwidth'))} | "
            f"{_format(row.get('far_sideband_fraction'))} | "
            f"{_format(row.get('work_proxy_scale'))} |"
        )
    lines.extend(
        [
            "",
            "## Candidate JSON",
            "",
            "```json",
            json.dumps(candidate, indent=2, sort_keys=True),
            "```",
            "",
            "## Rejected Options",
            "",
            "| Option | Basis | Risk | Reason |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in rejected_rows:
        lines.append(f"| {row.get('option')} | {row.get('basis')} | {row.get('risk_level')} | {row.get('reason')} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Files",
            "",
            "- `source_spectrum_design_audit_report.md`",
            "- `source_spectrum_summary.csv`",
            "- `source_envelope_spectrum.csv`",
            "- `smooth_envelope_candidate.json`",
            "- `rejected_source_spectrum_options.csv`",
            "",
            "## Guardrail",
            "",
            "This report can justify at most one future `51^3` smooth-envelope candidate plus two controls. It does not itself authorize broad source-shape sweeps, cutoff tuning, frequency sweeps, or spatial phase masks.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "source_spectrum_narrowing_candidate_supported":
        return "A smoother same-release temporal envelope is a plausible final mechanism-derived scale-lift candidate because it strongly reduces source sidebands while preserving the known carrier and release phase. Do not run it as a sweep."
    if label == "source_spectrum_not_supported_archive":
        return "The source-spectrum route is not supported; archive the passive scale-lift branch unless a genuinely new mechanism appears."
    return "The evidence is incomplete or inconsistent; do not launch a smooth-envelope candidate from this audit alone."


def _rows_by_role_and_kind(rows: list[dict[str, Any]], kind: str) -> dict[str, dict[str, Any]]:
    return {str(row.get("role")): row for row in rows if str(row.get("envelope_kind")) == kind}


def _rejected(option: str, basis: str, risk: str, reason: str) -> dict[str, Any]:
    return {"option": option, "basis": basis, "status": "rejected", "risk_level": risk, "reason": reason}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _relative_delta(left: float, right: float) -> float:
    return (left - right) / max(abs(right), EPSILON)


def _mean(values: list[Any]) -> float:
    parsed = [_float(value) for value in values if value not in (None, "")]
    return float(np.mean(parsed)) if parsed else 0.0


def _float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _summary_fields() -> list[str]:
    return [
        "summary",
        "source_spectrum_design_audit_classification",
        "current_source_envelope",
        "proposed_smooth_envelope",
        "drive_frequency",
        "proof_cutoff",
        "lift_cutoff",
        "proof_release_phase_cycles",
        "lift_release_phase_cycles",
        "dt",
        "hard_source_bandwidth_mean",
        "smooth_source_bandwidth_mean",
        "smooth_to_hard_source_bandwidth_ratio",
        "hard_far_sideband_fraction_mean",
        "smooth_far_sideband_fraction_mean",
        "smoothing_far_sideband_reduction_fraction",
        "hard_source_bandwidth_relative_delta_41_to_51",
        "hard_far_sideband_relative_delta_41_to_51",
        "same_modal_band",
        "observed_modal_bandwidth_relative_delta",
        "proof_spectral_concentration_mean",
        "lift_spectral_concentration_mean",
        "strict_major_loss",
        "lift_loose_to_strict_major_recovery",
        "shell_phase_coherence_drop",
        "radial_phase_coherence_drop",
        "angular_phase_coherence_drop",
        "phase_precompensation_classification",
        "phase_precompensation_model_r2",
        "candidate_gate",
    ]


def _spectrum_fields() -> list[str]:
    return [
        "role",
        "envelope_kind",
        "source_spectrum_design_audit_classification",
        "cutoff",
        "drive_frequency",
        "frequency",
        "offset_from_carrier",
        "abs_offset_from_carrier",
        "normalized_power",
        "inside_natural_band",
        "inside_far_sideband_threshold",
    ]


def _rejected_fields() -> list[str]:
    return ["option", "basis", "source_spectrum_design_audit_classification", "status", "risk_level", "reason"]
