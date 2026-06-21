"""Read-only closure report for the passive 3D scale-lift branch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import json
import math

import numpy as np

from .prototype_3d_refocusing_engineering import _format
from .prototype_3d_source_sponge import _write_csv


DEFAULT_PROOF_ROOT = "runs/release_phase_proof_pack_3d_20260619_234039"
DEFAULT_LIFT_ROOT = "runs/release_phase_resolution_lift_3d_20260620_091834"
DEFAULT_POSTMORTEM_ROOT = "runs/release_phase_resolution_postmortem_3d_20260620_100043"
DEFAULT_MODAL_ROOT = "runs/release_phase_modal_audit_3d_20260620_110344"
DEFAULT_DISPERSION_ROOT = "runs/release_phase_dispersion_audit_3d_20260620_150931"
DEFAULT_SPATIAL_PHASE_ROOT = "runs/spatial_phase_instrumentation_3d_20260620_170518"
DEFAULT_PRECOMP_ROOT = "runs/spatial_phase_precomp_design_3d_20260620_175852"
DEFAULT_SOURCE_SPECTRUM_ROOT = "runs/source_spectrum_design_audit_3d_20260620_181010"
DEFAULT_SMOOTH_ROOT = "runs/smooth_envelope_resolution_lift_3d_20260620_192501"
DEFAULT_PHASE_CONJUGATE_ROOT = "runs/boundary_phase_conjugate_3d_20260620_212918"
DEFAULT_MODAL_SPARSITY_ROOT = "runs/modal_sparsity_audit_3d_20260620_231602"
DEFAULT_RETURN_FAMILY_GATE_ROOT = "runs/return_family_gate_audit_3d_20260621_082543"
DEFAULT_OFF_COMB_ROOT = "runs/off_comb_leakage_audit_3d_20260621_085347"
DEFAULT_RETURN_PATTERN_ROOT = "runs/return_pattern_symmetry_audit_3d_20260621_091511"
DEFAULT_RESONATOR_ROOT = "runs/resonator_layer_3d_20260619_175949"
DEFAULT_CENTRAL_BURST_ROOT = "runs/central_burst_3d_20260620_103248"
DEFAULT_SECOND_PULSE_ROOTS = (
    "runs/second_pulse_3d_20260619_112731",
    "runs/second_pulse_3d_20260619_115332",
    "runs/second_pulse_3d_20260619_125050",
    "runs/second_pulse_3d_20260619_135358",
)


@dataclass(frozen=True)
class BranchClosureReportOptions:
    """Options for the passive branch closure synthesis."""

    output_root: str = "runs"
    proof_root: str = DEFAULT_PROOF_ROOT
    lift_root: str = DEFAULT_LIFT_ROOT
    postmortem_root: str = DEFAULT_POSTMORTEM_ROOT
    modal_root: str = DEFAULT_MODAL_ROOT
    dispersion_root: str = DEFAULT_DISPERSION_ROOT
    spatial_phase_root: str = DEFAULT_SPATIAL_PHASE_ROOT
    precomp_root: str = DEFAULT_PRECOMP_ROOT
    source_spectrum_root: str = DEFAULT_SOURCE_SPECTRUM_ROOT
    smooth_root: str = DEFAULT_SMOOTH_ROOT
    phase_conjugate_root: str = DEFAULT_PHASE_CONJUGATE_ROOT
    modal_sparsity_root: str = DEFAULT_MODAL_SPARSITY_ROOT
    return_family_gate_root: str = DEFAULT_RETURN_FAMILY_GATE_ROOT
    off_comb_root: str = DEFAULT_OFF_COMB_ROOT
    return_pattern_root: str = DEFAULT_RETURN_PATTERN_ROOT
    resonator_root: str = DEFAULT_RESONATOR_ROOT
    central_burst_root: str = DEFAULT_CENTRAL_BURST_ROOT
    second_pulse_roots: tuple[str, ...] = DEFAULT_SECOND_PULSE_ROOTS


def run_3d_branch_closure_report(
    *,
    options: BranchClosureReportOptions | None = None,
) -> dict[str, Any]:
    """Compile the passive 3D scale-lift branch closure packet from saved artifacts only."""

    options = options or BranchClosureReportOptions()
    control_id = datetime.now().strftime("branch_closure_report_3d_%Y%m%d_%H%M%S")
    root = Path(options.output_root) / control_id
    root.mkdir(parents=True, exist_ok=False)

    evidence_rows = _build_evidence_chain(options)
    claim_rows = _build_claim_rows(evidence_rows)
    forbidden_rows = _build_forbidden_rows(evidence_rows)
    reopen_rows = _build_reopen_rows()
    classification = classify_branch_closure(evidence_rows)
    summary_rows = [_summary_row(classification, evidence_rows, claim_rows)]
    for collection in (summary_rows, evidence_rows, claim_rows, forbidden_rows, reopen_rows):
        for row in collection:
            row["branch_closure_classification"] = classification["label"]

    summary_csv = root / "branch_closure_summary.csv"
    evidence_csv = root / "branch_closure_evidence_chain.csv"
    claims_csv = root / "branch_closure_claims.csv"
    forbidden_csv = root / "branch_closure_forbidden_paths.csv"
    reopen_csv = root / "branch_closure_reopen_criteria.csv"
    report_path = root / "branch_closure_report.md"
    summary_json = root / "branch_closure_summary.json"

    _write_csv(summary_csv, summary_rows, _summary_fields())
    _write_csv(evidence_csv, evidence_rows, _evidence_fields())
    _write_csv(claims_csv, claim_rows, _claim_fields())
    _write_csv(forbidden_csv, forbidden_rows, _forbidden_fields())
    _write_csv(reopen_csv, reopen_rows, _reopen_fields())
    _write_report(report_path, control_id, classification, summary_rows[0], evidence_rows, claim_rows, forbidden_rows, reopen_rows)
    summary_json.write_text(
        json.dumps(
            {
                "control_id": control_id,
                "classification": classification,
                "summary_csv": str(summary_csv),
                "evidence_csv": str(evidence_csv),
                "claims_csv": str(claims_csv),
                "forbidden_csv": str(forbidden_csv),
                "reopen_csv": str(reopen_csv),
                "report_path": str(report_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "control_id": control_id,
        "classification": classification,
        "summary_rows": summary_rows,
        "evidence_rows": evidence_rows,
        "claim_rows": claim_rows,
        "forbidden_rows": forbidden_rows,
        "reopen_rows": reopen_rows,
        "summary_csv": str(summary_csv),
        "evidence_csv": str(evidence_csv),
        "claims_csv": str(claims_csv),
        "forbidden_csv": str(forbidden_csv),
        "reopen_csv": str(reopen_csv),
        "report_path": str(report_path),
        "summary_json": str(summary_json),
        "path": str(root),
    }


def classify_branch_closure(evidence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify whether the evidence chain is complete enough to close the branch."""

    by_stage = {str(row.get("stage")): str(row.get("classification")) for row in evidence_rows}
    required = {
        "41^3 proof pack": "release_phase_quarter_dt_proof_supported",
        "51^3 resolution lift": "release_phase_resolution_lift_failed",
        "smooth-envelope source shaping": "smooth_envelope_no_rescue",
        "boundary phase-conjugate patch mask": "boundary_phase_conjugate_no_rescue",
        "modal sparsity audit": "common_51_source_signature_supported",
        "return-family gate audit": "return_family_weakened_not_gate_artifact",
        "off-comb leakage audit": "spatial_pattern_scrambling_supported",
        "return-pattern symmetry audit": "pattern_symmetry_inconclusive",
    }
    missing = [stage for stage in required if not by_stage.get(stage)]
    mismatched = [
        f"{stage}: expected {expected}, got {by_stage.get(stage)}"
        for stage, expected in required.items()
        if by_stage.get(stage) and by_stage.get(stage) != expected
    ]
    checks = {
        "required_stage_count": len(required),
        "missing_required_stages": missing,
        "mismatched_required_stages": mismatched,
        "mechanism_candidate": "none",
        "branch_status": "scientifically_useful_not_breakthrough_ready",
    }
    if missing:
        return {
            "label": "insufficient_artifacts",
            "reason": "The closure packet is missing one or more required read-only branch artifacts.",
            "checks": checks,
        }
    if mismatched:
        return {
            "label": "branch_closure_incomplete",
            "reason": "The evidence chain exists, but one or more required stages no longer match the closure interpretation.",
            "checks": checks,
        }
    return {
        "label": "passive_scale_lift_branch_closed",
        "reason": "The 41^3 structured refocusing proof is strong, the 51^3 scale lift failed under source/control/rescue audits, and no stable recoverable mechanism is supported by the saved artifacts.",
        "checks": checks,
    }


