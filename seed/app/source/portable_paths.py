"""Exact ``seed-portable-path-v1`` normalization shared by Source and Freeze."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from seed.app.core.errors import CommandError, CoreErrorCode


_WINDOWS_INVALID = set('<>:"|?*')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


def _admission(message: str) -> CommandError:
    return CommandError(CoreErrorCode.ADMISSION_INVALID, message)


def canonical_path(value: Any) -> str:
    """Return the existing portable relative path or its exact admission error."""

    if type(value) is not str:
        raise _admission("manifest path must be a plain string")
    path = unicodedata.normalize("NFC", value)
    if (
        not path
        or path.startswith("/")
        or re.match(r"^[A-Za-z]:", path)
        or "\\" in path
        or path.endswith("/")
    ):
        raise _admission("manifest path is not portable and relative")
    segments = path.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise _admission("manifest path contains an invalid segment")
    for segment in segments:
        if (
            segment.endswith((".", " "))
            or any(ord(character) < 32 or ord(character) == 127 for character in segment)
            or any(character in _WINDOWS_INVALID for character in segment)
            or segment.split(".", 1)[0].casefold().upper() in _RESERVED
        ):
            raise _admission("manifest path violates seed-portable-path-v1")
    return path


def portable_key(path: str) -> str:
    """Return the existing case-folded collision key for one canonical path."""

    return "/".join(segment.casefold() for segment in canonical_path(path).split("/"))
