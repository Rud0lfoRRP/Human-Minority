from __future__ import annotations

from dataclasses import replace

import pytest

from seed.app.providers.contracts import (
    CredentialBackendKind,
    CredentialReference,
    FactAssessment,
    LiveProviderObservation,
    ProviderCheckStage,
    ProviderFact,
    ProviderRouteScope,
)
from seed.app.providers.freshness import (
    FreshnessPolicy,
    ObservationStatus,
    ProviderInvalidation,
    ProviderInvalidationKind,
    evaluate_observation,
    evaluate_two_stage_provider_state,
)


def _route() -> ProviderRouteScope:
    return ProviderRouteScope(
        provider_id="provider-a",
        model_identifier="model-a",
        profile_id="profile-a",
        account_ref=None,
        project_ref=None,
        workspace_ref=None,
        organization_ref=None,
        region_ref=None,
        credential_reference_id="credential:example",
    )


def _fact(name: str, assessment: FactAssessment = FactAssessment.SATISFIED) -> ProviderFact:
    return ProviderFact(
        fact_name=name,
        assessment=assessment,
        provenance_ref=f"evidence:{name}",
    )


def _observation(
    *,
    observation_id: str,
    stage: ProviderCheckStage,
    observed_at: str,
    valid_until: str | None = None,
    facts: tuple[ProviderFact, ...] = (),
) -> LiveProviderObservation:
    return LiveProviderObservation.create(
        observation_id=observation_id,
        route=_route(),
        stage=stage,
        observed_at=observed_at,
        valid_until=valid_until,
        source_ref=f"source:{observation_id}",
        facts=facts,
    )


def test_credential_reference_is_a_stable_lookup_identity_not_secret_material() -> None:
    first = CredentialReference.create(
        provider_id="provider-a",
        backend=CredentialBackendKind.ENVIRONMENT,
        binding_id="env:SEED_TEST_TOKEN",
        account_ref="account-a",
    )
    second = CredentialReference.create(
        provider_id="provider-a",
        backend=CredentialBackendKind.ENVIRONMENT,
        binding_id="env:SEED_TEST_TOKEN",
        account_ref="account-a",
    )
    assert first == second
    assert first.reference_id.startswith("credential:")
    assert first.integrity_valid() is True
    assert "SEED_TEST_TOKEN" in first.persistent_material()["binding_id"]


def test_malformed_credential_reference_integrity_fails_closed() -> None:
    credential = CredentialReference.create(
        provider_id="provider-a",
        backend=CredentialBackendKind.ENVIRONMENT,
        binding_id="env:SEED_TEST_TOKEN",
    )
    assert replace(credential, binding_id="env:\ud800").integrity_valid() is False


def test_credential_reference_rejects_secret_like_binding_material() -> None:
    with pytest.raises(ValueError, match="lookup reference, not secret material"):
        CredentialReference.create(
            provider_id="provider-a",
            backend=CredentialBackendKind.EXTERNAL_SECRET_PROVIDER,
            binding_id="external:token=secret",
        )


def test_live_observation_sorts_facts_and_binds_integrity() -> None:
    observation = _observation(
        observation_id="obs-1",
        stage=ProviderCheckStage.ASSIGNMENT,
        observed_at="2026-09-16T10:00:00Z",
        facts=(_fact("runnable"), _fact("authenticated")),
    )
    assert tuple(fact.fact_name for fact in observation.facts) == (
        "authenticated",
        "runnable",
    )
    assert observation.integrity_valid() is True


def test_noncanonical_observation_material_is_integrity_invalid() -> None:
    observation = _observation(
        observation_id="obs-invalid-unicode",
        stage=ProviderCheckStage.ASSIGNMENT,
        observed_at="2026-09-16T10:00:00Z",
        facts=(_fact("authenticated"),),
    )
    malformed = replace(observation, source_ref="source:\ud800")
    assert malformed.integrity_valid() is False

    result = evaluate_observation(
        malformed,
        expected_route=_route(),
        required_stage=ProviderCheckStage.ASSIGNMENT,
        now="2026-09-16T10:01:00Z",
        policy=FreshnessPolicy(
            max_age_seconds=600,
            required_fact_names=("authenticated",),
        ),
    )
    assert result.status is ObservationStatus.INDETERMINATE
    assert result.reason_code == "OBSERVATION_INTEGRITY_INVALID"


def test_required_fresh_provider_facts_are_accepted() -> None:
    observation = _observation(
        observation_id="obs-1",
        stage=ProviderCheckStage.ASSIGNMENT,
        observed_at="2026-09-16T10:00:00Z",
        valid_until="2026-09-16T10:10:00Z",
        facts=(_fact("authenticated"), _fact("runnable")),
    )
    result = evaluate_observation(
        observation,
        expected_route=_route(),
        required_stage=ProviderCheckStage.ASSIGNMENT,
        now="2026-09-16T10:05:00Z",
        policy=FreshnessPolicy(
            max_age_seconds=600,
            required_fact_names=("authenticated", "runnable"),
        ),
    )
    assert result.status is ObservationStatus.FRESH
    assert result.reason_code == "OBSERVATION_FRESH"