def _build_evidence_chain(options: BranchClosureReportOptions) -> list[dict[str, Any]]:
    rows = [
        _proof_pack_row(Path(options.proof_root)),
        _resolution_lift_row(Path(options.lift_root)),
        _json_or_csv_stage(
            "51^3 postmortem",
            Path(options.postmortem_root),
            report_name="release_phase_resolution_postmortem_report.md",
            summary_name="release_phase_resolution_postmortem_summary.csv",
            classification_field="release_phase_resolution_postmortem_classification",
            closure_role="No single recalibrated retry",
            key_findings="Below-gate return humps remain, but lifted candidate and controls share shrinkage; no single cutoff or shell-window retry is predicted.",
            status="complete_negative",
        ),
        _json_or_csv_stage(
            "modal audit",
            Path(options.modal_root),
            report_name="release_phase_modal_audit_report.md",
            summary_name="modal_audit_summary.csv",
            classification_field="release_phase_modal_audit_classification",
            closure_role="Blur mechanism, no source correction",
            key_findings="Proof and lift rows share the dominant shell band near 0.012807 while 51^3 strict counts shrink and loose returns remain.",
            status="complete_negative",
        ),
        _json_or_csv_stage(
            "dispersion audit",
            Path(options.dispersion_root),
            report_name="release_phase_dispersion_audit_report.md",
            summary_name="dispersion_blur_model_summary.csv",
            classification_field="release_phase_dispersion_audit_classification",
            closure_role="Predictable blur, no safe candidate",
            key_findings="A scalable blur model is supported, but source discretization and shell-window sampling do not isolate a safe retry.",
            status="complete_negative",
        ),
        _json_or_csv_stage(
            "spatial phase instrumentation",
            Path(options.spatial_phase_root),
            report_name="spatial_phase_instrumentation_report.md",
            summary_name="spatial_phase_instrumentation_summary.csv",
            classification_field="spatial_phase_instrumentation_classification",
            closure_role="Spatial decoherence evidence",
            key_findings="The 51^3 failed-lift candidate loses shell/radial/angular coherence while return spread and radial center shift do not explain the strict-count loss.",
            status="complete_negative",
        ),
        _json_or_csv_stage(
            "spatial phase precompensation design",
            Path(options.precomp_root),
            report_name="phase_precompensation_design_report.md",
            summary_name="phase_error_modes.csv",
            classification_field="phase_precompensation_design_classification",
            closure_role="No safe low-dimensional correction",
            key_findings="Allowed global/per-face/cubic/harmonic/release-nudge bases had low explanatory power and unstable per-return drift.",
            status="complete_negative",
            fallback_classification="no_safe_phase_correction",
        ),
        _json_or_csv_stage(
            "source-spectrum design gate",
            Path(options.source_spectrum_root),
            report_name="source_spectrum_design_audit_report.md",
            summary_name="source_spectrum_summary.csv",
            classification_field="source_spectrum_design_audit_classification",
            closure_role="Only authorized one smooth-envelope test",
            key_findings="The hard-cutoff source had sidebands and a same-release smooth envelope theoretically narrowed them; the authorized physics test later failed.",
            status="complete_gate",
            fallback_classification="source_spectrum_narrowing_candidate_supported",
        ),
        _smooth_row(Path(options.smooth_root)),
        _phase_conjugate_row(Path(options.phase_conjugate_root)),
        _modal_sparsity_row(Path(options.modal_sparsity_root)),
        _return_family_gate_row(Path(options.return_family_gate_root)),
        _off_comb_row(Path(options.off_comb_root)),
        _return_pattern_row(Path(options.return_pattern_root)),
        _json_or_csv_stage(
            "passive resonator layer",
            Path(options.resonator_root),
            report_name="resonator_layer_report.md",
            summary_name="resonator_layer_summary.csv",
            classification_field="resonator_layer_classification",
            closure_role="Passive resonator route closed",
            key_findings="No-resonator and zero-coupling rows preserved the strict cluster; coupled resonator variants degraded strict counts.",
            status="complete_negative",
            fallback_classification="no_resonator_still_wins",
        ),
        _json_or_csv_stage(
            "central burst contrast branch",
            Path(options.central_burst_root),
            report_name="central_burst_report.md",
            summary_name="central_burst_summary.csv",
            classification_field="central_burst_classification",
            closure_role="Separate branch not an improvement",
            key_findings="The no-boundary central burst ladder produced transient or contaminated rows, not clean repeated shell returns.",
            status="separate_negative",
            fallback_classification="central_burst_transient",
        ),
    ]
    rows.extend(_second_pulse_rows(options.second_pulse_roots))
    return rows


