# Contributing

## Development Setup

```bash
uv sync --extra dev
```

## Local Validation

Run the full repository validation flow before opening a pull request:

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run python -m pyright .
uv run python -m pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
uv run python -m build
uv run bash scripts/smoke_test_executable.sh
```

## Configuration Notes

- keep `.check-unprotected-keys.toml` local and untracked
- generate a fresh starting config with `check-unprotected-keys --print-example-config`
- preserve the CLI contract: findings on stdout, operator-safe summaries and guidance on stderr

## Pull Requests

- keep changes scoped to the user-visible behavior or validation gap being fixed
- add or update focused tests for any CLI, config, reporting, or packaging change
- avoid committing generated outputs such as `build/`, `dist/`, `.coverage`, caches, or `*.egg-info/`

## Releases

- update [CHANGELOG.md](CHANGELOG.md) when behavior or distribution expectations change
- use GitHub Releases to trigger the trusted-publishing workflow defined in `.github/workflows/publish.yml`