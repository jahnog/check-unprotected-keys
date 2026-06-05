"""Unit tests for TOML configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from find_unencrypted_keys.config.loader import (
    ConfigurationError,
    load_search_configuration,
)


def test_load_search_configuration_trims_patterns_and_resolves_execution_root(
    tmp_path: Path,
) -> None:
    absolute_scope = (tmp_path / "absolute-scope").resolve()
    absolute_scope.mkdir()
    config_path = tmp_path / ".check-unprotected-keys.toml"
    config_path.write_text(
        f"""
[scan]
folder_patterns = ["  fixtures/default-scope  ", "  {absolute_scope}  "]
filename_patterns = ["  id_*  ", "  *.ppk  "]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    configuration = load_search_configuration(tmp_path)

    assert configuration.execution_root == tmp_path.resolve()
    assert configuration.folder_patterns == (
        "fixtures/default-scope",
        str(absolute_scope),
    )
    assert configuration.filename_patterns == ("id_*", "*.ppk")


def test_load_search_configuration_rejects_missing_filename_patterns(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / ".check-unprotected-keys.toml"
    config_path.write_text(
        '[scan]\nfolder_patterns = ["fixtures/default-scope"]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigurationError, match=r"scan.filename_patterns must be a non-empty array"
    ):
        load_search_configuration(tmp_path)


def test_load_search_configuration_rejects_blank_filename_pattern(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / ".check-unprotected-keys.toml"
    config_path.write_text(
        "[scan]\n"
        'folder_patterns = ["fixtures/default-scope"]\n'
        'filename_patterns = ["   " ]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigurationError, match=r"scan.filename_patterns\[1\] must not be blank"
    ):
        load_search_configuration(tmp_path)


def test_load_search_configuration_allows_duplicate_patterns_for_later_dedup(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / ".check-unprotected-keys.toml"
    config_path.write_text(
        (
            "[scan]\n"
            'folder_patterns = ["fixtures/default-scope", "fixtures/default-scope"]\n'
            'filename_patterns = ["id_*", "id_*"]\n'
        ),
        encoding="utf-8",
    )

    configuration = load_search_configuration(tmp_path)

    assert configuration.folder_patterns == (
        "fixtures/default-scope",
        "fixtures/default-scope",
    )
    assert configuration.filename_patterns == ("id_*", "id_*")
