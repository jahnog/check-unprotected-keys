# Implementation Plan: Check Unprotected Keys

**Branch**: `[001-check-unprotected-keys]` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-check-unprotected-keys/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Build a Python 3.12 standalone CLI that loads TOML-defined folder and filename
patterns, optionally narrows configured folder scope with a start folder,
classifies supported private-key material with `cryptography` and conservative
format-specific parsing, and prints only canonical file paths for files that
contain unprotected or empty-passphrase private keys.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `cryptography` for PEM/OpenSSH key parsing and
classification; Python standard library modules `argparse`, `pathlib`,
`fnmatch`, and `tomllib`; `PyInstaller` for standalone release artifact builds

**Storage**: N/A; read-only local filesystem plus a root-level
`.find-unencrypted-keys.toml` configuration file

**Testing**: `pytest`, `pytest-cov`, fixture-based unit tests, integration
tests, and contract checks for CLI and configuration behavior

**Target Platform**: Linux x86_64 local filesystems first, with portable path
handling for later cross-platform support

**Project Type**: Standalone CLI security scanner

**Packaging/Distribution**: `setuptools` console script for development and
wheel builds, plus a `PyInstaller` standalone executable smoke-tested during
release validation

**Performance Goals**: Scan 5,000 candidate files within 2 minutes on commodity
SSD-backed hardware while streaming line-oriented findings

**Constraints**: Local filesystem only, no secret material in logs or output,
canonical-path deduplication, continue after unreadable or malformed files, and
start-folder overrides may narrow folder scope only

**Quality Gates**: `ruff check . && ruff format --check . && pyright . && pytest --cov=src/find_unencrypted_keys --cov-report=term-missing --cov-fail-under=85`; release validation also runs `python -m build` and a PyInstaller smoke test

**Scale/Scope**: Thousands of files across configured folder globs; initial
support for PEM, OpenSSH private keys, PuTTY `.ppk` encryption headers, and
supported key material embedded in text containers such as `.env` files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-Design Gate**: PASS

- Architecture stays within explicit CLI, application-service, domain, and
  adapter boundaries; no additional pattern beyond a service-plus-adapter split
  is required at planning time.
- Public models and service boundaries are typed and named around scan scope,
  candidate files, and protection findings.
- Unit tests cover scope resolution, classification, and reporting; integration
  tests cover end-to-end scanning, unreadable files, and start-folder scoping;
  coverage is enforced at 85% minimum.
- Quality commands are concrete and identical for local and CI validation.
- Standalone delivery is documented as a wheel plus PyInstaller smoke-tested
  executable.

**Post-Design Review**: PASS

- [research.md](./research.md), [data-model.md](./data-model.md),
  [contracts/cli-contract.md](./contracts/cli-contract.md),
  [contracts/config-contract.md](./contracts/config-contract.md), and
  [quickstart.md](./quickstart.md) preserve the same layering, typing,
  test-gate, and packaging decisions.
- No design artifact introduces secret-leaking logs, hidden global state, or
  an exception to coverage or linting gates.

## Project Structure

### Documentation (this feature)

```text
specs/001-check-unprotected-keys/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli-contract.md
│   └── config-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
└── find_unencrypted_keys/
    ├── __init__.py
    ├── cli.py
    ├── config/
    │   ├── __init__.py
    │   ├── loader.py
    │   └── models.py
    ├── domain/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── scope.py
    │   └── classification.py
    ├── services/
    │   ├── __init__.py
    │   └── scan_service.py
    └── adapters/
        ├── __init__.py
        ├── filesystem.py
        ├── key_parsers.py
        └── reporting.py

tests/
├── contract/
│   ├── test_cli_contract.py
│   └── test_config_contract.py
├── integration/
│   └── test_scan_workflow.py
└── unit/
    ├── test_config_loader.py
    ├── test_scope_resolution.py
    ├── test_key_classification.py
    └── test_reporting.py
```

**Structure Decision**: Use a single-project Python CLI layout under
`src/find_unencrypted_keys/`, keeping CLI argument handling thin and isolating
filesystem access, configuration I/O, and key parsing behind typed adapters and
an application-level scan service.

## Complexity Tracking

No constitutional violations or approved complexity exceptions are required for
this design.
