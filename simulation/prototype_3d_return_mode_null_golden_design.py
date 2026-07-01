"""Read-only return-mode-null golden guard design audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import load_json_config, save_json, simulation_config_from_dict
from .prototype_3d import EPSILON, Lattice3D
from .prototype_3d_golden_cubic_hybrid_anchor import (
    GoldenCubicHybridAnchorOptions,
    build_golden_cubic_hybrid_anchor_variants,
)
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_CONFIG_PATH = "configs/long_validation_peak_0_92.json"
DEFAULT_ISOCHRONOUS_ROOT = "runs/isochronous_cubic_anchor_3d_20260621_184841"
DEFAULT_CLEANUP_ROOT = "runs/isochronous_anchor_cleanup_3d_20260621_193641"
DEFAULT_SACRED_ROOT = "runs/sacred_geometry_memory_anchor_3d_20260701_154048"
DEFAULT_HYBRID_ROOT = "runs/golden_cubic_hybrid_anchor_3d_20260701_162316"

ROLE_VARIANTS = {
    "neutral": "isochronous_cubic_anchor_41_neutral_reference",
    "isochronous_anchor_0p5x": "isochronous_cubic_anchor_41_isochronous_anchor_0p5x",
    "golden_ratio_double_shell": "sacred_geometry_anchor_41_golden_ratio_double_shell_anchor",
    "best_golden_cubic_hybrid": "golden_cubic_hybrid_anchor_41_hybrid_cubic_0p5x_golden_0p5x",
}


@dataclass(frozen=True)
class ReturnModeNullGoldenDesignOptions:
    """Options for the read-only return-mode-null golden guard design."""

    output_root: str = "runs"
    config_path: str = DEFAULT_CONFIG_PATH
    isochronous_root: str = DEFAULT_ISOCHRONOUS_ROOT
    cleanup_root: str = DEFAULT_CLEANUP_ROOT
    sacred_root: str = DEFAULT_SACRED_ROOT
    hybrid_root: str = DEFAULT_HYBRID_ROOT
    max_basis_vectors: int = 5
    min_node_frames_per_desired_role: int = 4
    min_common_nodes: int = 128
    min_meaningful_raw_overlap: float = 0.10
    min_overlap_reduction_fraction: float = 0.75
    min_retained_strength_fraction: float = 0.35
    min_sector_retained_fraction: float = 0.25
    max_renormalization_multiplier: float = 3.0
    polar_bins: int = 4
    theta_bins: int = 8
    harmonic_orders: tuple[int, ...] = (0, 1, 2, 3, 4)


def run_3d_return_mode_null_golden_design(
    *,
    options: ReturnModeNullGoldenDesignOptions | None = None,
) -> dict[str, Any]:
    """Design a return-mode-null golden profile from existing artifacts only."""

    options = options or ReturnModeNullGoldenDesignOptions()
    control_id = datetime.now().strftime("return_mode_null_golden_design_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    inputs = load_return_mode_null_design_inputs(options)
    if inputs["missing_artifacts"]:
        summary_row = _insufficient_summary_row(inputs, options)
        classification = classify_return_mode_null_golden_design(summary_row, options)
        return _write_outputs(root, control_id, summary_row, [], [], [], classification, options)

    design = _compute_design(inputs, options)
    classification = classify_return_mode_null_golden_design(design["summary_row"], options)
    for collection in (design["component_rows"], design["basis_rows"], design["summary_rows"]):
        for row in collection:
            row["return_mode_null_golden_design_classification"] = classification["label"]
    return _write_outputs(
        root,
        control_id,
        design["summary_row"],
        design["component_rows"],
        design["basis_rows"],
        design["summary_rows"],
        classification,
        options,
    )


def load_return_mode_null_design_inputs(options: ReturnModeNullGoldenDesignOptions) -> dict[str, Any]:
    """Load only saved artifacts needed by the design audit."""

    roots = {
        "isochronous": Path(options.isochronous_root),
        "cleanup": Path(options.cleanup_root),
        "sacred": Path(options.sacred_root),
        "hybrid": Path(options.hybrid_root),
    }
    required_paths = {
        "isochronous_displacement": roots["isochronous"] / "isochronous_anchor_displacement.csv",
        "isochronous_angular": roots["isochronous"] / "isochronous_anchor_angular.csv",
        "sacred_displacement": roots["sacred"] / "sacred_geometry_displacement.csv",
        "sacred_angular": roots["sacred"] / "sacred_geometry_angular.csv",
        "hybrid_displacement": roots["hybrid"] / "golden_cubic_hybrid_displacement.csv",
        "hybrid_angular": roots["hybrid"] / "golden_cubic_hybrid_angular.csv",
        "cleanup_summary": roots["cleanup"] / "isochronous_anchor_cleanup_summary.csv",
        "sacred_summary": roots["sacred"] / "sacred_geometry_anchor_summary.csv",
        "hybrid_summary": roots["hybrid"] / "golden_cubic_hybrid_summary.csv",
    }
    missing = [label for label, path in required_paths.items() if not path.exists()]
    if missing:
        return {"missing_artifacts": missing, "paths": {key: str(path) for key, path in required_paths.items()}}

    desired_variants = {
        ROLE_VARIANTS["neutral"],
        ROLE_VARIANTS["isochronous_anchor_0p5x"],
    }
    golden_variants = {ROLE_VARIANTS["golden_ratio_double_shell"]}
    hybrid_variants = {ROLE_VARIANTS["best_golden_cubic_hybrid"]}
    displacement_frames: dict[str, list[dict[str, Any]]] = {}
    displacement_frames.update(_load_node_frames(required_paths["isochronous_displacement"], desired_variants, "u"))
    displacement_frames.update(_load_node_frames(required_paths["sacred_displacement"], golden_variants, "u"))
    displacement_frames.update(_load_node_frames(required_paths["hybrid_displacement"], hybrid_variants, "u"))

    angular_rows: dict[str, list[dict[str, Any]]] = {}
    angular_rows.update(_load_angular_rows(required_paths["isochronous_angular"], desired_variants))
    angular_rows.update(_load_angular_rows(required_paths["sacred_angular"], golden_variants))
    angular_rows.update(_load_angular_rows(required_paths["hybrid_angular"], hybrid_variants))

    summary_rows = {
        "cleanup": _read_csv(required_paths["cleanup_summary"]),
        "sacred": _read_csv(required_paths["sacred_summary"]),
        "hybrid": _read_csv(required_paths["hybrid_summary"]),
    }
    missing_roles = [
        role
        for role, variant in ROLE_VARIANTS.items()
        if variant not in displacement_frames or not displacement_frames[variant]
    ]
    if missing_roles:
        missing.extend([f"node_frames:{role}" for role in missing_roles])
    missing_angular = [
        role
        for role, variant in ROLE_VARIANTS.items()
        if variant not in angular_rows or not angular_rows[variant]
    ]
    if missing_angular:
        missing.extend([f"angular_sectors:{role}" for role in missing_angular])

    return {
        "missing_artifacts": missing,
        "paths": {key: str(path) for key, path in required_paths.items()},
        "displacement_frames": displacement_frames,
        "angular_rows": angular_rows,
        "summary_rows": summary_rows,
    }


def project_onto_basis(vector: np.ndarray, basis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Project a vector onto an orthonormal basis matrix."""

    v = np.asarray(vector, dtype=float).ravel()
    q = np.asarray(basis, dtype=float)
    if q.size == 0:
        return np.zeros_like(v), v.copy()
    if q.ndim == 1:
        q = q.reshape((-1, 1))
    if q.shape[0] != v.size:
        raise ValueError("basis row count must match vector length")
    projection = q @ (q.T @ v)
    return projection, v - projection


