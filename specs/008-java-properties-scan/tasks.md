---
description: "Task list for Scan Java .properties Files for Unprotected Secrets"
---

# Tasks: Scan Java `.properties` Files for Unprotected Secrets

**Input**: Design documents from `specs/008-java-properties-scan/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/properties-inspection.md, quickstart.md

**Tests**: Unit + coverage tasks are REQUIRED per user story; integration tests
are added because this change crosses the filesystem and packaging boundaries.

**Organization**: Tasks are grouped by user story. US1 is the MVP and carries the
bulk of the feature; US2–US4 are independently testable precision, configuration,
and safety increments layered on top.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1/US2/US3/US4 (setup, foundational, and polish carry no story label)
- Exact file paths are included in each task

## Path Conventions

Single project: `src/check_unprotected_keys/` and `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the existing project's quality gates run before changes begin

- [X] T001 Confirm dev environment: `pip install -e ".[dev]"` and verify `pytest`, `ruff check src/ tests/`, `ruff format --check src/ tests/`, and `pyright src/` all run green on the current tree

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Additive, inert plumbing that all stories build on. These changes do
not alter scan behavior until wired in by US1, so the existing suite stays green.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Add `property_name_patterns: tuple[str, ...]` to `ScanConfigSection` in src/check_unprotected_keys/config/models.py and to `SearchConfiguration`, plus optional `property_key: str | None = None` and an `output_line` property (`f"{file_path}#{property_key}"` when set, else `file_path`) to `KeyFinding`, in src/check_unprotected_keys/domain/models.py
- [X] T003 [P] Create src/check_unprotected_keys/domain/properties.py with the `PropertyEntry(key, value, line_number)` dataclass, the `PropertyValueKind` StrEnum (`EMPTY`/`PLACEHOLDER`/`ENCRYPTED`/`PATH_LIKE`/`LITERAL`), and `parse_properties(text) -> tuple[PropertyEntry, ...]` (comments `#`/`!`, blank skip, `=`/`:`/whitespace separators, backslash continuations, escapes `\=` `\:` `\t` `\n` `\\`, leading-whitespace trim) per contracts/properties-inspection.md §2
- [X] T004 [P] Add `inspect_text_for_key_material(text) -> ProtectionAssessment | None` to src/check_unprotected_keys/adapters/key_parsers.py that unescapes `\n`, encodes, and reuses `_collect_assessments` + `select_file_assessment` (no duplicated parsing)

**Checkpoint**: Shared types, the pure parser, and the key-material helper exist and are unit-importable; scan behavior is unchanged.

---

## Phase 3: User Story 1 - Detect Plaintext Secrets in Properties Files by Default (Priority: P1) 🎯 MVP

**Goal**: A default scan reads `.properties` files and reports, one stdout line
per offending property (`<path>#<key>`), plaintext credentials under
secret-named keys, inline unprotected key material, and unprotected key files
referenced by path.

**Independent Test**: Run a default scan over an `application.properties` with a
plaintext `db.password`, an inline PEM value, and an `ssl.key.file=keys/...`
reference to an unprotected key; confirm each is reported per-property and a
benign setting is not.

### Tests for User Story 1 (REQUIRED) ⚠️

- [X] T005 [P] [US1] Unit tests for `matches_secret_name` (case-insensitive substring over dotted keys) and `is_credential_like` literal acceptance (e.g. `hunter2`, `changeme`) plus `classify_value` LITERAL/PATH_LIKE in tests/unit/test_property_secrets.py
- [X] T006 [P] [US1] Unit tests for `parse_properties` (separators, comments, blank lines, continuations, escapes, key casing) in tests/unit/test_properties_parsing.py
- [X] T007 [P] [US1] Unit tests for the inspector: literal secret, inline key material (unconditional), referenced key file (relative-to-properties-dir, out-of-scope skip, missing skip), and `files_scanned` dedupe in tests/unit/test_properties_inspector.py
- [X] T008 [P] [US1] Integration test: end-to-end default scan emitting one stdout line per offending property, following a referenced key file, and counting it once in tests/integration/test_properties_scan_workflow.py

### Implementation for User Story 1

