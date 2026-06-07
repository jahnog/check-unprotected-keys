"""Unit tests for malformed-path capture and stderr rendering."""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.adapters.reporting import emit_scan_result
from check_unprotected_keys.config.loader import load_search_configuration
from check_unprotected_keys.domain.models import ScanRequest
from check_unprotected_keys.services.scan_service import ScanService

from ..support.fixture_builders import (
    create_remediation_guidance_workspace,
    nonempty_output_lines,
    write_scan_configuration,
)


def test_scan_result_records_canonical_malformed_issue_paths(tmp_path: Path) -> None:
    workspace = create_remediation_guidance_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root,
        folder_patterns=("fixtures/default-scope",),
    )

    try:
        configuration = load_search_configuration(workspace.root)
        result = ScanService().run(
            ScanRequest(
                execution_root=workspace.root,
                configuration=configuration,
            )
        )
    finally:
        workspace.restore_permissions()

    assert result.malformed_count == 1
    assert tuple(issue.file_path for issue in result.malformed_issues) == (
        str(workspace.malformed_key),
    )


def test_emit_scan_result_logs_each_malformed_path_to_stderr(
    tmp_path: Path,
    capsys,
) -> None:
    workspace = create_remediation_guidance_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root,
        folder_patterns=("fixtures/default-scope",),
    )

    try:
        configuration = load_search_configuration(workspace.root)
        result = ScanService().run(
            ScanRequest(
                execution_root=workspace.root,
                configuration=configuration,
            )
        )
        emit_scan_result(result)
    finally:
        workspace.restore_permissions()

    captured = capsys.readouterr()

    assert str(workspace.malformed_key) not in nonempty_output_lines(captured.out)
    assert str(workspace.malformed_key) in nonempty_output_lines(captured.err)
