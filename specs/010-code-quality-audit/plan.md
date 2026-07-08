# Implementation Plan: Code Quality Audit — Errors, Maintainability, Expandability, Testability

**Branch**: `feature/code-quality-audit` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-code-quality-audit/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Remediate the findings of the 2026-07-08 code-quality audit in four
independently deliverable slices: (1) make every silently skipped location
observable in scan output and preserve partial results when the traversal
limit aborts a scan; (2) convert the three hard-coded detection dispatch
chains (key-format if/elif, usage-category/remediation parallel `match`
blocks, fixed 7-step properties pipeline) into registration-based extension
points; (3) give `ScanService` injectable collaborator seams and add dedicated
unit tests for `key_parsers` and orchestrator branches; (4) decompose the
1,006-line `domain/properties.py` god-module, unify the `100_000`
directory-limit default declared in three places, and remove the
`ScanConfigSection`/`SearchConfiguration` mirror plus duplicated loader
validation. Technical approach: table/registry-driven dispatch (Registry
pattern), constructor injection against `Protocol` seams, and a regression
baseline captured before any structural change.

## Technical Context

**Language/Version**: Python 3.12 (`requires-python = ">=3.12"`)

**Primary Dependencies**: `cryptography>=46.0.7,<47.0` (only runtime dep); stdlib `os.walk`, `fnmatch`, `glob`, `tomllib`

**Storage**: N/A (reads filesystem being scanned; TOML config file)

**Testing**: pytest 9 + pytest-cov, `--cov-fail-under=85`, branch coverage on; suites in `tests/{unit,integration,contract}` with fixture builders in `tests/support` and a properties corpus in `tests/fixtures`

**Target Platform**: OS-independent CLI (Linux primary); Python 3.12 runtime or PyInstaller binary

**Project Type**: Single-package CLI tool (`src/check_unprotected_keys`, hexagonal: cli → services → domain, adapters at I/O seams)

**Packaging/Distribution**: console script `check-unprotected-keys` + PyInstaller standalone binary — **unchanged by this feature**

**Performance Goals**: No regression: scan wall-time on the integration fixture trees stays within noise of current baseline; no additional filesystem stat/read calls on the hot path

**Constraints**: Findings/stdout contract must stay byte-identical for existing fixtures; stderr may gain new warning/notice lines only; exit codes 0/1/2 unchanged; no secret material may ever appear in new diagnostics

**Quality Gates**: `pytest` (coverage ≥85% enforced via addopts), `ruff check .`, `ruff format --check .`, `pyright` — run locally and in CI exactly as listed

**Scale/Scope**: ~3,100 src LOC / ~4,700 test LOC today; feature touches 9 source modules, adds ~6 new modules, adds ~4 test modules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Architecture / SOLID**: All changes preserve the existing cli → services →
  domain / adapters layering. Named pattern choices, each justified:
  - *Registry (table-driven dispatch)* for key-format recognizers,
    usage-category definitions, and properties assessment rules — replaces
    if/elif and parallel `match` chains so new detectors register instead of
    editing stable units (Open/Closed, spec FR-004/005/006).
  - *Dependency Injection via `Protocol` seams* on `ScanService` — collaborators
    (scope resolver, candidate discoverer, key inspector, properties inspector)
    become constructor fields with production defaults, enabling fake-driven
    unit tests (Dependency Inversion, spec FR-007). No DI framework; plain
    dataclass fields with `default_factory`.
  - *Separated reference data* — frozenset tables move to a data-only module,
    keeping logic modules small (Single Responsibility, spec FR-010).
  No speculative plugin loading, no dynamic discovery — registration stays
  in-process and explicit (KISS).
- **Clean Code / DRY / KISS**: Public seams (`KeyRecognizer`,
  `UsageCategoryDefinition`, `AssessmentRule`, `SkippedLocation`, service
  protocols) are fully type-annotated dataclasses/Protocols. The three-way
  duplicated `100_000` default collapses to one constant; the
  `ScanConfigSection` mirror type and the near-duplicate loader validators are
  removed/merged.
