# Quickstart: Check Unprotected Keys

## Purpose

Validate the feature end to end after implementation using the CLI and quality
gates defined in [plan.md](./plan.md), [data-model.md](./data-model.md), and the
contracts in [contracts/cli-contract.md](./contracts/cli-contract.md) and
[contracts/config-contract.md](./contracts/config-contract.md).

## Prerequisites

- Python 3.12 installed locally
- A virtual environment tool available
- Test fixtures containing protected, unprotected, public-only, malformed, and
  unreadable key files

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Create `.find-unencrypted-keys.toml` in the project root:

```toml
[scan]
folder_patterns = [
  "tests/fixtures/default-scope",
  "tests/fixtures/shared/.ssh"
]

filename_patterns = [
  "id_*",
  "*.ppk",
  ".env",
  ".env.*",
  "*_private.pem",
  "*_private.key"
]
```

## Validation Scenario 1: Default-Root Scan

```bash
find-unencrypted-keys
```

Expected outcome:

- One canonical full path is printed for each fixture file containing an
  unprotected private key.
- Files containing only protected private keys or public keys do not appear.
- The command exits with code `1` when at least one affected file is found.

## Validation Scenario 2: Start-Folder Narrowing

```bash
find-unencrypted-keys --start-folder tests/fixtures/team-a
```

Expected outcome:

- Only findings under `tests/fixtures/team-a` are reported.
- The same configured filename patterns still govern file selection.
- No files outside the supplied start folder are scanned or reported.

## Validation Scenario 3: Clean Scope

```bash
find-unencrypted-keys --start-folder tests/fixtures/protected-only
```

Expected outcome:

- No finding lines are printed.
- Any malformed or unreadable fixtures are summarized without being treated as
  findings.
- The command exits with code `0` when no affected file exists in scope.

## Quality Gates

```bash
ruff check .
ruff format --check .
pyright .
pytest --cov=src/find_unencrypted_keys --cov-report=term-missing --cov-fail-under=85
```

Expected outcome:

- All commands succeed with no lint, formatting, typing, or coverage failures.

## Standalone Artifact Smoke Test

```bash
python -m build
pyinstaller --noconfirm --clean --onefile src/find_unencrypted_keys/cli.py --name find-unencrypted-keys
./dist/find-unencrypted-keys --start-folder tests/fixtures/team-a
```

Expected outcome:

- The packaged executable starts successfully.
- The packaged executable produces the same findings as the editable-install
  command.
- The packaged executable does not emit secret material in stdout or stderr.