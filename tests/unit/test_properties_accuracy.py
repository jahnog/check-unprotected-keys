"""Enforced accuracy thresholds against the labeled corpus (US5, FR-014).

Asserts recall == 100% on MUST-FLAG and the false-positive rate <= target on
MUST-NOT-FLAG. The test compares booleans only; no property value is emitted
(SC-004).
"""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.adapters.properties_inspector import inspect_properties_file
from check_unprotected_keys.domain.models import EffectiveScope

from ..fixtures.properties_corpus.corpus import (
    DEFAULT_PATTERNS,
    MUST_FLAG,
    MUST_NOT_FLAG,
)

_MAX_FALSE_POSITIVE_RATE = 0.02


def _scope(root: Path) -> EffectiveScope:
    resolved = root.resolve()
    return EffectiveScope(
        root_directories=(resolved,),
        filename_patterns=("*.properties",),
        canonical_root_set=frozenset({resolved}),
    )


def _is_flagged(root: Path, key: str, value: str) -> bool:
    props = root / "case.properties"
    props.write_text(f"{key}={value}\n", encoding="utf-8")
    result = inspect_properties_file(
        props, name_patterns=DEFAULT_PATTERNS, scope=_scope(root)
    )
    return bool(result.findings)


def test_recall_is_total_on_must_flag(tmp_path: Path) -> None:
    missed = [
        (key, rationale)
        for key, value, rationale in MUST_FLAG
        if not _is_flagged(tmp_path, key, value)
    ]
    recall = 1 - len(missed) / len(MUST_FLAG)
    assert missed == [], f"false negatives (recall={recall:.2%}): {missed}"


def test_false_positive_rate_within_target_on_must_not_flag(tmp_path: Path) -> None:
    false_positives = [
        (key, rationale)
        for key, value, rationale in MUST_NOT_FLAG
        if _is_flagged(tmp_path, key, value)
    ]
    fp_rate = len(false_positives) / len(MUST_NOT_FLAG)
    assert fp_rate <= _MAX_FALSE_POSITIVE_RATE, (
        f"false positives (rate={fp_rate:.2%} > {_MAX_FALSE_POSITIVE_RATE:.0%}): "
        f"{false_positives}"
    )


def test_curated_core_has_zero_false_positives(tmp_path: Path) -> None:
    false_positives = [
        key for key, value, _ in MUST_NOT_FLAG if _is_flagged(tmp_path, key, value)
    ]
    assert false_positives == []
