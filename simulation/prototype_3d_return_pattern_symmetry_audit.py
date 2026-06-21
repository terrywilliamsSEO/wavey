"""Read-only return-pattern symmetry audit for 41^3 proof versus 51^3 controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from itertools import permutations, product
from pathlib import Path
from typing import Any
import csv
import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .prototype_3d import EPSILON
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_PROOF_ROOT = "runs/release_phase_proof_pack_3d_20260619_234039"
DEFAULT_LIFT_ROOT = "runs/release_phase_resolution_lift_3d_20260620_091834"
DEFAULT_SPATIAL_PHASE_ROOT = "runs/spatial_phase_instrumentation_3d_20260620_170518"
DEFAULT_SMOOTH_ROOT = "runs/smooth_envelope_resolution_lift_3d_20260620_192501"
DEFAULT_PHASE_CONJUGATE_ROOT = "runs/boundary_phase_conjugate_3d_20260620_212918"
DEFAULT_RETURN_FAMILY_GATE_ROOT = "runs/return_family_gate_audit_3d_20260621_082543"
DEFAULT_OFF_COMB_ROOT = "runs/off_comb_leakage_audit_3d_20260621_085347"


@dataclass(frozen=True)
class ReturnPatternSymmetryAuditOptions:
    """Options for the read-only return-pattern identity audit."""

    output_root: str = "runs"
    proof_root: str = DEFAULT_PROOF_ROOT
    lift_root: str = DEFAULT_LIFT_ROOT
    spatial_phase_root: str = DEFAULT_SPATIAL_PHASE_ROOT
    smooth_root: str = DEFAULT_SMOOTH_ROOT
    phase_conjugate_root: str = DEFAULT_PHASE_CONJUGATE_ROOT
    return_family_gate_root: str = DEFAULT_RETURN_FAMILY_GATE_ROOT
    off_comb_root: str = DEFAULT_OFF_COMB_ROOT
    include_reflections: bool = True
    sector_permutation_penalty: float = 0.18
    min_rescue_margin: float = 0.08
    marginal_rescue_margin: float = 0.04
    proof_memory_tolerance: float = 0.08
    transform_stability_threshold: float = 0.68
    source_signature_share_threshold: float = 0.67
    phase_vs_spatial_margin: float = 0.03
    max_pair_count: int = 12
    harmonic_orders: tuple[int, ...] = (0, 1, 2, 3, 4)


@dataclass
class FramePattern:
    """One return-window spatial pattern frame."""

    variant: str
    frame_id: str
    peak_rank: int
    time: float
    grid_size: int
    coords: np.ndarray | None = None
    displacement: np.ndarray | None = None
    velocity: np.ndarray | None = None
    sectors: dict[tuple[int, int], complex] | None = None
    theta_bins: int = 0
    polar_bins: int = 0


def run_3d_return_pattern_symmetry_audit(
    *,
    options: ReturnPatternSymmetryAuditOptions | None = None,
) -> dict[str, Any]:
    """Audit saved return-pattern artifacts without running new physics."""

    options = options or ReturnPatternSymmetryAuditOptions()
    control_id = datetime.now().strftime("return_pattern_symmetry_audit_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    records = _load_records(options)
    if not records:
        classification = classify_return_pattern_symmetry_audit([], options)
        return _write_empty_outputs(root, control_id, classification)

    pair_rows: list[dict[str, Any]] = []
    harmonic_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []

    for record in records:
        pair_result = _diagnose_record(record, options)
        pair_rows.extend(pair_result["pair_rows"])
        harmonic_rows.extend(pair_result["harmonic_rows"])
        summary = pair_result["summary"]
        summary_rows.append(summary)
        stability_rows.append(pair_result["stability"])

    classification = classify_return_pattern_symmetry_audit(summary_rows, options)
    source_signature_shared = classification.get("checks", {}).get("source_controls_share_transform_signature", False)
    for collection in (summary_rows, pair_rows, stability_rows, harmonic_rows):
        for row in collection:
            row["return_pattern_symmetry_classification"] = classification["label"]
            if "source_controls_share_transform_signature" in row:
                row["source_controls_share_transform_signature"] = source_signature_shared

    summary_csv = root / "return_pattern_symmetry_summary.csv"
    pair_csv = root / "return_pair_alignment.csv"
    stability_csv = root / "transform_stability.csv"
    harmonic_csv = root / "harmonic_pattern_similarity.csv"
    report_path = root / "return_pattern_symmetry_report.md"
    summary_json = root / "return_pattern_symmetry_summary.json"
    plots = {
        "raw_vs_aligned_similarity_plot": root / "raw_vs_aligned_similarity_plot.png",
        "transform_stability_plot": root / "transform_stability_plot.png",
        "symmetry_rescue_margin_plot": root / "symmetry_rescue_margin_plot.png",
    }

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(pair_csv, pair_rows, _pair_fields())
    _write_csv(stability_csv, stability_rows, _stability_fields())
    if harmonic_rows:
        _write_csv(harmonic_csv, harmonic_rows, _harmonic_fields())
    _write_plots(plots, summary_rows)
    _write_report(report_path, control_id, summary_rows, classification, plots, bool(harmonic_rows))
    summary_json.write_text(
        json.dumps(
            {
                "control_id": control_id,
                "classification": classification,
                "row_count": len(summary_rows),
                "pair_count": len(pair_rows),
                "harmonic_pair_count": len(harmonic_rows),
                "summary_csv": str(summary_csv),
                "pair_csv": str(pair_csv),
                "stability_csv": str(stability_csv),
                "harmonic_csv": str(harmonic_csv) if harmonic_rows else "",
                "report_path": str(report_path),
                "plots": {key: str(value) for key, value in plots.items()},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": summary_rows,
        "pair_rows": pair_rows,
        "stability_rows": stability_rows,
        "harmonic_rows": harmonic_rows,
        "summary_csv": str(summary_csv),
        "pair_csv": str(pair_csv),
        "stability_csv": str(stability_csv),
        "harmonic_csv": str(harmonic_csv) if harmonic_rows else "",
        "report_path": str(report_path),
        "summary_json": str(summary_json),
        "plots": {key: str(value) for key, value in plots.items()},
        "path": str(root),
    }


def enumerate_cubic_transforms(*, include_reflections: bool = False) -> list[dict[str, Any]]:
    """Return signed permutation matrices for proper cubic rotations, plus mirrors if requested."""

    transforms: list[dict[str, Any]] = []
    for perm in permutations(range(3)):
        base = np.zeros((3, 3), dtype=int)
        for row_index, col_index in enumerate(perm):
            base[row_index, col_index] = 1
        for signs in product((-1, 1), repeat=3):
            matrix = base.copy()
            for row_index, sign in enumerate(signs):
                matrix[row_index, :] *= sign
            det = int(round(float(np.linalg.det(matrix))))
            if det == 1 or include_reflections:
                kind = "cubic_rotation" if det == 1 else "cubic_reflection"
                transforms.append({"label": _matrix_label(matrix, kind), "kind": kind, "matrix": matrix, "determinant": det})
    transforms.sort(key=lambda item: (item["kind"], item["label"]))
    return transforms


def calculate_raw_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """Signed normalized similarity for real-valued patterns."""

    a = np.asarray(left, dtype=float).ravel()
    b = np.asarray(right, dtype=float).ravel()
    length = min(a.size, b.size)
    if length == 0:
        return 0.0
    a = a[:length]
    b = b[:length]
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= EPSILON:
        return 0.0
    value = float(np.dot(a, b) / denom)
    return float(np.clip(value, -1.0, 1.0))


def calculate_sign_aligned_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """Similarity after allowing a global sign flip."""

    return abs(calculate_raw_similarity(left, right))


def calculate_phase_aligned_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """Similarity after allowing one global complex phase rotation."""

    a = np.asarray(left, dtype=complex).ravel()
    b = np.asarray(right, dtype=complex).ravel()
    length = min(a.size, b.size)
    if length == 0:
        return 0.0
    a = a[:length]
    b = b[:length]
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= EPSILON:
        return 0.0
    value = abs(np.vdot(a, b)) / denom
    return float(np.clip(float(value), 0.0, 1.0))


def align_circular_sector_shift(left: np.ndarray, right: np.ndarray) -> dict[str, Any]:
    """Find the best common circular theta shift for polar-by-theta sector matrices."""

    a = np.asarray(left, dtype=complex)
    b = np.asarray(right, dtype=complex)
    if a.ndim != 2 or b.ndim != 2 or a.shape != b.shape or a.size == 0:
        return {"similarity": 0.0, "shift": 0, "transform_label": "sector_shift_0"}
    best = {"similarity": -1.0, "shift": 0, "transform_label": "sector_shift_0"}
    for shift in range(a.shape[1]):
        shifted = np.roll(b, shift=shift, axis=1)
        similarity = calculate_phase_aligned_similarity(a, shifted)
        if similarity > best["similarity"]:
            best = {"similarity": similarity, "shift": shift, "transform_label": f"sector_shift_{shift}"}
    return best


def calculate_transform_stability(labels: list[str]) -> dict[str, Any]:
    """Score whether the chosen transform is stable across consecutive returns."""

    clean = [str(label) for label in labels if str(label)]
    if not clean:
        return {"stability_score": 0.0, "dominant_transform": "", "dominant_fraction": 0.0, "transition_stability": 0.0}
    counts: dict[str, int] = {}
    for label in clean:
        counts[label] = counts.get(label, 0) + 1
    dominant, count = max(counts.items(), key=lambda item: (item[1], item[0]))
    dominant_fraction = count / len(clean)
    if len(clean) == 1:
        transition_stability = 1.0
    else:
        transition_stability = sum(1 for left, right in zip(clean, clean[1:]) if left == right) / (len(clean) - 1)
    stability = 0.65 * dominant_fraction + 0.35 * transition_stability
    return {
        "stability_score": float(stability),
        "dominant_transform": dominant,
        "dominant_fraction": float(dominant_fraction),
        "transition_stability": float(transition_stability),
    }


def classify_return_pattern_symmetry_audit(
    rows: list[dict[str, Any]],
    options: ReturnPatternSymmetryAuditOptions | None = None,
) -> dict[str, Any]:
    """Classify whether 51^3 pattern weakening is recoverable drift or true scrambling."""

    options = options or ReturnPatternSymmetryAuditOptions()
    proof = _proof_rows(rows)
    controls = _source_control_rows(rows)
    if not proof or not controls:
        return {
            "label": "insufficient_artifacts",
            "reason": "Required 41^3 proof and 51^3 source-control shell-pattern artifacts were not available.",
            "checks": {
                "proof_row_count": len(proof),
                "source_control_row_count": len(controls),
                "mechanism_candidate": "none",
            },
        }

    proof_raw = _mean(row.get("raw_pattern_memory_score") for row in proof)
    control_raw = _mean(row.get("raw_pattern_memory_score") for row in controls)
    proof_aligned = _mean(row.get("best_symmetry_aligned_memory_score") for row in proof)
    control_aligned = _mean(row.get("best_symmetry_aligned_memory_score") for row in controls)
    control_margin = _mean(row.get("symmetry_rescue_margin") for row in controls)
    control_spatial_margin = _mean(row.get("spatial_transform_rescue_margin") for row in controls)
    control_phase_margin = _mean(row.get("phase_or_sign_rescue_margin") for row in controls)
    control_stability = _mean(row.get("transform_stability_score") for row in controls)
    proof_stability = _mean(row.get("transform_stability_score") for row in proof)
    signatures = [str(row.get("dominant_transform_signature")) for row in controls if row.get("dominant_transform_signature")]
    signature_share = _dominant_share(signatures)
    source_controls_share_signature = signature_share >= options.source_signature_share_threshold
    rescued_to_proof = control_aligned >= max(0.0, proof_raw - options.proof_memory_tolerance)
    substantial_rescue = control_margin >= options.min_rescue_margin
    partial_rescue = control_margin >= options.marginal_rescue_margin
    spatial_leads = control_spatial_margin >= control_phase_margin + options.phase_vs_spatial_margin
    phase_leads = control_phase_margin >= control_spatial_margin + options.phase_vs_spatial_margin
    stable = control_stability >= options.transform_stability_threshold
    checks = {
        "proof_row_count": len(proof),
        "source_control_row_count": len(controls),
        "proof_raw_memory_mean": proof_raw,
        "source_control_raw_memory_mean": control_raw,
        "proof_aligned_memory_mean": proof_aligned,
        "source_control_aligned_memory_mean": control_aligned,
        "source_control_rescue_margin_mean": control_margin,
        "source_control_spatial_rescue_margin_mean": control_spatial_margin,
        "source_control_phase_or_sign_rescue_margin_mean": control_phase_margin,
        "proof_transform_stability_mean": proof_stability,
        "source_control_transform_stability_mean": control_stability,
        "source_transform_signature_share": signature_share,
        "source_controls_share_transform_signature": source_controls_share_signature,
        "rescued_to_proof_memory": rescued_to_proof,
        "substantial_rescue": substantial_rescue,
        "partial_rescue": partial_rescue,
        "spatial_transform_leads": spatial_leads,
        "phase_or_sign_leads": phase_leads,
        "stable_transforms": stable,
        "mechanism_candidate": "none",
    }
    if substantial_rescue and rescued_to_proof and spatial_leads and stable and source_controls_share_signature:
        checks["mechanism_candidate"] = "orientation_drift"
        return {
            "label": "orientation_drift_supported",
            "reason": "Allowed spatial symmetries substantially rescue 51^3 pattern memory, and the dominant transform remains coherent across returns and source controls.",
            "checks": checks,
        }
    if substantial_rescue and spatial_leads and not stable:
        checks["mechanism_candidate"] = "cubic_mode_hopping"
        return {
            "label": "cubic_mode_hopping_supported",
            "reason": "Cubic or sector permutations improve 51^3 pattern memory, but the chosen transform jumps between return pairs.",
            "checks": checks,
        }
    if substantial_rescue and phase_leads:
        checks["mechanism_candidate"] = "phase_precession"
        return {
            "label": "phase_precession_supported",
            "reason": "Global phase/sign alignment rescues 51^3 pattern memory more than spatial transforms.",
            "checks": checks,
        }
    if not partial_rescue:
        return {
            "label": "true_spatial_scrambling_supported",
            "reason": "No allowed sign, phase, cubic, reflection, sector-shift, permutation, or harmonic alignment meaningfully rescues 51^3 return-pattern memory.",
            "checks": checks,
        }
    return {
        "label": "pattern_symmetry_inconclusive",
        "reason": "Some symmetry alignments improve saved 51^3 pattern memory, but the rescue is not stable, not proof-like, or not separated from source controls.",
        "checks": checks,
    }


def _load_records(options: ReturnPatternSymmetryAuditOptions) -> list[dict[str, Any]]:
    summary_rows = _read_csv(Path(options.off_comb_root) / "off_comb_leakage_summary.csv")
    if not summary_rows:
        return []
    node_frames = _load_node_frame_sets(options)
    sector_frames = _load_sector_frame_sets(options)
    records = []
    for row in summary_rows:
        variant = str(row.get("variant"))
        alias = _spatial_alias(variant)
        nodes = node_frames.get(variant) or node_frames.get(alias) or []
        sectors = sector_frames.get(variant) or sector_frames.get(alias) or []
        artifact_kind = "node_frames" if len(nodes) >= 2 else "sector_frames" if len(sectors) >= 2 else "none"
        records.append(
            {
                "summary": row,
                "variant": variant,
                "artifact_source": row.get("artifact_source"),
                "audit_group": row.get("audit_group"),
                "prediction_role": row.get("prediction_role"),
                "grid_size": row.get("grid_size"),
                "node_frames": nodes,
                "sector_frames": sectors,
                "artifact_kind": artifact_kind,
            }
        )
    return records


def _load_node_frame_sets(options: ReturnPatternSymmetryAuditOptions) -> dict[str, list[FramePattern]]:
    frames = _load_node_frames(
        Path(options.spatial_phase_root) / "shell_displacement_frames.csv",
        Path(options.spatial_phase_root) / "shell_velocity_frames.csv",
    )
    return {variant: _sorted_frames(list(by_frame.values())) for variant, by_frame in frames.items()}


def _load_node_frames(displacement_path: Path, velocity_path: Path) -> dict[str, dict[str, FramePattern]]:
    rows = _read_csv(displacement_path)
    if not rows:
        return {}
    raw: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        variant = str(row.get("variant"))
        frame_id = str(row.get("frame_id"))
        frame = raw.setdefault(variant, {}).setdefault(
            frame_id,
            {
                "variant": variant,
                "frame_id": frame_id,
                "peak_rank": int(_first(row, "peak_rank")),
                "time": _first(row, "time"),
                "grid_size": int(_first(row, "grid_size")),
                "coords": [],
                "u": [],
                "v": [],
            },
        )
        frame["coords"].append((int(round(_first(row, "x"))), int(round(_first(row, "y"))), int(round(_first(row, "z")))))
        frame["u"].append(_first(row, "u"))
    if velocity_path.exists():
        velocity_index: dict[tuple[str, str], list[float]] = {}
        for row in _read_csv(velocity_path):
            velocity_index.setdefault((str(row.get("variant")), str(row.get("frame_id"))), []).append(_first(row, "v"))
        for variant, by_frame in raw.items():
            for frame_id, frame in by_frame.items():
                values = velocity_index.get((variant, frame_id), [])
                if len(values) == len(frame["u"]):
                    frame["v"] = values
    out: dict[str, dict[str, FramePattern]] = {}
    for variant, by_frame in raw.items():
        out[variant] = {}
        for frame_id, frame in by_frame.items():
            velocity = np.asarray(frame["v"], dtype=float) if len(frame["v"]) == len(frame["u"]) else None
            out[variant][frame_id] = FramePattern(
                variant=variant,
                frame_id=frame_id,
                peak_rank=int(frame["peak_rank"]),
                time=float(frame["time"]),
                grid_size=int(frame["grid_size"]),
                coords=np.asarray(frame["coords"], dtype=int),
                displacement=np.asarray(frame["u"], dtype=float),
                velocity=velocity,
            )
    return out


def _load_sector_frame_sets(options: ReturnPatternSymmetryAuditOptions) -> dict[str, list[FramePattern]]:
    paths = [
        (Path(options.spatial_phase_root) / "angular_shell_phase_coherence.csv", "spatial_phase"),
        (Path(options.smooth_root) / "smooth_envelope_angular_shell_phase_coherence.csv", "smooth_envelope"),
        (Path(options.phase_conjugate_root) / "boundary_phase_conjugate_angular_shell_phase_coherence.csv", "boundary_phase_conjugate"),
    ]
    frames: dict[str, dict[str, FramePattern]] = {}
    for path, _label in paths:
        for frame in _load_sector_frames(path):
            frames.setdefault(frame.variant, {})[frame.frame_id] = frame
    return {variant: _sorted_frames(list(by_frame.values())) for variant, by_frame in frames.items()}


def _load_sector_frames(path: Path) -> list[FramePattern]:
    rows = _read_csv(path)
    if not rows:
        return []
    grouped = _group_by(rows, "frame_id")
    frames = []
    for frame_id, sectors in grouped.items():
        if not sectors:
            continue
        variant = str(sectors[0].get("variant"))
        clean = [row for row in sectors if str(row.get("polar_bin")) not in {"", "octant"} and str(row.get("theta_bin")) != ""]
        if not clean:
            continue
        sector_values: dict[tuple[int, int], complex] = {}
        for row in clean:
            polar = int(round(_first(row, "polar_bin")))
            theta = int(round(_first(row, "theta_bin")))
            energy = max(_first(row, "shell_energy"), 0.0)
            amplitude = math.sqrt(energy) if energy > EPSILON else _first(row, "rms_displacement")
            coherence = _first(row, "phase_coherence")
            if coherence > EPSILON:
                amplitude *= coherence
            phase = 2.0 * math.pi * _first(row, "phase_mean_cycles")
            sector_values[(polar, theta)] = complex(amplitude * math.cos(phase), amplitude * math.sin(phase))
        frames.append(
            FramePattern(
                variant=variant,
                frame_id=str(frame_id),
                peak_rank=int(_first(sectors[0], "peak_rank")),
                time=_first(sectors[0], "time"),
                grid_size=int(_first(sectors[0], "grid_size")),
                sectors=sector_values,
                polar_bins=len({key[0] for key in sector_values}),
                theta_bins=len({key[1] for key in sector_values}),
            )
        )
    return frames


def _diagnose_record(record: dict[str, Any], options: ReturnPatternSymmetryAuditOptions) -> dict[str, Any]:
    variant = str(record["variant"])
    artifact_source = str(record.get("artifact_source"))
    audit_group = str(record.get("audit_group"))
    role = str(record.get("prediction_role"))
    grid_size = int(_first(record.get("summary", {}), "grid_size"))
    artifact_kind = str(record.get("artifact_kind"))
    node_frames = _sorted_frames(record.get("node_frames", []))[: options.max_pair_count]
    sector_frames = _sorted_frames(record.get("sector_frames", []))[: options.max_pair_count]
    frames = node_frames if len(node_frames) >= 2 else sector_frames
    pair_rows: list[dict[str, Any]] = []
    harmonic_rows: list[dict[str, Any]] = []
    if len(frames) >= 2:
        for left, right in zip(frames, frames[1:]):
            if artifact_kind == "node_frames" and left.coords is not None and right.coords is not None:
                pair_rows.append(_node_pair_row(variant, artifact_source, audit_group, role, grid_size, left, right, options))
            elif left.sectors is not None and right.sectors is not None:
                pair_rows.append(_sector_pair_row(variant, artifact_source, audit_group, role, grid_size, left, right, options))
                harmonic_rows.extend(_harmonic_rows(variant, artifact_source, audit_group, role, grid_size, left, right, options))

    if not pair_rows and len(sector_frames) >= 2:
        for left, right in zip(sector_frames, sector_frames[1:]):
            pair_rows.append(_sector_pair_row(variant, artifact_source, audit_group, role, grid_size, left, right, options))
            harmonic_rows.extend(_harmonic_rows(variant, artifact_source, audit_group, role, grid_size, left, right, options))

    stability = calculate_transform_stability([str(row.get("dominant_transform_label")) for row in pair_rows])
    raw_memory = _mean(row.get("raw_memory_score") for row in pair_rows)
    sign_memory = _mean(row.get("sign_aligned_similarity") for row in pair_rows)
    phase_memory = _mean(row.get("phase_aligned_similarity") for row in pair_rows)
    cubic_memory = _mean(row.get("cubic_rotation_similarity") for row in pair_rows)
    reflection_memory = _mean(row.get("cubic_reflection_similarity") for row in pair_rows)
    shift_memory = _mean(row.get("sector_circular_shift_similarity") for row in pair_rows)
    permutation_memory = _mean(row.get("sector_permutation_similarity_penalized") for row in pair_rows)
    harmonic_memory = _mean(row.get("harmonic_similarity") for row in pair_rows)
    best_memory = _mean(row.get("best_aligned_similarity") for row in pair_rows)
    spatial_memory = max(cubic_memory, reflection_memory, shift_memory, permutation_memory, harmonic_memory)
    phase_sign_memory = max(sign_memory, phase_memory)
    summary = {
        "variant": variant,
        "artifact_source": artifact_source,
        "audit_group": audit_group,
        "prediction_role": role,
        "grid_size": grid_size,
        "available_artifact_kind": artifact_kind,
        "return_frame_count": len(frames),
        "return_pair_count": len(pair_rows),
        "raw_pattern_memory_score": raw_memory,
        "sign_aligned_memory_score": sign_memory,
        "phase_aligned_memory_score": phase_memory,
        "cubic_rotation_memory_score": cubic_memory,
        "cubic_reflection_memory_score": reflection_memory,
        "sector_circular_shift_memory_score": shift_memory,
        "sector_permutation_memory_score": permutation_memory,
        "harmonic_memory_score": harmonic_memory,
        "best_symmetry_aligned_memory_score": best_memory,
        "symmetry_rescue_margin": max(0.0, best_memory - raw_memory),
        "phase_or_sign_rescue_margin": max(0.0, phase_sign_memory - raw_memory),
        "spatial_transform_rescue_margin": max(0.0, spatial_memory - raw_memory),
        "dominant_transform_signature": stability["dominant_transform"],
        "transform_stability_score": stability["stability_score"],
        "transform_dominant_fraction": stability["dominant_fraction"],
        "transform_transition_stability": stability["transition_stability"],
        "alignment_reduces_scrambling": max(0.0, best_memory - raw_memory) >= options.min_rescue_margin,
        "source_controls_share_transform_signature": "",
        "strict_major_peaks": _first(record.get("summary", {}), "strict_major_peaks"),
        "strict_refocus_peaks": _first(record.get("summary", {}), "strict_refocus_peaks"),
        "off_comb_energy_ratio": _first(record.get("summary", {}), "off_comb_energy_ratio"),
        "spatial_pattern_leakage_score": _first(record.get("summary", {}), "spatial_pattern_leakage_score"),
    }
    stability_row = {
        "variant": variant,
        "artifact_source": artifact_source,
        "audit_group": audit_group,
        "prediction_role": role,
        "grid_size": grid_size,
        "available_artifact_kind": artifact_kind,
        "return_pair_count": len(pair_rows),
        "dominant_transform": stability["dominant_transform"],
        "dominant_fraction": stability["dominant_fraction"],
        "transition_stability": stability["transition_stability"],
        "transform_stability_score": stability["stability_score"],
    }
    return {"summary": summary, "pair_rows": pair_rows, "stability": stability_row, "harmonic_rows": harmonic_rows}


def _node_pair_row(
    variant: str,
    artifact_source: str,
    audit_group: str,
    role: str,
    grid_size: int,
    left: FramePattern,
    right: FramePattern,
    options: ReturnPatternSymmetryAuditOptions,
) -> dict[str, Any]:
    left_values, right_values = _matched_node_values(left, right)
    raw = calculate_raw_similarity(left_values, right_values)
    raw_score = max(0.0, raw)
    sign = calculate_sign_aligned_similarity(left_values, right_values)
    phase = _node_phase_similarity(left, right)
    cubic = _best_cubic_alignment(left, right, include_reflections=False)
    reflected = (
        _best_cubic_alignment(left, right, include_reflections=True, reflection_only=True)
        if options.include_reflections
        else {"similarity": 0.0, "label": "", "kind": "cubic_reflection"}
    )
    reflection_similarity = reflected["similarity"]
    candidates = [
        ("raw", "identity", raw_score),
        ("sign_flip" if raw < 0.0 else "raw", "identity", sign),
        ("phase_shift", "global_phase", phase),
        (cubic["kind"], cubic["label"], cubic["similarity"]),
        (reflected["kind"], reflected["label"], reflection_similarity),
    ]
    dominant = max(candidates, key=lambda item: item[2])
    return {
        "variant": variant,
        "artifact_source": artifact_source,
        "audit_group": audit_group,
        "prediction_role": role,
        "grid_size": grid_size,
        "artifact_kind": "node_frames",
        "from_frame_id": left.frame_id,
        "to_frame_id": right.frame_id,
        "from_peak_rank": left.peak_rank,
        "to_peak_rank": right.peak_rank,
        "from_time": left.time,
        "to_time": right.time,
        "raw_similarity": raw,
        "raw_memory_score": raw_score,
        "sign_aligned_similarity": sign,
        "phase_aligned_similarity": phase,
        "cubic_rotation_similarity": cubic["similarity"],
        "cubic_rotation_label": cubic["label"],
        "cubic_reflection_similarity": reflection_similarity,
        "cubic_reflection_label": reflected["label"],
        "sector_circular_shift_similarity": "",
        "sector_circular_shift_label": "",
        "sector_permutation_similarity_penalized": "",
        "sector_permutation_moved_fraction": "",
        "harmonic_similarity": "",
        "best_aligned_similarity": dominant[2],
        "symmetry_rescue_margin": max(0.0, dominant[2] - raw_score),
        "dominant_transform_type": dominant[0],
        "dominant_transform_label": dominant[1],
        "matched_sample_count": len(left_values),
    }


def _sector_pair_row(
    variant: str,
    artifact_source: str,
    audit_group: str,
    role: str,
    grid_size: int,
    left: FramePattern,
    right: FramePattern,
    options: ReturnPatternSymmetryAuditOptions,
) -> dict[str, Any]:
    left_matrix = _sector_matrix(left)
    right_matrix = _sector_matrix(right)
    raw_complex = _complex_raw_similarity(left_matrix.ravel(), right_matrix.ravel())
    raw_score = max(0.0, raw_complex)
    sign = abs(raw_complex)
    phase = calculate_phase_aligned_similarity(left_matrix, right_matrix)
    shift = align_circular_sector_shift(left_matrix, right_matrix)
    permutation = _sector_permutation_similarity(left_matrix.ravel(), right_matrix.ravel(), options.sector_permutation_penalty)
    harmonic = _harmonic_similarity(left, right, options)
    candidates = [
        ("raw", "identity", raw_score),
        ("sign_flip" if raw_complex < 0.0 else "raw", "identity", sign),
        ("phase_shift", "global_phase", phase),
        ("sector_circular_shift", shift["transform_label"], shift["similarity"]),
        ("sector_permutation", permutation["transform_label"], permutation["similarity"]),
        ("harmonic_mode", "harmonic_coefficients", harmonic),
    ]
    dominant = max(candidates, key=lambda item: item[2])
    return {
        "variant": variant,
        "artifact_source": artifact_source,
        "audit_group": audit_group,
        "prediction_role": role,
        "grid_size": grid_size,
        "artifact_kind": "sector_frames",
        "from_frame_id": left.frame_id,
        "to_frame_id": right.frame_id,
        "from_peak_rank": left.peak_rank,
        "to_peak_rank": right.peak_rank,
        "from_time": left.time,
        "to_time": right.time,
        "raw_similarity": raw_complex,
        "raw_memory_score": raw_score,
        "sign_aligned_similarity": sign,
        "phase_aligned_similarity": phase,
        "cubic_rotation_similarity": "",
        "cubic_rotation_label": "",
        "cubic_reflection_similarity": "",
        "cubic_reflection_label": "",
        "sector_circular_shift_similarity": shift["similarity"],
        "sector_circular_shift_label": shift["transform_label"],
        "sector_permutation_similarity_penalized": permutation["similarity"],
        "sector_permutation_moved_fraction": permutation["moved_fraction"],
        "harmonic_similarity": harmonic,
        "best_aligned_similarity": dominant[2],
        "symmetry_rescue_margin": max(0.0, dominant[2] - raw_score),
        "dominant_transform_type": dominant[0],
        "dominant_transform_label": dominant[1],
        "matched_sample_count": left_matrix.size,
    }


def _matched_node_values(left: FramePattern, right: FramePattern, matrix: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    if left.coords is None or right.coords is None or left.displacement is None or right.displacement is None:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    left_map = {tuple(coord): value for coord, value in zip(left.coords.tolist(), left.displacement.tolist())}
    left_values = []
    right_values = []
    for coord, value in zip(right.coords.tolist(), right.displacement.tolist()):
        transformed = tuple((matrix @ np.asarray(coord, dtype=int)).tolist()) if matrix is not None else tuple(coord)
        if transformed in left_map:
            left_values.append(left_map[transformed])
            right_values.append(value)
    return np.asarray(left_values, dtype=float), np.asarray(right_values, dtype=float)


def _node_phase_similarity(left: FramePattern, right: FramePattern) -> float:
    if left.velocity is None or right.velocity is None:
        return 0.0
    left_u, right_u = _matched_node_values(left, right)
    left_v, right_v = _matched_velocity_values(left, right)
    if left_u.size == 0 or left_v.size != left_u.size or right_v.size != right_u.size:
        return 0.0
    left_scale = float(np.linalg.norm(left_u) / max(np.linalg.norm(left_v), EPSILON))
    right_scale = float(np.linalg.norm(right_u) / max(np.linalg.norm(right_v), EPSILON))
    scale = math.sqrt(max(left_scale, EPSILON) * max(right_scale, EPSILON))
    left_complex = left_u + 1j * scale * left_v
    right_complex = right_u + 1j * scale * right_v
    return calculate_phase_aligned_similarity(left_complex, right_complex)


def _matched_velocity_values(left: FramePattern, right: FramePattern, matrix: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    if left.coords is None or right.coords is None or left.velocity is None or right.velocity is None:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    left_map = {tuple(coord): value for coord, value in zip(left.coords.tolist(), left.velocity.tolist())}
    left_values = []
    right_values = []
    for coord, value in zip(right.coords.tolist(), right.velocity.tolist()):
        transformed = tuple((matrix @ np.asarray(coord, dtype=int)).tolist()) if matrix is not None else tuple(coord)
        if transformed in left_map:
            left_values.append(left_map[transformed])
            right_values.append(value)
    return np.asarray(left_values, dtype=float), np.asarray(right_values, dtype=float)


def _best_cubic_alignment(
    left: FramePattern,
    right: FramePattern,
    *,
    include_reflections: bool,
    reflection_only: bool = False,
) -> dict[str, Any]:
    best = {"similarity": 0.0, "label": "", "kind": "cubic_rotation"}
    for transform in enumerate_cubic_transforms(include_reflections=include_reflections):
        if not include_reflections and transform["determinant"] != 1:
            continue
        if reflection_only and transform["determinant"] != -1:
            continue
        left_values, right_values = _matched_node_values(left, right, transform["matrix"])
        similarity = calculate_sign_aligned_similarity(left_values, right_values)
        if similarity > best["similarity"]:
            best = {"similarity": similarity, "label": transform["label"], "kind": transform["kind"]}
    return best


def _sector_matrix(frame: FramePattern) -> np.ndarray:
    sectors = frame.sectors or {}
    if not sectors:
        return np.zeros((0, 0), dtype=complex)
    polar_values = sorted({key[0] for key in sectors})
    theta_values = sorted({key[1] for key in sectors})
    matrix = np.zeros((len(polar_values), len(theta_values)), dtype=complex)
    polar_index = {value: idx for idx, value in enumerate(polar_values)}
    theta_index = {value: idx for idx, value in enumerate(theta_values)}
    for key, value in sectors.items():
        matrix[polar_index[key[0]], theta_index[key[1]]] = value
    return matrix


def _complex_raw_similarity(left: np.ndarray, right: np.ndarray) -> float:
    a = np.asarray(left, dtype=complex).ravel()
    b = np.asarray(right, dtype=complex).ravel()
    length = min(a.size, b.size)
    if length == 0:
        return 0.0
    a = a[:length]
    b = b[:length]
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= EPSILON:
        return 0.0
    return float(np.clip(float(np.real(np.vdot(a, b)) / denom), -1.0, 1.0))


def _sector_permutation_similarity(left: np.ndarray, right: np.ndarray, penalty: float) -> dict[str, Any]:
    a = np.asarray(left, dtype=complex).ravel()
    b = np.asarray(right, dtype=complex).ravel()
    length = min(a.size, b.size)
    if length == 0:
        return {"similarity": 0.0, "raw_similarity": 0.0, "moved_fraction": 0.0, "transform_label": "sector_permutation_none"}
    a = a[:length]
    b = b[:length]
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= EPSILON:
        return {"similarity": 0.0, "raw_similarity": 0.0, "moved_fraction": 0.0, "transform_label": "sector_permutation_none"}
    scores = []
    for i in range(length):
        for j in range(length):
            scores.append((abs(np.conjugate(a[i]) * b[j]), i, j))
    scores.sort(reverse=True, key=lambda item: item[0])
    used_i: set[int] = set()
    used_j: set[int] = set()
    score = 0.0
    moved = 0
    for value, i, j in scores:
        if i in used_i or j in used_j:
            continue
        used_i.add(i)
        used_j.add(j)
        score += float(value)
        if i != j:
            moved += 1
        if len(used_i) == length:
            break
    raw = float(np.clip(score / denom, 0.0, 1.0))
    moved_fraction = moved / max(length, 1)
    penalized = max(0.0, raw - float(penalty) * moved_fraction)
    return {
        "similarity": float(np.clip(penalized, 0.0, 1.0)),
        "raw_similarity": raw,
        "moved_fraction": float(moved_fraction),
        "transform_label": f"sector_permutation_moved_{moved}",
    }


def _harmonic_rows(
    variant: str,
    artifact_source: str,
    audit_group: str,
    role: str,
    grid_size: int,
    left: FramePattern,
    right: FramePattern,
    options: ReturnPatternSymmetryAuditOptions,
) -> list[dict[str, Any]]:
    rows = []
    for order in options.harmonic_orders:
        left_coeff = _harmonic_coefficients(left, (order,))
        right_coeff = _harmonic_coefficients(right, (order,))
        rows.append(
            {
                "variant": variant,
                "artifact_source": artifact_source,
                "audit_group": audit_group,
                "prediction_role": role,
                "grid_size": grid_size,
                "from_frame_id": left.frame_id,
                "to_frame_id": right.frame_id,
                "from_peak_rank": left.peak_rank,
                "to_peak_rank": right.peak_rank,
                "harmonic_order": order,
                "harmonic_similarity": calculate_phase_aligned_similarity(left_coeff, right_coeff),
            }
        )
    return rows


def _harmonic_similarity(left: FramePattern, right: FramePattern, options: ReturnPatternSymmetryAuditOptions) -> float:
    left_coeff = _harmonic_coefficients(left, options.harmonic_orders)
    right_coeff = _harmonic_coefficients(right, options.harmonic_orders)
    return calculate_phase_aligned_similarity(left_coeff, right_coeff)


def _harmonic_coefficients(frame: FramePattern, orders: tuple[int, ...]) -> np.ndarray:
    matrix = _sector_matrix(frame)
    if matrix.size == 0:
        return np.asarray([], dtype=complex)
    theta_count = matrix.shape[1]
    theta = np.arange(theta_count, dtype=float)
    coeffs = []
    for order in orders:
        basis = np.exp(-2.0j * math.pi * float(order) * theta / max(theta_count, 1))
        coeffs.extend((matrix * basis).sum(axis=1) / max(theta_count, 1))
    return np.asarray(coeffs, dtype=complex)


def _write_plots(plots: dict[str, Path], rows: list[dict[str, Any]]) -> None:
    selected = _plot_rows(rows)
    labels = [_short_label(str(row.get("variant"))) for row in selected]
    raw = [_float(row.get("raw_pattern_memory_score")) for row in selected]
    aligned = [_float(row.get("best_symmetry_aligned_memory_score")) for row in selected]
    stability = [_float(row.get("transform_stability_score")) for row in selected]
    margin = [_float(row.get("symmetry_rescue_margin")) for row in selected]

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.9), 4), dpi=140)
    width = 0.38
    ax.bar(x - width / 2, raw, width, label="raw", color="#5577aa")
    ax.bar(x + width / 2, aligned, width, label="aligned", color="#66aa77")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
    ax.set_ylim(0.0, 1.05)
    ax.set_title("Raw vs Symmetry-Aligned Pattern Memory")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots["raw_vs_aligned_similarity_plot"])
    plt.close(fig)

    _bar_plot(plots["transform_stability_plot"], labels, stability, "Transform Stability", ylim=(0.0, 1.05))
    _bar_plot(plots["symmetry_rescue_margin_plot"], labels, margin, "Symmetry Rescue Margin", ylim=(0.0, max(0.12, max(margin, default=0.0) * 1.2)))


def _bar_plot(path: Path, labels: list[str], values: list[float], title: str, *, ylim: tuple[float, float]) -> None:
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.9), 4), dpi=140)
    ax.bar(range(len(labels)), values, color="#aa7744")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
    ax.set_ylim(*ylim)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_report(
    path: Path,
    control_id: str,
    rows: list[dict[str, Any]],
    classification: dict[str, Any],
    plots: dict[str, Path],
    has_harmonics: bool,
) -> None:
    checks = classification.get("checks", {})
    lines = [
        f"# Return-Pattern Symmetry Audit: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only audit of whether the 51^3 return-to-return spatial-pattern scrambling is recoverable by allowed sign, phase, cubic, reflection, sector-shift, permutation, or harmonic alignments. No new physics was run.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Mechanism-derived next candidate: `{checks.get('mechanism_candidate', 'none')}`",
        "",
        "## Mean Scores",
        "",
        f"- Proof raw memory mean: `{_format(checks.get('proof_raw_memory_mean'))}`",
        f"- 51^3 raw memory mean: `{_format(checks.get('source_control_raw_memory_mean'))}`",
        f"- Proof aligned memory mean: `{_format(checks.get('proof_aligned_memory_mean'))}`",
        f"- 51^3 aligned memory mean: `{_format(checks.get('source_control_aligned_memory_mean'))}`",
        f"- 51^3 rescue margin mean: `{_format(checks.get('source_control_rescue_margin_mean'))}`",
        f"- 51^3 transform stability mean: `{_format(checks.get('source_control_transform_stability_mean'))}`",
        f"- Source transform signature share: `{_format(checks.get('source_transform_signature_share'))}`",
        "",
        "## Rows",
        "",
        "| Variant | Artifact | Role | Grid | Frames | Raw | Best aligned | Rescue | Dominant transform | Stability |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in _plot_rows(rows):
        lines.append(
            "| "
            f"{row.get('variant')} | "
            f"{row.get('available_artifact_kind')} | "
            f"{row.get('prediction_role')} | "
            f"{row.get('grid_size')} | "
            f"{row.get('return_frame_count')} | "
            f"{_format(row.get('raw_pattern_memory_score'))} | "
            f"{_format(row.get('best_symmetry_aligned_memory_score'))} | "
            f"{_format(row.get('symmetry_rescue_margin'))} | "
            f"{row.get('dominant_transform_signature')} | "
            f"{_format(row.get('transform_stability_score'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(classification),
            "",
            "## Plots",
            "",
        ]
    )
    for plot in plots.values():
        lines.append(f"- `{plot.name}`")
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `return_pattern_symmetry_summary.csv`",
            "- `return_pair_alignment.csv`",
            "- `transform_stability.csv`",
        ]
    )
    if has_harmonics:
        lines.append("- `harmonic_pattern_similarity.csv`")
    lines.append("- `return_pattern_symmetry_summary.json`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "orientation_drift_supported":
        return "The saved 51^3 patterns look like a stable orientation drift under the allowed symmetry group, so the pattern loss is potentially recoverable in interpretation space."
    if label == "cubic_mode_hopping_supported":
        return "The 51^3 rows can be made more similar by symmetry alignment, but the transform changes from return to return, consistent with cubic-mode hopping rather than one stable drift."
    if label == "phase_precession_supported":
        return "The dominant rescue is global phase/sign alignment rather than spatial reorientation, consistent with phase precession."
    if label == "true_spatial_scrambling_supported":
        return "The allowed alignments do not meaningfully improve 51^3 return-pattern memory, so the off-comb pattern weakening remains true spatial scrambling under these artifacts."
    if label == "insufficient_artifacts":
        return "Required shell-pattern frames or sector artifacts were missing."
    return "The saved artifacts show partial rescue, but not enough stable separation to assign a recoverable symmetry mechanism."


def _write_empty_outputs(root: Path, control_id: str, classification: dict[str, Any]) -> dict[str, Any]:
    summary_csv = root / "return_pattern_symmetry_summary.csv"
    pair_csv = root / "return_pair_alignment.csv"
    stability_csv = root / "transform_stability.csv"
    report_path = root / "return_pattern_symmetry_report.md"
    _write_csv(summary_csv, [], _summary_fields())
    _write_csv(pair_csv, [], _pair_fields())
    _write_csv(stability_csv, [], _stability_fields())
    report_path.write_text(
        f"# Return-Pattern Symmetry Audit: {control_id}\n\n"
        f"- Result: `{classification['label']}`\n"
        f"- Reason: {classification['reason']}\n",
        encoding="utf-8",
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": [],
        "pair_rows": [],
        "stability_rows": [],
        "harmonic_rows": [],
        "summary_csv": str(summary_csv),
        "pair_csv": str(pair_csv),
        "stability_csv": str(stability_csv),
        "harmonic_csv": "",
        "report_path": str(report_path),
        "plots": {},
        "path": str(root),
    }


def _proof_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if int(_float(row.get("grid_size"))) == 41
        and row.get("available_artifact_kind") != "none"
        and str(row.get("prediction_role")) in {"proof_candidate", "proof_41_reference", "upper_immediate_control"}
    ]
    return selected or [
        row for row in rows if int(_float(row.get("grid_size"))) == 41 and row.get("available_artifact_kind") != "none"
    ]


def _source_control_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted_roles = {
        "candidate",
        "failed_lift_51_candidate",
        "hard_cutoff_control",
        "smooth_candidate",
        "smooth_negative_phase_control",
        "hard_51_control",
        "phase_conjugate_candidate",
        "shuffled_patch_phase_control",
        "amplitude_only_control",
        "phase_only_control",
        "wrong_return_target_control",
    }
    selected = [
        row
        for row in rows
        if int(_float(row.get("grid_size"))) == 51
        and row.get("available_artifact_kind") != "none"
        and str(row.get("prediction_role")) in wanted_roles
    ]
    return selected


def _spatial_alias(variant: str) -> str:
    aliases = {
        "quarter_dt_proof_candidate_cutoff_17p94": "spatial_phase_41_proof_cutoff_17p94",
        "resolution_lift_51_candidate_phase_0p5071": "spatial_phase_51_lift_candidate_phase_0p5071",
    }
    return aliases.get(variant, variant)


def _plot_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = [
        "quarter_dt_proof_candidate_cutoff_17p94",
        "spatial_phase_41_proof_cutoff_17p94",
        "resolution_lift_51_candidate_phase_0p5071",
        "spatial_phase_51_lift_candidate_phase_0p5071",
        "smooth_envelope_51_hard_cutoff_17p9425",
        "smooth_envelope_51_smooth_cutoff_17p9425",
        "phase_conjugate_51_hard_cutoff_17p9425",
        "phase_conjugate_51_candidate_cutoff_17p9425",
        "phase_conjugate_51_shuffled_cutoff_17p9425",
    ]
    by_variant = {str(row.get("variant")): row for row in rows}
    selected = [by_variant[variant] for variant in wanted if variant in by_variant]
    for variant in sorted(by_variant):
        if variant not in wanted and len(selected) < 12:
            selected.append(by_variant[variant])
    return selected


def _short_label(variant: str) -> str:
    replacements = {
        "quarter_dt_proof_candidate_cutoff_17p94": "41 proof",
        "spatial_phase_41_proof_cutoff_17p94": "41 frames",
        "resolution_lift_51_candidate_phase_0p5071": "51 lift",
        "spatial_phase_51_lift_candidate_phase_0p5071": "51 frames",
        "smooth_envelope_51_hard_cutoff_17p9425": "smooth hard",
        "smooth_envelope_51_smooth_cutoff_17p9425": "smooth",
        "phase_conjugate_51_hard_cutoff_17p9425": "pc hard",
        "phase_conjugate_51_candidate_cutoff_17p9425": "pc candidate",
        "phase_conjugate_51_shuffled_cutoff_17p9425": "pc shuffled",
    }
    return replacements.get(variant, variant.replace("_cutoff_17p9425", "").replace("_phase_0p5071", "")[:28])


def _matrix_label(matrix: np.ndarray, kind: str) -> str:
    axes = []
    names = ("x", "y", "z")
    for row in matrix:
        idx = int(np.argmax(np.abs(row)))
        sign = "-" if row[idx] < 0 else "+"
        axes.append(f"{sign}{names[idx]}")
    prefix = "rot" if kind == "cubic_rotation" else "ref"
    return f"{prefix}_{axes[0]}_{axes[1]}_{axes[2]}"


def _sorted_frames(frames: list[FramePattern]) -> list[FramePattern]:
    return sorted(frames, key=lambda frame: (frame.peak_rank, frame.time, frame.frame_id))


def _dominant_share(labels: list[str]) -> float:
    if not labels:
        return 0.0
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return max(counts.values()) / len(labels)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _group_by(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(field)), []).append(row)
    return grouped


def _first(row: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return _float(value)
    return 0.0


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _mean(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    return float(np.mean(parsed)) if parsed.size else 0.0


def _summary_fields() -> list[str]:
    return [
        "variant",
        "return_pattern_symmetry_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "grid_size",
        "available_artifact_kind",
        "return_frame_count",
        "return_pair_count",
        "raw_pattern_memory_score",
        "sign_aligned_memory_score",
        "phase_aligned_memory_score",
        "cubic_rotation_memory_score",
        "cubic_reflection_memory_score",
        "sector_circular_shift_memory_score",
        "sector_permutation_memory_score",
        "harmonic_memory_score",
        "best_symmetry_aligned_memory_score",
        "symmetry_rescue_margin",
        "phase_or_sign_rescue_margin",
        "spatial_transform_rescue_margin",
        "dominant_transform_signature",
        "transform_stability_score",
        "transform_dominant_fraction",
        "transform_transition_stability",
        "alignment_reduces_scrambling",
        "source_controls_share_transform_signature",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "off_comb_energy_ratio",
        "spatial_pattern_leakage_score",
    ]


def _pair_fields() -> list[str]:
    return [
        "variant",
        "return_pattern_symmetry_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "grid_size",
        "artifact_kind",
        "from_frame_id",
        "to_frame_id",
        "from_peak_rank",
        "to_peak_rank",
        "from_time",
        "to_time",
        "raw_similarity",
        "raw_memory_score",
        "sign_aligned_similarity",
        "phase_aligned_similarity",
        "cubic_rotation_similarity",
        "cubic_rotation_label",
        "cubic_reflection_similarity",
        "cubic_reflection_label",
        "sector_circular_shift_similarity",
        "sector_circular_shift_label",
        "sector_permutation_similarity_penalized",
        "sector_permutation_moved_fraction",
        "harmonic_similarity",
        "best_aligned_similarity",
        "symmetry_rescue_margin",
        "dominant_transform_type",
        "dominant_transform_label",
        "matched_sample_count",
    ]


def _stability_fields() -> list[str]:
    return [
        "variant",
        "return_pattern_symmetry_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "grid_size",
        "available_artifact_kind",
        "return_pair_count",
        "dominant_transform",
        "dominant_fraction",
        "transition_stability",
        "transform_stability_score",
    ]


def _harmonic_fields() -> list[str]:
    return [
        "variant",
        "return_pattern_symmetry_classification",
        "artifact_source",
        "audit_group",
        "prediction_role",
        "grid_size",
        "from_frame_id",
        "to_frame_id",
        "from_peak_rank",
        "to_peak_rank",
        "harmonic_order",
        "harmonic_similarity",
    ]
