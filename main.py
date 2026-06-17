"""Command-line entry point for WaveEngine."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from simulation.artifact_controls import ArtifactControlOptions, run_artifact_controls
from simulation.breathing_period_audit import (
    BreathingPeriodAuditOptions,
    discover_run_paths,
    run_breathing_period_audit,
)
from simulation.config import (
    SimulationConfig,
    SweepConfig,
    load_json_config,
    simulation_config_from_dict,
    sweep_config_from_dict,
)
from simulation.core_modal_probe import CoreModalProbeOptions, run_core_modal_probe
from simulation.fixed_domain_controls import FixedDomainGridControlOptions, run_fixed_domain_grid_control
from simulation.grid_controls import GridControlOptions, run_grid_control
from simulation.numerical_controls import DtControlOptions, run_dt_control
from simulation.resolution_diagnostics import (
    ResolutionDiagnosticsOptions,
    run_resolution_diagnostics,
    run_source_normalized_resolution_diagnostics,
)
from simulation.sweep import run_single_experiment, run_sweep
from simulation.time_resolved_diagnostics import DiagnosticOptions, diagnose_existing_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="2D lattice wave localization experiment engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one simulation")
    _add_common_sim_args(run_parser)
    run_parser.add_argument("--config", type=Path, help="JSON SimulationConfig override")

    sweep_parser = subparsers.add_parser("sweep", help="Run a parameter sweep and rank candidates")
    _add_common_sim_args(sweep_parser)
    sweep_parser.add_argument("--sweep-config", type=Path, help="JSON SweepConfig override")
    sweep_parser.add_argument("--max-runs", type=int, help="Maximum number of sweep runs")
    sweep_parser.add_argument("--seed", type=int, help="Sweep seed")
    sweep_parser.add_argument(
        "--sampling-mode",
        choices=("hybrid", "random", "stratified", "grid"),
        help="Sweep sampling strategy",
    )
    sweep_parser.add_argument("--report-top-n", type=int, help="Number of ranked runs to include in Markdown report")
    sweep_parser.add_argument("--export-frame-sequences", action="store_true", help="Export heatmap frame sequences for top sweep candidates")
    sweep_parser.add_argument("--frame-sequence-top-n", type=int, help="Number of top candidates to export frame sequences for")
    sweep_parser.add_argument("--frame-sequence-count", type=int, help="Number of frames to save per exported frame sequence")

    diagnose_parser = subparsers.add_parser("diagnose-run", help="Run or load a single run and generate mode-shape diagnostics")
    diagnose_parser.add_argument("--config", type=Path, help="JSON SimulationConfig to run before diagnostics")
    diagnose_parser.add_argument("--run-path", type=Path, help="Existing run directory to diagnose")
    diagnose_parser.add_argument("--output-root", default="runs", help="Directory for new run outputs")
    diagnose_parser.add_argument("--frame-interval", type=int, default=20, help="Base step interval for diagnostic frame snapshots")
    diagnose_parser.add_argument("--window-steps", type=int, default=30, help="Extra frame-capture radius around cutoff, best event, and late tail")
    diagnose_parser.add_argument("--reference-root", type=Path, help="Directory containing sweep summaries for short-peak references")
    diagnose_parser.add_argument("--save-frame-pngs", action="store_true", help="Also render every diagnostic energy/displacement frame as PNG")

    controls_parser = subparsers.add_parser("artifact-controls", help="Run targeted artifact controls for one long-run candidate")
    controls_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the baseline control")
    controls_parser.add_argument("--output-root", default="runs", help="Directory for artifact-control outputs")
    controls_parser.add_argument("--reference-root", type=Path, default=Path("runs"), help="Directory containing sweep summaries for short-peak references")
    controls_parser.add_argument("--frame-interval", type=int, default=20, help="Base step interval for diagnostic frame snapshots")
    controls_parser.add_argument("--window-steps", type=int, default=30, help="Extra frame-capture radius around cutoff, best event, and late tail")
    controls_parser.add_argument("--stronger-sponge-multiplier", type=float, default=2.0, help="Multiplier for stronger sponge damping")
    controls_parser.add_argument("--wider-sponge-multiplier", type=float, default=2.0, help="Multiplier for wider sponge boundary")

    dt_parser = subparsers.add_parser("dt-control", help="Run targeted smaller-dt control for one long-run candidate")
    dt_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the baseline control")
    dt_parser.add_argument("--output-root", default="runs", help="Directory for dt-control outputs")
    dt_parser.add_argument("--reference-root", type=Path, default=Path("runs"), help="Directory containing sweep summaries for short-peak references")
    dt_parser.add_argument("--frame-interval", type=int, default=20, help="Base step interval for diagnostic frame snapshots")
    dt_parser.add_argument("--window-steps", type=int, default=30, help="Extra frame-capture radius around cutoff, best event, and late tail")
    dt_parser.add_argument("--dt-multiplier", type=float, default=0.5, help="Multiplier for the smaller time step; default halves dt")

    grid_parser = subparsers.add_parser("grid-control", help="Run targeted larger-grid control for one long-run candidate")
    grid_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the baseline control")
    grid_parser.add_argument("--output-root", default="runs", help="Directory for grid-control outputs")
    grid_parser.add_argument("--reference-root", type=Path, default=Path("runs"), help="Directory containing sweep summaries for short-peak references")
    grid_parser.add_argument("--frame-interval", type=int, default=20, help="Base step interval for diagnostic frame snapshots")
    grid_parser.add_argument("--window-steps", type=int, default=30, help="Extra frame-capture radius around cutoff, best event, and late tail")
    grid_parser.add_argument("--grid-scale", type=float, default=1.5, help="Scale factor for the larger matched-proportion grid")
    grid_parser.add_argument("--larger-grid-size", type=int, help="Explicit odd larger grid size; overrides --grid-scale")
    grid_parser.add_argument("--larger-physical-duration", type=float, help="Optional physical end time for only the larger-grid variant")

    fixed_grid_parser = subparsers.add_parser(
        "fixed-domain-grid-control",
        help="Run true same-domain grid-refinement control for one long-run candidate",
    )
    fixed_grid_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the baseline control")
    fixed_grid_parser.add_argument("--output-root", default="runs", help="Directory for fixed-domain grid-control outputs")
    fixed_grid_parser.add_argument("--reference-root", type=Path, default=Path("runs"), help="Directory containing sweep summaries for short-peak references")
    fixed_grid_parser.add_argument("--frame-interval", type=int, default=20, help="Base step interval for diagnostic frame snapshots")
    fixed_grid_parser.add_argument("--window-steps", type=int, default=30, help="Extra frame-capture radius around cutoff, best event, and late tail")
    fixed_grid_parser.add_argument("--refined-grid-size", type=int, default=63, help="Same-domain refined grid size")
    fixed_grid_parser.add_argument("--include-81", action="store_true", help="Also run an optional 81x81 same-domain variant")

    resolution_parser = subparsers.add_parser(
        "resolution-diagnostics",
        help="Audit source, mask, energy-budget, radial, and mode-shape resolution sensitivity",
    )
    resolution_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the baseline candidate")
    resolution_parser.add_argument("--output-root", default="runs", help="Directory for resolution diagnostic outputs")
    resolution_parser.add_argument("--reference-root", type=Path, default=Path("runs"), help="Directory containing sweep summaries for short-peak references")
    resolution_parser.add_argument("--frame-interval", type=int, default=20, help="Base step interval for diagnostic frame snapshots")
    resolution_parser.add_argument("--window-steps", type=int, default=30, help="Extra frame-capture radius around cutoff, best event, and late tail")
    resolution_parser.add_argument(
        "--grid-sizes",
        type=int,
        nargs="+",
        default=(41, 63, 81),
        help="Fixed-domain grid sizes to audit; default is 41 63 81",
    )

    source_resolution_parser = subparsers.add_parser(
        "source-normalized-resolution-diagnostics",
        help="Run fixed-domain resolution diagnostics with physically normalized source coverage",
    )
    source_resolution_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the baseline candidate")
    source_resolution_parser.add_argument("--output-root", default="runs", help="Directory for source-normalized diagnostic outputs")
    source_resolution_parser.add_argument("--reference-root", type=Path, default=Path("runs"), help="Directory containing sweep summaries for short-peak references")
    source_resolution_parser.add_argument("--frame-interval", type=int, default=20, help="Base step interval for diagnostic frame snapshots")
    source_resolution_parser.add_argument("--window-steps", type=int, default=30, help="Extra frame-capture radius around cutoff, best event, and late tail")
    source_resolution_parser.add_argument(
        "--grid-sizes",
        type=int,
        nargs="+",
        default=(41, 63, 81),
        help="Fixed-domain grid sizes to audit; default is 41 63 81",
    )
    source_resolution_parser.add_argument(
        "--source-normalization",
        choices=("per_length", "constant_boundary_flux", "constant_total_work"),
        default="constant_total_work",
        help="Physical source normalization mode for the main variants",
    )

    breathing_audit_parser = subparsers.add_parser(
        "breathing-period-audit",
        help="Audit completed runs for breathing-period peak-picking sensitivity",
    )
    breathing_audit_parser.add_argument("--control-root", type=Path, help="Control folder containing run subdirectories")
    breathing_audit_parser.add_argument("--run-path", type=Path, action="append", help="Completed run directory to audit; repeatable")
    breathing_audit_parser.add_argument("--output-dir", type=Path, help="Directory for audit outputs")
    breathing_audit_parser.add_argument("--percentile", type=float, default=55.0, help="Core-energy percentile threshold for peak filtering")

    core_probe_parser = subparsers.add_parser(
        "core-modal-probe",
        help="Run controlled direct-core modal probes for the source-normalized fixed-domain 0.92 candidate",
    )
    core_probe_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the baseline candidate")
    core_probe_parser.add_argument("--output-root", default="runs", help="Directory for core-modal probe outputs")
    core_probe_parser.add_argument("--reference-root", type=Path, default=Path("runs"), help="Directory containing sweep summaries for short-peak references")
    core_probe_parser.add_argument("--frame-interval", type=int, default=20, help="Base step interval for diagnostic frame snapshots")
    core_probe_parser.add_argument("--window-steps", type=int, default=30, help="Extra frame-capture radius around cutoff, best event, and late tail")
    core_probe_parser.add_argument(
        "--source-normalization",
        choices=("per_length", "constant_boundary_flux", "constant_total_work"),
        default="constant_total_work",
        help="Physical boundary-source normalization mode for reference runs",
    )
    core_probe_parser.add_argument("--min-peak-separation", type=float, default=1.5, help="Minimum time separation for full-metric breathing peaks")

    return parser


def _add_common_sim_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-root", default="runs", help="Directory for run outputs")
    parser.add_argument("--grid-size", type=int, help="Lattice width and height")
    parser.add_argument("--steps", type=int, help="Number of integration steps")
    parser.add_argument("--dt", type=float, help="Integration time step")
    parser.add_argument("--drive-cutoff-time", type=float, help="Time when the boundary drive turns off")
    parser.add_argument("--boundary-mode", choices=("reflective", "sponge"), help="Boundary damping mode")
    parser.add_argument("--boundary-damping-width", type=int, help="Sponge boundary width in lattice cells")
    parser.add_argument("--boundary-damping-strength", type=float, help="Maximum added damping at the boundary edge")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        config = _load_sim_config(args.config)
        _apply_sim_overrides(config, args)
        summary = run_single_experiment(config, output_root=args.output_root)
        _print_single_summary(summary)
        return

    if args.command == "sweep":
        base_config = SimulationConfig()
        _apply_sim_overrides(base_config, args)
        sweep_config = _load_sweep_config(args.sweep_config)
        sweep_config.output_root = args.output_root
        if args.max_runs is not None:
            sweep_config.max_runs = args.max_runs
        if args.seed is not None:
            sweep_config.seed = args.seed
        if args.sampling_mode is not None:
            sweep_config.sampling_mode = args.sampling_mode
        if args.report_top_n is not None:
            sweep_config.report_top_n = args.report_top_n
        if args.export_frame_sequences:
            sweep_config.export_frame_sequences = True
        if args.frame_sequence_top_n is not None:
            sweep_config.frame_sequence_top_n = args.frame_sequence_top_n
        if args.frame_sequence_count is not None:
            sweep_config.frame_sequence_count = args.frame_sequence_count
        summaries = run_sweep(base_config, sweep_config)
        _print_top_runs(summaries[:10])
        return

    if args.command == "diagnose-run":
        if args.config is None and args.run_path is None:
            parser.error("diagnose-run requires --config or --run-path")
        if args.config is not None and args.run_path is not None:
            parser.error("diagnose-run accepts either --config or --run-path, not both")

        if args.run_path is not None:
            run_dir = args.run_path
        else:
            config = _load_sim_config(args.config)
            summary = run_single_experiment(config, output_root=args.output_root)
            run_dir = Path(summary["path"])

        diagnostics = diagnose_existing_run(
            run_dir,
            options=DiagnosticOptions(
                frame_interval=args.frame_interval,
                window_steps=args.window_steps,
                save_frame_pngs=args.save_frame_pngs,
            ),
            reference_root=args.reference_root if args.reference_root is not None else args.output_root,
        )
        _print_diagnostic_summary(diagnostics)
        return

    if args.command == "artifact-controls":
        config = _load_sim_config(args.config)
        result = run_artifact_controls(
            config,
            options=ArtifactControlOptions(
                output_root=args.output_root,
                frame_interval=args.frame_interval,
                window_steps=args.window_steps,
                stronger_sponge_multiplier=args.stronger_sponge_multiplier,
                wider_sponge_multiplier=args.wider_sponge_multiplier,
            ),
            reference_root=args.reference_root,
        )
        _print_artifact_control_summary(result)
        return

    if args.command == "dt-control":
        config = _load_sim_config(args.config)
        result = run_dt_control(
            config,
            options=DtControlOptions(
                output_root=args.output_root,
                frame_interval=args.frame_interval,
                window_steps=args.window_steps,
                dt_multiplier=args.dt_multiplier,
            ),
            reference_root=args.reference_root,
        )
        _print_dt_control_summary(result)
        return

    if args.command == "grid-control":
        config = _load_sim_config(args.config)
        result = run_grid_control(
            config,
            options=GridControlOptions(
                output_root=args.output_root,
                frame_interval=args.frame_interval,
                window_steps=args.window_steps,
                grid_scale=args.grid_scale,
                larger_grid_size=args.larger_grid_size,
                larger_physical_duration=args.larger_physical_duration,
            ),
            reference_root=args.reference_root,
        )
        _print_grid_control_summary(result)
        return

    if args.command == "fixed-domain-grid-control":
        config = _load_sim_config(args.config)
        result = run_fixed_domain_grid_control(
            config,
            options=FixedDomainGridControlOptions(
                output_root=args.output_root,
                frame_interval=args.frame_interval,
                window_steps=args.window_steps,
                refined_grid_size=args.refined_grid_size,
                include_81=args.include_81,
            ),
            reference_root=args.reference_root,
        )
        _print_fixed_domain_grid_control_summary(result)
        return

    if args.command == "resolution-diagnostics":
        config = _load_sim_config(args.config)
        result = run_resolution_diagnostics(
            config,
            options=ResolutionDiagnosticsOptions(
                output_root=args.output_root,
                frame_interval=args.frame_interval,
                window_steps=args.window_steps,
                grid_sizes=tuple(args.grid_sizes),
            ),
            reference_root=args.reference_root,
        )
        _print_resolution_diagnostics_summary(result)
        return

    if args.command == "source-normalized-resolution-diagnostics":
        config = _load_sim_config(args.config)
        result = run_source_normalized_resolution_diagnostics(
            config,
            options=ResolutionDiagnosticsOptions(
                output_root=args.output_root,
                frame_interval=args.frame_interval,
                window_steps=args.window_steps,
                grid_sizes=tuple(args.grid_sizes),
            ),
            reference_root=args.reference_root,
            source_normalization=args.source_normalization,
        )
        _print_source_normalized_resolution_summary(result)
        return

    if args.command == "breathing-period-audit":
        if args.control_root is None and not args.run_path:
            parser.error("breathing-period-audit requires --control-root or --run-path")
        run_paths = list(args.run_path or [])
        if args.control_root is not None:
            run_paths.extend(discover_run_paths(args.control_root))
        output_dir = args.output_dir
        if output_dir is None:
            output_dir = (args.control_root or Path(run_paths[0]).parent) / "breathing_period_audit"
        result = run_breathing_period_audit(
            run_paths,
            output_dir=output_dir,
            options=BreathingPeriodAuditOptions(percentile=args.percentile),
        )
        _print_breathing_period_audit_summary(result)
        return

    if args.command == "core-modal-probe":
        config = _load_sim_config(args.config)
        result = run_core_modal_probe(
            config,
            options=CoreModalProbeOptions(
                output_root=args.output_root,
                frame_interval=args.frame_interval,
                window_steps=args.window_steps,
                source_normalization=args.source_normalization,
                min_peak_separation=args.min_peak_separation,
            ),
            reference_root=args.reference_root,
        )
        _print_core_modal_probe_summary(result)
        return

    parser.error(f"Unknown command: {args.command}")


def _load_sim_config(path: Path | None) -> SimulationConfig:
    if path is None:
        return SimulationConfig()
    return simulation_config_from_dict(load_json_config(path))


def _load_sweep_config(path: Path | None) -> SweepConfig:
    if path is None:
        return SweepConfig()
    return sweep_config_from_dict(load_json_config(path))


def _apply_sim_overrides(config: SimulationConfig, args: argparse.Namespace) -> None:
    overrides: dict[str, Any] = {
        "grid_size": args.grid_size,
        "steps": args.steps,
        "dt": args.dt,
        "boundary_mode": args.boundary_mode,
        "boundary_damping_width": args.boundary_damping_width,
        "boundary_damping_strength": args.boundary_damping_strength,
    }
    for key, value in overrides.items():
        if value is not None:
            setattr(config, key, value)
    if args.drive_cutoff_time is not None:
        config.driver.drive_cutoff_time = args.drive_cutoff_time


def _print_single_summary(summary: dict[str, Any]) -> None:
    print("Run complete")
    print(f"run ID: {summary['run_id']}")
    print(f"anomaly_score: {summary['anomaly_score']:.3f}")
    print(f"best energy_well_ratio: {summary['best_energy_well_ratio']:.6g}")
    print(f"retention_score: {summary['retention_score']:.6g}")
    print(f"localization_index: {summary['localization_score']:.6g}")
    print(f"detected events: {', '.join(summary['detected_event_labels']) or 'none'}")
    print(f"path: {summary['path']}")


def _print_top_runs(summaries: list[dict[str, Any]]) -> None:
    print()
    print("Top 10 most interesting runs")
    print("=" * 32)
    for rank, summary in enumerate(summaries, start=1):
        config_path = Path(summary["path"]) / "config.json"
        config_data = load_json_config(config_path)
        defect = config_data["defect"]
        driver = config_data["driver"]
        print(f"{rank}. {summary['run_id']}")
        print(f"   drive frequency/amplitude: {driver['frequency']} / {driver['amplitude']}")
        print(
            "   defect: "
            f"radius={defect['radius']}, "
            f"stiffness x{defect['stiffness_multiplier']}, "
            f"damping x{defect['damping_multiplier']}, "
            f"coupling x{defect['coupling_multiplier']}"
        )
        print(f"   phase mode: {driver['phase_mode']}")
        print(
            "   boundary: "
            f"{config_data.get('boundary_mode', 'reflective')}, "
            f"width={config_data.get('boundary_damping_width', 0)}, "
            f"strength={config_data.get('boundary_damping_strength', 0)}"
        )
        print(f"   best energy_well_ratio: {summary['best_energy_well_ratio']:.6g}")
        print(f"   retention score: {summary['retention_score']:.6g}")
        print(f"   localization index: {summary['localization_score']:.6g}")
        print(f"   anomaly_score: {summary['anomaly_score']:.3f}")
        print(f"   detected events: {', '.join(summary['detected_event_labels']) or 'none'}")
        print(f"   evidence: {summary['path']}")
        print()


def _print_diagnostic_summary(diagnostics: dict[str, Any]) -> None:
    breathing = diagnostics.get("breathing_detection", {})
    transition = diagnostics.get("mode_transition_detection", {})
    angular = diagnostics.get("angular_detection", {})
    print("Mode diagnostics complete")
    print(f"run ID: {diagnostics.get('run_id')}")
    print(f"best event time: {diagnostics.get('best_frame_time')}")
    print(f"best energy_well_ratio: {float(diagnostics.get('best_energy_well_ratio', 0.0)):.6g}")
    print(f"retention score: {float(diagnostics.get('retention_score', 0.0)):.6g}")
    print(f"detected labels: {', '.join(_diagnostic_labels(diagnostics)) or 'none'}")
    transition_time = transition.get("transition_time") if transition.get("status") == "detected" else None
    print(f"transition time: {_format_optional(transition_time)}")
    print(f"breathing period: {_format_optional(breathing.get('estimated_period'))}")
    print(f"strongest angular mode: {angular.get('strongest_angular_mode', 'n/a')}")
    print(f"report: {diagnostics.get('report_path')}")


def _print_artifact_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("Artifact controls complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"ratio={float(row.get('best_energy_well_ratio', 0.0)):.6g}, "
            f"retention={float(row.get('retention_score', 0.0)):.6g}, "
            f"breathing={row.get('breathing_detected')}, "
            f"angular_r2={_format_optional(row.get('angular_phase_trend_r2'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")


def _print_dt_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("Time-step controls complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"dt={float(row.get('dt', 0.0)):.6g}, "
            f"steps={row.get('steps')}, "
            f"ratio={float(row.get('best_energy_well_ratio', 0.0)):.6g}, "
            f"core={_format_optional(row.get('best_core_energy'))}, "
            f"retention={float(row.get('retention_score', 0.0)):.6g}, "
            f"breathing={row.get('breathing_detected')}, "
            f"period={_format_optional(row.get('breathing_period'))}, "
            f"mode=m{row.get('strongest_angular_mode')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")


def _print_grid_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("Grid controls complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"grid={row.get('grid_size')}, "
            f"defect={row.get('defect_radius')}, "
            f"ratio={float(row.get('best_energy_well_ratio', 0.0)):.6g}, "
            f"core_fraction={_format_optional(row.get('best_core_fraction'))}, "
            f"core_density={_format_optional(row.get('best_core_energy_density'))}, "
            f"retention={float(row.get('retention_score', 0.0)):.6g}, "
            f"breathing={row.get('breathing_detected')}, "
            f"period={_format_optional(row.get('breathing_period'))}, "
            f"mode=m{row.get('strongest_angular_mode')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")


def _print_fixed_domain_grid_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("Fixed-domain grid controls complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"grid={row.get('grid_size')}, "
            f"dx={_format_optional(row.get('dx'))}, "
            f"ratio={float(row.get('best_energy_well_ratio', 0.0)):.6g}, "
            f"retention={float(row.get('retention_score', 0.0)):.6g}, "
            f"best_time={_format_optional(row.get('best_event_time'))}, "
            f"breathing={row.get('breathing_detected')}, "
            f"period={_format_optional(row.get('breathing_period'))}, "
            f"radial_peak={_format_optional(row.get('best_event_radial_peak_radius_physical'))}, "
            f"similarity={_format_optional(row.get('best_frame_similarity_to_baseline'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")


def _print_resolution_diagnostics_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("Resolution diagnostics complete")
    print(f"diagnostic ID: {result['diagnostic_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"grid={row.get('grid_size')}, "
            f"dx={_format_optional(row.get('dx'))}, "
            f"ratio={float(row.get('best_energy_well_ratio', 0.0)):.6g}, "
            f"retention={float(row.get('retention_score', 0.0)):.6g}, "
            f"best_time={_format_optional(row.get('best_event_time'))}, "
            f"period={_format_optional(row.get('breathing_period'))}, "
            f"radial_peak={_format_optional(row.get('radial_peak_radius'))}, "
            f"m={row.get('strongest_angular_mode')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"source audit: {result['source_audit_csv']}")
    print(f"mask audit: {result['mask_area_audit_csv']}")
    print(f"energy budget audit: {result['energy_budget_audit_csv']}")
    print(f"radial comparison: {result['radial_profile_comparison_csv']}")
    print(f"report: {result['report_path']}")


def _print_source_normalized_resolution_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("Source-normalized resolution diagnostics complete")
    print(f"diagnostic ID: {result['diagnostic_id']}")
    print(f"source normalization: {result['source_normalization']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("source-normalized variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"grid={row.get('grid_size')}, "
            f"dx={_format_optional(row.get('dx'))}, "
            f"ratio={float(row.get('best_energy_well_ratio', 0.0)):.6g}, "
            f"retention={float(row.get('retention_score', 0.0)):.6g}, "
            f"best_time={_format_optional(row.get('best_event_time'))}, "
            f"period={_format_optional(row.get('breathing_period'))}, "
            f"radial_peak={_format_optional(row.get('radial_peak_radius'))}, "
            f"m={row.get('strongest_angular_mode')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"source audit comparison: {result['source_audit_comparison_csv']}")
    print(f"injected work comparison: {result['injected_work_comparison_csv']}")
    print(f"mask audit: {result['mask_area_audit_csv']}")
    print(f"energy budget audit: {result['energy_budget_audit_csv']}")
    print(f"radial comparison: {result['radial_profile_comparison_csv']}")
    print(f"report: {result['report_path']}")


def _print_breathing_period_audit_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("Breathing-period audit complete")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"summary CSV: {result['summary_csv']}")
    print(f"peak times CSV: {result['peak_times_csv']}")
    print(f"report: {result['report_path']}")


def _print_core_modal_probe_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    best_core = result.get("best_matching_core_probe") or {}
    print("Core-modal probe complete")
    print(f"probe ID: {result['probe_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best matching core-probe run: {best_core.get('variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"drive={row.get('drive_location')}"
            f"{('/' + row.get('core_drive_mode')) if row.get('core_drive_mode') else ''}, "
            f"work={_format_optional(row.get('injected_work_before_cutoff'))}, "
            f"retention={_format_optional(row.get('post_cutoff_retention'))}, "
            f"period={_format_optional(row.get('breathing_period_after_cutoff'))}, "
            f"radial={_format_optional(row.get('radial_peak_after_cutoff_physical'))}, "
            f"m4={_format_optional(row.get('m4_strength_after_cutoff'))}, "
            f"sim={_format_optional(row.get('best_frame_similarity_to_boundary_reference'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")


def _diagnostic_labels(diagnostics: dict[str, Any]) -> list[str]:
    labels = []
    for key in ("breathing_detection", "mode_transition_detection"):
        label = diagnostics.get(key, {}).get("label")
        if label:
            labels.append(label)
    labels.extend(diagnostics.get("angular_detection", {}).get("labels", []))
    labels.extend(diagnostics.get("reference_comparison", {}).get("labels", []))
    return labels


def _format_optional(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.6g}"


if __name__ == "__main__":
    main()
