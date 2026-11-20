from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

import scripts.repair_plan_cascade_self_containment as repair_module
from scripts.repair_plan_cascade_self_containment import _refuse_base_repairs

SUFFIX = "r2026-11-17-repaired"
BASE = ("us-example", "statute", "base-v")
PRIMARY = ("us-example", "statute", "primary-v")
OTHER_PRIMARY = ("us-example", "regulation", "primary-w")
REPAIRED_PRIMARY = ("us-example", "statute", f"primary-v-{SUFFIX}")


def _row(scope: tuple[str, str, str], *, layer: str | None = None) -> dict[str, str]:
    row = {"jurisdiction": scope[0], "document_class": scope[1], "version": scope[2]}
    if layer is not None:
        row["layer"] = layer
    return row


def _payload(*rows: dict[str, str]) -> dict[str, object]:
    return {"name": "us-example-repair", "scopes": list(rows)}


def _mapped(*scopes: tuple[str, str, str]) -> dict[tuple[str, str, str], tuple[str, str, str]]:
    return {scope: (scope[0], scope[1], f"{scope[2]}-{SUFFIX}") for scope in scopes}


def test_allows_a_repair_of_primary_scopes_beside_bases():
    # The payload's base and the tracked base are both left out of the repair.
    _refuse_base_repairs(
        _payload(_row(BASE, layer="base"), _row(PRIMARY), _row(OTHER_PRIMARY)),
        _mapped(PRIMARY, OTHER_PRIMARY),
        frozenset({BASE, ("us-example", "regulation", "base-w")}),
    )


def test_refuses_a_scope_the_release_payload_marks_as_base():
    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be repaired: "
        r"us-example/statute/base-v$",
    ):
        _refuse_base_repairs(
            _payload(_row(BASE, layer="base"), _row(PRIMARY)),
            _mapped(BASE, PRIMARY),
            frozenset(),
        )


def test_refuses_a_scope_a_tracked_selector_marks_as_base():
    # The release payload carries the scope as primary.
    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be repaired: "
        r"us-example/statute/primary-v$",
    ):
        _refuse_base_repairs(
            _payload(_row(PRIMARY), _row(OTHER_PRIMARY)),
            _mapped(PRIMARY, OTHER_PRIMARY),
            frozenset({PRIMARY}),
        )


def test_refuses_a_repair_whose_new_scope_is_a_tracked_base():
    new_scope = ("us-example", "statute", f"primary-v-{SUFFIX}")
    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be repaired: "
        rf"us-example/statute/primary-v-{SUFFIX}$",
    ):
        _refuse_base_repairs(
            _payload(_row(PRIMARY)),
            _mapped(PRIMARY),
            frozenset({new_scope}),
        )


@pytest.mark.parametrize(
    ("rows", "repaired", "tracked", "refused"),
    [
        pytest.param(
            (_row(PRIMARY), _row(REPAIRED_PRIMARY, layer="base")),
            (PRIMARY,),
            frozenset(),
            f"us-example/statute/primary-v-{SUFFIX}",
            id="payload-base-is-the-new-scope",
        ),
        pytest.param(
            (_row(PRIMARY), _row(REPAIRED_PRIMARY, layer="base"), _row(OTHER_PRIMARY)),
            (PRIMARY, OTHER_PRIMARY),
            frozenset({OTHER_PRIMARY}),
            f"us-example/regulation/primary-w, us-example/statute/primary-v-{SUFFIX}",
            id="beside-a-tracked-base-key",
        ),
    ],
)
def test_refuses_a_repair_whose_new_scope_the_release_payload_marks_as_base(
    rows, repaired, tracked, refused
):
    # The release's own payload declares the new scope a base, so the repair
    # would write over a base's files. No tracked selector needs to say so.
    with pytest.raises(
        ValueError,
        match="^"
        + re.escape(f"base scopes are carried unchanged and cannot be repaired: {refused}")
        + "$",
    ):
        _refuse_base_repairs(_payload(*rows), _mapped(*repaired), tracked)


def test_names_every_refused_scope_in_order():
    with pytest.raises(
        ValueError,
        match=r"cannot be repaired: us-example/regulation/primary-w, us-example/statute/base-v$",
    ):
        _refuse_base_repairs(
            _payload(_row(BASE, layer="base"), _row(OTHER_PRIMARY)),
            _mapped(BASE, OTHER_PRIMARY),
            frozenset({OTHER_PRIMARY}),
        )


@pytest.mark.parametrize("layer", ["primary", "Base", ""])
def test_refuses_a_release_payload_with_an_invalid_layer(layer):
    with pytest.raises(
        ValueError, match=r"^release scope us-example/statute/base-v has an invalid layer"
    ):
        _refuse_base_repairs(
            _payload(_row(BASE, layer=layer), _row(PRIMARY)),
            _mapped(PRIMARY),
            frozenset(),
        )


