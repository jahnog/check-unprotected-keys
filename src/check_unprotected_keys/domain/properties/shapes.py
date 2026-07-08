"""Value-kind classification, exclusion shapes, and the credential gate."""

from __future__ import annotations

import math
import re
from collections import Counter
from enum import StrEnum

from check_unprotected_keys.domain.properties.reference_data import (
    ALG_ENUM,
    DOTTED_ID,
    DURATION,
    HEADER_NAME,
    HOSTNAME_DOTTED,
    IPV4,
    KEBAB_SNAKE,
    KEY_FILE_SUFFIXES,
    MIN_ENTROPY_BITS_PER_CHAR,
    MIN_SECRET_LENGTH,
    MIN_WEAK_ENTROPY,
    MIN_WEAK_LENGTH,
    SAMPLE_PATTERNS,
    SAMPLE_VOCAB,
    SEMVER,
)
from check_unprotected_keys.domain.properties.tiers import KeyNameTier


class PropertyValueKind(StrEnum):
    """The shape of a property value, used to decide how to assess it."""

    EMPTY = "empty"
    PLACEHOLDER = "placeholder"
    ENCRYPTED = "encrypted"
    PATH_LIKE = "path_like"
    LITERAL = "literal"


def classify_value(value: str) -> PropertyValueKind:
    """Classify a property value to decide how it should be assessed.

    The EMPTY / PLACEHOLDER / ENCRYPTED branches are recognized so callers can
    short-circuit good-practice values before applying credential heuristics.
    """

    stripped = value.strip()
    if stripped == "":
        return PropertyValueKind.EMPTY
    if _is_placeholder(stripped):
        return PropertyValueKind.PLACEHOLDER
    if _is_encrypted(stripped):
        return PropertyValueKind.ENCRYPTED
    if _is_path_like(stripped):
        return PropertyValueKind.PATH_LIKE
    return PropertyValueKind.LITERAL


def is_sample_placeholder(value: str, extra_ignore: tuple[str, ...] = ()) -> bool:
    """Return whether a value is a documentation default / mask token.

    Conservative by design (research Decision 5): only tokens that are never a
    live secret are listed, so no real credential is suppressed.
    """

    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in SAMPLE_VOCAB:
        return True
    if extra_ignore and lowered in {item.strip().lower() for item in extra_ignore}:
        return True
    return any(pattern.match(stripped) for pattern in SAMPLE_PATTERNS)


def is_non_secret_shape(value: str, tier: KeyNameTier) -> bool:
    """Return whether a literal value has a recognized non-credential shape.

    Always-excluded shapes (every tier) are implausible as a live secret;
    kebab/snake identifiers are excluded only under WEAK keys so glued or
    hyphenated secrets under STRONG keys are never dropped (research Decision 6).
    """

    stripped = value.strip()
    if not stripped:
        return False
    if stripped.lower() in ALG_ENUM:
        return True
    if DOTTED_ID.match(stripped):
        return True
    if _is_bare_host(stripped):
        return True
    if SEMVER.match(stripped):
        return True
    if HEADER_NAME.match(stripped):
        return True
    if DURATION.match(stripped):
        return True
    return tier == KeyNameTier.WEAK and KEBAB_SNAKE.match(stripped) is not None


def _is_bare_host(value: str) -> bool:
    return (
        value.lower() == "localhost"
        or bool(IPV4.match(value))
        or bool(HOSTNAME_DOTTED.match(value))
    )


def placeholder_default(value: str) -> str | None:
    """Return the default segment of a defaulted placeholder, if present.

    Handles ``${VAR:-default}`` and ``${VAR:default}``; returns ``None`` when
    there is no default (or it is empty) so the caller treats it as a plain
    externalized reference.
    """

    match = re.match(r"^\$\{[^:}]+:-?(.*)\}$", value.strip())
    if match is None:
        return None
    default = match.group(1)
    return default if default != "" else None


def is_credential_like(value: str, tier: KeyNameTier) -> bool:
    """Return whether a literal value plausibly holds a credential for ``tier``.

    STRONG keys use the loose base gate (catches word-like human passwords);
    WEAK keys require random-secret-like length and entropy. Pure booleans and
    numbers never qualify.
    """

    if _is_boolean(value) or _is_number(value):
        return False
    length = len(value)
    if tier == KeyNameTier.STRONG:
        return length >= MIN_SECRET_LENGTH and shannon_entropy(value) >= (
            MIN_ENTROPY_BITS_PER_CHAR
        )
    if tier == KeyNameTier.WEAK:
        return length >= MIN_WEAK_LENGTH and shannon_entropy(value) >= MIN_WEAK_ENTROPY
    return False


def _is_placeholder(value: str) -> bool:
    if value.startswith("${") and value.endswith("}"):
        return True
    if value.startswith("#{") and value.endswith("}"):
        return True
    if value.startswith("@") and value.endswith("@") and len(value) > 1:
        return True
    if value.startswith("{{") and value.endswith("}}"):
        return True
    if value.startswith("$ENV{") and value.endswith("}"):
        return True
    if value.startswith("$(") and value.endswith(")"):
        return True
    if re.match(r"^%\(.+\)[sd]$", value):
        return True
    lowered = value.lower()
    return lowered.startswith(
        ("vault:", "awskms:", "aws-kms:", "sops:", "secret:", "secretref:", "env:")
    )


def _is_encrypted(value: str) -> bool:
    if value.startswith("ENC(") and value.endswith(")"):
        return True
    if value.startswith("{ENC(") and value.endswith(")}"):
        return True
    return value.startswith("{cipher}")


def _is_path_like(value: str) -> bool:
    if "/" in value or "\\" in value:
        return True
    lowered = value.lower()
    if any(lowered.endswith(suffix) for suffix in KEY_FILE_SUFFIXES):
        return True
    return lowered.startswith("id_") and " " not in value


def _is_boolean(value: str) -> bool:
    return value.strip().lower() in {"true", "false", "yes", "no", "on", "off"}


def _is_number(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    try:
        float(candidate)
    except ValueError:
        return False
    return True


def shannon_entropy(value: str) -> float:
    counts = Counter(value)
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )
