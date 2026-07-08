"""Fake-driven unit tests for ScanService orchestration (spec 010 FR-007).

No test here touches the real filesystem: collaborators are substituted
through the Protocol seams in ``services/ports.py``.
"""

from __future__ import annotations

from pathlib import Path

from check_unprotected_keys.adapters.filesystem import (
    DirectoryLimitExceededError,
    DiscoveryIssue,
)
from check_unprotected_keys.adapters.properties_inspector import (
    PropertyFinding,
    PropertyFindingOrigin,
    PropertyInspectionResult,
)
from check_unprotected_keys.domain.classification import build_assessment
from check_unprotected_keys.domain.models import (
    CandidateFile,
    CandidateState,
    EffectiveScope,
    ProtectionClassification,
    ScanRequest,
    SearchConfiguration,
    SkippedLocation,
    SkipPhase,
    UsageCategory,
)
from check_unprotected_keys.services.scan_service import ScanService

_ROOT = Path("/mem/scan")


def _configuration() -> SearchConfiguration:
    return SearchConfiguration(
        config_file_path=_ROOT / ".check-unprotected-keys.toml",
        execution_root=_ROOT,
        base_folders=(str(_ROOT),),
        directory_names=(),
        ignore_directories=(),
        ignore_filename_patterns=(),
        filename_patterns=("id_*", "*.pem", "*.properties"),
        property_name_patterns=("*password*", "*secret*", "*key*"),
    )


def _scope() -> EffectiveScope:
    return EffectiveScope(
        root_directories=(_ROOT,),
        filename_patterns=("id_*", "*.pem", "*.properties"),
        canonical_root_set=frozenset({_ROOT}),
    )


def _candidate(name: str) -> CandidateFile:
    path = _ROOT / name
    return CandidateFile(
        canonical_path=path,
        display_path=str(path),
        matched_folder_pattern=f"base:{_ROOT}",
        matched_filename_pattern="id_*",
    )


def _request() -> ScanRequest:
    return ScanRequest(execution_root=_ROOT, configuration=_configuration())


def _service(
    *,
    candidates: list[CandidateFile] | None = None,
    issues: list[DiscoveryIssue] | None = None,
    resolver=None,
    discoverer=None,
    key_inspector=None,
    props_inspector=None,
) -> ScanService:
    def default_resolver(
        configuration, *, start_folder, visited_tracker=None, issues=None
    ):
        return _scope()

    def default_discoverer(scope, *, visited_tracker=None):
        return list(candidates or []), list(issues or [])

    def default_key_inspector(candidate_path: Path):
        return build_assessment(
            ProtectionClassification.UNPROTECTED,
            format_hint="pem",
            message="PEM private key is not protected.",
        )

    def default_props_inspector(path, *, name_patterns, scope, value_ignore=()):
        return PropertyInspectionResult(
            findings=(), assessed_references=(), unreadable=False
        )

    return ScanService(
        scope_resolver=resolver or default_resolver,
        candidate_discoverer=discoverer or default_discoverer,
        key_inspector=key_inspector or default_key_inspector,
        props_inspector=props_inspector or default_props_inspector,
    )


def test_limit_during_scope_resolution_returns_empty_flagged_result() -> None:
    def resolver(configuration, *, start_folder, visited_tracker=None, issues=None):
        if issues is not None:
            issues.append(
                DiscoveryIssue(
                    location=_ROOT / "promo-broken",
                    error_type="PermissionError",
                    phase=SkipPhase.DIRECTORY_PROMOTION,
                )
            )
        raise DirectoryLimitExceededError(2, _ROOT)

    result = _service(resolver=resolver).run(_request())

    assert result.directory_limit_exceeded is True
    assert result.exit_code == 2
    assert result.findings == []
    assert result.files_scanned == 0
    # FR-001: issues collected before the cap must still surface as skips.
    assert len(result.skipped_locations) == 1
    skip = result.skipped_locations[0]
    assert skip.path == _ROOT / "promo-broken"
    assert skip.reason == "PermissionError"
    assert skip.phase is SkipPhase.DIRECTORY_PROMOTION


def test_limit_mid_discovery_preserves_partial_candidates() -> None:
    partial = _candidate("id_rsa")

    def discoverer(scope, *, visited_tracker=None):
        error = DirectoryLimitExceededError(2, _ROOT / "deep")
        error.partial_candidates = (partial,)
        error.partial_issues = (
            DiscoveryIssue(location=_ROOT / "hidden", error_type="PermissionError"),
        )
        raise error

    result = _service(discoverer=discoverer).run(_request())

    assert result.directory_limit_exceeded is True
    assert result.exit_code == 2
    assert [finding.file_path for finding in result.findings] == [str(_ROOT / "id_rsa")]
    assert result.files_scanned == 1
    assert [skip.path for skip in result.skipped_locations] == [_ROOT / "hidden"]


def test_malformed_candidate_is_counted_and_classified() -> None:
    candidate = _candidate("id_broken")

    def key_inspector(candidate_path: Path):
        return build_assessment(
            ProtectionClassification.MALFORMED,
            format_hint="unknown",
            message="No private keys were detected.",
        )

    result = _service(candidates=[candidate], key_inspector=key_inspector).run(
        _request()
    )

    assert result.findings == []
    assert result.malformed_count == 1
    assert candidate.state is CandidateState.CLASSIFIED
    assert result.exit_code == 0


