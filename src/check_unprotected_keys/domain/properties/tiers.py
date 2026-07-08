"""Token-aware key-name matching and confidence tiers."""

from __future__ import annotations

import re
from enum import StrEnum

from check_unprotected_keys.domain.properties.reference_data import (
    QUALIFIER_DENYLIST,
    WEAK_TOKEN_PATTERNS,
)


class KeyNameTier(StrEnum):
    """Confidence tier of a property key (governs required value evidence)."""

    STRONG = "strong"
    WEAK = "weak"
    NONE = "none"


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_KEY_SEPARATORS = re.compile(r"[.\-_/\s]+")


def tokenize_key(key: str) -> tuple[str, ...]:
    """Split a property key into lowercased tokens.

    Splits on ``.`` ``_`` ``-`` ``/`` and whitespace, then on camelCase
    boundaries, so ``spring.datasource.password`` and ``dbPassword`` both yield a
    ``password`` token while ``compass`` yields only ``compass``.
    """

    tokens: list[str] = []
    for part in _KEY_SEPARATORS.split(key):
        if not part:
            continue
        for sub in _CAMEL_BOUNDARY.split(part):
            if sub:
                tokens.append(sub.lower())
    return tuple(tokens)


def _pattern_is_token_exact(pattern: str) -> bool:
    return len(pattern) <= 5 or pattern in WEAK_TOKEN_PATTERNS


def _pattern_tier(pattern: str) -> KeyNameTier:
    if pattern in WEAK_TOKEN_PATTERNS:
        return KeyNameTier.WEAK
    return KeyNameTier.STRONG


def classify_key_tier(key: str, patterns: tuple[str, ...]) -> KeyNameTier:
    """Classify a property key into a strength tier against the secret catalog.

    A pattern matches either as a whole token (short/ambiguous patterns) or as a
    substring within a token (long, low-collision patterns). A matched secret
    token immediately followed by a non-secret qualifier is demoted to WEAK. The
    strongest tier across all matches wins.
    """

    tokens = tokenize_key(key)
    best = KeyNameTier.NONE
    for raw_pattern in patterns:
        pattern = raw_pattern.lower()
        token_exact = _pattern_is_token_exact(pattern)
        for index, token in enumerate(tokens):
            matched = token == pattern if token_exact else pattern in token
            if not matched:
                continue
            tier = _pattern_tier(pattern)
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            if following is not None and following in QUALIFIER_DENYLIST:
                tier = KeyNameTier.WEAK
            if tier == KeyNameTier.STRONG:
                return KeyNameTier.STRONG
            best = KeyNameTier.WEAK
    return best
