---
description: "Task list for Move Ignore Patterns to Configuration"
---

# Tasks: Move Ignore Patterns to Configuration

**Input**: Design documents from `specs/007-move-ignore-to-config/`

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅ · quickstart.md ✅

**Tests**: Unit and integration tests are REQUIRED per the project constitution.
Write tests before implementation; verify they fail first; triage any post-implementation
failures before changing test or code.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: User story this task belongs to (US1 / US2 / US3 / US4)

---

## Phase 1: Setup

**Purpose**: Confirm prerequisites and shared test infrastructure before foundational work.

- [X] T001 Confirm design artifacts and contract at `specs/007-move-ignore-to-config/contracts/ignore-patterns-semantics.md` match clarified spec decisions (replace semantics, ignore-wins overlap, cache/package defaults)
- [X] T002 [P] Add `write_ignore_patterns_configuration()` helper (or extend existing writers) in `tests/support/fixture_builders.py` to build configs with explicit `ignore_directories` / `ignore_filename_patterns` / omit-key variants

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Model fields, packaged default catalog in example TOML, and loader resolution.
Must complete before any user story implementation.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Add `ignore_filename_patterns: tuple[str, ...]` and `load_warnings: tuple[str, ...] = ()` to `ScanConfigSection` in `src/check_unprotected_keys/config/models.py`
- [X] T004 [P] Add `ignore_filename_patterns: tuple[str, ...]` and `load_warnings: tuple[str, ...] = ()` to `SearchConfiguration` in `src/check_unprotected_keys/domain/models.py`
- [X] T005 Add `ignore_filename_patterns: frozenset[str] = frozenset()` to `EffectiveScope` in `src/check_unprotected_keys/domain/models.py`
- [X] T006 Populate full commented `ignore_directories` and `ignore_filename_patterns` catalogs (VCS, build, caches, package trees, public/cert/keystore/cache/package file patterns) in `src/check_unprotected_keys/resources/check-unprotected-keys.example.toml` with header comments documenting omit / `[]` / replace semantics
- [X] T007 Implement cached `_load_packaged_defaults()` in `src/check_unprotected_keys/config/loader.py` parsing `check-unprotected-keys.example.toml` via `importlib.resources` + `tomllib`
- [X] T008 Remove `DEFAULT_IGNORE_DIRECTORIES` and add `_resolve_ignore_list(scan_table, *, key, packaged_defaults, key_was_present)` implementing omit / `[]` / replace rules in `src/check_unprotected_keys/config/loader.py`
- [X] T009 Wire `ignore_directories` and `ignore_filename_patterns` resolution through `load_search_configuration()` into `ScanConfigSection` and `SearchConfiguration` in `src/check_unprotected_keys/config/loader.py`
- [X] T010 Update `tests/support/fixture_builders.py` and any constructors in `tests/unit/test_config_loader.py` / `tests/unit/test_scope_resolution.py` that build `SearchConfiguration` to include `ignore_filename_patterns` (default `()`)

**Checkpoint**: Loader compiles; packaged defaults load from example resource; existing tests pass or fail only on missing new fields.

---

## Phase 3: User Story 1 — Inspect and Understand All Ignore Rules (Priority: P1) 🎯 MVP

**Goal**: Operators see complete default ignore catalogs in packaged example configuration;
no hidden code-only default lists.

**Independent Test**: Run `--print-example-config` and confirm both ignore keys list full
default catalogs with explanatory comments (quickstart Scenario 1).

### Tests for User Story 1 (write first — MUST FAIL before T013–T014) ⚠️

- [X] T011 [P] [US1] Add unit tests in `tests/unit/test_config_loader.py`: omitted `ignore_directories` / `ignore_filename_patterns` resolve to packaged resource defaults (not empty, include sentinel entries like `.git` and `*.pub`)
- [X] T012 [P] [US1] Add unit test in `tests/unit/test_config_loader.py` or `tests/unit/test_cli.py`: `read_example_configuration_text()` / `--print-example-config` output contains both `ignore_directories` and `ignore_filename_patterns` keys with cache/package examples

### Implementation for User Story 1

- [X] T013 [US1] Verify `read_example_configuration_text()` in `src/check_unprotected_keys/config/loader.py` returns the updated example resource unchanged (no code-side default injection)
- [X] T014 [US1] Run US1 tests (`pytest tests/unit/test_config_loader.py tests/unit/test_cli.py -k ignore -q`) and confirm pass; triage failures before changing test or code

**Checkpoint**: US1 complete — defaults are visible and loadable from packaged configuration only.

---

## Phase 4: User Story 2 — Customize Ignore Behavior (Priority: P1)

**Goal**: Replace semantics for explicit ignore lists; filename ignores skip candidates
before inclusion matching (ignore wins on overlap).

