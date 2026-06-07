"""CLI contract tests for default scans."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_unprotected_keys.cli import main

from ..support.fixture_builders import (
    HOME_EXPANDED_FOLDER_PATTERN,
    PASSPHRASE,
    create_expanded_pattern_workspace,
    create_recommendation_workspace,
    create_scan_workspace,
    split_cli_streams,
    write_expanded_scan_configuration,
    write_recommendation_scan_configuration,
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
    assert str(workspace.malformed_key) in captured.err
    assert str(workspace.malformed_key) not in captured.out


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
    config_path = tmp_path / ".check-unprotected-keys.toml"
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


def test_cli_help_lists_supported_options(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Scan configured folders and filename patterns" in captured.out
    assert "--start-folder" in captured.out
    assert "--print-example-config" in captured.out
    assert "--version" in captured.out
    assert captured.err == ""


def test_cli_version_prints_program_name_and_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert captured.out.strip() == "check-unprotected-keys 0.1.0"
    assert captured.err == ""


def test_cli_can_print_packaged_example_configuration(capsys) -> None:
    exit_code = main(["--print-example-config"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[scan]" in captured.out
    assert "folder_patterns = [" in captured.out
    assert "filename_patterns = [" in captured.out
    assert captured.err == ""


def test_default_scan_contract_respects_expanded_catalog_overrides(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_expanded_pattern_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_expanded_scan_configuration(
        workspace.root,
        folder_patterns=(
            HOME_EXPANDED_FOLDER_PATTERN,
            "fixtures/expanded-patterns/repo-keys",
        ),
        filename_patterns=("id_*", "*.pem"),
    )

    monkeypatch.chdir(workspace.root)
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert set(captured.out.splitlines()) == {
        str(workspace.home_ssh_finding),
        str(workspace.repo_key_finding),
    }


def test_default_scan_contract_emits_usage_aware_remediation_guidance(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_recommendation_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_recommendation_scan_configuration(workspace.root)
    monkeypatch.chdir(workspace.root)

    exit_code = main([])
    captured = capsys.readouterr()
    stdout_lines, stderr_lines = split_cli_streams(captured.out, captured.err)
    stderr_text = "\n".join(stderr_lines)

    assert exit_code == 1
    assert set(stdout_lines) == {
        str(workspace.interactive_key),
        str(workspace.host_key),
        str(workspace.automation_key),
        str(workspace.embedded_config_key),
        str(workspace.unknown_key),
    }
    assert "Usage: interactive-user-key" not in captured.out
    assert "ssh-agent" not in captured.out
    assert f"Recommended protection for {workspace.interactive_key}:" in stderr_text
    assert "Usage: interactive-user-key" in stderr_text
    assert "Method: Passphrase plus session agent" in stderr_text
    assert "Usage: ssh-host-key" in stderr_text
    assert "Method: Reprovision as a managed host key" in stderr_text
    assert "Usage: automation-or-deployment-key" in stderr_text
    assert "Method: Move to a managed secret or identity" in stderr_text
    assert "Usage: embedded-config-secret" in stderr_text
    assert "Method: Externalize the embedded private key" in stderr_text
    assert "Usage: unknown" in stderr_text
    assert "Method: Classify usage before choosing a protection path" in stderr_text