- **Tests & coverage**: New unit tests are enumerated per work item in the
  Remediation Map below (key-parser paths, orchestrator branches via fakes,
  skipped-location reporting, single-source default). Integration tests cover
  unreadable-tree scans; contract tests extend only for the new stderr
  warnings. Coverage gate stays ≥85% and is expected to rise (key_parsers and
  scan_service branches gain direct coverage).
- **Post-implementation verification**: After implementation, the full unit
  suite and coverage report will be run (`pytest`); any failing test will be
  triaged — test logic vs. implementation logic — and the conclusion recorded
  in the task notes before the test or code is changed.
- **Lint/format/static analysis**: `ruff check .`, `ruff format --check .`,
  `pyright` — identical locally and in CI.
- **Packaging**: No change to entry points, PyInstaller spec, or release
  artifacts; the release smoke test is re-run unchanged. README gains a short
  section documenting the new skipped-location/truncation stderr warnings.
- **Git Flow**: Implementation proceeds on `feature/code-quality-audit`
  (4-word kebab slug) created via `git flow feature start code-quality-audit`
  just before coding begins; all commits and the PR are made manually by the
  user; no other git action is automated.

**Gate result (pre-Phase 0): PASS** — no violations to justify.

## Audit Findings → Remediation Map *(FR-014 traceability)*

Verified against source on 2026-07-08. Each finding maps to a work item (WI),
its fix approach, and its verification method. WIs are sequenced in the next
section.

