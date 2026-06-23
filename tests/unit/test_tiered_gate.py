"""Tests for tier-aware value evidence (US3)."""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.adapters.properties_inspector import inspect_properties_file
from check_unprotected_keys.domain.models import EffectiveScope
from check_unprotected_keys.domain.properties import KeyNameTier, is_credential_like

_PATTERNS = ("password", "secret", "private", "key", "token", "pwd", "pass")


def _scope(root: Path) -> EffectiveScope:
    resolved = root.resolve()
    return EffectiveScope(
        root_directories=(resolved,),
        filename_patterns=("*.properties",),
        canonical_root_set=frozenset({resolved}),
    )


def _flagged_keys(root: Path, body: str) -> set[str]:
    props = root / "app.properties"
    props.write_text(body, encoding="utf-8")
    result = inspect_properties_file(props, name_patterns=_PATTERNS, scope=_scope(root))
    return {f.property_key for f in result.findings}


def test_strong_key_flags_medium_value_weak_key_does_not(tmp_path: Path) -> None:
    flagged = _flagged_keys(
        tmp_path,
        "account.password=Mango7Tree\nrouting.key=Mango7Tree\n",
    )
    assert flagged == {"account.password"}


def test_weak_key_flags_random_secret_value(tmp_path: Path) -> None:
    flagged = _flagged_keys(tmp_path, "routing.key=A1b2C3d4E5f6G7h8\n")
    assert flagged == {"routing.key"}


def test_gate_length_boundary_for_weak_tier() -> None:
    # 11 chars fails the WEAK strict length floor; 12 passes (entropy permitting).
    assert is_credential_like("A1b2C3d4E5f", KeyNameTier.WEAK) is False
    assert is_credential_like("A1b2C3d4E5f6", KeyNameTier.WEAK) is True
    # Both clear the looser STRONG gate.
    assert is_credential_like("A1b2C3d4E5f", KeyNameTier.STRONG) is True
