"""Unit tests for SkippedLocation reporting (spec 010 US1, FR-001/FR-002)."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from check_unprotected_keys.adapters.reporting import emit_scan_result
from check_unprotected_keys.domain.models import (
    ProtectionClassification,
    ScanResult,
    SkippedLocation,
    SkipPhase,
)

from ..support.fixture_builders import nonempty_output_lines


def _emit(result: ScanResult) -> tuple[tuple[str, ...], tuple[str, ...]]:
    stdout = StringIO()
    stderr = StringIO()
    emit_scan_result(result, stdout=stdout, stderr=stderr)
    return (
        nonempty_output_lines(stdout.getvalue()),
        nonempty_output_lines(stderr.getvalue()),
    )


def test_skipped_location_is_frozen_and_carries_path_reason_phase() -> None:
    skip = SkippedLocation(
        path=Path("/tmp/example"),
        reason="PermissionError",
        phase=SkipPhase.CANDIDATE_DISCOVERY,
    )
    assert skip.path == Path("/tmp/example")
    assert skip.reason == "PermissionError"
    assert skip.phase is SkipPhase.CANDIDATE_DISCOVERY


def test_record_skip_appends_and_deduplicates_by_path() -> None:
    result = ScanResult()
    first = SkippedLocation(
        path=Path("/scan/hidden"),
        reason="PermissionError",
        phase=SkipPhase.CANDIDATE_DISCOVERY,
    )
    duplicate = SkippedLocation(
        path=Path("/scan/hidden"),
        reason="PermissionError",
        phase=SkipPhase.DIRECTORY_PROMOTION,
    )
    result.record_skip(first)
    result.record_skip(duplicate)

    assert result.skipped_locations == [first]


def test_warning_lines_are_sorted_by_path_and_precede_issue_categories() -> None:
    result = ScanResult()
    result.files_scanned = 1
    result.record_malformed(
        file_path="/scan/broken.key",
        matched_folder_pattern="base:/scan",
        matched_filename_pattern="*.key",
    )
    result.record_skip(
        SkippedLocation(
            path=Path("/scan/z-last"),
            reason="PermissionError",
            phase=SkipPhase.CANDIDATE_DISCOVERY,
        )
    )
    result.record_skip(
        SkippedLocation(
            path=Path("/scan/a-first"),
            reason="unreadable",
            phase=SkipPhase.FILE_INSPECTION,
        )
    )

    _stdout, stderr = _emit(result)

    warning_lines = tuple(
        line for line in stderr if line.startswith("WARNING: skipped ")
    )
    assert warning_lines == (
        "WARNING: skipped /scan/a-first (unreadable, during file-inspection)",
        "WARNING: skipped /scan/z-last (PermissionError, during candidate-discovery)",
    )
    # Warnings come after the malformed path list and before Issue categories.
    assert stderr.index(warning_lines[0]) > stderr.index("/scan/broken.key")
    assert stderr.index(warning_lines[-1]) < stderr.index(
        "Issue categories: malformed=1"
    )


def test_clean_result_emits_no_warning_lines() -> None:
    result = ScanResult()
    result.files_scanned = 3

    _stdout, stderr = _emit(result)

    assert not any(line.startswith("WARNING: skipped") for line in stderr)


def test_limit_abort_without_partial_results_keeps_error_only_contract() -> None:
    result = ScanResult()
    result.directory_limit_exceeded = True

    stdout, stderr = _emit(result)

    assert stdout == ()
    assert stderr[0].startswith("ERROR: Scan aborted")
    assert not any(line.startswith("NOTE:") for line in stderr)
    assert result.exit_code == 2


def test_limit_abort_with_partial_results_emits_findings_and_note() -> None:
    result = ScanResult()
    result.directory_limit_exceeded = True
    result.files_scanned = 1
    result.add_finding(
        file_path="/scan/id_rsa",
        classification=ProtectionClassification.UNPROTECTED,
    )

    stdout, stderr = _emit(result)

    assert stdout == ("/scan/id_rsa",)
    assert stderr[0].startswith("ERROR: Scan aborted")
    assert "Checked 1 file(s). Found 1 violation(s)." in stderr
    assert stderr[-1] == (
        "NOTE: Partial results above cover the directories visited before the limit."
    )
    assert result.exit_code == 2
