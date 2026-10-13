from __future__ import annotations

import random
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import pytest
import yaml

from scripts.compare_pdf_amendment_markup_with_html import (
    compare,
    html_words,
    main,
    marked_text_words,
)

HTML = b"""
<html><body><article>
  <p>9059 Income Exclusions</p>
  <p><span style="text-decoration: line-through">Old non&#8209;household rule.</span></p>
  <p><span style="font-weight: bold; text-decoration: underline">New</span>
     <span style="text-decoration: underline">rule text.</span></p>
</article></body></html>
"""


def _uniform(words: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Give every character of each word the word's one label."""
    return [(word, label * len(word)) for word, label in words]


def test_html_words_label_line_through_and_underline() -> None:
    assert html_words(HTML) == _uniform(
        [
            ("9059", "P"),
            ("Income", "P"),
            ("Exclusions", "P"),
            ("Old", "D"),
            ("non‑household", "D"),
            ("rule.", "D"),
            ("New", "I"),
            ("rule", "I"),
            ("text.", "I"),
        ]
    )


def test_marked_text_words_read_wdiff_delimiters() -> None:
    assert marked_text_words("Keep [-old words-] and {+new+}. ([-h-]{+g+})") == [
        ("Keep", "PPPP"),
        ("old", "DDD"),
        ("words", "DDDDD"),
        ("and", "PPP"),
        ("new.", "IIIP"),
        ("(hg)", "PDIP"),
    ]


def test_compare_passes_spelling_differences_and_fails_label_conflicts() -> None:
    html = html_words(HTML)
    agreeing = marked_text_words(
        "9059 Income Exclusions [-Old non-household rule.-] {+New rule text.+}"
    )
    conflicting = marked_text_words(
        "9059 Income Exclusions [-Old non-household rule.-] New {+rule text.+}"
    )

    result = compare(html, agreeing)
    assert result["ok"] is True
    assert result["differences"] == [
        {"html": "non‑household<D>", "pdf": "non-household<D>", "labels_agree": True}
    ]
    assert compare(html, conflicting)["ok"] is False


def test_main_checks_a_pdf_against_html(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "Old rule.", fontname="helv", fontsize=12)
    width = fitz.get_text_length("Old rule.", fontname="helv", fontsize=12)
    page.draw_line((72, 97), (72 + width, 97), width=0.6)
    pdf_path = tmp_path / "order.pdf"
    document.save(pdf_path)
    html_path = tmp_path / "order.htm"
    html_path.write_bytes(
        b'<html><body><p><span style="text-decoration: line-through">Old rule.</span></p>'
        b"</body></html>"
    )
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {"documents": [{"source_id": "order", "extraction": {"amendment_markup": True}}]}
        )
    )

    status = main(
        ["--manifest", str(manifest_path), "--pdf", str(pdf_path), "--html", str(html_path)]
    )

    assert status == 0
    assert '"label_conflicts": 0' in capsys.readouterr().out


def test_compare_fails_labels_swapped_inside_one_stretch() -> None:
    html = marked_text_words("keep [-old-] {+new+} end")
    pdf = marked_text_words("keep {+old+} [-new-] end")

    result = compare(html, pdf)

    assert result["ok"] is False
    assert result["label_conflicts"] == 1
    assert result["differences"][0]["labels_agree"] is False


def test_compare_passes_a_word_split_at_a_line_end_hyphen() -> None:
    html = marked_text_words("keep [-non-household rule-] end")
    pdf = marked_text_words("keep [-non- household rule-] end")

    assert compare(html, pdf)["ok"] is True


def test_compare_fails_a_split_word_whose_parts_change_label() -> None:
    html = marked_text_words("keep [-non-household-] end")
    pdf = marked_text_words("keep [-non--] {+household+} end")

    assert compare(html, pdf)["ok"] is False


def test_compare_fails_labels_swapped_between_words_spelled_differently() -> None:
    words = ["non-household", "full-time", "part-time", "self-employed", "low-income"]
    html = _uniform(
        [(word.replace("-", "\u2011"), label) for word, label in zip(words, "DDIDI", strict=True)]
    )
    pdf = _uniform([(word, label) for word, label in zip(words, "DIDDI", strict=True)])

    assert compare(html, pdf)["ok"] is False


def test_compare_fails_labels_swapped_inside_one_word() -> None:
    # 2005 -> 2006 in the HTML, 2006 -> 2005 in the PDF.
    html = html_words(
        b'<p>in 200<span style="text-decoration: line-through">5</span>'
        b'<span style="text-decoration: underline">6</span> only</p>'
    )
    pdf = marked_text_words("in 200{+5+}[-6-] only")

    assert html[1] == ("20056", "PPPDI")
    assert pdf[1] == ("20056", "PPPID")
    assert compare(html, pdf)["ok"] is False
    assert compare(html, marked_text_words("in 200[-5-]{+6+} only"))["ok"] is True


def test_compare_passes_a_repeated_phrase_split_differently_on_each_side() -> None:
    html = _uniform([("non-household", "D"), ("non-", "I"), ("household", "I")])
    pdf = _uniform([("non-", "D"), ("household", "D"), ("non-household", "I")])

    assert compare(html, pdf)["ok"] is True


