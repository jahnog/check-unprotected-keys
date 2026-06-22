---
description: "Task list for Symlink-Following, Cycle-Safe Folder Traversal"
---

# Tasks: Symlink-Following, Cycle-Safe Folder Traversal

**Input**: Design documents from `specs/006-symlink-safe-traversal/`

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅

**Tests**: Unit and integration tests are REQUIRED per the project constitution.
Write tests before implementation; verify they fail first; triage any post-implementation
failures before changing test or code.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: User story this task belongs to (US1 / US2 / US3)

---

## Phase 1: Foundational — Model Additions and Core Infrastructure

**Purpose**: Add all new data structures, config fields, and the `VisitedDirectoryTracker`
class without changing any existing traversal behavior. These are non-behavioral
additions that must exist before any user story implementation can compile.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T001 [P] Add `max_directory_visits: int = 100_000` field to `ScanConfigSection` in `src/check_unprotected_keys/config/models.py`
- [X] T002 [P] Add `max_directory_visits: int = 100_000` field to `SearchConfiguration` in `src/check_unprotected_keys/domain/models.py`
- [X] T003 Add `directory_limit_exceeded: bool = False` field to `ScanResult` and update `exit_code` property to return `2` when `directory_limit_exceeded` is True in `src/check_unprotected_keys/domain/models.py`
- [X] T004 Update `load_search_configuration` in `src/check_unprotected_keys/config/loader.py` to read optional `scan.max_directory_visits` integer (default `100_000`, validate ≥ 1, raise `ConfigurationError` on invalid value) and propagate through `ScanConfigSection` → `SearchConfiguration`
- [X] T005 [P] Define `DirectoryLimitExceededError(RuntimeError)` with `limit: int` and `path: Path` attributes in `src/check_unprotected_keys/adapters/filesystem.py`
- [X] T006 Implement `VisitedDirectoryTracker` class in `src/check_unprotected_keys/adapters/filesystem.py` with `__init__(self, limit: int)`, `try_visit(self, path: Path) -> bool` (stat path, key on `(st_ino, st_dev)`, return True if new / False if seen, raise `DirectoryLimitExceededError` if cap reached, propagate `OSError` for broken paths), and `visited_count: int` property
- [X] T007 Add module-level `_logger = logging.getLogger(__name__)` and private `_prune_with_visit_check(dirnames: list[str], current_path: Path, ignore_set: frozenset[str], tracker: VisitedDirectoryTracker, issues: list[DiscoveryIssue] | None = None) -> None` helper in `src/check_unprotected_keys/adapters/filesystem.py` that mutates `dirnames` in-place: skips ignored names, calls `tracker.try_visit` per subdirectory, logs DEBUG for already-visited and inaccessible, appends `DiscoveryIssue` for `OSError` when `issues` is provided, re-raises `DirectoryLimitExceededError`
- [X] T008 Update existing fixture builders and affected unit tests in `tests/unit/test_config_loader.py` and `tests/support/fixture_builders.py` to supply the new `max_directory_visits` field where `SearchConfiguration` or `ScanConfigSection` objects are constructed

**Checkpoint**: All models compile and existing tests pass. No traversal behavior changed yet.

---

## Phase 2: User Story 1 — Discover Keys Behind Symbolic Links (Priority: P1) 🎯 MVP

**Goal**: The scanner follows symbolic links to directories and files, discovering key
material that was previously silently skipped.

**Independent Test**: Create a real key file outside the search base; create a symlink
inside the search base pointing to the directory containing that file; run the scanner;
confirm the key is reported. Then remove the symlink; confirm the key is no longer found.

### Tests for User Story 1 (write first — MUST FAIL before T012–T015) ⚠️

