# Tasks: Search Bases and Directory Hints (Broad Discovery)

**Input**: Design documents from `/specs/005-search-bases-and-directory-hints/`

**Prerequisites**: spec.md (required), data-model.md, research.md, plan.md, quickstart.md (can be drafted in parallel), checklists/requirements.md, contracts/search-bases-semantics.md

**Tests**: Unit, contract, and integration test work is REQUIRED for the new resolution, promotion, pruning, and compat paths (NFR-002, SC-006). Pre-existing start-folder and default-scan tests provide strong regression coverage via the legacy compat path and narrow usage.

**Organization**: Tasks are grouped by user story (see spec.md) to enable independent implementation and verification. Phases follow the established pattern (Setup → Foundational → per-story → Polish).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files or independent concerns)
- **[Story]**: Which user story this task belongs to (US1 = bases, US2 = directory hints/promotion, US3 = pruning, US4 = compat/migration, US5 = start-folder)
- Include exact file paths

## Path Conventions (per plan.md)

- Config: `src/check_unprotected_keys/config/models.py`, `src/check_unprotected_keys/config/loader.py`, `src/check_unprotected_keys/resources/check-unprotected-keys.example.toml`
- Scope / Discovery: `src/check_unprotected_keys/adapters/filesystem.py`, `src/check_unprotected_keys/domain/scope.py`, `src/check_unprotected_keys/domain/models.py`
- Tests: `tests/unit/test_scope_resolution.py`, `tests/contract/test_config_contract.py`, `tests/integration/test_default_scan_workflow.py` (or new), `tests/support/fixture_builders.py`
- Docs: everything under `specs/005-search-bases-and-directory-hints/`, plus light updates to README.md and the 001-era contracts if references become stale
- Cleanup: removal of `src/find_unencrypted_keys/`

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Review plan.md, research.md, spec.md, data-model.md, and contracts/search-bases-semantics.md to confirm the semantic shift (bases vs. old folder patterns), the three new config fields, promotion + pruning as first-class concepts, and the compat strategy
- [ ] T002 [P] Run `uv sync --extra dev` and confirm the full quality gate commands from plan.md execute cleanly on a clean tree
- [ ] T003 [P] Confirm that `specs/005-search-bases-and-directory-hints/` now contains the required artifacts (spec, data-model, research, plan, quickstart draft, checklists, contracts supplement) and that the directory name follows the `NNN-slug` convention
- [ ] T004 [P] Grep the repository (excluding the now-deleted tree) to reconfirm zero live references to `find_unencrypted_keys` before the removal step

**Checkpoint**: Setup complete — the team understands the new mental model and the environment is ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user-story implementation that touches production behavior should begin until this phase is complete.

- [ ] T005 Update `src/check_unprotected_keys/config/models.py`:
  - Extend `ScanConfigSection` and `SearchConfiguration` with `base_folders`, `directory_names`, `ignore_directories` (tuples of str).
  - Keep `folder_patterns` in the dataclass for the compat bridge (or document the internal mapping).
- [ ] T006 Update `src/check_unprotected_keys/config/loader.py`:
  - Accept legacy `folder_patterns` when `base_folders` is absent.
  - Implement validation for the three new keys (non-empty when the primary key is used, strings, trimmed, no blanks).
  - Populate the new fields on `SearchConfiguration`.
  - As a convenience, contribute simple bare names from a legacy `folder_patterns` list into the effective directory hints.
- [ ] T007 Update the packaged example in `src/check_unprotected_keys/resources/check-unprotected-keys.example.toml`:
  - Introduce `base_folders`, `directory_names`, and `ignore_directories` with good curated content and explanatory comments.
  - Keep the file valid and useful as a "start here" config.
- [ ] T008 [P] Read the existing `tests/contract/test_config_contract.py` and `tests/unit/test_config_loader.py` to understand current validation test patterns for pattern arrays.
- [ ] T009 Add (or extend) a fixture builder helper in `tests/support/fixture_builders.py` that can create a workspace with:
  - A configurable base root.
  - Key material at multiple depths inside hinted directories (e.g. `apps/api/secrets/db.key`, `services/bar/deploy/id_ed25519`).
  - Noise directories (e.g. `node_modules`, `.git`, `target`) containing files that would otherwise match filename patterns.
  - A few files with matching filename patterns that live outside any hinted directory (to prove base walking works).