def test_compare_verdict_does_not_depend_on_the_side() -> None:
    first = _uniform([("b", "I"), ("c", "D"), ("a", "P"), ("b", "I")])
    second = _uniform([("c", "I"), ("c", "D"), ("b", "P"), ("b", "I")])

    assert compare(first, second)["ok"] is compare(second, first)["ok"] is False


@pytest.mark.parametrize(
    ("html", "pdf", "ok"),
    [
        # A footnote digit or other text on one side only, inside one label's run.
        ("keep [-old regulation-] end", "keep [-old regulation1-] end", True),
        ("keep [-a - b-] end", "keep [-a b-] end", True),
        # ... but not where it would carry a different label from its neighbours.
        ("keep [-old regulation-] end", "keep [-old regulation-]{+1+} end", False),
        # A deleted dash the other side lacks altogether.
        ("keep [-x-] mid [-\u2013-] end", "keep [-x-] mid end", False),
    ],
)
def test_compare_judges_text_present_on_one_side_by_its_neighbours(
    html: str, pdf: str, ok: bool
) -> None:
    assert compare(marked_text_words(html), marked_text_words(pdf))["ok"] is ok


def test_compare_fails_text_that_moves_and_changes_label() -> None:
    html = marked_text_words("keep [-a old b-] {+c d+} end")
    pdf = marked_text_words("keep [-a b-] {+c old d+} end")

    result = compare(html, pdf)

    assert result["ok"] is False
    assert result["moved_text"] == [{"text": "old", "html": ["DDD"], "pdf": ["III"]}]
    # Moved with the same label, it is a text difference, not a label conflict.
    same_label = marked_text_words("keep [-a b-] [-old-] {+c d+} end")
    assert compare(html, same_label)["moved_text"] == []


def test_compare_context_does_not_make_a_side_one_sided_at_the_start() -> None:
    html = marked_text_words("Intro text here [-old-] end")

    assert compare(html, marked_text_words("[-old-] end"))["ok"] is True


def test_compare_treats_a_decomposed_accent_as_its_composed_letter() -> None:
    html = [("caf\u00e9", "PPPD"), ("x", "D")]
    pdf = [("cafe\u0301", "PPPDD"), ("x", "D")]

    assert compare(html, pdf)["ok"] is True
    assert compare(html, [("cafe\u0301", "PPPPD"), ("x", "D")])["ok"] is False


_COMPARE_WORDS = ("old", "new", "rule", "text", "9059", "income", "non-household", "part-time")
_COMPARE_LABELS = ("P", "D", "I")


def _random_words(rng: random.Random) -> list[tuple[str, str]]:
    words = []
    for _ in range(rng.randrange(1, 12)):
        word = rng.choice(_COMPARE_WORDS)
        if rng.random() < 0.2:  # a word amended inside, like a changed digit
            labels = "".join(rng.choice(_COMPARE_LABELS) for _ in word)
        else:
            labels = rng.choice(_COMPARE_LABELS) * len(word)
        words.append((word, labels))
    return words


def test_property_compare_is_reflexive_and_symmetric() -> None:
    rng = random.Random(5741)
    for _ in range(3000):
        first = _random_words(rng)
        second = _random_words(rng) if rng.random() < 0.5 else list(first)
        assert compare(first, first)["ok"] is True
        assert compare(first, first)["differences"] == []
        assert compare(first, second)["ok"] is compare(second, first)["ok"], (first, second)


def _swap_labels(
    words: list[tuple[str, str]], first: tuple[int, int], second: tuple[int, int]
) -> list[tuple[str, str]]:
    labels = [list(word_labels) for _word, word_labels in words]
    (w1, c1), (w2, c2) = first, second
    labels[w1][c1], labels[w2][c2] = labels[w2][c2], labels[w1][c1]
    return [
        (word, "".join(word_labels)) for (word, _), word_labels in zip(words, labels, strict=True)
    ]


def test_property_compare_fails_any_swap_of_a_deleted_and_an_inserted_character() -> None:
    rng = random.Random(6741)
    checked = 0
    for _ in range(3000):
        words = _random_words(rng)
        positions = {
            label: [
                (word_index, char_index)
                for word_index, (_word, labels) in enumerate(words)
                for char_index, char_label in enumerate(labels)
                if char_label == label
            ]
            for label in ("D", "I")
        }
        deleted, inserted = positions["D"], positions["I"]
        if not deleted or not inserted:
            continue
        swapped = _swap_labels(words, rng.choice(deleted), rng.choice(inserted))
        assert compare(words, swapped)["ok"] is False, (words, swapped)
        # The same swap behind typographic spelling and line-end splits.
        html = [(word.replace("-", "\u2011"), labels) for word, labels in words]
        assert compare(html, _split_hyphenated(swapped, rng))["ok"] is False, (html, swapped)
        assert compare(html, _split_hyphenated(words, rng))["ok"] is True, (html, words)
        checked += 1
    assert checked > 1000


def _split_hyphenated(words: list[tuple[str, str]], rng: random.Random) -> list[tuple[str, str]]:
    """Split some hyphenated words after the hyphen, as a line-end break does."""
    out: list[tuple[str, str]] = []
    for word, labels in words:
        cut = word.find("-") + 1
        if 0 < cut < len(word) and rng.random() < 0.5:
            out.extend([(word[:cut], labels[:cut]), (word[cut:], labels[cut:])])
        else:
            out.append((word, labels))
    return out
