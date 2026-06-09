# Research: Start Folder Parameter (Unit Test Coverage)

## Unit Test Location for resolve_start_folder

**Decision**: Extend the existing `tests/unit/test_scope_resolution.py` with a new top-level group of tests for `resolve_start_folder` (e.g. `test_resolve_start_folder_omitted_returns_none`, `test_resolve_start_folder_accepts_valid_relative`, `test_resolve_start_folder_accepts_valid_absolute`, and three invalid cases that assert the exact `ValueError` messages). Keep all scope-related pure functions in one test module for discoverability.

**Rationale**:
- The file is already named and imports from `check_unprotected_keys.domain.scope`.
- Current tests in the file already cover the downstream consumers (`narrow_root_directories`, `build_effective_scope`) that receive the result of `resolve_start_folder`.
- Co-location makes it obvious that the four required states (passed/omitted/valid/invalid) are now covered at unit level.
- Adding a brand new file would increase the number of tiny test modules without benefit; the constitution and prior features favor focused but not over-fragmented unit modules.

**Alternatives considered**:
- New file `tests/unit/test_start_folder_resolution.py`: rejected for the discoverability and import-duplication reasons above.
- Putting the tests only in contract tests: rejected because the spec (User Story 4, FR-006, SC-004, NFR-002) explicitly requires *unit* tests, and contract tests cross more seams (argparse + main + error emission).

## Testing the "not readable" Invalid Case

**Decision**: Use a real temporary directory created under `tmp_path`, create a subdirectory, `chmod(0o000)` (or `0o111` to keep traverse but remove read for the dir itself on POSIX), assert that `resolve_start_folder` raises `ValueError` containing "not readable", then restore permissions in a `finally` (or use the existing `restore_permissions` pattern from `ScanWorkspace`). The test is marked to run only on POSIX or skipped gracefully on Windows where permission semantics differ.

**Rationale**:
- The production code uses real `os.access(resolved, os.R_OK)`; a pure mock would test the wrong thing.
- The project already has precedent for real unreadable fixtures (see `unreadable_key` + `restore_permissions` in `fixture_builders.py` and usage in default-scan contract tests).
- Keeping the test reliable and cross-platform while still exercising the exact branch in `resolve_start_folder` is achievable with the chmod + restore pattern.

**Alternatives considered**:
- Monkeypatch `os.access` to return False: rejected because it would not exercise the real resolution + `exists`/`is_dir` path that precedes the access check, and would make the test less faithful to the implementation contract.
- Rely only on integration/contract tests that happen to hit permission errors: rejected because those are heavier, slower, and the spec asks for explicit unit coverage of the invalid state.

## Scope of CLI Layer Unit Tests vs Domain Unit Tests

**Decision**: Add no new unit tests directly against `cli.main` or `build_argument_parser` for the `--start-folder` cases. The four states are fully exercised by:
- Domain unit tests on `resolve_start_folder` (new).
- Pre-existing contract tests (`test_cli_start_folder_contract.py`) that invoke `main(["--start-folder", ...])` and assert exit codes + stderr messages.
- The thin nature of `cli.py` (it only does argparse + one call to the domain function + one config load) makes additional unit tests on main low-value and duplicative.

**Rationale**:
- Constitution and project practice treat the CLI as a thin adapter whose primary validation is via contract tests.
- The explicit requirement in the spec is for unit tests of "the functionality with the parameter"; the domain function is the concentrated implementation of that functionality.
- Adding unit tests for argparse wiring would be brittle to help-text or dest changes and would not increase confidence in the validation logic.

**Alternatives considered**:
- White-box unit test of `main` with heavy monkeypatching of `resolve_start_folder`: rejected as it would duplicate the domain tests and violate the "test behavior not implementation" spirit for a thin layer.

## Contracts / Interface Documentation for This Slice

**Decision**: Do not duplicate the full CLI contract (already authoritative in `specs/001-check-unprotected-keys/contracts/cli-contract.md`). Create a small focused `contracts/start-folder-validation.md` (or place a short validation contract) that captures the exact `resolve_start_folder` signature, success return, and the three error message prefixes that callers may depend on. Reference the 001 contract from quickstart and data-model.

**Rationale**:
- Avoids maintenance burden of keeping two copies of the `--start-folder` option description in sync.
- The new unit tests become the living "contract test" for the validation rules.
- A one-page focused validation contract is useful for future maintainers who only care about the parameter seam.

**Alternatives considered**:
- Only reference the 001 contract with no file in this feature's contracts/: acceptable but slightly less self-contained for someone landing in the 004 directory.
- Full copy of the start-folder section into this feature's cli-contract.md: rejected for duplication risk.

## No Production Code or Packaging Changes Required

**Decision**: The implementation work for this feature is 100% additive unit tests + the four design artifacts (research, data-model, quickstart, contracts supplement). The existing `resolve_start_folder` implementation, CLI wiring, ScanRequest, error handling, and PyInstaller flow are already correct and sufficient to satisfy the "verify" part of the user request once the unit tests exist and pass.

**Rationale**:
- Direct inspection of `cli.py`, `domain/scope.py`, contract tests, and integration tests shows the four cases (omitted=None, valid relative/absolute, three classes of invalid) are already handled and observable.
- The spec's primary new mandate is the explicit unit tests (FR-006 etc.).
- Following the "no gold-plating" and constitution guidance, we do not rewrite working code or alter packaging just because we are writing the SDD artifacts now.

**Alternatives considered**:
- Minor refactor to make `resolve_start_folder` raise a custom exception instead of ValueError: rejected because it would be a behavior change with no user-visible benefit and would require updates to the catch site and all tests; the current ValueError messages are already part of the observable contract.

## Summary of Research Findings Applied

- Extend `tests/unit/test_scope_resolution.py`.
- Use real-fs unreadable dir + restore pattern for the readable-negative test (POSIX-focused or skipped).
- Keep CLI coverage in the pre-existing contract tests.
- Add a lightweight focused contract doc under `contracts/`.
- Zero production source changes. All "verify" work is completed by the new unit tests + quickstart execution.