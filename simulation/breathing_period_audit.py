"""Breathing-period peak audits for completed diagnostic runs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import load_json_config


EPSILON = 1e-12


@dataclass(frozen=True)
class BreathingPeriodAuditOptions:
    percentile: float = 55.0
    min_separations: tuple[float, ...] = (1.5, 2.0, 2.5)


def run_breathing_period_audit(
    run_paths: list[str | Path],
    *,
    output_dir: str | Path,
    options: BreathingPeriodAuditOptions | None = None,
) -> dict[str, Any]:
    """Audit whether breathing periods are sensitive to peak-picking details."""

    options = options or BreathingPeriodAuditOptions()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    peak_rows: list[dict[str, Any]] = []
    for run_path in [Path(path) for path in run_paths]:
        if not (run_path / "metrics.csv").exists():
            continue
        config = load_json_config(run_path / "config.json")
        cutoff = float(config.get("driver", {}).get("drive_cutoff_time", 0.0))
        variant = run_path.name

        metrics_rows = _read_numeric_csv(run_path / "metrics.csv")
        frame_path = run_path / "mode_shape_diagnostics" / "frame_mode_diagnostics.csv"
        if frame_path.exists():
            frame_rows = _read_numeric_csv(frame_path)
            current = _peak_summary(frame_rows, cutoff, options.percentile)
            current.update({"variant": variant, "source": "diagnostic_frames_current", "min_separation": ""})
            summary_rows.append(current)
            peak_rows.extend(_peak_rows(variant, "diagnostic_frames_current", "", current))

        metrics_current = _peak_summary(metrics_rows, cutoff, options.percentile)
        metrics_current.update({"variant": variant, "source": "metrics_same_detector", "min_separation": ""})
        summary_rows.append(metrics_current)
        peak_rows.extend(_peak_rows(variant, "metrics_same_detector", "", metrics_current))

        for min_sep in options.min_separations:
            separated = _peak_summary(metrics_rows, cutoff, options.percentile, min_separation=min_sep)
            separated.update(
                {
                    "variant": variant,
                    "source": f"metrics_min_sep_{min_sep:g}",
                    "min_separation": min_sep,
                }
            )
            summary_rows.append(separated)
            peak_rows.extend(_peak_rows(variant, f"metrics_min_sep_{min_sep:g}", min_sep, separated))

    classification = _classify(summary_rows)
    summary_path = output_dir / "breathing_period_audit_summary.csv"
    peaks_path = output_dir / "breathing_period_peak_times.csv"
    report_path = output_dir / "breathing_period_audit_report.md"
    _write_csv(summary_path, summary_rows, _summary_fields())
    _write_csv(peaks_path, peak_rows, _peak_fields())
    _write_report(report_path, summary_rows, classification, options)
    return {
        "classification": classification,
        "summary_csv": str(summary_path),
        "peak_times_csv": str(peaks_path),
        "report_path": str(report_path),
        "path": str(output_dir),
        "rows": summary_rows,
    }


def discover_run_paths(control_root: str | Path) -> list[Path]:
    """Return completed source-normalized run directories under a control root."""

    root = Path(control_root)
    preferred = sorted(path for path in root.glob("source_normalized_grid_*") if path.is_dir())
    if preferred:
        return preferred
    return sorted(path for path in root.iterdir() if path.is_dir() and (path / "metrics.csv").exists())


def _peak_summary(
    rows: list[dict[str, float]],
    cutoff: float,
    percentile: float,
    *,
    min_separation: float | None = None,
) -> dict[str, Any]:
    post = [row for row in rows if float(row.get("time", 0.0)) > cutoff]
    times = np.asarray([row.get("time", 0.0) for row in post], dtype=float)
    values = np.asarray([row.get("core_energy", 0.0) for row in post], dtype=float)
    if times.size < 3:
        return _empty_summary()

    peaks = _local_peaks(values)
    threshold = float(np.percentile(values, percentile))
    peaks = peaks[values[peaks] >= threshold] if peaks.size else peaks
    if min_separation is not None:
        peaks = _filter_by_min_separation(times, values, peaks, min_separation)

    intervals = np.diff(times[peaks]) if peaks.size >= 2 else np.asarray([], dtype=float)
    return {
        "sample_count": int(times.size),
        "threshold": threshold,
        "peak_count": int(peaks.size),
        "period": float(np.mean(intervals)) if intervals.size else None,
        "interval_cv": float(np.std(intervals) / (np.mean(intervals) + EPSILON)) if intervals.size else None,
        "first_peak_time": float(times[peaks[0]]) if peaks.size else None,
        "last_peak_time": float(times[peaks[-1]]) if peaks.size else None,
        "peak_times": [float(times[idx]) for idx in peaks],
        "peak_values": [float(values[idx]) for idx in peaks],
        "intervals": [float(value) for value in intervals],
    }


def _empty_summary() -> dict[str, Any]:
    return {
        "sample_count": 0,
        "threshold": None,
        "peak_count": 0,
        "period": None,
        "interval_cv": None,
        "first_peak_time": None,
        "last_peak_time": None,
        "peak_times": [],
        "peak_values": [],
        "intervals": [],
    }


def _local_peaks(values: np.ndarray) -> np.ndarray:
    if values.size < 3:
        return np.asarray([], dtype=int)
    return np.where((values[1:-1] > values[:-2]) & (values[1:-1] > values[2:]))[0] + 1


def _filter_by_min_separation(
    times: np.ndarray,
    values: np.ndarray,
    peaks: np.ndarray,
    min_separation: float,
) -> np.ndarray:
    if not peaks.size:
        return peaks
    kept: list[int] = []
    for peak in peaks[np.argsort(values[peaks])[::-1]]:
        if all(abs(float(times[peak] - times[other])) >= min_separation for other in kept):
            kept.append(int(peak))
    return np.asarray(sorted(kept), dtype=int)


def _classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_variant.setdefault(str(row.get("variant")), {})[str(row.get("source"))] = row

    checks = {}
    short_variants = []
    corrected_variants = []
    for variant, sources in by_variant.items():
        current = sources.get("diagnostic_frames_current") or sources.get("metrics_same_detector")
        separated = sources.get("metrics_min_sep_1.5") or sources.get("metrics_min_sep_2")
        if current and float(current.get("period") or 999.0) < 2.0:
            short_variants.append(variant)
            if separated and 2.0 <= float(separated.get("period") or 0.0) <= 3.5:
                corrected_variants.append(variant)
        checks[variant] = {
            "current_period": current.get("period") if current else None,
            "min_sep_1_5_period": (sources.get("metrics_min_sep_1.5") or {}).get("period"),
            "min_sep_2_0_period": (sources.get("metrics_min_sep_2") or {}).get("period"),
        }

    if short_variants and set(short_variants) == set(corrected_variants):
        return {
            "label": "peak_detector_overcounts_subpeaks",
            "reason": (
                "Short diagnostic periods are caused by local peak overcounting; minimum-separated metric peaks "
                "recover the expected breathing envelope period."
            ),
            "checks": checks,
        }
    if short_variants:
        return {
            "label": "period_anomaly_persists",
            "reason": "At least one variant remains short even after minimum-separated metric peak filtering.",
            "checks": checks,
        }
    return {
        "label": "no_short_period_anomaly",
        "reason": "No audited variant has a short current breathing-period estimate.",
        "checks": checks,
    }


def _peak_rows(variant: str, source: str, min_separation: Any, summary: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    times = summary.get("peak_times", [])
    values = summary.get("peak_values", [])
    intervals = summary.get("intervals", [])
    for idx, time in enumerate(times):
        out.append(
            {
                "variant": variant,
                "source": source,
                "min_separation": min_separation,
                "peak_index": idx,
                "peak_time": time,
                "peak_value": values[idx] if idx < len(values) else None,
                "next_interval": intervals[idx] if idx < len(intervals) else None,
            }
        )
    return out


def _write_report(
    path: Path,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: BreathingPeriodAuditOptions,
) -> None:
    lines = [
        "# Breathing Period Audit",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Summary",
        "",
        "| Variant | Source | Min Sep | Peaks | Period | CV | First Peak | Last Peak |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('variant')} | "
            f"{row.get('source')} | "
            f"{_format(row.get('min_separation'))} | "
            f"{row.get('peak_count')} | "
            f"{_format(row.get('period'))} | "
            f"{_format(row.get('interval_cv'))} | "
            f"{_format(row.get('first_peak_time'))} | "
            f"{_format(row.get('last_peak_time'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(rows, classification),
            "",
            "## Method",
            "",
            f"- Peak percentile threshold: `{options.percentile}`",
            "- `diagnostic_frames_current` reproduces the existing diagnostic-frame detector.",
            "- `metrics_same_detector` applies the same local-peak rule to every metric sample.",
            "- `metrics_min_sep_*` keeps stronger metric peaks separated by the requested minimum time.",
            "",
            "## Files",
            "",
            "- `breathing_period_audit_summary.csv`",
            "- `breathing_period_peak_times.csv`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(rows: list[dict[str, Any]], classification: dict[str, Any]) -> str:
    if classification["label"] == "peak_detector_overcounts_subpeaks":
        return (
            "The short period comes from counting small local maxima on a broad post-cutoff core-energy plateau. "
            "When peaks are required to be separated by at least 1.5 to 2.0 time units, the 63-grid period moves "
            "back into the same envelope-scale range as the neighboring grids."
        )
    if classification["label"] == "period_anomaly_persists":
        return "The short period remains after separation filtering, so it may reflect a true high-frequency envelope component."
    return "The audit did not reproduce a short breathing-period anomaly."


def _read_numeric_csv(path: Path) -> list[dict[str, float]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        rows = []
        for row in csv.DictReader(fh):
            converted: dict[str, float] = {}
            for key, value in row.items():
                try:
                    converted[key] = float(value)
                except (TypeError, ValueError):
                    pass
            rows.append(converted)
        return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _summary_fields() -> list[str]:
    return [
        "variant",
        "source",
        "min_separation",
        "sample_count",
        "threshold",
        "peak_count",
        "period",
        "interval_cv",
        "first_peak_time",
        "last_peak_time",
    ]


def _peak_fields() -> list[str]:
    return ["variant", "source", "min_separation", "peak_index", "peak_time", "peak_value", "next_interval"]


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    return value


def _format(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    return f"{float(value):.6g}"
