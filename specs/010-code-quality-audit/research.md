# Phase 0 Research: Code Quality Audit Remediation

**Feature**: `specs/010-code-quality-audit` | **Date**: 2026-07-08

No `NEEDS CLARIFICATION` markers remained in the Technical Context (stack,
gates, and packaging are fully determined by `pyproject.toml` and the existing
codebase). Research therefore focused on choosing mechanisms for the four
remediation slices. Each decision below was validated against the actual
source (audited 2026-07-08).

## R1. Extension-point mechanism: module-level registry tuples over plugins

- **Decision**: In-process, explicit registries — an ordered tuple of
  `KeyRecognizer` objects in `adapters/key_parsers.py`, a
  `UsageCategoryDefinition` mapping in `domain/remediation.py`, and an ordered
  tuple of `AssessmentRule`s in `adapters/properties_inspector.py`. Order in
  the tuple *is* the documented precedence (first match wins), which preserves
  today's dispatch semantics exactly.
- **Rationale**: Satisfies FR-004/005/006 (add by registering, not editing)
  with zero new dependencies and no runtime magic; deterministic ordering
  answers the spec's edge case about overlapping registrations; trivially
  unit-testable (assert registry completeness and order).
- **Alternatives considered**:
  - *`importlib.metadata` entry points / plugin discovery*: rejected — spec
    explicitly scopes extension points to maintainers, not end-user plugins;
    dynamic loading adds packaging complexity (PyInstaller hidden imports) and
    violates KISS.
  - *Decorator-based auto-registration* (`@register_recognizer`): rejected —
    import-order-dependent side effects make precedence implicit; an explicit
    tuple keeps ordering reviewable in one place.
  - *Subclass registry via `__init_subclass__`*: rejected for the same
    implicit-ordering reason.

## R2. Testability seams: `typing.Protocol` + dataclass field injection

- **Decision**: Define narrow Protocols in `services/ports.py`
  (`ScopeResolver`, `CandidateDiscoverer`, `KeyInspector`,
  `PropertiesInspector`) and give `ScanService` dataclass fields with
  production defaults (thin wrappers over the existing adapter functions).
  Callers construct `ScanService()` exactly as today; tests construct
  `ScanService(discoverer=fake, ...)`.
- **Rationale**: Dependency Inversion (constitution I) with no framework;
  `Protocol` gives pyright-checked structural typing so fakes need no
  inheritance; the CLI stays a thin adapter; zero behavior change.
- **Alternatives considered**:
  - *`abc.ABC` base classes*: rejected — nominal typing forces fakes to
    inherit; Protocols are the idiomatic modern-Python seam.
  - *Function-argument injection on `run()`*: rejected — pollutes the public
    call signature used by the CLI for a test-only concern.
  - *unittest.mock patching of module globals*: rejected — hidden coupling is
    exactly the audit finding (A9); patching entrenches it.

## R3. Skipped-location reporting: extend `ScanResult`, stderr-only emission

- **Decision**: New frozen dataclass `SkippedLocation(path, reason, phase)` in
  `domain/models.py`; `ScanResult.skipped_locations: list[SkippedLocation]`;
  `filesystem._discover_promoted_directories` gains the same `issues`
  threading `discover_candidate_files` already has; `ScanService` converts
  every `DiscoveryIssue` (currently reduced to a type-name count at
  `scan_service.py:212-213`) and every unresolvable properties reference into
  `SkippedLocation`s. Reporting emits one stderr line per skip
  (`WARNING: skipped <path> (<reason>, during <phase>)`) after the existing
  summary; stdout is untouched.
- **Rationale**: The plumbing half-exists (`DiscoveryIssue` already carries
  `location`); the fix is to stop discarding it. stderr-only keeps the stdout
  findings contract byte-identical (FR-003/SC-002). Existing
  `unreadable_count`/`error_summaries` fields stay for backward-compatible
  summaries.
- **Alternatives considered**:
  - *Structured (JSON) report output*: rejected — new output mode is scope
    creep; spec only requires observability.
  - *Logging module at WARNING level*: rejected — current `_logger.debug`
    lines are invisible by default and CLI configures no handler; scan output
    is the tool's contract surface, so warnings belong in the report path.

## R4. Directory-limit abort: preserve partial results

- **Decision**: `ScanService.run` catches `DirectoryLimitExceededError` from
  discovery, sets `directory_limit_exceeded = True`, and continues to assess
  the candidates discovered *before* the limit hit (discovery returns partial
  lists instead of raising through them). Exit code stays 2; the existing
  ERROR stderr line stays; a note is added that partial results are shown.
