"""Tiny 41^3 defect-lift sweep for the cubic sign-flip 3D source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import (
    EPSILON,
    Prototype3DConfig,
    Prototype3DOptions,
    _base_3d_config,
    _calibrate_amplitude,
    _coordinate_payload,
    _radial_bins,
    _run_variant,
    _summary_fields as _prototype_summary_fields,
    _write_csv as _write_prototype_csv,
)
from .prototype_3d_audit import Prototype3DFailureAuditOptions, run_3d_failure_audit
from .prototype_3d_cubic_confirmation import _stability_summary
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_radial_window_audit import (
    _corr,
    _profile_fields,
    _profile_for,
    _scan_windows,
    _shift,
    _window_profile_slice,
    _window_width,
)
from .prototype_3d_source_geometry import ALL_FACES
from .prototype_3d_source_sponge import _effective_source_area, _format, _merge_rows, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


@dataclass(frozen=True)
class DefectLiftSweep3DOptions:
    """Options for a tiny hand-picked defect-lift sweep."""

    output_root: str = "runs"
    grid_size: int = 41
    reference_source_grid_size: int = 31
    sample_every: int = 2
    radial_bins: int = 24
    window_radii: tuple[float, ...] = (2.5, 3.5, 5.0, 6.5, 8.0, 10.0, 12.0)
    window_width: float | None = None
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    target_work_per_source_area: float | None = None
    min_retention: float = 0.45
    max_outer_ratio: float = 2.0
    max_radius_range: float = 4.5
    lift_threshold: float = 1.5
    max_profile_correlation_for_lift: float = 0.95


def run_3d_defect_lift_sweep(
    base_config: SimulationConfig,
    *,
    options: DefectLiftSweep3DOptions | None = None,
) -> dict[str, Any]:
    """Run a tiny defect-lift sweep while holding the validated boundary drive fixed."""

    options = options or DefectLiftSweep3DOptions()
    control_id = datetime.now().strftime("defect_lift_sweep_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    reference_config = variants[0]
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    threshold_options = _threshold_like_options(options)
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
    configs_by_variant: dict[str, Prototype3DConfig] = {}

    for config in variants:
        config.drive_amplitude = reference_drive_amplitude
        target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
        _calibrate_amplitude(config, target_work)
        summary = _run_variant(config, root, _prototype_options(config, options))
        _add_control_fields(summary, config, reference_config, options, target_work_per_area)
        summary["classification_label"] = None
        rows.append(summary)
        configs_by_variant[config.name] = config

    prototype_summary_csv = root / "prototype_3d_summary.csv"
    _write_prototype_csv(prototype_summary_csv, rows, _prototype_summary_fields())
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": control_id,
            "classification": {
                "label": "defect_lift_sweep_3d",
                "reason": "Tiny hand-picked defect-lift sweep around the calibrated cubic sign-flip source.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "defect_lift_sweep_3d_report.md"),
        },
    )

    audit = run_3d_failure_audit(
        root,
        base_config,
        options=Prototype3DFailureAuditOptions(
            output_dir=root / "failure_mode_audit",
            radial_bins=options.radial_bins,
            near_shell_width_dx=options.near_shell_width_dx,
        ),
    )
    control_rows = _merge_rows(rows, audit["variants"])
    window_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    window_data: dict[tuple[str, float], dict[str, Any]] = {}
    for row in control_rows:
        config = configs_by_variant[row["variant"]]
        scanned = _scan_windows(row, config, options)
        window_rows.extend(scanned["rows"])
        profile_rows.extend(scanned["profiles"])
        window_data.update({(item["variant"], float(item["window_radius"])): item for item in scanned["rows"]})

    comparison_rows = _comparison_rows(control_rows, configs_by_variant, window_data, options)
    variant_summary_rows = _variant_summary_rows(comparison_rows)
    classification = classify_defect_lift_sweep(comparison_rows, options)
    for row in comparison_rows:
        row["defect_lift_sweep_classification"] = classification["label"]
    for row in variant_summary_rows:
        row["defect_lift_sweep_classification"] = classification["label"]

    summary_csv = root / "defect_lift_sweep_summary.csv"
    comparison_csv = root / "defect_lift_window_comparison.csv"
    profile_csv = root / "defect_lift_profile_comparison.csv"
    variant_window_csv = root / "defect_lift_variant_window_metrics.csv"
    report_path = root / "defect_lift_sweep_3d_report.md"
    _write_csv(summary_csv, variant_summary_rows, _variant_summary_fields())
    _write_csv(comparison_csv, comparison_rows, _comparison_fields())
    _write_csv(profile_csv, profile_rows, _profile_fields())
    _write_csv(variant_window_csv, window_rows, _variant_window_fields())
    _write_report(report_path, control_id, variant_summary_rows, comparison_rows, classification, options, audit)
    save_json(
        root / "defect_lift_sweep_3d_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": control_rows,
            "variant_summaries": variant_summary_rows,
            "window_comparisons": comparison_rows,
            "summary_csv": str(summary_csv),
            "comparison_csv": str(comparison_csv),
            "profile_csv": str(profile_csv),
            "variant_window_csv": str(variant_window_csv),
            "report_path": str(report_path),
            "audit_report_path": audit["report_path"],
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": control_rows,
        "variant_summaries": variant_summary_rows,
        "window_comparisons": comparison_rows,
        "summary_csv": str(summary_csv),
        "comparison_csv": str(comparison_csv),
        "profile_csv": str(profile_csv),
        "variant_window_csv": str(variant_window_csv),
        "report_path": str(report_path),
        "audit_report_path": audit["report_path"],
        "path": str(root),
    }


def classify_defect_lift_sweep(
    comparison_rows: list[dict[str, Any]],
    options: DefectLiftSweep3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether any hand-picked defect variant creates strict lift over neutral."""

    options = options or DefectLiftSweep3DOptions()
    successful = [
        row
        for row in comparison_rows
        if bool(row.get("strict_success"))
    ]
    checks = {
        "successful_windows": [
            {"variant": row["variant"], "window_radius": row["window_radius"]}
            for row in successful
        ],
        "lift_threshold": options.lift_threshold,
        "max_profile_correlation_for_lift": options.max_profile_correlation_for_lift,
    }
    if successful:
        best = max(successful, key=_success_score)
        return {
            "label": "defect_lift_found",
            "reason": "At least one defect variant beat the neutral baseline with strict retention lift, peak/work lift, radial-profile difference, and no global outer flag.",
            "best_variant": best["variant"],
            "best_window_radius": best["window_radius"],
            "checks": checks,
        }
    return {
        "label": "no_defect_lift_found",
        "reason": "No hand-picked defect variant beat the neutral baseline under the strict lift criteria.",
        "best_variant": _best_variant(comparison_rows),
        "best_window_radius": _best_window(comparison_rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: DefectLiftSweep3DOptions) -> list[Prototype3DConfig]:
    source_width = _base_dx(base, options.reference_source_grid_size)
    base_radius = _base_defect_radius(base)
    dx = _base_dx(base, options.grid_size)
    return [
        _boundary_config("neutral_lattice_baseline", base, options, source_width, stiffness=1.0, damping=1.0, coupling=1.0),
        _boundary_config("current_defect_reference", base, options, source_width),
        _boundary_config("stiff_inclusion_k2_0", base, options, source_width, stiffness=2.0),
        _boundary_config("very_soft_cavity_k0_15", base, options, source_width, stiffness=0.15),
        _boundary_config("low_coupling_cavity_c0_25", base, options, source_width, coupling=0.25),
        _boundary_config("high_coupling_inclusion_c1_5", base, options, source_width, coupling=1.5),
        _boundary_config("high_damping_defect_d2_5", base, options, source_width, damping=2.5),
        _boundary_config("low_damping_defect_d0_05", base, options, source_width, damping=0.05),
        _boundary_config("small_radius_r0_5", base, options, source_width, radius=0.5 * base_radius),
        _boundary_config("large_radius_r1_5", base, options, source_width, radius=1.5 * base_radius),
        _boundary_config(
            "thin_shell_wall",
            base,
            options,
            source_width,
            radius=base_radius,
            inner_radius=max(0.0, base_radius - dx),
            stiffness=0.2,
            coupling=0.35,
        ),
        _boundary_config(
            "thick_shell_wall",
            base,
            options,
            source_width,
            radius=base_radius,
            inner_radius=max(0.0, base_radius - 2.0 * dx),
            stiffness=0.2,
            coupling=0.35,
        ),
        _boundary_config(
            "nonlinear_defect_only",
            base,
            options,
            source_width,
            stiffness=1.0,
            damping=1.0,
            coupling=1.0,
            global_nonlinear=0.0,
            defect_nonlinear=max(0.25, 4.0 * base.nonlinear_strength),
        ),
        _boundary_config(
            "nonlinear_shell_wall",
            base,
            options,
            source_width,
            radius=base_radius,
            inner_radius=max(0.0, base_radius - dx),
            stiffness=1.0,
            damping=1.0,
            coupling=1.0,
            global_nonlinear=0.0,
            defect_nonlinear=max(0.25, 4.0 * base.nonlinear_strength),
        ),
    ]


def _boundary_config(
    name: str,
    base: SimulationConfig,
    options: DefectLiftSweep3DOptions,
    source_width: float,
    *,
    radius: float | None = None,
    inner_radius: float | None = None,
    stiffness: float | None = None,
    damping: float | None = None,
    coupling: float | None = None,
    global_nonlinear: float | None = None,
    defect_nonlinear: float | None = None,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, Prototype3DOptions(grid_size=options.grid_size), "boundary", "cubic")
    config.sponge_strength *= options.sponge_strength_multiplier
    config.boundary_source_inner_distance = config.sponge_width
    config.boundary_source_width = source_width
    config.boundary_faces = ALL_FACES
    config.boundary_cubic_phase_sign = -1.0
    if radius is not None:
        config.defect_radius = radius
        config.shell_inner_radius = radius + config.dx
        config.shell_outer_radius = radius + 3.0 * config.dx
    config.defect_inner_radius = inner_radius
    if stiffness is not None:
        config.defect_stiffness_multiplier = stiffness
    if damping is not None:
        config.defect_damping_multiplier = damping
    if coupling is not None:
        config.defect_coupling_multiplier = coupling
    if global_nonlinear is not None:
        config.nonlinear_strength = global_nonlinear
    config.defect_nonlinear_strength = defect_nonlinear
    return config


def _prototype_options(config: Prototype3DConfig, options: DefectLiftSweep3DOptions) -> Prototype3DOptions:
    return Prototype3DOptions(
        output_root=options.output_root,
        grid_size=config.grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        include_dt_control=False,
        include_sponge_control=False,
    )


def _threshold_like_options(options: DefectLiftSweep3DOptions) -> Any:
    from .prototype_3d_threshold_control import ThresholdControl3DOptions

    return ThresholdControl3DOptions(
        output_root=options.output_root,
        grid_size=options.grid_size,
        reference_source_grid_size=options.reference_source_grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        near_shell_width_dx=options.near_shell_width_dx,
        sponge_strength_multiplier=options.sponge_strength_multiplier,
    )


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    reference_config: Prototype3DConfig,
    options: DefectLiftSweep3DOptions,
    target_work_per_area: float,
) -> None:
    summary["defect_lift_role"] = "neutral_baseline" if config.name == "neutral_lattice_baseline" else "defect_variant"
    summary["defect_radius_multiplier"] = config.defect_radius / max(reference_config.defect_radius, EPSILON)
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    original_sponge_strength = reference_config.sponge_strength / max(options.sponge_strength_multiplier, EPSILON)
    summary["sponge_strength_multiplier_vs_original"] = config.sponge_strength / max(original_sponge_strength, EPSILON)
    summary["sponge_width_multiplier"] = config.sponge_width / max(reference_config.sponge_width, EPSILON)
    summary["source_width_physical_reference"] = reference_config.boundary_source_width
    summary["target_reference_work_per_source_area"] = target_work_per_area
    summary["calibration_source_grid_size"] = options.reference_source_grid_size
    summary.update(_stability_summary(config))


