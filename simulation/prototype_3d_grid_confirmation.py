"""Tiny 3D fixed-domain grid confirmation for the clean cubic sign-flip candidate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

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
from .prototype_3d_cubic_confirmation import _stability_summary
from .prototype_3d_source_geometry import ALL_FACES
from .prototype_3d_source_sponge import (
    _effective_source_area,
    _float_or,
    _format,
    _merge_rows,
    _ratio,
    _write_csv,
)


@dataclass(frozen=True)
class GridConfirmation3DOptions:
    """Options for the tiny 31^3 to 41^3 3D grid confirmation."""

    output_root: str = "runs"
    baseline_grid_size: int = 31
    refined_grid_size: int = 41
    sample_every: int = 2
    radial_bins: int = 24
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    include_original_cubic_41: bool = True
    negative_control: str = "direct_shell"
    min_retention: float = 0.45
    max_outer_ratio: float = 2.0
    max_near_radius_range: float = 4.5
    max_radius_shift: float = 4.5
    max_arrival_shift: float = 4.0
    min_near_peak_ratio: float = 0.20
    max_near_peak_ratio: float = 8.0


def run_3d_grid_confirmation_control(
    base_config: SimulationConfig,
    *,
    options: GridConfirmation3DOptions | None = None,
) -> dict[str, Any]:
    """Run a single-candidate 3D fixed-domain grid lift from 31^3 to 41^3."""

    options = options or GridConfirmation3DOptions()
    control_id = datetime.now().strftime("grid_confirmation_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    rows: list[dict[str, Any]] = []
    reference_work_per_area = 0.0
    reference_total_work = 0.0
    reference_config = variants[0]

    for idx, config in enumerate(variants):
        if idx == 0:
            summary = _run_variant(config, root, _prototype_options(config, options))
            reference_area = max(float(summary.get("effective_source_area") or 0.0), EPSILON)
            reference_total_work = float(summary["positive_work_before_cutoff"])
            reference_work_per_area = reference_total_work / reference_area
        else:
            if config.drive_location == "boundary":
                target_work = reference_work_per_area * max(_effective_source_area(config), EPSILON)
            else:
                target_work = reference_total_work
            _calibrate_amplitude(config, target_work)
            summary = _run_variant(config, root, _prototype_options(config, options))
        _add_control_fields(summary, config, reference_config, options)
        summary["classification_label"] = None
        rows.append(summary)

    prototype_summary_csv = root / "prototype_3d_summary.csv"
    _write_prototype_csv(prototype_summary_csv, rows, _prototype_summary_fields())
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": control_id,
            "classification": {
                "label": "grid_confirmation_3d_control",
                "reason": "Tiny fixed-domain 3D grid lift for the clean cubic sign-flip source.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "grid_confirmation_3d_report.md"),
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
    classification = classify_grid_confirmation_control(control_rows, options)
    for row in control_rows:
        row["grid_confirmation_classification"] = classification["label"]

    summary_csv = root / "grid_confirmation_3d_summary.csv"
    report_path = root / "grid_confirmation_3d_report.md"
    _write_csv(summary_csv, control_rows, _summary_fields())
    _write_report(report_path, control_id, control_rows, classification, options, audit)
    save_json(
        root / "grid_confirmation_3d_summary.json",
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


def classify_grid_confirmation_control(
    rows: list[dict[str, Any]],
    options: GridConfirmation3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the clean sign-flip source survives one 3D grid lift."""

    options = options or GridConfirmation3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No 3D grid-confirmation rows were available.", "checks": {}}
    by_variant = {row["variant"]: row for row in rows}
    reference = by_variant.get("sign_flip_stronger_sponge_31")
    refined = by_variant.get("sign_flip_stronger_sponge_41")
    original = by_variant.get("original_cubic_stronger_sponge_41")
    negative = by_variant.get("direct_shell_41_negative_control") or by_variant.get("uniform_phase_41_negative_control")
    checks = {
        "reference": _row_checks(reference, reference, options),
        "refined_sign_flip": _row_checks(refined, reference, options),
        "original_cubic_41": _row_checks(original, reference, options) if original else {},
        "negative_control": _row_checks(negative, reference, options) if negative else {},
        "hard_dt_warnings": [row["variant"] for row in rows if _has_hard_dt_warning(row)],
    }
    if checks["hard_dt_warnings"]:
        return {
            "label": "unstable_due_to_dt",
            "reason": f"At least one 3D grid-confirmation variant exceeded the hard dt estimate: {', '.join(checks['hard_dt_warnings'])}.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not checks["refined_sign_flip"].get("clean", False):
        return {
            "label": "resolution_sensitive",
            "reason": "The 41^3 sign-flipped cubic source did not preserve the clean near-shell tail.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if negative and not checks["negative_control"].get("transient_or_dirty", False):
        return {
            "label": "negative_control_competitive",
            "reason": "The 41^3 negative control was not transient or dirty enough to isolate the sign-flipped boundary source.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if original and checks["original_cubic_41"].get("clean", False):
        return {
            "label": "cubic_phase_resolution_lift_confirmed",
            "reason": "The 41^3 sign-flipped cubic source and optional original cubic source both preserved clean near-shell tails while the negative control did not.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "sign_flip_resolution_lift_confirmed",
        "reason": "The 41^3 sign-flipped cubic source preserved the clean near-shell tail; optional original cubic did not also pass.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: GridConfirmation3DOptions) -> list[Prototype3DConfig]:
    reference_width = _base_dx(base, options.baseline_grid_size)
    variants = [
        _boundary_config(
            "sign_flip_stronger_sponge_31",
            base,
            options,
            options.baseline_grid_size,
            cubic_sign=-1.0,
            phase_mode="cubic",
            source_width=reference_width,
        ),
        _boundary_config(
            "sign_flip_stronger_sponge_41",
            base,
            options,
            options.refined_grid_size,
            cubic_sign=-1.0,
            phase_mode="cubic",
            source_width=reference_width,
        ),
    ]
    if options.include_original_cubic_41:
        variants.append(
            _boundary_config(
                "original_cubic_stronger_sponge_41",
                base,
                options,
                options.refined_grid_size,
                cubic_sign=1.0,
                phase_mode="cubic",
                source_width=reference_width,
            )
        )
    if options.negative_control == "uniform_phase":
        variants.append(
            _boundary_config(
                "uniform_phase_41_negative_control",
                base,
                options,
                options.refined_grid_size,
                cubic_sign=1.0,
                phase_mode="uniform",
                source_width=reference_width,
            )
        )
    else:
        variants.append(
            _direct_config(
                "direct_shell_41_negative_control",
                base,
                options,
                options.refined_grid_size,
                "shell",
                source_width=reference_width,
            )
        )
    return variants


def _prototype_options(config: Prototype3DConfig, options: GridConfirmation3DOptions) -> Prototype3DOptions:
    return Prototype3DOptions(
        output_root=options.output_root,
        grid_size=config.grid_size,
        sample_every=options.sample_every,
        radial_bins=options.radial_bins,
        include_dt_control=False,
        include_sponge_control=False,
    )


def _boundary_config(
    name: str,
    base: SimulationConfig,
    options: GridConfirmation3DOptions,
    grid_size: int,
    *,
    cubic_sign: float,
    phase_mode: str,
    source_width: float,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, Prototype3DOptions(grid_size=grid_size), "boundary", phase_mode)
    _apply_common_geometry(config, options, source_width)
    config.boundary_faces = ALL_FACES
    config.boundary_cubic_phase_sign = cubic_sign
    return config


def _direct_config(
    name: str,
    base: SimulationConfig,
    options: GridConfirmation3DOptions,
    grid_size: int,
    drive_location: str,
    *,
    source_width: float,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, Prototype3DOptions(grid_size=grid_size), drive_location, "uniform")
    _apply_common_geometry(config, options, source_width)
    return config


def _apply_common_geometry(config: Prototype3DConfig, options: GridConfirmation3DOptions, source_width: float) -> None:
    config.sponge_strength *= options.sponge_strength_multiplier
    config.boundary_source_inner_distance = config.sponge_width
    config.boundary_source_width = source_width


def _base_dx(base: SimulationConfig, grid_size: int) -> float:
    domain = float(base.domain_width if base.domain_width is not None else base.grid_size - 1)
    return domain / float(max(grid_size - 1, 1))


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    reference_config: Prototype3DConfig,
    options: GridConfirmation3DOptions,
) -> None:
    summary["grid_confirmation_role"] = _role(config.name)
    summary["grid_confirmation_family"] = _family(config.name)
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    summary["sponge_strength_multiplier_vs_original"] = options.sponge_strength_multiplier
    summary["sponge_width_multiplier"] = config.sponge_width / max(reference_config.sponge_width, EPSILON)
    summary["source_width_physical_reference"] = reference_config.boundary_source_width
    summary.update(_stability_summary(config))


def _family(variant: str) -> str:
    if variant.startswith("sign_flip"):
        return "cubic_phase_sign_flip"
    if variant.startswith("original_cubic"):
        return "six_face_cubic"
    if variant.startswith("uniform"):
        return "uniform_phase_negative"
    if variant.startswith("direct"):
        return "direct_control"
    return "unknown"


def _role(variant: str) -> str:
    if variant.endswith("_31"):
        return "baseline_reference"
    if variant.endswith("_41"):
        return "refined_candidate"
    if variant.endswith("negative_control"):
        return "negative_control"
    return "optional_comparator"


def _row_checks(
    row: dict[str, Any] | None,
    reference: dict[str, Any] | None,
    options: GridConfirmation3DOptions,
) -> dict[str, Any]:
    if row is None:
        return {}
    retention = _float_or(row.get("near_shell_tail_retention"), 0.0)
    outer_ratio = _float_or(row.get("outer_to_near_tail_energy_ratio"), 999.0)
    radius_range = _float_or(row.get("late_tail_near_shell_peak_radius_range"), 999.0)
    arrival = row.get("first_meaningful_near_shell_arrival_time")
    near_peak_ratio = _ratio(row.get("near_shell_peak_fraction_of_work"), reference.get("near_shell_peak_fraction_of_work") if reference else None)
    radius_shift = _shift(row.get("late_tail_near_shell_peak_radius_median"), reference.get("late_tail_near_shell_peak_radius_median") if reference else None)
    arrival_shift = _shift(arrival, reference.get("first_meaningful_near_shell_arrival_time") if reference else None)
    global_outer = bool(row.get("global_peak_in_outer_window"))
    transient = arrival is not None and retention < 0.05
    dirty = global_outer or outer_ratio > options.max_outer_ratio
    clean = (
        retention >= options.min_retention
        and outer_ratio <= options.max_outer_ratio
        and not global_outer
        and options.min_near_peak_ratio <= near_peak_ratio <= options.max_near_peak_ratio
        and radius_range <= options.max_near_radius_range
        and (radius_shift is None or radius_shift <= options.max_radius_shift)
        and arrival is not None
        and (arrival_shift is None or arrival_shift <= options.max_arrival_shift)
        and not _has_hard_dt_warning(row)
    )
    return {
        "variant": row.get("variant"),
        "clean": clean,
        "transient": transient,
        "dirty": dirty,
        "transient_or_dirty": transient or dirty,
        "retention": retention,
        "outer_ratio": outer_ratio,
        "global_outer": global_outer,
        "near_peak_ratio_to_reference": near_peak_ratio,
        "radius_range": radius_range,
        "radius_shift": radius_shift,
        "arrival_shift": arrival_shift,
        "hard_dt_warning": _has_hard_dt_warning(row),
    }


def _shift(first: Any, second: Any) -> float | None:
    if first in (None, "") or second in (None, ""):
        return None
    return abs(float(first) - float(second))


def _has_hard_dt_warning(row: dict[str, Any]) -> bool:
    warnings = str(row.get("stability_warnings") or "")
    return "hard" in warnings.lower() and warnings.lower() != "none"


def _best_variant(rows: list[dict[str, Any]]) -> str:
    boundary_rows = [row for row in rows if row.get("drive_location") == "boundary"]
    pool = boundary_rows or rows
    if not pool:
        return "n/a"
    return str(max(pool, key=_score).get("variant", "n/a"))


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
    options: GridConfirmation3DOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Grid Confirmation Control: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny fixed-domain 3D grid-size confirmation for the clean sign-flipped cubic boundary source. "
            "This is a single-candidate resolution lift, not a 3D sweep."
        ),
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Grid | dx | Family | Role | Work/Area | Near Peak/Work | Near Retention | Near Radius Median | Near Radius Range | Outer/Near Tail | Global Outer? | Arrival | dt Warning |",
        "| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('grid_size')} | "
            f"{_format(row.get('dx'))} | "
            f"{row.get('grid_confirmation_family')} | "
            f"{row.get('grid_confirmation_role')} | "
            f"{_format(row.get('work_per_source_area'))} | "
            f"{_format(row.get('near_shell_peak_fraction_of_work'))} | "
            f"{_format(row.get('near_shell_tail_retention'))} | "
            f"{_format(row.get('late_tail_near_shell_peak_radius_median'))} | "
            f"{_format(row.get('late_tail_near_shell_peak_radius_range'))} | "
            f"{_format(row.get('outer_to_near_tail_energy_ratio'))} | "
            f"{row.get('global_peak_in_outer_window')} | "
            f"{_format(row.get('first_meaningful_near_shell_arrival_time'))} | "
            f"{row.get('stability_warnings')} |"
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
            "- Physical domain size, defect radius, sponge width, source inner-edge distance, drive frequency, and cutoff time are fixed.",
            f"- Sponge strength is `{options.sponge_strength_multiplier}` times the original 3D sponge strength for every variant.",
            "- Boundary variants are matched by injected work per physical source area.",
            "- The direct-shell negative control is matched by total injected work to the 31^3 sign-flip reference.",
            "- The source layer uses the same physical width as the 31^3 reference when lifted to 41^3.",
            "",
            "## Files",
            "",
            "- `grid_confirmation_3d_summary.csv`",
            "- `grid_confirmation_3d_summary.json`",
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
    if label == "cubic_phase_resolution_lift_confirmed":
        return "The clean sign-flipped cubic near-shell tail survived the 41^3 lift, and the optional original cubic comparator also remained clean."
    if label == "sign_flip_resolution_lift_confirmed":
        return "The clean sign-flipped cubic near-shell tail survived the 41^3 lift, but the optional original cubic comparator did not also pass."
    if label == "resolution_sensitive":
        return "The clean sign-flipped cubic source did not preserve the near-shell tail at 41^3. Do not increase 3D grid size further."
    if label == "negative_control_competitive":
        return "The 41^3 negative control was too competitive, so the boundary-source interpretation is not isolated by this grid check."
    if label == "unstable_due_to_dt":
        return "A hard dt warning appeared in the grid lift. Re-run with smaller dt before interpreting resolution behavior."
    return "The grid confirmation produced mixed metrics. Keep the next step narrow."


def _next_step(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label in {"cubic_phase_resolution_lift_confirmed", "sign_flip_resolution_lift_confirmed"}:
        return "Do not run a broad 3D sweep yet; next run one tiny lower-amplitude or phase-threshold check at the confirmed grid/resolution setting."
    return "Stay with targeted 31^3/41^3 controls and resolve this grid-lift confound before broader 3D work."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "grid_confirmation_classification",
        "grid_confirmation_family",
        "grid_confirmation_role",
        "grid_size",
        "dx",
        "dt",
        "steps",
        "physical_duration",
        "drive_location",
        "drive_phase_mode",
        "drive_amplitude",
        "drive_frequency",
        "drive_cutoff_time",
        "boundary_faces",
        "boundary_face_count",
        "boundary_phase_offset",
        "boundary_cubic_phase_sign",
        "sponge_strength",
        "sponge_strength_multiplier_vs_original",
        "sponge_width",
        "sponge_width_multiplier",
        "boundary_source_inner_distance",
        "boundary_source_width",
        "source_width_physical_reference",
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
        "recommended_dt_max",
        "hard_stability_dt_max",
        "dt_to_recommended_ratio",
        "dt_to_hard_limit_ratio",
        "stability_warnings",
        "path",
    ]
