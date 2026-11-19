"""Name-independent high-confidence credential value signatures."""

from __future__ import annotations

import re
from enum import StrEnum

from check_unprotected_keys.domain.properties.reference_data import (
    BLOB_MIN_ENTROPY,
    BLOB_MIN_LENGTH,
    PATH_SEGMENT_ANY_CLASS_MAX_ENTROPY,
    PATH_SEGMENT_TWO_CLASS_MAX_ENTROPY,
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
_PATH_SEPARATORS = re.compile(r"[/\\]")
_PATH_COMPONENT = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_PATH_COMPONENT_CLASSES = (
    re.compile(r"[a-z]"),
    re.compile(r"[A-Z]"),
    re.compile(r"[0-9]"),
    re.compile(r"[+_=-]"),
)
_IGNORED_PATH_COMPONENTS = frozenset({"", ".", ".."})


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
    if _is_wordlike_filesystem_path(value):
        return False
    classes = sum(
        bool(re.search(pattern, value))
        for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[+/_=-]")
    )
    if classes < 3:
        return False
    return shannon_entropy(value) >= BLOB_MIN_ENTROPY


def _is_wordlike_filesystem_path(value: str) -> bool:
    """Return whether ``value`` is a path of word-like directory components.

    Private to the blob check. A component that contains ``+`` or ``=`` fails
    the identifier pattern, so a base64 token that uses those characters stays
    eligible for the blob signature.
    """

    if "/" not in value and "\\" not in value:
        return False
    components = [
        part
        for part in _PATH_SEPARATORS.split(value)
        if part not in _IGNORED_PATH_COMPONENTS
    ]
    if len(components) < 2:
        return False
    return all(_is_wordlike_path_component(part) for part in components)


def _is_wordlike_path_component(component: str) -> bool:
    if _PATH_COMPONENT.fullmatch(component) is None:
        return False
    entropy = shannon_entropy(component)
    if entropy < PATH_SEGMENT_ANY_CLASS_MAX_ENTROPY:
        return True
    class_count = sum(
        pattern.search(component) is not None for pattern in _PATH_COMPONENT_CLASSES
    )
    return class_count <= 2 and entropy < PATH_SEGMENT_TWO_CLASS_MAX_ENTROPY
