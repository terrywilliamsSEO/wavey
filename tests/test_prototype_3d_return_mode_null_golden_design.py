import tempfile
import unittest
from pathlib import Path

import numpy as np

from simulation.prototype_3d_return_mode_null_golden_design import (
    ReturnModeNullGoldenDesignOptions,
    classify_return_mode_null_golden_design,
    overlap_fraction,
    project_onto_basis,
    retained_strength_fraction,
    run_3d_return_mode_null_golden_design,
)


class ReturnModeNullGoldenDesignTests(unittest.TestCase):
    def test_projection_math_projects_onto_orthonormal_basis(self) -> None:
        vector = np.asarray([1.0, 2.0, 3.0])
        basis = np.asarray([[1.0, 0.0], [0.0, 0.0], [0.0, 1.0]])

        projection, residual = project_onto_basis(vector, basis)

        self.assertTrue(np.allclose(projection, [1.0, 0.0, 3.0]))
        self.assertTrue(np.allclose(residual, [0.0, 2.0, 0.0]))
        self.assertAlmostEqual(float(np.dot(projection, residual)), 0.0)

    def test_overlap_reduction_after_null_projection(self) -> None:
        basis_vector = np.asarray([1.0, 1.0, 0.0])
        basis_vector = basis_vector / np.linalg.norm(basis_vector)
        basis = basis_vector.reshape((-1, 1))
        raw = np.asarray([1.0, 1.0, 1.0])

        raw_overlap = overlap_fraction(raw, basis)
        _, null = project_onto_basis(raw, basis)
        null_overlap = overlap_fraction(null, basis)

        self.assertGreater(raw_overlap, 0.8)
        self.assertAlmostEqual(null_overlap, 0.0, places=12)

    def test_retained_strength_fraction(self) -> None:
        raw = np.asarray([3.0, 4.0])
        residual = np.asarray([0.0, 4.0])

        self.assertAlmostEqual(retained_strength_fraction(raw, residual), 0.8)
        self.assertEqual(retained_strength_fraction(np.zeros(2), residual), 0.0)

    def test_classification_supported_for_nontrivial_null_candidate(self) -> None:
        result = classify_return_mode_null_golden_design(
            self._summary(
                raw_overlap=0.42,
                null_overlap=0.02,
                reduction=0.95,
                retained=0.72,
                sector_retained=0.61,
                renorm=1.39,
                nontrivial=True,
            ),
            ReturnModeNullGoldenDesignOptions(),
        )

        self.assertEqual(result["label"], "return_mode_null_golden_candidate_supported")

    def test_classification_not_viable_when_overlap_or_retained_strength_fails(self) -> None:
        low_overlap = classify_return_mode_null_golden_design(
            self._summary(raw_overlap=0.04, null_overlap=0.0, reduction=1.0, retained=0.75, sector_retained=0.75, renorm=1.33),
            ReturnModeNullGoldenDesignOptions(),
        )
        weak_residual = classify_return_mode_null_golden_design(
            self._summary(raw_overlap=0.4, null_overlap=0.0, reduction=1.0, retained=0.2, sector_retained=0.2, renorm=5.0),
            ReturnModeNullGoldenDesignOptions(),
        )

        self.assertEqual(low_overlap["label"], "null_golden_not_viable")
        self.assertEqual(weak_residual["label"], "null_golden_not_viable")

    def test_classification_inconclusive_for_manual_nontriviality_failure(self) -> None:
        result = classify_return_mode_null_golden_design(
            self._summary(
                raw_overlap=0.4,
                null_overlap=0.0,
                reduction=1.0,
                retained=0.6,
                sector_retained=0.6,
                renorm=1.67,
                nontrivial=False,
            ),
            ReturnModeNullGoldenDesignOptions(),
        )

        self.assertEqual(result["label"], "null_golden_design_inconclusive")

    def test_missing_artifact_handling_writes_empty_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_3d_return_mode_null_golden_design(
                options=ReturnModeNullGoldenDesignOptions(
                    output_root=str(root),
                    isochronous_root=str(root / "missing_iso"),
                    cleanup_root=str(root / "missing_cleanup"),
                    sacred_root=str(root / "missing_sacred"),
                    hybrid_root=str(root / "missing_hybrid"),
                )
            )

            self.assertEqual(result["classification"]["label"], "insufficient_artifacts")
            self.assertTrue(Path(result["summary_csv"]).exists())
            self.assertTrue(Path(result["golden_projection_components_csv"]).exists())
            self.assertTrue(Path(result["return_mode_basis_summary_csv"]).exists())

    def _summary(
        self,
        *,
        raw_overlap: float,
        null_overlap: float,
        reduction: float,
        retained: float,
        sector_retained: float,
        renorm: float,
        nontrivial: bool = True,
    ) -> dict[str, object]:
        return {
            "missing_artifacts": [],
            "artifacts_sufficient_for_candidate": True,
            "raw_golden_desired_basis_overlap": raw_overlap,
            "null_golden_desired_basis_overlap": null_overlap,
            "desired_overlap_reduction_fraction": reduction,
            "retained_golden_strength_fraction": retained,
            "sector_retained_strength_fraction": sector_retained,
            "renormalization_multiplier": renorm,
            "null_profile_nontrivial": nontrivial,
        }


if __name__ == "__main__":
    unittest.main()
