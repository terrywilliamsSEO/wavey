"""Tiny 3D sponge-strength controls for the best separated source geometry."""

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


@dataclass(frozen=True)
class SpongeStrengthControlOptions:
    """Options for the tiny 3D sponge-strength check."""

    output_root: str = "runs"
    grid_size: int = 31
    sample_every: int = 2
    radial_bins: int = 24
    near_shell_width_dx: float = 4.0
    weak_sponge_multiplier: float = 0.5
    stronger_sponge_multiplier: float = 2.0
    wider_sponge_multiplier: float = 2.0
    min_near_retention: float = 0.40
    min_near_peak_fraction_of_baseline: float = 0.50
    max_outer_ratio_fraction_for_improvement: float = 0.95
    max_near_radius_range: float = 4.5


def run_3d_sponge_strength_control(
    base_config: SimulationConfig,
    *,
    options: SpongeStrengthControlOptions | None = None,
) -> dict[str, Any]:
    """Run sponge-strength variants for the inner-sponge-edge 3D source."""

    options = options or SpongeStrengthControlOptions()
    control_id = datetime.now().strftime("sponge_strength_3d_%Y%m%d_%H%M%S")
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
    baseline_config = variants[0]
    rows: list[dict[str, Any]] = []
    reference_work_per_area = 0.0

    for idx, config in enumerate(variants):
        if idx == 0:
            summary = _run_variant(config, root, prototype_options)
            reference_area = max(float(summary.get("effective_source_area") or 0.0), EPSILON)
            reference_work_per_area = float(summary["positive_work_before_cutoff"]) / reference_area
        else:
            target_work = reference_work_per_area * max(_effective_source_area(config), EPSILON)
            _calibrate_amplitude(config, target_work)
            summary = _run_variant(config, root, prototype_options)
        _add_sponge_fields(summary, config, baseline_config)
        summary["classification_label"] = None
        rows.append(summary)

    prototype_summary_csv = root / "prototype_3d_summary.csv"
    _write_prototype_csv(prototype_summary_csv, rows, _prototype_summary_fields())
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": control_id,
            "classification": {"label": "sponge_strength_control", "reason": "Sponge-strength control."},
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "sponge_strength_control_report.md"),
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
    classification = classify_sponge_strength_control(control_rows, options)
    for row in control_rows:
        row["sponge_strength_classification"] = classification["label"]

    summary_csv = root / "sponge_strength_control_summary.csv"
    report_path = root / "sponge_strength_control_report.md"
    _write_csv(summary_csv, control_rows, _summary_fields())
    _write_report(report_path, control_id, control_rows, classification, options, audit)
    save_json(
        root / "sponge_strength_control_summary.json",
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


def classify_sponge_strength_control(
    rows: list[dict[str, Any]],
    options: SpongeStrengthControlOptions | None = None,
) -> dict[str, Any]:
    """Classify whether stronger/wider sponge preserves the near-shell signal."""

    options = options or SpongeStrengthControlOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No sponge-strength rows were available.", "checks": {}}
    baseline = next((row for row in rows if row["variant"] == "baseline_sponge_inner_edge"), rows[0])
    absorption_names = {
        "stronger_sponge_inner_edge",
        "wider_sponge_inner_edge",
        "stronger_wider_sponge_inner_edge",
    }
    absorption_rows = [row for row in rows if row.get("variant") in absorption_names]
    if not absorption_rows:
        return {"label": "inconclusive", "reason": "No stronger or wider sponge variants were available.", "checks": {}}

    checked = [(row, _comparison_checks(baseline, row, options)) for row in absorption_rows]
    preserved = [
        (row, checks)
        for row, checks in checked
        if all(
            checks[key]
            for key in (
                "near_peak_preserved",
                "near_shell_retained",
                "near_peak_radius_stable",
                "arrival_sensible",
                "no_outer_boundary_dominance",
            )
        )
    ]
    improved = [(row, checks) for row, checks in preserved if checks["outer_ratio_lowered"]]
    best_pool = improved or preserved or checked
    best, checks = max(best_pool, key=lambda item: _control_score(baseline, item[0]))
    weak = next((row for row in rows if row["variant"] == "weak_sponge_inner_edge"), None)
    weak_checks = _comparison_checks(baseline, weak, options) if weak is not None else {}
    common_checks = {"best_variant": best.get("variant"), "best_checks": checks, "weak_checks": weak_checks}

    if improved:
        return {
            "label": "sponge_strength_suppresses_outer_contamination",
            "reason": f"{best['variant']} preserved the near-defect shell tail while lowering outer/near tail contamination.",
            "best_variant": best["variant"],
            "checks": common_checks,
        }
    if preserved:
        return {
            "label": "sponge_strength_preserves_near_shell",
            "reason": f"{best['variant']} preserved the near-defect shell signal, but outer/near contamination did not clearly improve.",
            "best_variant": best["variant"],
            "checks": common_checks,
        }
    if not checks["near_shell_retained"]:
        return {
            "label": "sponge_sensitive",
            "reason": f"{best['variant']} did not retain the near-defect shell tail under the stronger/wider sponge check.",
            "best_variant": best["variant"],
            "checks": common_checks,
        }
    if checks["global_peak_outer"]:
        return {
            "label": "outer_boundary_contamination_persists",
            "reason": f"{best['variant']} kept global shell-peak dominance in the outer window.",
            "best_variant": best["variant"],
            "checks": common_checks,
        }
    return {
        "label": "inconclusive",
        "reason": "Sponge-strength variants changed mixed metrics, so the 3D near-shell control remains inconclusive.",
        "best_variant": best["variant"],
        "checks": common_checks,
    }


def _variant_plan(
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: SpongeStrengthControlOptions,
) -> list[Prototype3DConfig]:
    baseline = _base_3d_config("baseline_sponge_inner_edge", base, prototype_options, "boundary", "cubic")
    base_strength = baseline.sponge_strength
    base_width = baseline.sponge_width
    source_distance = base_width
    source_width = baseline.dx

    plan = [
        ("baseline_sponge_inner_edge", 1.0, 1.0),
        ("weak_sponge_inner_edge", options.weak_sponge_multiplier, 1.0),
        ("stronger_sponge_inner_edge", options.stronger_sponge_multiplier, 1.0),
        ("wider_sponge_inner_edge", 1.0, options.wider_sponge_multiplier),
        (
            "stronger_wider_sponge_inner_edge",
            options.stronger_sponge_multiplier,
            options.wider_sponge_multiplier,
        ),
    ]
    variants: list[Prototype3DConfig] = []
    for name, strength_multiplier, width_multiplier in plan:
        config = _base_3d_config(name, base, prototype_options, "boundary", "cubic")
        config.sponge_strength = base_strength * strength_multiplier
        config.sponge_width = base_width * width_multiplier
        config.boundary_source_inner_distance = source_distance
        config.boundary_source_width = source_width
        variants.append(config)
    return variants


def _add_sponge_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    baseline_config: Prototype3DConfig,
) -> None:
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    summary["sponge_width_multiplier"] = config.sponge_width / max(baseline_config.sponge_width, EPSILON)
    summary["sponge_strength_multiplier"] = config.sponge_strength / max(baseline_config.sponge_strength, EPSILON)


