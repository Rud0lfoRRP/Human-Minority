from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess

from human_minority import cli


SECURITY_CONTACT = "humanminority.security@proton.me"


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _init_public_fixture(root: Path) -> None:
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "public-test@example.invalid")
    _git(root, "config", "user.name", "Public Test")

    security = (
        "# Security\n\n"
        f"Report security issues privately to **{SECURITY_CONTACT}**.\n"
    ).encode()
    boundary = b"# Public Boundary\n"
    payload = b"VALUE = 7\n"
    manifest = {
        "schema_version": "seed-public-release-manifest-v1",
        "artifact_stage": "EARLY_SOURCE_DROP",
        "boundary_document": "PUBLIC_BOUNDARY.md",
        "files": [
            {
                "kind": "metadata",
                "mode": "100644",
                "public_path": "PUBLIC_BOUNDARY.md",
                "public_sha256": _sha256(boundary),
                "transformation": "NONE",
            },
            {
                "kind": "metadata",
                "mode": "100644",
                "public_path": "SECURITY.md",
                "public_sha256": _sha256(security),
                "transformation": "NONE",
            },
            {
                "kind": "runtime",
                "mode": "100644",
                "public_path": "payload.py",
                "public_sha256": _sha256(payload),
                "transformation": "NONE",
            },
        ],
    }
    (root / "PUBLIC_BOUNDARY.md").write_bytes(boundary)
    (root / "SECURITY.md").write_bytes(security)
    (root / "payload.py").write_bytes(payload)
    (root / "export-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "public fixture")


def _write_bundle(tmp_path: Path, *, status: str = "PASS") -> tuple[Path, Path]:
    candidate = tmp_path / "candidate.txt"
    candidate.write_bytes(b"human-minority exact candidate v1\n")
    identity = "sha256:" + _sha256(candidate.read_bytes())
    bundle = {
        "schema_version": "human-minority-verification-bundle-v1",
        "candidate": {
            "producer_id": "worker:example",
            "claim": {
                "claim_id": "claim:example",
                "assertion": "candidate matches the supplied bytes",
                "raw_artifact_ref": identity,
            },
            "evidence_ids": ["candidate:evidence"],
        },
        "obligation": {
            "plan_id": "plan:example",
            "claim_id": "claim:example",
            "candidate_identity": identity,
            "required_check_ids": ["check:independent"],
            "trusted_verifier_ids": ["verifier:example"],
        },
        "results": [
            {
                "verifier_id": "verifier:example",
                "candidate_identity": identity,
                "result": {
                    "result_id": "result:example",
                    "claim_id": "claim:example",
                    "check_id": "check:independent",
                    "status": status,
                    "evidence_ids": ["verifier:evidence"],
                },
            }
        ],
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    return candidate, bundle_path


def test_help_exposes_only_public_v1_commands() -> None:
    help_text = cli._build_parser().format_help()

    assert "inspect" in help_text
    assert "verify" in help_text
    for private_name in ("doctor", "providers", "runtime", "assess", "contract"):
        assert private_name not in help_text


def test_no_command_is_usage_exit_2() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    rc = cli.main([], stdout=stdout, stderr=stderr)

    assert rc == 2
    assert "usage:" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_version_json_is_stable() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    rc = cli.main(["--version", "--json"], stdout=stdout, stderr=stderr)

    assert rc == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["schema_version"] == "seed-cli-result-v1"
    assert payload["command"] == "human-minority --version"
    assert payload["status"] == "OK"
    assert payload["facts"]["product_version"] == "0.0.0.dev0"


def test_inspect_pass_and_committed_tamper_fail(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "public"
    _init_public_fixture(root)
    monkeypatch.chdir(root)

    stdout = io.StringIO()
    assert cli.main(["inspect", "--json"], stdout=stdout, stderr=io.StringIO()) == 0
    payload = json.loads(stdout.getvalue())
    assert payload["status"] == "OK"
    assert payload["facts"]["integrity"] == "PASS"
    assert payload["facts"]["integrity_scope"] == "COMMITTED_HEAD"
    assert payload["facts"]["authenticity"] == "NOT_ESTABLISHED"
    assert payload["facts"]["working_tree_clean"] is True
    assert payload["facts"]["boundary_document"] == "PUBLIC_BOUNDARY.md"
    assert any("trusted published reference" in warning for warning in payload["warnings"])

    (root / "payload.py").write_text("VALUE = 8\n", encoding="utf-8", newline="\n")
    _git(root, "add", "payload.py")
    _git(root, "commit", "-m", "tamper")
    stdout = io.StringIO()
    assert cli.main(["inspect", "--json"], stdout=stdout, stderr=io.StringIO()) == 1
    assert json.loads(stdout.getvalue())["status"] == "DRIFTED"


def test_inspect_reports_dirty_worktree_without_reclassifying_head_integrity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "public"
    _init_public_fixture(root)
    monkeypatch.chdir(root)
    (root / "payload.py").write_text("VALUE = 99\n", encoding="utf-8", newline="\n")
    (root / "untracked.txt").write_text("local-only\n", encoding="utf-8", newline="\n")

    stdout = io.StringIO()
    rc = cli.main(["inspect", "--json"], stdout=stdout, stderr=io.StringIO())

    assert rc == 0
    payload = json.loads(stdout.getvalue())
    assert payload["facts"]["integrity"] == "PASS"
    assert payload["facts"]["integrity_scope"] == "COMMITTED_HEAD"
    assert payload["facts"]["working_tree_clean"] is False
    assert any("does not cover uncommitted or untracked files" in warning for warning in payload["warnings"])


def test_inspect_self_consistent_rehash_does_not_claim_authenticity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "public"
    _init_public_fixture(root)
    monkeypatch.chdir(root)

    payload_path = root / "payload.py"
    payload_path.write_text("VALUE = 8\n", encoding="utf-8", newline="\n")
    manifest_path = root / "export-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime_entry = next(
        item for item in manifest["files"] if item["public_path"] == "payload.py"
    )
    runtime_entry["public_sha256"] = _sha256(payload_path.read_bytes())
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _git(root, "add", "payload.py", "export-manifest.json")
    _git(root, "commit", "-m", "self-consistent rehash")

    stdout = io.StringIO()
    rc = cli.main(["inspect", "--json"], stdout=stdout, stderr=io.StringIO())

    assert rc == 0
    result = json.loads(stdout.getvalue())
    assert result["facts"]["integrity"] == "PASS"
    assert result["facts"]["authenticity"] == "NOT_ESTABLISHED"
    assert any("trusted published reference" in warning for warning in result["warnings"])


def test_inspect_without_public_checkout_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stdout = io.StringIO()

    rc = cli.main(["inspect", "--json"], stdout=stdout, stderr=io.StringIO())

    assert rc == 3
    assert json.loads(stdout.getvalue())["status"] == "UNAVAILABLE"


def test_verify_maps_accept_and_needs_repair(tmp_path: Path) -> None:
    candidate, bundle = _write_bundle(tmp_path, status="PASS")
    stdout = io.StringIO()
    rc = cli.main(
        ["verify", "--candidate", str(candidate), "--bundle", str(bundle), "--json"],
        stdout=stdout,
        stderr=io.StringIO(),
    )
    assert rc == 0
    accepted = json.loads(stdout.getvalue())
    assert accepted["status"] == "ACCEPT"
    assert accepted["facts"]["verification"]["acceptance_outcome"] == "ACCEPT"

    candidate, bundle = _write_bundle(tmp_path, status="FAIL")
    stdout = io.StringIO()
    rc = cli.main(
        ["verify", "--candidate", str(candidate), "--bundle", str(bundle), "--json"],
        stdout=stdout,
        stderr=io.StringIO(),
    )
    assert rc == 1
    repair = json.loads(stdout.getvalue())
    assert repair["status"] == "NEEDS_REPAIR"


def test_verify_rejects_candidate_substitution_as_input_error(tmp_path: Path) -> None:
    candidate, bundle = _write_bundle(tmp_path)
    candidate.write_bytes(b"substituted bytes\n")
    stdout = io.StringIO()

    rc = cli.main(
        ["verify", "--candidate", str(candidate), "--bundle", str(bundle), "--json"],
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert rc == 2
    assert json.loads(stdout.getvalue())["status"] == "INPUT_REJECTED"
