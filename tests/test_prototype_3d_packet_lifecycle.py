"""Tests for 3D packet lifecycle diagnostics."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_packet_lifecycle import (
    PacketLifecycle3DOptions,
    _variant_plan,
    classify_packet_lifecycle,
)


class Prototype3DPacketLifecycleTests(unittest.TestCase):
    def test_variant_plan_reuses_clean_cubic_packet_variants(self) -> None:
        options = PacketLifecycle3DOptions()
        variants = _variant_plan(SimulationConfig(), options)
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual([variant.name for variant in variants], ["neutral_cubic_sign_flip_reference", "neutral_cubic_phase_offset"])
        for variant in variants:
            self.assertEqual(variant.grid_size, 41)
            self.assertEqual(variant.drive_phase_mode, "cubic")
            self.assertAlmostEqual(variant.boundary_cubic_phase_sign, -1.0)
            self.assertEqual(variant.boundary_source_inner_distance, variant.sponge_width)
            self.assertAlmostEqual(variant.defect_stiffness_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_damping_multiplier, 1.0)
            self.assertAlmostEqual(variant.defect_coupling_multiplier, 1.0)
        self.assertAlmostEqual(by_name["neutral_cubic_phase_offset"].boundary_phase_offset, options.phase_offset)

    def test_classification_detects_repeated_refocusing(self) -> None:
        rows = [_row("neutral_cubic_sign_flip_reference", peaks=3, refocus=2), _row("neutral_cubic_phase_offset", peaks=2, refocus=1)]

        result = classify_packet_lifecycle(rows, PacketLifecycle3DOptions())

        self.assertEqual(result["label"], "repeated_refocusing_supported")

    def test_classification_detects_single_pass_transport(self) -> None:
        rows = [
            _row("neutral_cubic_sign_flip_reference", peaks=1, refocus=0, exit=True),
            _row("neutral_cubic_phase_offset", peaks=1, refocus=0, exit=True),
        ]

        result = classify_packet_lifecycle(rows, PacketLifecycle3DOptions())

        self.assertEqual(result["label"], "single_pass_transport")

    def test_classification_detects_diffusive_tail(self) -> None:
        rows = [
            _row("neutral_cubic_sign_flip_reference", peaks=2, refocus=0, width_growth=0.55, decay=-0.03),
            _row("neutral_cubic_phase_offset", peaks=2, refocus=0, width_growth=0.40, decay=-0.02),
        ]

        result = classify_packet_lifecycle(rows, PacketLifecycle3DOptions())

        self.assertEqual(result["label"], "diffusive_transport_tail")


def _row(
    variant: str,
    *,
    peaks: int,
    refocus: int,
    exit: bool = False,
    width_growth: float = 0.05,
    decay: float = -0.002,
) -> dict:
    return {
        "variant": variant,
        "major_shell_peak_count": peaks,
        "refocus_peak_count": refocus,
        "shell_exit_detected": exit,
        "packet_width_growth_fraction": width_growth,
        "post_cutoff_shell_decay_rate": decay,
        "tail_shell_retention": 0.5,
        "tail_outer_to_shell_mean": 1.2,
        "inward_flux_fraction": 0.75,
        "outward_flux_fraction": 0.25,
    }


if __name__ == "__main__":
    unittest.main()
