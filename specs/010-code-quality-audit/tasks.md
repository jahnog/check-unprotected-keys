# Tasks: Code Quality Audit — Errors, Maintainability, Expandability, Testability

**Input**: Design documents from `/specs/010-code-quality-audit/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Unit test and coverage tasks are REQUIRED for every user story.
This feature is refactor-heavy, so characterization/regression tests are
written FIRST (Foundational phase) and gate every later task (SC-002).

**Organization**: Tasks are grouped by user story. Story 0 (the detailed
implementation plan, FR-014–FR-016) is already satisfied by `plan.md` and its
traceability map; Phase 2 verifies that gate.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project: `src/check_unprotected_keys/`, `tests/` at repository root
(per plan.md Project Structure).

---

## Phase 1: Setup

**Purpose**: Branch and environment readiness (no scaffolding needed — the
project structure already exists)

- [X] T001 Create the Git Flow feature branch from `develop` with `git flow feature start code-quality-audit` (the ONLY permitted git automation; all commits/PRs remain manual per constitution VI). Note: speckit scripts don't recognize `feature/*` branch names — rely on `.specify/feature.json` or `SPECIFY_FEATURE=010-code-quality-audit` for later speckit commands
- [X] T002 Verify the dev environment and record the pre-feature baseline: run `pytest`, `ruff check .`, `ruff format --check .`, `pyright`; note the overall coverage percentage AND the per-module coverage rows for `services/scan_service.py` and `adapters/key_parsers.py` (reference values for SC-004/SC-006 and T022/T027)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Safeguards that protect every refactor — plan.md WI-1/WI-2 —
plus the Story 0 gate check

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Confirm the Story 0 gate (FR-014–FR-016): plan.md's "Audit Findings → Remediation Map" covers FR-001–FR-013 with verification methods and the Constitution Check passes; record confirmation in specs/010-code-quality-audit/tasks.md notes
- [X] T004 [P] Tighten golden regression assertions (WI-1): make integration tests assert full stdout findings (content + order) and stable stderr summary lines in tests/integration/test_default_scan_workflow.py, tests/integration/test_properties_scan_workflow.py, and tests/integration/test_start_folder_scan.py
- [X] T005 [P] Write characterization unit tests for every current key-format path (WI-2, FR-008): valid/encrypted/malformed/truncated PEM, OpenSSH, PuTTY, public-key, and certificate inputs in tests/unit/test_key_parsers.py (against CURRENT code — must pass before any refactor)
- [X] T006 Run `pytest` to confirm T004–T005 pass against unchanged code and coverage stays ≥85% (baseline lock)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Silent failures become observable (Priority: P1) 🎯 MVP

**Goal**: Every location the scan cannot inspect is reported with path,
reason, and phase; a limit-aborted scan keeps its partial results; lossy
decoding never silently downgrades a real key to MALFORMED (WI-3, WI-5 /
FR-001, FR-002, FR-012)

**Independent Test**: Scan a tree containing an unreadable directory and an
unreadable file → scan completes, stderr lists each skipped location with a
reason; clean tree → zero warnings (quickstart.md §3)

### Tests for User Story 1 (REQUIRED) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T007 [P] [US1] Unit tests for SkippedLocation/SkipPhase model and ScanResult.record_skip in tests/unit/test_skipped_location_reporting.py (model shape, error_summaries consistency, reporting lines sorted by path, zero-warning clean case)
- [X] T008 [P] [US1] Unit tests for promotion-pass issue threading in tests/unit/test_filesystem_ignore_patterns.py (unreadable base/hint dir during _discover_promoted_directories yields a DiscoveryIssue instead of silent continue)
- [X] T009 [P] [US1] Unit tests for lossy-decode honesty in tests/unit/test_key_parsers.py (invalid-UTF-8 key bytes: parseable-UNPROTECTED still reported; unparseable-lossy classifies as uncertain skip `undecodable-content`, never MALFORMED)
- [X] T010 [P] [US1] Integration test in tests/integration/test_unreadable_tree_scan.py (fault injection: N unreadable locations → exactly N `WARNING: skipped` lines; SC-001)
- [X] T011 [P] [US1] Contract test in tests/contract/test_cli_skip_warnings_contract.py per contracts/cli-output.md (warning line format, stdout untouched, dangling .properties reference case, limit-abort partial results: finding on stdout + `NOTE:` line + exit 2)
- [X] T012 [US1] Extend tests/contract/test_cli_default_scan_contract.py to assert zero `WARNING: skipped` lines on the clean fixture tree

### Implementation for User Story 1

- [X] T013 [US1] Add SkippedLocation frozen dataclass, SkipPhase StrEnum, ScanResult.skipped_locations field, and record_skip() method in src/check_unprotected_keys/domain/models.py (per data-model.md)
- [X] T014 [US1] Thread DiscoveryIssue collection through _discover_promoted_directories and its _prune_with_visit_check call in src/check_unprotected_keys/adapters/filesystem.py, returning issues to the caller (A2)
- [X] T015 [US1] In src/check_unprotected_keys/services/scan_service.py convert every DiscoveryIssue (scope resolution, promotion, discovery) into SkippedLocation via record_skip instead of dropping paths at the record_unreadable(issue.error_type) call (A1)
- [X] T016 [US1] Preserve partial results on DirectoryLimitExceededError in src/check_unprotected_keys/services/scan_service.py: catch the error, set directory_limit_exceeded, and continue assessing candidates discovered before the abort (A3, FR-002; discovery returns partial lists per research.md R4)
- [X] T017 [US1] Record unresolvable .properties key-file references as SkippedLocation (phase REFERENCE_FOLLOW) in src/check_unprotected_keys/adapters/properties_inspector.py _follow_reference (A4)
- [X] T018 [US1] Emit `WARNING: skipped <path> (<reason>, during <phase>)` lines (sorted by path, after issue summary) and the limit-abort `NOTE: Partial results…` line in src/check_unprotected_keys/adapters/reporting.py per contracts/cli-output.md
- [X] T019 [US1] Implement lossy-decode honesty (WI-5, FR-012) in src/check_unprotected_keys/adapters/key_parsers.py: strict-UTF-8-first decode with lossy flag; lossy+unparseable → uncertain skip, not MALFORMED; document the intentional latin-1 fallback in src/check_unprotected_keys/adapters/properties_inspector.py _decode
- [X] T020 [US1] Run full `pytest` + coverage; triage any failure (test logic vs. implementation logic), record the conclusion, then fix; confirm golden baselines (T004) still pass

**Checkpoint**: User Story 1 fully functional — MVP deliverable (observable
scans)

---

## Phase 4: User Story 3 - Core orchestration and parsers are directly unit-testable (Priority: P3, executed early per plan sequencing) 

**Goal**: ScanService depends on Protocol seams with injectable fakes; its
limit/error branches are unit-tested without a real filesystem (WI-4 /
FR-007; FR-008 was satisfied by T005/T009)

**Independent Test**: `pytest tests/unit/test_scan_service_orchestration.py`
drives limit/malformed/unreadable branches with in-memory fakes
(quickstart.md §6)

> Executed before US2 because plan.md sequencing (WI-4 before WI-6/7/8) uses
> these seams to prove the registry refactors; spec priority labels are
> unchanged.

### Tests for User Story 3 (REQUIRED) ⚠️

- [X] T021 [P] [US3] Unit tests with in-memory fakes in tests/unit/test_scan_service_orchestration.py: directory-limit mid-stream (partial results kept), malformed/unreadable/clean state transitions, skip conversion, properties-candidate routing — written against the Protocol seams and FAILING first
- [X] T022 [US3] Coverage check task: assert scan_service.py branch coverage rises above the T002 baseline in the coverage report

### Implementation for User Story 3

- [X] T023 [P] [US3] Create Protocol seams ScopeResolver, CandidateDiscoverer, KeyInspector, PropertiesInspector in src/check_unprotected_keys/services/ports.py (per data-model.md)
- [X] T024 [US3] Refactor ScanService to injected dataclass fields with production defaults wrapping existing adapter functions in src/check_unprotected_keys/services/scan_service.py (`ScanService()` stays valid; CLI untouched)
- [X] T025 [US3] Run full `pytest` + coverage; triage failures (test vs. implementation logic, record conclusion); confirm golden baselines pass

**Checkpoint**: Orchestrator provable with fakes; registry refactors now
cheap to verify

---

## Phase 5: User Story 2 - New detection capability plugs in without editing stable code (Priority: P2)

**Goal**: Key-format recognizers, usage categories, and properties assessment
rules become ordered registries; adding a detector touches only its own unit
plus a registry entry (WI-6, WI-7, WI-8 / FR-004, FR-005, FR-006)

**Independent Test**: Registry demo test adds a dummy recognizer via the
registry only, verifies it participates in a scan, removes it, and verifies
baseline — zero modified lines in existing detection units (SC-003,
quickstart.md §5)

### Tests for User Story 2 (REQUIRED) ⚠️

- [X] T026 [P] [US2] Registry invariants + SC-003 demo tests in tests/unit/test_detection_registries.py: KEY_RECOGNIZERS first-match order per contracts/extension-points.md; every UsageCategory member defined exactly once with complete remediation; ASSESSMENT_RULES order equals documented steps; dummy-recognizer add/remove round-trip
- [X] T027 [US2] Coverage check task: registries and lookup paths covered; suite coverage ≥85%

### Implementation for User Story 2

- [X] T028 [US2] Convert _inspect_key_blob if/elif chain to KeyRecognizer entries and ordered KEY_RECOGNIZERS tuple in src/check_unprotected_keys/adapters/key_parsers.py, preserving exact precedence (A6; protected by T005)
- [X] T029 [P] [US2] Create UsageCategoryDefinition registry in src/check_unprotected_keys/domain/remediation.py, moving infer_usage_category match rules and build_remediation_recommendation prose verbatim from scan_service.py (A7; UNKNOWN as final catch-all)
- [X] T030 [US2] Replace infer_usage_category and build_remediation_recommendation bodies in src/check_unprotected_keys/services/scan_service.py with table lookups over USAGE_CATEGORY_DEFINITIONS (keep public function names for reporting/tests compatibility)
- [X] T031 [US2] Convert _assess_entry steps 1–7 into ordered AssessmentRule registry (AssessmentContext, RuleOutcome) in src/check_unprotected_keys/adapters/properties_inspector.py, preserving short-circuit semantics (A8; protected by properties corpus + T004)
- [X] T032 [US2] Run full `pytest` + coverage; triage failures (test vs. implementation logic, record conclusion); confirm golden baselines and remediation-text regression pass

**Checkpoint**: All three extension points live; Stories 1–3 remain green

---

## Phase 6: User Story 4 - Oversized and duplicated internals are consolidated (Priority: P4)

**Goal**: properties.py split into a cohesive package with data separated
from logic; directory-limit default single-sourced; loader duplication and
mirror type removed; unreachable candidate state removed (WI-9–WI-12 /
FR-009, FR-010, FR-011, FR-013)

**Independent Test**: `grep -rn "100_000" src/` returns exactly one hit;
regression suite passes with identical scan results; no production module
exceeds ~400 lines (quickstart.md §6–7)

### Tests for User Story 4 (REQUIRED) ⚠️

- [X] T033 [P] [US4] Single-source default test in tests/unit/test_config_loader.py: monkeypatch DEFAULT_MAX_DIRECTORY_VISITS and assert loader default and VisitedDirectoryTracker limit follow (SC-005)
- [X] T034 [P] [US4] Import-compatibility test in tests/unit/test_properties_parsing.py: all current public names importable from check_unprotected_keys.domain.properties after the package split

### Implementation for User Story 4

- [X] T035 [US4] Single-source the traversal default (WI-9): add DEFAULT_MAX_DIRECTORY_VISITS to src/check_unprotected_keys/domain/models.py; reference it from src/check_unprotected_keys/config/loader.py; make the tracker argument required and delete the 100_000 fallback in src/check_unprotected_keys/adapters/filesystem.py discover_candidate_files (A11)
- [X] T036 [US4] Split src/check_unprotected_keys/domain/properties.py into package src/check_unprotected_keys/domain/properties/{__init__,parser,tiers,signatures,shapes,bundles,reference_data}.py with API-preserving __init__.py re-exports; pure move, no logic edits (A12, WI-10; each module ≤400 lines)
- [X] T037 [US4] Consolidate config loading (WI-11): merge _validate_patterns/_validate_optional_patterns into one `required: bool` helper and build SearchConfiguration directly, deleting ScanConfigSection from src/check_unprotected_keys/config/models.py and its copy loop in src/check_unprotected_keys/config/loader.py (A13)
- [X] T038 [US4] Remove CandidateState.DUPLICATE_SKIPPED and document the remaining state machine in src/check_unprotected_keys/domain/models.py; confirm no references via pyright/grep (A14, WI-12)
- [X] T039 [US4] Run full `pytest` + coverage; triage failures (test vs. implementation logic, record conclusion); confirm golden baselines byte-identical (SC-002)

**Checkpoint**: All four user stories independently verified

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, final gates, packaging smoke, success-criteria
sign-off

- [X] T040 [P] Document the new `WARNING: skipped`/`NOTE:` stderr output and exit-code semantics in README.md (NFR-004 scope: docs only)
- [X] T041 [P] Module-size sweep: `wc -l` over src/check_unprotected_keys — no production module over 400 physical lines (SC-004); split further if any exceeds
- [X] T042 Run the full unit-test suite and coverage report; triage any failing test (test logic vs. implementation logic), record the conclusion, and only then fix the test or the code (constitution III)
- [X] T043 [P] Run `ruff check .`, `ruff format --check .`, `pyright` — all clean (SC-006)
- [X] T044 [P] Build and smoke-test the standalone executable: `pyinstaller --onefile --name check-unprotected-keys src/check_unprotected_keys/__main__.py && ./dist/check-unprotected-keys --help` (NFR-004 unchanged-packaging proof)
- [X] T045 Execute quickstart.md scenarios 1–8 end-to-end and check off SC-001…SC-007 against specs/010-code-quality-audit/spec.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately
- **Foundational (Phase 2)**: after Setup — BLOCKS all user stories (golden
  baseline + parser characterization protect every refactor)
- **User stories**: all depend on Phase 2. Recommended execution order per
  plan.md WI sequencing: **US1 (Phase 3) → US3 (Phase 4) → US2 (Phase 5) →
  US4 (Phase 6)** — safeguards and seams land before the refactors they
  protect. Spec priorities (P1–P4) are unaffected; each story remains
  independently testable.
- **Polish (Phase 7)**: after all desired stories

### User Story Dependencies

- **US1**: only Phase 2. Note T019 (lossy decode) touches key_parsers.py —
  coordinate with US2's T028 if run in parallel (same file).
- **US3**: only Phase 2; independent of US1 (different branches of
  scan_service.py — if run concurrently with US1, land T015/T016 first).
- **US2**: Phase 2 required; T005 characterization tests gate T028; US3's
  seams (T023–T024) make T032 verification cheaper but are not a hard
  dependency.
- **US4**: Phase 2 required; safest last (T036 pure move relies on the full
  strengthened suite).

### Within Each User Story

- Tests first, failing, then implementation; models before services before
  reporting; full suite + coverage + triage recording closes every story
  (T020, T025, T032, T039).

### Parallel Opportunities

- Phase 2: T004 ∥ T005 (different files)
- US1 tests: T007–T011 all [P]; implementation T013 → {T014, T017} ∥, then
  T015 → T016 → T018 → T019
- US3: T021 ∥ T023, then T024
- US2: T026 first; T029 [P] with T028; T030 after T029; T031 independent of
  T028–T030
- US4: T033 ∥ T034; T035–T038 sequential-ish (T036 alone is a large move);
  Polish: T040, T041, T043, T044 all [P] after T042

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (write first, watch them fail):
Task: "Unit tests for SkippedLocation reporting in tests/unit/test_skipped_location_reporting.py"
Task: "Promotion-pass issue tests in tests/unit/test_filesystem_ignore_patterns.py"
Task: "Lossy-decode tests in tests/unit/test_key_parsers.py"
Task: "Fault-injection integration test in tests/integration/test_unreadable_tree_scan.py"
Task: "Skip-warnings contract test in tests/contract/test_cli_skip_warnings_contract.py"

# Then implement models before plumbing:
Task: "SkippedLocation + SkipPhase + record_skip in src/check_unprotected_keys/domain/models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → Phase 2 Foundational (CRITICAL — the baseline is the
   safety net for everything)
2. Phase 3: User Story 1
3. **STOP and VALIDATE**: quickstart §3 fault-injection scenario; clean tree
   emits zero warnings; golden stdout identical
4. This alone ships the trust fix (no more silent skips)

### Incremental Delivery

1. Setup + Foundational → baseline locked
2. US1 → observable scans (MVP)
3. US3 → injectable seams + orchestrator tests
4. US2 → three registry extension points (SC-003 demo green)
5. US4 → consolidation on top of the strengthened suite
6. Polish → docs, gates, packaging smoke, SC sign-off

### Parallel Team Strategy

Single-maintainer repo: sequential order above is recommended. With two
developers, after Phase 2 one can take US1 (reporting chain) while the other
takes US3 (service seams); US2/US4 then proceed sequentially because they
touch the same files as US1/US3.

---

## Notes

### Execution log

- **T002 baseline (2026-07-08)**: pytest 324 passed, total coverage 93.08%
  (branch); per-module: `services/scan_service.py` 96% (3 missed stmts),
  `adapters/key_parsers.py` 88% (14 missed stmts),
  `domain/properties.py` 97%. `ruff check` clean; `ruff format --check`
  clean (55 files). `pyright`: 42 pre-existing errors, all in tests
  (loose helper return types) — gate for this feature is "no new errors".
- **T003 Story-0 gate (FR-014–FR-016) confirmed**: plan.md maps A1–A14 to
  WI-1–WI-13 covering FR-001–FR-013, each row with a verification method;
  sequencing places safeguards (WI-1/WI-2) first; Constitution Check passes
  pre-Phase-0 and post-Phase-1 with an empty Complexity Tracking table.

- **Final gates (2026-07-08, all 45 tasks done)**: pytest 382 passed (58 new
  tests), total coverage 95.18% branch (baseline 93.08%); `scan_service.py`
  99%, `key_parsers.py` covered directly per format. `ruff check` and
  `ruff format --check` clean. `pyright` 30 errors, all pre-existing in
  untouched test files (baseline was 42 — this feature removed 12, added 0).
  Largest production module 388 lines (limit 400). PyInstaller onefile binary
  built and smoke-tested (`--help`, `--version`, live fault-injection scan:
  1 finding on stdout, 1 `WARNING: skipped … PermissionError …`, exit 1).
  No test-failure triage was needed: no test failed unexpectedly during
  implementation (new tests failed before their implementation as required,
  then passed; golden baselines never broke).
- **Deviation note (T035)**: the `discover_candidate_files` tracker parameter
  stayed optional (its fallback now reads `DEFAULT_MAX_DIRECTORY_VISITS`)
  instead of becoming required, because 6 existing test call sites use the
  no-tracker form; FR-009's single-source requirement is met and tested.
- **Deviation note (T031)**: the rule registry has 8 entries, not 7 — the
  original pipeline's tier gate became its own `tier-gate` rule (it must sit
  between `placeholder-default` and `reference-follow`);
  contracts/extension-points.md was updated accordingly.

### General

- [P] tasks = different files, no dependencies
- Golden baselines (T004) are the SC-002 oracle — never weaken them to make a
  refactor pass; a diff there is a defect until triaged
- Story 0 (FR-014–FR-016) is satisfied by plan.md; T003 records the gate check
- All commits and the PR are manual (constitution VI); stop at any checkpoint
  to validate the story independently
- Code MUST satisfy SOLID, Clean Code, DRY, and KISS; no new dependencies
