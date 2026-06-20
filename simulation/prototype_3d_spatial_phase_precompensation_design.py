"""Read-only low-dimensional phase-precompensation design for the 51^3 lift."""

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
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_SPATIAL_PHASE_ROOT = "runs/spatial_phase_instrumentation_3d_20260620_170518"
FACE_NAMES = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")


@dataclass(frozen=True)
class SpatialPhasePrecompensationDesignOptions:
    """Options for read-only low-dimensional phase-error design."""

    output_root: str = "runs"
    spatial_phase_root: str = DEFAULT_SPATIAL_PHASE_ROOT
    angular_harmonic_m: int = 4
    ridge_lambda: float = 0.01
    min_matched_sector_samples: int = 96
    min_model_r2: float = 0.12
    max_peak_global_phase_std: float = 0.35
    max_global_phase_offset: float = 0.35
    max_face_phase_offset: float = 0.25
    max_cubic_multiplier_delta: float = 0.20
    max_angular_harmonic_amplitude: float = 0.25
    max_release_phase_nudge: float = 0.004
    baseline_cubic_sign: float = -1.0
    baseline_drive_frequency: float = 0.92
    baseline_target_release_phase: float = 0.5071
    baseline_cutoff: float = 17.9425


def run_3d_spatial_phase_precompensation_design(
    *,
    options: SpatialPhasePrecompensationDesignOptions | None = None,
) -> dict[str, Any]:
    """Infer a constrained phase-precompensation candidate from captured spatial frames."""

    options = options or SpatialPhasePrecompensationDesignOptions()
    control_id = datetime.now().strftime("spatial_phase_precomp_design_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)
    spatial_root = Path(options.spatial_phase_root)

    angular_rows = _read_csv(spatial_root / "angular_shell_phase_coherence.csv")
    radial_rows = _read_csv(spatial_root / "radial_shell_phase_frames.csv")
    comparison_rows = _read_csv(spatial_root / "spatial_phase_41_vs_51_comparison.csv")
    frame_rows = _read_csv(spatial_root / "spatial_phase_frame_index.csv")

    sector_samples = _sector_phase_error_samples(angular_rows, options)
    model = _fit_low_dimensional_model(sector_samples, options)
    per_peak_rows = _per_peak_mode_rows(sector_samples, options)
    radial_mode_rows = _radial_mode_rows(radial_rows)
    frame_mode_rows = _frame_mode_rows(frame_rows)
    summary_row = _summary_mode_row(model, sector_samples, per_peak_rows, comparison_rows, options)
    mode_rows = [summary_row, *model["coefficient_rows"], *per_peak_rows, *radial_mode_rows, *frame_mode_rows]
    rejected_rows = _rejected_rows(model, summary_row, options)
    classification = classify_spatial_phase_precompensation_design(summary_row, rejected_rows, options)
    candidate = _candidate_payload(classification, model, summary_row, options)

    for row_set in (mode_rows, rejected_rows):
        for row in row_set:
            row["phase_precompensation_design_classification"] = classification["label"]

    report_path = root / "phase_precompensation_design_report.md"
    modes_csv = root / "phase_error_modes.csv"
    candidate_json = root / "recommended_candidate.json"
    rejected_csv = root / "rejected_overfit_corrections.csv"
    _write_csv(modes_csv, mode_rows, _mode_fields())
    _write_csv(rejected_csv, rejected_rows, _rejected_fields())
    save_json(candidate_json, candidate)
    _write_report(report_path, control_id, summary_row, mode_rows, rejected_rows, candidate, classification, options)
    save_json(
        root / "spatial_phase_precompensation_design_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "spatial_phase_root": str(spatial_root),
            "summary_row": summary_row,
            "recommended_candidate": candidate,
            "mode_rows": mode_rows,
            "rejected_rows": rejected_rows,
            "report_path": str(report_path),
            "modes_csv": str(modes_csv),
            "recommended_candidate_json": str(candidate_json),
            "rejected_csv": str(rejected_csv),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_row": summary_row,
        "mode_rows": mode_rows,
        "rejected_rows": rejected_rows,
        "recommended_candidate": candidate,
        "report_path": str(report_path),
        "modes_csv": str(modes_csv),
        "recommended_candidate_json": str(candidate_json),
        "rejected_csv": str(rejected_csv),
        "path": str(root),
    }


def classify_spatial_phase_precompensation_design(
    summary: dict[str, Any],
    rejected_rows: list[dict[str, Any]] | None = None,
    options: SpatialPhasePrecompensationDesignOptions | None = None,
) -> dict[str, Any]:
    """Classify whether a low-dimensional precompensation candidate is safe to try."""

    options = options or SpatialPhasePrecompensationDesignOptions()
    matched = _int(summary.get("matched_sector_samples"))
    model_r2 = _float(summary.get("low_dimensional_model_r2"))
    peak_std = _float(summary.get("per_peak_global_phase_error_std_radians"))
    global_offset = abs(_float(summary.get("recommended_global_phase_offset_radians")))
    max_face = abs(_float(summary.get("recommended_max_face_phase_offset_radians")))
    cubic_delta = abs(_float(summary.get("recommended_cubic_multiplier_delta")))
    harmonic = abs(_float(summary.get("recommended_angular_harmonic_amplitude_radians")))
    release_nudge = abs(_float(summary.get("recommended_release_phase_nudge_cycles")))
    unsafe_allowed_rejections = [
        row
        for row in (rejected_rows or [])
        if str(row.get("status")) == "rejected"
        and str(row.get("risk_level")) == "high"
        and str(row.get("correction")) in {"low_dimensional_candidate", "release_phase_nudge"}
    ]
    safe_magnitude = (
        global_offset <= options.max_global_phase_offset
        and max_face <= options.max_face_phase_offset
        and cubic_delta <= options.max_cubic_multiplier_delta
        and harmonic <= options.max_angular_harmonic_amplitude
        and release_nudge <= options.max_release_phase_nudge
    )
    temporally_stable = peak_std <= options.max_peak_global_phase_std
    checks = {
        "matched_sector_samples": matched,
        "low_dimensional_model_r2": model_r2,
        "per_peak_global_phase_error_std_radians": peak_std,
        "safe_magnitude": safe_magnitude,
        "temporally_stable": temporally_stable,
        "unsafe_allowed_rejections": len(unsafe_allowed_rejections),
        "recommended_global_phase_offset_radians": _float(summary.get("recommended_global_phase_offset_radians")),
        "recommended_cubic_phase_strength_multiplier": _float(summary.get("recommended_cubic_phase_strength_multiplier")),
        "recommended_angular_harmonic_amplitude_radians": _float(summary.get("recommended_angular_harmonic_amplitude_radians")),
    }
    if matched < options.min_matched_sector_samples:
        return {
            "label": "inconclusive_phase_design",
            "reason": "Too few matched shell-sector phase samples were available for a stable low-dimensional correction.",
            "checks": checks,
        }
    if model_r2 >= options.min_model_r2 and temporally_stable and safe_magnitude:
        return {
            "label": "phase_precomp_candidate_supported",
            "reason": "A stable low-dimensional phase-error model explains enough of the 51^3 coherence loss to justify one precompensated candidate.",
            "checks": checks,
        }
    if not temporally_stable or model_r2 < options.min_model_r2:
        return {
            "label": "no_safe_phase_correction",
            "reason": "The shell phase error is not captured by a stable low-dimensional boundary correction.",
            "checks": checks,
        }
    if unsafe_allowed_rejections:
        return {
            "label": "overfit_risk_too_high",
            "reason": "The only plausible correction would exceed the allowed low-dimensional first-pass bounds.",
            "checks": checks,
        }
    return {
        "label": "inconclusive_phase_design",
        "reason": "The phase-error model is marginal or the correction magnitude is outside the safe first-pass bounds.",
        "checks": checks,
    }


def _sector_phase_error_samples(rows: list[dict[str, Any]], options: SpatialPhasePrecompensationDesignOptions) -> list[dict[str, Any]]:
    proof = [
        row
        for row in rows
        if _int(row.get("grid_size")) == 41 and str(row.get("polar_bin")) != "octant"
    ]
    lift = {
        (str(row.get("peak_rank")), str(row.get("polar_bin")), str(row.get("theta_bin"))): row
        for row in rows
        if _int(row.get("grid_size")) == 51 and str(row.get("polar_bin")) != "octant"
    }
    samples = []
    for row in proof:
        match = lift.get((str(row.get("peak_rank")), str(row.get("polar_bin")), str(row.get("theta_bin"))))
        if match is None:
            continue
        polar_bin = _int(row.get("polar_bin"))
        theta_bin = _int(row.get("theta_bin"))
        polar_bins = 4
        theta_bins = 8
        polar = (polar_bin + 0.5) / polar_bins * math.pi
        theta = (theta_bin + 0.5) / theta_bins * 2.0 * math.pi
        x = math.sin(polar) * math.cos(theta)
        y = math.sin(polar) * math.sin(theta)
        z = math.cos(polar)
        face_weights = _face_basis(x, y, z)
        cubic = (x**4 + y**4 + z**4) - 0.6
        proof_phase = _float(row.get("phase_mean_cycles"))
        lift_phase = _float(match.get("phase_mean_cycles"))
        error_cycles = _cycle_delta(lift_phase, proof_phase)
        proof_energy = max(_float(row.get("shell_energy")), 0.0)
        lift_energy = max(_float(match.get("shell_energy")), 0.0)
        weight = math.sqrt(proof_energy * lift_energy) * min(
            max(_float(row.get("phase_coherence")), 0.0),
            max(_float(match.get("phase_coherence")), 0.0),
        )
        samples.append(
            {
                "peak_rank": _int(row.get("peak_rank")),
                "polar_bin": polar_bin,
                "theta_bin": theta_bin,
                "theta_radians": theta,
                "polar_radians": polar,
                "x": x,
                "y": y,
                "z": z,
                "proof_phase_cycles": proof_phase,
                "lift_phase_cycles": lift_phase,
                "phase_error_cycles": error_cycles,
                "phase_error_radians": error_cycles * 2.0 * math.pi,
                "weight": weight,
                "cubic_basis_raw": cubic,
                **{f"face_basis_{face}": face_weights[index] for index, face in enumerate(FACE_NAMES)},
            }
        )
    _normalize_sample_basis(samples)
    return samples


def _fit_low_dimensional_model(
    samples: list[dict[str, Any]],
    options: SpatialPhasePrecompensationDesignOptions,
) -> dict[str, Any]:
    if not samples:
        return {
            "r2": 0.0,
            "weighted_rmse": 0.0,
            "coefficients": np.zeros(10, dtype=float),
            "coefficient_rows": [],
        }
    x_rows = []
    y = []
    weights = []
    for sample in samples:
        theta = _float(sample.get("theta_radians"))
        x_rows.append(
            [
                1.0,
                *[_float(sample.get(f"face_basis_{face}")) for face in FACE_NAMES],
                _float(sample.get("cubic_basis")),
                math.cos(options.angular_harmonic_m * theta),
                math.sin(options.angular_harmonic_m * theta),
            ]
        )
        y.append(_float(sample.get("phase_error_radians")))
        weights.append(max(_float(sample.get("weight")), EPSILON))
    x = np.asarray(x_rows, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    w_arr = np.asarray(weights, dtype=float)
    scaled_w = np.sqrt(w_arr / max(float(np.mean(w_arr)), EPSILON))
    xw = x * scaled_w[:, None]
    yw = y_arr * scaled_w
    ridge = float(options.ridge_lambda) * np.eye(x.shape[1])
    coefficients = np.linalg.solve(xw.T @ xw + ridge, xw.T @ yw)
    pred = x @ coefficients
    mean_y = float(np.average(y_arr, weights=w_arr))
    ss_res = float(np.sum(w_arr * (y_arr - pred) ** 2))
    ss_tot = float(np.sum(w_arr * (y_arr - mean_y) ** 2))
    r2 = float(1.0 - ss_res / max(ss_tot, EPSILON))
    rmse = math.sqrt(ss_res / max(float(np.sum(w_arr)), EPSILON))
    face_offsets = _center_face_offsets(coefficients[1:7])
    cubic_delta = coefficients[7] / (options.baseline_cubic_sign * 0.5 * math.pi)
    cubic_multiplier = 1.0 + cubic_delta
    harmonic_cos = float(coefficients[8])
    harmonic_sin = float(coefficients[9])
    harmonic_amplitude = math.hypot(harmonic_cos, harmonic_sin)
    harmonic_phase = math.atan2(-harmonic_sin, harmonic_cos)
    global_offset = float(coefficients[0] + float(np.mean(coefficients[1:7])))
    coefficient_rows = [
        _mode("global_phase_offset", "global", global_offset, "radians", "candidate", "weighted intercept plus mean face offset"),
        _mode("global_phase_offset_cycles", "global", global_offset / (2.0 * math.pi), "cycles", "candidate", "same global correction in cycles"),
        _mode("cubic_phase_strength_multiplier", "cubic", cubic_multiplier, "multiplier", "candidate", "low-dimensional cubic coefficient mapped to source multiplier"),
        _mode("cubic_phase_strength_delta", "cubic", cubic_delta, "multiplier_delta", "candidate", "delta from baseline sign-flip cubic strength"),
        _mode("angular_harmonic_m", "angular_harmonic", options.angular_harmonic_m, "integer", "candidate", "simple angular harmonic order"),
        _mode("angular_harmonic_amplitude", "angular_harmonic", harmonic_amplitude, "radians", "candidate", "amplitude of cosine/sine phase correction"),
        _mode("angular_harmonic_phase", "angular_harmonic", harmonic_phase, "radians", "candidate", "phase of angular harmonic correction"),
    ]
    for index, face in enumerate(FACE_NAMES):
        coefficient_rows.append(
            _mode(f"face_offset_{face}", "per_face", float(face_offsets[index]), "radians", "candidate", "centered per-face offset")
        )
    return {
        "r2": r2,
        "weighted_rmse": rmse,
        "coefficients": coefficients,
        "face_offsets": {face: float(face_offsets[index]) for index, face in enumerate(FACE_NAMES)},
        "global_phase_offset_radians": global_offset,
        "cubic_phase_strength_multiplier": float(cubic_multiplier),
        "cubic_multiplier_delta": float(cubic_delta),
        "angular_harmonic_m": options.angular_harmonic_m,
        "angular_harmonic_amplitude_radians": float(harmonic_amplitude),
        "angular_harmonic_phase_radians": float(harmonic_phase),
        "coefficient_rows": coefficient_rows,
    }


def _per_peak_mode_rows(samples: list[dict[str, Any]], options: SpatialPhasePrecompensationDesignOptions) -> list[dict[str, Any]]:
    rows = []
    by_peak: dict[int, list[dict[str, Any]]] = {}
    for sample in samples:
        by_peak.setdefault(_int(sample.get("peak_rank")), []).append(sample)
    peak_errors = []
    for peak in sorted(by_peak):
        subset = by_peak[peak]
        weights = [max(_float(sample.get("weight")), EPSILON) for sample in subset]
        errors = [_float(sample.get("phase_error_radians")) for sample in subset]
        mean_error = float(np.average(errors, weights=weights)) if errors else 0.0
        peak_errors.append(mean_error)
        rows.append(
            _mode(
                f"per_peak_global_error_return_{peak:02d}",
                "temporal_phase_drift",
                mean_error,
                "radians",
                "diagnostic",
                f"weighted mean 41^3-minus-51^3 sector phase error at return {peak}",
            )
        )
    rows.append(
        _mode(
            "per_peak_global_phase_error_std",
            "temporal_phase_drift",
            float(np.std(peak_errors)) if peak_errors else 0.0,
            "radians",
            "stability_gate",
            "standard deviation of per-return global phase error",
        )
    )
    release_nudge = 0.0
    if peak_errors and float(np.std(peak_errors)) <= options.max_peak_global_phase_std:
        release_nudge = float(np.mean(peak_errors)) / (2.0 * math.pi)
    rows.append(
        _mode(
            "release_phase_nudge",
            "temporal_phase_drift",
            release_nudge,
            "cycles",
            "candidate" if abs(release_nudge) > EPSILON else "rejected",
            "small release nudge is allowed only if per-return phase error is stable",
        )
    )
    return rows


def _radial_mode_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    by_grid: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_grid.setdefault(_int(row.get("grid_size")), []).append(row)
    for grid, subset in sorted(by_grid.items()):
        out.append(
            _mode(
                f"radial_phase_coherence_mean_{grid}",
                "radial_phase",
                _mean([row.get("phase_coherence") for row in subset]),
                "coherence",
                "diagnostic",
                "mean radial-bin phase coherence across captured return frames",
            )
        )
    return out


def _frame_mode_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    by_grid: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_grid.setdefault(_int(row.get("grid_size")), []).append(row)
    for grid, subset in sorted(by_grid.items()):
        out.append(
            _mode(
                f"shell_phase_coherence_mean_{grid}",
                "shell_phase",
                _mean([row.get("shell_phase_coherence") for row in subset]),
                "coherence",
                "diagnostic",
                "mean shell phase coherence across captured return frames",
            )
        )
    return out


def _summary_mode_row(
    model: dict[str, Any],
    samples: list[dict[str, Any]],
    per_peak_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    options: SpatialPhasePrecompensationDesignOptions,
) -> dict[str, Any]:
    per_peak_std = next(
        (_float(row.get("value")) for row in per_peak_rows if row.get("mode") == "per_peak_global_phase_error_std"),
        0.0,
    )
    release_nudge = next(
        (_float(row.get("value")) for row in per_peak_rows if row.get("mode") == "release_phase_nudge"),
        0.0,
    )
    comparison = comparison_rows[0] if comparison_rows else {}
    max_face = max((abs(value) for value in (model.get("face_offsets") or {}).values()), default=0.0)
    return {
        "mode": "low_dimensional_phase_design_summary",
        "basis": "summary",
        "value": model.get("r2", 0.0),
        "units": "r2",
        "status": "summary",
        "reason": "weighted low-dimensional fit over matched shell-sector phase errors",
        "matched_sector_samples": len(samples),
        "low_dimensional_model_r2": model.get("r2", 0.0),
        "low_dimensional_weighted_rmse_radians": model.get("weighted_rmse", 0.0),
        "per_peak_global_phase_error_std_radians": per_peak_std,
        "recommended_global_phase_offset_radians": model.get("global_phase_offset_radians", 0.0),
        "recommended_max_face_phase_offset_radians": max_face,
        "recommended_cubic_phase_strength_multiplier": model.get("cubic_phase_strength_multiplier", 1.0),
        "recommended_cubic_multiplier_delta": model.get("cubic_multiplier_delta", 0.0),
        "recommended_angular_harmonic_m": model.get("angular_harmonic_m", options.angular_harmonic_m),
        "recommended_angular_harmonic_amplitude_radians": model.get("angular_harmonic_amplitude_radians", 0.0),
        "recommended_angular_harmonic_phase_radians": model.get("angular_harmonic_phase_radians", 0.0),
        "recommended_release_phase_nudge_cycles": release_nudge,
        "baseline_cutoff": options.baseline_cutoff,
        "baseline_target_release_phase": options.baseline_target_release_phase,
        "shell_phase_coherence_drop": comparison.get("shell_phase_coherence_drop", ""),
        "radial_phase_coherence_drop": comparison.get("radial_phase_coherence_drop", ""),
        "angular_phase_coherence_drop": comparison.get("angular_phase_coherence_drop", ""),
        "strict_major_loss": comparison.get("strict_major_loss", ""),
        "strict_refocus_loss": comparison.get("strict_refocus_loss", ""),
    }


def _rejected_rows(
    model: dict[str, Any],
    summary: dict[str, Any],
    options: SpatialPhasePrecompensationDesignOptions,
) -> list[dict[str, Any]]:
    rows = [
        {
            "correction": "cell_by_cell_phase_mask",
            "basis": "per_node",
            "status": "rejected",
            "risk_level": "high",
            "reason": "Forbidden by protocol and would overfit the failed 51^3 frame evidence.",
        },
        {
            "correction": "broad_cutoff_tuning",
            "basis": "cutoff_sweep",
            "status": "rejected",
            "risk_level": "high",
            "reason": "Forbidden; only a tiny release-phase nudge is allowed and only if per-return phase drift is stable.",
        },
        {
            "correction": "frequency_sweep",
            "basis": "frequency",
            "status": "rejected",
            "risk_level": "high",
            "reason": "Forbidden; the modal band test keeps frequency fixed at 0.92.",
        },
        {
            "correction": "high_order_angular_harmonics",
            "basis": "angular_harmonic_m_gt_4",
            "status": "rejected",
            "risk_level": "medium",
            "reason": "A first-pass correction may use only one simple angular harmonic.",
        },
    ]
    if _float(summary.get("per_peak_global_phase_error_std_radians")) > options.max_peak_global_phase_std:
        rows.append(
            {
                "correction": "release_phase_nudge",
                "basis": "temporal_phase",
                "status": "rejected",
                "risk_level": "medium",
                "reason": "Per-return global phase error is not stable enough to justify changing cutoff/release phase.",
            }
        )
    if _float(summary.get("low_dimensional_model_r2")) < options.min_model_r2:
        rows.append(
            {
                "correction": "low_dimensional_candidate",
                "basis": "global_face_cubic_harmonic",
                "status": "rejected",
                "risk_level": "medium",
                "reason": "Allowed low-dimensional modes do not explain enough matched shell-sector phase error.",
            }
        )
    return rows


def _candidate_payload(
    classification: dict[str, Any],
    model: dict[str, Any],
    summary: dict[str, Any],
    options: SpatialPhasePrecompensationDesignOptions,
) -> dict[str, Any]:
    supported = classification["label"] == "phase_precomp_candidate_supported"
    release_nudge = _float(summary.get("recommended_release_phase_nudge_cycles")) if supported else 0.0
    target_phase = options.baseline_target_release_phase + release_nudge
    cutoff = (16.0 + target_phase) / max(options.baseline_drive_frequency, EPSILON)
    return {
        "classification": classification["label"],
        "recommended": supported,
        "reason": classification["reason"],
        "source": "prototype-3d-spatial-phase-precompensation-design",
        "spatial_phase_root": options.spatial_phase_root,
        "grid_size": 51,
        "drive_frequency": options.baseline_drive_frequency,
        "baseline_cutoff": options.baseline_cutoff,
        "baseline_target_release_phase": options.baseline_target_release_phase,
        "target_release_phase": target_phase,
        "cutoff": cutoff,
        "correction_basis": "global + per-face + cubic-strength + angular-harmonic",
        "global_phase_offset_radians": model.get("global_phase_offset_radians", 0.0) if supported else 0.0,
        "face_phase_offsets_radians": model.get("face_offsets", {}) if supported else {face: 0.0 for face in FACE_NAMES},
        "cubic_phase_strength_multiplier": model.get("cubic_phase_strength_multiplier", 1.0) if supported else 1.0,
        "angular_harmonic_m": model.get("angular_harmonic_m", options.angular_harmonic_m),
        "angular_harmonic_amplitude_radians": model.get("angular_harmonic_amplitude_radians", 0.0) if supported else 0.0,
        "angular_harmonic_phase_radians": model.get("angular_harmonic_phase_radians", 0.0) if supported else 0.0,
        "release_phase_nudge_cycles": release_nudge,
        "model_r2": summary.get("low_dimensional_model_r2"),
        "per_peak_global_phase_error_std_radians": summary.get("per_peak_global_phase_error_std_radians"),
        "forbidden": [
            "cell_by_cell_phase_mask",
            "broad_cutoff_tuning",
            "frequency_sweep",
            "new_resonator",
            "central_burst",
            "defect_changes",
            "medium_shaping",
        ],
    }


def _normalize_sample_basis(samples: list[dict[str, Any]]) -> None:
    max_cubic = max((abs(_float(sample.get("cubic_basis_raw"))) for sample in samples), default=1.0)
    for sample in samples:
        sample["cubic_basis"] = _float(sample.get("cubic_basis_raw")) / max(max_cubic, EPSILON)


def _face_basis(x: float, y: float, z: float) -> list[float]:
    values = [max(-x, 0.0), max(x, 0.0), max(-y, 0.0), max(y, 0.0), max(-z, 0.0), max(z, 0.0)]
    total = sum(values)
    if total <= EPSILON:
        return [1.0 / 6.0] * 6
    return [value / total for value in values]


def _center_face_offsets(values: np.ndarray) -> np.ndarray:
    centered = np.asarray(values, dtype=float) - float(np.mean(values))
    return centered


def _mode(mode: str, basis: str, value: Any, units: str, status: str, reason: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "basis": basis,
        "value": value,
        "units": units,
        "status": status,
        "reason": reason,
    }


def _write_report(
    path: Path,
    control_id: str,
    summary: dict[str, Any],
    mode_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    candidate: dict[str, Any],
    classification: dict[str, Any],
    options: SpatialPhasePrecompensationDesignOptions,
) -> None:
    lines = [
        f"# 3D Spatial Phase Precompensation Design: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only low-dimensional phase-error design from the captured `41^3` proof-row and `51^3` failed-lift spatial phase frames. This command does not run physics and does not fit cell-by-cell phase masks.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Recommended candidate: `{candidate.get('recommended')}`",
        "",
        "## Fit Summary",
        "",
        "| Samples | Model R2 | RMSE | Per-Peak Phase Std | Global Offset | Max Face Offset | Cubic Mult | Harmonic Amp | Release Nudge |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| "
        f"{summary.get('matched_sector_samples')} | "
        f"{_format(summary.get('low_dimensional_model_r2'))} | "
        f"{_format(summary.get('low_dimensional_weighted_rmse_radians'))} | "
        f"{_format(summary.get('per_peak_global_phase_error_std_radians'))} | "
        f"{_format(summary.get('recommended_global_phase_offset_radians'))} | "
        f"{_format(summary.get('recommended_max_face_phase_offset_radians'))} | "
        f"{_format(summary.get('recommended_cubic_phase_strength_multiplier'))} | "
        f"{_format(summary.get('recommended_angular_harmonic_amplitude_radians'))} | "
        f"{_format(summary.get('recommended_release_phase_nudge_cycles'))} |",
        "",
        "## Candidate JSON",
        "",
        "```json",
        json.dumps(candidate, indent=2, sort_keys=True),
        "```",
        "",
        "## Rejected Overfit Corrections",
        "",
        "| Correction | Basis | Risk | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in rejected_rows:
        lines.append(f"| {row.get('correction')} | {row.get('basis')} | {row.get('risk_level')} | {row.get('reason')} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Files",
            "",
            "- `phase_precompensation_design_report.md`",
            "- `phase_error_modes.csv`",
            "- `recommended_candidate.json`",
            "- `rejected_overfit_corrections.csv`",
            "",
            "## Guardrail",
            "",
            "If the classification is not `phase_precomp_candidate_supported`, do not run `prototype-3d-phase-precompensated-resolution-lift` from this design.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "phase_precomp_candidate_supported":
        return "A constrained low-dimensional correction is stable enough to justify one `51^3` candidate plus two controls."
    if label == "no_safe_phase_correction":
        return "The captured phase error is real, but it is not represented by a stable global/face/cubic/harmonic correction. Do not run the phase-precompensated physics candidate yet."
    if label == "overfit_risk_too_high":
        return "The tempting correction would rely on unstable or overly specific phase structure. Treat this as a finite-resolution warning until a simpler mechanism appears."
    return "The frame evidence is insufficient or marginal; inspect the mode table before proposing any source correction."


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _cycle_delta(left: Any, right: Any) -> float:
    return (_float(right) - _float(left) + 0.5) % 1.0 - 0.5


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


def _int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _mode_fields() -> list[str]:
    return [
        "mode",
        "basis",
        "phase_precompensation_design_classification",
        "value",
        "units",
        "status",
        "reason",
        "matched_sector_samples",
        "low_dimensional_model_r2",
        "low_dimensional_weighted_rmse_radians",
        "per_peak_global_phase_error_std_radians",
        "recommended_global_phase_offset_radians",
        "recommended_max_face_phase_offset_radians",
        "recommended_cubic_phase_strength_multiplier",
        "recommended_cubic_multiplier_delta",
        "recommended_angular_harmonic_m",
        "recommended_angular_harmonic_amplitude_radians",
        "recommended_angular_harmonic_phase_radians",
        "recommended_release_phase_nudge_cycles",
        "baseline_cutoff",
        "baseline_target_release_phase",
        "shell_phase_coherence_drop",
        "radial_phase_coherence_drop",
        "angular_phase_coherence_drop",
        "strict_major_loss",
        "strict_refocus_loss",
    ]


def _rejected_fields() -> list[str]:
    return [
        "correction",
        "basis",
        "phase_precompensation_design_classification",
        "status",
        "risk_level",
        "reason",
    ]
