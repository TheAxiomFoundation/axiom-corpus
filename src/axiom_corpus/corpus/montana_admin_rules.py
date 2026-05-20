"""Montana Administrative Rules source-first adapter."""

from __future__ import annotations

import json
import re
import sys
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from threading import local
from typing import Any, TextIO

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment, sha256_bytes
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

MONTANA_RULES_BASE_URL = "https://rules.mt.gov"
MONTANA_RULES_HOME_URL = f"{MONTANA_RULES_BASE_URL}/"
MONTANA_RULES_API_BASE_URL = f"{MONTANA_RULES_BASE_URL}/api/policy-library-public"
MONTANA_RULES_COLLECTION_NAME = "Administrative Rules of Montana"
MONTANA_RULES_JSON_FORMAT = "montana-rules-json"
MONTANA_RULES_HTML_FORMAT = "montana-rules-html"
MONTANA_RULES_USER_AGENT = "axiom-corpus/0.1 (max@axiom-foundation.org)"

_SOURCE_PREFIX = "montana-rules"
_ARM_REF_RE = re.compile(r"\bARM\s+(?P<cite>\d{1,2}\.\d{1,3}\.\d{1,4})\b")
_ARM_BARE_REF_RE = re.compile(r"\b(?P<cite>\d{1,2}\.\d{1,3}\.\d{1,4})\b")
_MCA_REF_RE = re.compile(r"\b(?P<cite>\d{1,2}-[0-9A-Za-z]{1,3}-\d{3,4}(?:\.\d+)?)\b")


