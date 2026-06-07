# Quickstart: Remediation Guidance Logging

## Purpose

Validate malformed-file path logging and usage-aware remediation guidance end to
end using the CLI contract in [contracts/cli-contract.md](./contracts/cli-contract.md)
and the reporting entities defined in [data-model.md](./data-model.md).

## Prerequisites

- Python 3.12 installed locally
- `uv` available for running the repo's configured tooling
- A clean checkout of the repository root

## Setup

From the repository root:

```bash
uv sync --extra dev
```

## Validation Scenario 1: Unit-Level Recommendation Mapping

```bash
uv run --extra dev pytest tests/unit/test_remediation_guidance.py --no-cov
```

Expected outcome:

- Interactive user-key fixtures map to session-oriented passphrase plus agent
  guidance.
- SSH host key fixtures map to host-specific hardening or reprovisioning
  guidance instead of interactive passphrase guidance.
- Automation and embedded-config fixtures map to non-interactive vault or
  secret-store guidance.
- Ambiguous fixtures fall back to a conservative `unknown` recommendation.

## Validation Scenario 2: Unit-Level Malformed Path Capture

```bash
uv run --extra dev pytest tests/unit/test_malformed_path_logging.py --no-cov
```

Expected outcome:

- Each malformed file is retained once with a canonical absolute path.
- Malformed counts remain correct when derived from the stored issues.
- Malformed file capture does not create findings or alter exit-code logic.

## Validation Scenario 3: CLI Contract Preservation

```bash
uv run --extra dev pytest tests/contract/test_cli_default_scan_contract.py --no-cov
```

Expected outcome:

- Stdout still contains only canonical finding paths.
- Stderr includes the scan summary plus malformed-file path lines and
  remediation guidance when present.
- Exit codes remain `0` with no findings and `1` when unprotected findings are
  present, even if malformed files also exist.

## Validation Scenario 4: Start-Folder Compatibility

```bash
uv run --extra dev pytest tests/contract/test_cli_start_folder_contract.py tests/integration/test_start_folder_scan.py --no-cov
```

Expected outcome:

- `--start-folder` keeps stdout as a path-only stream for the narrowed subtree.
- Stderr emits remediation guidance only for findings inside the requested
  subtree.
- Guidance ordering remains stable when scans are narrowed.

## Validation Scenario 5: End-to-End Workflow

```bash
uv run --extra dev pytest tests/integration/test_default_scan_workflow.py --no-cov
```

Expected outcome:

- A scan with mixed findings emits one stdout line per unprotected file.
- Operator-facing stderr output includes the malformed files that could not be
  fully evaluated.
- Each unprotected finding receives one remediation recommendation tied to a
  usage category.
- A malformed-only scan keeps stdout empty while still logging follow-up detail
  on stderr.

## Full Quality Gates

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pyright .
uv run --extra dev pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
```

Expected outcome:

- Linting, formatting, typing, and the full covered test suite all pass.

## Standalone Artifact Smoke Test

```bash
uv run --extra dev python -m build
uv run --extra dev bash scripts/smoke_test_executable.sh
```

Expected outcome:

- The packaged executable starts successfully.
- The packaged executable preserves stdout-only finding paths while showing the
  additional operator-facing stderr guidance.
- No secret material appears in either output stream.