"""Unit tests for scan-result reporting."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from find_unencrypted_keys.adapters.reporting import emit_scan_result
from find_unencrypted_keys.domain.models import (
    ProtectionClassification,
    ScanResult,
    UsageCategory,
)
from find_unencrypted_keys.services.scan_service import build_remediation_recommendation
from tests.support.fixture_builders import nonempty_output_lines


def test_emit_scan_result_keeps_guidance_off_stdout() -> None:
    result = ScanResult(files_scanned=1)
    result.add_finding(
        file_path=str(Path("/tmp/workspace/.ssh/id_ed25519")),
        classification=ProtectionClassification.UNPROTECTED,
        usage_category=UsageCategory.INTERACTIVE_USER_KEY,
        remediation=build_remediation_recommendation(
            UsageCategory.INTERACTIVE_USER_KEY
        ),
    )

    stdout = StringIO()
    stderr = StringIO()
    emit_scan_result(result, stdout=stdout, stderr=stderr)

    stdout_lines = nonempty_output_lines(stdout.getvalue())
    stderr_text = stderr.getvalue()

    assert stdout_lines == ("/tmp/workspace/.ssh/id_ed25519",)
    assert "Usage:" not in stdout.getvalue()
    assert "Method:" not in stdout.getvalue()
    assert "Recommended protection for /tmp/workspace/.ssh/id_ed25519:" in stderr_text
    assert "Usage: interactive-user-key" in stderr_text
    assert "Method: Passphrase plus session agent" in stderr_text


def test_emit_scan_result_reports_malformed_only_without_findings() -> None:
    malformed_path = str(
        Path("/tmp/workspace/fixtures/default-scope/broken_private.key")
    )
    result = ScanResult(files_scanned=1)
    result.record_malformed(
        file_path=malformed_path,
        matched_folder_pattern="fixtures/default-scope",
        matched_filename_pattern="*.key",
    )

    stdout = StringIO()
    stderr = StringIO()
    emit_scan_result(result, stdout=stdout, stderr=stderr)

    assert stdout.getvalue() == ""
    assert nonempty_output_lines(stderr.getvalue()) == (
        "Checked 1 file(s). Found 0 violation(s).",
        "Could not fully evaluate 1 malformed file(s).",
        malformed_path,
        "Issue categories: malformed=1",
    )
    assert "Recommended protection for" not in stderr.getvalue()
