from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.new_jersey_snap import reconstruct_new_jersey_snap_rules

ROOT = Path(__file__).resolve().parents[1]
BASE_PROVISIONS = (
    ROOT
    / "data/corpus/provisions/us-nj/regulation/2017-02-06-nj-snap-rules-base.jsonl"
)
RULEMAKING_PROVISIONS = (
    ROOT
    / "data/corpus/provisions/us-nj/rulemaking/2026-05-28-nj-snap-rulemaking-notices.jsonl"
)


def test_reconstruct_new_jersey_snap_rules_writes_current_scope(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = reconstruct_new_jersey_snap_rules(
        store,
        version="2026-05-28-nj-snap-rules-reconstructed",
        base_provisions_path=BASE_PROVISIONS,
        rulemaking_provisions_path=RULEMAKING_PROVISIONS,
        source_as_of="2026-05-28",
        expression_date="2025-09-15",
    )

    records = load_provisions(report.provisions_path)
    by_suffix = {record.citation_path.rsplit("/", 1)[-1]: record for record in records}

    assert report.coverage.complete
    assert report.provisions_written == 262
    assert by_suffix["njac-10-87"].heading == (
        "N.J.A.C. 10:87 New Jersey Supplemental Nutrition Assistance Program "
        "(NJ SNAP) Manual"
    )
    assert by_suffix["10-87-3.17"].heading == (
        "10:87-3.17 Fleeing felons and probation or parole violators"
    )
    assert "Actively seeking" in (by_suffix["10-87-3.17"].body or "")
    assert "CSSA" in (by_suffix["10-87-3.17"].body or "")
    assert by_suffix["10-87-9.11"].body == (
        "Unused NJ SNAP benefits will remain accessible to the household until they "
        "are expunged from the EBT account pursuant to N.J.A.C. 10:88-4.2."
    )
    assert "10:87-5.9(a)11ii" in (by_suffix["10-87-5.4"].body or "")
    assert "family cap" not in (by_suffix["10-87-5.7"].body or "").lower()
    assert "State of New Jersey mileage reimbursement rate" in (
        by_suffix["10-87-5.10"].body or ""
    )
    assert "domestic partnership" in (by_suffix["10-87-2.2"].body or "")
    assert "State SNAP Minimum Benefit Program" in (by_suffix["10-87-13.4"].body or "")
    assert sum((record.body or "").count("CWA") for record in records) == 0
