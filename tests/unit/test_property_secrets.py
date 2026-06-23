"""Unit tests for property secret-name matching and value heuristics."""

from __future__ import annotations

import pytest

from check_unprotected_keys.domain.properties import (
    PropertyValueKind,
    classify_value,
    is_credential_like,
    matches_secret_name,
)

_PATTERNS = ("password", "secret", "private", "key", "token")


@pytest.mark.parametrize(
    "key",
    ["password", "PASSWORD", "spring.datasource.password", "db.passWord", "api.secret"],
)
def test_matches_secret_name_is_case_insensitive_substring(key: str) -> None:
    assert matches_secret_name(key, _PATTERNS) is True


@pytest.mark.parametrize("key", ["server.port", "timeout", "host.name"])
def test_non_secret_keys_do_not_match(key: str) -> None:
    assert matches_secret_name(key, _PATTERNS) is False


def test_empty_pattern_list_matches_nothing() -> None:
    assert matches_secret_name("password", ()) is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", PropertyValueKind.EMPTY),
        ("   ", PropertyValueKind.EMPTY),
        ("${DB_PASSWORD}", PropertyValueKind.PLACEHOLDER),
        ("#{secret}", PropertyValueKind.PLACEHOLDER),
        ("@token@", PropertyValueKind.PLACEHOLDER),
        ("ENC(abc123==)", PropertyValueKind.ENCRYPTED),
        ("keys/server.key", PropertyValueKind.PATH_LIKE),
        ("/etc/app/id_rsa", PropertyValueKind.PATH_LIKE),
        ("server.pem", PropertyValueKind.PATH_LIKE),
        ("id_rsa", PropertyValueKind.PATH_LIKE),
        ("hunter2xyz", PropertyValueKind.LITERAL),
    ],
)
def test_classify_value(value: str, expected: PropertyValueKind) -> None:
    assert classify_value(value) is expected


@pytest.mark.parametrize("value", ["hunter2", "changeme", "xK9$mP2qLz", "S3cr3tValue"])
def test_credential_like_values_are_flagged(value: str) -> None:
    assert is_credential_like(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "true",
        "false",
        "YES",
        "8",
        "8080",
        "3.14",
        "abc",  # too short
        "aaaaaa",  # long enough but near-zero entropy
    ],
)
def test_non_credential_values_are_rejected(value: str) -> None:
    assert is_credential_like(value) is False
