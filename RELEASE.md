# Release Validation

This project ships two release artifacts:

- Python source and wheel distributions built from `pyproject.toml` and
  published to PyPI
- A standalone PyInstaller executable built from
  [check-unprotected-keys.spec](check-unprotected-keys.spec) and attached to
  the GitHub Release

## Preconditions

- Python 3.12 and `uv` are installed
- The working tree is clean, so generated build outputs can be reviewed
  separately from source changes

## Validation sequence

Run the full quality and release validation flow from the repository root:

```bash
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run python -m pyright .
uv run python -m pytest
uv run python -m build
uv run bash scripts/smoke_test_executable.sh
```

Expected results:

- Lint, format, type, and test gates all succeed (the coverage gate is applied
  by `pytest` through `addopts` in `pyproject.toml`)
- `python -m build` produces the wheel and source distribution in `dist/`
- The smoke test rebuilds the standalone executable from
  [check-unprotected-keys.spec](check-unprotected-keys.spec)
- The bundled executable answers `--help` and `--version`, returns the
  expected exit code for the fixture scan, prints canonical findings on
  stdout, and keeps operator guidance on stderr

## Cutting a release

The repository follows Git Flow. A release is prepared on a
`release/<version>` branch from `develop`, finished onto the production branch
with a matching `<version>` tag, and merged back into `develop`.

Before finishing the release branch:

- set `__version__` in `src/check_unprotected_keys/__init__.py` to the release
  version; the package version and `--version` output are derived from it, so
  it must match the Git tag
- move the `[Unreleased]` entries in [CHANGELOG.md](CHANGELOG.md) under a new
  dated version heading
- confirm the target commit has passed the full validation sequence above

## Publication flow

Publication is automated through
[.github/workflows/publish.yml](.github/workflows/publish.yml), which runs
when a GitHub Release is published.

One-time setup:

- the package name `check-unprotected-keys` exists on PyPI
- PyPI Trusted Publishing is configured for repository
  `jahnog/check-unprotected-keys` and workflow `.github/workflows/publish.yml`

Publishing a GitHub Release from the version tag triggers the workflow, which:

- rebuilds the source distribution and wheel
- rebuilds the standalone executable from
  [check-unprotected-keys.spec](check-unprotected-keys.spec)
- publishes the Python distributions to PyPI using OIDC trusted publishing
- attaches the standalone executable to the GitHub Release assets

## Notes

- `build/`, `dist/`, and `*.egg-info/` are generated outputs and are not
  source-of-truth inputs
- The standalone artifact is validated in CI through
  [scripts/smoke_test_executable.sh](scripts/smoke_test_executable.sh)
- The standalone executable is distributed only as a GitHub Release asset;
  PyPI receives the source and wheel artifacts
