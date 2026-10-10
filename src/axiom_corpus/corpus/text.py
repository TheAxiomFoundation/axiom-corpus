"""Shared text-normalization helpers for corpus adapters."""

from __future__ import annotations

import unicodedata


def strip_accents(value: str) -> str:
    """Return NFKD-normalized text with combining marks removed."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))
