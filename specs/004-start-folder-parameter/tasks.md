# Tasks: Start Folder Parameter

**Input**: Design documents from `/specs/004-start-folder-parameter/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/start-folder-validation.md, quickstart.md

**Tests**: Unit test and coverage tasks are REQUIRED for every user story per the tasks template and because the feature specification (FR-006, NFR-002, User Story 4, SC-004) explicitly mandates dedicated unit tests for the start-folder parameter states. Integration/contract tests already exist for end-to-end behavior and are leveraged for verification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. Note that the core production behavior (resolve_start_folder in domain/scope.py and its use in cli.py) is pre-existing and correct per research.md. The primary implementation work is additive unit tests + verification that the four states (passed, omitted, valid, invalid) work as specified.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., [US1], [US2], [US3], [US4])
- Include exact file paths in descriptions

## Path Conventions

Single project layout (per plan.md and project structure):
- Source: `src/check_unprotected_keys/domain/scope.py`, `src/check_unprotected_keys/cli.py`, `src/check_unprotected_keys/adapters/filesystem.py`
- Tests: `tests/unit/test_scope_resolution.py` (extend), `tests/contract/test_cli_start_folder_contract.py` (existing), `tests/support/fixture_builders.py` (existing patterns)
- Docs: `specs/004-start-folder-parameter/*.md` and contracts/ (already generated in planning phase)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm project readiness (structure, tooling, and design artifacts from prior /speckit-plan are in place). The project is already fully initialized; these tasks are lightweight confirmations.

- [x] T001 Review plan.md, research.md, and project structure to confirm Python 3.12 + pytest-cov (>=85% branch), layered architecture (cli -> domain/scope), and that no production source changes are required
- [x] T002 [P] Run `uv sync --extra dev` from repository root and confirm dev tools (pytest, ruff, pyright, coverage) are available and the quality gate commands from plan.md execute without error
- [x] T003 [P] Confirm that `specs/004-start-folder-parameter/` contains the required design artifacts (plan.md, research.md, data-model.md, quickstart.md, contracts/start-folder-validation.md) and that .specify/feature.json points to this feature directory

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core test-module and support preparation that MUST be complete before user story test and verification work. These are small and enable all subsequent stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add the import for `resolve_start_folder` (and keep existing imports) in `tests/unit/test_scope_resolution.py` so the new validation tests can directly exercise the function under test from `check_unprotected_keys.domain.scope`
- [x] T005 [P] Review `tests/support/fixture_builders.py` (especially ScanWorkspace.restore_permissions and unreadable_key patterns) and confirm the chmod + restore approach is usable for a "not readable" directory test under tmp_path (per research.md decision)
- [x] T006 [P] Read `specs/004-start-folder-parameter/contracts/start-folder-validation.md` and confirm the exact success/error contract (return None or resolved Path; three specific ValueError messages) that the new unit tests must assert
- [x] T007 Confirm that the existing `test_scope_resolution.py` module docstring and structure can accommodate a new section of `resolve_start_folder` tests without breaking current narrowing tests (no file rename or major refactor)

**Checkpoint**: Foundation ready - user story implementation (primarily test additions and verifications) can now begin in parallel

---

## Phase 3: User Story 1 - Narrow Search Scope via Start Folder (Priority: P1) 🎯

**Goal**: Verify (and document via tests/quickstart) that passing a valid optional start-folder parameter on the command line causes the search to launch scoped to (only under) that starting folder and its subtree, while filename patterns remain unchanged (per spec US1 acceptance scenarios and data-model).

**Independent Test**: Prepare (or use existing fixture) a workspace with configured folders containing findings both inside and outside a chosen subtree; invoke the tool (or run the relevant contract test) supplying the start-folder for the subtree only; verify that only findings under the supplied folder are reported and that the behavior matches the contract.

### Tests for User Story 1 (REQUIRED)

> **NOTE: Write/verify these tests FIRST, ensure the relevant contract and unit scenarios demonstrate the narrowing before considering the story complete**

- [x] T008 [P] [US1] Execute and verify the existing contract test `tests/contract/test_cli_start_folder_contract.py::test_cli_start_folder_reports_only_findings_under_the_requested_subtree` (and the absolute path variant) passes and demonstrates narrowed findings with unchanged filename patterns
- [x] T009 [P] [US1] After unit tests from US4 are present, run `pytest tests/unit/test_scope_resolution.py -q -k "resolve_start_folder"` (or the full module) and confirm the "valid passed" cases contribute to coverage of the happy-path resolution + narrowing flow used by this story
- [x] T010 [US1] Run the relevant portion of quickstart.md Scenario 2 (or the full start-folder contract module) and confirm it exercises the "narrow scope" behavior for this user story

### Implementation / Verification for User Story 1

- [x] T011 [P] [US1] Inspect (no modification) `src/check_unprotected_keys/domain/scope.py` (resolve_start_folder + narrow_root_directories) and `src/check_unprotected_keys/cli.py` (the call site) and confirm they implement the "launches search from the supplied start folder" behavior exactly as described in spec US1 and data-model.md (per research.md: zero production changes required)
- [x] T012 [US1] Cross-reference quickstart.md and data-model.md to ensure the "narrowed Effective Search Scope" and "passed valid" state are clearly linked to this user story's acceptance scenarios; make minimal clarifying edits only if the references are stale
- [x] T013 [US1] Confirm that the start-folder contract in `specs/001-check-unprotected-keys/contracts/cli-contract.md` (the --start-folder section) plus the focused `contracts/start-folder-validation.md` together fully describe the input/output for this story

**Checkpoint**: At this point, User Story 1 should be fully verifiable and testable independently (via contract tests + the new unit coverage from US4)

---

## Phase 4: User Story 2 - Default Behavior When Parameter Omitted (Priority: P1)

**Goal**: Verify that when the start-folder parameter is omitted the search launches over the entire configured scope exactly as before (full default behavior, identical findings/exit codes/output to the pre-existing unrestricted scan).

**Independent Test**: Run the identical configured scan once with the parameter omitted (default) and once with an explicit start-folder that encompasses the full scope; confirm identical findings, counts, exit codes, and output structure (per spec US2).

### Tests for User Story 2 (REQUIRED)

- [ ] T014 [P] [US2] Execute and verify the existing default-scan contract tests in `tests/contract/test_cli_default_scan_contract.py` (especially the ones that call `main([])` with no --start-folder) pass and produce the expected full-scope results
- [x] T015 [P] [US2] After the omitted-case unit test from US4 is added, run the unit tests with `-k "resolve_start_folder"` and confirm the omitted (None) path is covered and that downstream resolve_effective_scope with start_folder=None produces the full set of roots
- [x] T016 [US2] Run quickstart.md Scenario 2 (default scan portions) and the full default contract module to confirm omitted behavior matches the established unrestricted scan

### Implementation / Verification for User Story 2

- [x] T017 [P] [US2] Confirm (via code inspection, no changes) that `resolve_start_folder(execution_root, None)` returning None leads to the full configured scope in `resolve_effective_scope` / `narrow_root_directories` (as required by spec US2 and the "omitted" guarantee in contracts/start-folder-validation.md)
- [x] T018 [US2] Ensure quickstart.md Scenario 1 and Scenario 2 explicitly call out the "parameter omitted" case and that it is satisfied by the new unit test coverage
- [x] T019 [US2] Verify that ScanRequest.start_folder=None (the carrier from data-model.md) is exercised in the default path of cli.main and the scan service

**Checkpoint**: At this point, User Stories 1 AND 2 (the P1 behaviors) should both be independently verifiable

---

## Phase 5: User Story 3 - Error on Invalid Start Folder Value (Priority: P2)

**Goal**: Verify that the tool rejects an invalid start-folder value (does not exist, is not a directory, or is not readable) with a clear error, exit code 2, no findings on stdout, and no search work performed (fail-fast before config load or scanning).

**Independent Test**: Invoke the CLI (or run the contract test) supplying a non-existent path, a regular file as the "folder", and (where possible) an unreadable directory; verify error exit, diagnostic on stderr containing the exact message, empty stdout, and that scanning logic is never reached (per spec US3 and the error contract).

### Tests for User Story 3 (REQUIRED)

- [ ] T020 [P] [US3] Execute and verify the existing contract test `tests/contract/test_cli_start_folder_contract.py::test_cli_start_folder_returns_exit_code_two_for_invalid_paths` (non-existent case) passes with exit 2, empty stdout, and the expected "does not exist" message on stderr
- [x] T021 [P] [US3] After the invalid-case unit tests from US4 are added (including the not-readable chmod case), run `pytest ... -k "resolve_start_folder"` and confirm the three error paths (does not exist, not a directory, not readable) plus exact message assertions are covered at unit level
- [x] T022 [US3] Run quickstart.md Scenario 3 (the invalid manual or contract invocations) and confirm all three classes of invalid input produce the documented fast error with no scan side effects

### Implementation / Verification for User Story 3

- [x] T023 [P] [US3] Confirm (inspection only) that the three ValueError paths in `src/check_unprotected_keys/domain/scope.py:resolve_start_folder` (the exact messages from contracts/start-folder-validation.md) plus the catch in `cli.py` (turn into emit_error + return 2) fully satisfy the "fail fast, clear error, no search" acceptance scenarios for this story
- [x] T024 [US3] Verify that the unreadable error case (the one requiring real FS chmod + restore) is exercised by the new unit test and that the quickstart/contract tests cover at least the non-existent and not-a-directory cases
- [x] T025 [US3] Cross-check data-model.md "Validation Result for Start Folder" and the error outcomes against the actual raised messages to ensure consistency (no code changes)

**Checkpoint**: At this point, User Story 3 (invalid handling) is independently verifiable via contract + the dedicated unit tests

---

## Phase 6: User Story 4 - Explicit Unit Test Coverage of Parameter States (Priority: P2)

**Goal**: Deliver dedicated, executable unit tests (in the unit test suite, not just contract/integration) that explicitly cover the start-folder parameter for the four states: passed (with value), omitted, value is valid, and value is invalid. These tests must be isolated, fast, and directly assert the contract from contracts/start-folder-validation.md (per spec US4, FR-006, NFR-002, SC-004, research.md, and constitution requirement for unit tests on new/changed behavior).

**Independent Test**: Execute *only* the unit tests written for start-folder parameter handling (e.g. `pytest tests/unit/test_scope_resolution.py -q -k "resolve_start_folder"`); observe that tests for each of the four combinations exist, are isolated from full CLI/scan, pass, and contribute positively to coverage metrics for the validation logic.

### Tests for User Story 4 (REQUIRED) ⚠️

> **NOTE: Add these unit tests so they exercise resolve_start_folder directly. They can be developed in parallel with verification work in earlier stories once Phase 2 is complete. Write the test functions; they will initially be the "implementation" that makes the verification possible.**

- [x] T026 [P] [US4] Add `test_resolve_start_folder_omitted_returns_none` to `tests/unit/test_scope_resolution.py`: call `resolve_start_folder(execution_root, None)`, assert the result is exactly `None` with no exception raised. Import `resolve_start_folder` from `check_unprotected_keys.domain.scope`.
- [x] T027 [P] [US4] Add `test_resolve_start_folder_accepts_valid_relative` (and a companion for absolute) to `tests/unit/test_scope_resolution.py`: under a tmp_path, create a readable directory tree, call resolve_start_folder with a relative path (and separately an absolute path), assert the returned Path is resolved/absolute, exists, and is_dir().
- [x] T028 [US4] Add the three invalid tests to `tests/unit/test_scope_resolution.py`:
  - `test_resolve_start_folder_raises_for_nonexistent_path` (assert ValueError message contains "Start folder does not exist")
  - `test_resolve_start_folder_raises_for_file_instead_of_directory` (point at a file, assert "is not a directory")
  - `test_resolve_start_folder_raises_for_unreadable_directory` (create subdir under tmp_path, chmod to remove read, call resolve, assert "is not readable"; use try/finally or equivalent to restore permissions so tmp cleanup succeeds; mark xfail/skip on Windows if needed for permission semantics)
- [x] T029 [P] [US4] Update the module docstring at the top of `tests/unit/test_scope_resolution.py` to mention that it now also contains direct unit tests for `resolve_start_folder` validation (the four states).
- [x] T030 [P] [US4] Run the new tests in complete isolation (`uv run --extra dev pytest tests/unit/test_scope_resolution.py -q -k "resolve_start_folder" --tb=short`) and confirm all pass with the expected exact messages and return values.
- [x] T031 [US4] Run the full unit test module with coverage and confirm the new tests increase (or at minimum do not regress) coverage of `src/check_unprotected_keys/domain/scope.py` (especially the resolve_start_folder branches) while the overall suite still meets the 85% --cov-fail-under gate.

### Implementation / Verification for User Story 4

- [x] T032 [US4] Confirm that the added unit tests (and only the unit tests) satisfy the "dedicated, executable unit tests" requirement of spec US4 / FR-006 without relying on contract or integration tests for the core validation logic (per research.md decision to keep CLI coverage in existing contract tests).
- [x] T033 [US4] Verify that the tests follow the contract exactly (inputs: execution_root + raw str|None; outputs: Path|None or the three documented ValueError messages) as described in contracts/start-folder-validation.md and data-model.md "Validation Result for Start Folder".
- [x] T034 [US4] Ensure the unreadable test uses real os.access (no monkeypatch of os.access) per the research decision, and that the restore pattern prevents test pollution.

**Checkpoint**: At this point, User Story 4 (the explicit unit test coverage for all four states) is complete, independently runnable, and provides the unit-level proof for the behaviors in US1–US3.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, quality gates, coverage close-out, and documentation that affect the whole feature. Run after the desired user stories are complete.

- [x] T035 [P] Run the full project quality gates exactly as documented in plan.md: `uv run --extra dev ruff check . && uv run --extra dev ruff format --check . && uv run --extra dev pyright . && uv run --extra dev pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85`
- [x] T036 [P] Execute the runnable scenarios from `specs/004-start-folder-parameter/quickstart.md` (especially Scenario 1 for the new unit tests, Scenario 3 for invalid cases) and confirm they all pass now that the unit tests exist.
- [x] T037 Run the start-folder-specific contract and integration tests (`pytest tests/contract/test_cli_start_folder_contract.py tests/integration/test_start_folder_scan.py -q`) to confirm end-to-end behavior remains green.
- [x] T038 [P] Review overall coverage report for `src/check_unprotected_keys/domain/scope.py` and `cli.py`; if any new gaps were introduced by the feature work, add the minimal additional unit assertions (prefer staying inside the existing test_scope_resolution.py module).
- [x] T039 [P] Run a full `uv run --extra dev pytest` (or the CI-equivalent) one final time and confirm no regressions in unrelated tests and that the 85% gate still passes.
- [x] T040 Update any stale cross-references in quickstart.md, data-model.md, or the contracts file if the unit test names or exact messages drifted during implementation (keep changes minimal).
- [x] T041 [P] (Optional but recommended) Commit the completed work with a message referencing the feature branch and the primary user stories verified.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories (the import and support confirmation are prerequisites for writing the new tests).
- **User Stories (Phases 3–6)**: All depend on Foundational phase completion. User stories can then proceed in parallel (if staffed) or sequentially in priority order (P1 stories first).
- **Polish (Final Phase)**: Depends on the desired user stories being complete (at minimum US1 + US4 for a strong MVP verification).

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational. No hard dependency on other stories, but benefits from US4 unit tests for the "valid passed" coverage.
- **User Story 2 (P1)**: Can start after Foundational. Independent of US1 but shares the same "happy path" resolution seam; benefits from the omitted-case unit test in US4.
- **User Story 3 (P2)**: Can start after Foundational. The error paths are covered by both the pre-existing contract test and the new unit tests in US4.
- **User Story 4 (P2)**: Can start after Foundational (the test additions are largely independent of the verification work in US1–US3). The unit tests provide the executable proof that makes the verifications in the other stories stronger and more regression-safe.

### Within Each User Story

- For stories that have new test code (primarily US4): Add the unit tests so they can be run (they exercise the existing implementation).
- Verification/confirmation steps for behavior (US1–US3) can be done by running existing contract tests + the new unit tests.
- Story complete (checkpoint reached) before moving to next priority if following strict sequential delivery.
- Commit after logical groups of tasks.

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel.
- All Foundational tasks marked [P] can run in parallel (within Phase 2).
- Once Foundational phase completes, the four user story phases can start in parallel (different developers or different focus areas).
- Within US4, the individual test addition tasks (omitted, valid relative/absolute, the three invalid) can be worked on in parallel because they touch the same file but are independent functions.
- All polish tasks marked [P] (quality gates, quickstart execution, coverage review) can run in parallel where they do not conflict.
- Different user stories can be worked on in parallel by different team members after Phase 2.

---

## Parallel Example: User Story 4 (Core Unit Test Delivery)

```bash
# Launch the happy-path unit test additions together:
Task: "Add test_resolve_start_folder_omitted_returns_none ..."
Task: "Add test_resolve_start_folder_accepts_valid_relative and absolute ..."

# Launch the error-path unit test additions together:
Task: "Add the three invalid tests (nonexistent, not-a-directory, unreadable with chmod) ..."

# Then run them:
uv run --extra dev pytest tests/unit/test_scope_resolution.py -q -k "resolve_start_folder"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 4 Recommended)

Because this feature's value is the *verification* provided by the new unit tests:

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — the import and support confirmation)
3. Complete Phase 3 (US1) + Phase 6 (US4) — these together deliver the primary "narrow scope" behavior verified at unit + contract level
4. **STOP and VALIDATE**: Run only the new unit tests + the relevant contract test for US1. Confirm quickstart Scenario 1 and 2 pass.
5. Demo / consider the core verification delivered.

A minimal viable increment could also be just Phase 6 (US4) + running the pre-existing contract tests, since the behavior code already exists.

### Incremental Delivery

1. Setup + Foundational → ready for test work
2. US1 (narrow) verified via contract + new unit coverage → independently testable increment
3. US2 (omitted/default) verified → another independent increment
4. US3 (invalid error handling) verified → independent increment
5. US4 (dedicated unit tests for all four states) completed → the explicit unit proof required by the spec and constitution; now all stories have strong unit backing
6. Polish → full gates + quickstart execution

Each story adds verifiable confidence without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Phase 1 + Phase 2 together.
2. Once Foundational is done:
   - Developer A: US1 (run/verify contract tests + quickstart cross-check)
   - Developer B: US2 (similar verification)
   - Developer C: US3 (error contract test + prepare for unreadable)
   - Developer D (or any): US4 (add the actual unit test functions per research decisions)
3. Stories complete and can be reviewed/merged independently; the unit tests from US4 strengthen all of them.
4. One person runs the final polish gates and quickstart.

---

## Notes

- [P] tasks = different conceptual work or different test functions; even when editing the same test file, the additions for omitted vs. invalid cases have no ordering dependency.
- [Story] label maps task to specific user story for traceability (US1–US4 map directly to the four stories in spec.md).
- Each user story phase should be independently completable and testable (run its contract tests + the relevant slice of the new unit tests).
- The new unit tests (US4) are the main "code change" and should be added so they would have failed before the assertions were written (classic TDD for the test code itself).
- Existing contract and integration tests are intentionally reused for the behavior stories rather than duplicated.
- Commit after each logical group or at each checkpoint.
- Stop at any checkpoint (especially after US1+US4) to validate the story independently.
- All tasks use exact file paths and are specific enough to be executed by an LLM with only the design docs + this tasks list as context.
- No tasks modify production source under src/ (per research.md and plan summary). All changes are in tests/ and (minimally) the already-generated docs in specs/004-.... 

**Total tasks in this plan**: 41 (T001–T041). The majority of new work is concentrated in the US4 phase (the explicit unit tests) while the P1 stories focus on verification using the pre-existing high-quality contract tests.