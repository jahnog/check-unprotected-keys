"""Unit tests for defaulted-placeholder handling (US2, FR-009)."""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.adapters.properties_inspector import (
    PropertyFindingOrigin,
    inspect_properties_file,
)
from check_unprotected_keys.domain.models import EffectiveScope
from check_unprotected_keys.domain.properties import placeholder_default

_PATTERNS = ("password", "secret", "private", "key", "token", "pwd", "pass")


def _scope(root: Path) -> EffectiveScope:
    resolved = root.resolve()
    return EffectiveScope(
        root_directories=(resolved,),
        filename_patterns=("*.properties",),
        canonical_root_set=frozenset({resolved}),
    )


def test_placeholder_default_extraction() -> None:
    assert placeholder_default("${DB_PW:-hunter2}") == "hunter2"
    assert placeholder_default("${PORT:8080}") == "8080"
    assert placeholder_default("${DB_PASSWORD}") is None
    assert placeholder_default("${DB_PW:-}") is None


def _origins(root: Path, body: str) -> list[PropertyFindingOrigin]:
    props = root / "app.properties"
    props.write_text(body, encoding="utf-8")
    result = inspect_properties_file(props, name_patterns=_PATTERNS, scope=_scope(root))
    return [f.origin for f in result.findings]


def test_hardcoded_default_secret_is_reported(tmp_path: Path) -> None:
    assert _origins(tmp_path, "db.password=${DB_PW:-hunter2xyz}\n") == [
        PropertyFindingOrigin.PLAINTEXT_SECRET
    ]


def test_signature_in_default_is_reported(tmp_path: Path) -> None:
    assert _origins(tmp_path, "aws.secret=${AWS:-AKIAIOSFODNN7EXAMPLE}\n") == [
        PropertyFindingOrigin.VALUE_SIGNATURE
    ]


def test_non_secret_default_is_not_reported(tmp_path: Path) -> None:
    assert _origins(tmp_path, "service.port=${PORT:-8080}\n") == []


def test_plain_placeholder_without_default_is_not_reported(tmp_path: Path) -> None:
    assert _origins(tmp_path, "db.password=${DB_PASSWORD}\n") == []