@dataclass(frozen=True)
class MontanaAdminRulesExtractReport:
    """Result from a Montana Administrative Rules extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    title_count: int
    chapter_count: int
    subchapter_count: int
    rule_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]
    skipped_source_count: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SourceSnapshot:
    source_key: str
    source_path: Path
    sha256: str
    content: bytes
    source_url: str


@dataclass(frozen=True)
class _SectionNode:
    uuid: str
    section_id: str
    name: str
    section_type: str
    category: str | None
    effective_status: str | None
    substatuses: tuple[str, ...]
    parent_uuid: str | None
    ancestor_uuids: tuple[str, ...]
    citation_path: str
    ordinal: int

    @property
    def kind(self) -> str:
        return _node_kind(self.section_type, self.section_id)

    @property
    def display_id(self) -> str:
        return _node_display_id(self.kind, self.section_id)

    @property
    def label(self) -> str:
        label_kind = self.kind.title()
        return f"ARM {label_kind} {self.display_id}"

    @property
    def heading(self) -> str:
        prefix = self.section_type or self.kind.title()
        return f"{prefix} {self.display_id}. {self.name}"

    @property
    def source_url(self) -> str:
        return f"{MONTANA_RULES_HOME_URL}browse/collections/{{collection_uuid}}/sections/{self.uuid}"


@dataclass(frozen=True)
class _SectionSnapshot:
    node: _SectionNode
    snapshot: _SourceSnapshot | None
    policies: tuple[dict[str, Any], ...]
    error: str | None = None


@dataclass(frozen=True)
class _PolicySnapshot:
    parent: _SectionNode
    stub: dict[str, Any]
    policy_snapshot: _SourceSnapshot | None
    html_snapshot: _SourceSnapshot | None
    policy: dict[str, Any] | None
    body: str | None
    references_to: tuple[str, ...]
    error: str | None = None


def montana_admin_rules_run_id(
    version: str,
    *,
    only_title: str | None = None,
    only_section: str | None = None,
    include_not_effective: bool = False,
    limit_sections: int | None = None,
    limit_rules: int | None = None,
) -> str:
    """Return a scoped Montana Administrative Rules run id."""

    parts = [version]
    if include_not_effective:
        parts.append("include-not-effective")
    if only_title:
        parts.append(f"title-{_path_token(only_title)}")
    if only_section:
        parts.append(f"section-{_path_token(only_section)}")
    if limit_sections is not None:
        parts.append(f"limit-sections-{limit_sections}")
    if limit_rules is not None:
        parts.append(f"limit-rules-{limit_rules}")
    return "-".join(parts)


def extract_montana_admin_rules(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path | None = None,
    download_dir: str | Path | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    only_title: str | None = None,
    only_section: str | None = None,
    include_not_effective: bool = False,
    limit_sections: int | None = None,
    limit_rules: int | None = None,
    workers: int = 12,
    progress_stream: TextIO | None = None,
) -> MontanaAdminRulesExtractReport:
    """Snapshot official Montana ARM JSON/HTML and extract provisions."""

    jurisdiction = "us-mt"
    document_class = DocumentClass.REGULATION.value
    run_id = montana_admin_rules_run_id(
        version,
        only_title=only_title,
        only_section=only_section,
        include_not_effective=include_not_effective,
        limit_sections=limit_sections,
        limit_rules=limit_rules,
    )
    source_root = Path(source_dir) if source_dir is not None else None
    download_root = Path(download_dir) if download_dir is not None and source_root is None else None
    source_as_of_text = source_as_of or version
    expression_date_text = _date_text(expression_date, source_as_of_text)

    collection_snapshot = _snapshot_json(
        store,
        run_id=run_id,
        relative_name=f"{_SOURCE_PREFIX}/collections.json",
        url=_api_url("collections"),
        source_root=source_root,
        download_root=download_root,
    )
    collection_payload = _json_payload(collection_snapshot.content)
    collection = _find_arm_collection(collection_payload)
    collection_uuid = str(collection["uuid"])

    tree_snapshot = _snapshot_json(
        store,
        run_id=run_id,
        relative_name=f"{_SOURCE_PREFIX}/tree.json",
        url=_api_url(f"collections/{collection_uuid}/tree"),
        source_root=source_root,
        download_root=download_root,
    )
    tree_payload = _json_payload(tree_snapshot.content)
    all_nodes = _parse_tree_nodes(tree_payload)
    selected_nodes = _select_nodes(all_nodes, only_title=only_title, only_section=only_section)
    if limit_sections is not None:
        selected_nodes = selected_nodes[:limit_sections]
    if not selected_nodes:
        raise ValueError(
            "no Montana Administrative Rules sections selected "
            f"for title={only_title!r} section={only_section!r}"
        )

    inventory: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    source_paths: list[Path] = [collection_snapshot.source_path, tree_snapshot.source_path]
    errors: list[str] = []
    skipped_source_count = 0
    root_path = "us-mt/regulation"

    inventory.append(
        SourceInventoryItem(
            citation_path=root_path,
            source_url=MONTANA_RULES_HOME_URL,
            source_path=collection_snapshot.source_key,
            source_format=MONTANA_RULES_JSON_FORMAT,
            sha256=collection_snapshot.sha256,
            metadata={
                "kind": "collection",
                "collection_uuid": collection_uuid,
                "tree_source_path": tree_snapshot.source_key,
                "source_as_of": source_as_of_text,
                "selected_section_count": len(selected_nodes),
                "total_section_count": len(all_nodes),
                "include_not_effective": include_not_effective,
            },
        )
    )
    records.append(
        _root_record(
            version=run_id,
            source_path=collection_snapshot.source_key,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            collection_uuid=collection_uuid,
            selected_section_count=len(selected_nodes),
            total_section_count=len(all_nodes),
            include_not_effective=include_not_effective,
        )
    )

    section_results = _snapshot_sections(
        store,
        run_id=run_id,
        collection_uuid=collection_uuid,
        nodes=tuple(selected_nodes),
        include_not_effective=include_not_effective,
        source_root=source_root,
        download_root=download_root,
        workers=workers,
        progress_stream=progress_stream,
    )
    section_results = tuple(sorted(section_results, key=lambda result: result.node.ordinal))
    section_by_uuid = {result.node.uuid: result for result in section_results}
    for result in section_results:
        if result.snapshot is not None:
            source_paths.append(result.snapshot.source_path)
        if result.error:
            errors.append(result.error)
            skipped_source_count += 1

    selected_policies: list[tuple[_SectionNode, dict[str, Any]]] = []
    for result in section_results:
        for policy in result.policies:
            selected_policies.append((result.node, policy))
    selected_policies = _dedupe_policies(selected_policies)
    if limit_rules is not None:
        selected_policies = selected_policies[:limit_rules]
    if not selected_policies:
        raise ValueError("no Montana Administrative Rules policies extracted")

    needed_node_uuids = _needed_node_uuids(selected_policies)
    nodes_by_uuid = {node.uuid: node for node in all_nodes}
    tree_order = {node.uuid: index for index, node in enumerate(all_nodes)}
    for node in sorted(
        (nodes_by_uuid[uuid] for uuid in needed_node_uuids if uuid in nodes_by_uuid),
        key=lambda item: tree_order[item.uuid],
    ):
        snapshot = section_by_uuid.get(node.uuid).snapshot if node.uuid in section_by_uuid else None
        source_snapshot = snapshot or tree_snapshot
        _append_section_node(
            node,
            collection_uuid=collection_uuid,
            snapshot=source_snapshot,
            inventory=inventory,
            records=records,
            version=run_id,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            direct_rule_count=len(section_by_uuid.get(node.uuid).policies)
            if node.uuid in section_by_uuid
            else 0,
            tree_source_path=tree_snapshot.source_key,
        )

    policy_results = _snapshot_policies(
        store,
        run_id=run_id,
        collection_uuid=collection_uuid,
        policies=tuple(selected_policies),
        source_root=source_root,
        download_root=download_root,
        workers=workers,
        progress_stream=progress_stream,
    )
    policy_results = tuple(
        sorted(
            policy_results,
            key=lambda result: (
                result.parent.ordinal,
                str((result.policy or result.stub).get("citationId") or result.stub.get("sectionId") or ""),
            ),
        )
    )
    rule_count = 0
    for result in policy_results:
        if result.policy_snapshot is not None:
            source_paths.append(result.policy_snapshot.source_path)
        if result.html_snapshot is not None:
            source_paths.append(result.html_snapshot.source_path)
        if result.error:
            errors.append(result.error)
            skipped_source_count += 1
        if result.policy is None:
            continue
        _append_rule(
            result,
            collection_uuid=collection_uuid,
            inventory=inventory,
            records=records,
            version=run_id,
            source_as_of=source_as_of_text,
            expression_date=expression_date_text,
            ordinal=rule_count + 1,
        )
        rule_count += 1

    if rule_count == 0:
        raise ValueError("no Montana Administrative Rules rule records extracted")

    inventory_path = store.inventory_path(jurisdiction, document_class, run_id)
    store.write_inventory(inventory_path, inventory)
    provisions_path = store.provisions_path(jurisdiction, document_class, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
    )
    coverage_path = store.coverage_path(jurisdiction, document_class, run_id)
    store.write_json(coverage_path, coverage.to_mapping())

    emitted_nodes = [node for node in all_nodes if node.uuid in needed_node_uuids]
    return MontanaAdminRulesExtractReport(
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=run_id,
        title_count=sum(1 for node in emitted_nodes if node.kind == "title"),
        chapter_count=sum(1 for node in emitted_nodes if node.kind == "chapter"),
        subchapter_count=sum(1 for node in emitted_nodes if node.kind == "subchapter"),
        rule_count=rule_count,
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
        skipped_source_count=skipped_source_count,
        errors=tuple(errors),
    )


def _snapshot_sections(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    collection_uuid: str,
    nodes: tuple[_SectionNode, ...],
    include_not_effective: bool,
    source_root: Path | None,
    download_root: Path | None,
    workers: int,
    progress_stream: TextIO | None,
) -> tuple[_SectionSnapshot, ...]:
    if workers <= 1:
        return tuple(
            _snapshot_section(
                store,
                run_id=run_id,
                collection_uuid=collection_uuid,
                node=node,
                include_not_effective=include_not_effective,
                source_root=source_root,
                download_root=download_root,
                progress_stream=progress_stream,
            )
            for node in nodes
        )
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _snapshot_section,
                store,
                run_id=run_id,
                collection_uuid=collection_uuid,
                node=node,
                include_not_effective=include_not_effective,
                source_root=source_root,
                download_root=download_root,
                progress_stream=progress_stream,
            )
            for node in nodes
        ]
        return tuple(future.result() for future in as_completed(futures))


def _snapshot_section(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    collection_uuid: str,
    node: _SectionNode,
    include_not_effective: bool,
    source_root: Path | None,
    download_root: Path | None,
    progress_stream: TextIO | None,
) -> _SectionSnapshot:
    _progress(progress_stream, f"montana-admin-rules section {node.section_id}")
    relative_name = f"{_SOURCE_PREFIX}/sections/{_path_token(node.section_id)}-{node.uuid}.json"
    try:
        snapshot = _snapshot_json(
            store,
            run_id=run_id,
            relative_name=relative_name,
            url=_api_url(f"collections/{collection_uuid}/sections/{node.uuid}"),
            source_root=source_root,
            download_root=download_root,
        )
        payload = _json_payload(snapshot.content)
        policies = tuple(
            policy
            for policy in payload.get("childPolicies", [])
            if include_not_effective or policy.get("effectiveStatus") == "EFFECTIVE"
        )
        return _SectionSnapshot(node=node, snapshot=snapshot, policies=policies)
    except (OSError, ValueError, requests.RequestException) as exc:
        return _SectionSnapshot(
            node=node,
            snapshot=None,
            policies=(),
            error=f"section {node.section_id}: {exc}",
        )


def _snapshot_policies(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    collection_uuid: str,
    policies: tuple[tuple[_SectionNode, dict[str, Any]], ...],
    source_root: Path | None,
    download_root: Path | None,
    workers: int,
    progress_stream: TextIO | None,
) -> tuple[_PolicySnapshot, ...]:
    if workers <= 1:
        return tuple(
            _snapshot_policy(
                store,
                run_id=run_id,
                collection_uuid=collection_uuid,
                parent=parent,
                stub=stub,
                source_root=source_root,
                download_root=download_root,
                progress_stream=progress_stream,
            )
            for parent, stub in policies
        )
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _snapshot_policy,
                store,
                run_id=run_id,
                collection_uuid=collection_uuid,
                parent=parent,
                stub=stub,
                source_root=source_root,
                download_root=download_root,
                progress_stream=progress_stream,
            )
            for parent, stub in policies
        ]
        return tuple(future.result() for future in as_completed(futures))


def _snapshot_policy(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    collection_uuid: str,
    parent: _SectionNode,
    stub: dict[str, Any],
    source_root: Path | None,
    download_root: Path | None,
    progress_stream: TextIO | None,
) -> _PolicySnapshot:
    policy_uuid = str(stub.get("uuid") or "")
    citation_id = str(stub.get("sectionId") or _field_value(stub.get("policyFields"), "citation_id") or policy_uuid)
    _progress(progress_stream, f"montana-admin-rules rule {citation_id}")
    policy_snapshot: _SourceSnapshot | None = None
    html_snapshot: _SourceSnapshot | None = None
    body: str | None = None
    references: tuple[str, ...] = ()
    try:
        policy_snapshot = _snapshot_json(
            store,
            run_id=run_id,
            relative_name=f"{_SOURCE_PREFIX}/policies/{_path_token(citation_id)}-{policy_uuid}.json",
            url=_api_url(f"collections/{collection_uuid}/policies/{policy_uuid}"),
            source_root=source_root,
            download_root=download_root,
        )
        policy = _json_payload(policy_snapshot.content).get("policy")
        if not isinstance(policy, dict):
            raise ValueError("policy payload missing policy object")
        active_version = _active_version(policy)
        html_doc = active_version.get("accessibleHtmlDocument") if active_version else None
        if isinstance(html_doc, dict) and html_doc.get("contentUrl"):
            html_url = _absolute_url(str(html_doc["contentUrl"]))
            html_snapshot = _snapshot_bytes(
                store,
                run_id=run_id,
                relative_name=f"{_SOURCE_PREFIX}/html/{_path_token(citation_id)}-{policy_uuid}.html",
                url=html_url,
                source_root=source_root,
                download_root=download_root,
            )
            body = _html_body_text(html_snapshot.content)
            self_ref = f"us-mt/regulation/rule-{_path_token(citation_id)}"
            references = tuple(
                ref for ref in _references_to(html_snapshot.content, body or "") if ref != self_ref
            )
        return _PolicySnapshot(
            parent=parent,
            stub=stub,
            policy_snapshot=policy_snapshot,
            html_snapshot=html_snapshot,
            policy=policy,
            body=body,
            references_to=references,
        )
    except (OSError, ValueError, requests.RequestException) as exc:
        return _PolicySnapshot(
            parent=parent,
            stub=stub,
            policy_snapshot=policy_snapshot,
            html_snapshot=html_snapshot,
            policy=None,
            body=body,
            references_to=references,
            error=f"policy {citation_id}: {exc}",
        )


_thread_state = local()


def _session() -> requests.Session:
    session = getattr(_thread_state, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": MONTANA_RULES_USER_AGENT})
        _thread_state.session = session
    return session


def _snapshot_json(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    relative_name: str,
    url: str,
    source_root: Path | None,
    download_root: Path | None,
) -> _SourceSnapshot:
    return _snapshot_bytes(
        store,
        run_id=run_id,
        relative_name=relative_name,
        url=url,
        source_root=source_root,
        download_root=download_root,
    )


def _snapshot_bytes(
    store: CorpusArtifactStore,
    *,
    run_id: str,
    relative_name: str,
    url: str,
    source_root: Path | None,
    download_root: Path | None,
) -> _SourceSnapshot:
    source_path = store.source_path("us-mt", DocumentClass.REGULATION, run_id, relative_name)
    source_key = _source_key(run_id, relative_name)
    if source_root is None and source_path.exists():
        content = source_path.read_bytes()
        return _SourceSnapshot(
            source_key=source_key,
            source_path=source_path,
            sha256=sha256_bytes(content),
            content=content,
            source_url=url,
        )
    content = _load_bytes(
        source_root,
        download_root,
        relative_name=relative_name,
        url=url,
    )
    sha256 = store.write_bytes(source_path, content)
    return _SourceSnapshot(
        source_key=source_key,
        source_path=source_path,
        sha256=sha256,
        content=content,
        source_url=url,
    )


def _load_bytes(
    source_root: Path | None,
    download_root: Path | None,
    *,
    relative_name: str,
    url: str,
) -> bytes:
    if source_root is not None:
        return (source_root / relative_name).read_bytes()
    if download_root is not None:
        cached = download_root / relative_name
        if cached.exists():
            return cached.read_bytes()
    response = _get_with_retries(_session(), url)
    content = response.content
    if download_root is not None:
        cached = download_root / relative_name
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(content)
    return content


def _get_with_retries(
    session: requests.Session,
    url: str,
    *,
    attempts: int = 5,
) -> requests.Response:
    delay = 1.0
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=90)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            if attempt == attempts or status not in {429, 500, 502, 503, 504}:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 20)
    assert last_error is not None
    raise last_error


def _json_payload(content: bytes) -> dict[str, Any]:
    payload = json.loads(content.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    return payload


def _find_arm_collection(payload: dict[str, Any]) -> dict[str, Any]:
    collections = payload.get("collections")
    if not isinstance(collections, list):
        raise ValueError("collections payload missing collections list")
    for collection in collections:
        if isinstance(collection, dict) and collection.get("name") == MONTANA_RULES_COLLECTION_NAME:
            return collection
    raise ValueError(f"collection not found: {MONTANA_RULES_COLLECTION_NAME}")


def _parse_tree_nodes(tree: dict[str, Any]) -> list[_SectionNode]:
    nodes: list[_SectionNode] = []

    def walk(
        item: dict[str, Any],
        *,
        parent_uuid: str | None,
        parent_path: str,
        ancestors: tuple[str, ...],
    ) -> None:
        for child in item.get("childFolders") or []:
            if not isinstance(child, dict) or not child.get("uuid") or not child.get("sectionId"):
                continue
            section_id = str(child["sectionId"])
            kind = _node_kind(str(child.get("sectionType") or ""), section_id)
            citation_path = f"{parent_path}/{kind}-{_path_token(_node_display_id(kind, section_id))}"
            uuid = str(child["uuid"])
            node = _SectionNode(
                uuid=uuid,
                section_id=section_id,
                name=str(child.get("name") or ""),
                section_type=str(child.get("sectionType") or ""),
                category=child.get("category"),
                effective_status=child.get("effectiveStatus"),
                substatuses=tuple(str(value) for value in child.get("substatuses") or ()),
                parent_uuid=parent_uuid,
                ancestor_uuids=ancestors,
                citation_path=citation_path,
                ordinal=len(nodes) + 1,
            )
            nodes.append(node)
            walk(
                child,
                parent_uuid=uuid,
                parent_path=citation_path,
                ancestors=ancestors + (uuid,),
            )

    walk(tree, parent_uuid=None, parent_path="us-mt/regulation", ancestors=())
    return nodes


def _select_nodes(
    nodes: list[_SectionNode],
    *,
    only_title: str | None,
    only_section: str | None,
) -> list[_SectionNode]:
    selected = nodes
    if only_title is not None:
        title_token = _path_token(only_title)
        title_uuids = {
            node.uuid
            for node in selected
            if node.kind == "title" and _section_id_matches(node, title_token)
        }
        selected = [
            node
            for node in selected
            if node.uuid in title_uuids or any(uuid in title_uuids for uuid in node.ancestor_uuids)
        ]
    if only_section is not None:
        section_token = _path_token(only_section)
        section_uuids = {
            node.uuid for node in selected if _section_id_matches(node, section_token)
        }
        selected = [
            node
            for node in selected
            if node.uuid in section_uuids or any(uuid in section_uuids for uuid in node.ancestor_uuids)
        ]
    return selected


def _dedupe_policies(
    policies: list[tuple[_SectionNode, dict[str, Any]]],
) -> list[tuple[_SectionNode, dict[str, Any]]]:
    deduped: list[tuple[_SectionNode, dict[str, Any]]] = []
    seen: set[str] = set()
    for parent, policy in policies:
        uuid = str(policy.get("uuid") or "")
        if not uuid or uuid in seen:
            continue
        seen.add(uuid)
        deduped.append((parent, policy))
    return deduped


def _needed_node_uuids(policies: Iterable[tuple[_SectionNode, dict[str, Any]]]) -> set[str]:
    needed: set[str] = set()
    for parent, _policy in policies:
        needed.add(parent.uuid)
        needed.update(parent.ancestor_uuids)
    return needed


def _append_section_node(
    node: _SectionNode,
    *,
    collection_uuid: str,
    snapshot: _SourceSnapshot,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
    direct_rule_count: int,
    tree_source_path: str,
) -> None:
    source_url = node.source_url.format(collection_uuid=collection_uuid)
    metadata: dict[str, object] = {
        "kind": node.kind,
        "collection_uuid": collection_uuid,
        "section_uuid": node.uuid,
        "section_id": node.section_id,
        "section_type": node.section_type,
        "effective_status": node.effective_status,
        "substatuses": list(node.substatuses),
        "direct_rule_count": direct_rule_count,
        "tree_source_path": tree_source_path,
        "source_as_of": source_as_of,
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}
    inventory.append(
        SourceInventoryItem(
            citation_path=node.citation_path,
            source_url=source_url,
            source_path=snapshot.source_key,
            source_format=MONTANA_RULES_JSON_FORMAT,
            sha256=snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=node.citation_path,
            parent_citation_path=(
                "us-mt/regulation"
                if node.parent_uuid is None
                else _parent_path_from_record(records, node.parent_uuid)
            ),
            citation_label=node.label,
            heading=node.heading,
            body=None,
            version=version,
            source_url=source_url,
            source_path=snapshot.source_key,
            source_format=MONTANA_RULES_JSON_FORMAT,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level={"title": 1, "chapter": 2, "subchapter": 3}.get(node.kind, 3),
            ordinal=node.ordinal,
            kind=node.kind,
            legal_identifier=node.label,
            identifiers={
                "montana:arm_section": node.section_id,
                "montana:section_uuid": node.uuid,
            },
            metadata=metadata,
        )
    )


def _append_rule(
    result: _PolicySnapshot,
    *,
    collection_uuid: str,
    inventory: list[SourceInventoryItem],
    records: list[ProvisionRecord],
    version: str,
    source_as_of: str,
    expression_date: str,
    ordinal: int,
) -> None:
    policy = result.policy
    assert policy is not None
    citation_id = str(policy.get("citationId") or result.stub.get("sectionId") or "")
    policy_uuid = str(policy.get("uuid") or result.stub.get("uuid") or "")
    active_version = _active_version(policy)
    version_uuid = str(active_version.get("uuid") or "") if active_version else None
    fields = list(policy.get("fields") or [])
    if active_version:
        fields.extend(active_version.get("fields") or [])
    history = _field_value(fields, "history")
    effective_start = _field_value(fields, "effective_start_date") or (
        active_version.get("effectiveStartDate") if active_version else None
    )
    effective_end = _field_value(fields, "effective_end_date") or (
        active_version.get("effectiveEndDate") if active_version else None
    )
    html_snapshot = result.html_snapshot
    policy_snapshot = result.policy_snapshot
    source_snapshot = html_snapshot or policy_snapshot
    assert source_snapshot is not None
    source_format = MONTANA_RULES_HTML_FORMAT if html_snapshot else MONTANA_RULES_JSON_FORMAT
    source_url = (
        html_snapshot.source_url
        if html_snapshot is not None
        else f"{MONTANA_RULES_HOME_URL}browse/collections/{collection_uuid}/policies/{policy_uuid}"
    )
    metadata: dict[str, object] = {
        "kind": "rule",
        "collection_uuid": collection_uuid,
        "policy_uuid": policy_uuid,
        "policy_version_uuid": version_uuid,
        "version_number": _field_value(fields, "version_number")
        or (active_version.get("number") if active_version else None),
        "effective_status": policy.get("effectiveStatus") or result.stub.get("effectiveStatus"),
        "substatuses": list(policy.get("substatuses") or result.stub.get("substatuses") or []),
        "effective_start_date": effective_start,
        "effective_end_date": effective_end,
        "history": history,
        "contact_information": _field_value(fields, "contact_information"),
        "references_to": list(result.references_to),
        "policy_json_source_path": policy_snapshot.source_key if policy_snapshot else None,
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}
    citation_path = f"{result.parent.citation_path}/rule-{_path_token(citation_id)}"
    inventory.append(
        SourceInventoryItem(
            citation_path=citation_path,
            source_url=source_url,
            source_path=source_snapshot.source_key,
            source_format=source_format,
            sha256=source_snapshot.sha256,
            metadata=metadata,
        )
    )
    records.append(
        _record(
            citation_path=citation_path,
            parent_citation_path=result.parent.citation_path,
            citation_label=f"ARM {citation_id}",
            heading=str(policy.get("name") or result.stub.get("name") or citation_id),
            body=result.body,
            version=version,
            source_url=source_url,
            source_path=source_snapshot.source_key,
            source_id=policy_uuid,
            source_format=source_format,
            source_as_of=source_as_of,
            expression_date=expression_date,
            level=4,
            ordinal=ordinal,
            kind="rule",
            legal_identifier=f"ARM {citation_id}",
            identifiers={
                "montana:arm_rule": citation_id,
                "montana:policy_uuid": policy_uuid,
                **({"montana:policy_version_uuid": version_uuid} if version_uuid else {}),
            },
            metadata=metadata,
        )
    )


def _parent_path_from_record(records: list[ProvisionRecord], parent_uuid: str) -> str | None:
    for record in reversed(records):
        metadata = record.metadata or {}
        if metadata.get("section_uuid") == parent_uuid:
            return record.citation_path
    return "us-mt/regulation"


def _root_record(
    *,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    collection_uuid: str,
    selected_section_count: int,
    total_section_count: int,
    include_not_effective: bool,
) -> ProvisionRecord:
    return _record(
        citation_path="us-mt/regulation",
        citation_label="Administrative Rules of Montana",
        heading="Administrative Rules of Montana",
        body=None,
        version=version,
        source_url=MONTANA_RULES_HOME_URL,
        source_path=source_path,
        source_format=MONTANA_RULES_JSON_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        level=0,
        ordinal=0,
        kind="collection",
        legal_identifier="Administrative Rules of Montana",
        identifiers={"state:code": "ARM", "montana:collection_uuid": collection_uuid},
        metadata={
            "collection_uuid": collection_uuid,
            "selected_section_count": selected_section_count,
            "total_section_count": total_section_count,
            "include_not_effective": include_not_effective,
        },
    )


def _record(
    *,
    citation_path: str,
    heading: str | None,
    body: str | None,
    version: str,
    source_url: str,
    source_path: str,
    source_format: str,
    source_as_of: str,
    expression_date: str,
    level: int,
    ordinal: int | None,
    kind: str,
    parent_citation_path: str | None = None,
    citation_label: str | None = None,
    source_id: str | None = None,
    legal_identifier: str | None = None,
    identifiers: dict[str, str] | None = None,
    metadata: dict[str, object] | None = None,
) -> ProvisionRecord:
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path),
        jurisdiction="us-mt",
        document_class=DocumentClass.REGULATION.value,
        citation_path=citation_path,
        citation_label=citation_label,
        heading=heading,
        body=body,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id=source_id,
        source_format=source_format,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=parent_citation_path,
        parent_id=(
            deterministic_provision_id(parent_citation_path) if parent_citation_path else None
        ),
        level=level,
        ordinal=ordinal,
        kind=kind,
        legal_identifier=legal_identifier,
        identifiers=identifiers,
        metadata=metadata,
    )


def _active_version(policy: dict[str, Any]) -> dict[str, Any]:
    versions = [version for version in policy.get("policyVersions") or [] if isinstance(version, dict)]
    current_uuid = policy.get("currentVersionUuid")
    for version in versions:
        if version.get("isActive") is True and (
            current_uuid is None or version.get("uuid") == current_uuid
        ):
            return version
    for version in versions:
        if version.get("isActive") is True:
            return version
    for version in versions:
        if current_uuid is not None and version.get("uuid") == current_uuid:
            return version
    return versions[0] if versions else {}


def _html_body_text(content: bytes) -> str | None:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "meta"]):
        tag.decompose()
    body = soup.select_one("#documentBody") or soup.body or soup
    _prefix_ordered_list_items(body)
    text = body.get_text("\n", strip=True)
    return _clean_body(text)


def _prefix_ordered_list_items(body: Tag | BeautifulSoup) -> None:
    for ordered_list in body.find_all("ol"):
        list_class = " ".join(ordered_list.get("class") or [])
        for index, item in enumerate(ordered_list.find_all("li", recursive=False), start=1):
            marker = _list_marker(list_class, item, index)
            first = item.contents[0] if item.contents else None
            if isinstance(first, NavigableString):
                item.contents[0].replace_with(f"{marker} {first}")
            else:
                item.insert(0, f"{marker} ")


def _list_marker(list_class: str, item: Tag, index: int) -> str:
    style = item.get("style")
    marker_index = index
    if isinstance(style, str):
        match = re.search(r"counter-set:\s*list-item\s+(\d+)", style)
        if match:
            marker_index = int(match.group(1))
    if "lower-alpha" in list_class:
        value = _alpha(marker_index).lower()
    elif "upper-alpha" in list_class:
        value = _alpha(marker_index).upper()
    elif "lower-roman" in list_class:
        value = _roman(marker_index).lower()
    else:
        value = str(marker_index)
    return f"({value})"


def _references_to(html: bytes, text: str) -> tuple[str, ...]:
    refs: list[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(attrs={"citation-id": True}):
        citation = str(tag.get("citation-id") or "")
        refs.extend(_reference_from_citation_id(citation))
    for match in _ARM_REF_RE.finditer(text):
        refs.append(f"us-mt/regulation/rule-{_path_token(match.group('cite'))}")
    for match in _MCA_REF_RE.finditer(text):
        refs.append(f"us-mt/statute/{_normalize_mca_citation(match.group('cite'))}")
    return _unique(refs)


def _reference_from_citation_id(citation: str) -> list[str]:
    cleaned = citation.strip()
    refs: list[str] = []
    if "MCA" in cleaned.upper():
        for match in _MCA_REF_RE.finditer(cleaned):
            refs.append(f"us-mt/statute/{_normalize_mca_citation(match.group('cite'))}")
        return refs
    for match in _ARM_BARE_REF_RE.finditer(cleaned):
        refs.append(f"us-mt/regulation/rule-{_path_token(match.group('cite'))}")
    return refs


def _field_value(fields: Any, key: str) -> str | None:
    if not isinstance(fields, list):
        return None
    for field in fields:
        if isinstance(field, dict) and field.get("key") == key and field.get("value") is not None:
            return str(field["value"])
    return None


def _node_kind(section_type: str, section_id: str) -> str:
    normalized = section_type.strip().lower()
    if normalized in {"title", "chapter", "subchapter"}:
        return normalized
    section_text = section_id.strip().lower()
    if section_text.startswith("chapter"):
        return "chapter"
    if section_text.startswith("subchapter"):
        return "subchapter"
    return "section"


def _node_display_id(kind: str, section_id: str) -> str:
    text = _clean_text(section_id)
    if kind in {"chapter", "subchapter"}:
        match = re.match(rf"(?i)^{kind}\s+(.+)$", text)
        if match:
            return match.group(1).strip()
    return text


def _section_id_matches(node: _SectionNode, token: str) -> bool:
    return token in {
        _path_token(node.section_id),
        _path_token(node.display_id),
    }


def _api_url(path: str) -> str:
    return f"{MONTANA_RULES_API_BASE_URL}/{path.lstrip('/')}"


def _absolute_url(path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return f"{MONTANA_RULES_BASE_URL}/{path_or_url.lstrip('/')}"


def _source_key(run_id: str, relative_name: str) -> str:
    return f"sources/us-mt/regulation/{run_id}/{relative_name}"


def _path_token(value: str) -> str:
    token = _clean_text(value).lower()
    token = token.replace(".", "-")
    token = re.sub(r"[^a-z0-9]+", "-", token).strip("-")
    return safe_segment(token or "unknown")


def _normalize_mca_citation(value: str) -> str:
    parts = value.split("-")
    normalized: list[str] = []
    for part in parts:
        if part.isdigit():
            normalized.append(str(int(part)))
        else:
            normalized.append(part.upper())
    return "-".join(normalized)


def _clean_body(value: str) -> str | None:
    text = _clean_text(value)
    return text or None


def _clean_text(value: str) -> str:
    text = value.replace("\xa0", " ").replace("\ufffd", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    return text.strip()


def _date_text(value: date | str | None, fallback: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return value or fallback


def _progress(stream: TextIO | None, message: str) -> None:
    if stream is not None:
        print(message, file=stream, flush=True)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _alpha(value: int) -> str:
    letters = ""
    number = max(value, 1)
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(97 + remainder) + letters
    return letters


def _roman(value: int) -> str:
    pairs = (
        (1000, "m"),
        (900, "cm"),
        (500, "d"),
        (400, "cd"),
        (100, "c"),
        (90, "xc"),
        (50, "l"),
        (40, "xl"),
        (10, "x"),
        (9, "ix"),
        (5, "v"),
        (4, "iv"),
        (1, "i"),
    )
    number = max(value, 1)
    out = ""
    for arabic, roman in pairs:
        count, number = divmod(number, arabic)
        out += roman * count
    return out


if __name__ == "__main__":  # pragma: no cover
    from axiom_corpus.corpus.cli import main

    raise SystemExit(main(sys.argv[1:]))
