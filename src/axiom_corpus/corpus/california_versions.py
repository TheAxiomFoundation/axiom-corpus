"""Concurrent LegInfo versions of one California code section.

California's Legislative Counsel site (LegInfo) can list more than one current
version of a code section. Typically one version becomes inoperative on a
condition and the other becomes operative on the same condition, and both are
listed. ``codes_displaySection.xhtml`` then answers with a
"selectFromMultiples" picker instead of the section. Each picker link posts
three fields back to LegInfo: ``op_statues``, ``op_chapter`` and
``op_section``. They name the statute year, chapter and section of the act
that last added or amended that version. The displayed version page repeats
them in its ``printPopup()`` script and ends with a history note, such as
"Conditionally operative on or after July 1, 2024, by its own provisions."

The corpus gives every concurrent version its own same-number variant path,
``<section>--<slug>`` (``citation_segment.variant_segment``, the convention
the New Mexico, Vermont, Delaware, New Jersey and Alabama statute adapters
use). :func:`leginfo_variant_slug` derives the slug from the version itself:

1. ``inoperative-YYYY-MM-DD``: the note says the version becomes
   (conditionally) inoperative on, or on or after, a date.
2. ``repealed-YYYY-MM-DD``: otherwise, the note says it is repealed on, on or
   after, or as of a date.
3. ``operative-YYYY-MM-DD``: otherwise, the note says it is (conditionally)
   operative on, or on or after, a date.
4. ``stats-<year>[-ch-<chapter>][-sec-<section>]``: otherwise the triple
   itself (:func:`leginfo_act_slug`), labelled with LegInfo's own
   abbreviations. This covers, for example, the identical sections two 2002
   chapters each added to the Revenue and Taxation Code.

The date clauses come first because they name the version's role, and the
role outlives amendments. On 2026-09-25 LegInfo listed WIC 11450's later
version as Stats. 2024, Ch. 798, Sec. 2. On 2026-09-26 it was Stats. 2026,
Ch. 310, Sec. 2 (AB 2765), still "conditionally operative on or after July 1,
2024". A triple-based path would have moved overnight. The slug is a label
taken from LegInfo's note. The note says whether a date is conditional, and
the slug does not say whether the condition has occurred.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup
from bs4.element import Tag

_VALUE_RE = r"[0-9a-z]+(?:\.[0-9a-z]+)*"
_VALUE_FULLMATCH = re.compile(_VALUE_RE)
_ACT_SLUG_RE = re.compile(
    rf"stats-(?P<statues>{_VALUE_RE})"
    rf"(?:-ch-(?P<chapter>{_VALUE_RE}))?"
    rf"(?:-sec-(?P<section>{_VALUE_RE}))?"
)
_ROLE_SLUG_RE = re.compile(r"(?:inoperative|repealed|operative)-\d{4}-\d{2}-\d{2}")
ALL_VERSIONS = "all"
"""Section-spec selector for every version the picker offers (``WIC:11450@all``)."""

_ONCLICK_PARAM_RE = re.compile(r"'([^']+)':'([^']*)'")
_PAGE_VAR_RE = {
    field: re.compile(rf"var\s+{field}\s*=\s*'(?P<value>[^']*)'")
    for field in ("op_statues", "op_chapter", "op_section")
}
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = rf"(?P<date>(?:{_MONTHS}) \d{{1,2}}, \d{{4}})"
_ON = r"(?:on or after |on |as of )?"
_INOPERATIVE_CLAUSE = re.compile(rf"\binoperative {_ON}{_DATE}", re.IGNORECASE)
_REPEALED_CLAUSE = re.compile(rf"\brepealed {_ON}{_DATE}", re.IGNORECASE)
_OPERATIVE_CLAUSE = re.compile(rf"(?<![A-Za-z])operative {_ON}{_DATE}", re.IGNORECASE)
PICKER_COMMAND_PREFIX = "selectFromMultiples:"
VIEW_STATE_FIELD = "javax.faces.ViewState"


@dataclass(frozen=True)
class LegInfoVersion:
    """The ``op_statues``/``op_chapter``/``op_section`` triple of one version."""

    op_statues: str
    op_chapter: str
    op_section: str

    @property
    def act_slug(self) -> str:
        return leginfo_act_slug(self.op_statues, self.op_chapter, self.op_section)

    @property
    def label(self) -> str:
        """LegInfo's own notation for the act, e.g. ``Stats. 2024, Ch. 798, Sec. 2``."""
        parts = [f"Stats. {self.op_statues.strip()}"]
        if self.op_chapter.strip():
            parts.append(f"Ch. {self.op_chapter.strip()}")
        if self.op_section.strip():
            parts.append(f"Sec. {self.op_section.strip()}")
        return ", ".join(parts)

    def same_as(self, other: LegInfoVersion) -> bool:
        return self.normalized() == other.normalized()

    def normalized(self) -> tuple[str, str, str]:
        return (
            self.op_statues.strip().lower(),
            self.op_chapter.strip().lower(),
            self.op_section.strip().lower(),
        )