def _proof_pack_row(root: Path) -> dict[str, Any]:
    rows = _read_csv(root / "release_phase_proof_pack_summary.csv")
    proof = [row for row in rows if row.get("prediction_role") == "proof_candidate"]
    strict_rows = [row for row in proof if int(_first(row, "conservative_major_peaks")) >= 9 and int(_first(row, "conservative_refocus_peaks")) >= 8]
    phases = [_first(row, "cutoff_phase_cycles") for row in strict_rows]
    cutoffs = [_first(row, "drive_cutoff_time") for row in strict_rows]
    key = (
        f"{len(strict_rows)} proof-candidate rows preserved strict 9/8; "
        f"cutoffs {_range_text(cutoffs)}, phases {_range_text(phases)}; gates no-exit/global-outer/outer-shell/work passed."
        if strict_rows
        else "Required strict 9/8 proof-candidate rows were not found."
    )
    return _stage_row(
        stage="41^3 proof pack",
        artifact_root=root,
        report_name="release_phase_proof_pack_report.md",
        classification=_classification_from_rows(rows, "release_phase_proof_pack_classification"),
        status="supports_claim",
        closure_role="Freeze claim",
        key_findings=key,
        reopen_implication="Keep as 41^3 proof only; do not treat as scale validation.",
    )


