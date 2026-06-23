# Quickstart: Validate `.properties` Secret Inspection

A runnable guide proving the feature end-to-end. Implementation details live in
`plan.md`, `data-model.md`, and `contracts/properties-inspection.md`.

## Prerequisites

- Python 3.12, project installed in editable mode with dev extras:
  `pip install -e ".[dev]"`
- Run all commands from the repository root.

## Scenario 1 — Plaintext secrets are reported per property (US1, FR-009)

1. Create a sandbox with a config and a properties file:
   - `.check-unprotected-keys.toml` with `base_folders = ["."]`,
     `filename_patterns = ["*.properties"]` (the packaged example already
     includes `*.properties`).
   - `app/application.properties` containing a plaintext
     `spring.datasource.password=hunter2xyz` and a benign `server.port=8080`.
2. Run the scanner against the sandbox.
3. **Expected**: stdout contains exactly one line
   `<abs>/app/application.properties#spring.datasource.password`; `server.port`
   produces nothing; exit code is non-zero (findings present).

## Scenario 2 — Externalized / encrypted / empty values are ignored (US2, FR-005)

1. Add properties: `db.password=${DB_PASSWORD}`, `api.secret=ENC(abc123==)`,
   `cache.password=`.
2. Run the scanner.
3. **Expected**: none of the three appear on stdout; only genuine plaintext
   secrets from other entries are reported. No secret value text appears on any
   stream.

## Scenario 3 — Non-secret values under secret-named keys (US2, FR-004)

1. Add `audit.password.min.length=8` and `auth.secret.enabled=true`.
2. Run the scanner.
3. **Expected**: neither is reported (value `8` is a pure integer; `true` is a
   boolean and below length) — the credential-likeness gate suppresses them.

## Scenario 4 — Follow a referenced key file (US1, FR-007/FR-013)

1. Place an unprotected PEM private key at `app/keys/server.key` (inside scope).
2. Add `ssl.key.file=keys/server.key` to `app/application.properties` (relative
   path → resolves against the properties file's directory).
3. Run the scanner.
4. **Expected**: stdout includes
   `<abs>/app/application.properties#ssl.key.file`; the referenced key file
   counts once toward the `Checked N file(s)` total even if it is also discovered
   directly; an out-of-scope or missing path produces no finding and no error.

## Scenario 5 — Secret values never leak (US4, SC-003)

1. Reuse Scenario 1's plaintext secret value (`hunter2xyz`).
2. Run the scanner and capture **both** stdout and stderr.
3. **Expected**: the string `hunter2xyz` appears 0 times across both streams; the
   file path and property key are present.

## Scenario 6 — Configure the secret-name catalog (US3, FR-010)

1. Set `property_name_patterns = ["corp_token"]` in the config and add
   `corp_token=A9f2Kd83Lm` plus `password=hunter2xyz`.
2. Run the scanner.
3. **Expected**: only `#corp_token` is reported (replace semantics dropped the
   default `password`). Setting `property_name_patterns = []` reports neither on
   name grounds; omitting the key restores the packaged defaults.

## Automated validation

- Unit: `pytest tests/unit/test_properties_parsing.py
  tests/unit/test_property_secrets.py tests/unit/test_properties_inspector.py`
- Integration: `pytest tests/integration/test_properties_scan_workflow.py`
- Full gate (run before review):
  - `pytest`
  - `ruff check src/ tests/`
  - `ruff format --check src/ tests/`
  - `pyright src/`
- Packaging smoke: run the CLI with `--print-example-config` and confirm the
  output includes `*.properties` and the `property_name_patterns` catalog.
