"""CLI contract tests for --start-folder behavior."""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.cli import main
from tests.support.fixture_builders import (
    create_expanded_pattern_workspace,
    create_recommendation_workspace,
    create_start_folder_workspace,
    split_cli_streams,
    write_expanded_scan_configuration,
    write_recommendation_scan_configuration,
    write_scan_configuration,
)


def test_cli_start_folder_reports_only_findings_under_the_requested_subtree(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_start_folder_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root, folder_patterns=("fixtures/default-scope",)
    )
    monkeypatch.chdir(workspace.root)

    exit_code = main(["--start-folder", "fixtures/default-scope/team-a"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out.splitlines() == [str(workspace.team_a_finding)]


def test_cli_start_folder_accepts_absolute_paths_without_changing_filename_patterns(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_start_folder_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root, folder_patterns=("fixtures/default-scope",)
    )
    monkeypatch.chdir(workspace.root)

    exit_code = main(["--start-folder", str(workspace.team_a_root)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out.splitlines() == [str(workspace.team_a_finding)]


def test_cli_start_folder_returns_exit_code_two_for_invalid_paths(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_start_folder_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root, folder_patterns=("fixtures/default-scope",)
    )
    monkeypatch.chdir(workspace.root)

    exit_code = main(["--start-folder", "fixtures/default-scope/missing"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Start folder does not exist" in captured.err


def test_cli_start_folder_reports_only_expanded_catalog_findings(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_expanded_pattern_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_expanded_scan_configuration(workspace.root)
    monkeypatch.chdir(workspace.root)

    exit_code = main(["--start-folder", "fixtures/expanded-patterns/infra"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out.splitlines() == [str(workspace.infra_secret_finding)]


def test_cli_start_folder_preserves_guidance_for_matching_subtree(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace = create_recommendation_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_recommendation_scan_configuration(workspace.root)
    monkeypatch.chdir(workspace.root)

    exit_code = main(["--start-folder", "fixtures/remediation-guidance/repo-keys"])
    captured = capsys.readouterr()
    stdout_lines, stderr_lines = split_cli_streams(captured.out, captured.err)
    stderr_text = "\n".join(stderr_lines)

    assert exit_code == 1
    assert stdout_lines == (str(workspace.automation_key),)
    assert f"Recommended protection for {workspace.automation_key}:" in stderr_text
    assert "Usage: automation-or-deployment-key" in stderr_text
    assert str(workspace.interactive_key) not in stderr_text
    assert "Usage: interactive-user-key" not in stderr_text
