#!/usr/bin/env python3
"""Compare a PDF's extracted amendment markup with the publisher's HTML rendering.

Some registers publish the same order as an authenticated PDF and as HTML whose
inline styles carry the amendment markup (``text-decoration: line-through`` for
deleted text, ``underline`` for inserted text). This check extracts the PDF with
its manifest's ``extraction`` settings (``amendment_markup``, ``sort_blocks``),
labels every character of both renderings deleted (D), inserted (I) or plain
(P), and aligns the two word sequences from the first deleted or inserted word to
the last, with a few plain words of context on each side. It reports every
stretch where the sequences differ and exits 1 if the two sides of any such
stretch disagree on a label. Within a stretch the characters are compared one by
one, after typographic spelling differences (a non-breaking hyphen, a dash,
curly quotes, decomposed accents) are normalized and the words joined, so a
word split at a line-end hyphen still lines up, and labels swapped between two
words or two characters fail. Text present on one side only must carry the label
of a character next to the gap on the other side, and text that appears on one
side only in two places (moved text) must carry the same labels in both. The
check runs in both directions and passes only if both agree.

Usage::

    uv run --extra dev python scripts/compare_pdf_amendment_markup_with_html.py \\
        --manifest manifests/us-de-register-13-de-reg-1550.yaml \\
        --pdf data/corpus/sources/us-de/rulemaking/2026-09-23-de-register-13-de-reg-1550/official-documents/de-register-13-de-reg-1550.pdf \\
        --html /path/to/13-de-reg-1550.htm

No network access: fetch the HTML separately and pass its path.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString

from axiom_corpus.corpus import documents

# A word and its labels, one per character: D (deleted), I (inserted) or P
# (plain), so ``("20056", "PPPDI")`` is a number whose 5 is struck and 6 inserted.
Word = tuple[str, str]

_RUN_LABELS = {documents._AMENDMENT_DELETED: "D", documents._AMENDMENT_INSERTED: "I"}
_BLOCK_TAGS = {
    "article",
    "blockquote",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ol",
    "p",
    "section",
    "table",
    "td",
    "th",
    "tr",
    "ul",
}


def _words(chars: list[str], states: list[str | None]) -> list[Word]:
    words: list[Word] = []
    text: list[str] = []
    labels: list[str] = []
    for char, state in zip(chars, states, strict=True):
        if char.isspace():
            if text:
                words.append(("".join(text), "".join(labels)))
                text, labels = [], []
            continue
        text.append(char)
        labels.append(state or "P")
    if text:
        words.append(("".join(text), "".join(labels)))
    return words


def _word_label(labels: str) -> str:
    """A word's labels as a set: ``D``, ``I``, ``P`` or a mix such as ``DIP``."""
    return "".join(sorted(set(labels)))


def _shown(word: Word) -> str:
    text, labels = word
    return f"{text}<{labels if len(set(labels)) > 1 else labels[0]}>"


