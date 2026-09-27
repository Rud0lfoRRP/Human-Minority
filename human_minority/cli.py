"""Human Minority public product CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence, TextIO

from seed.app.verification.vertical import PublicVerificationError, verify_bundle_files

from ._version import __version__, build_revision
from .artifact import (
    PublicArtifactUnavailableError,
    PublicArtifactVerificationError,
    verify_public_artifact,
)
from .result import HumanMinorityCliResult, write_result


class HumanMinorityCliUsageError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise HumanMinorityCliUsageError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="human-minority",
        description=(
            "Inspect the published Human Minority artifact or evaluate one exact "
            "candidate against a portable verification bundle."
        ),
    )
    parser.add_argument("--version", action="store_true", help="show product version")
    parser.add_argument("--json", action="store_true", dest="json_output")
    subparsers = parser.add_subparsers(dest="command")

    inspect = subparsers.add_parser(
        "inspect",
        help="verify integrity and report facts for the current public checkout",
    )
    inspect.add_argument("--json", action="store_true", dest="json_output", default=argparse.SUPPRESS)

    verify = subparsers.add_parser(
        "verify",
        help="evaluate an exact candidate against a strict public verification bundle",
    )
    verify.add_argument("--candidate", type=Path, required=True)
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--expected-sha256")
    verify.add_argument("--json", action="store_true", dest="json_output", default=argparse.SUPPRESS)
    return parser


def _json_requested(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json_output", False))


def _run_version(args: argparse.Namespace, *, stdout: TextIO) -> int:
    revision = build_revision()
    write_result(
        HumanMinorityCliResult(
            command="human-minority --version",
            status="OK",
            facts={
                "product_version": __version__,
                "build_revision": revision if revision is not None else "UNKNOWN",
            },
        ),
        stream=stdout,
        json_output=_json_requested(args),
    )
    return 0


def _run_inspect(args: argparse.Namespace, *, stdout: TextIO) -> int:
    try:
        report = verify_public_artifact(Path.cwd())
    except PublicArtifactUnavailableError as exc:
        write_result(
            HumanMinorityCliResult(
                command="human-minority inspect",
                status="UNAVAILABLE",
                errors=(str(exc),),
            ),
            stream=stdout,
            json_output=_json_requested(args),
        )
        return 3
    except PublicArtifactVerificationError as exc:
        write_result(
            HumanMinorityCliResult(
                command="human-minority inspect",
                status="DRIFTED",
                facts={"integrity": "FAIL"},
                errors=(str(exc),),
            ),
            stream=stdout,
            json_output=_json_requested(args),
        )
        return 1

    warnings = [
        (
            "Integrity PASS validates committed HEAD against its committed manifest; "
            "compare public_commit and manifest_sha256 with a trusted published "
            "reference to establish authenticity."
        )
    ]
    if not report.working_tree_clean:
        warnings.append(
            "Working tree differs from committed HEAD; integrity PASS does not "
            "cover uncommitted or untracked files."
        )
    write_result(
        HumanMinorityCliResult(
            command="human-minority inspect",
            status="OK",
            facts={
                "product_version": __version__,
                "public_commit": report.public_commit,
                "manifest_sha256": report.manifest_sha256,
                "artifact_stage": report.artifact_stage,
                "boundary_document": report.boundary_document,
                "tracked_file_count": report.tracked_file_count,
                "integrity": "PASS",
                "integrity_scope": "COMMITTED_HEAD",
                "working_tree_clean": report.working_tree_clean,
                "authenticity": "NOT_ESTABLISHED",
            },
            warnings=tuple(warnings),
        ),
        stream=stdout,
        json_output=_json_requested(args),
    )
    return 0


def _run_verify(args: argparse.Namespace, *, stdout: TextIO) -> int:
    try:
        result = verify_bundle_files(
            candidate_path=args.candidate,
            bundle_path=args.bundle,
            expected_candidate_sha256=args.expected_sha256,
        )
    except PublicVerificationError as exc:
        write_result(
            HumanMinorityCliResult(
                command="human-minority verify",
                status="INPUT_REJECTED",
                errors=(str(exc),),
            ),
            stream=stdout,
            json_output=_json_requested(args),
        )
        return 2

    outcome = result.decision.outcome.value
    write_result(
        HumanMinorityCliResult(
            command="human-minority verify",
            status=outcome,
            facts={"verification": result.output()},
        ),
        stream=stdout,
        json_output=_json_requested(args),
    )
    return 0 if outcome == "ACCEPT" else 1


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = sys.stdout if stdout is None else stdout
    error = sys.stderr if stderr is None else stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
        if args.version:
            if args.command is not None:
                raise HumanMinorityCliUsageError("--version cannot be combined with a command")
            return _run_version(args, stdout=output)
        if args.command == "inspect":
            return _run_inspect(args, stdout=output)
        if args.command == "verify":
            return _run_verify(args, stdout=output)
        parser.print_help(file=output)
        return 2
    except HumanMinorityCliUsageError as exc:
        error.write(f"human-minority: {exc}\n")
        error.flush()
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception:
        error.write("human-minority: internal failure\n")
        error.flush()
        return 5
