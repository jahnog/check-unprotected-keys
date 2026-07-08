"""Protocol seams between the scan orchestrator and its collaborators.

`ScanService` depends on these structural interfaces instead of concrete
adapter modules (Dependency Inversion, spec 010 FR-007), so each orchestration
branch can be unit-tested with in-memory fakes. The production defaults are
the existing adapter functions, which satisfy these Protocols as-is.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from check_unprotected_keys.domain.discovery import (
    DiscoveryIssue,
    VisitedDirectoryTracker,
)
from check_unprotected_keys.domain.models import (
    CandidateFile,
    EffectiveScope,
    ProtectionAssessment,
    ProtectionClassification,
    SearchConfiguration,
    SkippedLocation,
)


class PropertyFindingLike(Protocol):
    """Minimal shape of one property-level finding (domain-facing)."""

    property_key: str
    classification: ProtectionClassification


class PropertiesInspectionOutcome(Protocol):
    """Structural result of inspecting one ``.properties`` file.

    Defined here so ports do not import adapter modules. The production
    ``PropertyInspectionResult`` dataclass satisfies this Protocol.
    """

    findings: tuple[PropertyFindingLike, ...]
    assessed_references: tuple[tuple[Path, ProtectionClassification], ...]
    unreadable: bool
    skipped: tuple[SkippedLocation, ...]


class ScopeResolver(Protocol):
    """Resolves the effective scan scope from configuration."""

    def __call__(
        self,
        configuration: SearchConfiguration,
        *,
        start_folder: Path | None,
        visited_tracker: VisitedDirectoryTracker | None = None,
        issues: list[DiscoveryIssue] | None = None,
    ) -> EffectiveScope: ...


class CandidateDiscoverer(Protocol):
    """Enumerates candidate files (and non-fatal issues) inside a scope."""

    def __call__(
        self,
        scope: EffectiveScope,
        *,
        visited_tracker: VisitedDirectoryTracker | None = None,
    ) -> tuple[list[CandidateFile], list[DiscoveryIssue]]: ...


class KeyInspector(Protocol):
    """Classifies the protection state of one candidate key file."""

    def __call__(self, candidate_path: Path) -> ProtectionAssessment: ...


class PropertiesInspector(Protocol):
    """Inspects one ``.properties`` file for per-property secrets."""

    def __call__(
        self,
        path: Path,
        *,
        name_patterns: tuple[str, ...],
        scope: EffectiveScope,
        value_ignore: tuple[str, ...] = (),
    ) -> PropertiesInspectionOutcome: ...
