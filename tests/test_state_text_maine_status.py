from pathlib import Path

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.state_adapters.maine import (
    MAINE_REVISED_STATUTES_INDEX,
    extract_maine_revised_statutes,
    parse_maine_section,
)

FIXTURE = Path(__file__).parent / "fixtures" / "state_text" / "maine-6147.html"
REALLOCATED_BODY = "(REALLOCATED TO TITLE 36, SECTION 6142)"
SECTION_HISTORY = "PL 1977, c. 721, §2 (NEW). PL 1979, c. 127, §203 (RAL)."


@pytest.mark.parametrize("as_bytes", [False, True])
def test_real_maine_6147_reallocated_page_parses_without_operative_text(as_bytes):
    html = FIXTURE.read_bytes() if as_bytes else FIXTURE.read_text(encoding="utf-8")

    parsed = parse_maine_section(html)

    assert parsed.display_section == "6147"
    assert parsed.heading == "Definitions"
    assert parsed.body == REALLOCATED_BODY
    assert parsed.notes == (REALLOCATED_BODY,)
    assert parsed.source_history == (SECTION_HISTORY,)


@pytest.mark.parametrize(
    ("annotation", "status"),
    [
        ("(REPEALED)", "repealed"),
        ("(WHOLE SECTION TEXT REPEALED 1/05/26)", "repealed"),
        ("(WHOLE SECTION TEXT REPEALED 12/31/2027)", "repealed"),
        (REALLOCATED_BODY, None),
        ("(REALLOCATED TO TITLE 30-A, SECTION 2001-A)", None),
    ],
)
def test_explicit_no_current_text_status_is_a_section_body(annotation, status):
    html = (
        '<div class="MRSSection"><h3 class="heading_section">§6147. Definitions</h3>'
        f'<div class="headnote_blip">{annotation}</div></div>'
    )

    parsed = parse_maine_section(html)

    assert parsed.body == annotation
    assert parsed.status == status


@pytest.mark.parametrize(
    "annotation",
    [
        "Scheduled maintenance",
        "(REPEALED Scheduled maintenance)",
        "(REALLOCATED TO Scheduled maintenance)",
        "(REALLOCATED FROM TITLE 36, SECTION 6147)",
        "(WHOLE SECTION TEXT EFFECTIVE 1/05/26)",
        "(WHOLE SECTION TEXT EFFECTIVE UNTIL 1/05/26)",
        "(FUTURE CONTINGENT TERMINATION: See PL 2003, c. 673, Pt. HH, §§6, 7)",
    ],
)
def test_status_annotation_requiring_operative_text_cannot_supply_body(annotation):
    html = (
        '<div class="MRSSection"><h3 class="heading_section">§6147. Definitions</h3>'
        f'<div class="headnote_blip">{annotation}</div></div>'
    )

    with pytest.raises(ValueError, match="lacks operative text or a status body"):
        parse_maine_section(html)


def test_only_explicit_no_current_text_annotations_enter_status_body():
    html = (
        '<div class="MRSSection"><h3 class="heading_section">§6147. Definitions</h3>'
        '<div class="headnote_blip">(REPEALED)</div>'
        '<div class="headnote_blip">Scheduled maintenance</div></div>'
    )

    parsed = parse_maine_section(html)

    assert parsed.body == "(REPEALED)"
    assert parsed.notes == ("(REPEALED)", "Scheduled maintenance")


def test_extract_real_maine_6147_reallocated_page_keeps_complete_coverage(tmp_path):
    source = tmp_path / "source"
    (source / "36").mkdir(parents=True)
    pages = {
        MAINE_REVISED_STATUTES_INDEX: (
            '<ul class="title_list"><li class="right_nav">'
            '<a href="36/title36ch0sec0.html">TITLE 36: TAXATION</a></li></ul>'
        ),
        "36/title36ch0sec0.html": (
            '<div class="title_toc MRSTitle_toclist">'
            '<div class="title_heading"><div>Title 36: TAXATION</div></div>'
            '<div class="MRSChapter_toclist"><a href="./title36ch902sec0.html">'
            "Chapter 902: HOMESTEAD TAX RELIEF ACT OF 1978</a> §6141 - §6151</div></div>"
        ),
        "36/title36ch902sec0.html": (
            '<div class="chapter_toclist"><div class="ch_heading">'
            "Title 36, Chapter 902: HOMESTEAD TAX RELIEF ACT OF 1978</div>"
            '<div class="MRSSection_toclist"><a href="./title36sec6147.html">'
            "36 §6147. Definitions (REALLOCATED TO TITLE 36, SECTION 6142)</a></div></div>"
        ),
        "36/title36sec6147.html": FIXTURE.read_text(encoding="utf-8"),
    }
    for relative_path, html in pages.items():
        (source / relative_path).write_text(html, encoding="utf-8")
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_maine_revised_statutes(
        store,
        version="2026-09-14",
        source_dir=source,
        only_title="36",
        workers=1,
    )

    assert report.coverage.complete is True
    assert report.errors == ()
    assert report.section_count == 1
    assert report.provisions_written == 3
    assert report.coverage.missing_from_provisions == ()
    records = load_provisions(report.provisions_path)
    section = next(record for record in records if record.citation_path == "us-me/statute/36/6147")
    assert section.body == REALLOCATED_BODY
    assert section.metadata["source_history"] == [SECTION_HISTORY]
