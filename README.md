# Find Unencrypted Keys

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
- A local virtual environment for development and validation

## Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Configure

Copy the example config and adjust the folder patterns for your environment:

```bash
cp .check-unprotected-keys.toml.example .check-unprotected-keys.toml
```

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

Default non-goals and exclusions:

- public-only artifacts such as `*.pub`, `authorized_keys`, and `known_hosts`
- certificate-only outputs such as `*.crt`, `*.cer`, and `*.csr`
- unsupported keystore families such as `*.p12`, `*.pfx`, and `*.jks`
- generic structured config files such as `*.json`, `*.yaml`, or `*.toml`
- generic token or secret-hunting globs such as `*token*`, `*secret*`, or broad `*key*`

## Usage

Run the default configured scan:

```bash
check-unprotected-keys
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
ruff check .
ruff format --check .
pyright .
pytest --cov=src/find_unencrypted_keys --cov-report=term-missing --cov-fail-under=85
```

## Standalone Smoke Test

```bash
PATH="$PWD/.venv/bin:$PATH" bash scripts/smoke_test_executable.sh
```

## Fixtures

The repository includes reusable fixtures under `tests/fixtures/` for the
quickstart scenarios:

- `tests/fixtures/default-scope/team-a`
- `tests/fixtures/default-scope/team-b`
- `tests/fixtures/protected-only`

Use [specs/001-check-unprotected-keys/quickstart.md](specs/001-check-unprotected-keys/quickstart.md)
for the full end-to-end validation flow.
