import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d_cubic_memory_tradeoff_map import (
    CUBIC_MEMORY_TRADEOFF_ROLES,
    CubicMemoryTradeoffMapOptions,
    build_cubic_memory_tradeoff_variants,
    classify_cubic_memory_tradeoff,
    validate_cubic_memory_tradeoff_guardrails,
    _comparison_rows,
)


class CubicMemoryTradeoffMapTests(unittest.TestCase):
    def test_fixed_map_construction_is_41_only_and_passive(self) -> None:
        options = CubicMemoryTradeoffMapOptions()
        variants = build_cubic_memory_tradeoff_variants(SimulationConfig(), options)

        self.assertEqual([getattr(variant, "_tradeoff_role") for variant in variants], list(CUBIC_MEMORY_TRADEOFF_ROLES))
        self.assertEqual({variant.grid_size for variant in variants}, {41})
        self.assertEqual({variant.drive_cutoff_time for variant in variants}, {17.94})
        self.assertEqual({variant.drive_frequency for variant in variants}, {0.92})
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertEqual(variants[0].memory_mechanism_profile, "none")

    def test_matched_randomized_controls_use_same_strength_factors(self) -> None:
        variants = build_cubic_memory_tradeoff_variants(SimulationConfig(), CubicMemoryTradeoffMapOptions())
        by_role = {getattr(variant, "_tradeoff_role"): variant for variant in variants}

        self.assertAlmostEqual(abs(by_role["cubic_split_0p5x"].memory_mechanism_strength), abs(by_role["random_equivalent_0p5x"].memory_mechanism_strength))
        self.assertAlmostEqual(abs(by_role["cubic_split_1p0x"].memory_mechanism_strength), abs(by_role["random_equivalent_1p0x"].memory_mechanism_strength))
        self.assertEqual(getattr(by_role["cubic_split_0p5x"], "_matched_random_role"), "random_equivalent_0p5x")
        self.assertEqual(getattr(by_role["cubic_split_1p5x"], "_matched_random_role"), "")
        self.assertLess(by_role["cubic_split_sign_flipped_1p0x"].memory_mechanism_strength, 0.0)

    def test_tradeoff_classification_supported_when_memory_and_strict_preserved(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.50, 9, 8, True),
            self._row("random_half", "random_equivalent_0p5x", 0.52, 9, 8, True),
            self._row("random", "random_equivalent_1p0x", 0.53, 9, 8, True),
            self._row("cubic", "cubic_split_1p0x", 0.62, 9, 8, True, matched="random_equivalent_1p0x"),
        ]
        comparisons = _comparison_rows(rows, CubicMemoryTradeoffMapOptions())

        result = classify_cubic_memory_tradeoff(rows, comparisons, CubicMemoryTradeoffMapOptions())

        self.assertEqual(result["label"], "cubic_memory_tradeoff_supported")

    def test_tradeoff_classification_memory_only_when_strict_drops(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.50, 9, 8, True),
            self._row("random_half", "random_equivalent_0p5x", 0.52, 9, 8, True),
            self._row("random", "random_equivalent_1p0x", 0.53, 9, 8, True),
            self._row("cubic", "cubic_split_1p0x", 0.62, 8, 7, True, matched="random_equivalent_1p0x"),
        ]
        comparisons = _comparison_rows(rows, CubicMemoryTradeoffMapOptions())

        result = classify_cubic_memory_tradeoff(rows, comparisons, CubicMemoryTradeoffMapOptions())

        self.assertEqual(result["label"], "memory_only_tradeoff_supported")

    def test_tradeoff_classification_no_tradeoff_when_random_not_beaten(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.50, 9, 8, True),
            self._row("random_half", "random_equivalent_0p5x", 0.52, 9, 8, True),
            self._row("random", "random_equivalent_1p0x", 0.64, 9, 8, True),
            self._row("cubic", "cubic_split_1p0x", 0.62, 9, 8, True, matched="random_equivalent_1p0x"),
        ]
        comparisons = _comparison_rows(rows, CubicMemoryTradeoffMapOptions())

        result = classify_cubic_memory_tradeoff(rows, comparisons, CubicMemoryTradeoffMapOptions())

        self.assertEqual(result["label"], "no_cubic_tradeoff")

    def test_closed_branch_guardrails_reject_cutoff_tuning_and_non_41_grid(self) -> None:
        cutoff_options = CubicMemoryTradeoffMapOptions(fixed_cutoff=17.93)
        grid_options = CubicMemoryTradeoffMapOptions(grid_size=51)

        self.assertIn("cutoff phase/timing tuning is forbidden", validate_cubic_memory_tradeoff_guardrails(cutoff_options))
        self.assertIn("cubic memory tradeoff map is fixed to 41^3", validate_cubic_memory_tradeoff_guardrails(grid_options))

    def test_missing_artifact_handling_marks_invalid(self) -> None:
        result = classify_cubic_memory_tradeoff([], [], CubicMemoryTradeoffMapOptions())

        self.assertEqual(result["label"], "invalid_tradeoff")
        self.assertIn("neutral_reference", result["checks"]["missing_required_artifacts"])

    def _row(
        self,
        variant: str,
        role: str,
        memory: float,
        major: int,
        refocus: int,
        clean: bool,
        *,
        matched: str = "",
    ) -> dict[str, object]:
        return {
            "variant": variant,
            "run_stage": "cubic_memory_41",
            "mechanism_role": role,
            "mechanism_profile": "cubic_degeneracy_split",
            "mechanism_strength_factor": 1.0,
            "matched_random_role": matched,
            "pattern_memory_score": memory,
            "pattern_memory_pair_count": 3,
            "conservative_major_peaks": major,
            "conservative_refocus_peaks": refocus,
            "return_timing_comb_score": 0.7,
            "off_comb_energy_ratio": 0.1,
            "modal_participation_ratio": 1.0,
            "energy_accounting_clean": True,
            "no_post_cutoff_external_work": True,
            "global_outer_false": True,
            "clean_gates_passed": clean,
        }


if __name__ == "__main__":
    unittest.main()
