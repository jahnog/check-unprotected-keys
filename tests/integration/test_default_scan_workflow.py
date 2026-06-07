"""Integration tests for the default scan workflow."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from check_unprotected_keys.adapters.reporting import emit_scan_result
from check_unprotected_keys.config.loader import load_search_configuration
from check_unprotected_keys.domain.models import ScanRequest
from check_unprotected_keys.services.scan_service import ScanService

from ..support.fixture_builders import (
    create_expanded_noise_workspace,
    create_expanded_pattern_workspace,
    create_recommendation_workspace,
    create_scan_workspace,
    nonempty_output_lines,
    write_expanded_scan_configuration,
    write_recommendation_scan_configuration,
    write_scan_configuration,
)


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
    assert tuple(issue.file_path for issue in result.malformed_issues) == (
        str(workspace.malformed_key),
    )
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


def test_expanded_default_scope_stays_bounded_on_mixed_noise_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = create_expanded_noise_workspace(tmp_path / "workspace")
    monkeypatch.setenv("HOME", str(workspace.home_root))
    write_expanded_scan_configuration(workspace.root)

    configuration = load_search_configuration(workspace.root)
    result = ScanService().run(
        ScanRequest(
            execution_root=workspace.root,
            configuration=configuration,
        )
    )

    assert result.files_scanned == 8
    assert {finding.file_path for finding in result.findings} == {
        str(workspace.home_ssh_finding),
        str(workspace.repo_key_finding),
        str(workspace.config_secret_finding),
        str(workspace.infra_secret_finding),
        str(workspace.vpn_secret_finding),
    }
    assert result.malformed_count == 1
    assert result.unreadable_count == 0


def test_expanded_default_scope_scan_reports_broader_category_findings(
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
        )
    )

    assert result.files_scanned == 6
    assert {finding.file_path for finding in result.findings} == {
        str(workspace.home_ssh_finding),
        str(workspace.repo_key_finding),
        str(workspace.config_secret_finding),
        str(workspace.infra_secret_finding),
        str(workspace.vpn_secret_finding),
    }
    assert result.malformed_count == 0
    assert result.unreadable_count == 0


def test_recommendation_workflow_emits_guidance_without_changing_stdout(
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
        )
    )

    stdout = StringIO()
    stderr = StringIO()
    emit_scan_result(result, stdout=stdout, stderr=stderr)
    stdout_lines = nonempty_output_lines(stdout.getvalue())
    stderr_text = stderr.getvalue()

    assert result.files_scanned == 5
    assert all(finding.remediation is not None for finding in result.findings)
    assert set(stdout_lines) == {
        str(workspace.interactive_key),
        str(workspace.host_key),
        str(workspace.automation_key),
        str(workspace.embedded_config_key),
        str(workspace.unknown_key),
    }
    assert f"Recommended protection for {workspace.interactive_key}:" in stderr_text
    assert "Usage: interactive-user-key" in stderr_text
    assert "Usage: ssh-host-key" in stderr_text
    assert "Usage: automation-or-deployment-key" in stderr_text
    assert "Usage: embedded-config-secret" in stderr_text
    assert "Usage: unknown" in stderr_text


def test_malformed_only_workflow_keeps_stdout_empty(
    tmp_path: Path,
) -> None:
    workspace = create_scan_workspace(tmp_path / "workspace")
    write_scan_configuration(
        workspace.root,
        folder_patterns=("fixtures/default-scope",),
        filename_patterns=("broken_private.key",),
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

    stdout = StringIO()
    stderr = StringIO()
    emit_scan_result(result, stdout=stdout, stderr=stderr)

    assert result.findings == []
    assert stdout.getvalue() == ""
    assert nonempty_output_lines(stderr.getvalue()) == (
        "Checked 1 file(s). Found 0 violation(s).",
        "Could not fully evaluate 1 malformed file(s).",
        str(workspace.malformed_key),
        "Issue categories: malformed=1",
    )
