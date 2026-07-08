"""CLI contract tests for skip warnings and partial results (spec 010 US1).

Contract: specs/010-code-quality-audit/contracts/cli-output.md
"""

from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

from check_unprotected_keys.cli import main

from ..support.fixture_builders import (
    split_cli_streams,
    write_pem_private_key,
)

_WARNING_PATTERN = re.compile(
    r"^WARNING: skipped (?P<path>.+) \((?P<reason>[A-Za-z-]+), "
    r"during (?P<phase>[a-z-]+)\)$"
)


def _write_config(root: Path, body: str) -> None:
    (root / ".check-unprotected-keys.toml").write_text(
        dedent(body).strip() + "\n", encoding="utf-8"
    )


def test_skip_warning_lines_follow_contract_format(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    scan_base = tmp_path / "workspace"
    hidden_dir = scan_base / "hidden"
    hidden_dir.mkdir(parents=True)

    locked_file = scan_base / "locked.pem"
    write_pem_private_key(locked_file, encrypted=False)

    finding_file = scan_base / "id_rsa"
    write_pem_private_key(finding_file, encrypted=False)

    props = scan_base / "app.properties"
    props.write_text("ssl.key.file=keys/missing.pem\n", encoding="utf-8")

    hidden_dir.chmod(0)
    locked_file.chmod(0)

    _write_config(
        tmp_path,
        f"""
        [scan]
        base_folders = ["{scan_base}"]
        filename_patterns = ["id_*", "*.pem", "*.properties"]
        """,
    )

    try:
        monkeypatch.chdir(tmp_path)
        exit_code = main([])
    finally:
        hidden_dir.chmod(0o755)
        locked_file.chmod(0o600)

    captured = capsys.readouterr()
    stdout_lines, stderr_lines = split_cli_streams(captured.out, captured.err)

    # stdout carries only the finding; warnings never leak there.
    assert stdout_lines == (str(finding_file.resolve()),)
    assert exit_code == 1

    warning_lines = [
        line for line in stderr_lines if line.startswith("WARNING: skipped ")
    ]
    assert len(warning_lines) == 3
    parsed = [_WARNING_PATTERN.match(line) for line in warning_lines]
    assert all(match is not None for match in parsed)

    by_path = {
        match["path"]: (match["reason"], match["phase"])
        for match in parsed
        if match is not None
    }
    assert by_path[str(hidden_dir.resolve())] == (
        "PermissionError",
        "candidate-discovery",
    )
    assert by_path[str(locked_file.resolve())] == ("unreadable", "file-inspection")
    assert by_path[str(scan_base.resolve() / "keys" / "missing.pem")] == (
        "unresolvable-reference",
        "reference-follow",
    )

    # Warnings are sorted by path and precede the Issue categories line.
    assert warning_lines == sorted(
        warning_lines, key=lambda line: line[len("WARNING: skipped ") :]
    )
    categories_index = next(
        index
        for index, line in enumerate(stderr_lines)
        if line.startswith("Issue categories:")
    )
    assert all(stderr_lines.index(line) < categories_index for line in warning_lines)


def test_limit_abort_preserves_partial_results(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    scan_base = tmp_path / "workspace"
    deep = scan_base / "deep"
    for child in ("sub0", "sub1", "sub2"):
        (deep / child).mkdir(parents=True)

    finding_file = scan_base / "id_rsa"
    write_pem_private_key(finding_file, encrypted=False)

    _write_config(
        tmp_path,
        f"""
        [scan]
        base_folders = ["{scan_base}"]
        filename_patterns = ["id_*"]
        max_directory_visits = 2
        """,
    )

    monkeypatch.chdir(tmp_path)
    exit_code = main([])
    captured = capsys.readouterr()
    stdout_lines, stderr_lines = split_cli_streams(captured.out, captured.err)

    # The finding discovered before the limit hit is preserved on stdout.
    assert stdout_lines == (str(finding_file.resolve()),)
    # Limit dominates the exit code even though findings exist.
    assert exit_code == 2
    assert stderr_lines[0].startswith("ERROR: Scan aborted")
    assert stderr_lines[-1] == (
        "NOTE: Partial results above cover the directories visited before the limit."
    )
