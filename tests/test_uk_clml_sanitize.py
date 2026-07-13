"""Tests for volatile CLML editorial-anchor sanitization of UK source captures.

legislation.gov.uk CLML embeds ``key-<32 hex>`` editorial-annotation identifiers
(``ChangeId``, ``CommentaryRef``/``Ref``, ``EffectId``, Commentary ``id``),
optionally with a volatile ``-<epoch-ms>`` suffix. These trip GitHub's Mailgun
API-key push-protection detector and churn on every fetch. Sanitization rewrites
them to deterministic document-local placeholders for the archived source
capture only, leaving provision/coverage/inventory derivations untouched.
"""

import json
import re

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.uk_legislation import (
    _sanitize_clml_editorial_anchors,
    extract_uk_legislation_sections,
)
from axiom_corpus.parsers.clml import parse_section

# The push-protection / Mailgun-detector shape we must guarantee is absent from
# every sanitized capture. Matches the raw editorial anchors, never a placeholder.
_DETECTOR_RE = re.compile(rb"key-[0-9a-f]{32}")

_HEX_A = "a" * 32
_HEX_B = "b" * 32
_HEX_C = "c" * 32


def _fixture_xml(*, sub1_ts: str, sub2_ts: str) -> str:
    """A schedule-paragraph CLML capture parametrized by ``ChangeId`` timestamps.

    Exercises every anchor-bearing attribute observed in real captures:

    * ``Ref`` on a ``CommentaryRef`` (hex A) paired with its ``Commentary`` id,
    * two ``Substitution`` elements sharing commentary hex B but carrying
      different ``ChangeId`` epoch-ms timestamps, each with a ``CommentaryRef``,
    * an ``EffectId`` inside a ``ukm:UnappliedEffects`` block (hex C).
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             DocumentURI="http://www.legislation.gov.uk/uksi/2012/9999"
             RestrictExtent="E+W">
<ukm:Metadata>
    <dc:identifier>http://www.legislation.gov.uk/uksi/2012/9999/schedule/1/paragraph/1</dc:identifier>
    <dc:title>The Sanitizer Fixture Regulations 2012</dc:title>
    <ukm:SecondaryMetadata>
        <ukm:Year Value="2012"/>
        <ukm:Number Value="9999"/>
        <ukm:Made Date="2012-11-16"/>
    </ukm:SecondaryMetadata>
    <ukm:UnappliedEffects>
        <ukm:UnappliedEffect EffectId="key-{_HEX_C}" Type="inserted"/>
    </ukm:UnappliedEffects>
</ukm:Metadata>
<Secondary>
    <Schedules>
        <Schedule DocumentURI="http://www.legislation.gov.uk/uksi/2012/9999/schedule/1"
                  id="schedule-1" RestrictExtent="E+W">
            <Number>SCHEDULE 1</Number>
            <ScheduleBody>
                <P1 DocumentURI="http://www.legislation.gov.uk/uksi/2012/9999/schedule/1/paragraph/1"
                    IdURI="http://www.legislation.gov.uk/id/uksi/2012/9999/schedule/1/paragraph/1"
                    id="schedule-1-paragraph-1">
                    <Pnumber><CommentaryRef Ref="key-{_HEX_A}"/>1</Pnumber>
                    <P1para>
                        <P2 id="schedule-1-paragraph-1-1">
                            <Pnumber>1</Pnumber>
                            <P2para>
                                <Text>The figure is <Substitution ChangeId="key-{_HEX_B}-{sub1_ts}" CommentaryRef="key-{_HEX_B}">£289.00</Substitution> per week rising to <Substitution ChangeId="key-{_HEX_B}-{sub2_ts}" CommentaryRef="key-{_HEX_B}">£375.00</Substitution> per week.</Text>
                            </P2para>
                        </P2>
                    </P1para>
                </P1>
            </ScheduleBody>
        </Schedule>
    </Schedules>
</Secondary>
<Commentaries>
    <Commentary Type="I" id="key-{_HEX_A}"><Para><Text>In force at 27.11.2012.</Text></Para></Commentary>
    <Commentary Type="F" id="key-{_HEX_B}"><Para><Text>Sums substituted (13.2.2026).</Text></Para></Commentary>
</Commentaries>
</Legislation>
"""


# ---------------------------------------------------------------------------
# Pure-function behaviour
# ---------------------------------------------------------------------------


