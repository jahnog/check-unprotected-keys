# Feature Specification: Code Quality Audit — Errors, Maintainability, Expandability, Testability

**Feature Branch**: `feature/code-quality-audit`

**Created**: 2026-07-08

**Status**: Draft

**Input**: User description: "Check the application for errors and maintainability, expandability and testability improvements" + amendment: "add the creation of a detailed implementation plan to fix the findings"

## User Scenarios & Testing *(mandatory)*

### User Story 0 - Detailed remediation plan exists before any fix (Priority: P0)

As the project owner, before any finding is fixed I have a detailed, reviewable
implementation plan that maps every audit finding to a concrete remediation:
what will change, in what order, how the change is verified, and what is
explicitly deferred. The plan is the gate for implementation — no fix work
starts until the plan covers all findings in Stories 1–4 and passes the
project's constitution check.

**Why this priority**: The remediation touches error handling, extension
seams, and core orchestration of a security tool. An agreed plan prevents
piecemeal refactoring, fixes an order of work that protects behavior (tests
strengthened before structure changes), and gives the owner a review point
before code churn begins.

**Independent Test**: Open the plan document and verify a traceability check:
every functional requirement and audit finding in this spec appears in the
plan with a remediation approach, sequencing, and verification method; the
plan's constitution-check section passes.

**Acceptance Scenarios**:

1. **Given** this specification's findings and requirements, **When** the plan
   is produced, **Then** each of FR-001 through FR-013 is traceable to at
   least one planned remediation step with a named verification method.
2. **Given** the plan, **When** it sequences the work, **Then** behavior-
   preserving safeguards (regression baseline, new tests) are scheduled before
   the structural refactors they protect.
3. **Given** the plan, **When** it is reviewed against the project
   constitution, **Then** architecture boundaries, test strategy, coverage
   expectations, quality commands, and packaging impact are all documented
   and no unjustified violations remain.
4. **Given** an approved plan, **When** implementation begins, **Then** the
   work items derive from the plan rather than ad-hoc choices.

---

### User Story 1 - Silent failures become observable (Priority: P1)

As an operator running a security scan, I need the tool to never silently drop
files or directories it could not inspect. Today, several traversal and
inspection steps swallow operating-system errors without any trace: a directory
the scanner cannot read is skipped with no diagnostic, so a scan can report
"clean" while whole subtrees were never examined. For a tool whose purpose is
to find unprotected secrets, an unexamined location is a false sense of safety.

**Why this priority**: This is a correctness/trust defect, not a style issue.
Every other improvement is worthless if the scan result itself can be
misleading. It is also independently shippable: surfacing skipped locations
requires no structural change.

**Independent Test**: Run a scan over a tree containing an unreadable
directory and an unreadable file; the scan completes, and the report/output
explicitly lists each location that could not be inspected and why.

**Acceptance Scenarios**:

1. **Given** a scan root containing a directory the process cannot read,
   **When** the scan runs, **Then** the scan completes and the output includes
   a warning identifying that directory and the reason it was skipped.
2. **Given** a candidate file that disappears or becomes unreadable mid-scan,
   **When** the scan runs, **Then** the file is reported as not-inspected with
   a reason, rather than being silently absent from results.
3. **Given** a fully readable tree, **When** the scan runs, **Then** no
   skip warnings are emitted and existing output is unchanged.

---

### User Story 2 - New detection capability plugs in without editing stable code (Priority: P2)

As a maintainer extending the tool (e.g., adding a new key format or a new
detection rule for property values), I can add the new capability as a
self-contained unit that registers into an extension point, instead of editing
existing dispatch chains. Today, adding a key format means editing a
byte-prefix if/else chain; adding a usage category means editing two parallel
enum-driven chains plus reporting; adding a properties detection layer means
inserting a step into a fixed numbered pipeline.

**Why this priority**: The project's history shows detection scope grows
release over release (key patterns → properties → i18n accuracy). Each growth
step currently touches stable, tested code, which is the main source of
regression risk going forward.

**Independent Test**: Add a trivial new detector (e.g., a dummy key format or
rule) using only the extension point — no modification to existing detection
units — and verify it participates in a scan; remove it and verify behavior
returns to baseline.

**Acceptance Scenarios**:

1. **Given** the refactored detection seams, **When** a maintainer adds a new
   key-format recognizer, **Then** no existing recognizer or dispatch logic is
   modified and all pre-existing tests still pass.
2. **Given** a new usage category, **When** it is introduced, **Then** its
   classification rule and its remediation text are defined in one place, and
   no other category's logic is edited.
3. **Given** the existing supported formats and rules, **When** the suite runs
   after the refactor, **Then** scan results over the regression fixtures are
   identical to pre-refactor results.

---

### User Story 3 - Core orchestration and parsers are directly unit-testable (Priority: P3)