| # | Finding (file:line) | Spec req | Work item / fix | Verification |
|---|--------------------|----------|-----------------|--------------|
| A1 | `ScanService.run` keeps only `issue.error_type` from `DiscoveryIssue`s — paths dropped (`services/scan_service.py:212-213`); report shows counts only (`adapters/reporting.py:55-69`) | FR-001 | **WI-3**: add `SkippedLocation(path, reason, phase)` to `ScanResult`; reporting emits one stderr line per skip | Unit tests on reporting; integration test over tree with chmod-000 dir/file |
| A2 | Hint-promotion pass swallows `OSError` with bare `continue` (`adapters/filesystem.py:310-311, 326-327`) and calls `_prune_with_visit_check` without an issues list (`filesystem.py:318`) | FR-001 | **WI-3**: thread `issues` through `_discover_promoted_directories`; return alongside promoted dirs | Unit test: unreadable base/hint dir yields a `DiscoveryIssue` |
| A3 | `DirectoryLimitExceededError` abort discards all partial results (`scan_service.py:206-209`); limit hit is reported but nothing else survives | FR-002 | **WI-3**: catch limit error, mark `directory_limit_exceeded`, keep candidates/findings gathered so far; reporting keeps ERROR line, adds partial-results note | Unit test with fake discoverer raising mid-stream; contract test for exit code 2 + stderr |
| A4 | `properties_inspector._follow_reference` returns `None` on `OSError` silently (`properties_inspector.py:207-209`) | FR-001 | **WI-3**: record unresolvable references as skipped locations (phase = reference-follow) | Unit test: dangling reference produces a skip entry, not silence |
| A5 | Lossy decodes can misclassify: `errors="replace"` in `inspect_text_for_key_material` (`key_parsers.py:74`) and PuTTY parse (`key_parsers.py:214`); `_decode` utf-8→latin-1 fallback silent (`properties_inspector.py:233-237`) | FR-012 | **WI-5**: detect replacement-character introduction / decode fallback; treat affected content as uncertain (never downgrade UNPROTECTED→MALFORMED); surface as skip/uncertain diagnostic | Unit tests with invalid-UTF-8 key bytes asserting classification is not MALFORMED-by-corruption |
| A6 | Key-format dispatch is a byte-prefix if/elif chain (`key_parsers.py:93-120`) | FR-004 | **WI-6**: `KeyRecognizer` protocol + ordered registry tuple; each format one recognizer; dispatch iterates registry | SC-003 demo: add+remove dummy recognizer, 0 lines changed in existing units; regression suite |
| A7 | `infer_usage_category` + `build_remediation_recommendation` are parallel per-category chains (`scan_service.py:55-82, 85-178`) | FR-005 | **WI-7**: `UsageCategoryDefinition` table pairing match rule + remediation text, single registry; both functions become table lookups | Unit test: every `UsageCategory` member has exactly one definition; regression on remediation text |
| A8 | `_assess_entry` is a fixed 7-step pipeline (`properties_inspector.py:109-163`) | FR-006 | **WI-8**: ordered `AssessmentRule` registry (name, applies, assess) preserving current order/short-circuit semantics | Registry-order unit test; full properties corpus regression |
| A9 | `ScanService` hard-wires `filesystem`/`key_parsers`/`properties_inspector` module calls (`scan_service.py:8-16, 197-229`) | FR-007 | **WI-4**: `Protocol` seams + injected collaborators with production defaults; orchestrator branches tested with fakes | New unit suite driving limit/malformed/unreadable branches with in-memory fakes |
| A10 | No dedicated `key_parsers` tests (parse paths covered only incidentally) | FR-008 | **WI-2**: `tests/unit/test_key_parsers.py` covering valid/encrypted/malformed/truncated per format (PEM, OpenSSH, PuTTY, public, certificate) | Coverage report shows direct coverage of `key_parsers` branches |
| A11 | `100_000` default in four places (`config/loader.py`, `domain/models.py:60`, `config/models.py:25`, fallback `filesystem.py:169`) | FR-009 | **WI-9**: single `DEFAULT_MAX_DIRECTORY_VISITS` constant in `domain/models.py`; all others reference it; remove the `filesystem.py` fallback tracker construction | Unit test asserting all sites resolve to the constant (SC-005) |
| A12 | `domain/properties.py` is 1,006 lines mixing tokenization, tiers, signatures, shapes, i18n bundles, parsing, plus ~350 lines of frozenset data | FR-010 | **WI-10**: split into `domain/properties/` package (`parser.py`, `tiers.py`, `signatures.py`, `shapes.py`, `bundles.py`, `reference_data.py`), re-export current public API from `__init__.py` so no caller changes | Import-compatibility test; module-size check (≤400 lines each); corpus regression |
| A13 | `_validate_patterns` / `_validate_optional_patterns` near-duplicates (`config/loader.py:239-291`); `ScanConfigSection` mirrors `SearchConfiguration` field-by-field with a copy loop (`loader.py:169-194`) | FR-011 | **WI-11**: merge validators into one parameterized helper; eliminate `ScanConfigSection` (loader builds `SearchConfiguration` directly) | Existing config-loader/contract tests pass unchanged |
| A14 | `CandidateState.DUPLICATE_SKIPPED` unreachable (dedupe at `filesystem.py:236-238` never creates a candidate); `DISCOVERED` is only ever the initial default | FR-013 | **WI-12**: remove `DUPLICATE_SKIPPED`; keep `DISCOVERED` as documented initial state | Grep/pyright confirm no references; suite passes |

## Sequencing *(FR-015)*

Safeguards land before the refactors they protect:

1. **WI-1 — Regression baseline** *(safeguard)*: capture current stdout/stderr
   of integration + contract fixtures as golden output (extend existing tests
   where assertions are loose). Gate for every later WI (SC-002).
2. **WI-2 — Key-parser unit tests** *(safeguard, A10/FR-008)*: written against
   the *current* code so WI-6's registry refactor is provably
   behavior-preserving.
3. **WI-3 — Observable skips & partial results** (A1, A2, A3, A4 / FR-001,
   FR-002): the only intended behavior change; lands early so the new warning
   contract is baselined before structural work.
4. **WI-4 — Injectable `ScanService` seams + orchestrator unit tests** (A9 /
   FR-007): enables fake-driven tests used by later WIs.
