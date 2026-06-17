"""Tiny 3D source-geometry controls for the cleaned inner-edge setup."""

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
    _run_variant,
    _summary_fields as _prototype_summary_fields,
    _write_csv as _write_prototype_csv,
)
from .prototype_3d_audit import (
    Prototype3DFailureAuditOptions,
    run_3d_failure_audit,
)
from .prototype_3d_source_sponge import (
    _effective_source_area,
    _float_or,
    _format,
    _merge_rows,
    _ratio,
    _write_csv,
)


ALL_FACES = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
SIDE_FACES = ("x_min", "x_max", "y_min", "y_max")
OPPOSITE_FACES = ("x_min", "x_max")


@dataclass(frozen=True)
class SourceGeometryControlOptions:
    """Options for the tiny 3D boundary source-geometry check."""

    output_root: str = "runs"
    grid_size: int = 31
    sample_every: int = 2
    radial_bins: int = 24
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 2.0
    min_near_retention: float = 0.50
    min_preserved_near_peak_fraction: float = 0.75
    min_improved_near_peak_gain: float = 1.10
    max_outer_ratio: float = 4.0
    max_outer_ratio_fraction_of_baseline: float = 1.10
    max_near_radius_range: float = 4.5
    random_phase_seed: int = 31092


def run_3d_source_geometry_control(
    base_config: SimulationConfig,
    *,
    options: SourceGeometryControlOptions | None = None,
) -> dict[str, Any]:
    """Run source-geometry variants from the stronger-sponge inner-edge setup."""

    options = options or SourceGeometryControlOptions()
    control_id = datetime.now().strftime("source_geometry_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    prototype_options = Prototype3DOptions(
        output_root=options.output_root,
        grid_size=options.grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        include_dt_control=False,
        include_sponge_control=False,
    )
    variants = _variant_plan(base_config, prototype_options, options)
    reference_config = variants[0]
    rows: list[dict[str, Any]] = []
    reference_work_per_area = 0.0
    reference_total_work = 0.0

    for idx, config in enumerate(variants):
        if idx == 0:
            summary = _run_variant(config, root, prototype_options)
            reference_area = max(float(summary.get("effective_source_area") or 0.0), EPSILON)
            reference_total_work = float(summary["positive_work_before_cutoff"])
            reference_work_per_area = reference_total_work / reference_area
        else:
            if config.drive_location == "boundary":
                target_work = reference_work_per_area * max(_effective_source_area(config), EPSILON)
            else:
                target_work = reference_total_work
            _calibrate_amplitude(config, target_work)
            summary = _run_variant(config, root, prototype_options)
        _add_control_fields(summary, config, reference_config)
        summary["classification_label"] = None
        rows.append(summary)

    prototype_summary_csv = root / "prototype_3d_summary.csv"
    _write_prototype_csv(prototype_summary_csv, rows, _prototype_summary_fields())
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": control_id,
            "classification": {
                "label": "source_geometry_control",
                "reason": "Source-geometry control with cubic boundary reference work density.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "source_geometry_control_report.md"),
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
    classification = classify_source_geometry_control(control_rows, options)
    for row in control_rows:
        row["source_geometry_classification"] = classification["label"]

    summary_csv = root / "source_geometry_control_summary.csv"
    report_path = root / "source_geometry_control_report.md"
    _write_csv(summary_csv, control_rows, _summary_fields())
    _write_report(report_path, control_id, control_rows, classification, options, audit)
    save_json(
        root / "source_geometry_control_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "variants": control_rows,
            "summary_csv": str(summary_csv),
            "report_path": str(report_path),
            "audit_report_path": audit["report_path"],
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "variants": control_rows,
        "summary_csv": str(summary_csv),
        "report_path": str(report_path),
        "audit_report_path": audit["report_path"],
        "path": str(root),
    }


def classify_source_geometry_control(
    rows: list[dict[str, Any]],
    options: SourceGeometryControlOptions | None = None,
) -> dict[str, Any]:
    """Classify whether a boundary source geometry improves near-shell transport."""

    options = options or SourceGeometryControlOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No source-geometry rows were available.", "checks": {}}
    baseline = next((row for row in rows if row["variant"] == "six_face_uniform"), rows[0])
    coherent_names = {
        "one_face",
        "two_opposite_faces",
        "four_side_faces",
        "six_face_rotating_cubic_phase",
        "phased_opposite_faces",
    }
    coherent_rows = [row for row in rows if row.get("variant") in coherent_names]
    random_row = next((row for row in rows if row.get("variant") == "random_phase_faces"), None)
    direct_rows = [row for row in rows if str(row.get("variant", "")).startswith("direct_")]
    if not coherent_rows:
        return {"label": "inconclusive", "reason": "No coherent boundary source-geometry variants were available.", "checks": {}}

    checked = [(row, _comparison_checks(baseline, row, options)) for row in coherent_rows]
    good = [(row, checks) for row, checks in checked if checks["good_near_shell_transport"]]
    improved = [(row, checks) for row, checks in good if checks["near_peak_improved"]]
    best_pool = improved or good or checked
    best, checks = max(best_pool, key=lambda item: _source_geometry_score(item[0]))
    random_checks = _comparison_checks(baseline, random_row, options) if random_row is not None else {}
    direct_checks = [(row, _comparison_checks(baseline, row, options)) for row in direct_rows]
    best_score = _source_geometry_score(best)
    random_competitive = bool(random_checks) and random_checks.get("good_near_shell_transport") and _source_geometry_score(random_row) >= 0.90 * best_score
    direct_competitive = [
        row["variant"]
        for row, direct_check in direct_checks
        if direct_check["good_near_shell_transport"] and _source_geometry_score(row) >= 0.90 * best_score
    ]
    common_checks = {
        "baseline_variant": baseline.get("variant"),
        "best_boundary_variant": best.get("variant"),
        "best_boundary_checks": checks,
        "random_checks": random_checks,
        "direct_checks": {row["variant"]: direct_check for row, direct_check in direct_checks},
    }

    if direct_competitive:
        return {
            "label": "direct_local_forcing_competitive",
            "reason": f"{', '.join(direct_competitive)} matched the best boundary near-shell transport closely enough to confound the boundary-geometry claim.",
            "best_variant": best["variant"],
            "checks": common_checks,
        }
    if random_competitive:
        return {
            "label": "coherent_boundary_phase_not_isolated",
            "reason": "The random phase boundary control was competitive with the best coherent boundary geometry.",
            "best_variant": best["variant"],
            "checks": common_checks,
        }
    if improved:
        return {
            "label": "boundary_phase_geometry_strengthens_near_shell",
            "reason": f"{best['variant']} strengthened retained near-defect shell transport versus six-face uniform drive.",
            "best_variant": best["variant"],
            "checks": common_checks,
        }
    if good:
        return {
            "label": "boundary_source_geometry_preserves_near_shell",
            "reason": f"{best['variant']} preserved near-defect shell transport, but did not clearly improve on six-face uniform drive.",
            "best_variant": best["variant"],
            "checks": common_checks,
        }
    return {
        "label": "source_geometry_sensitive",
        "reason": "No tested non-random boundary source geometry preserved the near-shell signal under the stronger-sponge setup.",
        "best_variant": best["variant"],
        "checks": common_checks,
    }


def _variant_plan(
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: SourceGeometryControlOptions,
) -> list[Prototype3DConfig]:
    random_offsets = _random_face_offsets(options.random_phase_seed)
    variants = [
        _base_boundary_config("six_face_rotating_cubic_phase", base, prototype_options, options, ALL_FACES, "cubic"),
        _base_boundary_config("six_face_uniform", base, prototype_options, options, ALL_FACES, "uniform"),
        _base_boundary_config("one_face", base, prototype_options, options, ("x_min",), "uniform"),
        _base_boundary_config("two_opposite_faces", base, prototype_options, options, OPPOSITE_FACES, "uniform"),
        _base_boundary_config("four_side_faces", base, prototype_options, options, SIDE_FACES, "uniform"),
        _base_boundary_config(
            "phased_opposite_faces",
            base,
            prototype_options,
            options,
            OPPOSITE_FACES,
            "face_offsets",
            {"x_min": 0.0, "x_max": float(np.pi)},
        ),
        _base_boundary_config("random_phase_faces", base, prototype_options, options, ALL_FACES, "face_offsets", random_offsets),
        _base_direct_config("direct_core_control", base, prototype_options, options, "core"),
        _base_direct_config("direct_shell_control", base, prototype_options, options, "shell"),
    ]
    return variants


def _base_boundary_config(
    name: str,
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: SourceGeometryControlOptions,
    faces: tuple[str, ...],
    phase_mode: str,
    phase_offsets: dict[str, float] | None = None,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, prototype_options, "boundary", phase_mode)
    _apply_cleaned_geometry(config, options)
    config.boundary_faces = faces
    config.boundary_face_phase_offsets = phase_offsets
    return config


def _base_direct_config(
    name: str,
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: SourceGeometryControlOptions,
    drive_location: str,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, prototype_options, drive_location, "uniform")
    _apply_cleaned_geometry(config, options)
    return config


def _apply_cleaned_geometry(config: Prototype3DConfig, options: SourceGeometryControlOptions) -> None:
    source_distance = config.sponge_width
    config.sponge_strength *= options.sponge_strength_multiplier
    config.boundary_source_inner_distance = source_distance
    config.boundary_source_width = config.dx


def _random_face_offsets(seed: int) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    return {face: float(rng.uniform(0.0, 2.0 * np.pi)) for face in ALL_FACES}


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    baseline_config: Prototype3DConfig,
) -> None:
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    summary["sponge_width_multiplier"] = config.sponge_width / max(baseline_config.sponge_width, EPSILON)
    summary["sponge_strength_multiplier"] = config.sponge_strength / max(baseline_config.sponge_strength, EPSILON)
    summary["source_geometry_role"] = _source_geometry_role(config.name)


