import tempfile
import unittest
from pathlib import Path

from simulation.prototype_3d_branch_closure_report import (
    BranchClosureReportOptions,
    _build_forbidden_rows,
    _build_reopen_rows,
    classify_branch_closure,
    run_3d_branch_closure_report,
)


class BranchClosureReportTests(unittest.TestCase):
    def test_classifies_closed_when_required_artifacts_match(self) -> None:
        result = classify_branch_closure(self._required_rows())

        self.assertEqual(result["label"], "passive_scale_lift_branch_closed")
        self.assertEqual(result["checks"]["mechanism_candidate"], "none")

    def test_classifies_missing_required_artifact(self) -> None:
        rows = [row for row in self._required_rows() if row["stage"] != "return-pattern symmetry audit"]

        result = classify_branch_closure(rows)

        self.assertEqual(result["label"], "insufficient_artifacts")
        self.assertIn("return-pattern symmetry audit", result["checks"]["missing_required_stages"])

    def test_classifies_mismatched_required_artifact(self) -> None:
        rows = self._required_rows()
        rows[-1]["classification"] = "orientation_drift_supported"

        result = classify_branch_closure(rows)

        self.assertEqual(result["label"], "branch_closure_incomplete")
        self.assertIn("return-pattern symmetry audit", result["checks"]["mismatched_required_stages"][0])

    def test_forbidden_paths_and_reopen_criteria_capture_guardrails(self) -> None:
        rows = self._required_rows()
        forbidden = _build_forbidden_rows(rows)
        reopen = _build_reopen_rows()

        forbidden_paths = {row["path"] for row in forbidden}
        self.assertIn("nearby cutoff / phase tuning", forbidden_paths)
        self.assertIn("smooth envelopes / source shaping", forbidden_paths)
        self.assertIn("61^3 or larger-grid escalation", forbidden_paths)
        self.assertEqual(reopen[0]["criterion"], "new_stable_spatial_memory_mechanism")
        self.assertEqual(reopen[0]["current_status"], "not_satisfied")

    def test_run_writes_insufficient_artifact_packet_without_physics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            options = BranchClosureReportOptions(
                output_root=str(temp_path / "runs"),
                proof_root=str(temp_path / "missing_proof"),
                lift_root=str(temp_path / "missing_lift"),
                postmortem_root=str(temp_path / "missing_postmortem"),
                modal_root=str(temp_path / "missing_modal"),
                dispersion_root=str(temp_path / "missing_dispersion"),
                spatial_phase_root=str(temp_path / "missing_spatial"),
                precomp_root=str(temp_path / "missing_precomp"),
                source_spectrum_root=str(temp_path / "missing_source_spectrum"),
                smooth_root=str(temp_path / "missing_smooth"),
                phase_conjugate_root=str(temp_path / "missing_phase_conjugate"),
                modal_sparsity_root=str(temp_path / "missing_modal_sparsity"),
                return_family_gate_root=str(temp_path / "missing_return_family"),
                off_comb_root=str(temp_path / "missing_off_comb"),
                return_pattern_root=str(temp_path / "missing_return_pattern"),
                resonator_root=str(temp_path / "missing_resonator"),
                central_burst_root=str(temp_path / "missing_central"),
                second_pulse_roots=(),
            )

            result = run_3d_branch_closure_report(options=options)

            self.assertEqual(result["classification"]["label"], "insufficient_artifacts")
            self.assertTrue(Path(result["report_path"]).exists())
            self.assertTrue(Path(result["summary_csv"]).exists())
            self.assertTrue(Path(result["forbidden_csv"]).exists())

    def _required_rows(self) -> list[dict[str, object]]:
        classifications = {
            "41^3 proof pack": "release_phase_quarter_dt_proof_supported",
            "51^3 resolution lift": "release_phase_resolution_lift_failed",
            "smooth-envelope source shaping": "smooth_envelope_no_rescue",
            "boundary phase-conjugate patch mask": "boundary_phase_conjugate_no_rescue",
            "modal sparsity audit": "common_51_source_signature_supported",
            "return-family gate audit": "return_family_weakened_not_gate_artifact",
            "off-comb leakage audit": "spatial_pattern_scrambling_supported",
            "return-pattern symmetry audit": "pattern_symmetry_inconclusive",
        }
        return [
            {
                "stage": stage,
                "artifact_root": f"runs/{stage.replace(' ', '_')}",
                "classification": classification,
            }
            for stage, classification in classifications.items()
        ]


if __name__ == "__main__":
    unittest.main()
