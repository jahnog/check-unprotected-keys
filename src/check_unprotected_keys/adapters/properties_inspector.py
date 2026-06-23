"""Inspect Java ``.properties`` files for unprotected secrets.

This adapter reads and decodes a ``.properties`` file, drives the pure parsing
and heuristics in :mod:`check_unprotected_keys.domain.properties`, reuses
:mod:`check_unprotected_keys.adapters.key_parsers` for embedded and referenced
key material, and follows key-file references. It never stores or returns a
property value, so findings are safe to print.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from check_unprotected_keys.adapters import key_parsers
from check_unprotected_keys.domain.models import (
    EffectiveScope,
    ProtectionClassification,
)
from check_unprotected_keys.domain.properties import (
    PropertyEntry,
    PropertyValueKind,
    classify_value,
    is_credential_like,
    matches_secret_name,
    parse_properties,
)

_NON_SECRET_KINDS = frozenset(
    {
        PropertyValueKind.EMPTY,
        PropertyValueKind.PLACEHOLDER,
        PropertyValueKind.ENCRYPTED,
    }
)


class PropertyFindingOrigin(StrEnum):
    """Why a property entry was reported (aids tests and future remediation)."""

    PLAINTEXT_SECRET = "plaintext-secret"
    INLINE_KEY_MATERIAL = "inline-key-material"
    REFERENCED_KEY_FILE = "referenced-key-file"


@dataclass(frozen=True, slots=True)
class PropertyFinding:
    """An offending property, identified by key name only (never its value)."""

    property_key: str
    classification: ProtectionClassification
    origin: PropertyFindingOrigin


@dataclass(frozen=True, slots=True)
class PropertyInspectionResult:
    """Outcome of inspecting one ``.properties`` file."""

    findings: tuple[PropertyFinding, ...]
    assessed_references: tuple[tuple[Path, ProtectionClassification], ...]
    unreadable: bool


def inspect_properties_file(
    path: Path,
    *,
    name_patterns: tuple[str, ...],
    scope: EffectiveScope,
) -> PropertyInspectionResult:
    """Inspect one ``.properties`` file and return its property-level findings."""

    try:
        raw = path.read_bytes()
    except OSError:
        return PropertyInspectionResult(
            findings=(), assessed_references=(), unreadable=True
        )

    text = _decode(raw)
    findings: list[PropertyFinding] = []
    references: list[tuple[Path, ProtectionClassification]] = []

    for entry in parse_properties(text):
        finding = _assess_entry(entry, path, name_patterns, scope, references)
        if finding is not None:
            findings.append(finding)

    return PropertyInspectionResult(
        findings=tuple(findings),
        assessed_references=tuple(references),
        unreadable=False,
    )


def _assess_entry(
    entry: PropertyEntry,
    properties_path: Path,
    name_patterns: tuple[str, ...],
    scope: EffectiveScope,
    references: list[tuple[Path, ProtectionClassification]],
) -> PropertyFinding | None:
    # 1. Inline key material — unconditional (FR-006), independent of the key name.
    material = key_parsers.inspect_text_for_key_material(entry.value)
    if material is not None:
        if material.classification == ProtectionClassification.UNPROTECTED:
            return PropertyFinding(
                property_key=entry.key,
                classification=ProtectionClassification.UNPROTECTED,
                origin=PropertyFindingOrigin.INLINE_KEY_MATERIAL,
            )
        return None

    # 2. Name gate — the remaining heuristics require a secret-named key (FR-003).
    if not matches_secret_name(entry.key, name_patterns):
        return None

    kind = classify_value(entry.value)

    # 3. Externalized / encrypted / empty values are never findings (FR-005).
    if kind in _NON_SECRET_KINDS:
        return None

    # 4. Path to a key file — follow and assess (FR-007). A path that is missing
    #    or out of scope is not a finding (the value is a path, not a secret).
    if kind == PropertyValueKind.PATH_LIKE:
        return _follow_reference(entry, properties_path, scope, references)

    # 5. Plaintext credential under a secret-named key (FR-004).
    if kind == PropertyValueKind.LITERAL and is_credential_like(entry.value):
        return PropertyFinding(
            property_key=entry.key,
            classification=ProtectionClassification.UNPROTECTED,
            origin=PropertyFindingOrigin.PLAINTEXT_SECRET,
        )
    return None


def _follow_reference(
    entry: PropertyEntry,
    properties_path: Path,
    scope: EffectiveScope,
    references: list[tuple[Path, ProtectionClassification]],
) -> PropertyFinding | None:
    candidate = Path(entry.value.strip()).expanduser()
    if not candidate.is_absolute():
        candidate = properties_path.parent / candidate

    try:
        canonical = candidate.resolve(strict=True)
    except OSError:
        return None  # Missing or unresolvable reference — skip gracefully.

    if not _within_scope(canonical, scope):
        return None

    assessment = key_parsers.inspect_candidate_file(canonical)
    references.append((canonical, assessment.classification))

    if assessment.classification == ProtectionClassification.UNPROTECTED:
        return PropertyFinding(
            property_key=entry.key,
            classification=ProtectionClassification.UNPROTECTED,
            origin=PropertyFindingOrigin.REFERENCED_KEY_FILE,
        )
    return None


def _within_scope(canonical: Path, scope: EffectiveScope) -> bool:
    return any(
        canonical == root or canonical.is_relative_to(root)
        for root in scope.canonical_root_set
    )


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")
