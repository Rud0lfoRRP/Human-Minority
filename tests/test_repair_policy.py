from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from seed.app.repair.contracts import (
    BudgetSnapshot,
    Diagnosis,
    ExecutorRoute,
    FailureClass,
    ProgressSnapshot,
    ProviderCapacity,
    RepairAction,
    RepairAttemptRecord,
    RepairMode,
    RepairPolicy,
    RepairRequest,
    RepairScopeViolation,
    WatchdogAssessment,
    WatchdogState,
)
from seed.app.repair.policy import (
    append_attempt,
    decide_repair,
    route_diagnosis,
    validate_repair_scope,
)


def _diagnosis() -> Diagnosis:
    return Diagnosis(
        failure_class=FailureClass.CANDIDATE_DEFECT,
        summary="candidate changed behavior incorrectly",
        evidence_ids=("evidence-1",),
        ownership="candidate",
        blast_radius="bounded",
        confirmed=True,
    )


def _request(*, attempt_number: int = 1, candidate_revision: str = "candidate-0") -> RepairRequest:
    return RepairRequest(
        request_id=f"repair-{attempt_number}",
        root_candidate_revision="candidate-0",
        candidate_revision=candidate_revision,
        claim_id="claim-1",
        diagnosis=_diagnosis(),
        acceptance_criteria=("focused check passes",),
        allowed_paths=("src",),
        forbidden_paths=("src/secrets",),
        attempt_number=attempt_number,
        post_repair_verification_plan_id="plan-1",
        required_check_ids=("check-1",),
        mandatory_security_check_ids=("check-1",),
        executor="agent-a",
        provider="provider-a",
        profile="profile-a",
        estimated_cost=Decimal("1.25"),
    )


def _policy(*, mode: RepairMode = RepairMode.AUTO) -> RepairPolicy:
    return RepairPolicy(
        mode=mode,
        max_attempts=3,
        money_cap=Decimal("10"),
        allowed_executors=("agent-a",),
        allowed_providers=("provider-a",),
        allow_automatic_substitution=False,
        no_progress_limit=2,
        deadline=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )


def _budget(*, attempts: int = 0, spent: str = "0") -> BudgetSnapshot:
    return BudgetSnapshot(
        attempts_used=attempts,
        money_spent=Decimal(spent),
        provider_capacity=ProviderCapacity.AVAILABLE,
    )


def _progress(*, no_progress: int = 0, strategy_available: bool = False) -> ProgressSnapshot:
    return ProgressSnapshot(
        consecutive_no_progress=no_progress,
        strategy_change_available=strategy_available,
    )


def _watchdog(state: WatchdogState = WatchdogState.OK) -> WatchdogAssessment:
    return WatchdogAssessment(
        state=state,
        reason="bounded test state",
        evidence_ids=("watchdog-evidence",),
    )


def _route(*, substituted_from: str | None = None, approved: bool = False) -> ExecutorRoute:
    return ExecutorRoute(
        executor="agent-a",
        provider="provider-a",
        profile="profile-a",
        substituted_from=substituted_from,
        substitution_approved=approved,
    )


def test_confirmed_candidate_defect_routes_to_repair_request() -> None:
    assert route_diagnosis(_diagnosis()) is RepairAction.PREPARE_REPAIR_REQUEST


def test_unconfirmed_candidate_defect_requires_more_evidence() -> None:
    diagnosis = Diagnosis(
        failure_class=FailureClass.CANDIDATE_DEFECT,
        summary="not yet proven",
        evidence_ids=("evidence-1",),
        ownership="candidate",
        blast_radius="unknown",
        confirmed=False,
    )
    assert route_diagnosis(diagnosis) is RepairAction.EXPAND_EVIDENCE


def test_scope_accepts_only_allowed_nonforbidden_paths() -> None:
    request = _request()
    validate_repair_scope(request, ("src/main.py", "src/lib/helper.py"))

    with pytest.raises(RepairScopeViolation):
        validate_repair_scope(request, ("tests/outside.py",))
    with pytest.raises(RepairScopeViolation):
        validate_repair_scope(request, ("src/secrets/token.txt",))
    with pytest.raises(RepairScopeViolation):
        validate_repair_scope(request, ("src/../escape.py",))


def test_auto_repair_is_admitted_only_inside_policy_budget() -> None:
    decision = decide_repair(
        _request(),
        policy=_policy(),
        budget=_budget(),
        progress=_progress(),
        watchdog=_watchdog(),
        route=_route(),
        now=datetime(2029, 1, 1, tzinfo=timezone.utc),
    )
    assert decision.action is RepairAction.EXECUTE_REPAIR