def _source_geometry_role(variant: str) -> str:
    if variant.startswith("direct_"):
        return "direct_control"
    if variant == "random_phase_faces":
        return "random_phase_control"
    if variant == "six_face_uniform":
        return "baseline_boundary"
    return "coherent_boundary"


def _comparison_checks(
    baseline: dict[str, Any],
    candidate: dict[str, Any] | None,
    options: SourceGeometryControlOptions,
) -> dict[str, Any]:
    if candidate is None:
        return {}
    near_peak_ratio = _ratio(candidate.get("near_shell_peak_fraction_of_work"), baseline.get("near_shell_peak_fraction_of_work"))
    outer_ratio = _float_or(candidate.get("outer_to_near_tail_energy_ratio"), float("inf"))
    baseline_outer = _float_or(baseline.get("outer_to_near_tail_energy_ratio"), options.max_outer_ratio)
    if bool(baseline.get("global_peak_in_outer_window")):
        outer_limit = options.max_outer_ratio
    else:
        outer_limit = min(options.max_outer_ratio, baseline_outer * options.max_outer_ratio_fraction_of_baseline)
    arrival = candidate.get("first_meaningful_near_shell_arrival_time")
    return {
        "candidate_variant": candidate.get("variant"),
        "near_peak_ratio_to_baseline": near_peak_ratio,
        "near_peak_preserved": near_peak_ratio >= options.min_preserved_near_peak_fraction,
        "near_peak_improved": near_peak_ratio >= options.min_improved_near_peak_gain,
        "near_shell_retained": _float_or(candidate.get("near_shell_tail_retention"), 0.0) >= options.min_near_retention,
        "outer_ratio_low": outer_ratio <= outer_limit,
        "outer_ratio_limit": outer_limit,
        "near_peak_radius_stable": _float_or(candidate.get("late_tail_near_shell_peak_radius_range"), 999.0) <= options.max_near_radius_range,
        "arrival_sensible": arrival is not None and 0.0 <= float(arrival) <= float(candidate.get("physical_duration") or 0.0),
        "no_outer_boundary_dominance": not bool(candidate.get("global_peak_in_outer_window")),
        "good_near_shell_transport": (
            near_peak_ratio >= options.min_preserved_near_peak_fraction
            and _float_or(candidate.get("near_shell_tail_retention"), 0.0) >= options.min_near_retention
            and outer_ratio <= outer_limit
            and _float_or(candidate.get("late_tail_near_shell_peak_radius_range"), 999.0) <= options.max_near_radius_range
            and arrival is not None
            and not bool(candidate.get("global_peak_in_outer_window"))
        ),
    }


