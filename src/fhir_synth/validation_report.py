"""Shared validation reporting — runs the three validators, emits status
messages through a :class:`ProgressReporter`, and returns a quality summary.

Used by every entry point (CLI, MCP, future surfaces) that wants the same
✅ / ⚠️ output and quality dict shape.
"""

from __future__ import annotations

from typing import Any

from fhir_synth.reporter import ProgressReporter


async def report_validation_results(
    resources: list[dict[str, Any]],
    reporter: ProgressReporter,
    fhir_version: str = "R4B",
) -> dict[str, Any]:
    """Validate ``resources`` and stream the results through ``reporter``.

    Runs three validators and emits one summary line per check (plus a few
    per-error detail lines as warnings when something fails). Returns the
    quality summary dict callers can attach to their response payload.

    Args:
        resources: The list of FHIR resource dicts to validate.
        reporter: The progress reporter to emit status through.
        fhir_version: Reported in the success line ("all valid FHIR R4B").

    Returns:
        Quality summary dict — same shape used by the MCP server's response
        payload (totals, pass rates, error samples).
    """
    from fhir_synth.code_generator.fhir_validation import (
        validate_references,
        validate_resources,
    )
    from fhir_synth.code_generator.us_core_validation import validate_us_core

    # ── FHIR validation ────────────────────────────────────────────────────
    vr = validate_resources(resources)
    if vr.is_valid:
        await reporter.info(f"   ✅ {vr.total} resources — all valid FHIR {fhir_version}")
    else:
        await reporter.warning(
            f"   ⚠️  {vr.total} resources — {vr.valid} valid, "
            f"{vr.invalid} invalid ({vr.pass_rate:.0%} pass rate)"
        )
        for err in vr.errors[:5]:
            await reporter.error(
                f"      ❌ {err['resourceType']}/{err['id']}: "
                f"{'; '.join(err['errors'][:2])}"
            )

    # ── Reference integrity ────────────────────────────────────────────────
    ref_errors = validate_references(resources)
    broken_refs = sum(len(e.get("errors", [])) for e in ref_errors)
    if broken_refs == 0:
        await reporter.info("   ✅ Reference integrity — all references valid")
    else:
        await reporter.warning(
            f"   ⚠️  Reference integrity — {broken_refs} broken reference(s)"
        )
        for entry in ref_errors[:3]:
            for err in entry.get("errors", [])[:2]:
                await reporter.error(
                    f"      ↳ {entry['resourceType']}/{entry['id']}: {err}"
                )

    # ── US Core compliance ─────────────────────────────────────────────────
    ucr = validate_us_core(resources)
    if ucr.total_checked > 0:
        if not ucr.has_warnings:
            await reporter.info(
                f"   ✅ US Core — {ucr.total_checked} resources fully compliant"
            )
        else:
            non_compliant = ucr.total_checked - ucr.fully_compliant
            await reporter.warning(
                f"   ⚠️  US Core — {non_compliant}/{ucr.total_checked} resources "
                f"missing must-support fields ({ucr.compliance_rate:.0%} compliant)"
            )
            for w in ucr.warnings[:3]:
                missing = ", ".join(w["missing_must_support"][:3])
                await reporter.error(
                    f"      ↳ {w['resourceType']}/{w['id']}: missing {missing}"
                )

    return {
        "fhir_total": vr.total,
        "fhir_valid": vr.valid,
        "fhir_invalid": vr.invalid,
        "fhir_pass_rate": round(vr.pass_rate, 3),
        "broken_references": broken_refs,
        "us_core_total_checked": ucr.total_checked,
        "us_core_fully_compliant": ucr.fully_compliant,
        "us_core_compliance_rate": (
            round(ucr.compliance_rate, 3) if ucr.total_checked > 0 else None
        ),
        "fhir_errors_sample": vr.errors[:5],
        "reference_errors_sample": ref_errors[:3],
    }


__all__ = ["report_validation_results"]
