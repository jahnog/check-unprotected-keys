"""Integration tests for narrowed start-folder scans."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from check_unprotected_keys.adapters.reporting import emit_scan_result
from check_unprotected_keys.config.loader import load_search_configuration
from check_unprotected_keys.domain.models import (
    ProtectionClassification,
    ScanRequest,
    UsageCategory,
)
from check_unprotected_keys.services.scan_service import ScanService
from tests.support.fixture_builders import (
    HOME_EXPANDED_FOLDER_PATTERN,
    create_expanded_pattern_workspace,
    create_recommendation_workspace,
    create_start_folder_workspace,
    nonempty_output_lines,
    write_expanded_scan_configuration,
    write_recommendation_scan_configuration,
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

    assert len(result.findings) == 1
    assert result.findings[0].file_path == str(workspace.team_a_finding)
    assert result.findings[0].classification == ProtectionClassification.UNPROTECTED
    assert result.findings[0].usage_category == UsageCategory.INTERACTIVE_USER_KEY
    assert result.findings[0].remediation is not None
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


def test_start_folder_guidance_stays_scoped_to_matching_subtree(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = create_recommendation_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_recommendation_scan_configuration(workspace.root)
    configuration = load_search_configuration(workspace.root)

    result = ScanService().run(
        ScanRequest(
            execution_root=workspace.root,
            configuration=configuration,
            start_folder=workspace.repo_keys_root,
        )
    )

    stdout = StringIO()
    stderr = StringIO()
    emit_scan_result(result, stdout=stdout, stderr=stderr)
    stderr_text = stderr.getvalue()

    assert result.files_scanned == 1
    assert nonempty_output_lines(stdout.getvalue()) == (str(workspace.automation_key),)
    assert f"Recommended protection for {workspace.automation_key}:" in stderr_text
    assert "Usage: automation-or-deployment-key" in stderr_text
    assert str(workspace.interactive_key) not in stderr_text
    assert "Usage: interactive-user-key" not in stderr_text