def _resolution_lift_row(root: Path) -> dict[str, Any]:
    rows = _read_csv(root / "release_phase_resolution_lift_summary.csv")
    candidate = next((row for row in rows if row.get("prediction_role") == "candidate"), rows[0] if rows else {})
    key = (
        f"Candidate reached default {int(_first(candidate, 'default_major_peaks_at_0p30'))}/{int(_first(candidate, 'default_refocus_peaks_at_0p30'))} "
        f"but conservative strict {int(_first(candidate, 'conservative_major_peaks'))}/{int(_first(candidate, 'conservative_refocus_peaks'))}; "
        f"no-exit={candidate.get('no_exit')}, global_outer_false={candidate.get('global_outer_false')}, outer/shell {_format(candidate.get('outer_shell'))}."
        if candidate
        else "Required 51^3 candidate summary was not found."
    )
    return _stage_row(
        stage="51^3 resolution lift",
        artifact_root=root,
        report_name="release_phase_resolution_lift_report.md",
        classification=_classification_from_rows(rows, "release_phase_resolution_lift_classification"),
        status="supports_non_claim",
        closure_role="Freeze non-claim",
        key_findings=key,
        reopen_implication="Do not call the 41^3 proof scale-validated.",
    )


def _smooth_row(root: Path) -> dict[str, Any]:
    rows = _read_csv(root / "smooth_envelope_resolution_lift_summary.csv")
    candidate = next((row for row in rows if row.get("prediction_role") == "smooth_candidate"), {})
    hard = next((row for row in rows if row.get("prediction_role") == "hard_cutoff_control"), {})
    key = (
        f"Smooth candidate reduced source bandwidth ratio to {_format(candidate.get('source_bandwidth_ratio_to_hard'))} "
        f"but stayed conservative strict {int(_first(candidate, 'conservative_major_peaks'))}/{int(_first(candidate, 'conservative_refocus_peaks'))}; "
        f"hard control strict {int(_first(hard, 'conservative_major_peaks'))}/{int(_first(hard, 'conservative_refocus_peaks'))}."
        if candidate
        else "Required smooth-envelope candidate summary was not found."
    )
    return _stage_row(
        stage="smooth-envelope source shaping",
        artifact_root=root,
        report_name="smooth_envelope_resolution_lift_report.md",
        classification=_classification_from_rows(rows, "smooth_envelope_resolution_lift_classification"),
        status="closed_negative",
        closure_role="Close source-shape route",
        key_findings=key,
        reopen_implication="Do not broaden smooth envelopes/source shapes from this result.",
    )


