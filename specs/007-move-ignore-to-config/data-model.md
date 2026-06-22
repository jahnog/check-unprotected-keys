# Data Model: Move Ignore Patterns to Configuration

## SearchConfiguration (Evolved)

**Purpose**: Validated runtime configuration including resolved ignore lists and non-fatal load
warnings.

**Fields** (additions marked **new**):

| Field | Type | Notes |
|-------|------|-------|
| `config_file_path` | `Path` | Unchanged |
| `execution_root` | `Path` | Unchanged |
| `base_folders` | `tuple[str, ...]` | Unchanged |
| `directory_names` | `tuple[str, ...]` | Unchanged |
| `ignore_directories` | `tuple[str, ...]` | Resolved per omit / `[]` / replace rules |
| `ignore_filename_patterns` | `tuple[str, ...]` | **new** — resolved per same rules |
| `filename_patterns` | `tuple[str, ...]` | Unchanged |
| `max_directory_visits` | `int` | Unchanged (default 100_000) |
| `load_warnings` | `tuple[str, ...]` | **new** — non-blocking messages (e.g. partial legacy list) |

**Validation rules** (additions):

- `ignore_filename_patterns` follows `_validate_optional_patterns` (array of non-blank strings;
  may be omitted or empty).
- Resolved lists are deduplicated preserving first-seen order (`dict.fromkeys`).

**Resolution rules** (both ignore keys):

```
if key absent from user TOML:
    effective = packaged_defaults[key]
elif user array empty:
    effective = ()
else:
    effective = user array only  # replace semantics
```

## ScanConfigSection (Evolved)

Mirror `SearchConfiguration` ignore fields and `load_warnings` at the config-layer DTO before
`execution_root` is attached.

## EffectiveScope (Evolved)

**Fields** (addition):

- `ignore_filename_patterns: frozenset[str]` — carried from configuration for candidate walks.

**Invariants** (additions):

- Filename ignores are evaluated before filename inclusion during discovery.
- Directory ignores continue to prune `dirnames` in both promotion and candidate walks.

## CandidateFile (Unchanged)

No schema change. Files matching `ignore_filename_patterns` never become `CandidateFile`
instances.

## ScanResult (Unchanged)

`files_scanned` counts only files that reached assessment (not ignored filenames).

## Packaged Default Catalog (Conceptual)

Not a runtime type — parsed once per load from `check-unprotected-keys.example.toml`:

- `default_ignore_directories: tuple[str, ...]`
- `default_ignore_filename_patterns: tuple[str, ...]`

Cached at module level in `loader.py` after first parse (function-local `lru_cache` or module
constant populated lazily from resource) to avoid re-reading the resource on every test.

## ConfigurationWarning Heuristic (Loader-internal)

**Inputs**:

- `user_had_explicit_ignore_directories: bool`
- `resolved_ignore_directories: tuple[str, ...]`
- `packaged_ignore_directories: tuple[str, ...]`

**Output**: Optional warning string appended to `load_warnings`.

**Predicate** (see `research.md`):

```text
user_had_explicit_ignore_directories
AND len(resolved) < len(packaged) / 2
AND {`.git`, `node_modules`} - set(resolved) is non-empty
```

## State Transitions (Discovery)

```text
file basename seen in walk
  → matches ignore_filename_patterns? → SKIPPED (terminal)
  → matches filename_patterns?      → CandidateFile → assessment pipeline
  → otherwise                       → SKIPPED (terminal)
```

Directory traversal unchanged except effective ignore set source moves from code constant to
configuration resolution.