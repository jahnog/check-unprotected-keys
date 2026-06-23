"""Unit tests for token-aware key tiering and value heuristics.

NFR-002 triage (feature 009): the previous version of this file asserted the
008 behavior — substring key matching (``matches_secret_name``) and a single
loose ``is_credential_like`` gate that flagged values like ``localhost``. That
behavior was the defect this feature fixes, so those expectations were the
incorrect ones; they are replaced here with token-aware tiering and the
tier-aware gate. The parsing/classification expectations that remain correct are
retained unchanged.
"""

from __future__ import annotations

import pytest

from check_unprotected_keys.domain.properties import (
    KeyNameTier,
    PropertyValueKind,
    classify_key_tier,
    classify_value,
    is_credential_like,
    tokenize_key,
)

_PATTERNS = (
    "password",
    "passwd",
    "pwd",
    "pass",
    "secret",
    "private",
    "passphrase",
    "key",
    "token",
    "credential",
    "apikey",
)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("dbPassword", ("db", "password")),
        ("spring.datasource.password", ("spring", "datasource", "password")),
        ("APIKey", ("api", "key")),
        ("api_key_header", ("api", "key", "header")),
        ("routing.key", ("routing", "key")),
    ],
)
def test_tokenize_key(key: str, expected: tuple[str, ...]) -> None:
    assert tokenize_key(key) == expected


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "PASSWORD",
        "spring.datasource.password",
        "db.passWord",
        "admin.pwd",
        "service.credential",
        "apikey",
    ],
)
def test_strong_keys(key: str) -> None:
    assert classify_key_tier(key, _PATTERNS) is KeyNameTier.STRONG


@pytest.mark.parametrize(
    "key",
    [
        "routing.key",
        "auth.token",
        "private.network",
        "signing.key.alias",
        "secret.rotation.days",
        "token.expiry.seconds",
        "password.min.length",
        "api.key.header.name",
    ],
)
def test_weak_or_demoted_keys(key: str) -> None:
    assert classify_key_tier(key, _PATTERNS) is KeyNameTier.WEAK


@pytest.mark.parametrize(
    "key",
    [
        "server.port",
        "timeout",
        "host.name",
        "compass.center",
        "tokenizer.mode",
        "monkey.patch.enabled",
        "keyboard.layout",
    ],
)
def test_non_secret_keys_are_none(key: str) -> None:
    assert classify_key_tier(key, _PATTERNS) is KeyNameTier.NONE


def test_empty_pattern_list_matches_nothing() -> None:
    assert classify_key_tier("password", ()) is KeyNameTier.NONE


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", PropertyValueKind.EMPTY),
        ("   ", PropertyValueKind.EMPTY),
        ("${DB_PASSWORD}", PropertyValueKind.PLACEHOLDER),
        ("#{secret}", PropertyValueKind.PLACEHOLDER),
        ("@token@", PropertyValueKind.PLACEHOLDER),
        ("{{ db_password }}", PropertyValueKind.PLACEHOLDER),
        ("vault:secret/data/app#key", PropertyValueKind.PLACEHOLDER),
        ("ENC(abc123==)", PropertyValueKind.ENCRYPTED),
        ("{cipher}AAABBBCCC", PropertyValueKind.ENCRYPTED),
        ("keys/server.key", PropertyValueKind.PATH_LIKE),
        ("/etc/app/id_rsa", PropertyValueKind.PATH_LIKE),
        ("server.pem", PropertyValueKind.PATH_LIKE),
        ("id_rsa", PropertyValueKind.PATH_LIKE),
        ("hunter2xyz", PropertyValueKind.LITERAL),
    ],
)
def test_classify_value(value: str, expected: PropertyValueKind) -> None:
    assert classify_value(value) is expected


@pytest.mark.parametrize(
    "value", ["hunter2", "Summer2024", "xK9$mP2qLz", "S3cr3tValue"]
)
def test_strong_tier_flags_word_like_and_random(value: str) -> None:
    assert is_credential_like(value, KeyNameTier.STRONG) is True


@pytest.mark.parametrize(
    "value",
    ["true", "false", "YES", "8", "8080", "3.14", "abc", "aaaaaa"],
)
def test_gate_rejects_non_credentials_in_every_tier(value: str) -> None:
    assert is_credential_like(value, KeyNameTier.STRONG) is False
    assert is_credential_like(value, KeyNameTier.WEAK) is False


def test_weak_tier_requires_stronger_evidence_than_strong() -> None:
    # Medium-strength value: accepted under STRONG, rejected under WEAK.
    assert is_credential_like("hunter2", KeyNameTier.STRONG) is True
    assert is_credential_like("hunter2", KeyNameTier.WEAK) is False
    # Random-secret-like value clears the WEAK strict gate.
    assert is_credential_like("A1b2C3d4E5f6G7h8", KeyNameTier.WEAK) is True


def test_none_tier_never_credential_like() -> None:
    assert is_credential_like("A1b2C3d4E5f6G7h8", KeyNameTier.NONE) is False