def test_money_cap_fails_closed() -> None:
    decision = decide_repair(
        _request(),
        policy=_policy(),
        budget=_budget(spent="9.50"),
        progress=_progress(),
        watchdog=_watchdog(),
        route=_route(),
        now=datetime(2029, 1, 1, tzinfo=timezone.utc),
    )
    assert decision.action is RepairAction.STOP_LIMIT


def test_manual_mode_requires_explicit_approval() -> None:
    blocked = decide_repair(
        _request(),
        policy=_policy(mode=RepairMode.MANUAL),
        budget=_budget(),
        progress=_progress(),
        watchdog=_watchdog(),
        route=_route(),
        manual_approval=False,
        now=datetime(2029, 1, 1, tzinfo=timezone.utc),
    )
    assert blocked.action is RepairAction.REQUIRE_OWNER_APPROVAL

    admitted = decide_repair(
        _request(),
        policy=_policy(mode=RepairMode.MANUAL),
        budget=_budget(),
        progress=_progress(),
        watchdog=_watchdog(),
        route=_route(),
        manual_approval=True,
        now=datetime(2029, 1, 1, tzinfo=timezone.utc),
    )
    assert admitted.action is RepairAction.EXECUTE_REPAIR


def test_critical_watchdog_contains_and_stops() -> None:
    decision = decide_repair(
        _request(),
        policy=_policy(),
        budget=_budget(),
        progress=_progress(),
        watchdog=_watchdog(WatchdogState.CRITICAL),
        route=_route(),
        now=datetime(2029, 1, 1, tzinfo=timezone.utc),
    )
    assert decision.action is RepairAction.CONTAIN_AND_STOP


def test_no_progress_requires_bounded_strategy_change_or_escalation() -> None:
    adaptable = decide_repair(
        _request(),
        policy=_policy(),
        budget=_budget(),
        progress=_progress(no_progress=2, strategy_available=True),
        watchdog=_watchdog(),
        route=_route(),
        now=datetime(2029, 1, 1, tzinfo=timezone.utc),
    )
    assert adaptable.action is RepairAction.ADAPT_STRATEGY

    exhausted = decide_repair(
        _request(),
        policy=_policy(),
        budget=_budget(),
        progress=_progress(no_progress=2, strategy_available=False),
        watchdog=_watchdog(),
        route=_route(),
        now=datetime(2029, 1, 1, tzinfo=timezone.utc),
    )
    assert exhausted.action is RepairAction.ESCALATE_NO_PROGRESS


def _record(
    *,
    attempt_number: int,
    parent: str,
    produced: str,
    request_id: str,
) -> RepairAttemptRecord:
    return RepairAttemptRecord(
        attempt_id=f"attempt-{attempt_number}",
        attempt_number=attempt_number,
        root_candidate_revision="candidate-0",
        parent_candidate_revision=parent,
        produced_candidate_revision=produced,
        request_id=request_id,
        candidate_claim_id="claim-1",
        raw_execution_evidence_ids=(f"execution-{attempt_number}",),
        verification_plan_id="plan-1",
        completed_check_ids=("check-1",),
        mandatory_security_check_ids=("check-1",),
        verification_result_ids=(f"result-{attempt_number}",),
        mandatory_security_result_ids=(f"result-{attempt_number}",),
        estimated_cost=Decimal("1.25"),
        actual_cost=Decimal("1.00"),
        final_control_decision_id=f"decision-{attempt_number}",
    )


def test_attempt_lineage_extends_exact_parent_chain() -> None:
    first_request = _request(attempt_number=1, candidate_revision="candidate-0")
    first = _record(
        attempt_number=1,
        parent="candidate-0",
        produced="candidate-1",
        request_id=first_request.request_id,
    )
    history = append_attempt((), first, first_request)
    assert history == (first,)

    second_request = _request(attempt_number=2, candidate_revision="candidate-1")
    second = _record(
        attempt_number=2,
        parent="candidate-1",
        produced="candidate-2",
        request_id=second_request.request_id,
    )
    history = append_attempt(history, second, second_request)
    assert history == (first, second)


def test_attempt_lineage_rejects_wrong_parent() -> None:
    request = _request(attempt_number=1, candidate_revision="candidate-0")
    record = _record(
        attempt_number=1,
        parent="not-the-request-candidate",
        produced="candidate-1",
        request_id=request.request_id,
    )
    with pytest.raises(ValueError, match="parent candidate"):
        append_attempt((), record, request)
