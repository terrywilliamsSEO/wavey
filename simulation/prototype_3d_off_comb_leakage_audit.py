"""Read-only off-comb leakage audit for 41^3 proof versus 51^3 source controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .prototype_3d import EPSILON
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_PROOF_ROOT = "runs/release_phase_proof_pack_3d_20260619_234039"
DEFAULT_LIFT_ROOT = "runs/release_phase_resolution_lift_3d_20260620_091834"
DEFAULT_SPATIAL_PHASE_ROOT = "runs/spatial_phase_instrumentation_3d_20260620_170518"
DEFAULT_SMOOTH_ROOT = "runs/smooth_envelope_resolution_lift_3d_20260620_192501"
DEFAULT_PHASE_CONJUGATE_ROOT = "runs/boundary_phase_conjugate_3d_20260620_212918"
DEFAULT_MODAL_SPARSITY_ROOT = "runs/modal_sparsity_audit_3d_20260620_231602"
DEFAULT_RETURN_FAMILY_GATE_ROOT = "runs/return_family_gate_audit_3d_20260621_082543"


@dataclass(frozen=True)
class OffCombLeakageAuditOptions:
    """Options for the read-only off-comb leakage localization audit."""

    output_root: str = "runs"
    proof_root: str = DEFAULT_PROOF_ROOT
    lift_root: str = DEFAULT_LIFT_ROOT
    spatial_phase_root: str = DEFAULT_SPATIAL_PHASE_ROOT
    smooth_root: str = DEFAULT_SMOOTH_ROOT
    phase_conjugate_root: str = DEFAULT_PHASE_CONJUGATE_ROOT
    modal_sparsity_root: str = DEFAULT_MODAL_SPARSITY_ROOT
    return_family_gate_root: str = DEFAULT_RETURN_FAMILY_GATE_ROOT
    shell_window_center_radius: float = 7.0
    shell_window_half_width: float = 2.0
    radial_ratio_support_delta: float = 0.12
    angular_coherence_drop_threshold: float = 0.10
    outer_correlation_threshold: float = 0.20
    modal_sideband_delta_threshold: float = 0.03
    spatial_pattern_delta_threshold: float = 0.08
    source_channel_count_for_mixed: int = 2


def run_3d_off_comb_leakage_audit(
    *,
    options: OffCombLeakageAuditOptions | None = None,
) -> dict[str, Any]:
    """Locate likely leakage channels using saved artifacts only."""

    options = options or OffCombLeakageAuditOptions()
    control_id = datetime.now().strftime("off_comb_leakage_audit_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    records = _load_records(options)
    if not records:
        classification = classify_off_comb_leakage_audit([], options)
        return _write_empty_outputs(root, control_id, classification)

    summary_rows: list[dict[str, Any]] = []
    radial_rows: list[dict[str, Any]] = []
    angular_rows: list[dict[str, Any]] = []
    outer_rows: list[dict[str, Any]] = []
    modal_rows: list[dict[str, Any]] = []
    pattern_rows: list[dict[str, Any]] = []

    for record in records:
        result = _diagnose_record(record, options)
        summary_rows.append(result["summary"])
        radial_rows.extend(result["radial_rows"])
        angular_rows.extend(result["angular_rows"])
        outer_rows.append(result["outer_row"])
        modal_rows.append(result["modal_row"])
        pattern_rows.append(result["pattern_row"])

    classification = classify_off_comb_leakage_audit(summary_rows, options)
    for collection in (summary_rows, radial_rows, angular_rows, outer_rows, modal_rows, pattern_rows):
        for row in collection:
            row["off_comb_leakage_classification"] = classification["label"]

    summary_csv = root / "off_comb_leakage_summary.csv"
    radial_csv = root / "radial_leakage_by_window.csv"
    angular_csv = root / "angular_leakage_by_sector.csv"
    outer_csv = root / "outer_recycling_correlation.csv"
    modal_csv = root / "modal_sideband_leakage.csv"
    pattern_csv = root / "spatial_pattern_leakage.csv"
    report_path = root / "off_comb_leakage_report.md"
    summary_json = root / "off_comb_leakage_summary.json"
    plots = {
        "radial_leakage_plot": root / "radial_leakage_plot.png",
        "angular_coherence_plot": root / "angular_coherence_plot.png",
        "outer_recycling_plot": root / "outer_recycling_plot.png",
        "modal_sidebands_plot": root / "modal_sidebands_plot.png",
        "pattern_similarity_decay_plot": root / "pattern_similarity_decay_plot.png",
    }

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(radial_csv, radial_rows, _radial_fields())
    _write_csv(angular_csv, angular_rows, _angular_fields())
    _write_csv(outer_csv, outer_rows, _outer_fields())
    _write_csv(modal_csv, modal_rows, _modal_fields())
    _write_csv(pattern_csv, pattern_rows, _pattern_fields())
    _write_plots(plots, summary_rows, radial_rows, angular_rows, outer_rows, modal_rows, pattern_rows)
    _write_report(report_path, control_id, summary_rows, classification, plots)
    summary_json.write_text(
        json.dumps(
            {
                "control_id": control_id,
                "classification": classification,
                "row_count": len(summary_rows),
                "summary_csv": str(summary_csv),
                "radial_csv": str(radial_csv),
                "angular_csv": str(angular_csv),
                "outer_csv": str(outer_csv),
                "modal_csv": str(modal_csv),
                "pattern_csv": str(pattern_csv),
                "report_path": str(report_path),
                "plots": {key: str(value) for key, value in plots.items()},
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
        "radial_rows": radial_rows,
        "angular_rows": angular_rows,
        "outer_rows": outer_rows,
        "modal_rows": modal_rows,
        "pattern_rows": pattern_rows,
        "summary_csv": str(summary_csv),
        "radial_csv": str(radial_csv),
        "angular_csv": str(angular_csv),
        "outer_csv": str(outer_csv),
        "modal_csv": str(modal_csv),
        "pattern_csv": str(pattern_csv),
        "report_path": str(report_path),
        "summary_json": str(summary_json),
        "plots": {key: str(value) for key, value in plots.items()},
        "path": str(root),
    }


def calculate_radial_leakage_ratio(shell_energy: float, neighboring_energy: float) -> float:
    """Return neighboring-window energy relative to the radius-5 shell-window energy."""

    shell = max(float(shell_energy), 0.0)
    neighbor = max(float(neighboring_energy), 0.0)
    return neighbor / max(shell, EPSILON)


def calculate_angular_sector_coherence(phase_cycles: list[float], weights: list[float] | None = None) -> float:
    """Calculate weighted circular coherence for angular-sector phase samples."""

    if not phase_cycles:
        return 0.0
    phases = np.asarray([float(value) for value in phase_cycles], dtype=float)
    if weights is None:
        w = np.ones(phases.size, dtype=float)
    else:
        w = np.asarray([max(float(value), 0.0) for value in weights], dtype=float)
        if w.size != phases.size:
            w = np.ones(phases.size, dtype=float)
    total = float(np.sum(w))
    if total <= EPSILON:
        w = np.ones(phases.size, dtype=float)
        total = float(np.sum(w))
    vector = np.exp(2.0j * math.pi * phases)
    return float(abs(np.sum(w * vector) / max(total, EPSILON)))


def calculate_outer_off_comb_correlation(
    outer_signal: np.ndarray,
    off_comb_signal: np.ndarray,
    *,
    max_lag_samples: int = 1,
) -> dict[str, float]:
    """Find the strongest positive-lag correlation from outer energy to off-comb shell energy."""

    outer = np.asarray(outer_signal, dtype=float)
    off_comb = np.asarray(off_comb_signal, dtype=float)
    length = min(outer.size, off_comb.size)
    if length < 3:
        return {"best_correlation": 0.0, "best_lag_samples": 0.0}
    outer = outer[:length]
    off_comb = off_comb[:length]
    best = -1.0
    best_lag = 0
    for lag in range(max(0, int(max_lag_samples)) + 1):
        if lag == 0:
            left = outer
            right = off_comb
        else:
            left = outer[:-lag]
            right = off_comb[lag:]
        if left.size < 3 or right.size < 3 or float(np.std(left)) <= EPSILON or float(np.std(right)) <= EPSILON:
            corr = 0.0
        else:
            corr = float(np.corrcoef(left, right)[0, 1])
            if not math.isfinite(corr):
                corr = 0.0
        if corr > best:
            best = corr
            best_lag = lag
    return {"best_correlation": max(best, 0.0), "best_lag_samples": float(best_lag)}


def calculate_modal_sideband_leakage(
    frequencies: np.ndarray,
    power: np.ndarray,
    *,
    center_frequency: float,
    center_half_width: float,
    sideband_half_width: float,
) -> dict[str, float]:
    """Measure sideband power near a modal band after excluding the center band."""

    freq = np.asarray(frequencies, dtype=float)
    pwr = np.asarray(power, dtype=float)
    if freq.size == 0 or pwr.size == 0 or freq.size != pwr.size:
        return {"center_power_fraction": 0.0, "sideband_power_fraction": 0.0, "sideband_to_center_ratio": 0.0}
    pwr = np.maximum(pwr, 0.0)
    total = float(np.sum(pwr))
    if total <= EPSILON:
        return {"center_power_fraction": 0.0, "sideband_power_fraction": 0.0, "sideband_to_center_ratio": 0.0}
    center = abs(float(center_frequency))
    central = np.abs(freq - center) <= max(float(center_half_width), 0.0)
    nearby = np.abs(freq - center) <= max(float(sideband_half_width), float(center_half_width))
    sideband = nearby & ~central
    center_power = float(np.sum(pwr[central]))
    sideband_power = float(np.sum(pwr[sideband]))
    return {
        "center_power_fraction": center_power / total,
        "sideband_power_fraction": sideband_power / total,
        "sideband_to_center_ratio": sideband_power / max(center_power, EPSILON),
    }


def classify_off_comb_leakage_audit(
    rows: list[dict[str, Any]],
    options: OffCombLeakageAuditOptions | None = None,
) -> dict[str, Any]:
    """Classify the dominant off-comb leakage mechanism from summary rows."""

    options = options or OffCombLeakageAuditOptions()
    proof = _proof_rows(rows)
    controls = _source_control_rows(rows)
    if not proof or len(controls) < 3:
        return {
            "label": "insufficient_artifacts",
            "reason": "Required 41^3 proof and 51^3 source-control leakage artifacts were not available.",
            "checks": {
                "proof_row_count": len(proof),
                "source_control_row_count": len(controls),
                "mechanism_candidate": "none",
            },
        }

    proof_radial = _mean(row.get("radial_leakage_ratio") for row in proof)
    control_radial = _mean(row.get("radial_leakage_ratio") for row in controls)
    radial_delta = control_radial - proof_radial
    proof_angular = _mean(row.get("angular_sector_coherence_mean") for row in proof)
    control_angular = _mean(row.get("angular_sector_coherence_mean") for row in controls)
    angular_drop = proof_angular - control_angular
    proof_outer = _mean(row.get("outer_off_comb_best_correlation") for row in proof)
    control_outer = _mean(row.get("outer_off_comb_best_correlation") for row in controls)
    outer_delta = control_outer - proof_outer
    proof_modal = _mean(row.get("modal_sideband_fraction") for row in proof)
    control_modal = _mean(row.get("modal_sideband_fraction") for row in controls)
    modal_delta = control_modal - proof_modal
    proof_pattern = _mean(row.get("spatial_pattern_leakage_score") for row in proof)
    control_pattern = _mean(row.get("spatial_pattern_leakage_score") for row in controls)
    pattern_delta = control_pattern - proof_pattern
    proof_flux = _mean(row.get("off_return_outward_flux_fraction") for row in proof)
    control_flux = _mean(row.get("off_return_outward_flux_fraction") for row in controls)
    flux_delta = control_flux - proof_flux

    supported = {
        "radial_leakage_supported": radial_delta >= options.radial_ratio_support_delta,
        "angular_leakage_supported": angular_drop >= options.angular_coherence_drop_threshold,
        "outer_recycling_supported": control_outer >= options.outer_correlation_threshold and outer_delta > 0.0,
        "modal_sideband_leakage_supported": modal_delta >= options.modal_sideband_delta_threshold,
        "spatial_pattern_scrambling_supported": pattern_delta >= options.spatial_pattern_delta_threshold,
    }
    supported_count = sum(1 for value in supported.values() if value)
    checks = {
        "proof_row_count": len(proof),
        "source_control_row_count": len(controls),
        "proof_radial_leakage_mean": proof_radial,
        "source_control_radial_leakage_mean": control_radial,
        "radial_leakage_delta": radial_delta,
        "proof_angular_coherence_mean": proof_angular,
        "source_control_angular_coherence_mean": control_angular,
        "angular_coherence_drop": angular_drop,
        "proof_outer_off_comb_correlation_mean": proof_outer,
        "source_control_outer_off_comb_correlation_mean": control_outer,
        "outer_correlation_delta": outer_delta,
        "proof_modal_sideband_fraction_mean": proof_modal,
        "source_control_modal_sideband_fraction_mean": control_modal,
        "modal_sideband_delta": modal_delta,
        "proof_spatial_pattern_leakage_mean": proof_pattern,
        "source_control_spatial_pattern_leakage_mean": control_pattern,
        "spatial_pattern_leakage_delta": pattern_delta,
        "proof_off_return_outward_flux_fraction_mean": proof_flux,
        "source_control_off_return_outward_flux_fraction_mean": control_flux,
        "off_return_outward_flux_delta": flux_delta,
        "supported_channels": [label for label, value in supported.items() if value],
        "mechanism_candidate": "none",
    }
    if supported_count >= options.source_channel_count_for_mixed:
        return {
            "label": "mixed_leakage_supported",
            "reason": "Multiple 51^3 leakage channels separate from the 41^3 proof rows, so the off-comb loss is mixed rather than a single clean channel.",
            "checks": checks,
        }
    for label, value in supported.items():
        if value:
            reasons = {
                "radial_leakage_supported": "The 51^3 rows show higher radial leakage around the return windows than the 41^3 proof rows.",
                "angular_leakage_supported": "The 51^3 rows lose angular-sector phase coherence relative to the 41^3 proof rows.",
                "outer_recycling_supported": "Lagged outer-window energy correlates with 51^3 off-comb shell energy.",
                "modal_sideband_leakage_supported": "The 51^3 rows move more shell-window spectral power into sidebands near the return band.",
                "spatial_pattern_scrambling_supported": "The 51^3 rows show stronger return-to-return spatial-pattern leakage than the 41^3 proof rows.",
            }
            return {"label": label, "reason": reasons[label], "checks": checks}
    return {
        "label": "leakage_inconclusive",
        "reason": "The audit found off-comb weakening but no leakage channel separated cleanly from the 41^3 proof rows.",
        "checks": checks,
    }


def _load_records(options: OffCombLeakageAuditOptions) -> list[dict[str, Any]]:
    gate_root = Path(options.return_family_gate_root)
    summary_rows = _read_csv(gate_root / "return_family_gate_summary.csv")
    if not summary_rows:
        return []
    occupancy_by_variant = _group_by(_read_csv(gate_root / "return_window_occupancy.csv"), "variant")
    modal_by_variant = {row.get("variant"): row for row in _read_csv(Path(options.modal_sparsity_root) / "modal_sparsity_summary.csv")}
    spatial = _load_spatial_artifacts(options)
    records = []
    for row in summary_rows:
        variant = str(row.get("variant"))
        timeseries, events = _load_lifecycle_for_row(row, options)
        record = {
            "variant": variant,
            "artifact_source": row.get("artifact_source"),
            "audit_group": row.get("audit_group"),
            "prediction_role": row.get("prediction_role"),
            "gate_summary": row,
            "gate_windows": occupancy_by_variant.get(variant, []),
            "timeseries": timeseries,
            "events": events,
            "modal_summary": modal_by_variant.get(variant, {}),
            "spatial": spatial.get(variant) or spatial.get(_spatial_alias(variant), {}),
        }
        records.append(record)
    return [record for record in records if record.get("gate_summary")]


def _load_lifecycle_for_row(
    row: dict[str, Any],
    options: OffCombLeakageAuditOptions,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    artifact = str(row.get("artifact_source"))
    variant = str(row.get("variant"))
    if artifact == "proof_pack":
        root = Path(options.proof_root) / variant
        return _read_csv(root / "packet_lifecycle_timeseries.csv"), _read_csv(root / "packet_lifecycle_events.csv")
    if artifact == "resolution_lift":
        root = Path(options.lift_root) / variant
        return _read_csv(root / "packet_lifecycle_timeseries.csv"), _read_csv(root / "packet_lifecycle_events.csv")
    if artifact == "spatial_phase_instrumentation":
        root = Path(options.spatial_phase_root)
        return (
            _group_by(_read_csv(root / "spatial_phase_lifecycle_timeseries.csv"), "variant").get(variant, []),
            _group_by(_read_csv(root / "spatial_phase_lifecycle_events.csv"), "variant").get(variant, []),
        )
    if artifact == "smooth_envelope":
        root = Path(options.smooth_root)
        return (
            _group_by(_read_csv(root / "smooth_envelope_lifecycle_timeseries.csv"), "variant").get(variant, []),
            _group_by(_read_csv(root / "smooth_envelope_lifecycle_events.csv"), "variant").get(variant, []),
        )
    if artifact == "boundary_phase_conjugate":
        root = Path(options.phase_conjugate_root)
        return (
            _group_by(_read_csv(root / "boundary_phase_conjugate_lifecycle_timeseries.csv"), "variant").get(variant, []),
            _group_by(_read_csv(root / "boundary_phase_conjugate_lifecycle_events.csv"), "variant").get(variant, []),
        )
    return [], []


def _load_spatial_artifacts(options: OffCombLeakageAuditOptions) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    _attach_spatial_set(
        artifacts,
        root=Path(options.spatial_phase_root),
        summary_name="spatial_phase_instrumentation_summary.csv",
        radial_name="shell_phase_coherence_by_radius.csv",
        angular_name="angular_shell_phase_coherence.csv",
        drift_name="phase_drift_across_return_peaks.csv",
        stability_name="node_antinode_stability_maps.csv",
    )
    _attach_spatial_set(
        artifacts,
        root=Path(options.smooth_root),
        summary_name="smooth_envelope_resolution_lift_summary.csv",
        radial_name="smooth_envelope_shell_phase_coherence_by_radius.csv",
        angular_name="smooth_envelope_angular_shell_phase_coherence.csv",
        drift_name="smooth_envelope_phase_drift_across_return_peaks.csv",
        stability_name="smooth_envelope_node_antinode_stability_maps.csv",
    )
    _attach_spatial_set(
        artifacts,
        root=Path(options.phase_conjugate_root),
        summary_name="boundary_phase_conjugate_summary.csv",
        radial_name="boundary_phase_conjugate_shell_phase_coherence_by_radius.csv",
        angular_name="boundary_phase_conjugate_angular_shell_phase_coherence.csv",
        drift_name="boundary_phase_conjugate_phase_drift_across_return_peaks.csv",
        stability_name="boundary_phase_conjugate_node_antinode_stability_maps.csv",
    )
    return artifacts


def _attach_spatial_set(
    artifacts: dict[str, dict[str, Any]],
    *,
    root: Path,
    summary_name: str,
    radial_name: str,
    angular_name: str,
    drift_name: str,
    stability_name: str,
) -> None:
    summary_by_variant = {row.get("variant"): row for row in _read_csv(root / summary_name)}
    radial_by_variant = _group_by(_read_csv(root / radial_name), "variant")
    angular_by_variant = _group_by(_read_csv(root / angular_name), "variant")
    drift_by_variant = _group_by(_read_csv(root / drift_name), "variant")
    stability_by_variant = _group_by(_read_csv(root / stability_name), "variant")
    for variant in set(summary_by_variant) | set(radial_by_variant) | set(angular_by_variant) | set(drift_by_variant) | set(stability_by_variant):
        artifacts[str(variant)] = {
            "summary": summary_by_variant.get(variant, {}),
            "radial": radial_by_variant.get(str(variant), []),
            "angular": angular_by_variant.get(str(variant), []),
            "drift": drift_by_variant.get(str(variant), []),
            "stability": stability_by_variant.get(str(variant), []),
        }


def _diagnose_record(record: dict[str, Any], options: OffCombLeakageAuditOptions) -> dict[str, Any]:
    row = record["gate_summary"]
    variant = record["variant"]
    artifact_source = str(record.get("artifact_source"))
    audit_group = str(record.get("audit_group"))
    role = str(record.get("prediction_role"))
    times = _array(ts.get("time") for ts in record.get("timeseries", []))
    shell = _array(ts.get("shell_window_energy") for ts in record.get("timeseries", []))
    outer = _array(ts.get("outer_active_energy") for ts in record.get("timeseries", []))
    inward = _array(ts.get("shell_inward_flux") for ts in record.get("timeseries", []))
    outward = _array(ts.get("shell_outward_flux") for ts in record.get("timeseries", []))
    centroid = _array(ts.get("packet_centroid_radius") for ts in record.get("timeseries", []))
    spread = _array(ts.get("packet_radial_spread") for ts in record.get("timeseries", []))
    width = _array(ts.get("packet_radial_width") for ts in record.get("timeseries", []))
    radial_rows, radial_summary = _radial_leakage_rows(
        record,
        times=times,
        shell=shell,
        centroid=centroid,
        spread=spread,
        width=width,
        options=options,
    )
    angular_rows, angular_summary = _angular_leakage_rows(record)
    outer_row = _outer_recycling_row(record, times, shell, outer)
    modal_row = _modal_sideband_row(record, times, shell)
    pattern_row = _spatial_pattern_row(record)
    flux_summary = _flux_summary(record, times, inward, outward)
    counts = _count_metrics(row)
    summary = {
        "variant": variant,
        "artifact_source": artifact_source,
        "audit_group": audit_group,
        "prediction_role": role,
        "grid_size": row.get("grid_size"),
        "strict_major_peaks": counts["strict_major_peaks"],
        "strict_refocus_peaks": counts["strict_refocus_peaks"],
        "default_major_peaks": counts["default_major_peaks"],
        "default_refocus_peaks": counts["default_refocus_peaks"],
        "loose_major_peaks": counts["loose_major_peaks"],
        "loose_refocus_peaks": counts["loose_refocus_peaks"],
        "off_comb_energy_ratio": _float(row.get("off_comb_energy_ratio")),
        "return_comb_score": _float(row.get("return_comb_score")),
        "late_return_area_survival_fraction": _float(row.get("late_return_area_survival_fraction")),
        "radial_leakage_ratio": radial_summary["radial_leakage_ratio"],
        "radial_centroid_offset_mean": radial_summary["radial_centroid_offset_mean"],
        "radial_spread_mean": radial_summary["radial_spread_mean"],
        "angular_sector_coherence_mean": angular_summary["angular_sector_coherence_mean"],
        "angular_mode_spread": angular_summary["angular_mode_spread"],
        "outer_off_comb_best_correlation": outer_row["best_correlation"],
        "outer_off_comb_best_lag_time": outer_row["best_lag_time"],
        "modal_sideband_fraction": modal_row["sideband_power_fraction"],
        "modal_sideband_to_center_ratio": modal_row["sideband_to_center_ratio"],
        "spatial_pattern_similarity": pattern_row["pattern_similarity"],
        "spatial_pattern_leakage_score": pattern_row["pattern_leakage_score"],
        "return_window_inward_flux_fraction": flux_summary["return_window_inward_flux_fraction"],
        "off_return_outward_flux_fraction": flux_summary["off_return_outward_flux_fraction"],
        "flux_leakage_delta": flux_summary["off_return_outward_flux_fraction"] - (1.0 - flux_summary["return_window_inward_flux_fraction"]),
        "no_exit": _bool(row.get("no_exit")),
        "global_outer_false": _bool(row.get("global_outer_false")),
    }
    return {
        "summary": summary,
        "radial_rows": radial_rows,
        "angular_rows": angular_rows,
        "outer_row": outer_row,
        "modal_row": modal_row,
        "pattern_row": pattern_row,
    }


def _radial_leakage_rows(
    record: dict[str, Any],
    *,
    times: np.ndarray,
    shell: np.ndarray,
    centroid: np.ndarray,
    spread: np.ndarray,
    width: np.ndarray,
    options: OffCombLeakageAuditOptions,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    rows = []
    ratios = []
    offsets = []
    spreads = []
    for window in record.get("gate_windows", []):
        start = _float(window.get("window_start"))
        end = _float(window.get("window_end"))
        mask = (times >= start) & (times <= end) if times.size else np.asarray([], dtype=bool)
        shell_area = _integrate(times[mask], shell[mask]) if mask.any() else _float(window.get("window_energy"))
        offset = _mean(np.abs(centroid[mask] - options.shell_window_center_radius)) if mask.any() and centroid.size else 0.0
        spread_mean = _mean(spread[mask]) if mask.any() and spread.size else 0.0
        width_mean = _mean(width[mask]) if mask.any() and width.size else 0.0
        neighbor_proxy = shell_area * max(0.0, (offset + 0.35 * spread_mean) / max(options.shell_window_half_width, EPSILON))
        ratio = calculate_radial_leakage_ratio(shell_area, neighbor_proxy)
        rows.append(
            {
                "variant": record["variant"],
                "artifact_source": record.get("artifact_source"),
                "audit_group": record.get("audit_group"),
                "prediction_role": record.get("prediction_role"),
                "return_index": window.get("return_index"),
                "window_start": start,
                "window_end": end,
                "shell_window_energy_area": shell_area,
                "neighboring_radial_energy_proxy": neighbor_proxy,
                "radial_leakage_ratio": ratio,
                "packet_centroid_offset_mean": offset,
                "packet_radial_spread_mean": spread_mean,
                "packet_radial_width_mean": width_mean,
            }
        )
        ratios.append(ratio)
        offsets.append(offset)
        spreads.append(spread_mean)
    return rows, {
        "radial_leakage_ratio": _mean(ratios),
        "radial_centroid_offset_mean": _mean(offsets),
        "radial_spread_mean": _mean(spreads),
    }


def _angular_leakage_rows(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    spatial = record.get("spatial", {})
    rows = []
    coherence_values = []
    mode_spread_values = []
    for frame_id, sectors in _group_by(spatial.get("angular", []), "frame_id").items():
        phase = [_float(row.get("phase_mean_cycles")) for row in sectors if row.get("polar_bin") != "octant"]
        weights = [_float(row.get("shell_energy")) for row in sectors if row.get("polar_bin") != "octant"]
        sector_coherence = calculate_angular_sector_coherence(phase, weights) if phase else 0.0
        energy = np.asarray(weights, dtype=float)
        participation = _participation_ratio(energy) if energy.size else 0.0
        mode_spread = participation / max(float(energy.size), 1.0) if energy.size else 0.0
        mean_stored_coherence = _mean(row.get("phase_coherence") for row in sectors if row.get("polar_bin") != "octant")
        rows.append(
            {
                "variant": record["variant"],
                "artifact_source": record.get("artifact_source"),
                "audit_group": record.get("audit_group"),
                "prediction_role": record.get("prediction_role"),
                "frame_id": frame_id,
                "return_index": _first_nonempty(sectors, "peak_rank"),
                "time": _first_nonempty(sectors, "time"),
                "sector_count": len(sectors),
                "weighted_phase_coherence": sector_coherence,
                "mean_sector_phase_coherence": mean_stored_coherence,
                "angular_mode_spread": mode_spread,
                "sector_energy_participation": participation,
            }
        )
        coherence_values.append(sector_coherence or mean_stored_coherence)
        mode_spread_values.append(mode_spread)
    summary = spatial.get("summary", {})
    if not rows and not _first(summary, "angular_phase_coherence_mean"):
        return rows, {"angular_sector_coherence_mean": "", "angular_mode_spread": ""}
    return rows, {
        "angular_sector_coherence_mean": _mean(coherence_values) or _first(summary, "angular_phase_coherence_mean"),
        "angular_mode_spread": _mean(mode_spread_values),
    }


def _outer_recycling_row(record: dict[str, Any], times: np.ndarray, shell: np.ndarray, outer: np.ndarray) -> dict[str, Any]:
    off_mask = _off_return_mask(record, times)
    off_signal = np.where(off_mask, shell, 0.0) if times.size and shell.size else np.asarray([], dtype=float)
    dt = _median_dt(times)
    period = _float(record["gate_summary"].get("predicted_return_period"))
    max_lag = int(max(1.0, period) / max(dt, EPSILON)) if dt > EPSILON else 1
    corr = calculate_outer_off_comb_correlation(outer, off_signal, max_lag_samples=min(max_lag, 300))
    lag_time = corr["best_lag_samples"] * dt
    off_area = _integrate(times[off_mask], shell[off_mask]) if off_mask.any() else 0.0
    outer_area = _integrate(times, outer) if times.size and outer.size else 0.0
    return {
        "variant": record["variant"],
        "artifact_source": record.get("artifact_source"),
        "audit_group": record.get("audit_group"),
        "prediction_role": record.get("prediction_role"),
        "best_correlation": corr["best_correlation"],
        "best_lag_samples": corr["best_lag_samples"],
        "best_lag_time": lag_time,
        "off_comb_shell_energy_area": off_area,
        "outer_energy_area": outer_area,
        "outer_to_off_comb_area_ratio": outer_area / max(off_area, EPSILON) if off_area > EPSILON else 0.0,
    }


def _modal_sideband_row(record: dict[str, Any], times: np.ndarray, shell: np.ndarray) -> dict[str, Any]:
    cutoff = _float(record["gate_summary"].get("drive_cutoff_time"))
    mask = times > cutoff if times.size else np.asarray([], dtype=bool)
    freq, power = _fft_power(times[mask], shell[mask])
    dominant = _float(record.get("modal_summary", {}).get("dominant_frequency"))
    if dominant <= EPSILON and freq.size:
        dominant = float(freq[int(np.argmax(power))]) if power.size else 0.0
    df = float(np.median(np.diff(freq))) if freq.size > 1 else 0.0
    leakage = calculate_modal_sideband_leakage(
        freq,
        power,
        center_frequency=dominant,
        center_half_width=max(1.5 * df, 0.20 * dominant),
        sideband_half_width=max(8.0 * df, 5.0 * dominant),
    )
    return {
        "variant": record["variant"],
        "artifact_source": record.get("artifact_source"),
        "audit_group": record.get("audit_group"),
        "prediction_role": record.get("prediction_role"),
        "dominant_frequency": dominant,
        "spectral_bandwidth": _float(record.get("modal_summary", {}).get("spectral_bandwidth")),
        "center_power_fraction": leakage["center_power_fraction"],
        "sideband_power_fraction": leakage["sideband_power_fraction"],
        "sideband_to_center_ratio": leakage["sideband_to_center_ratio"],
        "modal_participation_ratio": _float(record.get("modal_summary", {}).get("modal_participation_ratio")),
        "modes_for_99pct": _float(record.get("modal_summary", {}).get("modes_for_99pct")),
    }


def _spatial_pattern_row(record: dict[str, Any]) -> dict[str, Any]:
    spatial = record.get("spatial", {})
    summary = spatial.get("summary", {})
    drift_rows = spatial.get("drift", [])
    stability_rows = spatial.get("stability", [])
    if not summary and not drift_rows and not stability_rows:
        return {
            "variant": record["variant"],
            "artifact_source": record.get("artifact_source"),
            "audit_group": record.get("audit_group"),
            "prediction_role": record.get("prediction_role"),
            "pattern_similarity": "",
            "shell_phase_coherence": "",
            "radial_phase_coherence": "",
            "angular_phase_coherence": "",
            "node_phase_stability": "",
            "return_phase_drift_abs_mean_cycles": "",
            "phase_coherence_decay_per_return": "",
            "pattern_leakage_score": "",
        }
    shell_coherence = _first(summary, "shell_phase_coherence_mean")
    radial_coherence = _first(summary, "radial_phase_coherence_mean")
    angular_coherence = _first(summary, "angular_phase_coherence_mean")
    stability = _first(summary, "node_phase_stability_mean") or _mean(row.get("phase_coherence_over_returns") for row in stability_rows)
    pattern_similarity = _mean(value for value in (shell_coherence, radial_coherence, angular_coherence, stability) if value > 0.0)
    drift_abs = _first(summary, "return_phase_drift_abs_mean_cycles") or _mean(abs(_float(row.get("phase_drift_cycles"))) for row in drift_rows)
    similarity_decay = _phase_coherence_decay(drift_rows)
    leakage = max(0.0, 1.0 - pattern_similarity) + drift_abs + max(0.0, similarity_decay)
    return {
        "variant": record["variant"],
        "artifact_source": record.get("artifact_source"),
        "audit_group": record.get("audit_group"),
        "prediction_role": record.get("prediction_role"),
        "pattern_similarity": pattern_similarity,
        "shell_phase_coherence": shell_coherence,
        "radial_phase_coherence": radial_coherence,
        "angular_phase_coherence": angular_coherence,
        "node_phase_stability": stability,
        "return_phase_drift_abs_mean_cycles": drift_abs,
        "phase_coherence_decay_per_return": similarity_decay,
        "pattern_leakage_score": leakage,
    }


def _flux_summary(
    record: dict[str, Any],
    times: np.ndarray,
    inward: np.ndarray,
    outward: np.ndarray,
) -> dict[str, float]:
    if times.size == 0 or inward.size == 0 or outward.size == 0:
        return {"return_window_inward_flux_fraction": 0.0, "off_return_outward_flux_fraction": 0.0}
    return_mask = _return_mask(record, times)
    off_mask = ~return_mask
    return_in = _integrate(times[return_mask], inward[return_mask]) if return_mask.any() else 0.0
    return_out = _integrate(times[return_mask], outward[return_mask]) if return_mask.any() else 0.0
    off_in = _integrate(times[off_mask], inward[off_mask]) if off_mask.any() else 0.0
    off_out = _integrate(times[off_mask], outward[off_mask]) if off_mask.any() else 0.0
    return_fraction = return_in / max(return_in + return_out, EPSILON)
    off_out_fraction = off_out / max(off_in + off_out, EPSILON)
    return {
        "return_window_inward_flux_fraction": return_fraction,
        "off_return_outward_flux_fraction": off_out_fraction,
    }


def _return_mask(record: dict[str, Any], times: np.ndarray) -> np.ndarray:
    mask = np.zeros(times.size, dtype=bool)
    for window in record.get("gate_windows", []):
        start = _float(window.get("window_start"))
        end = _float(window.get("window_end"))
        mask |= (times >= start) & (times <= end)
    return mask


def _off_return_mask(record: dict[str, Any], times: np.ndarray) -> np.ndarray:
    cutoff = _float(record["gate_summary"].get("drive_cutoff_time"))
    return (times > cutoff) & ~_return_mask(record, times)


def _fft_power(times: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if times.size < 4 or values.size < 4:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    dt = _median_dt(times)
    centered = values - float(np.mean(values))
    freq = np.fft.rfftfreq(centered.size, d=max(dt, EPSILON))
    power = np.abs(np.fft.rfft(centered)) ** 2
    if freq.size <= 1:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    return freq[1:], power[1:]


def _phase_coherence_decay(rows: list[dict[str, Any]]) -> float:
    if len(rows) < 2:
        return 0.0
    x = np.asarray([_float(row.get("to_peak_rank")) for row in rows], dtype=float)
    y = np.asarray([_float(row.get("to_shell_phase_coherence")) for row in rows], dtype=float)
    good = np.isfinite(x) & np.isfinite(y)
    if int(np.sum(good)) < 2 or float(np.ptp(x[good])) <= EPSILON:
        return 0.0
    slope, _ = np.polyfit(x[good], y[good], 1)
    return float(-slope)


def _write_plots(
    plots: dict[str, Path],
    summary_rows: list[dict[str, Any]],
    radial_rows: list[dict[str, Any]],
    angular_rows: list[dict[str, Any]],
    outer_rows: list[dict[str, Any]],
    modal_rows: list[dict[str, Any]],
    pattern_rows: list[dict[str, Any]],
) -> None:
    _plot_summary_bar(plots["radial_leakage_plot"], summary_rows, "radial_leakage_ratio", "Radial Leakage Ratio")
    _plot_summary_bar(plots["angular_coherence_plot"], summary_rows, "angular_sector_coherence_mean", "Angular Sector Coherence")
    _plot_summary_bar(plots["outer_recycling_plot"], outer_rows, "best_correlation", "Outer / Off-Comb Correlation")
    _plot_summary_bar(plots["modal_sidebands_plot"], modal_rows, "sideband_power_fraction", "Modal Sideband Fraction")
    _plot_summary_bar(plots["pattern_similarity_decay_plot"], pattern_rows, "pattern_leakage_score", "Spatial Pattern Leakage")


def _plot_summary_bar(path: Path, rows: list[dict[str, Any]], key: str, title: str) -> None:
    selected = _plot_rows(rows)
    labels = [_short_label(str(row.get("variant"))) for row in selected]
    values = [_float(row.get(key)) for row in selected]
    fig, ax = plt.subplots(figsize=(max(7, len(labels) * 0.8), 4), dpi=140)
    ax.bar(range(len(labels)), values, color="#4477aa")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = [
        "quarter_dt_proof_candidate_cutoff_17p94",
        "resolution_lift_51_candidate_phase_0p5071",
        "smooth_envelope_51_hard_cutoff_17p9425",
        "smooth_envelope_51_smooth_cutoff_17p9425",
        "phase_conjugate_51_hard_cutoff_17p9425",
        "phase_conjugate_51_candidate_cutoff_17p9425",
        "phase_conjugate_51_shuffled_cutoff_17p9425",
    ]
    by_variant = {str(row.get("variant")): row for row in rows}
    selected = [by_variant[variant] for variant in wanted if variant in by_variant]
    for variant in sorted(by_variant):
        if variant not in wanted and len(selected) < 8:
            selected.append(by_variant[variant])
    return selected


def _short_label(variant: str) -> str:
    replacements = {
        "quarter_dt_proof_candidate_cutoff_17p94": "41 proof",
        "resolution_lift_51_candidate_phase_0p5071": "51 lift",
        "smooth_envelope_51_hard_cutoff_17p9425": "smooth hard",
        "smooth_envelope_51_smooth_cutoff_17p9425": "smooth",
        "phase_conjugate_51_hard_cutoff_17p9425": "pc hard",
        "phase_conjugate_51_candidate_cutoff_17p9425": "pc candidate",
        "phase_conjugate_51_shuffled_cutoff_17p9425": "pc shuffled",
    }
    return replacements.get(variant, variant.replace("_cutoff_17p9425", "").replace("_phase_0p5071", "")[:28])


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    plots: dict[str, Path],
) -> None:
    checks = classification.get("checks", {})
    lines = [
        f"# Off-Comb Leakage Audit: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only localization of where the 51^3 return-family energy leaks after the return-family gate audit rejected a detector-only explanation. No new physics was run.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Mechanism-derived next candidate: `{checks.get('mechanism_candidate', 'none')}`",
        "",
        "## Channel Means",
        "",
        f"- Proof radial leakage mean: `{_format(checks.get('proof_radial_leakage_mean'))}`",
        f"- 51^3 radial leakage mean: `{_format(checks.get('source_control_radial_leakage_mean'))}`",
        f"- Proof angular coherence mean: `{_format(checks.get('proof_angular_coherence_mean'))}`",
        f"- 51^3 angular coherence mean: `{_format(checks.get('source_control_angular_coherence_mean'))}`",
        f"- 51^3 outer/off-comb correlation mean: `{_format(checks.get('source_control_outer_off_comb_correlation_mean'))}`",
        f"- Proof modal sideband fraction mean: `{_format(checks.get('proof_modal_sideband_fraction_mean'))}`",
        f"- 51^3 modal sideband fraction mean: `{_format(checks.get('source_control_modal_sideband_fraction_mean'))}`",
        f"- Proof spatial-pattern leakage mean: `{_format(checks.get('proof_spatial_pattern_leakage_mean'))}`",
        f"- 51^3 spatial-pattern leakage mean: `{_format(checks.get('source_control_spatial_pattern_leakage_mean'))}`",
        f"- Supported channels: `{', '.join(checks.get('supported_channels', [])) or 'none'}`",
        "",
        "## Source-Control Comparison",
        "",
        "| Source | Role | Grid | Strict | Off-comb | Radial | Angular coherence | Outer corr | Modal sideband | Pattern leakage |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in _source_control_rows(rows):
        lines.append(
            "| "
            f"{row.get('artifact_source')} | "
            f"{row.get('prediction_role')} | "
            f"{row.get('grid_size')} | "
            f"{row.get('strict_major_peaks')}/{row.get('strict_refocus_peaks')} | "
            f"{_format(row.get('off_comb_energy_ratio'))} | "
            f"{_format(row.get('radial_leakage_ratio'))} | "
            f"{_format(row.get('angular_sector_coherence_mean'))} | "
            f"{_format(row.get('outer_off_comb_best_correlation'))} | "
            f"{_format(row.get('modal_sideband_fraction'))} | "
            f"{_format(row.get('spatial_pattern_leakage_score'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Plots",
            "",
        ]
    )
    for plot in plots.values():
        lines.append(f"- `{plot.name}`")
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `off_comb_leakage_summary.csv`",
            "- `radial_leakage_by_window.csv`",
            "- `angular_leakage_by_sector.csv`",
            "- `outer_recycling_correlation.csv`",
            "- `modal_sideband_leakage.csv`",
            "- `spatial_pattern_leakage.csv`",
            "- `off_comb_leakage_summary.json`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "mixed_leakage_supported":
        return "The 51^3 strict loss is not localized to one clean sink. The saved artifacts show several leakage signatures separating from the 41^3 proof rows, so source-shape or detector-only rescue remains unsupported."
    if label == "radial_leakage_supported":
        return "The strongest separator is radial leakage around the return windows."
    if label == "angular_leakage_supported":
        return "The strongest separator is angular-sector phase decoherence."
    if label == "outer_recycling_supported":
        return "The strongest separator is delayed outer-window energy recycling into off-comb shell energy."
    if label == "modal_sideband_leakage_supported":
        return "The strongest separator is sideband power near the return band."
    if label == "spatial_pattern_scrambling_supported":
        return "The strongest separator is return-to-return spatial-pattern scrambling."
    if label == "insufficient_artifacts":
        return "The required saved proof/source-control artifacts were missing."
    return "The current artifacts do not cleanly localize the off-comb leakage channel."


def _write_empty_outputs(root: Path, control_id: str, classification: dict[str, Any]) -> dict[str, Any]:
    summary_csv = root / "off_comb_leakage_summary.csv"
    radial_csv = root / "radial_leakage_by_window.csv"
    angular_csv = root / "angular_leakage_by_sector.csv"
    outer_csv = root / "outer_recycling_correlation.csv"
    modal_csv = root / "modal_sideband_leakage.csv"
    pattern_csv = root / "spatial_pattern_leakage.csv"
    report_path = root / "off_comb_leakage_report.md"
    _write_csv(summary_csv, [], _summary_fields())
    _write_csv(radial_csv, [], _radial_fields())
    _write_csv(angular_csv, [], _angular_fields())
    _write_csv(outer_csv, [], _outer_fields())
    _write_csv(modal_csv, [], _modal_fields())
    _write_csv(pattern_csv, [], _pattern_fields())
    report_path.write_text(
        f"# Off-Comb Leakage Audit: {control_id}\n\n"
        f"- Result: `{classification['label']}`\n"
        f"- Reason: {classification['reason']}\n",
        encoding="utf-8",
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": [],
        "radial_rows": [],
        "angular_rows": [],
        "outer_rows": [],
        "modal_rows": [],
        "pattern_rows": [],
        "summary_csv": str(summary_csv),
        "radial_csv": str(radial_csv),
        "angular_csv": str(angular_csv),
        "outer_csv": str(outer_csv),
        "modal_csv": str(modal_csv),
        "pattern_csv": str(pattern_csv),
        "report_path": str(report_path),
        "plots": {},
        "path": str(root),
    }


def _proof_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row.get("audit_group") == "proof_41" and row.get("prediction_role") in {"proof_candidate", "upper_immediate_control"}
    ]
    if selected:
        return selected
    return [row for row in rows if row.get("audit_group") in {"proof_41", "proof_41_reference"}]


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


def _spatial_alias(variant: str) -> str:
    aliases = {
        "quarter_dt_proof_candidate_cutoff_17p94": "spatial_phase_41_proof_cutoff_17p94",
        "resolution_lift_51_candidate_phase_0p5071": "spatial_phase_51_lift_candidate_phase_0p5071",
    }
    return aliases.get(variant, variant)


def _count_metrics(row: dict[str, Any]) -> dict[str, int]:
    return {
        "default_major_peaks": int(_first(row, "default_major_peaks_at_0p30", "default_major_peaks", "major_peaks_at_0p30")),
        "default_refocus_peaks": int(_first(row, "default_refocus_peaks_at_0p30", "default_refocus_peaks", "refocus_peaks_at_0p30")),
        "strict_major_peaks": int(_first(row, "strict_major_peaks", "conservative_major_peaks", "min_major_peaks_across_thresholds", "strict_major_peaks_at_0p40")),
        "strict_refocus_peaks": int(_first(row, "strict_refocus_peaks", "conservative_refocus_peaks", "min_refocus_peaks_across_thresholds", "strict_refocus_peaks_at_0p40")),
        "loose_major_peaks": int(_first(row, "loose_major_peaks", "loose_major_peaks_at_0p20", "major_peaks_at_0p20", "loose_major_peaks_at_0p25")),
        "loose_refocus_peaks": int(_first(row, "loose_refocus_peaks", "loose_refocus_peaks_at_0p20", "refocus_peaks_at_0p20", "loose_refocus_peaks_at_0p25")),
    }


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


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes"}


def _first(row: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return _float(value)
    return 0.0


def _first_nonempty(rows: list[dict[str, Any]], key: str) -> Any:
    for row in rows:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return ""


def _mean(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    return float(np.mean(parsed)) if parsed.size else 0.0


def _median_dt(times: np.ndarray) -> float:
    if times.size < 2:
        return 0.0
    return float(np.median(np.diff(times)))


def _integrate(times: np.ndarray, values: np.ndarray) -> float:
    if times.size < 2 or values.size < 2:
        return 0.0
    return float(np.trapz(values, times))


def _participation_ratio(values: np.ndarray) -> float:
    total = float(np.sum(values))
    if total <= EPSILON:
        return 0.0
    fractions = np.asarray(values, dtype=float) / total
    return float(1.0 / max(float(np.sum(fractions**2)), EPSILON))


def _summary_fields() -> list[str]:
    return [
        "variant",
        "off_comb_leakage_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "grid_size",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "default_major_peaks",
        "default_refocus_peaks",
        "loose_major_peaks",
        "loose_refocus_peaks",
        "off_comb_energy_ratio",
        "return_comb_score",
        "late_return_area_survival_fraction",
        "radial_leakage_ratio",
        "radial_centroid_offset_mean",
        "radial_spread_mean",
        "angular_sector_coherence_mean",
        "angular_mode_spread",
        "outer_off_comb_best_correlation",
        "outer_off_comb_best_lag_time",
        "modal_sideband_fraction",
        "modal_sideband_to_center_ratio",
        "spatial_pattern_similarity",
        "spatial_pattern_leakage_score",
        "return_window_inward_flux_fraction",
        "off_return_outward_flux_fraction",
        "flux_leakage_delta",
        "no_exit",
        "global_outer_false",
    ]


def _radial_fields() -> list[str]:
    return [
        "variant",
        "off_comb_leakage_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "return_index",
        "window_start",
        "window_end",
        "shell_window_energy_area",
        "neighboring_radial_energy_proxy",
        "radial_leakage_ratio",
        "packet_centroid_offset_mean",
        "packet_radial_spread_mean",
        "packet_radial_width_mean",
    ]


def _angular_fields() -> list[str]:
    return [
        "variant",
        "off_comb_leakage_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "frame_id",
        "return_index",
        "time",
        "sector_count",
        "weighted_phase_coherence",
        "mean_sector_phase_coherence",
        "angular_mode_spread",
        "sector_energy_participation",
    ]


def _outer_fields() -> list[str]:
    return [
        "variant",
        "off_comb_leakage_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "best_correlation",
        "best_lag_samples",
        "best_lag_time",
        "off_comb_shell_energy_area",
        "outer_energy_area",
        "outer_to_off_comb_area_ratio",
    ]


def _modal_fields() -> list[str]:
    return [
        "variant",
        "off_comb_leakage_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "dominant_frequency",
        "spectral_bandwidth",
        "center_power_fraction",
        "sideband_power_fraction",
        "sideband_to_center_ratio",
        "modal_participation_ratio",
        "modes_for_99pct",
    ]


def _pattern_fields() -> list[str]:
    return [
        "variant",
        "off_comb_leakage_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "pattern_similarity",
        "shell_phase_coherence",
        "radial_phase_coherence",
        "angular_phase_coherence",
        "node_phase_stability",
        "return_phase_drift_abs_mean_cycles",
        "phase_coherence_decay_per_return",
        "pattern_leakage_score",
    ]
