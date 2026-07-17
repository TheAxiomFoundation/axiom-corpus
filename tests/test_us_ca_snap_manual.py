import hashlib
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ca-cdss-mpp-calfresh-complete.yaml"
VERSION = "2026-07-17-ca-cdss-mpp-calfresh"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-ca" / "regulation" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-ca" / "regulation" / f"{VERSION}.json"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-ca" / "regulation" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions" / "us-ca" / "regulation" / f"{VERSION}.jsonl"
SOURCE_URL_ROOT = "https://www.cdss.ca.gov/Portals/9/Regs/Man/Fsman"
EXPECTED_SOURCES = {
    # stem: (extension, query, expression date, block count, sha256)
    "fsman01": ("docx", "JwD1ESXqFU37ScpIBvniFg%3d%3d", "2005-01-19", 103, "be804f7d5913d0b6ec4889398a6e5ca2a10e571f8520d26b58d956f638645af9"),
    "fsman02": ("docx", "ry1c8fKV1Fi8EscRAGz50Q%3d%3d", "2021-05-05", 10, "8503af402dca19bc84b9683be4eb9c431dfb0f69e2ef0a31c913b368fa1daf08"),
    "fsman03": ("docx", "s6TbIRZVtokkOhyNVTHJ2w%3d%3d", "2009-02-11", 4, "96849fc807cd913b3093490823c6339eefe2391a7b2e63fc3b23720f59f6770a"),
    "fsman04a": ("docx", "XxVnS3PVFjCyv_jeqObi5Q%3d%3d", "2011-08-02", 7, "4a0152510f1b8a6c65037d55951360cfb5cad08daf3953d5ff7ccf9608279ccb"),
    "fsman04b": ("docx", "3Pei6I55E7c5cMkoy9oDvw%3d%3d", "2008-07-01", 8, "862f4599b2e2ba8ba12215f2ba74b9b9dd8985ef2d0ee7093ac1eba51e3b26af"),
    "fsman05": ("docx", "s6TbIRZVtokkOhyNVTHJ2w%3d%3d", "2008-07-01", 4, "1e369d825d58dabc9621a791a4410cc5a824b7a9a0df34a3a796bef268254193"),
    "fsman06": ("docx", "wrx9nKY4BHRH9SGFqVVMkg%3d%3d", "2021-05-05", 3, "eb0eb8a58a8371c8f56e80a3bf49d561e01eb0ffcbae2567a2475d7abb8f4e75"),
    "fsman07": ("docx", "tZ6HMPXM1CMN4rGRYcPCLg%3d%3d", "2007-03-28", 3, "0a4a32aa78930de2f9a78ea17a26da6ab0c6fe4ad31f32bf8c51b4b61cd8a8a0"),
    "fsman08": ("docx", "l18Y1LceE92BoEjrk4ErxA%3d%3d", "2008-08-26", 7, "8304c6926f4e515c81fd0422ea1ec17bc5388204c5cdeab25c3614ad91d20c15"),
    "fsman09": ("docx", "_PXpqValtu90l_AGx7GSRA%3d%3d", "2008-08-27", 17, "2e47d2eeb139100de3172b9cee45be21c5a2c228185b06ee4d654497ea7bba60"),
    "fsman10": ("docx", "v30E0PK3cbcMvmbh-I6tOw%3d%3d", "2021-05-05", 7, "4035ebadf765c61071740888265be0d3bc05b498b9fba99c5b32a45bb4dd719b"),
    "fsman11a": ("docx", "wRLVdVqNMIpanJKOhq7knA%3d%3d", "2021-05-05", 62, "f9622e8805bbfc1712736763339e5925a22e5de8f4999615d345c819f2d50bf6"),
    "fsman11b": ("docx", "URy_ouNIinj726ZuHMPuDQ%3d%3d", "2021-05-05", 4, "b5706cfe6299aab00d26a80bc8fe40ca5d1151dcb7e2b123d9c719fa296b22d1"),
    "fsman11c": ("pdf", "o8oqwneG5OfQd_Bt5pitOQ%3d%3d", "2025-09-30", 142, "112ef5b1004d79d9bcb83dd68a97d741f15ee7f30580e9f77d5cbc00b98fd3f1"),
    "fsman12": ("docx", "x8jJzhj5pi1hbonWySyB8A%3d%3d", "2008-09-17", 40, "a4967287b4376fdce7526a6e9eff58bea9a9c165772f940ebecd2bdd8b325729"),
}


def test_california_calfresh_scope_retains_complete_official_manual() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    document_items = [item for item in inventory if item["metadata"]["kind"] == "document"]
    documents_by_id = {document["source_id"]: document for document in documents}
    document_items_by_path = {item["citation_path"]: item for item in document_items}

    assert len(documents) == len(documents_by_id) == len(EXPECTED_SOURCES)
    assert len(document_items) == len(document_items_by_path) == len(EXPECTED_SOURCES)
    for stem, expected in EXPECTED_SOURCES.items():
        extension, query, expression_date, block_count, expected_sha256 = expected
        source_id = f"ca-cdss-mpp-calfresh-{stem}"
        citation_path = f"us-ca/regulation/cdss-mpp/division-63/{stem}"
        source_url = f"{SOURCE_URL_ROOT}/{stem}.{extension}?ver={query}"
        document = documents_by_id[source_id]
        assert (
            document["citation_path"],
            document["source_url"],
            document["source_format"],
            document["source_as_of"],
            document["expression_date"],
        ) == (citation_path, source_url, extension, "2026-07-17", expression_date)

        item = document_items_by_path[citation_path]
        source_path = CORPUS_ROOT / item["source_path"]
        assert item["source_url"] == source_url
        assert item["metadata"]["block_count"] == block_count
        assert item["sha256"] == expected_sha256
        assert source_path.is_relative_to(SOURCE_ROOT)
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == expected_sha256

    ocr_document = documents_by_id["ca-cdss-mpp-calfresh-fsman11c"]
    assert ocr_document["extraction"] == {
        "ocr": True,
        "ocr_dpi": 200,
        "ocr_language": "eng",
    }
    assert all("extraction" not in document for document in documents if document is not ocr_document)

    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == []
    assert coverage["extra_provisions"] == []
    assert coverage["source_count"] == coverage["provision_count"] == len(inventory) == 436


def test_california_image_only_manual_section_has_ocr_text() -> None:
    provisions = [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]
    ocr_pages = [
        provision
        for provision in provisions
        if provision["source_id"] == "ca-cdss-mpp-calfresh-fsman11c"
        and provision["kind"] == "page"
    ]

    assert len(ocr_pages) == 142
    assert all(provision["body"].strip() for provision in ocr_pages)
    assert "FOOD STAMP HANDBOOK" in ocr_pages[0]["body"]
