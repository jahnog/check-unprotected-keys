"""Console reporting helpers for scan output."""

from __future__ import annotations

import sys
from textwrap import dedent
from typing import TextIO

from find_unencrypted_keys.domain.models import ScanResult


def emit_scan_result(
    result: ScanResult,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    """Emit finding paths to stdout and non-secret summaries to stderr."""

    stdout_stream = sys.stdout if stdout is None else stdout
    stderr_stream = sys.stderr if stderr is None else stderr

    for finding in result.findings:
        print(finding.file_path, file=stdout_stream)

    print(
        (
            f"Checked {result.files_scanned} file(s). "
            f"Found {len(result.findings)} violation(s)."
        ),
        file=stderr_stream,
    )

    if result.malformed_count or result.unreadable_count:
        summary_parts = []
        if result.malformed_count:
            summary_parts.append(f"{result.malformed_count} malformed")
        if result.unreadable_count:
            summary_parts.append(f"{result.unreadable_count} unreadable")
        print(
            "Could not fully evaluate " + ", ".join(summary_parts) + " file(s).",
            file=stderr_stream,
        )

    if result.safe_issue_breakdown:
        print(
            "Issue categories: " + ", ".join(result.safe_issue_breakdown),
            file=stderr_stream,
        )


def emit_error(message: str, *, stderr: TextIO | None = None) -> None:
    """Emit a user-facing error without leaking secrets."""

    stderr_stream = sys.stderr if stderr is None else stderr
    print(dedent(message).strip(), file=stderr_stream)
