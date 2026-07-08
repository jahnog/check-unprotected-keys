"""Parsing of Java ``.properties`` text into key/value entries (I/O-free)."""

from __future__ import annotations

from dataclasses import dataclass

_WHITESPACE = (" ", "\t", "\f")
_VALUE_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}


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
