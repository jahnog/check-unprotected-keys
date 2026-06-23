---
description: "Task list for Precise .properties Secret Detection"
---

# Tasks: Precise `.properties` Secret Detection (Near-Zero False Positives, Zero False Negatives)

**Input**: Design documents from `/specs/009-properties-detection-accuracy/`

**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/properties-detection.md, quickstart.md

**Tests**: Unit tests are REQUIRED for every user story (template policy). Integration tests are added where the change touches the scan workflow / packaging seams.

**Organization**: Tasks are grouped by user story (US1–US5 from spec.md) in priority order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths are included in each description

## Path Conventions

Single-package CLI layout: source under `src/check_unprotected_keys/`, tests under `tests/`.

## ⚠️ Shared-file reality (read first)

This feature is a refactor concentrated in two files —
`src/check_unprotected_keys/domain/properties.py` and
`src/check_unprotected_keys/adapters/properties_inspector.py`. The Foundational
phase builds the full decision-order **spine** with **safe stub** domain functions
(`match_value_signature → None`, `is_sample_placeholder → False`,
`is_non_secret_shape → False`, `placeholder_default → None`, tier-aware gate using
the base gate for both tiers). Each user story then **replaces its stub** with the
real rule plus tests, landing incrementally on a working engine. Tasks that edit
these two shared files are therefore **sequential** (never `[P]` among themselves);
`[P]` applies to the per-story test files and the corpus, which are distinct files.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Branch and test scaffolding for an existing project (no project init needed)

- [x] T001 Start the Git Flow feature branch manually (Constitution VI): `git flow feature start properties-detection-accuracy` (produces `feature/properties-detection-accuracy`); no other git action is automated
- [x] T002 [P] Create the corpus fixture package `tests/fixtures/properties_corpus/__init__.py` and an empty `tests/fixtures/properties_corpus/corpus.py` placeholder
- [x] T003 [P] Record a green baseline: run `pytest`, `ruff check src/ tests/`, `ruff format --check src/ tests/`, and `pyright src/` on the current tree and note the starting state

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared engine substrate every story builds on — tiers, tokenization, constants, config plumbing, and the rewritten decision-order spine with safe stubs

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add `KeyNameTier` StrEnum, `tokenize_key`, and `classify_key_tier` (substring-safe + token-exact catalogs, qualifier denylist; research Decisions 1–2), add the new module constants (`MIN_WEAK_LENGTH=12`, `MIN_WEAK_ENTROPY=3.0`, `BLOB_MIN_LENGTH=32`, `BLOB_MIN_ENTROPY=4.0`, catalogs, denylist, sample vocabulary, algorithm/keystore enum set), remove `matches_secret_name`, and add **safe stubs** for `match_value_signature`/`is_sample_placeholder`/`is_non_secret_shape`/`placeholder_default` plus a tier-aware `is_credential_like` signature (both tiers using the base gate for now) in `src/check_unprotected_keys/domain/properties.py`
- [x] T005 [P] Add `property_value_ignore: tuple[str, ...] = ()` to `ScanConfigSection` in `src/check_unprotected_keys/config/models.py` and to `SearchConfiguration` in `src/check_unprotected_keys/domain/models.py`
- [x] T006 Resolve `property_value_ignore` via the existing `_resolve_ignore_list` helper (default empty) in `src/check_unprotected_keys/config/loader.py` and thread it from `src/check_unprotected_keys/services/scan_service.py` into the inspector call (routing/accounting otherwise unchanged) — depends on T005
- [x] T007 Rewrite `_assess_entry` to the contract §3 decision order (inline material → value signature → value kind w/ placeholder-default re-assessment → key tier → path-like follow → literal sample/shape exclusions → tiered gate), add `VALUE_SIGNATURE` to `PropertyFindingOrigin`, and add the `value_ignore` parameter to `inspect_properties_file` in `src/check_unprotected_keys/adapters/properties_inspector.py` — depends on T004, T006
- [x] T008 Triage and update existing cases in `tests/unit/test_property_secrets.py` that encode the old loose/substring behavior or call the removed `matches_secret_name` (record the test-vs-implementation conclusion per NFR-002), and add `tokenize_key` / `classify_key_tier` (tiering + qualifier-demotion) unit tests
- [x] T009 Update `tests/unit/test_properties_inspector.py` for the new decision-order spine and the `value_ignore` parameter (triage any 008 expectation that changed per NFR-002)

