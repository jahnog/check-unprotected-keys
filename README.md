# Find Unencrypted Keys

`check-unprotected-keys` is a standalone Python CLI that scans configured
folders for private keys that are unprotected or protected with an empty
passphrase. It prints only canonical absolute file paths for affected files and
keeps stderr output limited to operator-safe summaries.

## Requirements

- Python 3.12
- A local virtual environment for development and validation

## Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Configure

Copy the example config and adjust the folder patterns for your environment:

```bash
cp .check-unprotected-keys.toml.example .check-unprotected-keys.toml
```

Example configuration:

```toml
[scan]
folder_patterns = [
  "tests/fixtures/default-scope",
  "tests/fixtures/protected-only"
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

## Usage

Run the default configured scan:

```bash
check-unprotected-keys
```

Narrow the scan to a subtree without changing filename matching:

```bash
check-unprotected-keys --start-folder tests/fixtures/default-scope/team-a
```

Exit codes:

- `0`: no affected files were found
- `1`: one or more affected files were found
- `2`: configuration or CLI input was invalid

## Quality Gates

```bash
ruff check .
ruff format --check .
pyright .
pytest --cov=src/find_unencrypted_keys --cov-report=term-missing --cov-fail-under=85
```

## Standalone Smoke Test

```bash
PATH="$PWD/.venv/bin:$PATH" bash scripts/smoke_test_executable.sh
```

## Fixtures

The repository includes reusable fixtures under `tests/fixtures/` for the
quickstart scenarios:

- `tests/fixtures/default-scope/team-a`
- `tests/fixtures/default-scope/team-b`
- `tests/fixtures/protected-only`

Use [specs/001-check-unprotected-keys/quickstart.md](specs/001-check-unprotected-keys/quickstart.md)
for the full end-to-end validation flow.
