from __future__ import annotations

import hashlib
import json

from axiom_corpus.corpus.ecfr import EcfrPartTarget, iter_ecfr_title_provisions

TITLE = 49

FIXTURES = {
    "direct_before_subpart": (
        "910",
        """
<ECFR>
  <DIV5 N="910" TYPE="PART">
    <HEAD>Part 910</HEAD>
    <DIV8 N="910.1" TYPE="SECTION">
      <HEAD>§ 910.1 Direct before.</HEAD>
      <P>Independent before-direct body.</P>
    </DIV8>
    <DIV6 N="A" TYPE="SUBPART">
      <HEAD>Subpart A</HEAD>
      <DIV8 N="910.2" TYPE="SECTION">
        <HEAD>§ 910.2 In subpart A.</HEAD>
        <P>Independent before-case subpart body.</P>
      </DIV8>
    </DIV6>
  </DIV5>
</ECFR>
""",
    ),
    "direct_after_subpart": (
        "911",
        """
<ECFR>
  <DIV5 N="911" TYPE="PART">
    <HEAD>Part 911</HEAD>
    <DIV6 N="A" TYPE="SUBPART">
      <HEAD>Subpart A</HEAD>
      <DIV8 N="911.1" TYPE="SECTION">
        <HEAD>§ 911.1 In subpart A.</HEAD>
        <P>Independent after-case subpart body.</P>
      </DIV8>
    </DIV6>
    <DIV8 N="911.2" TYPE="SECTION">
      <HEAD>§ 911.2 Direct after.</HEAD>
      <P>Independent after-direct body.</P>
    </DIV8>
  </DIV5>
</ECFR>
""",
    ),
    "direct_between_two_subparts": (
        "912",
        """
<ECFR>
  <DIV5 N="912" TYPE="PART">
    <HEAD>Part 912</HEAD>
    <DIV6 N="A" TYPE="SUBPART">
      <HEAD>Subpart A</HEAD>
      <DIV8 N="912.1" TYPE="SECTION">
        <HEAD>§ 912.1 In subpart A.</HEAD>
        <P>Independent between-case A body.</P>
      </DIV8>
    </DIV6>
    <DIV8 N="912.2" TYPE="SECTION">
      <HEAD>§ 912.2 Direct between.</HEAD>
      <P>Independent between-direct body.</P>
    </DIV8>
    <DIV6 N="B" TYPE="SUBPART">
      <HEAD>Subpart B</HEAD>
      <DIV8 N="912.3" TYPE="SECTION">
        <HEAD>§ 912.3 In subpart B.</HEAD>
        <P>Independent between-case B body.</P>
      </DIV8>
    </DIV6>
  </DIV5>
</ECFR>
""",
    ),
    "duplicate_direct_and_subpart": (
        "913",
        """
<ECFR>
  <DIV5 N="913" TYPE="PART">
    <HEAD>Part 913</HEAD>
    <DIV6 N="A" TYPE="SUBPART">
      <HEAD>Subpart A</HEAD>
      <DIV8 N="913.7" TYPE="SECTION">
        <HEAD>§ 913.7 Duplicate in subpart.</HEAD>
        <P>Independent duplicate subpart body.</P>
      </DIV8>
    </DIV6>
    <DIV8 N="913.7" TYPE="SECTION">
      <HEAD>§ 913.7 Duplicate direct.</HEAD>
      <P>Independent duplicate direct body.</P>
    </DIV8>
  </DIV5>
</ECFR>
""",
    ),
}

