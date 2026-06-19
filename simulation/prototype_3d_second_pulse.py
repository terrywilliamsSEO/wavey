"""Tiny active second-pulse control for 3D cubic refocusing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import math

import numpy as np

from .config import SimulationConfig, save_json
from .prototype_3d import EPSILON, Prototype3DConfig, _calibrate_amplitude
from .prototype_3d_grid_confirmation import _base_dx
from .prototype_3d_interference_diagnostics import _boundary_config as _interference_boundary_config, _threshold_like_options
from .prototype_3d_packet_lifecycle import (
    PacketLifecycle3DOptions,
    _event_fields,
    _plot_flux,
    _plot_lifecycle,
    _plot_radius_width,
    _run_lifecycle_variant,
    _timeseries_fields,
)
from .prototype_3d_source_sponge import _effective_source_area, _format, _write_csv
from .prototype_3d_threshold_control import _calibrated_reference_amplitude, _calibration_work_per_area


@dataclass(frozen=True)
class SecondPulse3DOptions(PacketLifecycle3DOptions):
    """Options for a tiny active second-pulse timing control."""

    reference_variant: str = "sign_flip_cutoff_minus_0p1"
    reference_events_csv: str | None = "runs/cutoff_phase_map_3d_20260619_104211/cutoff_phase_map_events.csv"
    reference_cutoff_time: float = 17.9
    reference_release_phase_cycles: float = 0.468
    second_pulse_duration: float = 2.0
    second_pulse_amplitude_scale: float = 1.0
    second_pulse_amplitude_scales: tuple[float, ...] | None = None
    second_pulse_durations: tuple[float, ...] | None = None
    second_pulse_roles: tuple[str, ...] = (
        "first_refocus",
        "preload_first_refocus",
        "second_refocus",
        "opposite_polarity",
        "phase_matched",
        "phase_offset_control",
    )
    second_pulse_micro_map: bool = False
    micro_map_targets: tuple[str, ...] = ("first_refocus",)
    launch_time_offsets: tuple[float, ...] = (-0.8, -0.4, 0.0, 0.4, 0.8)
    second_pulse_phase_modes: tuple[str, ...] = ("matched", "opposite", "plus_pi_4", "minus_pi_4")
    boundary_to_shell_travel_time: float | None = None
    preload_time: float = 1.0
    phase_offset_control: float = 0.5 * float(np.pi)
    max_outer_shell_target: float = 1.0
    min_retention_gain: float = 0.0
    min_refocus_gain: int = 1


def run_3d_second_pulse_control(
    base_config: SimulationConfig,
    *,
    options: SecondPulse3DOptions | None = None,
) -> dict[str, Any]:
    """Run a tiny active second-pulse control from the best release phase."""

    options = options or SecondPulse3DOptions()
    control_id = datetime.now().strftime("second_pulse_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    source_width = _base_dx(base_config, options.reference_source_grid_size)
    lifecycle_options = _lifecycle_options(options)
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
    target_work = target_work_per_area * max(_effective_source_area(_reference_config(base_config, options, source_width)), EPSILON)
    calibration_config = _reference_config(base_config, options, source_width)
    calibration_config.drive_amplitude = reference_drive_amplitude
    _calibrate_amplitude(calibration_config, target_work)

    event_times = _reference_event_times(options)
    variants = [_reference_config(base_config, options, source_width)] if options.second_pulse_micro_map else _variant_plan(base_config, options, source_width, event_times)
    rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for config in variants:
        config.drive_amplitude = calibration_config.drive_amplitude
        config.steps = max(config.steps, int(round(options.physical_duration / max(config.dt, EPSILON))))
        result = _run_lifecycle_variant(config, root, lifecycle_options)
        summary = result["summary"]
        _add_control_fields(summary, config, options, target_work_per_area)
        rows.append(summary)
        timeseries_rows.extend(result["timeseries"])
        event_rows.extend(result["events"])

    timing_audit = _timing_phase_audit(timeseries_rows, event_rows, rows, options)
    if options.second_pulse_micro_map:
        for config in _micro_map_variant_plan(base_config, options, source_width, timing_audit, event_times):
            config.drive_amplitude = calibration_config.drive_amplitude
            config.steps = max(config.steps, int(round(options.physical_duration / max(config.dt, EPSILON))))
            result = _run_lifecycle_variant(config, root, lifecycle_options)
            summary = result["summary"]
            _add_control_fields(summary, config, options, target_work_per_area)
            rows.append(summary)
            timeseries_rows.extend(result["timeseries"])
            event_rows.extend(result["events"])

    classification = classify_second_pulse_control(rows, options)
    reference = _reference_row(rows)
    extension = _extension_row(rows)
    for row in rows:
        row.update(_comparison_fields(row, reference, extension))
        row["second_pulse_classification"] = classification["label"]

    ranked_rows = _ranked_rows(rows)
    summary_csv = root / "second_pulse_summary.csv"
    ranked_csv = root / "second_pulse_ranked_summary.csv"
    timeseries_csv = root / "second_pulse_timeseries.csv"
    events_csv = root / "second_pulse_events.csv"
    timing_audit_csv = root / "second_pulse_timing_audit.csv"
    report_path = root / "second_pulse_report.md"
    _write_csv(summary_csv, rows, _summary_fields())
    _write_csv(ranked_csv, ranked_rows, _ranked_fields())
    _write_csv(timeseries_csv, timeseries_rows, _timeseries_fields())
    _write_csv(events_csv, event_rows, _event_fields())
    _write_csv(timing_audit_csv, timing_audit, _timing_audit_fields())
    _plot_lifecycle(root / "second_pulse_shell_energy_plot.png", timeseries_rows, event_rows)
    _plot_radius_width(root / "second_pulse_radius_width_plot.png", timeseries_rows)
    _plot_flux(root / "second_pulse_flux_balance_plot.png", timeseries_rows)
    _write_report(report_path, control_id, rows, classification, options, event_times, timing_audit)
    save_json(
        root / "second_pulse_3d_summary.json",
        {
            "control_id": control_id,
            "classification": classification,
            "event_times": event_times,
            "variants": rows,
            "summary_csv": str(summary_csv),
            "ranked_csv": str(ranked_csv),
            "timeseries_csv": str(timeseries_csv),
            "events_csv": str(events_csv),
            "timing_audit_csv": str(timing_audit_csv),
            "report_path": str(report_path),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "event_times": event_times,
        "variants": rows,
        "summary_csv": str(summary_csv),
        "ranked_csv": str(ranked_csv),
        "timeseries_csv": str(timeseries_csv),
        "events_csv": str(events_csv),
        "timing_audit_csv": str(timing_audit_csv),
        "report_path": str(report_path),
        "path": str(root),
    }


def classify_second_pulse_control(
    rows: list[dict[str, Any]],
    options: SecondPulse3DOptions | None = None,
) -> dict[str, Any]:
    """Classify whether a timed second pulse improves refocusing efficiently."""

    options = options or SecondPulse3DOptions()
    if not rows:
        return {"label": "inconclusive", "reason": "No second-pulse rows were available.", "checks": {}}
    reference = _reference_row(rows)
    extension = _extension_row(rows)
    checks = {row["variant"]: _row_checks(row, reference, extension, options) for row in rows}
    active_rows = [row for row in rows if row.get("second_pulse_role") not in {"reference", "passive_extension"}]
    clean_active = [row for row in active_rows if _is_clean(row, options)]
    successful = [row for row in clean_active if _beats_reference(row, reference, options)]
    best = _best_variant(clean_active or active_rows or rows)
    best_row = next((row for row in rows if row.get("variant") == best), None)
    extension_gain = _return_gain_per_added_work(extension, reference)
    best_gain = _return_gain_per_added_work(best_row, reference)

    if successful and best_gain is not None and (extension_gain is None or best_gain > extension_gain):
        return {
            "label": "active_second_pulse_promising",
            "reason": "A timed second pulse beat the no-pulse reference on refocus count, retention, cleanliness, decay, and work-normalized return gain.",
            "best_variant": best,
            "checks": checks,
        }
    if successful:
        return {
            "label": "second_pulse_gain_not_better_than_extension",
            "reason": "At least one active second pulse beat the reference, but the passive extension comparator matched or exceeded its return gain per added work.",
            "best_variant": best,
            "checks": checks,
        }
    if clean_active:
        return {
            "label": "second_pulse_no_improvement",
            "reason": "Second-pulse variants stayed mostly clean but did not beat the no-pulse release-phase reference under the strict criteria.",
            "best_variant": best,
            "checks": checks,
        }
    return {
        "label": "second_pulse_contaminated_or_inconclusive",
        "reason": "Second-pulse variants were contaminated, exited, or did not provide enough clean comparable rows.",
        "best_variant": best,
        "checks": checks,
    }


def _variant_plan(
    base: SimulationConfig,
    options: SecondPulse3DOptions,
    source_width: float,
    event_times: dict[str, float],
) -> list[Prototype3DConfig]:
    first_refocus = float(event_times["first_refocus_time"])
    second_refocus = float(event_times["second_refocus_time"])
    before_first = max(options.reference_cutoff_time + options.second_pulse_duration, first_refocus - options.preload_time)
    phase_match_offset = _phase_offset_to_release(
        base.driver.frequency,
        first_refocus,
        options.reference_release_phase_cycles,
    )
    if options.second_pulse_amplitude_scales or options.second_pulse_durations:
        scales = options.second_pulse_amplitude_scales or (options.second_pulse_amplitude_scale,)
        durations = options.second_pulse_durations or (options.second_pulse_duration,)
        variants = [_reference_config(base, options, source_width)]
        for duration in durations:
            variants.append(_passive_extension_config(base, options, source_width, duration=duration))
            for role in options.second_pulse_roles:
                for scale in scales:
                    prefix, center, phase_offset = _pulse_spec(
                        role,
                        first_refocus=first_refocus,
                        second_refocus=second_refocus,
                        before_first=before_first,
                        phase_match_offset=phase_match_offset,
                        phase_offset_control=options.phase_offset_control,
                    )
                    variants.append(
                        _pulse_config(
                            _map_variant_name(prefix, scale, duration),
                            base,
                            options,
                            source_width,
                            center,
                            phase_offset,
                            role,
                            amplitude_scale=scale,
                            duration=duration,
                        )
                    )
        return variants
    variants = [
        _reference_config(base, options, source_width),
        _pulse_config("second_at_first_refocus", base, options, source_width, first_refocus, 0.0, "first_refocus"),
        _pulse_config("second_before_first_refocus", base, options, source_width, before_first, 0.0, "preload_first_refocus"),
        _pulse_config("second_at_second_refocus", base, options, source_width, second_refocus, 0.0, "second_refocus"),
        _pulse_config("opposite_polarity_second", base, options, source_width, first_refocus, math.pi, "opposite_polarity"),
        _pulse_config("phase_matched_second", base, options, source_width, first_refocus, phase_match_offset, "phase_matched"),
        _pulse_config("phase_offset_second", base, options, source_width, first_refocus, options.phase_offset_control, "phase_offset_control"),
        _passive_extension_config(base, options, source_width),
    ]
    return variants


def _micro_map_variant_plan(
    base: SimulationConfig,
    options: SecondPulse3DOptions,
    source_width: float,
    timing_audit: list[dict[str, Any]],
    event_times: dict[str, float],
) -> list[Prototype3DConfig]:
    """Build a tiny travel-time-adjusted launch micro-map."""

    scales = options.second_pulse_amplitude_scales or (0.1, 0.2)
    target_times = _micro_map_target_times(timing_audit, event_times)
    variants: list[Prototype3DConfig] = []
    for target in options.micro_map_targets:
        target_time = target_times.get(target)
        if target_time is None:
            continue
        travel_time = _estimated_travel_time(timing_audit, options)
        ideal_launch_time = max(options.reference_cutoff_time + 0.5 * options.second_pulse_duration, target_time - travel_time)
        for offset in options.launch_time_offsets:
            center = ideal_launch_time + offset
            for phase_mode in options.second_pulse_phase_modes:
                phase_offset = _phase_offset_for_mode(base.driver.frequency, center, options.reference_release_phase_cycles, phase_mode)
                for scale in scales:
                    config = _pulse_config(
                        _micro_map_variant_name(target, offset, phase_mode, scale),
                        base,
                        options,
                        source_width,
                        center,
                        phase_offset,
                        f"micro_{target}_{phase_mode}",
                        amplitude_scale=scale,
                    )
                    setattr(config, "_second_pulse_target", target)
                    setattr(config, "_second_pulse_launch_offset", offset)
                    setattr(config, "_second_pulse_phase_mode", phase_mode)
                    setattr(config, "_target_shell_peak_time", target_time)
                    setattr(config, "_estimated_travel_time", travel_time)
                    setattr(config, "_ideal_launch_time", ideal_launch_time)
                    variants.append(config)
    return variants


def _micro_map_target_times(timing_audit: list[dict[str, Any]], event_times: dict[str, float]) -> dict[str, float | None]:
    peak_rows = [row for row in timing_audit if row.get("event") == "shell_peak"]
    by_rank = {int(row.get("peak_rank") or 0): float(row["peak_time"]) for row in peak_rows if row.get("peak_time") is not None}
    return {
        "first_peak": by_rank.get(1, event_times.get("first_peak_time")),
        "first_refocus": by_rank.get(2, event_times.get("first_refocus_time")),
        "second_refocus": by_rank.get(3, event_times.get("second_refocus_time")),
    }


def _estimated_travel_time(timing_audit: list[dict[str, Any]], options: SecondPulse3DOptions) -> float:
    if options.boundary_to_shell_travel_time is not None:
        return max(0.0, float(options.boundary_to_shell_travel_time))
    for row in timing_audit:
        value = row.get("estimated_boundary_to_shell_travel_time")
        if value is not None:
            return max(0.0, float(value))
    return max(0.0, float(options.reference_cutoff_time) * 0.5)


def _phase_offset_for_mode(frequency: float, center_time: float, release_phase_cycles: float, phase_mode: str) -> float:
    matched = _phase_offset_to_release(frequency, center_time, release_phase_cycles)
    if phase_mode == "matched":
        return matched
    if phase_mode == "opposite":
        return matched + math.pi
    if phase_mode == "plus_pi_4":
        return matched + 0.25 * math.pi
    if phase_mode == "minus_pi_4":
        return matched - 0.25 * math.pi
    raise ValueError(f"Unsupported second-pulse phase mode: {phase_mode}")


def _micro_map_variant_name(target: str, offset: float, phase_mode: str, scale: float) -> str:
    return f"micro_{target}_launch_{_safe_float(offset)}_{phase_mode}_scale_{_safe_float(scale)}"


def _reference_config(base: SimulationConfig, options: SecondPulse3DOptions, source_width: float) -> Prototype3DConfig:
    config = _base_boundary_config("no_second_pulse", base, options, source_width)
    setattr(config, "_second_pulse_role", "reference")
    return config


def _pulse_config(
    name: str,
    base: SimulationConfig,
    options: SecondPulse3DOptions,
    source_width: float,
    center: float,
    phase_offset: float,
    role: str,
    amplitude_scale: float | None = None,
    duration: float | None = None,
) -> Prototype3DConfig:
    config = _base_boundary_config(name, base, options, source_width)
    config.second_pulse_center_time = center
    config.second_pulse_duration = options.second_pulse_duration if duration is None else duration
    config.second_pulse_amplitude_scale = options.second_pulse_amplitude_scale if amplitude_scale is None else amplitude_scale
    config.second_pulse_phase_offset = phase_offset
    setattr(config, "_second_pulse_role", role)
    return config


def _passive_extension_config(
    base: SimulationConfig,
    options: SecondPulse3DOptions,
    source_width: float,
    *,
    duration: float | None = None,
) -> Prototype3DConfig:
    extension_duration = options.second_pulse_duration if duration is None else duration
    name = "extended_first_pulse_same_duration" if duration is None else f"extended_first_pulse_duration_{_safe_float(extension_duration)}"
    config = _base_boundary_config(name, base, options, source_width)
    config.drive_cutoff_time = options.reference_cutoff_time + extension_duration
    setattr(config, "_second_pulse_role", "passive_extension")
    return config


def _base_boundary_config(
    name: str,
    base: SimulationConfig,
    options: SecondPulse3DOptions,
    source_width: float,
) -> Prototype3DConfig:
    config = _interference_boundary_config(
        name,
        base,
        options,
        source_width,
        "cubic",
        cubic_sign=-1.0,
        phase_offset=0.0,
    )
    config.drive_cutoff_time = options.reference_cutoff_time
    config.drive_frequency = float(base.driver.frequency)
    return config


def _add_control_fields(
    row: dict[str, Any],
    config: Prototype3DConfig,
    options: SecondPulse3DOptions,
    target_work_per_area: float,
) -> None:
    start, end = _second_pulse_bounds_from_config(config)
    center = config.second_pulse_center_time
    row["second_pulse_role"] = getattr(config, "_second_pulse_role", "variant")
    row["target_reference_work_per_source_area"] = target_work_per_area
    row["drive_frequency"] = config.drive_frequency
    row["reference_release_phase_cycles"] = options.reference_release_phase_cycles
    row["drive_cutoff_time"] = config.drive_cutoff_time
    row["release_phase_cycles"] = _phase_cycles(config.drive_frequency, config.drive_cutoff_time, config.boundary_phase_offset)
    row["second_pulse_center_time"] = center
    row["second_pulse_start_time"] = start
    row["second_pulse_end_time"] = end
    row["second_pulse_duration"] = config.second_pulse_duration
    row["second_pulse_amplitude_scale"] = config.second_pulse_amplitude_scale
    row["second_pulse_phase_offset"] = config.second_pulse_phase_offset
    row["second_pulse_phase_offset_cycles"] = config.second_pulse_phase_offset / (2.0 * math.pi)
    row["second_pulse_target"] = getattr(config, "_second_pulse_target", None)
    row["second_pulse_launch_offset"] = getattr(config, "_second_pulse_launch_offset", None)
    row["second_pulse_phase_mode"] = getattr(config, "_second_pulse_phase_mode", None)
    row["target_shell_peak_time"] = getattr(config, "_target_shell_peak_time", None)
    row["estimated_boundary_to_shell_travel_time"] = getattr(config, "_estimated_travel_time", None)
    row["ideal_launch_time"] = getattr(config, "_ideal_launch_time", None)
    row["second_pulse_phase_at_center_cycles"] = (
        _phase_cycles(config.drive_frequency, center, config.boundary_phase_offset + config.second_pulse_phase_offset)
        if center is not None
        else None
    )


def _timing_phase_audit(
    timeseries_rows: list[dict[str, Any]],
    event_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    options: SecondPulse3DOptions,
) -> list[dict[str, Any]]:
    reference = _reference_row(summary_rows) or {}
    variant = str(reference.get("variant") or "no_second_pulse")
    series = sorted((row for row in timeseries_rows if row.get("variant") == variant), key=lambda row: float(row.get("time") or 0.0))
    peak_events = sorted(
        (row for row in event_rows if row.get("variant") == variant and row.get("event") == "shell_peak"),
        key=lambda row: float(row.get("time") or 0.0),
    )
    if not series or not peak_events:
        return []
    times = np.asarray([float(row["time"]) for row in series], dtype=float)
    shell = np.asarray([float(row.get("shell_window_energy") or 0.0) for row in series], dtype=float)
    flux = np.asarray([float(row.get("shell_radial_flux") or 0.0) for row in series], dtype=float)
    centroid = np.asarray([float(row.get("packet_centroid_radius") or 0.0) for row in series], dtype=float)
    width = np.asarray([float(row.get("packet_radial_width") or 0.0) for row in series], dtype=float)
    phase = _analytic_phase_cycles(shell)
    travel_time = _estimated_travel_time_from_reference(reference, options)
    rows: list[dict[str, Any]] = []
    for event in peak_events:
        peak_time = float(event["time"])
        launch_time = peak_time - travel_time
        local_flux = _interp(times, flux, peak_time)
        local_velocity = _local_slope(times, centroid, peak_time)
        rows.append(
            {
                "variant": variant,
                "event": "shell_peak",
                "peak_rank": event.get("peak_rank"),
                "peak_time": peak_time,
                "shell_energy": event.get("energy"),
                "radial_flux": local_flux,
                "radial_flux_direction": _flux_direction(local_flux),
                "packet_radial_velocity": local_velocity,
                "packet_motion": _packet_motion(local_velocity),
                "packet_centroid_radius": _interp(times, centroid, peak_time),
                "packet_radial_width": _interp(times, width, peak_time),
                "local_shell_phase_cycles": _interp(times, phase, peak_time),
                "estimated_boundary_to_shell_travel_time": travel_time,
                "ideal_launch_time": launch_time,
                "source_phase_at_launch_cycles": _phase_cycles(float(reference.get("drive_frequency") or 0.0), launch_time, 0.0),
                "source_phase_at_peak_cycles": _phase_cycles(float(reference.get("drive_frequency") or 0.0), peak_time, 0.0),
            }
        )
    return rows


def _estimated_travel_time_from_reference(reference: dict[str, Any], options: SecondPulse3DOptions) -> float:
    if options.boundary_to_shell_travel_time is not None:
        return max(0.0, float(options.boundary_to_shell_travel_time))
    arrival = reference.get("first_shell_arrival_time")
    if arrival is not None:
        return max(0.0, float(arrival))
    return max(0.0, float(options.reference_cutoff_time) * 0.5)


def _analytic_phase_cycles(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return np.asarray([], dtype=float)
    centered = values - float(np.mean(values))
    if float(np.max(np.abs(centered))) <= EPSILON:
        return np.zeros_like(centered, dtype=float)
    spectrum = np.fft.fft(centered)
    multiplier = np.zeros(values.size, dtype=float)
    multiplier[0] = 1.0
    if values.size % 2 == 0:
        multiplier[values.size // 2] = 1.0
        multiplier[1 : values.size // 2] = 2.0
    else:
        multiplier[1 : (values.size + 1) // 2] = 2.0
    analytic = np.fft.ifft(spectrum * multiplier)
    return np.mod(np.angle(analytic) / (2.0 * math.pi), 1.0)


def _interp(times: np.ndarray, values: np.ndarray, time: float) -> float | None:
    if times.size == 0 or values.size == 0:
        return None
    return float(np.interp(time, times, values))


def _local_slope(times: np.ndarray, values: np.ndarray, time: float) -> float | None:
    if times.size < 3 or values.size < 3:
        return None
    idx = int(np.searchsorted(times, time))
    start = max(0, idx - 2)
    end = min(times.size, idx + 3)
    if end - start < 3:
        return None
    x = times[start:end]
    y = values[start:end]
    if float(np.ptp(x)) <= EPSILON:
        return None
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)


def _flux_direction(value: float | None) -> str:
    if value is None or abs(value) <= EPSILON:
        return "flat"
    return "inward" if value < 0.0 else "outward"


def _packet_motion(value: float | None) -> str:
    if value is None or abs(value) <= EPSILON:
        return "flat"
    return "inbound" if value < 0.0 else "outbound"


def _comparison_fields(
    row: dict[str, Any],
    reference: dict[str, Any] | None,
    extension: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "refocus_count_delta": _delta(row.get("refocus_peak_count"), (reference or {}).get("refocus_peak_count")),
        "major_peak_count_delta": _delta(row.get("major_shell_peak_count"), (reference or {}).get("major_shell_peak_count")),
        "retention_delta": _delta(row.get("tail_shell_retention"), (reference or {}).get("tail_shell_retention")),
        "decay_rate_delta": _delta(row.get("post_cutoff_shell_decay_rate"), (reference or {}).get("post_cutoff_shell_decay_rate")),
        "outer_shell_delta": _delta(row.get("tail_outer_to_shell_mean"), (reference or {}).get("tail_outer_to_shell_mean")),
        "refocus_efficiency_delta": _delta(row.get("refocus_efficiency_total_work"), (reference or {}).get("refocus_efficiency_total_work")),
        "added_work_vs_reference": _delta(row.get("total_positive_work"), (reference or {}).get("total_positive_work")),
        "return_gain_per_added_work": _return_gain_per_added_work(row, reference),
        "clean_refocus_score": _clean_refocus_score(row, reference),
        "clean_refocus_score_delta": _delta(_clean_refocus_score(row, reference), _clean_refocus_score(reference, reference)),
        "added_work_efficiency": _added_work_efficiency(row, reference),
        "return_gain_per_added_work_vs_extension": _delta(
            _return_gain_per_added_work(row, reference),
            _return_gain_per_added_work(extension, reference),
        ),
    }


def _row_checks(
    row: dict[str, Any],
    reference: dict[str, Any] | None,
    extension: dict[str, Any] | None,
    options: SecondPulse3DOptions,
) -> dict[str, Any]:
    return {
        **_comparison_fields(row, reference, extension),
        "clean": _is_clean(row, options),
        "beats_reference": _beats_reference(row, reference, options),
        "role": row.get("second_pulse_role"),
        "refocus_peak_count": row.get("refocus_peak_count"),
        "tail_shell_retention": row.get("tail_shell_retention"),
        "tail_outer_to_shell_mean": row.get("tail_outer_to_shell_mean"),
        "post_cutoff_shell_decay_rate": row.get("post_cutoff_shell_decay_rate"),
        "refocus_efficiency_total_work": row.get("refocus_efficiency_total_work"),
    }


def _is_clean(row: dict[str, Any] | None, options: SecondPulse3DOptions) -> bool:
    if row is None:
        return False
    return (
        not bool(row.get("shell_exit_detected"))
        and not bool(row.get("global_peak_in_outer_window"))
        and float(row.get("tail_outer_to_shell_mean") or 999.0) <= options.max_outer_shell_target
    )


def _beats_reference(
    row: dict[str, Any] | None,
    reference: dict[str, Any] | None,
    options: SecondPulse3DOptions,
) -> bool:
    if row is None or reference is None or row.get("variant") == reference.get("variant"):
        return False
    return (
        _is_clean(row, options)
        and int(row.get("major_shell_peak_count") or 0) > int(reference.get("major_shell_peak_count") or 0)
        and int(row.get("refocus_peak_count") or 0) >= int(reference.get("refocus_peak_count") or 0) + options.min_refocus_gain
        and float(row.get("tail_shell_retention") or 0.0) > float(reference.get("tail_shell_retention") or 0.0) + options.min_retention_gain
        and float(row.get("post_cutoff_shell_decay_rate") or -999.0) > float(reference.get("post_cutoff_shell_decay_rate") or -999.0)
        and float(row.get("refocus_efficiency_total_work") or 0.0) > float(reference.get("refocus_efficiency_total_work") or 0.0)
        and (_added_work_efficiency(row, reference) or 0.0) > 0.0
    )


def _ranked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reference = _reference_row(rows)
    ranked = []
    for rank, row in enumerate(sorted(rows, key=lambda item: _rank_key(item, reference), reverse=True), start=1):
        ranked.append(
            {
                "rank": rank,
                "outer_shell_below_1": float(row.get("tail_outer_to_shell_mean") or 999.0) < 1.0,
                "clean_refocus_score": _clean_refocus_score(row, reference),
                "clean_refocus_score_delta": _delta(_clean_refocus_score(row, reference), _clean_refocus_score(reference, reference)),
                "added_work_efficiency": _added_work_efficiency(row, reference),
                **row,
            }
        )
    return ranked


def _rank_key(row: dict[str, Any], reference: dict[str, Any] | None) -> tuple[float, ...]:
    decay = float(row.get("post_cutoff_shell_decay_rate") or 0.0)
    ref_major = int((reference or {}).get("major_shell_peak_count") or 0)
    ref_refocus = int((reference or {}).get("refocus_peak_count") or 0)
    ref_retention = float((reference or {}).get("tail_shell_retention") or 0.0)
    ref_decay = float((reference or {}).get("post_cutoff_shell_decay_rate") or -999.0)
    return (
        1.0 if int(row.get("refocus_peak_count") or 0) > ref_refocus else 0.0,
        1.0 if int(row.get("major_shell_peak_count") or 0) > ref_major else 0.0,
        1.0 if float(row.get("tail_outer_to_shell_mean") or 999.0) < 1.0 else 0.0,
        0.0 if bool(row.get("shell_exit_detected")) else 1.0,
        1.0 if decay > ref_decay else 0.0,
        1.0 if float(row.get("tail_shell_retention") or 0.0) > ref_retention else 0.0,
        float(_added_work_efficiency(row, reference) or -999.0),
        float(row.get("refocus_peak_count") or 0.0),
        float(row.get("major_shell_peak_count") or 0.0),
        float(row.get("tail_shell_retention") or 0.0),
        -abs(decay),
        0.0 if bool(row.get("global_peak_in_outer_window")) else 1.0,
    )


def _best_variant(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "n/a"
    return str(_ranked_rows(rows)[0].get("variant", "n/a"))


def _reference_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("variant") == "no_second_pulse"), rows[0] if rows else None)


def _extension_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("second_pulse_role") == "passive_extension"), None)


def _return_gain_per_added_work(row: dict[str, Any] | None, reference: dict[str, Any] | None) -> float | None:
    if row is None or reference is None:
        return None
    added = float(row.get("total_positive_work") or 0.0) - float(reference.get("total_positive_work") or 0.0)
    if added <= EPSILON:
        return None
    tail_gain = float(row.get("tail_shell_energy_mean") or 0.0) - float(reference.get("tail_shell_energy_mean") or 0.0)
    return tail_gain / added


def _clean_refocus_score(row: dict[str, Any] | None, reference: dict[str, Any] | None) -> float | None:
    if row is None:
        return None
    ref_retention = float((reference or {}).get("tail_shell_retention") or 0.0)
    ref_decay = float((reference or {}).get("post_cutoff_shell_decay_rate") or 0.0)
    retention = float(row.get("tail_shell_retention") or 0.0)
    decay = float(row.get("post_cutoff_shell_decay_rate") or 0.0)
    retention_term = retention / (ref_retention + EPSILON) if ref_retention > EPSILON else retention
    decay_term = (decay - ref_decay) / (abs(ref_decay) + EPSILON) if abs(ref_decay) > EPSILON else 0.0
    return (
        float(row.get("refocus_peak_count") or 0.0)
        + 0.5 * float(row.get("major_shell_peak_count") or 0.0)
        + (1.0 if not bool(row.get("shell_exit_detected")) else -1.0)
        + (1.0 if float(row.get("tail_outer_to_shell_mean") or 999.0) < 1.0 else -1.0)
        + (1.0 if not bool(row.get("global_peak_in_outer_window")) else -1.0)
        + retention_term
        + max(-2.0, min(2.0, decay_term))
    )


def _added_work_efficiency(row: dict[str, Any] | None, reference: dict[str, Any] | None) -> float | None:
    if row is None or reference is None:
        return None
    added_work = float(row.get("second_pulse_positive_work") or 0.0)
    if added_work <= EPSILON:
        added_work = float(row.get("total_positive_work") or 0.0) - float(reference.get("total_positive_work") or 0.0)
    if added_work <= EPSILON:
        return None
    score = _clean_refocus_score(row, reference)
    reference_score = _clean_refocus_score(reference, reference)
    if score is None or reference_score is None:
        return None
    return (score - reference_score) / added_work


def _reference_event_times(options: SecondPulse3DOptions) -> dict[str, float]:
    fallback = {"first_peak_time": 20.8, "first_refocus_time": 35.84, "second_refocus_time": 41.12}
    if not options.reference_events_csv:
        return fallback
    path = Path(options.reference_events_csv)
    if not path.exists():
        return fallback
    peaks: dict[int, float] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("variant") != options.reference_variant or row.get("event") != "shell_peak":
                continue
            try:
                rank = int(float(row.get("peak_rank") or 0))
                time = float(row.get("time") or 0.0)
            except ValueError:
                continue
            peaks[rank] = time
    return {
        "first_peak_time": peaks.get(1, fallback["first_peak_time"]),
        "first_refocus_time": peaks.get(2, fallback["first_refocus_time"]),
        "second_refocus_time": peaks.get(3, fallback["second_refocus_time"]),
    }


def _phase_offset_to_release(frequency: float, center_time: float, release_phase_cycles: float) -> float:
    current = (float(frequency) * float(center_time)) % 1.0
    delta_cycles = (float(release_phase_cycles) - current + 0.5) % 1.0 - 0.5
    return 2.0 * math.pi * delta_cycles


def _pulse_spec(
    role: str,
    *,
    first_refocus: float,
    second_refocus: float,
    before_first: float,
    phase_match_offset: float,
    phase_offset_control: float,
) -> tuple[str, float, float]:
    if role == "first_refocus":
        return "second_at_first_refocus", first_refocus, 0.0
    if role == "preload_first_refocus":
        return "second_before_first_refocus", before_first, 0.0
    if role == "second_refocus":
        return "second_at_second_refocus", second_refocus, 0.0
    if role == "opposite_polarity":
        return "opposite_polarity_second", first_refocus, math.pi
    if role == "phase_matched":
        return "phase_matched_second", first_refocus, phase_match_offset
    if role == "phase_offset_control":
        return "phase_offset_second", first_refocus, phase_offset_control
    raise ValueError(f"Unsupported second-pulse role: {role}")


def _map_variant_name(prefix: str, scale: float, duration: float) -> str:
    return f"{prefix}_scale_{_safe_float(scale)}_duration_{_safe_float(duration)}"


def _safe_float(value: float) -> str:
    return str(float(value)).replace("-", "minus_").replace(".", "p")


def _phase_cycles(frequency: float, time: float | None, phase_offset: float = 0.0) -> float | None:
    if time is None:
        return None
    return (float(frequency) * float(time) + float(phase_offset) / (2.0 * math.pi)) % 1.0


def _second_pulse_bounds_from_config(config: Prototype3DConfig) -> tuple[float | None, float | None]:
    if config.second_pulse_center_time is None or config.second_pulse_duration <= EPSILON:
        return None, None
    half = 0.5 * float(config.second_pulse_duration)
    return float(config.second_pulse_center_time) - half, float(config.second_pulse_center_time) + half


def _lifecycle_options(options: SecondPulse3DOptions) -> PacketLifecycle3DOptions:
    return PacketLifecycle3DOptions(
        output_root=options.output_root,
        grid_size=options.grid_size,
        reference_source_grid_size=options.reference_source_grid_size,
        physical_duration=options.physical_duration,
        sample_every=options.sample_every,
        diagnostic_sample_every=options.diagnostic_sample_every,
        radial_bins=options.radial_bins,
        shell_window_radius=options.shell_window_radius,
        shell_window_width=options.shell_window_width,
        near_shell_width_dx=options.near_shell_width_dx,
        sponge_strength_multiplier=options.sponge_strength_multiplier,
        target_work_per_source_area=options.target_work_per_source_area,
        phase_offset=options.phase_offset,
        arrival_threshold_fraction=options.arrival_threshold_fraction,
        exit_threshold_fraction=options.exit_threshold_fraction,
        exit_hold_samples=options.exit_hold_samples,
        peak_threshold_fraction=options.peak_threshold_fraction,
        refocus_threshold_fraction=options.refocus_threshold_fraction,
        min_peak_separation_time=options.min_peak_separation_time,
        min_refocus_count=options.min_refocus_count,
        min_width_growth_fraction=options.min_width_growth_fraction,
        min_decay_rate_magnitude=options.min_decay_rate_magnitude,
    )


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: SecondPulse3DOptions,
    event_times: dict[str, float],
    timing_audit: list[dict[str, Any]],
) -> None:
    lines = [
        f"# 3D Second Pulse Control: {control_id}",
        "",
        "## Purpose",
        "",
        "Tiny active refocusing check asking whether a second cubic pulse can reinforce the return cycle more efficiently than just adding work.",
        "",
        "## Event Timing Source",
        "",
        f"- Reference variant: `{options.reference_variant}`",
        f"- First shell peak: `{_format(event_times.get('first_peak_time'))}`",
        f"- First refocus peak: `{_format(event_times.get('first_refocus_time'))}`",
        f"- Second refocus peak: `{_format(event_times.get('second_refocus_time'))}`",
        "",
        "## No-Pulse Timing / Phase Audit",
        "",
        "| Peak | Time | Flux Dir | Packet Motion | Shell Phase | Travel | Ideal Launch | Source Phase At Launch |",
        "| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in timing_audit:
        lines.append(
            "| "
            f"{row.get('peak_rank')} | "
            f"{_format(row.get('peak_time'))} | "
            f"{row.get('radial_flux_direction')} | "
            f"{row.get('packet_motion')} | "
            f"{_format(row.get('local_shell_phase_cycles'))} | "
            f"{_format(row.get('estimated_boundary_to_shell_travel_time'))} | "
            f"{_format(row.get('ideal_launch_time'))} | "
            f"{_format(row.get('source_phase_at_launch_cycles'))} |"
        )
    lines.extend(
        [
            "",
            "## Classification",
            "",
            f"- Result: `{classification['label']}`",
            f"- Reason: {classification['reason']}",
            f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
            "",
            "## Ranked Results",
            "",
            "Ranking priority: refocus peaks > reference, major peaks > reference, outer/shell below 1.0, no exit, decay better than reference, retention above reference, and added-work efficiency.",
            "",
            "| Rank | Variant | Role | Scale | Duration | Center | Phase At Center | Peaks | Refocus | Exit | Ret | Added Work Eff | Added Work | Outer/Shell | Decay | Global Outer |",
            "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in _ranked_rows(rows):
        exit_label = "false" if not bool(row.get("shell_exit_detected")) else _format(row.get("shell_exit_time"))
        lines.append(
            "| "
            f"{row['rank']} | "
            f"{row['variant']} | "
            f"{row.get('second_pulse_role')} | "
            f"{_format(row.get('second_pulse_amplitude_scale'))} | "
            f"{_format(row.get('second_pulse_duration'))} | "
            f"{_format(row.get('second_pulse_center_time'))} | "
            f"{_format(row.get('second_pulse_phase_at_center_cycles'))} | "
            f"{row.get('major_shell_peak_count')} | "
            f"{row.get('refocus_peak_count')} | "
            f"{exit_label} | "
            f"{_format(row.get('tail_shell_retention'))} | "
            f"{_format(row.get('added_work_efficiency'))} | "
            f"{_format(row.get('added_work_vs_reference'))} | "
            f"{_format(row.get('tail_outer_to_shell_mean'))} | "
            f"{_format(row.get('post_cutoff_shell_decay_rate'))} | "
            f"{row.get('global_peak_in_outer_window')} |"
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
            "- `second_pulse_summary.csv`",
            "- `second_pulse_ranked_summary.csv`",
            "- `second_pulse_timeseries.csv`",
            "- `second_pulse_events.csv`",
            "- `second_pulse_timing_audit.csv`",
            "- `second_pulse_shell_energy_plot.png`",
            "- `second_pulse_radius_width_plot.png`",
            "- `second_pulse_flux_balance_plot.png`",
            "",
            "## Next Step",
            "",
            _next_step(classification),
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "active_second_pulse_promising":
        return "A timed second pulse improved the refocusing sequence even after normalizing for total injected work. This supports active refocusing as the next engineering branch."
    if label == "second_pulse_gain_not_better_than_extension":
        return "A second pulse improved raw refocusing, but not more efficiently than the passive extension comparator. Treat extra work as the likely explanation until timing is refined."
    if label == "second_pulse_no_improvement":
        return "The second pulse stayed interpretable but did not improve on the sharp release-phase reference under the strict metrics."
    return "The second-pulse control is inconclusive or contaminated; inspect outer/shell and event traces before adding mechanisms."


def _next_step(classification: dict[str, Any]) -> str:
    if classification["label"] == "active_second_pulse_promising":
        return "Repeat the best second-pulse timing with one smaller duration or amplitude check before adding rotation, traps, or medium shaping."
    if classification["label"] == "second_pulse_gain_not_better_than_extension":
        return "Refine the passive-extension comparator or reduce second-pulse work before claiming active retention."
    return "Hold the release-phase reference and inspect second-pulse timing/phase traces before expanding controls."


def _summary_fields() -> list[str]:
    return [
        "variant",
        "second_pulse_classification",
        "second_pulse_role",
        "second_pulse_target",
        "second_pulse_launch_offset",
        "second_pulse_phase_mode",
        "target_shell_peak_time",
        "estimated_boundary_to_shell_travel_time",
        "ideal_launch_time",
        "drive_frequency",
        "drive_cutoff_time",
        "release_phase_cycles",
        "reference_release_phase_cycles",
        "second_pulse_center_time",
        "second_pulse_start_time",
        "second_pulse_end_time",
        "second_pulse_duration",
        "second_pulse_amplitude_scale",
        "second_pulse_phase_offset",
        "second_pulse_phase_offset_cycles",
        "second_pulse_phase_at_center_cycles",
        "major_shell_peak_count",
        "refocus_peak_count",
        "shell_exit_detected",
        "shell_exit_time",
        "tail_shell_retention",
        "tail_shell_energy_mean",
        "tail_outer_to_shell_mean",
        "post_cutoff_shell_decay_rate",
        "positive_work_before_cutoff",
        "second_pulse_positive_work",
        "total_positive_work",
        "added_work_vs_reference",
        "refocus_efficiency_total_work",
        "clean_refocus_score",
        "clean_refocus_score_delta",
        "added_work_efficiency",
        "return_gain_per_added_work",
        "return_gain_per_added_work_vs_extension",
        "shell_peak_energy",
        "shell_peak_fraction_of_total_work",
        "refocus_peak_ratio_max",
        "global_peak_in_outer_window",
        "inward_flux_fraction",
        "target_reference_work_per_source_area",
    ]


def _ranked_fields() -> list[str]:
    return ["rank", "outer_shell_below_1", *_summary_fields()]


def _timing_audit_fields() -> list[str]:
    return [
        "variant",
        "event",
        "peak_rank",
        "peak_time",
        "shell_energy",
        "radial_flux",
        "radial_flux_direction",
        "packet_radial_velocity",
        "packet_motion",
        "packet_centroid_radius",
        "packet_radial_width",
        "local_shell_phase_cycles",
        "estimated_boundary_to_shell_travel_time",
        "ideal_launch_time",
        "source_phase_at_launch_cycles",
        "source_phase_at_peak_cycles",
    ]


def _delta(value: Any, reference: Any) -> float | None:
    if value is None or reference is None:
        return None
    return float(value) - float(reference)
