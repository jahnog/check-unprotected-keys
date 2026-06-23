"""Unit tests for the pure ``.properties`` parser."""

from __future__ import annotations

from check_unprotected_keys.domain.properties import parse_properties


def test_parses_equals_colon_and_whitespace_separators() -> None:
    entries = parse_properties("a=1\nb:2\nc 3\n")
    assert [(e.key, e.value) for e in entries] == [("a", "1"), ("b", "2"), ("c", "3")]


def test_skips_comments_and_blank_lines() -> None:
    text = "# comment\n! also comment\n\n   \nkey=value\n"
    entries = parse_properties(text)
    assert [(e.key, e.value) for e in entries] == [("key", "value")]


def test_trims_insignificant_whitespace_around_key_and_value() -> None:
    (entry,) = parse_properties("   db.password   =   secret-value   \n")
    assert entry.key == "db.password"
    assert entry.value == "secret-value   "  # trailing handled by callers/heuristics


def test_joins_backslash_line_continuations() -> None:
    (entry,) = parse_properties("key=line1\\\n   line2\\\n   line3\n")
    assert entry.key == "key"
    assert entry.value == "line1line2line3"


def test_applies_value_escapes_including_newline() -> None:
    (entry,) = parse_properties("pem=a\\nb\\tc\\=d\n")
    assert entry.value == "a\nb\tc=d"


def test_escaped_separator_in_key_is_preserved() -> None:
    (entry,) = parse_properties("a\\=b=value\n")
    assert entry.key == "a=b"
    assert entry.value == "value"


def test_key_without_value_yields_empty_value() -> None:
    (entry,) = parse_properties("password\n")
    assert entry.key == "password"
    assert entry.value == ""


def test_records_one_based_start_line_number() -> None:
    entries = parse_properties("# header\n\nfirst=1\nsecond=2\n")
    assert entries[0].line_number == 3
    assert entries[1].line_number == 4


def test_preserves_key_casing() -> None:
    (entry,) = parse_properties("DB.PassWord=x\n")
    assert entry.key == "DB.PassWord"
