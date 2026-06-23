"""Unit tests for sample/mask and structured-shape value exclusions (US1)."""

from __future__ import annotations

import pytest

from check_unprotected_keys.domain.properties import (
    KeyNameTier,
    is_non_secret_shape,
    is_sample_placeholder,
)


@pytest.mark.parametrize(
    "value",
    [
        "changeme",
        "CHANGEME",
        "change_me",
        "your_password_here",
        "<password>",
        "[your-key]",
        "REDACTED",
        "none",
        "n/a",
        "xxxxxxxx",
        "********",
        "placeholder",
        "example",
    ],
)
def test_sample_placeholders_are_recognized(value: str) -> None:
    assert is_sample_placeholder(value) is True


@pytest.mark.parametrize(
    "value",
    ["hunter2", "changeit", "admin123", "S3cr3tValue", "Summer2024", "secret"],
)
def test_plausibly_real_values_are_not_sample(value: str) -> None:
    # These can be genuine (weak) credentials, so they must NOT be suppressed.
    assert is_sample_placeholder(value) is False


def test_extra_ignore_tokens_are_honored() -> None:
    assert is_sample_placeholder("internal-default", ("internal-default",)) is True
    assert is_sample_placeholder("internal-default") is False


@pytest.mark.parametrize(
    "value",
    [
        "RS256",
        "PBKDF2WithHmacSHA512",
        "PKCS12",
        "com.example.MyKeyProvider",
        "order.created.event",
        "localhost",
        "db.internal",
        "10.0.0.5",
        "1.2.3",
        "v2.0.1",
        "X-Api-Key",
        "30s",
        "15minutes",
    ],
)
def test_structured_shapes_excluded_in_every_tier(value: str) -> None:
    assert is_non_secret_shape(value, KeyNameTier.STRONG) is True
    assert is_non_secret_shape(value, KeyNameTier.WEAK) is True


def test_kebab_snake_identifier_excluded_only_under_weak_keys() -> None:
    assert is_non_secret_shape("order_created_event", KeyNameTier.WEAK) is True
    assert is_non_secret_shape("order_created_event", KeyNameTier.STRONG) is False


@pytest.mark.parametrize(
    "value",
    ["hunter2", "Summer2024", "A1b2C3d4E5f6", "correct-horse-battery-staple"],
)
def test_real_secret_shapes_not_excluded_under_strong(value: str) -> None:
    assert is_non_secret_shape(value, KeyNameTier.STRONG) is False
