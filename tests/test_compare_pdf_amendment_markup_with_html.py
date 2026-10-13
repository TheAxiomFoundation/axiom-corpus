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


def test_html_words_label_line_through_and_underline() -> None:
    assert html_words(HTML) == [
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


def test_marked_text_words_read_wdiff_delimiters() -> None:
    assert marked_text_words("Keep [-old words-] and {+new+}. ([-h-]{+g+})") == [
        ("Keep", "P"),
        ("old", "D"),
        ("words", "D"),
        ("and", "P"),
        ("new.", "IP"),
        ("(hg)", "DIP"),
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


_COMPARE_WORDS = ("old", "new", "rule", "text", "9059", "income")
_COMPARE_LABELS = ("P", "D", "I")


def _random_words(rng: random.Random) -> list[tuple[str, str]]:
    return [
        (rng.choice(_COMPARE_WORDS), rng.choice(_COMPARE_LABELS))
        for _ in range(rng.randrange(1, 12))
    ]


def test_property_compare_is_reflexive_and_symmetric() -> None:
    rng = random.Random(5741)
    for _ in range(3000):
        first = _random_words(rng)
        second = _random_words(rng) if rng.random() < 0.5 else list(first)
        assert compare(first, first)["ok"] is True
        assert compare(first, first)["differences"] == []
        assert compare(first, second)["ok"] is compare(second, first)["ok"], (first, second)


def test_property_compare_fails_any_swap_of_two_marked_labels() -> None:
    rng = random.Random(6741)
    checked = 0
    for _ in range(3000):
        words = _random_words(rng)
        pairs = [
            index
            for index in range(len(words) - 1)
            if {words[index][1], words[index + 1][1]} == {"D", "I"}
        ]
        if not pairs:
            continue
        index = rng.choice(pairs)
        swapped = list(words)
        swapped[index] = (words[index][0], words[index + 1][1])
        swapped[index + 1] = (words[index + 1][0], words[index][1])
        assert compare(words, swapped)["ok"] is False, (words, swapped)
        checked += 1
    assert checked > 500