**Checkpoint**: Engine spine builds and the suite is green with stubs (behavior ≈ 008 minus substring false matches). User stories can now begin.

---

## Phase 3: User Story 1 - Benign Secret-Named Configuration Is No Longer Reported (Priority: P1) 🎯 MVP

**Goal**: Ordinary config values under secret-sounding keys stop being reported (token-aware matching, qualifier demotion, sample/mask + shape exclusions, certificates).

**Independent Test**: Scan a `.properties` file of only benign secret-named entries (`signing.key.alias=primary`, `jwt.algorithm=RS256`, `cache.key.prefix=user:`, `db.password=changeme`, `db.host=localhost`, `key.serializer=...`, `compass.center=12.5`) → **zero** findings (quickstart Scenario A).

### Tests for User Story 1 (REQUIRED) ⚠️

- [x] T010 [P] [US1] Unit tests for `is_sample_placeholder` and tier-aware `is_non_secret_shape` (sample/mask vocab; dotted/class identifier; algorithm/keystore enum; bare host/IP/URL-without-credential; MIME; HTTP header; semantic version; public-key/cert markers) — positives and negatives — in `tests/unit/test_value_shapes.py`
- [x] T011 [P] [US1] Unit test that a `-----BEGIN CERTIFICATE-----` blob classifies as `PUBLIC_ONLY` in `tests/unit/test_key_parsers.py`
- [x] T012 [US1] Integration test: a benign secret-named `.properties` file yields 0 findings and exit code 0 (Scenario A) in `tests/integration/test_properties_scan_workflow.py`

### Implementation for User Story 1

- [x] T013 [US1] Implement `is_sample_placeholder` (Decision 5; honors `property_value_ignore`) replacing the stub in `src/check_unprotected_keys/domain/properties.py`
- [x] T014 [US1] Implement tier-aware `is_non_secret_shape` (Decision 6: always-excluded shapes + WEAK-only kebab/snake) replacing the stub in `src/check_unprotected_keys/domain/properties.py`
- [x] T015 [US1] Add a `-----BEGIN CERTIFICATE-----` → `PUBLIC_ONLY` branch in `_inspect_key_blob` in `src/check_unprotected_keys/adapters/key_parsers.py` (FR-010, DRY)
- [x] T016 [US1] Run the suite + coverage for the precision behaviors; confirm coverage stays ≥ 85% and Scenario A passes

**Checkpoint**: Benign secret-named config is silent; real-secret behavior unchanged.

---

## Phase 4: User Story 2 - Real Secrets Are Never Missed (Priority: P1)

**Goal**: Every plausible secret is reported even under benign key names (value-signature layer) and hardcoded placeholder defaults are assessed.

**Independent Test**: Scan a file with `datasource.url=jdbc:mysql://root:S3cr3t@db/app` (non-secret key), `notify.webhook=xoxb-...`, `db.password=${DB_PW:-fallbackSecret9}`, plus an inline PEM → all reported, no value leaked (quickstart Scenario B).

### Tests for User Story 2 (REQUIRED) ⚠️

- [x] T017 [P] [US2] Unit tests for `match_value_signature` across every family (AWS, GitHub, GitLab, Slack, Google, Stripe, Twilio, SendGrid, npm, OpenAI, JWT, embedded-credential URL, high-entropy blob) including negatives (bare URL, `jdbc://${u}:${p}@`, long identifiers/hashes) in `tests/unit/test_value_signatures.py`
- [x] T018 [P] [US2] Unit tests for `placeholder_default` extraction and defaulted-default assessment (`${VAR:-secret}` flagged, `${PORT:-8080}` not) in `tests/unit/test_property_placeholders.py`
- [x] T019 [US2] Integration test: embedded-credential URL under a non-secret key, a STRONG-key literal secret, and an inline PEM are all reported with **no secret value** in any stream (Scenario B) in `tests/integration/test_properties_scan_workflow.py` (after T012)

### Implementation for User Story 2

- [x] T020 [US2] Implement the `ValueSignature` enum and `match_value_signature` (curated, anchored, length-bounded catalog; embedded-credential URL rule rejecting placeholder `pw`; high-entropy-blob rule) replacing the stub in `src/check_unprotected_keys/domain/properties.py`
- [x] T021 [US2] Implement `placeholder_default` and wire the defaulted-placeholder re-assessment in `src/check_unprotected_keys/domain/properties.py` and the §3.3 branch of `_assess_entry` in `src/check_unprotected_keys/adapters/properties_inspector.py`
- [x] T022 [US2] Run the suite + coverage for recall behaviors; assert no property value appears in captured stdout/stderr (SC-004)

