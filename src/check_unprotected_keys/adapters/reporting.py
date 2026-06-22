"""Console reporting helpers for scan output."""

from __future__ import annotations

import sys
from textwrap import dedent
from typing import TextIO

from check_unprotected_keys.domain.models import KeyFinding, ScanResult


def emit_scan_result(
    result: ScanResult,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    """Emit finding paths to stdout and non-secret summaries to stderr."""

    stdout_stream = sys.stdout if stdout is None else stdout
    stderr_stream = sys.stderr if stderr is None else stderr

    if result.directory_limit_exceeded:
        print(
            "ERROR: Scan aborted — directory visit limit reached. "
            "Results are incomplete.\n"
            "Raise scan.max_directory_visits in your configuration "
            "to scan larger trees, or narrow the scope with --start-folder.",
            file=stderr_stream,
        )
        return

    for finding in result.findings:
        print(finding.file_path, file=stdout_stream)

    print(
        (
            f"Checked {result.files_scanned} file(s). "
            f"Found {len(result.findings)} violation(s)."
        ),
        file=stderr_stream,
    )

    _emit_issue_summary(result, stderr_stream)
    _emit_malformed_paths(result, stderr_stream)
    _emit_remediation_guidance(result, stderr_stream)

    if result.safe_issue_breakdown:
        print(
            "Issue categories: " + ", ".join(result.safe_issue_breakdown),
            file=stderr_stream,
        )


def _emit_issue_summary(result: ScanResult, stderr_stream: TextIO) -> None:
    if not (result.malformed_count or result.unreadable_count):
        return

    summary_parts = []
    if result.malformed_count:
        summary_parts.append(
            f"{result.malformed_count} files without detected private keys"
        )
    if result.unreadable_count:
        summary_parts.append(f"{result.unreadable_count} files that could not be read")
    print(
        "Could not fully evaluate " + ", ".join(summary_parts) + ".",
        file=stderr_stream,
    )


def _emit_malformed_paths(result: ScanResult, stderr_stream: TextIO) -> None:
    for issue in result.malformed_issues:
        print(issue.file_path, file=stderr_stream)


def _emit_remediation_guidance(result: ScanResult, stderr_stream: TextIO) -> None:
    for finding in result.findings:
        if finding.remediation is None:
            continue
        for line in _render_recommendation_lines(finding):
            print(line, file=stderr_stream)


def _render_recommendation_lines(finding: KeyFinding) -> tuple[str, ...]:
    remediation = finding.remediation
    if remediation is None:
        return ()

    return (
        f"Recommended protection for {finding.file_path}:",
        f"Usage: {remediation.usage_category.value}",
        f"Method: {remediation.title}",
        f"Summary: {remediation.summary}",
        f"Why: {remediation.rationale}",
        f"Next: {remediation.next_step_hint}",
    )


def emit_error(message: str, *, stderr: TextIO | None = None) -> None:
    """Emit a user-facing error without leaking secrets."""

    stderr_stream = sys.stderr if stderr is None else stderr
    print(dedent(message).strip(), file=stderr_stream)