- [X] T009 [US1] Implement `matches_secret_name`, `classify_value` (LITERAL + PATH_LIKE branches), and `is_credential_like` (`len >= 6` AND Shannon entropy `>= 2.5`, with `MIN_SECRET_LENGTH`/`MIN_ENTROPY_BITS_PER_CHAR` constants) in src/check_unprotected_keys/domain/properties.py
- [X] T010 [US1] Create src/check_unprotected_keys/adapters/properties_inspector.py with `PropertyInspectionResult`, `PropertyFinding` (+ `PropertyFindingOrigin`), and `inspect_properties_file(path, *, name_patterns, scope, already_scanned)` implementing the decision order inline → name gate → path-follow → literal (contracts §3), reusing key_parsers for inline material and reference assessment, resolving relative paths against the file's directory, and enforcing `scope.canonical_root_set` (depends on T003, T004, T009)
- [X] T011 [US1] Add `*.properties` to `filename_patterns` and a commented `property_name_patterns` catalog (`password`, `passwd`, `pwd`, `pass`, `secret`, `private`, `key`, `token`, `credential`, `apikey`, `passphrase`) to src/check_unprotected_keys/resources/check-unprotected-keys.example.toml
- [X] T012 [US1] Extend `_load_packaged_defaults` to also return the property-name catalog and resolve `property_name_patterns` via `_resolve_ignore_list` (omit/empty/replace) in src/check_unprotected_keys/config/loader.py, wiring it into `SearchConfiguration` (depends on T002, T011)
- [X] T013 [US1] Route `.properties` candidates (by suffix) to the inspector in src/check_unprotected_keys/services/scan_service.py, emit one `KeyFinding` per `PropertyFinding` with `property_key` set and `UsageCategory.EMBEDDED_CONFIG_SECRET`, and maintain a scan-level canonical-path set so followed key files increment `files_scanned` exactly once (FR-013) (depends on T010, T012)
- [X] T014 [US1] Print `finding.output_line` in `emit_scan_result` in src/check_unprotected_keys/adapters/reporting.py and generalize the `EMBEDDED_CONFIG_SECRET` remediation wording from "private key" to "secret" in src/check_unprotected_keys/services/scan_service.py (depends on T013)
- [X] T015 [US1] Update `files_scanned`/malformed expectations in tests/integration/test_default_scan_workflow.py for the new `*.properties` default pattern (depends on T013)
- [X] T016 [US1] Run `pytest` for the US1 modules and confirm coverage stays ≥ 85%; triage any failure (test vs. implementation) and record the conclusion before editing

**Checkpoint**: US1 is fully functional — `.properties` plaintext secrets, inline key material, and referenced key files are detected and reported per-property by a default scan.

---

## Phase 4: User Story 2 - Avoid False Positives on Externalized or Encrypted Values (Priority: P1)

**Goal**: Properties whose secret-named values are placeholders, encrypted
wrappers, empty, or obvious non-secrets (booleans/integers/short) are never
reported, making the scan precise.

**Independent Test**: Run a scan over a file mixing `db.password=${DB_PASSWORD}`,
an `ENC(...)` value, `password=`, and `audit.password.min.length=8` alongside one
real plaintext secret; confirm only the real secret is reported.

### Tests for User Story 2 (REQUIRED) ⚠️

- [X] T017 [P] [US2] Unit tests for `classify_value` EMPTY/PLACEHOLDER (`${...}`, `@...@`, `#{...}`)/ENCRYPTED (`ENC(...)`) and for `is_credential_like` rejecting pure booleans/integers and sub-threshold values in tests/unit/test_property_secrets.py
- [X] T018 [P] [US2] Integration test asserting placeholder, encrypted, empty, and non-secret-literal entries produce no findings while a real plaintext secret in the same file is reported in tests/integration/test_properties_scan_workflow.py

### Implementation for User Story 2

- [X] T019 [US2] Extend `classify_value` with EMPTY/PLACEHOLDER/ENCRYPTED detection and add the boolean/integer/float rejection to `is_credential_like` in src/check_unprotected_keys/domain/properties.py
- [X] T020 [US2] Wire the non-secret value kinds into the inspector decision order so EMPTY/PLACEHOLDER/ENCRYPTED short-circuit before the literal/path branches (FR-005, contracts §3.3) in src/check_unprotected_keys/adapters/properties_inspector.py (depends on T019)
- [X] T021 [US2] Run `pytest` for US2 behavior and confirm coverage stays ≥ 85%; triage any failure before editing

**Checkpoint**: US1 and US2 both work — detection is now precise, with externalized/encrypted/empty/non-secret values suppressed.

---

## Phase 5: User Story 3 - Customize Which Property Names Are Treated as Secrets (Priority: P2)

**Goal**: Operators control the secret-name catalog through configuration with
omit/empty/replace semantics, documented in the shipped example.

**Independent Test**: Set `property_name_patterns = ["corp_token"]` and confirm
only `#corp_token` is reported; set `[]` and confirm no name-based findings;
omit the key and confirm packaged defaults apply.

### Tests for User Story 3 (REQUIRED) ⚠️

- [X] T022 [P] [US3] Unit tests for `property_name_patterns` resolution — omit → packaged default, `[]` → disabled, non-empty → replace — and that the packaged default catalog is non-empty, in tests/unit/test_config_loader.py

### Implementation for User Story 3

- [X] T023 [US3] Document `property_name_patterns` omit/empty/replace semantics in the header comments of src/check_unprotected_keys/resources/check-unprotected-keys.example.toml (mirroring the existing ignore-key wording)
- [X] T024 [US3] Add a README section covering `.properties` inspection and `property_name_patterns` customization in README.md
- [X] T025 [US3] Run `pytest` for US3 behavior and confirm coverage stays ≥ 85%; triage any failure before editing

