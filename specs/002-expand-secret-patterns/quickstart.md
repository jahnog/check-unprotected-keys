# Quickstart: Expand Secret Patterns

## Purpose

Validate the expanded default pattern catalog end to end after implementation
using the CLI and quality gates defined in [plan.md](./plan.md),
[data-model.md](./data-model.md), and the contracts in
[contracts/cli-contract.md](./contracts/cli-contract.md) and
[contracts/config-contract.md](./contracts/config-contract.md).

This quickstart assumes the scanner remains bounded to currently supported key
material and does not become a generic token, password, or plaintext secret
detector.

## Prerequisites

- Python 3.12 installed locally
- A virtual environment tool available
- A deterministic validation workspace created from the shared fixture builders
- A deterministic `HOME` value for `~/.ssh` validation when exercising the
  expanded home-root behavior

## Setup

```bash
export REPO_ROOT="$PWD"
export QUICKSTART_WORKDIR="$REPO_ROOT/.tmp/expanded-quickstart"

python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

PYTHONPATH="$REPO_ROOT/src" python - <<'PY'
from pathlib import Path

from tests.support.fixture_builders import (
  create_expanded_noise_workspace,
  write_expanded_scan_configuration,
)

workspace = create_expanded_noise_workspace(Path(".tmp/expanded-quickstart"))
write_expanded_scan_configuration(workspace.root)
PY

export HOME="$QUICKSTART_WORKDIR/home"
cd "$QUICKSTART_WORKDIR"
```

The generated workspace includes `.check-unprotected-keys.toml` with a
validation catalog that mirrors the shipped example:

```toml
[scan]
folder_patterns = [
  "~/.ssh",
  "tests/fixtures/expanded-patterns/repo-keys",
  "tests/fixtures/expanded-patterns/config-secrets",
  "tests/fixtures/expanded-patterns/infra",
  "tests/fixtures/expanded-patterns/vpn"
]

filename_patterns = [
  "id_*",
  "identity",
  "ssh_host_*_key",
  "*.ppk",
  "*.pem",
  "*.key",
  ".env",
  ".env.*",
  "*.env",
  "*.env.*",
  "*.ovpn",
  "*.tfvars"
]
```

## Validation Scenario 1: Expanded Default Scope

```bash
PYTHONPATH="$REPO_ROOT/src" python -m check_unprotected_keys.cli
```

Expected outcome:

- One canonical full path is printed for each file containing supported
  unprotected private-key material reached through the expanded pattern catalog.
- Files stored under the home-backed SSH root and the repo-local repo-key,
  config-secret, infrastructure, and VPN categories are evaluated without
  manual pattern additions.
- Files containing only protected keys, public-only material, unsupported
  keystores, or unrelated structured config content do not appear as findings.

## Validation Scenario 2: Start-Folder Narrowing

```bash
PYTHONPATH="$REPO_ROOT/src" python -m check_unprotected_keys.cli --start-folder fixtures/expanded-patterns/infra
```

Expected outcome:

- Only findings beneath `tests/fixtures/expanded-patterns/infra` are reported.
- The same expanded filename patterns remain active during the narrowed scan.
- No files outside the supplied start folder are scanned or reported.

## Validation Scenario 3: Noise-Boundary Check

```bash
PYTHONPATH="$REPO_ROOT/src" python -m check_unprotected_keys.cli --start-folder fixtures/expanded-patterns/noise
```

Expected outcome:

- No finding lines are printed for public-only artifacts, unsupported
  keystores, certificate-only outputs, or unrelated structured config files.
- Any malformed or unreadable supported-key fixtures are summarized without
  being treated as findings.
- The command exits with code `0` when no affected file exists in scope.

## Validation Scenario 4: Configuration Override

Edit `.check-unprotected-keys.toml` in `$QUICKSTART_WORKDIR` to remove one category such as `vpn` and
reduce the filename list to a smaller subset:

```toml
[scan]
folder_patterns = [
  "~/.ssh",
  "tests/fixtures/expanded-patterns/repo-keys",
  "tests/fixtures/expanded-patterns/config-secrets"
]

filename_patterns = [
  "id_*",
  "*.pem",
  "*.key"
]
```

Expected outcome:

- The next scan immediately reflects the narrower scope with no code change.
- Files that were reachable only through the removed `vpn` category are no
  longer scanned.
- The remaining categories continue to produce deduplicated findings.

## Quality Gates

```bash
ruff check .
ruff format --check .
pyright .
pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
```

Expected outcome:

- All commands succeed with no lint, formatting, typing, or coverage failures.

## Standalone Artifact Smoke Test

```bash
cd "$REPO_ROOT"
PATH="$REPO_ROOT/.venv/bin:$PATH" bash scripts/smoke_test_executable.sh
```

Expected outcome:

- The packaged executable starts successfully.
- The packaged executable produces the same findings as the editable-install
  command for the expanded catalog scenarios.
- The packaged executable does not emit secret material in stdout or stderr.