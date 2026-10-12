from __future__ import annotations

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
