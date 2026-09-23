"""Pure diagnosis routing, admission, scope, and lineage policy for bounded repair."""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction

from seed.app.core.errors import CommandError
from seed.app.source.portable_paths import portable_key

from .contracts import (
    BudgetSnapshot,
    Diagnosis,
    ExecutorRoute,
    FailureClass,
    ProgressSnapshot,
    ProviderCapacity,
    RepairAction,
    RepairAttemptRecord,
    RepairDecision,
    RepairMode,
    RepairPolicy,
    RepairRequest,
    RepairScopeViolation,
    WatchdogAssessment,
    WatchdogState,
    normalize_repo_path,
)


_DIAGNOSIS_ROUTES = {
    FailureClass.VERIFICATION_INSUFFICIENCY: RepairAction.EXPAND_EVIDENCE,
    FailureClass.CHECK_DEFECT: RepairAction.REVISE_VERIFICATION_PLAN,
    FailureClass.ENVIRONMENT_FAILURE: RepairAction.RECOVER_INFRASTRUCTURE,
    FailureClass.PROVIDER_FAILURE: RepairAction.WAIT_OR_REROUTE,
    FailureClass.AUTHORIZATION_FAILURE: RepairAction.ESCALATE_POLICY,
    FailureClass.TASK_AMBIGUITY: RepairAction.CLARIFY_INTENT,
    FailureClass.SECURITY_CRITICAL: RepairAction.CONTAIN_AND_STOP,
    FailureClass.UPSTREAM_FAILURE: RepairAction.WAIT_UPSTREAM,
    FailureClass.UNKNOWN: RepairAction.EXPAND_EVIDENCE,
}


def route_diagnosis(diagnosis: Diagnosis) -> RepairAction:
    """Choose an action class before any RepairRequest can authorize mutation."""

    if diagnosis.failure_class is FailureClass.CANDIDATE_DEFECT:
        if diagnosis.confirmed:
            return RepairAction.PREPARE_REPAIR_REQUEST
        return RepairAction.EXPAND_EVIDENCE
    return _DIAGNOSIS_ROUTES[diagnosis.failure_class]


def decide_repair(
    request: RepairRequest,
    *,
    policy: RepairPolicy,
    budget: BudgetSnapshot,
    progress: ProgressSnapshot,
    watchdog: WatchdogAssessment,
    route: ExecutorRoute,
    manual_approval: bool = False,
    now: datetime | None = None,
) -> RepairDecision:
    """Admit one repair attempt without executing an agent, provider, or check."""

    if watchdog.state is WatchdogState.CRITICAL:
        return _decision(RepairAction.CONTAIN_AND_STOP, "critical watchdog condition")
    if budget.attempts_used >= policy.max_attempts or request.attempt_number > policy.max_attempts:
        return _decision(RepairAction.STOP_LIMIT, "attempt cap reached")
    if request.attempt_number != budget.attempts_used + 1:
        return _decision(RepairAction.ESCALATE_POLICY, "attempt sequence is inconsistent")
    if _exact_decimal_sum_exceeds(
        budget.money_spent,
        request.estimated_cost,
        policy.money_cap,
    ):
        return _decision(RepairAction.STOP_LIMIT, "money cap would be exceeded")
    if policy.deadline is not None:
        if now is None:
            return _decision(RepairAction.ESCALATE_POLICY, "deadline cannot be evaluated")
        if now.tzinfo is None:
            return _decision(RepairAction.ESCALATE_POLICY, "deadline clock is not timezone-aware")
        if now >= policy.deadline:
            return _decision(RepairAction.STOP_LIMIT, "explicit deadline reached")
    if budget.provider_capacity is not ProviderCapacity.AVAILABLE:
        return _decision(RepairAction.WAIT_OR_REROUTE, "provider capacity unavailable or unknown")
    if route.executor not in policy.allowed_executors or route.provider not in policy.allowed_providers:
        return _decision(RepairAction.ESCALATE_POLICY, "executor or provider is outside policy")
    if route.substituted_from is None:
        if (route.executor, route.provider, route.profile) != (
            request.executor,
            request.provider,
            request.profile,
        ):
            return _decision(RepairAction.ESCALATE_POLICY, "route does not match RepairRequest")
    else:
        if route.substituted_from != request.executor:
            return _decision(RepairAction.ESCALATE_POLICY, "substitution origin does not match")
        if route.profile != request.profile and not route.substitution_approved:
            return _decision(
                RepairAction.REQUIRE_OWNER_APPROVAL,
                "substitution profile change requires explicit approval",
            )
        if not (route.substitution_approved or policy.allow_automatic_substitution):
            return _decision(RepairAction.REQUIRE_OWNER_APPROVAL, "substitution is not authorized")
    if progress.consecutive_no_progress >= policy.no_progress_limit:
        if progress.strategy_change_available:
            return _decision(RepairAction.ADAPT_STRATEGY, "no progress requires bounded strategy change")
        return _decision(RepairAction.ESCALATE_NO_PROGRESS, "no progress persists")
    if watchdog.state is WatchdogState.WARNING_DEGRADED:
        return _decision(RepairAction.ADAPT_STRATEGY, "watchdog requires adaptation")
    if policy.mode is RepairMode.MANUAL:
        if type(manual_approval) is not bool:
            return _decision(
                RepairAction.REQUIRE_OWNER_APPROVAL,
                "manual approval must be an explicit boolean",
            )
        if not manual_approval:
            return _decision(RepairAction.REQUIRE_OWNER_APPROVAL, "manual approval required")
    return _decision(RepairAction.EXECUTE_REPAIR, "repair is inside the authorized envelope")