def _tree(root: Path) -> dict[str, bytes | None]:
    """Every path under ``root``, with a file's bytes and None for a directory."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


def _write_repo(
    repo: Path, *, release: Path, release_layer: str | None, tracked_base: bool
) -> None:
    """Write one scope whose rows name a parent it lacks, so an audit repairs it."""
    corpus = repo / "data" / "corpus"
    jurisdiction, document_class, version = BASE
    rows = [
        {
            "citation_path": "us-example/statute/1/a",
            "document_class": document_class,
            "jurisdiction": jurisdiction,
            "parent_citation_path": "us-example/statute/1",
            "version": version,
        }
    ]
    provisions = corpus / "provisions" / jurisdiction / document_class / f"{version}.jsonl"
    provisions.parent.mkdir(parents=True)
    provisions.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    inventory = corpus / "inventory" / jurisdiction / document_class / f"{version}.json"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(json.dumps({"items": []}) + "\n")
    coverage = corpus / "coverage" / jurisdiction / document_class / f"{version}.json"
    coverage.parent.mkdir(parents=True)
    coverage.write_text(json.dumps({"complete": True}) + "\n")
    source = corpus / "sources" / jurisdiction / document_class / version / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text(f"<p>{version}</p>\n")

    releases = repo / "manifests" / "releases"
    releases.mkdir(parents=True)
    (repo / "SIGNING-COMMANDS.md").write_text(
        f"sign_scope {jurisdiction} {document_class} {version}\n"
    )
    release_path = repo / release
    release_path.parent.mkdir(parents=True, exist_ok=True)
    release_path.write_text(
        json.dumps(_payload(_row(BASE, layer=release_layer)), indent=2, sort_keys=True) + "\n"
    )
    if tracked_base:
        (releases / "us-example-layered.json").write_text(
            json.dumps(
                {"name": "us-example-layered", "scopes": [_row(BASE, layer="base")]},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    else:
        # A tracked selector that marks no base: an inventory with no selector is refused.
        (releases / "us-example-plain.json").write_text(
            json.dumps({"name": "us-example-plain", "scopes": [_row(PRIMARY)]}) + "\n"
        )


@pytest.mark.parametrize(
    ("release", "release_layer", "tracked_base"),
    [
        # The release payload alone marks the scope: no tracked selector does.
        pytest.param(Path("repair") / "release.json", "base", False, id="payload-base"),
        # A tracked selector alone marks the scope: the release carries it as primary.
        pytest.param(
            Path("manifests") / "releases" / "release.json", None, True, id="tracked-base"
        ),
    ],
)
def test_main_refuses_a_base_repair_before_moving_anything(
    tmp_path, monkeypatch, release, release_layer, tracked_base
):
    repo = tmp_path / "repo"
    _write_repo(repo, release=release, release_layer=release_layer, tracked_base=tracked_base)
    report = tmp_path / "report.json"
    before = _tree(repo)
    fetched: list[list[tuple[str, str, str]]] = []
    monkeypatch.setattr(
        repair_module,
        "ensure_corpus_scopes",
        lambda scopes, *, repo: fetched.append(list(scopes)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_plan_cascade_self_containment.py",
            "--audit-residuals",
            "--repo",
            str(repo),
            "--release",
            str(release),
            "--suffix",
            SUFFIX,
            "--report",
            str(report),
        ],
    )

    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be repaired: "
        r"us-example/statute/base-v$",
    ):
        repair_module.main()

    # The audit reached the repair plan, and nothing was moved, written or unlinked.
    assert fetched == [[BASE]]
    assert _tree(repo) == before
    assert not report.exists()


def _write_scope_files(
    corpus: Path, scope: tuple[str, str, str], rows: list[dict[str, str]], *, sources: bool
) -> None:
    jurisdiction, document_class, version = scope
    provisions = corpus / "provisions" / jurisdiction / document_class / f"{version}.jsonl"
    provisions.parent.mkdir(parents=True, exist_ok=True)
    provisions.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    inventory = corpus / "inventory" / jurisdiction / document_class / f"{version}.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    items = [{"citation_path": row["citation_path"]} for row in rows]
    inventory.write_text(json.dumps({"items": items}) + "\n")
    coverage = corpus / "coverage" / jurisdiction / document_class / f"{version}.json"
    coverage.parent.mkdir(parents=True, exist_ok=True)
    coverage.write_text(json.dumps({"complete": True, "version": version}) + "\n")
    if sources:
        source = corpus / "sources" / jurisdiction / document_class / version / "source.html"
        source.parent.mkdir(parents=True)
        source.write_text(f"<p>{version}</p>\n")


def _write_payload_base_repo(repo: Path) -> None:
    """Write a primary scope to repair and the base its release payload names as the repair."""
    corpus = repo / "data" / "corpus"
    # The primary scope's row names a parent it lacks, so an audit repairs it.
    _write_scope_files(
        corpus,
        PRIMARY,
        [
            {
                "citation_path": "us-example/statute/1/a",
                "document_class": PRIMARY[1],
                "jurisdiction": PRIMARY[0],
                "parent_citation_path": "us-example/statute/1",
                "version": PRIMARY[2],
            }
        ],
        sources=True,
    )
    manifest = repo / ".axiom" / "ingest-manifests" / PRIMARY[0] / PRIMARY[1] / f"{PRIMARY[2]}.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"applied_files": [], "version": PRIMARY[2]}) + "\n")
    # The base whose name the suffix spells: self-contained, so the audit leaves it alone.
    _write_scope_files(
        corpus,
        REPAIRED_PRIMARY,
        [
            {
                "citation_path": "us-example/statute/2",
                "document_class": REPAIRED_PRIMARY[1],
                "jurisdiction": REPAIRED_PRIMARY[0],
                "version": REPAIRED_PRIMARY[2],
            }
        ],
        sources=False,
    )
    release = repo / "repair" / "release.json"
    release.parent.mkdir(parents=True)
    release.write_text(
        json.dumps(
            _payload(_row(PRIMARY), _row(REPAIRED_PRIMARY, layer="base")), indent=2, sort_keys=True
        )
        + "\n"
    )
    releases = repo / "manifests" / "releases"
    releases.mkdir(parents=True)
    # A tracked selector that marks no base, so only the release payload names one.
    (releases / "us-example-plain.json").write_text(
        json.dumps({"name": "us-example-plain", "scopes": [_row(PRIMARY)]}) + "\n"
    )
    (repo / "SIGNING-COMMANDS.md").write_text(
        f"sign_scope {PRIMARY[0]} {PRIMARY[1]} {PRIMARY[2]}\n"
    )


def test_main_refuses_a_repair_onto_a_payload_base_before_moving_anything(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _write_payload_base_repo(repo)
    report = tmp_path / "report.json"
    before = _tree(repo)
    fetched: list[list[tuple[str, str, str]]] = []
    monkeypatch.setattr(
        repair_module,
        "ensure_corpus_scopes",
        lambda scopes, *, repo: fetched.append(list(scopes)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_plan_cascade_self_containment.py",
            "--audit-residuals",
            "--repo",
            str(repo),
            "--release",
            str(Path("repair") / "release.json"),
            "--suffix",
            SUFFIX,
            "--report",
            str(report),
        ],
    )

    with pytest.raises(
        ValueError,
        match=rf"^base scopes are carried unchanged and cannot be repaired: "
        rf"us-example/statute/primary-v-{SUFFIX}$",
    ):
        repair_module.main()

    # The audit reached the repair plan, and the base's files are as they were.
    assert fetched == [[PRIMARY, REPAIRED_PRIMARY]]
    assert _tree(repo) == before
    assert not report.exists()


@pytest.mark.parametrize(
    ("rows", "mapping", "tracked"),
    [
        pytest.param(
            (_row(PRIMARY),),
            {PRIMARY: ("us-example", "statute", "primary-v-FIX")},
            frozenset({("us-example", "statute", "primary-v-fix")}),
            id="suffix-case",
        ),
        pytest.param(
            (_row(PRIMARY),),
            {PRIMARY: ("us-example", "statute", "primary-v-fix/")},
            frozenset({("us-example", "statute", "primary-v-fix")}),
            id="suffix-slash",
        ),
        pytest.param(
            (_row(PRIMARY), _row(("us-example", "statute", "primary-v-FIX"), layer="base")),
            {PRIMARY: ("us-example", "statute", "primary-v-fix")},
            frozenset(),
            id="payload-base-case",
        ),
    ],
)
def test_refuses_a_scope_name_a_selector_cannot_spell(rows, mapping, tracked):
    # On case-insensitive APFS, or through safe_segment, each spelling names
    # the files of another scope while comparing unequal to it.
    with pytest.raises(ValueError, match=r"^not a canonical scope: "):
        _refuse_base_repairs(_payload(*rows), mapping, tracked)


@pytest.mark.parametrize(
    ("rows", "mapping", "refusal"),
    [
        pytest.param(
            (_row(("us-example", "statute", "Base-V"), layer="primary"), _row(PRIMARY)),
            _mapped(PRIMARY),
            "release scope us-example/statute/Base-V has an invalid layer: 'primary'",
            id="same-row",
        ),
        pytest.param(
            (_row(BASE, layer="primary"), _row(PRIMARY)),
            {PRIMARY: ("us-example", "statute", "primary-v-FIX")},
            "release scope us-example/statute/base-v has an invalid layer: 'primary'",
            id="new-scope",
        ),
    ],
)
def test_refuses_an_invalid_layer_before_a_spelling(rows, mapping, refusal):
    # The layer loop runs before the spelling check, so a payload with a
    # layer other than "base" gets the layer refusal whatever else it misspells.
    with pytest.raises(ValueError, match=rf"^{re.escape(refusal)}$"):
        _refuse_base_repairs(_payload(*rows), mapping, frozenset())