**Independent Test**: Config with `ignore_directories = ["noise"]` only prunes `noise`;
config with `ignore_filename_patterns` skips overlap files (quickstart Scenarios 2–3).

### Tests for User Story 2 (write first — MUST FAIL before T019–T022) ⚠️

- [X] T015 [P] [US2] Add unit tests in `tests/unit/test_config_loader.py` for replace semantics: explicit non-empty `ignore_directories` / `ignore_filename_patterns` use only user entries (no packaged merge); copied defaults + custom entry works when user supplies full list
- [X] T016 [P] [US2] Add unit tests in `tests/unit/test_scope_resolution.py` or new `tests/unit/test_filesystem_ignore_patterns.py`: `discover_candidate_files` skips `id_rsa.pub` when `*.pub` is in `scope.ignore_filename_patterns` but still discovers `id_rsa`; ignored files are not counted toward scan assessment
- [X] T017 [US2] Run US2 tests and confirm T015–T016 fail before implementation; record failures

### Implementation for User Story 2

- [X] T018 [US2] Extend `build_effective_scope()` in `src/check_unprotected_keys/domain/scope.py` to accept and store `ignore_filename_patterns`
- [X] T019 [US2] Pass resolved `ignore_filename_patterns` from `resolve_effective_scope()` into `build_effective_scope()` in `src/check_unprotected_keys/adapters/filesystem.py`
- [X] T020 [US2] In `discover_candidate_files()` in `src/check_unprotected_keys/adapters/filesystem.py`, skip files matching `scope.ignore_filename_patterns` via `_match_filename_pattern()` **before** inclusion matching (no `CandidateFile`, no read)
- [X] T021 [US2] Add integration test in `tests/integration/test_ignore_patterns.py`: custom `ignore_directories` replace semantics (Scenario 2) and overlap skip for `id_rsa.pub` (Scenario 3)
- [X] T022 [US2] Run US2 tests and confirm pass; triage failures before changing test or code

**Checkpoint**: US2 complete — operators can customize ignores; ignore-over-inclusion works.

---

## Phase 5: User Story 3 — Disable Default Ignores (Priority: P2)

**Goal**: Explicit empty arrays disable all ignores of that type; overlap files scanned
when file ignores disabled.

**Independent Test**: `ignore_filename_patterns = []` causes `id_rsa.pub` to be read and
classified; `ignore_directories = []` descends into previously pruned trees (quickstart
Scenario 4).

### Tests for User Story 3 (write first — MUST FAIL before T025) ⚠️

- [X] T023 [P] [US3] Add unit tests in `tests/unit/test_config_loader.py`: `ignore_directories = []` and `ignore_filename_patterns = []` resolve to empty tuples (no packaged defaults applied)
- [X] T024 [P] [US3] Add integration tests in `tests/integration/test_ignore_patterns.py`: empty `ignore_filename_patterns` restores overlap scanning; empty `ignore_directories` traverses a noise directory that packaged defaults would prune

### Implementation for User Story 3

- [X] T025 [US3] Confirm loader empty-array branch in `_resolve_ignore_list()` returns `()` without reading packaged defaults in `src/check_unprotected_keys/config/loader.py` (fix if tests expose gap)
- [X] T026 [US3] Run US3 tests and confirm pass; triage failures before changing test or code

**Checkpoint**: US3 complete — power users can disable ignores per key.

---

## Phase 6: User Story 4 — Upgrade Without Surprises (Priority: P2)

**Goal**: Omitted keys keep packaged defaults; partial legacy lists warn on stderr; security
findings unchanged for representative fixtures; `files_scanned` may drop for skipped pub
sidecars.

**Independent Test**: Legacy partial `ignore_directories` emits stderr warning; representative
integration fixtures produce same findings (quickstart Scenario 5; SC-002).

### Tests for User Story 4 (write first — MUST FAIL before T029–T032) ⚠️

- [X] T027 [P] [US4] Add unit tests in `tests/unit/test_config_loader.py` for partial-legacy warning heuristic: `ignore_directories = ["my-custom-only"]` populates `load_warnings`; full copied default list does not warn
- [X] T028 [P] [US4] Add integration test in `tests/integration/test_ignore_patterns.py`: stderr contains migration warning for partial legacy config (FR-012 / SC-006); scan still completes
- [X] T029 [US4] Update `tests/integration/test_default_scan_workflow.py` expectations: `test_clean_scope_scan_excludes_protected_and_public_only_files` — adjust `files_scanned` if `id_rsa.pub` skipped by packaged file ignores; findings remain empty

### Implementation for User Story 4

