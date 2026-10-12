"""Release manifests for named corpus scope sets."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.models import DocumentClass

ScopeKey = tuple[str, str, str]
COMPLETE_EXPRESSION_DATES_PROFILE = "complete-expression-dates-v1"
# A base scope is served underneath the primary scopes of its release: for a
# citation path both layers carry, serving picks the primary row. Primary is
# the default and has exactly one encoding, the absent key, so historical
# selectors and signed scope dictionaries keep their byte-for-byte identity.
LAYER_BASE = "base"
LAYER_PRIMARY = "primary"
_RELEASE_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SCOPE_COMPONENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,255}$")
_RESERVED_RELEASE_NAMES = {"current"}


@dataclass(frozen=True)
class ReleaseScope:
    jurisdiction: str
    document_class: str
    version: str
    layer: str = LAYER_PRIMARY

    def __post_init__(self) -> None:
        for field, value in (
            ("jurisdiction", self.jurisdiction),
            ("document_class", self.document_class),
            ("version", self.version),
        ):
            if not isinstance(value, str) or not _SCOPE_COMPONENT_RE.fullmatch(value):
                raise ValueError(f"Release scope contains invalid {field}: {value!r}")
        try:
            DocumentClass(self.document_class)
        except ValueError as exc:
            raise ValueError(
                f"Release scope contains invalid document_class: {self.document_class}"
            ) from exc
        if self.layer not in {LAYER_BASE, LAYER_PRIMARY}:
            raise ValueError(f"Release scope contains invalid layer: {self.layer!r}")

    @property
    def key(self) -> ScopeKey:
        return (self.jurisdiction, self.document_class, self.version)

    @property
    def pair(self) -> tuple[str, str]:
        return (self.jurisdiction, self.document_class)

    @property
    def is_base(self) -> bool:
        return self.layer == LAYER_BASE

    def to_selector_mapping(self) -> dict[str, str]:
        """Return the one canonical selector encoding of this scope."""
        mapping = {
            "jurisdiction": self.jurisdiction,
            "document_class": self.document_class,
            "version": self.version,
        }
        if self.is_base:
            mapping["layer"] = LAYER_BASE
        return mapping


@dataclass(frozen=True)
class ReleaseManifest:
    name: str
    scopes: tuple[ReleaseScope, ...]
    description: str | None = None
    quality_profile: str | None = None

    def __post_init__(self) -> None:
        validate_release_name(self.name)
        if self.quality_profile not in {None, COMPLETE_EXPRESSION_DATES_PROFILE}:
            raise ValueError(
                f"Release selector {self.name!r} has unsupported quality_profile: "
                f"{self.quality_profile!r}"
            )
        _require_unique_scopes(self.scopes, manifest_path=Path(f"<{self.name}>"))
        _require_one_base_per_pair(self.scopes, manifest_path=Path(f"<{self.name}>"))

    @classmethod
    def load(cls, path: str | Path) -> ReleaseManifest:
        manifest_path = Path(path)
        data = _load_json_object(manifest_path)
        if set(data) - {"name", "description", "quality_profile", "scopes"}:
            raise ValueError(f"Release selector {manifest_path} has unsupported fields")
        name_value = data.get("name")
        if not isinstance(name_value, str):
            raise ValueError(f"Release selector {manifest_path} must contain an explicit name")
        name = validate_release_name(name_value)
        description_value = data.get("description")
        description = str(description_value) if description_value is not None else None
        quality_profile_value = data.get("quality_profile")
        quality_profile = (
            str(quality_profile_value) if quality_profile_value is not None else None
        )
        raw_scopes = data.get("scopes")
        if not isinstance(raw_scopes, list) or not raw_scopes:
            raise ValueError(
                f"Release manifest {manifest_path} must contain a non-empty scopes list"
            )
        scopes = tuple(_parse_scope(scope, manifest_path=manifest_path) for scope in raw_scopes)
        _require_unique_scopes(scopes, manifest_path=manifest_path)
        _require_one_base_per_pair(scopes, manifest_path=manifest_path)
        return cls(
            name=name,
            description=description,
            quality_profile=quality_profile,
            scopes=scopes,
        )

    @property
    def scope_keys(self) -> tuple[ScopeKey, ...]:
        return tuple(scope.key for scope in self.scopes)

    @property
    def requires_complete_expression_dates(self) -> bool:
        return self.quality_profile == COMPLETE_EXPRESSION_DATES_PROFILE

    @property
    def has_base_scope(self) -> bool:
        return any(scope.is_base for scope in self.scopes)


def resolve_release_manifest_path(release: str | Path) -> Path:
    """Resolve a release name or explicit path.

    Bare immutable names resolve only under the tracked repository selectors
    directory. ``current`` is reserved:
    production selection is the signed database pointer, never a mutable file.
    """
    release_path = Path(release)
    if release_path.exists() or release_path.suffix == ".json":
        return release_path
    validate_release_name(str(release))
    return Path("manifests") / "releases" / f"{release}.json"


def validate_release_name(name: str) -> str:
    """Validate one immutable release name and reject mutable aliases."""
    if name in _RESERVED_RELEASE_NAMES:
        raise ValueError(f"Release name {name!r} is reserved; use a new immutable named release")
    if len(name) > 128 or not _RELEASE_NAME_RE.fullmatch(name):
        raise ValueError(
            "Release names must be at most 128 characters and contain lowercase "
            "alphanumeric segments separated by single hyphens"
        )
    return name


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except OSError as exc:
        raise FileNotFoundError(f"Release manifest not found: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Release manifest {path} must be a JSON object")
    return data


def _parse_scope(raw_scope: Any, *, manifest_path: Path) -> ReleaseScope:
    if not isinstance(raw_scope, dict):
        raise ValueError(f"Release manifest {manifest_path} contains a non-object scope")
    if set(raw_scope) - {"layer"} != {"jurisdiction", "document_class", "version"}:
        raise ValueError(f"Release manifest {manifest_path} scope has unsupported fields")
    layer = LAYER_PRIMARY
    if "layer" in raw_scope:
        # Only the base layer is spelled out. An explicit "primary" would give a
        # primary scope a second encoding and break byte-for-byte scope reuse.
        if raw_scope["layer"] != LAYER_BASE:
            raise ValueError(
                f"Release manifest {manifest_path} scope layer must be {LAYER_BASE!r} "
                f"or absent (primary): {raw_scope['layer']!r}"
            )
        layer = LAYER_BASE
    jurisdiction = _required_string(raw_scope, "jurisdiction", manifest_path=manifest_path)
    document_class = _required_string(raw_scope, "document_class", manifest_path=manifest_path)
    version = _required_string(raw_scope, "version", manifest_path=manifest_path)
    for field, value in (
        ("jurisdiction", jurisdiction),
        ("document_class", document_class),
        ("version", version),
    ):
        if not _SCOPE_COMPONENT_RE.fullmatch(value):
            raise ValueError(
                f"Release manifest {manifest_path} contains invalid {field}: {value!r}"
            )
    try:
        DocumentClass(document_class)
    except ValueError as exc:
        raise ValueError(
            f"Release manifest {manifest_path} contains invalid document_class: {document_class}"
        ) from exc
    return ReleaseScope(
        jurisdiction=jurisdiction,
        document_class=document_class,
        version=version,
        layer=layer,
    )


def _required_string(data: dict[str, Any], key: str, *, manifest_path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Release manifest {manifest_path} scope missing {key}")
    return value


def _require_unique_scopes(scopes: Iterable[ReleaseScope], *, manifest_path: Path) -> None:
    seen: set[ScopeKey] = set()
    for scope in scopes:
        if scope.key in seen:
            raise ValueError(
                f"Release manifest {manifest_path} contains duplicate scope: "
                f"{scope.jurisdiction}/{scope.document_class}/{scope.version}"
            )
        seen.add(scope.key)


def _require_one_base_per_pair(scopes: Iterable[ReleaseScope], *, manifest_path: Path) -> None:
    seen: set[tuple[str, str]] = set()
    for scope in scopes:
        if not scope.is_base:
            continue
        if scope.pair in seen:
            raise ValueError(
                f"Release manifest {manifest_path} contains more than one base scope for "
                f"{scope.jurisdiction}/{scope.document_class}"
            )
        seen.add(scope.pair)
