# Phase 1 Data Model: Code Quality Audit Remediation

**Feature**: `specs/010-code-quality-audit` | **Date**: 2026-07-08

New/changed entities only; unchanged domain models (`KeyFinding`,
`ProtectionAssessment`, `EffectiveScope`, …) are not repeated.

## SkippedLocation *(new, `domain/models.py`)*

A location the scan discovered but could not inspect (spec: Skipped Location).

| Field | Type | Notes |
|-------|------|-------|
| `path` | `Path` | Location that was skipped; never contains file content |
| `reason` | `str` | OS error type or diagnostic slug (e.g. `PermissionError`, `undecodable-content`, `unresolvable-reference`) |
| `phase` | `SkipPhase` | Where in the scan it happened |

`SkipPhase` (StrEnum): `SCOPE_RESOLUTION`, `DIRECTORY_PROMOTION`,
`CANDIDATE_DISCOVERY`, `FILE_INSPECTION`, `REFERENCE_FOLLOW`.

Validation: frozen dataclass; `reason` non-empty.

Relationships: aggregated on `ScanResult.skipped_locations`; produced from
`DiscoveryIssue`s (filesystem adapter) and inspection failures.

## ScanResult *(changed, `domain/models.py`)*

- New field: `skipped_locations: list[SkippedLocation]` (default empty).
- New method: `record_skip(location: SkippedLocation)` — appends and updates
  the existing `error_summaries` counter (keeps summary lines consistent).
- Existing `unreadable_count`/`error_summaries`/`exit_code` semantics
  unchanged. `directory_limit_exceeded=True` now coexists with populated
  `findings` (partial results).

## DiscoveryIssue *(unchanged shape, wider use, `adapters/filesystem.py`)*

Now also produced by `_discover_promoted_directories` (promotion pass) and
returned to the service alongside promoted directories; the service converts
each into a `SkippedLocation` instead of reducing it to a type-name count.

## KeyRecognizer *(new seam, `adapters/key_parsers.py`)*

Registry entry for one key format (FR-004).

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | e.g. `putty`, `openssh-private`, `pem-private` |
| `matches` | `Callable[[bytes], bool]` | prefix/shape test on the stripped blob |
| `inspect` | `Callable[[bytes], ProtectionAssessment]` | existing `_inspect_*` functions |

`KEY_RECOGNIZERS: tuple[KeyRecognizer, ...]` — ordered; first `matches` wins
(preserves today's if/elif precedence). State: stateless.

## UsageCategoryDefinition *(new, `domain/remediation.py`)*

Single authoritative record per `UsageCategory` (FR-005; spec: Usage Category
Definition).

| Field | Type | Notes |
|-------|------|-------|
| `category` | `UsageCategory` | key |
| `matches` | `Callable[[CandidateFile], bool]` | classification rule (ordered evaluation) |
| `remediation` | `RemediationRecommendation` | the current hard-coded prose, moved verbatim |

`USAGE_CATEGORY_DEFINITIONS: tuple[UsageCategoryDefinition, ...]` — ordered as
today's `infer_usage_category` branch order; `UNKNOWN` is the mandatory final
catch-all. Invariant (unit-tested): every `UsageCategory` member appears
exactly once.

## AssessmentRule *(new seam, `adapters/properties_inspector.py`)*

One step of the properties assessment pipeline (FR-006).

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | e.g. `inline-key-material`, `value-signature`, `message-bundle-gate` |
| `assess` | `Callable[[AssessmentContext], RuleOutcome]` | returns finding / no-finding-stop / continue |

`AssessmentContext` (frozen): entry, properties path, tier/kind (lazily
computed), scope, value-ignore list, message-bundle flag, references sink.
`RuleOutcome`: `finding: PropertyFinding | None` + `stop: bool` — encodes the
current short-circuit semantics of steps 1–7. Registry order preserves
today's step order exactly.

## CandidateState *(changed, `domain/models.py`)*

`DUPLICATE_SKIPPED` removed (unreachable — dedupe never constructs a
candidate). Remaining transitions, now the documented state machine:

```
DISCOVERED ──> REPORTED     (finding emitted)
DISCOVERED ──> CLASSIFIED   (malformed, counted not reported)
DISCOVERED ──> CLEAN        (no key material / no findings)
DISCOVERED ──> UNREADABLE   (read failure)
```

## Service ports *(new, `services/ports.py`)*

Protocols (structural, pyright-checked); production defaults wrap existing
adapter functions:

- `ScopeResolver.resolve(configuration, start_folder, tracker) -> EffectiveScope`
- `CandidateDiscoverer.discover(scope, tracker) -> tuple[list[CandidateFile], list[DiscoveryIssue]]`
- `KeyInspector.inspect(path) -> ProtectionAssessment`
- `PropertiesInspector.inspect(path, *, name_patterns, scope, value_ignore) -> PropertyInspectionResult`

`ScanService` gains these as injected fields; no constructor-signature break
for existing callers (`ScanService()` still valid).

## Removed

- `config/models.py::ScanConfigSection` — loader constructs
  `SearchConfiguration` directly (FR-011).
- Fallback `VisitedDirectoryTracker(limit=100_000)` inside
  `discover_candidate_files` — tracker becomes a required argument; the
  default lives only in `DEFAULT_MAX_DIRECTORY_VISITS` (FR-009).
