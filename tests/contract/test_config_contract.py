"""Contract tests for configuration-driven scan semantics."""

from __future__ import annotations

from pathlib import Path

from find_unencrypted_keys.adapters.filesystem import (
    discover_candidate_files,
    resolve_effective_scope,
)
from find_unencrypted_keys.config.loader import load_search_configuration
from find_unencrypted_keys.domain.models import ScanRequest
from find_unencrypted_keys.services.scan_service import ScanService

from ..support.fixture_builders import (
    write_pem_private_key,
    write_putty_private_key,
    write_scan_configuration,
)


def test_config_contract_collapses_overlapping_folder_patterns_during_scope_resolution(
    tmp_path: Path,
) -> None:
    scope_root = tmp_path / "fixtures" / "config-scope"
    scope_root.mkdir(parents=True)
    finding_path = scope_root / "id_rsa"
    write_pem_private_key(finding_path, encrypted=False)

    write_scan_configuration(
        tmp_path,
        folder_patterns=("fixtures/config-scope", str(scope_root.resolve())),
        filename_patterns=("id_*", "id_*"),
    )
    configuration = load_search_configuration(tmp_path)

    effective_scope = resolve_effective_scope(configuration, start_folder=None)
    result = ScanService().run(
        ScanRequest(execution_root=tmp_path, configuration=configuration)
    )

    assert effective_scope.root_directories == (scope_root.resolve(),)
    assert [finding.file_path for finding in result.findings] == [
        str(finding_path.resolve())
    ]


def test_config_contract_deduplicates_candidate_discovery_from_overlapping_roots(
    tmp_path: Path,
) -> None:
    scope_root = tmp_path / "fixtures" / "config-scope"
    scope_root.mkdir(parents=True)
    id_rsa_path = scope_root / "id_rsa"
    pem_path = scope_root / "service_private.pem"
    ppk_path = scope_root / "desktop.ppk"
    write_pem_private_key(id_rsa_path, encrypted=False)
    write_pem_private_key(pem_path, encrypted=False)
    write_putty_private_key(ppk_path, encrypted=False)

    write_scan_configuration(
        tmp_path,
        folder_patterns=("fixtures/config-scope", str(scope_root.resolve())),
        filename_patterns=("id_*", "*_private.pem", "*.ppk"),
    )
    configuration = load_search_configuration(tmp_path)
    scope = resolve_effective_scope(configuration, start_folder=None)
    candidates, issues = discover_candidate_files(scope)

    assert issues == []
    assert {candidate.display_path for candidate in candidates} == {
        str(id_rsa_path.resolve()),
        str(pem_path.resolve()),
        str(ppk_path.resolve()),
    }
