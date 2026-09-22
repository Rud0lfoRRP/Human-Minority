from __future__ import annotations

from copy import deepcopy

import pytest

from seed.app.core.canonical_json import (
    MAX_INPUT_BYTES,
    MAX_INTEGER_DIGITS,
    MAX_NESTING_DEPTH,
    canonical_json_bytes,
    normalize_json,
    parse_json_bytes,
)
from seed.app.core.errors import (
    CanonicalJsonError,
    CanonicalSetError,
    CoreErrorCode,
    DuplicateKeyError,
    IntegrityError,
)
from seed.app.core.hashing import (
    _self_hash_with_exclusions,
    canonical_sha256,
    sha256_hex,
    verify_sha256,
)


GOLDEN_BYTES = '{"a":{"a":null,"b":true},"z":[3,2,1],"é":"Café"}'.encode()
GOLDEN_CANONICAL_HASH = "c2a3b742da21a99cbdcaf1f4bc202cae9472e4c748c1c19b2c15e1b99d6e9834"
GOLDEN_SELF_HASH = "25960887e50f258805f197d54ac5ebc6163460ac2ea18f031e015fee46e818da"


def test_canonical_json_golden_bytes_and_nfc() -> None:
    value = {"z": [3, 2, 1], "e\u0301": "Cafe\u0301", "a": {"b": True, "a": None}}
    assert canonical_json_bytes(value) == GOLDEN_BYTES


def test_object_order_is_canonical_but_array_order_is_not_changed() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})
    assert canonical_json_bytes({"items": [2, 1]}) != canonical_json_bytes({"items": [1, 2]})


def test_declared_canonical_set_is_sorted_by_canonical_item_bytes() -> None:
    value = {"items": ["é", "b", "a"]}
    assert canonical_json_bytes(value, canonical_set_paths={("items",)}) == (
        '{"items":["a","b","é"]}'.encode()
    )


def test_declared_canonical_set_rejects_normalized_duplicate() -> None:
    with pytest.raises(CanonicalSetError) as caught:
        canonical_json_bytes(
            {"items": ["é", "e\u0301"]},
            canonical_set_paths={("items",)},
        )
    assert caught.value.code is CoreErrorCode.CANONICAL_SET_DUPLICATE


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xef\xbb\xbf{}", CoreErrorCode.UTF8_BOM_FORBIDDEN),
        (b"\xff", CoreErrorCode.INVALID_UTF8),
        (b"{", CoreErrorCode.MALFORMED_JSON),
        (b'{"a":1,"a":2}', CoreErrorCode.DUPLICATE_JSON_KEY),
        (b'{"n":-0}', CoreErrorCode.NON_CANONICAL_INTEGER),
        (b'{"n":1.5}', CoreErrorCode.UNSUPPORTED_JSON_TYPE),
    ],
)
def test_strict_parser_rejects_invalid_input(payload: bytes, code: CoreErrorCode) -> None:
    with pytest.raises(CanonicalJsonError) as caught:
        parse_json_bytes(payload)
    assert caught.value.code is code


def test_duplicate_json_keys_preserve_specific_failure_type() -> None:
    with pytest.raises(DuplicateKeyError):
        parse_json_bytes(b'{"a":1,"a":2}')


def test_nfc_key_collision_is_rejected() -> None:
    with pytest.raises(CanonicalJsonError) as caught:
        normalize_json({"é": 1, "e\u0301": 2})
    assert caught.value.code is CoreErrorCode.NFC_KEY_COLLISION


def test_invalid_unicode_scalar_is_rejected() -> None:
    with pytest.raises(CanonicalJsonError) as caught:
        canonical_json_bytes("\ud800")
    assert caught.value.code is CoreErrorCode.INVALID_UNICODE


def test_integer_digit_bound_is_fail_closed() -> None:
    oversized = "1" * (MAX_INTEGER_DIGITS + 1)
    with pytest.raises(CanonicalJsonError) as caught:
        parse_json_bytes(oversized.encode())
    assert caught.value.code is CoreErrorCode.INTEGER_DIGIT_LIMIT_EXCEEDED


def test_input_size_bound_is_checked_before_decode() -> None:
    payload = b" " * (MAX_INPUT_BYTES + 1)
    with pytest.raises(CanonicalJsonError) as caught:
        parse_json_bytes(payload)
    assert caught.value.code is CoreErrorCode.INPUT_SIZE_LIMIT_EXCEEDED
    assert caught.value.details["limit"] == MAX_INPUT_BYTES


def test_nesting_depth_bound_is_fail_closed() -> None:
    value: object = None
    for _ in range(MAX_NESTING_DEPTH + 1):
        value = [value]
    with pytest.raises(CanonicalJsonError) as caught:
        canonical_json_bytes(value)
    assert caught.value.code is CoreErrorCode.NESTING_DEPTH_LIMIT_EXCEEDED
    assert caught.value.details["limit"] == MAX_NESTING_DEPTH


def test_exact_nesting_depth_boundary_remains_admitted() -> None:
    value: object = None
    for _ in range(MAX_NESTING_DEPTH):
        value = [value]
    encoded = canonical_json_bytes(value)
    assert encoded.startswith(b"[")
    assert encoded.endswith(b"]")


def test_sha256_and_canonical_hash_golden_vectors() -> None:
    assert sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    value = {"z": [3, 2, 1], "e\u0301": "Cafe\u0301", "a": {"b": True, "a": None}}
    assert canonical_sha256(value) == GOLDEN_CANONICAL_HASH


def test_self_hash_exclusion_golden_vector_is_immutable() -> None:
    value = {
        "schema_version": "v1",
        "payload": {"a": 1},
        "record_hash": "0" * 64,
    }
    original = deepcopy(value)
    assert _self_hash_with_exclusions(value, excluded_fields={("record_hash",)}) == GOLDEN_SELF_HASH
    assert value == original


def test_self_hash_exclusion_paths_are_nfc_normalized() -> None:
    nfd = {"cafe\u0301": "remove-me", "kept": 1}
    nfc = {"café": "remove-me", "kept": 1}
    assert _self_hash_with_exclusions(
        nfd,
        excluded_fields={("cafe\u0301",)},
    ) == _self_hash_with_exclusions(
        nfc,
        excluded_fields={("café",)},
    )


@pytest.mark.parametrize(
    "paths",
    [
        {("missing",)},
        {()},
        {("*",)},
        {("payload",), ("payload", "a")},
    ],
)
def test_invalid_self_hash_exclusions_fail_closed(paths: set[tuple[str, ...]]) -> None:
    with pytest.raises(IntegrityError) as caught:
        _self_hash_with_exclusions({"payload": {"a": 1}}, excluded_fields=paths)
    assert caught.value.code is CoreErrorCode.INVALID_HASH_EXCLUSION


def test_verify_sha256_accepts_exact_digest_and_rejects_mismatch() -> None:
    expected = sha256_hex(b"abc")
    verify_sha256(b"abc", expected)
    with pytest.raises(IntegrityError) as caught:
        verify_sha256(b"abd", expected)
    assert caught.value.code is CoreErrorCode.HASH_MISMATCH


@pytest.mark.parametrize("expected", ["ABC", "g" * 64, "0" * 63])
def test_verify_sha256_rejects_noncanonical_expected_digest(expected: str) -> None:
    with pytest.raises(IntegrityError) as caught:
        verify_sha256(b"abc", expected)
    assert caught.value.code is CoreErrorCode.HASH_MISMATCH
