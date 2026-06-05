"""Application service for orchestrating scans."""

from __future__ import annotations

from dataclasses import dataclass

from find_unencrypted_keys.adapters import filesystem, key_parsers
from find_unencrypted_keys.domain.classification import is_finding
from find_unencrypted_keys.domain.models import (
    CandidateState,
    ProtectionClassification,
    ScanRequest,
    ScanResult,
)


@dataclass(slots=True)
class ScanService:
    """Coordinate scope resolution, candidate discovery, and file assessment."""

    def run(self, request: ScanRequest) -> ScanResult:
        scope = filesystem.resolve_effective_scope(
            request.configuration,
            start_folder=request.start_folder,
        )
        candidates, issues = filesystem.discover_candidate_files(scope)

        result = ScanResult()
        for issue in issues:
            result.record_unreadable(issue.error_type)

        for candidate in candidates:
            result.files_scanned += 1
            assessment = key_parsers.inspect_candidate_file(candidate.canonical_path)

            if is_finding(assessment):
                candidate.state = CandidateState.REPORTED
                result.add_finding(
                    file_path=candidate.display_path,
                    classification=assessment.classification,
                )
                continue

            if assessment.classification == ProtectionClassification.MALFORMED:
                result.record_malformed()
                candidate.state = CandidateState.CLASSIFIED
            elif assessment.classification == ProtectionClassification.UNREADABLE:
                result.record_unreadable(assessment.classification.value)
                candidate.state = CandidateState.UNREADABLE
            else:
                candidate.state = CandidateState.CLEAN

        return result