def validate_repair_scope(request: RepairRequest, changed_paths: tuple[str, ...]) -> None:
    """Fail closed if a produced candidate escapes the request's path envelope."""

    allowed_exact = tuple(normalize_repo_path(path) for path in request.allowed_paths)
    allowed_portable = tuple(portable_key(path) for path in allowed_exact)
    forbidden = tuple(portable_key(path) for path in request.forbidden_paths)
    for raw_path in changed_paths:
        try:
            exact_path = normalize_repo_path(raw_path)
            portable_path = portable_key(exact_path)
        except (ValueError, CommandError) as error:
            raise RepairScopeViolation("changed path is not a portable repository path") from error
        if any(_within(portable_path, boundary) for boundary in forbidden):
            raise RepairScopeViolation("changed path intersects forbidden scope")
        if any(_within(exact_path, boundary) for boundary in allowed_exact):
            continue
        if any(_within(portable_path, boundary) for boundary in allowed_portable):
            raise RepairScopeViolation(
                "changed path matches allowed scope only by case or Unicode alias"
            )
        raise RepairScopeViolation("changed path is outside allowed scope")


def append_attempt(
    history: tuple[RepairAttemptRecord, ...],
    record: RepairAttemptRecord,
    request: RepairRequest,
) -> tuple[RepairAttemptRecord, ...]:
    """Return a new lineage tuple after validating the exact immutable chain."""

    expected_number = len(history) + 1
    if request.attempt_number != expected_number or record.attempt_number != expected_number:
        raise ValueError("attempt number does not extend lineage")
    if record.request_id != request.request_id:
        raise ValueError("attempt request id does not match RepairRequest")
    if record.root_candidate_revision != request.root_candidate_revision:
        raise ValueError("attempt root candidate does not match RepairRequest")
    if record.parent_candidate_revision != request.candidate_revision:
        raise ValueError("attempt parent candidate does not match RepairRequest")
    if record.verification_plan_id != request.post_repair_verification_plan_id:
        raise ValueError("attempt verification plan does not match RepairRequest")
    if set(record.completed_check_ids) != set(request.required_check_ids):
        raise ValueError("attempt did not complete all required checks")
    if set(record.mandatory_security_check_ids) != set(request.mandatory_security_check_ids):
        raise ValueError("attempt mandatory security checks do not match RepairRequest")
    if record.estimated_cost != request.estimated_cost:
        raise ValueError("attempt estimated cost does not match RepairRequest")
    if any(item.attempt_id == record.attempt_id for item in history):
        raise ValueError("attempt id must be unique")
    if history:
        previous = history[-1]
        if previous.produced_candidate_revision != record.parent_candidate_revision:
            raise ValueError("attempt parent candidate does not extend prior candidate")
        if previous.root_candidate_revision != record.root_candidate_revision:
            raise ValueError("attempt root candidate must remain stable")
    return (*history, record)


def _exact_decimal_sum_exceeds(spent, estimated, cap) -> bool:
    """Compare Decimal amounts exactly, independent of ambient Decimal context."""

    return Fraction(spent) + Fraction(estimated) > Fraction(cap)


def _within(path: str, boundary: str) -> bool:
    return path == boundary or path.startswith(boundary + "/")


def _decision(action: RepairAction, reason: str) -> RepairDecision:
    return RepairDecision(action=action, reasons=(reason,))
