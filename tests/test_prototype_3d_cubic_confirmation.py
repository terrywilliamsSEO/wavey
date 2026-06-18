"""Tests for 3D cubic dt/sponge confirmation controls."""

from __future__ import annotations

import unittest

from simulation.config import SimulationConfig
from simulation.prototype_3d import Prototype3DOptions
from simulation.prototype_3d_cubic_confirmation import (
    CubicConfirmationControlOptions,
    _variant_plan,
    classify_cubic_confirmation_control,
)
from simulation.prototype_3d_source_geometry import ALL_FACES


class Prototype3DCubicConfirmationTests(unittest.TestCase):
    def test_variant_plan_confirms_original_and_sign_flip(self) -> None:
        options = CubicConfirmationControlOptions()
        variants = _variant_plan(SimulationConfig(), Prototype3DOptions(grid_size=15), options)
        by_name = {variant.name: variant for variant in variants}

        self.assertEqual(by_name["six_face_cubic_reference"].boundary_cubic_phase_sign, 1.0)
        self.assertEqual(by_name["cubic_phase_sign_flip_reference"].boundary_cubic_phase_sign, -1.0)
        self.assertEqual(by_name["six_face_cubic_reference"].boundary_faces, ALL_FACES)
        self.assertEqual(by_name["cubic_phase_sign_flip_reference"].boundary_faces, ALL_FACES)
        self.assertEqual(by_name["six_face_cubic_half_dt"].dt, by_name["six_face_cubic_reference"].dt * 0.5)
        self.assertEqual(by_name["six_face_cubic_half_dt"].steps, by_name["six_face_cubic_reference"].steps * 2)
        self.assertGreater(by_name["cubic_phase_sign_flip_stronger_sponge"].sponge_strength, by_name["cubic_phase_sign_flip_reference"].sponge_strength)
        self.assertLess(by_name["cubic_phase_sign_flip_weak_sponge"].sponge_strength, by_name["cubic_phase_sign_flip_reference"].sponge_strength)
        self.assertLess(by_name["cubic_phase_sign_flip_amplitude_reduced"].drive_amplitude, by_name["cubic_phase_sign_flip_reference"].drive_amplitude)
        self.assertIn("direct_core_control", by_name)
        self.assertIn("direct_shell_control", by_name)

    def test_classification_detects_confirmed_family(self) -> None:
        rows = _confirmed_rows(amplitude_clean=True)

        result = classify_cubic_confirmation_control(rows, CubicConfirmationControlOptions())

        self.assertEqual(result["label"], "cubic_phase_dt_sponge_confirmed")

    def test_classification_detects_drive_strength_sensitivity(self) -> None:
        rows = _confirmed_rows(amplitude_clean=False)

        result = classify_cubic_confirmation_control(rows, CubicConfirmationControlOptions())

        self.assertEqual(result["label"], "cubic_phase_dt_sponge_confirmed_drive_strength_sensitive")

    def test_classification_detects_dt_sensitivity(self) -> None:
        rows = _confirmed_rows(amplitude_clean=True)
        for row in rows:
            if row["variant"] == "cubic_phase_sign_flip_half_dt":
                row["near_shell_tail_retention"] = 0.10

        result = classify_cubic_confirmation_control(rows, CubicConfirmationControlOptions())

        self.assertEqual(result["label"], "dt_sensitive")

    def test_classification_rejects_direct_competition(self) -> None:
        rows = _confirmed_rows(amplitude_clean=True)
        for row in rows:
            if row["variant"] == "direct_shell_control":
                row["near_shell_tail_retention"] = 0.30

        result = classify_cubic_confirmation_control(rows, CubicConfirmationControlOptions())

        self.assertEqual(result["label"], "direct_local_forcing_competitive")


def _confirmed_rows(*, amplitude_clean: bool) -> list[dict]:
    rows = []
    for family, outer in (("six_face_cubic", 2.8), ("cubic_phase_sign_flip", 1.1)):
        rows.extend(
            [
                _row(f"{family}_reference", family=family, role="reference", outer=outer),
                _row(f"{family}_repeat", family=family, role="repeat", outer=outer, near=1.95),
                _row(f"{family}_half_dt", family=family, role="half_dt", outer=outer, near=1.8, dt=0.02),
                _row(f"{family}_stronger_sponge", family=family, role="stronger_sponge", outer=outer * 0.8, near=1.7),
                _row(f"{family}_weak_sponge", family=family, role="weak_sponge", outer=outer * 1.1, near=1.7),
            ]
        )
    rows.append(
        _row(
            "cubic_phase_sign_flip_amplitude_reduced",
            family="cubic_phase_sign_flip",
            role="amplitude_reduced",
            outer=1.2 if amplitude_clean else 9.0,
            near=1.0 if amplitude_clean else 0.05,
            retention=0.55 if amplitude_clean else 0.10,
            global_outer=not amplitude_clean,
        )
    )
    rows.append(_row("direct_core_control", family="direct_control", role="direct_control", retention=0.001))
    rows.append(_row("direct_shell_control", family="direct_control", role="direct_control", retention=0.001))
    return rows


def _row(
    variant: str,
    *,
    family: str,
    role: str,
    outer: float = 1.0,
    near: float = 2.0,
    retention: float = 0.60,
    global_outer: bool = False,
    dt: float = 0.04,
) -> dict:
    return {
        "variant": variant,
        "cubic_confirmation_family": family,
        "cubic_confirmation_role": role,
        "dt": dt,
        "physical_duration": 56.0,
        "drive_location": "boundary" if family != "direct_control" else "core",
        "near_shell_peak_fraction_of_work": near,
        "near_shell_tail_retention": retention,
        "late_tail_near_shell_peak_radius_median": 5.0,
        "late_tail_near_shell_peak_radius_range": 1.0,
        "outer_to_near_tail_energy_ratio": outer,
        "global_peak_in_outer_window": global_outer,
        "first_meaningful_near_shell_arrival_time": 10.0,
        "stability_warnings": "none",
    }


if __name__ == "__main__":
    unittest.main()