def test_unreadable_candidate_records_skip_with_file_inspection_phase() -> None:
    candidate = _candidate("id_locked")

    def key_inspector(candidate_path: Path):
        return build_assessment(
            ProtectionClassification.UNREADABLE,
            format_hint="filesystem",
            message="It was not possible to read the file: PermissionError",
        )

    result = _service(candidates=[candidate], key_inspector=key_inspector).run(
        _request()
    )

    assert result.unreadable_count == 1
    assert candidate.state is CandidateState.UNREADABLE
    assert len(result.skipped_locations) == 1
    skip = result.skipped_locations[0]
    assert skip.path == candidate.canonical_path
    assert skip.phase is SkipPhase.FILE_INSPECTION
    assert skip.reason == ProtectionClassification.UNREADABLE.value


def test_undecodable_content_skip_reason_surfaces_on_file_inspection() -> None:
    candidate = _candidate("corrupt.ppk")

    def key_inspector(candidate_path: Path):
        return build_assessment(
            ProtectionClassification.UNREADABLE,
            format_hint="putty",
            message="PuTTY private key bytes could not be decoded (undecodable-content).",
            reason="undecodable-content",
        )

    result = _service(candidates=[candidate], key_inspector=key_inspector).run(
        _request()
    )

    assert len(result.skipped_locations) == 1
    skip = result.skipped_locations[0]
    assert skip.reason == "undecodable-content"
    assert skip.phase is SkipPhase.FILE_INSPECTION
    assert result.error_summaries.get("undecodable-content") == 1


def test_protected_candidate_is_clean_without_findings() -> None:
    candidate = _candidate("id_safe")

    def key_inspector(candidate_path: Path):
        return build_assessment(
            ProtectionClassification.PROTECTED_WITH_PASSPHRASE,
            format_hint="pem",
            message="PEM private key is protected with a passphrase.",
        )

    result = _service(candidates=[candidate], key_inspector=key_inspector).run(
        _request()
    )

    assert result.findings == []
    assert candidate.state is CandidateState.CLEAN
    assert result.exit_code == 0


def test_discovery_and_resolve_issues_become_phased_skips() -> None:
    def resolver(configuration, *, start_folder, visited_tracker=None, issues=None):
        if issues is not None:
            issues.append(
                DiscoveryIssue(
                    location=_ROOT / "base-file",
                    error_type="NotADirectory",
                    phase=SkipPhase.SCOPE_RESOLUTION,
                )
            )
            issues.append(
                DiscoveryIssue(
                    location=_ROOT / "promo-broken",
                    error_type="OSError",
                    phase=SkipPhase.DIRECTORY_PROMOTION,
                )
            )
        return _scope()

    issues = [
        DiscoveryIssue(
            location=_ROOT / "hidden",
            error_type="PermissionError",
            phase=SkipPhase.CANDIDATE_DISCOVERY,
        )
    ]
    result = _service(resolver=resolver, issues=issues).run(_request())

    phases = {skip.path: skip.phase for skip in result.skipped_locations}
    assert phases == {
        _ROOT / "base-file": SkipPhase.SCOPE_RESOLUTION,
        _ROOT / "promo-broken": SkipPhase.DIRECTORY_PROMOTION,
        _ROOT / "hidden": SkipPhase.CANDIDATE_DISCOVERY,
    }
    assert result.unreadable_count == 1  # only discovery issues feed the counter


def test_properties_candidate_routes_to_properties_inspector() -> None:
    candidate = CandidateFile(
        canonical_path=_ROOT / "app.properties",
        display_path=str(_ROOT / "app.properties"),
        matched_folder_pattern=f"base:{_ROOT}",
        matched_filename_pattern="*.properties",
    )
    referenced = _ROOT / "keys" / "server.pem"

    def props_inspector(path, *, name_patterns, scope, value_ignore=()):
        return PropertyInspectionResult(
            findings=(
                PropertyFinding(
                    property_key="db.password",
                    classification=ProtectionClassification.UNPROTECTED,
                    origin=PropertyFindingOrigin.PLAINTEXT_SECRET,
                ),
            ),
            assessed_references=(
                (referenced, ProtectionClassification.PROTECTED_WITH_PASSPHRASE),
            ),
            unreadable=False,
            skipped=(
                SkippedLocation(
                    path=_ROOT / "keys" / "missing.pem",
                    reason="unresolvable-reference",
                    phase=SkipPhase.REFERENCE_FOLLOW,
                ),
            ),
        )

    result = _service(candidates=[candidate], props_inspector=props_inspector).run(
        _request()
    )

    assert candidate.state is CandidateState.REPORTED
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.property_key == "db.password"
    assert finding.usage_category is UsageCategory.EMBEDDED_CONFIG_SECRET
    assert finding.remediation is not None
    # properties file + followed reference each count once
    assert result.files_scanned == 2
    assert [skip.reason for skip in result.skipped_locations] == [
        "unresolvable-reference"
    ]


def test_unreadable_properties_candidate_records_skip() -> None:
    candidate = CandidateFile(
        canonical_path=_ROOT / "locked.properties",
        display_path=str(_ROOT / "locked.properties"),
        matched_folder_pattern=f"base:{_ROOT}",
        matched_filename_pattern="*.properties",
    )

    def props_inspector(path, *, name_patterns, scope, value_ignore=()):
        return PropertyInspectionResult(
            findings=(), assessed_references=(), unreadable=True
        )

    result = _service(candidates=[candidate], props_inspector=props_inspector).run(
        _request()
    )

    assert candidate.state is CandidateState.UNREADABLE
    assert result.unreadable_count == 1
    assert [skip.phase for skip in result.skipped_locations] == [
        SkipPhase.FILE_INSPECTION
    ]
