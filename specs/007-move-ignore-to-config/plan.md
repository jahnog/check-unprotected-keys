# Implementation Plan: Move Ignore Patterns to Configuration

**Branch**: `007-move-ignore-to-config` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-move-ignore-to-config/spec.md`

## Summary

Externalize all ignore behavior into packaged TOML configuration: remove
`DEFAULT_IGNORE_DIRECTORIES` from code, add `ignore_filename_patterns`, resolve omit / empty /
replace semantics in the loader, filter ignored filenames before candidate creation, expand the
default catalog with cache and package artifacts, and emit a non-blocking stderr warning for
legacy partial `ignore_directories` lists. No new runtime dependencies.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: stdlib (`tomllib`, `importlib.resources`, `fnmatch`, `pathlib`);
`cryptography` unchanged

**Storage**: N/A (configuration files on disk; packaged example resource in wheel)

**Testing**: `pytest` + `pytest-cov`; coverage gate ≥ 85%

**Target Platform**: Linux (POSIX); Windows supported via existing pathlib/os.walk stack

**Project Type**: CLI standalone tool (setuptools console script + PyInstaller)

**Packaging/Distribution**: Bundled resource `check-unprotected-keys.example.toml` changes;
entry points unchanged (NFR-004)

**Performance Goals**: Ignore checks are O(patterns) per file basename; no extra filesystem
walks

**Constraints**: Load warnings must not block scans; stdout remains findings-only

**Quality Gates**:

- `pytest --cov-fail-under=85`
- `ruff check src/ tests/`
- `ruff format --check src/ tests/`
- `pyright src/`

**Scale/Scope**: Configuration-surface refactor touching loader, models, scope, filesystem
discovery, example TOML, README, and tests

## Constitution Check

### Pre-design gate

- **SOLID / layers**: Loader resolves configuration; domain models carry typed fields;
  `EffectiveScope` transports ignores; filesystem adapter applies filters. CLI prints warnings
  only. ✅
- **Single source of truth (DRY)**: Defaults parsed once from packaged example TOML; no parallel
  Python tuple. ✅
- **Open/Closed**: Extend `SearchConfiguration` / `EffectiveScope` with new optional field;
  discovery gains a guard clause before candidate creation. ✅
- **KISS**: Reuse `_validate_optional_patterns` and `_match_filename_pattern`; no new pattern
  engine. ✅
- **Tests**: Unit tests for loader resolution + warning heuristic; unit/integration tests for
  filename skip and replace semantics; update integration expectations for `files_scanned` where
  pub sidecars are now skipped. ✅
- **Post-implementation verification**: Full suite + coverage before review; triage failures
  before editing tests or code. ✅
- **Packaging**: Example resource update ships inside package; smoke `--print-example-config`. ✅

No violations. Complexity Tracking table not required.

### Post-design gate

Design artifacts (`research.md`, `data-model.md`, `contracts/ignore-patterns-semantics.md`)
confirm layer placement and contracts. Re-check passed. ✅

## Project Structure

### Documentation (this feature)

```text
specs/007-move-ignore-to-config/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ignore-patterns-semantics.md
└── tasks.md              # /speckit-tasks
```

### Source Code

```text
src/check_unprotected_keys/
├── config/
│   ├── loader.py           # PRIMARY: parse packaged defaults, resolve ignores, warnings
│   └── models.py           # Add ignore_filename_patterns, load_warnings
├── domain/
│   ├── models.py           # SearchConfiguration + EffectiveScope fields
│   └── scope.py            # Pass ignore_filename_patterns into EffectiveScope
├── adapters/
│   ├── filesystem.py       # Skip ignored filenames in discover_candidate_files
│   └── reporting.py        # Optional: emit_warning() helper for stderr
├── resources/
│   └── check-unprotected-keys.example.toml  # Full default ignore catalogs + comments
└── cli.py                  # Print load_warnings to stderr before scan

tests/
├── unit/
│   ├── test_config_loader.py       # Extend: omit/empty/replace, packaged defaults, warning
│   └── test_filesystem_discovery.py  # NEW or extend: filename ignore filtering
└── integration/
    └── test_default_scan_workflow.py  # Update files_scanned where pub sidecars skipped