def html_words(html: bytes) -> list[Word]:
    """Label each word of the HTML by its ancestors' text-decoration."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    root = soup.find("article") or soup.body or soup
    chars: list[str] = []
    states: list[str | None] = []
    previous_block: Any = None
    for node in root.descendants:
        if not isinstance(node, NavigableString) or isinstance(node, Comment):
            continue
        state: str | None = None
        block: Any = None
        for parent in node.parents:
            style = str(parent.get("style") or "") if hasattr(parent, "get") else ""
            if "line-through" in style:
                state = "D"
            elif "underline" in style and state is None:
                state = "I"
            if block is None and parent.name in _BLOCK_TAGS:
                block = parent
        if block is not previous_block:
            # Inline spans continue a word; a new block element starts one.
            chars.append(" ")
            states.append(None)
            previous_block = block
        chars.extend(str(node))
        states.extend([state] * len(str(node)))
    return _words(chars, states)


def _marked_text_labels(text: str) -> tuple[list[str], list[str | None]]:
    """Each character of wdiff-marked text with its label, delimiters removed.

    The delimiters are read as the extraction writes them
    (``documents._amendment_markup_runs``), so a struck "[" at the end of a run,
    written ``[-[-]``, is a deleted "[".
    """
    chars: list[str] = []
    states: list[str | None] = []
    for run, state in documents._amendment_markup_runs(text):
        chars.extend(run)
        states.extend([None if state is None else _RUN_LABELS[state]] * len(run))
    return chars, states


def marked_text_words(text: str) -> list[Word]:
    """Label each word of wdiff-marked text."""
    return _words(*_marked_text_labels(text))


def pdf_words(pdf: bytes, extraction: dict[str, Any]) -> list[Word]:
    """Label each word of the PDF's pages as the extraction marks them.

    Only a page the extraction marked (its block has ``metadata.amendment_markup``)
    is read as markup. A page outside the ``amendment_markup`` range is plain
    text: the extraction does not check it for delimiters, so any it holds are
    text, not markup.
    """
    chars: list[str] = []
    states: list[str | None] = []
    for block in documents._extract_pdf_blocks(pdf, extraction=extraction):
        if "amendment_markup" in block.metadata:
            block_chars, block_states = _marked_text_labels(block.body)
        else:
            block_chars, block_states = list(block.body), [None] * len(block.body)
        # A page break ends a word.
        chars.extend(["\n", *block_chars])
        states.extend([None, *block_states])
    return _words(chars, states)


# Plain words kept on each side of the marked span for the alignment, so a
# marked word split at a hyphen on one side (a plain "part-" before a marked
# "time") still lines up with its unsplit form.
_SPAN_CONTEXT_WORDS = 3


def _marked_bounds(words: list[Word]) -> tuple[int, int] | None:
    marked = [index for index, (_word, labels) in enumerate(words) if set(labels) != {"P"}]
    if not marked:
        return None
    return marked[0], marked[-1] + 1


def _marked_span(words: list[Word]) -> list[Word]:
    bounds = _marked_bounds(words)
    return [] if bounds is None else words[bounds[0] : bounds[1]]


def _aligned_span(words: list[Word]) -> list[Word]:
    """The marked span with up to ``_SPAN_CONTEXT_WORDS`` plain words on each side.

    Where one side has more context than the other (a span at the very start of
    one rendering), the extra plain words are one-sided at the edge of the
    alignment, which ``_labels_agree`` accepts.
    """
    bounds = _marked_bounds(words)
    if bounds is None:
        return []
    return words[max(bounds[0] - _SPAN_CONTEXT_WORDS, 0) : bounds[1] + _SPAN_CONTEXT_WORDS]


# Spellings that differ only in typography: hyphen, dash and quote variants are
# mapped to ASCII and soft hyphens dropped, after NFKC (ligatures, widths,
# composed accents).
_SPELLING = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\u00ad": None,
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
    }
)


def _spelling(word: str) -> str:
    return unicodedata.normalize("NFKC", word).translate(_SPELLING)


def _clusters(word: str, labels: str) -> list[tuple[str, str]]:
    """Split a word into base characters with their combining marks, each with one label.

    A cluster whose characters carry different labels gets their combined label
    (``DI``), which matches no single label.
    """
    clusters: list[tuple[str, list[str]]] = []
    for character, label in zip(word, labels, strict=True):
        if clusters and unicodedata.category(character).startswith("M"):
            clusters[-1] = (clusters[-1][0] + character, [*clusters[-1][1], label])
        else:
            clusters.append((character, [label]))
    return [(text, "".join(sorted(set(cluster_labels)))) for text, cluster_labels in clusters]


def _labelled_characters(words: list[Word]) -> tuple[list[str], list[str]]:
    characters: list[str] = []
    labels: list[str] = []
    for word, word_labels in words:
        for cluster, label in _clusters(word, word_labels):
            for normalized in _spelling(cluster):
                characters.append(normalized)
                labels.append(label)
    return characters, labels


# A word at least this long (normalized characters), or any word with a digit,
# that one side has and the other lacks in one differing stretch, while the
# other side has it unmatched in another stretch, is read as moved text and must
# keep its labels.
_MOVED_TEXT_MIN_CHARACTERS = 3

OneSided = tuple[str, str, str]  # (side, normalized word, labels)


def _labels_agree(
    html_part: list[Word], pdf_part: list[Word], *, at_start: bool, at_end: bool
) -> bool:
    """Compare the labels of one differing stretch character by character.

    Each side's characters keep their own labels, are normalized
    (``_spelling``, per base character and its combining marks), joined without
    spaces and aligned. Characters that match must carry the same label, so
    labels swapped between two words, or between two characters of one word
    (``200[-5-]{+6+}`` against ``200{+5+}[-6-]``), fail however the words are
    spelled or split. Characters that differ are accepted only where both sides
    share one label. Characters present on one side only (a footnote digit, a
    line-end hyphen) must share one label, and that label must be the label of a
    character next to the gap on the other side; plain text at the very start or
    end of the alignment (``at_start``, ``at_end``: context one side has and the
    other lacks) is also accepted.
    """
    html_characters, html_labels = _labelled_characters(html_part)
    pdf_characters, pdf_labels = _labelled_characters(pdf_part)
    matcher = difflib.SequenceMatcher(a=html_characters, b=pdf_characters, autojunk=False)
    agree = True
    for operation, a0, a1, b0, b1 in matcher.get_opcodes():
        if operation == "equal":
            agree = agree and html_labels[a0:a1] == pdf_labels[b0:b1]
        elif operation == "replace":
            agree = agree and len(set(html_labels[a0:a1]) | set(pdf_labels[b0:b1])) == 1
        else:
            if operation == "delete":
                labels, other, gap = html_labels[a0:a1], pdf_labels, b0
            else:
                labels, other, gap = pdf_labels[b0:b1], html_labels, a0
            one_sided = set(labels)
            around = set(other[max(gap - 1, 0) : gap + 1])
            at_edge = (gap == 0 and at_start) or (gap == len(other) and at_end)
            agree = (
                agree
                and len(one_sided) == 1
                and bool(one_sided & around or (at_edge and one_sided == {"P"}))
            )
    return agree


def _differing_stretches(
    first: list[Word], second: list[Word]
) -> tuple[difflib.SequenceMatcher[str], list[tuple[list[Word], list[Word], bool]], list[OneSided]]:
    matcher = difflib.SequenceMatcher(
        a=[f"{labels}|{word}" for word, labels in first],
        b=[f"{labels}|{word}" for word, labels in second],
        autojunk=False,
    )
    stretches = []
    one_sided_runs: list[OneSided] = []
    for operation, a0, a1, b0, b1 in matcher.get_opcodes():
        if operation == "equal":
            continue
        # The words next to the stretch (equal on both sides) give the label
        # check the context of a word present on one side only.
        agree = _labels_agree(
            first[max(a0 - 1, 0) : a1 + 1],
            second[max(b0 - 1, 0) : b1 + 1],
            at_start=a0 == 0 and b0 == 0,
            at_end=a1 == len(first) and b1 == len(second),
        )
        stretches.append((first[a0:a1], second[b0:b1], agree))
        for side, part, other in (
            ("html", first[a0:a1], second[b0:b1]),
            ("pdf", second[b0:b1], first[a0:a1]),
        ):
            one_sided_runs.extend((side, word, labels) for word, labels in _unmatched(part, other))
    return matcher, stretches, one_sided_runs


def _unmatched(part: list[Word], other: list[Word]) -> list[Word]:
    """Words of ``part`` (normalized) found nowhere in ``other``'s joined text.

    A word counts as found when its normalized text occurs anywhere in the other
    side's normalized words joined without spaces, so a word split at a line-end
    hyphen (``part-`` ``time`` against ``part-time``) or carrying a footnote digit
    (``time2`` against ``time``) is not read as missing.
    """
    joined = "".join(_spelling(word) for word, _labels in other)
    return [(_spelling(word), labels) for word, labels in part if _spelling(word) not in joined]


def _moved_text(one_sided_runs: list[OneSided]) -> list[dict[str, Any]]:
    """Words unmatched on both sides (here in the HTML, there in the PDF) with other labels.

    A word is flagged when one side has a label for it that the other side
    lacks, or when its occurrences, paired in reading order, differ: the first
    catches a move hidden by an extra occurrence elsewhere, the second two moves
    that swap their labels. A word that only occurs more often on one side, with
    the same labels, is a text difference and is not flagged.
    """
    by_text: dict[str, dict[str, list[str]]] = {}
    for side, text, labels in one_sided_runs:
        if len(text) >= _MOVED_TEXT_MIN_CHARACTERS or any(char.isdigit() for char in text):
            by_text.setdefault(text, {"html": [], "pdf": []})[side].append(labels)
    return [
        {"text": text, "html": sides["html"], "pdf": sides["pdf"]}
        for text, sides in sorted(by_text.items())
        if sides["html"]
        and sides["pdf"]
        and (
            set(sides["html"]) != set(sides["pdf"])
            or any(html != pdf for html, pdf in zip(sides["html"], sides["pdf"], strict=False))
        )
    ]


def compare(html: list[Word], pdf: list[Word]) -> dict[str, Any]:
    """Compare the marked spans of the two renderings.

    The alignment is run in both directions (HTML against PDF and PDF against
    HTML) and ``ok`` requires both to be free of label conflicts, so the verdict
    does not depend on which side is which. ``differences`` lists the HTML-to-PDF
    stretches. Word and label counts cover the marked spans (first to last
    marked word); the alignment adds up to ``_SPAN_CONTEXT_WORDS`` words on each
    side (``_aligned_span``). Text that is one-sided on both sides, as when a
    phrase moves, must keep its labels (``moved_text``).
    """
    html_span = _marked_span(html)
    pdf_span = _marked_span(pdf)
    html_aligned, pdf_aligned = _aligned_span(html), _aligned_span(pdf)
    matcher, stretches, one_sided_runs = _differing_stretches(html_aligned, pdf_aligned)
    _reverse, reverse_stretches, _reverse_runs = _differing_stretches(pdf_aligned, html_aligned)
    label_conflicts = sum(not agree for _html, _pdf, agree in stretches)
    reverse_label_conflicts = sum(not agree for _pdf, _html, agree in reverse_stretches)
    moved_text = _moved_text(one_sided_runs)
    differences = [
        {
            "html": " ".join(_shown(word) for word in html_part),
            "pdf": " ".join(_shown(word) for word in pdf_part),
            "labels_agree": agree,
        }
        for html_part, pdf_part, agree in stretches
    ]
    return {
        "html_words": len(html_span),
        "pdf_words": len(pdf_span),
        "html_label_counts": dict(Counter(_word_label(labels) for _word, labels in html_span)),
        "pdf_label_counts": dict(Counter(_word_label(labels) for _word, labels in pdf_span)),
        "equal_word_ratio": round(matcher.ratio(), 6),
        "differences": differences,
        "label_conflicts": label_conflicts,
        "reverse_label_conflicts": reverse_label_conflicts,
        "moved_text": moved_text,
        "ok": label_conflicts == 0 and reverse_label_conflicts == 0 and not moved_text,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--source-id", help="Manifest document to use (default: the only one).")
    args = parser.parse_args(argv)
    entries = yaml.safe_load(args.manifest.read_text())["documents"]
    if args.source_id:
        entries = [entry for entry in entries if entry["source_id"] == args.source_id]
    if len(entries) != 1:
        parser.error("the manifest must select exactly one document (use --source-id)")
    extraction = entries[0].get("extraction") or {}
    result = compare(
        html_words(args.html.read_bytes()),
        pdf_words(args.pdf.read_bytes(), extraction),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
