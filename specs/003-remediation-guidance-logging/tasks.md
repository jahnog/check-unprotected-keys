# Tasks: Remediation Guidance Logging

**Input**: Design documents from `/specs/003-remediation-guidance-logging/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Unit test and coverage tasks are REQUIRED for every user story. Add integration or contract tests whenever the change touches external seams, packaging boundaries, or runtime integrations.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the shared fixture and CLI-output scaffolding used by all remediation-guidance stories.

- [X] T001 Create remediation-guidance fixture workspace scaffolding in tests/support/fixture_builders.py
- [X] T002 [P] Add representative malformed, interactive SSH, host-key, automation, and embedded-config fixture builders in tests/support/fixture_builders.py
- [X] T003 [P] Add reusable CLI stdout/stderr capture helpers in tests/support/fixture_builders.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared reporting primitives that MUST be complete before any user story work begins.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Extend typed scan-result and finding primitives for malformed issues and guidance metadata in src/check_unprotected_keys/domain/models.py
- [X] T005 Wire candidate context needed for malformed-path and recommendation reporting in src/check_unprotected_keys/services/scan_service.py
- [X] T006 Add shared operator-safe stderr section rendering helpers in src/check_unprotected_keys/adapters/reporting.py

**Checkpoint**: Typed reporting foundations are ready; user story implementation can now proceed in priority order.

---

## Phase 3: User Story 1 - Surface Malformed File Paths (Priority: P1) 🎯 MVP

**Goal**: Make malformed files immediately actionable by logging each malformed path on the operator-facing console stream without changing finding stdout or exit codes.

**Independent Test**: Run a scan over a dataset containing malformed files and verify that stderr includes each malformed file path while stdout remains a plain finding-path stream.

### Tests for User Story 1 (REQUIRED)

- [X] T007 [P] [US1] Add unit tests for malformed issue capture and rendering in tests/unit/test_malformed_path_logging.py
- [X] T008 [P] [US1] Add CLI contract coverage for malformed path logging in tests/contract/test_cli_default_scan_contract.py
- [X] T009 [US1] Add end-to-end malformed-file workflow coverage in tests/integration/test_default_scan_workflow.py
- [X] T010 [US1] Verify coverage for malformed-path behavior through tests/unit/test_malformed_path_logging.py and tests/integration/test_default_scan_workflow.py

### Implementation for User Story 1

- [X] T011 [P] [US1] Populate malformed-file fixture scenarios and expected outputs in tests/support/fixture_builders.py
- [X] T012 [US1] Record canonical malformed issues in src/check_unprotected_keys/domain/models.py and src/check_unprotected_keys/services/scan_service.py
- [X] T013 [US1] Emit malformed-file path logs in src/check_unprotected_keys/adapters/reporting.py

**Checkpoint**: User Story 1 is independently functional and proves malformed files are surfaced without breaking machine-readable findings.

---

## Phase 4: User Story 2 - Recommend Low-Friction Protection Methods (Priority: P2)

**Goal**: Enrich unprotected findings with usage-aware remediation guidance that fits interactive, host, automation, and embedded-config workflows.

**Independent Test**: Run a scan over representative SSH, host-key, automation, and embedded-key fixtures and confirm that each unprotected finding receives the expected recommendation on stderr.

### Tests for User Story 2 (REQUIRED)

- [X] T014 [P] [US2] Add unit tests for usage-category inference and recommendation selection in tests/unit/test_remediation_guidance.py
- [X] T015 [P] [US2] Add CLI contract coverage for remediation guidance output in tests/contract/test_cli_default_scan_contract.py
- [X] T016 [US2] Add end-to-end recommendation workflow coverage in tests/integration/test_default_scan_workflow.py
- [X] T017 [US2] Verify coverage for recommendation behavior through tests/unit/test_remediation_guidance.py and tests/integration/test_default_scan_workflow.py

### Implementation for User Story 2

- [X] T018 [P] [US2] Populate interactive-user, host-key, automation, and embedded-config recommendation fixtures in tests/support/fixture_builders.py
- [X] T019 [US2] Add usage-category and remediation recommendation entities in src/check_unprotected_keys/domain/models.py
- [X] T020 [US2] Implement usage-category inference and finding enrichment in src/check_unprotected_keys/services/scan_service.py
- [X] T021 [US2] Emit per-finding remediation guidance blocks in src/check_unprotected_keys/adapters/reporting.py

**Checkpoint**: User Story 2 is independently functional and produces low-friction remediation guidance for supported unprotected findings.

---

## Phase 5: User Story 3 - Preserve Scriptable Output and Operator Trust (Priority: P3)

**Goal**: Keep the richer console output fully compatible with existing scriptable stdout behavior, malformed-only scans, and `--start-folder` workflows.

**Independent Test**: Run the CLI contract scenarios with findings, malformed-only input, and `--start-folder`, then verify stdout stays machine-readable while the new operator guidance remains on stderr.

### Tests for User Story 3 (REQUIRED)

- [X] T022 [P] [US3] Add unit tests for stdout/stderr separation and malformed-only no-finding output in tests/unit/test_reporting.py
- [X] T023 [P] [US3] Add CLI contract coverage for scriptable stdout and `--start-folder` compatibility in tests/contract/test_cli_default_scan_contract.py and tests/contract/test_cli_start_folder_contract.py
- [X] T024 [US3] Add integration coverage for malformed-only and start-folder guidance scenarios in tests/integration/test_default_scan_workflow.py and tests/integration/test_start_folder_scan.py
- [X] T025 [US3] Verify coverage for output-compatibility behavior through tests/unit/test_reporting.py and tests/integration/test_start_folder_scan.py

### Implementation for User Story 3

- [X] T026 [P] [US3] Refine stable stdout/stderr ordering and section formatting in src/check_unprotected_keys/adapters/reporting.py
- [X] T027 [US3] Preserve start-folder-compatible recommendation context in src/check_unprotected_keys/services/scan_service.py
- [X] T028 [US3] Document scriptable-output guarantees and operator guidance flow in specs/003-remediation-guidance-logging/contracts/cli-contract.md and specs/003-remediation-guidance-logging/quickstart.md

**Checkpoint**: All user stories are independently functional and the CLI contract remains stable for human and automated consumers.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finish operator-facing documentation, full validation, packaging, and quickstart execution across all stories.

- [X] T029 [P] Update operator-facing CLI guidance in README.md and .check-unprotected-keys.toml.example
- [X] T030 Run formatter, lint, type-check, pytest, and coverage commands from pyproject.toml
- [X] T031 [P] Build and smoke-test the standalone executable in scripts/smoke_test_executable.sh
- [X] T032 Run the documented quickstart validation from specs/003-remediation-guidance-logging/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup** has no dependencies and can begin immediately.
- **Phase 2: Foundational** depends on Phase 1 and blocks all user stories.
- **Phase 3: User Story 1** depends on Phase 2 and delivers the MVP.
- **Phase 4: User Story 2** depends on User Story 1 because recommendation guidance builds on the enriched reporting surfaces introduced for malformed-path visibility.
- **Phase 5: User Story 3** depends on User Stories 1 and 2 because it stabilizes the full stdout/stderr contract after both malformed logging and remediation guidance exist.
- **Phase 6: Polish** depends on all desired user stories being complete.

### User Story Dependencies

- **US1**: No story dependencies after the foundational phase.
- **US2**: Extends the enriched finding and reporting surfaces created for US1 while remaining independently testable with recommendation fixtures.
- **US3**: Validates compatibility and documentation after US1 and US2 have established the final stderr content.

### Within Each User Story

- Write tests first and confirm they fail before implementing the story.
- Update shared fixtures before changing the runtime reporting behavior they validate.
- Extend typed models before service orchestration and reporting formatting.
- Finish each story with its coverage-verification task before moving to the next priority.

### Parallel Opportunities

- T002 and T003 can run in parallel after T001.
- T007 and T008 can run in parallel for US1.
- T014 and T015 can run in parallel for US2.
- T022 and T023 can run in parallel for US3.
- T029 and T031 can run in parallel during polish.

---

## Parallel Example: User Story 1

```bash
Task: "Add unit tests for malformed issue capture and rendering in tests/unit/test_malformed_path_logging.py"
Task: "Add CLI contract coverage for malformed path logging in tests/contract/test_cli_default_scan_contract.py"
```

## Parallel Example: User Story 2

```bash
Task: "Add unit tests for usage-category inference and recommendation selection in tests/unit/test_remediation_guidance.py"
Task: "Populate interactive-user, host-key, automation, and embedded-config recommendation fixtures in tests/support/fixture_builders.py"
```

## Parallel Example: User Story 3

```bash
Task: "Add unit tests for stdout/stderr separation and malformed-only no-finding output in tests/unit/test_reporting.py"
Task: "Add CLI contract coverage for scriptable stdout and --start-folder compatibility in tests/contract/test_cli_start_folder_contract.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. Validate malformed-path visibility before moving on.

### Incremental Delivery

1. Deliver the MVP by finishing User Story 1.
2. Add User Story 2 to provide usage-aware remediation guidance.
3. Add User Story 3 to lock down CLI compatibility and documentation.
4. Finish with polish, packaging, and quickstart validation.

### Parallel Team Strategy

1. One developer completes Setup and Foundational work.
2. After US1 begins, a second developer can prepare US2 recommendation fixtures and unit tests in parallel.
3. Once US2 behavior is stable, a third developer can focus on US3 output-compatibility coverage and docs.

---

## Notes

- `[P]` tasks touch different files and can be completed independently.
- `[US1]`, `[US2]`, and `[US3]` provide traceability from tasks back to user stories.
- Each user story ends with an explicit coverage-verification task.
- The polish phase includes full quality gates, standalone executable smoke testing, and quickstart validation.