def test_sanitize_first_occurrence_ordering_and_reuse():
    raw = (
        b'<x A="key-'
        + _HEX_A.encode()
        + b'"/><y B="key-'
        + _HEX_B.encode()
        + (b'"/><z A2="key-' + _HEX_A.encode() + b'"/>')
    )
    out = _sanitize_clml_editorial_anchors(raw).decode()

    # First distinct anchor -> key-a1, second distinct -> key-a2; the third
    # token repeats the first digest and therefore reuses key-a1.
    assert out == '<x A="key-a1"/><y B="key-a2"/><z A2="key-a1"/>'


def test_sanitize_drops_timestamp_suffix_and_preserves_pairing():
    raw = _fixture_xml(sub1_ts="1771926836588", sub2_ts="1771926915639").encode()
    out = _sanitize_clml_editorial_anchors(raw).decode()

    # First-occurrence order across the whole document: the ``EffectId`` (hex C)
    # sits in the metadata ``UnappliedEffects`` block and is therefore first
    # (key-a1); then the ``CommentaryRef`` ``Ref`` in the Pnumber (hex A, key-a2);
    # then the ``Substitution`` commentary (hex B, key-a3).
    assert out.count("key-a1") == 1  # EffectId only (hex C)
    assert 'EffectId="key-a1"' in out
    assert out.count("key-a2") == 2  # CommentaryRef Ref + its Commentary id (hex A)
    assert out.count("key-a3") == 5  # 2 ChangeId + 2 CommentaryRef + Commentary id (hex B)

    # The volatile epoch-ms timestamps are gone entirely.
    assert "1771926836588" not in out
    assert "1771926915639" not in out
    # Both substitutions collapse onto the same placeholder (same commentary).
    assert 'ChangeId="key-a3"' in out
    assert 'CommentaryRef="key-a3"' in out
    # The paired Commentary ids resolve to the same placeholders as their refs.
    assert '<Commentary Type="I" id="key-a2">' in out
    assert '<Commentary Type="F" id="key-a3">' in out


def test_sanitize_removes_every_detector_token():
    raw = _fixture_xml(sub1_ts="1771926836588", sub2_ts="1771926915639").encode()
    assert _DETECTOR_RE.search(raw) is not None  # the fixture really has anchors
    out = _sanitize_clml_editorial_anchors(raw)
    assert _DETECTOR_RE.search(out) is None


def test_sanitize_is_idempotent():
    raw = _fixture_xml(sub1_ts="1771926836588", sub2_ts="1771926915639").encode()
    once = _sanitize_clml_editorial_anchors(raw)
    twice = _sanitize_clml_editorial_anchors(once)
    assert once == twice


def test_sanitize_is_deterministic():
    raw = _fixture_xml(sub1_ts="1771926836588", sub2_ts="1771926915639").encode()
    assert _sanitize_clml_editorial_anchors(raw) == _sanitize_clml_editorial_anchors(raw)


def test_sanitize_stable_across_timestamp_churn():
    # A later re-fetch of identical legislation returns fresh epoch-ms ChangeId
    # timestamps. The sanitized capture must be byte-identical regardless.
    first = _sanitize_clml_editorial_anchors(
        _fixture_xml(sub1_ts="1771926836588", sub2_ts="1771926915639").encode()
    )
    refetched = _sanitize_clml_editorial_anchors(
        _fixture_xml(sub1_ts="1799999999999", sub2_ts="1800000000000").encode()
    )
    assert first == refetched


def test_sanitize_noop_when_no_anchors():
    raw = b"<Legislation><Text>No editorial anchors here.</Text></Legislation>"
    assert _sanitize_clml_editorial_anchors(raw) == raw


def test_sanitize_leaves_element_text_untouched():
    # A key-<32 hex> literal in ELEMENT TEXT (not a tag) must be preserved: the
    # archived capture must not diverge from the substantive text that provisions
    # are derived from. The same digest as an attribute anchor is still sanitized.
    body_hex = "d" * 32
    raw = (
        f'<P CommentaryRef="key-{body_hex}"/><Text>The literal key-{body_hex} stays.</Text>'
    ).encode()
    out = _sanitize_clml_editorial_anchors(raw).decode()
    assert out == (f'<P CommentaryRef="key-a1"/><Text>The literal key-{body_hex} stays.</Text>')
    # The detector token survives only where it is genuine element text.
    assert out.count(f"key-{body_hex}") == 1


