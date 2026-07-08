# check-unprotected-keys

Standalone Python CLI that finds **unprotected private keys** and **plaintext
secrets in Java `.properties` files** under folders you authorize.

It reports only canonical absolute paths on stdout (script-friendly) and keeps
operator summaries, warnings, and remediation guidance on stderr. Secret values
are never printed.

## What it is for

Use this tool when you want a **bounded, high-signal scan** of machines or
repositories for material that should not sit on disk unprotected:

| Finds | Does not find |
| --- | --- |
| Private keys with no passphrase (or an empty one) | Public-only artifacts (`*.pub`, `known_hosts`, …) |
| Supported formats: PEM, OpenSSH, PuTTY, and key blocks embedded in matched text files | Generic API-token hunting across arbitrary file types |
| Secret-named or signature-matched credentials in `*.properties` | Certificate-only outputs (`*.crt`, `*.csr`, …) |
| Unprotected key files referenced from `.properties` paths | Unsupported keystores (`*.p12`, `*.jks`, …) |

Typical uses:

- Local workstation hygiene (SSH keys under `~/.ssh`, project `secrets/`, deploy trees)
- Pre-commit / CI checks that fail the build when unprotected keys are present
- Greppable inventories: one finding path per stdout line

## Requirements

- **Python 3.12+**
- **`uv`** recommended for reproducible install, build, and test runs

## Install

Published package:

```bash
python -m pip install check-unprotected-keys
```

Isolated CLI:

```bash
pipx install check-unprotected-keys
```

Development checkout (editable + dev tools):

```bash
uv sync --extra dev
```

Traditional virtualenv alternative: `pip install -e ".[dev]"`.

## Configuration

Config is loaded from **`.check-unprotected-keys.toml`** in the current working
directory. That file is intended to stay local (machine-specific roots) and is
gitignored by design.

Generate a starting file from the packaged example:

```bash
check-unprotected-keys --print-example-config > .check-unprotected-keys.toml
```

All keys live under the `[scan]` table.

### Configuration parameters

| Key | Required | Description |
| --- | --- | --- |
| `base_folders` | Yes\* | Search bases: ancestor trees the scanner may explore. `~` is expanded; relative paths resolve against the execution root (cwd); globs are allowed. Only existing directories after expansion are kept. |
| `folder_patterns` | Legacy | Accepted when `base_folders` is absent. Treated as bases. Bare names (no `/`, no globs) are also promoted into `directory_names` for broader discovery. Prefer `base_folders` + `directory_names` for new configs. |
| `directory_names` | No | Exact basenames of directories to **promote** at any depth under active bases (e.g. `secrets`, `.ssh`, `deploy`). Empty list disables promotion. If omitted with a legacy `folder_patterns` config, bare names from that list become hints; otherwise defaults to no extra hints unless set. |
| `filename_patterns` | Yes | Basename globs (`fnmatch`) for candidate files under any effective root (base or promoted). Unchanged by `--start-folder`. |
| `ignore_directories` | No | Exact basenames never descended into (VCS, `node_modules`, caches, …). **Omit** → packaged defaults. **`[]`** → disable directory pruning. **Non-empty** → replace defaults entirely (copy packaged list and add your entries to extend). |
| `ignore_filename_patterns` | No | Basename globs skipped before assessment (ignore wins over `filename_patterns`). Same omit / `[]` / replace semantics as `ignore_directories`. |
| `property_name_patterns` | No | Token-aware secret name fragments for `*.properties` keys (`password`, `token`, …). Same omit / `[]` / replace semantics. |
| `property_value_ignore` | No | Extra exact property values (case-insensitive) always treated as benign. Omit or `[]` → none; non-empty replaces. |
| `max_directory_visits` | No | Hard cap on distinct directories visited in one scan (default `100000`). When hit, partial findings already collected are still emitted, then the process exits `2`. |

\* New-style configs must define `base_folders` (or legacy `folder_patterns`) and `filename_patterns`.

### Minimal example

```toml
[scan]
base_folders = ["."]
directory_names = [".ssh", "secrets", "keys", "private", "certs", "deploy"]
filename_patterns = [
  "id_*",
  "*.pem",
  "*.key",
  "*.ppk",
  ".env",
  ".env.*",
  "*.properties",
]
# Optional overrides — omit to keep packaged defaults:
# ignore_directories = [...]
# ignore_filename_patterns = [...]
# property_name_patterns = [...]
# max_directory_visits = 100000
```

### How discovery works

1. Expand `base_folders` into concrete directories.
2. Optionally promote subtrees whose basename is in `directory_names`.
3. Walk effective roots, pruning `ignore_directories` and skipping
   `ignore_filename_patterns`.
4. Classify private-key candidates; inspect `*.properties` with a tiered
   secret classifier (name tokens, value signatures, inline keys, path refs).

Default packaged catalogs cover home SSH material, repo key/PKI roots, deploy
and infra trees, high-signal text containers (`.env*`, `*.ovpn`, `*.tfvars`),
and Java properties. Full lists: `--print-example-config`.

### Java `.properties` inspection

Reported when confidence is high enough:

- Plaintext credentials under secret-named keys (token-aware split on `. _ - /`
  and camelCase; STRONG names like `*.password` vs WEAK like bare `key`/`token`)
- Values matching known **signatures** (cloud tokens, JWTs, private keys,
  `scheme://user:password@host`) regardless of key name
