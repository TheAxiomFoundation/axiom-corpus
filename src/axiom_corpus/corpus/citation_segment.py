"""Grammar-safe citation-path hierarchy segments.

``schema/citation-path.v1.json`` allows a hierarchy segment to contain only
``[A-Za-z0-9]``, space, ``.``, ``-`` and the en-dash (U+2013). Publisher
section identifiers frequently carry other punctuation (Nebraska ``77-3,100``,
Connecticut ``12-740(a)-1``, Colorado ``39-22-103(1)``, Delaware ``1159, 1160``),
and passing them through verbatim produces paths the grammar gate rejects.

:func:`citation_segment` folds every run of characters outside the grammar
alphabet (together with any hyphens, dashes or whitespace touching that run)
into a single hyphen, so the result is deterministic and reversible by
inspection next to the publisher identifier the adapter keeps in provision
metadata (``metadata.publisher_section_id``). Characters the grammar already
accepts are left exactly as they are, so segments that were valid before are
returned unchanged and no released citation path moves.
"""

from __future__ import annotations

import re

_SAFE = r"A-Za-z0-9 .\-–"
_UNSAFE_RUN = rf"[-–\s]*[^{_SAFE}]+[-–\s]*"
_LEADING_UNSAFE_RE = re.compile(rf"^{_UNSAFE_RUN}")
_TRAILING_UNSAFE_RE = re.compile(rf"{_UNSAFE_RUN}$")
_INNER_UNSAFE_RE = re.compile(_UNSAFE_RUN)

VARIANT_SEPARATOR = "--"
"""Separator between a section segment and a same-number variant slug.

Follows the released New Mexico and Vermont statute paths
(``7-1-6.21--effective-2027-07-01``, ``32-5930ll--effective-2030-07-01``).
"""


def citation_segment(value: str, *, normalize_dashes: bool = False) -> str:
    """Return ``value`` as a grammar-safe citation-path hierarchy segment.

    Rules, applied in order:

    1. surrounding whitespace is dropped and, when ``normalize_dashes`` is
       set, en-dashes and em-dashes become hyphens (for publishers whose
       numbering uses the typographic dash interchangeably with ``-``);
    2. a run of characters outside the grammar alphabet at the start or end
       of the segment is removed together with adjacent hyphens, dashes and
       whitespace (``39-22-103(1)`` -> ``39-22-103-1``);
    3. every interior run is folded into one hyphen, again swallowing adjacent
       hyphens, dashes and whitespace (``77-3,100`` -> ``77-3-100``,
       ``12-740(a)-1`` -> ``12-740-a-1``, ``1159, 1160`` -> ``1159-1160``);
    4. ``/`` is never accepted inside a segment and an empty result raises.

    Segments that already satisfy the grammar are returned unchanged.
    """
    text = value.strip()
    if normalize_dashes:
        text = text.replace("–", "-").replace("—", "-")
    text = _LEADING_UNSAFE_RE.sub("", text)
    text = _TRAILING_UNSAFE_RE.sub("", text)
    text = _INNER_UNSAFE_RE.sub("-", text)
    if text in {"", ".", ".."}:
        raise ValueError(f"citation segment has no grammar-safe content: {value!r}")
    return text


def variant_segment(segment: str, variant: str | None) -> str:
    """Join a section segment with an optional same-number variant slug."""
    if not variant:
        return segment
    return f"{segment}{VARIANT_SEPARATOR}{citation_segment(variant)}"
