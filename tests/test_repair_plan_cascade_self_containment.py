from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import scripts.repair_plan_cascade_self_containment as repair_module
from scripts.repair_plan_cascade_self_containment import _refuse_base_repairs

SUFFIX = "r2026-11-17-repaired"
BASE = ("us-example", "statute", "base-v")
PRIMARY = ("us-example", "statute", "primary-v")
OTHER_PRIMARY = ("us-example", "regulation", "primary-w")


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
