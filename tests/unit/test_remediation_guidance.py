"""Unit tests for usage-aware remediation guidance."""

from __future__ import annotations

from pathlib import Path

from find_unencrypted_keys.config.loader import load_search_configuration
from find_unencrypted_keys.domain.models import ScanRequest, UsageCategory
from find_unencrypted_keys.services.scan_service import ScanService
from tests.support.fixture_builders import (
    create_recommendation_workspace,
    write_recommendation_scan_configuration,
)


def test_scan_service_infers_expected_usage_categories(
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

    findings_by_path = {finding.file_path: finding for finding in result.findings}

    assert result.files_scanned == 5
    assert findings_by_path[str(workspace.interactive_key)].usage_category == (
        UsageCategory.INTERACTIVE_USER_KEY
    )
    assert findings_by_path[str(workspace.host_key)].usage_category == (
        UsageCategory.SSH_HOST_KEY
    )
    assert findings_by_path[str(workspace.automation_key)].usage_category == (
        UsageCategory.AUTOMATION_OR_DEPLOYMENT_KEY
    )
    assert findings_by_path[str(workspace.embedded_config_key)].usage_category == (
        UsageCategory.EMBEDDED_CONFIG_SECRET
    )
    assert findings_by_path[str(workspace.unknown_key)].usage_category == (
        UsageCategory.UNKNOWN
    )


def test_scan_service_assigns_low_friction_recommendations(
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

    findings_by_path = {finding.file_path: finding for finding in result.findings}

    interactive_recommendation = findings_by_path[
        str(workspace.interactive_key)
    ].remediation
    host_recommendation = findings_by_path[str(workspace.host_key)].remediation
    automation_recommendation = findings_by_path[
        str(workspace.automation_key)
    ].remediation
    embedded_recommendation = findings_by_path[
        str(workspace.embedded_config_key)
    ].remediation
    unknown_recommendation = findings_by_path[str(workspace.unknown_key)].remediation

    assert interactive_recommendation is not None
    assert interactive_recommendation.title == "Passphrase plus session agent"
    assert "ssh-agent" in interactive_recommendation.summary

    assert host_recommendation is not None
    assert host_recommendation.title == "Reprovision as a managed host key"
    assert "non-interactive" in host_recommendation.summary

    assert automation_recommendation is not None
    assert automation_recommendation.title == "Move to a managed secret or identity"
    assert "vault-managed" in automation_recommendation.summary

    assert embedded_recommendation is not None
    assert embedded_recommendation.title == "Externalize the embedded private key"
    assert (
        "Remove the private key from the config file" in embedded_recommendation.summary
    )

    assert unknown_recommendation is not None
    assert (
        unknown_recommendation.title
        == "Classify usage before choosing a protection path"
    )
    assert (
        "Confirm whether this key is used by a human" in unknown_recommendation.summary
    )
