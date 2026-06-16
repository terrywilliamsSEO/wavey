"""Markdown report generation for sweeps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .band_analysis import analyze_frequency_band
from .config import SweepConfig, load_json_config


def write_sweep_report(
    output_root: str | Path,
    sweep_id: str,
    ranked: list[dict[str, Any]],
    sweep_config: SweepConfig,
    plan_path: str | Path,
    summary_path: str | Path,
) -> Path:
    output_root = Path(output_root)
    report_path = output_root / f"{sweep_id}_report.md"
    top_n = min(max(0, sweep_config.report_top_n), len(ranked))

    lines = [
        f"# Sweep Report: {sweep_id}",
        "",
        "## Overview",
        "",
        f"- Sampling mode: `{sweep_config.sampling_mode}`",
        f"- Seed: `{sweep_config.seed}`",
        f"- Runs completed: `{len(ranked)}`",
        f"- Plan: [{Path(plan_path).name}]({Path(plan_path).name})",
        f"- Summary JSON: [{Path(summary_path).name}]({Path(summary_path).name})",
        "",
        "## Top Candidates",
        "",
    ]

    if not ranked:
        lines.append("No runs were generated.")
    else:
        lines.extend(_candidate_table(ranked[:top_n], output_root))
        band = analyze_frequency_band(ranked)
        if band is not None:
            lines.append("")
            lines.extend(_frequency_band_section(band))
        lines.append("")
        lines.append("## Candidate Notes")
        lines.append("")
        for rank, summary in enumerate(ranked[:top_n], start=1):
            lines.extend(_candidate_notes(rank, summary, output_root))

    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def _candidate_table(summaries: list[dict[str, Any]], output_root: Path) -> list[str]:
    lines = [
        "| Rank | Run | Score | Ratio | Retention | Events | Evidence |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for rank, summary in enumerate(summaries, start=1):
        run_dir = Path(summary["path"])
        run_link = _relative_link(output_root, run_dir / "summary.json")
        evidence_link = _relative_link(output_root, run_dir / "best_frame.png")
        labels = ", ".join(summary.get("detected_event_labels", [])) or "none"
        lines.append(
            "| "
            f"{rank} | "
            f"[{summary['run_id']}]({run_link}) | "
            f"{float(summary.get('anomaly_score', 0.0)):.3f} | "
            f"{float(summary.get('best_energy_well_ratio', 0.0)):.6g} | "
            f"{float(summary.get('retention_score', 0.0)):.6g} | "
            f"{_escape_table(labels)} | "
            f"[best frame]({evidence_link}) |"
        )
    return lines


def _frequency_band_section(band: dict[str, Any]) -> list[str]:
    half = band["half_power_band"]
    lines = [
        "## Frequency Band Analysis",
        "",
        (
            f"- Strongest sampled frequency: `{band['strongest_frequency']}` "
            f"from `{band['strongest_run_id']}` "
            f"with energy-well ratio `{band['strongest_energy_well_ratio']:.6g}`"
        ),
        (
            f"- Half-maximum band: `{half['min_frequency']}` to `{half['max_frequency']}` "
            f"(width `{half['width']:.6g}`, threshold `{half['threshold']:.6g}`)"
        ),
        f"- Local peaks found: `{band['local_peak_count']}`",
        f"- Local troughs found: `{band['local_trough_count']}`",
        f"- Band classification: `{band['classification']}`",
        f"- Interpretation: {band['interpretation']}",
        f"- Mean adjacent shape correlation: `{_format_optional(band['mean_adjacent_shape_correlation'])}`",
        f"- Mean adjacent radial correlation: `{_format_optional(band['mean_adjacent_radial_correlation'])}`",
        "",
        "| Frequency | Energy-Well Ratio | Core Fraction | Score | Shape | Entropy | Corr To Strongest | Radial Corr |",
        "| ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    peak_freqs = {row["frequency"] for row in band["local_peaks"]}
    trough_freqs = {row["frequency"] for row in band["local_troughs"]}
    for row in band["rows"]:
        shape = ""
        if row["frequency"] in peak_freqs:
            shape = "peak"
        elif row["frequency"] in trough_freqs:
            shape = "trough"
        lines.append(
            "| "
            f"{row['frequency']:.6g} | "
            f"{row['energy_well_ratio']:.6g} | "
            f"{row['core_fraction']:.6g} | "
            f"{row['anomaly_score']:.3f} | "
            f"{shape} | "
            f"{row['spatial_entropy_normalized']:.3f} | "
            f"{_format_optional(row['mode_shape_correlation_to_strongest'])} | "
            f"{_format_optional(row['radial_profile_correlation_to_strongest'])} |"
        )

    if band["frequency_thresholds_should_be_downweighted"]:
        lines.extend(
            [
                "",
                (
                    "Dense frequency threshold flags in this sweep are downweighted in run summaries because "
                    "the repeated peak/trough pattern is better treated as band structure at this stage."
                ),
            ]
        )
    return lines


def _candidate_notes(rank: int, summary: dict[str, Any], output_root: Path) -> list[str]:
    config = load_json_config(Path(summary["path"]) / "config.json")
    defect = config["defect"]
    driver = config["driver"]
    run_dir = Path(summary["path"])
    lines = [
        f"### {rank}. {summary['run_id']}",
        "",
        f"- Drive frequency/amplitude: `{driver['frequency']}` / `{driver['amplitude']}`",
        (
            "- Defect: "
            f"radius `{defect['radius']}`, "
            f"stiffness x`{defect['stiffness_multiplier']}`, "
            f"damping x`{defect['damping_multiplier']}`, "
            f"coupling x`{defect['coupling_multiplier']}`"
        ),
        (
            "- Boundary: "
            f"`{config.get('boundary_mode', 'reflective')}`, "
            f"width `{config.get('boundary_damping_width', 0)}`, "
            f"strength `{config.get('boundary_damping_strength', 0)}`"
        ),
        f"- Events: `{', '.join(summary.get('detected_event_labels', [])) or 'none'}`",
        f"- Interpretation: {summary.get('plain_language_interpretation', '')}",
        (
            "- Evidence: "
            f"[best frame]({_relative_link(output_root, run_dir / 'best_frame.png')}), "
            f"[final heatmap]({_relative_link(output_root, run_dir / 'final_heatmap.png')}), "
            f"[energy ratio plot]({_relative_link(output_root, run_dir / 'energy_well_ratio_plot.png')}), "
            f"[core vs outer plot]({_relative_link(output_root, run_dir / 'core_vs_outer_energy_plot.png')}), "
            f"[core spectrum]({_relative_link(output_root, run_dir / 'core_spectrum_plot.png')})"
        ),
    ]
    if summary.get("frame_sequence_path"):
        lines.append(f"- Frame sequence: [{Path(summary['frame_sequence_path']).name}]({_relative_link(output_root, Path(summary['frame_sequence_path']))})")
    if summary.get("frequency_band_classification"):
        lines.append(
            "- Band context: "
            f"`{summary.get('frequency_band_role')}` in `{summary['frequency_band_classification']}`, "
            f"shape corr to strongest `{_format_optional(summary.get('mode_shape_correlation_to_strongest'))}`, "
            f"radial corr `{_format_optional(summary.get('radial_profile_correlation_to_strongest'))}`"
        )
    if summary.get("frequency_band_threshold_downweighted"):
        lines.append(f"- Threshold note: {summary.get('frequency_band_threshold_reason', '')}")
    lines.append("")
    return lines


def _relative_link(output_root: Path, target: Path) -> str:
    try:
        return target.relative_to(output_root).as_posix()
    except ValueError:
        return target.as_posix()


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def _format_optional(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"