```

**Structure Decision**: Single-package CLI layout under `src/check_unprotected_keys/` per
constitution; changes localized to config + filesystem adapter.

## Implementation Tasks

### Task 1 — Packaged Default Catalog (Example TOML)

**Files**: `resources/check-unprotected-keys.example.toml`, `README.md`

1. Replace empty `ignore_directories = []` stub with the full commented catalog (VCS, deps,
   build, caches, package trees, IDE, temp).
2. Add `ignore_filename_patterns` block with five families (public, cert, keystore, cache,
   package artifacts) and header comments explaining omit / `[]` / replace semantics.
3. Update README example config section to reference both ignore keys.

**Acceptance**: `--print-example-config` shows complete lists; comments document replace
semantics.

---

### Task 2 — Loader: Parse Packaged Defaults & Resolve Ignores

**Files**: `config/loader.py`

1. Add `_load_packaged_defaults() -> tuple[tuple[str, ...], tuple[str, ...]]` reading
   `check-unprotected-keys.example.toml` via `importlib.resources` (module-level cache).
2. Remove `DEFAULT_IGNORE_DIRECTORIES` constant.
3. Add `_resolve_ignore_list(user_table, key, packaged_defaults) -> tuple[str, ...]` implementing
   omit / `[]` / replace rules.
4. Load `ignore_filename_patterns` with `_validate_optional_patterns`.
5. Implement `_maybe_partial_legacy_warning(...)` per `research.md`; append to `load_warnings`.
6. Track whether `ignore_directories` was explicitly present in user TOML (check key membership
   before resolution).

**Acceptance**: Unit tests cover all resolution branches and warning predicate.

---

### Task 3 — Domain & Config Models

**Files**: `config/models.py`, `domain/models.py`, `domain/scope.py`

1. Add `ignore_filename_patterns: tuple[str, ...]` and `load_warnings: tuple[str, ...]` to
   `ScanConfigSection` and `SearchConfiguration`.
2. Add `ignore_filename_patterns: frozenset[str]` to `EffectiveScope` (default empty).
3. Extend `build_effective_scope(..., ignore_filename_patterns=...)` and wire from
   `filesystem.resolve_effective_scope`.

**Acceptance**: pyright clean; existing scope tests updated.

---

### Task 4 — Filesystem Discovery: Filename Ignore Filter

**Files**: `adapters/filesystem.py`

1. In `discover_candidate_files`, before inclusion match, skip files matching
   `scope.ignore_filename_patterns` using `_match_filename_pattern`.
2. Ensure `resolve_effective_scope` passes resolved `ignore_filename_patterns` into
   `build_effective_scope`.

**Acceptance**: Unit test — `id_rsa.pub` skipped when `*.pub` ignore active; private `id_rsa`
still discovered.

---

### Task 5 — CLI Warnings

**Files**: `cli.py`, optionally `adapters/reporting.py`

1. After successful `load_search_configuration`, print each `configuration.load_warnings` line
   to stderr (prefix e.g. `warning:`).
2. Do not alter exit code.

**Acceptance**: Scenario 5 in `quickstart.md` passes.

---

### Task 6 — Tests & Regression Updates

**Files**: `tests/unit/test_config_loader.py`, new/extended filesystem tests,
`tests/integration/test_default_scan_workflow.py`, fixture helpers if needed

1. Loader: omit → packaged defaults; `[]` → empty; explicit list → replace; warning heuristic
   true/false cases.
2. Discovery: ignore-over-inclusion precedence; empty file ignores restore overlap scanning.
3. Integration: `test_clean_scope_scan_excludes_protected_and_public_only_files` — adjust
   `files_scanned` if `id_rsa.pub` no longer counted; findings remain empty.
4. Add integration case: `vendor/` or `.npm/` pruned when defaults apply (omitted key).

**Acceptance**: `pytest --cov-fail-under=85` passes.

---

### Task 7 — Documentation & Contract Sync

**Files**: `contracts/ignore-patterns-semantics.md` (done), `README.md`, example TOML headers

1. Cross-link from README “Default non-goals” to `ignore_filename_patterns` in config.
2. Note migration for legacy partial `ignore_directories` lists.

**Acceptance**: Operator can configure ignores without reading source code (SC-001).

## Test Strategy

| Area | Test type | Key cases |
|------|-----------|-----------|
| Loader resolution | Unit | omit / `[]` / replace for both keys |
| Legacy warning | Unit | partial list triggers; full copied list silent |
| Filename ignore | Unit | overlap skip; empty ignores restore scan |
| Directory prune | Integration | package/cache dirs skipped with defaults |
| Findings regression | Integration | unchanged configs → same findings (SC-002) |

**Coverage impact**: New branches in `loader.py` and `discover_candidate_files`; expect modest
increase in `config/loader.py` and `adapters/filesystem.py` coverage.

## Post-Implementation Checklist

```bash
pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
ruff check src/ tests/
ruff format --check src/ tests/
pyright src/
uv run python -m check_unprotected_keys --print-example-config | head -80
```

Triage any failing test before changing expectations or implementation; record triage conclusion
in PR/commit notes.

## Complexity Tracking

> Not required — no constitution violations.