def overlap_fraction(vector: np.ndarray, basis: np.ndarray) -> float:
    """Return the fraction of vector norm captured by the basis."""

    v = np.asarray(vector, dtype=float).ravel()
    norm = float(np.linalg.norm(v))
    if norm <= EPSILON:
        return 0.0
    projection, _ = project_onto_basis(v, basis)
    return float(np.linalg.norm(projection) / norm)


def retained_strength_fraction(raw: np.ndarray, residual: np.ndarray) -> float:
    """Return retained residual norm as a fraction of raw norm."""

    raw_norm = float(np.linalg.norm(np.asarray(raw, dtype=float).ravel()))
    if raw_norm <= EPSILON:
        return 0.0
    return float(np.linalg.norm(np.asarray(residual, dtype=float).ravel()) / raw_norm)


def classify_return_mode_null_golden_design(
    summary: dict[str, Any],
    options: ReturnModeNullGoldenDesignOptions | None = None,
) -> dict[str, Any]:
    """Classify whether the null golden profile is worth one future physics candidate."""

    options = options or ReturnModeNullGoldenDesignOptions()
    missing = list(summary.get("missing_artifacts") or [])
    sufficient_artifacts = _bool(summary.get("artifacts_sufficient_for_candidate"))
    raw_overlap = _float(summary.get("raw_golden_desired_basis_overlap"))
    null_overlap = _float(summary.get("null_golden_desired_basis_overlap"))
    reduction = _float(summary.get("desired_overlap_reduction_fraction"))
    retained = _float(summary.get("retained_golden_strength_fraction"))
    sector_retained = _float(summary.get("sector_retained_strength_fraction"))
    renorm = _float(summary.get("renormalization_multiplier"))
    nontrivial = _bool(summary.get("null_profile_nontrivial"))
    checks = {
        "missing_artifacts": missing,
        "artifacts_sufficient_for_candidate": sufficient_artifacts,
        "raw_golden_desired_basis_overlap": raw_overlap,
        "null_golden_desired_basis_overlap": null_overlap,
        "desired_overlap_reduction_fraction": reduction,
        "retained_golden_strength_fraction": retained,
        "sector_retained_strength_fraction": sector_retained,
        "renormalization_multiplier": renorm,
        "null_profile_nontrivial": nontrivial,
        "min_meaningful_raw_overlap": options.min_meaningful_raw_overlap,
        "min_retained_strength_fraction": options.min_retained_strength_fraction,
        "max_renormalization_multiplier": options.max_renormalization_multiplier,
    }
    if missing or not sufficient_artifacts:
        return {
            "label": "insufficient_artifacts",
            "reason": "Required return-window node frames or sector artifacts are missing for the return-mode-null design.",
            "checks": checks,
        }
    if raw_overlap < options.min_meaningful_raw_overlap or reduction < options.min_overlap_reduction_fraction:
        return {
            "label": "null_golden_not_viable",
            "reason": "The projection did not remove a meaningful desired-return-mode overlap from the golden profile.",
            "checks": checks,
        }
    if retained < options.min_retained_strength_fraction or sector_retained < options.min_sector_retained_fraction or renorm > options.max_renormalization_multiplier:
        return {
            "label": "null_golden_not_viable",
            "reason": "The null projection removes too much of the golden structure to leave a practical passive profile.",
            "checks": checks,
        }
    if nontrivial:
        return {
            "label": "return_mode_null_golden_candidate_supported",
            "reason": "Projection removes meaningful desired-return-family overlap while retaining enough golden structure for a future fixed physics candidate.",
            "checks": checks,
        }
    return {
        "label": "null_golden_design_inconclusive",
        "reason": "Projection is possible, but the retained null profile is marginal or not stable enough to recommend.",
        "checks": checks,
    }


