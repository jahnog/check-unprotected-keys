"""Domain models for scan orchestration and reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ProtectionClassification(StrEnum):
    """File-level protection states for supported key material."""

    UNPROTECTED = "unprotected"
    PROTECTED_WITH_PASSPHRASE = "protected_with_passphrase"
    PUBLIC_ONLY = "public_only"
    MALFORMED = "malformed"
    UNREADABLE = "unreadable"


class UsageCategory(StrEnum):
    """Operator-facing usage categories for remediation guidance."""

    INTERACTIVE_USER_KEY = "interactive-user-key"
    SSH_HOST_KEY = "ssh-host-key"
    AUTOMATION_OR_DEPLOYMENT_KEY = "automation-or-deployment-key"
    EMBEDDED_CONFIG_SECRET = "embedded-config-secret"
    UNKNOWN = "unknown"


class CandidateState(StrEnum):
    """Lifecycle states for a candidate file during a scan."""

    DISCOVERED = "discovered"
    CLASSIFIED = "classified"
    REPORTED = "reported"
    CLEAN = "clean"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class SearchConfiguration:
    """Validated runtime search configuration.

    base_folders (preferred) or legacy folder_patterns define the ancestor
    trees (search bases) the scanner is authorized to explore.
    directory_names enable automatic promotion of high-value subdirectories.
    ignore_directories provide pruning for broad bases.
    """

    config_file_path: Path
    execution_root: Path
    base_folders: tuple[str, ...]
    directory_names: tuple[str, ...]
    ignore_directories: tuple[str, ...]
    ignore_filename_patterns: tuple[str, ...]
    filename_patterns: tuple[str, ...]
    property_name_patterns: tuple[str, ...] = ()
    max_directory_visits: int = 100_000
    load_warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScanRequest:
    """A single scanner invocation."""

    execution_root: Path
    configuration: SearchConfiguration
    start_folder: Path | None = None


@dataclass(frozen=True, slots=True)
class EffectiveScope:
    """The resolved directories and filename rules for a scan.

    ignore_directories may be carried for pruning during candidate walks
    (populated from configuration at resolution time).

    root_provenance (optional) maps each root to a rich label of the form
    "base:..., hint:..." (or just "base:...") for use in matched_folder_pattern.
    """

    root_directories: tuple[Path, ...]
    filename_patterns: tuple[str, ...]
    canonical_root_set: frozenset[Path]
    ignore_directories: frozenset[str] = frozenset()
    ignore_filename_patterns: frozenset[str] = frozenset()
    root_provenance: dict[Path, str] = field(default_factory=dict)


@dataclass(slots=True)
class CandidateFile:
    """A file selected for protection assessment."""

    canonical_path: Path
    display_path: str
    matched_folder_pattern: str
    matched_filename_pattern: str
    state: CandidateState = CandidateState.DISCOVERED


@dataclass(frozen=True, slots=True)
class ProtectionAssessment:
    """The safe-to-report classification for one candidate file."""

    classification: ProtectionClassification
    format_hint: str
    message: str


@dataclass(frozen=True, slots=True)
class RemediationRecommendation:
    """Operator-safe remediation guidance for one finding."""

    usage_category: UsageCategory
    title: str
    summary: str
    rationale: str
    next_step_hint: str


@dataclass(frozen=True, slots=True)
class MalformedScanIssue:
    """A candidate file that could not be fully parsed as supported key material."""

    file_path: str
    issue_type: str
    matched_folder_pattern: str
    matched_filename_pattern: str


@dataclass(frozen=True, slots=True)
class KeyFinding:
    """A file-level violation emitted to stdout.

    property_key is set only for property-level findings inside an inspected
    `.properties` file; it carries the offending property *key name*, never the
    secret value, so findings remain safe to print.
    """

    file_path: str
    classification: ProtectionClassification
    usage_category: UsageCategory | None = None
    remediation: RemediationRecommendation | None = None
    property_key: str | None = None

    @property
    def output_line(self) -> str:
        """Return the canonical stdout line for this finding.

        Property-level findings render as ``<file path>#<property key>`` so each
        offending property is independently identifiable; file-level findings
        render as the path alone.
        """

        if self.property_key is not None:
            return f"{self.file_path}#{self.property_key}"
        return self.file_path


@dataclass(slots=True)
class ScanResult:
    """Aggregate scan outcome for one command invocation."""

    files_scanned: int = 0
    findings: list[KeyFinding] = field(default_factory=list)
    malformed_issues: list[MalformedScanIssue] = field(default_factory=list)
    unreadable_count: int = 0
    error_summaries: dict[str, int] = field(default_factory=dict)
    directory_limit_exceeded: bool = False

    @property
    def exit_code(self) -> int:
        if self.directory_limit_exceeded:
            return 2
        return 1 if self.findings else 0

    @property
    def malformed_count(self) -> int:
        return len(self.malformed_issues)

    @property
    def safe_issue_breakdown(self) -> tuple[str, ...]:
        return tuple(
            f"{issue_type}={count}"
            for issue_type, count in sorted(self.error_summaries.items())
        )

    def add_finding(
        self,
        *,
        file_path: str,
        classification: ProtectionClassification,
        usage_category: UsageCategory | None = None,
        remediation: RemediationRecommendation | None = None,
        property_key: str | None = None,
    ) -> None:
        self.findings.append(
            KeyFinding(
                file_path=file_path,
                classification=classification,
                usage_category=usage_category,
                remediation=remediation,
                property_key=property_key,
            )
        )

    def record_malformed(
        self,
        *,
        file_path: str,
        matched_folder_pattern: str,
        matched_filename_pattern: str,
    ) -> None:
        self.malformed_issues.append(
            MalformedScanIssue(
                file_path=file_path,
                issue_type=ProtectionClassification.MALFORMED.value,
                matched_folder_pattern=matched_folder_pattern,
                matched_filename_pattern=matched_filename_pattern,
            )
        )
        self.record_issue(ProtectionClassification.MALFORMED.value)

    def record_unreadable(self, issue_type: str | None = None) -> None:
        self.unreadable_count += 1
        self.record_issue(issue_type or ProtectionClassification.UNREADABLE.value)

    def record_issue(self, issue_type: str) -> None:
        self.error_summaries[issue_type] = self.error_summaries.get(issue_type, 0) + 1
