# Tasks: Expand Secret Patterns

**Input**: Design documents from `/specs/002-expand-secret-patterns/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Unit test and coverage tasks are REQUIRED for every user story. Add integration or contract tests whenever the change touches external seams, packaging boundaries, or runtime integrations.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the shared fixture and configuration scaffolding used by all expanded-catalog stories.

- [X] T001 Create expanded-catalog fixture scaffolding in tests/fixtures/expanded-patterns/ and tests/support/fixture_builders.py
- [X] T002 [P] Add expanded baseline pattern constants and config-writing helpers in tests/support/fixture_builders.py
- [X] T003 [P] Prepare the shipped expanded example catalog in .check-unprotected-keys.toml.example

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared prerequisites that MUST be complete before any user story work begins.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Extend shared workspace builders for home-ssh, repo-key, config-subtree, infra, vpn, and noise scenarios in tests/support/fixture_builders.py
- [X] T005 [P] Add shared helper coverage for `~` expansion, canonical deduplication, and trimmed pattern loading in tests/unit/test_foundation_helpers.py and tests/unit/test_config_loader.py
- [X] T006 [P] Establish baseline catalog contracts and validation guidance in specs/002-expand-secret-patterns/contracts/config-contract.md, specs/002-expand-secret-patterns/contracts/cli-contract.md, and specs/002-expand-secret-patterns/quickstart.md

**Checkpoint**: Expanded-catalog foundations are ready; user story implementation can now proceed in priority order.

---

## Phase 3: User Story 1 - Broaden Default Secret Coverage (Priority: P1)

**Goal**: Ship a broader default folder and filename catalog that finds supported exposed key material in more common Linux-first locations without requiring operators to tune the config first.

**Independent Test**: Run a default scan against the expanded fixture dataset and verify that files under newly supported folder and filename conventions are evaluated and affected files are reported without local config edits.

### Tests for User Story 1 (REQUIRED)

- [X] T007 [P] [US1] Add unit tests for expanded default folder and filename catalog loading in tests/unit/test_config_loader.py and tests/unit/test_scope_resolution.py
- [X] T008 [P] [US1] Add configuration contract tests for broader default roots and filenames in tests/contract/test_config_contract.py
- [X] T009 [US1] Add expanded default-scan integration coverage in tests/integration/test_default_scan_workflow.py
- [X] T010 [US1] Verify US1 coverage behavior through tests/unit/test_config_loader.py and tests/integration/test_default_scan_workflow.py

### Implementation for User Story 1

- [X] T011 [P] [US1] Populate expanded default-scope fixtures and baseline pattern constants in tests/fixtures/expanded-patterns/ and tests/support/fixture_builders.py
- [X] T012 [US1] Implement the broadened shipped folder and filename catalog in .check-unprotected-keys.toml.example
- [X] T013 [US1] Align expanded default-scope examples in specs/002-expand-secret-patterns/contracts/config-contract.md and specs/002-expand-secret-patterns/quickstart.md

**Checkpoint**: User Story 1 is independently functional through the shipped expanded baseline catalog.

---

## Phase 4: User Story 2 - Expand Coverage Without Excess Noise (Priority: P2)

**Goal**: Keep the broader default catalog bounded so public-only, unsupported, and unrelated files do not turn the wider scan surface into noisy findings or unmanageable traversal.

**Independent Test**: Run the expanded catalog against a mixed noise dataset and verify that public-only files, unsupported keystores, certificate-only files, and generic config content do not become findings while overlap deduplication still holds.

### Tests for User Story 2 (REQUIRED)

- [X] T014 [P] [US2] Add unit tests for public-only, protected, and unsupported files matched by broader patterns in tests/unit/test_key_classification.py
- [X] T015 [P] [US2] Add contract tests for bounded exclusions and overlap deduplication in tests/contract/test_config_contract.py
- [X] T016 [US2] Add noise-boundary integration coverage in tests/integration/test_default_scan_workflow.py
- [X] T017 [US2] Verify US2 coverage behavior through tests/unit/test_key_classification.py and tests/integration/test_default_scan_workflow.py

### Implementation for User Story 2

- [X] T018 [P] [US2] Create noise-boundary fixtures for public-only, certificate-only, unsupported keystore, and generic config files in tests/fixtures/expanded-patterns/ and tests/support/fixture_builders.py
- [X] T019 [US2] Curate bounded exclusions and overlap examples in .check-unprotected-keys.toml.example and specs/002-expand-secret-patterns/contracts/config-contract.md
- [X] T020 [US2] Update operator guidance for exclusions and non-goals in README.md and specs/002-expand-secret-patterns/quickstart.md

**Checkpoint**: User Story 2 proves the broader catalog remains bounded and deduplicated.

---

## Phase 5: User Story 3 - Preserve Operator Control (Priority: P3)

**Goal**: Keep the expanded baseline configuration-driven and fully compatible with start-folder narrowing and operator overrides.

**Independent Test**: Edit the expanded catalog, rerun scans with and without `--start-folder`, and verify that the next scan respects operator changes while preserving unchanged filename-pattern behavior.

### Tests for User Story 3 (REQUIRED)

- [X] T021 [P] [US3] Add unit tests for `~`-expanded roots, configuration overrides, and narrowed root handling in tests/unit/test_scope_resolution.py and tests/unit/test_foundation_helpers.py
- [X] T022 [P] [US3] Add CLI contract tests for expanded-catalog `--start-folder` and override semantics in tests/contract/test_cli_start_folder_contract.py and tests/contract/test_cli_default_scan_contract.py
- [X] T023 [US3] Add narrowed-scope and configuration-override integration coverage in tests/integration/test_start_folder_scan.py
- [X] T024 [US3] Verify US3 coverage behavior through tests/unit/test_scope_resolution.py and tests/integration/test_start_folder_scan.py

### Implementation for User Story 3

- [X] T025 [P] [US3] Extend expanded-catalog workspace and override helpers in tests/support/fixture_builders.py
- [X] T026 [US3] Update expanded-catalog root expansion and narrowed-scope handling in src/find_unencrypted_keys/adapters/filesystem.py and src/find_unencrypted_keys/domain/scope.py
- [X] T027 [US3] Document operator-controlled catalog edits and start-folder behavior in specs/002-expand-secret-patterns/contracts/cli-contract.md and specs/002-expand-secret-patterns/quickstart.md

**Checkpoint**: All user stories are independently functional and compatible with operator-controlled scope updates.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, packaging, and operator-facing cleanup across all stories.

- [X] T028 [P] Update operator-facing examples in README.md and .check-unprotected-keys.toml.example
- [X] T029 Run formatter, lint, type-check, pytest, and coverage commands defined in pyproject.toml
- [X] T030 Refine fixture naming and expanded-catalog validation wording in tests/fixtures/expanded-patterns/ and specs/002-expand-secret-patterns/quickstart.md
- [X] T031 [P] Build and smoke-test the standalone executable with expanded-catalog scenarios in scripts/smoke_test_executable.sh
- [X] T032 Run the documented quickstart validation from specs/002-expand-secret-patterns/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup** has no dependencies and can begin immediately.
- **Phase 2: Foundational** depends on Phase 1 and blocks all user stories.
- **Phase 3: User Story 1** depends on Phase 2 and delivers the MVP.
- **Phase 4: User Story 2** depends on Phase 2 and builds on the broader default catalog established in US1.
- **Phase 5: User Story 3** depends on Phase 2 and the expanded catalog semantics established in US1.
- **Phase 6: Polish** depends on all desired user stories being complete.

### User Story Dependencies

- **US1**: No story dependencies after the foundational phase.
- **US2**: Extends US1 by proving bounded exclusions and low-noise behavior for the broader catalog.
- **US3**: Extends US1 by proving operator override and start-folder compatibility for the broader catalog.

### Within Each User Story

- Write tests first and confirm they fail before implementing the story.
- Update shared fixtures or helpers before changing shipped catalog examples.
- Change contracts and quickstart guidance after the underlying behavior is proven.
- Finish each story with its coverage verification task before moving to the next priority.

### Parallel Opportunities

- T002 and T003 can run in parallel after T001.
- T005 and T006 can run in parallel after T004.
- T007 and T008 can run in parallel for US1.
- T014 and T015 can run in parallel for US2.
- T021 and T022 can run in parallel for US3.
- T028 and T031 can run in parallel during polish.

---

## Parallel Example: User Story 1

```bash
Task: "Add expanded default-scope fixture coverage in tests/fixtures/expanded-patterns/"
Task: "Add broader default catalog contract tests in tests/contract/test_config_contract.py"
```

## Parallel Example: User Story 2

```bash
Task: "Create noise-boundary fixtures in tests/fixtures/expanded-patterns/ and tests/support/fixture_builders.py"
Task: "Add bounded-exclusion coverage in tests/unit/test_key_classification.py"
```

## Parallel Example: User Story 3

```bash
Task: "Add expanded-catalog start-folder contract coverage in tests/contract/test_cli_start_folder_contract.py"
Task: "Extend override-aware fixture helpers in tests/support/fixture_builders.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. Validate the broader default-scope workflow before moving on.

### Incremental Delivery

1. Deliver the MVP by finishing User Story 1.
2. Add User Story 2 to bound noise and exclusions for the broader catalog.
3. Add User Story 3 to preserve operator overrides and `--start-folder` compatibility.
4. Finish with polish, packaging, and quickstart validation.

### Parallel Team Strategy

1. One developer completes Setup and Foundational work.
2. After Phase 2, one developer can drive US1 while another prepares US2 noise fixtures and tests.
3. Start US3 once the broadened catalog semantics from US1 are stable.

---

## Notes

- `[P]` tasks touch different files and can be completed independently.
- `[US1]`, `[US2]`, and `[US3]` provide traceability from tasks back to user stories.
- Each user story ends with an explicit coverage-verification task.
- The polish phase includes standalone executable smoke testing and quickstart validation for the expanded catalog.