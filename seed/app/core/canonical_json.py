"""Strict parsing and deterministic bytes for ``seed-canonical-json-v1``."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Iterable, Mapping, TypeAlias
import unicodedata

from .errors import (
    CanonicalJsonError,
    CanonicalSetError,
    CoreErrorCode,
    DuplicateKeyError,
)


JsonValue: TypeAlias = None | bool | int | str | list["JsonValue"] | dict[str, "JsonValue"]
CanonicalPath: TypeAlias = tuple[str, ...]

_UTF8_BOM = b"\xef\xbb\xbf"
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_NESTING_DEPTH = 128
MAX_INTEGER_DIGITS = 1024


def _error(
    code: CoreErrorCode,
    message: str,
    **details: Any,
) -> CanonicalJsonError:
    return CanonicalJsonError(code, message, details=details)


def _normalize_string(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    try:
        normalized.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise _error(
            CoreErrorCode.INVALID_UNICODE,
            "JSON strings and keys must contain valid Unicode scalar values",
            start=error.start,
            end=error.end,
        ) from error
    return normalized


def _parse_integer(token: str) -> int:
    if token == "-0" or (token.startswith("0") and len(token) > 1) or token.startswith("-0"):
        raise _error(
            CoreErrorCode.NON_CANONICAL_INTEGER,
            f"non-canonical JSON integer spelling: {token!r}",
            token=token,
        )
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > MAX_INTEGER_DIGITS:
        raise _error(
            CoreErrorCode.INTEGER_DIGIT_LIMIT_EXCEEDED,
            f"JSON integer exceeds {MAX_INTEGER_DIGITS} digits",
            digits=len(digits),
            limit=MAX_INTEGER_DIGITS,
        )
    try:
        return int(token)
    except (ValueError, MemoryError) as error:
        raise _error(
            CoreErrorCode.RESOURCE_EXHAUSTED,
            "JSON integer conversion exceeded the bounded runtime",
        ) from error


def _reject_float(token: str) -> None:
    raise _error(
        CoreErrorCode.UNSUPPORTED_JSON_TYPE,
        "floating-point JSON numbers are forbidden",
        token=token,
    )


def _reject_constant(token: str) -> None:
    raise _error(
        CoreErrorCode.UNSUPPORTED_JSON_TYPE,
        "non-finite JSON numbers are forbidden",
        token=token,
    )


def _object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    raw_keys: set[str] = set()
    normalized_keys: dict[str, str] = {}
    result: dict[str, Any] = {}
    for raw_key, value in pairs:
        if raw_key in raw_keys:
            raise DuplicateKeyError(
                CoreErrorCode.DUPLICATE_JSON_KEY,
                f"raw duplicate JSON key: {raw_key!r}",
                details={"key": raw_key},
            )
        raw_keys.add(raw_key)
        key = _normalize_string(raw_key)
        previous = normalized_keys.get(key)
        if previous is not None:
            raise DuplicateKeyError(
                CoreErrorCode.NFC_KEY_COLLISION,
                f"JSON keys collide after NFC normalization: {previous!r}, {raw_key!r}",
                details={"normalized_key": key, "first_key": previous, "second_key": raw_key},
            )
        normalized_keys[key] = raw_key
        result[key] = value
    return result


def parse_json_bytes(data: bytes) -> JsonValue:
    """Parse strict UTF-8 JSON and return its NFC-normalized JSON value."""

    if not isinstance(data, bytes):
        raise _error(
            CoreErrorCode.UNSUPPORTED_JSON_TYPE,
            "strict JSON input must be bytes",
            actual_type=type(data).__name__,
        )
    try:
        if len(data) > MAX_INPUT_BYTES:
            raise _error(
                CoreErrorCode.INPUT_SIZE_LIMIT_EXCEEDED,
                f"JSON input exceeds {MAX_INPUT_BYTES} bytes",
                size=len(data),
                limit=MAX_INPUT_BYTES,
            )
        if data.startswith(_UTF8_BOM):
            raise _error(CoreErrorCode.UTF8_BOM_FORBIDDEN, "UTF-8 BOM is forbidden")
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise _error(
                CoreErrorCode.INVALID_UTF8,
                "input is not valid UTF-8",
                start=error.start,
                end=error.end,
            ) from error
        try:
            value = json.loads(
                text,
                object_pairs_hook=_object_from_pairs,
                parse_int=_parse_integer,
                parse_float=_reject_float,
                parse_constant=_reject_constant,
            )
        except JSONDecodeError as error:
            raise _error(
                CoreErrorCode.MALFORMED_JSON,
                error.msg,
                line=error.lineno,
                column=error.colno,
                position=error.pos,
            ) from error
        return normalize_json(value)
    except CanonicalJsonError:
        raise
    except (MemoryError, RecursionError, ValueError) as error:
        raise _error(
            CoreErrorCode.RESOURCE_EXHAUSTED,
            "JSON parsing exceeded the bounded runtime",
        ) from error


def _check_resource_limits(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_NESTING_DEPTH:
            raise _error(
                CoreErrorCode.NESTING_DEPTH_LIMIT_EXCEEDED,
                f"JSON nesting exceeds {MAX_NESTING_DEPTH}",
                depth=depth,
                limit=MAX_NESTING_DEPTH,
            )
        if type(node) is int:
            try:
                digits = len(str(abs(node)))
            except (ValueError, MemoryError) as error:
                raise _error(
                    CoreErrorCode.INTEGER_DIGIT_LIMIT_EXCEEDED,
                    f"JSON integer exceeds {MAX_INTEGER_DIGITS} digits",
                    limit=MAX_INTEGER_DIGITS,
                ) from error
            if digits > MAX_INTEGER_DIGITS:
                raise _error(
                    CoreErrorCode.INTEGER_DIGIT_LIMIT_EXCEEDED,
                    f"JSON integer exceeds {MAX_INTEGER_DIGITS} digits",
                    digits=digits,
                    limit=MAX_INTEGER_DIGITS,
                )
        elif type(node) is list:
            stack.extend((child, depth + 1) for child in node)
        elif isinstance(node, Mapping):
            stack.extend((child, depth + 1) for child in node.values())


def _normalize_set_paths(paths: Iterable[CanonicalPath]) -> frozenset[CanonicalPath]:
    result: set[CanonicalPath] = set()
    for path in paths:
        if not isinstance(path, tuple) or any(not isinstance(item, str) or not item for item in path):
            raise CanonicalSetError(
                CoreErrorCode.INVALID_CANONICAL_SET_PATH,
                "canonical-set paths must be tuples of non-empty strings",
                details={"path": repr(path)},
            )
        result.add(tuple("*" if item == "*" else _normalize_string(item) for item in path))
    return frozenset(result)


def _encode_normalized(value: JsonValue) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return text.encode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeError) as error:
        raise _error(
            CoreErrorCode.INVALID_UNICODE,
            "JSON string cannot be encoded as strict UTF-8",
        ) from error
    except (MemoryError, RecursionError, ValueError) as error:
        raise _error(
            CoreErrorCode.RESOURCE_EXHAUSTED,
            "canonical JSON encoding exceeded the bounded runtime",
        ) from error


def _normalize(
    value: Any,
    *,
    path: CanonicalPath,
    canonical_set_paths: frozenset[CanonicalPath],
) -> JsonValue:
    if value is None or type(value) is bool or type(value) is int:
        return value
    if type(value) is str:
        return _normalize_string(value)
    if type(value) is list:
        items = [
            _normalize(item, path=path + ("*",), canonical_set_paths=canonical_set_paths)
            for item in value
        ]
        if path not in canonical_set_paths:
            return items
        keyed = [(_encode_normalized(item), item) for item in items]
        keyed.sort(key=lambda pair: pair[0])
        for index in range(1, len(keyed)):
            if keyed[index - 1][0] == keyed[index][0]:
                raise CanonicalSetError(
                    CoreErrorCode.CANONICAL_SET_DUPLICATE,
                    "canonical-set array contains duplicate canonical items",
                    details={"path": path, "canonical_item": keyed[index][0].decode("utf-8")},
                )
        return [item for _, item in keyed]
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        origins: dict[str, str] = {}
        for raw_key, child in value.items():
            if type(raw_key) is not str:
                raise _error(
                    CoreErrorCode.UNSUPPORTED_JSON_TYPE,
                    "JSON object keys must be strings",
                    path=path,
                    actual_type=type(raw_key).__name__,
                )
            key = _normalize_string(raw_key)
            if key in normalized:
                raise DuplicateKeyError(
                    CoreErrorCode.NFC_KEY_COLLISION,
                    f"object keys collide after NFC normalization: {origins[key]!r}, {raw_key!r}",
                    details={"path": path, "normalized_key": key},
                )
            origins[key] = raw_key
            normalized[key] = _normalize(
                child,
                path=path + (key,),
                canonical_set_paths=canonical_set_paths,
            )
        return normalized
    raise _error(
        CoreErrorCode.UNSUPPORTED_JSON_TYPE,
        "value is outside the canonical JSON data model",
        path=path,
        actual_type=type(value).__name__,
    )


def normalize_json(
    value: Any,
    *,
    canonical_set_paths: Iterable[CanonicalPath] = (),
) -> JsonValue:
    """Return an NFC-normalized JSON value with declared sets canonicalized."""

    try:
        paths = _normalize_set_paths(canonical_set_paths)
        _check_resource_limits(value)
        return _normalize(value, path=(), canonical_set_paths=paths)
    except CanonicalJsonError:
        raise
    except (MemoryError, RecursionError, ValueError) as error:
        raise _error(
            CoreErrorCode.RESOURCE_EXHAUSTED,
            "canonical JSON normalization exceeded the bounded runtime",
        ) from error


def canonical_json_bytes(
    value: Any,
    *,
    canonical_set_paths: Iterable[CanonicalPath] = (),
) -> bytes:
    """Serialize a JSON value to exact ``seed-canonical-json-v1`` bytes."""

    normalized = normalize_json(value, canonical_set_paths=canonical_set_paths)
    return _encode_normalized(normalized)