def _phase_conjugate_row(root: Path) -> dict[str, Any]:
    rows = _read_csv(root / "boundary_phase_conjugate_summary.csv")
    candidate = next((row for row in rows if row.get("prediction_role") == "phase_conjugate_candidate"), {})
    shuffled = next((row for row in rows if row.get("prediction_role") == "shuffled_patch_phase_control"), {})
    key = (
        f"Frozen 96-patch candidate stayed conservative strict {int(_first(candidate, 'conservative_major_peaks'))}/{int(_first(candidate, 'conservative_refocus_peaks'))}; "
        f"shuffled control also strict {int(_first(shuffled, 'conservative_major_peaks'))}/{int(_first(shuffled, 'conservative_refocus_peaks'))}; no coherent wavefront rescue."
        if candidate
        else "Required phase-conjugate candidate summary was not found."
    )
    return _stage_row(
        stage="boundary phase-conjugate patch mask",
        artifact_root=root,
        report_name="boundary_phase_conjugate_report.md",
        classification=_classification_from_rows(rows, "boundary_phase_conjugate_classification"),
        status="closed_negative",
        closure_role="Close patch-mask route",
        key_findings=key,
        reopen_implication="Do not tune patch masks or increase patch counts.",
    )


def _modal_sparsity_row(root: Path) -> dict[str, Any]:
    rows = _read_csv(root / "modal_sparsity_summary.csv")
    proof = [row for row in rows if int(_first(row, "grid_size")) == 41 and row.get("prediction_role") == "proof_candidate"]
    controls = [row for row in rows if int(_first(row, "grid_size")) == 51]
    key = (
        f"Proof modes-for-99 mean {_format(_mean(row.get('modes_for_99pct') for row in proof))}; "
        f"51^3 mean {_format(_mean(row.get('modes_for_99pct') for row in controls))}; "
        "source-shaped 51^3 rows share one reconstruction/participation signature."
    )
    return _stage_row(
        stage="modal sparsity audit",
        artifact_root=root,
        report_name="modal_sparsity_audit_report.md",
        classification=_classification_from_rows(rows, "modal_sparsity_audit_classification"),
        status="supports_common_failure",
        closure_role="Close modal-sparsity-derived source variants",
        key_findings=key,
        reopen_implication="Do not convert modal sparsity into more source variants.",
    )


def _return_family_gate_row(root: Path) -> dict[str, Any]:
    summary = _read_json(root / "return_family_gate_summary.json")
    checks = summary.get("classification", {}).get("checks", {}) if summary else {}
    key = (
        f"Strict major loss {_format(checks.get('strict_major_loss'))}; source-control off-comb mean {_format(checks.get('source_control_off_comb_energy_ratio_mean'))}; "
        f"rank-normalized strength ratio {_format(checks.get('rank_normalized_strength_ratio'))}; detector-only rescue rejected."
    )
    return _stage_row(
        stage="return-family gate audit",
        artifact_root=root,
        report_name="return_family_gate_report.md",
        classification=str(summary.get("classification", {}).get("label", "")),
        status="supports_failure_explanation",
        closure_role="Freeze detector non-rescue",
        key_findings=key,
        reopen_implication="Do not tune return gates or thresholds to recover the claim.",
    )


def _off_comb_row(root: Path) -> dict[str, Any]:
    summary = _read_json(root / "off_comb_leakage_summary.json")
    checks = summary.get("classification", {}).get("checks", {}) if summary else {}
    key = (
        f"Spatial-pattern leakage proof mean {_format(checks.get('proof_spatial_pattern_leakage_mean'))}; "
        f"51^3 source-control mean {_format(checks.get('source_control_spatial_pattern_leakage_mean'))}; "
        f"delta {_format(checks.get('spatial_pattern_leakage_delta'))}; radial/modal/outer channels not supported."
    )
    return _stage_row(
        stage="off-comb leakage audit",
        artifact_root=root,
        report_name="off_comb_leakage_report.md",
        classification=str(summary.get("classification", {}).get("label", "")),
        status="supports_failure_explanation",
        closure_role="Freeze localization",
        key_findings=key,
        reopen_implication="Do not turn leakage localization into source masks or cutoff tuning.",
    )