- [ ] T010 [P] Review `tests/unit/test_scope_resolution.py` and `tests/integration/test_default_scan_workflow.py` to decide the best home for the first promotion / pruning unit tests vs. integration scenarios.
- [ ] T011 Confirm that the dead `src/find_unencrypted_keys/` tree can be removed with `rm -rf` (or `git rm -r`) with no other changes required (imports, pyproject packaging, scripts, or tests).

**Checkpoint**: Foundation ready — config model + loader + example are updated and the test support fixtures exist. User story work can now proceed (config work can be done in parallel with early discovery work).

---

## Phase 3: User Story 1 - Search Bases Define Authorized Trees (Priority: P1) 🎯

**Goal**: Make `base_folders` (and legacy `folder_patterns` via compat) the source of ancestor trees that are walked for filename matches at any depth.

### Tests for User Story 1 (REQUIRED)

- [ ] T012 [P] [US1] Add unit tests in `tests/unit/test_scope_resolution.py` (or a new `test_base_expansion.py` if preferred) that directly exercise base expansion for relative, absolute, `~`, and simple glob cases and verify the resulting roots.
- [ ] T013 [US1] Add an integration scenario (in `tests/integration/test_default_scan_workflow.py` or a new `test_broad_base_discovery.py`) that configures a single broad base over a workspace containing key material at depth (both hinted and non-hinted locations) and asserts that candidates are discovered from multiple depths and that `files_scanned` is greater than a narrow-config equivalent.
- [ ] T014 [P] [US1] Run the pre-existing default-scan and start-folder contract tests (`tests/contract/test_cli_default_scan_contract.py` and `test_cli_start_folder_contract.py`) and confirm they still pass (they exercise narrow "folder_patterns" values via the compat path).

### Implementation / Verification for User Story 1

- [ ] T015 Extend `resolve_effective_scope` (and/or extract `resolve_bases`) in `src/check_unprotected_keys/adapters/filesystem.py` so that the configured base entries are expanded exactly like the old folder patterns (reuse `_expand_folder_pattern` or a renamed helper).
- [ ] T016 Ensure that the bases themselves (after narrowing) are included in the `root_directories` passed to `discover_candidate_files` (so filename patterns catch material at arbitrary depth under the base).
- [ ] T017 Update any places that previously read `configuration.folder_patterns` for logging or diagnostics to prefer the new `base_folders` name while still supporting the legacy field during the transition.
- [ ] T018 Verify via test that a base of "." (or a temp workspace root) + the normal filename patterns causes files deep in the tree whose names match `id_*`, `*.pem`, `.env*`, etc. to be evaluated (even if their parent dir is not in any hint list).

**Checkpoint**: US1 (bases as the primary broad mechanism) is independently verifiable. Narrow legacy configs still work.

---

## Phase 4: User Story 2 - Directory Name Hints Enable Automatic Promotion (Priority: P1)

**Goal**: Implement automatic discovery of subdirectories whose basename matches entries in `directory_names`, union them with the bases, and enrich `matched_folder_pattern` with hint provenance.

### Tests for User Story 2 (REQUIRED)

- [ ] T019 [P] [US2] Add unit tests for the promotion helper (new function `discover_directory_hints_under_bases` or equivalent) covering:
  - Shallow and deep nesting.
  - Multiple hints.
  - Deduplication when a promoted dir coincides with a base.
  - No promotion when the name does not appear.
- [ ] T020 [US2] In the broad-base integration test, assert that candidates reached via a promoted directory carry a `matched_folder_pattern` value that mentions the hint (e.g. contains "hint:secrets" or equivalent) and that usage inference still works for those candidates.
- [ ] T021 [P] [US2] Add a test that a file whose name matches a filename pattern but whose parent is *not* a hinted directory is still discovered when under a base (proves bases provide coverage beyond hints).

### Implementation / Verification for User Story 2

