"""Integration tests for narrowed start-folder scans."""

from __future__ import annotations

from pathlib import Path

from find_unencrypted_keys.config.loader import load_search_configuration
from find_unencrypted_keys.domain.models import ScanRequest
from find_unencrypted_keys.services.scan_service import ScanService
from tests.support.fixture_builders import (
    create_start_folder_workspace,
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
