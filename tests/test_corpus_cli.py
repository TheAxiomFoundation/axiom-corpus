import json
import subprocess
from base64 import b64encode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.belgium_eli import (
    BelgianELIClassExtractReport,
    BelgianELIExtractReport,
    BelgianMoniteurDiscoveryReport,
    BelgianMoniteurSource,
)
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.coverage import ProvisionCoverageReport
from axiom_corpus.corpus.documents import OfficialDocumentExtractReport
from axiom_corpus.corpus.ecfr import EcfrExtractReport, EcfrInventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.nz_legislation import (
    NZLegislationClassExtractReport,
    NZLegislationExtractReport,
)
from axiom_corpus.corpus.states import StateStatuteExtractReport
from axiom_corpus.corpus.uk_legislation import (
    UKLegislationClassExtractReport,
    UKLegislationExtractReport,
)
from axiom_corpus.corpus.usc import UscExtractReport
from axiom_corpus.fetchers.nz_legislation_api import (
    NZLegislationAPIDownloadReport,
    NZLegislationAPISource,
)

SAMPLE_USLM_CLI = """
<uscDoc identifier="/us/usc/t26">
  <meta><docNumber>26</docNumber></meta>
  <title identifier="/us/usc/t26">
    <heading>Internal Revenue Code</heading>
    <section identifier="/us/usc/t26/s32">
      <num>§ 32.</num>
      <heading>Earned income</heading>
      <content><p>(a) Allowance of credit.</p></content>
    </section>
  </title>
</uscDoc>
"""


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_git_repo(repo):
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("test repo\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "Initial commit")
    return repo


def _test_ingest_keys():
    private_key = Ed25519PrivateKey.generate()
    private_key_text = b64encode(
        private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    ).decode("ascii")
    public_key_text = b64encode(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    return private_key_text, public_key_text


def _set_ingest_keys(monkeypatch):
    private_key, public_key = _test_ingest_keys()
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY", private_key)
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY", public_key)
    return private_key, public_key


def test_validate_manifest_cli(capsys):
    exit_code = main(["validate-manifest", "manifests/corpus.example.yaml"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"ok": true' in output


def test_sign_ingest_manifest_cli_writes_signed_scope_manifest(tmp_path, capsys, monkeypatch):
    repo = _init_git_repo(tmp_path / "repo")
    provision = repo / "data/corpus/provisions/us/statute/2026-06-06.jsonl"
    provision.parent.mkdir(parents=True)
    provision.write_text('{"citation_path":"us/statute/example","body":"Example."}\n')
    _set_ingest_keys(monkeypatch)

    exit_code = main(
        [
            "sign-ingest-manifest",
            "--repo",
            str(repo),
            "--jurisdiction",
            "us",
            "--document-class",
            "statute",
            "--version",
            "2026-06-06",
            "--command",
            "axiom-corpus-ingest extract-example --version 2026-06-06",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"applied_files": 1' in output
    manifest_path = repo / ".axiom/ingest-manifests/us/statute/2026-06-06.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["schema_version"] == "axiom-corpus/ingest-manifest/v1"
    assert manifest["command"]["text"].startswith("axiom-corpus-ingest extract-example")
    assert manifest["applied_files"][0]["path"] == (
        "data/corpus/provisions/us/statute/2026-06-06.jsonl"
    )
    assert manifest["axiom_corpus_git"]["root"] == "."
    assert manifest["signature"]["algorithm"] == "ed25519"


def test_guard_ingested_cli_rejects_unmanifested_corpus_artifact_change(
    tmp_path, capsys, monkeypatch
):
    repo = _init_git_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "feature")
    provision = repo / "data/corpus/provisions/us/statute/2026-06-06.jsonl"
    provision.parent.mkdir(parents=True)
    provision.write_text('{"citation_path":"us/statute/example","body":"Example."}\n')
    _git(repo, "add", "data/corpus/provisions/us/statute/2026-06-06.jsonl")
    _git(repo, "commit", "-m", "Add unmanifested corpus row")
    _set_ingest_keys(monkeypatch)

    exit_code = main(
        [
            "guard-ingested",
            "--repo",
            str(repo),
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["passed"] is False
    assert "Unmanifested corpus artifact change" in payload["issues"][0]


def test_guard_ingested_cli_accepts_signed_corpus_artifact_change(tmp_path, capsys, monkeypatch):
    repo = _init_git_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "feature")
    provision = repo / "data/corpus/provisions/us/statute/2026-06-06.jsonl"
    provision.parent.mkdir(parents=True)
    provision.write_text('{"citation_path":"us/statute/example","body":"Example."}\n')
    _set_ingest_keys(monkeypatch)
    assert (
        main(
            [
                "sign-ingest-manifest",
                "--repo",
                str(repo),
                "--jurisdiction",
                "us",
                "--document-class",
                "statute",
                "--version",
                "2026-06-06",
                "--command",
                "axiom-corpus-ingest extract-example --version 2026-06-06",
            ]
        )
        == 0
    )
    capsys.readouterr()
    _git(repo, "add", "data/corpus/provisions/us/statute/2026-06-06.jsonl")
    _git(repo, "add", ".axiom/ingest-manifests/us/statute/2026-06-06.json")
    _git(repo, "commit", "-m", "Add manifested corpus row")

    exit_code = main(
        [
            "guard-ingested",
            "--repo",
            str(repo),
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    payload = json.loads(output)
    assert payload["passed"] is True
    assert payload["issues"] == []
    assert payload["protected_changes"] == ["data/corpus/provisions/us/statute/2026-06-06.jsonl"]


def test_guard_ingested_cli_rejects_signed_change_without_public_key(tmp_path, capsys, monkeypatch):
    repo = _init_git_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "feature")
    provision = repo / "data/corpus/provisions/us/statute/2026-06-06.jsonl"
    provision.parent.mkdir(parents=True)
    provision.write_text('{"citation_path":"us/statute/example","body":"Example."}\n')
    _set_ingest_keys(monkeypatch)
    assert (
        main(
            [
                "sign-ingest-manifest",
                "--repo",
                str(repo),
                "--jurisdiction",
                "us",
                "--document-class",
                "statute",
                "--version",
                "2026-06-06",
                "--command",
                "axiom-corpus-ingest extract-example --version 2026-06-06",
            ]
        )
        == 0
    )
    capsys.readouterr()
    _git(repo, "add", "data/corpus/provisions/us/statute/2026-06-06.jsonl")
    _git(repo, "add", ".axiom/ingest-manifests/us/statute/2026-06-06.json")
    _git(repo, "commit", "-m", "Add manifested corpus row")
    monkeypatch.delenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY")

    exit_code = main(
        [
            "guard-ingested",
            "--repo",
            str(repo),
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["passed"] is False
    assert "AXIOM_CORPUS_INGEST_PUBLIC_KEY is required" in payload["issues"][0]


def test_guard_ingested_cli_rejects_tampered_ingest_manifest(tmp_path, capsys, monkeypatch):
    repo = _init_git_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "feature")
    provision = repo / "data/corpus/provisions/us/statute/2026-06-06.jsonl"
    provision.parent.mkdir(parents=True)
    provision.write_text('{"citation_path":"us/statute/example","body":"Example."}\n')
    _set_ingest_keys(monkeypatch)
    assert (
        main(
            [
                "sign-ingest-manifest",
                "--repo",
                str(repo),
                "--jurisdiction",
                "us",
                "--document-class",
                "statute",
                "--version",
                "2026-06-06",
                "--command",
                "axiom-corpus-ingest extract-example --version 2026-06-06",
            ]
        )
        == 0
    )
    capsys.readouterr()
    manifest_path = repo / ".axiom/ingest-manifests/us/statute/2026-06-06.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["command"]["text"] = "manual edit"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "data/corpus/provisions/us/statute/2026-06-06.jsonl")
    _git(repo, "add", ".axiom/ingest-manifests/us/statute/2026-06-06.json")
    _git(repo, "commit", "-m", "Add tampered manifest")

    exit_code = main(
        [
            "guard-ingested",
            "--repo",
            str(repo),
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["passed"] is False
    assert "Invalid ingest manifest signature" in payload["issues"][0]


def test_guard_ingested_cli_rejects_committed_tampered_artifact(tmp_path, capsys, monkeypatch):
    repo = _init_git_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "feature")
    provision = repo / "data/corpus/provisions/us/statute/2026-06-06.jsonl"
    provision.parent.mkdir(parents=True)
    provision.write_text('{"citation_path":"us/statute/example","body":"Example."}\n')
    _set_ingest_keys(monkeypatch)
    assert (
        main(
            [
                "sign-ingest-manifest",
                "--repo",
                str(repo),
                "--jurisdiction",
                "us",
                "--document-class",
                "statute",
                "--version",
                "2026-06-06",
                "--command",
                "axiom-corpus-ingest extract-example --version 2026-06-06",
            ]
        )
        == 0
    )
    capsys.readouterr()
    provision.write_text('{"citation_path":"us/statute/example","body":"Changed."}\n')
    _git(repo, "add", "data/corpus/provisions/us/statute/2026-06-06.jsonl")
    _git(repo, "add", ".axiom/ingest-manifests/us/statute/2026-06-06.json")
    _git(repo, "commit", "-m", "Add tampered manifested corpus row")
    provision.write_text('{"citation_path":"us/statute/example","body":"Example."}\n')

    exit_code = main(
        [
            "guard-ingested",
            "--repo",
            str(repo),
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["passed"] is False
    assert "sha256 does not match ingest manifest" in payload["issues"][0]


def test_guard_ingested_cli_rejects_rename_out_of_protected_corpus_path(
    tmp_path, capsys, monkeypatch
):
    repo = _init_git_repo(tmp_path / "repo")
    provision = repo / "data/corpus/provisions/us/statute/2026-06-06.jsonl"
    provision.parent.mkdir(parents=True)
    provision.write_text('{"citation_path":"us/statute/example","body":"Example."}\n')
    _git(repo, "add", "data/corpus/provisions/us/statute/2026-06-06.jsonl")
    _git(repo, "commit", "-m", "Add corpus row")
    _git(repo, "checkout", "-b", "feature")
    moved = repo / "tmp/2026-06-06.jsonl"
    moved.parent.mkdir()
    _git(repo, "mv", "data/corpus/provisions/us/statute/2026-06-06.jsonl", "tmp/2026-06-06.jsonl")
    _git(repo, "commit", "-m", "Move corpus row out of protected path")
    _set_ingest_keys(monkeypatch)

    exit_code = main(
        [
            "guard-ingested",
            "--repo",
            str(repo),
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["protected_changes"] == ["data/corpus/provisions/us/statute/2026-06-06.jsonl"]
    assert "Unmanifested corpus artifact change" in payload["issues"][0]


def test_guard_ingested_cli_accepts_signed_deleted_corpus_artifact(tmp_path, capsys, monkeypatch):
    repo = _init_git_repo(tmp_path / "repo")
    provision = repo / "data/corpus/provisions/us/statute/2026-06-06.jsonl"
    provision.parent.mkdir(parents=True)
    provision.write_text('{"citation_path":"us/statute/example","body":"Example."}\n')
    _git(repo, "add", "data/corpus/provisions/us/statute/2026-06-06.jsonl")
    _git(repo, "commit", "-m", "Add corpus row")
    _git(repo, "checkout", "-b", "feature")
    provision.unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "Remove corpus row")
    _set_ingest_keys(monkeypatch)
    assert (
        main(
            [
                "sign-ingest-manifest",
                "--repo",
                str(repo),
                "--jurisdiction",
                "us",
                "--document-class",
                "statute",
                "--version",
                "2026-06-06",
                "--deleted-file",
                "data/corpus/provisions/us/statute/2026-06-06.jsonl",
                "--command",
                "axiom-corpus-ingest remove-obsolete-scope --version 2026-06-06",
            ]
        )
        == 0
    )
    capsys.readouterr()
    _git(repo, "add", ".axiom/ingest-manifests/us/statute/2026-06-06.json")
    _git(repo, "commit", "-m", "Sign corpus row removal")

    exit_code = main(
        [
            "guard-ingested",
            "--repo",
            str(repo),
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    payload = json.loads(output)
    assert payload["passed"] is True
    assert payload["issues"] == []


def test_guard_ingested_cli_rejects_digest_in_official_documents(tmp_path, capsys, monkeypatch):
    repo = _init_git_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "feature")
    source = (
        repo / "data/corpus/sources/ca/policy/2026-07-01-example/official-documents" / "example.txt"
    )
    source.parent.mkdir(parents=True)
    source.write_text(
        "Title: Example agency page\n"
        "Sources:\n"
        "- https://example.test/official\n\n"
        "This is an agent-written summary, not captured official text.\n"
    )
    _set_ingest_keys(monkeypatch)
    assert (
        main(
            [
                "sign-ingest-manifest",
                "--repo",
                str(repo),
                "--jurisdiction",
                "ca",
                "--document-class",
                "policy",
                "--version",
                "2026-07-01-example",
                "--file",
                "data/corpus/sources/ca/policy/2026-07-01-example/official-documents/example.txt",
                "--command",
                "axiom-corpus-ingest extract-example --version 2026-07-01-example",
            ]
        )
        == 0
    )
    capsys.readouterr()
    _git(repo, "add", "data/corpus/sources/ca/policy/2026-07-01-example")
    _git(repo, "add", ".axiom/ingest-manifests/ca/policy/2026-07-01-example.json")
    _git(repo, "commit", "-m", "Add signed digest as official document")

    exit_code = main(
        [
            "guard-ingested",
            "--repo",
            str(repo),
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["passed"] is False
    assert "looks like an agent digest" in payload["issues"][0]
    assert "Move it to reasoning/" in payload["issues"][0]


def test_guard_ingested_cli_rejects_primary_source_reasoning_inventory(
    tmp_path, capsys, monkeypatch
):
    repo = _init_git_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "feature")
    inventory = repo / "data/corpus/inventory/ca/policy/2026-07-01-example.json"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "citation_path": "ca/policy/example",
                        "source_path": (
                            "sources/ca/policy/2026-07-01-example/reasoning/example.txt"
                        ),
                        "metadata": {"primary_source": True},
                    }
                ]
            },
            indent=2,
        )
        + "\n"
    )
    _set_ingest_keys(monkeypatch)
    assert (
        main(
            [
                "sign-ingest-manifest",
                "--repo",
                str(repo),
                "--jurisdiction",
                "ca",
                "--document-class",
                "policy",
                "--version",
                "2026-07-01-example",
                "--file",
                "data/corpus/inventory/ca/policy/2026-07-01-example.json",
                "--command",
                "axiom-corpus-ingest extract-example --version 2026-07-01-example",
            ]
        )
        == 0
    )
    capsys.readouterr()
    _git(repo, "add", "data/corpus/inventory/ca/policy/2026-07-01-example.json")
    _git(repo, "add", ".axiom/ingest-manifests/ca/policy/2026-07-01-example.json")
    _git(repo, "commit", "-m", "Add signed primary reasoning inventory")

    exit_code = main(
        [
            "guard-ingested",
            "--repo",
            str(repo),
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["passed"] is False
    assert "primary_source true" in payload["issues"][0]
    assert "is under reasoning/" in payload["issues"][0]


def test_inventory_ecfr_cli(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    monkeypatch.setattr(
        cli,
        "build_ecfr_inventory",
        lambda **kwargs: EcfrInventory(
            items=(SourceInventoryItem(citation_path="us/regulation/7/273/1"),),
            title_count=1,
            part_count=1,
        ),
    )
    base = tmp_path / "corpus"

    exit_code = main(
        [
            "inventory-ecfr",
            "--base",
            str(base),
            "--run-id",
            "2026-04-29",
            "--as-of",
            "2024-04-16",
            "--only-title",
            "7",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"items_written": 1' in output
    inventory = json.loads((base / "inventory/us/regulation/2026-04-29-title-7.json").read_text())
    assert inventory["items"][0]["citation_path"] == "us/regulation/7/273/1"


def test_extract_ecfr_cli(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    coverage = ProvisionCoverageReport(
        jurisdiction="us",
        document_class="regulation",
        version="2026-04-29-title-7",
        source_count=1,
        provision_count=1,
        matched_count=1,
        missing_from_provisions=(),
        extra_provisions=(),
    )

    def fake_extract(*args, **kwargs):
        return EcfrExtractReport(
            title_count=1,
            part_count=1,
            provisions_written=1,
            inventory_path=base / "inventory/us/regulation/2026-04-29-title-7.json",
            provisions_path=base / "provisions/us/regulation/2026-04-29-title-7.jsonl",
            coverage_path=base / "coverage/us/regulation/2026-04-29-title-7.json",
            coverage=coverage,
            source_paths=(base / "sources/us/regulation/2026-04-29-title-7/ecfr/title-7.xml",),
        )

    monkeypatch.setattr(cli, "extract_ecfr", fake_extract)

    exit_code = main(
        [
            "extract-ecfr",
            "--base",
            str(base),
            "--version",
            "2026-04-29",
            "--as-of",
            "2024-04-16",
            "--only-title",
            "7",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"provisions_written": 1' in output


def test_extract_official_documents_cli(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text("documents: []\n")
    coverage = ProvisionCoverageReport(
        jurisdiction="us-co",
        document_class="policy",
        version="2026-04-30",
        source_count=1,
        provision_count=1,
        matched_count=1,
        missing_from_provisions=(),
        extra_provisions=(),
    )

    def fake_extract(*args, **kwargs):
        assert kwargs["manifest_path"] == manifest_path
        assert kwargs["source_as_of"] == "2026-04-30"
        return OfficialDocumentExtractReport(
            jurisdiction="us-co",
            document_class="policy",
            document_count=1,
            block_count=3,
            provisions_written=4,
            inventory_path=base / "inventory/us-co/policy/2026-04-30.json",
            provisions_path=base / "provisions/us-co/policy/2026-04-30.jsonl",
            coverage_path=base / "coverage/us-co/policy/2026-04-30.json",
            coverage=coverage,
            source_paths=(base / "sources/us-co/policy/2026-04-30/doc.pdf",),
        )

    monkeypatch.setattr(cli, "extract_official_documents", fake_extract)

    exit_code = main(
        [
            "extract-official-documents",
            "--base",
            str(base),
            "--version",
            "2026-04-30",
            "--manifest",
            str(manifest_path),
            "--as-of",
            "2026-04-30",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"document_class": "policy"' in output
    assert '"block_count": 3' in output


def test_inventory_usc_cli(tmp_path, capsys):
    base = tmp_path / "corpus"
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_text(SAMPLE_USLM_CLI)

    exit_code = main(
        [
            "inventory-usc",
            "--base",
            str(base),
            "--run-id",
            "2026-04-29",
            "--source-xml",
            str(source_xml),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"items_written": 2' in output
    inventory = json.loads((base / "inventory/us/statute/2026-04-29-title-26.json").read_text())
    assert [item["citation_path"] for item in inventory["items"]] == [
        "us/statute/26",
        "us/statute/26/32",
    ]


def test_inventory_usc_cli_filters_sections(tmp_path, capsys):
    base = tmp_path / "corpus"
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_text(SAMPLE_USLM_CLI)

    exit_code = main(
        [
            "inventory-usc",
            "--base",
            str(base),
            "--run-id",
            "2026-04-29-eitc",
            "--source-xml",
            str(source_xml),
            "--section",
            "32",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"items_written": 1' in output
    inventory = json.loads(
        (base / "inventory/us/statute/2026-04-29-eitc-title-26.json").read_text()
    )
    assert [item["citation_path"] for item in inventory["items"]] == [
        "us/statute/26/32",
    ]


def test_extract_usc_cli(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_text(SAMPLE_USLM_CLI)
    coverage = ProvisionCoverageReport(
        jurisdiction="us",
        document_class="statute",
        version="2026-04-29-title-26",
        source_count=2,
        provision_count=2,
        matched_count=2,
        missing_from_provisions=(),
        extra_provisions=(),
    )

    def fake_extract(*args, **kwargs):
        assert kwargs["source_xml"] == source_xml
        assert kwargs["allowed_citation_paths"] is None
        return UscExtractReport(
            title="26",
            title_count=1,
            section_count=1,
            provisions_written=2,
            inventory_path=base / "inventory/us/statute/2026-04-29-title-26.json",
            provisions_path=base / "provisions/us/statute/2026-04-29-title-26.jsonl",
            coverage_path=base / "coverage/us/statute/2026-04-29-title-26.json",
            coverage=coverage,
            source_paths=(base / "sources/us/statute/2026-04-29-title-26/uslm/usc26.xml",),
        )

    monkeypatch.setattr(cli, "extract_usc", fake_extract)

    exit_code = main(
        [
            "extract-usc",
            "--base",
            str(base),
            "--version",
            "2026-04-29",
            "--source-xml",
            str(source_xml),
            "--as-of",
            "2026-04-01",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"provisions_written": 2' in output


def test_extract_usc_cli_filters_sections(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    source_xml = tmp_path / "usc26.xml"
    source_xml.write_text(SAMPLE_USLM_CLI)
    coverage = ProvisionCoverageReport(
        jurisdiction="us",
        document_class="statute",
        version="2026-04-29-eitc-title-26",
        source_count=1,
        provision_count=1,
        matched_count=1,
        missing_from_provisions=(),
        extra_provisions=(),
    )

    def fake_extract(*args, **kwargs):
        assert kwargs["source_xml"] == source_xml
        assert kwargs["allowed_citation_paths"] == {"us/statute/26/32"}
        return UscExtractReport(
            title="26",
            title_count=1,
            section_count=1,
            provisions_written=1,
            inventory_path=base / "inventory/us/statute/2026-04-29-eitc-title-26.json",
            provisions_path=base / "provisions/us/statute/2026-04-29-eitc-title-26.jsonl",
            coverage_path=base / "coverage/us/statute/2026-04-29-eitc-title-26.json",
            coverage=coverage,
            source_paths=(base / "sources/us/statute/2026-04-29-eitc-title-26/uslm/usc26.xml",),
        )

    monkeypatch.setattr(cli, "extract_usc", fake_extract)

    exit_code = main(
        [
            "extract-usc",
            "--base",
            str(base),
            "--version",
            "2026-04-29-eitc",
            "--source-xml",
            str(source_xml),
            "--section",
            "32",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"provisions_written": 1' in output


def test_extract_uk_legislation_cli(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    source_xml = tmp_path / "uk.xml"
    source_xml.write_text("<Legislation />")
    coverage = ProvisionCoverageReport(
        jurisdiction="uk",
        document_class="regulation",
        version="2026-05-29-uk-benefits",
        source_count=1,
        provision_count=1,
        matched_count=1,
        missing_from_provisions=(),
        extra_provisions=(),
    )

    def fake_extract(*args, **kwargs):
        assert kwargs["source_xmls"] == (source_xml,)
        assert kwargs["citations"] == ("uksi/2006/965/regulation/2",)
        return UKLegislationExtractReport(
            version="2026-05-29-uk-benefits",
            source_count=1,
            provisions_written=1,
            class_reports=(
                UKLegislationClassExtractReport(
                    document_class="regulation",
                    source_count=1,
                    provisions_written=1,
                    inventory_path=base / "inventory/uk/regulation/2026-05-29-uk-benefits.json",
                    provisions_path=base / "provisions/uk/regulation/2026-05-29-uk-benefits.jsonl",
                    coverage_path=base / "coverage/uk/regulation/2026-05-29-uk-benefits.json",
                    coverage=coverage,
                    source_paths=(
                        base
                        / "sources/uk/regulation/2026-05-29-uk-benefits/uksi/2006/965/regulation-2.xml",
                    ),
                ),
            ),
        )

    monkeypatch.setattr(cli, "extract_uk_legislation_sections", fake_extract)

    exit_code = main(
        [
            "extract-uk-legislation",
            "--base",
            str(base),
            "--version",
            "2026-05-29-uk-benefits",
            "--source-xml",
            str(source_xml),
            "--citation",
            "uksi/2006/965/regulation/2",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"jurisdiction": "uk"' in output
    assert '"document_class": "regulation"' in output


def test_extract_nz_legislation_cli(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    source_xml = tmp_path / "nz.xml"
    source_xml.write_text("<act />")
    source_dir = tmp_path / "pco"
    source_dir.mkdir()
    coverage = ProvisionCoverageReport(
        jurisdiction="nz",
        document_class="statute",
        version="2026-06-16-nz",
        source_count=1,
        provision_count=1,
        matched_count=1,
        missing_from_provisions=(),
        extra_provisions=(),
    )

    def fake_extract(*args, **kwargs):
        assert kwargs["source_xmls"] == (source_xml,)
        assert kwargs["source_dir"] == source_dir
        assert kwargs["source_pattern"] == "*.xml"
        assert kwargs["source_as_of"] == "2026-06-16"
        assert kwargs["expression_date"].isoformat() == "2026-04-01"
        assert kwargs["limit"] == 10
        return NZLegislationExtractReport(
            version="2026-06-16-nz",
            source_count=1,
            provisions_written=1,
            class_reports=(
                NZLegislationClassExtractReport(
                    document_class="statute",
                    source_count=1,
                    provisions_written=1,
                    inventory_path=base / "inventory/nz/statute/2026-06-16-nz.json",
                    provisions_path=base / "provisions/nz/statute/2026-06-16-nz.jsonl",
                    coverage_path=base / "coverage/nz/statute/2026-06-16-nz.json",
                    coverage=coverage,
                    source_paths=(
                        base / "sources/nz/statute/2026-06-16-nz/act/public/2007/0097/wholeof.xml",
                    ),
                ),
            ),
        )

    monkeypatch.setattr(cli, "extract_nz_legislation", fake_extract)

    exit_code = main(
        [
            "extract-nz-legislation",
            "--base",
            str(base),
            "--version",
            "2026-06-16-nz",
            "--source-xml",
            str(source_xml),
            "--source-dir",
            str(source_dir),
            "--as-of",
            "2026-06-16",
            "--expression-date",
            "2026-04-01",
            "--limit",
            "10",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"jurisdiction": "nz"' in output
    assert '"document_class": "statute"' in output


def test_extract_belgian_eli_cli(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    source_html = tmp_path / "be.html"
    source_html.write_text("<html></html>")
    source_dir = tmp_path / "eli"
    source_dir.mkdir()
    manifest_path = tmp_path / "be-brussels.yaml"
    manifest_path.write_text(
        """
version: "2026-06-30-be"
sources:
  - source_id: brussels-family-benefits
    jurisdiction: be-bru
    document_class: statute
    adapter: belgian-eli
    source_url: https://www.ejustice.just.fgov.be/eli/ordonnance/2019/04/25/2019012118/justel
""".lstrip()
    )
    coverage = ProvisionCoverageReport(
        jurisdiction="be-bru",
        document_class="statute",
        version="2026-06-30-be",
        source_count=1,
        provision_count=1,
        matched_count=1,
        missing_from_provisions=(),
        extra_provisions=(),
    )

    def fake_extract(*args, **kwargs):
        assert kwargs["source_htmls"] == (source_html,)
        assert kwargs["source_dir"] == source_dir
        assert kwargs["source_pattern"] == "*.html"
        assert kwargs["source_urls"] == (
            "https://www.ejustice.just.fgov.be/eli/arrete/2002/07/11/2002022564/justel",
            "https://www.ejustice.just.fgov.be/eli/ordonnance/2019/04/25/2019012118/justel",
        )
        assert kwargs["source_as_of"] == "2026-06-30"
        assert kwargs["expression_date"].isoformat() == "2026-01-01"
        assert kwargs["request_timeout"] == 5.0
        assert kwargs["limit"] == 10
        return BelgianELIExtractReport(
            version="2026-06-30-be",
            source_count=1,
            provisions_written=1,
            class_reports=(
                BelgianELIClassExtractReport(
                    jurisdiction="be-bru",
                    document_class="statute",
                    source_count=1,
                    provisions_written=1,
                    inventory_path=base / "inventory/be-bru/statute/2026-06-30-be.json",
                    provisions_path=base / "provisions/be-bru/statute/2026-06-30-be.jsonl",
                    coverage_path=base / "coverage/be-bru/statute/2026-06-30-be.json",
                    coverage=coverage,
                    source_paths=(
                        base
                        / "sources/be-bru/statute/2026-06-30-be/eli/ordonnance/2019/04/25/2019012118/justel.html",
                    ),
                ),
            ),
        )

    monkeypatch.setattr(cli, "extract_belgian_eli", fake_extract)

    exit_code = main(
        [
            "extract-belgian-eli",
            "--base",
            str(base),
            "--version",
            "2026-06-30-be",
            "--manifest",
            str(manifest_path),
            "--source-html",
            str(source_html),
            "--source-dir",
            str(source_dir),
            "--source-url",
            "https://www.ejustice.just.fgov.be/eli/arrete/2002/07/11/2002022564/justel",
            "--as-of",
            "2026-06-30",
            "--expression-date",
            "2026-01-01",
            "--request-timeout",
            "5",
            "--limit",
            "10",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"jurisdiction": "be-bru"' in output
    assert '"document_class": "statute"' in output


def test_discover_belgian_moniteur_cli_writes_manifest(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    manifest_path = tmp_path / "be-full-moniteur.yaml"

    def fake_discover(*, start_date, end_date, language, request_timeout, limit, max_editions):
        assert start_date == "2026-06-01"
        assert end_date == "2026-06-01"
        assert language == "fr"
        assert request_timeout == 5.0
        assert limit == 10
        assert max_editions == 4
        return BelgianMoniteurDiscoveryReport(
            start_date="2026-06-01",
            end_date="2026-06-01",
            language="fr",
            summary_pages_fetched=2,
            sources=(
                BelgianMoniteurSource(
                    source_id="be-statute-loi-20260530-2026003986",
                    source_url=(
                        "https://www.ejustice.just.fgov.be/cgi/article.pl?"
                        "language=fr&sum_date=2026-06-01&s_editie=2&"
                        "numac_search=2026003986&view_numac="
                    ),
                    jurisdiction="be",
                    document_class="statute",
                    document_type="loi",
                    numac="2026003986",
                    title="30 mai 2026. - Loi-programme, p. 29687.",
                    publication_date="2026-06-01",
                    edition=2,
                    section_title="Lois, décrets, ordonnances et règlements",
                    moniteur_url=(
                        "https://www.ejustice.just.fgov.be/eli/loi/2026/05/30/2026003986/moniteur"
                    ),
                    justel_url=(
                        "https://www.ejustice.just.fgov.be/eli/loi/2026/05/30/2026003986/justel"
                    ),
                    authority="Service public fédéral Chancellerie du Premier Ministre",
                ),
            ),
        )

    monkeypatch.setattr(cli, "discover_belgian_moniteur_sources", fake_discover)

    exit_code = main(
        [
            "discover-belgian-moniteur",
            "--start-date",
            "2026-06-01",
            "--end-date",
            "2026-06-01",
            "--version",
            "2026-06-30-be-full-moniteur",
            "--request-timeout",
            "5",
            "--limit",
            "10",
            "--max-editions",
            "4",
            "--manifest-output",
            str(manifest_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"source_count": 1' in output
    assert manifest_path.read_text().startswith("version: 2026-06-30-be-full-moniteur")
    assert "adapter: belgian-eli" in manifest_path.read_text()
    assert "source_status: official_original_publication" in manifest_path.read_text()


def test_download_nz_legislation_api_cli_uses_env_key(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    output_dir = tmp_path / "xml"
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setenv("NZ_LEGISLATION_API_KEY", "test-key")

    def fake_download(*args, **kwargs):
        assert args == (output_dir,)
        assert kwargs["api_key"] == "test-key"
        assert kwargs["legislation_types"] == ("act",)
        assert kwargs["publisher"] == "Parliamentary Counsel Office"
        assert kwargs["search_term"] == "Income Tax"
        assert kwargs["per_page"] == 100
        assert kwargs["max_pages"] == 1
        assert kwargs["limit"] == 5
        assert kwargs["resume"] is True
        assert kwargs["allow_failures"] is False
        assert kwargs["manifest_path"] == manifest_path
        source = NZLegislationAPISource(
            work_id="act_public_2007_97",
            version_id="act_public_2007_97_en_2026-04-01",
            title="Income Tax Act 2007",
            legislation_type="act",
            legislation_status="in_force",
            xml_url="https://www.legislation.govt.nz/act/public/2007/97/en/2026-04-01.xml/",
            relative_path="act/public/2007/97/act_public_2007_97_en_2026-04-01.xml",
            metadata={},
        )
        return NZLegislationAPIDownloadReport(
            output_dir=output_dir,
            discovered_count=1,
            downloaded_count=1,
            skipped_count=0,
            failed_count=0,
            sources=(source,),
            downloaded_paths=(output_dir / source.relative_path,),
            skipped_paths=(),
            failures=(),
            manifest_path=manifest_path,
        )

    monkeypatch.setattr(cli, "download_nz_legislation_api_sources", fake_download)

    exit_code = main(
        [
            "download-nz-legislation-api",
            "--output-dir",
            str(output_dir),
            "--legislation-type",
            "act",
            "--search-term",
            "Income Tax",
            "--max-pages",
            "1",
            "--limit",
            "5",
            "--manifest-path",
            str(manifest_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"jurisdiction": "nz"' in output
    assert '"downloaded_count": 1' in output
    assert "test-key" not in output


def test_extract_usc_dir_cli(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    source_dir = tmp_path / "uscode"
    source_dir.mkdir()
    coverage = ProvisionCoverageReport(
        jurisdiction="us",
        document_class="statute",
        version="2026-04-29",
        source_count=2,
        provision_count=2,
        matched_count=2,
        missing_from_provisions=(),
        extra_provisions=(),
    )

    def fake_extract_dir(*args, **kwargs):
        assert kwargs["source_dir"] == source_dir
        return UscExtractReport(
            title=None,
            title_count=53,
            section_count=1,
            provisions_written=2,
            inventory_path=base / "inventory/us/statute/2026-04-29.json",
            provisions_path=base / "provisions/us/statute/2026-04-29.jsonl",
            coverage_path=base / "coverage/us/statute/2026-04-29.json",
            coverage=coverage,
            source_paths=(base / "sources/us/statute/2026-04-29/uslm/usc26.xml",),
        )

    monkeypatch.setattr(cli, "extract_usc_directory", fake_extract_dir)

    exit_code = main(
        [
            "extract-usc-dir",
            "--base",
            str(base),
            "--version",
            "2026-04-29",
            "--source-dir",
            str(source_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"title_count": 53' in output


def test_export_supabase_cli(tmp_path, capsys):
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us", "regulation", "2026-04-29")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/273",
                heading="Certification of Eligible Households",
                version="2026-04-29",
            )
        ],
    )
    out = tmp_path / "supabase.jsonl"

    exit_code = main(["export-supabase", "--provisions", str(provisions), "--output", str(out)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"rows_written": 1' in output
    assert json.loads(out.read_text())["doc_type"] == "regulation"


def test_load_supabase_cli_dry_run(tmp_path, capsys):
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us", "regulation", "2026-04-29")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/273",
                heading="Certification of Eligible Households",
                version="2026-04-29",
            )
        ],
    )

    exit_code = main(["load-supabase", "--provisions", str(provisions), "--dry-run"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["rows_total"] == 1
    assert payload["rows_loaded"] == 0


def test_load_supabase_cli_replace_scope_dry_run(tmp_path, capsys):
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us-ga", "statute", "2022-11-01")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us-ga",
                document_class="statute",
                citation_path="us-ga/statute/1",
                heading="Title 1",
                version="2022-11-01",
            )
        ],
    )

    exit_code = main(
        [
            "load-supabase",
            "--provisions",
            str(provisions),
            "--replace-scope",
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["replace_scope"]["dry_run"] is True
    assert payload["rows_total"] == 1


def test_load_supabase_cli_dry_run_skips_navigation_writes(tmp_path, capsys):
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us-co", "statute", "2026-05-05")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
            )
        ],
    )

    exit_code = main(["load-supabase", "--provisions", str(provisions), "--dry-run"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    # Default --build-navigation is on, but dry-run still must not contact the API.
    assert payload["navigation"] == {"skipped": "dry-run"}


def test_load_supabase_cli_no_build_navigation_omits_navigation_section(tmp_path, capsys):
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us-co", "statute", "2026-05-05")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
            )
        ],
    )

    exit_code = main(
        [
            "load-supabase",
            "--provisions",
            str(provisions),
            "--dry-run",
            "--no-build-navigation",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "navigation" not in payload


def test_load_supabase_cli_rebuilds_navigation_after_provisions_load(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore
    from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport
    from axiom_corpus.corpus.supabase import SupabaseLoadReport

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us-co", "statute", "2026-05-05")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
                metadata={"status": "current"},
            ),
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39/article-22",
                parent_citation_path="us-co/statute/title-39",
                version="2026-05-05",
            ),
        ],
    )

    monkeypatch.setattr(cli, "resolve_service_key", lambda *a, **kw: "service")
    monkeypatch.setattr(
        cli,
        "load_provisions_to_supabase",
        lambda *a, **kw: SupabaseLoadReport(rows_total=1, rows_loaded=1, chunk_count=1),
    )
    captured: dict[str, object] = {}

    def fail_fetch_for_navigation(**kwargs):
        raise AssertionError("default navigation rebuild should use local provisions")

    monkeypatch.setattr(cli, "fetch_provisions_for_navigation", fail_fetch_for_navigation)
    monkeypatch.setattr(
        cli,
        "fetch_navigation_statuses",
        lambda **kwargs: {"us-co/statute/title-39/article-22": "inactive"},
    )

    def fake_writer(nodes, **kwargs):
        captured["node_paths"] = [n.path for n in nodes]
        captured["provision_ids"] = [n.provision_id for n in nodes]
        captured["statuses"] = {n.path: n.status for n in nodes}
        captured["replace_scope"] = kwargs.get("replace_scope")
        captured["replace_scopes"] = kwargs.get("replace_scopes")
        return NavigationSupabaseWriteReport(
            rows_total=len(captured["node_paths"]),
            rows_loaded=len(captured["node_paths"]),
            chunk_count=1,
            scopes_replaced=(("us-co", "statute", "2026-05-05"),),
            rows_deleted=0,
            delete_chunk_count=0,
        )

    monkeypatch.setattr(cli, "write_navigation_nodes_to_supabase", fake_writer)

    exit_code = main(["load-supabase", "--provisions", str(provisions)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["replace_scope"] is True
    assert captured["replace_scopes"] == (("us-co", "statute", "2026-05-05"),)
    assert set(captured["node_paths"]) == {
        "us-co/statute/title-39",
        "us-co/statute/title-39/article-22",
    }
    assert captured["statuses"] == {
        "us-co/statute/title-39": "current",
        "us-co/statute/title-39/article-22": "inactive",
    }
    assert payload["navigation"]["rows_loaded"] == 2
    assert payload["navigation"]["scopes_replaced"] == [["us-co", "statute", "2026-05-05"]]
    assert payload["navigation"]["source"] == "local"


def test_load_supabase_cli_can_rebuild_navigation_from_supabase(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore
    from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport
    from axiom_corpus.corpus.supabase import SupabaseLoadReport

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us-co", "statute", "2026-05-05")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
            ),
        ],
    )

    monkeypatch.setattr(cli, "resolve_service_key", lambda *a, **kw: "service")
    monkeypatch.setattr(
        cli,
        "load_provisions_to_supabase",
        lambda *a, **kw: SupabaseLoadReport(rows_total=1, rows_loaded=1, chunk_count=1),
    )
    captured: dict[str, object] = {}

    def fake_fetch_for_navigation(**kwargs):
        captured["fetch_scope"] = (
            kwargs["jurisdiction"],
            kwargs["doc_type"],
            kwargs["version"],
        )
        return (
            ProvisionRecord(
                id="11111111-1111-1111-1111-111111111111",
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
            ),
        )

    monkeypatch.setattr(cli, "fetch_provisions_for_navigation", fake_fetch_for_navigation)
    monkeypatch.setattr(cli, "fetch_navigation_statuses", lambda **kwargs: {})

    def fake_writer(nodes, **kwargs):
        captured["provision_ids"] = [n.provision_id for n in nodes]
        return NavigationSupabaseWriteReport(
            rows_total=len(captured["provision_ids"]),
            rows_loaded=len(captured["provision_ids"]),
            chunk_count=1,
            scopes_replaced=(("us-co", "statute", "2026-05-05"),),
            rows_deleted=0,
            delete_chunk_count=0,
        )

    monkeypatch.setattr(cli, "write_navigation_nodes_to_supabase", fake_writer)

    exit_code = main(
        [
            "load-supabase",
            "--provisions",
            str(provisions),
            "--navigation-source",
            "supabase",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["fetch_scope"] == ("us-co", "statute", "2026-05-05")
    assert captured["provision_ids"] == ["11111111-1111-1111-1111-111111111111"]
    assert payload["navigation"]["source"] == "supabase"


def test_build_navigation_index_all_requires_input_source():
    try:
        main(["build-navigation-index", "--all", "--dry-run"])
    except SystemExit as exc:
        assert str(exc) == "build-navigation-index --all requires --provisions or --from-supabase"
    else:
        raise AssertionError("expected SystemExit")


def test_build_navigation_index_passes_explicit_empty_replace_scope(capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli
    from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport

    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "resolve_service_key", lambda *a, **kw: "service")
    monkeypatch.setattr(cli, "fetch_provisions_for_navigation", lambda **kwargs: ())
    monkeypatch.setattr(cli, "fetch_navigation_statuses", lambda **kwargs: {})

    def fake_writer(nodes, **kwargs):
        captured["nodes"] = tuple(nodes)
        captured["replace_scopes"] = kwargs.get("replace_scopes")
        return NavigationSupabaseWriteReport(
            rows_total=0,
            rows_loaded=0,
            chunk_count=0,
            scopes_replaced=(("us-co", "statute", None),),
            rows_deleted=3,
            delete_chunk_count=1,
        )

    monkeypatch.setattr(cli, "write_navigation_nodes_to_supabase", fake_writer)

    exit_code = main(
        [
            "build-navigation-index",
            "--from-supabase",
            "--jurisdiction",
            "us-co",
            "--doc-type",
            "statute",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["nodes"] == ()
    assert captured["replace_scopes"] == (("us-co", "statute", None),)
    assert payload["nodes_built"] == 0
    assert payload["supabase"]["rows_deleted"] == 3


def test_build_navigation_index_from_supabase_preserves_existing_status(capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli
    from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport

    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "resolve_service_key", lambda *a, **kw: "service")
    monkeypatch.setattr(
        cli,
        "fetch_provisions_for_navigation",
        lambda **kwargs: (
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                id="11111111-1111-1111-1111-111111111111",
                version="2026-05-05",
            ),
        ),
    )
    monkeypatch.setattr(
        cli,
        "fetch_navigation_statuses",
        lambda **kwargs: {"us-co/statute/title-39": "current"},
    )

    def fake_writer(nodes, **kwargs):
        captured["statuses"] = {node.path: node.status for node in nodes}
        return NavigationSupabaseWriteReport(
            rows_total=1,
            rows_loaded=1,
            chunk_count=1,
            scopes_replaced=(("us-co", "statute", "2026-05-05"),),
            rows_deleted=0,
            delete_chunk_count=0,
        )

    monkeypatch.setattr(cli, "write_navigation_nodes_to_supabase", fake_writer)

    exit_code = main(
        [
            "build-navigation-index",
            "--from-supabase",
            "--jurisdiction",
            "us-co",
            "--doc-type",
            "statute",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["statuses"] == {"us-co/statute/title-39": "current"}
    assert payload["nodes_built"] == 1


def test_build_navigation_index_from_provisions_preserves_existing_status(
    tmp_path, capsys, monkeypatch
):
    import axiom_corpus.corpus.cli as cli
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore
    from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us-co", "statute", "2026-05-05")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
            )
        ],
    )

    monkeypatch.setattr(cli, "resolve_service_key", lambda *a, **kw: "service")
    monkeypatch.setattr(
        cli,
        "fetch_navigation_statuses",
        lambda **kw: {"us-co/statute/title-39": "current"},
    )

    captured: dict[str, object] = {}

    def fake_writer(nodes, **kwargs):
        captured["statuses"] = {node.path: node.status for node in nodes}
        captured["replace_scope"] = kwargs.get("replace_scope")
        return NavigationSupabaseWriteReport(
            rows_total=1,
            rows_loaded=1,
            chunk_count=1,
            scopes_replaced=(),
            rows_deleted=0,
            delete_chunk_count=0,
        )

    monkeypatch.setattr(cli, "write_navigation_nodes_to_supabase", fake_writer)

    exit_code = main(["build-navigation-index", "--provisions", str(provisions)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["statuses"] == {"us-co/statute/title-39": "current"}
    assert captured["replace_scope"] is False
    assert payload["preserved_status_count"] == 1
    assert payload["replace_scope"] is False


def test_build_navigation_index_from_provisions_replace_scope_is_explicit(
    tmp_path, capsys, monkeypatch
):
    import axiom_corpus.corpus.cli as cli
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore
    from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us-co", "statute", "2026-05-05")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
            )
        ],
    )

    monkeypatch.setattr(cli, "resolve_service_key", lambda *a, **kw: "service")
    monkeypatch.setattr(cli, "fetch_navigation_statuses", lambda **kw: {})
    captured: dict[str, object] = {}

    def fake_writer(nodes, **kwargs):
        captured["replace_scope"] = kwargs.get("replace_scope")
        return NavigationSupabaseWriteReport(
            rows_total=1,
            rows_loaded=1,
            chunk_count=1,
            scopes_replaced=(("us-co", "statute", "2026-05-05"),),
            rows_deleted=0,
            delete_chunk_count=0,
        )

    monkeypatch.setattr(cli, "write_navigation_nodes_to_supabase", fake_writer)

    exit_code = main(
        [
            "build-navigation-index",
            "--provisions",
            str(provisions),
            "--replace-scope",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["replace_scope"] is True
    assert payload["replace_scope"] is True


def test_build_navigation_index_no_preserve_statuses_skips_status_fetch(
    tmp_path, capsys, monkeypatch
):
    import axiom_corpus.corpus.cli as cli
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore
    from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us-co", "statute", "2026-05-05")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
            )
        ],
    )

    monkeypatch.setattr(cli, "resolve_service_key", lambda *a, **kw: "service")

    def fail_status_fetch(**kw):
        raise AssertionError("--no-preserve-statuses must skip the status fetch")

    monkeypatch.setattr(cli, "fetch_navigation_statuses", fail_status_fetch)
    monkeypatch.setattr(
        cli,
        "write_navigation_nodes_to_supabase",
        lambda nodes, **kw: NavigationSupabaseWriteReport(
            rows_total=1,
            rows_loaded=1,
            chunk_count=1,
            scopes_replaced=(("us-co", "statute", "2026-05-05"),),
            rows_deleted=0,
            delete_chunk_count=0,
        ),
    )

    exit_code = main(
        [
            "build-navigation-index",
            "--provisions",
            str(provisions),
            "--no-preserve-statuses",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["preserved_status_count"] == 0


def test_load_supabase_no_preserve_navigation_statuses_skips_status_fetch(
    tmp_path, capsys, monkeypatch
):
    import axiom_corpus.corpus.cli as cli
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore
    from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport
    from axiom_corpus.corpus.supabase import SupabaseLoadReport

    store = CorpusArtifactStore(tmp_path / "corpus")
    provisions = store.provisions_path("us-co", "statute", "2026-05-05")
    store.write_provisions(
        provisions,
        [
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
            )
        ],
    )

    monkeypatch.setattr(cli, "resolve_service_key", lambda *a, **kw: "service")
    monkeypatch.setattr(
        cli,
        "load_provisions_to_supabase",
        lambda *a, **kw: SupabaseLoadReport(rows_total=1, rows_loaded=1, chunk_count=1),
    )
    monkeypatch.setattr(
        cli,
        "fetch_provisions_for_navigation",
        lambda **kw: (
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/title-39",
                version="2026-05-05",
            ),
        ),
    )

    def fail_status_fetch(**kw):
        raise AssertionError("--no-preserve-navigation-statuses must skip status fetch")

    monkeypatch.setattr(cli, "fetch_navigation_statuses", fail_status_fetch)
    monkeypatch.setattr(
        cli,
        "write_navigation_nodes_to_supabase",
        lambda nodes, **kw: NavigationSupabaseWriteReport(
            rows_total=1,
            rows_loaded=1,
            chunk_count=1,
            scopes_replaced=(("us-co", "statute", "2026-05-05"),),
            rows_deleted=0,
            delete_chunk_count=0,
        ),
    )

    exit_code = main(
        [
            "load-supabase",
            "--provisions",
            str(provisions),
            "--no-preserve-navigation-statuses",
        ]
    )
    assert exit_code == 0


def test_apply_navigation_status_overrides_does_not_drop_existing_on_none():
    from axiom_corpus.corpus.cli import _apply_navigation_status_overrides

    record = ProvisionRecord(
        jurisdiction="x",
        document_class="y",
        citation_path="a",
    )
    applied = _apply_navigation_status_overrides(
        [record],
        existing_statuses={"a": "current"},
        overrides=[record],  # record carries no status
    )
    assert applied[0].metadata == {"status": "current"}


def test_apply_navigation_status_overrides_explicit_override_wins():
    from axiom_corpus.corpus.cli import _apply_navigation_status_overrides

    record = ProvisionRecord(
        jurisdiction="x",
        document_class="y",
        citation_path="a",
        metadata={"status": "updated"},
    )
    applied = _apply_navigation_status_overrides(
        [record],
        existing_statuses={"a": "current"},
        overrides=[record],
    )
    assert applied[0].metadata == {"status": "updated"}


def test_snapshot_provision_counts_cli_writes_supabase_counts(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    out = tmp_path / "provision-counts.json"
    monkeypatch.setattr(
        cli,
        "resolve_service_key",
        lambda *args, **kwargs: "service",
    )
    monkeypatch.setattr(
        cli,
        "fetch_provision_counts",
        lambda **kwargs: (
            {
                "jurisdiction": "us-wa",
                "document_class": "statute",
                "provision_count": 54631,
            },
        ),
    )

    exit_code = main(["snapshot-provision-counts", "--output", str(out)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["written_to"] == str(out)
    assert json.loads(out.read_text()) == {
        "rows": [
            {
                "document_class": "statute",
                "jurisdiction": "us-wa",
                "provision_count": 54631,
            }
        ]
    }


def test_snapshot_provision_counts_cli_can_count_release_manifest(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    release_dir = base / "releases"
    release_dir.mkdir(parents=True)
    release_path = release_dir / "test-release-v1.json"
    release_path.write_text(
        json.dumps(
            {
                "name": "test-release-v1",
                "scopes": [
                    {
                        "jurisdiction": "us",
                        "document_class": "guidance",
                        "version": "2026-05-01",
                    }
                ],
            }
        )
    )
    out = tmp_path / "provision-counts.json"
    monkeypatch.setattr(cli, "resolve_service_key", lambda *args, **kwargs: "service")

    def fake_fetch(release, **kwargs):
        assert release.name == "test-release-v1"
        assert release.scopes[0].jurisdiction == "us"
        assert kwargs["service_key"] == "service"
        return (
            {
                "jurisdiction": "us",
                "document_class": "guidance",
                "provision_count": 49,
            },
        )

    monkeypatch.setattr(cli, "fetch_release_provision_counts", fake_fetch)

    exit_code = main(
        [
            "snapshot-provision-counts",
            "--base",
            str(base),
            "--release",
            str(release_path),
            "--output",
            str(out),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["release_path"] == str(release_dir / "test-release-v1.json")
    assert json.loads(out.read_text()) == {
        "release_path": str(release_dir / "test-release-v1.json"),
        "rows": [
            {
                "document_class": "guidance",
                "jurisdiction": "us",
                "provision_count": 49,
            }
        ],
    }


def test_extract_state_statutes_batch_cli(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    html_release = tmp_path / "release76.2021.05.21"
    odt_release = tmp_path / "release90.2023.03"
    html_release.mkdir()
    odt_release.mkdir()
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        f"""
version: "2026-04-29"
sources:
  - source_id: us-tn-tca
    jurisdiction: us-tn
    document_class: statute
    adapter: cic-html
    version: "2026-04-29"
    options:
      release_dir: {html_release.name}
      source_as_of: "2021-05-21"
  - source_id: us-va-code
    jurisdiction: us-va
    document_class: statute
    adapter: cic-odt
    version: "2026-04-29"
    options:
      release_dir: {odt_release.name}
      source_as_of: "2023-03-01"
"""
    )
    coverage = ProvisionCoverageReport(
        jurisdiction="us-tn",
        document_class="statute",
        version="2026-04-29",
        source_count=1,
        provision_count=1,
        matched_count=1,
        missing_from_provisions=(),
        extra_provisions=(),
    )

    def fake_html(*args, **kwargs):
        assert kwargs["jurisdiction"] == "us-tn"
        assert kwargs["release_dir"] == html_release
        assert kwargs["source_as_of"] == "2021-05-21"
        return StateStatuteExtractReport(
            jurisdiction="us-tn",
            title_count=1,
            container_count=0,
            section_count=1,
            provisions_written=1,
            inventory_path=base / "inventory/us-tn/statute/2026-04-29.json",
            provisions_path=base / "provisions/us-tn/statute/2026-04-29.jsonl",
            coverage_path=base / "coverage/us-tn/statute/2026-04-29.json",
            coverage=coverage,
            source_paths=(base / "sources/us-tn/statute/2026-04-29/title.html",),
        )

    def fake_odt(*args, **kwargs):
        assert kwargs["jurisdiction"] == "us-va"
        assert kwargs["release_dir"] == odt_release
        assert kwargs["source_as_of"] == "2023-03-01"
        return StateStatuteExtractReport(
            jurisdiction="us-va",
            title_count=1,
            container_count=0,
            section_count=1,
            provisions_written=2,
            inventory_path=base / "inventory/us-va/statute/2026-04-29.json",
            provisions_path=base / "provisions/us-va/statute/2026-04-29.jsonl",
            coverage_path=base / "coverage/us-va/statute/2026-04-29.json",
            coverage=ProvisionCoverageReport(
                jurisdiction="us-va",
                document_class="statute",
                version="2026-04-29",
                source_count=2,
                provision_count=2,
                matched_count=2,
                missing_from_provisions=(),
                extra_provisions=(),
            ),
            source_paths=(base / "sources/us-va/statute/2026-04-29/title.odt",),
        )

    monkeypatch.setattr(cli, "extract_cic_html_release", fake_html)
    monkeypatch.setattr(cli, "extract_cic_odt_release", fake_odt)

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(base),
            "--manifest",
            str(manifest),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["source_count"] == 2
    assert payload["completed_count"] == 2
    assert payload["provisions_written"] == 3
    assert payload["coverage_complete"] is True
    assert payload["successful"] is True


def test_extract_state_statutes_batch_fails_on_skipped_sources(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    release = tmp_path / "release76.2021.05.21"
    release.mkdir()
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        f"""
version: "2026-04-29"
sources:
  - source_id: us-tn-tca
    jurisdiction: us-tn
    document_class: statute
    adapter: cic-html
    version: "2026-04-29"
    options:
      release_dir: {release.name}
"""
    )

    def fake_html(*args, **kwargs):
        return StateStatuteExtractReport(
            jurisdiction="us-tn",
            title_count=1,
            container_count=0,
            section_count=1,
            provisions_written=1,
            inventory_path=base / "inventory/us-tn/statute/2026-04-29.json",
            provisions_path=base / "provisions/us-tn/statute/2026-04-29.jsonl",
            coverage_path=base / "coverage/us-tn/statute/2026-04-29.json",
            coverage=ProvisionCoverageReport(
                jurisdiction="us-tn",
                document_class="statute",
                version="2026-04-29",
                source_count=1,
                provision_count=1,
                matched_count=1,
                missing_from_provisions=(),
                extra_provisions=(),
            ),
            source_paths=(base / "sources/us-tn/statute/2026-04-29/title.html",),
            skipped_source_count=1,
            errors=("blocked source",),
        )

    monkeypatch.setattr(cli, "extract_cic_html_release", fake_html)

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(base),
            "--manifest",
            str(manifest),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["coverage_complete"] is True
    assert payload["successful"] is False
    assert payload["rows"][0]["skipped_source_count"] == 1


def test_extract_state_statutes_batch_dry_run_reports_missing_sources(tmp_path, capsys):
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-04-29"
sources:
  - source_id: us-tn-tca
    jurisdiction: us-tn
    document_class: statute
    adapter: cic-html
    options:
      release_dir: missing-release
"""
    )

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path / "corpus"),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["dry_run"] is True
    assert payload["rows"][0]["source_path_exists"] is False


def test_extract_state_statutes_batch_dry_run_allows_live_texas_source(tmp_path, capsys):
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-05-01"
sources:
  - source_id: us-tx-statutes
    jurisdiction: us-tx
    document_class: statute
    adapter: texas-tcas
    source_url: https://statutes.capitol.texas.gov/
"""
    )

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path / "corpus"),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["rows"][0]["adapter"] == "texas-tcas"
    assert payload["rows"][0]["source_path"] is None
    assert payload["rows"][0]["source_path_exists"] is True


def test_extract_state_statutes_batch_dry_run_allows_live_ohio_source(tmp_path, capsys):
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-05-01"
sources:
  - source_id: us-oh-revised-code
    jurisdiction: us-oh
    document_class: statute
    adapter: ohio-revised-code
    source_url: https://codes.ohio.gov/ohio-revised-code
"""
    )

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path / "corpus"),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["rows"][0]["adapter"] == "ohio-revised-code"
    assert payload["rows"][0]["source_path"] is None
    assert payload["rows"][0]["source_path_exists"] is True


def test_extract_state_statutes_batch_dry_run_allows_live_minnesota_source(tmp_path, capsys):
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-05-01"
sources:
  - source_id: us-mn-statutes
    jurisdiction: us-mn
    document_class: statute
    adapter: minnesota-statutes
    source_url: https://www.revisor.mn.gov/statutes/
"""
    )

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path / "corpus"),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["rows"][0]["adapter"] == "minnesota-statutes"
    assert payload["rows"][0]["source_path"] is None
    assert payload["rows"][0]["source_path_exists"] is True


def test_extract_state_statutes_batch_dry_run_allows_live_nebraska_source(tmp_path, capsys):
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-05-04"
sources:
  - source_id: us-ne-revised-statutes
    jurisdiction: us-ne
    document_class: statute
    adapter: nebraska-revised-statutes
    source_url: https://nebraskalegislature.gov/laws/browse-statutes.php
"""
    )

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path / "corpus"),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["rows"][0]["adapter"] == "nebraska-revised-statutes"
    assert payload["rows"][0]["source_path"] is None
    assert payload["rows"][0]["source_path_exists"] is True


def test_extract_state_statutes_batch_dry_run_allows_live_washington_source(tmp_path, capsys):
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-05-04"
sources:
  - source_id: us-wa-rcw
    jurisdiction: us-wa
    document_class: statute
    adapter: washington-rcw
    source_url: https://app.leg.wa.gov/RCW/default.aspx
"""
    )

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path / "corpus"),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["rows"][0]["adapter"] == "washington-rcw"
    assert payload["rows"][0]["source_path"] is None
    assert payload["rows"][0]["source_path_exists"] is True


def test_extract_state_statutes_batch_dry_run_allows_live_indiana_source(tmp_path, capsys):
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-05-05"
sources:
  - source_id: us-in-code
    jurisdiction: us-in
    document_class: statute
    adapter: indiana-code
    source_url: https://iga.in.gov/ic/2025/2025-Indiana-Code-html.zip
"""
    )

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path / "corpus"),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["rows"][0]["adapter"] == "indiana-code"
    assert payload["rows"][0]["source_path"] is None
    assert payload["rows"][0]["source_path_exists"] is True


def test_extract_state_statutes_batch_dry_run_allows_live_montana_source(tmp_path, capsys):
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-05-05"
sources:
  - source_id: us-mt-code
    jurisdiction: us-mt
    document_class: statute
    adapter: montana-code
    source_url: https://mca.legmt.gov/bills/mca/index.html
"""
    )

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path / "corpus"),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["rows"][0]["adapter"] == "montana-code"
    assert payload["rows"][0]["source_path"] is None
    assert payload["rows"][0]["source_path_exists"] is True


def test_extract_state_statutes_batch_passes_utah_options(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-05-10"
sources:
  - source_id: us-ut-code
    jurisdiction: us-ut
    document_class: statute
    adapter: utah-code
    source_url: https://le.utah.gov/xcode/C_1800010118000101.html
    version: "2026-05-10"
    options:
      source_as_of: "2026-05-10"
      expression_date: "2026-05-10"
      request_delay_seconds: 0.25
      timeout_seconds: 60
      request_attempts: 8
      workers: 1
"""
    )

    def fake_utah(*args, **kwargs):
        assert kwargs["source_url"] == "https://le.utah.gov/xcode/C_1800010118000101.html"
        assert kwargs["source_as_of"] == "2026-05-10"
        assert kwargs["expression_date"] == "2026-05-10"
        assert kwargs["request_delay_seconds"] == 0.25
        assert kwargs["timeout_seconds"] == 60.0
        assert kwargs["request_attempts"] == 8
        assert kwargs["workers"] == 1
        return StateStatuteExtractReport(
            jurisdiction="us-ut",
            title_count=1,
            container_count=0,
            section_count=1,
            provisions_written=1,
            inventory_path=base / "inventory/us-ut/statute/2026-05-10.json",
            provisions_path=base / "provisions/us-ut/statute/2026-05-10.jsonl",
            coverage_path=base / "coverage/us-ut/statute/2026-05-10.json",
            coverage=ProvisionCoverageReport(
                jurisdiction="us-ut",
                document_class="statute",
                version="2026-05-10",
                source_count=1,
                provision_count=1,
                matched_count=1,
                missing_from_provisions=(),
                extra_provisions=(),
            ),
            source_paths=(base / "sources/us-ut/statute/2026-05-10/title.html",),
        )

    monkeypatch.setattr(cli, "extract_utah_code", fake_utah)

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(base),
            "--manifest",
            str(manifest),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["completed_count"] == 1
    assert payload["provisions_written"] == 1


def test_extract_state_statutes_batch_passes_wisconsin_options(tmp_path, capsys, monkeypatch):
    import axiom_corpus.corpus.cli as cli

    base = tmp_path / "corpus"
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        """
version: "2026-05-10"
sources:
  - source_id: us-wi-statutes
    jurisdiction: us-wi
    document_class: statute
    adapter: wisconsin-statutes
    source_url: https://docs.legis.wisconsin.gov/statutes/prefaces/toc
    version: "2026-05-10"
    options:
      source_as_of: "2026-04-03"
      expression_date: "2026-04-03"
      base_url: https://docs.legis.wisconsin.gov
      request_delay_seconds: 0.05
      timeout_seconds: 90
      request_attempts: 5
      workers: 8
"""
    )

    def fake_wisconsin(*args, **kwargs):
        assert kwargs["source_url"] == "https://docs.legis.wisconsin.gov/statutes/prefaces/toc"
        assert kwargs["base_url"] == "https://docs.legis.wisconsin.gov"
        assert kwargs["source_as_of"] == "2026-04-03"
        assert kwargs["expression_date"] == "2026-04-03"
        assert kwargs["request_delay_seconds"] == 0.05
        assert kwargs["timeout_seconds"] == 90.0
        assert kwargs["request_attempts"] == 5
        assert kwargs["workers"] == 8
        return StateStatuteExtractReport(
            jurisdiction="us-wi",
            title_count=1,
            container_count=0,
            section_count=1,
            provisions_written=1,
            inventory_path=base / "inventory/us-wi/statute/2026-05-10.json",
            provisions_path=base / "provisions/us-wi/statute/2026-05-10.jsonl",
            coverage_path=base / "coverage/us-wi/statute/2026-05-10.json",
            coverage=ProvisionCoverageReport(
                jurisdiction="us-wi",
                document_class="statute",
                version="2026-05-10",
                source_count=1,
                provision_count=1,
                matched_count=1,
                missing_from_provisions=(),
                extra_provisions=(),
            ),
            source_paths=(base / "sources/us-wi/statute/2026-05-10/chapter.html",),
        )

    monkeypatch.setattr(cli, "extract_wisconsin_statutes", fake_wisconsin)

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(base),
            "--manifest",
            str(manifest),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["completed_count"] == 1
    assert payload["provisions_written"] == 1


def test_extract_state_statutes_batch_dry_run_checks_california_source_zip(tmp_path, capsys):
    source_zip = tmp_path / "pubinfo_2025.zip"
    source_zip.write_bytes(b"zip placeholder")
    manifest = tmp_path / "state-statutes.yaml"
    manifest.write_text(
        f"""
version: "2026-05-01"
sources:
  - source_id: us-ca-codes
    jurisdiction: us-ca
    document_class: statute
    adapter: california-codes-bulk
    source_url: https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip
    options:
      source_zip: {source_zip.name}
"""
    )

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(tmp_path / "corpus"),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["rows"][0]["adapter"] == "california-codes-bulk"
    assert payload["rows"][0]["source_path"] == str(source_zip)
    assert payload["rows"][0]["source_path_exists"] is True


def test_artifact_report_cli_accepts_release_name(tmp_path, capsys):
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore

    store = CorpusArtifactStore(tmp_path / "corpus")
    store.write_inventory(
        store.inventory_path("us-co", "policy", "2026-04-30"),
        [SourceInventoryItem(citation_path="us-co/policy/doc")],
    )
    store.write_inventory(
        store.inventory_path("us-ny", "policy", "2026-04-30"),
        [SourceInventoryItem(citation_path="us-ny/policy/doc")],
    )
    release_dir = store.root / "releases"
    release_dir.mkdir(parents=True)
    release_path = release_dir / "test-release-v1.json"
    release_path.write_text(
        json.dumps(
            {
                "name": "test-release-v1",
                "scopes": [
                    {
                        "jurisdiction": "us-co",
                        "document_class": "policy",
                        "version": "2026-04-30",
                    }
                ],
            }
        )
    )

    exit_code = main(
        [
            "artifact-report",
            "--base",
            str(store.root),
            "--prefix",
            "inventory",
            "--release",
            str(release_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["release"] == "test-release-v1"
    assert payload["release_scope_count"] == 1
    assert payload["scope_count"] == 1
    assert payload["local_count"] == 1
    assert payload["rows"][0]["jurisdiction"] == "us-co"


def test_artifact_report_cli_without_release_reports_all_scopes(tmp_path, capsys):
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore

    store = CorpusArtifactStore(tmp_path / "corpus")
    store.write_inventory(
        store.inventory_path("us-co", "policy", "2026-04-30"),
        [SourceInventoryItem(citation_path="us-co/policy/doc")],
    )
    store.write_inventory(
        store.inventory_path("us-ny", "policy", "2026-04-30"),
        [SourceInventoryItem(citation_path="us-ny/policy/doc")],
    )
    exit_code = main(
        [
            "artifact-report",
            "--base",
            str(store.root),
            "--prefix",
            "inventory",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "release" not in payload
    assert payload["scope_count"] == 2

    exit_code = main(
        [
            "artifact-report",
            "--base",
            str(store.root),
            "--prefix",
            "inventory",
            "--all-scopes",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "release" not in payload
    assert payload["scope_count"] == 2


def test_validate_release_cli_gates_release(tmp_path, capsys):
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore

    store = CorpusArtifactStore(tmp_path / "corpus")
    source = store.source_path("us-co", "policy", "2026-04-30", "source.html")
    source_sha = store.write_text(source, "<p>Text.</p>")
    store.write_inventory(
        store.inventory_path("us-co", "policy", "2026-04-30"),
        [
            SourceInventoryItem(
                citation_path="us-co/policy/doc",
                source_path=source.relative_to(store.root).as_posix(),
                sha256=source_sha,
            )
        ],
    )
    store.write_provisions(
        store.provisions_path("us-co", "policy", "2026-04-30"),
        [
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="policy",
                citation_path="us-co/policy/doc",
                version="2026-04-30",
                body="Text.",
                source_path=source.relative_to(store.root).as_posix(),
                source_as_of="2026-04-30",
                expression_date="2026-04-30",
            )
        ],
    )
    store.write_json(
        store.coverage_path("us-co", "policy", "2026-04-30"),
        {
            "complete": True,
            "source_count": 1,
            "provision_count": 1,
            "matched_count": 1,
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )
    release_dir = store.root / "releases"
    release_dir.mkdir(parents=True)
    release_path = release_dir / "test-release-v1.json"
    release_path.write_text(
        json.dumps(
            {
                "name": "test-release-v1",
                "scopes": [
                    {
                        "jurisdiction": "us-co",
                        "document_class": "policy",
                        "version": "2026-04-30",
                    }
                ],
            }
        )
    )

    exit_code = main(
        ["validate-release", "--base", str(store.root), "--release", str(release_path)]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["error_count"] == 0
    assert payload["warning_count"] == 0


def test_resolve_encoded_paths_supports_monorepo_and_legacy_layouts(tmp_path):
    from argparse import Namespace

    from axiom_corpus.corpus.cli import (
        _jurisdictions_for_repo_checkout,
        _resolve_encoded_paths,
    )

    def _touch(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("rule: {}\n")

    # Monorepo layout: federal + state dirs inside one rulespec-us checkout.
    monorepo = tmp_path / "monorepo-root" / "rulespec-us"
    _touch(monorepo / "us" / "statutes" / "26" / "3111" / "a.yaml")
    _touch(monorepo / "us-ca" / "regulations" / "mpp" / "63-300" / "1.yaml")

    # Legacy layout: sibling per-jurisdiction checkouts under another root.
    legacy_root = tmp_path / "legacy-root"
    _touch(legacy_root / "rulespec-us" / "statutes" / "7" / "2014" / "e.yaml")
    _touch(legacy_root / "rulespec-us-ny" / "regulations" / "18-nycrr" / "387.1.yaml")

    encoded = _resolve_encoded_paths(
        Namespace(
            rulespec_repo=[],
            rulespec_root=[str(monorepo.parent), str(legacy_root)],
            rulespec_auto=False,
        ),
        ["us", "us-ca", "us-ny"],
    )

    assert encoded == {
        "us/statute/26/3111/a",
        "us/statute/7/2014/e",
        "us-ca/regulation/mpp/63-300/1",
        "us-ny/regulation/18-nycrr/387.1",
    }

    # An explicit --rulespec-repo pointing at a monorepo checkout covers every
    # jurisdiction directory inside it; legacy checkouts keep covering one.
    assert _jurisdictions_for_repo_checkout(monorepo) == ["us", "us-ca"]
    assert _jurisdictions_for_repo_checkout(legacy_root / "rulespec-us-ny") == ["us-ny"]

    encoded_explicit = _resolve_encoded_paths(
        Namespace(rulespec_repo=[str(monorepo)], rulespec_root=[], rulespec_auto=False),
        ["us", "us-ca"],
    )
    assert encoded_explicit == {
        "us/statute/26/3111/a",
        "us-ca/regulation/mpp/63-300/1",
    }