**Checkpoint**: US1 + US2 (both P1) deliver the precision-and-recall MVP.

---

## Phase 5: User Story 3 - Confidence Is Tiered by Key-Name Strength (Priority: P2)

**Goal**: STRONG keys keep catching word-like passwords; WEAK/ambiguous keys require high-entropy/length or a signature.

**Independent Test**: The same medium-strength value flags under `account.password` (STRONG) but not under `routing.key` (WEAK); a high-entropy value flags under both.

### Tests for User Story 3 (REQUIRED) ⚠️

- [x] T023 [P] [US3] Unit tests for tier-aware `is_credential_like` boundaries (STRONG `len≥6 ∧ H≥2.5`; WEAK `len≥12 ∧ H≥3.0`; same value under STRONG vs WEAK key) in `tests/unit/test_tiered_gate.py`

### Implementation for User Story 3

- [x] T024 [US3] Implement the tier-aware `is_credential_like` (STRONG base gate / WEAK strict gate; Decision 4) replacing the base-only stub in `src/check_unprotected_keys/domain/properties.py`
- [x] T025 [US3] Run the suite + coverage for the tier boundary cases; confirm coverage ≥ 85%

**Checkpoint**: The tier engine behind US1/US2 is explicit and independently verified.

---

## Phase 6: User Story 4 - Good-Practice Externalization and Encryption Are Recognized (Priority: P2)

**Goal**: The broad set of reference and encryption forms is recognized as non-findings.

**Independent Test**: Scan a file using `{cipher}…`, `{ENC(…)}`, `{{…}}`, `vault:`/`awskms:`/`sops:`/`env:` schemes, and `${PORT:-8080}` → no findings (quickstart Scenario C).

### Tests for User Story 4 (REQUIRED) ⚠️

- [x] T026 [P] [US4] Unit tests for widened `classify_value` PLACEHOLDER (`{{…}}`, `$ENV{…}`, `$(…)`, `%(…)s`, reference schemes) and ENCRYPTED (`{cipher}…`, `{ENC(…)}`) recognition in `tests/unit/test_property_kinds.py`

### Implementation for User Story 4

- [x] T027 [US4] Implement the widened PLACEHOLDER/ENCRYPTED branches in `classify_value` in `src/check_unprotected_keys/domain/properties.py` (Decision 7)
- [x] T028 [US4] Integration test: externalized/encrypted/cert values yield 0 findings (Scenario C) in `tests/integration/test_properties_scan_workflow.py` (after T019)

**Checkpoint**: Correctly-secured configuration never appears in results.

---

## Phase 7: User Story 5 - Accuracy Is Measured and Enforced (Priority: P2)

**Goal**: A labeled corpus enforces recall = 100% on MUST-FLAG and FP-rate ≤ target on MUST-NOT-FLAG.

**Independent Test**: `pytest tests/unit/test_properties_accuracy.py` passes; reintroducing any FP/FN fails it (quickstart Scenario D).

### Tests for User Story 5 (REQUIRED) ⚠️

- [x] T029 [P] [US5] Build the labeled corpus — `MUST_FLAG` (true secrets across strong/weak/none keys, every signature family, embedded-credential URLs, inline PEM, referenced key files, hardcoded placeholder defaults) and `MUST_NOT_FLAG` (every FP class: container words, qualified keys, identifiers, enums, hosts/URLs, durations, MIME, headers, versions, placeholders, encrypted wrappers, sample/mask tokens, public keys, certificates) — in `tests/fixtures/properties_corpus/corpus.py`
- [x] T030 [US5] Implement the parametrized accuracy test asserting recall == 100% on `MUST_FLAG` and FP-rate ≤ 2% (0 on the curated core) on `MUST_NOT_FLAG`, comparing booleans only (no value emitted), in `tests/unit/test_properties_accuracy.py`

### Implementation for User Story 5

- [x] T031 [US5] Tune the thresholds/catalogs (WEAK gate, blob bounds, denylist, sample vocab, signatures) in `src/check_unprotected_keys/domain/properties.py` against the corpus until both gates pass; record any threshold change and its rationale

