import unittest

import numpy as np

from simulation.config import SimulationConfig
from simulation.prototype_3d import Lattice3D
from simulation.prototype_3d_isochronous_anchor_cleanup_control import (
    ISOCHRONOUS_ANCHOR_CLEANUP_ROLES,
    IsochronousAnchorCleanupOptions,
    build_isochronous_anchor_cleanup_variants,
    classify_isochronous_anchor_cleanup,
    validate_isochronous_anchor_cleanup_guardrails,
    _comparison_rows,
)


class IsochronousAnchorCleanupControlTests(unittest.TestCase):
    def test_fixed_cleanup_rows_are_41_only_and_passive(self) -> None:
        variants = build_isochronous_anchor_cleanup_variants(SimulationConfig(), IsochronousAnchorCleanupOptions())

        self.assertEqual([getattr(variant, "_cleanup_role") for variant in variants], list(ISOCHRONOUS_ANCHOR_CLEANUP_ROLES))
        self.assertEqual({variant.grid_size for variant in variants}, {41})
        self.assertEqual({variant.drive_cutoff_time for variant in variants}, {17.94})
        self.assertEqual({variant.drive_frequency for variant in variants}, {0.92})
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))
        by_role = {getattr(variant, "_cleanup_role"): variant for variant in variants}
        self.assertEqual(by_role["isochronous_anchor_0p5x_reference"].memory_mechanism_profile, "isochronous_cubic_anchor")
        self.assertEqual(by_role["isochronous_anchor_0p5x_smooth_taper"].memory_mechanism_profile, "isochronous_cubic_anchor_smooth_taper")
        self.assertEqual(by_role["isochronous_anchor_0p5x_wide_smooth_taper"].memory_mechanism_profile, "isochronous_cubic_anchor_wide_smooth_taper")
        self.assertEqual(by_role["isochronous_anchor_0p5x_weaker_compensation"].memory_mechanism_profile, "isochronous_cubic_anchor_weaker_compensation")
        self.assertEqual(by_role["smooth_radial_compensation_only"].memory_mechanism_profile, "smooth_radial_compensation")
        self.assertAlmostEqual(abs(by_role["random_equivalent_0p5x"].memory_mechanism_strength), abs(by_role["isochronous_anchor_0p5x_smooth_taper"].memory_mechanism_strength))

    def test_cleanup_profiles_apply_passive_stiffness_variation(self) -> None:
        variants = build_isochronous_anchor_cleanup_variants(SimulationConfig(), IsochronousAnchorCleanupOptions())
        by_role = {getattr(variant, "_cleanup_role"): variant for variant in variants}

        for role in (
            "isochronous_anchor_0p5x_smooth_taper",
            "isochronous_anchor_0p5x_wide_smooth_taper",
            "isochronous_anchor_0p5x_weaker_compensation",
            "smooth_radial_compensation_only",
        ):
            lattice = Lattice3D(by_role[role])
            self.assertGreater(float(np.std(lattice.stiffness)), 0.0)

    def test_cleanup_supported_when_memory_strict_comb_and_off_comb_pass(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("random", "random_equivalent_0p5x", "control", 0.49, 9, 8, 0.69, 0.101, True),
            self._row("reference", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True, matched="random_equivalent_0p5x"),
            self._row("cleanup", "isochronous_anchor_0p5x_smooth_taper", "cleanup", 0.62, 9, 8, 0.68, 0.104, True, matched="random_equivalent_0p5x"),
        ]
        comparisons = _comparison_rows(rows, IsochronousAnchorCleanupOptions())

        result = classify_isochronous_anchor_cleanup(rows, comparisons, IsochronousAnchorCleanupOptions())

        self.assertEqual(result["label"], "isochronous_anchor_cleanup_supported")

    def test_cleanup_memory_only_when_off_comb_still_worsens(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("random", "random_equivalent_0p5x", "control", 0.49, 9, 8, 0.69, 0.101, True),
            self._row("reference", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True, matched="random_equivalent_0p5x"),
            self._row("cleanup", "isochronous_anchor_0p5x_smooth_taper", "cleanup", 0.62, 9, 8, 0.68, 0.120, True, matched="random_equivalent_0p5x"),
        ]
        comparisons = _comparison_rows(rows, IsochronousAnchorCleanupOptions())

        result = classify_isochronous_anchor_cleanup(rows, comparisons, IsochronousAnchorCleanupOptions())

        self.assertEqual(result["label"], "cleanup_memory_only_tradeoff")

    def test_cleanup_no_signal_when_cleanup_loses_memory_advantage(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("random", "random_equivalent_0p5x", "control", 0.51, 9, 8, 0.69, 0.101, True),
            self._row("reference", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True, matched="random_equivalent_0p5x"),
            self._row("cleanup", "isochronous_anchor_0p5x_smooth_taper", "cleanup", 0.505, 9, 8, 0.68, 0.104, True, matched="random_equivalent_0p5x"),
        ]
        comparisons = _comparison_rows(rows, IsochronousAnchorCleanupOptions())

        result = classify_isochronous_anchor_cleanup(rows, comparisons, IsochronousAnchorCleanupOptions())

        self.assertEqual(result["label"], "cleanup_no_signal")

    def test_required_controls_missing_or_dirty_mark_invalid(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("random", "random_equivalent_0p5x", "control", 0.49, 9, 8, 0.69, 0.101, True),
        ]

        result = classify_isochronous_anchor_cleanup(rows, [], IsochronousAnchorCleanupOptions())

        self.assertEqual(result["label"], "invalid_cleanup_test")
        self.assertIn("isochronous_anchor_0p5x_reference", result["checks"]["missing_required_artifacts"])

        dirty_rows = rows + [
            self._row("reference", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, False, matched="random_equivalent_0p5x")
        ]
        dirty_result = classify_isochronous_anchor_cleanup(dirty_rows, _comparison_rows(dirty_rows, IsochronousAnchorCleanupOptions()), IsochronousAnchorCleanupOptions())
        self.assertEqual(dirty_result["label"], "invalid_cleanup_test")
        self.assertIn("reference", dirty_result["checks"]["required_clean_gate_failures"])

    def test_missing_artifacts_and_guardrails(self) -> None:
        result = classify_isochronous_anchor_cleanup([], [], IsochronousAnchorCleanupOptions())
        self.assertEqual(result["label"], "invalid_cleanup_test")
        self.assertIn("neutral_reference", result["checks"]["missing_required_artifacts"])

        self.assertIn(
            "isochronous anchor cleanup is fixed to 41^3",
            validate_isochronous_anchor_cleanup_guardrails(IsochronousAnchorCleanupOptions(grid_size=51)),
        )
        self.assertIn(
            "cutoff phase/timing tuning is forbidden",
            validate_isochronous_anchor_cleanup_guardrails(IsochronousAnchorCleanupOptions(fixed_cutoff=17.93)),
        )

    def _row(
        self,
        variant: str,
        role: str,
        kind: str,
        memory: float,
        major: int,
        refocus: int,
        comb: float,
        off_comb: float,
        clean: bool,
        *,
        matched: str = "",
        pair_count: int = 3,
    ) -> dict[str, object]:
        return {
            "variant": variant,
            "run_stage": "isochronous_anchor_cleanup_41",
            "mechanism_role": role,
            "mechanism_profile": "isochronous_cubic_anchor_smooth_taper",
            "mechanism_strength_factor": 0.5,
            "cleanup_kind": kind,
            "matched_random_role": matched,
            "pattern_memory_score": memory,
            "pattern_memory_pair_count": pair_count,
            "conservative_major_peaks": major,
            "conservative_refocus_peaks": refocus,
            "return_timing_comb_score": comb,
            "off_comb_energy_ratio": off_comb,
            "modal_participation_ratio": 1.0,
            "energy_accounting_clean": True,
            "no_post_cutoff_external_work": True,
            "global_outer_false": True,
            "clean_gates_passed": clean,
        }


if __name__ == "__main__":
    unittest.main()
