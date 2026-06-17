"""Targeted boundary-transport mechanism controls for the 0.92 candidate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import math

from .config import SimulationConfig, save_json
from .core_modal_probe import (
    CoreModalProbeOptions,
    _attach_reference_similarities,
    _boundary_reference_config,
    _calibrate_drive_amplitude,
    _core_match_score,
    _core_success,
    _format,
    _run_and_diagnose,
    _summary_fields,
    _summary_row,
    _write_comparison_plots,
    _write_csv,
)
from .fixed_domain_controls import _fixed_domain_config


@dataclass(frozen=True)
class TransportControlOptions:
    """Options for the narrow source-geometry transport control plan."""

    output_root: str = "runs"
    frame_interval: int = 20
    window_steps: int = 30
    source_normalization: str = "constant_total_work"
    reference_grid_size: int = 63
    min_peak_separation: float = 1.5
    secondary_min_peak_separation: float = 2.0
    peak_percentile: float = 55.0
    min_core_retention: float = 0.15
    min_similarity_to_reference: float = 0.35
    min_radial_similarity_to_reference: float = 0.45
    min_m4_strength: float = 0.08


TRANSPORT_EXTRA_FIELDS = [
    "transport_question",
    "driver_sides",
    "boundary_phase_mode",
    "boundary_phase_winding",
    "core_drive_phase_mode",
    "core_drive_phase_winding",
    "core_drive_inner_radius_physical",
    "core_drive_outer_radius_physical",
    "core_drive_angle_center",
    "core_drive_angle_width",
    "transport_match_score",
]


def run_transport_controls(
    base_config: SimulationConfig,
    *,
    options: TransportControlOptions | None = None,
    reference_root: str | Path = "runs",
) -> dict[str, Any]:
    """Run narrow source-geometry controls against the 63x63 boundary reference."""

    options = options or TransportControlOptions()
    probe_options = _probe_options(options)
    control_id = datetime.now().strftime("transport_controls_%Y%m%d_%H%M%S")
    control_root = Path(options.output_root) / control_id
    control_root.mkdir(parents=True, exist_ok=False)

    rows: list[dict[str, Any]] = []
    configs_by_variant: dict[str, SimulationConfig] = {}

    reference_variant = f"boundary_reference_{options.reference_grid_size}"
    boundary_reference = _boundary_reference_config(
        base_config,
        options.reference_grid_size,
        options.source_normalization,
    )
    _run_variant(
        reference_variant,
        boundary_reference,
        "four-side source-normalized boundary reference",
        rows,
        configs_by_variant,
        control_root,
        probe_options,
        reference_root,
    )
    target_work = float(rows[0].get("injected_work_before_cutoff") or 0.0)

    for variant, question, config, drive_kind in _transport_variant_plan(base_config, options.reference_grid_size):
        _calibrate_drive_amplitude(config, target_work, drive_kind=drive_kind)
        _run_variant(
            variant,
            config,
            question,
            rows,
            configs_by_variant,
            control_root,
            probe_options,
            reference_root,
        )

    _attach_reference_similarities(rows, configs_by_variant)
    for row in rows:
        row["transport_match_score"] = _core_match_score(row) if row["variant"] != reference_variant else 1.0

    best_transport = _best_transport_match(rows)
    classification = classify_transport_controls(rows, options)
    for row in rows:
        row["classification_label"] = classification["label"]

    summary_path = control_root / "transport_control_summary.csv"
    report_path = control_root / "transport_control_report.md"
    plots_dir = control_root / "transport_control_comparison_plots"
    plots_dir.mkdir(exist_ok=True)
    _write_csv(summary_path, rows, _transport_summary_fields())
    _write_comparison_plots(rows, plots_dir)
    _write_report(report_path, control_id, base_config, rows, classification, best_transport, plots_dir, options)
    save_json(
        control_root / "transport_control_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "best_transport_match": best_transport,
            "variants": rows,
            "summary_csv": str(summary_path),
            "report_path": str(report_path),
            "comparison_plots_path": str(plots_dir),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "best_transport_match": best_transport,
        "variants": rows,
        "summary_csv": str(summary_path),
        "report_path": str(report_path),
        "comparison_plots_path": str(plots_dir),
        "path": str(control_root),
    }


def classify_transport_controls(
    rows: list[dict[str, Any]],
    options: TransportControlOptions | None = None,
) -> dict[str, Any]:
    """Classify which source geometry, if any, reproduces the reference family."""

    options = options or TransportControlOptions()
    probe_options = _probe_options(options)
    reference = next((row for row in rows if str(row.get("variant", "")).startswith("boundary_reference_")), None)
    if reference is None:
        return {"label": "inconclusive", "reason": "A boundary_reference row is required.", "checks": {}}

    reference_period = float(
        reference.get("diagnostic_envelope_period")
        or reference.get("breathing_period_after_cutoff")
        or reference.get("raw_diagnostic_frame_period")
        or 0.0
    )
    reference_variant = reference.get("variant")
    non_reference = [row for row in rows if row.get("variant") != reference_variant]
    annulus_rows = [row for row in non_reference if row.get("drive_location") == "annulus"]
    boundary_rows = [row for row in non_reference if row.get("drive_location") == "boundary"]
    annulus_successes = [row for row in annulus_rows if _core_success(row, reference_period, probe_options)]
    boundary_successes = [row for row in boundary_rows if _core_success(row, reference_period, probe_options)]
    inner_successes = [row for row in annulus_successes if "inner" in str(row.get("variant", "")) or "interface" in str(row.get("variant", ""))]
    rotating_rows = [row for row in non_reference if "rotating" in str(row.get("variant", ""))]
    rotating_best_m4 = max((float(row.get("m4_strength_after_cutoff") or 0.0) for row in rotating_rows), default=0.0)
    uniform_annulus_best_m4 = max(
        (
            float(row.get("m4_strength_after_cutoff") or 0.0)
            for row in annulus_rows
            if row.get("core_drive_phase_mode") == "uniform"
        ),
        default=0.0,
    )
    checks = {
        "boundary_reference_breathing": bool(reference.get("breathing_detected_after_cutoff")),
        "annulus_success_count": len(annulus_successes),
        "boundary_geometry_success_count": len(boundary_successes),
        "inner_ring_success_count": len(inner_successes),
        "rotating_best_m4_strength": rotating_best_m4,
        "uniform_annulus_best_m4_strength": uniform_annulus_best_m4,
        "best_transport_match": (_best_transport_match(rows) or {}).get("variant"),
    }

    if inner_successes:
        return {
            "label": "inner_ring_transport_supported",
            "reason": "An inner or interface annulus source reproduced the reference-like retained breathing family.",
            "checks": checks,
        }
    if annulus_successes:
        return {
            "label": "annulus_transport_supported",
            "reason": "At least one annulus source reproduced reference-like retained breathing with matched injected work.",
            "checks": checks,
        }
    if boundary_successes:
        return {
            "label": "boundary_geometry_sensitive",
            "reason": "A boundary-geometry variant reproduced the retained family, while direct annulus variants did not.",
            "checks": checks,
        }
    if bool(reference.get("breathing_detected_after_cutoff")):
        return {
            "label": "boundary_reference_only",
            "reason": "The four-side boundary reference retained breathing, but targeted transport variants did not reproduce it.",
            "checks": checks,
        }
    return {
        "label": "inconclusive",
        "reason": "The boundary reference did not clearly retain the family under this control pass.",
        "checks": checks,
    }


def _transport_variant_plan(base_config: SimulationConfig, grid_size: int) -> list[tuple[str, str, SimulationConfig, str]]:
    suffix = f"_{grid_size}"
    radius = float(
        base_config.defect.radius_physical
        if base_config.defect.radius_physical is not None
        else base_config.defect.radius
    )
    core_radius = float(
        base_config.core_radius_physical
        if base_config.core_radius_physical is not None
        else base_config.effective_core_radius
    )
    radial_peak = min(10.0, float(base_config.grid_size - 1) / 2.0 - 1.0)
    annulus_inner = radius + 1.0
    annulus_outer = min(radius + 4.0, radial_peak + 1.0)
    return [
        (
            f"boundary_left{suffix}",
            "one-side boundary source; tests whether four-side interference is required",
            _boundary_geometry_config(base_config, grid_size, sides=("left",), phase_mode="uniform"),
            "boundary",
        ),
        (
            f"boundary_left_right{suffix}",
            "two-side symmetric boundary source; tests pairwise interference geometry",
            _boundary_geometry_config(base_config, grid_size, sides=("left", "right"), phase_mode="uniform"),
            "boundary",
        ),
        (
            f"boundary_rotating_m4{suffix}",
            "four-side rotating boundary phase; tests whether angular injection seeds m=4",
            _boundary_geometry_config(base_config, grid_size, sides=("left", "right", "top", "bottom"), phase_mode="rotating", winding=4),
            "boundary",
        ),
        (
            f"inner_ring_interface{suffix}",
            "inner ring at the defect/core interface; tests whether the cavity boundary is the key source region",
            _annulus_config(base_config, grid_size, inner=max(0.0, radius - 0.5), outer=core_radius + 0.5),
            "core",
        ),
        (
            f"annulus_near_defect{suffix}",
            "full annulus just outside the defect; tests near-defect transport assembly",
            _annulus_config(base_config, grid_size, inner=annulus_inner, outer=annulus_outer),
            "core",
        ),
        (
            f"annulus_radial_peak{suffix}",
            "annulus near the source-normalized retained radial peak; tests shorter transport distance",
            _annulus_config(base_config, grid_size, inner=max(core_radius, radial_peak - 1.0), outer=radial_peak + 1.0),
            "core",
        ),
        (
            f"annulus_sector_one_side{suffix}",
            "one-sided annulus sector; tests local injection versus full-ring interference",
            _annulus_config(
                base_config,
                grid_size,
                inner=annulus_inner,
                outer=annulus_outer,
                angle_center=0.0,
                angle_width=0.5 * math.pi,
            ),
            "core",
        ),
        (
            f"annulus_rotating_m4{suffix}",
            "full annulus with m=4 rotating phase; tests whether angular injection seeds the m=4 tail",
            _annulus_config(
                base_config,
                grid_size,
                inner=annulus_inner,
                outer=annulus_outer,
                phase_mode="rotating",
                winding=4,
            ),
            "core",
        ),
    ]


def _boundary_geometry_config(
    base_config: SimulationConfig,
    grid_size: int,
    *,
    sides: tuple[str, ...],
    phase_mode: str,
    winding: int = 1,
) -> SimulationConfig:
    config = _fixed_domain_config(base_config, grid_size, source_normalization="constant_boundary_flux")
    config.drive_location = "boundary"
    config.driver.sides = sides
    config.driver.phase_mode = phase_mode
    config.driver.rotating_phase_winding = winding
    config.core_drive_amplitude = 0.0
    config.core_drive_mode = "burst"
    config.core_drive_cutoff_time = None
    return config


def _annulus_config(
    base_config: SimulationConfig,
    grid_size: int,
    *,
    inner: float,
    outer: float,
    phase_mode: str = "uniform",
    winding: int = 1,
    angle_center: float | None = None,
    angle_width: float | None = None,
) -> SimulationConfig:
    config = _fixed_domain_config(base_config, grid_size, source_normalization="constant_boundary_flux")
    config.drive_location = "annulus"
    config.driver.amplitude = 0.0
    config.core_drive_mode = "burst"
    config.core_drive_frequency = base_config.driver.frequency
    config.core_drive_amplitude = base_config.driver.amplitude
    config.core_drive_phase = 0.0
    config.core_drive_phase_mode = phase_mode
    config.core_drive_rotating_phase_winding = winding
    config.core_drive_cutoff_time = base_config.driver.drive_cutoff_time
    config.driver.drive_cutoff_time = config.core_drive_cutoff_time
    config.core_drive_inner_radius_physical = inner
    config.core_drive_outer_radius_physical = outer
    config.core_drive_angle_center = angle_center
    config.core_drive_angle_width = angle_width
    config.normalize_core_drive_work = True
    config.core_drive_work_reference = "boundary_reference"
    return config


def _run_variant(
    variant: str,
    config: SimulationConfig,
    question: str,
    rows: list[dict[str, Any]],
    configs_by_variant: dict[str, SimulationConfig],
    control_root: Path,
    probe_options: CoreModalProbeOptions,
    reference_root: str | Path,
) -> None:
    configs_by_variant[variant] = config
    summary, diagnostics = _run_and_diagnose(variant, config, control_root, probe_options, reference_root)
    row = _summary_row(variant, config, summary, diagnostics, probe_options)
    row.update(_transport_metadata(config, question))
    rows.append(row)


def _transport_metadata(config: SimulationConfig, question: str) -> dict[str, Any]:
    return {
        "transport_question": question,
        "driver_sides": ",".join(config.driver.sides),
        "boundary_phase_mode": config.driver.phase_mode,
        "boundary_phase_winding": config.driver.rotating_phase_winding,
        "core_drive_phase_mode": config.core_drive_phase_mode if config.drive_location != "boundary" else "",
        "core_drive_phase_winding": config.core_drive_rotating_phase_winding if config.drive_location != "boundary" else "",
        "core_drive_inner_radius_physical": config.core_drive_inner_radius_physical,
        "core_drive_outer_radius_physical": config.core_drive_outer_radius_physical,
        "core_drive_angle_center": config.core_drive_angle_center,
        "core_drive_angle_width": config.core_drive_angle_width,
    }


def _best_transport_match(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [row for row in rows if not str(row.get("variant", "")).startswith("boundary_reference_")]
    if not candidates:
        return None
    best = max(candidates, key=_core_match_score)
    return {
        "variant": best["variant"],
        "score": _core_match_score(best),
        "drive_location": best.get("drive_location"),
        "retention": best.get("post_cutoff_retention"),
        "period": best.get("breathing_period_after_cutoff"),
        "diagnostic_period": best.get("diagnostic_envelope_period"),
        "radial_similarity": best.get("radial_profile_similarity_to_boundary_reference"),
        "frame_similarity": best.get("best_frame_similarity_to_boundary_reference"),
        "m4_strength": best.get("m4_strength_after_cutoff"),
    }


def _probe_options(options: TransportControlOptions) -> CoreModalProbeOptions:
    return CoreModalProbeOptions(
        output_root=options.output_root,
        frame_interval=options.frame_interval,
        window_steps=options.window_steps,
        source_normalization=options.source_normalization,
        reference_grid_size=options.reference_grid_size,
        confirmation_grid_size=options.reference_grid_size,
        min_peak_separation=options.min_peak_separation,
        secondary_min_peak_separation=options.secondary_min_peak_separation,
        peak_percentile=options.peak_percentile,
        min_core_retention=options.min_core_retention,
        min_similarity_to_reference=options.min_similarity_to_reference,
        min_radial_similarity_to_reference=options.min_radial_similarity_to_reference,
        min_m4_strength=options.min_m4_strength,
    )


def _transport_summary_fields() -> list[str]:
    fields = list(_summary_fields())
    insertion_index = fields.index("grid_size") if "grid_size" in fields else len(fields)
    for field in reversed(TRANSPORT_EXTRA_FIELDS):
        if field not in fields:
            fields.insert(insertion_index, field)
    return fields


def _write_report(
    path: Path,
    control_id: str,
    base_config: SimulationConfig,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    best_transport: dict[str, Any] | None,
    plots_dir: Path,
    options: TransportControlOptions,
) -> None:
    lines = [
        f"# Transport Control Report: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Narrow source-geometry controls for the source-normalized fixed-domain 0.92 candidate. "
            "All variants are matched to the 63x63 boundary-reference injected work before cutoff."
        ),
        "",
        "## Base Case",
        "",
        f"- Source config grid: `{base_config.grid_size}`",
        f"- Control grid: `{options.reference_grid_size}`",
        f"- Drive frequency: `{base_config.driver.frequency}`",
        f"- Drive cutoff time: `{base_config.driver.drive_cutoff_time}`",
        f"- Source normalization for boundary references: `{options.source_normalization}`",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best non-reference transport match: `{(best_transport or {}).get('variant', 'n/a')}`",
        "",
        "## Direct Answers",
        "",
    ]
    for answer in _report_answers(rows, best_transport):
        lines.append(f"- {answer}")

    lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| Variant | Question | Drive | Work | Retention | Envelope Period | Metric min_sep=1.5 | Raw Period | Breathing | Radial Peak | m4 | Radial Sim | Frame Sim |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        drive = row["drive_location"] if row["drive_location"] == "boundary" else f"{row['drive_location']}:{row['core_drive_mode']}"
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('transport_question')} | "
            f"{drive} | "
            f"{_format(row.get('injected_work_before_cutoff'))} | "
            f"{_format(row.get('post_cutoff_retention'))} | "
            f"{_format(row.get('diagnostic_envelope_period'))} | "
            f"{_format(row.get('breathing_period_after_cutoff'))} | "
            f"{_format(row.get('raw_diagnostic_frame_period'))} | "
            f"{row.get('breathing_detected_after_cutoff')} | "
            f"{_format(row.get('radial_peak_after_cutoff_physical'))} | "
            f"{_format(row.get('m4_strength_after_cutoff'))} | "
            f"{_format(row.get('radial_profile_similarity_to_boundary_reference'))} | "
            f"{_format(row.get('best_frame_similarity_to_boundary_reference'))} |"
        )

    lines.extend(
        [
            "",
            "## Source Geometry",
            "",
            "| Variant | Boundary Sides | Boundary Phase | Core Phase | Inner R | Outer R | Angle Center | Angle Width | Core Area | Work / Core Area |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('driver_sides')} | "
            f"{row.get('boundary_phase_mode')}:{row.get('boundary_phase_winding')} | "
            f"{row.get('core_drive_phase_mode') or 'n/a'}:{row.get('core_drive_phase_winding') or 'n/a'} | "
            f"{_format(row.get('core_drive_inner_radius_physical'))} | "
            f"{_format(row.get('core_drive_outer_radius_physical'))} | "
            f"{_format(row.get('core_drive_angle_center'))} | "
            f"{_format(row.get('core_drive_angle_width'))} | "
            f"{_format(row.get('core_drive_effective_area'))} | "
            f"{_format(row.get('injected_work_per_core_area'))} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _classification_interpretation(classification),
            "",
            "## Files",
            "",
            "- `transport_control_summary.csv`",
            f"- Comparison plots: `{plots_dir}`",
        ]
    )
    for row in rows:
        lines.append(f"- `{row['variant']}` mode diagnostics: `{row.get('mode_shape_diagnostics_report')}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _report_answers(rows: list[dict[str, Any]], best_transport: dict[str, Any] | None) -> list[str]:
    non_reference = [row for row in rows if not str(row.get("variant", "")).startswith("boundary_reference_")]
    annulus = [row for row in non_reference if row.get("drive_location") == "annulus"]
    boundary = [row for row in non_reference if row.get("drive_location") == "boundary"]
    breathing_annulus = [row["variant"] for row in annulus if row.get("breathing_detected_after_cutoff")]
    breathing_boundary = [row["variant"] for row in boundary if row.get("breathing_detected_after_cutoff")]
    rotating = [row for row in non_reference if "rotating" in str(row.get("variant", ""))]
    sector = next((row for row in rows if str(row.get("variant", "")).startswith("annulus_sector_one_side_")), None)
    full_annulus = next((row for row in rows if str(row.get("variant", "")).startswith("annulus_near_defect_")), None)
    return [
        f"Annulus variants with retained breathing: `{', '.join(breathing_annulus) or 'none'}`.",
        f"Boundary-geometry variants with retained breathing: `{', '.join(breathing_boundary) or 'none'}`.",
        (
            "Best non-reference match is "
            f"`{(best_transport or {}).get('variant', 'n/a')}` with score `{_format((best_transport or {}).get('score'))}`, "
            f"radial similarity `{_format((best_transport or {}).get('radial_similarity'))}`, "
            f"frame similarity `{_format((best_transport or {}).get('frame_similarity'))}`, "
            f"and m4 `{_format((best_transport or {}).get('m4_strength'))}`."
        ),
        (
            "One-sided annulus sector retention is "
            f"`{_format((sector or {}).get('post_cutoff_retention'))}` versus full near-defect annulus "
            f"`{_format((full_annulus or {}).get('post_cutoff_retention'))}`."
        ),
        (
            "Rotating-phase m4 strengths are "
            f"`{', '.join(f'{row['variant']}={_format(row.get('m4_strength_after_cutoff'))}' for row in rotating) or 'n/a'}`."
        ),
        "This is a source-geometry control only; it does not broaden frequency, amplitude, or long-run sweep coverage.",
    ]


def _classification_interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "inner_ring_transport_supported":
        return (
            "The retained family can be excited from the defect/interface region under matched work. "
            "That points to a near-defect boundary assembly mechanism rather than a pure far-boundary-only effect."
        )
    if label == "annulus_transport_supported":
        return (
            "A direct annulus source reproduces the retained family under matched work. "
            "The next control should narrow which annulus radius, sector symmetry, and phase pattern matters."
        )
    if label == "boundary_geometry_sensitive":
        return (
            "The retained family appears sensitive to boundary-source geometry. "
            "Compare one-side, two-side, and rotating boundary variants before changing frequency coverage."
        )
    if label == "boundary_reference_only":
        return (
            "The full four-side boundary reference remains special under this control pass. "
            "The annulus/near-defect probes did not reproduce the reference family strongly enough."
        )
    return "The source-geometry evidence is mixed; inspect per-variant mode diagnostics before expanding the sweep."