def _compute_design(inputs: dict[str, Any], options: ReturnModeNullGoldenDesignOptions) -> dict[str, Any]:
    frames = inputs["displacement_frames"]
    neutral_variant = ROLE_VARIANTS["neutral"]
    anchor_variant = ROLE_VARIANTS["isochronous_anchor_0p5x"]
    golden_variant = ROLE_VARIANTS["golden_ratio_double_shell"]
    hybrid_variant = ROLE_VARIANTS["best_golden_cubic_hybrid"]
    common_nodes = _common_node_indices([frames[neutral_variant], frames[anchor_variant], frames[golden_variant], frames[hybrid_variant]])
    desired_vectors, desired_labels = _desired_frame_matrix(
        [*frames[neutral_variant], *frames[anchor_variant]],
        common_nodes,
        options,
    )
    basis, basis_rows = _build_return_mode_basis(desired_vectors, desired_labels, options)
    raw_profile = _raw_golden_profile_vector(common_nodes, options)
    raw_profile = _centered(raw_profile)
    projection, null_profile = project_onto_basis(raw_profile, basis)

    raw_overlap = overlap_fraction(raw_profile, basis)
    null_overlap = overlap_fraction(null_profile, basis)
    retained = retained_strength_fraction(raw_profile, null_profile)
    reduction = 0.0 if raw_overlap <= EPSILON else max(0.0, (raw_overlap - null_overlap) / raw_overlap)
    renorm = math.inf if retained <= EPSILON else 1.0 / retained
    raw_strength = 0.5 * GoldenCubicHybridAnchorOptions().mechanism_strength
    expected_strength = raw_strength * renorm if math.isfinite(renorm) else math.inf

    component_rows = _projection_component_rows(common_nodes, raw_profile, projection, null_profile, options)
    sector_retained = _sector_retained_fraction(component_rows)
    harmonic_rows = _harmonic_basis_rows(inputs["angular_rows"], options)
    basis_rows.extend(harmonic_rows)
    for row in basis_rows:
        if row.get("basis_kind") == "node_basis":
            vector = row.pop("_basis_vector", None)
            row["raw_golden_component_overlap"] = _basis_component_overlap(raw_profile, vector)
            row["null_golden_component_overlap"] = _basis_component_overlap(null_profile, vector)

    metric_rows = _summary_metric_rows(inputs, frames, options)
    summary_row = {
        "return_mode_null_golden_design_classification": "",
        "raw_golden_desired_basis_overlap": raw_overlap,
        "null_golden_desired_basis_overlap": null_overlap,
        "desired_overlap_reduction_fraction": reduction,
        "retained_golden_strength_fraction": retained,
        "sector_retained_strength_fraction": sector_retained,
        "raw_golden_strength": raw_strength,
        "renormalization_multiplier": renorm,
        "expected_perturbation_strength_after_rms_renormalization": expected_strength,
        "common_node_count": len(common_nodes),
        "desired_frame_count": int(desired_vectors.shape[0]),
        "basis_vector_count": int(basis.shape[1]) if basis.ndim == 2 else 0,
        "null_profile_nontrivial": retained >= options.min_retained_strength_fraction and sector_retained >= options.min_sector_retained_fraction,
        "artifacts_sufficient_for_candidate": (
            len(common_nodes) >= options.min_common_nodes
            and _frame_count(frames[neutral_variant]) >= options.min_node_frames_per_desired_role
            and _frame_count(frames[anchor_variant]) >= options.min_node_frames_per_desired_role
            and bool(inputs.get("angular_rows"))
        ),
        "missing_artifacts": [],
        "neutral_frame_count": _frame_count(frames[neutral_variant]),
        "anchor_frame_count": _frame_count(frames[anchor_variant]),
        "golden_frame_count": _frame_count(frames[golden_variant]),
        "hybrid_frame_count": _frame_count(frames[hybrid_variant]),
    }
    return {
        "summary_row": summary_row,
        "component_rows": component_rows,
        "basis_rows": basis_rows,
        "summary_rows": metric_rows,
    }


