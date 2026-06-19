"""Tests for the tiny 3D cutoff phase/timing map."""

from __future__ import annotations

import math
import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_cutoff_phase_map import (
    CutoffPhaseMap3DOptions,
    _cutoff_phase_cycles,
    _ranked_rows,
    _variant_plan,
    classify_cutoff_phase_map,
    event_threshold_sensitivity_audit,
    phase_lock_needle_width,
    release_phase_island_stability,
    summarize_event_threshold_sensitivity,
)


class Prototype3DCutoffPhaseMapTests(unittest.TestCase):
    def test_variant_plan_keeps_tiny_timing_scope(self) -> None:
        base = SimulationConfig()
        base.driver.frequency = 0.92
        base.driver.drive_cutoff_time = 16.0
        options = CutoffPhaseMap3DOptions()

        variants = _variant_plan(base, options)
        names = [variant.name for variant in variants]
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual(
            names,
            [
                "phase_offset_cutoff_minus_1p0",
                "phase_offset_cutoff_minus_0p5",
                "phase_offset_cutoff_reference",
                "phase_offset_cutoff_plus_0p5",
                "phase_offset_cutoff_plus_1p0",
                "phase_offset_delta_minus_0p0625",
                "phase_offset_delta_plus_0p0625",
                "sign_flip_cutoff_minus_0p5",
                "sign_flip_cutoff_reference",
                "sign_flip_cutoff_plus_0p5",
            ],
        )
        self.assertEqual(len(variants), 10)
        self.assertAlmostEqual(by_name["phase_offset_cutoff_reference"].drive_cutoff_time, 18.0)
        self.assertAlmostEqual(by_name["phase_offset_cutoff_reference"].drive_frequency, 0.92)
        self.assertAlmostEqual(by_name["phase_offset_cutoff_reference"].boundary_phase_offset, 0.5 * math.pi)
        self.assertAlmostEqual(by_name["sign_flip_cutoff_reference"].boundary_phase_offset, 0.0)
        for variant in variants:
            self.assertEqual(variant.grid_size, 41)
            self.assertEqual(variant.drive_phase_mode, "cubic")
            self.assertAlmostEqual(variant.boundary_cubic_phase_sign, -1.0)
            self.assertAlmostEqual(variant.defect_stiffness_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_damping_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_coupling_multiplier, 1.0)

    def test_cutoff_phase_includes_global_phase_offset(self) -> None:
        base = SimulationConfig()
        base.driver.frequency = 0.92
        options = CutoffPhaseMap3DOptions()
        variant = _variant_plan(base, options)[2]

        phase = _cutoff_phase_cycles(variant)

        self.assertAlmostEqual(phase, (0.92 * 18.0 + 0.25) % 1.0)

    def test_variant_plan_can_run_sign_flip_only_needle_offsets(self) -> None:
        base = SimulationConfig()
        base.driver.frequency = 0.92
        base.driver.drive_cutoff_time = 16.0
        options = CutoffPhaseMap3DOptions(
            include_phase_offset_family=False,
            polarity_cutoff_offsets=(-0.075, -0.070, -0.065, -0.060, -0.055, -0.050, -0.045),
        )

        variants = _variant_plan(base, options)

        self.assertEqual([variant.name for variant in variants], [
            "sign_flip_cutoff_minus_0p075",
            "sign_flip_cutoff_minus_0p07",
            "sign_flip_cutoff_minus_0p065",
            "sign_flip_cutoff_minus_0p06",
            "sign_flip_cutoff_minus_0p055",
            "sign_flip_cutoff_minus_0p05",
            "sign_flip_cutoff_minus_0p045",
        ])
        self.assertTrue(all(variant.boundary_phase_offset == 0.0 for variant in variants))

    def test_classification_detects_strong_timing_island(self) -> None:
        rows = [
            _row("phase_offset_cutoff_reference", peaks=9, refocus=8, retention=0.269, outer=0.809, phase=0.81, cutoff_offset=0.0),
            _row("phase_offset_cutoff_plus_0p5", peaks=10, refocus=9, retention=0.32, outer=0.70, phase=0.86, cutoff_offset=0.5),
            _row("phase_offset_cutoff_plus_1p0", peaks=10, refocus=9, retention=0.31, outer=0.75, phase=0.90, cutoff_offset=1.0),
        ]

        result = classify_cutoff_phase_map(rows, CutoffPhaseMap3DOptions())

        self.assertEqual(result["label"], "cutoff_phase_timing_island_supported")
        self.assertEqual(result["best_variant"], "phase_offset_cutoff_plus_0p5")
        self.assertEqual(
            result["release_phase_island_stability"]["label"],
            "neighboring_cluster_supported",
        )

    def test_classification_uses_sign_flip_reference_for_tight_refinement(self) -> None:
        rows = [
            _row(
                "sign_flip_cutoff_minus_0p14",
                family="sign_flip",
                axis="polarity_cutoff",
                cutoff_offset=-0.14,
                peaks=9,
                refocus=8,
                retention=0.312,
                outer=0.70,
                phase=0.43,
            ),
            _row(
                "sign_flip_cutoff_minus_0p12",
                family="sign_flip",
                axis="polarity_cutoff",
                cutoff_offset=-0.12,
                peaks=9,
                refocus=8,
                retention=0.318,
                outer=0.68,
                phase=0.45,
            ),
            _row(
                "sign_flip_cutoff_minus_0p1",
                family="sign_flip",
                axis="polarity_cutoff",
                cutoff_offset=-0.10,
                peaks=9,
                refocus=8,
                retention=0.322,
                outer=0.66,
                phase=0.468,
            ),
        ]

        result = classify_cutoff_phase_map(
            rows,
            CutoffPhaseMap3DOptions(reference_variant="sign_flip_cutoff_minus_0p1"),
        )

        self.assertEqual(result["label"], "cutoff_phase_timing_island_supported")
        self.assertEqual(result["best_variant"], "sign_flip_cutoff_minus_0p1")
        self.assertTrue(result["release_phase_island_stability"]["is_stable"])

    def test_classification_reports_tolerant_without_improvement(self) -> None:
        rows = [
            _row("phase_offset_cutoff_reference", peaks=9, refocus=8, retention=0.269, outer=0.809, phase=0.81),
            _row("phase_offset_cutoff_plus_0p5", peaks=8, refocus=7, retention=0.25, outer=0.82, phase=0.86),
        ]

        result = classify_cutoff_phase_map(rows, CutoffPhaseMap3DOptions())

        self.assertEqual(result["label"], "cutoff_phase_tolerant_no_improvement")

    def test_ranked_rows_use_cutoff_phase_decision_priority(self) -> None:
        rows = [
            _row("lower_refocus", peaks=9, refocus=7, retention=0.40, outer=0.50, phase=0.2),
            _row("exits", peaks=10, refocus=8, retention=0.50, outer=0.60, phase=0.3, exit_detected=True),
            _row("best", peaks=10, refocus=8, retention=0.45, outer=0.70, phase=0.4),
            _row("outer_above_one", peaks=10, refocus=8, retention=0.42, outer=1.20, phase=0.5),
        ]

        ranked = _ranked_rows(rows)

        self.assertEqual([row["variant"] for row in ranked], ["best", "outer_above_one", "exits", "lower_refocus"])
        self.assertEqual([row["rank"] for row in ranked], [1, 2, 3, 4])
        self.assertTrue(ranked[0]["outer_shell_below_1"])
        self.assertFalse(ranked[1]["outer_shell_below_1"])

    def test_ranked_rows_prioritize_major_shell_peaks_before_refocus(self) -> None:
        rows = [
            _row("higher_refocus", peaks=8, refocus=8, retention=0.50, outer=0.50, phase=0.2),
            _row("higher_major", peaks=9, refocus=7, retention=0.45, outer=0.50, phase=0.3),
        ]

        ranked = _ranked_rows(rows)

        self.assertEqual([row["variant"] for row in ranked], ["higher_major", "higher_refocus"])

    def test_release_phase_stability_rejects_single_isolated_point(self) -> None:
        rows = [
            _row("phase_offset_cutoff_reference", peaks=9, refocus=8, retention=0.269, outer=0.809, phase=0.81, cutoff_offset=0.0),
            _row("phase_offset_cutoff_plus_0p5", peaks=10, refocus=9, retention=0.32, outer=0.70, phase=0.86, cutoff_offset=0.5),
            _row("phase_offset_cutoff_plus_1p0", peaks=9, refocus=8, retention=0.31, outer=0.75, phase=0.90, cutoff_offset=1.0),
        ]

        stability = release_phase_island_stability(rows, CutoffPhaseMap3DOptions())

        self.assertEqual(stability["label"], "single_point_best")
        self.assertFalse(stability["is_stable"])

    def test_phase_lock_needle_width_reports_narrow_when_neighbors_are_close(self) -> None:
        rows = [
            _row("sign_flip_cutoff_minus_0p065", family="sign_flip", axis="polarity_cutoff", cutoff_offset=-0.065, peaks=10, refocus=9, retention=0.30, outer=0.70, phase=0.50, cutoff=17.935),
            _row("sign_flip_cutoff_minus_0p06", family="sign_flip", axis="polarity_cutoff", cutoff_offset=-0.060, peaks=11, refocus=10, retention=0.314, outer=0.63, phase=0.505, cutoff=17.94),
            _row("sign_flip_cutoff_minus_0p055", family="sign_flip", axis="polarity_cutoff", cutoff_offset=-0.055, peaks=10, refocus=9, retention=0.31, outer=0.62, phase=0.51, cutoff=17.945),
        ]

        width = phase_lock_needle_width(rows, CutoffPhaseMap3DOptions())

        self.assertEqual(width["label"], "narrow")
        self.assertEqual(width["best_cutoff"], 17.94)
        self.assertEqual(len(width["neighboring_within_one_peak_refocus"]), 2)

    def test_event_threshold_sensitivity_recounts_best_and_neighbors(self) -> None:
        rows = [
            _row("sign_flip_cutoff_minus_0p065", family="sign_flip", axis="polarity_cutoff", cutoff_offset=-0.065, peaks=2, refocus=1, retention=0.30, outer=0.70, phase=0.50, cutoff=17.935),
            _row("sign_flip_cutoff_minus_0p06", family="sign_flip", axis="polarity_cutoff", cutoff_offset=-0.060, peaks=2, refocus=1, retention=0.314, outer=0.63, phase=0.505, cutoff=17.94),
            _row("sign_flip_cutoff_minus_0p055", family="sign_flip", axis="polarity_cutoff", cutoff_offset=-0.055, peaks=2, refocus=1, retention=0.31, outer=0.62, phase=0.51, cutoff=17.945),
        ]
        timeseries = []
        for row in rows:
            timeseries.extend(_timeseries(row["variant"], row["drive_cutoff_time"]))

        audit = event_threshold_sensitivity_audit(rows, timeseries, CutoffPhaseMap3DOptions())
        summary = summarize_event_threshold_sensitivity(audit)

        self.assertEqual(len(audit), 27)
        self.assertEqual(summary["label"], "best_count_threshold_robust")
        self.assertEqual([row["relation_to_best"] for row in summary["variants"]], ["lower_neighbor", "best", "upper_neighbor"])


