"""CLI contract tests for default scans."""

from __future__ import annotations

from pathlib import Path

from find_unencrypted_keys.cli import main

from ..support.fixture_builders import (
    PASSPHRASE,
    create_scan_workspace,
    write_scan_configuration,
)


def test_default_scan_contract_reports_only_canonical_finding_paths(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_scan_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root, folder_patterns=("fixtures/default-scope",)
    )

    try:
        monkeypatch.chdir(workspace.root)
        exit_code = main([])
    finally:
        workspace.restore_permissions()

    captured = capsys.readouterr()
    lines = tuple(line for line in captured.out.splitlines() if line)
    expected_paths = {
        str(workspace.unprotected_pem),
        str(workspace.unprotected_openssh),
        str(workspace.unprotected_putty),
    }

    assert exit_code == 1
    assert set(lines) == expected_paths
    assert all(Path(line).is_absolute() for line in lines)
    assert all(Path(line) == Path(line).resolve() for line in lines)
    assert PASSPHRASE.decode() not in captured.out
    assert PASSPHRASE.decode() not in captured.err
    assert "Found 3 violation(s)." in captured.err


def test_default_scan_contract_returns_zero_for_clean_scope(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_scan_workspace(tmp_path / "workspace")
    write_scan_configuration(workspace.root, folder_patterns=("fixtures/clean-scope",))

    try:
        monkeypatch.chdir(workspace.root)
        exit_code = main([])
    finally:
        workspace.restore_permissions()

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == ""
    assert "Found 0 violation(s)." in captured.err


def test_default_scan_contract_summarizes_malformed_and_unreadable_files(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_scan_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root, folder_patterns=("fixtures/default-scope",)
    )

    try:
        monkeypatch.chdir(workspace.root)
        main([])
    finally:
        workspace.restore_permissions()

    captured = capsys.readouterr()

    assert "Could not fully evaluate 1 malformed, 1 unreadable file(s)." in captured.err


def test_cli_returns_exit_code_two_when_configuration_is_missing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Configuration file not found" in captured.err


def test_cli_returns_exit_code_two_for_invalid_configuration(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path = tmp_path / ".find-unencrypted-keys.toml"
    config_path.write_text(
        '[scan]\nfolder_patterns = ["   " ]\nfilename_patterns = ["id_*"]\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "scan.folder_patterns[1] must not be blank" in captured.err
