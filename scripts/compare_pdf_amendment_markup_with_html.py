#!/usr/bin/env python3
"""Compare a PDF's extracted amendment markup with the publisher's HTML rendering.

Some registers publish the same order as an authenticated PDF and as HTML whose
inline styles carry the amendment markup (``text-decoration: line-through`` for
deleted text, ``underline`` for inserted text). This check extracts the PDF with
its manifest's ``extraction`` settings (``amendment_markup``, ``sort_blocks``),
labels every word of both renderings deleted (D), inserted (I) or plain (P), and
aligns the two word sequences from the first deleted or inserted word to the
last. It reports every stretch where the sequences differ and exits 1 if the
two sides of any such stretch disagree on a label. Within a stretch, words with
the same text must carry the same label, so labels swapped between two words
fail; words spelled differently (a non-breaking hyphen, a word split at a
line-end hyphen) must carry the same labels in the same order.

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


def _collapsed(labels: list[str]) -> list[str]:
    """Drop consecutive repeats, so one word split in two keeps its label sequence."""
    return [label for index, label in enumerate(labels) if not index or label != labels[index - 1]]


def _labels_agree(html_part: list[Word], pdf_part: list[Word]) -> bool:
    """Compare the labels of one differing stretch word by word.

    The stretch's words are aligned by their text alone. Words that match must
    carry the same label, so two words whose labels are swapped
    (``keep [-old-] {+new+} end`` against ``keep {+old+} [-new-] end``) fail.
    Words spelled differently on the two sides (a non-breaking hyphen, a word
    split at a line-end hyphen) must carry the same sequence of labels, in
    order.
    """
    matcher = difflib.SequenceMatcher(
        a=[word for word, _label in html_part],
        b=[word for word, _label in pdf_part],
        autojunk=False,
    )
    for operation, a0, a1, b0, b1 in matcher.get_opcodes():
        html_labels = [label for _word, label in html_part[a0:a1]]
        pdf_labels = [label for _word, label in pdf_part[b0:b1]]
        if operation == "equal":
            if html_labels != pdf_labels:
                return False
        elif _collapsed(html_labels) != _collapsed(pdf_labels):
            return False
    return True


def compare(html: list[Word], pdf: list[Word]) -> dict[str, Any]:
    html_span = _marked_span(html)
    pdf_span = _marked_span(pdf)
    matcher = difflib.SequenceMatcher(
        a=[f"{label}|{word}" for word, label in html_span],
        b=[f"{label}|{word}" for word, label in pdf_span],
        autojunk=False,
    )
    differences = []
    label_conflicts = 0
    for operation, a0, a1, b0, b1 in matcher.get_opcodes():
        if operation == "equal":
            continue
        html_part = html_span[a0:a1]
        pdf_part = pdf_span[b0:b1]
        labels_agree = _labels_agree(html_part, pdf_part)
        if not labels_agree:
            label_conflicts += 1
        differences.append(
            {
                "html": " ".join(f"{word}<{label}>" for word, label in html_part),
                "pdf": " ".join(f"{word}<{label}>" for word, label in pdf_part),
                "labels_agree": labels_agree,
            }
        )
    return {
        "html_words": len(html_span),
        "pdf_words": len(pdf_span),
        "html_label_counts": dict(Counter(label for _word, label in html_span)),
        "pdf_label_counts": dict(Counter(label for _word, label in pdf_span)),
        "equal_word_ratio": round(matcher.ratio(), 6),
        "differences": differences,
        "label_conflicts": label_conflicts,
        "ok": label_conflicts == 0,
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
