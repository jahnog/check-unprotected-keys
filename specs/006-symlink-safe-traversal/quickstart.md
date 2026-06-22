# Quickstart Validation Guide: Symlink-Following, Cycle-Safe Folder Traversal

**Branch**: `006-symlink-safe-traversal` | **Date**: 2026-06-22

This guide describes how to validate the feature manually and confirms the end-to-end
scenarios from the spec. All scenarios use a temporary directory tree with real
filesystem structures. No real keys are needed — placeholder files with PEM headers
suffice to trigger unprotected-key detection.

---

## Prerequisites

```bash
# 1. Install the package in editable mode with dev dependencies
pip install -e ".[dev]"

# 2. Verify quality gates pass on main before this branch
pytest && ruff check src/ tests/ && ruff format --check src/ tests/ && pyright src/
```

---

## Setup: Minimal Configuration

All scenarios require a `.check-unprotected-keys.toml` in the working directory.
Use the broadest base so linked directories (wherever they point) are in scope:

```toml
[scan]
base_folders = ["."]
filename_patterns = ["*.key", "*.pem", "id_*"]
```

---

## Scenario 1 — Symlinked Directory: Keys Behind a Link Are Discovered

**Spec ref**: User Story 1, Acceptance Scenario 1

```bash
TMPDIR=$(mktemp -d)
REAL_DIR="$TMPDIR/real_secrets"
SCAN_DIR="$TMPDIR/workspace"

mkdir -p "$REAL_DIR" "$SCAN_DIR"

# Create an unprotected key placeholder in the real dir (outside workspace)
printf '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n' \
  > "$REAL_DIR/id_rsa"

# Link the real dir into the workspace
ln -s "$REAL_DIR" "$SCAN_DIR/linked_secrets"

cd "$SCAN_DIR"
cat > .check-unprotected-keys.toml <<EOF
[scan]
base_folders = ["."]
filename_patterns = ["id_*"]
EOF

check-unprotected-keys
```

**Expected**: The path to `id_rsa` (inside the linked directory) is reported on stdout.
Previously (before this feature) it would have been silently missed.

---

## Scenario 2 — Symlinked File: Link to a Key File Is Evaluated

**Spec ref**: User Story 1, Acceptance Scenario 2

```bash
TMPDIR=$(mktemp -d)
printf '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n' \
  > "$TMPDIR/real_id_rsa"

SCAN_DIR="$TMPDIR/workspace"
mkdir -p "$SCAN_DIR"
ln -s "$TMPDIR/real_id_rsa" "$SCAN_DIR/id_rsa_link"

cd "$SCAN_DIR"
cat > .check-unprotected-keys.toml <<EOF
[scan]
base_folders = ["."]
filename_patterns = ["id_*"]
EOF

check-unprotected-keys
```

**Expected**: The linked key file is reported as a finding.

---

## Scenario 3 — Cycle Detection: Self-Referential Link Terminates

**Spec ref**: User Story 2, Acceptance Scenario 1

```bash
SCAN_DIR=$(mktemp -d)
ln -s "$SCAN_DIR" "$SCAN_DIR/loop"  # self-referential link

printf '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n' \
  > "$SCAN_DIR/id_rsa"

cd "$SCAN_DIR"
cat > .check-unprotected-keys.toml <<EOF
[scan]
base_folders = ["."]
filename_patterns = ["id_*"]
EOF

check-unprotected-keys
```

**Expected**: Scan terminates promptly (not an infinite loop). `id_rsa` is reported
exactly once.

---

## Scenario 4 — Alias Detection: Two Links to Same Directory, Key Reported Once

**Spec ref**: User Story 2, Acceptance Scenario 4

```bash
TMPDIR=$(mktemp -d)
REAL_DIR="$TMPDIR/real"
SCAN_DIR="$TMPDIR/workspace"

mkdir -p "$REAL_DIR" "$SCAN_DIR"
printf '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n' \
  > "$REAL_DIR/id_rsa"

ln -s "$REAL_DIR" "$SCAN_DIR/link_a"
ln -s "$REAL_DIR" "$SCAN_DIR/link_b"

cd "$SCAN_DIR"
cat > .check-unprotected-keys.toml <<EOF
[scan]
base_folders = ["."]
filename_patterns = ["id_*"]
EOF

check-unprotected-keys
```

**Expected**: `id_rsa` appears exactly once on stdout. No duplicates.

---

## Scenario 5 — Broken Link: Scan Completes, Other Findings Still Reported

**Spec ref**: User Story 3, Acceptance Scenario 1

```bash
SCAN_DIR=$(mktemp -d)
ln -s "$SCAN_DIR/does_not_exist" "$SCAN_DIR/broken_link"
printf '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n' \
  > "$SCAN_DIR/id_rsa"

cd "$SCAN_DIR"
cat > .check-unprotected-keys.toml <<EOF
[scan]
base_folders = ["."]
filename_patterns = ["id_*"]
EOF

check-unprotected-keys
```

**Expected**: Scan completes (exit code 1 due to finding). `id_rsa` is reported.
The broken link produces no crash or abort.

---

## Scenario 6 — Hard Cap: Scan Aborts with Clear Error

**Spec ref**: FR-013

```bash
SCAN_DIR=$(mktemp -d)
# Create 5 real subdirectories
for i in 1 2 3 4 5; do mkdir "$SCAN_DIR/dir$i"; done

cd "$SCAN_DIR"
cat > .check-unprotected-keys.toml <<EOF
[scan]
base_folders = ["."]
filename_patterns = ["id_*"]
max_directory_visits = 3
EOF

check-unprotected-keys
echo "Exit code: $?"
```

**Expected**:
- Exit code: `2`
- Stderr contains a message including "directory visit limit" and "incomplete"
- Stdout: empty (no findings)

---

## Running the Automated Test Suite

After implementation, run the full suite to confirm coverage gate:

```bash
pytest
# Expect: 85%+ coverage, all tests pass

ruff check src/ tests/
ruff format --check src/ tests/
pyright src/
```

See `tests/integration/test_symlink_traversal.py` for the automated equivalents of the
manual scenarios above (using `pytest`'s `tmp_path` fixture for hermetic real-FS tests).