- [X] T009 [P] [US1] Write `tests/unit/test_visited_directory_tracker.py` covering: new real directory → `try_visit` returns `True` and `visited_count` increments; same directory visited again → returns `False`; same real directory reached via two paths (second path is a symlink to the first) → returns `False`; two distinct directories → both return `True`, count is 2; `visited_count` reflects unique entries only
- [X] T010 [P] [US1] Write integration tests in `tests/integration/test_symlink_traversal.py` for US1 SC1 (symlink inside base → real dir containing unprotected key → key reported), US1 SC2 (symlink inside base → key file directly → file evaluated and reported), and US1 SC3 (symlink → dir with passphrase-protected key → no finding, not a false positive)
- [X] T011 [US1] Run `pytest tests/unit/test_visited_directory_tracker.py tests/integration/test_symlink_traversal.py` and confirm T009–T010 tests fail (no behavior change yet); record which tests fail and why before proceeding

### Implementation for User Story 1

- [X] T012 [US1] Add `visited_tracker: VisitedDirectoryTracker` keyword parameter to `_discover_promoted_directories`, change `os.walk(..., followlinks=False)` → `followlinks=True`, replace inline `dirnames[:] = [d for d in dirnames if d not in ignore_names]` with `_prune_with_visit_check(dirnames, current, ignore_names, visited_tracker)`, and add `tracker.try_visit(base)` check before each walk (skip base if returns False) in `src/check_unprotected_keys/adapters/filesystem.py`
- [X] T013 [US1] Add `visited_tracker: VisitedDirectoryTracker` keyword parameter to `discover_candidate_files`, change `os.walk(..., followlinks=False)` → `followlinks=True`, replace inline `dirnames` ignore pruning with `_prune_with_visit_check(dirnames, current_path, ignore_set, visited_tracker, issues)`, and add `tracker.try_visit(root_directory)` check before each walk (skip root if returns False) in `src/check_unprotected_keys/adapters/filesystem.py`
- [X] T014 [US1] Add `visited_tracker: VisitedDirectoryTracker` keyword parameter to `resolve_effective_scope` and thread it into `_discover_promoted_directories` call in `src/check_unprotected_keys/adapters/filesystem.py`
- [X] T015 [US1] Update `ScanService.run()` in `src/check_unprotected_keys/services/scan_service.py`: construct `tracker = VisitedDirectoryTracker(limit=request.configuration.max_directory_visits)`, pass `visited_tracker=tracker` to both `filesystem.resolve_effective_scope(...)` and `filesystem.discover_candidate_files(...)`, wrap both calls in `try/except DirectoryLimitExceededError` that sets `result.directory_limit_exceeded = True` and returns early
- [X] T016 [US1] Run `pytest tests/unit/test_visited_directory_tracker.py tests/integration/test_symlink_traversal.py` and confirm all US1 tests pass; triage any failure — determine whether test logic or implementation logic is wrong, record conclusion, only then fix

**Checkpoint**: Symlinks to directories and files are followed. US1 acceptance scenarios pass independently.

---

## Phase 3: User Story 2 — Single-Visit Guarantee and Cycle Safety (Priority: P1)

**Goal**: Every scan terminates even in the presence of symbolic-link cycles,
and each real directory is entered at most once across all traversal passes.

**Independent Test**: Build a directory tree with a self-referential symlink and an
unprotected key. Run the scanner; confirm it terminates promptly, the key is reported
exactly once, and the process does not loop.

### Tests for User Story 2 (write first — hard cap and exit_code tests MUST FAIL) ⚠️

- [X] T017 [P] [US2] Write integration tests in `tests/integration/test_symlink_traversal.py` for US2 SC1 (self-referential link `dir/loop → dir` → terminates, key reported once), US2 SC2 (mutual cycle `a/link_to_b → b`, `b/link_to_a → a` → terminates, key reported once), US2 SC3 (ancestor loop `a/b/link_to_a → a` → terminates), and US2 SC4 (two distinct symlinks to same real dir → key reported exactly once, no duplicates)
- [X] T018 [P] [US2] Write unit tests in `tests/unit/test_visited_directory_tracker.py` for: hard cap of 1 dir with a second dir attempted → raises `DirectoryLimitExceededError` with correct `.limit` and `.path`; path that does not exist → `OSError` propagates (not swallowed)
- [X] T019 [P] [US2] Write integration test in `tests/integration/test_symlink_traversal.py` for FR-013: `max_directory_visits=2` config with a 5-dir tree → `result.directory_limit_exceeded` is `True`, `result.exit_code` is `2`, stdout is empty (no findings), stderr contains "directory visit limit"
- [X] T020 [US2] Run `pytest tests/unit/test_visited_directory_tracker.py tests/integration/test_symlink_traversal.py` and confirm T018–T019 tests fail (hard cap catching and reporting not wired yet); record failures before proceeding

