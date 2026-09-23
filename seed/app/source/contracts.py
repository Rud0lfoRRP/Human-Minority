"""Generic source-adapter contracts; structural facts stay separate from content capability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


SOURCE_ADAPTER_CONTRACT_VERSION = "seed-source-adapter-v0.1.0"


class SourceEntryKind(Enum):
    """Taxonomy-ready structural kinds; adapters expose only facts they can prove."""

    REGULAR_FILE = "REGULAR_FILE"
    EXECUTABLE_FILE = "EXECUTABLE_FILE"
    SYMLINK = "SYMLINK"
    GITLINK = "GITLINK"
    LFS_POINTER = "LFS_POINTER"
    DIRECTORY = "DIRECTORY"
    ARCHIVE_ENTRY = "ARCHIVE_ENTRY"
    SPECIAL = "SPECIAL"
    UNKNOWN = "UNKNOWN"


class SourceSupport(Enum):
    """How safely the adapter can handle a structural entry without expansion."""

    SUPPORTED = "SUPPORTED"
    SUPPORTED_WITH_RESTRICTIONS = "SUPPORTED_WITH_RESTRICTIONS"
    KNOWN_UNSUPPORTED = "KNOWN_UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


def _require_text(value: object, name: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a non-empty plain string")


def _require_sha256(value: object, name: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True)
class SourceIdentity:
    adapter_id: str
    source_locator: str
    revision: str
    snapshot_id: str
    contract_version: str = SOURCE_ADAPTER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "adapter_id",
            "source_locator",
            "revision",
            "snapshot_id",
            "contract_version",
        ):
            _require_text(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class SourceEntry:
    path: str
    kind: SourceEntryKind
    support: SourceSupport
    object_ref: str
    content_sha256: str | None
    size_bytes: int | None

    def __post_init__(self) -> None:
        _require_text(self.path, "path")
        if not isinstance(self.kind, SourceEntryKind):
            raise ValueError("kind must be a SourceEntryKind")
        if not isinstance(self.support, SourceSupport):
            raise ValueError("support must be a SourceSupport")
        _require_text(self.object_ref, "object_ref")
        if self.content_sha256 is not None:
            _require_sha256(self.content_sha256, "content_sha256")
        if self.size_bytes is not None and (
            type(self.size_bytes) is not int or self.size_bytes < 0
        ):
            raise ValueError("size_bytes must be a non-negative integer or None")


@dataclass(frozen=True)
class MaterializedSource:
    """Hash-bound materialization facts, not an implicit filesystem checkout."""

    identity: SourceIdentity
    entries: tuple[SourceEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SourceIdentity):
            raise ValueError("identity must be a SourceIdentity")
        if type(self.entries) is not tuple or any(
            not isinstance(entry, SourceEntry) for entry in self.entries
        ):
            raise ValueError("entries must be a tuple of SourceEntry values")


class SourceAdapter(Protocol):
    """Port for exact-source identity, structural enumeration and verification."""

    def identity(self, source_locator: str, revision: str) -> SourceIdentity: ...

    def resolve(self, source_locator: str, revision: str) -> SourceIdentity: ...

    def enumerate(self, identity: SourceIdentity) -> tuple[SourceEntry, ...]: ...

    def materialize(
        self,
        identity: SourceIdentity,
        entries: tuple[SourceEntry, ...],
    ) -> MaterializedSource: ...

    def verify(self, materialized: MaterializedSource) -> None: ...