def _write_outputs(
    root: Path,
    control_id: str,
    summary_row: dict[str, Any],
    component_rows: list[dict[str, Any]],
    basis_rows: list[dict[str, Any]],
    metric_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    options: ReturnModeNullGoldenDesignOptions,
) -> dict[str, Any]:
    summary_row["return_mode_null_golden_design_classification"] = classification["label"]
    for row in (component_rows + basis_rows + metric_rows):
        row["return_mode_null_golden_design_classification"] = classification["label"]

    summary_csv = root / "return_mode_null_golden_design_summary.csv"
    projection_csv = root / "golden_projection_components.csv"
    basis_csv = root / "return_mode_basis_summary.csv"
    report_path = root / "return_mode_null_golden_design_report.md"
    summary_json = root / "return_mode_null_golden_design_summary.json"
    plot_path = root / "raw_vs_null_golden_profile_coefficients.png"

    _write_csv(summary_csv, [summary_row], _summary_fields())
    _write_csv(projection_csv, component_rows, _projection_fields())
    _write_csv(basis_csv, basis_rows + metric_rows, _basis_fields())
    if component_rows:
        _plot_raw_vs_null(plot_path, component_rows)
    _write_report(report_path, control_id, summary_row, component_rows, basis_rows, metric_rows, classification, plot_path if component_rows else None)
    save_json(
        summary_json,
        {
            "control_id": control_id,
            "classification": classification,
            "summary_row": _json_safe(summary_row),
            "summary_csv": str(summary_csv),
            "golden_projection_components_csv": str(projection_csv),
            "return_mode_basis_summary_csv": str(basis_csv),
            "report_path": str(report_path),
            "plot": str(plot_path) if component_rows else "",
            "options": _json_safe(options.__dict__),
        },
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_row": summary_row,
        "component_rows": component_rows,
        "basis_rows": basis_rows,
        "metric_rows": metric_rows,
        "summary_csv": str(summary_csv),
        "golden_projection_components_csv": str(projection_csv),
        "return_mode_basis_summary_csv": str(basis_csv),
        "report_path": str(report_path),
        "summary_json": str(summary_json),
        "plot": str(plot_path) if component_rows else "",
        "path": str(root),
    }


def _load_node_frames(path: Path, variants: set[str], value_field: str) -> dict[str, list[dict[str, Any]]]:
    frames: dict[str, dict[str, dict[int, float]]] = {}
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            variant = str(row.get("variant", ""))
            if variant not in variants:
                continue
            frame_id = str(row.get("frame_id", ""))
            node_index = _int(row.get("node_index"))
            frames.setdefault(variant, {}).setdefault(frame_id, {})[node_index] = _float(row.get(value_field))
    out: dict[str, list[dict[str, Any]]] = {}
    for variant, by_frame in frames.items():
        out[variant] = [
            {"variant": variant, "frame_id": frame_id, "nodes": nodes}
            for frame_id, nodes in sorted(by_frame.items(), key=lambda item: item[0])
        ]
    return out