### Implementation for User Story 2

- [X] T021 [US2] Add `except DirectoryLimitExceededError` handler in `ScanService.run()` that sets `result.directory_limit_exceeded = True` and returns the partial (empty) `ScanResult` immediately in `src/check_unprotected_keys/services/scan_service.py` (T015 may have added a stub; complete the implementation here)
- [X] T022 [US2] Add `directory_limit_exceeded` guard at the top of `emit_scan_result` in `src/check_unprotected_keys/adapters/reporting.py` to print an actionable error to stderr and return early when `result.directory_limit_exceeded` is True: `"ERROR: Scan aborted — directory visit limit reached. Results are incomplete.\nRaise scan.max_directory_visits in your configuration to scan larger trees, or narrow the scope with --start-folder."`
- [X] T023 [US2] Add a commented-out `max_directory_visits` entry with description to the `[scan]` table in `src/check_unprotected_keys/resources/check-unprotected-keys.example.toml`
- [X] T024 [US2] Run `pytest tests/unit/test_visited_directory_tracker.py tests/integration/test_symlink_traversal.py` and confirm all US2 tests pass; triage any failure before changing test or code

**Checkpoint**: All US1 and US2 acceptance scenarios pass independently. Cycles are detected, scans terminate, and the hard cap aborts cleanly.

---

## Phase 4: User Story 3 — Tolerate Broken and Inaccessible Links (Priority: P2)

**Goal**: Dangling and permission-denied symbolic links are silently skipped without
aborting the scan. All other findings are still reported.

**Independent Test**: Create a dangling symlink alongside an unprotected key file.
Run the scanner; confirm it completes, the key is reported, and exit code is 1 (not 2).

### Tests for User Story 3 (write first — MUST FAIL if not yet handled) ⚠️

- [X] T025 [P] [US3] Write integration tests in `tests/integration/test_symlink_traversal.py` for US3 SC1 (dangling symlink present, valid key elsewhere → scan completes, key reported, no crash) and US3 SC2 (symlink to chmod-000 directory, valid key elsewhere → scan completes, all reachable findings reported)
- [X] T026 [P] [US3] Write integration test in `tests/integration/test_symlink_traversal.py` for edge case "ignored-name via link": a symlink whose basename is `node_modules` (or pointing to a dir named `node_modules`) is pruned and not descended into
- [X] T027 [US3] Confirm tests T025–T026 fail; then verify (and patch if needed) that `_prune_with_visit_check` in `src/check_unprotected_keys/adapters/filesystem.py` correctly catches `OSError` for broken/inaccessible link targets, appends a `DiscoveryIssue` to `issues` when provided, and logs at DEBUG; confirm the existing `onerror` callback in `discover_candidate_files` records issues for walk-level permission errors
- [X] T028 [US3] Run `pytest tests/integration/test_symlink_traversal.py` and confirm all US3 tests pass; triage any failure before changing test or code

**Checkpoint**: Broken and inaccessible links are silently skipped. All US1, US2, and US3 acceptance scenarios pass.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Full quality gate sweep and user-facing documentation.

