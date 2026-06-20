"""Tests for the read-only 3D release-phase return-map predictor."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from simulation.prototype_3d_release_phase_return_map import (
    ReleasePhaseReturnMapOptions,
    blind_confirmation_recommendations,
    classify_release_phase_return_map,
    phase_binned_summary,
    run_3d_release_phase_return_map,
)


class Prototype3DReleasePhaseReturnMapTests(unittest.TestCase):
    def test_phase_binned_summary_counts_reference_scope(self) -> None:
        rows = [
            _feature("run::pass_a", phase=0.491, cutoff=17.925, conservative_pass=True),
            _feature("run::pass_b", phase=0.504, cutoff=17.94, conservative_pass=True),
            _feature("run::fail", phase=0.449, cutoff=17.88, conservative_pass=False),
            _feature("run::coupled", phase=0.504, cutoff=17.94, conservative_pass=False, reference=False),
        ]

        binned = phase_binned_summary(rows, ReleasePhaseReturnMapOptions(phase_bin_width=0.025))

        reference_bins = {round(row["phase_bin_start"], 3): row for row in binned if row["scope"] == "reference_compatible"}
        all_bins = {round(row["phase_bin_start"], 3): row for row in binned if row["scope"] == "all_rows"}
        self.assertEqual(reference_bins[0.5]["row_count"], 1)
        self.assertEqual(reference_bins[0.5]["conservative_pass_count"], 1)
        self.assertEqual(all_bins[0.5]["row_count"], 2)
        self.assertEqual(all_bins[0.5]["conservative_pass_count"], 1)

    def test_classification_supports_neighboring_phase_rule(self) -> None:
        rows = [
            _feature("run::fail_a", phase=0.4128, cutoff=17.84, conservative_pass=False, strict=(8, 7)),
            _feature("run::fail_b", phase=0.4496, cutoff=17.88, conservative_pass=False, strict=(8, 7)),
            _feature("run::fail_c", phase=0.6628, cutoff=17.84, conservative_pass=False, strict=(5, 4)),
            _feature("run::pass_a", phase=0.4910, cutoff=17.925, conservative_pass=True),
            _feature("run::pass_b", phase=0.4956, cutoff=17.93, conservative_pass=True, default=(11, 10)),
            _feature("run::pass_c", phase=0.5002, cutoff=17.935, conservative_pass=True, default=(11, 10)),
            _feature("run::pass_d", phase=0.5048, cutoff=17.94, conservative_pass=True, default=(11, 10)),
            _feature("run::pass_e", phase=0.5140, cutoff=17.95, conservative_pass=True),
        ]
        binned = phase_binned_summary(rows)
        predictions = [
            {
                "prediction_kind": "existing_row",
                "scope": "reference_compatible",
                "nearest_neighbor_pass_correct": True,
            }
            for _ in rows
        ]
        model = {"top_separators": [{"abs_effect": 0.75}], "linear_model_available": True, "logistic_model_available": True}

        classification = classify_release_phase_return_map(rows, predictions, binned, model)

        self.assertEqual(classification["label"], "release_phase_predictive_rule_supported")
        self.assertAlmostEqual(classification["checks"]["best_cluster_center_phase"], 0.5002, places=3)

    def test_blind_recommendations_return_requested_roles(self) -> None:
        rows = [
            _feature("run::fail_low", phase=0.4864, cutoff=17.92, conservative_pass=False, strict=(8, 7)),
            _feature("run::pass_a", phase=0.4910, cutoff=17.925, conservative_pass=True),
            _feature("run::pass_b", phase=0.4956, cutoff=17.93, conservative_pass=True, default=(11, 10)),
            _feature("run::pass_c", phase=0.5002, cutoff=17.935, conservative_pass=True, default=(11, 10)),
            _feature("run::pass_d", phase=0.5048, cutoff=17.94, conservative_pass=True, default=(11, 10)),
            _feature("run::pass_e", phase=0.5140, cutoff=17.95, conservative_pass=True),
        ]

        recommendations = blind_confirmation_recommendations(rows)

        roles = [row["recommendation_role"] for row in recommendations]
        self.assertEqual(len(recommendations), 5)
        self.assertEqual(roles.count("predicted_strong"), 2)
        self.assertEqual(roles.count("predicted_boundary_edge"), 2)
        self.assertEqual(roles.count("predicted_weak_negative_control"), 1)
        self.assertEqual(len({row["cutoff_time"] for row in recommendations}), 5)

    def test_read_only_run_restores_csv_boolean_controls_for_computed_robust_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = tmp_path / "cutoff_phase_map_3d_fake"
            run_root.mkdir()
            _write_csv(
                run_root / "cutoff_phase_map_summary.csv",
                [
                    {
                        "variant": "sign_flip_cutoff_minus_0p07",
                        "family": "sign_flip",
                        "drive_frequency": "0.92",
                        "drive_cutoff_time": "17.93",
                        "cutoff_phase_cycles": "0.4956",
                        "major_shell_peak_count": "11",
                        "refocus_peak_count": "10",
                        "tail_shell_retention": "0.316",
                        "tail_outer_to_shell_mean": "0.638",
                        "post_cutoff_shell_decay_rate": "-0.024",
                        "shell_exit_detected": "false",
                        "global_peak_in_outer_window": "false",
                    }
                ],
            )
            _write_csv(
                run_root / "cutoff_phase_map_timeseries.csv",
                [
                    {"variant": "sign_flip_cutoff_minus_0p07", "time": "17.96", "shell_window_energy": "1.0"},
                    {"variant": "sign_flip_cutoff_minus_0p07", "time": "35.0", "shell_window_energy": "2.0"},
                    {"variant": "sign_flip_cutoff_minus_0p07", "time": "50.4", "shell_window_energy": "1.0"},
                    {"variant": "sign_flip_cutoff_minus_0p07", "time": "70.4", "shell_window_energy": "0.8"},
                ],
            )

            result = run_3d_release_phase_return_map(
                [run_root],
                options=ReleasePhaseReturnMapOptions(output_root=str(tmp_path / "runs")),
            )

        row = result["feature_rows"][0]
        self.assertTrue(row["no_exit"])
        self.assertTrue(row["global_outer_false"])


def _feature(
    row_id: str,
    *,
    phase: float,
    cutoff: float,
    conservative_pass: bool,
    reference: bool = True,
    strict: tuple[int, int] = (9, 8),
    default: tuple[int, int] = (10, 9),
) -> dict:
    return {
        "row_id": row_id,
        "run_id": "run",
        "variant": row_id.split("::", maxsplit=1)[-1],
        "reference_compatible": reference,
        "cutoff_time": cutoff,
        "release_phase_cycles": phase,
        "phase_distance_to_0p50": min(abs(phase - 0.5), 1.0 - abs(phase - 0.5)),
        "frequency": 0.92,
        "first_arrival_time": 9.6,
        "first_post_cutoff_peak_time": 35.84,
        "peak_interval_1": 8.0,
        "peak_interval_2": 8.0,
        "peak_interval_3": 8.0,
        "early_flux_balance": 0.64,
        "early_inward_flux_fraction": 0.82,
        "early_outer_shell_ratio": 0.64,
        "post_cutoff_shell_energy_area": 0.0028,
        "tail_energy_area_after_t50": 0.0012,
        "shell_energy_autocorrelation": 0.99,
        "dominant_spectral_concentration": 0.74,
        "return_timing_regularity": 0.84,
        "default_major_peaks": default[0],
        "default_refocus_peaks": default[1],
        "strict_major_peaks": strict[0],
        "strict_refocus_peaks": strict[1],
        "retention": 0.316 if conservative_pass else 0.24,
        "outer_shell": 0.64,
        "decay": -0.024,
        "no_exit": True,
        "global_outer_false": True,
        "conservative_pass": conservative_pass,
        "default_11_10_or_better": default[0] >= 11 and default[1] >= 10,
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