def _load_angular_rows(path: Path, variants: set[str]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            variant = str(row.get("variant", ""))
            if variant in variants:
                rows.setdefault(variant, []).append(dict(row))
    return rows


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _common_node_indices(frame_sets: list[list[dict[str, Any]]]) -> list[int]:
    common: set[int] | None = None
    for frames in frame_sets:
        for frame in frames[:1]:
            nodes = set(frame.get("nodes", {}).keys())
            common = nodes if common is None else common & nodes
    return sorted(common or set())


def _desired_frame_matrix(
    frames: list[dict[str, Any]],
    common_nodes: list[int],
    options: ReturnModeNullGoldenDesignOptions,
) -> tuple[np.ndarray, list[str]]:
    vectors = []
    labels = []
    for frame in frames:
        nodes = frame.get("nodes", {})
        if not nodes:
            continue
        vector = np.asarray([_float(nodes.get(node)) for node in common_nodes], dtype=float)
        vector = _centered(vector)
        norm = float(np.linalg.norm(vector))
        if norm <= EPSILON:
            continue
        vectors.append(vector / norm)
        labels.append(f"{frame.get('variant')}:{frame.get('frame_id')}")
    if not vectors:
        return np.zeros((0, len(common_nodes)), dtype=float), []
    return np.vstack(vectors), labels


def _build_return_mode_basis(
    desired_vectors: np.ndarray,
    labels: list[str],
    options: ReturnModeNullGoldenDesignOptions,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    if desired_vectors.size == 0:
        return np.zeros((desired_vectors.shape[1] if desired_vectors.ndim == 2 else 0, 0)), []
    candidates: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []
    mean_vector = _centered(np.mean(desired_vectors, axis=0))
    if np.linalg.norm(mean_vector) > EPSILON:
        candidates.append(mean_vector)
        rows.append(_basis_row("desired_mean", "mean_return_window_pattern", mean_vector, 0.0, 0.0, labels))
    centered = desired_vectors - np.mean(desired_vectors, axis=0, keepdims=True)
    try:
        _, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        singular_values = np.asarray([], dtype=float)
        vh = np.zeros((0, desired_vectors.shape[1]))
    variance = singular_values**2
    total = float(np.sum(variance))
    max_components = max(0, int(options.max_basis_vectors) - len(candidates))
    for idx in range(min(max_components, vh.shape[0])):
        vector = _centered(vh[idx])
        if np.linalg.norm(vector) <= EPSILON:
            continue
        frac = float(variance[idx] / total) if total > EPSILON else 0.0
        candidates.append(vector)
        rows.append(_basis_row(f"svd_{idx + 1}", "low_rank_return_frame_component", vector, float(singular_values[idx]), frac, labels))
    basis = _orthonormal_columns(candidates)
    for idx, row in enumerate(rows):
        row["basis_index"] = idx
        if basis.shape[1] > idx:
            row["_basis_vector"] = basis[:, idx].copy()
    return basis, rows[: basis.shape[1]]


def _raw_golden_profile_vector(common_nodes: list[int], options: ReturnModeNullGoldenDesignOptions) -> np.ndarray:
    base_config = simulation_config_from_dict(load_json_config(Path(options.config_path)))
    variants = build_golden_cubic_hybrid_anchor_variants(base_config, GoldenCubicHybridAnchorOptions())
    by_role = {getattr(config, "_golden_cubic_hybrid_role"): config for config in variants}
    neutral = Lattice3D(by_role["neutral_reference"])
    golden = Lattice3D(by_role["golden_ratio_double_shell_reference"])
    base = np.maximum(neutral.stiffness.ravel(), EPSILON)
    strength = abs(float(by_role["golden_ratio_double_shell_reference"].memory_mechanism_strength or 0.0))
    delta = golden.stiffness.ravel() / base - 1.0
    if strength > EPSILON:
        delta = delta / strength
    return np.asarray([delta[node] for node in common_nodes], dtype=float)


def _projection_component_rows(
    common_nodes: list[int],
    raw: np.ndarray,
    projection: np.ndarray,
    null: np.ndarray,
    options: ReturnModeNullGoldenDesignOptions,
) -> list[dict[str, Any]]:
    base_config = simulation_config_from_dict(load_json_config(Path(options.config_path)))
    variants = build_golden_cubic_hybrid_anchor_variants(base_config, GoldenCubicHybridAnchorOptions())
    neutral_config = next(config for config in variants if getattr(config, "_golden_cubic_hybrid_role") == "neutral_reference")
    lattice = Lattice3D(neutral_config)
    coords = lattice.coords
    flat_x = coords["x"].ravel()
    flat_y = coords["y"].ravel()
    flat_z = coords["z"].ravel()
    flat_radius = np.maximum(coords["radius"].ravel(), neutral_config.dx)
    raw_sector = _sector_coefficients(common_nodes, raw, flat_x, flat_y, flat_z, flat_radius, options)
    projection_sector = _sector_coefficients(common_nodes, projection, flat_x, flat_y, flat_z, flat_radius, options)
    null_sector = _sector_coefficients(common_nodes, null, flat_x, flat_y, flat_z, flat_radius, options)
    rows = []
    for key in sorted(raw_sector):
        polar_bin, theta_bin = key
        rows.append(
            {
                "component_kind": "angular_sector",
                "component_label": f"polar_{polar_bin}_theta_{theta_bin}",
                "polar_bin": polar_bin,
                "theta_bin": theta_bin,
                "harmonic_order": "",
                "raw_golden_coeff": raw_sector.get(key, 0.0),
                "projected_desired_coeff": projection_sector.get(key, 0.0),
                "null_golden_coeff": null_sector.get(key, 0.0),
            }
        )
    for order in options.harmonic_orders:
        raw_coeff = _harmonic_from_sector(raw_sector, order, options)
        projection_coeff = _harmonic_from_sector(projection_sector, order, options)
        null_coeff = _harmonic_from_sector(null_sector, order, options)
        rows.append(
            {
                "component_kind": "theta_harmonic",
                "component_label": f"m_{order}",
                "polar_bin": "",
                "theta_bin": "",
                "harmonic_order": order,
                "raw_golden_coeff": abs(raw_coeff),
                "projected_desired_coeff": abs(projection_coeff),
                "null_golden_coeff": abs(null_coeff),
            }
        )
    return rows


def _sector_coefficients(
    common_nodes: list[int],
    values: np.ndarray,
    flat_x: np.ndarray,
    flat_y: np.ndarray,
    flat_z: np.ndarray,
    flat_radius: np.ndarray,
    options: ReturnModeNullGoldenDesignOptions,
) -> dict[tuple[int, int], float]:
    bins: dict[tuple[int, int], list[float]] = {}
    for node, value in zip(common_nodes, values):
        radius = max(float(flat_radius[node]), EPSILON)
        theta = math.atan2(float(flat_y[node]), float(flat_x[node]))
        if theta < 0.0:
            theta += 2.0 * math.pi
        polar = math.acos(float(np.clip(flat_z[node] / radius, -1.0, 1.0)))
        polar_bin = min(int(polar / math.pi * options.polar_bins), options.polar_bins - 1)
        theta_bin = min(int(theta / (2.0 * math.pi) * options.theta_bins), options.theta_bins - 1)
        bins.setdefault((polar_bin, theta_bin), []).append(float(value))
    return {key: float(np.mean(vals)) for key, vals in bins.items()}


def _harmonic_from_sector(sectors: dict[tuple[int, int], float], order: int, options: ReturnModeNullGoldenDesignOptions) -> complex:
    total = 0.0j
    count = 0
    for (_, theta_bin), value in sectors.items():
        theta = (theta_bin + 0.5) / max(options.theta_bins, 1) * 2.0 * math.pi
        total += complex(value) * np.exp(-1j * float(order) * theta)
        count += 1
    return total / max(count, 1)


def _harmonic_basis_rows(
    angular_rows: dict[str, list[dict[str, Any]]],
    options: ReturnModeNullGoldenDesignOptions,
) -> list[dict[str, Any]]:
    rows = []
    role_by_variant = {variant: role for role, variant in ROLE_VARIANTS.items()}
    for variant, source_rows in angular_rows.items():
        sectors = _mean_complex_sector_pattern(source_rows)
        harmonic_values = {order: _harmonic_from_complex_sector(sectors, order, options) for order in options.harmonic_orders}
        dominant_order = max(harmonic_values, key=lambda order: abs(harmonic_values[order])) if harmonic_values else 0
        for order, coeff in harmonic_values.items():
            rows.append(
                {
                    "basis_kind": "angular_harmonic",
                    "basis_label": f"{role_by_variant.get(variant, variant)}_m_{order}",
                    "basis_index": "",
                    "source": role_by_variant.get(variant, variant),
                    "singular_value": "",
                    "explained_variance_fraction": "",
                    "source_frame_count": _angular_frame_count(source_rows),
                    "basis_norm": abs(coeff),
                    "raw_golden_component_overlap": "",
                    "null_golden_component_overlap": "",
                    "dominant_harmonic_order": dominant_order,
                    "harmonic_order": order,
                    "harmonic_magnitude": abs(coeff),
                    "harmonic_phase_cycles": (math.atan2(coeff.imag, coeff.real) / (2.0 * math.pi)) % 1.0 if abs(coeff) > EPSILON else 0.0,
                }
            )
    return rows


def _mean_complex_sector_pattern(rows: list[dict[str, Any]]) -> dict[tuple[int, int], complex]:
    buckets: dict[tuple[int, int], list[complex]] = {}
    for row in rows:
        polar_bin = _int(row.get("polar_bin"))
        theta_bin = _int(row.get("theta_bin"))
        amp = math.sqrt(max(_float(row.get("shell_energy")), 0.0)) * max(_float(row.get("phase_coherence")), 0.0)
        phase = _float(row.get("phase_mean_cycles")) * 2.0 * math.pi
        buckets.setdefault((polar_bin, theta_bin), []).append(amp * complex(math.cos(phase), math.sin(phase)))
    return {key: complex(np.mean(values)) for key, values in buckets.items() if values}


def _harmonic_from_complex_sector(sectors: dict[tuple[int, int], complex], order: int, options: ReturnModeNullGoldenDesignOptions) -> complex:
    total = 0.0j
    count = 0
    for (_, theta_bin), value in sectors.items():
        theta = (theta_bin + 0.5) / max(options.theta_bins, 1) * 2.0 * math.pi
        total += value * np.exp(-1j * float(order) * theta)
        count += 1
    return total / max(count, 1)


def _summary_metric_rows(inputs: dict[str, Any], frames: dict[str, list[dict[str, Any]]], options: ReturnModeNullGoldenDesignOptions) -> list[dict[str, Any]]:
    rows = []
    summary_by_role = _summary_by_role(inputs.get("summary_rows", {}))
    for role, variant in ROLE_VARIANTS.items():
        row = dict(summary_by_role.get(role, {}))
        rows.append(
            {
                "basis_kind": "artifact_summary",
                "basis_label": role,
                "basis_index": "",
                "source": variant,
                "singular_value": "",
                "explained_variance_fraction": "",
                "source_frame_count": _frame_count(frames.get(variant, [])),
                "basis_norm": "",
                "raw_golden_component_overlap": "",
                "null_golden_component_overlap": "",
                "dominant_harmonic_order": "",
                "harmonic_order": "",
                "harmonic_magnitude": "",
                "harmonic_phase_cycles": "",
                "pattern_memory_score": row.get("pattern_memory_score", ""),
                "strict_count": _strict_count(row),
                "return_timing_comb_score": row.get("return_timing_comb_score", ""),
                "off_comb_energy_ratio": row.get("off_comb_energy_ratio", ""),
            }
        )
    return rows


def _summary_by_role(summary_sets: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rows in summary_sets.values():
        for row in rows:
            role = str(row.get("mechanism_role", ""))
            if role == "neutral_reference":
                out["neutral"] = row
            elif role in {"isochronous_anchor_0p5x", "isochronous_anchor_0p5x_reference"}:
                out["isochronous_anchor_0p5x"] = row
            elif role == "golden_ratio_double_shell_anchor" or role == "golden_ratio_double_shell_reference":
                out["golden_ratio_double_shell"] = row
            elif role == "hybrid_cubic_0p5x_golden_0p5x":
                out["best_golden_cubic_hybrid"] = row
    return out


def _strict_count(row: dict[str, Any]) -> str:
    major = row.get("conservative_major_peaks", "")
    refocus = row.get("conservative_refocus_peaks", "")
    return f"{major}/{refocus}" if major != "" or refocus != "" else ""


def _basis_row(label: str, source: str, vector: np.ndarray, singular_value: float, explained: float, labels: list[str]) -> dict[str, Any]:
    return {
        "return_mode_null_golden_design_classification": "",
        "basis_kind": "node_basis",
        "basis_label": label,
        "basis_index": "",
        "source": source,
        "singular_value": singular_value,
        "explained_variance_fraction": explained,
        "source_frame_count": len(labels),
        "basis_norm": float(np.linalg.norm(vector)),
        "raw_golden_component_overlap": "",
        "null_golden_component_overlap": "",
        "dominant_harmonic_order": "",
        "harmonic_order": "",
        "harmonic_magnitude": "",
        "harmonic_phase_cycles": "",
        "_basis_vector": vector,
    }


def _orthonormal_columns(vectors: list[np.ndarray]) -> np.ndarray:
    columns: list[np.ndarray] = []
    for vector in vectors:
        v = np.asarray(vector, dtype=float).ravel().copy()
        for column in columns:
            v -= float(np.dot(column, v)) * column
        norm = float(np.linalg.norm(v))
        if norm > EPSILON:
            columns.append(v / norm)
    if not columns:
        length = vectors[0].size if vectors else 0
        return np.zeros((length, 0), dtype=float)
    return np.column_stack(columns)


def _basis_component_overlap(vector: np.ndarray, basis_vector: Any) -> float | str:
    if basis_vector is None:
        return ""
    v = np.asarray(vector, dtype=float).ravel()
    b = np.asarray(basis_vector, dtype=float).ravel()
    denom = float(np.linalg.norm(v) * np.linalg.norm(b))
    if denom <= EPSILON:
        return 0.0
    return float(abs(np.dot(v, b)) / denom)


def _sector_retained_fraction(rows: list[dict[str, Any]]) -> float:
    raw = []
    null = []
    for row in rows:
        if row.get("component_kind") != "angular_sector":
            continue
        raw.append(_float(row.get("raw_golden_coeff")))
        null.append(_float(row.get("null_golden_coeff")))
    if not raw:
        return 0.0
    raw_arr = np.asarray(raw, dtype=float)
    null_arr = np.asarray(null, dtype=float)
    norm = float(np.linalg.norm(raw_arr))
    if norm <= EPSILON:
        return 0.0
    return float(np.linalg.norm(null_arr) / norm)


def _insufficient_summary_row(inputs: dict[str, Any], options: ReturnModeNullGoldenDesignOptions) -> dict[str, Any]:
    return {
        "return_mode_null_golden_design_classification": "insufficient_artifacts",
        "raw_golden_desired_basis_overlap": 0.0,
        "null_golden_desired_basis_overlap": 0.0,
        "desired_overlap_reduction_fraction": 0.0,
        "retained_golden_strength_fraction": 0.0,
        "sector_retained_strength_fraction": 0.0,
        "raw_golden_strength": 0.5 * GoldenCubicHybridAnchorOptions().mechanism_strength,
        "renormalization_multiplier": math.inf,
        "expected_perturbation_strength_after_rms_renormalization": math.inf,
        "common_node_count": 0,
        "desired_frame_count": 0,
        "basis_vector_count": 0,
        "null_profile_nontrivial": False,
        "artifacts_sufficient_for_candidate": False,
        "missing_artifacts": list(inputs.get("missing_artifacts") or []),
        "neutral_frame_count": 0,
        "anchor_frame_count": 0,
        "golden_frame_count": 0,
        "hybrid_frame_count": 0,
    }


def _plot_raw_vs_null(path: Path, rows: list[dict[str, Any]]) -> None:
    sector_rows = [row for row in rows if row.get("component_kind") == "angular_sector"]
    labels = [str(row.get("component_label")) for row in sector_rows]
    raw = [_float(row.get("raw_golden_coeff")) for row in sector_rows]
    null = [_float(row.get("null_golden_coeff")) for row in sector_rows]
    x = np.arange(len(labels))
    plt.figure(figsize=(12, 5))
    plt.bar(x - 0.2, raw, width=0.4, label="raw golden")
    plt.bar(x + 0.2, null, width=0.4, label="null golden")
    plt.xticks(x, labels, rotation=90, fontsize=6)
    plt.ylabel("sector coefficient")
    plt.title("Raw vs return-mode-null golden profile coefficients")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _write_report(
    path: Path,
    control_id: str,
    summary: dict[str, Any],
    component_rows: list[dict[str, Any]],
    basis_rows: list[dict[str, Any]],
    metric_rows: list[dict[str, Any]],
    classification: dict[str, Any],
    plot_path: Path | None,
) -> None:
    lines = [
        f"# Return-Mode-Null Golden Design: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        "",
        "## Guardrails",
        "",
        "- This is a read-only design audit; it does not run new physics.",
        "- It uses saved return-window node frames and angular-sector artifacts only.",
        "- It does not reopen additive golden/cubic hybrid tuning.",
        "",
        "## Projection Summary",
        "",
        f"- Raw golden desired-basis overlap: `{_format(summary.get('raw_golden_desired_basis_overlap'))}`",
        f"- Null golden desired-basis overlap: `{_format(summary.get('null_golden_desired_basis_overlap'))}`",
        f"- Desired-overlap reduction: `{_format(summary.get('desired_overlap_reduction_fraction'))}`",
        f"- Retained golden strength: `{_format(summary.get('retained_golden_strength_fraction'))}`",
        f"- Sector retained strength: `{_format(summary.get('sector_retained_strength_fraction'))}`",
        f"- RMS renormalization multiplier: `{_format(summary.get('renormalization_multiplier'))}`",
        f"- Expected perturbation strength after RMS renormalization: `{_format(summary.get('expected_perturbation_strength_after_rms_renormalization'))}`",
        f"- Common shell nodes: `{summary.get('common_node_count')}`",
        f"- Desired return frames: `{summary.get('desired_frame_count')}`",
        f"- Basis vectors: `{summary.get('basis_vector_count')}`",
        f"- Nontrivial null profile: `{summary.get('null_profile_nontrivial')}`",
        f"- Artifacts sufficient for candidate design: `{summary.get('artifacts_sufficient_for_candidate')}`",
        "",
        "## Source Rows",
        "",
        "| Role | Frames | Memory | Strict | Comb | Off-comb |",
        "| --- | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in metric_rows:
        if row.get("basis_kind") != "artifact_summary":
            continue
        lines.append(
            f"| {row.get('basis_label')} | {row.get('source_frame_count')} | "
            f"{_format(row.get('pattern_memory_score'))} | {row.get('strict_count')} | "
            f"{_format(row.get('return_timing_comb_score'))} | {_format(row.get('off_comb_energy_ratio'))} |"
        )
    lines.extend(
        [
            "",
            "## Basis",
            "",
            "| Basis | Source | Frames | Singular | Explained | Raw overlap | Null overlap |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in basis_rows:
        if row.get("basis_kind") != "node_basis":
            continue
        lines.append(
            f"| {row.get('basis_label')} | {row.get('source')} | {row.get('source_frame_count')} | "
            f"{_format(row.get('singular_value'))} | {_format(row.get('explained_variance_fraction'))} | "
            f"{_format(row.get('raw_golden_component_overlap'))} | {_format(row.get('null_golden_component_overlap'))} |"
        )
    if plot_path:
        lines.extend(["", "## Plot", "", f"- `{plot_path.name}`"])
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `return_mode_null_golden_design_summary.csv`",
            "- `golden_projection_components.csv`",
            "- `return_mode_basis_summary.csv`",
            "- `return_mode_null_golden_design_summary.json`",
            "- `return_mode_null_golden_design_report.md`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _summary_fields() -> list[str]:
    return [
        "return_mode_null_golden_design_classification",
        "raw_golden_desired_basis_overlap",
        "null_golden_desired_basis_overlap",
        "desired_overlap_reduction_fraction",
        "retained_golden_strength_fraction",
        "sector_retained_strength_fraction",
        "raw_golden_strength",
        "renormalization_multiplier",
        "expected_perturbation_strength_after_rms_renormalization",
        "common_node_count",
        "desired_frame_count",
        "basis_vector_count",
        "null_profile_nontrivial",
        "artifacts_sufficient_for_candidate",
        "missing_artifacts",
        "neutral_frame_count",
        "anchor_frame_count",
        "golden_frame_count",
        "hybrid_frame_count",
    ]


def _projection_fields() -> list[str]:
    return [
        "return_mode_null_golden_design_classification",
        "component_kind",
        "component_label",
        "polar_bin",
        "theta_bin",
        "harmonic_order",
        "raw_golden_coeff",
        "projected_desired_coeff",
        "null_golden_coeff",
    ]


def _basis_fields() -> list[str]:
    return [
        "return_mode_null_golden_design_classification",
        "basis_kind",
        "basis_label",
        "basis_index",
        "source",
        "singular_value",
        "explained_variance_fraction",
        "source_frame_count",
        "basis_norm",
        "raw_golden_component_overlap",
        "null_golden_component_overlap",
        "dominant_harmonic_order",
        "harmonic_order",
        "harmonic_magnitude",
        "harmonic_phase_cycles",
        "pattern_memory_score",
        "strict_count",
        "return_timing_comb_score",
        "off_comb_energy_ratio",
    ]


def _frame_count(frames: list[dict[str, Any]]) -> int:
    return len({str(frame.get("frame_id")) for frame in frames})


def _angular_frame_count(rows: list[dict[str, Any]]) -> int:
    return len({str(row.get("frame_id")) for row in rows})


def _centered(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        return arr
    return arr - float(np.mean(arr))


def _float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "supported"}
    return bool(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value

