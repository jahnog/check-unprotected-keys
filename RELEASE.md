# Release Validation

This project supports two release artifacts:

- Python source and wheel distributions built from `pyproject.toml`
- A standalone `PyInstaller` executable built from [check-unprotected-keys.spec](check-unprotected-keys.spec) and attached to the GitHub Release

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
uv run python -m pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
uv run python -m build
uv run bash scripts/smoke_test_executable.sh
```

Expected results:

- Lint, format, type, and test gates all succeed
- `python -m build` produces the wheel and source distribution in `dist/`
- The smoke test rebuilds the standalone executable from [check-unprotected-keys.spec](check-unprotected-keys.spec)
- The bundled executable reports `--help`, reports `--version`, returns the expected exit code for the fixture scan, prints canonical findings on stdout, and keeps operator guidance on stderr

## Publication Flow

Publication is automated through [.github/workflows/publish.yml](.github/workflows/publish.yml).

Before creating a GitHub Release:

- confirm the package name `check-unprotected-keys` exists on PyPI
- configure PyPI Trusted Publishing for repository `jahnog/check-unprotected-keys` and workflow `.github/workflows/publish.yml`
- ensure the target commit has already passed the full validation sequence above
- update [CHANGELOG.md](CHANGELOG.md) for the release contents

When a GitHub Release is published, the workflow will:

- rebuild the source distribution and wheel
- rebuild the standalone executable from [check-unprotected-keys.spec](check-unprotected-keys.spec)
- publish the Python distributions to PyPI using OIDC trusted publishing
- attach the standalone executable to the GitHub Release assets

## Notes

- `build/`, `dist/`, and `*.egg-info/` are generated outputs and should not be treated as source-of-truth inputs
- The standalone artifact is validated locally in CI through [scripts/smoke_test_executable.sh](scripts/smoke_test_executable.sh)
- The standalone executable should remain a GitHub Release asset; PyPI distribution is limited to the source and wheel artifacts