- [ ] T022 Implement the promotion discovery logic (in `filesystem.py`, possibly calling helpers in `domain/scope.py`). It must run after base expansion and after start-folder narrowing of the bases.
- [ ] T023 During candidate enumeration (or in the promotion pass), enrich the `matched_folder_pattern` stored on `CandidateFile` (and on `MalformedScanIssue`) with base + hint provenance while keeping the field a string.
- [ ] T024 Make sure `infer_usage_category` (in `services/scan_service.py`) and the malformed recording path continue to receive usable strings (they already do lowercasing + substring checks).
- [ ] T025 Verify that promotion works when the same directory name appears under different bases and that canonical dedup still collapses them.

**Checkpoint**: US1 + US2 together deliver the core "broad + auto-promoted" experience. A single base + a realistic directory_names list now finds material at depth without any `**/` in the user's config.

---

## Phase 5: User Story 3 - Pruning Makes Broad Bases Practical (Priority: P1)

**Goal**: Implement `ignore_directories` (defaults + user override) and ensure pruning is applied uniformly to both promotion discovery and the main candidate walk.

### Tests for User Story 3 (REQUIRED)

- [ ] T026 [P] [US3] Add unit tests that exercise the pruning filter with the default set and with a user override; assert that directories whose basename matches an ignore entry are never returned as promoted roots and that `os.walk` (or the discovery helper) never descends into them.
- [ ] T027 [US3] Using the enhanced fixture builder from Phase 2, run a broad-base integration test with noise directories present and assert that zero candidates (and zero promotion) come from inside any ignored subtree, while real material elsewhere under the same base *is* found.
- [ ] T028 [P] [US3] Confirm that a directory name that appears in both `directory_names` and `ignore_directories` is ignored (ignores win).

### Implementation / Verification for User Story 3

- [ ] T029 Add pruning logic (topdown `dirnames` mutation in `os.walk`, or pre-filtering of glob results for the promotion phase). Apply it in both the promotion helper and in `discover_candidate_files` (or centralize it).
- [ ] T030 Wire the active ignore list (defaults union/replace user list) into the resolver and discovery functions. Make the default list live in one obvious place (the resources example + a constant or loader helper).
- [ ] T031 Update the on_error / DiscoveryIssue paths if pruning can surface new unreadable situations (unlikely, but keep consistent with existing error collection).

**Checkpoint**: US3 complete. Broad bases are now practical because common noise is pruned by default.

---

## Phase 6: User Story 4 - Backward Compatibility and Migration (Priority: P2)

**Goal**: Ensure legacy `folder_patterns` configs continue to work (and even gain broader discovery via the auto-hint contribution) and provide a clean migration story.

### Tests for User Story 4 (REQUIRED)

- [ ] T032 [P] [US4] Add unit / contract tests that load a config containing only the legacy `folder_patterns` key (no `base_folders`) and verify that it produces a valid `SearchConfiguration` and a successful scan.
- [ ] T033 [US4] In the compat test, verify that simple bare names from the legacy list are also treated as directory hints (so an old-style list of "secrets", "deploy", etc. automatically gets promotion).
- [ ] T034 [P] [US4] Run the full existing contract test suite for config loading (`tests/contract/test_config_contract.py`) and confirm no regressions for both legacy and new-style configs.
- [ ] T035 [US4] Add a quickstart or integration scenario that shows the "before/after" of a minimal migration (old flat list → new `base_folders` + `directory_names` + `ignore_directories`) producing equivalent or better results.

### Implementation / Verification for User Story 4

- [ ] T036 Finalize and test the compat bridge in the loader (legacy key → bases + auto-contributed hints).
- [ ] T037 Update the header comments in the packaged example and add a short "Migrating from older versions" section (or reference to the new quickstart/research).
- [ ] T038 Ensure that when both legacy and new keys are present the precedence is deterministic and documented (in contracts + research).

**Checkpoint**: US4 complete. Existing users can upgrade without breakage; the migration path is clear and tested.

---

## Phase 7: User Story 5 - Start-Folder Continues to Narrow Correctly (Priority: P2)

**Goal**: Verify that `--start-folder` (already heavily tested) still works correctly over the new base + promotion model.

