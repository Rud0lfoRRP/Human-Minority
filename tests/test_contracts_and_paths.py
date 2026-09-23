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


def test_acceptance_contract_rejects_mutable_or_untyped_results() -> None:
    passing = VerificationResult(
        "result-pass",
        "claim-1",
        "check-1",
        VerificationStatus.PASS,
        ("evidence-1",),
    )
    with pytest.raises(ValueError, match="verification_results must be a tuple"):
        AcceptanceDecision(
            "decision-list",
            "claim-1",
            AcceptanceOutcome.ACCEPT,
            [passing],  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="VerificationStatus"):
        VerificationResult(
            "result-string",
            "claim-1",
            "check-1",
            "PASS",  # type: ignore[arg-type]
            ("evidence-1",),
        )


def test_acceptance_contract_rejects_accept_over_failed_result() -> None:
    failing = VerificationResult(
        "result-fail",
        "claim-1",
        "check-1",
        VerificationStatus.FAIL,
        ("evidence-1",),
    )
    with pytest.raises(ValueError, match="every VerificationResult to PASS"):
        AcceptanceDecision(
            "decision-fail",
            "claim-1",
            AcceptanceOutcome.ACCEPT,
            (failing,),
        )


def test_materialized_source_rejects_mutable_entries() -> None:
    identity = SourceIdentity("git-v1", "repo", "a" * 40, "snapshot-1")
    entry = SourceEntry(
        "src/main.py",
        SourceEntryKind.REGULAR_FILE,
        SourceSupport.SUPPORTED,
        "blob:" + "b" * 40,
        "c" * 64,
        12,
    )
    with pytest.raises(ValueError, match="tuple of SourceEntry"):
        MaterializedSource(identity=identity, entries=[entry])  # type: ignore[arg-type]


@pytest.mark.parametrize("path", ["SECRET~1.JSO", "src/SECRET~1.JSO", "foo~12.txt"])
def test_windows_short_name_alias_shapes_fail_closed(path: str) -> None:
    with pytest.raises(CommandError) as caught:
        canonical_path(path)
    assert caught.value.code is CoreErrorCode.ADMISSION_INVALID


def test_acceptance_decision_rejects_mutable_results_and_nonpass_accept() -> None:
    result = VerificationResult(
        "result-1",
        "claim-1",
        "check-1",
        VerificationStatus.PASS,
        ("evidence-1",),
    )
    with pytest.raises(ValueError, match="verification_results must be a tuple"):
        AcceptanceDecision(
            "decision-1",
            "claim-1",
            AcceptanceOutcome.ACCEPT,
            [result],  # type: ignore[arg-type]
        )

    failing = VerificationResult(
        "result-fail",
        "claim-1",
        "check-1",
        VerificationStatus.FAIL,
        ("evidence-1",),
    )
    with pytest.raises(ValueError, match="every VerificationResult to PASS"):
        AcceptanceDecision(
            "decision-fail",
            "claim-1",
            AcceptanceOutcome.ACCEPT,
            (failing,),
        )


def test_verification_result_requires_typed_status() -> None:
    with pytest.raises(ValueError, match="VerificationStatus"):
        VerificationResult(
            "result-1",
            "claim-1",
            "check-1",
            "PASS",  # type: ignore[arg-type]
            ("evidence-1",),
        )


def test_windows_short_name_alias_shape_is_not_portable() -> None:
    with pytest.raises(CommandError):
        canonical_path("src/SECRET~1.JSO")


def test_claim_evidence_and_source_contracts_reject_mutable_or_malformed_fields() -> None:
    with pytest.raises(ValueError, match="claim_id"):
        CandidateClaim([], "assertion", "artifact:raw")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="origin_context"):
        Evidence("evidence-1", "artifact", "artifact:one", [])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="adapter_id"):
        SourceIdentity([], "repo", "revision", "snapshot")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="SourceEntryKind"):
        SourceEntry(
            "src/main.py",
            "REGULAR_FILE",  # type: ignore[arg-type]
            SourceSupport.SUPPORTED,
            "blob:one",
            "c" * 64,
            1,
        )
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        SourceEntry(
            "src/main.py",
            SourceEntryKind.REGULAR_FILE,
            SourceSupport.SUPPORTED,
            "blob:one",
            "not-a-digest",
            1,
        )
    with pytest.raises(ValueError, match="non-negative"):
        SourceEntry(
            "src/main.py",
            SourceEntryKind.REGULAR_FILE,
            SourceSupport.SUPPORTED,
            "blob:one",
            "c" * 64,
            -1,
        )


def test_verification_result_requires_nonempty_unique_evidence_ids() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        VerificationResult(
            "result-empty",
            "claim-1",
            "check-1",
            VerificationStatus.PASS,
            (),
        )
    with pytest.raises(ValueError, match="must be unique"):
        VerificationResult(
            "result-duplicate",
            "claim-1",
            "check-1",
            VerificationStatus.PASS,
            ("evidence-1", "evidence-1"),
        )