5. **WI-5 — Lossy-decode honesty** (A5 / FR-012).
6. **WI-6 — Key-recognizer registry** (A6 / FR-004) — protected by WI-2.
7. **WI-7 — Usage-category definition table** (A7 / FR-005).
8. **WI-8 — Properties assessment-rule registry** (A8 / FR-006) — protected by
   the corpus tests and WI-1 baseline.
9. **WI-9 — Single-source directory-limit default** (A11 / FR-009).
10. **WI-10 — Split `domain/properties.py`** (A12 / FR-010) — pure move,
    protected by everything above.
11. **WI-11 — Config loader consolidation** (A13 / FR-011).
12. **WI-12 — Candidate-state cleanup** (A14 / FR-013).
13. **WI-13 — Docs & final gates**: README warning-output section; full
    `pytest` + coverage, `ruff check`, `ruff format --check`, `pyright`;
    SC-001..SC-007 checklist pass.

**Out of scope / deferred**: runtime plugin loading, performance tuning,
remediation-text localization, any stdout findings-format change, packaging
changes.

## Project Structure

### Documentation (this feature)

```text
specs/010-code-quality-audit/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/check_unprotected_keys/
├── cli.py                          # unchanged (thin adapter)
├── config/
│   ├── loader.py                   # WI-11: merged validators, builds SearchConfiguration directly
│   └── models.py                   # WI-11: ScanConfigSection removed (or reduced to alias during transition)
├── domain/
│   ├── models.py                   # WI-3: SkippedLocation + ScanResult.skipped_locations;
│   │                               # WI-9: DEFAULT_MAX_DIRECTORY_VISITS; WI-12: state cleanup
│   ├── classification.py           # unchanged
│   ├── scope.py                    # unchanged
│   ├── remediation.py              # NEW (WI-7): UsageCategoryDefinition registry
│   └── properties/                 # NEW package (WI-10) replacing properties.py
│       ├── __init__.py             # re-exports current public API (import-compatible)
│       ├── parser.py               # parse_properties + entry model
│       ├── tiers.py                # key-name tier classification
│       ├── signatures.py           # provider value-signature patterns
│       ├── shapes.py               # value kinds, non-secret shapes, placeholders
│       ├── bundles.py              # i18n/message-bundle detection
│       └── reference_data.py       # frozenset tables (languages, vocab, denylists)
├── adapters/
│   ├── filesystem.py               # WI-3: issues threaded through promotion pass
│   ├── key_parsers.py              # WI-6: KeyRecognizer protocol + registry; WI-5 decode honesty
│   ├── properties_inspector.py     # WI-8: AssessmentRule registry; WI-3/WI-5 diagnostics
│   └── reporting.py                # WI-3: skipped-location + partial-results stderr lines
└── services/
    ├── ports.py                    # NEW (WI-4): Protocol seams for collaborators
    └── scan_service.py             # WI-4: injected collaborators; WI-7: table lookups

tests/
├── contract/                       # extended: new stderr warning lines (WI-3)
├── integration/
│   └── test_unreadable_tree_scan.py  # NEW (WI-3)
└── unit/
    ├── test_key_parsers.py           # NEW (WI-2)
    ├── test_scan_service_orchestration.py  # NEW (WI-4)
    ├── test_skipped_location_reporting.py  # NEW (WI-3)
    └── test_detection_registries.py        # NEW (WI-6/7/8, incl. SC-003 demo)
```

**Structure Decision**: Keep the existing single-package hexagonal layout.
New seams live where their layer dictates: registries whose content is domain
knowledge (`remediation.py`, `properties/`) go under `domain/`; the
key-recognizer registry stays in `adapters/key_parsers.py` because recognizers
wrap the `cryptography` library (infrastructure); service Protocols go in
`services/ports.py` so `ScanService` depends on abstractions, not adapter
modules. `domain/properties.py` becomes the `domain/properties/` package with
an API-preserving `__init__.py`, so all existing imports keep working.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations — table intentionally empty.

**Gate result (post-Phase 1 re-check): PASS** — design artifacts introduce no
new layers, no new dependencies, and no unjustified patterns; registries and
Protocol seams are the minimal mechanisms that satisfy FR-004..FR-007.
