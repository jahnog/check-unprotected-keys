"""Fault-injection integration tests for skipped-location reporting (SC-001)."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from check_unprotected_keys.adapters.reporting import emit_scan_result
from check_unprotected_keys.config.loader import load_search_configuration
from check_unprotected_keys.domain.models import ScanRequest, SkipPhase
from check_unprotected_keys.services.scan_service import ScanService

from ..support.fixture_builders import (
    nonempty_output_lines,
    write_pem_private_key,
    write_scan_configuration,
)


def test_every_unreadable_location_produces_exactly_one_warning(
    tmp_path: Path,
) -> None:
    scan_base = tmp_path / "workspace"
    hidden_dir = scan_base / "hidden"
    hidden_dir.mkdir(parents=True)
    (hidden_dir / "id_secret").write_text("sealed\n", encoding="utf-8")

    locked_file = scan_base / "locked.pem"
    write_pem_private_key(locked_file, encrypted=False)

    finding_file = scan_base / "id_rsa"
    write_pem_private_key(finding_file, encrypted=False)

    hidden_dir.chmod(0)
    locked_file.chmod(0)

    write_scan_configuration(
        tmp_path,
        base_folders=(str(scan_base),),
        filename_patterns=("id_*", "*.pem"),
    )

    try:
        configuration = load_search_configuration(tmp_path)
        result = ScanService().run(
            ScanRequest(execution_root=tmp_path, configuration=configuration)
        )
    finally:
        hidden_dir.chmod(0o755)
        locked_file.chmod(0o600)

    # Exactly N=2 unreadable locations -> exactly 2 skipped locations.
    skipped_paths = {skip.path for skip in result.skipped_locations}
    assert skipped_paths == {hidden_dir.resolve(), locked_file.resolve()}

    by_path = {skip.path: skip for skip in result.skipped_locations}
    assert by_path[hidden_dir.resolve()].phase is SkipPhase.CANDIDATE_DISCOVERY
    assert by_path[hidden_dir.resolve()].reason == "PermissionError"
    assert by_path[locked_file.resolve()].phase is SkipPhase.FILE_INSPECTION

    # The scan still completes and reports the readable finding.
    assert {finding.file_path for finding in result.findings} == {
        str(finding_file.resolve())
    }

    stdout = StringIO()
    stderr = StringIO()
    emit_scan_result(result, stdout=stdout, stderr=stderr)
    warning_lines = tuple(
        line
        for line in nonempty_output_lines(stderr.getvalue())
        if line.startswith("WARNING: skipped ")
    )
    assert len(warning_lines) == 2
    assert any(str(hidden_dir.resolve()) in line for line in warning_lines)
    assert any(str(locked_file.resolve()) in line for line in warning_lines)


def test_fully_readable_tree_emits_zero_warnings(tmp_path: Path) -> None:
    scan_base = tmp_path / "workspace"
    scan_base.mkdir()
    write_pem_private_key(scan_base / "id_rsa", encrypted=False)

    write_scan_configuration(
        tmp_path,
        base_folders=(str(scan_base),),
        filename_patterns=("id_*",),
    )

    configuration = load_search_configuration(tmp_path)
    result = ScanService().run(
        ScanRequest(execution_root=tmp_path, configuration=configuration)
    )

    assert result.skipped_locations == []

    stderr = StringIO()
    emit_scan_result(result, stdout=StringIO(), stderr=stderr)
    assert not any(
        line.startswith("WARNING: skipped")
        for line in nonempty_output_lines(stderr.getvalue())
    )