EXPECTED = {
    "direct_before_subpart": (
        ("part", "us/regulation/49/910", None, 0, None, None),
        (
            "section",
            "us/regulation/49/910/1",
            "us/regulation/49/910",
            1,
            None,
            "Independent before-direct body.",
        ),
        (
            "subpart",
            "us/regulation/49/910/subpart-A",
            "us/regulation/49/910",
            1,
            "A",
            None,
        ),
        (
            "section",
            "us/regulation/49/910/2",
            "us/regulation/49/910/subpart-A",
            2,
            "A",
            "Independent before-case subpart body.",
        ),
    ),
    "direct_after_subpart": (
        ("part", "us/regulation/49/911", None, 0, None, None),
        (
            "subpart",
            "us/regulation/49/911/subpart-A",
            "us/regulation/49/911",
            1,
            "A",
            None,
        ),
        (
            "section",
            "us/regulation/49/911/1",
            "us/regulation/49/911/subpart-A",
            2,
            "A",
            "Independent after-case subpart body.",
        ),
        (
            "section",
            "us/regulation/49/911/2",
            "us/regulation/49/911",
            1,
            None,
            "Independent after-direct body.",
        ),
    ),
    "direct_between_two_subparts": (
        ("part", "us/regulation/49/912", None, 0, None, None),
        (
            "subpart",
            "us/regulation/49/912/subpart-A",
            "us/regulation/49/912",
            1,
            "A",
            None,
        ),
        (
            "section",
            "us/regulation/49/912/1",
            "us/regulation/49/912/subpart-A",
            2,
            "A",
            "Independent between-case A body.",
        ),
        (
            "section",
            "us/regulation/49/912/2",
            "us/regulation/49/912",
            1,
            None,
            "Independent between-direct body.",
        ),
        (
            "subpart",
            "us/regulation/49/912/subpart-B",
            "us/regulation/49/912",
            1,
            "B",
            None,
        ),
        (
            "section",
            "us/regulation/49/912/3",
            "us/regulation/49/912/subpart-B",
            2,
            "B",
            "Independent between-case B body.",
        ),
    ),
    "duplicate_direct_and_subpart": (
        ("part", "us/regulation/49/913", None, 0, None, None),
        (
            "subpart",
            "us/regulation/49/913/subpart-A",
            "us/regulation/49/913",
            1,
            "A",
            None,
        ),
        (
            "section",
            "us/regulation/49/913/7",
            "us/regulation/49/913/subpart-A",
            2,
            "A",
            "Independent duplicate subpart body.",
        ),
        (
            "section",
            "us/regulation/49/913/7",
            "us/regulation/49/913",
            1,
            None,
            "Independent duplicate direct body.",
        ),
    ),
}


def run_case(name: str) -> dict[str, object]:
    part, xml_content = FIXTURES[name]
    records = tuple(
        iter_ecfr_title_provisions(
            xml_content,
            (EcfrPartTarget(title=TITLE, part=part),),
            version="round7-independent-order-probe",
            source_path=f"independent-{name}.xml",
        )
    )
    expected = EXPECTED[name]
    actual_shape = [
        (
            record.kind,
            record.citation_path,
            record.parent_citation_path,
            record.level,
            (record.metadata or {}).get("subpart"),
        )
        for record in records
    ]
    expected_shape = [row[:5] for row in expected]
    assert actual_shape == expected_shape, (name, actual_shape, expected_shape)

    body_checks: list[dict[str, object]] = []
    for record, row in zip(records, expected, strict=True):
        body_marker = row[5]
        if body_marker is not None:
            assert record.body is not None, (name, record.citation_path)
            assert body_marker in record.body, (
                name,
                record.citation_path,
                body_marker,
                record.body,
            )
        body_checks.append(
            {
                "citation_path": record.citation_path,
                "body_marker": body_marker,
                "matched": body_marker is None or body_marker in (record.body or ""),
            }
        )

    return {
        "document_order_exact": True,
        "record_count": len(records),
        "records": [
            {
                "kind": record.kind,
                "citation_path": record.citation_path,
                "parent_citation_path": record.parent_citation_path,
                "level": record.level,
                "metadata_subpart": (record.metadata or {}).get("subpart"),
            }
            for record in records
        ],
        "body_checks": body_checks,
    }


def main() -> None:
    results = {name: run_case(name) for name in FIXTURES}
    canonical = json.dumps(results, sort_keys=True, separators=(",", ":")).encode()
    print(
        json.dumps(
            {
                "result_sha256": hashlib.sha256(canonical).hexdigest(),
                "all_cases_passed": True,
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