def _return_pattern_row(root: Path) -> dict[str, Any]:
    summary = _read_json(root / "return_pattern_symmetry_summary.json")
    checks = summary.get("classification", {}).get("checks", {}) if summary else {}
    key = (
        f"51^3 raw/aligned memory {_format(checks.get('source_control_raw_memory_mean'))}/{_format(checks.get('source_control_aligned_memory_mean'))}; "
        f"transform stability {_format(checks.get('source_control_transform_stability_mean'))}; "
        f"signature share {_format(checks.get('source_transform_signature_share'))}; no stable symmetry rescue."
    )
    return _stage_row(
        stage="return-pattern symmetry audit",
        artifact_root=root,
        report_name="return_pattern_symmetry_report.md",
        classification=str(summary.get("classification", {}).get("label", "")),
        status="supports_closure",
        closure_role="Freeze recoverable-symmetry non-claim",
        key_findings=key,
        reopen_implication="Do not run orientation-drift, cubic-hopping, or phase-precession follow-ups from current artifacts.",
    )


def _json_or_csv_stage(
    stage: str,
    root: Path,
    *,
    report_name: str,
    summary_name: str,
    classification_field: str,
    closure_role: str,
    key_findings: str,
    status: str,
    fallback_classification: str = "",
) -> dict[str, Any]:
    rows = _read_csv(root / summary_name)
    classification = _classification_from_rows(rows, classification_field) or fallback_classification
    return _stage_row(
        stage=stage,
        artifact_root=root,
        report_name=report_name,
        classification=classification,
        status=status,
        closure_role=closure_role,
        key_findings=key_findings,
        reopen_implication="No branch reopen by itself.",
    )


def _second_pulse_rows(roots: tuple[str, ...]) -> list[dict[str, Any]]:
    out = []
    for index, root_text in enumerate(roots, start=1):
        root = Path(root_text)
        rows = _read_csv(root / "second_pulse_summary.csv")
        classification = _classification_from_rows(rows, "second_pulse_classification") or "second_pulse_contaminated_or_inconclusive"
        out.append(
            _stage_row(
                stage=f"active second-pulse control {index}",
                artifact_root=root,
                report_name="second_pulse_report.md",
                classification=classification,
                status="closed_negative",
                closure_role="Close active reinjection route",
                key_findings="Active second-pulse variants reduced clean return counts, worsened decay/outer contamination, or had negative added-work efficiency.",
                reopen_implication="Do not revisit active pulses without a new mechanism and work-efficiency criterion.",
            )
        )
    return out


