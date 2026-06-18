"""Tiny 3D dt/sponge confirmations for the clean cubic-phase source family."""

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
    _base_3d_config,
    _calibrate_amplitude,
    _run_variant,
    _summary_fields as _prototype_summary_fields,
    _write_csv as _write_prototype_csv,
)
from .prototype_3d_audit import Prototype3DFailureAuditOptions, run_3d_failure_audit
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
class CubicConfirmationControlOptions:
    """Options for the tiny 3D cubic dt/sponge confirmation."""

    output_root: str = "runs"
    grid_size: int = 31
    sample_every: int = 2
    radial_bins: int = 24
    near_shell_width_dx: float = 4.0
    base_sponge_strength_multiplier: float = 2.0
    weak_sponge_relative_multiplier: float = 0.75
    stronger_sponge_relative_multiplier: float = 1.5
    half_dt_multiplier: float = 0.5
    amplitude_reduction_multiplier: float = 0.75
    min_sign_flip_retention: float = 0.45
    min_cubic_retention: float = 0.45
    max_sign_flip_outer_ratio: float = 2.0
    max_cubic_outer_ratio: float = 4.0
    max_near_radius_range: float = 4.5
    max_radius_shift: float = 4.5
    max_arrival_shift: float = 3.0
    min_near_peak_ratio: float = 0.20
    max_near_peak_ratio: float = 8.0
    min_repeat_near_peak_fraction: float = 0.95


