import unittest

import numpy as np

from simulation.config import SimulationConfig
from simulation.prototype_3d import Lattice3D
from simulation.prototype_3d_sacred_geometry_memory_anchor import (
    SACRED_GEOMETRY_MEMORY_ANCHOR_ROLES,
    SacredGeometryMemoryAnchorOptions,
    build_sacred_geometry_memory_anchor_variants,
    classify_sacred_geometry_memory_anchor,
    validate_sacred_geometry_memory_anchor_guardrails,
    _comparison_rows,
    _pattern_similarity_rows,
)


class SacredGeometryMemoryAnchorTests(unittest.TestCase):
    def test_fixed_rows_are_41_only_and_passive(self) -> None:
        options = SacredGeometryMemoryAnchorOptions()
        variants = build_sacred_geometry_memory_anchor_variants(SimulationConfig(), options)

        self.assertEqual([getattr(variant, "_sacred_geometry_role") for variant in variants], list(SACRED_GEOMETRY_MEMORY_ANCHOR_ROLES))
        self.assertEqual({variant.grid_size for variant in variants}, {41})
        self.assertEqual({variant.drive_cutoff_time for variant in variants}, {17.94})
        self.assertEqual({variant.drive_frequency for variant in variants}, {0.92})
        self.assertTrue(all(variant.second_pulse_center_time is None for variant in variants))
        self.assertTrue(all(not variant.resonator_enabled for variant in variants))
        by_role = {getattr(variant, "_sacred_geometry_role"): variant for variant in variants}
        self.assertEqual(by_role["isochronous_anchor_0p5x_reference"].memory_mechanism_profile, "isochronous_cubic_anchor")
        self.assertEqual(by_role["icosahedral_shell_anchor"].memory_mechanism_profile, "icosahedral_shell_anchor")
        self.assertEqual(by_role["dodecahedral_shell_anchor"].memory_mechanism_profile, "dodecahedral_shell_anchor")
        self.assertEqual(by_role["golden_ratio_double_shell_anchor"].memory_mechanism_profile, "golden_ratio_double_shell_anchor")
        self.assertEqual(by_role["hex_flower_shell_projection_anchor"].memory_mechanism_profile, "hex_flower_shell_projection_anchor")
        self.assertEqual(by_role["randomized_matched_strength_control"].memory_mechanism_profile, "random_sacred_geometry_anchor")
        sacred_strengths = {
            by_role[role].memory_mechanism_strength
            for role in (
                "icosahedral_shell_anchor",
                "dodecahedral_shell_anchor",
                "golden_ratio_double_shell_anchor",
                "hex_flower_shell_projection_anchor",
                "randomized_matched_strength_control",
            )
        }
        self.assertEqual(len(sacred_strengths), 1)
        self.assertAlmostEqual(sacred_strengths.pop(), options.mechanism_strength * options.geometry_strength_factor)

    def test_geometry_profiles_apply_strength_matched_passive_stiffness(self) -> None:
        variants = build_sacred_geometry_memory_anchor_variants(SimulationConfig(), SacredGeometryMemoryAnchorOptions())
        by_role = {getattr(variant, "_sacred_geometry_role"): variant for variant in variants}
        neutral = Lattice3D(by_role["neutral_reference"])

        for role in (
            "icosahedral_shell_anchor",
            "dodecahedral_shell_anchor",
            "golden_ratio_double_shell_anchor",
            "hex_flower_shell_projection_anchor",
            "randomized_matched_strength_control",
        ):
            lattice = Lattice3D(by_role[role])
            active = lattice.coords["boundary_distance"] >= lattice.config.sponge_width
            relative_delta = lattice.stiffness / np.maximum(neutral.stiffness, 1.0e-12) - 1.0
            rms = float(np.sqrt(np.mean(relative_delta[active] ** 2)))
            self.assertGreater(float(np.std(relative_delta[active])), 0.0)
            self.assertAlmostEqual(rms, abs(lattice.config.memory_mechanism_strength), places=9)
            self.assertTrue(np.allclose(lattice.damping, neutral.damping))

    def test_supported_when_memory_strict_comb_off_comb_and_controls_pass(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("random", "randomized_matched_strength_control", "random", 0.51, 9, 8, 0.69, 0.105, True),
            self._row("sacred", "icosahedral_shell_anchor", "sacred_anchor", 0.62, 9, 8, 0.68, 0.110, True),
        ]
        _pattern_similarity_rows(rows)
        comparisons = _comparison_rows(rows, SacredGeometryMemoryAnchorOptions())

        result = classify_sacred_geometry_memory_anchor(rows, comparisons, SacredGeometryMemoryAnchorOptions())

        self.assertEqual(result["label"], "sacred_geometry_anchor_supported")

    def test_memory_only_when_off_comb_or_strict_trade_down(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("random", "randomized_matched_strength_control", "random", 0.51, 9, 8, 0.69, 0.105, True),
            self._row("sacred", "icosahedral_shell_anchor", "sacred_anchor", 0.62, 8, 7, 0.68, 0.120, True),
        ]
        _pattern_similarity_rows(rows)
        comparisons = _comparison_rows(rows, SacredGeometryMemoryAnchorOptions())

        result = classify_sacred_geometry_memory_anchor(rows, comparisons, SacredGeometryMemoryAnchorOptions())

        self.assertEqual(result["label"], "sacred_geometry_memory_only_tradeoff")

    def test_no_signal_when_sacred_rows_do_not_beat_random_control(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("random", "randomized_matched_strength_control", "random", 0.54, 9, 8, 0.69, 0.105, True),
            self._row("sacred", "icosahedral_shell_anchor", "sacred_anchor", 0.52, 9, 8, 0.68, 0.110, True),
        ]
        _pattern_similarity_rows(rows)
        comparisons = _comparison_rows(rows, SacredGeometryMemoryAnchorOptions())

        result = classify_sacred_geometry_memory_anchor(rows, comparisons, SacredGeometryMemoryAnchorOptions())

        self.assertEqual(result["label"], "sacred_geometry_no_signal")

    def test_required_controls_missing_or_dirty_mark_invalid(self) -> None:
        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
        ]
        _pattern_similarity_rows(rows)

        result = classify_sacred_geometry_memory_anchor(rows, _comparison_rows(rows, SacredGeometryMemoryAnchorOptions()), SacredGeometryMemoryAnchorOptions())

        self.assertEqual(result["label"], "invalid_sacred_geometry_test")
        self.assertIn("randomized_matched_strength_control", result["checks"]["missing_required_artifacts"])

        dirty_rows = rows + [self._row("random", "randomized_matched_strength_control", "random", 0.51, 9, 8, 0.69, 0.105, False)]
        _pattern_similarity_rows(dirty_rows)
        dirty_result = classify_sacred_geometry_memory_anchor(
            dirty_rows,
            _comparison_rows(dirty_rows, SacredGeometryMemoryAnchorOptions()),
            SacredGeometryMemoryAnchorOptions(),
        )
        self.assertEqual(dirty_result["label"], "invalid_sacred_geometry_test")
        self.assertIn("random", dirty_result["checks"]["required_clean_gate_failures"])

    def test_missing_artifacts_and_guardrails(self) -> None:
        result = classify_sacred_geometry_memory_anchor([], [], SacredGeometryMemoryAnchorOptions())
        self.assertEqual(result["label"], "invalid_sacred_geometry_test")
        self.assertIn("neutral_reference", result["checks"]["missing_required_artifacts"])

        rows = [
            self._row("neutral", "neutral_reference", "control", 0.50, 9, 8, 0.70, 0.100, True, pair_count=0),
            self._row("anchor", "isochronous_anchor_0p5x_reference", "reference", 0.63, 9, 8, 0.70, 0.115, True),
            self._row("random", "randomized_matched_strength_control", "random", 0.51, 9, 8, 0.69, 0.105, True),
        ]
        _pattern_similarity_rows(rows)
        artifact_result = classify_sacred_geometry_memory_anchor(
            rows,
            _comparison_rows(rows, SacredGeometryMemoryAnchorOptions()),
            SacredGeometryMemoryAnchorOptions(),
        )
        self.assertEqual(artifact_result["label"], "invalid_sacred_geometry_test")
        self.assertIn("neutral", artifact_result["checks"]["missing_required_artifacts"])

        self.assertIn(
            "sacred-geometry memory anchor is fixed to 41^3",
            validate_sacred_geometry_memory_anchor_guardrails(SacredGeometryMemoryAnchorOptions(grid_size=51)),
        )
        self.assertIn(
            "cutoff phase/timing tuning is forbidden",
            validate_sacred_geometry_memory_anchor_guardrails(SacredGeometryMemoryAnchorOptions(fixed_cutoff=17.93)),
        )
        self.assertIn(
            "frequency/source-shape tuning is forbidden",
            validate_sacred_geometry_memory_anchor_guardrails(SacredGeometryMemoryAnchorOptions(fixed_drive_frequency=0.91)),
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
            "run_stage": "sacred_geometry_anchor_41",
            "mechanism_role": role,
            "mechanism_profile": "icosahedral_shell_anchor",
            "mechanism_strength_factor": 0.5,
            "sacred_geometry_kind": kind,
            "matched_random_role": "randomized_matched_strength_control" if kind == "sacred_anchor" else "",
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
