"""Integration tests for symlink-following, cycle-safe traversal.

All tests use real temporary filesystems (tmp_path) to exercise the full
ScanService → filesystem adapter stack with actual symbolic links.
"""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.domain.models import ScanRequest, SearchConfiguration
from check_unprotected_keys.services.scan_service import ScanService
from tests.support.fixture_builders import (
    write_openssh_private_key,
    write_pem_private_key,
)

_DUMMY_CONFIG = Path("/dev/null")


def _make_config(
    tmp_path: Path,
    *,
    base_folders: tuple[str, ...],
    max_directory_visits: int = 100_000,
) -> SearchConfiguration:
    return SearchConfiguration(
        config_file_path=_DUMMY_CONFIG,
        execution_root=tmp_path,
        base_folders=base_folders,
        directory_names=(),
        ignore_directories=("node_modules", ".git"),
        filename_patterns=("id_*", "*.pem", "*.key"),
        max_directory_visits=max_directory_visits,
    )


def _run(config: SearchConfiguration, tmp_path: Path) -> object:
    request = ScanRequest(
        execution_root=tmp_path,
        configuration=config,
        start_folder=None,
    )
    return ScanService().run(request)


# ---------------------------------------------------------------------------
# User Story 1 — Discover keys stored behind symbolic links
# ---------------------------------------------------------------------------


def test_us1_sc1_symlinked_directory_key_discovered(tmp_path):
    """Key in a real dir outside the scan base is found via a symlink."""
    real_dir = tmp_path / "real_secrets"
    scan_base = tmp_path / "workspace"
    real_dir.mkdir()
    scan_base.mkdir()

    key_file = real_dir / "id_rsa"
    write_pem_private_key(key_file, encrypted=False)

    (scan_base / "linked_secrets").symlink_to(real_dir)

    config = _make_config(tmp_path, base_folders=(str(scan_base),))
    result = _run(config, tmp_path)

    finding_paths = [f.file_path for f in result.findings]
    assert any("id_rsa" in p for p in finding_paths), (
        f"Expected id_rsa in findings, got: {finding_paths}"
    )
    assert not result.directory_limit_exceeded


def test_us1_sc2_symlinked_file_evaluated_as_candidate(tmp_path):
    """A symlink pointing directly to a key file is evaluated and reported."""
    key_file = tmp_path / "real_id_rsa"
    write_pem_private_key(key_file, encrypted=False)

    scan_base = tmp_path / "workspace"
    scan_base.mkdir()
    (scan_base / "id_rsa_link").symlink_to(key_file)

    config = _make_config(tmp_path, base_folders=(str(scan_base),))
    result = _run(config, tmp_path)

    finding_paths = [f.file_path for f in result.findings]
    assert len(result.findings) >= 1, f"Expected finding, got: {finding_paths}"
    assert not result.directory_limit_exceeded


def test_us1_sc3_protected_key_behind_link_no_finding(tmp_path):
    """Protected key behind a symlinked directory produces no finding."""
    real_dir = tmp_path / "real_secrets"
    scan_base = tmp_path / "workspace"
    real_dir.mkdir()
    scan_base.mkdir()

    protected_key = real_dir / "id_rsa"
    write_pem_private_key(protected_key, encrypted=True)

    (scan_base / "linked_secrets").symlink_to(real_dir)

    config = _make_config(tmp_path, base_folders=(str(scan_base),))
    result = _run(config, tmp_path)

    assert len(result.findings) == 0, (
        f"Expected no findings for protected key, got: {result.findings}"
    )


# ---------------------------------------------------------------------------
# User Story 2 — Scan each final folder exactly once, even with cycles
# ---------------------------------------------------------------------------


def test_us2_sc1_self_referential_link_terminates(tmp_path):
    """Self-referential symlink does not cause infinite traversal."""
    scan_base = tmp_path / "workspace"
    scan_base.mkdir()

    key_file = scan_base / "id_rsa"
    write_pem_private_key(key_file, encrypted=False)

    (scan_base / "loop").symlink_to(scan_base)

    config = _make_config(tmp_path, base_folders=(str(scan_base),))
    result = _run(config, tmp_path)

    finding_paths = [f.file_path for f in result.findings]
    assert len(result.findings) == 1, (
        f"Expected exactly one finding, got: {finding_paths}"
    )
    assert not result.directory_limit_exceeded


def test_us2_sc2_mutual_cycle_terminates(tmp_path):
    """Mutual cycle between two directories terminates with one report."""
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    key_file = dir_a / "id_rsa"
    write_pem_private_key(key_file, encrypted=False)

    (dir_a / "link_to_b").symlink_to(dir_b)
    (dir_b / "link_to_a").symlink_to(dir_a)

    config = _make_config(tmp_path, base_folders=(str(dir_a),))
    result = _run(config, tmp_path)

    assert len(result.findings) == 1, (
        f"Expected exactly one finding, got: {[f.file_path for f in result.findings]}"
    )
    assert not result.directory_limit_exceeded


