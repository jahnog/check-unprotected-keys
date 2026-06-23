# Contract: `.properties` Secret Inspection

Defines the observable behavior of `.properties` content inspection: the
configuration surface, the per-entry decision order, the output format, and the
scan-accounting rules. This is the contract acceptance tests assert against.

## 1. Configuration contract (`[scan]` table)

- `filename_patterns` includes `*.properties` by default, selecting `.properties`
  files for inspection under the same authorized traversal and ignore rules as
  any candidate.
- `property_name_patterns` — array of secret-indicating property-name patterns.
  - **Omitted** → packaged default catalog applies.
  - **`[]`** → property-name matching disabled; no property is flagged on name
    grounds (inline key material is still assessed — see §3.1).
  - **Non-empty** → replaces the packaged catalog (replace semantics, matching
    `ignore_directories` / `ignore_filename_patterns`).
- Packaged default catalog (case-insensitive **substring** match over the full
  key): `password`, `passwd`, `pwd`, `pass`, `secret`, `private`, `key`,
  `token`, `credential`, `apikey`, `passphrase`.

## 2. Parsing contract

Input: the bytes of a `.properties` file (decoded UTF-8, Latin-1 fallback).
Output: an ordered sequence of `PropertyEntry(key, value, line_number)`.

- Lines whose first non-whitespace char is `#` or `!` are comments → skipped.
- Blank / whitespace-only lines → skipped.
- The key ends at the first unescaped `=`, `:`, or run of whitespace; the value
  is the remainder, leading whitespace trimmed.
- A line ending in an odd number of `\` continues onto the next line; leading
  whitespace of the continuation is trimmed before joining.
- Escapes applied: `\=`, `\:`, `\t`, `\n`, `\\`. (`\uXXXX` is out of scope.)
- Key matching is case-insensitive; surrounding whitespace is insignificant.

## 3. Per-entry decision order

For each `PropertyEntry`, evaluate in this exact order; the first match wins:

### 3.1 Inline key material (unconditional — FR-006)

If the value contains a `-----BEGIN` marker: unescape `\n`, reuse the key-material
parser. If the result is `UNPROTECTED` → **finding**
(`origin=INLINE_KEY_MATERIAL`). This branch ignores the key name.

### 3.2 Name gate

If the key does **not** match `property_name_patterns` → **not a finding** (stop).
The remaining rules require a name match.

### 3.3 Non-secret value kinds (FR-005)

If the value classifies as `EMPTY`, `PLACEHOLDER` (`${...}`, `@...@`, `#{...}`),
or `ENCRYPTED` (`ENC(...)`) → **not a finding** (stop).

### 3.4 Path-like value (FR-007)

If the value is `PATH_LIKE`: resolve it (relative → against the `.properties`
file's directory), canonicalize. Follow only if the file **exists** AND its
canonical path is within `scope.canonical_root_set`. If followed and the
referenced key file is `UNPROTECTED` → **finding** (`origin=REFERENCED_KEY_FILE`).
Missing or out-of-scope → **not a finding**, scan continues. The followed file is
reported to the caller for `files_scanned` accounting regardless of outcome.

### 3.5 Literal credential (FR-004)

If the value is a `LITERAL` that is credential-like — `len >= 6` AND Shannon
entropy `>= 2.5` AND not a pure boolean/integer — → **finding**
(`origin=PLAINTEXT_SECRET`). Otherwise → **not a finding**.

## 4. Output contract (FR-008/009, SC-003)

- Each finding emits exactly one stdout line: `<canonical file path>#<property key>`.
- A `.properties` file with N offending properties emits N stdout lines (one per
  property), each independently greppable.
- The secret **value** never appears on stdout, stderr, or in logs. Only the file
  path and the property key (a name) are emitted.
- stderr carries the existing summary + remediation, using the
  `embedded-config-secret` usage category.

### Example

Given `app.properties`:

```
spring.datasource.password=hunter2xyz
mail.host=${MAIL_HOST}
ssl.key.file=keys/server.key      # unprotected PEM, in-scope
db.password=${DB_PASSWORD}
audit.password.min.length=8
```

stdout (order follows discovery/parse order):

```
/abs/app.properties#spring.datasource.password
/abs/app.properties#ssl.key.file
```

Not emitted: `mail.host` (placeholder, name not secret anyway),
`db.password` (placeholder), `audit.password.min.length` (value `8` fails the
credential gate).

## 5. Accounting contract (FR-013)

- An inspected `.properties` file counts as 1 toward `files_scanned`.
- A key file reached only by following a reference (§3.4) counts toward
  `files_scanned` exactly once, deduplicated against directly-discovered
  candidates and against repeated references to the same file.

## 6. Failure handling

- `.properties` file unreadable (OSError) → recorded via the existing
  unreadable path; scan continues.
- Reference target unreadable → treated as not-a-finding for that property; scan
  continues.
- Scan never aborts on a single malformed entry, missing reference, or decode
  fallback.