def run_3d_cubic_confirmation_control(
    base_config: SimulationConfig,
    *,
    options: CubicConfirmationControlOptions | None = None,
) -> dict[str, Any]:
    """Run tiny confirmation variants around original and sign-flipped cubic phases."""

    options = options or CubicConfirmationControlOptions()
    control_id = datetime.now().strftime("cubic_confirmation_3d_%Y%m%d_%H%M%S")
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
    reference_total_work = 0.0

    for idx, config in enumerate(variants):
        should_match_work = not config.name.endswith("_amplitude_reduced")
        if idx == 0:
            summary = _run_variant(config, root, prototype_options)
            reference_area = max(float(summary.get("effective_source_area") or 0.0), EPSILON)
            reference_total_work = float(summary["positive_work_before_cutoff"])
            reference_work_per_area = reference_total_work / reference_area
        else:
            if should_match_work:
                if config.drive_location == "boundary":
                    target_work = reference_work_per_area * max(_effective_source_area(config), EPSILON)
                else:
                    target_work = reference_total_work
                _calibrate_amplitude(config, target_work)
            summary = _run_variant(config, root, prototype_options)
        _add_control_fields(summary, config, options)
        summary["classification_label"] = None
        rows.append(summary)

    prototype_summary_csv = root / "prototype_3d_summary.csv"
    _write_prototype_csv(prototype_summary_csv, rows, _prototype_summary_fields())
    save_json(
        root / "prototype_3d_summary.json",
        {
            "prototype_id": control_id,
            "classification": {
                "label": "cubic_confirmation_control",
                "reason": "Focused dt/sponge confirmation around original and sign-flipped cubic boundary phases.",
            },
            "variants": rows,
            "summary_csv": str(prototype_summary_csv),
            "report_path": str(root / "cubic_confirmation_control_report.md"),
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
    classification = classify_cubic_confirmation_control(control_rows, options)
    for row in control_rows:
        row["cubic_confirmation_classification"] = classification["label"]

    summary_csv = root / "cubic_confirmation_control_summary.csv"
    report_path = root / "cubic_confirmation_control_report.md"
    _write_csv(summary_csv, control_rows, _summary_fields())
    _write_report(report_path, control_id, control_rows, classification, options, audit)
    save_json(
        root / "cubic_confirmation_control_summary.json",
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


def classify_cubic_confirmation_control(
    rows: list[dict[str, Any]],
    options: CubicConfirmationControlOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the clean cubic-phase family survives dt/sponge checks."""

    options = options or CubicConfirmationControlOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No cubic-confirmation rows were available.", "checks": {}}
    by_variant = {row["variant"]: row for row in rows}
    sign_names = {
        "reference": "cubic_phase_sign_flip_reference",
        "repeat": "cubic_phase_sign_flip_repeat",
        "half_dt": "cubic_phase_sign_flip_half_dt",
        "stronger_sponge": "cubic_phase_sign_flip_stronger_sponge",
        "weak_sponge": "cubic_phase_sign_flip_weak_sponge",
        "amplitude_reduced": "cubic_phase_sign_flip_amplitude_reduced",
    }
    cubic_names = {
        "reference": "six_face_cubic_reference",
        "repeat": "six_face_cubic_repeat",
        "half_dt": "six_face_cubic_half_dt",
        "stronger_sponge": "six_face_cubic_stronger_sponge",
        "weak_sponge": "six_face_cubic_weak_sponge",
    }
    direct_names = ("direct_core_control", "direct_shell_control")

    sign_checks = _family_checks(by_variant, sign_names, "sign_flip", options)
    cubic_checks = _family_checks(by_variant, cubic_names, "cubic", options)
    direct_checks = {name: _row_checks(by_variant.get(name), None, "direct", options) for name in direct_names if name in by_variant}
    direct_transient = all(check.get("transient", False) for check in direct_checks.values())
    hard_dt_warnings = [row["variant"] for row in rows if _has_hard_dt_warning(row)]
    checks = {
        "sign_flip": sign_checks,
        "six_face_cubic": cubic_checks,
        "direct_controls": direct_checks,
        "hard_dt_warnings": hard_dt_warnings,
    }

    sign_core_pass = _family_core_pass(sign_checks)
    cubic_core_pass = _family_core_pass(cubic_checks)
    sign_sponge_pass = sign_checks.get("stronger_sponge", {}).get("clean", False)
    cubic_sponge_pass = cubic_checks.get("stronger_sponge", {}).get("clean", False)
    sign_half_dt_pass = sign_checks.get("half_dt", {}).get("clean", False)
    cubic_half_dt_pass = cubic_checks.get("half_dt", {}).get("clean", False)

    if hard_dt_warnings:
        return {
            "label": "unstable_due_to_dt",
            "reason": f"At least one variant exceeded the hard 3D dt stability estimate: {', '.join(hard_dt_warnings)}.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not direct_transient:
        return {
            "label": "direct_local_forcing_competitive",
            "reason": "A direct core/shell reference did not remain transient, confounding the boundary-only confirmation.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not sign_half_dt_pass or not cubic_half_dt_pass:
        return {
            "label": "dt_sensitive",
            "reason": "At least one cubic-phase family failed the half-dt clean-retention check.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if not sign_sponge_pass or not cubic_sponge_pass:
        return {
            "label": "sponge_sensitive",
            "reason": "At least one cubic-phase family failed the stronger-sponge clean-retention check.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if sign_core_pass and cubic_core_pass:
        amplitude = sign_checks.get("amplitude_reduced", {})
        if amplitude and not amplitude.get("clean", False):
            return {
                "label": "cubic_phase_dt_sponge_confirmed_drive_strength_sensitive",
                "reason": (
                    "Original and sign-flipped cubic phases survived repeat, half-dt, and stronger-sponge checks, "
                    "but the amplitude-reduced sign-flip probe did not retain the same clean near-shell tail."
                ),
                "best_variant": _best_variant(rows),
                "checks": checks,
            }
        return {
            "label": "cubic_phase_dt_sponge_confirmed",
            "reason": "Original and sign-flipped cubic phases survived repeat, half-dt, and stronger-sponge checks while direct local controls stayed transient.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    if sign_core_pass:
        return {
            "label": "sign_flip_confirmed_original_sensitive",
            "reason": "The sign-flipped cubic phase survived dt/sponge confirmation, but the original cubic family did not pass every confirmation check.",
            "best_variant": _best_variant(rows),
            "checks": checks,
        }
    return {
        "label": "inconclusive",
        "reason": "The cubic dt/sponge confirmation produced mixed metrics without a clean pass.",
        "best_variant": _best_variant(rows),
        "checks": checks,
    }


def _variant_plan(
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: CubicConfirmationControlOptions,
) -> list[Prototype3DConfig]:
    variants: list[Prototype3DConfig] = []
    for family, sign in (("six_face_cubic", 1.0), ("cubic_phase_sign_flip", -1.0)):
        variants.append(_base_boundary_config(f"{family}_reference", base, prototype_options, options, sign))
        variants.append(_base_boundary_config(f"{family}_repeat", base, prototype_options, options, sign))
        half_dt = _base_boundary_config(f"{family}_half_dt", base, prototype_options, options, sign)
        half_dt.dt *= options.half_dt_multiplier
        half_dt.steps = int(round(half_dt.steps / options.half_dt_multiplier))
        variants.append(half_dt)
        stronger = _base_boundary_config(f"{family}_stronger_sponge", base, prototype_options, options, sign)
        stronger.sponge_strength *= options.stronger_sponge_relative_multiplier
        variants.append(stronger)
        weak = _base_boundary_config(f"{family}_weak_sponge", base, prototype_options, options, sign)
        weak.sponge_strength *= options.weak_sponge_relative_multiplier
        variants.append(weak)
    amplitude = _base_boundary_config(
        "cubic_phase_sign_flip_amplitude_reduced",
        base,
        prototype_options,
        options,
        -1.0,
    )
    amplitude.drive_amplitude *= options.amplitude_reduction_multiplier
    variants.append(amplitude)
    variants.append(_base_direct_config("direct_core_control", base, prototype_options, options, "core"))
    variants.append(_base_direct_config("direct_shell_control", base, prototype_options, options, "shell"))
    return variants


def _base_boundary_config(
    name: str,
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: CubicConfirmationControlOptions,
    cubic_sign: float,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, prototype_options, "boundary", "cubic")
    _apply_cleaned_geometry(config, options)
    config.boundary_faces = ALL_FACES
    config.boundary_cubic_phase_sign = cubic_sign
    return config


def _base_direct_config(
    name: str,
    base: SimulationConfig,
    prototype_options: Prototype3DOptions,
    options: CubicConfirmationControlOptions,
    drive_location: str,
) -> Prototype3DConfig:
    config = _base_3d_config(name, base, prototype_options, drive_location, "uniform")
    _apply_cleaned_geometry(config, options)
    return config


def _apply_cleaned_geometry(config: Prototype3DConfig, options: CubicConfirmationControlOptions) -> None:
    source_distance = config.sponge_width
    config.sponge_strength *= options.base_sponge_strength_multiplier
    config.boundary_source_inner_distance = source_distance
    config.boundary_source_width = config.dx


def _add_control_fields(
    summary: dict[str, Any],
    config: Prototype3DConfig,
    options: CubicConfirmationControlOptions,
) -> None:
    summary["sponge_width"] = config.sponge_width
    summary["sponge_strength"] = config.sponge_strength
    summary["sponge_strength_multiplier"] = config.sponge_strength / max(_base_sponge_strength(config, options), EPSILON)
    summary["sponge_strength_multiplier_vs_original"] = config.sponge_strength / max(_original_sponge_strength(config, options), EPSILON)
    summary["sponge_width_multiplier"] = 1.0
    summary["cubic_confirmation_family"] = _family(config.name)
    summary["cubic_confirmation_role"] = _role(config.name)
    stability = _stability_summary(config)
    summary.update(stability)


def _original_sponge_strength(config: Prototype3DConfig, options: CubicConfirmationControlOptions) -> float:
    return config.sponge_strength / max(
        options.base_sponge_strength_multiplier * _relative_sponge_multiplier(config.name, options),
        EPSILON,
    )


def _base_sponge_strength(config: Prototype3DConfig, options: CubicConfirmationControlOptions) -> float:
    return _original_sponge_strength(config, options) * options.base_sponge_strength_multiplier


def _relative_sponge_multiplier(name: str, options: CubicConfirmationControlOptions) -> float:
    if name.endswith("_stronger_sponge"):
        return options.stronger_sponge_relative_multiplier
    if name.endswith("_weak_sponge"):
        return options.weak_sponge_relative_multiplier
    return 1.0


def _stability_summary(config: Prototype3DConfig) -> dict[str, Any]:
    max_stiffness = float(config.base_stiffness) * max(1.0, float(config.defect_stiffness_multiplier))
    max_coupling = float(config.coupling_strength) * max(1.0, float(config.defect_coupling_multiplier))
    omega_sq = max_stiffness + 12.0 * max_coupling / (config.dx * config.dx)
    omega = math.sqrt(max(omega_sq, EPSILON))
    recommended = 0.5 / omega
    hard = 1.8 / omega
    warnings = []
    if config.dt > hard:
        warnings.append("dt exceeds the hard 3D stability estimate.")
    elif config.dt > recommended:
        warnings.append("dt is above the conservative 3D accuracy recommendation.")
    return {
        "recommended_dt_max": recommended,
        "hard_stability_dt_max": hard,
        "dt_to_recommended_ratio": config.dt / recommended if recommended > 0.0 else 0.0,
        "dt_to_hard_limit_ratio": config.dt / hard if hard > 0.0 else 0.0,
        "stability_warnings": " | ".join(warnings) or "none",
    }


def _family(variant: str) -> str:
    if variant.startswith("six_face_cubic"):
        return "six_face_cubic"
    if variant.startswith("cubic_phase_sign_flip"):
        return "cubic_phase_sign_flip"
    if variant.startswith("direct_"):
        return "direct_control"
    return "unknown"


def _role(variant: str) -> str:
    if variant.startswith("direct_"):
        return "direct_control"
    for suffix, role in (
        ("_reference", "reference"),
        ("_repeat", "repeat"),
        ("_half_dt", "half_dt"),
        ("_stronger_sponge", "stronger_sponge"),
        ("_weak_sponge", "weak_sponge"),
        ("_amplitude_reduced", "amplitude_reduced"),
    ):
        if variant.endswith(suffix):
            return role
    return "unknown"


def _family_checks(
    by_variant: dict[str, dict[str, Any]],
    names: dict[str, str],
    family: str,
    options: CubicConfirmationControlOptions,
) -> dict[str, dict[str, Any]]:
    reference = by_variant.get(names["reference"])
    return {
        role: _row_checks(by_variant.get(name), reference, family, options)
        for role, name in names.items()
        if name in by_variant
    }


def _family_core_pass(checks: dict[str, dict[str, Any]]) -> bool:
    required = ("reference", "repeat", "half_dt", "stronger_sponge")
    return all(checks.get(role, {}).get("clean", False) for role in required) and checks.get("repeat", {}).get("reproducible", False)


def _row_checks(
    row: dict[str, Any] | None,
    reference: dict[str, Any] | None,
    family: str,
    options: CubicConfirmationControlOptions,
) -> dict[str, Any]:
    if row is None:
        return {}
    retention = _float_or(row.get("near_shell_tail_retention"), 0.0)
    outer_ratio = _float_or(row.get("outer_to_near_tail_energy_ratio"), 999.0)
    radius_range = _float_or(row.get("late_tail_near_shell_peak_radius_range"), 999.0)
    arrival = row.get("first_meaningful_near_shell_arrival_time")
    global_outer = bool(row.get("global_peak_in_outer_window"))
    min_retention = options.min_sign_flip_retention if family == "sign_flip" else options.min_cubic_retention
    max_outer = options.max_sign_flip_outer_ratio if family == "sign_flip" else options.max_cubic_outer_ratio
    near_peak_ratio = _ratio(row.get("near_shell_peak_fraction_of_work"), reference.get("near_shell_peak_fraction_of_work") if reference else None)
    radius_shift = _shift(row.get("late_tail_near_shell_peak_radius_median"), reference.get("late_tail_near_shell_peak_radius_median") if reference else None)
    arrival_shift = _shift(arrival, reference.get("first_meaningful_near_shell_arrival_time") if reference else None)
    near_peak_same_order = (
        reference is None
        or options.min_near_peak_ratio <= near_peak_ratio <= options.max_near_peak_ratio
    )
    stable_radius = radius_range <= options.max_near_radius_range and (
        radius_shift is None or radius_shift <= options.max_radius_shift
    )
    stable_arrival = arrival is not None and (
        arrival_shift is None or arrival_shift <= options.max_arrival_shift
    )
    clean = (
        retention >= min_retention
        and outer_ratio <= max_outer
        and not global_outer
        and near_peak_same_order
        and stable_radius
        and stable_arrival
        and not _has_hard_dt_warning(row)
    )
    reproducible = clean and (
        reference is None
        or near_peak_ratio >= options.min_repeat_near_peak_fraction
        or row.get("cubic_confirmation_role") != "repeat"
    )
    return {
        "variant": row.get("variant"),
        "clean": clean,
        "reproducible": reproducible,
        "transient": arrival is not None and retention < 0.05,
        "retention": retention,
        "outer_ratio": outer_ratio,
        "global_outer": global_outer,
        "near_peak_ratio_to_reference": near_peak_ratio,
        "near_peak_same_order": near_peak_same_order,
        "radius_range": radius_range,
        "radius_shift": radius_shift,
        "arrival_shift": arrival_shift,
        "stable_radius": stable_radius,
        "stable_arrival": stable_arrival,
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
    options: CubicConfirmationControlOptions,
    audit: dict[str, Any],
) -> None:
    lines = [
        f"# 3D Cubic Confirmation Control: {control_id}",
        "",
        "## Purpose",
        "",
        (
            "Tiny 31^3 dt/sponge confirmation for the question: does the clean cubic-phase near-shell "
            "family survive stricter integration and small sponge changes before any larger grid?"
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
        "| Variant | Family | Role | dt | Sponge x | Work/Area | Near Peak/Work | Near Retention | Near Radius Median | Near Radius Range | Outer/Near Tail | Global Outer? | Arrival | dt Warning |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['variant']} | "
            f"{row.get('cubic_confirmation_family')} | "
            f"{row.get('cubic_confirmation_role')} | "
            f"{_format(row.get('dt'))} | "
            f"{_format(row.get('sponge_strength_multiplier'))} | "
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
            "- Source location: original inner sponge edge.",
            f"- Baseline sponge strength: `{options.base_sponge_strength_multiplier}` times the original 3D sponge strength.",
            "- Boundary confirmation variants are matched by injected work per physical source area, except the explicit amplitude-reduced probe.",
            "- Direct core/shell controls are matched by total injected work to the original cubic reference.",
            "",
            "## Files",
            "",
            "- `cubic_confirmation_control_summary.csv`",
            "- `cubic_confirmation_control_summary.json`",
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
    if label == "cubic_phase_dt_sponge_confirmed":
        return (
            "The original and sign-flipped cubic boundary phases survived deterministic repeat, half-dt, and "
            "stronger-sponge confirmation while direct local controls stayed transient."
        )
    if label == "cubic_phase_dt_sponge_confirmed_drive_strength_sensitive":
        return (
            "The cubic-phase family survived the main numerical and sponge checks, but the amplitude-reduced sign-flip "
            "probe did not stay clean. Treat drive strength as a threshold variable before increasing grid size."
        )
    if label == "sign_flip_confirmed_original_sensitive":
        return (
            "The sign-flipped cubic phase is the stronger 3D reference candidate; the original cubic phase did not pass "
            "all confirmation checks."
        )
    if label == "dt_sensitive":
        return "Half-dt did not preserve the clean near-shell family, so do not increase grid size yet."
    if label == "sponge_sensitive":
        return "Stronger sponge did not preserve the clean near-shell family, so the current 3D candidate remains sponge-sensitive."
    if label == "direct_local_forcing_competitive":
        return "A direct core/shell reference did not remain transient, so the boundary-only interpretation is confounded."
    if label == "unstable_due_to_dt":
        return "A hard dt stability warning appeared. Rerun with smaller dt before interpreting the 3D family."
    return "The confirmation produced mixed metrics. Keep the next step small and do not increase 3D grid size."


def _next_step(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "cubic_phase_dt_sponge_confirmed":
        return "Keep 31^3 and consider one narrow amplitude/phase threshold probe before any larger grid."
    if label == "cubic_phase_dt_sponge_confirmed_drive_strength_sensitive":
        return "Keep 31^3 and run a tiny drive-strength threshold check around the sign-flipped cubic phase."
    if label == "sign_flip_confirmed_original_sensitive":
        return "Promote sign-flipped cubic as the primary 3D reference and run one narrow drive-strength check at 31^3."
    return "Stay at 31^3 and resolve the dt/sponge confound before any larger grid."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "cubic_confirmation_classification",
        "cubic_confirmation_family",
        "cubic_confirmation_role",
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
        "sponge_strength_multiplier",
        "sponge_strength_multiplier_vs_original",
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
        "recommended_dt_max",
        "hard_stability_dt_max",
        "dt_to_recommended_ratio",
        "dt_to_hard_limit_ratio",
        "stability_warnings",
        "path",
    ]