def _comparison_checks(
    baseline: dict[str, Any],
    candidate: dict[str, Any] | None,
    options: SpongeStrengthControlOptions,
) -> dict[str, Any]:
    if candidate is None:
        return {}
    near_peak_ratio = _ratio(candidate.get("near_shell_peak_fraction_of_work"), baseline.get("near_shell_peak_fraction_of_work"))
    outer_ratio_fraction = _ratio(candidate.get("outer_to_near_tail_energy_ratio"), baseline.get("outer_to_near_tail_energy_ratio"))
    baseline_radius = baseline.get("late_tail_near_shell_peak_radius_median")
    candidate_radius = candidate.get("late_tail_near_shell_peak_radius_median")
    radius_shift = None
    if baseline_radius not in (None, "") and candidate_radius not in (None, ""):
        radius_shift = abs(float(candidate_radius) - float(baseline_radius))
    arrival = candidate.get("first_meaningful_near_shell_arrival_time")
    return {
        "baseline_variant": baseline.get("variant"),
        "candidate_variant": candidate.get("variant"),
        "near_peak_ratio_to_baseline": near_peak_ratio,
        "outer_ratio_fraction_of_baseline": outer_ratio_fraction,
        "near_peak_preserved": near_peak_ratio >= options.min_near_peak_fraction_of_baseline,
        "outer_ratio_lowered": outer_ratio_fraction <= options.max_outer_ratio_fraction_for_improvement,
        "near_shell_retained": _float_or(candidate.get("near_shell_tail_retention"), 0.0) >= options.min_near_retention,
        "near_peak_radius_stable": (
            _float_or(candidate.get("late_tail_near_shell_peak_radius_range"), 999.0) <= options.max_near_radius_range
            and (radius_shift is None or radius_shift <= options.max_near_radius_range)
        ),
        "arrival_sensible": arrival is not None and 0.0 <= float(arrival) <= float(candidate.get("physical_duration") or 0.0),
        "no_outer_boundary_dominance": not bool(candidate.get("global_peak_in_outer_window")),
        "global_peak_outer": bool(candidate.get("global_peak_in_outer_window")),
        "radius_shift": radius_shift,
    }