- Inline private-key material in a value
- Paths that resolve to an **unprotected** key file (relative to the properties
  file’s directory)

Never reported: externalized refs (`${...}`, `vault:…`), encrypted wrappers
(`ENC(...)`, `{cipher}…`), placeholders, booleans/numbers, and recognizable
non-secret shapes. Message bundles (locale-suffixed or known base names) skip
name-based credential matching; signatures and key material still apply.

Each property finding is one stdout line: `<path>#<property key>`.

## CLI parameters

| Option | Description |
| --- | --- |
| `-h`, `--help` | Show help and exit. |
| `--version` | Print `check-unprotected-keys <version>` and exit. |
| `--print-example-config` | Write the packaged example TOML to stdout and exit `0`. |
| `--start-folder PATH` | Narrow the scan to a subtree. Filename patterns stay the same; only configured bases/promotions that interact with this path participate. Path must exist and be a directory. |

There is no global config-path flag: place `.check-unprotected-keys.toml` in the
directory from which you invoke the tool (execution root).

## Example usages

### Default scan from the current directory

```bash
check-unprotected-keys
```

Uses `.check-unprotected-keys.toml` in the cwd (or fails with exit `2` if
required config is missing/invalid).

### Module invocation (useful in a repo checkout)

```bash
uv run python -m check_unprotected_keys
uv run python -m check_unprotected_keys --version
```

### Print and capture example config

```bash
check-unprotected-keys --print-example-config
check-unprotected-keys --print-example-config > .check-unprotected-keys.toml
```

### Narrow to a fixture or project subtree

```bash
check-unprotected-keys --start-folder tests/fixtures/default-scope/team-a
```

```bash
check-unprotected-keys --start-folder /srv/app/deploy
```

### Scriptable pipeline

```bash
# Collect finding paths only (stdout); keep operator noise on stderr
mapfile -t findings < <(check-unprotected-keys 2>/dev/null) || true
```

Stdout: one canonical absolute path (or `path#property`) per line.  
Stderr: scan summary, skipped-location warnings, malformed-file paths, remediation tips.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No affected files |
| `1` | One or more findings |
| `2` | Invalid config/CLI input, or directory-visit limit aborted the scan (partial results may still have been printed) |

### Skipped locations and partial results

Unreadable or unresolvable locations are never silent. Stderr examples:

```text
WARNING: skipped /srv/app/secrets (PermissionError, during candidate-discovery)
WARNING: skipped /srv/app/locked.pem (unreadable, during file-inspection)
WARNING: skipped /srv/app/keys/missing.pem (unresolvable-reference, during reference-follow)
```

Warnings are sorted by path, once per location, and never include file content.
If `max_directory_visits` aborts traversal, findings collected so far remain on
stdout and stderr ends with:

```text
NOTE: Partial results above cover the directories visited before the limit.
```

## Compile, debug, and test

Commands below assume a clone of this repository and `uv sync --extra dev`
already run from the repo root.

### Compile / build

Editable install (run CLI and tests against local `src/`):

```bash
uv sync --extra dev
```

Python source distribution and wheel:

```bash
uv run python -m build
```

Artifacts land in `dist/` (e.g. `check_unprotected_keys-*.whl`, `*.tar.gz`).

Standalone executable (PyInstaller):

```bash
uv run python -m PyInstaller --noconfirm --clean check-unprotected-keys.spec
```

Binary: `dist/check-unprotected-keys`. Or run the full packaging smoke test:

```bash
uv run bash scripts/smoke_test_executable.sh
```

### Debug

Run the CLI under the debugger against a local config and optional start folder:

```bash
uv run python -m pdb -m check_unprotected_keys --start-folder tests/fixtures/default-scope/team-a
```

Drop into the debugger on the first failing test:

```bash
uv run python -m pytest --pdb -x
```

Verbose single-test debugging:

```bash
uv run python -m pytest tests/unit/test_key_classification.py -vv --tb=long -k "unprotected"
```

Print package version and help while validating the environment:

```bash
uv run python -m check_unprotected_keys --version
uv run python -m check_unprotected_keys --help
```

### Run all tests

Full suite with coverage gate (≥ 85%, branch coverage on):

```bash
uv run python -m pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
```

`pyproject.toml` already sets the same coverage options as `addopts`, so a
shorter form is equivalent in this repo:

```bash
uv run python -m pytest
```

Focused slices:

```bash
uv run python -m pytest tests/unit -q
uv run python -m pytest tests/integration -q
uv run python -m pytest tests/contract -q
```

### Quality gates (lint, types, tests)

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run python -m pyright .
uv run python -m pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
```

## Release validation

See [RELEASE.md](RELEASE.md) for wheel + standalone validation and the GitHub
Release → PyPI trusted-publishing path. Full local sequence:

```bash
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run python -m pyright .
uv run python -m pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
uv run python -m build
uv run bash scripts/smoke_test_executable.sh
```

## Fixtures

Reusable trees under `tests/fixtures/`:

- `tests/fixtures/default-scope/team-a` / `team-b` — unprotected key samples
- `tests/fixtures/protected-only` — passphrase-protected material
- `tests/fixtures/properties_corpus` — properties detection corpus

End-to-end scenarios: [specs/001-check-unprotected-keys/quickstart.md](specs/001-check-unprotected-keys/quickstart.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Keep PRs scoped; do not commit generated
`build/`, `dist/`, caches, or machine-local `.check-unprotected-keys.toml`.
