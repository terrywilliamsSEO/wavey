"""Read-only survivor-bias audit for the cubic-memory tradeoff map."""

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

from .prototype_3d import EPSILON
from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_TRADEOFF_ROOT = "runs/cubic_memory_tradeoff_map_3d_20260621_142657"
DEFAULT_SPATIAL_MEMORY_LAB_ROOT = "runs/spatial_memory_mechanism_lab_3d_20260621_103028"


@dataclass(frozen=True)
class CubicMemorySurvivorBiasAuditOptions:
    """Options for the read-only cubic-memory survivor-bias audit."""

    output_root: str = "runs"
    tradeoff_root: str = DEFAULT_TRADEOFF_ROOT
    spatial_memory_lab_root: str = DEFAULT_SPATIAL_MEMORY_LAB_ROOT
    min_same_window_gain: float = 0.025
    survivor_gain_fraction_threshold: float = 0.35
    min_neutral_window_pair_coverage: float = 0.50


@dataclass
class ReturnFrame:
    """One saved shell return frame from an existing artifact."""

    variant: str
    frame_id: str
    peak_rank: int
    time: float
    shell_energy: float
    values: dict[int, float]


@dataclass(frozen=True)
class NeutralWindow:
    """A predicted neutral return window bounded by adjacent neutral return midpoints."""

    index: int
    center_time: float
    lower_time: float
    upper_time: float


