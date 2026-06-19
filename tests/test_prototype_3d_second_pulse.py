"""Tests for the tiny 3D second-pulse control."""

from __future__ import annotations

import math
import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_second_pulse import (
    SecondPulse3DOptions,
    _phase_cycles,
    _phase_offset_to_release,
    _ranked_rows,
    _reference_event_times,
    _variant_plan,
    classify_second_pulse_control,
)


class Prototype3DSecondPulseTests(unittest.TestCase):
    def test_variant_plan_uses_refocus_events_and_reference_release_phase(self) -> None:
        base = SimulationConfig()
        base.driver.frequency = 0.92
        options = SecondPulse3DOptions(reference_events_csv=None, second_pulse_amplitude_scale=0.5)
        event_times = _reference_event_times(options)

        variants = _variant_plan(base, options, source_width=1.0, event_times=event_times)
        names = [variant.name for variant in variants]
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual(
            names,
            [
                "no_second_pulse",
                "second_at_first_refocus",
                "second_before_first_refocus",
                "second_at_second_refocus",
                "opposite_polarity_second",
                "phase_matched_second",
                "phase_offset_second",
                "extended_first_pulse_same_duration",
            ],
        )
        self.assertAlmostEqual(by_name["no_second_pulse"].drive_cutoff_time, 17.9)
        self.assertIsNone(by_name["no_second_pulse"].second_pulse_center_time)
        self.assertAlmostEqual(by_name["second_at_first_refocus"].second_pulse_center_time, 35.84)
        self.assertAlmostEqual(by_name["second_at_first_refocus"].second_pulse_amplitude_scale, 0.5)
        self.assertAlmostEqual(by_name["second_before_first_refocus"].second_pulse_center_time, 34.84)
        self.assertAlmostEqual(by_name["second_at_second_refocus"].second_pulse_center_time, 41.12)
        self.assertAlmostEqual(by_name["extended_first_pulse_same_duration"].drive_cutoff_time, 19.9)
        matched = by_name["phase_matched_second"]
        phase = _phase_cycles(matched.drive_frequency, matched.second_pulse_center_time, matched.second_pulse_phase_offset)
        self.assertAlmostEqual(phase, options.reference_release_phase_cycles)

    def test_phase_offset_to_release_wraps_to_shortest_offset(self) -> None:
        offset = _phase_offset_to_release(0.92, 35.84, 0.468)

        self.assertAlmostEqual(offset / (2.0 * math.pi), 0.4952, places=4)

    def test_classification_detects_active_second_pulse_promising(self) -> None:
        rows = [
            _row("no_second_pulse", "reference", peaks=9, refocus=8, retention=0.322, outer=0.66, decay=-0.0237, tail=0.10, total_work=1.0),
            _row("phase_matched_second", "phase_matched", peaks=10, refocus=9, retention=0.36, outer=0.70, decay=-0.020, tail=0.13, total_work=1.2),
            _row("extended_first_pulse_same_duration", "passive_extension", peaks=10, refocus=9, retention=0.34, outer=0.80, decay=-0.021, tail=0.11, total_work=1.2),
        ]

        result = classify_second_pulse_control(rows, SecondPulse3DOptions())

        self.assertEqual(result["label"], "active_second_pulse_promising")
        self.assertEqual(result["best_variant"], "phase_matched_second")

    def test_ranked_rows_include_efficiency_priority(self) -> None:
        rows = [
            _row("reference", "reference", peaks=9, refocus=8, retention=0.40, outer=0.50, decay=-0.03, tail=0.10, total_work=1.0),
            _row("higher_retention_lower_efficiency", "active", peaks=10, refocus=9, retention=0.50, outer=0.50, decay=-0.03, tail=0.11, total_work=2.0),
            _row("lower_retention_higher_efficiency", "active", peaks=10, refocus=9, retention=0.45, outer=0.50, decay=-0.03, tail=0.11, total_work=1.1),
        ]

        ranked = _ranked_rows(rows)

        self.assertEqual(ranked[0]["variant"], "lower_retention_higher_efficiency")
        self.assertGreater(ranked[0]["added_work_efficiency"], ranked[1]["added_work_efficiency"])

    def test_variant_plan_can_make_reduced_work_map(self) -> None:
        base = SimulationConfig()
        base.driver.frequency = 0.92
        options = SecondPulse3DOptions(
            reference_events_csv=None,
            second_pulse_amplitude_scales=(0.1, 0.2),
            second_pulse_durations=(2.0, 1.0),
            second_pulse_roles=("phase_matched",),
        )

        variants = _variant_plan(base, options, source_width=1.0, event_times=_reference_event_times(options))
        names = [variant.name for variant in variants]

        self.assertEqual(
            names,
            [
                "no_second_pulse",
                "extended_first_pulse_duration_2p0",
                "phase_matched_second_scale_0p1_duration_2p0",
                "phase_matched_second_scale_0p2_duration_2p0",
                "extended_first_pulse_duration_1p0",
                "phase_matched_second_scale_0p1_duration_1p0",
                "phase_matched_second_scale_0p2_duration_1p0",
            ],
        )
        self.assertAlmostEqual(variants[2].second_pulse_amplitude_scale, 0.1)
        self.assertAlmostEqual(variants[5].second_pulse_duration, 1.0)


def _row(
    variant: str,
    role: str,
    *,
    peaks: int,
    refocus: int,
    retention: float,
    outer: float,
    decay: float,
    tail: float,
    total_work: float,
    exit_detected: bool = False,
    global_outer: bool = False,
) -> dict:
    return {
        "variant": variant,
        "second_pulse_role": role,
        "major_shell_peak_count": peaks,
        "refocus_peak_count": refocus,
        "tail_shell_retention": retention,
        "tail_outer_to_shell_mean": outer,
        "post_cutoff_shell_decay_rate": decay,
        "tail_shell_energy_mean": tail,
        "total_positive_work": total_work,
        "refocus_efficiency_total_work": tail / total_work,
        "shell_exit_detected": exit_detected,
        "shell_exit_time": None if not exit_detected else 80.0,
        "global_peak_in_outer_window": global_outer,
    }


if __name__ == "__main__":
    unittest.main()
