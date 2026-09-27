"""Stable Human Minority CLI result envelope."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Mapping, Sequence


RESULT_SCHEMA_VERSION = "seed-cli-result-v1"


@dataclass(frozen=True)
class HumanMinorityCliResult:
    command: str
    status: str
    facts: Mapping[str, object] = field(default_factory=dict)
    warnings: Sequence[str] = ()
    errors: Sequence[str] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "command": self.command,
            "status": self.status,
            "facts": dict(self.facts),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    def render_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def render_human(self) -> str:
        lines = [f"{self.command}: {self.status}"]
        for key in sorted(self.facts):
            value = self.facts[key]
            if isinstance(value, (dict, list, tuple)):
                rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
            else:
                rendered = str(value)
            lines.append(f"{key}: {rendered}")
        for warning in self.warnings:
            lines.append(f"warning: {warning}")
        for error in self.errors:
            lines.append(f"error: {error}")
        return "\n".join(lines)


def write_result(result: HumanMinorityCliResult, *, stream, json_output: bool) -> None:
    stream.write(result.render_json() if json_output else result.render_human())
    stream.write("\n")
    stream.flush()
