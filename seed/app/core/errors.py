"""Typed fail-closed errors for the Human Minority public verification core."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class CoreErrorCode(str, Enum):
    INVALID_UTF8 = "INVALID_UTF8"
    UTF8_BOM_FORBIDDEN = "UTF8_BOM_FORBIDDEN"
    MALFORMED_JSON = "MALFORMED_JSON"
    DUPLICATE_JSON_KEY = "DUPLICATE_JSON_KEY"
    NFC_KEY_COLLISION = "NFC_KEY_COLLISION"
    UNSUPPORTED_JSON_TYPE = "UNSUPPORTED_JSON_TYPE"
    NON_CANONICAL_INTEGER = "NON_CANONICAL_INTEGER"
    INVALID_UNICODE = "INVALID_UNICODE"
    CANONICAL_SET_DUPLICATE = "CANONICAL_SET_DUPLICATE"
    INVALID_CANONICAL_SET_PATH = "INVALID_CANONICAL_SET_PATH"
    INPUT_SIZE_LIMIT_EXCEEDED = "INPUT_SIZE_LIMIT_EXCEEDED"
    NESTING_DEPTH_LIMIT_EXCEEDED = "NESTING_DEPTH_LIMIT_EXCEEDED"
    INTEGER_DIGIT_LIMIT_EXCEEDED = "INTEGER_DIGIT_LIMIT_EXCEEDED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    INVALID_HASH_EXCLUSION = "INVALID_HASH_EXCLUSION"
    HASH_MISMATCH = "HASH_MISMATCH"
    ADMISSION_INVALID = "ADMISSION_INVALID"


class SeedCoreError(Exception):
    """Base error with a stable machine-readable code and immutable details."""

    def __init__(
        self,
        code: CoreErrorCode,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = MappingProxyType(dict(details or {}))

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


class CanonicalJsonError(SeedCoreError):
    """Canonical JSON parsing or serialization failed."""


class DuplicateKeyError(CanonicalJsonError):
    """A raw or post-NFC duplicate object key was observed."""


class CanonicalSetError(CanonicalJsonError):
    """A schema-declared canonical set is invalid."""


class IntegrityError(SeedCoreError):
    """Canonical bytes do not satisfy an integrity assertion."""


class CommandError(SeedCoreError):
    """Structured admission or command validation failed closed."""