def _comparison_rows(
    control_rows: list[dict[str, Any]],
    configs_by_variant: dict[str, Prototype3DConfig],
    window_data: dict[tuple[str, float], dict[str, Any]],
    options: DefectLiftSweep3DOptions,
) -> list[dict[str, Any]]:
    neutral_name = "neutral_lattice_baseline"
    neutral_config = configs_by_variant[neutral_name]
    reference_radius = configs_by_variant.get("current_defect_reference", neutral_config).defect_radius
    neutral_best = np.load(Path(str(_row_by_variant(control_rows, neutral_name)["path"])) / "best_shell_energy_density.npy")
    rows: list[dict[str, Any]] = []
    for variant, config in configs_by_variant.items():
        if variant == neutral_name:
            continue
        variant_best = np.load(Path(str(_row_by_variant(control_rows, variant)["path"])) / "best_shell_energy_density.npy")
        coords = _coordinate_payload(config)
        radius_grid = coords["radius"]
        window_width = _window_width(config, options)
        for radius in options.window_radii:
            defect = window_data[(variant, float(radius))]
            neutral = window_data[(neutral_name, float(radius))]
            variant_profile = _profile_for(variant, radius, window_data)
            neutral_profile = _profile_for(neutral_name, radius, window_data)
            window_mask_3d = (radius_grid > radius) & (radius_grid <= radius + window_width)
            row = {
                "variant": variant,
                "window_radius": radius,
                "window_outer_radius": radius + window_width,
                "defect_retention": defect["shell_tail_retention"],
                "neutral_retention": neutral["shell_tail_retention"],
                "defect_lift_retention": _safe_ratio(defect["shell_tail_retention"], neutral["shell_tail_retention"]),
                "defect_peak_work": defect["shell_peak_fraction_of_work"],
                "neutral_peak_work": neutral["shell_peak_fraction_of_work"],
                "defect_lift_peak_work": _safe_ratio(defect["shell_peak_fraction_of_work"], neutral["shell_peak_fraction_of_work"]),
                "defect_outer_near": defect["outer_to_shell_tail_energy_ratio"],
                "neutral_outer_near": neutral["outer_to_shell_tail_energy_ratio"],
                "defect_radius_median": defect["late_tail_shell_peak_radius_median"],
                "neutral_radius_median": neutral["late_tail_shell_peak_radius_median"],
                "radius_median_shift": _shift(defect["late_tail_shell_peak_radius_median"], neutral["late_tail_shell_peak_radius_median"]),
                "defect_radius_range": defect["late_tail_shell_peak_radius_range"],
                "neutral_radius_range": neutral["late_tail_shell_peak_radius_range"],
                "defect_arrival_time": defect["first_meaningful_shell_arrival_time"],
                "neutral_arrival_time": neutral["first_meaningful_shell_arrival_time"],
                "arrival_time_shift": _shift(defect["first_meaningful_shell_arrival_time"], neutral["first_meaningful_shell_arrival_time"]),
                "defect_window_clean": defect["window_clean"],
                "neutral_window_clean": neutral["window_clean"],
                "defect_global_outer": defect["variant_global_peak_in_outer_window"],
                "neutral_global_outer": neutral["variant_global_peak_in_outer_window"],
                "radial_profile_correlation": _corr(variant_profile, neutral_profile),
                "window_radial_profile_correlation": _corr(
                    _window_profile_slice(variant_profile, config, radius, window_width, options),
                    _window_profile_slice(neutral_profile, neutral_config, radius, window_width, options),
                ),
                "best_frame_similarity": _corr(variant_best.ravel(), neutral_best.ravel()),
                "window_best_frame_similarity": _corr(variant_best[window_mask_3d], neutral_best[window_mask_3d]),
            }
            row["profile_differs_from_neutral"] = (
                float(row["radial_profile_correlation"]) <= options.max_profile_correlation_for_lift
                or float(row["window_radial_profile_correlation"]) <= options.max_profile_correlation_for_lift
            )
            row["strict_success"] = (
                bool(row["defect_window_clean"])
                and not bool(row["defect_global_outer"])
                and float(row["defect_lift_retention"]) > options.lift_threshold
                and float(row["defect_lift_peak_work"]) > options.lift_threshold
                and bool(row["profile_differs_from_neutral"])
            )
            row.update(_variant_config_fields(config, reference_radius))
            rows.append(row)
    return rows


