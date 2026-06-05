"""Integration tests for the default scan workflow."""

from __future__ import annotations

from pathlib import Path

from find_unencrypted_keys.config.loader import load_search_configuration
from find_unencrypted_keys.domain.models import ScanRequest
from find_unencrypted_keys.services.scan_service import ScanService

from ..support.fixture_builders import create_scan_workspace, write_scan_configuration


def test_default_scope_scan_reports_findings_and_non_finding_counts(
    tmp_path: Path,
) -> None:
    workspace = create_scan_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root, folder_patterns=("fixtures/default-scope",)
    )

    try:
        configuration = load_search_configuration(workspace.root)
        request = ScanRequest(
            execution_root=workspace.root,
            configuration=configuration,
        )
        result = ScanService().run(request)
    finally:
        workspace.restore_permissions()

    assert result.files_scanned == 6
    assert {finding.file_path for finding in result.findings} == {
        str(workspace.unprotected_pem),
        str(workspace.unprotected_openssh),
        str(workspace.unprotected_putty),
    }
    assert result.malformed_count == 1
    assert result.unreadable_count == 1


def test_clean_scope_scan_excludes_protected_and_public_only_files(
    tmp_path: Path,
) -> None:
    workspace = create_scan_workspace(tmp_path / "workspace")
    write_scan_configuration(workspace.root, folder_patterns=("fixtures/clean-scope",))

    try:
        configuration = load_search_configuration(workspace.root)
        request = ScanRequest(
            execution_root=workspace.root,
            configuration=configuration,
        )
        result = ScanService().run(request)
    finally:
        workspace.restore_permissions()

    assert result.files_scanned == 3
    assert result.findings == []
    assert result.malformed_count == 0
    assert result.unreadable_count == 0
