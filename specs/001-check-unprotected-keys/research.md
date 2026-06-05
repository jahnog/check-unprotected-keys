# Research: Check Unprotected Keys

## Runtime, Tooling, and Packaging

**Decision**: Use Python 3.12 with standard-library `argparse`, `pathlib`,
`fnmatch`, and `tomllib`; add `cryptography` as the runtime parsing library;
use `pytest`, `pytest-cov`, `ruff`, and `pyright` for quality gates; package
the application with `setuptools` and smoke-test a `PyInstaller` executable.

**Rationale**:

- Python 3.12 provides stable modern typing and a standard-library TOML reader.
- Standard-library CLI, config, and filesystem tools keep the dependency
  surface small for a security-sensitive scanner.
- `cryptography` is the smallest widely supported choice for PEM and OpenSSH
  private-key parsing without adopting a larger framework.
- `ruff` plus `pyright` keeps linting, formatting, and static analysis fast and
  deterministic for local and CI runs.
- `PyInstaller` satisfies the standalone-executable requirement without forcing
  the development workflow to depend on bundled artifacts.

**Alternatives considered**:

- `click` or `typer`: rejected because the CLI surface is too small to justify
  another runtime dependency.
- YAML configuration: rejected in favor of TOML because Python 3.12 can read it
  without extra packages.
- `mypy`: rejected because `pyright` offers faster feedback with simpler setup
  for this repo.
- Wheel-only delivery: rejected because the constitution requires a documented
  standalone executable smoke test.

## Configuration and Scope Resolution

**Decision**: Store scan rules in a root-level `.find-unencrypted-keys.toml`
file with `folder_patterns` and `filename_patterns`; resolve folder patterns
relative to the execution root unless they are absolute; when `--start-folder`
is provided, narrow only the configured folder matches beneath that folder and
leave filename patterns unchanged.

**Rationale**:

- A single TOML config file keeps runtime configuration explicit and versionable.
- Resolving folder patterns relative to the execution root matches the spec's
  default-root behavior.
- Applying the start-folder override only to folder matching preserves the user
  requirement that filename patterns remain untouched.
- Canonical absolute-path resolution before deduplication avoids duplicate
  findings from overlapping patterns or symlinks.

**Alternatives considered**:

- Merging the start folder into filename rules: rejected because it changes
  filename semantics and conflicts with the specification.
- Silent skipping of duplicate or symlinked paths without canonicalization:
  rejected because it risks duplicate reporting and inconsistent behavior.

## Key Classification Strategy

**Decision**: Support PEM PKCS#1, PKCS#8, and OpenSSH private keys via
`cryptography`; inspect PuTTY `.ppk` files conservatively through their
encryption header; treat `.env` and similar text containers as supported only
when they embed recognized private-key encodings; classify results as
`UNPROTECTED`, `PROTECTED_WITH_PASSPHRASE`, `PUBLIC_ONLY`, `MALFORMED`, or
`UNREADABLE`.

**Rationale**:

- Supported private-key encodings can be parsed reliably without inventing a
  regex-only detector.
- `.ppk` headers provide a conservative way to recognize empty or missing
  protection without claiming unsupported full-format parsing.
- Restricting `.env` handling to embedded key material keeps the feature scoped
  to private/public keys rather than generic secrets.
- Explicit malformed and unreadable states prevent false negatives while keeping
  violation reporting focused on actual unprotected keys.

**Alternatives considered**:

- Regex-only key detection: rejected because it is brittle and hard to trust for
  security-sensitive file formats.
- Generic `_SECRET=` or `_TOKEN=` heuristics in `.env`: rejected because the
  feature is about key protection, not all secret disclosure.
- First-release support for PKCS#12, JKS, GPG, or cloud-specific formats:
  rejected to keep the initial parser surface testable and conservative.

## Reporting and Exit Semantics

**Decision**: Print one canonical full path per affected file to stdout, emit a
non-secret summary of unreadable or malformed files to stderr, return exit code
`1` when findings exist, `0` when the scan completes without findings, and `2`
for configuration or invocation errors.

**Rationale**:

- Path-only finding output satisfies the specification and avoids leaking secret
  material into logs.
- A separate non-finding summary preserves operator visibility without mixing
  unreadable files into the violation set.
- Distinct exit codes let automation tell the difference between findings and a
  broken invocation.

**Alternatives considered**:

- Reporting each offending key instance: rejected because the specification asks
  for file-level output and per-key output increases leakage risk.
- Treating unreadable files as findings: rejected because inability to inspect a
  file is operationally distinct from confirmed unprotected key material.