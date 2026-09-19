# Contributing

Thanks for taking the time to contribute. Bug reports and pull requests are
welcome through the
[issue tracker](https://github.com/jahnog/check-unprotected-keys/issues).

## Development setup

Requirements: Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
```

`pip install -e ".[dev]"` inside a virtual environment also works.

## Branching

The repository follows Git Flow: day-to-day work lands on `develop`, and
changes are made on `feature/<slug>` branches created from `develop`. CI runs
on every pull request.

## Local validation

Run the full validation flow from the repository root before opening a pull
request. It is the same sequence CI executes:

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run python -m pyright .
uv run python -m pytest
uv run python -m build
uv run bash scripts/smoke_test_executable.sh
```

`pytest` already applies the coverage gate (`--cov-fail-under=85`, branch
coverage on) through `addopts` in `pyproject.toml`.

## Configuration notes

- Keep `.check-unprotected-keys.toml` local and untracked; it holds
  machine-specific scan roots and is gitignored.
- Generate a fresh starting config with
  `check-unprotected-keys --print-example-config`.
- Preserve the CLI contract: findings only on stdout; summaries, warnings, and
  remediation guidance on stderr; secret values never printed.

## Pull requests

- Keep changes scoped to the user-visible behavior or validation gap being
  fixed.
- Add or update focused tests for any CLI, config, reporting, or packaging
  change. Suites live under `tests/unit`, `tests/integration`, and
  `tests/contract`.
- Do not commit generated outputs such as `build/`, `dist/`, `.coverage`,
  caches, or `*.egg-info/`.
- Update [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]` when behavior or
  distribution expectations change.

## Releases

See [RELEASE.md](RELEASE.md) for the release validation and publication flow.
