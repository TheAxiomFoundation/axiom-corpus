"""The california-code-sections adapter's concurrent-version capture (``@all`` / ``@<slug>``).

LegInfo serves a multi-version section as a ``selectFromMultiples`` picker whose
form view state is good for one post. ``FakeLegInfo`` reproduces that: each GET
issues a fresh token, and a post with any other token gets the picker back
(observed live on 2026-09-25 and 2026-09-26).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.states import (
    CaliforniaVersionError,
    _california_section_request,
    _california_section_spec,
    _california_section_token,
    _california_sections_run_id,
    extract_california_code_sections,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
V1_NOTE = (
    "(Amended by Stats. 2024, Ch. 798, Sec. 1. Effective January 1, 2025. Conditionally "
    "inoperative on or after July 1, 2024, by its own provisions.)"
)
V2_NOTE = (
    "(Amended by Stats. 2026, Ch. 310, Sec. 2. Effective September 18, 2026. Conditionally "
    "operative on or after July 1, 2024, by its own provisions.)"
)


@dataclass
class FakeVersion:
    triple: tuple[str, str, str]
    note: str
    paragraphs: tuple[str, ...]
    uid: str

    @property
    def link_text(self) -> str:
        return f"(Amended by Stats. {self.triple[0]}, Ch. {self.triple[1]}, Sec. {self.triple[2]}.)"


@dataclass
class FakeLegInfo:
    versions: list[FakeVersion]
    section: str = "11450"
    single_page: bool = False
    wrong_version_on_post: int | None = None
    change_picker_on_get: int | None = None
    log: list[tuple[str, str]] = field(default_factory=list)
    issued: int = 0
    live_token: str | None = None

    def picker(self, token: str, versions: list[FakeVersion]) -> bytes:
        links = "".join(
            "<a onclick=\"mojarra.jsfcljs(document.getElementById('selectFromMultiples'),"
            f"{{'selectFromMultiples:j_idt139:{i}:j_idt141':'selectFromMultiples:j_idt139:{i}:j_idt141',"
            f"'lawCode':'WIC','sectionNum':'{self.section}.','op_statues':'{v.triple[0]}',"
            f"'op_chapter':'{v.triple[1]}','op_section':'{v.triple[2]}','nodeTreePath':'16.6.2.18'}},'');"
            f'return false">{v.link_text}</a>'
            for i, v in enumerate(versions)
        )
        return (
            '<html><body><form id="selectFromMultiples" action="/faces/selectFromMultiples.xhtml">'
            '<input type="hidden" name="selectFromMultiples" value="selectFromMultiples" />'
            f'<input type="hidden" name="javax.faces.ViewState" value="{token}" />{links}'
            "</form></body></html>"
        ).encode()

    def page(self, version: FakeVersion) -> bytes:
        paragraphs = "".join(f"<p>{text}</p>" for text in version.paragraphs)
        return (
            "<html><head><script>function printPopup(){"
            f"var op_statues = '{version.triple[0]}'; var op_chapter = '{version.triple[1]}'; "
            f"var op_section = '{version.triple[2]}';}}</script></head><body>"
            '<div id="single_law_section"><div id="codeLawSectionNoHead"><div><font>'
            f"<h6><b>{self.section}.  </b></h6>{paragraphs}<i>{version.note}</i>"
            "</font></div></div></div>"
            "<a onclick=\"mojarra.jsfcljs(document.getElementById('displayCodeSection'),"
            f"{{'sectionuid':'{version.uid}'}},'');return false\">PDF</a></body></html>"
        ).encode()

    def session_class(self) -> type:
        fake = self

        class Response:
            status_code = 200

            def __init__(self, content: bytes):
                self.content = content

            def raise_for_status(self) -> None:
                return None

        class Session:
            def __init__(self) -> None:
                self.headers: dict[str, str] = {}

            def get(self, url: str, timeout: float) -> Response:
                fake.log.append(("GET", url))
                if fake.single_page:
                    return Response(fake.page(fake.versions[0]))
                fake.issued += 1
                token = f"state-{fake.issued}"
                fake.live_token = token
                versions = list(fake.versions)
                if (
                    fake.change_picker_on_get is not None
                    and fake.issued >= fake.change_picker_on_get
                ):
                    versions = versions[:1]
                return Response(fake.picker(token, versions))

            def post(self, url: str, data: dict[str, str], timeout: float) -> Response:
                fake.log.append(("POST", url))
                assert url == "https://leginfo.legislature.ca.gov/faces/selectFromMultiples.xhtml"
                token = data["javax.faces.ViewState"]
                if token != fake.live_token:
                    return Response(fake.picker(f"state-{fake.issued}", fake.versions))
                fake.live_token = None
                triple = (data["op_statues"], data["op_chapter"], data["op_section"])
                index = next(i for i, v in enumerate(fake.versions) if v.triple == triple)
                if fake.wrong_version_on_post == index:
                    index = (index + 1) % len(fake.versions)
                return Response(fake.page(fake.versions[index]))

        return Session


def _two_versions() -> list[FakeVersion]:
    return [
        FakeVersion(("2024", "798", "1"), V1_NOTE, ("(a) Version one text.", "(e) $10."), "id_v1"),
        FakeVersion(("2026", "310", "2"), V2_NOTE, ("(a) Version one text.", "(e) $15."), "id_v2"),
    ]


def _install(monkeypatch: pytest.MonkeyPatch, fake: FakeLegInfo) -> None:
    monkeypatch.setattr("axiom_corpus.corpus.states.requests.Session", fake.session_class())
    monkeypatch.setattr("axiom_corpus.corpus.states.time.sleep", lambda _seconds: None)


def _extract(tmp_path: Path, spec: str, *, cache: Path | None = None, base: str = "corpus"):
    store = CorpusArtifactStore(tmp_path / base)
    return extract_california_code_sections(
        store,
        version="2026-09-26-test",
        sections=(spec,),
        download_dir=cache,
        request_delay_seconds=0,
        preserve_tables=True,
    )


def _rows(report) -> dict[str, dict]:
    return {
        record.citation_path: record.to_mapping()
        for record in load_provisions(report.provisions_path)
    }


def test_all_versions_become_variant_rows_and_the_plain_path_is_never_written(
    tmp_path, monkeypatch
):
    fake = FakeLegInfo(_two_versions())
    _install(monkeypatch, fake)
    report = _extract(tmp_path, "WIC:11450@all")
    rows = _rows(report)
    assert list(rows) == [
        "us-ca/statute/wic/11450--inoperative-2024-07-01",
        "us-ca/statute/wic/11450--operative-2024-07-01",
    ]
    assert report.coverage.complete
    assert report.provisions_path.name == "2026-09-26-test-us-ca-sections-wic-11450--all.jsonl"
    v1, v2 = rows.values()
    assert v2["body"].splitlines()[:2] == ["(a) Version one text.", "(e) $15."]
    assert v2["identifiers"]["california:variant"] == "operative-2024-07-01"
    assert v2["source_id"] == "id_v2"
    assert v2["legal_identifier"] == v2["citation_label"] == "Cal. WIC Code § 11450"
    assert v2["source_url"] == (
        "https://leginfo.legislature.ca.gov/faces/printCodeSectionWindow.xhtml?lawCode=WIC"
        "&sectionNum=11450.&op_statues=2026&op_chapter=310&op_section=2"
    )
    metadata = v2["metadata"]
    assert (metadata["op_statues"], metadata["op_chapter"], metadata["op_section"]) == (
        "2026",
        "310",
        "2",
    )
    assert metadata["variant"] == "operative-2024-07-01"
    assert metadata["canonical_citation_path"] == "us-ca/statute/wic/11450"
    assert metadata["status"] == "future_or_conditional"
    assert v1["metadata"]["status"] == "effective_until"
    assert metadata["leginfo_version_label"] == "Stats. 2026, Ch. 310, Sec. 2"
    assert metadata["variant_citation_paths"] == list(rows)
    assert metadata["leginfo_picker"]["index"] == 1
    assert metadata["leginfo_picker"]["source_path"].endswith(
        "/california-leginfo-pickers/WIC-11450.html"
    )
    assert [v["op_section"] for v in metadata["leginfo_picker"]["versions"]] == ["1", "2"]
    assert metadata["leginfo_retrieval"]["method"] == "POST"
    assert "javax.faces.ViewState" not in metadata["leginfo_retrieval"]["fields"]
    assert metadata["leginfo_retrieval"]["fields"]["op_section"] == "2"
    inventory = load_source_inventory(report.inventory_path)
    assert [item.metadata for item in inventory] == [row["metadata"] for row in rows.values()]
    written = sorted(path.name for path in report.source_paths)
    assert written == [
        "WIC-11450--inoperative-2024-07-01.html",
        "WIC-11450--operative-2024-07-01.html",
        "WIC-11450.html",
    ]
    # Every version gets its own GET: a reused view state would get the picker back.
    assert [method for method, _ in fake.log] == ["GET", "POST", "GET", "POST"]


def test_a_slug_selector_keeps_one_version_but_checks_them_all(tmp_path, monkeypatch):
    fake = FakeLegInfo(_two_versions())
    _install(monkeypatch, fake)
    report = _extract(tmp_path, "WIC:11450@operative-2024-07-01")
    assert list(_rows(report)) == ["us-ca/statute/wic/11450--operative-2024-07-01"]
    assert len(fake.log) == 4


def test_a_selector_leginfo_does_not_offer_raises_with_what_it_offers(tmp_path, monkeypatch):
    _install(monkeypatch, FakeLegInfo(_two_versions()))
    with pytest.raises(
        CaliforniaVersionError, match="inoperative-2024-07-01, operative-2024-07-01"
    ):
        _extract(tmp_path, "WIC:11450@operative-2027-01-01")


def test_a_post_that_returns_another_version_raises(tmp_path, monkeypatch):
    _install(monkeypatch, FakeLegInfo(_two_versions(), wrong_version_on_post=1))
    with pytest.raises(CaliforniaVersionError, match="did not return it"):
        _extract(tmp_path, "WIC:11450@all")


def test_a_picker_that_changes_mid_capture_raises(tmp_path, monkeypatch):
    _install(monkeypatch, FakeLegInfo(_two_versions(), change_picker_on_get=2))
    with pytest.raises(CaliforniaVersionError, match="picker changed"):
        _extract(tmp_path, "WIC:11450@all")


def test_two_versions_with_one_slug_raise(tmp_path, monkeypatch):
    versions = _two_versions()
    versions[0].note = V2_NOTE
    _install(monkeypatch, FakeLegInfo(versions))
    with pytest.raises(CaliforniaVersionError, match="share variant slug operative-2024-07-01"):
        _extract(tmp_path, "WIC:11450@all")


def test_a_single_page_section_still_gets_a_variant_row(tmp_path, monkeypatch):
    fake = FakeLegInfo(_two_versions()[1:], single_page=True)
    _install(monkeypatch, fake)
    report = _extract(tmp_path, "WIC:11450@all")
    (row,) = _rows(report).values()
    assert row["citation_path"] == "us-ca/statute/wic/11450--operative-2024-07-01"
    assert "leginfo_picker" not in row["metadata"]
    assert row["metadata"]["leginfo_retrieval"] == {
        "method": "GET",
        "url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
        "?lawCode=WIC&sectionNum=11450",
    }
    assert [path.name for path in report.source_paths] == ["WIC-11450--operative-2024-07-01.html"]


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_a_rerun_from_the_download_cache_is_offline_and_byte_identical(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    _install(monkeypatch, FakeLegInfo(_two_versions()))
    _extract(tmp_path, "WIC:11450@all", cache=cache, base="first")

    class Offline:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def get(self, *args, **kwargs):
            raise AssertionError("network used")

        post = get

    monkeypatch.setattr("axiom_corpus.corpus.states.requests.Session", Offline)
    _extract(tmp_path, "WIC:11450@all", cache=cache, base="second")
    assert _tree(tmp_path / "first") == _tree(tmp_path / "second")
    assert sorted(path.name for path in cache.rglob("*.html")) == [
        "WIC-11450--inoperative-2024-07-01.html",
        "WIC-11450--operative-2024-07-01.html",
        "WIC-11450.html",
    ]


def test_an_unselected_spec_keeps_the_legacy_picker_behaviour(tmp_path, monkeypatch):
    """Documents why the legacy path cannot capture version 2: its second post
    reuses the first GET's view state, gets the picker back, and the first
    version wins at the plain path."""
    fake = FakeLegInfo(_two_versions())
    _install(monkeypatch, fake)
    report = _extract(tmp_path, "WIC:11450")
    (row,) = _rows(report).values()
    assert row["citation_path"] == "us-ca/statute/wic/11450"
    assert row["source_id"] == "id_v1"
    assert row["metadata"]["op_statues"] is None
    assert "variant" not in row["metadata"]
    assert [method for method, _ in fake.log] == ["GET", "POST", "POST"]


def test_section_requests_parse_selectors_and_keep_legacy_specs():
    assert _california_section_request("WIC:11450@all") == ("WIC", "11450", "all")
    assert _california_section_request(" wic 11450 @ Operative-2024-07-01") == (
        "WIC",
        "11450",
        "operative-2024-07-01",
    )
    assert _california_section_request("RTC:17552.3@stats-2002-ch-35-sec-22") == (
        "RTC",
        "17552.3",
        "stats-2002-ch-35-sec-22",
    )
    url = (
        "https://leginfo.legislature.ca.gov/faces/printCodeSectionWindow.xhtml?lawCode=WIC"
        "&sectionNum=11450.&op_statues=2026&op_chapter=310&op_section=2"
    )
    assert _california_section_request(url) == ("WIC", "11450.", None)
    assert _california_section_spec("WIC:11450") == ("WIC", "11450")
    with pytest.raises(ValueError, match="pins a LegInfo version"):
        _california_section_spec("WIC:11450@all")
    with pytest.raises(ValueError, match="version selector"):
        _california_section_request("WIC:11450@latest")


_SECTION_NUMBERS = st.from_regex(r"[1-9][0-9]{0,5}(\.[0-9]{1,3}){0,2}", fullmatch=True)
_CODES = st.sampled_from(["WIC", "RTC", "UIC", "GOV", "HSC"])


@given(st.lists(st.tuples(_CODES, _SECTION_NUMBERS), min_size=1, max_size=12))
def test_unselected_run_ids_are_exactly_the_historical_ones(specs):
    legacy = "-".join(f"{code.lower()}-{_california_section_token(sec)}" for code, sec in specs)
    if len(legacy) > 120:
        import hashlib

        legacy = hashlib.sha256(legacy.encode("utf-8")).hexdigest()[:16]
    expected = f"v-us-ca-sections-{legacy}"
    assert _california_sections_run_id("v", tuple(specs)) == expected
    assert _california_sections_run_id("v", tuple((c, s, None) for c, s in specs)) == expected


# --- the legacy path is byte-identical on committed scopes ------------------------------


@dataclass(frozen=True)
class CommittedScope:
    prefix: str
    version: str
    specs: tuple[str, ...]
    as_of: str
    preserve_tables: bool


COMMITTED_SCOPES = (
    CommittedScope(
        "2026-06-25-ca-wic-calworks",
        "2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452"
        "-wic-11452.018",
        ("WIC:11450", "WIC:11450.12", "WIC:11451.5", "WIC:11452", "WIC:11452.018"),
        "2026-06-25",
        False,
    ),
    CommittedScope(
        "2026-09-23-ca-rtc-sb-1435",
        "2026-09-23-ca-rtc-sb-1435-us-ca-sections-rtc-17024.5-rtc-17052",
        ("RTC:17024.5", "RTC:17052"),
        "2026-09-23",
        True,
    ),
)
_PARENT_FIELDS = ("parent_citation_path", "parent_id")
_DETACH_KEYS = ("self_contained_root", "detached_parent_citation_path")


def _comparable(row: dict) -> dict:
    row = {key: value for key, value in row.items() if key not in _PARENT_FIELDS}
    row["metadata"] = {
        key: value for key, value in row["metadata"].items() if key not in _DETACH_KEYS
    }
    return row


@pytest.mark.parametrize("scope", COMMITTED_SCOPES, ids=lambda scope: scope.prefix)
def test_unselected_specs_still_reproduce_committed_scopes_offline(tmp_path, monkeypatch, scope):
    """Differential check: rerunning a merged scope from its retained LegInfo bytes, with
    the network blocked, gives its committed sources, inventory and coverage byte for
    byte and its committed rows up to the parent detachment applied after extraction."""
    retained = CORPUS_ROOT / f"sources/us-ca/statute/{scope.version}/california-leginfo-sections"
    cache = tmp_path / "cache" / "california-leginfo-sections"
    shutil.copytree(retained, cache)

    class Offline:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def get(self, *args, **kwargs):
            raise AssertionError("network used")

        post = get

    monkeypatch.setattr("axiom_corpus.corpus.states.requests.Session", Offline)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_california_code_sections(
        store,
        version=scope.prefix,
        sections=scope.specs,
        source_as_of=scope.as_of,
        expression_date=scope.as_of,
        download_dir=tmp_path / "cache",
        request_delay_seconds=0,
        preserve_tables=scope.preserve_tables,
    )
    assert report.provisions_path.stem == scope.version
    for kind, suffix in (("inventory", ".json"), ("coverage", ".json")):
        committed = CORPUS_ROOT / f"{kind}/us-ca/statute/{scope.version}{suffix}"
        rerun = tmp_path / f"corpus/{kind}/us-ca/statute/{scope.version}{suffix}"
        assert rerun.read_bytes() == committed.read_bytes(), kind
    for path in report.source_paths:
        assert path.read_bytes() == (retained / path.name).read_bytes()
    committed_rows = [
        json.loads(line)
        for line in (CORPUS_ROOT / f"provisions/us-ca/statute/{scope.version}.jsonl")
        .read_text()
        .splitlines()
    ]
    assert all(row.get("parent_citation_path") is None for row in committed_rows)
    rerun_rows = [record.to_mapping() for record in load_provisions(report.provisions_path)]
    assert [_comparable(row) for row in rerun_rows] == [_comparable(row) for row in committed_rows]
