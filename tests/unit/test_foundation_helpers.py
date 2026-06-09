"""Unit tests for foundational helper modules used by the scanner."""

from __future__ import annotations

import runpy
import stat
from io import StringIO
from pathlib import Path

import pytest

import check_unprotected_keys.cli as cli_module
from check_unprotected_keys.adapters.filesystem import resolve_effective_scope
from check_unprotected_keys.adapters.reporting import emit_error, emit_scan_result
from check_unprotected_keys.config.loader import (
    ConfigurationError,
    load_search_configuration,
)
from check_unprotected_keys.domain.models import (
    KeyFinding,
    ProtectionClassification,
    ScanResult,
)
from check_unprotected_keys.domain.scope import (
    build_effective_scope,
    narrow_root_directories,
    resolve_start_folder,
)
from tests.support.fixture_builders import (
    HOME_EXPANDED_FOLDER_PATTERN,
    create_expanded_pattern_workspace,
    write_expanded_scan_configuration,
    write_scan_configuration,
)


def test_load_search_configuration_rejects_missing_scan_table(tmp_path: Path) -> None:
    config_path = tmp_path / ".check-unprotected-keys.toml"
    config_path.write_text("[other]\nvalue = 1\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match=r"must define a \[scan\] table"):
        load_search_configuration(tmp_path)


def test_load_search_configuration_rejects_non_string_pattern(tmp_path: Path) -> None:
    config_path = tmp_path / ".check-unprotected-keys.toml"
    config_path.write_text(
        '[scan]\nfolder_patterns = [1]\nfilename_patterns = ["id_*"]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigurationError, match=r"scan.folder_patterns\[1\] must be a string pattern"
    ):
        load_search_configuration(tmp_path)


def test_load_search_configuration_rejects_invalid_toml(tmp_path: Path) -> None:
    config_path = tmp_path / ".check-unprotected-keys.toml"
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


def test_resolve_effective_scope_expands_home_roots_and_deduplicates_them(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = create_expanded_pattern_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_scan_configuration(
        workspace.root,
        folder_patterns=(
            HOME_EXPANDED_FOLDER_PATTERN,
            str(workspace.home_ssh_root),
            "fixtures/expanded-patterns/repo-keys",
        ),
        filename_patterns=("id_*", "*.pem"),
    )
    configuration = load_search_configuration(workspace.root)

    scope = resolve_effective_scope(configuration, start_folder=None)

    assert scope.root_directories == (
        workspace.home_ssh_root,
        workspace.repo_keys_root,
    )
    assert scope.canonical_root_set == frozenset(
        {workspace.home_ssh_root, workspace.repo_keys_root}
    )


def test_write_expanded_scan_configuration_uses_home_and_repo_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = create_expanded_pattern_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_expanded_scan_configuration(workspace.root)
    configuration = load_search_configuration(workspace.root)

    scope = resolve_effective_scope(configuration, start_folder=None)

    assert scope.root_directories == (
        workspace.home_ssh_root,
        workspace.repo_keys_root,
        workspace.config_secrets_root,
        workspace.infra_root,
        workspace.vpn_root,
    )


def test_resolve_effective_scope_keeps_override_filename_patterns_after_narrowing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = create_expanded_pattern_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_expanded_scan_configuration(
        workspace.root,
        folder_patterns=(
            HOME_EXPANDED_FOLDER_PATTERN,
            "fixtures/expanded-patterns/repo-keys",
            "fixtures/expanded-patterns/vpn",
        ),
        filename_patterns=("*.pem", "*.ovpn"),
    )
    configuration = load_search_configuration(workspace.root)

    scope = resolve_effective_scope(configuration, start_folder=workspace.vpn_root)

    assert scope.root_directories == (workspace.vpn_root,)
    assert scope.filename_patterns == ("*.pem", "*.ovpn")


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
        unreadable_count=1,
    )
    result.record_malformed(
        file_path="/tmp/malformed.key",
        matched_folder_pattern="fixtures/default-scope",
        matched_filename_pattern="*.key",
    )

    emit_scan_result(result, stdout=stdout, stderr=stderr)

    assert stdout.getvalue() == "/tmp/finding.pem\n"
    assert "Found 1 violation(s)." in stderr.getvalue()
    expected = "1 files without detected private keys, 1 files that could not be read"
    assert expected in stderr.getvalue()


def test_emit_error_writes_trimmed_message() -> None:
    stderr = StringIO()

    emit_error("\n  invalid configuration  \n", stderr=stderr)

    assert stderr.getvalue() == "invalid configuration\n"


def test_module_entrypoint_delegates_to_cli_main(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "main", lambda: 7)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("check_unprotected_keys", run_name="__main__")

    assert exc_info.value.code == 7
