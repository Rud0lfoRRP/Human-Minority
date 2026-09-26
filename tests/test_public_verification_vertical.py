from __future__ import annotations

import json
from pathlib import Path

import pytest

from seed.app.verification.claims import AcceptanceOutcome
from seed.app.verification.vertical import (
    PublicVerificationError,
    verify_bundle_files,
)


EXAMPLE_ROOT = Path("examples/public_verification")


def test_public_verification_bundle_accepts_exact_published_example() -> None:
    result = verify_bundle_files(
        candidate_path=EXAMPLE_ROOT / "candidate.txt",
        bundle_path=EXAMPLE_ROOT / "bundle.json",
    )

    assert result.decision.outcome is AcceptanceOutcome.ACCEPT
    assert result.claim_id == "claim:example"
    assert result.plan_id == "plan:example"
    assert len(result.binding_fingerprint) == 64


def test_public_verification_bundle_rejects_candidate_substitution(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.txt"
    candidate.write_bytes(b"substituted candidate\n")

    with pytest.raises(
        PublicVerificationError,
        match="obligation candidate identity mismatch",
    ):
        verify_bundle_files(
            candidate_path=candidate,
            bundle_path=EXAMPLE_ROOT / "bundle.json",
        )


def test_public_verification_bundle_rejects_producer_verdict_field(
    tmp_path: Path,
) -> None:
    raw = json.loads((EXAMPLE_ROOT / "bundle.json").read_text(encoding="utf-8"))
    raw["results"][0]["result"]["acceptance"] = "ACCEPT"
    bundle = tmp_path / "bundle.json"
    bundle.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(
        PublicVerificationError,
        match="fields do not match the exact schema",
    ):
        verify_bundle_files(
            candidate_path=EXAMPLE_ROOT / "candidate.txt",
            bundle_path=bundle,
        )