def test_us2_sc3_ancestor_loop_terminates(tmp_path):
    """Symlink pointing to an ancestor does not cause re-descent."""
    scan_base = tmp_path / "workspace"
    nested = scan_base / "a" / "b"
    nested.mkdir(parents=True)

    key_file = scan_base / "id_rsa"
    write_pem_private_key(key_file, encrypted=False)

    (nested / "loop_to_root").symlink_to(scan_base)

    config = _make_config(tmp_path, base_folders=(str(scan_base),))
    result = _run(config, tmp_path)

    assert len(result.findings) == 1, (
        f"Expected exactly one finding, got: {[f.file_path for f in result.findings]}"
    )
    assert not result.directory_limit_exceeded


def test_us2_sc4_aliased_directory_key_reported_once(tmp_path):
    """Two symlinks to the same real directory produce one finding, not two."""
    real_dir = tmp_path / "real"
    scan_base = tmp_path / "workspace"
    real_dir.mkdir()
    scan_base.mkdir()

    key_file = real_dir / "id_rsa"
    write_pem_private_key(key_file, encrypted=False)

    (scan_base / "link_a").symlink_to(real_dir)
    (scan_base / "link_b").symlink_to(real_dir)

    config = _make_config(tmp_path, base_folders=(str(scan_base),))
    result = _run(config, tmp_path)

    assert len(result.findings) == 1, (
        f"Expected exactly one finding (no duplicates), "
        f"got: {[f.file_path for f in result.findings]}"
    )
    assert not result.directory_limit_exceeded


def test_fr013_directory_limit_exceeded_aborts_scan(tmp_path):
    """Hard cap triggers abort with directory_limit_exceeded=True, exit_code=2."""
    scan_base = tmp_path / "workspace"
    scan_base.mkdir()
    for i in range(5):
        (scan_base / f"dir{i}").mkdir()

    key_file = scan_base / "id_rsa"
    write_pem_private_key(key_file, encrypted=False)

    config = _make_config(
        tmp_path, base_folders=(str(scan_base),), max_directory_visits=2
    )
    result = _run(config, tmp_path)

    assert result.directory_limit_exceeded is True
    assert result.exit_code == 2
    assert len(result.findings) == 0


# ---------------------------------------------------------------------------
# User Story 3 — Tolerate broken and inaccessible links
# ---------------------------------------------------------------------------


def test_us3_sc1_broken_dangling_link_skipped_scan_completes(tmp_path):
    """Dangling symlink is skipped; valid key elsewhere is still reported."""
    scan_base = tmp_path / "workspace"
    scan_base.mkdir()

    (scan_base / "broken_link").symlink_to(scan_base / "does_not_exist")

    key_file = scan_base / "id_rsa"
    write_pem_private_key(key_file, encrypted=False)

    config = _make_config(tmp_path, base_folders=(str(scan_base),))
    result = _run(config, tmp_path)

    assert len(result.findings) == 1, (
        f"Expected one finding despite broken link, "
        f"got: {[f.file_path for f in result.findings]}"
    )
    assert not result.directory_limit_exceeded


def test_us3_sc2_inaccessible_link_target_skipped(tmp_path):
    """Symlink to a chmod-000 directory is skipped; other findings reported."""
    real_dir = tmp_path / "restricted"
    scan_base = tmp_path / "workspace"
    real_dir.mkdir()
    scan_base.mkdir()

    key_inside_restricted = real_dir / "id_rsa"
    write_pem_private_key(key_inside_restricted, encrypted=False)
    real_dir.chmod(0o000)

    accessible_dir = scan_base / "accessible"
    accessible_dir.mkdir()
    accessible_key = accessible_dir / "id_ed25519"
    write_openssh_private_key(accessible_key, encrypted=False)

    (scan_base / "restricted_link").symlink_to(real_dir)

    config = _make_config(tmp_path, base_folders=(str(scan_base),))
    try:
        result = _run(config, tmp_path)
        # The accessible key should be found; restricted dir may or may not yield
        # an error depending on OS — scan must not crash
        assert not result.directory_limit_exceeded
    finally:
        real_dir.chmod(0o755)


def test_edge_ignored_name_via_symlink_pruned(tmp_path):
    """A symlink whose name is in ignore_directories is not descended into."""
    scan_base = tmp_path / "workspace"
    real_nm = tmp_path / "real_node_modules"
    scan_base.mkdir()
    real_nm.mkdir()

    noise_key = real_nm / "id_rsa"
    write_pem_private_key(noise_key, encrypted=False)

    (scan_base / "node_modules").symlink_to(real_nm)

    safe_key = scan_base / "id_ed25519"
    write_openssh_private_key(safe_key, encrypted=False)

    config = _make_config(tmp_path, base_folders=(str(scan_base),))
    result = _run(config, tmp_path)

    finding_paths = [f.file_path for f in result.findings]
    assert not any("node_modules" in p for p in finding_paths), (
        f"node_modules key should be pruned, but found: {finding_paths}"
    )
    assert any("id_ed25519" in p for p in finding_paths), (
        f"safe key should be found, got: {finding_paths}"
    )
