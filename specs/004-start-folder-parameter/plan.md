# Implementation Plan: Start Folder Parameter

**Branch**: `[004-start-folder-parameter]` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-start-folder-parameter/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add dedicated, isolated unit tests that directly verify the optional `--start-folder` (start-folder parameter) handling for the four states explicitly required by the feature spec: parameter passed (with value), parameter omitted, value is valid (existing readable directory, relative or absolute), and value is invalid (non-existent, not a directory, or unreadable). 

The production behavior is already implemented in the thin CLI adapter (`cli.py`) which calls the pure domain function `resolve_start_folder(execution_root, raw_value: str | None)` (in `domain/scope.py`). That function returns `Path | None` or raises `ValueError` with actionable messages; the caller turns ValueError into exit code 2 + error emission. Narrowing of configured roots happens downstream via `narrow_root_directories` + `build_effective_scope` (already exercised by existing unit tests).

This plan produces the required design artifacts, research notes on test placement and permission-error testing, a data model for the parameter/validation concepts, a quickstart validation guide, and (optionally) a focused contract supplement. No runtime behavior, packaging, or public CLI surface changes are planned—only the unit test additions and supporting SDD docs to satisfy FR-006, NFR-002, SC-004, and the constitution's unit-test mandate. Existing contract/integration tests for start-folder continue to provide end-to-end coverage.

## Technical Context

**Language/Version**: Python 3.12 (project `requires-python = ">=3.12"`)

**Primary Dependencies**: `cryptography` (runtime only, for key parsing elsewhere; unchanged by this feature). No new runtime dependencies. Dev dependencies (pytest, pytest-cov, ruff, pyright, pyinstaller, build) declared under `[project.optional-dependencies] dev` in pyproject.toml.

**Storage**: N/A. The start-folder parameter involves only transient path resolution + existence/readability checks against the real filesystem (using `pathlib.Path`, `os.access`). Configuration is a single root `.check-unprotected-keys.toml`; no persistent state.

**Testing**: `pytest` + `pytest-cov` (configured in `[tool.pytest.ini_options]` and `[tool.coverage.*]`). Branch coverage enabled. Minimum 85% coverage enforced (`--cov-fail-under=85`). Existing unit tests live in `tests/unit/`, contract tests in `tests/contract/`, integration in `tests/integration/`. Fixture builders in `tests/support/` provide reusable tmp workspaces with key material and permission scenarios.

**Target Platform**: OS-independent (portable `pathlib` + `os` primitives). Primary dev/CI on Linux; the standalone PyInstaller binary and wheel must continue to work on common developer OSes.

**Project Type**: Standalone CLI security scanner (console entry point + optional PyInstaller one-file executable).

**Packaging/Distribution**: Unchanged. `check-unprotected-keys = "check_unprotected_keys.cli:main"` console script; PyInstaller used only for release artifacts (smoke-tested via `scripts/smoke_test_executable.sh`). This feature adds no entry points or packaging changes (NFR-004).

**Performance Goals**: N/A for the parameter itself (a handful of path operations performed once before any `os.walk` of candidate trees). Must not regress existing scan throughput.

**Constraints**:
- Validation of start-folder MUST occur early, before `load_search_configuration` and before any scan work (fail-fast with clear message).
- Error messages for invalid start-folder are turned into exit code 2 (user error) via the existing `except (ConfigurationError, ValueError)` path in `cli.main`.
- Relative paths resolved against `Path.cwd().resolve()` (execution_root).
- `~` expansion supported via `Path.expanduser()`.
- Must not print secrets, raw keys, or file contents in error paths.
- `os.access(..., os.R_OK)` + `is_dir()` + `exists()` checks are authoritative (real FS, not mocked in production).

**Quality Gates**: Exact commands (local and CI):
`uv run --extra dev ruff check . && uv run --extra dev ruff format --check . && uv run --extra dev pyright . && uv run --extra dev pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85`
Release path also executes `uv run --extra dev python -m build` and the smoke test script. All gates must pass with no manual exceptions.

**Scale/Scope**: Tiny. The change is limited to adding unit tests for one small pure function (`resolve_start_folder`) plus its immediate caller context, plus the four required SDD artifacts for this feature slice. No impact on number of users, LOC scanned, or concurrent use.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-Design Gate**: PASS

