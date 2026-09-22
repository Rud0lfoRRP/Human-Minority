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


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: str
    artifact_ref: str
    origin_context: str | None = None


@dataclass(frozen=True)
class VerificationCheck:
    check_id: str
    name: str
    method: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class VerificationResult:
    result_id: str
    claim_id: str
    check_id: str
    status: VerificationStatus
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class AcceptanceDecision:
    decision_id: str
    claim_id: str
    outcome: AcceptanceOutcome
    verification_results: tuple[VerificationResult, ...]

    def __post_init__(self) -> None:
        if not self.verification_results:
            raise ValueError("AcceptanceDecision requires at least one VerificationResult")
        if any(result.claim_id != self.claim_id for result in self.verification_results):
            raise ValueError("VerificationResult claim_id must match AcceptanceDecision claim_id")
