import json
from pathlib import Path

from axiom_corpus.corpus import montana_admin_rules as arm
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.montana_admin_rules import extract_montana_admin_rules

COLLECTION_UUID = "arm-collection"
TITLE_UUID = "title-42"
CHAPTER_UUID = "chapter-42-15"
SUBCHAPTER_UUID = "subchapter-42-15-2"
EFFECTIVE_POLICY_UUID = "policy-effective"
REPEALED_POLICY_UUID = "policy-repealed"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_montana_admin_rules_sources(source_dir: Path) -> None:
    root = source_dir / "montana-rules"
    _write_json(
        root / "collections.json",
        {
            "collections": [
                {
                    "uuid": COLLECTION_UUID,
                    "name": "Administrative Rules of Montana",
                    "category": "COLLECTION",
                }
            ]
        },
    )
    _write_json(
        root / "tree.json",
        {
            "uuid": COLLECTION_UUID,
            "name": "Administrative Rules of Montana",
            "childFolders": [
                {
                    "uuid": TITLE_UUID,
                    "sectionType": "Title",
                    "sectionId": "42",
                    "name": "REVENUE",
                    "childFolders": [
                        {
                            "uuid": CHAPTER_UUID,
                            "sectionType": "Chapter",
                            "sectionId": "42.15",
                            "name": "INCOME TAX",
                            "childFolders": [
                                {
                                    "uuid": SUBCHAPTER_UUID,
                                    "sectionType": "Subchapter",
                                    "sectionId": "42.15.2",
                                    "name": "Montana Additions and Subtractions",
                                    "childFolders": [],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )
    for section_id, uuid, child_policies in (
        ("42", TITLE_UUID, []),
        ("42.15", CHAPTER_UUID, []),
        (
            "42.15.2",
            SUBCHAPTER_UUID,
            [
                {
                    "uuid": EFFECTIVE_POLICY_UUID,
                    "sectionId": "42.15.204",
                    "category": "DOCUMENT",
                    "effectiveStatus": "EFFECTIVE",
                    "substatuses": [],
                    "name": "DEFINITIONS",
                    "policyFields": [
                        {"key": "citation_id", "value": "42.15.204"},
                        {"key": "name", "value": "DEFINITIONS"},
                    ],
                },
                {
                    "uuid": REPEALED_POLICY_UUID,
                    "sectionId": "42.15.215",
                    "category": "DOCUMENT",
                    "effectiveStatus": "INEFFECTIVE",
                    "substatuses": ["REVOKED"],
                    "name": "SENIOR INTEREST INCOME EXCLUSION (REPEALED)",
                    "policyFields": [
                        {"key": "citation_id", "value": "42.15.215"},
                        {"key": "name", "value": "SENIOR INTEREST INCOME EXCLUSION (REPEALED)"},
                    ],
                },
            ],
        ),
    ):
        _write_json(
            root / "sections" / f"{section_id.replace('.', '-')}-{uuid}.json",
            {
                "uuid": uuid,
                "name": section_id,
                "childSections": [],
                "childPolicies": child_policies,
            },
        )
    _write_policy(root, EFFECTIVE_POLICY_UUID, "42.15.204", "DEFINITIONS", "active-version")
    _write_policy(
        root,
        REPEALED_POLICY_UUID,
        "42.15.215",
        "SENIOR INTEREST INCOME EXCLUSION (REPEALED)",
        "repealed-version",
        effective_status="INEFFECTIVE",
        substatuses=["REVOKED"],
    )


def _write_policy(
    root: Path,
    policy_uuid: str,
    citation_id: str,
    name: str,
    version_uuid: str,
    *,
    effective_status: str = "EFFECTIVE",
    substatuses: list[str] | None = None,
) -> None:
    _write_json(
        root / "policies" / f"{citation_id.replace('.', '-')}-{policy_uuid}.json",
        {
            "policy": {
                "uuid": policy_uuid,
                "citationId": citation_id,
                "name": name,
                "effectiveStatus": effective_status,
                "substatuses": substatuses or [],
                "currentVersionUuid": version_uuid,
                "fields": [
                    {"key": "name", "value": name},
                    {"key": "citation_id", "value": citation_id},
                    {"key": "contact_information", "value": "revenue.mt.gov/contact/"},
                ],
                "policyVersions": [
                    {
                        "uuid": version_uuid,
                        "number": "100",
                        "isActive": True,
                        "effectiveStartDate": "2026-01-01",
                        "accessibleHtmlDocument": {
                            "contentType": "text/html",
                            "contentUrl": f"/document/{policy_uuid}",
                            "label": "ACCESSIBLE_HTML",
                        },
                        "fields": [
                            {"key": "version_number", "value": "100"},
                            {"key": "effective_start_date", "value": "2026-01-01"},
                            {
                                "key": "history",
                                "value": "NEW, 2026 MAR p. 1, Eff. 1/1/26.",
                            },
                        ],
                    }
                ],
            }
        },
    )
    _write(
        root / "html" / f"{citation_id.replace('.', '-')}-{policy_uuid}.html",
        f"""<html><body><div id="documentBody">
<p><strong><span citation-id="{citation_id}">{citation_id}</span> {name}</strong></p>
<ol class="decimal">
<li style="counter-set: list-item 1;">A taxpayer must use ARM 42.15.216.</li>
<li style="counter-set: list-item 2;">The term is defined in <span citation-id="15-30-2101, MCA">15-30-2101</span>, MCA.</li>
</ol>
<p><strong>History: </strong>NEW, 2026 MAR p. 1, Eff. 1/1/26.</p>
</div></body></html>""",
    )


def test_extract_montana_admin_rules_local_sources_writes_records(tmp_path):
    source_dir = tmp_path / "montana-source"
    _write_montana_admin_rules_sources(source_dir)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_montana_admin_rules(
        store,
        version="2026-05-19",
        source_dir=source_dir,
        only_title="42",
        workers=1,
    )

    assert report.coverage.complete
    assert report.title_count == 1
    assert report.chapter_count == 1
    assert report.subchapter_count == 1
    assert report.rule_count == 1
    assert report.provisions_written == 5

    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-mt/regulation",
        "us-mt/regulation/title-42",
        "us-mt/regulation/title-42/chapter-42-15",
        "us-mt/regulation/title-42/chapter-42-15/subchapter-42-15-2",
        "us-mt/regulation/title-42/chapter-42-15/subchapter-42-15-2/rule-42-15-204",
    ]
    rule = records[-1]
    assert rule.heading == "DEFINITIONS"
    assert rule.citation_label == "ARM 42.15.204"
    assert rule.body is not None
    assert "(1) A taxpayer must use ARM 42.15.216." in rule.body
    assert rule.metadata is not None
    assert rule.metadata["effective_start_date"] == "2026-01-01"
    assert rule.metadata["references_to"] == [
        "us-mt/statute/15-30-2101",
        "us-mt/regulation/rule-42-15-216",
    ]

    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        record.citation_path for record in records
    ]
    assert inventory[-1].source_format == "montana-rules-html"


def test_extract_montana_admin_rules_include_not_effective(tmp_path):
    source_dir = tmp_path / "montana-source"
    _write_montana_admin_rules_sources(source_dir)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_montana_admin_rules(
        store,
        version="2026-05-19",
        source_dir=source_dir,
        only_section="42.15.2",
        include_not_effective=True,
        workers=1,
    )

    assert report.version == "2026-05-19-include-not-effective-section-42-15-2"
    assert report.rule_count == 2
    records = load_provisions(report.provisions_path)
    assert records[-1].citation_path.endswith("rule-42-15-215")


def test_extract_montana_admin_rules_cli_local_sources(tmp_path, capsys):
    source_dir = tmp_path / "montana-source"
    _write_montana_admin_rules_sources(source_dir)
    base = tmp_path / "corpus"

    exit_code = main(
        [
            "extract-montana-administrative-rules",
            "--base",
            str(base),
            "--version",
            "2026-05-19",
            "--source-dir",
            str(source_dir),
            "--only-title",
            "42",
            "--workers",
            "1",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"jurisdiction": "us-mt"' in out
    assert '"title_count": 1' in out
    assert '"rule_count": 1' in out
    assert '"coverage_complete": true' in out


def test_montana_admin_rules_tree_strips_redundant_section_words():
    nodes = arm._parse_tree_nodes(
        {
            "childFolders": [
                {
                    "uuid": "title-1",
                    "sectionType": "Title",
                    "sectionId": "1",
                    "name": "SECRETARY OF STATE",
                    "childFolders": [
                        {
                            "uuid": "chapter-1-4",
                            "sectionType": "Chapter",
                            "sectionId": "Chapter 1.4",
                            "name": "RULE REVIEW",
                            "childFolders": [
                                {
                                    "uuid": "subchapter-1-4-1",
                                    "sectionType": "Subchapter",
                                    "sectionId": "Subchapter 1.4.1",
                                    "name": "MODEL RULES",
                                    "childFolders": [],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )

    assert [node.citation_path for node in nodes] == [
        "us-mt/regulation/title-1",
        "us-mt/regulation/title-1/chapter-1-4",
        "us-mt/regulation/title-1/chapter-1-4/subchapter-1-4-1",
    ]
    assert nodes[1].label == "ARM Chapter 1.4"
    assert nodes[1].heading == "Chapter 1.4. RULE REVIEW"
    assert [
        node.citation_path
        for node in arm._select_nodes(nodes, only_title=None, only_section="1.4")
    ] == [
        "us-mt/regulation/title-1/chapter-1-4",
        "us-mt/regulation/title-1/chapter-1-4/subchapter-1-4-1",
    ]
