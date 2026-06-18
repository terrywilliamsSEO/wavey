"""Tiny 3D controls focused on the clean six-face cubic boundary source."""

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
from .prototype_3d_audit import Prototype3DFailureAuditOptions, run_3d_failure_audit
from .prototype_3d_source_geometry import ALL_FACES, _random_face_offsets
from .prototype_3d_source_sponge import (
    _effective_source_area,
    _float_or,
    _format,
    _merge_rows,
    _ratio,
    _write_csv,
)


@dataclass(frozen=True)
class CubicFocusControlOptions:
    """Options for the tiny six-face cubic focus control."""

    output_root: str = "runs"
    grid_size: int = 31
    sample_every: int = 2
    radial_bins: int = 24
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 2.0
    phase_offset: float = 0.5 * float(np.pi)
    imbalance_scale: float = 0.75
    second_imbalance_scale: float = 0.85
    random_phase_seed: int = 31092
    min_near_retention: float = 0.50
    max_outer_ratio: float = 4.0
    max_near_radius_range: float = 4.5
    min_repeat_near_peak_fraction: float = 0.95


def run_3d_cubic_focus_control(
    base_config: SimulationConfig,
    *,
    options: CubicFocusControlOptions | None = None,
) -> dict[str, Any]:
    """Run focused variants around the six-face cubic 3D boundary source."""

    options = options or CubicFocusControlOptions()
    control_id = datetime.now().strftime("cubic_focus_3d_%Y%m%d_%H%M%S")
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
                "label": "cubic_focus_control",
                "reason": "Focused six-face cubic boundary source control.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "cubic_focus_control_report.md"),
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
    classification = classify_cubic_focus_control(control_rows, options)
    for row in control_rows:
        row["cubic_focus_classification"] = classification["label"]

    summary_csv = root / "cubic_focus_control_summary.csv"
    report_path = root / "cubic_focus_control_report.md"
    _write_csv(summary_csv, control_rows, _summary_fields())
    _write_report(report_path, control_id, control_rows, classification, options, audit)
    save_json(
        root / "cubic_focus_control_summary.json",
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


def classify_cubic_focus_control(
    rows: list[dict[str, Any]],
    options: CubicFocusControlOptions | None = None,
) -> dict[str, Any]:
    """Classify which cubic-source perturbations remain clean."""

    options = options or CubicFocusControlOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No cubic-focus rows were available.", "checks": {}}
    by_variant = {row["variant"]: row for row in rows}
    reference = by_variant.get("six_face_cubic_reference", rows[0])
    repeat = by_variant.get("six_face_cubic_repeat")
    sign_flip = by_variant.get("cubic_phase_sign_flip")
    offset = by_variant.get("cubic_phase_offset")
    random_a = f"random_phase_seed_{options.random_phase_seed}_a"
    random_b = f"random_phase_seed_{options.random_phase_seed}_b"
    dirty_names = (
        "cubic_missing_z_max_face",
        "cubic_face_imbalance",
        "six_face_uniform_same_coverage",
        random_a,
        random_b,
    )
    symmetry_break_names = ("cubic_missing_z_max_face", "cubic_face_imbalance")
    non_cubic_names = ("six_face_uniform_same_coverage", random_a, random_b)
    direct_names = ("direct_core_control", "direct_shell_control")
    checks = {
        "reference": _row_checks(reference, options),
        "repeat": _row_checks(repeat, options) if repeat else {},
        "sign_flip": _row_checks(sign_flip, options) if sign_flip else {},
        "phase_offset": _row_checks(offset, options) if offset else {},
        "dirty_controls": {name: _row_checks(by_variant.get(name), options) for name in dirty_names if by_variant.get(name)},
        "direct_controls": {name: _row_checks(by_variant.get(name), options) for name in direct_names if by_variant.get(name)},
        "repeat_near_peak_fraction": _ratio(
            repeat.get("near_shell_peak_fraction_of_work") if repeat else None,
            reference.get("near_shell_peak_fraction_of_work"),
        ),
    }
    reference_clean = checks["reference"].get("clean", False)
    repeat_clean = checks["repeat"].get("clean", False) and checks["repeat_near_peak_fraction"] >= options.min_repeat_near_peak_fraction
    sign_flip_clean = checks["sign_flip"].get("clean", False)
    offset_clean = checks["phase_offset"].get("clean", False)
    dirty_controls_dirty = all(check.get("global_outer", False) for check in checks["dirty_controls"].values())
    symmetry_break_clean = [
        name
        for name in symmetry_break_names
        if checks["dirty_controls"].get(name, {}).get("clean", False)
    ]
    non_cubic_outer_flagged = all(
        checks["dirty_controls"].get(name, {}).get("global_outer", False)
        for name in non_cubic_names
        if name in checks["dirty_controls"]
    )
    direct_transient = all(check.get("transient", False) for check in checks["direct_controls"].values())

    if not reference_clean or not repeat_clean:
        return {
            "label": "six_face_cubic_not_reproducible",
            "reason": "The six-face cubic reference did not repeat as a clean retained near-shell case.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if sign_flip_clean and offset_clean and dirty_controls_dirty and direct_transient:
        return {
            "label": "cubic_phase_family_clean",
            "reason": "Six-face cubic, sign-flipped cubic, and phase-offset cubic all stayed clean while uniform/random/partial-face controls remained outer-flagged.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if sign_flip_clean and symmetry_break_clean and non_cubic_outer_flagged and direct_transient:
        return {
            "label": "cubic_phase_structure_not_full_symmetry",
            "reason": (
                "The six-face cubic source repeated cleanly and the sign-flipped cubic phase stayed clean, while "
                "uniform/random phase controls were outer-flagged. Mild cubic symmetry breaks also stayed clean, so "
                f"perfect six-face balance is not isolated as the required ingredient ({', '.join(symmetry_break_clean)})."
            ),
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if dirty_controls_dirty and direct_transient:
        return {
            "label": "exact_cubic_clean_but_phase_sensitive",
            "reason": "Six-face cubic repeated cleanly, but sign or offset perturbations did not all stay clean.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not dirty_controls_dirty:
        return {
            "label": "cubic_not_isolated_from_dirty_controls",
            "reason": "At least one uniform, random, partial-face, or imbalance control was not outer-flagged.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not direct_transient:
        return {
            "label": "direct_local_forcing_competitive",
            "reason": "At least one direct local control retained the near-shell signal enough to confound boundary-only interpretation.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "inconclusive",
        "reason": "The cubic focus control produced mixed cleanliness and retention metrics.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: CubicFocusControlOptions,
) -> list[Prototype3DConfig]:
    random_offsets = _random_face_offsets(options.random_phase_seed)
    variants = [
        _base_boundary_config("six_face_cubic_reference", base, prototype_options, options, ALL_FACES, "cubic"),
        _base_boundary_config("six_face_cubic_repeat", base, prototype_options, options, ALL_FACES, "cubic"),
        _base_boundary_config(
            "cubic_phase_sign_flip",
            base,
            prototype_options,
            options,
            ALL_FACES,
            "cubic",
            cubic_sign=-1.0,
        ),
        _base_boundary_config(
            "cubic_phase_offset",
            base,
            prototype_options,
            options,
            ALL_FACES,
            "cubic",
            phase_offset=options.phase_offset,
        ),
        _base_boundary_config("cubic_missing_z_max_face", base, prototype_options, options, ALL_FACES[:-1], "cubic"),
        _base_boundary_config(
            "cubic_face_imbalance",
            base,
            prototype_options,
            options,
            ALL_FACES,
            "cubic",
            amplitude_scales={"x_min": options.imbalance_scale, "z_max": options.second_imbalance_scale},
        ),
        _base_boundary_config("six_face_uniform_same_coverage", base, prototype_options, options, ALL_FACES, "uniform"),
        _base_boundary_config(
            f"random_phase_seed_{options.random_phase_seed}_a",
            base,
            prototype_options,
            options,
            ALL_FACES,
            "face_offsets",
            face_offsets=random_offsets,
        ),
        _base_boundary_config(
            f"random_phase_seed_{options.random_phase_seed}_b",
            base,
            prototype_options,
            options,
            ALL_FACES,
            "face_offsets",
            face_offsets=random_offsets,
        ),
        _base_direct_config("direct_core_control", base, prototype_options, options, "core"),
        _base_direct_config("direct_shell_control", base, prototype_options, options, "shell"),
    ]
    return variants


def _base_boundary_config(
    name: str,
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: CubicFocusControlOptions,
    faces: tuple[str, ...],
    phase_mode: str,
    *,
    face_offsets: dict[str, float] | None = None,
    phase_offset: float = 0.0,
    cubic_sign: float = 1.0,
    amplitude_scales: dict[str, float] | None = None,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, prototype_options, "boundary", phase_mode)
    _apply_cleaned_geometry(config, options)
    config.boundary_faces = faces
    config.boundary_face_phase_offsets = face_offsets
    config.boundary_phase_offset = phase_offset
    config.boundary_cubic_phase_sign = cubic_sign
    config.boundary_face_amplitude_scales = amplitude_scales
    return config


def _base_direct_config(
    name: str,
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: CubicFocusControlOptions,
    drive_location: str,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, prototype_options, drive_location, "uniform")
    _apply_cleaned_geometry(config, options)
    return config


def _apply_cleaned_geometry(config: Prototype3DConfig, options: CubicFocusControlOptions) -> None:
    source_distance = config.sponge_width
    config.sponge_strength *= options.sponge_strength_multiplier
    config.boundary_source_inner_distance = source_distance
    config.boundary_source_width = config.dx


def _add_control_fields(summary: dict[str, Any], config: Prototype3DConfig, reference_config: Prototype3DConfig) -> None:
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    summary["sponge_width_multiplier"] = config.sponge_width / max(reference_config.sponge_width, EPSILON)
    summary["sponge_strength_multiplier"] = config.sponge_strength / max(reference_config.sponge_strength, EPSILON)
    summary["cubic_focus_role"] = _variant_role(config.name)


def _variant_role(variant: str) -> str:
    if variant.startswith("direct_"):
        return "direct_control"
    if variant.startswith("random_phase"):
        return "random_phase_control"
    if variant in {"six_face_uniform_same_coverage", "cubic_missing_z_max_face", "cubic_face_imbalance"}:
        return "dirty_control"
    if variant == "six_face_cubic_reference":
        return "reference"
    if variant == "six_face_cubic_repeat":
        return "repeat"
    return "cubic_perturbation"


def _row_checks(row: dict[str, Any] | None, options: CubicFocusControlOptions) -> dict[str, Any]:
    if row is None:
        return {}
    retention = _float_or(row.get("near_shell_tail_retention"), 0.0)
    outer_ratio = _float_or(row.get("outer_to_near_tail_energy_ratio"), 999.0)
    radius_range = _float_or(row.get("late_tail_near_shell_peak_radius_range"), 999.0)
    arrival = row.get("first_meaningful_near_shell_arrival_time")
    global_outer = bool(row.get("global_peak_in_outer_window"))
    clean = (
        retention >= options.min_near_retention
        and outer_ratio <= options.max_outer_ratio
        and radius_range <= options.max_near_radius_range
        and arrival is not None
        and not global_outer
    )
    transient = arrival is not None and retention < 0.05
    return {
        "variant": row.get("variant"),
        "clean": clean,
        "global_outer": global_outer,
        "transient": transient,
        "near_shell_retained": retention >= options.min_near_retention,
        "near_retention": retention,
        "outer_ratio": outer_ratio,
        "near_radius_range": radius_range,
        "arrival_sensible": arrival is not None and 0.0 <= float(arrival) <= float(row.get("physical_duration") or 0.0),
    }


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    pool = [row for row in rows if row.get("drive_location") == "boundary"] or rows
    best = max(pool, key=_score)
    return str(best.get("variant", "n/a"))


def _score(row: dict[str, Any]) -> float:
    near_peak = float(row.get("near_shell_peak_fraction_of_work") or 0.0)
    retention = float(row.get("near_shell_tail_retention") or 0.0)
    outer_ratio = max(float(row.get("outer_to_near_tail_energy_ratio") or 999.0), 0.25)
    range_penalty = max(float(row.get("late_tail_near_shell_peak_radius_range") or 1.0), 1.0)
    outer_factor = 0.5 if bool(row.get("global_peak_in_outer_window")) else 1.0
    return near_peak * retention * outer_factor / (outer_ratio * range_penalty)


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: CubicFocusControlOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Cubic Focus Control: {control_id}",
        "",
        "## Purpose",
        "",
        "Tiny 31^3 control for the question: what exact part of the six-face cubic boundary source makes it clean?",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Role | Faces | Phase | Sign | Offset | Work/Area | Near Peak/Work | Near Retention | Near Radius Range | Outer/Near Tail | Global Outer? | Arrival |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('cubic_focus_role')} | "
            f"{row.get('boundary_face_count')} | "
            f"{row.get('drive_phase_mode')} | "
            f"{_format(row.get('boundary_cubic_phase_sign'))} | "
            f"{_format(row.get('boundary_phase_offset'))} | "
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
            "- Boundary variants are matched by injected work per physical source area.",
            "- Direct core/shell controls are matched by total injected work to the cubic reference.",
            "",
            "## Files",
            "",
            "- `cubic_focus_control_summary.csv`",
            "- `cubic_focus_control_summary.json`",
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
    label = classification["label"]
    if label == "cubic_phase_family_clean":
        return "The clean near-shell tail is robust to cubic sign and global phase offset, while non-cubic or symmetry-broken controls remain dirty."
    if label == "cubic_phase_structure_not_full_symmetry":
        return (
            "The clean near-shell tail appears tied more to the cubic phase structure than to exact six-face balance: "
            "uniform/random phases were outer-flagged, while a missing face and mild face imbalance still retained a clean tail. "
            "The global phase-offset variant was outer-flagged, so phase timing remains a sensitivity."
        )
    if label == "exact_cubic_clean_but_phase_sensitive":
        return "The exact six-face cubic pattern repeats cleanly, but sign or phase-offset perturbations do not all preserve the clean tail."
    if label == "six_face_cubic_not_reproducible":
        return "The six-face cubic reference did not reproduce cleanly, so the current clean case is not stable enough for broader interpretation."
    if label == "cubic_not_isolated_from_dirty_controls":
        return "A dirty control was not outer-flagged, so the exact cubic source is not isolated by this pass."
    if label == "direct_local_forcing_competitive":
        return "A direct local control retained enough signal to confound a boundary-only interpretation."
    return "The cubic focus control produced mixed metrics. Keep this as a narrow diagnostic result."


def _next_step(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label in {"cubic_phase_family_clean", "exact_cubic_clean_but_phase_sensitive", "cubic_phase_structure_not_full_symmetry"}:
        return "Keep 31^3 and run a basic dt or sponge confirmation for the clean cubic variant before increasing grid size."
    return "Stay at 31^3 and resolve the cubic-source confound before any larger 3D grid."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "cubic_focus_classification",
        "cubic_focus_role",
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
        "boundary_phase_offset",
        "boundary_cubic_phase_sign",
        "boundary_face_amplitude_scales",
        "sponge_strength",
        "sponge_strength_multiplier",
        "sponge_width",
        "sponge_width_multiplier",
        "boundary_source_inner_distance",
        "boundary_source_width",
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