def _variant_summary_rows(comparison_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in comparison_rows:
        by_variant.setdefault(str(row["variant"]), []).append(row)
    summaries = []
    for variant, rows in by_variant.items():
        best = max(rows, key=_success_score)
        summaries.append(
            {
                "variant": variant,
                "best_window_radius": best["window_radius"],
                "strict_success": any(bool(row.get("strict_success")) for row in rows),
                "best_defect_lift_retention": best["defect_lift_retention"],
                "best_defect_lift_peak_work": best["defect_lift_peak_work"],
                "best_defect_retention": best["defect_retention"],
                "best_neutral_retention": best["neutral_retention"],
                "best_defect_peak_work": best["defect_peak_work"],
                "best_neutral_peak_work": best["neutral_peak_work"],
                "best_radial_profile_correlation": best["radial_profile_correlation"],
                "best_window_profile_correlation": best["window_radial_profile_correlation"],
                "best_frame_similarity": best["window_best_frame_similarity"],
                "best_defect_outer_near": best["defect_outer_near"],
                "best_defect_global_outer": best["defect_global_outer"],
                "best_radius_median_shift": best["radius_median_shift"],
                "best_arrival_time_shift": best["arrival_time_shift"],
                **_variant_config_fields_from_row(best),
            }
        )
    return summaries


def _variant_config_fields(config: Prototype3DConfig, reference_radius: float) -> dict[str, Any]:
    return {
        "defect_radius": config.defect_radius,
        "defect_radius_multiplier": config.defect_radius / max(reference_radius, EPSILON),
        "defect_inner_radius": config.defect_inner_radius,
        "nonlinear_strength": config.nonlinear_strength,
        "defect_nonlinear_strength": config.defect_nonlinear_strength,
        "defect_stiffness_multiplier": config.defect_stiffness_multiplier,
        "defect_damping_multiplier": config.defect_damping_multiplier,
        "defect_coupling_multiplier": config.defect_coupling_multiplier,
    }


def _variant_config_fields_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "defect_radius",
            "defect_radius_multiplier",
            "defect_inner_radius",
            "nonlinear_strength",
            "defect_nonlinear_strength",
            "defect_stiffness_multiplier",
            "defect_damping_multiplier",
            "defect_coupling_multiplier",
        )
    }


