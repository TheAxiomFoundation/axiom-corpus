"""Sectioning of monolithic document bodies into child provisions.

Captured policy documents (tax forms, guides, worksheets) often carry
their own printed structure — ``Part 1 – …``, ``Step 2 – …``,
``Schedule 3 …`` — but a scaffolded scope lands as ONE document-level
provision holding the entire capture. The app then has no child nodes
to navigate into, unlike statutes where every subsection is a node.

``split_document_body`` turns such a body into an intro plus one
section per top-level marker, preserving text exactly: the intro and
section bodies are contiguous slices whose concatenation reproduces
the original body byte-for-byte. Repeated ``(continued)`` headings of
the current section merge into it; a marker that repeats
non-consecutively (a capture concatenating several forms, e.g. one
Schedule 6 per province) makes the body unsplittable and returns
``None`` — splitting those on section markers would interleave
unrelated forms.

Consumed by the ``section-provisions`` CLI command (rewrites a scope's
provisions jsonl) and by release validation, which warns when a
document-level provision could be sectioned but has not been.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Ordered by preference: the first family with at least two distinct
# markers wins. Families must be top-level printed section headings;
# table artifacts like ``Column 1`` repeat per row and never form a
# navigable outline, so they are deliberately absent.
_MARKER_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("part", re.compile(r"(?m)^(Part (\d+)[^\n]*)$")),
    ("step", re.compile(r"(?m)^(Step (\d+)[^\n]*)$")),
    ("schedule", re.compile(r"(?m)^(Schedule (\d+)[^\n]*)$")),
)

_CONTINUED_SUFFIX = re.compile(r"\s*\(continued\)\s*$")


@dataclass(frozen=True)
class DocumentSection:
    slug: str
    heading: str
    body: str


@dataclass(frozen=True)
class DocumentSplit:
    intro: str
    sections: tuple[DocumentSection, ...]


def split_document_body(body: str) -> DocumentSplit | None:
    """Split ``body`` on its own top-level section markers.

    Returns ``None`` when the body has no usable structure: fewer than
    two distinct markers in every family, or a marker family whose
    numbers repeat non-consecutively (concatenated sibling forms).
    """
    for family, pattern in _MARKER_FAMILIES:
        matches = list(pattern.finditer(body))
        distinct = {f"{family}-{m.group(2)}" for m in matches}
        if len(distinct) < 2:
            continue
        return _split_on_markers(body, family, matches)
    return None


def _split_on_markers(
    body: str,
    family: str,
    matches: list[re.Match[str]],
) -> DocumentSplit | None:
    starts: list[tuple[str, str, int]] = []  # (slug, heading, offset)
    seen: set[str] = set()
    for match in matches:
        slug = f"{family}-{match.group(2)}"
        if starts and starts[-1][0] == slug:
            # "(continued)" run of the section already open — no cut.
            continue
        if slug in seen:
            return None
        seen.add(slug)
        heading = _CONTINUED_SUFFIX.sub("", match.group(1).strip())
        starts.append((slug, heading, match.start()))
    intro = body[: starts[0][2]]
    sections: list[DocumentSection] = []
    for i, (slug, heading, offset) in enumerate(starts):
        end = starts[i + 1][2] if i + 1 < len(starts) else len(body)
        sections.append(DocumentSection(slug=slug, heading=heading, body=body[offset:end]))
    reassembled = intro + "".join(section.body for section in sections)
    if reassembled != body:
        raise AssertionError("document split lost text — slices must reassemble the body")
    return DocumentSplit(intro=intro, sections=tuple(sections))