### Tests for User Story 5 (REQUIRED)

- [ ] T039 [P] [US5] Run all pre-existing start-folder contract and integration tests (`tests/contract/test_cli_start_folder_contract.py`, `tests/integration/test_start_folder_scan.py`) and confirm they pass unchanged (or with only trivial updates for new field names in diagnostics).
- [ ] T040 [US5] Add at least one new start-folder scenario (contract or integration) that uses a broad base + hints and supplies a `--start-folder` pointing at a subtree containing only some of the hinted material; assert that only candidates under the start folder are reported and that `files_scanned` reflects the narrowing.
- [ ] T041 [P] [US5] Add a unit test in the scope module that passes a start folder to the full `resolve_effective_scope` (with bases + hints) and verifies that promotion search is also limited to the start-folder subtree.

### Implementation / Verification for User Story 5

- [ ] T042 Extend or reuse `narrow_root_directories` (in `domain/scope.py`) so it correctly filters both the base list and the subsequently discovered promoted list.
- [ ] T043 Ensure that promotion discovery receives the (already narrowed) bases when a start folder is present.
- [ ] T044 Verify that the classic "start folder replaces a parent base" behavior still works when a configured base is an ancestor of the supplied start folder.

**Checkpoint**: US5 complete. The investment from spec 004 is protected; broad discovery does not regress targeted investigations.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T045 [P] Delete the dead tree: `rm -rf src/find_unencrypted_keys` (or the git equivalent). Re-run a full grep to confirm zero references. Commit the removal as a separate logical change if desired.
- [ ] T046 [P] Run the full project quality gates exactly as documented in plan.md.
- [ ] T047 Execute the runnable scenarios from `specs/005-search-bases-and-directory-hints/quickstart.md` (unit tests for the new resolver, broad base + promotion, pruning verification, start-folder narrowing over the new model, legacy compat, and the final gate run).
- [ ] T048 Review overall coverage for the changed modules (`config/*`, `adapters/filesystem.py`, `domain/scope.py`). Add any missing unit assertions needed to keep the suite above 85% branch coverage.
- [ ] T049 [P] Lightly update README.md (and the 001 config contract if it contains hard examples of the old "high-signal only" philosophy) to reflect the new controllable-breadth model. Keep changes minimal and reference the new spec.
- [ ] T050 Run a final full `uv run --extra dev pytest` (or CI-equivalent) and confirm no unrelated regressions.
- [ ] T051 (Optional but recommended) Update CHANGELOG.md with a brief entry for the feature + the duplicate package cleanup.
- [ ] T052 Commit the completed work with a message that references the feature branch and the primary user stories (US1–US3 especially).

---

## Dependencies & Execution Order

- Phase 1 (Setup) → no blockers.
- Phase 2 (Foundational) → blocks most production changes but can be worked while early test-fixture and research reading happen.
- US1 (bases) can begin as soon as the config model accepts the new key and the resolver can expand bases.
- US2 (hints + promotion) depends on US1 having bases resolved.
- US3 (pruning) can be developed in parallel with US2 once the promotion helper skeleton exists; it affects both promotion and the main walk.
- US4 (compat) can be developed early (mostly loader work) and provides a safety net for running old tests.
- US5 (start-folder) can be verified as soon as the resolver accepts a start folder; it largely reuses 004 tests.
- Polish (including the deletion of the dead tree) happens after the stories that exercise the new code paths are passing.

Parallel opportunities exist within phases (different test files, config work vs. discovery work, reading vs. writing).

**MVP recommendation**: Complete Phases 1–2, then US1 + US2 + US3 (the P1 stories) + the compat tests from US4. At that point a broad base + hints + pruning is demonstrably working and all existing narrow/start-folder tests still pass. Then finish US5 verification + polish.

All tasks should use exact file paths and be specific enough that an LLM or developer can execute them with only the spec artifacts as context.

**Total tasks**: ~52 (T001–T052). The majority of new production code is in the config layer and `adapters/filesystem.py`; the majority of new test code is in unit + a focused integration scenario for broad discovery. The dead-tree cleanup is a one-line removal after confirmation.