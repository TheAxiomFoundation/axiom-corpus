"""Source coverage: how much of the text an extractor read from a source reached its rows.

The release content check (``content_quality``) reads rows, so it finds a row made of
page navigation and a document with no text below it, but not a source whose rows kept
some of its text and lost the rest (docs/source-coverage-check.md). This module measures
that loss for one source document from two texts:

``region``
    What the extractor read from the source: an HTML page's content root or the nodes
    its ``html_text_selector`` names, a PDF's pages or the lines of its page range or
    windows between the start and stop markers, a DOCX body between its markers. Text
    the extractor removes on purpose (drop selectors, drop lines, running headers,
    repeated section headings) is not part of the region; its words are counted apart
    as ``deliberately_dropped_words``.
``extracted``
    The heading and the body of every row made from the source.

Both are read as words: maximal runs of letters and digits, casefolded, after Unicode
NFKC (so ligatures and width variants compare equal), with soft hyphens and zero-width
characters removed and a word hyphenated at a line end joined. A change of case,
whitespace or punctuation therefore never reads as loss. Words are counted as a
multiset: a phrase the source prints twice must be kept twice.

``kept_words`` is the size of the multiset intersection of the region's and the
extracted words, so ``0 <= kept_words <= region_words`` and ``coverage`` is their ratio
(1.0 for a region with no words: nothing was there to lose). The ``longest_missing_runs``
are what a reviewer reads: the stretches of the region with no counterpart in the
extracted text. A run runs from one missing word to another and is not ended by fewer
than ``RUN_BREAK_WORDS`` kept words in a row, so a lost passage stays one run although a
heading's words recur inside it. Every missing word lies in exactly one run, so the
runs' word counts sum to ``region_words - kept_words`` (only the ``MISSING_RUN_LIMIT``
longest are recorded).

The figures are recorded, per source, in a scope's coverage report under
``source_coverage``. Nothing gates on them yet.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

SOURCE_COVERAGE_VERSION = "source-coverage-v1"
# How many missing runs a source records, longest first.
MISSING_RUN_LIMIT = 10
# This many kept words in a row end a missing run; fewer stay inside it.
RUN_BREAK_WORDS = 4
# A recorded run shows at most this much of its text: its opening and its close.
MISSING_RUN_HEAD_CHARS = 110
MISSING_RUN_TAIL_CHARS = 50
# ... and this much of the region just before it, so a one-word run can be placed.
MISSING_RUN_BEFORE_CHARS = 40
# The bar the design note proposes for a later ``low_source_coverage`` finding: a
# source whose rows keep under half of a region of at least 50 words. Reports rank
# by it; no release check reads it.
REVIEW_COVERAGE = 0.5
REVIEW_MIN_REGION_WORDS = 50

# Characters that never show and never separate words: the soft hyphen and the
# zero-width space, non-joiner, joiner, word joiner and byte-order mark.
_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"))
# A word hyphenated at a line end. Extractors join a paragraph's lines with spaces
# before a row is written, so the break is any whitespace after a hyphen that follows a
# letter and precedes one: "appli-\ncant" in a page's text and "appli- cant" in the row
# made from it are both "applicant".
_LINE_END_HYPHEN = re.compile(r"(?<=[^\W\d_])[-\u2010\u2011]\s+(?=[^\W\d_])")
_WORD = re.compile(r"[^\W_]+")
# How many consecutive words anchor a region word to the extracted text, longest
# stretch first (see _matched).
_ANCHOR_SIZES = (8, 4, 2)


class _Row(Protocol):
    """A provision record, or anything else with a heading and a body."""

    @property
    def heading(self) -> str | None: ...

    @property
    def body(self) -> str | None: ...


def normalized(text: str) -> str:
    """``text`` with compatibility forms folded, invisible characters removed and
    words hyphenated at a line end joined. Case and punctuation are kept."""
    folded = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    return _LINE_END_HYPHEN.sub("", folded)


def words(text: str) -> list[str]:
    """The words of ``text``, in order: casefolded runs of letters and digits."""
    return [match.group().casefold() for match in _WORD.finditer(normalized(text))]


def row_texts(rows: Iterable[_Row]) -> list[str]:
    """The extracted text of a source: each row's heading, then its body."""
    texts: list[str] = []
    for row in rows:
        for text in (row.heading, row.body):
            if isinstance(text, str) and text:
                texts.append(text)
    return texts