- [X] T029 [P] Run `pytest` (full suite including existing contract, integration, and unit tests) and verify coverage stays ≥ 85% with branch coverage; triage any failing test — determine whether the test's expectation or the implementation's logic is incorrect, record that conclusion, then fix the appropriate side
- [X] T030 [P] Run `ruff check src/ tests/`, `ruff format --check src/ tests/`, and `pyright src/`; fix all issues reported (do not skip or suppress without justification)
- [X] T031 Run the six manual validation scenarios in `specs/006-symlink-safe-traversal/quickstart.md` against the installed package (`pip install -e ".[dev]"`) to confirm end-to-end behavior matches expectations
- [X] T032 Add one-line entry to `CHANGELOG.md` (or `README.md` "What's new" section) noting that the scanner now follows symbolic links and handles cycles automatically

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 2)**: Depends on Phase 1 complete — BLOCKS phases 3 and 4
- **US2 (Phase 3)**: Depends on Phase 2 complete (tracker is wired, now add error handling and cycle tests)
- **US3 (Phase 4)**: Can start after Phase 1 complete; T025–T026 tests can be written in parallel with Phase 2/3 implementation; T027 requires Phase 2 implementation to be in place
- **Polish (Phase 5)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 1); no dependency on US2 or US3
- **US2 (P1)**: Shares the implementation work with US1 (tracker already wired); Phase 3 adds error-handling wiring and cycle-specific tests
- **US3 (P2)**: Broken-link handling is implemented as part of `_prune_with_visit_check` (Foundational + US1); Phase 4 adds tests and verifies correctness

### Within Each User Story

1. Write tests → confirm they fail
2. Implement (models before services, helpers before callers)
3. Run tests → triage any failure (test logic vs. implementation logic) → fix the correct side
4. Coverage stays ≥ 85%

---

## Parallel Opportunities

```bash
# Phase 1: run all [P] tasks together
T001 Add max_directory_visits to config/models.py
T002 Add max_directory_visits to domain/models.py
T005 Define DirectoryLimitExceededError in filesystem.py
# T003, T004, T006, T007, T008 depend on T001/T002 or each other — run sequentially

# Phase 2 tests: run all [P] test-writing tasks together
T009 Write VisitedDirectoryTracker unit tests
T010 Write US1 integration tests

# Phase 3 tests: run all [P] test-writing tasks together
T017 Write US2 cycle integration tests
T018 Write VisitedDirectoryTracker hard-cap unit tests
T019 Write FR-013 limit-exceeded integration test

# Phase 4 tests: run all [P] test-writing tasks together
T025 Write US3 broken/inaccessible link tests
T026 Write ignored-name via link edge case test

# Phase 5: run all [P] quality tasks together
T029 Full pytest + coverage
T030 ruff + pyright
```

---

## Parallel Example: User Story 1

```bash
# Write all US1 test files together (different files, no implementation dependencies):
Task T009: "Write VisitedDirectoryTracker unit tests in tests/unit/test_visited_directory_tracker.py"
Task T010: "Write US1 symlink integration tests in tests/integration/test_symlink_traversal.py"

# Then implement traversal changes (T012–T013 touch different parts of filesystem.py but
# the same file — run sequentially; T014 and T015 touch different files — run in parallel):
Task T014: "Add visited_tracker param to resolve_effective_scope in adapters/filesystem.py"
Task T015: "Wire VisitedDirectoryTracker in ScanService.run() in services/scan_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Foundational (T001–T008)
2. Complete Phase 2: User Story 1 (T009–T016)
3. **STOP and VALIDATE**: Run `pytest tests/integration/test_symlink_traversal.py` and manual Scenario 1 from quickstart.md
4. Symlinks followed, keys discovered — this is the headline value (SC-001)

### Incremental Delivery

1. Foundational (Phase 1) → nothing observable yet
2. US1 (Phase 2) → symlinks followed; MVP deliverable ✅
3. US2 (Phase 3) → cycle protection observable; tests for all edge cases green ✅
4. US3 (Phase 4) → broken links skipped gracefully ✅
5. Polish (Phase 5) → full coverage gate, all quality checks pass ✅

---

## Notes

- `[P]` tasks operate on different files or have no incomplete predecessors
- `[Story]` label maps each task to its user story for traceability
- Always confirm tests fail **before** implementing; never implement to fix a test
  without first determining whether the test's expectation was wrong
- After implementation, run the full suite and coverage report; triage failures as
  (test logic vs. implementation logic) and record conclusion before touching anything
- Code must satisfy SOLID, Clean Code, DRY, and KISS per the project constitution
- The `_prune_with_visit_check` helper eliminates duplicated `dirnames` pruning logic —
  do not inline the pattern in both walk sites
