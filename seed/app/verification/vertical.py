"""Portable Human Minority verification bundle V1.

This module validates exact candidate bytes, producer claim material, explicit
verification obligations and independently supplied verifier results. It does
not execute candidate code, authenticate verifier identities, grant publication
authority or implement a second lifecycle.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

from seed.app.core.canonical_json import JsonValue, parse_json_bytes
from seed.app.core.errors import CanonicalJsonError
from seed.app.core.hashing import canonical_sha256, sha256_hex

from .claims import (
    AcceptanceDecision,
    CandidateClaim,
    VerificationResult,
    VerificationStatus,
)
from .decision import AcceptanceBindingError, decide_acceptance


BUNDLE_SCHEMA_VERSION = "human-minority-verification-bundle-v1"
MAX_CANDIDATE_BYTES = 8 * 1024 * 1024
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PublicVerificationError(ValueError):
    """The public verification bundle is malformed or fails exact binding."""


@dataclass(frozen=True)
class CandidateBundle:
    candidate_identity: str
    producer_id: str
    claim: CandidateClaim
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class VerificationObligation:
    plan_id: str
    claim_id: str
    candidate_identity: str
    required_check_ids: tuple[str, ...]
    trusted_verifier_ids: tuple[str, ...]


@dataclass(frozen=True)
class VerifierResultEnvelope:
    verifier_id: str
    candidate_identity: str
    result: VerificationResult

    @property
    def fingerprint(self) -> str:
        return canonical_sha256(
            {
                "verifier_id": self.verifier_id,
                "candidate_identity": self.candidate_identity,
                "result": {
                    "result_id": self.result.result_id,
                    "claim_id": self.result.claim_id,
                    "check_id": self.result.check_id,
                    "status": self.result.status.value,
                    "evidence_ids": list(self.result.evidence_ids),
                },
            }
        )


@dataclass(frozen=True)
class PublicVerticalResult:
    candidate_identity: str
    producer_id: str
    claim_id: str
    plan_id: str
    required_check_ids: tuple[str, ...]
    verifier_results: tuple[VerifierResultEnvelope, ...]
    decision: AcceptanceDecision
    binding_fingerprint: str

    def output(self) -> dict[str, JsonValue]:
        return {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "candidate_identity": self.candidate_identity,
            "producer_id": self.producer_id,
            "claim_id": self.claim_id,
            "plan_id": self.plan_id,
            "required_check_ids": list(self.required_check_ids),
            "results": [
                {
                    "verifier_id": envelope.verifier_id,
                    "candidate_identity": envelope.candidate_identity,
                    "envelope_fingerprint": envelope.fingerprint,
                    "result_id": envelope.result.result_id,
                    "check_id": envelope.result.check_id,
                    "status": envelope.result.status.value,
                    "evidence_ids": list(envelope.result.evidence_ids),
                }
                for envelope in self.verifier_results
            ],
            "acceptance_outcome": self.decision.outcome.value,
            "decision_id": self.decision.decision_id,
            "binding_fingerprint": self.binding_fingerprint,
        }


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise PublicVerificationError(f"{name} must be a non-empty plain string")
    return value


def _text_tuple(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not list or not value:
        raise PublicVerificationError(f"{name} must be a non-empty array")
    if any(type(item) is not str or not item for item in value):
        raise PublicVerificationError(f"{name} must contain non-empty strings")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise PublicVerificationError(f"{name} must be unique")
    return result


def _exact_object(
    value: object,
    *,
    name: str,
    fields: frozenset[str],
) -> Mapping[str, JsonValue]:
    if type(value) is not dict or set(value) != fields:
        raise PublicVerificationError(f"{name} fields do not match the exact schema")
    return value


def _status(value: object) -> VerificationStatus:
    if type(value) is not str:
        raise PublicVerificationError("result.status must be a string")
    try:
        return VerificationStatus(value)
    except ValueError as exc:
        raise PublicVerificationError("result.status is unsupported") from exc


def _candidate_identity(candidate_bytes: bytes) -> str:
    return f"sha256:{sha256_hex(candidate_bytes)}"


def _read_candidate(path: Path) -> bytes:
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_CANDIDATE_BYTES + 1)
    except OSError as exc:
        raise PublicVerificationError("candidate could not be read") from exc
    if len(data) > MAX_CANDIDATE_BYTES:
        raise PublicVerificationError("candidate exceeds the public size limit")
    return data


def _load_bundle(path: Path) -> Mapping[str, JsonValue]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PublicVerificationError("bundle could not be read") from exc
    try:
        parsed = parse_json_bytes(raw)
    except CanonicalJsonError as exc:
        raise PublicVerificationError("bundle is not strict JSON") from exc
    return _exact_object(
        parsed,
        name="bundle",
        fields=frozenset(
            {"schema_version", "candidate", "obligation", "results"}
        ),
    )


def _parse_candidate(
    raw: object,
    *,
    candidate_identity: str,
) -> CandidateBundle:
    value = _exact_object(
        raw,
        name="candidate",
        fields=frozenset({"producer_id", "claim", "evidence_ids"}),
    )
    claim_raw = _exact_object(
        value["claim"],
        name="candidate.claim",
        fields=frozenset({"claim_id", "assertion", "raw_artifact_ref"}),
    )
    claim = CandidateClaim(
        claim_id=_text(claim_raw["claim_id"], "candidate.claim.claim_id"),
        assertion=_text(claim_raw["assertion"], "candidate.claim.assertion"),
        raw_artifact_ref=_text(
            claim_raw["raw_artifact_ref"],
            "candidate.claim.raw_artifact_ref",
        ),
    )
    return CandidateBundle(
        candidate_identity=candidate_identity,
        producer_id=_text(value["producer_id"], "candidate.producer_id"),
        claim=claim,
        evidence_ids=_text_tuple(
            value["evidence_ids"],
            "candidate.evidence_ids",
        ),
    )


def _parse_obligation(raw: object) -> VerificationObligation:
    value = _exact_object(
        raw,
        name="obligation",
        fields=frozenset(
            {
                "plan_id",
                "claim_id",
                "candidate_identity",
                "required_check_ids",
                "trusted_verifier_ids",
            }
        ),
    )
    return VerificationObligation(
        plan_id=_text(value["plan_id"], "obligation.plan_id"),
        claim_id=_text(value["claim_id"], "obligation.claim_id"),
        candidate_identity=_text(
            value["candidate_identity"],
            "obligation.candidate_identity",
        ),
        required_check_ids=_text_tuple(
            value["required_check_ids"],
            "obligation.required_check_ids",
        ),
        trusted_verifier_ids=_text_tuple(
            value["trusted_verifier_ids"],
            "obligation.trusted_verifier_ids",
        ),
    )


def _parse_result_envelope(raw: object) -> VerifierResultEnvelope:
    value = _exact_object(
        raw,
        name="results[]",
        fields=frozenset({"verifier_id", "candidate_identity", "result"}),
    )
    result_raw = _exact_object(
        value["result"],
        name="results[].result",
        fields=frozenset(
            {"result_id", "claim_id", "check_id", "status", "evidence_ids"}
        ),
    )
    try:
        result = VerificationResult(
            result_id=_text(result_raw["result_id"], "result.result_id"),
            claim_id=_text(result_raw["claim_id"], "result.claim_id"),
            check_id=_text(result_raw["check_id"], "result.check_id"),
            status=_status(result_raw["status"]),
            evidence_ids=_text_tuple(
                result_raw["evidence_ids"],
                "result.evidence_ids",
            ),
        )
    except ValueError as exc:
        raise PublicVerificationError("verification result contract is invalid") from exc
    return VerifierResultEnvelope(
        verifier_id=_text(value["verifier_id"], "results[].verifier_id"),
        candidate_identity=_text(
            value["candidate_identity"],
            "results[].candidate_identity",
        ),
        result=result,
    )


def _parse_results(raw: object) -> tuple[VerifierResultEnvelope, ...]:
    if type(raw) is not list or not raw:
        raise PublicVerificationError("results must be a non-empty array")
    return tuple(_parse_result_envelope(item) for item in raw)


def _require_expected_sha256(
    candidate_bytes: bytes,
    expected_candidate_sha256: str | None,
) -> None:
    if expected_candidate_sha256 is None:
        return
    if _HEX64.fullmatch(expected_candidate_sha256) is None:
        raise PublicVerificationError(
            "expected candidate SHA-256 must be lowercase 64-character hex"
        )
    if sha256_hex(candidate_bytes) != expected_candidate_sha256:
        raise PublicVerificationError("expected candidate SHA-256 mismatch")


def verify_bundle(
    *,
    candidate_bytes: bytes,
    bundle: Mapping[str, JsonValue],
    expected_candidate_sha256: str | None = None,
) -> PublicVerticalResult:
    """Validate one public bundle and reduce its exact verifier results."""

    if type(candidate_bytes) is not bytes:
        raise PublicVerificationError("candidate_bytes must be bytes")
    if len(candidate_bytes) > MAX_CANDIDATE_BYTES:
        raise PublicVerificationError("candidate exceeds the public size limit")
    _require_expected_sha256(candidate_bytes, expected_candidate_sha256)

    root = _exact_object(
        bundle,
        name="bundle",
        fields=frozenset(
            {"schema_version", "candidate", "obligation", "results"}
        ),
    )
    if root["schema_version"] != BUNDLE_SCHEMA_VERSION:
        raise PublicVerificationError("bundle schema_version is unsupported")

    identity = _candidate_identity(candidate_bytes)
    candidate = _parse_candidate(
        root["candidate"],
        candidate_identity=identity,
    )
    obligation = _parse_obligation(root["obligation"])
    envelopes = _parse_results(root["results"])

    if obligation.candidate_identity != identity:
        raise PublicVerificationError("obligation candidate identity mismatch")
    if candidate.claim.raw_artifact_ref != identity:
        raise PublicVerificationError("claim raw artifact reference mismatch")
    if obligation.claim_id != candidate.claim.claim_id:
        raise PublicVerificationError("obligation claim binding mismatch")
    if candidate.producer_id in obligation.trusted_verifier_ids:
        raise PublicVerificationError(
            "producer must not be a trusted verifier for the same vertical"
        )

    seen_pairs: set[tuple[str, str]] = set()
    seen_result_ids: set[str] = set()
    by_check: dict[str, VerifierResultEnvelope] = {}
    for envelope in envelopes:
        if envelope.verifier_id == candidate.producer_id:
            raise PublicVerificationError(
                "producer identity must not verify its own candidate"
            )
        if envelope.verifier_id not in obligation.trusted_verifier_ids:
            raise PublicVerificationError("verifier identity is not trusted")
        if envelope.candidate_identity != identity:
            raise PublicVerificationError("verifier result candidate identity mismatch")
        if envelope.result.claim_id != candidate.claim.claim_id:
            raise PublicVerificationError("verifier result claim binding mismatch")

        if envelope.result.result_id in seen_result_ids:
            raise PublicVerificationError("duplicate verification result_id")
        seen_result_ids.add(envelope.result.result_id)

        pair = (envelope.verifier_id, envelope.result.check_id)
        if pair in seen_pairs:
            raise PublicVerificationError("duplicate verifier/check binding")
        seen_pairs.add(pair)
        if envelope.result.check_id in by_check:
            raise PublicVerificationError("duplicate required check result")
        by_check[envelope.result.check_id] = envelope

    if set(by_check) != set(obligation.required_check_ids):
        raise PublicVerificationError(
            "verification results do not cover the exact required checks"
        )

    ordered_envelopes = tuple(
        by_check[check_id] for check_id in obligation.required_check_ids
    )
    try:
        decision = decide_acceptance(
            claim_id=obligation.claim_id,
            plan_id=obligation.plan_id,
            expected_check_ids=obligation.required_check_ids,
            results=tuple(item.result for item in ordered_envelopes),
        )
    except AcceptanceBindingError as exc:
        raise PublicVerificationError("acceptance binding rejected") from exc

    binding_fingerprint = canonical_sha256(
        {
            "candidate_identity": identity,
            "producer_id": candidate.producer_id,
            "claim": {
                "claim_id": candidate.claim.claim_id,
                "assertion": candidate.claim.assertion,
                "raw_artifact_ref": candidate.claim.raw_artifact_ref,
            },
            "candidate_evidence_ids": list(candidate.evidence_ids),
            "plan_id": obligation.plan_id,
            "required_check_ids": list(obligation.required_check_ids),
            "trusted_verifier_ids": list(obligation.trusted_verifier_ids),
            "verifier_result_fingerprints": [
                item.fingerprint for item in ordered_envelopes
            ],
            "decision_id": decision.decision_id,
        }
    )
    return PublicVerticalResult(
        candidate_identity=identity,
        producer_id=candidate.producer_id,
        claim_id=candidate.claim.claim_id,
        plan_id=obligation.plan_id,
        required_check_ids=obligation.required_check_ids,
        verifier_results=ordered_envelopes,
        decision=decision,
        binding_fingerprint=binding_fingerprint,
    )


def verify_bundle_files(
    *,
    candidate_path: Path,
    bundle_path: Path,
    expected_candidate_sha256: str | None = None,
) -> PublicVerticalResult:
    candidate_bytes = _read_candidate(candidate_path)
    bundle = _load_bundle(bundle_path)
    return verify_bundle(
        candidate_bytes=candidate_bytes,
        bundle=bundle,
        expected_candidate_sha256=expected_candidate_sha256,
    )


def _print_json(value: Mapping[str, JsonValue]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate one exact candidate against a strict Human Minority "
            "verification bundle. This reference command does not execute "
            "candidate code or authenticate verifier identities."
        )
    )
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args(argv)

    try:
        result = verify_bundle_files(
            candidate_path=args.candidate,
            bundle_path=args.bundle,
            expected_candidate_sha256=args.expected_sha256,
        )
    except PublicVerificationError as exc:
        _print_json(
            {
                "schema_version": BUNDLE_SCHEMA_VERSION,
                "status": "INPUT_REJECTED",
                "error": str(exc),
            }
        )
        return 2

    _print_json(result.output())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
