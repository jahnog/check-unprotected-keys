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
    KeyNameTier,
    PropertyEntry,
    PropertyValueKind,
    classify_key_tier,
    classify_value,
    is_credential_like,
    is_message_bundle,
    is_non_secret_shape,
    is_sample_placeholder,
    match_value_signature,
    parse_properties,
    placeholder_default,
)

_REASSESSABLE_DEFAULT_KINDS = frozenset({PropertyValueKind.LITERAL})


class PropertyFindingOrigin(StrEnum):
    """Why a property entry was reported (aids tests and future remediation)."""

    PLAINTEXT_SECRET = "plaintext-secret"
    VALUE_SIGNATURE = "value-signature"
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
    value_ignore: tuple[str, ...] = (),
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
    message_bundle = is_message_bundle(path.name)

    for entry in parse_properties(text):
        finding = _assess_entry(
            entry, path, name_patterns, scope, references, value_ignore, message_bundle
        )
        if finding is not None:
            findings.append(finding)

    return PropertyInspectionResult(
        findings=tuple(findings),
        assessed_references=tuple(references),
        unreadable=False,
    )


def _finding(key: str, origin: PropertyFindingOrigin) -> PropertyFinding:
    return PropertyFinding(
        property_key=key,
        classification=ProtectionClassification.UNPROTECTED,
        origin=origin,
    )


def _assess_entry(
    entry: PropertyEntry,
    properties_path: Path,
    name_patterns: tuple[str, ...],
    scope: EffectiveScope,
    references: list[tuple[Path, ProtectionClassification]],
    value_ignore: tuple[str, ...],
    message_bundle: bool,
) -> PropertyFinding | None:
    value = entry.value

    # 1. Inline key material — unconditional (FR-010), independent of the key
    #    name. Public keys and certificates classify as non-UNPROTECTED here.
    material = key_parsers.inspect_text_for_key_material(value)
    if material is not None:
        if material.classification == ProtectionClassification.UNPROTECTED:
            return _finding(entry.key, PropertyFindingOrigin.INLINE_KEY_MATERIAL)
        return None

    # 2. Value signature — unconditional (FR-003), independent of the key name.
    if match_value_signature(value) is not None:
        return _finding(entry.key, PropertyFindingOrigin.VALUE_SIGNATURE)

    # 3. i18n/message bundles hold text *about* secrets, not secrets (FR-015).
    #    The unconditional layers above still apply; the name-gated gate is skipped.
    if message_bundle:
        return None

    kind = classify_value(value)
    if kind in (PropertyValueKind.EMPTY, PropertyValueKind.ENCRYPTED):
        return None

    tier = classify_key_tier(entry.key, name_patterns)

    # 4. Externalized reference (FR-005/FR-008). A hardcoded placeholder default
    #    is still assessed (FR-009); everything else is never a finding.
    if kind == PropertyValueKind.PLACEHOLDER:
        return _assess_placeholder_default(entry.key, value, tier, value_ignore)

    # 5. Keys with no secret token are only reportable via a value signature,
    #    which was already handled above.
    if tier == KeyNameTier.NONE:
        return None

    # 6. Path to a key file — follow and assess (FR-007). Missing or out-of-scope
    #    references are not findings (the value is a path, not a secret).
    if kind == PropertyValueKind.PATH_LIKE:
        return _follow_reference(entry, properties_path, scope, references)

    # 7. Literal credential under a secret-named key, tier-aware (FR-004/FR-006/FR-007).
    if kind == PropertyValueKind.LITERAL and _is_reportable_literal(
        value, tier, value_ignore
    ):
        return _finding(entry.key, PropertyFindingOrigin.PLAINTEXT_SECRET)
    return None


def _is_reportable_literal(
    value: str, tier: KeyNameTier, value_ignore: tuple[str, ...]
) -> bool:
    if is_sample_placeholder(value, value_ignore):
        return False
    if is_non_secret_shape(value, tier):
        return False
    return is_credential_like(value, tier)


def _assess_placeholder_default(
    key: str,
    value: str,
    tier: KeyNameTier,
    value_ignore: tuple[str, ...],
) -> PropertyFinding | None:
    default = placeholder_default(value)
    if default is None:
        return None
    if match_value_signature(default) is not None:
        return _finding(key, PropertyFindingOrigin.VALUE_SIGNATURE)
    if tier == KeyNameTier.NONE:
        return None
    if classify_value(default) not in _REASSESSABLE_DEFAULT_KINDS:
        return None
    if _is_reportable_literal(default, tier, value_ignore):
        return _finding(key, PropertyFindingOrigin.PLAINTEXT_SECRET)
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
