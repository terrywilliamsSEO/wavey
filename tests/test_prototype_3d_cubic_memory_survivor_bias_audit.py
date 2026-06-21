import tempfile
import unittest
from pathlib import Path

from simulation.prototype_3d_cubic_memory_survivor_bias_audit import (
    CubicMemorySurvivorBiasAuditOptions,
    ReturnFrame,
    classify_cubic_memory_survivor_bias,
    compute_survivor_bias_metrics,
    load_cubic_memory_tradeoff_artifact,
)


def _frame(variant: str, index: int, time: float, values: list[float]) -> ReturnFrame:
    return ReturnFrame(
        variant=variant,
        frame_id=f"{variant}_return_{index:02d}",
        peak_rank=index,
        time=time,
        shell_energy=1.0,
        values={node: value for node, value in enumerate(values)},
    )


def _summary(variant: str, role: str, *, matched_random_role: str = "") -> dict:
    return {
        "variant": variant,
        "mechanism_role": role,
        "mechanism_profile": "cubic_degeneracy_split" if role.startswith("cubic") else "none",
        "mechanism_strength_factor": 0.5 if "0p5x" in role else 0.0,
        "split_orientation": "standard",
        "matched_random_role": matched_random_role,
        "conservative_major_peaks": 9,
        "conservative_refocus_peaks": 8,
        "default_major_peaks_at_0p30": 10,
        "default_refocus_peaks_at_0p30": 9,
        "loose_major_peaks_at_0p25": 11,
        "loose_refocus_peaks_at_0p25": 10,
        "return_timing_comb_score": 0.7,
        "off_comb_energy_ratio": 0.1,
        "clean_gates_passed": True,
    }


class CubicMemorySurvivorBiasAuditTests(unittest.TestCase):
    def test_matched_window_memory_exposes_skipped_return(self) -> None:
        neutral = "cubic_memory_tradeoff_41_neutral_reference"
        random = "cubic_memory_tradeoff_41_random_equivalent_0p5x"
        cubic = "cubic_memory_tradeoff_41_cubic_split_0p5x"
        summaries = [
            _summary(neutral, "neutral_reference"),
            _summary(random, "random_equivalent_0p5x"),
            _summary(cubic, "cubic_split_0p5x", matched_random_role="random_equivalent_0p5x"),
        ]
        frames = {
            neutral: [
                _frame(neutral, 1, 10.0, [1.0, 0.0]),
                _frame(neutral, 2, 20.0, [0.0, 1.0]),
                _frame(neutral, 3, 30.0, [1.0, 0.0]),
                _frame(neutral, 4, 40.0, [0.0, 1.0]),
            ],
            random: [
                _frame(random, 1, 10.0, [1.0, 0.0]),
                _frame(random, 2, 20.0, [0.0, 1.0]),
                _frame(random, 3, 30.0, [1.0, 0.0]),
                _frame(random, 4, 40.0, [0.0, 1.0]),
            ],
            cubic: [
                _frame(cubic, 1, 10.0, [1.0, 0.0]),
                _frame(cubic, 2, 30.0, [1.0, 0.0]),
                _frame(cubic, 3, 40.0, [0.0, 1.0]),
            ],
        }

        rows, matched_rows, index_rows = compute_survivor_bias_metrics(summaries, frames)
        cubic_row = next(row for row in rows if row["variant"] == cubic)

        self.assertAlmostEqual(cubic_row["all_available_memory"], 0.5)
        self.assertAlmostEqual(cubic_row["neutral_predicted_window_memory"], 0.0)
        self.assertAlmostEqual(cubic_row["neutral_window_pair_coverage"], 1.0 / 3.0)
        self.assertTrue(any(row["method"] == "neutral_predicted_window" for row in matched_rows))
        self.assertTrue(any(row["variant"] == cubic and not row["neutral_window_pair_available"] for row in index_rows))

    def test_survivor_bias_classification(self) -> None:
        rows = [
            {
                "variant": "neutral",
                "mechanism_role": "neutral_reference",
                "return_frame_count": 4,
                "all_available_memory": 0.2,
                "first_n_return_index_memory": 0.2,
                "neutral_predicted_window_memory": 0.2,
                "late_return_memory_decay": 0.0,
            },
            {
                "variant": "random",
                "mechanism_role": "random_equivalent_0p5x",
                "return_frame_count": 4,
                "all_available_memory": 0.25,
                "first_n_return_index_memory": 0.25,
                "neutral_predicted_window_memory": 0.25,
                "late_return_memory_decay": 0.0,
            },
            {
                "variant": "cubic",
                "mechanism_role": "cubic_split_0p5x",
                "matched_random_variant": "random",
                "return_frame_count": 3,
                "clean_gates_passed": True,
                "neutral_window_pair_coverage": 0.34,
                "all_available_memory": 0.8,
                "neutral_predicted_window_memory": 0.24,
                "all_available_memory_delta_vs_neutral": 0.6,
                "all_available_memory_delta_vs_matched_random": 0.55,
                "neutral_predicted_window_memory_delta_vs_neutral": 0.04,
                "neutral_predicted_window_memory_delta_vs_matched_random": -0.01,
                "late_return_memory_decay_delta_vs_neutral": -0.1,
                "late_return_memory_decay_delta_vs_matched_random": -0.1,
            },
        ]

        result = classify_cubic_memory_survivor_bias(rows)

        self.assertEqual(result["label"], "cubic_memory_survivor_bias_supported")

    def test_real_same_window_classification(self) -> None:
        rows = [
            {
                "variant": "neutral",
                "mechanism_role": "neutral_reference",
                "return_frame_count": 4,
                "all_available_memory": 0.2,
                "first_n_return_index_memory": 0.2,
                "neutral_predicted_window_memory": 0.2,
                "late_return_memory_decay": 0.0,
            },
            {
                "variant": "random",
                "mechanism_role": "random_equivalent_0p5x",
                "return_frame_count": 4,
                "all_available_memory": 0.25,
                "first_n_return_index_memory": 0.25,
                "neutral_predicted_window_memory": 0.25,
                "late_return_memory_decay": 0.0,
            },
            {
                "variant": "cubic",
                "mechanism_role": "cubic_split_0p5x",
                "matched_random_variant": "random",
                "return_frame_count": 4,
                "clean_gates_passed": True,
                "neutral_window_pair_coverage": 1.0,
                "all_available_memory": 0.8,
                "neutral_predicted_window_memory": 0.72,
                "all_available_memory_delta_vs_neutral": 0.6,
                "all_available_memory_delta_vs_matched_random": 0.55,
                "neutral_predicted_window_memory_delta_vs_neutral": 0.52,
                "neutral_predicted_window_memory_delta_vs_matched_random": 0.47,
                "late_return_memory_decay_delta_vs_neutral": 0.05,
                "late_return_memory_decay_delta_vs_matched_random": 0.05,
            },
        ]

        result = classify_cubic_memory_survivor_bias(rows)

        self.assertEqual(result["label"], "cubic_memory_real_same_window_gain")

    def test_missing_artifact_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = load_cubic_memory_tradeoff_artifact(Path(tmpdir))

        self.assertFalse(artifact["valid"])
        self.assertIn("cubic_memory_tradeoff_summary.csv", artifact["missing"])
        self.assertEqual(classify_cubic_memory_survivor_bias([])["label"], "insufficient_artifacts")


if __name__ == "__main__":
    unittest.main()
