"""Provider-neutral deterministic acceptance reduction shared by private Control and public verification."""

from __future__ import annotations

from seed.app.core.hashing import canonical_sha256

from .claims import (
    AcceptanceDecision,
    AcceptanceOutcome,
    VerificationResult,
    VerificationStatus,
)


class AcceptanceBindingError(ValueError):
    """Verification results are not exactly bound to the expected obligation."""


def decide_acceptance(
    *,
    claim_id: str,
    plan_id: str,
    expected_check_ids: tuple[str, ...],
    results: tuple[VerificationResult, ...],
) -> AcceptanceDecision:
    """Reduce one exact verification result set into the canonical Control decision."""

    for value, name in ((claim_id, "claim_id"), (plan_id, "plan_id")):
        if type(value) is not str or not value:
            raise AcceptanceBindingError(f"{name} must be a non-empty plain string")
    if type(expected_check_ids) is not tuple or not expected_check_ids:
        raise AcceptanceBindingError("expected_check_ids must be a non-empty tuple")
    if any(type(value) is not str or not value for value in expected_check_ids):
        raise AcceptanceBindingError(
            "expected_check_ids must contain non-empty plain strings"
        )
    if len(expected_check_ids) != len(set(expected_check_ids)):
        raise AcceptanceBindingError("expected_check_ids must be unique")
    if type(results) is not tuple:
        raise AcceptanceBindingError("results must be a tuple")
    if any(type(result) is not VerificationResult for result in results):
        raise AcceptanceBindingError(
            "results must contain exact VerificationResult values"
        )

    by_check = {result.check_id: result for result in results}
    if len(by_check) != len(results) or set(by_check) != set(expected_check_ids):
        raise AcceptanceBindingError(
            "verification results do not cover the exact VerificationPlan"
        )
    ordered = tuple(by_check[check_id] for check_id in expected_check_ids)
    if any(result.claim_id != claim_id for result in ordered):
        raise AcceptanceBindingError("verification result claim binding mismatch")

    if any(result.status is VerificationStatus.INCONCLUSIVE for result in ordered):
        outcome = AcceptanceOutcome.REJECT
    elif all(result.status is VerificationStatus.PASS for result in ordered):
        outcome = AcceptanceOutcome.ACCEPT
    else:
        outcome = AcceptanceOutcome.NEEDS_REPAIR

    material = {
        "claim_id": claim_id,
        "outcome": outcome.value,
        "plan_id": plan_id,
        "result_ids": [result.result_id for result in ordered],
    }
    return AcceptanceDecision(
        decision_id=f"control:{canonical_sha256(material)}",
        claim_id=claim_id,
        outcome=outcome,
        verification_results=ordered,
    )
