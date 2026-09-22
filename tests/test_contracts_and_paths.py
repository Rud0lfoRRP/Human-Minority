from __future__ import annotations

import pytest

from seed.app.core.errors import CommandError, CoreErrorCode
from seed.app.source.contracts import (
    MaterializedSource,
    SourceEntry,
    SourceEntryKind,
    SourceIdentity,
    SourceSupport,
)
from seed.app.source.portable_paths import canonical_path, portable_key
from seed.app.verification.claims import (
    AcceptanceDecision,
    AcceptanceOutcome,
    CandidateClaim,
    Evidence,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)


def test_verification_contracts_hold_provider_neutral_facts() -> None:
    claim = CandidateClaim("claim-1", "candidate changed only allowed files", "artifact:raw")
    evidence = Evidence("evidence-1", "DIFF", "artifact:diff", "candidate")
    check = VerificationCheck("check-1", "diff scope", "deterministic", (evidence.evidence_id,))
    result = VerificationResult(
        "result-1",
        claim.claim_id,
        check.check_id,
        VerificationStatus.PASS,
        (evidence.evidence_id,),
    )
    decision = AcceptanceDecision(
        "decision-1",
        claim.claim_id,
        AcceptanceOutcome.ACCEPT,
        (result,),
    )
    assert decision.verification_results == (result,)
    assert result.status is VerificationStatus.PASS


def test_acceptance_decision_requires_verification_results() -> None:
    with pytest.raises(ValueError, match="at least one VerificationResult"):
        AcceptanceDecision("decision-1", "claim-1", AcceptanceOutcome.REJECT, ())


def test_acceptance_decision_rejects_mismatched_claim_results() -> None:
    result = VerificationResult(
        "result-1",
        "claim-other",
        "check-1",
        VerificationStatus.FAIL,
        ("evidence-1",),
    )
    with pytest.raises(ValueError, match="claim_id must match"):
        AcceptanceDecision(
            "decision-1",
            "claim-1",
            AcceptanceOutcome.REJECT,
            (result,),
        )


def test_source_contract_can_describe_hash_bound_materialization() -> None:
    identity = SourceIdentity(
        adapter_id="git-v1",
        source_locator="repo",
        revision="a" * 40,
        snapshot_id="snapshot-1",
    )
    entry = SourceEntry(
        path="src/main.py",
        kind=SourceEntryKind.REGULAR_FILE,
        support=SourceSupport.SUPPORTED,
        object_ref="blob:" + "b" * 40,
        content_sha256="c" * 64,
        size_bytes=12,
    )
    materialized = MaterializedSource(identity=identity, entries=(entry,))
    assert materialized.identity.contract_version == "seed-source-adapter-v0.1.0"
    assert materialized.entries == (entry,)


@pytest.mark.parametrize(
    "path",
    [
        "/absolute/path",
        "C:/drive/path",
        "a\\b",
        "../escape",
        "a/../escape",
        "a//b",
        "a/./b",
        "CON",
        "con.txt",
        "folder/NUL.data",
        "trailing. ",
    ],
)
def test_nonportable_repository_paths_fail_closed(path: str) -> None:
    with pytest.raises(CommandError) as caught:
        canonical_path(path)
    assert caught.value.code is CoreErrorCode.ADMISSION_INVALID


@pytest.mark.parametrize(
    "path",
    [
        "COM¹",
        "com².txt",
        "Folder/LPT³.data",
        "lpt¹",
    ],
)
def test_windows_superscript_device_names_fail_closed(path: str) -> None:
    with pytest.raises(CommandError) as caught:
        canonical_path(path)
    assert caught.value.code is CoreErrorCode.ADMISSION_INVALID


@pytest.mark.parametrize("path", ["src/\ud800.py", "src/\udfff.py"])
def test_lone_unicode_surrogates_fail_closed(path: str) -> None:
    with pytest.raises(CommandError) as caught:
        canonical_path(path)
    assert caught.value.code is CoreErrorCode.ADMISSION_INVALID


def test_valid_non_bmp_and_nonreserved_names_remain_allowed() -> None:
    assert canonical_path("src/😀.py") == "src/😀.py"
    assert canonical_path("COM0.txt") == "COM0.txt"


def test_portable_path_is_nfc_normalized() -> None:
    assert canonical_path("Cafe\u0301/file.txt") == "Café/file.txt"


def test_portable_key_is_casefolded_per_segment() -> None:
    assert portable_key("Folder/É.TXT") == portable_key("folder/é.txt")


def test_plain_relative_posix_path_is_preserved() -> None:
    assert canonical_path("src/package/module.py") == "src/package/module.py"
