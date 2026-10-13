#!/usr/bin/env python3
"""Compare a PDF's extracted amendment markup with the publisher's HTML rendering.

Some registers publish the same order as an authenticated PDF and as HTML whose
inline styles carry the amendment markup (``text-decoration: line-through`` for
deleted text, ``underline`` for inserted text). This check extracts the PDF with
its manifest's ``extraction`` settings (``amendment_markup``, ``sort_blocks``),
labels every word of both renderings deleted (D), inserted (I) or plain (P), and
aligns the two word sequences from the first deleted or inserted word to the
last. It reports every stretch where the sequences differ and exits 1 if the
two sides of any such stretch disagree on a label. Within a stretch the
characters are compared one by one, after typographic spelling differences (a
non-breaking hyphen, curly quotes) are normalized and the words joined, so a
word split at a line-end hyphen still lines up and labels swapped between two
words fail. The check runs in both directions and passes only if both agree.

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

Word = tuple[str, str]

_DELIMITER_STATES = {"[-": "D", "-]": None, "{+": "I", "+}": None}
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
    labels: set[str] = set()
    for char, state in zip(chars, states, strict=True):
        if char.isspace():
            if text:
                words.append(("".join(text), "".join(sorted(labels))))
                text, labels = [], set()
            continue
        text.append(char)
        labels.add(state or "P")
    if text:
        words.append(("".join(text), "".join(sorted(labels))))
    return words


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


def marked_text_words(text: str) -> list[Word]:
    """Label each word of wdiff-marked text."""
    chars: list[str] = []
    states: list[str | None] = []
    state: str | None = None
    index = 0
    while index < len(text):
        token = text[index : index + 2]
        if token in _DELIMITER_STATES:
            state = _DELIMITER_STATES[token]
            index += 2
            continue
        chars.append(text[index])
        states.append(state)
        index += 1
    return _words(chars, states)


def pdf_words(pdf: bytes, extraction: dict[str, Any]) -> list[Word]:
    blocks = documents._extract_pdf_blocks(pdf, extraction=extraction)
    return marked_text_words("\n\n".join(block.body for block in blocks))


def _marked_span(words: list[Word]) -> list[Word]:
    marked = [index for index, (_word, label) in enumerate(words) if label != "P"]
    if not marked:
        return []
    return words[marked[0] : marked[-1] + 1]


# Spellings that differ only in typography: hyphen and quote variants are
# mapped to ASCII and soft hyphens dropped, after NFKC (ligatures, widths).
_SPELLING = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
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


def _labelled_characters(words: list[Word]) -> tuple[list[str], list[str]]:
    characters: list[str] = []
    labels: list[str] = []
    for word, label in words:
        for character in _spelling(word):
            characters.append(character)
            labels.append(label)
    return characters, labels


def _labels_agree(html_part: list[Word], pdf_part: list[Word]) -> bool:
    """Compare the labels of one differing stretch character by character.

    Both sides' words are normalized (``_spelling``), joined without spaces and
    aligned character by character, each character carrying its word's label.
    Characters that match must carry the same label, so labels swapped between
    two words fail however the words are spelled or split
    (``keep [-old-] {+new+} end`` against ``keep {+old+} [-new-] end``;
    ``non-`` ``household`` against ``non-household``). Characters that differ
    are accepted only inside a stretch whose labels are one and the same on
    both sides, and characters present on one side only only if they are
    hyphens (a word hyphenated at a line end).
    """
    html_characters, html_labels = _labelled_characters(html_part)
    pdf_characters, pdf_labels = _labelled_characters(pdf_part)
    matcher = difflib.SequenceMatcher(a=html_characters, b=pdf_characters, autojunk=False)
    for operation, a0, a1, b0, b1 in matcher.get_opcodes():
        if operation == "equal":
            if html_labels[a0:a1] != pdf_labels[b0:b1]:
                return False
        elif operation == "replace":
            if len(set(html_labels[a0:a1]) | set(pdf_labels[b0:b1])) != 1:
                return False
        elif any(character != "-" for character in html_characters[a0:a1] + pdf_characters[b0:b1]):
            return False
    return True


def _differing_stretches(
    first: list[Word], second: list[Word]
) -> tuple[difflib.SequenceMatcher[str], list[tuple[list[Word], list[Word], bool]]]:
    matcher = difflib.SequenceMatcher(
        a=[f"{label}|{word}" for word, label in first],
        b=[f"{label}|{word}" for word, label in second],
        autojunk=False,
    )
    stretches = []
    for operation, a0, a1, b0, b1 in matcher.get_opcodes():
        if operation == "equal":
            continue
        first_part, second_part = first[a0:a1], second[b0:b1]
        stretches.append((first_part, second_part, _labels_agree(first_part, second_part)))
    return matcher, stretches


def compare(html: list[Word], pdf: list[Word]) -> dict[str, Any]:
    """Compare the marked spans of the two renderings.

    The alignment is run in both directions (HTML against PDF and PDF against
    HTML) and ``ok`` requires both to be free of label conflicts, so the verdict
    does not depend on which side is which. ``differences`` lists the HTML-to-PDF
    stretches.
    """
    html_span = _marked_span(html)
    pdf_span = _marked_span(pdf)
    matcher, stretches = _differing_stretches(html_span, pdf_span)
    _reverse_matcher, reverse_stretches = _differing_stretches(pdf_span, html_span)
    label_conflicts = sum(not agree for _html, _pdf, agree in stretches)
    reverse_label_conflicts = sum(not agree for _pdf, _html, agree in reverse_stretches)
    differences = [
        {
            "html": " ".join(f"{word}<{label}>" for word, label in html_part),
            "pdf": " ".join(f"{word}<{label}>" for word, label in pdf_part),
            "labels_agree": agree,
        }
        for html_part, pdf_part, agree in stretches
    ]
    return {
        "html_words": len(html_span),
        "pdf_words": len(pdf_span),
        "html_label_counts": dict(Counter(label for _word, label in html_span)),
        "pdf_label_counts": dict(Counter(label for _word, label in pdf_span)),
        "equal_word_ratio": round(matcher.ratio(), 6),
        "differences": differences,
        "label_conflicts": label_conflicts,
        "reverse_label_conflicts": reverse_label_conflicts,
        "ok": label_conflicts == 0 and reverse_label_conflicts == 0,
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
