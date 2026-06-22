"""Integration tests for configurable ignore directories and filename patterns."""

from __future__ import annotations

import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

from check_unprotected_keys.cli import main
from check_unprotected_keys.config.loader import load_search_configuration
from check_unprotected_keys.domain.models import ScanRequest
from check_unprotected_keys.services.scan_service import ScanService
from tests.support.fixture_builders import (
    write_ignore_patterns_configuration,
    write_pem_private_key,
)


def test_replace_semantics_prune_only_configured_directory(tmp_path: Path) -> None:
    noise = tmp_path / "noise"
    real = tmp_path / "real"
    noise.mkdir()
    real.mkdir()
    write_pem_private_key(noise / "id_rsa", encrypted=False)
    write_pem_private_key(real / "id_rsa", encrypted=False)

    write_ignore_patterns_configuration(
        tmp_path,
        ignore_directories=("noise",),
        ignore_filename_patterns=(),
    )
    configuration = load_search_configuration(tmp_path)
    result = ScanService().run(
        ScanRequest(execution_root=tmp_path, configuration=configuration)
    )

    finding_paths = {finding.file_path for finding in result.findings}
    assert str(real / "id_rsa") in finding_paths
    assert str(noise / "id_rsa") not in finding_paths


def test_packaged_file_ignore_skips_pub_sidecar(tmp_path: Path) -> None:
    keys = tmp_path / "keys"
    keys.mkdir()
    write_pem_private_key(keys / "id_rsa", encrypted=False)
    (keys / "id_rsa.pub").write_text("ssh-rsa AAAA\n", encoding="utf-8")

    write_ignore_patterns_configuration(tmp_path)
    configuration = load_search_configuration(tmp_path)
    result = ScanService().run(
        ScanRequest(execution_root=tmp_path, configuration=configuration)
    )

    assert len(result.findings) == 1
    assert result.files_scanned == 1


def test_empty_file_ignores_restore_overlap_scanning(tmp_path: Path) -> None:
    keys = tmp_path / "keys"
    keys.mkdir()
    (keys / "id_rsa.pub").write_text("ssh-rsa AAAA\n", encoding="utf-8")

    write_ignore_patterns_configuration(
        tmp_path,
        ignore_filename_patterns=(),
    )
    configuration = load_search_configuration(tmp_path)
    result = ScanService().run(
        ScanRequest(execution_root=tmp_path, configuration=configuration)
    )

    assert result.files_scanned == 1
    assert result.findings == []


def test_empty_directory_ignores_traverse_noise_tree(tmp_path: Path) -> None:
    noise = tmp_path / "node_modules" / "pkg"
    noise.mkdir(parents=True)
    write_pem_private_key(noise / "id_rsa", encrypted=False)

    write_ignore_patterns_configuration(
        tmp_path,
        ignore_directories=(),
        ignore_filename_patterns=(),
    )
    configuration = load_search_configuration(tmp_path)
    result = ScanService().run(
        ScanRequest(execution_root=tmp_path, configuration=configuration)
    )

    assert any("node_modules" in finding.file_path for finding in result.findings)


def test_partial_legacy_warning_printed_to_stderr(tmp_path: Path, monkeypatch) -> None:
    write_ignore_patterns_configuration(
        tmp_path,
        ignore_directories=("my-custom-only",),
    )
    stderr = StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.chdir(tmp_path)

    exit_code = main([])

    assert exit_code == 0
    assert "partial extension list" in stderr.getvalue()


def test_cli_module_runs_with_ignore_configuration(tmp_path: Path) -> None:
    write_ignore_patterns_configuration(tmp_path)
    child_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COVERAGE", "COV_CORE"))
    }
    completed = subprocess.run(
        [sys.executable, "-m", "check_unprotected_keys"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=child_env,
    )

    assert completed.returncode in {0, 1}
