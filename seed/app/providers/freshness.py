"""Explicit provider-observation freshness and invalidation policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import unicodedata

from .contracts import (
    FactAssessment,
    LiveProviderObservation,
    ProviderCheckStage,
    ProviderRouteScope,
)


class ProviderInvalidationKind(str, Enum):
    ROUTE_CHANGED = "ROUTE_CHANGED"
    CREDENTIAL_CHANGED = "CREDENTIAL_CHANGED"
    PROVIDER_FEEDBACK = "PROVIDER_FEEDBACK"
    RESET_BOUNDARY_CROSSED = "RESET_BOUNDARY_CROSSED"
    EXTERNAL_USAGE_CONSUMED = "EXTERNAL_USAGE_CONSUMED"
    MATERIAL_WAIT = "MATERIAL_WAIT"
    CONCURRENCY_PLAN_CHANGED = "CONCURRENCY_PLAN_CHANGED"
    WATCHDOG_INVALIDATED = "WATCHDOG_INVALIDATED"


class ObservationStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class FreshnessPolicy:
    max_age_seconds: int
    required_fact_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.max_age_seconds) is not int or self.max_age_seconds < 0:
            raise ValueError("max_age_seconds must be a non-negative integer")
        if type(self.required_fact_names) is not tuple or any(
            type(name) is not str or not name for name in self.required_fact_names
        ):
            raise ValueError("required_fact_names must be plain non-empty strings")
        normalized_names = tuple(
            unicodedata.normalize("NFC", name) for name in self.required_fact_names
        )
        try:
            for name in normalized_names:
                name.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("required_fact_names must contain valid Unicode scalar values") from exc
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError("required_fact_names must be unique")
        object.__setattr__(self, "required_fact_names", normalized_names)


@dataclass(frozen=True)
class ProviderInvalidation:
    kind: ProviderInvalidationKind
    occurred_at: str
    provenance_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProviderInvalidationKind):
            raise ValueError("kind must be ProviderInvalidationKind")
        _instant(self.occurred_at)
        if type(self.provenance_ref) is not str or not self.provenance_ref:
            raise ValueError("provenance_ref must be a non-empty string")


@dataclass(frozen=True)
class ObservationEvaluation:
    status: ObservationStatus
    reason_code: str
    observation_id: str
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, ObservationStatus):
            raise ValueError("status must be an ObservationStatus")
        for name, value in (
            ("reason_code", self.reason_code),
            ("observation_id", self.observation_id),
        ):
            if type(value) is not str or not value:
                raise ValueError(f"{name} must be a non-empty plain string")
        if type(self.provenance_refs) is not tuple or any(
            type(value) is not str or not value for value in self.provenance_refs
        ):
            raise ValueError("provenance_refs must be a tuple of non-empty plain strings")


def evaluate_observation(
    observation: LiveProviderObservation,
    *,
    expected_route: ProviderRouteScope,
    required_stage: ProviderCheckStage,
    now: str,
    policy: FreshnessPolicy,
    invalidations: tuple[ProviderInvalidation, ...] = (),
) -> ObservationEvaluation:
    if not isinstance(observation, LiveProviderObservation):
        raise ValueError("observation must be LiveProviderObservation")
    if not observation.integrity_valid():
        return _result(
            observation,
            ObservationStatus.INDETERMINATE,
            "OBSERVATION_INTEGRITY_INVALID",
        )
    if observation.route != expected_route:
        return _result(observation, ObservationStatus.STALE, "ROUTE_SCOPE_MISMATCH")
    if observation.stage is not required_stage:
        return _result(observation, ObservationStatus.STALE, "CHECK_STAGE_MISMATCH")
    try:
        observed = _instant(observation.observed_at)
        valid_until = (
            _instant(observation.valid_until)
            if observation.valid_until is not None
            else None
        )
    except ValueError:
        return _result(
            observation,
            ObservationStatus.INDETERMINATE,
            "OBSERVATION_TIME_INVALID",
        )
    current = _instant(now)
    if observed > current:
        return _result(observation, ObservationStatus.INDETERMINATE, "OBSERVATION_FROM_FUTURE")
    if (current - observed).total_seconds() > policy.max_age_seconds:
        return _result(observation, ObservationStatus.STALE, "EXPLICIT_MAX_AGE_EXCEEDED")
    if valid_until is not None and current > valid_until:
        return _result(observation, ObservationStatus.STALE, "PROVIDER_VALIDITY_EXPIRED")
    for invalidation in invalidations:
        occurred = _instant(invalidation.occurred_at)
        if observed <= occurred <= current:
            return ObservationEvaluation(
                ObservationStatus.STALE,
                f"INVALIDATED_{invalidation.kind.value}",
                observation.observation_id,
                (observation.source_ref, invalidation.provenance_ref),
            )
    facts = {fact.fact_name: fact for fact in observation.facts}
    if any(name not in facts for name in policy.required_fact_names):
        return _result(observation, ObservationStatus.INDETERMINATE, "REQUIRED_FACT_MISSING")
    if any(
        facts[name].assessment is FactAssessment.UNKNOWN
        for name in policy.required_fact_names
    ):
        return _result(observation, ObservationStatus.INDETERMINATE, "REQUIRED_FACT_UNKNOWN")
    return _result(observation, ObservationStatus.FRESH, "OBSERVATION_FRESH")


def evaluate_two_stage_provider_state(
    assignment: LiveProviderObservation,
    predispatch: LiveProviderObservation,
    *,
    expected_route: ProviderRouteScope,
    now: str,
    assignment_policy: FreshnessPolicy,
    predispatch_policy: FreshnessPolicy,
    invalidations: tuple[ProviderInvalidation, ...] = (),
) -> ObservationEvaluation:
    assignment_result = evaluate_observation(
        assignment,
        expected_route=expected_route,
        required_stage=ProviderCheckStage.ASSIGNMENT,
        now=now,
        policy=assignment_policy,
        invalidations=invalidations,
    )
    if assignment_result.status is not ObservationStatus.FRESH:
        return assignment_result
    dispatch_result = evaluate_observation(
        predispatch,
        expected_route=expected_route,
        required_stage=ProviderCheckStage.PRE_DISPATCH,
        now=now,
        policy=predispatch_policy,
        invalidations=invalidations,
    )
    if dispatch_result.status is not ObservationStatus.FRESH:
        return dispatch_result
    if _instant(predispatch.observed_at) < _instant(assignment.observed_at):
        return _result(predispatch, ObservationStatus.STALE, "PREDISPATCH_PRECEDES_ASSIGNMENT")
    return ObservationEvaluation(
        ObservationStatus.FRESH,
        "ASSIGNMENT_AND_PREDISPATCH_FRESH",
        predispatch.observation_id,
        (assignment.source_ref, predispatch.source_ref),
    )


def _result(
    observation: LiveProviderObservation,
    status: ObservationStatus,
    reason_code: str,
) -> ObservationEvaluation:
    return ObservationEvaluation(
        status, reason_code, observation.observation_id, (observation.source_ref,)
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