def _control_score(baseline: dict[str, Any], candidate: dict[str, Any]) -> float:
    near_peak = _ratio(candidate.get("near_shell_peak_fraction_of_work"), baseline.get("near_shell_peak_fraction_of_work"))
    outer_drop = _ratio(baseline.get("outer_to_near_tail_energy_ratio"), candidate.get("outer_to_near_tail_energy_ratio"))
    retention = float(candidate.get("near_shell_tail_retention") or 0.0)
    radius_penalty = 1.0 / max(float(candidate.get("late_tail_near_shell_peak_radius_range") or 1.0), 1.0)
    outer_bonus = 0.5 if not bool(candidate.get("global_peak_in_outer_window")) else -0.5
    return near_peak + outer_drop + retention + radius_penalty + outer_bonus


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: SpongeStrengthControlOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Sponge-Strength Control: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny 31^3 control for the question: if the source stays at the inner sponge edge and injected "
            "work per physical source area is matched, does the near-defect shell signal survive weaker, "
            "stronger, wider, and stronger+wider sponge settings?"
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
        "| Variant | Sponge x | Width x | Source d | Source/Sponge | Work/Area | Near Peak/Work | Near Retention | Near Radius Range | Outer/Near Tail | Global Peak R | Global Outer? | Arrival |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('sponge_strength_multiplier'))} | "
            f"{_format(row.get('sponge_width_multiplier'))} | "
            f"{_format(row.get('boundary_source_inner_distance'))} | "
            f"{_format(row.get('source_sponge_overlap_fraction'))} | "
            f"{_format(row.get('work_per_source_area'))} | "
            f"{_format(row.get('near_shell_peak_fraction_of_work'))} | "
            f"{_format(row.get('near_shell_tail_retention'))} | "
            f"{_format(row.get('late_tail_near_shell_peak_radius_range'))} | "
            f"{_format(row.get('outer_to_near_tail_energy_ratio'))} | "
            f"{_format(row.get('global_shell_peak_radius'))} | "
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
            "- Grid size, domain size, defect, drive frequency, cutoff time, and source position are unchanged.",
            "- Work is matched per physical source area to the baseline inner-sponge-edge source.",
            "- Wider sponge variants intentionally keep the source at the original inner-edge location instead of moving it.",
            "",
            "## Files",
            "",
            "- `sponge_strength_control_summary.csv`",
            "- `sponge_strength_control_summary.json`",
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
    if label == "sponge_strength_suppresses_outer_contamination":
        return (
            "At least one stronger or wider sponge variant preserved the retained near-defect shell window while reducing "
            "outer-window tail contamination. Check the variant table before treating wider sponge as clean, because it "
            "can reintroduce source/sponge overlap when the source location is held fixed."
        )
    if label == "sponge_strength_preserves_near_shell":
        return (
            "The near-defect shell signal survived stronger/wider absorption, but the outer/near ratio did not improve "
            "enough to call the sponge change a cleanup."
        )
    if label == "sponge_sensitive":
        return (
            "The near-defect shell signal is sensitive to stronger or wider sponge settings. Stay at 31^3 and inspect "
            "source damping/absorption geometry before any source-geometry comparison."
        )
    if label == "outer_boundary_contamination_persists":
        return "Outer-window residue still dominates the global shell metric, so the separated-source geometry is not clean yet."
    return "The sponge-strength check changed mixed metrics. Keep this as a narrow control result, not a broader 3D claim."


def _next_step(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "sponge_strength_suppresses_outer_contamination":
        return "Keep 31^3 and run a tiny source-geometry comparison from the stronger-sponge inner-edge setup; do not increase grid size yet."
    if label == "sponge_strength_preserves_near_shell":
        return "Keep 31^3 and run a tiny source-geometry comparison from the inner-sponge-edge setup; do not increase grid size yet."
    return "Keep 31^3 and inspect sponge/source geometry before adding any larger grid or broad sweep."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "sponge_strength_classification",
        "grid_size",
        "dx",
        "dt",
        "physical_duration",
        "drive_location",
        "drive_phase_mode",
        "drive_amplitude",
        "drive_frequency",
        "drive_cutoff_time",
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