def _source_geometry_score(row: dict[str, Any] | None) -> float:
    if row is None:
        return 0.0
    near_peak = float(row.get("near_shell_peak_fraction_of_work") or 0.0)
    retention = float(row.get("near_shell_tail_retention") or 0.0)
    outer_ratio = max(float(row.get("outer_to_near_tail_energy_ratio") or 999.0), 0.25)
    radius_range = max(float(row.get("late_tail_near_shell_peak_radius_range") or 1.0), 1.0)
    outer_penalty = 0.5 if bool(row.get("global_peak_in_outer_window")) else 1.0
    return (near_peak * max(retention, 0.0) * outer_penalty) / (outer_ratio * radius_range)


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: SourceGeometryControlOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Source-Geometry Control: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny 31^3 control for the question: which boundary source geometry transports energy into the "
            "near-defect shell window without creating outer-boundary residue?"
        ),
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best boundary variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Role | Faces | Phase | Work | Work/Area | Near Peak/Work | Near Retention | Near Radius Range | Outer/Near Tail | Global Outer? | Arrival |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('source_geometry_role')} | "
            f"{_faces_label(row.get('boundary_faces'))} | "
            f"{row.get('drive_phase_mode')} | "
            f"{_format(row.get('positive_work_before_cutoff'))} | "
            f"{_format(row.get('work_per_source_area'))} | "
            f"{_format(row.get('near_shell_peak_fraction_of_work'))} | "
            f"{_format(row.get('near_shell_tail_retention'))} | "
            f"{_format(row.get('late_tail_near_shell_peak_radius_range'))} | "
            f"{_format(row.get('outer_to_near_tail_energy_ratio'))} | "
            f"{row.get('global_peak_in_outer_window')} | "
            f"{_format(row.get('first_meaningful_near_shell_arrival_time'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Controls Held Fixed",
            "",
            f"- Grid size: `{options.grid_size}^3`",
            "- Source location: original inner sponge edge.",
            "- Sponge: stronger sponge at original width.",
            "- Boundary variants are matched by injected work per physical source area from the stronger-sponge cubic six-face reference.",
            "- Direct core/shell controls are matched by total injected work to that same cubic reference.",
            "",
            "## Files",
            "",
            "- `source_geometry_control_summary.csv`",
            "- `source_geometry_control_summary.json`",
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


