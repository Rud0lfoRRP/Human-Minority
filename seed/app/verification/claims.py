"""Domain-neutral claim-verification contracts; no check execution or policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VerificationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class AcceptanceOutcome(Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    NEEDS_REPAIR = "NEEDS_REPAIR"


@dataclass(frozen=True)
class CandidateClaim:
    claim_id: str
    assertion: str
    raw_artifact_ref: str

    def __post_init__(self) -> None:
        for field_name in ("claim_id", "assertion", "raw_artifact_ref"):
            _require_text(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: str
    artifact_ref: str
    origin_context: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "kind", "artifact_ref"):
            _require_text(getattr(self, field_name), field_name)
        if self.origin_context is not None:
            _require_text(self.origin_context, "origin_context")


def _require_text(value: object, name: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a non-empty plain string")


def _require_text_tuple(values: object, name: str) -> None:
    if type(values) is not tuple:
        raise ValueError(f"{name} must be a tuple")
    if any(type(value) is not str or not value for value in values):
        raise ValueError(f"{name} must contain non-empty plain strings")


@dataclass(frozen=True)
class VerificationCheck:
    check_id: str
    name: str
    method: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("check_id", "name", "method"):
            _require_text(getattr(self, field_name), field_name)
        _require_text_tuple(self.evidence_ids, "evidence_ids")


@dataclass(frozen=True)
class VerificationResult:
    result_id: str
    claim_id: str
    check_id: str
    status: VerificationStatus
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("result_id", "claim_id", "check_id"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.status, VerificationStatus):
            raise ValueError("status must be a VerificationStatus")
        _require_text_tuple(self.evidence_ids, "evidence_ids")


@dataclass(frozen=True)
class AcceptanceDecision:
    decision_id: str
    claim_id: str
    outcome: AcceptanceOutcome
    verification_results: tuple[VerificationResult, ...]

    def __post_init__(self) -> None:
        _require_text(self.decision_id, "decision_id")
        _require_text(self.claim_id, "claim_id")
        if not isinstance(self.outcome, AcceptanceOutcome):
            raise ValueError("outcome must be an AcceptanceOutcome")
        if type(self.verification_results) is not tuple:
            raise ValueError("verification_results must be a tuple")
        if not self.verification_results:
            raise ValueError("AcceptanceDecision requires at least one VerificationResult")
        if any(not isinstance(result, VerificationResult) for result in self.verification_results):
            raise ValueError("verification_results must contain VerificationResult values")
        if any(result.claim_id != self.claim_id for result in self.verification_results):
            raise ValueError("VerificationResult claim_id must match AcceptanceDecision claim_id")
        if self.outcome is AcceptanceOutcome.ACCEPT and any(
            result.status is not VerificationStatus.PASS for result in self.verification_results
        ):
            raise ValueError("ACCEPT requires every VerificationResult to PASS")
