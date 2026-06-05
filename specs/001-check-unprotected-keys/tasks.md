# Tasks: Check Unprotected Keys

**Input**: Design documents from `/specs/001-check-unprotected-keys/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Unit test and coverage tasks are REQUIRED for every user story. Add integration or contract tests whenever the change touches external seams, packaging boundaries, or runtime integrations.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Initialize project metadata, runtime dependencies, dev dependencies, and console entry point in pyproject.toml
- [X] T002 [P] Configure Ruff, pytest, coverage, setuptools, and build defaults in pyproject.toml
- [X] T003 [P] Configure Pyright for src/ and tests/ in pyrightconfig.json
- [X] T004 Create package marker modules in src/find_unencrypted_keys/__init__.py, src/find_unencrypted_keys/config/__init__.py, src/find_unencrypted_keys/domain/__init__.py, src/find_unencrypted_keys/services/__init__.py, and src/find_unencrypted_keys/adapters/__init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create shared scan request, effective scope, and finding models in src/find_unencrypted_keys/domain/models.py
- [X] T006 [P] Implement scope resolution primitives in src/find_unencrypted_keys/domain/scope.py
- [X] T007 [P] Implement configuration models and base TOML loader scaffolding in src/find_unencrypted_keys/config/models.py and src/find_unencrypted_keys/config/loader.py
- [X] T008 [P] Implement filesystem discovery, canonicalization, and dedup helpers in src/find_unencrypted_keys/adapters/filesystem.py
- [X] T009 [P] Implement safe console reporting and non-secret error summary helpers in src/find_unencrypted_keys/adapters/reporting.py
- [X] T010 Establish scan orchestration and CLI skeletons in src/find_unencrypted_keys/services/scan_service.py and src/find_unencrypted_keys/cli.py
- [X] T011 [P] Add CI quality and build workflow in .github/workflows/ci.yml

**Checkpoint**: Foundation ready - user story implementation can now begin in priority order

---

## Phase 3: User Story 1 - Detect Unprotected Keys (Priority: P1) 🎯 MVP

**Goal**: Detect files in the configured default scope that contain unprotected or empty-passphrase private keys and print only their canonical full paths.

**Independent Test**: Run the scanner with a valid configuration and fixture data, then verify that default execution reports only affected files and returns the findings exit code.

### Tests for User Story 1 (REQUIRED) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T012 [P] [US1] Add unit tests for PEM, OpenSSH, and PuTTY protection classification in tests/unit/test_key_classification.py
- [X] T013 [P] [US1] Add CLI contract tests for default scan output and exit codes in tests/contract/test_cli_default_scan_contract.py
- [X] T014 [US1] Add default-scope integration tests for findings and clean files in tests/integration/test_default_scan_workflow.py
- [X] T015 [US1] Verify US1 coverage behavior through tests/unit/test_key_classification.py and tests/integration/test_default_scan_workflow.py

### Implementation for User Story 1

- [X] T016 [P] [US1] Implement protection assessment rules and finding classification in src/find_unencrypted_keys/domain/classification.py
- [X] T017 [P] [US1] Implement PEM, OpenSSH, and PuTTY parser adapters in src/find_unencrypted_keys/adapters/key_parsers.py
- [X] T018 [US1] Implement default-scope scan execution and file-level finding aggregation in src/find_unencrypted_keys/services/scan_service.py
- [X] T019 [US1] Implement default CLI execution path and findings exit codes in src/find_unencrypted_keys/cli.py
- [X] T020 [US1] Emit canonical finding paths and unreadable-file summaries in src/find_unencrypted_keys/adapters/reporting.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Limit the Scan Scope (Priority: P2)

**Goal**: Allow operators to provide a start folder that narrows configured folder matching without changing filename-pattern behavior.

**Independent Test**: Run the scanner with and without --start-folder against the same fixture set and verify that only the narrowed subtree is searched while filename matches remain unchanged.

### Tests for User Story 2 (REQUIRED) ⚠️

- [X] T021 [P] [US2] Add unit tests for start-folder scope narrowing in tests/unit/test_scope_resolution.py
- [X] T022 [P] [US2] Add CLI contract tests for --start-folder semantics in tests/contract/test_cli_start_folder_contract.py
- [X] T023 [US2] Add narrowed-scope integration tests in tests/integration/test_start_folder_scan.py
- [X] T024 [US2] Verify US2 coverage behavior through tests/unit/test_scope_resolution.py and tests/integration/test_start_folder_scan.py

### Implementation for User Story 2

- [X] T025 [US2] Implement start-folder narrowing rules in src/find_unencrypted_keys/domain/scope.py
- [X] T026 [US2] Update filesystem root expansion and canonical root filtering in src/find_unencrypted_keys/adapters/filesystem.py
- [X] T027 [US2] Update scan orchestration for narrowed folder scopes in src/find_unencrypted_keys/services/scan_service.py
- [X] T028 [US2] Add CLI validation and user-facing errors for --start-folder in src/find_unencrypted_keys/cli.py

**Checkpoint**: At this point, User Stories 1 and 2 should both work independently.


## Phase 5: User Story 3 - Manage Search Patterns Through Configuration (Priority: P3)

**Goal**: Make folder and filename patterns fully configuration-driven, including overlap handling and deduplicated candidate discovery.

**Independent Test**: Modify `.find-unencrypted-keys.toml` fixtures to add and remove folder and filename patterns, rerun the scanner, and confirm the next scan reflects the updated scope without code changes.

### Tests for User Story 3

- [X] T029 [P] [US3] Add unit tests for TOML configuration validation in `tests/unit/test_config_loader.py`
- [X] T030 [US3] Add the configuration contract test in `tests/contract/test_config_contract.py`

### Implementation for User Story 3

- [X] T031 [US3] Implement TOML configuration parsing and schema validation in `src/find_unencrypted_keys/config/loader.py`
- [X] T032 [US3] Implement configuration-backed folder and filename scope resolution in `src/find_unencrypted_keys/adapters/filesystem.py`
- [X] T033 [US3] Implement overlap deduplication and config-driven scan-request composition in `src/find_unencrypted_keys/services/scan_service.py`
- [X] T034 [US3] Update runtime configuration examples in `specs/001-check-unprotected-keys/contracts/config-contract.md` and `specs/001-check-unprotected-keys/quickstart.md`
- [X] T035 [US3] Verify US3 coverage stays above the enforced threshold in `tests/unit/test_config_loader.py` and `tests/contract/test_config_contract.py`

**Checkpoint**: Maintainers can evolve the scan scope through configuration only, with deduplicated results.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finalize documentation, validation, packaging, and cross-story hardening.

- [X] T036 [P] Update operator-facing documentation in `README.md` and `specs/001-check-unprotected-keys/quickstart.md`
- [X] T037 Refine shared scan interfaces in `src/find_unencrypted_keys/services/scan_service.py` and `src/find_unencrypted_keys/domain/models.py`
- [X] T038 [P] Run formatter, lint, type-check, pytest, and coverage commands defined in `pyproject.toml`
- [X] T039 Harden secret-safe error summaries in `src/find_unencrypted_keys/adapters/reporting.py` and `src/find_unencrypted_keys/services/scan_service.py`
- [X] T040 [P] Build and smoke-test the standalone executable with `scripts/smoke_test_executable.sh`
- [X] T041 Run the documented quickstart validation from `specs/001-check-unprotected-keys/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup** has no dependencies and starts immediately.
- **Phase 2: Foundational** depends on Phase 1 and blocks all user stories.
- **Phase 3: User Story 1** depends on Phase 2 and delivers the MVP.
- **Phase 4: User Story 2** depends on Phase 2 and the baseline scan flow from User Story 1.
- **Phase 5: User Story 3** depends on Phase 2 and can proceed after the foundational config scaffolding exists.
- **Phase 6: Polish** depends on all desired user stories being complete.