def test_sanitize_rewrites_effect_uri_anchor_paired_with_effectid():
    # ukm:UnappliedEffects carry the anchor both as an EffectId attribute and as
    # the final path segment of an effect URI; both are inside tags and share the
    # digest, so both collapse onto one placeholder.
    hexv = "e" * 32
    raw = (
        f'<ukm:UnappliedEffect EffectId="key-{hexv}" '
        f'URI="http://www.legislation.gov.uk/id/effect/key-{hexv}"/>'
    ).encode()
    out = _sanitize_clml_editorial_anchors(raw).decode()
    assert out == (
        '<ukm:UnappliedEffect EffectId="key-a1" '
        'URI="http://www.legislation.gov.uk/id/effect/key-a1"/>'
    )
    assert _DETECTOR_RE.search(out.encode()) is None


# ---------------------------------------------------------------------------
# Derivation-neutrality: bodies strip markup, so provisions are unaffected
# ---------------------------------------------------------------------------


def test_provision_body_identical_from_sanitized_and_unsanitized_xml():
    xml = _fixture_xml(sub1_ts="1771926836588", sub2_ts="1771926915639")
    sanitized = _sanitize_clml_editorial_anchors(xml.encode()).decode()

    unsanitized_section = parse_section(xml)
    sanitized_section = parse_section(sanitized)

    assert sanitized_section.text == unsanitized_section.text
    assert sanitized_section.title == unsanitized_section.title
    # The substituted monetary values survive; the anchors never appear in body.
    assert "£289.00" in unsanitized_section.text
    assert "£375.00" in unsanitized_section.text
    assert "key-" not in sanitized_section.text


def test_extract_writes_sanitized_source_but_unaffected_provisions(tmp_path):
    xml = _fixture_xml(sub1_ts="1771926836588", sub2_ts="1771926915639")
    source_xml = tmp_path / "fixture-schedule-1-paragraph-1.xml"
    source_xml.write_text(xml)

    base = tmp_path / "data" / "corpus"
    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-07-13-uk-sanitizer-fixture",
        source_xmls=(source_xml,),
        expression_date="2026-02-13",
    )

    assert report.provisions_written == 1
    assert report.class_reports[0].coverage.complete

    # Archived source capture: sanitized, no detector token, placeholder present.
    stored_sources = list((base / "sources").rglob("*.xml"))
    assert len(stored_sources) == 1
    stored_bytes = stored_sources[0].read_bytes()
    assert _DETECTOR_RE.search(stored_bytes) is None
    assert b"key-a1" in stored_bytes

    # Provision derivation: unaffected, body carries the substantive text only.
    provisions_path = base / "provisions/uk/regulation/2026-07-13-uk-sanitizer-fixture.jsonl"
    row = json.loads(provisions_path.read_text().strip())
    assert row["citation_path"] == "uk/regulation/uksi/2012/9999/schedule/1/paragraph/1"
    assert "£289.00" in row["body"]
    assert "£375.00" in row["body"]
    assert "key-" not in json.dumps(row)


def test_extract_provisions_stable_across_timestamp_churn(tmp_path):
    # End-to-end reproducibility: a re-fetch with churned ChangeId timestamps
    # must yield byte-identical sources *and* provisions.
    def _run(version: str, sub1_ts: str, sub2_ts: str) -> tuple[bytes, bytes]:
        base = tmp_path / version
        source_xml = tmp_path / f"{version}.xml"
        source_xml.write_text(_fixture_xml(sub1_ts=sub1_ts, sub2_ts=sub2_ts))
        extract_uk_legislation_sections(
            CorpusArtifactStore(base / "data" / "corpus"),
            version=version,
            source_xmls=(source_xml,),
            expression_date="2026-02-13",
        )
        source_bytes = next((base / "data" / "corpus" / "sources").rglob("*.xml")).read_bytes()
        provisions = (
            base / "data" / "corpus" / "provisions/uk/regulation" / f"{version}.jsonl"
        ).read_bytes()
        return source_bytes, provisions

    first_source, first_provisions = _run("v-original", "1771926836588", "1771926915639")
    second_source, second_provisions = _run("v-refetch", "1799999999999", "1800000000000")

    # ``version`` is embedded in provision rows, so compare with it neutralized.
    assert first_source == second_source
    assert first_provisions.replace(b"v-original", b"V") == second_provisions.replace(
        b"v-refetch", b"V"
    )
