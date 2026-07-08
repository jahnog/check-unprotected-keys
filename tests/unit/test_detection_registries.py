"""Registry invariants and the SC-003 extension demo (spec 010 US2).

Contract: specs/010-code-quality-audit/contracts/extension-points.md
"""

from __future__ import annotations

from pathlib import Path

import pytest

from check_unprotected_keys.adapters import key_parsers
from check_unprotected_keys.adapters.key_parsers import (
    KEY_RECOGNIZERS,
    KeyRecognizer,
    inspect_candidate_file,
)
from check_unprotected_keys.adapters.properties_inspector import ASSESSMENT_RULES
from check_unprotected_keys.domain.classification import build_assessment
from check_unprotected_keys.domain.models import (
    ProtectionClassification,
    UsageCategory,
)
from check_unprotected_keys.domain.remediation import (
    USAGE_CATEGORY_DEFINITIONS,
    build_remediation_recommendation,
)

# ---------------------------------------------------------------------------
# Key-recognizer registry (FR-004)
# ---------------------------------------------------------------------------

_EXPECTED_RECOGNIZER_ORDER = (
    "putty",
    "openssh-private",
    "pem-private",
    "pem-public",
    "openssh-public",
    "certificate",
)


def test_key_recognizer_order_is_the_documented_precedence() -> None:
    assert tuple(r.name for r in KEY_RECOGNIZERS) == _EXPECTED_RECOGNIZER_ORDER


def test_recognizer_names_are_unique() -> None:
    names = [r.name for r in KEY_RECOGNIZERS]
    assert len(names) == len(set(names))


def test_dummy_recognizer_registers_and_unregisters_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-003 demo: a new format participates via the registry alone — zero
    modified lines in existing detection units — and removal restores baseline.
    """

    marker = b"DUMMY-KEY-FORMAT-V1"
    dummy = KeyRecognizer(
        name="dummy",
        matches=lambda blob: blob.startswith(marker),
        inspect=lambda blob: build_assessment(
            ProtectionClassification.UNPROTECTED,
            format_hint="dummy",
            message="Dummy format key is not protected.",
        ),
    )

    target = tmp_path / "sample.dummykey"
    target.write_bytes(marker + b"\npayload\n")

    # Baseline: unrecognized content is MALFORMED.
    assert (
        inspect_candidate_file(target).classification
        == ProtectionClassification.MALFORMED
    )

    monkeypatch.setattr(key_parsers, "KEY_RECOGNIZERS", (*KEY_RECOGNIZERS, dummy))
    registered = inspect_candidate_file(target)
    assert registered.classification == ProtectionClassification.UNPROTECTED
    assert registered.format_hint == "dummy"

    monkeypatch.setattr(key_parsers, "KEY_RECOGNIZERS", KEY_RECOGNIZERS)
    assert (
        inspect_candidate_file(target).classification
        == ProtectionClassification.MALFORMED
    )


# ---------------------------------------------------------------------------
# Usage-category definitions (FR-005)
# ---------------------------------------------------------------------------


def test_every_usage_category_is_defined_exactly_once() -> None:
    categories = [definition.category for definition in USAGE_CATEGORY_DEFINITIONS]
    assert sorted(categories) == sorted(UsageCategory)
    assert len(categories) == len(set(categories))


def test_unknown_is_the_final_catch_all() -> None:
    assert USAGE_CATEGORY_DEFINITIONS[-1].category is UsageCategory.UNKNOWN


def test_every_definition_carries_complete_remediation() -> None:
    for definition in USAGE_CATEGORY_DEFINITIONS:
        remediation = definition.remediation
        assert remediation.usage_category is definition.category
        assert remediation.title
        assert remediation.summary
        assert remediation.rationale
        assert remediation.next_step_hint


def test_remediation_lookup_matches_registry() -> None:
    for definition in USAGE_CATEGORY_DEFINITIONS:
        assert (
            build_remediation_recommendation(definition.category)
            is definition.remediation
        )


# ---------------------------------------------------------------------------
# Properties assessment rules (FR-006)
# ---------------------------------------------------------------------------

_EXPECTED_RULE_ORDER = (
    "inline-key-material",
    "value-signature",
    "message-bundle-gate",
    "value-kind-gate",
    "placeholder-default",
    "tier-gate",
    "reference-follow",
    "literal-credential",
)


def test_assessment_rule_order_matches_contract() -> None:
    assert tuple(rule.name for rule in ASSESSMENT_RULES) == _EXPECTED_RULE_ORDER


def test_assessment_rule_names_are_unique() -> None:
    names = [rule.name for rule in ASSESSMENT_RULES]
    assert len(names) == len(set(names))
