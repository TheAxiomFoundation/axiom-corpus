"""Client for the Lex legislation API (lex.lab.i.ai.gov.uk).

Lex is the DSIT/i.AI service that serves AI-normalised UK legislation text. It
exposes a small REST surface; we use two endpoints:

- ``POST /legislation/lookup`` for act-level metadata (enactment date, provision
  count).
- ``POST /legislation/section/lookup`` for the normalised text of every section
  in an act or statutory instrument.

Section ordering from ``section/lookup`` is not sequential, so a reliable
single-section read needs ``limit`` at least as large as the act's provision
count. The natural unit of retrieval is therefore the whole instrument.
"""

from __future__ import annotations

from datetime import date

import requests
from pydantic import BaseModel

LEX_BASE_URL = "https://lex.lab.i.ai.gov.uk"


class LexLegislation(BaseModel):
    """Act/SI-level metadata from ``/legislation/lookup``."""

    model_config = {"extra": "ignore"}

    id: str
    uri: str = ""
    title: str = ""
    type: str
    year: int
    number: int
    enactment_date: date | None = None
    valid_date: date | None = None
    modified_date: date | None = None
    number_of_provisions: int | None = None

    @property
    def reference_date(self) -> date | None:
        """Best available date for this instrument.

        Statutory instruments carry no enactment date in Lex, so fall back to the
        version's valid (in-force) date, then the last-modified date.
        """
        return self.enactment_date or self.valid_date or self.modified_date


class LexSection(BaseModel):
    """A single provision from ``/legislation/section/lookup``."""

    model_config = {"extra": "ignore"}

    id: str
    uri: str = ""
    title: str = ""
    text: str = ""
    number: int | None = None
    provision_type: str = "section"


class LexClient:
    """Minimal synchronous client for the Lex legislation API."""

    def __init__(self, base_url: str = LEX_BASE_URL, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: dict[str, object]) -> object:
        response = requests.post(
            f"{self.base_url}{path}",
            json=payload,
            headers={"Accept": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def lookup_legislation(self, leg_type: str, year: int, number: int) -> LexLegislation:
        """Fetch act/SI metadata by exact type, year, and number."""
        data = self._post(
            "/legislation/lookup",
            {"legislation_type": leg_type, "year": year, "number": number},
        )
        return LexLegislation.model_validate(data)

    def lookup_sections_raw(self, legislation_id: str, limit: int) -> list[dict[str, object]]:
        """Fetch raw section dicts for an act/SI, preserving Lex provenance fields."""
        data = self._post(
            "/legislation/section/lookup",
            {"legislation_id": legislation_id, "limit": limit},
        )
        if not isinstance(data, list):
            raise ValueError(f"unexpected Lex section payload for {legislation_id}")
        return data
