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
from simulation.prototype_3d import Prototype3DOptions, run_3d_prototype
from simulation.prototype_3d_audit import (
    Prototype3DFailureAuditOptions,
    run_3d_failure_audit,
)
from simulation.prototype_3d_cubic_confirmation import (
    CubicConfirmationControlOptions,
    run_3d_cubic_confirmation_control,
)
from simulation.prototype_3d_cubic_focus import (
    CubicFocusControlOptions,
    run_3d_cubic_focus_control,
)
from simulation.prototype_3d_cutoff_phase_map import (
    CutoffPhaseMap3DOptions,
    run_3d_cutoff_phase_map_control,
)
from simulation.prototype_3d_defect_control import (
    DefectControl3DOptions,
    run_3d_defect_control,
)
from simulation.prototype_3d_defect_lift_sweep import (
    DefectLiftSweep3DOptions,
    run_3d_defect_lift_sweep,
)
from simulation.prototype_3d_grid_confirmation import (
    GridConfirmation3DOptions,
    run_3d_grid_confirmation_control,
)
from simulation.prototype_3d_interference_diagnostics import (
    InterferenceDiagnostics3DOptions,
    run_3d_interference_diagnostics,
)
from simulation.prototype_3d_standing_persistence import (
    StandingPersistence3DOptions,
    run_3d_standing_persistence_control,
)
from simulation.prototype_3d_transport_packet import (
    TransportPacket3DOptions,
    run_3d_transport_packet_audit,
)
from simulation.prototype_3d_packet_lifecycle import (
    PacketLifecycle3DOptions,
    run_3d_packet_lifecycle_audit,
)
from simulation.prototype_3d_refocusing_engineering import (
    RefocusingEngineering3DOptions,
    run_3d_refocusing_engineering_control,
)
from simulation.prototype_3d_refocusing_map import (
    RefocusingMap3DOptions,
    run_3d_refocusing_map_control,
)
from simulation.prototype_3d_resonator_layer import (
    ResonatorLayer3DOptions,
    run_3d_resonator_layer_control,
)
from simulation.prototype_3d_release_phase_return_map import (
    ReleasePhaseReturnMapOptions,
    run_3d_release_phase_return_map,
)
from simulation.prototype_3d_release_phase_blind_confirmation import (
    ReleasePhaseBlindConfirmationOptions,
    run_3d_release_phase_blind_confirmation,
)
from simulation.prototype_3d_release_phase_numerical_validation import (
    ReleasePhaseNumericalValidationOptions,
    run_3d_release_phase_numerical_validation,
)
from simulation.prototype_3d_release_phase_dt_recenter import (
    ReleasePhaseDtRecenterOptions,
    run_3d_release_phase_dt_recenter,
)
from simulation.prototype_3d_release_phase_proof_pack import (
    ReleasePhaseProofPackOptions,
    run_3d_release_phase_proof_pack,
)
from simulation.prototype_3d_release_phase_resolution_lift import (
    ReleasePhaseResolutionLiftOptions,
    run_3d_release_phase_resolution_lift,
)
from simulation.prototype_3d_release_phase_resolution_postmortem import (
    DEFAULT_LIFT_ROOT,
    DEFAULT_PROOF_ROOT,
    ReleasePhaseResolutionPostmortemOptions,
    run_3d_release_phase_resolution_postmortem,
)
from simulation.prototype_3d_release_phase_modal_audit import (
    DEFAULT_CENTRAL_ROOT as DEFAULT_MODAL_CENTRAL_ROOT,
    DEFAULT_LIFT_ROOT as DEFAULT_MODAL_LIFT_ROOT,
    DEFAULT_POSTMORTEM_ROOT as DEFAULT_MODAL_POSTMORTEM_ROOT,
    DEFAULT_PROOF_ROOT as DEFAULT_MODAL_PROOF_ROOT,
    ReleasePhaseModalAuditOptions,
    run_3d_release_phase_modal_audit,
)
from simulation.prototype_3d_release_phase_dispersion_audit import (
    DEFAULT_CONFIG_PATH as DEFAULT_DISPERSION_CONFIG_PATH,
    DEFAULT_LIFT_ROOT as DEFAULT_DISPERSION_LIFT_ROOT,
    DEFAULT_MODAL_ROOT as DEFAULT_DISPERSION_MODAL_ROOT,
    DEFAULT_POSTMORTEM_ROOT as DEFAULT_DISPERSION_POSTMORTEM_ROOT,
    DEFAULT_PROOF_ROOT as DEFAULT_DISPERSION_PROOF_ROOT,
    ReleasePhaseDispersionAuditOptions,
    run_3d_release_phase_dispersion_audit,
)
from simulation.prototype_3d_spatial_phase_instrumentation import (
    SpatialPhaseInstrumentationOptions,
    run_3d_spatial_phase_instrumentation,
)
from simulation.prototype_3d_spatial_phase_precompensation_design import (
    DEFAULT_SPATIAL_PHASE_ROOT as DEFAULT_PRECOMP_SPATIAL_PHASE_ROOT,
    SpatialPhasePrecompensationDesignOptions,
    run_3d_spatial_phase_precompensation_design,
)
from simulation.prototype_3d_source_spectrum_design_audit import (
    DEFAULT_CONFIG_PATH as DEFAULT_SOURCE_SPECTRUM_CONFIG_PATH,
    DEFAULT_DISPERSION_ROOT as DEFAULT_SOURCE_SPECTRUM_DISPERSION_ROOT,
    DEFAULT_PRECOMP_ROOT as DEFAULT_SOURCE_SPECTRUM_PRECOMP_ROOT,
    DEFAULT_SPATIAL_PHASE_ROOT as DEFAULT_SOURCE_SPECTRUM_SPATIAL_ROOT,
    SourceSpectrumDesignAuditOptions,
    run_3d_source_spectrum_design_audit,
)
from simulation.prototype_3d_central_burst import (
    CentralBurst3DOptions,
    run_3d_central_burst_control,
)
from simulation.prototype_3d_second_pulse import (
    SecondPulse3DOptions,
    run_3d_second_pulse_control,
)
from simulation.prototype_3d_radial_window_audit import (
    RadialWindowAudit3DOptions,
    run_3d_radial_window_audit,
)
from simulation.prototype_3d_threshold_control import (
    ThresholdControl3DOptions,
    run_3d_threshold_control,
)
from simulation.prototype_3d_source_sponge import (
    SourceSpongeControlOptions,
    run_3d_source_sponge_control,
)
from simulation.prototype_3d_source_geometry import (
    SourceGeometryControlOptions,
    run_3d_source_geometry_control,
)
from simulation.prototype_3d_sponge_strength import (
    SpongeStrengthControlOptions,
    run_3d_sponge_strength_control,
)
from simulation.resolution_diagnostics import (
    ResolutionDiagnosticsOptions,
    run_resolution_diagnostics,
    run_source_normalized_resolution_diagnostics,
)
from simulation.sweep import run_single_experiment, run_sweep
from simulation.time_resolved_diagnostics import DiagnosticOptions, diagnose_existing_run
from simulation.transport_controls import TransportControlOptions, run_transport_controls


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

    transport_parser = subparsers.add_parser(
        "transport-controls",
        help="Run targeted source-geometry transport controls for the fixed-domain 0.92 candidate",
    )
    transport_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the baseline candidate")
    transport_parser.add_argument("--output-root", default="runs", help="Directory for transport-control outputs")
    transport_parser.add_argument("--reference-root", type=Path, default=Path("runs"), help="Directory containing sweep summaries for short-peak references")
    transport_parser.add_argument("--frame-interval", type=int, default=20, help="Base step interval for diagnostic frame snapshots")
    transport_parser.add_argument("--window-steps", type=int, default=30, help="Extra frame-capture radius around cutoff, best event, and late tail")
    transport_parser.add_argument(
        "--source-normalization",
        choices=("per_length", "constant_boundary_flux", "constant_total_work"),
        default="constant_total_work",
        help="Physical boundary-source normalization mode for the four-side reference",
    )
    transport_parser.add_argument("--grid-size", type=int, default=63, help="Fixed-domain grid size for this narrow transport control")
    transport_parser.add_argument("--min-peak-separation", type=float, default=1.5, help="Minimum time separation for full-metric breathing peaks")
    transport_parser.add_argument(
        "--boundary-match-mode",
        choices=("total_work", "work_per_length"),
        default="total_work",
        help="How boundary geometry variants are matched to the four-side reference",
    )
    transport_parser.add_argument("--boundary-only", action="store_true", help="Run only boundary-geometry variants, skipping annulus probes")

    prototype_3d_parser = subparsers.add_parser(
        "prototype-3d",
        help="Run a tiny fixed-domain 3D shell-breathing prototype for the 0.92 candidate",
    )
    prototype_3d_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    prototype_3d_parser.add_argument("--output-root", default="runs", help="Directory for 3D prototype outputs")
    prototype_3d_parser.add_argument("--grid-size", type=int, default=31, help="3D grid size; default starts tiny at 31^3")
    prototype_3d_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    prototype_3d_parser.add_argument("--skip-dt-control", action="store_true", help="Skip the half-dt confirmation variant")
    prototype_3d_parser.add_argument("--skip-sponge-control", action="store_true", help="Skip the stronger-sponge confirmation variant")

    prototype_3d_audit_parser = subparsers.add_parser(
        "prototype-3d-audit",
        help="Audit a completed tiny 3D prototype for source/sponge and near-defect shell failure modes",
    )
    prototype_3d_audit_parser.add_argument("--run-path", type=Path, required=True, help="Completed prototype-3d output folder")
    prototype_3d_audit_parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/long_validation_peak_0_92.json"),
        help="2D baseline config used to derive 3D geometry; defaults to the long 0.92 candidate",
    )
    prototype_3d_audit_parser.add_argument("--output-dir", type=Path, help="Directory for audit outputs")
    prototype_3d_audit_parser.add_argument("--radial-bins", type=int, default=24, help="Radial bin count used by the prototype run")
    prototype_3d_audit_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Near-defect shell audit width in dx units")

    source_sponge_parser = subparsers.add_parser(
        "prototype-3d-source-sponge-control",
        help="Run tiny 31^3 3D controls that separate boundary source placement from sponge damping",
    )
    source_sponge_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    source_sponge_parser.add_argument("--output-root", default="runs", help="Directory for source/sponge control outputs")
    source_sponge_parser.add_argument("--grid-size", type=int, default=31, help="3D grid size; keep tiny at 31^3")
    source_sponge_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    source_sponge_parser.add_argument("--gap-cells-from-sponge", type=float, default=3.0, help="Gap in dx units for the inward source variant")
    source_sponge_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Near-defect shell audit width in dx units")

    sponge_strength_parser = subparsers.add_parser(
        "prototype-3d-sponge-strength-control",
        help="Run tiny 31^3 sponge-strength controls for the inner-sponge-edge 3D source",
    )
    sponge_strength_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    sponge_strength_parser.add_argument("--output-root", default="runs", help="Directory for sponge-strength control outputs")
    sponge_strength_parser.add_argument("--grid-size", type=int, default=31, help="3D grid size; keep tiny at 31^3")
    sponge_strength_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    sponge_strength_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Near-defect shell audit width in dx units")
    sponge_strength_parser.add_argument("--weak-sponge-multiplier", type=float, default=0.5, help="Multiplier for weak sponge damping")
    sponge_strength_parser.add_argument("--stronger-sponge-multiplier", type=float, default=2.0, help="Multiplier for stronger sponge damping")
    sponge_strength_parser.add_argument("--wider-sponge-multiplier", type=float, default=2.0, help="Multiplier for wider sponge boundary")

    source_geometry_parser = subparsers.add_parser(
        "prototype-3d-source-geometry-control",
        help="Run tiny 31^3 source-geometry controls from the stronger-sponge inner-edge 3D setup",
    )
    source_geometry_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    source_geometry_parser.add_argument("--output-root", default="runs", help="Directory for source-geometry control outputs")
    source_geometry_parser.add_argument("--grid-size", type=int, default=31, help="3D grid size; keep tiny at 31^3")
    source_geometry_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    source_geometry_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Near-defect shell audit width in dx units")
    source_geometry_parser.add_argument("--sponge-strength-multiplier", type=float, default=2.0, help="Stronger sponge multiplier for every variant")
    source_geometry_parser.add_argument("--random-phase-seed", type=int, default=31092, help="Deterministic seed for random face phases")

    cubic_focus_parser = subparsers.add_parser(
        "prototype-3d-cubic-focus-control",
        help="Run tiny 31^3 controls around the clean six-face cubic 3D boundary source",
    )
    cubic_focus_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    cubic_focus_parser.add_argument("--output-root", default="runs", help="Directory for cubic-focus control outputs")
    cubic_focus_parser.add_argument("--grid-size", type=int, default=31, help="3D grid size; keep tiny at 31^3")
    cubic_focus_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    cubic_focus_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Near-defect shell audit width in dx units")
    cubic_focus_parser.add_argument("--sponge-strength-multiplier", type=float, default=2.0, help="Stronger sponge multiplier for every variant")
    cubic_focus_parser.add_argument("--phase-offset", type=float, default=0.5 * 3.141592653589793, help="Global phase offset for the cubic phase-offset variant")
    cubic_focus_parser.add_argument("--imbalance-scale", type=float, default=0.75, help="Amplitude multiplier for the first weakened face")
    cubic_focus_parser.add_argument("--second-imbalance-scale", type=float, default=0.85, help="Amplitude multiplier for the second weakened face")
    cubic_focus_parser.add_argument("--random-phase-seed", type=int, default=31092, help="Deterministic seed for repeated random face phases")

    cubic_confirmation_parser = subparsers.add_parser(
        "prototype-3d-cubic-confirmation-control",
        help="Run tiny 31^3 dt/sponge confirmations for clean cubic-phase 3D boundary sources",
    )
    cubic_confirmation_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    cubic_confirmation_parser.add_argument("--output-root", default="runs", help="Directory for cubic-confirmation control outputs")
    cubic_confirmation_parser.add_argument("--grid-size", type=int, default=31, help="3D grid size; keep tiny at 31^3")
    cubic_confirmation_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    cubic_confirmation_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Near-defect shell audit width in dx units")
    cubic_confirmation_parser.add_argument("--base-sponge-strength-multiplier", type=float, default=2.0, help="Baseline stronger sponge multiplier versus the original 3D sponge")
    cubic_confirmation_parser.add_argument("--weak-sponge-relative-multiplier", type=float, default=0.75, help="Weak sponge multiplier relative to the confirmation baseline sponge")
    cubic_confirmation_parser.add_argument("--stronger-sponge-relative-multiplier", type=float, default=1.5, help="Stronger sponge multiplier relative to the confirmation baseline sponge")
    cubic_confirmation_parser.add_argument("--half-dt-multiplier", type=float, default=0.5, help="Time-step multiplier for the half-dt variants")
    cubic_confirmation_parser.add_argument("--amplitude-reduction-multiplier", type=float, default=0.75, help="Drive-amplitude multiplier for the sign-flip amplitude-reduced probe")

    grid_confirmation_parser = subparsers.add_parser(
        "prototype-3d-grid-confirmation-control",
        help="Run a tiny fixed-domain 31^3 to 41^3 grid confirmation for the clean 3D sign-flip source",
    )
    grid_confirmation_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    grid_confirmation_parser.add_argument("--output-root", default="runs", help="Directory for 3D grid-confirmation outputs")
    grid_confirmation_parser.add_argument("--baseline-grid-size", type=int, default=31, help="Baseline 3D grid size")
    grid_confirmation_parser.add_argument("--refined-grid-size", type=int, default=41, help="Refined 3D grid size")
    grid_confirmation_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    grid_confirmation_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Near-defect shell audit width in dx units")
    grid_confirmation_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    grid_confirmation_parser.add_argument("--skip-original-cubic-41", action="store_true", help="Skip the optional original cubic 41^3 comparator")
    grid_confirmation_parser.add_argument(
        "--negative-control",
        choices=("direct_shell", "uniform_phase"),
        default="direct_shell",
        help="Single 41^3 negative control to run",
    )

    threshold_parser = subparsers.add_parser(
        "prototype-3d-threshold-control",
        help="Run a tiny 41^3 amplitude/phase threshold check for the clean 3D sign-flip source",
    )
    threshold_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    threshold_parser.add_argument("--output-root", default="runs", help="Directory for 3D threshold-control outputs")
    threshold_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this control is intended for 41^3")
    threshold_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    threshold_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    threshold_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Near-defect shell audit width in dx units")
    threshold_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    threshold_parser.add_argument(
        "--skip-amp-1-5",
        action="store_true",
        help="Skip the optional 1.5x high-amplitude variant",
    )
    threshold_parser.add_argument("--skip-direct-core", action="store_true", help="Skip the direct-core reference control")
    threshold_parser.add_argument("--skip-direct-shell", action="store_true", help="Skip the direct-shell reference control")

    defect_parser = subparsers.add_parser(
        "prototype-3d-defect-control",
        help="Run a tiny 41^3 defect-dependence control for the clean 3D sign-flip source",
    )
    defect_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    defect_parser.add_argument("--output-root", default="runs", help="Directory for 3D defect-control outputs")
    defect_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this control is intended for 41^3")
    defect_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    defect_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    defect_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Near-defect shell audit width in dx units")
    defect_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    defect_parser.add_argument("--smaller-radius-multiplier", type=float, default=0.75, help="Multiplier for the smaller-defect-radius variant")
    defect_parser.add_argument("--larger-radius-multiplier", type=float, default=1.25, help="Multiplier for the larger-defect-radius variant")

    radial_window_parser = subparsers.add_parser(
        "prototype-3d-radial-window-audit",
        help="Run a tiny 41^3 radial-window neutral-vs-defect audit for the clean 3D sign-flip source",
    )
    radial_window_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    radial_window_parser.add_argument("--output-root", default="runs", help="Directory for 3D radial-window audit outputs")
    radial_window_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this audit is intended for 41^3")
    radial_window_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    radial_window_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    radial_window_parser.add_argument("--radial-bins", type=int, default=24, help="Number of radial bins for shell-window profiles")
    radial_window_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    radial_window_parser.add_argument("--window-width", type=float, help="Physical width for each scanned shell window; defaults to near-shell-width-dx * dx")
    radial_window_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    radial_window_parser.add_argument(
        "--window-radii",
        type=float,
        nargs="+",
        default=[2.5, 3.5, 5.0, 6.5, 8.0, 10.0, 12.0],
        help="Inner radii of shell windows to scan",
    )

    defect_lift_parser = subparsers.add_parser(
        "prototype-3d-defect-lift-sweep",
        help="Run a tiny stronger/different-defect lift sweep against the neutral 3D shell-tail baseline",
    )
    defect_lift_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    defect_lift_parser.add_argument("--output-root", default="runs", help="Directory for 3D defect-lift sweep outputs")
    defect_lift_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this sweep is intended for 41^3")
    defect_lift_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    defect_lift_parser.add_argument("--sample-every", type=int, default=2, help="Sample interval for 3D metrics")
    defect_lift_parser.add_argument("--radial-bins", type=int, default=24, help="Number of radial bins for shell-window profiles")
    defect_lift_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    defect_lift_parser.add_argument("--window-width", type=float, help="Physical width for each scanned shell window; defaults to near-shell-width-dx * dx")
    defect_lift_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    defect_lift_parser.add_argument("--lift-threshold", type=float, default=1.5, help="Required lift threshold for retention and peak/work")
    defect_lift_parser.add_argument(
        "--max-profile-correlation-for-lift",
        type=float,
        default=0.95,
        help="Maximum radial or window-profile correlation allowed for a lifted defect to count as profile-different",
    )
    defect_lift_parser.add_argument("--min-retention", type=float, default=0.45, help="Minimum shell-window retention for a clean lifted window")
    defect_lift_parser.add_argument("--max-outer-ratio", type=float, default=2.0, help="Maximum outer/shell tail ratio for a clean lifted window")
    defect_lift_parser.add_argument("--max-radius-range", type=float, default=4.5, help="Maximum late-tail shell peak radius range for a clean lifted window")
    defect_lift_parser.add_argument(
        "--window-radii",
        type=float,
        nargs="+",
        default=[2.5, 3.5, 5.0, 6.5, 8.0, 10.0, 12.0],
        help="Inner radii of shell windows to scan",
    )

    interference_parser = subparsers.add_parser(
        "prototype-3d-interference-diagnostics",
        help="Run tiny neutral-lattice phase/interference diagnostics for the clean 3D shell-tail family",
    )
    interference_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    interference_parser.add_argument("--output-root", default="runs", help="Directory for 3D interference diagnostic outputs")
    interference_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this diagnostic is intended for 41^3")
    interference_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    interference_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval for 3D metrics")
    interference_parser.add_argument("--diagnostic-sample-every", type=int, default=20, help="Sample interval for phase/interference diagnostics")
    interference_parser.add_argument("--radial-bins", type=int, default=24, help="Number of radial bins for shell-window profiles")
    interference_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    interference_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    interference_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    interference_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    interference_parser.add_argument("--phase-offset", type=float, default=0.5 * 3.141592653589793, help="Global cubic phase offset control in radians")
    interference_parser.add_argument("--random-phase-seeds", type=int, nargs="+", default=[31092, 41092], help="Seeds for deterministic per-cell random boundary phase controls")

    standing_parser = subparsers.add_parser(
        "prototype-3d-standing-persistence",
        help="Run dense settled shell-pattern diagnostics for the two clean neutral cubic 3D variants",
    )
    standing_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    standing_parser.add_argument("--output-root", default="runs", help="Directory for 3D standing-persistence outputs")
    standing_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this confirmation is intended for 41^3")
    standing_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    standing_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval for base 3D metrics")
    standing_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for settled shell diagnostics")
    standing_parser.add_argument("--radial-bins", type=int, default=24, help="Number of radial bins for shell-window profiles")
    standing_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    standing_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    standing_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    standing_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    standing_parser.add_argument("--phase-offset", type=float, default=0.5 * 3.141592653589793, help="Global cubic phase offset control in radians")
    standing_parser.add_argument("--settle-after-cutoff", type=float, default=8.0, help="Delay after drive cutoff before standing metrics begin")
    standing_parser.add_argument("--node-quantile", type=float, default=0.20, help="Quantile used to identify settled node and antinode shell cells")
    standing_parser.add_argument("--min-standing-score", type=float, default=0.60, help="Minimum composite standing score for a pass")
    standing_parser.add_argument("--min-node-antinode-stability", type=float, default=0.55, help="Minimum node/antinode mask stability for a pass")
    standing_parser.add_argument("--min-frame-similarity", type=float, default=0.55, help="Minimum frame-to-mean and frame-to-frame shell similarity for a pass")
    standing_parser.add_argument("--min-phase-stability", type=float, default=0.25, help="Minimum settled shell phase stability for a pass")
    standing_parser.add_argument("--min-spectral-concentration", type=float, default=0.20, help="Minimum settled shell-energy spectral concentration for a pass")

    packet_parser = subparsers.add_parser(
        "prototype-3d-transport-packet-audit",
        help="Run motion/flux diagnostics for the clean neutral cubic 3D shell-window tail",
    )
    packet_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    packet_parser.add_argument("--output-root", default="runs", help="Directory for 3D transport-packet outputs")
    packet_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this audit is intended for 41^3")
    packet_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    packet_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval for base 3D metrics")
    packet_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for motion/flux diagnostics")
    packet_parser.add_argument("--radial-bins", type=int, default=32, help="Number of radial bins for packet tracking")
    packet_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    packet_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    packet_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    packet_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    packet_parser.add_argument("--phase-offset", type=float, default=0.5 * 3.141592653589793, help="Global cubic phase offset control in radians")
    packet_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    packet_parser.add_argument("--exit-threshold-fraction", type=float, default=0.15, help="Fraction of shell peak used to mark shell-window exit after the peak")
    packet_parser.add_argument("--exit-hold-samples", type=int, default=5, help="Consecutive below-threshold samples required to mark shell-window exit")
    packet_parser.add_argument("--max-lag-samples", type=int, default=80, help="Maximum lag count for shell-pattern correlation")
    packet_parser.add_argument("--min-abs-radial-group-velocity", type=float, default=0.05, help="Minimum radial group velocity magnitude for packet-like classification")
    packet_parser.add_argument("--min-directional-flux-fraction", type=float, default=0.60, help="Minimum inward or outward flux fraction for packet-like classification")
    packet_parser.add_argument("--max-stationary-radial-velocity", type=float, default=0.03, help="Maximum radial group velocity magnitude for modal-drift classification")
    packet_parser.add_argument("--min-phase-or-angular-drift-rate", type=float, default=0.02, help="Minimum phase or angular drift rate for modal-drift classification")

    lifecycle_parser = subparsers.add_parser(
        "prototype-3d-packet-lifecycle-audit",
        help="Run an extended lifecycle audit for the clean neutral cubic 3D transport packet",
    )
    lifecycle_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    lifecycle_parser.add_argument("--output-root", default="runs", help="Directory for 3D packet-lifecycle outputs")
    lifecycle_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this audit is intended for 41^3")
    lifecycle_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    lifecycle_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving the drive cutoff")
    lifecycle_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to the shared calibration options")
    lifecycle_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    lifecycle_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    lifecycle_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    lifecycle_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    lifecycle_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    lifecycle_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    lifecycle_parser.add_argument("--phase-offset", type=float, default=0.5 * 3.141592653589793, help="Global cubic phase offset control in radians")
    lifecycle_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    lifecycle_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    lifecycle_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    lifecycle_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Fraction of post-cutoff shell peak required for major lifecycle peaks")
    lifecycle_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    lifecycle_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    lifecycle_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    lifecycle_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    lifecycle_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")

    refocus_parser = subparsers.add_parser(
        "prototype-3d-refocusing-engineering-control",
        help="Run a tiny phase/cutoff/frequency refocusing-engineering control for the clean 3D packet",
    )
    refocus_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    refocus_parser.add_argument("--output-root", default="runs", help="Directory for 3D refocusing-engineering outputs")
    refocus_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this control is intended for 41^3")
    refocus_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    refocus_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving each variant cutoff")
    refocus_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to the shared calibration options")
    refocus_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for refocusing lifecycle diagnostics")
    refocus_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    refocus_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    refocus_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    refocus_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    refocus_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    refocus_parser.add_argument("--phase-offset", type=float, default=0.5 * 3.141592653589793, help="Reference global cubic phase offset in radians")
    refocus_parser.add_argument("--phase-delta", type=float, default=3.141592653589793 / 16.0, help="Small phase offset delta around the reference")
    refocus_parser.add_argument("--cutoff-delta", type=float, default=2.0, help="Small drive cutoff delta around the reference cutoff")
    refocus_parser.add_argument("--frequency-delta", type=float, default=0.02, help="Small drive frequency delta around the reference frequency")
    refocus_parser.add_argument("--no-chirp", action="store_true", help="Disable the optional low-to-high chirp variant")
    refocus_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    refocus_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    refocus_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    refocus_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Fraction of post-cutoff shell peak required for major lifecycle peaks")
    refocus_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    refocus_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    refocus_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    refocus_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    refocus_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")
    refocus_parser.add_argument("--min-retention-ratio", type=float, default=0.80, help="Minimum retention fraction versus phase-offset reference for clean variants")
    refocus_parser.add_argument("--max-outer-shell-ratio", type=float, default=2.25, help="Maximum tail outer/shell ratio for clean variants")
    refocus_parser.add_argument("--min-refocus-ratio-improvement", type=float, default=0.05, help="Minimum return-peak ratio lift for improvement")
    refocus_parser.add_argument("--min-exit-delay", type=float, default=2.0, help="Minimum exit-time delay for improvement")

    refocus_map_parser = subparsers.add_parser(
        "prototype-3d-refocusing-map-control",
        help="Run a tiny cutoff-frequency map around the clean 3D refocusing winners",
    )
    refocus_map_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    refocus_map_parser.add_argument("--output-root", default="runs", help="Directory for 3D refocusing-map outputs")
    refocus_map_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this control is intended for 41^3")
    refocus_map_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    refocus_map_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving each variant cutoff")
    refocus_map_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to shared calibration options")
    refocus_map_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    refocus_map_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    refocus_map_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    refocus_map_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    refocus_map_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    refocus_map_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    refocus_map_parser.add_argument("--phase-offset", type=float, default=0.5 * 3.141592653589793, help="Reference global cubic phase offset in radians")
    refocus_map_parser.add_argument("--cutoff-center", type=float, help="Winning cutoff center; defaults to base cutoff plus cutoff-delta")
    refocus_map_parser.add_argument("--cutoff-delta", type=float, default=2.0, help="Offset from base cutoff used when cutoff-center is omitted")
    refocus_map_parser.add_argument("--cutoff-step", type=float, default=1.0, help="Tiny cutoff step around the winning cutoff")
    refocus_map_parser.add_argument("--frequency-center", type=float, help="Winning frequency center; defaults to base frequency plus frequency-delta")
    refocus_map_parser.add_argument("--frequency-delta", type=float, default=0.02, help="Offset from base frequency used when frequency-center is omitted")
    refocus_map_parser.add_argument("--frequency-step", type=float, default=0.01, help="Tiny frequency step around the winning frequency")
    refocus_map_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    refocus_map_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    refocus_map_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    refocus_map_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Fraction of post-cutoff shell peak required for major lifecycle peaks")
    refocus_map_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    refocus_map_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    refocus_map_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    refocus_map_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    refocus_map_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")
    refocus_map_parser.add_argument("--min-retention-ratio", type=float, default=0.80, help="Minimum retention fraction versus cutoff_long reference for clean variants")
    refocus_map_parser.add_argument("--max-outer-shell-ratio", type=float, default=2.25, help="Maximum tail outer/shell ratio for generally clean variants")
    refocus_map_parser.add_argument("--strict-retention-target", type=float, default=0.30, help="Strict target for a strong constructive combined result")
    refocus_map_parser.add_argument("--strict-outer-shell-target", type=float, default=1.0, help="Strict outer/shell target for a strong constructive combined result")

    cutoff_phase_parser = subparsers.add_parser(
        "prototype-3d-cutoff-phase-map-control",
        help="Run a tiny cutoff release-phase map around the clean 3D refocusing packet",
    )
    cutoff_phase_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    cutoff_phase_parser.add_argument("--output-root", default="runs", help="Directory for 3D cutoff-phase map outputs")
    cutoff_phase_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this control is intended for 41^3")
    cutoff_phase_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    cutoff_phase_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving each variant cutoff")
    cutoff_phase_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to shared calibration options")
    cutoff_phase_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    cutoff_phase_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    cutoff_phase_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    cutoff_phase_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    cutoff_phase_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    cutoff_phase_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    cutoff_phase_parser.add_argument("--phase-offset", type=float, default=0.5 * 3.141592653589793, help="Reference global cubic phase offset in radians")
    cutoff_phase_parser.add_argument(
        "--release-phase-island-refinement",
        action="store_true",
        help="Use the tight passive cutoff/polarity preset around sign_flip_cutoff_minus_0p1",
    )
    cutoff_phase_parser.add_argument(
        "--phase-lock-needle-map",
        choices=("first", "tight"),
        help="Use the sign-flip-only ultra-fine cutoff preset around the provisional 17.94 needle",
    )
    cutoff_phase_parser.add_argument(
        "--threshold-robust-confirmation",
        action="store_true",
        help="Use the sign-flip-only 17.920-17.950 cutoff set for threshold-robust refocusing confirmation",
    )
    cutoff_phase_parser.add_argument("--sign-flip-only", action="store_true", help="Run only the sign-flip/polarity cutoff family")
    cutoff_phase_parser.add_argument("--reference-variant", help="Variant used as the comparison reference for classification")
    cutoff_phase_parser.add_argument("--cutoff-center", type=float, help="Winning cutoff center; defaults to base cutoff plus cutoff-delta")
    cutoff_phase_parser.add_argument("--cutoff-delta", type=float, default=2.0, help="Offset from base cutoff used when cutoff-center is omitted")
    cutoff_phase_parser.add_argument("--cutoff-offsets", type=float, nargs="+", default=[-1.0, -0.5, 0.0, 0.5, 1.0], help="Tiny cutoff offsets around the center")
    cutoff_phase_parser.add_argument("--phase-offset-deltas", type=float, nargs="+", default=[-3.141592653589793 / 16.0, 0.0, 3.141592653589793 / 16.0], help="Small global phase-offset deltas at the center cutoff")
    cutoff_phase_parser.add_argument("--no-polarity-family", action="store_true", help="Disable the compact sign-flip/polarity comparison family")
    cutoff_phase_parser.add_argument("--polarity-cutoff-offsets", type=float, nargs="+", default=[-0.5, 0.0, 0.5], help="Cutoff offsets for the compact sign-flip family")
    cutoff_phase_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    cutoff_phase_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    cutoff_phase_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    cutoff_phase_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Fraction of post-cutoff shell peak required for major lifecycle peaks")
    cutoff_phase_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    cutoff_phase_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    cutoff_phase_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    cutoff_phase_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    cutoff_phase_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")
    cutoff_phase_parser.add_argument("--min-retention-ratio", type=float, default=0.80, help="Minimum retention fraction versus cutoff reference for clean variants")
    cutoff_phase_parser.add_argument("--max-outer-shell-ratio", type=float, default=2.25, help="Maximum tail outer/shell ratio for clean variants")
    cutoff_phase_parser.add_argument("--strict-retention-target", type=float, default=0.30, help="Strict retention target for timing-island evidence")
    cutoff_phase_parser.add_argument("--strict-outer-shell-target", type=float, default=1.0, help="Strict outer/shell target for timing-island evidence")
    cutoff_phase_parser.add_argument("--timing-cluster-phase-tolerance-cycles", type=float, default=0.12, help="Max circular phase span for a timing-island cluster")

    resonator_layer_parser = subparsers.add_parser(
        "prototype-3d-resonator-layer-control",
        help="Run the narrow passive boundary-inner-edge resonator layer test around the 3D phase-lock cluster",
    )
    resonator_layer_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    resonator_layer_parser.add_argument("--output-root", default="runs", help="Directory for 3D resonator-layer outputs")
    resonator_layer_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this control is fixed at 41^3")
    resonator_layer_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    resonator_layer_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving each tested cutoff")
    resonator_layer_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to shared calibration options")
    resonator_layer_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle and energy diagnostics")
    resonator_layer_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    resonator_layer_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    resonator_layer_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    resonator_layer_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    resonator_layer_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    resonator_layer_parser.add_argument("--fixed-drive-frequency", type=float, default=0.92, help="Fixed sign-flip cubic drive frequency for the resonator test")
    resonator_layer_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    resonator_layer_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    resonator_layer_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    resonator_layer_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Default peak threshold; robust report also checks 0.25, 0.35, and 0.40")
    resonator_layer_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    resonator_layer_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    resonator_layer_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    resonator_layer_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    resonator_layer_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")

    release_phase_return_map_parser = subparsers.add_parser(
        "prototype-3d-release-phase-return-map",
        help="Build a read-only release-phase return-map predictor from existing 3D run artifacts",
    )
    release_phase_return_map_parser.add_argument(
        "--run-roots",
        type=Path,
        nargs="+",
        required=True,
        help="Existing run directories to analyze; no new physics simulations are run",
    )
    release_phase_return_map_parser.add_argument("--output-root", default="runs", help="Directory for release-phase return-map outputs")
    release_phase_return_map_parser.add_argument("--phase-bin-width", type=float, default=0.025, help="Release-phase bin width in cycles")
    release_phase_return_map_parser.add_argument("--strict-major-peak-target", type=int, default=9, help="Strict major-peak floor for conservative pass")
    release_phase_return_map_parser.add_argument("--strict-refocus-peak-target", type=int, default=8, help="Strict refocus-peak floor for conservative pass")
    release_phase_return_map_parser.add_argument("--default-top-major-target", type=int, default=11, help="Default-detector major-peak target for top-row marking")
    release_phase_return_map_parser.add_argument("--default-top-refocus-target", type=int, default=10, help="Default-detector refocus-peak target for top-row marking")
    release_phase_return_map_parser.add_argument("--strict-outer-shell-target", type=float, default=1.0, help="Maximum outer/shell ratio for conservative pass")

    release_phase_blind_parser = subparsers.add_parser(
        "prototype-3d-release-phase-blind-confirmation",
        help="Run the five-cutoff blind confirmation of the 3D release-phase predictor",
    )
    release_phase_blind_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    release_phase_blind_parser.add_argument("--cutoffs", type=float, nargs="+", required=True, help="Five predictor-recommended cutoffs to test without tuning")
    release_phase_blind_parser.add_argument("--output-root", default="runs", help="Directory for release-phase blind-confirmation outputs")
    release_phase_blind_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this confirmation is fixed at 41^3")
    release_phase_blind_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    release_phase_blind_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving each tested cutoff")
    release_phase_blind_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to shared calibration options")
    release_phase_blind_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    release_phase_blind_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    release_phase_blind_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    release_phase_blind_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    release_phase_blind_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    release_phase_blind_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    release_phase_blind_parser.add_argument("--fixed-drive-frequency", type=float, default=0.92, help="Fixed sign-flip cubic drive frequency")
    release_phase_blind_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    release_phase_blind_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    release_phase_blind_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    release_phase_blind_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Default peak threshold; strict checks use 0.35 and 0.40")
    release_phase_blind_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    release_phase_blind_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    release_phase_blind_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    release_phase_blind_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    release_phase_blind_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")

    release_phase_numerical_parser = subparsers.add_parser(
        "prototype-3d-release-phase-numerical-validation",
        help="Run baseline/half-dt numerical validation of the blind-confirmed 3D release-phase rule",
    )
    release_phase_numerical_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    release_phase_numerical_parser.add_argument("--cutoffs", type=float, nargs="+", required=True, help="Pre-registered cutoffs to validate at baseline and half dt")
    release_phase_numerical_parser.add_argument("--output-root", default="runs", help="Directory for release-phase numerical-validation outputs")
    release_phase_numerical_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this validation is fixed at 41^3")
    release_phase_numerical_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    release_phase_numerical_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving each tested cutoff")
    release_phase_numerical_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to shared calibration options")
    release_phase_numerical_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    release_phase_numerical_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    release_phase_numerical_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    release_phase_numerical_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    release_phase_numerical_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    release_phase_numerical_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    release_phase_numerical_parser.add_argument("--fixed-drive-frequency", type=float, default=0.92, help="Fixed sign-flip cubic drive frequency")
    release_phase_numerical_parser.add_argument("--include-quarter-dt", action="store_true", help="Also run quarter-dt rows; off by default because runtime roughly doubles the half-dt check")
    release_phase_numerical_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    release_phase_numerical_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    release_phase_numerical_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    release_phase_numerical_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Default peak threshold; strict checks use 0.35 and 0.40")
    release_phase_numerical_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    release_phase_numerical_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    release_phase_numerical_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    release_phase_numerical_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    release_phase_numerical_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")

    release_phase_dt_recenter_parser = subparsers.add_parser(
        "prototype-3d-release-phase-dt-recenter",
        help="Run the fixed half-dt release-phase recentering map around the surviving 3D phase row",
    )
    release_phase_dt_recenter_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    release_phase_dt_recenter_parser.add_argument("--output-root", default="runs", help="Directory for release-phase half-dt recentering outputs")
    release_phase_dt_recenter_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this control is fixed at 41^3")
    release_phase_dt_recenter_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    release_phase_dt_recenter_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving each tested cutoff")
    release_phase_dt_recenter_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to shared calibration options")
    release_phase_dt_recenter_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    release_phase_dt_recenter_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    release_phase_dt_recenter_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    release_phase_dt_recenter_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    release_phase_dt_recenter_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    release_phase_dt_recenter_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    release_phase_dt_recenter_parser.add_argument("--fixed-drive-frequency", type=float, default=0.92, help="Fixed sign-flip cubic drive frequency")
    release_phase_dt_recenter_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    release_phase_dt_recenter_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    release_phase_dt_recenter_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    release_phase_dt_recenter_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Default peak threshold; strict checks use 0.35 and 0.40")
    release_phase_dt_recenter_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    release_phase_dt_recenter_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    release_phase_dt_recenter_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    release_phase_dt_recenter_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    release_phase_dt_recenter_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")

    release_phase_proof_pack_parser = subparsers.add_parser(
        "prototype-3d-release-phase-proof-pack",
        help="Run the fixed quarter-dt proof pack for the passive release-phase rule",
    )
    release_phase_proof_pack_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    release_phase_proof_pack_parser.add_argument("--output-root", default="runs", help="Directory for release-phase proof-pack outputs")
    release_phase_proof_pack_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this proof pack is fixed at 41^3")
    release_phase_proof_pack_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    release_phase_proof_pack_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving each tested cutoff")
    release_phase_proof_pack_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to shared calibration options")
    release_phase_proof_pack_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    release_phase_proof_pack_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    release_phase_proof_pack_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    release_phase_proof_pack_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    release_phase_proof_pack_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    release_phase_proof_pack_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    release_phase_proof_pack_parser.add_argument("--fixed-drive-frequency", type=float, default=0.92, help="Fixed sign-flip cubic drive frequency")
    release_phase_proof_pack_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    release_phase_proof_pack_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    release_phase_proof_pack_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    release_phase_proof_pack_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Default peak threshold; strict checks use 0.35 and 0.40")
    release_phase_proof_pack_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    release_phase_proof_pack_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    release_phase_proof_pack_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    release_phase_proof_pack_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    release_phase_proof_pack_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")

    release_phase_resolution_lift_parser = subparsers.add_parser(
        "prototype-3d-release-phase-resolution-lift",
        help="Run one recalibrated 3D resolution lift for the passive release-phase rule",
    )
    release_phase_resolution_lift_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    release_phase_resolution_lift_parser.add_argument("--output-root", default="runs", help="Directory for release-phase resolution-lift outputs")
    release_phase_resolution_lift_parser.add_argument("--grid-size", type=int, default=51, help="Lift grid size; use 51 by default or 61 for one larger explicit check")
    release_phase_resolution_lift_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    release_phase_resolution_lift_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time while preserving each phase-targeted cutoff")
    release_phase_resolution_lift_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to shared calibration options")
    release_phase_resolution_lift_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    release_phase_resolution_lift_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    release_phase_resolution_lift_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured physical shell window")
    release_phase_resolution_lift_parser.add_argument("--shell-window-width", type=float, default=4.0, help="Physical width for the measured shell window")
    release_phase_resolution_lift_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Fallback shell-window width in dx units")
    release_phase_resolution_lift_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    release_phase_resolution_lift_parser.add_argument("--fixed-drive-frequency", type=float, default=0.92, help="Fixed sign-flip cubic drive frequency")
    release_phase_resolution_lift_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    release_phase_resolution_lift_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    release_phase_resolution_lift_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    release_phase_resolution_lift_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Default peak threshold; strict checks use 0.35 and 0.40")
    release_phase_resolution_lift_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    release_phase_resolution_lift_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    release_phase_resolution_lift_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    release_phase_resolution_lift_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    release_phase_resolution_lift_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")

    release_phase_resolution_postmortem_parser = subparsers.add_parser(
        "prototype-3d-release-phase-resolution-postmortem",
        help="Read-only postmortem comparing the 41^3 proof pack with the failed 51^3 release-phase lift",
    )
    release_phase_resolution_postmortem_parser.add_argument("--output-root", default="runs", help="Directory for release-phase resolution postmortem outputs")
    release_phase_resolution_postmortem_parser.add_argument("--proof-root", default=DEFAULT_PROOF_ROOT, help="Existing 41^3 proof-pack run root")
    release_phase_resolution_postmortem_parser.add_argument("--lift-root", default=DEFAULT_LIFT_ROOT, help="Existing 51^3 resolution-lift run root")
    release_phase_resolution_postmortem_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Default peak threshold used for comparison")
    release_phase_resolution_postmortem_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Refocus threshold used for comparison")
    release_phase_resolution_postmortem_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    release_phase_resolution_postmortem_parser.add_argument("--low-peak-threshold-fraction", type=float, default=0.20, help="Low threshold used to detect below-gate return humps")
    release_phase_resolution_postmortem_parser.add_argument("--strict-peak-threshold-fraction", type=float, default=0.40, help="Strict threshold used for shrinkage comparison")
    release_phase_resolution_postmortem_parser.add_argument("--radial-shift-predict-threshold", type=float, default=0.75, help="Required coherent radial shift before predicting a shell-window retry")
    release_phase_resolution_postmortem_parser.add_argument("--timing-shift-predict-threshold", type=float, default=0.75, help="Required coherent timing shift before predicting a cutoff retry")

    release_phase_modal_audit_parser = subparsers.add_parser(
        "prototype-3d-release-phase-modal-audit",
        help="Read-only modal audit comparing 41^3 proof, 51^3 blur, and central-burst contrast artifacts",
    )
    release_phase_modal_audit_parser.add_argument("--output-root", default="runs", help="Directory for release-phase modal-audit outputs")
    release_phase_modal_audit_parser.add_argument("--proof-root", default=DEFAULT_MODAL_PROOF_ROOT, help="Existing 41^3 proof-pack run root")
    release_phase_modal_audit_parser.add_argument("--lift-root", default=DEFAULT_MODAL_LIFT_ROOT, help="Existing 51^3 resolution-lift run root")
    release_phase_modal_audit_parser.add_argument("--postmortem-root", default=DEFAULT_MODAL_POSTMORTEM_ROOT, help="Existing release-phase resolution-postmortem run root")
    release_phase_modal_audit_parser.add_argument("--central-root", default=DEFAULT_MODAL_CENTRAL_ROOT, help="Existing central HF burst run root")
    release_phase_modal_audit_parser.add_argument("--same-band-relative-tolerance", type=float, default=0.16, help="Relative tolerance for considering proof/lift shell spectra the same modal band")
    release_phase_modal_audit_parser.add_argument("--min-strict-major-loss", type=float, default=1.0, help="Minimum strict major-peak loss needed for blur/finiteness classification")
    release_phase_modal_audit_parser.add_argument("--min-loose-recovery", type=float, default=1.0, help="Minimum loose-threshold recovery above strict counts needed for blur classification")
    release_phase_modal_audit_parser.add_argument("--blur-width-growth-threshold", type=float, default=0.03, help="Relative radial-width/spread growth threshold for blur classification")
    release_phase_modal_audit_parser.add_argument("--blur-bandwidth-growth-threshold", type=float, default=0.05, help="Relative spectral-bandwidth growth threshold for blur classification")
    release_phase_modal_audit_parser.add_argument("--blur-tail-radius-shift-threshold", type=float, default=0.40, help="Tail-radius shift threshold for blur classification")
    release_phase_modal_audit_parser.add_argument("--finite-grid-concentration-ratio", type=float, default=1.20, help="Proof/lift concentration ratio needed for finite-grid-resonance classification")

    release_phase_dispersion_audit_parser = subparsers.add_parser(
        "prototype-3d-release-phase-dispersion-audit",
        help="Read-only dispersion/blur model for 41^3 proof rows versus failed 51^3 lift rows",
    )
    release_phase_dispersion_audit_parser.add_argument("--output-root", default="runs", help="Directory for release-phase dispersion-audit outputs")
    release_phase_dispersion_audit_parser.add_argument("--config", default=DEFAULT_DISPERSION_CONFIG_PATH, help="Baseline config used only to reconstruct source/shell geometry")
    release_phase_dispersion_audit_parser.add_argument("--proof-root", default=DEFAULT_DISPERSION_PROOF_ROOT, help="Existing 41^3 proof-pack run root")
    release_phase_dispersion_audit_parser.add_argument("--lift-root", default=DEFAULT_DISPERSION_LIFT_ROOT, help="Existing 51^3 resolution-lift run root")
    release_phase_dispersion_audit_parser.add_argument("--postmortem-root", default=DEFAULT_DISPERSION_POSTMORTEM_ROOT, help="Existing release-phase resolution-postmortem run root")
    release_phase_dispersion_audit_parser.add_argument("--modal-root", default=DEFAULT_DISPERSION_MODAL_ROOT, help="Existing release-phase modal-audit run root")
    release_phase_dispersion_audit_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Reference grid used for fixed physical source width")
    release_phase_dispersion_audit_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Physical shell-window inner radius")
    release_phase_dispersion_audit_parser.add_argument("--shell-window-width", type=float, default=4.0, help="Physical shell-window width")
    release_phase_dispersion_audit_parser.add_argument("--same-band-relative-tolerance", type=float, default=0.16, help="Relative tolerance for considering proof/lift shell spectra the same modal band")
    release_phase_dispersion_audit_parser.add_argument("--min-strict-major-loss", type=float, default=1.0, help="Minimum strict major-peak loss needed for blur classification")
    release_phase_dispersion_audit_parser.add_argument("--min-loose-recovery", type=float, default=1.0, help="Minimum loose-threshold recovery above strict counts needed for blur classification")
    release_phase_dispersion_audit_parser.add_argument("--min-bandwidth-growth", type=float, default=0.05, help="Minimum relative bandwidth growth needed for blur classification")
    release_phase_dispersion_audit_parser.add_argument("--min-tail-radius-shift", type=float, default=0.40, help="Minimum tail-radius shift needed for blur classification")
    release_phase_dispersion_audit_parser.add_argument("--max-lift-bandwidth-cv", type=float, default=0.02, help="Maximum 51^3 bandwidth CV for a predictable blur model")
    release_phase_dispersion_audit_parser.add_argument("--max-lift-tail-radius-cv", type=float, default=0.04, help="Maximum 51^3 tail-radius CV for a predictable blur model")

    spatial_phase_parser = subparsers.add_parser(
        "prototype-3d-spatial-phase-instrumentation",
        help="Instrumentation-only reproduction of the 41^3 proof row and failed 51^3 lift candidate with shell phase frames",
    )
    spatial_phase_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for fixed-domain lattice constants")
    spatial_phase_parser.add_argument("--output-root", default="runs", help="Directory for spatial-phase instrumentation outputs")
    spatial_phase_parser.add_argument("--proof-grid-size", type=int, default=41, help="Frozen proof-row grid size")
    spatial_phase_parser.add_argument("--lift-grid-size", type=int, default=51, help="Frozen failed-lift candidate grid size")
    spatial_phase_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define fixed physical source-layer width")
    spatial_phase_parser.add_argument("--physical-duration", type=float, default=96.0, help="Physical end time for reproductions")
    spatial_phase_parser.add_argument("--sample-every", type=int, default=10, help="Compatibility sampling interval")
    spatial_phase_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense lifecycle/sample interval")
    spatial_phase_parser.add_argument("--radial-bins", type=int, default=40, help="Number of lifecycle radial bins")
    spatial_phase_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Physical shell-window inner radius")
    spatial_phase_parser.add_argument("--shell-window-width", type=float, default=4.0, help="Physical shell-window width")
    spatial_phase_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Fallback shell-window width in dx units")
    spatial_phase_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    spatial_phase_parser.add_argument("--target-work-per-source-area", type=float, help="Override matched work per physical source area")
    spatial_phase_parser.add_argument("--fixed-drive-frequency", type=float, default=0.92, help="Fixed sign-flip cubic drive frequency")
    spatial_phase_parser.add_argument("--proof-cutoff", type=float, default=17.94, help="Frozen 41^3 proof-row cutoff")
    spatial_phase_parser.add_argument("--lift-target-release-phase", type=float, default=0.5071, help="Frozen 51^3 failed-lift target release phase")
    spatial_phase_parser.add_argument("--dt-scale", type=float, default=0.25, help="dt scale for both reproductions")
    spatial_phase_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first arrival")
    spatial_phase_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit")
    spatial_phase_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required for exit")
    spatial_phase_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Default event peak threshold")
    spatial_phase_parser.add_argument("--frame-peak-threshold-fraction", type=float, default=0.20, help="Loose threshold used only for storing spatial return frames")
    spatial_phase_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first peak required for refocus peaks")
    spatial_phase_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between return peaks")
    spatial_phase_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    spatial_phase_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    spatial_phase_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")
    spatial_phase_parser.add_argument("--max-return-frames", type=int, default=12, help="Maximum loose return-peak frames to export per reproduction")
    spatial_phase_parser.add_argument("--radial-phase-bins", type=int, default=12, help="Number of radial shell phase bins")
    spatial_phase_parser.add_argument("--angular-theta-bins", type=int, default=8, help="Number of azimuth bins for spherical shell phase coherence")
    spatial_phase_parser.add_argument("--angular-polar-bins", type=int, default=4, help="Number of polar bins for spherical shell phase coherence")
    spatial_phase_parser.add_argument("--coherence-drop-threshold", type=float, default=0.12, help="Shell coherence drop threshold for decoherence classification")
    spatial_phase_parser.add_argument("--radial-coherence-drop-threshold", type=float, default=0.12, help="Radial coherence drop threshold for decoherence classification")
    spatial_phase_parser.add_argument("--angular-coherence-drop-threshold", type=float, default=0.12, help="Angular coherence drop threshold for decoherence classification")
    spatial_phase_parser.add_argument("--node-stability-drop-threshold", type=float, default=0.10, help="Node/antinode stability drop threshold")
    spatial_phase_parser.add_argument("--width-growth-threshold", type=float, default=0.15, help="Relative return-spread growth threshold for coherent blur")
    spatial_phase_parser.add_argument("--center-shift-threshold", type=float, default=0.40, help="Radial center shift threshold for shell-window alignment classification")

    precomp_design_parser = subparsers.add_parser(
        "prototype-3d-spatial-phase-precompensation-design",
        help="Read-only low-dimensional phase-precompensation design from captured spatial phase frames",
    )
    precomp_design_parser.add_argument("--output-root", default="runs", help="Directory for phase-precompensation design outputs")
    precomp_design_parser.add_argument("--spatial-phase-root", default=DEFAULT_PRECOMP_SPATIAL_PHASE_ROOT, help="Existing spatial phase instrumentation run root")
    precomp_design_parser.add_argument("--angular-harmonic-m", type=int, default=4, help="Simple angular harmonic order allowed in the low-dimensional correction")
    precomp_design_parser.add_argument("--ridge-lambda", type=float, default=0.01, help="Ridge regularization used for the low-dimensional phase-error fit")
    precomp_design_parser.add_argument("--min-matched-sector-samples", type=int, default=96, help="Minimum matched shell-sector phase samples")
    precomp_design_parser.add_argument("--min-model-r2", type=float, default=0.12, help="Minimum low-dimensional model R2 for candidate support")
    precomp_design_parser.add_argument("--max-peak-global-phase-std", type=float, default=0.35, help="Maximum per-return global phase-error std for temporal stability")
    precomp_design_parser.add_argument("--max-global-phase-offset", type=float, default=0.35, help="Maximum safe global phase offset in radians")
    precomp_design_parser.add_argument("--max-face-phase-offset", type=float, default=0.25, help="Maximum safe per-face phase offset in radians")
    precomp_design_parser.add_argument("--max-cubic-multiplier-delta", type=float, default=0.20, help="Maximum safe cubic strength multiplier delta")
    precomp_design_parser.add_argument("--max-angular-harmonic-amplitude", type=float, default=0.25, help="Maximum safe angular harmonic phase amplitude in radians")
    precomp_design_parser.add_argument("--max-release-phase-nudge", type=float, default=0.004, help="Maximum safe release-phase nudge in cycles")
    precomp_design_parser.add_argument("--baseline-cubic-sign", type=float, default=-1.0, help="Baseline sign-flip cubic sign")
    precomp_design_parser.add_argument("--baseline-drive-frequency", type=float, default=0.92, help="Baseline drive frequency")
    precomp_design_parser.add_argument("--baseline-target-release-phase", type=float, default=0.5071, help="Baseline 51^3 target release phase")
    precomp_design_parser.add_argument("--baseline-cutoff", type=float, default=17.9425, help="Baseline 51^3 failed-lift cutoff")

    source_spectrum_parser = subparsers.add_parser(
        "prototype-3d-source-spectrum-design-audit",
        help="Read-only source-spectrum audit for a possible smooth-envelope 51^3 candidate",
    )
    source_spectrum_parser.add_argument("--output-root", default="runs", help="Directory for source-spectrum design audit outputs")
    source_spectrum_parser.add_argument("--config", dest="config_path", default=DEFAULT_SOURCE_SPECTRUM_CONFIG_PATH, help="Baseline JSON SimulationConfig")
    source_spectrum_parser.add_argument("--dispersion-root", default=DEFAULT_SOURCE_SPECTRUM_DISPERSION_ROOT, help="Existing release-phase dispersion audit root")
    source_spectrum_parser.add_argument("--spatial-phase-root", default=DEFAULT_SOURCE_SPECTRUM_SPATIAL_ROOT, help="Existing spatial phase instrumentation root")
    source_spectrum_parser.add_argument("--precomp-root", default=DEFAULT_SOURCE_SPECTRUM_PRECOMP_ROOT, help="Existing phase-precompensation design root")
    source_spectrum_parser.add_argument("--physical-duration", type=float, default=96.0, help="Physical duration used for source-spectrum zero padding")
    source_spectrum_parser.add_argument("--dt-scale", type=float, default=0.25, help="dt scale used by the proof/lift source comparison")
    source_spectrum_parser.add_argument("--proof-cutoff", type=float, default=17.94, help="41^3 proof-row cutoff")
    source_spectrum_parser.add_argument("--lift-cutoff", type=float, default=17.9425, help="51^3 failed-lift cutoff")
    source_spectrum_parser.add_argument("--drive-frequency", type=float, help="Override carrier frequency; defaults to config driver frequency")
    source_spectrum_parser.add_argument("--phase-cycle-index", type=int, default=16, help="Reference release-phase cycle index")
    source_spectrum_parser.add_argument("--far-sideband-multiplier", type=float, default=2.0, help="Far-sideband threshold in multiples of 1/cutoff")
    source_spectrum_parser.add_argument("--min-modal-bandwidth-growth", type=float, default=0.05, help="Minimum observed modal bandwidth growth for support")
    source_spectrum_parser.add_argument("--min-spatial-coherence-drop", type=float, default=0.10, help="Minimum spatial coherence drop for support")
    source_spectrum_parser.add_argument("--min-current-far-sideband-fraction", type=float, default=0.01, help="Minimum hard-window far-sideband fraction for support")
    source_spectrum_parser.add_argument("--min-smoothing-sideband-reduction", type=float, default=0.50, help="Minimum theoretical sideband reduction for support")
    source_spectrum_parser.add_argument("--max-smooth-bandwidth-ratio", type=float, default=1.05, help="Maximum smooth/hard source bandwidth ratio for support")

    central_burst_parser = subparsers.add_parser(
        "prototype-3d-central-burst-control",
        aliases=["central-hf-scattering-branch"],
        help="Run the firewalled 3D central high-frequency burst scattering branch",
    )
    central_burst_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for fixed-domain lattice constants")
    central_burst_parser.add_argument("--output-root", default="runs", help="Directory for central-burst outputs")
    central_burst_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; first pass is fixed at 41^3")
    central_burst_parser.add_argument("--physical-duration", type=float, default=96.0, help="Physical end time for post-burst return tracking")
    central_burst_parser.add_argument("--sample-every", type=int, default=10, help="Compatibility sampling interval")
    central_burst_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    central_burst_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    central_burst_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    central_burst_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    central_burst_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Fallback shell-window width in dx units")
    central_burst_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    central_burst_parser.add_argument("--burst-duration", type=float, default=6.0, help="Duration of the central velocity burst")
    central_burst_parser.add_argument("--burst-radius", type=float, default=1.0, help="Physical radius of the tiny central burst mask")
    central_burst_parser.add_argument("--frequencies", type=float, nargs="+", default=[0.92, 1.84, 3.68, 5.52, 7.36], help="Central-burst frequency ladder")
    central_burst_parser.add_argument("--energy-labels", nargs="+", default=["low", "medium", "high", "extreme"], help="Energy-ladder labels")
    central_burst_parser.add_argument("--burst-acceleration-scales", type=float, nargs="+", default=[0.05, 0.15, 0.35, 0.75], help="Velocity-kick acceleration scales for the energy ladder")
    central_burst_parser.add_argument("--no-half-dt-check", action="store_true", help="Disable the automatic half-dt check of the best baseline row")
    central_burst_parser.add_argument("--event-thresholds", type=float, nargs="+", default=[0.25, 0.30, 0.35, 0.40], help="Peak thresholds used for event-count sensitivity")
    central_burst_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Default peak threshold")
    central_burst_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    central_burst_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    central_burst_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    central_burst_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    central_burst_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")

    second_pulse_parser = subparsers.add_parser(
        "prototype-3d-second-pulse-control",
        help="Run a tiny timed second-pulse control from the best 3D release phase",
    )
    second_pulse_parser.add_argument("--config", type=Path, required=True, help="JSON SimulationConfig for the 2D baseline candidate")
    second_pulse_parser.add_argument("--output-root", default="runs", help="Directory for 3D second-pulse outputs")
    second_pulse_parser.add_argument("--grid-size", type=int, default=41, help="3D grid size; this control is intended for 41^3")
    second_pulse_parser.add_argument("--reference-source-grid-size", type=int, default=31, help="Grid size used to define the fixed physical source-layer width")
    second_pulse_parser.add_argument("--physical-duration", type=float, default=96.0, help="Extended physical end time")
    second_pulse_parser.add_argument("--sample-every", type=int, default=10, help="Sample interval passed to shared calibration options")
    second_pulse_parser.add_argument("--diagnostic-sample-every", type=int, default=4, help="Dense sample interval for lifecycle diagnostics")
    second_pulse_parser.add_argument("--radial-bins", type=int, default=40, help="Number of radial bins for packet radius/width tracking")
    second_pulse_parser.add_argument("--shell-window-radius", type=float, default=5.0, help="Inner radius of the measured shell window")
    second_pulse_parser.add_argument("--shell-window-width", type=float, help="Physical width for the measured shell window; defaults to near-shell-width-dx * dx")
    second_pulse_parser.add_argument("--near-shell-width-dx", type=float, default=4.0, help="Default shell-window width in dx units")
    second_pulse_parser.add_argument("--sponge-strength-multiplier", type=float, default=3.0, help="Sponge strength multiplier versus the original 3D sponge")
    second_pulse_parser.add_argument("--reference-variant", default="sign_flip_cutoff_minus_0p1", help="Variant name to read from the cutoff-phase events CSV")
    second_pulse_parser.add_argument("--reference-events-csv", default="runs/cutoff_phase_map_3d_20260619_104211/cutoff_phase_map_events.csv", help="Cutoff-phase events CSV used to choose refocus timing")
    second_pulse_parser.add_argument("--reference-cutoff-time", type=float, default=17.9, help="Best first-pulse release cutoff")
    second_pulse_parser.add_argument("--reference-release-phase-cycles", type=float, default=0.468, help="Best first-pulse release phase in cycles")
    second_pulse_parser.add_argument("--second-pulse-duration", type=float, default=2.0, help="Duration of each second pulse")
    second_pulse_parser.add_argument("--second-pulse-amplitude-scale", type=float, default=1.0, help="Amplitude scale applied only to second-pulse variants")
    second_pulse_parser.add_argument("--second-pulse-amplitude-scales", type=float, nargs="+", help="Run a reduced-work map over multiple second-pulse amplitude scales")
    second_pulse_parser.add_argument("--second-pulse-durations", type=float, nargs="+", help="Run a reduced-work map over multiple second-pulse durations")
    second_pulse_parser.add_argument(
        "--second-pulse-roles",
        nargs="+",
        default=["first_refocus", "preload_first_refocus", "second_refocus", "opposite_polarity", "phase_matched", "phase_offset_control"],
        help="Second-pulse roles to include in reduced-work maps",
    )
    second_pulse_parser.add_argument("--second-pulse-micro-map", action="store_true", help="Run a travel-time-adjusted second-pulse timing/phase micro-map")
    second_pulse_parser.add_argument("--micro-map-targets", nargs="+", default=["first_refocus"], help="Shell peaks to target in micro-map mode: first_peak, first_refocus, second_refocus")
    second_pulse_parser.add_argument("--launch-time-offsets", type=float, nargs="+", default=[-0.8, -0.4, 0.0, 0.4, 0.8], help="Offsets around target_time - boundary_to_shell_travel_time for micro-map launches")
    second_pulse_parser.add_argument("--second-pulse-phase-modes", nargs="+", default=["matched", "opposite", "plus_pi_4", "minus_pi_4"], help="Micro-map phase modes: matched, opposite, plus_pi_4, minus_pi_4")
    second_pulse_parser.add_argument("--boundary-to-shell-travel-time", type=float, help="Override empirical boundary-to-shell travel time for second-pulse micro-map")
    second_pulse_parser.add_argument("--preload-time", type=float, default=1.0, help="How far before first refocus to center the preload pulse")
    second_pulse_parser.add_argument("--phase-offset-control", type=float, default=0.5 * 3.141592653589793, help="Global phase offset for the phase-offset second-pulse control")
    second_pulse_parser.add_argument("--arrival-threshold-fraction", type=float, default=0.10, help="Fraction of shell peak used to mark first meaningful shell arrival")
    second_pulse_parser.add_argument("--exit-threshold-fraction", type=float, default=0.12, help="Fraction of shell peak used to mark shell-window exit after the peak")
    second_pulse_parser.add_argument("--exit-hold-samples", type=int, default=10, help="Consecutive below-threshold samples required to mark shell-window exit")
    second_pulse_parser.add_argument("--peak-threshold-fraction", type=float, default=0.30, help="Fraction of post-cutoff shell peak required for major lifecycle peaks")
    second_pulse_parser.add_argument("--refocus-threshold-fraction", type=float, default=0.35, help="Fraction of first major peak required for later refocus peaks")
    second_pulse_parser.add_argument("--min-peak-separation-time", type=float, default=5.0, help="Minimum time separation between major lifecycle peaks")
    second_pulse_parser.add_argument("--min-refocus-count", type=int, default=2, help="Minimum major-peak count for repeated-refocusing classification")
    second_pulse_parser.add_argument("--min-width-growth-fraction", type=float, default=0.30, help="Minimum tail width/spread growth for diffusive classification")
    second_pulse_parser.add_argument("--min-decay-rate-magnitude", type=float, default=0.01, help="Minimum post-peak log decay-rate magnitude for diffusive classification")
    second_pulse_parser.add_argument("--max-outer-shell-ratio", type=float, default=1.0, help="Maximum outer/shell tail ratio for a clean second-pulse variant")
    second_pulse_parser.add_argument("--min-retention-gain", type=float, default=0.0, help="Minimum retention gain over the no-pulse reference")
    second_pulse_parser.add_argument("--min-refocus-gain", type=int, default=1, help="Minimum refocus-count gain over the no-pulse reference")

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

    if args.command == "transport-controls":
        config = _load_sim_config(args.config)
        result = run_transport_controls(
            config,
            options=TransportControlOptions(
                output_root=args.output_root,
                frame_interval=args.frame_interval,
                window_steps=args.window_steps,
                source_normalization=args.source_normalization,
                reference_grid_size=args.grid_size,
                min_peak_separation=args.min_peak_separation,
                boundary_match_mode=args.boundary_match_mode,
                boundary_only=args.boundary_only,
            ),
            reference_root=args.reference_root,
        )
        _print_transport_control_summary(result)
        return

    if args.command == "prototype-3d":
        config = _load_sim_config(args.config)
        result = run_3d_prototype(
            config,
            options=Prototype3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                sample_every=args.sample_every,
                include_dt_control=not args.skip_dt_control,
                include_sponge_control=not args.skip_sponge_control,
            ),
        )
        _print_3d_prototype_summary(result)
        return

    if args.command == "prototype-3d-audit":
        config = _load_sim_config(args.config)
        result = run_3d_failure_audit(
            args.run_path,
            config,
            options=Prototype3DFailureAuditOptions(
                output_dir=args.output_dir,
                radial_bins=args.radial_bins,
                near_shell_width_dx=args.near_shell_width_dx,
            ),
        )
        _print_3d_failure_audit_summary(result)
        return

    if args.command == "prototype-3d-source-sponge-control":
        config = _load_sim_config(args.config)
        result = run_3d_source_sponge_control(
            config,
            options=SourceSpongeControlOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                sample_every=args.sample_every,
                gap_cells_from_sponge=args.gap_cells_from_sponge,
                near_shell_width_dx=args.near_shell_width_dx,
            ),
        )
        _print_3d_source_sponge_control_summary(result)
        return

    if args.command == "prototype-3d-sponge-strength-control":
        config = _load_sim_config(args.config)
        result = run_3d_sponge_strength_control(
            config,
            options=SpongeStrengthControlOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                sample_every=args.sample_every,
                near_shell_width_dx=args.near_shell_width_dx,
                weak_sponge_multiplier=args.weak_sponge_multiplier,
                stronger_sponge_multiplier=args.stronger_sponge_multiplier,
                wider_sponge_multiplier=args.wider_sponge_multiplier,
            ),
        )
        _print_3d_sponge_strength_control_summary(result)
        return

    if args.command == "prototype-3d-source-geometry-control":
        config = _load_sim_config(args.config)
        result = run_3d_source_geometry_control(
            config,
            options=SourceGeometryControlOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                sample_every=args.sample_every,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                random_phase_seed=args.random_phase_seed,
            ),
        )
        _print_3d_source_geometry_control_summary(result)
        return

    if args.command == "prototype-3d-cubic-focus-control":
        config = _load_sim_config(args.config)
        result = run_3d_cubic_focus_control(
            config,
            options=CubicFocusControlOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                sample_every=args.sample_every,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                phase_offset=args.phase_offset,
                imbalance_scale=args.imbalance_scale,
                second_imbalance_scale=args.second_imbalance_scale,
                random_phase_seed=args.random_phase_seed,
            ),
        )
        _print_3d_cubic_focus_control_summary(result)
        return

    if args.command == "prototype-3d-cubic-confirmation-control":
        config = _load_sim_config(args.config)
        result = run_3d_cubic_confirmation_control(
            config,
            options=CubicConfirmationControlOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                sample_every=args.sample_every,
                near_shell_width_dx=args.near_shell_width_dx,
                base_sponge_strength_multiplier=args.base_sponge_strength_multiplier,
                weak_sponge_relative_multiplier=args.weak_sponge_relative_multiplier,
                stronger_sponge_relative_multiplier=args.stronger_sponge_relative_multiplier,
                half_dt_multiplier=args.half_dt_multiplier,
                amplitude_reduction_multiplier=args.amplitude_reduction_multiplier,
            ),
        )
        _print_3d_cubic_confirmation_control_summary(result)
        return

    if args.command == "prototype-3d-grid-confirmation-control":
        config = _load_sim_config(args.config)
        result = run_3d_grid_confirmation_control(
            config,
            options=GridConfirmation3DOptions(
                output_root=args.output_root,
                baseline_grid_size=args.baseline_grid_size,
                refined_grid_size=args.refined_grid_size,
                sample_every=args.sample_every,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                include_original_cubic_41=not args.skip_original_cubic_41,
                negative_control=args.negative_control,
            ),
        )
        _print_3d_grid_confirmation_control_summary(result)
        return

    if args.command == "prototype-3d-threshold-control":
        config = _load_sim_config(args.config)
        amplitude_multipliers = (0.5, 0.75, 1.0, 1.25) if args.skip_amp_1_5 else (0.5, 0.75, 1.0, 1.25, 1.5)
        result = run_3d_threshold_control(
            config,
            options=ThresholdControl3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                sample_every=args.sample_every,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                amplitude_multipliers=amplitude_multipliers,
                include_direct_core=not args.skip_direct_core,
                include_direct_shell=not args.skip_direct_shell,
            ),
        )
        _print_3d_threshold_control_summary(result)
        return

    if args.command == "prototype-3d-defect-control":
        config = _load_sim_config(args.config)
        result = run_3d_defect_control(
            config,
            options=DefectControl3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                sample_every=args.sample_every,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                smaller_radius_multiplier=args.smaller_radius_multiplier,
                larger_radius_multiplier=args.larger_radius_multiplier,
            ),
        )
        _print_3d_defect_control_summary(result)
        return

    if args.command == "prototype-3d-radial-window-audit":
        config = _load_sim_config(args.config)
        result = run_3d_radial_window_audit(
            config,
            options=RadialWindowAudit3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                window_radii=tuple(args.window_radii),
                window_width=args.window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
            ),
        )
        _print_3d_radial_window_audit_summary(result)
        return

    if args.command == "prototype-3d-defect-lift-sweep":
        config = _load_sim_config(args.config)
        result = run_3d_defect_lift_sweep(
            config,
            options=DefectLiftSweep3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                sample_every=args.sample_every,
                radial_bins=args.radial_bins,
                window_radii=tuple(args.window_radii),
                window_width=args.window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                min_retention=args.min_retention,
                max_outer_ratio=args.max_outer_ratio,
                max_radius_range=args.max_radius_range,
                lift_threshold=args.lift_threshold,
                max_profile_correlation_for_lift=args.max_profile_correlation_for_lift,
            ),
        )
        _print_3d_defect_lift_sweep_summary(result)
        return

    if args.command == "prototype-3d-interference-diagnostics":
        config = _load_sim_config(args.config)
        result = run_3d_interference_diagnostics(
            config,
            options=InterferenceDiagnostics3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                sample_every=args.sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                phase_offset=args.phase_offset,
                random_phase_seeds=tuple(args.random_phase_seeds),
            ),
        )
        _print_3d_interference_diagnostics_summary(result)
        return

    if args.command == "prototype-3d-standing-persistence":
        config = _load_sim_config(args.config)
        result = run_3d_standing_persistence_control(
            config,
            options=StandingPersistence3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                phase_offset=args.phase_offset,
                settle_after_cutoff=args.settle_after_cutoff,
                node_quantile=args.node_quantile,
                min_standing_score=args.min_standing_score,
                min_node_antinode_stability=args.min_node_antinode_stability,
                min_frame_similarity=args.min_frame_similarity,
                min_phase_stability=args.min_phase_stability,
                min_spectral_concentration=args.min_spectral_concentration,
            ),
        )
        _print_3d_standing_persistence_summary(result)
        return

    if args.command == "prototype-3d-transport-packet-audit":
        config = _load_sim_config(args.config)
        result = run_3d_transport_packet_audit(
            config,
            options=TransportPacket3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                phase_offset=args.phase_offset,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                max_lag_samples=args.max_lag_samples,
                min_abs_radial_group_velocity=args.min_abs_radial_group_velocity,
                min_directional_flux_fraction=args.min_directional_flux_fraction,
                max_stationary_radial_velocity=args.max_stationary_radial_velocity,
                min_phase_or_angular_drift_rate=args.min_phase_or_angular_drift_rate,
            ),
        )
        _print_3d_transport_packet_summary(result)
        return

    if args.command == "prototype-3d-packet-lifecycle-audit":
        config = _load_sim_config(args.config)
        result = run_3d_packet_lifecycle_audit(
            config,
            options=PacketLifecycle3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                phase_offset=args.phase_offset,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
            ),
        )
        _print_3d_packet_lifecycle_summary(result)
        return

    if args.command == "prototype-3d-refocusing-engineering-control":
        config = _load_sim_config(args.config)
        result = run_3d_refocusing_engineering_control(
            config,
            options=RefocusingEngineering3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                phase_offset=args.phase_offset,
                phase_delta=args.phase_delta,
                cutoff_delta=args.cutoff_delta,
                frequency_delta=args.frequency_delta,
                include_chirp=not args.no_chirp,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
                min_retention_ratio=args.min_retention_ratio,
                max_outer_shell_ratio=args.max_outer_shell_ratio,
                min_refocus_ratio_improvement=args.min_refocus_ratio_improvement,
                min_exit_delay=args.min_exit_delay,
            ),
        )
        _print_3d_refocusing_engineering_summary(result)
        return

    if args.command == "prototype-3d-refocusing-map-control":
        config = _load_sim_config(args.config)
        result = run_3d_refocusing_map_control(
            config,
            options=RefocusingMap3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                phase_offset=args.phase_offset,
                cutoff_center=args.cutoff_center,
                cutoff_delta=args.cutoff_delta,
                cutoff_step=args.cutoff_step,
                frequency_center=args.frequency_center,
                frequency_delta=args.frequency_delta,
                frequency_step=args.frequency_step,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
                min_retention_ratio=args.min_retention_ratio,
                max_outer_shell_ratio=args.max_outer_shell_ratio,
                strict_retention_target=args.strict_retention_target,
                strict_outer_shell_target=args.strict_outer_shell_target,
            ),
        )
        _print_3d_refocusing_map_summary(result)
        return

    if args.command == "prototype-3d-cutoff-phase-map-control":
        config = _load_sim_config(args.config)
        refinement_offsets = (-0.16, -0.14, -0.12, -0.10, -0.08, -0.06, -0.04)
        cutoff_offsets = tuple(args.cutoff_offsets)
        phase_offsets = tuple(args.phase_offset_deltas)
        polarity_cutoff_offsets = tuple(args.polarity_cutoff_offsets)
        reference_variant = args.reference_variant or "phase_offset_cutoff_reference"
        include_phase_offset_family = not args.sign_flip_only
        if args.release_phase_island_refinement:
            cutoff_offsets = refinement_offsets
            phase_offsets = (0.0,)
            polarity_cutoff_offsets = refinement_offsets
            reference_variant = args.reference_variant or "sign_flip_cutoff_minus_0p1"
        if args.phase_lock_needle_map:
            needle_offsets = {
                "first": (-0.075, -0.070, -0.065, -0.060, -0.055, -0.050, -0.045),
                "tight": (-0.066, -0.064, -0.062, -0.060, -0.058, -0.056, -0.054),
            }[args.phase_lock_needle_map]
            cutoff_offsets = ()
            phase_offsets = (0.0,)
            polarity_cutoff_offsets = needle_offsets
            include_phase_offset_family = False
            reference_variant = args.reference_variant or "sign_flip_cutoff_minus_0p06"
        if args.threshold_robust_confirmation:
            cutoff_offsets = ()
            phase_offsets = (0.0,)
            polarity_cutoff_offsets = (-0.080, -0.075, -0.070, -0.065, -0.060, -0.055, -0.050)
            include_phase_offset_family = False
            reference_variant = args.reference_variant or "sign_flip_cutoff_minus_0p07"
        result = run_3d_cutoff_phase_map_control(
            config,
            options=CutoffPhaseMap3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                phase_offset=args.phase_offset,
                reference_variant=reference_variant,
                cutoff_center=args.cutoff_center,
                cutoff_delta=args.cutoff_delta,
                cutoff_offsets=cutoff_offsets,
                phase_offsets=phase_offsets,
                include_phase_offset_family=include_phase_offset_family,
                include_polarity_family=not args.no_polarity_family,
                polarity_cutoff_offsets=polarity_cutoff_offsets,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
                min_retention_ratio=args.min_retention_ratio,
                max_outer_shell_ratio=args.max_outer_shell_ratio,
                strict_retention_target=args.strict_retention_target,
                strict_outer_shell_target=args.strict_outer_shell_target,
                timing_cluster_phase_tolerance_cycles=args.timing_cluster_phase_tolerance_cycles,
            ),
        )
        _print_3d_cutoff_phase_map_summary(result)
        return

    if args.command == "prototype-3d-resonator-layer-control":
        config = _load_sim_config(args.config)
        result = run_3d_resonator_layer_control(
            config,
            options=ResonatorLayer3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                fixed_drive_frequency=args.fixed_drive_frequency,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
            ),
        )
        _print_3d_resonator_layer_summary(result)
        return

    if args.command == "prototype-3d-release-phase-return-map":
        result = run_3d_release_phase_return_map(
            list(args.run_roots),
            options=ReleasePhaseReturnMapOptions(
                output_root=args.output_root,
                phase_bin_width=args.phase_bin_width,
                strict_major_peak_target=args.strict_major_peak_target,
                strict_refocus_peak_target=args.strict_refocus_peak_target,
                default_top_major_target=args.default_top_major_target,
                default_top_refocus_target=args.default_top_refocus_target,
                strict_outer_shell_target=args.strict_outer_shell_target,
            ),
        )
        _print_3d_release_phase_return_map_summary(result)
        return

    if args.command == "prototype-3d-release-phase-blind-confirmation":
        config = _load_sim_config(args.config)
        result = run_3d_release_phase_blind_confirmation(
            config,
            options=ReleasePhaseBlindConfirmationOptions(
                output_root=args.output_root,
                cutoffs=tuple(args.cutoffs),
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                fixed_drive_frequency=args.fixed_drive_frequency,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
            ),
        )
        _print_3d_release_phase_blind_confirmation_summary(result)
        return

    if args.command == "prototype-3d-release-phase-numerical-validation":
        config = _load_sim_config(args.config)
        result = run_3d_release_phase_numerical_validation(
            config,
            options=ReleasePhaseNumericalValidationOptions(
                output_root=args.output_root,
                cutoffs=tuple(args.cutoffs),
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                fixed_drive_frequency=args.fixed_drive_frequency,
                include_quarter_dt=args.include_quarter_dt,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
            ),
        )
        _print_3d_release_phase_numerical_validation_summary(result)
        return

    if args.command == "prototype-3d-release-phase-dt-recenter":
        config = _load_sim_config(args.config)
        result = run_3d_release_phase_dt_recenter(
            config,
            options=ReleasePhaseDtRecenterOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                fixed_drive_frequency=args.fixed_drive_frequency,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
            ),
        )
        _print_3d_release_phase_dt_recenter_summary(result)
        return

    if args.command == "prototype-3d-release-phase-proof-pack":
        config = _load_sim_config(args.config)
        result = run_3d_release_phase_proof_pack(
            config,
            options=ReleasePhaseProofPackOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                fixed_drive_frequency=args.fixed_drive_frequency,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
            ),
        )
        _print_3d_release_phase_proof_pack_summary(result)
        return

    if args.command == "prototype-3d-release-phase-resolution-lift":
        config = _load_sim_config(args.config)
        result = run_3d_release_phase_resolution_lift(
            config,
            options=ReleasePhaseResolutionLiftOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                fixed_drive_frequency=args.fixed_drive_frequency,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
            ),
        )
        _print_3d_release_phase_resolution_lift_summary(result)
        return

    if args.command == "prototype-3d-release-phase-resolution-postmortem":
        result = run_3d_release_phase_resolution_postmortem(
            options=ReleasePhaseResolutionPostmortemOptions(
                output_root=args.output_root,
                proof_root=args.proof_root,
                lift_root=args.lift_root,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                low_peak_threshold_fraction=args.low_peak_threshold_fraction,
                strict_peak_threshold_fraction=args.strict_peak_threshold_fraction,
                radial_shift_predict_threshold=args.radial_shift_predict_threshold,
                timing_shift_predict_threshold=args.timing_shift_predict_threshold,
            )
        )
        _print_3d_release_phase_resolution_postmortem_summary(result)
        return

    if args.command == "prototype-3d-release-phase-modal-audit":
        result = run_3d_release_phase_modal_audit(
            options=ReleasePhaseModalAuditOptions(
                output_root=args.output_root,
                proof_root=args.proof_root,
                lift_root=args.lift_root,
                postmortem_root=args.postmortem_root,
                central_root=args.central_root,
                same_band_relative_tolerance=args.same_band_relative_tolerance,
                min_strict_major_loss=args.min_strict_major_loss,
                min_loose_recovery=args.min_loose_recovery,
                blur_width_growth_threshold=args.blur_width_growth_threshold,
                blur_bandwidth_growth_threshold=args.blur_bandwidth_growth_threshold,
                blur_tail_radius_shift_threshold=args.blur_tail_radius_shift_threshold,
                finite_grid_concentration_ratio=args.finite_grid_concentration_ratio,
            )
        )
        _print_3d_release_phase_modal_audit_summary(result)
        return

    if args.command == "prototype-3d-release-phase-dispersion-audit":
        result = run_3d_release_phase_dispersion_audit(
            options=ReleasePhaseDispersionAuditOptions(
                output_root=args.output_root,
                config_path=args.config,
                proof_root=args.proof_root,
                lift_root=args.lift_root,
                postmortem_root=args.postmortem_root,
                modal_root=args.modal_root,
                reference_source_grid_size=args.reference_source_grid_size,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                same_band_relative_tolerance=args.same_band_relative_tolerance,
                min_strict_major_loss=args.min_strict_major_loss,
                min_loose_recovery=args.min_loose_recovery,
                min_bandwidth_growth=args.min_bandwidth_growth,
                min_tail_radius_shift=args.min_tail_radius_shift,
                max_lift_bandwidth_cv=args.max_lift_bandwidth_cv,
                max_lift_tail_radius_cv=args.max_lift_tail_radius_cv,
            )
        )
        _print_3d_release_phase_dispersion_audit_summary(result)
        return

    if args.command == "prototype-3d-spatial-phase-instrumentation":
        config = _load_sim_config(args.config)
        result = run_3d_spatial_phase_instrumentation(
            config,
            options=SpatialPhaseInstrumentationOptions(
                output_root=args.output_root,
                proof_grid_size=args.proof_grid_size,
                lift_grid_size=args.lift_grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                target_work_per_source_area=args.target_work_per_source_area,
                fixed_drive_frequency=args.fixed_drive_frequency,
                proof_cutoff=args.proof_cutoff,
                lift_target_release_phase=args.lift_target_release_phase,
                dt_scale=args.dt_scale,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                frame_peak_threshold_fraction=args.frame_peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
                max_return_frames=args.max_return_frames,
                radial_phase_bins=args.radial_phase_bins,
                angular_theta_bins=args.angular_theta_bins,
                angular_polar_bins=args.angular_polar_bins,
                coherence_drop_threshold=args.coherence_drop_threshold,
                radial_coherence_drop_threshold=args.radial_coherence_drop_threshold,
                angular_coherence_drop_threshold=args.angular_coherence_drop_threshold,
                node_stability_drop_threshold=args.node_stability_drop_threshold,
                width_growth_threshold=args.width_growth_threshold,
                center_shift_threshold=args.center_shift_threshold,
            ),
        )
        _print_3d_spatial_phase_instrumentation_summary(result)
        return

    if args.command == "prototype-3d-spatial-phase-precompensation-design":
        result = run_3d_spatial_phase_precompensation_design(
            options=SpatialPhasePrecompensationDesignOptions(
                output_root=args.output_root,
                spatial_phase_root=args.spatial_phase_root,
                angular_harmonic_m=args.angular_harmonic_m,
                ridge_lambda=args.ridge_lambda,
                min_matched_sector_samples=args.min_matched_sector_samples,
                min_model_r2=args.min_model_r2,
                max_peak_global_phase_std=args.max_peak_global_phase_std,
                max_global_phase_offset=args.max_global_phase_offset,
                max_face_phase_offset=args.max_face_phase_offset,
                max_cubic_multiplier_delta=args.max_cubic_multiplier_delta,
                max_angular_harmonic_amplitude=args.max_angular_harmonic_amplitude,
                max_release_phase_nudge=args.max_release_phase_nudge,
                baseline_cubic_sign=args.baseline_cubic_sign,
                baseline_drive_frequency=args.baseline_drive_frequency,
                baseline_target_release_phase=args.baseline_target_release_phase,
                baseline_cutoff=args.baseline_cutoff,
            )
        )
        _print_3d_spatial_phase_precompensation_design_summary(result)
        return

    if args.command == "prototype-3d-source-spectrum-design-audit":
        result = run_3d_source_spectrum_design_audit(
            options=SourceSpectrumDesignAuditOptions(
                output_root=args.output_root,
                config_path=args.config_path,
                dispersion_root=args.dispersion_root,
                spatial_phase_root=args.spatial_phase_root,
                precomp_root=args.precomp_root,
                physical_duration=args.physical_duration,
                dt_scale=args.dt_scale,
                proof_cutoff=args.proof_cutoff,
                lift_cutoff=args.lift_cutoff,
                drive_frequency=args.drive_frequency,
                phase_cycle_index=args.phase_cycle_index,
                far_sideband_multiplier=args.far_sideband_multiplier,
                min_modal_bandwidth_growth=args.min_modal_bandwidth_growth,
                min_spatial_coherence_drop=args.min_spatial_coherence_drop,
                min_current_far_sideband_fraction=args.min_current_far_sideband_fraction,
                min_smoothing_sideband_reduction=args.min_smoothing_sideband_reduction,
                max_smooth_bandwidth_ratio=args.max_smooth_bandwidth_ratio,
            )
        )
        _print_3d_source_spectrum_design_audit_summary(result)
        return

    if args.command in {"prototype-3d-central-burst-control", "central-hf-scattering-branch"}:
        config = _load_sim_config(args.config)
        result = run_3d_central_burst_control(
            config,
            options=CentralBurst3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                burst_duration=args.burst_duration,
                burst_radius=args.burst_radius,
                frequencies=tuple(args.frequencies),
                energy_labels=tuple(args.energy_labels),
                burst_acceleration_scales=tuple(args.burst_acceleration_scales),
                include_half_dt_check=not args.no_half_dt_check,
                event_thresholds=tuple(args.event_thresholds),
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                min_peak_separation_time=args.min_peak_separation_time,
            ),
        )
        _print_3d_central_burst_summary(result)
        return

    if args.command == "prototype-3d-second-pulse-control":
        config = _load_sim_config(args.config)
        result = run_3d_second_pulse_control(
            config,
            options=SecondPulse3DOptions(
                output_root=args.output_root,
                grid_size=args.grid_size,
                reference_source_grid_size=args.reference_source_grid_size,
                physical_duration=args.physical_duration,
                sample_every=args.sample_every,
                diagnostic_sample_every=args.diagnostic_sample_every,
                radial_bins=args.radial_bins,
                shell_window_radius=args.shell_window_radius,
                shell_window_width=args.shell_window_width,
                near_shell_width_dx=args.near_shell_width_dx,
                sponge_strength_multiplier=args.sponge_strength_multiplier,
                reference_variant=args.reference_variant,
                reference_events_csv=args.reference_events_csv,
                reference_cutoff_time=args.reference_cutoff_time,
                reference_release_phase_cycles=args.reference_release_phase_cycles,
                second_pulse_duration=args.second_pulse_duration,
                second_pulse_amplitude_scale=args.second_pulse_amplitude_scale,
                second_pulse_amplitude_scales=tuple(args.second_pulse_amplitude_scales) if args.second_pulse_amplitude_scales else None,
                second_pulse_durations=tuple(args.second_pulse_durations) if args.second_pulse_durations else None,
                second_pulse_roles=tuple(args.second_pulse_roles),
                second_pulse_micro_map=args.second_pulse_micro_map,
                micro_map_targets=tuple(args.micro_map_targets),
                launch_time_offsets=tuple(args.launch_time_offsets),
                second_pulse_phase_modes=tuple(args.second_pulse_phase_modes),
                boundary_to_shell_travel_time=args.boundary_to_shell_travel_time,
                preload_time=args.preload_time,
                phase_offset_control=args.phase_offset_control,
                arrival_threshold_fraction=args.arrival_threshold_fraction,
                exit_threshold_fraction=args.exit_threshold_fraction,
                exit_hold_samples=args.exit_hold_samples,
                peak_threshold_fraction=args.peak_threshold_fraction,
                refocus_threshold_fraction=args.refocus_threshold_fraction,
                min_peak_separation_time=args.min_peak_separation_time,
                min_refocus_count=args.min_refocus_count,
                min_width_growth_fraction=args.min_width_growth_fraction,
                min_decay_rate_magnitude=args.min_decay_rate_magnitude,
                max_outer_shell_target=args.max_outer_shell_ratio,
                min_retention_gain=args.min_retention_gain,
                min_refocus_gain=args.min_refocus_gain,
            ),
        )
        _print_3d_second_pulse_summary(result)
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


