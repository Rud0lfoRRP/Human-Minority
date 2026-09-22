"""Immutable, provider-neutral contracts for bounded repair policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import PurePosixPath


class FailureClass(Enum):
    CANDIDATE_DEFECT = "CANDIDATE_DEFECT"
    VERIFICATION_INSUFFICIENCY = "VERIFICATION_INSUFFICIENCY"
    CHECK_DEFECT = "CHECK_DEFECT"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    AUTHORIZATION_FAILURE = "AUTHORIZATION_FAILURE"
    TASK_AMBIGUITY = "TASK_AMBIGUITY"
    SECURITY_CRITICAL = "SECURITY_CRITICAL"
    UPSTREAM_FAILURE = "UPSTREAM_FAILURE"
    UNKNOWN = "UNKNOWN"


class RepairAction(Enum):
    PREPARE_REPAIR_REQUEST = "PREPARE_REPAIR_REQUEST"
    EXPAND_EVIDENCE = "EXPAND_EVIDENCE"
    REVISE_VERIFICATION_PLAN = "REVISE_VERIFICATION_PLAN"
    RECOVER_INFRASTRUCTURE = "RECOVER_INFRASTRUCTURE"
    WAIT_OR_REROUTE = "WAIT_OR_REROUTE"
    ESCALATE_POLICY = "ESCALATE_POLICY"
    CLARIFY_INTENT = "CLARIFY_INTENT"
    CONTAIN_AND_STOP = "CONTAIN_AND_STOP"
    WAIT_UPSTREAM = "WAIT_UPSTREAM"
    REQUIRE_OWNER_APPROVAL = "REQUIRE_OWNER_APPROVAL"
    EXECUTE_REPAIR = "EXECUTE_REPAIR"
    STOP_LIMIT = "STOP_LIMIT"
    ADAPT_STRATEGY = "ADAPT_STRATEGY"
    ESCALATE_NO_PROGRESS = "ESCALATE_NO_PROGRESS"


class RepairMode(Enum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"


class ProviderCapacity(Enum):
    AVAILABLE = "AVAILABLE"
    EXHAUSTED = "EXHAUSTED"
    UNKNOWN = "UNKNOWN"


class WatchdogState(Enum):
    OK = "OK"
    WARNING_DEGRADED = "WARNING_DEGRADED"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Diagnosis:
    failure_class: FailureClass
    summary: str
    evidence_ids: tuple[str, ...]
    ownership: str
    blast_radius: str
    confirmed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.failure_class, FailureClass):
            raise ValueError("failure_class must be a FailureClass")
        if type(self.confirmed) is not bool:
            raise ValueError("confirmed must be a boolean")
        _require_text(self.summary, "diagnosis summary")
        _require_unique_text(self.evidence_ids, "diagnosis evidence")
        _require_text(self.ownership, "diagnosis ownership")
        _require_text(self.blast_radius, "diagnosis blast radius")


@dataclass(frozen=True)
class RepairRequest:
    request_id: str
    root_candidate_revision: str
    candidate_revision: str
    claim_id: str
    diagnosis: Diagnosis
    acceptance_criteria: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    attempt_number: int
    post_repair_verification_plan_id: str
    required_check_ids: tuple[str, ...]
    mandatory_security_check_ids: tuple[str, ...]
    executor: str
    provider: str
    profile: str
    estimated_cost: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.diagnosis, Diagnosis):
            raise ValueError("diagnosis must be a Diagnosis")
        for name, value in (
            ("request_id", self.request_id),
            ("root_candidate_revision", self.root_candidate_revision),
            ("candidate_revision", self.candidate_revision),
            ("claim_id", self.claim_id),
            ("post_repair_verification_plan_id", self.post_repair_verification_plan_id),
            ("executor", self.executor),
            ("provider", self.provider),
            ("profile", self.profile),
        ):
            _require_text(value, name)
        if self.diagnosis.failure_class is not FailureClass.CANDIDATE_DEFECT or not self.diagnosis.confirmed:
            raise ValueError("RepairRequest requires a confirmed candidate defect")
        _require_unique_text(self.acceptance_criteria, "acceptance criteria")
        if not self.allowed_paths:
            raise ValueError("allowed_paths must not be empty")
        _require_unique_paths(self.allowed_paths, "allowed_paths")
        _require_unique_paths(self.forbidden_paths, "forbidden_paths", allow_empty=True)
        if type(self.attempt_number) is not int or self.attempt_number <= 0:
            raise ValueError("attempt_number must be a positive integer")
        _require_unique_text(self.required_check_ids, "required checks")
        _require_unique_text(self.mandatory_security_check_ids, "mandatory security checks")
        if not set(self.mandatory_security_check_ids).issubset(self.required_check_ids):
            raise ValueError("mandatory security checks must be a subset of required checks")
        _require_nonnegative_decimal(self.estimated_cost, "estimated_cost")


@dataclass(frozen=True)
class RepairPolicy:
    mode: RepairMode
    max_attempts: int
    money_cap: Decimal
    allowed_executors: tuple[str, ...]
    allowed_providers: tuple[str, ...]
    allow_automatic_substitution: bool
    no_progress_limit: int
    deadline: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, RepairMode):
            raise ValueError("mode must be a RepairMode")
        if type(self.max_attempts) is not int or self.max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")
        _require_nonnegative_decimal(self.money_cap, "money_cap")
        if self.money_cap == 0:
            raise ValueError("money_cap must be positive")
        _require_unique_text(self.allowed_executors, "allowed executors")
        _require_unique_text(self.allowed_providers, "allowed providers")
        if type(self.allow_automatic_substitution) is not bool:
            raise ValueError("allow_automatic_substitution must be a boolean")
        if type(self.no_progress_limit) is not int or self.no_progress_limit <= 0:
            raise ValueError("no_progress_limit must be a positive integer")
        if self.deadline is not None and self.deadline.tzinfo is None:
            raise ValueError("deadline must be timezone-aware")


@dataclass(frozen=True)
class BudgetSnapshot:
    attempts_used: int
    money_spent: Decimal
    provider_capacity: ProviderCapacity

    def __post_init__(self) -> None:
        if not isinstance(self.provider_capacity, ProviderCapacity):
            raise ValueError("provider_capacity must be a ProviderCapacity")
        if type(self.attempts_used) is not int or self.attempts_used < 0:
            raise ValueError("attempts_used must be a non-negative integer")
        _require_nonnegative_decimal(self.money_spent, "money_spent")


@dataclass(frozen=True)
class ProgressSnapshot:
    consecutive_no_progress: int
    strategy_change_available: bool

    def __post_init__(self) -> None:
        if type(self.consecutive_no_progress) is not int or self.consecutive_no_progress < 0:
            raise ValueError("consecutive_no_progress must be a non-negative integer")
        if type(self.strategy_change_available) is not bool:
            raise ValueError("strategy_change_available must be a boolean")


@dataclass(frozen=True)
class WatchdogAssessment:
    state: WatchdogState
    reason: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.state, WatchdogState):
            raise ValueError("state must be a WatchdogState")
        _require_text(self.reason, "watchdog reason")
        _require_unique_text(self.evidence_ids, "watchdog evidence")


@dataclass(frozen=True)
class ExecutorRoute:
    executor: str
    provider: str
    profile: str
    substituted_from: str | None
    substitution_approved: bool

    def __post_init__(self) -> None:
        _require_text(self.executor, "route executor")
        _require_text(self.provider, "route provider")
        _require_text(self.profile, "route profile")
        if self.substituted_from is not None:
            _require_text(self.substituted_from, "substituted_from")
        if type(self.substitution_approved) is not bool:
            raise ValueError("substitution_approved must be a boolean")


@dataclass(frozen=True)
class RepairDecision:
    action: RepairAction
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.action, RepairAction):
            raise ValueError("action must be a RepairAction")
        _require_unique_text(self.reasons, "repair decision reasons")


@dataclass(frozen=True)
class RepairAttemptRecord:
    attempt_id: str
    attempt_number: int
    root_candidate_revision: str
    parent_candidate_revision: str
    produced_candidate_revision: str
    request_id: str
    candidate_claim_id: str
    raw_execution_evidence_ids: tuple[str, ...]
    verification_plan_id: str
    completed_check_ids: tuple[str, ...]
    mandatory_security_check_ids: tuple[str, ...]
    verification_result_ids: tuple[str, ...]
    mandatory_security_result_ids: tuple[str, ...]
    estimated_cost: Decimal
    actual_cost: Decimal | None
    final_control_decision_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("attempt_id", self.attempt_id),
            ("root_candidate_revision", self.root_candidate_revision),
            ("parent_candidate_revision", self.parent_candidate_revision),
            ("produced_candidate_revision", self.produced_candidate_revision),
            ("request_id", self.request_id),
            ("candidate_claim_id", self.candidate_claim_id),
            ("verification_plan_id", self.verification_plan_id),
            ("final_control_decision_id", self.final_control_decision_id),
        ):
            _require_text(value, name)
        if type(self.attempt_number) is not int or self.attempt_number <= 0:
            raise ValueError("attempt_number must be a positive integer")
        if self.produced_candidate_revision == self.parent_candidate_revision:
            raise ValueError("repair attempt must produce a new candidate")
        _require_unique_text(self.raw_execution_evidence_ids, "raw execution evidence")
        _require_unique_text(self.completed_check_ids, "completed checks")
        _require_unique_text(self.mandatory_security_check_ids, "mandatory security checks")
        if not set(self.mandatory_security_check_ids).issubset(self.completed_check_ids):
            raise ValueError("mandatory security checks must be a subset of completed checks")
        _require_unique_text(self.verification_result_ids, "verification results")
        _require_unique_text(self.mandatory_security_result_ids, "mandatory security results")
        if not set(self.mandatory_security_result_ids).issubset(self.verification_result_ids):
            raise ValueError("mandatory security results must be a subset of verification results")
        if len(self.verification_result_ids) != len(self.completed_check_ids):
            raise ValueError("verification results must correspond to completed checks")
        if len(self.mandatory_security_result_ids) != len(self.mandatory_security_check_ids):
            raise ValueError("mandatory security results must correspond to mandatory security checks")
        _require_nonnegative_decimal(self.estimated_cost, "estimated_cost")
        if self.actual_cost is not None:
            _require_nonnegative_decimal(self.actual_cost, "actual_cost")


class RepairScopeViolation(ValueError):
    """A produced diff escaped the exact RepairRequest path envelope."""


def normalize_repo_path(path: str) -> str:
    _require_text(path, "repository path")
    if "\\" in path:
        raise ValueError("repository path must use POSIX separators")
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() in {"", "."}:
        raise ValueError("repository path must be normalized and relative")
    if pure.parts and ":" in pure.parts[0]:
        raise ValueError("repository path must not be a drive path")
    normalized = pure.as_posix()
    if normalized != path:
        raise ValueError("repository path must already be normalized")
    return normalized


def _require_unique_paths(values: tuple[str, ...], name: str, *, allow_empty: bool = False) -> None:
    if not values and not allow_empty:
        raise ValueError(f"{name} must not be empty")
    normalized = tuple(normalize_repo_path(value) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must be unique")


def _require_unique_text(values: tuple[str, ...], name: str) -> None:
    if not values:
        raise ValueError(f"{name} must not be empty")
    for value in values:
        _require_text(value, name)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _require_text(value: object, name: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a non-empty plain string")


def _require_nonnegative_decimal(value: object, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a finite non-negative Decimal")