- **Rationale**: FR-002 plus the audit's observation that an aborted scan
  today returns an empty `ScanResult()` (`scan_service.py:206-209`), hiding
  everything already found — the same "false sense of safety" class as A1.
- **Alternatives considered**:
  - *Keep abort-and-discard*: rejected — contradicts Story 1's intent.
  - *Make the limit a soft warning without exit code 2*: rejected — changes
    the documented exit-code contract for no requirement.

## R5. Lossy-decode honesty (FR-012)

- **Decision**: Replace silent `errors="replace"` / latin-1 fallback with
  explicit two-step decode: try strict UTF-8; on failure decode with
  `errors="replace"` **and flag** `lossy=True`. A lossy PuTTY/OpenSSH/PEM blob
  that fails to parse classifies as UNREADABLE-style "uncertain" (reported as
  a skip with reason `undecodable-content`) rather than MALFORMED; a blob that
  *still* parses as UNPROTECTED keeps reporting UNPROTECTED (never suppress a
  real finding). `properties_inspector._decode` keeps the latin-1 fallback
  (correct for the .properties format, whose legacy encoding *is* Latin-1)
  but this is documented as format-intended, not a silent guess.
- **Rationale**: The risk in A5 is a corrupted-by-replacement key being
  asserted MALFORMED (a confident "no finding"). Marking it uncertain keeps
  the tool honest without inventing an encoding-detection dependency.
- **Alternatives considered**:
  - *chardet/charset-normalizer detection*: rejected — new dependency for a
    marginal case; constitution requires justified deps.
  - *Treat undecodable as UNPROTECTED (fail-closed)*: rejected — floods
    reports with false positives on binary junk matching name patterns.

## R6. `domain/properties.py` decomposition: package with API-preserving façade

- **Decision**: Convert the module to a `domain/properties/` package split by
  concern (`parser`, `tiers`, `signatures`, `shapes`, `bundles`,
  `reference_data`), with `__init__.py` re-exporting the existing public names
  so all current imports (`from check_unprotected_keys.domain.properties
  import ...`) work unchanged. Data frozensets live in `reference_data.py` as
  plain Python constants.
- **Rationale**: Pure mechanical move protected by the corpus tests; the
  façade avoids touching 15+ import sites in src+tests (KISS). Python-constant
  data (vs TOML/JSON resources) keeps PyInstaller packaging untouched and the
  tables type-checked.
- **Alternatives considered**:
  - *Move tables to packaged TOML resources*: rejected — runtime file loading
    adds failure modes and PyInstaller data-file handling for zero functional
    gain; "data separated from logic" is satisfied by a data-only module.
  - *Rename modules and update all imports*: rejected — churn without benefit;
    the façade gives the same cohesion with a reviewable diff.

## R7. Config consolidation

- **Decision**: Delete `ScanConfigSection` (26-line field-mirror of
  `SearchConfiguration`); `config/loader.py` constructs `SearchConfiguration`
  directly. Merge `_validate_patterns`/`_validate_optional_patterns` into one
  helper parameterized by `required: bool`. `DEFAULT_MAX_DIRECTORY_VISITS`
  lives beside `SearchConfiguration` in `domain/models.py`; `config` and
  `filesystem` import it; the redundant fallback
  `VisitedDirectoryTracker(limit=100_000)` in
  `discover_candidate_files` is removed (the tracker parameter becomes
  required — `ScanService` always passes one).
- **Rationale**: DRY at the right level; the mirror type is pure ceremony; a
  required tracker parameter removes a third copy of the default and an
  untested code path.
- **Alternatives considered**: keeping `ScanConfigSection` as a type alias for
  one release — noted as a fallback if pyright reveals external usage, but
  nothing outside `config/` references it, so direct removal is planned.

## R8. Regression baseline strategy (WI-1)

- **Decision**: Before any refactor, tighten integration/contract assertions
  to capture full stdout (findings order + content) and the stable stderr
  summary lines for the existing fixture trees and properties corpus, so
  SC-002's "identical results" is machine-checked rather than eyeballed.
- **Rationale**: The suite is strong but some workflow tests assert subsets;
  golden assertions make every subsequent WI's "behavior preserved" claim
  executable.
- **Alternatives considered**: snapshot-testing library (syrupy) — rejected,
  plain assertions suffice and add no dependency.
