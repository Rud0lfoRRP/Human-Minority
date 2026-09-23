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


@dataclass(frozen=True)
class SourceIdentity:
    adapter_id: str
    source_locator: str
    revision: str
    snapshot_id: str
    contract_version: str = SOURCE_ADAPTER_CONTRACT_VERSION


@dataclass(frozen=True)
class SourceEntry:
    path: str
    kind: SourceEntryKind
    support: SourceSupport
    object_ref: str
    content_sha256: str | None
    size_bytes: int | None


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
