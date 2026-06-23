"""Tests for widened externalization/encryption recognition (US4, FR-008)."""

from __future__ import annotations

import pytest

from check_unprotected_keys.domain.properties import PropertyValueKind, classify_value


@pytest.mark.parametrize(
    "value",
    [
        "${DB_PASSWORD}",
        "#{secret}",
        "@token@",
        "{{ db_password }}",
        "$ENV{DB_PASSWORD}",
        "$(secret)",
        "%(password)s",
        "vault:secret/data/app#password",
        "vault://secret/app",
        "awskms:alias/app-key",
        "sops:enc:AES256",
        "secret:projects/app/secret",
        "env:DB_PASSWORD",
    ],
)
def test_externalized_references_classify_as_placeholder(value: str) -> None:
    assert classify_value(value) is PropertyValueKind.PLACEHOLDER


@pytest.mark.parametrize(
    "value",
    ["ENC(abc123==)", "{ENC(abc123==)}", "{cipher}AAABBBCCCDDD"],
)
def test_encryption_wrappers_classify_as_encrypted(value: str) -> None:
    assert classify_value(value) is PropertyValueKind.ENCRYPTED


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hunter2xyz", PropertyValueKind.LITERAL),
        ("RS256", PropertyValueKind.LITERAL),
        ("keys/server.key", PropertyValueKind.PATH_LIKE),
        ("", PropertyValueKind.EMPTY),
    ],
)
def test_non_reference_values_keep_their_kind(
    value: str, expected: PropertyValueKind
) -> None:
    assert classify_value(value) is expected
