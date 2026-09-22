"""Secret-provider port; implementations own transient materialization."""

from __future__ import annotations

from contextlib import AbstractContextManager
from enum import Enum
from typing import Protocol

from .contracts import CredentialReference


class CredentialResolutionFailureKind(str, Enum):
    MISSING_BINDING = "MISSING_BINDING"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    CREDENTIAL_REVOKED = "CREDENTIAL_REVOKED"
    INSUFFICIENT_PROVIDER_PERMISSION = "INSUFFICIENT_PROVIDER_PERMISSION"
    UNKNOWN = "UNKNOWN"


class CredentialResolutionError(RuntimeError):
    def __init__(
        self,
        kind: CredentialResolutionFailureKind,
        *,
        reference_id: str,
        provider_id: str,
    ) -> None:
        if not isinstance(kind, CredentialResolutionFailureKind):
            raise ValueError("kind must be CredentialResolutionFailureKind")
        self.kind = kind
        self.reference_id = reference_id
        self.provider_id = provider_id
        super().__init__(
            f"provider credential resolution failed: {kind.value}; "
            f"provider={provider_id}; reference={reference_id}"
        )


class SecretProvider(Protocol):
    """Resolve late and expose secret bytes only inside a bounded context."""

    def resolve(
        self, reference: CredentialReference
    ) -> AbstractContextManager[memoryview]: ...