def _row(
    variant: str,
    *,
    peaks: int,
    refocus: int,
    retention: float,
    outer: float,
    phase: float,
    family: str = "phase_offset",
    axis: str = "cutoff",
    cutoff_offset: float = 0.0,
    exit_detected: bool = False,
    global_outer: bool = False,
    cutoff: float = 18.0,
) -> dict:
    return {
        "variant": variant,
        "family": family,
        "drive_cutoff_time": cutoff,
        "major_shell_peak_count": peaks,
        "refocus_peak_count": refocus,
        "refocus_peak_ratio_max": 2.0,
        "tail_shell_retention": retention,
        "tail_outer_to_shell_mean": outer,
        "shell_exit_detected": exit_detected,
        "shell_exit_time": None if not exit_detected else 74.0,
        "post_cutoff_shell_decay_rate": -0.03,
        "global_peak_in_outer_window": global_outer,
        "cutoff_phase_cycles": phase,
        "axis_label": axis,
        "cutoff_offset_from_center": cutoff_offset,
    }


def _timeseries(variant: str, cutoff: float) -> list[dict]:
    rows = []
    for time, energy in [
        (cutoff + 1.0, 1.0),
        (cutoff + 2.0, 3.0),
        (cutoff + 3.0, 1.0),
        (cutoff + 8.0, 0.8),
        (cutoff + 9.0, 2.0),
        (cutoff + 10.0, 0.7),
    ]:
        rows.append({"variant": variant, "time": time, "shell_window_energy": energy})
    return rows


if __name__ == "__main__":
    unittest.main()
