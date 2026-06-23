# Phase 1 Data Model: Scan Java `.properties` Files for Unprotected Secrets

Types are grouped by layer. **New** marks additions; **Changed** marks edits to
existing types. All dataclasses follow the existing `frozen=True, slots=True`
convention unless they need mutation (none here do).

## Configuration layer

### `ScanConfigSection` (Changed — `config/models.py`)

Add one field:

| Field | Type | Notes |
|-------|------|-------|
| `property_name_patterns` | `tuple[str, ...]` | Secret-indicating property-name patterns; resolved via omit/empty/replace. Default `()` keeps the dataclass total; loader supplies the resolved value. |

### Loader resolution (Changed — `config/loader.py`)

- `_load_packaged_defaults()` returns a 3-tuple: `(ignore_directories,
  ignore_filename_patterns, property_name_patterns)` parsed from the packaged
  example TOML; the packaged catalog MUST be non-empty.
- `property_name_patterns` resolved with the existing `_resolve_ignore_list`
  helper (omit → packaged default; `[]` → disabled; non-empty → replace).

## Domain layer

### `SearchConfiguration` (Changed — `domain/models.py`)

Add `property_name_patterns: tuple[str, ...]` (mirrors `ScanConfigSection`).
The scan service reads it from `request.configuration`; it is **not** threaded
through `EffectiveScope` (only needed at assessment time, not discovery).

### `PropertyValueKind` (New — `domain/properties.py`)

`StrEnum` describing the shape of a property value:

| Member | Meaning |
|--------|---------|
| `EMPTY` | Blank/whitespace-only value → never a finding |
| `PLACEHOLDER` | Externalized reference: `${...}`, `@...@`, `#{...}` → never a finding |
| `ENCRYPTED` | Recognized encrypted wrapper: `ENC(...)` → never a finding |
| `PATH_LIKE` | Filesystem path to a possible key file → follow (FR-007) |
| `LITERAL` | Plain literal → apply credential-likeness gate (FR-004) |

### `PropertyEntry` (New — `domain/properties.py`)

| Field | Type | Notes |
|-------|------|-------|
| `key` | `str` | Property key, whitespace-trimmed, separator-unescaped |
| `value` | `str` | Logical value (continuations joined, escapes applied) |
| `line_number` | `int` | 1-based source line of the entry start (for traceability; never the value) |

### `KeyFinding` (Changed — `domain/models.py`)

Add one optional field and one derived accessor:

| Field | Type | Notes |
|-------|------|-------|
| `property_key` | `str \| None = None` | Set for property-level findings; `None` for file-level key findings |
| `output_line` (property) | `str` | `f"{file_path}#{property_key}"` when `property_key` is set, else `file_path` |

Invariant: `KeyFinding` never carries the secret value (SC-003). Only `file_path`
and `property_key` (a key name, not a value) are stored.

## Adapter layer

### `PropertyInspectionResult` (New — `adapters/properties_inspector.py`)

Return type of `inspect_properties_file(...)`:

| Field | Type | Notes |
|-------|------|-------|
| `findings` | `tuple[PropertyFinding, ...]` | One per offending property |
| `assessed_references` | `tuple[tuple[Path, ProtectionClassification], ...]` | Canonical paths of key files followed (FR-007), for `files_scanned` accounting (FR-013) |
| `unreadable` | `bool` | True when the `.properties` file could not be read (OSError) |

### `PropertyFinding` (New — `adapters/properties_inspector.py`)

Intermediate, mapped to `KeyFinding` by the service:

| Field | Type | Notes |
|-------|------|-------|
| `property_key` | `str` | Offending property key |
| `classification` | `ProtectionClassification` | Always `UNPROTECTED` for emitted findings |
| `origin` | `PropertyFindingOrigin` | `PLAINTEXT_SECRET` / `INLINE_KEY_MATERIAL` / `REFERENCED_KEY_FILE` (drives nothing in output today; aids tests + future remediation nuance) |

## State & accounting (service layer — `services/scan_service.py`)

- **Routing**: `candidate.canonical_path.suffix == ".properties"` →
  properties inspector; else existing key parser. No new persistent state.
- **`files_scanned`**: a `.properties` file counts as 1 when inspected. Each
  entry in `assessed_references` whose canonical path is **not** already in the
  scan-level `seen: set[Path]` (seeded with every candidate canonical path)
  increments `files_scanned` once and is added to `seen` (FR-013).
- **Findings**: each `PropertyFinding` becomes a `KeyFinding` with `property_key`
  set, `classification=UNPROTECTED`, `usage_category=EMBEDDED_CONFIG_SECRET`, and
  the matching remediation. `CandidateState` transitions reuse existing values
  (`REPORTED` when any property finding is emitted, else `CLEAN`).
- **Unreadable**: `unreadable=True` routes through the existing
  `record_unreadable` path.

## Validation rules (from requirements)

- Secret-name match is case-insensitive substring over the full key (FR-003).
- A value is reported as a plaintext secret only if `LITERAL` AND credential-like
  (`len >= 6` AND entropy `>= 2.5`, not pure bool/int) (FR-004).
- `EMPTY`/`PLACEHOLDER`/`ENCRYPTED` are never findings (FR-005).
- Inline key material is assessed on every value regardless of key name (FR-006).
- Relative reference paths resolve against the `.properties` file's directory;
  out-of-scope or missing references are skipped gracefully (FR-007).
- No property value is ever stored on a finding or emitted (FR-008, SC-003).
- Followed key files count once toward `files_scanned`, deduped against direct
  discovery (FR-013).
