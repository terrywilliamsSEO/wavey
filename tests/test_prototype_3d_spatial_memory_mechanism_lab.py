import unittest

import numpy as np

from simulation.config import SimulationConfig
from simulation.prototype_3d_spatial_memory_mechanism_lab import (
    SPATIAL_MEMORY_VARIANT_ROLES,
    SpatialMemoryMechanismLabOptions,
    build_spatial_memory_variants,
    calculate_profile_strength_match,
    calculate_spatial_pattern_memory,
    classify_spatial_memory_mechanism_lab,
    validate_closed_branch_guardrails,
)


class SpatialMemoryMechanismLabTests(unittest.TestCase):
    def test_mechanism_variant_construction_is_fixed_and_passive(self) -> None:
        options = SpatialMemoryMechanismLabOptions()
        variants = build_spatial_memory_variants(SimulationConfig(), options)

        self.assertEqual([getattr(variant, "_spatial_memory_role") for variant in variants], list(SPATIAL_MEMORY_VARIANT_ROLES))
        self.assertEqual({variant.drive_cutoff_time for variant in variants}, {17.94})
        self.assertEqual({variant.drive_frequency for variant in variants}, {0.92})
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertEqual(variants[0].memory_mechanism_profile, "none")
        self.assertEqual(variants[-1].memory_mechanism_profile, "random_equivalent")

    def test_perturbation_strength_matching_uses_rms_strength(self) -> None:
        reference = np.asarray([1.0, -1.0, 1.0, -1.0])
        randomized = np.asarray([-1.0, 1.0, -1.0, 1.0])

        result = calculate_profile_strength_match(reference, randomized, strength=0.035)

        self.assertAlmostEqual(result["reference_strength_l2"], 0.035)
        self.assertAlmostEqual(result["comparison_strength_l2"], 0.035)
        self.assertAlmostEqual(result["relative_match_error"], 0.0)

    def test_spatial_pattern_memory_is_sign_insensitive(self) -> None:
        rows = []
        frames = {
            1: [1.0, -2.0, 3.0],
            2: [-1.0, 2.0, -3.0],
            3: [1.0, -2.0, 3.0],
        }
        for frame_id, values in frames.items():
            for node_index, value in enumerate(values):
                rows.append(
                    {
                        "variant": "unit",
                        "frame_id": frame_id,
                        "peak_rank": frame_id,
                        "time": float(frame_id),
                        "node_index": node_index,
                        "u": value,
                    }
                )

        result = calculate_spatial_pattern_memory(rows)

        self.assertEqual(result["pair_count"], 2)
        self.assertAlmostEqual(result["pattern_memory_score"], 1.0)

    def test_spatial_pattern_memory_accepts_artifact_frame_ids(self) -> None:
        rows = []
        frames = {
            "unit_return_01": (1, 1.0, [1.0, 0.0]),
            "unit_return_02": (2, 2.0, [0.0, 1.0]),
            "unit_return_03": (3, 3.0, [1.0, 0.0]),
        }
        for frame_id, (peak_rank, time, values) in frames.items():
            for node_index, value in enumerate(values):
                rows.append(
                    {
                        "variant": "unit",
                        "frame_id": frame_id,
                        "peak_rank": peak_rank,
                        "time": time,
                        "node_index": node_index,
                        "u": value,
                    }
                )

        result = calculate_spatial_pattern_memory(rows)

        self.assertEqual(result["pair_count"], 2)
        self.assertEqual(result["pair_rows"][0]["from_frame_id"], "unit_return_01")
        self.assertEqual(result["pair_rows"][0]["to_frame_id"], "unit_return_02")

    def test_classification_supported_when_mechanism_beats_reference_and_random_cleanly(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.55, True),
            self._row("random", "random_equivalent_control", 0.56, True),
            self._row("anchor", "anisotropy_anchor", 0.64, True),
        ]
        comparisons = [self._comparison("anchor", "anisotropy_anchor", 0.09, 0.08, True)]

        result = classify_spatial_memory_mechanism_lab(rows, comparisons, SpatialMemoryMechanismLabOptions())

        self.assertEqual(result["label"], "spatial_memory_mechanism_supported")

    def test_classification_partial_when_memory_improves_but_gates_fail(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.55, True),
            self._row("random", "random_equivalent_control", 0.56, True),
            self._row("anchor", "anisotropy_anchor", 0.64, False),
        ]
        comparisons = [self._comparison("anchor", "anisotropy_anchor", 0.09, 0.08, False)]

        result = classify_spatial_memory_mechanism_lab(rows, comparisons, SpatialMemoryMechanismLabOptions())

        self.assertEqual(result["label"], "spatial_memory_partial_signal")

    def test_classification_no_mechanism_when_random_control_is_not_beaten(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", 0.55, True),
            self._row("random", "random_equivalent_control", 0.66, True),
            self._row("anchor", "anisotropy_anchor", 0.64, True),
        ]
        comparisons = [self._comparison("anchor", "anisotropy_anchor", 0.09, -0.02, True)]

        result = classify_spatial_memory_mechanism_lab(rows, comparisons, SpatialMemoryMechanismLabOptions())

        self.assertEqual(result["label"], "no_spatial_memory_mechanism_found")

    def test_closed_branch_guardrails_reject_cutoff_tuning_and_61(self) -> None:
        cutoff_options = SpatialMemoryMechanismLabOptions(fixed_cutoff=17.93)
        grid_options = SpatialMemoryMechanismLabOptions(lift_grid_size=61)

        self.assertIn("cutoff phase/timing tuning is forbidden", validate_closed_branch_guardrails(cutoff_options))
        self.assertIn("61^3 is forbidden", validate_closed_branch_guardrails(grid_options))

    def test_missing_artifact_handling_marks_invalid(self) -> None:
        result = classify_spatial_memory_mechanism_lab([], [], SpatialMemoryMechanismLabOptions())

        self.assertEqual(result["label"], "invalid_mechanism_test")
        self.assertIn("neutral_reference", result["checks"]["missing_required_artifacts"])

    def _row(self, variant: str, role: str, memory: float, clean: bool) -> dict[str, object]:
        return {
            "variant": variant,
            "run_stage": "mechanism_41",
            "mechanism_role": role,
            "pattern_memory_score": memory,
            "pattern_memory_pair_count": 3,
            "energy_accounting_clean": True,
            "no_post_cutoff_external_work": True,
            "global_outer_false": True,
            "clean_gates_passed": clean,
            "random_strength_match_error": 0.0,
        }

    def _comparison(
        self,
        variant: str,
        role: str,
        neutral_delta: float,
        random_delta: float,
        clean: bool,
    ) -> dict[str, object]:
        return {
            "variant": variant,
            "run_stage": "mechanism_41",
            "mechanism_role": role,
            "memory_delta_vs_neutral": neutral_delta,
            "memory_delta_vs_random_control": random_delta,
            "clean_gates_passed": clean,
        }


if __name__ == "__main__":
    unittest.main()
