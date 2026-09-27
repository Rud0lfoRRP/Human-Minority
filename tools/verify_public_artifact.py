from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from human_minority.artifact import (  # noqa: E402
    PublicArtifactUnavailableError,
    PublicArtifactVerificationError,
    verify_public_artifact,
)


__all__ = [
    "PublicArtifactUnavailableError",
    "PublicArtifactVerificationError",
    "verify_public_artifact",
]


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    try:
        verify_public_artifact(root)
    except PublicArtifactVerificationError as exc:
        print(f"PUBLIC ARTIFACT VERIFY: FAIL: {exc}", file=sys.stderr)
        return 2
    print("PUBLIC ARTIFACT VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
