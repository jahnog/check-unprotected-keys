"""Name-independent high-confidence credential value signatures."""

from __future__ import annotations

import re
from enum import StrEnum

from check_unprotected_keys.domain.properties.reference_data import (
    BLOB_MIN_ENTROPY,
    BLOB_MIN_LENGTH,
)
from check_unprotected_keys.domain.properties.shapes import shannon_entropy


class ValueSignature(StrEnum):
    """A recognized high-confidence credential format (name-independent)."""

    AWS_ACCESS_KEY = "aws-access-key"
    GITHUB_TOKEN = "github-token"
    GITLAB_TOKEN = "gitlab-token"
    SLACK_TOKEN = "slack-token"
    GOOGLE_API_KEY = "google-api-key"
    STRIPE_KEY = "stripe-key"
    TWILIO_KEY = "twilio-key"
    SENDGRID_KEY = "sendgrid-key"
    NPM_TOKEN = "npm-token"
    OPENAI_KEY = "openai-key"
    JWT = "jwt"
    EMBEDDED_CREDENTIAL_URL = "embedded-credential-url"
    HIGH_ENTROPY_BLOB = "high-entropy-blob"


_TOKEN_GUARD = r"(?<![A-Za-z0-9_])"
_SIGNATURE_PATTERNS: tuple[tuple[ValueSignature, re.Pattern[str]], ...] = (
    (
        ValueSignature.AWS_ACCESS_KEY,
        re.compile(
            _TOKEN_GUARD
            + r"(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|A3T[A-Z0-9])[A-Z0-9]{16}"
        ),
    ),
    (
        ValueSignature.GITHUB_TOKEN,
        re.compile(
            _TOKEN_GUARD + r"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[0-9A-Za-z_]{82})"
        ),
    ),
    (
        ValueSignature.GITLAB_TOKEN,
        re.compile(_TOKEN_GUARD + r"glpat-[0-9A-Za-z_-]{20}"),
    ),
    (
        ValueSignature.SLACK_TOKEN,
        re.compile(_TOKEN_GUARD + r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    ),
    (
        ValueSignature.GOOGLE_API_KEY,
        re.compile(_TOKEN_GUARD + r"AIza[0-9A-Za-z_-]{35}"),
    ),
    (
        ValueSignature.STRIPE_KEY,
        re.compile(_TOKEN_GUARD + r"[sr]k_(?:live|test)_[0-9A-Za-z]{16,}"),
    ),
    (ValueSignature.TWILIO_KEY, re.compile(_TOKEN_GUARD + r"SK[0-9a-fA-F]{32}")),
    (
        ValueSignature.SENDGRID_KEY,
        re.compile(_TOKEN_GUARD + r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}"),
    ),
    (ValueSignature.NPM_TOKEN, re.compile(_TOKEN_GUARD + r"npm_[A-Za-z0-9]{36}")),
    (
        ValueSignature.OPENAI_KEY,
        re.compile(_TOKEN_GUARD + r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    ),
    (
        ValueSignature.JWT,
        re.compile(r"eyJ[A-Za-z0-9_-]{6,}\.eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"),
    ),
)
_EMBEDDED_CREDENTIAL_URL = re.compile(
    r"[A-Za-z][A-Za-z0-9+.\-]*://[^/\s:@]+:([^/\s:@]+)@"
)
_BLOB_CHARS = re.compile(r"^[A-Za-z0-9+/_=-]+$")


def match_value_signature(value: str) -> ValueSignature | None:
    """Return the high-confidence credential signature a value matches, if any.

    Detected independently of the key name (FR-003), so secrets hidden under
    benign key names are still reported.
    """

    candidate = value.strip()
    if not candidate:
        return None
    for signature, pattern in _SIGNATURE_PATTERNS:
        if pattern.search(candidate):
            return signature
    url_match = _EMBEDDED_CREDENTIAL_URL.search(candidate)
    if url_match is not None:
        password = url_match.group(1)
        if password and not any(ch in password for ch in "${}"):
            return ValueSignature.EMBEDDED_CREDENTIAL_URL
    if _looks_like_high_entropy_blob(candidate):
        return ValueSignature.HIGH_ENTROPY_BLOB
    return None


def _looks_like_high_entropy_blob(value: str) -> bool:
    if len(value) < BLOB_MIN_LENGTH or not _BLOB_CHARS.match(value):
        return False
    classes = sum(
        bool(re.search(pattern, value))
        for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[+/_=-]")
    )
    if classes < 3:
        return False
    return shannon_entropy(value) >= BLOB_MIN_ENTROPY
