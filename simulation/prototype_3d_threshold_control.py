"""Tiny 41^3 amplitude and phase tolerance check for the 3D sign-flip source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import math

from .config import SimulationConfig, save_json
from .prototype_3d import (
    EPSILON,
    Prototype3DConfig,
    Prototype3DOptions,
    _audit_work,
    _base_3d_config,
    _calibrate_amplitude,
    _run_variant,
    _summary_fields as _prototype_summary_fields,
    _write_csv as _write_prototype_csv,
)
from .prototype_3d_audit import Prototype3DFailureAuditOptions, run_3d_failure_audit
from .prototype_3d_cubic_confirmation import _stability_summary
from .prototype_3d_grid_confirmation import _base_dx
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
class ThresholdControl3DOptions:
    """Options for the tiny 41^3 sign-flip amplitude/phase tolerance check."""

    output_root: str = "runs"
    grid_size: int = 41
    reference_source_grid_size: int = 31
    sample_every: int = 2
    radial_bins: int = 24
    near_shell_width_dx: float = 4.0
    sponge_strength_multiplier: float = 3.0
    amplitude_multipliers: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5)
    phase_offsets: tuple[float, ...] = (-math.pi / 8.0, -math.pi / 16.0, 0.0, math.pi / 16.0, math.pi / 8.0)
    include_direct_core: bool = True
    include_direct_shell: bool = True
    min_retention: float = 0.45
    max_outer_ratio: float = 2.0
    max_near_radius_range: float = 4.5
    max_radius_shift: float = 4.5
    max_arrival_shift: float = 4.0
    min_near_peak_ratio: float = 0.20
    max_near_peak_ratio: float = 8.0


def run_3d_threshold_control(
    base_config: SimulationConfig,
    *,
    options: ThresholdControl3DOptions | None = None,
) -> dict[str, Any]:
    """Run a focused 41^3 amplitude/phase check around sign-flipped cubic forcing."""

    options = options or ThresholdControl3DOptions()
    control_id = datetime.now().strftime("threshold_control_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    variants = _variant_plan(base_config, options)
    reference_config = variants[0]
    source_width = _base_dx(base_config, options.reference_source_grid_size)
    target_work_per_area = _calibration_work_per_area(base_config, options, source_width)
    reference_drive_amplitude = _calibrated_reference_amplitude(
        base_config,
        options,
        source_width,
        target_work_per_area,
    )
    rows: list[dict[str, Any]] = []
    reference_total_work = 0.0

    for idx, config in enumerate(variants):
        role = _role(config.name)
        if config.drive_location == "boundary":
            if role in {"reference", "amplitude"}:
                config.drive_amplitude = reference_drive_amplitude * float(_amplitude_multiplier(config.name) or 1.0)
            elif role == "phase":
                config.drive_amplitude = reference_drive_amplitude
                target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
                _calibrate_amplitude(config, target_work)
        if idx == 0:
            summary = _run_variant(config, root, _prototype_options(config, options))
            reference_total_work = float(summary["positive_work_before_cutoff"])
        else:
            if role == "direct_control":
                _calibrate_amplitude(config, reference_total_work)
            summary = _run_variant(config, root, _prototype_options(config, options))
        _add_control_fields(summary, config, reference_config, options, target_work_per_area)
        summary["classification_label"] = None
        rows.append(summary)

    prototype_summary_csv = root / "prototype_3d_summary.csv"
    _write_prototype_csv(prototype_summary_csv, rows, _prototype_summary_fields())
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": control_id,
            "classification": {
                "label": "threshold_control_3d",
                "reason": "Tiny 41^3 amplitude and phase tolerance check around the sign-flipped cubic source.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "threshold_control_3d_report.md"),
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
    classification = classify_threshold_control(control_rows, options)
    for row in control_rows:
        row["threshold_control_classification"] = classification["label"]

    summary_csv = root / "threshold_control_3d_summary.csv"
    report_path = root / "threshold_control_3d_report.md"
    _write_csv(summary_csv, control_rows, _summary_fields())
    _write_report(report_path, control_id, control_rows, classification, options, audit)
    save_json(
        root / "threshold_control_3d_summary.json",
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


def classify_threshold_control(
    rows: list[dict[str, Any]],
    options: ThresholdControl3DOptions | None = None,
) -> dict[str, Any]:
    """Classify amplitude and phase tolerance for the 41^3 sign-flipped source."""

    options = options or ThresholdControl3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No 3D threshold-control rows were available.", "checks": {}}

    by_variant = {row["variant"]: row for row in rows}
    reference = by_variant.get("sign_flip_amp_1_0_reference")
    amplitude_checks = {
        _float_label(row["threshold_multiplier"]): _row_checks(row, reference, options)
        for row in rows
        if row.get("threshold_axis") == "amplitude"
    }
    phase_checks = {
        _phase_key(float(row.get("boundary_phase_offset") or 0.0)): _row_checks(row, reference, options)
        for row in rows
        if row.get("threshold_axis") == "phase"
    }
    direct_checks = {
        row["variant"]: _row_checks(row, reference, options)
        for row in rows
        if row.get("threshold_axis") == "direct"
    }
    hard_dt_warnings = [row["variant"] for row in rows if _has_hard_dt_warning(row)]

    checks = {
        "reference": _row_checks(reference, reference, options),
        "amplitude": amplitude_checks,
        "phase": phase_checks,
        "direct_controls": direct_checks,
        "hard_dt_warnings": hard_dt_warnings,
    }
    direct_transient = all(check.get("transient", False) for check in direct_checks.values())
    lower_clean = all(amplitude_checks.get(label, {}).get("clean", False) for label in ("0.5", "0.75"))
    mid_low_clean = amplitude_checks.get("0.75", {}).get("clean", False)
    upper_clean = all(amplitude_checks.get(label, {}).get("clean", False) for label in ("1.25", "1.5") if label in amplitude_checks)
    upper_dirty = any(amplitude_checks.get(label, {}).get("dirty", False) for label in ("1.25", "1.5") if label in amplitude_checks)
    small_phase_clean = all(phase_checks.get(label, {}).get("clean", False) for label in ("-pi/16", "+pi/16"))
    broad_phase_clean = small_phase_clean and all(phase_checks.get(label, {}).get("clean", False) for label in ("-pi/8", "+pi/8"))

    if hard_dt_warnings:
        return {
            "label": "unstable_due_to_dt",
            "reason": f"At least one 41^3 threshold-control variant exceeded the hard dt estimate: {', '.join(hard_dt_warnings)}.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not checks["reference"].get("clean", False):
        return {
            "label": "reference_not_reproduced",
            "reason": "The 1.0x sign-flipped cubic 41^3 reference did not reproduce the clean near-shell tail.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if direct_checks and not direct_transient:
        return {
            "label": "direct_control_competitive",
            "reason": "A direct core/shell control did not remain transient enough to isolate boundary transport.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if upper_dirty:
        return {
            "label": "high_drive_outer_contaminated",
            "reason": "A higher-amplitude sign-flip variant became outer-contaminated or global-outer flagged.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not small_phase_clean:
        return {
            "label": "phase_tuned",
            "reason": "At least one +/-pi/16 phase-offset variant failed the clean near-shell check.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if lower_clean and upper_clean and broad_phase_clean:
        return {
            "label": "amplitude_phase_tolerant",
            "reason": "The sign-flipped cubic 41^3 family stayed clean across 0.5x-1.5x amplitude and +/-pi/8 phase offsets while direct controls stayed transient.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if mid_low_clean and upper_clean and small_phase_clean:
        return {
            "label": "threshold_below_half_amplitude",
            "reason": "The family stayed clean at 0.75x and small phase offsets, but 0.5x did not pass.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not mid_low_clean:
        return {
            "label": "amplitude_threshold_sensitive",
            "reason": "The family did not stay clean at 0.75x amplitude, suggesting a drive-strength threshold before broader 3D work.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "inconclusive",
        "reason": "The 41^3 amplitude/phase tolerance check produced mixed metrics.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(base: SimulationConfig, options: ThresholdControl3DOptions) -> list[Prototype3DConfig]:
    reference_width = _base_dx(base, options.reference_source_grid_size)
    variants: list[Prototype3DConfig] = []
    for multiplier in options.amplitude_multipliers:
        name = "sign_flip_amp_1_0_reference" if abs(multiplier - 1.0) < 1e-9 else f"sign_flip_amp_{_name_number(multiplier)}"
        config = _boundary_config(
            name,
            base,
            options,
            source_width=reference_width,
            phase_offset=0.0,
        )
        config.drive_amplitude *= multiplier
        variants.append(config)
    if "sign_flip_amp_1_0_reference" not in {variant.name for variant in variants}:
        variants.insert(
            0,
            _boundary_config(
                "sign_flip_amp_1_0_reference",
                base,
                options,
                source_width=reference_width,
                phase_offset=0.0,
            ),
        )
    else:
        variants.sort(key=lambda item: 0 if item.name == "sign_flip_amp_1_0_reference" else 1)
    for offset in options.phase_offsets:
        if abs(offset) < 1e-12:
            continue
        variants.append(
            _boundary_config(
                f"sign_flip_phase_{_phase_name(offset)}",
                base,
                options,
                source_width=reference_width,
                phase_offset=offset,
            )
        )
    if options.include_direct_core:
        variants.append(_direct_config("direct_core_41_control", base, options, "core", source_width=reference_width))
    if options.include_direct_shell:
        variants.append(_direct_config("direct_shell_41_control", base, options, "shell", source_width=reference_width))
    return variants


def _prototype_options(config: Prototype3DConfig, options: ThresholdControl3DOptions) -> Prototype3DOptions:
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
    options: ThresholdControl3DOptions,
    *,
    source_width: float,
    phase_offset: float,
    grid_size: int | None = None,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, Prototype3DOptions(grid_size=grid_size or options.grid_size), "boundary", "cubic")
    _apply_common_geometry(config, options, source_width)
    config.boundary_faces = ALL_FACES
    config.boundary_cubic_phase_sign = -1.0
    config.boundary_phase_offset = phase_offset
    return config


def _direct_config(
    name: str,
    base: SimulationConfig,
    options: ThresholdControl3DOptions,
    drive_location: str,
    *,
    source_width: float,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, Prototype3DOptions(grid_size=options.grid_size), drive_location, "uniform")
    _apply_common_geometry(config, options, source_width)
    return config


def _calibration_work_per_area(
    base: SimulationConfig,
    options: ThresholdControl3DOptions,
    source_width: float,
) -> float:
    config = _boundary_config(
        "calibration_sign_flip_reference",
        base,
        options,
        source_width=source_width,
        phase_offset=0.0,
        grid_size=options.reference_source_grid_size,
    )
    area = max(_effective_source_area(config), EPSILON)
    return _audit_work(config) / area


def _calibrated_reference_amplitude(
    base: SimulationConfig,
    options: ThresholdControl3DOptions,
    source_width: float,
    target_work_per_area: float,
) -> float:
    config = _boundary_config(
        "calibration_sign_flip_41",
        base,
        options,
        source_width=source_width,
        phase_offset=0.0,
        grid_size=options.grid_size,
    )
    target_work = target_work_per_area * max(_effective_source_area(config), EPSILON)
    _calibrate_amplitude(config, target_work)
    return config.drive_amplitude


def _apply_common_geometry(config: Prototype3DConfig, options: ThresholdControl3DOptions, source_width: float) -> None:
    config.sponge_strength *= options.sponge_strength_multiplier
    config.boundary_source_inner_distance = config.sponge_width
    config.boundary_source_width = source_width


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    reference_config: Prototype3DConfig,
    options: ThresholdControl3DOptions,
    target_work_per_area: float,
) -> None:
    summary["threshold_axis"] = _axis(config.name)
    summary["threshold_role"] = _role(config.name)
    summary["threshold_multiplier"] = _amplitude_multiplier(config.name)
    summary["phase_offset_label"] = _phase_key(config.boundary_phase_offset)
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    original_sponge_strength = reference_config.sponge_strength / max(options.sponge_strength_multiplier, EPSILON)
    summary["sponge_strength_multiplier_vs_original"] = config.sponge_strength / max(original_sponge_strength, EPSILON)
    summary["sponge_width_multiplier"] = config.sponge_width / max(reference_config.sponge_width, EPSILON)
    summary["source_width_physical_reference"] = reference_config.boundary_source_width
    summary["target_reference_work_per_source_area"] = target_work_per_area
    summary["calibration_source_grid_size"] = options.reference_source_grid_size
    summary.update(_stability_summary(config))


def _axis(variant: str) -> str:
    if variant.startswith("sign_flip_amp_"):
        return "amplitude"
    if variant.startswith("sign_flip_phase_"):
        return "phase"
    if variant.startswith("direct_"):
        return "direct"
    return "unknown"


def _role(variant: str) -> str:
    if variant == "sign_flip_amp_1_0_reference":
        return "reference"
    if variant.startswith("sign_flip_amp_"):
        return "amplitude"
    if variant.startswith("sign_flip_phase_"):
        return "phase"
    if variant.startswith("direct_"):
        return "direct_control"
    return "unknown"


def _amplitude_multiplier(variant: str) -> float | None:
    if not variant.startswith("sign_flip_amp_"):
        return None
    if variant == "sign_flip_amp_1_0_reference":
        return 1.0
    return float(variant.replace("sign_flip_amp_", "").replace("_", "."))


def _row_checks(
    row: dict[str, Any] | None,
    reference: dict[str, Any] | None,
    options: ThresholdControl3DOptions,
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
    options: ThresholdControl3DOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Threshold Control: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny 41^3 amplitude and phase tolerance check around the sign-flipped cubic stronger-sponge "
            "boundary reference. This is not a broad 3D sweep."
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
        "| Variant | Axis | Role | Amp x | Phase | Work/Area | Near Peak/Work | Near Retention | Near Radius Median | Near Radius Range | Outer/Near Tail | Global Outer? | Arrival | dt Warning |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('threshold_axis')} | "
            f"{row.get('threshold_role')} | "
            f"{_format(row.get('threshold_multiplier'))} | "
            f"{row.get('phase_offset_label')} | "
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
            f"- Grid size: `{options.grid_size}^3`",
            "- Physical domain size, defect radius, sponge width, source inner-edge distance, drive frequency, and cutoff time are fixed.",
            f"- Sponge strength is `{options.sponge_strength_multiplier}` times the original 3D sponge strength for every variant.",
            f"- The 1.0x reference is calibrated to the work per physical source area of the `{options.reference_source_grid_size}^3` sign-flip stronger-sponge reference.",
            "- Amplitude variants keep their explicit drive-amplitude multiplier so injected work can vary naturally.",
            "- Phase variants are matched by injected work per physical source area to the 1.0x reference.",
            "- Direct core/shell controls are matched by total injected work to the 1.0x reference.",
            "- The source layer uses the same physical width as the 31^3 reference.",
            "",
            "## Files",
            "",
            "- `threshold_control_3d_summary.csv`",
            "- `threshold_control_3d_summary.json`",
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
    if label == "amplitude_phase_tolerant":
        return "The clean 41^3 sign-flip near-shell tail survived the tested amplitude and phase window, consistent with a robust transport family under this tiny check."
    if label == "threshold_below_half_amplitude":
        return "The clean family survived 0.75x amplitude and small phase offsets, but 0.5x did not pass. Treat the threshold as below the current reference but not absent."
    if label == "amplitude_threshold_sensitive":
        return "The clean family did not survive the lower-amplitude check, suggesting drive-strength threshold sensitivity."
    if label == "phase_tuned":
        return "A small phase offset disrupted the clean near-shell tail, so the 41^3 source remains phase-tuned."
    if label == "high_drive_outer_contaminated":
        return "A higher-amplitude variant pushed energy toward outer contamination, so stronger drive is not automatically better."
    if label == "direct_control_competitive":
        return "A direct local control retained too much near-shell signal, weakening the boundary-transport isolation."
    if label == "reference_not_reproduced":
        return "The 41^3 reference did not reproduce, so this threshold pass cannot be interpreted."
    if label == "unstable_due_to_dt":
        return "A hard dt warning appeared. Re-run with smaller dt before interpreting the threshold behavior."
    return "The threshold control produced mixed metrics. Keep the next step targeted."


def _next_step(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "amplitude_phase_tolerant":
        return "Do not broad sweep yet; next consider one targeted 41^3 direct-control repeat or a single stricter numerical check around the tolerant window."
    if label in {"threshold_below_half_amplitude", "amplitude_threshold_sensitive"}:
        return "Stay at 41^3 and refine only the lower-amplitude threshold bracket before any broader 3D work."
    if label == "phase_tuned":
        return "Stay at 41^3 and narrow the phase-offset bracket before any broader 3D work."
    return "Resolve this focused threshold-control result before any broad 3D sweep."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "threshold_control_classification",
        "threshold_axis",
        "threshold_role",
        "threshold_multiplier",
        "phase_offset_label",
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
        "calibration_source_grid_size",
        "target_reference_work_per_source_area",
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


def _name_number(value: float) -> str:
    return f"{value:g}".replace(".", "_").replace("-", "neg_")


def _float_label(value: Any) -> str:
    if value in (None, ""):
        return ""
    return f"{float(value):g}"


def _phase_name(value: float) -> str:
    sign = "pos" if value > 0.0 else "neg"
    denominator = round(math.pi / abs(value))
    return f"{sign}_pi_{denominator}"


def _phase_key(value: float) -> str:
    if abs(value) < 1e-12:
        return "0"
    sign = "+" if value > 0.0 else "-"
    denominator = round(math.pi / abs(value))
    return f"{sign}pi/{denominator}"
