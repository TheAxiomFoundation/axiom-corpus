"""Generated operative sections retain normalized text once, in DOM order."""

from html import escape

import pytest
from bs4 import BeautifulSoup
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.test_state_operative_text import _extracted_body, _normalized_tokens, _operative_tokens

_WORDS = st.text(
    alphabet="abc XYZ019,.;:$%&<>é£-\t\n\u00a0\u2011\u2013\u2014",
    min_size=0,
    max_size=35,
)
_INLINE_TAGS = st.sampled_from(["span", "em", "strong", "a"])


@st.composite
def _generated_section(draw, jurisdiction: str):
    """Vary wrappers independently of content, with distinct text-node markers."""
    kinds = ["direct", "inline", "paragraph", "multiple", "nested", "fallback", "table"]
    if jurisdiction == "maine":
        kinds.append("fallback_history")
    chunks = draw(
        st.lists(
            st.tuples(
                st.sampled_from(kinds),
                _WORDS,
                _INLINE_TAGS,
            ),
            min_size=1,
            max_size=12,
        )
    )
    bodies: list[str] = []
    for index, (kind, payload, inline_tag) in enumerate(chunks):
        text = escape(f"NODE{index} {payload} END{index}")
        inline = f"<span>LABEL{index}</span><{inline_tag}>{text}</{inline_tag}>"
        if jurisdiction == "maine":
            paragraph = f'<div class="mrs-text">{inline}</div>'
            if kind == "direct":
                body = text
            elif kind == "inline":
                body = f"<span>{inline}<br>BREAK{index}</span>"
            elif kind == "paragraph":
                body = paragraph
            elif kind == "multiple":
                body = (
                    '<div class="MRSSubSection">'
                    f'<div class="mrs-text"><span class="headnote">HEAD{index}</span>'
                    f"FIRST{index}</div>{paragraph}"
                    f'<div class="mrs-text">LAST{index}</div></div>'
                )
            elif kind == "nested":
                body = (
                    f'<div class="MRSSubSection"><div class="mrs-text">'
                    f'<span class="letpara_id">A{index}.</span>INTRO{index}'
                    f'<div class="mrs-text"><span class="letpara_id">(1{index})</span>'
                    f'{inline}<span class="bhistory">EMBEDDED{index}</span></div>'
                    f"TAIL{index}</div>"
                    f'<div class="MRSSubSection">{paragraph}</div></div>'
                )
            elif kind in {"fallback", "fallback_history"}:
                history = (
                    f'<span class="bhistory">FALLBACK_HISTORY{index}</span>'
                    if kind == "fallback_history"
                    else ""
                )
                body = (
                    f'<div class="MRSSubSection">FALLBACK{index}'
                    f"<p>{inline}</p><div>TAIL{index}</div>{history}</div>"
                )
            else:
                body = (
                    '<div class="MRSSubSection"><div class="mrs-text">'
                    f"INTRO{index}<table><thead><tr><th>HEADER{index}</th>"
                    f"<th>RATE{index}</th></tr></thead><tbody><tr>"
                    f"<td><p>{inline}</p></td><td>CELL{index}<br>AFTER{index}</td>"
                    f"</tr></tbody></table>TAIL{index}</div></div>"
                )
        elif kind == "direct":
            body = text
        elif kind == "inline":
            body = f"<span>{inline}</span><span>SIBLING{index}<br>BREAK{index}</span>"
        elif kind == "paragraph":
            body = f"<span><p>{inline}</p></span>"
        elif kind == "multiple":
            body = f"<div><p>FIRST{index}</p><p>{inline}</p><p>LAST{index}</p></div>"
        elif kind == "nested":
            body = f"<div>INTRO{index}<div><p>{inline}</p></div>TAIL{index}</div>"
        elif kind == "fallback":
            body = f"<div>FALLBACK{index}<em>{inline}</em>TAIL{index}</div>"
        else:
            body = (
                f"<div>INTRO{index}<table><thead><tr><th>HEADER{index}</th>"
                f"<th>RATE{index}</th></tr></thead><tbody><tr>"
                f"<td><p>{inline}</p></td><td>CELL{index}<br>AFTER{index}</td>"
                f"</tr></tbody></table>TAIL{index}</div>"
            )
        bodies.append(body)
        bodies.append(f"<!-- COMMENT{index} -->")

    if jurisdiction == "maine":
        return (
            '<div class="MRSSection"><h3 class="heading_section">§1. Metadata</h3>'
            + "\n".join(bodies)
            + '<div class="note">EDITORIAL</div><div class="qhistory">SECTION HISTORY</div>'
            + '<span class="bhistory">EXTERNAL_HISTORY</span>'
            + '<div class="headnote_blip">STATUS_METADATA</div>'
            + "<script>SCRIPT_METADATA</script><style>STYLE_METADATA</style></div>"
        )
    return (
        '<section class="laws-body">'
        + "\n".join(bodies)
        + '<div class="laws-notice"><p>NOTICE_METADATA</p></div>'
        + "<script>SCRIPT_METADATA</script><style>STYLE_METADATA</style></section>"
    )


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_generated_section_keeps_all_operative_text_once_in_order(jurisdiction: str, data):
    html = data.draw(_generated_section(jurisdiction), label="operative section")
    body = _extracted_body(html, jurisdiction)

    assert body.split() == _operative_tokens(html, jurisdiction)
    for row in BeautifulSoup(html, "lxml").select("tr"):
        expected_row = " ".join(_normalized_tokens(row.get_text(" ", strip=True), jurisdiction))
        assert expected_row in body.splitlines()
