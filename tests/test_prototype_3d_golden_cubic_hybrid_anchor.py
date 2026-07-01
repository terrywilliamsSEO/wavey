import unittest

import numpy as np

from simulation.config import SimulationConfig
from simulation.prototype_3d import Lattice3D
from simulation.prototype_3d_golden_cubic_hybrid_anchor import (
    GOLDEN_CUBIC_HYBRID_ANCHOR_ROLES,
    GoldenCubicHybridAnchorOptions,
    _combined_strength_factor,
    _comparison_rows,
    _mechanism_comparison_rows,
    build_golden_cubic_hybrid_anchor_variants,
    classify_golden_cubic_hybrid_anchor,
    validate_golden_cubic_hybrid_anchor_guardrails,
)


class GoldenCubicHybridAnchorTests(unittest.TestCase):
    def test_fixed_rows_are_41_only_and_passive(self) -> None:
        options = GoldenCubicHybridAnchorOptions()
        variants = build_golden_cubic_hybrid_anchor_variants(SimulationConfig(), options)

        self.assertEqual([getattr(variant, "_golden_cubic_hybrid_role") for variant in variants], list(GOLDEN_CUBIC_HYBRID_ANCHOR_ROLES))
        self.assertEqual({variant.grid_size for variant in variants}, {41})
        self.assertEqual({variant.drive_cutoff_time for variant in variants}, {17.94})
        self.assertEqual({variant.drive_frequency for variant in variants}, {0.92})
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))

        by_role = {getattr(variant, "_golden_cubic_hybrid_role"): variant for variant in variants}
        self.assertEqual(by_role["neutral_reference"].memory_mechanism_profile, "none")
        self.assertEqual(by_role["isochronous_anchor_0p5x_reference"].memory_mechanism_profile, "isochronous_cubic_anchor")
        self.assertEqual(by_role["golden_ratio_double_shell_reference"].memory_mechanism_profile, "golden_ratio_double_shell_anchor")
        self.assertEqual(by_role["hybrid_cubic_0p5x_golden_0p25x"].memory_mechanism_profile, "golden_cubic_hybrid_anchor")
        self.assertEqual(by_role["hybrid_cubic_0p5x_golden_0p5x"].memory_mechanism_profile, "golden_cubic_hybrid_anchor")
        self.assertEqual(by_role["hybrid_cubic_0p25x_golden_0p5x"].memory_mechanism_profile, "golden_cubic_hybrid_anchor")
        self.assertEqual(by_role["randomized_matched_strength_hybrid_control"].memory_mechanism_profile, "random_golden_cubic_hybrid_anchor")

    def test_hybrid_profile_is_sum_of_cubic_and_golden_components(self) -> None:
        variants = build_golden_cubic_hybrid_anchor_variants(SimulationConfig(), GoldenCubicHybridAnchorOptions())
        by_role = {getattr(variant, "_golden_cubic_hybrid_role"): variant for variant in variants}
        neutral = Lattice3D(by_role["neutral_reference"])
        cubic = Lattice3D(by_role["isochronous_anchor_0p5x_reference"])
        golden = Lattice3D(by_role["golden_ratio_double_shell_reference"])
        hybrid_half_half = Lattice3D(by_role["hybrid_cubic_0p5x_golden_0p5x"])
        hybrid_half_quarter = Lattice3D(by_role["hybrid_cubic_0p5x_golden_0p25x"])

        base = np.maximum(neutral.stiffness, 1.0e-12)
        cubic_delta = cubic.stiffness / base - 1.0
        golden_delta = golden.stiffness / base - 1.0
        half_half_delta = hybrid_half_half.stiffness / base - 1.0
        half_quarter_delta = hybrid_half_quarter.stiffness / base - 1.0

        self.assertTrue(np.allclose(half_half_delta, cubic_delta + golden_delta, atol=1.0e-12))
        self.assertTrue(np.allclose(half_quarter_delta, cubic_delta + 0.5 * golden_delta, atol=1.0e-12))
        self.assertTrue(np.allclose(hybrid_half_half.damping, neutral.damping))

    def test_randomized_hybrid_control_matches_strongest_combined_strength(self) -> None:
        options = GoldenCubicHybridAnchorOptions()
        variants = build_golden_cubic_hybrid_anchor_variants(SimulationConfig(), options)
        by_role = {getattr(variant, "_golden_cubic_hybrid_role"): variant for variant in variants}
        random_control = by_role["randomized_matched_strength_hybrid_control"]
        expected_factor = _combined_strength_factor(0.5, 0.5)

        self.assertAlmostEqual(getattr(random_control, "_mechanism_strength_factor"), expected_factor)
        self.assertAlmostEqual(random_control.memory_mechanism_strength, options.mechanism_strength * expected_factor)

        neutral = Lattice3D(by_role["neutral_reference"])
        random_lattice = Lattice3D(random_control)
        active = random_lattice.coords["boundary_distance"] >= random_lattice.config.sponge_width
        relative_delta = random_lattice.stiffness / np.maximum(neutral.stiffness, 1.0e-12) - 1.0
        rms = float(np.sqrt(np.mean(relative_delta[active] ** 2)))
        self.assertAlmostEqual(rms, random_control.memory_mechanism_strength, places=9)

    def test_supported_when_hybrid_decouples_memory_strict_comb_and_off_comb(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("golden", "golden_ratio_double_shell_reference", "reference", 0.66, 7, 6, 0.55, 0.080, True),
            self._row("random", "randomized_matched_strength_hybrid_control", "random", 0.51, 9, 8, 0.69, 0.105, True),
            self._row("hybrid", "hybrid_cubic_0p5x_golden_0p25x", "hybrid", 0.62, 9, 8, 0.68, 0.110, True),
        ]
        _mechanism_comparison_rows(rows)
        comparisons = _comparison_rows(rows, GoldenCubicHybridAnchorOptions())

        result = classify_golden_cubic_hybrid_anchor(rows, comparisons, GoldenCubicHybridAnchorOptions())

        self.assertEqual(result["label"], "golden_cubic_hybrid_supported")

    def test_memory_only_when_hybrid_keeps_memory_but_loses_strict_or_off_comb(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("golden", "golden_ratio_double_shell_reference", "reference", 0.66, 7, 6, 0.55, 0.080, True),
            self._row("random", "randomized_matched_strength_hybrid_control", "random", 0.51, 9, 8, 0.69, 0.105, True),
            self._row("hybrid", "hybrid_cubic_0p5x_golden_0p25x", "hybrid", 0.62, 8, 7, 0.68, 0.120, True),
        ]
        _mechanism_comparison_rows(rows)
        comparisons = _comparison_rows(rows, GoldenCubicHybridAnchorOptions())

        result = classify_golden_cubic_hybrid_anchor(rows, comparisons, GoldenCubicHybridAnchorOptions())

        self.assertEqual(result["label"], "hybrid_memory_only_tradeoff")

    def test_no_signal_when_hybrid_does_not_beat_random_control(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("golden", "golden_ratio_double_shell_reference", "reference", 0.66, 7, 6, 0.55, 0.080, True),
            self._row("random", "randomized_matched_strength_hybrid_control", "random", 0.56, 9, 8, 0.69, 0.105, True),
            self._row("hybrid", "hybrid_cubic_0p5x_golden_0p25x", "hybrid", 0.54, 9, 8, 0.68, 0.110, True),
        ]
        _mechanism_comparison_rows(rows)
        comparisons = _comparison_rows(rows, GoldenCubicHybridAnchorOptions())

        result = classify_golden_cubic_hybrid_anchor(rows, comparisons, GoldenCubicHybridAnchorOptions())

        self.assertEqual(result["label"], "hybrid_no_signal")

    def test_required_controls_missing_or_dirty_mark_invalid(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("golden", "golden_ratio_double_shell_reference", "reference", 0.66, 7, 6, 0.55, 0.080, True),
        ]
        _mechanism_comparison_rows(rows)
        result = classify_golden_cubic_hybrid_anchor(rows, _comparison_rows(rows, GoldenCubicHybridAnchorOptions()), GoldenCubicHybridAnchorOptions())

        self.assertEqual(result["label"], "invalid_hybrid_test")
        self.assertIn("randomized_matched_strength_hybrid_control", result["checks"]["missing_required_artifacts"])

        dirty_rows = rows + [self._row("random", "randomized_matched_strength_hybrid_control", "random", 0.51, 9, 8, 0.69, 0.105, False)]
        _mechanism_comparison_rows(dirty_rows)
        dirty_result = classify_golden_cubic_hybrid_anchor(
            dirty_rows,
            _comparison_rows(dirty_rows, GoldenCubicHybridAnchorOptions()),
            GoldenCubicHybridAnchorOptions(),
        )
        self.assertEqual(dirty_result["label"], "invalid_hybrid_test")
        self.assertIn("random", dirty_result["checks"]["required_clean_gate_failures"])

    def test_missing_artifacts_and_guardrails(self) -> None:
        result = classify_golden_cubic_hybrid_anchor([], [], GoldenCubicHybridAnchorOptions())
        self.assertEqual(result["label"], "invalid_hybrid_test")
        self.assertIn("neutral_reference", result["checks"]["missing_required_artifacts"])

        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True, pair_count=0),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("golden", "golden_ratio_double_shell_reference", "reference", 0.66, 7, 6, 0.55, 0.080, True),
            self._row("random", "randomized_matched_strength_hybrid_control", "random", 0.51, 9, 8, 0.69, 0.105, True),
        ]
        _mechanism_comparison_rows(rows)
        artifact_result = classify_golden_cubic_hybrid_anchor(
            rows,
            _comparison_rows(rows, GoldenCubicHybridAnchorOptions()),
            GoldenCubicHybridAnchorOptions(),
        )
        self.assertEqual(artifact_result["label"], "invalid_hybrid_test")
        self.assertIn("neutral", artifact_result["checks"]["missing_required_artifacts"])

        self.assertIn(
            "golden/cubic hybrid anchor is fixed to 41^3",
            validate_golden_cubic_hybrid_anchor_guardrails(GoldenCubicHybridAnchorOptions(grid_size=51)),
        )
        self.assertIn(
            "cutoff phase/timing tuning is forbidden",
            validate_golden_cubic_hybrid_anchor_guardrails(GoldenCubicHybridAnchorOptions(fixed_cutoff=17.93)),
        )
        self.assertIn(
            "frequency/source-shape tuning is forbidden",
            validate_golden_cubic_hybrid_anchor_guardrails(GoldenCubicHybridAnchorOptions(fixed_drive_frequency=0.91)),
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
        pair_count: int = 3,
    ) -> dict[str, object]:
        return {
            "variant": variant,
            "run_stage": "golden_cubic_hybrid_anchor_41",
            "mechanism_role": role,
            "mechanism_profile": "golden_cubic_hybrid_anchor" if kind == "hybrid" else "reference",
            "mechanism_strength_factor": _combined_strength_factor(0.5, 0.25) if kind == "hybrid" else 0.5,
            "hybrid_cubic_factor": 0.5 if kind == "hybrid" else 0.0,
            "hybrid_golden_factor": 0.25 if kind == "hybrid" else 0.0,
            "golden_cubic_hybrid_kind": kind,
            "matched_random_role": "randomized_matched_strength_hybrid_control" if kind == "hybrid" else "",
            "pattern_memory_score": memory,
            "pattern_memory_pair_count": pair_count,
            "shell_phase_coherence_mean": 0.70,
            "radial_phase_coherence_mean": 0.72,
            "angular_phase_coherence_mean": 0.71,
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
