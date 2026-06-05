"""Unit tests for foundational helper modules used by the scanner."""

from __future__ import annotations

import stat
from io import StringIO
from pathlib import Path

import pytest

from find_unencrypted_keys.adapters.reporting import emit_error, emit_scan_result
from find_unencrypted_keys.config.loader import (
    ConfigurationError,
    load_search_configuration,
)
from find_unencrypted_keys.domain.models import (
    KeyFinding,
    ProtectionClassification,
    ScanResult,
)
from find_unencrypted_keys.domain.scope import (
    build_effective_scope,
    narrow_root_directories,
    resolve_start_folder,
)


def test_load_search_configuration_rejects_missing_scan_table(tmp_path: Path) -> None:
    config_path = tmp_path / ".find-unencrypted-keys.toml"
    config_path.write_text("[other]\nvalue = 1\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match=r"must define a \[scan\] table"):
        load_search_configuration(tmp_path)


def test_load_search_configuration_rejects_non_string_pattern(tmp_path: Path) -> None:
    config_path = tmp_path / ".find-unencrypted-keys.toml"
    config_path.write_text(
        '[scan]\nfolder_patterns = [1]\nfilename_patterns = ["id_*"]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigurationError, match=r"scan.folder_patterns\[1\] must be a string pattern"
    ):
        load_search_configuration(tmp_path)


def test_load_search_configuration_rejects_invalid_toml(tmp_path: Path) -> None:
    config_path = tmp_path / ".find-unencrypted-keys.toml"
    config_path.write_text("[scan\nfolder_patterns = []\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="not valid TOML"):
        load_search_configuration(tmp_path)


def test_resolve_start_folder_resolves_relative_directory(tmp_path: Path) -> None:
    nested = tmp_path / "team-a"
    nested.mkdir()

    resolved = resolve_start_folder(tmp_path, "team-a")

    assert resolved == nested.resolve()


def test_resolve_start_folder_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        resolve_start_folder(tmp_path, "missing")


def test_resolve_start_folder_rejects_non_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "id_rsa"
    file_path.write_text("not-a-directory\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not a directory"):
        resolve_start_folder(tmp_path, str(file_path))


def test_resolve_start_folder_rejects_unreadable_directory(tmp_path: Path) -> None:
    directory = tmp_path / "restricted"
    directory.mkdir()
    directory.chmod(0)

    try:
        with pytest.raises(ValueError, match="not readable"):
            resolve_start_folder(tmp_path, str(directory))
    finally:
        directory.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def test_narrow_root_directories_filters_to_requested_subtree(tmp_path: Path) -> None:
    included = tmp_path / "team-a"
    excluded = tmp_path / "team-b"
    included.mkdir()
    excluded.mkdir()

    narrowed = narrow_root_directories(
        (included, excluded),
        start_folder=included,
    )

    assert narrowed == (included.resolve(),)


def test_build_effective_scope_canonicalizes_paths(tmp_path: Path) -> None:
    scope = build_effective_scope(
        (tmp_path / ".",),
        ("id_*",),
    )

    assert scope.root_directories == (tmp_path.resolve(),)
    assert scope.canonical_root_set == frozenset({tmp_path.resolve()})


def test_emit_scan_result_writes_summary_and_findings() -> None:
    stdout = StringIO()
    stderr = StringIO()
    result = ScanResult(
        files_scanned=3,
        findings=[
            KeyFinding(
                file_path="/tmp/finding.pem",
                classification=ProtectionClassification.UNPROTECTED,
            )
        ],
        malformed_count=1,
        unreadable_count=1,
    )

    emit_scan_result(result, stdout=stdout, stderr=stderr)

    assert stdout.getvalue() == "/tmp/finding.pem\n"
    assert "Found 1 violation(s)." in stderr.getvalue()
    assert "1 malformed, 1 unreadable" in stderr.getvalue()


def test_emit_error_writes_trimmed_message() -> None:
    stderr = StringIO()

    emit_error("\n  invalid configuration  \n", stderr=stderr)

    assert stderr.getvalue() == "invalid configuration\n"