### User Story Dependencies

- **US1**: No story dependencies after the foundational phase.
- **US2**: Extends the default scan flow from US1 with narrowed folder scope.
- **US3**: Builds on the foundational configuration scaffolding and can proceed independently of US2.

### Within Each User Story

- Write tests first and confirm they fail before implementing the story.
- Implement parsing/models before orchestration.
- Update CLI or reporting adapters after the underlying domain behavior exists.
- Finish each story with its coverage verification task before moving on.

## Parallel Opportunities

- T006, T007, and T008 can run in parallel once the foundational models exist.
- T011 and T012 can run in parallel for US1.
- T015 and T016 can run in parallel for US1.
- T021 and T022 can run in parallel for US2.
- T028 and T029 can run in parallel for US3.
- T036, T038, and T040 can run in parallel during polish.

---

## Parallel Example: User Story 1

```bash
Task: "Add protected, unprotected, empty-passphrase, and public-only fixture files in tests/fixtures/default-scope/"
Task: "Add unit tests for key classification and safe reporting in tests/unit/test_key_classification.py and tests/unit/test_reporting.py"

Task: "Implement PEM, PKCS#8, and OpenSSH key parsing in src/find_unencrypted_keys/adapters/key_parsers.py"
Task: "Implement protection-assessment rules in src/find_unencrypted_keys/domain/classification.py"
```

## Parallel Example: User Story 2

```bash
Task: "Add narrowed-scope and clean-scope fixture directories in tests/fixtures/team-a/ and tests/fixtures/protected-only/"
Task: "Add unit tests for start-folder scope narrowing in tests/unit/test_scope_resolution.py"
```

## Parallel Example: User Story 3

```bash
Task: "Add configuration-update and overlap fixtures in tests/fixtures/config-scope/"
Task: "Add unit tests for TOML configuration validation in tests/unit/test_config_loader.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. Validate the default-root scan behavior before moving on.

### Incremental Delivery

1. Deliver the MVP by finishing User Story 1.
2. Add User Story 2 to support targeted scans with `--start-folder`.
3. Add User Story 3 to make pattern evolution and overlap handling fully configuration-driven.
4. Finish with polish, packaging, and quickstart validation.

### Parallel Team Strategy

1. One developer completes Setup and Foundational work.
2. After Phase 2, one developer focuses on US1 while another can prepare US3 configuration tests and fixtures.
3. Start US2 after the US1 scan flow is stable.

---

## Notes

- `[P]` tasks touch different files and can be completed independently.
- `[US1]`, `[US2]`, and `[US3]` provide traceability from tasks back to user stories.
- Each story ends with an explicit coverage-verification task.
- The polished deliverable includes standalone executable smoke testing and quickstart validation.