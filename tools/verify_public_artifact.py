from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


MANIFEST_NAME = "export-manifest.json"
MANIFEST_SCHEMA = "seed-public-release-manifest-v1"
SECURITY_CONTACT = "humanminority.security@proton.me"


class PublicArtifactVerificationError(RuntimeError):
    pass


def _run_git(root: Path, *args: str) -> bytes:
    if not root.is_dir():
        raise PublicArtifactVerificationError(f"repository path does not exist: {root}")
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise PublicArtifactVerificationError(f"cannot execute git in {root}: {exc}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise PublicArtifactVerificationError(
            f"git {' '.join(args)} failed: {stderr or 'unknown git error'}"
        )
    return completed.stdout


def _git_blob(root: Path, path: str) -> bytes:
    return _run_git(root, "show", f"HEAD:{path}")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_public_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PublicArtifactVerificationError("manifest public_path must be a non-empty string")
    if "\\" in value:
        raise PublicArtifactVerificationError(f"manifest path uses backslash: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise PublicArtifactVerificationError(f"unsafe manifest path: {value}")
    return path.as_posix()


def _git_tree(root: Path) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for raw in _run_git(root, "ls-tree", "-rz", "--full-tree", "HEAD").split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        mode_b, type_b, blob_b = metadata.split(b" ", 2)
        path = raw_path.decode("utf-8")
        if type_b != b"blob":
            raise PublicArtifactVerificationError(
                f"non-blob tracked entry is not allowed: {path}"
            )
        if path in entries:
            raise PublicArtifactVerificationError(f"duplicate tracked path: {path}")
        entries[path] = (mode_b.decode("ascii"), blob_b.decode("ascii"))
    return entries


def verify_public_artifact(root: Path) -> None:
    root = root.resolve()
    manifest_bytes = _git_blob(root, MANIFEST_NAME)
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicArtifactVerificationError(
            "committed export-manifest.json is not valid UTF-8 JSON"
        ) from exc

    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise PublicArtifactVerificationError("unexpected public manifest schema")

    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise PublicArtifactVerificationError("manifest files must be a non-empty list")

    expected: dict[str, tuple[str, str]] = {}
    for entry in raw_files:
        if not isinstance(entry, dict):
            raise PublicArtifactVerificationError("manifest file entry must be an object")
        public_path = _safe_public_path(entry.get("public_path"))
        if public_path == MANIFEST_NAME:
            raise PublicArtifactVerificationError("manifest must not self-list export-manifest.json")
        mode = entry.get("mode")
        if mode not in {"100644", "100755"}:
            raise PublicArtifactVerificationError(f"unsupported mode for {public_path}: {mode!r}")
        sha = entry.get("public_sha256")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise PublicArtifactVerificationError(f"invalid SHA-256 for {public_path}")
        if public_path in expected:
            raise PublicArtifactVerificationError(f"duplicate manifest path: {public_path}")
        expected[public_path] = (mode, sha)

    tracked = _git_tree(root)
    expected_tracked = set(expected) | {MANIFEST_NAME}
    if set(tracked) != expected_tracked:
        missing = sorted(expected_tracked - set(tracked))
        extra = sorted(set(tracked) - expected_tracked)
        raise PublicArtifactVerificationError(
            f"tracked-file set mismatch: missing={missing}, extra={extra}"
        )
    if tracked[MANIFEST_NAME][0] != "100644":
        raise PublicArtifactVerificationError("export-manifest.json must be mode 100644")

    for public_path, (mode, sha) in expected.items():
        observed_mode = tracked[public_path][0]
        if observed_mode != mode:
            raise PublicArtifactVerificationError(
                f"mode mismatch for {public_path}: expected {mode}, got {observed_mode}"
            )
        observed = _sha256_bytes(_git_blob(root, public_path))
        if observed != sha:
            raise PublicArtifactVerificationError(
                f"SHA-256 mismatch for {public_path}: expected {sha}, got {observed}"
            )

    try:
        security = _git_blob(root, "SECURITY.md").decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicArtifactVerificationError(
            "committed SECURITY.md is not valid UTF-8"
        ) from exc
    if security.count(SECURITY_CONTACT) != 1:
        raise PublicArtifactVerificationError(
            "SECURITY.md must contain the publication security contact exactly once"
        )


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    try:
        verify_public_artifact(root)
    except PublicArtifactVerificationError as exc:
        print(f"PUBLIC ARTIFACT VERIFY: FAIL: {exc}", file=sys.stderr)
        return 2
    print("PUBLIC ARTIFACT VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
