"""Application service for orchestrating scans."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from check_unprotected_keys.adapters import (
    filesystem,
    key_parsers,
    properties_inspector,
)
from check_unprotected_keys.domain.discovery import (
    DirectoryLimitExceededError,
    DiscoveryIssue,
    VisitedDirectoryTracker,
)
from check_unprotected_keys.domain import remediation as remediation_registry
from check_unprotected_keys.domain.classification import is_finding
from check_unprotected_keys.domain.models import (
    CandidateFile,
    CandidateState,
    EffectiveScope,
    ProtectionClassification,
    ScanRequest,
    ScanResult,
    SkippedLocation,
    SkipPhase,
    UsageCategory,
)
from check_unprotected_keys.services.ports import (
    CandidateDiscoverer,
    KeyInspector,
    PropertiesInspector,
    ScopeResolver,
)

# Classification rules and remediation prose live in the single authoritative
# registry (FR-005); these names stay importable from here for compatibility.
infer_usage_category = remediation_registry.infer_usage_category
build_remediation_recommendation = remediation_registry.build_remediation_recommendation


@dataclass(slots=True)
class ScanService:
    """Coordinate scope resolution, candidate discovery, and file assessment.

    Collaborators are injected through the Protocol seams in
    :mod:`check_unprotected_keys.services.ports` (FR-007); the defaults are the
    production adapters, so ``ScanService()`` behaves exactly as before.
    """

    scope_resolver: ScopeResolver = field(default=filesystem.resolve_effective_scope)
    candidate_discoverer: CandidateDiscoverer = field(
        default=filesystem.discover_candidate_files
    )
    key_inspector: KeyInspector = field(default=key_parsers.inspect_candidate_file)
    props_inspector: PropertiesInspector = field(
        default=properties_inspector.inspect_properties_file
    )

    def run(self, request: ScanRequest) -> ScanResult:
        tracker = VisitedDirectoryTracker(
            limit=request.configuration.max_directory_visits
        )
        result = ScanResult()
        resolve_issues: list[DiscoveryIssue] = []
        try:
            scope = self.scope_resolver(
                request.configuration,
                start_folder=request.start_folder,
                visited_tracker=tracker,
                issues=resolve_issues,
            )
        except DirectoryLimitExceededError:
            result.directory_limit_exceeded = True
            # FR-001: promotion/base issues collected before the cap must not
            # be dropped when the visit limit aborts during scope resolution.
            for issue in resolve_issues:
                result.record_skip(
                    SkippedLocation(
                        path=issue.location,
                        reason=issue.error_type,
                        phase=issue.phase,
                    )
                )
            return result

        try:
            candidates, issues = self.candidate_discoverer(
                scope,
                visited_tracker=tracker,
            )
        except DirectoryLimitExceededError as error:
            # Keep whatever discovery gathered before the cap (FR-002): the
            # partial candidates are still assessed and reported below.
            result.directory_limit_exceeded = True
            candidates = list(error.partial_candidates)
            issues = list(error.partial_issues)

        for issue in resolve_issues:
            result.record_skip(
                SkippedLocation(
                    path=issue.location,
                    reason=issue.error_type,
                    phase=issue.phase,
                )
            )
        for issue in issues:
            result.record_unreadable(issue.error_type)
            result.record_skip(
                SkippedLocation(
                    path=issue.location,
                    reason=issue.error_type,
                    phase=issue.phase,
                )
            )

        # Seed with every directly-discovered file so a key file reached only by
        # following a .properties reference is counted at most once (FR-013).
        scanned_paths: set[Path] = {
            candidate.canonical_path for candidate in candidates
        }

        for candidate in candidates:
            if candidate.canonical_path.suffix == ".properties":
                self._inspect_properties_candidate(
                    candidate, request, scope, result, scanned_paths
                )
                continue

            result.files_scanned += 1
            assessment = self.key_inspector(candidate.canonical_path)

            if is_finding(assessment):
                candidate.state = CandidateState.REPORTED
                usage_category = infer_usage_category(candidate)
                result.add_finding(
                    file_path=candidate.display_path,
                    classification=assessment.classification,
                    usage_category=usage_category,
                    remediation=build_remediation_recommendation(usage_category),
                )
                continue

            if assessment.classification == ProtectionClassification.MALFORMED:
                result.record_malformed(
                    file_path=candidate.display_path,
                    matched_folder_pattern=candidate.matched_folder_pattern,
                    matched_filename_pattern=candidate.matched_filename_pattern,
                )
                candidate.state = CandidateState.CLASSIFIED
            elif assessment.classification == ProtectionClassification.UNREADABLE:
                skip_reason = (
                    assessment.reason or ProtectionClassification.UNREADABLE.value
                )
                result.record_unreadable(skip_reason)
                result.record_skip(
                    SkippedLocation(
                        path=candidate.canonical_path,
                        reason=skip_reason,
                        phase=SkipPhase.FILE_INSPECTION,
                    )
                )
                candidate.state = CandidateState.UNREADABLE
            else:
                candidate.state = CandidateState.CLEAN

        return result

    def _inspect_properties_candidate(
        self,
        candidate: CandidateFile,
        request: ScanRequest,
        scope: EffectiveScope,
        result: ScanResult,
        scanned_paths: set[Path],
    ) -> None:
        """Inspect one ``.properties`` candidate for per-property secrets."""

        result.files_scanned += 1
        inspection = self.props_inspector(
            candidate.canonical_path,
            name_patterns=request.configuration.property_name_patterns,
            scope=scope,
            value_ignore=request.configuration.property_value_ignore,
        )

        if inspection.unreadable:
            result.record_unreadable()
            result.record_skip(
                SkippedLocation(
                    path=candidate.canonical_path,
                    reason=ProtectionClassification.UNREADABLE.value,
                    phase=SkipPhase.FILE_INSPECTION,
                )
            )
            candidate.state = CandidateState.UNREADABLE
            return

        for skip in inspection.skipped:
            result.record_skip(skip)

        # Count followed key files once (FR-013); their findings are emitted below.
        for reference_path, _classification in inspection.assessed_references:
            if reference_path not in scanned_paths:
                scanned_paths.add(reference_path)
                result.files_scanned += 1

        if not inspection.findings:
            candidate.state = CandidateState.CLEAN
            return

        candidate.state = CandidateState.REPORTED
        usage_category = UsageCategory.EMBEDDED_CONFIG_SECRET
        remediation = build_remediation_recommendation(usage_category)
        for finding in inspection.findings:
            result.add_finding(
                file_path=candidate.display_path,
                classification=finding.classification,
                usage_category=usage_category,
                remediation=remediation,
                property_key=finding.property_key,
            )
