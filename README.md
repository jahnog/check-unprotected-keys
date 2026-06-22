# check-unprotected-keys

`check-unprotected-keys` is a standalone Python CLI that scans configured
folders for private keys that are unprotected or protected with an empty
passphrase. It prints only canonical absolute file paths for affected files and
keeps stderr output limited to operator-safe summaries, malformed-file review
paths, and usage-aware remediation guidance.

The scanner is intentionally bounded to currently supported key material:
PEM, OpenSSH, PuTTY, and supported key blocks embedded in matched text files.
It does not perform generic plaintext API-key, token, or password detection.

## Requirements

- Python 3.12
- `uv` for reproducible development and release validation

## Install

Published install:

```bash
python -m pip install check-unprotected-keys
```

Isolated CLI install:

```bash
pipx install check-unprotected-keys
```

Development install:

```bash
uv sync --extra dev
```

If you prefer a traditional virtual environment, `pip install -e .[dev]` is
also supported.

## Configure

Print the packaged example config and adjust the folder patterns for your
environment. The local `.check-unprotected-keys.toml` is intentionally ignored
so machine-specific scan roots do not end up in version control:

```bash
check-unprotected-keys --print-example-config > .check-unprotected-keys.toml
```

The same command works with the published wheel, `pipx` install, editable repo
checkout, and the standalone executable.

Example configuration:

```toml
# Curated expanded default catalog.
# Excluded by default: public-only files such as *.pub or known_hosts,
# certificate-only outputs such as *.crt or *.csr, unsupported keystore
# families such as *.p12 or *.jks, generic structured config formats such as
# *.json or *.yaml, and generic token-hunting globs.
[scan]
folder_patterns = [
  "~/.ssh",
  ".ssh",
  "keys",
  "private",
  "certs",
  "certificates",
  "tls",
  "ssl",
  "pki",
  "secrets",
  "config/keys",
  "config/certs",
  "config/tls",
  "config/secrets",
  ".config/keys",
  ".config/certs",
  ".config/tls",
  ".config/secrets",
  "deploy",
  "deployment",
  "infra",
  "ansible",
  "terraform",
  "docker",
  "helm",
  "k8s",
  "kubernetes",
  "vpn",
  "openvpn"
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

Default coverage categories:

- `~/.ssh` and `.ssh` for home-backed SSH material
- repo-local key and PKI roots such as `keys`, `private`, `certs`, `tls`, `pki`, and `secrets`
- curated config subtrees such as `config/keys`, `config/certs`, and `.config/secrets`
- deployment and infrastructure roots such as `deploy`, `infra`, `ansible`, `terraform`, `docker`, `helm`, `k8s`, and `vpn`
- high-signal text containers such as `.env*`, `*.ovpn`, and `*.tfvars` when they embed supported key blocks

Default non-goals and exclusions (configured via `ignore_filename_patterns` in
`.check-unprotected-keys.toml`; run `--print-example-config` for the full packaged lists):

- public-only artifacts such as `*.pub`, `authorized_keys`, and `known_hosts`
- certificate-only outputs such as `*.crt`, `*.cer`, and `*.csr`
- unsupported keystore families such as `*.p12`, `*.pfx`, and `*.jks`
- cache and package-manager artifact files such as `package-lock.json`, `*.whl`, or `*.cache`
- directory pruning via `ignore_directories` (VCS, `node_modules`, `vendor`, `.npm`, caches, etc.)

Omit an ignore key to use packaged defaults. Set `ignore_directories = []` or
`ignore_filename_patterns = []` to disable that ignore type. When a key is present with
entries, only those entries apply (replace semantics). Legacy configs with partial
`ignore_directories` extension lists receive a load-time stderr warning — copy packaged
defaults and merge your custom entries.

## Usage

Run the default configured scan:

```bash
check-unprotected-keys
```

The package also supports module invocation:

```bash
uv run python -m check_unprotected_keys --version
```

Inspect the installed program version:

```bash
check-unprotected-keys --version
```

Print the installed example configuration:

```bash
check-unprotected-keys --print-example-config
```

Stdout remains scriptable: one canonical affected-file path per line. Stderr is
reserved for the scan summary, malformed-file follow-up paths, and guidance
such as session-agent recommendations for interactive SSH keys or vault-style
recommendations for automation-oriented secrets.

Narrow the scan to a subtree without changing filename matching:

```bash
check-unprotected-keys --start-folder tests/fixtures/default-scope/team-a
```

The `--start-folder` filter keeps the same stdout-only path contract and limits
stderr guidance to findings reachable beneath the requested subtree.

Exit codes:

- `0`: no affected files were found
- `1`: one or more affected files were found
- `2`: configuration or CLI input was invalid

## Quality Gates

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run python -m pyright .
uv run python -m pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
```

## Standalone Smoke Test

```bash
uv run bash scripts/smoke_test_executable.sh
```

The smoke test builds through [check-unprotected-keys.spec](check-unprotected-keys.spec),
verifies `--help` and `--version`, and checks that the bundled executable keeps
finding paths on stdout while leaving operator messaging on stderr.

## Release Validation

See [RELEASE.md](RELEASE.md) for the supported validation flow for wheels and
the standalone executable, plus the GitHub Release to PyPI publication path.

## Fixtures

The repository includes reusable fixtures under `tests/fixtures/` for the
quickstart scenarios:

- `tests/fixtures/default-scope/team-a`
- `tests/fixtures/default-scope/team-b`
- `tests/fixtures/protected-only`

Use [specs/001-check-unprotected-keys/quickstart.md](specs/001-check-unprotected-keys/quickstart.md)
for the full end-to-end validation flow.
