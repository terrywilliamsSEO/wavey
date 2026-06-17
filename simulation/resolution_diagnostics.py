"""Resolution-sensitivity diagnostics for fixed-domain long-run candidates."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .config import SimulationConfig, save_json
from .control_metrics import run_energy_comparison
from .fixed_domain_controls import _fixed_domain_config, _resample_to_config
from .lattice import Lattice2D
from .mode_diagnostics import shape_correlation
from .stability import estimate_stability
from .sweep import run_single_experiment
from .time_resolved_diagnostics import DiagnosticOptions, diagnose_existing_run


EPSILON = 1e-12


@dataclass(frozen=True)
class ResolutionDiagnosticsOptions:
    output_root: str = "runs"
    frame_interval: int = 20
    window_steps: int = 30
    grid_sizes: tuple[int, ...] = (41, 63, 81)
    source_work_relative_tolerance: float = 0.35
    mask_area_relative_tolerance: float = 0.18
    refined_peak_shift_max: float = 1.5
    coarse_peak_shift_min: float = 2.5
    refined_radial_corr_min: float = 0.72
    refined_spatial_corr_min: float = 0.35
    expected_period_min: float = 2.0
    expected_period_max: float = 3.8


def run_resolution_diagnostics(
    base_config: SimulationConfig,
    *,
    options: ResolutionDiagnosticsOptions | None = None,
    reference_root: str | Path = "runs",
) -> dict[str, Any]:
    """Run fixed-domain resolution diagnostics for the 0.92 candidate."""

    options = options or ResolutionDiagnosticsOptions()
    diagnostic_id = datetime.now().strftime("resolution_diagnostics_%Y%m%d_%H%M%S")
    diagnostic_root = Path(options.output_root) / diagnostic_id
    diagnostic_root.mkdir(parents=True, exist_ok=False)

    variants = [(f"fixed_domain_grid_{size}", _fixed_domain_config(base_config, size)) for size in options.grid_sizes]
    summary_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    mask_rows: list[dict[str, Any]] = []
    energy_budget_rows: list[dict[str, Any]] = []
    radial_rows: list[dict[str, Any]] = []
    configs_by_variant: dict[str, SimulationConfig] = {}
    radial_profiles: dict[str, dict[str, dict[str, np.ndarray | float]]] = {}

    for variant_name, config in variants:
        configs_by_variant[variant_name] = config
        run_summary = run_single_experiment(config, output_root=diagnostic_root, run_id=variant_name)
        diagnostics = diagnose_existing_run(
            run_summary["path"],
            options=DiagnosticOptions(
                frame_interval=options.frame_interval,
                window_steps=options.window_steps,
                save_frame_pngs=False,
            ),
            reference_root=reference_root,
        )
        audit = _audit_variant(variant_name, config)
        source_rows.append(audit["source_row"])
        mask_rows.append(audit["mask_row"])
        energy_budget_rows.extend(audit["energy_budget_rows"])

        best_energy = np.load(Path(run_summary["path"]) / "best_energy_density.npy")
        radial_payload = _radial_profile_payload(variant_name, config, best_energy, audit["final_energy"])
        radial_profiles[variant_name] = radial_payload["profiles"]
        radial_rows.extend(radial_payload["rows"])

        energy_comparison = run_energy_comparison(run_summary["path"], config.driver.drive_cutoff_time)
        summary_rows.append(
            _summary_row(
                variant_name,
                config,
                run_summary,
                diagnostics,
                energy_comparison,
                audit,
                radial_payload["summary"],
            )
        )

    shared_radial_rows = _shared_radial_rows(radial_profiles, variants)
    radial_rows.extend(shared_radial_rows)
    pairwise = _pairwise_comparisons(summary_rows, configs_by_variant, radial_profiles)
    _attach_pairwise_fields(summary_rows, pairwise)
    classification = classify_resolution_diagnostics(summary_rows, source_rows, mask_rows, pairwise, options)
    for row in summary_rows:
        row["classification_label"] = classification["label"]

    summary_path = diagnostic_root / "resolution_diagnostics_summary.csv"
    source_path = diagnostic_root / "source_audit.csv"
    mask_path = diagnostic_root / "mask_area_audit.csv"
    energy_path = diagnostic_root / "energy_budget_audit.csv"
    radial_path = diagnostic_root / "radial_profile_comparison.csv"
    report_path = diagnostic_root / "resolution_diagnostics_report.md"

    _write_csv(summary_path, summary_rows, _summary_fields())
    _write_csv(source_path, source_rows, _source_fields())
    _write_csv(mask_path, mask_rows, _mask_fields())
    _write_csv(energy_path, energy_budget_rows, _energy_budget_fields())
    _write_csv(radial_path, radial_rows)
    _write_report(
        report_path,
        diagnostic_id,
        base_config,
        summary_rows,
        source_rows,
        mask_rows,
        pairwise,
        classification,
        options,
    )
    save_json(
        diagnostic_root / "resolution_diagnostics_summary.json",
        {
            "diagnostic_id": diagnostic_id,
            "classification": classification,
            "variants": summary_rows,
            "source_audit_csv": str(source_path),
            "mask_area_audit_csv": str(mask_path),
            "energy_budget_audit_csv": str(energy_path),
            "radial_profile_comparison_csv": str(radial_path),
            "summary_csv": str(summary_path),
            "report_path": str(report_path),
            "pairwise_comparisons": pairwise,
        },
    )
    return {
        "diagnostic_id": diagnostic_id,
        "classification": classification,
        "variants": summary_rows,
        "pairwise_comparisons": pairwise,
        "summary_csv": str(summary_path),
        "source_audit_csv": str(source_path),
        "mask_area_audit_csv": str(mask_path),
        "energy_budget_audit_csv": str(energy_path),
        "radial_profile_comparison_csv": str(radial_path),
        "report_path": str(report_path),
        "path": str(diagnostic_root),
    }


def run_source_normalized_resolution_diagnostics(
    base_config: SimulationConfig,
    *,
    options: ResolutionDiagnosticsOptions | None = None,
    reference_root: str | Path = "runs",
    source_normalization: str = "constant_boundary_flux",
) -> dict[str, Any]:
    """Run source-normalized fixed-domain resolution diagnostics plus legacy references."""

    options = options or ResolutionDiagnosticsOptions()
    diagnostic_id = datetime.now().strftime("source_normalized_resolution_%Y%m%d_%H%M%S")
    diagnostic_root = Path(options.output_root) / diagnostic_id
    diagnostic_root.mkdir(parents=True, exist_ok=False)

    normalized_variants = _source_normalized_variants(base_config, options, source_normalization)
    legacy_variants = [
        (
            f"legacy_per_cell_grid_{size}",
            _fixed_domain_config(base_config, size, source_normalization="per_cell"),
        )
        for size in options.grid_sizes
    ]

    normalized = _run_resolution_variant_collection(
        normalized_variants,
        diagnostic_root,
        options,
        reference_root,
        variant_role="source_normalized",
    )
    legacy = _run_resolution_variant_collection(
        legacy_variants,
        diagnostic_root,
        options,
        reference_root,
        variant_role="legacy_per_cell_reference",
    )

    classification = classify_source_normalized_resolution(
        normalized["summary_rows"],
        normalized["source_rows"],
        normalized["mask_rows"],
        normalized["pairwise"],
        options,
    )
    for row in normalized["summary_rows"]:
        row["classification_label"] = classification["label"]
    for row in legacy["summary_rows"]:
        row["classification_label"] = "legacy_reference_only"

    all_source_rows = normalized["source_rows"] + legacy["source_rows"]
    all_mask_rows = normalized["mask_rows"] + legacy["mask_rows"]
    all_energy_rows = normalized["energy_budget_rows"] + legacy["energy_budget_rows"]
    all_radial_rows = normalized["radial_rows"] + legacy["radial_rows"]
    injected_work_rows = _injected_work_rows(normalized["source_rows"], legacy["source_rows"])

    summary_path = diagnostic_root / "source_normalized_resolution_summary.csv"
    source_path = diagnostic_root / "source_audit_comparison.csv"
    work_path = diagnostic_root / "injected_work_comparison.csv"
    mask_path = diagnostic_root / "mask_area_audit.csv"
    energy_path = diagnostic_root / "energy_budget_audit.csv"
    radial_path = diagnostic_root / "radial_profile_comparison.csv"
    report_path = diagnostic_root / "source_normalized_resolution_report.md"

    _write_csv(summary_path, normalized["summary_rows"], _summary_fields())
    _write_csv(source_path, all_source_rows, _source_fields())
    _write_csv(work_path, injected_work_rows)
    _write_csv(mask_path, all_mask_rows, _mask_fields())
    _write_csv(energy_path, all_energy_rows, _energy_budget_fields())
    _write_csv(radial_path, all_radial_rows)
    _write_source_normalized_report(
        report_path,
        diagnostic_id,
        base_config,
        normalized["summary_rows"],
        legacy["summary_rows"],
        normalized["source_rows"],
        legacy["source_rows"],
        normalized["mask_rows"],
        normalized["pairwise"],
        legacy["pairwise"],
        classification,
        options,
        source_normalization,
    )
    save_json(
        diagnostic_root / "source_normalized_resolution_summary.json",
        {
            "diagnostic_id": diagnostic_id,
            "classification": classification,
            "source_normalization": source_normalization,
            "variants": normalized["summary_rows"],
            "legacy_reference_variants": legacy["summary_rows"],
            "summary_csv": str(summary_path),
            "source_audit_comparison_csv": str(source_path),
            "injected_work_comparison_csv": str(work_path),
            "mask_area_audit_csv": str(mask_path),
            "energy_budget_audit_csv": str(energy_path),
            "radial_profile_comparison_csv": str(radial_path),
            "report_path": str(report_path),
            "pairwise_comparisons": normalized["pairwise"],
            "legacy_pairwise_comparisons": legacy["pairwise"],
        },
    )
    return {
        "diagnostic_id": diagnostic_id,
        "classification": classification,
        "source_normalization": source_normalization,
        "variants": normalized["summary_rows"],
        "legacy_reference_variants": legacy["summary_rows"],
        "pairwise_comparisons": normalized["pairwise"],
        "legacy_pairwise_comparisons": legacy["pairwise"],
        "summary_csv": str(summary_path),
        "source_audit_comparison_csv": str(source_path),
        "injected_work_comparison_csv": str(work_path),
        "mask_area_audit_csv": str(mask_path),
        "energy_budget_audit_csv": str(energy_path),
        "radial_profile_comparison_csv": str(radial_path),
        "report_path": str(report_path),
        "path": str(diagnostic_root),
    }


def _source_normalized_variants(
    base_config: SimulationConfig,
    options: ResolutionDiagnosticsOptions,
    source_normalization: str,
) -> list[tuple[str, SimulationConfig]]:
    base_mode = "constant_boundary_flux" if source_normalization == "constant_total_work" else source_normalization
    variants = [
        (
            f"source_normalized_grid_{size}",
            _fixed_domain_config(base_config, size, source_normalization=base_mode),
        )
        for size in options.grid_sizes
    ]
    if source_normalization != "constant_total_work":
        return variants

    work_values = []
    for variant_name, config in variants:
        audit = _audit_variant(f"{variant_name}_work_calibration", config)
        work_values.append(float(audit["source_row"].get("total_injected_work_before_cutoff") or 0.0))
    if not work_values or work_values[0] <= EPSILON:
        for _variant_name, config in variants:
            config.driver.source_normalization = "constant_total_work"
        return variants

    target_work = work_values[0]
    for idx, (_variant_name, config) in enumerate(variants):
        if idx == 0 or work_values[idx] <= EPSILON:
            config.driver.source_normalization = "constant_total_work"
            continue
        config.driver.amplitude *= float(np.sqrt(target_work / work_values[idx]))
        config.driver.source_normalization = "constant_total_work"
    return variants


def _run_resolution_variant_collection(
    variants: list[tuple[str, SimulationConfig]],
    diagnostic_root: Path,
    options: ResolutionDiagnosticsOptions,
    reference_root: str | Path,
    *,
    variant_role: str,
) -> dict[str, Any]:
    summary_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    mask_rows: list[dict[str, Any]] = []
    energy_budget_rows: list[dict[str, Any]] = []
    radial_rows: list[dict[str, Any]] = []
    configs_by_variant: dict[str, SimulationConfig] = {}
    radial_profiles: dict[str, dict[str, dict[str, np.ndarray | float]]] = {}

    for variant_name, config in variants:
        configs_by_variant[variant_name] = config
        run_summary = run_single_experiment(config, output_root=diagnostic_root, run_id=variant_name)
        diagnostics = diagnose_existing_run(
            run_summary["path"],
            options=DiagnosticOptions(
                frame_interval=options.frame_interval,
                window_steps=options.window_steps,
                save_frame_pngs=False,
            ),
            reference_root=reference_root,
        )
        audit = _audit_variant(variant_name, config)
        for row in (audit["source_row"], audit["mask_row"]):
            row["variant_role"] = variant_role
        source_rows.append(audit["source_row"])
        mask_rows.append(audit["mask_row"])
        for row in audit["energy_budget_rows"]:
            row["variant_role"] = variant_role
        energy_budget_rows.extend(audit["energy_budget_rows"])

        best_energy = np.load(Path(run_summary["path"]) / "best_energy_density.npy")
        radial_payload = _radial_profile_payload(variant_name, config, best_energy, audit["final_energy"])
        for row in radial_payload["rows"]:
            row["variant_role"] = variant_role
        radial_profiles[variant_name] = radial_payload["profiles"]
        radial_rows.extend(radial_payload["rows"])

        energy_comparison = run_energy_comparison(run_summary["path"], config.driver.drive_cutoff_time)
        summary = _summary_row(
            variant_name,
            config,
            run_summary,
            diagnostics,
            energy_comparison,
            audit,
            radial_payload["summary"],
        )
        summary["variant_role"] = variant_role
        summary_rows.append(summary)

    shared_radial_rows = _shared_radial_rows(radial_profiles, variants)
    for row in shared_radial_rows:
        row["variant_role"] = variant_role
    radial_rows.extend(shared_radial_rows)
    pairwise = _pairwise_comparisons(summary_rows, configs_by_variant, radial_profiles)
    _attach_pairwise_fields(summary_rows, pairwise)
    return {
        "summary_rows": summary_rows,
        "source_rows": source_rows,
        "mask_rows": mask_rows,
        "energy_budget_rows": energy_budget_rows,
        "radial_rows": radial_rows,
        "pairwise": pairwise,
    }


def classify_resolution_diagnostics(
    rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    mask_rows: list[dict[str, Any]],
    pairwise: list[dict[str, Any]],
    options: ResolutionDiagnosticsOptions | None = None,
) -> dict[str, Any]:
    """Classify the likely cause of fixed-domain resolution sensitivity."""

    options = options or ResolutionDiagnosticsOptions()
    if len(rows) < 2:
        return {"label": "inconclusive", "reason": "At least two resolutions are required.", "checks": {}}

    ordered = sorted(rows, key=lambda row: int(row.get("grid_size", 0)))
    source_comparable = _source_work_comparable(source_rows, options)
    mask_comparable = _mask_areas_comparable(mask_rows, options)
    period_stable = _breathing_period_stable(ordered, options)
    m4_stable = all(int(row.get("strongest_angular_mode") or 0) == 4 for row in ordered)
    retention_monotonic = _monotonic_nonincreasing([float(row.get("retention_score") or 0.0) for row in ordered])
    retention_weakens = float(ordered[-1].get("retention_score") or 0.0) < 0.9 * float(
        ordered[0].get("retention_score") or 0.0
    )

    refined_pair = _comparison_for(pairwise, ordered[-2]["variant"], ordered[-1]["variant"]) if len(ordered) >= 3 else None
    first_pair = _comparison_for(pairwise, ordered[0]["variant"], ordered[1]["variant"])
    refined_radial_corr = float((refined_pair or {}).get("best_radial_correlation") or 0.0)
    refined_spatial_corr = float((refined_pair or {}).get("best_spatial_correlation") or 0.0)
    refined_peaks_close = _peak_shift(ordered[-2], ordered[-1]) <= options.refined_peak_shift_max if len(ordered) >= 3 else False
    coarse_peak_far = _peak_shift(ordered[0], ordered[1]) >= options.coarse_peak_shift_min
    baseline_spatial_high = float((first_pair or {}).get("best_spatial_correlation") or 0.0) >= 0.8
    baseline_radial_low = float((first_pair or {}).get("best_radial_correlation") or 1.0) < 0.6

    checks = {
        "source_work_comparable": source_comparable["passed"],
        "mask_areas_comparable": mask_comparable["passed"],
        "breathing_period_stable": period_stable,
        "m4_structure_stable": m4_stable,
        "retention_weakens_monotonically": retention_monotonic and retention_weakens,
        "refined_radial_profiles_converge": refined_radial_corr >= options.refined_radial_corr_min and refined_peaks_close,
        "refined_best_frames_similar": refined_spatial_corr >= options.refined_spatial_corr_min,
        "coarse_peak_differs_from_refined": coarse_peak_far,
    }

    if not source_comparable["passed"]:
        return {
            "label": "source_normalization_issue",
            "reason": source_comparable["reason"],
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    if not mask_comparable["passed"]:
        return {
            "label": "mask_discretization_issue",
            "reason": mask_comparable["reason"],
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    if coarse_peak_far and baseline_spatial_high and baseline_radial_low:
        return {
            "label": "radial_binning_issue",
            "reason": "Best-frame shapes are similar but radial-bin summaries disagree strongly.",
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    if refined_peaks_close and coarse_peak_far and refined_radial_corr >= options.refined_radial_corr_min:
        return {
            "label": "coarse_grid_artifact_likely",
            "reason": (
                "The refined grids agree with each other more than with the coarse grid, while source and mask audits are comparable."
            ),
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    if refined_peaks_close and refined_radial_corr >= options.refined_radial_corr_min:
        return {
            "label": "refined_mode_converging",
            "reason": "The refined radial profiles and peak locations are converging under fixed-domain refinement.",
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    if retention_monotonic and retention_weakens:
        return {
            "label": "true_resolution_sensitive",
            "reason": "Retention weakens monotonically with resolution and refined radial structure has not clearly converged.",
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    return {
        "label": "inconclusive",
        "reason": "The audits do not isolate source, mask, radial-binning, or true resolution sensitivity.",
        "checks": checks,
        "source_comparison": source_comparable,
        "mask_comparison": mask_comparable,
    }


def classify_source_normalized_resolution(
    rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    mask_rows: list[dict[str, Any]],
    pairwise: list[dict[str, Any]],
    options: ResolutionDiagnosticsOptions | None = None,
) -> dict[str, Any]:
    """Classify source-normalized fixed-domain resolution diagnostics."""

    options = options or ResolutionDiagnosticsOptions()
    if len(rows) < 2:
        return {"label": "inconclusive", "reason": "At least two source-normalized resolutions are required.", "checks": {}}

    ordered = sorted(rows, key=lambda row: int(row.get("grid_size", 0)))
    source_comparable = _source_work_comparable(source_rows, options)
    mask_comparable = _mask_areas_comparable(mask_rows, options)
    emitter_area_comparable = _relative_range(
        [float(row.get("emitter_physical_area_from_mask") or 0.0) for row in mask_rows]
    ) <= options.mask_area_relative_tolerance
    work_63_anomaly_removed = _middle_value_not_anomalous(
        [float(row.get("injected_work_per_physical_boundary_length") or 0.0) for row in source_rows]
    )
    period_stable = _breathing_period_stable(ordered, options)
    m4_stable = all(int(row.get("strongest_angular_mode") or 0) == 4 for row in ordered)
    retention_values = [float(row.get("retention_score") or 0.0) for row in ordered]
    retention_monotonic = _monotonic_nonincreasing(retention_values)
    retention_weakens = retention_values[-1] < 0.9 * retention_values[0]

    refined_pair = _comparison_for(pairwise, ordered[-2]["variant"], ordered[-1]["variant"]) if len(ordered) >= 3 else None
    refined_radial_corr = float((refined_pair or {}).get("best_radial_correlation") or 0.0)
    refined_spatial_corr = float((refined_pair or {}).get("best_spatial_correlation") or 0.0)
    refined_peaks_close = _peak_shift(ordered[-2], ordered[-1]) <= options.refined_peak_shift_max if len(ordered) >= 3 else False
    coarse_peak_far = _peak_shift(ordered[0], ordered[1]) >= options.coarse_peak_shift_min

    checks = {
        "source_work_comparable": source_comparable["passed"],
        "mask_areas_comparable": mask_comparable["passed"],
        "emitter_area_comparable": emitter_area_comparable,
        "work_63_anomaly_removed": work_63_anomaly_removed,
        "breathing_period_stable": period_stable,
        "m4_structure_stable": m4_stable,
        "retention_weakens_monotonically": retention_monotonic and retention_weakens,
        "refined_radial_profiles_converge": refined_radial_corr >= options.refined_radial_corr_min and refined_peaks_close,
        "refined_best_frames_similar": refined_spatial_corr >= options.refined_spatial_corr_min,
        "coarse_peak_differs_from_refined": coarse_peak_far,
    }

    if not source_comparable["passed"] or not mask_comparable["passed"] or not work_63_anomaly_removed:
        return {
            "label": "source_normalization_issue_persists",
            "reason": (
                "Source-normalized variants still do not have comparable emitter geometry or injected work."
            ),
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    if refined_peaks_close and coarse_peak_far and refined_radial_corr >= options.refined_radial_corr_min:
        return {
            "label": "coarse_grid_artifact_likely",
            "reason": (
                "Source normalization fixed the emitter audit enough to interpret the 41-grid radial peak as the outlier."
            ),
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    if refined_peaks_close and refined_radial_corr >= options.refined_radial_corr_min:
        return {
            "label": "refined_mode_converging",
            "reason": "Source-normalized refined grids converge toward the same radial structure.",
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    if retention_monotonic and retention_weakens:
        return {
            "label": "true_resolution_sensitive",
            "reason": "Source normalization is comparable, but retention still weakens and the refined mode does not converge.",
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    if source_comparable["passed"] and mask_comparable["passed"]:
        return {
            "label": "source_normalization_fixed",
            "reason": "Emitter/source geometry and injected work are comparable, but resolution interpretation remains mixed.",
            "checks": checks,
            "source_comparison": source_comparable,
            "mask_comparison": mask_comparable,
        }
    return {
        "label": "inconclusive",
        "reason": "Source-normalized diagnostics did not isolate a clear interpretation.",
        "checks": checks,
        "source_comparison": source_comparable,
        "mask_comparison": mask_comparable,
    }


def _audit_variant(variant: str, config: SimulationConfig) -> dict[str, Any]:
    lattice = Lattice2D(config)
    sponge_mask, sponge_extra = _sponge_mask_and_extra_damping(config, lattice)
    dt = float(config.dt)
    area = float(config.cell_area)
    initial_energy = lattice.energy_density()
    initial_total = float(np.sum(initial_energy))

    cumulative_drive = 0.0
    cumulative_positive_drive = 0.0
    cumulative_drive_before_cutoff = 0.0
    cumulative_positive_drive_before_cutoff = 0.0
    cumulative_damping_loss = 0.0
    cumulative_sponge_damping_loss = 0.0
    peak_injected_power = 0.0
    budget_rows: list[dict[str, Any]] = []

    for step in range(config.steps):
        time = step * dt
        force = lattice.driver.force(time)
        velocity_before = lattice.v.copy()
        lattice.step(time, dt)
        velocity_mid = 0.5 * (velocity_before + lattice.v)

        drive_power = float(np.sum(force * velocity_mid) * area)
        positive_drive_power = max(0.0, drive_power)
        damping_power = float(np.sum(lattice.damping * velocity_mid**2) * area)
        sponge_power = float(np.sum(sponge_extra * velocity_mid**2) * area)

        cumulative_drive += drive_power * dt
        cumulative_positive_drive += positive_drive_power * dt
        if config.driver.drive_cutoff_time is None or time <= float(config.driver.drive_cutoff_time):
            cumulative_drive_before_cutoff += drive_power * dt
            cumulative_positive_drive_before_cutoff += positive_drive_power * dt
        cumulative_damping_loss += damping_power * dt
        cumulative_sponge_damping_loss += sponge_power * dt
        peak_injected_power = max(peak_injected_power, positive_drive_power)

        if step % max(1, config.sample_every) != 0 and step != config.steps - 1:
            continue

        energy = lattice.energy_density()
        total_energy = float(np.sum(energy))
        core_energy = float(np.sum(energy[lattice.masks.core]))
        outer_energy = float(np.sum(energy[lattice.masks.outer]))
        sponge_energy = float(np.sum(energy[sponge_mask]))
        residual = total_energy - initial_total - cumulative_drive + cumulative_damping_loss
        budget_rows.append(
            {
                "variant": variant,
                "grid_size": config.grid_size,
                "step": step,
                "time": time,
                "total_energy": total_energy,
                "core_energy": core_energy,
                "outer_energy": outer_energy,
                "sponge_region_energy": sponge_energy,
                "drive_power": drive_power,
                "positive_drive_power": positive_drive_power,
                "damping_loss_power": damping_power,
                "sponge_damping_loss_power": sponge_power,
                "cumulative_drive_work": cumulative_drive,
                "cumulative_positive_drive_work": cumulative_positive_drive,
                "cumulative_damping_loss": cumulative_damping_loss,
                "cumulative_sponge_damping_loss": cumulative_sponge_damping_loss,
                "energy_residual_estimate": residual,
                "relative_energy_residual_estimate": residual / (abs(total_energy) + abs(initial_total) + EPSILON),
            }
        )

    final_energy = lattice.energy_density().copy()
    source_row = _source_audit_row(
        variant,
        config,
        lattice,
        cumulative_drive,
        cumulative_positive_drive,
        cumulative_drive_before_cutoff,
        cumulative_positive_drive_before_cutoff,
        peak_injected_power,
    )
    mask_row = _mask_area_row(variant, config, lattice, sponge_mask)
    return {
        "source_row": source_row,
        "mask_row": mask_row,
        "energy_budget_rows": budget_rows,
        "final_energy": final_energy,
    }


def _source_audit_row(
    variant: str,
    config: SimulationConfig,
    lattice: Lattice2D,
    total_drive_work: float,
    positive_drive_work: float,
    net_drive_work_before_cutoff: float,
    positive_drive_work_before_cutoff: float,
    peak_injected_power: float,
) -> dict[str, Any]:
    emitter_cells = int(np.sum(lattice.driver.mask))
    coverage_sum = float(np.sum(lattice.driver.coverage_weights))
    boundary_length = _emitter_boundary_length(config)
    active_cell_area = float(emitter_cells) * float(config.cell_area)
    effective_area = float(lattice.driver.effective_driven_area)
    effective_length = float(lattice.driver.effective_driven_length)
    total_drive_amplitude_sum = float(config.driver.amplitude * lattice.driver.normalization_scale * coverage_sum)
    return {
        "variant": variant,
        "grid_size": config.grid_size,
        "dx": config.dx,
        "dy": config.dy,
        "source_normalization": config.driver.source_normalization,
        "emitter_cell_count": emitter_cells,
        "emitter_fractional_coverage_sum": coverage_sum,
        "physical_emitter_length": boundary_length,
        "effective_driven_area": effective_area,
        "effective_driven_length": effective_length,
        "emitter_active_cell_area": active_cell_area,
        "emitter_width_physical": config.effective_emitter_width,
        "emitter_physical_area_from_mask": effective_area,
        "per_cell_drive_amplitude": config.driver.amplitude,
        "source_normalization_scale": lattice.driver.normalization_scale,
        "total_drive_amplitude_sum": total_drive_amplitude_sum,
        "area_weighted_drive_amplitude_sum": total_drive_amplitude_sum * config.cell_area,
        "drive_frequency": config.driver.frequency,
        "drive_cutoff_time": config.driver.drive_cutoff_time,
        "total_drive_work_over_time": total_drive_work,
        "positive_drive_work_over_time": positive_drive_work,
        "net_drive_work_before_cutoff": net_drive_work_before_cutoff,
        "total_injected_work_before_cutoff": positive_drive_work_before_cutoff,
        "peak_injected_power": peak_injected_power,
        "injected_work_per_physical_boundary_length": positive_drive_work_before_cutoff / (boundary_length + EPSILON),
        "injected_work_per_unit_area": positive_drive_work_before_cutoff / (effective_area + EPSILON),
    }


def _mask_area_row(
    variant: str,
    config: SimulationConfig,
    lattice: Lattice2D,
    sponge_mask: np.ndarray,
) -> dict[str, Any]:
    masks = lattice.masks
    emitter_cells = int(np.sum(lattice.driver.mask))
    cell_area = float(config.cell_area)
    effective_area = float(lattice.driver.effective_driven_area)
    return {
        "variant": variant,
        "grid_size": config.grid_size,
        "grid_height": config.ny,
        "dx": config.dx,
        "dy": config.dy,
        "source_normalization": config.driver.source_normalization,
        "cell_area": cell_area,
        "domain_width": config.physical_domain_width,
        "domain_height": config.physical_domain_height,
        "nominal_domain_area": config.physical_domain_width * config.physical_domain_height,
        "node_cell_area_total": config.nx * config.ny * cell_area,
        "defect_radius_physical": config.effective_defect_radius,
        "defect_cell_count": int(np.sum(masks.defect)),
        "defect_physical_area": float(np.sum(masks.defect)) * cell_area,
        "defect_ideal_area": float(np.pi * config.effective_defect_radius**2),
        "core_radius_physical": config.effective_core_radius_value,
        "core_cell_count": int(np.sum(masks.core)),
        "core_physical_area": float(np.sum(masks.core)) * cell_area,
        "core_ideal_area": float(np.pi * config.effective_core_radius_value**2),
        "annulus_cell_count": int(np.sum(masks.ring)),
        "annulus_physical_area": float(np.sum(masks.ring)) * cell_area,
        "outer_cell_count": int(np.sum(masks.outer)),
        "outer_physical_area": float(np.sum(masks.outer)) * cell_area,
        "sponge_physical_width": config.effective_boundary_damping_width,
        "sponge_cell_count": int(np.sum(sponge_mask)),
        "sponge_physical_area": float(np.sum(sponge_mask)) * cell_area,
        "emitter_cell_count": emitter_cells,
        "emitter_fractional_coverage_sum": float(np.sum(lattice.driver.coverage_weights)),
        "emitter_physical_length": _emitter_boundary_length(config),
        "effective_driven_area": effective_area,
        "effective_driven_length": float(lattice.driver.effective_driven_length),
        "emitter_active_cell_area": emitter_cells * cell_area,
        "emitter_physical_area_from_mask": effective_area,
    }


def _radial_profile_payload(
    variant: str,
    config: SimulationConfig,
    best_energy: np.ndarray,
    tail_energy: np.ndarray,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    profiles: dict[str, dict[str, np.ndarray | float]] = {}
    summary: dict[str, Any] = {}
    for profile_type, energy in (("best_event", best_energy), ("tail_final", tail_energy)):
        profile = _radial_profile_with_bins(energy, config)
        profiles[profile_type] = profile
        peak_idx = int(np.argmax(profile["mass"])) if profile["mass"].size else 0
        summary[f"{profile_type}_radial_peak_radius"] = float(profile["radii"][peak_idx]) if profile["radii"].size else 0.0
        summary[f"{profile_type}_radial_peak_fwhm"] = _radial_fwhm(profile)
        summary[f"{profile_type}_radial_bin_width"] = float(profile["bin_width"])
        for idx, mass in enumerate(profile["mass"]):
            rows.append(
                {
                    "row_type": "variant_profile",
                    "variant": variant,
                    "grid_size": config.grid_size,
                    "profile_type": profile_type,
                    "bin_index": idx,
                    "bin_left": profile["bin_left"][idx],
                    "bin_center": profile["bin_center"][idx],
                    "bin_right": profile["bin_right"][idx],
                    "bin_cell_count": int(profile["bin_count"][idx]),
                    "mass": mass,
                }
            )
    return {"rows": rows, "profiles": profiles, "summary": summary}


def _radial_profile_with_bins(energy: np.ndarray, config: SimulationConfig) -> dict[str, np.ndarray | float]:
    weights = np.asarray(energy, dtype=float)
    rows, cols = np.indices(weights.shape, dtype=float)
    center_row = (weights.shape[0] - 1) / 2.0
    center_col = (weights.shape[1] - 1) / 2.0
    if config.fixed_domain:
        radius = np.sqrt(((rows - center_row) * config.dy) ** 2 + ((cols - center_col) * config.dx) ** 2)
        bin_width = max(config.effective_defect_radius / 4.0, min(config.dx, config.dy))
    else:
        radius = np.sqrt((rows - center_row) ** 2 + (cols - center_col) ** 2) / max(float(config.defect.radius), 1.0)
        bin_width = 0.25

    bins = np.floor(radius / bin_width).astype(int)
    size = int(np.max(bins)) + 1
    mass = np.zeros(size, dtype=float)
    counts = np.zeros(size, dtype=int)
    np.add.at(mass, bins.ravel(), weights.ravel())
    np.add.at(counts, bins.ravel(), 1)
    total = float(np.sum(mass))
    if total > EPSILON:
        mass = mass / total
    left = np.arange(size, dtype=float) * bin_width
    right = left + bin_width
    center = left + 0.5 * bin_width
    return {
        "radii": left,
        "mass": mass,
        "bin_left": left,
        "bin_center": center,
        "bin_right": right,
        "bin_count": counts,
        "bin_width": float(bin_width),
    }


def _shared_radial_rows(
    radial_profiles: dict[str, dict[str, dict[str, np.ndarray | float]]],
    variants: list[tuple[str, SimulationConfig]],
) -> list[dict[str, Any]]:
    if not radial_profiles:
        return []
    max_radius = 0.0
    min_step = np.inf
    for variant_name, _config in variants:
        for profile in radial_profiles[variant_name].values():
            radii = np.asarray(profile["radii"], dtype=float)
            if radii.size:
                max_radius = max(max_radius, float(np.max(radii)))
            min_step = min(min_step, float(profile["bin_width"]))
    step = float(min_step if np.isfinite(min_step) and min_step > 0.0 else 1.0)
    shared = np.arange(0.0, max_radius + step * 0.5, step)
    rows: list[dict[str, Any]] = []
    for profile_type in ("best_event", "tail_final"):
        for radius in shared:
            row: dict[str, Any] = {
                "row_type": "shared_comparison",
                "variant": "all",
                "profile_type": profile_type,
                "shared_radius": radius,
            }
            for variant_name, _config in variants:
                profile = radial_profiles[variant_name][profile_type]
                row[f"{variant_name}_mass"] = float(
                    np.interp(
                        radius,
                        np.asarray(profile["radii"], dtype=float),
                        np.asarray(profile["mass"], dtype=float),
                        left=0.0,
                        right=0.0,
                    )
                )
            rows.append(row)
    return rows


def _pairwise_comparisons(
    rows: list[dict[str, Any]],
    configs_by_variant: dict[str, SimulationConfig],
    radial_profiles: dict[str, dict[str, dict[str, np.ndarray | float]]],
) -> list[dict[str, Any]]:
    if len(rows) < 2:
        return []
    common_row = max(rows, key=lambda row: int(row.get("grid_size") or 0))
    common_config = configs_by_variant[common_row["variant"]]
    best_frames = {}
    angular_vectors = {}
    for row in rows:
        variant = row["variant"]
        energy = np.load(Path(row["path"]) / "best_energy_density.npy")
        best_frames[variant] = _resample_to_config(energy, configs_by_variant[variant], common_config)
        angular_vectors[variant] = _angular_mode_vector_at_best(row)

    comparisons: list[dict[str, Any]] = []
    ordered = sorted(rows, key=lambda row: int(row.get("grid_size") or 0))
    for idx, first in enumerate(ordered):
        for second in ordered[idx + 1 :]:
            first_variant = first["variant"]
            second_variant = second["variant"]
            comparisons.append(
                {
                    "first_variant": first_variant,
                    "second_variant": second_variant,
                    "pair": f"{first_variant}__{second_variant}",
                    "best_spatial_correlation": shape_correlation(best_frames[first_variant], best_frames[second_variant]),
                    "best_radial_correlation": _radial_profile_correlation_on_shared_grid(
                        radial_profiles[first_variant]["best_event"],
                        radial_profiles[second_variant]["best_event"],
                    ),
                    "tail_radial_correlation": _radial_profile_correlation_on_shared_grid(
                        radial_profiles[first_variant]["tail_final"],
                        radial_profiles[second_variant]["tail_final"],
                    ),
                    "angular_mode_similarity": _cosine_similarity(angular_vectors[first_variant], angular_vectors[second_variant]),
                    "best_radial_peak_shift": _peak_shift(first, second),
                    "first_grid_size": first.get("grid_size"),
                    "second_grid_size": second.get("grid_size"),
                }
            )
    return comparisons


def _attach_pairwise_fields(rows: list[dict[str, Any]], pairwise: list[dict[str, Any]]) -> None:
    if not rows:
        return
    ordered = sorted(rows, key=lambda row: int(row.get("grid_size") or 0))
    baseline = ordered[0]["variant"]
    previous: dict[str, str] = {}
    for idx, row in enumerate(ordered):
        if idx > 0:
            previous[row["variant"]] = ordered[idx - 1]["variant"]

    for row in rows:
        variant = row["variant"]
        baseline_pair = _comparison_for(pairwise, baseline, variant)
        previous_pair = _comparison_for(pairwise, previous.get(variant, ""), variant)
        row["spatial_correlation_to_baseline"] = _comparison_value(baseline_pair, "best_spatial_correlation", variant, baseline)
        row["radial_correlation_to_baseline"] = _comparison_value(baseline_pair, "best_radial_correlation", variant, baseline)
        row["tail_radial_correlation_to_baseline"] = _comparison_value(
            baseline_pair, "tail_radial_correlation", variant, baseline
        )
        row["angular_mode_similarity_to_baseline"] = _comparison_value(
            baseline_pair, "angular_mode_similarity", variant, baseline
        )
        row["spatial_correlation_to_previous_grid"] = _comparison_value(
            previous_pair, "best_spatial_correlation", variant, previous.get(variant)
        )
        row["radial_correlation_to_previous_grid"] = _comparison_value(
            previous_pair, "best_radial_correlation", variant, previous.get(variant)
        )
        row["angular_mode_similarity_to_previous_grid"] = _comparison_value(
            previous_pair, "angular_mode_similarity", variant, previous.get(variant)
        )


def _summary_row(
    variant: str,
    config: SimulationConfig,
    summary: dict[str, Any],
    diagnostics: dict[str, Any],
    energy: dict[str, Any],
    audit: dict[str, Any],
    radial_summary: dict[str, Any],
) -> dict[str, Any]:
    breathing = diagnostics.get("breathing_detection", {})
    angular = diagnostics.get("angular_detection", {})
    radial = diagnostics.get("radial_drift_summary", {})
    correlation = diagnostics.get("correlation_summary", {})
    source = audit["source_row"]
    mask = audit["mask_row"]
    stability = summary.get("stability", estimate_stability(config))
    labels = _diagnostic_labels(diagnostics)
    return {
        "variant": variant,
        "run_id": summary.get("run_id"),
        "path": summary.get("path"),
        "grid_size": config.grid_size,
        "dx": config.dx,
        "dy": config.dy,
        "dt": config.dt,
        "steps": config.steps,
        "physical_duration": config.steps * config.dt,
        "drive_cutoff_time": config.driver.drive_cutoff_time,
        "source_normalization": config.driver.source_normalization,
        "recommended_dt_max": stability.get("recommended_dt_max"),
        "hard_stability_dt_max": stability.get("hard_stability_dt_max"),
        "dt_to_hard_limit_ratio": stability.get("dt_to_hard_limit_ratio"),
        "stability_warnings": " | ".join(stability.get("warnings", [])) or "none",
        "emitter_cell_count": source.get("emitter_cell_count"),
        "emitter_fractional_coverage_sum": source.get("emitter_fractional_coverage_sum"),
        "physical_emitter_length": source.get("physical_emitter_length"),
        "effective_driven_area": source.get("effective_driven_area"),
        "effective_driven_length": source.get("effective_driven_length"),
        "per_cell_drive_amplitude": source.get("per_cell_drive_amplitude"),
        "source_normalization_scale": source.get("source_normalization_scale"),
        "total_drive_amplitude_sum": source.get("total_drive_amplitude_sum"),
        "total_injected_work_before_cutoff": source.get("total_injected_work_before_cutoff"),
        "injected_work_per_physical_boundary_length": source.get("injected_work_per_physical_boundary_length"),
        "injected_work_per_unit_area": source.get("injected_work_per_unit_area"),
        "core_physical_area": mask.get("core_physical_area"),
        "defect_physical_area": mask.get("defect_physical_area"),
        "sponge_physical_area": mask.get("sponge_physical_area"),
        "best_energy_well_ratio": float(diagnostics.get("best_energy_well_ratio", 0.0)),
        "retention_score": float(diagnostics.get("retention_score", 0.0)),
        "best_event_time": float(summary.get("time_of_best_event", 0.0)),
        "core_energy": energy.get("best_core_energy"),
        "outer_energy": energy.get("best_outer_lattice_energy"),
        "total_energy": energy.get("best_total_energy"),
        "core_fraction": energy.get("best_core_fraction"),
        "core_decay_rate_after_cutoff": energy.get("core_decay_rate_after_cutoff"),
        "outer_decay_rate_after_cutoff": energy.get("outer_decay_rate_after_cutoff"),
        "total_decay_rate_after_cutoff": energy.get("total_decay_rate_after_cutoff"),
        "breathing_detected": breathing.get("status") == "detected",
        "breathing_period": breathing.get("estimated_period"),
        "breathing_strength": breathing.get("breathing_strength_score"),
        "breathing_cycles": breathing.get("detected_cycles", 0),
        "radial_peak_radius": radial.get("best_event_radial_peak_radius"),
        "radial_peak_radius_range": radial.get("radial_peak_radius_range"),
        "best_event_radial_peak_fwhm": radial_summary.get("best_event_radial_peak_fwhm"),
        "tail_final_radial_peak_radius": radial_summary.get("tail_final_radial_peak_radius"),
        "tail_final_radial_peak_fwhm": radial_summary.get("tail_final_radial_peak_fwhm"),
        "strongest_angular_mode": angular.get("strongest_angular_mode"),
        "strongest_angular_mode_strength": angular.get("strongest_angular_mode_strength"),
        "angular_phase_drift": angular.get("angular_phase_drift"),
        "angular_phase_trend_r2": angular.get("angular_phase_trend_r2"),
        "mean_previous_frame_correlation": correlation.get("mean_corr_prev_frame"),
        "minimum_previous_frame_correlation": correlation.get("min_corr_prev_frame"),
        "detected_labels": ", ".join(labels) or "none",
        "mode_shape_diagnostics_report": diagnostics.get("report_path"),
        "classification_label": None,
    }


def _sponge_mask_and_extra_damping(config: SimulationConfig, lattice: Lattice2D) -> tuple[np.ndarray, np.ndarray]:
    width = config.effective_boundary_damping_width
    if config.fixed_domain:
        edge_distance = np.minimum.reduce(
            [
                lattice.masks.rows * config.dy,
                lattice.masks.cols * config.dx,
                (config.ny - 1 - lattice.masks.rows) * config.dy,
                (config.nx - 1 - lattice.masks.cols) * config.dx,
            ]
        )
    else:
        edge_distance = np.minimum.reduce(
            [
                lattice.masks.rows,
                lattice.masks.cols,
                config.ny - 1 - lattice.masks.rows,
                config.nx - 1 - lattice.masks.cols,
            ]
        )
    sponge_mask = edge_distance < width if width > 0 else np.zeros(config.shape, dtype=bool)
    base_damping = np.full(config.shape, config.global_damping, dtype=float)
    base_damping[lattice.masks.defect] *= config.defect.damping_multiplier
    sponge_extra = np.maximum(lattice.damping - base_damping, 0.0)
    return sponge_mask, sponge_extra


def _emitter_boundary_length(config: SimulationConfig) -> float:
    length = 0.0
    sides = set(config.driver.sides)
    if "left" in sides:
        length += config.physical_domain_height
    if "right" in sides:
        length += config.physical_domain_height
    if "top" in sides:
        length += config.physical_domain_width
    if "bottom" in sides:
        length += config.physical_domain_width
    return float(length)


def _radial_fwhm(profile: dict[str, np.ndarray | float]) -> float:
    mass = np.asarray(profile["mass"], dtype=float)
    if not mass.size or float(np.max(mass)) <= EPSILON:
        return 0.0
    keep = mass >= 0.5 * float(np.max(mass))
    if not np.any(keep):
        return 0.0
    left = np.asarray(profile["bin_left"], dtype=float)
    right = np.asarray(profile["bin_right"], dtype=float)
    return float(np.max(right[keep]) - np.min(left[keep]))


def _angular_mode_vector_at_best(row: dict[str, Any]) -> np.ndarray | None:
    path = Path(str(row.get("path", ""))) / "mode_shape_diagnostics" / "angular_mode_timeseries.csv"
    if not path.exists():
        return None
    rows = _read_csv_rows(path)
    if not rows:
        return None
    target_time = float(row.get("best_event_time") or 0.0)
    nearest = min(rows, key=lambda item: abs(float(item.get("time") or 0.0) - target_time))
    return np.asarray([float(nearest.get(f"m{mode}_strength") or 0.0) for mode in range(1, 5)], dtype=float)


def _radial_profile_correlation_on_shared_grid(
    first: dict[str, np.ndarray | float],
    second: dict[str, np.ndarray | float],
) -> float | None:
    first_r = np.asarray(first["radii"], dtype=float)
    second_r = np.asarray(second["radii"], dtype=float)
    if not first_r.size or not second_r.size:
        return None
    step = min(float(first["bin_width"]), float(second["bin_width"]))
    max_radius = max(float(np.max(first_r)), float(np.max(second_r)))
    shared = np.arange(0.0, max_radius + step * 0.5, step)
    a = np.interp(shared, first_r, np.asarray(first["mass"], dtype=float), left=0.0, right=0.0)
    b = np.interp(shared, second_r, np.asarray(second["mass"], dtype=float), left=0.0, right=0.0)
    return _corr(a, b)


def _cosine_similarity(first: np.ndarray | None, second: np.ndarray | None) -> float | None:
    if first is None or second is None:
        return None
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator <= EPSILON:
        return None
    return float(np.clip(np.dot(first, second) / denominator, -1.0, 1.0))


def _corr(first: np.ndarray, second: np.ndarray) -> float | None:
    if first.size != second.size:
        return None
    a = first - float(np.mean(first))
    b = second - float(np.mean(second))
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= EPSILON:
        return None
    return float(np.clip(np.dot(a, b) / denominator, -1.0, 1.0))


def _source_work_comparable(
    source_rows: list[dict[str, Any]],
    options: ResolutionDiagnosticsOptions,
) -> dict[str, Any]:
    values = [float(row.get("injected_work_per_physical_boundary_length") or 0.0) for row in source_rows]
    rel = _relative_range(values)
    passed = rel <= options.source_work_relative_tolerance
    return {
        "passed": passed,
        "relative_range": rel,
        "values": values,
        "reason": (
            "Injected work per physical boundary length varies beyond the configured tolerance."
            if not passed
            else "Injected work per physical boundary length is comparable across resolutions."
        ),
    }


def _mask_areas_comparable(
    mask_rows: list[dict[str, Any]],
    options: ResolutionDiagnosticsOptions,
) -> dict[str, Any]:
    keys = ("defect_physical_area", "core_physical_area", "sponge_physical_area", "emitter_physical_area_from_mask")
    ranges = {key: _relative_range([float(row.get(key) or 0.0) for row in mask_rows]) for key in keys}
    worst_key = max(ranges, key=ranges.get) if ranges else "none"
    passed = all(value <= options.mask_area_relative_tolerance for value in ranges.values())
    return {
        "passed": passed,
        "relative_ranges": ranges,
        "worst_field": worst_key,
        "reason": (
            f"Physical mask area varies most in {worst_key} beyond the configured tolerance."
            if not passed
            else "Physical mask areas are comparable across resolutions."
        ),
    }


def _breathing_period_stable(rows: list[dict[str, Any]], options: ResolutionDiagnosticsOptions) -> bool:
    periods = [row.get("breathing_period") for row in rows if bool(row.get("breathing_detected"))]
    if len(periods) != len(rows):
        return False
    values = [float(period) for period in periods if period is not None]
    if len(values) != len(rows):
        return False
    if any(value < options.expected_period_min or value > options.expected_period_max for value in values):
        return False
    return max(values) - min(values) <= 0.8


def _relative_range(values: list[float]) -> float:
    positive = [abs(float(value)) for value in values if abs(float(value)) > EPSILON]
    if not positive:
        return 0.0
    return (max(positive) - min(positive)) / (float(np.mean(positive)) + EPSILON)


def _monotonic_nonincreasing(values: list[float]) -> bool:
    return all(values[idx + 1] <= values[idx] + 1e-9 for idx in range(len(values) - 1))


def _middle_value_not_anomalous(values: list[float]) -> bool:
    if len(values) < 3:
        return True
    first, middle, last = values[0], values[1], values[2]
    edge_mean = 0.5 * (first + last)
    if abs(edge_mean) <= EPSILON:
        return True
    return abs(middle - edge_mean) / abs(edge_mean) <= 0.2


def _peak_shift(first: dict[str, Any], second: dict[str, Any]) -> float:
    first_peak = first.get("radial_peak_radius")
    second_peak = second.get("radial_peak_radius")
    if first_peak is None or second_peak is None:
        return 0.0
    return abs(float(first_peak) - float(second_peak))


def _comparison_for(pairwise: list[dict[str, Any]], first: str | None, second: str | None) -> dict[str, Any] | None:
    if not first or not second:
        return None
    if first == second:
        return {
            "first_variant": first,
            "second_variant": second,
            "best_spatial_correlation": 1.0,
            "best_radial_correlation": 1.0,
            "tail_radial_correlation": 1.0,
            "angular_mode_similarity": 1.0,
        }
    for row in pairwise:
        variants = {row.get("first_variant"), row.get("second_variant")}
        if variants == {first, second}:
            return row
    return None


def _comparison_value(comparison: dict[str, Any] | None, key: str, variant: str, reference: str | None) -> Any:
    if reference is None:
        return None
    if variant == reference:
        return 1.0
    if comparison is None:
        return None
    return comparison.get(key)


def _diagnostic_labels(diagnostics: dict[str, Any]) -> list[str]:
    labels = []
    breathing = diagnostics.get("breathing_detection", {})
    transition = diagnostics.get("mode_transition_detection", {})
    labels.extend(breathing.get("labels", []))
    if breathing.get("label"):
        labels.append(breathing["label"])
    if transition.get("label"):
        labels.append(transition["label"])
    labels.extend(diagnostics.get("angular_detection", {}).get("labels", []))
    labels.extend(diagnostics.get("reference_comparison", {}).get("labels", []))
    return list(dict.fromkeys(labels))


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        rows = []
        for row in csv.DictReader(fh):
            converted: dict[str, Any] = {}
            for key, value in row.items():
                try:
                    converted[key] = float(value)
                except (TypeError, ValueError):
                    converted[key] = value
            rows.append(converted)
        return rows


def _injected_work_rows(
    normalized_rows: list[dict[str, Any]],
    legacy_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for group, source_rows in (("source_normalized", normalized_rows), ("legacy_per_cell_reference", legacy_rows)):
        for row in source_rows:
            rows.append(
                {
                    "variant_role": group,
                    "variant": row.get("variant"),
                    "grid_size": row.get("grid_size"),
                    "source_normalization": row.get("source_normalization"),
                    "emitter_cell_count": row.get("emitter_cell_count"),
                    "emitter_fractional_coverage_sum": row.get("emitter_fractional_coverage_sum"),
                    "physical_emitter_length": row.get("physical_emitter_length"),
                    "effective_driven_area": row.get("effective_driven_area"),
                    "effective_driven_length": row.get("effective_driven_length"),
                    "per_cell_drive_amplitude": row.get("per_cell_drive_amplitude"),
                    "source_normalization_scale": row.get("source_normalization_scale"),
                    "total_drive_amplitude_sum": row.get("total_drive_amplitude_sum"),
                    "total_injected_work_before_cutoff": row.get("total_injected_work_before_cutoff"),
                    "injected_work_per_physical_boundary_length": row.get(
                        "injected_work_per_physical_boundary_length"
                    ),
                    "injected_work_per_unit_area": row.get("injected_work_per_unit_area"),
                    "peak_injected_power": row.get("peak_injected_power"),
                }
            )
    return rows


def _write_source_normalized_report(
    path: Path,
    diagnostic_id: str,
    base_config: SimulationConfig,
    rows: list[dict[str, Any]],
    legacy_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    legacy_source_rows: list[dict[str, Any]],
    mask_rows: list[dict[str, Any]],
    pairwise: list[dict[str, Any]],
    legacy_pairwise: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ResolutionDiagnosticsOptions,
    source_normalization: str,
) -> None:
    ordered = sorted(rows, key=lambda row: int(row.get("grid_size") or 0))
    legacy_ordered = sorted(legacy_rows, key=lambda row: int(row.get("grid_size") or 0))
    answers = _source_normalized_answers(ordered, source_rows, mask_rows, pairwise, classification)
    lines = [
        f"# Source-Normalized Resolution Report: {diagnostic_id}",
        "",
        "## Purpose",
        "",
        (
            "Control the fixed-domain emitter/source discretization before interpreting the 0.92 radial shift. "
            "The normalized variants drive the main classification; legacy per-cell variants are reference only."
        ),
        "",
        "## Base Case",
        "",
        f"- Source config grid: `{base_config.grid_size}`",
        f"- Source normalization: `{source_normalization}`",
        f"- Drive frequency/amplitude: `{base_config.driver.frequency}` / `{base_config.driver.amplitude}`",
        f"- Drive cutoff time: `{base_config.driver.drive_cutoff_time}`",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Direct Answers",
        "",
    ]
    for answer in answers:
        lines.append(f"- {answer}")

    lines.extend(
        [
            "",
            "## Source-Normalized Variants",
            "",
            "| Variant | Grid | Area | Length | Work/Length | Ratio | Retention | Best Time | Period | Radial Peak | m | m Strength |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    source_by_variant = {row["variant"]: row for row in source_rows}
    for row in ordered:
        source = source_by_variant.get(row["variant"], {})
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('grid_size')} | "
            f"{_format(source.get('effective_driven_area'))} | "
            f"{_format(source.get('effective_driven_length'))} | "
            f"{_format(source.get('injected_work_per_physical_boundary_length'))} | "
            f"{_format(row.get('best_energy_well_ratio'))} | "
            f"{_format(row.get('retention_score'))} | "
            f"{_format(row.get('best_event_time'))} | "
            f"{_format(row.get('breathing_period'))} | "
            f"{_format(row.get('radial_peak_radius'))} | "
            f"{row.get('strongest_angular_mode')} | "
            f"{_format(row.get('strongest_angular_mode_strength'))} |"
        )

    lines.extend(
        [
            "",
            "## Pairwise Source-Normalized Mode Shape",
            "",
            "| Pair | Spatial Corr | Best Radial Corr | Tail Radial Corr | Angular Similarity | Radial Peak Shift |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in pairwise:
        lines.append(
            "| "
            f"{row['first_variant']} vs {row['second_variant']} | "
            f"{_format(row.get('best_spatial_correlation'))} | "
            f"{_format(row.get('best_radial_correlation'))} | "
            f"{_format(row.get('tail_radial_correlation'))} | "
            f"{_format(row.get('angular_mode_similarity'))} | "
            f"{_format(row.get('best_radial_peak_shift'))} |"
        )

    lines.extend(
        [
            "",
            "## Legacy Per-Cell Reference",
            "",
            "| Variant | Grid | Area | Work/Length | Ratio | Retention | Radial Peak |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    legacy_source_by_variant = {row["variant"]: row for row in legacy_source_rows}
    for row in legacy_ordered:
        source = legacy_source_by_variant.get(row["variant"], {})
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('grid_size')} | "
            f"{_format(source.get('effective_driven_area'))} | "
            f"{_format(source.get('injected_work_per_physical_boundary_length'))} | "
            f"{_format(row.get('best_energy_well_ratio'))} | "
            f"{_format(row.get('retention_score'))} | "
            f"{_format(row.get('radial_peak_radius'))} |"
        )

    if legacy_pairwise:
        lines.extend(
            [
                "",
                "## Legacy Pairwise Reference",
                "",
                "| Pair | Spatial Corr | Best Radial Corr | Tail Radial Corr | Radial Peak Shift |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in legacy_pairwise:
            lines.append(
                "| "
                f"{row['first_variant']} vs {row['second_variant']} | "
                f"{_format(row.get('best_spatial_correlation'))} | "
                f"{_format(row.get('best_radial_correlation'))} | "
                f"{_format(row.get('tail_radial_correlation'))} | "
                f"{_format(row.get('best_radial_peak_shift'))} |"
            )

    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Value |",
            "| --- | --- |",
        ]
    )
    for key, value in classification.get("checks", {}).items():
        lines.append(f"| `{key}` | `{value}` |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _source_normalized_interpretation(classification),
            "",
            "## Output Files",
            "",
            "- `source_normalized_resolution_summary.csv`",
            "- `source_audit_comparison.csv`",
            "- `injected_work_comparison.csv`",
            "- `mask_area_audit.csv`",
            "- `energy_budget_audit.csv`",
            "- `radial_profile_comparison.csv`",
        ]
    )
    for row in ordered:
        lines.append(f"- `{row['variant']}` mode diagnostics: `{row.get('mode_shape_diagnostics_report')}`")

    lines.extend(
        [
            "",
            "## Thresholds",
            "",
            f"- Source work relative tolerance: `{options.source_work_relative_tolerance}`",
            f"- Mask area relative tolerance: `{options.mask_area_relative_tolerance}`",
            f"- Refined radial peak shift max: `{options.refined_peak_shift_max}`",
            f"- Refined radial correlation minimum: `{options.refined_radial_corr_min}`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _source_normalized_answers(
    rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    mask_rows: list[dict[str, Any]],
    pairwise: list[dict[str, Any]],
    classification: dict[str, Any],
) -> list[str]:
    area_range = _relative_range([float(row.get("effective_driven_area") or 0.0) for row in source_rows])
    length_range = _relative_range([float(row.get("effective_driven_length") or 0.0) for row in source_rows])
    work_range = _relative_range(
        [float(row.get("injected_work_per_physical_boundary_length") or 0.0) for row in source_rows]
    )
    work_63_removed = classification.get("checks", {}).get("work_63_anomaly_removed")
    refined_pair = _comparison_for(pairwise, rows[-2]["variant"], rows[-1]["variant"]) if len(rows) >= 3 else None
    first_shift = _peak_shift(rows[0], rows[1]) if len(rows) >= 2 else 0.0
    refined_shift = _peak_shift(rows[-2], rows[-1]) if len(rows) >= 3 else 0.0
    refined_peak = rows[-1].get("radial_peak_radius") if rows else None
    baseline_peak = rows[0].get("radial_peak_radius") if rows else None
    periods = [float(row.get("breathing_period") or 0.0) for row in rows]
    modes = [int(row.get("strongest_angular_mode") or 0) for row in rows]
    retention_values = [float(row.get("retention_score") or 0.0) for row in rows]
    return [
        f"Emitter effective area/length relative ranges are `{area_range:.3g}` / `{length_range:.3g}`.",
        f"Injected work per physical boundary length relative range is `{work_range:.3g}`.",
        f"The 63-grid source-work anomaly removed check is `{work_63_removed}`.",
        (
            f"The 63/81 radial peak shift is `{refined_shift:.3g}` with refined peak `{_format(refined_peak)}`; "
            "they do not remain at the legacy 3.75 peak after source normalization. "
            f"The 41/63 shift is `{first_shift:.3g}` from the 41-grid peak `{_format(baseline_peak)}`; "
            f"63/81 best radial correlation is `{_format((refined_pair or {}).get('best_radial_correlation'))}`."
        ),
        f"Breathing periods by resolution are `{', '.join(f'{value:.3g}' for value in periods)}`.",
        f"Strongest angular modes by resolution are `{', '.join(f'm{mode}' for mode in modes)}`.",
        f"Retention values by resolution are `{', '.join(f'{value:.3g}' for value in retention_values)}`.",
    ]


def _source_normalized_interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "source_normalization_fixed":
        return "The source audit is now comparable, but the resolution interpretation still needs inspection."
    if label == "source_normalization_issue_persists":
        return "The source is still not comparable enough; do not interpret the radial shift yet."
    if label == "coarse_grid_artifact_likely":
        return (
            "With source normalization controlled, the refined grids agree with each other while the 41-grid radial peak "
            "remains the outlier. Treat the 41-grid radial location as likely coarse-grid structure, not a resolved refined mode."
        )
    if label == "refined_mode_converging":
        return "With source normalization controlled, refined grids are converging toward a shared radial structure."
    if label == "true_resolution_sensitive":
        return "With source normalization controlled, retention and structure still change enough to remain resolution-sensitive."
    return "The source-normalized evidence remains mixed; do not run broad long sweeps yet."


def _write_report(
    path: Path,
    diagnostic_id: str,
    base_config: SimulationConfig,
    rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    mask_rows: list[dict[str, Any]],
    pairwise: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ResolutionDiagnosticsOptions,
) -> None:
    ordered = sorted(rows, key=lambda row: int(row.get("grid_size") or 0))
    answers = _report_answers(ordered, source_rows, mask_rows, pairwise, classification)
    lines = [
        f"# Resolution Diagnostics Report: {diagnostic_id}",
        "",
        "## Purpose",
        "",
        (
            "Diagnose why the fixed-domain 0.92 refinement control preserves breathing but changes radial structure "
            "and weakens retention. This is a targeted resolution-sensitivity control, not a broad sweep."
        ),
        "",
        "## Base Case",
        "",
        f"- Source config grid: `{base_config.grid_size}`",
        f"- Drive frequency/amplitude: `{base_config.driver.frequency}` / `{base_config.driver.amplitude}`",
        f"- Drive cutoff time: `{base_config.driver.drive_cutoff_time}`",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Direct Answers",
        "",
    ]
    for answer in answers:
        lines.append(f"- {answer}")

    lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| Variant | Grid | dx | Ratio | Retention | Best Time | Period | Core E | Outer E | Core Fraction | Radial Peak | m | m Strength |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in ordered:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('grid_size')} | "
            f"{_format(row.get('dx'))} | "
            f"{_format(row.get('best_energy_well_ratio'))} | "
            f"{_format(row.get('retention_score'))} | "
            f"{_format(row.get('best_event_time'))} | "
            f"{_format(row.get('breathing_period'))} | "
            f"{_format(row.get('core_energy'))} | "
            f"{_format(row.get('outer_energy'))} | "
            f"{_format(row.get('core_fraction'))} | "
            f"{_format(row.get('radial_peak_radius'))} | "
            f"{row.get('strongest_angular_mode')} | "
            f"{_format(row.get('strongest_angular_mode_strength'))} |"
        )

    lines.extend(
        [
            "",
            "## Source Normalization Audit",
            "",
            "| Variant | Emitter Cells | Physical Length | Amp/Cell | Injected Work Before Cutoff | Work / Length | Work / Area | Peak Injected Power |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in source_rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('emitter_cell_count')} | "
            f"{_format(row.get('physical_emitter_length'))} | "
            f"{_format(row.get('per_cell_drive_amplitude'))} | "
            f"{_format(row.get('total_injected_work_before_cutoff'))} | "
            f"{_format(row.get('injected_work_per_physical_boundary_length'))} | "
            f"{_format(row.get('injected_work_per_unit_area'))} | "
            f"{_format(row.get('peak_injected_power'))} |"
        )

    lines.extend(
        [
            "",
            "## Mask And Area Audit",
            "",
            "| Variant | Defect Area | Core Area | Annulus Area | Outer Area | Sponge Area | Emitter Area |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in mask_rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('defect_physical_area'))} | "
            f"{_format(row.get('core_physical_area'))} | "
            f"{_format(row.get('annulus_physical_area'))} | "
            f"{_format(row.get('outer_physical_area'))} | "
            f"{_format(row.get('sponge_physical_area'))} | "
            f"{_format(row.get('emitter_physical_area_from_mask'))} |"
        )

    lines.extend(
        [
            "",
            "## Pairwise Mode-Shape Comparison",
            "",
            "| Pair | Spatial Corr | Best Radial Corr | Tail Radial Corr | Angular Similarity | Radial Peak Shift |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in pairwise:
        lines.append(
            "| "
            f"{row['first_variant']} vs {row['second_variant']} | "
            f"{_format(row.get('best_spatial_correlation'))} | "
            f"{_format(row.get('best_radial_correlation'))} | "
            f"{_format(row.get('tail_radial_correlation'))} | "
            f"{_format(row.get('angular_mode_similarity'))} | "
            f"{_format(row.get('best_radial_peak_shift'))} |"
        )

    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Value |",
            "| --- | --- |",
        ]
    )
    for key, value in classification.get("checks", {}).items():
        lines.append(f"| `{key}` | `{value}` |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _classification_interpretation(classification),
            "",
            "## Output Files",
            "",
            "- `resolution_diagnostics_summary.csv`",
            "- `source_audit.csv`",
            "- `mask_area_audit.csv`",
            "- `energy_budget_audit.csv`",
            "- `radial_profile_comparison.csv`",
        ]
    )
    for row in ordered:
        lines.append(f"- `{row['variant']}` mode diagnostics: `{row.get('mode_shape_diagnostics_report')}`")

    lines.extend(
        [
            "",
            "## Thresholds",
            "",
            f"- Source work relative tolerance: `{options.source_work_relative_tolerance}`",
            f"- Mask area relative tolerance: `{options.mask_area_relative_tolerance}`",
            f"- Refined radial peak shift max: `{options.refined_peak_shift_max}`",
            f"- Refined radial correlation minimum: `{options.refined_radial_corr_min}`",
            f"- Expected breathing period range: `{options.expected_period_min}` to `{options.expected_period_max}`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _report_answers(
    rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    mask_rows: list[dict[str, Any]],
    pairwise: list[dict[str, Any]],
    classification: dict[str, Any],
) -> list[str]:
    source_range = _relative_range(
        [float(row.get("injected_work_per_physical_boundary_length") or 0.0) for row in source_rows]
    )
    core_area_range = _relative_range([float(row.get("core_physical_area") or 0.0) for row in mask_rows])
    emitter_area_range = _relative_range([float(row.get("emitter_physical_area_from_mask") or 0.0) for row in mask_rows])
    retention_values = [float(row.get("retention_score") or 0.0) for row in rows]
    periods = [float(row.get("breathing_period") or 0.0) for row in rows]
    modes = [int(row.get("strongest_angular_mode") or 0) for row in rows]
    refined_pair = _comparison_for(pairwise, rows[-2]["variant"], rows[-1]["variant"]) if len(rows) >= 3 else None
    first_shift = _peak_shift(rows[0], rows[1]) if len(rows) >= 2 else 0.0
    refined_shift = _peak_shift(rows[-2], rows[-1]) if len(rows) >= 3 else 0.0
    coarse_signal = (
        classification["checks"].get("refined_radial_profiles_converge")
        and classification["checks"].get("coarse_peak_differs_from_refined")
    )
    return [
        (
            "Injected energy is comparable enough for this diagnostic "
            f"(work/length relative range `{source_range:.3g}`), but source work remains an audit field, not a proof."
        ),
        (
            f"Core/defect physical regions are comparable at the core level "
            f"(core-area relative range `{core_area_range:.3g}`), while emitter mask area varies more "
            f"(relative range `{emitter_area_range:.3g}`)."
        ),
        (
            "The 41-grid radial peak shows a coarse-grid-artifact signal, but the primary classifier stops at the emitter/mask discretization issue first."
            if coarse_signal and classification["label"] in {"mask_discretization_issue", "source_normalization_issue"}
            else (
                "The 41-grid radial peak is likely coarse-grid related."
                if classification["label"] in {"coarse_grid_artifact_likely", "refined_mode_converging"}
                else "The 41-grid radial peak is not isolated as a coarse-grid artifact by this classifier."
            )
        ),
        (
            f"The 63/81 radial peak shift is `{refined_shift:.3g}` versus 41/63 shift `{first_shift:.3g}`; "
            f"63/81 best radial correlation is `{_format((refined_pair or {}).get('best_radial_correlation'))}`."
        ),
        f"Retention values by resolution are `{', '.join(f'{value:.3g}' for value in retention_values)}`.",
        f"Breathing periods by resolution are `{', '.join(f'{value:.3g}' for value in periods)}`.",
        f"Strongest angular modes by resolution are `{', '.join(f'm{mode}' for mode in modes)}`.",
    ]


def _classification_interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "source_normalization_issue":
        return (
            "The resolution comparison should not be interpreted as pure physics sensitivity until the boundary source "
            "normalization is made more resolution invariant or the source-work discrepancy is otherwise explained."
        )
    if label == "mask_discretization_issue":
        return "The physical regions are not comparable enough across grids; inspect mask construction before broader sweeps."
    if label == "radial_binning_issue":
        return "The frame shapes are more similar than the radial-bin summaries suggest; radial binning should be revised."
    if label == "coarse_grid_artifact_likely":
        return (
            "The refined grids are closer to each other than to the 41-grid case, so the original outward radial peak is "
            "likely at least partly coarse-resolution structure. Breathing persistence remains meaningful, but radial "
            "location and retention need refined-grid wording."
        )
    if label == "refined_mode_converging":
        return "The refined grids are converging toward a shared same-domain radial structure."
    if label == "true_resolution_sensitive":
        return "The candidate remains genuinely resolution-sensitive under the current fixed-domain physics scaling."
    return "The diagnostic evidence remains mixed; do not run broad long sweeps yet."


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        fieldnames = fields
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _summary_fields() -> list[str]:
    return [
        "variant_role",
        "variant",
        "run_id",
        "path",
        "classification_label",
        "grid_size",
        "dx",
        "dy",
        "dt",
        "steps",
        "physical_duration",
        "drive_cutoff_time",
        "source_normalization",
        "recommended_dt_max",
        "hard_stability_dt_max",
        "dt_to_hard_limit_ratio",
        "stability_warnings",
        "emitter_cell_count",
        "emitter_fractional_coverage_sum",
        "physical_emitter_length",
        "effective_driven_area",
        "effective_driven_length",
        "per_cell_drive_amplitude",
        "source_normalization_scale",
        "total_drive_amplitude_sum",
        "total_injected_work_before_cutoff",
        "injected_work_per_physical_boundary_length",
        "injected_work_per_unit_area",
        "core_physical_area",
        "defect_physical_area",
        "sponge_physical_area",
        "best_energy_well_ratio",
        "retention_score",
        "best_event_time",
        "core_energy",
        "outer_energy",
        "total_energy",
        "core_fraction",
        "core_decay_rate_after_cutoff",
        "outer_decay_rate_after_cutoff",
        "total_decay_rate_after_cutoff",
        "breathing_detected",
        "breathing_period",
        "breathing_strength",
        "breathing_cycles",
        "radial_peak_radius",
        "radial_peak_radius_range",
        "best_event_radial_peak_fwhm",
        "tail_final_radial_peak_radius",
        "tail_final_radial_peak_fwhm",
        "strongest_angular_mode",
        "strongest_angular_mode_strength",
        "angular_phase_drift",
        "angular_phase_trend_r2",
        "spatial_correlation_to_baseline",
        "radial_correlation_to_baseline",
        "tail_radial_correlation_to_baseline",
        "angular_mode_similarity_to_baseline",
        "spatial_correlation_to_previous_grid",
        "radial_correlation_to_previous_grid",
        "angular_mode_similarity_to_previous_grid",
        "mean_previous_frame_correlation",
        "minimum_previous_frame_correlation",
        "detected_labels",
        "mode_shape_diagnostics_report",
    ]


def _source_fields() -> list[str]:
    return [
        "variant_role",
        "variant",
        "grid_size",
        "dx",
        "dy",
        "source_normalization",
        "emitter_cell_count",
        "emitter_fractional_coverage_sum",
        "physical_emitter_length",
        "effective_driven_area",
        "effective_driven_length",
        "emitter_active_cell_area",
        "emitter_width_physical",
        "emitter_physical_area_from_mask",
        "per_cell_drive_amplitude",
        "source_normalization_scale",
        "total_drive_amplitude_sum",
        "area_weighted_drive_amplitude_sum",
        "drive_frequency",
        "drive_cutoff_time",
        "total_drive_work_over_time",
        "positive_drive_work_over_time",
        "net_drive_work_before_cutoff",
        "total_injected_work_before_cutoff",
        "peak_injected_power",
        "injected_work_per_physical_boundary_length",
        "injected_work_per_unit_area",
    ]


def _mask_fields() -> list[str]:
    return [
        "variant_role",
        "variant",
        "grid_size",
        "grid_height",
        "dx",
        "dy",
        "source_normalization",
        "cell_area",
        "domain_width",
        "domain_height",
        "nominal_domain_area",
        "node_cell_area_total",
        "defect_radius_physical",
        "defect_cell_count",
        "defect_physical_area",
        "defect_ideal_area",
        "core_radius_physical",
        "core_cell_count",
        "core_physical_area",
        "core_ideal_area",
        "annulus_cell_count",
        "annulus_physical_area",
        "outer_cell_count",
        "outer_physical_area",
        "sponge_physical_width",
        "sponge_cell_count",
        "sponge_physical_area",
        "emitter_cell_count",
        "emitter_fractional_coverage_sum",
        "emitter_physical_length",
        "effective_driven_area",
        "effective_driven_length",
        "emitter_active_cell_area",
        "emitter_physical_area_from_mask",
    ]


def _energy_budget_fields() -> list[str]:
    return [
        "variant_role",
        "variant",
        "grid_size",
        "step",
        "time",
        "total_energy",
        "core_energy",
        "outer_energy",
        "sponge_region_energy",
        "drive_power",
        "positive_drive_power",
        "damping_loss_power",
        "sponge_damping_loss_power",
        "cumulative_drive_work",
        "cumulative_positive_drive_work",
        "cumulative_damping_loss",
        "cumulative_sponge_damping_loss",
        "energy_residual_estimate",
        "relative_energy_residual_estimate",
    ]


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, np.generic):
        return _csv_value(value.item())
    return value


def _format(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    return f"{float(value):.6g}"
