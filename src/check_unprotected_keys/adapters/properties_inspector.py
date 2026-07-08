"""Inspect Java ``.properties`` files for unprotected secrets.

This adapter reads and decodes a ``.properties`` file, drives the pure parsing
and heuristics in :mod:`check_unprotected_keys.domain.properties`, reuses
:mod:`check_unprotected_keys.adapters.key_parsers` for embedded and referenced
key material, and follows key-file references. It never stores or returns a
property value, so findings are safe to print.

Per-entry assessment runs through the ordered ``ASSESSMENT_RULES`` registry
(spec 010 FR-006): adding a detection layer means registering one
``AssessmentRule`` at an explicit position — existing rules are not edited.
The registry order replicates the historical fixed pipeline exactly
(specs/010-code-quality-audit/contracts/extension-points.md).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from check_unprotected_keys.adapters import key_parsers
from check_unprotected_keys.domain.models import (
    EffectiveScope,
    ProtectionClassification,
    SkippedLocation,
    SkipPhase,
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
    """Outcome of inspecting one ``.properties`` file.

    ``skipped`` carries key-file references that could not be resolved and
    followed (FR-001); they are surfaced as scan warnings, never dropped.
    """

    findings: tuple[PropertyFinding, ...]
    assessed_references: tuple[tuple[Path, ProtectionClassification], ...]
    unreadable: bool
    skipped: tuple[SkippedLocation, ...] = ()


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
    skipped: list[SkippedLocation] = []
    message_bundle = is_message_bundle(path.name)

    for entry in parse_properties(text):
        context = AssessmentContext(
            entry=entry,
            properties_path=path,
            name_patterns=name_patterns,
            scope=scope,
            references=references,
            value_ignore=value_ignore,
            message_bundle=message_bundle,
            skipped=skipped,
        )
        finding = _assess_entry(context)
        if finding is not None:
            findings.append(finding)

    return PropertyInspectionResult(
        findings=tuple(findings),
        assessed_references=tuple(references),
        unreadable=False,
        skipped=tuple(skipped),
    )


def _finding(key: str, origin: PropertyFindingOrigin) -> PropertyFinding:
    return PropertyFinding(
        property_key=key,
        classification=ProtectionClassification.UNPROTECTED,
        origin=origin,
    )


@dataclass(slots=True)
class AssessmentContext:
    """Shared state one property entry carries through the assessment rules.

    ``kind`` and ``tier`` are computed lazily so gate rules that never need
    them (inline material, signatures, bundles) stay as cheap as before.
    """

    entry: PropertyEntry
    properties_path: Path
    name_patterns: tuple[str, ...]
    scope: EffectiveScope
    references: list[tuple[Path, ProtectionClassification]]
    value_ignore: tuple[str, ...]
    message_bundle: bool
    skipped: list[SkippedLocation]
    _kind: PropertyValueKind | None = field(default=None, init=False)
    _tier: KeyNameTier | None = field(default=None, init=False)

    @property
    def value(self) -> str:
        return self.entry.value

    @property
    def kind(self) -> PropertyValueKind:
        if self._kind is None:
            self._kind = classify_value(self.entry.value)
        return self._kind

    @property
    def tier(self) -> KeyNameTier:
        if self._tier is None:
            self._tier = classify_key_tier(self.entry.key, self.name_patterns)
        return self._tier


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    """What one assessment rule decided for the current entry.

    ``finding`` reports the entry; ``stop=True`` ends the pipeline without a
    finding. Both unset means "no opinion — try the next rule".
    """

    finding: PropertyFinding | None = None
    stop: bool = False


_CONTINUE = RuleOutcome()
_STOP = RuleOutcome(stop=True)


@dataclass(frozen=True, slots=True)
class AssessmentRule:
    """One registered step of the per-property assessment pipeline."""

    name: str
    assess: Callable[[AssessmentContext], RuleOutcome]


def _rule_inline_key_material(context: AssessmentContext) -> RuleOutcome:
    # Unconditional (FR-010), independent of the key name. Public keys and
    # certificates classify as non-UNPROTECTED here.
    material = key_parsers.inspect_text_for_key_material(context.value)
    if material is None:
        return _CONTINUE
    if material.classification == ProtectionClassification.UNPROTECTED:
        return RuleOutcome(
            finding=_finding(
                context.entry.key, PropertyFindingOrigin.INLINE_KEY_MATERIAL
            )
        )
    return _STOP


def _rule_value_signature(context: AssessmentContext) -> RuleOutcome:
    # Unconditional (FR-003), independent of the key name.
    if match_value_signature(context.value) is not None:
        return RuleOutcome(
            finding=_finding(context.entry.key, PropertyFindingOrigin.VALUE_SIGNATURE)
        )
    return _CONTINUE


def _rule_message_bundle_gate(context: AssessmentContext) -> RuleOutcome:
    # i18n/message bundles hold text *about* secrets, not secrets (FR-015).
    # The unconditional rules above still apply; the name-gated ones are skipped.
    return _STOP if context.message_bundle else _CONTINUE


def _rule_value_kind_gate(context: AssessmentContext) -> RuleOutcome:
    if context.kind in (PropertyValueKind.EMPTY, PropertyValueKind.ENCRYPTED):
        return _STOP
    return _CONTINUE


def _rule_placeholder_default(context: AssessmentContext) -> RuleOutcome:
    # Externalized reference (FR-005/FR-008). A hardcoded placeholder default
    # is still assessed (FR-009); everything else is never a finding.
    if context.kind != PropertyValueKind.PLACEHOLDER:
        return _CONTINUE
    return RuleOutcome(
        finding=_assess_placeholder_default(
            context.entry.key, context.value, context.tier, context.value_ignore
        ),
        stop=True,
    )


def _rule_tier_gate(context: AssessmentContext) -> RuleOutcome:
    # Keys with no secret token are only reportable via a value signature,
    # which was already handled above.
    return _STOP if context.tier == KeyNameTier.NONE else _CONTINUE


def _rule_reference_follow(context: AssessmentContext) -> RuleOutcome:
    # Path to a key file — follow and assess (FR-007). Missing or out-of-scope
    # references are not findings (the value is a path, not a secret).
    if context.kind != PropertyValueKind.PATH_LIKE:
        return _CONTINUE
    return RuleOutcome(
        finding=_follow_reference(
            context.entry,
            context.properties_path,
            context.scope,
            context.references,
            context.skipped,
        ),
        stop=True,
    )


def _rule_literal_credential(context: AssessmentContext) -> RuleOutcome:
    # Literal credential under a secret-named key (FR-004/FR-006/FR-007).
    if context.kind == PropertyValueKind.LITERAL and _is_reportable_literal(
        context.value, context.tier, context.value_ignore
    ):
        return RuleOutcome(
            finding=_finding(context.entry.key, PropertyFindingOrigin.PLAINTEXT_SECRET)
        )
    return _CONTINUE


# Ordered registry: evaluated top to bottom; the first finding or stop wins.
# Insert new detection layers at an explicit position; do not edit existing
# rules (contracts/extension-points.md).
ASSESSMENT_RULES: tuple[AssessmentRule, ...] = (
    AssessmentRule("inline-key-material", _rule_inline_key_material),
    AssessmentRule("value-signature", _rule_value_signature),
    AssessmentRule("message-bundle-gate", _rule_message_bundle_gate),
    AssessmentRule("value-kind-gate", _rule_value_kind_gate),
    AssessmentRule("placeholder-default", _rule_placeholder_default),
    AssessmentRule("tier-gate", _rule_tier_gate),
    AssessmentRule("reference-follow", _rule_reference_follow),
    AssessmentRule("literal-credential", _rule_literal_credential),
)


def _assess_entry(context: AssessmentContext) -> PropertyFinding | None:
    for rule in ASSESSMENT_RULES:
        outcome = rule.assess(context)
        if outcome.finding is not None or outcome.stop:
            return outcome.finding
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
    skipped: list[SkippedLocation],
) -> PropertyFinding | None:
    candidate = Path(entry.value.strip()).expanduser()
    if not candidate.is_absolute():
        candidate = properties_path.parent / candidate

    try:
        canonical = candidate.resolve(strict=True)
    except OSError:
        # Missing or unresolvable reference — not a finding (the value is a
        # path, not a secret), but never a silent drop (FR-001).
        skipped.append(
            SkippedLocation(
                path=candidate,
                reason="unresolvable-reference",
                phase=SkipPhase.REFERENCE_FOLLOW,
            )
        )
        return None

    if not _within_scope(canonical, scope):
        return None

    assessment = key_parsers.inspect_candidate_file(canonical)
    references.append((canonical, assessment.classification))

    if assessment.classification == ProtectionClassification.UNREADABLE:
        # Resolved but uninspectable reference — never a silent drop (FR-001).
        skipped.append(
            SkippedLocation(
                path=canonical,
                reason=(
                    assessment.reason or ProtectionClassification.UNREADABLE.value
                ),
                phase=SkipPhase.REFERENCE_FOLLOW,
            )
        )
        return None

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
    """Decode ``.properties`` bytes: UTF-8 first, then Latin-1.

    The Latin-1 fallback is format-intended, not a guess: the Java
    ``.properties`` format's legacy encoding *is* ISO-8859-1, and Latin-1
    decodes every byte sequence losslessly (no replacement characters), so it
    cannot corrupt content into a false classification (FR-012).
    """

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")
