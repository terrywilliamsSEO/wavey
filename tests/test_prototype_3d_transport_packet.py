"""Tests for 3D transport-packet diagnostics."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_transport_packet import (
    TransportPacket3DOptions,
    _variant_plan,
    classify_transport_packet,
)


class Prototype3DTransportPacketTests(unittest.TestCase):
    def test_variant_plan_reuses_two_clean_cubic_variants(self) -> None:
        options = TransportPacket3DOptions()
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

    def test_classification_detects_moving_transport_packet(self) -> None:
        rows = [_row("neutral_cubic_sign_flip_reference", radial_v=-0.12, inward=0.72), _row("neutral_cubic_phase_offset", radial_v=-0.09, inward=0.68)]

        result = classify_transport_packet(rows, TransportPacket3DOptions())

        self.assertEqual(result["label"], "moving_transport_packet_supported")

    def test_classification_detects_drifting_modal_structure(self) -> None:
        rows = [
            _row("neutral_cubic_sign_flip_reference", radial_v=0.01, inward=0.51, phase_v=0.06),
            _row("neutral_cubic_phase_offset", radial_v=0.00, inward=0.50, angular=0.04),
        ]

        result = classify_transport_packet(rows, TransportPacket3DOptions())

        self.assertEqual(result["label"], "drifting_modal_structure_supported")

    def test_classification_detects_mixed_transport_and_drift(self) -> None:
        rows = [
            _row("neutral_cubic_sign_flip_reference", radial_v=-0.08, inward=0.71),
            _row("neutral_cubic_phase_offset", radial_v=0.01, inward=0.50, phase_v=0.05),
        ]

        result = classify_transport_packet(rows, TransportPacket3DOptions())

        self.assertEqual(result["label"], "mixed_transport_and_drift")


def _row(
    variant: str,
    *,
    radial_v: float,
    inward: float,
    phase_v: float = 0.0,
    angular: float = 0.0,
) -> dict:
    return {
        "variant": variant,
        "radial_group_velocity": radial_v,
        "inward_flux_fraction": inward,
        "outward_flux_fraction": 1.0 - inward,
        "shell_exit_detected": False,
        "mean_angular_drift_rate": angular,
        "shell_phase_velocity": phase_v,
    }


if __name__ == "__main__":
    unittest.main()
