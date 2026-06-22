import unittest

import numpy as np

from simulation.config import SimulationConfig
from simulation.prototype_3d import Lattice3D
from simulation.prototype_3d_angular_mode_cleanup_control import (
    ANGULAR_MODE_CLEANUP_ROLES,
    AngularModeCleanupOptions,
    build_angular_mode_cleanup_variants,
    classify_angular_mode_cleanup,
    validate_angular_mode_cleanup_guardrails,
    _comparison_rows,
)


class AngularModeCleanupControlTests(unittest.TestCase):
    def test_fixed_rows_are_41_only_and_passive(self) -> None:
        options = AngularModeCleanupOptions()
        variants = build_angular_mode_cleanup_variants(SimulationConfig(), options)

        self.assertEqual([getattr(variant, "_angular_cleanup_role") for variant in variants], list(ANGULAR_MODE_CLEANUP_ROLES))
        self.assertEqual({variant.grid_size for variant in variants}, {41})
        self.assertEqual({variant.drive_cutoff_time for variant in variants}, {17.94})
        self.assertEqual({variant.drive_frequency for variant in variants}, {0.92})
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))
        by_role = {getattr(variant, "_angular_cleanup_role"): variant for variant in variants}
        self.assertEqual(by_role["random_equivalent_0p5x"].memory_mechanism_profile, "random_equivalent")
        self.assertEqual(by_role["isochronous_anchor_0p5x_reference"].memory_mechanism_profile, "isochronous_cubic_anchor")
        self.assertEqual(by_role["angular_cleanup_only_weak"].memory_mechanism_profile, "angular_high_mode_cleanup")
        self.assertEqual(by_role["anchor_0p5x_weak_angular_cleanup"].memory_mechanism_profile, "isochronous_anchor_angular_cleanup")
        self.assertEqual(by_role["anchor_0p5x_medium_angular_cleanup"].memory_mechanism_profile, "isochronous_anchor_medium_angular_cleanup")
        self.assertEqual(
            by_role["anchor_0p5x_cubic_preserving_angular_cleanup"].memory_mechanism_profile,
            "isochronous_anchor_cubic_preserving_angular_cleanup",
        )
        self.assertEqual(by_role["randomized_matched_damping_control"].memory_mechanism_profile, "random_angular_cleanup")
        self.assertAlmostEqual(
            getattr(by_role["anchor_0p5x_weak_angular_cleanup"], "_anchor_memory_strength"),
            options.mechanism_strength * 0.5,
        )
        self.assertAlmostEqual(
            by_role["anchor_0p5x_weak_angular_cleanup"].memory_mechanism_strength,
            options.angular_cleanup_strength,
        )
        self.assertAlmostEqual(
            by_role["anchor_0p5x_medium_angular_cleanup"].memory_mechanism_strength,
            options.angular_cleanup_strength * options.medium_cleanup_multiplier,
        )

    def test_angular_cleanup_profiles_apply_passive_damping_shell(self) -> None:
        variants = build_angular_mode_cleanup_variants(SimulationConfig(), AngularModeCleanupOptions())
        by_role = {getattr(variant, "_angular_cleanup_role"): variant for variant in variants}

        neutral = Lattice3D(by_role["neutral_reference"])
        cleanup_only = Lattice3D(by_role["angular_cleanup_only_weak"])
        anchor_reference = Lattice3D(by_role["isochronous_anchor_0p5x_reference"])
        anchor_cleanup = Lattice3D(by_role["anchor_0p5x_weak_angular_cleanup"])
        cubic_preserving = Lattice3D(by_role["anchor_0p5x_cubic_preserving_angular_cleanup"])
        random_damping = Lattice3D(by_role["randomized_matched_damping_control"])

        self.assertGreater(float(np.std(cleanup_only.damping - neutral.damping)), 0.0)
        self.assertGreaterEqual(float(np.min(cleanup_only.damping - neutral.damping)), -1.0e-12)
        self.assertGreater(float(np.std(random_damping.damping - neutral.damping)), 0.0)
        self.assertGreaterEqual(float(np.min(random_damping.damping - neutral.damping)), -1.0e-12)
        self.assertGreater(float(np.std(anchor_cleanup.damping - anchor_reference.damping)), 0.0)
        self.assertGreater(float(np.std(cubic_preserving.damping - anchor_reference.damping)), 0.0)
        self.assertGreater(float(np.std(anchor_cleanup.stiffness - neutral.stiffness)), 0.0)

    def test_supported_when_memory_strict_comb_off_comb_and_controls_pass(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("random", "random_equivalent_0p5x", "control", 0.49, 9, 8, 0.69, 0.101, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("random_damping", "randomized_matched_damping_control", "random_damping", 0.51, 9, 8, 0.70, 0.110, True),
            self._row("cleanup", "anchor_0p5x_weak_angular_cleanup", "cleanup", 0.62, 9, 8, 0.68, 0.108, True),
        ]
        comparisons = _comparison_rows(rows, AngularModeCleanupOptions())

        result = classify_angular_mode_cleanup(rows, comparisons, AngularModeCleanupOptions())

        self.assertEqual(result["label"], "angular_cleanup_supported")

    def test_memory_only_when_cleanup_does_not_reduce_off_comb(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("random", "random_equivalent_0p5x", "control", 0.49, 9, 8, 0.69, 0.101, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("random_damping", "randomized_matched_damping_control", "random_damping", 0.51, 9, 8, 0.70, 0.110, True),
            self._row("cleanup", "anchor_0p5x_weak_angular_cleanup", "cleanup", 0.62, 9, 8, 0.68, 0.120, True),
        ]
        comparisons = _comparison_rows(rows, AngularModeCleanupOptions())

        result = classify_angular_mode_cleanup(rows, comparisons, AngularModeCleanupOptions())

        self.assertEqual(result["label"], "angular_cleanup_memory_only_tradeoff")

    def test_no_signal_when_cleanup_loses_to_controls(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("random", "random_equivalent_0p5x", "control", 0.51, 9, 8, 0.69, 0.101, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("random_damping", "randomized_matched_damping_control", "random_damping", 0.52, 9, 8, 0.70, 0.110, True),
            self._row("cleanup", "anchor_0p5x_weak_angular_cleanup", "cleanup", 0.505, 9, 8, 0.68, 0.108, True),
        ]
        comparisons = _comparison_rows(rows, AngularModeCleanupOptions())

        result = classify_angular_mode_cleanup(rows, comparisons, AngularModeCleanupOptions())

        self.assertEqual(result["label"], "angular_cleanup_no_signal")

    def test_required_controls_missing_or_dirty_mark_invalid(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("random", "random_equivalent_0p5x", "control", 0.49, 9, 8, 0.69, 0.101, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
        ]

        result = classify_angular_mode_cleanup(rows, _comparison_rows(rows, AngularModeCleanupOptions()), AngularModeCleanupOptions())

        self.assertEqual(result["label"], "invalid_angular_cleanup_test")
        self.assertIn("randomized_matched_damping_control", result["checks"]["missing_required_artifacts"])

        dirty_rows = rows + [
            self._row("random_damping", "randomized_matched_damping_control", "random_damping", 0.51, 9, 8, 0.70, 0.110, False)
        ]
        dirty_result = classify_angular_mode_cleanup(dirty_rows, _comparison_rows(dirty_rows, AngularModeCleanupOptions()), AngularModeCleanupOptions())
        self.assertEqual(dirty_result["label"], "invalid_angular_cleanup_test")
        self.assertIn("random_damping", dirty_result["checks"]["required_clean_gate_failures"])

    def test_missing_artifacts_and_guardrails(self) -> None:
        result = classify_angular_mode_cleanup([], [], AngularModeCleanupOptions())
        self.assertEqual(result["label"], "invalid_angular_cleanup_test")
        self.assertIn("neutral_reference", result["checks"]["missing_required_artifacts"])

        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True, pair_count=0),
            self._row("random", "random_equivalent_0p5x", "control", 0.49, 9, 8, 0.69, 0.101, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("random_damping", "randomized_matched_damping_control", "random_damping", 0.51, 9, 8, 0.70, 0.110, True),
        ]
        artifact_result = classify_angular_mode_cleanup(rows, _comparison_rows(rows, AngularModeCleanupOptions()), AngularModeCleanupOptions())
        self.assertEqual(artifact_result["label"], "invalid_angular_cleanup_test")
        self.assertIn("neutral", artifact_result["checks"]["missing_required_artifacts"])

        self.assertIn(
            "angular-mode cleanup control is fixed to 41^3",
            validate_angular_mode_cleanup_guardrails(AngularModeCleanupOptions(grid_size=51)),
        )
        self.assertIn(
            "cutoff phase/timing tuning is forbidden",
            validate_angular_mode_cleanup_guardrails(AngularModeCleanupOptions(fixed_cutoff=17.93)),
        )
        self.assertIn(
            "frequency/source-shape tuning is forbidden",
            validate_angular_mode_cleanup_guardrails(AngularModeCleanupOptions(fixed_drive_frequency=0.91)),
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
            "run_stage": "angular_mode_cleanup_41",
            "mechanism_role": role,
            "mechanism_profile": "isochronous_anchor_angular_cleanup",
            "mechanism_strength_factor": 0.5,
            "anchor_strength_factor": 0.5,
            "angular_cleanup_strength_factor": 1.0,
            "angular_cleanup_strength": 0.006,
            "angular_cleanup_kind": kind,
            "matched_random_role": "random_equivalent_0p5x" if kind == "cleanup" else "",
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
