"""Tiny 3D source/sponge separation controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import (
    EPSILON,
    Lattice3D,
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


@dataclass(frozen=True)
class SourceSpongeControlOptions:
    """Options for the tiny 3D source/sponge separation control."""

    output_root: str = "runs"
    grid_size: int = 31
    sample_every: int = 2
    radial_bins: int = 24
    gap_cells_from_sponge: float = 3.0
    near_shell_width_dx: float = 4.0
    min_near_peak_gain: float = 1.10
    max_outer_ratio_fraction: float = 0.75
    max_near_radius_range: float = 4.5


def run_3d_source_sponge_control(
    base_config: SimulationConfig,
    *,
    options: SourceSpongeControlOptions | None = None,
) -> dict[str, Any]:
    """Run source/sponge separation variants at tiny 31^3 scale."""

    options = options or SourceSpongeControlOptions()
    control_id = datetime.now().strftime("source_sponge_3d_%Y%m%d_%H%M%S")
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
        summary["classification_label"] = None
        rows.append(summary)

    prototype_summary_csv = root / "prototype_3d_summary.csv"
    _write_prototype_csv(prototype_summary_csv, rows, _prototype_summary_fields())
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": control_id,
            "classification": {"label": "source_sponge_control", "reason": "Source/sponge separation control."},
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "source_sponge_control_report.md"),
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
    classification = classify_source_sponge_control(control_rows, options)
    for row in control_rows:
        row["source_sponge_classification"] = classification["label"]

    summary_csv = root / "source_sponge_control_summary.csv"
    report_path = root / "source_sponge_control_report.md"
    _write_csv(summary_csv, control_rows, _summary_fields())
    _write_report(report_path, control_id, control_rows, classification, options, audit)
    save_json(
        root / "source_sponge_control_summary.json",
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


def classify_source_sponge_control(
    rows: list[dict[str, Any]],
    options: SourceSpongeControlOptions | None = None,
) -> dict[str, Any]:
    """Classify whether source/sponge separation strengthens the near-defect shell."""

    options = options or SourceSpongeControlOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No source/sponge rows were available.", "checks": {}}
    reference = next((row for row in rows if row["variant"] == "source_at_outer_boundary_inside_sponge"), rows[0])
    candidates = [row for row in rows if row is not reference]
    checked = [(row, _comparison_checks(reference, row, options)) for row in candidates]
    full_pass = [
        (row, checks)
        for row, checks in checked
        if all(
            checks[key]
            for key in (
                "near_peak_strengthened",
                "outer_ratio_lowered",
                "near_peak_radius_stable",
                "near_shell_retained",
                "arrival_sensible",
                "no_outer_boundary_dominance",
            )
        )
    ]
    retained_candidates = [
        (row, checks)
        for row, checks in checked
        if checks["near_shell_retained"]
        and checks["arrival_sensible"]
        and checks["near_peak_radius_stable"]
        and checks["no_outer_boundary_dominance"]
    ]
    if full_pass:
        best, checks = max(full_pass, key=lambda item: _improvement_score(reference, item[0]))
    elif retained_candidates:
        best, checks = max(retained_candidates, key=lambda item: _improvement_score(reference, item[0]))
    else:
        best = max(candidates, key=lambda row: _improvement_score(reference, row), default=None)
        checks = _comparison_checks(reference, best, options) if best is not None else {}
    if best is None:
        return {"label": "inconclusive", "reason": "No source/sponge comparison candidates were available.", "checks": {}}

    if all(
        checks[key]
        for key in (
            "near_peak_strengthened",
            "outer_ratio_lowered",
            "near_peak_radius_stable",
            "near_shell_retained",
            "arrival_sensible",
            "no_outer_boundary_dominance",
        )
    ):
        return {
            "label": "source_sponge_separation_improves_near_shell",
            "reason": f"{best['variant']} strengthened the near-defect shell without outer-boundary dominance.",
            "best_variant": best["variant"],
            "checks": checks,
        }
    if checks["near_peak_strengthened"] and checks["outer_ratio_lowered"]:
        if not checks["near_shell_retained"]:
            return {
                "label": "transient_near_shell_improvement_not_retained",
                "reason": f"{best['variant']} strengthened the near-defect peak, but the post-cutoff near-shell tail did not retain it.",
                "best_variant": best["variant"],
                "checks": checks,
            }
        return {
            "label": "near_shell_improves_but_outer_bias_persists",
            "reason": f"{best['variant']} improved near-shell metrics, but outer-boundary contamination remains.",
            "best_variant": best["variant"],
            "checks": checks,
        }
    if not checks["near_peak_strengthened"]:
        return {
            "label": "near_shell_not_strengthened",
            "reason": "Separating the source from the sponge did not increase near-defect shell peak per work.",
            "best_variant": best["variant"],
            "checks": checks,
        }
    return {
        "label": "inconclusive",
        "reason": "Source/sponge separation changed metrics, but not enough criteria moved together.",
        "best_variant": best["variant"],
        "checks": checks,
    }


def _variant_plan(
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: SourceSpongeControlOptions,
) -> list[Prototype3DConfig]:
    base_config = _base_3d_config("source_at_outer_boundary_inside_sponge", base, prototype_options, "boundary", "cubic")
    dx = base_config.dx
    source_width = dx
    variants = [
        base_config,
        _base_3d_config("source_at_inner_sponge_edge", base, prototype_options, "boundary", "cubic"),
        _base_3d_config("source_excluded_from_sponge_damping", base, prototype_options, "boundary", "cubic"),
        _base_3d_config("source_inside_domain_gap_from_sponge", base, prototype_options, "boundary", "cubic"),
    ]
    variants[0].boundary_source_inner_distance = 0.0
    variants[0].boundary_source_width = source_width
    variants[1].boundary_source_inner_distance = variants[1].sponge_width
    variants[1].boundary_source_width = source_width
    variants[2].boundary_source_inner_distance = 0.0
    variants[2].boundary_source_width = source_width
    variants[2].exclude_source_from_sponge_damping = True
    variants[3].boundary_source_inner_distance = variants[3].sponge_width + options.gap_cells_from_sponge * dx
    variants[3].boundary_source_width = source_width
    return variants


def _effective_source_area(config: Prototype3DConfig) -> float:
    return float(Lattice3D(config).source.effective_area)


def _merge_rows(prototype_rows: list[dict[str, Any]], audit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audit_by_variant = {row["variant"]: row for row in audit_rows}
    merged = []
    for row in prototype_rows:
        audit = audit_by_variant.get(row["variant"], {})
        merged.append({**row, **audit})
    return merged


def _improvement_score(reference: dict[str, Any], candidate: dict[str, Any]) -> float:
    near_gain = _ratio(candidate.get("near_shell_peak_fraction_of_work"), reference.get("near_shell_peak_fraction_of_work"))
    outer_ratio = _ratio(reference.get("outer_to_near_tail_energy_ratio"), candidate.get("outer_to_near_tail_energy_ratio"))
    retention = float(candidate.get("near_shell_tail_retention") or 0.0)
    range_penalty = 1.0 / max(float(candidate.get("late_tail_near_shell_peak_radius_range") or 1.0), 1.0)
    return near_gain + outer_ratio + retention + range_penalty


def _comparison_checks(
    reference: dict[str, Any],
    best: dict[str, Any],
    options: SourceSpongeControlOptions,
) -> dict[str, Any]:
    near_gain = _ratio(best.get("near_shell_peak_fraction_of_work"), reference.get("near_shell_peak_fraction_of_work"))
    outer_ratio_fraction = _ratio(best.get("outer_to_near_tail_energy_ratio"), reference.get("outer_to_near_tail_energy_ratio"))
    arrival = best.get("first_meaningful_near_shell_arrival_time")
    return {
        "reference_variant": reference.get("variant"),
        "best_variant": best.get("variant"),
        "near_peak_gain": near_gain,
        "outer_ratio_fraction": outer_ratio_fraction,
        "near_peak_strengthened": near_gain >= options.min_near_peak_gain,
        "outer_ratio_lowered": outer_ratio_fraction <= options.max_outer_ratio_fraction,
        "near_peak_radius_stable": _float_or(best.get("late_tail_near_shell_peak_radius_range"), 999.0) <= options.max_near_radius_range,
        "near_shell_retained": _float_or(best.get("near_shell_tail_retention"), 0.0) >= 0.20,
        "arrival_sensible": arrival is not None and 0.0 <= float(arrival) <= float(best.get("physical_duration") or 0.0),
        "no_outer_boundary_dominance": not bool(best.get("global_peak_in_outer_window")),
    }


def _ratio(numerator: Any, denominator: Any) -> float:
    return float(numerator or 0.0) / max(float(denominator or 0.0), EPSILON)


def _float_or(value: Any, default: float) -> float:
    if value in (None, ""):
        return default
    return float(value)


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: SourceSpongeControlOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Source/Sponge Control: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny 31^3 control for the question: if the boundary source is separated from sponge damping, "
            "does the near-defect shell signal strengthen without outer-boundary contamination?"
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
        "| Variant | Source d | Exclude Sponge | Source/Sponge | Work/Area | Near Peak/Work | Near Retention | Near Radius Range | Outer/Near Tail | Global Peak R | Global Outer? | Arrival |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{_format(row.get('boundary_source_inner_distance'))} | "
            f"{row.get('exclude_source_from_sponge_damping')} | "
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
            "## Files",
            "",
            "- `source_sponge_control_summary.csv`",
            "- `source_sponge_control_summary.json`",
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
    if label == "source_sponge_separation_improves_near_shell":
        return "A separated source strengthened the near-defect shell window and reduced outer-boundary dominance in this tiny control."
    if label == "near_shell_improves_but_outer_bias_persists":
        return "Source/sponge separation helped the near-defect window, but the global shell metric is still contaminated by outer-boundary residue."
    if label == "near_shell_not_strengthened":
        return "Moving or undamping the source did not strengthen the near-defect shell signal under matched work per source area."
    return "The control changed mixed metrics. Keep this as a narrow diagnostic result, not a broader 3D claim."


def _next_step(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "source_sponge_separation_improves_near_shell":
        return "Repeat only the best separated-source geometry with a small sponge-strength check at 31^3 before considering any larger 3D grid."
    if label == "near_shell_improves_but_outer_bias_persists":
        return "Keep 31^3 and harden the 3D classifier around near-defect shell windows before changing grid size."
    return "Stay at 31^3 and inspect whether the 3D boundary source geometry or shell-window definition needs revision."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "source_sponge_classification",
        "grid_size",
        "dx",
        "dt",
        "physical_duration",
        "drive_location",
        "drive_phase_mode",
        "drive_amplitude",
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


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, np.generic):
        return _csv_value(value.item())
    return value


def _format(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    if isinstance(value, bool):
        return str(value).lower()
    return f"{float(value):.6g}"