def test_explicit_max_age_expires_observation_even_before_valid_until() -> None:
    observation = _observation(
        observation_id="obs-1",
        stage=ProviderCheckStage.ASSIGNMENT,
        observed_at="2026-09-16T10:00:00Z",
        valid_until="2026-09-16T10:30:00Z",
        facts=(_fact("authenticated"),),
    )
    result = evaluate_observation(
        observation,
        expected_route=_route(),
        required_stage=ProviderCheckStage.ASSIGNMENT,
        now="2026-09-16T10:06:00Z",
        policy=FreshnessPolicy(
            max_age_seconds=300,
            required_fact_names=("authenticated",),
        ),
    )
    assert result.status is ObservationStatus.STALE
    assert result.reason_code == "EXPLICIT_MAX_AGE_EXCEEDED"


def test_unknown_required_fact_is_indeterminate() -> None:
    observation = _observation(
        observation_id="obs-1",
        stage=ProviderCheckStage.ASSIGNMENT,
        observed_at="2026-09-16T10:00:00Z",
        facts=(_fact("authenticated", FactAssessment.UNKNOWN),),
    )
    result = evaluate_observation(
        observation,
        expected_route=_route(),
        required_stage=ProviderCheckStage.ASSIGNMENT,
        now="2026-09-16T10:01:00Z",
        policy=FreshnessPolicy(
            max_age_seconds=600,
            required_fact_names=("authenticated",),
        ),
    )
    assert result.status is ObservationStatus.INDETERMINATE
    assert result.reason_code == "REQUIRED_FACT_UNKNOWN"


def test_post_observation_invalidation_makes_fact_stale_and_preserves_provenance() -> None:
    observation = _observation(
        observation_id="obs-1",
        stage=ProviderCheckStage.ASSIGNMENT,
        observed_at="2026-09-16T10:00:00Z",
        facts=(_fact("authenticated"),),
    )
    result = evaluate_observation(
        observation,
        expected_route=_route(),
        required_stage=ProviderCheckStage.ASSIGNMENT,
        now="2026-09-16T10:05:00Z",
        policy=FreshnessPolicy(
            max_age_seconds=600,
            required_fact_names=("authenticated",),
        ),
        invalidations=(
            ProviderInvalidation(
                kind=ProviderInvalidationKind.CREDENTIAL_CHANGED,
                occurred_at="2026-09-16T10:03:00Z",
                provenance_ref="event:credential-rotated",
            ),
        ),
    )
    assert result.status is ObservationStatus.STALE
    assert result.reason_code == "INVALIDATED_CREDENTIAL_CHANGED"
    assert result.provenance_refs == ("source:obs-1", "event:credential-rotated")


def test_same_instant_invalidation_makes_observation_stale() -> None:
    observation = _observation(
        observation_id="obs-same-instant",
        stage=ProviderCheckStage.ASSIGNMENT,
        observed_at="2026-09-16T10:00:00Z",
        facts=(_fact("authenticated"),),
    )
    result = evaluate_observation(
        observation,
        expected_route=_route(),
        required_stage=ProviderCheckStage.ASSIGNMENT,
        now="2026-09-16T10:00:00Z",
        policy=FreshnessPolicy(
            max_age_seconds=600,
            required_fact_names=("authenticated",),
        ),
        invalidations=(
            ProviderInvalidation(
                kind=ProviderInvalidationKind.CREDENTIAL_CHANGED,
                occurred_at="2026-09-16T10:00:00Z",
                provenance_ref="event:same-instant-credential-change",
            ),
        ),
    )
    assert result.status is ObservationStatus.STALE
    assert result.reason_code == "INVALIDATED_CREDENTIAL_CHANGED"


def test_route_change_invalidation_preserves_source_and_event_provenance() -> None:
    observation = _observation(
        observation_id="obs-route",
        stage=ProviderCheckStage.ASSIGNMENT,
        observed_at="2026-09-16T10:00:00Z",
        facts=(_fact("authenticated"),),
    )
    result = evaluate_observation(
        observation,
        expected_route=_route(),
        required_stage=ProviderCheckStage.ASSIGNMENT,
        now="2026-09-16T10:04:00Z",
        policy=FreshnessPolicy(
            max_age_seconds=600,
            required_fact_names=("authenticated",),
        ),
        invalidations=(
            ProviderInvalidation(
                kind=ProviderInvalidationKind.ROUTE_CHANGED,
                occurred_at="2026-09-16T10:02:00Z",
                provenance_ref="event:route-changed",
            ),
        ),
    )
    assert result.status is ObservationStatus.STALE
    assert result.reason_code == "INVALIDATED_ROUTE_CHANGED"
    assert result.provenance_refs == ("source:obs-route", "event:route-changed")


def test_two_stage_provider_state_requires_assignment_then_predispatch() -> None:
    assignment = _observation(
        observation_id="assignment",
        stage=ProviderCheckStage.ASSIGNMENT,
        observed_at="2026-09-16T10:00:00Z",
        facts=(_fact("authenticated"),),
    )
    predispatch = _observation(
        observation_id="predispatch",
        stage=ProviderCheckStage.PRE_DISPATCH,
        observed_at="2026-09-16T10:01:00Z",
        facts=(_fact("runnable"),),
    )
    result = evaluate_two_stage_provider_state(
        assignment,
        predispatch,
        expected_route=_route(),
        now="2026-09-16T10:02:00Z",
        assignment_policy=FreshnessPolicy(
            max_age_seconds=600,
            required_fact_names=("authenticated",),
        ),
        predispatch_policy=FreshnessPolicy(
            max_age_seconds=600,
            required_fact_names=("runnable",),
        ),
    )
    assert result.status is ObservationStatus.FRESH
    assert result.reason_code == "ASSIGNMENT_AND_PREDISPATCH_FRESH"
