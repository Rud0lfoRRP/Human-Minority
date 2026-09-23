"""Provider-neutral facts; no dispatch, authorization, or secret custody."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from seed.app.core.errors import CanonicalJsonError
from seed.app.core.hashing import canonical_sha256


_BINDING_PATTERNS = {
    "ENVIRONMENT": re.compile(r"^env:[A-Z][A-Z0-9_]{1,126}$"),
    "HOST_SESSION": re.compile(r"^session:[A-Za-z0-9_.-]{1,120}$"),
    "OS_CREDENTIAL_STORE": re.compile(r"^os-store:[A-Za-z0-9_.:/-]{1,116}$"),
    "EXTERNAL_SECRET_PROVIDER": re.compile(r"^external:[A-Za-z0-9_.:/-]{1,116}$"),
}
_SECRET_MARKERS = ("sk-", "bearer ", "api_key=", "token=", "password=")


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a non-empty plain string")
    normalized = unicodedata.normalize("NFC", value)
    try:
        normalized.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must contain valid Unicode scalar values") from exc
    return normalized


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


class CredentialBackendKind(str, Enum):
    ENVIRONMENT = "ENVIRONMENT"
    HOST_SESSION = "HOST_SESSION"
    OS_CREDENTIAL_STORE = "OS_CREDENTIAL_STORE"
    EXTERNAL_SECRET_PROVIDER = "EXTERNAL_SECRET_PROVIDER"


class ProviderCapability(str, Enum):
    TEXT_INPUT = "TEXT_INPUT"
    IMAGE_INPUT = "IMAGE_INPUT"
    AUDIO_INPUT = "AUDIO_INPUT"
    TOOL_CALLING = "TOOL_CALLING"
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"


class FactAssessment(str, Enum):
    SATISFIED = "SATISFIED"
    BLOCKING = "BLOCKING"
    UNKNOWN = "UNKNOWN"


class ProviderCheckStage(str, Enum):
    ASSIGNMENT = "ASSIGNMENT"
    PRE_DISPATCH = "PRE_DISPATCH"


class ProviderLimitScopeKind(str, Enum):
    ACCOUNT = "ACCOUNT"
    ORGANIZATION = "ORGANIZATION"
    PROJECT = "PROJECT"
    WORKSPACE = "WORKSPACE"
    MODEL_PROFILE = "MODEL_PROFILE"
    REGION = "REGION"
    CREDENTIAL = "CREDENTIAL"
    PROVIDER_DEFINED = "PROVIDER_DEFINED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CredentialReference:
    reference_id: str
    provider_id: str
    backend: CredentialBackendKind
    binding_id: str
    account_ref: str | None
    project_ref: str | None
    workspace_ref: str | None
    reference_version: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference_id", _text(self.reference_id, "reference_id"))
        object.__setattr__(self, "provider_id", _text(self.provider_id, "provider_id"))
        if not isinstance(self.backend, CredentialBackendKind):
            raise ValueError("backend must be a CredentialBackendKind")
        binding_id = _text(self.binding_id, "binding_id")
        object.__setattr__(self, "binding_id", binding_id)
        lowered = binding_id.casefold()
        if any(marker in lowered for marker in _SECRET_MARKERS):
            raise ValueError("binding_id must be a lookup reference, not secret material")
        if _BINDING_PATTERNS[self.backend.value].fullmatch(binding_id) is None:
            raise ValueError("binding_id does not match its credential backend")
        for name in ("account_ref", "project_ref", "workspace_ref", "reference_version"):
            object.__setattr__(self, name, _optional_text(getattr(self, name), name))

    @classmethod
    def create(
        cls,
        *,
        provider_id: str,
        backend: CredentialBackendKind,
        binding_id: str,
        account_ref: str | None = None,
        project_ref: str | None = None,
        workspace_ref: str | None = None,
        reference_version: str | None = None,
    ) -> "CredentialReference":
        provider_id = _text(provider_id, "provider_id")
        if not isinstance(backend, CredentialBackendKind):
            raise ValueError("backend must be a CredentialBackendKind")
        binding_id = _text(binding_id, "binding_id")
        lowered = binding_id.casefold()
        if any(marker in lowered for marker in _SECRET_MARKERS):
            raise ValueError("binding_id must be a lookup reference, not secret material")
        if _BINDING_PATTERNS[backend.value].fullmatch(binding_id) is None:
            raise ValueError("binding_id does not match its credential backend")
        account_ref = _optional_text(account_ref, "account_ref")
        project_ref = _optional_text(project_ref, "project_ref")
        workspace_ref = _optional_text(workspace_ref, "workspace_ref")
        reference_version = _optional_text(reference_version, "reference_version")
        material = {
            "provider_id": provider_id,
            "backend": backend.value,
            "binding_id": binding_id,
            "account_ref": account_ref,
            "project_ref": project_ref,
            "workspace_ref": workspace_ref,
            "reference_version": reference_version,
        }
        return cls(
            reference_id=f"credential:{canonical_sha256(material)[:32]}",
            provider_id=provider_id,
            backend=backend,
            binding_id=binding_id,
            account_ref=account_ref,
            project_ref=project_ref,
            workspace_ref=workspace_ref,
            reference_version=reference_version,
        )

    def persistent_material(self) -> dict[str, str | None]:
        return {
            "reference_id": self.reference_id,
            "provider_id": self.provider_id,
            "backend": self.backend.value,
            "binding_id": self.binding_id,
            "account_ref": self.account_ref,
            "project_ref": self.project_ref,
            "workspace_ref": self.workspace_ref,
            "reference_version": self.reference_version,
        }

    def integrity_valid(self) -> bool:
        try:
            material = self.persistent_material()
            material.pop("reference_id")
            return self.reference_id == f"credential:{canonical_sha256(material)[:32]}"
        except (AttributeError, TypeError, ValueError, CanonicalJsonError):
            return False


@dataclass(frozen=True)
class ProviderRouteScope:
    provider_id: str
    model_identifier: str
    profile_id: str
    account_ref: str | None
    project_ref: str | None
    workspace_ref: str | None
    organization_ref: str | None
    region_ref: str | None
    credential_reference_id: str | None

    def __post_init__(self) -> None:
        for name in ("provider_id", "model_identifier", "profile_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "account_ref", "project_ref", "workspace_ref", "organization_ref",
            "region_ref", "credential_reference_id",
        ):
            object.__setattr__(self, name, _optional_text(getattr(self, name), name))

    def material(self) -> dict[str, str | None]:
        return {
            name: getattr(self, name)
            for name in (
                "provider_id", "model_identifier", "profile_id", "account_ref",
                "project_ref", "workspace_ref", "organization_ref", "region_ref",
                "credential_reference_id",
            )
        }


@dataclass(frozen=True)
class ProviderProfileIdentity:
    provider_id: str
    model_identifier: str
    profile_id: str

    def __post_init__(self) -> None:
        for name in ("provider_id", "model_identifier", "profile_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))

    def material(self) -> dict[str, str]:
        return {
            "provider_id": self.provider_id,
            "model_identifier": self.model_identifier,
            "profile_id": self.profile_id,
        }


@dataclass(frozen=True)
class ProviderLimitScope:
    kind: ProviderLimitScopeKind
    reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProviderLimitScopeKind):
            raise ValueError("limit scope kind must be ProviderLimitScopeKind")
        object.__setattr__(self, "reference", _text(self.reference, "limit scope reference"))

    def material(self) -> dict[str, str]:
        return {"kind": self.kind.value, "reference": self.reference}


@dataclass(frozen=True)
class DeclaredProviderLimit:
    name: str
    value: str
    scope: ProviderLimitScope
    provenance_ref: str

    def __post_init__(self) -> None:
        for field in ("name", "value", "provenance_ref"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if not isinstance(self.scope, ProviderLimitScope):
            raise ValueError("scope must be a ProviderLimitScope")


@dataclass(frozen=True)
class ProviderModelProfile:
    identity: ProviderProfileIdentity
    capabilities: frozenset[ProviderCapability]
    declared_limits: tuple[DeclaredProviderLimit, ...]
    provenance_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ProviderProfileIdentity):
            raise ValueError("identity must be a ProviderProfileIdentity")
        if type(self.capabilities) is not frozenset or any(
            not isinstance(value, ProviderCapability) for value in self.capabilities
        ):
            raise ValueError("capabilities must be ProviderCapability values")
        if type(self.declared_limits) is not tuple or any(
            not isinstance(value, DeclaredProviderLimit) for value in self.declared_limits
        ):
            raise ValueError("declared_limits must be DeclaredProviderLimit values")
        names = tuple(limit.name for limit in self.declared_limits)
        if len(names) != len(set(names)):
            raise ValueError("declared provider limit names must be unique")
        object.__setattr__(self, "provenance_ref", _text(self.provenance_ref, "provenance_ref"))


@dataclass(frozen=True)
class ProviderFact:
    fact_name: str
    assessment: FactAssessment
    provenance_ref: str
    enforced_scope: ProviderLimitScope | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_name", _text(self.fact_name, "fact_name"))
        if not isinstance(self.assessment, FactAssessment):
            raise ValueError("assessment must be FactAssessment")
        object.__setattr__(self, "provenance_ref", _text(self.provenance_ref, "provenance_ref"))
        if self.enforced_scope is not None and not isinstance(
            self.enforced_scope, ProviderLimitScope
        ):
            raise ValueError("enforced_scope must be ProviderLimitScope or None")

    def material(self) -> dict[str, object]:
        return {
            "fact_name": self.fact_name,
            "assessment": self.assessment.value,
            "provenance_ref": self.provenance_ref,
            "enforced_scope": (
                self.enforced_scope.material() if self.enforced_scope is not None else None
            ),
        }


@dataclass(frozen=True)
class LiveProviderObservation:
    observation_id: str
    route: ProviderRouteScope
    stage: ProviderCheckStage
    observed_at: str
    valid_until: str | None
    source_ref: str
    facts: tuple[ProviderFact, ...]
    observation_fingerprint: str

    def __post_init__(self) -> None:
        for name in ("observation_id", "observed_at", "source_ref", "observation_fingerprint"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "valid_until", _optional_text(self.valid_until, "valid_until"))
        if not isinstance(self.route, ProviderRouteScope):
            raise ValueError("route must be ProviderRouteScope")
        if not isinstance(self.stage, ProviderCheckStage):
            raise ValueError("stage must be ProviderCheckStage")
        observed_instant = _instant(self.observed_at)
        if self.valid_until is not None and _instant(self.valid_until) < observed_instant:
            raise ValueError("valid_until cannot precede observed_at")
        if type(self.facts) is not tuple or any(
            not isinstance(fact, ProviderFact) for fact in self.facts
        ):
            raise ValueError("facts must be ProviderFact values")
        names = tuple(fact.fact_name for fact in self.facts)
        if len(names) != len(set(names)):
            raise ValueError("provider fact names must be unique")
        object.__setattr__(
            self,
            "facts",
            tuple(sorted(self.facts, key=lambda fact: fact.fact_name)),
        )

    def _material(self) -> dict[str, object]:
        return {
            "observation_id": self.observation_id,
            "route": self.route.material(),
            "stage": self.stage.value,
            "observed_at": self.observed_at,
            "valid_until": self.valid_until,
            "source_ref": self.source_ref,
            "facts": [fact.material() for fact in self.facts],
        }

    def integrity_valid(self) -> bool:
        try:
            return self.observation_fingerprint == canonical_sha256(self._material())
        except (AttributeError, TypeError, ValueError, CanonicalJsonError):
            return False

    @classmethod
    def create(
        cls,
        *,
        observation_id: str,
        route: ProviderRouteScope,
        stage: ProviderCheckStage,
        observed_at: str,
        valid_until: str | None,
        source_ref: str,
        facts: tuple[ProviderFact, ...],
    ) -> "LiveProviderObservation":
        normalized_observation_id = _text(observation_id, "observation_id")
        normalized_observed_at = _text(observed_at, "observed_at")
        normalized_valid_until = _optional_text(valid_until, "valid_until")
        normalized_source_ref = _text(source_ref, "source_ref")
        observed_instant = _instant(normalized_observed_at)
        if normalized_valid_until is not None and _instant(normalized_valid_until) < observed_instant:
            raise ValueError("valid_until cannot precede observed_at")
        if not isinstance(route, ProviderRouteScope):
            raise ValueError("route must be ProviderRouteScope")
        if not isinstance(stage, ProviderCheckStage):
            raise ValueError("stage must be ProviderCheckStage")
        if type(facts) is not tuple or any(not isinstance(fact, ProviderFact) for fact in facts):
            raise ValueError("facts must be ProviderFact values")
        names = tuple(fact.fact_name for fact in facts)
        if len(names) != len(set(names)):
            raise ValueError("provider fact names must be unique")
        ordered = tuple(sorted(facts, key=lambda fact: fact.fact_name))
        material = {
            "observation_id": normalized_observation_id,
            "route": route.material(),
            "stage": stage.value,
            "observed_at": normalized_observed_at,
            "valid_until": normalized_valid_until,
            "source_ref": normalized_source_ref,
            "facts": [fact.material() for fact in ordered],
        }
        return cls(
            normalized_observation_id,
            route,
            stage,
            normalized_observed_at,
            normalized_valid_until,
            normalized_source_ref,
            ordered,
            canonical_sha256(material),
        )


def _instant(value: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise ValueError("timestamps must be ISO-8601 UTC values ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("timestamp must be a valid ISO-8601 UTC instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("timestamp must be UTC")
    return parsed
