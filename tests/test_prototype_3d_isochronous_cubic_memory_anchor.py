import unittest

import numpy as np

from simulation.config import SimulationConfig
from simulation.prototype_3d import Lattice3D
from simulation.prototype_3d_isochronous_cubic_memory_anchor import (
    ISOCHRONOUS_CUBIC_ANCHOR_ROLES,
    IsochronousCubicMemoryAnchorOptions,
    build_isochronous_cubic_anchor_variants,
    classify_isochronous_cubic_anchor,
    validate_isochronous_cubic_anchor_guardrails,
    _comparison_rows,
)


class IsochronousCubicMemoryAnchorTests(unittest.TestCase):
    def test_fixed_anchor_map_construction_is_41_only_and_passive(self) -> None:
        variants = build_isochronous_cubic_anchor_variants(SimulationConfig(), IsochronousCubicMemoryAnchorOptions())

        self.assertEqual([getattr(variant, "_anchor_role") for variant in variants], list(ISOCHRONOUS_CUBIC_ANCHOR_ROLES))
        self.assertEqual({variant.grid_size for variant in variants}, {41})
        self.assertEqual({variant.drive_cutoff_time for variant in variants}, {17.94})
        self.assertEqual({variant.drive_frequency for variant in variants}, {0.92})
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))
        by_role = {getattr(variant, "_anchor_role"): variant for variant in variants}
        self.assertEqual(by_role["radial_compensation_only"].memory_mechanism_profile, "radial_compensation")
        self.assertEqual(by_role["isochronous_anchor_0p5x"].memory_mechanism_profile, "isochronous_cubic_anchor")

    def test_anchor_profile_applies_passive_stiffness_variation(self) -> None:
        variants = build_isochronous_cubic_anchor_variants(SimulationConfig(), IsochronousCubicMemoryAnchorOptions())
        by_role = {getattr(variant, "_anchor_role"): variant for variant in variants}

        radial_lattice = Lattice3D(by_role["radial_compensation_only"])
        anchor_lattice = Lattice3D(by_role["isochronous_anchor_0p5x"])

        self.assertGreater(float(np.std(radial_lattice.stiffness)), 0.0)
        self.assertGreater(float(np.std(anchor_lattice.stiffness)), 0.0)

    def test_matched_randomized_controls_use_same_strength_factors(self) -> None:
        variants = build_isochronous_cubic_anchor_variants(SimulationConfig(), IsochronousCubicMemoryAnchorOptions())
        by_role = {getattr(variant, "_anchor_role"): variant for variant in variants}

        self.assertAlmostEqual(abs(by_role["isochronous_anchor_0p5x"].memory_mechanism_strength), abs(by_role["random_equivalent_0p5x"].memory_mechanism_strength))
        self.assertAlmostEqual(abs(by_role["isochronous_anchor_1p0x"].memory_mechanism_strength), abs(by_role["random_equivalent_1p0x"].memory_mechanism_strength))
        self.assertEqual(getattr(by_role["isochronous_anchor_0p5x"], "_matched_random_role"), "random_equivalent_0p5x")
        self.assertEqual(getattr(by_role["isochronous_anchor_1p0x"], "_matched_random_role"), "random_equivalent_1p0x")

    def test_supported_when_memory_strict_comb_and_off_comb_all_pass(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.50, 9, 8, 0.70, True),
            self._row("random_half", "random_equivalent_0p5x", 0.52, 9, 8, 0.69, True),
            self._row("random", "random_equivalent_1p0x", 0.53, 9, 8, 0.68, True),
            self._row("anchor", "isochronous_anchor_1p0x", 0.62, 9, 8, 0.66, True, matched="random_equivalent_1p0x", off_comb=0.09),
        ]
        comparisons = _comparison_rows(rows, IsochronousCubicMemoryAnchorOptions())

        result = classify_isochronous_cubic_anchor(rows, comparisons, IsochronousCubicMemoryAnchorOptions())

        self.assertEqual(result["label"], "isochronous_cubic_anchor_supported")

    def test_memory_only_when_anchor_beats_controls_but_comb_strict_or_off_comb_drops(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.50, 9, 8, 0.70, True),
            self._row("random_half", "random_equivalent_0p5x", 0.52, 9, 8, 0.69, True),
            self._row("random", "random_equivalent_1p0x", 0.53, 9, 8, 0.68, True),
            self._row("anchor", "isochronous_anchor_1p0x", 0.62, 9, 8, 0.68, True, matched="random_equivalent_1p0x", off_comb=0.12),
        ]
        comparisons = _comparison_rows(rows, IsochronousCubicMemoryAnchorOptions())

        result = classify_isochronous_cubic_anchor(rows, comparisons, IsochronousCubicMemoryAnchorOptions())

        self.assertEqual(result["label"], "memory_only_anchor_tradeoff")

    def test_diagnostic_row_clean_failure_does_not_invalidate_anchor_test(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.50, 9, 8, 0.70, True),
            self._row("random_half", "random_equivalent_0p5x", 0.52, 9, 8, 0.69, True),
            self._row("random", "random_equivalent_1p0x", 0.53, 9, 8, 0.68, True),
            self._row("radial", "radial_compensation_only", 0.54, 6, 5, 0.68, False),
            self._row("anchor", "isochronous_anchor_1p0x", 0.62, 9, 8, 0.66, True, matched="random_equivalent_1p0x", off_comb=0.09),
        ]
        comparisons = _comparison_rows(rows, IsochronousCubicMemoryAnchorOptions())

        result = classify_isochronous_cubic_anchor(rows, comparisons, IsochronousCubicMemoryAnchorOptions())

        self.assertEqual(result["label"], "isochronous_cubic_anchor_supported")
        self.assertEqual(result["checks"]["control_clean_gate_failures"], [])

    def test_no_signal_when_anchor_does_not_beat_random_control(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.50, 9, 8, 0.70, True),
            self._row("random_half", "random_equivalent_0p5x", 0.52, 9, 8, 0.69, True),
            self._row("random", "random_equivalent_1p0x", 0.64, 9, 8, 0.68, True),
            self._row("anchor", "isochronous_anchor_1p0x", 0.62, 9, 8, 0.66, True, matched="random_equivalent_1p0x"),
        ]
        comparisons = _comparison_rows(rows, IsochronousCubicMemoryAnchorOptions())

        result = classify_isochronous_cubic_anchor(rows, comparisons, IsochronousCubicMemoryAnchorOptions())

        self.assertEqual(result["label"], "no_isochronous_anchor_signal")

    def test_guardrails_reject_cutoff_tuning_and_non_41_grid(self) -> None:
        cutoff_options = IsochronousCubicMemoryAnchorOptions(fixed_cutoff=17.93)
        grid_options = IsochronousCubicMemoryAnchorOptions(grid_size=51)

        self.assertIn("cutoff phase/timing tuning is forbidden", validate_isochronous_cubic_anchor_guardrails(cutoff_options))
        self.assertIn("isochronous cubic anchor is fixed to 41^3", validate_isochronous_cubic_anchor_guardrails(grid_options))

    def test_missing_artifacts_mark_invalid(self) -> None:
        result = classify_isochronous_cubic_anchor([], [], IsochronousCubicMemoryAnchorOptions())

        self.assertEqual(result["label"], "invalid_anchor_test")
        self.assertIn("neutral_reference", result["checks"]["missing_required_artifacts"])

    def _row(
        self,
        variant: str,
        role: str,
        memory: float,
        major: int,
        refocus: int,
        comb: float,
        clean: bool,
        *,
        matched: str = "",
        off_comb: float = 0.1,
    ) -> dict[str, object]:
        return {
            "variant": variant,
            "run_stage": "isochronous_anchor_41",
            "mechanism_role": role,
            "mechanism_profile": "isochronous_cubic_anchor",
            "mechanism_strength_factor": 1.0,
            "anchor_kind": "isochronous_anchor",
            "matched_random_role": matched,
            "pattern_memory_score": memory,
            "pattern_memory_pair_count": 3,
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
