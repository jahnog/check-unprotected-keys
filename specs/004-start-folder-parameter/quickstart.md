# Quickstart: Start Folder Parameter (Verification + Unit Tests)

## Purpose

Provide runnable validation scenarios that prove the optional start-folder parameter launches searches from the supplied folder (or the full scope when omitted), fails fast and safely on invalid values, and that dedicated unit tests exist and pass for the four required states (passed, omitted, valid, invalid). References:

- Feature spec: [spec.md](./spec.md)
- Data model: [data-model.md](./data-model.md)
- Focused validation contract: [contracts/start-folder-validation.md](./contracts/start-folder-validation.md)
- Full CLI contract (for context): `specs/001-check-unprotected-keys/contracts/cli-contract.md`

## Prerequisites

- Python 3.12+
- `uv` package manager (for reproducible dev environment)
- A clean checkout of the repository

## Setup

From the repository root:

```bash
uv sync --extra dev
```

This installs the project in editable mode plus all dev tools (pytest, coverage, ruff, pyright, etc.).

## Validation Scenario 1: Run the Dedicated Unit Tests for the Four Parameter States

After the new unit tests are added to `tests/unit/test_scope_resolution.py`, execute only the start-folder resolution tests:

```bash
uv run --extra dev pytest tests/unit/test_scope_resolution.py -q -k "resolve_start_folder or start_folder"
```

Expected outcome:
- All tests in the `resolve_start_folder` family pass.
- Tests exist and are clearly named for the four cases: omitted (returns None), passed+valid (relative and absolute both accepted), and the three invalid modes (does not exist, not a directory, not readable).
- No other unrelated tests are required for this scenario.
- Running with coverage (`--cov=...`) shows the branches inside `resolve_start_folder` and its callers in `cli.py` are now exercised at unit level.

## Validation Scenario 2: CLI "Omitted" (Default Full Scope) vs "Passed Valid"

Use an existing contract or integration test that exercises both modes, or run a manual invocation against a prepared workspace. The simplest reproducible way is to invoke the contract tests that already cover start-folder:

```bash
uv run --extra dev pytest tests/contract/test_cli_start_folder_contract.py::test_cli_start_folder_reports_only_findings_under_the_requested_subtree -q --tb=line
uv run --extra dev pytest tests/contract/test_cli_default_scan_contract.py -q -k "default_scan" --tb=no
```

Or run the full start-folder contract module:

```bash
uv run --extra dev pytest tests/contract/test_cli_start_folder_contract.py -q --tb=line
```

Expected outcome:
- When `--start-folder` points at a subtree containing only some of the findings, only those findings are emitted (one path per line on stdout) and the exit code is 1.
- When the parameter is omitted (the default tests), the full configured scope is used and the expected broader set of findings appears.
- Filename patterns remain unchanged in both cases (visible via the files that are/aren't reported).
- Stderr contains only safe summaries; no secrets.

## Validation Scenario 3: Invalid Start Folder Values Produce Fast Error (Exit 2)

These can be driven from the existing contract tests or by direct CLI calls against a temp layout. Example direct invocations (after `uv sync --extra dev`):

```bash
# Create a minimal temp layout for manual verification (one-time)
mkdir -p /tmp/cuk-quickstart-test/fixtures/sub
cat > /tmp/cuk-quickstart-test/.check-unprotected-keys.toml << 'EOF'
[scan]
folder_patterns = ["fixtures"]
filename_patterns = ["id_*"]
EOF

cd /tmp/cuk-quickstart-test

# Case: non-existent
uv run --extra dev python -m check_unprotected_keys --start-folder fixtures/does-not-exist
echo "Exit code was $?"

# Case: a file instead of directory (use the config file itself)
uv run --extra dev python -m check_unprotected_keys --start-folder .check-unprotected-keys.toml
echo "Exit code was $?"

cd -
```

Expected outcome for each invalid case:
- Exit code 2.
- stdout is empty (no findings).
- stderr contains a clear message including one of:
  - "Start folder does not exist: ..."
  - "Start folder is not a directory: ..."
  - "Start folder is not readable: ..."
- No configuration loading or scanning work occurs after the error (observable by the speed and by the absence of any "Found N violation(s)" summary that would come from the scan service).

The contract test `test_cli_start_folder_returns_exit_code_two_for_invalid_paths` already asserts the non-existent case; run it to re-verify:

```bash
uv run --extra dev pytest tests/contract/test_cli_start_folder_contract.py::test_cli_start_folder_returns_exit_code_two_for_invalid_paths -q --tb=line
```

## Validation Scenario 4: Full Quality Gate Run (ensures nothing is broken)

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pyright .
uv run --extra dev pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85 -q
```

Expected outcome: all gates green. The new unit tests contribute positively to the coverage numbers for the scope and CLI modules.

## Notes

- The quickstart deliberately re-uses the heavy lifting already present in `tests/support/fixture_builders.py` (StartFolderWorkspace, etc.) and the pre-existing contract/integration tests. New manual workspace setup is only shown for the "invalid" manual demo.
- Because the feature is primarily about adding the missing unit tests, the most important runnable proof is Scenario 1 (the unit tests themselves) plus re-running the start-folder contract tests (Scenarios 2+3).
- All commands are safe to run repeatedly; they create only throw-away tmp state or use the test framework's tmp_path fixtures.

After executing the scenarios above, the implementation satisfies the acceptance criteria in the feature spec (SC-001 through SC-005) and the constitution's test/coverage requirements.