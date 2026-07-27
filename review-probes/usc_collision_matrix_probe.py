from __future__ import annotations

import hashlib
import json

from axiom_corpus.corpus.usc import (
    UscNestedProvision,
    UscParagraph,
    UscSubsection,
    build_usc_inventory_from_xml,
    iter_usc_title_provisions,
    parse_uslm_title,
)


def triplicate_xml(*, idless: bool = False) -> str:
    paragraphs = []
    headings = ("Repealed", "Reenacted", "Third enactment")
    for index, (label, heading) in enumerate(
        zip(("A", "B", "C"), headings, strict=True),
        start=1,
    ):
        id_attribute = "" if idless else f' id="paragraph-{index}"'
        status = ' status="repealed"' if index == 1 else ""
        paragraphs.append(
            f"""
<paragraph{id_attribute}{status} identifier="/us/usc/t99/s1/a/1">
  <num>(1)</num><heading>{heading}</heading><content><p>Body {index}.</p></content>
  <subparagraph id="branch-{label}" identifier="/us/usc/t99/s1/a/1/{label}">
    <num>({label})</num><content><p>Branch {label}.</p></content>
  </subparagraph>
</paragraph>"""
        )
    return f"""
<uscDoc>
  <meta><docNumber>99</docNumber></meta>
  <title id="title-99" identifier="/us/usc/t99">
    <num>Title 99</num><heading>Probe title</heading>
    <section id="section-1" identifier="/us/usc/t99/s1">
      <num>§ 1</num><heading>Triplicate collision</heading>
      <subsection id="subsection-a" identifier="/us/usc/t99/s1/a">
        <num>(a)</num>{"".join(paragraphs)}
      </subsection>
    </section>
  </title>
</uscDoc>"""


def same_id_sibling_xml() -> str:
    return """
<uscDoc>
  <meta><docNumber>99</docNumber></meta>
  <title id="title-99" identifier="/us/usc/t99">
    <num>Title 99</num><heading>Probe title</heading>
    <section id="section-2" identifier="/us/usc/t99/s2">
      <num>§ 2</num><heading>Duplicate source id</heading>
      <subsection id="subsection-a" identifier="/us/usc/t99/s2/a">
        <num>(a)</num>
        <paragraph id="same-id" identifier="/us/usc/t99/s2/a/1">
          <num>(1)</num><heading>First</heading>
          <subparagraph id="branch-A" identifier="/us/usc/t99/s2/a/1/A">
            <num>(A)</num><content><p>First branch.</p></content>
          </subparagraph>
        </paragraph>
        <paragraph id="same-id" identifier="/us/usc/t99/s2/a/2">
          <num>(2)</num><heading>Second</heading>
          <subparagraph id="branch-B" identifier="/us/usc/t99/s2/a/2/B">
            <num>(B)</num><content><p>Second branch.</p></content>
          </subparagraph>
        </paragraph>
      </subsection>
    </section>
  </title>
</uscDoc>"""


def cross_depth_xml() -> str:
    return """
<uscDoc>
  <meta><docNumber>99</docNumber></meta>
  <title id="title-99" identifier="/us/usc/t99">
    <num>Title 99</num><heading>Probe title</heading>
    <section id="shared-id" identifier="/us/usc/t99/s3">
      <num>§ 3</num><heading>Cross-depth ids</heading>
      <subsection id="sub-a" identifier="/us/usc/t99/s3/a">
        <num>(a)</num>
        <paragraph id="shared-id" identifier="/us/usc/t99/s3/a/1">
          <num>(1)</num>
          <subparagraph id="shared-id" identifier="/us/usc/t99/s3/a/1/A">
            <num>(A)</num><content><p>A.</p></content>
          </subparagraph>
        </paragraph>
      </subsection>
      <subsection id="sub-b" identifier="/us/usc/t99/s3/b">
        <num>(b)</num>
        <paragraph id="shared-id" identifier="/us/usc/t99/s3/b/1">
          <num>(1)</num>
          <subparagraph id="shared-id" identifier="/us/usc/t99/s3/b/1/A">
            <num>(A)</num><content><p>B.</p></content>
          </subparagraph>
        </paragraph>
      </subsection>
    </section>
  </title>
</uscDoc>"""


def single_title_xml(title: int) -> str:
    return f"""
<uscDoc>
  <meta><docNumber>{title}</docNumber></meta>
  <title id="title-{title}" identifier="/us/usc/t{title}">
    <num>Title {title}</num><heading>Title {title}</heading>
    <section id="section-{title}-1" identifier="/us/usc/t{title}/s1">
      <num>§ 1</num><heading>Same printed number</heading>
    </section>
  </title>
</uscDoc>"""


def parsed_paths(xml_content: str) -> tuple[list[str], list[dict[str, object]]]:
    document = parse_uslm_title(xml_content)
    paths = [document.citation_path]
    colliding_paragraphs: list[dict[str, object]] = []

    def nested(provision: UscNestedProvision) -> None:
        paths.append(provision.citation_path)
        for child in provision.children:
            nested(child)

    def paragraph(provision: UscParagraph) -> None:
        paths.append(provision.citation_path)
        colliding_paragraphs.append(
            {
                "path": provision.citation_path,
                "heading": provision.heading,
                "body": provision.body,
            }
        )
        for child in provision.children:
            nested(child)

    def subsection(provision: UscSubsection) -> None:
        paths.append(provision.citation_path)
        for child in provision.descendants:
            if isinstance(child, UscParagraph):
                paragraph(child)
            else:
                nested(child)

    for section in document.sections:
        paths.append(section.citation_path)
        for child in section.descendants:
            if isinstance(child, UscSubsection):
                subsection(child)
            else:
                nested(child)
    return paths, colliding_paragraphs


def adapter_result(xml_content: str) -> dict[str, object]:
    paths, paragraphs = parsed_paths(xml_content)
    inventory_paths = [
        item.citation_path for item in build_usc_inventory_from_xml(xml_content).items
    ]
    records = tuple(
        iter_usc_title_provisions(
            xml_content,
            version="round4-collision-matrix",
            source_path="synthetic.xml",
        )
    )
    parent_record = next(
        (record for record in records if record.citation_path.endswith("/a/1")),
        None,
    )
    return {
        "parsed_paths": paths,
        "parsed_path_multiplicity": {
            path: paths.count(path) for path in dict.fromkeys(paths) if paths.count(path) > 1
        },
        "colliding_paragraphs": paragraphs,
        "inventory_paths": inventory_paths,
        "record_paths": [record.citation_path for record in records],
        "normalized_parent": (
            {
                "heading": parent_record.heading,
                "body": parent_record.body,
            }
            if parent_record is not None
            else None
        ),
    }


def main() -> None:
    title_26_paths = set(adapter_result(single_title_xml(26))["inventory_paths"])
    title_42_paths = set(adapter_result(single_title_xml(42))["inventory_paths"])
    result = {
        "triplicate_unique_ids": adapter_result(triplicate_xml()),
        "triplicate_idless_position_fallback": adapter_result(triplicate_xml(idless=True)),
        "same_source_id_siblings_invalid_xml_id": adapter_result(same_id_sibling_xml()),
        "same_source_id_at_different_depths_and_parents": adapter_result(cross_depth_xml()),
        "cross_title": {
            "title_26_paths": sorted(title_26_paths),
            "title_42_paths": sorted(title_42_paths),
            "intersection": sorted(title_26_paths & title_42_paths),
        },
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    print(
        json.dumps(
            {
                "result_sha256": hashlib.sha256(canonical).hexdigest(),
                **result,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