- Architecture keeps CLI adapters, application services, domain logic, and infrastructure concerns separated. `resolve_start_folder` and the narrowing helpers live in `domain/scope.py` (pure, no I/O except the explicit validation FS checks that belong at the domain seam). The CLI (`cli.py`) remains a thin argparse + orchestration adapter that only calls the domain function and turns its `ValueError` into the documented error path. No new layers or hidden state.
- Public interfaces and cross-module seams are already typed (`ScanRequest.start_folder: Path | None`, `resolve_start_folder(execution_root: Path, raw_value: str | None) -> Path | None`). The new unit tests will exercise the typed seam directly.
- Unit tests for the new/changed behavior (the four parameter states) are explicitly required by the spec (FR-006, User Story 4, SC-004, NFR-002). Existing contract tests (`test_cli_start_folder_contract.py`) and integration tests (`test_start_folder_scan.py`) plus the current `test_scope_resolution.py` (narrowing) will be supplemented by focused unit tests on `resolve_start_folder` itself. Coverage gate remains 85% with branch coverage; new tests are expected to increase coverage of the validation paths.
- Linting, formatting, and static analysis commands are listed exactly (see Technical Context) and match the declared toolchain in `pyproject.toml` (ruff, pyright, pytest-cov). They are deterministic via `uv run --extra dev`.
- Standalone executable packaging, artifact smoke tests, and release impacts are documented as "no change" (NFR-004). The feature only adds tests and docs; the `scripts/smoke_test_executable.sh` and PyInstaller flow are unaffected.

**Post-Design Review**: PASS

- [research.md](./research.md) records explicit decisions on unit test placement (extend existing `test_scope_resolution.py`), real-filesystem testing of the unreadable case, keeping CLI surface validation in the pre-existing contract tests, and the decision to add zero production code changes.
- [data-model.md](./data-model.md) clearly separates the early validation result (the unit-testable seam for the four states) from the later effective scope narrowing, and ties both back to `ScanRequest.start_folder` and the entities already present in `domain/models.py`.
- [contracts/start-folder-validation.md](./contracts/start-folder-validation.md) provides a focused, testable contract for `resolve_start_folder` without duplicating the broader CLI contract from spec 001.
- [quickstart.md](./quickstart.md) gives concrete, repeatable `uv run` commands that exercise the new unit tests, the four parameter states via CLI, and the full project quality gates.
- All artifacts preserve the existing SOLID boundaries (domain scope logic remains independent of CLI argparse and of the later filesystem discovery adapters). No new patterns were introduced. Coverage expectations and the exact quality commands are documented. Standalone packaging impact is explicitly "none".

## Project Structure

### Documentation (this feature)

```text
specs/004-start-folder-parameter/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── (optional focused validation contract or reference to 001 cli-contract)
└── tasks.md   # (created later by /speckit-tasks)
```

### Source Code (repository root)

```text
src/
└── check_unprotected_keys/
    ├── cli.py                          # thin adapter: calls resolve_start_folder then load + ScanService
    ├── domain/
    │   ├── models.py                   # ScanRequest (already has start_folder: Path | None), EffectiveScope
    │   └── scope.py                    # resolve_start_folder (primary unit under test), narrow_root_directories, build_effective_scope
    └── adapters/
        └── filesystem.py               # resolve_effective_scope (uses domain narrowing + config)

tests/
├── contract/
│   └── test_cli_start_folder_contract.py   # (pre-existing end-to-end CLI for --start-folder)
├── integration/
│   └── test_start_folder_scan.py           # (pre-existing integration using ScanRequest + start_folder)
├── support/
│   └── fixture_builders.py                 # StartFolderWorkspace + helpers (already supports start-folder scenarios)
└── unit/
    └── test_scope_resolution.py            # (pre-existing for narrow/build; will be extended or augmented for resolve_start_folder validation cases)
```

**Structure Decision**: Follow the existing single-project Python CLI layout defined by the constitution and prior features. All new unit tests go under `tests/unit/` co-located with the other scope-resolution tests (or as additions inside the same file). The domain function `resolve_start_folder` is the natural unit-test seam because it encapsulates the "passed/omitted/valid/invalid" logic with clear inputs (execution_root + raw CLI string) and outputs (Path|None or ValueError with exact messages). The CLI layer stays thin and continues to be validated primarily via contract tests. No new source packages, no changes under `src/check_unprotected_keys/` for production code.

## Complexity Tracking

No constitutional violations or approved complexity exceptions are required. This is a pure test-addition feature inside the already-correct layered boundaries.
