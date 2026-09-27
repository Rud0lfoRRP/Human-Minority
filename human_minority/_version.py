"""Canonical Human Minority product version identity."""

from __future__ import annotations

import os

PRODUCT_NAME = "human-minority"
__version__ = "0.0.0.dev0"


def build_revision() -> str | None:
    value = os.environ.get("HUMAN_MINORITY_BUILD_REVISION")
    if value is None:
        return None
    value = value.strip()
    return value or None