def _faces_label(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    if isinstance(value, str):
        return value
    return ",".join(str(part) for part in value)


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "boundary_phase_geometry_strengthens_near_shell":
        return "A coherent boundary geometry improved the retained near-shell tail while direct local controls did not stay competitive."
    if label == "boundary_source_geometry_preserves_near_shell":
        return (
            "The six-face cubic boundary geometry remains the cleanest retained near-shell case in this set: it avoids "
            "global outer-window dominance, but no tested geometry produced a stronger clean tail."
        )
    if label == "direct_local_forcing_competitive":
        return "A direct local control was competitive, so the near-shell tail is not isolated to boundary transport in this control."
    if label == "coherent_boundary_phase_not_isolated":
        return "The random phase boundary control was competitive, so coherent phase geometry is not isolated by this pass."
    if label == "source_geometry_sensitive":
        return "The retained near-shell signal is sensitive to source geometry under stronger sponge; inspect the least-bad variant before expanding."
    return "The source-geometry control changed mixed metrics. Keep this as a narrow 3D diagnostic result."


def _next_step(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "boundary_phase_geometry_strengthens_near_shell":
        return "Keep 31^3 and rerun the best geometry with one direct-core/direct-shell confirmation and a dt check before increasing grid size."
    if label == "boundary_source_geometry_preserves_near_shell":
        return "Keep 31^3 and narrow around the preserved six-face cubic boundary geometry; do not increase grid size yet."
    return "Stay at 31^3 and resolve the source-geometry confound before any larger 3D grid."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "source_geometry_classification",
        "source_geometry_role",
        "grid_size",
        "dx",
        "dt",
        "physical_duration",
        "drive_location",
        "drive_phase_mode",
        "drive_amplitude",
        "drive_frequency",
        "drive_cutoff_time",
        "boundary_faces",
        "boundary_face_count",
        "boundary_face_phase_offsets",
        "sponge_strength",
        "sponge_strength_multiplier",
        "sponge_width",
        "sponge_width_multiplier",
        "boundary_source_inner_distance",
        "boundary_source_width",
        "exclude_source_from_sponge_damping",
        "effective_source_area",
        "positive_work_before_cutoff",
        "work_per_source_area",
        "source_sponge_overlap_fraction",
        "source_high_sponge_overlap_fraction",
        "source_mean_sponge_fraction_of_max",
        "near_shell_peak_fraction_of_work",
        "near_shell_peak_time",
        "near_shell_peak_radius_at_peak_time",
        "first_meaningful_near_shell_arrival_time",
        "near_shell_tail_retention",
        "near_shell_tail_fraction_of_total",
        "late_tail_near_shell_peak_radius_median",
        "late_tail_near_shell_peak_radius_range",
        "outer_to_near_tail_energy_ratio",
        "global_shell_peak_radius",
        "global_peak_in_outer_window",
        "post_cutoff_shell_retention",
        "shell_breathing_detected",
        "shell_breathing_period",
        "path",
    ]