@dataclass(frozen=True)
class LegInfoPickerLink:
    """One version offered by a ``selectFromMultiples`` picker, in picker order."""

    index: int
    version: LegInfoVersion
    text: str
    command_key: str
    params: tuple[tuple[str, str], ...]

    @property
    def param_map(self) -> dict[str, str]:
        return dict(self.params)


@dataclass(frozen=True)
class LegInfoPicker:
    """A parsed ``form#selectFromMultiples`` page."""

    action: str
    inputs: tuple[tuple[str, str], ...]
    links: tuple[LegInfoPickerLink, ...]

    @property
    def versions(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(link.version.normalized() for link in self.links)

    def post_payload(self, link: LegInfoPickerLink) -> dict[str, str]:
        """The form fields LegInfo's own onclick handler submits for ``link``."""
        return dict(self.inputs) | link.param_map

    def retrieval_fields(self, link: LegInfoPickerLink) -> dict[str, str]:
        """``post_payload`` without the per-request view state token."""
        payload = self.post_payload(link)
        payload.pop(VIEW_STATE_FIELD, None)
        return payload


def _normalized_value(value: str, *, field: str, required: bool) -> str:
    text = value.strip().lower()
    if not text:
        if required:
            raise ValueError(f"LegInfo {field} must not be empty")
        return ""
    if not _VALUE_FULLMATCH.fullmatch(text):
        raise ValueError(f"LegInfo {field} is not a slug-safe value: {value!r}")
    return text


def leginfo_act_slug(op_statues: str, op_chapter: str, op_section: str) -> str:
    """Return the act slug for one LegInfo version triple.

    >>> leginfo_act_slug("2024", "798", "2")
    'stats-2024-ch-798-sec-2'
    >>> leginfo_act_slug("2004", "", "12")
    'stats-2004-sec-12'
    """
    statues = _normalized_value(op_statues, field="op_statues", required=True)
    chapter = _normalized_value(op_chapter, field="op_chapter", required=False)
    section = _normalized_value(op_section, field="op_section", required=False)
    slug = f"stats-{statues}"
    if chapter:
        slug += f"-ch-{chapter}"
    if section:
        slug += f"-sec-{section}"
    return slug


def parse_leginfo_act_slug(slug: str) -> LegInfoVersion:
    """Invert :func:`leginfo_act_slug` (the triple comes back lowercased)."""
    match = _ACT_SLUG_RE.fullmatch(slug.strip().lower())
    if match is None:
        raise ValueError(f"not a LegInfo act slug: {slug!r}")
    return LegInfoVersion(
        op_statues=match.group("statues"),
        op_chapter=match.group("chapter") or "",
        op_section=match.group("section") or "",
    )


def _iso_date(text: str) -> str:
    return datetime.strptime(text, "%B %d, %Y").date().isoformat()


def leginfo_variant_slug(history: str | None, version: LegInfoVersion) -> str:
    """Return the same-number variant slug for one concurrent version.

    See the module docstring for the order of the rules.

    >>> v = LegInfoVersion("2026", "310", "2")
    >>> leginfo_variant_slug("(... Conditionally operative on or after July 1, 2024, by its "
    ...     "own provisions.)", v)
    'operative-2024-07-01'
    >>> leginfo_variant_slug("(Added by Stats. 2002, Ch. 35, Sec. 22. Effective May 8, 2002.)",
    ...     LegInfoVersion("2002", "35", "22"))
    'stats-2002-ch-35-sec-22'
    """
    note = " ".join((history or "").split())
    for prefix, clause in (
        ("inoperative", _INOPERATIVE_CLAUSE),
        ("repealed", _REPEALED_CLAUSE),
        ("operative", _OPERATIVE_CLAUSE),
    ):
        match = clause.search(note)
        if match is not None:
            return f"{prefix}-{_iso_date(match.group('date'))}"
    return version.act_slug


def validate_leginfo_selector(value: str) -> str:
    """Normalize a section-spec version selector: ``all`` or one variant slug."""
    text = value.strip().lower()
    if text == ALL_VERSIONS:
        return text
    if _ROLE_SLUG_RE.fullmatch(text):
        date.fromisoformat(text[-10:])
        return text
    if _ACT_SLUG_RE.fullmatch(text):
        return text
    raise ValueError(
        "LegInfo version selector must be 'all', operative-/inoperative-/repealed-YYYY-MM-DD, "
        f"or stats-<year>[-ch-<chapter>][-sec-<section>]: {value!r}"
    )


def parse_leginfo_picker(html_bytes: bytes) -> LegInfoPicker | None:
    """Parse a LegInfo ``selectFromMultiples`` page, or return ``None``."""
    soup = BeautifulSoup(html_bytes, "html.parser")
    form = soup.find("form", id="selectFromMultiples")
    if not isinstance(form, Tag):
        return None
    inputs: list[tuple[str, str]] = []
    for input_tag in form.find_all("input"):
        name = input_tag.get("name")
        if not isinstance(name, str) or not name:
            continue
        value = input_tag.get("value", "")
        inputs.append((name, value if isinstance(value, str) else ""))
    action = form.get("action")
    action_path = (
        action if isinstance(action, str) and action else "/faces/selectFromMultiples.xhtml"
    )
    links: list[LegInfoPickerLink] = []
    for anchor in form.find_all("a", onclick=re.compile("op_statues")):
        onclick = anchor.get("onclick")
        if not isinstance(onclick, str):
            continue
        params = tuple(_ONCLICK_PARAM_RE.findall(onclick))
        param_map = dict(params)
        command_keys = [key for key in param_map if key.startswith(PICKER_COMMAND_PREFIX)]
        if not command_keys:
            continue
        version = LegInfoVersion(
            op_statues=param_map.get("op_statues", ""),
            op_chapter=param_map.get("op_chapter", ""),
            op_section=param_map.get("op_section", ""),
        )
        links.append(
            LegInfoPickerLink(
                index=len(links),
                version=version,
                text=" ".join(anchor.get_text(" ", strip=True).split()),
                command_key=command_keys[0],
                params=params,
            )
        )
    return LegInfoPicker(action=action_path, inputs=tuple(inputs), links=tuple(links))


def leginfo_page_version(html_bytes: bytes) -> LegInfoVersion | None:
    """Read the displayed version's triple from a LegInfo section page.

    LegInfo writes the triple into the ``printPopup()`` script of every
    ``codes_displaySection`` page (``var op_statues = '2024';`` ...). Returns
    ``None`` when any of the three variables is absent.
    """
    text = html_bytes.decode("utf-8", errors="replace")
    values: dict[str, str] = {}
    for field, pattern in _PAGE_VAR_RE.items():
        match = pattern.search(text)
        if match is None:
            return None
        values[field] = match.group("value")
    return LegInfoVersion(**values)


_INOPERATIVE_RE = re.compile(
    r"\b(?:inoperative|repealed conditionally|conditionally repealed|repealed as of|"
    r"repealed on)\b",
    re.IGNORECASE,
)
_CONDITIONALLY_OPERATIVE_RE = re.compile(
    r"\b(?:conditionally operative|operative on or after)\b", re.IGNORECASE
)


def leginfo_version_status(history: str | None) -> str | None:
    """Map a LegInfo history note to the corpus's variant ``status`` vocabulary.

    The vocabulary is the one the New Mexico, Indiana and Nevada statute
    adapters write: ``effective_until`` for a version whose note says it
    becomes inoperative or is repealed, and ``future_or_conditional`` for one
    whose note says it is conditionally operative or operative on or after a
    date. The mapping reads only the note. It does not decide whether the
    condition has occurred.
    """
    if not history:
        return None
    if _INOPERATIVE_RE.search(history):
        return "effective_until"
    if _CONDITIONALLY_OPERATIVE_RE.search(history):
        return "future_or_conditional"
    return None