**Checkpoint**: All P1+P2 detection and configuration behavior is functional.

---

## Phase 6: User Story 4 - Never Expose the Secret Value (Priority: P2)

**Goal**: Findings identify only the file path and property key; no secret value
ever reaches stdout, stderr, or logs.

**Independent Test**: Scan a file with a known plaintext secret value, capture
both streams, and assert the value string appears zero times while the path and
property key appear.

### Tests for User Story 4 (REQUIRED) ⚠️

- [X] T026 [US4] Tests asserting the secret value string is absent from both stdout and stderr while `output_line` carries `<path>#<key>`, covering reporting and remediation output, in tests/integration/test_properties_scan_workflow.py and tests/unit/test_reporting.py

### Implementation for User Story 4

- [X] T027 [US4] Audit `inspect_properties_file`, `KeyFinding` construction, reporting, and remediation to guarantee no property value is stored on a finding or emitted; add an assertion/guard where a value could otherwise reach output, across src/check_unprotected_keys/adapters/properties_inspector.py, src/check_unprotected_keys/services/scan_service.py, and src/check_unprotected_keys/adapters/reporting.py
- [X] T028 [US4] Run `pytest` for US4 behavior and confirm coverage stays ≥ 85%; triage any failure before editing

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final documentation, full-gate verification, and packaging

- [X] T029 [P] Final README.md pass: document the `<path>#<property key>` output form and the no-secret-values guarantee
- [X] T030 Run the full `pytest` suite with coverage report; triage any failing test (test logic vs. implementation logic), record the conclusion, then fix the test or code
- [X] T031 [P] Run `ruff check src/ tests/`, `ruff format --check src/ tests/`, and `pyright src/`; resolve all findings
- [X] T032 Packaging smoke test: run the CLI with `--print-example-config` and confirm output includes `*.properties` and the `property_name_patterns` catalog
- [X] T033 Execute the quickstart.md scenarios end-to-end and confirm expected outcomes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — the MVP; delivers most of the feature
- **US2 (Phase 4)**: Depends on US1 (extends the inspector and heuristic) — testable independently via its own fixtures
- **US3 (Phase 5)**: Depends on US1's loader/example-TOML work (T011, T012) — otherwise independent
- **US4 (Phase 6)**: Depends on US1's finding/reporting path — otherwise independent
- **Polish (Phase 7)**: Depends on all desired stories complete

### User Story Dependencies

- US1 is foundational to the others (it introduces the inspector, config wiring, and output path). US2/US3/US4 each add a separable facet (precision, configuration, no-leak) and are individually testable once US1 lands.

### Within Each User Story

- Write unit/integration tests first and confirm they fail before implementing
- Domain (`properties.py`) before adapter (`properties_inspector.py`) before service/reporting
- After implementing, run the suite + coverage and triage failures before editing

### Parallel Opportunities

- Foundational T002, T003, T004 are all `[P]` (distinct files)
- US1 tests T005, T006, T007, T008 are all `[P]` (distinct test files)
- US2 tests T017, T018 are `[P]`; Polish T029 and T031 are `[P]`
- Once Foundational completes, US1 begins; after US1, US2/US3/US4 can be split across developers

---

## Parallel Example: User Story 1

```bash
# Launch all US1 test authoring in parallel (distinct files):
Task: "Unit tests for secret-name match + credential heuristic in tests/unit/test_property_secrets.py"
Task: "Unit tests for parse_properties in tests/unit/test_properties_parsing.py"
Task: "Unit tests for the inspector in tests/unit/test_properties_inspector.py"
Task: "Integration test for end-to-end .properties scan in tests/integration/test_properties_scan_workflow.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational)
2. Complete Phase 3 (US1)
3. **STOP and VALIDATE**: run quickstart Scenarios 1 and 4 — plaintext secrets and referenced key files are reported per-property
4. This is a shippable increment: default `.properties` secret detection

### Incremental Delivery

1. Setup + Foundational → inert plumbing ready
2. US1 → MVP detection (may over-report externalized values) → demo
3. US2 → precision (suppress placeholders/encrypted/empty/non-secrets) → demo
4. US3 → configurable catalog + docs → demo
5. US4 → verified no-leak guarantee → demo

---

## Notes

- `[P]` = different files, no dependency on an incomplete task
- Inline key-material detection (FR-006) is intentionally unconditional (runs in US1); name-gated heuristics are added across US1/US2 — see research.md Decision 3
- Secret values must never be stored on a `KeyFinding` or emitted (Principle V / SC-003); US4 verifies this explicitly
- Code MUST satisfy SOLID, Clean Code, DRY, and KISS
- Commit after each task or logical group; stop at any checkpoint to validate