As a maintainer, I can unit-test the scan orchestrator with fake collaborators
and test each key parser directly. Today the orchestrator reaches into
filesystem, parsing, and inspection modules through hard-wired references, so
its branches (directory-visit limits, malformed/unreadable state transitions)
can only be exercised through slow end-to-end tests, and the key-format
parsers have no dedicated tests — their edge cases are covered only
incidentally.

**Why this priority**: Testability gaps compound: every future change to
orchestration or parsing is verified only indirectly. Fixing this makes User
Story 2's extension points provable and cheap to keep proving.

**Independent Test**: Write a unit test that drives the orchestrator with
in-memory fakes (no real filesystem) through its limit/error branches, and
dedicated parser tests covering malformed, truncated, and encrypted inputs.

**Acceptance Scenarios**:

1. **Given** the orchestrator with substituted fake collaborators, **When**
   its unit tests run, **Then** the directory-limit and error-state branches
   are exercised without touching the real filesystem.
2. **Given** dedicated parser tests, **When** the coverage report runs,
   **Then** each supported key format's parse paths (valid, encrypted,
   malformed, truncated) are covered by named tests.

---

### User Story 4 - Oversized and duplicated internals are consolidated (Priority: P4)

As a maintainer reading the code, each module has one clear responsibility and
each fact lives in one place. Today one domain module of ~1,000 lines mixes
six concerns and embeds large hard-coded data tables; a ~95-line prose-
generating block hard-codes remediation text; a traversal safety limit default
is declared in three separate places; two configuration-validation routines
are near-duplicates; and a configuration section type mirrors another type
field-by-field.

**Why this priority**: Pure maintainability. Valuable, but it changes no
observable behavior, so it is safest to do last on top of the strengthened
test base from Stories 1–3.

**Independent Test**: After consolidation, the full regression suite passes
with identical scan results; each previously duplicated fact (e.g., the
traversal limit default) can be changed in exactly one place and takes effect
everywhere.

**Acceptance Scenarios**:

1. **Given** the consolidated modules, **When** the traversal limit default is
   changed at its single source, **Then** configuration loading, defaults, and
   traversal all observe the new value.
2. **Given** the split-up domain module, **When** a maintainer looks for
   language-code data, detection tiers, or bundle detection, **Then** each
   lives in its own clearly named unit, and the large data tables are
   separated from logic.
3. **Given** the consolidation, **When** the regression fixtures are scanned,
   **Then** results are identical to pre-refactor output.

---

### Edge Cases

- What happens when a directory becomes unreadable between discovery and
  inspection? It must appear as a skipped location with a reason, not vanish.
- How does the system handle a file whose text decoding is ambiguous (not
  valid in the primary encoding)? Decoding fallbacks must not corrupt content
  in a way that misclassifies a real unprotected key as merely malformed; when
  content is decoded lossily, the result must be flagged as uncertain rather
  than asserted.
- What happens when two extension-point registrations claim the same input?
  Resolution order must be deterministic and documented.
- What happens when the visited-directory safety limit is reached? The scan
  must report that the limit truncated traversal rather than ending silently.
- Candidate lifecycle states that no code path can reach must be either wired
  to real transitions or removed, so reported states always reflect reality.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The scan MUST record every location (directory or file) it
  discovers but cannot inspect, with an actionable reason, and surface these
  in the scan output; no traversal or inspection error may be discarded
  without a trace.
- **FR-002**: The scan MUST explicitly report when the directory-visit safety
  limit truncates traversal.
- **FR-003**: Scan results for all existing regression fixtures MUST remain
  identical before and after the improvements, except for the new
  skipped-location and truncation reporting.
- **FR-004**: Adding a new key-format recognizer MUST be possible without
  modifying existing recognizers or the dispatch that selects among them.
- **FR-005**: Adding a new usage category MUST require defining its
  classification rule and remediation guidance in a single authoritative
  place; no parallel per-category chains may need coordinated edits.
- **FR-006**: Adding a new properties-detection rule MUST be possible by
  registering it, without editing the fixed assessment pipeline's existing
  steps.
- **FR-007**: The scan orchestrator MUST depend on its collaborators
  (traversal, parsing, inspection, reporting) through substitutable seams so
  each branch of its logic can be unit-tested with fakes.
- **FR-008**: Each supported key format's parsing paths (valid, encrypted,
  malformed, truncated inputs) MUST be covered by dedicated unit tests.
- **FR-009**: Every configurable or safety-relevant default (e.g., the
  directory-visit limit) MUST have exactly one authoritative definition.
- **FR-010**: The oversized properties domain module MUST be decomposed into
  cohesive units with the embedded reference data tables separated from
  detection logic, preserving behavior.
- **FR-011**: Duplicated configuration-validation logic and field-by-field
  mirrored configuration types MUST be consolidated to a single source each.
