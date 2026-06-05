"""Integration tests for narrowed start-folder scans."""

from __future__ import annotations

from pathlib import Path

from find_unencrypted_keys.config.loader import load_search_configuration
from find_unencrypted_keys.domain.models import ScanRequest
from find_unencrypted_keys.services.scan_service import ScanService
from tests.support.fixture_builders import (
    HOME_EXPANDED_FOLDER_PATTERN,
    create_expanded_pattern_workspace,
    create_start_folder_workspace,
    write_expanded_scan_configuration,
    write_scan_configuration,
)


def test_start_folder_scan_reports_only_nested_team_findings(tmp_path: Path) -> None:
    workspace = create_start_folder_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root, folder_patterns=("fixtures/default-scope",)
    )
    configuration = load_search_configuration(workspace.root)

    result = ScanService().run(
        ScanRequest(
            execution_root=workspace.root,
            configuration=configuration,
            start_folder=workspace.team_a_root,
        )
    )

    assert result.findings == [
        type(result.findings[0])(
            file_path=str(workspace.team_a_finding),
            classification=result.findings[0].classification,
        )
    ]
    assert result.files_scanned == 2


def test_start_folder_scan_leaves_filename_patterns_unchanged(tmp_path: Path) -> None:
    workspace = create_start_folder_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root, folder_patterns=("fixtures/default-scope",)
    )
    configuration = load_search_configuration(workspace.root)

    result = ScanService().run(
        ScanRequest(
            execution_root=workspace.root,
            configuration=configuration,
            start_folder=workspace.team_a_root,
        )
    )

    assert result.files_scanned == 2
    assert {finding.file_path for finding in result.findings} == {
        str(workspace.team_a_finding)
    }


def test_start_folder_scan_reports_only_expanded_infra_findings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = create_expanded_pattern_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_expanded_scan_configuration(workspace.root)
    configuration = load_search_configuration(workspace.root)

    result = ScanService().run(
        ScanRequest(
            execution_root=workspace.root,
            configuration=configuration,
            start_folder=workspace.infra_root,
        )
    )

    assert result.files_scanned == 1
    assert {finding.file_path for finding in result.findings} == {
        str(workspace.infra_secret_finding)
    }


def test_start_folder_scan_respects_expanded_catalog_overrides(
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
        ),
        filename_patterns=("id_*", "*.pem"),
    )
    configuration = load_search_configuration(workspace.root)

    result = ScanService().run(
        ScanRequest(
            execution_root=workspace.root,
            configuration=configuration,
            start_folder=workspace.repo_keys_root,
        )
    )

    assert result.files_scanned == 2
    assert {finding.file_path for finding in result.findings} == {
        str(workspace.repo_key_finding)
    }
