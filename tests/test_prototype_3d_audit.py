"""Tests for 3D prototype failure-mode audits."""

from __future__ import annotations

import unittest

from simulation.prototype_3d_audit import (
    Prototype3DFailureAuditOptions,
    _geometry_audit,
    classify_3d_failure_audit,
)
from tests.test_prototype_3d import _small_3d_config


class Prototype3DFailureAuditTests(unittest.TestCase):
    def test_classifies_boundary_layer_trapped_reference(self) -> None:
        rows = [
            {
                "variant": "boundary_cubic_31",
                "drive_location": "boundary",
                "source_sponge_overlap_fraction": 1.0,
                "outer_to_near_tail_energy_ratio": 25.0,
                "global_peak_in_outer_window": True,
                "near_shell_peak_fraction_of_work": 1e-10,
                "first_meaningful_near_shell_arrival_time": None,
                "near_shell_tail_retention": 0.0,
                "near_shell_tail_fraction_of_total": 0.001,
            }
        ]

        result = classify_3d_failure_audit(rows, Prototype3DFailureAuditOptions())

        self.assertEqual(result["label"], "boundary_layer_trapped")

    def test_boundary_source_overlap_with_sponge_is_reported(self) -> None:
        config = _small_3d_config("boundary", "uniform")

        result = _geometry_audit(config)

        self.assertGreater(result["source_cell_count"], 0)
        self.assertGreater(result["source_sponge_overlap_fraction"], 0.0)
        self.assertLessEqual(result["source_sponge_overlap_fraction"], 1.0)


if __name__ == "__main__":
    unittest.main()
