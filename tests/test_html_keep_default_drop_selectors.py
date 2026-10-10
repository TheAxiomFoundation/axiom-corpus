from axiom_corpus.corpus.documents import _extract_html_blocks

# A page whose <nav> is never closed, so the whole body (main content included) sits inside it,
# as on revenue.louisiana.gov (2026-10-06).
UNCLOSED_NAV_PAGE = b"""<!doctype html><html><head><title>Rates</title></head><body>
<nav class="nav-main"><ul><li><a href="/">Home</a></li><li><a href="/forms">Forms</a></li></ul>
<div class="page-content"><main id="main"><h1>What are the individual income tax rates?</h1>
<p>For taxable periods beginning on or after January 1, 2025, the individual income tax rate is a flat 3%.</p>
</main><aside>Related pages</aside></div>
</body></html>"""


def test_default_drops_remove_content_wrapped_in_an_unclosed_nav() -> None:
    blocks = _extract_html_blocks(
        UNCLOSED_NAV_PAGE, source_url="https://example.gov/rates", fallback_title="Rates", extraction=None
    )
    assert "flat 3%" not in " ".join(block.body for block in blocks)


def test_keep_default_drop_selectors_keeps_nav_and_reads_the_selected_root() -> None:
    blocks = _extract_html_blocks(
        UNCLOSED_NAV_PAGE,
        source_url="https://example.gov/rates",
        fallback_title="Rates",
        extraction={"html_content_selector": "main", "html_keep_default_drop_selectors": ["nav"]},
    )
    text = " ".join(block.body for block in blocks)
    assert "flat 3%" in text
    assert "Forms" not in text
    assert "Related pages" not in text


def test_keep_default_drop_selectors_accepts_a_string_and_still_drops_the_rest() -> None:
    page = b"""<html><body><nav><main><header>Site banner</header><p>Body text.</p></main></body></html>"""
    blocks = _extract_html_blocks(
        page,
        source_url="https://example.gov/page",
        fallback_title="Page",
        extraction={"html_content_selector": "main", "html_keep_default_drop_selectors": "nav"},
    )
    text = " ".join(block.body for block in blocks)
    assert "Body text." in text
    assert "Site banner" not in text
