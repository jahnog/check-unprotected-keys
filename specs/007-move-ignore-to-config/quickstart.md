# Quickstart Validation Guide: Move Ignore Patterns to Configuration

**Branch**: `007-move-ignore-to-config` | **Date**: 2026-06-22

Validates end-to-end behavior from [spec.md](spec.md) and
[contracts/ignore-patterns-semantics.md](contracts/ignore-patterns-semantics.md).

---

## Prerequisites

```bash
pip install -e ".[dev]"

pytest && ruff check src/ tests/ && ruff format --check src/ tests/ && pyright src/
```

---

## Scenario 1 — Packaged Example Lists All Defaults (US1)

```bash
uv run python -m check_unprotected_keys --print-example-config | \
  grep -E 'ignore_directories|ignore_filename_patterns' -A2
```

**Expect**: Both keys present with commented categories; no reliance on hidden code constants.

---

## Scenario 2 — Replace Semantics (US2)

```bash
TMP=$(mktemp -d)
mkdir -p "$TMP/noise" "$TMP/real"
# Decoy under custom ignore dir name only
printf '-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n' > "$TMP/noise/id_rsa"
printf '-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n' > "$TMP/real/id_rsa"

cd "$TMP"
cat > .check-unprotected-keys.toml <<'EOF'
[scan]
base_folders = ["."]
directory_names = []
ignore_directories = ["noise"]
ignore_filename_patterns = []
filename_patterns = ["id_*"]
EOF

uv run python -m check_unprotected_keys 2>/dev/null | grep -q real/id_rsa
echo "finding in real/: $?"
```

**Expect**: Finding only from `real/`; `noise/` pruned despite packaged defaults **not** merged.

---

## Scenario 3 — Ignore Wins on Overlap (US2 / FR-008)

Use default file ignores via omitted key:

```bash
TMP=$(mktemp -d)
mkdir -p "$TMP/keys"
printf 'ssh-rsa AAAA...\n' > "$TMP/keys/id_rsa.pub"
printf '-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n' > "$TMP/keys/id_rsa"

cd "$TMP"
cat > .check-unprotected-keys.toml <<'EOF'
[scan]
base_folders = ["."]
filename_patterns = ["id_*"]
EOF

uv run python -m check_unprotected_keys 2>&1 | tee /tmp/out.txt
grep -c id_rsa.pub /tmp/out.txt || true
```

**Expect**: Private key finding on stdout; `id_rsa.pub` not assessed (`files_scanned` excludes
pub sidecar when packaged `*.pub` ignore applies).

---

## Scenario 4 — Empty Array Disables Ignores (US3)

```bash
# Same tree as Scenario 3 but explicit empty file ignores
cat > .check-unprotected-keys.toml <<'EOF'
[scan]
base_folders = ["."]
ignore_filename_patterns = []
filename_patterns = ["id_*"]
EOF

uv run python -m check_unprotected_keys 2>&1 | tee /tmp/out2.txt
```

**Expect**: `files_scanned` increases vs Scenario 3 (pub file read/classified as non-finding).

---

## Scenario 5 — Partial Legacy Warning (FR-012)

```bash
cat > .check-unprotected-keys.toml <<'EOF'
[scan]
base_folders = ["."]
ignore_directories = ["my-custom-only"]
filename_patterns = ["id_*"]
EOF

uv run python -m check_unprotected_keys 2>&1 | head -5
```

**Expect**: stderr warning mentioning replace semantics / copying packaged defaults; scan still
runs.

---

## Automated Tests

```bash
# Loader + resolution
uv run --extra dev pytest tests/unit/test_config_loader.py -q --tb=line -k "ignore"

# Discovery filtering
uv run --extra dev pytest tests/unit/test_filesystem_discovery.py -q --tb=line -k "ignore"

# Integration regressions
uv run --extra dev pytest tests/integration/test_default_scan_workflow.py -q --tb=line
```

**Expect**: New tests cover replace/omit/empty, overlap skip, warning heuristic; existing
integration tests updated where `files_scanned` expectations change for pub sidecars.

---

## Quality Gates (post-implementation)

```bash
pytest --cov=src/check_unprotected_keys --cov-report=term-missing --cov-fail-under=85
ruff check src/ tests/
ruff format --check src/ tests/
pyright src/
```