- **FR-012**: Text decoding of inspected content MUST NOT allow lossy
  character replacement to change a classification from "unprotected key"
  to "malformed"; lossy decoding MUST be treated as an uncertain result.
- **FR-013**: Candidate lifecycle states that are defined but unreachable
  MUST be wired to real transitions or removed.
- **FR-014**: A detailed implementation plan MUST be produced and recorded in
  this feature's directory before any remediation is implemented; it MUST map
  every audit finding and every functional requirement above to a concrete
  remediation approach, an execution order, and a verification method.
- **FR-015**: The plan MUST sequence behavior-preserving safeguards (regression
  baseline capture, new orchestrator/parser tests) ahead of the structural
  refactors that depend on them, and MUST state what is out of scope or
  deferred.
- **FR-016**: The plan MUST include the project's constitution compliance
  check (architecture boundaries, test/coverage strategy, quality commands,
  packaging impact) and MUST pass it before implementation starts.

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: Feature MUST preserve explicit boundaries between CLI
  entrypoints, application services, domain logic, and infrastructure concerns,
  and MUST comply with SOLID, Clean Code, DRY, and KISS.
- **NFR-002**: Feature MUST describe required unit tests that validate the
  change, any needed integration or contract tests, and the expected
  coverage-report impact; after implementation the full unit-test suite and
  coverage report are run, with any failing test triaged (test logic vs.
  implementation logic) before the test or code is changed. For this feature
  specifically: new unit tests for the orchestrator's error/limit branches and
  for each key parser; integration tests for skipped-location reporting over
  unreadable trees; contract tests updated only for the new warning output;
  coverage MUST NOT decrease and is expected to rise in the parsing and
  orchestration areas.
- **NFR-003**: Feature MUST remain compliant with the project's linting,
  formatting, and static analysis gates.
- **NFR-004**: Standalone packaging, entry points, and release artifacts do
  NOT change. User-facing documentation changes only to describe the new
  skipped-location/truncation warnings in scan output.

### Key Entities

- **Skipped Location**: a directory or file the scan discovered but could not
  inspect; carries the path, the failure reason, and the scan phase where it
  was encountered. Appears in scan output alongside findings.
- **Detection Extension Point**: the registration seam through which key-format
  recognizers, usage categories, and properties-detection rules are added;
  defines deterministic selection/ordering among registered units.
- **Usage Category Definition**: the single authoritative record pairing a
  category's classification rule with its remediation guidance.
- **Reference Data Table**: static domain knowledge (language codes,
  vocabulary lists, signature patterns) held as data, separate from the logic
  that consumes it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A scan over a tree with N unreadable locations reports exactly N
  skipped-location warnings, each naming the path and reason; zero silent
  skips remain (verified by fault-injection tests).
- **SC-002**: Scan findings over the existing regression fixture set are 100%
  identical before and after the change (excluding the new warnings section).
- **SC-003**: A demonstration detector can be added and removed by touching
  only its own new unit and a registration entry — zero modified lines in
  existing detection units — with the full suite passing in both states.
- **SC-004**: Orchestrator error/limit branches and all key-parser paths are
  covered by dedicated unit tests; overall coverage does not decrease, and no
  production module exceeds 400 physical lines (`wc -l`) after decomposition.
- **SC-005**: Each safety/configuration default resolves to one definition;
  changing it in that one place propagates everywhere (verified by test).
- **SC-006**: Full test suite, coverage gate, lint, format, and static
  analysis all pass on the final change.
- **SC-007**: 100% of the audit findings and functional requirements in this
  spec are traceable to a step in the recorded implementation plan (with
  sequencing and verification method) before the first remediation change is
  made; the plan's constitution check passes with zero unjustified violations.

## Assumptions

- "Check the application" is interpreted as: the audit itself has been
  performed (its findings are reflected in the user stories above), and this
  feature covers *acting* on the audit — observable-error fixes plus
  maintainability, expandability, and testability refactors. The audit found
  no crash-level bugs; the error-class findings are silent error swallowing,
  lossy-decoding misclassification risk, and unreachable lifecycle states.
- Existing scan output may be extended (new warnings) but existing findings
  content is not altered, so downstream consumers are unaffected.
- No new runtime dependencies are needed; all work is internal restructuring
  plus reporting additions.
- Behavior preservation is defined by the existing regression fixtures and
  test suite; where a silent behavior becomes an explicit warning, that is the
  intended change, not a regression.
- The extension points are in-process registration seams for maintainers, not
  a runtime plugin system for end users; dynamic loading of third-party
  plugins is out of scope.
- Scan performance must not measurably regress, but no performance improvement
  targets are in scope.
- The detailed implementation plan (Story 0, FR-014–FR-016) is the plan
  artifact produced by the project's standard planning phase and recorded in
  this feature's directory; it is a review-and-approval gate, not a separate
  application feature. Approval is given by the project owner reviewing the
  plan document.
