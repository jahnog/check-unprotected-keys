"""Directory-visit budget, tracker, and non-fatal discovery issues.

These types sit in the domain layer so application ports and the scan
orchestrator do not depend on adapter modules (FR-007). The filesystem
adapter re-exports them for backward-compatible imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from check_unprotected_keys.domain.models import (
    DEFAULT_MAX_DIRECTORY_VISITS,
    CandidateFile,
    SkipPhase,
)


class DirectoryLimitExceededError(RuntimeError):
    """Raised when the visited-directory count reaches the configured hard cap.

    ``partial_candidates``/``partial_issues`` carry whatever discovery gathered
    before the cap was hit so callers can report partial results (FR-002).
    """

    def __init__(self, limit: int, path: Path) -> None:
        self.limit = limit
        self.path = path
        self.partial_candidates: tuple[CandidateFile, ...] = ()
        self.partial_issues: tuple[DiscoveryIssue, ...] = ()
        super().__init__(
            f"Directory visit limit ({limit}) reached at: {path}. Scan is incomplete."
        )


class DirectoryVisitBudget:
    """Shared charge counter for directory visits across scan phases.

    Promotion and discovery each keep their own cycle-detection set, but both
    charge this budget so ``max_directory_visits`` is a single hard cap rather
    than ~2× independent limits.
    """

    def __init__(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("directory visit budget limit must be non-negative")
        self._limit = limit
        self._used = 0

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def used(self) -> int:
        return self._used

    def charge(self, path: Path) -> None:
        """Consume one visit slot for ``path``, or raise if the cap is reached."""

        if self._used >= self._limit:
            raise DirectoryLimitExceededError(self._limit, path)
        self._used += 1


class VisitedDirectoryTracker:
    """Tracks visited directories by OS-level identity within one walk phase.

    Uses ``(st_ino, st_dev)`` as the directory key so bind mounts and
    case-insensitive filesystem aliases are correctly deduplicated. The visit
    budget may be shared across phases; the cycle set is always local.
    """

    def __init__(
        self,
        limit: int | None = None,
        *,
        budget: DirectoryVisitBudget | None = None,
    ) -> None:
        if budget is not None and limit is not None:
            raise ValueError("pass limit or budget, not both")
        if budget is None:
            budget = DirectoryVisitBudget(
                limit if limit is not None else DEFAULT_MAX_DIRECTORY_VISITS
            )
        self._budget = budget
        self._visited: set[tuple[int, int]] = set()

    @property
    def budget(self) -> DirectoryVisitBudget:
        return self._budget

    def try_visit(self, path: Path) -> bool:
        """Stat path and record as visited if new.

        Returns True if the directory is newly visited (caller should descend).
        Returns False if already visited (caller should skip).
        Raises OSError if path cannot be stat'd (broken or inaccessible link).
        Raises DirectoryLimitExceededError if the shared budget is exhausted.
        """
        stat = path.stat()
        key = (stat.st_ino, stat.st_dev)
        if key in self._visited:
            return False
        self._budget.charge(path)
        self._visited.add(key)
        return True

    @property
    def visited_count(self) -> int:
        return len(self._visited)


@dataclass(frozen=True, slots=True)
class DiscoveryIssue:
    """A non-fatal filesystem issue discovered while expanding scope or walking."""

    location: Path
    error_type: str
    phase: SkipPhase = SkipPhase.CANDIDATE_DISCOVERY