def _write_report(
    path: Path,
    control_id: str,
    variant_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: DefectLiftSweep3DOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Defect-Lift Sweep: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny hand-picked defect sweep for the question: can any defect configuration create real lift "
            "over the neutral-lattice cubic-boundary shell tail?"
        ),
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        f"- Best window radius: `{_format(classification.get('best_window_radius'))}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Success | Best Radius | Lift Ret | Lift Peak | Def Ret | Neu Ret | Profile Corr | Window Corr | Outer/Near | Global Outer |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in variant_rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('strict_success')} | "
            f"{_format(row.get('best_window_radius'))} | "
            f"{_format(row.get('best_defect_lift_retention'))} | "
            f"{_format(row.get('best_defect_lift_peak_work'))} | "
            f"{_format(row.get('best_defect_retention'))} | "
            f"{_format(row.get('best_neutral_retention'))} | "
            f"{_format(row.get('best_radial_profile_correlation'))} | "
            f"{_format(row.get('best_window_profile_correlation'))} | "
            f"{_format(row.get('best_defect_outer_near'))} | "
            f"{row.get('best_defect_global_outer')} |"
        )
    lines.extend(
        [
            "",
            "## Strict Success Rule",
            "",
            f"- defect_lift_retention > `{options.lift_threshold}`",
            f"- defect_lift_peak_work > `{options.lift_threshold}`",
            f"- radial or window profile correlation <= `{options.max_profile_correlation_for_lift}`",
            "- global outer flag must be false",
            "- shell window must pass retention/outer/radius/arrival cleanliness gates",
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Controls Held Fixed",
            "",
            f"- Grid size: `{options.grid_size}^3`",
            "- Source: calibrated sign-flipped cubic boundary source at the inner sponge edge.",
            "- Every variant is matched by injected work per physical source area.",
            "- Drive frequency, cutoff time, physical domain, source geometry, sponge width, and sponge strength are fixed.",
            "",
            "## Files",
            "",
            "- `defect_lift_sweep_summary.csv`",
            "- `defect_lift_window_comparison.csv`",
            "- `defect_lift_profile_comparison.csv`",
            "- `defect_lift_variant_window_metrics.csv`",
            "- `prototype_3d_summary.csv`",
            "- `prototype_3d_summary.json`",
            f"- failure-mode audit report: `{audit['report_path']}`",
            "",
            "## Next Step",
            "",
            _next_step(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    if classification["label"] == "defect_lift_found":
        return "A defect variant finally produced strict lift over neutral. Verify it with one repeat/half-dt control before reviving defect-localization language."
    return "No tested defect variant beat neutral under the strict rule. The project should pivot away from defect-well language and treat this as structured boundary transport unless a future targeted variant changes that."


def _next_step(classification: dict[str, Any]) -> str:
    if classification["label"] == "defect_lift_found":
        return "Run a tiny repeat/half-dt confirmation for the lifted defect variant; do not broad sweep."
    return "Pivot the 3D branch toward structured boundary transport modes; next use a tiny neutral-lattice boundary-phase negative control, not defect-well expansion."


def _success_score(row: dict[str, Any]) -> float:
    lift = float(row.get("defect_lift_retention") or 0.0) * float(row.get("defect_lift_peak_work") or 0.0)
    profile_diff = 1.0 - min(float(row.get("radial_profile_correlation") or 1.0), float(row.get("window_radial_profile_correlation") or 1.0))
    clean = 1.0 if bool(row.get("defect_window_clean")) and not bool(row.get("defect_global_outer")) else 0.25
    return lift * (0.25 + profile_diff) * clean


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(max(rows, key=_success_score).get("variant", "n/a"))


def _best_window(rows: list[dict[str, Any]]) -> float | str:
    if not rows:
        return "n/a"
    return float(max(rows, key=_success_score).get("window_radius", 0.0))


def _base_defect_radius(base: SimulationConfig) -> float:
    return float(base.defect.radius_physical if base.defect.radius_physical is not None else base.defect.radius)


def _safe_ratio(first: Any, second: Any) -> float:
    return float(first or 0.0) / (float(second or 0.0) + EPSILON)


def _row_by_variant(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    for row in rows:
        if row["variant"] == variant:
            return row
    raise KeyError(variant)


def _variant_summary_fields() -> list[str]:
    return [
        "variant",
        "defect_lift_sweep_classification",
        "strict_success",
        "best_window_radius",
        "best_defect_lift_retention",
        "best_defect_lift_peak_work",
        "best_defect_retention",
        "best_neutral_retention",
        "best_defect_peak_work",
        "best_neutral_peak_work",
        "best_radial_profile_correlation",
        "best_window_profile_correlation",
        "best_frame_similarity",
        "best_defect_outer_near",
        "best_defect_global_outer",
        "best_radius_median_shift",
        "best_arrival_time_shift",
        "defect_radius",
        "defect_radius_multiplier",
        "defect_inner_radius",
        "nonlinear_strength",
        "defect_nonlinear_strength",
        "defect_stiffness_multiplier",
        "defect_damping_multiplier",
        "defect_coupling_multiplier",
    ]


def _comparison_fields() -> list[str]:
    return [
        "variant",
        "window_radius",
        "window_outer_radius",
        "defect_lift_sweep_classification",
        "strict_success",
        "defect_retention",
        "neutral_retention",
        "defect_lift_retention",
        "defect_peak_work",
        "neutral_peak_work",
        "defect_lift_peak_work",
        "defect_outer_near",
        "neutral_outer_near",
        "defect_radius_median",
        "neutral_radius_median",
        "radius_median_shift",
        "defect_radius_range",
        "neutral_radius_range",
        "defect_arrival_time",
        "neutral_arrival_time",
        "arrival_time_shift",
        "defect_window_clean",
        "neutral_window_clean",
        "defect_global_outer",
        "neutral_global_outer",
        "profile_differs_from_neutral",
        "radial_profile_correlation",
        "window_radial_profile_correlation",
        "best_frame_similarity",
        "window_best_frame_similarity",
        "defect_radius",
        "defect_radius_multiplier",
        "defect_inner_radius",
        "nonlinear_strength",
        "defect_nonlinear_strength",
        "defect_stiffness_multiplier",
        "defect_damping_multiplier",
        "defect_coupling_multiplier",
    ]


def _variant_window_fields() -> list[str]:
    return [
        "variant",
        "radial_window_role",
        "window_radius",
        "window_outer_radius",
        "window_width",
        "window_bin_count",
        "positive_work_before_cutoff",
        "work_per_source_area",
        "shell_peak_fraction_of_work",
        "shell_peak_time",
        "shell_peak_radius_at_peak_time",
        "shell_tail_fraction_of_total",
        "shell_tail_retention",
        "outer_tail_mean_energy",
        "outer_to_shell_tail_energy_ratio",
        "first_meaningful_shell_arrival_time",
        "late_tail_shell_peak_radius_median",
        "late_tail_shell_peak_radius_range",
        "variant_global_peak_in_outer_window",
        "window_clean",
        "total_tail_mean_energy",
        "metrics_total_tail_mean_energy",
    ]