def run_3d_cubic_memory_survivor_bias_audit(
    *,
    options: CubicMemorySurvivorBiasAuditOptions | None = None,
) -> dict[str, Any]:
    """Audit saved cubic-memory artifacts without running new physics."""

    options = options or CubicMemorySurvivorBiasAuditOptions()
    control_id = datetime.now().strftime("cubic_memory_survivor_bias_audit_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    artifact = load_cubic_memory_tradeoff_artifact(options.tradeoff_root)
    if not artifact["valid"]:
        classification = classify_cubic_memory_survivor_bias([], options)
        return _write_empty_outputs(root, control_id, classification, artifact["missing"])

    summary_rows, matched_rows, memory_index_rows = compute_survivor_bias_metrics(
        artifact["tradeoff_summary_rows"],
        artifact["frames_by_variant"],
        options,
    )
    classification = classify_cubic_memory_survivor_bias(summary_rows, options)
    for collection in (summary_rows, matched_rows, memory_index_rows):
        for row in collection:
            row["cubic_memory_survivor_bias_classification"] = classification["label"]

    summary_csv = root / "cubic_memory_survivor_bias_summary.csv"
    matched_csv = root / "matched_return_memory.csv"
    index_csv = root / "memory_by_return_index.csv"
    report_path = root / "cubic_memory_survivor_bias_report.md"
    summary_json = root / "cubic_memory_survivor_bias_summary.json"
    plots = {
        "memory_by_return_index": root / "memory_by_return_index_plot.png",
        "matched_window_memory": root / "matched_window_memory_plot.png",
        "memory_vs_strict_count": root / "memory_vs_strict_count_plot.png",
    }

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(matched_csv, matched_rows, _matched_fields())
    _write_csv(index_csv, memory_index_rows, _index_fields())
    _write_plots(plots, summary_rows, memory_index_rows)
    _write_report(report_path, control_id, classification, summary_rows, plots)
    summary_json.write_text(
        json.dumps(
            {
                "control_id": control_id,
                "classification": classification,
                "summary_csv": str(summary_csv),
                "matched_return_memory_csv": str(matched_csv),
                "memory_by_return_index_csv": str(index_csv),
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
        "matched_rows": matched_rows,
        "memory_by_return_index_rows": memory_index_rows,
        "summary_csv": str(summary_csv),
        "matched_return_memory_csv": str(matched_csv),
        "memory_by_return_index_csv": str(index_csv),
        "report_path": str(report_path),
        "summary_json": str(summary_json),
        "plots": {key: str(value) for key, value in plots.items()},
        "path": str(root),
    }


def load_cubic_memory_tradeoff_artifact(tradeoff_root: str | Path) -> dict[str, Any]:
    """Load the saved tradeoff summary and shell displacement frames."""

    root = Path(tradeoff_root)
    summary_rows = _read_csv(root / "cubic_memory_tradeoff_summary.csv")
    frame_rows = _read_csv(root / "cubic_memory_frames.csv")
    displacement_rows = _read_csv(root / "cubic_memory_displacement.csv")
    missing = []
    if not summary_rows:
        missing.append("cubic_memory_tradeoff_summary.csv")
    if not frame_rows:
        missing.append("cubic_memory_frames.csv")
    if not displacement_rows:
        missing.append("cubic_memory_displacement.csv")
    frames_by_variant = build_return_frames(displacement_rows, frame_rows) if not missing else {}
    if frames_by_variant and "cubic_memory_tradeoff_41_neutral_reference" not in frames_by_variant:
        missing.append("neutral_reference_frames")
    return {
        "valid": not missing,
        "missing": missing,
        "tradeoff_summary_rows": summary_rows,
        "frames_by_variant": frames_by_variant,
    }


def build_return_frames(
    displacement_rows: list[dict[str, Any]],
    frame_rows: list[dict[str, Any]] | None = None,
) -> dict[str, list[ReturnFrame]]:
    """Build compact return-frame vectors from saved node displacement rows."""

    metadata: dict[tuple[str, str], dict[str, Any]] = {}
    for row in frame_rows or []:
        metadata[(str(row.get("variant")), str(row.get("frame_id")))] = row

    raw: dict[tuple[str, str], dict[str, Any]] = {}
    for row in displacement_rows:
        variant = str(row.get("variant"))
        frame_id = str(row.get("frame_id"))
        key = (variant, frame_id)
        meta = metadata.get(key, row)
        frame = raw.setdefault(
            key,
            {
                "variant": variant,
                "frame_id": frame_id,
                "peak_rank": int(round(_float(meta.get("peak_rank")))),
                "time": _float(meta.get("time")),
                "shell_energy": _float(meta.get("shell_energy")),
                "values": {},
            },
        )
        node_index = int(round(_float(row.get("node_index"))))
        frame["values"][node_index] = _float(row.get("u"))

    grouped: dict[str, list[ReturnFrame]] = {}
    for frame in raw.values():
        grouped.setdefault(str(frame["variant"]), []).append(
            ReturnFrame(
                variant=str(frame["variant"]),
                frame_id=str(frame["frame_id"]),
                peak_rank=int(frame["peak_rank"]),
                time=float(frame["time"]),
                shell_energy=float(frame["shell_energy"]),
                values=dict(frame["values"]),
            )
        )
    return {variant: _sort_frames(frames) for variant, frames in grouped.items()}


def compute_survivor_bias_metrics(
    tradeoff_summary_rows: list[dict[str, Any]],
    frames_by_variant: dict[str, list[ReturnFrame]],
    options: CubicMemorySurvivorBiasAuditOptions | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Compute survivor, equal-index, and neutral-window memory metrics."""

    options = options or CubicMemorySurvivorBiasAuditOptions()
    summary_by_variant = {str(row.get("variant")): row for row in tradeoff_summary_rows}
    variants = [str(row.get("variant")) for row in tradeoff_summary_rows if str(row.get("variant")) in frames_by_variant]
    neutral_variant = _neutral_variant(variants)
    neutral_frames = frames_by_variant.get(neutral_variant, [])
    windows = neutral_return_windows(neutral_frames)
    assignments = {
        variant: assign_frames_to_neutral_windows(frames, windows)
        for variant, frames in frames_by_variant.items()
        if variant in variants
    }
    selected_variants = [variant for variant in variants if frames_by_variant.get(variant)]
    min_frame_count = min((len(frames_by_variant[variant]) for variant in selected_variants), default=0)
    shared_window_indices = sorted(set.intersection(*(set(assignments.get(variant, {})) for variant in selected_variants))) if selected_variants else []

    matched_rows: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    metric_cache: dict[str, dict[str, Any]] = {}

    for variant in variants:
        summary = summary_by_variant[variant]
        frames = frames_by_variant[variant]
        all_pairs = _surviving_peak_pairs(variant, frames, method="all_available")
        first_pairs = _surviving_peak_pairs(variant, frames[:min_frame_count], method="first_n_return_index")
        neutral_pairs = _neutral_window_pairs(variant, assignments.get(variant, {}), windows, "neutral_predicted_window")
        shared_pairs = _shared_window_pairs(variant, assignments.get(variant, {}), shared_window_indices)
        matched_rows.extend(all_pairs)
        matched_rows.extend(first_pairs)
        matched_rows.extend(neutral_pairs)
        matched_rows.extend(shared_pairs)

        available_neutral_pairs = [row for row in neutral_pairs if _bool(row.get("pair_available"))]
        all_scores = [_float(row.get("memory_score")) for row in all_pairs if _bool(row.get("pair_available"))]
        first_scores = [_float(row.get("memory_score")) for row in first_pairs if _bool(row.get("pair_available"))]
        neutral_scores = [_float(row.get("memory_score")) for row in available_neutral_pairs]
        shared_scores = [_float(row.get("memory_score")) for row in shared_pairs if _bool(row.get("pair_available"))]
        assigned_count = len(assignments.get(variant, {}))
        metric_cache[variant] = {
            "variant": variant,
            "mechanism_role": summary.get("mechanism_role"),
            "mechanism_profile": summary.get("mechanism_profile"),
            "mechanism_strength_factor": summary.get("mechanism_strength_factor"),
            "split_orientation": summary.get("split_orientation"),
            "matched_random_role": summary.get("matched_random_role"),
            "matched_random_variant": _matched_random_variant(str(summary.get("matched_random_role") or ""), tradeoff_summary_rows),
            "return_frame_count": len(frames),
            "neutral_return_window_count": len(windows),
            "assigned_neutral_window_count": assigned_count,
            "neutral_window_return_coverage": assigned_count / max(len(windows), 1),
            "all_available_pair_count": len(all_scores),
            "all_available_memory": _mean(all_scores),
            "all_available_memory_std": _std(all_scores),
            "first_n_frame_count": min_frame_count,
            "first_n_pair_count": len(first_scores),
            "first_n_return_index_memory": _mean(first_scores),
            "neutral_window_pair_count": len(neutral_scores),
            "neutral_window_possible_pair_count": max(len(windows) - 1, 0),
            "neutral_window_pair_coverage": len(neutral_scores) / max(len(windows) - 1, 1),
            "neutral_predicted_window_memory": _mean(neutral_scores),
            "shared_window_count": len(shared_window_indices),
            "shared_window_pair_count": len(shared_scores),
            "shared_window_memory": _mean(shared_scores),
            "late_return_memory_decay": late_return_memory_decay(available_neutral_pairs),
            "strict_major_peaks": summary.get("conservative_major_peaks"),
            "strict_refocus_peaks": summary.get("conservative_refocus_peaks"),
            "default_major_peaks": summary.get("default_major_peaks_at_0p30"),
            "default_refocus_peaks": summary.get("default_refocus_peaks_at_0p30"),
            "loose_major_peaks": summary.get("loose_major_peaks_at_0p25"),
            "loose_refocus_peaks": summary.get("loose_refocus_peaks_at_0p25"),
            "return_timing_comb_score": summary.get("return_timing_comb_score"),
            "off_comb_energy_ratio": summary.get("off_comb_energy_ratio"),
            "clean_gates_passed": summary.get("clean_gates_passed"),
        }

        by_all = {int(_float(row.get("return_pair_index"))): row for row in all_pairs}
        by_first = {int(_float(row.get("return_pair_index"))): row for row in first_pairs}
        by_neutral = {int(_float(row.get("neutral_window_from_index"))): row for row in neutral_pairs}
        for index in range(1, max(len(windows), len(all_pairs) + 1)):
            all_row = by_all.get(index, {})
            first_row = by_first.get(index, {})
            neutral_row = by_neutral.get(index, {})
            index_rows.append(
                {
                    "variant": variant,
                    "mechanism_role": summary.get("mechanism_role"),
                    "return_pair_index": index,
                    "all_available_memory": all_row.get("memory_score", ""),
                    "first_n_return_index_memory": first_row.get("memory_score", ""),
                    "neutral_window_memory": neutral_row.get("memory_score", ""),
                    "neutral_window_pair_available": neutral_row.get("pair_available", False),
                    "neutral_window_from_index": neutral_row.get("neutral_window_from_index", index),
                    "neutral_window_to_index": neutral_row.get("neutral_window_to_index", index + 1),
                    "neutral_window_from_time": neutral_row.get("neutral_window_from_time", ""),
                    "neutral_window_to_time": neutral_row.get("neutral_window_to_time", ""),
                    "from_time": neutral_row.get("from_time", all_row.get("from_time", "")),
                    "to_time": neutral_row.get("to_time", all_row.get("to_time", "")),
                }
            )

    summary_rows = list(metric_cache.values())
    _attach_deltas(summary_rows)
    _attach_relationship_fields(summary_rows)
    return summary_rows, matched_rows, index_rows


def neutral_return_windows(neutral_frames: list[ReturnFrame]) -> list[NeutralWindow]:
    """Build neutral predicted return windows from adjacent neutral-return midpoints."""

    frames = _sort_frames(neutral_frames)
    windows: list[NeutralWindow] = []
    for idx, frame in enumerate(frames):
        lower = -math.inf if idx == 0 else 0.5 * (frames[idx - 1].time + frame.time)
        upper = math.inf if idx == len(frames) - 1 else 0.5 * (frame.time + frames[idx + 1].time)
        windows.append(NeutralWindow(index=idx + 1, center_time=frame.time, lower_time=lower, upper_time=upper))
    return windows


def assign_frames_to_neutral_windows(
    frames: list[ReturnFrame],
    windows: list[NeutralWindow],
) -> dict[int, ReturnFrame]:
    """Assign each saved frame to the nearest neutral predicted return window."""

    candidates: dict[int, list[ReturnFrame]] = {}
    for frame in frames:
        for window in windows:
            if window.lower_time <= frame.time < window.upper_time:
                candidates.setdefault(window.index, []).append(frame)
                break
    assigned: dict[int, ReturnFrame] = {}
    by_index = {window.index: window for window in windows}
    for index, frame_candidates in candidates.items():
        window = by_index[index]
        assigned[index] = min(
            frame_candidates,
            key=lambda frame: (abs(frame.time - window.center_time), -frame.shell_energy, frame.frame_id),
        )
    return assigned


def late_return_memory_decay(pair_rows: list[dict[str, Any]]) -> float:
    """Return late minus early neutral-window memory."""

    rows = [row for row in pair_rows if _bool(row.get("pair_available"))]
    if len(rows) < 4:
        return 0.0
    rows = sorted(rows, key=lambda row: _float(row.get("neutral_window_from_index")))
    split = max(1, len(rows) // 3)
    early = [_float(row.get("memory_score")) for row in rows[:split]]
    late = [_float(row.get("memory_score")) for row in rows[-split:]]
    return _mean(late) - _mean(early)


def classify_cubic_memory_survivor_bias(
    rows: list[dict[str, Any]],
    options: CubicMemorySurvivorBiasAuditOptions | None = None,
) -> dict[str, Any]:
    """Classify whether cubic memory is same-window gain or survivor bias."""

    options = options or CubicMemorySurvivorBiasAuditOptions()
    neutral = next((row for row in rows if row.get("mechanism_role") == "neutral_reference"), None)
    random_controls = [row for row in rows if str(row.get("mechanism_role")).startswith("random_equivalent")]
    cubic_rows = [
        row
        for row in rows
        if row.get("mechanism_role") not in {"neutral_reference"}
        and not str(row.get("mechanism_role")).startswith("random_equivalent")
    ]
    missing = []
    if neutral is None:
        missing.append("neutral_reference")
    if not random_controls:
        missing.append("randomized_controls")
    if not cubic_rows:
        missing.append("cubic_rows")
    if any(_float(row.get("return_frame_count")) < 2 for row in rows):
        missing.append("return_frames")
    if missing:
        return {
            "label": "insufficient_artifacts",
            "reason": "Required cubic tradeoff return-window/frame artifacts were missing.",
            "checks": {"missing_required_artifacts": missing},
        }

    candidates = [
        row
        for row in cubic_rows
        if row.get("matched_random_variant")
        and _bool(row.get("clean_gates_passed"))
        and _float(row.get("all_available_memory_delta_vs_neutral")) > options.min_same_window_gain
        and _float(row.get("all_available_memory_delta_vs_matched_random")) > options.min_same_window_gain
    ]
    real = [
        row
        for row in candidates
        if _float(row.get("neutral_window_pair_coverage")) >= options.min_neutral_window_pair_coverage
        and _float(row.get("neutral_predicted_window_memory_delta_vs_neutral")) > options.min_same_window_gain
        and _float(row.get("neutral_predicted_window_memory_delta_vs_matched_random")) > options.min_same_window_gain
    ]
    survivor = []
    for row in candidates:
        all_gain = min(_float(row.get("all_available_memory_delta_vs_neutral")), _float(row.get("all_available_memory_delta_vs_matched_random")))
        same_gain = min(_float(row.get("neutral_predicted_window_memory_delta_vs_neutral")), _float(row.get("neutral_predicted_window_memory_delta_vs_matched_random")))
        gain_fraction = same_gain / max(all_gain, EPSILON)
        late_gain = min(_float(row.get("late_return_memory_decay_delta_vs_neutral")), _float(row.get("late_return_memory_decay_delta_vs_matched_random")))
        if (
            same_gain <= options.min_same_window_gain
            or gain_fraction < options.survivor_gain_fraction_threshold
            or late_gain <= 0.0
        ):
            survivor.append(row)
    best_pool = real or survivor or candidates or cubic_rows
    best = max(
        best_pool,
        key=lambda row: (
            _float(row.get("all_available_delta_vs_neutral")),
            _float(row.get("neutral_predicted_window_memory_delta_vs_neutral")),
        ),
        default={},
    )
    checks = {
        "neutral_all_available_memory": neutral.get("all_available_memory"),
        "neutral_first_n_return_index_memory": neutral.get("first_n_return_index_memory"),
        "neutral_predicted_window_memory": neutral.get("neutral_predicted_window_memory"),
        "surviving_memory_candidate_count": len(candidates),
        "same_window_candidate_count": len(real),
        "survivor_bias_candidate_count": len(survivor),
        "best_role": best.get("mechanism_role"),
        "best_variant": best.get("variant"),
        "best_all_available_memory": best.get("all_available_memory"),
        "best_first_n_return_index_memory": best.get("first_n_return_index_memory"),
        "best_neutral_predicted_window_memory": best.get("neutral_predicted_window_memory"),
        "best_neutral_window_pair_coverage": best.get("neutral_window_pair_coverage"),
        "best_late_return_memory_decay": best.get("late_return_memory_decay"),
        "best_all_delta_vs_neutral": best.get("all_available_memory_delta_vs_neutral"),
        "best_neutral_window_delta_vs_neutral": best.get("neutral_predicted_window_memory_delta_vs_neutral"),
        "strict_vs_all_memory_correlation": neutral.get("strict_vs_all_memory_correlation"),
        "strict_vs_neutral_window_memory_correlation": neutral.get("strict_vs_neutral_window_memory_correlation"),
        "comb_vs_all_memory_correlation": neutral.get("comb_vs_all_memory_correlation"),
        "comb_vs_neutral_window_memory_correlation": neutral.get("comb_vs_neutral_window_memory_correlation"),
    }
    if real and not survivor:
        return {
            "label": "cubic_memory_real_same_window_gain",
            "reason": "Cubic rows beat neutral and matched randomized controls on neutral-matched return-window memory, not just surviving-peak memory.",
            "best_variant": best.get("variant"),
            "best_role": best.get("mechanism_role"),
            "checks": checks,
        }
    if survivor and not real:
        return {
            "label": "cubic_memory_survivor_bias_supported",
            "reason": "The cubic memory advantage mostly disappears or decays when scored on neutral-matched return windows instead of only surviving peaks.",
            "best_variant": best.get("variant"),
            "best_role": best.get("mechanism_role"),
            "checks": checks,
        }
    return {
        "label": "cubic_memory_tradeoff_inconclusive",
        "reason": "Matched-window evidence is mixed across cubic rows or does not clearly separate same-window gain from survivor bias.",
        "best_variant": best.get("variant"),
        "best_role": best.get("mechanism_role"),
        "checks": checks,
    }


def _surviving_peak_pairs(variant: str, frames: list[ReturnFrame], *, method: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sorted_frames = _sort_frames(frames)
    for index, (left, right) in enumerate(zip(sorted_frames, sorted_frames[1:]), start=1):
        score = _frame_similarity(left, right)
        rows.append(
            _pair_row(
                variant=variant,
                method=method,
                pair_available=True,
                return_pair_index=index,
                left=left,
                right=right,
                memory_score=score["score"],
                signed_similarity=score["signed_similarity"],
                matched_node_count=score["matched_node_count"],
            )
        )
    return rows


def _neutral_window_pairs(
    variant: str,
    assigned: dict[int, ReturnFrame],
    windows: list[NeutralWindow],
    method: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_index = {window.index: window for window in windows}
    for index in range(1, len(windows)):
        left = assigned.get(index)
        right = assigned.get(index + 1)
        if left is None or right is None:
            rows.append(
                _pair_row(
                    variant=variant,
                    method=method,
                    pair_available=False,
                    return_pair_index=index,
                    neutral_from=by_index[index],
                    neutral_to=by_index[index + 1],
                )
            )
            continue
        score = _frame_similarity(left, right)
        rows.append(
            _pair_row(
                variant=variant,
                method=method,
                pair_available=True,
                return_pair_index=index,
                left=left,
                right=right,
                memory_score=score["score"],
                signed_similarity=score["signed_similarity"],
                matched_node_count=score["matched_node_count"],
                neutral_from=by_index[index],
                neutral_to=by_index[index + 1],
            )
        )
    return rows


def _shared_window_pairs(
    variant: str,
    assigned: dict[int, ReturnFrame],
    shared_indices: list[int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair_index, (left_index, right_index) in enumerate(zip(shared_indices, shared_indices[1:]), start=1):
        left = assigned.get(left_index)
        right = assigned.get(right_index)
        if left is None or right is None:
            continue
        score = _frame_similarity(left, right)
        rows.append(
            _pair_row(
                variant=variant,
                method="shared_neutral_windows",
                pair_available=True,
                return_pair_index=pair_index,
                left=left,
                right=right,
                memory_score=score["score"],
                signed_similarity=score["signed_similarity"],
                matched_node_count=score["matched_node_count"],
                neutral_from_index=left_index,
                neutral_to_index=right_index,
            )
        )
    return rows


def _pair_row(
    *,
    variant: str,
    method: str,
    pair_available: bool,
    return_pair_index: int,
    left: ReturnFrame | None = None,
    right: ReturnFrame | None = None,
    memory_score: float | str = "",
    signed_similarity: float | str = "",
    matched_node_count: int | str = "",
    neutral_from: NeutralWindow | None = None,
    neutral_to: NeutralWindow | None = None,
    neutral_from_index: int | None = None,
    neutral_to_index: int | None = None,
) -> dict[str, Any]:
    return {
        "variant": variant,
        "method": method,
        "pair_available": pair_available,
        "return_pair_index": return_pair_index,
        "neutral_window_from_index": neutral_from.index if neutral_from else neutral_from_index or "",
        "neutral_window_to_index": neutral_to.index if neutral_to else neutral_to_index or "",
        "neutral_window_from_time": neutral_from.center_time if neutral_from else "",
        "neutral_window_to_time": neutral_to.center_time if neutral_to else "",
        "from_frame_id": left.frame_id if left else "",
        "to_frame_id": right.frame_id if right else "",
        "from_peak_rank": left.peak_rank if left else "",
        "to_peak_rank": right.peak_rank if right else "",
        "from_time": left.time if left else "",
        "to_time": right.time if right else "",
        "signed_similarity": signed_similarity,
        "memory_score": memory_score,
        "matched_node_count": matched_node_count,
    }


def _frame_similarity(left: ReturnFrame, right: ReturnFrame) -> dict[str, Any]:
    common = sorted(set(left.values) & set(right.values))
    if not common:
        return {"signed_similarity": 0.0, "score": 0.0, "matched_node_count": 0}
    a = np.asarray([left.values[index] for index in common], dtype=float)
    b = np.asarray([right.values[index] for index in common], dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= EPSILON:
        signed = 0.0
    else:
        signed = float(np.clip(float(np.dot(a, b) / denom), -1.0, 1.0))
    return {"signed_similarity": signed, "score": abs(signed), "matched_node_count": len(common)}


def _attach_deltas(rows: list[dict[str, Any]]) -> None:
    neutral = next((row for row in rows if row.get("mechanism_role") == "neutral_reference"), {})
    by_variant = {str(row.get("variant")): row for row in rows}
    for row in rows:
        matched = by_variant.get(str(row.get("matched_random_variant") or ""), {})
        for metric in (
            "all_available_memory",
            "first_n_return_index_memory",
            "neutral_predicted_window_memory",
            "shared_window_memory",
            "late_return_memory_decay",
        ):
            row[f"{metric}_delta_vs_neutral"] = _float(row.get(metric)) - _float(neutral.get(metric))
            row[f"{metric}_delta_vs_matched_random"] = (
                _float(row.get(metric)) - _float(matched.get(metric)) if matched else ""
            )
        all_gain = _float(row.get("all_available_memory_delta_vs_neutral"))
        neutral_gain = _float(row.get("neutral_predicted_window_memory_delta_vs_neutral"))
        row["same_window_gain_fraction_vs_all_gain"] = neutral_gain / max(all_gain, EPSILON) if all_gain > EPSILON else 0.0
        first_gain = _float(row.get("first_n_return_index_memory_delta_vs_neutral"))
        row["return_index_gain_fraction_vs_all_gain"] = first_gain / max(all_gain, EPSILON) if all_gain > EPSILON else 0.0


def _attach_relationship_fields(rows: list[dict[str, Any]]) -> None:
    strict_proxy = [
        _float(row.get("strict_major_peaks")) + 0.08 * _float(row.get("strict_refocus_peaks"))
        for row in rows
    ]
    comb = [_float(row.get("return_timing_comb_score")) for row in rows]
    all_memory = [_float(row.get("all_available_memory")) for row in rows]
    neutral_window_memory = [_float(row.get("neutral_predicted_window_memory")) for row in rows]
    fields = {
        "strict_vs_all_memory_correlation": _correlation(strict_proxy, all_memory),
        "strict_vs_neutral_window_memory_correlation": _correlation(strict_proxy, neutral_window_memory),
        "comb_vs_all_memory_correlation": _correlation(comb, all_memory),
        "comb_vs_neutral_window_memory_correlation": _correlation(comb, neutral_window_memory),
    }
    for row in rows:
        row.update(fields)


def _write_plots(
    plots: dict[str, Path],
    summary_rows: list[dict[str, Any]],
    index_rows: list[dict[str, Any]],
) -> None:
    selected = _plot_variants(summary_rows)
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=140)
    for variant in selected:
        rows = [
            row
            for row in index_rows
            if row.get("variant") == variant and row.get("neutral_window_memory") not in ("", None)
        ]
        xs = [_float(row.get("return_pair_index")) for row in rows]
        ys = [_float(row.get("neutral_window_memory")) for row in rows]
        ax.plot(xs, ys, marker="o", linewidth=1.2, label=_short_label(variant))
    ax.set_xlabel("Neutral return-pair index")
    ax.set_ylabel("Neutral-window memory")
    ax.set_ylim(0.0, 1.05)
    ax.set_title("Memory by Neutral Return Index")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(plots["memory_by_return_index"])
    plt.close(fig)

    labels = [_short_label(str(row.get("variant"))) for row in summary_rows if str(row.get("variant")) in selected]
    rows = [row for row in summary_rows if str(row.get("variant")) in selected]
    x = np.arange(len(rows))
    width = 0.26
    fig, ax = plt.subplots(figsize=(max(9, len(rows) * 0.9), 4.5), dpi=140)
    ax.bar(x - width, [_float(row.get("all_available_memory")) for row in rows], width, label="surviving")
    ax.bar(x, [_float(row.get("first_n_return_index_memory")) for row in rows], width, label="first N")
    ax.bar(x + width, [_float(row.get("neutral_predicted_window_memory")) for row in rows], width, label="neutral windows")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.set_ylim(0.0, 1.05)
    ax.set_title("Surviving vs Matched-Window Memory")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(plots["matched_window_memory"])
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=140)
    for row in summary_rows:
        x_value = _float(row.get("strict_major_peaks")) + 0.08 * _float(row.get("strict_refocus_peaks"))
        ax.scatter([x_value], [_float(row.get("all_available_memory"))], color="#5577aa", s=36)
        ax.scatter([x_value], [_float(row.get("neutral_predicted_window_memory"))], color="#aa7755", marker="x", s=42)
        ax.annotate(_short_label(str(row.get("variant"))), (x_value, _float(row.get("neutral_predicted_window_memory"))), fontsize=6, xytext=(3, 3), textcoords="offset points")
    ax.axvline(9.0 + 0.08 * 8.0, color="black", linestyle="--", linewidth=1, alpha=0.55)
    ax.set_xlabel("Strict count proxy: major + 0.08*refocus")
    ax.set_ylabel("Memory")
    ax.set_ylim(0.0, 1.05)
    ax.set_title("Memory vs Strict Count")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(plots["memory_vs_strict_count"])
    plt.close(fig)


def _write_report(
    path: Path,
    control_id: str,
    classification: dict[str, Any],
    rows: list[dict[str, Any]],
    plots: dict[str, Path],
) -> None:
    checks = classification.get("checks", {})
    lines = [
        f"# Cubic Memory Survivor-Bias Audit: {control_id}",
        "",
        "## Purpose",
        "",
        "Read-only audit of whether the cubic-memory tradeoff map's memory gain is true same-return-window improvement or inflated by comparing fewer cleaner surviving returns. No new physics was run.",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Reason: {classification['reason']}",
        f"- Best variant: `{classification.get('best_variant', 'n/a')}`",
        "",
        "## Key Checks",
        "",
        f"- Neutral surviving memory: `{_format(checks.get('neutral_all_available_memory'))}`",
        f"- Neutral first-N return-index memory: `{_format(checks.get('neutral_first_n_return_index_memory'))}`",
        f"- Neutral predicted-window memory: `{_format(checks.get('neutral_predicted_window_memory'))}`",
        f"- Best surviving memory: `{_format(checks.get('best_all_available_memory'))}`",
        f"- Best first-N return-index memory: `{_format(checks.get('best_first_n_return_index_memory'))}`",
        f"- Best neutral-window memory: `{_format(checks.get('best_neutral_predicted_window_memory'))}`",
        f"- Best neutral-window pair coverage: `{_format(checks.get('best_neutral_window_pair_coverage'))}`",
        f"- Strict-vs-surviving-memory correlation: `{_format(checks.get('strict_vs_all_memory_correlation'))}`",
        f"- Strict-vs-neutral-window-memory correlation: `{_format(checks.get('strict_vs_neutral_window_memory_correlation'))}`",
        "",
        "## Summary Rows",
        "",
        "| Variant | Role | Surviving | First N | Neutral windows | Coverage | Strict | Default | Loose | Comb | Clean |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('variant')} | {row.get('mechanism_role')} | "
            f"{_format(row.get('all_available_memory'))} | "
            f"{_format(row.get('first_n_return_index_memory'))} | "
            f"{_format(row.get('neutral_predicted_window_memory'))} | "
            f"{_format(row.get('neutral_window_pair_coverage'))} | "
            f"{_int(row.get('strict_major_peaks'))}/{_int(row.get('strict_refocus_peaks'))} | "
            f"{_int(row.get('default_major_peaks'))}/{_int(row.get('default_refocus_peaks'))} | "
            f"{_int(row.get('loose_major_peaks'))}/{_int(row.get('loose_refocus_peaks'))} | "
            f"{_format(row.get('return_timing_comb_score'))} | "
            f"{row.get('clean_gates_passed')} |"
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
            "- `cubic_memory_survivor_bias_summary.csv`",
            "- `matched_return_memory.csv`",
            "- `memory_by_return_index.csv`",
            "- `cubic_memory_survivor_bias_summary.json`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _interpretation(classification: dict[str, Any]) -> str:
    label = classification["label"]
    if label == "cubic_memory_real_same_window_gain":
        return "The cubic memory advantage survives neutral-window matching, so the saved artifacts support a real same-window pattern-memory gain rather than only survivor selection."
    if label == "cubic_memory_survivor_bias_supported":
        return "The cubic memory advantage is inflated by survivor selection: the high surviving-peak score does not remain a clean same-neutral-window advantage, especially in late or missing return windows."
    if label == "insufficient_artifacts":
        return "Required saved return frames or tradeoff summaries were missing."
    return "The evidence is mixed: some memory advantage remains under matching, but not enough to cleanly distinguish same-window mechanism from survivor bias."


def _write_empty_outputs(
    root: Path,
    control_id: str,
    classification: dict[str, Any],
    missing: list[str],
) -> dict[str, Any]:
    summary_csv = root / "cubic_memory_survivor_bias_summary.csv"
    matched_csv = root / "matched_return_memory.csv"
    index_csv = root / "memory_by_return_index.csv"
    report_path = root / "cubic_memory_survivor_bias_report.md"
    _write_csv(summary_csv, [], _summary_fields())
    _write_csv(matched_csv, [], _matched_fields())
    _write_csv(index_csv, [], _index_fields())
    report_path.write_text(
        f"# Cubic Memory Survivor-Bias Audit: {control_id}\n\n"
        f"- Result: `{classification['label']}`\n"
        f"- Reason: {classification['reason']}\n"
        f"- Missing artifacts: `{', '.join(missing)}`\n",
        encoding="utf-8",
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": [],
        "matched_rows": [],
        "memory_by_return_index_rows": [],
        "summary_csv": str(summary_csv),
        "matched_return_memory_csv": str(matched_csv),
        "memory_by_return_index_csv": str(index_csv),
        "report_path": str(report_path),
        "plots": {},
        "path": str(root),
    }


def _matched_random_variant(role: str, summary_rows: list[dict[str, Any]]) -> str:
    if not role:
        return ""
    for row in summary_rows:
        if row.get("mechanism_role") == role:
            return str(row.get("variant"))
    return ""


def _neutral_variant(variants: list[str]) -> str:
    for variant in variants:
        if variant.endswith("neutral_reference"):
            return variant
    return "cubic_memory_tradeoff_41_neutral_reference"


def _plot_variants(rows: list[dict[str, Any]]) -> list[str]:
    wanted_roles = {
        "neutral_reference",
        "random_equivalent_0p5x",
        "random_equivalent_1p0x",
        "cubic_split_1p0x",
        "cubic_split_sign_flipped_0p5x",
    }
    selected = [str(row.get("variant")) for row in rows if row.get("mechanism_role") in wanted_roles]
    for row in sorted(rows, key=lambda item: str(item.get("variant"))):
        variant = str(row.get("variant"))
        if variant not in selected and len(selected) < 8:
            selected.append(variant)
    return selected


def _short_label(variant: str) -> str:
    replacements = {
        "cubic_memory_tradeoff_41_neutral_reference": "neutral",
        "cubic_memory_tradeoff_41_random_equivalent_0p5x": "random 0.5x",
        "cubic_memory_tradeoff_41_random_equivalent_1p0x": "random 1.0x",
        "cubic_memory_tradeoff_41_cubic_split_1p0x": "cubic 1.0x",
        "cubic_memory_tradeoff_41_cubic_split_sign_flipped_0p5x": "flip 0.5x",
    }
    return replacements.get(variant, variant.replace("cubic_memory_tradeoff_41_", "")[:24])


def _sort_frames(frames: list[ReturnFrame]) -> list[ReturnFrame]:
    return sorted(frames, key=lambda frame: (frame.time, frame.peak_rank, frame.frame_id))


def _correlation(left: list[float], right: list[float]) -> float:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    valid = np.isfinite(a) & np.isfinite(b)
    a = a[valid]
    b = b[valid]
    if a.size < 2 or float(np.std(a)) <= EPSILON or float(np.std(b)) <= EPSILON:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _mean(values: list[Any]) -> float:
    parsed = [_float(value) for value in values if value not in (None, "")]
    return float(np.mean(parsed)) if parsed else 0.0


def _std(values: list[Any]) -> float:
    parsed = [_float(value) for value in values if value not in (None, "")]
    return float(np.std(parsed)) if parsed else 0.0


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


def _int(value: Any) -> int:
    return int(round(_float(value)))


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def _summary_fields() -> list[str]:
    return [
        "variant",
        "cubic_memory_survivor_bias_classification",
        "mechanism_role",
        "mechanism_profile",
        "mechanism_strength_factor",
        "split_orientation",
        "matched_random_role",
        "matched_random_variant",
        "return_frame_count",
        "neutral_return_window_count",
        "assigned_neutral_window_count",
        "neutral_window_return_coverage",
        "all_available_pair_count",
        "all_available_memory",
        "all_available_memory_std",
        "first_n_frame_count",
        "first_n_pair_count",
        "first_n_return_index_memory",
        "neutral_window_pair_count",
        "neutral_window_possible_pair_count",
        "neutral_window_pair_coverage",
        "neutral_predicted_window_memory",
        "shared_window_count",
        "shared_window_pair_count",
        "shared_window_memory",
        "late_return_memory_decay",
        "all_available_memory_delta_vs_neutral",
        "all_available_memory_delta_vs_matched_random",
        "first_n_return_index_memory_delta_vs_neutral",
        "first_n_return_index_memory_delta_vs_matched_random",
        "neutral_predicted_window_memory_delta_vs_neutral",
        "neutral_predicted_window_memory_delta_vs_matched_random",
        "shared_window_memory_delta_vs_neutral",
        "shared_window_memory_delta_vs_matched_random",
        "late_return_memory_decay_delta_vs_neutral",
        "late_return_memory_decay_delta_vs_matched_random",
        "same_window_gain_fraction_vs_all_gain",
        "return_index_gain_fraction_vs_all_gain",
        "strict_major_peaks",
        "strict_refocus_peaks",
        "default_major_peaks",
        "default_refocus_peaks",
        "loose_major_peaks",
        "loose_refocus_peaks",
        "return_timing_comb_score",
        "off_comb_energy_ratio",
        "clean_gates_passed",
        "strict_vs_all_memory_correlation",
        "strict_vs_neutral_window_memory_correlation",
        "comb_vs_all_memory_correlation",
        "comb_vs_neutral_window_memory_correlation",
    ]


def _matched_fields() -> list[str]:
    return [
        "variant",
        "cubic_memory_survivor_bias_classification",
        "method",
        "pair_available",
        "return_pair_index",
        "neutral_window_from_index",
        "neutral_window_to_index",
        "neutral_window_from_time",
        "neutral_window_to_time",
        "from_frame_id",
        "to_frame_id",
        "from_peak_rank",
        "to_peak_rank",
        "from_time",
        "to_time",
        "signed_similarity",
        "memory_score",
        "matched_node_count",
    ]


def _index_fields() -> list[str]:
    return [
        "variant",
        "cubic_memory_survivor_bias_classification",
        "mechanism_role",
        "return_pair_index",
        "all_available_memory",
        "first_n_return_index_memory",
        "neutral_window_memory",
        "neutral_window_pair_available",
        "neutral_window_from_index",
        "neutral_window_to_index",
        "neutral_window_from_time",
        "neutral_window_to_time",
        "from_time",
        "to_time",
    ]