def _print_transport_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    best = result.get("best_transport_match") or {}
    print("Transport controls complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best non-reference match: {best.get('variant', 'n/a')}")
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


def _print_3d_prototype_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D prototype complete")
    print(f"prototype ID: {result['prototype_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"drive={row.get('drive_location')}/{row.get('drive_phase_mode')}, "
            f"retention={_format_optional(row.get('post_cutoff_shell_retention'))}, "
            f"period={_format_optional(row.get('shell_breathing_period'))}, "
            f"radius={_format_optional(row.get('best_shell_peak_radius'))}, "
            f"radius_range={_format_optional(row.get('post_cutoff_shell_radius_range'))}, "
            f"radial_sim={_format_optional(row.get('radial_similarity_to_reference'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_failure_audit_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    reference = next((row for row in result["variants"] if row["variant"] == "boundary_cubic_31"), result["variants"][0])
    print("3D failure-mode audit complete")
    print(f"prototype root: {result['prototype_root']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(
        "reference: "
        f"source/sponge={_format_optional(reference.get('source_sponge_overlap_fraction'))}, "
        f"global_radius={_format_optional(reference.get('global_shell_peak_radius'))}, "
        f"near_peak/work={_format_optional(reference.get('near_shell_peak_fraction_of_work'))}, "
        f"near_tail_fraction={_format_optional(reference.get('near_shell_tail_fraction_of_total'))}, "
        f"outer/near_tail={_format_optional(reference.get('outer_to_near_tail_energy_ratio'))}"
    )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"geometry audit: {result['geometry_csv']}")
    print(f"shell-window timeseries: {result['timeseries_csv']}")
    print(f"radial snapshots: {result['snapshots_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_source_sponge_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D source/sponge control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"source_d={_format_optional(row.get('boundary_source_inner_distance'))}, "
            f"source/sponge={_format_optional(row.get('source_sponge_overlap_fraction'))}, "
            f"work/area={_format_optional(row.get('work_per_source_area'))}, "
            f"near_peak/work={_format_optional(row.get('near_shell_peak_fraction_of_work'))}, "
            f"near_retention={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_sponge_strength_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D sponge-strength control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"sponge_x={_format_optional(row.get('sponge_strength_multiplier'))}, "
            f"width_x={_format_optional(row.get('sponge_width_multiplier'))}, "
            f"source/sponge={_format_optional(row.get('source_sponge_overlap_fraction'))}, "
            f"work/area={_format_optional(row.get('work_per_source_area'))}, "
            f"near_peak/work={_format_optional(row.get('near_shell_peak_fraction_of_work'))}, "
            f"near_retention={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_source_geometry_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D source-geometry control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best boundary variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"role={row.get('source_geometry_role')}, "
            f"faces={row.get('boundary_face_count')}, "
            f"phase={row.get('drive_phase_mode')}, "
            f"work/area={_format_optional(row.get('work_per_source_area'))}, "
            f"near_peak/work={_format_optional(row.get('near_shell_peak_fraction_of_work'))}, "
            f"near_retention={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_cubic_focus_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D cubic-focus control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"role={row.get('cubic_focus_role')}, "
            f"faces={row.get('boundary_face_count')}, "
            f"phase={row.get('drive_phase_mode')}, "
            f"sign={_format_optional(row.get('boundary_cubic_phase_sign'))}, "
            f"offset={_format_optional(row.get('boundary_phase_offset'))}, "
            f"work/area={_format_optional(row.get('work_per_source_area'))}, "
            f"near_peak/work={_format_optional(row.get('near_shell_peak_fraction_of_work'))}, "
            f"near_retention={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_cubic_confirmation_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D cubic-confirmation control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"family={row.get('cubic_confirmation_family')}, "
            f"role={row.get('cubic_confirmation_role')}, "
            f"dt={_format_optional(row.get('dt'))}, "
            f"sponge_x={_format_optional(row.get('sponge_strength_multiplier'))}, "
            f"work/area={_format_optional(row.get('work_per_source_area'))}, "
            f"near_peak/work={_format_optional(row.get('near_shell_peak_fraction_of_work'))}, "
            f"near_retention={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}, "
            f"dt_warning={row.get('stability_warnings')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_grid_confirmation_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D grid-confirmation control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"grid={row.get('grid_size')}, "
            f"dx={_format_optional(row.get('dx'))}, "
            f"family={row.get('grid_confirmation_family')}, "
            f"role={row.get('grid_confirmation_role')}, "
            f"work/area={_format_optional(row.get('work_per_source_area'))}, "
            f"near_peak/work={_format_optional(row.get('near_shell_peak_fraction_of_work'))}, "
            f"near_retention={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}, "
            f"dt_warning={row.get('stability_warnings')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_threshold_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D threshold control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"axis={row.get('threshold_axis')}, "
            f"amp_x={_format_optional(row.get('threshold_multiplier'))}, "
            f"phase={row.get('phase_offset_label')}, "
            f"work/area={_format_optional(row.get('work_per_source_area'))}, "
            f"near_peak/work={_format_optional(row.get('near_shell_peak_fraction_of_work'))}, "
            f"near_retention={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}, "
            f"dt_warning={row.get('stability_warnings')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_defect_control_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D defect control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"role={row.get('defect_control_role')}, "
            f"radius_x={_format_optional(row.get('defect_radius_multiplier'))}, "
            f"k={_format_optional(row.get('defect_stiffness_multiplier'))}, "
            f"damp={_format_optional(row.get('defect_damping_multiplier'))}, "
            f"coupling={_format_optional(row.get('defect_coupling_multiplier'))}, "
            f"work/area={_format_optional(row.get('work_per_source_area'))}, "
            f"fixed_peak/work={_format_optional(row.get('fixed_near_shell_peak_fraction_of_work'))}, "
            f"fixed_retention={_format_optional(row.get('fixed_near_shell_tail_retention'))}, "
            f"fixed_outer/near={_format_optional(row.get('fixed_outer_to_near_tail_energy_ratio'))}, "
            f"fixed_global_outer={row.get('fixed_global_peak_in_outer_window')}, "
            f"dt_warning={row.get('stability_warnings')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_radial_window_audit_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D radial-window audit complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best window radius: {_format_optional(classification.get('best_window_radius'))}")
    print("windows:")
    for row in result["window_comparisons"]:
        print(
            f"  - r={_format_optional(row.get('window_radius'))}: "
            f"def_ret={_format_optional(row.get('defect_retention'))}, "
            f"neu_ret={_format_optional(row.get('neutral_retention'))}, "
            f"lift_ret={_format_optional(row.get('defect_lift_retention'))}, "
            f"def_peak/work={_format_optional(row.get('defect_peak_work'))}, "
            f"neu_peak/work={_format_optional(row.get('neutral_peak_work'))}, "
            f"lift_peak={_format_optional(row.get('defect_lift_peak_work'))}, "
            f"radial_corr={_format_optional(row.get('radial_profile_correlation'))}, "
            f"frame_sim={_format_optional(row.get('window_best_frame_similarity'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"comparison CSV: {result['comparison_csv']}")
    print(f"variant window CSV: {result['variant_windows_csv']}")
    print(f"profile CSV: {result['profile_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_defect_lift_sweep_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D defect-lift sweep complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print(f"best window radius: {_format_optional(classification.get('best_window_radius'))}")
    print("variant best windows:")
    for row in result["variant_summaries"]:
        print(
            f"  - {row['variant']}: "
            f"success={row.get('strict_success')}, "
            f"r={_format_optional(row.get('best_window_radius'))}, "
            f"lift_ret={_format_optional(row.get('best_defect_lift_retention'))}, "
            f"lift_peak={_format_optional(row.get('best_defect_lift_peak_work'))}, "
            f"ret={_format_optional(row.get('best_defect_retention'))}, "
            f"outer/near={_format_optional(row.get('best_defect_outer_near'))}, "
            f"profile_corr={_format_optional(row.get('best_radial_profile_correlation'))}, "
            f"global_outer={row.get('best_defect_global_outer')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"comparison CSV: {result['comparison_csv']}")
    print(f"variant window CSV: {result['variant_window_csv']}")
    print(f"profile CSV: {result['profile_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_interference_diagnostics_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D interference diagnostics complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"role={row.get('interference_role')}, "
            f"phase={row.get('drive_phase_mode')}, "
            f"work/area={_format_optional(row.get('work_per_source_area'))}, "
            f"near_ret={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"coherence={_format_optional(row.get('tail_phase_coherence_mean'))}, "
            f"standing={_format_optional(row.get('standing_shell_persistence'))}, "
            f"cubic_proj={_format_optional(row.get('tail_cubic_projection_mean'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"phase CSV: {result['phase_csv']}")
    print(f"modal CSV: {result['modal_csv']}")
    print(f"wavefront CSV: {result['wavefront_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_standing_persistence_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D standing-shell persistence control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"standing={_format_optional(row.get('standing_score'))}, "
            f"node/anti={_format_optional(row.get('node_antinode_stability'))}, "
            f"to_mean={_format_optional(row.get('frame_similarity_to_mean_mean'))}, "
            f"f2f={_format_optional(row.get('frame_to_frame_similarity_mean'))}, "
            f"phase={_format_optional(row.get('radial_shell_phase_stability'))}, "
            f"spectral={_format_optional(row.get('shell_energy_spectral_concentration'))}, "
            f"retention={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"timeseries CSV: {result['timeseries_csv']}")
    print(f"autocorrelation CSV: {result['autocorrelation_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_transport_packet_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D transport-packet audit complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"retention={_format_optional(row.get('near_shell_tail_retention'))}, "
            f"outer/near={_format_optional(row.get('outer_to_near_tail_energy_ratio'))}, "
            f"arrival={_format_optional(row.get('first_shell_arrival_time'))}, "
            f"exit={row.get('shell_exit_detected')}, "
            f"radial_v={_format_optional(row.get('radial_group_velocity'))}, "
            f"in_flux={_format_optional(row.get('inward_flux_fraction'))}, "
            f"out_flux={_format_optional(row.get('outward_flux_fraction'))}, "
            f"phase_v={_format_optional(row.get('shell_phase_velocity'))}, "
            f"ang_drift={_format_optional(row.get('mean_angular_drift_rate'))}, "
            f"f2f={_format_optional(row.get('mean_frame_to_frame_similarity'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"timeseries CSV: {result['timeseries_csv']}")
    print(f"lag correlation CSV: {result['lag_correlation_csv']}")
    print(f"report: {result['report_path']}")
    print(f"audit report: {result['audit_report_path']}")


def _print_3d_packet_lifecycle_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D packet lifecycle audit complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"life={row.get('lifecycle_label')}, "
            f"peaks={row.get('major_shell_peak_count')}, "
            f"refocus={row.get('refocus_peak_count')}, "
            f"ret={_format_optional(row.get('tail_shell_retention'))}, "
            f"outer/shell={_format_optional(row.get('tail_outer_to_shell_mean'))}, "
            f"arrival={_format_optional(row.get('first_shell_arrival_time'))}, "
            f"exit={row.get('shell_exit_detected')}, "
            f"decay={_format_optional(row.get('post_cutoff_shell_decay_rate'))}, "
            f"radius_v={_format_optional(row.get('post_cutoff_radial_velocity'))}, "
            f"width_growth={_format_optional(row.get('packet_width_growth_fraction'))}, "
            f"in_flux={_format_optional(row.get('inward_flux_fraction'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"timeseries CSV: {result['timeseries_csv']}")
    print(f"events CSV: {result['events_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_refocusing_engineering_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D refocusing engineering control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        print(
            f"  - {row['variant']}: "
            f"axis={row.get('axis_label')}, "
            f"refocus={row.get('refocus_peak_count')}, "
            f"ratio={_format_optional(row.get('refocus_peak_ratio_max'))}, "
            f"exit={_format_optional(row.get('shell_exit_time'))}, "
            f"ret={_format_optional(row.get('tail_shell_retention'))}, "
            f"outer/shell={_format_optional(row.get('tail_outer_to_shell_mean'))}, "
            f"decay={_format_optional(row.get('post_cutoff_shell_decay_rate'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"timeseries CSV: {result['timeseries_csv']}")
    print(f"events CSV: {result['events_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_refocusing_map_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D refocusing cutoff-frequency map complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        exit_label = "no" if not row.get("shell_exit_detected") else _format_optional(row.get("shell_exit_time"))
        print(
            f"  - {row['variant']}: "
            f"role={row.get('map_role')}, "
            f"cutoff={_format_optional(row.get('drive_cutoff_time'))}, "
            f"freq={_format_optional(row.get('drive_frequency'))}, "
            f"peaks={row.get('major_shell_peak_count')}, "
            f"refocus={row.get('refocus_peak_count')}, "
            f"ratio={_format_optional(row.get('refocus_peak_ratio_max'))}, "
            f"exit={exit_label}, "
            f"ret={_format_optional(row.get('tail_shell_retention'))}, "
            f"outer/shell={_format_optional(row.get('tail_outer_to_shell_mean'))}, "
            f"decay={_format_optional(row.get('post_cutoff_shell_decay_rate'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"timeseries CSV: {result['timeseries_csv']}")
    print(f"events CSV: {result['events_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_cutoff_phase_map_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D cutoff phase timing map complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        exit_label = "no" if not row.get("shell_exit_detected") else _format_optional(row.get("shell_exit_time"))
        print(
            f"  - {row['variant']}: "
            f"family={row.get('family')}, "
            f"axis={row.get('axis_label')}, "
            f"cutoff={_format_optional(row.get('drive_cutoff_time'))}, "
            f"phase={_format_optional(row.get('cutoff_phase_cycles'))}, "
            f"peaks={row.get('major_shell_peak_count')}, "
            f"refocus={row.get('refocus_peak_count')}, "
            f"exit={exit_label}, "
            f"ret={_format_optional(row.get('tail_shell_retention'))}, "
            f"outer/shell={_format_optional(row.get('tail_outer_to_shell_mean'))}, "
            f"decay={_format_optional(row.get('post_cutoff_shell_decay_rate'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"ranked CSV: {result['ranked_csv']}")
    print(f"timeseries CSV: {result['timeseries_csv']}")
    print(f"events CSV: {result['events_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_resonator_layer_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D passive resonator layer control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("top conservative rows:")
    for row in result.get("threshold_robust_scores", [])[:8]:
        print(
            f"  - {row['variant']}: "
            f"resonator={row.get('resonator_variant')}, "
            f"cutoff={_format_optional(row.get('drive_cutoff_time'))}, "
            f"strict={row.get('min_major_peaks_across_thresholds')}/{row.get('min_refocus_peaks_across_thresholds')}, "
            f"default={row.get('default_major_peaks')}/{row.get('default_refocus_peaks')}, "
            f"ret={_format_optional(row.get('retention_median'))}, "
            f"outer/shell={_format_optional(row.get('outer_shell_median'))}, "
            f"score={_format_optional(row.get('conservative_score'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"threshold robust CSV: {result['threshold_robust_csv']}")
    print(f"energy timeseries CSV: {result['energy_timeseries_csv']}")
    print(f"coupling exchange CSV: {result['coupling_exchange_csv']}")
    print(f"events CSV: {result['events_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_release_phase_return_map_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D release-phase return map complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("blind recommendations:")
    for row in result.get("prediction_rows", []):
        if row.get("prediction_kind") != "blind_recommendation":
            continue
        print(
            f"  - {row.get('recommendation_role')}: "
            f"cutoff={_format_optional(row.get('cutoff_time'))}, "
            f"phase={_format_optional(row.get('release_phase_cycles'))}, "
            f"predicted={row.get('nearest_neighbor_predicted_major')}/{row.get('nearest_neighbor_predicted_refocus')}"
        )
    print(f"feature CSV: {result['feature_csv']}")
    print(f"predictions CSV: {result['predictions_csv']}")
    print(f"binned CSV: {result['binned_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_release_phase_blind_confirmation_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D release-phase blind confirmation complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("rows:")
    for row in result.get("summary_rows", []):
        print(
            f"  - {row.get('prediction_role')}: "
            f"cutoff={_format_optional(row.get('drive_cutoff_time'))}, "
            f"phase={_format_optional(row.get('cutoff_phase_cycles'))}, "
            f"default={row.get('default_major_peaks_at_0p30')}/{row.get('default_refocus_peaks_at_0p30')}, "
            f"strict={row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')}, "
            f"ret={_format_optional(row.get('retention'))}, "
            f"outer/shell={_format_optional(row.get('outer_shell'))}, "
            f"clean={row.get('strict_clean_pass')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"prediction check CSV: {result['prediction_check_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_release_phase_numerical_validation_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D release-phase numerical validation complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("rows:")
    for row in result.get("summary_rows", []):
        print(
            f"  - {row.get('dt_variant')} / {row.get('prediction_role')}: "
            f"cutoff={_format_optional(row.get('drive_cutoff_time'))}, "
            f"phase={_format_optional(row.get('cutoff_phase_cycles'))}, "
            f"default={row.get('default_major_peaks_at_0p30')}/{row.get('default_refocus_peaks_at_0p30')}, "
            f"strict={row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')}, "
            f"ret={_format_optional(row.get('retention'))}, "
            f"outer/shell={_format_optional(row.get('outer_shell'))}, "
            f"clean={row.get('strict_clean_pass')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"comparison CSV: {result['comparison_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_release_phase_dt_recenter_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D release-phase half-dt recentering complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("rows:")
    for row in result.get("summary_rows", []):
        print(
            f"  - {row.get('prediction_role')}: "
            f"cutoff={_format_optional(row.get('drive_cutoff_time'))}, "
            f"phase={_format_optional(row.get('cutoff_phase_cycles'))}, "
            f"default={row.get('default_major_peaks_at_0p30')}/{row.get('default_refocus_peaks_at_0p30')}, "
            f"strict={row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')}, "
            f"ret={_format_optional(row.get('retention'))}, "
            f"outer/shell={_format_optional(row.get('outer_shell'))}, "
            f"clean={row.get('strict_clean_pass')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"threshold robust CSV: {result['threshold_robust_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_release_phase_proof_pack_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D release-phase proof pack complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("gates:")
    for row in result.get("gate_rows", []):
        value = row.get("value")
        value_label = _format_optional(value) if isinstance(value, (int, float)) else str(value)
        print(f"  - {row.get('gate')}: pass={row.get('pass')} value={value_label} threshold={row.get('threshold')}")
    print("rows:")
    for row in result.get("summary_rows", []):
        print(
            f"  - {row.get('prediction_role')}: "
            f"cutoff={_format_optional(row.get('drive_cutoff_time'))}, "
            f"phase={_format_optional(row.get('cutoff_phase_cycles'))}, "
            f"default={row.get('default_major_peaks_at_0p30')}/{row.get('default_refocus_peaks_at_0p30')}, "
            f"strict={row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')}, "
            f"tail={_format_optional(row.get('tail_area_after_t50'))}, "
            f"timing={_format_optional(row.get('return_timing_regularity'))}, "
            f"clean={row.get('strict_clean_pass')}"
        )
    print(f"candidate card: {result['candidate_card_path']}")
    print(f"summary CSV: {result['summary_csv']}")
    print(f"threshold robust CSV: {result['threshold_robust_csv']}")
    print(f"gates CSV: {result['gates_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_release_phase_resolution_lift_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D release-phase resolution lift complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print("gates:")
    for row in result.get("gate_rows", []):
        value = row.get("value")
        value_label = _format_optional(value) if isinstance(value, (int, float)) else str(value)
        print(f"  - {row.get('gate')}: pass={row.get('pass')} value={value_label} threshold={row.get('threshold')}")
    print("rows:")
    for row in result.get("summary_rows", []):
        print(
            f"  - {row.get('prediction_role')}: "
            f"grid={row.get('grid_size')}, "
            f"target_phase={_format_optional(row.get('target_release_phase'))}, "
            f"cutoff={_format_optional(row.get('drive_cutoff_time'))}, "
            f"phase={_format_optional(row.get('cutoff_phase_cycles'))}, "
            f"default={row.get('default_major_peaks_at_0p30')}/{row.get('default_refocus_peaks_at_0p30')}, "
            f"strict={row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')}, "
            f"tail={_format_optional(row.get('tail_area_after_t50'))}, "
            f"timing={_format_optional(row.get('return_timing_regularity'))}, "
            f"energy_clean={row.get('energy_accounting_clean')}, "
            f"clean={row.get('strict_clean_pass')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"threshold robust CSV: {result['threshold_robust_csv']}")
    print(f"gates CSV: {result['gates_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_release_phase_resolution_postmortem_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D release-phase resolution postmortem complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    checks = classification.get("checks", {})
    if checks:
        print("checks:")
        for key, value in checks.items():
            print(f"  - {key}: {_format_optional(value) if isinstance(value, (int, float)) else value}")
    print("prediction:")
    for row in result.get("prediction_rows", []):
        print(
            f"  - {row.get('recommendation')}: "
            f"cutoff={_format_optional(row.get('predicted_cutoff'))}, "
            f"shell_radius={_format_optional(row.get('predicted_shell_window_radius'))}, "
            f"reason={row.get('reason')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"comparison CSV: {result['comparison_csv']}")
    print(f"prediction CSV: {result['prediction_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_release_phase_modal_audit_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D release-phase modal audit complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    checks = classification.get("checks", {})
    if checks:
        print("checks:")
        for key, value in checks.items():
            print(f"  - {key}: {_format_optional(value) if isinstance(value, (int, float)) else value}")
    print("rows:")
    for row in result.get("summary_rows", []):
        print(
            f"  - {row.get('audit_group')} / {row.get('variant')}: "
            f"grid={row.get('grid_size')}, "
            f"loose={row.get('loose_major_peaks')}/{row.get('loose_refocus_peaks')}, "
            f"default={row.get('default_major_peaks')}/{row.get('default_refocus_peaks')}, "
            f"strict={row.get('strict_major_peaks')}/{row.get('strict_refocus_peaks')}, "
            f"freq={_format_optional(row.get('dominant_shell_frequency'))}, "
            f"conc={_format_optional(row.get('dominant_spectral_concentration'))}, "
            f"bandwidth={_format_optional(row.get('spectral_bandwidth'))}, "
            f"tail_radius={_format_optional(row.get('tail_packet_radius_mean'))}, "
            f"outer/shell={_format_optional(row.get('tail_outer_to_shell_mean'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"spectrum CSV: {result['spectrum_csv']}")
    print(f"jitter CSV: {result['jitter_csv']}")
    print(f"radial CSV: {result['radial_csv']}")
    print(f"phase CSV: {result['phase_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_release_phase_dispersion_audit_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D release-phase dispersion audit complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    checks = classification.get("checks", {})
    if checks:
        print("checks:")
        for key, value in checks.items():
            print(f"  - {key}: {_format_optional(value) if isinstance(value, (int, float)) else value}")
    print("comparison:")
    for row in result.get("summary_rows", []):
        print(
            f"  - same_band={row.get('same_modal_band')}, "
            f"freq={_format_optional(row.get('proof_dominant_frequency_mean'))}/{_format_optional(row.get('lift_dominant_frequency_mean'))}, "
            f"bandwidth_delta={_format_optional(row.get('spectral_bandwidth_relative_delta'))}, "
            f"tail_shift={_format_optional(row.get('tail_radius_shift'))}, "
            f"strict_loss={_format_optional(row.get('strict_major_loss'))}, "
            f"loose_recovery={_format_optional(row.get('lift_loose_to_strict_major_recovery'))}, "
            f"spatial_phase={row.get('true_spatial_phase_frames_available')}"
        )
    print("prediction:")
    for row in result.get("prediction_rows", []):
        print(f"  - {row.get('recommendation')}: {row.get('reason')}")
    print(f"summary CSV: {result['summary_csv']}")
    print(f"feature CSV: {result['feature_csv']}")
    print(f"source CSV: {result['source_csv']}")
    print(f"shell CSV: {result['shell_csv']}")
    print(f"phase CSV: {result['phase_csv']}")
    print(f"prediction CSV: {result['prediction_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_spatial_phase_instrumentation_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D spatial phase instrumentation complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    checks = classification.get("checks", {})
    if checks:
        print("checks:")
        for key, value in checks.items():
            print(f"  - {key}: {_format_optional(value) if isinstance(value, (int, float)) else value}")
    print("reproductions:")
    for row in result.get("variants", []):
        print(
            f"  - {row.get('audit_group')} / {row.get('variant')}: "
            f"grid={row.get('grid_size')}, "
            f"cutoff={_format_optional(row.get('drive_cutoff_time'))}, "
            f"phase={_format_optional(row.get('cutoff_phase_cycles'))}, "
            f"default={row.get('default_major_peaks_at_0p30')}/{row.get('default_refocus_peaks_at_0p30')}, "
            f"strict={row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')}, "
            f"frames={row.get('instrumented_return_frame_count')}, "
            f"shell_coh={_format_optional(row.get('shell_phase_coherence_mean'))}, "
            f"radial_coh={_format_optional(row.get('radial_phase_coherence_mean'))}, "
            f"angular_coh={_format_optional(row.get('angular_phase_coherence_mean'))}, "
            f"spread={_format_optional(row.get('return_radial_spread_mean'))}"
        )
    print("comparison:")
    for row in result.get("comparison_rows", []):
        print(
            f"  - strict_loss={_format_optional(row.get('strict_major_loss'))}, "
            f"shell_drop={_format_optional(row.get('shell_phase_coherence_drop'))}, "
            f"radial_drop={_format_optional(row.get('radial_phase_coherence_drop'))}, "
            f"angular_drop={_format_optional(row.get('angular_phase_coherence_drop'))}, "
            f"node_drop={_format_optional(row.get('node_phase_stability_drop'))}, "
            f"center_shift={_format_optional(row.get('return_radial_centroid_shift'))}, "
            f"spread_growth={_format_optional(row.get('return_radial_spread_relative_growth'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"frame index CSV: {result['frame_index_csv']}")
    print(f"displacement CSV: {result['displacement_csv']}")
    print(f"velocity CSV: {result['velocity_csv']}")
    print(f"radial phase CSV: {result['radial_frames_csv']}")
    print(f"angular phase CSV: {result['angular_csv']}")
    print(f"stability CSV: {result['stability_csv']}")
    print(f"comparison CSV: {result['comparison_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_spatial_phase_precompensation_design_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D spatial phase precompensation design complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    checks = classification.get("checks", {})
    if checks:
        print("checks:")
        for key, value in checks.items():
            print(f"  - {key}: {_format_optional(value) if isinstance(value, (int, float)) else value}")
    summary = result.get("summary_row", {})
    print("fit summary:")
    print(
        "  - "
        f"samples={summary.get('matched_sector_samples')}, "
        f"r2={_format_optional(summary.get('low_dimensional_model_r2'))}, "
        f"rmse={_format_optional(summary.get('low_dimensional_weighted_rmse_radians'))}, "
        f"per_peak_phase_std={_format_optional(summary.get('per_peak_global_phase_error_std_radians'))}, "
        f"global_offset={_format_optional(summary.get('recommended_global_phase_offset_radians'))}, "
        f"max_face_offset={_format_optional(summary.get('recommended_max_face_phase_offset_radians'))}, "
        f"cubic_mult={_format_optional(summary.get('recommended_cubic_phase_strength_multiplier'))}, "
        f"harmonic_amp={_format_optional(summary.get('recommended_angular_harmonic_amplitude_radians'))}, "
        f"release_nudge={_format_optional(summary.get('recommended_release_phase_nudge_cycles'))}"
    )
    candidate = result.get("recommended_candidate", {})
    print("candidate:")
    print(
        "  - "
        f"recommended={candidate.get('recommended')}, "
        f"target_phase={_format_optional(candidate.get('target_release_phase'))}, "
        f"cutoff={_format_optional(candidate.get('cutoff'))}, "
        f"basis={candidate.get('correction_basis')}"
    )
    print("rejected corrections:")
    for row in result.get("rejected_rows", []):
        print(f"  - {row.get('correction')}: {row.get('risk_level')} risk, {row.get('reason')}")
    print(f"modes CSV: {result['modes_csv']}")
    print(f"candidate JSON: {result['recommended_candidate_json']}")
    print(f"rejected CSV: {result['rejected_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_source_spectrum_design_audit_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D source spectrum design audit complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    checks = classification.get("checks", {})
    if checks:
        print("checks:")
        for key, value in checks.items():
            print(f"  - {key}: {_format_optional(value) if isinstance(value, (int, float)) else value}")
    summary = result.get("summary_row", {})
    print("source-spectrum summary:")
    print(
        "  - "
        f"envelope={summary.get('current_source_envelope')} -> {summary.get('proposed_smooth_envelope')}, "
        f"modal_bw_growth={_format_optional(summary.get('observed_modal_bandwidth_relative_delta'))}, "
        f"hard_sideband={_format_optional(summary.get('hard_far_sideband_fraction_mean'))}, "
        f"smooth_sideband={_format_optional(summary.get('smooth_far_sideband_fraction_mean'))}, "
        f"sideband_reduction={_format_optional(summary.get('smoothing_far_sideband_reduction_fraction'))}, "
        f"source_bw_ratio={_format_optional(summary.get('smooth_to_hard_source_bandwidth_ratio'))}, "
        f"candidate_gate={summary.get('candidate_gate')}"
    )
    print("source windows:")
    for row in result.get("source_rows", []):
        print(
            f"  - {row.get('role')} / {row.get('envelope_kind')}: "
            f"phase={_format_optional(row.get('release_phase_cycles'))}, "
            f"bw={_format_optional(row.get('source_bandwidth'))}, "
            f"far_sideband={_format_optional(row.get('far_sideband_fraction'))}, "
            f"scale={_format_optional(row.get('work_proxy_scale'))}"
        )
    candidate = result.get("candidate", {})
    print("candidate:")
    print(
        "  - "
        f"recommended={candidate.get('recommended')}, "
        f"envelope={candidate.get('envelope')}, "
        f"cutoff={_format_optional(candidate.get('cutoff'))}, "
        f"target_phase={_format_optional(candidate.get('target_release_phase'))}, "
        f"work_policy={candidate.get('total_work_policy')}"
    )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"spectrum CSV: {result['spectrum_csv']}")
    print(f"candidate JSON: {result['candidate_json']}")
    print(f"rejected CSV: {result['rejected_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_central_burst_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D central HF scattering branch complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("top rows:")
    for row in sorted(result.get("variants", []), key=lambda item: float(item.get("central_burst_score") or 0.0), reverse=True)[:6]:
        print(
            f"  - {row.get('variant')}: "
            f"dt={row.get('dt_variant')}, "
            f"f={_format_optional(row.get('burst_frequency'))}, "
            f"energy={row.get('energy_label')}, "
            f"default={row.get('major_peaks_at_0p30')}/{row.get('refocus_peaks_at_0p30')}, "
            f"strict={row.get('conservative_major_peaks')}/{row.get('conservative_refocus_peaks')}, "
            f"ret={_format_optional(row.get('tail_shell_retention'))}, "
            f"outer/shell={_format_optional(row.get('tail_outer_to_shell_mean'))}, "
            f"energy_err={_format_optional(row.get('energy_accounting_error'))}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"threshold CSV: {result['threshold_csv']}")
    print(f"timeseries CSV: {result['timeseries_csv']}")
    print(f"events CSV: {result['events_csv']}")
    print(f"energy CSV: {result['energy_csv']}")
    print(f"report: {result['report_path']}")


def _print_3d_second_pulse_summary(result: dict[str, Any]) -> None:
    classification = result["classification"]
    print("3D second pulse control complete")
    print(f"control ID: {result['control_id']}")
    print(f"classification: {classification['label']}")
    print(f"reason: {classification['reason']}")
    print(f"best variant: {classification.get('best_variant', 'n/a')}")
    print("variants:")
    for row in result["variants"]:
        exit_label = "no" if not row.get("shell_exit_detected") else _format_optional(row.get("shell_exit_time"))
        print(
            f"  - {row['variant']}: "
            f"role={row.get('second_pulse_role')}, "
            f"center={_format_optional(row.get('second_pulse_center_time'))}, "
            f"phase={_format_optional(row.get('second_pulse_phase_at_center_cycles'))}, "
            f"peaks={row.get('major_shell_peak_count')}, "
            f"refocus={row.get('refocus_peak_count')}, "
            f"exit={exit_label}, "
            f"ret={_format_optional(row.get('tail_shell_retention'))}, "
            f"eff={_format_optional(row.get('refocus_efficiency_total_work'))}, "
            f"added_work_eff={_format_optional(row.get('added_work_efficiency'))}, "
            f"gain/work={_format_optional(row.get('return_gain_per_added_work'))}, "
            f"outer/shell={_format_optional(row.get('tail_outer_to_shell_mean'))}, "
            f"decay={_format_optional(row.get('post_cutoff_shell_decay_rate'))}, "
            f"global_outer={row.get('global_peak_in_outer_window')}"
        )
    print(f"summary CSV: {result['summary_csv']}")
    print(f"ranked CSV: {result['ranked_csv']}")
    print(f"timeseries CSV: {result['timeseries_csv']}")
    print(f"events CSV: {result['events_csv']}")
    print(f"timing audit CSV: {result['timing_audit_csv']}")
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
