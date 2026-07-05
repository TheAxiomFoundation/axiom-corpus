"""Provision anchors — a derived, rebuildable leaf-level annotation layer.

Ratified 2026-07-04 (``docs/granularity-policy-proposal.md`` §4, "the annotation
layer is a real table that goes to the drafted leaves"). One
:class:`ProvisionAnchor` row per drafted leaf, keyed by its **citation path**,
carrying char offsets into an *asserted* parent provision, the leaf text as a
verified-derived column (byte-equal to the parent slice), extraction provenance,
and a confidence field.

Why a separate layer at all
---------------------------
``corpus.provisions`` stores structure at exactly the depth the official source
*asserts* (the assertion frontier): USLM statutes assert to paragraph/clause,
eCFR asserts only to the section, manuals assert to the block/page. Paragraph
hierarchy *inside* a CFR section is indentation typography, not identified nodes
— two reasonable parsers disagree about where ``(d)(6)(iii)`` ends, and baking
that judgement into ``uuid5(citation_path)`` identity would make a heuristic
load-bearing for every grounding, claim, and staleness pin. So sub-frontier
structure lives here as **re-derivable annotation**: a wrong span is a
re-derivation; a wrong identity is a migration across every consumer.

Disciplines (enforced by this module and its tests)
---------------------------------------------------
* **Derived and rebuildable** from ``(provisions x extractor version)``. A
  boundary correction is a rebuild plus a parent-hash re-check, never a
  migration.
* **Byte-equal gate**: ``anchor.text`` must equal
  ``parent.body[char_start:char_end]`` exactly. Corrupting an offset fails
  verification.
* **Label-at-head gate**: the printed label (``(d)``, ``(6)``, ``(iii)``,
  ``(A)``) must appear at the span head.
* **The leaf path is the stable key** (paths are printed labels — a boundary
  fix changes offsets, not the key). Groundings of record cite
  ``(asserted provision id, leaf path, span)``, never an anchor-row surrogate.
* **Confidence** distinguishes ``machine_asserted`` (a span pass-through from a
  deeper provision the publisher already asserts) from ``label_inferred`` (a
  span the extractor inferred from printed-label typography).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.models import ProvisionRecord

# --------------------------------------------------------------------------- #
# Constants                                                                     #
# --------------------------------------------------------------------------- #

#: Bumped when the generation algorithm changes such that offsets could move.
#: The table is rebuildable from (provisions x this version); the pair is the
#: cache key for a rebuild. Any change to :func:`generate_anchors` output for
#: identical input MUST bump this.
EXTRACTOR_VERSION = "provision-anchors/1.0.0"

CONFIDENCE_MACHINE_ASSERTED = "machine_asserted"
CONFIDENCE_LABEL_INFERRED = "label_inferred"
_CONFIDENCE_VALUES = frozenset(
    {CONFIDENCE_MACHINE_ASSERTED, CONFIDENCE_LABEL_INFERRED}
)

_STATUS_ACTIVE = "active"

# Roman-numeral (lowercase) recognizer for i..xxxix, used to disambiguate a
# lowercase alpha label from a lowercase roman label by outline context.
_ROMAN_LOWER = re.compile(r"^(?:x{0,3})(?:ix|iv|v?i{0,3})$")
_ROMAN_UPPER = re.compile(r"^(?:X{0,3})(?:IX|IV|V?I{0,3})$")

# A printed paragraph label token as it appears at a span head: "(d)", "(6)",
# "(iii)", "(A)". Alphanumeric, 1-6 chars, parenthesized.
_LABEL_TOKEN = re.compile(r"\(([A-Za-z0-9]{1,6})\)")

# A *strong* paragraph head: a label at start-of-body or immediately after a
# newline (eCFR flattens each labeled paragraph onto its own line), OR inline
# after an em-dash / en-dash (eCFR runs the first child onto the parent line,
# e.g. "(6) Shelter costs—(i) Homeless shelter deduction."). Strong heads are
# always treated as structure.
_HEAD = re.compile(r"(?:\A|\n|[—–])\s*(\([A-Za-z0-9]{1,6}\))")

# A *weak* (candidate) inline head: a single label after sentence-terminal
# punctuation (". " / ": " / ".\n\n"), e.g. eCFR's inline first child
# "(iii) Standard utility allowances. (A) A State agency may use…". This is
# ambiguous with cross-references ("paragraph (d)(6)(ii)(C)") and parentheticals
# ("(standards)"), so a weak head is only accepted during tree building when it
# is exactly the expected next outline child of the currently open node — never
# on its own. The trailing lookahead requires a following char that is not
# another "(", which rejects multi-segment reference runs like "(d)(6)(ii)".
_WEAK_HEAD = re.compile(r"[.:]\s+(\([A-Za-z0-9]{1,4}\))(?=[^(])")


# --------------------------------------------------------------------------- #
# Data model                                                                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProvisionAnchor:
    """One drafted leaf inside an asserted parent provision.

    ``citation_path`` is the stable key. ``parent_provision_id`` /
    ``parent_citation_path`` name the asserted row this leaf lives in;
    ``char_start`` / ``char_end`` are byte offsets (Python ``str`` indices, which
    are code points — ASCII regulatory text makes these equal) into
    ``parent`` body; ``text`` is the verified-derived slice.
    """

    citation_path: str
    parent_provision_id: str
    parent_citation_path: str
    char_start: int
    char_end: int
    text: str
    label: str
    depth: int
    confidence: str = CONFIDENCE_LABEL_INFERRED
    status: str = _STATUS_ACTIVE
    extractor_version: str = EXTRACTOR_VERSION
    #: sha256 of the parent body at generation time. A parent edit changes this
    #: hash and triggers a re-check on rebuild.
    parent_body_sha256: str = ""
    jurisdiction: str | None = None
    document_class: str | None = None
    version: str | None = None
    ordinal: int | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.confidence not in _CONFIDENCE_VALUES:
            raise ValueError(
                f"confidence must be one of {sorted(_CONFIDENCE_VALUES)}; "
                f"got {self.confidence!r}"
            )
        if self.char_start < 0 or self.char_end < self.char_start:
            raise ValueError(
                f"invalid span [{self.char_start}, {self.char_end}) for "
                f"{self.citation_path!r}"
            )

    @property
    def span(self) -> tuple[int, int]:
        return (self.char_start, self.char_end)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ProvisionAnchor:
        return cls(
            citation_path=str(data["citation_path"]),
            parent_provision_id=str(data["parent_provision_id"]),
            parent_citation_path=str(data["parent_citation_path"]),
            char_start=int(data["char_start"]),
            char_end=int(data["char_end"]),
            text=str(data["text"]),
            label=str(data["label"]),
            depth=int(data["depth"]),
            confidence=str(data.get("confidence", CONFIDENCE_LABEL_INFERRED)),
            status=str(data.get("status", _STATUS_ACTIVE)),
            extractor_version=str(data.get("extractor_version", EXTRACTOR_VERSION)),
            parent_body_sha256=str(data.get("parent_body_sha256", "")),
            jurisdiction=data.get("jurisdiction"),
            document_class=data.get("document_class"),
            version=data.get("version"),
            ordinal=data.get("ordinal"),
            metadata=(
                dict(data["metadata"])
                if isinstance(data.get("metadata"), Mapping)
                else None
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "citation_path": self.citation_path,
            "parent_provision_id": self.parent_provision_id,
            "parent_citation_path": self.parent_citation_path,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "text": self.text,
            "label": self.label,
            "depth": self.depth,
            "confidence": self.confidence,
            "status": self.status,
            "extractor_version": self.extractor_version,
            "parent_body_sha256": self.parent_body_sha256,
        }
        for key in ("jurisdiction", "document_class", "version", "ordinal"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.metadata:
            out["metadata"] = self.metadata
        return out


# --------------------------------------------------------------------------- #
# Parsing                                                                        #
# --------------------------------------------------------------------------- #


def body_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass
class _Head:
    """A printed label occurrence at a paragraph head."""

    offset: int  # index of the '(' character
    token: str  # label token without parens, e.g. "d", "6", "iii", "A"
    weak: bool = False  # inline candidate; accept only if outline-valid


def _scan_heads(body: str) -> list[_Head]:
    """Return every paragraph-head label occurrence, in document order.

    Emits *strong* heads (line-leading or em/en-dash inline first children) and
    *weak* inline candidates (a single label after ". "/": "). Weak candidates
    at an offset already claimed by a strong head are dropped; the rest are only
    accepted by :func:`_build_tree` when they are the expected next outline
    child, which filters out cross-references and parentheticals.
    """
    strong_offsets: set[int] = set()
    heads: list[_Head] = []
    for match in _HEAD.finditer(body):
        offset = match.start(1)
        strong_offsets.add(offset)
        heads.append(_Head(offset=offset, token=match.group(1)[1:-1]))
    for match in _WEAK_HEAD.finditer(body):
        offset = match.start(1)
        if offset in strong_offsets:
            continue
        heads.append(_Head(offset=offset, token=match.group(1)[1:-1], weak=True))
    heads.sort(key=lambda h: h.offset)
    return heads


def _token_forms(token: str) -> frozenset[str]:
    """The outline *forms* a token could take.

    A token can be ambiguous: 'i' is both a lowercase-alpha and a lowercase
    roman numeral; 'A'/'B'/... uppercase alpha vs uppercase roman ('I','V','X').
    We return the candidate set; :func:`_build_tree` resolves by outline order.
    """
    forms: set[str] = set()
    if token.isdigit():
        forms.add("digit")
        return frozenset(forms)
    if token.isalpha() and token.islower():
        forms.add("alpha_lower")
        if _ROMAN_LOWER.match(token):
            forms.add("roman_lower")
        return frozenset(forms)
    if token.isalpha() and token.isupper():
        forms.add("alpha_upper")
        if _ROMAN_UPPER.match(token):
            forms.add("roman_upper")
        return frozenset(forms)
    return frozenset({"other"})


# The CFR / common-law outline order. A child's form is the next form after its
# parent's form. We use this to (a) infer depth and (b) disambiguate roman vs
# alpha. Statutes (USLM-flattened) and manuals reuse the same ladder.
_OUTLINE_LADDER: tuple[str, ...] = (
    "alpha_lower",  # (a)
    "digit",  # (1)
    "roman_lower",  # (i)
    "alpha_upper",  # (A)
    "digit",  # (1)   (repeats)
    "alpha_lower",  # (a)   (repeats)
    "roman_lower",  # (i)   (repeats)
    "alpha_upper",  # (A)   (repeats)
)

_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def _label_ordinal(token: str, form: str) -> int | None:
    """Position of a label within its sequence: a→1, iv→4, C→3, 5→5.

    Used to enforce that sibling labels increase monotonically within a parent —
    a new child whose ordinal is not greater than the previous sibling's means
    the outline restarted (a new list), so the node belongs at a different depth.
    Returns ``None`` when the token has no well-defined ordinal.
    """
    if form == "digit":
        try:
            return int(token)
        except ValueError:
            return None
    if form in ("alpha_lower", "alpha_upper") and len(token) == 1:
        return ord(token.lower()) - ord("a") + 1
    if form in ("roman_lower", "roman_upper"):
        total = 0
        prev = 0
        for ch in reversed(token.lower()):
            value = _ROMAN_VALUES.get(ch)
            if value is None:
                return None
            if value < prev:
                total -= value
            else:
                total += value
                prev = value
        return total or None
    return None


@dataclass
class _Node:
    token: str
    form: str
    offset: int  # '(' index
    depth: int  # 0-based outline depth
    parent: _Node | None
    children: list[_Node] = field(default_factory=list)
    end: int | None = None  # exclusive end of this node's span in body


def _expected_child_form(parent_form: str | None) -> str:
    if parent_form is None:
        return _OUTLINE_LADDER[0]
    try:
        idx = _OUTLINE_LADDER.index(parent_form)
    except ValueError:  # pragma: no cover - defensive
        return "alpha_lower"
    return _OUTLINE_LADDER[min(idx + 1, len(_OUTLINE_LADDER) - 1)]


def _resolve_form(token: str, candidate_forms: frozenset[str], want: str) -> str | None:
    """Pick the outline form for ``token`` given what the current context wants.

    Prefers an exact match to ``want`` (child position); otherwise falls back to
    the least-ambiguous single candidate.
    """
    if want in candidate_forms:
        return want
    # Sibling / ancestor case: prefer a non-roman alpha reading when the token is
    # unambiguous, else the sole candidate.
    non_ambig = candidate_forms - {"roman_lower", "roman_upper"}
    if len(candidate_forms) == 1:
        return next(iter(candidate_forms))
    if len(non_ambig) == 1:
        return next(iter(non_ambig))
    # Still ambiguous (e.g. bare 'i'): default to the outline ladder reading.
    return None


def _sibling_ordinal_ok(parent: _Node, token: str, form: str) -> bool:
    """Whether ``token`` may be the next child of ``parent`` by ordinal order.

    Sibling labels of the same form must increase monotonically (``(1),(2),(3)``;
    ``(a),(b)``). If the parent's last child of this form has an ordinal ``>=``
    the new token's, the outline restarted a list — the new node belongs at a
    different depth, so reject placement here and let the caller pop. Undefined
    ordinals (unexpected tokens) never block placement.
    """
    new_ordinal = _label_ordinal(token, form)
    if new_ordinal is None:
        return True
    last_same_form = next(
        (child for child in reversed(parent.children) if child.form == form),
        None,
    )
    if last_same_form is None:
        return True
    last_ordinal = _label_ordinal(last_same_form.token, last_same_form.form)
    if last_ordinal is None:
        return True
    return new_ordinal > last_ordinal


def _build_tree(body: str, heads: Sequence[_Head]) -> list[_Node]:
    """Assemble a paragraph tree from head occurrences using the outline ladder.

    Returns the list of top-level nodes. Each node's ``end`` is set to the start
    of the next sibling-or-shallower head (or end-of-body).
    """
    roots: list[_Node] = []
    # stack holds the current ancestor chain of open nodes.
    stack: list[_Node] = []

    for head in heads:
        forms = _token_forms(head.token)

        if head.weak:
            # A weak (inline) candidate is accepted only if it is exactly the
            # expected next outline child of the currently open node. It never
            # pops the stack: if it does not fit here it is almost certainly a
            # cross-reference or parenthetical, so discard it.
            if not stack:
                continue
            want = _expected_child_form(stack[-1].form)
            if _resolve_form(head.token, forms, want) != want:
                continue
            node = _Node(
                token=head.token,
                form=want,
                offset=head.offset,
                depth=stack[-1].depth + 1,
                parent=stack[-1],
            )
            stack[-1].children.append(node)
            stack.append(node)
            continue

        placed = False
        # Try to place as a child of the deepest open node whose expected child
        # form this token can take.
        while stack:
            want = _expected_child_form(stack[-1].form)
            form = _resolve_form(head.token, forms, want)
            if form == want and _sibling_ordinal_ok(stack[-1], head.token, form):
                node = _Node(
                    token=head.token,
                    form=form,
                    offset=head.offset,
                    depth=stack[-1].depth + 1,
                    parent=stack[-1],
                )
                stack[-1].children.append(node)
                stack.append(node)
                placed = True
                break
            # Not a child here — either the form does not fit, or the ordinal did
            # not increase (a restarted list). This head is a sibling of, or
            # shallower than, some ancestor. Pop and retry at the right depth.
            stack.pop()
        if placed:
            continue
        # Empty stack: this is a new top-level node.
        want = _expected_child_form(None)
        form = _resolve_form(head.token, forms, want) or (
            next(iter(forms)) if forms else "other"
        )
        node = _Node(
            token=head.token,
            form=form,
            offset=head.offset,
            depth=0,
            parent=None,
        )
        roots.append(node)
        stack.append(node)

    _assign_ends(body, roots)
    return roots


def _iter_nodes(roots: Sequence[_Node]) -> Iterator[_Node]:
    for root in roots:
        yield root
        yield from _iter_nodes(root.children)


def _assign_ends(body: str, roots: Sequence[_Node]) -> None:
    """Set each node's exclusive ``end`` offset.

    A node ends where the next head at the same or a shallower depth begins; the
    deepest last node ends at end-of-body. We compute this from the flat,
    document-ordered head list.
    """
    flat = sorted(_iter_nodes(roots), key=lambda n: n.offset)
    for i, node in enumerate(flat):
        end = len(body)
        for later in flat[i + 1 :]:
            if later.depth <= node.depth:
                end = later.offset
                break
        # Trim trailing whitespace from the span so byte-equality is stable.
        while end > node.offset and body[end - 1] in "\n\r\t ":
            end -= 1
        node.end = end


def _node_citation_path(parent_path: str, chain: Sequence[str]) -> str:
    return "/".join([parent_path, *chain])


# --------------------------------------------------------------------------- #
# Generation                                                                     #
# --------------------------------------------------------------------------- #


class AnchorVerificationError(ValueError):
    """Raised when a generated/loaded anchor fails a mechanical gate."""


def verify_anchor(anchor: ProvisionAnchor, parent_body: str) -> None:
    """Assert the two mechanical gates from the policy. Raises on failure.

    1. **Byte-equal**: ``parent_body[start:end] == anchor.text``.
    2. **Label-at-head**: the printed label appears at the span head.
    """
    if anchor.char_end > len(parent_body):
        raise AnchorVerificationError(
            f"{anchor.citation_path}: span end {anchor.char_end} exceeds parent "
            f"body length {len(parent_body)}"
        )
    slice_text = parent_body[anchor.char_start : anchor.char_end]
    if slice_text != anchor.text:
        raise AnchorVerificationError(
            f"{anchor.citation_path}: text is not byte-equal to parent slice "
            f"[{anchor.char_start}:{anchor.char_end}]"
        )
    head = anchor.text.lstrip()
    expected = f"({anchor.label})"
    if not head.startswith(expected):
        raise AnchorVerificationError(
            f"{anchor.citation_path}: printed label {expected} not at span head "
            f"(head begins {head[:16]!r})"
        )


def generate_anchors_for_provision(
    provision: ProvisionRecord,
    *,
    confidence: str = CONFIDENCE_LABEL_INFERRED,
    include_intermediate: bool = True,
    min_depth: int = 0,
) -> list[ProvisionAnchor]:
    """Parse ``provision.body`` into a paragraph tree and emit anchors.

    Every emitted anchor is verified (byte-equal + label-at-head) before it is
    returned; a parse that would violate a gate raises rather than emitting a
    bad row.

    ``include_intermediate`` also emits ancestor paragraphs (``(d)``, ``(d)(6)``)
    so intermediate citation paths resolve, not only the deepest leaves.
    """
    body = provision.body or ""
    parent_id = provision.id
    if not parent_id:
        raise ValueError(
            f"provision {provision.citation_path!r} has no id; cannot anchor"
        )
    parent_path = provision.citation_path
    parent_hash = body_sha256(body)

    heads = _scan_heads(body)
    roots = _build_tree(body, heads)

    anchors: list[ProvisionAnchor] = []
    ordinal = 0

    def _emit(node: _Node, chain: list[str]) -> None:
        nonlocal ordinal
        path = _node_citation_path(parent_path, chain)
        end = node.end if node.end is not None else len(body)
        text = body[node.offset : end]
        if (include_intermediate or not node.children) and node.depth >= min_depth:
            anchor = ProvisionAnchor(
                citation_path=path,
                parent_provision_id=str(parent_id),
                parent_citation_path=parent_path,
                char_start=node.offset,
                char_end=end,
                text=text,
                label=node.token,
                depth=node.depth,
                confidence=confidence,
                parent_body_sha256=parent_hash,
                jurisdiction=provision.jurisdiction,
                document_class=provision.document_class,
                version=provision.version,
                ordinal=ordinal,
            )
            verify_anchor(anchor, body)
            anchors.append(anchor)
            ordinal += 1
        for child in node.children:
            _emit(child, [*chain, child.token])

    for root in roots:
        _emit(root, [root.token])

    # Hard invariant: the leaf path is the stable PRIMARY KEY, so no two anchors
    # may share a citation path. A collision means the paragraph parse is
    # ambiguous at that node; fail loudly rather than emit rows the DB would
    # reject (or, worse, silently dedupe).
    counts = Counter(a.citation_path for a in anchors)
    collisions = sorted(path for path, count in counts.items() if count > 1)
    if collisions:
        raise AnchorVerificationError(
            f"{parent_path}: duplicate anchor citation paths "
            f"(ambiguous paragraph parse): {collisions[:5]}"
        )
    return anchors


def anchor_for_stored_leaf(
    leaf_provision: ProvisionRecord,
    *,
    label_offset: int | None = None,
) -> ProvisionAnchor:
    """Build a single anchor for a leaf that is *already stored* as a provision.

    Used for block-grained sources (state manuals/regs) where the publisher's
    asserted frontier already has the leaf as its own row, but a consumer cites
    it by its *printed label* path (e.g. ``.../365/180/A``) rather than the
    stored slug. The anchor spans the printed-label paragraph inside the stored
    body so the label-keyed path resolves, and is marked ``machine_asserted``
    (the boundary is the publisher's, not inferred).

    ``label_offset`` overrides where the label starts (defaults to the first
    ``(<last-segment>)`` occurrence in the body, skipping any boilerplate
    prefix).
    """
    body = leaf_provision.body or ""
    parent_id = leaf_provision.id
    if not parent_id:
        raise ValueError(
            f"leaf provision {leaf_provision.citation_path!r} has no id"
        )
    label = leaf_provision.citation_path.rsplit("/", 1)[-1]
    needle = f"({label})"
    if label_offset is None:
        label_offset = body.find(needle)
    if label_offset < 0:
        raise AnchorVerificationError(
            f"{leaf_provision.citation_path}: printed label {needle} not found "
            f"in stored body"
        )
    text = body[label_offset:].rstrip()
    end = label_offset + len(text)
    anchor = ProvisionAnchor(
        citation_path=leaf_provision.citation_path,
        parent_provision_id=str(parent_id),
        parent_citation_path=leaf_provision.citation_path,
        char_start=label_offset,
        char_end=end,
        text=text,
        label=label,
        depth=0,
        confidence=CONFIDENCE_MACHINE_ASSERTED,
        parent_body_sha256=body_sha256(body),
        jurisdiction=leaf_provision.jurisdiction,
        document_class=leaf_provision.document_class,
        version=leaf_provision.version,
        ordinal=0,
    )
    verify_anchor(anchor, body)
    return anchor


def _scan_inline_numbered_run(text: str, base_offset: int) -> list[tuple[int, str]]:
    """Find a run-in numbered list ``(1) … (2) … (3)`` inside ``text``.

    Returns ``[(offset_in_parent, token), …]`` only if the numerals form a
    contiguous ``1, 2, 3, …`` sequence (a genuine enumeration, not a stray
    cross-reference). ``base_offset`` is added so offsets are parent-relative.
    Conservative by design: a broken sequence yields ``[]`` so we never mint
    leaves from ambiguous typography.
    """
    hits = [
        (m.start(), m.group(1))
        for m in re.finditer(r"\((\d{1,3})\)", text)
    ]
    if not hits:
        return []
    run: list[tuple[int, str]] = []
    expected = 1
    for offset, token in hits:
        if int(token) == expected:
            run.append((base_offset + offset, token))
            expected += 1
        else:
            break
    # Require at least two items to call it a list.
    return run if len(run) >= 2 else []


def generate_stored_leaf_anchors(
    leaf_provision: ProvisionRecord,
    *,
    label_offset: int | None = None,
    include_inline_children: bool = True,
) -> list[ProvisionAnchor]:
    """Anchor a stored block leaf plus any run-in numbered children.

    The stored leaf (e.g. ``.../365/180/A``) is emitted ``machine_asserted``
    (publisher boundary). If its body contains a contiguous run-in numbered
    list — ``(A) … eligible: (1) … (2) … (3) …`` — each item is additionally
    emitted as a ``label_inferred`` child (``.../365/180/A/1``), so a consumer
    citing the sub-item resolves. Each child spans from its ``(n)`` label to the
    next item (last runs to end-of-leaf). Every anchor is verified.
    """
    leaf = anchor_for_stored_leaf(leaf_provision, label_offset=label_offset)
    anchors = [leaf]
    if not include_inline_children:
        return anchors
    body = leaf_provision.body or ""
    run = _scan_inline_numbered_run(leaf.text, base_offset=leaf.char_start)
    if not run:
        return anchors
    parent_hash = body_sha256(body)
    for i, (offset, token) in enumerate(run):
        end = run[i + 1][0] if i + 1 < len(run) else leaf.char_end
        # Trim trailing whitespace / separators.
        while end > offset and body[end - 1] in "\n\r\t ;,":
            end -= 1
        child = ProvisionAnchor(
            citation_path=f"{leaf.citation_path}/{token}",
            parent_provision_id=leaf.parent_provision_id,
            parent_citation_path=leaf.parent_citation_path,
            char_start=offset,
            char_end=end,
            text=body[offset:end],
            label=token,
            depth=1,
            confidence=CONFIDENCE_LABEL_INFERRED,
            parent_body_sha256=parent_hash,
            jurisdiction=leaf_provision.jurisdiction,
            document_class=leaf_provision.document_class,
            version=leaf_provision.version,
            ordinal=i + 1,
        )
        verify_anchor(child, body)
        anchors.append(child)
    return anchors


def generate_anchors(
    provisions: Iterable[ProvisionRecord],
    *,
    target_citation_paths: Sequence[str] | None = None,
    confidence: str = CONFIDENCE_LABEL_INFERRED,
) -> list[ProvisionAnchor]:
    """Generate anchors for one or more asserted provisions.

    If ``target_citation_paths`` is given, only those provisions are parsed
    (and each must have a non-empty body). Provisions with empty bodies are
    skipped (nothing to anchor).
    """
    wanted = set(target_citation_paths) if target_citation_paths is not None else None
    out: list[ProvisionAnchor] = []
    for provision in provisions:
        if wanted is not None and provision.citation_path not in wanted:
            continue
        if not (provision.body or "").strip():
            continue
        out.extend(
            generate_anchors_for_provision(provision, confidence=confidence)
        )
    return out


# --------------------------------------------------------------------------- #
# Resolver                                                                        #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AnchorResolution:
    """A resolved citation path → (provision id, leaf path, span)."""

    citation_path: str
    provision_id: str
    parent_citation_path: str
    span: tuple[int, int]
    match: str  # "exact" | "descendant" | "ancestor"
    anchor: ProvisionAnchor

    @property
    def text(self) -> str:
        return self.anchor.text


class AnchorResolver:
    """Resolve a citation path to ``(provision_id, span)`` over an anchor set.

    Fallback semantics (documented in ``docs/provision-anchors.md``):

    * **exact** — a leaf whose path equals the query. Preferred.
    * **descendant** — no exact leaf, but the query is an *ancestor* of stored
      leaves (e.g. query ``.../273/9/d`` when only ``.../d/6/iii`` was drafted).
      Resolves to the minimal span covering all matching descendants.
    * **ancestor** — no exact or descendant match, but a *prefix* of the query
      is a stored leaf (e.g. query ``.../d/6/iii/A`` drilling below the drafted
      frontier). Resolves to the deepest stored ancestor's span.

    A path that matches nothing returns ``None``.
    """

    def __init__(self, anchors: Iterable[ProvisionAnchor]) -> None:
        self._by_path: dict[str, ProvisionAnchor] = {}
        for anchor in anchors:
            # Last write wins is fine: identical paths must have identical spans
            # from a deterministic generator.
            self._by_path[anchor.citation_path] = anchor

    def __len__(self) -> int:
        return len(self._by_path)

    def paths(self) -> frozenset[str]:
        return frozenset(self._by_path)

    def resolve(self, citation_path: str) -> AnchorResolution | None:
        exact = self._by_path.get(citation_path)
        if exact is not None:
            return AnchorResolution(
                citation_path=citation_path,
                provision_id=exact.parent_provision_id,
                parent_citation_path=exact.parent_citation_path,
                span=exact.span,
                match="exact",
                anchor=exact,
            )

        prefix = citation_path + "/"
        descendants = [
            anchor
            for path, anchor in self._by_path.items()
            if path.startswith(prefix)
        ]
        if descendants:
            # Descendants exist, so the query is an ancestor of drafted leaves —
            # it is NOT a below-frontier drill, so the ancestor fallback does not
            # apply (mirrors the SQL RPC's `NOT EXISTS (descendant)` guard). A
            # shared span is only well defined when they all live in one parent
            # provision; otherwise the query is ambiguous and resolves to nothing.
            provision_ids = {a.parent_provision_id for a in descendants}
            if len(provision_ids) == 1:
                start = min(a.char_start for a in descendants)
                end = max(a.char_end for a in descendants)
                covering = min(descendants, key=lambda a: (a.char_start, -a.char_end))
                return AnchorResolution(
                    citation_path=citation_path,
                    provision_id=covering.parent_provision_id,
                    parent_citation_path=covering.parent_citation_path,
                    span=(start, end),
                    match="descendant",
                    anchor=covering,
                )
            return None

        # Ancestor fallback: walk up the query path looking for a stored leaf.
        # Only reached when the query has no descendants (a below-frontier drill).
        segments = citation_path.split("/")
        for cut in range(len(segments) - 1, 0, -1):
            candidate = "/".join(segments[:cut])
            anchor = self._by_path.get(candidate)
            if anchor is not None:
                return AnchorResolution(
                    citation_path=citation_path,
                    provision_id=anchor.parent_provision_id,
                    parent_citation_path=anchor.parent_citation_path,
                    span=anchor.span,
                    match="ancestor",
                    anchor=anchor,
                )
        return None


# --------------------------------------------------------------------------- #
# JSONL I/O                                                                       #
# --------------------------------------------------------------------------- #


def load_anchors(path: str | Path) -> tuple[ProvisionAnchor, ...]:
    """Read an anchors JSONL artifact (mirrors ``load_provisions``)."""
    p = Path(path)
    if not p.exists():
        return ()
    anchors: list[ProvisionAnchor] = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        anchors.append(ProvisionAnchor.from_mapping(json.loads(line)))
    return tuple(anchors)


def write_anchors_jsonl(
    path: str | Path, anchors: Iterable[ProvisionAnchor]
) -> int:
    """Write anchors as JSONL, one row per line, keys sorted for stable diffs."""
    rows = list(anchors)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(
        json.dumps(anchor.to_mapping(), sort_keys=True, ensure_ascii=False)
        for anchor in rows
    )
    output_path.write_text(payload + ("\n" if rows else ""))
    return len(rows)


def verify_anchors_against_provisions(
    anchors: Iterable[ProvisionAnchor],
    provisions: Iterable[ProvisionRecord],
) -> None:
    """Re-run both mechanical gates for every anchor against its parent body.

    Also checks the parent-body hash matches (staleness guard): if a parent's
    body changed since generation, the anchor must be rebuilt, not trusted.
    """
    by_id = {p.id: p for p in provisions if p.id}
    by_path = {p.citation_path: p for p in provisions}
    for anchor in anchors:
        parent = by_id.get(anchor.parent_provision_id) or by_path.get(
            anchor.parent_citation_path
        )
        if parent is None:
            raise AnchorVerificationError(
                f"{anchor.citation_path}: parent provision "
                f"{anchor.parent_citation_path} not found for verification"
            )
        body = parent.body or ""
        verify_anchor(anchor, body)
        if anchor.parent_body_sha256 and anchor.parent_body_sha256 != body_sha256(
            body
        ):
            raise AnchorVerificationError(
                f"{anchor.citation_path}: parent body hash drifted; rebuild "
                f"anchors (stored {anchor.parent_body_sha256[:12]}, now "
                f"{body_sha256(body)[:12]})"
            )


def anchor_to_supabase_row(anchor: ProvisionAnchor) -> dict[str, Any]:
    """Serialize an anchor to a ``corpus.provision_anchors`` REST upsert row.

    The JSONL artifact keeps the clean field name ``text``; the DB column is
    ``anchor_text`` (``text`` is a Postgres type keyword). Rename at the DB
    boundary so the upsert payload matches the DDL exactly. ``metadata`` is jsonb
    and passes through; every other field maps 1:1.
    """
    row = anchor.to_mapping()
    row["anchor_text"] = row.pop("text")
    return row
