"""SHA-256 helpers bound to ``seed-canonical-json-v1`` bytes."""

from __future__ import annotations

from hashlib import sha256
import hmac
from typing import Any, Iterable, Protocol

from .canonical_json import CanonicalPath, JsonValue, canonical_json_bytes, normalize_json
from .errors import CoreErrorCode, IntegrityError




def sha256_hex(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise IntegrityError(
            CoreErrorCode.UNSUPPORTED_JSON_TYPE,
            "SHA-256 input must be bytes",
            details={"actual_type": type(data).__name__},
        )
    return sha256(data).hexdigest()


def canonical_sha256(
    value: Any,
    *,
    canonical_set_paths: Iterable[CanonicalPath] = (),
) -> str:
    return sha256_hex(canonical_json_bytes(value, canonical_set_paths=canonical_set_paths))


def _validate_exclusions(paths: Iterable[CanonicalPath]) -> tuple[CanonicalPath, ...]:
    normalized: list[CanonicalPath] = []
    for path in paths:
        if not isinstance(path, tuple) or not path or any(type(item) is not str or not item or item == "*" for item in path):
            raise IntegrityError(
                CoreErrorCode.INVALID_HASH_EXCLUSION,
                "self-hash exclusions must be non-empty exact object-field paths",
                details={"path": repr(path)},
            )
        normalized.append(path)
    if len(normalized) != len(set(normalized)):
        raise IntegrityError(CoreErrorCode.INVALID_HASH_EXCLUSION, "duplicate self-hash exclusion")
    ordered = tuple(sorted(normalized))
    for index, path in enumerate(ordered):
        for other in ordered[index + 1 :]:
            if len(other) > len(path) and other[: len(path)] == path:
                raise IntegrityError(
                    CoreErrorCode.INVALID_HASH_EXCLUSION,
                    "overlapping self-hash exclusions are ambiguous",
                    details={"parent": path, "child": other},
                )
    return ordered


def _without_fields(value: JsonValue, paths: tuple[CanonicalPath, ...]) -> JsonValue:
    if type(value) is not dict:
        raise IntegrityError(
            CoreErrorCode.INVALID_HASH_EXCLUSION,
            "self-hash exclusions require an object root",
        )

    def remove(node: JsonValue, path: CanonicalPath) -> JsonValue:
        if type(node) is not dict:
            raise IntegrityError(
                CoreErrorCode.INVALID_HASH_EXCLUSION,
                "self-hash exclusion traverses a non-object",
                details={"path": path},
            )
        key = path[0]
        if key not in node:
            raise IntegrityError(
                CoreErrorCode.INVALID_HASH_EXCLUSION,
                "declared self-hash field is absent",
                details={"path": path},
            )
        copied = dict(node)
        if len(path) == 1:
            del copied[key]
        else:
            copied[key] = remove(copied[key], path[1:])
        return copied

    result: JsonValue = value
    for path in sorted(paths, key=len, reverse=True):
        result = remove(result, path)
    return result


def _self_hash_with_exclusions(
    value: Any,
    *,
    excluded_fields: Iterable[CanonicalPath],
    canonical_set_paths: Iterable[CanonicalPath] = (),
) -> str:
    """Hash a payload after removing exactly its declared self-hash fields."""

    exclusions = _validate_exclusions(excluded_fields)
    normalized = normalize_json(value, canonical_set_paths=canonical_set_paths)
    return canonical_sha256(
        _without_fields(normalized, exclusions),
        canonical_set_paths=canonical_set_paths,
    )








def _require_expected_sha256(expected_hash: Any) -> str:
    if (
        type(expected_hash) is not str
        or len(expected_hash) != 64
        or any(character not in "0123456789abcdef" for character in expected_hash)
    ):
        raise IntegrityError(
            CoreErrorCode.HASH_MISMATCH,
            "expected SHA-256 must be a lowercase 64-character hex digest",
            details={"actual_type": type(expected_hash).__name__},
        )
    return expected_hash


def verify_sha256(data: bytes, expected_hash: str) -> None:
    expected_hash = _require_expected_sha256(expected_hash)
    actual = sha256_hex(data)
    if not hmac.compare_digest(actual, expected_hash):
        raise IntegrityError(
            CoreErrorCode.HASH_MISMATCH,
            "SHA-256 mismatch",
            details={"expected": expected_hash, "actual": actual},
        )