def _build_claim_rows(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    support = _supporting_roots(evidence_rows)
    return [
        {
            "claim_type": "frozen_claim",
            "statement": "At 41^3, the neutral-lattice stronger-sponge inner-sponge-edge sign-flip cubic boundary source supports structured boundary-interference shell-window refocusing under strong controls.",
            "support_level": "supported_at_41^3",
            "supporting_artifacts": support.get("41^3 proof pack", ""),
        },
        {
            "claim_type": "frozen_non_claim",
            "statement": "The passive release-phase packet-control rule is not scale-validated at 51^3.",
            "support_level": "failed_scale_lift",
            "supporting_artifacts": "; ".join(filter(None, [support.get("51^3 resolution lift", ""), support.get("51^3 postmortem", "")])),
        },
        {
            "claim_type": "frozen_failure_explanation",
            "statement": "At 51^3, return timing remains organized, but strict return-family purity and spatial-pattern identity weaken.",
            "support_level": "supported_failure_localization",
            "supporting_artifacts": "; ".join(filter(None, [support.get("return-family gate audit", ""), support.get("off-comb leakage audit", ""), support.get("return-pattern symmetry audit", "")])),
        },
        {
            "claim_type": "frozen_forbidden_paths",
            "statement": "Do not run cutoff tuning, source shaping, patch masks, smooth envelopes, active pulses, resonators, central bursts, 61^3, detector retuning, or symmetry-lock runs from the current evidence.",
            "support_level": "closed_until_new_mechanism",
            "supporting_artifacts": "branch_closure_forbidden_paths.csv",
        },
        {
            "claim_type": "future_unlock_condition",
            "statement": "Reopen only if a genuinely new mechanism predicts stable spatial-pattern memory, not merely better launch timing, better source shape, or a looser detector.",
            "support_level": "required_for_reopen",
            "supporting_artifacts": "branch_closure_reopen_criteria.csv",
        },
    ]


def _build_forbidden_rows(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    support = _supporting_roots(evidence_rows)
    return [
        _forbidden("nearby cutoff / phase tuning", "51^3 lift and postmortem show shared shrinkage and no single predictive retry.", support, "51^3 resolution lift", "51^3 postmortem"),
        _forbidden("smooth envelopes / source shaping", "The authorized same-release smooth-envelope test reduced sidebands but failed strict counts and coherence.", support, "source-spectrum design gate", "smooth-envelope source shaping"),
        _forbidden("patch masks / phase-conjugate wavefront fitting", "The frozen 96-patch candidate did not beat hard or shuffled controls.", support, "boundary phase-conjugate patch mask"),
        _forbidden("modal-sparsity-derived source variants", "51^3 source controls share a common modal/reconstruction signature rather than separating into a useful rescue.", support, "modal sparsity audit"),
        _forbidden("return gate or detector retuning", "The return-family gate audit rejects detector-only rescue.", support, "return-family gate audit"),
        _forbidden("off-comb-derived source masks", "Off-comb leakage localizes pattern scrambling but does not produce a stable source-control mechanism.", support, "off-comb leakage audit"),
        _forbidden("symmetry lock / orientation drift / cubic hopping / phase precession runs", "The symmetry audit found partial alignment rescue without stable transform signatures.", support, "return-pattern symmetry audit"),
        _forbidden("active second pulses", "Active reinjection reduced clean returns or failed added-work efficiency in existing controls.", support, "active second-pulse control 1", "active second-pulse control 2", "active second-pulse control 3", "active second-pulse control 4"),
        _forbidden("passive resonator expansion", "Coupled resonator variants degraded strict counts while no-resonator/zero-coupling rows preserved the cluster.", support, "passive resonator layer"),
        _forbidden("central burst broadening", "The central burst branch remained transient or contaminated and is not an improvement to the passive release-phase rule.", support, "central burst contrast branch"),
        _forbidden("61^3 or larger-grid escalation", "The 51^3 scale checkpoint failed and follow-on audits found no safe stable-memory mechanism.", support, "51^3 resolution lift", "return-pattern symmetry audit"),
    ]


def _build_reopen_rows() -> list[dict[str, Any]]:
    return [
        {
            "criterion": "new_stable_spatial_memory_mechanism",
            "required_evidence": "A mechanism-specific prediction for stable return-to-return spatial-pattern identity at higher resolution.",
            "current_status": "not_satisfied",
            "why_current_evidence_fails": "Current alignment improves scores but transform signatures are unstable and not shared across source controls.",
        },
        {
            "criterion": "pre_registered_non_tuning_prediction",
            "required_evidence": "A one-shot prediction made before seeing new 51^3 outcomes, with fixed gates and controls.",
            "current_status": "not_satisfied",
            "why_current_evidence_fails": "Existing proposed retries are timing/source-shape/patch variations already exhausted or explicitly unsupported.",
        },
        {
            "criterion": "preserve_clean_41_claim",
            "required_evidence": "Any future branch must leave the 41^3 proof claim and non-scale-validation wording intact unless it supplies a new validation ladder.",
            "current_status": "required_guardrail",
            "why_current_evidence_fails": "The 41^3 result is scientifically useful, but not breakthrough-ready or scale-validated.",
        },
    ]


def _summary_row(
    classification: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "branch_status": classification.get("checks", {}).get("branch_status", "scientifically_useful_not_breakthrough_ready"),
        "final_label": classification["label"],
        "frozen_claim": next(row["statement"] for row in claim_rows if row["claim_type"] == "frozen_claim"),
        "frozen_non_claim": next(row["statement"] for row in claim_rows if row["claim_type"] == "frozen_non_claim"),
        "failure_explanation": next(row["statement"] for row in claim_rows if row["claim_type"] == "frozen_failure_explanation"),
        "mechanism_candidate": classification.get("checks", {}).get("mechanism_candidate", "none"),
        "required_stage_count": classification.get("checks", {}).get("required_stage_count", 0),
        "evidence_stage_count": len(evidence_rows),
    }


def _write_report(
    path: Path,
    control_id: str,
    classification: dict[str, Any],
    summary: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
    forbidden_rows: list[dict[str, Any]],
    reopen_rows: list[dict[str, Any]],
) -> None:
    lines = [
        f"# Passive 3D Scale-Lift Branch Closure: {control_id}",
        "",
        "## Classification",
        "",
        f"- Result: `{classification['label']}`",
        f"- Status: `{summary['branch_status']}`",
        f"- Reason: {classification['reason']}",
        f"- Mechanism-derived next candidate: `{summary['mechanism_candidate']}`",
        "",
        "## Frozen Claims",
        "",
    ]
    for row in claim_rows:
        lines.append(f"- `{row['claim_type']}`: {row['statement']}")
    lines.extend(
        [
            "",
            "## Evidence Chain",
            "",
            "| Stage | Classification | Closure role | Key finding |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in evidence_rows:
        lines.append(
            f"| {row.get('stage')} | `{row.get('classification')}` | {row.get('closure_role')} | {row.get('key_findings')} |"
        )
    lines.extend(
        [
            "",
            "## Forbidden Paths",
            "",
            "| Path | Reason |",
            "| --- | --- |",
        ]
    )
    for row in forbidden_rows:
        lines.append(f"| {row.get('path')} | {row.get('reason')} |")
    lines.extend(
        [
            "",
            "## Reopen Criteria",
            "",
            "| Criterion | Required evidence | Current status |",
            "| --- | --- | --- |",
        ]
    )
    for row in reopen_rows:
        lines.append(f"| {row.get('criterion')} | {row.get('required_evidence')} | {row.get('current_status')} |")
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `branch_closure_summary.csv`",
            "- `branch_closure_evidence_chain.csv`",
            "- `branch_closure_claims.csv`",
            "- `branch_closure_forbidden_paths.csv`",
            "- `branch_closure_reopen_criteria.csv`",
            "- `branch_closure_summary.json`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _stage_row(
    *,
    stage: str,
    artifact_root: Path,
    report_name: str,
    classification: str,
    status: str,
    closure_role: str,
    key_findings: str,
    reopen_implication: str,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "artifact_root": str(artifact_root),
        "report_path": str(artifact_root / report_name),
        "classification": classification,
        "status": status,
        "closure_role": closure_role,
        "key_findings": key_findings,
        "reopen_implication": reopen_implication,
    }


def _forbidden(path: str, reason: str, support: dict[str, str], *stages: str) -> dict[str, Any]:
    return {
        "path": path,
        "status": "forbidden_until_new_mechanism",
        "reason": reason,
        "supporting_artifacts": "; ".join(filter(None, [support.get(stage, "") for stage in stages])),
    }


def _supporting_roots(evidence_rows: list[dict[str, Any]]) -> dict[str, str]:
    return {str(row.get("stage")): str(row.get("artifact_root")) for row in evidence_rows}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _classification_from_rows(rows: list[dict[str, Any]], field: str) -> str:
    for row in rows:
        value = row.get(field)
        if value not in (None, ""):
            return str(value)
    return ""


def _first(row: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return _float(value)
    return 0.0


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _mean(values: Any) -> float:
    parsed = np.asarray([_float(value) for value in values if value not in (None, "")], dtype=float)
    return float(np.mean(parsed)) if parsed.size else 0.0


def _range_text(values: list[float]) -> str:
    clean = [value for value in values if math.isfinite(value) and value != 0.0]
    if not clean:
        return "n/a"
    if len(clean) == 1:
        return _format(clean[0])
    return f"{_format(min(clean))}-{_format(max(clean))}"


def _summary_fields() -> list[str]:
    return [
        "branch_closure_classification",
        "branch_status",
        "final_label",
        "frozen_claim",
        "frozen_non_claim",
        "failure_explanation",
        "mechanism_candidate",
        "required_stage_count",
        "evidence_stage_count",
    ]


def _evidence_fields() -> list[str]:
    return [
        "branch_closure_classification",
        "stage",
        "artifact_root",
        "report_path",
        "classification",
        "status",
        "closure_role",
        "key_findings",
        "reopen_implication",
    ]


def _claim_fields() -> list[str]:
    return ["branch_closure_classification", "claim_type", "statement", "support_level", "supporting_artifacts"]


def _forbidden_fields() -> list[str]:
    return ["branch_closure_classification", "path", "status", "reason", "supporting_artifacts"]


def _reopen_fields() -> list[str]:
    return [
        "branch_closure_classification",
        "criterion",
        "required_evidence",
        "current_status",
        "why_current_evidence_fails",
    ]
