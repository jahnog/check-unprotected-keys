# Release Validation

This project supports two release artifacts:

- Python source and wheel distributions built from `pyproject.toml`
- A standalone `PyInstaller` executable built from [check-unprotected-keys.spec](check-unprotected-keys.spec)

## Preconditions

- Python 3.12 is available
- `uv` is installed
- The working tree is clean enough that generated build outputs can be reviewed separately from source changes

## Validation Sequence

Run the full quality and release validation flow from the repository root:

```bash
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run python -m pyright .
uv run python -m pytest --cov=src/find_unencrypted_keys --cov-report=term-missing --cov-fail-under=85
uv run python -m build
uv run bash scripts/smoke_test_executable.sh
```

Expected results:

- Lint, format, type, and test gates all succeed
- `python -m build` produces the wheel and source distribution in `dist/`
- The smoke test rebuilds the standalone executable from [check-unprotected-keys.spec](check-unprotected-keys.spec)
- The bundled executable reports `--help`, reports `--version`, returns the expected exit code for the fixture scan, prints canonical findings on stdout, and keeps operator guidance on stderr

## Notes

- `build/`, `dist/`, and `*.egg-info/` are generated outputs and should not be treated as source-of-truth inputs
- The standalone artifact is validated locally in CI through [scripts/smoke_test_executable.sh](scripts/smoke_test_executable.sh)
- This repository does not yet define automated publication to a package index; release readiness is currently established through the validation sequence above