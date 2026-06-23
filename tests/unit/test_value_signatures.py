"""Unit tests for the unconditional value-signature catalog (US2)."""

from __future__ import annotations

import pytest

from check_unprotected_keys.domain.properties import (
    ValueSignature,
    match_value_signature,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("AKIAIOSFODNN7EXAMPLE", ValueSignature.AWS_ACCESS_KEY),
        ("ghp_" + "a" * 36, ValueSignature.GITHUB_TOKEN),
        ("github_pat_" + "A" * 82, ValueSignature.GITHUB_TOKEN),
        ("glpat-" + "x" * 20, ValueSignature.GITLAB_TOKEN),
        ("xoxb-1234567890-AbCdEfGhIjKl", ValueSignature.SLACK_TOKEN),
        ("AIza" + "A" * 35, ValueSignature.GOOGLE_API_KEY),
        ("sk_live_" + "A" * 24, ValueSignature.STRIPE_KEY),
        ("SK" + "0" * 32, ValueSignature.TWILIO_KEY),
        ("SG." + "A" * 22 + "." + "B" * 43, ValueSignature.SENDGRID_KEY),
        ("npm_" + "a" * 36, ValueSignature.NPM_TOKEN),
        ("sk-proj-" + "A" * 24, ValueSignature.OPENAI_KEY),
        (
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.S3cr3tSignature123",
            ValueSignature.JWT,
        ),
        (
            "jdbc:mysql://root:S3cr3tPass@db.internal:3306/app",
            ValueSignature.EMBEDDED_CREDENTIAL_URL,
        ),
        (
            "mongodb://admin:Hunter2Pass@cluster0.example.net",
            ValueSignature.EMBEDDED_CREDENTIAL_URL,
        ),
        (
            "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0uv",
            ValueSignature.HIGH_ENTROPY_BLOB,
        ),
    ],
)
def test_signatures_match(value: str, expected: ValueSignature) -> None:
    assert match_value_signature(value) is expected


@pytest.mark.parametrize(
    "value",
    [
        "https://auth.example.com/token",  # bare URL, no embedded credential
        "jdbc:postgresql://db.internal:5432/app",  # no user:pass
        "jdbc://${user}:${password}@db",  # placeholder credentials, not literal
        "order.created.event",
        "com.example.MyKeyProvider",
        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",  # hex hash
        "ghp_short",
        "hello world",
        "",
    ],
)
def test_non_signatures_return_none(value: str) -> None:
    assert match_value_signature(value) is None