@dataclass(frozen=True)
class MissingRun:
    """A stretch of the region with no counterpart in the extracted text.

    ``words`` is the number of missing words in the stretch and ``offset`` the
    position of its first one among the region's words (words the extractor dropped on
    purpose after reading them included). ``text`` is the stretch as the source prints
    it, from its first missing word to its last, with any short run of kept words
    inside it; ``before`` is the end of the text ahead of it.
    """

    offset: int
    words: int
    text: str
    before: str = ""

    def to_mapping(self) -> dict[str, Any]:
        return {
            "offset": self.offset,
            "words": self.words,
            "text": self.text,
            "before": self.before,
        }


@dataclass(frozen=True)
class SourceCoverage:
    """The coverage figures of one source document."""

    region_words: int
    kept_words: int
    deliberately_dropped_words: int = 0
    longest_missing_runs: tuple[MissingRun, ...] = ()

    def __post_init__(self) -> None:
        for name in ("region_words", "kept_words", "deliberately_dropped_words"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer, not {value!r}")
        if self.kept_words > self.region_words:
            raise ValueError(
                f"kept_words ({self.kept_words}) exceeds region_words ({self.region_words})"
            )

    @property
    def missing_words(self) -> int:
        return self.region_words - self.kept_words

    @property
    def coverage(self) -> float:
        """The share of the region's words that reached a row, in [0, 1]."""
        if not self.region_words:
            return 1.0
        return self.kept_words / self.region_words

    def to_mapping(self) -> dict[str, Any]:
        return {
            "region_words": self.region_words,
            "kept_words": self.kept_words,
            "deliberately_dropped_words": self.deliberately_dropped_words,
            "longest_missing_runs": [run.to_mapping() for run in self.longest_missing_runs],
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SourceCoverage:
        runs = data.get("longest_missing_runs", ())
        if not isinstance(runs, list | tuple):
            raise ValueError("longest_missing_runs must be a list")
        parsed: list[MissingRun] = []
        for run in runs:
            if not isinstance(run, Mapping):
                raise ValueError("each missing run must be a mapping")
            offset, count, text = run.get("offset"), run.get("words"), run.get("text")
            before = run.get("before", "")
            if (
                not isinstance(offset, int)
                or isinstance(offset, bool)
                or offset < 0
                or not isinstance(count, int)
                or isinstance(count, bool)
                or count < 1
                or not isinstance(text, str)
                or not isinstance(before, str)
            ):
                raise ValueError(f"invalid missing run: {dict(run)!r}")
            parsed.append(MissingRun(offset=offset, words=count, text=text, before=before))
        return cls(
            region_words=_required_count(data, "region_words"),
            kept_words=_required_count(data, "kept_words"),
            deliberately_dropped_words=_required_count(data, "deliberately_dropped_words"),
            longest_missing_runs=tuple(parsed),
        )


def measure_source_coverage(
    region: Iterable[str],
    extracted: Iterable[str],
    *,
    dropped: Iterable[str] = (),
    dropped_from_region: Iterable[str] = (),
) -> SourceCoverage:
    """Measure how much of ``region`` the ``extracted`` texts keep.

    ``region`` is the text the extractor read, in reading order; its pieces are one
    text (a word hyphenated across two of them is one word). Each of ``extracted`` is
    one row's heading or body and is read on its own. ``dropped`` are texts the
    extractor removed on purpose before reading the region; ``dropped_from_region`` are
    texts it removed on purpose after reading them as part of ``region`` (a navigation
    block, a repeated section heading), whose words leave the region.
    """
    region_text = normalized("\n".join(region))
    spans = [
        (match.group().casefold(), match.start(), match.end())
        for match in _WORD.finditer(region_text)
    ]
    region_words = [word for word, _start, _end in spans]
    extracted_words = [words(text) for text in extracted]
    set_aside_words = [words(text) for text in dropped_from_region]

    region_counts = Counter(region_words)
    set_aside = _counts(set_aside_words) & region_counts
    kept = (region_counts - set_aside) & _counts(extracted_words)

    matched = _matched(region_words, [*extracted_words, *set_aside_words])
    runs = []
    for start, end, count in _missing_runs(matched):
        # Take the punctuation that touches the run with it: "(a) ... income."
        opens, closes = spans[start][1], spans[end - 1][2]
        while (
            opens > 0
            and not region_text[opens - 1].isspace()
            and (start == 0 or opens > spans[start - 1][2])
        ):
            opens -= 1
        while (
            closes < len(region_text)
            and not region_text[closes].isspace()
            and (end == len(spans) or closes < spans[end][1])
        ):
            closes += 1
        runs.append(
            MissingRun(
                offset=start,
                words=count,
                text=_excerpt(region_text[opens:closes]),
                before=_tail(region_text[:opens]),
            )
        )
    runs.sort(key=lambda run: (-run.words, run.offset))
    return SourceCoverage(
        region_words=len(region_words) - sum(set_aside.values()),
        kept_words=sum(kept.values()),
        deliberately_dropped_words=sum(len(words(text)) for text in dropped)
        + sum(set_aside.values()),
        longest_missing_runs=tuple(runs[:MISSING_RUN_LIMIT]),
    )


def missing_run_lengths(
    region: Iterable[str],
    extracted: Iterable[str],
    *,
    dropped_from_region: Iterable[str] = (),
) -> list[int]:
    """The missing words of every missing run, in reading order (not only the longest)."""
    region_words = words("\n".join(region))
    matched = _matched(
        region_words,
        [*(words(text) for text in extracted), *(words(text) for text in dropped_from_region)],
    )
    return [count for _start, _end, count in _missing_runs(matched)]


def _counts(sequences: Iterable[Sequence[str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for sequence in sequences:
        counts.update(sequence)
    return counts


def _matched(region_words: Sequence[str], sequences: Sequence[Sequence[str]]) -> list[bool]:
    """Which region words have a counterpart in ``sequences``, one use per occurrence.

    A word that occurs ``r`` times in the region and ``s`` times in the sequences is
    matched ``min(r, s)`` times, so the unmatched words are exactly the multiset
    difference. Which occurrences are matched only decides where the missing runs
    fall, and the aim is to leave a lost passage whole: the "the" inside a lost
    paragraph must not use up the "the" of a kept one. So words are matched in order
    of how much of their surroundings survives: first those inside a stretch of
    ``_ANCHOR_SIZES[0]`` consecutive words that a sequence also holds, then shorter
    stretches, and what is left over goes to the shortest gaps first.
    """
    available = _counts(sequences)
    matched = [False] * len(region_words)

    def take(index: int) -> None:
        word = region_words[index]
        if available[word] > 0:
            available[word] -= 1
            matched[index] = True

    for size in _ANCHOR_SIZES:
        for index in _anchored(region_words, sequences, size):
            if not matched[index]:
                take(index)
    gaps = _unmatched_runs(matched)
    for start, end in sorted(gaps, key=lambda gap: (gap[1] - gap[0], gap[0])):
        for index in range(start, end):
            take(index)
    return matched


def _anchored(
    region_words: Sequence[str], sequences: Sequence[Sequence[str]], size: int
) -> list[int]:
    """Positions of the region inside ``size`` consecutive words a sequence also holds."""
    wanted = set(_shingles(region_words, size))
    if not wanted:
        return []
    held: set[tuple[str, ...]] = set()
    for sequence in sequences:
        held.update(shingle for shingle in _shingles(sequence, size) if shingle in wanted)
    covered = [False] * len(region_words)
    for index, shingle in enumerate(_shingles(region_words, size)):
        if shingle in held:
            for position in range(index, index + size):
                covered[position] = True
    return [index for index, flag in enumerate(covered) if flag]


def _shingles(sequence: Sequence[str], size: int) -> Iterable[tuple[str, ...]]:
    return zip(*(sequence[offset:] for offset in range(size)), strict=False)


def _missing_runs(matched: Sequence[bool]) -> list[tuple[int, int, int]]:
    """The missing runs as (first missing position, end, missing words).

    A run starts at an unmatched position and ends after the last unmatched position
    that fewer than ``RUN_BREAK_WORDS`` matched positions in a row separate from the
    one before it.
    """
    runs: list[tuple[int, int, int]] = []
    start: int | None = None
    last = count = kept = 0
    for index, flag in enumerate(matched):
        if not flag:
            if start is None:
                start, count = index, 0
            count += 1
            last, kept = index, 0
        elif start is not None:
            kept += 1
            if kept >= RUN_BREAK_WORDS:
                runs.append((start, last + 1, count))
                start = None
    if start is not None:
        runs.append((start, last + 1, count))
    return runs


def _unmatched_runs(matched: Sequence[bool]) -> list[tuple[int, int]]:
    """The maximal stretches of unmatched positions, as half-open ranges."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, flag in enumerate(matched):
        if flag:
            if start is not None:
                runs.append((start, index))
                start = None
        elif start is None:
            start = index
    if start is not None:
        runs.append((start, len(matched)))
    return runs


def _excerpt(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= MISSING_RUN_HEAD_CHARS + MISSING_RUN_TAIL_CHARS + 3:
        return text
    return (
        f"{text[:MISSING_RUN_HEAD_CHARS].rstrip()} \u2026 {text[-MISSING_RUN_TAIL_CHARS:].lstrip()}"
    )


def _tail(text: str) -> str:
    """The last ``MISSING_RUN_BEFORE_CHARS`` characters of ``text``, from a word start."""
    text = " ".join(text[-4 * MISSING_RUN_BEFORE_CHARS :].split())
    if len(text) <= MISSING_RUN_BEFORE_CHARS:
        return text
    cut = text[-MISSING_RUN_BEFORE_CHARS:]
    return cut.split(" ", 1)[1] if " " in cut else cut


class SourceRegion:
    """What one extraction read from its source, told to it as the extractor works.

    An extraction path that supports the measure calls ``start`` with the kind of
    region it reads, ``read`` with each piece of the region in reading order, and
    ``drop`` with each text it removes on purpose (``read=True`` when that text was
    already passed to ``read``). A path that calls none of them leaves the source
    unmeasured.
    """

    def __init__(self) -> None:
        self.kind: str | None = None
        self._read: list[str] = []
        self._dropped: list[str] = []
        self._dropped_from_region: list[str] = []

    @property
    def measured(self) -> bool:
        return self.kind is not None

    def start(self, kind: str) -> None:
        self.kind = kind

    def read(self, text: str) -> None:
        if text:
            self._read.append(text)

    def drop(self, text: str, *, read: bool = False) -> None:
        if text:
            (self._dropped_from_region if read else self._dropped).append(text)

    @property
    def texts(self) -> tuple[str, ...]:
        """The region's pieces, in reading order."""
        return tuple(self._read)

    def measure(self, extracted: Iterable[str]) -> SourceCoverage:
        if self.kind is None:
            raise ValueError("no region was read from this source")
        return measure_source_coverage(
            self._read,
            extracted,
            dropped=self._dropped,
            dropped_from_region=self._dropped_from_region,
        )


@dataclass(frozen=True)
class SourceCoverageEntry:
    """One source document's figures, as its scope's coverage report records them."""

    source_path: str
    source_format: str
    region: str
    figures: SourceCoverage

    def to_mapping(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_format": self.source_format,
            "region": self.region,
            **self.figures.to_mapping(),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SourceCoverageEntry:
        return cls(
            source_path=_required_text(data, "source_path"),
            source_format=_required_text(data, "source_format"),
            region=_required_text(data, "region"),
            figures=SourceCoverage.from_mapping(data),
        )


@dataclass(frozen=True)
class UnmeasuredSource:
    """A source whose format or segmentation records no region yet."""

    source_path: str
    source_format: str

    def to_mapping(self) -> dict[str, Any]:
        return {"source_path": self.source_path, "source_format": self.source_format}


@dataclass(frozen=True)
class SourceCoverageReport:
    """A scope's ``source_coverage``: one entry per measured source, in manifest order."""

    sources: tuple[SourceCoverageEntry, ...]
    unmeasured: tuple[UnmeasuredSource, ...] = ()
    measure: str = SOURCE_COVERAGE_VERSION

    def to_mapping(self) -> dict[str, Any]:
        return {
            "measure": self.measure,
            "sources": [entry.to_mapping() for entry in self.sources],
            "unmeasured": [source.to_mapping() for source in self.unmeasured],
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SourceCoverageReport:
        if not isinstance(data, Mapping):
            raise ValueError("source_coverage must be a mapping")
        sources = data.get("sources")
        unmeasured = data.get("unmeasured", ())
        if not isinstance(sources, list | tuple) or not isinstance(unmeasured, list | tuple):
            raise ValueError("source_coverage sources and unmeasured must be lists")
        for row in (*sources, *unmeasured):
            if not isinstance(row, Mapping):
                raise ValueError("each source_coverage source must be a mapping")
        return cls(
            sources=tuple(SourceCoverageEntry.from_mapping(row) for row in sources),
            unmeasured=tuple(
                UnmeasuredSource(
                    source_path=_required_text(row, "source_path"),
                    source_format=_required_text(row, "source_format"),
                )
                for row in unmeasured
            ),
            measure=_required_text(data, "measure"),
        )


def needs_review(figures: SourceCoverage) -> bool:
    """Whether a source is under the proposed review bar (see ``REVIEW_COVERAGE``)."""
    return figures.region_words >= REVIEW_MIN_REGION_WORDS and figures.coverage < REVIEW_COVERAGE


def _required_count(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"source_coverage {key} must be a non-negative integer, not {value!r}")
    return value


def _required_text(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"source_coverage {key} must be a non-empty string, not {value!r}")
    return value
