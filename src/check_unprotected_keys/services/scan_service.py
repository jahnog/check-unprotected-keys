"""Application service for orchestrating scans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from check_unprotected_keys.adapters import (
    filesystem,
    key_parsers,
    properties_inspector,
)
from check_unprotected_keys.adapters.filesystem import (
    DirectoryLimitExceededError,
    VisitedDirectoryTracker,
)
from check_unprotected_keys.domain.classification import is_finding
from check_unprotected_keys.domain.models import (
    CandidateFile,
    CandidateState,
    EffectiveScope,
    ProtectionClassification,
    RemediationRecommendation,
    ScanRequest,
    ScanResult,
    UsageCategory,
)

EMBEDDED_CONFIG_PATTERNS = frozenset(
    {
        ".env",
        ".env.*",
        "*.env",
        "*.env.*",
        "*.ovpn",
        "*.tfvars",
    }
)
INTERACTIVE_USER_PATTERNS = frozenset({"id_*", "identity", "*.ppk"})
AUTOMATION_PATH_HINTS = (
    "repo-keys",
    "deploy",
    "deployment",
    "infra",
    "ci",
    "cd",
    "runner",
    "pipeline",
    "vpn",
    "k8s",
    "kubernetes",
)


def infer_usage_category(candidate: CandidateFile) -> UsageCategory:
    """Infer a safe usage category from path and matched-pattern metadata."""

    matched_filename_pattern = candidate.matched_filename_pattern.lower()
    file_name = candidate.canonical_path.name.lower()
    path_parts = {part.lower() for part in candidate.canonical_path.parts}
    directory_text = str(candidate.canonical_path.parent).lower()
    folder_pattern = candidate.matched_folder_pattern.lower()
    automation_hint = _contains_automation_hint(directory_text, folder_pattern)

    if matched_filename_pattern == "ssh_host_*_key" or file_name.startswith(
        "ssh_host_"
    ):
        return UsageCategory.SSH_HOST_KEY

    if matched_filename_pattern in EMBEDDED_CONFIG_PATTERNS:
        return UsageCategory.EMBEDDED_CONFIG_SECRET

    if ".ssh" in path_parts or ".ssh" in folder_pattern:
        return UsageCategory.INTERACTIVE_USER_KEY

    if matched_filename_pattern in INTERACTIVE_USER_PATTERNS and not automation_hint:
        return UsageCategory.INTERACTIVE_USER_KEY

    if automation_hint:
        return UsageCategory.AUTOMATION_OR_DEPLOYMENT_KEY

    return UsageCategory.UNKNOWN


def build_remediation_recommendation(
    usage_category: UsageCategory,
) -> RemediationRecommendation:
    """Return the least-disruptive safe recommendation for a usage category."""

    match usage_category:
        case UsageCategory.INTERACTIVE_USER_KEY:
            return RemediationRecommendation(
                usage_category=usage_category,
                title="Passphrase plus session agent",
                summary=(
                    "Add a passphrase and load the key into ssh-agent or a "
                    "system keychain once per session."
                ),
                rationale=(
                    "Interactive SSH workflows can tolerate one unlock per "
                    "login session without repeated prompts."
                ),
                next_step_hint=(
                    "Re-save the key with a passphrase, then load it once per "
                    "session with ssh-add or your platform keychain."
                ),
            )
        case UsageCategory.SSH_HOST_KEY:
            return RemediationRecommendation(
                usage_category=usage_category,
                title="Reprovision as a managed host key",
                summary=(
                    "Keep host startup non-interactive by rotating the key "
                    "under root-only control or moving to certificate-based "
                    "host identity."
                ),
                rationale=(
                    "SSH host keys must stay available during service startup, "
                    "so interactive passphrase prompts are not appropriate."
                ),
                next_step_hint=(
                    "Rotate the host key with strict ownership and evaluate "
                    "host certificates or platform-managed host identity."
                ),
            )
        case UsageCategory.AUTOMATION_OR_DEPLOYMENT_KEY:
            return RemediationRecommendation(
                usage_category=usage_category,
                title="Move to a managed secret or identity",
                summary=(
                    "Replace the file-based key with a vault-managed secret or "
                    "workload identity that can be retrieved non-interactively."
                ),
                rationale=(
                    "Automation and deployment workflows break when they depend "
                    "on manual unlock prompts."
                ),
                next_step_hint=(
                    "Store the key in your secret manager or switch the "
                    "workload to a managed identity path."
                ),
            )
        case UsageCategory.EMBEDDED_CONFIG_SECRET:
            return RemediationRecommendation(
                usage_category=usage_category,
                title="Externalize the embedded secret",
                summary=(
                    "Remove the secret from the config file and load it "
                    "from a vault, secret manager, or OS/application key store."
                ),
                rationale=(
                    "Embedded secrets are hard to rotate and spread plaintext "
                    "secret material through config distribution."
                ),
                next_step_hint=(
                    "Delete the embedded secret from the file and leave only a "
                    "reference or lookup identifier."
                ),
            )
        case UsageCategory.UNKNOWN:
            return RemediationRecommendation(
                usage_category=usage_category,
                title="Classify usage before choosing a protection path",
                summary=(
                    "Confirm whether this key is used by a human or an "
                    "unattended workload before picking passphrase or vault "
                    "guidance."
                ),
                rationale=(
                    "The safest remediation depends on whether an interactive "
                    "prompt is acceptable."
                ),
                next_step_hint=(
                    "Identify the consuming process, then choose session-agent "
                    "protection for human use or managed secret storage for "
                    "unattended use."
                ),
            )


def _contains_automation_hint(directory_text: str, folder_pattern: str) -> bool:
    return any(
        hint in directory_text or hint in folder_pattern
        for hint in AUTOMATION_PATH_HINTS
    )


@dataclass(slots=True)
class ScanService:
    """Coordinate scope resolution, candidate discovery, and file assessment."""

    def run(self, request: ScanRequest) -> ScanResult:
        tracker = VisitedDirectoryTracker(
            limit=request.configuration.max_directory_visits
        )
        try:
            scope = filesystem.resolve_effective_scope(
                request.configuration,
                start_folder=request.start_folder,
                visited_tracker=tracker,
            )
            candidates, issues = filesystem.discover_candidate_files(
                scope,
                visited_tracker=tracker,
            )
        except DirectoryLimitExceededError:
            result = ScanResult()
            result.directory_limit_exceeded = True
            return result

        result = ScanResult()
        for issue in issues:
            result.record_unreadable(issue.error_type)

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
            assessment = key_parsers.inspect_candidate_file(candidate.canonical_path)

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
                result.record_unreadable(assessment.classification.value)
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
        inspection = properties_inspector.inspect_properties_file(
            candidate.canonical_path,
            name_patterns=request.configuration.property_name_patterns,
            scope=scope,
            value_ignore=request.configuration.property_value_ignore,
        )

        if inspection.unreadable:
            result.record_unreadable()
            candidate.state = CandidateState.UNREADABLE
            return

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
