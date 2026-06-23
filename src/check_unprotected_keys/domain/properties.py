"""Pure parsing and secret heuristics for Java ``.properties`` content.

This module is I/O-free: it turns decoded text into property entries and
classifies values. Byte reading, key-file reference following, and reuse of the
key-material parser live in the adapter layer.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

_WHITESPACE = (" ", "\t", "\f")
_VALUE_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}

# Credential-likeness gate (research.md Decision 4): a literal value is treated
# as a plaintext secret only when it is long enough AND high-entropy enough.
MIN_SECRET_LENGTH = 6
MIN_ENTROPY_BITS_PER_CHAR = 2.5

# Value suffixes that signal a path to key material (used for PATH_LIKE).
_KEY_FILE_SUFFIXES = (".pem", ".key", ".ppk", ".p8", ".pk8", ".ovpn", ".tfvars")


class PropertyValueKind(StrEnum):
    """The shape of a property value, used to decide how to assess it."""

    EMPTY = "empty"
    PLACEHOLDER = "placeholder"
    ENCRYPTED = "encrypted"
    PATH_LIKE = "path_like"
    LITERAL = "literal"


@dataclass(frozen=True, slots=True)
class PropertyEntry:
    """A single parsed ``key = value`` pair.

    line_number is the 1-based physical line where the entry starts. The value
    is the logical value (continuations joined, escapes applied); it is never
    emitted to any output stream.
    """

    key: str
    value: str
    line_number: int


def matches_secret_name(key: str, patterns: tuple[str, ...]) -> bool:
    """Return whether a property key signals secret-bearing content.

    Matching is case-insensitive substring over the full key, so dotted keys
    such as ``spring.datasource.password`` match a ``password`` pattern.
    """

    lowered = key.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


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


def is_credential_like(value: str) -> bool:
    """Return whether a literal value plausibly holds a credential.

    Requires both a minimum length and minimum Shannon entropy, and rejects pure
    booleans and numbers, so obvious non-secrets under secret-named keys (for
    example ``password.min.length=8`` or ``auth.secret.enabled=true``) are not
    reported.
    """

    if _is_boolean(value) or _is_number(value):
        return False
    if len(value) < MIN_SECRET_LENGTH:
        return False
    return _shannon_entropy(value) >= MIN_ENTROPY_BITS_PER_CHAR


def _is_placeholder(value: str) -> bool:
    return (
        (value.startswith("${") and value.endswith("}"))
        or (value.startswith("#{") and value.endswith("}"))
        or (value.startswith("@") and value.endswith("@") and len(value) > 1)
    )


def _is_encrypted(value: str) -> bool:
    return value.startswith("ENC(") and value.endswith(")")


def _is_path_like(value: str) -> bool:
    if "/" in value or "\\" in value:
        return True
    lowered = value.lower()
    if any(lowered.endswith(suffix) for suffix in _KEY_FILE_SUFFIXES):
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


def _shannon_entropy(value: str) -> float:
    counts = Counter(value)
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


def parse_properties(text: str) -> tuple[PropertyEntry, ...]:
    """Parse ``.properties`` text into entries (common Java subset).

    Handles ``#``/``!`` comments, blank lines, ``=``/``:``/whitespace
    separators, backslash line continuations, and the escapes ``\\=`` ``\\:``
    ``\\t`` ``\\n`` ``\\r`` ``\\f`` ``\\\\``. Full ``\\uXXXX`` unescaping is out
    of scope.
    """

    entries: list[PropertyEntry] = []
    physical = text.splitlines()
    total = len(physical)
    index = 0
    while index < total:
        start_line = index + 1
        stripped = physical[index].lstrip()
        if stripped == "" or stripped[0] in ("#", "!"):
            index += 1
            continue

        logical = stripped
        while _ends_with_odd_backslashes(logical) and index + 1 < total:
            logical = logical[:-1] + physical[index + 1].lstrip()
            index += 1
        index += 1

        key, value = _split_key_value(logical)
        entries.append(PropertyEntry(key=key, value=value, line_number=start_line))
    return tuple(entries)


def _ends_with_odd_backslashes(line: str) -> bool:
    count = 0
    position = len(line) - 1
    while position >= 0 and line[position] == "\\":
        count += 1
        position -= 1
    return count % 2 == 1


def _split_key_value(line: str) -> tuple[str, str]:
    key_chars: list[str] = []
    index = 0
    separator_index: int | None = None
    while index < len(line):
        char = line[index]
        if char == "\\" and index + 1 < len(line):
            nxt = line[index + 1]
            key_chars.append(_VALUE_ESCAPES.get(nxt, nxt))
            index += 2
            continue
        if char in _WHITESPACE or char in ("=", ":"):
            separator_index = index
            break
        key_chars.append(char)
        index += 1

    key = "".join(key_chars)
    if separator_index is None:
        return key, ""

    cursor = separator_index
    while cursor < len(line) and line[cursor] in _WHITESPACE:
        cursor += 1
    if cursor < len(line) and line[cursor] in ("=", ":"):
        cursor += 1
        while cursor < len(line) and line[cursor] in _WHITESPACE:
            cursor += 1

    return key, _unescape(line[cursor:])


def _unescape(value: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            out.append(_VALUE_ESCAPES.get(nxt, nxt))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)