- [X] T030 [US4] Implement `_maybe_partial_legacy_warning()` and populate `load_warnings` on `SearchConfiguration` in `src/check_unprotected_keys/config/loader.py` per `research.md` heuristic
- [X] T031 [US4] Print each `configuration.load_warnings` entry to stderr in `src/check_unprotected_keys/cli.py` after successful load (optional `emit_warning()` helper in `src/check_unprotected_keys/adapters/reporting.py`)
- [X] T032 [US4] Add integration test in `tests/integration/test_ignore_patterns.py`: omitted ignore keys apply expanded defaults — `vendor/` or `.npm/` pruned, findings identical to SC-002 fixtures for unchanged configs
- [X] T033 [US4] Run US4 tests and full `tests/integration/test_default_scan_workflow.py`; triage failures (test logic vs. implementation) before changing test or code

**Checkpoint**: US4 complete — migration path clear; regressions controlled.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, quality gates, and quickstart validation across all stories.

- [X] T034 [P] Update `README.md` default non-goals section to reference `ignore_filename_patterns`, replace semantics, and partial-list migration guidance
- [X] T035 [P] Add cross-reference in `src/check_unprotected_keys/resources/check-unprotected-keys.example.toml` header to `ignore_filename_patterns` replacing comment-only file exclusions
- [X] T036 Run full quality gates: `pytest --cov-fail-under=85`, `ruff check src/ tests/`, `ruff format --check src/ tests/`, `pyright src/`
- [X] T037 Run manual validation scenarios from `specs/007-move-ignore-to-config/quickstart.md` and record pass/fail in PR or task notes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational (T006–T009 minimum)
- **US2 (Phase 4)**: Depends on Foundational; independently testable after T018–T020
- **US3 (Phase 5)**: Depends on Foundational loader; benefits from US2 discovery filter for integration tests
- **US4 (Phase 6)**: Depends on Foundational loader; warning + regression tests may run after US2/US3
- **Polish (Phase 7)**: Depends on all desired user stories

### User Story Dependencies

| Story | Depends on | Independent test |
|-------|------------|------------------|
| US1 | Foundational | `--print-example-config` + loader omit-key tests |
| US2 | Foundational | Replace semantics + overlap skip integration |
| US3 | Foundational (loader) | Empty-array unit + integration |
| US4 | Foundational + US2 discovery for regression | Warning stderr + SC-002 findings |

US2–US4 can proceed in parallel **after** Phase 2 if staffed; US3 loader tests only need Phase 2.

### Within Each User Story

1. Tests written and failing
2. Implementation
3. Tests passing
4. Triage before editing expectations

---

## Parallel Execution Examples

### Foundational (after T006 example TOML exists)

```bash
# Parallel model updates:
T003: config/models.py
T004: domain/models.py
T005: EffectiveScope field in domain/models.py
```

### User Story 2

```bash
# Parallel tests before implementation:
T015: tests/unit/test_config_loader.py
T016: tests/unit/test_filesystem_ignore_patterns.py
```

### User Story 4

```bash
# Parallel tests before implementation:
T027: tests/unit/test_config_loader.py (warning heuristic)
T028: tests/integration/test_ignore_patterns.py (stderr warning)
T029: tests/integration/test_default_scan_workflow.py (files_scanned)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1–2 (Setup + Foundational)
2. Complete Phase 3 (US1) — visible defaults in packaged config
3. **STOP and VALIDATE**: quickstart Scenario 1 + loader omit-key tests
4. Demo: `--print-example-config` shows full ignore catalogs

### Incremental Delivery

1. Foundational → US1 (transparency MVP)
2. US2 (customize + filename filter) → validate Scenarios 2–3
3. US3 (disable via `[]`) → validate Scenario 4
4. US4 (migration warning + regressions) → validate Scenario 5 + SC-002
5. Polish → full gates + quickstart

### Suggested MVP Scope

**User Story 1 only** after Foundational: delivers the core request (“move patterns to
configuration files”) with packaged catalogs and loader reading defaults from resource.
US2 is required for full feature value (filename ignores + replace semantics in discovery).

---

## Task Summary

| Phase | Tasks | Story |
|-------|-------|-------|
| Setup | T001–T002 | — |
| Foundational | T003–T010 | — |
| US1 | T011–T014 | 4 tasks |
| US2 | T015–T022 | 8 tasks |
| US3 | T023–T026 | 4 tasks |
| US4 | T027–T033 | 7 tasks |
| Polish | T034–T037 | — |
| **Total** | **37 tasks** | |

**Parallel opportunities**: 15 tasks marked `[P]`

---

## Notes

- All tasks include explicit file paths per checklist format
- Verify tests fail before implementing each story phase
- After implementation, run full unit-test suite and coverage report; triage failures per constitution
- Code MUST satisfy SOLID, Clean Code, DRY, and KISS
- Commit after each task or logical group; stop at any checkpoint to validate story independently