**Checkpoint**: The near-zero-FP / zero-FN guarantee is enforced and regression-proof.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, packaging, and the full quality gate

- [x] T032 [P] Update the `property_name_patterns` comment block in `src/check_unprotected_keys/resources/check-unprotected-keys.example.toml` (token-aware matching, tiering, the unconditional value-signature layer, the optional `property_value_ignore` key) and update `README.md` to match
- [x] T033 Run the full `pytest` + coverage report; triage any failing test (test logic vs. implementation logic), record the conclusion, and only then fix the test or the code (Constitution III, NFR-002)
- [x] T034 [P] Run `ruff check src/ tests/`, `ruff format --check src/ tests/`, and `pyright src/`; resolve any findings
- [x] T035 Smoke-test the packaged config: `check-unprotected-keys --print-example-config`
- [x] T036 Execute quickstart.md Scenarios A–D end-to-end and confirm the expected outcomes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**
- **User Stories (Phase 3–7)**: all depend on Foundational; the two P1 stories (US1, US2) form the MVP
- **Polish (Phase 8)**: depends on all targeted stories being complete

### User Story Dependencies

- **US1 (P1)** and **US2 (P1)**: both start after Foundational; independent in *behavior*, but both edit `domain/properties.py` and `properties_inspector.py`, so order their shared-file edits sequentially
- **US3 (P2)**: replaces the foundational base-only gate stub with the real tiered gate; behaviorally sharpens US1/US2 (which run on the stub until then)
- **US4 (P2)**: widens `classify_value`; independent of US1–US3
- **US5 (P2)**: depends on US1–US4 being implemented so the corpus reflects final behavior; T031 tuning may touch `domain/properties.py`

### Within Each User Story

- Write the story's unit tests first and confirm they fail on the stub, then implement the rule
- After implementing, run the full suite + coverage; triage any failure (test vs. implementation) before changing test or code
- Domain rule before adapter wiring; pure functions before integration tests

### Shared-file serialization (cannot be `[P]`)

- `domain/properties.py`: T004 → T013 → T014 → T020 → T021 → T024 → T027 → T031
- `adapters/properties_inspector.py`: T007 → T021
- `tests/integration/test_properties_scan_workflow.py`: T012 → T019 → T028

### Parallel Opportunities

- Setup: T002, T003 in parallel
- Foundational: T005 in parallel with T004 (different files); T008/T009 after the spine lands
- Per-story **test files are distinct and `[P]`**: T010/T011, T017/T018, T023, T026, T029 can each be authored in parallel with other stories' test files
- Polish: T032 and T034 in parallel

---

## Parallel Example: User Story 1

```bash
# Author US1 test files in parallel (distinct files):
Task: "Unit tests for is_sample_placeholder/is_non_secret_shape in tests/unit/test_value_shapes.py"
Task: "Unit test certificate → PUBLIC_ONLY in tests/unit/test_key_parsers.py"
# Then implement sequentially on the shared domain file:
Task: "Implement is_sample_placeholder in domain/properties.py"
Task: "Implement is_non_secret_shape in domain/properties.py"   # after the previous edit
```

---

## Implementation Strategy

### MVP (the two P1 stories)

1. Phase 1 Setup → Phase 2 Foundational (spine + stubs; suite green)
2. Phase 3 US1 (precision) → validate Scenario A independently
3. Phase 4 US2 (recall) → validate Scenario B independently
4. **STOP and VALIDATE**: benign config is silent AND every planted secret is caught with no value leak — this is the shippable MVP that satisfies the user's "near-zero FP, zero FN" ask

### Incremental Delivery

5. US3 sharpens the tier gate → US4 widens externalization recognition → US5 locks the guarantee with the enforced corpus
6. Phase 8 polish: docs, packaging smoke, full quality gate, quickstart run

---

## Notes

- `[P]` = different files, no incomplete-task dependency; the two shared engine files force sequential edits (see Shared-file serialization)
- `[Story]` label maps each task to its user story for traceability
- Verify each story's tests fail on the foundational stub before implementing the real rule
- No property value is ever stored on a finding, emitted to any stream, or asserted by value in tests (Principle V, SC-004)
- Code MUST satisfy SOLID, Clean Code, DRY, KISS; commits and the PR are authored manually by the user (Constitution VI)
